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

from ..core import (
    LedgerView, Move, ContractResult, Unit,
    UNIT_TYPE_STRUCTURED_NOTE, QUANTITY_EPSILON,
)


# Type alias for coupon schedule
CouponSchedule = List[Tuple[datetime, float]]


# ============================================================================
# COUPON SCHEDULE GENERATION
# ============================================================================

def generate_structured_note_coupon_schedule(
    issue_date: datetime,
    maturity_date: datetime,
    coupon_rate: float,
    notional: float,
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

    schedule: CouponSchedule = []
    months_between = 12 // frequency
    coupon_amount = (notional * coupon_rate) / frequency

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
    notional: float,
    strike_price: float,
    participation_rate: float,
    protection_level: float,
    issue_date: datetime,
    maturity_date: datetime,
    currency: str,
    issuer_wallet: str,
    holder_wallet: str,
    cap_rate: Optional[float] = None,
    coupon_rate: float = 0.0,
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
    # Validation
    if notional <= 0:
        raise ValueError(f"notional must be positive, got {notional}")
    if strike_price <= 0:
        raise ValueError(f"strike_price must be positive, got {strike_price}")
    if participation_rate <= 0:
        raise ValueError(
            f"participation_rate must be positive, got {participation_rate}"
        )
    if protection_level < 0 or protection_level > 1:
        raise ValueError(
            f"protection_level must be between 0 and 1, got {protection_level}"
        )
    if cap_rate is not None and cap_rate <= 0:
        raise ValueError(f"cap_rate must be positive if specified, got {cap_rate}")
    if coupon_rate < 0:
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
        min_balance=-1.0,  # Allow short positions
        max_balance=1000000.0,
        decimal_places=0,  # Whole units
        transfer_rule=None,
        _state={
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
        }
    )


# ============================================================================
# PURE PAYOFF CALCULATIONS
# ============================================================================

def compute_performance(final_price: float, strike_price: float) -> float:
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
    if strike_price <= 0:
        raise ValueError(f"strike_price must be positive, got {strike_price}")

    return (final_price - strike_price) / strike_price


def compute_payoff_rate(
    performance: float,
    participation_rate: float,
    cap_rate: Optional[float],
    protection_level: float,
) -> float:
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
    if performance > 0:
        # Upside: participate up to cap
        raw_return = participation_rate * performance
        if cap_rate is not None:
            return min(raw_return, cap_rate)
        return raw_return
    else:
        # Downside: protected to floor
        # protection_level of 0.90 means max loss is -10% (0.90 - 1.0)
        floor = protection_level - 1.0
        return max(performance, floor)


# ============================================================================
# COUPON PAYMENT
# ============================================================================

