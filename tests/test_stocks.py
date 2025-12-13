"""
Tests for stocks.py - Stock Contracts with Dividend Scheduling

Tests:
- create_stock_unit factory (creates stock units with dividend schedules)
- process_dividends (processes dividend payments on payment dates)
- stock_contract lifecycle integration (automated dividend processing via LifecycleEngine)

Dividend schedule format: list of Dividend objects with ex_date, payment_date, amount_per_share, and currency.
"""

import pytest
from datetime import datetime, timedelta

from ledger import (
    Ledger, cash,
    create_stock_unit,
    process_dividends,
    Dividend,
    stock_contract,
    deferred_cash_contract,
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
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 0.25, "USD"),
            Dividend(datetime(2024, 6, 15), datetime(2024, 6, 15), 0.25, "USD"),
            Dividend(datetime(2024, 9, 15), datetime(2024, 9, 15), 0.25, "USD"),
            Dividend(datetime(2024, 12, 15), datetime(2024, 12, 15), 0.25, "USD"),
        ]
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            dividend_schedule=schedule,
        )

        assert unit._state['processed_dividends'] == []
        assert len(unit._state['dividend_schedule']) == 4

    def test_create_stock_unit_no_schedule(self):
        unit = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
        )

        assert unit._state['dividend_schedule'] == []
        assert unit._state['processed_dividends'] == []


# ============================================================================
# process_dividends Tests
# ============================================================================

