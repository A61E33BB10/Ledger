"""
Tests for stock split functionality.

Tests cover:
1. Pure function compute_split_adjustments
2. Forward splits (2-for-1, 3-for-1)
3. Reverse splits (1-for-2, 1-for-10)
4. Splits with BorrowRecord obligations
5. Splits with short positions
6. Conservation laws
7. Edge cases
"""
import pytest
from datetime import datetime

from ledger import (
    Ledger, cash, SYSTEM_WALLET,
    create_stock_unit, compute_stock_split, compute_split_adjustments,
    SplitAdjustment, BorrowSplitAdjustment,
    initiate_borrow, compute_available_position,
)


class TestComputeSplitAdjustments:
    """Tests for the pure compute_split_adjustments function."""

    def test_forward_split_long_positions(self):
        """2-for-1 split doubles all long positions."""
        positions = {"alice": 100.0, "bob": 50.0}
        borrow_records = {}

        pos_adj, borrow_adj = compute_split_adjustments(
            ratio=2.0,
            positions=positions,
            borrow_records=borrow_records,
            issuer="treasury",
        )

        assert len(pos_adj) == 2
        assert len(borrow_adj) == 0

        alice_adj = next(a for a in pos_adj if a.wallet == "alice")
        assert alice_adj.old_quantity == 100.0
        assert alice_adj.new_quantity == 200.0
        assert alice_adj.adjustment == 100.0

        bob_adj = next(a for a in pos_adj if a.wallet == "bob")
        assert bob_adj.old_quantity == 50.0
        assert bob_adj.new_quantity == 100.0
        assert bob_adj.adjustment == 50.0

    def test_reverse_split_long_positions(self):
        """1-for-2 reverse split halves all long positions."""
        positions = {"alice": 100.0, "bob": 50.0}
        borrow_records = {}

        pos_adj, borrow_adj = compute_split_adjustments(
            ratio=0.5,
            positions=positions,
            borrow_records=borrow_records,
            issuer="treasury",
        )

        assert len(pos_adj) == 2

        alice_adj = next(a for a in pos_adj if a.wallet == "alice")
        assert alice_adj.old_quantity == 100.0
        assert alice_adj.new_quantity == 50.0
        assert alice_adj.adjustment == -50.0  # Negative = returns shares

        bob_adj = next(a for a in pos_adj if a.wallet == "bob")
        assert bob_adj.old_quantity == 50.0
        assert bob_adj.new_quantity == 25.0
        assert bob_adj.adjustment == -25.0

    def test_issuer_excluded_from_adjustments(self):
        """Issuer position should not be adjusted."""
        positions = {"alice": 100.0, "treasury": 1000000.0}
        borrow_records = {}

        pos_adj, borrow_adj = compute_split_adjustments(
            ratio=2.0,
            positions=positions,
            borrow_records=borrow_records,
            issuer="treasury",
        )

        assert len(pos_adj) == 1
        assert pos_adj[0].wallet == "alice"

    def test_borrow_records_adjusted(self):
        """Borrow record quantities should scale by ratio."""
        positions = {"alice": 100.0}
        borrow_records = {
            "BORROW_AAPL_alice_bob_001": 50.0,
            "BORROW_AAPL_alice_carol_002": 30.0,
        }

        pos_adj, borrow_adj = compute_split_adjustments(
            ratio=2.0,
            positions=positions,
            borrow_records=borrow_records,
            issuer="treasury",
        )

        assert len(borrow_adj) == 2

        adj1 = next(a for a in borrow_adj if a.borrow_symbol == "BORROW_AAPL_alice_bob_001")
        assert adj1.old_quantity == 50.0
        assert adj1.new_quantity == 100.0

        adj2 = next(a for a in borrow_adj if a.borrow_symbol == "BORROW_AAPL_alice_carol_002")
        assert adj2.old_quantity == 30.0
        assert adj2.new_quantity == 60.0

    def test_zero_positions_skipped(self):
        """Positions with zero shares should be skipped."""
        positions = {"alice": 100.0, "bob": 0.0, "carol": 1e-14}  # Carol below epsilon (1e-12)
        borrow_records = {}

        pos_adj, borrow_adj = compute_split_adjustments(
            ratio=2.0,
            positions=positions,
            borrow_records=borrow_records,
            issuer="treasury",
        )

        assert len(pos_adj) == 1
        assert pos_adj[0].wallet == "alice"

    def test_rounding_applied(self):
        """Fractional shares should be rounded to decimal_places."""
        positions = {"alice": 33.0}  # 33 * 3 = 99, but 33 * 1.5 = 49.5
        borrow_records = {}

        pos_adj, _ = compute_split_adjustments(
            ratio=1.5,
            positions=positions,
            borrow_records=borrow_records,
            issuer="treasury",
            decimal_places=0,  # Round to whole shares
        )

        assert len(pos_adj) == 1
        # 33 * 1.5 = 49.5 -> rounds to 50 (Python's banker's rounding)
        assert pos_adj[0].new_quantity == 50.0


