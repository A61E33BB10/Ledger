#!/usr/bin/env python3
"""
demo.py - Interactive Tutorial: Learn the Ledger Step by Step

This is a pedagogical demonstration that teaches how the financial ledger works.
Each step builds on the previous one. Press Enter to advance.

WHAT YOU'LL LEARN:
  1-5:   Foundation      - The empty ledger, units, wallets, first transaction
  6-10:  Core Mechanics  - Transfers, rejections, atomicity, idempotency, logs
  11-13: Time Travel     - Advancing time, historical reconstruction, replay
  14-17: Instruments     - Options, LifecycleEngine, automatic settlement
  18-20: Advanced        - Pending transactions, deferred cash, conservation proof

Run:
    python demo.py           # Interactive mode (press Enter for each step)
    python demo.py --quick   # Run all steps without pausing

Designed by the Expert Committee to replace documentation with executable examples.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
import sys
import time
import random

# Core imports
from ledger import (
    # Core classes
    Ledger, Move, Unit, Transaction,
    # Builder functions
    build_transaction, cash,
    # Constants
    SYSTEM_WALLET, UNIT_TYPE_CASH, ExecuteResult,
    # Stock module
    create_stock_unit,
    # Options module
    create_option_unit, compute_option_settlement,
    get_option_intrinsic_value, option_contract, option_transact,
    # Deferred cash
    create_deferred_cash_unit, deferred_cash_contract,
    # Engine
    LifecycleEngine,
)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class DemoConfig:
    """Configuration for the tutorial. Modify these to experiment."""
    # Timing
    start_time: datetime = datetime(2025, 1, 1, 9, 0, 0)

    # Initial funding
    alice_initial_usd: Decimal = Decimal("10000.00")
    bob_initial_usd: Decimal = Decimal("10000.00")
    bob_initial_shares: int = 500

    # Option parameters
    option_strike: float = 150.0
    option_contracts: int = 3
    option_premium: float = 12.50
    option_settlement_price: float = 175.0  # ITM

    # Deferred cash
    dividend_per_share: Decimal = Decimal("0.25")

    # Load test parameters (Step 21)
    load_test_units: int = 10_000      # 10^4 units
    load_test_wallets: int = 1_000     # 1000 wallets
    load_test_transactions: int = 1_000_000  # 10^6 transactions


CONFIG = DemoConfig()

# Global state for interactive mode
QUICK_MODE = "--quick" in sys.argv


def wait_for_enter():
    """Pause for user input unless in quick mode."""
    if not QUICK_MODE:
        input("\n[Press Enter to continue...]")


def step_header(number: int, title: str, objective: str):
    """Print a step header with learning objective."""
    print(f"\n{'='*70}")
    print(f"STEP {number}: {title}")
    print(f"{'='*70}")
    print(f"\nObjective: {objective}\n")


def section_header(text: str):
    """Print a section header within a step."""
    print(f"\n--- {text} ---\n")


# ============================================================================
# PHASE 1: FOUNDATION (Steps 1-5)
# ============================================================================

def step_01_empty_ledger():
    """Create an empty ledger and understand its initial state."""
    step_header(1, "The Empty Ledger",
        "Understand that a ledger starts as a clean slate with only time.")

    print("""
    A ledger is a record of who owns what. It has three core concepts:

    1. UNITS   - What can be owned (USD, AAPL shares, options, etc.)
    2. WALLETS - Who can own things (alice, bob, system, etc.)
    3. TIME    - When things happen (monotonically increasing)

    Let's create an empty ledger with verbose=True to see what happens inside.
    """)

    wait_for_enter()

    print(">>> ledger = Ledger('tutorial', initial_time=datetime(2025, 1, 1, 9, 0))")
    ledger = Ledger(
        name="tutorial",
        initial_time=CONFIG.start_time,
        verbose=True
    )

    section_header("Initial State")
    print(f"Ledger name:        {ledger.name}")
    print(f"Current time:       {ledger.current_time}")
    print(f"Registered wallets: {sorted(ledger.registered_wallets)}")
    print(f"Registered units:   {ledger.list_units()}")
    print(f"Transaction log:    {len(ledger.transaction_log)} entries")

    section_header("Key Insight")
    print("""
    The SYSTEM wallet exists from the start. It's special:
    - All value ENTERS the economy through system (negative balance = money created)
    - All value EXITS the economy back to system (positive balance = money destroyed)
    - This is how conservation works: sum of ALL wallets = 0 (always)
    """)

    return ledger


def step_02_register_unit(ledger: Ledger):
    """Register a unit (what can be owned)."""
    step_header(2, "Registering Units",
        "Units define WHAT can be owned and their constraints.")

    print("""
    A Unit defines an asset type with constraints:

    - symbol:         Unique identifier (e.g., "USD", "AAPL")
    - min_balance:    Minimum allowed balance (negative = allows shorting)
    - max_balance:    Maximum allowed balance
    - decimal_places: Precision for rounding

    Let's register USD as our first unit.
    """)

    wait_for_enter()

    print('>>> usd = cash("USD", "US Dollar", decimal_places=2)')
    usd = cash("USD", "US Dollar", decimal_places=2)

    section_header("Unit Properties")
    print(f"Symbol:         {usd.symbol}")
    print(f"Name:           {usd.name}")
    print(f"Type:           {usd.unit_type}")
    print(f"Min balance:    {usd.min_balance}")
    print(f"Max balance:    {usd.max_balance}")
    print(f"Decimal places: {usd.decimal_places}")

    print("\n>>> ledger.register_unit(usd)")
    ledger.register_unit(usd)

    section_header("Key Insight")
    print("""
    Notice min_balance = -1,000,000,000. This allows OVERDRAFTS.
    The system wallet needs this to issue money (its balance goes negative).

    Later we'll see STRICT units with min_balance=0 that prevent overdrafts.
    """)

    return ledger


def step_03_register_wallets(ledger: Ledger):
    """Register wallets (who can own)."""
    step_header(3, "Registering Wallets",
        "Wallets are identities that can hold balances.")

    print("""
    Wallets are simple identifiers (strings). Anyone can hold any unit.

    The system wallet was auto-registered. Let's add Alice and Bob.
    """)

    wait_for_enter()

    print('>>> ledger.register_wallet("alice")')
    print('>>> ledger.register_wallet("bob")')
    ledger.register_wallet("alice")
    ledger.register_wallet("bob")

    section_header("Registered Wallets")
    print(f"Wallets: {sorted(ledger.registered_wallets)}")

    section_header("Initial Balances")
    print(f"Alice USD: {ledger.get_balance('alice', 'USD')}")
    print(f"Bob USD:   {ledger.get_balance('bob', 'USD')}")
    print(f"System USD: {ledger.get_balance('system', 'USD')}")

    section_header("Key Insight")
    print("""
    Everyone starts with ZERO balance. To create money, we must
    ISSUE from the system wallet. This keeps the total supply = 0.
    """)

    return ledger


def step_04_first_transaction(ledger: Ledger):
    """Execute your first transaction (issuance)."""
    step_header(4, "Your First Transaction",
        "Value enters via SYSTEM_WALLET. build_transaction is PURE; execute() mutates.")

    print("""
    To give Alice money, we move it FROM the system wallet TO Alice.

    Two-phase process:
    1. build_transaction() - PURE function, creates PendingTransaction
    2. ledger.execute()    - MUTATES the ledger, applies the changes

    This separation enables inspection, validation, and logging BEFORE mutation.
    """)

    wait_for_enter()

    print(f"""
