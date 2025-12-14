# System Design

This document presents the formal design of the Ledger system. The argument for correctness proceeds from first principles: we define the core structures, establish their invariants, and demonstrate that correctness follows from compositionality.

---

## 1. Foundational Definitions

### 1.1 The State Space

The ledger state `S` is defined as:

```
S = (B, U, L, t)

where:
  B : Wallet × Symbol → Decimal     (balance function)
  U : Symbol → Unit                  (unit registry)
  L : List[Transaction]              (immutable log)
  t : datetime                       (logical time)
```

### 1.2 The Conservation Law

**Definition (Conservation):** For any state `S` and any unit symbol `u`:

```
∑_{w ∈ Wallets} B(w, u) = 0
```

This is the central invariant. Every unit in circulation has a corresponding liability in the system wallet. Value is neither created nor destroyed, only transferred.

### 1.3 Transitions

State transitions occur only through `execute()`:

```
execute : S × PendingTransaction → S × ExecuteResult
```

No other operation modifies `S`. This is enforced by:
- The `LedgerView` protocol exposes only read methods
- Mutation methods are internal to `Ledger.execute()`
- All dataclasses are frozen (`@dataclass(frozen=True)`)

---

## 2. Core Data Structures

### 2.1 Move

A `Move` is an atomic transfer specification:

```python
@dataclass(frozen=True, slots=True)
class Move:
    quantity: Decimal      # Must be non-zero, finite
    unit_symbol: str       # Must be registered in U
    source: str            # Wallet debited
    dest: str              # Wallet credited
    contract_id: str       # Provenance identifier
```

**Invariant:** For any valid `Move m`:
```
m.quantity ≠ 0 ∧ m.source ≠ m.dest ∧ is_finite(m.quantity)
```

### 2.2 Unit

A `Unit` defines an asset type with constraints:

```python
@dataclass(frozen=True, slots=True)
class Unit:
    symbol: str
    name: str
    unit_type: str
    min_balance: Decimal
    max_balance: Decimal
    decimal_places: Optional[int]
    transfer_rule: Optional[TransferRule]
    _frozen_state: Tuple[Tuple[str, Any], ...]  # Immutable state representation
```

**Key insight:** Unit state is stored as a frozen tuple of key-value pairs. Access via the `state` property returns a fresh dictionary, preventing accidental mutation. State updates create new `Unit` instances.

### 2.3 PendingTransaction

A `PendingTransaction` represents intent before execution:

```python
@dataclass(frozen=True, slots=True)
class PendingTransaction:
    moves: Tuple[Move, ...]
    state_changes: Tuple[UnitStateChange, ...]
    origin: TransactionOrigin
    timestamp: datetime
    units_to_create: Tuple[Unit, ...]
    intent_id: str  # Content-addressable hash
```

**Invariant (Content Identity):** Two `PendingTransaction` instances with identical content have identical `intent_id`. This enables idempotency.

### 2.4 Transaction

A `Transaction` is the executed record:

```python
@dataclass(frozen=True, slots=True)
class Transaction:
    exec_id: str           # Ledger-assigned unique ID
    ledger_name: str       # Which ledger executed this
    execution_time: datetime
    sequence_number: int   # Monotonic ordering
    ... # All PendingTransaction fields
```

---

## 3. The Execution Model

### 3.1 Validation Phase

Before applying a transaction, `execute()` validates:

1. **Unit registration:** All referenced units exist in `U`
2. **Wallet registration:** All referenced wallets exist
3. **Balance constraints:** For each wallet `w` and unit `u`:
   ```
   unit.min_balance ≤ B'(w, u) ≤ unit.max_balance
   ```
   where `B'` is the proposed post-transaction balance
4. **Transfer rules:** Each move satisfies its unit's `transfer_rule` (if defined)
5. **Idempotency:** The `intent_id` has not been previously executed

### 3.2 Application Phase

If validation succeeds:

