# Ledger v0.1 Design Document

## Overview

The Ledger is a high-performance financial simulation system designed for Monte Carlo simulations, backtesting, and reproducible financial modeling. It provides:

1. **Double-entry bookkeeping** with transaction logging
2. **Time travel** via `clone_at()` for reconstructing any past state
3. **Deterministic execution** ensuring reproducible results
4. **Smart contracts** for automated lifecycle events (settlement, dividends, hedging)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CORE FRAMEWORK                          │
├─────────────────────────────────────────────────────────────────┤
│  core.py          Protocols, data structures, transfer rules   │
│  ledger.py        Stateful Ledger class (only mutable component)│
│  lifecycle.py     SmartContract protocol and LifecycleEngine   │
│  pricing_source.py Pricing sources for simulations             │
│  black_scholes.py  Black-Scholes pricing and Greeks            │
├─────────────────────────────────────────────────────────────────┤
│                     EXAMPLE APPLICATIONS                        │
├─────────────────────────────────────────────────────────────────┤
│  options.py       Bilateral option contracts                   │
│  forwards.py      Forward contracts with physical delivery     │
│  stocks.py        Stock contracts with dividend scheduling     │
│  delta_hedge_strategy.py  Delta hedging strategy               │
└─────────────────────────────────────────────────────────────────┘
```

## Basic Usage

### Creating a Ledger

```python
from ledger import Ledger
from ledger.core import cash

# Create ledger
ledger = Ledger("simulation")

# Register units and wallets
ledger.register_unit(cash("USD", "US Dollar"))
ledger.register_wallet("alice")
ledger.register_wallet("bob")

# Set initial balances
ledger.set_balance("alice", "USD", 10000.0)
ledger.set_balance("bob", "USD", 5000.0)
```

### Creating and Executing Transactions

```python
from ledger.core import Move

# Create transaction
moves = [
    Move(source="alice", dest="bob", unit="USD", quantity=100.0, contract_id="payment_1")
]
tx = ledger.create_transaction(moves)

# Execute transaction
result = ledger.execute(tx)
# Returns: ExecuteResult.APPLIED
```

### Working with Smart Contracts

```python
from ledger.lifecycle import LifecycleEngine
from ledger.options import option_contract, create_option_unit

# Create and register an option
option_unit = create_option_unit(
    symbol="AAPL_C150",
    name="AAPL Call 150",
    underlying="AAPL",
    strike=150.0,
    maturity=datetime(2025, 12, 19),
    option_type="call",
    quantity=100,
    currency="USD",
    long_wallet="alice",
    short_wallet="bob"
)
ledger.register_unit(option_unit)

# Set up lifecycle engine
engine = LifecycleEngine(ledger)
engine.register("BILATERAL_OPTION", option_contract)

# Step through time with market prices
prices = {"AAPL": 155.0}
transactions = engine.step(datetime(2025, 12, 19), prices)
```

## Core Data Structures

### Move
```python
@dataclass(frozen=True)
class Move:
    source: str       # Source wallet
    dest: str         # Destination wallet
    unit: str         # Unit symbol
    quantity: float   # Amount to transfer
    contract_id: str  # Identifier for audit trail
    metadata: Optional[Dict] = None
```

Moves are immutable and represent a single balance transfer.

### Unit

```python
@dataclass
class Unit:
    symbol: str
    name: str
    unit_type: str
    min_balance: float = 0.0
    max_balance: float = float('inf')
    decimal_places: Optional[int] = None
    transfer_rule: Optional[TransferRule] = None
    _state: Optional[UnitState] = None
```

Units define tradeable asset types. The `_state` dict holds unit-specific data like term sheets and lifecycle state. Unlike other core structures, Unit is mutable (not frozen) because the `_state` field updates during contract execution.

### Transaction
```python
@dataclass(frozen=True)
class Transaction:
    moves: Tuple[Move, ...]
    tx_id: str
    timestamp: datetime
    ledger_name: str
    state_deltas: Tuple[StateDelta, ...] = ()
    contract_ids: FrozenSet[str] = None
    execution_time: Optional[datetime] = None
```

A Transaction is an atomic group of moves and state changes. Either all apply, or none do.

The `__repr__()` uses Unicode box-drawing to display transaction details:

```
┌────────────────────────────────────────────────────────────────┐
│ Transaction: abc123                                            │
├────────────────────────────────────────────────────────────────┤
│   timestamp      : 2024-01-01 00:00:00                        │
│   ledger_name    : test                                        │
│   execution_time : 2024-01-01 00:00:00                        │
│   contract_ids   : {'test'}                                    │
├────────────────────────────────────────────────────────────────┤
│ Moves (1):                                                     │
│  [0] alice → bob: 100.0 USD                                    │
└────────────────────────────────────────────────────────────────┘
```

### StateDelta
```python
@dataclass(frozen=True)
class StateDelta:
    unit: str
    old_state: Any
    new_state: Any
