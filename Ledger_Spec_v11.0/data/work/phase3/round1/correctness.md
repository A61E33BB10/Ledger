# Phase 3 Round 1 — Correctness-Architect Adversarial Review of `phase2/proposal_v1.md`

**Reviewer.** Independent correctness-architect instance (Will Wilson stance: determinism + property primacy + state-space exploration + declarative correctness). The Phase-2 `correctness.md` was authored by a separate instance — I treat it as **input under audit**, not as my own work.

**Posture.** I am asked: are the 14 cross-layer laws closed under composition with the executor + valuation FSM + settlement layer? Are the 4 Goodhart traps actually avoided? Is the 12-boundary determinism catalogue exhaustive? Which laws need fault-injection that the proposal lacks the harness for?

**Verdict preview.** **Conditional pass with 3 BLOCKING and 7 UNMITIGATED-MAJOR findings.** The integration is *coherent*, but it is **not closed under composition** in three load-bearing places, the boundary catalogue has structural omissions, and the witnessing program inherits Goodhart traps it claims to defend against. Grade in §F.

---

## §A. Closure-under-composition audit (the 14 laws × executor × valuation FSM × settlement layer)

I attack each law by asking: *given this law's pre/post-condition, does composing the executor's commit semantics + the valuation FSM's transition rules + the settlement layer's external boundary preserve the law, or are there interleavings where the postcondition is violated even though every per-component invariant holds?* Closure is the only property that justifies aggregating laws into a single ledger guarantee.

### A.1 BLOCKING — L1 (Lineage Closure) is **not closed** under valuation-FSM `Stale → Pricing` re-entry

**Failure scenario.** L13 `ValuationRecord` carries `attestation_snap` (FK to L19) per §3.5. The valuation FSM (val v1.0 §6.5) admits `Stale → Pricing` when freshness recovers. If the executor commits a hedge `pending_tx` derived from a `ValuationRecord` whose `attestation_snap` references a snapshot that was *garbage-collected* between the original FIRM emission and the `Stale → Pricing` re-entry (TEMPORAL §6.2 explicitly admits ContinueAsNew payload elision), then the L1 closure walk reaches a leaf with no signed envelope. **Per-component invariants all hold** (the snapshot store enforced its retention contract; the FSM transitioned legally; the executor verified `tx_id` integrity). The composed law fails.

**Why proposal misses it.** §4 row L1 marks witnessed under "finite move histories"; no row in §3 fault catalogue Cluster VI or Cluster V tests *snapshot retention horizon × FSM re-entry* as a joint fault. §8 Theorem 2 (Replay Determinism Lifting) assumes snapshot determinism but does *not* assert the snapshot store's retention horizon is a ledger invariant — only an "operational" one (NAZAROV C-A10).

**Required fix (BLOCKING).** Promote retention sufficiency from a *conditional assumption* (C-A10) to a **structural invariant** of the closed system: every snapshot referenced by a non-terminal `ValuationRecord` MUST be retained until that record reaches a terminal lifecycle state. Add a fault-row *(VI, retention-violated-during-FSM-reentry)* with detection = pre-commit lineage walk, recovery = block FSM transition, escalation = ALERT.

### A.2 BLOCKING — L5/L6/L7 conservation is **not closed** under multi-CCP novation

**Failure scenario.** Per §3.3 L9, PositionState carries `ccp_binding`; per L7 the conservation scope is per-CCP. CDM `BusinessEvent ∈ {Novation, ClearingNovation}` legally re-binds a contract from CCP_A to CCP_B in a single atomic event. The executor commits one transaction with `StateDelta`s in two distinct conservation scopes. `∑_w Δ ac(w, u, CCP_A) = -X` and `∑_w Δ ac(w, u, CCP_B) = +X` — **per-CCP closure fails by design** for this single transaction; only a *cross-CCP* conservation law catches it. The proposal's L7 explicitly forbids cross-CCP aggregation.