1. For each `Move(q, u, s, d, _)`:
   ```
   B(s, u) := B(s, u) - q
   B(d, u) := B(d, u) + q
   ```

2. For each `UnitStateChange(u, old, new)`:
   ```
   U(u) := U(u) with state updated to new
   ```

3. Append `Transaction` to `L`

4. Record `intent_id` in seen set

### 3.3 Atomicity

The application phase is all-or-nothing. If any step would violate an invariant, the entire transaction is rejected. The state `S` remains unchanged.

**Proof sketch:** Validation is performed on a computed `net` accumulator without modifying actual balances. Only after all validations pass do we apply changes in a single pass with no observable intermediate states.

---

## 4. Correctness by Construction

### 4.1 Preservation of Conservation

**Theorem:** If conservation holds for state `S`, and `execute(S, tx) = (S', APPLIED)`, then conservation holds for `S'`.

**Proof:** Each `Move(q, u, s, d, _)` in `tx` decrements `B(s, u)` by `q` and increments `B(d, u)` by `q`. The net change is:
```
ΔB(s, u) + ΔB(d, u) = -q + q = 0
```

Since all moves have zero-sum effect, and `S` satisfies conservation, `S'` satisfies conservation. ∎

### 4.2 Referential Transparency of Contracts

Contract functions have the signature:

```python
def contract(view: LedgerView, symbol: str, time: datetime,
             prices: Dict[str, Decimal]) -> PendingTransaction
```

**Property:** A contract function is referentially transparent if:
```
∀ v, s, t, p: contract(v, s, t, p) = contract(v, s, t, p)
```

This holds by construction because:
1. `LedgerView` provides only read methods (no side effects)
2. All inputs are immutable (frozen dataclasses, datetime, Decimal)
3. No global mutable state is accessed
4. All computations use pure arithmetic

### 4.3 Replay Determinism

**Theorem:** Given an initial state `S₀` and log `L = [tx₁, tx₂, ..., txₙ]`, replaying the log produces the same final state.

**Proof:** By induction on `n`:
- Base: `S₀` is deterministic by construction
- Step: `execute(Sₖ, txₖ₊₁)` is deterministic because:
  - Validation is pure (reads only from `Sₖ`)
  - Application is sequential and deterministic
  - No external state is accessed

Since each step is deterministic, the composition is deterministic. ∎

---

## 5. Component Boundaries

### 5.1 Pure Layer (No State Access)

```
┌─────────────────────────────────────────────────────────────┐
│  Pure Functions                                             │
│  - compute_option_settlement(state, prices, time) → moves   │
│  - compute_bond_coupon(state, date) → moves                 │
│  - compute_nav(holdings, cash, prices) → Decimal            │
│                                                             │
│  Inputs: UnitState (dict), prices (dict), time (datetime)   │
│  Outputs: List[Move], UnitStateChange, or scalar values     │
│  Side effects: NONE                                         │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 View Layer (Read-Only State)

```
┌─────────────────────────────────────────────────────────────┐
│  LedgerView Protocol                                        │
│  - get_balance(wallet, unit) → Decimal                      │
│  - get_unit_state(symbol) → Dict (copy)                     │
│  - get_positions(unit) → Dict[wallet, Decimal]              │
│  - current_time → datetime                                  │
│                                                             │
│  Read operations only. Cannot observe any mutation.         │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Mutation Layer (Controlled State Change)

