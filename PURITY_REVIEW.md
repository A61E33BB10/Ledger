# Pure Function and Immutability Review

**Date:** December 2025 (Updated for v3.1)
**Reviewers:** 7 Specialized Agents
**Status:** MARGIN_LOAN REFACTORED - Pattern Established

---

## Executive Summary

Seven specialized agents performed a comprehensive review of the codebase's adherence to **pure function** and **immutability** principles. The initial findings identified significant violations:

| Metric | Before v3.1 | After v3.1 |
|--------|-------------|------------|
| Total `compute_*` functions reviewed | 21 | 21 |
| Functions with hidden state dependencies | 17 (81%) | **9 (43%)** |
| Truly pure functions | 4 (19%) | **12 (57%)** |
| Critical immutability violations | 2 | 2 (documented) |
| Modules refactored | 0 | **1 (margin_loan.py)** |

**Status:** The `margin_loan.py` module has been fully refactored to the pure function pattern. This serves as the template for remaining modules.

---

## The Pattern (Implemented in v3.1)

### Frozen Dataclasses

```python
@dataclass(frozen=True, slots=True)
class MarginLoanTerms:
    """Immutable term sheet - set at creation, never changes."""
    interest_rate: float
    initial_margin: float
    maintenance_margin: float
    haircuts: Mapping[str, float]
    margin_call_deadline_days: int
    currency: str
    borrower_wallet: str
    lender_wallet: str

@dataclass(frozen=True, slots=True)
class MarginLoanState:
    """Immutable snapshot of lifecycle state at a point in time."""
    loan_amount: float
    collateral: Mapping[str, float]
    accrued_interest: float
    last_accrual_date: Optional[datetime]
    margin_call_amount: float
    margin_call_deadline: Optional[datetime]
    liquidated: bool
    # ... more fields

@dataclass(frozen=True, slots=True)
class MarginStatusResult:
    """Immutable result of margin status calculation."""
    collateral_value: float
    total_debt: float
    margin_ratio: float
    status: str
    # ... more fields
```

### Pure Calculation Functions

```python
def calculate_collateral_value(
    collateral: Mapping[str, float],
    prices: Mapping[str, float],
    haircuts: Mapping[str, float],
) -> float:
    """PURE FUNCTION - All inputs explicit, no hidden state."""
    total_value = 0.0
    for asset, quantity in collateral.items():
        price = prices.get(asset, 0.0)
        haircut = haircuts.get(asset, 0.0)
        total_value += quantity * price * haircut
    return total_value

def calculate_margin_status(
    terms: MarginLoanTerms,
    state: MarginLoanState,
    prices: Mapping[str, float],
    current_time: Optional[datetime],
) -> MarginStatusResult:
    """PURE FUNCTION - All inputs explicit, no LedgerView."""
    # ... calculation using typed inputs
```

### Adapter Functions

```python
def load_margin_loan(view: LedgerView, symbol: str) -> Tuple[MarginLoanTerms, MarginLoanState]:
    """Load a margin loan from ledger state as typed frozen dataclasses."""

def to_state_dict(terms: MarginLoanTerms, state: MarginLoanState) -> Dict[str, Any]:
    """Convert typed dataclasses back to state dict for ledger storage."""
```

---

## Module Status

### COMPLETED: margin_loan.py

| Function | Status | Pure Function |
|----------|--------|---------------|
| `compute_collateral_value()` | REFACTORED | `calculate_collateral_value()` |
| `compute_margin_status()` | REFACTORED | `calculate_margin_status()` |
| `compute_add_collateral()` | REFACTORED | Uses `calculate_collateral_value()` |
| `compute_interest_accrual()` | REFACTORED | `calculate_interest_accrual()` |
| `compute_margin_call()` | REFACTORED | Uses `calculate_margin_status()` |
| `compute_margin_cure()` | REFACTORED | Uses `calculate_collateral_value()` |
| `compute_liquidation()` | REFACTORED | Uses `calculate_margin_status()` |
| `compute_repayment()` | REFACTORED | Uses `calculate_pending_interest()` |

**Agent Verdicts (v3.1):**
| Agent | Verdict |
|-------|---------|
| Jane Street CTO | APPROVE |
| FinOps Architect | APPROVE |
| Karpathy | APPROVE WITH RECOMMENDATIONS (implemented) |

