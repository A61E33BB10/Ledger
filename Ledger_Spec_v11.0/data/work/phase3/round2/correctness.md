# Phase 3 Round 2 — Correctness-Architect closure-check review (independent)

**Reviewer.** Correctness-Architect (Will Wilson — Antithesis), independent fresh-context instance. Did **not** see `phase2/correctness_v2.md`.
**Artefact.** `phase3/round2/proposal_v2.md` (654 lines, dated R2).
**Baseline.** R1 awarded `correctness B+` with 4 BLOCKING findings (A.1, A.2, A.3, B-1) plus Goodhart §C and fault-injection §D requirements.
**Mode.** Closure check + new findings + grade re-issue.

---

## §1. Determinism Audit

The catalogue at `proposal_v2.md §7` enumerates **17 boundaries (B1–B17)**, up from 12 in v1. Verified in v2 lines 290–311.

| # | Boundary | Strategy in v2 | Injectable / Pinned? |
|---|----------|----------------|----------------------|
| B1 | `now()` wall-clock | L19 ClockAuthority | Yes (L19 attest_offset; ADR-4) |
| B2 | RNG entropy | Seeded in workflow input | Yes |
| B3 | Price/FX/vol feed | Snapshot-pinned via L19 (sic — should be L12 or snapshot ID, not L19) | Yes — but textual conflation flagged below |
| B4 | Event oracles | Signal-driven; snapshot-pinned | Yes |
| B5 | Reference data | Bitemporal `as_of` | Yes |
| B6 | Settlement infra | SsiSnapshotRef versioning | Yes |
| B7 | Calibration filter state | `KalmanContinuePayload` v1 | Yes |
| B8 | Workflow scheduling | Temporal-managed | Yes (joint property) |
| B9 | CDM enum universe | L21 `cdm_version` pin | Yes |
| B10 | Hash / canonicalisation | RFC 8785 JCS | Yes (ADR-6, C-A11) |
| B11 | Operator / human | **Append-only public verification keys; HSM rotation discipline** | Yes (ADR-11) |
| B12 | Network reordering | Idempotency key per N4; out-of-order signal handling | Yes |
| B13 | Floating-point | Pinned BLAS / threads / IEEE 754 mode | Yes (NEW) |
| B14 | Storage iter order | Sorted iteration | Yes (NEW) |
| B15 | Intra-handler concurrency | Single-threaded handler | Yes (NEW) |
| B16 | Unicode / locale | NFC; UTF-8; fixed locale | Yes (NEW) |
| B17 | Test-environment seed | Deterministic seed | Yes (NEW) |

**Verdict.** Catalogue grew by 5 (B13–B17). Floating-point determinism (B13), iteration order (B14), and locale (B16) were the three highest-yield boundaries in my experience at FoundationDB; their addition closes the largest replay-determinism gaps that R1 implicitly asserted as out-of-scope. **B11 strengthening (closes A.3) is verified at line 304.**

**Residual gaps** (NEW findings — see §6 below):

- **B-NEW-1: Database transaction-isolation level** is not enumerated as a boundary. If L13 commit happens under one isolation level and replay reads under another, the visible read set diverges. Should be either an axiom of the storage layer (ADR-needed) or a B18.
- **B-NEW-2: Compiler determinism** for native components (executor, pricer). LLVM auto-vectorisation, link-time optimisation, and PGO can produce different floating-point sequences from the same source. Pinning `component_pin` (a git SHA) does not pin the *binary*; reproducible-build chain (deterministic linker, frozen toolchain) is needed. Either add B18 or extend B13.
- **B-NEW-3: Garbage collection / allocator determinism** in JVM/Python/Go components. GC pauses are not bit-affecting, but allocator-driven nondeterministic hash-map iteration order in CPython can affect canonical serialisation if it touches dict iteration. RFC 8785 JCS sorts keys, so this *should* be moot — but only if the canonicaliser is enforced at every serialisation site, including logging and observability paths. Worth one line in §11 versioning algebra.

---

## §2. Property Coverage (Λ1–Λ15 — 15 laws)

The 15 cross-layer laws at `proposal_v2.md §6` (lines 264–286) form a property ramp roughly:

