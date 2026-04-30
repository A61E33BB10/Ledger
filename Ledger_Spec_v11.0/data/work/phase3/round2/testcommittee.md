# TESTCOMMITTEE — Phase 3 Round 2 Closure Review of `proposal_v2.md`

**Reviewer.** Independent TESTCOMMITTEE panel (Beck / Hughes / Fowler / Feathers / Lamport).
**Artefact under review.** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/work/phase3/round2/proposal_v2.md` (654 lines).
**Reference.** R1 consolidated findings, `phase3/round1/R1_consolidated_findings.md`.
**R1 verdict (testcommittee).** C−.
**Mode.** Closure check on R1 BLOCKING set + new findings.

---

## §1. Closure of R1 BLOCKING findings

For each R1 testcommittee BLOCKING finding: **CLOSED / PARTIALLY CLOSED / FAILS TO CLOSE** with citation in v2.

### F-01 — L1 oracle too weak; constant-stub passes

**Status.** **FAILS TO CLOSE (worse than R1).**

**Citation in v2.** §6 row Λ1 (line 270): "C-A10 retention promoted to structural: every snapshot referenced by non-terminal ValuationRecord retained until terminal" + classification "**Genuinely unwitnessed** under vendor opacity (surrogate: trust registry + threat model + multi-source consensus); accepted as architectural risk per Λ7 owner". §15.3 (line 563) confirms.

**Why this fails.** The R1 finding was that the L1 oracle (Lineage Closure) is constant-stub-passable. v2 does not give the L1 oracle a predicate; it instead **promotes Λ1 to "genuinely unwitnessed"** and accepts vendor opacity as architectural risk. This converts a *test* problem into a *governance* problem. A constant-stub still passes — the proposal merely renames the constant-stub-passing as "accepted residual risk." Beck: "renaming a vacuous test as 'unwitnessed' does not make it less vacuous." There is no oracle text in v2 that a reimplementer could compile.

**Required for closure.** State the L1 lineage-closure oracle as a decidable predicate over `(L14[≤t_known], snapshot_store, retention_horizon)` and assert the test fails when retention is violated by N transactions. The "structural promotion of C-A10" is an *architectural commitment*, not an oracle.

---

### F-02 — L4 oracle tests `read==read`, not bitemporal predicate

**Status.** **PARTIALLY CLOSED.**

**Citation in v2.** §6 row Λ4 (line 273): "reclassified **witnessed-by-induction over bounded restatement chain** `κ_restate` pinned in L7Pb". §2 gives concrete `Bitemporal<T>` API with `as_of` and `with_corrections_through` (lines 80–110); §10.2 line 401 binds C-A10 retention.

**Why partial.** The direction is correct — Λ4 is now claimed safety-by-induction, not unwitnessed — and §2 provides the predicates over which induction would proceed (`t_obs ≤ t_known`, `restate_link` chain, mode-a/mode-b queries). However the proposal **does not exhibit the induction step** in v2 itself; it gestures to `formalis_v2.md §7` and `correctness_v2.md §1`. The bitemporal predicate **chain monotonicity** (every restate_link points to an earlier `t_known`; the chain has depth ≤ κ_restate) is not stated as the test oracle. The reviewer has to take it on faith that the deferred file has it.

**Required for closure.** In §6 Λ4 row, state the oracle precisely: `∀ R_n ∈ restatement_chain(R_0): t_known(R_{n}) ≥ t_known(R_{n-1}) ∧ depth ≤ κ_restate ∧ as_of(t) is monotone in t`. Pin κ_restate concretely (e.g., "κ_restate = 64 per L7Pb"); v2 says only that κ_restate "is pinned" without naming the bound.

---

### F-03 — L6 omits HWM-cross-mandate-collapse fixture

**Status.** **FAILS TO CLOSE.**

**Citation in v2.** None. `grep -i "HWM\|hwm\|cross-mandate"` over v2 returns zero matches. §4.5 SBL sub-leaf register (line 209) lists 14 sub-leaves but no HWM fixture; §6 Λ6 row (line 275) says "structurally-typed FeeReserve" but not the cross-mandate-collapse failure mode; §14 GT4 (line 542) names aggregation-masking meta-property but does not exhibit the fixture.

**Why this fails.** The R1 finding required a *named, version-controlled fixture* exercising the HWM-cross-mandate collapse case. v2 does not contain it and does not cite it in any companion artefact list (§Appendix A, line 636).

**Required for closure.** Add an entry under §14 (or new §14a "Regression fixture corpus") explicitly naming the HWM-cross-mandate-collapse fixture as a CI-required artefact, owner, file path.

---

### F-04 — L9 `referentially_independent` predicate undefined → vacuous pass

**Status.** **PARTIALLY CLOSED (gestural).**

**Citation in v2.** §6 row Λ9 (line 279): "Forgetful-Functor Composition | dependence-relation lattice (closes testcommittee F-04) | Witnessed".

**Why partial.** v2 claims closure — "(closes testcommittee F-04)" — but the actual *content* is the phrase "dependence-relation lattice." This is a gesture toward a structure, not a predicate. The R1 finding required: (a) define the predicate; (b) partition test inputs by the lattice; (c) demonstrate the partition is non-trivial (i.e., shrinking actually lands in distinct cells). v2 gives only (a) by naming a structure and asserting "Witnessed" without showing the lattice's elements, partial order, or join/meet. The proposal cites `correctness_v2.md §1` for detail. A reimplementer cannot construct the test from §6 row Λ9 alone.

**Required for closure.** Inline (or cite a precise §) the lattice's elements and the partition predicate. State the four canonical inputs that should land in four distinct cells.

---

### F-05 — L12 generator rejection-samples into Θ_AF then asserts in-region

**Status.** **CLOSED at headline; INSUFFICIENT for execution.**

**Citation in v2.** §6 row Λ12 (line 282): "Hamiltonian-MC sampler (replaces rejection — closes testcommittee F-05)". §9 Theorem 5 hypotheses (lines 376–381) define Θ_AF as model-versioned closed type.

**Why "closed at headline."** Hughes: replacing rejection with HMC is the right architectural move, and naming HMC concretely is more than v1 gave. However the v2 proposal does not specify (i) the HMC step size / leapfrog parameters / acceptance target, (ii) the burn-in length, (iii) the mixing diagnostic that gates the test (Gelman-Rubin R̂ < 1.01 or equivalent). Without these, an implementer can write an HMC sampler that mixes poorly and produces the same biased generator the proposal aimed to eliminate. **A poorly-tuned HMC is a slow rejection sampler.**

**Required for full closure.** Pin (i)-(iii) in §6 row Λ12 or in `correctness_v2.md`; add to L7Pb tolerance pins.

---

### F-06 — No per-stratum coverage targets

**Status.** **CLOSED.**

**Citation in v2.** §14 GT3 (line 541): "First-class coverage targets per stratum: 5% near-arbitrage-boundary; 10% deadline-near-fire; 10% multi-CCP; 5% manufactured-payment-cross-jurisdiction. CI-asserted".

**Verdict.** Concrete percentages stated; CI-asserted claim made. Beck: this is a real specification a CI job can enforce. Caveats (raised as new findings below): (a) only four strata named; the R1 brief implied more (e.g., LIBOR cessation, corporate-action cascade, tokenised-collateral chain reorg from R1 §3 finding 25 — line 417 of R1 doc); (b) no stratum for **arbitrage-far-from-boundary** baseline, so the test cannot detect "all 5% landed but everywhere else is empty."

---

### F-07 — No declared test pyramid

**Status.** **FAILS TO CLOSE.**

**Citation in v2.** None. `grep -i "pyramid\|test count\|test target\|level 1\|level 2"` over v2 returns no matches in a testing context. §14 lists Goodhart traps but not pyramid shape; §17 lists 9 verification checks but not per-layer counts.

**Why this fails.** The R1 finding required a declared pyramid with target counts per layer (unit / property / integration / characterisation / invariant). v2 omits this entirely. Fowler: "the whole point of the test pyramid is to remind us broad-scope tests should be rare" — without a declared pyramid, the proposal cannot demonstrate it has not inverted to an ice-cream cone.

**Required for closure.** Add a §14a "Test Pyramid" with per-layer counts: e.g., L1 unit (target N_u), L2 property (target N_p with strata), L3 integration (target N_i), L4 characterisation (target N_c), L5 invariant verification / TLA+ (target N_v).

---

### F-15 / F-16 — 2 of 4 unwitnessed laws are recoverable (TLA+ for liveness; induction for bitemporal)

**Status.** **CLOSED.**

**Citation in v2.** §6 line 286: "**1 genuinely unwitnessed** (Λ1, vendor opacity ...) + **3 witnessed-via-composition** (Λ4 bounded restatement chain; Λ8 erasure-coding ε; Λ13 TLA+ + bounded horizon)". §15.3 (line 561) confirms.

**Verdict.** Reclassification is concrete and matches the R1 prescription exactly. Λ13 TLA+ Büchi automaton + bounded-horizon simulation is named (line 283); Λ4 induction over bounded chain is named; Λ8 erasure-coding ε is named. Lamport: this is the right structure. Caveat: the named surrogate parameters (κ_restate, (n, k, ε), T_max, N_handler) are **listed** in §17 verification checks (line 601) but **not concretely valued** in the proposal — e.g., "T_max = ?", "(n, k) = ?". Until valued, the witnesses are still abstract.

---

## §2. Closure scoreboard

| # | Finding | Status | Severity post-v2 |
|---|---------|--------|------------------|
| F-01 | L1 oracle constant-stub | **FAILS TO CLOSE** | BLOCKING |
| F-02 | L4 bitemporal predicate | **PARTIALLY CLOSED** | UNMITIGATED MAJOR |
| F-03 | L6 HWM-cross-mandate fixture | **FAILS TO CLOSE** | BLOCKING |
| F-04 | L9 dependence-relation predicate | **PARTIALLY CLOSED (gestural)** | UNMITIGATED MAJOR |
| F-05 | L12 HMC sampler | **CLOSED at headline; tuning unspecified** | UNMITIGATED MAJOR |
| F-06 | Per-stratum coverage targets | **CLOSED** | (none) |
| F-07 | Declared test pyramid | **FAILS TO CLOSE** | BLOCKING |
| F-15/16 | Unwitnessed-law reclassification | **CLOSED (with surrogate-value gap)** | MINOR |

**Closure rate.** 2 of 8 fully closed (25%); 3 partial; 3 fail. R1 prescriptions only partially absorbed.

---

## §3. New findings against v2

### N-01 BLOCKING — Mutation operators named, kill-rate targets not specified

**Citation.** §14 GT2 (line 540): "15 mutation operators (was 10): + M-FAKE-CERT, M-AGGREGATE, M-DEFLATE, M-BIAS, M-SHRUG-RETRY. **Mandatory survivor reporting with stratified kill-rate targets**".

**Defect.** The phrase "stratified kill-rate targets" appears with no actual numbers. By contrast GT3 (per-stratum coverage) gives concrete percentages. The mutation kill-rate target is the load-bearing metric — without "≥80% per operator class" or similar, mutation testing is theatre. Feathers: a unit-test suite without a kill-rate target tells you nothing about its discriminating power.

**Required.** Add concrete kill-rate targets per operator family. The TESTCOMMITTEE charter specifies > 80%; v2 must either adopt or justify a different number.

---

### N-02 BLOCKING — Oracle text deferred to companion files; proposal alone is not sufficient to reimplement tests

**Citation.** §6 (lines 264–286) — every Λ-law row gives a 1-line "strengthened oracle" but the test predicate, generators, and shrinking strategy live in `correctness_v2.md §1`, `formalis_v2.md §7`. §17 line 600 says "All R1 BLOCKING findings closed — cite finding ID at each section" but the proposal cites the companion files for the actual oracle content.

**Defect.** Beck's First Commandment of testing: tests are normative. If the proposal cannot be read alone to derive the test suite, the proposal is descriptive, not normative. v2 explicitly lists 7 specialist files in Appendix A (line 636) as load-bearing. A reimplementer would need to read all 7. This violates the R1 T3 BLOCKING finding (proposal as navigation document, not specification).

**Required.** Inline the actual oracle predicates for at least the 15 Λ-laws (one per row, one paragraph each), not the 1-line summary table.

---

### N-03 BLOCKING — Determinism-boundary catalogue lacks per-boundary test

**Citation.** §7 (lines 290–310) catalogues 17 boundaries (B1–B17) with strategy phrases. No row names a test that fails when the strategy is not in force.

**Defect.** Each "Strategy" cell is operational ("Pinned PRNG seed in workflow input") not testable ("PRNG seed test: assert workflow output is bit-identical when seed is fixed and input is fixed"). B13 (floating-point), B15 (intra-handler concurrency), B16 (Unicode/locale) are particularly prone to silent violation. With no per-boundary characterisation test, the boundary catalogue is a list of intentions.

**Required.** For each B# add a "Test name" column: `det_test.py::test_B<n>_<predicate>`. Determinism violations must fail CI, not lurk.

---

### N-04 UNMITIGATED MAJOR — GT5 three-layer defence not gated by a meta-test

**Citation.** §14 GT5 (line 543): "Three-layer defence: (a) type system + `mypy --strict` + custom AST lint banning `cast` / `__new__` outside ctor module; (b) runtime checker on every write attempt; (c) adversarial Hypothesis test attempting reflection / `__post_init__` bypass".

**Defect.** The three layers are named but no meta-test demonstrates that the *adversarial* layer (c) actually exercises bypass attempts. A trivial `@given(st.nothing())` Hypothesis test technically attempts adversarial bypass and passes vacuously. Goodhart's Law applies recursively to anti-Goodhart tests.

**Required.** Add a meta-property: the adversarial Hypothesis test must report at least K failed bypass attempts per CI run (proving it exercised the witness boundary).

---

### N-05 UNMITIGATED MAJOR — Λ8 cosmic-ray surrogate has ε named, value not pinned

**Citation.** §6 line 278: "Λ8 Replay Determinism | three-engine, adversarial-completion, bit-identical-pricer oracle ... | Witnessed via composition (cosmic-ray ε bound from erasure-coding)". §10.2 row C-A12 (line 419) names cross-replica integrity but no ε value.

**Defect.** The R1 prescription was "ε function of erasure-coding parameters (n, k)". v2 names the function but does not pin (n, k); without a value, the bound is symbolic. Hughes: a property-based test cannot run on a symbolic bound.

**Required.** Pin (n, k, ε) concretely in L7Pb or §11 versioning algebra `refdata_pin`.

---

### N-06 MINOR — Goodhart trap GT4 (aggregation-masking) names a meta-property not exhibits one

**Citation.** §14 GT4 (line 542): "P-CCC-7 meta-property: aggregation tests must pass at every per-class projection, not only globally".

**Defect.** P-CCC-7 is named; its concrete predicate is not stated. R1 testcommittee C.4 specifically asked for a meta-property test in the property catalogue. The "P-CCC-7" reference is a forward reference to `correctness_v2.md`.

**Required.** Inline the meta-property predicate, even if one line: `∀ EventClass c: aggregation_invariant(restrict_to(c)) holds AND aggregation_invariant(global) holds`.

---

## §4. Pyramid declaration check (per request)

**Result.** No pyramid declaration in v2. Per-layer counts absent. F-07 fails to close.

## §5. Per-stratum coverage targets (concretely numbered?)

**Result.** Yes — §14 GT3 gives concrete percentages (5%, 10%, 10%, 5%) for four strata. Caveats (N-06): only four strata; baseline "far from boundary" missing; LIBOR cessation / corporate-action cascade / tokenised-collateral fixtures missing.

## §6. Are the strengthened oracles actually decidable?

**Λ1 (Lineage Closure).** No — surrendered to "genuinely unwitnessed."
**Λ2 (Snapshot Determinism).** Yes — content-addressed bit-identical replay test is decidable.
**Λ3 (Settlement-Move Closure).** Yes — bijection between settlement instruction and move-stream segment; decidable per-instruction.
**Λ4 (Bitemporal Coherence).** Conditionally — induction is decidable IF κ_restate is pinned (it is not in proposal_v2; deferred).
**Λ5 (Per-Class Conservation).** Yes — Σ=0 per class is structurally decidable.
**Λ6 (Mandate-as-Unit Conservation).** Yes — structurally typed.
**Λ7 (Per-CCP Conservation Scope).** Yes.
**Λ8 (Replay Determinism).** Conditional on ε being pinned (N-05).
**Λ9 (Forgetful-Functor Composition).** No — "dependence-relation lattice" gestural; predicate not given.
**Λ10 (Workflow-History Replay).** Yes — `tx_id` formula stated.
**Λ11 (Calibration / Valuation Consistency).** Yes — metamorphic catalogue named (vega convexity, forward-rate, AD-vs-bump, local-vol round-trip), each individually decidable.
**Λ12 (No-Arbitrage Admissibility).** Conditional on HMC tuning being pinned (F-05).
**Λ13 (Obligation Liveness).** Conditional on T_max + N_handler being pinned.
**Λ14 (Capability-Scope Closure).** Yes — runtime-checked phantom witness.
**Λ15 (Novation Bridge Conservation).** Yes — union-scope or two-tx decomposition is structural.

**Decidability score.** 8 of 15 fully decidable as stated; 5 conditional (waiting on parameter pins); 2 not decidable (Λ1 surrendered, Λ9 gestural).

---

## §7. Grade

**Grade: C+ (was C− in R1).**

**Rationale.**

**Movement up (C− → C+):**
- Genuine progress on F-15/F-16 (unwitnessed-law reclassification) — exactly the R1 prescription absorbed.
- F-06 closed cleanly with concrete percentages.
- F-05 (HMC) named at headline; structure is right.
- 15 mutation operators including the five named additions.
- GT5 (witness-laundering) added with three-layer defence.
- §11 Versioning Algebra and §12 Operational Floor materially improve the testable-surface area.

**Held back from B-:**
- F-01 *fails to close* — surrender, not a fix.
- F-03 *fails to close* — fixture corpus still absent.
- F-07 *fails to close* — pyramid declaration entirely missing.
- F-02, F-04 partial / gestural — oracle predicates not inlined.
- N-01 BLOCKING — mutation kill-rate targets unstated.
- N-02 BLOCKING — proposal still navigates to companion files for load-bearing oracle text.
- 5 of 15 Λ-oracles depend on parameter pins not yet committed.

**Convergence verdict.** **NOT CONVERGED.** 4 BLOCKING (F-01, F-03, F-07, N-01, N-02 — count 5) + 4 UNMITIGATED MAJOR (F-02, F-04, F-05, N-04, N-05 — count 5) remain open. R3 must:

1. Convert F-01 from surrender to surrogate-with-decidable-oracle (e.g., trust-registry consistency property).
2. Inline an explicit fixture corpus list, including HWM-cross-mandate-collapse and the four R1-named historical bugs.
3. Add §14a Test Pyramid with per-layer target counts.
4. Pin mutation kill-rate targets (≥ 80% per operator family).
5. Inline Λ-oracle predicates (one paragraph each) into §6 rather than deferring to companion files.
6. Pin all surrogate parameter values: κ_restate, (n, k, ε), T_max, N_handler, HMC step / leapfrog / R̂.

**Beck's closing observation.** *"Tests are the specification."* v2 has improved the architectural-commitment layer; it has *not* improved the test-as-specification layer to the point a reimplementer could build the suite. Until §6 oracles are inlined and the pyramid is declared, this remains a navigation document for tests, not a specification.

— TESTCOMMITTEE (Beck / Hughes / Fowler / Feathers / Lamport)
