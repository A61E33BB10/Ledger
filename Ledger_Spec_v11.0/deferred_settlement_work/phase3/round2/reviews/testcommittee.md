# TESTCOMMITTEE — Round 2 Adversarial Review of `proposal_v2.md`

**Reviewers.** Beck, Hughes, Fowler, Feathers, Lamport.
**Phase.** Round 2 verification of R1 closure for the Settlement Team's deferred-settlement specification.
**Independence.** Written without consulting the Round 2 formalis or jane-street-cto reviews; written against the Settlement Team's R1 closure record (§15.2/§15.3/§15.4) without taking the closure record on faith.
**Stance restated.** Tests are normative. The R1 panel asked for (a) a TLA+ model rewritten at Phase 2 fidelity with fairness pinned, (b) walking-skeleton tests for 8 missing variants, (c) generator type signatures with shrink lattices, (d) mutation-testing targets with the query-shape gap acknowledged, (e) a v10.3 regression gate, plus six majors. We verify what was actually delivered in the file, not what the closure table says was delivered.

---

## VERDICT

**REJECT_REVISE.**

The Settlement Team has materially closed three of our five R1 BLOCKING items (B-2 walking-skeleton list, B-3 generator type signatures with shrink lattices, partial structural closure of state model via §6.5 workflow spec). The closure record (§15.2/§15.3) is honestly written and accurately maps R1 themes to v2 sections **for the Round 1 cross-team panel** (jane_street/temporal/correctness/lattner/halmos/cartan/nazarov findings); it does **not** systematically address the testcommittee R1 BLOCKING items B-1, B-4, B-5 or unmitigated majors M-2, M-4, M-6. Specifically:

- **B-1 (TLA+ rewritten at Phase 2 fidelity).** Not closed. PO-8 is logged "Open; tractable in minutes" with the **same** state-space estimate (10⁵–10⁶) the R1 panel rejected as stale. No rewritten TLA+ model is shipped. PSS/PS wallet family, two-layer status, obligation graph, witness as action parameter, fairness regime — none are encoded in a delivered TLA+ artefact. The §6.5.5 commutativity table is a useful intermediate, but it is not a TLA+ model.
- **B-4 (mutation testing targets + query-shape gap).** Not closed. The proposal mentions "mutation testing" twice in passing (§11 type-vs-runtime row for DS7; §13.4 verification of generator coverage). No numeric target (DS1 100%, overall 80%) appears. The query-shape mutation gap from R1 B-4 is not acknowledged. Mitigation via typed-PnL boundary is in §12.1.1 phantom wallet class — but the proposal does not connect the type design to the mutation-testing claim.
- **B-5 (v10.3 regression gate).** Not closed. No §11.6 (or equivalent) enumerating P1–P10 + P11–P20 with pass-unchanged / pass-with-migration / replace verdict per invariant. §11.A reasserts seven v10.3 invariants by reference, which is the opposite of a regression gate — it asserts inheritance without certifying behaviour-preservation per test.
- **M-2 (fairness regime).** Not closed. The proposal commits to liveness behaviour (DS9 Buy-In Closure; §6.5.4 deadline + watchdog) without stating fairness assumptions. No `WF` / `SF` annotation per action. R1 was explicit: "Without this, 'PO-8 passes TLC' is a meaningless claim." Status quo unchanged.
- **M-4 (v10.3 characterisation tests).** Not closed. None of the six named characterisation tests (`test_v10_3_pnl_uses_own_only`, etc.) are added. §11.A is reassertion-by-reference, not characterisation-by-golden-fixture.
- **M-6 (bitemporal model in PO-8).** Not addressed; PO-8 still cites a single-clock spec and the v2 closure table marks Theme F closed via the §6.5.5 commutativity table — that is replay-permutation, not bitemporal.

**B-2 is in good shape.** All eight R1-missing variants now have walking-skeleton entries (WS-1..WS-12) including DvP CSD-reject (WS-11), FX Herstatt (WS-9), recall (WS-7), CA (WS-8), recon-lag (WS-5), short (WS-6), Sell happy (WS-2), T+1 (WS-3). One row per scenario; verification predicate stated. Beck accepts the table-of-twelve as sufficient for sign-off prerequisite, with the caveat that the rows are *test plans*, not *test code*, and the M-3 walking-skeleton for DvP-asymmetric (cash settled / securities failed) is implicit in WS-11 but the κ-dispatch verification predicate is not pinned.

