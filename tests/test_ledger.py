"""
test_ledger.py - Unit tests for ledger.py

Tests:
- Ledger creation and configuration
- Wallet and unit registration
- Balance operations
- Transaction execution (validation, idempotency, rejection)
- execute() with state deltas
- clone(), clone_at() and replay()
"""

import pytest
from datetime import datetime, timedelta
from ledger import (
    Ledger, Move, Transaction, ExecuteResult,
    cash, UnitStateChange, build_transaction,
    create_stock_unit,
    LedgerError, InsufficientFunds, WalletNotRegistered, UnitNotRegistered,
)


# Helper for creating test stocks
def _stock(symbol: str, name: str, issuer: str, shortable: bool = False):
    """Create a stock unit for testing."""
    return create_stock_unit(symbol, name, issuer, "USD", shortable=shortable)


# Simple state comparison utilities for tests
def ledger_state_equals(ledger1: Ledger, ledger2: Ledger, tolerance: float = 1e-9) -> bool:
    """Check if two ledgers have equivalent state (balances and unit states)."""
    diff = compare_ledger_states(ledger1, ledger2, tolerance)
    return diff["equal"]


def compare_ledger_states(ledger1: Ledger, ledger2: Ledger, tolerance: float = 1e-9) -> dict:
    """Compare two ledger states and return differences."""
    balance_diffs = []
    state_diffs = []

    # Compare balances
    all_wallets = ledger1.registered_wallets | ledger2.registered_wallets
    all_units = set(ledger1.units.keys()) | set(ledger2.units.keys())

    for wallet in all_wallets:
        for unit in all_units:
            bal1 = ledger1.balances.get(wallet, {}).get(unit, 0.0)
            bal2 = ledger2.balances.get(wallet, {}).get(unit, 0.0)
            if abs(bal1 - bal2) > tolerance:
                balance_diffs.append((wallet, unit, bal1, bal2))

    # Compare unit states
    for unit_sym in all_units:
        if unit_sym in ledger1.units and unit_sym in ledger2.units:
            state1 = ledger1.get_unit_state(unit_sym)
            state2 = ledger2.get_unit_state(unit_sym)
            if state1 != state2:
                state_diffs.append((unit_sym, state1, state2))

    return {
        "equal": len(balance_diffs) == 0 and len(state_diffs) == 0,
        "balance_diffs": balance_diffs,
        "state_diffs": state_diffs,
    }


class TestLedgerCreation:
    """Tests for Ledger initialization."""

    def test_create_ledger(self):
        ledger = Ledger("test", verbose=False)
        assert ledger.name == "test"
        assert ledger.verbose is False

    def test_create_with_initial_time(self):
        t = datetime(2025, 1, 1, 9, 30)
        ledger = Ledger("test", initial_time=t, verbose=False)
        assert ledger.current_time == t



