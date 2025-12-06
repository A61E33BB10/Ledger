"""
delta_hedge_example.py - Step-by-Step Delta Hedging Example

Demonstrates the complete lifecycle of a delta hedging strategy:
1. Setup: Create ledger, register assets, fund wallets
2. Strategy Creation: Define terms and register the strategy unit
3. Price Path Generation: Generate GBM path with TimeSeriesPricingSource
4. Daily Rebalancing: Compute and execute daily delta rebalancing
5. Liquidation: Close out all positions at maturity
6. Analysis: Compute P&L breakdown

This example shows both manual rebalancing (using compute_rebalance)
and automatic rebalancing (using LifecycleEngine).

Run this file directly:
    python delta_hedge_example.py
"""

from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any
import math
import random
import time

from ledger import (
    # Core
    Ledger, Move, cash,

    # Stock module
    create_stock_unit,

    # Delta hedge strategy
    create_delta_hedge_unit,
    compute_rebalance,
    compute_liquidation,
    get_hedge_state,
    compute_hedge_pnl_breakdown,
    delta_hedge_contract,

    # Engine
    LifecycleEngine,

    # Pricing sources
    TimeSeriesPricingSource,

    # Black-Scholes (t_in_days convention)
    call as bs_call,
    call_delta as bs_delta,
)


def stock(symbol: str, name: str, issuer: str, shortable: bool = False):
    """Helper to create a simple stock unit."""
    return create_stock_unit(symbol, name, issuer, "USD", shortable=shortable)


def timing(func):
    """Simple timing decorator."""
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[{func.__name__}] completed in {elapsed:.2f}s")
        return result
    return wrapper


def summarize_hedge(ledger: Ledger, strategy_symbol: str) -> Dict[str, Any]:
    """Get summary information about a delta hedge strategy."""
    state = ledger.get_unit_state(strategy_symbol)
    return {
        'rebalance_count': state.get('rebalance_count', 0),
        'cumulative_cash': state.get('cumulative_cash', 0.0),
        'liquidated': state.get('liquidated', False),
    }


def generate_gbm_path(
    start_price: float,
    start_date: datetime,
    num_days: int,
    volatility: float,
    drift: float = 0.0,
    seed: int = 42
) -> List[Tuple[datetime, float]]:
    """
    Generate a Geometric Brownian Motion price path.

    Uses the discrete GBM formula:
        S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)

    where Z ~ N(0,1)

    Args:
        start_price: Initial price S(0)
        start_date: Start datetime
        num_days: Number of days to simulate
        volatility: Annualized volatility (e.g., 0.25 for 25%)
        drift: Annualized drift (default 0 for risk-neutral)
        seed: Random seed for reproducibility

    Returns:
        List of (datetime, price) tuples for TimeSeriesPricingSource
    """
    random.seed(seed)

    dt = 1.0 / 252.0  # Daily time step (trading days per year)
    path = [(start_date, start_price)]

    price = start_price
    for day in range(1, num_days):
        # Standard normal random variable
        z = random.gauss(0, 1)

        # GBM step: S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
        exponent = (drift - 0.5 * volatility ** 2) * dt + volatility * math.sqrt(dt) * z
        price = price * math.exp(exponent)

        date = start_date + timedelta(days=day)
        path.append((date, price))

    return path


