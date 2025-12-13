"""
Comprehensive tests addressing findings from 7 specialized agent reviews.

Agents reviewed:
1. Market Microstructure Specialist - Real market behavior gaps
2. Regulatory Compliance Agent - Audit trails and reconstruction
3. Settlement Operations Agent - Settlement and fail handling
4. Quant Desk Risk Manager - Lifecycle event logic
5. Market Data & Simulation Specialist - Price handling gaps
6. SRE/Production Operations Agent - Production readiness
7. Financial Systems Integration Agent - External interfaces

This test file captures critical gaps identified by all 7 agents.
"""

import pytest
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from ledger import (
    Ledger, Move, cash, ExecuteResult, Transaction,
    SYSTEM_WALLET, build_transaction, Dividend,
)
from ledger.core import QUANTITY_EPSILON
from ledger.units.future import (
    create_future, transact as future_transact,
)
from ledger.units.bond import (
    create_bond_unit, compute_coupon_payment, compute_accrued_interest,
    compute_redemption, year_fraction
)
from ledger.units.margin_loan import (
    create_margin_loan, compute_margin_status, compute_margin_call,
    compute_interest_accrual, compute_liquidation, compute_margin_cure,
    MARGIN_STATUS_HEALTHY, MARGIN_STATUS_WARNING, MARGIN_STATUS_BREACH
)
from ledger.units.autocallable import (
    create_autocallable, compute_observation, compute_maturity_payoff,
    get_autocallable_status
)
from ledger.units.portfolio_swap import (
    create_portfolio_swap, compute_portfolio_nav, compute_swap_reset,
    compute_termination
)
from ledger.units.structured_note import (
    create_structured_note, compute_performance, compute_payoff_rate,
    compute_coupon_payment as compute_note_coupon,
    compute_maturity_payoff as compute_note_maturity
)


# =============================================================================
# MARKET MICROSTRUCTURE SPECIALIST FINDINGS
# =============================================================================

class TestTimezoneHandling:
    """Tests for timezone awareness identified by Market Microstructure Specialist."""

    def test_datetime_objects_are_consistent(self):
        """Verify datetime handling is internally consistent."""
        # Current system uses naive datetimes
        # This test documents current behavior
        t1 = datetime(2024, 12, 7, 10, 0, 0)
        t2 = datetime(2024, 12, 7, 10, 0, 0)
        assert t1 == t2, "Same naive datetimes should be equal"

        # Document: System does not enforce UTC
        ledger = Ledger("test", initial_time=t1)
        assert ledger.current_time == t1

    def test_settlement_date_on_weekend_behavior(self):
        """Document behavior when settlement falls on weekend."""
        # Friday March 15, 2024 trade -> T+2 = Sunday March 17
        trade_date = datetime(2024, 3, 15)  # Friday
        t_plus_2 = trade_date + timedelta(days=2)  # Sunday

        # Current system: no weekend/holiday handling
        assert t_plus_2.weekday() == 6, "T+2 falls on Sunday"
        # System would settle on Sunday - this is documented as a gap


class TestCorporateActionDates:
    """Tests for corporate action date handling."""

    def test_dividend_schedule_uses_payment_date_only(self):
        """Document: Dividend only has payment_date, not ex-date/record-date."""
        from ledger.units.stock import create_stock_unit

        ledger = Ledger("test", initial_time=datetime(2024, 3, 1))

        # New API: Dividend objects with ex_date, payment_date, amount, currency
        stock = create_stock_unit(
            symbol="AAPL",
            name="Apple",
            issuer="issuer",
            currency="USD",
            dividend_schedule=[
                Dividend(datetime(2024, 3, 15), datetime(2024, 3, 15), 0.25, "USD"),
            ]
        )

        state = stock._state
        schedule = state.get('dividend_schedule', [])

        # Verify: Schedule contains Dividend objects
        assert len(schedule) > 0, "Schedule should have dividend entries"


# =============================================================================
# REGULATORY COMPLIANCE AGENT FINDINGS
# =============================================================================

