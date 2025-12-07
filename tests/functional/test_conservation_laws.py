"""
test_conservation_laws.py - Functional tests for conservation invariants

Tests the fundamental invariant:
    For every unit, at all times: Σ(balances across all wallets) = constant

Conservation must be maintained:
- After single transfers
- After multi-move transactions
- After many random transactions
- With rounding operations
- After dividends, settlements, and lifecycle events
"""

import pytest
import random
from datetime import datetime, timedelta
from ledger import (
    Ledger, Move, ContractResult,
    cash,
    create_stock_unit,
    create_option_unit,
    create_forward_unit,
    create_delta_hedge_unit,
    LifecycleEngine,
    stock_contract,
    option_contract,
    forward_contract,
    delta_hedge_contract,
    compute_scheduled_dividend,
    compute_option_settlement,
    TimeSeriesPricingSource,
)


def total_supply(ledger: Ledger, unit: str) -> float:
    """Calculate total supply of a unit across all wallets."""
    return ledger.total_supply(unit)


def verify_all_units_conserved(ledger: Ledger, expected_supplies: dict, tolerance: float = 1e-9) -> bool:
    """Verify all units have expected total supply."""
    for unit, expected in expected_supplies.items():
        actual = total_supply(ledger, unit)
        if abs(actual - expected) > tolerance:
            return False
    return True


