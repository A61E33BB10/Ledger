#!/usr/bin/env python3
"""
future_demo_real.py - Futures Demo Using Real Ledger Infrastructure

This script demonstrates the complete lifecycle of a futures contract
using the actual Ledger system, not a simplified mock.

Showcases:
1. Ledger setup with cash and futures units
2. Trading (buy/sell with algebraic quantities)
3. Daily mark-to-market settlement
4. Multi-holder scenarios (Alice profits, Bob loses)
5. Position closing
6. Expiry settlement
7. LifecycleEngine integration

Run with: python future_demo_real.py
"""

from datetime import datetime
from ledger import (
    Ledger,
    cash,
    create_future,
    future_transact,
    future_mark_to_market,
    future_contract,
    LifecycleEngine,
)


def print_separator(title: str):
    """Print a section separator."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_state(ledger: Ledger, symbol: str):
    """Print the current state of the futures contract and all participants."""
    state = ledger.get_unit_state(symbol)
    ch = state['clearinghouse']
    mult = state['multiplier']
    currency = state['currency']
    wallets_state = state.get('wallets', {})

    print(f"\n  --- {symbol} State ---")

    # Show wallet states
    print(f"\n  Wallet States:")
    for wallet in sorted(wallets_state.keys()):
        if wallet == ch:
            continue
        w = wallets_state[wallet]
        pos = w.get('position', 0)
        vcash = w.get('virtual_cash', 0)
        print(f"    {wallet:12}: position={pos:+6.0f}, virtual_cash={vcash:+15,.0f}")

    # Show clearinghouse state
    ch_state = wallets_state.get(ch, {})
    print(f"\n  Clearinghouse ({ch}):")
    print(f"    position:     {ch_state.get('position', 0):+.0f}")
    print(f"    virtual_cash: {ch_state.get('virtual_cash', 0):+,.0f}")

    # Show cash balances
    print(f"\n  Cash Balances ({currency}):")
    all_wallets = set(wallets_state.keys()) | {ch}
    for wallet in ['alice', 'bob', 'charlie', ch]:
        if wallet in ledger.registered_wallets:
            balance = ledger.get_balance(wallet, currency)
            print(f"    {wallet:12}: {balance:+15,.2f}")

    # Zero-sum checks
    total_pos = sum(w.get('position', 0) for w in wallets_state.values())
    total_vcash = sum(w.get('virtual_cash', 0) for w in wallets_state.values())

    print(f"\n  Zero-Sum Invariants:")
    print(f"    Sum of positions:    {total_pos:+.0f} (should be 0)")
    print(f"    Sum of virtual_cash: {total_vcash:+,.0f} (should be 0)")

    if state.get('last_settle_price'):
        print(f"\n  Last Settlement: {state['last_settle_price']:,.2f} on {state.get('last_settle_date')}")
    if state.get('settled'):
        print(f"  CONTRACT SETTLED at {state.get('settlement_price'):,.2f}")


def main():
    print("""
================================================================================
              FUTURES DEMO - REAL LEDGER INFRASTRUCTURE
================================================================================

This demo uses the actual Ledger system to demonstrate exchange-traded
futures with daily mark-to-market settlement.

Contract: ESZ24 (E-mini S&P 500 December 2024)
Multiplier: $50 per index point
Participants: Alice, Bob, Charlie, CME (clearinghouse)
""")

    # =========================================================================
    # SETUP
    # =========================================================================
    print_separator("SETUP: Creating Ledger and Registering Units")

    expiry = datetime(2024, 12, 20, 16, 0, 0)  # Dec 20, 2024 4pm
    ledger = Ledger("futures_demo", datetime(2024, 11, 1), verbose=False)

    # Register cash unit
    ledger.register_unit(cash("USD", "US Dollar"))

    # Register futures contract
    ledger.register_unit(create_future(
        symbol="ESZ24",
        name="E-mini S&P 500 Dec 2024",
        underlying="SPX",
        expiry=expiry,
        multiplier=50.0,
        currency="USD",
        clearinghouse="CME"
    ))

    # Register wallets
    for wallet in ["alice", "bob", "charlie", "CME"]:
        ledger.register_wallet(wallet)

    # Fund accounts with cash
    ledger.set_balance("alice", "USD", 500_000)
    ledger.set_balance("bob", "USD", 500_000)
    ledger.set_balance("charlie", "USD", 500_000)
    ledger.set_balance("CME", "USD", 50_000_000)  # Clearinghouse has deep pockets

    print(f"  Created ledger: {ledger.name}")
    print(f"  Registered units: {ledger.list_units()}")
    print(f"  Registered wallets: {sorted(ledger.registered_wallets)}")
    print(f"  Contract expiry: {expiry}")

    print_state(ledger, "ESZ24")

    # =========================================================================
    # DAY 1: Initial Trading
    # =========================================================================
    print_separator("DAY 1: Initial Trading (Nov 1, 2024)")

    print("""
  Alice goes LONG 10 contracts at 4500 (bullish)
  Bob goes SHORT 5 contracts at 4500 (bearish)
  Charlie goes LONG 3 contracts at 4510 (late entry)