- **Universal/structural** (no crashes, conservation, append-only): Λ2, Λ3, Λ5, Λ6, Λ7, Λ15
- **Safety properties** (consistency, replay, determinism): Λ1, Λ4, Λ8, Λ10, Λ14
- **Domain properties** (no-arbitrage, calibration consistency): Λ11, Λ12
- **Liveness** (Obligation discharge): Λ13
- **Compositional** (forgetful functor): Λ9

**Λ15 Novation Bridge Conservation (NEW)** — verified at line 277: "union-scope or two-tx decomposition with registered bridge `Obligation`". Witnessed. **This closes R1 A.2.**

**Witnessed-via-composition reclassification** (line 286): Λ4 (bounded restatement chain), Λ8 (cosmic-ray ε from erasure-coding), Λ13 (TLA+ + bounded horizon). Surrogate parameters specified per `formalis_v2.md §7`. **Genuinely unwitnessed = 1 (Λ1, vendor opacity).**

**Coverage gaps** (NEW):

- **No explicit property for L18 BreakRegister FSM totality.** The FSM `OPEN → INVESTIGATING → ASSIGNED → AGED-1/3/5 → ESCALATED → AT-RISK → MATERIAL → CLOSED-{CLEAN, ADJ, WAIVED}` (line 483) is a state machine but no Λ asserts that every break reaches a terminal state under bounded staleness. Suggest: **Λ16 BreakRegister Liveness** — every `OPEN` break reaches `CLOSED-*` within `T_break_max` (pinned in L7Pb), with bounded-horizon witness analogous to Λ13.

  ```python
  @hypothesis.given(break_event=gen_break_event(), staleness=st.integers(min_value=0, max_value=T_BREAK_MAX_NS))
  def test_break_register_liveness(break_event, staleness):
      sim = simulate_break_lifecycle(break_event, advance_time=staleness)
      assert sim.terminal_state in {'CLOSED-CLEAN', 'CLOSED-ADJ', 'CLOSED-WAIVED'}
      if sim.terminal_state == 'CLOSED-WAIVED':
          assert sim.four_eyes_attestation is not None
  ```

- **No property tying L17 RegulatorySubmission acknowledgement_status to L13 lineage**. Th-6 (Pillar-3-Projection-Lifting) covers Pillar 3 specifically; what about CFTC/EMIR/SFTR? Suggest a generalised metamorphic property:
  ```python
  @hypothesis.given(submission=gen_regulatory_submission())
  def test_regsub_lineage_invariant(submission):
      reproduced = mu_projection(submission.regulator, submission.rule_set,
                                  L13.up_to(submission.t_known),
                                  L14.up_to(submission.t_known),
                                  L7Pc.up_to(submission.t_known))
      assert canonical_serialise(reproduced) == canonical_serialise(submission.payload)
  ```

- **Λ9 Forgetful-Functor Composition** is named but its oracle ("dependence-relation lattice") is not inlined. testcommittee F-04 was a R1 BLOCKING and the v2 row labels it "Witnessed". I cannot independently verify without reading `correctness_v2.md`; flagging as **partial closure pending arbiter check**.

---

## §3. Conservation Laws

| Law | Scope | Status in v2 |
|-----|-------|--------------|
| Λ5 Per-Event-Class Σ=0 | Per closed event class | Witnessed; type-tagged handler (line 274) |
| Λ6 Mandate-as-Unit | Structurally typed `FeeReserve` | Witnessed (line 275) |
| Λ7 Per-CCP scope | Single CCP | Witnessed; multi-CCP delegated to Λ15 (line 276) |
| **Λ15 Novation Bridge** | Multi-CCP novation | **Witnessed via union-scope or two-tx decomposition with bridge Obligation** (line 277) |

**Λ15 is the right answer to A.2.** The two-tx decomposition (CCP_A → Bridge → CCP_B) preserves per-CCP conservation by introducing an explicit bridging `Obligation` that holds the inter-CCP flow as a typed first-class artefact. This is the construction I'd have suggested.

**Conservation property I'd want to see explicitly stated** (Hypothesis):

