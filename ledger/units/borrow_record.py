"""
borrow_record.py - Securities Borrowing and Lending (SBL) Record Unit

=== SBL MODEL ===

A BorrowRecord represents a securities lending liability:
    - Borrower received shares from Lender
    - Borrower must return shares on demand (or at term end)
    - Borrower pays fees to Lender (via DeferredCash)

When a borrow is initiated:
    1. Shares move: lender -> borrower
    2. BorrowRecord created (tracks the liability)
    3. BorrowRecord assigned to borrower (holder of the obligation)

When shares are returned:
    1. Shares move: borrower -> lender
    2. BorrowRecord extinguished (borrower -> system)
    3. Final fee settlement via DeferredCash

=== AVAILABLE POSITION ===

The key invariant for short selling:

    Available_Position = Owned_Shares - Borrow_Obligations >= 0

A borrower cannot sell more shares than they own minus what they owe.
This prevents naked short selling.

=== PURE FUNCTIONS ===

Core logic in pure functions:
    compute_available_position(view, wallet, stock) -> float
    compute_borrow_fee(quantity, rate_bps, days) -> float
    validate_short_sale(view, seller, stock, qty) -> bool

All trivially testable with FakeView.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange,
    build_transaction, empty_pending_transaction,
    SYSTEM_WALLET, QUANTITY_EPSILON, UNIT_TYPE_BORROW_RECORD,
)
from .deferred_cash import create_deferred_cash_unit


# =============================================================================
# CONSTANTS
# =============================================================================

# Default collateral margin (102% = shares worth $100 require $102 collateral)
DEFAULT_COLLATERAL_MARGIN = 1.02

# Default borrow rate in basis points (50 bps = 0.5% annualized)
DEFAULT_BORROW_RATE_BPS = 50


# =============================================================================
# ENUMS
# =============================================================================

class BorrowStatus(str, Enum):
    """Status of a borrow record."""
    ACTIVE = "active"           # Shares borrowed, liability open
    RECALLED = "recalled"       # Lender requested return
    RETURNED = "returned"       # Shares returned, closed
    BOUGHT_IN = "bought_in"     # Force-closed due to failure to return


class ContractType(str, Enum):
    """Type of borrow contract."""
    OPEN = "open"           # Callable on demand by lender
    TERM = "term"           # Fixed term, not callable until maturity
    OVERNIGHT = "overnight" # Must be returned or rolled next day


# =============================================================================
# PURE FUNCTIONS
# =============================================================================

def compute_available_position(
    view: LedgerView,
    wallet: str,
    stock_symbol: str,
) -> float:
    """
    Compute shares available for sale or delivery.

    Available = Owned - Borrowed_Obligations

    A wallet can only sell/deliver shares it actually has available,
    not shares it owes to lenders.

    Args:
        view: Read-only ledger access
        wallet: Wallet to check
        stock_symbol: Stock to check

    Returns:
        Number of shares available (can be negative if over-borrowed)

    Example:
        Alice owns 100 AAPL, borrowed 50 from Bob (owes 50 back)
        Available = 100 - 50 = 50 shares she can sell
    """
    # Get owned shares (could be negative if short)
    owned = view.get_balance(wallet, stock_symbol)

    # Sum all active borrow obligations for this stock
    # BorrowRecords are named: BORROW_{stock}_{borrower}_{lender}_{id}
    borrow_obligations = 0.0

    # Find BorrowRecord units by checking all units that match the pattern
    # and seeing if this wallet holds them
    # Pattern: BORROW_{stock}_{borrower}_{lender}_{id}
    prefix = f"BORROW_{stock_symbol}_{wallet}_"

    # We need to iterate over potential borrow records
    # Use get_positions on each potential borrow record symbol
    # The challenge: we don't have list_units in LedgerView
    # Solution: Check the borrow records we know about by trying to get their state
    # This is a limitation - in practice, the Ledger implementation has list_units()

    # For now, use a workaround: get all positions for potential borrow record symbols
    # by iterating through known units. Since Ledger implements LedgerView and has
    # list_units(), we can use duck typing here.
    if hasattr(view, 'list_units'):
        for symbol in view.list_units():
            if not symbol.startswith(prefix):
                continue

            # Check if wallet holds this BorrowRecord
            balance = view.get_balance(wallet, symbol)
            if balance < QUANTITY_EPSILON:
                continue

            # This is a BorrowRecord for this stock held by this wallet
            state = view.get_unit_state(symbol)
            if state.get('status') in (BorrowStatus.RETURNED.value, BorrowStatus.BOUGHT_IN.value):
                continue  # Already closed

            # Add the obligation quantity
            borrow_obligations += state.get('quantity', 0.0)

    return owned - borrow_obligations


def compute_borrow_fee(
    quantity: float,
    rate_bps: float,
    days: int,
    price: float,
) -> float:
    """
    Compute borrow fee for a period.

    Fee = quantity * price * (rate_bps / 10000) * (days / 365)

    Args:
        quantity: Number of shares borrowed
        rate_bps: Annualized rate in basis points
        days: Number of days
        price: Current share price

    Returns:
        Fee amount in currency units

    Example:
        1000 shares at $100, 50 bps rate, 30 days
        Fee = 1000 * 100 * (50/10000) * (30/365) = $41.10
    """
    if quantity <= 0 or days <= 0 or price <= 0:
        return 0.0
    annual_rate = rate_bps / 10000.0
    return quantity * price * annual_rate * (days / 365.0)


def compute_required_collateral(
    quantity: float,
    price: float,
    margin: float = DEFAULT_COLLATERAL_MARGIN,
) -> float:
    """
    Compute required collateral for a borrow.

    Collateral = quantity * price * margin

    Args:
        quantity: Number of shares borrowed
        price: Current share price
        margin: Collateral margin (e.g., 1.02 for 102%)

    Returns:
        Required collateral amount

    Example:
        1000 shares at $100 with 102% margin
        Collateral = 1000 * 100 * 1.02 = $102,000
    """
    if quantity <= 0 or price <= 0:
        return 0.0
    return quantity * price * margin


def validate_short_sale(
    view: LedgerView,
    seller: str,
    stock_symbol: str,
    quantity: float,
) -> Tuple[bool, str]:
    """
    Validate if a short sale is permitted.

    A short sale is permitted if:
        Available_Position - quantity >= 0

    OR if the seller already has a borrow in place covering the sale.

    Args:
        view: Read-only ledger access
        seller: Wallet attempting to sell
        stock_symbol: Stock being sold
        quantity: Number of shares to sell

    Returns:
        (is_valid, reason) tuple

    Example:
        Alice has 50 available AAPL, tries to sell 100
        -> (False, "Insufficient available position: 50 < 100")
    """
    if quantity <= 0:
        return False, "Quantity must be positive"

    available = compute_available_position(view, seller, stock_symbol)

    if available >= quantity - QUANTITY_EPSILON:
        return True, "Sufficient available position"

    shortfall = quantity - max(0.0, available)
    return False, f"Insufficient available position: {available:.2f} available, need {quantity:.2f} (shortfall: {shortfall:.2f})"


# =============================================================================
# BORROW RECORD FACTORY
# =============================================================================

def create_borrow_record_unit(
    stock_symbol: str,
    borrower: str,
    lender: str,
    quantity: float,
    borrow_date: datetime,
    rate_bps: float = DEFAULT_BORROW_RATE_BPS,
    contract_type: ContractType = ContractType.OPEN,
    collateral_currency: str = "USD",
    collateral_amount: float = 0.0,
    term_end_date: Optional[datetime] = None,
    borrow_id: Optional[str] = None,
) -> Unit:
    """
    Create a BorrowRecord unit representing a securities lending liability.

    The BorrowRecord is a first-class unit that tracks:
    - Who borrowed from whom
    - How many shares
    - The fee rate
    - Collateral posted
    - Current status (active, recalled, returned)

    Args:
        stock_symbol: The stock being borrowed (e.g., "AAPL")
        borrower: Wallet receiving the shares
        lender: Wallet lending the shares
        quantity: Number of shares borrowed
        borrow_date: When the borrow was initiated
        rate_bps: Annualized fee rate in basis points
        contract_type: OPEN (callable), TERM (fixed), or OVERNIGHT
        collateral_currency: Currency for collateral (default USD)
        collateral_amount: Initial collateral posted
        term_end_date: For TERM contracts, when it matures
        borrow_id: Optional unique ID (auto-generated if not provided)

    Returns:
        Unit configured as a BorrowRecord

    Example:
        # Alice borrows 1000 AAPL from Bob
        borrow = create_borrow_record_unit(
            stock_symbol="AAPL",
            borrower="alice",
            lender="bob",
            quantity=1000,
            borrow_date=datetime(2024, 3, 15),
            rate_bps=50,
        )
        ledger.register_unit(borrow)
        # Move the record to the borrower
        ledger.execute(build_transaction(view, [
            Move(1, borrow.symbol, "system", "alice", "borrow_initiate")
        ]))
    """
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")
    if borrower == lender:
        raise ValueError("borrower and lender must be different")
    if rate_bps < 0:
        raise ValueError(f"rate_bps cannot be negative, got {rate_bps}")

    # Generate unique symbol if not provided
    if borrow_id is None:
        borrow_id = borrow_date.strftime("%Y%m%d%H%M%S")

    symbol = f"BORROW_{stock_symbol}_{borrower}_{lender}_{borrow_id}"

    return Unit(
        symbol=symbol,
        name=f"Borrow: {quantity:.0f} {stock_symbol} ({borrower} from {lender})",
        unit_type=UNIT_TYPE_BORROW_RECORD,
        min_balance=-1.0,  # Allow system extinguishment
        max_balance=1.0,   # Quantity is always 1 (like DeferredCash)
        decimal_places=0,
        transfer_rule=None,
        _state={
            'stock_symbol': stock_symbol,
            'borrower': borrower,
            'lender': lender,
            'quantity': quantity,
            'borrow_date': borrow_date,
            'rate_bps': rate_bps,
            'contract_type': contract_type.value,
            'collateral_currency': collateral_currency,
            'collateral_amount': collateral_amount,
            'term_end_date': term_end_date,
            'status': BorrowStatus.ACTIVE.value,
            'recall_notice_date': None,
            'recall_due_date': None,
            'return_date': None,
            'accrued_fees': 0.0,
            'last_fee_date': borrow_date,
        }
    )


# =============================================================================
# BORROW INITIATION
# =============================================================================

def initiate_borrow(
    view: LedgerView,
    stock_symbol: str,
    borrower: str,
    lender: str,
    quantity: float,
    rate_bps: float = DEFAULT_BORROW_RATE_BPS,
    contract_type: ContractType = ContractType.OPEN,
    borrow_id: Optional[str] = None,
) -> PendingTransaction:
    """
    Initiate a securities borrow.

    This creates:
    1. Move: shares from lender to borrower
    2. BorrowRecord unit tracking the liability

    Args:
        view: Read-only ledger access
        stock_symbol: Stock to borrow
        borrower: Wallet receiving shares
        lender: Wallet lending shares
        quantity: Number of shares
        rate_bps: Fee rate in basis points
        contract_type: Type of borrow contract
        borrow_id: Optional unique ID

    Returns:
        PendingTransaction with share move and BorrowRecord creation

    Example:
        result = initiate_borrow(view, "AAPL", "alice", "bob", 1000)
        ledger.execute(result)
        # Alice now has 1000 AAPL and owes them back to Bob
    """
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")

    # Check lender has sufficient shares
    lender_balance = view.get_balance(lender, stock_symbol)
    if lender_balance < quantity - QUANTITY_EPSILON:
        raise ValueError(
            f"Lender {lender} has insufficient {stock_symbol}: "
            f"{lender_balance:.2f} < {quantity:.2f}"
        )

    timestamp = view.current_time

    # Create BorrowRecord unit
    borrow_unit = create_borrow_record_unit(
        stock_symbol=stock_symbol,
        borrower=borrower,
        lender=lender,
        quantity=quantity,
        borrow_date=timestamp,
        rate_bps=rate_bps,
        contract_type=contract_type,
        borrow_id=borrow_id,
    )

    # Moves:
    # 1. Shares: lender -> borrower
    # 2. BorrowRecord: system -> borrower (assigns the liability)
    moves = [
        Move(
            quantity=quantity,
            unit_symbol=stock_symbol,
            source=lender,
            dest=borrower,
            contract_id=f"borrow_{borrow_unit.symbol}_shares",
        ),
        Move(
            quantity=1.0,
            unit_symbol=borrow_unit.symbol,
            source=SYSTEM_WALLET,
            dest=borrower,
            contract_id=f"borrow_{borrow_unit.symbol}_record",
        ),
    ]

    return build_transaction(view, moves, units_to_create=(borrow_unit,))


# =============================================================================
# BORROW RETURN
# =============================================================================

def compute_borrow_return(
    view: LedgerView,
    borrow_symbol: str,
    return_time: datetime,
    final_price: float = 0.0,
) -> PendingTransaction:
    """
    Return borrowed shares and close the borrow.

    This creates:
    1. Move: shares from borrower to lender
    2. Move: BorrowRecord from borrower to system (extinguish)
    3. State update: status -> RETURNED
    4. DeferredCash for any accrued fees (if final_price provided)

    Args:
        view: Read-only ledger access
        borrow_symbol: Symbol of the BorrowRecord unit
        return_time: When the return is executed
        final_price: Current share price (for fee calculation)

    Returns:
        PendingTransaction with return moves

    Example:
        result = compute_borrow_return(view, "BORROW_AAPL_alice_bob_001", now, 150.0)
        ledger.execute(result)
        # Alice returns shares to Bob, borrow is closed
    """
    state = view.get_unit_state(borrow_symbol)

    # Check if already returned
    if state.get('status') in (BorrowStatus.RETURNED.value, BorrowStatus.BOUGHT_IN.value):
        return empty_pending_transaction(view)

    stock_symbol = state['stock_symbol']
    borrower = state['borrower']
    lender = state['lender']
    quantity = state['quantity']

    # Check borrower has the shares to return
    borrower_balance = view.get_balance(borrower, stock_symbol)
    if borrower_balance < quantity - QUANTITY_EPSILON:
        raise ValueError(
            f"Borrower {borrower} has insufficient {stock_symbol} to return: "
            f"{borrower_balance:.2f} < {quantity:.2f}"
        )

    # Check borrower holds the BorrowRecord
    borrow_balance = view.get_balance(borrower, borrow_symbol)
    if borrow_balance < 1 - QUANTITY_EPSILON:
        raise ValueError(f"Borrower {borrower} does not hold {borrow_symbol}")

    # Calculate final fees
    borrow_date = state['borrow_date']
    last_fee_date = state.get('last_fee_date', borrow_date)
    rate_bps = state['rate_bps']
    days_since_last = (return_time - last_fee_date).days
    final_fee = compute_borrow_fee(quantity, rate_bps, days_since_last, final_price) if final_price > 0 else 0.0
    total_fees = state.get('accrued_fees', 0.0) + final_fee

    moves = [
        # Return shares to lender
        Move(
            quantity=quantity,
            unit_symbol=stock_symbol,
            source=borrower,
            dest=lender,
            contract_id=f"return_{borrow_symbol}_shares",
        ),
        # Extinguish the BorrowRecord
        Move(
            quantity=1.0,
            unit_symbol=borrow_symbol,
            source=borrower,
            dest=SYSTEM_WALLET,
            contract_id=f"return_{borrow_symbol}_record",
        ),
    ]

    units_to_create: List[Unit] = []

    # Create DeferredCash for fees if any
    if total_fees > QUANTITY_EPSILON:
        fee_dc = create_deferred_cash_unit(
            symbol=f"FEE_{borrow_symbol}",
            amount=total_fees,
            currency=state.get('collateral_currency', 'USD'),
            payment_date=return_time,  # Due immediately
            payer_wallet=borrower,
            payee_wallet=lender,
            reference=f"borrow_fee_{borrow_symbol}",
        )
        units_to_create.append(fee_dc)
        moves.append(Move(
            quantity=1.0,
            unit_symbol=fee_dc.symbol,
            source=SYSTEM_WALLET,
            dest=borrower,
            contract_id=f"return_{borrow_symbol}_fee",
        ))

    # Update state
    new_state = {
        **state,
        'status': BorrowStatus.RETURNED.value,
        'return_date': return_time,
        'accrued_fees': total_fees,
    }
    state_changes = [UnitStateChange(unit=borrow_symbol, old_state=state, new_state=new_state)]

    return build_transaction(
        view, moves, state_changes,
        units_to_create=tuple(units_to_create) if units_to_create else None,
    )


# =============================================================================
# RECALL MANAGEMENT
# =============================================================================

def initiate_recall(
    view: LedgerView,
    borrow_symbol: str,
    recall_date: datetime,
    settlement_days: int = 2,
) -> PendingTransaction:
    """
    Lender initiates a recall (requests shares back).

    This updates the BorrowRecord state with recall notice and due date.
    The borrower must return shares by the due date or face buy-in.

    Args:
        view: Read-only ledger access
        borrow_symbol: Symbol of the BorrowRecord
        recall_date: When the recall notice is issued
        settlement_days: Days until shares must be returned (default T+2)

    Returns:
        PendingTransaction with state update

    Example:
        result = initiate_recall(view, "BORROW_AAPL_alice_bob_001", now)
        ledger.execute(result)
        # Bob has recalled his shares, Alice must return within T+2
    """
    state = view.get_unit_state(borrow_symbol)

    if state.get('status') != BorrowStatus.ACTIVE.value:
        return empty_pending_transaction(view)

    # Check contract type allows recall
    if state.get('contract_type') == ContractType.TERM.value:
        term_end = state.get('term_end_date')
        if term_end and recall_date < term_end:
            raise ValueError(
                f"Cannot recall TERM borrow before {term_end}, current date is {recall_date}"
            )

    recall_due = recall_date + timedelta(days=settlement_days)

    new_state = {
        **state,
        'status': BorrowStatus.RECALLED.value,
        'recall_notice_date': recall_date,
        'recall_due_date': recall_due,
    }
    state_changes = [UnitStateChange(unit=borrow_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, [], state_changes)


# =============================================================================
# LIFECYCLE CONTRACT
# =============================================================================

def borrow_record_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float],
) -> PendingTransaction:
    """
    SmartContract interface for BorrowRecord with LifecycleEngine.

    This handles:
    - Daily fee accrual (creates DeferredCash for periodic fees)
    - Recall deadline enforcement (future: auto buy-in)

    Currently this is a stub - fee accrual will be added in Phase 3.

    Args:
        view: Read-only ledger access
        symbol: BorrowRecord symbol
        timestamp: Current time
        prices: Current prices (for mark-to-market)

    Returns:
        PendingTransaction with any lifecycle actions
    """
    state = view.get_unit_state(symbol)

    # Skip if already closed
    if state.get('status') in (BorrowStatus.RETURNED.value, BorrowStatus.BOUGHT_IN.value):
        return empty_pending_transaction(view)

    # Future: check recall deadline and trigger buy-in
    # Future: daily fee accrual

    return empty_pending_transaction(view)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_active_borrows(
    view: LedgerView,
    wallet: str,
    stock_symbol: Optional[str] = None,
) -> List[str]:
    """
    Get all active BorrowRecord symbols for a wallet.

    Args:
        view: Read-only ledger access
        wallet: Wallet to check
        stock_symbol: Optional filter by stock

    Returns:
        List of BorrowRecord symbols
    """
    active = []

    # Build prefix for filtering
    if stock_symbol:
        prefix = f"BORROW_{stock_symbol}_{wallet}_"
    else:
        prefix = f"BORROW_"

    # Iterate over all units to find BorrowRecords
    if hasattr(view, 'list_units'):
        for symbol in view.list_units():
            if not symbol.startswith(prefix):
                continue

            # For non-stock-specific search, verify this is for the wallet
            if not stock_symbol and f"_{wallet}_" not in symbol:
                continue

            # Check if wallet holds this BorrowRecord
            balance = view.get_balance(wallet, symbol)
            if balance < QUANTITY_EPSILON:
                continue

            state = view.get_unit_state(symbol)
            if state.get('status') not in (BorrowStatus.RETURNED.value, BorrowStatus.BOUGHT_IN.value):
                active.append(symbol)

    return active


def get_total_borrowed(
    view: LedgerView,
    wallet: str,
    stock_symbol: str,
) -> float:
    """
    Get total shares borrowed by a wallet for a stock.

    Args:
        view: Read-only ledger access
        wallet: Wallet to check
        stock_symbol: Stock to check

    Returns:
        Total borrowed quantity
    """
    total = 0.0
    for borrow_symbol in get_active_borrows(view, wallet, stock_symbol):
        state = view.get_unit_state(borrow_symbol)
        total += state.get('quantity', 0.0)
    return total
