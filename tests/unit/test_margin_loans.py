"""
test_margin_loans.py - Unit tests for margin loan units

Tests:
- Factory function (create_margin_loan) validation
- Collateral value calculation with different haircuts
- Margin status calculation at various levels
- Interest accrual over multiple days
- Margin call issuance and cure
- Full and partial liquidation
- Full and partial repayment
- Add collateral functionality
- transact() interface
- Full margin loan lifecycle
- Conservation laws (all moves balance)
- Edge cases (zero collateral, zero loan, etc.)
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from tests.fake_view import FakeView
from ledger import (
    create_margin_loan,
    compute_collateral_value,
    compute_margin_status,
    compute_interest_accrual,
    compute_margin_call,
    compute_margin_cure,
    compute_margin_loan_liquidation,
    compute_repayment,
    compute_add_collateral,
    margin_loan_transact,
    margin_loan_contract,
    MARGIN_STATUS_HEALTHY,
    MARGIN_STATUS_WARNING,
    MARGIN_STATUS_BREACH,
    MARGIN_STATUS_LIQUIDATION,
    UNIT_TYPE_MARGIN_LOAN,
)


# ============================================================================
# CREATE MARGIN LOAN TESTS
# ============================================================================

class TestCreateMarginLoan:
    """Tests for create_margin_loan factory function."""

    def test_create_basic_margin_loan(self):
        """Create a basic margin loan with valid parameters."""
        loan = create_margin_loan(
            symbol="LOAN_001",
            name="Margin Loan #1",
            loan_amount=100000.0,
            interest_rate=0.08,
            collateral={"AAPL": Decimal("1000"), "MSFT": Decimal("500")},
            haircuts={"AAPL": Decimal("0.70"), "MSFT": Decimal("0.75")},
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )

        assert loan.symbol == "LOAN_001"
        assert loan.name == "Margin Loan #1"
        assert loan.unit_type == UNIT_TYPE_MARGIN_LOAN

        state = loan.state
        assert state["loan_amount"] == 100000.0
        assert state["interest_rate"] == 0.08
        assert state["accrued_interest"] == 0.0
        assert state["collateral"] == {"AAPL": Decimal("1000"), "MSFT": Decimal("500")}
        assert state["haircuts"] == {"AAPL": Decimal("0.70"), "MSFT": Decimal("0.75")}
        assert state["initial_margin"] == 1.5
        assert state["maintenance_margin"] == 1.25
        assert state["borrower_wallet"] == "alice"
        assert state["lender_wallet"] == "bank"
        assert state["currency"] == "USD"
        assert state["margin_call_amount"] == 0.0
        assert state["margin_call_deadline"] is None
        assert state["liquidated"] is False

    def test_create_loan_with_origination_date(self):
        """Create margin loan with explicit origination date."""
        orig_date = datetime(2024, 1, 15)
        loan = create_margin_loan(
            symbol="LOAN_002",
            name="Dated Loan",
            loan_amount=50000.0,
            interest_rate=0.06,
            collateral={"AAPL": Decimal("500")},
            haircuts={"AAPL": Decimal("0.80")},
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="bob",
            lender_wallet="bank",
            currency="USD",
            origination_date=orig_date,
        )

        assert loan.state["origination_date"] == orig_date
        assert loan.state["last_accrual_date"] == orig_date

    def test_create_loan_with_treasury_collateral(self):
        """Create margin loan with high-haircut treasury collateral."""
        loan = create_margin_loan(
            symbol="LOAN_003",
            name="Treasury Backed Loan",
            loan_amount=1000000.0,
            interest_rate=0.04,
            collateral={"UST_10Y": Decimal("100")},
            haircuts={"UST_10Y": Decimal("0.95")},  # 95% credit for treasuries
            initial_margin=1.2,
            maintenance_margin=1.1,
            borrower_wallet="fund",
            lender_wallet="prime_broker",
            currency="USD",
        )

        assert loan.state["haircuts"]["UST_10Y"] == Decimal("0.95")

    def test_zero_loan_amount_raises(self):
        """Zero loan_amount raises ValueError."""
        with pytest.raises(ValueError, match="loan_amount must be positive"):
            create_margin_loan(
                symbol="BAD",
                name="Bad Loan",
                loan_amount=0.0,
                interest_rate=0.08,
                collateral={"AAPL": Decimal("100")},
                haircuts={"AAPL": Decimal("0.70")},
                initial_margin=1.5,
                maintenance_margin=1.25,
                borrower_wallet="alice",
                lender_wallet="bank",
                currency="USD",
            )

    def test_negative_loan_amount_raises(self):
        """Negative loan_amount raises ValueError."""
        with pytest.raises(ValueError, match="loan_amount must be positive"):
            create_margin_loan(
                symbol="BAD",
                name="Bad Loan",
                loan_amount=-10000.0,
                interest_rate=0.08,
                collateral={"AAPL": Decimal("100")},
                haircuts={"AAPL": Decimal("0.70")},
                initial_margin=1.5,
                maintenance_margin=1.25,
                borrower_wallet="alice",
                lender_wallet="bank",
                currency="USD",
            )

    def test_negative_interest_rate_raises(self):
        """Negative interest_rate raises ValueError."""
        with pytest.raises(ValueError, match="interest_rate cannot be negative"):
            create_margin_loan(
                symbol="BAD",
                name="Bad Loan",
                loan_amount=100000.0,
                interest_rate=-0.01,
                collateral={"AAPL": Decimal("100")},
                haircuts={"AAPL": Decimal("0.70")},
                initial_margin=1.5,
                maintenance_margin=1.25,
                borrower_wallet="alice",
                lender_wallet="bank",
                currency="USD",
            )

    def test_zero_interest_rate_allowed(self):
        """Zero interest_rate is allowed (interest-free loan)."""
        loan = create_margin_loan(
            symbol="LOAN_FREE",
            name="Interest-Free Loan",
            loan_amount=100000.0,
            interest_rate=0.0,
            collateral={"AAPL": Decimal("100")},
            haircuts={"AAPL": Decimal("0.70")},
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )
        assert loan.state["interest_rate"] == 0.0

    def test_negative_initial_margin_raises(self):
        """Negative initial_margin raises ValueError."""
        with pytest.raises(ValueError, match="initial_margin must be positive"):
            create_margin_loan(
                symbol="BAD",
                name="Bad Loan",
                loan_amount=100000.0,
                interest_rate=0.08,
                collateral={"AAPL": Decimal("100")},
                haircuts={"AAPL": Decimal("0.70")},
                initial_margin=-1.5,
                maintenance_margin=1.25,
                borrower_wallet="alice",
                lender_wallet="bank",
                currency="USD",
            )

    def test_maintenance_exceeds_initial_raises(self):
        """maintenance_margin > initial_margin raises ValueError."""
        with pytest.raises(ValueError, match="maintenance_margin.*cannot exceed"):
            create_margin_loan(
                symbol="BAD",
                name="Bad Loan",
                loan_amount=100000.0,
                interest_rate=0.08,
                collateral={"AAPL": Decimal("100")},
                haircuts={"AAPL": Decimal("0.70")},
                initial_margin=1.25,
                maintenance_margin=1.50,  # Higher than initial
                borrower_wallet="alice",
                lender_wallet="bank",
                currency="USD",
            )

    def test_empty_borrower_wallet_raises(self):
        """Empty borrower_wallet raises ValueError."""
        with pytest.raises(ValueError, match="borrower_wallet cannot be empty"):
            create_margin_loan(
                symbol="BAD",
                name="Bad Loan",
                loan_amount=100000.0,
                interest_rate=0.08,
                collateral={"AAPL": Decimal("100")},
                haircuts={"AAPL": Decimal("0.70")},
                initial_margin=1.5,
                maintenance_margin=1.25,
                borrower_wallet="",
                lender_wallet="bank",
                currency="USD",
            )

    def test_same_borrower_lender_raises(self):
        """Same borrower and lender wallet raises ValueError."""
        with pytest.raises(ValueError, match="must be different"):
            create_margin_loan(
                symbol="BAD",
                name="Bad Loan",
                loan_amount=100000.0,
                interest_rate=0.08,
                collateral={"AAPL": Decimal("100")},
                haircuts={"AAPL": Decimal("0.70")},
                initial_margin=1.5,
                maintenance_margin=1.25,
                borrower_wallet="alice",
                lender_wallet="alice",
                currency="USD",
            )

    def test_haircut_out_of_range_raises(self):
        """Haircut outside [0, 1] raises ValueError."""
        with pytest.raises(ValueError, match="haircut.*must be in"):
            create_margin_loan(
                symbol="BAD",
                name="Bad Loan",
                loan_amount=100000.0,
                interest_rate=0.08,
                collateral={"AAPL": Decimal("100")},
                haircuts={"AAPL": Decimal("1.5")},  # Invalid: > 1
                initial_margin=1.5,
                maintenance_margin=1.25,
                borrower_wallet="alice",
                lender_wallet="bank",
                currency="USD",
            )

    def test_collateral_without_haircut_raises(self):
        """Collateral asset without corresponding haircut raises ValueError."""
        with pytest.raises(ValueError, match="no corresponding haircut"):
            create_margin_loan(
                symbol="BAD",
                name="Bad Loan",
                loan_amount=100000.0,
                interest_rate=0.08,
                collateral={"AAPL": Decimal("100"), "MSFT": Decimal("50")},
                haircuts={"AAPL": Decimal("0.70")},  # Missing MSFT haircut
                initial_margin=1.5,
                maintenance_margin=1.25,
                borrower_wallet="alice",
                lender_wallet="bank",
                currency="USD",
            )

    def test_negative_collateral_quantity_raises(self):
        """Negative collateral quantity raises ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            create_margin_loan(
                symbol="BAD",
                name="Bad Loan",
                loan_amount=100000.0,
                interest_rate=0.08,
                collateral={"AAPL": -100},
                haircuts={"AAPL": Decimal("0.70")},
                initial_margin=1.5,
                maintenance_margin=1.25,
                borrower_wallet="alice",
                lender_wallet="bank",
                currency="USD",
            )


