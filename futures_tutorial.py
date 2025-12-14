#!/usr/bin/env python3
"""
futures_tutorial.py - Complete Futures Tutorial with Daily Mark-to-Market

This tutorial demonstrates the complete lifecycle of exchange-traded futures:
1. The virtual_cash model (how MTM works mathematically)
2. Trading (buy/sell between parties via clearinghouse)
3. Daily mark-to-market settlement
4. Position closing
5. Final expiry settlement
6. LifecycleEngine integration for automated processing

MATHEMATICAL MODEL:
    Each trader has:
        virtual_cash = sum of (-qty * price * multiplier) for all trades
        position = net contracts held

    At any moment:
        economic_value = virtual_cash + position * current_price * multiplier

    On MTM at price P:
        target_vcash = -position * P * multiplier
        variation_margin = virtual_cash - target_vcash
        virtual_cash = target_vcash (reset)

    This equals: position * (P - avg_entry_price) * multiplier
    but without tracking average entry prices explicitly.

USAGE:
    python futures_tutorial.py           # Run full tutorial
    python futures_tutorial.py --quick   # Run abbreviated version

Configuration parameters are exposed at the top for experimentation.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import sys

from ledger import (
    Ledger,
    Move,
    cash,
    build_transaction,
    SYSTEM_WALLET,
    create_future,
    future_transact,
    future_mark_to_market,
    future_contract,
    LifecycleEngine,
    TimeSeriesPricingSource,
    UNIT_TYPE_FUTURE,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class FuturesConfig:
    """Configuration for the futures tutorial."""
    # Contract specification
    symbol: str = "ESZ25"
    name: str = "E-mini S&P 500 Dec 2025"
    underlying: str = "SPX"
    multiplier: Decimal = Decimal("50")  # $50 per point
    currency: str = "USD"
    clearinghouse: str = "CME"

    # Timeline
    start_date: datetime = datetime(2025, 1, 1)
    expiry: datetime = datetime(2025, 1, 10)
    trading_days: int = 10

    # Initial prices
    initial_price: Decimal = Decimal("4500")
    price_volatility: float = 0.01  # 1% daily volatility

    # Participants
    initial_cash: Decimal = Decimal("1000000")

    # Positions
    alice_contracts: int = 10
    bob_contracts: int = -5  # Short
    charlie_contracts: int = 3


# Quick config for fast runs
QUICK_CONFIG = FuturesConfig(
    trading_days=5,
    alice_contracts=5,
    bob_contracts=-3,
    charlie_contracts=2,
)


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def header(title: str, char: str = "=") -> None:
    """Print a section header."""
    width = 70
    print(f"\n{char * width}")
    print(f"  {title}")
    print(f"{char * width}")


def subheader(title: str) -> None:
    """Print a sub-section header."""
    print(f"\n  --- {title} ---")


def status(passed: bool, message: str) -> None:
    """Print status with checkmark."""
    mark = "\u2713" if passed else "\u2717"
    print(f"  {mark} {message}")


def print_futures_state(ledger: Ledger, symbol: str, title: Optional[str] = None) -> None:
    """Print the current state of a futures contract."""
    state = ledger.get_unit_state(symbol)
    ch = state['clearinghouse']
    mult = state['multiplier']
    currency = state['currency']
    wallets_state = state.get('wallets', {})

    if title:
        print(f"\n  {title}")

    # Show trader wallet states
    print(f"\n  Wallet States:")
    print(f"  {'Wallet':<12} {'Position':>10} {'Virtual Cash':>15}")
    print(f"  {'-'*12} {'-'*10} {'-'*15}")

    for wallet in sorted(wallets_state.keys()):
        if wallet == ch:
            continue
        w = wallets_state[wallet]
        pos = w.get('position', 0)
        vcash = w.get('virtual_cash', 0)
        if pos != 0 or vcash != 0:
            print(f"  {wallet:<12} {pos:>+10.0f} {vcash:>+15,.0f}")

    # Show clearinghouse
    ch_state = wallets_state.get(ch, {})
    ch_pos = ch_state.get('position', 0)
    ch_vcash = ch_state.get('virtual_cash', 0)
    print(f"\n  Clearinghouse ({ch}):")
    print(f"    Position:     {ch_pos:+.0f}")
    print(f"    Virtual Cash: {ch_vcash:+,.0f}")

    # Show cash balances
    print(f"\n  Cash Balances ({currency}):")
    for wallet in ['alice', 'bob', 'charlie', ch]:
        if wallet in ledger.registered_wallets:
            balance = ledger.get_balance(wallet, currency)
            print(f"    {wallet:<12}: {balance:>+15,.2f}")

    # Zero-sum verification
    total_pos = sum(w.get('position', 0) for w in wallets_state.values())
    total_vcash = sum(w.get('virtual_cash', 0) for w in wallets_state.values())

    print(f"\n  Zero-Sum Invariants:")
    status(abs(total_pos) < 1e-10, f"Sum(positions) = {total_pos:.0f}")
    status(abs(total_vcash) < 1e-6, f"Sum(virtual_cash) = {total_vcash:.0f}")

    if state.get('last_settle_price'):
        print(f"\n  Last Settlement: {state['last_settle_price']:,.2f}")


# =============================================================================
# PART 1: THE MATHEMATICS OF MARK-TO-MARKET
# =============================================================================

def part1_mathematical_model(config: FuturesConfig) -> None:
    """Explain the virtual_cash model with concrete examples."""
    header("PART 1: The Mathematics of Mark-to-Market")

    print("""
  THE VIRTUAL CASH MODEL
  ======================

  Each trader's state is tracked with two numbers:
    - position: net contracts held (+ = long, - = short)
    - virtual_cash: accumulated "paper" value from trades

  When you trade:
    virtual_cash += -qty * price * multiplier

  This records what you "spent" (or "received" if selling).

  Example: Alice buys 10 contracts at 4500, multiplier = $50
    virtual_cash = 0 - (10 * 4500 * 50) = -2,250,000

  She now "owes" $2.25M worth of index exposure.
