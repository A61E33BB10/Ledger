# Ledger

**Version 4.1.0**

A formally-structured financial ledger system with compositional correctness guarantees.

---

## Problem Statement

Financial systems require:

1. **Correctness**: Every balance must be explainable by a finite sequence of atomic transactions.
2. **Auditability**: Any historical state must be reconstructible from the transaction log.
3. **Determinism**: Given identical inputs, execution must produce identical outputs.

Traditional approaches conflate these requirements with implementation complexity. This system separates them by construction.

---

## Core Guarantees

The system provides these guarantees through structural enforcement, not runtime assertion:

| Guarantee | Mechanism |
|-----------|-----------|
| **Double-entry invariant** | `sum(all_balances[unit]) == 0` for all units at all times |
| **Atomicity** | Transactions fully apply or fully reject; no partial states |
| **Referential transparency** | Contract functions are pure: `f(v, x) = f(v, x)` always |
| **Replay determinism** | `replay(log) == original_state` by construction |
| **Decimal precision** | All quantities use `Decimal`; no floating-point accumulation errors |

See [MANIFESTO.md](MANIFESTO.md) for the governing principles.

---

## Architecture Overview

```
                    ┌─────────────────────────────────────────────────┐
                    │                   Ledger                        │
                    │  - balances: Dict[wallet, Dict[unit, Decimal]]  │
                    │  - units: Dict[symbol, Unit]                    │
                    │  - transaction_log: List[Transaction]           │
                    └─────────────────────────────────────────────────┘
                                         │
                         ┌───────────────┼───────────────┐
                         │               │               │
                         ▼               ▼               ▼
              ┌──────────────────┐ ┌──────────┐ ┌─────────────────┐
              │   LedgerView     │ │ execute()│ │ LifecycleEngine │
              │   (read-only)    │ │ (mutate) │ │ (orchestration) │
              └──────────────────┘ └──────────┘ └─────────────────┘
                         │                               │
                         ▼                               ▼
              ┌──────────────────┐            ┌─────────────────────┐
              │  Pure Functions  │            │  Event Scheduler    │
              │  (contracts)     │            │  + Smart Contracts  │
              └──────────────────┘            └─────────────────────┘
```

### Data Flow

1. **Pure functions** receive a `LedgerView` (read-only access) and produce a `PendingTransaction`
2. **`execute()`** validates and atomically applies the transaction, appending to the log
3. **LifecycleEngine** orchestrates scheduled events and contract polling

This separation ensures that all state-reading logic is pure, and all mutation is channeled through a single controlled point.

---

## Intended Users

- **Quantitative developers** building trading systems, risk engines, or portfolio simulations
- **Financial engineers** requiring auditable position tracking with exact arithmetic
- **Researchers** needing deterministic replay for backtesting or Monte Carlo analysis

---

## Usage

```python
from decimal import Decimal
from ledger import Ledger, Move, build_transaction, cash, SYSTEM_WALLET

# Create ledger (test_mode enables set_balance for testing)
ledger = Ledger("demo", test_mode=True)

# Register units and wallets
ledger.register_unit(cash("USD", "US Dollar"))
ledger.register_wallet("alice")
ledger.register_wallet("bob")

# Issue currency from system wallet
tx = build_transaction(ledger, [
    Move(Decimal("1000"), "USD", SYSTEM_WALLET, "alice", "issuance")
])
ledger.execute(tx)

# Transfer between wallets
tx = build_transaction(ledger, [
    Move(Decimal("250"), "USD", "alice", "bob", "payment_001")
])
ledger.execute(tx)

# Verify balances
assert ledger.get_balance("alice", "USD") == Decimal("750")
assert ledger.get_balance("bob", "USD") == Decimal("250")
assert ledger.get_balance(SYSTEM_WALLET, "USD") == Decimal("-1000")

# Double-entry holds: sum of all positions = 0
assert ledger.total_supply("USD") == Decimal("0")
```

---

## Key Types

| Type | Description |
|------|-------------|
| `Move` | Immutable transfer specification: `(quantity, unit, source, dest, contract_id)` |
| `Unit` | Immutable asset definition with balance constraints and optional transfer rules |
| `PendingTransaction` | Intent before execution: moves, state changes, origin metadata |
| `Transaction` | Executed record with ledger-assigned ID and execution timestamp |
| `LedgerView` | Protocol for read-only ledger access (enables pure contract functions) |

All core types are frozen dataclasses (`@dataclass(frozen=True, slots=True)`), ensuring immutability and enabling safe sharing across threads.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [MANIFESTO.md](MANIFESTO.md) | Governing principles and invariants |
| [design.md](design.md) | Formal system design, correctness argument, and preconditions |
| [QIS.md](QIS.md) | Methodology for creating new strategies |
| [lifecycle.md](lifecycle.md) | Event scheduling and temporal behavior |
| [AGENTS.md](AGENTS.md) | Expert agent specifications for code review |
| [TESTING.md](TESTING.md) | Testing committee charter and methodology |
| [EXPERT_REVIEW.md](EXPERT_REVIEW.md) | Formal committee review and remediation status |

---

## Installation

```bash
pip install -e .
```

## Testing

```bash
pytest tests/ -q
```

975 tests verify correctness across all unit types and lifecycle scenarios.

---

## License

Proprietary. All rights reserved.