class TestBasicConservation:
    """Basic conservation tests for simple transfers."""

    def test_simple_transfer_conserves(self):
        """Single transfer conserves total supply."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        # Initial supply
        ledger.set_balance("alice", "USD", 1000.0)
        initial_supply = total_supply(ledger, "USD")

        # Transfer
        tx = ledger.create_transaction([
            Move("alice", "bob", "USD", 100.0, "payment")
        ])
        ledger.execute(tx)

        # Conservation check
        final_supply = total_supply(ledger, "USD")
        assert abs(final_supply - initial_supply) < 1e-9

    def test_multi_move_conserves(self):
        """Multi-move transaction conserves total supply."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Initial supplies
        ledger.set_balance("alice", "USD", 10000.0)
        ledger.set_balance("bob", "AAPL", 100.0)
        initial_usd = total_supply(ledger, "USD")
        initial_aapl = total_supply(ledger, "AAPL")

        # Trade
        tx = ledger.create_transaction([
            Move("alice", "bob", "USD", 1500.0, "trade"),
            Move("bob", "alice", "AAPL", 10.0, "trade"),
        ])
        ledger.execute(tx)

        # Conservation check
        assert abs(total_supply(ledger, "USD") - initial_usd) < 1e-9
        assert abs(total_supply(ledger, "AAPL") - initial_aapl) < 1e-9

    def test_many_transactions_conserve(self):
        """Many random transactions conserve total supply."""
        random.seed(42)

        ledger = Ledger("test", verbose=False, fast_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        # Create many wallets
        wallets = [f"wallet_{i}" for i in range(20)]
        for w in wallets:
            ledger.register_wallet(w)

        # Initial distribution
        for w in wallets:
            ledger.set_balance(w, "USD", 10000.0)
            ledger.set_balance(w, "AAPL", 100.0)

        initial_usd = total_supply(ledger, "USD")
        initial_aapl = total_supply(ledger, "AAPL")

        # Execute many random transactions
        for i in range(1000):
            source = random.choice(wallets)
            dest = random.choice([w for w in wallets if w != source])
            unit = random.choice(["USD", "AAPL"])
            amount = random.uniform(0.01, 10.0)

            tx = ledger.create_transaction([
                Move(source, dest, unit, amount, f"tx_{i}")
            ])
            ledger.execute(tx)

        # Conservation check
        assert abs(total_supply(ledger, "USD") - initial_usd) < 1e-6
        assert abs(total_supply(ledger, "AAPL") - initial_aapl) < 1e-6


class TestConservationWithRounding:
    """Conservation tests with rounding operations."""

    def test_rounding_conserves(self):
        """Rounding doesn't leak or create value."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.set_balance("alice", "USD", 100.0)
        initial_supply = total_supply(ledger, "USD")

        # Many small transactions that require rounding
        for i in range(100):
            tx = ledger.create_transaction([
                Move("alice", "bob", "USD", 0.01, f"micro_{i}")
            ])
            ledger.execute(tx)

        # Verify conservation
        final_supply = total_supply(ledger, "USD")
        assert abs(final_supply - initial_supply) < 1e-9

    def test_fractional_transfers_conserve(self):
        """Fractional amounts conserve."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("charlie")

        ledger.set_balance("alice", "USD", 1000.0)
        initial_supply = total_supply(ledger, "USD")

        # Transfer with rounding
        tx1 = ledger.create_transaction([
            Move("alice", "bob", "USD", 333.33, "split1")
        ])
        ledger.execute(tx1)

        tx2 = ledger.create_transaction([
            Move("alice", "charlie", "USD", 333.33, "split2")
        ])
        ledger.execute(tx2)

        # Verify conservation
        final_supply = total_supply(ledger, "USD")
        assert abs(final_supply - initial_supply) < 1e-9


class TestConservationWithDividends:
    """Conservation tests for dividend payments."""

    def test_dividend_payment_conserves(self):
        """Dividend payment conserves total USD."""
        ledger = Ledger("test", datetime(2025, 3, 15), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        schedule = [(datetime(2025, 3, 15), 0.25)]
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD",
            dividend_schedule=schedule, shortable=True
        ))

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("alice", "AAPL", 1000)
        ledger.set_balance("bob", "AAPL", 500)
        ledger.set_balance("treasury", "USD", 10000000)

        initial_usd = total_supply(ledger, "USD")
        initial_aapl = total_supply(ledger, "AAPL")

        # Process dividend
        result = compute_scheduled_dividend(ledger, "AAPL", datetime(2025, 3, 15))
        ledger.execute_contract(result)

        # Conservation check - USD and AAPL should be conserved
        assert abs(total_supply(ledger, "USD") - initial_usd) < 1e-9
        assert abs(total_supply(ledger, "AAPL") - initial_aapl) < 1e-9

    def test_multiple_dividends_conserve(self):
        """Multiple dividend payments conserve."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        schedule = [
            (datetime(2025, 3, 15), 0.25),
            (datetime(2025, 6, 15), 0.25),
            (datetime(2025, 9, 15), 0.25),
            (datetime(2025, 12, 15), 0.25),
        ]
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD",
            dividend_schedule=schedule, shortable=True
        ))

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("alice", "AAPL", 1000)
        ledger.set_balance("bob", "AAPL", 500)
        ledger.set_balance("treasury", "USD", 10000000)

        initial_usd = total_supply(ledger, "USD")

        # Process all dividends
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)

        for date in [datetime(2025, 3, 15), datetime(2025, 6, 15),
                     datetime(2025, 9, 15), datetime(2025, 12, 15)]:
            ledger.advance_time(date)
            engine.step(date, {"AAPL": 150.0})

        # Conservation check
        assert abs(total_supply(ledger, "USD") - initial_usd) < 1e-9


class TestConservationWithOptions:
    """Conservation tests for option settlements."""

    def test_option_settlement_conserves(self):
        """Option settlement conserves underlying and cash."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        option = create_option_unit(
            "AAPL_C150", "AAPL Call", "AAPL", 150.0,
            datetime(2025, 6, 20), "call", 100, "USD", "alice", "bob"
        )
        ledger.register_unit(option)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("alice", "AAPL_C150", 5)
        ledger.set_balance("bob", "AAPL_C150", -5)
        ledger.set_balance("alice", "USD", 100000)
        ledger.set_balance("bob", "AAPL", 1000)

        initial_usd = total_supply(ledger, "USD")
        initial_aapl = total_supply(ledger, "AAPL")

        # Settle at maturity
        ledger.advance_time(datetime(2025, 6, 20))
        result = compute_option_settlement(ledger, "AAPL_C150", 170.0)
        ledger.execute_contract(result)

        # Conservation check
        assert abs(total_supply(ledger, "USD") - initial_usd) < 1e-9
        assert abs(total_supply(ledger, "AAPL") - initial_aapl) < 1e-9