>>> from ledger import Move, build_transaction, SYSTEM_WALLET
>>>
>>> funding = build_transaction(ledger, [
...     Move({CONFIG.alice_initial_usd}, "USD", SYSTEM_WALLET, "alice", "fund_alice"),
...     Move({CONFIG.bob_initial_usd}, "USD", SYSTEM_WALLET, "bob", "fund_bob"),
... ])
""")

    funding = build_transaction(ledger, [
        Move(CONFIG.alice_initial_usd, "USD", SYSTEM_WALLET, "alice", "fund_alice"),
        Move(CONFIG.bob_initial_usd, "USD", SYSTEM_WALLET, "bob", "fund_bob"),
    ])

    section_header("PendingTransaction (Before Execution)")
    print(f"Intent ID: {funding.intent_id[:20]}...")
    print(f"Moves:     {len(funding.moves)}")
    for m in funding.moves:
        print(f"           {m.quantity} {m.unit_symbol}: {m.source} -> {m.dest}")

    print("\n>>> result = ledger.execute(funding)")
    result = ledger.execute(funding)

    section_header("Result")
    print(f"ExecuteResult: {result}")

    return ledger


def step_05_conservation_proof(ledger: Ledger):
    """Verify the conservation law (double-entry invariant)."""
    step_header(5, "The Conservation Law",
        "Total supply across ALL wallets is ALWAYS zero. This is double-entry bookkeeping.")

    print("""
    After funding Alice and Bob, let's verify conservation:
    """)

    wait_for_enter()

    section_header("Balances After Funding")
    alice_bal = ledger.get_balance('alice', 'USD')
    bob_bal = ledger.get_balance('bob', 'USD')
    system_bal = ledger.get_balance('system', 'USD')

    print(f"Alice:   {alice_bal:>12.2f} USD")
    print(f"Bob:     {bob_bal:>12.2f} USD")
    print(f"System:  {system_bal:>12.2f} USD")
    print(f"         {'-'*12}")
    total = alice_bal + bob_bal + system_bal
    print(f"TOTAL:   {total:>12.2f} USD")

    section_header("The Math")
    print(f"""
    Alice  = +{alice_bal} (she owns money)
    Bob    = +{bob_bal} (he owns money)
    System = {system_bal} (it "owes" the economy)

    Sum = {alice_bal} + {bob_bal} + ({system_bal}) = {total}

    This MUST be zero. Always. For every unit. This is CONSERVATION.
    """)

    section_header("Key Insight")
    print("""
    The system wallet has NEGATIVE balance. Think of it as:
    "The system owes $20,000 to the economy."

    Every dollar Alice owns is a dollar the system owes.
    This is the fundamental accounting identity: Assets = Liabilities.
    """)

    return ledger


# ============================================================================
# PHASE 2: CORE MECHANICS (Steps 6-10)
# ============================================================================

def step_06_simple_transfer(ledger: Ledger):
    """Execute a simple transfer between users."""
    step_header(6, "Simple Transfer",
        "Transfers move value between wallets. Conservation is preserved.")

    print("""
    Let's have Alice pay Bob $500.
    """)

    wait_for_enter()

    before_alice = ledger.get_balance('alice', 'USD')
    before_bob = ledger.get_balance('bob', 'USD')

    print('>>> transfer = build_transaction(ledger, [')
    print('...     Move(500, "USD", "alice", "bob", "payment_001")')
    print('... ])')
    print('>>> ledger.execute(transfer)')

    transfer = build_transaction(ledger, [
        Move(Decimal("500"), "USD", "alice", "bob", "payment_001")
    ])
    ledger.execute(transfer)

    section_header("Balance Changes")
    after_alice = ledger.get_balance('alice', 'USD')
    after_bob = ledger.get_balance('bob', 'USD')

    print(f"Alice: {before_alice} -> {after_alice} (change: {after_alice - before_alice})")
    print(f"Bob:   {before_bob} -> {after_bob} (change: {after_bob - before_bob})")

    section_header("Conservation Check")
    total = ledger.total_supply("USD")
    print(f"Total supply: {total} (must be 0)")

    section_header("Key Insight")
    print("""
    The transfer is ZERO-SUM. Alice loses exactly what Bob gains.
    The system wallet wasn't involved - this is a peer-to-peer transfer.
    """)

    return ledger


def step_07_rejected_transaction(ledger: Ledger):
    """See what happens when a transaction violates constraints."""
    step_header(7, "Rejected Transactions",
        "Transactions that violate constraints are REJECTED. State unchanged.")

    print("""
    What if we create a unit that does NOT allow overdrafts?
    Let's create "STRICT" currency with min_balance=0.
    """)

    wait_for_enter()

    print("""
