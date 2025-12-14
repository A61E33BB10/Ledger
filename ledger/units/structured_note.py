"""
structured_note.py - Structured Notes with Principal Protection and Participation

This module provides structured note creation and lifecycle processing:
1. create_structured_note() - Factory for structured notes with payoff parameters
2. compute_performance() - Calculate underlying performance vs strike
3. compute_payoff_rate() - Calculate return rate based on participation, cap, protection
4. compute_coupon_payment() - Process optional periodic coupon payments
5. compute_maturity_payoff() - Final settlement at maturity
6. transact() - Event-driven interface for COUPON and MATURITY events
7. structured_note_contract() - SmartContract for LifecycleEngine integration

A structured note is a debt instrument with embedded options:
- Principal Protection: Floor on return (typically 90-100%)
- Participation Rate: Upside capture (e.g., 80% of index gains)
- Cap: Maximum return (e.g., 25% over term)
- Coupons: Optional periodic payments

Payoff Formula:
    performance = (final_price - strike_price) / strike_price

    if performance > 0:
        # Upside: participate up to cap
        return_rate = min(participation_rate * performance, cap_rate)
                      if cap_rate else participation_rate * performance
    else:
        # Downside: protected to floor
        return_rate = max(performance, protection_level - 1.0)

    payout = notional * (1 + return_rate)

All functions take LedgerView (read-only) and return immutable results.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from decimal import Decimal

import math

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange,
    UNIT_TYPE_STRUCTURED_NOTE, QUANTITY_EPSILON,
    build_transaction, empty_pending_transaction,
    _freeze_state,
)


# Type alias for coupon schedule
CouponSchedule = List[Tuple[datetime, Decimal]]


# ============================================================================
# COUPON SCHEDULE GENERATION
# ============================================================================

def generate_structured_note_coupon_schedule(
    issue_date: datetime,
    maturity_date: datetime,
    coupon_rate: Decimal,
    notional: Decimal,
    frequency: int,
) -> CouponSchedule:
    """
    Generate a coupon payment schedule for a structured note.

    Args:
        issue_date: Note issue date.
        maturity_date: Note maturity date.
        coupon_rate: Annual coupon rate (e.g., 0.02 for 2%).
        notional: Principal amount.
        frequency: Payments per year (0=no coupons, 1=annual, 2=semi-annual,
                   4=quarterly, 12=monthly).

    Returns:
        List of (payment_date, coupon_amount) tuples. Empty list if frequency=0.

    Raises:
        ValueError: If frequency is not 0, 1, 2, 4, or 12.

    Example:
        >>> schedule = generate_structured_note_coupon_schedule(
        ...     issue_date=datetime(2024, 1, 15),
        ...     maturity_date=datetime(2025, 1, 15),
        ...     coupon_rate=0.02,
        ...     notional=100000.0,
        ...     frequency=2,
        ... )
        >>> len(schedule)
        2
        >>> schedule[0][1]  # coupon amount
        1000.0
    """
    if frequency == 0:
        return []

    if frequency not in [1, 2, 4, 12]:
        raise ValueError(f"Frequency must be 0, 1, 2, 4, or 12, got {frequency}")

    # Ensure parameters are Decimal
    notional = Decimal(str(notional)) if not isinstance(notional, Decimal) else notional
    coupon_rate = Decimal(str(coupon_rate)) if not isinstance(coupon_rate, Decimal) else coupon_rate

    schedule: CouponSchedule = []
    months_between = 12 // frequency
    coupon_amount = (notional * coupon_rate) / Decimal(frequency)

    current_date = issue_date

    while True:
        month = current_date.month + months_between
        year = current_date.year

        while month > 12:
            month -= 12
            year += 1

        try:
            next_date = current_date.replace(year=year, month=month)
        except ValueError:
            # Handle day overflow (e.g., Jan 31 -> Feb 31)
            if month == 12:
                next_month = 1
                next_year = year + 1
            else:
                next_month = month + 1
                next_year = year

            from datetime import timedelta
            next_date = datetime(next_year, next_month, 1) - timedelta(days=1)
            next_date = next_date.replace(
                hour=current_date.hour, minute=current_date.minute
            )

        current_date = next_date

        if current_date > maturity_date:
            break

        schedule.append((current_date, coupon_amount))

    return schedule


# ============================================================================
# STRUCTURED NOTE UNIT CREATION
# ============================================================================

def create_structured_note(
    symbol: str,
    name: str,
    underlying: str,
    notional: Decimal,
    strike_price: Decimal,
    participation_rate: Decimal,
    protection_level: Decimal,
    issue_date: datetime,
    maturity_date: datetime,
    currency: str,
    issuer_wallet: str,
    holder_wallet: str,
    cap_rate: Optional[Decimal] = None,
    coupon_rate: Decimal = Decimal("0.0"),
    coupon_frequency: int = 0,
    coupon_schedule: Optional[CouponSchedule] = None,
) -> Unit:
    """
    Create a structured note unit with embedded option payoff.

    A structured note combines a debt instrument with derivative-like payoffs:
    - Principal protection provides a floor on losses
    - Participation rate determines upside capture
    - Optional cap limits maximum return
    - Optional coupons provide periodic income

    Args:
        symbol: Unique identifier for the structured note (e.g., "SN_SPX_2025").
        name: Human-readable name (e.g., "S&P 500 Principal Protected Note").
        underlying: Symbol of the underlying asset (e.g., "SPX").
        notional: Principal amount invested.
        strike_price: Reference level for calculating performance.
        participation_rate: Fraction of upside captured (e.g., 0.80 for 80%).
        protection_level: Fraction of principal protected (e.g., 0.90 for 90%).
        issue_date: Note issue date.
        maturity_date: Note maturity date.
        currency: Settlement currency (e.g., "USD").
        issuer_wallet: Wallet of the note issuer (pays coupons and principal).
        holder_wallet: Wallet of the note holder (receives payments).
        cap_rate: Maximum return rate (e.g., 0.25 for 25% cap). None = uncapped.
        coupon_rate: Annual coupon rate (e.g., 0.02 for 2%). Default 0.0.
        coupon_frequency: Payments per year (0=none, 1, 2, 4, or 12). Default 0.
        coupon_schedule: Optional pre-defined schedule. If None, will be generated.

    Returns:
        Unit configured as a structured note with lifecycle support.
        The unit stores state including:
        - underlying, notional, strike_price
        - participation_rate, cap_rate, protection_level
        - issue_date, maturity_date, currency
        - issuer_wallet, holder_wallet
        - coupon_rate, coupon_frequency, coupon_schedule
        - paid_coupons: history of completed coupon payments
        - matured: whether final payoff has been settled
        - next_coupon_index: tracks next coupon payment

    Raises:
        ValueError: If validation fails for any parameter.

    Example:
        >>> note = create_structured_note(
        ...     symbol="SN_SPX_2025",
        ...     name="S&P 500 Principal Protected Note 2025",
        ...     underlying="SPX",
        ...     notional=100000.0,
        ...     strike_price=4500.0,
        ...     participation_rate=0.80,
        ...     protection_level=0.90,
        ...     issue_date=datetime(2024, 1, 15),
        ...     maturity_date=datetime(2025, 1, 15),
        ...     currency="USD",
        ...     issuer_wallet="bank",
        ...     holder_wallet="investor",
        ...     cap_rate=0.25,
        ... )
        >>> note.unit_type
        'STRUCTURED_NOTE'
    """
    # Ensure financial parameters are Decimal
    notional = Decimal(str(notional)) if not isinstance(notional, Decimal) else notional
    strike_price = Decimal(str(strike_price)) if not isinstance(strike_price, Decimal) else strike_price
    participation_rate = Decimal(str(participation_rate)) if not isinstance(participation_rate, Decimal) else participation_rate
    protection_level = Decimal(str(protection_level)) if not isinstance(protection_level, Decimal) else protection_level
    if cap_rate is not None:
        cap_rate = Decimal(str(cap_rate)) if not isinstance(cap_rate, Decimal) else cap_rate
    coupon_rate = Decimal(str(coupon_rate)) if not isinstance(coupon_rate, Decimal) else coupon_rate

    # Validation
    if notional <= Decimal("0"):
        raise ValueError(f"notional must be positive, got {notional}")
    if strike_price <= Decimal("0"):
        raise ValueError(f"strike_price must be positive, got {strike_price}")
    if participation_rate <= Decimal("0"):
        raise ValueError(
            f"participation_rate must be positive, got {participation_rate}"
        )
    if protection_level < Decimal("0") or protection_level > Decimal("1"):
        raise ValueError(
            f"protection_level must be between 0 and 1, got {protection_level}"
        )
    if cap_rate is not None and cap_rate <= Decimal("0"):
        raise ValueError(f"cap_rate must be positive if specified, got {cap_rate}")
    if coupon_rate < Decimal("0"):
        raise ValueError(f"coupon_rate cannot be negative, got {coupon_rate}")
    if coupon_frequency not in [0, 1, 2, 4, 12]:
        raise ValueError(
            f"coupon_frequency must be 0, 1, 2, 4, or 12, got {coupon_frequency}"
        )
    if not currency or not currency.strip():
        raise ValueError("currency cannot be empty")
    if not issuer_wallet or not issuer_wallet.strip():
        raise ValueError("issuer_wallet cannot be empty")
    if not holder_wallet or not holder_wallet.strip():
        raise ValueError("holder_wallet cannot be empty")
    if issuer_wallet == holder_wallet:
        raise ValueError("issuer_wallet and holder_wallet must be different")
    if maturity_date <= issue_date:
        raise ValueError("maturity_date must be after issue_date")

    # Generate coupon schedule if not provided
    if coupon_schedule is None:
        schedule = generate_structured_note_coupon_schedule(
            issue_date, maturity_date, coupon_rate, notional, coupon_frequency
        )
    else:
        schedule = coupon_schedule

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_STRUCTURED_NOTE,
        min_balance=Decimal("-1.0"),  # Allow short positions
        max_balance=Decimal("1000000.0"),
        decimal_places=0,  # Whole units
        transfer_rule=None,
        _frozen_state=_freeze_state({
            'underlying': underlying,
            'notional': notional,
            'strike_price': strike_price,
            'participation_rate': participation_rate,
            'cap_rate': cap_rate,
            'protection_level': protection_level,
            'issue_date': issue_date,
            'maturity_date': maturity_date,
            'currency': currency,
            'issuer_wallet': issuer_wallet,
            'holder_wallet': holder_wallet,
            'coupon_rate': coupon_rate,
            'coupon_frequency': coupon_frequency,
            'coupon_schedule': schedule,
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        })
    )


# ============================================================================
# PURE PAYOFF CALCULATIONS
# ============================================================================

def compute_performance(final_price: Decimal, strike_price: Decimal) -> Decimal:
    """
    Calculate the percentage performance of the underlying.

    Args:
        final_price: Final price of the underlying at maturity.
        strike_price: Reference/initial price for comparison.

    Returns:
        Performance as a decimal (e.g., 0.10 for +10%, -0.15 for -15%).

    Raises:
        ValueError: If strike_price is not positive.

    Example:
        >>> compute_performance(4950.0, 4500.0)
        0.1
        >>> compute_performance(4050.0, 4500.0)
        -0.1
        >>> compute_performance(4500.0, 4500.0)
        0.0
    """
    # Ensure parameters are Decimal
    final_price = Decimal(str(final_price)) if not isinstance(final_price, Decimal) else final_price
    strike_price = Decimal(str(strike_price)) if not isinstance(strike_price, Decimal) else strike_price

    if strike_price <= Decimal("0"):
        raise ValueError(f"strike_price must be positive, got {strike_price}")

    return (final_price - strike_price) / strike_price


def compute_payoff_rate(
    performance: Decimal,
    participation_rate: Decimal,
    cap_rate: Optional[Decimal],
    protection_level: Decimal,
) -> Decimal:
    """
    Calculate the return rate based on performance and note parameters.

    This implements the core structured note payoff logic:
    - On the upside: multiply performance by participation rate, cap if needed
    - On the downside: limit loss to (protection_level - 1)

    Args:
        performance: Underlying performance as decimal (e.g., 0.10 for +10%).
        participation_rate: Upside capture rate (e.g., 0.80 for 80%).
        cap_rate: Maximum return rate, or None if uncapped.
        protection_level: Principal protection as fraction (e.g., 0.90 for 90%).

    Returns:
        Return rate as decimal to be applied to notional.
        Final payout = notional * (1 + return_rate).

    Example:
        >>> # 20% up, 80% participation, 25% cap
        >>> compute_payoff_rate(0.20, 0.80, 0.25, 0.90)
        0.16
        >>> # 40% up hits cap
        >>> compute_payoff_rate(0.40, 0.80, 0.25, 0.90)
        0.25
        >>> # 15% down, 90% protection limits loss to -10%
        >>> compute_payoff_rate(-0.15, 0.80, 0.25, 0.90)
        -0.1
        >>> # 5% down, still within protection
        >>> compute_payoff_rate(-0.05, 0.80, 0.25, 0.90)
        -0.05
    """
    # Ensure parameters are Decimal
    performance = Decimal(str(performance)) if not isinstance(performance, Decimal) else performance
    participation_rate = Decimal(str(participation_rate)) if not isinstance(participation_rate, Decimal) else participation_rate
    if cap_rate is not None:
        cap_rate = Decimal(str(cap_rate)) if not isinstance(cap_rate, Decimal) else cap_rate
    protection_level = Decimal(str(protection_level)) if not isinstance(protection_level, Decimal) else protection_level

    if performance > Decimal("0"):
        # Upside: participate up to cap
        raw_return = participation_rate * performance
        if cap_rate is not None:
            return min(raw_return, cap_rate)
        return raw_return
    else:
        # Downside: protected to floor
        # protection_level of 0.90 means max loss is -10% (0.90 - 1.0)
        floor = protection_level - Decimal("1.0")
        return max(performance, floor)


# ============================================================================
# COUPON PAYMENT
# ============================================================================

def compute_coupon_payment(
    view: LedgerView,
    symbol: str,
    payment_date: datetime,
) -> PendingTransaction:
    """
    Process a scheduled coupon payment if due.

    Checks if the next scheduled coupon has reached its payment date.
    If so, generates payment moves from issuer to all note holders.

    Args:
        view: Read-only ledger access.
        symbol: Symbol of the structured note.
        payment_date: Current timestamp to check against scheduled date.

    Returns:
        PendingTransaction containing:
        - moves: Tuple of Move objects transferring currency from issuer to holders.
        - state_updates: Updates next_coupon_index and appends to paid_coupons.
        Returns empty PendingTransaction if no coupon is due or schedule exhausted.

    Example:
        >>> result = compute_coupon_payment(view, "SN_SPX_2025", datetime(2024, 7, 15))
        >>> len(result.moves)
        1
        >>> result.moves[0].source
        'bank'
    """
    state = view.get_unit_state(symbol)
    schedule = state.get('coupon_schedule', [])
    next_idx = int(state.get('next_coupon_index', 0))

    if next_idx >= len(schedule):
        return empty_pending_transaction(view)

    scheduled_date, coupon_amount = schedule[next_idx]
    # Ensure coupon_amount is Decimal (may be loaded as float from state)
    coupon_amount = Decimal(str(coupon_amount)) if not isinstance(coupon_amount, Decimal) else coupon_amount

    if payment_date < scheduled_date:
        return empty_pending_transaction(view)

    issuer = state['issuer_wallet']
    currency = state['currency']
    positions = view.get_positions(symbol)

    moves: List[Move] = []
    total_paid = Decimal("0.0")

    for wallet in sorted(positions.keys()):
        notes_held = positions[wallet]
        if notes_held > Decimal("0") and wallet != issuer:
            # Ensure notes_held is Decimal for arithmetic
            notes_held_decimal = Decimal(str(notes_held)) if not isinstance(notes_held, Decimal) else notes_held
            payout = notes_held_decimal * coupon_amount
            moves.append(Move(
                quantity=payout,
                unit_symbol=currency,
                source=issuer,
                dest=wallet,
                contract_id=f'sn_coupon_{symbol}_{next_idx}_{wallet}',
            ))
            total_paid += payout

    paid_coupons = list(state.get('paid_coupons', []))
    paid_coupons.append({
        'payment_number': next_idx,
        'payment_date': scheduled_date,
        'coupon_amount': coupon_amount,
        'total_paid': total_paid,
    })

    new_state = {
        **state,
        'next_coupon_index': next_idx + 1,
        'paid_coupons': paid_coupons,
    }
    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


# ============================================================================
# MATURITY PAYOFF
# ============================================================================

def compute_maturity_payoff(
    view: LedgerView,
    symbol: str,
    final_price: Decimal,
) -> PendingTransaction:
    """
    Calculate and pay the final payoff at maturity.

    Computes the structured note payoff based on underlying performance
    and pays all note holders their entitled amounts.

    Args:
        view: Read-only ledger access.
        symbol: Symbol of the structured note.
        final_price: Final price of the underlying at maturity.

    Returns:
        PendingTransaction containing:
        - moves: Payment moves from issuer to each holder.
        - state_updates: Marks note as matured with final settlement details.
        Returns empty PendingTransaction if already matured or maturity not reached.

    Raises:
        ValueError: If final_price is not positive.

    Example:
        >>> # Underlying up 10%, 80% participation = 8% return
        >>> result = compute_maturity_payoff(view, "SN_SPX_2025", 4950.0)
        >>> # notional=100000, return=8% => payout=108000
    """
    # Ensure final_price is Decimal
    final_price = Decimal(str(final_price)) if not isinstance(final_price, Decimal) else final_price

    if final_price <= Decimal("0"):
        raise ValueError(f"final_price must be positive, got {final_price}")

    state = view.get_unit_state(symbol)

    if state.get('matured', False):
        return empty_pending_transaction(view)

    maturity_date = state['maturity_date']
    if view.current_time < maturity_date:
        return empty_pending_transaction(view)

    # Extract parameters and ensure they are Decimal (may be loaded as float from state)
    notional = state['notional']
    notional = Decimal(str(notional)) if not isinstance(notional, Decimal) else notional

    strike_price = state['strike_price']
    strike_price = Decimal(str(strike_price)) if not isinstance(strike_price, Decimal) else strike_price

    participation_rate = state['participation_rate']
    participation_rate = Decimal(str(participation_rate)) if not isinstance(participation_rate, Decimal) else participation_rate

    cap_rate = state.get('cap_rate')
    if cap_rate is not None:
        cap_rate = Decimal(str(cap_rate)) if not isinstance(cap_rate, Decimal) else cap_rate

    protection_level = state['protection_level']
    protection_level = Decimal(str(protection_level)) if not isinstance(protection_level, Decimal) else protection_level

    issuer = state['issuer_wallet']
    currency = state['currency']

    # Calculate payoff
    performance = compute_performance(final_price, strike_price)
    return_rate = compute_payoff_rate(
        performance, participation_rate, cap_rate, protection_level
    )
    payout_per_note = notional * (Decimal("1") + return_rate)

    # Generate moves for all holders
    positions = view.get_positions(symbol)
    moves: List[Move] = []
    total_paid = Decimal("0.0")

    for wallet in sorted(positions.keys()):
        notes_held = positions[wallet]
        if notes_held > Decimal("0") and wallet != issuer:
            # Ensure notes_held is Decimal for arithmetic
            notes_held_decimal = Decimal(str(notes_held)) if not isinstance(notes_held, Decimal) else notes_held
            total_payout = notes_held_decimal * payout_per_note
            if abs(total_payout) > QUANTITY_EPSILON:
                moves.append(Move(
                    quantity=total_payout,
                    unit_symbol=currency,
                    source=issuer,
                    dest=wallet,
                    contract_id=f'sn_maturity_{symbol}_{wallet}',
                ))
                total_paid += total_payout

    new_state = {
        **state,
        'matured': True,
        'maturity_settlement': {
            'final_price': final_price,
            'performance': performance,
            'return_rate': return_rate,
            'payout_per_note': payout_per_note,
            'total_paid': total_paid,
        },
    }
    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


# ============================================================================
# TRANSACTION INTERFACE
# ============================================================================

def transact(
    view: LedgerView,
    symbol: str,
    seller: str,
    buyer: str,
    qty: Decimal,
    price: Decimal,
) -> PendingTransaction:
    """
    Execute a structured note trade (secondary market transfer).

    Structured notes trade like bonds in the secondary market. The buyer
    acquires the right to receive future coupons and the maturity payoff.

    Args:
        view: Read-only ledger access.
        symbol: Structured note symbol.
        seller: Wallet selling the structured note units.
        buyer: Wallet buying the structured note units.
        qty: Quantity to transfer (positive Decimal, whole units).
        price: Price per unit (mark-to-market value, Decimal).

    Returns:
        PendingTransaction containing:
        - Move transferring the structured note units from seller to buyer.
        - Move transferring cash from buyer to seller (if price > 0).

    Raises:
        ValueError: If qty <= 0, price < 0, seller == buyer, or invalid state.

    Example:
        # Alice sells her structured note to Bob
        result = transact(
            view, "SN_SPX_2025",
            seller_id="alice",
            buyer_id="bob",
            qty=1,
            price=102000.0  # Trading at premium due to favorable performance
        )
        ledger.execute(result)
    """
    # Ensure parameters are Decimal
    qty = Decimal(str(qty)) if not isinstance(qty, Decimal) else qty
    price = Decimal(str(price)) if not isinstance(price, Decimal) else price

    # Validate quantity
    if qty <= Decimal("0"):
        raise ValueError(f"qty must be positive, got {qty}")

    # Validate price
    if price < Decimal("0"):
        raise ValueError(f"price must be non-negative, got {price}")

    # Validate wallets
    if seller == buyer:
        raise ValueError("seller and buyer must be different")

    # Get unit state
    state = view.get_unit_state(symbol)

    # Check if already matured
    if state.get('matured', False):
        raise ValueError(f"Structured note {symbol} has already matured")

    # Check seller has sufficient balance
    seller_balance = view.get_balance(seller, symbol)
    if seller_balance < qty - QUANTITY_EPSILON:
        raise ValueError(
            f"Seller {seller} has insufficient balance: {seller_balance} < {qty}"
        )

    currency = state['currency']

    # Build moves
    moves = [
        # Transfer the structured note units
        Move(
            quantity=qty,
            unit_symbol=symbol,
            source=seller,
            dest=buyer,
            contract_id=f'sn_trade_{symbol}_unit',
        ),
    ]

    # Cash payment if price > 0
    total_payment = qty * price
    if total_payment > QUANTITY_EPSILON:
        moves.append(Move(
            quantity=total_payment,
            unit_symbol=currency,
            source=buyer,
            dest=seller,
            contract_id=f'sn_trade_{symbol}_cash',
        ))

    return build_transaction(view, moves)


def _process_lifecycle_event(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> PendingTransaction:
    """
    Generate moves and state updates for a structured note lifecycle event.

    This is the unified entry point for all structured note lifecycle events,
    routing to the appropriate handler based on event_type.

    Args:
        view: Read-only ledger access.
        symbol: Structured note symbol.
        event_type: Type of event (COUPON or MATURITY).
        event_date: When the event occurs.
        **kwargs: Event-specific parameters:
            - For MATURITY: final_price (Decimal, required)
            - For COUPON: None required

    Returns:
        PendingTransaction with moves and state_updates, or empty result
        if event_type is unknown or required parameters are missing.

    Example:
        >>> # Process a coupon payment
        >>> result = _process_lifecycle_event(view, "SN_SPX_2025", "COUPON", datetime(2024, 7, 15))

        >>> # Process maturity settlement
        >>> result = _process_lifecycle_event(view, "SN_SPX_2025", "MATURITY", datetime(2025, 1, 15),
        ...                   final_price=4950.0)
    """
    if event_type == 'COUPON':
        return compute_coupon_payment(view, symbol, event_date)

    elif event_type == 'MATURITY':
        final_price = kwargs.get('final_price')
        if final_price is None:
            return empty_pending_transaction(view)
        return compute_maturity_payoff(view, symbol, final_price)

    else:
        return empty_pending_transaction(view)


# ============================================================================
# SMART CONTRACT
# ============================================================================

def structured_note_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, Decimal]
) -> PendingTransaction:
    """
    SmartContract function for automatic structured note lifecycle processing.

    This function provides the SmartContract interface required by LifecycleEngine.
    It automatically processes coupon payments and maturity settlement when due.

    Args:
        view: Read-only ledger access.
        symbol: Structured note symbol to process.
        timestamp: Current time for date checking.
        prices: Price data dictionary (must contain underlying price for maturity).

    Returns:
        PendingTransaction with coupon payment or maturity moves if due,
        or empty result if no events are due.

    Example:
        >>> engine = LifecycleEngine(ledger)
        >>> engine.register("STRUCTURED_NOTE", structured_note_contract)
        >>> # Engine will automatically settle at maturity
    """
    state = view.get_unit_state(symbol)

    # Check for maturity first
    if not state.get('matured', False):
        maturity_date = state.get('maturity_date')
        if maturity_date and timestamp >= maturity_date:
            underlying = state.get('underlying')
            if not underlying:
                raise ValueError(f"Structured note {symbol} has no underlying defined")
            if underlying not in prices:
                raise ValueError(f"Missing price for structured note underlying '{underlying}' in {symbol}")
            final_price = prices[underlying]
            # Ensure final_price is Decimal (may come as float from prices dict)
            final_price = Decimal(str(final_price)) if not isinstance(final_price, Decimal) else final_price
            return compute_maturity_payoff(view, symbol, final_price)

    # Check for coupon payment
    schedule = state.get('coupon_schedule', [])
    next_idx = int(state.get('next_coupon_index', 0))

    if next_idx < len(schedule):
        scheduled_date, _ = schedule[next_idx]
        if timestamp >= scheduled_date:
            return compute_coupon_payment(view, symbol, timestamp)

    return empty_pending_transaction(view)
