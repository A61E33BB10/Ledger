# Ledger Testing Committee Charter

**Version:** 1.1
**Date:** December 2025
**Last Updated:** Hypothesis integration and conformance suite completion

---

## Purpose

The **Ledger Testing Committee** is established to ensure that the Ledger system's
correctness guarantees are *enforced by tests*, not merely asserted by documentation
or implementation discipline.

The committee's mandate is to design, review, and evolve a **test corpus that functions
as an executable specification** of the Ledger.

**Success Criterion:**
> An independent team can implement a compliant Ledger and pass the full conformance
> test suite without consulting the original implementation or documentation.

At that point, the tests *are* the specification.

---

## Committee Composition

The committee draws on the work of these foundational influences:

### Foundational Members

| Name | Expertise | Role |
|------|-----------|------|
| **Kent Beck** | TDD, tests as specification | Test design methodology |
| **John Hughes** | Property-based testing, QuickCheck | Stateful testing, shrinking |
| **Martin Fowler** | Integration testing, test taxonomy | Test architecture |
| **Michael Feathers** | Characterization tests, legacy code | Change safety |
| **Leslie Lamport** | State machines, invariants | Formal properties |

### Advisory Members

| Name | Expertise | Role |
|------|-----------|------|
| **David Parnas** | Precise specification | Testable modularity |
| **Andreas Zeller** | Failure minimization | Debugging from tests |
| **Nassim Nicholas Taleb** | Failure-mode thinking | Stress testing |

The committee evaluates correctness through **observable behavior captured by tests**,
not by reviewing implementation code directly.

---

## Overarching Testing Principles

### 1. Tests Are Normative
- Tests define required behavior
- Documentation explains intent; tests enforce it
- If it's not tested, it's not guaranteed

### 2. Invariants First
- Conservation, atomicity, determinism, and idempotency must be tested explicitly
- No invariant may exist without a corresponding test
- Invariant tests are the foundation; everything else is derived

### 3. Property-Based by Default
- Where behavior spans large state spaces, properties replace examples
- Randomized input generation is mandatory for stateful logic
- Shrinking provides minimal counterexamples

### 4. Composition over Isolation
- Integration tests are favored over heavily mocked unit tests
- The system must be tested as a composed whole
- Mocks are acceptable only for external boundaries

### 5. Determinism Is Mandatory
- Tests must be reproducible given the same seed and inputs
- Any nondeterminism is considered a defect
- Seeds must be captured and reportable

### 6. Failure Modes Are First-Class
- Rejection paths, invalid inputs, and boundary conditions are tested explicitly
- Silent degradation is forbidden
- Error messages/codes must be stable and testable

### 7. Automation Is Non-Negotiable
- All tests must be runnable in CI
- Manual testing is not a correctness mechanism
- Flaky tests are bugs

---

## Hypothesis: Property-Based Testing Framework

### Why Hypothesis?

The Testing Committee selected **Hypothesis** as the property-based testing framework
for the Ledger conformance suite. This section explains the rationale and usage.

### The Problem with Example-Based Tests

Traditional example-based tests have a fundamental limitation:

```python
# Example-based: tests ONE specific case
def test_transfer_conserves():
    ledger.transfer("alice", "bob", Decimal("100"))
    assert ledger.total_supply() == initial_supply
```

This test passes, but does it prove conservation holds for ALL transfers?
What about edge cases like:
- Very small amounts (`0.0000001`)?
- Very large amounts (`999999999999.99`)?
- Amounts with trailing zeros (`100.00` vs `100`)?
- Rapid sequences of transfers?

**You cannot enumerate all edge cases manually.**

### The Property-Based Solution

Property-based testing inverts the approach:

1. **Define the property** (invariant) that must always hold
2. **Let the framework generate** hundreds of random test cases
3. **When a failure is found**, automatically shrink to minimal counterexample

```python
# Property-based: tests the PROPERTY across many cases
@given(st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000")))
def test_any_transfer_conserves(amount):
    ledger.transfer("alice", "bob", amount)
    assert ledger.total_supply() == initial_supply
```

