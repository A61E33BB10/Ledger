#!/usr/bin/env python3
"""
future_demo.py - Educational Demo of Futures with Daily Mark-to-Market

This script demonstrates the complete lifecycle of a futures contract:
1. Contract creation
2. Trading (buy/sell between parties)
3. Daily mark-to-market settlement
4. Final expiry settlement

The goal is to make the math crystal clear.

=== THE VIRTUAL CASH MODEL ===

Each trader has:
    virtual_cash = sum of (-qty * price * mult) for all their trades
    position = net contracts held (from ledger balances)

At any moment:
    economic_value = virtual_cash + position * current_price * mult

On MTM at price P:
    target_vcash = -position * P * mult   # what vcash WOULD be if all trades were at P
    vm = virtual_cash - target_vcash      # settlement amount
    virtual_cash = target_vcash           # reset

This is equivalent to: position * (P - avg_entry_price) * mult
but without tracking average entry price explicitly.

Run with: python future_demo.py
"""

from datetime import datetime, date

# =============================================================================
# MINIMAL FUTURES IMPLEMENTATION (self-contained for educational clarity)
# =============================================================================

EPSILON = 1e-12


class SimpleLedger:
    """
    Minimal ledger that tracks positions and cash balances.
    In a real system, this would be the full Ledger class.
    """
    def __init__(self):
        self.positions = {}   # {symbol: {wallet: qty}}
        self.cash = {}        # {wallet: amount}
        self.futures = {}     # {symbol: state}

    def register_future(self, symbol, multiplier, currency, clearinghouse):
        """Create a futures contract."""
        self.futures[symbol] = {
            'multiplier': multiplier,
            'currency': currency,
            'clearinghouse': clearinghouse,
            'wallets': {},  # {wallet: {'position': float, 'virtual_cash': float}}
        }
        self.positions[symbol] = {}

    def get_position(self, symbol, wallet):
        return self.positions.get(symbol, {}).get(wallet, 0.0)

    def get_cash(self, wallet):
        return self.cash.get(wallet, 0.0)

    def trade(self, symbol, wallet, qty, price):
        """
        Execute a trade.
        qty > 0: wallet buys from clearinghouse
        qty < 0: wallet sells to clearinghouse
        """
        state = self.futures[symbol]
        mult = state['multiplier']
        ch = state['clearinghouse']
        wallets = state['wallets']

        # Update trader position and virtual_cash
        if symbol not in self.positions:
            self.positions[symbol] = {}
        old_pos = self.positions[symbol].get(wallet, 0.0)
        new_pos = old_pos + qty
        self.positions[symbol][wallet] = new_pos

        old_vcash = wallets.get(wallet, {}).get('virtual_cash', 0.0)
        vcash_change = -qty * price * mult
        new_vcash = old_vcash + vcash_change
        wallets[wallet] = {'position': new_pos, 'virtual_cash': new_vcash}

        # Update clearinghouse position and virtual_cash (opposite of trader)
        old_ch_pos = self.positions[symbol].get(ch, 0.0)
        ch_new_pos = old_ch_pos - qty
        self.positions[symbol][ch] = ch_new_pos

        ch_old_vcash = wallets.get(ch, {}).get('virtual_cash', 0.0)
        wallets[ch] = {'position': ch_new_pos, 'virtual_cash': ch_old_vcash - vcash_change}

        return new_vcash

    def mark_to_market(self, symbol, price):
        """
        Settle all positions to the given price.
        Returns dict of {wallet: vm_amount} for all settlements.

        We settle wallets with positions OR with virtual_cash (to handle
        wallets that closed their position but haven't been settled yet).
        """
        state = self.futures[symbol]
        mult = state['multiplier']
        ch = state['clearinghouse']
        wallets = state['wallets']
        settlements = {}

        # Settle all wallets that have either a position or virtual_cash
        wallets_to_settle = set(self.positions.get(symbol, {}).keys()) | set(wallets.keys())

        for wallet in wallets_to_settle:
            if wallet == ch:
                continue

            pos = self.positions.get(symbol, {}).get(wallet, 0.0)
            vcash = wallets.get(wallet, {}).get('virtual_cash', 0.0)

            # Skip if nothing to settle
            if abs(pos) < EPSILON and abs(vcash) < EPSILON:
                continue

            target_vcash = -pos * price * mult
            vm = vcash - target_vcash

            if abs(vm) > EPSILON:
                # Settle in cash
                self.cash[wallet] = self.cash.get(wallet, 0.0) + vm
                self.cash[ch] = self.cash.get(ch, 0.0) - vm
                settlements[wallet] = vm

            # Reset or remove wallet state
            if abs(pos) < EPSILON:
                wallets.pop(wallet, None)
            else:
                wallets[wallet] = {'position': pos, 'virtual_cash': target_vcash}

        # Update clearinghouse state to maintain zero-sum invariant
        ch_pos = self.positions.get(symbol, {}).get(ch, 0.0)
        ch_target_vcash = -ch_pos * price * mult
        wallets[ch] = {'position': ch_pos, 'virtual_cash': ch_target_vcash}

        return settlements


