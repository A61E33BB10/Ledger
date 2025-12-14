"""
delta_hedge_strategy.py - Delta Hedging Strategy for Call Options

This module provides a complete delta hedging framework for call options.
Delta hedging is a risk management strategy that maintains a market-neutral position
by dynamically adjusting the underlying asset holdings to offset option price sensitivity.

The strategy tracks a call option position and automatically rebalances the underlying
stock holdings to maintain delta neutrality. All operations are implemented as pure
functions that take a LedgerView (read-only snapshot) and return immutable results.

Key Components:
- Strategy unit creation with term sheet parameters
- Automatic rebalancing based on Black-Scholes delta
- Position liquidation at maturity
- Comprehensive P&L tracking and analysis
- Smart contract integration for automated lifecycle management
"""

from __future__ import annotations
from datetime import datetime
from decimal import Decimal
import math
from typing import Dict, Any, List

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange, UNIT_TYPE_DELTA_HEDGE_STRATEGY,
    build_transaction, empty_pending_transaction, _freeze_state,
)
from ..black_scholes import call_s as bs_call_delta, call as bs_call_price


def create_delta_hedge_unit(
    symbol: str,
    name: str,
    underlying: str,
    strike: Decimal,
    maturity: datetime,
    volatility: Decimal,
    num_options: Decimal,
    option_multiplier: int,
    currency: str,
    strategy_wallet: str,
    market_wallet: str,
    risk_free_rate: Decimal = Decimal("0.0"),
) -> Unit:
    """
    Create a delta hedge strategy unit with complete term sheet configuration.

    A delta hedge strategy unit represents a call option position paired with
    a dynamic hedging program. The unit stores all contract parameters and tracks
    the evolving hedge state including share holdings, cash flows, and rebalance history.

    Args:
        symbol: Unique identifier for this strategy (e.g., "AAPL_HEDGE_150_DEC25")
        name: Human-readable description of the strategy
        underlying: Symbol of the underlying asset being hedged (e.g., "AAPL")
        strike: Option strike price in currency units
        maturity: Option expiration datetime (timezone-aware recommended)
        volatility: Annualized volatility for Black-Scholes calculations (e.g., 0.20 for 20%)
        num_options: Number of call option contracts (positive for long positions)
        option_multiplier: Number of shares per option contract (typically 100)
        currency: Currency unit for all cash flows (e.g., "USD")
        strategy_wallet: Wallet address that holds the hedge positions
        market_wallet: Counterparty wallet address for executing trades
        risk_free_rate: Annualized risk-free rate for option pricing (default 0.0)

    Returns:
        Unit: A configured delta hedge strategy unit with type "DELTA_HEDGE_STRATEGY".
              Initial state includes zero shares held, zero cumulative cash, and
              ready-to-trade status.

    Example:
        >>> unit = create_delta_hedge_unit(
        ...     symbol="AAPL_HEDGE_150_DEC25",
        ...     name="AAPL 150 Call Hedge",
        ...     underlying="AAPL",
        ...     strike=150.0,
        ...     maturity=datetime(2025, 12, 19),
        ...     volatility=0.25,
        ...     num_options=10,
        ...     option_multiplier=100,
        ...     currency="USD",
        ...     strategy_wallet="trader1",
        ...     market_wallet="market_maker"
        ... )
    """
    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_DELTA_HEDGE_STRATEGY,
        min_balance=-100.0,
        max_balance=100.0,
        decimal_places=4,
        _frozen_state=_freeze_state({
            'underlying': underlying,
            'strike': strike,
            'maturity': maturity,
            'volatility': volatility,
            'risk_free_rate': risk_free_rate,
            'num_options': num_options,
            'option_multiplier': option_multiplier,
            'currency': currency,
            'strategy_wallet': strategy_wallet,
            'market_wallet': market_wallet,
            'current_shares': Decimal("0.0"),
            'cumulative_cash': Decimal("0.0"),
            'rebalance_count': 0,
            'liquidated': False,
        })
    )


