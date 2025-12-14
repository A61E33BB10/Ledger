"""
test_bonds_lifecycle.py - End-to-end lifecycle tests for bond units

Tests complete bond lifecycle scenarios:
- Bond issuance to maturity
- Multiple coupon payments
- Multi-holder scenarios
- LifecycleEngine integration

Coupons use DeferredCash pattern (like stock dividends).
"""

import pytest
from datetime import datetime
from decimal import Decimal
from ledger import (
    Ledger, Move,
    cash,
    Coupon,
    create_bond_unit,
    process_coupons,
    compute_redemption,
    compute_accrued_interest,
    LifecycleEngine,
    bond_contract,
    deferred_cash_contract,
)


def execute_coupon_with_settlement(ledger, bond_symbol, coupon_date):
    """Execute coupon payment and settle the DeferredCash immediately.

    Bond coupons use DeferredCash pattern (like stock dividends).
    This helper processes both the entitlement and settlement in one call.
    """
    # Step 1: Create coupon entitlements (DeferredCash units)
    result = process_coupons(ledger, bond_symbol, coupon_date)

    if not result.moves:
        return  # No coupon due

    # Execute to create DeferredCash units and entitlement moves
    ledger.execute(result)

    # Step 2: Settle each DeferredCash unit immediately
    for dc_unit in result.units_to_create:
        dc_symbol = dc_unit.symbol
        settlement = deferred_cash_contract(ledger, dc_symbol, coupon_date, {})
        if settlement.moves:
            ledger.execute(settlement)


