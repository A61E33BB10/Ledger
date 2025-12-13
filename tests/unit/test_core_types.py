"""
test_core_types.py - Unit tests for core data structures

Tests:
- Move: creation, validation, immutability, edge cases
- Transaction: creation, validation, state_changes
- UnitStateChange: creation, immutability
- Unit: rounding, factories
"""

import pytest
import math
from datetime import datetime
from ledger import (
    Move, Transaction, Unit, UnitStateChange,
    TransactionOrigin, OriginType,
    cash,
)


# Helper for creating test origins
def _test_origin() -> TransactionOrigin:
    return TransactionOrigin(
        origin_type=OriginType.USER_ACTION,
        source_id="test",
    )


class TestMoveCreation:
    """Tests for Move creation and validation."""

    def test_create_valid_move(self):
        """Valid move creation with all fields."""
        move = Move(100.0, "USD", "alice", "bob", "tx_001")
        assert move.source == "alice"
        assert move.dest == "bob"
        assert move.unit_symbol == "USD"
        assert move.quantity == 100.0
        assert move.contract_id == "tx_001"
        assert move.metadata is None

    def test_move_with_metadata(self):
        """Move can carry arbitrary metadata."""
        metadata = {"note": "payment", "reference": "INV-123"}
        move = Move(100.0, "USD", "alice", "bob", "tx_001", metadata)
        assert move.metadata == metadata

    def test_move_large_quantity(self):
        """Move handles large quantities."""
        move = Move(1_000_000_000.0, "USD", "alice", "bob", "tx_001")
        assert move.quantity == 1_000_000_000.0

    def test_move_small_quantity(self):
        """Move handles small quantities above epsilon."""
        move = Move(0.0001, "USD", "alice", "bob", "tx_001")
        assert move.quantity == 0.0001

    def test_move_fractional_quantity(self):
        """Move handles fractional quantities."""
        move = Move(10.5, "AAPL", "alice", "bob", "tx_001")
        assert move.quantity == 10.5


class TestMoveValidation:
    """Tests for Move input validation."""

    def test_move_zero_quantity_raises(self):
        """Zero quantity is rejected."""
        with pytest.raises(ValueError, match="quantity is effectively zero"):
            Move(0.0, "USD", "alice", "bob", "tx_001")

    def test_move_near_zero_quantity_allowed(self):
        """Very small quantities near zero are allowed if above epsilon."""
        # The epsilon check in Move allows very small quantities
        move = Move(1e-12, "USD", "alice", "bob", "tx_001")
        assert move.quantity == 1e-12

    def test_move_same_source_dest_raises(self):
        """Source and dest must differ."""
        with pytest.raises(ValueError, match="Source and dest must be different"):
            Move(100.0, "USD", "alice", "alice", "tx_001")

    def test_move_nan_quantity_raises(self):
        """NaN quantity is rejected."""
        with pytest.raises(ValueError, match="finite"):
            Move(float('nan'), "USD", "alice", "bob", "tx_001")

    def test_move_inf_quantity_raises(self):
        """Infinite quantity is rejected."""
        with pytest.raises(ValueError, match="finite"):
            Move(float('inf'), "USD", "alice", "bob", "tx_001")

    def test_move_neg_inf_quantity_raises(self):
        """Negative infinite quantity is rejected."""
        with pytest.raises(ValueError, match="finite"):
            Move(float('-inf'), "USD", "alice", "bob", "tx_001")

    def test_move_negative_quantity_allowed(self):
        """Negative quantities are allowed (for reversals)."""
        move = Move(-100.0, "USD", "alice", "bob", "tx_001")
        assert move.quantity == -100.0


class TestMoveImmutability:
    """Tests for Move immutability (frozen=True)."""

    def test_move_is_frozen(self):
        """Move attributes cannot be modified."""
        move = Move(100.0, "USD", "alice", "bob", "tx_001")
        with pytest.raises(AttributeError):
            move.quantity = 200.0

    def test_move_source_frozen(self):
        """Move source cannot be modified."""
        move = Move(100.0, "USD", "alice", "bob", "tx_001")
        with pytest.raises(AttributeError):
            move.source = "charlie"

    def test_move_hashable(self):
        """Frozen Move is hashable."""
        move = Move(100.0, "USD", "alice", "bob", "tx_001")
        # Should not raise
        hash(move)

    def test_move_equality(self):
        """Two identical moves are equal."""
        move1 = Move(100.0, "USD", "alice", "bob", "tx_001")
        move2 = Move(100.0, "USD", "alice", "bob", "tx_001")
        assert move1 == move2