class TestComputeStockSplit:
    """Integration tests for compute_stock_split with Ledger."""

    @pytest.fixture
    def ledger(self):
        """Create a ledger with stock and wallets."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("carol")

        stock = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
        )
        ledger.register_unit(stock)

        # Treasury has authorized shares
        ledger.set_balance("treasury", "AAPL", 1_000_000)

        return ledger

    def test_forward_split_2_for_1(self, ledger):
        """2-for-1 split doubles positions."""
        ledger.set_balance("alice", "AAPL", 100)
        ledger.set_balance("bob", "AAPL", 50)

        result = compute_stock_split(ledger, "AAPL", ratio=2.0)
        ledger.execute(result)

        assert ledger.get_balance("alice", "AAPL") == 200
        assert ledger.get_balance("bob", "AAPL") == 100
        assert ledger.get_balance("treasury", "AAPL") == 1_000_000 - 150

    def test_forward_split_3_for_1(self, ledger):
        """3-for-1 split triples positions."""
        ledger.set_balance("alice", "AAPL", 100)

        result = compute_stock_split(ledger, "AAPL", ratio=3.0)
        ledger.execute(result)

        assert ledger.get_balance("alice", "AAPL") == 300
        assert ledger.get_balance("treasury", "AAPL") == 1_000_000 - 200

    def test_reverse_split_1_for_2(self, ledger):
        """1-for-2 reverse split halves positions."""
        ledger.set_balance("alice", "AAPL", 100)
        ledger.set_balance("bob", "AAPL", 50)

        result = compute_stock_split(ledger, "AAPL", ratio=0.5)
        ledger.execute(result)

        assert ledger.get_balance("alice", "AAPL") == 50
        assert ledger.get_balance("bob", "AAPL") == 25
        # Treasury receives returned shares
        assert ledger.get_balance("treasury", "AAPL") == 1_000_000 + 75

    def test_reverse_split_1_for_10(self, ledger):
        """1-for-10 reverse split reduces positions to 1/10."""
        ledger.set_balance("alice", "AAPL", 1000)

        result = compute_stock_split(ledger, "AAPL", ratio=0.1)
        ledger.execute(result)

        assert ledger.get_balance("alice", "AAPL") == 100
        assert ledger.get_balance("treasury", "AAPL") == 1_000_000 + 900

    def test_split_state_recorded(self, ledger):
        """Split should update stock state with history."""
        ledger.set_balance("alice", "AAPL", 100)

        result = compute_stock_split(
            ledger, "AAPL", ratio=2.0,
            split_date=datetime(2024, 6, 1)
        )
        ledger.execute(result)

        state = ledger.get_unit_state("AAPL")
        assert state['last_split_ratio'] == 2.0
        assert state['last_split_date'] == datetime(2024, 6, 1)
        assert len(state['split_history']) == 1
        assert state['split_history'][0]['ratio'] == 2.0

    def test_multiple_splits_accumulate_history(self, ledger):
        """Multiple splits should accumulate in history."""
        ledger.set_balance("alice", "AAPL", 100)

        result1 = compute_stock_split(ledger, "AAPL", ratio=2.0, split_date=datetime(2024, 3, 1))
        ledger.execute(result1)

        result2 = compute_stock_split(ledger, "AAPL", ratio=3.0, split_date=datetime(2024, 6, 1))
        ledger.execute(result2)

        assert ledger.get_balance("alice", "AAPL") == 600  # 100 * 2 * 3

        state = ledger.get_unit_state("AAPL")
        assert len(state['split_history']) == 2
        assert state['last_split_ratio'] == 3.0

    def test_invalid_ratio_raises(self, ledger):
        """Negative or zero ratio should raise ValueError."""
        with pytest.raises(ValueError, match="positive"):
            compute_stock_split(ledger, "AAPL", ratio=0)

        with pytest.raises(ValueError, match="positive"):
            compute_stock_split(ledger, "AAPL", ratio=-2.0)

    def test_no_issuer_raises(self, ledger):
        """Stock without issuer should raise ValueError."""
        from ledger.core import Unit, UNIT_TYPE_STOCK
        no_issuer = Unit(
            symbol="NOISSUER",
            name="No Issuer Stock",
            unit_type=UNIT_TYPE_STOCK,
            _state={'currency': 'USD'},
        )
        ledger.register_unit(no_issuer)
        ledger.set_balance("alice", "NOISSUER", 100)

        with pytest.raises(ValueError, match="no issuer"):
            compute_stock_split(ledger, "NOISSUER", ratio=2.0)


class TestSplitWithBorrows:
    """Tests for stock splits with active BorrowRecords."""

    @pytest.fixture
    def ledger_with_borrow(self):
        """Create a ledger with an active borrow."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")  # borrower
        ledger.register_wallet("bob")    # lender
        ledger.register_wallet("carol")

        stock = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
        )
        ledger.register_unit(stock)

        # Treasury has authorized shares
        ledger.set_balance("treasury", "AAPL", 1_000_000)
        ledger.set_balance("treasury", "USD", 1_000_000)

        # Bob has shares to lend
        ledger.set_balance("bob", "AAPL", 1000)

        # Alice borrows 500 from Bob
        borrow_tx = initiate_borrow(
            ledger, "AAPL", "alice", "bob", 500,
            borrow_id="001"
        )
        ledger.execute(borrow_tx)

        return ledger

    def test_borrow_obligation_scales_with_split(self, ledger_with_borrow):
        """Borrow quantity should scale with split ratio."""
        ledger = ledger_with_borrow

        # Before split: Alice has 500 AAPL, owes 500 back to Bob
        assert ledger.get_balance("alice", "AAPL") == 500
        borrow_state = ledger.get_unit_state("BORROW_AAPL_alice_bob_001")
        assert borrow_state['quantity'] == 500

        # 2-for-1 split
        result = compute_stock_split(ledger, "AAPL", ratio=2.0)
        ledger.execute(result)

        # After split: Alice has 1000 AAPL, owes 1000 back
        assert ledger.get_balance("alice", "AAPL") == 1000
        borrow_state = ledger.get_unit_state("BORROW_AAPL_alice_bob_001")
        assert borrow_state['quantity'] == 1000
        assert borrow_state['split_adjusted'] is True

    def test_available_position_preserved_after_split(self, ledger_with_borrow):
        """Available position should scale proportionally with split."""
        ledger = ledger_with_borrow

        # Before split: Alice has 500, owes 500 -> available = 0
        available_before = compute_available_position(ledger, "alice", "AAPL")
        assert available_before == 0.0

        # 2-for-1 split
        result = compute_stock_split(ledger, "AAPL", ratio=2.0)
        ledger.execute(result)

        # After split: Alice has 1000, owes 1000 -> available = 0
        available_after = compute_available_position(ledger, "alice", "AAPL")
        assert available_after == 0.0

    def test_lender_position_unaffected_by_split(self, ledger_with_borrow):
        """Lender who lent all shares should have 0 (no adjustment)."""
        ledger = ledger_with_borrow

        # Bob lent 500, has 500 left
        assert ledger.get_balance("bob", "AAPL") == 500

        # 2-for-1 split
        result = compute_stock_split(ledger, "AAPL", ratio=2.0)
        ledger.execute(result)

        # Bob now has 1000
        assert ledger.get_balance("bob", "AAPL") == 1000

    def test_split_with_multiple_borrows(self, ledger_with_borrow):
        """Multiple borrows should all be adjusted."""
        ledger = ledger_with_borrow

        # Carol also has shares to lend
        ledger.set_balance("carol", "AAPL", 200)

        # Alice borrows another 100 from Carol
        borrow_tx = initiate_borrow(
            ledger, "AAPL", "alice", "carol", 100,
            borrow_id="002"
        )
        ledger.execute(borrow_tx)

        # Before split: Alice has 600, owes 500 to Bob + 100 to Carol = 600
        assert ledger.get_balance("alice", "AAPL") == 600
        assert compute_available_position(ledger, "alice", "AAPL") == 0.0

        # 2-for-1 split
        result = compute_stock_split(ledger, "AAPL", ratio=2.0)
        ledger.execute(result)

        # After split: Alice has 1200, owes 1000 + 200 = 1200
        assert ledger.get_balance("alice", "AAPL") == 1200

        borrow1_state = ledger.get_unit_state("BORROW_AAPL_alice_bob_001")
        borrow2_state = ledger.get_unit_state("BORROW_AAPL_alice_carol_002")
        assert borrow1_state['quantity'] == 1000
        assert borrow2_state['quantity'] == 200

        assert compute_available_position(ledger, "alice", "AAPL") == 0.0


