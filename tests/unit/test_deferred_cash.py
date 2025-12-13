"""
Tests for deferred_cash.py - DeferredCash Unit for T+n Settlement

Tests:
- create_deferred_cash_unit factory (creates DeferredCash units with payment obligations)
- compute_deferred_cash_settlement (executes payment on payment date)
- transact (event-driven interface for SETTLEMENT)
- deferred_cash_contract lifecycle integration (automated settlement via LifecycleEngine)
- Conservation laws maintained throughout lifecycle
"""

import pytest
from datetime import datetime, timedelta

from ledger import (
    Ledger, cash,
    Move,
    LifecycleEngine,
    create_deferred_cash_unit,
    compute_deferred_cash_settlement,
    deferred_cash_transact,
    deferred_cash_contract,
    SYSTEM_WALLET,
)


# ============================================================================
# create_deferred_cash_unit Tests
# ============================================================================

class TestCreateDeferredCashUnit:
    """Tests for create_deferred_cash_unit factory."""

    def test_create_deferred_cash_unit_basic(self):
        """Test basic DeferredCash unit creation."""
        unit = create_deferred_cash_unit(
            symbol="DC_trade_123",
            amount=15000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),
            payer_wallet="buyer",
            payee_wallet="seller",
        )

        assert unit.symbol == "DC_trade_123"
        assert unit.unit_type == "DEFERRED_CASH"
        assert unit._state['amount'] == 15000.0
        assert unit._state['currency'] == "USD"
        assert unit._state['payment_date'] == datetime(2024, 3, 17)
        assert unit._state['payer_wallet'] == "buyer"
        assert unit._state['payee_wallet'] == "seller"
        assert unit._state['settled'] is False
        assert unit._state['reference'] is None

    def test_create_deferred_cash_unit_with_reference(self):
        """Test DeferredCash with reference ID."""
        unit = create_deferred_cash_unit(
            symbol="DC_trade_456",
            amount=25000.0,
            currency="EUR",
            payment_date=datetime(2024, 6, 15),
            payer_wallet="alice",
            payee_wallet="bob",
            reference="trade_456",
        )

        assert unit._state['reference'] == "trade_456"

    def test_create_deferred_cash_unit_quantity_always_one(self):
        """DeferredCash quantity is always 1 (amount is in state)."""
        unit = create_deferred_cash_unit(
            symbol="DC_test",
            amount=99999.99,
            currency="USD",
            payment_date=datetime(2024, 1, 1),
            payer_wallet="a",
            payee_wallet="b",
        )

        # Max balance is 1.0 (enforces quantity = 1)
        assert unit.max_balance == 1.0
        assert unit.decimal_places == 0  # No fractional units

    def test_create_deferred_cash_validates_amount(self):
        """Amount must be positive."""
        with pytest.raises(ValueError, match="amount must be positive"):
            create_deferred_cash_unit(
                symbol="DC_test",
                amount=0.0,
                currency="USD",
                payment_date=datetime(2024, 1, 1),
                payer_wallet="a",
                payee_wallet="b",
            )

        with pytest.raises(ValueError, match="amount must be positive"):
            create_deferred_cash_unit(
                symbol="DC_test",
                amount=-100.0,
                currency="USD",
                payment_date=datetime(2024, 1, 1),
                payer_wallet="a",
                payee_wallet="b",
            )

    def test_create_deferred_cash_validates_currency(self):
        """Currency cannot be empty."""
        with pytest.raises(ValueError, match="currency cannot be empty"):
            create_deferred_cash_unit(
                symbol="DC_test",
                amount=100.0,
                currency="",
                payment_date=datetime(2024, 1, 1),
                payer_wallet="a",
                payee_wallet="b",
            )

    def test_create_deferred_cash_validates_wallets(self):
        """Payer and payee must be different and non-empty."""
        with pytest.raises(ValueError, match="payer_wallet cannot be empty"):
            create_deferred_cash_unit(
                symbol="DC_test",
                amount=100.0,
                currency="USD",
                payment_date=datetime(2024, 1, 1),
                payer_wallet="",
                payee_wallet="b",
            )

        with pytest.raises(ValueError, match="payee_wallet cannot be empty"):
            create_deferred_cash_unit(
                symbol="DC_test",
                amount=100.0,
                currency="USD",
                payment_date=datetime(2024, 1, 1),
                payer_wallet="a",
                payee_wallet="",
            )

        with pytest.raises(ValueError, match="payer_wallet and payee_wallet must be different"):
            create_deferred_cash_unit(
                symbol="DC_test",
                amount=100.0,
                currency="USD",
                payment_date=datetime(2024, 1, 1),
                payer_wallet="alice",
                payee_wallet="alice",
            )


