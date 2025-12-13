#!/usr/bin/env python3
"""
future_demo_lifecycle.py - Full Stack Futures Demo with LifecycleEngine

This script demonstrates the complete futures lifecycle using:
- Real Ledger infrastructure
- TimeSeriesPricingSource for historical price simulation
- LifecycleEngine for automated daily MTM processing
- Verbose mode to see all internal operations

This is the "production-like" setup showing how all components integrate.

Run with: python future_demo_lifecycle.py
"""

from datetime import datetime, timedelta
from ledger import (
    Ledger,
    Move,
    cash,
    build_transaction,
    SYSTEM_WALLET,
    create_future,
    future_transact,
    future_contract,
    LifecycleEngine,
    TimeSeriesPricingSource,
    UNIT_TYPE_FUTURE,
)


def generate_price_path(start_price: float, dates: list, volatility: float = 0.02, seed: int = 42):
    """
    Generate a simple price path for demo purposes.
    Uses a deterministic random walk for reproducibility.
    """
    import random
    random.seed(seed)

    prices = []
    price = start_price
    for date in dates:
        # Simple random walk with drift
        change = random.gauss(0.0005, volatility)  # Small positive drift
        price = price * (1 + change)
        prices.append((date, round(price, 2)))
    return prices


def main():
    print("""
================================================================================
        FUTURES LIFECYCLE ENGINE DEMO - FULL STACK INTEGRATION
================================================================================

This demo shows the complete integration of:
  - Ledger (with verbose mode ON to see all operations)
  - TimeSeriesPricingSource (simulated daily SPX prices)
  - LifecycleEngine (automated daily MTM processing)
  - future_contract (SmartContract for futures)

Scenario:
  - ESZ24: E-mini S&P 500 Dec 2024 futures
  - 20 trading days from Nov 1 to Nov 29, 2024
  - Alice goes long, Bob goes short
  - Daily automated MTM via LifecycleEngine
""")

    # =========================================================================
    # SETUP DATES AND PRICE PATH
    # =========================================================================
    print("="*70)
    print("  PHASE 1: Setting Up Price Path")
    print("="*70)

    # Generate trading days (skip weekends for realism)
    start_date = datetime(2024, 11, 1)
    trading_days = []
    current = start_date
    while len(trading_days) < 20:
        if current.weekday() < 5:  # Monday=0 to Friday=4
            trading_days.append(current)
        current += timedelta(days=1)

    print(f"\n  Trading period: {trading_days[0].date()} to {trading_days[-1].date()}")
    print(f"  Number of trading days: {len(trading_days)}")

    # Generate SPX price path
    spx_prices = generate_price_path(
        start_price=4500.0,
        dates=trading_days,
        volatility=0.015,  # ~1.5% daily vol
        seed=12345
    )

    print(f"\n  SPX Price Path:")
    print(f"    Start:  {spx_prices[0][1]:,.2f}")
    print(f"    End:    {spx_prices[-1][1]:,.2f}")
    print(f"    Change: {(spx_prices[-1][1]/spx_prices[0][1] - 1)*100:+.2f}%")

    # Create TimeSeriesPricingSource
    pricing_source = TimeSeriesPricingSource(
        price_paths={"SPX": spx_prices},
        base_currency="USD"
    )
    print(f"\n  Created: {pricing_source}")

    # =========================================================================
    # SETUP LEDGER (VERBOSE MODE)
    # =========================================================================
    print("\n" + "="*70)
    print("  PHASE 2: Creating Ledger (Verbose Mode)")
    print("="*70)

    expiry = datetime(2024, 12, 20, 16, 0, 0)

    # Create ledger with verbose=True to see all operations
    ledger = Ledger(
        name="futures_lifecycle_demo",
        initial_time=trading_days[0],
        verbose=True  # This will print all moves and state changes
    )

    print(f"\n  Ledger created: {ledger.name}")
    print(f"  Verbose mode: ON")

    # Register units
    print("\n  Registering units...")
    ledger.register_unit(cash("USD", "US Dollar"))
    ledger.register_unit(create_future(
        symbol="ESZ24",
        name="E-mini S&P 500 Dec 2024",
        underlying="SPX",
        expiry=expiry,
        multiplier=50.0,
        currency="USD",
        clearinghouse_id="CME"
    ))

    # Register wallets
    print("\n  Registering wallets...")
    for wallet in ["alice", "bob", "CME"]:
        ledger.register_wallet(wallet)

    # Fund accounts via SYSTEM_WALLET
    print("\n  Funding accounts...")
    # SYSTEM_WALLET is auto-registered by the ledger
    funding_tx = build_transaction(ledger, [
        Move(1_000_000, "USD", SYSTEM_WALLET, "alice", "fund_alice"),
        Move(1_000_000, "USD", SYSTEM_WALLET, "bob", "fund_bob"),
        Move(100_000_000, "USD", SYSTEM_WALLET, "CME", "fund_cme"),
    ])
    ledger.execute(funding_tx)

    print(f"\n  Initial balances:")
    print(f"    alice: ${ledger.get_balance('alice', 'USD'):,.0f}")
    print(f"    bob:   ${ledger.get_balance('bob', 'USD'):,.0f}")
    print(f"    CME:   ${ledger.get_balance('CME', 'USD'):,.0f}")

    # =========================================================================
    # SETUP LIFECYCLE ENGINE
    # =========================================================================
    print("\n" + "="*70)
    print("  PHASE 3: Creating LifecycleEngine")
    print("="*70)

    engine = LifecycleEngine(ledger)
    engine.register(UNIT_TYPE_FUTURE, future_contract)

    print(f"\n  LifecycleEngine created")
    print(f"  Registered contracts: {list(engine.contracts.keys())}")

    # =========================================================================
    # INITIAL TRADES (Day 1)
    # =========================================================================
    print("\n" + "="*70)
    print("  PHASE 4: Initial Trades (Day 1)")
    print("="*70)

    day1_price = pricing_source.get_price("SPX", trading_days[0])
    print(f"\n  Day 1: {trading_days[0].date()}")
    print(f"  SPX Price: {day1_price:,.2f}")

    print("\n  --- Alice buys 20 contracts (goes LONG) ---")
    # Long: clearinghouse sells to alice
    result = future_transact(ledger, "ESZ24", seller_id="CME", buyer_id="alice", qty=20, price=day1_price)
    ledger.execute(result)

    print("\n  --- Bob sells 15 contracts (goes SHORT) ---")
    # Short: bob sells to clearinghouse
    result = future_transact(ledger, "ESZ24", seller_id="bob", buyer_id="CME", qty=15, price=day1_price)
    ledger.execute(result)

    # Show initial state
    state = ledger.get_unit_state("ESZ24")
    print(f"\n  After Day 1 trades:")
    for wallet in ["alice", "bob"]:
        w = state['wallets'].get(wallet, {})
        print(f"    {wallet}: position={w.get('position', 0):+.0f}, vcash={w.get('virtual_cash', 0):+,.0f}")

    # =========================================================================
    # RUN LIFECYCLE ENGINE FOR ALL TRADING DAYS
    # =========================================================================
    print("\n" + "="*70)
    print("  PHASE 5: Running LifecycleEngine (Daily MTM)")
    print("="*70)

    print(f"\n  Processing {len(trading_days)} trading days...")
    print(f"  (Verbose output shows each MTM settlement)\n")

    # Track daily P&L for summary
    daily_data = []

    for i, day in enumerate(trading_days):
        prices = pricing_source.get_prices({"SPX"}, day)
        spx_price = prices.get("SPX", 0)

        # Get balances before MTM
        alice_before = ledger.get_balance("alice", "USD")
        bob_before = ledger.get_balance("bob", "USD")

        print(f"\n  {'='*60}")
        print(f"  Day {i+1}: {day.date()} | SPX: {spx_price:,.2f}")
        print(f"  {'='*60}")

        # Run lifecycle engine step
        transactions = engine.step(day, prices)

        # Get balances after MTM
        alice_after = ledger.get_balance("alice", "USD")
        bob_after = ledger.get_balance("bob", "USD")

        alice_pnl = alice_after - alice_before
        bob_pnl = bob_after - bob_before

        daily_data.append({
            'day': i + 1,
            'date': day.date(),
            'spx': spx_price,
            'alice_pnl': alice_pnl,
            'bob_pnl': bob_pnl,
            'alice_balance': alice_after,
            'bob_balance': bob_after,
        })

        if transactions:
            print(f"\n  Daily P&L: Alice={alice_pnl:+,.0f}, Bob={bob_pnl:+,.0f}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "="*70)
    print("  PHASE 6: Summary")
    print("="*70)

    print("\n  Daily P&L History:")
    print(f"  {'Day':<5} {'Date':<12} {'SPX':>10} {'Alice P&L':>12} {'Bob P&L':>12}")
    print(f"  {'-'*5} {'-'*12} {'-'*10} {'-'*12} {'-'*12}")

    for d in daily_data:
        if d['alice_pnl'] != 0 or d['bob_pnl'] != 0:
            print(f"  {d['day']:<5} {str(d['date']):<12} {d['spx']:>10,.2f} {d['alice_pnl']:>+12,.0f} {d['bob_pnl']:>+12,.0f}")

    # Final state
    final_state = ledger.get_unit_state("ESZ24")
    print(f"\n  Final State:")
    print(f"    Last settlement price: {final_state.get('last_settle_price'):,.2f}")
    print(f"    Contract settled: {final_state.get('settled', False)}")

    # Final balances
    print(f"\n  Final Cash Balances:")
    alice_final = ledger.get_balance("alice", "USD")
    bob_final = ledger.get_balance("bob", "USD")
    cme_final = ledger.get_balance("CME", "USD")

    print(f"    alice:  ${alice_final:>12,.0f}  (P&L: ${alice_final - 1_000_000:+,.0f})")
    print(f"    bob:    ${bob_final:>12,.0f}  (P&L: ${bob_final - 1_000_000:+,.0f})")
    print(f"    CME:    ${cme_final:>12,.0f}  (P&L: ${cme_final - 100_000_000:+,.0f})")

    # Verify P&L calculation
    entry_price = spx_prices[0][1]
    final_price = spx_prices[-1][1]
    price_change = final_price - entry_price

    print(f"\n  P&L Verification:")
    print(f"    Entry price: {entry_price:,.2f}")
    print(f"    Final price: {final_price:,.2f}")
    print(f"    Price change: {price_change:+,.2f}")
    print(f"    Alice expected: 20 * {price_change:+,.2f} * 50 = ${20 * price_change * 50:+,.0f}")
    print(f"    Bob expected:   -15 * {price_change:+,.2f} * 50 = ${-15 * price_change * 50:+,.0f}")

    # Conservation check
    total_initial = 1_000_000 + 1_000_000 + 100_000_000
    total_final = alice_final + bob_final + cme_final
    print(f"\n  Cash Conservation:")
    print(f"    Initial total: ${total_initial:,.0f}")
    print(f"    Final total:   ${total_final:,.0f}")
    print(f"    Difference:    ${total_final - total_initial:,.0f} (should be 0)")

    # =========================================================================
    # TRANSACTION LOG
    # =========================================================================
    print("\n" + "="*70)
    print("  PHASE 7: Transaction Log Summary")
    print("="*70)

    print(f"\n  Total transactions logged: {len(ledger.transaction_log)}")
    print(f"\n  Last 5 transactions:")
    for tx in ledger.transaction_log[-5:]:
        print(f"    [{tx.timestamp.date()}] {len(tx.moves)} moves")
        for move in tx.moves[:3]:  # Show first 3 moves
            print(f"      {move.source} -> {move.dest}: {move.unit_symbol} {move.quantity:,.2f}")

    print("\n" + "="*70)
    print("  DEMO COMPLETE")
    print("="*70)
    print("""
  This demo showed:
  1. TimeSeriesPricingSource with simulated daily prices
  2. LifecycleEngine automatically processing daily MTM
  3. Ledger verbose mode showing all internal operations
  4. Complete audit trail via transaction_log
  5. Zero-sum cash conservation throughout
""")


if __name__ == "__main__":
    main()