**Why proposal misses it.** §3.5 L14 says "single-writer (executor)" and §8 Theorem 1 assumes "handler-class type-tagging is enforced". But ClearingNovation is *one* CDM event class crossing two scopes. The proposal does not name a *bridging* conservation invariant. §4 P-L7 generator `gen_cleared_unit` does not stratify across CCP boundary changes.

**Required fix (BLOCKING).** Either (a) add L15 *Novation Bridge Conservation*: for `BusinessEvent ∈ Novation_Set`, conservation holds in the *union* scope and is permitted to fail per-component scope; OR (b) split novation into two atomic transactions with an explicit bridge `Obligation` recording the gap. Choice (a) is cleaner; it requires an explicit law, not a silent exception.

### A.3 BLOCKING — Boundary B11 (operator/human) is **not closed** under signature-key rotation

**Failure scenario.** B11 says "captured attestation is replayed; the human's uncaptured deliberation is not." Replay verifies signatures against a *historical key registry* (B4). When an HSM key is rotated and the **old key is destroyed** (HSM custody discipline C-A2 *requires* key destruction on rotation in many regimes), replaying an old envelope past rotation **cannot re-verify**. The proposal's L1 demands `signature_verified()` per `walk_lineage`; under key destruction, L1 *forces* lineage walks to fail on every commit older than the rotation horizon.

**Why proposal misses it.** §2 B4 says "reverify signature against the historical key registry (D10.3, FORMALIS)" — but does not assert keys are *retained* indefinitely. §6 C-A2 names HSM discipline as conditional but does not enumerate "keys must outlive any envelope they signed" as a derived obligation.

**Required fix (BLOCKING).** State explicitly: **public verification keys are append-only; rotation means adding a new key, never removing the old**. Document this as the cryptographic contract the data layer requires from the security layer. If the security layer cannot make that promise, B11 replay is *structurally* broken and L1 cannot close.

---

## §B. Determinism boundary catalogue — exhaustiveness audit

The proposal claims **12 boundaries**. I find at least **5 omissions** that admit non-determinism unaccounted for. Anything reaching a handler that is not on this list is, by the proposal's own §2 closing line, "a non-deterministic boundary I have failed to enumerate".

### B.1 UNMITIGATED MAJOR — Floating-point math (B13)

`ValuationRecord` is computed by pricing code; many pricers use IEEE-754 double precision, not Decimal. IEEE-754 ops are **not associative**; thread scheduling, vectorisation, FMA fusion, and BLAS implementation choice all produce bit-different results from "the same input". §4 P-L2 uses Mahalanobis tolerance; P-L8 demands *bit-identical* replay. These are inconsistent unless every pricer is either Decimal-only or run under a determinism-pinned BLAS.

**Required fix.** Add B13 (numerical determinism boundary). Captured by: BLAS implementation pin in L21 + thread count pin + `fp:strict` compile flag. Replay: pin or fail.

### B.2 UNMITIGATED MAJOR — Persistent storage iteration order (B14)

L8/L9 reads from PositionState are sets of `(w, u)` rows. RocksDB / Postgres / etc. **iteration order depends on internal compaction state, table fragmentation, page layout**. Any handler that iterates a position set and feeds the iteration into a hash (`tx_id` derivation) is non-deterministic across replicas even with bit-identical commits. The proposal mentions canonicalisation rule (B10) but does not say it is applied at every aggregation point inside a handler.

**Required fix.** Add B14. Mandate: every set/map iteration in handler code is preceded by canonical sort. Property: `gen_state_with_two_storage_engines` and check `tx_id_engine_A == tx_id_engine_B`.

### B.3 UNMITIGATED MAJOR — Concurrency / scheduling inside handlers (B15)

The executor is "single-writer" but a *handler* invocation may legitimately fire concurrent activity calls (e.g., enrich SSI in parallel with party master lookup). Activity completion order is non-deterministic at the worker level; Temporal serialises via workflow history but the *handler's reduction* of those results may use `asyncio.as_completed` or the equivalent — feeding completion order into the output. This is the classic FoundationDB-discovered class of bug.

