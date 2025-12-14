# Lifecycle and Event System

This document describes the temporal behavior of the Ledger system: how events are scheduled, ordered, executed, and how the system preserves determinism through time.

---

## 1. Time Model

### 1.1 Logical Time

The ledger maintains a **logical clock** that advances only through explicit calls:

```python
ledger = Ledger("demo", initial_time=datetime(2024, 1, 1))

# Time advances only when explicitly commanded
ledger.advance_time(datetime(2024, 1, 2))  # Now ledger.current_time = Jan 2
```

**No implicit time:** The system never calls `datetime.now()`. Time is a parameter, not an observation.

### 1.2 Monotonicity

Logical time is monotonically non-decreasing:

```
∀ t₁, t₂ ∈ timeline: t₁ < t₂ ⟹ state(t₂) is reachable from state(t₁)
```

Attempting to move time backward is either rejected or treated as a no-op.

---

## 2. Event Model

### 2.1 Event Structure

An `Event` is an immutable specification of a scheduled action:

```python
@dataclass(frozen=True, slots=True)
class Event:
    trigger_time: datetime    # When to execute
    priority: int = 0         # Order within same timestamp (lower = first)
    symbol: str = ""          # Affected unit
    action: str = ""          # Event type ("dividend", "coupon", "expiry", etc.)
    params: tuple = ()        # Frozen parameters as (key, value) pairs
```

### 2.2 Event Ordering

Events are ordered lexicographically by:

1. `trigger_time` (earliest first)
2. `priority` (lowest first)
3. `symbol` (alphabetical)

This total ordering ensures deterministic execution across replays.

### 2.3 Event Identity

Each event has a deterministic `event_id`:

```
event_id = f"{action}:{symbol}:{trigger_time.isoformat()}:{params_hash}"
```

This enables:
- **Deduplication**: Prevent double-execution
- **Audit trail**: Track which events fired

---

## 3. Scheduling Model

### 3.1 EventScheduler

The scheduler is a priority queue of pending events:

```python
class EventScheduler:
    _heap: List[Event]          # Min-heap by (time, priority, symbol)
    _handlers: Dict[str, EventHandler]  # action → handler function
    _executed: Set[str]         # Executed event_ids for deduplication
```

### 3.2 Scheduling Events

```python
# Schedule a single event
scheduler.schedule(Event(
    trigger_time=datetime(2024, 3, 15),
    symbol="AAPL",
    action="dividend",
    params=(("amount", "0.25"), ("currency", "USD")),
))

# Schedule multiple events
scheduler.schedule_many([event1, event2, event3])
```

### 3.3 Retrieving Due Events

```python
due_events = scheduler.get_due(as_of=datetime(2024, 3, 15))
```

Returns all events with `trigger_time <= as_of`, in execution order.

---

## 4. Handler Model

### 4.1 Handler Signature

An event handler is a pure function:

```python
EventHandler = Callable[[Event, LedgerView, Dict[str, Decimal]], PendingTransaction]
```

- **Input**: Event specification, read-only ledger view, current prices
- **Output**: `PendingTransaction` describing the required state changes

### 4.2 Built-In Handlers

| Action | Handler | Description |
|--------|---------|-------------|
| `dividend` | `handle_dividend` | Distribute cash to shareholders |
| `coupon` | `handle_coupon` | Pay bond coupon to holders |
| `expiry` | `handle_expiry` | Close expired derivatives |
| `maturity` | `handle_maturity` | Settle bond at maturity |
| `settlement` | `handle_settlement` | Settle deferred cash obligations |
| `split` | `handle_split` | Apply stock split ratio |

### 4.3 Registering Custom Handlers

```python
def custom_handler(event: Event, view: LedgerView,
                   prices: Dict[str, Decimal]) -> PendingTransaction:
    # Pure computation...
    return build_transaction(view, moves=[...])

scheduler.register("custom_action", custom_handler)
```

---

## 5. LifecycleEngine

The `LifecycleEngine` combines scheduled events with smart contract polling:

```
┌──────────────────────────────────────────────────────────────┐
│                     LifecycleEngine.step()                   │
├──────────────────────────────────────────────────────────────┤
│  1. Advance ledger time                                      │
│  2. Process scheduled events (in priority order)             │
│  3. Poll smart contracts for triggered conditions            │
│  4. Repeat until no more events fire (cascading)             │
└──────────────────────────────────────────────────────────────┘
```

### 5.1 Execution Loop

