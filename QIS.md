# Strategy Methodology

This document defines how to create, validate, and integrate new strategies into the Ledger system without breaking correctness guarantees.

---

## 1. Conceptual Model

### 1.1 What is a Strategy?

A strategy is a **pure function** that computes target holdings given the current state:

```python
Strategy = Callable[[Decimal, Dict[str, Decimal], Dict[str, Any]], Dict[str, Decimal]]
#                    ↑       ↑                    ↑                 ↑
#                    NAV     prices               state             target_holdings
```

The strategy does not execute trades. It returns a **target portfolio**. The system computes the required rebalancing trades to reach that target.

### 1.2 The QIS Framework

A Quantitative Investment Strategy (QIS) wraps a strategy function with:

1. **NAV tracking**: The hypothetical portfolio's net asset value
2. **Self-financing constraint**: Rebalancing preserves NAV
3. **Financing costs**: Cash accrues interest (positive or negative)
4. **Settlement**: Payoff calculation at maturity

**Core equations:**

```
NAV:          V_t = Σ(holdings × prices) + cash
Financing:    cash_{t+dt} = cash_t × e^{r×dt}
Self-finance: NAV_before_rebalance = NAV_after_rebalance
Payoff:       Payoff_T = Notional × (V_T / V_0 - 1)
```

---

## 2. Required Properties

### 2.1 Purity

A strategy function must be **pure**:

```
∀ nav, prices, state: strategy(nav, prices, state) = strategy(nav, prices, state)
```

**Forbidden:**
- Reading global variables
- Calling `datetime.now()`, `random.random()`, or any non-deterministic function
- Network I/O, file I/O, or any external state access
- Mutating any input argument

**Allowed:**
- Mathematical computations using inputs
- Accessing constants defined at module level
- Creating new data structures from inputs

### 2.2 Determinism

Given identical inputs, the strategy must produce identical outputs. This is a consequence of purity, but deserves explicit emphasis:

```
# FORBIDDEN: Non-deterministic behavior
def bad_strategy(nav, prices, state):
    import random
    if random.random() > 0.5:  # ❌ Non-deterministic
        return {"AAPL": nav / prices["AAPL"]}
    return {}

# ALLOWED: Deterministic behavior
def good_strategy(nav, prices, state):
    target_weight = Decimal("0.6")
    return {"AAPL": (nav * target_weight) / prices["AAPL"]}
```

### 2.3 Totality

A strategy must be **total**: defined for all valid inputs within its domain.

```
# FORBIDDEN: Partial function
def partial_strategy(nav, prices, state):
    return {"AAPL": nav / prices["AAPL"]}  # ❌ Fails if "AAPL" not in prices

# ALLOWED: Total function with explicit domain
def total_strategy(nav, prices, state):
    required = {"AAPL", "GOOG"}
    if not required.issubset(prices.keys()):
        raise ValueError(f"Missing required prices: {required - prices.keys()}")
    return {"AAPL": nav / prices["AAPL"]}
```

### 2.4 Decimal Arithmetic

All quantities must use `Decimal`, not `float`:

```python
from decimal import Decimal

# FORBIDDEN
def float_strategy(nav, prices, state):
    return {"AAPL": float(nav) * 0.6 / float(prices["AAPL"])}  # ❌ float

# ALLOWED
def decimal_strategy(nav, prices, state):
    weight = Decimal("0.6")
    return {"AAPL": (nav * weight) / prices["AAPL"]}
```

---

## 3. Strategy Creation Process

### Step 1: Define the Mathematical Model

Write out the strategy as equations:

```
target_weight(asset) = w_i           (constant weights)
target_holdings(asset) = NAV × w_i / price_i
```

### Step 2: Implement as a Pure Function

```python
from decimal import Decimal
from typing import Dict, Any

def fixed_weight_strategy(
    nav: Decimal,
    prices: Dict[str, Decimal],
    state: Dict[str, Any],
) -> Dict[str, Decimal]:
    """
    Fixed-weight strategy: maintain constant portfolio weights.

    Required state keys:
        target_weights: Dict[str, Decimal] mapping asset → weight

    Returns:
        Dict[str, Decimal] mapping asset → target quantity
    """
    weights = state.get("target_weights", {})
    target = {}

    for asset, weight in weights.items():
        if asset not in prices:
            raise ValueError(f"Missing price for {asset}")
        target[asset] = (nav * weight) / prices[asset]

    return target
```

### Step 3: Write Unit Tests

Test the function in isolation, verifying:

1. **Correctness**: Outputs match expected values
2. **Determinism**: Same inputs produce same outputs
3. **Edge cases**: Zero NAV, missing prices, extreme values

