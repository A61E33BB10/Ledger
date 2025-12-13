# Ledger v4.0 Proposal (Condensed)

**Date:** December 2025
**Status:** APPROVED WITH CHANGES
**Current:** 882 tests passing, examples migrated to SYSTEM_WALLET pattern
**Reviewers:** 4 experts (Jane Street CTO, Karpathy, Lattner, FinOps)

---

## Guiding Principles

1. **Simplify and robustify** - Delete code, don't add complexity
2. **Ship small, ship fast** - Focused releases over grand rewrites
3. **The best code is code that doesn't exist** - YAGNI applies
4. **Security and correctness are non-negotiable** - No silent corruption

---

## Already Completed

- [x] All example files use `build_transaction(ledger, ...)` pattern
- [x] All example files use SYSTEM_WALLET instead of `set_balance()` or `balances[]`
- [x] All example files removed `fast_mode` and `no_log` parameters
- [x] Fixed `get_memory_stats()` - `seen_tx_ids` → `seen_intent_ids`
- [x] Deleted `Ledger.build_transaction()` wrapper
- [x] 882 tests passing

---

## v4.0 Scope: Security & Correctness

**Timeline:** 1-2 days
**Breaking changes:** Yes (intentional)

### 4.0.1 Delete `fast_mode` and `no_log` [CRITICAL]

**File:** `ledger/ledger.py`
**Lines to delete:** ~60 (30+ references)

These flags create silent corruption and audit trail gaps.

```python
# BEFORE (delete all of this)
def __init__(self, name: str, ..., fast_mode: bool = False, no_log: bool = False):
    self.fast_mode = fast_mode
    self.no_log = no_log
    ...
    if not use_fast_mode:
        valid, reason = self._validate_pending(pending)
    ...
    if not self.no_log:
        self.transaction_log.append(tx)

# AFTER
def __init__(self, name: str, initial_time: Optional[datetime] = None, verbose: bool = False):
    # Always validates. Always logs. No exceptions.
```

**Also update:**
- Ledger class docstring (lines 37-81) - remove performance mode documentation
- `clone()` method - remove `fast_mode`/`no_log` copying
- `replay()` method - remove `fast_mode`/`no_log` parameters
- `execute()` method - remove `fast_mode` parameter

### 4.0.2 Deprecate `set_balance()` [CRITICAL]

**File:** `ledger/ledger.py:356-379`

Don't delete immediately - deprecate with warning first (tests use it heavily).

```python
def set_balance(self, wallet: str, unit: str, quantity: float) -> None:
    """DEPRECATED: Use issue()/redeem() for proper audit trail."""
    import warnings
    warnings.warn(
        "set_balance() bypasses double-entry accounting. "
        "Use issue() or redeem() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # ... existing implementation (keep for now) ...
```

**Remove completely in v4.1** after tests are migrated.

### 4.0.3 Auto-Register SYSTEM_WALLET [HIGH]

**File:** `ledger/ledger.py` in `__init__`

```python
def __init__(self, name: str, initial_time: Optional[datetime] = None, verbose: bool = False):
    # ... existing init ...
    self.register_wallet(SYSTEM_WALLET)  # Always available
```

This eliminates the need for `ledger.register_wallet(SYSTEM_WALLET)` in every test/example.

### 4.0.4 DO NOT Add `issue()` / `redeem()` Convenience Methods

**Expert consensus (Karpathy):** The explicit SYSTEM_WALLET pattern is clearer and more educational:

```python
# This is explicit and shows what's happening
tx = build_transaction(ledger, [
    Move(SYSTEM_WALLET, "alice", "USD", 1000.0, "initial_balance")
])
ledger.execute(tx)
```

Adding `issue()`/`redeem()` would:
1. Create two ways to do the same thing
2. Hide what's actually happening
3. Not save meaningful typing

**Decision:** Keep the explicit pattern. Do not add convenience methods.

### 4.0.5 Fix FakeView Non-Determinism [HIGH]

**File:** `tests/fake_view.py:43`

```python
# BEFORE
self._time = time or datetime.now()  # Non-deterministic!

# AFTER
if time is None:
    raise ValueError("FakeView requires explicit time for deterministic tests")
self._time = time
```