Hypothesis will:
- Generate 100+ random `amount` values
- Include edge cases (min/max bounds, strange decimal representations)
- If any amount breaks conservation, report the **smallest** failing case

### What Hypothesis Brings to the Table

| Feature | Benefit |
|---------|---------|
| **Automatic Input Generation** | Tests cases humans wouldn't think of |
| **Shrinking** | When a test fails, finds the *minimal* counterexample |
| **Reproducibility** | Failing cases are deterministic via seed |
| **Composable Strategies** | Build complex test inputs from simple primitives |
| **Stateful Testing** | Test sequences of operations, not just single calls |
| **Integration with pytest** | Works seamlessly with existing test infrastructure |

### Shrinking: The Killer Feature

When Hypothesis finds a failing case, it doesn't just report it—it **shrinks** it:

```
Falsifying example: test_canonicalization(
    d1=Decimal('100.000000'),
    d2=Decimal('100'),
)
```

Instead of reporting some complex 47-digit decimal that happened to fail,
Hypothesis finds the **simplest** input that demonstrates the bug.

This is invaluable for debugging. Compare:
- Without shrinking: "Failed with input `Decimal('847293.847293847293')`"
- With shrinking: "Failed with input `Decimal('100.0')` vs `Decimal('100')`"

The second immediately suggests the bug is in trailing zero handling.

### Strategies Used in the Conformance Suite

The conformance tests use these Hypothesis strategies:

```python
# Generate valid decimal quantities
st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("1000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Generate wallet names from a fixed set
st.sampled_from(["alice", "bob", "charlie", "treasury"])

# Generate lists of transactions
st.lists(
    st.tuples(decimal_quantity, wallet_name, wallet_name),
    min_size=1,
    max_size=10,
)

# Composite strategies for complex inputs
@st.composite
def valid_move(draw, wallets, units, balances):
    """Generate a move that won't be rejected."""
    unit = draw(st.sampled_from(units))
    source = draw(st.sampled_from(wallets))
    dest = draw(st.sampled_from([w for w in wallets if w != source]))
    # ... ensure sufficient balance ...
    return Move(quantity, unit, source, dest, contract_id)
```

### Key Invariants Tested with Hypothesis

| Invariant | Property Test |
|-----------|---------------|
| **Conservation** | Any sequence of valid transfers preserves total supply |
| **Atomicity** | Any failing transaction leaves state unchanged |
| **Idempotency** | Any transaction executed N times produces same state as once |
| **Canonicalization** | Equal Decimals produce identical normalized strings |
| **Intent Identity** | Same transaction content always produces same `intent_id` |

### Committee Perspective: John Hughes on Property-Based Testing

> *"Don't write tests. Write properties."*
>
> A single property test replaces hundreds of example tests. More importantly,
> it tests cases the developer never imagined. The shrinking algorithm ensures
> that when bugs are found, they are presented in their simplest form.
>
> For a financial ledger where correctness is paramount, property-based testing
> is not optional—it is the only responsible approach to testing invariants
> that must hold for ALL inputs, not just the ones we happened to think of.
>
> — **John Hughes**, co-creator of QuickCheck

### Running Property Tests

```bash
# Run all conformance tests (includes property tests)
pytest tests/conformance/ -v

# Run with more examples (slower, more thorough)
pytest tests/conformance/ -v --hypothesis-seed=0 -p no:randomly

# See hypothesis statistics
pytest tests/conformance/ -v --hypothesis-show-statistics
```

### Configuration

Hypothesis settings are configured per-test:

```python
@given(st.integers(min_value=1, max_value=100))
@settings(max_examples=50)  # Run 50 random cases
def test_conservation_holds(num_transfers):
    ...
```

For CI, we use `max_examples=50-200` for balance between speed and coverage.
For release validation, increase to `max_examples=1000`.

---

## Test Categories

### Category 1: Conformance Tests (Normative)

These tests define the **minimum requirements** for any compliant Ledger implementation.

#### 1.1 State Machine Conformance
- `execute()` is the only mutation point
- State transitions are atomic
- Intermediate states are unobservable

