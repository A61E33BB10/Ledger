"""
test_structured_notes.py - Unit tests for structured note lifecycle

Tests:
- Factory function (create_structured_note)
- Performance calculation (compute_performance)
- Payoff rate calculation (compute_payoff_rate)
- Coupon payment (compute_coupon_payment)
- Maturity payoff (compute_maturity_payoff)
- transact() interface
- Smart contract (structured_note_contract)
- Full lifecycle scenarios
- Edge cases and boundary conditions
- Conservation laws
"""

import pytest
from datetime import datetime, timedelta
from tests.fake_view import FakeView
from ledger.units.structured_note import (
    create_structured_note,
    compute_performance,
    compute_payoff_rate,
    compute_coupon_payment,
    compute_maturity_payoff,
    transact,
    _process_lifecycle_event as sn_lifecycle_event,
    structured_note_contract,
    generate_structured_note_coupon_schedule,
)


# ============================================================================
# COUPON SCHEDULE GENERATION TESTS
# ============================================================================

class TestGenerateCouponSchedule:
    """Tests for generate_structured_note_coupon_schedule function."""

    def test_no_coupons_frequency_zero(self):
        """Frequency 0 returns empty schedule."""
        schedule = generate_structured_note_coupon_schedule(
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            coupon_rate=0.02,
            notional=100000.0,
            frequency=0,
        )
        assert schedule == []

    def test_annual_coupon_schedule(self):
        """Generate annual coupon schedule."""
        schedule = generate_structured_note_coupon_schedule(
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2026, 1, 15),
            coupon_rate=0.02,
            notional=100000.0,
            frequency=1,
        )
        assert len(schedule) == 2  # 2 annual payments
        # Annual coupon = 100000 * 0.02 / 1 = 2000
        for _, amount in schedule:
            assert amount == 2000.0

    def test_semi_annual_coupon_schedule(self):
        """Generate semi-annual coupon schedule."""
        schedule = generate_structured_note_coupon_schedule(
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            coupon_rate=0.02,
            notional=100000.0,
            frequency=2,
        )
        assert len(schedule) == 2  # 2 semi-annual payments
        # Semi-annual coupon = 100000 * 0.02 / 2 = 1000
        for _, amount in schedule:
            assert amount == 1000.0

    def test_quarterly_coupon_schedule(self):
        """Generate quarterly coupon schedule."""
        schedule = generate_structured_note_coupon_schedule(
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            coupon_rate=0.04,
            notional=100000.0,
            frequency=4,
        )
        assert len(schedule) == 4  # 4 quarterly payments
        # Quarterly coupon = 100000 * 0.04 / 4 = 1000
        for _, amount in schedule:
            assert amount == 1000.0

    def test_invalid_frequency_raises(self):
        """Invalid frequency raises ValueError."""
        with pytest.raises(ValueError, match="Frequency must be"):
            generate_structured_note_coupon_schedule(
                issue_date=datetime(2024, 1, 15),
                maturity_date=datetime(2025, 1, 15),
                coupon_rate=0.02,
                notional=100000.0,
                frequency=3,  # Invalid
            )


# ============================================================================
# CREATE STRUCTURED NOTE TESTS
# ============================================================================