""")

    subheader("Daily Mark-to-Market Settlement")

    print(f"""
  At end of each day, we settle to the closing price:

  For each trader with position P and virtual_cash V:
    1. target_vcash = -P * settle_price * multiplier
       (What V would be if all trades were at settle_price)

    2. variation_margin = V - target_vcash
       (The P&L from price movement)

    3. Cash transfer:
       VM > 0 => trader RECEIVES cash (profit)
       VM < 0 => trader PAYS cash (loss)

    4. Reset: virtual_cash = target_vcash

  Example: Alice (long 10) after price rises from 4500 to 4520:
    current V = -2,250,000 (from buying at 4500)
    target V  = -10 * 4520 * 50 = -2,260,000
    VM = -2,250,000 - (-2,260,000) = +$10,000

  Alice RECEIVES $10,000 (profit from price going up)

  Math verification:
    10 contracts * $20 price move * $50 multiplier = $10,000 ✓
""")

    subheader("Why This Model Works")

    print("""
  The beauty of virtual_cash:

  1. NO average price tracking needed
     - Multiple trades at different prices? No problem.
     - Partial closes? Automatically handled.

  2. Zero-sum is automatic
     - Sum of all virtual_cash = 0 (always)
     - Sum of all positions = 0 (always)
     - Clearinghouse is just another participant

  3. Settlement = difference between actual and target
     - When position closes (position → 0):
       target_vcash = 0
       VM = vcash - 0 = vcash
       All accumulated P&L becomes realized cash

  This is mathematically equivalent to tracking entry prices,
  but with simpler implementation (~50 lines of logic).
