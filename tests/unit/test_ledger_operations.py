"""
test_ledger_operations.py - Unit tests for Ledger class operations

Tests:
- Ledger creation and configuration
- Wallet registration
- Unit registration
- Balance operations
- Time management
- Transaction execution
- execute_contract with state updates
"""

import pytest
from datetime import datetime, timedelta
from ledger import (
    Ledger, Move, Transaction, ContractResult, ExecuteResult,
    cash, StateDelta,
    create_stock_unit,
    LedgerError, InsufficientFunds, WalletNotRegistered, UnitNotRegistered,
)


def _stock(symbol: str, name: str, issuer: str, shortable: bool = False):
    """Create a stock unit for testing."""
    return create_stock_unit(symbol, name, issuer, "USD", shortable=shortable)


class TestLedgerCreation:
    """Tests for Ledger initialization."""

    def test_create_ledger_minimal(self):
        """Create ledger with minimal arguments."""
        ledger = Ledger("test")
        assert ledger.name == "test"
        assert ledger.fast_mode is False
        assert ledger.no_log is False

    def test_create_ledger_with_options(self):
        """Create ledger with all options."""
        t = datetime(2025, 1, 1, 9, 30)
        ledger = Ledger(
            name="test",
            initial_time=t,
            verbose=False,
            fast_mode=True,
            no_log=True
        )
        assert ledger.name == "test"
        assert ledger.current_time == t
        assert ledger.verbose is False
        assert ledger.fast_mode is True
        assert ledger.no_log is True

    def test_create_ledger_default_time(self):
        """Ledger has reasonable default time."""
        ledger = Ledger("test", verbose=False)
        assert ledger.current_time is not None


class TestWalletRegistration:
    """Tests for wallet registration."""

    def test_register_wallet(self):
        """Register a wallet."""
        ledger = Ledger("test", verbose=False)
        wallet_id = ledger.register_wallet("alice")
        assert wallet_id == "alice"
        assert "alice" in ledger.list_wallets()

    def test_register_multiple_wallets(self):
        """Register multiple wallets."""
        ledger = Ledger("test", verbose=False)
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("charlie")
        assert len(ledger.list_wallets()) == 3

    def test_register_duplicate_wallet_raises(self):
        """Registering duplicate wallet raises."""
        ledger = Ledger("test", verbose=False)
        ledger.register_wallet("alice")
        with pytest.raises(ValueError, match="already registered"):
            ledger.register_wallet("alice")

    def test_is_registered_true(self):
        """is_registered returns True for registered wallet."""
        ledger = Ledger("test", verbose=False)
        ledger.register_wallet("alice")
        assert ledger.is_registered("alice") is True

    def test_is_registered_false(self):
        """is_registered returns False for unregistered wallet."""
        ledger = Ledger("test", verbose=False)
        assert ledger.is_registered("unknown") is False

    def test_list_wallets_returns_copy(self):
        """list_wallets returns a copy, not internal set."""
        ledger = Ledger("test", verbose=False)
        ledger.register_wallet("alice")
        wallets = ledger.list_wallets()
        wallets.add("hacker")
        assert "hacker" not in ledger.list_wallets()