```python
@hypothesis.given(novation=gen_multi_ccp_novation())
def test_lambda15_novation_bridge(novation):
    pre_state = ledger_state_before(novation)
    post_state = apply_novation(pre_state, novation)
    # Per-CCP conservation preserved
    for ccp in {novation.ccp_a, novation.ccp_b}:
        assert sum_per_class(post_state, ccp) == sum_per_class(pre_state, ccp) + bridge_delta(novation, ccp)
    # Bridge obligation witnessed
    bridge = post_state.obligations[novation.bridge_id]
    assert bridge.kind == 'NovationBridge'
    assert bridge.discharge_predicate is not None
    # Global Σ = 0 still holds
    assert global_sum(post_state) == global_sum(pre_state)
```

---

## §4. Goodhart traps (5; was 4)

Verified at `proposal_v2.md §14` (lines 533–545). 5 traps with detection mechanisms:

| Trap | Detection mechanism | Verdict |
|------|---------------------|---------|
| GT1 Snapshot stub-swap | Boundary-integrity production test (pull N committed tx; replay; assert byte-identical) | Strong |
| GT2 Mutation set exclusion | 15 mutation operators; mandatory survivor reporting; stratified kill-rate | Strong |
| GT3 Biased generators | First-class coverage targets per stratum (5% near-arb-boundary; 10% deadline-near-fire; 10% multi-CCP; 5% mfg-pay-cross-juris); CI-asserted | Strong |
| GT4 Aggregation-masking | P-CCC-7 meta-property: aggregation tests must pass at every per-class projection | Adequate; would prefer it inlined as code in §6 not deferred |
| **GT5 Type-system witness laundering (NEW)** | **Three-layer defence**: (a) `mypy --strict` + AST lint banning `cast`/`__new__` outside ctor; (b) runtime checker on every write; (c) adversarial Hypothesis test attempting reflection bypass; closed witness inventory (W1–W5) | **Strong — this is the right answer** |

**Mutation operators verified at 15** (line 540): + M-FAKE-CERT, M-AGGREGATE, M-DEFLATE, M-BIAS, M-SHRUG-RETRY (was 10).

**Goodhart sub-finding (NEW — minor):** GT2's "stratified kill-rate target" needs a numeric floor. "Mandatory survivor reporting" without a minimum kill-rate per stratum is itself a Goodhart trap (Goodhart-on-Goodhart): teams will report 0% kill on a stratum with a shrug. Suggest: **per-stratum kill-rate ≥ 80% on universal/structural laws; ≥ 60% on domain properties; surviving mutants on Λ5/Λ6/Λ7/Λ15 are deployment blockers.**

---

## §5. Fault-tolerance / Cluster V silent-corruption harness (closes B-1)

Verified at `proposal_v2.md §8`, line 324:

> | V Smart-contract / move stream (L13) | … | **Bit-flip test** (closes correctness D-1) | Quorum-based commit |

**Closes R1 B-1 in principle.** But the v2 inline is one cell in a 49-cell matrix; the actual harness lives in `correctness_v2.md §3`. From the proposal alone I cannot verify:
- byte-position / bit-flip distribution (uniform random vs targeted at length-prefix / hash-anchor?),
- recovery oracle (does the harness assert that chain verification *fails* on a single-bit flip? Does it test multi-bit flips that escape Hamming distance?),
- "bugification" — adversarial-but-legal corruptions (e.g., replay of an earlier transaction with a stale `prev_hash`).

**C-A12 Cross-replica integrity (NEW conditional)** at line 419 names "Storage operations lead" as owner with detection signal "cross-replica disagreement; erasure-coding integrity test failure" and compensation "restore from quorum; re-replicate". This is the *operational* counterpart to the bit-flip test. Together they form the Λ8 surrogate. **Acceptable.**

**Fault-class coverage (7×7 = 49 cells) inlined at §8 lines 318–326.** All 7 clusters × 7 fault classes have a strategy. This closes halmos M2 / karpathy m2 (R1 §2 line 337).

**NEW FINDINGS on fault catalogue:**