**Note:** Grep for `FakeView()` without `time=` to identify affected tests before making this change.

### 4.0.6 Fix Typing Bugs [MEDIUM]

**File:** `ledger/core.py`

```python
# Bug 1: Type mismatch (line ~517)
# BEFORE
contract_ids: FrozenSet[str] = None

# AFTER
contract_ids: FrozenSet[str] = field(default_factory=frozenset)

# Bug 2: UnitStateChange typing (lines 257-258)
# BEFORE
old_state: Any
new_state: Any

# AFTER
old_state: UnitState | None
new_state: UnitState
```

### 4.0.7 Increase Intent ID Hash Length [MEDIUM]

**File:** `ledger/core.py:366`

```python
# BEFORE - 64 bits, birthday collision at ~4B transactions
return hashlib.sha256(content.encode()).hexdigest()[:16]

# AFTER - 128 bits, safe for high-frequency systems
return hashlib.sha256(content.encode()).hexdigest()[:32]
```

### 4.0.8 Update Documentation [HIGH]

Remove all references to deleted features:

- [ ] `ledger/ledger.py` docstring (lines 37-81)
- [ ] `README.md` performance table
- [ ] `DESIGN.md` mode documentation

---

## v4.1 Scope: Financial Precision

**Timeline:** 1 week after v4.0
**Breaking changes:** Yes

### 4.1.1 Remove `set_balance()` Completely

After migrating all tests in v4.0.

### 4.1.2 Decimal Migration [CRITICAL]

Float precision errors are guaranteed on large portfolios.

```python
# BEFORE
quantity: float

# AFTER
from decimal import Decimal, ROUND_HALF_EVEN

quantity: Decimal

# Precision per asset class
PRECISION = {
    'CASH': 2,      # USD, EUR
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

---

## v4.2 Scope: Immutability

**Timeline:** 2 weeks after v4.1

### 4.2.1 Make Unit Frozen [HIGH]

**File:** `ledger/core.py:572-594`

```python
@dataclass(frozen=True, slots=True)
class Unit:
    ...
    _state: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def with_state(self, new_state: Mapping[str, Any]) -> 'Unit':
        """Return new Unit with updated state (functional update)."""
        return Unit(
            symbol=self.symbol,
            name=self.name,
            unit_type=self.unit_type,
            min_balance=self.min_balance,
            max_balance=self.max_balance,
            decimal_places=self.decimal_places,
            transfer_rule=self.transfer_rule,
            _state=MappingProxyType(dict(new_state))
        )
```

### 4.2.2 Return MappingProxyType Instead of Deep Copies

Performance optimization: return read-only views instead of copies.

```python
def get_unit_state(self, symbol: str) -> Mapping[str, Any]:
    unit = self.units.get(symbol)
    if unit and unit._state:
        return unit._state  # Already immutable MappingProxyType
    return MappingProxyType({})
```

### 4.2.3 Fix Type Aliases [HIGH]

**File:** `ledger/core.py:75-79`

```python
# BEFORE
UnitState = Dict[str, Any]
Positions = Dict[str, Dict[str, float]]

# AFTER
UnitState = Mapping[str, Any]
Positions = Mapping[str, Mapping[str, float]]
```

---

## v4.3 Scope: API Improvements

**Timeline:** 1 month after v4.0

### 4.3.1 Replace `verbose` with Standard Logging

```python
import logging
logger = logging.getLogger(__name__)

class Ledger:
    def __init__(self, name: str, initial_time: Optional[datetime] = None):
        # No verbose flag - use standard logging
        ...

    def execute(self, pending: PendingTransaction) -> ExecuteResult:
        ...
        logger.debug("Transaction %s applied", tx.exec_id)