def print_state(ledger, symbol, title):
    """Print current state of all positions and cash."""
    state = ledger.futures[symbol]
    ch = state['clearinghouse']
    mult = state['multiplier']
    wallets = state['wallets']

    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

    # Show trader wallet states
    print(f"\n  Trader Wallet States ({symbol}):")
    for wallet in sorted(wallets.keys()):
        if wallet == ch:
            continue
        w_state = wallets[wallet]
        pos = w_state.get('position', 0.0)
        vcash = w_state.get('virtual_cash', 0.0)
        print(f"    {wallet:12}: position={pos:+8.0f}, virtual_cash={vcash:+,.0f}")

    # Show clearinghouse state
    print(f"\n  Clearinghouse State ({ch}):")
    ch_state = wallets.get(ch, {})
    ch_pos = ch_state.get('position', 0.0)
    ch_vcash = ch_state.get('virtual_cash', 0.0)
    print(f"    position:     {ch_pos:+.0f} contracts")
    print(f"    virtual_cash: {ch_vcash:+,.0f}")

    # Show cash balances
    print(f"\n  Cash Balances:")
    for wallet in sorted(ledger.cash.keys()):
        print(f"    {wallet:12}: {ledger.cash[wallet]:+,.2f}")

    # Verify conservation (zero-sum checks)
    total_pos = sum(w.get('position', 0.0) for w in wallets.values())
    total_vcash = sum(w.get('virtual_cash', 0.0) for w in wallets.values())
    total_cash = sum(ledger.cash.values())
    print(f"\n  Zero-Sum Invariants:")
    print(f"    Sum of positions:    {total_pos:+.0f} (should be 0)")
    print(f"    Sum of virtual_cash: {total_vcash:+,.0f} (should be 0)")
    print(f"    Sum of cash:         {total_cash:+,.2f} (should be 0)")


