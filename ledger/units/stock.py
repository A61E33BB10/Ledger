"""
stock.py - Stock Unit with Dividend Processing

=== DIVIDEND MODEL ===

A Dividend has:
    ex_date: datetime          - When entitlements are computed
    payment_date: datetime     - When cash is paid (via DeferredCash)
    amount_per_share: Decimal  - Dividend amount
    currency: str              - Payment currency

On ex_date:
    - Compute entitlement for each holder: shares * amount_per_share
    - Create a DeferredCash unit for each holder
    - Mark dividend as processed

On payment_date:
    - DeferredCash settles automatically via lifecycle engine
    - We don't do anything - DeferredCash handles it

State format (trivially simple):
    processed_dividends: [div_key, ...]  - which dividends have been processed

=== PURE FUNCTION ===

The core logic is ONE pure function:
    compute_dividend_entitlements(div, today, positions, processed, issuer, symbol)
        -> (entitlements, new_processed)

This is trivially testable - no mocks needed.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, FrozenSet, List, Mapping, Optional, Tuple
from decimal import Decimal

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange,
    build_transaction, empty_pending_transaction,
    STOCK_DECIMAL_PLACES, DEFAULT_STOCK_SHORT_MIN_BALANCE,
    UNIT_TYPE_STOCK, QUANTITY_EPSILON, SYSTEM_WALLET,
    _freeze_state,
)
from .deferred_cash import create_deferred_cash_unit


@dataclass(frozen=True, slots=True)
class Dividend:
    """A scheduled dividend payment."""
    ex_date: datetime
    payment_date: datetime
    amount_per_share: Decimal
    currency: str

    def __post_init__(self):
        # Convert amount_per_share to Decimal if it's not already
        if not isinstance(self.amount_per_share, Decimal):
            object.__setattr__(self, 'amount_per_share', Decimal(str(self.amount_per_share)))

        if self.payment_date < self.ex_date:
            raise ValueError("payment_date must be >= ex_date")
        if self.amount_per_share <= Decimal("0"):
            raise ValueError("amount_per_share must be positive")

    @property
    def key(self) -> str:
        """Unique key: ISO date of ex_date."""
        return self.ex_date.date().isoformat()


@dataclass(frozen=True, slots=True)
class DividendEntitlement:
    """
    Instruction to create a DeferredCash unit for a dividend payment.

    This is what the pure function returns - a description of what to create.
    The orchestrator handles actual unit creation.
    """
    symbol: str           # e.g., "DIV_AAPL_2024-03-15_alice"
    amount: Decimal       # shares * amount_per_share
    currency: str
    payment_date: datetime
    payer_wallet: str     # issuer
    payee_wallet: str     # shareholder


@dataclass(frozen=True, slots=True)
class SplitAdjustment:
    """
    Instruction to adjust a position for a stock split.

    For longs: adjustment is positive (receive free shares from issuer)
    For shorts: adjustment is negative (owe more shares back)
    """
    wallet: str
    old_quantity: Decimal
    new_quantity: Decimal
    adjustment: Decimal  # new_quantity - old_quantity


@dataclass(frozen=True, slots=True)
class BorrowSplitAdjustment:
    """Instruction to adjust a BorrowRecord quantity for a stock split."""
    borrow_symbol: str
    old_quantity: Decimal
    new_quantity: Decimal


# =============================================================================
# PURE FUNCTIONS - The core logic, trivially testable
# =============================================================================

def compute_split_adjustments(
    ratio: Decimal,
    positions: Mapping[str, Decimal],
    borrow_records: Mapping[str, Decimal],
    issuer: str,
    decimal_places: int = STOCK_DECIMAL_PLACES,
) -> Tuple[List[SplitAdjustment], List[BorrowSplitAdjustment]]:
    """
    Compute all adjustments needed for a stock split. Pure function.

    In a stock split:
    - Long positions: holder receives free shares from issuer
    - Short positions: holder owes more shares (adjustment from holder to issuer)
    - Borrow obligations: quantity owed increases proportionally

    Args:
        ratio: Split ratio (2.0 = 2-for-1 forward, 0.5 = 1-for-2 reverse)
        positions: Current share positions {wallet: shares} (can be negative for shorts)
        borrow_records: Active borrow quantities {borrow_symbol: quantity}
        issuer: The issuer wallet (source/sink of shares)
        decimal_places: Rounding precision for fractional shares

    Returns:
        (position_adjustments, borrow_adjustments)

    Example (2-for-1 split):
        Alice owns 100 shares -> receives 100 more (now 200)
        Bob is short 50 shares -> owes 50 more (now short 100)
        Borrow of 30 shares -> obligation becomes 60

    Invariants:
        - Sum of adjustments from issuer = sum of adjustments to holders
        - Borrow obligations scale by ratio
        - Fractional shares rounded to decimal_places
    """
    # Ensure ratio is a Decimal
    if not isinstance(ratio, Decimal):
        ratio = Decimal(str(ratio))

    position_adjustments: List[SplitAdjustment] = []
    borrow_adjustments: List[BorrowSplitAdjustment] = []

    # Adjust share positions
    for wallet, shares in sorted(positions.items()):
        if wallet == issuer:
            continue
        if abs(shares) < QUANTITY_EPSILON:
            continue

        # Calculate new quantity with rounding
        new_shares = (shares * ratio).quantize(Decimal(10) ** -decimal_places)
        adjustment = new_shares - shares

        if abs(adjustment) > QUANTITY_EPSILON:
            position_adjustments.append(SplitAdjustment(
                wallet=wallet,
                old_quantity=shares,
                new_quantity=new_shares,
                adjustment=adjustment,
            ))

    # Adjust borrow record obligations
    for borrow_symbol, quantity in sorted(borrow_records.items()):
        if quantity < QUANTITY_EPSILON:
            continue

        new_quantity = (quantity * ratio).quantize(Decimal(10) ** -decimal_places)
        if abs(new_quantity - quantity) > QUANTITY_EPSILON:
            borrow_adjustments.append(BorrowSplitAdjustment(
                borrow_symbol=borrow_symbol,
                old_quantity=quantity,
                new_quantity=new_quantity,
            ))

    return position_adjustments, borrow_adjustments


def compute_dividend_entitlements(
    div: Dividend,
    today: date,
    positions: Mapping[str, Decimal],
    processed: FrozenSet[str],
    issuer: str,
    stock_symbol: str,
) -> Tuple[List[DividendEntitlement], FrozenSet[str]]:
    """
    Compute dividend entitlements on ex_date. Pure function.

    Args:
        div: The dividend to process
        today: Current date
        positions: Current share positions {wallet: shares}
        processed: Set of already-processed dividend keys
        issuer: The wallet that pays dividends
        stock_symbol: Symbol of the stock (for naming)

    Returns:
        (entitlements, new_processed)
        - entitlements: List of DeferredCash instructions to create
        - new_processed: Updated set of processed dividend keys

    Invariants:
        - Returns empty list if today < ex_date
        - Returns empty list if dividend already processed
        - Creates one entitlement per eligible holder
    """
    div_key = div.key

    # Already processed? Return unchanged.
    if div_key in processed:
        return [], processed

    # Not yet ex_date? Nothing to do.
    if today < div.ex_date.date():
        return [], processed

    # Process: create entitlement for each holder
    entitlements = []
    for wallet, shares in sorted(positions.items()):
        if wallet == issuer:
            continue
        if shares <= QUANTITY_EPSILON:
            continue

        amount = shares * div.amount_per_share
        entitlements.append(DividendEntitlement(
            symbol=f"DIV_{stock_symbol}_{div_key}_{wallet}",
            amount=amount,
            currency=div.currency,
            payment_date=div.payment_date,
            payer_wallet=issuer,
            payee_wallet=wallet,
        ))

    # Mark as processed
    new_processed = processed | {div_key}

    return entitlements, new_processed


# =============================================================================
# ORCHESTRATOR - Connects pure function to LedgerView
# =============================================================================

def process_dividends(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
) -> PendingTransaction:
    """
    Process all dividend events at timestamp.

    On ex_date, creates DeferredCash entitlements for each holder.
    The DeferredCash units settle automatically on payment_date.
    """
    state = view.get_unit_state(symbol)
    schedule: List[Dividend] = state.get('dividend_schedule', [])

    if not schedule:
        return empty_pending_transaction(view)

    issuer = state.get('issuer')
    if not issuer:
        raise ValueError(f"Stock {symbol} has no issuer defined")

    positions = view.get_positions(symbol)
    today = timestamp.date()
    processed = frozenset(state.get('processed_dividends', []))

    all_entitlements: List[DividendEntitlement] = []
    new_processed = processed

    for div in schedule:
        entitlements, new_processed = compute_dividend_entitlements(
            div=div,
            today=today,
            positions=positions,
            processed=new_processed,
            issuer=issuer,
            stock_symbol=symbol,
        )
        all_entitlements.extend(entitlements)

    if not all_entitlements:
        return empty_pending_transaction(view)

    # Create DeferredCash units and moves
    moves: List[Move] = []
    units_to_create: List[Unit] = []

    for ent in all_entitlements:
        # Create the DeferredCash unit
        dc_unit = create_deferred_cash_unit(
            symbol=ent.symbol,
            amount=ent.amount,
            currency=ent.currency,
            payment_date=ent.payment_date,
            payer_wallet=ent.payer_wallet,
            payee_wallet=ent.payee_wallet,
            reference=f"{symbol}_dividend_{ent.symbol}",
        )
        units_to_create.append(dc_unit)

        # Move entitlement from system to payee
        moves.append(Move(
            quantity=Decimal("1"),
            unit_symbol=ent.symbol,
            source=SYSTEM_WALLET,
            dest=ent.payee_wallet,
            contract_id=f'dividend_entitlement_{ent.symbol}',
        ))

    # Update state
    new_state = {
        **state,
        'processed_dividends': list(new_processed),
    }
    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes, units_to_create=tuple(units_to_create))


# =============================================================================
# STOCK UNIT FACTORY
# =============================================================================

def create_stock_unit(
    symbol: str,
    name: str,
    issuer: str,
    currency: str,
    dividend_schedule: Optional[List[Dividend]] = None,
    shortable: bool = False,
) -> Unit:
    """
    Create a stock unit.

    Args:
        symbol: Stock identifier (e.g., "AAPL")
        name: Human-readable name
        issuer: Wallet that pays dividends
        currency: Default currency (stock's denomination)
        dividend_schedule: List of Dividend objects
        shortable: Allow negative balances (short selling)
    """
    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_STOCK,
        min_balance=DEFAULT_STOCK_SHORT_MIN_BALANCE if shortable else Decimal("0"),
        max_balance=Decimal("Infinity"),
        decimal_places=STOCK_DECIMAL_PLACES,
        _frozen_state=_freeze_state({
            'issuer': issuer,
            'currency': currency,
            'shortable': shortable,
            'dividend_schedule': dividend_schedule or [],
            'processed_dividends': [],
        })
    )


# =============================================================================
# OTHER STOCK OPERATIONS
# =============================================================================

def compute_stock_split(
    view: LedgerView,
    symbol: str,
    ratio: Decimal,
    split_date: Optional[datetime] = None,
) -> PendingTransaction:
    """
    Execute a stock split with full balance adjustments.

    In a stock split:
    - Long holders receive free shares from the issuer
    - Short holders owe additional shares to the issuer
    - BorrowRecord obligations are adjusted proportionally

    Args:
        view: Read-only ledger access
        symbol: Stock symbol
        ratio: Split ratio (2.0 = 2-for-1, 0.5 = 1-for-2 reverse)
        split_date: When the split occurs (defaults to current time)

    Returns:
        PendingTransaction with share moves and state updates

    Example (2-for-1 split):
        Alice owns 100 AAPL -> Move(100, AAPL, issuer, alice) -> 200 shares
        Bob borrowed 50 from Carol -> BorrowRecord quantity: 50 -> 100
    """
    # Ensure ratio is a Decimal
    if not isinstance(ratio, Decimal):
        ratio = Decimal(str(ratio))

    if ratio <= Decimal("0"):
        raise ValueError(f"Split ratio must be positive, got {ratio}")

    state = view.get_unit_state(symbol)
    issuer = state.get('issuer')
    if not issuer:
        raise ValueError(f"Stock {symbol} has no issuer defined")

    # Get current positions
    positions = view.get_positions(symbol)

    # Get active borrow records for this stock
    borrow_records: Dict[str, Decimal] = {}
    if hasattr(view, 'list_units'):
        prefix = f"BORROW_{symbol}_"
        for unit_symbol in view.list_units():
            if not unit_symbol.startswith(prefix):
                continue
            borrow_state = view.get_unit_state(unit_symbol)
            # Skip closed borrows
            if borrow_state.get('status') in ('returned', 'bought_in'):
                continue
            quantity = borrow_state.get('quantity', Decimal("0"))
            if not isinstance(quantity, Decimal):
                quantity = Decimal(str(quantity))
            borrow_records[unit_symbol] = quantity

    # Get unit for decimal places
    unit = view.get_unit(symbol)

    # Compute adjustments using pure function
    position_adjs, borrow_adjs = compute_split_adjustments(
        ratio=ratio,
        positions=positions,
        borrow_records=borrow_records,
        issuer=issuer,
        decimal_places=unit.decimal_places,
    )

    moves: List[Move] = []
    state_changes: List[UnitStateChange] = []
    effective_date = split_date or view.current_time
    split_key = effective_date.strftime("%Y-%m-%d")

    # Create moves for position adjustments
    for adj in position_adjs:
        if adj.adjustment > 0:
            # Long position: issuer sends shares to holder
            moves.append(Move(
                quantity=adj.adjustment,
                unit_symbol=symbol,
                source=issuer,
                dest=adj.wallet,
                contract_id=f"split_{symbol}_{split_key}_{adj.wallet}",
            ))
        else:
            # Short position: holder returns shares to issuer
            moves.append(Move(
                quantity=-adj.adjustment,
                unit_symbol=symbol,
                source=adj.wallet,
                dest=issuer,
                contract_id=f"split_{symbol}_{split_key}_{adj.wallet}",
            ))

    # Create state changes for borrow record adjustments
    for borrow_adj in borrow_adjs:
        borrow_state = view.get_unit_state(borrow_adj.borrow_symbol)
        new_borrow_state = {
            **borrow_state,
            'quantity': borrow_adj.new_quantity,
            'split_adjusted': True,
            'last_split_date': effective_date,
            'last_split_ratio': ratio,
        }
        state_changes.append(UnitStateChange(
            unit=borrow_adj.borrow_symbol,
            old_state=borrow_state,
            new_state=new_borrow_state,
        ))

    # Update stock state with split record
    split_history = list(state.get('split_history', []))
    split_history.append({
        'date': effective_date,
        'ratio': ratio,
    })
    new_state = {
        **state,
        'last_split_ratio': ratio,
        'last_split_date': effective_date,
        'split_history': split_history,
    }
    state_changes.append(UnitStateChange(unit=symbol, old_state=state, new_state=new_state))

    return build_transaction(view, moves, state_changes)


def transact(
    view: LedgerView,
    symbol: str,
    seller: str,
    buyer: str,
    qty: Decimal,
    price: Decimal,
) -> PendingTransaction:
    """
    Execute a stock trade (DVP settlement).

    Creates two moves:
    1. Stock: seller -> buyer
    2. Cash: buyer -> seller
    """
    # Ensure qty and price are Decimals
    if not isinstance(qty, Decimal):
        qty = Decimal(str(qty))
    if not isinstance(price, Decimal):
        price = Decimal(str(price))

    if qty <= Decimal("0"):
        raise ValueError(f"qty must be positive, got {qty}")
    if not price.is_finite() or price <= Decimal("0"):
        raise ValueError(f"price must be positive and finite, got {price}")
    if seller == buyer:
        raise ValueError("seller and buyer must be different")

    state = view.get_unit_state(symbol)
    currency = state.get('currency', 'USD')

    unit = view.get_unit(symbol)
    seller_balance = view.get_balance(seller, symbol)
    if seller_balance - qty < unit.min_balance - QUANTITY_EPSILON:
        raise ValueError(f"Insufficient shares: {seller} has {seller_balance}, needs {qty}")

    moves = [
        Move(qty, symbol, seller, buyer, f'stock_{symbol}_shares'),
        Move(qty * price, currency, buyer, seller, f'stock_{symbol}_cash'),
    ]
    return build_transaction(view, moves)


def stock_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, Decimal],
) -> PendingTransaction:
    """SmartContract for LifecycleEngine: process dividends."""
    return process_dividends(view, symbol, timestamp)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def add_dividend(state: dict, dividend: Dividend) -> dict:
    """Add a dividend to a stock's schedule. Pure function."""
    schedule = list(state.get('dividend_schedule', []))
    schedule.append(dividend)
    return {**state, 'dividend_schedule': schedule}


def remove_dividend(state: dict, ex_date: datetime) -> dict:
    """Remove a dividend from a stock's schedule by ex_date. Pure function."""
    schedule = state.get('dividend_schedule', [])
    key = ex_date.date().isoformat()
    new_schedule = [d for d in schedule if d.key != key]
    return {**state, 'dividend_schedule': new_schedule}