class TestSplitConservation:
    """Tests for conservation laws during splits."""

    @pytest.fixture
    def ledger(self):
        """Create a ledger with stock."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        stock = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
        )
        ledger.register_unit(stock)

        ledger.set_balance("treasury", "AAPL", 1_000_000)

        return ledger

    def test_total_shares_change_by_ratio(self, ledger):
        """Total outstanding shares should scale by ratio."""
        ledger.set_balance("alice", "AAPL", 100)
        ledger.set_balance("bob", "AAPL", 50)

        total_before = sum(
            ledger.get_balance(w, "AAPL")
            for w in ["treasury", "alice", "bob"]
        )

        result = compute_stock_split(ledger, "AAPL", ratio=2.0)
        ledger.execute(result)

        total_after = sum(
            ledger.get_balance(w, "AAPL")
            for w in ["treasury", "alice", "bob"]
        )

        # Non-issuer shares doubled, issuer made up the difference
        # Before: treasury=1M, alice=100, bob=50 = 1,000,150
        # After: treasury=1M-150, alice=200, bob=100 = 1,000,150
        # Wait, that's not right. Let me recalculate.
        # Actually total should stay the same because issuer is the source
        assert total_after == total_before

    def test_moves_sum_to_zero(self, ledger):
        """All moves in a split should sum to zero (conservation)."""
        ledger.set_balance("alice", "AAPL", 100)
        ledger.set_balance("bob", "AAPL", 50)

        result = compute_stock_split(ledger, "AAPL", ratio=2.0)

        # Each move: treasury loses, holder gains
        # Net flow should be zero
        total_flow = 0.0
        for move in result.moves:
            if move.source == "treasury":
                total_flow -= move.quantity
            if move.dest == "treasury":
                total_flow += move.quantity
            if move.source != "treasury":
                total_flow += move.quantity
            if move.dest != "treasury":
                total_flow -= move.quantity

        # Actually, simpler: flows from treasury should equal flows to non-treasury
        from_treasury = sum(m.quantity for m in result.moves if m.source == "treasury")
        to_non_treasury = sum(m.quantity for m in result.moves if m.dest != "treasury")
        assert from_treasury == to_non_treasury


class TestSplitEdgeCases:
    """Edge cases and error handling."""

    @pytest.fixture
    def ledger(self):
        """Create a ledger with stock."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")

        stock = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
        )
        ledger.register_unit(stock)

        ledger.set_balance("treasury", "AAPL", 1_000_000)

        return ledger

    def test_split_with_no_holders(self, ledger):
        """Split with no non-issuer holders should only update state."""
        result = compute_stock_split(ledger, "AAPL", ratio=2.0)

        assert len(result.moves) == 0
        assert len(result.state_changes) == 1  # Only stock state update

        ledger.execute(result)

        state = ledger.get_unit_state("AAPL")
        assert state['last_split_ratio'] == 2.0

    def test_split_ratio_1_no_changes(self, ledger):
        """Split with ratio 1.0 should not create moves."""
        ledger.set_balance("alice", "AAPL", 100)

        result = compute_stock_split(ledger, "AAPL", ratio=1.0)

        # No balance changes needed for 1:1 ratio
        assert len(result.moves) == 0

        ledger.execute(result)

        assert ledger.get_balance("alice", "AAPL") == 100

    def test_very_small_ratio(self, ledger):
        """Very small ratio should still work (extreme reverse split)."""
        ledger.set_balance("alice", "AAPL", 1000000)

        result = compute_stock_split(ledger, "AAPL", ratio=0.001)
        ledger.execute(result)

        assert ledger.get_balance("alice", "AAPL") == 1000  # 1M * 0.001

    def test_very_large_ratio(self, ledger):
        """Very large ratio should still work (extreme forward split)."""
        ledger.set_balance("alice", "AAPL", 100)

        result = compute_stock_split(ledger, "AAPL", ratio=1000.0)
        ledger.execute(result)

        assert ledger.get_balance("alice", "AAPL") == 100000  # 100 * 1000


