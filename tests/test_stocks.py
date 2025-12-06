"""
Tests for stocks.py - Stock Contracts with Dividend Scheduling

Tests:
- create_stock_unit factory (creates stock units with dividend schedules)
- compute_scheduled_dividend (processes dividend payments on payment dates)
- stock_contract lifecycle integration (automated dividend processing via LifecycleEngine)

Dividend schedule format: list of (payment_date, dividend_per_share) tuples.
"""

import pytest
from datetime import datetime, timedelta

from ledger import (
    Ledger, cash,
    create_stock_unit,
    compute_scheduled_dividend,
    stock_contract,
    LifecycleEngine,
)


# ============================================================================
# create_stock_unit Tests
# ============================================================================

class TestCreateStockUnit:
    """Tests for create_stock_unit factory."""

    def test_create_stock_unit_basic(self):
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
        )

        assert unit.symbol == "AAPL"
        assert unit.name == "Apple Inc."
        assert unit.unit_type == "STOCK"
        assert unit.min_balance == 0.0  # Not shortable

    def test_create_stock_unit_shortable(self):
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            shortable=True,
        )

        assert unit.min_balance < 0  # Shortable

    def test_create_stock_unit_with_schedule(self):
        schedule = [
            (datetime(2024, 3, 15), 0.25),
            (datetime(2024, 6, 15), 0.25),
            (datetime(2024, 9, 15), 0.25),
            (datetime(2024, 12, 15), 0.25),
        ]
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            dividend_schedule=schedule,
        )

        assert unit._state['next_payment_index'] == 0
        assert len(unit._state['dividend_schedule']) == 4

    def test_create_stock_unit_no_schedule(self):
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
        )

        assert unit._state['dividend_schedule'] == []
        assert unit._state['paid_dividends'] == []


# ============================================================================
# compute_scheduled_dividend Tests
# ============================================================================