#### 1.2 Conservation & Double-Entry
- For any unit `u`: `Σ balances(w, u) == 0`
- Tested with random transaction sequences
- Mixed issuance, transfer, redemption

#### 1.3 Idempotency & Identity
- Same `PendingTransaction` twice: first `APPLIED`, second `ALREADY_APPLIED`
- State unchanged after replay
- `intent_id` is deterministic and canonical

#### 1.4 Deterministic Replay
- `replay(log, inputs) == original_state`
- Random transaction logs
- Random lifecycle timelines

#### 1.5 Temporal Semantics
- Time advances only explicitly
- Events execute in total order
- Cascading events converge within `max_passes`

#### 1.6 Strategy (QIS) Semantics
- Strategies are pure and deterministic
- Rebalancing is self-financing: `NAV_before == NAV_after`
- Financing accrual follows formula

---

### Category 2: Property-Based Tests

Tests using randomized input generation with automatic shrinking.

#### 2.1 Ledger Properties
```
property: conservation_holds
  ∀ sequence of valid transactions:
    sum(balances[u]) == 0 for all units u
```

```
property: atomicity_holds
  ∀ transaction tx that fails validation:
    state_after == state_before
```

```
property: idempotency_holds
  ∀ transaction tx:
    execute(execute(tx)) produces ALREADY_APPLIED
    state after second execute == state after first
```

#### 2.2 Canonicalization Properties
```
property: intent_id_canonical
  ∀ semantically equivalent transactions tx1, tx2:
    intent_id(tx1) == intent_id(tx2)
```

```
property: decimal_normalization
  ∀ decimals d1, d2 where d1 == d2:
    normalize(d1) == normalize(d2)
```

---

### Category 3: Failure & Rejection Tests

Explicit testing of unhappy paths.

| Test | Input | Expected |
|------|-------|----------|
| Unknown unit | Move references unregistered unit | `REJECTED` |
| Unknown wallet | Move references unregistered wallet | `REJECTED` |
| Min balance breach | Transfer causes `balance < min_balance` | `REJECTED` |
| Max balance breach | Transfer causes `balance > max_balance` | `REJECTED` |
| Zero quantity | `Move(0, ...)` | `REJECTED` |
| Source == Dest | `Move(100, "USD", "alice", "alice", ...)` | `REJECTED` |
| Transfer rule violation | Move violates unit's transfer_rule | `REJECTED` |

---

### Category 4: Integration Tests

End-to-end scenarios testing composed behavior.

#### 4.1 Full Lifecycle
```
Issuance → Trades → Corporate Action → Settlement → Redemption
```
Assert invariants after every stage.

#### 4.2 Timeline Replay
```
Capture (timestamp, prices) sequence + executed tx log
Replay from genesis
Assert identical final state
```

---

### Category 5: Stress & Scale Tests

Performance under load (semantic correctness required; performance thresholds optional).

| Test | Scale | Requirement |
|------|-------|-------------|
| Large log replay | 100k+ transactions | Correct final state |
| Many wallets | 10k+ wallets | Invariants hold |
| Many units | 1k+ units | Invariants hold |
| Long timeline | 10+ years simulated | Events fire correctly |

---

### Category 6: Mutation Tests

Controlled fault injection to verify test sensitivity.

| Mutation | Expected Result |
|----------|-----------------|
| Remove conservation check | Conservation tests fail |
| Disable `intent_id` seen-set | Idempotency tests fail |
| Change event sort order | Lifecycle determinism tests fail |
| Allow partial transaction apply | Atomicity tests fail |
| Replace Decimal with float | Precision tests fail or drift detected |

---

## Test Harness Requirements

### Deterministic Runs
- Same seed + same inputs = identical results
- Including ordering, IDs, error messages

### Reproducible Failures
Any failing test must print:
- Seed
- Minimized counterexample (shrunk case)
- Full serialized scenario

### No Hidden Dependencies
Tests must fail if core logic observes:
- `datetime.now()`
- Unseeded randomness
- Environment variables

---

## Current Test Coverage Assessment