def main():
    print("=" * 70)
    print("DELTA HEDGING STRATEGY - COMPLETE EXAMPLE")
    print("=" * 70)

    # =========================================================================
    # STEP 1: SETUP
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 1: SETUP")
    print("=" * 70)

    start_date = datetime(2024, 4, 1, 9, 30)
    maturity_date = datetime(2025, 4, 1, 16, 0)  # 90 days

    ledger = Ledger(
        name="delta_hedge_demo",
        initial_time=start_date,
        verbose=True,
        fast_mode=False,
        no_log=False,
    )

    # Register assets
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL", shortable=True))

    # Register wallets
    strategy = ledger.register_wallet("strategy")
    market = ledger.register_wallet("market")

    # Fund wallets
    ledger.balances[market]["USD"] = 10_000_000
    ledger.balances[market]["AAPL"] = 100_000
    ledger.balances[strategy]["USD"] = 100_000

    print(f"Strategy: ${ledger.get_balance(strategy, 'USD'):,.2f} cash")
    print(f"Market:   ${ledger.get_balance(market, 'USD'):,.2f} cash, "
          f"{ledger.get_balance(market, 'AAPL'):,} AAPL")

    # =========================================================================
    # STEP 2: CREATE STRATEGY
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 2: CREATE STRATEGY")
    print("=" * 70)

    spot_price = 150.0
    strike = 150.0
    volatility = 0.25
    num_options = 10
    multiplier = 100

    # Create and register the strategy unit
    strategy_unit = create_delta_hedge_unit(
        symbol="HEDGE_AAPL_150",
        name="AAPL Delta Hedge $150",
        underlying="AAPL",
        strike=strike,
        maturity=maturity_date,
        volatility=volatility,
        num_options=num_options,
        option_multiplier=multiplier,
        currency="USD",
        strategy_wallet=strategy,
        market_wallet=market,
        risk_free_rate=0.0,
    )
    ledger.register_unit(strategy_unit)

    # Show initial option value (t_in_days = calendar days * 252/365)
    num_days = (maturity_date - start_date).days
    t_in_days = num_days * (252.0 / 365.0)  # Convert to trading days
    initial_option_price = bs_call(spot_price, strike, t_in_days, volatility)
    initial_delta = bs_delta(spot_price, strike, t_in_days, volatility)

    print(f"Strategy: Long {num_options} calls, strike ${strike}, {num_days} calendar days ({t_in_days:.0f} trading days)")
    print(f"Initial option price: ${initial_option_price:.2f}/share")
    print(f"Initial delta: {initial_delta:.4f}")
    print(f"Total option cost: ${initial_option_price * num_options * multiplier:,.2f}")

    # =========================================================================
    # STEP 3: GENERATE PRICE PATH
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 3: GENERATE PRICE PATH (GBM via TimeSeriesPricingSource)")
    print("=" * 70)

    num_days = (maturity_date - start_date).days

    # Generate GBM path with zero drift (risk-neutral, zero-rate)
    aapl_path = generate_gbm_path(
        start_price=spot_price,
        start_date=start_date,
        num_days=num_days,
        volatility=volatility,
        drift=0.0,  # Zero-rate risk-neutral measure
        seed=123
    )

    # Create pricing source
    pricing_source = TimeSeriesPricingSource(
        price_paths={'AAPL': aapl_path},
        base_currency='USD'
    )

    # Extract prices for convenience
    prices = [price for _, price in aapl_path]
    timestamps = pricing_source.get_all_timestamps()

    print(f"Pricing source: {pricing_source}")
    print(f"Generated {num_days} days of GBM prices")
    print(f"  Start: ${prices[0]:.2f}, End: ${prices[-1]:.2f}")
    print(f"  Min: ${min(prices):.2f}, Max: ${max(prices):.2f}")
    print(f"  Drift: 0% (zero-rate), Vol: {volatility:.1%}")

    # =========================================================================
    # STEP 4: RUN DAILY REBALANCING
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 4: RUN DAILY REBALANCING")
    print("=" * 70)

    for day, date in enumerate(timestamps):
        # Get price from pricing source
        price = pricing_source.get_price("AAPL", date)

        ledger.advance_time(date)

        # Compute and execute rebalance
        result = compute_rebalance(ledger, "HEDGE_AAPL_150", price, min_trade_size=0.01)

        if not result.is_empty():
            ledger.execute_contract(result)

            # Print progress every 10 days
            if day % 10 == 0:
                state = get_hedge_state(ledger, "HEDGE_AAPL_150", price)
                print(f"Day {day:3d}: Price=${price:7.2f}, "
                      f"Delta={state['delta']:.4f}, "
                      f"Shares={state['current_shares']:8.1f}")

    # Get final state from unit
    summary = summarize_hedge(ledger, "HEDGE_AAPL_150")
    print(f"\nTotal rebalances: {summary['rebalance_count']}")

    # =========================================================================
    # STEP 5: LIQUIDATE AT MATURITY
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 5: LIQUIDATE AT MATURITY")
    print("=" * 70)

    # Get final price from pricing source (last timestamp)
    final_date = timestamps[-1]
    final_price = pricing_source.get_price("AAPL", final_date)
    ledger.advance_time(maturity_date)

    state_before = get_hedge_state(ledger, "HEDGE_AAPL_150", final_price)
    print(f"Before liquidation: {state_before['current_shares']:.1f} shares")

    # Compute and execute liquidation
    liq_result = compute_liquidation(ledger, "HEDGE_AAPL_150", final_price)
    if not liq_result.is_empty():
        ledger.execute_contract(liq_result)

    state_after = get_hedge_state(ledger, "HEDGE_AAPL_150", final_price)
    print(f"After liquidation:  {state_after['current_shares']:.1f} shares")
    print(f"Liquidated: {state_after['liquidated']}")

    # =========================================================================
    # STEP 6: P&L ANALYSIS
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 6: P&L ANALYSIS")
    print("=" * 70)

    pnl = compute_hedge_pnl_breakdown(ledger, "HEDGE_AAPL_150", final_price)

    print(f"Final Spot:       ${pnl['final_spot']:.2f}")
    print(f"Option Payoff:    ${pnl['option_payoff']:,.2f}")
    print(f"Cumulative Cash:  ${pnl['cumulative_cash']:,.2f}")
    print(f"Hedge P&L:        ${pnl['hedge_pnl']:,.2f}")
    print(f"Net P&L:          ${pnl['net_pnl']:,.2f}")
    print(f"Rebalances:       {pnl['rebalance_count']}")

    # =========================================================================
    # STEP 7: FINAL LEDGER STATE
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 7: FINAL LEDGER STATE")
    print("=" * 70)

    print(f"Strategy: ${ledger.get_balance(strategy, 'USD'):,.2f} cash, "
          f"{ledger.get_balance(strategy, 'AAPL'):.1f} AAPL")
    print(f"Market:   ${ledger.get_balance(market, 'USD'):,.2f} cash, "
          f"{ledger.get_balance(market, 'AAPL'):.1f} AAPL")

    print("\n" + "=" * 70)
    print("COMPLETE!")
    print("=" * 70)