**B-3 is closed.** §13.4.4 ships generator type signatures with shrink lattices for all six dimensions identified in R1 B-3. Failure-reason is a closed sum (§12.1.4). Hedgehog-style shrinking is named. The `gen_witness_arrival_perm` shrink-to-lex-min is exactly what Hughes asked for.

The remaining items are not "minor improvement free of trade-off" — they are direct gaps against R1 BLOCKING that the closure record silently fails to enumerate. **Pareto is not reached on the testcommittee axis.** Round 3 (or a tightly-scoped patch round) is required for B-1, B-4, B-5, M-2, M-4, M-6. The patch surface is small (one TLA+ refactor; one §11.4 mutation-target stanza; one §11.6 regression-gate table; one §11.7 characterisation-test list; one fairness-annotation paragraph in §6.5 or PO-8). Estimated 2–3 person-days.

---

## R1 CLOSURE TABLE (testcommittee findings only)

| R1 finding | Status | Evidence in v2 | Verdict |
|---|---|---|---|
| **B-1** TLA+ rewritten at Phase 2 fidelity (PSS/PS family, two-layer status, obligation graph, witness param, D_max bound, state-space re-estimate, symmetry abstractions) | **NOT CLOSED** | §13.2 PO-8 row "Open; tractable in minutes"; §15.1 item 7 "state-space ~10⁵–10⁶" — same stale estimate; no TLA+ artefact attached; D_max=2 pinned (the only delivered piece) | LAMPORT REJECT |
| **B-2** Walking-skeleton tests for 8 missing variants | **CLOSED** | §13.3 WS-1..WS-12 covers all R1-named variants: Sell happy (WS-2), T+1 (WS-3), recon-lag (WS-5), short (WS-6), recall (WS-7), CA (WS-8), FX Herstatt (WS-9), DvP CSD-reject (WS-11), plus T+0 (WS-4), partial (WS-10), manual override (WS-12) | BECK ACCEPT (with M-3 caveat) |
| **B-3** Generator type signatures + shrink lattices for 6 dimensions; failure_reason closed sum | **CLOSED** | §13.4.4 lists `gen_settlement_window`, `gen_finality_lag`, `gen_witness_arrival_perm`, `gen_failure_reason`, `gen_corporate_action_in_window`, `gen_partial_chain_depth`; shrink lattices stated; §12.1.4 failure_reason as closed sum | HUGHES ACCEPT |
| **B-4** Mutation testing targets (DS1=100%, overall=80%); query-shape mutation gap acknowledged; typed-PnL mitigation | **NOT CLOSED** | §11 type-vs-runtime mentions "(RT) mutation testing" for DS7 only; no numeric targets; no §11.4; no query-shape gap statement; §12.1.1 phantom wallet class shipped (mitigation present) but not connected to mutation-testing claim | FEATHERS REJECT |
| **B-5** v10.3 regression-gate certifying P1–P10 + P11–P20 (pass / pass-with-migration / replace) | **NOT CLOSED** | §11.A reasserts seven v10.3 invariants by reference; no per-invariant pass/migrate/replace verdict; no test-pass attestation | FOWLER REJECT |
| **M-1** `pending_*` projection-only test seam — `view.pending_in/out` shim in test harness | **PARTIALLY CLOSED** | §4.1.5 "Inflight projections (named explicitly)" added; production projection clarified, but test-harness shim not separately specified. The named projection in §4.1.5 doubles as the test seam — Hughes accepts as adequate | HUGHES ACCEPT (lukewarm) |
| **M-2** Fairness regime per action for liveness invariants | **NOT CLOSED** | §6.5.4 deadline-timer + watchdog described operationally; no `WF`/`SF` annotation; PO-8 owes liveness check that is undecidable without fairness regime | LAMPORT REJECT |
| **M-3** Walking-skeleton for DvP-asymmetric (CSD `sese.025` cash settled, `sese.024` securities failed) | **PARTIALLY CLOSED** | WS-11 covers DvP CSD-reject in single-leg form; the *asymmetric* case (one leg `Settled`, the other `Failed`) is implicit in §6.5.3 DvP-S disambiguation but the verification predicate (κ dispatch fired correctly per `L_16.ReferenceMaster`) is not pinned in the WS-11 row | BECK ACCEPT-WITH-CAVEAT |
| **M-4** Six v10.3 characterisation tests (golden-file diff tests) | **NOT CLOSED** | None of `test_v10_3_pnl_uses_own_only`, `test_v10_3_recon_uses_settled_bucket`, `test_v10_3_clone_at_includes_obligations`, `test_v10_3_fail_does_not_reverse_position`, `test_v10_3_settle_projection_is_pure`, `test_v10_3_fail_resolution_is_closed_sum` appear in v2 | FEATHERS REJECT |
| **M-5** DS5 generator exercises CSD restatement (RestatementEvent constructor) | **CLOSED** | §6.5.5 commutativity table includes restated-vs-original handling; G5 closed via Reading (a) "treat restatement as new obligation"; bitemporal `t_known` discipline §4.5.1; matches Hughes's R1 ask | HUGHES ACCEPT |
| **M-6** Bitemporal model in PO-8 — TLA+ extended with `(t_obs, t_known)` cross-product | **NOT CLOSED** | Acknowledged via §11.A "DS16 is structural property of the bitemporal model; not separate"; option (a) "structural only" was R1's acceptable minimum, but the v2 must *say* "we do not check bitemporality in TLA+" — instead it asserts §6.5.5 closes Theme F, which is replay-permutation, not bitemporality | LAMPORT REJECT (option (a) honesty not yet asserted) |
| **m-1** Test naming convention `test_<actor>_<scope>_<scenario>_<outcome>` | **NOT CLOSED** | WS-1..WS-12 use `WS-N` shorthand only | BECK MINOR |
| **m-2** Combinatorial coverage criteria (pairwise of variant × outcome × delay × settle_date; full at nightly) | **NOT CLOSED** | §13.4 G-DS-1 verification mentions "5%, 95%, 99% latency cells"; not a coverage matrix | HUGHES MINOR |
| **m-3** Test pyramid shape (60/30/8/2) | **NOT CLOSED** | Not addressed | FOWLER MINOR |
| **m-4** Mutation-survivor categories (wall-clock, error message text, cross-workflow races, hash-preserving serialisation) | **NOT CLOSED** | Not addressed; tied to B-4 | FEATHERS MINOR |
| **m-5** `\|trades\|` parameter in PO-8 | **NOT CLOSED** | PO-8 specifies `\|W\|=3, \|U\|=2, depth=8`; no `\|trades\|` | LAMPORT MINOR |
| **m-6** §3 worked example numbers as runnable test fixtures | **PARTIALLY CLOSED** | §3 + §3.X tables are now reproducible by independent computation (R1 feynman closed); not yet shipped as test fixtures | BECK MINOR |
| **m-7** Decimal precision pinned per quantity type in generators | **CLOSED** | §0.5 decimal types; §13.4.4 generators reference `D_n` types | HUGHES ACCEPT |
| **m-8** L_18 aging FSM characterisation test (calendar convention) | **NOT CLOSED** | §4.9 L_18 mapping referenced; no characterisation test pinning calendar convention | FEATHERS MINOR |

