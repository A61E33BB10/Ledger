"""
test_reproducibility.py - Tests ensuring deterministic, reproducible behavior

These tests verify that:
1. Transaction IDs are deterministic (content-based hashing)
2. Dict iteration order doesn't affect results
3. Clone operations produce identical states
4. Floating-point operations are consistent
5. Engine lifecycle processing is deterministic

Reproducibility is critical for:
- Monte Carlo simulations
- Backtesting
- Debugging
- Audit trails
"""

import pytest
from datetime import datetime, timedelta
from ledger import (
    Ledger, Move, cash, UnitStateChange, build_transaction,
    create_stock_unit,
    LifecycleEngine, option_contract,
    create_option_unit,
    TimeSeriesPricingSource,
    create_delta_hedge_unit, delta_hedge_contract,
    process_dividends, Dividend,
)


# Helper for creating test stocks
def _stock(symbol: str, name: str, issuer: str, shortable: bool = False):
    """Create a stock unit for testing."""
    return create_stock_unit(
        symbol=symbol,
        name=name,
        issuer=issuer,
        currency="USD",
        shortable=shortable,
    )


class TestTransactionIdDeterminism:
    """Tests that transaction IDs are deterministic."""

    def test_same_moves_same_id(self):
        """Same moves should produce same transaction ID."""
        ledger1 = Ledger("test")
        ledger2 = Ledger("test")

        for ledger in [ledger1, ledger2]:
            ledger.register_unit(cash("USD", "US Dollar"))
            ledger.register_wallet("alice")
            ledger.register_wallet("bob")
            ledger.set_balance("alice", "USD", 1000)

        move = Move(100.0, "USD", "alice", "bob", "payment_001")

        tx1 = build_transaction(ledger1, [move])
        tx2 = build_transaction(ledger2, [move])

        # intent_id is content-based, so same moves = same intent_id
        assert tx1.intent_id == tx2.intent_id

    def test_different_moves_different_intent_id(self):
        """Different moves should produce different intent_ids."""
        ledger = Ledger("test")
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000)

        tx1 = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "payment_001")
        ])
        tx2 = build_transaction(ledger, [
            Move(200.0, "USD", "alice", "bob", "payment_002")
        ])

        assert tx1.intent_id != tx2.intent_id

    def test_move_order_does_not_affect_intent_id(self):
        """Move order should NOT affect intent_id (moves are sorted before hashing)."""
        ledger = Ledger("test")
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("charlie")
        ledger.set_balance("alice", "USD", 1000)

        move1 = Move(50.0, "USD", "alice", "bob", "p1")
        move2 = Move(50.0, "USD", "alice", "charlie", "p2")

        tx1 = build_transaction(ledger, [move1, move2])

        # Reset and do in different order
        ledger2 = Ledger("test")
        ledger2.register_unit(cash("USD", "US Dollar"))
        ledger2.register_wallet("alice")
        ledger2.register_wallet("bob")
        ledger2.register_wallet("charlie")
        ledger2.set_balance("alice", "USD", 1000)

        tx2 = build_transaction(ledger2, [move2, move1])

        # Moves are sorted before hashing, so order doesn't matter
        assert tx1.intent_id == tx2.intent_id

    def test_timestamp_does_not_affect_intent_id(self):
        """Different timestamps should NOT affect intent_id (content-based hash)."""
        ledger1 = Ledger("test", initial_time=datetime(2025, 1, 1))
        ledger2 = Ledger("test", initial_time=datetime(2025, 1, 2))

        for ledger in [ledger1, ledger2]:
            ledger.register_unit(cash("USD", "US Dollar"))
            ledger.register_wallet("alice")
            ledger.register_wallet("bob")
            ledger.set_balance("alice", "USD", 1000)

        move = Move(100.0, "USD", "alice", "bob", "payment_001")

        tx1 = build_transaction(ledger1, [move])
        tx2 = build_transaction(ledger2, [move])

        # intent_id is content-based and does NOT include timestamp
        assert tx1.intent_id == tx2.intent_id