```python
def step(timestamp: datetime, prices: Dict[str, Decimal]) -> List[Transaction]:
    ledger.advance_time(timestamp)
    executed = []

    for pass_num in range(max_passes):  # Safety limit
        pass_executed = []

        # Phase 1: Scheduled events
        for event in scheduler.get_due(timestamp):
            handler = handlers[event.action]
            pending = handler(event, ledger, prices)
            if not pending.is_empty():
                result = ledger.execute(pending)
                if result == ExecuteResult.APPLIED:
                    pass_executed.append(transaction)

        # Phase 2: Smart contract polling
        for unit_type, contract in contracts.items():
            for symbol in units_of_type(unit_type):
                pending = contract.check_lifecycle(ledger, symbol, timestamp, prices)
                if not pending.is_empty():
                    result = ledger.execute(pending)
                    if result == ExecuteResult.APPLIED:
                        pass_executed.append(transaction)

        executed.extend(pass_executed)

        if not pass_executed:
            break  # No events fired; stable state reached

    return executed
```

### 5.2 Cascading Events

Some events trigger other events:
- Bond maturity triggers deferred cash settlement
- Autocall observation may trigger early redemption

The loop continues until a stable state (no events fire).

**Safety limit:** `max_passes = 10` prevents infinite loops from circular triggers.

---

## 6. Smart Contracts

### 6.1 SmartContract Protocol

```python
class SmartContract(Protocol):
    def check_lifecycle(
        self,
        view: LedgerView,
        symbol: str,
        timestamp: datetime,
        prices: Dict[str, Decimal],
    ) -> PendingTransaction:
        """Check if lifecycle events should fire."""
        ...
```

### 6.2 Contract Registration

```python
engine = LifecycleEngine(ledger)
engine.register("BOND", bond_contract)
engine.register("STOCK", stock_contract)
engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract())
```

### 6.3 Polling Semantics

Each `step()`, the engine polls all registered contracts for all units of their type. Contracts return either:
- An empty `PendingTransaction` (no action needed)
- A non-empty `PendingTransaction` (execute this transaction)

---

## 7. Determinism Guarantees

### 7.1 Input Determinism

All inputs to the lifecycle step are explicit:
- `timestamp`: Explicit parameter
- `prices`: Explicit parameter
- `ledger state`: Determined by prior transactions

### 7.2 Ordering Determinism

Event execution order is determined by:
1. Event ordering (time, priority, symbol)
2. Smart contract polling order (alphabetical by unit type, then symbol)

This total ordering ensures identical behavior across replays.

### 7.3 Idempotency

Events track executed `event_id`s. Re-executing the same event produces no effect.

Transactions track `intent_id`. Re-executing the same transaction returns `ALREADY_APPLIED`.

---

## 8. Replay Semantics

Given:
- Initial state `S₀`
- Sequence of `(timestamp, prices)` tuples

Replay produces identical final state:

```python
def replay(S₀, timeline):
    ledger = Ledger.from_state(S₀)
    engine = LifecycleEngine(ledger)

    for timestamp, prices in timeline:
        engine.step(timestamp, prices)

    return ledger.state
```

**Theorem:** `replay(S₀, timeline) = replay(S₀, timeline)` for all valid inputs.

This holds because:
1. All handlers are pure functions
2. All state transitions are deterministic
3. All orderings are total

---

## 9. Alignment with Manifesto

| Principle | Lifecycle Enforcement |
|-----------|----------------------|
| **Environmental Determinism** | Time and prices are parameters, not observations |
| **Functional Purity** | Handlers are pure; side effects in `execute()` only |
| **Transactional Completeness** | Each event produces an atomic transaction |
| **Double-Entry** | All moves in event transactions are balanced |
| **Log as Truth** | Transaction log records all lifecycle events |

---

## 10. Example: Bond Lifecycle

```python
# Create bond with coupon schedule
bond = create_bond_unit(
    symbol="CORP",
    name="Corporate Bond",
    face_value=Decimal("1000"),
    coupon_rate=Decimal("0.05"),
    coupon_frequency=2,  # Semi-annual
    issue_date=datetime(2024, 1, 1),
    maturity_date=datetime(2029, 1, 1),
    issuer="treasury",
    currency="USD",
)
ledger.register_unit(bond)

# Lifecycle engine handles coupons and maturity automatically
engine = LifecycleEngine(ledger)
engine.register("BOND", bond_contract)

# Advance through time
for year in range(2024, 2030):
    for month in [7, 1]:  # July and January coupons
        engine.step(
            datetime(year, month, 1),
            {"CORP": Decimal("1000")}  # Bond price
        )
```

The engine automatically:
1. Pays coupons on schedule
2. Redeems principal at maturity
3. Records all transactions in the log

---

## 11. Summary

The lifecycle system provides:

1. **Explicit time**: Logical clock advances only on command
2. **Ordered events**: Total ordering ensures determinism
3. **Pure handlers**: Event processing is referentially transparent
4. **Cascading support**: Events can trigger other events safely
5. **Full auditability**: Transaction log records all lifecycle activity

These properties ensure that the system's temporal behavior is **predictable**, **reproducible**, and **auditable**.
