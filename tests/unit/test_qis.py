"""
test_qis.py - Comprehensive Tests for QIS (Quantitative Investment Strategy)

Tests cover:
1. Pure functions: compute_nav, accrue_financing, compute_rebalance, compute_payoff
2. Unit creation: create_qis validation
3. Built-in strategies: leveraged_strategy, fixed_weight_strategy
4. Lifecycle: rebalancing, settlement
5. Smart contract integration
6. Conservation laws
7. 2x Leveraged ETF demo scenario
"""

import pytest
import math
from datetime import datetime, timedelta

from ledger import (
    Ledger, cash, SYSTEM_WALLET, Move, build_transaction,
    UNIT_TYPE_QIS,
)
from ledger.units.qis import (
    compute_nav,
    accrue_financing,
    compute_rebalance,
    compute_payoff,
    create_qis,
    compute_qis_rebalance,
    compute_qis_settlement,
    qis_contract,
    leveraged_strategy,
    fixed_weight_strategy,
    get_qis_nav,
    get_qis_return,
    get_qis_leverage,
    DAYS_PER_YEAR,
)
from ledger.enhanced_lifecycle import LifecycleEngine


# ============================================================================
# PURE FUNCTION TESTS
# ============================================================================

class TestComputeNav:
    """Tests for compute_nav pure function."""

    def test_cash_only(self):
        """NAV of cash-only portfolio equals cash."""
        nav = compute_nav({}, 1000.0, {})
        assert nav == 1000.0

    def test_single_holding(self):
        """NAV = quantity * price + cash."""
        holdings = {"SPX": 10.0}
        prices = {"SPX": 100.0}
        nav = compute_nav(holdings, 0.0, prices)
        assert nav == 1000.0

    def test_multiple_holdings(self):
        """NAV = sum of all holdings + cash."""
        holdings = {"SPX": 10.0, "TLT": 20.0}
        prices = {"SPX": 100.0, "TLT": 50.0}
        # 10*100 + 20*50 = 1000 + 1000 = 2000
        nav = compute_nav(holdings, 500.0, prices)
        assert nav == 2500.0

    def test_negative_cash_leverage(self):
        """Leveraged portfolio: holdings > NAV, cash < 0."""
        # 2x leverage: $200 in stock, -$100 cash, NAV = $100
        holdings = {"SPX": 2.0}
        prices = {"SPX": 100.0}
        nav = compute_nav(holdings, -100.0, prices)
        assert nav == 100.0

    def test_missing_price_treated_as_zero(self):
        """Missing prices are treated as 0."""
        holdings = {"SPX": 10.0, "UNKNOWN": 5.0}
        prices = {"SPX": 100.0}  # UNKNOWN not in prices
        nav = compute_nav(holdings, 0.0, prices)
        assert nav == 1000.0  # UNKNOWN contributes 0


class TestAccrueFinancing:
    """Tests for accrue_financing pure function."""

    def test_zero_days_no_change(self):
        """Zero days means no financing accrual."""
        result = accrue_financing(1000.0, 0.05, 0)
        assert result == 1000.0

    def test_positive_cash_earns_interest(self):
        """Positive cash earns interest."""
        # $1000 at 5% for 365 days = $1000 * e^0.05 ≈ $1051.27
        result = accrue_financing(1000.0, 0.05, 365)
        expected = 1000.0 * math.exp(0.05)
        assert abs(result - expected) < 0.01

    def test_negative_cash_accrues_cost(self):
        """Negative cash (borrowing) becomes more negative."""
        # -$1000 at 5% for 365 days = -$1000 * e^0.05 ≈ -$1051.27
        result = accrue_financing(-1000.0, 0.05, 365)
        expected = -1000.0 * math.exp(0.05)
        assert abs(result - expected) < 0.01
        assert result < -1000.0  # More negative

    def test_zero_rate_no_change(self):
        """Zero rate means no financing."""
        result = accrue_financing(1000.0, 0.0, 365)
        assert result == 1000.0

    def test_daily_financing(self):
        """Single day financing."""
        result = accrue_financing(1000.0, 0.05, 1)
        expected = 1000.0 * math.exp(0.05 / 365)
        assert abs(result - expected) < 0.0001