class TestCreateStructuredNote:
    """Tests for create_structured_note factory function."""

    def test_create_basic_structured_note(self):
        """Create a basic structured note with participation and cap."""
        note = create_structured_note(
            symbol="SN_SPX_2025",
            name="S&P 500 Protected Note 2025",
            underlying="SPX",
            notional=100000.0,
            strike_price=4500.0,
            participation_rate=0.80,
            protection_level=0.90,
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            cap_rate=0.25,
        )

        assert note.symbol == "SN_SPX_2025"
        assert note.unit_type == "STRUCTURED_NOTE"

        state = note._state
        assert state['underlying'] == "SPX"
        assert state['notional'] == 100000.0
        assert state['strike_price'] == 4500.0
        assert state['participation_rate'] == 0.80
        assert state['cap_rate'] == 0.25
        assert state['protection_level'] == 0.90
        assert state['currency'] == "USD"
        assert state['issuer_wallet'] == "bank"
        assert state['holder_wallet'] == "investor"
        assert state['matured'] is False

    def test_create_uncapped_structured_note(self):
        """Create a structured note without a cap."""
        note = create_structured_note(
            symbol="SN_UNCAPPED",
            name="Uncapped Note",
            underlying="SPX",
            notional=100000.0,
            strike_price=4500.0,
            participation_rate=1.00,
            protection_level=1.00,  # 100% protection
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            cap_rate=None,  # Uncapped
        )

        assert note._state['cap_rate'] is None

    def test_create_note_with_coupons(self):
        """Create a structured note with coupon payments."""
        note = create_structured_note(
            symbol="SN_COUPON",
            name="Coupon-Paying Note",
            underlying="SPX",
            notional=100000.0,
            strike_price=4500.0,
            participation_rate=0.50,
            protection_level=0.95,
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            coupon_rate=0.02,
            coupon_frequency=2,
        )

        state = note._state
        assert state['coupon_rate'] == 0.02
        assert state['coupon_frequency'] == 2
        assert len(state['coupon_schedule']) == 2

    def test_create_note_with_custom_schedule(self):
        """Create a note with pre-defined coupon schedule."""
        custom_schedule = [
            (datetime(2024, 7, 15), 500.0),
            (datetime(2025, 1, 15), 500.0),
        ]

        note = create_structured_note(
            symbol="SN_CUSTOM",
            name="Custom Schedule Note",
            underlying="SPX",
            notional=100000.0,
            strike_price=4500.0,
            participation_rate=0.80,
            protection_level=0.90,
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            coupon_schedule=custom_schedule,
        )

        assert note._state['coupon_schedule'] == custom_schedule

    def test_zero_notional_raises(self):
        """Zero or negative notional raises ValueError."""
        with pytest.raises(ValueError, match="notional must be positive"):
            create_structured_note(
                symbol="BAD",
                name="Bad Note",
                underlying="SPX",
                notional=0.0,
                strike_price=4500.0,
                participation_rate=0.80,
                protection_level=0.90,
                issue_date=datetime(2024, 1, 15),
                maturity_date=datetime(2025, 1, 15),
                currency="USD",
                issuer_wallet="bank",
                holder_wallet="investor",
            )

    def test_negative_notional_raises(self):
        """Negative notional raises ValueError."""
        with pytest.raises(ValueError, match="notional must be positive"):
            create_structured_note(
                symbol="BAD",
                name="Bad Note",
                underlying="SPX",
                notional=-100000.0,
                strike_price=4500.0,
                participation_rate=0.80,
                protection_level=0.90,
                issue_date=datetime(2024, 1, 15),
                maturity_date=datetime(2025, 1, 15),
                currency="USD",
                issuer_wallet="bank",
                holder_wallet="investor",
            )

    def test_zero_strike_raises(self):
        """Zero strike price raises ValueError."""
        with pytest.raises(ValueError, match="strike_price must be positive"):
            create_structured_note(
                symbol="BAD",
                name="Bad Note",
                underlying="SPX",
                notional=100000.0,
                strike_price=0.0,
                participation_rate=0.80,
                protection_level=0.90,
                issue_date=datetime(2024, 1, 15),
                maturity_date=datetime(2025, 1, 15),
                currency="USD",
                issuer_wallet="bank",
                holder_wallet="investor",
            )

    def test_zero_participation_raises(self):
        """Zero participation rate raises ValueError."""
        with pytest.raises(ValueError, match="participation_rate must be positive"):
            create_structured_note(
                symbol="BAD",
                name="Bad Note",
                underlying="SPX",
                notional=100000.0,
                strike_price=4500.0,
                participation_rate=0.0,
                protection_level=0.90,
                issue_date=datetime(2024, 1, 15),
                maturity_date=datetime(2025, 1, 15),
                currency="USD",
                issuer_wallet="bank",
                holder_wallet="investor",
            )

    def test_invalid_protection_level_raises(self):
        """Protection level outside [0,1] raises ValueError."""
        with pytest.raises(ValueError, match="protection_level must be between"):
            create_structured_note(
                symbol="BAD",
                name="Bad Note",
                underlying="SPX",
                notional=100000.0,
                strike_price=4500.0,
                participation_rate=0.80,
                protection_level=1.5,  # Invalid
                issue_date=datetime(2024, 1, 15),
                maturity_date=datetime(2025, 1, 15),
                currency="USD",
                issuer_wallet="bank",
                holder_wallet="investor",
            )

    def test_zero_cap_rate_raises(self):
        """Zero cap rate raises ValueError."""
        with pytest.raises(ValueError, match="cap_rate must be positive"):
            create_structured_note(
                symbol="BAD",
                name="Bad Note",
                underlying="SPX",
                notional=100000.0,
                strike_price=4500.0,
                participation_rate=0.80,
                protection_level=0.90,
                issue_date=datetime(2024, 1, 15),
                maturity_date=datetime(2025, 1, 15),
                currency="USD",
                issuer_wallet="bank",
                holder_wallet="investor",
                cap_rate=0.0,
            )

    def test_same_issuer_holder_raises(self):
        """Same issuer and holder wallet raises ValueError."""
        with pytest.raises(ValueError, match="must be different"):
            create_structured_note(
                symbol="BAD",
                name="Bad Note",
                underlying="SPX",
                notional=100000.0,
                strike_price=4500.0,
                participation_rate=0.80,
                protection_level=0.90,
                issue_date=datetime(2024, 1, 15),
                maturity_date=datetime(2025, 1, 15),
                currency="USD",
                issuer_wallet="bank",
                holder_wallet="bank",  # Same as issuer
            )

    def test_maturity_before_issue_raises(self):
        """Maturity before issue date raises ValueError."""
        with pytest.raises(ValueError, match="maturity_date must be after"):
            create_structured_note(
                symbol="BAD",
                name="Bad Note",
                underlying="SPX",
                notional=100000.0,
                strike_price=4500.0,
                participation_rate=0.80,
                protection_level=0.90,
                issue_date=datetime(2025, 1, 15),
                maturity_date=datetime(2024, 1, 15),  # Before issue
                currency="USD",
                issuer_wallet="bank",
                holder_wallet="investor",
            )

    def test_empty_currency_raises(self):
        """Empty currency raises ValueError."""
        with pytest.raises(ValueError, match="currency cannot be empty"):
            create_structured_note(
                symbol="BAD",
                name="Bad Note",
                underlying="SPX",
                notional=100000.0,
                strike_price=4500.0,
                participation_rate=0.80,
                protection_level=0.90,
                issue_date=datetime(2024, 1, 15),
                maturity_date=datetime(2025, 1, 15),
                currency="",
                issuer_wallet="bank",
                holder_wallet="investor",
            )