# ============================================================================
# compute_deferred_cash_settlement Tests
# ============================================================================

class TestComputeDeferredCashSettlement:
    """Tests for compute_deferred_cash_settlement function."""

    @pytest.fixture
    def setup_ledger(self):
        """Create a test ledger with DeferredCash obligation."""
        ledger = Ledger("test", datetime(2024, 3, 15), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Register wallets
        ledger.register_wallet("buyer")
        ledger.register_wallet("seller")

        # Fund buyer with cash
        ledger.set_balance("buyer", "USD", 50000.0)

        return ledger

    def test_settlement_on_payment_date(self, setup_ledger):
        """Settlement executes on payment date."""
        ledger = setup_ledger

        # Create DeferredCash unit
        dc_unit = create_deferred_cash_unit(
            symbol="DC_trade_123",
            amount=15000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),
            payer_wallet="buyer",
            payee_wallet="seller",
        )
        ledger.register_unit(dc_unit)

        # Create the obligation (system → buyer)
        ledger.set_balance("buyer", "DC_trade_123", 1)

        # Advance to payment date
        ledger.advance_time(datetime(2024, 3, 17))

        # Execute settlement
        result = compute_deferred_cash_settlement(ledger, "DC_trade_123", datetime(2024, 3, 17))

        assert not result.is_empty()
        assert len(result.moves) == 2

        # Check cash payment
        cash_move = next(m for m in result.moves if m.unit_symbol == "USD")
        assert cash_move.source == "buyer"
        assert cash_move.dest == "seller"
        assert cash_move.quantity == 15000.0

        # Check extinguishment
        extinguish_move = next(m for m in result.moves if m.unit_symbol == "DC_trade_123")
        assert extinguish_move.source == "buyer"
        assert extinguish_move.dest == SYSTEM_WALLET
        assert extinguish_move.quantity == 1.0

        # Check state update
        sc = next(d for d in result.state_changes if d.unit == "DC_trade_123")
        assert sc.new_state['settled'] is True

    def test_settlement_before_payment_date_returns_empty(self, setup_ledger):
        """Settlement should not execute before payment date."""
        ledger = setup_ledger

        dc_unit = create_deferred_cash_unit(
            symbol="DC_trade_123",
            amount=15000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),
            payer_wallet="buyer",
            payee_wallet="seller",
        )
        ledger.register_unit(dc_unit)
        ledger.set_balance("buyer", "DC_trade_123", 1)

        # Try to settle before payment date
        result = compute_deferred_cash_settlement(ledger, "DC_trade_123", datetime(2024, 3, 16))

        assert result.is_empty()

    def test_settlement_already_settled_returns_empty(self, setup_ledger):
        """Already settled DeferredCash returns empty result."""
        ledger = setup_ledger

        dc_unit = create_deferred_cash_unit(
            symbol="DC_trade_123",
            amount=15000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),
            payer_wallet="buyer",
            payee_wallet="seller",
        )
        ledger.register_unit(dc_unit)
        ledger.set_balance("buyer", "DC_trade_123", 1)

        # First settlement
        ledger.advance_time(datetime(2024, 3, 17))
        result1 = compute_deferred_cash_settlement(ledger, "DC_trade_123", datetime(2024, 3, 17))
        ledger.execute(result1)

        # Try second settlement
        result2 = compute_deferred_cash_settlement(ledger, "DC_trade_123", datetime(2024, 3, 17))

        assert result2.is_empty()

    def test_settlement_no_position_returns_empty(self, setup_ledger):
        """If payee has no DeferredCash position, return empty."""
        ledger = setup_ledger

        dc_unit = create_deferred_cash_unit(
            symbol="DC_trade_123",
            amount=15000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),
            payer_wallet="buyer",
            payee_wallet="seller",
        )
        ledger.register_unit(dc_unit)

        # No obligation created (payee has no position)
        ledger.advance_time(datetime(2024, 3, 17))
        result = compute_deferred_cash_settlement(ledger, "DC_trade_123", datetime(2024, 3, 17))

        assert result.is_empty()

    def test_settlement_updates_ledger_balances(self, setup_ledger):
        """Settlement should correctly update all ledger balances."""
        ledger = setup_ledger

        dc_unit = create_deferred_cash_unit(
            symbol="DC_trade_123",
            amount=15000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),
            payer_wallet="buyer",
            payee_wallet="seller",
        )
        ledger.register_unit(dc_unit)
        ledger.set_balance("buyer", "DC_trade_123", 1)

        # Pre-settlement balances
        assert ledger.get_balance("buyer", "USD") == 50000.0
        assert ledger.get_balance("seller", "USD") == 0.0
        assert ledger.get_balance("buyer", "DC_trade_123") == 1.0

        # Execute settlement
        ledger.advance_time(datetime(2024, 3, 17))
        result = compute_deferred_cash_settlement(ledger, "DC_trade_123", datetime(2024, 3, 17))
        ledger.execute(result)

        # Post-settlement balances
        assert ledger.get_balance("buyer", "USD") == 35000.0  # -15000
        assert ledger.get_balance("seller", "USD") == 15000.0  # +15000
        assert ledger.get_balance("buyer", "DC_trade_123") == 0.0  # Extinguished
        assert ledger.get_balance(SYSTEM_WALLET, "DC_trade_123") == 1.0  # Returned to system


