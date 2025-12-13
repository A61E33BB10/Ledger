"""
test_portfolio_swaps.py - Unit tests for Portfolio Swaps (Total Return Swaps)

Tests:
- Factory function (create_portfolio_swap) validation
- NAV calculation (compute_portfolio_nav)
- Funding amount calculation (compute_funding_amount)
- Reset settlement (compute_swap_reset)
- Termination (compute_termination)
- transact() interface
- SmartContract (portfolio_swap_contract)
- Multi-period scenarios
- Edge cases and conservation laws

Target: 25+ comprehensive tests
"""

import pytest
from datetime import datetime, timedelta
from tests.fake_view import FakeView
from ledger.units.portfolio_swap import (
    create_portfolio_swap,
    compute_portfolio_nav,
    compute_funding_amount,
    compute_swap_reset,
    compute_termination,
    transact,
    portfolio_swap_contract,
)
from ledger.core import UNIT_TYPE_PORTFOLIO_SWAP


# ============================================================================
# CREATE PORTFOLIO SWAP TESTS
# ============================================================================

class TestCreatePortfolioSwap:
    """Tests for create_portfolio_swap factory function."""

    def test_create_basic_swap(self):
        """Create a basic portfolio swap with valid parameters."""
        swap = create_portfolio_swap(
            symbol="TRS_TECH_2025",
            name="Tech Portfolio TRS Q1 2025",
            reference_portfolio={"AAPL": 0.4, "GOOG": 0.35, "MSFT": 0.25},
            notional=1_000_000.0,
            funding_spread=0.0050,  # 50 bps
            reset_schedule=[datetime(2025, 1, 15), datetime(2025, 4, 15)],
            payer_wallet="dealer",
            receiver_wallet="hedge_fund",
            currency="USD",
        )

        assert swap.symbol == "TRS_TECH_2025"
        assert swap.name == "Tech Portfolio TRS Q1 2025"
        assert swap.unit_type == UNIT_TYPE_PORTFOLIO_SWAP

        state = swap._state
        assert state["reference_portfolio"] == {"AAPL": 0.4, "GOOG": 0.35, "MSFT": 0.25}
        assert state["notional"] == 1_000_000.0
        assert state["funding_spread"] == 0.0050
        assert state["payer_wallet"] == "dealer"
        assert state["receiver_wallet"] == "hedge_fund"
        assert state["currency"] == "USD"
        assert state["terminated"] is False
        assert state["next_reset_index"] == 0

    def test_create_swap_with_initial_nav(self):
        """Create swap with pre-set initial NAV."""
        swap = create_portfolio_swap(
            symbol="TRS_SPY",
            name="S&P 500 TRS",
            reference_portfolio={"SPY": 1.0},
            notional=5_000_000.0,
            funding_spread=0.0025,
            reset_schedule=[datetime(2025, 3, 31)],
            payer_wallet="bank",
            receiver_wallet="client",
            currency="USD",
            initial_nav=5_000_000.0,
        )

        assert swap._state["last_nav"] == 5_000_000.0

    def test_create_swap_with_issue_date(self):
        """Create swap with explicit issue date."""
        issue = datetime(2025, 1, 1)
        swap = create_portfolio_swap(
            symbol="TRS_BONDS",
            name="Bond Portfolio TRS",
            reference_portfolio={"TLT": 0.6, "IEF": 0.4},
            notional=10_000_000.0,
            funding_spread=0.0030,
            reset_schedule=[datetime(2025, 6, 30)],
            payer_wallet="dealer",
            receiver_wallet="pension",
            currency="USD",
            issue_date=issue,
        )

        assert swap._state["issue_date"] == issue
        assert swap._state["last_reset_date"] == issue

    def test_create_euro_denominated_swap(self):
        """Create a Euro-denominated portfolio swap."""
        swap = create_portfolio_swap(
            symbol="TRS_EU",
            name="Euro Equities TRS",
            reference_portfolio={"SAP": 0.5, "ASML": 0.5},
            notional=2_000_000.0,
            funding_spread=0.0040,
            reset_schedule=[datetime(2025, 6, 30)],
            payer_wallet="eu_bank",
            receiver_wallet="eu_fund",
            currency="EUR",
        )

        assert swap._state["currency"] == "EUR"

    def test_weights_not_summing_to_one_raises(self):
        """Portfolio weights not summing to 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={"AAPL": 0.5, "GOOG": 0.3},  # Sum = 0.8
                notional=1_000_000.0,
                funding_spread=0.005,
                reset_schedule=[datetime(2025, 3, 31)],
                payer_wallet="dealer",
                receiver_wallet="client",
                currency="USD",
            )

    def test_weights_exceeding_one_raises(self):
        """Portfolio weights exceeding 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={"AAPL": 0.6, "GOOG": 0.6},  # Sum = 1.2
                notional=1_000_000.0,
                funding_spread=0.005,
                reset_schedule=[datetime(2025, 3, 31)],
                payer_wallet="dealer",
                receiver_wallet="client",
                currency="USD",
            )

    def test_empty_portfolio_raises(self):
        """Empty reference portfolio raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={},
                notional=1_000_000.0,
                funding_spread=0.005,
                reset_schedule=[datetime(2025, 3, 31)],
                payer_wallet="dealer",
                receiver_wallet="client",
                currency="USD",
            )

    def test_negative_weight_raises(self):
        """Negative portfolio weight raises ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={"AAPL": 1.2, "GOOG": -0.2},  # Negative weight
                notional=1_000_000.0,
                funding_spread=0.005,
                reset_schedule=[datetime(2025, 3, 31)],
                payer_wallet="dealer",
                receiver_wallet="client",
                currency="USD",
            )

    def test_non_positive_notional_raises(self):
        """Zero or negative notional raises ValueError."""
        with pytest.raises(ValueError, match="notional must be positive"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={"AAPL": 1.0},
                notional=0.0,
                funding_spread=0.005,
                reset_schedule=[datetime(2025, 3, 31)],
                payer_wallet="dealer",
                receiver_wallet="client",
                currency="USD",
            )

        with pytest.raises(ValueError, match="notional must be positive"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={"AAPL": 1.0},
                notional=-1_000_000.0,
                funding_spread=0.005,
                reset_schedule=[datetime(2025, 3, 31)],
                payer_wallet="dealer",
                receiver_wallet="client",
                currency="USD",
            )

    def test_negative_funding_spread_raises(self):
        """Negative funding spread raises ValueError."""
        with pytest.raises(ValueError, match="funding_spread cannot be negative"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={"AAPL": 1.0},
                notional=1_000_000.0,
                funding_spread=-0.005,
                reset_schedule=[datetime(2025, 3, 31)],
                payer_wallet="dealer",
                receiver_wallet="client",
                currency="USD",
            )

    def test_empty_reset_schedule_raises(self):
        """Empty reset schedule raises ValueError."""
        with pytest.raises(ValueError, match="reset_schedule cannot be empty"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={"AAPL": 1.0},
                notional=1_000_000.0,
                funding_spread=0.005,
                reset_schedule=[],
                payer_wallet="dealer",
                receiver_wallet="client",
                currency="USD",
            )

    def test_same_wallets_raises(self):
        """Same payer and receiver wallet raises ValueError."""
        with pytest.raises(ValueError, match="must be different"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={"AAPL": 1.0},
                notional=1_000_000.0,
                funding_spread=0.005,
                reset_schedule=[datetime(2025, 3, 31)],
                payer_wallet="same_wallet",
                receiver_wallet="same_wallet",
                currency="USD",
            )

    def test_empty_wallet_raises(self):
        """Empty wallet names raise ValueError."""
        with pytest.raises(ValueError, match="payer_wallet cannot be empty"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={"AAPL": 1.0},
                notional=1_000_000.0,
                funding_spread=0.005,
                reset_schedule=[datetime(2025, 3, 31)],
                payer_wallet="",
                receiver_wallet="client",
                currency="USD",
            )

    def test_empty_currency_raises(self):
        """Empty currency raises ValueError."""
        with pytest.raises(ValueError, match="currency cannot be empty"):
            create_portfolio_swap(
                symbol="BAD",
                name="Bad Swap",
                reference_portfolio={"AAPL": 1.0},
                notional=1_000_000.0,
                funding_spread=0.005,
                reset_schedule=[datetime(2025, 3, 31)],
                payer_wallet="dealer",
                receiver_wallet="client",
                currency="",
            )


