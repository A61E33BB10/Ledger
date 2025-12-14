"""
portfolio_swap.py - Portfolio Swaps (Total Return Swaps)

This module provides portfolio swap (total return swap) functionality where:
- One party (payer) pays the return of a reference portfolio
- The other party (receiver) receives the portfolio return and pays a funding rate

Key Concepts:
1. Reference Portfolio: A basket of assets with defined weights (must sum to 1.0)
2. NAV Calculation: Net Asset Value based on portfolio weights and current prices
3. Funding Leg: Periodic payment based on notional * spread * time fraction
4. Reset Schedule: Dates when swap settles and NAV baseline resets

Settlement Pattern:
    At each reset date:
    - Calculate portfolio return = (current_nav - last_nav) / last_nav
    - Calculate return amount = notional * portfolio_return
    - Calculate funding amount = notional * funding_spread * (days_elapsed / 365)

    Net settlement:
    - If return_amount > funding_amount:
        Payer owes receiver the difference (portfolio outperformed funding)
    - If funding_amount > return_amount:
        Receiver owes payer the difference (funding exceeded portfolio return)

All functions take LedgerView (read-only) and return immutable results.
"""

from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange,
    QUANTITY_EPSILON, UNIT_TYPE_PORTFOLIO_SWAP,
    build_transaction, empty_pending_transaction,
    _freeze_state,
)


def create_portfolio_swap(
    symbol: str,
    name: str,
    reference_portfolio: Dict[str, Decimal],
    notional: Decimal | float,
    funding_spread: Decimal | float,
    reset_schedule: List[datetime],
    payer_wallet: str,
    receiver_wallet: str,
    currency: str,
    initial_nav: Optional[Decimal | float] = None,
    issue_date: Optional[datetime] = None,
) -> Unit:
    """
    Create a portfolio swap (total return swap) unit.

    A portfolio swap exchanges the total return of a reference portfolio for a
    funding rate. The payer pays the portfolio return; the receiver receives the
    portfolio return and pays the funding rate (spread over benchmark).

    Args:
        symbol: Unique identifier for the swap (e.g., "TRS_SPY_2025")
        name: Human-readable name (e.g., "S&P 500 Total Return Swap")
        reference_portfolio: Dictionary mapping asset symbols to weights.
                            Weights must sum to 1.0 (100%).
                            Example: {"AAPL": 0.3, "GOOG": 0.3, "MSFT": 0.4}
        notional: The notional principal amount for calculations
        funding_spread: Annual funding spread as decimal (e.g., 0.005 = 50 bps)
        reset_schedule: List of reset dates when the swap settles
        payer_wallet: Wallet that pays portfolio return (typically the swap dealer)
        receiver_wallet: Wallet that receives return and pays funding (typically investor)
        currency: Settlement currency (e.g., "USD", "EUR")
        initial_nav: Optional initial NAV. If None, must be set before first reset.
        issue_date: Optional issue date for the swap.

    Returns:
        Unit: A portfolio swap unit with type "PORTFOLIO_SWAP".
        The unit's _state contains:
        - reference_portfolio: asset weights
        - notional: principal amount
        - last_nav: NAV at last reset (for return calculation)
        - funding_spread: annual spread
        - reset_schedule: list of reset dates
        - last_reset_date: date of last reset
        - payer_wallet, receiver_wallet: counterparties
        - currency: settlement currency
        - terminated: whether swap has been terminated
        - next_reset_index: tracks next reset
        - reset_history: audit trail of completed resets

    Raises:
        ValueError: If portfolio weights don't sum to 1.0, notional is not positive,
                   funding_spread is negative, reset_schedule is empty, or wallets
                   are empty/identical.

    Example:
        # Create a total return swap on a 3-stock portfolio
        swap = create_portfolio_swap(
            symbol="TRS_TECH_2025",
            name="Tech Portfolio TRS Q1 2025",
            reference_portfolio={"AAPL": Decimal('0.4'), "GOOG": Decimal('0.35'), "MSFT": Decimal('0.25')},
            notional=Decimal('1000000.0'),
            funding_spread=Decimal('0.0050'),  # 50 bps annual
            reset_schedule=[datetime(2025, 1, 15), datetime(2025, 4, 15)],
            payer_wallet="dealer",
            receiver_wallet="hedge_fund",
            currency="USD",
        )
        ledger.register_unit(swap)
    """
    # Convert float inputs to Decimal
    notional = Decimal(str(notional)) if not isinstance(notional, Decimal) else notional
    funding_spread = Decimal(str(funding_spread)) if not isinstance(funding_spread, Decimal) else funding_spread
    if initial_nav is not None:
        initial_nav = Decimal(str(initial_nav)) if not isinstance(initial_nav, Decimal) else initial_nav

    # Validate portfolio weights sum to 1.0
    if not reference_portfolio:
        raise ValueError("reference_portfolio cannot be empty")

    # Convert all portfolio weights to Decimal
    reference_portfolio = {
        asset: Decimal(str(weight)) if not isinstance(weight, Decimal) else weight
        for asset, weight in reference_portfolio.items()
    }

    weight_sum = sum(reference_portfolio.values())
    if abs(weight_sum - Decimal('1.0')) > QUANTITY_EPSILON:
        raise ValueError(
            f"Portfolio weights must sum to 1.0, got {weight_sum:.6f}"
        )

    # Validate all weights are non-negative
    for asset, weight in reference_portfolio.items():
        if weight < 0:
            raise ValueError(
                f"Portfolio weight for {asset} cannot be negative, got {weight}"
            )

    # Validate notional
    if notional <= 0:
        raise ValueError(f"notional must be positive, got {notional}")

    # Validate funding spread
    if funding_spread < 0:
        raise ValueError(f"funding_spread cannot be negative, got {funding_spread}")

    # Validate reset schedule
    if not reset_schedule:
        raise ValueError("reset_schedule cannot be empty")

    # Validate wallets
    if not payer_wallet or not payer_wallet.strip():
        raise ValueError("payer_wallet cannot be empty")
    if not receiver_wallet or not receiver_wallet.strip():
        raise ValueError("receiver_wallet cannot be empty")
    if payer_wallet == receiver_wallet:
        raise ValueError("payer_wallet and receiver_wallet must be different")

    # Validate currency
    if not currency or not currency.strip():
        raise ValueError("currency cannot be empty")

    # Sort reset schedule
    sorted_schedule = sorted(reset_schedule)

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_PORTFOLIO_SWAP,
        min_balance=Decimal('-1.0'),  # Swaps typically tracked as position count
        max_balance=Decimal('1.0'),
        decimal_places=0,
        transfer_rule=None,
        _frozen_state=_freeze_state({
            'reference_portfolio': dict(reference_portfolio),
            'notional': notional,
            'last_nav': initial_nav,  # May be None until initialized
            'funding_spread': funding_spread,
            'reset_schedule': sorted_schedule,
            'last_reset_date': issue_date,
            'payer_wallet': payer_wallet,
            'receiver_wallet': receiver_wallet,
            'currency': currency,
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
            'issue_date': issue_date,
        })
    )