### PENDING: Other Modules

| Module | Priority | Hidden Dependencies | Status |
|--------|----------|---------------------|--------|
| autocallable.py | HIGH | 14+ | Pending |
| bond.py | MEDIUM | 3 | Pending |
| future.py | MEDIUM | 4 | Pending |
| portfolio_swap.py | LOW | 2 (already has 2 pure) | Pending |
| structured_note.py | LOW | 2 (already has 2 pure) | Pending |

---

## What's Now Possible (v3.1)

### Stress Testing Without State Mutation

```python
from ledger import (
    calculate_collateral_value,
    calculate_margin_status,
    load_margin_loan,
)

# Load once
terms, state = load_margin_loan(view, "LOAN_001")

# Test multiple price scenarios
for scenario_name, stressed_prices in scenarios.items():
    result = calculate_margin_status(terms, state, stressed_prices, now)
    print(f"{scenario_name}: ratio={result.margin_ratio}, status={result.status}")

# Test different haircuts
conservative_terms = MarginLoanTerms(
    **{**terms.__dict__, 'haircuts': {k: v * 0.9 for k, v in terms.haircuts.items()}}
)
stressed_result = calculate_margin_status(conservative_terms, state, prices, now)
```

### Parallel Scenario Analysis

```python
from concurrent.futures import ThreadPoolExecutor

def run_scenario(scenario):
    prices, haircuts = scenario
    terms_adj = MarginLoanTerms(**{**terms.__dict__, 'haircuts': haircuts})
    return calculate_margin_status(terms_adj, state, prices, now)

# Safe because dataclasses are frozen
with ThreadPoolExecutor() as executor:
    results = list(executor.map(run_scenario, scenarios))
```

### Testing Without Mocks

```python
def test_margin_breach_detection():
    terms = MarginLoanTerms(
        interest_rate=0.05,
        initial_margin=1.5,
        maintenance_margin=1.25,
        haircuts={'AAPL': 0.7},
        margin_call_deadline_days=3,
        currency='USD',
        borrower_wallet='borrower',
        lender_wallet='lender',
    )
    state = MarginLoanState(
        loan_amount=100000,
        collateral={'AAPL': 1000},
        accrued_interest=0,
        # ...
    )
    prices = {'AAPL': 140.0}  # Below maintenance

    result = calculate_margin_status(terms, state, prices, None)

    assert result.status == MARGIN_STATUS_BREACH
    assert result.margin_ratio < 1.25
```

---

## Remaining Immutability Issues (Documented)

These are accepted design tradeoffs, documented for transparency:

| Issue | Location | Status | Mitigation |
|-------|----------|--------|------------|
| `Unit` not frozen | core.py:351-373 | Accepted | Deep copy in `get_unit_state()` |
| `ContractResult.state_updates` mutable | core.py:266-267 | Accepted | Convention-based immutability |
| `Move.metadata` mutable | core.py | Accepted | Convention-based immutability |

---

## Recommended Next Steps

### To Apply Pattern to Other Modules

1. **autocallable.py** - Create `AutocallableTerms`, `AutocallableState`, pure `calculate_observation()`
2. **bond.py** - Create `BondTerms`, `BondState`, pure `calculate_accrued_interest()`
3. **future.py** - Create `FutureTerms`, `FutureState`, pure `calculate_margin()`

### Template

For each module:
1. Define frozen `{Instrument}Terms` dataclass for immutable contract parameters
2. Define frozen `{Instrument}State` dataclass for lifecycle state
3. Extract `calculate_*` pure functions with explicit parameters
4. Add `load_{instrument}()` and `to_state_dict()` adapters
5. Update `compute_*` functions to delegate to pure functions
6. Export new types and functions in `__init__.py`

---

## Summary

**v3.1 establishes the pure function pattern for financial calculations.**

The `margin_loan.py` refactoring demonstrates:
- Frozen dataclasses for type safety and immutability
- Pure functions with explicit parameters for testability
- Adapter functions for LedgerView integration
- Full backward compatibility with existing `compute_*` API

This pattern should be applied to remaining modules as priorities dictate.