# ============================================================================
# COMPUTE PORTFOLIO NAV TESTS
# ============================================================================

class TestComputePortfolioNav:
    """Tests for compute_portfolio_nav function."""

    def test_single_asset_nav(self):
        """NAV calculation with single asset."""
        weights = {"AAPL": 1.0}
        prices = {"AAPL": 150.0}
        notional = 1_000_000.0

        nav = compute_portfolio_nav(weights, prices, notional)

        # NAV = 1.0 * 150 * 1_000_000 / 100 = 1,500,000
        assert nav == pytest.approx(1_500_000.0, rel=1e-6)

    def test_multi_asset_nav(self):
        """NAV calculation with multiple assets."""
        weights = {"AAPL": 0.5, "GOOG": 0.3, "MSFT": 0.2}
        prices = {"AAPL": 150.0, "GOOG": 100.0, "MSFT": 200.0}
        notional = 1_000_000.0

        nav = compute_portfolio_nav(weights, prices, notional)

        # weighted_price = 0.5*150 + 0.3*100 + 0.2*200 = 75 + 30 + 40 = 145
        # NAV = 145 * 1_000_000 / 100 = 1,450,000
        assert nav == pytest.approx(1_450_000.0, rel=1e-6)

    def test_nav_with_equal_weights(self):
        """NAV calculation with equal weights."""
        weights = {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}
        prices = {"A": 100.0, "B": 100.0, "C": 100.0, "D": 100.0}
        notional = 1_000_000.0

        nav = compute_portfolio_nav(weights, prices, notional)

        # weighted_price = 0.25*100 * 4 = 100
        # NAV = 100 * 1_000_000 / 100 = 1,000,000
        assert nav == pytest.approx(1_000_000.0, rel=1e-6)

    def test_missing_price_raises(self):
        """Missing price for portfolio asset raises ValueError."""
        weights = {"AAPL": 0.5, "GOOG": 0.5}
        prices = {"AAPL": 150.0}  # Missing GOOG

        with pytest.raises(ValueError, match="Missing price for portfolio asset"):
            compute_portfolio_nav(weights, prices, 1_000_000.0)