class TestUnitRegistration:
    """Tests for unit registration."""

    def test_register_unit(self):
        """Register a unit."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        assert "USD" in ledger.list_units()

    def test_register_multiple_units(self):
        """Register multiple units."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(cash("EUR", "Euro"))
        ledger.register_unit(_stock("AAPL", "Apple", "treasury"))
        assert len(ledger.list_units()) == 3

    def test_get_unit_state(self):
        """Get unit state returns state dict."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL_ISSUER"))
        state = ledger.get_unit_state("AAPL")
        assert state["issuer"] == "AAPL_ISSUER"
        # Note: unit_type is on the Unit object, not in _state dict
        assert ledger.units["AAPL"].unit_type == "STOCK"

    def test_get_unit_state_unregistered_raises(self):
        """Getting state of unregistered unit raises."""
        ledger = Ledger("test", verbose=False)
        with pytest.raises(UnitNotRegistered):
            ledger.get_unit_state("UNKNOWN")

    def test_update_unit_state(self):
        """Update unit state merges with existing."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL_ISSUER"))
        ledger.update_unit_state("AAPL", {"price": 150.0, "custom": "value"})
        state = ledger.get_unit_state("AAPL")
        assert state["price"] == 150.0
        assert state["custom"] == "value"
        assert state["issuer"] == "AAPL_ISSUER"  # Original preserved

    def test_list_units_sorted(self):
        """list_units returns sorted list."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple", "treasury"))
        ledger.register_unit(cash("EUR", "Euro"))
        units = ledger.list_units()
        assert units == sorted(units)


class TestBalanceOperations:
    """Tests for balance queries and operations."""

    def test_get_balance_default_zero(self):
        """Unset balance returns zero."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        assert ledger.get_balance("alice", "USD") == 0.0

    def test_get_balance_unregistered_wallet_raises(self):
        """Getting balance for unregistered wallet raises."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        with pytest.raises(WalletNotRegistered):
            ledger.get_balance("unknown", "USD")

    def test_set_balance(self):
        """set_balance sets balance directly."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.set_balance("alice", "USD", 1000.0)
        assert ledger.get_balance("alice", "USD") == 1000.0

    def test_get_wallet_balances(self):
        """get_wallet_balances returns all balances for wallet."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple", "treasury"))
        ledger.register_wallet("alice")
        ledger.set_balance("alice", "USD", 1000.0)
        ledger.set_balance("alice", "AAPL", 10.0)

        bals = ledger.get_wallet_balances("alice")
        assert bals["USD"] == 1000.0
        assert bals["AAPL"] == 10.0

    def test_get_positions(self):
        """get_positions returns all holders of a unit."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "treasury"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("charlie")

        ledger.set_balance("alice", "AAPL", 100.0)
        ledger.set_balance("bob", "AAPL", 50.0)
        # charlie has zero - should not appear

        positions = ledger.get_positions("AAPL")
        assert positions == {"alice": 100.0, "bob": 50.0}
        assert "charlie" not in positions

    def test_total_supply(self):
        """total_supply sums all balances for a unit."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.set_balance("alice", "USD", 1000.0)
        ledger.set_balance("bob", "USD", 500.0)

        assert ledger.total_supply("USD") == 1500.0

    def test_total_supply_with_negative(self):
        """total_supply handles negative balances."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.set_balance("alice", "USD", 1000.0)
        ledger.set_balance("bob", "USD", -500.0)

        assert ledger.total_supply("USD") == 500.0


class TestTimeManagement:
    """Tests for time management."""

    def test_advance_time(self):
        """advance_time moves time forward."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.advance_time(datetime(2025, 1, 2))
        assert ledger.current_time == datetime(2025, 1, 2)

    def test_advance_time_multiple(self):
        """advance_time can be called multiple times."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.advance_time(datetime(2025, 1, 2))
        ledger.advance_time(datetime(2025, 1, 3))
        ledger.advance_time(datetime(2025, 1, 4))
        assert ledger.current_time == datetime(2025, 1, 4)

    def test_advance_time_same_time_ok(self):
        """advance_time to same time is allowed."""
        t = datetime(2025, 1, 1)
        ledger = Ledger("test", t, verbose=False)
        ledger.advance_time(t)  # Should not raise
        assert ledger.current_time == t

    def test_advance_time_backwards_raises(self):
        """advance_time backwards raises."""
        ledger = Ledger("test", datetime(2025, 1, 2), verbose=False)
        with pytest.raises(ValueError, match="Cannot move time backwards"):
            ledger.advance_time(datetime(2025, 1, 1))