class TestProcessDividends:
    """Tests for process_dividends function."""

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
            Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 0.25, "USD"),
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

        result = process_dividends(ledger, "AAPL", datetime(2024, 3, 29))

        assert not result.is_empty()
        assert len(result.moves) == 2  # Alice and Bob get DeferredCash entitlements
        assert len(result.units_to_create) == 2  # Two DeferredCash units

        # Check DeferredCash entitlements (qty=1 each)
        alice_move = next(m for m in result.moves if m.dest == "alice")
        bob_move = next(m for m in result.moves if m.dest == "bob")

        assert alice_move.quantity == 1.0  # DeferredCash entitlement
        assert bob_move.quantity == 1.0

        # Check DeferredCash units contain correct amounts
        alice_dc = next(u for u in result.units_to_create if "alice" in u.symbol)
        bob_dc = next(u for u in result.units_to_create if "bob" in u.symbol)

        assert alice_dc._state['amount'] == 250.0  # 1000 * 0.25
        assert bob_dc._state['amount'] == 125.0   # 500 * 0.25

    def test_dividend_before_payment_date_returns_empty(self, setup_ledger):
        ledger = setup_ledger

        schedule = [
            Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 0.25, "USD"),
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
        result = process_dividends(ledger, "AAPL", datetime(2024, 3, 28))

        assert result.is_empty()

    def test_dividend_updates_state(self, setup_ledger):
        ledger = setup_ledger

        schedule = [
            Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 0.25, "USD"),
            Dividend(datetime(2024, 6, 29), datetime(2024, 6, 29), 0.25, "USD"),
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

        result = process_dividends(ledger, "AAPL", datetime(2024, 3, 29))

        # Check state updates - now just processed_dividends list
        sc = next(d for d in result.state_changes if d.unit == "AAPL")
        assert 'processed_dividends' in sc.new_state
        assert '2024-03-29' in sc.new_state['processed_dividends']

    def test_schedule_exhausted_returns_empty(self, setup_ledger):
        ledger = setup_ledger

        schedule = [
            Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 0.25, "USD"),
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
        result1 = process_dividends(ledger, "AAPL", datetime(2024, 3, 29))
        ledger.execute(result1)

        # Try second dividend (should be empty)
        result2 = process_dividends(ledger, "AAPL", datetime(2024, 6, 29))
        assert result2.is_empty()

    def test_issuer_excluded_from_dividend(self, setup_ledger):
        ledger = setup_ledger

        schedule = [
            Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 0.25, "USD"),
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

        result = process_dividends(ledger, "AAPL", datetime(2024, 3, 29))

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
            Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 0.25, "USD"),
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

        # Create lifecycle engine with both STOCK and DEFERRED_CASH contracts
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Run past payment date
        results = engine.run(
            [datetime(2024, 3, 28), datetime(2024, 3, 29), datetime(2024, 3, 30)],
            lambda ts: {}
        )

        # Check Alice received dividend (via DeferredCash settlement)
        assert ledger.get_balance("alice", "USD") == 250.0

    def test_multiple_dividends_via_engine(self):
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        treasury = ledger.register_wallet("treasury")
        alice = ledger.register_wallet("alice")

        ledger.set_balance(treasury, "USD", 1_000_000)

        # Quarterly schedule
        schedule = [
            Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 0.25, "USD"),
            Dividend(datetime(2024, 6, 28), datetime(2024, 6, 28), 0.25, "USD"),
            Dividend(datetime(2024, 9, 27), datetime(2024, 9, 27), 0.25, "USD"),
            Dividend(datetime(2024, 12, 27), datetime(2024, 12, 27), 0.25, "USD"),
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
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Run through the year (daily)
        timestamps = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(365)]
        engine.run(timestamps, lambda ts: {})

        # Check Alice's total dividends: 4 * 1000 * 0.25 = 1000 (via DeferredCash)
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

        schedule = [Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 1.00, "USD")]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        # Different share amounts
        ledger.set_balance("alice", "TEST", 100)
        ledger.set_balance("bob", "TEST", 500)
        ledger.set_balance("charlie", "TEST", 1000)

        # Use lifecycle engine to process both dividend entitlement and DeferredCash settlement
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)
        engine.step(datetime(2024, 3, 29), {"TEST": 100.0})

        assert ledger.get_balance("alice", "USD") == 100.0
        assert ledger.get_balance("bob", "USD") == 500.0
        assert ledger.get_balance("charlie", "USD") == 1000.0

    def test_dividend_with_fractional_shares(self, dividend_ledger):
        """Dividend should work with fractional share amounts."""
        ledger = dividend_ledger

        schedule = [Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 0.50, "USD")]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "TEST", 33.5)  # Fractional shares

        # Use lifecycle engine to process both dividend entitlement and DeferredCash settlement
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)
        engine.step(datetime(2024, 3, 29), {"TEST": 100.0})

        assert ledger.get_balance("alice", "USD") == pytest.approx(16.75, rel=1e-6)

    def test_dividend_zero_shares_no_payment(self, dividend_ledger):
        """Shareholders with zero shares get no dividend."""
        ledger = dividend_ledger

        schedule = [Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 1.00, "USD")]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "TEST", 100)
        ledger.set_balance("bob", "TEST", 0)  # Zero shares

        ledger.advance_time(datetime(2024, 3, 29))
        result = process_dividends(ledger, "TEST", datetime(2024, 3, 29))

        # Only alice should receive dividend (DeferredCash move)
        # The moves include: 1 DeferredCash entitlement for alice
        deferred_cash_moves = [m for m in result.moves if m.dest not in ("system",)]
        assert len(deferred_cash_moves) == 1
        assert deferred_cash_moves[0].dest == "alice"

    def test_dividend_negative_shares_no_payment(self, dividend_ledger):
        """Short sellers (negative shares) don't receive dividends."""
        ledger = dividend_ledger

        schedule = [Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 1.00, "USD")]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule, shortable=True)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "TEST", 100)
        ledger.set_balance("bob", "TEST", -50)  # Short position

        ledger.advance_time(datetime(2024, 3, 29))
        result = process_dividends(ledger, "TEST", datetime(2024, 3, 29))

        # Only alice should receive dividend (DeferredCash entitlement)
        # The moves include: 1 DeferredCash entitlement for alice
        deferred_cash_moves = [m for m in result.moves if m.dest not in ("system",)]
        assert len(deferred_cash_moves) == 1
        assert deferred_cash_moves[0].dest == "alice"
        # Check the unit state contains alice's dividend amount (100 shares × $1)
        dc_units = [u for u in result.units_to_create if "DIV_TEST" in u.symbol and "alice" in u.symbol]
        assert len(dc_units) == 1
        assert dc_units[0]._state['amount'] == 100.0

    def test_dividend_reduces_treasury_balance(self, dividend_ledger):
        """Dividend payments should reduce treasury balance."""
        ledger = dividend_ledger
        initial_treasury = ledger.get_balance("treasury", "USD")

        schedule = [Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 5.00, "USD")]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "TEST", 1000)

        # Use lifecycle engine to process both dividend entitlement and DeferredCash settlement
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)
        engine.step(datetime(2024, 3, 29), {"TEST": 100.0})

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
            Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 0.25, "USD"),
            Dividend(datetime(2024, 6, 28), datetime(2024, 6, 28), 0.25, "USD"),
            Dividend(datetime(2024, 9, 27), datetime(2024, 9, 27), 0.25, "USD"),
            Dividend(datetime(2024, 12, 27), datetime(2024, 12, 27), 0.30, "USD"),  # Special year-end dividend
        ]
        unit = create_stock_unit("DIV", "Dividend Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "DIV", 1000)

        return ledger

    def test_sequential_dividend_payments(self, scheduled_ledger):
        """Dividends should be paid sequentially per schedule."""
        ledger = scheduled_ledger

        # Use lifecycle engine to process both dividend entitlement and DeferredCash settlement
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # First dividend
        engine.step(datetime(2024, 3, 29), {"DIV": 100.0})
        assert ledger.get_balance("alice", "USD") == 250.0

        # Second dividend
        engine.step(datetime(2024, 6, 28), {"DIV": 100.0})
        assert ledger.get_balance("alice", "USD") == 500.0

        # Third dividend
        engine.step(datetime(2024, 9, 27), {"DIV": 100.0})
        assert ledger.get_balance("alice", "USD") == 750.0

        # Fourth dividend (special)
        engine.step(datetime(2024, 12, 27), {"DIV": 100.0})
        assert ledger.get_balance("alice", "USD") == 1050.0  # 750 + 300

    def test_paid_dates_accumulate(self, scheduled_ledger):
        """Processed dividends should accumulate after each dividend."""
        ledger = scheduled_ledger

        assert ledger.get_unit_state("DIV").get('processed_dividends', []) == []

        # Use lifecycle engine to process both dividend entitlement and DeferredCash settlement
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        engine.step(datetime(2024, 3, 29), {"DIV": 100.0})
        # processed_dividends format: [div_key, ...]
        assert len(ledger.get_unit_state("DIV").get('processed_dividends', [])) == 1

        engine.step(datetime(2024, 6, 28), {"DIV": 100.0})
        assert len(ledger.get_unit_state("DIV").get('processed_dividends', [])) == 2


class TestDividendEdgeCases:
    """Edge case tests for dividend processing."""

    def test_dividend_no_shareholders(self):
        """Dividend with no shareholders should return empty result."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.set_balance("treasury", "USD", 1_000_000)

        schedule = [Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 1.00, "USD")]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        # No shareholders
        ledger.advance_time(datetime(2024, 3, 29))
        result = process_dividends(ledger, "TEST", datetime(2024, 3, 29))

        # Should have no moves
        assert len(result.moves) == 0

    def test_dividend_only_treasury_holds_shares(self):
        """If only treasury holds shares, no dividend is paid."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.set_balance("treasury", "USD", 1_000_000)

        schedule = [Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 1.00, "USD")]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        # Only treasury holds shares
        ledger.set_balance("treasury", "TEST", 10000)

        ledger.advance_time(datetime(2024, 3, 29))
        result = process_dividends(ledger, "TEST", datetime(2024, 3, 29))

        assert len(result.moves) == 0

    def test_dividend_same_day_multiple_stocks(self):
        """Multiple stocks can pay dividends on the same day."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.set_balance("treasury", "USD", 10_000_000)

        payment_date = datetime(2024, 3, 29)
        schedule = [Dividend(payment_date, payment_date, 1.00, "USD")]

        # Create two stocks
        ledger.register_unit(create_stock_unit("STOCK1", "Stock One", "treasury", "USD", schedule))
        ledger.register_unit(create_stock_unit("STOCK2", "Stock Two", "treasury", "USD", schedule))

        ledger.set_balance("alice", "STOCK1", 100)
        ledger.set_balance("alice", "STOCK2", 200)

        # Use lifecycle engine to process both dividend entitlement and DeferredCash settlement
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)
        engine.step(payment_date, {"STOCK1": 100.0, "STOCK2": 100.0})

        assert ledger.get_balance("alice", "USD") == 300.0  # 100 + 200

    def test_dividend_deterministic_order(self):
        """Dividend payments should be in deterministic (sorted) order."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.set_balance("treasury", "USD", 1_000_000)

        schedule = [Dividend(datetime(2024, 3, 29), datetime(2024, 3, 29), 1.00, "USD")]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        # Register in non-sorted order
        for name in ["zebra", "alice", "charlie", "bob"]:
            ledger.register_wallet(name)
            ledger.set_balance(name, "TEST", 10)

        ledger.advance_time(datetime(2024, 3, 29))
        result = process_dividends(ledger, "TEST", datetime(2024, 3, 29))

        # DeferredCash moves recipients should be in sorted order
        # Filter to only include moves to shareholders (not system moves)
        recipients = [m.dest for m in result.moves if m.dest not in ("system",)]
        assert recipients == sorted(recipients)


