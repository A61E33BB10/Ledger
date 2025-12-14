"""
test_core.py - Unit tests for core data structures

Tests:
- Move: creation, validation, immutability
- Transaction: creation, validation, state_changes
- UnitStateChange: creation, immutability
- Transfer rules: bilateral transfers, rule violations
- Unit factories: cash
"""

import pytest
from datetime import datetime
from decimal import Decimal
from ledger import (
    Move, Transaction, PendingTransaction, Unit, UnitStateChange,
    TransactionOrigin, OriginType,
    cash,
    bilateral_transfer_rule,
    TransferRuleViolation,
)
from .fake_view import FakeView


# Helper to create a minimal valid origin
def _test_origin() -> TransactionOrigin:
    return TransactionOrigin(
        origin_type=OriginType.USER_ACTION,
        source_id="test",
    )


class TestMove:
    """Tests for Move dataclass."""

    def test_create_valid_move(self):
        move = Move(Decimal("100.0"), "USD", "alice", "bob", "tx_001")
        assert move.source == "alice"
        assert move.dest == "bob"
        assert move.unit_symbol == "USD"
        assert move.quantity == Decimal("100.0")
        assert move.contract_id == "tx_001"
        assert move.metadata is None

    def test_move_with_metadata(self):
        move = Move(Decimal("100.0"), "USD", "alice", "bob", "tx_001", {"note": "payment"})
        assert move.metadata == {"note": "payment"}

    def test_move_zero_quantity_raises(self):
        with pytest.raises(ValueError, match="quantity is effectively zero"):
            Move(Decimal("0.0"), "USD", "alice", "bob", "tx_001")

    def test_move_same_source_dest_raises(self):
        with pytest.raises(ValueError, match="Source and dest must be different"):
            Move(Decimal("100.0"), "USD", "alice", "alice", "tx_001")

    def test_move_is_frozen(self):
        move = Move(Decimal("100.0"), "USD", "alice", "bob", "tx_001")
        with pytest.raises(AttributeError):
            move.quantity = 200.0

    def test_move_negative_quantity_allowed(self):
        # Negative quantities are allowed (for reversals, etc.)
        move = Move(Decimal("-100.0"), "USD", "alice", "bob", "tx_001")
        assert move.quantity == Decimal("-100.0")

    def test_move_repr(self):
        move = Move(Decimal("100.0"), "USD", "alice", "bob", "tx_001")
        assert "alice" in repr(move)
        assert "bob" in repr(move)
        assert "100" in repr(move)
        assert "USD" in repr(move)


class TestTransaction:
    """Tests for Transaction dataclass."""

    def test_create_valid_transaction(self):
        move = Move(Decimal("100.0"), "USD", "alice", "bob", "tx_001")
        tx = Transaction(
            moves=(move,),
            state_changes=(),
            origin=_test_origin(),
            timestamp=datetime(2025, 1, 1),
            intent_id="intent_123",
            exec_id="exec_123",
            ledger_name="test",
            execution_time=datetime(2025, 1, 1),
            sequence_number=0,
        )
        assert tx.exec_id == "exec_123"
        assert tx.intent_id == "intent_123"
        assert len(tx.moves) == 1
        assert tx.contract_ids == frozenset({"tx_001"})

    def test_transaction_multiple_moves(self):
        moves = (
            Move(Decimal("100.0"), "USD", "alice", "bob", "trade_001"),
            Move(Decimal("10.0"), "AAPL", "bob", "alice", "trade_001"),
        )
        tx = Transaction(
            moves=moves,
            state_changes=(),
            origin=_test_origin(),
            timestamp=datetime(2025, 1, 1),
            intent_id="intent_123",
            exec_id="exec_123",
            ledger_name="test",
            execution_time=datetime(2025, 1, 1),
            sequence_number=0,
        )
        assert len(tx.moves) == 2
        assert tx.contract_ids == frozenset({"trade_001"})

    def test_transaction_with_state_changes(self):
        move = Move(Decimal("100.0"), "USD", "alice", "bob", "tx_001")
        delta = UnitStateChange("AAPL", {"price": Decimal("100")}, {"price": Decimal("105")})
        tx = Transaction(
            moves=(move,),
            state_changes=(delta,),
            origin=_test_origin(),
            timestamp=datetime(2025, 1, 1),
            intent_id="intent_123",
            exec_id="exec_123",
            ledger_name="test",
            execution_time=datetime(2025, 1, 1),
            sequence_number=0,
        )
        assert len(tx.state_changes) == 1
        assert tx.state_changes[0].unit == "AAPL"

    def test_transaction_state_only(self):
        delta = UnitStateChange("AAPL", {"settled": False}, {"settled": True})
        tx = Transaction(
            moves=(),
            state_changes=(delta,),
            origin=_test_origin(),
            timestamp=datetime(2025, 1, 1),
            intent_id="intent_123",
            exec_id="exec_123",
            ledger_name="test",
            execution_time=datetime(2025, 1, 1),
            sequence_number=0,
        )
        assert len(tx.moves) == 0
        assert len(tx.state_changes) == 1

    def test_transaction_empty_raises(self):
        with pytest.raises(ValueError, match="must have moves, state_changes, or units_to_create"):
            Transaction(
                moves=(),
                state_changes=(),
                origin=_test_origin(),
                timestamp=datetime(2025, 1, 1),
                intent_id="intent_123",
                exec_id="exec_123",
                ledger_name="test",
                execution_time=datetime(2025, 1, 1),
                sequence_number=0,
            )

    def test_transaction_is_frozen(self):
        move = Move(Decimal("100.0"), "USD", "alice", "bob", "tx_001")
        tx = Transaction(
            moves=(move,),
            state_changes=(),
            origin=_test_origin(),
            timestamp=datetime(2025, 1, 1),
            intent_id="intent_123",
            exec_id="exec_123",
            ledger_name="test",
            execution_time=datetime(2025, 1, 1),
            sequence_number=0,
        )
        with pytest.raises(AttributeError):
            tx.exec_id = "new_id"