class TestWalletRegistration:
    """Tests for wallet registration."""

    def test_register_wallet(self):
        ledger = Ledger("test", verbose=False)
        wallet_id = ledger.register_wallet("alice")
        assert wallet_id == "alice"
        assert "alice" in ledger.list_wallets()

    def test_register_duplicate_wallet_raises(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_wallet("alice")
        with pytest.raises(ValueError, match="already registered"):
            ledger.register_wallet("alice")

    def test_is_registered(self):
        ledger = Ledger("test", verbose=False)
        assert not ledger.is_registered("alice")
        ledger.register_wallet("alice")
        assert ledger.is_registered("alice")


class TestUnitRegistration:
    """Tests for unit registration."""

    def test_register_unit(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        assert "USD" in ledger.list_units()

    def test_get_unit_state(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL_ISSUER"))
        state = ledger.get_unit_state("AAPL")
        assert state["issuer"] == "AAPL_ISSUER"

    def test_get_unit_state_unregistered_raises(self):
        ledger = Ledger("test", verbose=False)
        with pytest.raises(UnitNotRegistered):
            ledger.get_unit_state("UNKNOWN")

    def test_update_unit_state(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL_ISSUER"))
        ledger.update_unit_state("AAPL", {"price": 150.0})
        state = ledger.get_unit_state("AAPL")
        assert state["price"] == 150.0
        assert state["issuer"] == "AAPL_ISSUER"  # Original state preserved


class TestBalanceOperations:
    """Tests for balance queries."""

    def test_get_balance_default_zero(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        assert ledger.get_balance("alice", "USD") == 0.0

    def test_get_balance_unregistered_wallet_raises(self):
        ledger = Ledger("test", verbose=False)
        with pytest.raises(WalletNotRegistered):
            ledger.get_balance("unknown", "USD")

    def test_get_wallet_balances(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL"))
        ledger.register_wallet("alice")
        ledger.balances["alice"]["USD"] = 1000.0
        ledger.balances["alice"]["AAPL"] = 10.0

        bals = ledger.get_wallet_balances("alice")
        assert bals["USD"] == 1000.0
        assert bals["AAPL"] == 10.0

    def test_get_positions(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("charlie")

        ledger.set_balance("alice", "AAPL", 100.0)
        ledger.set_balance("bob", "AAPL", 50.0)
        # charlie has zero

        positions = ledger.get_positions("AAPL")
        assert positions == {"alice": 100.0, "bob": 50.0}

    def test_total_supply(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.balances["alice"]["USD"] = 1000.0
        ledger.balances["bob"]["USD"] = -500.0

        assert ledger.total_supply("USD") == 500.0


class TestTimeManagement:
    """Tests for time management."""

    def test_advance_time(self):
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.advance_time(datetime(2025, 1, 2))
        assert ledger.current_time == datetime(2025, 1, 2)

    def test_advance_time_backwards_raises(self):
        ledger = Ledger("test", datetime(2025, 1, 2), verbose=False)
        with pytest.raises(ValueError, match="Cannot move time backwards"):
            ledger.advance_time(datetime(2025, 1, 1))


class TestTransactionExecution:
    """Tests for transaction execution."""

    def test_execute_simple_transaction(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.balances["alice"]["USD"] = 1000.0

        tx = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "payment")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.APPLIED
        assert ledger.get_balance("alice", "USD") == 900.0
        assert ledger.get_balance("bob", "USD") == 100.0

    def test_execute_multi_move_transaction(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL", shortable=True))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.balances["alice"]["USD"] = 10000.0
        ledger.balances["bob"]["AAPL"] = 100.0

        tx = build_transaction(ledger, [
            Move(1500.0, "USD", "alice", "bob", "trade"),
            Move(10.0, "AAPL", "bob", "alice", "trade"),
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.APPLIED
        assert ledger.get_balance("alice", "USD") == 8500.0
        assert ledger.get_balance("alice", "AAPL") == 10.0
        assert ledger.get_balance("bob", "USD") == 1500.0
        assert ledger.get_balance("bob", "AAPL") == 90.0

    def test_idempotency(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.balances["alice"]["USD"] = 1000.0

        tx = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "payment")
        ])

        result1 = ledger.execute(tx)
        result2 = ledger.execute(tx)

        assert result1 == ExecuteResult.APPLIED
        assert result2 == ExecuteResult.ALREADY_APPLIED
        assert ledger.get_balance("alice", "USD") == 900.0  # Only applied once

    def test_reject_insufficient_funds(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL", shortable=False))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        tx = build_transaction(ledger, [
            Move(100.0, "AAPL", "alice", "bob", "trade")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

    def test_reject_unregistered_unit(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        tx = build_transaction(ledger, [
            Move(100.0, "UNKNOWN", "alice", "bob", "trade")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

    def test_reject_unregistered_wallet(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")

        tx = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "unknown", "trade")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED



class TestExecuteContract:
    """Tests for execute method."""

    def test_execute_with_moves(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.balances["alice"]["USD"] = 1000.0

        pending = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "payment")
        ])
        outcome = ledger.execute(pending)

        assert outcome == ExecuteResult.APPLIED
        assert ledger.get_balance("bob", "USD") == 100.0

    def test_execute_with_state_changes(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL"))

        old_state = ledger.get_unit_state("AAPL")
        new_state = {**old_state, "settled": True, "price": 150.0}
        pending = build_transaction(ledger, [], state_changes=[
            UnitStateChange(unit="AAPL", old_state=old_state, new_state=new_state)
        ])
        outcome = ledger.execute(pending)

        assert outcome == ExecuteResult.APPLIED
        state = ledger.get_unit_state("AAPL")
        assert state["settled"] is True
        assert state["price"] == 150.0

    def test_execute_records_state_changes(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.balances["alice"]["USD"] = 1000.0
        ledger.register_unit(cash("USD", "US Dollar"))

        old_state = ledger.get_unit_state("AAPL")
        new_state = {**old_state, "settled": True}
        pending = build_transaction(
            ledger,
            [Move(100.0, "USD", "alice", "bob", "payment")],
            state_changes=[UnitStateChange(unit="AAPL", old_state=old_state, new_state=new_state)]
        )
        ledger.execute(pending)

        # Check that state delta was recorded
        tx = ledger.transaction_log[-1]
        assert len(tx.state_changes) == 1
        assert tx.state_changes[0].unit == "AAPL"

    def test_execute_empty_transaction(self):
        ledger = Ledger("test", verbose=False)
        # Empty transactions should be handled gracefully
        pending = build_transaction(ledger, [])
        outcome = ledger.execute(pending)
        # Empty transactions return APPLIED (no-op is successful)
        assert outcome == ExecuteResult.APPLIED


class TestCloneAndReplay:
    """Tests for clone() and replay() methods."""

    def test_clone_creates_independent_copy(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.balances["alice"]["USD"] = 1000.0

        clone = ledger.clone()

        # Modify clone
        clone.balances["alice"]["USD"] = 500.0

        # Original unchanged
        assert ledger.get_balance("alice", "USD") == 1000.0
        assert clone.get_balance("alice", "USD") == 500.0

    def test_clone_copies_units(self):
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL"))
        ledger.update_unit_state("AAPL", {"price": 150.0})

        clone = ledger.clone()

        # Modify clone state
        clone.update_unit_state("AAPL", {"price": 200.0})

        # Original unchanged
        assert ledger.get_unit_state("AAPL")["price"] == 150.0
        assert clone.get_unit_state("AAPL")["price"] == 200.0

    def test_replay_reconstructs_state(self):
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Initial funding via transaction (recorded in log)
        tx0 = build_transaction(ledger, [Move(1000.0, "USD", "treasury", "alice", "fund")])
        ledger.execute(tx0)

        # Execute more transactions
        ledger.advance_time(datetime(2025, 1, 2))
        tx1 = build_transaction(ledger, [Move(100.0, "USD", "alice", "bob", "p1")])
        ledger.execute(tx1)

        ledger.advance_time(datetime(2025, 1, 3))
        tx2 = build_transaction(ledger, [Move(200.0, "USD", "alice", "bob", "p2")])
        ledger.execute(tx2)

        # Replay
        replayed = ledger.replay()

        assert replayed.get_balance("alice", "USD") == 700.0
        assert replayed.get_balance("bob", "USD") == 300.0
        assert replayed.get_balance("treasury", "USD") == -1000.0


    def test_clone_deep_copies_nested_state(self):
        """Verify clone creates true deep copy of nested state."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "AAPL"))
        ledger.update_unit_state("AAPL", {
            "nested": {"inner": [1, 2, 3]},
            "list": [{"a": 1}, {"b": 2}]
        })

        clone = ledger.clone()

        # Modify clone's nested state
        clone_state = clone.get_unit_state("AAPL")
        clone_state["nested"]["inner"].append(4)
        clone_state["list"][0]["a"] = 999
        clone.update_unit_state("AAPL", clone_state)

        # Original should be unchanged
        orig_state = ledger.get_unit_state("AAPL")
        assert orig_state["nested"]["inner"] == [1, 2, 3]
        assert orig_state["list"][0]["a"] == 1

    def test_clone_at_reconstructs_past(self):
        """Test clone_at returns a working Ledger at past time."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.balances["alice"]["USD"] = 1000.0

        # Day 1: transfer 100
        ledger.advance_time(datetime(2025, 1, 2))
        tx1 = build_transaction(ledger, [Move(100.0, "USD", "alice", "bob", "p1")])
        ledger.execute(tx1)

        # Day 2: transfer 200
        ledger.advance_time(datetime(2025, 1, 3))
        tx2 = build_transaction(ledger, [Move(200.0, "USD", "alice", "bob", "p2")])
        ledger.execute(tx2)

        # Clone at day 1
        past_ledger = ledger.clone_at(datetime(2025, 1, 2))

        # Verify state
        assert past_ledger.get_balance("alice", "USD") == 900.0
        assert past_ledger.get_balance("bob", "USD") == 100.0
        assert len(past_ledger.transaction_log) == 1

    def test_clone_at_can_continue_executing(self):
        """Test clone_at returns a Ledger that can execute new transactions."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.balances["alice"]["USD"] = 1000.0

        # Execute transaction
        ledger.advance_time(datetime(2025, 1, 2))
        tx1 = build_transaction(ledger, [Move(100.0, "USD", "alice", "bob", "p1")])
        ledger.execute(tx1)

        # Clone at initial time
        past_ledger = ledger.clone_at(datetime(2025, 1, 1))

        # Execute different transaction on clone
        past_ledger.advance_time(datetime(2025, 1, 2))
        tx_alt = build_transaction(past_ledger, [Move(500.0, "USD", "alice", "bob", "alt")])
        past_ledger.execute(tx_alt)

        # Verify divergent states
        assert ledger.get_balance("alice", "USD") == 900.0
        assert past_ledger.get_balance("alice", "USD") == 500.0


    def test_clone_at_future_raises(self):
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        with pytest.raises(ValueError, match="future"):
            ledger.clone_at(datetime(2025, 12, 31))


class TestStateVerification:
    """Tests for state comparison utilities."""

    def test_ledger_state_equals_identical(self):
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.balances["alice"]["USD"] = 1000.0

        clone1 = ledger.clone()
        clone2 = ledger.clone()

        assert ledger_state_equals(clone1, clone2)

    def test_ledger_state_equals_different(self):
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.balances["alice"]["USD"] = 1000.0

        clone1 = ledger.clone()

        ledger.advance_time(datetime(2025, 1, 2))
        tx = build_transaction(ledger, [Move(100.0, "USD", "alice", "bob", "p")])
        ledger.execute(tx)

        clone2 = ledger.clone()

        assert not ledger_state_equals(clone1, clone2)

    def test_compare_ledger_states_details(self):
        ledger1 = Ledger("test1", datetime(2025, 1, 1), verbose=False)
        ledger1.register_unit(cash("USD", "US Dollar"))
        ledger1.register_wallet("alice")
        ledger1.balances["alice"]["USD"] = 1000.0

        ledger2 = Ledger("test2", datetime(2025, 1, 1), verbose=False)
        ledger2.register_unit(cash("USD", "US Dollar"))
        ledger2.register_wallet("alice")
        ledger2.balances["alice"]["USD"] = 900.0

        diff = compare_ledger_states(ledger1, ledger2)

        assert not diff["equal"]
        assert len(diff["balance_diffs"]) == 1
        assert diff["balance_diffs"][0] == ("alice", "USD", 1000.0, 900.0)
