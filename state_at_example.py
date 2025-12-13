"""
state_at_example.py - State Reconstruction with clone_at()

Demonstrates the clone_at() function for time travel and state reconstruction:
1. Creates 3 delta hedging strategies with different strikes
2. Runs them for 10 weeks using the LifecycleEngine
3. Takes a snapshot (clone) at the end of each week
4. Verifies that clone_at() reconstructs each snapshot exactly

The clone_at() function returns a full Ledger at any past time, which can
then be used to execute new transactions for divergent scenario analysis.

Run this file directly:
    python state_at_example.py
"""

from datetime import datetime, timedelta
from typing import List, Tuple, Dict
import math
import random

from ledger import (
    # Core
    Ledger, Move, cash, build_transaction, SYSTEM_WALLET,

    # Stock module
    create_stock_unit,

    # Delta hedge strategy
    create_delta_hedge_unit,
    delta_hedge_contract,

    # Engine
    LifecycleEngine,

    # Pricing sources
    TimeSeriesPricingSource,
)


def stock(symbol: str, name: str, issuer: str, shortable: bool = False):
    """Helper to create a simple stock unit."""
    return create_stock_unit(symbol, name, issuer, "USD", shortable=shortable)


def summarize_hedge(ledger: Ledger, strategy_symbol: str) -> dict:
    """Get summary information about a delta hedge strategy."""
    state = ledger.get_unit_state(strategy_symbol)
    return {
        'rebalance_count': state.get('rebalance_count', 0),
        'cumulative_cash': state.get('cumulative_cash', 0.0),
        'liquidated': state.get('liquidated', False),
    }


class DeltaHedgeContract:
    """Wrapper for delta_hedge_contract to provide class-based interface."""
    def __init__(self, min_trade_size: float = 0.01):
        self._contract = delta_hedge_contract(min_trade_size=min_trade_size)

    def check_lifecycle(self, view, symbol, timestamp, prices):
        return self._contract(view, symbol, timestamp, prices)


def generate_gbm_path(
    start_price: float,
    start_date: datetime,
    num_days: int,
    volatility: float,
    drift: float = 0.0,
    seed: int = 42
) -> List[Tuple[datetime, float]]:
    """Generate a Geometric Brownian Motion price path."""
    random.seed(seed)

    dt = 1.0 / 252.0
    path = [(start_date, start_price)]

    price = start_price
    for day in range(1, num_days):
        z = random.gauss(0, 1)
        exponent = (drift - 0.5 * volatility ** 2) * dt + volatility * math.sqrt(dt) * z
        price = price * math.exp(exponent)
        date = start_date + timedelta(days=day)
        path.append((date, price))

    return path


def compare_ledgers(ledger1: Ledger, ledger2: Ledger, tolerance: float = 1e-6) -> Tuple[bool, List[str]]:
    """
    Compare two ledgers for equality within numeric tolerance.

    Returns:
        Tuple of (is_equal, list_of_differences)
    """
    differences = []

    # Compare balances
    all_wallets = ledger1.registered_wallets | ledger2.registered_wallets
    all_units = set(ledger1.units.keys()) | set(ledger2.units.keys())

    for wallet in all_wallets:
        for unit in all_units:
            val1 = ledger1.balances.get(wallet, {}).get(unit, 0.0)
            val2 = ledger2.balances.get(wallet, {}).get(unit, 0.0)
            if abs(val1 - val2) > tolerance:
                differences.append(f"Balance ({wallet}, {unit}): {val1} vs {val2} (diff={val1-val2})")

    # Compare unit states
    for unit_symbol in all_units:
        state1 = ledger1.get_unit_state(unit_symbol) if unit_symbol in ledger1.units else {}
        state2 = ledger2.get_unit_state(unit_symbol) if unit_symbol in ledger2.units else {}

        # Compare numeric fields with tolerance, others with equality
        all_fields = set(state1.keys()) | set(state2.keys())
        for field in all_fields:
            v1 = state1.get(field)
            v2 = state2.get(field)

            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                if abs(v1 - v2) > tolerance:
                    differences.append(f"State {unit_symbol}.{field}: {v1} vs {v2} (diff={v1-v2})")
            elif v1 != v2:
                differences.append(f"State {unit_symbol}.{field}: {v1} vs {v2}")

    return len(differences) == 0, differences


