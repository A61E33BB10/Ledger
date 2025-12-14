"""
test_bonds.py - Unit tests for bond units with coupons and accrued interest

Tests:
- Coupon dataclass
- Factory function (create_bond_unit)
- Day count conventions (30/360, ACT/360, ACT/365)
- Accrued interest calculation (compute_accrued_interest - pure function)
- Coupon processing (process_coupons → DeferredCash entitlements)
- Redemption (compute_redemption)
- transact() interface
- Full bond lifecycle

"""

import pytest
from datetime import datetime, date
from decimal import Decimal
from tests.fake_view import FakeView
from ledger import (
    Coupon,
    create_bond_unit,
    compute_accrued_interest,
    process_coupons,
    compute_redemption,
    bond_transact,
    year_fraction,
)


# ============================================================================
# COUPON DATACLASS TESTS
# ============================================================================

class TestCoupon:
    """Tests for the Coupon frozen dataclass."""

    def test_create_coupon(self):
        """Create a valid coupon."""
        coupon = Coupon(
            payment_date=datetime(2025, 6, 15),
            amount=25.0,
            currency="USD",
        )
        assert coupon.payment_date == datetime(2025, 6, 15)
        assert coupon.amount == Decimal("25.0")
        assert coupon.currency == "USD"

    def test_coupon_is_frozen(self):
        """Coupon is immutable."""
        coupon = Coupon(datetime(2025, 6, 15), 25.0, "USD")
        with pytest.raises(AttributeError):
            coupon.amount = 50.0

    def test_coupon_key(self):
        """Coupon key is the date ISO format."""
        coupon = Coupon(datetime(2025, 6, 15, 10, 30), 25.0, "USD")
        assert coupon.key == "2025-06-15"

    def test_zero_amount_raises(self):
        """Zero coupon amount raises ValueError."""
        with pytest.raises(ValueError, match="amount must be positive"):
            Coupon(datetime(2025, 6, 15), 0.0, "USD")

    def test_negative_amount_raises(self):
        """Negative coupon amount raises ValueError."""
        with pytest.raises(ValueError, match="amount must be positive"):
            Coupon(datetime(2025, 6, 15), -10.0, "USD")


# ============================================================================
# DAY COUNT / YEAR FRACTION TESTS
# ============================================================================

class TestYearFraction:
    """Tests for year_fraction day count convention helper."""

    def test_30_360_one_year(self):
        """30/360: exactly one year is 1.0."""
        start = date(2024, 1, 15)
        end = date(2025, 1, 15)
        frac = year_fraction(start, end, "30/360")
        assert float(frac) == pytest.approx(1.0, abs=0.001)

    def test_30_360_half_year(self):
        """30/360: six months is 0.5."""
        start = date(2024, 1, 15)
        end = date(2024, 7, 15)
        frac = year_fraction(start, end, "30/360")
        assert float(frac) == pytest.approx(0.5, abs=0.001)

    def test_30_360_one_month(self):
        """30/360: one month is 30/360 = 0.0833..."""
        start = date(2024, 1, 15)
        end = date(2024, 2, 15)
        frac = year_fraction(start, end, "30/360")
        assert float(frac) == pytest.approx(30/360, abs=0.001)

    def test_act_360_one_year(self):
        """ACT/360: 365/366 days is actual/360."""
        start = date(2024, 1, 15)
        end = date(2025, 1, 15)  # 366 days (leap year)
        frac = year_fraction(start, end, "ACT/360")
        # 2024 is leap year, so 366 days
        assert float(frac) == pytest.approx(366/360, abs=0.001)

    def test_act_360_30_days(self):
        """ACT/360: 30 actual days."""
        start = date(2024, 1, 15)
        end = date(2024, 2, 14)  # 30 days
        frac = year_fraction(start, end, "ACT/360")
        assert float(frac) == pytest.approx(30/360, abs=0.001)

    def test_act_365_one_year(self):
        """ACT/365: actual days / 365."""
        start = date(2024, 1, 15)
        end = date(2025, 1, 15)  # 366 days (leap year)
        frac = year_fraction(start, end, "ACT/365")
        assert float(frac) == pytest.approx(366/365, abs=0.001)

    def test_invalid_convention_raises(self):
        """Invalid day count convention raises ValueError."""
        with pytest.raises(ValueError, match="Unknown day count convention"):
            year_fraction(date(2024, 1, 1), date(2024, 2, 1), "INVALID")