@timing
def main_with_lifecycle_engine():
    """
    Demonstrates automatic rebalancing using LifecycleEngine.

    The LifecycleEngine handles daily rebalancing and liquidation by
    calling the delta_hedge_contract handler at each time step.
    """
    print("\n\n" + "=" * 70)
    print("BONUS: DELTA HEDGING WITH LIFECYCLE ENGINE")
    print("=" * 70)
    print("""
    This example shows how LifecycleEngine automates rebalancing.
    The engine calls check_lifecycle() at each step, which triggers
    rebalancing before maturity and liquidation at maturity.
    """)

    start_date = datetime(2024, 4, 1, 1, 30)
    maturity_date = datetime(2025, 4, 1, 16, 0)

    ledger = Ledger("engine_hedge", start_date, verbose=True, fast_mode=False, no_log=False)

    ledger.register_unit(cash("USD", "US Dollar"))
    ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL", shortable=True))

    strategy = ledger.register_wallet("strategy")
    market = ledger.register_wallet("market")

    ledger.balances[market]["USD"] = 10_000_000
    ledger.balances[market]["AAPL"] = 100_000
    ledger.balances[strategy]["USD"] = 100_000

    # Create strategy
    ledger.register_unit(create_delta_hedge_unit(
        symbol="HEDGE_AAPL",
        name="AAPL Hedge",
        underlying="AAPL",
        strike=150.0,
        maturity=maturity_date,
        volatility=0.25,
        num_options=10,
        option_multiplier=100,
        currency="USD",
        strategy_wallet=strategy,
        market_wallet=market,
        risk_free_rate=0.0,
    ))

    # Generate price path (include maturity day)
    num_days = (maturity_date - start_date).days + 1
    aapl_path = generate_gbm_path(150.0, start_date, num_days, 0.25, 0.0, seed=123)
    pricing_source = TimeSeriesPricingSource({'AAPL': aapl_path}, 'USD')
    timestamps = pricing_source.get_all_timestamps()
    # Ensure maturity is included for liquidation
    if maturity_date not in timestamps:
        timestamps.append(maturity_date)

    # Create engine with delta_hedge_contract
    engine = LifecycleEngine(ledger)
    engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract(min_trade_size=0.01))

    print("--- Running Engine ---")

    # Use engine.run() for fully automatic execution
    def price_fn(t):
        price = pricing_source.get_price("AAPL", t)
        return {"AAPL": price} if price else {}

    all_txs = engine.run(timestamps, price_fn)
    print(f"Total transactions: {len(all_txs)}")

    # Summary
    summary = summarize_hedge(ledger, "HEDGE_AAPL")
    print(f"Rebalances: {summary['rebalance_count']}")
    print(f"Liquidated: {summary['liquidated']}")
    print(f"Cumulative cash: ${summary['cumulative_cash']:,.2f}")

    final_price = pricing_source.get_price("AAPL", timestamps[-1])
    pnl = compute_hedge_pnl_breakdown(ledger, "HEDGE_AAPL", final_price)
    print(f"Net P&L: ${pnl['net_pnl']:,.2f}")


if __name__ == "__main__":
    main()
    main_with_lifecycle_engine()