class TestTransactionExecution:
    """Tests for transaction execution."""

    def test_execute_simple_transaction(self):
        """Execute simple single-move transaction."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        tx = ledger.create_transaction([
            Move("alice", "bob", "USD", 100.0, "payment")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.APPLIED
        assert ledger.get_balance("alice", "USD") == 900.0
        assert ledger.get_balance("bob", "USD") == 100.0

    def test_execute_multi_move_atomic(self):
        """Multi-move transaction is atomic."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple", "treasury", shortable=True))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.set_balance("alice", "USD", 10000.0)
        ledger.set_balance("bob", "AAPL", 100.0)

        # Trade: alice pays cash, bob delivers stock
        tx = ledger.create_transaction([
            Move("alice", "bob", "USD", 1500.0, "trade"),
            Move("bob", "alice", "AAPL", 10.0, "trade"),
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.APPLIED
        assert ledger.get_balance("alice", "USD") == 8500.0
        assert ledger.get_balance("alice", "AAPL") == 10.0
        assert ledger.get_balance("bob", "USD") == 1500.0
        assert ledger.get_balance("bob", "AAPL") == 90.0

    def test_execute_idempotency(self):
        """Same transaction executes only once."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        tx = ledger.create_transaction([
            Move("alice", "bob", "USD", 100.0, "payment")
        ])

        result1 = ledger.execute(tx)
        result2 = ledger.execute(tx)

        assert result1 == ExecuteResult.APPLIED
        assert result2 == ExecuteResult.ALREADY_APPLIED
        assert ledger.get_balance("alice", "USD") == 900.0  # Only applied once

    def test_execute_reject_insufficient_funds(self):
        """Reject transaction with insufficient funds."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "treasury", shortable=False))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        tx = ledger.create_transaction([
            Move("alice", "bob", "AAPL", 100.0, "trade")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

    def test_execute_reject_unregistered_unit(self):
        """Reject transaction with unregistered unit."""
        ledger = Ledger("test", verbose=False)
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        tx = ledger.create_transaction([
            Move("alice", "bob", "UNKNOWN", 100.0, "trade")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

    def test_execute_reject_unregistered_wallet(self):
        """Reject transaction with unregistered wallet."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")

        tx = ledger.create_transaction([
            Move("alice", "unknown", "USD", 100.0, "trade")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

    def test_execute_fast_mode_skips_validation(self):
        """fast_mode=True skips balance validation."""
        ledger = Ledger("test", verbose=False, fast_mode=True)
        ledger.register_unit(_stock("AAPL", "Apple", "treasury", shortable=False))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        # Would be rejected in normal mode
        tx = ledger.create_transaction([
            Move("alice", "bob", "AAPL", 100.0, "trade")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.APPLIED
        assert ledger.get_balance("alice", "AAPL") == -100.0

    def test_execute_no_log_mode(self):
        """no_log=True skips transaction logging."""
        ledger = Ledger("test", verbose=False, no_log=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        tx = ledger.create_transaction([
            Move("alice", "bob", "USD", 100.0, "payment")
        ])
        ledger.execute(tx)

        assert len(ledger.transaction_log) == 0

    def test_execute_applies_rounding(self):
        """Transaction applies unit rounding."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        tx = ledger.create_transaction([
            Move("alice", "bob", "USD", 100.456, "payment")
        ])
        ledger.execute(tx)

        # Rounded to 2 decimal places
        assert ledger.get_balance("bob", "USD") == 100.46


class TestExecuteContract:
    """Tests for execute_contract method."""

    def test_execute_contract_with_moves(self):
        """execute_contract applies moves."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        result = ContractResult(moves=[
            Move("alice", "bob", "USD", 100.0, "payment")
        ])
        outcome = ledger.execute_contract(result)

        assert outcome == ExecuteResult.APPLIED
        assert ledger.get_balance("bob", "USD") == 100.0

    def test_execute_contract_with_state_updates(self):
        """execute_contract applies state updates."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "treasury"))

        result = ContractResult(state_updates={
            "AAPL": {"settled": True, "price": 150.0}
        })
        outcome = ledger.execute_contract(result)

        assert outcome == ExecuteResult.APPLIED
        state = ledger.get_unit_state("AAPL")
        assert state["settled"] is True
        assert state["price"] == 150.0

    def test_execute_contract_records_state_deltas(self):
        """execute_contract records state deltas in log."""
        ledger = Ledger("test", verbose=False, no_log=False)
        ledger.register_unit(_stock("AAPL", "Apple", "treasury"))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        result = ContractResult(
            moves=[Move("alice", "bob", "USD", 100.0, "payment")],
            state_updates={"AAPL": {"settled": True}}
        )
        ledger.execute_contract(result)

        tx = ledger.transaction_log[-1]
        assert len(tx.state_deltas) == 1
        assert tx.state_deltas[0].unit == "AAPL"
        assert tx.state_deltas[0].new_state["settled"] is True

    def test_execute_empty_contract(self):
        """execute_contract with empty result is APPLIED."""
        ledger = Ledger("test", verbose=False)
        result = ContractResult()
        outcome = ledger.execute_contract(result)
        assert outcome == ExecuteResult.APPLIED


class TestClone:
    """Tests for clone() method."""

    def test_clone_creates_independent_copy(self):
        """Clone is independent of original."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.set_balance("alice", "USD", 1000.0)

        clone = ledger.clone()
        clone.set_balance("alice", "USD", 500.0)

        assert ledger.get_balance("alice", "USD") == 1000.0
        assert clone.get_balance("alice", "USD") == 500.0

    def test_clone_copies_unit_state(self):
        """Clone copies unit state independently."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "treasury"))
        ledger.update_unit_state("AAPL", {"price": 150.0})

        clone = ledger.clone()
        clone.update_unit_state("AAPL", {"price": 200.0})

        assert ledger.get_unit_state("AAPL")["price"] == 150.0
        assert clone.get_unit_state("AAPL")["price"] == 200.0

    def test_clone_deep_copies_nested_state(self):
        """Clone creates deep copy of nested state."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "treasury"))
        ledger.update_unit_state("AAPL", {
            "nested": {"inner": [1, 2, 3]},
            "list": [{"a": 1}]
        })

        clone = ledger.clone()

        # Modify clone's nested state
        clone_state = clone.get_unit_state("AAPL")
        clone_state["nested"]["inner"].append(4)
        clone.update_unit_state("AAPL", clone_state)

        # Original unchanged
        orig_state = ledger.get_unit_state("AAPL")
        assert orig_state["nested"]["inner"] == [1, 2, 3]


class TestCloneAt:
    """Tests for clone_at() method."""

    def test_clone_at_reconstructs_past(self):
        """clone_at reconstructs ledger at past time."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        # Day 1
        ledger.advance_time(datetime(2025, 1, 2))
        tx1 = ledger.create_transaction([Move("alice", "bob", "USD", 100.0, "p1")])
        ledger.execute(tx1)

        # Day 2
        ledger.advance_time(datetime(2025, 1, 3))
        tx2 = ledger.create_transaction([Move("alice", "bob", "USD", 200.0, "p2")])
        ledger.execute(tx2)

        # Clone at day 1
        past_ledger = ledger.clone_at(datetime(2025, 1, 2))

        assert past_ledger.get_balance("alice", "USD") == 900.0
        assert past_ledger.get_balance("bob", "USD") == 100.0

    def test_clone_at_can_continue_executing(self):
        """Clone from clone_at can execute new transactions."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        ledger.advance_time(datetime(2025, 1, 2))
        tx1 = ledger.create_transaction([Move("alice", "bob", "USD", 100.0, "p1")])
        ledger.execute(tx1)

        # Clone at initial time
        past_ledger = ledger.clone_at(datetime(2025, 1, 1))

        # Execute different transaction on clone
        past_ledger.advance_time(datetime(2025, 1, 2))
        tx_alt = past_ledger.create_transaction([Move("alice", "bob", "USD", 500.0, "alt")])
        past_ledger.execute(tx_alt)

        # Divergent states
        assert ledger.get_balance("alice", "USD") == 900.0
        assert past_ledger.get_balance("alice", "USD") == 500.0

    def test_clone_at_no_log_raises(self):
        """clone_at raises when no_log=True."""
        ledger = Ledger("test", verbose=False, no_log=True)
        with pytest.raises(LedgerError, match="no_log"):
            ledger.clone_at(datetime(2025, 1, 1))

    def test_clone_at_future_raises(self):
        """clone_at raises for future time."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        with pytest.raises(ValueError, match="future"):
            ledger.clone_at(datetime(2025, 12, 31))


class TestReplay:
    """Tests for replay() method."""

    def test_replay_recreates_state(self):
        """replay() recreates state from transaction log."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Initial funding via transaction
        tx0 = ledger.create_transaction([Move("treasury", "alice", "USD", 1000.0, "fund")])
        ledger.execute(tx0)

        ledger.advance_time(datetime(2025, 1, 2))
        tx1 = ledger.create_transaction([Move("alice", "bob", "USD", 100.0, "p1")])
        ledger.execute(tx1)

        # Replay
        replayed = ledger.replay()

        assert replayed.get_balance("alice", "USD") == 900.0
        assert replayed.get_balance("bob", "USD") == 100.0

    def test_replay_no_log_raises(self):
        """replay() raises when no_log=True."""
        ledger = Ledger("test", verbose=False, no_log=True)
        with pytest.raises(LedgerError, match="no_log"):
            ledger.replay()