class TestComputeScheduledDividend:
    """Tests for compute_scheduled_dividend function."""

    @pytest.fixture
    def setup_ledger(self):
        """Create a test ledger with stock and shareholders."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        treasury = ledger.register_wallet("treasury")
        alice = ledger.register_wallet("alice")
        bob = ledger.register_wallet("bob")

        # Fund treasury
        ledger.set_balance(treasury, "USD", 1_000_000)

        return ledger

    def test_dividend_payment_on_date(self, setup_ledger):
        ledger = setup_ledger

        schedule = [
            (datetime(2024, 3, 29), 0.25),
        ]
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            dividend_schedule=schedule,
        )
        ledger.register_unit(unit)

        # Distribute shares
        ledger.set_balance("alice", "AAPL", 1000)
        ledger.set_balance("bob", "AAPL", 500)

        # Advance to payment date
        ledger.advance_time(datetime(2024, 3, 29))

        result = compute_scheduled_dividend(ledger, "AAPL", datetime(2024, 3, 29))

        assert not result.is_empty()
        assert len(result.moves) == 2  # Alice and Bob

        # Check amounts
        alice_move = next(m for m in result.moves if m.dest == "alice")
        bob_move = next(m for m in result.moves if m.dest == "bob")

        assert alice_move.quantity == 250.0  # 1000 * 0.25
        assert bob_move.quantity == 125.0   # 500 * 0.25

    def test_dividend_before_payment_date_returns_empty(self, setup_ledger):
        ledger = setup_ledger

        schedule = [
            (datetime(2024, 3, 29), 0.25),
        ]
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            dividend_schedule=schedule,
        )
        ledger.register_unit(unit)

        ledger.set_balance("alice", "AAPL", 1000)

        # Before payment date
        result = compute_scheduled_dividend(ledger, "AAPL", datetime(2024, 3, 28))

        assert result.is_empty()

    def test_dividend_updates_state(self, setup_ledger):
        ledger = setup_ledger

        schedule = [
            (datetime(2024, 3, 29), 0.25),
            (datetime(2024, 6, 29), 0.25),
        ]
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            dividend_schedule=schedule,
        )
        ledger.register_unit(unit)

        ledger.set_balance("alice", "AAPL", 1000)
        ledger.advance_time(datetime(2024, 3, 29))

        result = compute_scheduled_dividend(ledger, "AAPL", datetime(2024, 3, 29))

        # Check state updates
        assert "AAPL" in result.state_updates
        updates = result.state_updates["AAPL"]
        assert updates['next_payment_index'] == 1
        assert len(updates['paid_dividends']) == 1

    def test_schedule_exhausted_returns_empty(self, setup_ledger):
        ledger = setup_ledger

        schedule = [
            (datetime(2024, 3, 29), 0.25),
        ]
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            dividend_schedule=schedule,
        )
        ledger.register_unit(unit)

        ledger.set_balance("alice", "AAPL", 1000)
        ledger.advance_time(datetime(2024, 3, 29))

        # First dividend
        result1 = compute_scheduled_dividend(ledger, "AAPL", datetime(2024, 3, 29))
        ledger.execute_contract(result1)

        # Try second dividend (should be empty)
        result2 = compute_scheduled_dividend(ledger, "AAPL", datetime(2024, 6, 29))
        assert result2.is_empty()

    def test_issuer_excluded_from_dividend(self, setup_ledger):
        ledger = setup_ledger

        schedule = [
            (datetime(2024, 3, 29), 0.25),
        ]
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            dividend_schedule=schedule,
        )
        ledger.register_unit(unit)

        # Treasury holds some shares
        ledger.set_balance("treasury", "AAPL", 500)
        ledger.set_balance("alice", "AAPL", 1000)

        ledger.advance_time(datetime(2024, 3, 29))

        result = compute_scheduled_dividend(ledger, "AAPL", datetime(2024, 3, 29))

        # Only Alice should receive dividend
        assert len(result.moves) == 1
        assert result.moves[0].dest == "alice"


# ============================================================================
# stock_contract Integration Tests
# ============================================================================

class TestStockContractIntegration:
    """Tests for stock_contract with LifecycleEngine."""

    def test_lifecycle_engine_processes_dividends(self):
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        treasury = ledger.register_wallet("treasury")
        alice = ledger.register_wallet("alice")

        ledger.set_balance(treasury, "USD", 1_000_000)

        schedule = [
            (datetime(2024, 3, 29), 0.25),
        ]
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            dividend_schedule=schedule,
        )
        ledger.register_unit(unit)

        ledger.set_balance("alice", "AAPL", 1000)

        # Create lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)

        # Run past payment date
        results = engine.run(
            [datetime(2024, 3, 28), datetime(2024, 3, 29), datetime(2024, 3, 30)],
            lambda ts: {}
        )

        # Check Alice received dividend
        assert ledger.get_balance("alice", "USD") == 250.0

    def test_multiple_dividends_via_engine(self):
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        treasury = ledger.register_wallet("treasury")
        alice = ledger.register_wallet("alice")

        ledger.set_balance(treasury, "USD", 1_000_000)

        # Quarterly schedule
        schedule = [
            (datetime(2024, 3, 29), 0.25),
            (datetime(2024, 6, 28), 0.25),
            (datetime(2024, 9, 27), 0.25),
            (datetime(2024, 12, 27), 0.25),
        ]
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            dividend_schedule=schedule,
        )
        ledger.register_unit(unit)

        ledger.set_balance("alice", "AAPL", 1000)

        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)

        # Run through the year (daily)
        timestamps = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(365)]
        engine.run(timestamps, lambda ts: {})

        # Check Alice's total dividends: 4 * 1000 * 0.25 = 1000
        assert ledger.get_balance("alice", "USD") == 1000.0

    def test_stock_unit_type(self):
        """Stock units should have unit_type STOCK."""
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
        )

        assert unit.unit_type == "STOCK"


# ============================================================================
# Extended Dividend Tests
# ============================================================================

class TestDividendPaymentDetails:
    """Detailed tests for dividend payment mechanics."""

    @pytest.fixture
    def dividend_ledger(self):
        """Create a test ledger with multiple shareholders."""
        ledger = Ledger("dividend_test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Register wallets
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("charlie")
        ledger.register_wallet("dave")

        # Fund treasury
        ledger.set_balance("treasury", "USD", 10_000_000)

        return ledger

    def test_dividend_proportional_to_shares(self, dividend_ledger):
        """Dividend amount should be proportional to shares held."""
        ledger = dividend_ledger

        schedule = [(datetime(2024, 3, 29), 1.00)]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        # Different share amounts
        ledger.set_balance("alice", "TEST", 100)
        ledger.set_balance("bob", "TEST", 500)
        ledger.set_balance("charlie", "TEST", 1000)

        ledger.advance_time(datetime(2024, 3, 29))
        result = compute_scheduled_dividend(ledger, "TEST", datetime(2024, 3, 29))
        ledger.execute_contract(result)

        assert ledger.get_balance("alice", "USD") == 100.0
        assert ledger.get_balance("bob", "USD") == 500.0
        assert ledger.get_balance("charlie", "USD") == 1000.0

    def test_dividend_with_fractional_shares(self, dividend_ledger):
        """Dividend should work with fractional share amounts."""
        ledger = dividend_ledger

        schedule = [(datetime(2024, 3, 29), 0.50)]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "TEST", 33.5)  # Fractional shares

        ledger.advance_time(datetime(2024, 3, 29))
        result = compute_scheduled_dividend(ledger, "TEST", datetime(2024, 3, 29))
        ledger.execute_contract(result)

        assert ledger.get_balance("alice", "USD") == pytest.approx(16.75, rel=1e-6)

    def test_dividend_zero_shares_no_payment(self, dividend_ledger):
        """Shareholders with zero shares get no dividend."""
        ledger = dividend_ledger

        schedule = [(datetime(2024, 3, 29), 1.00)]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "TEST", 100)
        ledger.set_balance("bob", "TEST", 0)  # Zero shares

        ledger.advance_time(datetime(2024, 3, 29))
        result = compute_scheduled_dividend(ledger, "TEST", datetime(2024, 3, 29))

        # Only alice should receive dividend
        assert len(result.moves) == 1
        assert result.moves[0].dest == "alice"

    def test_dividend_negative_shares_no_payment(self, dividend_ledger):
        """Short sellers (negative shares) don't receive dividends."""
        ledger = dividend_ledger

        schedule = [(datetime(2024, 3, 29), 1.00)]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule, shortable=True)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "TEST", 100)
        ledger.set_balance("bob", "TEST", -50)  # Short position

        ledger.advance_time(datetime(2024, 3, 29))
        result = compute_scheduled_dividend(ledger, "TEST", datetime(2024, 3, 29))

        # Only alice should receive dividend
        assert len(result.moves) == 1
        assert result.moves[0].dest == "alice"
        assert result.moves[0].quantity == 100.0

    def test_dividend_reduces_treasury_balance(self, dividend_ledger):
        """Dividend payments should reduce treasury balance."""
        ledger = dividend_ledger
        initial_treasury = ledger.get_balance("treasury", "USD")

        schedule = [(datetime(2024, 3, 29), 5.00)]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "TEST", 1000)

        ledger.advance_time(datetime(2024, 3, 29))
        result = compute_scheduled_dividend(ledger, "TEST", datetime(2024, 3, 29))
        ledger.execute_contract(result)

        assert ledger.get_balance("treasury", "USD") == initial_treasury - 5000.0
        assert ledger.get_balance("alice", "USD") == 5000.0


