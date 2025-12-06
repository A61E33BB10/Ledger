"""
test_core.py - Unit tests for core data structures

Tests:
- Move: creation, validation, immutability
- Transaction: creation, validation, state_deltas
- ContractResult: creation, is_empty
- StateDelta: creation, immutability
- Transfer rules: bilateral transfers, rule violations
- Unit factories: cash
"""

import pytest
from datetime import datetime
from ledger import (
    Move, Transaction, ContractResult, Unit, StateDelta,
    cash,
    bilateral_transfer_rule,
    TransferRuleViolation,
)
from .fake_view import FakeView


class TestMove:
    """Tests for Move dataclass."""

    def test_create_valid_move(self):
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        assert move.source == "alice"
        assert move.dest == "bob"
        assert move.unit == "USD"
        assert move.quantity == 100.0
        assert move.contract_id == "tx_001"
        assert move.metadata is None

    def test_move_with_metadata(self):
        move = Move("alice", "bob", "USD", 100.0, "tx_001", {"note": "payment"})
        assert move.metadata == {"note": "payment"}

    def test_move_zero_quantity_raises(self):
        with pytest.raises(ValueError, match="quantity is effectively zero"):
            Move("alice", "bob", "USD", 0.0, "tx_001")

    def test_move_same_source_dest_raises(self):
        with pytest.raises(ValueError, match="Source and dest must be different"):
            Move("alice", "alice", "USD", 100.0, "tx_001")

    def test_move_is_frozen(self):
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        with pytest.raises(AttributeError):
            move.quantity = 200.0

    def test_move_negative_quantity_allowed(self):
        # Negative quantities are allowed (for reversals, etc.)
        move = Move("alice", "bob", "USD", -100.0, "tx_001")
        assert move.quantity == -100.0

    def test_move_repr(self):
        move = Move("alice", "bob", "USD", 100.0, "tx_001")
        assert "alice" in repr(move)
        assert "bob" in repr(move)
        assert "100" in repr(move)
        assert "USD" in repr(move)


class TestTransaction:
    """Tests for Transaction dataclass."""

    def test_create_valid_transaction(self):
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

    def test_transaction_with_state_deltas(self):
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
        with pytest.raises(ValueError, match="must have moves or state_deltas"):
            Transaction(
                moves=(),
                tx_id="tx_123",
                timestamp=datetime(2025, 1, 1),
                ledger_name="test"
            )

    def test_transaction_is_frozen(self):
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
        result = ContractResult()
        assert result.is_empty()
        assert len(result.moves) == 0
        assert len(result.state_updates) == 0

    def test_result_with_moves(self):
        moves = [Move("alice", "bob", "USD", 100.0, "tx_001")]
        result = ContractResult(moves=moves)
        assert not result.is_empty()
        assert len(result.moves) == 1

    def test_result_with_state_updates(self):
        result = ContractResult(state_updates={"AAPL": {"settled": True}})
        assert not result.is_empty()
        assert result.state_updates["AAPL"]["settled"] is True

    def test_result_with_both(self):
        moves = [Move("alice", "bob", "USD", 100.0, "tx_001")]
        result = ContractResult(
            moves=moves,
            state_updates={"AAPL": {"settled": True}}
        )
        assert not result.is_empty()


class TestStateDelta:
    """Tests for StateDelta dataclass."""

    def test_create_state_delta(self):
        delta = StateDelta(
            unit="AAPL",
            old_state={"settled": False},
            new_state={"settled": True}
        )
        assert delta.unit == "AAPL"
        assert delta.old_state == {"settled": False}
        assert delta.new_state == {"settled": True}

    def test_state_delta_is_frozen(self):
        delta = StateDelta("AAPL", {}, {})
        with pytest.raises(AttributeError):
            delta.unit = "MSFT"


class TestUnitFactories:
    """Tests for cash and stock factory functions."""

    def test_cash_unit(self):
        usd = cash("USD", "US Dollar", decimal_places=2)
        assert usd.symbol == "USD"
        assert usd.name == "US Dollar"
        assert usd.unit_type == "CASH"
        assert usd.decimal_places == 2
        assert usd.min_balance == -1_000_000_000.0

    def test_cash_rounding(self):
        usd = cash("USD", "US Dollar", decimal_places=2)
        assert usd.round(100.456) == 100.46
        assert usd.round(100.444) == 100.44

class TestTransferRules:
    """Tests for transfer rules."""

    def test_bilateral_rule_allows_counterparties(self):
        view = FakeView(
            balances={"alice": {"OPT": 1}, "bob": {"OPT": -1}},
            states={"OPT": {"long_wallet": "alice", "short_wallet": "bob"}}
        )
        move = Move("alice", "bob", "OPT", 1.0, "close")
        # Should not raise
        bilateral_transfer_rule(view, move)

    def test_bilateral_rule_rejects_third_party(self):
        view = FakeView(
            balances={"alice": {"OPT": 1}, "bob": {"OPT": -1}},
            states={"OPT": {"long_wallet": "alice", "short_wallet": "bob"}}
        )
        move = Move("alice", "charlie", "OPT", 1.0, "illegal")
        with pytest.raises(TransferRuleViolation):
            bilateral_transfer_rule(view, move)

