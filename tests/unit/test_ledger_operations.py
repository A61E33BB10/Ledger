"""
test_ledger_operations.py - Unit tests for Ledger class operations

Tests:
- Ledger creation and configuration
- Wallet registration
- Unit registration
- Balance operations
- Time management
- Transaction execution
- execute with state updates
"""

import pytest
from datetime import datetime, timedelta
from ledger import (
    Ledger, Move, Transaction, ExecuteResult,
    cash, UnitStateChange, build_transaction,
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

    def test_create_ledger_with_options(self):
        """Create ledger with all options."""
        t = datetime(2025, 1, 1, 9, 30)
        ledger = Ledger(
            name="test",
            initial_time=t,
            verbose=False
        )
        assert ledger.name == "test"
        assert ledger.current_time == t
        assert ledger.verbose is False

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
        # 4 wallets: alice, bob, charlie, and the auto-registered 'system' wallet
        assert len(ledger.list_wallets()) == 4

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

        tx = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "payment")
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

    def test_execute_idempotency(self):
        """Same transaction executes only once."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        tx = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "payment")
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

        tx = build_transaction(ledger, [
            Move(100.0, "AAPL", "alice", "bob", "trade")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

    def test_execute_reject_unregistered_unit(self):
        """Reject transaction with unregistered unit."""
        ledger = Ledger("test", verbose=False)
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        tx = build_transaction(ledger, [
            Move(100.0, "UNKNOWN", "alice", "bob", "trade")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

    def test_execute_reject_unregistered_wallet(self):
        """Reject transaction with unregistered wallet."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")

        tx = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "unknown", "trade")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

    def test_execute_applies_rounding(self):
        """Transaction applies unit rounding."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        tx = build_transaction(ledger, [
            Move(100.456, "USD", "alice", "bob", "payment")
        ])
        ledger.execute(tx)

        # Rounded to 2 decimal places
        assert ledger.get_balance("bob", "USD") == 100.46


class TestExecuteContract:
    """Tests for execute method."""

    def test_execute_with_moves(self):
        """execute applies moves."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        pending = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "payment")
        ])
        outcome = ledger.execute(pending)

        assert outcome == ExecuteResult.APPLIED
        assert ledger.get_balance("bob", "USD") == 100.0

    def test_execute_with_state_changes(self):
        """execute applies state deltas."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "treasury"))

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
        """execute records state deltas in log."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(_stock("AAPL", "Apple", "treasury"))
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", 1000.0)

        old_state = ledger.get_unit_state("AAPL")
        new_state = {**old_state, "settled": True}
        pending = build_transaction(
            ledger,
            [Move(100.0, "USD", "alice", "bob", "payment")],
            state_changes=[UnitStateChange(unit="AAPL", old_state=old_state, new_state=new_state)]
        )
        ledger.execute(pending)

        tx = ledger.transaction_log[-1]
        assert len(tx.state_changes) == 1
        assert tx.state_changes[0].unit == "AAPL"
        assert tx.state_changes[0].new_state["settled"] is True

    def test_execute_empty_transaction(self):
        """execute with empty result is APPLIED (no-op is successful)."""
        ledger = Ledger("test", verbose=False)
        pending = build_transaction(ledger, [])
        outcome = ledger.execute(pending)
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
        tx1 = build_transaction(ledger, [Move(100.0, "USD", "alice", "bob", "p1")])
        ledger.execute(tx1)

        # Day 2
        ledger.advance_time(datetime(2025, 1, 3))
        tx2 = build_transaction(ledger, [Move(200.0, "USD", "alice", "bob", "p2")])
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
        tx1 = build_transaction(ledger, [Move(100.0, "USD", "alice", "bob", "p1")])
        ledger.execute(tx1)

        # Clone at initial time
        past_ledger = ledger.clone_at(datetime(2025, 1, 1))

        # Execute different transaction on clone
        past_ledger.advance_time(datetime(2025, 1, 2))
        tx_alt = build_transaction(past_ledger, [Move(500.0, "USD", "alice", "bob", "alt")])
        past_ledger.execute(tx_alt)

        # Divergent states
        assert ledger.get_balance("alice", "USD") == 900.0
        assert past_ledger.get_balance("alice", "USD") == 500.0

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
        tx0 = build_transaction(ledger, [Move(1000.0, "USD", "treasury", "alice", "fund")])
        ledger.execute(tx0)

        ledger.advance_time(datetime(2025, 1, 2))
        tx1 = build_transaction(ledger, [Move(100.0, "USD", "alice", "bob", "p1")])
        ledger.execute(tx1)

        # Replay
        replayed = ledger.replay()

        assert replayed.get_balance("alice", "USD") == 900.0
        assert replayed.get_balance("bob", "USD") == 100.0


