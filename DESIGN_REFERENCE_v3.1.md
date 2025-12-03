# Ledger Framework: Reference Design Document

**Version**: 3.1  
**Purpose**: Complete specification for a closed ledger system supporting financial record keeping and simulations  
**Audience**: Developers implementing or using this framework  

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Foundational Concepts](#2-foundational-concepts)
3. [Core Data Structures](#3-core-data-structures)
4. [The Transaction](#4-the-transaction)
5. [The Ledger](#5-the-ledger)
6. [Smart Contracts](#6-smart-contracts)
7. [The Lifecycle Engine](#7-the-lifecycle-engine)
8. [Pricing Sources](#8-pricing-sources)
9. [Monte Carlo Simulation Architecture](#9-monte-carlo-simulation-architecture)
10. [Analysis and Metrics](#10-analysis-and-metrics)
11. [State Verification and Ledger Equality](#11-state-verification-and-ledger-equality)
12. [Implementation Guidelines](#12-implementation-guidelines)
13. [Summary](#13-summary)

---

## 1. Introduction

### 1.1 What This Framework Does

This framework implements a **closed ledger system** that serves two complementary purposes:

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

The same core architecture serves both purposes. The difference lies in configuration:
- Record keeping: `verbose=True`, `fast_mode=False`, `no_log=False` (full validation and audit)
- Simulation: `verbose=False`, `fast_mode=True`, `no_log=True` (maximum throughput)

### 1.2 Asset Class Agnostic

The framework is **not limited to equities**. It can represent any asset that can be owned and transferred:

| Asset Class | Examples |
|-------------|----------|
| **Equities** | Stocks, ETFs, ADRs |
| **Fixed Income** | Bonds, notes, bills, loans |
| **Currencies** | USD, EUR, GBP, JPY, cryptocurrencies |
| **Commodities** | Gold, oil, wheat, natural gas |
| **Derivatives** | Options, futures, forwards, swaps |
| **Real Assets** | Real estate tokens, infrastructure |
| **Alternatives** | Private equity, hedge fund units |
| **Synthetic** | Indices, baskets, virtual portfolios |

The only requirement is that the asset can be represented as a **quantity held in a wallet**. The framework doesn't care what the asset "is"—it only tracks balances and enforces conservation.

### 1.3 Primary Use Cases

**Monte Carlo Simulation**

A portfolio manager holds stocks, options, and hedging strategies. To understand the distribution of possible outcomes, they:

1. Generate 1,000 simulated price paths for each asset
2. For each path, simulate the portfolio from today to some horizon
3. Collect 1,000 final portfolio values
4. Analyze the distribution: expected return, VaR, maximum drawdown

**Backtesting**

A trader wants to test a delta-hedging strategy on historical data:

1. Load historical prices as a PricingSource
2. Set up the portfolio with initial positions
3. Run the simulation, letting the strategy rebalance automatically
4. Compute P&L attribution: how much came from the option vs. the hedge

**Record Keeping**

A fund administrator maintains the official books:

1. Record all trades as transactions
2. Process corporate actions (dividends, splits) via smart contracts
3. Generate daily NAV reports
4. Provide audit trail for regulators

**Reinforcement Learning**

An AI agent learns to trade:

1. The ledger acts as the environment
2. Agent observes portfolio state
3. Agent takes actions (trades)
4. Environment steps forward, lifecycle events fire
5. Agent receives reward (P&L)

### 1.4 Design Philosophy

The framework is built on principles from double-entry accounting:

| Principle | Meaning |
|-----------|---------|
| **Ownership = Balance** | If you own 100 shares, your wallet balance is 100. No separate records. |
| **All Changes are Moves** | Every balance change transfers value from one wallet to another. |
| **Conservation Law** | Total quantity of any asset across all wallets is constant. |
| **Atomicity** | Related changes happen together or not at all. |
| **Determinism** | Given the same inputs, execution produces identical results. |
| **Immutability** | Unit states are immutable; updates create new versions. |

---

## 2. Foundational Concepts

### 2.1 The Closed System

The ledger is a **closed system**. Value cannot appear from nowhere or disappear into nothing. Every increase in one wallet is matched by a decrease in another.

```
Before:  Alice has 100 USD,  Bob has 0 USD      Total: 100 USD
Trade:   Alice sends 30 USD to Bob
After:   Alice has 70 USD,   Bob has 30 USD     Total: 100 USD
```

This seems obvious for simple transfers, but the principle extends to everything:

- **Buying stock**: Your cash decreases, your stock increases. The market's cash increases, market's stock decreases.
- **Receiving dividends**: Issuer's cash decreases, your cash increases.
- **Commodity delivery**: Warehouse's inventory decreases, buyer's inventory increases.
- **Option exercise**: Complex multi-leg exchange, but totals still balance.

### 2.2 Wallets

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

**Virtual Wallets**: Represent external counterparties (brokers, exchanges, issuers, warehouses). Needed to maintain the closed system. You don't own these; they're bookkeeping entries.

```
When you buy 100 barrels of oil from a commodity dealer:

  Move: your_wallet → dealer_wallet : 8,000 USD
  Move: dealer_wallet → your_wallet : 100 OIL
  
The dealer_wallet is virtual. It receives your cash and delivers oil.
Conservation is maintained. Every move has a source and destination.
```

### 2.3 Units

A **Unit** is a type of asset that can be held in wallets. Examples:

- Currencies: USD, EUR, BTC
- Equities: AAPL, GOOG
- Commodities: GOLD, OIL, WHEAT
- Bonds: US_TREASURY_10Y
- Derivatives: AAPL_CALL_150_DEC25

Each unit has properties:

```
Unit:
  symbol:         "AAPL"
  name:           "Apple Inc."
  unit_type:      "STOCK"
  decimal_places: 6              # Precision for balances
  min_balance:    -1,000,000     # Negative = shorting allowed
  max_balance:    +∞
  transfer_rule:  None           # Or: bilateral, whitelist, etc.
  state:          UnitState      # Immutable lifecycle state
```

### 2.4 Immutable Unit State

The `state` field holds lifecycle information and is **immutable**. When state changes, a new state object replaces the old one entirely.

```python
# State is a frozen (immutable) dataclass
@dataclass(frozen=True)
class StockState:
    issuer: str
    dividend_schedule: Tuple[DividendEvent, ...]  # Immutable tuple
    last_dividend_paid: Optional[datetime]
    
@dataclass(frozen=True)
class OptionState:
    underlying: str
    strike: float
    maturity: datetime
    option_type: str  # "call" or "put"
    long_wallet: str
    short_wallet: str
    settled: bool
    exercised: bool
    settlement_price: Optional[float]
```

**Why Immutable State?**

1. **Pure Functions**: State update functions take old state and return new state. No mutation.
   ```python
   def settle_option(old_state: OptionState, price: float) -> OptionState:
       # Pure function - no side effects
       return OptionState(
           underlying=old_state.underlying,
           strike=old_state.strike,
           maturity=old_state.maturity,
           option_type=old_state.option_type,
           long_wallet=old_state.long_wallet,
           short_wallet=old_state.short_wallet,
           settled=True,                    # Changed
           exercised=price > old_state.strike,  # Changed
           settlement_price=price,          # Changed
       )
   ```

2. **Easy Testing**: Pure functions are trivial to test.
   ```python
   def test_settle_option_itm():
       old = OptionState(..., settled=False, exercised=False)
       new = settle_option(old, price=175.0)  # Strike is 150
       assert new.settled == True
       assert new.exercised == True
       assert new.settlement_price == 175.0
   ```

3. **Clean Replay**: Backward replay replaces current state with previous state. No partial mutations to undo.
   ```python
   # Transaction stores both old and new state
   state_delta = StateDelta(
       unit="OPT_123",
       old_state=old_state,   # Complete immutable object
       new_state=new_state,   # Complete immutable object
   )
   
   # Replay backward: simply restore old_state
   unit.state = state_delta.old_state
   ```

4. **Thread Safety**: Immutable objects can be shared across threads without locks.

5. **Debugging**: You can inspect any historical state without worrying about mutations.

### 2.5 Moves

A **Move** is an atomic transfer of value from one wallet to another.

```
Move:
  source:      "alice"           # Wallet losing value
  dest:        "bob"             # Wallet gaining value
  unit:        "USD"             # What is being transferred
  quantity:    1000.0            # How much (always positive)
  contract_id: "payment_001"     # What generated this move
  metadata:    {reason: "..."}   # Additional context
```

Every change to a wallet balance is represented as a Move. There are no other mechanisms for changing balances. This is fundamental to auditability.

---

## 3. Core Data Structures

### 3.1 StateDelta

When a unit's state changes, we record both the complete old state and the complete new state. Since states are immutable, this is a simple replacement.

```python
@dataclass(frozen=True)
class StateDelta:
    unit: str
    old_state: Any  # Complete immutable state object
    new_state: Any  # Complete immutable state object
```

Example for option settlement:

```python
state_delta = StateDelta(
    unit="OPT_AAPL_150",
    old_state=OptionState(
        underlying="AAPL",
        strike=150.0,
        maturity=datetime(2025, 12, 19),
        option_type="call",
        long_wallet="alice",
        short_wallet="bob",
        settled=False,
        exercised=False,
        settlement_price=None,
    ),
    new_state=OptionState(
        underlying="AAPL",
        strike=150.0,
        maturity=datetime(2025, 12, 19),
        option_type="call",
        long_wallet="alice",
        short_wallet="bob",
        settled=True,
        exercised=True,
        settlement_price=175.0,
    ),
)
```

### 3.2 ContractResult

Smart contracts compute what should happen but don't execute it directly. They return a **ContractResult**:

```
ContractResult:
  moves:        [Move, Move, ...]      # Balance changes
  state_deltas: [StateDelta, ...]      # Unit state replacements
```

This separation allows:
- **Simulation**: Compute what would happen without doing it
- **Validation**: Check if the result is valid before execution
- **Composition**: Combine results from multiple contracts
- **Testing**: Verify contract logic without a real ledger

### 3.3 Snapshot

A **Snapshot** captures the complete state of the ledger at a point in time:

```
Snapshot:
  timestamp:    2025-06-15 10:30:00
  balances:     {wallet → {unit → quantity}}
  unit_states:  {unit → immutable_state_object}
```

Snapshots are used for:
- P&L calculation (compare two points in time)
- Analysis (examine state at any historical moment)
- Checkpointing (save/restore simulation state)
- Verification (compare reconstructed state to known-good state)

---

## 4. The Transaction

### 4.1 Definition

A **Transaction** is an atomic, timestamped batch of changes that either ALL succeed or ALL fail together.

```
Transaction:
  tx_id:        "abc123"                    # Unique identifier
  timestamp:    2025-06-15 10:30:00         # When created
  moves:        [Move, Move, ...]           # Balance changes
  state_deltas: [StateDelta, ...]           # Unit state replacements
  source:       "european_option.settle"    # What generated this
  metadata:     {reason: "ITM exercise"}    # Context
```

### 4.2 Why Transactions Exist

**Atomicity: All-or-Nothing Execution**

A stock purchase involves two legs:
1. Buyer sends cash to seller
2. Seller sends shares to buyer

These MUST happen together. If only one executes, someone loses value.

```
# BAD: Individual moves
ledger.move(alice, bob, USD, 15000)   ✓ Applied
ledger.move(bob, alice, AAPL, 100)    ✗ Failed (Bob has no shares)
# Result: Alice lost $15,000, got nothing

# GOOD: Atomic transaction
Transaction([
  Move(alice → bob, 15000 USD),
  Move(bob → alice, 100 AAPL),
])
# Either BOTH apply, or NEITHER applies
```

**NET Validation: Aggregate Position Check**

Transactions are validated by their **net effect** on each wallet, not move-by-move. This enables complex operations:

```
# Alice has 0 AAPL, wants to borrow and sell in one transaction

Transaction([
  Move(lender → alice, 100 AAPL),   # Borrow: Alice receives 100
  Move(alice → buyer, 50 AAPL),     # Sell: Alice sends 50
])

# Move-by-move validation would fail:
#   Move 2 fails because Alice has 0 when it's checked

# NET validation succeeds:
#   Alice's net change: +100 - 50 = +50 AAPL
#   Final position: 50 AAPL ≥ 0 minimum → Valid
```

**Idempotency: No Double Execution**

Each transaction has a unique `tx_id`. The ledger tracks which IDs have been applied:

```
result1 = ledger.execute(tx)  # → APPLIED
result2 = ledger.execute(tx)  # → ALREADY_APPLIED (same tx_id)
```

This prevents accidental double-spending and enables safe retries.

**Ordering: Establishes Timeline**

Transactions have timestamps that establish the order of events. This is essential for:
- Determining what state existed at any past time
- Knowing which lifecycle events have fired
- Creating audit trails

### 4.3 Transaction Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│  1. CREATION                                                 │
│     Smart contract or user creates Transaction               │
│     with moves and state_deltas                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. VALIDATION                                               │
│     - tx_id not already applied?                             │
│     - All wallets exist?                                     │
│     - All units exist?                                       │
│     - Transfer rules satisfied? (bilateral, whitelist)       │
│     - NET positions within min/max constraints?              │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│  3a. EXECUTION          │   │  3b. REJECTION          │
│  - Apply all moves      │   │  - No changes made      │
│  - Replace unit states  │   │  - Return reason        │
│    (immutable swap)     │   │                         │
│  - Log transaction      │   │                         │
│  - Mark tx_id seen      │   │                         │
│  - Return APPLIED       │   │  - Return REJECTED      │
└─────────────────────────┘   └─────────────────────────┘
```

### 4.4 State Deltas with Immutable States

Since unit states are immutable, a StateDelta simply records the before and after objects:

```python
# Option settlement transaction
Transaction(
    tx_id="settle_OPT_123",
    timestamp=datetime(2025, 12, 19, 16, 0),
    moves=[
        Move("alice", "bob", "USD", 45000, "settle_cash"),
        Move("bob", "alice", "AAPL", 300, "settle_delivery"),
        Move("alice", "bob", "OPT_123", 3, "close_position"),
    ],
    state_deltas=[
        StateDelta(
            unit="OPT_123",
            old_state=OptionState(..., settled=False, ...),
            new_state=OptionState(..., settled=True, ...),
        ),
    ],
)
```

**Replay backward** is trivial: replace `new_state` with `old_state`.

**Replay forward** is also trivial: replace `old_state` with `new_state`.

No field-by-field mutation tracking needed.

---

## 5. The Ledger

### 5.1 What the Ledger Manages

The Ledger is the central stateful component. It maintains:

```
Ledger:
  name:              "main"
  current_time:      datetime
  
  # Core state
  wallets:           Set[str]                    # Registered wallet IDs
  units:             Dict[str, Unit]             # Registered units
  balances:          Dict[str, Dict[str, float]] # wallet → unit → quantity
  
  # Audit trail
  transaction_log:   List[Transaction]           # All executed transactions
  seen_tx_ids:       Set[str]                    # For idempotency
  
  # Configuration
  verbose:           bool                        # Print debug output
  fast_mode:         bool                        # Skip validation
  no_log:            bool                        # Skip transaction logging
```

### 5.2 Key Operations

**Registration**

Before use, wallets and units must be registered:

```python
ledger.register_wallet("alice")
ledger.register_wallet("bob")

ledger.register_unit(Unit(
    symbol="USD",
    name="US Dollar",
    unit_type="CASH",
    decimal_places=2,
    state=CashState(issuer="FED"),
))
```

**Execution**

Execute a transaction:

```python
tx = Transaction(
    tx_id="trade_001",
    timestamp=ledger.current_time,
    moves=[Move("alice", "bob", "USD", 1000, "payment")],
    state_deltas=[]
)

result = ledger.execute(tx)
# result is APPLIED, ALREADY_APPLIED, or REJECTED
```

Or execute a ContractResult (which creates a transaction internally):

```python
result = some_contract.compute_settlement(ledger, ...)
ledger.execute_contract(result)
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
state = ledger.get_unit_state("OPT_123")  # Returns immutable state object
positions = ledger.get_positions("AAPL")  # All wallets holding AAPL
```

### 5.3 State Reconstruction

A critical capability: reconstruct the ledger state at any past time.

**Why Needed**

- P&L calculation: Compare portfolio value at T0 vs T1
- Debugging: "What was the state when that trade happened?"
- Analysis: "What was my maximum drawdown?"
- Verification: Confirm reconstruction matches known-good checkpoint

**The Unwind Algorithm**

We reconstruct past state by **unwinding** from the present:

```
state_at(T):
  1. Start with CURRENT state (balances + unit_states)
  2. For each transaction AFTER T (in reverse chronological order):
     a. Reverse moves: add quantity back to source, subtract from dest
     b. Restore old unit states: replace new_state with old_state
  3. Return reconstructed state
```

**Why Unwind, Not Replay?**

Replay (start from zero, apply transactions up to T) has a fatal flaw: it misses initial balances set via direct assignment.

```
# Setup
ledger.balances["alice"]["USD"] = 100,000  # Direct assignment, not logged

# Later
ledger.execute(trade_tx)  # Logged

# Replay approach
state_at(T0):
  Start from zero → alice.USD = 0
  Apply transactions up to T0 → no transactions yet
  Result: alice.USD = 0  ← WRONG!

# Unwind approach
state_at(T0):
  Start from current → alice.USD = 95,000
  Reverse transactions after T0 → trade_tx is after T0, reverse it
  Result: alice.USD = 100,000  ← CORRECT!
```

The current state is always correct (it includes everything). We just undo the documented changes.

**Immutable State Makes Unwind Simple**

With immutable states, reversing a state change is trivial:

```python
# Forward: unit.state = state_delta.new_state
# Backward: unit.state = state_delta.old_state

for state_delta in reversed(tx.state_deltas):
    self.units[state_delta.unit].state = state_delta.old_state
```

No need to track individual field changes or compute inverses.

### 5.4 Cloning

Create an independent copy of the ledger:

```python
ledger_copy = ledger.clone()
```

The clone has:
- Same wallets, units, balances, unit states
- Same transaction log
- Independent state: changes to clone don't affect original

**This is essential for Monte Carlo simulation** (see Section 9) and for **state verification** (see Section 11).

### 5.5 Performance Modes

For different use cases:

| Mode | Validation | Logging | Use Case |
|------|------------|---------|----------|
| Standard | Yes | Yes | Production, debugging, record keeping |
| fast_mode | No | Yes | Trusted simulations |
| no_log | Yes | No | Memory-constrained |
| fast_mode + no_log | No | No | Maximum throughput (Monte Carlo) |

```python
# Record keeping (safe, auditable)
ledger = Ledger("main", fast_mode=False, no_log=False)

# Maximum speed (Monte Carlo with millions of transactions)
ledger = Ledger("main", fast_mode=True, no_log=True)
```

---

## 6. Smart Contracts

### 6.1 What is a Smart Contract?

A **Smart Contract** is a deterministic program that computes balance and state changes based on current conditions.

```
Smart Contract: (Ledger State, Time, Prices, Params) → ContractResult
```

Key properties:
- **Pure function**: No side effects. Same inputs → same outputs.
- **Reads ledger**: Examines balances, unit states, time
- **Returns result**: ContractResult with moves and state_deltas
- **Does not execute**: The ledger executes the result

### 6.2 Contract Interface

Every instrument type implements this interface:

```python
class SmartContract(Protocol):
    
    def check_lifecycle(
        self,
        ledger: LedgerView,      # Read-only access
        unit_symbol: str,         # Which unit to check
        current_time: datetime,   # Current time
        prices: Dict[str, float], # Current prices
    ) -> ContractResult:
        """
        Check if any lifecycle events should fire.
        
        Returns ContractResult with moves and state_deltas.
        Returns empty ContractResult if no events.
        """
        ...
```

### 6.3 Example: Stock with Dividend Schedule

Stocks are not just static assets—they have lifecycle events too. A stock that pays dividends has a **dividend schedule** as part of its state.

```python
@dataclass(frozen=True)
class DividendEvent:
    ex_date: datetime           # Must own before this date
    record_date: datetime       # Ownership checked on this date
    payment_date: datetime      # Cash delivered on this date
    amount_per_share: float     # Dividend amount
    currency: str               # Payment currency

@dataclass(frozen=True)
class StockState:
    issuer: str
    dividend_schedule: Tuple[DividendEvent, ...]
    dividends_paid: Tuple[datetime, ...]  # Record of which have been paid
```

The stock contract checks if any dividends are due:

```python
class StockContract:
    
    def check_lifecycle(self, ledger, symbol, t, prices) -> ContractResult:
        state = ledger.get_unit_state(symbol)
        
        moves = []
        new_dividends_paid = list(state.dividends_paid)
        
        for div in state.dividend_schedule:
            # Skip if already paid
            if div.payment_date in state.dividends_paid:
                continue
            
            # Skip if not yet payment date
            if t < div.payment_date:
                continue
            
            # Pay dividend to all holders
            positions = ledger.get_positions(symbol)
            for wallet, shares in positions.items():
                if shares > 0 and wallet != state.issuer:
                    amount = shares * div.amount_per_share
                    moves.append(Move(
                        source=f"{state.issuer}_treasury",
                        dest=wallet,
                        unit=div.currency,
                        quantity=amount,
                        contract_id=f"div_{symbol}_{div.payment_date.date()}",
                    ))
            
            new_dividends_paid.append(div.payment_date)
        
        if not moves:
            return ContractResult()  # No dividends due
        
        # Create new immutable state
        new_state = StockState(
            issuer=state.issuer,
            dividend_schedule=state.dividend_schedule,
            dividends_paid=tuple(new_dividends_paid),
        )
        
        state_delta = StateDelta(
            unit=symbol,
            old_state=state,
            new_state=new_state,
        )
        
        return ContractResult(moves=moves, state_deltas=[state_delta])
```

**Example dividend schedule:**

```python
aapl_state = StockState(
    issuer="AAPL",
    dividend_schedule=(
        DividendEvent(
            ex_date=datetime(2025, 2, 7),
            record_date=datetime(2025, 2, 10),
            payment_date=datetime(2025, 2, 13),
            amount_per_share=0.25,
            currency="USD",
        ),
        DividendEvent(
            ex_date=datetime(2025, 5, 9),
            record_date=datetime(2025, 5, 12),
            payment_date=datetime(2025, 5, 15),
            amount_per_share=0.25,
            currency="USD",
        ),
        # ... quarterly dividends
    ),
    dividends_paid=(),
)
```

### 6.4 Example: European Call Option

```python
class EuropeanOptionContract:
    
    def check_lifecycle(self, ledger, symbol, t, prices) -> ContractResult:
        state = ledger.get_unit_state(symbol)
        
        # Already settled → nothing to do
        if state.settled:
            return ContractResult()
        
        # Not yet matured → nothing to do
        if t < state.maturity:
            return ContractResult()
        
        # Time to settle
        spot = prices[state.underlying]
        strike = state.strike
        long_wallet = state.long_wallet
        short_wallet = state.short_wallet
        quantity = state.quantity
        
        # Get position size
        position = ledger.get_balance(long_wallet, symbol)
        if position <= 0:
            return ContractResult()
        
        moves = []
        is_itm = spot > strike
        
        if is_itm:
            # Physical delivery
            total_shares = position * quantity
            total_cash = total_shares * strike
            
            moves.append(Move(long_wallet, short_wallet, state.currency, 
                              total_cash, f"settle_{symbol}_cash"))
            moves.append(Move(short_wallet, long_wallet, state.underlying,
                              total_shares, f"settle_{symbol}_delivery"))
        
        # Close out option position
        moves.append(Move(long_wallet, short_wallet, symbol, 
                          position, f"close_{symbol}"))
        
        # Create new immutable state
        new_state = OptionState(
            underlying=state.underlying,
            strike=state.strike,
            maturity=state.maturity,
            option_type=state.option_type,
            long_wallet=state.long_wallet,
            short_wallet=state.short_wallet,
            quantity=state.quantity,
            currency=state.currency,
            settled=True,
            exercised=is_itm,
            settlement_price=spot,
        )
        
        state_delta = StateDelta(unit=symbol, old_state=state, new_state=new_state)
        
        return ContractResult(moves=moves, state_deltas=[state_delta])
```

### 6.5 Example: Delta Hedging Strategy

A strategy that maintains delta-neutral position for a call option:

```python
class DeltaHedgeContract:
    
    def check_lifecycle(self, ledger, symbol, t, prices) -> ContractResult:
        state = ledger.get_unit_state(symbol)
        
        if state.liquidated:
            return ContractResult()
        
        # Past maturity → liquidate
        if t >= state.maturity:
            return self._compute_liquidation(ledger, symbol, prices, state)
        
        # Compute required hedge
        spot = prices[state.underlying]
        delta = self._compute_delta(state, spot, t)
        target_shares = delta * state.num_options * state.multiplier
        
        current_shares = ledger.get_balance(state.strategy_wallet, 
                                            state.underlying)
        shares_to_trade = target_shares - current_shares
        
        if abs(shares_to_trade) < state.min_trade:
            return ContractResult()  # No rebalance needed
        
        # Generate rebalancing trades
        moves = self._create_rebalance_moves(state, shares_to_trade, spot)
        
        # Update cumulative cash in state
        new_state = DeltaHedgeState(
            ...
            cumulative_cash=state.cumulative_cash - shares_to_trade * spot,
            rebalance_count=state.rebalance_count + 1,
        )
        
        return ContractResult(
            moves=moves, 
            state_deltas=[StateDelta(symbol, state, new_state)]
        )
```

### 6.6 Contract Registry

The system needs to know which contract handles each unit type:

```python
contract_registry = {
    "STOCK": StockContract(),            # Handles dividends
    "EUROPEAN_OPTION": EuropeanOptionContract(),
    "VARIANCE_SWAP": VarianceSwapContract(),
    "FORWARD": ForwardContract(),
    "DELTA_HEDGE_STRATEGY": DeltaHedgeContract(),
    "BOND": BondContract(),              # Handles coupons
    "CASH": CashContract(),              # Usually no-op
}

def get_contract(unit: Unit) -> SmartContract:
    return contract_registry.get(unit.unit_type)
```

---

## 7. The Lifecycle Engine

### 7.1 Purpose

The **Lifecycle Engine** automates lifecycle events. Instead of manually calling each contract, the engine:

1. Advances time
2. Gets current prices
3. Checks all units for events
4. Executes any resulting transactions

### 7.2 The Step Function

```python
class LifecycleEngine:
    
    def __init__(self, ledger: Ledger, registry: Dict[str, SmartContract]):
        self.ledger = ledger
        self.registry = registry
    
    def step(self, t: datetime, prices: Dict[str, float]) -> List[Transaction]:
        """
        Advance to time t and process all lifecycle events.
        
        Returns list of transactions that were executed.
        """
        # 1. Advance time
        self.ledger.advance_time(t)
        
        # 2. Check each unit
        executed = []
        for symbol, unit in self.ledger.units.items():
            contract = self.registry.get(unit.unit_type)
            if contract is None:
                continue
            
            # 3. Compute lifecycle events
            result = contract.check_lifecycle(
                self.ledger, symbol, t, prices
            )
            
            # 4. Execute if non-empty
            if not result.is_empty():
                tx = self.ledger.execute_contract(result)
                executed.append(tx)
        
        return executed
```

### 7.3 Iteration Order

When multiple units have events at the same time, they are processed in deterministic order (by symbol name or registration order). For most instruments, order doesn't matter. When it does (e.g., a hedge depends on an option settling first), the instruments should be designed to handle this, or the time granularity should be increased.

---

## 8. Pricing Sources

### 8.1 Purpose

A **PricingSource** provides asset prices at any point in time. The Lifecycle Engine queries it to:

- Determine option settlement prices
- Calculate hedge deltas
- Value portfolios
- Pay dividends in correct currency

### 8.2 Interface

```python
class PricingSource(Protocol):
    base_currency: str
    
    def get_price(self, unit: str, t: datetime) -> Optional[float]:
        """Get price of unit at time t in base currency."""
        ...
    
    def get_prices(self, units: Set[str], t: datetime) -> Dict[str, float]:
        """Get prices for multiple units."""
        ...
```

### 8.3 Implementations

**StaticPricingSource**

Fixed prices, ignores time. Useful for testing.

```python
prices = StaticPricingSource({
    "AAPL": 175.0,
    "GOOG": 140.0,
    "GOLD": 2050.0,  # Per ounce
    "EUR": 1.08,
    "BTC": 45000.0,
})
```

**TimeSeriesPricingSource**

Prices vary over time. Returns the most recent price at or before the requested time.

```python
prices = TimeSeriesPricingSource()
prices.add("AAPL", datetime(2025, 1, 1), 170.0)
prices.add("AAPL", datetime(2025, 1, 2), 172.5)
prices.add("AAPL", datetime(2025, 1, 3), 171.0)

prices.get_price("AAPL", datetime(2025, 1, 2, 12, 0))  # → 172.5
```

**SimulatedPricingSource**

Pre-generated price paths, typically from Monte Carlo simulation.

```python
# Path: list of (datetime, price) tuples
aapl_path = [
    (datetime(2025, 1, 1), 170.0),
    (datetime(2025, 1, 2), 173.5),
    (datetime(2025, 1, 3), 168.2),
    ...
]

prices = SimulatedPricingSource({
    "AAPL": aapl_path,
    "GOOG": goog_path,
    "EUR": eur_path,
})
```

---

## 9. Monte Carlo Simulation Architecture

### 9.1 The Goal

We want to understand the **distribution of outcomes** for a portfolio. This requires:

1. Simulating many possible futures (price paths)
2. For each future, evolving the portfolio through time
3. Analyzing the collection of final states

### 9.2 The Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MONTE CARLO SIMULATION                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   INPUTS:                                                        │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│   │ Initial Ledger  │  │ Path Generator  │  │ N = num paths   │ │
│   │ (portfolio)     │  │ (GBM, etc.)     │  │ (e.g., 1000)    │ │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│            │                    │                    │           │
│            └────────────────────┼────────────────────┘           │
│                                 ▼                                │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              PATH GENERATION                             │   │
│   │                                                          │   │
│   │  For each asset (AAPL, GOOG, ..., EUR):                 │   │
│   │    Generate N price paths from T_start to T_end         │   │
│   │                                                          │   │
│   │  Result: N PricingSources, each containing all assets   │   │
│   │                                                          │   │
│   │  paths[0] = PricingSource with path 0 for all assets    │   │
│   │  paths[1] = PricingSource with path 1 for all assets    │   │
│   │  ...                                                     │   │
│   │  paths[999] = PricingSource with path 999 for all assets│   │
│   └─────────────────────────────────────────────────────────┘   │
│                                 │                                │
│                                 ▼                                │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              LEDGER CLONING                              │   │
│   │                                                          │   │
│   │  ledger_0 = initial_ledger.clone()                      │   │
│   │  ledger_1 = initial_ledger.clone()                      │   │
│   │  ...                                                     │   │
│   │  ledger_999 = initial_ledger.clone()                    │   │
│   │                                                          │   │
│   │  Each clone is INDEPENDENT                               │   │
│   │  Same initial state, will diverge based on prices       │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                 │                                │
│                                 ▼                                │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              PARALLEL SIMULATION                         │   │
│   │                                                          │   │
│   │  For i in 0..999 (can be parallelized):                 │   │
│   │    engine_i = LifecycleEngine(ledger_i, contracts)      │   │
│   │                                                          │   │
│   │    For t in timestamps:                                  │   │
│   │      prices = paths[i].get_prices(t)                    │   │
│   │      engine_i.step(t, prices)                           │   │
│   │      snapshots[i].append(ledger_i.snap())               │   │
│   │                                                          │   │
│   │  Result: 1000 ledgers at final time, each with history  │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                 │                                │
│                                 ▼                                │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              ANALYSIS                                    │   │
│   │                                                          │   │
│   │  For each ledger_i:                                      │   │
│   │    pnl[i] = compute_pnl(ledger_i, T_start, T_end)       │   │
│   │    max_drawdown[i] = compute_max_drawdown(snapshots[i]) │   │
│   │    sharpe[i] = compute_sharpe(snapshots[i])             │   │
│   │                                                          │   │
│   │  Aggregate:                                              │   │
│   │    expected_pnl = mean(pnl)                              │   │
│   │    var_95 = percentile(pnl, 5)                          │   │
│   │    cvar_95 = mean(pnl[pnl < var_95])                    │   │
│   │    prob_loss = count(pnl < 0) / N                       │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 Concrete Example

**Setup**: Portfolio with stocks, currencies, and a delta-hedged call option

```
Assets to simulate:
  - 10 stocks: AAPL, GOOG, MSFT, AMZN, META, NVDA, TSLA, JPM, V, JNJ
  - 2 currencies: USD (numeraire), EUR (foreign)
  
  Total: 11 price processes (USD is always 1.0)

Initial portfolio:
  - Wallet "strategy":
      USD:  100,000
      AAPL: 0
  - Long 10 call options on AAPL, strike 150, expiring in 90 days
  - Delta hedge strategy attached to the options

Parameters:
  - Simulation horizon: 90 days
  - Daily time steps
  - 1,000 Monte Carlo paths
  - Each stock: volatility 20-40%, drift 0%
  - EUR/USD: volatility 10%, drift 0%
```

**Step 1: Generate Price Paths**

Using Geometric Brownian Motion (or any other model):

```python
def generate_gbm_path(S0, T_days, volatility, drift, seed):
    """Generate one price path."""
    dt = 1/252  # Daily steps
    path = [(start_date, S0)]
    S = S0
    
    np.random.seed(seed)
    for day in range(1, T_days + 1):
        Z = np.random.normal()
        S = S * np.exp((drift - 0.5*volatility**2)*dt + volatility*np.sqrt(dt)*Z)
        path.append((start_date + timedelta(days=day), S))
    
    return path

# Generate 1000 paths for each asset
assets = {
    "AAPL": (150.0, 0.25),  # (initial_price, volatility)
    "GOOG": (140.0, 0.28),
    "MSFT": (380.0, 0.22),
    # ... 7 more stocks
    "EUR": (1.08, 0.10),    # EUR/USD exchange rate
}

all_paths = {}
for asset, (S0, vol) in assets.items():
    all_paths[asset] = [
        generate_gbm_path(S0, 90, vol, 0.0, seed=i*1000+hash(asset)%1000)
        for i in range(1000)
    ]

# Create 1000 PricingSources (one per simulation path)
pricing_sources = []
for i in range(1000):
    path_dict = {asset: all_paths[asset][i] for asset in assets}
    path_dict["USD"] = [(t, 1.0) for t, _ in all_paths["AAPL"][i]]  # Numeraire
    pricing_sources.append(SimulatedPricingSource(path_dict))
```

**Step 2: Clone the Ledger**

```python
# Setup initial ledger
initial_ledger = Ledger("template", verbose=False, fast_mode=True, no_log=True)

# Register all assets
initial_ledger.register_unit(cash("USD"))
initial_ledger.register_unit(cash("EUR"))
for stock in ["AAPL", "GOOG", "MSFT", ...]:
    initial_ledger.register_unit(stock_unit(stock))

# Register wallets
initial_ledger.register_wallet("strategy")
initial_ledger.register_wallet("market")

# Set initial balances
initial_ledger.balances["strategy"]["USD"] = 100_000
initial_ledger.balances["market"]["USD"] = 10_000_000
initial_ledger.balances["market"]["AAPL"] = 100_000

# Create and register option + hedge strategy
# (details omitted for brevity)

# Clone 1000 times
ledgers = [initial_ledger.clone() for _ in range(1000)]
```

**Step 3: Run Simulations**

```python
from concurrent.futures import ProcessPoolExecutor

def run_single_simulation(args):
    ledger, pricing_source, timestamps = args
    engine = LifecycleEngine(ledger, contract_registry)
    snapshots = []
    
    for t in timestamps:
        prices = pricing_source.get_prices(all_assets, t)
        engine.step(t, prices)
        snapshots.append(ledger.snap())
    
    return ledger, snapshots

# Prepare arguments
timestamps = [start_date + timedelta(days=d) for d in range(91)]
args = [(ledgers[i], pricing_sources[i], timestamps) for i in range(1000)]

# Run in parallel
with ProcessPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(run_single_simulation, args))

final_ledgers = [r[0] for r in results]
all_snapshots = [r[1] for r in results]
```

**Step 4: Analyze Results**

```python
# Compute P&L for each path
pnls = []
for i, ledger in enumerate(final_ledgers):
    snap_start = ledger.state_at(start_date)
    snap_end = ledger.snap()
    final_prices = pricing_sources[i].get_prices(all_assets, end_date)
    
    pnl = compute_pnl(snap_start, snap_end, final_prices)
    pnls.append(pnl)

pnls = np.array(pnls)

# Statistics
print(f"Expected P&L: ${np.mean(pnls):,.2f}")
print(f"Std Dev: ${np.std(pnls):,.2f}")
print(f"95% VaR: ${np.percentile(pnls, 5):,.2f}")
print(f"Probability of loss: {np.mean(pnls < 0):.1%}")

# Maximum drawdown across all paths
max_drawdowns = [
    compute_max_drawdown(snapshots, pricing_sources[i])
    for i, snapshots in enumerate(all_snapshots)
]

print(f"Average max drawdown: {np.mean(max_drawdowns):.1%}")
print(f"Worst max drawdown: {np.max(max_drawdowns):.1%}")
```

### 9.4 Why This Architecture Works

**Independence**: Each ledger clone is completely independent. Path i's prices only affect ledger i. No cross-contamination.

**Parallelism**: Since ledgers are independent, simulations can run in parallel across CPU cores or machines.

**Reproducibility**: Given the same random seeds, the same results are produced every time.

**Full History**: Each ledger maintains its complete history (if no_log=False), enabling rich analysis.

**Autonomous Lifecycle**: The Lifecycle Engine handles all events automatically. No manual intervention needed for option expiry, dividend payments, hedge rebalancing, etc.

---

## 10. Analysis and Metrics

### 10.1 P&L Calculation

**Basic P&L**: Difference in portfolio value

```python
def compute_pnl(snap_start: Snapshot, snap_end: Snapshot, 
                prices_start: Dict, prices_end: Dict) -> float:
    value_start = portfolio_value(snap_start, prices_start)
    value_end = portfolio_value(snap_end, prices_end)
    return value_end - value_start

def portfolio_value(snap: Snapshot, prices: Dict) -> float:
    total = 0.0
    for unit, balance in snap.balances["strategy"].items():
        if unit in prices:
            total += balance * prices[unit]
    return total
```

**P&L Attribution**: Decompose into price effect vs. flow effect

```python
def compute_pnl_attribution(snap_start, snap_end, prices_start, prices_end):
    # Price P&L: initial positions × price change
    price_pnl = sum(
        snap_start.balances["strategy"].get(unit, 0) * 
        (prices_end.get(unit, 0) - prices_start.get(unit, 0))
        for unit in prices_start
    )
    
    # Flow P&L: change in positions × ending price
    flow_pnl = sum(
        (snap_end.balances["strategy"].get(unit, 0) - 
         snap_start.balances["strategy"].get(unit, 0)) *
        prices_end.get(unit, 0)
        for unit in prices_end
    )
    
    return {"price_pnl": price_pnl, "flow_pnl": flow_pnl}
```

### 10.2 Drawdown Analysis

**Maximum Drawdown**: Largest peak-to-trough decline

```python
def compute_max_drawdown(snapshots: List[Snapshot], 
                         prices_fn: Callable) -> float:
    values = [
        portfolio_value(s, prices_fn(s.timestamp))
        for s in snapshots
    ]
    
    peak = values[0]
    max_drawdown = 0.0
    
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            drawdown = (peak - v) / peak
            max_drawdown = max(max_drawdown, drawdown)
    
    return max_drawdown
```

### 10.3 Risk Metrics

**Value at Risk (VaR)**

```python
def compute_var(pnls: np.array, confidence: float = 0.95) -> float:
    return np.percentile(pnls, (1 - confidence) * 100)
```

**Conditional VaR (Expected Shortfall)**

```python
def compute_cvar(pnls: np.array, confidence: float = 0.95) -> float:
    var = compute_var(pnls, confidence)
    return np.mean(pnls[pnls <= var])
```

**Sharpe Ratio**

```python
def compute_sharpe(daily_returns: np.array, risk_free_rate: float = 0.0) -> float:
    excess_returns = daily_returns - risk_free_rate / 252
    return np.sqrt(252) * np.mean(excess_returns) / np.std(excess_returns)
```

---

## 11. State Verification and Ledger Equality

### 11.1 The Problem

When developing and testing the framework, we need confidence that state reconstruction works correctly. How do we verify that `ledger.state_at(t0)` produces the correct result?

### 11.2 The Solution: Checkpoint and Compare

**Strategy**: At time T0, clone the ledger to create a checkpoint. Later, reconstruct state at T0 and compare with the checkpoint.

```python
# At T0: Create checkpoint
checkpoint_t0 = ledger.clone()

# Execute transactions...
ledger.execute(tx1)
ledger.execute(tx2)
ledger.execute(tx3)

# Later: Verify reconstruction
reconstructed = ledger.state_at(t0)
assert ledger_state_equals(reconstructed, checkpoint_t0.snap())
```

### 11.3 Defining Ledger Equality

Two ledger states are **equal** if they have:

1. **Same wallets**: Identical set of registered wallet IDs
2. **Same units**: Identical set of registered unit symbols
3. **Same balances**: For each wallet and unit, identical quantities
4. **Same unit states**: For each unit, identical state objects

**NOT required to be equal**:
- Transaction log (may differ in length)
- Seen tx_ids (may differ)
- Current time (snapshots have their own timestamp)

```python
def ledger_state_equals(snap_a: Snapshot, snap_b: Snapshot) -> bool:
    """
    Compare two ledger states for equality.
    
    Returns True if wallets, units, balances, and unit states are identical.
    """
    # Check wallets
    if set(snap_a.balances.keys()) != set(snap_b.balances.keys()):
        return False
    
    # Check units
    if set(snap_a.unit_states.keys()) != set(snap_b.unit_states.keys()):
        return False
    
    # Check balances (with tolerance for floating point)
    for wallet in snap_a.balances:
        for unit in set(snap_a.balances[wallet].keys()) | set(snap_b.balances[wallet].keys()):
            bal_a = snap_a.balances[wallet].get(unit, 0.0)
            bal_b = snap_b.balances[wallet].get(unit, 0.0)
            if abs(bal_a - bal_b) > 1e-9:
                return False
    
    # Check unit states
    for unit in snap_a.unit_states:
        if snap_a.unit_states[unit] != snap_b.unit_states[unit]:
            return False
    
    return True
```

### 11.4 Detailed Comparison for Debugging

When states don't match, we need to know why:

```python
def compare_ledger_states(snap_a: Snapshot, snap_b: Snapshot) -> Dict:
    """
    Detailed comparison of two ledger states.
    
    Returns dict describing all differences.
    """
    differences = {
        "wallets": {"only_in_a": [], "only_in_b": []},
        "units": {"only_in_a": [], "only_in_b": []},
        "balances": [],  # List of {wallet, unit, value_a, value_b}
        "unit_states": [],  # List of {unit, state_a, state_b}
    }
    
    # Compare wallets
    wallets_a = set(snap_a.balances.keys())
    wallets_b = set(snap_b.balances.keys())
    differences["wallets"]["only_in_a"] = list(wallets_a - wallets_b)
    differences["wallets"]["only_in_b"] = list(wallets_b - wallets_a)
    
    # Compare units
    units_a = set(snap_a.unit_states.keys())
    units_b = set(snap_b.unit_states.keys())
    differences["units"]["only_in_a"] = list(units_a - units_b)
    differences["units"]["only_in_b"] = list(units_b - units_a)
    
    # Compare balances
    for wallet in wallets_a & wallets_b:
        all_units = set(snap_a.balances[wallet].keys()) | set(snap_b.balances[wallet].keys())
        for unit in all_units:
            bal_a = snap_a.balances[wallet].get(unit, 0.0)
            bal_b = snap_b.balances[wallet].get(unit, 0.0)
            if abs(bal_a - bal_b) > 1e-9:
                differences["balances"].append({
                    "wallet": wallet,
                    "unit": unit,
                    "value_a": bal_a,
                    "value_b": bal_b,
                    "difference": bal_a - bal_b,
                })
    
    # Compare unit states
    for unit in units_a & units_b:
        if snap_a.unit_states[unit] != snap_b.unit_states[unit]:
            differences["unit_states"].append({
                "unit": unit,
                "state_a": snap_a.unit_states[unit],
                "state_b": snap_b.unit_states[unit],
            })
    
    return differences
```

### 11.5 Automated Verification in Tests

```python
def test_state_reconstruction():
    """Verify that state reconstruction matches checkpoint."""
    ledger = create_test_ledger()
    
    # Set initial state
    ledger.balances["alice"]["USD"] = 100_000
    ledger.balances["alice"]["AAPL"] = 100
    t0 = ledger.current_time
    
    # Create checkpoint at T0
    checkpoint = ledger.clone()
    
    # Execute some transactions
    ledger.advance_time(t0 + timedelta(hours=1))
    ledger.execute(trade_tx_1)
    
    ledger.advance_time(t0 + timedelta(hours=2))
    ledger.execute(trade_tx_2)
    
    ledger.advance_time(t0 + timedelta(hours=3))
    ledger.execute(trade_tx_3)
    
    # Reconstruct state at T0
    reconstructed = ledger.state_at(t0)
    expected = checkpoint.snap()
    
    # Compare
    assert ledger_state_equals(reconstructed, expected), \
        f"State mismatch:\n{compare_ledger_states(reconstructed, expected)}"
```

### 11.6 Verifying Unit State Reconstruction

The immutable state design makes this straightforward:

```python
def test_unit_state_reconstruction():
    """Verify that unit states are correctly reconstructed."""
    ledger = create_test_ledger_with_option()
    t0 = ledger.current_time
    
    # Checkpoint before settlement
    checkpoint = ledger.clone()
    
    # Advance to maturity and settle
    ledger.advance_time(maturity_date)
    engine.step(maturity_date, {"AAPL": 175.0})  # Option settles
    
    # Verify current state shows settled
    current_state = ledger.get_unit_state("OPT_123")
    assert current_state.settled == True
    
    # Reconstruct at T0 (before settlement)
    reconstructed = ledger.state_at(t0)
    
    # Verify reconstructed state shows NOT settled
    assert reconstructed.unit_states["OPT_123"].settled == False
    
    # Verify matches checkpoint
    assert reconstructed.unit_states["OPT_123"] == checkpoint.snap().unit_states["OPT_123"]
```

---

## 12. Implementation Guidelines

### 12.1 Verbose Mode

When `verbose=True`, transactions print detailed information:

**Successful Execution:**

```
................................................................................
▶️  Ledger [main] executing:

   tx_id:     settle_OPT_123_20250619
   timestamp: 2025-06-19 16:00:00
   source:    european_option.settlement
   
   Moves (3):
      [0] alice → bob      : +45,000.00 USD     (settle_OPT_123_cash)
      [1] bob   → alice    : +300.000000 AAPL   (settle_OPT_123_delivery)
      [2] alice → bob      : +3.00 OPT_123      (close_OPT_123)
   
   State Deltas (1):
      OPT_123:
        settled          : False → True
        exercised        : False → True
        settlement_price : None  → 175.0

   → APPLIED ✓
   
   Balances after:
      alice: {USD: 54,962.50, AAPL: 300.0, OPT_123: 0.0}
      bob:   {USD: 55,037.50, AAPL: 200.0, OPT_123: 0.0}
................................................................................
```

**Rejected Transaction:**

```
................................................................................
▶️  Ledger [main] executing:

   tx_id:     transfer_001
   timestamp: 2025-06-15 10:30:00
   
   Moves (1):
      [0] alice → charlie : +5.00 OPT_123 (transfer_attempt)

   → REJECTED ✗
   
   Reason: TransferRuleViolation
           Bilateral OPT_123: charlie not authorized
           Allowed parties: alice, bob
................................................................................
```

### 12.2 File Organization

```
ledger/
├── __init__.py              # Package exports
├── core.py                  # Ledger, Move, Transaction, Snapshot
├── engine.py                # LifecycleEngine
├── pricing.py               # PricingSource implementations
├── analysis.py              # P&L, drawdown, risk metrics
├── verification.py          # ledger_state_equals, compare_ledger_states
├── black_scholes.py         # Option pricing (user's existing file)
│
├── contracts/
│   ├── __init__.py          # Contract registry
│   ├── base.py              # SmartContract protocol
│   ├── stock.py             # Dividend handling
│   ├── european_option.py   # Call/put options
│   ├── variance_swap.py     # Variance swaps
│   ├── forward.py           # Forward contracts
│   └── delta_hedge.py       # Delta hedging strategy
│
└── simulation/
    ├── __init__.py
    ├── path_generator.py    # GBM, Heston, etc.
    └── monte_carlo.py       # Parallel simulation runner
```

### 12.3 Thread Safety

The Ledger is **NOT thread-safe**. For parallel Monte Carlo:

- Clone the ledger for each path
- Run each simulation in a separate process (not thread)
- Use ProcessPoolExecutor, not ThreadPoolExecutor

### 12.4 Memory Considerations

For large simulations:

| Configuration | Memory per Ledger | Use Case |
|---------------|-------------------|----------|
| no_log=False | High (keeps all transactions) | Record keeping, debugging |
| no_log=True | Low (only current state) | Production Monte Carlo |

### 12.5 Performance Tips

1. **Use fast_mode=True** for trusted simulations (skips validation)
2. **Use no_log=True** for Monte Carlo (don't need transaction history per path)
3. **Batch path generation** before simulation (don't generate on-the-fly)
4. **Use NumPy** for path generation and analysis
5. **Parallelize** across CPU cores using ProcessPoolExecutor
6. **Use immutable states** (no defensive copying needed)

---

## 13. Summary

### 13.1 Key Concepts

| Concept | Definition |
|---------|------------|
| **Wallet** | Account holding balances of various units |
| **Unit** | Type of asset (stock, currency, commodity, derivative) |
| **Move** | Atomic transfer of value between wallets |
| **Transaction** | Atomic batch of moves + state replacements |
| **StateDelta** | Record of unit state replacement (old → new) |
| **Snapshot** | Complete state at a point in time |
| **SmartContract** | Pure function computing lifecycle events |
| **LifecycleEngine** | Orchestrates autonomous execution |
| **PricingSource** | Provides asset prices at any time |

### 13.2 Key Properties

| Property | Meaning |
|----------|---------|
| **Conservation** | Total quantity of any unit never changes |
| **Atomicity** | Transactions are all-or-nothing |
| **Determinism** | Same inputs → same outputs |
| **Immutability** | Unit states are immutable; updates replace entirely |
| **Auditability** | Every change is logged and reversible |
| **State-Sufficiency** | Portfolio value depends only on current state |
| **Path-Independence** | P&L depends only on start and end states |

### 13.3 Dual Purpose

| Purpose | Configuration | Features Used |
|---------|---------------|---------------|
| **Record Keeping** | verbose=True, fast_mode=False, no_log=False | Full validation, audit trail, verbose output |
| **Simulation** | verbose=False, fast_mode=True, no_log=True | Maximum throughput, minimal memory |

### 13.4 Monte Carlo Workflow

```
1. SETUP
   - Create initial ledger with portfolio
   - Register all units (any asset class)
   - Set initial balances

2. GENERATE
   - Generate N price paths for each asset
   - Create N PricingSources

3. CLONE
   - Clone ledger N times
   - Each clone gets one PricingSource

4. SIMULATE
   - For each (ledger, pricing_source) pair:
     - Create LifecycleEngine
     - Step through all timestamps
     - Record snapshots

5. ANALYZE
   - Compute P&L for each path
   - Compute drawdowns, risk metrics
   - Aggregate across paths

6. VERIFY (optional)
   - Compare reconstructed states to checkpoints
   - Ensure state_at() works correctly
```

### 13.5 What Makes This Framework Unique

1. **Unified Model**: Any asset class uses the same Move primitive
2. **Autonomous Lifecycle**: No manual intervention for any lifecycle event
3. **Full Reversibility**: Can reconstruct any past state exactly (balances AND unit states)
4. **Immutable States**: Pure functions, easy testing, clean replay
5. **Simulation-Ready**: Designed for Monte Carlo from the ground up
6. **Record-Keeping Ready**: Full audit trails when needed
7. **Verifiable**: Built-in comparison tools to validate reconstruction

---

*End of Design Document*