- **F-NEW-1: No Byzantine-attestor harness.** §8 row IV ("Oracle attestations") handles missing/late/duplicated/contradicted/mis-attributed/silent-corruption/partition for honest faults; there is no row for *malicious* attestor (signed valid envelope with deliberately wrong content). C-A3 ("Vendor honesty") has detection via cross-vendor disagreement, but no fault-injection harness simulates a coordinated multi-vendor lie. This is the SBF / FTX failure mode. Recommendation: add column 8 "Byzantine" or row VIII "Adversarial attestor" with quarantine + audit-trail discipline.

- **F-NEW-2: Cluster VII (Orchestration) silent-corruption strategy** is "Hash detect" (line 326). What hashes? L17 / L18 are append-only but BreakRegister (L18) is *mutable* per `break_id`. Mutable + hash-detect is a contradiction unless the hash is over the FSM transition log, not the current state. Worth one sentence of clarification.

- **F-NEW-3: Bugification (R1 D-3) — partial.** GT3's coverage targets (5% near-arb, etc.) constitute *some* bugification. But the R1 ask was specifically "adversarial-legal generators (zero-balance, leap-second, near-singular Hessians)". Of those three, only "near-singular Hessians" maps to the calibration stratum. **No leap-second strategy is named anywhere in v2** despite L19 ClockAuthority carrying `leap_second_policy_version`. This is a real gap — leap-second is a documented production failure mode (multiple major outages 2012, 2015, 2017) and the field has the carrier but no harness. Recommendation: add a leap-second injection harness gated on L19's policy version.

---

## §6. R1 Blocker closure verification

| R1 Blocker | v2 location | Closure status |
|-----------|-------------|----------------|
| **A.1 Λ1 not closed under FSM Stale→Pricing × snapshot retention** | `proposal_v2.md §6` line 270 ("Λ1 Lineage Closure | C-A10 retention promoted to *structural*: every snapshot referenced by non-terminal `ValuationRecord` retained until terminal") | **CLOSED.** Retention promoted from realism-budget axiom to structural invariant. The Stale→Pricing FSM re-entry now has a contractual guarantee that the snapshot it references is retained until the FSM reaches a terminal state. C-A10 still listed at line 417 with extended-retention compensating action. The promotion is the right architectural move. |
| **A.2 Λ5/Λ6/Λ7 not closed under multi-CCP novation** | `proposal_v2.md §6` line 277 (Λ15 Novation Bridge Conservation NEW; closes correctness A.2) | **CLOSED.** Λ15 added; union-scope or two-tx decomposition with registered bridge `Obligation`; witnessed. The two-tx decomposition is structurally correct: it makes the inter-CCP flow a first-class typed artefact rather than a hidden side-effect. |
| **A.3 B11 not closed under HSM key rotation** | `proposal_v2.md §7` line 304 ("B11 | Operator / human interaction | Append-only verification keys; HSM rotation discipline (closes correctness A.3)"); ADR-11 line 589 | **CLOSED.** Append-only public verification keys, with rotation adding a new key and never removing the old. This is the only shape that supports replay re-verification of envelopes signed under historical keys. ADR-11 documents it. |
| **B-1 No fault-injection harness for Cluster V silent-corruption** | `proposal_v2.md §8` line 324 ("V … | **Bit-flip test** (closes correctness D-1) | Quorum-based commit"); C-A12 line 419 (cross-replica integrity NEW) | **PARTIALLY CLOSED.** The bit-flip test is named at the right cell of the fault matrix and has an operational compensating control (C-A12). But the proposal v2 alone does not show the harness's bit-position distribution, multi-bit coverage, or adversarial-replay strategy; the detail lives in `correctness_v2.md §3`. **Conditional close** pending arbiter verification of the harness specification. |

**Three closed; one partially closed (pending arbiter verification of harness in companion file).**

---

## §7. Realism budget — 12 conditional (was 10)

Verified at `proposal_v2.md §10.2` lines 406–419.

- **C-A11 canonical-serialiser stability (NEW)** — line 418. Detection: RFC 8785 JCS test-suite drift, cross-implementation hash mismatch. Compensation: pin `canonicalisation_version`. Owner: TEMPORAL canonicalisation owner. Blast radius: every cross-implementation replay claim becomes rhetorical.
- **C-A12 cross-replica integrity (NEW; for Λ8 cosmic-ray surrogate)** — line 419. Owner: Storage operations lead. Detection: cross-replica disagreement, erasure-coding integrity test. Compensation: restore from quorum, re-replicate. Blast radius: bit-flip undetected, replay produces phantom answers.