**Required fix.** Add B15 (intra-handler concurrency). Mandate: every multi-result reduction is over a canonical order (sort by activity_seq, never by completion). Property: simulator delivers activity completions in adversarial orders.

### B.4 MAJOR — Locale / encoding / Unicode normalisation (B16)

Free-text-like fields exist even under V12 (legal entity names, free-form addresses inside SSI metadata, ISDA Master party legal name). Hash inputs that include such strings will diverge across NFC/NFD normalisation, locale collation, or charset boundary handling. Cross-jurisdiction LEI registration is a known minefield.

**Required fix.** Add B16. Mandate NFC + UTF-8-byte canonicalisation at every parser ring boundary.

### B.5 MAJOR — Test environment as boundary (B17)

The proposal *witnesses* laws via Hypothesis-style tests; but the test runner itself is a non-deterministic boundary (Hypothesis seed, parallel test workers, OS-scheduled order of fuzzed inputs). If the property catalogue is run with a wall-clock seed, "passing" today does not mean "passing tomorrow". This is the simulator-determinism mirror of B1.

**Required fix.** Test seeds derived from `git_sha` of the test corpus + `cdm_version`. Failed shrinks committed to the test artefact directly. CI artefact: `(seed, repro)` for every successful run.

**Boundary count after fix: 17, not 12.** Phase 3 must justify any number lower than 17 by demonstrating structural unreachability.

---

## §C. Goodhart trap audit — are the 4 stated traps actually avoided?

The proposal lists 4 Goodhart traps in §6 (mirrored as §9.6 in the synthesis). I check each.

### C.1 Trap "snapshot coverage stub-swap" — **NOT avoided** (UNMITIGATED MAJOR)

The mitigation is "P-L8 demands byte-identical replay". But P-L8 reads `tx.inputs_pinned` — a generator output — and replays the handler. **The generator constructs the snapshot under test**; it is not testing the *production* snapshot store. If production swaps the store for a stub, no Hypothesis test detects it because the test harness builds its own snapshot.

**Required fix.** Add a *boundary-integrity* test that runs in production (or staging-mirror): pull a sample of N committed transactions, fetch their snapshots from the *production* store, replay, verify byte-identical. This is fault-injection-against-infrastructure, not property-based testing. The proposal lacks this harness.

### C.2 Trap "mutation set exclusion" — **partially avoided**

§4.4 names 10 mutation operators; §6 trap #2 says M-CDM, M-CANON, M-LATE are mandatory; they appear in the operator list. Good. **But:** the 80% / 90% mutation-score targets are cited from "addendum §6" without verifying which mutations are *killable* by the property tests as written. P-L2 uses Mahalanobis tolerance; M-CONS in the calibration step may produce a perturbation *within* tolerance and survive. **The mutation score becomes a Goodhart metric the moment it is targeted.**

**Required fix.** Mutation-score must be reported alongside *which mutants survived* and *why*; survivors are themselves a finding, not a tail allowance.

### C.3 Trap "biased generators" — **NOT avoided** (UNMITIGATED MAJOR)

§4.1 enumerates generators per CDM ProductType × EventIntent. But:
- `gen_market_snapshot` has no specification of how it *biases toward edge cases*. Hypothesis defaults are normal-ish; arbitrage-near-boundary configurations are exponentially rare under uniform sampling.
- `gen_obligation` does not specify deadline distribution; if all generated deadlines are far-future, P-L13 never triggers escalation paths.
- `gen_workflow_history` "bounded length" — bounded to what? Goodhart fires the moment "bounded" means "10 events" because that is the test-suite walltime budget.

**Required fix.** Specify *coverage targets* per generator stratum (e.g., 5% of `gen_market_snapshot` outputs land within ε of arbitrage boundary; 10% of `gen_obligation` outputs have deadline within current sim-clock + δ to force timer-fire path). Coverage targets become first-class assertions of the test program, *not aspirational*.

### C.4 Trap "aggregation-averaged conservation" — **avoided** (acceptable)

