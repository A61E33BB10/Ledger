"""
Conservation Law Conformance Tests

INVARIANT: For all units u, at all times t:
    Σ_{w ∈ wallets} balance(w, u, t) = constant

This is the fundamental double-entry accounting invariant.
Transfers redistribute but never create or destroy value.

These tests use property-based testing to verify conservation
holds for arbitrary valid transaction sequences.
"""

import pytest
from hypothesis import given, settings, assume, note, Phase
from hypothesis import strategies as st
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Tuple

from ledger import (
    Ledger, Move, ExecuteResult, cash, build_transaction,
    create_stock_unit,
)
from ledger.core import QUANTITY_EPSILON


# =============================================================================
# STRATEGIES FOR PROPERTY-BASED TESTING
# =============================================================================

@st.composite
def decimal_quantity(draw, min_value=Decimal("0.01"), max_value=Decimal("1000000")):
    """Generate a valid quantity as Decimal."""
    # Use string to avoid float precision issues
    value = draw(st.decimals(
        min_value=min_value,
        max_value=max_value,
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ))
    return value


@st.composite
def wallet_name(draw):
    """Generate a valid wallet name."""
    return draw(st.sampled_from([
        "alice", "bob", "charlie", "dave", "eve",
        "treasury", "market", "clearing", "issuer"
    ]))


@st.composite
def valid_move(draw, wallets: List[str], units: List[str], balances: Dict[Tuple[str, str], Decimal]):
    """
    Generate a valid move that won't be rejected.

    This strategy ensures:
    - Source has sufficient balance (or unit is shortable)
    - Source != dest
    - Quantity > 0
    """
    unit = draw(st.sampled_from(units))
    source = draw(st.sampled_from(wallets))
    dest = draw(st.sampled_from([w for w in wallets if w != source]))

    # Get source balance
    source_balance = balances.get((source, unit), Decimal("0"))

    # Determine max quantity (allow shorting for testing)
    max_qty = max(source_balance, Decimal("1000"))
    min_qty = Decimal("0.01")

    if max_qty < min_qty:
        max_qty = min_qty

    quantity = draw(st.decimals(
        min_value=min_qty,
        max_value=max_qty,
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ))

    contract_id = draw(st.text(alphabet="abcdefghijklmnop", min_size=5, max_size=10))

    return Move(quantity, unit, source, dest, contract_id)