class TestMoveRepr:
    """Tests for Move string representation."""

    def test_move_repr_contains_fields(self):
        """Repr includes key fields."""
        move = Move(100.0, "USD", "alice", "bob", "tx_001")
        repr_str = repr(move)
        assert "alice" in repr_str
        assert "bob" in repr_str
        assert "USD" in repr_str
        assert "100" in repr_str


class TestTransaction:
    """Tests for Transaction dataclass."""

    def test_create_valid_transaction(self):
        """Transaction with single move."""
        move = Move(100.0, "USD", "alice", "bob", "tx_001")
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
        """Transaction with multiple moves."""
        moves = (
            Move(100.0, "USD", "alice", "bob", "trade_001"),
            Move(10.0, "AAPL", "bob", "alice", "trade_001"),
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

    def test_transaction_multiple_contract_ids(self):
        """Transaction aggregates multiple contract IDs."""
        moves = (
            Move(100.0, "USD", "alice", "bob", "contract_A"),
            Move(10.0, "AAPL", "bob", "alice", "contract_B"),
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
        assert tx.contract_ids == frozenset({"contract_A", "contract_B"})

    def test_transaction_with_state_changes(self):
        """Transaction can include state deltas."""
        move = Move(100.0, "USD", "alice", "bob", "tx_001")
        delta = UnitStateChange("AAPL", {"price": 100}, {"price": 105})
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
        """Transaction with only state deltas (no moves) is valid."""
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
        """Transaction with no moves AND no state_changes AND no units_to_create raises."""
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
        """Transaction attributes cannot be modified."""
        move = Move(100.0, "USD", "alice", "bob", "tx_001")
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

    def test_transaction_repr_includes_state_changes(self):
        """Repr shows state deltas when present."""
        move = Move(100.0, "USD", "alice", "bob", "tx_001")
        delta = UnitStateChange("AAPL", {"old": 1}, {"new": 2})
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
        """Create valid UnitStateChange."""
        sc = UnitStateChange(
            unit="AAPL",
            old_state={"settled": False, "price": 100},
            new_state={"settled": True, "price": 150}
        )
        assert sc.unit == "AAPL"
        assert sc.old_state == {"settled": False, "price": 100}
        assert sc.new_state == {"settled": True, "price": 150}

    def test_state_change_is_frozen(self):
        """UnitStateChange attributes cannot be modified."""
        sc = UnitStateChange("AAPL", {}, {})
        with pytest.raises(AttributeError):
            sc.unit = "MSFT"

    def test_state_change_empty_states(self):
        """UnitStateChange with empty states is valid."""
        sc = UnitStateChange("AAPL", {}, {})
        assert sc.old_state == {}
        assert sc.new_state == {}


class TestUnitFactories:
    """Tests for unit factory functions."""

    def test_cash_unit(self):
        """Cash factory creates correct unit."""
        usd = cash("USD", "US Dollar", decimal_places=2)
        assert usd.symbol == "USD"
        assert usd.name == "US Dollar"
        assert usd.unit_type == "CASH"
        assert usd.decimal_places == 2
        # Cash allows negative balances (borrowing)
        assert usd.min_balance == -1_000_000_000.0

    def test_cash_default_decimal_places(self):
        """Cash has default decimal places."""
        usd = cash("USD", "US Dollar")
        assert usd.decimal_places >= 0

    def test_cash_rounding(self):
        """Cash unit rounds correctly."""
        usd = cash("USD", "US Dollar", decimal_places=2)
        assert usd.round(100.456) == 100.46
        assert usd.round(100.454) == 100.45
        # Standard rounding (not banker's rounding)
        assert usd.round(100.445) == 100.44

    def test_cash_rounding_negative(self):
        """Cash unit rounds negative values correctly."""
        usd = cash("USD", "US Dollar", decimal_places=2)
        assert usd.round(-100.456) == -100.46
        assert usd.round(-100.454) == -100.45


class TestUnitRounding:
    """Tests for Unit.round() method."""

    def test_round_no_decimal_places(self):
        """Unit with no decimal places rounds to int."""
        unit = Unit("SHARES", "Shares", "STOCK", None, decimal_places=0)
        assert unit.round(10.6) == 11
        assert unit.round(10.4) == 10

    def test_round_many_decimal_places(self):
        """Unit with many decimal places preserves precision."""
        unit = Unit("PRECISE", "Precise", "STOCK", None, decimal_places=8)
        assert unit.round(0.123456789) == 0.12345679

    def test_round_none_decimal_places(self):
        """Unit with None decimal places doesn't round."""
        unit = Unit("NOROUND", "No Rounding", "STOCK", None, decimal_places=None)
        value = 100.123456789
        assert unit.round(value) == value