**Closure score:** 4 closed (B-2, B-3, M-1 implicitly via §4.1.5, M-5), 2 partially closed (M-1, M-3), 6 not closed (B-1, B-4, B-5, M-2, M-4, M-6), 6 minors not closed.

---

## NEW ISSUES (introduced by v2's revisions)

### N-1 (LAMPORT) — Wallet-family pullback to 3 classes invalidates the Phase-1-fidelity TLA+ even further
v1 had 10 wallet classes with PSS/PS subdivision; v2 collapses to 3 classes with side-as-sign in `cpty_virtual` (§0.2, §2.3, closes lattner M-1, geohot). This is the right design choice. **But the TLA+ model now needs another rewrite from yet another baseline.** The Phase-1 §8.5 model is doubly stale: it has neither (a) the v1 PSS/PS family nor (b) the v2 `cpty_virtual` signed scheme. PO-8 status "Open; tractable in minutes" is at this point *aspirational* — the model has not been written at *any* fidelity matching v2.
**Action.** TLA+ model rewrite is mandatory before PO-8 can claim status.

### N-2 (HUGHES) — `gen_partial_chain_depth :: Gen Int` shrinks to 0; D_max=2 means the generator can never exercise the boundary
§13.4.4 says `partial_chain_depth: shrink to 0 (no partials)`. Given D_max=2 (§6.4, DS11b), shrinking to 0 means the generator's minimal counterexample to DS11a or DS11b will collapse out of the partial-fill regime entirely. The shrink lattice should target `1` (single partial), then `0`, in that order. Otherwise property tests will report `[0]` as the minimal counterexample for partial-conservation bugs that are only exhibited at depth ≥1.
**Action.** Re-order shrink lattice for `partial_chain_depth`: `2 → 1 → 0`, with `1` as the natural minimum for partial-flow tests.

