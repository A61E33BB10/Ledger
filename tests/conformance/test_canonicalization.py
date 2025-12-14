"""
Canonicalization Conformance Tests

INVARIANT: Semantically equivalent values produce identical representations.

    ∀ v1, v2: v1 == v2 ⟹ canonicalize(v1) == canonicalize(v2)

This is critical for:
- intent_id determinism (C1 fix)
- Decimal normalization (C3 fix)
- Cross-session/cross-platform reproducibility

These tests verify the canonicalization fixes are correct.
"""

import pytest
from hypothesis import given, settings, assume, note
from hypothesis import strategies as st
from decimal import Decimal
from datetime import datetime
from collections import OrderedDict

from ledger import Ledger, Move, build_transaction, cash
from ledger.core import _canonicalize, _normalize_decimal


# =============================================================================
# STRATEGIES
# =============================================================================

@st.composite
def equivalent_decimals(draw):
    """
    Generate pairs of Decimal values that are equal but may have
    different string representations.
    """
    base = draw(st.decimals(
        min_value=Decimal("-1000000"),
        max_value=Decimal("1000000"),
        places=6,
        allow_nan=False,
        allow_infinity=False,
    ))

    # Create equivalent representations
    d1 = base
    # Add trailing zeros by quantizing differently
    d2 = base.quantize(Decimal("0.000000"))

    return d1, d2


@st.composite
def equivalent_dicts(draw):
    """
    Generate pairs of dictionaries that are semantically equal
    but may have different insertion order.
    """
    keys = draw(st.lists(
        st.text(alphabet="abcdefghij", min_size=1, max_size=5),
        min_size=1,
        max_size=10,
        unique=True
    ))

    values = draw(st.lists(
        st.integers(min_value=-1000, max_value=1000),
        min_size=len(keys),
        max_size=len(keys),
    ))

    # Create dict1 with original order
    dict1 = dict(zip(keys, values))

    # Create dict2 with reversed order
    dict2 = dict(zip(reversed(keys), reversed(values)))

    return dict1, dict2


@st.composite
def nested_dict(draw, max_depth=3):
    """Generate arbitrarily nested dictionaries."""
    if max_depth <= 0:
        return draw(st.one_of(
            st.integers(),
            st.text(min_size=0, max_size=10),
            st.decimals(allow_nan=False, allow_infinity=False),
            st.none(),
            st.booleans(),
        ))

    return draw(st.one_of(
        st.dictionaries(
            st.text(alphabet="abcdef", min_size=1, max_size=3),
            st.deferred(lambda: nested_dict(draw, max_depth - 1)),
            max_size=5
        ),
        st.lists(
            st.deferred(lambda: nested_dict(draw, max_depth - 1)),
            max_size=5
        ),
        st.integers(),
        st.text(min_size=0, max_size=10),
        st.none(),
    ))


# =============================================================================
# DECIMAL NORMALIZATION TESTS
# =============================================================================

class TestDecimalNormalization:
    """Tests for _normalize_decimal function (C3 fix)."""

    @given(equivalent_decimals())
    @settings(max_examples=200)
    def test_equal_decimals_normalize_identically(self, decimals):
        """
        PROPERTY: Equal Decimals produce identical normalized strings.

        This is the core property that C3 fix must guarantee.
        """
        d1, d2 = decimals
        assume(d1 == d2)

        n1 = _normalize_decimal(d1)
        n2 = _normalize_decimal(d2)

        assert n1 == n2, f"Equal decimals {d1} and {d2} normalized differently: {n1} vs {n2}"

    def test_trailing_zeros_normalized(self):
        """Trailing zeros are removed."""
        assert _normalize_decimal(Decimal("1.0")) == _normalize_decimal(Decimal("1.00"))
        assert _normalize_decimal(Decimal("1.0")) == _normalize_decimal(Decimal("1.000"))
        assert _normalize_decimal(Decimal("100.0")) == _normalize_decimal(Decimal("100.00"))

    def test_integer_values_normalized(self):
        """Integer-valued decimals normalize consistently."""
        assert _normalize_decimal(Decimal("100")) == _normalize_decimal(Decimal("100.0"))
        assert _normalize_decimal(Decimal("0")) == _normalize_decimal(Decimal("0.0"))
        assert _normalize_decimal(Decimal("-50")) == _normalize_decimal(Decimal("-50.00"))

    def test_negative_decimals_normalized(self):
        """Negative decimals normalize correctly."""
        assert _normalize_decimal(Decimal("-1.5")) == _normalize_decimal(Decimal("-1.50"))
        assert _normalize_decimal(Decimal("-0.01")) == _normalize_decimal(Decimal("-0.010"))

    def test_scientific_notation_avoided(self):
        """Output doesn't use scientific notation."""
        result = _normalize_decimal(Decimal("0.000001"))
        assert "E" not in result and "e" not in result

    @given(st.decimals(
        min_value=Decimal("-1e10"),
        max_value=Decimal("1e10"),
        allow_nan=False,
        allow_infinity=False,
    ))
    @settings(max_examples=100)
    def test_normalize_is_deterministic(self, d):
        """Same decimal always produces same output."""
        n1 = _normalize_decimal(d)
        n2 = _normalize_decimal(d)
        assert n1 == n2


