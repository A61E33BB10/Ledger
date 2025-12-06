"""
examples.py - Comprehensive Usage Examples for the Ledger System

This module demonstrates the features of the ledger system:
1. Basic operations (wallets, units, transactions)
2. Memory monitoring and optimization
3. Ledger operations (clone, replay, time travel)
4. Smart contracts (dividends)
5. Precision and rounding
6. Load testing and performance benchmarks
7. Transfer rules and bilateral instruments
8. LifecycleEngine for autonomous contract execution

For detailed examples of specific features, see:
- option_example.py: Complete bilateral option lifecycle
- delta_hedge_example.py: Delta hedging with daily rebalancing
- state_at_example.py: State reconstruction with clone_at()

Run this file directly to execute all examples:
    python examples.py
"""

from datetime import datetime, timedelta
import time
import random

from ledger import (
    # Core
    Ledger, Unit, Move, ExecuteResult, ContractResult,
    StateDelta,
    cash,
    bilateral_transfer_rule,

    # Stock module
    create_stock_unit,
    stock_contract,

    # Options module
    create_option_unit,
    build_option_trade,
    compute_option_settlement,
    option_contract,

    # Forwards module
    create_forward_unit,
    forward_contract,

    # Engine
    LifecycleEngine,
)


def stock(symbol: str, name: str, issuer: str, shortable: bool = False):
    """Helper to create a simple stock unit (for examples)."""
    return create_stock_unit(symbol, name, issuer, "USD", shortable=shortable)


def example_basic_operations():
    """Example 1: Basic Ledger Operations"""
    print("="*80)
    print("EXAMPLE 1: Basic Ledger Operations")
    print("="*80 + "\n")

    # Create a ledger with verbose output
    ledger = Ledger(
        name="demo",
        initial_time=datetime(2024, 1, 1, 9, 30, 0),
        verbose=True,
        fast_mode=False,
        no_log=False
    )

    # Register units (asset types)
    print("Registering units...")
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL", shortable=True))
    ledger.register_unit(stock("MSFT", "Microsoft Corp.", issuer="MSFT", shortable=False))
    print()

    # List units
    print(f"Registered unit symbols: {ledger.list_units()}")
    print()

    # Register wallets
    print("Registering wallets...")
    alice = ledger.register_wallet("alice")
    bob = ledger.register_wallet("bob")
    charlie = ledger.register_wallet("charlie")
    mint = ledger.register_wallet("mint")
    market = ledger.register_wallet("market")
    print(f"Registered: {ledger.list_wallets()}\n")

    # Issue currency (mint -> alice)
    print("--- Transaction 1: Issue currency ---")
    tx1 = ledger.create_transaction([
        Move(source=mint, dest=alice, unit="USD", quantity=10000.0, contract_id="initial_funding")
    ])
    ledger.execute(tx1)

    # Simple payment (alice -> bob)
    print("--- Transaction 2: Payment ---")
    ledger.advance_time(datetime(2024, 1, 1, 9, 31, 0))
    tx2 = ledger.create_transaction([
        Move(source=alice, dest=bob, unit="USD", quantity=150.75, contract_id="payment_001")
    ])
    ledger.execute(tx2)

    # Multi-move transaction (stock purchase)
    print("--- Transaction 3: Stock Purchase (multi-move) ---")
    ledger.advance_time(datetime(2024, 1, 1, 9, 32, 0))
    tx3 = ledger.create_transaction([
        Move(source=alice, dest=market, unit="USD", quantity=5000.0, contract_id="trade_001"),
        Move(source=market, dest=alice, unit="AAPL", quantity=25.0, contract_id="trade_001")
    ])
    ledger.execute(tx3)

    # Query balances
    print("\n--- Balance Queries ---")
    print(f"Alice USD balance: ${ledger.get_balance('alice', 'USD'):.2f}")
    print(f"Alice AAPL balance: {ledger.get_balance('alice', 'AAPL')} shares")
    print(f"Alice all balances: {ledger.get_wallet_balances('alice')}")
    print(f"Total USD supply: ${ledger.total_supply('USD'):.2f}")
    print(f"Total AAPL supply: {ledger.total_supply('AAPL')} shares")

    # Idempotency test
    print("\n--- Transaction 4: Idempotency Test ---")
    result = ledger.execute(tx2)
    print(f"Result: {result}")

    # Rejection test
    print("\n--- Transaction 5: Insufficient Funds Test ---")
    ledger.advance_time(datetime(2024, 1, 1, 9, 33, 0))
    tx_bad = ledger.create_transaction([
        Move(source=charlie, dest=alice, unit="MSFT", quantity=10.0, contract_id="bad_trade")
    ])
    result_bad = ledger.execute(tx_bad)
    print(f"Result: {result_bad}")

    # Final state
    print("\n--- Final State ---")
    for wallet in ledger.list_wallets():
        balances = ledger.get_wallet_balances(wallet)
        non_zero = {k: v for k, v in balances.items() if v != 0}
        if non_zero:
            print(f"  {wallet}: {non_zero}")

    return ledger