class TestBondIssueToMaturity:
    """Tests for complete bond lifecycle from issue to maturity."""

    def test_corporate_bond_full_lifecycle(self):
        """Corporate bond: issue → 4 semi-annual coupons → redemption."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2026, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Explicit coupon schedule - 5% annual, semi-annual payments = $25 each
        schedule = [
            Coupon(datetime(2024, 7, 15), 25.0, "USD"),
            Coupon(datetime(2025, 1, 15), 25.0, "USD"),
            Coupon(datetime(2025, 7, 15), 25.0, "USD"),
            Coupon(datetime(2026, 1, 15), 25.0, "USD"),
        ]

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond 5% 2026",
            face_value=1000.0,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")

        # Initial positions: investor buys 10 bonds at par
        ledger.set_balance("investor", "CORP", Decimal("10"))
        ledger.set_balance("investor", "USD", Decimal("0"))
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
            execute_coupon_with_settlement(ledger, "CORP", date)
            investor_cash.append(ledger.get_balance("investor", "USD"))

        # Each coupon: 10 bonds × $25 = $250
        # After 4 coupons: $1000
        assert ledger.get_balance("investor", "USD") == Decimal("1000.0")

        # Redemption at maturity
        result = compute_redemption(ledger, "CORP", maturity_date)
        ledger.execute(result)

        # 10 bonds × $1000 = $10,000
        assert ledger.get_balance("investor", "USD") == Decimal("11000.0")

        # Total return: $11,000 on $10,000 invested = 10% over 2 years = 5% p.a.
        state = ledger.get_unit_state("CORP")
        assert state["redeemed"] is True

    def test_treasury_bond_act_365_convention(self):
        """Treasury bond with ACT/365 day count convention."""
        issue_date = datetime(2024, 5, 15)
        maturity_date = datetime(2025, 5, 15)

        ledger = Ledger("test", issue_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        bond = create_bond_unit(
            symbol="US1Y",
            name="US Treasury 1-Year",
            face_value=1000.0,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="us_treasury",
            issue_date=issue_date,
            coupon_schedule=[],  # Zero coupon for simplicity
            day_count_convention="ACT/365",
        )
        ledger.register_unit(bond)

        ledger.register_wallet("us_treasury")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "US1Y", Decimal("5"))
        ledger.set_balance("us_treasury", "USD", 10_000_000)

        # Verify day count convention is stored
        state = ledger.get_unit_state("US1Y")
        assert state["day_count_convention"] == "ACT/365"


class TestBondMultipleHolders:
    """Tests for bonds with multiple holders."""

    def test_coupon_distributed_proportionally(self):
        """Coupon payment distributed proportionally to all holders."""
        issue_date = datetime(2024, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        schedule = [Coupon(datetime(2024, 7, 15), 30.0, "USD")]  # $30 coupon

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            maturity_date=datetime(2024, 7, 15),
            currency="USD",
            issuer_wallet="corporation",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("charlie")

        # Multiple holders
        ledger.set_balance("alice", "CORP", Decimal("10"))
        ledger.set_balance("bob", "CORP", Decimal("20"))
        ledger.set_balance("charlie", "CORP", Decimal("5"))
        ledger.set_balance("corporation", "USD", 100_000)

        # Process coupon (with DeferredCash settlement)
        ledger.advance_time(datetime(2024, 7, 15))
        execute_coupon_with_settlement(ledger, "CORP", datetime(2024, 7, 15))

        # Verify proportional distribution
        # Total bonds: 35, total coupon: 35 × $30 = $1050
        assert ledger.get_balance("alice", "USD") == Decimal("10") * Decimal("30.0")  # $300
        assert ledger.get_balance("bob", "USD") == Decimal("20") * Decimal("30.0")    # $600
        assert ledger.get_balance("charlie", "USD") == Decimal("5") * Decimal("30.0") # $150

    def test_redemption_to_multiple_holders(self):
        """Redemption pays all holders their principal."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2025, 1, 15)

        ledger = Ledger("test", maturity_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            issue_date=issue_date,
            coupon_schedule=[],  # Skip coupons for this test
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.set_balance("alice", "CORP", Decimal("10"))
        ledger.set_balance("bob", "CORP", Decimal("15"))
        ledger.set_balance("corporation", "USD", 100_000)

        # Redemption
        result = compute_redemption(ledger, "CORP", maturity_date)
        ledger.execute(result)

        assert ledger.get_balance("alice", "USD") == Decimal("10000.0")
        assert ledger.get_balance("bob", "USD") == Decimal("15000.0")


class TestBondAccruedInterest:
    """Tests for accrued interest calculation in lifecycle."""

    def test_accrued_interest_mid_period(self):
        """Accrued interest calculated correctly mid-period."""
        issue_date = datetime(2024, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        schedule = [Coupon(datetime(2024, 7, 15), 25.0, "USD")]

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            maturity_date=datetime(2024, 7, 15),
            currency="USD",
            issuer_wallet="corporation",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        # Check accrued interest 3 months into 6-month period (pure function)
        from datetime import date
        accrued = compute_accrued_interest(
            coupon_amount=25.0,
            last_coupon_date=date(2024, 1, 15),
            next_coupon_date=date(2024, 7, 15),
            settlement_date=date(2024, 4, 15),
            day_count_convention="30/360",
        )

        # Expected: 25 × (3 months / 6 months) ≈ 12.5
        assert float(accrued) == pytest.approx(12.5, abs=1.0)


class TestBondLifecycleEngine:
    """Tests for bonds with LifecycleEngine."""

    def test_auto_coupon_payment_via_lifecycle_engine(self):
        """LifecycleEngine automatically processes coupon payments."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2025, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        schedule = [
            Coupon(datetime(2024, 7, 15), 30.0, "USD"),
            Coupon(datetime(2025, 1, 15), 30.0, "USD"),
        ]

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "CORP", Decimal("10"))
        ledger.set_balance("corporation", "USD", 100_000)

        engine = LifecycleEngine(ledger)
        engine.register("BOND", bond_contract)

        # Step through each month
        for month in range(1, 13):
            date = datetime(2024, month, 15)
            ledger.advance_time(date)
            engine.step(date, {})

        # Should have processed some coupons
        state = ledger.get_unit_state("CORP")
        # At least one coupon should have been processed
        assert len(state["processed_coupons"]) >= 1

    def test_auto_redemption_via_lifecycle_engine(self):
        """LifecycleEngine automatically redeems at maturity."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2024, 7, 15)

        ledger = Ledger("test", issue_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Simple zero coupon bond
        bond = create_bond_unit(
            symbol="ZERO",
            name="Zero Coupon Bond",
            face_value=1000.0,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            issue_date=issue_date,
            coupon_schedule=[],
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "ZERO", Decimal("5"))
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
        assert ledger.get_balance("investor", "USD") == Decimal("5000.0")


class TestBondMultiCurrency:
    """Tests for bonds in different currencies."""

    def test_euro_bond_coupon_payment(self):
        """Euro-denominated bond pays coupons in EUR."""
        issue_date = datetime(2024, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("EUR", "Euro"))

        schedule = [Coupon(datetime(2024, 7, 15), 20.0, "EUR")]  # €20 coupon

        bond = create_bond_unit(
            symbol="EURO_CORP",
            name="Euro Corporate Bond",
            face_value=1000.0,
            maturity_date=datetime(2024, 7, 15),
            currency="EUR",
            issuer_wallet="eu_issuer",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("eu_issuer")
        ledger.register_wallet("eu_investor")
        ledger.set_balance("eu_investor", "EURO_CORP", Decimal("10"))
        ledger.set_balance("eu_issuer", "EUR", 100_000)

        # Coupon payment (with DeferredCash settlement)
        ledger.advance_time(datetime(2024, 7, 15))
        execute_coupon_with_settlement(ledger, "EURO_CORP", datetime(2024, 7, 15))

        # Verify EUR is used
        assert ledger.get_balance("eu_investor", "EUR") == Decimal("200.0")  # 10 × €20

    def test_yen_bond_large_face_value(self):
        """Yen-denominated bond with large face value."""
        issue_date = datetime(2024, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("JPY", "Japanese Yen"))

        # Japanese corporate bonds often have ¥100M face value
        schedule = [Coupon(datetime(2024, 7, 15), 500_000.0, "JPY")]  # ¥500,000 coupon

        bond = create_bond_unit(
            symbol="JGB",
            name="JGB 10-Year",
            face_value=100_000_000.0,  # ¥100 million
            maturity_date=datetime(2024, 7, 15),
            currency="JPY",
            issuer_wallet="mof",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("mof")  # Ministry of Finance
        ledger.register_wallet("jp_investor")
        ledger.set_balance("jp_investor", "JGB", Decimal("1"))
        ledger.set_balance("mof", "JPY", 1_000_000_000_000)

        # Coupon payment (with DeferredCash settlement)
        ledger.advance_time(datetime(2024, 7, 15))
        execute_coupon_with_settlement(ledger, "JGB", datetime(2024, 7, 15))

        # ¥500,000 coupon
        assert ledger.get_balance("jp_investor", "JPY") == Decimal("500000.0")


class TestBondConservation:
    """Tests verifying conservation laws for bonds."""

    def test_coupon_payment_conserves_total_cash(self):
        """Coupon payment conserves total cash in system."""
        issue_date = datetime(2024, 1, 15)

        ledger = Ledger("test", issue_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        schedule = [Coupon(datetime(2024, 7, 15), 25.0, "USD")]

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            maturity_date=datetime(2024, 7, 15),
            currency="USD",
            issuer_wallet="corporation",
            issue_date=issue_date,
            coupon_schedule=schedule,
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "CORP", Decimal("10"))
        ledger.set_balance("investor", "USD", Decimal("1000"))
        ledger.set_balance("corporation", "USD", 100_000)

        initial_total = (
            ledger.get_balance("investor", "USD") +
            ledger.get_balance("corporation", "USD")
        )

        # Coupon payment (with DeferredCash settlement)
        ledger.advance_time(datetime(2024, 7, 15))
        execute_coupon_with_settlement(ledger, "CORP", datetime(2024, 7, 15))

        final_total = (
            ledger.get_balance("investor", "USD") +
            ledger.get_balance("corporation", "USD")
        )

        assert final_total == initial_total

    def test_redemption_conserves_total_cash(self):
        """Redemption conserves total cash in system."""
        issue_date = datetime(2024, 1, 15)
        maturity_date = datetime(2024, 7, 15)

        ledger = Ledger("test", maturity_date, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        bond = create_bond_unit(
            symbol="CORP",
            name="Corporate Bond",
            face_value=1000.0,
            maturity_date=maturity_date,
            currency="USD",
            issuer_wallet="corporation",
            issue_date=issue_date,
            coupon_schedule=[],
        )
        ledger.register_unit(bond)

        ledger.register_wallet("corporation")
        ledger.register_wallet("investor")
        ledger.set_balance("investor", "CORP", Decimal("10"))
        ledger.set_balance("investor", "USD", Decimal("0"))
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