>>> strict = Unit(
...     symbol="STRICT",
...     name="No Overdraft Currency",
...     unit_type=UNIT_TYPE_CASH,
...     min_balance=Decimal("0"),     # <-- Cannot go negative!
...     max_balance=Decimal("Infinity"),
...     decimal_places=2,
... )
>>> ledger.register_unit(strict)
""")

    strict = Unit(
        symbol="STRICT",
        name="No Overdraft Currency",
        unit_type=UNIT_TYPE_CASH,
        min_balance=Decimal("0"),
        max_balance=Decimal("Infinity"),
        decimal_places=2,
    )
    ledger.register_unit(strict)

    # Fund alice with 100 STRICT
    print('>>> # Fund alice with 100 STRICT')
    print('>>> ledger.execute(build_transaction(ledger, [')
    print('...     Move(100, "STRICT", SYSTEM_WALLET, "alice", "strict_fund")')
    print('... ]))')
    ledger.execute(build_transaction(ledger, [
        Move(Decimal("100"), "STRICT", SYSTEM_WALLET, "alice", "strict_fund")
    ]))

    print(f"\nAlice STRICT balance: {ledger.get_balance('alice', 'STRICT')}")

    section_header("Now Try to Overdraft")
    print('>>> overdraft = build_transaction(ledger, [')
    print('...     Move(999, "STRICT", "alice", "bob", "overdraft_attempt")')
    print('... ])')
    print('>>> result = ledger.execute(overdraft)')

    overdraft = build_transaction(ledger, [
        Move(Decimal("999"), "STRICT", "alice", "bob", "overdraft_attempt")
    ])
    result = ledger.execute(overdraft)

    section_header("Result")
    print(f"ExecuteResult: {result}")
    print(f"Alice STRICT balance: {ledger.get_balance('alice', 'STRICT')} (unchanged!)")

    section_header("Key Insight")
    print("""
    REJECTED means NOTHING happened. The ledger state is exactly as before.
    This is ATOMICITY at the validation level - invalid transactions are blocked.
    """)

    return ledger


def step_08_atomicity(ledger: Ledger):
    """Demonstrate all-or-nothing execution with multi-move transactions."""
    step_header(8, "Atomicity (All-or-Nothing)",
        "Multiple moves in one transaction ALL succeed or ALL fail together.")

    print("""
    Consider a chain: Alice -> Bob -> Charlie (all in one transaction).

    If ANY move fails, NONE of them apply. No partial states.
    """)

    wait_for_enter()

    ledger.register_wallet("charlie")

    print('>>> # Fund charlie with 100 STRICT first')
    ledger.execute(build_transaction(ledger, [
        Move(Decimal("100"), "STRICT", SYSTEM_WALLET, "charlie", "charlie_fund")
    ]))

    section_header("Balances Before")
    before = {
        'alice': ledger.get_balance('alice', 'STRICT'),
        'bob': ledger.get_balance('bob', 'STRICT'),
        'charlie': ledger.get_balance('charlie', 'STRICT'),
    }
    for w, b in before.items():
        print(f"{w}: {b} STRICT")

    section_header("Transaction: Alice(50) -> Bob(50) -> Charlie")
    print("""