class TestConservationWithDeltaHedge:
    """Conservation tests for delta hedge strategies."""

    def test_delta_hedge_rebalancing_conserves(self):
        """Delta hedge rebalancing conserves all units."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        hedge = create_delta_hedge_unit(
            "HEDGE", "Test Hedge", "AAPL", 150.0,
            datetime(2025, 6, 20), 0.25, 10, 100, "USD",
            "trader", "market", 0.0
        )
        ledger.register_unit(hedge)

        ledger.register_wallet("trader")
        ledger.register_wallet("market")
        ledger.register_wallet("treasury")

        ledger.set_balance("trader", "USD", 500000)
        ledger.set_balance("market", "USD", 10000000)
        ledger.set_balance("market", "AAPL", 100000)

        initial_usd = total_supply(ledger, "USD")
        initial_aapl = total_supply(ledger, "AAPL")

        # Generate price path
        prices = [(datetime(2025, 1, 1) + timedelta(days=i), 150 + i * 0.5)
                  for i in range(30)]
        pricing = TimeSeriesPricingSource({"AAPL": prices}, "USD")

        # Run engine
        engine = LifecycleEngine(ledger)
        engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract(min_trade_size=0.01))

        for date, price in prices:
            ledger.advance_time(date)
            engine.step(date, {"AAPL": price})

        # Conservation check
        assert abs(total_supply(ledger, "USD") - initial_usd) < 1e-6
        assert abs(total_supply(ledger, "AAPL") - initial_aapl) < 1e-6


class TestConservationInMonteCarloMode:
    """Conservation tests in Monte Carlo mode."""

    def test_fast_mode_conserves(self):
        """fast_mode=True still conserves."""
        ledger = Ledger("test", verbose=False, fast_mode=True, no_log=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        wallets = [f"w_{i}" for i in range(10)]
        for w in wallets:
            ledger.register_wallet(w)
            ledger.set_balance(w, "USD", 10000)
            ledger.set_balance(w, "AAPL", 100)

        initial_usd = total_supply(ledger, "USD")
        initial_aapl = total_supply(ledger, "AAPL")

        # Many fast transactions
        random.seed(123)
        for i in range(10000):
            src = random.choice(wallets)
            dst = random.choice([w for w in wallets if w != src])
            unit = random.choice(["USD", "AAPL"])
            amt = random.uniform(0.01, 5.0)

            tx = ledger.create_transaction([Move(src, dst, unit, amt, f"tx_{i}")])
            ledger.execute(tx)

        # Conservation check
        assert abs(total_supply(ledger, "USD") - initial_usd) < 1e-4
        assert abs(total_supply(ledger, "AAPL") - initial_aapl) < 1e-4


class TestPositionSumEqualsSupply:
    """Verify position sum equals total supply."""

    def test_position_sum_matches_supply(self):
        """Sum of get_positions equals total_supply."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        wallets = ["alice", "bob", "charlie", "treasury"]
        for w in wallets:
            ledger.register_wallet(w)

        ledger.set_balance("alice", "USD", 1000)
        ledger.set_balance("bob", "USD", -500)  # Short
        ledger.set_balance("charlie", "USD", 2000)
        ledger.set_balance("treasury", "AAPL", 10000)
        ledger.set_balance("alice", "AAPL", 100)

        # Verify position sum equals supply
        usd_positions = ledger.get_positions("USD")
        usd_sum = sum(usd_positions.values())
        assert abs(usd_sum - total_supply(ledger, "USD")) < 1e-9

        aapl_positions = ledger.get_positions("AAPL")
        aapl_sum = sum(aapl_positions.values())
        assert abs(aapl_sum - total_supply(ledger, "AAPL")) < 1e-9