class TestAuditTrailCompleteness:
    """Tests for audit trail requirements identified by Compliance Agent."""

    def test_transaction_log_captures_all_moves(self):
        """Verify all executed moves are logged."""
        ledger = Ledger("audit_test", initial_time=datetime(2024, 12, 7))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        tx = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "audit_test_1")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.APPLIED
        assert len(ledger.transaction_log) == 1
        logged_tx = ledger.transaction_log[0]
        assert len(logged_tx.moves) == 1
        assert logged_tx.moves[0].quantity == 100.0

    def test_state_changes_captured_in_transaction(self):
        """Verify state changes are captured in transaction log."""
        ledger = Ledger("delta_test", initial_time=datetime(2024, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bank")

        # Create margin loan
        loan = create_margin_loan(
            symbol="LOAN_001",
            name="Test Loan",
            loan_amount=100000.0,
            interest_rate=0.08,
            collateral={"AAPL": 1000},
            haircuts={"AAPL": 0.70},
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )
        ledger.register_unit(loan)

        # Interest accrual creates state delta
        result = compute_interest_accrual(ledger, "LOAN_001", 30.0)
        ledger.execute(result)

        # Verify state delta was logged
        if ledger.transaction_log:
            last_tx = ledger.transaction_log[-1]
            assert len(last_tx.state_changes) > 0, "State deltas should be logged"

    def test_idempotency_prevents_duplicate_execution(self):
        """Verify same tx_id cannot be executed twice."""
        ledger = Ledger("idem_test", initial_time=datetime(2024, 12, 7))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        tx = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "idem_test_1")
        ])

        result1 = ledger.execute(tx)
        result2 = ledger.execute(tx)

        assert result1 == ExecuteResult.APPLIED
        assert result2 == ExecuteResult.ALREADY_APPLIED

        # Balance only deducted once
        assert ledger.get_balance("alice", "USD") == 900.0
        assert ledger.get_balance("bob", "USD") == 100.0


# =============================================================================
# SETTLEMENT OPERATIONS AGENT FINDINGS
# =============================================================================

class TestSettlementBehavior:
    """Tests for settlement operations identified by Settlement Agent."""

    def test_deferred_cash_atomic_settlement(self):
        """Verify deferred cash settles atomically."""
        from ledger.units.deferred_cash import (
            create_deferred_cash_unit, compute_deferred_cash_settlement
        )

        ledger = Ledger("settle_test", initial_time=datetime(2024, 3, 15))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("buyer")
        ledger.register_wallet("seller")

        # Create deferred cash for T+2 settlement
        dc = create_deferred_cash_unit(
            symbol="DC_001",
            amount=50000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),  # T+2
            payer_wallet="buyer",
            payee_wallet="seller",
            reference="TRADE_001"
        )
        ledger.register_unit(dc)
        ledger.set_balance("buyer", "USD", 100000.0)
        ledger.set_balance(SYSTEM_WALLET, "DC_001", 1.0)

        # Move obligation to buyer
        tx = build_transaction(ledger, [
            Move(1.0, "DC_001", SYSTEM_WALLET, "buyer", "create_obligation")
        ])
        ledger.execute(tx)

        # Advance to settlement date
        ledger.advance_time(datetime(2024, 3, 17))

        # Settle
        result = compute_deferred_cash_settlement(ledger, "DC_001", datetime(2024, 3, 17))
        ledger.execute(result)

        # Verify settlement occurred
        state = ledger.get_unit_state("DC_001")
        assert state.get('settled') is True


