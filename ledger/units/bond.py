"""
bond.py - Bond Units for Fixed Income Instruments

This module provides bond unit creation and lifecycle processing:
1. create_bond_unit() - Factory for bond units with coupon schedules
2. compute_accrued_interest() - Calculate accrued interest as of a date
3. compute_coupon_payment() - Process scheduled coupon payments
4. compute_redemption() - Final principal repayment at maturity
5. transact() - Event-driven interface for COUPON, REDEMPTION, CALL, PUT events
6. bond_contract() - SmartContract for LifecycleEngine integration

Bonds represent debt instruments with:
- Fixed or floating coupon payments
- Accrued interest calculation using day count conventions
- Redemption at maturity (or early call/put)

All functions take LedgerView (read-only) and return immutable results.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional

from ..core import (
    LedgerView, Move, ContractResult, Unit,
    SYSTEM_WALLET,
)


# Type alias for coupon schedule
CouponSchedule = List[Tuple[datetime, float]]


# ============================================================================
# DAY COUNT CONVENTIONS
# ============================================================================

def days_30_360(start_date: datetime, end_date: datetime) -> float:
    """
    Calculate days between two dates using 30/360 convention.

    This convention assumes 30 days per month and 360 days per year.
    Commonly used for corporate bonds.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        Number of days using 30/360 convention
    """
    d1 = start_date.day
    d2 = end_date.day
    m1 = start_date.month
    m2 = end_date.month
    y1 = start_date.year
    y2 = end_date.year

    # Adjust day counts per 30/360 rules
    if d1 == 31:
        d1 = 30
    if d2 == 31 and d1 >= 30:
        d2 = 30

    return 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)


def days_act_360(start_date: datetime, end_date: datetime) -> float:
    """
    Calculate actual days between two dates.

    Used with ACT/360 convention (actual days / 360).
    Commonly used for money market instruments.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        Actual number of days
    """
    delta = end_date - start_date
    return float(delta.days)


def days_act_act(start_date: datetime, end_date: datetime) -> float:
    """
    Calculate actual days between two dates.

    Used with ACT/ACT convention (actual days / actual days in year).
    Commonly used for government bonds.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        Actual number of days
    """
    delta = end_date - start_date
    return float(delta.days)


def year_fraction(start_date: datetime, end_date: datetime, convention: str) -> float:
    """
    Calculate the year fraction between two dates using a day count convention.

    Args:
        start_date: Start date
        end_date: End date
        convention: Day count convention ("30/360", "ACT/360", "ACT/ACT")

    Returns:
        Year fraction as a float

    Raises:
        ValueError: If convention is not supported
    """
    if convention == "30/360":
        days = days_30_360(start_date, end_date)
        return days / 360.0
    elif convention == "ACT/360":
        days = days_act_360(start_date, end_date)
        return days / 360.0
    elif convention == "ACT/ACT":
        days = days_act_act(start_date, end_date)
        # For ACT/ACT, we need to determine the actual days in the year
        # Simple implementation: use 365.25 as average
        # More sophisticated implementations would handle leap years properly
        return days / 365.25
    else:
        raise ValueError(f"Unsupported day count convention: {convention}")


# ============================================================================
# COUPON SCHEDULE GENERATION
# ============================================================================

def generate_coupon_schedule(
    issue_date: datetime,
    maturity_date: datetime,
    coupon_rate: float,
    face_value: float,
    frequency: int,
) -> CouponSchedule:
    """
    Generate a coupon payment schedule.

    Args:
        issue_date: Bond issue date
        maturity_date: Bond maturity date
        coupon_rate: Annual coupon rate (e.g., 0.05 for 5%)
        face_value: Par/notional amount
        frequency: Payments per year (1=annual, 2=semi-annual, 4=quarterly)

    Returns:
        List of (payment_date, coupon_amount) tuples
    """
    if frequency not in [1, 2, 4, 12]:
        raise ValueError(f"Frequency must be 1, 2, 4, or 12, got {frequency}")

    schedule: CouponSchedule = []
    months_between = 12 // frequency
    coupon_amount = (face_value * coupon_rate) / frequency

    # Start from the first coupon date
    current_date = issue_date

    # Calculate payment dates by adding months
    while True:
        # Move to next payment date
        month = current_date.month + months_between
        year = current_date.year

        while month > 12:
            month -= 12
            year += 1

        try:
            next_date = current_date.replace(year=year, month=month)
        except ValueError:
            # Handle day overflow (e.g., Jan 31 -> Feb 31 doesn't exist)
            # Move to last day of the month
            if month == 12:
                next_month = 1
                next_year = year + 1
            else:
                next_month = month + 1
                next_year = year
            next_date = datetime(next_year, next_month, 1) - timedelta(days=1)
            next_date = next_date.replace(hour=current_date.hour, minute=current_date.minute)

        current_date = next_date

        if current_date > maturity_date:
            break

        schedule.append((current_date, coupon_amount))

    return schedule


# ============================================================================
# BOND UNIT CREATION
# ============================================================================

def create_bond_unit(
    symbol: str,
    name: str,
    face_value: float,
    coupon_rate: float,
    coupon_frequency: int,
    maturity_date: datetime,
    currency: str,
    issuer_wallet: str,
    holder_wallet: str,
    issue_date: datetime = None,
    day_count_convention: str = "30/360",
    coupon_schedule: Optional[CouponSchedule] = None,
) -> Unit:
    """
    Create a bond unit representing a debt instrument.

    Args:
        symbol: Unique bond identifier (e.g., "US10Y", "CORP_5Y_2029")
        name: Human-readable bond name (e.g., "US Treasury 10-Year")
        face_value: Par/notional amount (principal)
        coupon_rate: Annual coupon rate (e.g., 0.05 for 5%)
        coupon_frequency: Payments per year (1=annual, 2=semi-annual, 4=quarterly, 12=monthly)
        maturity_date: Bond maturity date
        currency: Settlement currency
        issuer_wallet: Who pays coupons and redemption
        holder_wallet: Who receives payments
        issue_date: Bond issue date (defaults to current time if None)
        day_count_convention: "30/360", "ACT/360", or "ACT/ACT" (default: "30/360")
        coupon_schedule: Optional pre-defined schedule. If None, will be generated.

    Returns:
        Unit configured for bond with coupon lifecycle support.
        The unit stores bond state including:
        - face_value: par amount
        - coupon_rate: annual rate
        - coupon_frequency: payments per year
        - coupon_schedule: payment schedule
        - maturity_date: redemption date
        - currency: payment currency
        - issuer_wallet: payer
        - holder_wallet: payee
        - day_count_convention: accrual calculation method
        - next_coupon_index: tracks next payment
        - accrued_interest: current accrued amount
        - redeemed: whether principal has been repaid
        - paid_coupons: history of completed payments

    Example:
        bond = create_bond_unit(
            symbol="CORP_5Y_2029",
            name="Corporate Bond 5% 2029",
            face_value=1000.0,
            coupon_rate=0.05,
            coupon_frequency=2,  # Semi-annual
            maturity_date=datetime(2029, 12, 15),
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
        )
        ledger.register_unit(bond)
    """
    if face_value <= 0:
        raise ValueError(f"face_value must be positive, got {face_value}")
    if coupon_rate < 0:
        raise ValueError(f"coupon_rate cannot be negative, got {coupon_rate}")
    if coupon_frequency not in [1, 2, 4, 12]:
        raise ValueError(f"coupon_frequency must be 1, 2, 4, or 12, got {coupon_frequency}")
    if day_count_convention not in ["30/360", "ACT/360", "ACT/ACT"]:
        raise ValueError(f"day_count_convention must be '30/360', 'ACT/360', or 'ACT/ACT', got {day_count_convention}")

    # Generate coupon schedule if not provided
    if coupon_schedule is None:
        if issue_date is None:
            raise ValueError("issue_date is required when coupon_schedule is not provided")
        schedule = generate_coupon_schedule(
            issue_date, maturity_date, coupon_rate, face_value, coupon_frequency
        )
    else:
        schedule = coupon_schedule

    return Unit(
        symbol=symbol,
        name=name,
        unit_type="BOND",
        min_balance=-10_000.0,
        max_balance=10_000.0,
        decimal_places=0,  # Bonds are whole units
        transfer_rule=None,
        _state={
            'face_value': face_value,
            'coupon_rate': coupon_rate,
            'coupon_frequency': coupon_frequency,
            'coupon_schedule': schedule,
            'maturity_date': maturity_date,
            'currency': currency,
            'issuer_wallet': issuer_wallet,
            'holder_wallet': holder_wallet,
            'day_count_convention': day_count_convention,
            'issue_date': issue_date,
            'next_coupon_index': 0,
            'accrued_interest': 0.0,
            'redeemed': False,
            'paid_coupons': [],
        }
    )


# ============================================================================
# ACCRUED INTEREST
# ============================================================================

def compute_accrued_interest(
    view: LedgerView,
    bond_symbol: str,
    as_of_date: datetime,
) -> float:
    """
    Calculate accrued interest on a bond as of a specific date.

    Accrued interest = (days since last coupon / days in period) × coupon_amount

    Args:
        view: Read-only ledger access
        bond_symbol: Symbol of the bond unit
        as_of_date: Date to calculate accrued interest

    Returns:
        Accrued interest amount in the bond's currency
    """
    state = view.get_unit_state(bond_symbol)

    schedule = state.get('coupon_schedule', [])
    next_idx = state.get('next_coupon_index', 0)
    convention = state.get('day_count_convention', '30/360')

    if next_idx >= len(schedule):
        # No more coupons - no accrual
        return 0.0

    # Find the last coupon date
    if next_idx == 0:
        # No coupons paid yet - accrue from issue date
        last_coupon_date = state.get('issue_date')
        if last_coupon_date is None:
            # Fallback: calculate the theoretical previous coupon date
            # by subtracting one coupon period from the first scheduled coupon
            next_coupon_date, _ = schedule[0]
            frequency = state.get('coupon_frequency', 2)
            months_between = 12 // frequency

            # Calculate target month and year with proper underflow handling
            target_month = next_coupon_date.month - months_between
            target_year = next_coupon_date.year

            # Handle month underflow (e.g., January - 6 = July previous year)
            while target_month <= 0:
                target_month += 12
                target_year -= 1

            # Handle day overflow (e.g., March 31 - 1 month != February 31)
            target_day = next_coupon_date.day
            while target_day > 0:
                try:
                    last_coupon_date = datetime(
                        target_year,
                        target_month,
                        target_day,
                        next_coupon_date.hour,
                        next_coupon_date.minute,
                        next_coupon_date.second,
                    )
                    break
                except ValueError:
                    # Day doesn't exist in this month, try previous day
                    target_day -= 1
            else:
                # Should never happen, but fail safely
                raise ValueError(
                    f"Cannot compute fallback coupon date from {next_coupon_date}"
                )
    else:
        last_coupon_date, _ = schedule[next_idx - 1]

    next_coupon_date, coupon_amount = schedule[next_idx]

    # Calculate accrued interest
    if as_of_date <= last_coupon_date:
        return 0.0

    if as_of_date >= next_coupon_date:
        # Full coupon has accrued
        return coupon_amount

    # Partial accrual
    days_accrued = year_fraction(last_coupon_date, as_of_date, convention)
    days_in_period = year_fraction(last_coupon_date, next_coupon_date, convention)

    if days_in_period <= 0:
        return 0.0

    accrued = (days_accrued / days_in_period) * coupon_amount
    return accrued


# ============================================================================
# COUPON PAYMENT
# ============================================================================

def compute_coupon_payment(
    view: LedgerView,
    bond_symbol: str,
    payment_date: datetime,
) -> ContractResult:
    """
    Process a scheduled coupon payment if due.

    This function checks if the next scheduled coupon payment has reached its
    payment date. If so, it generates payment moves for all bondholders and
    updates the unit state to track the payment.

    Payment logic:
    - Only wallets with positive bond balances receive coupons
    - The issuer wallet does not pay itself coupons
    - Payment amount = bonds_held × coupon_amount
    - Payments are sorted by wallet name for deterministic ordering

    Args:
        view: Read-only ledger access
        bond_symbol: Symbol of the bond unit
        payment_date: Current timestamp to check against scheduled payment_date

    Returns:
        ContractResult containing:
        - moves: Tuple of Move objects transferring currency from issuer to bondholders
        - state_updates: Updates next_coupon_index and appends to paid_coupons history
        Returns empty ContractResult if no coupon is due or schedule is exhausted.
    """
    state = view.get_unit_state(bond_symbol)
    schedule = state.get('coupon_schedule', [])
    next_idx = state.get('next_coupon_index', 0)

    if next_idx >= len(schedule):
        return ContractResult()

    scheduled_date, coupon_amount = schedule[next_idx]

    if payment_date < scheduled_date:
        return ContractResult()

    issuer = state['issuer_wallet']
    currency = state['currency']
    positions = view.get_positions(bond_symbol)

    moves: List[Move] = []
    total_paid = 0.0

    for wallet in sorted(positions.keys()):
        bonds_held = positions[wallet]
        if bonds_held > 0 and wallet != issuer:
            payout = bonds_held * coupon_amount
            moves.append(Move(
                source=issuer,
                dest=wallet,
                unit=currency,
                quantity=payout,
                contract_id=f'coupon_{bond_symbol}_{next_idx}_{wallet}',
            ))
            total_paid += payout

    paid_coupons = list(state.get('paid_coupons', []))
    paid_coupons.append({
        'payment_number': next_idx,
        'payment_date': scheduled_date,
        'coupon_amount': coupon_amount,
        'total_paid': total_paid,
    })

    # Update accrued interest to 0 after payment
    state_updates = {
        bond_symbol: {
            **state,
            'next_coupon_index': next_idx + 1,
            'accrued_interest': 0.0,
            'paid_coupons': paid_coupons,
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


# ============================================================================
# REDEMPTION
# ============================================================================

def compute_redemption(
    view: LedgerView,
    bond_symbol: str,
    redemption_date: datetime,
    redemption_price: Optional[float] = None,
    allow_early: bool = False,
) -> ContractResult:
    """
    Process bond redemption (principal repayment) at maturity or early call/put.

    Redemption pays back the face value (or redemption_price if specified) to
    bondholders and marks the bond as redeemed.

    Args:
        view: Read-only ledger access
        bond_symbol: Symbol of the bond unit
        redemption_date: Date of redemption
        redemption_price: Optional redemption amount per bond (defaults to face_value)
        allow_early: If True, allows redemption before maturity (for CALL/PUT events)

    Returns:
        ContractResult containing:
        - moves: Principal payments from issuer to bondholders
        - state_updates: Marks bond as redeemed
        Returns empty ContractResult if already redeemed or maturity not reached
        (unless allow_early is True).
    """
    state = view.get_unit_state(bond_symbol)

    if state.get('redeemed'):
        return ContractResult()

    # Check maturity date unless early redemption is explicitly allowed
    maturity_date = state['maturity_date']
    if not allow_early and redemption_date < maturity_date:
        return ContractResult()  # Not yet matured

    issuer = state['issuer_wallet']
    currency = state['currency']
    face_value = state['face_value']
    redemption_amount = redemption_price if redemption_price is not None else face_value

    positions = view.get_positions(bond_symbol)

    moves: List[Move] = []
    total_redeemed = 0.0

    for wallet in sorted(positions.keys()):
        bonds_held = positions[wallet]
        if bonds_held > 0 and wallet != issuer:
            payment = bonds_held * redemption_amount
            moves.append(Move(
                source=issuer,
                dest=wallet,
                unit=currency,
                quantity=payment,
                contract_id=f'redemption_{bond_symbol}_{wallet}',
            ))
            total_redeemed += payment

    state_updates = {
        bond_symbol: {
            **state,
            'redeemed': True,
            'redemption_date': redemption_date,
            'redemption_amount': redemption_amount,
            'total_redeemed': total_redeemed,
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
    Generate moves and state updates for a bond lifecycle event.

    This is the unified entry point for all bond lifecycle events, routing
    to the appropriate handler based on event_type.

    Args:
        view: Read-only ledger access
        symbol: Bond symbol
        event_type: Type of event (COUPON, REDEMPTION, CALL, PUT)
        event_date: When the event occurs
        **kwargs: Event-specific parameters:
            - For COUPON: None (uses scheduled coupon)
            - For REDEMPTION: redemption_price (optional, defaults to face_value)
            - For CALL: redemption_price (optional)
            - For PUT: redemption_price (optional)

    Returns:
        ContractResult with moves and state_updates, or empty result
        if event_type is unknown.

    Example:
        # Process a scheduled coupon
        result = transact(ledger, "CORP_5Y_2029", "COUPON", datetime(2024, 6, 15))

        # Process redemption at maturity
        result = transact(ledger, "CORP_5Y_2029", "REDEMPTION", datetime(2029, 12, 15))

        # Process early call
        result = transact(ledger, "CORP_5Y_2029", "CALL", datetime(2027, 6, 15),
                         redemption_price=1050.0)
    """
    handlers = {
        'COUPON': lambda: compute_coupon_payment(view, symbol, event_date),
        'REDEMPTION': lambda: compute_redemption(view, symbol, event_date,
                                                 kwargs.get('redemption_price'),
                                                 allow_early=False),
        'CALL': lambda: compute_redemption(view, symbol, event_date,
                                           kwargs.get('redemption_price'),
                                           allow_early=True),  # CALL allows early redemption
        'PUT': lambda: compute_redemption(view, symbol, event_date,
                                          kwargs.get('redemption_price'),
                                          allow_early=True),   # PUT allows early redemption
    }

    handler = handlers.get(event_type)
    if handler is None:
        return ContractResult()  # Unknown event type - no action

    return handler()


# ============================================================================
# SMART CONTRACT
# ============================================================================

def bond_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> ContractResult:
    """
    SmartContract function for automatic bond lifecycle processing.

    This function provides the SmartContract interface required by LifecycleEngine.
    It automatically processes coupon payments and redemption when due.

    Args:
        view: Read-only ledger access
        symbol: Bond symbol to process
        timestamp: Current time for date checking
        prices: Price data (unused for bond processing)

    Returns:
        ContractResult with coupon payment or redemption moves if due,
        or empty result if no events are due.
    """
    state = view.get_unit_state(symbol)

    # Check for redemption first
    if not state.get('redeemed'):
        maturity_date = state.get('maturity_date')
        if maturity_date and timestamp >= maturity_date:
            # Process redemption at maturity
            return compute_redemption(view, symbol, timestamp)

    # Check for coupon payment
    schedule = state.get('coupon_schedule', [])
    next_idx = state.get('next_coupon_index', 0)

    if next_idx < len(schedule):
        scheduled_date, _ = schedule[next_idx]
        if timestamp >= scheduled_date:
            return compute_coupon_payment(view, symbol, timestamp)

    return ContractResult()