class TestDividendWithShareChanges:
    """Tests for dividends when shareholdings change between payments."""

    def test_shareholder_sells_before_next_dividend(self):
        """New owner should receive dividend after purchase.

        Tests the ex_date vs payment_date distinction:
        - Ex-date snapshots who is eligible
        - Payment-date is when cash is paid
        - Selling shares AFTER ex-date means seller still gets that dividend
        - Selling shares BEFORE ex-date means buyer gets the dividend
        """
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("treasury", "USD", 10_000_000)

        # Ex-dates are BEFORE payment dates
        schedule = [
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 29), 1.00, "USD"),  # Ex-date 3/15, pay 3/29
            Dividend(datetime(2024, 6, 14), datetime(2024, 6, 28), 1.00, "USD"),  # Ex-date 6/14, pay 6/28
        ]
        unit = create_stock_unit("TEST", "Test Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "TEST", 1000)

        # Use lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # First ex-date snapshot (Alice holds) - creates DeferredCash
        engine.step(datetime(2024, 3, 15), {"TEST": 100.0})

        # First dividend payment to Alice (DeferredCash settles)
        engine.step(datetime(2024, 3, 29), {"TEST": 100.0})
        assert ledger.get_balance("alice", "USD") == 1000.0

        # Alice sells to Bob AFTER first dividend but BEFORE second ex-date
        ledger.set_balance("alice", "TEST", 0)
        ledger.set_balance("bob", "TEST", 1000)

        # Second ex-date snapshot (Bob now holds) - creates DeferredCash for Bob
        engine.step(datetime(2024, 6, 14), {"TEST": 100.0})

        # Second dividend payment to Bob (DeferredCash settles)
        engine.step(datetime(2024, 6, 28), {"TEST": 100.0})

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
            Dividend(datetime(2024, 1, 15), datetime(2024, 1, 15), 0.10, "USD"),
            Dividend(datetime(2024, 2, 15), datetime(2024, 2, 15), 0.10, "USD"),
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 0.10, "USD"),
            Dividend(datetime(2024, 4, 15), datetime(2024, 4, 15), 0.10, "USD"),
            Dividend(datetime(2024, 5, 15), datetime(2024, 5, 15), 0.10, "USD"),
            Dividend(datetime(2024, 6, 15), datetime(2024, 6, 15), 0.10, "USD"),
            Dividend(datetime(2024, 7, 15), datetime(2024, 7, 15), 0.10, "USD"),
            Dividend(datetime(2024, 8, 15), datetime(2024, 8, 15), 0.10, "USD"),
            Dividend(datetime(2024, 9, 15), datetime(2024, 9, 15), 0.10, "USD"),
            Dividend(datetime(2024, 10, 15), datetime(2024, 10, 15), 0.10, "USD"),
            Dividend(datetime(2024, 11, 15), datetime(2024, 11, 15), 0.10, "USD"),
            Dividend(datetime(2024, 12, 15), datetime(2024, 12, 15), 0.10, "USD"),
        ]
        unit = create_stock_unit("MONTHLY", "Monthly Dividend Stock", "treasury", "USD", schedule)
        ledger.register_unit(unit)

        ledger.set_balance("alice", "MONTHLY", 1000)
        ledger.set_balance("bob", "MONTHLY", 500)

        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Run daily for the year
        timestamps = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(365)]
        engine.run(timestamps, lambda ts: {})

        # Check that all 12 dividends were processed (processed_dividends format: [div_key, ...])
        processed = ledger.get_unit_state("MONTHLY").get('processed_dividends', [])
        assert len(processed) == 12  # 12 monthly dividends

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
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 1.00, "USD"),
            Dividend(datetime(2024, 6, 15), datetime(2024, 6, 15), 1.00, "USD"),
            Dividend(datetime(2024, 9, 15), datetime(2024, 9, 15), 1.00, "USD"),
            Dividend(datetime(2024, 12, 15), datetime(2024, 12, 15), 1.00, "USD"),
        ]
        ledger.register_unit(create_stock_unit("QTRLY", "Quarterly Stock", "treasury", "USD", q_schedule))

        # Monthly stock
        m_schedule = [
            Dividend(datetime(2024, 1, 15), datetime(2024, 1, 15), 0.25, "USD"),
            Dividend(datetime(2024, 2, 15), datetime(2024, 2, 15), 0.25, "USD"),
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 0.25, "USD"),
            Dividend(datetime(2024, 4, 15), datetime(2024, 4, 15), 0.25, "USD"),
            Dividend(datetime(2024, 5, 15), datetime(2024, 5, 15), 0.25, "USD"),
            Dividend(datetime(2024, 6, 15), datetime(2024, 6, 15), 0.25, "USD"),
            Dividend(datetime(2024, 7, 15), datetime(2024, 7, 15), 0.25, "USD"),
            Dividend(datetime(2024, 8, 15), datetime(2024, 8, 15), 0.25, "USD"),
            Dividend(datetime(2024, 9, 15), datetime(2024, 9, 15), 0.25, "USD"),
            Dividend(datetime(2024, 10, 15), datetime(2024, 10, 15), 0.25, "USD"),
            Dividend(datetime(2024, 11, 15), datetime(2024, 11, 15), 0.25, "USD"),
            Dividend(datetime(2024, 12, 15), datetime(2024, 12, 15), 0.25, "USD"),
        ]
        ledger.register_unit(create_stock_unit("MTHLY", "Monthly Stock", "treasury", "USD", m_schedule))

        ledger.set_balance("alice", "QTRLY", 100)
        ledger.set_balance("alice", "MTHLY", 100)

        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        timestamps = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(365)]
        engine.run(timestamps, lambda ts: {})

        # Quarterly: 4 * 100 * 1.00 = 400
        # Monthly: 12 * 100 * 0.25 = 300
        assert ledger.get_balance("alice", "USD") == 700.0


