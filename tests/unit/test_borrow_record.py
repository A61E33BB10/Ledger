"""
test_borrow_record.py - Tests for Securities Borrowing and Lending (SBL)

Tests:
- BorrowRecord creation and validation
- Available position computation
- Short sale validation
- Borrow initiation and return
- Recall management
- Fee calculation
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from ledger import (
    Ledger, cash, Move, build_transaction,
    create_stock_unit, create_borrow_record_unit,
    initiate_borrow, compute_borrow_return, initiate_recall,
    compute_available_position, validate_short_sale,
    compute_borrow_fee, compute_required_collateral,
    get_active_borrows, get_total_borrowed,
    BorrowStatus, BorrowContractType,
    UNIT_TYPE_BORROW_RECORD,
)


# =============================================================================
# PURE FUNCTION TESTS
# =============================================================================

class TestComputeBorrowFee:
    """Tests for compute_borrow_fee pure function."""

    def test_basic_fee_calculation(self):
        """Standard fee calculation."""
        # 1000 shares at $100, 50 bps rate, 30 days
        # Fee = 1000 * 100 * (50/10000) * (30/365) = $41.10
        fee = compute_borrow_fee(
            quantity=Decimal("1000"),
            rate_bps=50,
            days=30,
            price=Decimal("100.0"),
        )
        expected = Decimal("1000") * Decimal("100") * (Decimal("50") / Decimal("10000")) * (Decimal("30") / Decimal("365"))
        assert abs(float(fee) - float(expected)) < 0.01

    def test_zero_quantity(self):
        """Zero quantity returns zero fee."""
        fee = compute_borrow_fee(0, 50, 30, 100.0)
        assert fee == Decimal("0.0")

    def test_zero_days(self):
        """Zero days returns zero fee."""
        fee = compute_borrow_fee(1000, 50, 0, 100.0)
        assert fee == Decimal("0.0")

    def test_annual_fee(self):
        """Full year at 100 bps = 1% of notional."""
        fee = compute_borrow_fee(
            quantity=Decimal("1000"),
            rate_bps=100,
            days=365,
            price=Decimal("100.0"),
        )
        # 1000 * 100 * 1% = $1000
        assert abs(float(fee) - 1000.0) < 0.01


class TestComputeRequiredCollateral:
    """Tests for compute_required_collateral pure function."""

    def test_standard_margin(self):
        """102% margin calculation."""
        collateral = compute_required_collateral(
            quantity=Decimal("1000"),
            price=100.0,
            margin=1.02,
        )
        assert collateral == Decimal("102000.0")

    def test_htb_margin(self):
        """105% margin for hard-to-borrow."""
        collateral = compute_required_collateral(
            quantity=Decimal("1000"),
            price=100.0,
            margin=1.05,
        )
        assert collateral == Decimal("105000.0")

    def test_zero_quantity(self):
        """Zero quantity returns zero collateral."""
        collateral = compute_required_collateral(0, Decimal("100.0"))
        assert collateral == Decimal("0.0")


# =============================================================================
# BORROW RECORD CREATION TESTS
# =============================================================================

class TestCreateBorrowRecordUnit:
    """Tests for create_borrow_record_unit factory."""

    def test_basic_creation(self):
        """Create a basic borrow record."""
        borrow = create_borrow_record_unit(
            stock_symbol="AAPL",
            borrower="alice",
            lender="bob",
            quantity=Decimal("1000"),
            borrow_date=datetime(2024, 3, 15),
        )

        assert borrow.unit_type == UNIT_TYPE_BORROW_RECORD
        assert "BORROW_AAPL_alice_bob" in borrow.symbol

        state = borrow.state
        assert state['stock_symbol'] == "AAPL"
        assert state['borrower'] == "alice"
        assert state['lender'] == "bob"
        assert state['quantity'] == 1000
        assert state['status'] == BorrowStatus.ACTIVE.value

    def test_with_custom_rate(self):
        """Create with custom borrow rate."""
        borrow = create_borrow_record_unit(
            stock_symbol="GME",
            borrower="alice",
            lender="bob",
            quantity=Decimal("100"),
            borrow_date=datetime(2024, 3, 15),
            rate_bps=500,  # 5% for hard-to-borrow
        )

        assert borrow.state['rate_bps'] == 500

    def test_term_contract(self):
        """Create a term borrow (fixed duration)."""
        borrow = create_borrow_record_unit(
            stock_symbol="AAPL",
            borrower="alice",
            lender="bob",
            quantity=Decimal("1000"),
            borrow_date=datetime(2024, 3, 15),
            contract_type=BorrowContractType.TERM,
            term_end_date=datetime(2024, 6, 15),
        )

        assert borrow.state['contract_type'] == BorrowContractType.TERM.value
        assert borrow.state['term_end_date'] == datetime(2024, 6, 15)

    def test_invalid_quantity(self):
        """Zero or negative quantity raises error."""
        with pytest.raises(ValueError, match="positive"):
            create_borrow_record_unit(
                stock_symbol="AAPL",
                borrower="alice",
                lender="bob",
                quantity=Decimal("0"),
                borrow_date=datetime(2024, 3, 15),
            )

    def test_same_borrower_lender(self):
        """Cannot borrow from self."""
        with pytest.raises(ValueError, match="different"):
            create_borrow_record_unit(
                stock_symbol="AAPL",
                borrower="alice",
                lender="alice",
                quantity=Decimal("1000"),
                borrow_date=datetime(2024, 3, 15),
            )


# =============================================================================
# AVAILABLE POSITION TESTS
# =============================================================================

class TestComputeAvailablePosition:
    """Tests for compute_available_position pure function."""

    @pytest.fixture
    def ledger_with_stock(self):
        """Create a ledger with stock for testing."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        stock = create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True)
        ledger.register_unit(stock)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("treasury", "USD", 1_000_000)
        ledger.set_balance("treasury", "AAPL", 10_000)

        return ledger

    def test_owned_shares_only(self, ledger_with_stock):
        """Available = owned when no borrows."""
        ledger = ledger_with_stock
        ledger.set_balance("alice", "AAPL", Decimal("1000"))

        available = compute_available_position(ledger, "alice", "AAPL")
        assert available == Decimal("1000.0")

    def test_with_borrow_obligation(self, ledger_with_stock):
        """Available = owned - borrowed obligations."""
        ledger = ledger_with_stock

        # Alice borrows 500 AAPL from Bob
        ledger.set_balance("bob", "AAPL", Decimal("500"))
        ledger.advance_time(datetime(2024, 1, 2))

        result = initiate_borrow(ledger, "AAPL", "alice", "bob", 500)
        ledger.execute(result)

        # Alice now has 500 AAPL but owes 500 back
        assert ledger.get_balance("alice", "AAPL") == Decimal("500.0")
        available = compute_available_position(ledger, "alice", "AAPL")
        assert available == Decimal("0.0")  # 500 owned - 500 owed = 0 available

    def test_multiple_borrows(self, ledger_with_stock):
        """Multiple borrows sum up obligations."""
        ledger = ledger_with_stock

        # Alice borrows from multiple lenders
        ledger.set_balance("bob", "AAPL", Decimal("1000"))
        ledger.set_balance("treasury", "AAPL", Decimal("10000"))

        ledger.advance_time(datetime(2024, 1, 2))
        result1 = initiate_borrow(ledger, "AAPL", "alice", "bob", 300, borrow_id="001")
        ledger.execute(result1)

        ledger.advance_time(datetime(2024, 1, 3))
        result2 = initiate_borrow(ledger, "AAPL", "alice", "treasury", 200, borrow_id="002")
        ledger.execute(result2)

        # Alice has 500 AAPL, owes 500 back total
        assert ledger.get_balance("alice", "AAPL") == Decimal("500.0")
        available = compute_available_position(ledger, "alice", "AAPL")
        assert available == Decimal("0.0")

    def test_partial_return_restores_availability(self, ledger_with_stock):
        """Returning borrowed shares restores availability."""
        ledger = ledger_with_stock

        # Alice borrows 500 from Bob
        ledger.set_balance("bob", "AAPL", Decimal("500"))
        ledger.advance_time(datetime(2024, 1, 2))

        result = initiate_borrow(ledger, "AAPL", "alice", "bob", 500)
        ledger.execute(result)

        # Alice returns the shares
        ledger.advance_time(datetime(2024, 1, 5))
        borrow_symbol = get_active_borrows(ledger, "alice", "AAPL")[0]
        return_result = compute_borrow_return(ledger, borrow_symbol, ledger.current_time, 150.0)
        ledger.execute(return_result)

        # Alice has 0 AAPL, owes 0
        assert ledger.get_balance("alice", "AAPL") == Decimal("0.0")
        available = compute_available_position(ledger, "alice", "AAPL")
        assert available == Decimal("0.0")