class TestPendingTransaction:
    """Tests for PendingTransaction dataclass."""

    def test_create_valid_pending_transaction(self):
        move = Move(Decimal("100.0"), "USD", "alice", "bob", "tx_001")
        pending = PendingTransaction(
            moves=(move,),
            state_changes=(),
            origin=_test_origin(),
            timestamp=datetime(2025, 1, 1),
        )
        assert len(pending.moves) == 1
        assert pending.intent_id  # Should be auto-computed
        assert not pending.is_empty()

    def test_pending_transaction_auto_intent_id(self):
        """Same content produces same intent_id."""
        move = Move(Decimal("100.0"), "USD", "alice", "bob", "tx_001")
        p1 = PendingTransaction(
            moves=(move,),
            state_changes=(),
            origin=_test_origin(),
            timestamp=datetime(2025, 1, 1),
        )
        p2 = PendingTransaction(
            moves=(move,),
            state_changes=(),
            origin=_test_origin(),
            timestamp=datetime(2025, 1, 2),  # Different timestamp
        )
        # Same content (moves, origin) = same intent_id
        assert p1.intent_id == p2.intent_id

    def test_pending_transaction_is_empty(self):
        pending = PendingTransaction(
            moves=(),
            state_changes=(),
            origin=_test_origin(),
            timestamp=datetime(2025, 1, 1),
        )
        assert pending.is_empty()

class TestTransactionRepr:
    """Tests for Transaction representation."""

    def test_transaction_repr_includes_state_changes(self):
        move = Move(Decimal("100.0"), "USD", "alice", "bob", "tx_001")
        delta = UnitStateChange("AAPL", {"old": Decimal("1")}, {"new": Decimal("2")})
        tx = Transaction(
            moves=(move,),
            state_changes=(delta,),
            origin=_test_origin(),
            timestamp=datetime(2025, 1, 1),
            intent_id="intent_123",
            exec_id="exec_123",
            ledger_name="test",
            execution_time=datetime(2025, 1, 1),
            sequence_number=0,
        )
        repr_str = repr(tx)
        assert "State Changes" in repr_str
        assert "AAPL" in repr_str


class TestUnitStateChange:
    """Tests for UnitStateChange dataclass."""

    def test_create_state_change(self):
        sc = UnitStateChange(
            unit="AAPL",
            old_state={"settled": False},
            new_state={"settled": True}
        )
        assert sc.unit == "AAPL"
        assert sc.old_state == {"settled": False}
        assert sc.new_state == {"settled": True}

    def test_state_change_is_frozen(self):
        sc = UnitStateChange("AAPL", {}, {})
        with pytest.raises(AttributeError):
            sc.unit = "MSFT"


class TestUnitFactories:
    """Tests for cash and stock factory functions."""

    def test_cash_unit(self):
        usd = cash("USD", "US Dollar", decimal_places=2)
        assert usd.symbol == "USD"
        assert usd.name == "US Dollar"
        assert usd.unit_type == "CASH"
        assert usd.decimal_places == Decimal("2")
        assert usd.min_balance == -1_000_000_000.0

    def test_cash_rounding(self):
        usd = cash("USD", "US Dollar", decimal_places=2)
        assert usd.round(100.456) == Decimal("100.46")
        assert usd.round(100.444) == Decimal("100.44")

class TestTransferRules:
    """Tests for transfer rules."""

    def test_bilateral_rule_allows_counterparties(self):
        view = FakeView(
            balances={"alice": {"OPT": Decimal("1")}, "bob": {"OPT": -1}},
            states={"OPT": {"long_wallet": "alice", "short_wallet": "bob"}}
        )
        move = Move(Decimal("1.0"), "OPT", "alice", "bob", "close")
        # Should not raise
        bilateral_transfer_rule(view, move)

    def test_bilateral_rule_rejects_third_party(self):
        view = FakeView(
            balances={"alice": {"OPT": Decimal("1")}, "bob": {"OPT": -1}},
            states={"OPT": {"long_wallet": "alice", "short_wallet": "bob"}}
        )
        move = Move(Decimal("1.0"), "OPT", "alice", "charlie", "illegal")
        with pytest.raises(TransferRuleViolation):
            bilateral_transfer_rule(view, move)