# ============================================================================
# PERFORMANCE CALCULATION TESTS
# ============================================================================

class TestComputePerformance:
    """Tests for compute_performance function."""

    def test_performance_positive(self):
        """Positive performance when final > strike."""
        perf = compute_performance(4950.0, 4500.0)
        assert perf == pytest.approx(0.10, abs=0.0001)

    def test_performance_negative(self):
        """Negative performance when final < strike."""
        perf = compute_performance(4050.0, 4500.0)
        assert perf == pytest.approx(-0.10, abs=0.0001)

    def test_performance_flat(self):
        """Zero performance when final == strike."""
        perf = compute_performance(4500.0, 4500.0)
        assert perf == 0.0

    def test_performance_large_gain(self):
        """Large positive performance."""
        perf = compute_performance(6750.0, 4500.0)
        assert perf == pytest.approx(0.50, abs=0.0001)

    def test_performance_large_loss(self):
        """Large negative performance."""
        perf = compute_performance(2250.0, 4500.0)
        assert perf == pytest.approx(-0.50, abs=0.0001)

    def test_performance_zero_strike_raises(self):
        """Zero strike price raises ValueError."""
        with pytest.raises(ValueError, match="strike_price must be positive"):
            compute_performance(4500.0, 0.0)

    def test_performance_negative_strike_raises(self):
        """Negative strike price raises ValueError."""
        with pytest.raises(ValueError, match="strike_price must be positive"):
            compute_performance(4500.0, -100.0)