§6 says per-(scope) conservation is mandatory; L5/L6/L7 are explicitly per-class / per-mandate / per-CCP. But see §A.2: cross-CCP novation *requires* an aggregated scope law, and the proposal forbids it. This is the *opposite* failure mode — **over-strict per-scope checks block legitimate composition**. Both are Goodhart adjacent.

### C.5 NEW Goodhart trap missed by the proposal (UNMITIGATED MAJOR)

**"Type-system witness laundering."** §5 U1 surrogates obligation liveness with "structural induction; FORMALIS I10 captures it". But a type-system witness is only as strong as the executor's *adherence* to the type discipline at runtime. Python does not enforce phantom types at runtime; refined newtypes are nominal. The proposal *claims* type-level witnesses for U1 and (implicitly) for the StatesHome single-writer-per-field discipline; in practice these collapse to "we trust the developer to obey the contract". This is the maximally-Goodhart-able case: a metric ("type-checks pass") that imposes zero correctness pressure.

**Required fix.** Either (a) port to a language that enforces phantom types at runtime (Rust, OCaml); or (b) supplement every type-witness with a runtime checker that fires on every write attempt and a Hypothesis test that adversarially attempts violation.

---

## §D. Laws that need fault-injection but proposal lacks the harness

The 49-cell fault matrix in §3 enumerates *what fault breaks what law*. It does **not** specify a fault-injection harness. The witnessing programs in §4 generate *legal* inputs and check *invariants*; they do not inject *faults* (silent corruption, partition, message reordering, clock skew, disk errors). This is the classic FoundationDB lesson: **deterministic simulation must include fault injection at every boundary**, otherwise the fault catalogue is documentation, not a test program.

### D.1 BLOCKING gap — no harness for Cluster V silent-corruption

§3 Cluster V silent-corruption: "Hash chain (Invariant 4)". But there is *no test* in §4 that injects a corrupt byte into a stored move and verifies that the next chain verification flags it. This is two lines of code; its absence is a tell.

### D.2 UNMITIGATED MAJOR — no harness for Cluster IV partition

Cluster IV partition recovery is "Liveness budget: define max_silence beyond which obligations escalate". `max_silence` is not defined anywhere. The harness needed: simulate gateway-down for `max_silence + ε` and verify obligation escalation fires. The simulator does not exist in the proposal.

### D.3 UNMITIGATED MAJOR — no bugification

Antithesis-style **bugification** (inject pathological-but-legal behaviour: zero-balance moves, max-precision Decimals, leap-second clock advances, near-zero correlation matrices, near-singular Hessians) is *not mentioned*. The proposal's generators sample legal inputs; bugification samples *adversarial-legal* inputs. The four unwitnessed laws (L1, L4, L8, L13) are precisely the ones bugification finds violations in for free.

### D.4 MAJOR — no clock-skew harness for L4

P-L4 uses `t_v ≤ t_k` but never tests `t_v` arriving *out of order* relative to `t_k` ingestion. The bitemporal subtle bug is when `(t_v_old, t_k_new)` pairs interleave with `(t_v_new, t_k_older)`; this is the regulatory-restatement nightmare. Generator-level only; no fault injection.

---

## §E. Other findings

### E.1 UNMITIGATED MAJOR — L11 metamorphic relations are too narrow

P-L11 cites put-call parity, calendar-spread non-negativity, strike homogeneity. **Missing:**
- Vega convexity-on-ATM (curvature in $\sigma$ at ATM is non-negative for European calls)
- Forward-rate consistency (calibrated curves must satisfy $f(t, T_1, T_2) \cdot DF(T_1) = DF(T_1) - DF(T_2)$ within tolerance — known to fail under non-monotone interpolation)
- Greeks-via-bumping match Greeks-via-AD on second derivatives at small bump sizes
- Local-vol calibration round-trip: calibrate to surface, reprice surface, check no-arb residual

These are *standard* in derivatives shops; their absence in §4 is alarming.

