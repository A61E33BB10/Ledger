# Changelog

All notable changes to the Ledger system will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [4.1.0] - 2025-12-14

### Fixed

#### CRITICAL Fixes

- **CRITICAL-1: Unit Registration Atomicity** (`ledger/ledger.py`)
  - **Problem:** Units from `pending.units_to_create` were registered BEFORE move validation. If validation failed, units remained registered, violating atomicity.
  - **Solution:** Implemented rollback mechanism. Units are now temporarily registered for validation, then unregistered if validation fails. This ensures the ledger is never left in an inconsistent state.

- **CRITICAL-2: Stale State Detection** (`ledger/ledger.py`)
  - **Problem:** `state_changes` were applied without verifying `old_state` matched current state. Stale transactions could silently overwrite newer state.
  - **Solution:** Added optimistic concurrency validation. When applying state changes, the system now compares `old_state` with current unit state and logs warnings when discrepancies are detected.

#### HIGH Priority Fixes

- **HIGH-1: SmartContract Protocol Type Consistency** (`ledger/core.py`)
  - **Problem:** Protocol signature used `Dict[str, float]` for prices but implementations used `Dict[str, Decimal]`.
  - **Solution:** Changed protocol signature to `Dict[str, Decimal]` for consistency with the rest of the codebase.

- **HIGH-2: Decimal Finiteness Check** (`ledger/units/future.py`)
  - **Problem:** Used `math.isfinite(float(price))` which converts Decimal to float, risking precision loss.
  - **Solution:** Replaced with `price.is_finite()` which operates directly on Decimal values.

- **HIGH-3: Division by Zero Guard** (`ledger/units/portfolio_swap.py`)
  - **Problem:** `portfolio_return = (current_nav - last_nav) / last_nav` had no guard against `last_nav <= 0`.
  - **Solution:** Added explicit validation: `if last_nav <= Decimal("0"): raise ValueError(...)`.

- **HIGH-4: Documentation Correction** (`ledger/ledger.py`)
  - **Problem:** Docstring for `verify_double_entry` claimed `Dict[str, float]` but returned `Dict[str, Decimal]`.
  - **Solution:** Updated docstring to correctly state `Dict[str, Decimal]`.

### Added

- `requirements.txt` - Pinned Python dependency versions for reproducible builds
- `CHANGELOG.md` - This file
- `RELEASE_REVIEW_v4.0.0.md` - Comprehensive expert committee review

### Changed

- Test count increased from 975 to 1047 (additional conformance tests)

---

## [4.0.0] - 2025-12-14

### Added

- Initial public release
- Core ledger with double-entry accounting
- 12 financial instrument types:
  - Stock (with dividends and splits)
  - Bond (with coupons and maturity)
  - Option (bilateral, physical delivery)
  - Forward (bilateral)
  - Future (with mark-to-market)
  - Deferred Cash (T+n settlement)
  - Margin Loan (with collateral management)
  - Portfolio Swap (TRS)
  - Structured Note (autocallable)
  - QIS (quantitative investment strategies)
  - Borrow Record (securities lending)
  - Autocallable (observation-based early redemption)
- LifecycleEngine for event-driven processing
- EventScheduler for scheduled events
- Property-based testing with Hypothesis
- Comprehensive conformance test suite
- Expert committee review process

### Documentation

- MANIFESTO.md - Governing principles
- design.md - Formal system design
- lifecycle.md - Event and temporal behavior
- QIS.md - Strategy methodology
- TESTING.md - Testing committee charter
- AGENTS.md - Expert agent specifications
- EXPERT_REVIEW.md - Committee review findings

---

## Expert Committee

The Ledger system is reviewed by a virtual expert committee:

- **Jane Street CTO** - Code correctness, silent failures
- **FinOps Architect** - Financial instrument correctness
- **Andrej Karpathy** - Simplicity, educational clarity
- **Chris Lattner** - API design, long-term maintainability
- **Formal Methods Committee** - Invariant verification, determinism
- **Testing Committee** - Test coverage and methodology

All releases undergo comprehensive review against manifesto principles.

---

*For detailed review findings, see `RELEASE_REVIEW_v4.0.0.md` and `EXPERT_REVIEW.md`.*
