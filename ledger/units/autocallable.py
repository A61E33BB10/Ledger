"""
autocallable.py - Autocallable Structured Products

This module provides autocallable structured product creation and lifecycle processing:
1. create_autocallable() - Factory for autocallable units with observation schedules
2. compute_observation() - Process observation dates (autocall, coupon, knock-in)
3. compute_maturity_payoff() - Final settlement if not autocalled
4. transact() - Event-driven interface for OBSERVATION, MATURITY events
5. autocallable_contract() - SmartContract for LifecycleEngine integration

Autocallables are structured products that:
- Auto-redeem if underlying reaches autocall barrier on observation dates
- Pay conditional coupons if underlying >= coupon barrier
- Have optional "memory" feature where missed coupons accumulate
- Have put barrier for downside risk (knock-in put)

All functions take LedgerView (read-only) and return immutable results.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..core import (
    LedgerView, Move, ContractResult, Unit,
    QUANTITY_EPSILON, UNIT_TYPE_AUTOCALLABLE,
)


def create_autocallable(
    symbol: str,
    name: str,
    underlying: str,
    notional: float,
    initial_spot: float,
    autocall_barrier: float,
    coupon_barrier: float,
    coupon_rate: float,
    put_barrier: float,
    issue_date: datetime,
    maturity_date: datetime,
    observation_schedule: List[datetime],
    currency: str,
    issuer_wallet: str,
    holder_wallet: str,
    memory_feature: bool = True,
) -> Unit:
    """
    Create an autocallable structured product unit.

    An autocallable is a structured product that may auto-redeem early if the
    underlying reaches certain levels on observation dates. It pays conditional
    coupons and has downside protection through a put barrier.

    Args:
        symbol: Unique identifier for the autocallable (e.g., "AUTO_SPX_2025")
        name: Human-readable name (e.g., "SPX Autocallable 8% 2025")
        underlying: Symbol of the underlying asset (e.g., "SPX")
        notional: Principal amount invested
        initial_spot: Reference spot price at issue date
        autocall_barrier: Barrier for early redemption as fraction of initial
                          (e.g., 1.0 = 100% of initial spot)
        coupon_barrier: Barrier for coupon payment as fraction of initial
                        (e.g., 0.7 = 70% of initial spot)
        coupon_rate: Coupon rate per observation period (e.g., 0.08 = 8%)
        put_barrier: Barrier for knock-in put as fraction of initial
                     (e.g., 0.6 = 60% of initial spot)
        issue_date: Date when autocallable was issued
        maturity_date: Final maturity date
        observation_schedule: List of observation dates for autocall/coupon checks
        currency: Settlement currency (e.g., "USD")
        issuer_wallet: Wallet of the product issuer (pays coupons/redemption)
        holder_wallet: Wallet of the product holder (receives payments)
        memory_feature: If True, missed coupons accumulate and are paid on
                        subsequent coupon dates or autocall

    Returns:
        Unit: An autocallable unit with type UNIT_TYPE_AUTOCALLABLE.
        The unit's _state contains all term sheet data plus:
        - observation_history: List of processed observations
        - coupon_memory: Accumulated unpaid coupons
        - put_knocked_in: Whether put barrier was breached
        - autocalled: Whether product has auto-redeemed
        - autocall_date: Date of autocall (if any)
        - settled: Whether final settlement has occurred

    Raises:
        ValueError: If parameters are invalid (non-positive notional,
                    invalid barriers, empty wallets, etc.)

    Example:
        autocallable = create_autocallable(
            symbol="AUTO_SPX_2025",
            name="SPX Autocallable 8% 2025",
            underlying="SPX",
            notional=100000.0,
            initial_spot=4500.0,
            autocall_barrier=1.0,    # 100% of initial
            coupon_barrier=0.7,       # 70% of initial
            coupon_rate=0.08,         # 8% per period
            put_barrier=0.6,          # 60% of initial
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            observation_schedule=[
                datetime(2024, 4, 15),
                datetime(2024, 7, 15),
                datetime(2024, 10, 15),
                datetime(2025, 1, 15),
            ],
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            memory_feature=True,
        )
        ledger.register_unit(autocallable)
    """
    # Validate notional
    if notional <= 0:
        raise ValueError(f"notional must be positive, got {notional}")

    # Validate initial_spot
    if initial_spot <= 0:
        raise ValueError(f"initial_spot must be positive, got {initial_spot}")

    # Validate barriers
    if autocall_barrier <= 0:
        raise ValueError(f"autocall_barrier must be positive, got {autocall_barrier}")
    if coupon_barrier <= 0:
        raise ValueError(f"coupon_barrier must be positive, got {coupon_barrier}")
    if put_barrier <= 0:
        raise ValueError(f"put_barrier must be positive, got {put_barrier}")

    # Validate coupon_rate
    if coupon_rate < 0:
        raise ValueError(f"coupon_rate cannot be negative, got {coupon_rate}")

    # Validate wallets
    if not issuer_wallet or not issuer_wallet.strip():
        raise ValueError("issuer_wallet cannot be empty")
    if not holder_wallet or not holder_wallet.strip():
        raise ValueError("holder_wallet cannot be empty")
    if issuer_wallet == holder_wallet:
        raise ValueError("issuer_wallet and holder_wallet must be different")

    # Validate currency
    if not currency or not currency.strip():
        raise ValueError("currency cannot be empty")

    # Validate dates
    if maturity_date <= issue_date:
        raise ValueError("maturity_date must be after issue_date")

    # Validate observation schedule
    if not observation_schedule:
        raise ValueError("observation_schedule cannot be empty")

    # Sort observation schedule
    sorted_schedule = sorted(observation_schedule)

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_AUTOCALLABLE,
        min_balance=-10.0,
        max_balance=10.0,
        decimal_places=0,
        transfer_rule=None,
        _state={
            'underlying': underlying,
            'notional': notional,
            'initial_spot': initial_spot,
            'autocall_barrier': autocall_barrier,
            'coupon_barrier': coupon_barrier,
            'coupon_rate': coupon_rate,
            'put_barrier': put_barrier,
            'issue_date': issue_date,
            'maturity_date': maturity_date,
            'observation_schedule': sorted_schedule,
            'currency': currency,
            'issuer_wallet': issuer_wallet,
            'holder_wallet': holder_wallet,
            'memory_feature': memory_feature,
            # State tracking
            'observation_history': [],
            'coupon_memory': 0.0,
            'put_knocked_in': False,
            'autocalled': False,
            'autocall_date': None,
            'settled': False,
        }
    )


def compute_observation(
    view: LedgerView,
    symbol: str,
    observation_date: datetime,
    spot: float,
) -> ContractResult:
    """
    Process an observation date for an autocallable.

    This function checks the underlying spot price against the various barriers
    and generates appropriate payments and state updates.

    Observation logic (in order):
    1. Check autocall: If performance >= autocall_barrier, product auto-redeems
       with principal + current coupon + accumulated memory coupons
    2. Check coupon: If performance >= coupon_barrier, pay coupon (+ memory if applicable)
    3. Check put knock-in: If performance <= put_barrier, put is knocked in

    Args:
        view: Read-only ledger access
        symbol: Autocallable symbol
        observation_date: Date of observation
        spot: Current spot price of underlying

    Returns:
        ContractResult with:
        - moves: Payment moves (coupon and/or redemption)
        - state_updates: Updated observation history, coupon memory, barriers

    Raises:
        ValueError: If spot price is not positive

    Example:
        # Observation where underlying is at 110% of initial (autocall triggered)
        result = compute_observation(
            view, "AUTO_SPX_2025",
            datetime(2024, 4, 15),
            spot=4950.0  # 110% of 4500
        )
        # Product autocalls, holder receives notional + coupon
    """
    if spot <= 0:
        raise ValueError(f"spot must be positive, got {spot}")

    state = view.get_unit_state(symbol)

    # Check if already autocalled or settled
    if state.get('autocalled', False) or state.get('settled', False):
        return ContractResult()

    # Check if this observation date is in the schedule
    schedule = state.get('observation_schedule', [])
    if observation_date not in schedule:
        return ContractResult()

    # Check if already processed
    history = state.get('observation_history', [])
    processed_dates = [obs['date'] for obs in history]
    if observation_date in processed_dates:
        return ContractResult()

    # Get state values
    initial_spot = state['initial_spot']
    notional = state['notional']
    autocall_barrier = state['autocall_barrier']
    coupon_barrier = state['coupon_barrier']
    coupon_rate = state['coupon_rate']
    put_barrier = state['put_barrier']
    currency = state['currency']
    issuer_wallet = state['issuer_wallet']
    holder_wallet = state['holder_wallet']
    memory_feature = state.get('memory_feature', True)
    coupon_memory = state.get('coupon_memory', 0.0)
    put_knocked_in = state.get('put_knocked_in', False)

    # Calculate performance
    performance = spot / initial_spot

    # Prepare observation record
    observation_record = {
        'date': observation_date,
        'spot': spot,
        'performance': performance,
        'autocalled': False,
        'coupon_paid': 0.0,
        'memory_paid': 0.0,
        'total_coupon_earned': 0.0,
        'put_knocked_in': False,
    }

    moves: List[Move] = []
    new_coupon_memory = coupon_memory
    new_put_knocked_in = put_knocked_in
    autocalled = False
    autocall_date = None

    # Step 1: Check autocall
    if performance >= autocall_barrier:
        # Autocall triggered - pay principal + current coupon + memory
        current_coupon = notional * coupon_rate
        payout_per_unit = notional + current_coupon
        memory_paid = 0.0

        if memory_feature and coupon_memory > QUANTITY_EPSILON:
            payout_per_unit += coupon_memory
            memory_paid = coupon_memory
            new_coupon_memory = 0.0

        observation_record['autocalled'] = True
        observation_record['coupon_paid'] = current_coupon
        observation_record['memory_paid'] = memory_paid
        observation_record['total_coupon_earned'] = current_coupon + memory_paid
        autocalled = True
        autocall_date = observation_date

        # Use get_positions to find all current holders
        positions = view.get_positions(symbol)
        for wallet in sorted(positions.keys()):
            units_held = positions[wallet]
            if units_held > 0 and wallet != issuer_wallet:
                payout = units_held * payout_per_unit
                moves.append(Move(
                    source=issuer_wallet,
                    dest=wallet,
                    unit=currency,
                    quantity=payout,
                    contract_id=f'autocall_{symbol}_{observation_date.isoformat()}_{wallet}',
                ))

    else:
        # Step 2: Check coupon barrier
        if performance >= coupon_barrier:
            # Coupon paid
            current_coupon = notional * coupon_rate
            memory_paid = 0.0
            payment_per_unit = current_coupon

            if memory_feature and coupon_memory > QUANTITY_EPSILON:
                # Pay accumulated coupons too
                payment_per_unit += coupon_memory
                memory_paid = coupon_memory
                new_coupon_memory = 0.0

            observation_record['coupon_paid'] = current_coupon
            observation_record['memory_paid'] = memory_paid
            observation_record['total_coupon_earned'] = current_coupon + memory_paid

            # Use get_positions to find all current holders
            positions = view.get_positions(symbol)
            for wallet in sorted(positions.keys()):
                units_held = positions[wallet]
                if units_held > 0 and wallet != issuer_wallet:
                    total_payment = units_held * payment_per_unit
                    moves.append(Move(
                        source=issuer_wallet,
                        dest=wallet,
                        unit=currency,
                        quantity=total_payment,
                        contract_id=f'coupon_{symbol}_{observation_date.isoformat()}_{wallet}',
                    ))
        else:
            # Coupon missed
            if memory_feature:
                new_coupon_memory += notional * coupon_rate

        # Step 3: Check put knock-in (only if not already knocked in)
        if not put_knocked_in and performance <= put_barrier:
            new_put_knocked_in = True
            observation_record['put_knocked_in'] = True

    # Update history
    new_history = list(history)
    new_history.append(observation_record)

    # Build state updates
    state_updates = {
        symbol: {
            **state,
            'observation_history': new_history,
            'coupon_memory': new_coupon_memory,
            'put_knocked_in': new_put_knocked_in,
            'autocalled': autocalled,
            'autocall_date': autocall_date,
            'settled': autocalled,  # If autocalled, it's settled
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


def compute_maturity_payoff(
    view: LedgerView,
    symbol: str,
    final_spot: float,
) -> ContractResult:
    """
    Compute final settlement at maturity if not already autocalled.

    Maturity payoff logic:
    - If already autocalled: No action (already settled)
    - If put knocked in: Principal at risk, pay back min(1.0, final_perf) * notional
    - If put not knocked in: Full principal protection, pay back notional
    - In both cases: Add any accumulated memory coupons

    Args:
        view: Read-only ledger access
        symbol: Autocallable symbol
        final_spot: Final spot price at maturity

    Returns:
        ContractResult with:
        - moves: Final redemption payment
        - state_updates: Mark as settled

    Raises:
        ValueError: If final_spot is not positive

    Example:
        # Maturity with put knocked in, final spot at 50% of initial
        result = compute_maturity_payoff(view, "AUTO_SPX_2025", final_spot=2250.0)
        # Holder receives 50% of notional (loss of 50%)

        # Maturity without knock-in
        result = compute_maturity_payoff(view, "AUTO_SPX_2025", final_spot=4000.0)
        # Holder receives full notional (principal protected)
    """
    if final_spot <= 0:
        raise ValueError(f"final_spot must be positive, got {final_spot}")

    state = view.get_unit_state(symbol)

    # Check if already autocalled or settled
    if state.get('autocalled', False) or state.get('settled', False):
        return ContractResult()

    # Get state values
    initial_spot = state['initial_spot']
    notional = state['notional']
    currency = state['currency']
    issuer_wallet = state['issuer_wallet']
    holder_wallet = state['holder_wallet']
    memory_feature = state.get('memory_feature', True)
    coupon_memory = state.get('coupon_memory', 0.0)
    put_knocked_in = state.get('put_knocked_in', False)

    # Calculate final performance
    final_perf = final_spot / initial_spot

    # Determine payout per unit
    if put_knocked_in:
        # Principal at risk - pay back based on final performance, capped at 100%
        payout_per_unit = notional * min(1.0, final_perf)
    else:
        # Principal protected
        payout_per_unit = notional

    # Add any accumulated memory coupons
    if memory_feature and coupon_memory > QUANTITY_EPSILON:
        payout_per_unit += coupon_memory

    moves: List[Move] = []

    # Use get_positions to find all current holders
    if payout_per_unit > QUANTITY_EPSILON:
        positions = view.get_positions(symbol)
        for wallet in sorted(positions.keys()):
            units_held = positions[wallet]
            if units_held > 0 and wallet != issuer_wallet:
                payout = units_held * payout_per_unit
                moves.append(Move(
                    source=issuer_wallet,
                    dest=wallet,
                    unit=currency,
                    quantity=payout,
                    contract_id=f'maturity_{symbol}_{wallet}',
                ))

    # Build state updates
    state_updates = {
        symbol: {
            **state,
            'settled': True,
            'settlement_date': view.current_time,
            'final_spot': final_spot,
            'final_performance': final_perf,
            'final_payout': payout_per_unit,
            'coupon_memory': 0.0,  # Paid out
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


def transact(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> ContractResult:
    """
    Generate moves and state updates for an autocallable lifecycle event.

    This is the unified entry point for all autocallable lifecycle events,
    routing to the appropriate handler based on event_type.

    Args:
        view: Read-only ledger access
        symbol: Autocallable symbol
        event_type: Type of event (OBSERVATION, MATURITY)
        event_date: When the event occurs
        **kwargs: Event-specific parameters:
            - For OBSERVATION: spot (float, required) - current spot price
            - For MATURITY: final_spot (float, required) - final spot price

    Returns:
        ContractResult with moves and state_updates, or empty result
        if event_type is unknown or required parameters are missing.

    Example:
        # Process an observation
        result = transact(view, "AUTO_SPX_2025", "OBSERVATION",
                         datetime(2024, 4, 15), spot=4800.0)

        # Process maturity settlement
        result = transact(view, "AUTO_SPX_2025", "MATURITY",
                         datetime(2025, 1, 15), final_spot=4200.0)
    """
    if event_type == 'OBSERVATION':
        spot = kwargs.get('spot')
        if spot is None:
            return ContractResult()
        return compute_observation(view, symbol, event_date, spot)

    elif event_type == 'MATURITY':
        final_spot = kwargs.get('final_spot')
        if final_spot is None:
            return ContractResult()
        return compute_maturity_payoff(view, symbol, final_spot)

    else:
        return ContractResult()  # Unknown event type


def autocallable_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> ContractResult:
    """
    SmartContract function for automatic autocallable lifecycle processing.

    This function provides the SmartContract interface required by LifecycleEngine.
    It automatically processes observation dates and maturity when due.

    Processing order:
    1. Check if already settled - return empty if so
    2. Check for observation dates that match timestamp
    3. Check for maturity if timestamp >= maturity_date

    Args:
        view: Read-only ledger access
        symbol: Autocallable symbol to process
        timestamp: Current simulation time
        prices: Price data dictionary (must contain underlying price)

    Returns:
        ContractResult with payment moves if an observation or maturity
        is triggered, or empty result if no events are due.

    Example:
        # Register with LifecycleEngine
        engine = LifecycleEngine(ledger)
        engine.register("AUTOCALLABLE", autocallable_contract)

        # Engine will automatically process observations and maturity
        timestamps = [datetime(2024, 4, 15), datetime(2024, 7, 15), ...]
        prices_func = lambda ts: {"SPX": get_price(ts)}
        engine.run(timestamps, prices_func)
    """
    state = view.get_unit_state(symbol)

    # Check if already settled
    if state.get('settled', False) or state.get('autocalled', False):
        return ContractResult()

    underlying = state.get('underlying')
    spot = prices.get(underlying)
    if spot is None:
        return ContractResult()

    # Check for observation dates
    schedule = state.get('observation_schedule', [])
    for obs_date in schedule:
        if timestamp >= obs_date:
            # Check if this observation has been processed
            history = state.get('observation_history', [])
            processed_dates = [obs['date'] for obs in history]
            if obs_date not in processed_dates:
                return compute_observation(view, symbol, obs_date, spot)

    # Check for maturity
    maturity_date = state.get('maturity_date')
    if maturity_date and timestamp >= maturity_date:
        return compute_maturity_payoff(view, symbol, spot)

    return ContractResult()


def get_autocallable_status(
    view: LedgerView,
    symbol: str,
) -> Dict[str, Any]:
    """
    Get the current status of an autocallable.

    Args:
        view: Read-only ledger access
        symbol: Autocallable symbol

    Returns:
        Dictionary with status information:
        - autocalled: Whether the product has auto-redeemed
        - settled: Whether final settlement has occurred
        - put_knocked_in: Whether put barrier was breached
        - coupon_memory: Accumulated unpaid coupons
        - observations_processed: Number of observations processed
        - next_observation: Next scheduled observation date (if any)

    Example:
        status = get_autocallable_status(view, "AUTO_SPX_2025")
        if status['autocalled']:
            print(f"Autocalled on {status['autocall_date']}")
    """
    state = view.get_unit_state(symbol)

    history = state.get('observation_history', [])
    schedule = state.get('observation_schedule', [])
    processed_dates = set(obs['date'] for obs in history)

    # Find next unprocessed observation
    next_obs = None
    for obs_date in schedule:
        if obs_date not in processed_dates:
            next_obs = obs_date
            break

    return {
        'autocalled': state.get('autocalled', False),
        'autocall_date': state.get('autocall_date'),
        'settled': state.get('settled', False),
        'put_knocked_in': state.get('put_knocked_in', False),
        'coupon_memory': state.get('coupon_memory', 0.0),
        'observations_processed': len(history),
        'total_observations': len(schedule),
        'next_observation': next_obs,
        'notional': state.get('notional', 0.0),
        'initial_spot': state.get('initial_spot', 0.0),
    }


def get_total_coupons_paid(
    view: LedgerView,
    symbol: str,
) -> float:
    """
    Calculate total coupons paid to date.

    Args:
        view: Read-only ledger access
        symbol: Autocallable symbol

    Returns:
        Total coupons paid (including memory coupons)

    Example:
        total = get_total_coupons_paid(view, "AUTO_SPX_2025")
        print(f"Total coupons paid: {total}")
    """
    state = view.get_unit_state(symbol)
    history = state.get('observation_history', [])

    total = 0.0
    for obs in history:
        total += obs.get('coupon_paid', 0.0)
        total += obs.get('memory_paid', 0.0)

    return total