@st.composite
def transaction_sequence(draw, num_transactions: int = 10):
    """
    Generate a sequence of transactions that can be executed.

    Returns: (initial_balances, moves_list)
    """
    wallets = ["alice", "bob", "charlie", "treasury"]
    units = ["USD", "STOCK"]

    # Generate initial balances
    initial_balances = {}
    for wallet in wallets:
        for unit in units:
            balance = draw(st.decimals(
                min_value=Decimal("0"),
                max_value=Decimal("100000"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            ))
            initial_balances[(wallet, unit)] = balance

    # Generate moves
    moves_list = []
    current_balances = dict(initial_balances)

    for _ in range(num_transactions):
        # Pick a unit and source with positive balance
        candidates = [
            (w, u) for (w, u), bal in current_balances.items()
            if bal > Decimal("0.01")
        ]

        if not candidates:
            break

        source, unit = draw(st.sampled_from(candidates))
        dest = draw(st.sampled_from([w for w in wallets if w != source]))

        max_qty = current_balances[(source, unit)]
        quantity = draw(st.decimals(
            min_value=Decimal("0.01"),
            max_value=max_qty,
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ))

        contract_id = f"tx_{len(moves_list)}"

        moves_list.append(Move(quantity, unit, source, dest, contract_id))

        # Update balances
        current_balances[(source, unit)] -= quantity
        current_balances[(dest, unit)] = current_balances.get((dest, unit), Decimal("0")) + quantity

    return initial_balances, moves_list


# =============================================================================
# CONSERVATION PROPERTY TESTS
# =============================================================================

class TestConservationProperties:
    """Property-based tests for conservation invariant."""

    @given(transaction_sequence())
    @settings(max_examples=100, phases=[Phase.generate, Phase.target])
    def test_conservation_holds_for_arbitrary_sequences(self, scenario):
        """
        PROPERTY: Conservation holds for any valid transaction sequence.

        ∀ sequence S of valid transactions:
            initial_supply(u) = final_supply(u) for all units u
        """
        initial_balances, moves_list = scenario

        # Skip empty scenarios
        assume(len(moves_list) > 0)

        # Setup ledger
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            "STOCK", "Test Stock", "treasury", "USD", shortable=True
        ))

        wallets = set()
        for (wallet, unit), balance in initial_balances.items():
            wallets.add(wallet)

        for wallet in wallets:
            ledger.register_wallet(wallet)

        # Set initial balances
        for (wallet, unit), balance in initial_balances.items():
            ledger.set_balance(wallet, unit, balance)

        # Record initial supplies
        initial_usd = ledger.total_supply("USD")
        initial_stock = ledger.total_supply("STOCK")

        note(f"Initial USD supply: {initial_usd}")
        note(f"Initial STOCK supply: {initial_stock}")
        note(f"Number of moves: {len(moves_list)}")

        # Execute moves
        for move in moves_list:
            tx = build_transaction(ledger, [move])
            result = ledger.execute(tx)
            # We don't require all to succeed, but track failures
            note(f"Move {move.contract_id}: {result}")

        # Verify conservation
        final_usd = ledger.total_supply("USD")
        final_stock = ledger.total_supply("STOCK")

        assert abs(initial_usd - final_usd) < QUANTITY_EPSILON, \
            f"USD conservation violated: {initial_usd} -> {final_usd}"
        assert abs(initial_stock - final_stock) < QUANTITY_EPSILON, \
            f"STOCK conservation violated: {initial_stock} -> {final_stock}"

    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=20)
    def test_conservation_holds_after_many_transfers(self, num_transfers):
        """
        PROPERTY: Conservation holds after N sequential transfers.
        """
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        wallets = ["alice", "bob", "charlie", "dave"]
        for w in wallets:
            ledger.register_wallet(w)

        # Initial supply only in alice
        initial_supply = Decimal("100000.00")
        ledger.set_balance("alice", "USD", initial_supply)

        # Execute random transfers
        import random
        random.seed(42 + num_transfers)  # Deterministic per num_transfers

        for i in range(num_transfers):
            # Find wallets with positive balance
            sources = [w for w in wallets if ledger.get_balance(w, "USD") > Decimal("1")]
            if not sources:
                break

            source = random.choice(sources)
            dest = random.choice([w for w in wallets if w != source])
            max_qty = ledger.get_balance(source, "USD")
            quantity = Decimal(str(round(random.uniform(0.01, float(max_qty)), 2)))

            tx = build_transaction(ledger, [
                Move(quantity, "USD", source, dest, f"transfer_{i}")
            ])
            ledger.execute(tx)

        # Verify conservation
        final_supply = ledger.total_supply("USD")
        assert abs(initial_supply - final_supply) < QUANTITY_EPSILON

    @given(st.lists(st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("1000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ), min_size=2, max_size=10))
    @settings(max_examples=50)
    def test_multi_move_transaction_conserves(self, quantities):
        """
        PROPERTY: A single transaction with multiple moves conserves.
        """
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Create enough wallets
        wallets = [f"wallet_{i}" for i in range(len(quantities) + 1)]
        for w in wallets:
            ledger.register_wallet(w)

        # Fund first wallet with sum of all quantities
        total = sum(quantities)
        ledger.set_balance(wallets[0], "USD", total)

        initial_supply = ledger.total_supply("USD")

        # Create chain of transfers
        moves = []
        for i, qty in enumerate(quantities):
            moves.append(Move(qty, "USD", wallets[i], wallets[i+1], f"chain_{i}"))

        tx = build_transaction(ledger, moves)
        result = ledger.execute(tx)

        # Regardless of success/failure, conservation must hold
        final_supply = ledger.total_supply("USD")
        assert abs(initial_supply - final_supply) < QUANTITY_EPSILON


# =============================================================================
# EXPLICIT CONSERVATION TESTS (Examples)
# =============================================================================

class TestConservationExamples:
    """Explicit example-based conservation tests."""

    def test_simple_transfer_conserves(self):
        """Basic transfer doesn't create/destroy value."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000.00"))

        initial = ledger.total_supply("USD")

        tx = build_transaction(ledger, [
            Move(Decimal("500.00"), "USD", "alice", "bob", "transfer")
        ])
        ledger.execute(tx)

        final = ledger.total_supply("USD")
        assert initial == final == Decimal("1000.00")

    def test_rejected_transaction_conserves(self):
        """Rejected transaction doesn't affect conservation."""
        ledger = Ledger("test", verbose=False, test_mode=True)
        # Use non-shortable stock to ensure rejection when overdrawing
        ledger.register_unit(create_stock_unit(
            "STOCK", "Test Stock", "treasury", "USD", shortable=False
        ))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "STOCK", Decimal("100.00"))

        initial = ledger.total_supply("STOCK")

        # Try to transfer more than available (non-shortable, so will reject)
        tx = build_transaction(ledger, [
            Move(Decimal("500.00"), "STOCK", "alice", "bob", "overdraft")
        ])
        result = ledger.execute(tx)

        assert result == ExecuteResult.REJECTED
        final = ledger.total_supply("STOCK")
        assert initial == final

    def test_partial_transaction_rejected_conserves(self):
        """
        Transaction where one move fails rejects entirely.
        Conservation holds because atomicity ensures no partial apply.
        """
        ledger = Ledger("test", verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD", shortable=False
        ))

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("10000.00"))
        ledger.set_balance("alice", "AAPL", Decimal("10"))  # Only 10 shares

        initial_usd = ledger.total_supply("USD")
        initial_aapl = ledger.total_supply("AAPL")

        # Try trade: USD move OK, but AAPL move exceeds balance
        tx = build_transaction(ledger, [
            Move(Decimal("1000.00"), "USD", "alice", "bob", "trade"),
            Move(Decimal("100"), "AAPL", "alice", "bob", "trade"),  # Fails
        ])
        result = ledger.execute(tx)

        # Both must fail due to atomicity
        assert result == ExecuteResult.REJECTED

        # Conservation holds
        assert ledger.total_supply("USD") == initial_usd
        assert ledger.total_supply("AAPL") == initial_aapl

        # Balances unchanged
        assert ledger.get_balance("alice", "USD") == Decimal("10000.00")
        assert ledger.get_balance("alice", "AAPL") == Decimal("10")