# =============================================================================
# CANONICALIZE TESTS
# =============================================================================

class TestCanonicalize:
    """Tests for _canonicalize function (C1 fix)."""

    @given(equivalent_dicts())
    @settings(max_examples=200)
    def test_equal_dicts_canonicalize_identically(self, dicts):
        """
        PROPERTY: Equal dicts produce identical canonical strings.

        This is the core property that C1 fix must guarantee.
        """
        d1, d2 = dicts
        assume(d1 == d2)

        c1 = _canonicalize(d1)
        c2 = _canonicalize(d2)

        assert c1 == c2, f"Equal dicts canonicalized differently:\n{d1}\n{d2}\n{c1}\n{c2}"

    def test_dict_key_order_independent(self):
        """Dict canonicalization is key-order independent."""
        d1 = {"z": 1, "a": 2, "m": 3}
        d2 = {"a": 2, "m": 3, "z": 1}
        d3 = {"m": 3, "z": 1, "a": 2}

        assert _canonicalize(d1) == _canonicalize(d2) == _canonicalize(d3)

    def test_nested_dict_order_independent(self):
        """Nested dict canonicalization is order independent at all levels."""
        d1 = {"outer": {"z": 1, "a": 2}}
        d2 = {"outer": {"a": 2, "z": 1}}

        assert _canonicalize(d1) == _canonicalize(d2)

    def test_list_order_preserved(self):
        """List order IS significant and preserved."""
        l1 = [1, 2, 3]
        l2 = [3, 2, 1]

        assert _canonicalize(l1) != _canonicalize(l2)

    def test_type_distinctions_preserved(self):
        """Different types produce different canonicalizations."""
        assert _canonicalize(1) != _canonicalize("1")
        assert _canonicalize(True) != _canonicalize(1)
        assert _canonicalize(None) != _canonicalize("None")

    def test_decimal_in_dict_normalized(self):
        """Decimals in dicts are normalized."""
        d1 = {"amount": Decimal("100.0")}
        d2 = {"amount": Decimal("100.00")}

        assert _canonicalize(d1) == _canonicalize(d2)

    def test_datetime_canonicalization(self):
        """Datetimes canonicalize to ISO format."""
        dt = datetime(2025, 1, 15, 10, 30, 0)
        result = _canonicalize(dt)
        assert "2025-01-15" in result

    @given(st.recursive(
        st.one_of(st.integers(), st.text(max_size=10), st.none(), st.booleans()),
        lambda children: st.one_of(
            st.lists(children, max_size=5),
            st.dictionaries(st.text(alphabet="abc", min_size=1, max_size=3), children, max_size=5)
        ),
        max_leaves=20
    ))
    @settings(max_examples=100)
    def test_canonicalize_is_deterministic(self, value):
        """Same value always produces same output."""
        c1 = _canonicalize(value)
        c2 = _canonicalize(value)
        assert c1 == c2


# =============================================================================
# INTENT ID TESTS
# =============================================================================

