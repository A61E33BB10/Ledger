"""
test_core_types.py - Unit tests for core data structures

Tests:
- Move: creation, validation, immutability, edge cases
- Transaction: creation, validation, state_deltas
- ContractResult: creation, is_empty
- StateDelta: creation, immutability
- Unit: rounding, factories
"""

import pytest
import math
from datetime import datetime
from ledger import (
    Move, Transaction, ContractResult, Unit, StateDelta,
    cash,
)


class TestMoveCreation:
    """Tests for Move creation and validation."""

    def test_create_valid_move(self):
        """Valid move creation with all fields."""
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        assert move.source == "alice"
        assert move.dest == "bob"
        assert move.unit == "USD"
        assert move.quantity == 100.0
        assert move.contract_id == "tx_001"
        assert move.metadata is None

    def test_move_with_metadata(self):
        """Move can carry arbitrary metadata."""
        metadata = {"note": "payment", "reference": "INV-123"}
        move = Move("alice", "bob", "USD", 100.0, "tx_001", metadata)
        assert move.metadata == metadata

    def test_move_large_quantity(self):
        """Move handles large quantities."""
        move = Move("alice", "bob", "USD", 1_000_000_000.0, "tx_001")
        assert move.quantity == 1_000_000_000.0

    def test_move_small_quantity(self):
        """Move handles small quantities above epsilon."""
        move = Move("alice", "bob", "USD", 0.0001, "tx_001")
        assert move.quantity == 0.0001

    def test_move_fractional_quantity(self):
        """Move handles fractional quantities."""
        move = Move("alice", "bob", "AAPL", 10.5, "tx_001")
        assert move.quantity == 10.5


class TestMoveValidation:
    """Tests for Move input validation."""

    def test_move_zero_quantity_raises(self):
        """Zero quantity is rejected."""
        with pytest.raises(ValueError, match="quantity is effectively zero"):
            Move("alice", "bob", "USD", 0.0, "tx_001")

    def test_move_near_zero_quantity_allowed(self):
        """Very small quantities near zero are allowed if above epsilon."""
        # The epsilon check in Move allows very small quantities
        move = Move("alice", "bob", "USD", 1e-12, "tx_001")
        assert move.quantity == 1e-12

    def test_move_same_source_dest_raises(self):
        """Source and dest must differ."""
        with pytest.raises(ValueError, match="Source and dest must be different"):
            Move("alice", "alice", "USD", 100.0, "tx_001")

    def test_move_nan_quantity_raises(self):
        """NaN quantity is rejected."""
        with pytest.raises(ValueError, match="finite"):
            Move("alice", "bob", "USD", float('nan'), "tx_001")

    def test_move_inf_quantity_raises(self):
        """Infinite quantity is rejected."""
        with pytest.raises(ValueError, match="finite"):
            Move("alice", "bob", "USD", float('inf'), "tx_001")

    def test_move_neg_inf_quantity_raises(self):
        """Negative infinite quantity is rejected."""
        with pytest.raises(ValueError, match="finite"):
            Move("alice", "bob", "USD", float('-inf'), "tx_001")

    def test_move_negative_quantity_allowed(self):
        """Negative quantities are allowed (for reversals)."""
        move = Move("alice", "bob", "USD", -100.0, "tx_001")
        assert move.quantity == -100.0


class TestMoveImmutability:
    """Tests for Move immutability (frozen=True)."""

    def test_move_is_frozen(self):
        """Move attributes cannot be modified."""
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        with pytest.raises(AttributeError):
            move.quantity = 200.0

    def test_move_source_frozen(self):
        """Move source cannot be modified."""
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        with pytest.raises(AttributeError):
            move.source = "charlie"

    def test_move_hashable(self):
        """Frozen Move is hashable."""
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        # Should not raise
        hash(move)

    def test_move_equality(self):
        """Two identical moves are equal."""
        move1 = Move("alice", "bob", "USD", 100.0, "tx_001")
        move2 = Move("alice", "bob", "USD", 100.0, "tx_001")
        assert move1 == move2


class TestMoveRepr:
    """Tests for Move string representation."""

    def test_move_repr_contains_fields(self):
        """Repr includes key fields."""
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        repr_str = repr(move)
        assert "alice" in repr_str
        assert "bob" in repr_str
        assert "USD" in repr_str
        assert "100" in repr_str