# =============================================================================
# STRESS TESTS
# =============================================================================

class TestConservationStress:
    """Stress tests for conservation under load."""

    @pytest.mark.parametrize("num_transactions", [100, 1000, 10000])
    def test_conservation_under_load(self, num_transactions):
        """Conservation holds after many transactions."""
        import random
        random.seed(42)

        ledger = Ledger("stress", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        wallets = [f"wallet_{i}" for i in range(100)]
        for w in wallets:
            ledger.register_wallet(w)

        # Distribute initial supply
        initial_supply = Decimal("10000000.00")
        per_wallet = initial_supply / len(wallets)
        for w in wallets:
            ledger.set_balance(w, "USD", per_wallet)

        # Execute many random transfers
        for i in range(num_transactions):
            source = random.choice(wallets)
            dest = random.choice([w for w in wallets if w != source])
            source_bal = ledger.get_balance(source, "USD")

            if source_bal > Decimal("0.01"):
                qty = Decimal(str(round(random.uniform(0.01, float(source_bal)), 2)))
                tx = build_transaction(ledger, [
                    Move(qty, "USD", source, dest, f"stress_{i}")
                ])
                ledger.execute(tx)

        final_supply = ledger.total_supply("USD")
        assert abs(initial_supply - final_supply) < QUANTITY_EPSILON

    def test_conservation_with_rounding(self):
        """Conservation holds even with decimal rounding."""
        ledger = Ledger("round", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        # Use a quantity that tests rounding
        ledger.set_balance("alice", "USD", Decimal("100.00"))

        initial = ledger.total_supply("USD")

        # Transfer 1/3 (will round)
        tx = build_transaction(ledger, [
            Move(Decimal("33.333333"), "USD", "alice", "bob", "third")
        ])
        ledger.execute(tx)

        final = ledger.total_supply("USD")

        # With rounding, we may have small discrepancy but within tolerance
        assert abs(initial - final) < Decimal("0.01")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