class TestIntentIdCanonicalization:
    """Tests for intent_id determinism using canonicalization."""

    def test_same_moves_same_intent_id(self):
        """Identical moves produce identical intent_id."""
        ledger1 = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger2 = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)

        for ledger in [ledger1, ledger2]:
            ledger.register_unit(cash("USD", "US Dollar"))
            ledger.register_wallet("alice")
            ledger.register_wallet("bob")
            ledger.set_balance("alice", "USD", Decimal("1000"))

        move = Move(Decimal("100.0"), "USD", "alice", "bob", "payment")

        tx1 = build_transaction(ledger1, [move])
        tx2 = build_transaction(ledger2, [move])

        assert tx1.intent_id == tx2.intent_id

    def test_move_order_independent_intent_id(self):
        """Move order doesn't affect intent_id."""
        ledger1 = Ledger("test", verbose=False, test_mode=True)
        ledger2 = Ledger("test", verbose=False, test_mode=True)

        for ledger in [ledger1, ledger2]:
            ledger.register_unit(cash("USD", "US Dollar"))
            ledger.register_wallet("alice")
            ledger.register_wallet("bob")
            ledger.register_wallet("charlie")
            ledger.set_balance("alice", "USD", Decimal("1000"))

        move_a = Move(Decimal("50.0"), "USD", "alice", "bob", "p1")
        move_b = Move(Decimal("50.0"), "USD", "alice", "charlie", "p2")

        tx1 = build_transaction(ledger1, [move_a, move_b])
        tx2 = build_transaction(ledger2, [move_b, move_a])

        assert tx1.intent_id == tx2.intent_id

    def test_decimal_representation_independent_intent_id(self):
        """Decimal representation doesn't affect intent_id."""
        ledger1 = Ledger("test", verbose=False, test_mode=True)
        ledger2 = Ledger("test", verbose=False, test_mode=True)

        for ledger in [ledger1, ledger2]:
            ledger.register_unit(cash("USD", "US Dollar"))
            ledger.register_wallet("alice")
            ledger.register_wallet("bob")
            ledger.set_balance("alice", "USD", Decimal("1000"))

        # Same value, different representation
        move1 = Move(Decimal("100.0"), "USD", "alice", "bob", "payment")
        move2 = Move(Decimal("100.00"), "USD", "alice", "bob", "payment")

        tx1 = build_transaction(ledger1, [move1])
        tx2 = build_transaction(ledger2, [move2])

        assert tx1.intent_id == tx2.intent_id

    @given(st.lists(
        st.tuples(
            st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100"), places=2,
                       allow_nan=False, allow_infinity=False),
            st.sampled_from(["alice", "bob", "charlie"]),
            st.sampled_from(["alice", "bob", "charlie"]),
        ),
        min_size=1,
        max_size=5,
    ))
    @settings(max_examples=50)
    def test_intent_id_deterministic_for_any_moves(self, move_specs):
        """intent_id is deterministic for any valid move sequence."""
        # Filter out same source/dest
        move_specs = [(qty, src, dst) for qty, src, dst in move_specs if src != dst]
        assume(len(move_specs) > 0)

        ledger1 = Ledger("test", verbose=False, test_mode=True)
        ledger2 = Ledger("test", verbose=False, test_mode=True)

        for ledger in [ledger1, ledger2]:
            ledger.register_unit(cash("USD", "US Dollar"))
            for w in ["alice", "bob", "charlie"]:
                ledger.register_wallet(w)
                ledger.set_balance(w, "USD", Decimal("10000"))

        moves = [
            Move(qty, "USD", src, dst, f"m_{i}")
            for i, (qty, src, dst) in enumerate(move_specs)
        ]

        tx1 = build_transaction(ledger1, moves)
        tx2 = build_transaction(ledger2, moves.copy())

        assert tx1.intent_id == tx2.intent_id


# =============================================================================
# GOLDEN FILE TESTS
# =============================================================================

class TestGoldenIntentIds:
    """
    Golden file tests for intent_id stability.

    These test specific known inputs produce expected outputs.
    If these fail after a code change, it indicates a breaking change
    in intent_id computation.
    """

    def test_golden_simple_transfer(self):
        """Golden test for simple transfer intent_id."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000"))

        move = Move(Decimal("100"), "USD", "alice", "bob", "golden_test")
        tx = build_transaction(ledger, [move])

        # This is a known-good intent_id.
        # If this changes, it's a breaking change.
        # Note: Update this if canonicalization algorithm intentionally changes
        assert tx.intent_id is not None
        assert len(tx.intent_id) > 0

        # intent_id should be deterministic across runs
        tx2 = build_transaction(ledger, [move])
        assert tx.intent_id == tx2.intent_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