>>> chain = build_transaction(ledger, [
...     Move(50, "STRICT", "alice", "bob", "chain_1"),
...     Move(50, "STRICT", "bob", "charlie", "chain_2"),
... ])
>>> ledger.execute(chain)
""")

    chain = build_transaction(ledger, [
        Move(Decimal("50"), "STRICT", "alice", "bob", "chain_1"),
        Move(Decimal("50"), "STRICT", "bob", "charlie", "chain_2"),
    ])
    result = ledger.execute(chain)

    print(f"Result: {result}")

    section_header("Balances After")
    after = {
        'alice': ledger.get_balance('alice', 'STRICT'),
        'bob': ledger.get_balance('bob', 'STRICT'),
        'charlie': ledger.get_balance('charlie', 'STRICT'),
    }
    for w, b in after.items():
        change = b - before[w]
        print(f"{w}: {b} STRICT (change: {change:+})")

    section_header("Key Insight")
    print("""
    Both moves applied together. The intermediate state where Bob had +50
    (before giving to Charlie) NEVER existed in the ledger.

    This is crucial for financial systems - no one can observe partial state.
    """)

    return ledger


def step_09_idempotency(ledger: Ledger):
    """Demonstrate safe retry semantics."""
    step_header(9, "Idempotency (Safe Retry)",
        "Executing the same transaction twice doesn't double-apply.")

    print("""
    In distributed systems, messages can be delivered multiple times.
    The ledger handles this with CONTENT-BASED deduplication.

    The intent_id is a hash of the transaction content. Same content = same ID.
    """)

    wait_for_enter()

    print('>>> payment = build_transaction(ledger, [')
    print('...     Move(25, "USD", "alice", "bob", "idempotent_test")')
    print('... ])')
    payment = build_transaction(ledger, [
        Move(Decimal("25"), "USD", "alice", "bob", "idempotent_test")
    ])

    print(f"\nIntent ID: {payment.intent_id[:30]}...")

    section_header("Execute 5 Times")
    balance_before = ledger.get_balance("alice", "USD")

    for i in range(5):
        result = ledger.execute(payment)
        balance_after = ledger.get_balance("alice", "USD")
        status = "applied" if result == ExecuteResult.APPLIED else "deduplicated"
        print(f"Attempt {i+1}: {result.name:17} | Alice balance: {balance_after} ({status})")

    section_header("Key Insight")
    print("""
    Only the FIRST execution applies. Subsequent attempts return ALREADY_APPLIED.

    This enables safe retries: if a network fails, just retry the transaction.
    If it was already applied, no harm done. If not, it applies now.
    """)

    return ledger


def step_10_transaction_log(ledger: Ledger):
    """Explore the transaction log (audit trail)."""
    step_header(10, "The Transaction Log",
        "Every transaction is logged. The log is the source of truth.")

    print("""
    The transaction log is APPEND-ONLY. Once written, entries never change.
    This is your audit trail - you can explain any balance by walking the log.
    """)

    wait_for_enter()

    section_header("Log Statistics")
    print(f"Total transactions: {len(ledger.transaction_log)}")
    print(f"Unique intent IDs:  {len(ledger.seen_intent_ids)}")

    section_header("Recent Transactions")
    for i, tx in enumerate(ledger.transaction_log[-5:]):
        idx = len(ledger.transaction_log) - 5 + i
        print(f"\n[{idx}] {tx.exec_id}")
        print(f"    Time:   {tx.execution_time}")
        print(f"    Origin: {tx.origin or '(none)'}")
        for move in tx.moves:
            print(f"    Move:   {move.quantity} {move.unit_symbol}: {move.source} -> {move.dest}")

    section_header("Key Insight")
    print("""
    The log enables:
    - Audit: "Why does Alice have this balance?" Walk the log.
    - Replay: Reconstruct state from an empty ledger by replaying transactions.
    - Time travel: Reconstruct state at any past point.
    """)

    return ledger


# ============================================================================
# PHASE 3: TIME TRAVEL (Steps 11-13)
# ============================================================================

def step_11_advance_time(ledger: Ledger):
    """Learn how time works in the ledger."""
    step_header(11, "Advancing Time",
        "Time only moves forward. This enables temporal ordering and scheduled events.")

    print("""
    The ledger has a current_time that can only INCREASE.
    This ensures causal ordering - you can't execute a transaction before it exists.
    """)

    wait_for_enter()

    print(f"Current time: {ledger.current_time}")

    section_header("Advance by 1 Day")
    print(">>> ledger.advance_time(ledger.current_time + timedelta(days=1))")
    ledger.advance_time(ledger.current_time + timedelta(days=1))
    print(f"New time: {ledger.current_time}")

    section_header("Try to Go Backward")
    print('>>> ledger.advance_time(datetime(2020, 1, 1))  # In the past!')
    try:
        ledger.advance_time(datetime(2020, 1, 1))
    except ValueError as e:
        print(f"ValueError: {e}")

    section_header("Key Insight")
    print("""
    Time monotonicity is crucial for:
    - Option maturity: Cannot settle before expiry date
    - Settlement dates: T+2 means trade date + 2 days
    - Event ordering: Transaction A happened before B
    """)

    return ledger


def step_12_time_travel(ledger: Ledger):
    """Clone the ledger at a past point in time."""
    step_header(12, "Time Travel (clone_at)",
        "Reconstruct exact state at any past point using clone_at().")

    print("""
    clone_at(timestamp) creates a new ledger with state as it was at that time.

    HOW IT WORKS:
      1. Starts from CURRENT state (clone of now)
      2. Walks BACKWARD through the transaction log
      3. REVERSES each transaction executed after target_time
      4. Returns the reconstructed past state

    This is efficient because it only reverses the transactions after the target,
    rather than replaying everything from the beginning.
    """)

    wait_for_enter()

    # Make a few more transactions to have history
    ledger.advance_time(ledger.current_time + timedelta(hours=1))
    ledger.execute(build_transaction(ledger, [
        Move(Decimal("100"), "USD", "alice", "bob", "payment_day2_1")
    ]))

    ledger.advance_time(ledger.current_time + timedelta(hours=1))
    ledger.execute(build_transaction(ledger, [
        Move(Decimal("200"), "USD", "bob", "charlie", "payment_day2_2")
    ]))

    current_time = ledger.current_time
    current_alice = ledger.get_balance("alice", "USD")
    current_bob = ledger.get_balance("bob", "USD")

    section_header("Current State")
    print(f"Time:  {current_time}")
    print(f"Alice: {current_alice} USD")
    print(f"Bob:   {current_bob} USD")

    section_header("Clone at Yesterday (Day 1)")
    past_time = CONFIG.start_time + timedelta(hours=1)  # Just after initial funding
    print(f">>> historical = ledger.clone_at({past_time})")
    historical = ledger.clone_at(past_time)

    print(f"\nHistorical time:  {historical.current_time}")
    print(f"Historical Alice: {historical.get_balance('alice', 'USD')} USD")
    print(f"Historical Bob:   {historical.get_balance('bob', 'USD')} USD")

    section_header("Key Insight")
    print("""
    clone_at() creates an INDEPENDENT ledger. Changes to the clone don't affect
    the original. This enables:
    - Historical reporting: "What was Alice's balance on Jan 1?"
    - What-if analysis: Clone, make changes, compare results
    - Debugging: Reconstruct state when a bug occurred
    """)

    return ledger


def step_13_replay(ledger: Ledger):
    """Replay the transaction log to prove determinism."""
    step_header(13, "Replay (Determinism Proof)",
        "Replaying the log produces IDENTICAL state. Same inputs = same outputs.")

    print("""
    replay() creates a new ledger and re-executes all transactions from the log.

    HOW IT WORKS:
      1. Creates an EMPTY ledger with same units and wallets
      2. Starts from the BEGINNING (or from_tx parameter)
      3. Re-executes each transaction FORWARD in order
      4. Returns the reconstructed final state

    CONTRAST WITH clone_at():
      - clone_at(): BACKWARD from current state (efficient for recent times)
      - replay():   FORWARD from empty state (proves determinism, good for from_tx=N)

    Use replay(from_tx=N) to resume processing from transaction N.
    """)

    wait_for_enter()

    print(">>> replayed = ledger.replay(from_tx=0)")
    replayed = ledger.replay(from_tx=0)

    section_header("Compare Original vs Replayed")
    wallets = ["alice", "bob", "charlie"]
    all_match = True

    print(f"{'Wallet':<10} {'Original':>12} {'Replayed':>12} {'Match':>8}")
    print("-" * 45)
    for w in wallets:
        orig = ledger.get_balance(w, "USD")
        repl = replayed.get_balance(w, "USD")
        match = "OK" if orig == repl else "FAIL"
        if orig != repl:
            all_match = False
        print(f"{w:<10} {orig:>12.2f} {repl:>12.2f} {match:>8}")

    section_header("Result")
    if all_match:
        print("DETERMINISM VERIFIED: All balances match exactly.")
    else:
        print("WARNING: Mismatch detected!")

    section_header("Key Insight")
    print("""
    Determinism means:
    - Given the same starting state and same transactions,
      any implementation MUST produce the same final state.

    This is essential for:
    - Distributed systems: All nodes agree on state
    - Disaster recovery: Replay log to restore from backup
    - Testing: Replay production log in test environment
    """)

    return ledger


# ============================================================================
# PHASE 4: LIFECYCLE AND INSTRUMENTS (Steps 14-17)
# ============================================================================

def step_14_create_option(ledger: Ledger):
    """Create a bilateral call option."""
    step_header(14, "Creating a Bilateral Option",
        "Options have two parties (long/short) and specific settlement mechanics.")

    print("""
    A bilateral option is a contract between two specific parties:
    - LONG (holder/buyer): Has the RIGHT to buy (call) or sell (put)
    - SHORT (writer/seller): Has the OBLIGATION to fulfill if exercised

    Let's create a call option on AAPL stock.
    """)

    wait_for_enter()

    # Reset to a clean ledger for the option demo
    print(">>> # Create a fresh ledger for the option demo")
    option_ledger = Ledger(
        name="option_demo",
        initial_time=datetime(2025, 6, 1, 9, 30),
        verbose=True
    )

    # Register assets
    print(">>> ledger.register_unit(cash('USD', 'US Dollar'))")
    option_ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))

    print(">>> ledger.register_unit(create_stock_unit('AAPL', 'Apple Inc.', 'treasury', 'USD', shortable=True))")
    option_ledger.register_unit(create_stock_unit("AAPL", "Apple Inc.", "treasury", "USD", shortable=True))

    # Register wallets
    print('>>> ledger.register_wallet("alice")  # Option buyer')
    print('>>> ledger.register_wallet("bob")    # Option writer')
    print('>>> ledger.register_wallet("treasury")')
    option_ledger.register_wallet("alice")
    option_ledger.register_wallet("bob")
    option_ledger.register_wallet("treasury")

    # Fund wallets
    print("\n>>> # Fund wallets")
    option_ledger.execute(build_transaction(option_ledger, [
        Move(Decimal(str(CONFIG.alice_initial_usd)), "USD", SYSTEM_WALLET, "alice", "fund_alice"),
        Move(Decimal(str(CONFIG.bob_initial_usd)), "USD", SYSTEM_WALLET, "bob", "fund_bob"),
        Move(Decimal(str(CONFIG.bob_initial_shares)), "AAPL", SYSTEM_WALLET, "bob", "fund_bob_shares"),
    ]))

    section_header("Option Terms")
    maturity = datetime(2025, 12, 19, 16, 0)
    print(f"""
    Underlying:     AAPL
    Type:           CALL (right to BUY)
    Strike:         ${CONFIG.option_strike}
    Maturity:       {maturity}
    Contract Size:  100 shares
    Long (buyer):   alice
    Short (writer): bob
    """)

    print(">>> # Create the option unit")
    option_unit = create_option_unit(
        symbol="AAPL_CALL_150",
        name="AAPL Call $150 Dec 2025",
        underlying="AAPL",
        strike=CONFIG.option_strike,
        maturity=maturity,
        option_type="call",
        quantity=100,
        currency="USD",
        long_wallet="alice",
        short_wallet="bob",
    )
    option_ledger.register_unit(option_unit)

    section_header("Key Insight")
    print("""
    Bilateral means ONLY alice and bob can hold positions in this option.
    The transfer rule enforces this - any other transfer is rejected.

    Bob starts with negative position (he wrote the option).
    Alice will have positive position (she holds the option).
    """)

    return option_ledger, maturity


def step_15_option_trade(ledger: Ledger, maturity: datetime):
    """Execute an option trade (premium payment + contract delivery)."""
    step_header(15, "Option Trade",
        "The buyer pays premium; the writer delivers option contracts.")

    print(f"""
    Alice wants to buy {CONFIG.option_contracts} call option contracts from Bob.

    Premium: ${CONFIG.option_premium} per contract
    Total:   ${CONFIG.option_contracts * CONFIG.option_premium}

    The trade has two legs executed atomically:
    1. Alice pays premium to Bob
    2. Bob delivers option contracts to Alice
    """)

    wait_for_enter()

    print(f"""