```

StateDelta captures the complete before/after state for any unit state change. This enables time travel via the UNWIND algorithm.

### ContractResult

```python
@dataclass(frozen=True)
class ContractResult:
    moves: Tuple[Move, ...] = ()
    state_updates: StateUpdates = field(default_factory=dict)
```

ContractResult is the return type from smart contracts. It contains moves to execute and state updates to apply. The ledger applies these atomically when executing a contract.

### LedgerView Protocol

```python
class LedgerView(Protocol):
    @property
    def current_time(self) -> datetime: ...

    def get_balance(self, wallet: str, unit: str) -> float: ...
    def get_unit_state(self, unit: str) -> UnitState: ...
    def get_positions(self, unit: str) -> Positions: ...
    def list_wallets(self) -> Set[str]: ...
```

LedgerView is a protocol defining read-only ledger access. Smart contracts and pure functions receive LedgerView instead of Ledger, ensuring they cannot mutate state directly. The Ledger class implements this protocol.

## Reproducibility

Reproducibility is a core requirement of the system. The same inputs must always produce the same outputs.

### Guarantees

1. **Deterministic iteration**: Collections are iterated in sorted order
2. **Deterministic transaction IDs**: Content-based hashing
3. **Deterministic floating-point**: Consistent rounding per unit
4. **Complete audit trail**: Every change is logged with StateDelta records

### Clone

```python
clone = ledger.clone()  # Deep copy for Monte Carlo branching
```

Returns a completely independent copy. Changes to one don't affect the other.

### Clone At (Time Travel)

```python
past_ledger = ledger.clone_at(target_time)  # Reconstruct past state
```

Uses the **UNWIND algorithm** to reconstruct state at any past timestamp.

## The UNWIND Algorithm

UNWIND is the algorithm used for time-travel state reconstruction.

### Why Not REPLAY?

A naive approach would replay transactions from the beginning:

```python
def replay_to(target_time):
    new_ledger = empty_ledger()
    for tx in transaction_log:
        if tx.timestamp <= target_time:
            apply(tx)
    return new_ledger
```

This fails because initial balances set via `set_balance()` are not logged as transactions. They exist in current state but not in the transaction log.

### UNWIND: Start from Current, Work Backwards

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
            cloned.balances[move.source] += move.quantity
            cloned.balances[move.dest] -= move.quantity

        # 4. Restore old_state from StateDelta
        for delta in tx.state_deltas:
            cloned.units[delta.unit]._state = delta.old_state

    return cloned
```

This works because:
- Current state includes all `set_balance()` effects
- We only undo documented changes (transactions)
- StateDelta.old_state contains the exact prior state

### execution_time vs timestamp

- `timestamp`: When the transaction was created
- `execution_time`: When the transaction was applied to the ledger

UNWIND uses `execution_time` because that's when the state change occurred:

```python
# Transaction created at t0
tx = ledger.create_transaction([...])  # tx.timestamp = t0

# But executed at t2
ledger.advance_time(t2)
ledger.execute(tx)  # tx.execution_time = t2

# clone_at(t1) will not include this transaction
# because execution_time (t2) > target_time (t1)
```

## State Comparison

### ledger_state_equals()

```python
def ledger_state_equals(
    a: Ledger,
    b: Ledger,
    tolerance: float = 1e-9,
    compare_time: bool = False
) -> bool
```

Compares:
1. Registered wallets (must be identical sets)
2. All balances (within tolerance)
3. All unit states (exact equality)
4. Optionally: current_time

### compare_ledger_states()

Returns a detailed diff dict for debugging:

```python
{
    'equal': False,
    'time_a': datetime(...),
    'time_b': datetime(...),
    'time_matches': False,
    'balance_diffs': [('alice', 'USD', 1000.0, 2000.0)],
    'state_diffs': [('OPT', {...}, {...})],
    'missing_wallets_a': [],
    'missing_wallets_b': [],
    'missing_units_a': [],
    'missing_units_b': [],
}
```

## The Checkpoint-and-Verify Pattern

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

This pattern validates that clone_at() correctly reconstructs past state.

## Smart Contracts and LifecycleEngine

### SmartContract Protocol

```python
class SmartContract(Protocol):
    def check_lifecycle(
        self,
        view: LedgerView,
        symbol: str,
        timestamp: datetime,
        prices: Dict[str, float]
    ) -> ContractResult:
        ...
```

Smart contracts are pure functions that read ledger state via LedgerView and return ContractResult objects containing moves and state updates to execute.

### LifecycleEngine

