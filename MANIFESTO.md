# Financial Ledger Architecture: Foundational Principles

**Status:** ADOPTED (December 2025)
**Expert Sign-Off:** Jane Street CTO, Karpathy, Lattner, FinOps Architect

---

## Core Philosophy (5 Sentences)

1. **The log is truth** - The transaction log is the sole source of truth; all state is a derived, rebuildable cache.
2. **Mutations are transactions** - Only `execute()` mutates state; everything else is a pure function of `LedgerView`.
3. **Double-entry is mandatory** - Every movement has equal and opposite entries; the sum of all positions is always zero.
4. **Content determines identity** - Transaction IDs are deterministic hashes of content, enabling idempotency and deduplication.
5. **Environment is explicit** - All external inputs (time, prices, random seeds) are captured and replayable.

---

## Principle 1: State Ownership

**The Ledger owns all financial state. Period.**

All balance modifications MUST flow through the Ledger's transaction mechanism. No external system may directly manipulate balances, positions, or unit state.

```python
# CORRECT: State changes through transactions
tx = build_transaction(ledger, [
    Move(SYSTEM_WALLET, "alice", "USD", 1000.0, "issuance")
])
ledger.execute(tx)

# WRONG: Direct state manipulation (forbidden)
ledger.balances["alice"]["USD"] = 1000.0  # Never do this
```

**Invariant:** `sum(all_balances[unit]) == 0` for every unit at all times.

---

## Principle 2: Double-Entry Enforcement

**Every movement has an equal and opposite entry.**

The system enforces double-entry accounting at the transaction level. Money cannot appear from nowhere or disappear into nothing.

```python
# Issuance: SYSTEM_WALLET goes negative, recipient goes positive
Move(SYSTEM_WALLET, "alice", "USD", 1000.0, "issue")  # Net change: 0

# Transfer: Source decreases, destination increases
Move("alice", "bob", "USD", 500.0, "transfer")  # Net change: 0

# Redemption: Holder returns to SYSTEM_WALLET
Move("alice", SYSTEM_WALLET, "USD", 200.0, "redeem")  # Net change: 0
```

**Invariant:** For any transaction, `sum(debits) == sum(credits)`.

---

## Principle 3: Transactional Completeness

**A transaction either fully succeeds or fully fails.**

Multi-leg operations (trades, settlements, corporate actions) execute atomically. Partial application is impossible.

```python
# Atomic trade: both legs succeed or neither does
tx = build_transaction(ledger, [
    Move("alice", "bob", "USD", 50_000.0, "payment"),
    Move("bob", "alice", "AAPL", 100.0, "delivery"),
])
result = ledger.execute(tx)  # All-or-nothing
```

**Invariant:** The system is never in an inconsistent intermediate state.

---

## Principle 4: Functional Purity

**Contract logic is pure. Side effects live in `execute()`.**

Contract functions (`option_contract`, `bond_contract`, etc.) are pure functions that take a `LedgerView` and return a `ContractResult`. They cannot mutate state directly.

```python
# Pure function: reads view, returns instructions
def option_contract(view: LedgerView, symbol: str,
                   eval_time: datetime, prices: Dict[str, float]) -> ContractResult:
    state = view.get_unit_state(symbol)
    # ... pure computation ...
    return ContractResult(moves=[...], state_updates={...})

# Impure execution: Ledger applies the result
result = option_contract(ledger, "AAPL-CALL-150", now, {"AAPL": 155.0})
ledger.execute_contract(result)  # Only place where mutation happens
```

**Invariant:** Given the same `LedgerView` and inputs, a contract function always returns the same result.

---

## Principle 5: Environmental Determinism

**All external inputs are captured and replayable.**

Time, market prices, random seeds - everything needed to reproduce a calculation must be explicitly provided and logged.

```python
# Time is explicit, not implicit
ledger = Ledger("demo", initial_time=datetime(2024, 1, 1))
ledger.advance_time(datetime(2024, 1, 2))  # Explicit advancement

# Prices are parameters, not fetched
result = option_contract(ledger, symbol, eval_time, prices={"AAPL": 150.0})

# Random seeds are captured for reproducibility
tx = build_transaction(ledger, moves, origin=TransactionOrigin(
    random_seed=42,  # Captured for replay
))
```