# ============================================================================
# CREATE BOND UNIT TESTS
# ============================================================================

class TestCreateBondUnit:
    """Tests for create_bond_unit factory function."""

    def test_create_basic_corporate_bond(self):
        """Create a basic corporate bond with coupon schedule."""
        schedule = [
            Coupon(datetime(2025, 6, 15), 25.0, "USD"),
            Coupon(datetime(2025, 12, 15), 25.0, "USD"),
        ]
        bond = create_bond_unit(
            symbol="CORP_5Y_2029",
            name="Corporate Bond 5% 2029",
            face_value=1000.0,
            maturity_date=datetime(2025, 12, 15),
            currency="USD",
            issuer_wallet="corporation",
            issue_date=datetime(2024, 12, 15),
            coupon_schedule=schedule,
            day_count_convention="30/360",
        )

        assert bond.symbol == "CORP_5Y_2029"
        assert bond.name == "Corporate Bond 5% 2029"
        assert bond.unit_type == "BOND"

        state = bond.state
        assert state["face_value"] == 1000.0
        assert state["currency"] == "USD"
        assert state["issuer_wallet"] == "corporation"
        assert state["day_count_convention"] == "30/360"
        assert state["next_coupon_index"] == 0
        assert state["redeemed"] is False
        assert len(state["coupon_schedule"]) == 2

    def test_create_zero_coupon_bond(self):
        """Create a zero coupon bond (empty schedule)."""
        bond = create_bond_unit(
            symbol="ZCB",
            name="Zero Coupon Bond",
            face_value=1000.0,
            maturity_date=datetime(2025, 12, 15),
            currency="USD",
            issuer_wallet="issuer",
            issue_date=datetime(2024, 12, 15),
            coupon_schedule=[],
        )

        assert bond.state["coupon_schedule"] == []

    def test_create_bond_act_360(self):
        """Create a bond with ACT/360 convention."""
        bond = create_bond_unit(
            symbol="ACT360",
            name="ACT/360 Bond",
            face_value=1000.0,
            maturity_date=datetime(2025, 12, 15),
            currency="USD",
            issuer_wallet="issuer",
            issue_date=datetime(2024, 12, 15),
            coupon_schedule=[],
            day_count_convention="ACT/360",
        )

        assert bond.state["day_count_convention"] == "ACT/360"

    def test_create_bond_act_365(self):
        """Create a bond with ACT/365 convention."""
        bond = create_bond_unit(
            symbol="ACT365",
            name="ACT/365 Bond",
            face_value=1000.0,
            maturity_date=datetime(2025, 12, 15),
            currency="USD",
            issuer_wallet="issuer",
            issue_date=datetime(2024, 12, 15),
            coupon_schedule=[],
            day_count_convention="ACT/365",
        )

        assert bond.state["day_count_convention"] == "ACT/365"

    def test_zero_face_value_raises(self):
        """Zero face_value raises ValueError."""
        with pytest.raises(ValueError, match="face_value must be positive"):
            create_bond_unit(
                symbol="BAD",
                name="Bad Bond",
                face_value=0.0,
                maturity_date=datetime(2029, 12, 15),
                currency="USD",
                issuer_wallet="issuer",
                issue_date=datetime(2024, 12, 15),
                coupon_schedule=[],
            )

    def test_negative_face_value_raises(self):
        """Negative face_value raises ValueError."""
        with pytest.raises(ValueError, match="face_value must be positive"):
            create_bond_unit(
                symbol="BAD",
                name="Bad Bond",
                face_value=-100.0,
                maturity_date=datetime(2029, 12, 15),
                currency="USD",
                issuer_wallet="issuer",
                issue_date=datetime(2024, 12, 15),
                coupon_schedule=[],
            )

    def test_empty_issuer_raises(self):
        """Empty issuer_wallet raises ValueError."""
        with pytest.raises(ValueError, match="issuer_wallet cannot be empty"):
            create_bond_unit(
                symbol="BAD",
                name="Bad Bond",
                face_value=1000.0,
                maturity_date=datetime(2029, 12, 15),
                currency="USD",
                issuer_wallet="",
                issue_date=datetime(2024, 12, 15),
                coupon_schedule=[],
            )

    def test_invalid_day_count_raises(self):
        """Invalid day_count_convention raises ValueError."""
        with pytest.raises(ValueError, match="Unknown day_count_convention"):
            create_bond_unit(
                symbol="BAD",
                name="Bad Bond",
                face_value=1000.0,
                maturity_date=datetime(2029, 12, 15),
                currency="USD",
                issuer_wallet="issuer",
                issue_date=datetime(2024, 12, 15),
                coupon_schedule=[],
                day_count_convention="INVALID",
            )