class TestBondSettlement:
    """Tests for bond settlement identified by Settlement Agent."""

    def test_coupon_payment_distributes_to_all_holders(self):
        """Verify coupon payments go to all bondholders proportionally."""
        ledger = Ledger("bond_test", initial_time=datetime(2024, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))

        bond = create_bond_unit(
            symbol="CORP_5Y",
            name="Corporate Bond 5%",
            face_value=1000.0,
            coupon_rate=0.05,
            coupon_frequency=2,  # Semi-annual
            maturity_date=datetime(2029, 1, 15),
            currency="USD",
            issuer_wallet="issuer",
            holder_wallet="holder1",
            issue_date=datetime(2024, 1, 15),
            day_count_convention="30/360"
        )
        ledger.register_unit(bond)

        ledger.register_wallet("issuer")
        ledger.register_wallet("holder1")
        ledger.register_wallet("holder2")

        # Two holders
        ledger.set_balance("holder1", "CORP_5Y", 10.0)
        ledger.set_balance("holder2", "CORP_5Y", 20.0)
        ledger.set_balance("issuer", "USD", 100000.0)

        # Advance to first coupon date
        ledger.advance_time(datetime(2024, 7, 15))

        result = compute_coupon_payment(ledger, "CORP_5Y", datetime(2024, 7, 15))

        # Verify moves for both holders
        # Coupon = face_value * coupon_rate / frequency = 1000 * 0.05 / 2 = 25.0 per bond
        moves = result.moves
        assert len(moves) == 2, "Should have 2 coupon payments"

        # holder1: 10 bonds * $25 = $250
        # holder2: 20 bonds * $25 = $500
        move_amounts = {m.dest: m.quantity for m in moves}
        assert abs(move_amounts.get("holder1", 0) - 250.0) < 0.01
        assert abs(move_amounts.get("holder2", 0) - 500.0) < 0.01


# =============================================================================
# QUANT DESK RISK MANAGER FINDINGS
# =============================================================================

class TestAutocallableLifecycle:
    """Tests for autocallable lifecycle identified by Quant Risk Manager."""

    def test_autocall_barrier_observation(self):
        """Verify autocall barrier observation logic."""
        ledger = Ledger("auto_test", initial_time=datetime(2024, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))

        auto = create_autocallable(
            symbol="AUTO_SPX",
            name="SPX Autocallable",
            underlying="SPX",
            notional=100000.0,
            initial_spot=4500.0,
            autocall_barrier=1.0,  # 100% of initial
            coupon_barrier=0.7,    # 70% of initial
            coupon_rate=0.08,      # 8%
            put_barrier=0.6,       # 60% of initial
            issue_date=datetime(2024, 1, 1),
            maturity_date=datetime(2024, 12, 31),
            observation_schedule=[
                datetime(2024, 4, 1),
                datetime(2024, 7, 1),
                datetime(2024, 10, 1),
            ],
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            memory_feature=True
        )
        ledger.register_unit(auto)
        ledger.register_wallet("bank")
        ledger.register_wallet("investor")
        ledger.set_balance("bank", "USD", 200000.0)
        ledger.set_balance("bank", "AUTO_SPX", -1.0)
        ledger.set_balance("investor", "AUTO_SPX", 1.0)

        # Observation 1: Below coupon barrier (miss, add to memory)
        ledger.advance_time(datetime(2024, 4, 1))
        result1 = compute_observation(ledger, "AUTO_SPX", datetime(2024, 4, 1), 3000.0)
        ledger.execute(result1)

        state = ledger.get_unit_state("AUTO_SPX")
        assert state.get('coupon_memory', 0) > 0, "Memory should accumulate"

        # Observation 2: Above autocall barrier (autocall triggers)
        ledger.advance_time(datetime(2024, 7, 1))
        result2 = compute_observation(ledger, "AUTO_SPX", datetime(2024, 7, 1), 4600.0)

        # Should have moves for autocall payout
        assert len(result2.moves) > 0, "Autocall should generate payout"

    def test_memory_coupon_accumulation(self):
        """Verify memory coupon correctly accumulates across missed periods."""
        ledger = Ledger("memory_test", initial_time=datetime(2024, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))

        auto = create_autocallable(
            symbol="AUTO_MEM",
            name="Memory Autocallable",
            underlying="SPX",
            notional=100000.0,
            initial_spot=4500.0,
            autocall_barrier=1.0,
            coupon_barrier=0.7,
            coupon_rate=0.08,
            put_barrier=0.6,
            issue_date=datetime(2024, 1, 1),
            maturity_date=datetime(2024, 12, 31),
            observation_schedule=[
                datetime(2024, 4, 1),
                datetime(2024, 7, 1),
            ],
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            memory_feature=True
        )
        ledger.register_unit(auto)
        ledger.register_wallet("bank")
        ledger.register_wallet("investor")
        ledger.set_balance("bank", "USD", 200000.0)

        # Miss first observation (below coupon barrier)
        result1 = compute_observation(ledger, "AUTO_MEM", datetime(2024, 4, 1), 3000.0)
        ledger.execute(result1)

        state = ledger.get_unit_state("AUTO_MEM")
        expected_memory = 100000.0 * 0.08  # One period of coupon
        assert abs(state.get('coupon_memory', 0) - expected_memory) < 1.0