**Invariant:** `replay(log)` produces identical state to the original execution.

---

## Principle 6: Calculation Inputs Capture

**Every derived value records its inputs.**

When computing P&L, Greeks, valuations, or any derived metric, capture the inputs that produced it. This enables audit, debugging, and regulatory compliance.

```python
# Valuation captures its inputs
valuation = ValueResult(
    value=Decimal("1523.45"),
    inputs={
        "spot_price": Decimal("150.25"),
        "volatility": Decimal("0.22"),
        "risk_free_rate": Decimal("0.05"),
        "time_to_expiry": Decimal("0.25"),
    },
    model="black_scholes",
    timestamp=datetime(2024, 1, 15, 16, 0, 0),
)
```

**Invariant:** Any calculated value can be independently verified from its captured inputs.

---

## Principle 7: Decimal Precision

**Financial calculations use exact decimal arithmetic.**

Floating-point errors compound in large portfolios. Use `Decimal` with explicit precision and rounding modes per context.

```python
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_DOWN, ROUND_UP

# Precision per asset class
PRECISION = {
    'CASH': 2,      # USD, EUR - cents
    'STOCK': 6,     # Fractional shares
    'CRYPTO': 8,    # BTC, ETH
    'RATE': 8,      # Interest rates
}

# Rounding mode per context
ROUNDING_MODE = {
    'CASH': ROUND_HALF_EVEN,    # Banker's rounding - unbiased
    'STOCK': ROUND_DOWN,        # Never create shares from rounding
    'FEES': ROUND_UP,           # Fees always round against customer
}
```

**Invariant:** No precision loss in financial calculations.

---

## Principle 8: Reconciliation

**External systems are reconciled, not trusted.**

When interacting with external systems (banks, custodians, exchanges), the ledger maintains its own truth. External data is reconciled, and breaks are surfaced.

```python
# Internal position (truth)
internal = ledger.get_balance("custody_account", "AAPL")

# External position (from custodian)
external = custodian.get_position("AAPL")

# Reconciliation (surfaces breaks)
if internal != external:
    record_reconciliation_break(
        account="custody_account",
        unit="AAPL",
        internal=internal,
        external=external,
        timestamp=now,
    )
```

**Invariant:** The ledger is the book of record; external systems are advisory.

---

## Optional Persistence

The in-memory ledger can optionally persist to durable storage for crash recovery:

```python
# Option 1: JSON export/import
ledger.export_log("transactions.json")
restored = Ledger.from_log("transactions.json")

# Option 2: WAL backend (future)
ledger = Ledger("demo", wal_path="/var/lib/ledger/demo.wal")

# Option 3: Database backend (future)
ledger = Ledger("demo", backend=PostgresBackend(connection_string))
```

The persistence layer is an implementation detail. The principles above hold regardless of storage backend.

---

## What These Principles Enable

1. **Complete Audit Trail** - Every balance can be explained by walking the log
2. **Deterministic Replay** - Any historical state can be reconstructed
3. **Fearless Refactoring** - Pure functions are easy to test and change
4. **Regulatory Compliance** - Full traceability for regulators
5. **Debugging** - Reproduce any bug with captured inputs
6. **Parallelization** - Pure contract logic can run concurrently (read-only)

---

## What These Principles Forbid

1. **Direct balance manipulation** - Everything through transactions
2. **Implicit time** - No `datetime.now()` in contract logic
3. **Hidden state** - No mutable globals or singletons
4. **Partial transactions** - No half-executed multi-leg operations
5. **Silent failures** - Validation failures are explicit rejections
6. **Floating-point money** - Decimal arithmetic only

---

## Expert Amendments Incorporated

| Expert | Amendment | Status |
|--------|-----------|--------|
| Jane Street CTO | Add Error Correction principle | Covered by Reconciliation |
| Karpathy | Remove database jargon, simplify | Done - WAL is optional |
| Lattner | Calculation Inputs Capture | Added as Principle 6 |
| FinOps | Double-Entry Enforcement | Added as Principle 2 |
| FinOps | Decimal Precision | Added as Principle 7 |
| FinOps | Reconciliation | Added as Principle 8 |

---

*These principles guide the development of the Ledger system. All new features and changes should be evaluated against them.*
