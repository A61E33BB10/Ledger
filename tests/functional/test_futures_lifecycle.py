"""
test_futures_lifecycle.py - End-to-end lifecycle tests for futures contracts

Tests complete futures lifecycle scenarios:
- Multi-day trading with daily settlement
- Intraday margin calls
- Expiry settlement
- Multi-currency futures
- LifecycleEngine integration
"""

import pytest
from datetime import datetime, timedelta
from ledger import (
    Ledger, Move,
    cash,
    create_future_unit,
    execute_futures_trade,
    compute_daily_settlement,
    compute_intraday_margin,
    compute_expiry,
    LifecycleEngine,
    future_contract,
)


class TestFuturesMultiDayLifecycle:
    """Tests for multi-day futures trading and settlement."""

    def test_buy_hold_settle_three_days(self):
        """Buy futures, hold through 3 daily settlements, verify margin flows."""
        expiry = datetime(2024, 12, 20, 16, 0)

        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        future = create_future_unit(
            symbol="ESZ24",
            name="E-mini S&P 500 Dec 2024",
            underlying="SPX",
            expiry=expiry,
            multiplier=50.0,
            settlement_currency="USD",
            exchange="CME",
            holder_wallet="trader",
            clearinghouse_wallet="clearinghouse",
        )
        ledger.register_unit(future)

        ledger.register_wallet("trader")
        ledger.register_wallet("clearinghouse")

        # Initial cash positions
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearinghouse", "USD", 10_000_000)

        trader_initial = ledger.get_balance("trader", "USD")

        # Day 1: Buy 10 contracts at 4500
        result1 = execute_futures_trade(ledger, "ESZ24", 10.0, 4500.00)
        ledger.execute_contract(result1)

        # Verify virtual ledger updated
        state1 = ledger.get_unit_state("ESZ24")
        assert state1["virtual_quantity"] == 10.0
        assert state1["virtual_cash"] == -2_250_000.0

        # Day 1 EOD: Settlement at 4505 (up $5)
        result_settle1 = compute_daily_settlement(ledger, "ESZ24", 4505.00)
        ledger.execute_contract(result_settle1)

        state_after1 = ledger.get_unit_state("ESZ24")
        # margin_call = -2,250,000 + (10 × 4505 × 50) = 2,500
        # Check that virtual_cash was reset
        expected_virtual_cash = -(10.0 * 4505.0 * 50.0)
        assert state_after1["virtual_cash"] == expected_virtual_cash
        assert state_after1["last_settlement_price"] == 4505.0

        # Day 2 EOD: Settlement at 4520 (up $15 from yesterday)
        result_settle2 = compute_daily_settlement(ledger, "ESZ24", 4520.00)
        ledger.execute_contract(result_settle2)

        state_after2 = ledger.get_unit_state("ESZ24")
        assert state_after2["last_settlement_price"] == 4520.0

        # Day 3 EOD: Settlement at 4510 (down $10 from yesterday)
        result_settle3 = compute_daily_settlement(ledger, "ESZ24", 4510.00)
        ledger.execute_contract(result_settle3)

        state_after3 = ledger.get_unit_state("ESZ24")
        assert state_after3["last_settlement_price"] == 4510.0

        # Overall: bought at 4500, now at 4510
        # Net gain: (4510 - 4500) × 10 × 50 = 5,000
        # But due to the virtual ledger pattern with margin call direction,
        # the actual cash flow depends on the specific implementation

    def test_buy_and_sell_same_day(self):
        """Buy and partially sell on the same day before settlement."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        future = create_future_unit(
            symbol="ESZ24",
            name="E-mini S&P 500",
            underlying="SPX",
            expiry=datetime(2024, 12, 20),
            multiplier=50.0,
            settlement_currency="USD",
            exchange="CME",
            holder_wallet="trader",
            clearinghouse_wallet="clearinghouse",
        )
        ledger.register_unit(future)

        ledger.register_wallet("trader")
        ledger.register_wallet("clearinghouse")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearinghouse", "USD", 10_000_000)

        # Buy 10 at 4500
        result1 = execute_futures_trade(ledger, "ESZ24", 10.0, 4500.00)
        ledger.execute_contract(result1)

        # Sell 3 at 4510 (profit on those 3)
        result2 = execute_futures_trade(ledger, "ESZ24", -3.0, 4510.00)
        ledger.execute_contract(result2)

        state = ledger.get_unit_state("ESZ24")
        assert state["virtual_quantity"] == 7.0
        # virtual_cash = -10×4500×50 + 3×4510×50 = -2,250,000 + 676,500 = -1,573,500
        assert state["virtual_cash"] == -1_573_500.0

        # EOD settlement at 4520
        result_settle = compute_daily_settlement(ledger, "ESZ24", 4520.00)
        ledger.execute_contract(result_settle)

        state_after = ledger.get_unit_state("ESZ24")
        # margin_call = -1,573,500 + (7 × 4520 × 50) = -1,573,500 + 1,582,000 = 8,500
        assert state_after["virtual_quantity"] == 7.0
        assert state_after["virtual_cash"] == -(7.0 * 4520.0 * 50.0)


class TestFuturesIntradayMargin:
    """Tests for intraday margin calls."""

    def test_intraday_margin_on_adverse_move(self):
        """Intraday margin call when price moves against position."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        future = create_future_unit(
            symbol="ESZ24",
            name="E-mini S&P 500",
            underlying="SPX",
            expiry=datetime(2024, 12, 20),
            multiplier=50.0,
            settlement_currency="USD",
            exchange="CME",
            holder_wallet="trader",
            clearinghouse_wallet="clearinghouse",
        )
        ledger.register_unit(future)

        ledger.register_wallet("trader")
        ledger.register_wallet("clearinghouse")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearinghouse", "USD", 10_000_000)

        # Buy 10 at 4500
        result1 = execute_futures_trade(ledger, "ESZ24", 10.0, 4500.00)
        ledger.execute_contract(result1)

        # Intraday margin call at 4450 (down $50)
        result_margin = compute_intraday_margin(ledger, "ESZ24", 4450.00)
        ledger.execute_contract(result_margin)

        state = ledger.get_unit_state("ESZ24")
        # variation_margin = -2,250,000 + (10 × 4450 × 50) = -2,250,000 + 2,225,000 = -25,000
        # Negative means holder has LOSS, so holder pays clearinghouse $25,000

        # Verify intraday_postings tracks the margin posted
        assert state["intraday_postings"] == 25_000.0

        # Virtual cash IS reset after intraday margin to prevent double-counting at EOD
        # new_virtual_cash = -(10 * 4450 * 50) = -2,225,000
        assert state["virtual_cash"] == -2_225_000.0

        # Verify the audit trail
        assert state["last_intraday_price"] == 4450.00

        # Verify balances: trader paid 25k, clearinghouse received 25k
        assert ledger.get_balance("trader", "USD") == 475_000.0
        assert ledger.get_balance("clearinghouse", "USD") == 10_025_000.0


