"""
Idempotency Conformance Tests

INVARIANT: Duplicate execution is detected and prevented.

    ∀ transaction T:
        execute(T) = APPLIED ⟹ execute(T) again = ALREADY_APPLIED
        state after second execute = state after first execute

This guarantees safe retry semantics and prevents double-spending.
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


class TestIdempotencyProperties:
    """Property-based idempotency tests."""

    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=50)
    def test_repeated_execution_always_idempotent(self, num_repeats):
        """
        PROPERTY: Executing the same transaction N times produces same result.
        """
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("10000"))

        tx = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "payment")
        ])

        results = []
        for i in range(num_repeats + 1):
            results.append(ledger.execute(tx))

        # First should succeed
        assert results[0] == ExecuteResult.APPLIED

        # All subsequent should be ALREADY_APPLIED
        for r in results[1:]:
            assert r == ExecuteResult.ALREADY_APPLIED

        # Final balance reflects only one execution
        assert ledger.get_balance("alice", "USD") == Decimal("9900")
        assert ledger.get_balance("bob", "USD") == Decimal("100")

    @given(st.lists(
        st.tuples(
            st.decimals(min_value=Decimal("1"), max_value=Decimal("100"),
                       places=2, allow_nan=False, allow_infinity=False),
            st.text(alphabet="abcdef", min_size=5, max_size=10),
        ),
        min_size=1,
        max_size=10,
    ))
    @settings(max_examples=50)
    def test_different_transactions_independent(self, tx_specs):
        """
        PROPERTY: Different transactions have independent idempotency.
        """
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000000"))

        transactions = []
        for qty, contract_id in tx_specs:
            tx = build_transaction(ledger, [
                Move(qty, "USD", "alice", "bob", contract_id)
            ])
            transactions.append(tx)

        # Execute all
        results1 = [ledger.execute(tx) for tx in transactions]

        # All unique contract_ids should succeed
        # (some may be ALREADY_APPLIED if contract_id collision)
        unique_ids = set(tx.intent_id for tx in transactions)

        # Execute all again
        results2 = [ledger.execute(tx) for tx in transactions]

        # All should be ALREADY_APPLIED now
        for r in results2:
            assert r == ExecuteResult.ALREADY_APPLIED


class TestIdempotencyExamples:
    """Explicit idempotency examples."""

    def test_basic_idempotency(self):
        """Basic idempotency: second execute returns ALREADY_APPLIED."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000"))

        tx = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "payment")
        ])

        result1 = ledger.execute(tx)
        result2 = ledger.execute(tx)

        assert result1 == ExecuteResult.APPLIED
        assert result2 == ExecuteResult.ALREADY_APPLIED

    def test_state_unchanged_after_duplicate(self):
        """State is identical before and after duplicate execution."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000"))

        tx = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "payment")
        ])

        ledger.execute(tx)

        # Capture state after first execution
        alice_bal = ledger.get_balance("alice", "USD")
        bob_bal = ledger.get_balance("bob", "USD")
        log_len = len(ledger.transaction_log)

        # Execute again
        ledger.execute(tx)

        # State unchanged
        assert ledger.get_balance("alice", "USD") == alice_bal
        assert ledger.get_balance("bob", "USD") == bob_bal
        assert len(ledger.transaction_log) == log_len

    def test_intent_id_tracked(self):
        """Executed intent_ids are tracked."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000"))

        tx = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "payment")
        ])

        assert tx.intent_id not in ledger.seen_intent_ids

        ledger.execute(tx)

        assert tx.intent_id in ledger.seen_intent_ids

    def test_same_content_different_object_idempotent(self):
        """Two PendingTransaction objects with same content are idempotent."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000"))

        # Create two separate objects with same content
        tx1 = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "same_content")
        ])
        tx2 = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "same_content")
        ])

        assert tx1.intent_id == tx2.intent_id
        assert tx1 is not tx2

        result1 = ledger.execute(tx1)
        result2 = ledger.execute(tx2)

        assert result1 == ExecuteResult.APPLIED
        assert result2 == ExecuteResult.ALREADY_APPLIED

    def test_rejected_not_marked_as_seen(self):
        """Rejected transactions don't pollute the seen set."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        # Use non-shortable stock to ensure rejection when balance is zero
        ledger.register_unit(create_stock_unit(
            "STOCK", "Test Stock", "treasury", "USD", shortable=False
        ))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        # No balance - will reject (non-shortable)
        tx = build_transaction(ledger, [
            Move(Decimal("100"), "STOCK", "alice", "bob", "will_fail")
        ])

        result1 = ledger.execute(tx)
        assert result1 == ExecuteResult.REJECTED
        assert tx.intent_id not in ledger.seen_intent_ids

        # Fix the issue
        ledger.set_balance("alice", "STOCK", Decimal("1000"))

        # Now can execute
        result2 = ledger.execute(tx)
        assert result2 == ExecuteResult.APPLIED

    def test_replay_respects_idempotency(self):
        """Replay doesn't double-execute transactions."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000"))

        tx = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "payment")
        ])
        ledger.execute(tx)

        # Replay
        replayed = ledger.replay()

        # Replayed ledger has correct balances (from executing log)
        # The transaction was in the log, so it applies once
        # Net effect: alice = 0 - 100 = -100 (no initial balance in replay)
        # bob = 0 + 100 = 100
        assert replayed.get_balance("bob", "USD") == Decimal("100")


class TestIdempotencyByIntentNotEconomics:
    """
    Critical tests verifying idempotency is by INTENT, not by economics.

    Idempotency = at most once per intent, not at most once per idea.
    """

    def test_economically_identical_distinct_intents_both_apply(self):
        """
        TEST B: Economically identical transactions with distinct intents must BOTH apply.

        This is the critical negative test: the Ledger MUST NOT reject tx2.
        If it does, idempotency is incorrectly collapsing legitimate repeated actions.
        """
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD", shortable=True
        ))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("10000"))
        ledger.set_balance("bob", "AAPL", Decimal("100"))

        # Two transactions with IDENTICAL economics but DIFFERENT intents
        # Same: quantity, unit, source, dest
        # Different: contract_id (representing different order_ids)
        tx1 = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "order-001")
        ])
        tx2 = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "order-002")
        ])

        # Verify they have different intent IDs
        assert tx1.intent_id != tx2.intent_id, \
            "CRITICAL: Economically identical transactions must have different intent_ids"

        # Execute both
        result1 = ledger.execute(tx1)
        result2 = ledger.execute(tx2)

        # BOTH must be APPLIED - NOT deduplicated
        assert result1 == ExecuteResult.APPLIED, "First transaction must apply"
        assert result2 == ExecuteResult.APPLIED, \
            "CRITICAL: Second transaction must ALSO apply (distinct intent)"

        # Alice transferred 200 total (100 + 100)
        assert ledger.get_balance("alice", "USD") == Decimal("9800")
        # Bob received 200 total
        assert ledger.get_balance("bob", "USD") == Decimal("200")

        # Transaction log increased by exactly 2
        assert len(ledger.transaction_log) == 2

    def test_same_trade_parameters_different_nonces(self):
        """
        Multiple buy orders at same price/quantity must all execute.

        Simulates: User places 3 separate buy orders for 10 AAPL @ $150 each.
        All 3 should execute independently.
        """
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD", shortable=True
        ))
        ledger.register_wallet("buyer")
        ledger.register_wallet("seller")
        ledger.set_balance("buyer", "USD", Decimal("100000"))
        ledger.set_balance("seller", "AAPL", Decimal("1000"))

        # Three identical trades with different nonces
        trades = []
        for i in range(3):
            tx = build_transaction(ledger, [
                Move(Decimal("10"), "AAPL", "seller", "buyer", f"buy_order_{i}"),
                Move(Decimal("1500"), "USD", "buyer", "seller", f"payment_{i}"),
            ])
            trades.append(tx)

        # All intent_ids must be unique
        intent_ids = [tx.intent_id for tx in trades]
        assert len(set(intent_ids)) == 3, "All trades must have unique intent_ids"

        # Execute all
        results = [ledger.execute(tx) for tx in trades]

        # All must apply
        for i, result in enumerate(results):
            assert result == ExecuteResult.APPLIED, f"Trade {i} must apply"

        # Final state reflects all 3 trades
        assert ledger.get_balance("buyer", "AAPL") == Decimal("30")  # 10 * 3
        assert ledger.get_balance("buyer", "USD") == Decimal("95500")  # 100000 - 4500
        assert ledger.get_balance("seller", "AAPL") == Decimal("970")  # 1000 - 30
        assert ledger.get_balance("seller", "USD") == Decimal("4500")  # 1500 * 3

    def test_intent_identity_is_content_hash_not_economics(self):
        """
        Verify that intent identity = hash(transaction content), not economic meaning.
        """
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("10000"))

        # Same move, different contract_id
        move1 = Move(Decimal("100"), "USD", "alice", "bob", "contract_A")
        move2 = Move(Decimal("100"), "USD", "alice", "bob", "contract_B")

        tx1 = build_transaction(ledger, [move1])
        tx2 = build_transaction(ledger, [move2])

        # Contract_id is part of content, so intent_ids differ
        assert tx1.intent_id != tx2.intent_id

        # Same contract_id but different object instances
        tx3 = build_transaction(ledger, [move1])
        tx4 = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "contract_A")
        ])

        # Same content = same intent_id
        assert tx3.intent_id == tx4.intent_id


class TestIdempotencyAcrossClones:
    """Idempotency tests across clone operations."""

    def test_clone_preserves_seen_intents(self):
        """Clone preserves the seen intents set."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000"))

        tx = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "payment")
        ])
        ledger.execute(tx)

        clone = ledger.clone()

        # Clone has same seen intents
        assert tx.intent_id in clone.seen_intent_ids

        # Re-executing on clone should be ALREADY_APPLIED
        result = clone.execute(tx)
        assert result == ExecuteResult.ALREADY_APPLIED

    def test_clone_independent_after_divergence(self):
        """Clone has independent seen set after divergence."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000"))

        clone = ledger.clone()

        # Execute on original only
        tx = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "divergent")
        ])
        result_original = ledger.execute(tx)

        # Clone doesn't have this in seen set
        assert tx.intent_id not in clone.seen_intent_ids

        # Clone can still execute
        result_clone = clone.execute(tx)

        assert result_original == ExecuteResult.APPLIED
        assert result_clone == ExecuteResult.APPLIED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