# ============================================================================
# COLLATERAL VALUE TESTS
# ============================================================================

class TestComputeCollateralValue:
    """Tests for compute_collateral_value function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000"), 'MSFT': Decimal("500")},
            'haircuts': {'AAPL': Decimal("0.70"), 'MSFT': Decimal("0.75")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': False,
        }

    def test_collateral_value_basic(self):
        """Calculate collateral value with multiple assets."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
        )
        prices = {'AAPL': Decimal("150.0"), 'MSFT': Decimal("300.0")}

        value = compute_collateral_value(view, 'LOAN_001', prices)

        # AAPL: 1000 * 150 * 0.70 = 105,000
        # MSFT: 500 * 300 * 0.75 = 112,500
        # Total: 217,500
        assert value == pytest.approx(217500.0, abs=0.01)

    def test_collateral_value_missing_price_raises(self):
        """Missing price raises ValueError."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
        )
        prices = {'AAPL': Decimal("150.0")}  # Missing MSFT price

        with pytest.raises(ValueError, match="Missing price for collateral asset 'MSFT'"):
            compute_collateral_value(view, 'LOAN_001', prices)

    def test_collateral_value_zero_haircut(self):
        """Zero haircut means asset not counted."""
        state = dict(self.loan_state)
        state['haircuts'] = {'AAPL': Decimal("0.0"), 'MSFT': Decimal("0.75")}

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
        )
        prices = {'AAPL': Decimal("150.0"), 'MSFT': Decimal("300.0")}

        value = compute_collateral_value(view, 'LOAN_001', prices)

        # Only MSFT counted: 500 * 300 * 0.75 = 112,500
        assert value == pytest.approx(112500.0, abs=0.01)

    def test_collateral_value_full_haircut(self):
        """Full haircut (1.0) gives full credit."""
        state = dict(self.loan_state)
        state['collateral'] = {'UST_10Y': Decimal("1000")}
        state['haircuts'] = {'UST_10Y': Decimal("1.0")}

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
        )
        prices = {'UST_10Y': Decimal("100.0")}

        value = compute_collateral_value(view, 'LOAN_001', prices)

        # 1000 * 100 * 1.0 = 100,000
        assert value == pytest.approx(100000.0, abs=0.01)

    def test_collateral_value_empty_collateral(self):
        """Empty collateral pool has zero value."""
        state = dict(self.loan_state)
        state['collateral'] = {}

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
        )
        prices = {'AAPL': Decimal("150.0")}

        value = compute_collateral_value(view, 'LOAN_001', prices)
        assert value == Decimal("0.0")


# ============================================================================
# MARGIN STATUS TESTS
# ============================================================================

class TestComputeMarginStatus:
    """Tests for compute_margin_status function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': False,
        }

    def test_margin_status_healthy(self):
        """Margin status is HEALTHY when ratio >= initial_margin."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 1),
        )
        # 1000 * 200 * 0.80 = 160,000 collateral value
        # 160,000 / 100,000 = 1.6 margin ratio >= 1.5 initial
        prices = {'AAPL': Decimal("200.0")}

        status = compute_margin_status(view, 'LOAN_001', prices)

        assert status['status'] == MARGIN_STATUS_HEALTHY
        assert float(status['collateral_value']) == pytest.approx(160000.0, abs=0.01)
        assert float(status['total_debt']) == pytest.approx(100000.0, abs=0.01)
        assert float(status['margin_ratio']) == pytest.approx(1.6, abs=0.01)
        assert status['shortfall'] == 0.0
        assert status['excess'] > 0

    def test_margin_status_warning(self):
        """Margin status is WARNING when maintenance <= ratio < initial."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 1),
        )
        # 1000 * 175 * 0.80 = 140,000 collateral value
        # 140,000 / 100,000 = 1.4 margin ratio
        # 1.25 <= 1.4 < 1.5 -> WARNING
        prices = {'AAPL': Decimal("175.0")}

        status = compute_margin_status(view, 'LOAN_001', prices)

        assert status['status'] == MARGIN_STATUS_WARNING
        assert float(status['margin_ratio']) == pytest.approx(1.4, abs=0.01)
        assert status['shortfall'] == 0.0

    def test_margin_status_breach(self):
        """Margin status is BREACH when ratio < maintenance."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 1),
        )
        # 1000 * 150 * 0.80 = 120,000 collateral value
        # 120,000 / 100,000 = 1.2 margin ratio < 1.25 maintenance
        prices = {'AAPL': Decimal("150.0")}

        status = compute_margin_status(view, 'LOAN_001', prices)

        assert status['status'] == MARGIN_STATUS_BREACH
        assert float(status['margin_ratio']) == pytest.approx(1.2, abs=0.01)
        # Shortfall = 1.25 * 100,000 - 120,000 = 5,000
        assert float(status['shortfall']) == pytest.approx(5000.0, abs=0.01)

    def test_margin_status_liquidation(self):
        """Margin status is LIQUIDATION when deadline has passed."""
        state = dict(self.loan_state)
        state['margin_call_deadline'] = datetime(2024, 1, 1, 12, 0)

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 2),  # After deadline
        )
        prices = {'AAPL': Decimal("150.0")}

        status = compute_margin_status(view, 'LOAN_001', prices)

        assert status['status'] == MARGIN_STATUS_LIQUIDATION

    def test_margin_status_with_accrued_interest(self):
        """Margin status accounts for accrued interest in total debt."""
        state = dict(self.loan_state)
        state['accrued_interest'] = 5000.0  # $5k accrued

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 1),
        )
        # 1000 * 200 * 0.80 = 160,000 collateral value
        # Total debt = 100,000 + 5,000 = 105,000
        # 160,000 / 105,000 = 1.52 margin ratio
        prices = {'AAPL': Decimal("200.0")}

        status = compute_margin_status(view, 'LOAN_001', prices)

        assert float(status['total_debt']) == pytest.approx(105000.0, abs=0.01)
        assert float(status['margin_ratio']) == pytest.approx(160000/105000, abs=0.01)

    def test_margin_status_zero_debt(self):
        """Zero debt gives infinite margin ratio."""
        state = dict(self.loan_state)
        state['loan_amount'] = 0.0
        state['accrued_interest'] = 0.0

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 1),
        )
        prices = {'AAPL': Decimal("200.0")}

        status = compute_margin_status(view, 'LOAN_001', prices)

        assert status['status'] == MARGIN_STATUS_HEALTHY
        assert status['margin_ratio'] == float('inf')

    def test_margin_status_liquidated_loan(self):
        """Liquidated loan returns LIQUIDATION status."""
        state = dict(self.loan_state)
        state['liquidated'] = True

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 1),
        )
        prices = {'AAPL': Decimal("200.0")}

        status = compute_margin_status(view, 'LOAN_001', prices)

        assert status['status'] == MARGIN_STATUS_LIQUIDATION


# ============================================================================
# INTEREST ACCRUAL TESTS
# ============================================================================

class TestComputeInterestAccrual:
    """Tests for compute_interest_accrual function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': False,
        }

    def test_interest_accrual_30_days(self):
        """Accrue 30 days of interest at 8%."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 2, 1),
        )

        result = compute_interest_accrual(view, 'LOAN_001', 30)

        # Interest = 100,000 * 0.08 / 365 * 30 = $657.53
        assert len(result.moves) == 0  # No moves, just state update
        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert float(sc.new_state['accrued_interest']) == pytest.approx(657.53, abs=0.01)

    def test_interest_accrual_one_year(self):
        """Accrue full year of interest at 8%."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2025, 1, 1),
        )

        result = compute_interest_accrual(view, 'LOAN_001', 365)

        # Interest = 100,000 * 0.08 = 8,000
        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert float(sc.new_state['accrued_interest']) == pytest.approx(8000.0, abs=0.01)

    def test_interest_accrual_cumulative(self):
        """Interest accrues cumulatively."""
        state = dict(self.loan_state)
        state['accrued_interest'] = 500.0  # Already accrued

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 2, 1),
        )

        result = compute_interest_accrual(view, 'LOAN_001', 30)

        # New interest = 100,000 * 0.08 / 365 * 30 = $657.53
        # Total = 500 + 657.53 = 1157.53
        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert float(sc.new_state['accrued_interest']) == pytest.approx(1157.53, abs=0.01)

    def test_interest_accrual_zero_days(self):
        """Zero days accrues no interest."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 1),
        )

        result = compute_interest_accrual(view, 'LOAN_001', 0)

        assert result.is_empty()

    def test_interest_accrual_negative_days_raises(self):
        """Negative days raises ValueError."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 1),
        )

        with pytest.raises(ValueError, match="days cannot be negative"):
            compute_interest_accrual(view, 'LOAN_001', -5)

    def test_interest_accrual_zero_interest_rate(self):
        """Zero interest rate accrues no interest."""
        state = dict(self.loan_state)
        state['interest_rate'] = 0.0

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 2, 1),
        )

        result = compute_interest_accrual(view, 'LOAN_001', 30)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['accrued_interest'] == 0.0

    def test_interest_accrual_liquidated_loan(self):
        """Liquidated loan does not accrue interest."""
        state = dict(self.loan_state)
        state['liquidated'] = True

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 2, 1),
        )

        result = compute_interest_accrual(view, 'LOAN_001', 30)

        assert result.is_empty()


# ============================================================================
# MARGIN CALL TESTS
# ============================================================================

