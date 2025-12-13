"""
test_bonds_lifecycle.py - End-to-end lifecycle tests for bond units

Tests complete bond lifecycle scenarios:
- Bond issuance to maturity
- Multiple coupon payments
- Early redemption (call/put)
- Multi-holder scenarios
- LifecycleEngine integration
"""

import pytest
from datetime import datetime, timedelta
from ledger import (
    Ledger, Move,
    cash,
    create_bond_unit,
    compute_coupon_payment,
    compute_redemption,
    compute_accrued_interest,
    LifecycleEngine,
    bond_contract,
    generate_coupon_schedule,
)


class TestBondIssueToMaturity:
    """Tests for complete bond lifecycle from issue to maturity."""

    def test_corporate_bond_full_lifecycle(self):
        """Corporate bond: issue → 4 semi-annual coupons → redemption."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2026, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Generate schedule for 5% semi-annual bond
        schedule = generate_coupon_schedule(
            issue_date=issue_date,
            maturity_date=maturity_date,
            coupon_rate=0.05,
            face_value=1000.0,
            frequency=2,
        )

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond 5% 2026",
            face_value=1000.0,
            coupon_rate=0.05,
            coupon_frequency=2,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")

        # Initial positions: investor buys 10 bonds at par
        ledger.set_balance("investor", "CORP", 10)
        ledger.set_balance("investor", "USD", 0)
        ledger.set_balance("corporation", "USD", 1_000_000)

        investor_cash = []
        investor_cash.append(ledger.get_balance("investor", "USD"))

        # Process 4 semi-annual coupons
        coupon_dates = [
            datetime(2024, 7, 15),
            datetime(2025, 1, 15),
            datetime(2025, 7, 15),
            datetime(2026, 1, 15),
        ]

        for date in coupon_dates:
            ledger.advance_time(date)
            result = compute_coupon_payment(ledger, "CORP", date)
            ledger.execute(result)
            investor_cash.append(ledger.get_balance("investor", "USD"))

        # Each coupon: 10 bonds × $25 = $250
        # After 4 coupons: $1000
        assert ledger.get_balance("investor", "USD") == 1000.0

        # Redemption at maturity
        result = compute_redemption(ledger, "CORP", maturity_date)
        ledger.execute(result)

        # 10 bonds × $1000 = $10,000
        assert ledger.get_balance("investor", "USD") == 11000.0

        # Total return: $11,000 on $10,000 invested = 10% over 2 years = 5% p.a.
        state = ledger.get_unit_state("CORP")
        assert state["redeemed"] is True

    def test_treasury_bond_act_act_convention(self):
        """Treasury bond with ACT/ACT day count convention."""
        issue_date = datetime(2024, 5, 15)
        maturity_date = datetime(2025, 5, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        bond = create_bond_unit(
            symbol="US1Y",
            name="US Treasury 1-Year",
            face_value=1000.0,
            coupon_rate=0.04,
            coupon_frequency=2,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="us_treasury",
            holder_wallet="investor",
            issue_date=issue_date,
            day_count_convention="ACT/ACT",
        )
        ledger.register_unit(bond)

        ledger.register_wallet("us_treasury")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "US1Y", 5)
        ledger.set_balance("us_treasury", "USD", 10_000_000)

        # Verify day count convention is stored
        state = ledger.get_unit_state("US1Y")
        assert state["day_count_convention"] == "ACT/ACT"


class TestBondMultipleHolders:
    """Tests for bonds with multiple holders."""

    def test_coupon_distributed_proportionally(self):
        """Coupon payment distributed proportionally to all holders."""
        issue_date = datetime(2024, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        schedule = [(datetime(2024, 7, 15), 30.0)]  # $30 coupon

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            coupon_rate=0.06,  # 6% annual, semi-annual = 3% per period
            coupon_frequency=2,
            maturity_date=datetime(2024, 7, 15),
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("charlie")

        # Multiple holders
        ledger.set_balance("alice", "CORP", 10)
        ledger.set_balance("bob", "CORP", 20)
        ledger.set_balance("charlie", "CORP", 5)
        ledger.set_balance("corporation", "USD", 100_000)

        # Process coupon
        ledger.advance_time(datetime(2024, 7, 15))
        result = compute_coupon_payment(ledger, "CORP", datetime(2024, 7, 15))
        ledger.execute(result)

        # Verify proportional distribution
        # Total bonds: 35, total coupon: 35 × $30 = $1050
        assert ledger.get_balance("alice", "USD") == 10 * 30.0  # $300
        assert ledger.get_balance("bob", "USD") == 20 * 30.0    # $600
        assert ledger.get_balance("charlie", "USD") == 5 * 30.0 # $150

    def test_redemption_to_multiple_holders(self):
        """Redemption pays all holders their principal."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2025, 1, 15)

        ledger = Ledger("test", maturity_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            coupon_rate=0.05,
            coupon_frequency=2,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=issue_date,
            coupon_schedule=[],  # Skip coupons for this test
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.set_balance("alice", "CORP", 10)
        ledger.set_balance("bob", "CORP", 15)
        ledger.set_balance("corporation", "USD", 100_000)

        # Redemption
        result = compute_redemption(ledger, "CORP", maturity_date)
        ledger.execute(result)

        assert ledger.get_balance("alice", "USD") == 10_000.0
        assert ledger.get_balance("bob", "USD") == 15_000.0


class TestBondEarlyRedemption:
    """Tests for callable and putable bonds."""

    def test_callable_bond_early_call(self):
        """Callable bond redeemed early at call price."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2029, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        bond = create_bond_unit(
            symbol="CALLABLE",
            name="Callable Bond",
            face_value=1000.0,
            coupon_rate=0.06,
            coupon_frequency=2,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=issue_date,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "CALLABLE", 10)
        ledger.set_balance("corporation", "USD", 100_000)

        # Call at 102% after 2 years (use CALL event via transact to allow early redemption)
        call_date = datetime(2026, 1, 15)
        ledger.advance_time(call_date)

        # Use compute_redemption with allow_early=True for early call
        result = compute_redemption(ledger, "CALLABLE", call_date, redemption_price=1020.0, allow_early=True)
        ledger.execute(result)

        # 10 bonds × $1020 = $10,200
        assert ledger.get_balance("investor", "USD") == 10_200.0

        state = ledger.get_unit_state("CALLABLE")
        assert state["redeemed"] is True
        assert state["redemption_amount"] == 1020.0

    def test_putable_bond_early_put(self):
        """Putable bond put back to issuer at put price."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2029, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        bond = create_bond_unit(
            symbol="PUTABLE",
            name="Putable Bond",
            face_value=1000.0,
            coupon_rate=0.04,
            coupon_frequency=2,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=issue_date,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "PUTABLE", 10)
        ledger.set_balance("corporation", "USD", 100_000)

        # Put at par after 3 years (use allow_early=True for early put)
        put_date = datetime(2027, 1, 15)
        ledger.advance_time(put_date)

        result = compute_redemption(ledger, "PUTABLE", put_date, redemption_price=1000.0, allow_early=True)
        ledger.execute(result)

        assert ledger.get_balance("investor", "USD") == 10_000.0


