"""
test_bonds.py - Unit tests for bond units with coupons and accrued interest

Tests:
- Factory function (create_bond_unit)
- Accrued interest calculation (compute_accrued_interest)
- Day count conventions (30/360, ACT/360, ACT/ACT)
- Coupon payment (compute_coupon_payment)
- Redemption (compute_redemption)
- transact() interface
- Full bond lifecycle
"""

import pytest
from datetime import datetime, timedelta
from tests.fake_view import FakeView
from ledger import (
    create_bond_unit,
    compute_accrued_interest,
    compute_coupon_payment,
    compute_redemption,
    bond_transact,
    generate_coupon_schedule,
    year_fraction,
)


# ============================================================================
# HELPER FUNCTIONS / DAY COUNT TESTS
# ============================================================================

class TestYearFraction:
    """Tests for year_fraction day count convention helper."""

    def test_30_360_one_year(self):
        """30/360: exactly one year is 1.0."""
        start = datetime(2024, 1, 15)
        end = datetime(2025, 1, 15)
        frac = year_fraction(start, end, "30/360")
        assert frac == pytest.approx(1.0, abs=0.001)

    def test_30_360_half_year(self):
        """30/360: six months is 0.5."""
        start = datetime(2024, 1, 15)
        end = datetime(2024, 7, 15)
        frac = year_fraction(start, end, "30/360")
        assert frac == pytest.approx(0.5, abs=0.001)

    def test_30_360_one_month(self):
        """30/360: one month is 30/360 = 0.0833..."""
        start = datetime(2024, 1, 15)
        end = datetime(2024, 2, 15)
        frac = year_fraction(start, end, "30/360")
        assert frac == pytest.approx(30/360, abs=0.001)

    def test_act_360_one_year(self):
        """ACT/360: 365 days is 365/360."""
        start = datetime(2024, 1, 15)
        end = datetime(2025, 1, 15)  # 366 days (leap year)
        frac = year_fraction(start, end, "ACT/360")
        # 2024 is leap year, so 366 days
        assert frac == pytest.approx(366/360, abs=0.001)

    def test_act_360_30_days(self):
        """ACT/360: 30 actual days."""
        start = datetime(2024, 1, 15)
        end = datetime(2024, 2, 14)  # 30 days
        frac = year_fraction(start, end, "ACT/360")
        assert frac == pytest.approx(30/360, abs=0.001)

    def test_act_act_one_year(self):
        """ACT/ACT: approximately 1.0 for a year."""
        start = datetime(2024, 1, 15)
        end = datetime(2025, 1, 15)
        frac = year_fraction(start, end, "ACT/ACT")
        # Uses 365.25 average
        assert frac == pytest.approx(366/365.25, abs=0.01)

    def test_invalid_convention_raises(self):
        """Invalid day count convention raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported day count convention"):
            year_fraction(datetime(2024, 1, 1), datetime(2024, 2, 1), "INVALID")


class TestGenerateCouponSchedule:
    """Tests for generate_coupon_schedule function."""

    def test_annual_coupon_schedule(self):
        """Generate annual coupon schedule."""
        schedule = generate_coupon_schedule(
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2027, 1, 15),
            coupon_rate=0.05,
            face_value=1000.0,
            frequency=1,
        )

        assert len(schedule) == 3  # 3 annual payments
        # Annual coupon = 1000 * 0.05 / 1 = 50
        for date, amount in schedule:
            assert amount == 50.0

        # Check dates
        assert schedule[0][0] == datetime(2025, 1, 15)
        assert schedule[1][0] == datetime(2026, 1, 15)
        assert schedule[2][0] == datetime(2027, 1, 15)

    def test_semi_annual_coupon_schedule(self):
        """Generate semi-annual coupon schedule."""
        schedule = generate_coupon_schedule(
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            coupon_rate=0.04,
            face_value=1000.0,
            frequency=2,
        )

        assert len(schedule) == 2  # 2 semi-annual payments
        # Semi-annual coupon = 1000 * 0.04 / 2 = 20
        for date, amount in schedule:
            assert amount == 20.0

        assert schedule[0][0] == datetime(2024, 7, 15)
        assert schedule[1][0] == datetime(2025, 1, 15)

    def test_quarterly_coupon_schedule(self):
        """Generate quarterly coupon schedule."""
        schedule = generate_coupon_schedule(
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            coupon_rate=0.08,
            face_value=1000.0,
            frequency=4,
        )

        assert len(schedule) == 4  # 4 quarterly payments
        # Quarterly coupon = 1000 * 0.08 / 4 = 20
        for date, amount in schedule:
            assert amount == 20.0

    def test_monthly_coupon_schedule(self):
        """Generate monthly coupon schedule."""
        schedule = generate_coupon_schedule(
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2024, 7, 15),
            coupon_rate=0.12,
            face_value=1000.0,
            frequency=12,
        )

        assert len(schedule) == 6  # 6 monthly payments
        # Monthly coupon = 1000 * 0.12 / 12 = 10
        for date, amount in schedule:
            assert amount == 10.0

    def test_invalid_frequency_raises(self):
        """Invalid frequency raises ValueError."""
        with pytest.raises(ValueError, match="Frequency must be"):
            generate_coupon_schedule(
                issue_date=datetime(2024, 1, 15),
                maturity_date=datetime(2025, 1, 15),
                coupon_rate=0.05,
                face_value=1000.0,
                frequency=3,  # Not 1, 2, 4, or 12
            )


# ============================================================================
# CREATE BOND UNIT TESTS
# ============================================================================

class TestCreateBondUnit:
    """Tests for create_bond_unit factory function."""

    def test_create_basic_corporate_bond(self):
        """Create a basic corporate bond with semi-annual coupons."""
        bond = create_bond_unit(
            symbol="CORP_5Y_2029",
            name="Corporate Bond 5% 2029",
            face_value=1000.0,
            coupon_rate=0.05,
            coupon_frequency=2,
            maturity_date=datetime(2029, 12, 15),
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=datetime(2024, 12, 15),
            day_count_convention="30/360",
        )

        assert bond.symbol == "CORP_5Y_2029"
        assert bond.name == "Corporate Bond 5% 2029"
        assert bond.unit_type == "BOND"

        state = bond._state
        assert state["face_value"] == 1000.0
        assert state["coupon_rate"] == 0.05
        assert state["coupon_frequency"] == 2
        assert state["currency"] == "USD"
        assert state["issuer_wallet"] == "corporation"
        assert state["holder_wallet"] == "investor"
        assert state["day_count_convention"] == "30/360"
        assert state["next_coupon_index"] == 0
        assert state["accrued_interest"] == 0.0
        assert state["redeemed"] is False

    def test_create_treasury_bond(self):
        """Create a US Treasury bond with ACT/ACT convention."""
        bond = create_bond_unit(
            symbol="US10Y",
            name="US Treasury 10-Year",
            face_value=1000.0,
            coupon_rate=0.04,
            coupon_frequency=2,
            maturity_date=datetime(2034, 11, 15),
            currency="USD",
            issuer_wallet="us_treasury",
            holder_wallet="investor",
            issue_date=datetime(2024, 11, 15),
            day_count_convention="ACT/ACT",
        )

        state = bond._state
        assert state["day_count_convention"] == "ACT/ACT"

    def test_create_euro_bond(self):
        """Create a Euro-denominated bond."""
        bond = create_bond_unit(
            symbol="EURO_CORP",
            name="Euro Corporate Bond",
            face_value=1000.0,
            coupon_rate=0.03,
            coupon_frequency=1,
            maturity_date=datetime(2030, 6, 15),
            currency="EUR",
            issuer_wallet="eu_corporation",
            holder_wallet="eu_investor",
            issue_date=datetime(2024, 6, 15),
        )

        assert bond._state["currency"] == "EUR"

    def test_create_bond_with_provided_schedule(self):
        """Create a bond with a pre-defined coupon schedule."""
        custom_schedule = [
            (datetime(2025, 6, 15), 25.0),
            (datetime(2025, 12, 15), 25.0),
            (datetime(2026, 6, 15), 30.0),  # Non-uniform
        ]

        bond = create_bond_unit(
            symbol="CUSTOM",
            name="Custom Bond",
            face_value=1000.0,
            coupon_rate=0.05,
            coupon_frequency=2,
            maturity_date=datetime(2026, 6, 15),
            currency="USD",
            issuer_wallet="issuer",
            holder_wallet="holder",
            coupon_schedule=custom_schedule,
        )

        assert bond._state["coupon_schedule"] == custom_schedule

    def test_zero_face_value_raises(self):
        """Zero or negative face_value raises ValueError."""
        with pytest.raises(ValueError, match="face_value must be positive"):
            create_bond_unit(
                symbol="BAD",
                name="Bad Bond",
                face_value=0.0,
                coupon_rate=0.05,
                coupon_frequency=2,
                maturity_date=datetime(2029, 12, 15),
                currency="USD",
                issuer_wallet="issuer",
                holder_wallet="holder",
                issue_date=datetime(2024, 12, 15),
            )

    def test_negative_coupon_rate_raises(self):
        """Negative coupon_rate raises ValueError."""
        with pytest.raises(ValueError, match="coupon_rate cannot be negative"):
            create_bond_unit(
                symbol="BAD",
                name="Bad Bond",
                face_value=1000.0,
                coupon_rate=-0.01,
                coupon_frequency=2,
                maturity_date=datetime(2029, 12, 15),
                currency="USD",
                issuer_wallet="issuer",
                holder_wallet="holder",
                issue_date=datetime(2024, 12, 15),
            )

    def test_invalid_frequency_raises(self):
        """Invalid coupon_frequency raises ValueError."""
        with pytest.raises(ValueError, match="coupon_frequency must be"):
            create_bond_unit(
                symbol="BAD",
                name="Bad Bond",
                face_value=1000.0,
                coupon_rate=0.05,
                coupon_frequency=3,
                maturity_date=datetime(2029, 12, 15),
                currency="USD",
                issuer_wallet="issuer",
                holder_wallet="holder",
                issue_date=datetime(2024, 12, 15),
            )

    def test_invalid_day_count_raises(self):
        """Invalid day_count_convention raises ValueError."""
        with pytest.raises(ValueError, match="day_count_convention must be"):
            create_bond_unit(
                symbol="BAD",
                name="Bad Bond",
                face_value=1000.0,
                coupon_rate=0.05,
                coupon_frequency=2,
                maturity_date=datetime(2029, 12, 15),
                currency="USD",
                issuer_wallet="issuer",
                holder_wallet="holder",
                issue_date=datetime(2024, 12, 15),
                day_count_convention="INVALID",
            )

    def test_missing_issue_date_without_schedule_raises(self):
        """Missing issue_date without coupon_schedule raises ValueError."""
        with pytest.raises(ValueError, match="issue_date is required"):
            create_bond_unit(
                symbol="BAD",
                name="Bad Bond",
                face_value=1000.0,
                coupon_rate=0.05,
                coupon_frequency=2,
                maturity_date=datetime(2029, 12, 15),
                currency="USD",
                issuer_wallet="issuer",
                holder_wallet="holder",
                # No issue_date, no coupon_schedule
            )


# ============================================================================
# ACCRUED INTEREST TESTS
# ============================================================================

class TestComputeAccruedInterest:
    """Tests for compute_accrued_interest function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.bond_state = {
            'face_value': 1000.0,
            'coupon_rate': 0.05,
            'coupon_frequency': 2,
            'coupon_schedule': [
                (datetime(2025, 6, 15), 25.0),  # Semi-annual = $25
                (datetime(2025, 12, 15), 25.0),
            ],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'issuer',
            'holder_wallet': 'holder',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': 0,
            'accrued_interest': 0.0,
            'redeemed': False,
            'paid_coupons': [],
        }

    def test_accrued_interest_at_issue_date(self):
        """Accrued interest is zero at issue date."""
        view = FakeView(
            balances={'holder': {'BOND': 1}},
            states={'BOND': self.bond_state},
        )

        accrued = compute_accrued_interest(view, 'BOND', datetime(2024, 12, 15))
        assert accrued == 0.0

    def test_accrued_interest_half_period(self):
        """Accrued interest at half of coupon period."""
        view = FakeView(
            balances={'holder': {'BOND': 1}},
            states={'BOND': self.bond_state},
        )

        # Half way through 6-month period
        accrued = compute_accrued_interest(view, 'BOND', datetime(2025, 3, 15))
        # Expected: 25 * (3 months / 6 months) = 12.5
        assert accrued == pytest.approx(12.5, abs=0.5)

    def test_accrued_interest_full_period(self):
        """Accrued interest equals full coupon at payment date."""
        view = FakeView(
            balances={'holder': {'BOND': 1}},
            states={'BOND': self.bond_state},
        )

        accrued = compute_accrued_interest(view, 'BOND', datetime(2025, 6, 15))
        # Full coupon has accrued
        assert accrued == 25.0

    def test_accrued_interest_after_coupon_paid(self):
        """Accrued interest resets after coupon payment."""
        state = dict(self.bond_state)
        state['next_coupon_index'] = 1  # First coupon has been paid
        state['paid_coupons'] = [{
            'payment_number': 0,
            'payment_date': datetime(2025, 6, 15),
            'coupon_amount': 25.0,
        }]

        view = FakeView(
            balances={'holder': {'BOND': 1}},
            states={'BOND': state},
        )

        # One month after first coupon
        accrued = compute_accrued_interest(view, 'BOND', datetime(2025, 7, 15))
        # Expected: 25 * (1 month / 6 months) ≈ 4.17
        assert accrued == pytest.approx(25.0 / 6, abs=0.5)

    def test_accrued_interest_no_more_coupons(self):
        """Accrued interest is zero when no more coupons scheduled."""
        state = dict(self.bond_state)
        state['next_coupon_index'] = 2  # All coupons paid

        view = FakeView(
            balances={'holder': {'BOND': 1}},
            states={'BOND': state},
        )

        accrued = compute_accrued_interest(view, 'BOND', datetime(2025, 12, 20))
        assert accrued == 0.0

    def test_accrued_interest_act_360(self):
        """Accrued interest with ACT/360 convention."""
        state = dict(self.bond_state)
        state['day_count_convention'] = 'ACT/360'

        view = FakeView(
            balances={'holder': {'BOND': 1}},
            states={'BOND': state},
        )

        # 30 actual days from issue
        accrued = compute_accrued_interest(view, 'BOND', datetime(2025, 1, 14))
        # ACT/360: 30 days / 360 vs period days / 360
        # This is approximately 1 month worth
        assert accrued > 0  # Just verify positive