# ============================================================================
# PAYOFF RATE CALCULATION TESTS
# ============================================================================

class TestComputePayoffRate:
    """Tests for compute_payoff_rate function."""

    def test_payoff_upside_no_cap(self):
        """Upside with participation only (no cap)."""
        # 20% up, 80% participation
        rate = compute_payoff_rate(0.20, 0.80, None, 0.90)
        assert rate == pytest.approx(0.16, abs=0.0001)

    def test_payoff_upside_below_cap(self):
        """Upside with participation below cap."""
        # 20% up, 80% participation, 25% cap
        rate = compute_payoff_rate(0.20, 0.80, 0.25, 0.90)
        assert rate == pytest.approx(0.16, abs=0.0001)

    def test_payoff_upside_at_cap(self):
        """Upside exactly at cap."""
        # 31.25% up, 80% participation = 25%, cap = 25%
        rate = compute_payoff_rate(0.3125, 0.80, 0.25, 0.90)
        assert rate == pytest.approx(0.25, abs=0.0001)

    def test_payoff_upside_hit_cap(self):
        """Upside exceeds cap."""
        # 40% up, 80% participation = 32%, capped at 25%
        rate = compute_payoff_rate(0.40, 0.80, 0.25, 0.90)
        assert rate == pytest.approx(0.25, abs=0.0001)

    def test_payoff_downside_within_protection(self):
        """Downside loss within protection level."""
        # 5% down, 90% protection (floor at -10%)
        rate = compute_payoff_rate(-0.05, 0.80, 0.25, 0.90)
        assert rate == pytest.approx(-0.05, abs=0.0001)

    def test_payoff_downside_at_protection(self):
        """Downside exactly at protection floor."""
        # 10% down, 90% protection (floor at -10%)
        rate = compute_payoff_rate(-0.10, 0.80, 0.25, 0.90)
        assert rate == pytest.approx(-0.10, abs=0.0001)

    def test_payoff_downside_protection_triggered(self):
        """Downside exceeds protection, loss capped at floor."""
        # 15% down, 90% protection (floor at -10%)
        rate = compute_payoff_rate(-0.15, 0.80, 0.25, 0.90)
        assert rate == pytest.approx(-0.10, abs=0.0001)

    def test_payoff_downside_large_loss_protected(self):
        """Large loss protected at floor."""
        # 50% down, 90% protection (floor at -10%)
        rate = compute_payoff_rate(-0.50, 0.80, 0.25, 0.90)
        assert rate == pytest.approx(-0.10, abs=0.0001)

    def test_payoff_full_protection(self):
        """100% protection means no loss."""
        # 30% down, 100% protection
        rate = compute_payoff_rate(-0.30, 0.80, 0.25, 1.00)
        assert rate == pytest.approx(0.0, abs=0.0001)

    def test_payoff_no_protection(self):
        """0% protection means full downside exposure."""
        # 30% down, 0% protection (floor at -100%)
        rate = compute_payoff_rate(-0.30, 0.80, 0.25, 0.00)
        assert rate == pytest.approx(-0.30, abs=0.0001)

    def test_payoff_flat_performance(self):
        """Flat performance returns zero."""
        rate = compute_payoff_rate(0.0, 0.80, 0.25, 0.90)
        assert rate == 0.0

    def test_payoff_high_participation(self):
        """Participation rate > 100% (leverage)."""
        # 10% up, 150% participation = 15%
        rate = compute_payoff_rate(0.10, 1.50, None, 0.90)
        assert rate == pytest.approx(0.15, abs=0.0001)


# ============================================================================
# COUPON PAYMENT TESTS
# ============================================================================