def _time_to_maturity_days(maturity: datetime, current_time: datetime) -> float:
    """
    Calculate time to maturity in trading days.

    Converts the time difference between maturity and current time into trading days
    using the standard 252 trading days per 365 calendar days convention.

    Args:
        maturity: Option expiration datetime
        current_time: Current evaluation datetime

    Returns:
        float: Time to maturity in trading days. Returns 0.0 if maturity has passed.
    """
    delta = maturity - current_time
    days = delta.total_seconds() / (24 * 3600)
    trading_days = days * (252.0 / 365.0)
    return max(0.0, trading_days)


def _compute_delta(spot: Decimal, strike: Decimal, t_in_days: float, volatility: Decimal) -> Decimal:
    """
    Compute Black-Scholes delta for a call option.

    Delta measures the rate of change of option price with respect to changes in the
    underlying asset price. For call options, delta ranges from 0 to 1.

    Args:
        spot: Current price of the underlying asset
        strike: Option strike price
        t_in_days: Time to maturity in trading days
        volatility: Annualized volatility

    Returns:
        Decimal: Call option delta. Returns 1.0 if expired in-the-money, 0.0 if expired
                 out-of-the-money, or the Black-Scholes delta if time remains.
    """
    if t_in_days <= 0:
        return Decimal("1.0") if spot > strike else Decimal("0.0")
    # Convert Decimal to float for Black-Scholes computation, then back to Decimal
    delta_float = bs_call_delta(float(spot), float(strike), t_in_days, float(volatility))
    return Decimal(str(delta_float))