# ============================================================================
# COUPON PAYMENT TESTS
# ============================================================================

class TestComputeCouponPayment:
    """Tests for compute_coupon_payment function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.bond_state = {
            'face_value': 1000.0,
            'coupon_rate': 0.05,
            'coupon_frequency': 2,
            'coupon_schedule': [
                (datetime(2025, 6, 15), 25.0),
                (datetime(2025, 12, 15), 25.0),
            ],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'issuer',
            'holder_wallet': 'holder',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': 0,
            'accrued_interest': 0.0,
            'redeemed': False,
            'paid_coupons': [],
        }

    def test_coupon_payment_on_schedule(self):
        """Coupon payment generates correct moves on scheduled date."""
        view = FakeView(
            balances={
                'holder': {'BOND': 10, 'USD': 0},
                'issuer': {'USD': 10000},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_coupon_payment(view, 'BOND', datetime(2025, 6, 15))

        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'issuer'
        assert move.dest == 'holder'
        assert move.unit_symbol == 'USD'
        # 10 bonds × $25 coupon = $250
        assert move.quantity == 250.0

    def test_coupon_payment_updates_state(self):
        """Coupon payment updates next_coupon_index and paid_coupons."""
        view = FakeView(
            balances={
                'holder': {'BOND': 10},
                'issuer': {'USD': 10000},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_coupon_payment(view, 'BOND', datetime(2025, 6, 15))
        sc = next(d for d in result.state_changes if d.unit == "BOND")

        assert sc.new_state['next_coupon_index'] == 1
        assert sc.new_state['accrued_interest'] == 0.0
        assert len(sc.new_state['paid_coupons']) == 1
        assert sc.new_state['paid_coupons'][0]['payment_number'] == 0

    def test_coupon_payment_before_schedule_returns_empty(self):
        """Coupon payment before scheduled date returns empty result."""
        view = FakeView(
            balances={
                'holder': {'BOND': 10},
                'issuer': {'USD': 10000},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_coupon_payment(view, 'BOND', datetime(2025, 6, 1))

        assert len(result.moves) == 0

    def test_coupon_payment_multiple_holders(self):
        """Coupon payment distributes to multiple bondholders."""
        view = FakeView(
            balances={
                'holder': {'BOND': 10},
                'alice': {'BOND': 5},
                'bob': {'BOND': 3},
                'issuer': {'USD': 100000},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_coupon_payment(view, 'BOND', datetime(2025, 6, 15))

        # Three holders (excluding issuer)
        assert len(result.moves) == 3

        # Verify total payment
        total = sum(m.quantity for m in result.moves)
        # (10 + 5 + 3) × $25 = $450
        assert total == 450.0

    def test_coupon_payment_issuer_not_paid(self):
        """Issuer does not receive coupon payments on their own bonds."""
        view = FakeView(
            balances={
                'holder': {'BOND': 10},
                'issuer': {'BOND': 5, 'USD': 100000},  # Issuer holds some bonds
            },
            states={'BOND': self.bond_state},
        )

        result = compute_coupon_payment(view, 'BOND', datetime(2025, 6, 15))

        # Only holder receives, not issuer
        assert len(result.moves) == 1
        assert result.moves[0].dest == 'holder'

    def test_coupon_schedule_exhausted_returns_empty(self):
        """No coupon payment when schedule is exhausted."""
        state = dict(self.bond_state)
        state['next_coupon_index'] = 2  # Past all coupons

        view = FakeView(
            balances={
                'holder': {'BOND': 10},
                'issuer': {'USD': 100000},
            },
            states={'BOND': state},
        )

        result = compute_coupon_payment(view, 'BOND', datetime(2026, 6, 15))

        assert len(result.moves) == 0


# ============================================================================
# REDEMPTION TESTS
# ============================================================================

class TestComputeRedemption:
    """Tests for compute_redemption function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.bond_state = {
            'face_value': 1000.0,
            'coupon_rate': 0.05,
            'coupon_frequency': 2,
            'coupon_schedule': [
                (datetime(2025, 6, 15), 25.0),
                (datetime(2025, 12, 15), 25.0),
            ],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'issuer',
            'holder_wallet': 'holder',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': 2,  # All coupons paid
            'accrued_interest': 0.0,
            'redeemed': False,
            'paid_coupons': [],
        }

    def test_redemption_at_maturity(self):
        """Redemption pays face value to bondholders."""
        view = FakeView(
            balances={
                'holder': {'BOND': 10, 'USD': 0},
                'issuer': {'USD': 100000},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_redemption(view, 'BOND', datetime(2025, 12, 15))

        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'issuer'
        assert move.dest == 'holder'
        # 10 bonds × $1000 face value = $10,000
        assert move.quantity == 10000.0

    def test_redemption_marks_redeemed(self):
        """Redemption marks bond as redeemed."""
        view = FakeView(
            balances={
                'holder': {'BOND': 10},
                'issuer': {'USD': 100000},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_redemption(view, 'BOND', datetime(2025, 12, 15))
        sc = next(d for d in result.state_changes if d.unit == "BOND")

        assert sc.new_state['redeemed'] is True
        assert sc.new_state['redemption_amount'] == 1000.0

    def test_redemption_custom_price(self):
        """Redemption with custom price (callable bond)."""
        view = FakeView(
            balances={
                'holder': {'BOND': 10},
                'issuer': {'USD': 100000},
            },
            states={'BOND': self.bond_state},
        )

        # Call at 102% of face value
        result = compute_redemption(view, 'BOND', datetime(2025, 12, 15), redemption_price=1020.0)

        move = result.moves[0]
        # 10 bonds × $1020 = $10,200
        assert move.quantity == 10200.0

    def test_redemption_multiple_holders(self):
        """Redemption pays all bondholders."""
        view = FakeView(
            balances={
                'holder': {'BOND': 10},
                'alice': {'BOND': 5},
                'issuer': {'USD': 100000},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_redemption(view, 'BOND', datetime(2025, 12, 15))

        assert len(result.moves) == 2
        total = sum(m.quantity for m in result.moves)
        # (10 + 5) × $1000 = $15,000
        assert total == 15000.0

    def test_redemption_already_redeemed_returns_empty(self):
        """Cannot redeem an already-redeemed bond."""
        state = dict(self.bond_state)
        state['redeemed'] = True

        view = FakeView(
            balances={
                'holder': {'BOND': 10},
                'issuer': {'USD': 100000},
            },
            states={'BOND': state},
        )

        result = compute_redemption(view, 'BOND', datetime(2025, 12, 20))

        assert len(result.moves) == 0


# ============================================================================
# FULL LIFECYCLE TESTS
# ============================================================================

class TestBondFullLifecycle:
    """Tests for complete bond lifecycle scenarios."""

    def test_bond_issue_to_maturity(self):
        """Complete bond lifecycle: issue → coupons → redemption."""
        # Create bond with 2 semi-annual coupons
        bond_state = {
            'face_value': 1000.0,
            'coupon_rate': 0.06,  # 6% annual
            'coupon_frequency': 2,
            'coupon_schedule': [
                (datetime(2025, 6, 15), 30.0),  # $30 per coupon
                (datetime(2025, 12, 15), 30.0),
            ],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'corporation',
            'holder_wallet': 'investor',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': 0,
            'accrued_interest': 0.0,
            'redeemed': False,
            'paid_coupons': [],
        }

        # Step 1: First coupon payment
        view1 = FakeView(
            balances={
                'investor': {'BOND': 5, 'USD': 0},
                'corporation': {'USD': 100000},
            },
            states={'BOND': bond_state},
        )

        result1 = compute_coupon_payment(view1, 'BOND', datetime(2025, 6, 15))
        assert len(result1.moves) == 1
        # 5 bonds × $30 = $150
        assert result1.moves[0].quantity == 150.0

        # Update state
        state_after_coupon1 = next(d for d in result1.state_changes if d.unit == 'BOND').new_state
        assert state_after_coupon1['next_coupon_index'] == 1

        # Step 2: Second coupon payment
        view2 = FakeView(
            balances={
                'investor': {'BOND': 5, 'USD': 150},
                'corporation': {'USD': 99850},
            },
            states={'BOND': state_after_coupon1},
        )

        result2 = compute_coupon_payment(view2, 'BOND', datetime(2025, 12, 15))
        assert len(result2.moves) == 1
        assert result2.moves[0].quantity == 150.0

        state_after_coupon2 = next(d for d in result2.state_changes if d.unit == 'BOND').new_state
        assert state_after_coupon2['next_coupon_index'] == 2

        # Step 3: Redemption at maturity
        view3 = FakeView(
            balances={
                'investor': {'BOND': 5, 'USD': 300},
                'corporation': {'USD': 99700},
            },
            states={'BOND': state_after_coupon2},
        )

        result3 = compute_redemption(view3, 'BOND', datetime(2025, 12, 15))
        assert len(result3.moves) == 1
        # 5 bonds × $1000 = $5000
        assert result3.moves[0].quantity == 5000.0

        state_final = next(d for d in result3.state_changes if d.unit == 'BOND').new_state
        assert state_final['redeemed'] is True

        # Total received by investor: $150 + $150 + $5000 = $5300
        # On $5000 invested (5 × $1000), that's 6% return over 1 year


# ============================================================================
# CONSERVATION LAW TESTS
# ============================================================================

class TestConservationLaws:
    """Tests verifying conservation laws for bonds."""

    def test_coupon_payment_conserves_cash(self):
        """Coupon payment is a pure transfer (conserves total cash)."""
        bond_state = {
            'face_value': 1000.0,
            'coupon_rate': 0.05,
            'coupon_frequency': 2,
            'coupon_schedule': [(datetime(2025, 6, 15), 25.0)],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'issuer',
            'holder_wallet': 'holder',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': 0,
            'accrued_interest': 0.0,
            'redeemed': False,
            'paid_coupons': [],
        }

        view = FakeView(
            balances={
                'holder': {'BOND': 10, 'USD': 0},
                'issuer': {'USD': 10000},
            },
            states={'BOND': bond_state},
        )

        result = compute_coupon_payment(view, 'BOND', datetime(2025, 6, 15))

        # Each move transfers from issuer to holder
        for move in result.moves:
            assert move.source == 'issuer'
            assert move.dest != 'issuer'
            assert move.quantity > 0

    def test_redemption_conserves_cash(self):
        """Redemption is a pure transfer (conserves total cash)."""
        bond_state = {
            'face_value': 1000.0,
            'coupon_rate': 0.05,
            'coupon_frequency': 2,
            'coupon_schedule': [],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'issuer',
            'holder_wallet': 'holder',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': 0,
            'accrued_interest': 0.0,
            'redeemed': False,
            'paid_coupons': [],
        }

        view = FakeView(
            balances={
                'holder': {'BOND': 10},
                'alice': {'BOND': 5},
                'issuer': {'USD': 100000},
            },
            states={'BOND': bond_state},
        )

        result = compute_redemption(view, 'BOND', datetime(2025, 12, 15))

        # Verify all moves are from issuer to holders
        total_out = 0
        for move in result.moves:
            assert move.source == 'issuer'
            total_out += move.quantity

        # Total should equal sum of all bonds × face value
        # (10 + 5) × 1000 = 15000
        assert total_out == 15000.0