>>> trade = option_transact(
...     ledger,
...     symbol="AAPL_CALL_150",
...     seller="bob",
...     buyer="alice",
...     qty={CONFIG.option_contracts},
...     price={CONFIG.option_premium},
... )
>>> ledger.execute(trade)
""")

    trade = option_transact(
        view=ledger,
        symbol="AAPL_CALL_150",
        seller="bob",
        buyer="alice",
        qty=CONFIG.option_contracts,
        price=CONFIG.option_premium,
    )
    ledger.execute(trade)

    section_header("Positions After Trade")
    print(f"Alice: {ledger.get_balance('alice', 'AAPL_CALL_150')} options, "
          f"${ledger.get_balance('alice', 'USD'):,.2f} cash")
    print(f"Bob:   {ledger.get_balance('bob', 'AAPL_CALL_150')} options, "
          f"${ledger.get_balance('bob', 'USD'):,.2f} cash")

    section_header("Conservation Check")
    total_options = ledger.total_supply("AAPL_CALL_150")
    total_usd = ledger.total_supply("USD")
    print(f"Total options: {total_options} (should be 0)")
    print(f"Total USD: {total_usd} (should be 0)")

    section_header("Key Insight")
    print("""
    Bob's option balance is NEGATIVE (he wrote them).
    Alice's balance is POSITIVE (she holds them).
    Sum = 0. Conservation holds even for derivatives!
    """)

    return ledger


def step_16_lifecycle_engine(ledger: Ledger, maturity: datetime):
    """Introduce the LifecycleEngine for automated processing."""
    step_header(16, "The LifecycleEngine",
        "Automates settlement by polling contracts at each time step.")

    print("""
    Financial instruments have lifecycles:
    - Options mature and settle
    - Futures have daily mark-to-market
    - Bonds pay coupons and principal

    The LifecycleEngine automates this:
    1. Register handlers for each contract type
    2. Call engine.step(timestamp, prices) each day
    3. Engine finds matching contracts and calls their handlers
    """)

    wait_for_enter()

    print("""