### N-3 (BECK) — WS-11 (DvP CSD-reject) does not distinguish symmetric-fail from asymmetric-fail
WS-11 verification predicate: "sese.024 inbound; FSM transitions to Failed; DS7 (no real-wallet move); CSDR penalty obligation spawns." That covers the *symmetric* CSD-reject case (both legs fail). The *asymmetric* case from R1 M-3 (cash settled `sese.025`, securities failed `sese.024`) is the highest-risk DvP failure mode and is not separately tested. §6.5.3 DvP-L/S/E disambiguation is correct — but the test that demonstrates DvP-S violation does not throw DvP-E off (κ-dispatch fires the right compensation, BreakRegister kind = `dvp_asymmetric_settlement`, no real-wallet move on the *settled* leg either) is owed.
**Action.** Split WS-11 into WS-11a (symmetric reject) and WS-11b (asymmetric one-leg-settled-other-failed); pin κ-dispatch verification predicate per CSD regime.

### N-4 (FEATHERS) — `gen_corporate_action_in_window` shrinks to "no-CA case", which means CA-related properties are never tested at the boundary
§13.4.4 says `CorpAction: shrink to no-CA case`. This is the same shape error as N-2: the natural minimum case for testing CA-during-open-window is *one* CA, not zero. Shrinking to zero CAs means the generator produces "trivially passes" inputs as the minimal counterexample for any G3-related property test. The PO-4 / G3 follow-on (matthias + correctness, ETA: 1 week post-R2) inherits this trap.
**Action.** Shrink lattice: `1 CA at midpoint of (T, t_d]` → `1 CA at boundary` → `no CA`.

### N-5 (LAMPORT) — `attempt_seq` in `tx_id = hash_jcs(business_event_id, attempt_seq)` makes idempotency a function of monotonic external state
§6.5.1 closes temporal B-1 with `tx_id` formula. Across `ContinueAsNew`, `attempt_seq` is carried (per closure note). **This means dedup_key (§4.5.1) and tx_id together depend on monotonic state that is local to a single workflow execution.** If the workflow itself fails over (multi-region replication per G8 mitigation), `attempt_seq` must remain consistent across replicas, or two replicas with different `attempt_seq` values will produce two distinct `tx_id`s for the same business event. The fairness assumption in M-2 collides with this: weak fairness on `ReceiveConfirmation` per `tx_id` requires `tx_id` stability across replicas.
**Action.** Pin "attempt_seq is durable across CaN AND across multi-region failover" as TA-DS-N (extend trust-assumption registry §13.5).

### N-6 (HUGHES) — DS3 sign-convention verification on SELL is a single worked example, not a property test
§3.X.5 verifies recon identity on the SELL by independent computation — that closes the Round 1 cross-team blocker (Theme 2). But it is *one example*. The R1 testcommittee position is that example tests do not ship; property tests do. The proposal needs a property `prop_recon_identity_holds_on_arbitrary_(buy_or_sell)_under_arbitrary_finality_arrival_permutation` that uses `gen_witness_arrival_perm` + `gen_settlement_window`. Without it, DS3 is verified at two points (the BUY in §3, the SELL in §3.X) and untested everywhere else.
**Action.** Add `prop_DS3_recon_identity` with type signature in §13.4.4; the WS-1 / WS-2 walking-skeleton tests are the *example seeds*, the property test is the *spec*.

---

## SPECIFIC SCRUTINY (responding to the prompt)

### BECK — §13.3 walking-skeleton 12-test list — present? All R1 B-2 variants covered?
**Yes for the table; partial for the verification predicates.** WS-1..WS-12 covers Sell happy (WS-2), T+1 (WS-3), recon-lag (WS-5), short (WS-6), recall (WS-7), CA (WS-8), FX Herstatt (WS-9), DvP CSD-reject (WS-11) — all eight R1 missing variants are present, plus T+0 (WS-4) and manual override (WS-12) as v2 additions. Table format is acceptable for a sign-off prerequisite list; row depth is shallow (one verification clause per row) and the M-3 asymmetric-DvP case is not split (see N-3). **Beck rates B-2 closed**, with a tightening request that WS-11 split into 11a/11b. The §13.3 statement "Each test runs as an end-to-end integration test under the property generator framework (§13.4.4)" is the right discipline — the tests *are* property-test seeded, not example-only.