class TestComputeRebalance:
    """Tests for compute_rebalance pure function."""

    def test_buy_decreases_cash(self):
        """Buying shares decreases cash."""
        current = {}
        target = {"SPX": 10.0}
        prices = {"SPX": 100.0}

        new_holdings, new_cash = compute_rebalance(current, 1000.0, target, prices)

        assert new_holdings == {"SPX": 10.0}
        assert new_cash == 0.0  # 1000 - 10*100 = 0

    def test_sell_increases_cash(self):
        """Selling shares increases cash."""
        current = {"SPX": 10.0}
        target = {}
        prices = {"SPX": 100.0}

        new_holdings, new_cash = compute_rebalance(current, 0.0, target, prices)

        assert new_holdings == {}
        assert new_cash == 1000.0  # 0 + 10*100 = 1000

    def test_self_financing_preserved(self):
        """NAV before = NAV after (self-financing constraint)."""
        current = {"SPX": 10.0, "TLT": 20.0}
        target = {"SPX": 15.0, "TLT": 10.0}
        prices = {"SPX": 100.0, "TLT": 50.0}
        initial_cash = 500.0

        # NAV before: 10*100 + 20*50 + 500 = 2500
        nav_before = compute_nav(current, initial_cash, prices)

        new_holdings, new_cash = compute_rebalance(current, initial_cash, target, prices)

        # NAV after should be same
        nav_after = compute_nav(new_holdings, new_cash, prices)
        assert abs(nav_after - nav_before) < 0.01

    def test_leverage_via_negative_cash(self):
        """Leverage creates negative cash balance."""
        # Start with $100 cash, want $200 in stock (2x leverage)
        current = {}
        target = {"SPX": 2.0}
        prices = {"SPX": 100.0}

        new_holdings, new_cash = compute_rebalance(current, 100.0, target, prices)

        assert new_holdings == {"SPX": 2.0}
        assert new_cash == -100.0  # 100 - 2*100 = -100 (borrowed)

    def test_zero_holdings_cleaned_up(self):
        """Near-zero holdings are removed."""
        current = {"SPX": 10.0}
        target = {"SPX": 0.0}
        prices = {"SPX": 100.0}

        new_holdings, new_cash = compute_rebalance(current, 0.0, target, prices)

        assert "SPX" not in new_holdings


class TestComputePayoff:
    """Tests for compute_payoff pure function."""

    def test_positive_return(self):
        """Positive return = positive payoff."""
        # V_T = 120, V_0 = 100, N = 1000
        # Payoff = 1000 * (120/100 - 1) = 1000 * 0.2 = 200
        payoff = compute_payoff(120.0, 100.0, 1000.0)
        assert abs(payoff - 200.0) < 0.01

    def test_negative_return(self):
        """Negative return = negative payoff."""
        # V_T = 80, V_0 = 100, N = 1000
        # Payoff = 1000 * (80/100 - 1) = 1000 * -0.2 = -200
        payoff = compute_payoff(80.0, 100.0, 1000.0)
        assert abs(payoff - (-200.0)) < 0.01

    def test_zero_return(self):
        """Zero return = zero payoff."""
        payoff = compute_payoff(100.0, 100.0, 1000.0)
        assert abs(payoff) < 0.01

    def test_invalid_initial_nav(self):
        """Initial NAV must be positive."""
        with pytest.raises(ValueError, match="initial_nav must be positive"):
            compute_payoff(100.0, 0.0, 1000.0)


# ============================================================================
# UNIT CREATION TESTS
# ============================================================================