def compute_portfolio_nav(
    portfolio_weights: Dict[str, Decimal],
    prices: Dict[str, Decimal],
    notional: Decimal | float,
) -> Decimal:
    """
    Calculate the current NAV of a reference portfolio.

    The NAV represents the total value of the portfolio based on current prices
    and the original notional amount.

    NAV = notional * sum(weight_i * price_i / initial_price_i)

    For simplicity, we use: NAV = sum(weight_i * price_i) * notional / 100
    assuming prices are normalized indices starting at 100.

    More typically in practice:
    NAV = sum(weight_i * price_i) where this gives a portfolio index level,
    then multiplied by notional to get dollar value.

    Args:
        portfolio_weights: Dictionary mapping asset symbols to weights (sum to 1.0)
        prices: Dictionary mapping asset symbols to current prices
        notional: The notional principal amount

    Returns:
        Decimal: Current NAV of the portfolio

    Raises:
        ValueError: If a portfolio asset is missing from prices

    Example:
        weights = {"AAPL": Decimal('0.5'), "GOOG": Decimal('0.5')}
        prices = {"AAPL": Decimal('150.0'), "GOOG": Decimal('100.0')}
        nav = compute_portfolio_nav(weights, prices, Decimal('1000000.0'))
        # NAV = (0.5 * 150 + 0.5 * 100) * 1_000_000 / 100 = 1,250,000
    """
    # Convert float inputs to Decimal
    notional = Decimal(str(notional)) if not isinstance(notional, Decimal) else notional

    weighted_price = Decimal('0.0')

    for asset, weight in portfolio_weights.items():
        if asset not in prices:
            raise ValueError(f"Missing price for portfolio asset: {asset}")
        weighted_price += weight * prices[asset]

    # The weighted price gives us a portfolio "index level"
    # NAV is this index level times the notional, normalized
    # Using 100 as the base level for prices
    nav = weighted_price * notional / Decimal('100.0')

    return nav