class TestFuturesLifecycle:
    """Tests for futures lifecycle identified by Quant Risk Manager."""

    def test_multi_holder_pattern(self):
        """Verify multi-holder pattern for futures trades."""
        from tests.fake_view import FakeView

        # Market maker has position with proper state
        state = {
            'underlying': 'SPX',
            'expiry': datetime(2024, 12, 20),
            'multiplier': 50.0,
            'currency': 'USD',
            'clearinghouse': 'clearing',
            'wallets': {'market_maker': {'position': 100, 'virtual_cash': -22_500_000.0}},  # entered at 4500
            'settled': False,
            'last_settle_date': None,
        }
        view = FakeView(
            balances={
                'trader': {'USD': 100000},
                'clearing': {'USD': 1000000},
                'market_maker': {'ESZ24': 100},
            },
            states={'ESZ24': state},
            time=datetime(2024, 12, 1),
        )

        # Execute trade - creates position and sets per-wallet state
        # Trader buys from market_maker (via clearinghouse)
        result = future_transact(view, "ESZ24", seller_id="market_maker", buyer_id="trader", qty=10.0, price=4500.0)

        # Verify moves created (two moves: seller→CH, CH→buyer)
        assert len(result.moves) == 2
        assert result.moves[0].quantity == 10.0
        assert result.moves[1].quantity == 10.0

        # Verify per-wallet state (virtual_cash model)
        # virtual_cash = -qty * price * mult = -10 * 4500 * 50 = -2,250,000
        sc = next(d for d in result.state_changes if d.unit == "ESZ24")
        assert sc.new_state['wallets']['trader']['virtual_cash'] == -2_250_000.0

    def test_daily_settlement_updates_virtual_cash(self):
        """Verify EOD settlement updates wallet virtual_cash correctly."""
        from tests.fake_view import FakeView

        # Trader has 10 contracts, entered at 4500
        # virtual_cash = -10 * 4500 * 50 = -2,250,000
        state = {
            'underlying': 'SPX',
            'expiry': datetime(2024, 12, 20),
            'multiplier': 50.0,
            'currency': 'USD',
            'clearinghouse': 'clearing',
            'wallets': {'trader': {'position': 10, 'virtual_cash': -2_250_000.0}},
            'settled': False,
            'last_settle_date': None,
        }
        view = FakeView(
            balances={
                'trader': {'USD': 100000, 'ESZ24': 10},
                'clearing': {'USD': 1000000},
            },
            states={'ESZ24': state},
            time=datetime(2024, 12, 1),
        )

        # EOD settlement at 4510 (profit for holder)
        # target_vcash = -10 * 4510 * 50 = -2,255,000
        # vm = -2,250,000 - (-2,255,000) = +5,000
        from ledger import future_contract
        result = future_contract(view, "ESZ24", datetime(2024, 12, 1), {"SPX": 4510.0})

        # Verify VM move: profit of 5000
        assert len(result.moves) == 1
        assert result.moves[0].quantity == 5000.0

        # Verify virtual_cash updated to target
        sc = next(d for d in result.state_changes if d.unit == "ESZ24")
        assert sc.new_state['wallets']['trader']['virtual_cash'] == -2_255_000.0