class TestComputeCouponPayment:
    """Tests for compute_coupon_payment function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.02,
            'coupon_frequency': 2,
            'coupon_schedule': [
                (datetime(2024, 7, 15), 1000.0),
                (datetime(2025, 1, 15), 1000.0),
            ],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

    def test_coupon_payment_on_schedule(self):
        """Coupon payment generates correct moves."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 5, 'USD': 0},
                'bank': {'USD': 1000000},
            },
            states={'SN_TEST': self.note_state},
        )

        result = compute_coupon_payment(view, 'SN_TEST', datetime(2024, 7, 15))

        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'bank'
        assert move.dest == 'investor'
        assert move.unit_symbol == 'USD'
        # 5 notes * $1000 coupon = $5000
        assert move.quantity == 5000.0

    def test_coupon_payment_updates_state(self):
        """Coupon payment updates state correctly."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 5},
                'bank': {'USD': 1000000},
            },
            states={'SN_TEST': self.note_state},
        )

        result = compute_coupon_payment(view, 'SN_TEST', datetime(2024, 7, 15))
        sc = next(d for d in result.state_changes if d.unit == "SN_TEST")

        assert sc.new_state['next_coupon_index'] == 1
        assert len(sc.new_state['paid_coupons']) == 1

    def test_coupon_before_schedule_returns_empty(self):
        """Coupon before scheduled date returns empty."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 5},
                'bank': {'USD': 1000000},
            },
            states={'SN_TEST': self.note_state},
        )

        result = compute_coupon_payment(view, 'SN_TEST', datetime(2024, 7, 1))

        assert len(result.moves) == 0

    def test_coupon_schedule_exhausted_returns_empty(self):
        """Exhausted schedule returns empty."""
        state = dict(self.note_state)
        state['next_coupon_index'] = 2

        view = FakeView(
            balances={
                'investor': {'SN_TEST': 5},
                'bank': {'USD': 1000000},
            },
            states={'SN_TEST': state},
        )

        result = compute_coupon_payment(view, 'SN_TEST', datetime(2025, 6, 15))

        assert len(result.moves) == 0

    def test_coupon_multiple_holders(self):
        """Coupon payment to multiple holders."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 5},
                'alice': {'SN_TEST': 3},
                'bank': {'USD': 1000000},
            },
            states={'SN_TEST': self.note_state},
        )

        result = compute_coupon_payment(view, 'SN_TEST', datetime(2024, 7, 15))

        assert len(result.moves) == 2
        total = sum(m.quantity for m in result.moves)
        # (5 + 3) * $1000 = $8000
        assert total == 8000.0


# ============================================================================
# MATURITY PAYOFF TESTS
# ============================================================================

class TestComputeMaturityPayoff:
    """Tests for compute_maturity_payoff function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.0,
            'coupon_frequency': 0,
            'coupon_schedule': [],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

    def test_maturity_payoff_upside(self):
        """Maturity payoff with positive performance."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1, 'USD': 0},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2025, 1, 15),
        )

        # 10% up, 80% participation = 8% return
        # Payout = 100000 * (1 + 0.08) = 108000
        result = compute_maturity_payoff(view, 'SN_TEST', 4950.0)

        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'bank'
        assert move.dest == 'investor'
        assert move.quantity == pytest.approx(108000.0, abs=0.01)

    def test_maturity_payoff_cap_hit(self):
        """Maturity payoff when cap is hit."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2025, 1, 15),
        )

        # 50% up, 80% participation = 40%, capped at 25%
        # Payout = 100000 * (1 + 0.25) = 125000
        result = compute_maturity_payoff(view, 'SN_TEST', 6750.0)

        move = result.moves[0]
        assert move.quantity == pytest.approx(125000.0, abs=0.01)

    def test_maturity_payoff_protection_triggered(self):
        """Maturity payoff when protection is triggered."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2025, 1, 15),
        )

        # 20% down, 90% protection limits loss to 10%
        # Payout = 100000 * (1 - 0.10) = 90000
        result = compute_maturity_payoff(view, 'SN_TEST', 3600.0)

        move = result.moves[0]
        assert move.quantity == pytest.approx(90000.0, abs=0.01)

    def test_maturity_payoff_flat(self):
        """Maturity payoff with flat performance."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2025, 1, 15),
        )

        # Flat performance = return principal only
        result = compute_maturity_payoff(view, 'SN_TEST', 4500.0)

        move = result.moves[0]
        assert move.quantity == pytest.approx(100000.0, abs=0.01)

    def test_maturity_marks_matured(self):
        """Maturity marks note as matured."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2025, 1, 15),
        )

        result = compute_maturity_payoff(view, 'SN_TEST', 4950.0)
        sc = next(d for d in result.state_changes if d.unit == "SN_TEST")

        assert sc.new_state['matured'] is True
        assert 'maturity_settlement' in sc.new_state

    def test_maturity_already_matured_returns_empty(self):
        """Already matured note returns empty."""
        state = dict(self.note_state)
        state['matured'] = True

        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': state},
            time=datetime(2025, 1, 15),
        )

        result = compute_maturity_payoff(view, 'SN_TEST', 4950.0)

        assert len(result.moves) == 0

    def test_maturity_before_date_returns_empty(self):
        """Maturity before maturity date returns empty."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2024, 12, 15),  # Before maturity
        )

        result = compute_maturity_payoff(view, 'SN_TEST', 4950.0)

        assert len(result.moves) == 0

    def test_maturity_zero_final_price_raises(self):
        """Zero final price raises ValueError."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2025, 1, 15),
        )

        with pytest.raises(ValueError, match="final_price must be positive"):
            compute_maturity_payoff(view, 'SN_TEST', 0.0)

    def test_maturity_multiple_holders(self):
        """Maturity payoff to multiple holders."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 2},
                'alice': {'SN_TEST': 3},
                'bank': {'USD': 1000000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2025, 1, 15),
        )

        # 10% up, 80% participation = 8% return
        result = compute_maturity_payoff(view, 'SN_TEST', 4950.0)

        assert len(result.moves) == 2
        total = sum(m.quantity for m in result.moves)
        # (2 + 3) * 108000 = 540000
        assert total == pytest.approx(540000.0, abs=0.01)