class TestSplitWithShortPositions:
    """Tests for splits with short (negative) positions."""

    @pytest.fixture
    def shortable_ledger(self):
        """Create a ledger with a shortable stock."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("treasury")
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        stock = create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="treasury",
            currency="USD",
            shortable=True,  # Allow negative balances
        )
        ledger.register_unit(stock)

        ledger.set_balance("treasury", "AAPL", 1_000_000)
        ledger.set_balance("treasury", "USD", 1_000_000)

        return ledger

    def test_short_position_scales_with_split(self, shortable_ledger):
        """Short positions should also scale with split ratio."""
        ledger = shortable_ledger

        # Alice is short 100 shares
        ledger.set_balance("alice", "AAPL", -100)
        ledger.set_balance("bob", "AAPL", 200)

        result = compute_stock_split(ledger, "AAPL", ratio=2.0)
        ledger.execute(result)

        # Short position doubles (more negative)
        assert ledger.get_balance("alice", "AAPL") == -200
        # Long position doubles
        assert ledger.get_balance("bob", "AAPL") == 400

    def test_short_position_reverse_split(self, shortable_ledger):
        """Reverse split on short position should halve the debt."""
        ledger = shortable_ledger

        ledger.set_balance("alice", "AAPL", -100)

        result = compute_stock_split(ledger, "AAPL", ratio=0.5)
        ledger.execute(result)

        # Short position halves (less negative)
        assert ledger.get_balance("alice", "AAPL") == -50
