# QIS Implementation Proposals

Four experts reviewed the QIS (Quantitative Investment Strategy) specification independently. Below are their proposals.

---

## Expert 1: Jane Street CTO Review

### Summary
A QIS is economically a **total return swap on a leveraged virtual portfolio**. The key insight is that the QIS maintains a *hypothetical ledger* that is internal to the QIS unit state - similar to how futures use virtual cash.

### Proposed Data Structures

```python
@dataclass(frozen=True, slots=True)
class QISTerms:
    """Immutable term sheet - set at creation, never changes."""
    symbol: str
    notional: float
    initial_nav: float
    inception_date: datetime
    maturity_date: datetime
    financing_rate_spread: float
    payer_wallet: str
    receiver_wallet: str
    settlement_currency: str
    rebalance_schedule: Tuple[datetime, ...]
    eligible_assets: Tuple[str, ...]
    leverage_limit: Optional[float]
    strategy_id: str

@dataclass(frozen=True, slots=True)
class PortfolioHolding:
    """Single asset position: phi_t^i"""
    asset: str
    quantity: float

@dataclass(frozen=True, slots=True)
class PortfolioState:
    """Complete hypothetical portfolio state."""
    holdings: Tuple[PortfolioHolding, ...]
    cash_balance: float  # C_t - can be negative
    last_rebalance_time: Optional[datetime]
    last_nav: float
    accumulated_financing: float
    rebalance_count: int

@dataclass(frozen=True, slots=True)
class QISState:
    """Complete QIS lifecycle state."""
    portfolio: PortfolioState
    current_nav: float
    inception_nav: float
    terminated: bool
    settlement_history: Tuple[dict, ...]
    final_return: Optional[float]
```

### Strategy Protocol

```python
@runtime_checkable
class QISStrategy(Protocol):
    def compute_holdings(
        self,
        timestamp: datetime,
        current_holdings: Tuple[PortfolioHolding, ...],
        current_cash: float,
        current_nav: float,
        prices: Mapping[str, float],
        external_signals: Optional[Mapping[str, float]] = None,
    ) -> Tuple[PortfolioHolding, ...]:
        """Compute target holdings. Cash computed to maintain self-financing."""
        ...
```

### Pure Calculation Functions

```python
def calculate_nav(holdings, cash_balance, prices) -> NAVCalculationResult
def calculate_financing(cash_balance, rate, days) -> float
def calculate_total_return(nav_terminal, nav_initial) -> float
def calculate_payoff(total_return, notional) -> float
def verify_self_financing(old_holdings, old_cash, new_holdings, new_cash, prices) -> bool
def compute_cash_for_self_financing(target_holdings, nav, prices) -> float
```

### Key Architectural Concerns
1. **Pricing consistency**: All pure functions take prices as explicit input
2. **Self-financing verification**: Called on every rebalance
3. **Leverage constraints**: Validated at rebalance time
4. **State reconstruction**: Uses UnitStateChange with complete snapshots
5. **Negative cash**: Explicitly supported for leveraged positions

---

## Expert 2: FinOps Architect Review

### Summary
QIS fits naturally into existing architecture but requires careful attention to financial precision, financing accrual conventions, and audit trail requirements.

### Financial Precision: Decimal vs Float

**Recommendation**: Use `Decimal` internally, `float` at interface boundary.

```python
from decimal import Decimal, ROUND_HALF_EVEN

CASH_PRECISION = Decimal("0.01")      # 2 decimal places
RATE_PRECISION = Decimal("0.00000001") # 8 decimal places
QTY_PRECISION = Decimal("0.000001")   # 6 decimal places

def round_cash(amount: Decimal) -> Decimal:
    return amount.quantize(CASH_PRECISION, rounding=ROUND_HALF_EVEN)
```

**Rationale**: Float errors compound over 252 trading days. On $1T AUM across 1000 strategies, this creates $250 annual reconciliation errors.

### Financing: Daily Compounding (Industry Standard)

```python
def accrue_financing_daily_compound(cash: Decimal, rate: Decimal, days: int) -> Decimal:
    """Daily compounding: C * (1 + r/365)^days"""
    daily_rate = rate / Decimal("365")
    return cash * (Decimal("1") + daily_rate) ** days
```

**Why not continuous?** Daily compounding is industry standard, deterministic, and creates distinct audit events.

### Self-Financing Constraint Verification