# ============================================================================
# ACCRUED INTEREST TESTS (Pure Function)
# ============================================================================

class TestComputeAccruedInterest:
    """Tests for compute_accrued_interest pure function."""

    def test_accrued_interest_at_issue_date(self):
        """Accrued interest is zero at issue date."""
        accrued = compute_accrued_interest(
            coupon_amount=25.0,
            last_coupon_date=date(2024, 12, 15),
            next_coupon_date=date(2025, 6, 15),
            settlement_date=date(2024, 12, 15),
            day_count_convention="30/360",
        )
        assert accrued == Decimal("0.0")

    def test_accrued_interest_half_period(self):
        """Accrued interest at half of coupon period."""
        accrued = compute_accrued_interest(
            coupon_amount=25.0,
            last_coupon_date=date(2024, 12, 15),
            next_coupon_date=date(2025, 6, 15),
            settlement_date=date(2025, 3, 15),  # Half way
            day_count_convention="30/360",
        )
        # Expected: 25 * (3 months / 6 months) = 12.5
        assert accrued == pytest.approx(12.5, abs=0.1)

    def test_accrued_interest_full_period(self):
        """Accrued interest equals full coupon at payment date."""
        accrued = compute_accrued_interest(
            coupon_amount=25.0,
            last_coupon_date=date(2024, 12, 15),
            next_coupon_date=date(2025, 6, 15),
            settlement_date=date(2025, 6, 15),
            day_count_convention="30/360",
        )
        assert accrued == Decimal("25.0")

    def test_accrued_interest_before_last_coupon(self):
        """Accrued is 0 before last coupon date."""
        accrued = compute_accrued_interest(
            coupon_amount=25.0,
            last_coupon_date=date(2024, 12, 15),
            next_coupon_date=date(2025, 6, 15),
            settlement_date=date(2024, 12, 1),  # Before last coupon
            day_count_convention="30/360",
        )
        assert accrued == Decimal("0.0")

    def test_accrued_interest_act_360(self):
        """Accrued interest with ACT/360 convention."""
        accrued = compute_accrued_interest(
            coupon_amount=25.0,
            last_coupon_date=date(2024, 12, 15),
            next_coupon_date=date(2025, 6, 15),
            settlement_date=date(2025, 1, 14),  # 30 actual days
            day_count_convention="ACT/360",
        )
        # 30 days passed out of ~182 days total period
        assert accrued > 0


# ============================================================================
# COUPON PROCESSING TESTS
# ============================================================================