def compute_rebalance(
    view: LedgerView,
    strategy_symbol: str,
    spot_price: Decimal,
    min_trade_size: Decimal = Decimal("0.0001"),
) -> PendingTransaction:
    """
    Compute the rebalancing trades needed to maintain delta neutrality.

    This function calculates the target hedge position based on the current Black-Scholes
    delta and generates the necessary buy or sell orders to achieve that position.
    The function is pure and stateless - it only reads from the LedgerView and returns
    new moves and state updates.

    Args:
        view: Read-only snapshot of the current ledger state
        strategy_symbol: Symbol of the delta hedge strategy unit
        spot_price: Current market price of the underlying asset
        min_trade_size: Minimum number of shares required to trigger a trade (default 0.0001)

    Returns:
        PendingTransaction: Contains moves for buying/selling shares and corresponding cash
                       transfers, plus updated strategy state with new share count,
                       cumulative cash, and incremented rebalance count.
                       Returns empty PendingTransaction if no rebalance is needed, the option
                       has expired, or the strategy is already liquidated.

    Raises:
        ValueError: If spot_price is not positive and finite

    Notes:
        - Buying shares: Transfers shares from market to strategy wallet, cash in reverse
        - Selling shares: Transfers shares from strategy to market wallet, receives cash
        - All trades are atomic with matching contract IDs for audit trail
        - State updates preserve all existing strategy parameters
    """
    # Ensure parameters are Decimal
    spot_price = Decimal(str(spot_price)) if not isinstance(spot_price, Decimal) else spot_price
    min_trade_size = Decimal(str(min_trade_size)) if not isinstance(min_trade_size, Decimal) else min_trade_size

    if not (spot_price > 0 and math.isfinite(float(spot_price))):
        raise ValueError(f"spot_price must be positive and finite, got {spot_price}")

    state = view.get_unit_state(strategy_symbol)

    if state.get('liquidated'):
        return empty_pending_transaction(view)

    # Ensure state values are Decimal
    current_shares_raw = state.get('current_shares', Decimal("0.0"))
    current_shares = Decimal(str(current_shares_raw)) if not isinstance(current_shares_raw, Decimal) else current_shares_raw
    cumulative_cash_raw = state.get('cumulative_cash', Decimal("0.0"))
    cumulative_cash = Decimal(str(cumulative_cash_raw)) if not isinstance(cumulative_cash_raw, Decimal) else cumulative_cash_raw
    rebalance_count = state.get('rebalance_count', 0)

    t_in_days = _time_to_maturity_days(state['maturity'], view.current_time)

    if t_in_days <= 0:
        return empty_pending_transaction(view)

    # Ensure state values are Decimal for arithmetic
    strike = Decimal(str(state['strike'])) if not isinstance(state['strike'], Decimal) else state['strike']
    volatility = Decimal(str(state['volatility'])) if not isinstance(state['volatility'], Decimal) else state['volatility']
    num_options = Decimal(str(state['num_options'])) if not isinstance(state['num_options'], Decimal) else state['num_options']
    option_multiplier = Decimal(str(state['option_multiplier']))

    delta = _compute_delta(spot_price, strike, t_in_days, volatility)
    target_shares = delta * num_options * option_multiplier
    shares_to_trade = target_shares - current_shares

    if abs(shares_to_trade) < min_trade_size:
        return empty_pending_transaction(view)

    ts = view.current_time
    strategy_wallet = state['strategy_wallet']
    market_wallet = state['market_wallet']
    underlying = state['underlying']
    currency = state['currency']

    if shares_to_trade > 0:
        cash_amount = shares_to_trade * spot_price
        moves = [
            Move(quantity=shares_to_trade, unit_symbol=underlying, source=market_wallet, dest=strategy_wallet,
                 contract_id=f"hedge_{strategy_symbol}_{ts.isoformat()}_buy"),
            Move(quantity=cash_amount, unit_symbol=currency, source=strategy_wallet, dest=market_wallet,
                 contract_id=f"hedge_{strategy_symbol}_{ts.isoformat()}_pay"),
        ]
        new_shares = current_shares + shares_to_trade
        new_cash = cumulative_cash - cash_amount
    else:
        sell_qty = -shares_to_trade
        cash_amount = sell_qty * spot_price
        moves = [
            Move(quantity=sell_qty, unit_symbol=underlying, source=strategy_wallet, dest=market_wallet,
                 contract_id=f"hedge_{strategy_symbol}_{ts.isoformat()}_sell"),
            Move(quantity=cash_amount, unit_symbol=currency, source=market_wallet, dest=strategy_wallet,
                 contract_id=f"hedge_{strategy_symbol}_{ts.isoformat()}_recv"),
        ]
        new_shares = current_shares - sell_qty
        new_cash = cumulative_cash + cash_amount

    new_state = {
        **state,
        'current_shares': new_shares,
        'cumulative_cash': new_cash,
        'rebalance_count': rebalance_count + 1,
    }
    state_changes = [UnitStateChange(unit=strategy_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


def compute_liquidation(
    view: LedgerView,
    strategy_symbol: str,
    spot_price: Decimal,
) -> PendingTransaction:
    """
    Compute trades to liquidate all remaining hedge positions at maturity.

    This function closes out the delta hedge by selling all held shares and
    marking the strategy as liquidated. Typically called when the option
    reaches maturity or when explicitly terminating the strategy.

    Args:
        view: Read-only snapshot of the current ledger state
        strategy_symbol: Symbol of the delta hedge strategy unit
        spot_price: Current market price of the underlying asset

    Returns:
        PendingTransaction: Contains moves to sell all shares to market wallet and receive cash,
                       plus updated state with zero shares, final cumulative cash total,
                       and liquidated flag set to True.
                       Returns state-only update if no shares to liquidate.
                       Returns empty PendingTransaction if already liquidated.

    Raises:
        ValueError: If spot_price is not positive and finite

    Notes:
        - Liquidation is irreversible - once set, the strategy cannot be rebalanced
        - All remaining shares are sold in a single transaction
        - Cash proceeds are added to cumulative_cash for final P&L calculation
    """
    # Ensure spot_price is Decimal
    spot_price = Decimal(str(spot_price)) if not isinstance(spot_price, Decimal) else spot_price

    if not (spot_price > 0 and math.isfinite(float(spot_price))):
        raise ValueError(f"spot_price must be positive and finite, got {spot_price}")

    state = view.get_unit_state(strategy_symbol)

    if state.get('liquidated'):
        return empty_pending_transaction(view)

    # Ensure state values are Decimal
    current_shares_raw = state.get('current_shares', Decimal("0.0"))
    current_shares = Decimal(str(current_shares_raw)) if not isinstance(current_shares_raw, Decimal) else current_shares_raw
    cumulative_cash_raw = state.get('cumulative_cash', Decimal("0.0"))
    cumulative_cash = Decimal(str(cumulative_cash_raw)) if not isinstance(cumulative_cash_raw, Decimal) else cumulative_cash_raw
    rebalance_count = state.get('rebalance_count', 0)

    if current_shares <= 0:
        new_state = {**state, 'current_shares': Decimal("0.0"), 'liquidated': True}
        state_changes = [UnitStateChange(unit=strategy_symbol, old_state=state, new_state=new_state)]
        return build_transaction(view, [], state_changes)

    ts = view.current_time
    cash_amount = current_shares * spot_price

    moves = [
        Move(quantity=current_shares, unit_symbol=state['underlying'], source=state['strategy_wallet'], dest=state['market_wallet'],
             contract_id=f"hedge_{strategy_symbol}_{ts.isoformat()}_liquidate"),
        Move(quantity=cash_amount, unit_symbol=state['currency'], source=state['market_wallet'], dest=state['strategy_wallet'],
             contract_id=f"hedge_{strategy_symbol}_{ts.isoformat()}_liquidate_recv"),
    ]

    new_state = {
        **state,
        'current_shares': Decimal("0.0"),
        'cumulative_cash': cumulative_cash + cash_amount,
        'rebalance_count': rebalance_count + 1,
        'liquidated': True,
    }
    state_changes = [UnitStateChange(unit=strategy_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


def get_hedge_state(
    view: LedgerView,
    strategy_symbol: str,
    spot_price: Decimal,
) -> Dict[str, Any]:
    """
    Get comprehensive snapshot of the delta hedge strategy state.

    Computes and returns all relevant metrics for monitoring and analyzing the hedge,
    including position details, option valuation, and profit/loss tracking.

    Args:
        view: Read-only snapshot of the current ledger state
        strategy_symbol: Symbol of the delta hedge strategy unit
        spot_price: Current market price of the underlying asset

    Returns:
        Dict[str, Any]: Dictionary containing:
            - spot_price: Input spot price
            - time_to_maturity_days: Trading days remaining until maturity
            - delta: Current Black-Scholes delta of the option
            - target_shares: Theoretical hedge position based on delta
            - current_shares: Actual shares currently held
            - shares_to_trade: Difference between target and current (for next rebalance)
            - option_value: Current theoretical value of the option position
            - shares_value: Market value of shares held
            - cumulative_cash: Net cash flow from all hedge trades
            - hedge_pnl: Current hedge P&L (shares_value + cumulative_cash)
            - rebalance_count: Total number of rebalances executed
            - liquidated: Whether strategy has been closed out

    Raises:
        ValueError: If spot_price is not positive and finite

    Notes:
        - Option value uses Black-Scholes pricing before maturity
        - At maturity, option value equals intrinsic value max(0, spot - strike)
        - hedge_pnl represents the cost of maintaining the delta hedge
    """
    # Ensure spot_price is Decimal
    spot_price = Decimal(str(spot_price)) if not isinstance(spot_price, Decimal) else spot_price

    if not (spot_price > 0 and math.isfinite(float(spot_price))):
        raise ValueError(f"spot_price must be positive and finite, got {spot_price}")

    state = view.get_unit_state(strategy_symbol)

    # Ensure state values are Decimal
    current_shares_raw = state.get('current_shares', Decimal("0.0"))
    current_shares = Decimal(str(current_shares_raw)) if not isinstance(current_shares_raw, Decimal) else current_shares_raw
    cumulative_cash_raw = state.get('cumulative_cash', Decimal("0.0"))
    cumulative_cash = Decimal(str(cumulative_cash_raw)) if not isinstance(cumulative_cash_raw, Decimal) else cumulative_cash_raw

    # Ensure state values are Decimal for arithmetic
    strike = Decimal(str(state['strike'])) if not isinstance(state['strike'], Decimal) else state['strike']
    volatility = Decimal(str(state['volatility'])) if not isinstance(state['volatility'], Decimal) else state['volatility']
    num_options = Decimal(str(state['num_options'])) if not isinstance(state['num_options'], Decimal) else state['num_options']
    option_multiplier = Decimal(str(state['option_multiplier']))

    t_in_days = _time_to_maturity_days(state['maturity'], view.current_time)
    delta = _compute_delta(spot_price, strike, t_in_days, volatility)
    target_shares = delta * num_options * option_multiplier

    if t_in_days <= 0:
        option_value = max(Decimal("0"), spot_price - strike) * num_options * option_multiplier
    else:
        # Convert to float for Black-Scholes, then back to Decimal
        bs_price = bs_call_price(float(spot_price), float(strike), t_in_days, float(volatility))
        option_value = Decimal(str(bs_price)) * num_options * option_multiplier

    shares_value = current_shares * spot_price
    hedge_pnl = shares_value + cumulative_cash

    return {
        'spot_price': spot_price,
        'time_to_maturity_days': t_in_days,
        'delta': delta,
        'target_shares': target_shares,
        'current_shares': current_shares,
        'shares_to_trade': target_shares - current_shares,
        'option_value': option_value,
        'shares_value': shares_value,
        'cumulative_cash': cumulative_cash,
        'hedge_pnl': hedge_pnl,
        'rebalance_count': state.get('rebalance_count', 0),
        'liquidated': state.get('liquidated', False),
    }


def compute_hedge_pnl_breakdown(
    view: LedgerView,
    strategy_symbol: str,
    final_spot: Decimal,
) -> Dict[str, Decimal]:
    """
    Compute detailed profit and loss breakdown for the delta hedge strategy.

    This function provides a comprehensive analysis of the hedge performance by comparing
    the option payoff against the cost of maintaining the hedge. Typically used at maturity
    to evaluate how well the hedge replicated the option value.

    Args:
        view: Read-only snapshot of the current ledger state
        strategy_symbol: Symbol of the delta hedge strategy unit
        final_spot: Final price of the underlying asset for P&L calculation

    Returns:
        Dict[str, Decimal]: Dictionary containing:
            - final_spot: Input final spot price
            - option_payoff: Intrinsic value of option at final spot
            - shares_held: Number of shares in hedge position
            - shares_value: Market value of shares at final spot
            - cumulative_cash: Total net cash from all trades
            - hedge_pnl: Total P&L from hedge (shares_value + cumulative_cash)
            - net_pnl: Difference between option payoff and hedge cost (ideally near zero)
            - rebalance_count: Number of rebalances executed

    Raises:
        ValueError: If final_spot is not positive and finite

    Notes:
        - net_pnl measures hedge effectiveness: closer to zero means better replication
        - Negative net_pnl: hedge cost more than option value (tracking error)
        - Positive net_pnl: hedge cost less than option value (unlikely with frequent rebalancing)
        - option_payoff = max(0, final_spot - strike) * num_options * multiplier
    """
    # Ensure final_spot is Decimal
    final_spot = Decimal(str(final_spot)) if not isinstance(final_spot, Decimal) else final_spot

    if not (final_spot > 0 and math.isfinite(float(final_spot))):
        raise ValueError(f"final_spot must be positive and finite, got {final_spot}")

    state = view.get_unit_state(strategy_symbol)

    # Ensure state values are Decimal
    current_shares_raw = state.get('current_shares', Decimal("0.0"))
    current_shares = Decimal(str(current_shares_raw)) if not isinstance(current_shares_raw, Decimal) else current_shares_raw
    cumulative_cash_raw = state.get('cumulative_cash', Decimal("0.0"))
    cumulative_cash = Decimal(str(cumulative_cash_raw)) if not isinstance(cumulative_cash_raw, Decimal) else cumulative_cash_raw

    # Ensure state values are Decimal for arithmetic
    strike = Decimal(str(state['strike'])) if not isinstance(state['strike'], Decimal) else state['strike']
    num_options = Decimal(str(state['num_options'])) if not isinstance(state['num_options'], Decimal) else state['num_options']
    option_multiplier = Decimal(str(state['option_multiplier']))

    intrinsic = max(Decimal("0"), final_spot - strike)
    option_payoff = intrinsic * num_options * option_multiplier
    shares_value = current_shares * final_spot
    hedge_pnl = shares_value + cumulative_cash
    net_pnl = option_payoff - hedge_pnl

    return {
        'final_spot': final_spot,
        'option_payoff': option_payoff,
        'shares_held': current_shares,
        'shares_value': shares_value,
        'cumulative_cash': cumulative_cash,
        'hedge_pnl': hedge_pnl,
        'net_pnl': net_pnl,
        'rebalance_count': state.get('rebalance_count', 0),
    }


def delta_hedge_contract(min_trade_size: Decimal = Decimal("0.01")):
    """
    Factory function that returns a smart contract for automated delta hedging.

    Creates a lifecycle management function that can be registered with the ledger's
    smart contract system. The returned function automatically handles rebalancing
    and liquidation based on current market prices and time.

    Args:
        min_trade_size: Minimum share quantity to trigger rebalancing trades (default 0.01)

    Returns:
        Callable: A smart contract function with signature:
                 (view: LedgerView, symbol: str, timestamp: datetime, prices: Dict[str, Decimal])
                 -> PendingTransaction

    Smart Contract Behavior:
        - Checks if strategy is already liquidated (returns empty if so)
        - Retrieves current price for the underlying asset from prices dict
        - At or after maturity: triggers liquidation of all positions
        - Before maturity: triggers rebalancing if needed based on delta
        - Returns empty PendingTransaction if no action needed or price unavailable

    Example:
        >>> contract_fn = delta_hedge_contract(min_trade_size=0.01)
        >>> ledger.register_contract(
        ...     symbol="AAPL_HEDGE_150_DEC25",
        ...     contract=contract_fn
        ... )

    Notes:
        - The contract is pure and stateless - all state changes go through PendingTransaction
        - Requires price data for the underlying asset to be provided in prices dict
        - Safe to call repeatedly - idempotent when no changes are needed
    """
    def check_lifecycle(
        view: LedgerView,
        symbol: str,
        timestamp: datetime,
        prices: Dict[str, Decimal]
    ) -> PendingTransaction:
        state = view.get_unit_state(symbol)

        if state.get('liquidated'):
            return empty_pending_transaction(view)

        underlying = state.get('underlying')
        if not underlying:
            raise ValueError(f"Delta hedge {symbol} has no underlying defined")
        if underlying not in prices:
            raise ValueError(f"Missing price for delta hedge underlying '{underlying}' in {symbol}")
        spot_price = prices[underlying]

        maturity = state.get('maturity')
        if maturity and timestamp >= maturity:
            return compute_liquidation(view, symbol, spot_price)

        return compute_rebalance(view, symbol, spot_price, min_trade_size)

    return check_lifecycle