### Summary

| Metric | Current | Target |
|--------|---------|--------|
| Total Tests | **1044** | - |
| Test Files | 42 | - |
| Lines of Test Code | ~20,000 | - |
| Conformance Tests | **69** | Core invariants |
| Property-Based Tests | **6 files** | All invariant tests |
| Mutation Test Suite | None | Required |
| Stress Tests | Good | 10k transactions |

### Conformance Test Suite

The conformance test suite (`tests/conformance/`) defines the **normative behavior**
of the Ledger. These tests use `hypothesis` for property-based testing.

| File | Tests | Coverage |
|------|-------|----------|
| `test_conservation.py` | 10 | Double-entry conservation |
| `test_atomicity.py` | 7 | All-or-nothing semantics |
| `test_idempotency.py` | 10 | Duplicate detection |
| `test_canonicalization.py` | 19 | Intent ID determinism |
| `test_determinism.py` | 10 | Replay, clone, state |
| `test_temporal.py` | 13 | Time ordering |

**Run conformance tests:**
```bash
pytest tests/conformance/ -v
```

### Coverage by Category

| Category | Status | Notes |
|----------|--------|-------|
| Conservation | ✅ **Excellent** | `conformance/test_conservation.py` + property tests |
| Atomicity | ✅ **Excellent** | `conformance/test_atomicity.py` |
| Idempotency | ✅ **Excellent** | `conformance/test_idempotency.py` |
| Canonicalization | ✅ **Excellent** | `conformance/test_canonicalization.py` - C1/C3 verified |
| Determinism | ✅ **Excellent** | `conformance/test_determinism.py` |
| Temporal | ✅ **Excellent** | `conformance/test_temporal.py` |
| Reproducibility | ✅ Good | `test_reproducibility.py` |
| Event Ordering | ✅ Good | `test_scheduled_events.py` |
| Failure Modes | ✅ Good | Multiple files |
| Property-Based | ✅ **Good** | Uses `hypothesis` framework |
| Mutation Testing | ⚠️ Pending | Not yet implemented |
| Stress Testing | ✅ Good | 100/1k/10k transaction tests |

---

## Committee Review: Priority Gaps

### RESOLVED (Previously Critical)

#### ~~Gap 1: Property-Based Testing Infrastructure~~ ✅ RESOLVED
**Status:** `hypothesis` library integrated. Conformance tests use proper property-based testing with automatic shrinking.

#### ~~Gap 2: Canonicalization Test Suite~~ ✅ RESOLVED
**Status:** `tests/conformance/test_canonicalization.py` provides comprehensive property tests for `_canonicalize()` and `_normalize_decimal()`. C1/C3 fixes are now verified.

### REMAINING (Should Address)

#### Gap 3: Mutation Testing
**Issue:** No mutation testing infrastructure.
**Impact:** Cannot prove tests detect semantic regressions.
**Recommendation:** Integrate `mutmut` or equivalent; run on CI schedule.

### HIGH (Should Address)

#### Gap 4: Cross-Process Determinism
**Issue:** No tests verify `intent_id` stability across Python versions/platforms.
**Impact:** Serialization divergence could break distributed systems.
**Recommendation:** Add golden file tests with expected `intent_id` values.

#### Gap 5: Stress Test Suite
**Issue:** Limited scale testing; only `test_many_transactions_conserve` with 1000 txs.
**Impact:** May miss O(n²) issues or memory leaks.
**Recommendation:** Add 100k+ transaction tests; benchmark regression thresholds.

#### Gap 6: Event Scheduling Edge Cases
**Issue:** H4 (events during step) behavior not explicitly tested.
**Impact:** Semantic ambiguity could cause implementation divergence.
**Recommendation:** Add tests that explicitly document and verify the behavior.

### MEDIUM (Should Consider)

#### Gap 7: Fuzz Testing
**Issue:** No adversarial input testing.
**Impact:** May miss edge cases in parsing/validation.
**Recommendation:** Add structured fuzzing for event params, state dicts.