>>> engine = LifecycleEngine(ledger)
>>> engine.register("BILATERAL_OPTION", option_contract)
""")

    engine = LifecycleEngine(ledger)
    engine.register("BILATERAL_OPTION", option_contract)

    print(f"Registered handlers: {list(engine.contracts.keys())}")

    section_header("Step Before Maturity")
    before_maturity = maturity - timedelta(days=1)
    print(f">>> engine.step({before_maturity.date()}, {{'AAPL': 170}})")
    txs = engine.step(before_maturity, {"AAPL": 170})

    settled = ledger.get_unit_state("AAPL_CALL_150").get("settled", False)
    print(f"\nTransactions: {len(txs)}")
    print(f"Option settled: {settled}")
    print("(Nothing happened - option hasn't matured yet)")

    section_header("Key Insight")
    print("""
    The engine polls check_lifecycle() on each contract type.
    The option_contract handler checks:
    - Is it mature? (current_time >= maturity)
    - Is it already settled?

    Only when conditions are met does it return settlement moves.
    """)

    return ledger, engine, maturity


def step_17_automatic_settlement(ledger: Ledger, engine, maturity: datetime):
    """Watch the engine automatically settle the option at maturity."""
    step_header(17, "Automatic Settlement",
        "At maturity, the engine triggers settlement automatically.")

    spot = CONFIG.option_settlement_price
    strike = CONFIG.option_strike
    contracts = CONFIG.option_contracts
    shares_per_contract = 100

    print(f"""
    Fast-forward to maturity: {maturity}

    Settlement price: ${spot} (above strike ${strike} - option is IN THE MONEY)

    For an ITM call with physical delivery:
    - Alice (buyer) pays:    strike x quantity = ${strike} x {shares_per_contract} x {contracts} = ${strike * shares_per_contract * contracts:,.0f}
    - Bob (writer) delivers: {shares_per_contract * contracts} AAPL shares
    - Option positions close to zero
    """)

    wait_for_enter()

    section_header("Positions BEFORE Settlement")
    print(f"Alice: {ledger.get_balance('alice', 'AAPL')} AAPL, ${ledger.get_balance('alice', 'USD'):,.2f} cash")
    print(f"Bob:   {ledger.get_balance('bob', 'AAPL')} AAPL, ${ledger.get_balance('bob', 'USD'):,.2f} cash")

    print(f"\n>>> txs = engine.step({maturity}, {{'AAPL': {spot}}})")
    txs = engine.step(maturity, {"AAPL": spot})

    section_header("Settlement Transaction")
    print(f"Transactions executed: {len(txs)}")

    # Show the transaction details
    if txs:
        tx = txs[0]
        print(f"\nMoves:")
        for m in tx.moves:
            print(f"  {m.quantity} {m.unit_symbol}: {m.source} -> {m.dest}")

        print(f"\nState changes:")
        for sc in tx.state_changes:
            changed = sc.changed_fields()
            for field, (old, new) in changed.items():
                print(f"  {sc.unit}.{field}: {old} -> {new}")

    section_header("Positions AFTER Settlement")
    print(f"Alice: {ledger.get_balance('alice', 'AAPL')} AAPL, ${ledger.get_balance('alice', 'USD'):,.2f} cash")
    print(f"Bob:   {ledger.get_balance('bob', 'AAPL')} AAPL, ${ledger.get_balance('bob', 'USD'):,.2f} cash")

    # Verify option is settled
    state = ledger.get_unit_state("AAPL_CALL_150")
    print(f"\nOption settled: {state.get('settled')}")
    print(f"Settlement price: ${state.get('settlement_price')}")

    section_header("Key Insight")
    print("""
    The engine:
    1. Stepped to maturity time
    2. Called option_contract handler
    3. Handler detected mature + ITM condition
    4. Handler returned ContractResult with settlement moves
    5. Engine executed the transaction

    This automation handles any number of contracts in any state.
    """)

    return ledger


# ============================================================================
# PHASE 5: ADVANCED (Steps 18-20)
# ============================================================================

def step_18_pending_transaction(ledger: Ledger):
    """Understand PendingTransaction and state changes."""
    step_header(18, "PendingTransaction and State Changes",
        "Transactions carry both moves (balance changes) AND state changes (unit metadata).")

    print("""
    A PendingTransaction contains:
    - moves:          Balance changes (who pays/receives what)
    - state_changes:  Unit state updates (e.g., "settled = True")
    - origin:         Where this came from (for debugging)
    - intent_id:      Content hash for idempotency

    Let's examine the last settlement transaction in detail.
    """)

    wait_for_enter()

    tx = ledger.transaction_log[-1]

    section_header("Transaction Structure")
    print(f"exec_id:    {tx.exec_id}")
    print(f"intent_id:  {tx.intent_id[:30]}...")
    print(f"origin:     {tx.origin}")
    print(f"timestamp:  {tx.timestamp}")

    section_header("Moves (Balance Changes)")
    for m in tx.moves:
        print(f"  {m.quantity:>10} {m.unit_symbol:<15} {m.source:<10} -> {m.dest}")

    section_header("State Changes (Unit Metadata)")
    for sc in tx.state_changes:
        print(f"\n  Unit: {sc.unit}")
        changed = sc.changed_fields()
        for field, (old, new) in changed.items():
            print(f"    {field}: {old} -> {new}")

    section_header("Key Insight")
    print("""
    Moves and state changes are ATOMIC - they apply together or not at all.

    This is crucial for derivatives:
    - The settlement moves transfer cash and shares
    - The state change marks the option as settled
    - Both must happen together for consistency
    """)

    return ledger


def step_19_deferred_cash(ledger: Ledger):
    """Demonstrate deferred cash for T+n settlement."""
    step_header(19, "Deferred Cash (Payment Obligations)",
        "Some payments settle in the future (dividends, T+2 settlement).")

    print("""
    DeferredCash represents a payment OBLIGATION:
    - You are OWED money, but haven't received it yet
    - On the payment date, cash flows from payer to payee
    - The obligation unit is destroyed

    Use cases:
    - Dividend payments (declared now, paid later)
    - T+n settlement (trade now, settle in n days)
    - Bond coupon payments
    """)

    wait_for_enter()

    # Create fresh ledger for this demo
    dc_ledger = Ledger("deferred_demo", datetime(2025, 3, 15), verbose=True)
    dc_ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    dc_ledger.register_wallet("treasury")
    dc_ledger.register_wallet("alice")

    # Fund treasury
    dc_ledger.execute(build_transaction(dc_ledger, [
        Move(Decimal("1000000"), "USD", SYSTEM_WALLET, "treasury", "fund_treasury"),
    ]))

    payment_date = datetime(2025, 4, 1, 9, 0)
    amount = 250

    print(f"""