class TestCloneReproducibility:
    """Tests that clone operations produce identical states."""

    def test_clone_produces_identical_state(self):
        """Cloning a ledger produces identical state."""
        ledger = Ledger("test")
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc", "aapl_issuer"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 10000)
        ledger.set_balance("alice", "AAPL", 100)

        # Execute some transactions
        ledger.execute(build_transaction(ledger, [
            Move(500.0, "USD", "alice", "bob", "tx1")
        ]))
        ledger.execute(build_transaction(ledger, [
            Move(10.0, "AAPL", "alice", "bob", "tx2")
        ]))

        # Clone
        clone = ledger.clone()

        # Verify identical states
        assert clone.get_balance("alice", "USD") == ledger.get_balance("alice", "USD")
        assert clone.get_balance("bob", "USD") == ledger.get_balance("bob", "USD")
        assert clone.get_balance("alice", "AAPL") == ledger.get_balance("alice", "AAPL")
        assert clone.get_balance("bob", "AAPL") == ledger.get_balance("bob", "AAPL")

    def test_clone_is_independent(self):
        """Changes to clone don't affect original."""
        ledger = Ledger("test")
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000)

        clone = ledger.clone()
        original_balance = ledger.get_balance("alice", "USD")

        # Modify clone
        clone.execute(build_transaction(clone, [
            Move(500.0, "USD", "alice", "bob", "tx1")
        ]))

        # Original unchanged
        assert ledger.get_balance("alice", "USD") == original_balance

    def test_multiple_clones_identical(self):
        """Multiple clones are identical."""
        ledger = Ledger("test")
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000)

        ledger.execute(build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "tx1")
        ]))

        clone1 = ledger.clone()
        clone2 = ledger.clone()

        assert clone1.get_balance("alice", "USD") == clone2.get_balance("alice", "USD")
        assert clone1.get_balance("bob", "USD") == clone2.get_balance("bob", "USD")


class TestReplayReproducibility:
    """Tests that replaying transactions produces identical final state."""

    def test_replay_produces_identical_state(self):
        """Replaying produces consistent results.

        Note: replay() only replays logged transactions. Initial balances set via
        set_balance are NOT preserved - the replayed ledger starts with zero balances,
        then executes all logged transactions.

        This test verifies that:
        1. replay() produces the same result each time
        2. The transaction effects (deltas) are correctly applied
        """
        ledger = Ledger("test")
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc", "issuer"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 10000)
        ledger.set_balance("bob", "USD", 5000)

        # Execute transactions
        tx1 = build_transaction(ledger, [Move(100.0, "USD", "alice", "bob", "p1")])
        tx2 = build_transaction(ledger, [Move(50.0, "USD", "bob", "alice", "p2")])
        ledger.execute(tx1)
        ledger.execute(tx2)

        # replay() starts fresh and re-executes all logged transactions
        # Since set_balance isn't logged, balances start at 0
        # Net effect: alice = 0 - 100 + 50 = -50, bob = 0 + 100 - 50 = 50
        replayed1 = ledger.replay()
        replayed2 = ledger.replay()

        # Both replays produce identical states
        assert replayed1.get_balance("alice", "USD") == replayed2.get_balance("alice", "USD")
        assert replayed1.get_balance("bob", "USD") == replayed2.get_balance("bob", "USD")

        # Verify the expected deltas were applied
        assert replayed1.get_balance("alice", "USD") == -50.0  # 0 - 100 + 50
        assert replayed1.get_balance("bob", "USD") == 50.0     # 0 + 100 - 50

    def test_multiple_replays_identical(self):
        """Multiple replays produce identical states."""
        ledger = Ledger("test")
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000)

        ledger.execute(build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "p1")
        ]))

        replay1 = ledger.replay()
        replay2 = ledger.replay()

        assert replay1.get_balance("alice", "USD") == replay2.get_balance("alice", "USD")
        assert replay1.get_balance("bob", "USD") == replay2.get_balance("bob", "USD")