```

### 4.3.2 Improve `build_transaction` Signature

```python
def build_transaction(
    ledger: LedgerView,  # Renamed from 'view'
    moves: Sequence[Move],
    *,  # Force keyword-only after this
    state_updates: Mapping[str, Any] | None = None,
    origin: TransactionOrigin | None = None,
) -> PendingTransaction:
```

### 4.3.3 Reduce Root Exports (115 → ~40)

Add progressive disclosure through documentation:

```python
"""
ledger - Financial Ledger System

Quick Start (most users need only these):
    from ledger import Ledger, Move, build_transaction, cash, SYSTEM_WALLET

Full instrument access:
    from ledger import create_option_unit, option_contract
    from ledger import create_bond_unit, bond_contract
"""
```

---

## NOT in v4.x (Deferred or Rejected)

| Item | Status | Reason |
|------|--------|--------|
| `issue()`/`redeem()` methods | REJECTED | Explicit SYSTEM_WALLET pattern is clearer |
| Futures redesign | DEFERRED | Current 277 lines is functional |
| Pattern application to modules | DEFERRED | Apply when needed |
| Strategy registry | REJECTED | YAGNI - only 1 strategy exists |
| `margin_loan.py` refactor | DEFERRED | Works but verbose (1,486 lines) |
| Settlement status tracking | DEFERRED to v4.3 | Not blocking for v4.0 |
| External reconciliation hooks | DEFERRED to v4.3 | Not blocking for v4.0 |

---

## Migration Checklist

### Before v4.0 Deployment

- [ ] Delete `fast_mode` parameter and all references (~30 locations)
- [ ] Delete `no_log` parameter and all references (~20 locations)
- [ ] Add deprecation warning to `set_balance()`
- [ ] Auto-register SYSTEM_WALLET in `__init__`
- [ ] Fix FakeView non-determinism (check tests first)
- [ ] Fix typing bugs (contract_ids, UnitStateChange)
- [ ] Increase intent_id hash to 32 chars
- [ ] Update Ledger docstring
- [ ] Update README.md
- [ ] Update DESIGN.md
- [ ] Run full test suite: `pytest tests/ -v`

### v4.0 Breaking Changes

| v3.x | v4.0 |
|------|------|
| `Ledger(..., fast_mode=True)` | Remove argument (always validates) |
| `Ledger(..., no_log=True)` | Remove argument (always logs) |
| `ledger.set_balance(w, u, q)` | Deprecated with warning; use SYSTEM_WALLET |
| `FakeView()` | `FakeView(time=datetime(...))` |

---

## Test Updates Required

```python
# Update all tests using fast_mode/no_log
# BEFORE
ledger = Ledger("test", fast_mode=True, no_log=True)

# AFTER
ledger = Ledger("test")
```

Estimated test updates: ~50 call sites for fast_mode/no_log, ~25 for set_balance

---

## Summary

| Version | Scope | Timeline | Key Changes |
|---------|-------|----------|-------------|
| **v4.0** | Security & Correctness | 1-2 days | Delete fast_mode/no_log, deprecate set_balance, auto-register SYSTEM_WALLET |
| **v4.1** | Financial Precision | +1 week | Remove set_balance, Decimal migration |
| **v4.2** | Immutability | +2 weeks | Frozen Unit, MappingProxyType, type aliases |
| **v4.3** | API Improvements | +1 month | Standard logging, better build_transaction, reduced exports |

**v4.0 is the critical release.** It removes dangerous flags and fixes correctness bugs. Ship it first, then iterate.

---

## Expert Sign-Off (Updated December 2025)

| Expert | Verdict | Key Feedback |
|--------|---------|--------------|
| Jane Street CTO | **APPROVED** | Phased approach correct, scope minimal |
| Karpathy | **APPROVED WITH CHANGES** | Do NOT add issue()/redeem() - explicit pattern is clearer |
| Chris Lattner | **APPROVED WITH CHANGES** | Update all documentation, fix verbose→logging in v4.3 |
| FinOps Architect | **APPROVED WITH CHANGES** | Auto-register SYSTEM_WALLET, increase hash length |

### Consolidated Required Changes (All Accepted)

1. ~~Add `issue()`/`redeem()` methods~~ → **REJECTED** (Karpathy: explicit pattern is better)
2. Auto-register SYSTEM_WALLET on Ledger init → **ACCEPTED**
3. Increase intent_id hash from 16 to 32 chars → **ACCEPTED**
4. Deprecate (not delete) `set_balance()` with warning → **ACCEPTED**
5. Update all documentation when deleting features → **ACCEPTED**
6. Replace `verbose` with standard logging → **DEFERRED to v4.3**

---

*This proposal was updated based on expert review after example file migration was completed.*