""")

    # Alice buys 10 contracts
    result = future_transact(ledger, "ESZ24", "alice", qty=10, price=4500.0)
    ledger.execute_contract(result)
    print(f"  Alice buys 10 @ 4500: virtual_cash = {ledger.get_unit_state('ESZ24')['wallets']['alice']['virtual_cash']:+,.0f}")

    # Bob sells 5 contracts (goes short)
    result = future_transact(ledger, "ESZ24", "bob", qty=-5, price=4500.0)
    ledger.execute_contract(result)
    print(f"  Bob sells 5 @ 4500:   virtual_cash = {ledger.get_unit_state('ESZ24')['wallets']['bob']['virtual_cash']:+,.0f}")

    # Charlie buys 3 contracts at slightly higher price
    result = future_transact(ledger, "ESZ24", "charlie", qty=3, price=4510.0)
    ledger.execute_contract(result)
    print(f"  Charlie buys 3 @ 4510: virtual_cash = {ledger.get_unit_state('ESZ24')['wallets']['charlie']['virtual_cash']:+,.0f}")

    print_state(ledger, "ESZ24")

    # =========================================================================
    # DAY 1 CLOSE: Mark-to-Market at 4520
    # =========================================================================
    print_separator("DAY 1 CLOSE: MTM at 4520 (price up $20)")

    print("""
  Settlement price: 4520

  Expected variation margin:
    Alice (long 10): (4520-4500) * 10 * 50 = +$10,000
    Bob (short 5):   (4520-4500) * -5 * 50 = -$5,000
    Charlie (long 3): (4520-4510) * 3 * 50 = +$1,500