Both NEW conditionals address the gaps R1 flagged. **C-A1 / C-A2 remain OPEN** (production deployment blocked on assignment per nazarov M-2). This is correctly flagged at line 408; not a v2 regression.

---

## §8. NEW Findings (issued by this reviewer)

### N-CORR-1 (UNMITIGATED MAJOR) — Bit-flip harness specification not inlined
The closure of R1 B-1 depends on `correctness_v2.md §3`. The proposal v2 inlines a 1-cell entry in the 49-cell matrix; the harness's bit-position distribution, multi-bit coverage, and adversarial-replay strategy are not visible from the proposal alone. **Required:** either inline a 5-line specification of the bit-flip test in §8, or have the arbiter explicitly load `correctness_v2.md §3` before approving B-1 closure.

### N-CORR-2 (UNMITIGATED MAJOR) — No leap-second injection harness
L19 ClockAuthority carries `leap_second_policy_version` (line 169) but no fault-injection cell in §8 names a leap-second harness. This is a documented production failure mode (multiple 2012/2015/2017 outages). **Required:** add a leap-second injection harness gated on L19 policy version.

### N-CORR-3 (UNMITIGATED MAJOR) — No Byzantine-attestor harness
§8 row IV handles honest-fault attestation classes but no harness simulates a coordinated multi-vendor false attestation (the FTX-style failure). C-A3 names the assumption; no fault-injection class kills it. **Required:** add Byzantine-attestor cell or row to §8 fault catalogue with quarantine + audit-trail discipline.

### N-CORR-4 (UNMITIGATED MAJOR) — Λ16 BreakRegister Liveness missing
L18 has a 10-state FSM but no Λ asserts every `OPEN` break reaches a terminal state within bounded time. Should be Λ16 with bounded-horizon witness analogous to Λ13 (TLA+ + production observability).

### N-CORR-5 (UNMITIGATED MAJOR) — GT2 stratified kill-rate has no numeric floor
"Mandatory survivor reporting" without a per-stratum minimum kill-rate is itself a Goodhart trap. **Required:** per-stratum kill-rate ≥ 80% on universal/structural laws (Λ2, Λ3, Λ5, Λ6, Λ7, Λ15), ≥ 60% on domain properties (Λ11, Λ12); surviving mutants on conservation laws are deployment blockers.

### N-CORR-6 (MAJOR) — Database isolation level not in B-catalogue
B14 covers iteration order; B-NEW (database transaction-isolation level for L13 commit / replay reads) is not enumerated. If L13 commit happens at SERIALIZABLE and replay reads at SNAPSHOT, the visible read set diverges. **Required:** B18 isolation-level pin OR explicit ADR that L13 is single-writer and isolation level is moot.

### N-CORR-7 (MAJOR) — Compiler / link-time determinism out of B-catalogue
B13 pins BLAS/threads/IEEE-754 mode at runtime. It does not pin the *binary*: LLVM auto-vectorisation, LTO, and PGO can produce different floating-point sequences from the same source. `component_pin` is a git SHA, not a binary digest. **Required:** either extend B13 with reproducible-build chain (deterministic linker + frozen toolchain + binary digest) or add B19.

### N-CORR-8 (MINOR) — B3 wording conflates L19 with snapshot
Line 296 says B3 "External price/FX/vol feeds | Snapshot-pinned via L19". L19 is ClockAuthority; price feeds are pinned via L9/L12 snapshots, not L19. Either a typo or a wording infelicity. Replace "via L19" with "via L9/L12 snapshot ID; wall-clock pin via L19".

### N-CORR-9 (MINOR) — Λ9 oracle not inlined
Λ9 Forgetful-Functor Composition is labelled "Witnessed" with note "dependence-relation lattice (closes testcommittee F-04)". The oracle is in `correctness_v2.md §1`. From proposal alone I cannot verify the lattice is well-formed. Conditional pass; arbiter must verify.

