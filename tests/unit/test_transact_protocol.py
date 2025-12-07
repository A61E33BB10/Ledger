"""
Tests for the transact() protocol across all unit types.

This module tests the unified transact() interface that provides a consistent
way to trigger lifecycle events across stocks, options, and forwards.

Test coverage:
- Stock transact() with DIVIDEND and SPLIT events
- Option transact() with EXERCISE, EXPIRY, and ASSIGNMENT events
- Forward transact() with DELIVERY and EARLY_TERMINATION events
- Unknown event types return empty results
- Event-specific parameter handling
"""

import pytest
from datetime import datetime, timedelta

from ledger import (
    Ledger,
    cash,
    create_stock_unit,
    create_option_unit,
    create_forward_unit,
    stock_transact,
    option_transact,
    forward_transact,
)


# ============================================================================
# Stock transact() Tests
# ============================================================================

class TestStockTransact:
    """Tests for stock_transact() function."""

    @pytest.fixture
    def stock_ledger(self):
        """Create a ledger with a stock unit."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.set_balance("treasury", "USD", 1_000_000)

        schedule = [
            (datetime(2024, 3, 15), 0.50),
            (datetime(2024, 6, 15), 0.50),
        ]
        stock = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            dividend_schedule=schedule,
        )
        ledger.register_unit(stock)

        ledger.set_balance("alice", "AAPL", 1000)
        ledger.set_balance("bob", "AAPL", 500)

        return ledger

    def test_dividend_event(self, stock_ledger):
        """DIVIDEND event should trigger dividend payment."""
        ledger = stock_ledger
        ledger.advance_time(datetime(2024, 3, 15))

        result = stock_transact(
            ledger, "AAPL", "DIVIDEND", datetime(2024, 3, 15)
        )

        assert not result.is_empty()
        assert len(result.moves) == 2  # Alice and Bob

        # Apply the result
        ledger.execute_contract(result)

        # Verify payments
        assert ledger.get_balance("alice", "USD") == 500.0
        assert ledger.get_balance("bob", "USD") == 250.0

    def test_split_event(self, stock_ledger):
        """SPLIT event should record the split in state."""
        ledger = stock_ledger

        result = stock_transact(
            ledger, "AAPL", "SPLIT", datetime(2024, 2, 1), ratio=2.0
        )

        assert not result.is_empty()
        assert "AAPL" in result.state_updates

        # Apply the result
        ledger.execute_contract(result)

        # Verify split was recorded
        state = ledger.get_unit_state("AAPL")
        assert state['last_split_ratio'] == 2.0
        assert state['last_split_date'] == datetime(2024, 2, 1)

    def test_unknown_event_type(self, stock_ledger):
        """Unknown event types should return empty result."""
        ledger = stock_ledger

        result = stock_transact(
            ledger, "AAPL", "UNKNOWN_EVENT", datetime(2024, 2, 1)
        )

        assert result.is_empty()

    def test_dividend_before_payment_date(self, stock_ledger):
        """DIVIDEND event before payment date should return empty result."""
        ledger = stock_ledger

        result = stock_transact(
            ledger, "AAPL", "DIVIDEND", datetime(2024, 3, 14)
        )

        assert result.is_empty()

    def test_multiple_dividends_via_transact(self, stock_ledger):
        """Multiple DIVIDEND events should process each payment."""
        ledger = stock_ledger

        # First dividend
        ledger.advance_time(datetime(2024, 3, 15))
        r1 = stock_transact(ledger, "AAPL", "DIVIDEND", datetime(2024, 3, 15))
        ledger.execute_contract(r1)

        assert ledger.get_balance("alice", "USD") == 500.0

        # Second dividend
        ledger.advance_time(datetime(2024, 6, 15))
        r2 = stock_transact(ledger, "AAPL", "DIVIDEND", datetime(2024, 6, 15))
        ledger.execute_contract(r2)

        assert ledger.get_balance("alice", "USD") == 1000.0


# ============================================================================
# Option transact() Tests
# ============================================================================

class TestOptionTransact:
    """Tests for option_transact() function."""

    @pytest.fixture
    def option_ledger(self):
        """Create a ledger with an option unit."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Create stock for underlying
        stock = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
        )
        ledger.register_unit(stock)

        ledger.register_wallet("alice")  # Long
        ledger.register_wallet("bob")    # Short

        # Fund wallets
        ledger.set_balance("alice", "USD", 100_000)
        ledger.set_balance("bob", "AAPL", 1000)

        # Create call option
        option = create_option_unit(
            symbol="AAPL_CALL_150",
            name="AAPL Call 150",
            underlying="AAPL",
            strike=150.0,
            maturity=datetime(2024, 12, 20),
            option_type="call",
            quantity=100.0,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        ledger.register_unit(option)

        # Give alice the option position
        ledger.set_balance("alice", "AAPL_CALL_150", 1.0)
        ledger.set_balance("bob", "AAPL_CALL_150", -1.0)

        return ledger

    def test_exercise_event(self, option_ledger):
        """EXERCISE event should settle option early."""
        ledger = option_ledger

        result = option_transact(
            ledger, "AAPL_CALL_150", "EXERCISE",
            datetime(2024, 6, 1),
            settlement_price=160.0
        )

        assert not result.is_empty()
        assert len(result.moves) == 3  # Cash, delivery, close

        ledger.execute_contract(result)

        # Verify option is settled
        state = ledger.get_unit_state("AAPL_CALL_150")
        assert state['settled'] is True
        assert state['exercised'] is True

    def test_expiry_event(self, option_ledger):
        """EXPIRY event should settle option at maturity."""
        ledger = option_ledger
        ledger.advance_time(datetime(2024, 12, 20))

        result = option_transact(
            ledger, "AAPL_CALL_150", "EXPIRY",
            datetime(2024, 12, 20),
            settlement_price=160.0
        )

        assert not result.is_empty()

        ledger.execute_contract(result)

        # Verify settlement
        state = ledger.get_unit_state("AAPL_CALL_150")
        assert state['settled'] is True
        assert state['settlement_price'] == 160.0

    def test_assignment_event(self, option_ledger):
        """ASSIGNMENT event should force settlement."""
        ledger = option_ledger

        result = option_transact(
            ledger, "AAPL_CALL_150", "ASSIGNMENT",
            datetime(2024, 6, 1),
            settlement_price=160.0
        )

        assert not result.is_empty()

        ledger.execute_contract(result)

        state = ledger.get_unit_state("AAPL_CALL_150")
        assert state['settled'] is True

    def test_missing_settlement_price(self, option_ledger):
        """Option events without settlement_price should return empty result."""
        ledger = option_ledger

        result = option_transact(
            ledger, "AAPL_CALL_150", "EXERCISE",
            datetime(2024, 6, 1)
            # No settlement_price provided
        )

        assert result.is_empty()

    def test_unknown_option_event(self, option_ledger):
        """Unknown event types should return empty result."""
        ledger = option_ledger

        result = option_transact(
            ledger, "AAPL_CALL_150", "UNKNOWN",
            datetime(2024, 6, 1),
            settlement_price=160.0
        )

        assert result.is_empty()

    def test_otm_expiry(self, option_ledger):
        """OTM option expiry should close without delivery."""
        ledger = option_ledger
        ledger.advance_time(datetime(2024, 12, 20))

        # Option expires OTM
        result = option_transact(
            ledger, "AAPL_CALL_150", "EXPIRY",
            datetime(2024, 12, 20),
            settlement_price=140.0  # Below strike
        )

        assert not result.is_empty()

        ledger.execute_contract(result)

        state = ledger.get_unit_state("AAPL_CALL_150")
        assert state['settled'] is True
        assert state['exercised'] is False  # Not exercised (OTM)


# ============================================================================
# Forward transact() Tests
# ============================================================================

class TestForwardTransact:
    """Tests for forward_transact() function."""

    @pytest.fixture
    def forward_ledger(self):
        """Create a ledger with a forward contract."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Create commodity
        from ledger.core import Unit
        oil = Unit(
            symbol="OIL",
            name="Crude Oil",
            unit_type="COMMODITY",
            min_balance=0.0,
        )
        ledger.register_unit(oil)

        ledger.register_wallet("alice")  # Long
        ledger.register_wallet("bob")    # Short

        # Fund wallets
        ledger.set_balance("alice", "USD", 500_000)
        ledger.set_balance("bob", "OIL", 10_000)

        # Create forward contract
        forward = create_forward_unit(
            symbol="OIL_FWD_MAR25",
            name="Oil Forward March 2025",
            underlying="OIL",
            forward_price=80.0,
            delivery_date=datetime(2025, 3, 15),
            quantity=100.0,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        ledger.register_unit(forward)

        # Give alice the long position
        ledger.set_balance("alice", "OIL_FWD_MAR25", 1.0)
        ledger.set_balance("bob", "OIL_FWD_MAR25", -1.0)

        return ledger

    def test_delivery_event(self, forward_ledger):
        """DELIVERY event should settle forward at maturity."""
        ledger = forward_ledger
        ledger.advance_time(datetime(2025, 3, 15))

        result = forward_transact(
            ledger, "OIL_FWD_MAR25", "DELIVERY",
            datetime(2025, 3, 15)
        )

        assert not result.is_empty()
        assert len(result.moves) == 3  # Cash, delivery, close

        ledger.execute_contract(result)

        # Verify settlement
        state = ledger.get_unit_state("OIL_FWD_MAR25")
        assert state['settled'] is True

        # Verify physical delivery occurred
        assert ledger.get_balance("alice", "OIL") == 100.0
        assert ledger.get_balance("bob", "OIL") == 9_900.0

    def test_early_termination_event(self, forward_ledger):
        """EARLY_TERMINATION event should settle forward before maturity."""
        ledger = forward_ledger
        ledger.advance_time(datetime(2025, 1, 15))

        result = forward_transact(
            ledger, "OIL_FWD_MAR25", "EARLY_TERMINATION",
            datetime(2025, 1, 15)
        )

        assert not result.is_empty()

        ledger.execute_contract(result)

        state = ledger.get_unit_state("OIL_FWD_MAR25")
        assert state['settled'] is True

    def test_delivery_before_maturity(self, forward_ledger):
        """DELIVERY event before maturity should return empty result."""
        ledger = forward_ledger
        ledger.advance_time(datetime(2025, 2, 1))

        result = forward_transact(
            ledger, "OIL_FWD_MAR25", "DELIVERY",
            datetime(2025, 2, 1)
        )

        assert result.is_empty()

    def test_unknown_forward_event(self, forward_ledger):
        """Unknown event types should return empty result."""
        ledger = forward_ledger

        result = forward_transact(
            ledger, "OIL_FWD_MAR25", "UNKNOWN",
            datetime(2025, 3, 15)
        )

        assert result.is_empty()


# ============================================================================
# Cross-Instrument Tests
# ============================================================================

class TestTransactProtocolConsistency:
    """Tests for consistency across all transact() implementations."""

    def test_all_transact_functions_have_same_signature(self):
        """All transact() functions should have consistent signatures."""
        import inspect

        stock_sig = inspect.signature(stock_transact)
        option_sig = inspect.signature(option_transact)
        forward_sig = inspect.signature(forward_transact)

        # All should have: view, symbol, event_type, event_date, **kwargs
        assert len(stock_sig.parameters) == 5
        assert len(option_sig.parameters) == 5
        assert len(forward_sig.parameters) == 5

        # Check parameter names
        stock_params = list(stock_sig.parameters.keys())
        option_params = list(option_sig.parameters.keys())
        forward_params = list(forward_sig.parameters.keys())

        assert stock_params == option_params == forward_params

    def test_empty_result_for_unknown_events(self):
        """All transact() implementations should return empty for unknown events."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")

        # Stock
        stock = create_stock_unit("TEST", "Test", "treasury", "USD")
        ledger.register_unit(stock)

        result = stock_transact(ledger, "TEST", "BOGUS_EVENT", datetime(2024, 1, 1))
        assert result.is_empty()

    def test_transact_does_not_modify_ledger_directly(self):
        """transact() should return ContractResult, not modify ledger."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")

        ledger.set_balance("treasury", "USD", 1_000_000)

        schedule = [(datetime(2024, 3, 15), 1.00)]
        stock = create_stock_unit("TEST", "Test", "treasury", "USD", schedule)
        ledger.register_unit(stock)

        ledger.set_balance("alice", "TEST", 100)
        ledger.advance_time(datetime(2024, 3, 15))

        # Call transact but don't execute result
        result = stock_transact(ledger, "TEST", "DIVIDEND", datetime(2024, 3, 15))

        # Ledger should not be modified
        assert ledger.get_balance("alice", "USD") == 0.0

        # Only after execute_contract should it change
        ledger.execute_contract(result)
        assert ledger.get_balance("alice", "USD") == 100.0


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestTransactEdgeCases:
    """Tests for edge cases in the transact() protocol."""

    def test_stock_split_with_invalid_ratio(self):
        """Stock split with invalid ratio should raise ValueError."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")

        stock = create_stock_unit("TEST", "Test", "treasury", "USD")
        ledger.register_unit(stock)

        with pytest.raises(ValueError, match="Split ratio must be positive"):
            stock_transact(ledger, "TEST", "SPLIT", datetime(2024, 1, 1), ratio=-1.0)

    def test_option_exercise_with_invalid_price(self):
        """Option exercise with invalid price should raise ValueError."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))

        stock = create_stock_unit("AAPL", "Apple", "treasury", "USD")
        ledger.register_unit(stock)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        option = create_option_unit(
            symbol="OPT",
            name="Option",
            underlying="AAPL",
            strike=100.0,
            maturity=datetime(2024, 12, 20),
            option_type="call",
            quantity=100.0,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        ledger.register_unit(option)

        ledger.set_balance("alice", "OPT", 1.0)
        ledger.set_balance("bob", "OPT", -1.0)

        with pytest.raises(ValueError, match="settlement_price must be positive"):
            option_transact(
                ledger, "OPT", "EXERCISE",
                datetime(2024, 6, 1),
                settlement_price=-100.0
            )