class TestComputeMarginCall:
    """Tests for compute_margin_call function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'margin_call_deadline_days': 3,
            'liquidated': False,
        }

    def test_margin_call_issued_on_breach(self):
        """Margin call is issued when below maintenance."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 15),
        )
        # 1000 * 150 * 0.80 = 120,000 < 1.25 * 100,000 = 125,000
        prices = {'AAPL': Decimal("150.0")}

        result = compute_margin_call(view, 'LOAN_001', prices)

        assert len(result.moves) == 0
        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert float(sc.new_state['margin_call_amount']) == pytest.approx(5000.0, abs=0.01)
        assert sc.new_state['margin_call_deadline'] == datetime(2024, 1, 18)  # +3 days

    def test_no_margin_call_when_healthy(self):
        """No margin call when above maintenance margin."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 15),
        )
        # 1000 * 200 * 0.80 = 160,000 >= 1.25 * 100,000
        prices = {'AAPL': Decimal("200.0")}

        result = compute_margin_call(view, 'LOAN_001', prices)

        assert result.is_empty()

    def test_no_margin_call_when_already_active(self):
        """No new margin call when one is already active."""
        state = dict(self.loan_state)
        state['margin_call_deadline'] = datetime(2024, 1, 18)
        state['margin_call_amount'] = 5000.0

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 16),
        )
        prices = {'AAPL': Decimal("140.0")}  # Even worse

        result = compute_margin_call(view, 'LOAN_001', prices)

        assert result.is_empty()

    def test_no_margin_call_on_liquidated_loan(self):
        """No margin call on liquidated loan."""
        state = dict(self.loan_state)
        state['liquidated'] = True

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 15),
        )
        prices = {'AAPL': Decimal("100.0")}

        result = compute_margin_call(view, 'LOAN_001', prices)

        assert result.is_empty()


# ============================================================================
# MARGIN CURE TESTS
# ============================================================================

class TestComputeMarginCure:
    """Tests for compute_margin_cure function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("1000.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 5000.0,
            'margin_call_deadline': datetime(2024, 1, 18),
            'liquidated': False,
            'total_interest_paid': 0.0,
            'total_principal_paid': 0.0,
        }

    def test_cure_applies_to_interest_first(self):
        """Cure payment applies to interest before principal."""
        view = FakeView(
            balances={
                'alice': {'USD': Decimal("50000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 16),
        )

        result = compute_margin_cure(view, 'LOAN_001', 1500.0)

        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'alice'
        assert move.dest == 'bank'
        assert move.quantity == Decimal("1500.0")
        assert move.unit_symbol == 'USD'

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        # 1000 interest paid first, then 500 to principal
        assert sc.new_state['accrued_interest'] == 0.0
        assert float(sc.new_state['loan_amount']) == pytest.approx(99500.0, abs=0.01)
        assert sc.new_state['total_interest_paid'] == 1000.0
        assert sc.new_state['total_principal_paid'] == 500.0

    def test_cure_clears_margin_call_on_full_payoff(self):
        """Cure clears margin call when debt is fully paid."""
        state = dict(self.loan_state)
        state['loan_amount'] = 1000.0
        state['accrued_interest'] = 100.0

        view = FakeView(
            balances={
                'alice': {'USD': Decimal("50000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': state},
            time=datetime(2024, 1, 16),
        )

        result = compute_margin_cure(view, 'LOAN_001', 1100.0)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert float(sc.new_state['loan_amount']) == pytest.approx(0.0, abs=0.01)
        assert float(sc.new_state['accrued_interest']) == pytest.approx(0.0, abs=0.01)
        assert sc.new_state['margin_call_amount'] == 0.0
        assert sc.new_state['margin_call_deadline'] is None

    def test_cure_zero_amount_raises(self):
        """Zero cure_amount raises ValueError."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 16),
        )

        with pytest.raises(ValueError, match="cure_amount must be positive"):
            compute_margin_cure(view, 'LOAN_001', 0.0)

    def test_cure_exceeds_debt_raises(self):
        """Cure amount exceeding total debt raises ValueError."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 16),
        )

        with pytest.raises(ValueError, match="exceeds total_debt"):
            compute_margin_cure(view, 'LOAN_001', 200000.0)

    def test_cure_liquidated_loan_raises(self):
        """Cure on liquidated loan raises ValueError."""
        state = dict(self.loan_state)
        state['liquidated'] = True

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 16),
        )

        with pytest.raises(ValueError, match="Cannot cure a liquidated loan"):
            compute_margin_cure(view, 'LOAN_001', 5000.0)


# ============================================================================
# LIQUIDATION TESTS
# ============================================================================

class TestComputeLiquidation:
    """Tests for compute_liquidation function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("2000.0"),  # Total debt = 102,000
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 5000.0,
            'margin_call_deadline': datetime(2024, 1, 15),  # Past due
            'liquidated': False,
        }

    def test_liquidation_full_recovery(self):
        """Liquidation with proceeds covering full debt."""
        view = FakeView(
            balances={
                'alice': {'USD': Decimal("10000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 16),  # After deadline
        )
        prices = {'AAPL': Decimal("120.0")}
        # Sale proceeds = $110,000 (sold 1000 shares at $110)
        sale_proceeds = 110000.0

        result = compute_margin_loan_liquidation(view, 'LOAN_001', prices, sale_proceeds)

        # Should have debt payment + surplus return
        assert len(result.moves) == 2

        # First move: debt payment
        debt_move = result.moves[0]
        assert debt_move.source == 'alice'
        assert debt_move.dest == 'bank'
        assert debt_move.quantity == pytest.approx(102000.0, abs=0.01)

        # Second move: surplus to borrower
        surplus_move = result.moves[1]
        assert surplus_move.source == 'bank'
        assert surplus_move.dest == 'alice'
        assert surplus_move.quantity == pytest.approx(8000.0, abs=0.01)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['liquidated'] is True
        assert sc.new_state['collateral'] == {}
        assert sc.new_state['loan_amount'] == 0.0
        assert sc.new_state['accrued_interest'] == 0.0

    def test_liquidation_partial_recovery(self):
        """Liquidation with proceeds less than debt (bad debt)."""
        view = FakeView(
            balances={
                'alice': {'USD': Decimal("10000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 16),
        )
        prices = {'AAPL': Decimal("80.0")}
        # Sale proceeds = $80,000 (sold at distressed price)
        sale_proceeds = 80000.0

        result = compute_margin_loan_liquidation(view, 'LOAN_001', prices, sale_proceeds)

        # Only partial debt payment
        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.quantity == pytest.approx(80000.0, abs=0.01)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['liquidated'] is True
        # On liquidation, loan_amount and accrued_interest are zeroed.
        # The deficiency (unpaid debt) is tracked separately as bad debt.
        # Remaining debt = 102,000 - 80,000 = 22,000 (tracked as deficiency)
        assert sc.new_state['accrued_interest'] == 0.0
        assert sc.new_state['loan_amount'] == 0.0
        assert float(sc.new_state['liquidation_deficiency']) == pytest.approx(22000.0, abs=0.01)

    def test_liquidation_already_liquidated_raises(self):
        """Cannot liquidate already liquidated loan."""
        state = dict(self.loan_state)
        state['liquidated'] = True

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 16),
        )
        prices = {'AAPL': Decimal("100.0")}

        with pytest.raises(ValueError, match="already liquidated"):
            compute_margin_loan_liquidation(view, 'LOAN_001', prices, 80000.0)

    def test_liquidation_negative_proceeds_raises(self):
        """Negative sale proceeds raises ValueError."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 16),
        )
        prices = {'AAPL': Decimal("100.0")}

        with pytest.raises(ValueError, match="cannot be negative"):
            compute_margin_loan_liquidation(view, 'LOAN_001', prices, -5000.0)

    def test_cannot_liquidate_during_breach_period(self):
        """CRITICAL: Cannot liquidate when status is BREACH (deadline not passed)."""
        state = dict(self.loan_state)
        state['margin_call_deadline'] = datetime(2024, 1, 20)
        view = FakeView(
            balances={'alice': {'USD': Decimal("10000")}, 'bank': {'USD': Decimal("100000")}},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 16),
        )
        prices = {'AAPL': Decimal("120.0")}
        status = compute_margin_status(view, 'LOAN_001', prices)
        assert status['status'] == MARGIN_STATUS_BREACH
        with pytest.raises(ValueError, match="Cannot liquidate.*BREACH"):
            compute_margin_loan_liquidation(view, 'LOAN_001', prices, 90000.0)

    def test_can_liquidate_when_deadline_passed(self):
        """CRITICAL: CAN liquidate when status is LIQUIDATION (deadline passed)."""
        state = dict(self.loan_state)
        state['margin_call_deadline'] = datetime(2024, 1, 15)
        view = FakeView(
            balances={'alice': {'USD': Decimal("10000")}, 'bank': {'USD': Decimal("100000")}},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 16),
        )
        prices = {'AAPL': Decimal("120.0")}
        status = compute_margin_status(view, 'LOAN_001', prices)
        assert status['status'] == MARGIN_STATUS_LIQUIDATION
        result = compute_margin_loan_liquidation(view, 'LOAN_001', prices, 95000.0)
        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['liquidated'] is True

    def test_margin_call_3day_deadline_liquidate_after_1day_fails(self):
        """CRITICAL: Issue margin call with 3-day deadline, try to liquidate after 1 day - should fail."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'margin_call_deadline_days': 3,
            'liquidated': False,
        }
        view_day0 = FakeView(
            balances={'alice': {'USD': Decimal("50000")}, 'bank': {'USD': Decimal("0")}},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 15),
        )
        prices = {'AAPL': Decimal("150.0")}
        result_call = compute_margin_call(view_day0, 'LOAN_001', prices)
        state_after_call = next(d for d in result_call.state_changes if d.unit == 'LOAN_001').new_state
        assert state_after_call['margin_call_deadline'] == datetime(2024, 1, 18)
        view_day1 = FakeView(
            balances={'alice': {'USD': Decimal("50000")}, 'bank': {'USD': Decimal("0")}},
            states={'LOAN_001': state_after_call},
            time=datetime(2024, 1, 16),
        )
        status = compute_margin_status(view_day1, 'LOAN_001', prices)
        assert status['status'] == MARGIN_STATUS_BREACH
        with pytest.raises(ValueError, match="Cannot liquidate.*BREACH"):
            compute_margin_loan_liquidation(view_day1, 'LOAN_001', prices, 115000.0)

    def test_margin_call_3day_deadline_liquidate_after_4days_succeeds(self):
        """CRITICAL: Issue margin call with 3-day deadline, try to liquidate after 4 days - should succeed."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'margin_call_deadline_days': 3,
            'liquidated': False,
        }
        view_day0 = FakeView(
            balances={'alice': {'USD': Decimal("50000")}, 'bank': {'USD': Decimal("0")}},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 15, 10, 0),
        )
        prices = {'AAPL': Decimal("150.0")}
        result_call = compute_margin_call(view_day0, 'LOAN_001', prices)
        state_after_call = next(d for d in result_call.state_changes if d.unit == 'LOAN_001').new_state
        assert state_after_call['margin_call_deadline'] == datetime(2024, 1, 18, 10, 0)
        view_day4 = FakeView(
            balances={'alice': {'USD': Decimal("50000")}, 'bank': {'USD': Decimal("0")}},
            states={'LOAN_001': state_after_call},
            time=datetime(2024, 1, 19, 10, 0),
        )
        status = compute_margin_status(view_day4, 'LOAN_001', prices)
        assert status['status'] == MARGIN_STATUS_LIQUIDATION
        result = compute_margin_loan_liquidation(view_day4, 'LOAN_001', prices, 115000.0)
        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['liquidated'] is True
        assert sc.new_state['collateral'] == {}
        assert sc.new_state['loan_amount'] == 0.0