def compute_funding_amount(
    notional: Decimal | float,
    spread: Decimal | float,
    days: int,
) -> Decimal:
    """
    Calculate the funding leg payment for a period.

    The funding amount is calculated using ACT/365 day count convention:
    funding = notional * spread * (days / 365)

    Args:
        notional: The notional principal amount
        spread: Annual funding spread as decimal (e.g., 0.005 = 50 bps)
        days: Number of days in the period

    Returns:
        Decimal: Funding amount for the period

    Example:
        # 50 bps on $1M for 90 days
        funding = compute_funding_amount(Decimal('1000000.0'), Decimal('0.005'), 90)
        # funding = 1,000,000 * 0.005 * (90/365) = 1,232.88
    """
    # Convert float inputs to Decimal
    notional = Decimal(str(notional)) if not isinstance(notional, Decimal) else notional
    spread = Decimal(str(spread)) if not isinstance(spread, Decimal) else spread

    if days < 0:
        raise ValueError(f"days cannot be negative, got {days}")

    return notional * spread * (Decimal(days) / Decimal('365'))


def compute_swap_reset(
    view: LedgerView,
    symbol: str,
    current_nav: Decimal | float,
    funding_rate: Decimal | float,
    days_elapsed: int,
) -> PendingTransaction:
    """
    Compute the periodic reset settlement for a portfolio swap.

    At each reset:
    1. Calculate portfolio return = (current_nav - last_nav) / last_nav
    2. Calculate return amount = notional * portfolio_return
    3. Calculate funding amount = notional * funding_spread * (days / 365)
    4. Net settlement determines direction of payment

    Args:
        view: Read-only view of the ledger state
        symbol: Portfolio swap symbol
        current_nav: Current NAV of the reference portfolio
        funding_rate: The funding spread to use (from state, or override)
        days_elapsed: Days since last reset for funding calculation

    Returns:
        PendingTransaction with:
        - moves: Settlement payment move (if non-zero)
        - state_updates: Updated last_nav, last_reset_date, reset_history

    Raises:
        ValueError: If swap is terminated or last_nav is not set

    Example:
        # Reset with NAV increase from 1M to 1.05M over 90 days
        result = compute_swap_reset(view, "TRS_TECH", Decimal('1050000.0'), Decimal('0.005'), 90)
        # return_amount = 1M * 0.05 = 50,000
        # funding_amount = 1M * 0.005 * (90/365) = 1,232.88
        # net = 50,000 - 1,232.88 = 48,767.12 (payer to receiver)
    """
    # Convert float inputs to Decimal
    current_nav = Decimal(str(current_nav)) if not isinstance(current_nav, Decimal) else current_nav
    funding_rate = Decimal(str(funding_rate)) if not isinstance(funding_rate, Decimal) else funding_rate

    if current_nav <= 0:
        raise ValueError(f"current_nav must be positive, got {current_nav}")
    if days_elapsed < 0:
        raise ValueError(f"days_elapsed cannot be negative, got {days_elapsed}")

    state = view.get_unit_state(symbol)

    if state.get('terminated', False):
        return empty_pending_transaction(view)  # Already terminated

    last_nav = state.get('last_nav')
    if last_nav is None:
        raise ValueError(
            f"last_nav not initialized for swap {symbol}. "
            "Set initial_nav when creating the swap or initialize before first reset."
        )

    # Convert state values to Decimal if they're floats
    last_nav = Decimal(str(last_nav)) if not isinstance(last_nav, Decimal) else last_nav
    notional = state['notional']
    notional = Decimal(str(notional)) if not isinstance(notional, Decimal) else notional

    # HIGH-3 FIX (v4.1): Guard against division by zero
    if last_nav <= Decimal("0"):
        raise ValueError(f"last_nav must be positive for portfolio return calculation, got {last_nav}")

    payer_wallet = state['payer_wallet']
    receiver_wallet = state['receiver_wallet']
    currency = state['currency']
    next_reset_index = state.get('next_reset_index', 0)
    reset_history = list(state.get('reset_history', []))

    # Calculate portfolio return
    portfolio_return = (current_nav - last_nav) / last_nav
    return_amount = notional * portfolio_return

    # Calculate funding amount
    funding_amount = compute_funding_amount(notional, funding_rate, days_elapsed)

    # Net settlement
    # Positive return_amount means portfolio went up (payer owes receiver)
    # Positive funding_amount means receiver owes funding (reduces what receiver gets)
    net_settlement = return_amount - funding_amount

    moves: List[Move] = []

    if abs(net_settlement) > QUANTITY_EPSILON:
        if net_settlement > 0:
            # Payer owes receiver (portfolio outperformed funding)
            moves.append(Move(
                quantity=net_settlement,
                unit_symbol=currency,
                source=payer_wallet,
                dest=receiver_wallet,
                contract_id=f'swap_reset_{symbol}_{next_reset_index}',
            ))
        else:
            # Receiver owes payer (funding exceeded portfolio return)
            moves.append(Move(
                quantity=-net_settlement,
                unit_symbol=currency,
                source=receiver_wallet,
                dest=payer_wallet,
                contract_id=f'swap_reset_{symbol}_{next_reset_index}',
            ))

    # Record reset in history
    reset_history.append({
        'reset_number': next_reset_index,
        'reset_date': view.current_time,
        'last_nav': last_nav,
        'current_nav': current_nav,
        'portfolio_return': portfolio_return,
        'return_amount': return_amount,
        'funding_amount': funding_amount,
        'net_settlement': net_settlement,
        'days_elapsed': days_elapsed,
    })

    # Update state
    new_state = {
        **state,
        'last_nav': current_nav,
        'last_reset_date': view.current_time,
        'next_reset_index': next_reset_index + 1,
        'reset_history': reset_history,
    }
    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


