"""
Temporal Conformance Tests

INVARIANT: Time-based operations respect ordering and causality.

    ∀ events e1, e2:
        time(e1) < time(e2) ⟹ e1 happens-before e2 in log

This ensures:
- Events are ordered by time
- Time can only advance forward
- Transactions log their execution time
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from decimal import Decimal
from datetime import datetime, timedelta

from ledger import (
    Ledger, Move, ExecuteResult, cash, build_transaction,
    create_stock_unit,
)


class TestTemporalOrdering:
    """Tests for temporal ordering of events."""

    def test_transaction_log_ordered_by_execution(self):
        """Transaction log reflects execution order."""
        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("10000"))

        # Execute transactions
        for i in range(5):
            tx = build_transaction(ledger, [
                Move(Decimal("100"), "USD", "alice", "bob", f"tx_{i}")
            ])
            ledger.execute(tx)

        # Log should have 5 entries
        assert len(ledger.transaction_log) == 5

        # Each entry should contain the transaction
        for i, entry in enumerate(ledger.transaction_log):
            assert f"tx_{i}" in str(entry)

    def test_advance_time_updates_current_time(self):
        """advance_time updates ledger's current time."""
        start_time = datetime(2025, 1, 1, 0, 0, 0)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)

        assert ledger.current_time == start_time

        # Advance time
        new_time = datetime(2025, 1, 15, 12, 0, 0)
        ledger.advance_time(new_time)

        assert ledger.current_time == new_time

    def test_advance_time_rejects_past(self):
        """advance_time rejects times in the past."""
        start_time = datetime(2025, 1, 15, 0, 0, 0)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)

        past_time = datetime(2025, 1, 1, 0, 0, 0)

        with pytest.raises(ValueError, match="(?i)backward|Cannot move time"):
            ledger.advance_time(past_time)

    def test_transaction_timestamp_matches_execution_time(self):
        """Transactions log execution time."""
        start_time = datetime(2025, 1, 1, 0, 0, 0)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("1000"))

        tx = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "payment")
        ])
        ledger.execute(tx)

        # Transaction in log should have timestamp
        logged = ledger.transaction_log[0]
        assert logged.timestamp is not None
        # Timestamp should be >= start_time
        assert logged.timestamp >= start_time


class TestTemporalConsistency:
    """Tests for temporal consistency across operations."""

    def test_time_advances_monotonically(self):
        """Time can only advance forward."""
        start_time = datetime(2025, 1, 1, 0, 0, 0)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)

        times = [
            datetime(2025, 1, 2, 0, 0, 0),
            datetime(2025, 1, 3, 0, 0, 0),
            datetime(2025, 1, 4, 0, 0, 0),
        ]

        for t in times:
            ledger.advance_time(t)
            assert ledger.current_time == t

    def test_clone_preserves_current_time(self):
        """Clone preserves the current time."""
        start_time = datetime(2025, 1, 1, 0, 0, 0)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)

        # Advance time
        new_time = datetime(2025, 6, 15, 12, 0, 0)
        ledger.advance_time(new_time)

        clone = ledger.clone()

        assert clone.current_time == ledger.current_time

    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=20)
    def test_transactions_logged_with_ascending_times(self, num_txs):
        """Transactions are logged with non-decreasing timestamps."""
        start_time = datetime(2025, 1, 1, 0, 0, 0)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("100000"))

        for i in range(num_txs):
            # Advance time between some transactions
            if i > 0 and i % 3 == 0:
                ledger.advance_time(start_time + timedelta(days=i))

            tx = build_transaction(ledger, [
                Move(Decimal("100"), "USD", "alice", "bob", f"tx_{i}")
            ])
            ledger.execute(tx)

        # Verify timestamps are non-decreasing
        timestamps = [tx.timestamp for tx in ledger.transaction_log]
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i-1], \
                f"Timestamp {timestamps[i]} < {timestamps[i-1]}"