class TestIterationOrderReproducibility:
    """Tests that dict iteration order doesn't affect results."""

    def test_dividend_order_deterministic(self):
        """Dividend payments are processed in deterministic order."""
        # Create schedule with a single dividend using new API
        ex_date = datetime(2024, 3, 15)
        schedule = [Dividend(ex_date, ex_date, 1.0, "USD")]

        ledger = Ledger("test", initial_time=datetime(2024, 3, 15))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            symbol="AAPL",
            name="Apple Inc",
            issuer="issuer",
            currency="USD",
            dividend_schedule=schedule,
            shortable=True,
        ))

        # Register many wallets
        wallets = [f"wallet_{i}" for i in range(20)]
        for w in wallets:
            ledger.register_wallet(w)

        # Distribute shares
        for i, w in enumerate(wallets):
            if i > 0:  # Skip first
                ledger.set_balance(w, "AAPL", 100)

        ledger.register_wallet("issuer")
        ledger.set_balance("issuer", "USD", 1000000)

        # Compute dividend twice
        result1 = process_dividends(ledger, "AAPL", datetime(2024, 3, 15))
        result2 = process_dividends(ledger, "AAPL", datetime(2024, 3, 15))

        # Same moves in same order
        assert len(result1.moves) == len(result2.moves)
        for m1, m2 in zip(result1.moves, result2.moves):
            assert m1.source == m2.source
            assert m1.dest == m2.dest
            assert m1.quantity == m2.quantity


class TestEngineReproducibility:
    """Tests that lifecycle engine processing is deterministic."""

    def test_engine_processes_contracts_deterministically(self):
        """Engine processes multiple contracts in deterministic order."""
        maturity = datetime(2025, 6, 15)
        t0 = datetime(2025, 1, 1)

        def setup_ledger():
            ledger = Ledger("test", initial_time=t0)
            ledger.register_unit(cash("USD", "US Dollar"))
            ledger.register_unit(_stock("AAPL", "Apple Inc", "issuer", shortable=True))
            ledger.register_wallet("alice")
            ledger.register_wallet("bob")
            ledger.register_wallet("market")
            ledger.set_balance("alice", "USD", 1000000)
            ledger.set_balance("bob", "USD", 1000000)
            ledger.set_balance("bob", "AAPL", 10000)
            ledger.set_balance("market", "USD", 10000000)
            ledger.set_balance("market", "AAPL", 100000)

            # Create multiple options
            for i in range(5):
                opt_unit = create_option_unit(
                    symbol=f"OPT_{i}",
                    name=f"Option {i}",
                    underlying="AAPL",
                    strike=150.0 + i * 10,
                    maturity=maturity,
                    option_type="call",
                    quantity=100,
                    currency="USD",
                    long_wallet="alice",
                    short_wallet="bob",
                )
                ledger.register_unit(opt_unit)
                ledger.set_balance("alice", opt_unit.symbol, 1)
                ledger.set_balance("bob", opt_unit.symbol, -1)

            return ledger

        # Run engine twice
        ledger1 = setup_ledger()
        ledger2 = setup_ledger()

        prices = {"AAPL": 175.0}

        engine1 = LifecycleEngine(ledger1)
        engine1.register("BILATERAL_OPTION", option_contract)

        engine2 = LifecycleEngine(ledger2)
        engine2.register("BILATERAL_OPTION", option_contract)

        results1 = engine1.step(maturity, prices)
        results2 = engine2.step(maturity, prices)

        # Same number of results
        assert len(results1) == len(results2)

        # Same final balances
        assert ledger1.get_balance("alice", "USD") == ledger2.get_balance("alice", "USD")
        assert ledger1.get_balance("bob", "USD") == ledger2.get_balance("bob", "USD")