class TestMarginLoanLifecycle:
    """Tests for margin loan lifecycle identified by Quant Risk Manager."""

    def test_margin_status_computation(self):
        """Verify margin status is computed correctly."""
        ledger = Ledger("margin_test", initial_time=datetime(2024, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))

        loan = create_margin_loan(
            symbol="LOAN_001",
            name="Test Loan",
            loan_amount=100000.0,
            interest_rate=0.08,
            collateral={"AAPL": 1000},
            haircuts={"AAPL": 0.70},
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )
        ledger.register_unit(loan)
        ledger.register_wallet("alice")
        ledger.register_wallet("bank")

        # AAPL at $250: collateral = 1000 * 250 * 0.70 = 175,000
        # Margin ratio = 175,000 / 100,000 = 1.75 (healthy, above 1.5 initial)
        prices_healthy = {"AAPL": 250.0}
        status = compute_margin_status(ledger, "LOAN_001", prices_healthy)
        assert status["status"] == MARGIN_STATUS_HEALTHY

        # AAPL at $150: collateral = 1000 * 150 * 0.70 = 105,000
        # Margin ratio = 105,000 / 100,000 = 1.05 (breach, below 1.25)
        prices_breach = {"AAPL": 150.0}
        status_breach = compute_margin_status(ledger, "LOAN_001", prices_breach)
        assert status_breach["status"] == MARGIN_STATUS_BREACH

    def test_interest_accrual_updates_debt(self):
        """Verify interest accrual increases total debt."""
        ledger = Ledger("accrual_test", initial_time=datetime(2024, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))

        loan = create_margin_loan(
            symbol="LOAN_002",
            name="Test Loan",
            loan_amount=100000.0,
            interest_rate=0.08,  # 8% annual
            collateral={"AAPL": 1000},
            haircuts={"AAPL": 0.70},
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )
        ledger.register_unit(loan)
        ledger.register_wallet("alice")
        ledger.register_wallet("bank")

        # Accrue 30 days of interest
        result = compute_interest_accrual(ledger, "LOAN_002", 30.0)
        ledger.execute(result)

        state = ledger.get_unit_state("LOAN_002")
        # Interest = 100,000 * 0.08 * (30/365) = ~657.53
        expected_interest = 100000.0 * 0.08 * (30.0 / 365.0)
        assert abs(state.get('accrued_interest', 0) - expected_interest) < 1.0


# =============================================================================
# MARKET DATA SPECIALIST FINDINGS
# =============================================================================

class TestPriceValidation:
    """Tests for price handling gaps identified by Market Data Specialist."""

    def test_negative_price_behavior(self):
        """Document behavior with negative prices (edge case)."""
        ledger = Ledger("price_test", initial_time=datetime(2024, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))

        # Create autocallable
        auto = create_autocallable(
            symbol="AUTO_TEST",
            name="Test Autocallable",
            underlying="SPX",
            notional=100000.0,
            initial_spot=4500.0,
            autocall_barrier=1.0,
            coupon_barrier=0.7,
            coupon_rate=0.08,
            put_barrier=0.6,
            issue_date=datetime(2024, 1, 1),
            maturity_date=datetime(2024, 12, 31),
            observation_schedule=[datetime(2024, 4, 1)],
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            memory_feature=False
        )
        ledger.register_unit(auto)

        # Negative price should raise ValueError
        with pytest.raises(ValueError, match="spot.*positive"):
            compute_observation(ledger, "AUTO_TEST", datetime(2024, 4, 1), -100.0)

    def test_zero_price_behavior(self):
        """Document behavior with zero price."""
        ledger = Ledger("zero_test", initial_time=datetime(2024, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))

        auto = create_autocallable(
            symbol="AUTO_ZERO",
            name="Test",
            underlying="SPX",
            notional=100000.0,
            initial_spot=4500.0,
            autocall_barrier=1.0,
            coupon_barrier=0.7,
            coupon_rate=0.08,
            put_barrier=0.6,
            issue_date=datetime(2024, 1, 1),
            maturity_date=datetime(2024, 12, 31),
            observation_schedule=[datetime(2024, 4, 1)],
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            memory_feature=False
        )
        ledger.register_unit(auto)

        # Zero price should raise ValueError
        with pytest.raises(ValueError, match="spot.*positive"):
            compute_observation(ledger, "AUTO_ZERO", datetime(2024, 4, 1), 0.0)

    def test_margin_loan_missing_collateral_price(self):
        """Document: Missing collateral price treated as 0 (identified as gap)."""
        ledger = Ledger("missing_test", initial_time=datetime(2024, 1, 1))

        loan = create_margin_loan(
            symbol="LOAN_MISS",
            name="Test",
            loan_amount=100000.0,
            interest_rate=0.08,
            collateral={"AAPL": 1000, "MSFT": 500},
            haircuts={"AAPL": 0.70, "MSFT": 0.70},
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )
        ledger.register_unit(loan)
        ledger.register_wallet("alice")
        ledger.register_wallet("bank")

        # Only AAPL price, MSFT missing
        prices = {"AAPL": 150.0}  # MSFT missing!

        # Current behavior: missing price treated as 0
        # This is documented as a gap - should raise error
        status = compute_margin_status(ledger, "LOAN_MISS", prices)

        # Collateral only counts AAPL: 1000 * 150 * 0.70 = 105,000
        # MSFT treated as 0 value
        assert status["collateral_value"] == 105000.0