# ============================================================================
# COMPUTE FUNDING AMOUNT TESTS
# ============================================================================

class TestComputeFundingAmount:
    """Tests for compute_funding_amount function."""

    def test_quarterly_funding(self):
        """Funding amount for a quarter (~91 days)."""
        notional = 1_000_000.0
        spread = 0.005  # 50 bps
        days = 91

        funding = compute_funding_amount(notional, spread, days)

        # funding = 1_000_000 * 0.005 * (91/365) = 1,246.58
        expected = 1_000_000.0 * 0.005 * (91 / 365)
        assert funding == pytest.approx(expected, rel=1e-6)

    def test_annual_funding(self):
        """Funding amount for a full year."""
        notional = 1_000_000.0
        spread = 0.01  # 100 bps
        days = 365

        funding = compute_funding_amount(notional, spread, days)

        # funding = 1_000_000 * 0.01 * (365/365) = 10,000
        assert funding == pytest.approx(10_000.0, rel=1e-6)

    def test_zero_days_funding(self):
        """Funding amount for zero days is zero."""
        funding = compute_funding_amount(1_000_000.0, 0.005, 0)
        assert funding == 0.0

    def test_zero_spread_funding(self):
        """Funding amount with zero spread is zero."""
        funding = compute_funding_amount(1_000_000.0, 0.0, 90)
        assert funding == 0.0

    def test_negative_days_raises(self):
        """Negative days raises ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            compute_funding_amount(1_000_000.0, 0.005, -10)


# ============================================================================
# COMPUTE SWAP RESET TESTS
# ============================================================================

class TestComputeSwapReset:
    """Tests for compute_swap_reset function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.swap_state = {
            'reference_portfolio': {'AAPL': 0.5, 'GOOG': 0.5},
            'notional': 1_000_000.0,
            'last_nav': 1_000_000.0,
            'funding_spread': 0.005,  # 50 bps
            'reset_schedule': [datetime(2025, 3, 31), datetime(2025, 6, 30)],
            'last_reset_date': datetime(2025, 1, 1),
            'payer_wallet': 'dealer',
            'receiver_wallet': 'hedge_fund',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
        }

    def test_positive_return_settlement(self):
        """Positive portfolio return - payer pays receiver."""
        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 3, 31),
        )

        # NAV increased from 1M to 1.05M (5% return)
        result = compute_swap_reset(view, 'TRS_TECH', 1_050_000.0, 0.005, 90)

        assert len(result.moves) == 1
        move = result.moves[0]

        # return_amount = 1M * 0.05 = 50,000
        # funding_amount = 1M * 0.005 * (90/365) = 1,232.88
        # net = 50,000 - 1,232.88 = 48,767.12
        expected_funding = 1_000_000.0 * 0.005 * (90 / 365)
        expected_net = 50_000.0 - expected_funding

        assert move.source == 'dealer'
        assert move.dest == 'hedge_fund'
        assert move.quantity == pytest.approx(expected_net, rel=1e-6)
        assert move.unit_symbol == 'USD'

    def test_negative_return_settlement(self):
        """Negative portfolio return - receiver pays payer."""
        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 3, 31),
        )

        # NAV decreased from 1M to 0.95M (-5% return)
        result = compute_swap_reset(view, 'TRS_TECH', 950_000.0, 0.005, 90)

        assert len(result.moves) == 1
        move = result.moves[0]

        # return_amount = 1M * (-0.05) = -50,000
        # funding_amount = 1M * 0.005 * (90/365) = 1,232.88
        # net = -50,000 - 1,232.88 = -51,232.88
        expected_funding = 1_000_000.0 * 0.005 * (90 / 365)
        expected_net = -50_000.0 - expected_funding

        # Receiver pays payer (net is negative)
        assert move.source == 'hedge_fund'
        assert move.dest == 'dealer'
        assert move.quantity == pytest.approx(-expected_net, rel=1e-6)

    def test_funding_exceeds_return(self):
        """Funding cost exceeds positive return - receiver pays net."""
        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 3, 31),
        )

        # Tiny positive return (0.1% = 1000), large funding period (365 days)
        # return_amount = 1M * 0.001 = 1,000
        # funding_amount = 1M * 0.005 * 1 = 5,000
        # net = 1,000 - 5,000 = -4,000 (receiver pays)
        result = compute_swap_reset(view, 'TRS_TECH', 1_001_000.0, 0.005, 365)

        assert len(result.moves) == 1
        move = result.moves[0]

        assert move.source == 'hedge_fund'
        assert move.dest == 'dealer'
        assert move.quantity == pytest.approx(4_000.0, rel=1e-6)

    def test_reset_updates_state(self):
        """Reset updates last_nav, next_reset_index, and history."""
        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 3, 31),
        )

        result = compute_swap_reset(view, 'TRS_TECH', 1_050_000.0, 0.005, 90)
        sc = next(d for d in result.state_changes if d.unit == "TRS_TECH")

        assert sc.new_state['last_nav'] == 1_050_000.0
        assert sc.new_state['last_reset_date'] == datetime(2025, 3, 31)
        assert sc.new_state['next_reset_index'] == 1
        assert len(sc.new_state['reset_history']) == 1

        history = sc.new_state['reset_history'][0]
        assert history['reset_number'] == 0
        assert history['last_nav'] == 1_000_000.0
        assert history['current_nav'] == 1_050_000.0
        assert history['portfolio_return'] == pytest.approx(0.05, rel=1e-6)

    def test_reset_on_terminated_swap_returns_empty(self):
        """Reset on terminated swap returns empty result."""
        state = dict(self.swap_state)
        state['terminated'] = True

        view = FakeView(
            balances={},
            states={'TRS_TECH': state},
        )

        result = compute_swap_reset(view, 'TRS_TECH', 1_050_000.0, 0.005, 90)
        assert len(result.moves) == 0
        assert len(result.state_changes) == 0

    def test_reset_without_last_nav_raises(self):
        """Reset without initialized last_nav raises ValueError."""
        state = dict(self.swap_state)
        state['last_nav'] = None

        view = FakeView(
            balances={},
            states={'TRS_TECH': state},
        )

        with pytest.raises(ValueError, match="last_nav not initialized"):
            compute_swap_reset(view, 'TRS_TECH', 1_050_000.0, 0.005, 90)

    def test_zero_nav_change_with_funding(self):
        """Zero NAV change still settles funding amount."""
        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 3, 31),
        )

        # NAV unchanged (1M to 1M)
        result = compute_swap_reset(view, 'TRS_TECH', 1_000_000.0, 0.005, 90)

        assert len(result.moves) == 1
        move = result.moves[0]

        # return_amount = 0
        # funding_amount = 1M * 0.005 * (90/365) = 1,232.88
        # net = -1,232.88 (receiver pays)
        expected_funding = 1_000_000.0 * 0.005 * (90 / 365)

        assert move.source == 'hedge_fund'
        assert move.dest == 'dealer'
        assert move.quantity == pytest.approx(expected_funding, rel=1e-6)

    def test_zero_funding_spread(self):
        """Zero funding spread - only portfolio return settles."""
        state = dict(self.swap_state)
        state['funding_spread'] = 0.0

        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': state},
            time=datetime(2025, 3, 31),
        )

        result = compute_swap_reset(view, 'TRS_TECH', 1_050_000.0, 0.0, 90)

        assert len(result.moves) == 1
        move = result.moves[0]

        # net = 50,000 - 0 = 50,000
        assert move.source == 'dealer'
        assert move.dest == 'hedge_fund'
        assert move.quantity == pytest.approx(50_000.0, rel=1e-6)