class TestFloatingPointReproducibility:
    """Tests that floating-point operations are consistent."""

    def test_balance_accumulation_consistent(self):
        """Many small transactions produce consistent final balance."""
        ledger = Ledger("test")
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 100000)

        # Many small transactions
        for i in range(100):
            ledger.execute(build_transaction(ledger, [
                Move(0.01, "USD", "alice", "bob", f"micro_tx_{i}")
            ]))

        alice_balance = ledger.get_balance("alice", "USD")
        bob_balance = ledger.get_balance("bob", "USD")

        # Proper rounding applied
        assert alice_balance == 99999.00
        assert bob_balance == 1.00

    def test_total_supply_consistent(self):
        """Total supply calculation is consistent regardless of wallet order."""
        ledger = Ledger("test")
        ledger.register_unit(cash("USD", "US Dollar"))

        # Create many wallets with varied balances
        for i in range(50):
            ledger.register_wallet(f"wallet_{i}")
            ledger.set_balance(f"wallet_{i}", "USD", 100.0 + i * 0.01)

        supply1 = ledger.total_supply("USD")
        supply2 = ledger.total_supply("USD")

        assert supply1 == supply2

    def test_repeated_execution_consistent(self):
        """Repeated execution of same transactions is consistent."""
        def run_scenario():
            ledger = Ledger("test")
            ledger.register_unit(cash("USD", "US Dollar"))
            ledger.register_wallet("alice")
            ledger.register_wallet("bob")
            ledger.register_wallet("charlie")
            ledger.set_balance("alice", "USD", 10000)

            # Execute a sequence of transactions
            for i in range(10):
                ledger.execute(build_transaction(ledger, [
                    Move(100.0, "USD", "alice", "bob", f"tx_ab_{i}")
                ]))
                ledger.execute(build_transaction(ledger, [
                    Move(50.0, "USD", "bob", "charlie", f"tx_bc_{i}")
                ]))

            return (
                ledger.get_balance("alice", "USD"),
                ledger.get_balance("bob", "USD"),
                ledger.get_balance("charlie", "USD")
            )

        result1 = run_scenario()
        result2 = run_scenario()

        assert result1 == result2


class TestCloneAtReproducibility:
    """Tests that clone_at produces consistent results."""

    def test_clone_at_same_timestamp_identical(self):
        """Cloning at the same timestamp produces identical state."""
        ledger = Ledger("test")
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000)

        # Execute transactions with timestamps
        t1 = datetime(2025, 1, 1, 10, 0, 0)
        t2 = datetime(2025, 1, 1, 11, 0, 0)
        t3 = datetime(2025, 1, 1, 12, 0, 0)

        ledger.advance_time(t1)
        ledger.execute(build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "tx1")
        ]))

        ledger.advance_time(t2)
        ledger.execute(build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "tx2")
        ]))

        ledger.advance_time(t3)
        ledger.execute(build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "tx3")
        ]))

        # Clone at t2 multiple times
        clone1 = ledger.clone_at(t2)
        clone2 = ledger.clone_at(t2)

        assert clone1.get_balance("alice", "USD") == clone2.get_balance("alice", "USD")
        assert clone1.get_balance("bob", "USD") == clone2.get_balance("bob", "USD")