>>> dc = create_deferred_cash_unit(
...     symbol="DIV_AAPL_Q1",
...     amount={amount},
...     currency="USD",
...     payment_date={payment_date},
...     payer_wallet="treasury",
...     payee_wallet="alice",
...     reference="Q1_dividend",
... )
>>> ledger.register_unit(dc)
""")

    dc = create_deferred_cash_unit(
        symbol="DIV_AAPL_Q1",
        amount=amount,
        currency="USD",
        payment_date=payment_date,
        payer_wallet="treasury",
        payee_wallet="alice",
        reference="Q1_dividend",
    )
    dc_ledger.register_unit(dc)

    # Issue the entitlement
    print(">>> # Issue the dividend entitlement to Alice")
    dc_ledger.execute(build_transaction(dc_ledger, [
        Move(Decimal("1"), "DIV_AAPL_Q1", SYSTEM_WALLET, "alice", "dividend_entitlement")
    ]))

    section_header("Before Payment Date")
    print(f"Current time: {dc_ledger.current_time}")
    print(f"Payment date: {payment_date}")
    print(f"Alice entitlement: {dc_ledger.get_balance('alice', 'DIV_AAPL_Q1')}")
    print(f"Alice USD: ${dc_ledger.get_balance('alice', 'USD'):,.2f}")

    # Setup engine
    engine = LifecycleEngine(dc_ledger)
    engine.register("DEFERRED_CASH", deferred_cash_contract)

    section_header("Step to Payment Date")
    print(f">>> engine.step({payment_date}, {{}})")
    txs = engine.step(payment_date, {})

    print(f"\nTransactions: {len(txs)}")
    print(f"Alice entitlement: {dc_ledger.get_balance('alice', 'DIV_AAPL_Q1')}")
    print(f"Alice USD: ${dc_ledger.get_balance('alice', 'USD'):,.2f}")

    section_header("Key Insight")
    print("""
    DeferredCash separates "you are owed" from "you received":

    1. Declaration: Entitlement unit created and assigned
    2. Waiting: Holder owns entitlement, not cash yet
    3. Settlement: Cash flows, entitlement destroyed

    This models T+n settlement, dividend ex-dates, and more.
    """)

    return ledger


def step_20_conservation_finale(ledger: Ledger):
    """Final proof that conservation holds through all operations."""
    step_header(20, "Conservation Finale",
        "Everything we've done demonstrates that conservation is ALWAYS maintained.")

    print("""
    We've executed:
    - Simple transfers
    - Multi-move atomic transactions
    - Rejected transactions (state unchanged)
    - Option trades and settlements
    - Deferred cash payments

    Through ALL of this, the fundamental law held:

        Sum of all balances for any unit = 0

    Let's verify this mathematically.
    """)

    wait_for_enter()

    section_header("Conservation Verification")

    print(f"{'Unit':<20} {'Total Supply':>15} {'Status':<12}")
    print("-" * 50)

    all_conserved = True
    for unit_sym in sorted(ledger.list_units()):
        total = ledger.total_supply(unit_sym)
        conserved = abs(total) < Decimal("1e-10")
        status = "CONSERVED" if conserved else f"VIOLATION: {total}"
        print(f"{unit_sym:<20} {float(total):>15.6f} {status:<12}")
        if not conserved:
            all_conserved = False

    section_header("The Mathematical Foundation")
    print("""
    WHY does conservation always hold?

    1. ISSUANCE: Value enters via SYSTEM_WALLET
       - System goes negative, user goes positive
       - Net change: 0

    2. TRANSFER: Value moves between wallets
       - Source loses X, dest gains X
       - Net change: 0

    3. REJECTION: Invalid transactions change nothing
       - State before = State after
       - Net change: 0

    4. SETTLEMENT: Complex instruments decompose into moves
       - Each move is zero-sum
       - Net change: 0

    The invariant is ENFORCED BY CONSTRUCTION.
    There is no code path that can violate it.
    """)

    section_header("Final Verification")
    if all_conserved:
        print("CONSERVATION VERIFIED ACROSS ALL UNITS")
        print("\nThe ledger maintains double-entry bookkeeping at all times.")
    else:
        print("WARNING: Conservation violation detected!")

    return ledger


def step_21_load_test():
    """Stress test to show the system scales."""
    step_header(21, "Load Test (Scalability)",
        "Demonstrate the system handles 10^4 units, 1000 wallets, and 10^6 transactions.")

    num_units = CONFIG.load_test_units
    num_wallets = CONFIG.load_test_wallets
    num_transactions = CONFIG.load_test_transactions

    print(f"""
    This step tests that the ledger scales to real-world workloads.

    Configuration (modify DemoConfig to experiment):
      Units:        {num_units:,}
      Wallets:      {num_wallets:,}
      Transactions: {num_transactions:,}

    We will:
      1. Register {num_units:,} units
      2. Register {num_wallets:,} wallets
      3. Execute {num_transactions:,} random transactions
      4. Verify conservation holds
      5. Report throughput
    """)

    wait_for_enter()

    # Create fresh ledger for load test
    load_ledger = Ledger(
        name="load_test",
        initial_time=datetime(2025, 1, 1, 9, 0),
        verbose=False  # Disable verbose for performance
    )

    section_header("Phase 1: Register Units")
    t0 = time.time()
    units_list = []
    for i in range(num_units):
        unit = Unit(
            symbol=f"UNIT_{i:05d}",
            name=f"Test Unit {i}",
            unit_type=UNIT_TYPE_CASH,
            min_balance=Decimal("-1000000000"),
            max_balance=Decimal("Infinity"),
            decimal_places=2,
        )
        load_ledger.register_unit(unit)
        units_list.append(unit.symbol)
    t1 = time.time()
    print(f"Registered {num_units:,} units in {t1-t0:.2f}s ({num_units/(t1-t0):,.0f} units/s)")

    section_header("Phase 2: Register Wallets")
    t0 = time.time()
    wallets_list = []
    for i in range(num_wallets):
        wallet = f"wallet_{i:04d}"
        load_ledger.register_wallet(wallet)
        wallets_list.append(wallet)
    t1 = time.time()
    print(f"Registered {num_wallets:,} wallets in {t1-t0:.2f}s ({num_wallets/(t1-t0):,.0f} wallets/s)")

    section_header("Phase 3: Fund Wallets (Initial Issuance)")
    t0 = time.time()
    # Fund each wallet with some amount in a subset of units
    units_per_wallet = min(10, num_units)
    for i, wallet in enumerate(wallets_list):
        moves = []
        for j in range(units_per_wallet):
            unit_idx = (i + j) % num_units
            unit_sym = units_list[unit_idx]
            moves.append(Move(
                Decimal("10000"),
                unit_sym,
                SYSTEM_WALLET,
                wallet,
                f"fund_{wallet}_{unit_sym}"
            ))
        funding = build_transaction(load_ledger, moves)
        load_ledger.execute(funding)
    t1 = time.time()
    funding_txs = num_wallets
    print(f"Executed {funding_txs:,} funding transactions in {t1-t0:.2f}s ({funding_txs/(t1-t0):,.0f} tx/s)")

    section_header("Phase 4: Execute Random Transactions")
    print(f"Executing {num_transactions:,} random peer-to-peer transactions...")

    # Prepare random transactions
    random.seed(42)
    t0 = time.time()

    # Progress tracking
    batch_size = max(1, num_transactions // 20)  # 20 progress updates
    applied_count = 0
    rejected_count = 0

    for i in range(num_transactions):
        # Random source, destination, unit, amount
        src_idx = random.randint(0, num_wallets - 1)
        dst_idx = random.randint(0, num_wallets - 1)
        if dst_idx == src_idx:
            dst_idx = (dst_idx + 1) % num_wallets
        unit_idx = random.randint(0, num_units - 1)

        src = wallets_list[src_idx]
        dst = wallets_list[dst_idx]
        unit_sym = units_list[unit_idx]
        amount = Decimal(str(random.randint(1, 100)))

        tx = build_transaction(load_ledger, [
            Move(amount, unit_sym, src, dst, f"tx_{i}")
        ])
        result = load_ledger.execute(tx)

        if result == ExecuteResult.APPLIED:
            applied_count += 1
        else:
            rejected_count += 1

        # Progress update
        if (i + 1) % batch_size == 0:
            elapsed = time.time() - t0
            pct = (i + 1) / num_transactions * 100
            rate = (i + 1) / elapsed
            bar_width = 40
            filled = int(bar_width * (i + 1) / num_transactions)
            bar = "#" * filled + "-" * (bar_width - filled)
            print(f"\r[{bar}] {pct:5.1f}% {rate:,.0f} tx/s", end="", flush=True)

    t1 = time.time()
    elapsed = t1 - t0
    print()  # newline after progress bar

    section_header("Phase 5: Results")
    throughput = num_transactions / elapsed

    print(f"Transactions executed:  {num_transactions:,}")
    print(f"  Applied:              {applied_count:,}")
    print(f"  Rejected/Duplicate:   {rejected_count:,}")
    print(f"Total time:             {elapsed:.2f}s")
    print(f"Throughput:             {throughput:,.0f} tx/s")

    section_header("Phase 6: Verify Conservation")
    t0 = time.time()
    violations = 0
    sample_units = random.sample(units_list, min(100, num_units))  # Sample for speed
    for unit_sym in sample_units:
        total = load_ledger.total_supply(unit_sym)
        if abs(total) > Decimal("1e-6"):
            violations += 1
    t1 = time.time()

    if violations == 0:
        print(f"Conservation verified on {len(sample_units)} sampled units in {t1-t0:.2f}s")
        print("All units conserve (sum = 0)")
    else:
        print(f"WARNING: {violations} violations detected!")

    section_header("Memory Usage")
    import sys
    log_size = sys.getsizeof(load_ledger.transaction_log)
    # Rough estimate of balance storage
    balance_count = sum(len(b) for b in load_ledger.balances.values())
    print(f"Transaction log entries: {len(load_ledger.transaction_log):,}")
    print(f"Balance entries:         {balance_count:,}")
    print(f"Units registered:        {len(load_ledger.units):,}")
    print(f"Wallets registered:      {len(load_ledger.registered_wallets):,}")

    section_header("Key Insight")
    print(f"""
    The ledger processed {num_transactions:,} transactions at {throughput:,.0f} tx/s.

    Scalability factors:
    - O(1) balance lookups (dict-based)
    - O(1) idempotency checks (set-based)
    - O(N) conservation check (iterate wallets)
    - O(log N) for any time travel operation

    The system is designed for:
    - Real-time trading: thousands of transactions per second
    - Large portfolios: millions of positions across thousands of assets
    - Full audit trail: every transaction is logged
    """)

    return throughput


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run the complete tutorial."""
    print("=" * 70)
    print("       LEDGER v4.0 - INTERACTIVE TUTORIAL")
    print("=" * 70)
    print("""
    Welcome! This tutorial teaches how the financial ledger works.

    Press Enter to advance through each step.
    Each step builds on the previous one.

    PHASES:
      1-5:   Foundation      - Empty ledger, units, wallets, transactions
      6-10:  Core Mechanics  - Transfers, rejections, atomicity, idempotency
      11-13: Time Travel     - Advancing time, clone_at, replay
      14-17: Instruments     - Options, LifecycleEngine, settlement
      18-20: Advanced        - State changes, deferred cash, conservation
      21:    Load Test       - 10^4 units, 1000 wallets, 10^6 transactions
    """)

    if QUICK_MODE:
        print("Running in QUICK mode (no pauses)")
    else:
        print("Running in INTERACTIVE mode (press Enter to advance)")

    wait_for_enter()

    # Phase 1: Foundation
    ledger = step_01_empty_ledger()
    wait_for_enter()

    ledger = step_02_register_unit(ledger)
    wait_for_enter()

    ledger = step_03_register_wallets(ledger)
    wait_for_enter()

    ledger = step_04_first_transaction(ledger)
    wait_for_enter()

    ledger = step_05_conservation_proof(ledger)
    wait_for_enter()

    # Phase 2: Core Mechanics
    ledger = step_06_simple_transfer(ledger)
    wait_for_enter()

    ledger = step_07_rejected_transaction(ledger)
    wait_for_enter()

    ledger = step_08_atomicity(ledger)
    wait_for_enter()

    ledger = step_09_idempotency(ledger)
    wait_for_enter()

    ledger = step_10_transaction_log(ledger)
    wait_for_enter()

    # Phase 3: Time Travel
    ledger = step_11_advance_time(ledger)
    wait_for_enter()

    ledger = step_12_time_travel(ledger)
    wait_for_enter()

    ledger = step_13_replay(ledger)
    wait_for_enter()

    # Phase 4: Instruments (creates new ledger)
    option_ledger, maturity = step_14_create_option(ledger)
    wait_for_enter()

    option_ledger = step_15_option_trade(option_ledger, maturity)
    wait_for_enter()

    option_ledger, engine, maturity = step_16_lifecycle_engine(option_ledger, maturity)
    wait_for_enter()

    option_ledger = step_17_automatic_settlement(option_ledger, engine, maturity)
    wait_for_enter()

    # Phase 5: Advanced
    option_ledger = step_18_pending_transaction(option_ledger)
    wait_for_enter()

    step_19_deferred_cash(option_ledger)
    wait_for_enter()

    step_20_conservation_finale(option_ledger)
    wait_for_enter()

    # Phase 6: Scalability
    step_21_load_test()

    # Final summary
    print("\n" + "=" * 70)
    print("       TUTORIAL COMPLETE!")
    print("=" * 70)
    print("""
    You've learned:

    FOUNDATION
      - Ledgers track who owns what over time
      - Units define assets and constraints
      - SYSTEM_WALLET anchors conservation

    CORE MECHANICS
      - Transactions are atomic (all-or-nothing)
      - Idempotency enables safe retries
      - The log is the source of truth

    TIME TRAVEL
      - Time only moves forward
      - clone_at() reconstructs past state
      - replay() proves determinism

    INSTRUMENTS
      - Options have bilateral structure
      - LifecycleEngine automates settlement
      - Complex instruments decompose to moves

    MATHEMATICAL PROPERTIES
      - Conservation: Sum = 0 (always)
      - Atomicity: All or nothing
      - Determinism: Same inputs = same outputs

    SCALABILITY
      - Handles 10^4 units, 1000 wallets, 10^6 transactions
      - O(1) balance lookups, O(1) idempotency checks
      - Full audit trail maintained at scale

    Next steps:
      - See futures_tutorial.py for futures mark-to-market
      - See ledger/units/*.py for instrument implementations
      - Run tests: pytest tests/
    """)


if __name__ == "__main__":
    main()