# ============================================================================
# TRANSACT INTERFACE TESTS
# ============================================================================

class TestTransact:
    """Tests for transact() unified interface."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.02,
            'coupon_frequency': 2,
            'coupon_schedule': [
                (datetime(2024, 7, 15), 1000.0),
            ],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

    def test_lifecycle_event_coupon(self):
        """_process_lifecycle_event handles COUPON event."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 5},
                'bank': {'USD': 100000},
            },
            states={'SN_TEST': self.note_state},
        )

        result = sn_lifecycle_event(view, 'SN_TEST', 'COUPON', datetime(2024, 7, 15))

        assert len(result.moves) == 1

    def test_lifecycle_event_maturity(self):
        """_process_lifecycle_event handles MATURITY event."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2025, 1, 15),
        )

        result = sn_lifecycle_event(view, 'SN_TEST', 'MATURITY', datetime(2025, 1, 15),
                          final_price=4950.0)

        assert len(result.moves) == 1

    def test_lifecycle_event_maturity_missing_price_returns_empty(self):
        """MATURITY without final_price returns empty."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2025, 1, 15),
        )

        result = sn_lifecycle_event(view, 'SN_TEST', 'MATURITY', datetime(2025, 1, 15))

        assert len(result.moves) == 0

    def test_lifecycle_event_unknown_returns_empty(self):
        """Unknown event type returns empty."""
        view = FakeView(
            balances={},
            states={'SN_TEST': self.note_state},
        )

        result = sn_lifecycle_event(view, 'SN_TEST', 'UNKNOWN', datetime(2024, 7, 15))

        assert len(result.moves) == 0


# ============================================================================
# SMART CONTRACT TESTS
# ============================================================================