### HUGHES — Generators with type signatures + shrink lattices — present? Failure-reason closed sum?
**Yes.** §13.4.4 ships six generator type signatures (`gen_settlement_window :: Gen SettlementWindow`, `gen_finality_lag :: AssetClass -> Gen Duration`, `gen_witness_arrival_perm`, `gen_failure_reason :: Gen FailureReason`, `gen_corporate_action_in_window`, `gen_partial_chain_depth`) with shrink lattices stated for each. Failure-reason is a closed sum in §12.1.4. **Hughes rates B-3 closed.** Shrink-lattice ordering bugs flagged in N-2 (partial_chain_depth shrinks to 0 instead of 1) and N-4 (CorpAction shrinks to none instead of one). The empirical-distribution mitigation for G-DS-1 quick-finality bias (§13.4 G-DS-1) is good — the `L_7^P.GeneratorDistributionPin` per-asset-class with quarterly refresh is the right discipline.

### FOWLER — Regression-gate spec for v10.3 tests — present?
**No.** No §11.6 (or equivalent) enumerating P1–P10 + P11–P20 with pass-unchanged / pass-with-migration / replace verdict per v10.3 invariant. §11.A reasserts seven v10.3 invariants by reference — that is the *opposite* of a regression gate, since reassertion claims inheritance without certifying that any v10.3 test passes against the new wallet schema. Specifically:
- v10.3 tests that **enumerate wallets** via `SELECT * FROM wallet_registry` will see new `cpty_virtual` and `csd_virtual` rows (§2.3). v2 does not certify whether v10.3 tests pass.
- v10.3 tests that **sum `own` across wallets for a unit**: §2.6 says conservation now holds over `\mathcal{W} = \mathcal{W}_real ∪ \mathcal{W}_cpty_virtual ∪ \mathcal{W}_csd_virtual`. v10.3 tests summing over real-wallets-only will regress unless `\mathcal{W}_cpty_virtual` and `\mathcal{W}_csd_virtual` net to zero per unit at quiescence — which they do by design, but no test certifies this.
- v10.3 tests that **assert `nostro_external = w.own(ccy)`** must be replaced by the §4.1 identity. v2 does not enumerate which tests are replaced.

**Fowler rates B-5 not closed.** This is a Round 2 gap that prevents the v10.3 → v11.0 stage-1 migration from being shipped safely. Required §11.6 table:
```
| v10.3 invariant | v10.3 test name | v11.0 verdict | New test (if replaced) |
| P1 conservation | test_p1_*       | passes-with-schema-migration | — |
| P10 PnL path-indep | test_p10_*   | passes-unchanged              | — |
| ... (P1..P10 + P11..P20) ... |
```

### FEATHERS — 6 v10.3 characterisation tests added?
**No.** None of `test_v10_3_pnl_uses_own_only`, `test_v10_3_recon_uses_settled_bucket`, `test_v10_3_clone_at_includes_obligations`, `test_v10_3_fail_does_not_reverse_position`, `test_v10_3_settle_projection_is_pure`, `test_v10_3_fail_resolution_is_closed_sum` appear. §11.A is reassertion, not characterisation. **Feathers rates M-4 not closed.** These six tests are the silent-assumption pinpoints for v10.3; without them, the v11.0 extension can probabilistically perturb a v10.3 assumption and the test suite will be green. Feathers's rule applies: "the test you don't write is the assumption that will silently break."

The proposal claims (§11) "Recommendation: take CT cost for DS17 and DS7" — this is the correct call; CT mitigation reduces what characterisation tests must catch — but it does not *replace* the six characterisation tests, which pin v10.3 behaviour *before* the type system can be applied as the new gate.