# ============================================================================
# deferred_cash_contract Integration Tests
# ============================================================================

class TestDeferredCashContractIntegration:
    """Tests for deferred_cash_contract with LifecycleEngine."""

    def test_lifecycle_engine_processes_settlement(self):
        """LifecycleEngine automatically settles DeferredCash on payment date."""
        ledger = Ledger("test", datetime(2024, 3, 15), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        ledger.register_wallet("buyer")
        ledger.register_wallet("seller")
        ledger.set_balance("buyer", "USD", 100000.0)

        # Create DeferredCash
        dc_unit = create_deferred_cash_unit(
            symbol="DC_trade_123",
            amount=25000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),
            payer_wallet="buyer",
            payee_wallet="seller",
            reference="trade_123",
        )
        ledger.register_unit(dc_unit)
        ledger.set_balance("buyer", "DC_trade_123", 1)

        # Create lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Run past payment date
        timestamps = [
            datetime(2024, 3, 15),
            datetime(2024, 3, 16),
            datetime(2024, 3, 17),  # Payment date
            datetime(2024, 3, 18),
        ]
        engine.run(timestamps, lambda ts: {})

        # Check settlement occurred
        assert ledger.get_balance("buyer", "USD") == 75000.0  # -25000
        assert ledger.get_balance("seller", "USD") == 25000.0  # +25000
        assert ledger.get_balance("buyer", "DC_trade_123") == 0.0  # Extinguished

        # Check state updated
        state = ledger.get_unit_state("DC_trade_123")
        assert state['settled'] is True

    def test_multiple_deferred_cash_different_dates(self):
        """LifecycleEngine handles multiple DeferredCash with different payment dates."""
        ledger = Ledger("test", datetime(2024, 3, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        ledger.register_wallet("buyer")
        ledger.register_wallet("seller")
        ledger.set_balance("buyer", "USD", 100000.0)

        # Create multiple DeferredCash obligations
        dc1 = create_deferred_cash_unit(
            symbol="DC_trade_1",
            amount=10000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 10),
            payer_wallet="buyer",
            payee_wallet="seller",
        )
        dc2 = create_deferred_cash_unit(
            symbol="DC_trade_2",
            amount=15000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 15),
            payer_wallet="buyer",
            payee_wallet="seller",
        )
        dc3 = create_deferred_cash_unit(
            symbol="DC_trade_3",
            amount=20000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 20),
            payer_wallet="buyer",
            payee_wallet="seller",
        )

        ledger.register_unit(dc1)
        ledger.register_unit(dc2)
        ledger.register_unit(dc3)

        ledger.set_balance("buyer", "DC_trade_1", 1)
        ledger.set_balance("buyer", "DC_trade_2", 1)
        ledger.set_balance("buyer", "DC_trade_3", 1)

        # Create lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Run through all payment dates
        timestamps = [datetime(2024, 3, 1) + timedelta(days=i) for i in range(25)]
        engine.run(timestamps, lambda ts: {})

        # All should be settled
        assert ledger.get_balance("buyer", "USD") == 55000.0  # -45000 total
        assert ledger.get_balance("seller", "USD") == 45000.0  # +45000 total
        assert ledger.get_balance("buyer", "DC_trade_1") == 0.0
        assert ledger.get_balance("buyer", "DC_trade_2") == 0.0
        assert ledger.get_balance("buyer", "DC_trade_3") == 0.0