class TestTemporalBoundaryConditions:
    """Tests for temporal boundary conditions."""

    def test_same_time_advance_allowed(self):
        """Advancing to same time is allowed (no-op)."""
        start_time = datetime(2025, 1, 1, 0, 0, 0)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)

        # Advance to same time should work
        ledger.advance_time(start_time)
        assert ledger.current_time == start_time

    def test_microsecond_precision_preserved(self):
        """Microsecond precision is preserved in time."""
        start_time = datetime(2025, 1, 1, 12, 30, 45, 123456)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)

        assert ledger.current_time == start_time
        assert ledger.current_time.microsecond == 123456

    def test_initial_time_defaults_reasonably(self):
        """Ledger without initial time uses a default."""
        ledger = Ledger("test", verbose=False, test_mode=True)

        # Should have some default time
        assert ledger.current_time is not None
        assert isinstance(ledger.current_time, datetime)

    def test_time_affects_transaction_timestamp(self):
        """Advancing time affects subsequent transaction timestamps."""
        start_time = datetime(2025, 1, 1, 0, 0, 0)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.set_balance("alice", "USD", Decimal("10000"))

        # First transaction at start time
        tx1 = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "first")
        ])
        ledger.execute(tx1)

        # Advance time
        later_time = datetime(2025, 6, 15, 0, 0, 0)
        ledger.advance_time(later_time)

        # Second transaction at later time
        tx2 = build_transaction(ledger, [
            Move(Decimal("100"), "USD", "alice", "bob", "second")
        ])
        ledger.execute(tx2)

        # Timestamps should differ
        assert ledger.transaction_log[0].timestamp < ledger.transaction_log[1].timestamp


class TestTemporalWithUnits:
    """Tests for time-dependent unit behavior."""

    def test_option_maturity_checked_against_current_time(self):
        """Option maturity is validated against ledger time."""
        from ledger.units.option import create_option_unit

        start_time = datetime(2025, 1, 1, 0, 0, 0)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        maturity = datetime(2025, 6, 15, 0, 0, 0)
        option = create_option_unit(
            symbol="OPT001",
            name="Test Option",
            underlying="USD",
            strike=Decimal("100"),
            maturity=maturity,
            option_type="call",
            quantity=Decimal("100"),
            currency="USD",
            long_wallet="holder",
            short_wallet="issuer",
        )
        ledger.register_unit(option)

        ledger.register_wallet("issuer")
        ledger.register_wallet("holder")
        ledger.register_wallet("buyer")

        # The option unit state should have maturity info
        state = ledger.get_unit_state("OPT001")
        assert "maturity" in state

        # Verify time progresses correctly
        assert ledger.current_time == start_time

        # Advance past maturity
        ledger.advance_time(maturity + timedelta(days=1))
        assert ledger.current_time > maturity

    def test_bond_maturity_affects_state(self):
        """Bond maturity date is part of unit state."""
        from ledger.units.bond import create_bond_unit, Coupon

        start_time = datetime(2025, 1, 1, 0, 0, 0)
        ledger = Ledger("test", start_time, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        issue_date = datetime(2025, 1, 1, 0, 0, 0)
        maturity = datetime(2025, 12, 31, 0, 0, 0)

        # Create a simple coupon schedule
        coupon_schedule = [
            Coupon(
                payment_date=datetime(2025, 6, 30),
                amount=Decimal("25"),  # 5% annual on 1000 face, semi-annual
                currency="USD",
            ),
            Coupon(
                payment_date=maturity,
                amount=Decimal("25"),
                currency="USD",
            ),
        ]

        bond = create_bond_unit(
            symbol="BOND001",
            name="Test Bond",
            issuer_wallet="issuer",
            currency="USD",
            face_value=Decimal("1000"),
            maturity_date=maturity,
            issue_date=issue_date,
            coupon_schedule=coupon_schedule,
        )
        ledger.register_unit(bond)
        ledger.register_wallet("issuer")

        # Bond state should include maturity
        state = ledger.get_unit_state("BOND001")
        assert "maturity_date" in state or "maturity" in state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