```python
def verify_self_financing(
    old_holdings, old_cash, new_holdings, new_cash, prices, tolerance=Decimal("0.01")
) -> Tuple[bool, Decimal]:
    """Verify NAV unchanged by rebalancing."""
    nav_before = compute_qis_nav(old_holdings, old_cash, prices)
    nav_after = compute_qis_nav(new_holdings, new_cash, prices)
    discrepancy = nav_after - nav_before
    return abs(discrepancy) <= tolerance, discrepancy
```

### Audit Trail Requirements

| Event Type | Required Fields |
|------------|-----------------|
| QIS_INCEPTION | initial_nav, notional, strategy_id |
| QIS_REBALANCE | pre/post holdings, trades, prices, nav_discrepancy |
| QIS_FINANCING | cash_before, cash_after, rate, days |
| QIS_MATURITY | terminal_nav, total_return, settlement_amount |

### Edge Cases

1. **Negative NAV**: Log event, continue tracking, consider termination trigger
2. **Extreme leverage**: Validate against `MAX_LEVERAGE` at rebalance
3. **Corporate actions**: Stock splits multiply quantity, dividends add cash or reinvest

```python
def apply_stock_split(holdings: Dict, symbol: str, ratio: Decimal) -> Dict:
    """Self-financing preserved: qty increases, price decreases proportionally."""
    new_holdings = dict(holdings)
    new_holdings[symbol] = holdings[symbol] * ratio
    return new_holdings
```

---

## Expert 3: Chris Lattner Review (API Design)

### Summary
Focus on **progressive disclosure of complexity**. Simple strategies should be simple to define. The Strategy Protocol is the key abstraction.

### The Strategy Protocol (Progressive Disclosure)

```python
@dataclass(frozen=True)
class InformationSet:
    """All information available to strategy at time t_k."""
    timestamp: datetime
    prices: Dict[str, float]
    current_holdings: PortfolioState
    current_cash: float
    nav: float
    financing_rate: float
    historical_prices: Optional[Dict[str, List[float]]] = None
    custom_data: Optional[Dict[str, Any]] = None

@dataclass(frozen=True)
class RebalanceDecision:
    """Strategy output: target holdings."""
    target_holdings: Dict[str, float]
    metadata: Optional[Dict[str, Any]] = None

@runtime_checkable
class Strategy(Protocol):
    @property
    def name(self) -> str: ...

    def rebalance(self, info: InformationSet) -> RebalanceDecision: ...
```

### Simple Strategy: Fixed Weights (~25 lines)

```python
@dataclass
class FixedWeightStrategy(BaseStrategy):
    weights: Dict[str, float]  # Must sum to 1.0

    @property
    def name(self) -> str:
        return "FixedWeight"

    def rebalance(self, info: InformationSet) -> RebalanceDecision:
        target_holdings = {}
        for symbol, weight in self.weights.items():
            price = info.prices.get(symbol, 0)
            if price > 0:
                target_holdings[symbol] = (weight * info.nav) / price
        return RebalanceDecision(target_holdings=target_holdings)
```

### Strategy Combinator: Leverage Wrapper

```python
@dataclass
class LeveragedStrategy(BaseStrategy):
    base_strategy: BaseStrategy
    leverage: float = 2.0

    def rebalance(self, info: InformationSet) -> RebalanceDecision:
        base = self.base_strategy.rebalance(info)
        return RebalanceDecision(
            target_holdings={s: q * self.leverage for s, q in base.target_holdings.items()},
            metadata={'leverage': self.leverage, 'base': self.base_strategy.name}
        )
```

### Design Principles

1. **Library over Language**: Strategy protocol is just Python - no magic
2. **Progressive Disclosure**: Simple case = implement `rebalance()`. Advanced = add validation, historical data
3. **Meet users where they are**: Interface looks like every backtesting framework's signal generator

### Long-Term Evolution Path

- **Phase 1**: Strategy protocol, basic implementations, lifecycle integration
- **Phase 2**: Strategy combinators (leveraged, hedged, blended)
- **Phase 3**: Multi-currency, path-dependent strategies, backtesting integration
- **Phase 4**: Strategy versioning, real-time NAV streaming, performance attribution

---

## Expert 4: Karpathy Review (Radical Simplicity)

### Summary
QIS is just **Portfolio Swap + Strategy Function**. The complexity is in the mathematics, not the software. One file, ~250-300 lines.