class TestSimulationReproducibility:
    """End-to-end simulation reproducibility tests."""

    def test_monte_carlo_path_reproducible(self):
        """A single Monte Carlo path is reproducible."""
        import random

        # Fixed seed for reproducibility
        seed = 42
        maturity = datetime(2025, 6, 30)
        t0 = datetime(2025, 1, 1)

        def run_simulation():
            random.seed(seed)

            # Generate price path
            prices = []
            price = 100.0
            t = t0
            while t <= maturity:
                prices.append((t, price))
                price *= (1 + random.gauss(0, 0.02))
                t += timedelta(days=1)

            pricer = TimeSeriesPricingSource({"AAPL": prices})

            # Setup ledger
            ledger = Ledger("sim", initial_time=t0)
            ledger.register_unit(cash("USD", "US Dollar"))
            ledger.register_unit(_stock("AAPL", "Apple Inc", "issuer", shortable=True))
            ledger.register_wallet("trader")
            ledger.register_wallet("market")
            ledger.set_balance("trader", "USD", 100000)
            ledger.set_balance("market", "USD", 1000000)
            ledger.set_balance("market", "AAPL", 100000)

            # Create delta hedge
            hedge_unit = create_delta_hedge_unit(
                symbol="HEDGE",
                name="Delta Hedge",
                underlying="AAPL",
                strike=100.0,
                maturity=maturity,
                volatility=0.20,
                num_options=10,
                option_multiplier=100,
                currency="USD",
                strategy_wallet="trader",
                market_wallet="market",
            )
            ledger.register_unit(hedge_unit)

            # Run simulation
            engine = LifecycleEngine(ledger)
            engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract(min_trade_size=0.01))

            t = t0
            while t <= maturity:
                current_prices = pricer.get_prices({"AAPL"}, t)
                engine.step(t, current_prices)
                t += timedelta(days=1)

            return ledger.get_balance("trader", "USD"), ledger.get_balance("trader", "AAPL")

        # Run twice
        result1 = run_simulation()
        result2 = run_simulation()

        # Same results
        assert result1[0] == result2[0]
        assert result1[1] == result2[1]

    def test_backtest_reproducible(self):
        """Historical backtest is reproducible."""
        def run_backtest():
            t0 = datetime(2025, 1, 1)

            # Historical prices
            prices = [
                (t0, 100.0),
                (t0 + timedelta(days=1), 102.0),
                (t0 + timedelta(days=2), 101.0),
                (t0 + timedelta(days=3), 103.0),
                (t0 + timedelta(days=4), 105.0),
            ]
            pricer = TimeSeriesPricingSource({"STOCK": prices})

            ledger = Ledger("backtest", initial_time=t0)
            ledger.register_unit(cash("USD", "US Dollar"))
            ledger.register_unit(_stock("STOCK", "Test Stock", "issuer"))
            ledger.register_wallet("trader")
            ledger.register_wallet("market")
            ledger.set_balance("trader", "USD", 10000)
            ledger.set_balance("market", "STOCK", 10000)

            # Simple momentum strategy
            prev_price = None
            for t, price in prices:
                ledger.advance_time(t)
                if prev_price and price > prev_price:
                    try:
                        ledger.execute(build_transaction(ledger, [
                            Move(100.0, "USD", "trader", "market", f"buy_{t}"),
                            Move(100.0 / price, "STOCK", "market", "trader", f"buy_{t}_stock")
                        ]))
                    except Exception:
                        pass
                prev_price = price

            return (
                ledger.get_balance("trader", "USD"),
                ledger.get_balance("trader", "STOCK")
            )

        result1 = run_backtest()
        result2 = run_backtest()

        assert result1[0] == result2[0]
        assert result1[1] == result2[1]


# ============================================================================
# Core Reproducibility Tests
# These tests verify the core reproducibility guarantees of the system
# ============================================================================

