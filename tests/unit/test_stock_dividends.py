"""
Tests for stock dividend processing with DeferredCash model.

The dividend model:
- On ex_date: Create DeferredCash entitlements for each holder
- On payment_date: DeferredCash settles automatically via lifecycle engine

State is minimal: just 'processed_dividends' list of dividend keys that have been processed.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass
from typing import Dict, Set

from ledger.core import (
    LedgerView, Unit, UnitState, UNIT_TYPE_STOCK, QUANTITY_EPSILON, _freeze_state,
)
from ledger.units.stock import (
    Dividend, process_dividends, compute_dividend_entitlements,
    add_dividend, remove_dividend,
    DividendEntitlement,
)


# =============================================================================
# FAKE VIEW - Minimal implementation of LedgerView protocol
# =============================================================================

@dataclass
class FakeView:
    """Minimal LedgerView for testing."""
    _current_time: datetime
    _positions: Dict[str, Dict[str, float]]  # {symbol: {wallet: balance}}
    _unit_states: Dict[str, dict]
    _units: Dict[str, Unit]

    @property
    def current_time(self) -> datetime:
        return self._current_time

    def get_balance(self, wallet_id: str, unit_symbol: str) -> float:
        return self._positions.get(unit_symbol, {}).get(wallet_id, Decimal("0.0"))

    def get_unit_state(self, unit_symbol: str) -> UnitState:
        return dict(self._unit_states.get(unit_symbol, {}))

    def get_positions(self, unit_symbol: str) -> Dict[str, float]:
        return dict(self._positions.get(unit_symbol, {}))

    def list_wallets(self) -> Set[str]:
        wallets = set()
        for positions in self._positions.values():
            wallets.update(positions.keys())
        return wallets

    def get_unit(self, symbol: str) -> Unit:
        return self._units.get(symbol)


def make_stock_unit(symbol: str, issuer: str, currency: str, schedule=None) -> Unit:
    """Create a stock unit with optional dividend schedule."""
    return Unit(
        symbol=symbol,
        name=f"{symbol} Stock",
        unit_type=UNIT_TYPE_STOCK,
        _frozen_state=_freeze_state({
            'issuer': issuer,
            'currency': currency,
            'dividend_schedule': schedule or [],
            'processed_dividends': [],
        })
    )


# =============================================================================
# DIVIDEND DATACLASS TESTS
# =============================================================================

class TestDividend:
    """Tests for the Dividend dataclass."""

    def test_valid_dividend(self):
        """A dividend with valid dates and amount is created."""
        d = Dividend(
            ex_date=datetime(2024, 3, 1),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        assert d.key == "2024-03-01"
        assert d.amount_per_share == Decimal("0.50")

    def test_payment_before_ex_date_fails(self):
        """Payment date before ex_date is invalid."""
        with pytest.raises(ValueError, match="payment_date must be >= ex_date"):
            Dividend(
                ex_date=datetime(2024, 3, 15),
                payment_date=datetime(2024, 3, 1),
                amount_per_share=0.50,
                currency="USD",
            )

    def test_zero_amount_fails(self):
        """Zero dividend amount is invalid."""
        with pytest.raises(ValueError, match="amount_per_share must be positive"):
            Dividend(
                ex_date=datetime(2024, 3, 1),
                payment_date=datetime(2024, 3, 15),
                amount_per_share=0.0,
                currency="USD",
            )

    def test_negative_amount_fails(self):
        """Negative dividend amount is invalid."""
        with pytest.raises(ValueError, match="amount_per_share must be positive"):
            Dividend(
                ex_date=datetime(2024, 3, 1),
                payment_date=datetime(2024, 3, 15),
                amount_per_share=-0.50,
                currency="USD",
            )

    def test_same_day_ex_and_payment(self):
        """Ex-date and payment date can be the same."""
        d = Dividend(
            ex_date=datetime(2024, 3, 15),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        assert d.key == "2024-03-15"


# =============================================================================
# PURE FUNCTION TESTS - compute_dividend_entitlements
# =============================================================================

class TestComputeDividendEntitlements:
    """Tests for the pure compute_dividend_entitlements function."""

    def test_before_ex_date_returns_empty(self):
        """Before ex_date, no entitlements are created."""
        div = Dividend(
            ex_date=datetime(2024, 3, 10),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        positions = {"alice": Decimal("100.0"), "bob": Decimal("50.0")}

        entitlements, new_processed = compute_dividend_entitlements(
            div=div,
            today=datetime(2024, 3, 5).date(),  # Before ex_date
            positions=positions,
            processed=frozenset(),
            issuer="treasury",
            stock_symbol="AAPL",
        )

        assert entitlements == []
        assert new_processed == frozenset()

    def test_on_ex_date_creates_entitlements(self):
        """On ex_date, entitlements are created for each holder."""
        div = Dividend(
            ex_date=datetime(2024, 3, 10),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        positions = {"alice": Decimal("100.0"), "bob": Decimal("50.0")}

        entitlements, new_processed = compute_dividend_entitlements(
            div=div,
            today=datetime(2024, 3, 10).date(),  # On ex_date
            positions=positions,
            processed=frozenset(),
            issuer="treasury",
            stock_symbol="AAPL",
        )

        assert len(entitlements) == 2
        assert "2024-03-10" in new_processed

        # Check entitlement amounts
        alice_ent = next(e for e in entitlements if e.payee_wallet == "alice")
        bob_ent = next(e for e in entitlements if e.payee_wallet == "bob")

        assert alice_ent.amount == Decimal("50.0")  # 100 * 0.50
        assert bob_ent.amount == Decimal("25.0")   # 50 * 0.50
        assert alice_ent.currency == "USD"
        assert alice_ent.payer_wallet == "treasury"

    def test_already_processed_returns_empty(self):
        """Already processed dividend returns empty."""
        div = Dividend(
            ex_date=datetime(2024, 3, 10),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        positions = {"alice": Decimal("100.0")}

        entitlements, new_processed = compute_dividend_entitlements(
            div=div,
            today=datetime(2024, 3, 10).date(),
            positions=positions,
            processed=frozenset(["2024-03-10"]),  # Already processed
            issuer="treasury",
            stock_symbol="AAPL",
        )

        assert entitlements == []
        assert new_processed == frozenset(["2024-03-10"])

    def test_issuer_excluded(self):
        """Issuer doesn't get entitlement on own shares."""
        div = Dividend(
            ex_date=datetime(2024, 3, 10),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        positions = {"treasury": Decimal("1000.0"), "alice": Decimal("100.0")}

        entitlements, new_processed = compute_dividend_entitlements(
            div=div,
            today=datetime(2024, 3, 10).date(),
            positions=positions,
            processed=frozenset(),
            issuer="treasury",
            stock_symbol="AAPL",
        )

        assert len(entitlements) == 1
        assert entitlements[0].payee_wallet == "alice"

    def test_zero_shares_excluded(self):
        """Wallet with zero shares gets no entitlement."""
        div = Dividend(
            ex_date=datetime(2024, 3, 10),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        positions = {"alice": Decimal("0.0"), "bob": Decimal("100.0")}

        entitlements, new_processed = compute_dividend_entitlements(
            div=div,
            today=datetime(2024, 3, 10).date(),
            positions=positions,
            processed=frozenset(),
            issuer="treasury",
            stock_symbol="AAPL",
        )

        assert len(entitlements) == 1
        assert entitlements[0].payee_wallet == "bob"

    def test_multi_currency_dividend(self):
        """Dividend currency can differ from stock currency."""
        div = Dividend(
            ex_date=datetime(2024, 3, 10),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="GBP",  # HSBC pays GBP dividends
        )
        positions = {"alice": Decimal("100.0")}

        entitlements, _ = compute_dividend_entitlements(
            div=div,
            today=datetime(2024, 3, 10).date(),
            positions=positions,
            processed=frozenset(),
            issuer="hsbc_treasury",
            stock_symbol="HSBC",
        )

        assert len(entitlements) == 1
        assert entitlements[0].currency == "GBP"
        assert entitlements[0].amount == 50.0


# =============================================================================
# PROCESS DIVIDENDS ORCHESTRATOR TESTS
# =============================================================================

class TestProcessDividends:
    """Tests for the process_dividends orchestrator function."""

    def test_no_schedule_returns_empty(self):
        """No dividend schedule produces empty transaction."""
        unit = make_stock_unit("AAPL", "treasury", "USD", schedule=[])
        view = FakeView(
            _current_time=datetime(2024, 3, 15),
            _positions={"AAPL": {"alice": Decimal("100.0")}},
            _unit_states={"AAPL": unit.state},
            _units={"AAPL": unit},
        )

        result = process_dividends(view, "AAPL", datetime(2024, 3, 15))
        assert result.is_empty()

    def test_before_ex_date_returns_empty(self):
        """Before ex_date, no entitlements are created."""
        div = Dividend(
            ex_date=datetime(2024, 3, 10),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        unit = make_stock_unit("AAPL", "treasury", "USD", schedule=[div])
        view = FakeView(
            _current_time=datetime(2024, 3, 5),  # Before ex_date
            _positions={"AAPL": {"alice": Decimal("100.0")}},
            _unit_states={"AAPL": unit.state},
            _units={"AAPL": unit},
        )

        result = process_dividends(view, "AAPL", datetime(2024, 3, 5))
        assert result.is_empty()

    def test_on_ex_date_creates_deferred_cash(self):
        """On ex_date, DeferredCash units are created for each holder."""
        div = Dividend(
            ex_date=datetime(2024, 3, 10),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        unit = make_stock_unit("AAPL", "treasury", "USD", schedule=[div])
        view = FakeView(
            _current_time=datetime(2024, 3, 10),
            _positions={"AAPL": {"alice": Decimal("100.0"), "bob": Decimal("50.0")}},
            _unit_states={"AAPL": unit.state},
            _units={"AAPL": unit},
        )

        result = process_dividends(view, "AAPL", datetime(2024, 3, 10))

        # Should have moves (entitlements) and units_to_create (DeferredCash)
        assert len(result.moves) == 2
        assert len(result.units_to_create) == 2

        # Check state update marks dividend as processed
        assert len(result.state_changes) == 1
        assert "2024-03-10" in result.state_changes[0].new_state["processed_dividends"]

        # Check DeferredCash amounts
        alice_dc = next(u for u in result.units_to_create if "alice" in u.symbol)
        bob_dc = next(u for u in result.units_to_create if "bob" in u.symbol)

        assert alice_dc.state["amount"] == 50.0  # 100 * 0.50
        assert bob_dc.state["amount"] == 25.0   # 50 * 0.50

    def test_idempotent_processing(self):
        """Re-processing ex_date doesn't create duplicate entitlements."""
        div = Dividend(
            ex_date=datetime(2024, 3, 10),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        # State shows dividend already processed
        state = {
            'issuer': 'treasury',
            'currency': 'USD',
            'dividend_schedule': [div],
            'processed_dividends': ['2024-03-10'],
        }
        unit = Unit(symbol="AAPL", name="Apple", unit_type=UNIT_TYPE_STOCK, _frozen_state=_freeze_state(state))
        view = FakeView(
            _current_time=datetime(2024, 3, 10),
            _positions={"AAPL": {"alice": Decimal("100.0")}},
            _unit_states={"AAPL": state},
            _units={"AAPL": unit},
        )

        result = process_dividends(view, "AAPL", datetime(2024, 3, 10))
        assert result.is_empty()

    def test_no_issuer_raises(self):
        """Missing issuer raises ValueError."""
        div = Dividend(
            ex_date=datetime(2024, 3, 10),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        state = {
            'currency': 'USD',
            'dividend_schedule': [div],
            'processed_dividends': [],
            # No issuer!
        }
        unit = Unit(symbol="AAPL", name="Apple", unit_type=UNIT_TYPE_STOCK, _frozen_state=_freeze_state(state))
        view = FakeView(
            _current_time=datetime(2024, 3, 10),
            _positions={"AAPL": {"alice": Decimal("100.0")}},
            _unit_states={"AAPL": state},
            _units={"AAPL": unit},
        )

        with pytest.raises(ValueError, match="no issuer defined"):
            process_dividends(view, "AAPL", datetime(2024, 3, 10))

    def test_multiple_dividends_late_processing(self):
        """If lifecycle engine skips dates, all due dividends are processed."""
        div1 = Dividend(
            ex_date=datetime(2024, 3, 1),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.25,
            currency="USD",
        )
        div2 = Dividend(
            ex_date=datetime(2024, 6, 1),
            payment_date=datetime(2024, 6, 15),
            amount_per_share=0.30,
            currency="USD",
        )
        unit = make_stock_unit("AAPL", "treasury", "USD", schedule=[div1, div2])
        view = FakeView(
            _current_time=datetime(2024, 7, 1),  # Way after both
            _positions={"AAPL": {"alice": Decimal("100.0")}},
            _unit_states={"AAPL": unit.state},
            _units={"AAPL": unit},
        )

        result = process_dividends(view, "AAPL", datetime(2024, 7, 1))

        # Both dividends should create entitlements
        assert len(result.units_to_create) == 2
        total = sum(u.state["amount"] for u in result.units_to_create)
        assert total == Decimal("55.0")  # 100 * 0.25 + 100 * 0.30


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================

class TestHelperFunctions:
    """Tests for add_dividend, remove_dividend."""

    def test_add_dividend(self):
        """add_dividend adds to schedule."""
        state = {'dividend_schedule': [], 'issuer': 'treasury'}
        div = Dividend(
            ex_date=datetime(2024, 3, 1),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )

        new_state = add_dividend(state, div)

        assert len(new_state['dividend_schedule']) == 1
        assert new_state['dividend_schedule'][0] == div
        # Original unchanged (pure function)
        assert len(state['dividend_schedule']) == 0

    def test_remove_dividend(self):
        """remove_dividend removes by ex_date."""
        div = Dividend(
            ex_date=datetime(2024, 3, 1),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=0.50,
            currency="USD",
        )
        state = {'dividend_schedule': [div], 'issuer': 'treasury'}

        new_state = remove_dividend(state, datetime(2024, 3, 1))

        assert len(new_state['dividend_schedule']) == 0
        # Original unchanged
        assert len(state['dividend_schedule']) == 1