class TestTransaction:
    """Tests for Transaction dataclass."""

    def test_create_valid_transaction(self):
        """Transaction with single move."""
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        tx = Transaction(
            moves=(move,),
            tx_id="tx_123",
            timestamp=datetime(2025, 1, 1),
            ledger_name="test"
        )
        assert tx.tx_id == "tx_123"
        assert len(tx.moves) == 1
        assert tx.contract_ids == frozenset({"tx_001"})

    def test_transaction_multiple_moves(self):
        """Transaction with multiple moves."""
        moves = (
            Move("alice", "bob", "USD", 100.0, "trade_001"),
            Move("bob", "alice", "AAPL", 10.0, "trade_001"),
        )
        tx = Transaction(
            moves=moves,
            tx_id="tx_123",
            timestamp=datetime(2025, 1, 1),
            ledger_name="test"
        )
        assert len(tx.moves) == 2
        assert tx.contract_ids == frozenset({"trade_001"})

    def test_transaction_multiple_contract_ids(self):
        """Transaction aggregates multiple contract IDs."""
        moves = (
            Move("alice", "bob", "USD", 100.0, "contract_A"),
            Move("bob", "alice", "AAPL", 10.0, "contract_B"),
        )
        tx = Transaction(
            moves=moves,
            tx_id="tx_123",
            timestamp=datetime(2025, 1, 1),
            ledger_name="test"
        )
        assert tx.contract_ids == frozenset({"contract_A", "contract_B"})

    def test_transaction_with_state_deltas(self):
        """Transaction can include state deltas."""
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        delta = StateDelta("AAPL", {"price": 100}, {"price": 105})
        tx = Transaction(
            moves=(move,),
            tx_id="tx_123",
            timestamp=datetime(2025, 1, 1),
            ledger_name="test",
            state_deltas=(delta,)
        )
        assert len(tx.state_deltas) == 1
        assert tx.state_deltas[0].unit == "AAPL"

    def test_transaction_state_only(self):
        """Transaction with only state deltas (no moves) is valid."""
        delta = StateDelta("AAPL", {"settled": False}, {"settled": True})
        tx = Transaction(
            moves=(),
            tx_id="tx_123",
            timestamp=datetime(2025, 1, 1),
            ledger_name="test",
            state_deltas=(delta,)
        )
        assert len(tx.moves) == 0
        assert len(tx.state_deltas) == 1

    def test_transaction_empty_raises(self):
        """Transaction with no moves AND no state_deltas raises."""
        with pytest.raises(ValueError, match="must have moves or state_deltas"):
            Transaction(
                moves=(),
                tx_id="tx_123",
                timestamp=datetime(2025, 1, 1),
                ledger_name="test"
            )

    def test_transaction_is_frozen(self):
        """Transaction attributes cannot be modified."""
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        tx = Transaction(
            moves=(move,),
            tx_id="tx_123",
            timestamp=datetime(2025, 1, 1),
            ledger_name="test"
        )
        with pytest.raises(AttributeError):
            tx.tx_id = "new_id"

    def test_transaction_repr_includes_state_deltas(self):
        """Repr shows state deltas when present."""
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        delta = StateDelta("AAPL", {"old": 1}, {"new": 2})
        tx = Transaction(
            moves=(move,),
            tx_id="tx_123",
            timestamp=datetime(2025, 1, 1),
            ledger_name="test",
            state_deltas=(delta,)
        )
        repr_str = repr(tx)
        assert "State Deltas" in repr_str
        assert "AAPL" in repr_str


class TestContractResult:
    """Tests for ContractResult dataclass."""

    def test_empty_result(self):
        """Empty ContractResult."""
        result = ContractResult()
        assert result.is_empty()
        assert len(result.moves) == 0
        assert len(result.state_updates) == 0

    def test_result_with_moves_only(self):
        """ContractResult with moves but no state updates."""
        moves = [Move("alice", "bob", "USD", 100.0, "tx_001")]
        result = ContractResult(moves=moves)
        assert not result.is_empty()
        assert len(result.moves) == 1
        assert len(result.state_updates) == 0

    def test_result_with_state_updates_only(self):
        """ContractResult with state updates but no moves."""
        result = ContractResult(state_updates={"AAPL": {"settled": True}})
        assert not result.is_empty()
        assert len(result.moves) == 0
        assert result.state_updates["AAPL"]["settled"] is True

    def test_result_with_both(self):
        """ContractResult with moves and state updates."""
        moves = [Move("alice", "bob", "USD", 100.0, "tx_001")]
        result = ContractResult(
            moves=moves,
            state_updates={"AAPL": {"settled": True}}
        )
        assert not result.is_empty()
        assert len(result.moves) == 1
        assert len(result.state_updates) == 1

    def test_result_empty_moves_list(self):
        """ContractResult with empty moves list is empty."""
        result = ContractResult(moves=[])
        assert result.is_empty()

    def test_result_empty_state_dict(self):
        """ContractResult with empty state dict is empty."""
        result = ContractResult(state_updates={})
        assert result.is_empty()


class TestStateDelta:
    """Tests for StateDelta dataclass."""

    def test_create_state_delta(self):
        """Create valid StateDelta."""
        delta = StateDelta(
            unit="AAPL",
            old_state={"settled": False, "price": 100},
            new_state={"settled": True, "price": 150}
        )
        assert delta.unit == "AAPL"
        assert delta.old_state == {"settled": False, "price": 100}
        assert delta.new_state == {"settled": True, "price": 150}

    def test_state_delta_is_frozen(self):
        """StateDelta attributes cannot be modified."""
        delta = StateDelta("AAPL", {}, {})
        with pytest.raises(AttributeError):
            delta.unit = "MSFT"

    def test_state_delta_empty_states(self):
        """StateDelta with empty states is valid."""
        delta = StateDelta("AAPL", {}, {})
        assert delta.old_state == {}
        assert delta.new_state == {}


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