# ============================================================================
# Conservation Laws Tests
# ============================================================================

class TestConservationLaws:
    """Tests that conservation laws are maintained throughout DeferredCash lifecycle."""

    def test_conservation_cash_throughout_lifecycle(self):
        """Total USD supply remains constant throughout DeferredCash lifecycle."""
        ledger = Ledger("test", datetime(2024, 3, 15), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        ledger.register_wallet("buyer")
        ledger.register_wallet("seller")

        # Initial USD supply
        ledger.set_balance("buyer", "USD", 100000.0)
        ledger.set_balance("seller", "USD", 50000.0)
        initial_usd_supply = ledger.total_supply("USD")

        # Create DeferredCash
        dc_unit = create_deferred_cash_unit(
            symbol="DC_trade_123",
            amount=30000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),
            payer_wallet="buyer",
            payee_wallet="seller",
        )
        ledger.register_unit(dc_unit)

        # Create obligation
        ledger.set_balance("buyer", "DC_trade_123", 1)

        # USD supply unchanged after obligation creation
        assert ledger.total_supply("USD") == initial_usd_supply

        # Execute settlement
        ledger.advance_time(datetime(2024, 3, 17))
        result = compute_deferred_cash_settlement(ledger, "DC_trade_123", datetime(2024, 3, 17))
        ledger.execute(result)

        # USD supply unchanged after settlement
        assert ledger.total_supply("USD") == initial_usd_supply

        # Verify balances
        assert ledger.get_balance("buyer", "USD") == 70000.0
        assert ledger.get_balance("seller", "USD") == 80000.0

    def test_conservation_deferred_cash_lifecycle(self):
        """DeferredCash supply follows: 0 → 1 (creation) → 0 (extinguishment)."""
        ledger = Ledger("test", datetime(2024, 3, 15), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        ledger.register_wallet("buyer")
        ledger.register_wallet("seller")
        ledger.set_balance("buyer", "USD", 100000.0)

        # Create DeferredCash
        dc_unit = create_deferred_cash_unit(
            symbol="DC_trade_123",
            amount=15000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),
            payer_wallet="buyer",
            payee_wallet="seller",
        )
        ledger.register_unit(dc_unit)

        # Initial: no DeferredCash in circulation
        assert ledger.total_supply("DC_trade_123") == 0.0

        # Create obligation (system → buyer)
        ledger.set_balance("buyer", "DC_trade_123", 1)

        # After creation: 1 unit in circulation
        # Note: system wallet is excluded from total_supply calculation
        assert ledger.get_balance("buyer", "DC_trade_123") == 1.0

        # Execute settlement
        ledger.advance_time(datetime(2024, 3, 17))
        result = compute_deferred_cash_settlement(ledger, "DC_trade_123", datetime(2024, 3, 17))
        ledger.execute(result)

        # After extinguishment: buyer has 0, system has 1
        assert ledger.get_balance("buyer", "DC_trade_123") == 0.0
        assert ledger.get_balance(SYSTEM_WALLET, "DC_trade_123") == 1.0  # Returned to system


# ============================================================================
# T+2 Settlement Pattern Tests
# ============================================================================