class TestProcessCoupons:
    """Tests for process_coupons function (creates DeferredCash entitlements)."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.bond_state = {
            'face_value': Decimal("1000.0"),
            'coupon_schedule': [
                Coupon(datetime(2025, 6, 15), 25.0, "USD"),
                Coupon(datetime(2025, 12, 15), 25.0, "USD"),
            ],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'issuer',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': Decimal("0"),
            'processed_coupons': [],
            'redeemed': False,
        }

    def test_coupon_payment_creates_deferred_cash(self):
        """Coupon payment creates DeferredCash entitlements on scheduled date."""
        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10"), 'USD': Decimal("0")},
                'issuer': {'USD': Decimal("10000")},
            },
            states={'BOND': self.bond_state},
        )

        result = process_coupons(view, 'BOND', datetime(2025, 6, 15))

        # One entitlement move (DeferredCash unit from system to holder)
        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'system'
        assert move.dest == 'holder'
        assert move.quantity == Decimal("1.0")  # DeferredCash quantity is always 1

        # DeferredCash unit created with correct amount
        assert len(result.units_to_create) == 1
        dc_unit = result.units_to_create[0]
        # 10 bonds × $25 coupon = $250
        assert dc_unit.state['amount'] == 250.0
        assert dc_unit.state['currency'] == 'USD'
        assert dc_unit.state['payer_wallet'] == 'issuer'
        assert dc_unit.state['payee_wallet'] == 'holder'

    def test_coupon_payment_updates_state(self):
        """Coupon payment updates processed_coupons."""
        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'issuer': {'USD': Decimal("10000")},
            },
            states={'BOND': self.bond_state},
        )

        result = process_coupons(view, 'BOND', datetime(2025, 6, 15))
        sc = next(d for d in result.state_changes if d.unit == "BOND")

        assert "2025-06-15" in sc.new_state['processed_coupons']

    def test_coupon_payment_before_schedule_returns_empty(self):
        """Coupon payment before scheduled date returns empty result."""
        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'issuer': {'USD': Decimal("10000")},
            },
            states={'BOND': self.bond_state},
        )

        result = process_coupons(view, 'BOND', datetime(2025, 6, 1))

        assert len(result.moves) == 0

    def test_coupon_payment_multiple_holders(self):
        """Coupon payment creates DeferredCash for multiple bondholders."""
        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'alice': {'BOND': Decimal("5")},
                'bob': {'BOND': Decimal("3")},
                'issuer': {'USD': Decimal("100000")},
            },
            states={'BOND': self.bond_state},
        )

        result = process_coupons(view, 'BOND', datetime(2025, 6, 15))

        # Three entitlement moves (one DeferredCash per holder)
        assert len(result.moves) == 3
        assert len(result.units_to_create) == 3

        # Verify total payment amount in DeferredCash units
        total = sum(dc.state['amount'] for dc in result.units_to_create)
        # (10 + 5 + 3) × $25 = $450
        assert total == Decimal("450.0")

    def test_coupon_payment_issuer_not_paid(self):
        """Issuer does not receive coupon payments on their own bonds."""
        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'issuer': {'BOND': Decimal("5"), 'USD': Decimal("100000")},  # Issuer holds some bonds
            },
            states={'BOND': self.bond_state},
        )

        result = process_coupons(view, 'BOND', datetime(2025, 6, 15))

        # Only holder receives, not issuer
        assert len(result.moves) == 1
        assert result.moves[0].dest == 'holder'

    def test_already_processed_coupon_not_repeated(self):
        """Already processed coupon is not repeated."""
        state = dict(self.bond_state)
        state['processed_coupons'] = ['2025-06-15']  # Already processed

        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'issuer': {'USD': Decimal("100000")},
            },
            states={'BOND': state},
        )

        result = process_coupons(view, 'BOND', datetime(2025, 6, 15))

        assert len(result.moves) == 0

    def test_redeemed_bond_no_coupons(self):
        """Redeemed bond does not process coupons."""
        state = dict(self.bond_state)
        state['redeemed'] = True

        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'issuer': {'USD': Decimal("100000")},
            },
            states={'BOND': state},
        )

        result = process_coupons(view, 'BOND', datetime(2025, 6, 15))

        assert len(result.moves) == 0


# ============================================================================
# REDEMPTION TESTS
# ============================================================================

class TestComputeRedemption:
    """Tests for compute_redemption function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.bond_state = {
            'face_value': Decimal("1000.0"),
            'coupon_schedule': [],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'issuer',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': Decimal("0"),
            'processed_coupons': [],
            'redeemed': False,
        }

    def test_redemption_at_maturity(self):
        """Redemption pays face value to bondholders."""
        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10"), 'USD': Decimal("0")},
                'issuer': {'USD': Decimal("100000")},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_redemption(view, 'BOND', datetime(2025, 12, 15))

        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'issuer'
        assert move.dest == 'holder'
        # 10 bonds × $1000 face value = $10,000
        assert move.quantity == Decimal("10000.0")

    def test_redemption_marks_redeemed(self):
        """Redemption marks bond as redeemed."""
        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'issuer': {'USD': Decimal("100000")},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_redemption(view, 'BOND', datetime(2025, 12, 15))
        sc = next(d for d in result.state_changes if d.unit == "BOND")

        assert sc.new_state['redeemed'] is True

    def test_redemption_multiple_holders(self):
        """Redemption pays all bondholders."""
        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'alice': {'BOND': Decimal("5")},
                'issuer': {'USD': Decimal("100000")},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_redemption(view, 'BOND', datetime(2025, 12, 15))

        assert len(result.moves) == 2
        total = sum(m.quantity for m in result.moves)
        # (10 + 5) × $1000 = $15,000
        assert total == Decimal("15000.0")

    def test_redemption_before_maturity_returns_empty(self):
        """Redemption before maturity returns empty."""
        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'issuer': {'USD': Decimal("100000")},
            },
            states={'BOND': self.bond_state},
        )

        result = compute_redemption(view, 'BOND', datetime(2025, 6, 15))

        assert len(result.moves) == 0

    def test_redemption_already_redeemed_returns_empty(self):
        """Cannot redeem an already-redeemed bond."""
        state = dict(self.bond_state)
        state['redeemed'] = True

        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'issuer': {'USD': Decimal("100000")},
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
            'face_value': Decimal("1000.0"),
            'coupon_schedule': [
                Coupon(datetime(2025, 6, 15), 30.0, "USD"),  # $30 per coupon
                Coupon(datetime(2025, 12, 15), 30.0, "USD"),
            ],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'corporation',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': Decimal("0"),
            'processed_coupons': [],
            'redeemed': False,
        }

        # Step 1: First coupon payment (creates DeferredCash entitlement)
        view1 = FakeView(
            balances={
                'investor': {'BOND': Decimal("5"), 'USD': Decimal("0")},
                'corporation': {'USD': Decimal("100000")},
            },
            states={'BOND': bond_state},
        )

        result1 = process_coupons(view1, 'BOND', datetime(2025, 6, 15))
        assert len(result1.moves) == 1
        assert len(result1.units_to_create) == 1
        # 5 bonds × $30 = $150 in DeferredCash
        assert result1.units_to_create[0].state['amount'] == 150.0

        # Update state
        state_after_coupon1 = next(d for d in result1.state_changes if d.unit == 'BOND').new_state
        assert '2025-06-15' in state_after_coupon1['processed_coupons']

        # Step 2: Second coupon payment
        view2 = FakeView(
            balances={
                'investor': {'BOND': Decimal("5"), 'USD': Decimal("150")},
                'corporation': {'USD': Decimal("99850")},
            },
            states={'BOND': state_after_coupon1},
        )

        result2 = process_coupons(view2, 'BOND', datetime(2025, 12, 15))
        assert len(result2.moves) == 1
        assert result2.units_to_create[0].state['amount'] == 150.0

        state_after_coupon2 = next(d for d in result2.state_changes if d.unit == 'BOND').new_state
        assert '2025-12-15' in state_after_coupon2['processed_coupons']

        # Step 3: Redemption at maturity (direct cash, not DeferredCash)
        view3 = FakeView(
            balances={
                'investor': {'BOND': Decimal("5"), 'USD': Decimal("300")},
                'corporation': {'USD': Decimal("99700")},
            },
            states={'BOND': state_after_coupon2},
        )

        result3 = compute_redemption(view3, 'BOND', datetime(2025, 12, 15))
        assert len(result3.moves) == 1
        # 5 bonds × $1000 = $5000
        assert result3.moves[0].quantity == 5000.0

        state_final = next(d for d in result3.state_changes if d.unit == 'BOND').new_state
        assert state_final['redeemed'] is True