# ============================================================================
# COMPUTE TERMINATION TESTS
# ============================================================================

class TestComputeTermination:
    """Tests for compute_termination function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.swap_state = {
            'reference_portfolio': {'AAPL': 0.5, 'GOOG': 0.5},
            'notional': 1_000_000.0,
            'last_nav': 1_000_000.0,
            'funding_spread': 0.005,
            'reset_schedule': [datetime(2025, 3, 31), datetime(2025, 6, 30)],
            'last_reset_date': datetime(2025, 1, 1),
            'payer_wallet': 'dealer',
            'receiver_wallet': 'hedge_fund',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
        }

    def test_termination_with_gain(self):
        """Termination with positive return."""
        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 2, 15),
        )

        result = compute_termination(view, 'TRS_TECH', 1_020_000.0, 0.005, 45)

        assert len(result.moves) == 1
        sc = next(d for d in result.state_changes if d.unit == "TRS_TECH")
        assert sc.new_state['terminated'] is True

        move = result.moves[0]
        # return_amount = 1M * 0.02 = 20,000
        # funding_amount = 1M * 0.005 * (45/365) = 616.44
        # net = 20,000 - 616.44 = 19,383.56
        expected_funding = 1_000_000.0 * 0.005 * (45 / 365)
        expected_net = 20_000.0 - expected_funding

        assert move.source == 'dealer'
        assert move.dest == 'hedge_fund'
        assert move.quantity == pytest.approx(expected_net, rel=1e-6)

    def test_termination_with_loss(self):
        """Termination with negative return."""
        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 2, 15),
        )

        result = compute_termination(view, 'TRS_TECH', 980_000.0, 0.005, 45)

        sc = next(d for d in result.state_changes if d.unit == "TRS_TECH")
        assert sc.new_state['terminated'] is True

        move = result.moves[0]
        # return_amount = 1M * (-0.02) = -20,000
        # funding_amount = 1M * 0.005 * (45/365) = 616.44
        # net = -20,000 - 616.44 = -20,616.44

        assert move.source == 'hedge_fund'
        assert move.dest == 'dealer'

    def test_termination_marks_terminated(self):
        """Termination sets terminated flag and records termination details."""
        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 2, 15),
        )

        result = compute_termination(view, 'TRS_TECH', 1_000_000.0, 0.005, 45)
        sc = next(d for d in result.state_changes if d.unit == "TRS_TECH")

        assert sc.new_state['terminated'] is True
        assert sc.new_state['termination_date'] == datetime(2025, 2, 15)
        assert sc.new_state['termination_nav'] == 1_000_000.0
        assert any(h.get('is_termination') for h in sc.new_state['reset_history'])

    def test_termination_already_terminated_returns_empty(self):
        """Termination on already-terminated swap returns empty."""
        state = dict(self.swap_state)
        state['terminated'] = True

        view = FakeView(
            balances={},
            states={'TRS_TECH': state},
        )

        result = compute_termination(view, 'TRS_TECH', 1_000_000.0, 0.005, 45)
        assert len(result.moves) == 0


# ============================================================================
# TRANSACT INTERFACE TESTS
# ============================================================================

class TestTransact:
    """Tests for transact() unified interface."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.swap_state = {
            'reference_portfolio': {'AAPL': 0.5, 'GOOG': 0.5},
            'notional': 1_000_000.0,
            'last_nav': None,  # Not initialized
            'funding_spread': 0.005,
            'reset_schedule': [datetime(2025, 3, 31)],
            'last_reset_date': None,
            'payer_wallet': 'dealer',
            'receiver_wallet': 'hedge_fund',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
        }

    def test_transact_initialize_event(self):
        """transact handles INITIALIZE event."""
        view = FakeView(
            balances={},
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 1, 1),
        )

        result = transact(view, 'TRS_TECH', 'INITIALIZE', datetime(2025, 1, 1),
                         initial_nav=1_000_000.0)

        sc = next(d for d in result.state_changes if d.unit == "TRS_TECH")
        assert sc.new_state['last_nav'] == 1_000_000.0

    def test_transact_reset_event(self):
        """transact handles RESET event."""
        state = dict(self.swap_state)
        state['last_nav'] = 1_000_000.0

        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': state},
            time=datetime(2025, 3, 31),
        )

        result = transact(view, 'TRS_TECH', 'RESET', datetime(2025, 3, 31),
                         current_nav=1_050_000.0, days_elapsed=90)

        assert len(result.moves) == 1
        sc = next(d for d in result.state_changes if d.unit == "TRS_TECH")
        assert sc.new_state['next_reset_index'] == 1

    def test_transact_termination_event(self):
        """transact handles TERMINATION event."""
        state = dict(self.swap_state)
        state['last_nav'] = 1_000_000.0

        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': state},
            time=datetime(2025, 2, 15),
        )

        result = transact(view, 'TRS_TECH', 'TERMINATION', datetime(2025, 2, 15),
                         final_nav=1_020_000.0, days_elapsed=45)

        assert len(result.moves) == 1
        sc = next(d for d in result.state_changes if d.unit == "TRS_TECH")
        assert sc.new_state['terminated'] is True

    def test_transact_unknown_event_returns_empty(self):
        """transact returns empty for unknown event type."""
        view = FakeView(
            balances={},
            states={'TRS_TECH': self.swap_state},
        )

        result = transact(view, 'TRS_TECH', 'UNKNOWN', datetime(2025, 1, 1))
        assert len(result.moves) == 0
        assert len(result.state_changes) == 0

    def test_transact_missing_params_returns_empty(self):
        """transact returns empty when required params are missing."""
        state = dict(self.swap_state)
        state['last_nav'] = 1_000_000.0

        view = FakeView(
            balances={},
            states={'TRS_TECH': state},
        )

        # RESET without current_nav
        result = transact(view, 'TRS_TECH', 'RESET', datetime(2025, 3, 31),
                         days_elapsed=90)
        assert len(result.moves) == 0

        # RESET without days_elapsed
        result = transact(view, 'TRS_TECH', 'RESET', datetime(2025, 3, 31),
                         current_nav=1_050_000.0)
        assert len(result.moves) == 0