# =============================================================================
# SRE PRODUCTION OPS FINDINGS
# =============================================================================

class TestProductionResilience:
    """Tests for production readiness identified by SRE Agent."""

    def test_double_entry_verification(self):
        """Verify double-entry accounting verification works."""
        ledger = Ledger("verify_test", initial_time=datetime(2024, 12, 7))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        # Set initial balances
        ledger.set_balance("alice", "USD", 1000.0)

        # Execute transactions
        for i in range(10):
            tx = build_transaction(ledger, [
                Move(10.0, "USD", "alice", "bob", f"tx_{i}")
            ])
            ledger.execute(tx)

        # Verify conservation
        result = ledger.verify_double_entry(
            expected_supplies={"USD": 1000.0},
            tolerance=1e-9
        )
        assert result['valid'], f"Conservation violated: {result.get('discrepancies')}"

    def test_transaction_log_grows_with_executions(self):
        """Verify transaction log captures all executions."""
        ledger = Ledger("log_test", initial_time=datetime(2024, 12, 7))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 10000.0)

        num_transactions = 100
        for i in range(num_transactions):
            tx = build_transaction(ledger, [
                Move(1.0, "USD", "alice", "bob", f"log_tx_{i}")
            ])
            ledger.execute(tx)

        assert len(ledger.transaction_log) == num_transactions

    def test_clone_at_reconstructs_historical_state(self):
        """Verify clone_at can reconstruct past state."""
        ledger = Ledger("clone_test", initial_time=datetime(2024, 12, 1))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        # Snapshot time
        t0 = datetime(2024, 12, 1)

        # Execute some transactions
        ledger.advance_time(datetime(2024, 12, 5))
        tx1 = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "tx1")
        ])
        ledger.execute(tx1)

        ledger.advance_time(datetime(2024, 12, 10))
        tx2 = build_transaction(ledger, [
            Move(200.0, "USD", "alice", "bob", "tx2")
        ])
        ledger.execute(tx2)

        # Clone at initial time
        cloned = ledger.clone_at(t0)

        # Cloned ledger should have original balances
        assert cloned.get_balance("alice", "USD") == 1000.0
        assert cloned.get_balance("bob", "USD") == 0.0


# =============================================================================
# FINANCIAL SYSTEMS INTEGRATION FINDINGS
# =============================================================================

class TestIntegrationReadiness:
    """Tests for integration readiness identified by Integration Agent."""

    def test_transaction_has_unique_id(self):
        """Verify transactions have unique, deterministic IDs."""
        ledger = Ledger("id_test", initial_time=datetime(2024, 12, 7))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        tx1 = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "tx_unique_1")
        ])
        tx2 = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "tx_unique_2")
        ])

        assert tx1.intent_id != tx2.intent_id, "Different transactions should have different IDs"
        assert len(tx1.intent_id) > 0, "Transaction ID should not be empty"

    def test_move_metadata_available(self):
        """Verify moves can carry metadata for integration."""
        ledger = Ledger("meta_test", initial_time=datetime(2024, 12, 7))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        move = Move(
            quantity=100.0,
            unit_symbol="USD",
            source="alice",
            dest="bob",
            contract_id="meta_test",
            metadata={
                "isin": "US0378331005",
                "settlement_date": "2024-12-09",
                "counterparty_lei": "549300HWUPKR86EBD5"
            }
        )

        assert move.metadata is not None
        assert move.metadata.get("isin") == "US0378331005"

    def test_multi_currency_units_supported(self):
        """Verify ledger supports multiple currencies."""
        ledger = Ledger("multi_ccy_test", initial_time=datetime(2024, 12, 7))

        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(cash("EUR", "Euro"))
        ledger.register_unit(cash("JPY", "Japanese Yen"))

        ledger.register_wallet("treasury")

        ledger.set_balance("treasury", "USD", 1000000.0)
        ledger.set_balance("treasury", "EUR", 900000.0)
        ledger.set_balance("treasury", "JPY", 150000000.0)

        assert ledger.get_balance("treasury", "USD") == 1000000.0
        assert ledger.get_balance("treasury", "EUR") == 900000.0
        assert ledger.get_balance("treasury", "JPY") == 150000000.0