def main():
    print("""
================================================================================
                    FUTURES MARK-TO-MARKET DEMO
================================================================================

This demo shows how futures daily settlement works using the virtual_cash model.

Contract: ES (E-mini S&P 500)
Multiplier: $50 per index point
Traders: Alice (goes long), Bob (goes short)

""")

    # Setup
    ledger = SimpleLedger()
    ledger.register_future('ES', multiplier=50.0, currency='USD', clearinghouse='CME')

    # Initialize cash to zero
    for wallet in ['Alice', 'Bob', 'CME']:
        ledger.cash[wallet] = 0.0

    print_state(ledger, 'ES', 'Initial State')

    # =========================================================================
    # DAY 1: Trading
    # =========================================================================
    print("\n" + "="*60)
    print("  DAY 1: TRADING")
    print("="*60)

    print("""
  Alice buys 10 contracts at 4500
  Bob sells 10 contracts at 4500

  For Alice (buy 10 at 4500):
    virtual_cash = 0 - (10 * 4500 * 50) = -2,250,000
    (She "owes" $2.25M worth of index exposure)

  For Bob (sell 10 at 4500):
    virtual_cash = 0 - (-10 * 4500 * 50) = +2,250,000
    (He's "owed" $2.25M worth of index exposure)
""")

    alice_vcash = ledger.trade('ES', 'Alice', qty=10, price=4500.0)
    print(f"  Alice trades: virtual_cash = {alice_vcash:+,.0f}")

    bob_vcash = ledger.trade('ES', 'Bob', qty=-10, price=4500.0)
    print(f"  Bob trades:   virtual_cash = {bob_vcash:+,.0f}")

    print_state(ledger, 'ES', 'After Day 1 Trading')

    # =========================================================================
    # DAY 1 CLOSE: Mark-to-Market at 4520
    # =========================================================================
    print("\n" + "="*60)
    print("  DAY 1 CLOSE: MTM at 4520 (price up $20)")
    print("="*60)

    print("""
  Settlement price: 4520 (up $20 from trade price)

  For Alice (long 10 contracts):
    current virtual_cash = -2,250,000
    target_vcash = -10 * 4520 * 50 = -2,260,000
    vm = -2,250,000 - (-2,260,000) = +10,000
    ALICE RECEIVES $10,000 (profit from price going up)

  For Bob (short 10 contracts):
    current virtual_cash = +2,250,000
    target_vcash = -(-10) * 4520 * 50 = +2,260,000
    vm = +2,250,000 - (+2,260,000) = -10,000
    BOB PAYS $10,000 (loss from price going up)

  Math check: 10 contracts * $20 move * $50 mult = $10,000
""")

    settlements = ledger.mark_to_market('ES', price=4520.0)
    for wallet, vm in sorted(settlements.items()):
        action = "receives" if vm > 0 else "pays"
        print(f"  {wallet} {action} ${abs(vm):,.0f}")

    print_state(ledger, 'ES', 'After Day 1 MTM')

    # =========================================================================
    # DAY 2: Price drops to 4480
    # =========================================================================
    print("\n" + "="*60)
    print("  DAY 2 CLOSE: MTM at 4480 (price down $40)")
    print("="*60)

    print("""
  Settlement price: 4480 (down $40 from yesterday's 4520)

  For Alice (long 10):
    current virtual_cash = -2,260,000 (from yesterday's MTM)
    target_vcash = -10 * 4480 * 50 = -2,240,000
    vm = -2,260,000 - (-2,240,000) = -20,000
    ALICE PAYS $20,000

  For Bob (short 10):
    current virtual_cash = +2,260,000
    target_vcash = +10 * 4480 * 50 = +2,240,000
    vm = +2,260,000 - (+2,240,000) = +20,000
    BOB RECEIVES $20,000

  Math check: 10 contracts * $40 move * $50 mult = $20,000
""")

    settlements = ledger.mark_to_market('ES', price=4480.0)
    for wallet, vm in sorted(settlements.items()):
        action = "receives" if vm > 0 else "pays"
        print(f"  {wallet} {action} ${abs(vm):,.0f}")

    print_state(ledger, 'ES', 'After Day 2 MTM')

    # =========================================================================
    # DAY 3: Alice adds to position
    # =========================================================================
    print("\n" + "="*60)
    print("  DAY 3: ALICE BUYS 5 MORE AT 4490")
    print("="*60)

    print("""
  Alice buys 5 more contracts at 4490.

  Her virtual_cash update:
    old_vcash = -2,240,000 (from yesterday's MTM)
    new_vcash = -2,240,000 - (5 * 4490 * 50) = -2,240,000 - 1,122,500 = -3,362,500

  She now has 15 contracts with virtual_cash = -3,362,500
""")

    alice_vcash = ledger.trade('ES', 'Alice', qty=5, price=4490.0)
    print(f"  Alice trades: virtual_cash = {alice_vcash:+,.0f}")

    print_state(ledger, 'ES', 'After Day 3 Trading')

    # =========================================================================
    # DAY 3 CLOSE: MTM at 4500
    # =========================================================================
    print("\n" + "="*60)
    print("  DAY 3 CLOSE: MTM at 4500")
    print("="*60)

    print("""
  Settlement price: 4500

  For Alice (long 15):
    current virtual_cash = -3,362,500
    target_vcash = -15 * 4500 * 50 = -3,375,000
    vm = -3,362,500 - (-3,375,000) = +12,500
    ALICE RECEIVES $12,500

    Breakdown:
    - Original 10 contracts: (4500-4480) * 10 * 50 = +10,000
    - New 5 contracts: (4500-4490) * 5 * 50 = +2,500
    - Total: +12,500 (matches!)

  For Bob (short 10):
    current virtual_cash = +2,240,000
    target_vcash = +10 * 4500 * 50 = +2,250,000
    vm = +2,240,000 - (+2,250,000) = -10,000
    BOB PAYS $10,000
""")

    settlements = ledger.mark_to_market('ES', price=4500.0)
    for wallet, vm in sorted(settlements.items()):
        action = "receives" if vm > 0 else "pays"
        print(f"  {wallet} {action} ${abs(vm):,.0f}")

    print_state(ledger, 'ES', 'After Day 3 MTM')

    # =========================================================================
    # DAY 4: Bob closes his position
    # =========================================================================
    print("\n" + "="*60)
    print("  DAY 4: BOB CLOSES HIS SHORT (buys 10 at 4510)")
    print("="*60)

    print("""
  Bob buys 10 contracts at 4510 to close his short.

  His virtual_cash update:
    old_vcash = +2,250,000 (from yesterday's MTM)
    new_vcash = +2,250,000 - (10 * 4510 * 50) = +2,250,000 - 2,255,000 = -5,000

  He now has 0 contracts with virtual_cash = -5,000
  (This -5,000 represents his total loss: sold at 4500, bought at 4510)
""")

    bob_vcash = ledger.trade('ES', 'Bob', qty=10, price=4510.0)
    print(f"  Bob trades: virtual_cash = {bob_vcash:+,.0f}")

    print_state(ledger, 'ES', 'After Day 4 Trading')

    # =========================================================================
    # DAY 4 CLOSE: MTM at 4520
    # =========================================================================
    print("\n" + "="*60)
    print("  DAY 4 CLOSE: MTM at 4520")
    print("="*60)

    print("""
  Settlement price: 4520

  For Alice (long 15):
    current virtual_cash = -3,375,000
    target_vcash = -15 * 4520 * 50 = -3,390,000
    vm = -3,375,000 - (-3,390,000) = +15,000
    ALICE RECEIVES $15,000

  For Bob (position = 0):
    current virtual_cash = -5,000
    target_vcash = -0 * 4520 * 50 = 0
    vm = -5,000 - 0 = -5,000
    BOB PAYS $5,000 (his realized loss from closing the trade)
""")

    settlements = ledger.mark_to_market('ES', price=4520.0)
    for wallet, vm in sorted(settlements.items()):
        action = "receives" if vm > 0 else "pays"
        print(f"  {wallet} {action} ${abs(vm):,.0f}")

    print_state(ledger, 'ES', 'After Day 4 MTM')

    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    print("\n" + "="*60)
    print("  FINAL SUMMARY")
    print("="*60)

    alice_cash = ledger.cash['Alice']
    bob_cash = ledger.cash['Bob']
    cme_cash = ledger.cash['CME']

    print(f"""
  Running P&L since inception:

  Alice:
    - Cash settled: ${alice_cash:+,.0f}
    - Position: 15 contracts
    - Trades: Bought 10 @ 4500, then 5 @ 4490
    - Current price: 4520
    - Unrealized P&L = position * (price - target) = already in virtual_cash
    - Total value = cash + virtual_cash + position * price * mult
                  = {alice_cash:+,.0f} + {ledger.futures['ES']['wallets']['Alice']['virtual_cash']:+,.0f} + 15*4520*50
                  = {alice_cash:+,.0f} + {ledger.futures['ES']['wallets']['Alice']['virtual_cash']:+,.0f} + 3,390,000
                  = {alice_cash + ledger.futures['ES']['wallets']['Alice']['virtual_cash'] + 15*4520*50:,.0f}
    - Cost basis = 10*4500*50 + 5*4490*50 = 2,250,000 + 1,122,500 = 3,372,500
    - Net P&L = {alice_cash + ledger.futures['ES']['wallets']['Alice']['virtual_cash'] + 15*4520*50 - 3372500:+,.0f}

  Bob:
    - Cash settled: ${bob_cash:+,.0f}
    - Position: 0 contracts (closed out)
    - Trades: Sold 10 @ 4500, bought 10 @ 4510
    - Net P&L: 10 * (4500-4510) * 50 = -$5,000
    - This matches his cash! Bob is done.

  Clearinghouse (CME):
    - Cash: ${cme_cash:+,.0f}
    - Position: {ledger.get_position('ES', 'CME'):+.0f} contracts
    - The CH is always the counterparty to all trades

  Total cash in system: {alice_cash + bob_cash + cme_cash:,.0f} (zero-sum verified)
""")

    # =========================================================================
    # THE KEY INSIGHT
    # =========================================================================
    print("="*60)
    print("  THE KEY INSIGHT")
    print("="*60)
    print("""
  The virtual_cash model works because:

  1. When you trade, virtual_cash records what you "spent": -qty * price * mult

  2. At MTM, target_vcash = -position * settle_price * mult
     This is what you WOULD have spent if all trades were at settle_price

  3. The difference (vm = vcash - target) is exactly the P&L from price movement

  This avoids tracking average entry prices, handling partial closes,
  or complex P&L calculations. The math just works.

  When position goes to zero:
    target_vcash = 0
    vm = vcash - 0 = vcash
    All accumulated virtual_cash becomes realized cash.

  The implementation is ~50 lines of logic. That's all you need.
""")


if __name__ == '__main__':
    main()