# ============================================================================
# REPAYMENT TESTS
# ============================================================================

class TestComputeRepayment:
    """Tests for compute_repayment function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("1000.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': False,
            'total_interest_paid': 0.0,
            'total_principal_paid': 0.0,
        }

    def test_full_repayment(self):
        """Full loan repayment clears all debt."""
        view = FakeView(
            balances={
                'alice': {'USD': Decimal("150000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 6, 1),
        )

        result = compute_repayment(view, 'LOAN_001', 101000.0)

        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'alice'
        assert move.dest == 'bank'
        assert move.quantity == Decimal("101000.0")

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert float(sc.new_state['loan_amount']) == pytest.approx(0.0, abs=0.01)
        assert float(sc.new_state['accrued_interest']) == pytest.approx(0.0, abs=0.01)

    def test_partial_repayment(self):
        """Partial repayment reduces debt."""
        view = FakeView(
            balances={
                'alice': {'USD': Decimal("50000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 6, 1),
        )

        result = compute_repayment(view, 'LOAN_001', 20000.0)

        move = result.moves[0]
        assert move.quantity == Decimal("20000.0")

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        # 1000 interest first, then 19000 principal
        assert sc.new_state['accrued_interest'] == 0.0
        assert float(sc.new_state['loan_amount']) == pytest.approx(81000.0, abs=0.01)

    def test_repayment_interest_only(self):
        """Repayment less than accrued interest pays only interest."""
        view = FakeView(
            balances={
                'alice': {'USD': Decimal("50000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 6, 1),
        )

        result = compute_repayment(view, 'LOAN_001', 500.0)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert float(sc.new_state['accrued_interest']) == pytest.approx(500.0, abs=0.01)
        assert sc.new_state['loan_amount'] == 100000.0  # Unchanged

    def test_repayment_zero_raises(self):
        """Zero repayment raises ValueError."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 6, 1),
        )

        with pytest.raises(ValueError, match="repayment_amount must be positive"):
            compute_repayment(view, 'LOAN_001', 0.0)

    def test_repayment_exceeds_debt_raises(self):
        """Repayment exceeding debt raises ValueError."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 6, 1),
        )

        with pytest.raises(ValueError, match="exceeds total_debt"):
            compute_repayment(view, 'LOAN_001', 200000.0)

    def test_repayment_liquidated_loan_raises(self):
        """Repayment on liquidated loan raises ValueError."""
        state = dict(self.loan_state)
        state['liquidated'] = True

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 6, 1),
        )

        with pytest.raises(ValueError, match="Cannot repay a liquidated loan"):
            compute_repayment(view, 'LOAN_001', 10000.0)


# ============================================================================
# ADD COLLATERAL TESTS
# ============================================================================

class TestComputeAddCollateral:
    """Tests for compute_add_collateral function."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80"), 'MSFT': Decimal("0.75")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': False,
        }

    def test_add_existing_collateral(self):
        """Add more of existing collateral asset."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 15),
        )

        result = compute_add_collateral(view, 'LOAN_001', 'AAPL', 500)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['collateral']['AAPL'] == 1500

    def test_add_new_collateral_asset(self):
        """Add new asset type as collateral."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 15),
        )

        result = compute_add_collateral(view, 'LOAN_001', 'MSFT', 200)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['collateral']['MSFT'] == 200
        assert sc.new_state['collateral']['AAPL'] == 1000  # Unchanged

    def test_add_collateral_zero_quantity_raises(self):
        """Zero quantity raises ValueError."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 15),
        )

        with pytest.raises(ValueError, match="quantity must be positive"):
            compute_add_collateral(view, 'LOAN_001', 'AAPL', 0)

    def test_add_collateral_no_haircut_raises(self):
        """Asset without haircut raises ValueError."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 15),
        )

        with pytest.raises(ValueError, match="No haircut defined"):
            compute_add_collateral(view, 'LOAN_001', 'GOOGL', 100)

    def test_add_collateral_liquidated_raises(self):
        """Adding collateral to liquidated loan raises ValueError."""
        state = dict(self.loan_state)
        state['liquidated'] = True

        view = FakeView(
            balances={},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 15),
        )

        with pytest.raises(ValueError, match="Cannot add collateral to a liquidated"):
            compute_add_collateral(view, 'LOAN_001', 'AAPL', 500)


# ============================================================================
# TRANSACT INTERFACE TESTS
# ============================================================================

class TestTransact:
    """Tests for transact() unified interface."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'margin_call_deadline_days': 3,
            'liquidated': False,
            'total_interest_paid': 0.0,
            'total_principal_paid': 0.0,
        }

    def test_transact_interest_accrual(self):
        """transact handles INTEREST_ACCRUAL event."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 2, 1),
        )

        result = margin_loan_transact(view, 'LOAN_001', 'INTEREST_ACCRUAL',
                                       datetime(2024, 2, 1), days=30)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['accrued_interest'] > 0

    def test_transact_margin_call(self):
        """transact handles MARGIN_CALL event."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 15),
        )
        prices = {'AAPL': Decimal("150.0")}  # Below maintenance

        result = margin_loan_transact(view, 'LOAN_001', 'MARGIN_CALL',
                                       datetime(2024, 1, 15), prices=prices)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['margin_call_amount'] > 0

    def test_transact_repayment(self):
        """transact handles REPAYMENT event."""
        view = FakeView(
            balances={
                'alice': {'USD': Decimal("150000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 6, 1),
        )

        result = margin_loan_transact(view, 'LOAN_001', 'REPAYMENT',
                                       datetime(2024, 6, 1), repayment_amount=50000.0)

        assert len(result.moves) == 1
        assert result.moves[0].quantity == 50000.0

    def test_transact_add_collateral(self):
        """transact handles ADD_COLLATERAL event."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 15),
        )

        result = margin_loan_transact(view, 'LOAN_001', 'ADD_COLLATERAL',
                                       datetime(2024, 1, 15), asset='AAPL', quantity=Decimal("500"))

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['collateral']['AAPL'] == 1500

    def test_transact_unknown_event_raises(self):
        """transact raises ValueError for unknown event type."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 15),
        )

        with pytest.raises(ValueError, match="Unknown event type 'UNKNOWN'"):
            margin_loan_transact(view, 'LOAN_001', 'UNKNOWN', datetime(2024, 1, 15))

    def test_transact_missing_required_params_raises(self):
        """transact raises ValueError when required params missing."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 15),
        )

        # INTEREST_ACCRUAL without days
        with pytest.raises(ValueError, match="Missing 'days' parameter"):
            margin_loan_transact(view, 'LOAN_001', 'INTEREST_ACCRUAL', datetime(2024, 1, 15))


# ============================================================================
# FULL LIFECYCLE TESTS
# ============================================================================