### N-CORR-10 (MINOR) — Cluster VII silent-corruption "Hash detect" ambiguity
Line 326: L18 BreakRegister is mutable per `break_id`; "Hash detect" without specifying *what* is hashed (FSM transition log? current state snapshot?) leaves a contradiction. Worth one clarifying sentence.

---

## §9. Grade

**v1 (R1) grade.** B+ (with 4 BLOCKING findings stipulated).

**v2 grade. A−.**

**Rationale.**
- Three R1 BLOCKING findings are cleanly closed (A.1 retention promotion is structurally correct; A.2 Λ15 with bridge Obligation is the right architecture; A.3 append-only verification keys + ADR-11 is the only sound rotation discipline).
- One R1 BLOCKING (B-1) is partially closed at the proposal layer but conditionally closed pending arbiter inspection of `correctness_v2.md §3` harness detail.
- Determinism boundary catalogue grew 12 → 17 with three high-yield additions (B13/B14/B16); two further boundaries are arguably needed (compiler determinism, isolation level) but the catalogue is now defensible at structural rather than rhetorical level.
- 15 cross-layer laws with **1 genuinely unwitnessed** (was 4 unwitnessed) and explicit composition witnesses for the rest is a major correctness improvement.
- 5 Goodhart traps with detection mechanisms close §C; mutation operators 10 → 15 close §D mutation requirements.
- 12 conditional realism-budget items with detection / compensation / blast-radius per assumption (C-A11, C-A12 NEW) close T11.
- Goodhart hardening at GT5 (type-system witness laundering, three-layer defence) is the *single most important* improvement — it kills the dominant rhetorical failure mode of phantom-type Python.

**Why not A.** Ten new findings (one UMAJOR cluster on bit-flip harness inlining, one each on leap-second, Byzantine-attestor, Λ16 liveness, kill-rate floor; plus four MAJOR/MINOR on isolation level, compiler determinism, B3 wording, Λ9 oracle inlining, Cluster VII hash ambiguity). None is a closure-failure, but together they show the proposal is **closed against R1 but still ahead of where v3 needs to land**. A clean A requires:
1. Inline the bit-flip harness specification (5 lines is enough).
2. Add a leap-second injection cell.
3. Add a Byzantine-attestor row to §8 fault catalogue.
4. Add Λ16 BreakRegister Liveness as a cross-layer law.
5. Numeric kill-rate floors in GT2.
6. Resolve the compiler-determinism / isolation-level boundary questions.

**Convergence stance.** R2 has reached B-grade unblock per R1's own §6 path: every theme T1–T12 + 4 correctness blockers addressed. The grade improvement from B+ to A− reflects (i) blocker closure, (ii) substantive structural improvements (Λ15, retention promotion, witness inventory), (iii) measurable witness reduction (4 unwitnessed → 1). The remaining ten findings are unmitigated-major / minor in R1's vocabulary; under FORMALIS "zero blocking, zero unmitigated major" criterion, **R3 is needed for full convergence**. Recommendation: address N-CORR-1 through N-CORR-5 in R3; the remaining four can be deferred with documented rulings.

---

## §10. Required actions for R3 (prioritised)

1. **Inline 5-line bit-flip harness spec in §8** (closes N-CORR-1, completes B-1 closure).
2. **Add leap-second injection cell to §8** with reference to L19 leap_second_policy_version (closes N-CORR-2).
3. **Add Byzantine-attestor row VIII or column 8 to §8** (closes N-CORR-3).
4. **Add Λ16 BreakRegister Liveness** to §6 with bounded-horizon witness (closes N-CORR-4).
5. **Add per-stratum kill-rate numeric floors to GT2** (closes N-CORR-5).
6. **Resolve compiler-determinism and isolation-level boundary questions** in §7 + §11 versioning algebra (closes N-CORR-6, N-CORR-7).
7. **Clarify B3 wording (L9/L12 vs L19)** (closes N-CORR-8).
8. **Inline Λ9 lattice oracle definition** (closes N-CORR-9).
9. **Clarify Cluster VII hash-detect target** (closes N-CORR-10).

---

*End of correctness-architect closure-check. Independent review; did not consult `phase2/correctness_v2.md`.*