def compute_termination(
    view: LedgerView,
    symbol: str,
    final_nav: Decimal | float,
    funding_rate: Decimal | float,
    days_elapsed: int,
) -> PendingTransaction:
    """
    Compute early or scheduled termination of a portfolio swap.

    Termination performs a final reset settlement and marks the swap as terminated.
    This handles both scheduled maturity and early termination scenarios.

    Args:
        view: Read-only view of the ledger state
        symbol: Portfolio swap symbol
        final_nav: Final NAV at termination
        funding_rate: The funding spread for the final period
        days_elapsed: Days since last reset

    Returns:
        PendingTransaction with:
        - moves: Final settlement payment move (if non-zero)
        - state_updates: Marks swap as terminated

    Example:
        # Early termination with final NAV
        result = compute_termination(view, "TRS_TECH", Decimal('980000.0'), Decimal('0.005'), 45)
    """
    # Convert float inputs to Decimal
    final_nav = Decimal(str(final_nav)) if not isinstance(final_nav, Decimal) else final_nav
    funding_rate = Decimal(str(funding_rate)) if not isinstance(funding_rate, Decimal) else funding_rate

    if final_nav <= 0:
        raise ValueError(f"final_nav must be positive, got {final_nav}")
    if days_elapsed < 0:
        raise ValueError(f"days_elapsed cannot be negative, got {days_elapsed}")

    state = view.get_unit_state(symbol)

    if state.get('terminated', False):
        return empty_pending_transaction(view)  # Already terminated

    last_nav = state.get('last_nav')
    if last_nav is None:
        raise ValueError(
            f"last_nav not initialized for swap {symbol}. "
            "Cannot terminate without a baseline NAV."
        )

    # Convert state values to Decimal if they're floats
    last_nav = Decimal(str(last_nav)) if not isinstance(last_nav, Decimal) else last_nav
    notional = state['notional']
    notional = Decimal(str(notional)) if not isinstance(notional, Decimal) else notional

    # HIGH-3 FIX (v4.1): Guard against division by zero
    if last_nav <= Decimal("0"):
        raise ValueError(f"last_nav must be positive for portfolio return calculation, got {last_nav}")

    payer_wallet = state['payer_wallet']
    receiver_wallet = state['receiver_wallet']
    currency = state['currency']
    next_reset_index = state.get('next_reset_index', 0)
    reset_history = list(state.get('reset_history', []))

    # Calculate final settlement (same logic as reset)
    portfolio_return = (final_nav - last_nav) / last_nav
    return_amount = notional * portfolio_return
    funding_amount = compute_funding_amount(notional, funding_rate, days_elapsed)
    net_settlement = return_amount - funding_amount

    moves: List[Move] = []

    if abs(net_settlement) > QUANTITY_EPSILON:
        if net_settlement > 0:
            moves.append(Move(
                quantity=net_settlement,
                unit_symbol=currency,
                source=payer_wallet,
                dest=receiver_wallet,
                contract_id=f'swap_termination_{symbol}',
            ))
        else:
            moves.append(Move(
                quantity=-net_settlement,
                unit_symbol=currency,
                source=receiver_wallet,
                dest=payer_wallet,
                contract_id=f'swap_termination_{symbol}',
            ))

    # Record final reset in history
    reset_history.append({
        'reset_number': next_reset_index,
        'reset_date': view.current_time,
        'last_nav': last_nav,
        'current_nav': final_nav,
        'portfolio_return': portfolio_return,
        'return_amount': return_amount,
        'funding_amount': funding_amount,
        'net_settlement': net_settlement,
        'days_elapsed': days_elapsed,
        'is_termination': True,
    })

    # Update state - mark as terminated
    new_state = {
        **state,
        'last_nav': final_nav,
        'last_reset_date': view.current_time,
        'next_reset_index': next_reset_index + 1,
        'reset_history': reset_history,
        'terminated': True,
        'termination_date': view.current_time,
        'termination_nav': final_nav,
    }
    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