""")

    result = future_mark_to_market(ledger, "ESZ24", price=4520.0, settle_date=datetime(2024, 11, 1).date())
    ledger.execute_contract(result)

    print(f"  Moves executed: {len(result.moves)}")
    for move in result.moves:
        print(f"    {move.source} -> {move.dest}: ${move.quantity:,.0f}")

    print_state(ledger, "ESZ24")

    # =========================================================================
    # DAY 2: Price drops, Bob profits
    # =========================================================================
    print_separator("DAY 2 CLOSE: MTM at 4480 (price down $40)")

    print("""
  Settlement price: 4480 (down $40 from yesterday's 4520)

  Expected variation margin:
    Alice (long 10): (4480-4520) * 10 * 50 = -$20,000
    Bob (short 5):   (4480-4520) * -5 * 50 = +$10,000
    Charlie (long 3): (4480-4520) * 3 * 50 = -$6,000
""")

    ledger.advance_time(datetime(2024, 11, 2))
    result = future_mark_to_market(ledger, "ESZ24", price=4480.0, settle_date=datetime(2024, 11, 2).date())
    ledger.execute_contract(result)

    print(f"  Moves executed: {len(result.moves)}")
    for move in result.moves:
        direction = "receives" if move.dest != "CME" else "pays"
        party = move.dest if move.dest != "CME" else move.source
        print(f"    {party} {direction} ${move.quantity:,.0f}")

    print_state(ledger, "ESZ24")

    # =========================================================================
    # DAY 3: Bob closes his short position
    # =========================================================================
    print_separator("DAY 3: Bob Closes Short (buys 5 @ 4490)")

    print("""
  Bob decides to take his profit and close his short position.
  He buys 5 contracts at 4490 to close.
""")

    ledger.advance_time(datetime(2024, 11, 3))

    result = future_transact(ledger, "ESZ24", "bob", qty=5, price=4490.0)
    ledger.execute_contract(result)

    bob_state = ledger.get_unit_state('ESZ24')['wallets'].get('bob', {})
    print(f"  Bob buys 5 @ 4490")
    print(f"  Bob's position: {bob_state.get('position', 0)}")
    print(f"  Bob's virtual_cash: {bob_state.get('virtual_cash', 0):+,.0f}")

    # End of day MTM at 4495
    print(f"\n  Day 3 MTM at 4495:")
    result = future_mark_to_market(ledger, "ESZ24", price=4495.0, settle_date=datetime(2024, 11, 3).date())
    ledger.execute_contract(result)

    for move in result.moves:
        direction = "receives" if move.dest != "CME" else "pays"
        party = move.dest if move.dest != "CME" else move.source
        print(f"    {party} {direction} ${move.quantity:,.0f}")

    print_state(ledger, "ESZ24")

    # =========================================================================
    # EXPIRY: Contract settles at 4550
    # =========================================================================
    print_separator("EXPIRY: Dec 20, 2024 - Final Settlement at 4550")

    print("""
  Contract expires. Final settlement at 4550.

  Remaining positions:
    Alice: Long 10 contracts
    Charlie: Long 3 contracts
""")

    ledger.advance_time(expiry)

    # Use future_contract which handles both MTM and expiry
    result = future_contract(ledger, "ESZ24", expiry, {"SPX": 4550.0})
    ledger.execute_contract(result)

    print(f"  Moves executed: {len(result.moves)}")
    for move in result.moves:
        direction = "receives" if move.dest != "CME" else "pays"
        party = move.dest if move.dest != "CME" else move.source
        print(f"    {party} {direction} ${move.quantity:,.0f}")

    print_state(ledger, "ESZ24")

    # =========================================================================
    # FINAL P&L SUMMARY
    # =========================================================================
    print_separator("FINAL P&L SUMMARY")

    initial_cash = 500_000

    alice_cash = ledger.get_balance("alice", "USD")
    bob_cash = ledger.get_balance("bob", "USD")
    charlie_cash = ledger.get_balance("charlie", "USD")
    cme_cash = ledger.get_balance("CME", "USD")

    alice_pnl = alice_cash - initial_cash
    bob_pnl = bob_cash - initial_cash
    charlie_pnl = charlie_cash - initial_cash

    print(f"""
  Alice:
    Initial cash:  ${initial_cash:>12,.0f}
    Final cash:    ${alice_cash:>12,.0f}
    P&L:           ${alice_pnl:>+12,.0f}
    Trades: Bought 10 @ 4500, held to expiry @ 4550
    Expected: 10 * (4550-4500) * 50 = +$25,000

  Bob:
    Initial cash:  ${initial_cash:>12,.0f}
    Final cash:    ${bob_cash:>12,.0f}
    P&L:           ${bob_pnl:>+12,.0f}
    Trades: Sold 5 @ 4500, bought back @ 4490
    Expected: 5 * (4500-4490) * 50 = +$2,500

  Charlie:
    Initial cash:  ${initial_cash:>12,.0f}
    Final cash:    ${charlie_cash:>12,.0f}
    P&L:           ${charlie_pnl:>+12,.0f}
    Trades: Bought 3 @ 4510, held to expiry @ 4550
    Expected: 3 * (4550-4510) * 50 = +$6,000

  Total P&L: ${alice_pnl + bob_pnl + charlie_pnl:+,.0f}
  (Should net to CME's loss, which is the counterparty)

  CME (Clearinghouse):
    Initial cash:  $50,000,000
    Final cash:    ${cme_cash:>12,.0f}
    Change:        ${cme_cash - 50_000_000:>+12,.0f}
""")

    # Verify conservation
    total_cash = alice_cash + bob_cash + charlie_cash + cme_cash
    initial_total = 500_000 * 3 + 50_000_000
    print(f"  Cash Conservation Check:")
    print(f"    Initial total: ${initial_total:,.0f}")
    print(f"    Final total:   ${total_cash:,.0f}")
    print(f"    Difference:    ${total_cash - initial_total:,.0f} (should be 0)")

    # =========================================================================
    # LIFECYCLE ENGINE DEMO
    # =========================================================================
    print_separator("BONUS: LifecycleEngine Integration")

    print("""
  The LifecycleEngine can automate daily MTM for all futures contracts.
  Here's how it would be used:
""")

    print("""
  # Setup
  engine = LifecycleEngine(ledger)
  engine.register("FUTURE", future_contract)

  # Daily processing
  for date in trading_days:
      ledger.advance_time(date)
      prices = get_market_prices(date)  # {"SPX": 4520.0, ...}
      engine.step(date, prices)

  # The engine automatically:
  # - Finds all FUTURE-type units
  # - Calls future_contract() for each
  # - Which performs MTM and handles expiry
""")

    print("\n" + "="*70)
    print("  DEMO COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