```python
def test_fixed_weight_strategy():
    nav = Decimal("1000000")
    prices = {"AAPL": Decimal("150"), "GOOG": Decimal("2500")}
    state = {"target_weights": {"AAPL": Decimal("0.6"), "GOOG": Decimal("0.4")}}

    result = fixed_weight_strategy(nav, prices, state)

    # Verify weights
    assert result["AAPL"] == Decimal("600000") / Decimal("150")  # 4000 shares
    assert result["GOOG"] == Decimal("400000") / Decimal("2500")  # 160 shares

    # Verify determinism
    assert fixed_weight_strategy(nav, prices, state) == result
```

### Step 4: Create the QIS Unit

```python
from ledger import create_qis

qis = create_qis(
    symbol="QIS_FIXED_60_40",
    name="Fixed 60/40 Strategy",
    notional=Decimal("1000000"),
    strategy=fixed_weight_strategy,
    underlying={"AAPL", "GOOG"},
    financing_rate=Decimal("0.02"),
    payer_wallet="investor",
    receiver_wallet="dealer",
    initial_prices={"AAPL": Decimal("150"), "GOOG": Decimal("2500")},
    target_weights={"AAPL": Decimal("0.6"), "GOOG": Decimal("0.4")},
)
```

### Step 5: Register and Test Integration

```python
ledger.register_unit(qis)
ledger.set_balance("investor", "QIS_FIXED_60_40", Decimal("1"))
ledger.set_balance("dealer", "QIS_FIXED_60_40", Decimal("-1"))

# Test rebalancing
result = compute_qis_rebalance(
    view=ledger,
    symbol="QIS_FIXED_60_40",
    prices={"AAPL": Decimal("155"), "GOOG": Decimal("2600")},
    timestamp=datetime.now(),
)
```

---

## 4. Validation Checklist

Before deploying a new strategy:

| Check | Description | How to Verify |
|-------|-------------|---------------|
| **Purity** | No side effects | Code review; no I/O, no globals |
| **Determinism** | Same inputs → same outputs | Run 100× with same inputs |
| **Totality** | No unhandled cases | Test edge cases; analyze domain |
| **Decimal** | No float arithmetic | grep for `float(` in strategy code |
| **Conservation** | Rebalancing preserves NAV | Assert NAV_before = NAV_after |
| **Financing** | Interest accrual is correct | Verify cash changes match formula |

---

## 5. Allowed Practices

| Practice | Reason |
|----------|--------|
| Using `Decimal` for all quantities | Exact arithmetic |
| Reading from `state` dictionary | Explicit parameterization |
| Raising `ValueError` for invalid inputs | Fail-fast on domain violations |
| Computing derived values from inputs | Pure computation |
| Using module-level constants | Immutable, deterministic |

---

## 6. Forbidden Practices

| Practice | Reason | Alternative |
|----------|--------|-------------|
| `datetime.now()` | Non-deterministic | Use timestamp parameter |
| `random.random()` | Non-deterministic | Use seeded RNG from state |
| `float()` | Precision loss | Use `Decimal` |
| Global mutable state | Hidden dependencies | Pass via `state` dict |
| Network/file I/O | Side effects | Pre-fetch data, pass as input |
| Mutating inputs | Violates purity | Return new structures |

---

## 7. Built-In Strategy Examples

### 7.1 Leveraged Strategy

```python
def leveraged_strategy(
    nav: Decimal,
    prices: Dict[str, Decimal],
    state: Dict[str, Any],
) -> Dict[str, Decimal]:
    """
    Constant leverage on a single underlying.

    Required state:
        leverage: Decimal (e.g., 2.0 for 2x)
        underlying: str (e.g., "SPX")
    """
    leverage = state["leverage"]
    underlying = state["underlying"]

    if underlying not in prices:
        raise ValueError(f"Missing price for {underlying}")

    target_exposure = nav * leverage
    target_quantity = target_exposure / prices[underlying]

    return {underlying: target_quantity}
```

### 7.2 Fixed Weight Strategy

See implementation in Step 2 above.

---

## 8. Error Handling

Strategies should fail explicitly rather than silently degrade:

```python
# FORBIDDEN: Silent degradation
def silent_strategy(nav, prices, state):
    weights = state.get("weights", {})  # Silent empty default
    return {a: nav * w / prices.get(a, Decimal("1"))  # Silent price default
            for a, w in weights.items()}

# ALLOWED: Explicit failure
def explicit_strategy(nav, prices, state):
    if "weights" not in state:
        raise ValueError("Strategy requires 'weights' in state")

    weights = state["weights"]
    missing = set(weights.keys()) - set(prices.keys())
    if missing:
        raise ValueError(f"Missing prices for: {missing}")

    return {a: nav * w / prices[a] for a, w in weights.items()}
```

---

## 9. Summary

A correctly implemented strategy:

1. **Is a pure function** with no side effects
2. **Uses Decimal** for all quantities
3. **Is total** over its declared domain
4. **Fails explicitly** when preconditions are violated
5. **Is deterministic** for identical inputs

These properties ensure the strategy can be composed with the Ledger's execution model without breaking conservation, replay, or audit guarantees.