def example_memory_monitoring():
    """Example 2: Memory Monitoring"""
    print("\n\n" + "="*80)
    print("EXAMPLE 2: Memory Monitoring")
    print("="*80 + "\n")

    print("Creating ledger with sample data...")
    mem_ledger = Ledger("memory_test", verbose=False, fast_mode=True, no_log=False)
    mem_ledger.register_unit(cash("USD", "US Dollar"))
    mem_ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL"))

    trader = mem_ledger.register_wallet("trader")
    broker = mem_ledger.register_wallet("broker")

    print("Executing 10,000 transactions...")
    for i in range(10_000):
        mem_ledger.advance_time(mem_ledger.current_time + timedelta(microseconds=1))
        tx = mem_ledger.create_transaction([
            Move(source=trader, dest=broker, unit="USD", quantity=100.0, contract_id=f"trade_{i}")
        ])
        mem_ledger.execute(tx)

    stats = mem_ledger.get_memory_stats()
    print(f"Memory stats: {stats}")

    # Compare with no_log mode
    print("\n--- Comparing with no_log=True ---")
    nolog_ledger = Ledger("memory_test_nolog", verbose=False, fast_mode=True, no_log=True)
    nolog_ledger.register_unit(cash("USD", "US Dollar"))
    nolog_ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL"))
    nolog_trader = nolog_ledger.register_wallet("trader")
    nolog_broker = nolog_ledger.register_wallet("broker")

    print("Executing 10,000 transactions with no_log=True...")
    for i in range(10_000):
        nolog_ledger.advance_time(nolog_ledger.current_time + timedelta(microseconds=1))
        tx = nolog_ledger.create_transaction([
            Move(source=nolog_trader, dest=nolog_broker, unit="USD", quantity=100.0, contract_id=f"trade_{i}")
        ])
        nolog_ledger.execute(tx)

    stats_no_log = nolog_ledger.get_memory_stats()
    print(f"Memory stats (no_log): {stats_no_log}")

    savings = stats['total'] - stats_no_log['total']
    savings_pct = (savings / stats['total']) * 100 if stats['total'] > 0 else 0

    print(f"Memory savings with no_log=True: {savings:,} bytes ({savings_pct:.1f}%)")


def example_ledger_operations(ledger: Ledger):
    """Example 3: Ledger Operations (clone, replay)"""
    print("\n\n" + "="*80)
    print("EXAMPLE 3: Ledger Operations (clone, replay)")
    print("="*80 + "\n")

    # Clone ledger
    print("--- Cloning Ledger ---")
    ledger_clone = ledger.clone()
    ledger_clone.name = "demo_clone"
    ledger_clone.verbose = False

    ledger_clone.advance_time(datetime(2024, 1, 1, 9, 34, 0))
    tx_clone = ledger_clone.create_transaction([
        Move(source="alice", dest="bob", unit="USD", quantity=100.0, contract_id="clone_payment")
    ])
    ledger_clone.execute(tx_clone)

    print(f"Original Alice balance: ${ledger.get_balance('alice', 'USD'):.2f}")
    print(f"Clone Alice balance: ${ledger_clone.get_balance('alice', 'USD'):.2f}")
    print("(Clone is independent - changes don't affect original)\n")

    # Replay ledger
    print("--- Replaying Ledger History ---")
    print("Creating new ledger by replaying all transactions...")
    ledger_replay = ledger.replay(from_tx=0, fast_mode=True, no_log=False)
    ledger_replay.verbose = False

    print(f"Original Alice balance: ${ledger.get_balance('alice', 'USD'):.2f}")
    print(f"Replayed Alice balance: ${ledger_replay.get_balance('alice', 'USD'):.2f}")
    print("(Replay produces identical state)\n")