class TestMarginLoanFullLifecycle:
    """Tests for complete margin loan lifecycle scenarios."""

    def test_healthy_loan_to_repayment(self):
        """Complete lifecycle: origination -> interest -> repayment."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': False,
            'total_interest_paid': 0.0,
            'total_principal_paid': 0.0,
            'origination_date': datetime(2024, 1, 1),
            'last_accrual_date': datetime(2024, 1, 1),
        }

        # Step 1: Check initial status (healthy)
        view1 = FakeView(
            balances={'alice': {'USD': Decimal("200000")}, 'bank': {'USD': Decimal("0")}},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 1),
        )
        prices = {'AAPL': Decimal("200.0")}  # Value = 1000 * 200 * 0.8 = 160,000

        status1 = compute_margin_status(view1, 'LOAN_001', prices)
        assert status1['status'] == MARGIN_STATUS_HEALTHY
        assert float(status1['margin_ratio']) == pytest.approx(1.6, abs=0.01)

        # Step 2: Accrue 30 days of interest (updates last_accrual_date to Jan 1)
        result2 = compute_interest_accrual(view1, 'LOAN_001', 30)
        state_after_interest = next(d for d in result2.state_changes if d.unit == 'LOAN_001').new_state
        # Interest = 100,000 * 0.08 / 365 * 30 = $657.53
        expected_interest = 100000 * 0.08 / 365 * 30
        assert float(state_after_interest['accrued_interest']) == pytest.approx(expected_interest, abs=0.01)

        # Step 3: Full repayment on same day (no pending interest)
        # Use the same time to avoid pending interest accumulation
        view3 = FakeView(
            balances={'alice': {'USD': Decimal("200000")}, 'bank': {'USD': Decimal("0")}},
            states={'LOAN_001': state_after_interest},
            time=datetime(2024, 1, 1),  # Same day as accrual
        )

        total_due = 100000 + expected_interest
        result3 = compute_repayment(view3, 'LOAN_001', total_due)

        assert len(result3.moves) == 1
        assert float(result3.moves[0].quantity) == pytest.approx(total_due, abs=0.01)

        final_state = next(d for d in result3.state_changes if d.unit == 'LOAN_001').new_state
        assert float(final_state['loan_amount']) == pytest.approx(0.0, abs=0.01)
        assert float(final_state['accrued_interest']) == pytest.approx(0.0, abs=0.01)

    def test_margin_call_then_cure(self):
        """Lifecycle: price drop -> margin call -> cure."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'margin_call_deadline_days': 3,
            'liquidated': False,
            'total_interest_paid': 0.0,
            'total_principal_paid': 0.0,
        }

        # Step 1: Price drops, margin call issued
        view1 = FakeView(
            balances={'alice': {'USD': Decimal("50000")}, 'bank': {'USD': Decimal("0")}},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 15),
        )
        prices = {'AAPL': Decimal("150.0")}  # Value = 1000 * 150 * 0.8 = 120,000

        status1 = compute_margin_status(view1, 'LOAN_001', prices)
        assert status1['status'] == MARGIN_STATUS_BREACH
        # Shortfall = 1.25 * 100,000 - 120,000 = 5,000
        assert float(status1['shortfall']) == pytest.approx(5000.0, abs=0.01)

        result1 = compute_margin_call(view1, 'LOAN_001', prices)
        state_after_call = next(d for d in result1.state_changes if d.unit == 'LOAN_001').new_state
        assert float(state_after_call['margin_call_amount']) == pytest.approx(5000.0, abs=0.01)
        assert state_after_call['margin_call_deadline'] == datetime(2024, 1, 18)

        # Step 2: Borrower cures with cash payment
        view2 = FakeView(
            balances={'alice': {'USD': Decimal("50000")}, 'bank': {'USD': Decimal("0")}},
            states={'LOAN_001': state_after_call},
            time=datetime(2024, 1, 16),
        )

        # Pay down $10,000 to reduce debt
        result2 = compute_margin_cure(view2, 'LOAN_001', 10000.0, prices=prices)

        assert len(result2.moves) == 1
        assert result2.moves[0].quantity == 10000.0

        state_after_cure = next(d for d in result2.state_changes if d.unit == 'LOAN_001').new_state
        assert float(state_after_cure['loan_amount']) == pytest.approx(90000.0, abs=0.01)

        # Verify margin is now healthy
        # New debt = 90,000, collateral value = 120,000
        # Ratio = 120,000 / 90,000 = 1.33 > 1.25
        view3 = FakeView(
            balances={'alice': {'USD': Decimal("40000")}, 'bank': {'USD': Decimal("10000")}},
            states={'LOAN_001': state_after_cure},
            time=datetime(2024, 1, 16),
        )

        status3 = compute_margin_status(view3, 'LOAN_001', prices)
        assert float(status3['margin_ratio']) == pytest.approx(120000/90000, abs=0.01)
        # Should be above maintenance but below initial
        assert status3['status'] == MARGIN_STATUS_WARNING

    def test_margin_call_then_liquidation(self):
        """Lifecycle: margin call -> deadline passes -> liquidation."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("2000.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 10000.0,
            'margin_call_deadline': datetime(2024, 1, 15),  # Past due
            'liquidated': False,
        }

        view = FakeView(
            balances={'alice': {'USD': Decimal("10000")}, 'bank': {'USD': Decimal("0")}},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 16),  # After deadline
        )
        prices = {'AAPL': Decimal("100.0")}  # Low price

        # Verify liquidation status
        status = compute_margin_status(view, 'LOAN_001', prices)
        assert status['status'] == MARGIN_STATUS_LIQUIDATION

        # Liquidate at distressed price
        # Sale proceeds = 1000 shares * $95/share = $95,000 (assume slippage)
        result = compute_margin_loan_liquidation(view, 'LOAN_001', prices, 95000.0)

        # Total debt = 102,000, proceeds = 95,000
        # Partial recovery - one move for proceeds
        assert len(result.moves) == 1
        assert result.moves[0].quantity == pytest.approx(95000.0, abs=0.01)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['liquidated'] is True
        assert sc.new_state['collateral'] == {}
        # On liquidation, loan_amount and accrued_interest are zeroed.
        # The deficiency (unpaid debt) is tracked separately as bad debt.
        # Remaining debt = 102,000 - 95,000 = 7,000 (tracked as deficiency)
        assert sc.new_state['loan_amount'] == 0.0
        assert sc.new_state['accrued_interest'] == 0.0
        assert float(sc.new_state['liquidation_deficiency']) == pytest.approx(7000.0, abs=0.01)


# ============================================================================
# CONSERVATION LAW TESTS
# ============================================================================

class TestConservationLaws:
    """Tests verifying conservation laws for margin loans."""

    def test_repayment_conserves_cash(self):
        """Repayment is a pure transfer (conserves total cash)."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("1000.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': False,
            'total_interest_paid': 0.0,
            'total_principal_paid': 0.0,
        }

        view = FakeView(
            balances={'alice': {'USD': Decimal("200000")}, 'bank': {'USD': Decimal("0")}},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 6, 1),
        )

        result = compute_repayment(view, 'LOAN_001', 50000.0)

        # Net cash flow: -50000 from alice, +50000 to bank = 0
        total_out = sum(-m.quantity for m in result.moves if m.source == 'alice')
        total_in = sum(m.quantity for m in result.moves if m.dest == 'bank')

        assert total_out + total_in == 0

    def test_liquidation_full_recovery_conserves(self):
        """Full recovery liquidation conserves cash (surplus returned)."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("2000.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 5000.0,
            'margin_call_deadline': datetime(2024, 1, 15),
            'liquidated': False,
        }

        view = FakeView(
            balances={'alice': {'USD': Decimal("10000")}, 'bank': {'USD': Decimal("200000")}},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 16),
        )
        prices = {'AAPL': Decimal("100.0")}

        # Proceeds = 120,000, debt = 102,000, surplus = 18,000
        result = compute_margin_loan_liquidation(view, 'LOAN_001', prices, 120000.0)

        # Two moves: debt payment + surplus return
        assert len(result.moves) == 2

        # Net for alice: -102,000 debt + 18,000 surplus = -84,000 (paid to bank)
        # Net for bank: +102,000 debt - 18,000 surplus = +84,000 (received)
        alice_net = sum(
            m.quantity if m.dest == 'alice' else -m.quantity if m.source == 'alice' else 0
            for m in result.moves
        )
        bank_net = sum(
            m.quantity if m.dest == 'bank' else -m.quantity if m.source == 'bank' else 0
            for m in result.moves
        )

        # These should cancel out
        assert alice_net + bank_net == pytest.approx(0.0, abs=0.01)


# ============================================================================
# EDGE CASES TESTS
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_small_loan(self):
        """Very small loan amount works correctly."""
        loan = create_margin_loan(
            symbol="TINY",
            name="Tiny Loan",
            loan_amount=0.01,
            interest_rate=0.08,
            collateral={"AAPL": Decimal("1")},
            haircuts={"AAPL": Decimal("0.80")},
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )
        assert loan.state["loan_amount"] == 0.01

    def test_very_high_interest_rate(self):
        """High interest rate (payday loan style) works correctly."""
        loan = create_margin_loan(
            symbol="PAYDAY",
            name="High Interest Loan",
            loan_amount=1000.0,
            interest_rate=3.0,  # 300% APR
            collateral={"AAPL": Decimal("100")},
            haircuts={"AAPL": Decimal("0.80")},
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )
        assert loan.state["interest_rate"] == 3.0

    def test_many_collateral_assets(self):
        """Loan with many different collateral assets."""
        collateral = {f"ASSET_{i}": 100.0 for i in range(10)}
        haircuts = {f"ASSET_{i}": 0.70 for i in range(10)}

        loan = create_margin_loan(
            symbol="MULTI",
            name="Multi-Collateral Loan",
            loan_amount=100000.0,
            interest_rate=0.08,
            collateral=collateral,
            haircuts=haircuts,
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )

        assert len(loan.state["collateral"]) == 10

    def test_zero_collateral_value(self):
        """Handle zero collateral value gracefully."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("0")},  # Zero quantity
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': False,
        }

        view = FakeView(
            balances={},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 1),
        )
        prices = {'AAPL': Decimal("200.0")}

        status = compute_margin_status(view, 'LOAN_001', prices)

        assert status['collateral_value'] == 0.0
        assert float(status['margin_ratio']) == pytest.approx(0.0, abs=0.01)
        assert status['status'] == MARGIN_STATUS_BREACH

    def test_fractional_quantities(self):
        """Handle fractional collateral quantities."""
        loan_state = {
            'loan_amount': Decimal("1000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'BTC': Decimal("0.5")},  # Half a bitcoin
            'haircuts': {'BTC': Decimal("0.60")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': False,
        }

        view = FakeView(
            balances={},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 1),
        )
        prices = {'BTC': Decimal("50000.0")}

        value = compute_collateral_value(view, 'LOAN_001', prices)

        # 0.5 * 50,000 * 0.60 = 15,000
        assert value == pytest.approx(15000.0, abs=0.01)


# ============================================================================
# SMART CONTRACT TESTS
# ============================================================================

class TestPendingInterest:
    """Tests for pending interest inclusion in debt calculations (CRITICAL BUG FIX)."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'margin_call_deadline_days': 3,
            'liquidated': False,
            'origination_date': datetime(2024, 1, 1),
            'last_accrual_date': datetime(2024, 1, 1),
            'total_interest_paid': 0.0,
            'total_principal_paid': 0.0,
        }

    def test_liquidation_includes_pending_interest(self):
        """Liquidation includes pending interest accrued since last_accrual_date."""
        # Loan originated on Jan 1, last accrual on Jan 1
        # 5 days pass without accrual (Jan 1 -> Jan 6)
        # Expected pending interest = 100,000 * 0.08 / 365 * 5 = $109.59
        state = dict(self.loan_state)
        state['margin_call_deadline'] = datetime(2024, 1, 5)  # Deadline passed

        view = FakeView(
            balances={
                'alice': {'USD': Decimal("10000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': state},
            time=datetime(2024, 1, 6),  # 5 days after last accrual
        )
        prices = {'AAPL': Decimal("100.0")}

        # Expected pending interest
        expected_pending = 100000 * 0.08 / 365 * 5  # ~109.59
        expected_total_debt = 100000 + 0 + expected_pending  # ~100,109.59

        # Liquidate with proceeds covering full debt including pending
        sale_proceeds = 102000.0
        result = compute_margin_loan_liquidation(view, 'LOAN_001', prices, sale_proceeds)

        # Debt payment should include pending interest
        debt_move = result.moves[0]
        assert float(debt_move.quantity) == pytest.approx(expected_total_debt, abs=0.01)

        # Surplus should be proceeds minus total debt (including pending)
        surplus_move = result.moves[1]
        expected_surplus = sale_proceeds - expected_total_debt
        assert float(surplus_move.quantity) == pytest.approx(expected_surplus, abs=0.01)

    def test_cure_includes_pending_interest(self):
        """Cure amount validation includes pending interest in total debt."""
        # 5 days pass without accrual
        view = FakeView(
            balances={
                'alice': {'USD': Decimal("50000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 6),  # 5 days after last accrual
        )

        # Expected pending interest
        expected_pending = 100000 * 0.08 / 365 * 5  # ~109.59
        expected_total_debt = 100000 + 0 + expected_pending  # ~100,109.59

        # Cure with exact total debt (should succeed)
        result = compute_margin_cure(view, 'LOAN_001', expected_total_debt)

        # Should generate one move for the cure amount
        assert len(result.moves) == 1
        assert float(result.moves[0].quantity) == pytest.approx(expected_total_debt, abs=0.01)

        # Final state should have zero debt
        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert float(sc.new_state['loan_amount']) == pytest.approx(0.0, abs=0.01)
        assert float(sc.new_state['accrued_interest']) == pytest.approx(0.0, abs=0.01)

    def test_cure_exceeding_debt_with_pending_interest_raises(self):
        """Cure amount exceeding total debt (including pending) raises error."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 6),  # 5 days after last accrual
        )

        # Try to cure with more than total debt (including pending)
        expected_total_debt = 100000 + (100000 * 0.08 / 365 * 5)
        excessive_cure = expected_total_debt + 1000

        with pytest.raises(ValueError, match="exceeds total_debt"):
            compute_margin_cure(view, 'LOAN_001', excessive_cure)

    def test_repayment_includes_pending_interest(self):
        """Repayment includes pending interest in total debt calculation."""
        # 5 days pass without accrual
        view = FakeView(
            balances={
                'alice': {'USD': Decimal("150000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 6),  # 5 days after last accrual
        )

        # Expected pending interest
        expected_pending = 100000 * 0.08 / 365 * 5  # ~109.59
        expected_total_debt = 100000 + 0 + expected_pending  # ~100,109.59

        # Full repayment including pending interest
        result = compute_repayment(view, 'LOAN_001', expected_total_debt)

        # Should generate one move for the repayment
        assert len(result.moves) == 1
        assert float(result.moves[0].quantity) == pytest.approx(expected_total_debt, abs=0.01)

        # Final state should have zero debt
        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert float(sc.new_state['loan_amount']) == pytest.approx(0.0, abs=0.01)
        assert float(sc.new_state['accrued_interest']) == pytest.approx(0.0, abs=0.01)

        # Total interest paid should equal the pending interest (no accrued)
        assert float(sc.new_state['total_interest_paid']) == pytest.approx(expected_pending, abs=0.01)
        assert float(sc.new_state['total_principal_paid']) == pytest.approx(100000.0, abs=0.01)

    def test_repayment_exceeding_debt_with_pending_interest_raises(self):
        """Repayment exceeding total debt (including pending) raises error."""
        view = FakeView(
            balances={},
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 6),  # 5 days after last accrual
        )

        # Try to repay more than total debt (including pending)
        expected_total_debt = 100000 + (100000 * 0.08 / 365 * 5)
        excessive_repayment = expected_total_debt + 1000

        with pytest.raises(ValueError, match="exceeds total_debt"):
            compute_repayment(view, 'LOAN_001', excessive_repayment)

    def test_pending_interest_5_day_liquidation_scenario(self):
        """
        CRITICAL TEST: 5-day pending interest scenario.

        Scenario:
        - Loan originated with $100k @ 8% on Jan 1
        - Interest accrues for 5 days but compute_interest_accrual() is NOT called
        - On Jan 6, loan is liquidated
        - Verify lender receives full debt including 5 days of pending interest

        This test ensures lenders don't lose accrued-but-not-persisted interest.
        """
        # Setup loan with margin call deadline past due
        state = dict(self.loan_state)
        state['margin_call_deadline'] = datetime(2024, 1, 5)  # Deadline passed

        view = FakeView(
            balances={
                'alice': {'USD': Decimal("10000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': state},
            time=datetime(2024, 1, 6),  # 5 days after origination/last_accrual
        )
        prices = {'AAPL': Decimal("100.0")}

        # Calculate expected pending interest for 5 days
        expected_pending_interest = 100000 * 0.08 / 365 * 5  # ~109.59
        expected_total_debt = 100000 + 0 + expected_pending_interest  # ~100,109.59

        # Liquidate with sale proceeds that cover full debt
        sale_proceeds = 105000.0
        result = compute_margin_loan_liquidation(view, 'LOAN_001', prices, sale_proceeds)

        # Verify debt payment includes pending interest
        assert len(result.moves) == 2  # Debt payment + surplus

        debt_move = result.moves[0]
        assert debt_move.source == 'alice'
        assert debt_move.dest == 'bank'
        assert float(debt_move.quantity) == pytest.approx(expected_total_debt, abs=0.01)

        # Verify surplus is correct (proceeds - full debt including pending)
        surplus_move = result.moves[1]
        assert surplus_move.source == 'bank'
        assert surplus_move.dest == 'alice'
        expected_surplus = sale_proceeds - expected_total_debt  # ~4,890.41
        assert float(surplus_move.quantity) == pytest.approx(expected_surplus, abs=0.01)

        # Verify liquidation state
        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['liquidated'] is True
        assert sc.new_state['loan_amount'] == 0.0
        assert sc.new_state['accrued_interest'] == 0.0
        assert sc.new_state['collateral'] == {}
        assert sc.new_state['liquidation_proceeds'] == sale_proceeds
        assert sc.new_state['liquidation_deficiency'] == 0.0  # Full recovery

    def test_pending_interest_payment_waterfall(self):
        """Test that pending interest is paid before accrued interest and principal."""
        # Setup with both accrued and pending interest
        state = dict(self.loan_state)
        state['accrued_interest'] = 500.0  # $500 already accrued

        view = FakeView(
            balances={
                'alice': {'USD': Decimal("50000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': state},
            time=datetime(2024, 1, 6),  # 5 days after last accrual
        )

        # Expected pending interest for 5 days
        expected_pending = 100000 * 0.08 / 365 * 5  # ~109.59
        total_interest = 500.0 + expected_pending  # ~609.59

        # Repay enough to cover all interest plus some principal
        repayment = 1000.0
        result = compute_repayment(view, 'LOAN_001', repayment)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")

        # All interest should be paid first (accrued + pending)
        assert float(sc.new_state['accrued_interest']) == pytest.approx(0.0, abs=0.01)
        assert float(sc.new_state['total_interest_paid']) == pytest.approx(total_interest, abs=0.01)

        # Remaining goes to principal
        principal_payment = repayment - total_interest  # ~390.41
        assert float(sc.new_state['loan_amount']) == pytest.approx(100000 - principal_payment, abs=0.01)
        assert float(sc.new_state['total_principal_paid']) == pytest.approx(principal_payment, abs=0.01)

    def test_pending_interest_updates_last_accrual_date(self):
        """Verify that operations with pending interest update last_accrual_date."""
        view = FakeView(
            balances={
                'alice': {'USD': Decimal("50000")},
                'bank': {'USD': Decimal("100000")},
            },
            states={'LOAN_001': self.loan_state},
            time=datetime(2024, 1, 6),  # 5 days after last accrual
        )

        # Make a repayment that includes pending interest
        result = compute_repayment(view, 'LOAN_001', 1000.0)

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")

        # last_accrual_date should be updated to current time
        assert sc.new_state['last_accrual_date'] == datetime(2024, 1, 6)

    def test_add_collateral_includes_pending_interest_in_cure_check(self):
        """
        Adding collateral cure check should include pending interest.

        This test verifies that when checking if adding collateral cures a margin call,
        the total_debt calculation includes pending interest (interest accrued since
        last_accrual_date but not yet persisted). Without this, a margin call could
        be incorrectly cleared when pending interest would keep the ratio below
        maintenance margin.
        """
        # Setup: loan with margin call and pending interest
        state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'last_accrual_date': datetime(2024, 1, 1),
            'collateral': {'AAPL': Decimal("1000")},  # 1000 shares
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 5000.0,
            'margin_call_deadline': datetime(2024, 1, 20),
            'margin_call_deadline_days': 3,
            'liquidated': False,
        }

        # 30 days after last accrual = significant pending interest
        # Pending interest = 100000 * 0.08 / 365 * 30 = ~$657.53
        view = FakeView(
            balances={'alice': {'AAPL': Decimal("100")}},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 31),  # 30 days elapsed
        )

        # Calculate expected pending interest
        pending_interest = 100000 * 0.08 / 365 * 30  # ~657.53
        total_debt_with_pending = 100000 + pending_interest  # ~100,657.53

        # Price of AAPL such that:
        # - WITHOUT pending interest: ratio would be ABOVE maintenance (1.25)
        # - WITH pending interest: ratio would be BELOW maintenance (1.25)
        #
        # After adding 50 more shares: 1050 shares total
        # Collateral value = 1050 * price * 0.80
        #
        # We want: collateral_value / 100000 >= 1.25 (passes without pending)
        #          collateral_value / 100657.53 < 1.25 (fails with pending)
        #
        # So: 125000 <= collateral_value < 125821.91
        # With 1050 * 0.80 = 840 effective shares: 148.81 <= price < 149.79
        # Use price = 149.00
        prices = {'AAPL': Decimal("149.00")}
        haircuts = {'AAPL': Decimal("0.80")}

        # Verify our math:
        # After adding 50 shares: 1050 total
        # Collateral value = 1050 * 149 * 0.80 = 125,160
        # Without pending: ratio = 125160 / 100000 = 1.2516 >= 1.25 (would clear!)
        # With pending: ratio = 125160 / 100657.53 = 1.2434 < 1.25 (stays in margin call)

        # Add 50 shares of collateral (haircuts come from state)
        result = compute_add_collateral(
            view, 'LOAN_001', 'AAPL', 50.0, prices=prices
        )

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")

        # Margin call should NOT be cleared because pending interest
        # keeps the true ratio below maintenance margin
        assert sc.new_state['margin_call_deadline'] is not None, \
            "Margin call should NOT be cleared when pending interest keeps ratio below maintenance"
        assert sc.new_state['margin_call_amount'] == 5000.0, \
            "Margin call amount should remain unchanged"

        # Verify collateral was added
        assert sc.new_state['collateral']['AAPL'] == 1050

    def test_add_collateral_clears_margin_call_when_truly_above_maintenance(self):
        """
        Adding enough collateral should clear margin call when ratio is truly above
        maintenance (including pending interest in the calculation).
        """
        state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'last_accrual_date': datetime(2024, 1, 1),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 5000.0,
            'margin_call_deadline': datetime(2024, 1, 20),
            'margin_call_deadline_days': 3,
            'liquidated': False,
        }

        # 30 days pending interest = ~$657.53
        view = FakeView(
            balances={'alice': {'AAPL': Decimal("200")}},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 31),
        )

        # Use a higher price so that even with pending interest, ratio exceeds maintenance
        # Need: collateral_value / 100657.53 >= 1.25
        # So: collateral_value >= 125,821.91
        # With 1100 shares (after adding 100) and 0.80 haircut:
        # 1100 * price * 0.80 >= 125821.91
        # price >= 143.00
        prices = {'AAPL': Decimal("160.00")}  # Plenty above threshold
        haircuts = {'AAPL': Decimal("0.80")}

        # Verify: 1100 * 160 * 0.80 = 140,800
        # Ratio = 140800 / 100657.53 = 1.399 > 1.25 (clears margin call)

        result = compute_add_collateral(
            view, 'LOAN_001', 'AAPL', 100.0, prices=prices
        )

        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")

        # Margin call SHOULD be cleared
        assert sc.new_state['margin_call_deadline'] is None, \
            "Margin call should be cleared when ratio is truly above maintenance"
        assert sc.new_state['margin_call_amount'] == 0.0
        assert sc.new_state['collateral']['AAPL'] == 1100


class TestPendingInterestAfterPartialRepayment:
    """Tests for pending interest calculation after partial principal repayment.

    This test class verifies that _calculate_pending_interest correctly uses
    loan_amount (which already represents current outstanding principal) instead
    of incorrectly subtracting total_principal_paid again.
    """

    def test_pending_interest_after_partial_principal_payment(self):
        """
        After a partial principal payment, pending interest should be calculated
        on the CURRENT outstanding principal (loan_amount), not on the original
        amount minus total_principal_paid.

        This test catches a bug where loan_amount was being double-reduced:
        - loan_amount is already reduced when payments are made
        - Subtracting total_principal_paid again would under-calculate interest
        """
        # Scenario: Original loan was 100k, borrower repaid 50k principal
        # loan_amount should now be 50k (it gets reduced in compute_repayment)
        # total_principal_paid tracks the cumulative amount for record-keeping
        state = {
            'loan_amount': Decimal("50000.0"),  # Current outstanding (already reduced)
            'total_principal_paid': Decimal("50000.0"),  # For record-keeping
            'interest_rate': Decimal("0.10"),  # 10% annual
            'accrued_interest': Decimal("0.0"),
            'last_accrual_date': datetime(2024, 1, 1),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'margin_call_deadline_days': 3,
            'liquidated': False,
        }

        # 10 days after last accrual
        view = FakeView(
            balances={'alice': {'USD': Decimal("100000")}},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 11),  # 10 days later
        )

        # Calculate margin status (which uses pending interest internally)
        prices = {'AAPL': Decimal("100.0")}
        status = compute_margin_status(view, 'LOAN_001', prices)

        # Expected pending interest = 50000 * 0.10 / 365 * 10 = ~$136.99
        expected_pending = 50000 * 0.10 / 365 * 10

        assert float(status['pending_interest']) == pytest.approx(expected_pending, abs=0.01), \
            f"Pending interest should be {expected_pending}, got {status['pending_interest']}"

        # Total debt should be loan_amount + accrued + pending
        expected_debt = 50000.0 + 0.0 + expected_pending
        assert float(status['total_debt']) == pytest.approx(expected_debt, abs=0.01)

    def test_liquidation_after_partial_repayment_includes_correct_interest(self):
        """
        After a partial repayment, liquidation should calculate pending interest
        on the current outstanding principal, not the original.
        """
        # After partial repayment: loan_amount reduced to 50k
        state = {
            'loan_amount': Decimal("50000.0"),
            'total_principal_paid': Decimal("50000.0"),
            'interest_rate': Decimal("0.10"),
            'accrued_interest': Decimal("0.0"),
            'last_accrual_date': datetime(2024, 1, 1),
            'collateral': {'AAPL': Decimal("500")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 10000.0,
            'margin_call_deadline': datetime(2024, 1, 5),  # Deadline passed
            'margin_call_deadline_days': 3,
            'liquidated': False,
        }

        # 10 days after last accrual, deadline has passed
        view = FakeView(
            balances={'alice': {}, 'bank': {}},
            states={'LOAN_001': state},
            time=datetime(2024, 1, 11),
        )

        # Price crash triggers liquidation eligibility
        prices = {'AAPL': Decimal("50.0")}  # Collateral value = 500 * 50 * 0.80 = 20,000

        # Sale proceeds cover the debt
        # Expected debt = 50000 + 0 + (50000 * 0.10 / 365 * 10) = 50136.99
        expected_pending = 50000 * 0.10 / 365 * 10
        expected_debt = 50000 + expected_pending

        # Sell all collateral for exactly the debt amount
        result = compute_margin_loan_liquidation(view, 'LOAN_001', prices, sale_proceeds=expected_debt)

        # Should have move for debt payment (no surplus, no deficiency)
        assert len(result.moves) == 1
        assert float(result.moves[0].quantity) == pytest.approx(expected_debt, abs=0.01)


class TestMarginLoanContract:
    """Tests for margin_loan_contract SmartContract function."""

    def test_contract_issues_margin_call(self):
        """Smart contract issues margin call when below maintenance."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'margin_call_deadline_days': 3,
            'liquidated': False,
        }

        view = FakeView(
            balances={},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 15),
        )
        prices = {'AAPL': Decimal("150.0")}  # Below maintenance

        result = margin_loan_contract(view, 'LOAN_001', datetime(2024, 1, 15), prices)

        assert any(d.unit == 'LOAN_001' for d in result.state_changes)
        sc = next(d for d in result.state_changes if d.unit == "LOAN_001")
        assert sc.new_state['margin_call_amount'] > 0

    def test_contract_no_action_when_healthy(self):
        """Smart contract takes no action when loan is healthy."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': False,
        }

        view = FakeView(
            balances={},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 15),
        )
        prices = {'AAPL': Decimal("200.0")}  # Healthy

        result = margin_loan_contract(view, 'LOAN_001', datetime(2024, 1, 15), prices)

        assert result.is_empty()

    def test_contract_no_action_when_liquidated(self):
        """Smart contract takes no action on liquidated loan."""
        loan_state = {
            'loan_amount': Decimal("0.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("0.0"),
            'collateral': {},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'liquidated': True,
        }

        view = FakeView(
            balances={},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 15),
        )
        prices = {'AAPL': Decimal("100.0")}

        result = margin_loan_contract(view, 'LOAN_001', datetime(2024, 1, 15), prices)

        assert result.is_empty()


# ============================================================================
# PURE FUNCTION PATTERN TESTS
# ============================================================================

from ledger import (
    MarginLoanTerms,
    MarginLoanState,
    MarginStatusResult,
    load_margin_loan,
    calculate_collateral_value,
    calculate_pending_interest,
    calculate_margin_status,
    calculate_interest_accrual,
)


class TestPureFunctionPattern:
    """Tests demonstrating the pure function architecture.

    These tests show how the new pattern enables:
    1. Testing without LedgerView (no mocks needed)
    2. Stress testing by passing different parameters
    3. What-if analysis by modifying haircuts/prices
    4. Full isolation of calculation logic
    """

    def test_calculate_collateral_value_pure(self):
        """Pure function: calculate collateral value without LedgerView."""
        collateral = {'AAPL': Decimal("1000"), 'MSFT': Decimal("500")}
        prices = {'AAPL': Decimal("150.0"), 'MSFT': Decimal("300.0")}
        haircuts = {'AAPL': Decimal("0.70"), 'MSFT': Decimal("0.75")}

        # Direct call - no view, no state lookup
        value = calculate_collateral_value(collateral, prices, haircuts)

        # AAPL: 1000 * 150 * 0.70 = 105,000
        # MSFT: 500 * 300 * 0.75 = 112,500
        assert value == pytest.approx(217500.0, abs=0.01)

    def test_stress_test_haircuts(self):
        """Stress test: more conservative haircuts without mutating state."""
        collateral = {'AAPL': Decimal("1000"), 'MSFT': Decimal("500")}
        prices = {'AAPL': Decimal("150.0"), 'MSFT': Decimal("300.0")}
        base_haircuts = {'AAPL': Decimal("0.70"), 'MSFT': Decimal("0.75")}

        # Base case
        base_value = calculate_collateral_value(collateral, prices, base_haircuts)

        # Stressed case: 10% more conservative haircuts
        stressed_haircuts = {k: v * Decimal("0.9") for k, v in base_haircuts.items()}
        stressed_value = calculate_collateral_value(collateral, prices, stressed_haircuts)

        # Stressed value should be 10% lower
        assert float(stressed_value) == pytest.approx(float(base_value) * 0.9, abs=0.01)

    def test_stress_test_prices(self):
        """Stress test: price shock scenarios without mutating state."""
        collateral = {'AAPL': Decimal("1000")}
        haircuts = {'AAPL': Decimal("0.80")}

        base_prices = {'AAPL': Decimal("200.0")}
        base_value = calculate_collateral_value(collateral, base_prices, haircuts)
        assert float(base_value) == pytest.approx(160000.0, abs=0.01)

        # 20% price crash
        shocked_prices = {'AAPL': Decimal("160.0")}  # 20% drop
        shocked_value = calculate_collateral_value(collateral, shocked_prices, haircuts)
        assert float(shocked_value) == pytest.approx(128000.0, abs=0.01)

    def test_calculate_margin_status_pure(self):
        """Pure function: margin status without LedgerView."""
        terms = MarginLoanTerms(
            interest_rate=0.08,
            initial_margin=1.5,
            maintenance_margin=1.25,
            haircuts={'AAPL': Decimal("0.80")},
            margin_call_deadline_days=3,
            currency='USD',
            borrower_wallet='alice',
            lender_wallet='bank',
        )

        state = MarginLoanState(
            loan_amount=100000.0,
            collateral={'AAPL': Decimal("1000")},
            accrued_interest=0.0,
            last_accrual_date=None,
            margin_call_amount=0.0,
            margin_call_deadline=None,
            liquidated=False,
            origination_date=datetime(2024, 1, 1),
            total_interest_paid=0.0,
            total_principal_paid=0.0,
        )

        prices = {'AAPL': Decimal("200.0")}  # Value = 160,000, ratio = 1.6

        result = calculate_margin_status(terms, state, prices, datetime(2024, 1, 15))

        assert isinstance(result, MarginStatusResult)
        assert result.status == MARGIN_STATUS_HEALTHY
        assert float(result.collateral_value) == pytest.approx(160000.0, abs=0.01)
        assert float(result.margin_ratio) == pytest.approx(1.6, abs=0.01)

    def test_what_if_analysis(self):
        """What-if analysis: test different scenarios without any ledger."""
        terms = MarginLoanTerms(
            interest_rate=0.08,
            initial_margin=1.5,
            maintenance_margin=1.25,
            haircuts={'AAPL': Decimal("0.80")},
            margin_call_deadline_days=3,
            currency='USD',
            borrower_wallet='alice',
            lender_wallet='bank',
        )

        state = MarginLoanState(
            loan_amount=100000.0,
            collateral={'AAPL': Decimal("1000")},
            accrued_interest=0.0,
            last_accrual_date=None,
            margin_call_amount=0.0,
            margin_call_deadline=None,
            liquidated=False,
            origination_date=datetime(2024, 1, 1),
            total_interest_paid=0.0,
            total_principal_paid=0.0,
        )

        now = datetime(2024, 1, 15)

        # Scenario 1: Current price
        result_base = calculate_margin_status(terms, state, {'AAPL': Decimal("200.0")}, now)
        assert result_base.status == MARGIN_STATUS_HEALTHY

        # Scenario 2: 10% price drop
        result_drop10 = calculate_margin_status(terms, state, {'AAPL': Decimal("180.0")}, now)
        assert result_drop10.status == MARGIN_STATUS_WARNING  # ratio = 1.44

        # Scenario 3: 25% price drop
        result_drop25 = calculate_margin_status(terms, state, {'AAPL': Decimal("150.0")}, now)
        assert result_drop25.status == MARGIN_STATUS_BREACH  # ratio = 1.2

    def test_load_margin_loan_returns_frozen_dataclasses(self):
        """load_margin_loan returns frozen dataclasses that can't be mutated."""
        loan_state = {
            'loan_amount': Decimal("100000.0"),
            'interest_rate': Decimal("0.08"),
            'accrued_interest': Decimal("500.0"),
            'collateral': {'AAPL': Decimal("1000")},
            'haircuts': {'AAPL': Decimal("0.80")},
            'initial_margin': 1.5,
            'maintenance_margin': 1.25,
            'borrower_wallet': 'alice',
            'lender_wallet': 'bank',
            'currency': 'USD',
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'margin_call_deadline_days': 3,
            'liquidated': False,
            'total_interest_paid': 0.0,
            'total_principal_paid': 0.0,
        }

        view = FakeView(
            balances={},
            states={'LOAN_001': loan_state},
            time=datetime(2024, 1, 15),
        )

        terms, state = load_margin_loan(view, 'LOAN_001')

        # Both should be frozen
        assert isinstance(terms, MarginLoanTerms)
        assert isinstance(state, MarginLoanState)

        # Verify immutability - these should raise
        with pytest.raises(Exception):  # FrozenInstanceError
            terms.interest_rate = 0.10  # type: ignore

        with pytest.raises(Exception):  # FrozenInstanceError
            state.loan_amount = 50000.0  # type: ignore

    def test_calculate_pending_interest_pure(self):
        """Pure function: pending interest calculation."""
        loan_amount = 100000.0
        interest_rate = 0.08
        last_accrual = datetime(2024, 1, 1)
        current_time = datetime(2024, 1, 31)  # 30 days

        pending = calculate_pending_interest(
            loan_amount, interest_rate, last_accrual, current_time
        )

        # Expected: 100000 * 0.08 / 365 * 30 = 657.53
        assert float(pending) == pytest.approx(657.53, abs=0.01)

    def test_calculate_interest_accrual_pure(self):
        """Pure function: interest accrual calculation."""
        terms = MarginLoanTerms(
            interest_rate=0.08,
            initial_margin=1.5,
            maintenance_margin=1.25,
            haircuts={'AAPL': Decimal("0.80")},
            margin_call_deadline_days=3,
            currency='USD',
            borrower_wallet='alice',
            lender_wallet='bank',
        )

        state = MarginLoanState(
            loan_amount=100000.0,
            collateral={'AAPL': Decimal("1000")},
            accrued_interest=100.0,  # Already have some accrued
            last_accrual_date=datetime(2024, 1, 1),
            margin_call_amount=0.0,
            margin_call_deadline=None,
            liquidated=False,
            origination_date=datetime(2024, 1, 1),
            total_interest_paid=0.0,
            total_principal_paid=0.0,
        )

        new_interest, total_accrued = calculate_interest_accrual(terms, state, days=30)

        # Expected new: 100000 * 0.08 / 365 * 30 = 657.53
        assert float(new_interest) == pytest.approx(657.53, abs=0.01)
        # Total = existing 100 + new 657.53
        assert float(total_accrued) == pytest.approx(757.53, abs=0.01)

    def test_margin_status_result_is_typed(self):
        """MarginStatusResult provides typed access to all fields."""
        terms = MarginLoanTerms(
            interest_rate=0.08,
            initial_margin=1.5,
            maintenance_margin=1.25,
            haircuts={'AAPL': Decimal("0.80")},
            margin_call_deadline_days=3,
            currency='USD',
            borrower_wallet='alice',
            lender_wallet='bank',
        )

        state = MarginLoanState(
            loan_amount=100000.0,
            collateral={'AAPL': Decimal("1000")},
            accrued_interest=0.0,
            last_accrual_date=None,
            margin_call_amount=0.0,
            margin_call_deadline=None,
            liquidated=False,
            origination_date=datetime(2024, 1, 1),
            total_interest_paid=0.0,
            total_principal_paid=0.0,
        )

        result = calculate_margin_status(terms, state, {'AAPL': Decimal("200.0")}, datetime(2024, 1, 15))

        # All fields are typed - IDE autocomplete works
        assert isinstance(result.collateral_value, Decimal)
        assert isinstance(result.total_debt, Decimal)
        assert isinstance(result.margin_ratio, Decimal)
        assert isinstance(result.status, str)
        assert isinstance(result.shortfall, Decimal)
        assert isinstance(result.excess, Decimal)
        assert isinstance(result.pending_interest, Decimal)

    def test_parallel_scenario_analysis(self):
        """Multiple scenarios can run in parallel - dataclasses are thread-safe."""
        terms = MarginLoanTerms(
            interest_rate=0.08,
            initial_margin=1.5,
            maintenance_margin=1.25,
            haircuts={'AAPL': Decimal("0.80")},
            margin_call_deadline_days=3,
            currency='USD',
            borrower_wallet='alice',
            lender_wallet='bank',
        )

        state = MarginLoanState(
            loan_amount=100000.0,
            collateral={'AAPL': Decimal("1000")},
            accrued_interest=0.0,
            last_accrual_date=None,
            margin_call_amount=0.0,
            margin_call_deadline=None,
            liquidated=False,
            origination_date=datetime(2024, 1, 1),
            total_interest_paid=0.0,
            total_principal_paid=0.0,
        )

        now = datetime(2024, 1, 15)

        # Run many scenarios - all share the same frozen terms/state
        price_scenarios = [
            {'AAPL': Decimal("250.0")},  # Bull case
            {'AAPL': Decimal("200.0")},  # Base case
            {'AAPL': Decimal("180.0")},  # Mild drop
            {'AAPL': Decimal("150.0")},  # Significant drop
            {'AAPL': Decimal("100.0")},  # Crash
        ]

        results = [
            calculate_margin_status(terms, state, prices, now)
            for prices in price_scenarios
        ]

        # Verify each scenario produced correct result
        assert results[0].status == MARGIN_STATUS_HEALTHY  # ratio = 2.0
        assert results[1].status == MARGIN_STATUS_HEALTHY  # ratio = 1.6
        assert results[2].status == MARGIN_STATUS_WARNING  # ratio = 1.44
        assert results[3].status == MARGIN_STATUS_BREACH   # ratio = 1.2
        assert results[4].status == MARGIN_STATUS_BREACH   # ratio = 0.8