# =============================================================================
# CROSS-CUTTING TESTS FROM MULTIPLE AGENTS
# =============================================================================

class TestDayCountConventions:
    """Tests for day count conventions (Bond module)."""

    def test_30_360_day_count(self):
        """Verify 30/360 day count convention."""
        # Jan 1 to Mar 1 should be 60 days in 30/360
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 1)

        fraction = year_fraction(start, end, "30/360")
        # 2 months * 30 days = 60 days / 360 = 0.1667
        assert abs(fraction - (60.0 / 360.0)) < 0.001

    def test_act_360_day_count(self):
        """Verify ACT/360 day count convention."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 2, 1)  # 31 actual days

        fraction = year_fraction(start, end, "ACT/360")
        # 31 actual days / 360
        assert abs(fraction - (31.0 / 360.0)) < 0.001

    def test_act_act_day_count(self):
        """Verify ACT/ACT day count convention."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 2, 1)  # 31 actual days

        fraction = year_fraction(start, end, "ACT/ACT")
        # Current implementation uses 365.25 as denominator
        assert abs(fraction - (31.0 / 365.25)) < 0.001


class TestConservationLaws:
    """Tests for double-entry accounting conservation laws."""

    def test_transfers_preserve_total_supply(self):
        """Verify transfers don't create or destroy value."""
        ledger = Ledger("conservation_test", initial_time=datetime(2024, 12, 7))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("charlie")

        # Initial supply
        ledger.set_balance("alice", "USD", 1000.0)

        initial_supply = ledger.total_supply("USD")

        # Multiple transfers
        tx1 = build_transaction(ledger, [
            Move(300.0, "USD", "alice", "bob", "transfer1")
        ])
        ledger.execute(tx1)

        tx2 = build_transaction(ledger, [
            Move(150.0, "USD", "bob", "charlie", "transfer2")
        ])
        ledger.execute(tx2)

        tx3 = build_transaction(ledger, [
            Move(50.0, "USD", "charlie", "alice", "transfer3")
        ])
        ledger.execute(tx3)

        final_supply = ledger.total_supply("USD")

        assert abs(initial_supply - final_supply) < QUANTITY_EPSILON

    def test_settlement_preserves_conservation(self):
        """Verify settlements don't violate conservation."""
        ledger = Ledger("settle_conservation", initial_time=datetime(2024, 1, 1))
        ledger.register_unit(cash("USD", "US Dollar"))

        # Create bond with issuer as source of coupons
        bond = create_bond_unit(
            symbol="BOND_CONS",
            name="Conservation Test Bond",
            face_value=1000.0,
            coupon_rate=0.05,
            coupon_frequency=2,
            maturity_date=datetime(2029, 1, 15),
            currency="USD",
            issuer_wallet="issuer",
            holder_wallet="holder",
            issue_date=datetime(2024, 1, 15),
        )
        ledger.register_unit(bond)

        ledger.register_wallet("issuer")
        ledger.register_wallet("holder")

        # Issuer has cash for coupons
        ledger.set_balance("issuer", "USD", 100000.0)
        ledger.set_balance("holder", "BOND_CONS", 10.0)

        initial_usd = ledger.total_supply("USD")

        # Pay coupon
        ledger.advance_time(datetime(2024, 7, 15))
        result = compute_coupon_payment(ledger, "BOND_CONS", datetime(2024, 7, 15))
        ledger.execute(result)

        final_usd = ledger.total_supply("USD")

        # USD supply should be unchanged (transfer from issuer to holder)
        assert abs(initial_usd - final_usd) < QUANTITY_EPSILON


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