### E.2 MINOR — L9 forgetful-functor composition is **only partially specified**

P-L9 asserts `F(e2 ∘ e1) = F(e2) ∘ F(e1)` for `referentially_independent(e1, e2)`. But CDM events that look independent at the wire often share a `tradeIdentifier`; the test must explicitly partition by *which* dependence relations matter (timestamp ordering vs. trade lineage). The proposal does not name the dependence relation lattice.

### E.3 MINOR — `gen_calibrated_state` is rejection-sampled into Θ_AF

§4.1 says rejection-sample. Under tight admissibility regions and high-dimensional state, rejection rates can approach 1 and tests degenerate to no-op. Need MCMC / Hamiltonian sampling on the admissibility manifold, not rejection.

### E.4 MINOR — §8 Theorem 4 (Substantiation) elides the *recovery* property

"L14 hash-chained move stream + L18 deterministic identity + multi-replica verification compose to substantiation". But substantiation requires not just *detection* of corruption but *recovery* (rebuild from chain remnants + replicas). The theorem as stated is a detection theorem, not substantiation. Either rename to "Substantiation Detection" or extend the proof to include recovery.

### E.5 MINOR — Mutation-score targets are not stratified

80% overall, 90% on event handlers. But what about pricing code (where L11 lives)? What about the canonicalisation layer (where L8/L9 live)? A single global number is itself Goodhart-vulnerable.

---

## §F. Findings classification and grade

### Blocking (3)
- **B1.** L1 not closed under FSM `Stale → Pricing` re-entry × snapshot retention (§A.1). Required: structural invariant on retention horizon.
- **B2.** L5/L6/L7 not closed under multi-CCP novation (§A.2). Required: explicit Novation Bridge law or two-tx decomposition.
- **B3.** B11 boundary not closed under HSM key rotation (§A.3). Required: append-only public-key contract.
- **B4.** No fault-injection harness for Cluster V silent-corruption (§D.1). Required: minimal test inserting a corrupt byte and asserting chain-verification flags it.

### Unmitigated Major (7)
- **M1.** Floating-point determinism boundary (B13) absent (§B.1).
- **M2.** Storage iteration order boundary (B14) absent (§B.2).
- **M3.** Intra-handler concurrency boundary (B15) absent (§B.3).
- **M4.** Goodhart "biased generators" not actually closed — coverage targets undefined (§C.3).
- **M5.** Goodhart "type-system witness laundering" not named (§C.5).
- **M6.** No partition / max_silence harness (§D.2); no bugification (§D.3).
- **M7.** L11 metamorphic relations too narrow (§E.1).

### Minor (6)
- **m1.** Locale/Unicode boundary (B16) absent (§B.4).
- **m2.** Test-environment boundary (B17) absent (§B.5).
- **m3.** Mutation-score reporting must list survivors (§C.2).
- **m4.** L9 dependence relation lattice unspecified (§E.2).
- **m5.** `gen_calibrated_state` rejection-sample degeneracy (§E.3).
- **m6.** Theorem 4 conflates detection with substantiation (§E.4); mutation-score not stratified (§E.5).

### Grade

**B+ (conditional pass).**

The proposal is a coherent integration; the 14 cross-layer laws are the right *ontology*. But the **closure under composition** with the executor + valuation FSM + settlement layer fails in three places I can name (and likely more I have not constructed scenarios for). The boundary catalogue undercounts by at least 5; the property catalogue lacks a fault-injection harness; the type-witness story for unwitnessed laws is the one Goodhart trap the proposal does not name.

This is **not yet ready** to be the load-bearing data specification. The fixes are concrete, scoped, and tractable — none requires a re-architecture. Phase-2 specialist authors should respond to the 4 BLOCKING findings in `proposal_v2`. With those addressed, this becomes an A-grade specification.

The framework's most important asset is the **honest** §5 unwitnessed-laws section; the most important *liability* is the **uneven sharpness** between determinism rigour (high) and fault-injection rigour (low).

— end of Phase 3 round 1 correctness-architect review —