```
┌─────────────────────────────────────────────────────────────┐
│  Ledger.execute(pending: PendingTransaction) → ExecuteResult│
│                                                             │
│  This is the ONLY mutation point.                           │
│  All state changes flow through here.                       │
│  All changes are logged.                                    │
│  All invariants are checked.                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Alignment with Manifesto

| Manifesto Principle | Design Enforcement |
|---------------------|-------------------|
| **State Ownership** | Only `execute()` mutates state |
| **Double-Entry** | Conservation law proved for every transaction |
| **Atomicity** | Validation before application; no intermediate states |
| **Functional Purity** | Contracts receive `LedgerView`, return `PendingTransaction` |
| **Environmental Determinism** | Time, prices are explicit parameters; no `datetime.now()` |
| **Calculation Inputs Capture** | `TransactionOrigin` records provenance |
| **Decimal Precision** | All quantities are `Decimal`; no `float` |
| **Reconciliation** | Log enables audit trail; external data is advisory |

---

## 7. Decomposition Strategy

Complex operations are composed from elementary pure functions:

**Example: Bond Coupon Payment**

```
compute_coupon_entitlements : (positions, coupon_rate) → List[Entitlement]
    ↓
entitlement_to_move : Entitlement → Move
    ↓
create_pending_transaction : List[Move] → PendingTransaction
    ↓
execute : PendingTransaction → Transaction
```

Each function is:
- **Total:** Defined for all valid inputs
- **Pure:** No side effects
- **Testable:** Can be verified in isolation

The composition is correct if each component is correct. This is the essence of compositional verification.

---

## 8. Error Handling

Errors are values, not control flow exceptions in the pure layer:

```python
class ExecuteResult(Enum):
    APPLIED = "applied"           # Success
    ALREADY_APPLIED = "already_applied"  # Idempotent replay
    REJECTED = "rejected"         # Validation failure
```

Validation failures produce `REJECTED` with a reason string. The state is unchanged. The caller decides how to handle the rejection.

---

## 9. Formal Preconditions

The following preconditions must hold for the system guarantees to be valid:

### 9.1 Decimal Context

The Ledger requires a deterministic Decimal arithmetic context. The module configures this at load time (`core.py:30-47`):

```
Precondition: decimal.getcontext() must not be modified by external code
Configuration: prec=50, rounding=ROUND_HALF_EVEN
```

If your application requires different Decimal settings, use `decimal.localcontext()` for those operations. Never modify the global context after importing `ledger.core`.

### 9.2 Threading Model

The Ledger is **single-threaded by design**.

```
Precondition: All operations on a single Ledger instance must execute sequentially
Violation: Concurrent access produces undefined behavior
```

This is intentional. Financial correctness requires deterministic ordering. If concurrency is needed, use:
- Separate Ledger instances per thread
- External synchronization (locks) around Ledger access
- A command queue that serializes operations

### 9.3 Rounding Policy

Move quantities are validated against unit balance constraints, but rounding is applied at the **unit level**, not the move level.

```
Precondition: Move.quantity values should be pre-rounded to match the unit's decimal_places
Responsibility: The caller creating the Move must ensure appropriate precision
```

Each `Unit` defines:
- `decimal_places`: Optional precision constraint (None = unlimited)
- `round()` method: Used during balance calculations

If a Move quantity has more precision than the unit's `decimal_places`, the balance calculation will round, which may cause unexpected validation results near boundaries.

### 9.4 Event Scheduling Semantics

Events scheduled during `step(t)` execute in the **next** call to `step()`, not the current one.

```
step(t) semantics:
  1. get_due(t) retrieves events with trigger_time <= t
  2. Each event handler executes
  3. Handlers may schedule new events (added to heap)
  4. New events are NOT retrieved until next step()
```

This is intentional to prevent infinite loops and ensure deterministic ordering. If you need cascading events within a single timestamp, schedule them with the same `trigger_time` but different `priority` values.

---

## 10. Conclusion

The system achieves correctness through structural enforcement:

1. **Immutability** prevents inadvertent state corruption
2. **Controlled mutation** (single `execute()` point) enables comprehensive validation
3. **Referential transparency** enables compositional reasoning
4. **Content-addressable transactions** enable idempotency
5. **Conservation invariant** holds by construction

These properties are not tested into existence; they follow from the type structure and data flow of the system. A program written in this style is a proof that the invariants hold.