class TestStructuredNoteContract:
    """Tests for structured_note_contract smart contract."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.02,
            'coupon_frequency': 2,
            'coupon_schedule': [
                (datetime(2024, 7, 15), 1000.0),
            ],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

    def test_contract_processes_maturity(self):
        """Smart contract processes maturity when due."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2025, 1, 15),
        )

        result = structured_note_contract(
            view, 'SN_TEST', datetime(2025, 1, 15), {'SPX': 4950.0}
        )

        assert len(result.moves) == 1

    def test_contract_processes_coupon(self):
        """Smart contract processes coupon when due."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 5},
                'bank': {'USD': 100000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2024, 7, 15),
        )

        result = structured_note_contract(
            view, 'SN_TEST', datetime(2024, 7, 15), {'SPX': 4500.0}
        )

        assert len(result.moves) == 1

    def test_contract_no_events_returns_empty(self):
        """Smart contract returns empty when no events due."""
        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': self.note_state},
            time=datetime(2024, 5, 15),
        )

        result = structured_note_contract(
            view, 'SN_TEST', datetime(2024, 5, 15), {'SPX': 4500.0}
        )

        assert len(result.moves) == 0


# ============================================================================
# FULL LIFECYCLE TESTS
# ============================================================================

class TestFullLifecycle:
    """Tests for complete structured note lifecycle scenarios."""

    def test_note_issue_to_maturity_with_gain(self):
        """Complete lifecycle: issue -> coupons -> maturity with gain."""
        note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.02,
            'coupon_frequency': 2,
            'coupon_schedule': [
                (datetime(2024, 7, 15), 1000.0),
                (datetime(2025, 1, 15), 1000.0),
            ],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

        # Step 1: First coupon
        view1 = FakeView(
            balances={
                'investor': {'SN_TEST': 1, 'USD': 0},
                'bank': {'USD': 1000000},
            },
            states={'SN_TEST': note_state},
        )

        result1 = compute_coupon_payment(view1, 'SN_TEST', datetime(2024, 7, 15))
        assert len(result1.moves) == 1
        assert result1.moves[0].quantity == 1000.0

        state_after_c1 = next(d for d in result1.state_changes if d.unit == 'SN_TEST').new_state

        # Step 2: Second coupon
        view2 = FakeView(
            balances={
                'investor': {'SN_TEST': 1, 'USD': 1000},
                'bank': {'USD': 999000},
            },
            states={'SN_TEST': state_after_c1},
        )

        result2 = compute_coupon_payment(view2, 'SN_TEST', datetime(2025, 1, 15))
        assert len(result2.moves) == 1
        assert result2.moves[0].quantity == 1000.0

        state_after_c2 = next(d for d in result2.state_changes if d.unit == 'SN_TEST').new_state

        # Step 3: Maturity (10% up, 8% participation return)
        view3 = FakeView(
            balances={
                'investor': {'SN_TEST': 1, 'USD': 2000},
                'bank': {'USD': 998000},
            },
            states={'SN_TEST': state_after_c2},
            time=datetime(2025, 1, 15),
        )

        result3 = compute_maturity_payoff(view3, 'SN_TEST', 4950.0)
        assert len(result3.moves) == 1
        assert result3.moves[0].quantity == pytest.approx(108000.0, abs=0.01)

        # Total received: 1000 + 1000 + 108000 = 110000
        # On 100000 invested, that's 10% total return

    def test_note_lifecycle_with_loss_protected(self):
        """Lifecycle with loss limited by protection."""
        note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.0,
            'coupon_frequency': 0,
            'coupon_schedule': [],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': note_state},
            time=datetime(2025, 1, 15),
        )

        # 30% down, but protected to 10% loss
        result = compute_maturity_payoff(view, 'SN_TEST', 3150.0)

        assert result.moves[0].quantity == pytest.approx(90000.0, abs=0.01)


# ============================================================================
# EDGE CASES AND BOUNDARY TESTS
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_100_percent_protection_no_loss(self):
        """100% protection means no loss possible."""
        note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 0.50,
            'cap_rate': None,
            'protection_level': 1.00,  # 100% protection
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.0,
            'coupon_frequency': 0,
            'coupon_schedule': [],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': note_state},
            time=datetime(2025, 1, 15),
        )

        # 50% down, but 100% protected
        result = compute_maturity_payoff(view, 'SN_TEST', 2250.0)

        # Full principal returned
        assert result.moves[0].quantity == pytest.approx(100000.0, abs=0.01)

    def test_100_percent_participation_full_upside(self):
        """100% participation captures full upside."""
        note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 1.00,
            'cap_rate': None,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.0,
            'coupon_frequency': 0,
            'coupon_schedule': [],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': note_state},
            time=datetime(2025, 1, 15),
        )

        # 20% up, 100% participation
        result = compute_maturity_payoff(view, 'SN_TEST', 5400.0)

        assert result.moves[0].quantity == pytest.approx(120000.0, abs=0.01)

    def test_very_small_notional(self):
        """Very small notional handled correctly."""
        note_state = {
            'underlying': 'SPX',
            'notional': 100.0,  # Small notional
            'strike_price': 4500.0,
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.0,
            'coupon_frequency': 0,
            'coupon_schedule': [],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': note_state},
            time=datetime(2025, 1, 15),
        )

        result = compute_maturity_payoff(view, 'SN_TEST', 4950.0)

        # 10% up, 8% return on 100 = 108
        assert result.moves[0].quantity == pytest.approx(108.0, abs=0.01)

    def test_very_high_strike_price(self):
        """Very high strike price handled correctly."""
        note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 100000.0,  # High strike
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.0,
            'coupon_frequency': 0,
            'coupon_schedule': [],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': note_state},
            time=datetime(2025, 1, 15),
        )

        # Final at 50000 = 50% loss, protected to 10%
        result = compute_maturity_payoff(view, 'SN_TEST', 50000.0)

        assert result.moves[0].quantity == pytest.approx(90000.0, abs=0.01)


# ============================================================================
# CONSERVATION LAW TESTS
# ============================================================================

class TestConservationLaws:
    """Tests verifying conservation laws for structured notes."""

    def test_coupon_payment_conserves_cash(self):
        """Coupon payment is a pure transfer."""
        note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.02,
            'coupon_frequency': 2,
            'coupon_schedule': [(datetime(2024, 7, 15), 1000.0)],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

        view = FakeView(
            balances={
                'investor': {'SN_TEST': 10, 'USD': 0},
                'bank': {'USD': 100000},
            },
            states={'SN_TEST': note_state},
        )

        result = compute_coupon_payment(view, 'SN_TEST', datetime(2024, 7, 15))

        for move in result.moves:
            assert move.source == 'bank'
            assert move.dest != 'bank'
            assert move.quantity > 0

    def test_maturity_payoff_conserves_cash(self):
        """Maturity payoff is a pure transfer."""
        note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.0,
            'coupon_frequency': 0,
            'coupon_schedule': [],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

        view = FakeView(
            balances={
                'investor': {'SN_TEST': 2},
                'alice': {'SN_TEST': 3},
                'bank': {'USD': 1000000},
            },
            states={'SN_TEST': note_state},
            time=datetime(2025, 1, 15),
        )

        result = compute_maturity_payoff(view, 'SN_TEST', 4950.0)

        total_out = 0
        for move in result.moves:
            assert move.source == 'bank'
            total_out += move.quantity

        # (2 + 3) * 108000 = 540000
        assert total_out == pytest.approx(540000.0, abs=0.01)

    def test_net_flow_equals_payoff_calculation(self):
        """Net cash flow matches payoff formula."""
        note_state = {
            'underlying': 'SPX',
            'notional': 100000.0,
            'strike_price': 4500.0,
            'participation_rate': 0.80,
            'cap_rate': 0.25,
            'protection_level': 0.90,
            'issue_date': datetime(2024, 1, 15),
            'maturity_date': datetime(2025, 1, 15),
            'currency': 'USD',
            'issuer_wallet': 'bank',
            'holder_wallet': 'investor',
            'coupon_rate': 0.0,
            'coupon_frequency': 0,
            'coupon_schedule': [],
            'paid_coupons': [],
            'matured': False,
            'next_coupon_index': 0,
        }

        view = FakeView(
            balances={
                'investor': {'SN_TEST': 1},
                'bank': {'USD': 500000},
            },
            states={'SN_TEST': note_state},
            time=datetime(2025, 1, 15),
        )

        final_price = 4950.0
        result = compute_maturity_payoff(view, 'SN_TEST', final_price)

        # Calculate expected payoff manually
        perf = compute_performance(final_price, 4500.0)
        rate = compute_payoff_rate(perf, 0.80, 0.25, 0.90)
        expected_payout = 100000.0 * (1 + rate)

        assert result.moves[0].quantity == pytest.approx(expected_payout, abs=0.01)
