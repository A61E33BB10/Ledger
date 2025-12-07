# Ledger

A Python double-entry accounting system for financial simulations, portfolio management, and backtesting.

## What is the Ledger?

The Ledger is a high-performance financial simulation system that serves as the golden source of truth for ownership records. It separates quantities from values: the ledger tracks who owns what, while external systems handle pricing and valuation. Built on immutable data structures and pure functions, it provides complete audit trails, deterministic execution, and time-travel capabilities for reconstructing any past state.

**Key Features:**
- **Immutable transactions** - Double-entry bookkeeping with atomic moves between wallets
- **Pure functions** - All business logic reads state via LedgerView and returns ContractResult
- **Conservation laws** - Total supply of any unit remains constant across all wallets
- **Time travel** - Reconstruct ledger state at any point in history via `clone_at()`
- **Dual-mode execution** - Full audit trail for production, high-throughput for Monte Carlo (150k+ tx/sec)

**Target Use Cases:**
- Monte Carlo simulations for derivatives and portfolio strategies
- Backtesting trading strategies with complete audit trails
- Educational tool for understanding financial instruments
- Simulation environment for complex structured products

## Quick Start

### Installation

```bash
pip install -e .
```

### Basic Usage

```python
from ledger import Ledger, cash, Move
from datetime import datetime

# Create ledger and register units
ledger = Ledger("simulation")
ledger.register_unit(cash("USD", "US Dollar"))

# Register wallets
ledger.register_wallet("alice")
ledger.register_wallet("bob")

# Set initial balances
ledger.set_balance("alice", "USD", 10000.0)
ledger.set_balance("bob", "USD", 5000.0)

# Transfer funds
moves = [Move("alice", "bob", "USD", 100.0, "payment_1")]
tx = ledger.create_transaction(moves)
ledger.execute(tx)

# Check balances
print(f"Alice: ${ledger.get_balance('alice', 'USD')}")  # 9900.0
print(f"Bob: ${ledger.get_balance('bob', 'USD')}")      # 5100.0
```

### Working with Financial Instruments

```python
from ledger import create_stock_unit, create_option_unit, LifecycleEngine
from datetime import datetime

# Create a stock with dividends
stock = create_stock_unit(
    symbol="AAPL",
    name="Apple Inc.",
    issuer="treasury",
    currency="USD",
    dividend_schedule=[
        (datetime(2025, 3, 15), 0.25),
        (datetime(2025, 6, 15), 0.25),
    ]
)
ledger.register_unit(stock)

# Create an option
option = create_option_unit(
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
ledger.register_unit(option)

# Use lifecycle engine to process automated events
engine = LifecycleEngine(ledger)
engine.register("STOCK", stock_contract)
engine.register("BILATERAL_OPTION", option_contract)

# Step through time with market prices
prices = {"AAPL": 155.0}
engine.step(datetime(2025, 12, 19), prices)
```

## Supported Instruments

The Ledger provides implementations for a comprehensive set of financial instruments:

- **Cash & Stock** - Simple currency units and equities with dividend scheduling
- **Options** - Bilateral call/put options with physical delivery at maturity
- **Forwards** - Forward contracts with delivery obligations
- **Futures** - Exchange-traded futures using virtual ledger pattern for daily settlement
- **Bonds** - Fixed income with coupon payments, accrued interest, and day count conventions
- **Deferred Cash** - T+n settlement obligations for realistic trade settlement
- **Margin Loans** - Collateralized lending with margin calls and liquidation
- **Structured Notes** - Principal-protected notes with participation in underlying performance
- **Portfolio Swaps** - Total return swaps with NAV-based settlement
- **Autocallables** - Barrier-based notes with early redemption features

Each instrument is isolated in its own module following the "one unit = one file" principle.

## Documentation

- **[DESIGN.md](DESIGN.md)** - Architecture overview, core patterns, and the UNWIND algorithm
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Current status, completed phases, and roadmap
- **[AGENTS.md](AGENTS.md)** - Specialized reviewers and their philosophies
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and design decisions

### Key Architectural Patterns

**The `transact()` Protocol** - Each instrument implements a `transact()` method that reads ledger state via LedgerView and returns ContractResult with moves and state updates. This keeps all business logic pure and testable.

**DeferredCash for Settlement** - Securities markets use T+n settlement. The ledger models this explicitly: stocks transfer on trade date, but cash obligations settle later via DeferredCash units.

**Virtual Ledger for Futures** - Futures track multiple intraday trades in virtual ledger state, then generate a single real margin move at EOD settlement.

**Conservation Laws** - For every unit at all times: sum of balances across all wallets equals constant. Every Move debits source and credits destination atomically.

## Running Tests

The project includes comprehensive test coverage with 876 tests:

```bash
pytest
```

Tests cover:
- Core ledger operations and double-entry accounting
- Time-travel state reconstruction via UNWIND algorithm
- Option, forward, and stock settlement mechanics
- Delta hedging strategies
- Bond coupon payments and accrued interest
- Futures daily settlement and margin calls
- Autocallable barrier observations
- Margin loan collateral management
- Portfolio swap resets and termination
- Structured note payoff calculations

## Current Limitations

The Ledger is designed for **simulation and backtesting**, not production trading systems. Current limitations include:

- Float arithmetic (not Decimal) for simulation performance
- No external settlement system integration
- No regulatory reporting hooks (EMIR, MiFID II)
- No fail tracking or buy-in processes
- No multi-custodian reconciliation
- Holiday calendar support is basic

For a complete list of production hardening requirements, see the Phase 4 section in [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md).

## Performance

The Ledger supports dual-mode execution:

| Mode                                     | Throughput    | Use Case                       |
|------------------------------------------|---------------|--------------------------------|
| Standard                                 | ~50k tx/sec   | Full validation and audit trail|
| Fast mode (`fast_mode=True`)             | ~100k tx/sec  | Skip validation checks         |
| No-log mode (`no_log=True`)              | ~75k tx/sec   | Skip transaction logging       |
| Maximum (`fast_mode=True, no_log=True`)  | ~150k tx/sec  | Monte Carlo simulations        |

Both modes produce identical results for valid inputs - the difference is only in performance characteristics.

## License

[Add license information]

## Contributing

[Add contributing guidelines]