""")


# =============================================================================
# PART 2: BASIC TRADING AND MTM
# =============================================================================

def part2_trading_and_mtm(config: FuturesConfig) -> Ledger:
    """Demonstrate basic futures trading and mark-to-market."""
    header("PART 2: Trading and Daily Settlement")

    # Setup
    ledger = Ledger(
        name="futures_tutorial",
        initial_time=config.start_date,
        verbose=False,
    )

    # Register units
    ledger.register_unit(cash(config.currency, f"{config.currency} Currency"))
    ledger.register_unit(create_future(
        symbol=config.symbol,
        name=config.name,
        underlying=config.underlying,
        expiry=config.expiry,
        multiplier=config.multiplier,
        currency=config.currency,
        clearinghouse_id=config.clearinghouse,
    ))

    # Register wallets
    for wallet in ["alice", "bob", "charlie", config.clearinghouse]:
        ledger.register_wallet(wallet)

    # Fund accounts
    funding_tx = build_transaction(ledger, [
        Move(config.initial_cash, config.currency, SYSTEM_WALLET, "alice", "fund"),
        Move(config.initial_cash, config.currency, SYSTEM_WALLET, "bob", "fund"),
        Move(config.initial_cash, config.currency, SYSTEM_WALLET, "charlie", "fund"),
        Move(config.initial_cash * 100, config.currency, SYSTEM_WALLET, config.clearinghouse, "fund"),
    ])
    ledger.execute(funding_tx)

    print(f"\n  Setup complete:")
    print(f"    Contract:    {config.symbol} ({config.name})")
    print(f"    Multiplier:  ${config.multiplier}/point")
    print(f"    Expiry:      {config.expiry.date()}")
    print(f"    Participants: alice, bob, charlie")

    # Day 1: Initial trades
    subheader(f"Day 1: Initial Trades at {config.initial_price}")

    trade_price = config.initial_price

    # Alice goes long
    result = future_transact(
        ledger, config.symbol,
        seller_id=config.clearinghouse,
        buyer_id="alice",
        qty=abs(config.alice_contracts),
        price=trade_price
    )
    ledger.execute(result)
    print(f"  Alice BUYS {config.alice_contracts} contracts at {trade_price}")

    # Bob goes short
    result = future_transact(
        ledger, config.symbol,
        seller_id="bob",
        buyer_id=config.clearinghouse,
        qty=abs(config.bob_contracts),
        price=trade_price
    )
    ledger.execute(result)
    print(f"  Bob SELLS {abs(config.bob_contracts)} contracts at {trade_price}")

    # Charlie goes long at slightly higher price
    charlie_price = trade_price + Decimal("10")
    result = future_transact(
        ledger, config.symbol,
        seller_id=config.clearinghouse,
        buyer_id="charlie",
        qty=abs(config.charlie_contracts),
        price=charlie_price
    )
    ledger.execute(result)
    print(f"  Charlie BUYS {config.charlie_contracts} contracts at {charlie_price}")

    print_futures_state(ledger, config.symbol, "After Day 1 Trades")

    # Day 1 Close: MTM at higher price
    subheader("Day 1 Close: Price rises to 4520")

    settle_price = config.initial_price + Decimal("20")

    print(f"\n  Settlement price: {settle_price}")
    print(f"  Expected P&L:")
    alice_expected = config.alice_contracts * (settle_price - trade_price) * config.multiplier
    bob_expected = config.bob_contracts * (settle_price - trade_price) * config.multiplier
    charlie_expected = config.charlie_contracts * (settle_price - charlie_price) * config.multiplier
    print(f"    Alice (long {config.alice_contracts}):  {alice_expected:+,.0f}")
    print(f"    Bob (short {abs(config.bob_contracts)}):    {bob_expected:+,.0f}")
    print(f"    Charlie (long {config.charlie_contracts}): {charlie_expected:+,.0f}")

    # Execute MTM
    result = future_mark_to_market(
        ledger, config.symbol,
        price=settle_price,
        settle_date=config.start_date.date()
    )
    ledger.execute(result)

    # Verify
    alice_cash = ledger.get_balance("alice", config.currency)
    bob_cash = ledger.get_balance("bob", config.currency)
    charlie_cash = ledger.get_balance("charlie", config.currency)

    print(f"\n  Cash balances after MTM:")
    print(f"    Alice:   ${alice_cash:,.0f} (change: ${alice_cash - config.initial_cash:+,.0f})")
    print(f"    Bob:     ${bob_cash:,.0f} (change: ${bob_cash - config.initial_cash:+,.0f})")
    print(f"    Charlie: ${charlie_cash:,.0f} (change: ${charlie_cash - config.initial_cash:+,.0f})")

    # Day 2: Price drops
    subheader("Day 2 Close: Price drops to 4480")

    ledger.advance_time(config.start_date + timedelta(days=1))
    settle_price_2 = config.initial_price - Decimal("20")

    print(f"\n  Settlement price: {settle_price_2} (down $40 from Day 1 settle)")

    result = future_mark_to_market(
        ledger, config.symbol,
        price=settle_price_2,
        settle_date=(config.start_date + timedelta(days=1)).date()
    )
    ledger.execute(result)

    alice_cash = ledger.get_balance("alice", config.currency)
    bob_cash = ledger.get_balance("bob", config.currency)

    print(f"\n  P&L from Day 1 to Day 2:")
    print(f"    Alice: Lost ${config.alice_contracts * 40 * config.multiplier:,.0f} (long, price down)")
    print(f"    Bob: Gained ${abs(config.bob_contracts) * 40 * config.multiplier:,.0f} (short, price down)")

    return ledger


# =============================================================================
# PART 3: POSITION CLOSING
# =============================================================================

def part3_position_closing(ledger: Ledger, config: FuturesConfig) -> None:
    """Demonstrate closing a position."""
    header("PART 3: Position Closing")

    print("""
  When closing a position:
  1. Trade in opposite direction (short covers by buying)
  2. Position goes to zero
  3. Next MTM settles remaining virtual_cash to actual cash
  4. Realized P&L = final cash - initial cash