class TestReproducibilityWithDynamicUnits:
    """Tests for replay/clone with dynamically created units (units_to_create)."""

    def test_replay_with_dynamically_created_units(self):
        """Replay must correctly handle transactions that create units."""
        from ledger.units.stock import Dividend
        from ledger.units.deferred_cash import deferred_cash_contract
        from ledger import LifecycleEngine

        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.set_balance("treasury", "USD", 1_000_000)

        # Create stock with dividend
        schedule = [Dividend(
            ex_date=datetime(2024, 3, 15),
            payment_date=datetime(2024, 3, 15),
            amount_per_share=1.00,
            currency="USD"
        )]
        stock = create_stock_unit("AAPL", "Apple", "treasury", "USD", schedule)
        ledger.register_unit(stock)
        ledger.set_balance("alice", "AAPL", 100)

        # Process dividend (creates DeferredCash units)
        ledger.advance_time(datetime(2024, 3, 15))
        from ledger.units.stock import process_dividends
        pending = process_dividends(ledger, "AAPL", datetime(2024, 3, 15))
        ledger.execute(pending)

        # Settle via lifecycle
        engine = LifecycleEngine(ledger, contracts={"DEFERRED_CASH": deferred_cash_contract})
        engine.step(datetime(2024, 3, 15), {})

        # Capture original state
        original_balance = ledger.get_balance("alice", "USD")
        assert original_balance == 100.0

        # Replay should succeed and produce identical state
        replayed = ledger.replay()
        assert replayed.get_balance("alice", "USD") == original_balance

    def test_clone_at_before_unit_was_created(self):
        """clone_at to time before a unit was dynamically created should not have that unit."""
        from ledger.core import PendingTransaction, TransactionOrigin, OriginType, Unit

        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")

        # At t1, execute transaction that creates a unit
        t1 = datetime(2024, 1, 2)
        ledger.advance_time(t1)

        new_unit = Unit(symbol="DYNAMIC", name="Dynamic Unit", unit_type="TEST")
        pending = PendingTransaction(
            moves=(Move(1.0, "DYNAMIC", "system", "alice", "create"),),
            state_changes=(),
            origin=TransactionOrigin(OriginType.CONTRACT, "test"),
            timestamp=t1,
            units_to_create=(new_unit,),
        )
        ledger.execute(pending)

        # Verify unit exists now
        assert "DYNAMIC" in ledger.units
        assert ledger.get_balance("alice", "DYNAMIC") == 1.0

        # clone_at before unit creation
        t0 = datetime(2024, 1, 1)
        cloned = ledger.clone_at(t0)

        # The dynamically created unit should NOT exist in the clone
        assert "DYNAMIC" not in cloned.units

    def test_replay_full_with_dynamic_units(self):
        """Full replay correctly handles transactions that create units."""
        from ledger.core import PendingTransaction, TransactionOrigin, OriginType, Unit

        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        # Transaction 0: creates UnitX
        t1 = datetime(2024, 1, 2)
        ledger.advance_time(t1)
        new_unit = Unit(symbol="UNITX", name="Unit X", unit_type="TEST")
        tx0 = PendingTransaction(
            moves=(Move(10.0, "UNITX", "system", "alice", "create"),),
            state_changes=(),
            origin=TransactionOrigin(OriginType.CONTRACT, "create"),
            timestamp=t1,
            units_to_create=(new_unit,),
        )
        ledger.execute(tx0)

        # Transaction 1: transfers UNITX
        t2 = datetime(2024, 1, 3)
        ledger.advance_time(t2)
        tx1 = build_transaction(ledger, [Move(5.0, "UNITX", "alice", "bob", "transfer")])
        ledger.execute(tx1)

        # Full replay (from_tx=0) should work correctly
        replayed = ledger.replay(from_tx=0)
        assert "UNITX" in replayed.units
        assert replayed.get_balance("alice", "UNITX") == 5.0
        assert replayed.get_balance("bob", "UNITX") == 5.0

    def test_intent_id_includes_units_to_create(self):
        """Two transactions with different units_to_create should have different intent_ids."""
        from ledger.core import PendingTransaction, TransactionOrigin, OriginType, Unit

        origin = TransactionOrigin(OriginType.CONTRACT, "test")
        t = datetime(2024, 1, 1)

        unit_a = Unit(symbol="UNIT_A", name="Unit A", unit_type="TEST")
        unit_b = Unit(symbol="UNIT_B", name="Unit B", unit_type="TEST")

        tx1 = PendingTransaction(
            moves=(),
            state_changes=(),
            origin=origin,
            timestamp=t,
            units_to_create=(unit_a,),
        )

        tx2 = PendingTransaction(
            moves=(),
            state_changes=(),
            origin=origin,
            timestamp=t,
            units_to_create=(unit_b,),
        )

        assert tx1.intent_id != tx2.intent_id

    def test_clone_at_with_staggered_unit_creation(self):
        """clone_at should correctly handle multiple units created at different times."""
        from ledger.core import PendingTransaction, TransactionOrigin, OriginType, Unit

        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")

        # t1: create UnitA
        t1 = datetime(2024, 1, 2)
        ledger.advance_time(t1)
        unit_a = Unit(symbol="UNIT_A", name="Unit A", unit_type="TEST")
        tx1 = PendingTransaction(
            moves=(Move(1.0, "UNIT_A", "system", "alice", "create"),),
            state_changes=(),
            origin=TransactionOrigin(OriginType.CONTRACT, "create_a"),
            timestamp=t1,
            units_to_create=(unit_a,),
        )
        ledger.execute(tx1)

        # t2: create UnitB
        t2 = datetime(2024, 1, 3)
        ledger.advance_time(t2)
        unit_b = Unit(symbol="UNIT_B", name="Unit B", unit_type="TEST")
        tx2 = PendingTransaction(
            moves=(Move(1.0, "UNIT_B", "system", "alice", "create"),),
            state_changes=(),
            origin=TransactionOrigin(OriginType.CONTRACT, "create_b"),
            timestamp=t2,
            units_to_create=(unit_b,),
        )
        ledger.execute(tx2)

        # Current state has both
        assert "UNIT_A" in ledger.units
        assert "UNIT_B" in ledger.units

        # clone_at(t1.5) should have UnitA but not UnitB
        t_mid = datetime(2024, 1, 2, 12, 0)
        cloned = ledger.clone_at(t_mid)

        assert "UNIT_A" in cloned.units
        assert "UNIT_B" not in cloned.units
        assert cloned.get_balance("alice", "UNIT_A") == 1.0