def transact(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> PendingTransaction:
    """
    Generate moves and state updates for a portfolio swap lifecycle event.

    This is the unified entry point for all portfolio swap lifecycle events,
    routing to the appropriate handler based on event_type.

    Args:
        view: Read-only ledger access
        symbol: Portfolio swap symbol
        event_type: Type of event (RESET, TERMINATION, INITIALIZE)
        event_date: When the event occurs
        **kwargs: Event-specific parameters:
            - For RESET: current_nav (Decimal), days_elapsed (int),
                        funding_rate (Decimal, optional - uses state default)
            - For TERMINATION: final_nav (Decimal), days_elapsed (int),
                              funding_rate (Decimal, optional)
            - For INITIALIZE: initial_nav (Decimal) - sets the baseline NAV

    Returns:
        PendingTransaction with moves and state_updates, or empty result
        if event_type is unknown or required parameters are missing.

    Example:
        # Initialize swap with starting NAV
        result = transact(view, "TRS_TECH", "INITIALIZE", datetime(2025, 1, 1),
                         initial_nav=Decimal('1000000.0'))

        # Periodic reset
        result = transact(view, "TRS_TECH", "RESET", datetime(2025, 4, 1),
                         current_nav=Decimal('1050000.0'), days_elapsed=90)

        # Early termination
        result = transact(view, "TRS_TECH", "TERMINATION", datetime(2025, 6, 1),
                         final_nav=Decimal('1020000.0'), days_elapsed=61)
    """
    state = view.get_unit_state(symbol)

    if event_type == 'INITIALIZE':
        # Initialize the baseline NAV
        initial_nav = kwargs.get('initial_nav')
        if initial_nav is None:
            return empty_pending_transaction(view)

        # Convert float to Decimal
        initial_nav = Decimal(str(initial_nav)) if not isinstance(initial_nav, Decimal) else initial_nav

        if initial_nav <= 0:
            return empty_pending_transaction(view)

        new_state = {
            **state,
            'last_nav': initial_nav,
            'last_reset_date': event_date,
        }
        state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]
        return build_transaction(view, [], state_changes)

    elif event_type == 'RESET':
        current_nav = kwargs.get('current_nav')
        days_elapsed = kwargs.get('days_elapsed')
        if current_nav is None or days_elapsed is None:
            return empty_pending_transaction(view)

        funding_rate = kwargs.get('funding_rate', state.get('funding_spread', Decimal('0.0')))
        return compute_swap_reset(view, symbol, current_nav, funding_rate, days_elapsed)

    elif event_type == 'TERMINATION':
        final_nav = kwargs.get('final_nav')
        days_elapsed = kwargs.get('days_elapsed')
        if final_nav is None or days_elapsed is None:
            return empty_pending_transaction(view)

        funding_rate = kwargs.get('funding_rate', state.get('funding_spread', Decimal('0.0')))
        return compute_termination(view, symbol, final_nav, funding_rate, days_elapsed)

    else:
        return empty_pending_transaction(view)  # Unknown event type