""")

    subheader("Bob Closes His Short Position")

    # Bob buys back to close
    close_price = Decimal("4490")
    ledger.advance_time(ledger.current_time + timedelta(hours=1))

    bob_pos_before = ledger.get_unit_state(config.symbol)['wallets'].get('bob', {}).get('position', 0)
    print(f"\n  Bob's position before: {bob_pos_before:+.0f} contracts")

    result = future_transact(
        ledger, config.symbol,
        seller_id=config.clearinghouse,
        buyer_id="bob",
        qty=abs(config.bob_contracts),  # Buy back the shorts
        price=close_price
    )
    ledger.execute(result)

    bob_state = ledger.get_unit_state(config.symbol)['wallets'].get('bob', {})
    print(f"  Bob BUYS {abs(config.bob_contracts)} contracts at {close_price} to close")
    print(f"  Bob's position after: {bob_state.get('position', 0):.0f}")
    print(f"  Bob's virtual_cash: {bob_state.get('virtual_cash', 0):,.0f}")
    print(f"  (Will be settled to cash at next MTM)")

    # MTM to settle Bob's closing
    subheader("Day 3 MTM: Bob's P&L Realized")

    settle_price_3 = Decimal("4495")
    ledger.advance_time(ledger.current_time + timedelta(hours=12))

    bob_cash_before = ledger.get_balance("bob", config.currency)

    result = future_mark_to_market(
        ledger, config.symbol,
        price=settle_price_3,
        settle_date=(config.start_date + timedelta(days=2)).date()
    )
    ledger.execute(result)

    bob_cash_after = ledger.get_balance("bob", config.currency)
    bob_pnl = bob_cash_after - config.initial_cash

    print(f"\n  Settlement price: {settle_price_3}")
    print(f"  Bob's final cash: ${bob_cash_after:,.0f}")
    print(f"  Bob's total P&L: ${bob_pnl:+,.0f}")

    # Calculate expected P&L manually
    entry_price = config.initial_price
    exit_price = close_price
    expected_pnl = config.bob_contracts * (exit_price - entry_price) * config.multiplier

    print(f"\n  P&L verification:")
    print(f"    Entry: Sold {abs(config.bob_contracts)} at {entry_price}")
    print(f"    Exit:  Bought {abs(config.bob_contracts)} at {close_price}")
    print(f"    Expected: {config.bob_contracts} * ({close_price} - {entry_price}) * {config.multiplier}")
    print(f"             = ${expected_pnl:+,.0f}")

    status(abs(bob_pnl - expected_pnl) < 1, f"P&L matches expected: ${bob_pnl:+,.0f}")


# =============================================================================
# PART 4: EXPIRY AND FINAL SETTLEMENT
# =============================================================================

def part4_expiry(ledger: Ledger, config: FuturesConfig) -> None:
    """Demonstrate contract expiry and final settlement."""
    header("PART 4: Contract Expiry")

    print("""
  At expiry:
  1. Final settlement price is determined
  2. All open positions are closed at settlement price
  3. Final MTM settles all remaining positions
  4. Contract marked as 'settled'