### Key Insight

```
QIS = NAV tracking + Self-financing rebalancing + Financing costs + Settlement
```

All of this already exists in `portfolio_swap.py`. The only new thing is the **strategy function**.

### The Simplest Possible Strategy Type

```python
# A strategy is just a function
Strategy = Callable[[float, float, dict], float]  # (nav, price, state) -> target_holdings
```

### 2x Leveraged SPX in 10 Lines

```python
def leveraged_2x(nav: float, price: float, state: dict) -> float:
    """Target holdings for 2x leveraged exposure."""
    return (2.0 * nav) / price

qis = create_qis(
    symbol="QIS_2X_SPX",
    underlying="SPX",
    notional=1_000_000,
    strategy=leveraged_2x,
    funding_rate=0.05,
    rebalance_schedule=monthly_dates,
    payer_wallet="dealer",
    receiver_wallet="investor",
)
```

### Core Pure Functions (~100 lines total)

```python
def compute_nav(holdings: float, price: float, cash: float) -> float:
    """V_t = phi_t * P_t + C_t"""
    return holdings * price + cash

def accrue_financing(cash: float, rate: float, days: int) -> float:
    """C_{t+dt} = C_t * e^{r*dt}"""
    return cash * (1 + rate * days / 365)

def compute_rebalance(nav, price, current_holdings, current_cash, strategy, state):
    """Self-financing: NAV before = NAV after."""
    target = strategy(nav, price, state)
    delta = target - current_holdings
    new_cash = current_cash - delta * price
    assert abs(compute_nav(target, price, new_cash) - nav) < 1e-9
    return target, new_cash

def compute_qis_payoff(final_nav, initial_nav, notional) -> float:
    """Payoff_T = N * (V_T / V_0 - 1)"""
    return notional * (final_nav / initial_nav - 1)
```

### What NOT to Do

1. NOT create a separate "hypothetical ledger" class
2. NOT create complex strategy hierarchies
3. NOT add abstract base classes
4. NOT separate portfolio state from swap state
5. NOT create Strategy registry or factory patterns

### File Structure

```
ledger/units/qis.py      # ~250-300 lines, ONE file
tests/unit/test_qis.py   # ~200 lines
```

---

## Comparison Summary

| Aspect | Jane Street | FinOps | Lattner | Karpathy |
|--------|-------------|--------|---------|----------|
| **Focus** | Correctness & type safety | Financial precision | API design & evolution | Radical simplicity |
| **Numeric type** | float (with epsilon) | Decimal internally | float | float |
| **Strategy type** | Protocol with frozen dataclass | Protocol | Protocol + BaseStrategy | Simple Callable |
| **Financing** | Continuous | Daily compound | Configurable | Linear approx |
| **Files** | 1 large file | 1 file + tests | strategies/ directory | 1 file |
| **Lines estimate** | ~600 | ~500 | ~400 + strategies | ~250-300 |
| **Abstractions** | Full frozen dataclasses | Decimal wrappers | Progressive disclosure | Minimal |

---

## Recommended Synthesis

Based on all four reviews, the recommended approach:

1. **Start with Karpathy's minimal implementation** (~300 lines) as the foundation
2. **Use Lattner's Strategy Protocol** for extensibility without complexity
3. **Add FinOps precision guards** (tolerance checks, audit events) for financial correctness
4. **Follow Jane Street's state design** with frozen dataclasses for the QIS terms

### Minimal Viable Implementation

```python
# ledger/units/qis.py

UNIT_TYPE_QIS = "QIS"

# Strategy: just a callable
Strategy = Callable[[float, Dict[str, float], dict], Dict[str, float]]

# Core functions
def compute_nav(holdings, cash, prices) -> float
def accrue_financing(cash, rate, days) -> float
def compute_rebalance(nav, holdings, cash, strategy, prices, state) -> Tuple[Dict, float]
def verify_self_financing(nav_before, nav_after, tolerance=0.01) -> bool

# Unit creation
def create_qis(...) -> Unit

# Lifecycle
def compute_qis_rebalance(view, symbol, strategy, prices, days) -> PendingTransaction
def compute_qis_settlement(view, symbol, prices) -> PendingTransaction

# SmartContract
def qis_contract(strategy_registry) -> Callable
```

**Total: ~300-400 lines in one file.**