def example_smart_contracts():
    """Example 4: Smart Contracts with Scheduled Dividends"""
    print("\n\n" + "="*80)
    print("EXAMPLE 4: Smart Contracts with Scheduled Dividends")
    print("="*80 + "\n")

    print("Demonstrating the stock contract with scheduled dividends.")
    print("Dividends are scheduled at unit creation and paid automatically via LifecycleEngine.\n")

    # Create quarterly dividend schedule as simple (date, amount) tuples
    start_date = datetime(2024, 1, 1)
    schedule = [
        (datetime(2024, 3, 29), 0.25),  # Q1 payment
        (datetime(2024, 6, 28), 0.25),  # Q2 payment
        (datetime(2024, 9, 27), 0.25),  # Q3 payment
        (datetime(2024, 12, 27), 0.25), # Q4 payment
    ]

    print(f"Created dividend schedule with {len(schedule)} payments:")
    for payment_date, amount in schedule:
        print(f"  Payment: {payment_date.date()}, Amount: ${amount}")

    sc_ledger = Ledger("smart_contract_demo", initial_time=start_date, verbose=True)
    sc_ledger.register_unit(cash("USD", "US Dollar"))

    # Register stock with dividend schedule
    sc_ledger.register_unit(create_stock_unit(
        "AAPL", "Apple Inc.",
        issuer="aapl_treasury",
        currency="USD",
        dividend_schedule=schedule,
        shortable=True,
    ))

    print("\n--- Setting up wallets and initial positions ---")
    treasury = sc_ledger.register_wallet("aapl_treasury")
    alice = sc_ledger.register_wallet("alice")
    bob = sc_ledger.register_wallet("bob")
    charlie = sc_ledger.register_wallet("charlie")
    mint = sc_ledger.register_wallet("mint")

    tx = sc_ledger.create_transaction([
        Move(source=mint, dest=treasury, unit="USD", quantity=100000.0, contract_id="treasury_funding")
    ])
    sc_ledger.execute(tx)

    print("\n--- Distributing shares ---")
    sc_ledger.advance_time(datetime(2024, 1, 2, 9, 0, 0))
    tx = sc_ledger.create_transaction([
        Move(source=treasury, dest=alice, unit="AAPL", quantity=100.0, contract_id="initial_dist"),
        Move(source=treasury, dest=bob, unit="AAPL", quantity=50.0, contract_id="initial_dist"),
        Move(source=treasury, dest=charlie, unit="AAPL", quantity=25.0, contract_id="initial_dist")
    ])
    sc_ledger.execute(tx)

    # Setup engine with stock_contract
    engine = LifecycleEngine(sc_ledger)
    engine.register("STOCK", stock_contract)

    # Check balances BEFORE dividend
    print(f"\nBefore dividend payment:")
    print(f"  Alice USD: ${sc_ledger.get_balance(alice, 'USD'):.2f}")
    print(f"  Treasury USD: ${sc_ledger.get_balance(treasury, 'USD'):.2f}")

    # Run engine to the first payment date (March 29, 2024)
    print("\n--- Running Engine to First Dividend Payment ---")
    payment_date = schedule[0][0]
    txs = engine.step(payment_date, {})

    print(f"Executed {len(txs)} transaction(s) at {payment_date}")
    assert len(txs) == 1, f"Expected 1 dividend transaction, got {len(txs)}"

    # Check balances AFTER execution
    print(f"\nAfter dividend payment:")
    alice_usd = sc_ledger.get_balance(alice, 'USD')
    bob_usd = sc_ledger.get_balance(bob, 'USD')
    charlie_usd = sc_ledger.get_balance(charlie, 'USD')
    treasury_usd = sc_ledger.get_balance(treasury, 'USD')

    print(f"  Alice USD: ${alice_usd:.2f} (100 shares x $0.25 = $25)")
    print(f"  Bob USD: ${bob_usd:.2f} (50 shares x $0.25 = $12.50)")
    print(f"  Charlie USD: ${charlie_usd:.2f} (25 shares x $0.25 = $6.25)")
    print(f"  Treasury USD: ${treasury_usd:.2f}")

    # Verify amounts
    assert alice_usd == 25.0, f"Alice should have $25, got ${alice_usd}"
    assert bob_usd == 12.5, f"Bob should have $12.50, got ${bob_usd}"
    assert charlie_usd == 6.25, f"Charlie should have $6.25, got ${charlie_usd}"
    print("\nAll dividend amounts verified!")

    # Check that state was updated
    state = sc_ledger.get_unit_state('AAPL')
    paid_count = len(state.get('paid_dividends', []))
    print(f"\nState updated: paid_dividends = {paid_count} record(s)")
    assert paid_count == 1, f"Expected 1 paid dividend, got {paid_count}"