""")

    # Jump to expiry
    ledger.advance_time(config.expiry)

    # Get current positions
    state = ledger.get_unit_state(config.symbol)
    wallets = state.get('wallets', {})

    print(f"\n  Remaining positions at expiry:")
    for wallet in ['alice', 'charlie']:
        w = wallets.get(wallet, {})
        pos = w.get('position', 0)
        if pos != 0:
            print(f"    {wallet}: {pos:+.0f} contracts")

    # Final settlement price
    final_price = Decimal("4550")

    subheader(f"Final Settlement at {final_price}")

    # Use future_contract which handles expiry
    prices = {config.underlying: final_price}
    result = future_contract(ledger, config.symbol, config.expiry, prices)
    ledger.execute(result)

    # Final state
    state = ledger.get_unit_state(config.symbol)

    print(f"\n  Contract status:")
    print(f"    Settled: {state.get('settled', False)}")
    print(f"    Settlement price: {state.get('settlement_price', 'N/A')}")

    # Final P&L summary
    subheader("Final P&L Summary")

    alice_cash = ledger.get_balance("alice", config.currency)
    bob_cash = ledger.get_balance("bob", config.currency)
    charlie_cash = ledger.get_balance("charlie", config.currency)
    cme_cash = ledger.get_balance(config.clearinghouse, config.currency)

    alice_pnl = alice_cash - config.initial_cash
    bob_pnl = bob_cash - config.initial_cash
    charlie_pnl = charlie_cash - config.initial_cash

    print(f"\n  Participant       Initial         Final           P&L")
    print(f"  {'-'*60}")
    print(f"  Alice         ${config.initial_cash:>12,.0f}  ${alice_cash:>12,.0f}  ${alice_pnl:>+12,.0f}")
    print(f"  Bob           ${config.initial_cash:>12,.0f}  ${bob_cash:>12,.0f}  ${bob_pnl:>+12,.0f}")
    print(f"  Charlie       ${config.initial_cash:>12,.0f}  ${charlie_cash:>12,.0f}  ${charlie_pnl:>+12,.0f}")
    print(f"  {'-'*60}")
    print(f"  Total P&L:                                    ${alice_pnl + bob_pnl + charlie_pnl:>+12,.0f}")

    # Cash conservation
    total_initial = config.initial_cash * 3 + config.initial_cash * 100
    total_final = alice_cash + bob_cash + charlie_cash + cme_cash
    conservation_ok = abs(total_final - total_initial) < 1

    print(f"\n  Conservation check:")
    status(conservation_ok, f"Total cash: ${total_final:,.0f} (initial: ${total_initial:,.0f})")


# =============================================================================
# PART 5: LIFECYCLE ENGINE INTEGRATION
# =============================================================================

def part5_lifecycle_engine(config: FuturesConfig) -> None:
    """Demonstrate automated MTM via LifecycleEngine."""
    header("PART 5: LifecycleEngine for Automated Processing")

    print("""
  The LifecycleEngine automates daily settlement:
  1. Register contract type handlers
  2. Call engine.step(timestamp, prices) each day
  3. Engine finds all futures, calls future_contract for each
  4. MTM and expiry handled automatically
