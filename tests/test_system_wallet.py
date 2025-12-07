"""
Tests for SYSTEM_WALLET constant and its special treatment in the ledger.

The system wallet is exempt from balance validation and can hold any balance,
enabling issuance, redemption, and obligation lifecycle operations.
"""

import pytest
from datetime import datetime

from ledger import Ledger, Move, cash
from ledger.core import SYSTEM_WALLET, UNIT_TYPE_CASH, UNIT_TYPE_STOCK, UNIT_TYPE_BILATERAL_OPTION


class TestSystemWalletConstant:
    """Test that the SYSTEM_WALLET constant is properly defined and exported."""

    def test_system_wallet_constant_exists(self):
        """SYSTEM_WALLET constant should be defined."""
        assert SYSTEM_WALLET == "system"

    def test_unit_type_constants_exist(self):
        """Unit type constants should be defined."""
        assert UNIT_TYPE_CASH == "CASH"
        assert UNIT_TYPE_STOCK == "STOCK"
        assert UNIT_TYPE_BILATERAL_OPTION == "BILATERAL_OPTION"


class TestSystemWalletBehavior:
    """Test that the system wallet is exempt from balance validation."""

    def test_system_wallet_can_go_negative(self):
        """System wallet can hold negative balances for issuance."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet(SYSTEM_WALLET)
        ledger.register_wallet("treasury")

        # Issuance: system wallet can go negative without limit
        tx = ledger.create_transaction([
            Move(SYSTEM_WALLET, "treasury", "USD", 1_000_000.0, "initial_issuance")
        ])
        result = ledger.execute(tx)

        assert result.value == "applied"
        assert ledger.get_balance(SYSTEM_WALLET, "USD") == -1_000_000.0
        assert ledger.get_balance("treasury", "USD") == 1_000_000.0

    def test_system_wallet_can_go_very_negative(self):
        """System wallet can exceed the normal minimum balance limits."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet(SYSTEM_WALLET)
        ledger.register_wallet("treasury")

        # Issue more than the default cash minimum balance
        # Default cash minimum is -1_000_000_000, but system wallet is exempt
        tx = ledger.create_transaction([
            Move(SYSTEM_WALLET, "treasury", "USD", 10_000_000_000.0, "large_issuance")
        ])
        result = ledger.execute(tx)

        assert result.value == "applied"
        assert ledger.get_balance(SYSTEM_WALLET, "USD") == -10_000_000_000.0

    def test_system_wallet_redemption(self):
        """System wallet can receive units back (redemption)."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet(SYSTEM_WALLET)
        ledger.register_wallet("alice")

        # Issuance
        tx1 = ledger.create_transaction([
            Move(SYSTEM_WALLET, "alice", "USD", 1000.0, "issuance")
        ])
        ledger.execute(tx1)

        # Redemption
        tx2 = ledger.create_transaction([
            Move("alice", SYSTEM_WALLET, "USD", 500.0, "redemption")
        ])
        result = ledger.execute(tx2)

        assert result.value == "applied"
        assert ledger.get_balance(SYSTEM_WALLET, "USD") == -500.0
        assert ledger.get_balance("alice", "USD") == 500.0

    def test_non_system_wallet_respects_limits(self):
        """Regular wallets still enforce balance constraints."""
        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        # Give alice some initial balance
        ledger.set_balance("alice", "USD", 1000.0)

        # Alice tries to spend more than the cash minimum balance allows
        # This should fail because alice is not the system wallet
        # Cash default min is -1_000_000_000, so spending 2 billion should fail
        tx = ledger.create_transaction([
            Move("alice", "bob", "USD", 2_000_000_000.0, "overspend")
        ])
        result = ledger.execute(tx)

        assert result.value == "rejected"
        assert ledger.get_balance("alice", "USD") == 1000.0

    def test_system_wallet_with_stock_unit(self):
        """System wallet works with stock units for issuance."""
        from ledger.units.stock import create_stock_unit

        ledger = Ledger("test", verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(
            create_stock_unit("AAPL", "Apple Inc", "treasury", "USD", shortable=False)
        )
        ledger.register_wallet(SYSTEM_WALLET)
        ledger.register_wallet("investor")

        # System wallet can issue stock (go negative on stock)
        tx = ledger.create_transaction([
            Move(SYSTEM_WALLET, "investor", "AAPL", 100.0, "stock_issuance")
        ])
        result = ledger.execute(tx)

        assert result.value == "applied"
        assert ledger.get_balance(SYSTEM_WALLET, "AAPL") == -100.0
        assert ledger.get_balance("investor", "AAPL") == 100.0

    def test_system_wallet_in_fast_mode(self):
        """System wallet exemption works in fast_mode too."""
        ledger = Ledger("test", verbose=False, fast_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet(SYSTEM_WALLET)
        ledger.register_wallet("treasury")

        # In fast mode, validation is skipped but system wallet should still work
        tx = ledger.create_transaction([
            Move(SYSTEM_WALLET, "treasury", "USD", 5_000_000_000.0, "issuance_fast")
        ])
        result = ledger.execute(tx)

        assert result.value == "applied"
        assert ledger.get_balance(SYSTEM_WALLET, "USD") == -5_000_000_000.0