def portfolio_swap_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, Decimal]
) -> PendingTransaction:
    """
    SmartContract function for automatic portfolio swap processing.

    This function provides the SmartContract interface required by LifecycleEngine.
    It automatically processes reset events when due based on the reset schedule.

    The engine calls this function at each timestamp. If a reset date has been
    reached, it calculates the current NAV from prices and processes the reset.

    Args:
        view: Read-only view of the ledger state
        symbol: Portfolio swap symbol to process
        timestamp: Current simulation time
        prices: Market prices dictionary (must contain all portfolio assets)

    Returns:
        PendingTransaction with reset moves if a reset date has been reached,
        or empty result if no events are due.

    Example:
        # Register with LifecycleEngine
        engine = LifecycleEngine(ledger)
        engine.register("PORTFOLIO_SWAP", portfolio_swap_contract)

        # Engine will automatically process resets
        timestamps = [datetime(2025, 1, i) for i in range(1, 120)]
        prices_func = lambda ts: {"AAPL": Decimal('150.0'), "GOOG": Decimal('100.0')}
        engine.run(timestamps, prices_func)
    """
    state = view.get_unit_state(symbol)

    if state.get('terminated', False):
        return empty_pending_transaction(view)

    reset_schedule = state.get('reset_schedule', [])
    next_reset_index = state.get('next_reset_index', 0)

    if next_reset_index >= len(reset_schedule):
        return empty_pending_transaction(view)  # All resets processed

    next_reset_date = reset_schedule[next_reset_index]
    if timestamp < next_reset_date:
        return empty_pending_transaction(view)  # Not yet time for reset

    # Time for a reset - calculate current NAV
    portfolio = state.get('reference_portfolio', {})
    notional = state.get('notional', Decimal('0.0'))
    # Convert notional to Decimal if it's a float
    notional = Decimal(str(notional)) if not isinstance(notional, Decimal) else notional

    try:
        current_nav = compute_portfolio_nav(portfolio, prices, notional)
    except ValueError:
        return empty_pending_transaction(view)  # Missing prices

    # Calculate days elapsed
    last_reset_date = state.get('last_reset_date')
    if last_reset_date is None:
        # First reset - use issue date or assume 0 days funding
        issue_date = state.get('issue_date')
        if issue_date:
            days_elapsed = (next_reset_date - issue_date).days
        else:
            days_elapsed = 0
    else:
        days_elapsed = (next_reset_date - last_reset_date).days

    funding_rate = state.get('funding_spread', Decimal('0.0'))
    # Convert funding_rate to Decimal if it's a float
    funding_rate = Decimal(str(funding_rate)) if not isinstance(funding_rate, Decimal) else funding_rate

    # Check if last_nav is initialized
    if state.get('last_nav') is None:
        # FIRST RESET: Establishes the NAV baseline for future return calculations.
        #
        # At the first reset, we have no prior NAV to compute a portfolio return,
        # so return_amount = 0. However, if an issue_date exists and time has passed,
        # funding still accrues from issue_date to first reset.
        #
        # Settlement logic:
        # - Portfolio return leg: 0 (no prior NAV to compare against)
        # - Funding leg: notional * spread * (days from issue_date to first reset)
        #
        # The receiver pays funding to the payer if days_elapsed > 0 and spread > 0.

        payer_wallet = state['payer_wallet']
        receiver_wallet = state['receiver_wallet']
        currency = state['currency']
        notional_for_funding = state.get('notional', Decimal('0.0'))
        # Convert notional to Decimal if it's a float
        notional_for_funding = Decimal(str(notional_for_funding)) if not isinstance(notional_for_funding, Decimal) else notional_for_funding
        reset_history = list(state.get('reset_history', []))

        moves: List[Move] = []

        # Compute funding for the period from issue_date to first reset
        funding_amount = compute_funding_amount(notional_for_funding, funding_rate, days_elapsed)

        if abs(funding_amount) > QUANTITY_EPSILON:
            # Receiver pays funding to payer (no portfolio return to offset)
            moves.append(Move(
                quantity=funding_amount,
                unit_symbol=currency,
                source=receiver_wallet,
                dest=payer_wallet,
                contract_id=f'swap_reset_{symbol}_{next_reset_index}',
            ))

        # Record first reset in history
        reset_history.append({
            'reset_number': next_reset_index,
            'reset_date': timestamp,
            'last_nav': None,  # No prior NAV
            'current_nav': current_nav,
            'portfolio_return': Decimal('0.0'),  # First reset: no return calculation
            'return_amount': Decimal('0.0'),
            'funding_amount': funding_amount,
            'net_settlement': -funding_amount,  # Negative = receiver pays
            'days_elapsed': days_elapsed,
            'is_initial_reset': True,
        })

        new_state = {
            **state,
            'last_nav': current_nav,
            'last_reset_date': timestamp,
            'next_reset_index': next_reset_index + 1,
            'reset_history': reset_history,
        }
        state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]
        return build_transaction(view, moves, state_changes)

    return compute_swap_reset(view, symbol, current_nav, funding_rate, days_elapsed)