def example_load_test(
    num_wallets: int = 10_000,
    num_units: int = 10_000,
    num_moves: int = 1_000_000,
):
    """Example 5: Load Performance Test

    Demonstrates the ledger's capacity for large-scale simulations:
    - Thousands of wallets and units
    - High-volume transaction processing
    - Memory consumption patterns

    Args:
        num_wallets: Number of wallets to create (default 10,000)
        num_units: Number of stock units to create (default 10,000)
        num_moves: Number of transactions to execute (default 1,000,000)

    Returns:
        dict with performance metrics
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Load Performance Test")
    print("=" * 80 + "\n")

    print("Setting up large-scale simulation:")
    print(f"  - {num_wallets:,} wallets")
    print(f"  - {num_units:,} shortable shares")
    print(f"  - {num_moves:,} random moves")
    print()

    load_ledger = Ledger(
        name="load_test",
        verbose=False,
        fast_mode=True,  # Use fast mode for load testing
        no_log=True      # Skip logging for maximum throughput
    )

    # Phase 1: Register units
    print(f"1. Registering {num_units:,} shares...", end=" ", flush=True)
    setup_start = time.perf_counter()
    for i in range(1, num_units + 1):
        load_ledger.register_unit(stock(
            symbol=f"STOCK{i:05d}",
            name=f"Company {i}",
            issuer=f"ISSUER{i}",
            shortable=True
        ))
    setup_units = time.perf_counter() - setup_start
    print(f"Done in {setup_units:.2f}s ({num_units/setup_units:,.0f} units/s)")

    # Phase 2: Register wallets
    print(f"2. Registering {num_wallets:,} wallets...", end=" ", flush=True)
    setup_start = time.perf_counter()
    wallets = []
    for i in range(1, num_wallets + 1):
        wallet_id = f"wallet_{i:05d}"
        load_ledger.register_wallet(wallet_id)
        wallets.append(wallet_id)
    setup_wallets = time.perf_counter() - setup_start
    print(f"Done in {setup_wallets:.2f}s ({num_wallets/setup_wallets:,.0f} wallets/s)")

    # Phase 3: Prepare random moves (pre-generate for accurate timing)
    print(f"3. Preparing {num_moves:,} random moves...", end=" ", flush=True)
    prep_start = time.perf_counter()

    random.seed(42)  # Reproducible
    units = [f"STOCK{i:05d}" for i in range(1, num_units + 1)]

    # Pre-generate all moves for accurate execution timing
    random_moves = []
    for _ in range(num_moves):
        source = random.choice(wallets)
        dest = random.choice(wallets)
        while dest == source:
            dest = random.choice(wallets)
        unit = random.choice(units)
        quantity = random.uniform(1.0, 100.0)
        random_moves.append((source, dest, unit, quantity))

    prep_time = time.perf_counter() - prep_start
    print(f"Done in {prep_time:.2f}s")

    # Phase 4: Execute transactions
    print(f"\n4. Executing {num_moves:,} transactions...", flush=True)

    # Progress reporting
    report_interval = max(1, num_moves // 10)
    exec_start = time.perf_counter()
    last_report = exec_start

    for i, (source, dest, unit, quantity) in enumerate(random_moves):
        load_ledger.advance_time(load_ledger.current_time + timedelta(microseconds=1))
        tx = load_ledger.create_transaction([
            Move(source=source, dest=dest, unit=unit, quantity=quantity, contract_id=f"trade_{i}")
        ])
        load_ledger.execute(tx)

        # Progress report every 10%
        if (i + 1) % report_interval == 0:
            elapsed = time.perf_counter() - exec_start
            current_tps = (i + 1) / elapsed
            pct = ((i + 1) / num_moves) * 100
            print(f"   {pct:5.1f}% complete ({i+1:,} txs) - {current_tps:,.0f} tx/s")

    exec_time = time.perf_counter() - exec_start
    throughput = num_moves / exec_time

    # Results
    print("\n" + "=" * 80)
    print("LOAD TEST RESULTS (fast_mode=True, no_log=True)")
    print("=" * 80)
    print(f"{'Phase':<40} {'Time':>10} {'Rate':>20}")
    print("-" * 80)
    print(f"{'Setup: ' + f'{num_units:,} units':<40} {setup_units:>8.2f}s {f'{num_units/setup_units:,.0f} units/s':>20}")
    print(f"{'Setup: ' + f'{num_wallets:,} wallets':<40} {setup_wallets:>8.2f}s {f'{num_wallets/setup_wallets:,.0f} wallets/s':>20}")
    print(f"{'Preparation: ' + f'{num_moves:,} moves':<40} {prep_time:>8.2f}s {'-':>20}")
    print(f"{'Execution: ' + f'{num_moves:,} transactions':<40} {exec_time:>8.2f}s {f'{throughput:,.0f} tx/s':>20}")
    print("-" * 80)
    total_time = setup_units + setup_wallets + prep_time + exec_time
    print(f"{'TOTAL':<40} {total_time:>8.2f}s")

    # Memory stats
    print(f"\n5. Memory consumption after {num_moves:,} transactions:")
    stats = load_ledger.get_memory_stats()
    print(f"   {stats}")

    # Sample positions
    print("\n6. Sample wallet balances (first 5 wallets):")
    for wallet in wallets[:5]:
        balances = load_ledger.get_wallet_balances(wallet)
        non_zero = {k: round(v, 2) for k, v in sorted(balances.items())[:5] if v != 0}
        print(f"   {wallet}: {len(balances)} positions, sample: {non_zero if non_zero else '(all zero)'}")

    # Position statistics
    total_positions = sum(
        1 for w in wallets
        for v in load_ledger.get_wallet_balances(w).values()
        if v != 0
    )
    print(f"\nNon-zero positions: {total_positions:,}")
    print(f"Average positions per wallet: {total_positions / len(wallets):.1f}")

    return {
        'throughput': throughput,
        'setup_units_time': setup_units,
        'setup_wallets_time': setup_wallets,
        'exec_time': exec_time,
        'total_time': total_time,
        'num_wallets': num_wallets,
        'num_units': num_units,
        'num_moves': num_moves,
    }


def example_precision():
    """Example 6: Rounding and Precision Verification"""
    print("\n\n" + "="*80)
    print("EXAMPLE 6: Rounding and Precision")
    print("="*80 + "\n")

    print("Demonstrating that unit rounding prevents floating-point drift...")
    print("Test: Transfer 0.01 USD 100 times (should equal exactly 1.00)\n")

    precision_ledger = Ledger("precision_test", verbose=False, fast_mode=True)
    precision_ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))

    a = precision_ledger.register_wallet("a")
    b = precision_ledger.register_wallet("b")

    for i in range(100):
        precision_ledger.advance_time(precision_ledger.current_time + timedelta(seconds=1))
        tx = precision_ledger.create_transaction([
            Move(source=a, dest=b, unit="USD", quantity=0.01, contract_id=f"t{i}")
        ])
        precision_ledger.execute(tx)

    balance_b = precision_ledger.get_balance("b", "USD")
    balance_a = precision_ledger.get_balance("a", "USD")

    print(f"Wallet B balance: {balance_b}")
    print(f"Wallet A balance: {balance_a}")
    print(f"Total supply: {precision_ledger.total_supply('USD')}")

    print("PASS" if balance_b == 1.00 else f"FAIL: {balance_b}")

    # Fractional shares
    print("\n--- Testing fractional shares with 6 decimal places ---")
    precision_ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL", shortable=True))
    trader1 = precision_ledger.register_wallet("trader1")
    trader2 = precision_ledger.register_wallet("trader2")

    for i in range(1000):
        precision_ledger.advance_time(precision_ledger.current_time + timedelta(microseconds=1))
        tx = precision_ledger.create_transaction([
            Move(source=trader1, dest=trader2, unit="AAPL", quantity=0.000001, contract_id=f"micro_{i}")
        ])
        precision_ledger.execute(tx)

    aapl_balance = precision_ledger.get_balance("trader2", "AAPL")
    print(f"Trader2 AAPL balance after 1000 micro-trades: {aapl_balance}")
    print("PASS" if aapl_balance == 0.001000 else f"FAIL: expected 0.001000")

    # Conservation law
    print("\n--- Testing conservation law ---")
    usd_supply = precision_ledger.total_supply("USD")
    aapl_supply = precision_ledger.total_supply("AAPL")
    print(f"USD total supply: {usd_supply} {'OK' if abs(usd_supply) < 1e-10 else 'FAIL'}")
    print(f"AAPL total supply: {aapl_supply} {'OK' if abs(aapl_supply) < 1e-10 else 'FAIL'}")


def example_performance_benchmark():
    """Example 7: Performance Benchmark"""
    print("\n\n" + "="*80)
    print("EXAMPLE 7: Performance Benchmark")
    print("="*80 + "\n")

    print("Running performance benchmark with 50,000 transactions...")
    print("(Testing different performance modes)\n")

    N = 50_000

    def run_benchmark(fast_mode: bool, no_log: bool):
        bench = Ledger("bench", initial_time=datetime(2024, 1, 1),
                       verbose=False, fast_mode=fast_mode, no_log=no_log)
        bench.register_unit(cash("USD", "US Dollar"))
        buyer = bench.register_wallet("buyer")
        seller = bench.register_wallet("seller")

        start = time.perf_counter()
        for i in range(N):
            bench.advance_time(bench.current_time + timedelta(microseconds=1))
            tx = bench.create_transaction([
                Move(source=buyer, dest=seller, unit="USD", quantity=100.0, contract_id=f"trade_{i}")
            ])
            bench.execute(tx)
        elapsed = time.perf_counter() - start
        return N / elapsed

    print("1. Standard mode (validation + logging)...", end=" ", flush=True)
    tps_std = run_benchmark(False, False)
    print(f"{tps_std:,.0f} tx/sec")
    time.sleep(1)

    print("2. Fast mode (skip validation)...", end=" ", flush=True)
    tps_fast = run_benchmark(True, False)
    print(f"{tps_fast:,.0f} tx/sec ({tps_fast/tps_std:.2f}x)")
    time.sleep(1)

    print("3. No-log mode (skip logging)...", end=" ", flush=True)
    tps_nolog = run_benchmark(False, True)
    print(f"{tps_nolog:,.0f} tx/sec ({tps_nolog/tps_std:.2f}x)")
    time.sleep(1)

    print("4. Maximum speed (fast + no-log)...", end=" ", flush=True)
    tps_max = run_benchmark(True, True)
    print(f"{tps_max:,.0f} tx/sec ({tps_max/tps_std:.2f}x)")

    print("\n" + "="*80)
    print("PERFORMANCE SUMMARY")
    print("="*80)
    print(f"{'Configuration':<35} {'Throughput':<20} {'Speedup':<15}")
    print("-"*80)
    print(f"{'Standard (validate + log)':<35} {f'{tps_std:,.0f} tx/sec':<20} {'1.00x baseline':<15}")
    print(f"{'Fast mode (skip validation)':<35} {f'{tps_fast:,.0f} tx/sec':<20} {f'{tps_fast/tps_std:.2f}x faster':<15}")
    print(f"{'No-log mode (skip logging)':<35} {f'{tps_nolog:,.0f} tx/sec':<20} {f'{tps_nolog/tps_std:.2f}x faster':<15}")
    print(f"{'Maximum (fast + no-log)':<35} {f'{tps_max:,.0f} tx/sec':<20} {f'{tps_max/tps_std:.2f}x faster':<15}")

    return tps_max


def example_bilateral_options():
    """Example 8: Bilateral Options with Transfer Rules"""
    print("\n\n" + "="*80)
    print("EXAMPLE 8: Bilateral Option with Transfer Rules")
    print("="*80 + "\n")

    print("Creating a bilateral OTC call option between Alice (long) and Bob (short)...")
    print("This option can only be held by Alice and Bob. Third-party transfers are rejected.\n")

    ledger = Ledger("bilateral_demo", verbose=True)

    ledger.register_unit(cash("USD", "US Dollar"))
    ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL", shortable=True))

    alice = ledger.register_wallet("alice")
    bob = ledger.register_wallet("bob")
    charlie = ledger.register_wallet("charlie")
    mint = ledger.register_wallet("mint")

    # Create bilateral option using direct parameters
    otc_call = create_option_unit(
        symbol="OTC_AAPL_CALL_150",
        name="OTC AAPL Call $150 (Alice/Bob)",
        underlying="AAPL",
        strike=150.0,
        maturity=datetime(2024, 12, 31),
        option_type="call",
        quantity=100,
        currency="USD",
        long_wallet=alice,
        short_wallet=bob,
    )
    ledger.register_unit(otc_call)

    print("\n--- Initial Funding ---")
    tx = ledger.create_transaction([
        Move(source=mint, dest=alice, unit="USD", quantity=100000, contract_id="fund_alice"),
        Move(source=mint, dest=bob, unit="USD", quantity=100000, contract_id="fund_bob"),
        Move(source=mint, dest=charlie, unit="USD", quantity=100000, contract_id="fund_charlie"),
    ])
    ledger.execute(tx)

    print("\n--- Bob writes option to Alice (ALLOWED) ---")
    ledger.advance_time(datetime(2024, 6, 1))
    premium = 850.0
    tx = ledger.create_transaction([
        Move(source=alice, dest=bob, unit="USD", quantity=premium, contract_id="premium"),
        Move(source=bob, dest=alice, unit="OTC_AAPL_CALL_150", quantity=1, contract_id="option_trade")
    ])
    result = ledger.execute(tx)
    print(f"Result: {result}\n")

    print("--- Current Positions ---")
    print(f"Alice: {ledger.get_balance(alice, 'OTC_AAPL_CALL_150')} option (long)")
    print(f"Bob: {ledger.get_balance(bob, 'OTC_AAPL_CALL_150')} option (short)")

    print("\n--- Alice tries to sell option to Charlie (REJECTED) ---")
    ledger.advance_time(datetime(2024, 6, 2))
    tx_illegal = ledger.create_transaction([
        Move(source=alice, dest=charlie, unit="OTC_AAPL_CALL_150", quantity=1, contract_id="illegal_transfer")
    ])
    result = ledger.execute(tx_illegal)
    print(f"Result: {result}")

    print("\n--- Alice closes position with Bob (ALLOWED) ---")
    ledger.advance_time(datetime(2024, 6, 3))
    close_tx = ledger.create_transaction([
        Move(source=alice, dest=bob, unit="OTC_AAPL_CALL_150", quantity=1, contract_id="close_position")
    ])
    result = ledger.execute(close_tx)
    print(f"Result: {result}")

    print("\n--- Final Positions ---")
    print(f"Alice: {ledger.get_balance(alice, 'OTC_AAPL_CALL_150')} option")
    print(f"Bob: {ledger.get_balance(bob, 'OTC_AAPL_CALL_150')} option")
    print(f"Charlie: {ledger.get_balance(charlie, 'OTC_AAPL_CALL_150')} option")


def example_clone_and_clone_at():
    """Example 9: State Cloning and Time Travel"""
    print("\n\n" + "="*80)
    print("EXAMPLE 9: State Cloning and Time Travel with clone_at()")
    print("="*80 + "\n")

    print("Demonstrating clone() and clone_at() for state capture and time travel...")
    print("clone_at() reconstructs a full Ledger at any past time for divergent scenarios.\n")

    ledger = Ledger("clone_demo", datetime(2025, 1, 1), verbose=False)
    ledger.register_unit(cash("USD", "US Dollar"))
    ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL"))

    alice = ledger.register_wallet("alice")
    bob = ledger.register_wallet("bob")

    # Initial funding
    ledger.balances[alice]["USD"] = 10_000
    ledger.balances[alice]["AAPL"] = 100

    print("--- Initial State (Jan 1) ---")
    clone_t0 = ledger.clone()
    print(f"Alice: ${clone_t0.get_balance('alice', 'USD'):,.2f} USD, "
          f"{clone_t0.get_balance('alice', 'AAPL')} AAPL")

    # Day 1: Transfer
    print("\n--- Day 1 Transaction ---")
    ledger.advance_time(datetime(2025, 1, 2))
    tx1 = ledger.create_transaction([
        Move(alice, bob, "USD", 1000.0, "payment_1"),
        Move(alice, bob, "AAPL", 25.0, "trade_1"),
    ])
    ledger.execute(tx1)
    print(f"Alice sends $1000 and 25 AAPL to Bob")

    # Day 2: Another transfer
    print("\n--- Day 2 Transaction ---")
    ledger.advance_time(datetime(2025, 1, 3))
    tx2 = ledger.create_transaction([
        Move(alice, bob, "USD", 500.0, "payment_2"),
    ])
    ledger.execute(tx2)
    print(f"Alice sends $500 to Bob")

    # Current state
    print("\n--- Current State (Jan 3) ---")
    print(f"Alice: ${ledger.get_balance('alice', 'USD'):,.2f} USD, "
          f"{ledger.get_balance('alice', 'AAPL')} AAPL")
    print(f"Bob:   ${ledger.get_balance('bob', 'USD'):,.2f} USD, "
          f"{ledger.get_balance('bob', 'AAPL')} AAPL")

    # Reconstruct state at Day 1
    print("\n--- Reconstructing State at Day 1 (clone_at) ---")
    clone_t1 = ledger.clone_at(datetime(2025, 1, 2))
    print(f"Alice at Jan 2: ${clone_t1.get_balance('alice', 'USD'):,.2f} USD, "
          f"{clone_t1.get_balance('alice', 'AAPL')} AAPL")

    # Reconstruct state at Day 0
    print("\n--- Reconstructing State at Day 0 ---")
    clone_t0_reconstructed = ledger.clone_at(datetime(2025, 1, 1))
    print(f"Alice at Jan 1: ${clone_t0_reconstructed.get_balance('alice', 'USD'):,.2f} USD, "
          f"{clone_t0_reconstructed.get_balance('alice', 'AAPL')} AAPL")

    # Verify reconstruction matches original by comparing balances
    print("\n--- Verifying Reconstruction ---")
    match = True
    for wallet in clone_t0.registered_wallets:
        for unit in clone_t0.units:
            v1 = clone_t0.get_balance(wallet, unit)
            v2 = clone_t0_reconstructed.get_balance(wallet, unit)
            if abs(v1 - v2) > 1e-10:
                match = False
                print(f"Mismatch: {wallet}/{unit}: {v1} vs {v2}")
    if match:
        print("Reconstructed state matches original clone!")

    # Demonstrate that clone_at returns a working ledger
    print("\n--- Divergent Timeline Demo ---")
    print("clone_at() returns a full Ledger that can execute new transactions.")
    clone_t1.advance_time(datetime(2025, 1, 2, 12, 0))
    alt_tx = clone_t1.create_transaction([Move(bob, alice, "USD", 500.0, "refund")])
    clone_t1.execute(alt_tx)
    print(f"In alternate timeline: Bob refunds $500 to Alice")
    print(f"  Alternate Alice USD: ${clone_t1.get_balance('alice', 'USD'):,.2f}")
    print(f"  Main timeline Alice USD: ${ledger.get_balance('alice', 'USD'):,.2f}")


def example_lifecycle_engine():
    """Example 10: LifecycleEngine for Autonomous Contract Execution"""
    print("\n\n" + "="*80)
    print("EXAMPLE 10: LifecycleEngine for Autonomous Contract Execution")
    print("="*80 + "\n")

    print("Demonstrating automatic lifecycle events for options and forwards...")
    print("The LifecycleEngine orchestrates contract execution by calling check_lifecycle().\n")

    start = datetime(2025, 1, 1)
    maturity = datetime(2025, 1, 5)

    ledger = Ledger("engine_demo", start, verbose=True)
    ledger.register_unit(cash("USD", "US Dollar"))
    ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL", shortable=True))

    alice = ledger.register_wallet("alice")
    bob = ledger.register_wallet("bob")

    # Fund wallets
    ledger.balances[alice]["USD"] = 100_000
    ledger.balances[bob]["USD"] = 100_000
    ledger.balances[bob]["AAPL"] = 500

    # Create an option expiring on Jan 5
    print("--- Creating Option (maturity: Jan 5) ---")
    ledger.register_unit(create_option_unit(
        symbol="AAPL_C150",
        name="AAPL Call 150",
        underlying="AAPL",
        strike=150.0,
        maturity=maturity,
        option_type="call",
        quantity=100,
        currency="USD",
        long_wallet=alice,
        short_wallet=bob,
    ))

    # Create a forward expiring on Jan 5
    print("--- Creating Forward (delivery: Jan 5) ---")
    ledger.register_unit(create_forward_unit(
        symbol="AAPL_FWD",
        name="AAPL Forward",
        underlying="AAPL",
        forward_price=155.0,
        delivery_date=maturity,
        quantity=50,
        currency="USD",
        long_wallet=alice,
        short_wallet=bob,
    ))

    # Trade: Bob writes option and forward to Alice
    print("\n--- Initial Trade ---")
    trade_tx = ledger.create_transaction([
        Move(bob, alice, "AAPL_C150", 2, "option_trade"),
        Move(bob, alice, "AAPL_FWD", 1, "forward_trade"),
    ])
    ledger.execute(trade_tx)
    print(f"Alice: {ledger.get_balance(alice, 'AAPL_C150')} options, "
          f"{ledger.get_balance(alice, 'AAPL_FWD')} forwards")

    # Create engine with contract handlers
    engine = LifecycleEngine(ledger)
    engine.register("BILATERAL_OPTION", option_contract)
    engine.register("BILATERAL_FORWARD", forward_contract)

    print("\n--- Running Engine (Jan 1 to Jan 6) ---")
    timestamps = [start + timedelta(days=i) for i in range(6)]

    # Price rises to $160 (options ITM, forward profitable for Alice)
    def get_prices(t):
        day = (t - start).days
        return {"AAPL": 150 + day * 2}  # 150 -> 160

    for t in timestamps:
        price = get_prices(t)["AAPL"]
        txs = engine.step(t, get_prices(t))
        if txs:
            print(f"  {t.date()}: AAPL=${price} - {len(txs)} settlement(s) executed")
        else:
            print(f"  {t.date()}: AAPL=${price} - no events")

    # Check final state
    print("\n--- Final State ---")
    print(f"Alice: ${ledger.get_balance(alice, 'USD'):,.2f} USD, "
          f"{ledger.get_balance(alice, 'AAPL')} AAPL")
    print(f"Bob:   ${ledger.get_balance(bob, 'USD'):,.2f} USD, "
          f"{ledger.get_balance(bob, 'AAPL')} AAPL")

    opt_state = ledger.get_unit_state("AAPL_C150")
    fwd_state = ledger.get_unit_state("AAPL_FWD")
    print(f"\nOption settled: {opt_state.get('settled')}, exercised: {opt_state.get('exercised')}")
    print(f"Forward settled: {fwd_state.get('settled')}")


def print_summary():
    """Print usage recommendations"""
    print("\n\n" + "="*80)
    print("SUMMARY: Usage Recommendations")
    print("="*80)
    print("""
