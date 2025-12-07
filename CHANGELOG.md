# Changelog

All notable changes to the Ledger project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [3.0] - December 2025 (Current)

### Added - Phase 3: Complex Instruments
- **Margin Loans** (`ledger/units/margin_loan.py`) - 1,063 lines
  - Collateral pools with asset-specific haircuts
  - Margin status (HEALTHY, WARNING, BREACH, LIQUIDATION)
  - Interest accrual (simple interest, ACT/365)
  - Margin call issuance and cure mechanisms
  - Liquidation with deficiency tracking
- **Structured Notes** (`ledger/units/structured_note.py`) - 657 lines
  - Principal protection with configurable floor
  - Participation rate and cap for upside
  - Optional periodic coupons
- **Portfolio Swaps** (`ledger/units/portfolio_swap.py`) - 711 lines
  - Total return swap on reference portfolio
  - NAV-based settlement with funding leg
  - Reset schedule with state tracking
- **Autocallables** (`ledger/units/autocallable.py`) - 665 lines
  - Barrier observations (autocall, coupon, knock-in)
  - Memory coupon feature
  - Path-dependent payoffs

### Added - Agent Review Framework
- 7 specialized domain agents reviewed the codebase
- 28 new tests covering agent-identified gaps
- `test_agent_review_findings.py` with comprehensive lifecycle tests

### Fixed - Quant Risk Manager Findings
- Autocallable memory coupon audit gap - Added `total_coupon_earned` to observation records
- Futures intraday margin double-counting - Track posted margin only, not abs()
- Margin loan post-liquidation accrual - Block interest accrual after liquidation
- Bond accrued interest edge case - Handle month underflow without issue_date
- Portfolio swap first reset payment skip - Compute funding on first reset
- Margin call timing race condition - Include pending interest in margin status

### Changed
- Liquidation now zeros out `loan_amount`/`accrued_interest` and tracks `liquidation_deficiency` separately

### Test Coverage
- **846 tests** at Phase 3 completion
- **876 tests** after agent review fixes

---

## [2.0] - December 2025

### Added - Phase 2: Exchange-Traded Instruments
- **Futures** (`ledger/units/future.py`) - 610 lines
  - Virtual Ledger pattern for intraday trading
  - Daily settlement (EOD variation margin)
  - Intraday margin calls
  - Expiry settlement
  - Multi-currency support
- **Bonds** (`ledger/units/bond.py`) - 656 lines
  - Coupon schedule generation
  - Day count conventions (30/360, ACT/360, ACT/ACT)
  - Accrued interest calculation
  - Early redemption (CALL/PUT events)
  - Multiple bondholder support

### Fixed
- Intraday margin double-counting bug - `compute_intraday_margin()` now resets `virtual_cash`

### Design Decisions
- **Accepted**: Virtual Ledger pattern for futures (trades update state, EOD settles cash)
- **Accepted**: Separate margin functions (daily, intraday, expiry) rather than unified helper
- **Accepted**: Allow_early parameter for early bond redemption

### Test Coverage
- **589 tests** passing

---

## [1.0] - December 2025

### Added - Phase 1: Foundation
- **Core Types** (`ledger/core.py`)
  - `Move` - Immutable transfer record
  - `Transaction` - Atomic, timestamped collection of moves
  - `ContractResult` - Output from contract execution
  - `StateDelta` - Unit state change record
  - `Unit` - Asset type definition with constraints
  - `LedgerView` - Read-only ledger protocol
- **Ledger** (`ledger/ledger.py`)
  - Double-entry accounting enforcement
  - Balance constraint validation
  - Transaction idempotency
  - UNWIND algorithm for state reconstruction
  - Fast mode (no validation) and normal mode
- **Stock** (`ledger/units/stock.py`)
  - Dividends with DeferredCash pattern
  - Stock splits with ratio adjustment
- **Options** (`ledger/units/option.py`)
  - European call/put with cash settlement
  - Exercise, assignment, expiry events
  - Bilateral transfer rules
- **Forwards** (`ledger/units/forward.py`)
  - Physical or cash settlement
  - Early termination support
- **Delta Hedging** (`ledger/strategies/delta_hedge.py`)
  - Black-Scholes delta calculation
  - Rebalancing logic

### Added - Constants
- `SYSTEM_WALLET` - Reserved wallet for issuance/redemption
- `UNIT_TYPE_*` constants for all instrument types

### Design Decisions
- **Accepted**: String constants for unit types (not enums) - simpler, extensible
- **Accepted**: Pure functions + stateful ledger - contracts return results, ledger applies
- **Accepted**: One unit = one file principle
- **Accepted**: Quantities not values - ledger tracks units, not monetary worth
- **Rejected**: Lifecycle enum - too rigid, events vary by instrument
- **Rejected**: Term sheets in core - kept in unit modules for cohesion
- **Deferred**: Short position dividend obligations - track for Phase 4

### Test Coverage
- **464 tests** passing

---

## Design Philosophy

These principles have remained constant throughout development:

1. **Immutability** - All data structures are frozen/immutable
2. **Pure Functions** - Contracts take LedgerView, return ContractResult
3. **Double-Entry** - Every move has source and destination
4. **Conservation** - Total quantities are preserved across transactions
5. **Determinism** - Same inputs always produce same outputs

---

## Version Compatibility

| Version | Tests | Python | Breaking Changes                  |
|---------|-------|--------|-----------------------------------|
| 3.0     | 876   | 3.12+  | Liquidation now zeros loan_amount |
| 2.0     | 589   | 3.12+  | None                              |
| 1.0     | 464   | 3.12+  | Initial release                   |

---

## Production Readiness

As of v3.0, the Ledger is production-ready for:
- Simulation and backtesting
- Educational demonstrations
- Prototype development

**Not yet production-ready for:**
- Live trading systems (needs persistence, idempotency)
- Regulatory reporting (needs audit trail enhancements)
- External integration (needs event publishing)

See [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for the Phase 4 production hardening roadmap.