class TestBondAccruedInterest:
    """Tests for accrued interest calculation in lifecycle."""

    def test_accrued_interest_mid_period(self):
        """Accrued interest calculated correctly mid-period."""
        issue_date = datetime(2024, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        schedule = [(datetime(2024, 7, 15), 25.0)]

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            coupon_rate=0.05,
            coupon_frequency=2,
            maturity_date=datetime(2024, 7, 15),
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        # Check accrued interest 3 months into 6-month period
        accrued = compute_accrued_interest(ledger, "CORP", datetime(2024, 4, 15))

        # Expected: 25 × (3 months / 6 months) ≈ 12.5
        assert accrued == pytest.approx(12.5, abs=1.0)


class TestBondLifecycleEngine:
    """Tests for bonds with LifecycleEngine."""

    def test_auto_coupon_payment_via_lifecycle_engine(self):
        """LifecycleEngine automatically processes coupon payments."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2025, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        schedule = generate_coupon_schedule(
            issue_date=issue_date,
            maturity_date=maturity_date,
            coupon_rate=0.06,
            face_value=1000.0,
            frequency=2,
        )

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            coupon_rate=0.06,
            coupon_frequency=2,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "CORP", 10)
        ledger.set_balance("corporation", "USD", 100_000)

        engine = LifecycleEngine(ledger)
        engine.register("BOND", bond_contract)

        # Step through each month
        for month in range(1, 13):
            date = datetime(2024, month, 15)
            ledger.advance_time(date)
            engine.step(date, {})

        # Should have received 2 coupons: July and January
        # But January 2025 is maturity, so check state
        state = ledger.get_unit_state("CORP")
        # At least one coupon should have been paid
        assert state["next_coupon_index"] >= 1

    def test_auto_redemption_via_lifecycle_engine(self):
        """LifecycleEngine automatically redeems at maturity."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2024, 7, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Simple bond with no intermediate coupons
        bond = create_bond_unit(
            symbol="ZERO",
            name="Zero Coupon Bond",
            face_value=1000.0,
            coupon_rate=0.0,  # Zero coupon
            coupon_frequency=2,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=issue_date,
            coupon_schedule=[],
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "ZERO", 5)
        ledger.set_balance("corporation", "USD", 100_000)

        engine = LifecycleEngine(ledger)
        engine.register("BOND", bond_contract)

        # Step past maturity
        ledger.advance_time(maturity_date)
        engine.step(maturity_date, {})

        # Should be redeemed
        state = ledger.get_unit_state("ZERO")
        assert state["redeemed"] is True

        # Investor received principal
        assert ledger.get_balance("investor", "USD") == 5000.0


class TestBondMultiCurrency:
    """Tests for bonds in different currencies."""

    def test_euro_bond_coupon_payment(self):
        """Euro-denominated bond pays coupons in EUR."""
        issue_date = datetime(2024, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("EUR", "Euro"))

        schedule = [(datetime(2024, 7, 15), 20.0)]  # €20 coupon

        bond = create_bond_unit(
            symbol="EURO_CORP",
            name="Euro Corporate Bond",
            face_value=1000.0,
            coupon_rate=0.04,
            coupon_frequency=2,
            maturity_date=datetime(2024, 7, 15),
            currency="EUR",
            issuer_wallet="eu_issuer",
            holder_wallet="eu_investor",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("eu_issuer")
        ledger.register_wallet("eu_investor")
        ledger.set_balance("eu_investor", "EURO_CORP", 10)
        ledger.set_balance("eu_issuer", "EUR", 100_000)

        # Coupon payment
        ledger.advance_time(datetime(2024, 7, 15))
        result = compute_coupon_payment(ledger, "EURO_CORP", datetime(2024, 7, 15))
        ledger.execute(result)

        # Verify EUR is used
        assert ledger.get_balance("eu_investor", "EUR") == 200.0  # 10 × €20

    def test_yen_bond_large_face_value(self):
        """Yen-denominated bond with large face value."""
        issue_date = datetime(2024, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("JPY", "Japanese Yen"))

        # Japanese corporate bonds often have ¥100M face value
        schedule = [(datetime(2024, 7, 15), 500_000.0)]  # ¥500,000 coupon

        bond = create_bond_unit(
            symbol="JGB",
            name="JGB 10-Year",
            face_value=100_000_000.0,  # ¥100 million
            coupon_rate=0.01,  # 1%
            coupon_frequency=2,
            maturity_date=datetime(2024, 7, 15),
            currency="JPY",
            issuer_wallet="mof",
            holder_wallet="jp_investor",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("mof")  # Ministry of Finance
        ledger.register_wallet("jp_investor")
        ledger.set_balance("jp_investor", "JGB", 1)
        ledger.set_balance("mof", "JPY", 1_000_000_000_000)

        # Coupon payment
        ledger.advance_time(datetime(2024, 7, 15))
        result = compute_coupon_payment(ledger, "JGB", datetime(2024, 7, 15))
        ledger.execute(result)

        # ¥500,000 coupon
        assert ledger.get_balance("jp_investor", "JPY") == 500_000.0


class TestBondConservation:
    """Tests verifying conservation laws for bonds."""

    def test_coupon_payment_conserves_total_cash(self):
        """Coupon payment conserves total cash in system."""
        issue_date = datetime(2024, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        schedule = [(datetime(2024, 7, 15), 25.0)]

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            coupon_rate=0.05,
            coupon_frequency=2,
            maturity_date=datetime(2024, 7, 15),
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "CORP", 10)
        ledger.set_balance("investor", "USD", 1000)
        ledger.set_balance("corporation", "USD", 100_000)

        initial_total = (
            ledger.get_balance("investor", "USD") +
            ledger.get_balance("corporation", "USD")
        )

        # Coupon payment
        ledger.advance_time(datetime(2024, 7, 15))
        result = compute_coupon_payment(ledger, "CORP", datetime(2024, 7, 15))
        ledger.execute(result)

        final_total = (
            ledger.get_balance("investor", "USD") +
            ledger.get_balance("corporation", "USD")
        )

        assert final_total == initial_total

    def test_redemption_conserves_total_cash(self):
        """Redemption conserves total cash in system."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2024, 7, 15)

        ledger = Ledger("test", maturity_date, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            coupon_rate=0.0,
            coupon_frequency=2,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            holder_wallet="investor",
            issue_date=issue_date,
            coupon_schedule=[],
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "CORP", 10)
        ledger.set_balance("investor", "USD", 0)
        ledger.set_balance("corporation", "USD", 100_000)

        initial_total = (
            ledger.get_balance("investor", "USD") +
            ledger.get_balance("corporation", "USD")
        )

        # Redemption
        result = compute_redemption(ledger, "CORP", maturity_date)
        ledger.execute(result)

        final_total = (
            ledger.get_balance("investor", "USD") +
            ledger.get_balance("corporation", "USD")
        )

        assert final_total == initial_total