# ============================================================================
# Bulletproof Dividend Processing Tests
# ============================================================================

class TestBulletproofDividendProcessing:
    """
    Tests verifying the new date-based dividend tracking is bulletproof.

    These tests verify behavior that would BREAK with index-based tracking:
    1. Unsorted schedules
    2. Schedule modifications after creation
    3. Multiple dividends becoming due at once
    4. Idempotency (calling twice doesn't double-pay)
    """

    @pytest.fixture
    def base_ledger(self):
        """Create a basic test ledger."""
        ledger = Ledger("bulletproof_test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.set_balance("treasury", "USD", 10_000_000)
        return ledger

    def test_unsorted_schedule_processes_correctly(self, base_ledger):
        """
        Dividends should process correctly even if schedule is not sorted.

        OLD BUG: Index-based tracking assumed sorted schedule.
        """
        ledger = base_ledger

        # Schedule is INTENTIONALLY unsorted
        schedule = [
            Dividend(datetime(2024, 12, 15), datetime(2024, 12, 15), 0.40, "USD"),  # Q4 - listed first
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 0.10, "USD"),   # Q1 - listed second
            Dividend(datetime(2024, 9, 15), datetime(2024, 9, 15), 0.30, "USD"),   # Q3 - listed third
            Dividend(datetime(2024, 6, 15), datetime(2024, 6, 15), 0.20, "USD"),   # Q2 - listed fourth
        ]
        unit = create_stock_unit("UNSORTED", "Unsorted Dividends", "treasury", "USD", schedule)
        ledger.register_unit(unit)
        ledger.set_balance("alice", "UNSORTED", 1000)

        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Run through the year
        timestamps = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(365)]
        engine.run(timestamps, lambda ts: {})

        # All dividends should be paid: 1000 * (0.10 + 0.20 + 0.30 + 0.40) = 1000
        assert ledger.get_balance("alice", "USD") == 1000.0
        assert len(ledger.get_unit_state("UNSORTED").get('processed_dividends', [])) == 4

    def test_multiple_due_dividends_processed_at_once(self, base_ledger):
        """
        If engine skips time and multiple dividends become due, all should process.

        OLD BUG: Index-based tracking only processed one dividend per call.
        """
        ledger = base_ledger

        schedule = [
            Dividend(datetime(2024, 1, 15), datetime(2024, 1, 15), 1.00, "USD"),
            Dividend(datetime(2024, 2, 15), datetime(2024, 2, 15), 2.00, "USD"),
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 3.00, "USD"),
        ]
        unit = create_stock_unit("SKIP", "Skip Test", "treasury", "USD", schedule)
        ledger.register_unit(unit)
        ledger.set_balance("alice", "SKIP", 100)

        # Jump directly to after all dividends are due (skip intermediate dates)
        # Use lifecycle engine to process both dividend entitlement and DeferredCash settlement
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)
        engine.step(datetime(2024, 4, 1), {"SKIP": 100.0})

        # All three dividends should be paid in one call: 100 * (1 + 2 + 3) = 600
        assert ledger.get_balance("alice", "USD") == 600.0
        assert len(ledger.get_unit_state("SKIP").get('processed_dividends', [])) == 3

    def test_idempotency_no_double_payment(self, base_ledger):
        """
        Calling engine.step twice should not double-pay.

        This verifies the processed_dividends tracking works correctly.
        """
        ledger = base_ledger

        schedule = [Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 1.00, "USD")]
        unit = create_stock_unit("IDEM", "Idempotent Test", "treasury", "USD", schedule)
        ledger.register_unit(unit)
        ledger.set_balance("alice", "IDEM", 100)

        # Use lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # First call - should pay
        engine.step(datetime(2024, 3, 15), {"IDEM": 100.0})
        assert ledger.get_balance("alice", "USD") == 100.0

        # Second call - should do nothing (already processed)
        engine.step(datetime(2024, 3, 15), {"IDEM": 100.0})

        # Balance unchanged
        assert ledger.get_balance("alice", "USD") == 100.0

    def test_schedule_addition_after_creation(self, base_ledger):
        """
        Adding a dividend to the schedule after creation should work.

        This simulates a real-world scenario where dividend schedules are updated.
        """
        ledger = base_ledger

        # Start with only Q1 and Q2
        initial_schedule = [
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 1.00, "USD"),
            Dividend(datetime(2024, 6, 15), datetime(2024, 6, 15), 1.00, "USD"),
        ]
        unit = create_stock_unit("DYNAMIC", "Dynamic Schedule", "treasury", "USD", initial_schedule)
        ledger.register_unit(unit)
        ledger.set_balance("alice", "DYNAMIC", 100)

        # Use lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Process Q1
        engine.step(datetime(2024, 3, 15), {"DYNAMIC": 100.0})
        assert ledger.get_balance("alice", "USD") == 100.0

        # Now simulate adding Q3 and Q4 to the schedule by modifying state
        state = ledger.get_unit_state("DYNAMIC")
        new_schedule = list(state['dividend_schedule'])
        new_schedule.append(Dividend(datetime(2024, 9, 15), datetime(2024, 9, 15), 1.00, "USD"))
        new_schedule.append(Dividend(datetime(2024, 12, 15), datetime(2024, 12, 15), 1.00, "USD"))

        # Update the schedule in unit state
        ledger.units["DYNAMIC"]._state['dividend_schedule'] = new_schedule

        # Process Q2
        engine.step(datetime(2024, 6, 15), {"DYNAMIC": 100.0})
        assert ledger.get_balance("alice", "USD") == 200.0

        # Process Q3 (newly added)
        engine.step(datetime(2024, 9, 15), {"DYNAMIC": 100.0})
        assert ledger.get_balance("alice", "USD") == 300.0

        # Process Q4 (newly added)
        engine.step(datetime(2024, 12, 15), {"DYNAMIC": 100.0})
        assert ledger.get_balance("alice", "USD") == 400.0

    def test_early_dividend_insertion(self, base_ledger):
        """
        Inserting a dividend BEFORE a previously-paid one should still work.

        OLD BUG: Index-based would skip this because next_payment_index > 0.
        """
        ledger = base_ledger

        # Start with just Q2
        initial_schedule = [
            Dividend(datetime(2024, 6, 15), datetime(2024, 6, 15), 2.00, "USD"),
        ]
        unit = create_stock_unit("INSERT", "Insert Test", "treasury", "USD", initial_schedule)
        ledger.register_unit(unit)
        ledger.set_balance("alice", "INSERT", 100)

        # Use lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Process Q2
        engine.step(datetime(2024, 6, 15), {"INSERT": 100.0})
        assert ledger.get_balance("alice", "USD") == 200.0

        # Now INSERT a Q1 dividend that's already past due
        state = ledger.get_unit_state("INSERT")
        new_schedule = list(state['dividend_schedule'])
        new_schedule.insert(0, Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 1.00, "USD"))  # Insert at beginning
        ledger.units["INSERT"]._state['dividend_schedule'] = new_schedule

        # Process again - the Q1 dividend should now be picked up
        engine.step(datetime(2024, 6, 16), {"INSERT": 100.0})

        # Q1 (1.00 * 100 = 100) should now be paid too
        assert ledger.get_balance("alice", "USD") == 300.0

    def test_duplicate_dates_in_schedule(self, base_ledger):
        """
        If same date appears twice in schedule (edge case), handle gracefully.

        After first payment, second entry with same date should be skipped
        because that date is already in processed_dividends.
        """
        ledger = base_ledger

        # Duplicate date in schedule (weird but possible)
        schedule = [
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 1.00, "USD"),
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 2.00, "USD"),  # Same date, different amount
            Dividend(datetime(2024, 6, 15), datetime(2024, 6, 15), 1.00, "USD"),
        ]
        unit = create_stock_unit("DUP", "Duplicate Test", "treasury", "USD", schedule)
        ledger.register_unit(unit)
        ledger.set_balance("alice", "DUP", 100)

        # Use lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)
        engine.step(datetime(2024, 3, 15), {"DUP": 100.0})

        # Only first entry for 3/15 should process (100 * 1.00 = 100)
        # The duplicate is skipped because the date key is already paid
        assert ledger.get_balance("alice", "USD") == 100.0

        # Verify the date is in processed_dividends
        processed = ledger.get_unit_state("DUP").get('processed_dividends', [])
        assert '2024-03-15' in processed

    def test_past_due_dividends_on_first_run(self, base_ledger):
        """
        If unit is created with already-past-due dividends, they should all pay.
        """
        ledger = base_ledger

        # Create unit with schedule where all dividends are already past
        schedule = [
            Dividend(datetime(2023, 3, 15), datetime(2023, 3, 15), 1.00, "USD"),  # Past
            Dividend(datetime(2023, 6, 15), datetime(2023, 6, 15), 1.00, "USD"),  # Past
            Dividend(datetime(2023, 9, 15), datetime(2023, 9, 15), 1.00, "USD"),  # Past
        ]
        unit = create_stock_unit("PAST", "Past Due Test", "treasury", "USD", schedule)
        ledger.register_unit(unit)
        ledger.set_balance("alice", "PAST", 100)

        # Use lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)
        engine.step(datetime(2024, 1, 1), {"PAST": 100.0})

        # All three should pay: 100 * 3 = 300
        assert ledger.get_balance("alice", "USD") == 300.0
        assert len(ledger.get_unit_state("PAST").get('processed_dividends', [])) == 3

    def test_empty_schedule_returns_empty(self, base_ledger):
        """Empty dividend schedule should return empty transaction."""
        ledger = base_ledger

        unit = create_stock_unit("EMPTY", "No Dividends", "treasury", "USD", [])
        ledger.register_unit(unit)
        ledger.set_balance("alice", "EMPTY", 100)

        result = process_dividends(ledger, "EMPTY", datetime(2024, 6, 15))
        assert result.is_empty()

    def test_deterministic_processing_order(self, base_ledger):
        """
        Multiple due dividends should process in chronological order.
        """
        ledger = base_ledger

        # Unsorted schedule
        schedule = [
            Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 3.00, "USD"),  # Third chronologically
            Dividend(datetime(2024, 1, 15), datetime(2024, 1, 15), 1.00, "USD"),  # First chronologically
            Dividend(datetime(2024, 2, 15), datetime(2024, 2, 15), 2.00, "USD"),  # Second chronologically
        ]
        unit = create_stock_unit("ORDER", "Order Test", "treasury", "USD", schedule)
        ledger.register_unit(unit)
        ledger.set_balance("alice", "ORDER", 100)

        # Use lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)
        engine.step(datetime(2024, 4, 1), {"ORDER": 100.0})

        # Total should be 100 * (1 + 2 + 3) = 600
        assert ledger.get_balance("alice", "USD") == 600.0