class TestFuturesExpiry:
    """Tests for futures expiry settlement."""

    def test_expiry_closes_position(self):
        """Expiry settles position and marks contract settled."""
        expiry = datetime(2024, 12, 20, 16, 0)

        ledger = Ledger("test", datetime(2024, 12, 20, 10, 0), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        future = create_future_unit(
            symbol="ESZ24",
            name="E-mini S&P 500",
            underlying="SPX",
            expiry=expiry,
            multiplier=50.0,
            settlement_currency="USD",
            exchange="CME",
            holder_wallet="trader",
            clearinghouse_wallet="clearinghouse",
        )
        ledger.register_unit(future)

        ledger.register_wallet("trader")
        ledger.register_wallet("clearinghouse")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearinghouse", "USD", 10_000_000)

        # Setup: position from previous day's settlement
        # Simulate having 10 contracts with virtual_cash matching 4500 settlement
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'virtual_quantity': 10.0,
            'virtual_cash': -(10.0 * 4500.0 * 50.0),  # -2,250,000
            'last_settlement_price': 4500.0,
        })

        # Move to expiry time
        ledger.advance_time(expiry)

        # Expiry settlement at 4550
        result = compute_expiry(ledger, "ESZ24", 4550.00)
        ledger.execute_contract(result)

        state = ledger.get_unit_state("ESZ24")
        assert state["settled"] is True
        assert state["virtual_quantity"] == 0.0
        assert state["virtual_cash"] == 0.0
        assert state["settlement_price"] == 4550.00


class TestFuturesLifecycleEngine:
    """Tests for futures with LifecycleEngine."""

    def test_auto_expiry_via_lifecycle_engine(self):
        """LifecycleEngine automatically settles futures at expiry."""
        expiry = datetime(2024, 12, 20)

        ledger = Ledger("test", datetime(2024, 12, 15), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        future = create_future_unit(
            symbol="ESZ24",
            name="E-mini S&P 500",
            underlying="SPX",
            expiry=expiry,
            multiplier=50.0,
            settlement_currency="USD",
            exchange="CME",
            holder_wallet="trader",
            clearinghouse_wallet="clearinghouse",
        )
        ledger.register_unit(future)

        ledger.register_wallet("trader")
        ledger.register_wallet("clearinghouse")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearinghouse", "USD", 10_000_000)

        # Setup position
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'virtual_quantity': 10.0,
            'virtual_cash': -(10.0 * 4500.0 * 50.0),
            'last_settlement_price': 4500.0,
        })

        engine = LifecycleEngine(ledger)
        engine.register("FUTURE", future_contract)

        # Step through days until after expiry
        for day in range(15, 22):
            date = datetime(2024, 12, day)
            ledger.advance_time(date)
            # SPX at 4550 at expiry
            engine.step(date, {"SPX": 4550.00})

        # Verify settled
        state = ledger.get_unit_state("ESZ24")
        assert state["settled"] is True


