"""
Atomicity Conformance Tests

INVARIANT: Transactions are all-or-nothing.

    ∀ transaction T:
        T succeeds ⟹ all moves in T are applied
        T fails ⟹ no moves in T are applied

Partial application is impossible by construction.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from decimal import Decimal
from datetime import datetime

from ledger import (
    Ledger, Move, ExecuteResult, cash, build_transaction,
    create_stock_unit,
)


class TestAtomicityProperties:
    """Property-based atomicity tests."""

    @given(st.integers(min_value=2, max_value=10))
    @settings(max_examples=50)
    def test_multi_move_all_or_nothing(self, num_moves):
        """
        PROPERTY: A transaction with N moves either applies all N or none.
        """
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD", shortable=True
        ))

        wallets = [f"wallet_{i}" for i in range(num_moves + 1)]
        for w in wallets:
            ledger.register_wallet(w)

        # Fund first wallet with enough for all moves
        ledger.set_balance(wallets[0], "USD", Decimal("1000000"))

        # Capture initial state
        initial_balances = {
            (w, "USD"): ledger.get_balance(w, "USD")
            for w in wallets
        }

        # Create chain of moves
        moves = []
        for i in range(num_moves):
            moves.append(Move(
                Decimal("100"),
                "USD",
                wallets[i],
                wallets[i + 1],
                f"chain_{i}"
            ))

        tx = build_transaction(ledger, moves)
        result = ledger.execute(tx)

        if result == ExecuteResult.APPLIED:
            # All moves should be reflected
            assert ledger.get_balance(wallets[0], "USD") == Decimal("1000000") - Decimal("100")
            assert ledger.get_balance(wallets[-1], "USD") == Decimal("100")
        else:
            # No moves should be reflected
            for w in wallets:
                assert ledger.get_balance(w, "USD") == initial_balances[(w, "USD")]


class TestAtomicityExamples:
    """Explicit atomicity examples."""

    def test_failing_last_move_rolls_back_all(self):
        """If the last move fails, all previous moves are not applied."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD", shortable=False  # No shorting
        ))

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        # Alice has USD but no AAPL
        ledger.set_balance("alice", "USD", Decimal("10000"))
        ledger.set_balance("alice", "AAPL", Decimal("0"))

        # Capture initial
        initial_usd = ledger.get_balance("alice", "USD")
        initial_aapl = ledger.get_balance("alice", "AAPL")

        # First move OK, second will fail (no AAPL to transfer)
        tx = build_transaction(ledger, [
            Move(Decimal("1000"), "USD", "alice", "bob", "trade_usd"),
            Move(Decimal("100"), "AAPL", "alice", "bob", "trade_aapl"),  # Fails
        ])

        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

        # Neither move applied
        assert ledger.get_balance("alice", "USD") == initial_usd
        assert ledger.get_balance("alice", "AAPL") == initial_aapl
        assert ledger.get_balance("bob", "USD") == Decimal("0")
        assert ledger.get_balance("bob", "AAPL") == Decimal("0")

    def test_failing_first_move_prevents_all(self):
        """If the first move fails, subsequent moves are not applied."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        # Use non-shortable units to ensure rejection
        ledger.register_unit(create_stock_unit(
            "USD_NS", "USD Non-Shortable", "treasury", "USD", shortable=False
        ))
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD", shortable=False
        ))

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        # Alice has AAPL but not enough USD_NS
        ledger.set_balance("alice", "USD_NS", Decimal("100"))
        ledger.set_balance("alice", "AAPL", Decimal("1000"))

        # First move fails (not enough USD_NS and not shortable), second would have been OK
        tx = build_transaction(ledger, [
            Move(Decimal("10000"), "USD_NS", "alice", "bob", "trade_usd"),  # Fails
            Move(Decimal("100"), "AAPL", "alice", "bob", "trade_aapl"),
        ])

        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

        # Neither move applied
        assert ledger.get_balance("alice", "AAPL") == Decimal("1000")
        assert ledger.get_balance("bob", "AAPL") == Decimal("0")

    def test_middle_move_failure(self):
        """Failure in middle move prevents all."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD", shortable=False
        ))
        ledger.register_unit(create_stock_unit(
            "MSFT", "Microsoft", "treasury", "USD", shortable=False
        ))

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.set_balance("alice", "USD", Decimal("10000"))
        ledger.set_balance("alice", "AAPL", Decimal("0"))  # No AAPL
        ledger.set_balance("alice", "MSFT", Decimal("1000"))

        initial = {
            "USD": ledger.get_balance("alice", "USD"),
            "AAPL": ledger.get_balance("alice", "AAPL"),
            "MSFT": ledger.get_balance("alice", "MSFT"),
        }

        # Move 1: OK, Move 2: Fails, Move 3: Would be OK
        tx = build_transaction(ledger, [
            Move(Decimal("1000"), "USD", "alice", "bob", "ok1"),
            Move(Decimal("100"), "AAPL", "alice", "bob", "fails"),
            Move(Decimal("100"), "MSFT", "alice", "bob", "ok2"),
        ])

        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

        # All unchanged
        assert ledger.get_balance("alice", "USD") == initial["USD"]
        assert ledger.get_balance("alice", "AAPL") == initial["AAPL"]
        assert ledger.get_balance("alice", "MSFT") == initial["MSFT"]

    def test_log_unchanged_on_failure(self):
        """Transaction log is not modified on rejection."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        # Use non-shortable stock to force rejection
        ledger.register_unit(create_stock_unit(
            "STOCK", "Test Stock", "treasury", "USD", shortable=False
        ))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        initial_log_length = len(ledger.transaction_log)

        # This will fail - no balance and not shortable
        tx = build_transaction(ledger, [
            Move(Decimal("1000"), "STOCK", "alice", "bob", "fail")
        ])

        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED
        assert len(ledger.transaction_log) == initial_log_length

    def test_seen_intents_unchanged_on_failure(self):
        """Seen intents set is not modified on rejection."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        # Use non-shortable stock to force rejection
        ledger.register_unit(create_stock_unit(
            "STOCK", "Test Stock", "treasury", "USD", shortable=False
        ))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        initial_seen_count = len(ledger.seen_intent_ids)

        # This will fail
        tx = build_transaction(ledger, [
            Move(Decimal("1000"), "STOCK", "alice", "bob", "fail")
        ])

        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED
        assert len(ledger.seen_intent_ids) == initial_seen_count

        # Can retry with same intent_id after fixing the issue
        ledger.set_balance("alice", "STOCK", Decimal("10000"))
        result2 = ledger.execute(tx)
        assert result2 == ExecuteResult.APPLIED


class TestAtomicityWithStateChanges:
    """Atomicity tests involving state changes."""

    def test_state_changes_atomic_with_moves(self):
        """State changes are also rolled back on failure."""
        from ledger.core import UnitStateChange

        ledger = Ledger("test", verbose=False, test_mode=True)
        # Use non-shortable to ensure rejection
        ledger.register_unit(create_stock_unit(
            "USD_NS", "USD Non-Shortable", "treasury", "USD", shortable=False
        ))
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD"
        ))

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        ledger.set_balance("alice", "USD_NS", Decimal("100"))  # Not enough

        initial_state = ledger.get_unit_state("AAPL")

        # Transaction with state change AND failing move
        old_state = ledger.get_unit_state("AAPL")
        new_state = {**old_state, "custom_field": "modified"}

        tx = build_transaction(
            ledger,
            [Move(Decimal("10000"), "USD_NS", "alice", "bob", "fail")],
            state_changes=[UnitStateChange("AAPL", old_state, new_state)]
        )

        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED

        # State unchanged
        current_state = ledger.get_unit_state("AAPL")
        assert current_state.get("custom_field") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
