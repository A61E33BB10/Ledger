"""
qis.py - Quantitative Investment Strategy (QIS)

A QIS is a total return swap on a self-financing, leveraged hypothetical portfolio.

Key insight: QIS = NAV tracking + Strategy function + Financing costs + Settlement

The hypothetical portfolio is just state variables:
- holdings: Dict[str, float]  # asset -> quantity (phi_t)
- cash: float                 # cash balance (C_t, negative when leveraged)

The strategy is just a function:
- Strategy: (nav, prices, state) -> target_holdings

Core equations from the QIS spec:
- NAV: V_t = sum(phi_t^i * P_t^i) + C_t
- Financing: C_{t+dt} = C_t * e^{r*dt}
- Self-financing: NAV before rebalance = NAV after rebalance
- Payoff: Payoff_T = N * (V_T / V_0 - 1)

~250 lines. One file. No unnecessary abstractions.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
import math

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange,
    QUANTITY_EPSILON,
    build_transaction, empty_pending_transaction,
    TransactionOrigin, OriginType,
)


# ============================================================================
# CONSTANTS
# ============================================================================

UNIT_TYPE_QIS = "QIS"

# Days per year for financing calculations
DAYS_PER_YEAR = 365.0


# ============================================================================
# STRATEGY TYPE
# ============================================================================

# A strategy is just a function: (nav, prices, state) -> target_holdings
# - nav: current portfolio NAV
# - prices: dict of asset prices
# - state: QIS state dict (for access to params, history, etc.)
# Returns: Dict[str, float] mapping asset symbols to target quantities
Strategy = Callable[[float, Dict[str, float], Dict[str, Any]], Dict[str, float]]


# ============================================================================
# PURE FUNCTIONS - The math, nothing else
# ============================================================================

def compute_nav(
    holdings: Dict[str, float],
    cash: float,
    prices: Dict[str, float],
) -> float:
    """
    Compute NAV of the hypothetical portfolio.

    V_t = sum_i(phi_t^i * P_t^i) + C_t

    Args:
        holdings: asset symbol -> quantity
        cash: cash balance (can be negative for leverage)
        prices: asset symbol -> price

    Returns:
        Net Asset Value
    """
    risky_value = sum(
        qty * prices.get(symbol, 0.0)
        for symbol, qty in holdings.items()
    )
    return risky_value + cash


def accrue_financing(
    cash: float,
    rate: float,
    days: float,
) -> float:
    """
    Apply financing cost to cash balance using continuous compounding.

    C_{t+dt} = C_t * e^{r*dt}

    For negative cash (borrowing), this makes it more negative (cost).
    For positive cash, this makes it more positive (income).

    Args:
        cash: current cash balance
        rate: annual financing rate
        days: days elapsed

    Returns:
        Updated cash balance after financing
    """
    if days <= 0 or abs(rate) < QUANTITY_EPSILON:
        return cash

    year_fraction = days / DAYS_PER_YEAR
    return cash * math.exp(rate * year_fraction)


def compute_rebalance(
    current_holdings: Dict[str, float],
    current_cash: float,
    target_holdings: Dict[str, float],
    prices: Dict[str, float],
) -> tuple[Dict[str, float], float]:
    """
    Execute a self-financing rebalance.

    Self-financing constraint: NAV before = NAV after
    Cash adjusts to absorb the cost of trades.

    Args:
        current_holdings: current positions
        current_cash: current cash
        target_holdings: target positions from strategy
        prices: execution prices

    Returns:
        (new_holdings, new_cash)

    The self-financing constraint is automatically satisfied:
    - Buy delta shares -> cash decreases by delta * price
    - Sell delta shares -> cash increases by delta * price
    """
    # Compute NAV before
    nav_before = compute_nav(current_holdings, current_cash, prices)

    # Compute cash delta from trades
    all_symbols = set(current_holdings.keys()) | set(target_holdings.keys())
    cash_delta = 0.0

    for symbol in all_symbols:
        old_qty = current_holdings.get(symbol, 0.0)
        new_qty = target_holdings.get(symbol, 0.0)
        delta = new_qty - old_qty
        price = prices.get(symbol, 0.0)
        # Buying (delta > 0) costs cash, selling recovers cash
        cash_delta -= delta * price

    new_cash = current_cash + cash_delta

    # Clean up zero holdings
    new_holdings = {s: q for s, q in target_holdings.items() if abs(q) > QUANTITY_EPSILON}

    # Verify self-financing (defense in depth)
    nav_after = compute_nav(new_holdings, new_cash, prices)
    if abs(nav_after - nav_before) > 0.01:  # 1 cent tolerance
        raise ValueError(
            f"Self-financing violated: NAV changed from {nav_before:.4f} to {nav_after:.4f}"
        )

    return new_holdings, new_cash


def compute_payoff(
    final_nav: float,
    initial_nav: float,
    notional: float,
) -> float:
    """
    Compute QIS payoff at maturity.

    Payoff_T = N * (V_T / V_0 - 1)

    Positive: strategy made money, dealer pays investor
    Negative: strategy lost money, investor pays dealer
    """
    if initial_nav <= 0:
        raise ValueError(f"initial_nav must be positive, got {initial_nav}")

    total_return = (final_nav / initial_nav) - 1.0
    return notional * total_return


# ============================================================================
# UNIT CREATION
# ============================================================================

def create_qis(
    symbol: str,
    name: str,
    notional: float,
    initial_nav: float,
    funding_rate: float,
    payer_wallet: str,
    receiver_wallet: str,
    currency: str,
    eligible_assets: List[str],
    rebalance_dates: List[datetime],
    maturity_date: datetime,
    inception_date: Optional[datetime] = None,
) -> Unit:
    """
    Create a QIS (Quantitative Investment Strategy) unit.

    Args:
        symbol: Unique identifier (e.g., "QIS_2X_SPX")
        name: Human-readable name
        notional: Principal amount for payoff calculation (N)
        initial_nav: Starting NAV (V_0)
        funding_rate: Annual financing rate for borrowed cash
        payer_wallet: Dealer wallet (pays positive returns)
        receiver_wallet: Investor wallet (receives returns)
        currency: Settlement currency symbol
        eligible_assets: Assets the strategy can hold
        rebalance_dates: Scheduled rebalancing dates
        maturity_date: Final settlement date
        inception_date: Start date (defaults to first rebalance)

    Returns:
        Unit with type "QIS"

    Example:
        qis = create_qis(
            symbol="QIS_2X_SPX",
            name="2x Leveraged S&P 500",
            notional=1_000_000,
            initial_nav=100.0,  # Start with $100 NAV
            funding_rate=0.05,
            payer_wallet="dealer",
            receiver_wallet="investor",
            currency="USD",
            eligible_assets=["SPX"],
            rebalance_dates=[...],
            maturity_date=datetime(2025, 12, 31),
        )
    """
    # Validation
    if notional <= 0:
        raise ValueError(f"notional must be positive, got {notional}")
    if initial_nav <= 0:
        raise ValueError(f"initial_nav must be positive, got {initial_nav}")
    if not payer_wallet or not payer_wallet.strip():
        raise ValueError("payer_wallet cannot be empty")
    if not receiver_wallet or not receiver_wallet.strip():
        raise ValueError("receiver_wallet cannot be empty")
    if payer_wallet == receiver_wallet:
        raise ValueError("payer_wallet and receiver_wallet must be different")
    if not rebalance_dates:
        raise ValueError("rebalance_dates cannot be empty")

    sorted_dates = sorted(rebalance_dates)
    inception = inception_date or sorted_dates[0]

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_QIS,
        min_balance=-1.0,  # Position tracking, not balance
        max_balance=1.0,
        decimal_places=0,
        transfer_rule=None,
        _state={
            # Term sheet (immutable)
            'notional': notional,
            'initial_nav': initial_nav,
            'funding_rate': funding_rate,
            'payer_wallet': payer_wallet,
            'receiver_wallet': receiver_wallet,
            'currency': currency,
            'eligible_assets': list(eligible_assets),
            'rebalance_dates': sorted_dates,
            'maturity_date': maturity_date,
            'inception_date': inception,

            # Portfolio state (mutable via transactions)
            'holdings': {},           # phi_t: asset -> quantity
            'cash': initial_nav,      # C_t: starts as full NAV in cash
            'nav': initial_nav,       # V_t: current NAV

            # Lifecycle tracking
            'next_rebalance_idx': 0,
            'last_rebalance_date': inception,
            'rebalance_count': 0,
            'terminated': False,
            'final_nav': None,
            'final_return': None,
        }
    )


# ============================================================================
# LIFECYCLE FUNCTIONS
# ============================================================================

def compute_qis_rebalance(
    view: LedgerView,
    symbol: str,
    strategy: Strategy,
    prices: Dict[str, float],
) -> PendingTransaction:
    """
    Execute a rebalancing of the QIS hypothetical portfolio.

    Steps:
    1. Accrue financing since last rebalance
    2. Compute current NAV
    3. Call strategy to get target holdings
    4. Execute self-financing trades
    5. Update state

    No real moves occur - this is all within the hypothetical portfolio.
    """
    state = view.get_unit_state(symbol)

    if state.get('terminated'):
        return empty_pending_transaction(view)

    # Accrue financing
    last_date = state['last_rebalance_date']
    days_elapsed = (view.current_time - last_date).total_seconds() / 86400.0

    current_cash = state['cash']
    cash_after_financing = accrue_financing(current_cash, state['funding_rate'], days_elapsed)

    # Compute NAV
    holdings = dict(state['holdings'])
    nav = compute_nav(holdings, cash_after_financing, prices)

    # Call strategy
    target_holdings = strategy(nav, prices, state)

    # Validate eligible assets
    for asset in target_holdings:
        if asset not in state['eligible_assets']:
            raise ValueError(f"Asset {asset} not in eligible_assets")

    # Rebalance (self-financing)
    new_holdings, new_cash = compute_rebalance(
        holdings, cash_after_financing, target_holdings, prices
    )

    # Build new state
    new_state = {
        **state,
        'holdings': new_holdings,
        'cash': new_cash,
        'nav': nav,
        'last_rebalance_date': view.current_time,
        'rebalance_count': state['rebalance_count'] + 1,
        'next_rebalance_idx': state['next_rebalance_idx'] + 1,
    }

    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, [], state_changes)


def compute_qis_settlement(
    view: LedgerView,
    symbol: str,
    prices: Dict[str, float],
) -> PendingTransaction:
    """
    Compute final settlement of the QIS at maturity.

    Payoff_T = N * (V_T / V_0 - 1)

    Positive payoff: dealer pays investor
    Negative payoff: investor pays dealer
    """
    state = view.get_unit_state(symbol)

    if state.get('terminated'):
        return empty_pending_transaction(view)

    # Accrue final financing
    last_date = state['last_rebalance_date']
    days_elapsed = (view.current_time - last_date).total_seconds() / 86400.0

    cash_after_financing = accrue_financing(state['cash'], state['funding_rate'], days_elapsed)

    # Compute final NAV
    holdings = dict(state['holdings'])
    final_nav = compute_nav(holdings, cash_after_financing, prices)

    # Compute payoff
    initial_nav = state['initial_nav']
    notional = state['notional']
    payoff = compute_payoff(final_nav, initial_nav, notional)
    total_return = (final_nav / initial_nav) - 1.0

    # Generate settlement move
    payer = state['payer_wallet']
    receiver = state['receiver_wallet']
    currency = state['currency']

    moves = []
    if abs(payoff) > QUANTITY_EPSILON:
        if payoff > 0:
            # Strategy made money - dealer pays investor
            moves.append(Move(
                quantity=payoff,
                unit_symbol=currency,
                source=payer,
                dest=receiver,
                contract_id=f'qis_settlement_{symbol}',
            ))
        else:
            # Strategy lost money - investor pays dealer
            moves.append(Move(
                quantity=-payoff,
                unit_symbol=currency,
                source=receiver,
                dest=payer,
                contract_id=f'qis_settlement_{symbol}',
            ))

    # Update state to terminated
    new_state = {
        **state,
        'holdings': {},
        'cash': 0.0,
        'nav': final_nav,
        'terminated': True,
        'final_nav': final_nav,
        'final_return': total_return,
    }

    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


# ============================================================================
# SMART CONTRACT
# ============================================================================

def qis_contract(
    strategy: Strategy,
) -> Callable[[LedgerView, str, datetime, Dict[str, float]], PendingTransaction]:
    """
    Create a QIS smart contract bound to a specific strategy.

    The returned function can be registered with LifecycleEngine.

    Args:
        strategy: The trading strategy function

    Returns:
        SmartContract-compatible function

    Example:
        def leveraged_2x(nav, prices, state):
            price = prices.get("SPX", 0)
            return {"SPX": (2.0 * nav) / price} if price > 0 else {}

        engine.register("QIS", qis_contract(leveraged_2x))
    """
    def check_lifecycle(
        view: LedgerView,
        symbol: str,
        timestamp: datetime,
        prices: Dict[str, float],
    ) -> PendingTransaction:
        state = view.get_unit_state(symbol)

        if state.get('terminated'):
            return empty_pending_transaction(view)

        maturity = state['maturity_date']

        # Check if at or past maturity
        if timestamp >= maturity:
            return compute_qis_settlement(view, symbol, prices)

        # Check if rebalance is due
        rebalance_dates = state['rebalance_dates']
        next_idx = state.get('next_rebalance_idx', 0)

        if next_idx < len(rebalance_dates):
            next_date = rebalance_dates[next_idx]
            if timestamp >= next_date:
                return compute_qis_rebalance(view, symbol, strategy, prices)

        return empty_pending_transaction(view)

    return check_lifecycle


# ============================================================================
# BUILT-IN STRATEGIES
# ============================================================================

def leveraged_strategy(underlying: str, leverage: float) -> Strategy:
    """
    Create a leveraged strategy for a single underlying.

    Target: holdings * price = leverage * NAV
    Cash: (1 - leverage) * NAV (negative when leverage > 1)

    Args:
        underlying: Asset symbol to hold
        leverage: Target leverage (e.g., 2.0 for 2x)

    Returns:
        Strategy function

    Example:
        # 2x leveraged SPX
        strategy = leveraged_strategy("SPX", 2.0)
    """
    def strategy_fn(nav: float, prices: Dict[str, float], state: Dict[str, Any]) -> Dict[str, float]:
        price = prices.get(underlying)
        if not price or price <= 0:
            return {}  # Can't trade without price

        target_value = leverage * nav
        target_qty = target_value / price

        return {underlying: target_qty}

    return strategy_fn


def fixed_weight_strategy(weights: Dict[str, float]) -> Strategy:
    """
    Create a fixed-weight allocation strategy.

    Maintains constant portfolio weights across assets.

    Args:
        weights: Asset symbol -> target weight (should sum to <= 1.0)

    Returns:
        Strategy function

    Example:
        # 60/40 equity/bond
        strategy = fixed_weight_strategy({"SPX": 0.6, "TLT": 0.4})
    """
    def strategy_fn(nav: float, prices: Dict[str, float], state: Dict[str, Any]) -> Dict[str, float]:
        holdings = {}
        for symbol, weight in weights.items():
            price = prices.get(symbol)
            if price and price > 0:
                target_value = weight * nav
                holdings[symbol] = target_value / price
        return holdings

    return strategy_fn


# ============================================================================
# QUERY FUNCTIONS
# ============================================================================

def get_qis_nav(view: LedgerView, symbol: str, prices: Dict[str, float]) -> float:
    """Get current NAV of a QIS given prices."""
    state = view.get_unit_state(symbol)
    return compute_nav(state['holdings'], state['cash'], prices)


def get_qis_return(view: LedgerView, symbol: str, prices: Dict[str, float]) -> float:
    """Get current total return of a QIS."""
    state = view.get_unit_state(symbol)
    current_nav = compute_nav(state['holdings'], state['cash'], prices)
    initial_nav = state['initial_nav']
    return (current_nav / initial_nav) - 1.0


def get_qis_leverage(view: LedgerView, symbol: str, prices: Dict[str, float]) -> float:
    """Get current leverage ratio of a QIS."""
    state = view.get_unit_state(symbol)
    holdings = state['holdings']
    cash = state['cash']

    risky_value = sum(qty * prices.get(s, 0) for s, qty in holdings.items())
    nav = risky_value + cash

    if abs(nav) < QUANTITY_EPSILON:
        return float('inf')

    return risky_value / nav