LEDGER MODES:

  Production (full audit trail):
      ledger = Ledger("prod", verbose=False, fast_mode=False, no_log=False)

  Monte Carlo simulations (maximum speed):
      ledger = Ledger("mc", verbose=False, fast_mode=True, no_log=True)

  Debugging:
      ledger = Ledger("debug", verbose=True, fast_mode=False, no_log=False)

SPECIALIZED MODULES:

  Options (options.py):
    - create_option_unit(): Create bilateral option with transfer rules
    - build_option_trade(): Build premium + option transfer moves
    - compute_option_settlement(): Compute settlement at maturity

  Forwards (forwards.py):
    - create_forward_unit(): Create bilateral forward
    - compute_forward_settlement(): Compute physical delivery

  Delta Hedging (delta_hedge_strategy.py):
    - create_delta_hedge_unit(): Create strategy as a unit
    - compute_rebalance(): Compute daily rebalancing trades
    - compute_liquidation(): Close out at maturity

  Stocks (stocks.py):
    - create_stock_unit(): Create stock with dividend schedule
    - Dividend schedule: List of (payment_date, dividend_per_share) tuples

TRANSFER RULES:

  Built-in rules:
    - bilateral_transfer_rule: Only original counterparties can transact

STATE MANAGEMENT:

  Clone and Time Travel:
    - ledger.clone(): Create independent deep copy
    - ledger.clone_at(t): Reconstruct full Ledger at any past time

  LifecycleEngine for Autonomous Execution:
    - SmartContract protocol: check_lifecycle(view, symbol, t, prices)
    - LifecycleEngine: Orchestrates step(t, prices) across all units
    - Built-in contracts: option_contract, forward_contract, stock_contract

See option_example.py and delta_hedge_example.py for detailed examples.
""")


def run_all_examples():
    """Run all examples in order."""
    # Examples 1-3: Core operations
    ledger = example_basic_operations()        # Example 1
    example_memory_monitoring()                # Example 2
    example_ledger_operations(ledger)          # Example 3

    # Example 4: Smart contracts with dividends
    example_smart_contracts()                  # Example 4

    # Examples 5-7: Performance and precision
    example_load_test(num_wallets=100, num_units=100, num_moves=10_000)  # Example 5 (reduced for demo)
    example_precision()                        # Example 6
    example_performance_benchmark()            # Example 7

    # Examples 8-10: Advanced features
    example_bilateral_options()                # Example 8
    example_clone_and_clone_at()               # Example 9
    example_lifecycle_engine()                 # Example 10

    print_summary()


if __name__ == "__main__":
    run_all_examples()
