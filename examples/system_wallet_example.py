"""
Example: Using the SYSTEM_WALLET for issuance and redemption.

This example demonstrates Phase 1 implementation of the system wallet,
showing how it can be used for token issuance, redemption, and obligation
lifecycle without being subject to normal balance constraints.
"""

from datetime import datetime
from ledger import Ledger, Move, cash, build_transaction, SYSTEM_WALLET, UNIT_TYPE_CASH
from ledger.units.stock import create_stock_unit

def main():
    print("=" * 80)
    print("SYSTEM WALLET - Issuance and Redemption Example")
    print("=" * 80)
    print()

    # Create ledger
    ledger = Ledger("demo", initial_time=datetime(2024, 1, 1), verbose=True)

    # Register units
    ledger.register_unit(cash("USD", "US Dollar"))
    ledger.register_unit(
        create_stock_unit("AAPL", "Apple Inc", "treasury", "USD", shortable=False)
    )

    # Register wallets
    ledger.register_wallet(SYSTEM_WALLET)
    ledger.register_wallet("treasury")
    ledger.register_wallet("investor_a")
    ledger.register_wallet("investor_b")

    print()
    print("Example 1: Cash Issuance")
    print("-" * 80)
    print("The system wallet issues 10 million USD to the treasury.")
    print("This creates currency 'from nothing' - the system wallet goes negative.")
    print()

    tx1 = build_transaction(ledger, [
        Move(10_000_000.0, "USD", SYSTEM_WALLET, "treasury", "initial_cash_issuance")
    ])
    ledger.execute(tx1)

    print()
    print(f"System wallet USD balance: ${ledger.get_balance(SYSTEM_WALLET, 'USD'):,.2f}")
    print(f"Treasury USD balance: ${ledger.get_balance('treasury', 'USD'):,.2f}")
    print()

    print("Example 2: Stock Issuance")
    print("-" * 80)
    print("The system wallet issues 1000 shares of AAPL to investor_a.")
    print()

    tx2 = build_transaction(ledger, [
        Move(1000.0, "AAPL", SYSTEM_WALLET, "investor_a", "stock_issuance_a")
    ])
    ledger.execute(tx2)

    print()
    print(f"System wallet AAPL balance: {ledger.get_balance(SYSTEM_WALLET, 'AAPL'):,.2f}")
    print(f"Investor A AAPL balance: {ledger.get_balance('investor_a', 'AAPL'):,.2f}")
    print()

    print("Example 3: Additional Issuance")
    print("-" * 80)
    print("The system wallet issues another 500 shares to investor_b.")
    print()

    tx3 = build_transaction(ledger, [
        Move(500.0, "AAPL", SYSTEM_WALLET, "investor_b", "stock_issuance_b")
    ])
    ledger.execute(tx3)

    print()
    print(f"System wallet AAPL balance: {ledger.get_balance(SYSTEM_WALLET, 'AAPL'):,.2f}")
    print(f"Investor B AAPL balance: {ledger.get_balance('investor_b', 'AAPL'):,.2f}")
    print()

    print("Example 4: Stock Redemption (Buyback)")
    print("-" * 80)
    print("Investor A returns 300 shares to the system wallet (redemption).")
    print()

    tx4 = build_transaction(ledger, [
        Move(300.0, "AAPL", "investor_a", SYSTEM_WALLET, "stock_redemption")
    ])
    ledger.execute(tx4)

    print()
    print(f"System wallet AAPL balance: {ledger.get_balance(SYSTEM_WALLET, 'AAPL'):,.2f}")
    print(f"Investor A AAPL balance: {ledger.get_balance('investor_a', 'AAPL'):,.2f}")
    print()

    print("=" * 80)
    print("SUMMARY: System Wallet is Exempt from Balance Constraints")
    print("=" * 80)
    print()
    print("The system wallet now holds:")
    print(f"  USD:  ${ledger.get_balance(SYSTEM_WALLET, 'USD'):,.2f}")
    print(f"  AAPL: {ledger.get_balance(SYSTEM_WALLET, 'AAPL'):,.2f} shares")
    print()
    print("These negative balances represent issued tokens in circulation.")
    print("Total supply verification:")
    print(f"  USD total supply:  ${ledger.total_supply('USD'):,.2f}")
    print(f"  AAPL total supply: {ledger.total_supply('AAPL'):,.2f} shares")
    print()
    print("Note: A normal wallet would have been rejected for violating min_balance,")
    print("but the SYSTEM_WALLET is exempt from these constraints.")
    print()

    print("=" * 80)
    print("UNIT TYPE CONSTANTS")
    print("=" * 80)
    print()
    print("Phase 1 also introduces unit type constants for clarity:")
    print(f"  UNIT_TYPE_CASH = '{UNIT_TYPE_CASH}'")
    print()
    print("Available constants:")
    from ledger.core import (
        UNIT_TYPE_STOCK,
        UNIT_TYPE_BILATERAL_OPTION,
        UNIT_TYPE_BILATERAL_FORWARD,
        UNIT_TYPE_DEFERRED_CASH,
        UNIT_TYPE_DELTA_HEDGE_STRATEGY,
    )
    print(f"  UNIT_TYPE_STOCK = '{UNIT_TYPE_STOCK}'")
    print(f"  UNIT_TYPE_BILATERAL_OPTION = '{UNIT_TYPE_BILATERAL_OPTION}'")
    print(f"  UNIT_TYPE_BILATERAL_FORWARD = '{UNIT_TYPE_BILATERAL_FORWARD}'")
    print(f"  UNIT_TYPE_DEFERRED_CASH = '{UNIT_TYPE_DEFERRED_CASH}'")
    print(f"  UNIT_TYPE_DELTA_HEDGE_STRATEGY = '{UNIT_TYPE_DELTA_HEDGE_STRATEGY}'")
    print()


if __name__ == "__main__":
    main()