class TestDividendScheduleExecution:
    """Tests for sequential dividend schedule execution."""

    @pytest.fixture
    def scheduled_ledger(self):
        """Create a test ledger with quarterly dividend stock."""
        ledger = Ledger("schedule_test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")

        ledger.set_balance("treasury", "USD", 10_000_000)
        ledger.set_balance("alice", "USD", 0)

        # Create stock with 4 quarterly dividends
        schedule = [
            (datetime(2024, 3, 29), 0.25),
            (datetime(2024, 6, 28), 0.25),
            (datetime(2024, 9, 27), 0.25),
            (datetime(2024, 12, 27), 0.30),  # Special year-end dividend
        ]
        unit = create_stock_unit("DIV", "Dividend Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "DIV", 1000)

        return ledger

    def test_sequential_dividend_payments(self, scheduled_ledger):
        """Dividends should be paid sequentially per schedule."""
        ledger = scheduled_ledger

        # First dividend
        ledger.advance_time(datetime(2024, 3, 29))
        r1 = compute_scheduled_dividend(ledger, "DIV", datetime(2024, 3, 29))
        ledger.execute_contract(r1)
        assert ledger.get_balance("alice", "USD") == 250.0

        # Second dividend
        ledger.advance_time(datetime(2024, 6, 28))
        r2 = compute_scheduled_dividend(ledger, "DIV", datetime(2024, 6, 28))
        ledger.execute_contract(r2)
        assert ledger.get_balance("alice", "USD") == 500.0

        # Third dividend
        ledger.advance_time(datetime(2024, 9, 27))
        r3 = compute_scheduled_dividend(ledger, "DIV", datetime(2024, 9, 27))
        ledger.execute_contract(r3)
        assert ledger.get_balance("alice", "USD") == 750.0

        # Fourth dividend (special)
        ledger.advance_time(datetime(2024, 12, 27))
        r4 = compute_scheduled_dividend(ledger, "DIV", datetime(2024, 12, 27))
        ledger.execute_contract(r4)
        assert ledger.get_balance("alice", "USD") == 1050.0  # 750 + 300

    def test_payment_index_advances(self, scheduled_ledger):
        """Payment index should advance after each dividend."""
        ledger = scheduled_ledger

        assert ledger.get_unit_state("DIV")['next_payment_index'] == 0

        ledger.advance_time(datetime(2024, 3, 29))
        r1 = compute_scheduled_dividend(ledger, "DIV", datetime(2024, 3, 29))
        ledger.execute_contract(r1)
        assert ledger.get_unit_state("DIV")['next_payment_index'] == 1

        ledger.advance_time(datetime(2024, 6, 28))
        r2 = compute_scheduled_dividend(ledger, "DIV", datetime(2024, 6, 28))
        ledger.execute_contract(r2)
        assert ledger.get_unit_state("DIV")['next_payment_index'] == 2


class TestDividendEdgeCases:
    """Edge case tests for dividend processing."""

    def test_dividend_no_shareholders(self):
        """Dividend with no shareholders should update state but have no moves."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.set_balance("treasury", "USD", 1_000_000)

        schedule = [(datetime(2024, 3, 29), 1.00)]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        # No shareholders
        ledger.advance_time(datetime(2024, 3, 29))
        result = compute_scheduled_dividend(ledger, "TEST", datetime(2024, 3, 29))

        # Should have no moves but still update state
        assert len(result.moves) == 0
        assert "TEST" in result.state_updates
        assert result.state_updates["TEST"]['next_payment_index'] == 1

    def test_dividend_only_treasury_holds_shares(self):
        """If only treasury holds shares, no dividend is paid."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.set_balance("treasury", "USD", 1_000_000)

        schedule = [(datetime(2024, 3, 29), 1.00)]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        # Only treasury holds shares
        ledger.set_balance("treasury", "TEST", 10000)

        ledger.advance_time(datetime(2024, 3, 29))
        result = compute_scheduled_dividend(ledger, "TEST", datetime(2024, 3, 29))

        assert len(result.moves) == 0

    def test_dividend_same_day_multiple_stocks(self):
        """Multiple stocks can pay dividends on the same day."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.set_balance("treasury", "USD", 10_000_000)

        payment_date = datetime(2024, 3, 29)
        schedule = [(payment_date, 1.00)]

        # Create two stocks
        ledger.register_unit(create_stock_unit("STOCK1", "Stock One", "treasury", "USD", schedule))
        ledger.register_unit(create_stock_unit("STOCK2", "Stock Two", "treasury", "USD", schedule))

        ledger.set_balance("alice", "STOCK1", 100)
        ledger.set_balance("alice", "STOCK2", 200)

        ledger.advance_time(payment_date)

        r1 = compute_scheduled_dividend(ledger, "STOCK1", payment_date)
        r2 = compute_scheduled_dividend(ledger, "STOCK2", payment_date)

        ledger.execute_contract(r1)
        ledger.execute_contract(r2)

        assert ledger.get_balance("alice", "USD") == 300.0  # 100 + 200

    def test_dividend_deterministic_order(self):
        """Dividend payments should be in deterministic (sorted) order."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.set_balance("treasury", "USD", 1_000_000)

        schedule = [(datetime(2024, 3, 29), 1.00)]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        # Register in non-sorted order
        for name in ["zebra", "alice", "charlie", "bob"]:
            ledger.register_wallet(name)
            ledger.set_balance(name, "TEST", 10)

        ledger.advance_time(datetime(2024, 3, 29))
        result = compute_scheduled_dividend(ledger, "TEST", datetime(2024, 3, 29))

        # Moves should be in sorted order
        recipients = [m.dest for m in result.moves]
        assert recipients == sorted(recipients)


class TestDividendWithShareChanges:
    """Tests for dividends when shareholdings change between payments."""

    def test_shareholder_sells_before_next_dividend(self):
        """New owner should receive dividend after purchase."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("treasury", "USD", 10_000_000)

        schedule = [
            (datetime(2024, 3, 29), 1.00),
            (datetime(2024, 6, 28), 1.00),
        ]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "TEST", 1000)

        # First dividend to Alice
        ledger.advance_time(datetime(2024, 3, 29))
        r1 = compute_scheduled_dividend(ledger, "TEST", datetime(2024, 3, 29))
        ledger.execute_contract(r1)
        assert ledger.get_balance("alice", "USD") == 1000.0

        # Alice sells to Bob
        ledger.set_balance("alice", "TEST", 0)
        ledger.set_balance("bob", "TEST", 1000)

        # Second dividend to Bob
        ledger.advance_time(datetime(2024, 6, 28))
        r2 = compute_scheduled_dividend(ledger, "TEST", datetime(2024, 6, 28))
        ledger.execute_contract(r2)

        assert ledger.get_balance("alice", "USD") == 1000.0  # No change
        assert ledger.get_balance("bob", "USD") == 1000.0    # Bob gets dividend


class TestDividendIntegrationWithEngine:
    """Integration tests with LifecycleEngine."""

    def test_engine_processes_all_scheduled_dividends(self):
        """Engine should process all dividends through the year."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("treasury", "USD", 100_000_000)

        # Monthly schedule
        schedule = [
            (datetime(2024, 1, 15), 0.10),
            (datetime(2024, 2, 15), 0.10),
            (datetime(2024, 3, 15), 0.10),
            (datetime(2024, 4, 15), 0.10),
            (datetime(2024, 5, 15), 0.10),
            (datetime(2024, 6, 15), 0.10),
            (datetime(2024, 7, 15), 0.10),
            (datetime(2024, 8, 15), 0.10),
            (datetime(2024, 9, 15), 0.10),
            (datetime(2024, 10, 15), 0.10),
            (datetime(2024, 11, 15), 0.10),
            (datetime(2024, 12, 15), 0.10),
        ]
        unit = create_stock_unit("MONTHLY", "Monthly Dividend Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "MONTHLY", 1000)
        ledger.set_balance("bob", "MONTHLY", 500)

        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)

        # Run daily for the year
        timestamps = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(365)]
        engine.run(timestamps, lambda ts: {})

        # Check paid dividends
        paid = ledger.get_unit_state("MONTHLY").get('paid_dividends', [])
        assert len(paid) == 12  # 12 monthly payments

        # Alice: 12 * 1000 * 0.10 = 1200
        # Bob: 12 * 500 * 0.10 = 600
        assert ledger.get_balance("alice", "USD") == 1200.0
        assert ledger.get_balance("bob", "USD") == 600.0

    def test_engine_with_multiple_stock_types(self):
        """Engine should handle multiple stocks with different schedules."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.set_balance("treasury", "USD", 100_000_000)

        # Quarterly stock
        q_schedule = [
            (datetime(2024, 3, 15), 1.00),
            (datetime(2024, 6, 15), 1.00),
            (datetime(2024, 9, 15), 1.00),
            (datetime(2024, 12, 15), 1.00),
        ]
        ledger.register_unit(create_stock_unit("QTRLY", "Quarterly Stock", "treasury", "USD", q_schedule))

        # Monthly stock
        m_schedule = [
            (datetime(2024, 1, 15), 0.25),
            (datetime(2024, 2, 15), 0.25),
            (datetime(2024, 3, 15), 0.25),
            (datetime(2024, 4, 15), 0.25),
            (datetime(2024, 5, 15), 0.25),
            (datetime(2024, 6, 15), 0.25),
            (datetime(2024, 7, 15), 0.25),
            (datetime(2024, 8, 15), 0.25),
            (datetime(2024, 9, 15), 0.25),
            (datetime(2024, 10, 15), 0.25),
            (datetime(2024, 11, 15), 0.25),
            (datetime(2024, 12, 15), 0.25),
        ]
        ledger.register_unit(create_stock_unit("MTHLY", "Monthly Stock", "treasury", "USD", m_schedule))

        ledger.set_balance("alice", "QTRLY", 100)
        ledger.set_balance("alice", "MTHLY", 100)

        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)

        timestamps = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(365)]
        engine.run(timestamps, lambda ts: {})

        # Quarterly: 4 * 100 * 1.00 = 400
        # Monthly: 12 * 100 * 0.25 = 300
        assert ledger.get_balance("alice", "USD") == 700.0