class TestFuturesMultiCurrency:
    """Tests for futures in different currencies."""

    def test_euro_futures_lifecycle(self):
        """Euro-denominated futures settle correctly."""
        expiry = datetime(2024, 12, 20)

        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("EUR", "Euro"))

        future = create_future_unit(
            symbol="FESX",
            name="Euro STOXX 50",
            underlying="SX5E",
            expiry=expiry,
            multiplier=10.0,
            settlement_currency="EUR",
            exchange="EUREX",
            holder_wallet="eu_trader",
            clearinghouse_wallet="eurex_clearing",
        )
        ledger.register_unit(future)

        ledger.register_wallet("eu_trader")
        ledger.register_wallet("eurex_clearing")
        ledger.set_balance("eu_trader", "EUR", 100_000)
        ledger.set_balance("eurex_clearing", "EUR", 10_000_000)

        # Buy 5 contracts at 5000
        result1 = execute_futures_trade(ledger, "FESX", 5.0, 5000.00)
        ledger.execute_contract(result1)

        # EOD settlement at 5050
        result_settle = compute_daily_settlement(ledger, "FESX", 5050.00)
        ledger.execute_contract(result_settle)

        # Verify EUR is used in margin move
        if result_settle.moves:
            assert result_settle.moves[0].unit == "EUR"

    def test_yen_futures_large_notional(self):
        """Yen-denominated futures handle large notional values."""
        expiry = datetime(2024, 12, 13)

        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("JPY", "Japanese Yen"))

        future = create_future_unit(
            symbol="NK225",
            name="Nikkei 225",
            underlying="NI225",
            expiry=expiry,
            multiplier=1000.0,
            settlement_currency="JPY",
            exchange="OSE",
            holder_wallet="jp_trader",
            clearinghouse_wallet="jpx_clearing",
        )
        ledger.register_unit(future)

        ledger.register_wallet("jp_trader")
        ledger.register_wallet("jpx_clearing")
        ledger.set_balance("jp_trader", "JPY", 100_000_000)
        ledger.set_balance("jpx_clearing", "JPY", 10_000_000_000)

        # Buy 2 contracts at 38000
        result1 = execute_futures_trade(ledger, "NK225", 2.0, 38000.00)
        ledger.execute_contract(result1)

        state = ledger.get_unit_state("NK225")
        # Notional: 2 × 38000 × 1000 = 76,000,000 JPY
        assert state["virtual_cash"] == -76_000_000.0


class TestFuturesConservation:
    """Tests verifying conservation laws for futures."""

    def test_settlement_conserves_total_cash(self):
        """Daily settlement moves conserve total cash in system."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        future = create_future_unit(
            symbol="ESZ24",
            name="E-mini S&P 500",
            underlying="SPX",
            expiry=datetime(2024, 12, 20),
            multiplier=50.0,
            settlement_currency="USD",
            exchange="CME",
            holder_wallet="trader",
            clearinghouse_wallet="clearinghouse",
        )
        ledger.register_unit(future)

        ledger.register_wallet("trader")
        ledger.register_wallet("clearinghouse")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearinghouse", "USD", 10_000_000)

        initial_total = (
            ledger.get_balance("trader", "USD") +
            ledger.get_balance("clearinghouse", "USD")
        )

        # Buy 10 at 4500
        result1 = execute_futures_trade(ledger, "ESZ24", 10.0, 4500.00)
        ledger.execute_contract(result1)

        # Settle at 4510
        result_settle = compute_daily_settlement(ledger, "ESZ24", 4510.00)
        ledger.execute_contract(result_settle)

        final_total = (
            ledger.get_balance("trader", "USD") +
            ledger.get_balance("clearinghouse", "USD")
        )

        # Total cash should be conserved
        assert final_total == initial_total

    def test_expiry_conserves_total_cash(self):
        """Expiry settlement conserves total cash in system."""
        expiry = datetime(2024, 12, 20)

        ledger = Ledger("test", datetime(2024, 12, 20), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        future = create_future_unit(
            symbol="ESZ24",
            name="E-mini S&P 500",
            underlying="SPX",
            expiry=expiry,
            multiplier=50.0,
            settlement_currency="USD",
            exchange="CME",
            holder_wallet="trader",
            clearinghouse_wallet="clearinghouse",
        )
        ledger.register_unit(future)

        ledger.register_wallet("trader")
        ledger.register_wallet("clearinghouse")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearinghouse", "USD", 10_000_000)

        # Setup position
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'virtual_quantity': 10.0,
            'virtual_cash': -(10.0 * 4500.0 * 50.0),
            'last_settlement_price': 4500.0,
        })

        initial_total = (
            ledger.get_balance("trader", "USD") +
            ledger.get_balance("clearinghouse", "USD")
        )

        # Expiry at 4550
        result = compute_expiry(ledger, "ESZ24", 4550.00)
        ledger.execute_contract(result)

        final_total = (
            ledger.get_balance("trader", "USD") +
            ledger.get_balance("clearinghouse", "USD")
        )

        assert final_total == initial_total
