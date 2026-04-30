# Phase 3 — Round 1 — TESTCOMMITTEE Adversarial Review

**Reviewer panel.** Beck (TDD), Hughes (QuickCheck/PBT), Fowler (test pyramid), Feathers (legacy/characterization), Lamport (TLA+/invariants).
**Target.** `phase2/proposal_v1.md`, with drilldowns into `phase2/correctness.md` and `phase2/formalis.md`.
**Stance.** Tests are normative. If the proposal cannot be reimplemented from the test suite alone, the specification is incomplete. If a law has no shrinker, no oracle, or no failing-mutant, it is not specified — it is decorative.

The proposal lists 14 cross-layer laws (CORRECTNESS L1–L14), 12 determinism boundaries (B1–B12), 49 fault rows, 4 unwitnessed laws (U1–U4), 4 Goodhart traps, and 10 mutation operators (M-CONS … M-LATE). I attack each axis in turn.

---

## §A — Per-law audit: generator + oracle + shrinker triple

The `phase2/correctness.md` §4.2 sketches one Hypothesis-style snippet per law. **A property test is a triple of (generator, oracle, shrinker).** I evaluate each.

| Law | Generator named? | Oracle decidable? | Shrinker bias hazard | Verdict |
|---|---|---|---|---|
| L1 Lineage closure | `gen_committed_tx` | "envelopes != [] ∧ signature_verified" — *trivially passable*: a constant non-empty stub passes. **Oracle is too weak.** | Hypothesis will shrink to the empty lineage; if the stub passes empty, the bug never surfaces. | **BLOCKING** |
| L2 Snapshot determinism | `gen_market_snapshot` | Mahalanobis-zero is *not* what L8 demands — L8 demands bit-identity. The oracle silently weakens to "close enough" and lets MC drift through. | No shrinker for snapshot graphs is documented. | **UNMITIGATED MAJOR** |
| L3 Settlement-move closure | `gen_committed_tx_with_settlement` | One-direction only (`tx → confirms`); the bidirectional walk required by §1.L3 is absent from the snippet. | — | **UNMITIGATED MAJOR** |
| L4 Bitemporal coherence | `gen_bitemporal_datum` | Snippet only checks `read == read` (same call twice). It does **not** check the substantive predicate `t_v ≤ t_k` nor restatement-version monotonicity. Idempotence of `read` is necessary but laughably insufficient. | — | **BLOCKING** |
| L5 Per-class conservation | `gen_oracle_event` | OK in shape. But `MONOTONE_FIELDS` is a free string list — no closed enum cited. Adding a new monotone field silently exempts it from the test. | Shrinker will collapse to single-handler, single-field; multi-field cross-class violations missed. | **UNMITIGATED MAJOR** |
| L6 Mandate-as-unit | `gen_mandate` + `gen_mandate_lifecycle_event` | Tests unit-count zero-sum. Does **not** test HWM-not-shared-across-mandates — the actual failure mode named in §1.L6 ("cross-mandate HWM collapse"). | — | **BLOCKING** |
| L7 Per-CCP conservation | `gen_cleared_unit` | OK. | Stratification by CCP-count not stated — Hypothesis will mostly draw 1-CCP cases. | MINOR |
| L8 Replay determinism | `gen_committed_tx` | OK in shape; relies on `tx_id == content_hash(...)` cross-cutting. | The shrinker for "non-deterministic handler" needs a *seeded clock injection* generator that is not specified. | **UNMITIGATED MAJOR** |
| L9 Forgetful composition | `gen_event` × 2 | `assume(referentially_independent(...))` — the predicate `referentially_independent` is undefined. Hypothesis will reject most pairs and the test passes vacuously. (Goodhart trap #3 in person.) | — | **BLOCKING** |
| L10 Workflow-history coherence | `gen_workflow_history` | Tests `replay == replay` (idempotence on identical inputs). Does **not** test that history under a *worker restart* produces the same decisions, which is the actual L10 statement. | — | **UNMITIGATED MAJOR** |
| L11 Calibration/valuation | `gen_option`, `gen_perturbation` | Put-call-parity OK. Cross-model contamination (the *named* failure mode) requires a generator that pairs jacobian@modelA with price@modelB — absent. | — | **UNMITIGATED MAJOR** |
| L12 Admissibility | `gen_calibrated_state` | Trivially passable: the generator rejection-samples to stay in Θ_AF, then asserts in-region. **It tests the generator, not the system.** | This is a textbook Goodhart trap not listed in §6. | **BLOCKING** |
| L13 Obligation liveness (bounded) | `gen_obligation`, `gen_simulation_horizon` | OK for bounded surrogate. Compensation handler totality (FORMALIS I10) referenced but not generated. | — | MINOR (escalates with U1 below) |
| L14 Capability scope | `gen_capability_set`, `gen_query` | OK. Replay-time bypass (the *named* Goodhart trap in §1.L14) requires a generator that runs the same query through the replay path — absent. | — | **UNMITIGATED MAJOR** |

**Aggregate:** 4 BLOCKING, 6 UNMITIGATED MAJOR, 2 MINOR oracle-quality findings on the 14 laws. The proposal's snippets are *illustrative*, not *normative*. Beck: "If the test does not fail when the code is wrong, it does not exist."

---

## §B — Are the 4 unwitnessed laws genuinely unwitnessed?

CORRECTNESS §5 surrenders four laws (L1, L4, L8, L13) as unwitnessed-by-finite-test. I tested whether the surrender was earned.

### B.1 — U1 (L13 obligation liveness over unbounded futures) — **PARTIAL SURRENDER, 70% RECOVERABLE**

The proposal proposes "structural induction (FORMALIS I10)" as surrogate. Hughes: liveness over `ω` is decidable by *Büchi automaton model-checking* whenever the obligation type has finite state. Lamport: TLA+'s `<>P` (eventually P) is exactly this check. The proposal does not invoke either.

**Recoverable witnesses the proposal failed to try:**
1. **TLA+ specification** of the obligation FSM with a `WF_vars(Discharge ∨ Compensate ∨ Default)` weak-fairness constraint — TLC checks `<>(state ∈ {D,C,Def})` over the full reachable state space.
2. **Stateful Hypothesis (`RuleBasedStateMachine`)** with a deadline-bounded model — the same machine generalises liveness *up to* the model's bisimulation horizon.
3. **Coverage-guided obligation FSM exploration** with deadline-skip mutation: forces the system to demonstrate terminal-reachability from every reachable non-terminal.

**Verdict.** Not genuinely unwitnessed. The "surrogate" is a retreat from machinery the team has not invested in. **UNMITIGATED MAJOR.**

### B.2 — U2 (L4 bitemporal under unbounded restatements) — **PARTIAL SURRENDER, 60% RECOVERABLE**

Surrender claim: "chains are over `ω`". Lamport: this is a *safety* property (closure under any chain prefix), not a liveness property. Safety properties on append-only structures are decidable by induction on the chain. The proposal conflates "we cannot enumerate all chains" with "we cannot decide the property".

**Recoverable.** Inductive property: ∀v_n. `replay(read, t_econ, knowledge=v_n) = replay(read, t_econ, knowledge=v_{n-1})` for every datum whose `knowledge_time(v_n) > t_k`. This is decidable per-step; the unbounded chain is irrelevant.

**Verdict.** **UNMITIGATED MAJOR.** The surrogate is correct *but the underlying law is witnessable* — the surrender was unnecessary.

### B.3 — U3 (L1 lineage under vendor opacity) — **GENUINELY UNWITNESSED**

Trust registry + threat model + multi-source consensus is the right move. **MINOR**: the proposal does not specify what happens when a vendor's attestation is statistically inconsistent but within innovation-gating tolerance — the residual risk is real but the surrender is principled. **Accept with operational mitigation specified in CC-3 + Cluster III row "contradicted".**

### B.4 — U4 (L8 replay under cosmic-ray bit flips) — **GENUINELY UNWITNESSED, BUT MIS-CLASSIFIED**

This is a *storage-integrity* property, not a *test* property. The hash-chain (P-CCC-1) decides it post-hoc; what cannot be decided ex-ante is the storage system's failure rate. **MINOR** — accept the framing but rename to "storage-integrity surrogate", not "unwitnessed law".

**Aggregate.** Of the 4 declared unwitnessed laws, **2 (U1, U2) are recoverable with machinery the proposal failed to invoke**. Hughes: "The tester is the first to give up. Don't be the first."

---

## §C — Are the 4 Goodhart traps actually avoided?

CORRECTNESS §6 lists 4 traps. I checked each against the test program in §4.

### C.1 — "Snapshot coverage = 100%" — **AVOIDED**

P-L8 demands byte-identical replay. The trap is closed.

### C.2 — "Mutation score is high but excludes some operators" — **PARTIALLY AVOIDED**

The 10 listed operators (M-CONS … M-LATE) catch the named failure modes. But Feathers: **operator coverage is not the same as kill rate**. The proposal does not specify which mutants must be *killed by which property tests* — a mutation may be killed by a unit test that has nothing to do with the law it threatens. Mutation testing without a property-to-mutant mapping degenerates into a coverage metric.

**Missing operators identified by panel:**
- M-BIAS: bias a generator to skip a CDM ProductType (catches Goodhart trap #3 itself).
- M-DEFLATE: collapse a closed enum to a single value (kills L9 forgetful composition's domain coverage).
- M-AGGREGATE: replace `per_class_sum == 0` with `aggregate_sum == 0` (catches Goodhart trap #4 itself).
- M-FAKE-CERT: flip `certified=False` to `certified=True` without re-projection (kills L11/L12 directly).
- M-SHRUG-RETRY: replace activity retry-policy with infinite (catches L13 latent default).

**Verdict.** **UNMITIGATED MAJOR.** The mutation set as listed is necessary but not sufficient.

### C.3 — "Property catalogue is large but generators are biased" — **NOT AVOIDED**

The proposal cites stratification by `CDM ProductType × EventIntent matrix` but does not specify *coverage targets per stratum*. Hypothesis's default biasing (favour small examples, simple data) will under-explore the long tail (cross-currency QIS with manufactured payments, cleared-via-2-CCPs SBL with rehypothecation, mandate with crystallisation during a corporate action). The proposal has no per-stratum coverage assertion.

**Verdict.** **BLOCKING.** Without measured per-stratum coverage, the property suite is statistical theatre.

### C.4 — "Conservation passes under aggregation that masks per-scope violation" — **TEXTUALLY AVOIDED, OPERATIONALLY UNTESTED**

§6 trap #4 says "any aggregation MUST be accompanied by the per-scope check". This is a *recommendation*, not a *test*. The proposal does not include a meta-property:

```python
@given(s=gen_state_with_violation_in_one_scope())
def test_aggregation_does_not_mask(s):
    assert aggregate_sum(s) == 0  # masking case
    assert any(scope_sum(s, scope) != 0 for scope in s.scopes)
```

Without this, the trap is *named* but not *trapped*.

**Verdict.** **UNMITIGATED MAJOR.**

---

## §D — Mutation classes ranked by bug-per-dollar (Beck + Feathers)

The proposal ranks 10 mutation operators by "expected kill rate against the 14 laws" but provides no empirical or proxied basis. The panel ranks differently:

| Rank | Operator | Why it is bug-per-dollar champion | Coverage of laws |
|---|---|---|---|
| 1 | **M-CANON** (alter canonicalisation) | Catches every replay/composition/idempotency bug at once. One mutation, ~6 laws fail. | L8, L9, L1, L2, L10 + all P-CCC |
| 2 | **M-CONS** (flip sign on delta) | Catches the highest-severity class (silent revenue leak) with one-line cost. | L5, L6, L7 |
| 3 | **M-FAKE-CERT** (flip certified flag) — *new, panel* | One bit, two laws, billions of dollars in fake PnL. | L11, L12 |
| 4 | **M-AGGREGATE** (collapse per-scope to aggregate) — *new, panel* | Directly kills Goodhart trap #4. | L5, L6, L7 |
| 5 | **M-CLOCK** (insert wall-clock read) | Catches the most common Temporal-determinism violation. | L8, L10 |
| 6 | **M-CDM** (silently accept unknown enum) | One-line bug, breaks every parser-ring guarantee. | L9, U3 |
| 7 | **M-NOPROJ** (skip Θ_AF projection) | Targets the no-arbitrage law directly. | L12 |
| 8 | **M-CACHE** (cache adjusted date) | Bitemporal poison. | L4, L13 |
| 9 | **M-LATE** (drop late-flag) | Calibration drift over time. | L4, L9 |
| 10 | **M-BOUND** (`<` ↔ `≤`) | High volume, low severity per kill. | L11, L13 |
| 11 | **M-CAP** (skip capability check) | Detected by P-L14 directly. | L14 |

**Recommendation.** Promote M-FAKE-CERT and M-AGGREGATE into the canonical operator set. Demote M-BOUND from the front of the list — bound errors are caught by ordinary unit tests, not load-bearing property tests.

**MINOR finding.** The proposal does not specify a *mutation budget*: how many mutations per merge? Per release? Per quarter? Without a budget, the 80% target is aspirational.

---

## §E — Where regression tests for known historical bug classes are missing

Feathers: "Code without characterization tests is bugs in waiting." I scanned the proposal for regression-test fixtures of historical bug classes from the v10.3 corpus and prior addenda.

### E.1 — Missing: LIBOR-cessation fallback regression fixture

The valuation document v1.0 §5.7 references LIBOR cessation. There is no named regression scenario in the property catalogue covering: (a) LIBOR fixing pre-cessation, (b) RFR-rate fallback post-cessation, (c) bitemporal restatement of a fixing that crossed the cessation date. **UNMITIGATED MAJOR** — this is exactly the class of historical bug (single-axis "as-of") L4 was written to forbid, with no fixture to prove it.

### E.2 — Missing: dividend-equivalent payment (DEP) cross-jurisdiction regression

Manufactured payments under SBL have produced historical mis-attribution bugs (US-871(m), German fiscal events). MATTHIAS Top-5 Gap #2 names this. There is no fixture in §4.1 for a manufactured-payment rate observation crossing a withholding-tax jurisdiction boundary. **UNMITIGATED MAJOR.**

### E.3 — Missing: corporate-action cascade regression (split → merger)

A historical class: corporate actions that mutate `unit_id` mid-life (stock split, merger, ISIN change). The proposal names these in `gen_corp_action` but no fixture asserts that downstream obligations on the *pre-action* `unit_id` route correctly to the *post-action* one (a `supersedes` chain test). **UNMITIGATED MAJOR.**

### E.4 — Missing: leap-second / DST regression on durable timers

TEMPORAL §6.1 names retroactive calendar amendments as worst-fit. The historical bug class — a durable timer fires twice across DST or once per leap-second — has no fixture. **MINOR.**

### E.5 — Missing: CCP migration regression

A unit moves from CCP_A to CCP_B (real event: Brexit-driven migrations 2019–2021). Per-CCP conservation L7 must hold across the migration boundary. No fixture. **MINOR.**

### E.6 — Missing: tokenised-collateral chain reorganisation regression

Strategic Gap #3. No fixture for a chain reorg invalidating a tokenised collateral attestation. Given v10.3 §10.6 names this risk, **UNMITIGATED MAJOR.**

### E.7 — Present, well-covered: hash-chain integrity, conservation, idempotency

These have continuous-verification properties (P-CCC-1 … P-CCC-6). Well-served.

**Aggregate regression-fixture verdict.** 4 UNMITIGATED MAJOR + 2 MINOR. The proposal has the *property catalogue* but not the *historical-bug fixture set*. Property tests prove generic laws; characterization tests prove "the bug we shipped in 2017 stays dead". The proposal needs both.

---

## §F — Pyramid shape (Fowler)

The proposal does not declare its test-pyramid shape. From the §4 inventory:
- 14 cross-layer property tests (L1–L14).
- 6 cross-cutting properties (P-CCC-1..6).
- 49 fault rows (recovery and detection mechanisms).
- 10 mutation operators.
- ~12 generators.

This is a *flat* structure: everything sits at the property-test layer. There is **no documented unit-test layer** for individual leaves, **no documented integration-test layer** for boundary contracts (B1–B12), and **no documented end-to-end / scenario layer** for full workflows.

Fowler: "Broad scope tests should be rare. The pyramid is a reminder that they cost the most to maintain." The proposal inverts this — it has *only* broad-scope tests in its catalogue.

**Verdict.** **BLOCKING.** Either (a) declare explicitly that per-leaf invariants (FORMALIS I1–I20) are the unit-test layer (and exhibit the test files), or (b) produce a pyramid declaration showing test counts per layer with target ratios.

---

## §G — Determinism boundary B11 / B12 testability

B11 (operator/human interaction) and B12 (network/message reordering) are *new* boundaries flagged by CORRECTNESS as absent from Phase 1. The proposal admits them but does not specify generators. Without `gen_governance_attestation` and `gen_message_reorder_scenario`, these boundaries fail the "every boundary MUST be injectable in the simulation harness" rule from §2 of correctness.md. **UNMITIGATED MAJOR.**

---

## §H — Specification-completeness test (Beck): can someone reimplement from tests?

Beck's normative test: **given only the test suite, can a fresh team reimplement the system?**

Drilling at random into proposal §3 leaves:
- L8 UnitStatus: "3T + 2W + 2C = 7 invariants (`formalis.md` L5)" — the *count* is in the proposal; the *content* is in `formalis.md`. A reimplementer cannot reconstruct the seven invariants from the proposal alone.
- L13 Calibrated Market Object: "4T + 2W + 2C = 8 invariants" — same issue. A reimplementer cannot tell which witness type `arbitrage_certificate` carries.
- L14 MoveStream: "11 invariants" — the load-bearing leaf, with the highest invariant count. The proposal compresses to one line.

**Verdict.** The proposal is a *navigation document*, not a *specification*. A reimplementer must read seven specialist files plus the v10.3 corpus to know what to build. **MINOR** as a proposal-quality finding (the proposal is honest about its compression — "specialist files are the authoritative source"); **UNMITIGATED MAJOR** as a Phase-3 deliverable: the union of `proposal_v1.md + correctness.md + formalis.md + minsky.md` must be normatively complete or no test suite can be built from it.

---

## §I — Findings summary

| ID | Severity | Topic |
|---|---|---|
| F-01 | **BLOCKING** | L1 oracle is too weak; constant-stub passes |
| F-02 | **BLOCKING** | L4 oracle tests `read == read` not `t_v ≤ t_k` |
| F-03 | **BLOCKING** | L6 omits HWM-cross-mandate-collapse (the named failure mode) |
| F-04 | **BLOCKING** | L9 has undefined predicate `referentially_independent` → vacuous pass |
| F-05 | **BLOCKING** | L12 generator rejection-samples into Θ_AF then asserts in-region (Goodhart) |
| F-06 | **BLOCKING** | Goodhart trap #3 not avoided — no per-stratum coverage targets |
| F-07 | **BLOCKING** | No declared test pyramid; flat structure inverts Fowler |
| F-08 | **UNMITIGATED MAJOR** | L2 oracle weakens L8's bit-identity to Mahalanobis-zero |
| F-09 | **UNMITIGATED MAJOR** | L3 bidirectional walk reduced to one direction |
| F-10 | **UNMITIGATED MAJOR** | L5 monotone-field list is a free string set; new fields silently exempted |
| F-11 | **UNMITIGATED MAJOR** | L8 has no seeded-clock-injection generator |
| F-12 | **UNMITIGATED MAJOR** | L10 tests `replay == replay`, not "replay across worker restart" |
| F-13 | **UNMITIGATED MAJOR** | L11 cross-model-contamination generator absent |
| F-14 | **UNMITIGATED MAJOR** | L14 replay-time bypass scenario absent |
| F-15 | **UNMITIGATED MAJOR** | U1 (liveness) recoverable via TLA+ / RuleBasedStateMachine — surrender unearned |
| F-16 | **UNMITIGATED MAJOR** | U2 (bitemporal) is a safety property, decidable by induction — surrender unearned |
| F-17 | **UNMITIGATED MAJOR** | Mutation set missing M-FAKE-CERT, M-AGGREGATE, M-DEFLATE, M-BIAS, M-SHRUG-RETRY |
| F-18 | **UNMITIGATED MAJOR** | Goodhart trap #4 named not trapped — no aggregation-masking meta-property |
| F-19 | **UNMITIGATED MAJOR** | LIBOR-cessation regression fixture absent |
| F-20 | **UNMITIGATED MAJOR** | Manufactured-payment cross-jurisdiction regression fixture absent |
| F-21 | **UNMITIGATED MAJOR** | Corporate-action cascade (`supersedes`) regression fixture absent |
| F-22 | **UNMITIGATED MAJOR** | Tokenised-collateral chain-reorg regression fixture absent |
| F-23 | **UNMITIGATED MAJOR** | B11 / B12 boundaries lack named generators |
| F-24 | **UNMITIGATED MAJOR** | Spec is a navigation doc; reimplementation from tests requires 4+ files |
| F-25 | MINOR | L7 stratification by CCP-count not stated |
| F-26 | MINOR | L13 compensation-handler totality referenced but not generated |
| F-27 | MINOR | U3 trust-registry mitigation accepted; statistical-inconsistency-within-tolerance gap noted |
| F-28 | MINOR | U4 reframe as storage-integrity surrogate, not unwitnessed law |
| F-29 | MINOR | No mutation budget (mutations/merge, mutations/release) |
| F-30 | MINOR | Leap-second / DST regression fixture absent |
| F-31 | MINOR | CCP migration regression fixture absent |

**Total.** 7 BLOCKING, 17 UNMITIGATED MAJOR, 7 MINOR.

---

## §J — Grade

**C− (Conditional, requires rework before Phase 3 round 2).**

Rationale: the proposal correctly identifies the laws, the boundaries, the fault classes, and the unwitnessed residue. **The architecture of the test program is right.** But the property snippets are illustrative-grade, the unwitnessed surrender is over-broad (2 of 4 are recoverable), the mutation set is incomplete on the highest-severity operators, and **four named historical-bug classes have no regression fixture**. A test suite written to this proposal would pass green while the system was wrong in any of the seven blocking dimensions.

To reach **B+** (acceptable for round 2): close the 7 BLOCKING findings.
To reach **A−** (panel-recommended for arbiter review): close BLOCKING + 12 of 17 UNMITIGATED MAJOR, with named owners and merge-gate property tests.
To reach **A** (Beck's "specification is the test suite"): close all BLOCKING + UNMITIGATED MAJOR + produce the regression fixture corpus E.1–E.6 as version-controlled artefacts.

---

*"Code without tests is bad code. It doesn't matter how well written it is."* — Feathers.
*"Don't write tests. Generate them — and let the shrinker tell you the bug."* — Hughes.
*"The key step is finding a suitable invariant — a state predicate true in all reachable states."* — Lamport.
*"Write tests until fear is transformed into boredom."* — Beck.
*"Broad scope tests should be rare."* — Fowler.

— end Phase 3 Round 1 TESTCOMMITTEE review —