```python
engine = LifecycleEngine(ledger)
engine.register("BILATERAL_OPTION", option_contract)
engine.register("STOCK", stock_contract)

# Step through time
for timestamp in timestamps:
    prices = get_prices(timestamp)
    transactions = engine.step(timestamp, prices)
```

The engine:
1. Advances ledger time to the new timestamp
2. Iterates all units in sorted order (for determinism)
3. Calls the registered contract for each unit type
4. Executes resulting moves and state changes
5. Returns list of executed transactions

## Example Applications

### Options (options.py)

Bilateral call/put options with physical delivery:

```python
unit = create_option_unit(
    symbol="AAPL_C150",
    name="AAPL Call 150",
    underlying="AAPL",
    strike=150.0,
    maturity=datetime(2025, 12, 19),
    option_type="call",
    quantity=100,
    currency="USD",
    long_wallet="alice",
    short_wallet="bob"
)
```

Settlement at maturity:
- **ITM Call**: Long pays strike, receives underlying
- **ITM Put**: Long delivers underlying, receives strike
- **OTM**: Positions close out

### Forwards (forwards.py)

Forward contracts with physical delivery:

```python
unit = create_forward_unit(
    symbol="OIL_FWD_JUN25",
    name="Oil Forward June 2025",
    underlying="OIL",
    forward_price=75.0,
    delivery_date=datetime(2025, 6, 1),
    quantity=1000,
    currency="USD",
    long_wallet="buyer",
    short_wallet="seller"
)
```

At delivery:
- Long pays forward_price * quantity
- Short delivers underlying
- Forward positions close out

### Stocks (stocks.py)

Stocks with dividend scheduling:

```python
schedule = [
    (datetime(2024, 3, 15), 0.25),
    (datetime(2024, 6, 15), 0.25),
    (datetime(2024, 9, 15), 0.25),
    (datetime(2024, 12, 15), 0.25),
]

unit = create_stock_unit(
    symbol="AAPL",
    name="Apple Inc.",
    issuer="treasury",
    currency="USD",
    dividend_schedule=schedule,
    shortable=True
)
```

The dividend schedule is a simple list of (payment_date, dividend_per_share) tuples. The stock_contract automatically processes dividend payments when dates are reached.

### Delta Hedge Strategy (delta_hedge_strategy.py)

Automated delta hedging using Black-Scholes:

```python
unit = create_delta_hedge_unit(
    symbol="AAPL_HEDGE",
    name="AAPL Delta Hedge Strategy",
    underlying="AAPL",
    strike=150.0,
    maturity=datetime(2025, 6, 1),
    volatility=0.20,
    risk_free_rate=0.05,
    num_options=10,
    option_multiplier=100,
    currency="USD",
    strategy_wallet="hedge_fund",
    market_wallet="market"
)
```

The delta_hedge_contract automatically rebalances the underlying position based on Black-Scholes delta calculations at each time step.

## Performance Considerations

### fast_mode

```python
ledger = Ledger("sim", fast_mode=True)
```

Skips validation checks during execution for better Monte Carlo performance. Validation includes wallet/unit registration checks, balance constraints, transfer rules, and timestamp validation. Only use when inputs are trusted.

### no_log

```python
ledger = Ledger("sim", no_log=True)
```

Disables transaction logging. Faster but prevents `clone_at()` and `replay()` functionality. Use for simulations where history is not needed.

### Position Index

The ledger maintains an inverted index of non-zero positions by unit:

```python
positions = ledger.get_positions("AAPL")  # O(1) lookup
# Returns: {"alice": 100, "bob": 50, ...}
```

This enables efficient iteration over holders of a specific unit without scanning all wallets.

## Testing

### Test Files

- `test_reproducibility.py`: Reproducibility guarantees and time-travel
- `test_ledger.py`: Core ledger operations
- `test_engine.py`: LifecycleEngine integration
- `test_options.py`: Option settlement
- `test_forwards.py`: Forward settlement
- `test_stocks.py`: Dividend processing
- `test_delta_hedge.py`: Delta hedging strategy

### Key Test Patterns

The test suite validates:
- UNWIND algorithm correctness via checkpoint-and-verify
- Deterministic execution across clones
- State delta immutability
- Transaction replay with state changes
- Lifecycle engine integration

## Unit State Storage

Units store their state in a `_state` dict that can contain any JSON-serializable data:

```python
unit._state = {
    'underlying': 'AAPL',
    'strike': 150.0,
    'maturity': datetime(2025, 12, 19),
    'option_type': 'call',
    'quantity': 100,
    'currency': 'USD',
    'long_wallet': 'alice',
    'short_wallet': 'bob',
    'settled': False,
}
```

Smart contracts read this state via `view.get_unit_state(symbol)` and can update it by returning state_updates in ContractResult.