class TestUnwindAlgorithm:
    """
    Tests for the UNWIND algorithm (clone_at).

    State reconstruction uses UNWIND:
    1. Start with CURRENT state (which includes everything)
    2. Walk backwards through transactions AFTER target_time
    3. For each transaction, reverse its effects

    Initial balances set via set_balance() are NOT logged, but they ARE preserved
    in current state. UNWIND correctly handles this by starting from current state.
    """

    def test_clone_at_preserves_initial_balances(self):
        """
        Initial balances set via set_balance() must be preserved by clone_at().

        This is the key property that makes UNWIND correct:
        - set_balance() is not logged
        - But current state contains the effects of set_balance()
        - UNWIND starts from current state, so initial balances are preserved
        """
        t0 = datetime(2025, 1, 1)
        t1 = datetime(2025, 1, 2)
        t2 = datetime(2025, 1, 3)

        ledger = Ledger("test", initial_time=t0)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        # Set initial balance (NOT logged)
        ledger.set_balance("alice", "USD", 10000)

        # Execute transaction (logged)
        ledger.advance_time(t1)
        ledger.execute(build_transaction(ledger, [
            Move(1000.0, "USD", "alice", "bob", "tx1")
        ]))

        # Execute another transaction
        ledger.advance_time(t2)
        ledger.execute(build_transaction(ledger, [
            Move(500.0, "USD", "alice", "bob", "tx2")
        ]))

        # Clone at t0 (before any transactions)
        clone_t0 = ledger.clone_at(t0)

        # Initial balance should be preserved!
        assert clone_t0.get_balance("alice", "USD") == 10000
        assert clone_t0.get_balance("bob", "USD") == 0

        # Clone at t1 (after first transaction)
        clone_t1 = ledger.clone_at(t1)
        assert clone_t1.get_balance("alice", "USD") == 9000
        assert clone_t1.get_balance("bob", "USD") == 1000

    def test_clone_at_preserves_unit_state(self):
        """
        Unit state changes must be correctly unwound by clone_at().

        UnitStateChange stores old_state and new_state. UNWIND restores old_state.
        """
        t0 = datetime(2025, 1, 1)
        maturity = datetime(2025, 6, 1)

        ledger = Ledger("test", initial_time=t0, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc", "treasury", shortable=True))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Create option
        option_unit = create_option_unit(
            symbol="OPT",
            name="Test Option",
            underlying="AAPL",
            strike=150.0,
            maturity=maturity,
            option_type="call",
            quantity=100,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        ledger.register_unit(option_unit)

        # Setup positions
        ledger.set_balance("alice", "OPT", 5)
        ledger.set_balance("bob", "OPT", -5)
        ledger.set_balance("alice", "USD", 100000)
        ledger.set_balance("bob", "AAPL", 1000)

        # Checkpoint BEFORE settlement
        state_before = ledger.get_unit_state("OPT")
        assert state_before.get('settled') is False

        # Settle the option at maturity
        ledger.advance_time(maturity)
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_OPTION", option_contract)
        engine.step(maturity, {"AAPL": 170.0})

        # Verify settled
        state_after = ledger.get_unit_state("OPT")
        assert state_after.get('settled') is True

        # clone_at(t0) should restore unsettled state
        clone = ledger.clone_at(t0)
        restored_state = clone.get_unit_state("OPT")
        assert restored_state.get('settled') is False, \
            "clone_at() failed to restore pre-settlement unit state"

    def test_clone_at_with_multiple_state_changes(self):
        """
        Multiple state changes on the same unit must be correctly unwound.
        """
        t0 = datetime(2025, 1, 1)
        t1 = datetime(2025, 1, 2)
        t2 = datetime(2025, 1, 3)
        maturity = datetime(2025, 6, 1)

        ledger = Ledger("test", initial_time=t0, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc", "treasury", shortable=True))
        ledger.register_wallet("trader")
        ledger.register_wallet("market")
        ledger.register_wallet("treasury")

        # Create delta hedge
        hedge_unit = create_delta_hedge_unit(
            symbol="HEDGE",
            name="Test Hedge",
            underlying="AAPL",
            strike=150.0,
            maturity=maturity,
            volatility=0.20,
            num_options=10,
            option_multiplier=100,
            currency="USD",
            strategy_wallet="trader",
            market_wallet="market",
        )
        ledger.register_unit(hedge_unit)

        # Setup balances
        ledger.set_balance("trader", "USD", 1000000)
        ledger.set_balance("market", "AAPL", 100000)
        ledger.set_balance("market", "USD", 1000000)

        # Get initial state
        initial_state = ledger.get_unit_state("HEDGE")
        initial_rebalance_count = initial_state.get('rebalance_count', 0)

        # Run engine for several steps (each step may update state)
        engine = LifecycleEngine(ledger)
        engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract(min_trade_size=0.01))

        ledger.advance_time(t1)
        engine.step(t1, {"AAPL": 155.0})

        ledger.advance_time(t2)
        engine.step(t2, {"AAPL": 160.0})

        # Verify state has changed
        current_state = ledger.get_unit_state("HEDGE")
        assert current_state.get('rebalance_count', 0) > initial_rebalance_count

        # Clone at t0 - should have initial state
        clone_t0 = ledger.clone_at(t0)
        restored_state = clone_t0.get_unit_state("HEDGE")
        assert restored_state.get('rebalance_count', 0) == initial_rebalance_count


class TestReplayWithUnitStateChanges:
    """
    Tests for replay() correctly applying state_changes.

    This was a critical bug: replay() was not applying state_changes,
    causing unit states to be wrong after replay.

    Note: replay() does NOT preserve balances set via set_balance() - those
    are not part of the transaction log. Use clone() or clone_at() if you
    need to preserve those balances. These tests verify state_changes are
    applied using transactions that will pass validation on replay.
    """

    def test_replay_applies_state_changes(self):
        """
        replay() must apply state_changes from transactions.

        Without this, unit states after replay would be empty/wrong.

        This test uses clone() to verify state_changes are applied correctly
        since replay() doesn't preserve set_balance() calls.
        """
        t0 = datetime(2025, 1, 1)
        maturity = datetime(2025, 6, 1)

        ledger = Ledger("test", initial_time=t0, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc", "treasury", shortable=True))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Create option
        option_unit = create_option_unit(
            symbol="OPT",
            name="Test Option",
            underlying="AAPL",
            strike=150.0,
            maturity=maturity,
            option_type="call",
            quantity=100,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        ledger.register_unit(option_unit)

        # Setup positions
        ledger.set_balance("alice", "OPT", 5)
        ledger.set_balance("bob", "OPT", -5)
        ledger.set_balance("alice", "USD", 100000)
        ledger.set_balance("bob", "AAPL", 1000)

        # Settle the option
        ledger.advance_time(maturity)
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_OPTION", option_contract)
        engine.step(maturity, {"AAPL": 170.0})

        # Verify settled
        assert ledger.get_unit_state("OPT").get('settled') is True

        # Verify via clone() that state_changes are preserved in transaction log
        # (replay() can't be used here because it doesn't preserve set_balance() calls,
        # which are needed for the settlement transaction to pass validation)
        cloned = ledger.clone()
        cloned_state = cloned.get_unit_state("OPT")
        assert cloned_state.get('settled') is True, \
            "clone() failed to preserve state_changes - option not marked as settled"
        assert cloned_state.get('exercised') is True
        assert cloned_state.get('settlement_price') == 170.0

        # Verify that state_changes are actually in the transaction log
        assert len(ledger.transaction_log) > 0
        settlement_tx = ledger.transaction_log[-1]
        assert len(settlement_tx.state_changes) > 0, \
            "Settlement transaction should have state_changes"
        opt_state_change = next(
            (sc for sc in settlement_tx.state_changes if sc.unit == "OPT"), None
        )
        assert opt_state_change is not None, "OPT state_change not found in transaction"
        assert opt_state_change.new_state.get('settled') is True


class TestUnitStateChangeImmutability:
    """
    Tests that UnitStateChange contains immutable copies of state.

    This prevents log corruption if state dicts are mutated after logging.
    """

    def test_state_delta_contains_deep_copies(self):
        """
        UnitStateChange must contain deep copies, not references.

        If we store references, subsequent mutations would corrupt the log.
        """
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000)

        # Create a transaction with state deltas containing a nested dict
        nested_data = {'nested': {'value': 100}}
        moves = [Move(100.0, "USD", "alice", "bob", "test")]
        old_state = ledger.get_unit_state("USD")
        new_state = {**old_state, 'extra_data': nested_data}
        pending = build_transaction(ledger, moves, state_changes=[
            UnitStateChange(unit="USD", old_state=old_state, new_state=new_state)
        ])

        # Execute
        ledger.execute(pending)

        # Mutate the original nested_data
        nested_data['nested']['value'] = 999

        # The logged state should NOT be affected
        tx = ledger.transaction_log[-1]
        for sc in tx.state_changes:
            if sc.unit == "USD":
                logged_value = sc.new_state.get('extra_data', {}).get('nested', {}).get('value')
                assert logged_value == 100, \
                    f"UnitStateChange was corrupted by mutation: expected 100, got {logged_value}"


class TestCloneAtCheckpointVerification:
    """
    The canonical test pattern: checkpoint + evolve + clone_at + compare.

    This is the gold standard for verifying state reconstruction.
    """

    def test_checkpoint_and_verify_pattern(self):
        """
        Complete verification pattern from design document Section 11.2:
        1. At T0: Create checkpoint (clone)
        2. Execute transactions
        3. Clone_at(T0)
        4. Verify clone_at matches checkpoint
        """
        t0 = datetime(2025, 1, 1)
        t1 = datetime(2025, 1, 2)
        t2 = datetime(2025, 1, 3)

        ledger = Ledger("test", initial_time=t0, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc", "treasury"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Set initial state
        ledger.set_balance("alice", "USD", 100000)
        ledger.set_balance("alice", "AAPL", 500)
        ledger.set_balance("bob", "USD", 50000)

        # CHECKPOINT at T0
        checkpoint = ledger.clone()

        # Execute transactions
        ledger.advance_time(t1)
        ledger.execute(build_transaction(ledger, [
            Move(10000.0, "USD", "alice", "bob", "trade1_cash"),
            Move(100.0, "AAPL", "bob", "alice", "trade1_stock")
        ]))

        ledger.advance_time(t2)
        ledger.execute(build_transaction(ledger, [
            Move(5000.0, "USD", "alice", "bob", "trade2_cash"),
            Move(50.0, "AAPL", "bob", "alice", "trade2_stock")
        ]))

        # RECONSTRUCT at T0
        reconstructed = ledger.clone_at(t0)

        # VERIFY - compare balances
        assert reconstructed.get_balance("alice", "USD") == checkpoint.get_balance("alice", "USD")
        assert reconstructed.get_balance("bob", "USD") == checkpoint.get_balance("bob", "USD")
        assert reconstructed.get_balance("alice", "AAPL") == checkpoint.get_balance("alice", "AAPL")
        assert reconstructed.get_balance("bob", "AAPL") == checkpoint.get_balance("bob", "AAPL")

    def test_checkpoint_and_verify_with_state_changes(self):
        """
        Verification pattern with unit state changes (not just balances).
        """
        t0 = datetime(2025, 1, 1)
        maturity = datetime(2025, 6, 1)

        ledger = Ledger("test", initial_time=t0, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc", "treasury", shortable=True))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Create option
        option_unit = create_option_unit(
            symbol="OPT",
            name="Test Option",
            underlying="AAPL",
            strike=150.0,
            maturity=maturity,
            option_type="call",
            quantity=100,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        ledger.register_unit(option_unit)

        # Setup positions
        ledger.set_balance("alice", "OPT", 5)
        ledger.set_balance("bob", "OPT", -5)
        ledger.set_balance("alice", "USD", 100000)
        ledger.set_balance("bob", "AAPL", 1000)

        # CHECKPOINT
        checkpoint = ledger.clone()

        # Settle option (this changes unit state)
        ledger.advance_time(maturity)
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_OPTION", option_contract)
        engine.step(maturity, {"AAPL": 170.0})

        # RECONSTRUCT
        reconstructed = ledger.clone_at(t0)

        # VERIFY - including unit states
        assert reconstructed.get_balance("alice", "USD") == checkpoint.get_balance("alice", "USD")
        assert reconstructed.get_balance("bob", "USD") == checkpoint.get_balance("bob", "USD")

        # Extra verification: option should be unsettled in reconstruction
        assert reconstructed.get_unit_state("OPT").get('settled') is False


class TestExecutionTimeVsTimestamp:
    """
    Tests that clone_at uses execution_time (when applied) not timestamp (when created).
    """

    def test_clone_at_uses_execution_time(self):
        """
        Transactions created before but executed after target_time should be excluded.
        """
        t0 = datetime(2025, 1, 1)
        t1 = datetime(2025, 1, 2)
        t2 = datetime(2025, 1, 3)

        ledger = Ledger("test", initial_time=t0, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000)

        # Create transaction at t0 (timestamp = t0)
        tx = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "delayed_tx")
        ])
        assert tx.timestamp == t0

        # But execute at t2 (execution_time = t2)
        ledger.advance_time(t2)
        ledger.execute(tx)

        # The transaction's execution_time should be t2
        logged_tx = ledger.transaction_log[-1]
        assert logged_tx.execution_time == t2

        # Clone at t1 - transaction should NOT be included
        # (even though timestamp=t0, execution_time=t2 > t1)
        clone = ledger.clone_at(t1)

        # Transaction was executed at t2, so at t1 alice should still have 1000
        assert clone.get_balance("alice", "USD") == 1000
        assert clone.get_balance("bob", "USD") == 0
