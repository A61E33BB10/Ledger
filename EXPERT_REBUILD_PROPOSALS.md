# Expert Committee: Ledger Rebuild Proposals

**Date:** December 2025
**Context:** Four domain experts independently reviewed the Financial Ledger manifesto and current implementation, then proposed how they would rebuild the system from scratch.

---

## Table of Contents

1. [Jane Street CTO - Correctness & Type Safety Focus](#jane-street-cto)
2. [Andrej Karpathy - Radical Simplicity Focus](#andrej-karpathy)
3. [Chris Lattner - Architecture & API Design Focus](#chris-lattner)
4. [FinOps Architect - Financial Domain Focus](#finops-architect)
5. [Synthesis: Common Themes](#synthesis)

---

<a name="jane-street-cto"></a>
## 1. Jane Street CTO Review

### Executive Summary

> The current codebase is fundamentally sound. The manifesto principles are correct and the implementation largely adheres to them. However, there is significant over-engineering in the event scheduling system that violates the YAGNI principle.

**Proposed reduction:** ~12,000 lines → ~4,000 lines (67% reduction)

### What to KEEP

| Component | Verdict | Manifesto Justification |
|-----------|---------|------------------------|
| `Move`, `PendingTransaction`, `Transaction` | KEEP | Correctly immutable with `frozen=True, slots=True` |
| Content-addressable `intent_id` | KEEP | Enforces Principle 4: "Content determines identity" |
| `LedgerView` protocol | KEEP | Enforces Principle 4: "Functional purity" |
| `UnitStateChange` snapshots | KEEP | Enables Principle 1: "The log is truth" |
| `clone_at()` unwind algorithm | KEEP | Correct implementation of time-travel |

### What to REMOVE/SIMPLIFY

#### 1. Event Scheduling System (MAJOR SIMPLIFICATION)

**Current:** 1,118 lines with 31 event types, complex state machine, priority queues
**Proposed:** ~200 lines

```python
# Proposed replacement - events are just data
@dataclass(frozen=True, slots=True)
class ScheduledEvent:
    trigger_time: datetime
    unit_symbol: str
    event_type: str  # Free-form string, not enum
    params: Dict[str, str]

class EventScheduler:
    def schedule(self, event: ScheduledEvent) -> str: ...
    def get_due(self, as_of: datetime) -> list[ScheduledEvent]: ...
    def mark_executed(self, event_id: str) -> None: ...
```

**What was removed:**
- `EventStatus` state machine (7 states)
- `EventPriority` enum (6 levels)
- `EventRecord` wrapper class
- `EventRegistry` with 4 indices
- Supersession tracking
- Retry logic
- 20+ convenience scheduling functions

#### 2. Use Decimal Instead of Float

**Manifesto violation:** "Decimal Precision - Exact decimal arithmetic" but code uses `float`

```python
# Current (WRONG per manifesto):
quantity: float

# Proposed (CORRECT per manifesto):
from decimal import Decimal
quantity: Decimal
```

#### 3. Remove Unused Unit Types

| Module | Lines | Verdict | Reason |
|--------|-------|---------|--------|
| `portfolio_swap.py` | 707 | REMOVE | No tests, speculative |
| `structured_note.py` | 752 | REMOVE | No tests, speculative |
| `autocallable.py` | ~500 | REMOVE | No tests, speculative |

#### 4. Standardize Error Handling with Result Type

```python
@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    value: T | None
    error: str | None

    @staticmethod
    def ok(value: T) -> 'Result[T]': ...
    @staticmethod
    def err(error: str) -> 'Result[T]': ...
```

### Proposed File Structure

```
ledger/
    core.py               # Move, Transaction, Unit, Result, protocols
    ledger.py             # Ledger class (single mutation point)
    events.py             # ScheduledEvent, EventScheduler (~200 lines)
    lifecycle.py          # LifecycleEngine (~150 lines)
    handlers.py           # Event handler functions (~200 lines)
    units/
        stock.py, bond.py, option.py, forward.py,
        future.py, deferred_cash.py, borrow_record.py
```

---

<a name="andrej-karpathy"></a>
## 2. Andrej Karpathy Review

### Executive Summary

> This codebase is **over-engineered by a factor of 5-10x**. It suffers from "enterprise-itis" - the disease where simple problems get wrapped in layers of abstraction until nobody can understand what's actually happening.
>
> The manifesto principles are **sound**. The implementation **violates them**.

**Proposed reduction:** ~40,000 lines → ~6,000 lines (85% reduction)

### The Core Problem

> The manifesto says: "The log is truth" and "Mutations are transactions"
>
> But the implementation has:
> - **1,117 lines** just for event scheduling infrastructure
> - **656 lines** of event handlers that mostly delegate to other functions
> - **553 lines** of "enhanced lifecycle engine"
> - **1,486 lines** for margin loans alone
>
> This is not simplicity. This is **Java masquerading as Python**.

### Radical Rebuild: 3 Files, ~1,500 Lines

#### File 1: `ledger.py` (~500 lines)

```python
"""
ledger.py - Complete double-entry ledger in one file.

Data:
  Move: frozen dataclass (quantity, unit, source, dest, contract_id)
  Transaction: frozen dataclass (moves, state_changes, timestamp, exec_id)
  Unit: simple dataclass (symbol, name, type, state_dict)

State:
  Ledger: balances, units, transaction_log, current_time

Operations:
  execute(moves, state_changes) -> ExecuteResult
  clone_at(timestamp) -> Ledger
"""

@dataclass(frozen=True, slots=True)
class Move:
    quantity: float
    unit: str
    source: str
    dest: str
    contract_id: str

class Ledger:
    def execute(self, moves: List[Move], state_changes=None) -> str:
        # ~50 lines of validation + application
        ...
```

#### File 2: `instruments.py` (~600 lines)

```python
"""
instruments.py - Financial instruments as pure functions.

Each instrument type has:
1. create_*(): Factory returning (unit_config, initial_state)
2. settle_*(): Pure function (state, prices, time) -> (moves, new_state)

No classes. No inheritance. Just data in, data out.
"""

def create_option(symbol, underlying, strike, expiry, is_call,
                  long_wallet, short_wallet, currency) -> dict:
    return {'name': f"{'Call' if is_call else 'Put'} {underlying} {strike}", ...}

def settle_option(symbol, state, spot, now) -> Tuple[List[tuple], dict]:
    # ~30 lines of pure settlement logic
    ...
```

#### File 3: `engine.py` (~400 lines)

```python
"""
engine.py - Run the ledger through time.

One simple loop:
    for each timestamp:
        for each unit:
            (moves, new_state) = settle(unit, state, prices, time)
            if moves:
                ledger.execute(moves, [(unit, new_state)])
"""

SETTLERS = {
    'STOCK': settle_dividends,
    'OPTION': settle_option,
    'FORWARD': settle_forward,
    'BOND': settle_bond,
}

def step(ledger: Ledger, prices: Dict[str, float]) -> int:
    # ~30 lines
    ...
```

### What Gets Deleted

1. **ASCII art in `__repr__`** - use simple f-strings
2. **Frozen dataclasses for state** - use plain dicts
3. **Event scheduling infrastructure** - events are just function calls
4. **Handler class hierarchy** - use a dict of functions
5. **30-value EventType enum** - use strings or 5-value enum
6. **Memory stats** - premature optimization
7. **EventExecutionLog** - the transaction log IS the audit trail

### The Karpathy Test

| Question | Current | Proposed |
|----------|---------|----------|
| Can a newcomer understand in one reading? | No | Yes |
| Is there anything I can delete? | Most of it | Very little |
| Am I solving real or imaginary problems? | Imaginary | Real |
| Would I be embarrassed in a tutorial? | Yes | No |
| Can this be one file instead of many? | 30+ files | 3 files |

---

<a name="chris-lattner"></a>
## 3. Chris Lattner Review

### Executive Summary

> This is a competently built ledger system with solid foundational principles. The manifesto is excellent. However, the implementation has accumulated architectural debt that creates friction for users and maintainers alike.

### Architectural Problems Identified

#### Problem 1: Unit State as Untyped Dictionary

```python
# Current - No schema, no validation
UnitState = Dict[str, Any]
_state={'issuer': issuer, 'currency': currency, ...}
```

**Solution:** The `margin_loan.py` pattern should be universal - typed state dataclasses for every unit type.

#### Problem 2: Two Competing Lifecycle Systems

The codebase has both SmartContract polling AND ScheduledEvents:

```python
def step(self, timestamp, prices):
    scheduled_txs = self._process_scheduled_events(...)  # System 1
    polling_txs = self._process_smart_contracts(...)     # System 2
```

**Problem:** Users must understand both systems, behavior depends on which fires first.

#### Problem 3: Progressive Disclosure Failure

```python
# Current: Flat API surface - 100+ exports, no guidance
from ledger import create_option_unit, compute_option_settlement,
    option_transact, option_contract, get_option_intrinsic_value, ...

# Proposed: Layered API
from ledger import Ledger, Cash, Move  # Level 1: Essential
from ledger.instruments import Option   # Level 2: As needed
from ledger.core import PendingTransaction  # Level 3: Advanced
```

### Proposed Architecture

#### Layer 1: Primitives (no internal dependencies)
```
primitives/
    decimal.py, time.py, money.py, quantity.py, result.py
```

#### Layer 2: Core (depends only on primitives)
```
core/
    wallet.py, move.py, unit.py, transaction.py, view.py, errors.py
```

#### Layer 3: Ledger (depends on core)
```
engine/
    ledger.py, executor.py, log.py, replay.py
```

#### Layer 4: Instruments (depends on core, NOT engine)
```
instruments/
    base.py, registry.py
    cash/, equity/, option/, bond/, forward/
```

#### Layer 5: Lifecycle (depends on instruments)
```
lifecycle/
    event.py, registry.py, handlers.py, engine.py
```

### Typed Instrument Pattern

```python
@dataclass(frozen=True, slots=True)
class OptionTerms:
    """Immutable - set at creation, never changes."""
    underlying: str
    strike: Decimal
    maturity: datetime
    option_type: Literal['call', 'put']
    # Schema versioning for evolution
    @classmethod
    def schema_version(cls) -> int: return 1

@dataclass(frozen=True, slots=True)
class OptionState:
    """Mutable - changes over lifecycle."""
    settled: bool = False
    settlement_price: Decimal | None = None

class OptionInstrument(Instrument[OptionTerms, OptionState]):
    @classmethod
    def settle(cls, view, symbol, price) -> Result[PendingTransaction, Error]:
        # Pure calculation with explicit error handling
        ...
```

### Unified Lifecycle System

```python
@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    event_type: str
    unit_symbol: str
    trigger_time: datetime
    params: dict[str, Any]
    price_dependencies: FrozenSet[str]

class LifecycleHandler(Protocol):
    def handles(self, event_type: str) -> bool: ...
    def validate(self, event, view, prices) -> Result[None, Error]: ...
    def execute(self, event, view, prices) -> Result[PendingTransaction, Error]: ...
```

---

<a name="finops-architect"></a>
## 4. FinOps Architect Review

### Executive Summary

> This is a **well-designed ledger system** that gets the fundamental principles right. However, from a **real trading desk perspective**, there are significant gaps and some over-engineering.

### Critical Domain Issues

#### Issue 1: Settlement Model is Wrong

```
Current Model (Incorrect):
    Trade -> Immediate position change -> DeferredCash for payment

Real World (DVP):
    Trade Date (T): Trade agreed, nothing moves
    Settlement Date (T+1/T+2): Both securities AND cash move atomically
```

**Manifesto Violation:** Principle 5 (Environmental Determinism) - doesn't capture pending settlement state correctly.

#### Issue 2: Float for Money is a Cardinal Sin

```python
# Current - WRONG
Positions = Dict[str, float]
quantity: float

# On a billion-dollar portfolio, floating point errors
# compound to material differences
>>> 0.1 + 0.2
0.30000000000000004
```

#### Issue 3: Missing Financial Concepts

| Missing | Impact |
|---------|--------|
| Trade Status Lifecycle | No pending/confirmed/settled states |
| Netting | No bilateral/multilateral netting |
| Corporate Action Elections | No optional dividends |
| FX | Multi-currency needs CCY units |
| Margin/Collateral | Critical for derivatives |
| P&L Attribution | Realized vs unrealized |
| Lot-level Tracking | Tax lot identification |

#### Issue 4: Bilateral Instruments Overengineered

The `bilateral_transfer_rule` prevents modeling:
- Exchange-traded options (fungible)
- Cleared derivatives

### Proposed Settlement System

```python
class SettlementStatus(Enum):
    PENDING = auto()
    MATCHED = auto()
    SETTLING = auto()
    SETTLED = auto()
    FAILED = auto()

@dataclass
class SettlementObligation:
    obligation_id: str
    trade_date: datetime
    settlement_date: datetime

    # Delivery leg
    deliver_wallet: str
    deliver_symbol: str
    deliver_quantity: Decimal

    # Payment leg
    pay_wallet: str
    pay_symbol: str
    pay_amount: Decimal

    status: SettlementStatus = SettlementStatus.PENDING

    def to_dvp_moves(self) -> List[Move]:
        """Generate atomic DVP moves."""
        return [
            Move(self.deliver_quantity, self.deliver_symbol,
                 self.deliver_wallet, self.pay_wallet, ...),
            Move(self.pay_amount, self.pay_symbol,
                 self.pay_wallet, self.deliver_wallet, ...),
        ]
```

### Minimal Unit Types Needed

| Unit Type | Purpose | Keep/Remove |
|-----------|---------|-------------|
| `CASH` | Fungible currency | KEEP |
| `EQUITY` | Stock position | KEEP |
| `BOND` | Fixed income | KEEP |
| `OPTION_POSITION` | Cleared option | KEEP |
| `BILATERAL_CONTRACT` | OTC derivative | KEEP |
| `OBLIGATION` | Pending settlement | ADD |
| `DEFERRED_CASH` | Payment tracking | REMOVE (use OBLIGATION) |
| `DELTA_HEDGE_STRATEGY` | Trading strategy | REMOVE (not an instrument) |
| `STRUCTURED_NOTE` | Composite | REMOVE (portfolio of others) |

### What to Keep from Current System

1. **`Move`, `Transaction` structure** - just needs Decimal
2. **`black_scholes.py`** - clean, correct formulas
3. **`LedgerView` protocol** - good separation
4. **`verify_double_entry()`** - essential
5. **`clone_at()` / `replay()`** - valuable
6. **Intent ID hashing** - good idempotency
7. **Conservation law tests** - critical

---

<a name="synthesis"></a>
## 5. Synthesis: Common Themes

### Universal Agreement

All four experts agree on these points:

| Issue | Consensus |
|-------|-----------|
| **Manifesto is correct** | The 5 sentences and 8 principles are sound |
| **Float must become Decimal** | Cardinal sin in financial systems |
| **Event system is overbuilt** | 1100+ lines should be ~200 lines |
| **Handler classes should be functions** | Dict of functions, not class hierarchy |
| **Unused unit types should be deleted** | portfolio_swap, structured_note, autocallable |
| **Core ledger logic is sound** | execute(), clone_at(), intent_id hashing |

### Line Count Estimates

| Expert | Current | Proposed | Reduction |
|--------|---------|----------|-----------|
| Jane Street CTO | ~12,000 | ~4,000 | 67% |
| Karpathy | ~40,000 | ~6,000 | 85% |
| Lattner | ~12,000 | ~6,000 | 50% |
| FinOps | ~12,000 | ~5,000 | 58% |

### Priority Actions

#### CRITICAL (All Experts Agree)
1. Replace `float` with `Decimal` everywhere
2. Simplify event scheduler to ~200 lines
3. Delete unused unit types

#### HIGH PRIORITY
4. Add Result type for error handling (Jane Street, Lattner)
5. Implement proper DVP settlement (FinOps)
6. Add typed state dataclasses (Jane Street, Lattner)

#### MEDIUM PRIORITY
7. Progressive disclosure API (Lattner)
8. Unify lifecycle systems (Lattner, Karpathy)
9. Add margin/collateral model (FinOps)

### Divergent Views

| Topic | Jane Street | Karpathy | Lattner | FinOps |
|-------|-------------|----------|---------|--------|
| **File count** | ~15 files | 3 files | ~25 files (layered) | ~15 files |
| **Type safety** | Maximum (NewType, TypedDict) | Minimal (plain dicts) | Protocol-based | Domain types |
| **Abstraction level** | High (Result types) | Low (just functions) | Medium (Protocols) | Domain-driven |

### Final Recommendation

The rebuild should:

1. **Start with Karpathy's simplicity** - prove the core works in minimal code
2. **Add Jane Street's type safety** - Decimal, Result types, frozen dataclasses
3. **Structure with Lattner's layers** - progressive disclosure, clean boundaries
4. **Validate with FinOps domain knowledge** - proper settlement, real trading semantics

The goal: **Minimal correct code** that a newcomer can understand in an afternoon, but that scales to production trading desks.

---

*Generated by Expert Committee Review - December 2025*