# =============================================================================
# SHORT SALE VALIDATION TESTS
# =============================================================================

class TestValidateShortSale:
    """Tests for validate_short_sale pure function."""

    @pytest.fixture
    def ledger_with_stock(self):
        """Create a ledger with stock for testing."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        stock = create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True)
        ledger.register_unit(stock)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("treasury", "USD", 1_000_000)
        ledger.set_balance("treasury", "AAPL", 10_000)

        return ledger

    def test_sufficient_owned_shares(self, ledger_with_stock):
        """Can sell when owning sufficient shares."""
        ledger = ledger_with_stock
        ledger.set_balance("alice", "AAPL", Decimal("1000"))

        is_valid, reason = validate_short_sale(ledger, "alice", "AAPL", 500)
        assert is_valid is True

    def test_insufficient_available(self, ledger_with_stock):
        """Cannot sell more than available."""
        ledger = ledger_with_stock
        ledger.set_balance("alice", "AAPL", Decimal("100"))

        is_valid, reason = validate_short_sale(ledger, "alice", "AAPL", 500)
        assert is_valid is False
        assert "Insufficient" in reason

    def test_borrowed_shares_available(self, ledger_with_stock):
        """Cannot sell borrowed shares (they're owed back)."""
        ledger = ledger_with_stock

        # Alice borrows 500 from Bob
        ledger.set_balance("bob", "AAPL", Decimal("500"))
        ledger.advance_time(datetime(2024, 1, 2))

        result = initiate_borrow(ledger, "AAPL", "alice", "bob", 500)
        ledger.execute(result)

        # Alice has 500 AAPL but available is 0
        is_valid, reason = validate_short_sale(ledger, "alice", "AAPL", 100)
        assert is_valid is False
        assert "Insufficient" in reason

    def test_owned_plus_borrowed(self, ledger_with_stock):
        """Can sell owned shares even with borrows outstanding."""
        ledger = ledger_with_stock

        # Alice owns 200, borrows 500 from Bob
        ledger.set_balance("alice", "AAPL", Decimal("200"))
        ledger.set_balance("bob", "AAPL", Decimal("500"))
        ledger.advance_time(datetime(2024, 1, 2))

        result = initiate_borrow(ledger, "AAPL", "alice", "bob", 500)
        ledger.execute(result)

        # Alice has 700 AAPL, owes 500, available = 200
        is_valid, reason = validate_short_sale(ledger, "alice", "AAPL", 200)
        assert is_valid is True

        # But cannot sell 300
        is_valid, reason = validate_short_sale(ledger, "alice", "AAPL", 300)
        assert is_valid is False


# =============================================================================
# BORROW INITIATION TESTS
# =============================================================================

class TestInitiateBorrow:
    """Tests for initiate_borrow function."""

    @pytest.fixture
    def ledger_with_stock(self):
        """Create a ledger with stock for testing."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        stock = create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True)
        ledger.register_unit(stock)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("treasury", "USD", 1_000_000)
        ledger.set_balance("bob", "AAPL", Decimal("1000"))

        return ledger

    def test_basic_borrow(self, ledger_with_stock):
        """Basic borrow transfers shares and creates record."""
        ledger = ledger_with_stock
        ledger.advance_time(datetime(2024, 1, 2))

        result = initiate_borrow(ledger, "AAPL", "alice", "bob", 500)

        # Check the pending transaction
        assert len(result.units_to_create) == 1  # BorrowRecord
        assert len(result.moves) == 2  # Shares + BorrowRecord assignment

        # Execute
        ledger.execute(result)

        # Verify balances
        assert ledger.get_balance("alice", "AAPL") == Decimal("500.0")
        assert ledger.get_balance("bob", "AAPL") == Decimal("500.0")

        # Verify BorrowRecord exists
        borrows = get_active_borrows(ledger, "alice", "AAPL")
        assert len(borrows) == 1

    def test_lender_insufficient_shares(self, ledger_with_stock):
        """Cannot borrow more than lender has."""
        ledger = ledger_with_stock

        with pytest.raises(ValueError, match="insufficient"):
            initiate_borrow(ledger, "AAPL", "alice", "bob", 2000)

    def test_borrow_record_state(self, ledger_with_stock):
        """Verify BorrowRecord state after creation."""
        ledger = ledger_with_stock
        ledger.advance_time(datetime(2024, 1, 2))

        result = initiate_borrow(ledger, "AAPL", "alice", "bob", 500, rate_bps=75)
        ledger.execute(result)

        borrow_symbol = get_active_borrows(ledger, "alice", "AAPL")[0]
        state = ledger.get_unit_state(borrow_symbol)

        assert state['stock_symbol'] == "AAPL"
        assert state['borrower'] == "alice"
        assert state['lender'] == "bob"
        assert state['quantity'] == 500
        assert state['rate_bps'] == 75
        assert state['status'] == BorrowStatus.ACTIVE.value


# =============================================================================
# BORROW RETURN TESTS
# =============================================================================

class TestComputeBorrowReturn:
    """Tests for compute_borrow_return function."""

    @pytest.fixture
    def ledger_with_borrow(self):
        """Create a ledger with an active borrow."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        stock = create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True)
        ledger.register_unit(stock)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("treasury", "USD", 1_000_000)
        ledger.set_balance("alice", "USD", 100_000)
        ledger.set_balance("bob", "AAPL", Decimal("1000"))

        # Initiate borrow
        ledger.advance_time(datetime(2024, 1, 2))
        result = initiate_borrow(ledger, "AAPL", "alice", "bob", 500, rate_bps=50)
        ledger.execute(result)

        return ledger

    def test_basic_return(self, ledger_with_borrow):
        """Return borrowed shares."""
        ledger = ledger_with_borrow

        # Advance time and return
        ledger.advance_time(datetime(2024, 1, 10))
        borrow_symbol = get_active_borrows(ledger, "alice", "AAPL")[0]

        result = compute_borrow_return(ledger, borrow_symbol, ledger.current_time, 150.0)
        ledger.execute(result)

        # Verify shares returned
        assert ledger.get_balance("alice", "AAPL") == Decimal("0.0")
        assert ledger.get_balance("bob", "AAPL") == Decimal("1000.0")

        # Verify borrow closed
        assert len(get_active_borrows(ledger, "alice", "AAPL")) == 0

        # Verify state updated
        state = ledger.get_unit_state(borrow_symbol)
        assert state['status'] == BorrowStatus.RETURNED.value

    def test_insufficient_shares_to_return(self, ledger_with_borrow):
        """Cannot return if borrower sold the shares."""
        ledger = ledger_with_borrow

        # Alice sells the borrowed shares (leaves her short)
        ledger.advance_time(datetime(2024, 1, 5))
        sell_tx = build_transaction(ledger, [
            Move(Decimal("500.0"), "AAPL", "alice", "treasury", "sell")
        ])
        ledger.execute(sell_tx)

        # Now Alice has 0 AAPL but owes 500
        assert ledger.get_balance("alice", "AAPL") == Decimal("0.0")

        # Cannot return
        borrow_symbol = get_active_borrows(ledger, "alice", "AAPL")[0]
        with pytest.raises(ValueError, match="insufficient"):
            compute_borrow_return(ledger, borrow_symbol, ledger.current_time, 150.0)


# =============================================================================
# RECALL TESTS
# =============================================================================

class TestInitiateRecall:
    """Tests for initiate_recall function."""

    @pytest.fixture
    def ledger_with_borrow(self):
        """Create a ledger with an active borrow."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        stock = create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True)
        ledger.register_unit(stock)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("bob", "AAPL", Decimal("1000"))

        ledger.advance_time(datetime(2024, 1, 2))
        result = initiate_borrow(ledger, "AAPL", "alice", "bob", 500)
        ledger.execute(result)

        return ledger

    def test_basic_recall(self, ledger_with_borrow):
        """Lender can recall shares."""
        ledger = ledger_with_borrow
        borrow_symbol = get_active_borrows(ledger, "alice", "AAPL")[0]

        ledger.advance_time(datetime(2024, 1, 10))
        result = initiate_recall(ledger, borrow_symbol, ledger.current_time)
        ledger.execute(result)

        state = ledger.get_unit_state(borrow_symbol)
        assert state['status'] == BorrowStatus.RECALLED.value
        assert state['recall_notice_date'] == datetime(2024, 1, 10)
        assert state['recall_due_date'] == datetime(2024, 1, 12)  # T+2


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================

class TestHelperFunctions:
    """Tests for helper functions."""

    @pytest.fixture
    def ledger_with_borrows(self):
        """Create a ledger with multiple borrows."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        for sym in ["AAPL", "GOOG"]:
            stock = create_stock_unit(sym, sym, "treasury", "USD", shortable=True)
            ledger.register_unit(stock)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("bob", "AAPL", Decimal("1000"))
        ledger.set_balance("bob", "GOOG", Decimal("500"))

        # Create multiple borrows
        ledger.advance_time(datetime(2024, 1, 2))
        result1 = initiate_borrow(ledger, "AAPL", "alice", "bob", 300, borrow_id="001")
        ledger.execute(result1)

        ledger.advance_time(datetime(2024, 1, 3))
        result2 = initiate_borrow(ledger, "AAPL", "alice", "bob", 200, borrow_id="002")
        ledger.execute(result2)

        ledger.advance_time(datetime(2024, 1, 4))
        result3 = initiate_borrow(ledger, "GOOG", "alice", "bob", 100, borrow_id="003")
        ledger.execute(result3)

        return ledger

    def test_get_active_borrows_all(self, ledger_with_borrows):
        """Get all active borrows for a wallet."""
        ledger = ledger_with_borrows
        borrows = get_active_borrows(ledger, "alice")
        assert len(borrows) == 3

    def test_get_active_borrows_by_stock(self, ledger_with_borrows):
        """Get borrows filtered by stock."""
        ledger = ledger_with_borrows
        aapl_borrows = get_active_borrows(ledger, "alice", "AAPL")
        assert len(aapl_borrows) == 2

        goog_borrows = get_active_borrows(ledger, "alice", "GOOG")
        assert len(goog_borrows) == 1

    def test_get_total_borrowed(self, ledger_with_borrows):
        """Get total borrowed quantity."""
        ledger = ledger_with_borrows

        total_aapl = get_total_borrowed(ledger, "alice", "AAPL")
        assert total_aapl == Decimal("500.0")  # 300 + 200

        total_goog = get_total_borrowed(ledger, "alice", "GOOG")
        assert total_goog == Decimal("100.0")


# =============================================================================
# INTEGRATION / LIFECYCLE TESTS
# =============================================================================

class TestBorrowLifecycle:
    """End-to-end tests for the full borrow lifecycle."""

    def test_full_lifecycle(self):
        """Test complete borrow -> short sell -> cover -> return cycle."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        stock = create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True)
        ledger.register_unit(stock)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("market")
        ledger.register_wallet("treasury")

        # Setup
        ledger.set_balance("bob", "AAPL", Decimal("1000"))
        ledger.set_balance("alice", "USD", 100_000)
        ledger.set_balance("market", "AAPL", 10_000)
        ledger.set_balance("market", "USD", 1_000_000)

        # Step 1: Alice borrows 500 AAPL from Bob
        ledger.advance_time(datetime(2024, 1, 2))
        borrow_result = initiate_borrow(ledger, "AAPL", "alice", "bob", 500)
        ledger.execute(borrow_result)

        assert ledger.get_balance("alice", "AAPL") == Decimal("500.0")
        assert compute_available_position(ledger, "alice", "AAPL") == 0.0

        # Step 2: Alice sells the borrowed shares (short sale)
        # She needs to own the shares first (which she got from borrowing)
        # But available is 0, so she can't sell more than she owns free
        # Actually, she CAN sell them - she just creates a naked position
        # The invariant is: after the sale, available must be >= 0

        # Let's simulate: Alice wants to sell to market
        # Her available is 0, so she can't do a "naked" short
        # But if she owns shares separately, she can sell those

        # Give Alice some owned shares
        ledger.set_balance("treasury", "AAPL", Decimal("1000"))
        tx = build_transaction(ledger, [
            Move(Decimal("200"), "AAPL", "treasury", "alice", "gift")
        ])
        ledger.execute(tx)

        # Now Alice has 700 AAPL (500 borrowed + 200 owned)
        # Available = 700 - 500 = 200
        assert ledger.get_balance("alice", "AAPL") == Decimal("700.0")
        assert compute_available_position(ledger, "alice", "AAPL") == 200.0

        # She can sell 200 (her owned shares)
        is_valid, _ = validate_short_sale(ledger, "alice", "AAPL", 200)
        assert is_valid is True

        sell_tx = build_transaction(ledger, [
            Move(Decimal("200"), "AAPL", "alice", "market", "sell"),
            Move(Decimal("30000"), "USD", "market", "alice", "proceeds"),  # $150/share
        ])
        ledger.execute(sell_tx)

        # After selling, Alice has 500 AAPL (700 - 200)
        assert ledger.get_balance("alice", "AAPL") == Decimal("500.0")

        # Step 3: Alice needs to return 500 shares to Bob
        # She already has exactly 500, so she can return now
        ledger.advance_time(datetime(2024, 1, 10))

        # Step 4: Alice returns borrowed shares
        borrow_symbol = get_active_borrows(ledger, "alice", "AAPL")[0]
        return_result = compute_borrow_return(ledger, borrow_symbol, ledger.current_time, 150.0)
        ledger.execute(return_result)

        # Verify final state
        assert ledger.get_balance("alice", "AAPL") == Decimal("0.0")
        assert ledger.get_balance("bob", "AAPL") == Decimal("1000.0")
        assert len(get_active_borrows(ledger, "alice", "AAPL")) == 0

        state = ledger.get_unit_state(borrow_symbol)
        assert state['status'] == BorrowStatus.RETURNED.value

    def test_conservation_of_shares(self):
        """Total shares remain constant through borrow cycle."""
        ledger = Ledger("test", datetime(2024, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        stock = create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True)
        ledger.register_unit(stock)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Initial: 1000 shares exist (bob has them all)
        ledger.set_balance("bob", "AAPL", Decimal("1000"))

        def total_shares():
            return sum(
                ledger.get_balance(w, "AAPL")
                for w in ["alice", "bob", "treasury", "system"]
            )

        assert total_shares() == 1000.0

        # Borrow: shares move but total unchanged
        ledger.advance_time(datetime(2024, 1, 2))
        result = initiate_borrow(ledger, "AAPL", "alice", "bob", 500)
        ledger.execute(result)

        assert total_shares() == 1000.0

        # Return: shares move back
        ledger.advance_time(datetime(2024, 1, 10))
        borrow_symbol = get_active_borrows(ledger, "alice", "AAPL")[0]
        return_result = compute_borrow_return(ledger, borrow_symbol, ledger.current_time)
        ledger.execute(return_result)

        assert total_shares() == 1000.0