def main():
    print("=" * 70)
    print("CLONE_AT RECONSTRUCTION EXAMPLE")
    print("=" * 70)
    print("""
This example demonstrates the clone_at() function:
1. Running 3 delta hedge strategies for 10 weeks
2. Taking snapshots (clones) at the end of each week
3. Verifying that clone_at() reconstructs each snapshot exactly

clone_at() returns a full Ledger at any past time,
enabling divergent scenario analysis from historical states.
    """)

    # =========================================================================
    # SETUP
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 1: SETUP")
    print("=" * 70)

    start_date = datetime(2025, 1, 6, 9, 30)  # Monday
    maturity_date = datetime(2025, 6, 30, 16, 0)  # Far enough for 10 weeks
    num_weeks = 10

    # Create ledger with logging enabled (required for clone_at)
    ledger = Ledger(
        name="state_at_demo",
        initial_time=start_date,
        verbose=False,
    )

    # Register assets with explicit decimal places for rounding
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="treasury", shortable=True))

    # Register wallets
    strategy1 = ledger.register_wallet("strategy_atm")
    strategy2 = ledger.register_wallet("strategy_itm")
    strategy3 = ledger.register_wallet("strategy_otm")
    market = ledger.register_wallet("market")
    ledger.register_wallet("treasury")

    # Fund wallets via SYSTEM_WALLET (proper issuance)
    # SYSTEM_WALLET is auto-registered by the ledger

    funding_tx = build_transaction(ledger, [
        Move(50_000_000.0, "USD", SYSTEM_WALLET, market, "initial_fund_market_usd"),
        Move(500_000.0, "AAPL", SYSTEM_WALLET, market, "initial_fund_market_aapl"),
        Move(500_000.0, "USD", SYSTEM_WALLET, strategy1, "initial_fund_s1_usd"),
        Move(500_000.0, "USD", SYSTEM_WALLET, strategy2, "initial_fund_s2_usd"),
        Move(500_000.0, "USD", SYSTEM_WALLET, strategy3, "initial_fund_s3_usd"),
    ])
    ledger.execute(funding_tx)

    print(f"Start date: {start_date}")
    print(f"Maturity:   {maturity_date}")
    print(f"Duration:   {num_weeks} weeks")

    # =========================================================================
    # CREATE 3 DELTA HEDGE STRATEGIES
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 2: CREATE 3 DELTA HEDGE STRATEGIES")
    print("=" * 70)

    spot_price = 150.0
    volatility = 0.25
    num_options = 10
    multiplier = 100

    strategies = [
        ("HEDGE_ATM", "ATM Hedge", strategy1, 150.0),  # At-the-money
        ("HEDGE_ITM", "ITM Hedge", strategy2, 140.0),  # In-the-money
        ("HEDGE_OTM", "OTM Hedge", strategy3, 160.0),  # Out-of-the-money
    ]

    for symbol, name, wallet, strike in strategies:
        unit = create_delta_hedge_unit(
            symbol=symbol,
            name=name,
            underlying="AAPL",
            strike=strike,
            maturity=maturity_date,
            volatility=volatility,
            num_options=num_options,
            option_multiplier=multiplier,
            currency="USD",
            strategy_wallet=wallet,
            market_wallet=market,
            risk_free_rate=0.0,
        )
        ledger.register_unit(unit)
        print(f"  Created {symbol}: strike=${strike}, wallet={wallet}")

    # =========================================================================
    # GENERATE PRICE PATH
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 3: GENERATE PRICE PATH")
    print("=" * 70)

    # 10 weeks = 70 calendar days
    num_days = num_weeks * 7

    aapl_path = generate_gbm_path(
        start_price=spot_price,
        start_date=start_date,
        num_days=num_days,
        volatility=volatility,
        drift=0.0,
        seed=42
    )

    pricing_source = TimeSeriesPricingSource(
        price_paths={'AAPL': aapl_path},
        base_currency='USD'
    )

    prices = [p for _, p in aapl_path]
    print(f"Generated {num_days} days of prices")
    print(f"  Start: ${prices[0]:.2f}")
    print(f"  End:   ${prices[-1]:.2f}")
    print(f"  Min:   ${min(prices):.2f}")
    print(f"  Max:   ${max(prices):.2f}")

    # =========================================================================
    # RUN WITH WEEKLY CLONES
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 4: RUN ENGINE WITH WEEKLY CLONES")
    print("=" * 70)

    # Setup engine
    engine = LifecycleEngine(ledger)
    engine.register("DELTA_HEDGE_STRATEGY", DeltaHedgeContract(min_trade_size=0.01))

    # Get all timestamps
    all_timestamps = pricing_source.get_all_timestamps()

    # Store clones at end of each week
    weekly_clones: Dict[int, Ledger] = {}
    clone_times: Dict[int, datetime] = {}

    def price_fn(t: datetime) -> Dict[str, float]:
        price = pricing_source.get_price("AAPL", t)
        return {"AAPL": price} if price else {}

    total_transactions = 0

    for week in range(num_weeks):
        week_start = week * 7
        week_end = min((week + 1) * 7, len(all_timestamps))
        week_timestamps = all_timestamps[week_start:week_end]

        if not week_timestamps:
            break

        # Run engine for this week
        txs = engine.run(week_timestamps, price_fn)
        total_transactions += len(txs)

        # Take clone at end of week
        clone_time = week_timestamps[-1]
        weekly_clones[week] = ledger.clone()
        clone_times[week] = clone_time

        # Get current state for display
        price = pricing_source.get_price("AAPL", clone_time)
        print(f"Week {week+1:2d}: {clone_time.date()}, AAPL=${price:.2f}, "
              f"txs={len(txs):3d}, total_txs={total_transactions}")

    print(f"\nTotal transactions: {total_transactions}")
    print(f"Clones taken: {len(weekly_clones)}")

    # =========================================================================
    # VERIFY CLONE_AT MATCHES CLONES
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 5: VERIFY CLONE_AT MATCHES CLONES")
    print("=" * 70)

    all_match = True

    for week in range(num_weeks):
        if week not in weekly_clones:
            continue

        target_time = clone_times[week]
        expected_clone = weekly_clones[week]

        # Reconstruct ledger at that time
        reconstructed = ledger.clone_at(target_time)

        # Compare
        is_equal, differences = compare_ledgers(expected_clone, reconstructed)

        if is_equal:
            print(f"Week {week+1:2d}: MATCH")
        else:
            print(f"Week {week+1:2d}: MISMATCH - {len(differences)} differences")
            for diff in differences[:5]:  # Show first 5
                print(f"    {diff}")
            all_match = False

    # =========================================================================
    # DETAILED COMPARISON FOR ONE WEEK
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 6: DETAILED COMPARISON (Week 5)")
    print("=" * 70)

    week = 4  # Week 5 (0-indexed)
    if week in weekly_clones:
        target_time = clone_times[week]
        expected = weekly_clones[week]
        reconstructed = ledger.clone_at(target_time)

        print(f"Target time: {target_time}")
        print(f"\nBalances comparison:")

        # Build balance dicts for comparison
        all_wallets = sorted(expected.registered_wallets)
        all_units = sorted(expected.units.keys())

        print(f"{'Wallet':<20} {'Unit':<15} {'Expected':>15} {'Reconstructed':>15} {'Diff':>12}")
        print("-" * 80)

        for wallet in all_wallets:
            for unit in all_units:
                exp_val = expected.get_balance(wallet, unit)
                rec_val = reconstructed.get_balance(wallet, unit)
                diff = exp_val - rec_val

                if exp_val != 0 or rec_val != 0:
                    diff_str = f"{diff:.6f}" if abs(diff) > 1e-10 else "0"
                    print(f"{wallet:<20} {unit:<15} {exp_val:>15.2f} {rec_val:>15.2f} {diff_str:>12}")

        # Check strategy states
        print(f"\nStrategy states comparison:")
        for symbol in ["HEDGE_ATM", "HEDGE_ITM", "HEDGE_OTM"]:
            exp_state = expected.get_unit_state(symbol)
            rec_state = reconstructed.get_unit_state(symbol)

            if exp_state and rec_state:
                exp_cash = exp_state.get('cumulative_cash', 0)
                rec_cash = rec_state.get('cumulative_cash', 0)
                exp_count = exp_state.get('rebalance_count', 0)
                rec_count = rec_state.get('rebalance_count', 0)

                print(f"  {symbol}:")
                print(f"    cumulative_cash: expected={exp_cash:.2f}, reconstructed={rec_cash:.2f}")
                print(f"    rebalance_count: expected={exp_count}, reconstructed={rec_count}")

    # =========================================================================
    # DEMONSTRATE DIVERGENT SCENARIOS
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 7: DEMONSTRATE DIVERGENT SCENARIOS")
    print("=" * 70)

    # clone_at returns a full Ledger that can execute new transactions
    week5_ledger = ledger.clone_at(clone_times[4])
    print(f"Created clone at week 5: {clone_times[4]}")
    print(f"  Clone has {len(week5_ledger.transaction_log)} transactions")
    print(f"  Original has {len(ledger.transaction_log)} transactions")

    # Execute a new transaction on the clone (divergent timeline)
    week5_ledger.advance_time(clone_times[4] + timedelta(hours=1))
    test_move = Move(1000.0, "USD", "strategy_atm", "market", "test_move")
    tx = build_transaction(week5_ledger, [test_move])
    week5_ledger.execute(tx)

    print(f"\nExecuted test transaction on week 5 clone")
    print(f"  Clone now has {len(week5_ledger.transaction_log)} transactions")
    print(f"  Original still has {len(ledger.transaction_log)} transactions")

    # Verify original is unchanged
    original_balance = ledger.get_balance("strategy_atm", "USD")
    clone_balance = week5_ledger.get_balance("strategy_atm", "USD")
    print(f"\n  Original strategy_atm USD: ${original_balance:,.2f}")
    print(f"  Clone strategy_atm USD:    ${clone_balance:,.2f}")
    print(f"  Difference: ${original_balance - clone_balance:,.2f} (the test transfer)")

    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if all_match:
        print("SUCCESS: All weekly clones match clone_at() reconstruction")
    else:
        print("FAILURE: Some clones did not match")

    print(f"\nFinal strategy states:")
    for symbol, name, wallet, strike in strategies:
        summary = summarize_hedge(ledger, symbol)
        shares = ledger.get_balance(wallet, "AAPL")
        usd = ledger.get_balance(wallet, "USD")
        print(f"  {symbol}: rebalances={summary['rebalance_count']}, "
              f"shares={shares:.1f}, USD=${usd:,.2f}")

    print(f"\nTransaction log size: {len(ledger.transaction_log)}")

    return all_match


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