class TestCreateQIS:
    """Tests for create_qis unit factory."""

    def test_basic_creation(self):
        """Create a basic QIS unit."""
        qis = create_qis(
            symbol="QIS_TEST",
            name="Test QIS",
            notional=1_000_000,
            initial_nav=100.0,
            funding_rate=0.05,
            payer_wallet="dealer",
            receiver_wallet="investor",
            currency="USD",
            eligible_assets=["SPX"],
            rebalance_dates=[datetime(2025, 1, 1), datetime(2025, 2, 1)],
            maturity_date=datetime(2025, 12, 31),
        )

        assert qis.symbol == "QIS_TEST"
        assert qis.unit_type == UNIT_TYPE_QIS
        assert qis._state['notional'] == 1_000_000
        assert qis._state['initial_nav'] == 100.0
        assert qis._state['cash'] == 100.0  # Starts in cash
        assert qis._state['holdings'] == {}
        assert qis._state['terminated'] == False

    def test_validation_notional_positive(self):
        """Notional must be positive."""
        with pytest.raises(ValueError, match="notional must be positive"):
            create_qis(
                symbol="QIS_TEST", name="Test", notional=0,
                initial_nav=100, funding_rate=0.05,
                payer_wallet="a", receiver_wallet="b", currency="USD",
                eligible_assets=["SPX"],
                rebalance_dates=[datetime(2025, 1, 1)],
                maturity_date=datetime(2025, 12, 31),
            )

    def test_validation_wallets_different(self):
        """Payer and receiver wallets must be different."""
        with pytest.raises(ValueError, match="must be different"):
            create_qis(
                symbol="QIS_TEST", name="Test", notional=1000,
                initial_nav=100, funding_rate=0.05,
                payer_wallet="same", receiver_wallet="same", currency="USD",
                eligible_assets=["SPX"],
                rebalance_dates=[datetime(2025, 1, 1)],
                maturity_date=datetime(2025, 12, 31),
            )


# ============================================================================
# STRATEGY TESTS
# ============================================================================

class TestLeveragedStrategy:
    """Tests for leveraged_strategy factory."""

    def test_2x_leverage(self):
        """2x leverage targets 200% exposure."""
        strategy = leveraged_strategy("SPX", 2.0)
        nav = 100.0
        prices = {"SPX": 50.0}

        target = strategy(nav, prices, {})

        # Target value = 2 * 100 = 200
        # Target qty = 200 / 50 = 4
        assert abs(target["SPX"] - 4.0) < 0.01

    def test_1x_no_leverage(self):
        """1x leverage = fully invested, no borrowing."""
        strategy = leveraged_strategy("SPX", 1.0)
        nav = 100.0
        prices = {"SPX": 50.0}

        target = strategy(nav, prices, {})

        # Target value = 1 * 100 = 100
        # Target qty = 100 / 50 = 2
        assert abs(target["SPX"] - 2.0) < 0.01

    def test_missing_price_returns_empty(self):
        """Missing price returns empty holdings."""
        strategy = leveraged_strategy("SPX", 2.0)
        target = strategy(100.0, {}, {})  # No prices

        assert target == {}


class TestFixedWeightStrategy:
    """Tests for fixed_weight_strategy factory."""

    def test_60_40_allocation(self):
        """60/40 allocation between two assets."""
        strategy = fixed_weight_strategy({"SPX": 0.6, "TLT": 0.4})
        nav = 1000.0
        prices = {"SPX": 100.0, "TLT": 50.0}

        target = strategy(nav, prices, {})

        # SPX: 0.6 * 1000 / 100 = 6 shares
        # TLT: 0.4 * 1000 / 50 = 8 shares
        assert abs(target["SPX"] - 6.0) < 0.01
        assert abs(target["TLT"] - 8.0) < 0.01


# ============================================================================
# LIFECYCLE TESTS
# ============================================================================