# ============================================================================
# CONSERVATION LAW TESTS
# ============================================================================

class TestConservationLaws:
    """Tests verifying conservation laws for bonds."""

    def test_coupon_payment_creates_correct_entitlements(self):
        """Coupon payment creates DeferredCash with correct amounts."""
        bond_state = {
            'face_value': Decimal("1000.0"),
            'coupon_schedule': [Coupon(datetime(2025, 6, 15), 25.0, "USD")],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'issuer',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': Decimal("0"),
            'processed_coupons': [],
            'redeemed': False,
        }

        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10"), 'USD': Decimal("0")},
                'issuer': {'USD': Decimal("10000")},
            },
            states={'BOND': bond_state},
        )

        result = process_coupons(view, 'BOND', datetime(2025, 6, 15))

        # DeferredCash entitlement created
        assert len(result.units_to_create) == 1
        dc_unit = result.units_to_create[0]

        # DeferredCash records the correct payer/payee
        assert dc_unit.state['payer_wallet'] == 'issuer'
        assert dc_unit.state['payee_wallet'] == 'holder'
        assert dc_unit.state['amount'] == 250.0  # 10 bonds × $25

    def test_redemption_conserves_cash(self):
        """Redemption is a pure transfer (conserves total cash)."""
        bond_state = {
            'face_value': Decimal("1000.0"),
            'coupon_schedule': [],
            'maturity_date': datetime(2025, 12, 15),
            'currency': 'USD',
            'issuer_wallet': 'issuer',
            'day_count_convention': '30/360',
            'issue_date': datetime(2024, 12, 15),
            'next_coupon_index': Decimal("0"),
            'processed_coupons': [],
            'redeemed': False,
        }

        view = FakeView(
            balances={
                'holder': {'BOND': Decimal("10")},
                'alice': {'BOND': Decimal("5")},
                'issuer': {'USD': Decimal("100000")},
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
        assert total_out == Decimal("15000.0")