### LAMPORT — TLA+ model updated for §6.5 PSS/PS wallet family + per-leg L_15 + witness envelopes? D_max pinned? Fairness regime stated?
**Mixed.**
- **D_max pinned: YES.** §6.4 + DS11b: `D_max = 2`. PO-9 closed (§13.2 row). This is the *only* of the five B-1 sub-items closed.
- **PSS/PS wallet family encoded in TLA+: NO.** Wallet family in v2 is *simpler* (3 classes, signed `cpty_virtual` per §0.2) than the v1 model the R1 panel rejected as stale. But "simpler" does not mean "modelled" — PO-8 says "Open; tractable in minutes" with no shipped model. State-space estimate "10⁵–10⁶" (§15.1 item 7) is the same number from R1; it has not been re-derived against the v2 wallet schema. See N-1.
- **Per-leg L_15 + projection (no transaction-level FSM) encoded: NO.** §5.1 is the canonical-FSM ruling (closes lattner B-1 / halmos M8); §5.3 is the projection function. The TLA+ model that verifies the projection-as-homomorphism (per-leg lattice → transaction observable) is not shipped.
- **Witness envelope as TLA+ action parameter: NO.** §4.5 specifies the envelope at the data layer; the TLA+ action `Discharge_with_witness(o, ε)` versus `Discharge_by_inference(o)` distinction (R1 B-1 item 4) is not encoded.
- **Obligation-graph for CSDR penalty (R1 B-1 item 3): NO.** §6.3 specifies CSDR penalty as L_15 row with parent_obligation_id; not encoded in TLA+.
- **Fairness regime stated: NO.** §6.5.4 deadline + watchdog is operational; no `WF`/`SF` annotations on `ReceiveConfirmation`, `Tick`, `DischargeBuyIn`. M-2 unaddressed.

**Lamport rates B-1 not closed and M-2 not closed.** PO-8 is "Open; tractable" — but the spec scope for what TLA+ must check has expanded (10/11 invariants encoded; bitemporality elided per option (a); fairness annotations needed; obligation-graph for CSDR; signed cpty_virtual scheme). The 3-day ETA in §15.5 item 4 is implausible without a written model. The R1 ask was: rewrite the model in this proposal. v2 does not ship it.

### Mutation testing 100% on DS1 — achievable now under v2 type design?
**Conditionally yes — mitigation is shipped, claim is not.** §12.1.1 phantom wallet class (RealWallet vs CptyVirtual vs CsdVirtual phantom-types) is exactly the typed-PnL boundary R1 B-4 asked for. The PnL function with signature `pnl :: WalletHandle Real -> Money` makes "use `cpty_virtual.own` in the PnL formula" a compile-time error, not a survived mutation. **The architectural pre-condition for 100% mutation score on DS1 is met.**

But:
- The proposal does not state the 100% target.
- The proposal does not state the 80% overall target.
- The proposal does not acknowledge the query-shape-mutation gap (mutmut/pitest do not mutate SQL projections; this is *not* a code mutation).
- The proposal does not connect §12.1.1 phantom typing to the mutation-testing claim. A reader of v2 would not know that DS7's "(RT) mutation testing" row in §11 type-vs-runtime decomposition is achievable only because §12.1.1 was scoped into v11.0 core.

**Feathers rates B-4 not closed.** The required §11.4 stanza is small (~5 lines):

```
§11.4 Mutation testing targets
- DS1 (PnL formula): 100% mutation kill rate on the typed-PnL function; achievable due to phantom wallet class §12.1.1.
- DS7 (failure non-reversal): 100% on the FSM step function in §5.2.
- Overall: ≥80% on Settlement-Library code.
- Acknowledged gap: SQL-projection mutations (recon-identity query shape) are not detected by code-level mutators; mitigated by the fact that all PnL/recon flow through typed projections per §12.1.1, but not eliminable. Manual code-review gate for PnL query shape.
```

This is one paragraph of work.

---

## PARETO JUDGMENT

**Pareto NOT reached on the testcommittee axis.**

Six R1 BLOCKING/MAJOR items are not closed:
- B-1 TLA+ rewrite (LAMPORT)
- B-4 mutation testing targets (FEATHERS)
- B-5 v10.3 regression gate (FOWLER)
- M-2 fairness regime (LAMPORT)
- M-4 v10.3 characterisation tests (FEATHERS)
- M-6 bitemporal model — option (a) honesty not asserted (LAMPORT)

Plus six new issues (N-1..N-6) that are direct consequences of the v2 wallet-class refactor or surfaced during shrink-lattice review.