def compute_coupon_payment(
    view: LedgerView,
    symbol: str,
    payment_date: datetime,
) -> ContractResult:
    """
    Process a scheduled coupon payment if due.

    Checks if the next scheduled coupon has reached its payment date.
    If so, generates payment moves from issuer to all note holders.

    Args:
        view: Read-only ledger access.
        symbol: Symbol of the structured note.
        payment_date: Current timestamp to check against scheduled date.

    Returns:
        ContractResult containing:
        - moves: Tuple of Move objects transferring currency from issuer to holders.
        - state_updates: Updates next_coupon_index and appends to paid_coupons.
        Returns empty ContractResult if no coupon is due or schedule exhausted.

    Example:
        >>> result = compute_coupon_payment(view, "SN_SPX_2025", datetime(2024, 7, 15))
        >>> len(result.moves)
        1
        >>> result.moves[0].source
        'bank'
    """
    state = view.get_unit_state(symbol)
    schedule = state.get('coupon_schedule', [])
    next_idx = state.get('next_coupon_index', 0)

    if next_idx >= len(schedule):
        return ContractResult()

    scheduled_date, coupon_amount = schedule[next_idx]

    if payment_date < scheduled_date:
        return ContractResult()

    issuer = state['issuer_wallet']
    currency = state['currency']
    positions = view.get_positions(symbol)

    moves: List[Move] = []
    total_paid = 0.0

    for wallet in sorted(positions.keys()):
        notes_held = positions[wallet]
        if notes_held > 0 and wallet != issuer:
            payout = notes_held * coupon_amount
            moves.append(Move(
                source=issuer,
                dest=wallet,
                unit=currency,
                quantity=payout,
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

    state_updates = {
        symbol: {
            **state,
            'next_coupon_index': next_idx + 1,
            'paid_coupons': paid_coupons,
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


# ============================================================================
# MATURITY PAYOFF
# ============================================================================

def compute_maturity_payoff(
    view: LedgerView,
    symbol: str,
    final_price: float,
) -> ContractResult:
    """
    Calculate and pay the final payoff at maturity.

    Computes the structured note payoff based on underlying performance
    and pays all note holders their entitled amounts.

    Args:
        view: Read-only ledger access.
        symbol: Symbol of the structured note.
        final_price: Final price of the underlying at maturity.

    Returns:
        ContractResult containing:
        - moves: Payment moves from issuer to each holder.
        - state_updates: Marks note as matured with final settlement details.
        Returns empty ContractResult if already matured or maturity not reached.

    Raises:
        ValueError: If final_price is not positive.

    Example:
        >>> # Underlying up 10%, 80% participation = 8% return
        >>> result = compute_maturity_payoff(view, "SN_SPX_2025", 4950.0)
        >>> # notional=100000, return=8% => payout=108000
    """
    if final_price <= 0:
        raise ValueError(f"final_price must be positive, got {final_price}")

    state = view.get_unit_state(symbol)

    if state.get('matured', False):
        return ContractResult()

    maturity_date = state['maturity_date']
    if view.current_time < maturity_date:
        return ContractResult()

    # Extract parameters
    notional = state['notional']
    strike_price = state['strike_price']
    participation_rate = state['participation_rate']
    cap_rate = state.get('cap_rate')
    protection_level = state['protection_level']
    issuer = state['issuer_wallet']
    currency = state['currency']

    # Calculate payoff
    performance = compute_performance(final_price, strike_price)
    return_rate = compute_payoff_rate(
        performance, participation_rate, cap_rate, protection_level
    )
    payout_per_note = notional * (1 + return_rate)

    # Generate moves for all holders
    positions = view.get_positions(symbol)
    moves: List[Move] = []
    total_paid = 0.0

    for wallet in sorted(positions.keys()):
        notes_held = positions[wallet]
        if notes_held > 0 and wallet != issuer:
            total_payout = notes_held * payout_per_note
            if abs(total_payout) > QUANTITY_EPSILON:
                moves.append(Move(
                    source=issuer,
                    dest=wallet,
                    unit=currency,
                    quantity=total_payout,
                    contract_id=f'sn_maturity_{symbol}_{wallet}',
                ))
                total_paid += total_payout

    state_updates = {
        symbol: {
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
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


# ============================================================================
# TRANSACTION INTERFACE
# ============================================================================

def transact(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> ContractResult:
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
            - For MATURITY: final_price (float, required)
            - For COUPON: None required

    Returns:
        ContractResult with moves and state_updates, or empty result
        if event_type is unknown or required parameters are missing.

    Example:
        >>> # Process a coupon payment
        >>> result = transact(view, "SN_SPX_2025", "COUPON", datetime(2024, 7, 15))

        >>> # Process maturity settlement
        >>> result = transact(view, "SN_SPX_2025", "MATURITY", datetime(2025, 1, 15),
        ...                   final_price=4950.0)
    """
    if event_type == 'COUPON':
        return compute_coupon_payment(view, symbol, event_date)

    elif event_type == 'MATURITY':
        final_price = kwargs.get('final_price')
        if final_price is None:
            return ContractResult()
        return compute_maturity_payoff(view, symbol, final_price)

    else:
        return ContractResult()


# ============================================================================
# SMART CONTRACT
# ============================================================================

def structured_note_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> ContractResult:
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
        ContractResult with coupon payment or maturity moves if due,
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
            final_price = prices.get(underlying)
            if final_price is not None:
                return compute_maturity_payoff(view, symbol, final_price)

    # Check for coupon payment
    schedule = state.get('coupon_schedule', [])
    next_idx = state.get('next_coupon_index', 0)

    if next_idx < len(schedule):
        scheduled_date, _ = schedule[next_idx]
        if timestamp >= scheduled_date:
            return compute_coupon_payment(view, symbol, timestamp)

    return ContractResult()