#### Gap 8: Error Message Stability
**Issue:** Tests assert on `REJECTED` but not error reasons.
**Impact:** Clients cannot rely on error codes/messages.
**Recommendation:** Standardize error codes; test for stability.

---

## Recommended Test Structure

```
tests/
├── conformance/           # Normative tests (defines spec)
│   ├── test_conservation.py
│   ├── test_atomicity.py
│   ├── test_idempotency.py
│   ├── test_determinism.py
│   ├── test_canonicalization.py
│   └── test_temporal.py
├── property/              # Property-based tests
│   ├── test_ledger_properties.py
│   ├── test_decimal_properties.py
│   └── test_event_properties.py
├── integration/           # End-to-end scenarios
│   ├── test_lifecycle_full.py
│   ├── test_timeline_replay.py
│   └── test_strategy_execution.py
├── failure/               # Explicit failure mode tests
│   ├── test_validation_rejections.py
│   ├── test_boundary_conditions.py
│   └── test_error_messages.py
├── stress/                # Scale and performance
│   ├── test_large_logs.py
│   ├── test_many_wallets.py
│   └── test_long_timelines.py
├── mutation/              # Mutation test targets
│   └── mutmut_config.py
└── unit/                  # Component unit tests
    └── ...existing...
```

---

## CI/CD Requirements

### On Every PR
- All conformance tests pass
- All property tests pass (fixed seed)
- No test flakiness

### Nightly
- Property tests with rotating seeds
- Stress tests
- Coverage report

### Weekly
- Mutation testing
- Cross-platform verification
- Performance regression benchmarks

---

## Action Items

### Phase 1: Foundation ✅ COMPLETE

1. [x] Add `hypothesis` dependency
2. [x] Convert conservation tests to property-based (`tests/conformance/test_conservation.py`)
3. [x] Add canonicalization property tests (`tests/conformance/test_canonicalization.py`)
4. [x] Add explicit atomicity tests (`tests/conformance/test_atomicity.py`)
5. [x] Add idempotency tests including intent-vs-economics distinction
6. [x] Add determinism tests (`tests/conformance/test_determinism.py`)
7. [x] Add temporal tests (`tests/conformance/test_temporal.py`)

### Phase 2: Coverage (Near-Term)

8. [ ] Add cross-process `intent_id` golden tests
9. [ ] Add stress test suite (100k transactions)
10. [ ] Add event scheduling edge case tests
11. [ ] Standardize error codes

### Phase 3: Infrastructure (Ongoing)

12. [ ] Integrate mutation testing (`mutmut`)
13. [ ] Add fuzz testing for state/params
14. [ ] Set up nightly CI with rotating seeds
15. [ ] Create conformance test certification report

---

## Invocation Template

To invoke the Testing Committee in a new session:

```
You are the Ledger Testing Committee, comprising Kent Beck, John Hughes,
Martin Fowler, Michael Feathers, and Leslie Lamport.

Your role is to evaluate test coverage and recommend improvements based on:
1. Tests as specification (Beck) - Can someone reimplement from tests alone?
2. Property-based testing (Hughes) - Are invariants tested with random inputs?
3. Integration architecture (Fowler) - Is the system tested as a whole?
4. Change safety (Feathers) - Will tests catch semantic regressions?
5. Formal properties (Lamport) - Are state machine invariants verified?

Review the following test suite and identify:
- Gaps in conformance coverage
- Missing property-based tests
- Untested failure modes
- Scale/stress testing needs

Prioritize findings as CRITICAL, HIGH, or MEDIUM.

Test files to review:
{test_file_list}
```

---

## Closing Statement

> *Correctness is not something we hope for.*
>
> *It is something we specify, test, and continuously enforce.*

The Ledger's guarantees are too important to live only in prose.
They must live in tests.

---

**Signed:**

Kent Beck — *Tests define behavior*
John Hughes — *Properties over examples*
Martin Fowler — *Test the system, not the units*
Michael Feathers — *Tests enable safe change*
Leslie Lamport — *Invariants are contracts*

---

*This charter governs the testing strategy for the Ledger system. All test additions
and modifications should be evaluated against these principles.*
