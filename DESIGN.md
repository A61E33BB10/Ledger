# Ledger System Design

**Version:** 1.0
**Purpose:** Comprehensive system design documentation for developers

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Core Philosophy](#2-core-philosophy)
3. [Foundational Concepts](#3-foundational-concepts)
4. [Architecture Overview](#4-architecture-overview)
5. [Key Data Structures](#5-key-data-structures)
6. [The Transaction Model](#6-the-transaction-model)
7. [The Ledger](#7-the-ledger)
8. [Smart Contracts](#8-smart-contracts)
9. [Design Patterns](#9-design-patterns)
10. [Unit Types and Lifecycle](#10-unit-types-and-lifecycle)
11. [Conservation Laws and Invariants](#11-conservation-laws-and-invariants)
12. [State Management](#12-state-management)
13. [Code Organization](#13-code-organization)

---

## 1. Introduction

### 1.1 What This System Does

The Ledger is a **closed financial accounting system** built on double-entry bookkeeping principles. It serves two complementary purposes:

**Record Keeping (Production Use)**
- Track real portfolios with full audit trails
- Maintain accurate ownership records across any asset class
- Support reconciliation with external systems
- Provide complete transaction history for compliance and reporting

**Simulation (Analysis Use)**
- Run Monte Carlo simulations with thousands of price paths
- Backtest trading strategies on historical data
- Train reinforcement learning agents
- Analyze risk metrics and outcome distributions

The same core business logic serves both purposes. The difference lies in configuration:
- Record keeping: `verbose=True`, `fast_mode=False`, `no_log=False` (full validation and audit)
- Simulation: `verbose=False`, `fast_mode=True`, `no_log=True` (maximum throughput)

### 1.2 Asset Class Agnostic

The framework is **not limited to equities**. It can represent any asset that can be owned and transferred:

| Asset Class        | Examples                              |
|--------------------|---------------------------------------|
| **Equities**       | Stocks, ETFs, ADRs                    |
| **Fixed Income**   | Bonds, notes, bills, loans            |
| **Currencies**     | USD, EUR, GBP, JPY, cryptocurrencies  |
| **Commodities**    | Gold, oil, wheat, natural gas         |
| **Derivatives**    | Options, futures, forwards, swaps     |
| **Real Assets**    | Real estate tokens, infrastructure    |
| **Alternatives**   | Private equity, hedge fund units      |
| **Synthetic**      | Indices, baskets, virtual portfolios  |

The only requirement is that the asset can be represented as a **quantity held in a wallet**. The framework doesn't care what the asset "is"—it only tracks balances and enforces conservation.

---

## 2. Core Philosophy

### 2.1 Fundamental Principles

The framework is built on principles from double-entry accounting and functional programming:

| Principle                 | Meaning                                                             |
|---------------------------|---------------------------------------------------------------------|
| **Ownership = Balance**   | If you own 100 shares, your wallet balance is 100. No separate records.|
| **All Changes are Moves** | Every balance change transfers value from one wallet to another.    |
| **Conservation Law**      | Total quantity of any asset across all wallets is constant.         |
| **Atomicity**             | Related changes happen together or not at all.                      |
| **Determinism**           | Given the same inputs, execution produces identical results.        |
| **Immutability**          | Unit states are immutable; updates create new versions.             |
| **Pure Functions**        | Business logic never mutates state directly.                        |

### 2.2 Quantities Over Values

**The Ledger stores QUANTITIES, not VALUES.**

```
Ledger State:    wallet → unit → quantity    (immutable facts)
Valuation:       unit → price                (external, time-varying)
NPV:             Σ(quantity × price)         (computed externally, never stored)
```

The ledger answers: "Who owns what, when?"
The ledger does NOT answer: "What is this worth?"

Valuation, pricing models, and risk metrics are **external concerns**. The ledger provides the quantities; external systems provide the prices.

### 2.3 Pure Functions + Stateful Ledger

All business logic is implemented as pure functions:
- Take `LedgerView` (read-only interface)
- Return `ContractResult` (immutable moves + state updates)
- Never mutate ledger state directly

Only the `Ledger` class mutates state by applying `ContractResult` atomically.

This separation enables:
- **Easy testing**: Pure functions are trivial to test
- **Composability**: Results can be combined and analyzed
- **Reproducibility**: Same inputs always produce same outputs
- **Simulation**: Compute what would happen without doing it

---

## 3. Foundational Concepts

### 3.1 The Closed System

The ledger is a **closed system**. Value cannot appear from nowhere or disappear into nothing. Every increase in one wallet is matched by a decrease in another.

```
Before:  Alice has 100 USD,  Bob has 0 USD      Total: 100 USD
Trade:   Alice sends 30 USD to Bob
After:   Alice has 70 USD,   Bob has 30 USD     Total: 100 USD
```

This principle extends to everything:

- **Buying stock**: Your cash decreases, your stock increases. The market's cash increases, market's stock decreases.
- **Receiving dividends**: Issuer's cash decreases, your cash increases.
- **Option exercise**: Complex multi-leg exchange, but totals still balance.

### 3.2 Wallets

A **Wallet** is an account that holds quantities of various assets. Each wallet has a unique identifier.

```
Wallet "alice":
  USD:   50,000
  AAPL:  100
  GOLD:  10      # Ounces of gold
  BTC:   2.5     # Bitcoin

Wallet "bob":
  USD:   30,000
  EUR:   10,000
  OIL:   1000    # Barrels of crude oil
```

There are two categories of wallets:

**Real Wallets**: Represent your actual portfolio. Changes affect your P&L.

**Virtual Wallets**: Represent external counterparties (brokers, exchanges, issuers). Needed to maintain the closed system. You don't own these; they're bookkeeping entries.

**System Wallet**: A special reserved wallet (`"system"`) for:
- Issuance/redemption of units (tokens enter/exit circulation)
- DeferredCash creation (obligation enters existence)
- Extinguishing obligations (obligation satisfied)

The system wallet is exempt from balance validation and represents "outside the system."

### 3.3 Units

A **Unit** is a type of asset that can be held in wallets. Each unit has properties:

```python
@dataclass
class Unit:
    symbol: str              # Short identifier (e.g., "AAPL", "USD")
    name: str                # Human-readable name
    unit_type: str           # Category (STOCK, CASH, OPTION, etc.)
    decimal_places: int      # Precision for balances
    min_balance: float       # Negative = shorting allowed
    max_balance: float       # Maximum position size
    transfer_rule: Optional[TransferRule]  # Validation function
    _state: Optional[UnitState]  # Internal state dictionary
```

### 3.4 Moves

A **Move** is an atomic transfer of value from one wallet to another.

```python
@dataclass(frozen=True)
class Move:
    source: str       # Wallet losing value
    dest: str         # Wallet gaining value
    unit: str         # What is being transferred
    quantity: float   # How much (always positive)
    contract_id: str  # What generated this move
    metadata: Optional[Dict] = None  # Additional context
```

Every change to a wallet balance is represented as a Move. There are no other mechanisms for changing balances. This is fundamental to auditability.

---

## 4. Architecture Overview

### 4.1 Layered Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEMS                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │  Pricing Engine │  │  Risk Engine    │  │  Market Data Service    │ │
│  │  (Black-Scholes,│  │  (VaR, Greeks,  │  │  (Prices, Rates,       │ │
│  │   Models, etc.) │  │   Scenarios)    │  │   Volatilities)        │ │
│  └────────┬────────┘  └────────┬────────┘  └───────────┬─────────────┘ │
│           │                    │                       │               │
│           │ Prices             │ Risk Queries          │ Market Data   │
│           ▼                    ▼                       ▼               │
├─────────────────────────────────────────────────────────────────────────┤
│                           VALUATION LAYER                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Unit-specific compute_npv() methods:                            │   │
│  │    - Bonds: clean/dirty price, accrued interest                 │   │
│  │    - Options: model price from external pricer                   │   │
│  │    - Futures: virtual ledger position value                       │   │
│  │    - Convertibles: bond floor + conversion value                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                       │
│                                 │ Quantities + Term Sheets              │
│                                 ▼                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                              LEDGER                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  • Wallet balances (quantities only)                            │   │
│  │  • Atomic moves between wallets                                  │   │
│  │  • Conservation laws                                             │   │
│  │  • Audit trail and transaction log                               │   │
│  │  • LifecycleEngine for automated events                         │   │
│  │  • Unit-specific transact() methods for cash flows              │   │
│  │  • Time travel via clone_at()                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Data Flow

1. **External systems** provide market data, prices, and risk metrics
2. **Valuation layer** computes NPVs using quantities from ledger + external prices
3. **Ledger** maintains the golden source of ownership records
4. **Smart contracts** read ledger state via `LedgerView` and return `ContractResult`
5. **Lifecycle engine** orchestrates contract execution and state updates

---

## 5. Key Data Structures

### 5.1 Move

The atomic unit of balance transfer:

```python
@dataclass(frozen=True, slots=True)
class Move:
    source: str       # Source wallet
    dest: str         # Destination wallet
    unit: str         # Unit symbol
    quantity: float   # Amount to transfer (positive)
    contract_id: str  # Reference for audit trail
    metadata: Optional[Dict] = None
```

Moves are:
- **Immutable**: Cannot be changed after creation
- **Validated**: Source ≠ dest, quantity is finite and non-zero
- **Auditable**: contract_id tracks what generated the move

### 5.2 ContractResult

The output from smart contract execution:

```python
@dataclass(frozen=True)
class ContractResult:
    moves: Tuple[Move, ...] = ()
    state_updates: StateUpdates = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Return True if no moves and no state updates."""
        return not self.moves and not self.state_updates
```

This separation allows:
- **Simulation**: Compute what would happen without executing
- **Validation**: Check if the result is valid before execution
- **Composition**: Combine results from multiple contracts
- **Testing**: Verify contract logic without a real ledger

### 5.3 Transaction

An atomic, timestamped batch of changes:

```python
@dataclass(frozen=True, slots=True)
class Transaction:
    moves: Tuple[Move, ...]              # Balance changes
    tx_id: str                           # Unique identifier
    timestamp: datetime                  # When created
    ledger_name: str                     # Ledger this belongs to
    state_deltas: Tuple[StateDelta, ...] # Unit state changes
    contract_ids: FrozenSet[str]         # What generated this
    execution_time: Optional[datetime]   # When applied
```

Transactions provide:
- **Atomicity**: All moves apply together or none do
- **Idempotency**: Same tx_id cannot be applied twice
- **Auditability**: Complete record of what changed and why
- **Time travel**: execution_time enables state reconstruction

### 5.4 StateDelta

Records complete before/after state for unit state changes:

```python
@dataclass(frozen=True)
class StateDelta:
    unit: str      # Which unit's state changed
    old_state: Any # Complete state before (immutable)
    new_state: Any # Complete state after (immutable)
```

Since unit states are immutable, a StateDelta simply records the before and after objects. This makes state reconstruction trivial:
- **Forward**: Apply new_state
- **Backward**: Apply old_state

### 5.5 LedgerView

Read-only interface for pure functions:

```python
class LedgerView(Protocol):
    @property
    def current_time(self) -> datetime: ...

    def get_balance(self, wallet: str, unit: str) -> float: ...
    def get_unit_state(self, unit: str) -> UnitState: ...
    def get_positions(self, unit: str) -> Positions: ...
    def list_wallets(self) -> Set[str]: ...
```

Smart contracts receive `LedgerView`, not `Ledger`, ensuring they cannot mutate state directly. This is a type-level guarantee enforced by static type checkers.

### 5.6 Unit

Definition of a tradeable asset type:

```python
@dataclass
class Unit:
    symbol: str              # Identifier (e.g., "AAPL")
    name: str                # Full name
    unit_type: str           # Category
    min_balance: float       # Minimum allowed balance
    max_balance: float       # Maximum allowed balance
    decimal_places: int      # Rounding precision
    transfer_rule: Optional[TransferRule]  # Validation
    _state: Optional[UnitState]  # Internal state dict
```

The `_state` field holds unit-specific data like term sheets and lifecycle information. Unlike other core structures, Unit is mutable because `_state` updates during contract execution.

---

## 6. The Transaction Model

### 6.1 Why Transactions Exist

**Atomicity: All-or-Nothing Execution**

A stock purchase involves two legs that MUST happen together:

```python
# BAD: Individual moves
ledger.move(alice, bob, USD, 15000)   # Applied
ledger.move(bob, alice, AAPL, 100)    # Failed (Bob has no shares)
# Result: Alice lost $15,000, got nothing

# GOOD: Atomic transaction
Transaction([
    Move(alice, bob, "USD", 15000, "trade"),
    Move(bob, alice, "AAPL", 100, "trade"),
])
# Either BOTH apply, or NEITHER applies
```

**NET Validation: Aggregate Position Check**

Transactions are validated by their **net effect** on each wallet, not move-by-move:

```python
# Alice has 0 AAPL, wants to borrow and sell in one transaction

Transaction([
    Move(lender, alice, "AAPL", 100, "borrow"),  # Borrow: Alice receives 100
    Move(alice, buyer, "AAPL", 50, "sell"),      # Sell: Alice sends 50
])

# Move-by-move validation would fail:
#   Move 2 fails because Alice has 0 when it's checked

# NET validation succeeds:
#   Alice's net change: +100 - 50 = +50 AAPL
#   Final position: 50 AAPL ≥ 0 minimum → Valid
```

**Idempotency: No Double Execution**

Each transaction has a unique `tx_id` generated via deterministic hashing. The ledger tracks which IDs have been applied:

```python
result1 = ledger.execute(tx)  # → APPLIED
result2 = ledger.execute(tx)  # → ALREADY_APPLIED (same tx_id)
```

### 6.2 Transaction Lifecycle

```
1. CREATION
   Smart contract or user creates Transaction
   with moves and state_deltas
                ↓
2. VALIDATION
   - tx_id not already applied?
   - All wallets exist?
   - All units exist?
   - Transfer rules satisfied?
   - NET positions within min/max constraints?
                ↓
    ┌───────────┴──────────┐
    ↓                      ↓
3a. EXECUTION          3b. REJECTION
    - Apply all moves      - No changes made
    - Replace unit states  - Return reason
    - Log transaction
    - Mark tx_id seen
    - Return APPLIED       - Return REJECTED
```

### 6.3 State Deltas with Immutable States

Since unit states are immutable, reversing state changes is trivial:

```python
# Transaction with state change
Transaction(
    tx_id="settle_option",
    moves=[...],
    state_deltas=[
        StateDelta(
            unit="OPT_123",
            old_state=OptionState(..., settled=False),
            new_state=OptionState(..., settled=True),
        ),
    ],
)

# Replay backward: replace new_state with old_state
unit._state = state_delta.old_state

# Replay forward: replace old_state with new_state
unit._state = state_delta.new_state
```

No field-by-field mutation tracking needed.

---

## 7. The Ledger

### 7.1 Core State

The Ledger maintains:

```python
class Ledger:
    name: str                           # Ledger identifier
    current_time: datetime              # Logical clock

    # Core state
    wallets: Set[str]                   # Registered wallet IDs
    units: Dict[str, Unit]              # Registered units
    balances: Dict[str, Dict[str, float]]  # wallet → unit → quantity

    # Audit trail
    transaction_log: List[Transaction]  # All executed transactions
    seen_tx_ids: Set[str]               # For idempotency

    # Configuration
    verbose: bool                       # Print debug output
    fast_mode: bool                     # Skip validation
    no_log: bool                        # Skip transaction logging
```

### 7.2 Key Operations

**Registration**

Before use, wallets and units must be registered:

```python
ledger.register_wallet("alice")
ledger.register_unit(Unit(
    symbol="USD",
    name="US Dollar",
    unit_type="CASH",
    decimal_places=2,
    _state={'issuer': 'FED'},
))
```

**Execution**

Execute a transaction or contract result:

```python
# Execute transaction
tx = Transaction(...)
result = ledger.execute(tx)  # Returns ExecuteResult enum

# Execute contract result
contract_result = some_contract.check_lifecycle(...)
ledger.execute_contract(contract_result)
```

**Time Advancement**

The ledger has a logical clock that must be advanced explicitly:

```python
ledger.advance_time(datetime(2025, 6, 16, 9, 30))
```

Time can only move forward, never backward.

**State Queries**

```python
balance = ledger.get_balance("alice", "USD")
state = ledger.get_unit_state("OPT_123")
positions = ledger.get_positions("AAPL")  # All wallets holding AAPL
```

### 7.3 The UNWIND Algorithm (Time Travel)

The ledger can reconstruct its state at any past time using the **UNWIND algorithm**:

```python
past_ledger = ledger.clone_at(target_time)
```

**Why UNWIND, Not REPLAY?**

Replay (start from zero, apply transactions up to T) fails because initial balances set via `set_balance()` are not logged as transactions.

UNWIND starts from current state and works backwards:

```python
def clone_at(target_time):
    # 1. Start with current state (includes all setup and transactions)
    cloned = self.clone()

    # 2. Walk backwards through transactions after target_time
    for tx in reversed(transaction_log):
        if tx.execution_time <= target_time:
            break

        # 3. Reverse each move
        for move in tx.moves:
            cloned.balances[move.source][move.unit] += move.quantity
            cloned.balances[move.dest][move.unit] -= move.quantity

        # 4. Restore old_state from StateDelta
        for delta in tx.state_deltas:
            cloned.units[delta.unit]._state = delta.old_state

    return cloned
```

This works because:
- Current state includes all `set_balance()` effects
- We only undo documented changes (transactions)
- StateDelta.old_state contains the exact prior state

### 7.4 Cloning for Monte Carlo

Create an independent copy of the ledger:

```python
ledger_copy = ledger.clone()
```

The clone has:
- Same wallets, units, balances, unit states
- Same transaction log (if no_log=False)
- **Independent state**: changes to clone don't affect original

This is essential for Monte Carlo simulation where each path needs its own ledger.

### 7.5 Performance Modes

| Mode               | Validation | Logging | Use Case                         |
|--------------------|------------|---------|----------------------------------|
| Standard           | Yes        | Yes     | Production, debugging            |
| fast_mode          | No         | Yes     | Trusted simulations              |
| no_log             | Yes        | No      | Memory-constrained               |
| fast_mode + no_log | No         | No      | Maximum throughput (Monte Carlo) |

```python
# Record keeping (safe, auditable)
ledger = Ledger("main", fast_mode=False, no_log=False)

# Maximum speed (Monte Carlo with millions of transactions)
ledger = Ledger("sim", fast_mode=True, no_log=True)
```

---

## 8. Smart Contracts

### 8.1 What is a Smart Contract?

A **Smart Contract** is a deterministic program that computes balance and state changes based on current conditions.

```
Smart Contract: (Ledger State, Time, Prices, Params) → ContractResult
```

Key properties:
- **Pure function**: No side effects. Same inputs → same outputs.
- **Reads ledger**: Examines balances, unit states, time via LedgerView
- **Returns result**: ContractResult with moves and state_updates
- **Does not execute**: The ledger executes the result

### 8.2 Contract Interface

```python
class SmartContract(Protocol):
    def check_lifecycle(
        self,
        view: LedgerView,
        symbol: str,
        timestamp: datetime,
        prices: Dict[str, float]
    ) -> ContractResult:
        """
        Check if any lifecycle events should fire.

        Returns ContractResult with moves and state_updates.
        Returns empty ContractResult if no events.
        """
        ...
```

### 8.3 Example: Stock with Dividends

Stocks have lifecycle events too. A stock that pays dividends has a **dividend schedule** in its state:

```python
# Stock state
{
    'issuer': 'AAPL',
    'issuer_wallet': 'treasury',
    'dividend_currency': 'USD',
    'dividend_schedule': [
        (datetime(2025, 2, 13), 0.25),  # (payment_date, amount_per_share)
        (datetime(2025, 5, 15), 0.25),
        (datetime(2025, 8, 14), 0.25),
        (datetime(2025, 11, 13), 0.25),
    ],
    'dividends_paid': []  # Tracks which have been paid
}
```

The stock contract checks if any dividends are due:

```python
def check_lifecycle(view, symbol, timestamp, prices):
    state = view.get_unit_state(symbol)
    moves = []
    new_dividends_paid = list(state['dividends_paid'])

    for payment_date, div_per_share in state['dividend_schedule']:
        # Skip if already paid
        if payment_date in state['dividends_paid']:
            continue

        # Skip if not yet payment date
        if timestamp < payment_date:
            continue

        # Pay dividend to all holders
        positions = view.get_positions(symbol)
        for wallet, shares in positions.items():
            if shares > 0 and wallet != state['issuer_wallet']:
                amount = shares * div_per_share
                moves.append(Move(
                    source=state['issuer_wallet'],
                    dest=wallet,
                    unit=state['dividend_currency'],
                    quantity=amount,
                    contract_id=f"div_{symbol}_{payment_date.date()}",
                ))

        new_dividends_paid.append(payment_date)

    if not moves:
        return ContractResult()  # No dividends due

    return ContractResult(
        moves=tuple(moves),
        state_updates={symbol: {
            **state,
            'dividends_paid': new_dividends_paid,
        }}
    )
```

### 8.4 Example: European Call Option

```python
def check_lifecycle(view, symbol, timestamp, prices):
    state = view.get_unit_state(symbol)

    # Already settled → nothing to do
    if state.get('settled', False):
        return ContractResult()

    # Not yet matured → nothing to do
    if timestamp < state['maturity']:
        return ContractResult()

    # Time to settle
    spot = prices[state['underlying']]
    strike = state['strike']
    long_wallet = state['long_wallet']
    short_wallet = state['short_wallet']
    quantity = state['quantity']

    # Get position size
    position = view.get_balance(long_wallet, symbol)
    if position <= 0:
        return ContractResult()

    moves = []
    is_itm = spot > strike

    if is_itm:
        # Physical delivery
        total_shares = position * quantity
        total_cash = total_shares * strike

        moves.append(Move(long_wallet, short_wallet, state['currency'],
                          total_cash, f"settle_{symbol}_cash"))
        moves.append(Move(short_wallet, long_wallet, state['underlying'],
                          total_shares, f"settle_{symbol}_delivery"))

    # Close out option position
    moves.append(Move(long_wallet, short_wallet, symbol,
                      position, f"close_{symbol}"))

    return ContractResult(
        moves=tuple(moves),
        state_updates={symbol: {
            **state,
            'settled': True,
            'exercised': is_itm,
            'settlement_price': spot,
        }}
    )
```

### 8.5 The Lifecycle Engine

The **Lifecycle Engine** automates lifecycle events:

```python
class LifecycleEngine:
    def __init__(self, ledger: Ledger):
        self.ledger = ledger
        self.contracts: Dict[str, SmartContract] = {}

    def register(self, unit_type: str, contract: SmartContract):
        """Register a contract handler for a unit type."""
        self.contracts[unit_type] = contract

    def step(self, timestamp: datetime, prices: Dict[str, float]) -> List[Transaction]:
        """
        Advance to timestamp and process all lifecycle events.

        Returns list of transactions that were executed.
        """
        # 1. Advance time
        self.ledger.advance_time(timestamp)

        # 2. Check each unit (deterministic order)
        executed = []
        for symbol in sorted(self.ledger.units.keys()):
            unit = self.ledger.units[symbol]
            contract = self.contracts.get(unit.unit_type)
            if contract is None:
                continue

            # 3. Compute lifecycle events
            result = contract.check_lifecycle(
                self.ledger, symbol, timestamp, prices
            )

            # 4. Execute if non-empty
            if not result.is_empty():
                tx = self.ledger.execute_contract(result)
                executed.append(tx)

        return executed
```

---

## 9. Design Patterns

### 9.1 The Virtual Ledger Pattern (Futures)

Futures require special handling because multiple trades can occur at different prices before EOD settlement. The naive approach `Δprice × quantity` **fails** when trades occur at varying prices.

**Solution: Virtual Ledger inside unit state**

The future unit maintains internal tracking that accumulates during the day:

```python
# Future state
{
    'underlying': 'ES',
    'expiry': datetime(2025, 12, 19),
    'multiplier': 50.0,
    'settlement_currency': 'USD',
    'holder_wallet': 'trader',
    'clearinghouse_wallet': 'exchange',

    # Virtual ledger (internal to unit state)
    'virtual_quantity': 0.0,        # Net contracts held
    'virtual_cash': 0.0,            # Cumulative trade cash
    'last_settlement_price': 0.0,
    'intraday_postings': 0.0,
}
```

**Phase 1: Trade Execution (no real moves)**

Each trade updates the virtual ledger only:

```python
def execute_futures_trade(state, trade_qty, trade_price):
    """Trade updates virtual ledger only. Returns state update, NO moves."""
    new_virtual_qty = state['virtual_quantity'] + trade_qty
    new_virtual_cash = state['virtual_cash'] + (-trade_qty * trade_price * state['multiplier'])

    return ContractResult(
        moves=(),  # No real moves during trading
        state_updates={symbol: {
            **state,
            'virtual_quantity': new_virtual_qty,
            'virtual_cash': new_virtual_cash,
        }}
    )
```

**Phase 2: EOD Settlement (ONE real move)**

At end-of-day, calculate margin call from the virtual ledger:

```python
def compute_daily_settlement(view, symbol, settlement_price):
    state = view.get_unit_state(symbol)

    # Hypothetical unwind at settlement price
    unwind_value = state['virtual_quantity'] * settlement_price * state['multiplier']

    # margin_call = virtual_cash + unwind_value
    margin_call = state['virtual_cash'] + unwind_value

    # Generate ONE real move
    if margin_call > 0:
        move = Move(state['clearinghouse_wallet'], state['holder_wallet'],
                    state['settlement_currency'], margin_call, f"vm_{symbol}")
    elif margin_call < 0:
        move = Move(state['holder_wallet'], state['clearinghouse_wallet'],
                    state['settlement_currency'], abs(margin_call), f"vm_{symbol}")
    else:
        move = None  # No margin call needed

    # Reset virtual ledger for next day
    new_virtual_cash = -state['virtual_quantity'] * settlement_price * state['multiplier']

    return ContractResult(
        moves=(move,) if move else (),
        state_updates={symbol: {
            **state,
            'virtual_cash': new_virtual_cash,
            'last_settlement_price': settlement_price,
            'intraday_postings': 0.0,
        }}
    )
```

### 9.2 The DeferredCash Pattern (T+N Settlement)

Securities markets use T+2 settlement. The ledger models this explicitly using DeferredCash units.

**Trade Date (T):**
```python
# Stock moves immediately (economic ownership transfers)
Move(source="seller", dest="buyer", unit="AAPL", quantity=100)

# Create DeferredCash obligation (settles T+2)
Move(source="system", dest="buyer", unit="DC_trade_123", quantity=1)
```

The DeferredCash unit state contains:
```python
{
    'unit_type': 'DEFERRED_CASH',
    'amount': 15000.0,
    'currency': 'USD',
    'payment_date': datetime(2025, 6, 17),  # T+2
    'payer_wallet': 'buyer',
    'payee_wallet': 'seller',
    'settled': False,
}
```

**Settlement Date (T+2):**
```python
# Cash payment fires
Move(source="buyer", dest="seller", unit="USD", quantity=15000)

# Extinguish the obligation
Move(source="buyer", dest="system", unit="DC_trade_123", quantity=1)
```

### 9.3 The DeferredCash Pattern (Dividends)

**Critical:** Dividend entitlement is determined on ex-date, NOT payment date. Position changes after ex-date do NOT affect payment.

**On Ex-Date** (create entitlement):

```python
# For each holder at EOD on ex-date
dc_symbol = f"DIV_{stock_symbol}_{ex_date.date()}_{wallet}"

Move(source="system", dest=wallet, unit=dc_symbol, quantity=1)

# DeferredCash state
{
    'unit_type': 'DEFERRED_CASH',
    'amount': shares * dividend_per_share,
    'currency': 'USD',
    'payment_date': datetime(2025, 2, 13),
    'payer_wallet': 'issuer_wallet',
    'payee_wallet': wallet,
    'settled': False,
}
```

**On Payment Date** (execute payment):

```python
# Real cash move
Move(source='issuer_wallet', dest=wallet, unit='USD', quantity=amount)

# Extinguish the DeferredCash unit
Move(source=wallet, dest='system', unit=dc_symbol, quantity=1)
```

### 9.4 The transact() Protocol

Each unit type implements a `transact()` method for explicit cash flow generation:

```python
def transact(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> ContractResult:
    """
    Generate moves and state updates for a lifecycle event.

    Args:
        view: Read-only ledger access
        symbol: Unit symbol
        event_type: Type of event (COUPON, SETTLEMENT, DIVIDEND, etc.)
        event_date: When the event occurs
        **kwargs: Event-specific parameters

    Returns:
        ContractResult with moves and state_updates
    """
```

Example event types:
- Bonds: COUPON, REDEMPTION, CALL, PUT
- Options: EXERCISE, EXPIRY, ASSIGNMENT
- Stocks: DIVIDEND, SPLIT, MERGER
- Futures: DAILY_SETTLEMENT, EXPIRY, MARGIN_CALL

### 9.5 The Checkpoint-and-Verify Pattern

A key testing pattern for validating state reconstruction:

```python
# 1. Checkpoint at T0
checkpoint = ledger.clone()

# 2. Execute transactions
ledger.advance_time(t1)
ledger.execute(...)
ledger.advance_time(t2)
ledger.execute(...)

# 3. Reconstruct state at T0
reconstructed = ledger.clone_at(t0)

# 4. Verify they match
assert ledger_state_equals(reconstructed, checkpoint)
```

This validates that `clone_at()` correctly reconstructs past state.

---

## 10. Unit Types and Lifecycle

### 10.1 Cash

Simple currency units with no lifecycle events:

```python
Unit(
    symbol="USD",
    name="US Dollar",
    unit_type="CASH",
    decimal_places=2,
    min_balance=-1_000_000_000.0,  # Allow overdrafts
    _state={'issuer': 'central_bank'}
)
```

### 10.2 Stock

Equities with dividend scheduling:

```python
{
    'issuer': 'AAPL',
    'issuer_wallet': 'treasury',
    'dividend_currency': 'USD',
    'dividend_schedule': [
        (datetime(2025, 2, 13), 0.25),
        (datetime(2025, 5, 15), 0.25),
        # ... quarterly dividends
    ],
    'dividends_paid': []
}
```

Lifecycle events:
- **DIVIDEND**: Pay dividend to all holders on payment date
- **SPLIT**: Adjust quantities and state
- **MERGER**: Complex corporate action

### 10.3 Bilateral Option

Call/put options between two counterparties:

```python
{
    'underlying': 'AAPL',
    'strike': 150.0,
    'maturity': datetime(2025, 12, 19),
    'option_type': 'call',  # or 'put'
    'quantity': 100,        # Multiplier
    'currency': 'USD',
    'long_wallet': 'alice',
    'short_wallet': 'bob',
    'settled': False,
    'exercised': False,
    'settlement_price': None,
}
```

Lifecycle events:
- **SETTLEMENT**: At maturity, check ITM/OTM and execute physical delivery
- **EARLY_EXERCISE**: For American options

Transfer rule: `bilateral_transfer_rule` (only alice and bob can hold)

### 10.4 Future

Exchange-traded futures with daily settlement:

```python
{
    'underlying': 'ES',
    'expiry': datetime(2025, 12, 19),
    'multiplier': 50.0,
    'settlement_currency': 'USD',
    'holder_wallet': 'trader',
    'clearinghouse_wallet': 'exchange',
    'virtual_quantity': 15.0,
    'virtual_cash': -157500.0,
    'last_settlement_price': 105.0,
    'intraday_postings': 0.0,
}
```

Lifecycle events:
- **DAILY_SETTLEMENT**: EOD margin calculation and reset
- **INTRADAY_MARGIN**: Risk-based margin call
- **EXPIRY**: Final settlement

### 10.5 Forward

Bilateral forward contract with delivery:

```python
{
    'underlying': 'OIL',
    'forward_price': 75.0,
    'delivery_date': datetime(2025, 6, 1),
    'quantity': 1000,
    'currency': 'USD',
    'long_wallet': 'buyer',
    'short_wallet': 'seller',
    'delivered': False,
}
```

Lifecycle events:
- **DELIVERY**: At delivery date, exchange cash for underlying

---

## 11. Conservation Laws and Invariants

### 11.1 The Conservation Law

For every unit, at all times:

```
Σ(balances across all wallets) = constant
```

Every `Move` debits source and credits destination atomically. The total supply for any unit must remain constant (except for explicit issuance/redemption via the system wallet).

### 11.2 Balance Constraints

Each unit defines minimum and maximum balance:

```python
unit.min_balance  # Can be negative (allows shorting)
unit.max_balance  # Can be infinite
```

After applying the NET effect of a transaction, every wallet's balance must satisfy:

```
min_balance ≤ wallet_balance ≤ max_balance
```

### 11.3 The System Wallet Exception

The `"system"` wallet is exempt from balance validation. It represents "outside the system" where:
- Units enter circulation (issuance)
- Units exit circulation (redemption)
- Obligations come into existence (DeferredCash creation)
- Obligations are extinguished (DeferredCash settlement)

### 11.4 Transfer Rules

Units can specify additional validation logic via `transfer_rule`:

```python
def bilateral_transfer_rule(view: LedgerView, move: Move) -> None:
    """Only original counterparties can hold bilateral units."""
    state = view.get_unit_state(move.unit)
    authorized = {state['long_wallet'], state['short_wallet']}

    if move.source not in authorized or move.dest not in authorized:
        raise TransferRuleViolation(
            f"Bilateral {move.unit}: unauthorized party"
        )
```

### 11.5 Deterministic Execution

Same inputs always produce same outputs:
- Deterministic iteration (sorted order)
- Deterministic transaction IDs (content-based hashing)
- No reliance on system time or randomness
- Pure functions for all business logic

---

## 12. State Management

### 12.1 Immutable Unit States

Unit states are stored as dictionaries but should be treated as immutable. When state changes:

```python
# Old state
old_state = view.get_unit_state(symbol)

# Compute new state (create new dict, don't modify old)
new_state = {**old_state, 'settled': True, 'exercised': True}

# Return state update
return ContractResult(
    moves=...,
    state_updates={symbol: new_state}
)
```

Why immutable states:
- **Pure functions**: Easy to test and reason about
- **Clean replay**: Trivial to reverse state changes
- **Thread safety**: Can be shared across threads
- **Debugging**: Inspect any historical state

### 12.2 State Reconstruction

The UNWIND algorithm reconstructs state at any past time:

1. Start with current state (includes all effects)
2. Walk backward through transactions after target time
3. Reverse each move
4. Restore old_state from StateDelta

```python
past_ledger = ledger.clone_at(target_time)
```

This enables:
- P&L calculation (compare two points in time)
- Analysis (examine state at any historical moment)
- Verification (compare reconstructed to known-good checkpoint)

### 12.3 Snapshot

A **Snapshot** captures complete ledger state at a point in time:

```python
@dataclass
class Snapshot:
    timestamp: datetime
    balances: Dict[str, Dict[str, float]]  # wallet → unit → quantity
    unit_states: Dict[str, Any]            # unit → state
```

Snapshots are used for:
- P&L calculation
- Analysis
- Checkpointing
- Verification

### 12.4 State Comparison

Compare two ledger states:

```python
def ledger_state_equals(
    a: Ledger,
    b: Ledger,
    tolerance: float = 1e-9,
    compare_time: bool = False
) -> bool:
    """
    Return True if ledgers have identical state.

    Compares:
    - Registered wallets (must be identical sets)
    - All balances (within tolerance)
    - All unit states (exact equality)
    - Optionally: current_time
    """
```

For debugging, get detailed differences:

```python
diff = compare_ledger_states(ledger_a, ledger_b)
# Returns dict with:
# - balance_diffs: List of (wallet, unit, value_a, value_b)
# - state_diffs: List of (unit, state_a, state_b)
# - missing_wallets_a/b
# - missing_units_a/b
```

---

## 13. Code Organization

### 13.1 Directory Structure

```
ledger/
├── core.py              # Types, protocols, base classes
├── ledger.py            # Main Ledger class
├── lifecycle.py         # LifecycleEngine
├── pricing.py           # PricingSource implementations
├── analysis.py          # P&L, risk metrics
├── verification.py      # State comparison utilities
├── black_scholes.py     # [UTILITY - External to ledger]
│
├── units/
│   ├── __init__.py      # Re-exports all unit factories
│   ├── cash.py          # Simple cash
│   ├── stock.py         # Equity with dividends
│   ├── option.py        # Vanilla options (bilateral)
│   ├── forward.py       # Forward contracts (bilateral)
│   ├── future.py        # Exchange-traded futures
│   └── bond.py          # Fixed income
│
└── strategies/
    ├── delta_hedge.py   # Delta hedging strategy
    └── ...              # Other strategies
```

### 13.2 Principle: One Unit = One File

Each instrument type lives in its own file because:
- Future instruments will each have hundreds of lines
- Each has unique state requirements and lifecycle events
- Isolation prevents bugs in one instrument from affecting others
- New developers can understand one instrument at a time
- Adding instruments means adding files, not modifying existing code

### 13.3 Adding a New Instrument

The pattern (see `options.py` as example):

1. **`create_X_unit()`** - Factory function with all term sheet params in `_state`
2. **`compute_X_settlement()`** - Pure function returning `ContractResult`
3. **`X_contract`** - Object implementing SmartContract protocol

Example:

```python
# 1. Factory
def create_option_unit(
    symbol: str,
    name: str,
    underlying: str,
    strike: float,
    maturity: datetime,
    option_type: str,
    quantity: float,
    currency: str,
    long_wallet: str,
    short_wallet: str
) -> Unit:
    return Unit(
        symbol=symbol,
        name=name,
        unit_type="BILATERAL_OPTION",
        transfer_rule=bilateral_transfer_rule,
        _state={
            'underlying': underlying,
            'strike': strike,
            'maturity': maturity,
            'option_type': option_type,
            'quantity': quantity,
            'currency': currency,
            'long_wallet': long_wallet,
            'short_wallet': short_wallet,
            'settled': False,
        }
    )

# 2. Pure function
def compute_option_settlement(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> ContractResult:
    state = view.get_unit_state(symbol)
    # ... logic ...
    return ContractResult(moves=..., state_updates=...)

# 3. Contract object
class OptionContract:
    def check_lifecycle(self, view, symbol, timestamp, prices):
        return compute_option_settlement(view, symbol, timestamp, prices)

option_contract = OptionContract()
```

### 13.4 Thread Safety

The Ledger is **NOT thread-safe**. For parallel Monte Carlo:
- Clone the ledger for each path
- Run each simulation in a separate process (not thread)
- Use `ProcessPoolExecutor`, not `ThreadPoolExecutor`

### 13.5 Testing Strategy

The test suite validates:
- UNWIND algorithm correctness via checkpoint-and-verify
- Deterministic execution across clones
- State delta immutability
- Transaction replay with state changes
- Lifecycle engine integration
- Conservation laws maintained

Test files mirror source structure:
- `test_ledger.py`: Core ledger operations
- `test_engine.py`: LifecycleEngine
- `test_options.py`: Option settlement
- `test_stocks.py`: Dividend processing
- `test_reproducibility.py`: Time-travel and determinism

---

## Summary

The Ledger provides a solid foundation for financial simulation and portfolio management. The architecture cleanly separates:

- **Quantities** (ledger's domain) from **values** (external)
- **Business logic** (pure functions) from **state mutation** (Ledger class)
- **Instruments** (one file each) from **core infrastructure**

Key design patterns:
- **Virtual Ledger**: Internal state tracking for complex instruments (futures)
- **DeferredCash**: Explicit modeling of settlement obligations
- **UNWIND**: Backward state reconstruction from transaction log
- **Pure Functions**: All contracts return ContractResult, never mutate
- **Immutable States**: Simple, correct state management

The system serves both production record-keeping and high-throughput simulation with identical business logic, differing only in performance configuration.

---

*This is a living document. As new patterns emerge and the system evolves, this design document should be updated to reflect current best practices.*