""")

    # Setup fresh ledger
    ledger = Ledger(
        name="lifecycle_demo",
        initial_time=config.start_date,
        verbose=False,
    )

    ledger.register_unit(cash(config.currency, f"{config.currency} Currency"))
    ledger.register_unit(create_future(
        symbol=config.symbol,
        name=config.name,
        underlying=config.underlying,
        expiry=config.expiry,
        multiplier=config.multiplier,
        currency=config.currency,
        clearinghouse_id=config.clearinghouse,
    ))

    for wallet in ["alice", "bob", config.clearinghouse]:
        ledger.register_wallet(wallet)

    ledger.execute(build_transaction(ledger, [
        Move(config.initial_cash, config.currency, SYSTEM_WALLET, "alice", "fund"),
        Move(config.initial_cash, config.currency, SYSTEM_WALLET, "bob", "fund"),
        Move(config.initial_cash * 100, config.currency, SYSTEM_WALLET, config.clearinghouse, "fund"),
    ]))

    # Initial trades
    future_transact(ledger, config.symbol, config.clearinghouse, "alice", 10, config.initial_price)
    result = future_transact(ledger, config.symbol, config.clearinghouse, "alice", 10, config.initial_price)
    ledger.execute(result)

    result = future_transact(ledger, config.symbol, "bob", config.clearinghouse, 5, config.initial_price)
    ledger.execute(result)

    # Setup engine
    subheader("Setting Up LifecycleEngine")

    engine = LifecycleEngine(ledger)
    engine.register(UNIT_TYPE_FUTURE, future_contract)

    print(f"  Registered handlers: {list(engine.contracts.keys())}")

    # Generate price path
    subheader("Running Daily Settlement")

    trading_dates = []
    current = config.start_date
    for _ in range(config.trading_days):
        trading_dates.append(current)
        current += timedelta(days=1)

    # Simple price path
    import random
    random.seed(42)
    price = float(config.initial_price)
    prices_path = []
    for date in trading_dates:
        change = random.gauss(0, config.price_volatility) * price
        price = price + change
        prices_path.append((date, Decimal(str(round(price, 2)))))

    print(f"\n  Processing {len(trading_dates)} trading days...")
    print(f"  {'Date':<12} {'Price':>10} {'Transactions':>15}")
    print(f"  {'-'*12} {'-'*10} {'-'*15}")

    for date, price_val in prices_path:
        prices = {config.underlying: price_val}
        txs = engine.step(date, prices)
        print(f"  {date.date()!s:<12} {price_val:>10,.2f} {len(txs):>15}")

    # Final state
    subheader("Final State After Automated Processing")

    alice_cash = ledger.get_balance("alice", config.currency)
    bob_cash = ledger.get_balance("bob", config.currency)

    print(f"\n  Final cash balances:")
    print(f"    Alice: ${alice_cash:,.0f} (P&L: ${alice_cash - config.initial_cash:+,.0f})")
    print(f"    Bob:   ${bob_cash:,.0f} (P&L: ${bob_cash - config.initial_cash:+,.0f})")

    state = ledger.get_unit_state(config.symbol)
    print(f"\n  Contract status: {'Settled' if state.get('settled') else 'Active'}")
    print(f"  Transactions logged: {len(ledger.transaction_log)}")


# =============================================================================
# MAIN
# =============================================================================

def print_summary() -> None:
    """Print summary and key takeaways."""
    header("SUMMARY: Key Takeaways")

    print("""
  FUTURES TRADING MECHANICS:

  1. Virtual Cash Model
     - Track position + virtual_cash (not average price)
     - virtual_cash = sum of (-qty * price * mult) for all trades
     - Elegant, ~50 lines of logic, handles all cases

  2. Daily Mark-to-Market
     - Settle to closing price each day
     - VM = virtual_cash - (-position * price * mult)
     - Positive VM = profit, Negative VM = loss

  3. Zero-Sum Game
     - Sum of all positions = 0 (always)
     - Sum of all virtual_cash = 0 (always)
     - Clearinghouse is counterparty to everyone

  4. LifecycleEngine Integration
     - Register: engine.register("FUTURE", future_contract)
     - Daily: engine.step(date, prices)
     - Handles MTM and expiry automatically

  FOR MORE INFORMATION:
  - See ledger/units/future.py for implementation
  - Run: python demo.py for comprehensive ledger tutorial
""")


def main() -> bool:
    """Run the complete futures tutorial."""
    quick_mode = "--quick" in sys.argv
    config = QUICK_CONFIG if quick_mode else FuturesConfig()

    if quick_mode:
        print("Running in QUICK mode")

    print("""
================================================================================
              FUTURES TUTORIAL - Complete Mark-to-Market Demo
================================================================================

This tutorial demonstrates exchange-traded futures with daily settlement.
Follow along to understand the mathematics and mechanics.
""")

    # Run all parts
    part1_mathematical_model(config)
    ledger = part2_trading_and_mtm(config)
    part3_position_closing(ledger, config)
    part4_expiry(ledger, config)
    part5_lifecycle_engine(config)
    print_summary()

    print(f"\n{'=' * 70}")
    print("  TUTORIAL COMPLETE")
    print(f"{'=' * 70}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