class TestT2SettlementPattern:
    """Tests for T+2 stock settlement pattern using DeferredCash."""

    def test_t2_stock_trade_complete_flow(self):
        """Complete T+2 settlement flow: trade date → settlement date."""
        ledger = Ledger("test", datetime(2024, 3, 15), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Create stock
        from ledger import create_stock_unit
        stock = create_stock_unit("AAPL", "Apple Inc.", "treasury", "USD")
        ledger.register_unit(stock)

        # Register participants
        ledger.register_wallet("buyer")
        ledger.register_wallet("seller")

        # Initial positions
        ledger.set_balance("buyer", "USD", 100000.0)
        ledger.set_balance("seller", "AAPL", 100.0)

        # === Trade Date (T) ===
        trade_date = datetime(2024, 3, 15)
        settlement_date = datetime(2024, 3, 19)  # T+2 (skip weekend)
        trade_price = 150.0
        trade_qty = 100.0
        trade_amount = trade_price * trade_qty

        # Stock moves immediately (economic ownership transfers)
        ledger.set_balance("seller", "AAPL", 0.0)  # Seller no longer has stock
        ledger.set_balance("buyer", "AAPL", trade_qty)

        # Create DeferredCash obligation
        dc_unit = create_deferred_cash_unit(
            symbol="DC_trade_AAPL_20240315",
            amount=trade_amount,
            currency="USD",
            payment_date=settlement_date,
            payer_wallet="buyer",
            payee_wallet="seller",
            reference="trade_AAPL_20240315",
        )
        ledger.register_unit(dc_unit)
        ledger.set_balance("buyer", "DC_trade_AAPL_20240315", 1)

        # After trade date: buyer has stock, obligation; seller has neither
        assert ledger.get_balance("buyer", "AAPL") == 100.0
        assert ledger.get_balance("seller", "AAPL") == 0.0
        assert ledger.get_balance("buyer", "DC_trade_AAPL_20240315") == 1.0
        assert ledger.get_balance("buyer", "USD") == 100000.0  # Cash not yet moved
        assert ledger.get_balance("seller", "USD") == 0.0

        # === Settlement Date (T+2) ===
        ledger.advance_time(settlement_date)

        # Execute settlement
        result = compute_deferred_cash_settlement(
            ledger,
            "DC_trade_AAPL_20240315",
            settlement_date
        )
        ledger.execute(result)

        # After settlement: cash paid, obligation extinguished
        assert ledger.get_balance("buyer", "USD") == 85000.0  # -15000
        assert ledger.get_balance("seller", "USD") == 15000.0  # +15000
        assert ledger.get_balance("buyer", "DC_trade_AAPL_20240315") == 0.0  # Extinguished

        # Stock position unchanged
        assert ledger.get_balance("buyer", "AAPL") == 100.0
        assert ledger.get_balance("seller", "AAPL") == 0.0

    def test_t2_settlement_with_lifecycle_engine(self):
        """T+2 settlement automated by LifecycleEngine."""
        ledger = Ledger("test", datetime(2024, 3, 15), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        from ledger import create_stock_unit
        stock = create_stock_unit("AAPL", "Apple Inc.", "treasury", "USD")
        ledger.register_unit(stock)

        ledger.register_wallet("buyer")
        ledger.register_wallet("seller")

        ledger.set_balance("buyer", "USD", 200000.0)
        ledger.set_balance("seller", "AAPL", 100.0)

        # Trade on T
        trade_date = datetime(2024, 3, 15)
        settlement_date = datetime(2024, 3, 19)  # T+2

        ledger.set_balance("buyer", "AAPL", 100.0)

        dc_unit = create_deferred_cash_unit(
            symbol="DC_AAPL_T2",
            amount=15000.0,
            currency="USD",
            payment_date=settlement_date,
            payer_wallet="buyer",
            payee_wallet="seller",
        )
        ledger.register_unit(dc_unit)
        ledger.set_balance("buyer", "DC_AAPL_T2", 1)

        # Setup lifecycle engine
        engine = LifecycleEngine(ledger)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Run from T to T+5
        timestamps = [trade_date + timedelta(days=i) for i in range(6)]
        engine.run(timestamps, lambda ts: {})

        # Verify settlement occurred on T+2
        assert ledger.get_balance("buyer", "USD") == 185000.0
        assert ledger.get_balance("seller", "USD") == 15000.0
        assert ledger.get_unit_state("DC_AAPL_T2")['settled'] is True


# ============================================================================
# Dividend DeferredCash Pattern Tests
# ============================================================================

class TestDividendDeferredCashPattern:
    """Tests for dividend payment pattern using DeferredCash."""

    def test_dividend_deferred_cash_creation(self):
        """Dividend entitlement creates DeferredCash on ex-date."""
        ledger = Ledger("test", datetime(2024, 3, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        ledger.register_wallet("alice")
        ledger.register_wallet("treasury")

        ledger.set_balance("treasury", "USD", 1000000.0)

        # Alice owns 1000 shares on ex-date
        ex_date = datetime(2024, 3, 15)
        payment_date = datetime(2024, 3, 29)
        dividend_per_share = 0.50
        alice_shares = 1000.0
        alice_dividend = alice_shares * dividend_per_share

        # Create DeferredCash for Alice's dividend entitlement
        dc_unit = create_deferred_cash_unit(
            symbol=f"DIV_AAPL_{ex_date.date()}_alice",
            amount=alice_dividend,
            currency="USD",
            payment_date=payment_date,
            payer_wallet="treasury",
            payee_wallet="alice",
            reference=f"dividend_AAPL_{ex_date.date()}",
        )
        ledger.register_unit(dc_unit)

        # Create entitlement
        # For dividends, Alice (payee) holds the entitlement
        ledger.set_balance("alice", dc_unit.symbol, 1)

        # Alice has dividend entitlement, but cash not yet paid
        assert ledger.get_balance("alice", dc_unit.symbol) == 1.0
        assert ledger.get_balance("alice", "USD") == 0.0

        # Execute payment on payment date
        ledger.advance_time(payment_date)
        result = compute_deferred_cash_settlement(ledger, dc_unit.symbol, payment_date)
        ledger.execute(result)

        # Cash received, entitlement extinguished
        assert ledger.get_balance("alice", "USD") == 500.0
        assert ledger.get_balance("alice", dc_unit.symbol) == 0.0

    def test_dividend_position_change_after_ex_date(self):
        """Position changes after ex-date don't affect dividend entitlement."""
        ledger = Ledger("test", datetime(2024, 3, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        from ledger import create_stock_unit
        stock = create_stock_unit("AAPL", "Apple Inc.", "treasury", "USD")
        ledger.register_unit(stock)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("treasury", "USD", 1000000.0)
        ledger.set_balance("alice", "AAPL", 1000.0)

        # Ex-date: Alice owns 1000 shares
        ex_date = datetime(2024, 3, 15)
        payment_date = datetime(2024, 3, 29)
        dividend_per_share = 0.50

        # Create DeferredCash for Alice's entitlement (1000 shares × $0.50)
        dc_unit = create_deferred_cash_unit(
            symbol=f"DIV_AAPL_{ex_date.date()}_alice",
            amount=500.0,
            currency="USD",
            payment_date=payment_date,
            payer_wallet="treasury",
            payee_wallet="alice",
        )
        ledger.register_unit(dc_unit)
        ledger.set_balance("alice", dc_unit.symbol, 1)

        # Alice sells all shares to Bob after ex-date
        ledger.advance_time(datetime(2024, 3, 16))
        ledger.set_balance("alice", "AAPL", 0.0)  # Alice no longer has stock
        ledger.set_balance("bob", "AAPL", 1000.0)

        # Alice has no stock, but still has dividend entitlement
        assert ledger.get_balance("alice", "AAPL") == 0.0
        assert ledger.get_balance("bob", "AAPL") == 1000.0
        assert ledger.get_balance("alice", dc_unit.symbol) == 1.0

        # Payment date: Alice still receives dividend
        ledger.advance_time(payment_date)
        result = compute_deferred_cash_settlement(ledger, dc_unit.symbol, payment_date)
        ledger.execute(result)

        # Alice receives full dividend despite selling shares
        assert ledger.get_balance("alice", "USD") == 500.0
        assert ledger.get_balance("bob", "USD") == 0.0  # Bob gets nothing