class TestQISLifecycle:
    """Tests for QIS lifecycle operations."""

    @pytest.fixture
    def ledger(self):
        """Create a ledger with QIS setup."""
        ledger = Ledger("qis_test", initial_time=datetime(2025, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("dealer")
        ledger.register_wallet("investor")
        # SYSTEM_WALLET is auto-registered

        # Fund wallets
        fund = build_transaction(ledger, [
            Move(10_000_000.0, "USD", SYSTEM_WALLET, "dealer", "fund_dealer"),
            Move(1_000_000.0, "USD", SYSTEM_WALLET, "investor", "fund_investor"),
        ])
        ledger.execute(fund)

        return ledger

    def test_rebalance_updates_holdings(self, ledger):
        """Rebalancing updates portfolio holdings."""
        qis = create_qis(
            symbol="QIS_TEST",
            name="Test QIS",
            notional=1_000_000,
            initial_nav=100.0,
            funding_rate=0.0,  # Zero for exact calculations
            payer_wallet="dealer",
            receiver_wallet="investor",
            currency="USD",
            eligible_assets=["SPX"],
            rebalance_dates=[datetime(2025, 1, 15)],
            maturity_date=datetime(2025, 12, 31),
            inception_date=datetime(2025, 1, 1),
        )
        ledger.register_unit(qis)

        # Advance time
        ledger.advance_time(datetime(2025, 1, 15))

        # Define strategy
        strategy = leveraged_strategy("SPX", 2.0)
        prices = {"SPX": 50.0}

        # Rebalance
        tx = compute_qis_rebalance(ledger, "QIS_TEST", strategy, prices)
        ledger.execute(tx)

        # Check state
        state = ledger.get_unit_state("QIS_TEST")
        assert "SPX" in state['holdings']
        assert state['holdings']["SPX"] == 4.0  # 2*100/50 = 4
        assert state['cash'] == -100.0  # 100 - 4*50 = -100

    def test_settlement_positive_return(self, ledger):
        """Settlement with positive return: dealer pays investor."""
        qis = create_qis(
            symbol="QIS_TEST",
            name="Test QIS",
            notional=1_000_000,
            initial_nav=100.0,
            funding_rate=0.0,  # No financing for simplicity
            payer_wallet="dealer",
            receiver_wallet="investor",
            currency="USD",
            eligible_assets=["SPX"],
            rebalance_dates=[datetime(2025, 1, 15)],
            maturity_date=datetime(2025, 12, 31),
            inception_date=datetime(2025, 1, 1),
        )
        ledger.register_unit(qis)

        # Set initial holdings manually for test
        state = ledger.get_unit_state("QIS_TEST")
        state['holdings'] = {"SPX": 1.0}
        state['cash'] = 0.0
        ledger.units["QIS_TEST"]._state = state

        ledger.advance_time(datetime(2025, 12, 31))

        # Price went up: initial = 100 (1 share * 100), final = 120
        initial_balance_dealer = ledger.get_balance("dealer", "USD")
        initial_balance_investor = ledger.get_balance("investor", "USD")

        prices = {"SPX": 120.0}
        tx = compute_qis_settlement(ledger, "QIS_TEST", prices)
        ledger.execute(tx)

        # Return = (120 - 100) / 100 = 20%
        # Payoff = 1_000_000 * 0.20 = 200_000
        final_state = ledger.get_unit_state("QIS_TEST")
        assert final_state['terminated'] == True
        assert abs(final_state['final_return'] - 0.2) < 0.01

        # Dealer paid investor
        assert ledger.get_balance("dealer", "USD") < initial_balance_dealer
        assert ledger.get_balance("investor", "USD") > initial_balance_investor


# ============================================================================
# SMART CONTRACT TESTS
# ============================================================================

class TestQISContract:
    """Tests for QIS smart contract integration."""

    @pytest.fixture
    def ledger(self):
        """Create a ledger with QIS setup."""
        ledger = Ledger("qis_test", initial_time=datetime(2025, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("dealer")
        ledger.register_wallet("investor")
        # SYSTEM_WALLET is auto-registered

        fund = build_transaction(ledger, [
            Move(10_000_000.0, "USD", SYSTEM_WALLET, "dealer", "fund_dealer"),
            Move(1_000_000.0, "USD", SYSTEM_WALLET, "investor", "fund_investor"),
        ])
        ledger.execute(fund)

        return ledger

    def test_contract_triggers_rebalance(self, ledger):
        """Contract triggers rebalance on schedule."""
        qis = create_qis(
            symbol="QIS_TEST",
            name="Test QIS",
            notional=1_000_000,
            initial_nav=100.0,
            funding_rate=0.05,
            payer_wallet="dealer",
            receiver_wallet="investor",
            currency="USD",
            eligible_assets=["SPX"],
            rebalance_dates=[datetime(2025, 1, 15)],
            maturity_date=datetime(2025, 12, 31),
            inception_date=datetime(2025, 1, 1),
        )
        ledger.register_unit(qis)

        strategy = leveraged_strategy("SPX", 2.0)
        contract = qis_contract(strategy)

        # Before rebalance date - no action
        tx = contract(ledger, "QIS_TEST", datetime(2025, 1, 10), {"SPX": 50.0})
        assert tx.is_empty()

        # On rebalance date - triggers
        ledger.advance_time(datetime(2025, 1, 15))
        tx = contract(ledger, "QIS_TEST", datetime(2025, 1, 15), {"SPX": 50.0})
        assert not tx.is_empty()

    def test_contract_triggers_settlement_at_maturity(self, ledger):
        """Contract triggers settlement at maturity."""
        qis = create_qis(
            symbol="QIS_TEST",
            name="Test QIS",
            notional=1_000_000,
            initial_nav=100.0,
            funding_rate=0.0,
            payer_wallet="dealer",
            receiver_wallet="investor",
            currency="USD",
            eligible_assets=["SPX"],
            rebalance_dates=[datetime(2025, 1, 15)],
            maturity_date=datetime(2025, 3, 1),
            inception_date=datetime(2025, 1, 1),
        )
        ledger.register_unit(qis)

        strategy = leveraged_strategy("SPX", 1.0)
        contract = qis_contract(strategy)

        # Set up holdings
        state = ledger.get_unit_state("QIS_TEST")
        state['holdings'] = {"SPX": 1.0}
        state['cash'] = 0.0
        state['next_rebalance_idx'] = 1  # Skip rebalance
        ledger.units["QIS_TEST"]._state = state

        ledger.advance_time(datetime(2025, 3, 1))

        # At maturity - triggers settlement
        tx = contract(ledger, "QIS_TEST", datetime(2025, 3, 1), {"SPX": 110.0})
        assert not tx.is_empty()
        assert len(tx.moves) == 1  # Settlement payment


# ============================================================================
# 2X LEVERAGED ETF DEMO
# ============================================================================

class TestLeveraged2xETFDemo:
    """
    Demo: 2x Leveraged SPX ETF with daily rebalancing.

    This demonstrates the full QIS lifecycle including:
    - Daily rebalancing to maintain 2x leverage
    - Financing costs on borrowed funds
    - Settlement at maturity
    """

    def test_2x_leveraged_etf_lifecycle(self):
        """
        Simulate a 2x leveraged SPX ETF over 3 days.

        Setup:
        - Initial NAV: $100
        - Target: 2x exposure to SPX
        - Funding rate: 5% annually
        - Daily rebalancing
        """
        # Setup
        inception = datetime(2025, 1, 1)
        ledger = Ledger("2x_etf", initial_time=inception)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("dealer")
        ledger.register_wallet("investor")
        # SYSTEM_WALLET is auto-registered

        # Fund wallets
        fund = build_transaction(ledger, [
            Move(1_000_000.0, "USD", SYSTEM_WALLET, "dealer", "fund"),
            Move(100_000.0, "USD", SYSTEM_WALLET, "investor", "fund"),
        ])
        ledger.execute(fund)

        # Create QIS
        rebalance_dates = [
            datetime(2025, 1, 1),
            datetime(2025, 1, 2),
            datetime(2025, 1, 3),
        ]
        maturity = datetime(2025, 1, 4)

        qis = create_qis(
            symbol="QIS_2X_SPX",
            name="2x Leveraged SPX",
            notional=10_000,  # $10K notional
            initial_nav=100.0,
            funding_rate=0.05,  # 5% annual
            payer_wallet="dealer",
            receiver_wallet="investor",
            currency="USD",
            eligible_assets=["SPX"],
            rebalance_dates=rebalance_dates,
            maturity_date=maturity,
            inception_date=inception,
        )
        ledger.register_unit(qis)

        strategy = leveraged_strategy("SPX", 2.0)
        contract = qis_contract(strategy)

        # Price path: 100 -> 102 -> 99 -> 101
        price_path = [
            (datetime(2025, 1, 1), 100.0),
            (datetime(2025, 1, 2), 102.0),  # +2%
            (datetime(2025, 1, 3), 99.0),   # -2.94%
            (datetime(2025, 1, 4), 101.0),  # +2.02%
        ]

        # Run lifecycle
        for ts, price in price_path:
            ledger.advance_time(ts)
            tx = contract(ledger, "QIS_2X_SPX", ts, {"SPX": price})
            if not tx.is_empty():
                ledger.execute(tx)

        # Verify terminated
        final_state = ledger.get_unit_state("QIS_2X_SPX")
        assert final_state['terminated'] == True

        # The final return should be approximately 2x the SPX return
        # SPX: 100 -> 101 = 1% return
        # Expected 2x ETF: ~2% return (minus financing drag)
        spx_return = (101 - 100) / 100  # 1%

        # Due to daily rebalancing and path dependency, 2x ETF doesn't exactly
        # give 2x return, but it should be close
        final_return = final_state['final_return']
        assert final_return is not None
        # Allow for some deviation due to financing and path dependency
        assert -0.10 < final_return < 0.10  # Sanity check

        print(f"\n=== 2x Leveraged ETF Results ===")
        print(f"SPX return: {spx_return*100:.2f}%")
        print(f"2x ETF return: {final_return*100:.2f}%")
        print(f"Final NAV: {final_state['final_nav']:.2f}")


# ============================================================================
# CONSERVATION LAW TESTS
# ============================================================================

class TestConservationLaws:
    """Tests verifying conservation laws."""

    def test_self_financing_throughout_lifecycle(self):
        """Self-financing constraint holds for all rebalances."""
        ledger = Ledger("conservation", initial_time=datetime(2025, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("dealer")
        ledger.register_wallet("investor")
        # SYSTEM_WALLET is auto-registered

        fund = build_transaction(ledger, [
            Move(1_000_000.0, "USD", SYSTEM_WALLET, "dealer", "fund"),
        ])
        ledger.execute(fund)

        qis = create_qis(
            symbol="QIS_CONS",
            name="Conservation Test",
            notional=10_000,
            initial_nav=100.0,
            funding_rate=0.0,  # No financing for clean test
            payer_wallet="dealer",
            receiver_wallet="investor",
            currency="USD",
            eligible_assets=["SPX", "TLT"],
            rebalance_dates=[
                datetime(2025, 1, 1),
                datetime(2025, 1, 2),
                datetime(2025, 1, 3),
            ],
            maturity_date=datetime(2025, 1, 4),
        )
        ledger.register_unit(qis)

        # Varying allocation strategy
        def varying_strategy(nav, prices, state):
            count = state.get('rebalance_count', 0)
            if count == 0:
                return {"SPX": nav / prices["SPX"]}  # 100% SPX
            elif count == 1:
                return {
                    "SPX": 0.5 * nav / prices["SPX"],
                    "TLT": 0.5 * nav / prices["TLT"],
                }  # 50/50
            else:
                return {"TLT": nav / prices["TLT"]}  # 100% TLT

        prices = {"SPX": 100.0, "TLT": 50.0}

        for i, date in enumerate([datetime(2025, 1, 1), datetime(2025, 1, 2), datetime(2025, 1, 3)]):
            ledger.advance_time(date)
            nav_before = get_qis_nav(ledger, "QIS_CONS", prices)

            tx = compute_qis_rebalance(ledger, "QIS_CONS", varying_strategy, prices)
            ledger.execute(tx)

            nav_after = get_qis_nav(ledger, "QIS_CONS", prices)

            # NAV should be unchanged by rebalancing (self-financing)
            assert abs(nav_after - nav_before) < 0.01, f"Self-financing violated at rebalance {i}"

    def test_settlement_conserves_cash(self):
        """Settlement is a pure transfer between wallets."""
        ledger = Ledger("settlement_cons", initial_time=datetime(2025, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("dealer")
        ledger.register_wallet("investor")
        # SYSTEM_WALLET is auto-registered

        fund = build_transaction(ledger, [
            Move(1_000_000.0, "USD", SYSTEM_WALLET, "dealer", "fund"),
            Move(100_000.0, "USD", SYSTEM_WALLET, "investor", "fund"),
        ])
        ledger.execute(fund)

        qis = create_qis(
            symbol="QIS_SETT",
            name="Settlement Test",
            notional=10_000,
            initial_nav=100.0,
            funding_rate=0.0,
            payer_wallet="dealer",
            receiver_wallet="investor",
            currency="USD",
            eligible_assets=["SPX"],
            rebalance_dates=[datetime(2025, 1, 1)],
            maturity_date=datetime(2025, 1, 2),
        )
        ledger.register_unit(qis)

        # Set up a position
        state = ledger.get_unit_state("QIS_SETT")
        state['holdings'] = {"SPX": 1.0}
        state['cash'] = 0.0
        state['next_rebalance_idx'] = 1
        ledger.units["QIS_SETT"]._state = state

        # Get total USD before settlement
        total_before = (
            ledger.get_balance("dealer", "USD") +
            ledger.get_balance("investor", "USD")
        )

        ledger.advance_time(datetime(2025, 1, 2))
        tx = compute_qis_settlement(ledger, "QIS_SETT", {"SPX": 110.0})
        ledger.execute(tx)

        # Total USD after settlement (between dealer and investor only)
        total_after = (
            ledger.get_balance("dealer", "USD") +
            ledger.get_balance("investor", "USD")
        )

        # Total should be unchanged (transfer, not creation/destruction)
        assert abs(total_after - total_before) < 0.01


# ============================================================================
# QUERY FUNCTION TESTS
# ============================================================================

class TestQueryFunctions:
    """Tests for QIS query functions."""

    @pytest.fixture
    def ledger_with_qis(self):
        """Create a ledger with a QIS that has positions."""
        ledger = Ledger("query_test", initial_time=datetime(2025, 1, 1))
        qis = create_qis(
            symbol="QIS_QUERY",
            name="Query Test",
            notional=10_000,
            initial_nav=100.0,
            funding_rate=0.05,
            payer_wallet="dealer",
            receiver_wallet="investor",
            currency="USD",
            eligible_assets=["SPX"],
            rebalance_dates=[datetime(2025, 1, 1)],
            maturity_date=datetime(2025, 12, 31),
        )
        ledger.register_unit(qis)

        # Set up 2x leveraged position
        state = ledger.get_unit_state("QIS_QUERY")
        state['holdings'] = {"SPX": 2.0}  # 2 shares at $100 = $200
        state['cash'] = -100.0  # Borrowed $100
        ledger.units["QIS_QUERY"]._state = state

        return ledger

    def test_get_qis_nav(self, ledger_with_qis):
        """get_qis_nav returns current NAV."""
        prices = {"SPX": 100.0}
        nav = get_qis_nav(ledger_with_qis, "QIS_QUERY", prices)
        # 2*100 - 100 = 100
        assert abs(nav - 100.0) < 0.01

    def test_get_qis_return(self, ledger_with_qis):
        """get_qis_return returns current total return."""
        # Price unchanged, NAV unchanged, return = 0
        prices = {"SPX": 100.0}
        ret = get_qis_return(ledger_with_qis, "QIS_QUERY", prices)
        assert abs(ret) < 0.01

        # Price up 10%, NAV should be up ~20% (2x leverage)
        prices = {"SPX": 110.0}
        ret = get_qis_return(ledger_with_qis, "QIS_QUERY", prices)
        # NAV = 2*110 - 100 = 120, return = 20%
        assert abs(ret - 0.20) < 0.01

    def test_get_qis_leverage(self, ledger_with_qis):
        """get_qis_leverage returns current leverage ratio."""
        prices = {"SPX": 100.0}
        leverage = get_qis_leverage(ledger_with_qis, "QIS_QUERY", prices)
        # Risky value = 200, NAV = 100, leverage = 2.0
        assert abs(leverage - 2.0) < 0.01