# ============================================================================
# SMART CONTRACT TESTS
# ============================================================================

class TestPortfolioSwapContract:
    """Tests for portfolio_swap_contract SmartContract function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.swap_state = {
            'reference_portfolio': {'AAPL': 0.5, 'GOOG': 0.5},
            'notional': 1_000_000.0,
            'last_nav': 1_000_000.0,
            'funding_spread': 0.005,
            'reset_schedule': [datetime(2025, 3, 31), datetime(2025, 6, 30)],
            'last_reset_date': datetime(2025, 1, 1),
            'payer_wallet': 'dealer',
            'receiver_wallet': 'hedge_fund',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
            'issue_date': datetime(2025, 1, 1),
        }

    def test_contract_processes_due_reset(self):
        """Contract processes reset when date is reached."""
        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'hedge_fund': {'USD': 1_000_000},
            },
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 3, 31),
        )

        prices = {'AAPL': 110.0, 'GOOG': 90.0}  # weighted = 100, NAV = 1M
        result = portfolio_swap_contract(view, 'TRS_TECH', datetime(2025, 3, 31), prices)

        # Should process the reset
        assert any(d.unit == 'TRS_TECH' for d in result.state_changes)

    def test_contract_returns_empty_before_reset(self):
        """Contract returns empty before reset date."""
        view = FakeView(
            balances={},
            states={'TRS_TECH': self.swap_state},
            time=datetime(2025, 3, 15),
        )

        prices = {'AAPL': 110.0, 'GOOG': 90.0}
        result = portfolio_swap_contract(view, 'TRS_TECH', datetime(2025, 3, 15), prices)

        assert len(result.moves) == 0

    def test_contract_returns_empty_when_terminated(self):
        """Contract returns empty for terminated swap."""
        state = dict(self.swap_state)
        state['terminated'] = True

        view = FakeView(
            balances={},
            states={'TRS_TECH': state},
        )

        prices = {'AAPL': 110.0, 'GOOG': 90.0}
        result = portfolio_swap_contract(view, 'TRS_TECH', datetime(2025, 3, 31), prices)

        assert len(result.moves) == 0


# ============================================================================
# MULTI-PERIOD SCENARIO TESTS
# ============================================================================

class TestMultiPeriodScenarios:
    """Tests for multi-period swap scenarios."""

    def test_two_reset_cycle(self):
        """Complete cycle with two resets."""
        initial_state = {
            'reference_portfolio': {'SPY': 1.0},
            'notional': 1_000_000.0,
            'last_nav': 1_000_000.0,
            'funding_spread': 0.004,  # 40 bps
            'reset_schedule': [datetime(2025, 3, 31), datetime(2025, 6, 30)],
            'last_reset_date': datetime(2025, 1, 1),
            'payer_wallet': 'bank',
            'receiver_wallet': 'fund',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
        }

        # First reset: +5% return
        view1 = FakeView(
            balances={
                'bank': {'USD': 100_000_000},
                'fund': {'USD': 10_000_000},
            },
            states={'TRS_SPY': initial_state},
            time=datetime(2025, 3, 31),
        )

        result1 = compute_swap_reset(view1, 'TRS_SPY', 1_050_000.0, 0.004, 90)
        state_after_reset1 = next(d for d in result1.state_changes if d.unit == 'TRS_SPY').new_state

        assert state_after_reset1['last_nav'] == 1_050_000.0
        assert state_after_reset1['next_reset_index'] == 1

        # Second reset: -3% return from new baseline
        view2 = FakeView(
            balances={
                'bank': {'USD': 100_000_000},
                'fund': {'USD': 10_000_000},
            },
            states={'TRS_SPY': state_after_reset1},
            time=datetime(2025, 6, 30),
        )

        # NAV drops from 1.05M to 1.0185M (-3%)
        new_nav = 1_050_000.0 * 0.97
        result2 = compute_swap_reset(view2, 'TRS_SPY', new_nav, 0.004, 91)
        state_after_reset2 = next(d for d in result2.state_changes if d.unit == 'TRS_SPY').new_state

        assert state_after_reset2['last_nav'] == pytest.approx(new_nav, rel=1e-6)
        assert state_after_reset2['next_reset_index'] == 2
        assert len(state_after_reset2['reset_history']) == 2


# ============================================================================
# CONSERVATION LAW TESTS
# ============================================================================

class TestConservationLaws:
    """Tests verifying conservation laws for portfolio swaps."""

    def test_reset_conserves_cash(self):
        """Reset settlement is a pure transfer (conserves total cash)."""
        swap_state = {
            'reference_portfolio': {'AAPL': 1.0},
            'notional': 1_000_000.0,
            'last_nav': 1_000_000.0,
            'funding_spread': 0.005,
            'reset_schedule': [datetime(2025, 3, 31)],
            'last_reset_date': datetime(2025, 1, 1),
            'payer_wallet': 'dealer',
            'receiver_wallet': 'client',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
        }

        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'client': {'USD': 1_000_000},
            },
            states={'TRS': swap_state},
            time=datetime(2025, 3, 31),
        )

        result = compute_swap_reset(view, 'TRS', 1_050_000.0, 0.005, 90)

        # Verify single move (pure transfer)
        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source != move.dest
        assert move.quantity > 0

    def test_termination_conserves_cash(self):
        """Termination settlement is a pure transfer."""
        swap_state = {
            'reference_portfolio': {'AAPL': 1.0},
            'notional': 1_000_000.0,
            'last_nav': 1_000_000.0,
            'funding_spread': 0.005,
            'reset_schedule': [datetime(2025, 3, 31)],
            'last_reset_date': datetime(2025, 1, 1),
            'payer_wallet': 'dealer',
            'receiver_wallet': 'client',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
        }

        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'client': {'USD': 1_000_000},
            },
            states={'TRS': swap_state},
            time=datetime(2025, 2, 15),
        )

        result = compute_termination(view, 'TRS', 980_000.0, 0.005, 45)

        # Verify single move
        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source != move.dest
        assert move.quantity > 0


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_small_nav_change(self):
        """Very small NAV change near epsilon threshold."""
        swap_state = {
            'reference_portfolio': {'AAPL': 1.0},
            'notional': 1_000_000.0,
            'last_nav': 1_000_000.0,
            'funding_spread': 0.0,  # Zero funding to isolate nav effect
            'reset_schedule': [datetime(2025, 3, 31)],
            'last_reset_date': datetime(2025, 1, 1),
            'payer_wallet': 'dealer',
            'receiver_wallet': 'client',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
        }

        view = FakeView(
            balances={
                'dealer': {'USD': 10_000_000},
                'client': {'USD': 1_000_000},
            },
            states={'TRS': swap_state},
            time=datetime(2025, 3, 31),
        )

        # NAV change of $1 (0.0001%)
        result = compute_swap_reset(view, 'TRS', 1_000_001.0, 0.0, 90)

        assert len(result.moves) == 1
        assert result.moves[0].quantity == pytest.approx(1.0, rel=1e-6)

    def test_large_notional_precision(self):
        """Large notional amounts maintain precision."""
        swap_state = {
            'reference_portfolio': {'AAPL': 1.0},
            'notional': 1_000_000_000.0,  # $1B notional
            'last_nav': 1_000_000_000.0,
            'funding_spread': 0.0001,  # 1 bp
            'reset_schedule': [datetime(2025, 3, 31)],
            'last_reset_date': datetime(2025, 1, 1),
            'payer_wallet': 'dealer',
            'receiver_wallet': 'client',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
        }

        view = FakeView(
            balances={
                'dealer': {'USD': 100_000_000_000},
                'client': {'USD': 10_000_000_000},
            },
            states={'TRS': swap_state},
            time=datetime(2025, 3, 31),
        )

        # 0.01% return = $100K on $1B
        result = compute_swap_reset(view, 'TRS', 1_000_100_000.0, 0.0001, 90)

        assert len(result.moves) == 1
        # return = 100,000
        # funding = 1B * 0.0001 * 90/365 = 24,657.53
        expected_funding = 1_000_000_000.0 * 0.0001 * (90 / 365)
        expected_net = 100_000.0 - expected_funding

        assert result.moves[0].quantity == pytest.approx(expected_net, rel=1e-6)

    def test_single_day_period(self):
        """Single day period for funding calculation."""
        funding = compute_funding_amount(1_000_000.0, 0.05, 1)
        # 1M * 0.05 * (1/365) = 136.99
        expected = 1_000_000.0 * 0.05 / 365
        assert funding == pytest.approx(expected, rel=1e-6)

    def test_invalid_current_nav_raises(self):
        """Non-positive current_nav raises ValueError."""
        swap_state = {
            'reference_portfolio': {'AAPL': 1.0},
            'notional': 1_000_000.0,
            'last_nav': 1_000_000.0,
            'funding_spread': 0.005,
            'reset_schedule': [datetime(2025, 3, 31)],
            'payer_wallet': 'dealer',
            'receiver_wallet': 'client',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
        }

        view = FakeView(
            balances={},
            states={'TRS': swap_state},
        )

        with pytest.raises(ValueError, match="must be positive"):
            compute_swap_reset(view, 'TRS', 0.0, 0.005, 90)

        with pytest.raises(ValueError, match="must be positive"):
            compute_swap_reset(view, 'TRS', -100.0, 0.005, 90)

    def test_negative_days_elapsed_raises(self):
        """Negative days_elapsed raises ValueError."""
        swap_state = {
            'reference_portfolio': {'AAPL': 1.0},
            'notional': 1_000_000.0,
            'last_nav': 1_000_000.0,
            'funding_spread': 0.005,
            'reset_schedule': [datetime(2025, 3, 31)],
            'payer_wallet': 'dealer',
            'receiver_wallet': 'client',
            'currency': 'USD',
            'terminated': False,
            'next_reset_index': 0,
            'reset_history': [],
        }

        view = FakeView(
            balances={},
            states={'TRS': swap_state},
        )

        with pytest.raises(ValueError, match="cannot be negative"):
            compute_swap_reset(view, 'TRS', 1_050_000.0, 0.005, -10)