The closure record §15.2 / §15.3 is **Round 1 cross-team-correct** — every theme except B-2/B-3 in our review is mapped to a non-test closure in §15.2/§15.3, but the testcommittee asks were not table-rowed and not delivered. This is a pattern: the closure record indexes by R1 source (jane_street / temporal / nazarov / lattner / halmos / cartan / correctness) and **does not have rows for testcommittee findings** beyond B-2 (Theme 7) and B-3 (Theme 8). The testcommittee R1 review listed B-1 through B-5 explicitly; closure for testcommittee B-1, B-4, B-5 is not enumerated in §15.2.

**Pareto rule applies:** zero blocking remaining + zero unmitigated major remaining + no minor improvement without offsetting trade-off.

We have:
- 3 unclosed BLOCKING (B-1, B-4, B-5)
- 3 unclosed/unmitigated MAJOR (M-2, M-4, M-6)
- 6 new issues (N-1..N-6) — most are minor patches (3 of 6 are shrink-lattice ordering or splitting a single WS row), but N-1 (TLA+ doubly-stale) compounds B-1.
- 6 unclosed MINOR (m-1, m-2, m-3, m-4, m-5, m-8)

**Recommendation.** A tightly-scoped patch round (call it R2.5) targeting B-1, B-4, B-5, M-2, M-4, M-6, and new N-1..N-6, with deliverables:

1. **§11.4 Mutation testing targets stanza** (5 lines; closes B-4).
2. **§11.6 v10.3 regression-gate table** (P1–P10 + P11–P20 with verdict per row; closes B-5).
3. **§11.7 v10.3 characterisation tests list** (six named tests; closes M-4).
4. **§13.2 PO-8 row revision + new sub-section** specifying TLA+ action set, variable list, fairness annotations, two-layer status check, witness as parameter, obligation-graph (closes B-1, M-2, M-6, N-1).
5. **§13.4.4 shrink-lattice corrections** for `gen_partial_chain_depth` and `gen_corporate_action_in_window` (closes N-2, N-4).
6. **WS-11 split into 11a/11b** in §13.3 (closes M-3, N-3).
7. **§13.5 TA-DS-N** for attempt_seq durability across CaN + multi-region failover (closes N-5).
8. **§13.4.4 add `prop_DS3_recon_identity`** as a property test seeded by WS-1/WS-2 (closes N-6).

Estimated patch effort: 2–3 person-days for the Settlement Team's testcommittee co-author. After R2.5, if the eight items above are delivered cleanly and the TLA+ model produces a TLC run log (PO-8 evidence), Pareto on the testcommittee axis is reachable.

The good news is that the architectural pre-conditions for the unclosed items are *already in v2*: phantom wallet class for B-4, §11.A reassertion as the skeleton for B-5, the 3-class wallet schema as a smaller TLA+ surface than v1's 10-class one for B-1. The mitigations are written; the test-layer commitments are not.

---

## RECOMMENDATION

**REJECT_REVISE.**

Submit a tightly-scoped R2.5 patch round addressing items 1–8 above. Estimated 2–3 person-days. After R2.5, re-run testcommittee review on the patched v2 and run TLA+ TLC to produce PO-8 evidence. If both pass, Pareto is reached on the testcommittee axis.

Six R1 items not closed. Six new issues introduced. The proposal is closer to ready than v1 and the closure record is honestly written for the items it indexes — but the items it does not index are the testcommittee's load-bearing ones, and the test layer is not yet a refusing oracle for the six unclosed items.

---

*Five voices, one suite, one verdict. Beck reads the table-of-twelve and accepts B-2; Hughes signs off B-3 with two shrink-lattice ordering tweaks. Fowler refuses to ship the migration without an enumerated regression gate. Feathers refuses to let the extension perturb v10.3 silent assumptions without golden-pinning them first. Lamport refuses to call PO-8 "tractable in minutes" while the model is not written at v2 fidelity, and refuses to certify any liveness claim until the fairness regime is on the page.*

*"A unit test that takes 1/10th of a second is a slow unit test."* — Feathers
*"Don't write tests. Generate them — but shrink to the boundary, not past it."* — Hughes (paraphrased, contra v2's `partial_chain_depth → 0` and `CorpAction → none`)
*"If you're thinking without writing, you only think you're thinking — and TLA+ counts as writing."* — Lamport
*"Clean code that works — but only after the test refuses to accept the wrong implementation."* — Beck
*"Every v10.3 test must pass without modification, or the modification must be enumerated and approved."* — Fowler
