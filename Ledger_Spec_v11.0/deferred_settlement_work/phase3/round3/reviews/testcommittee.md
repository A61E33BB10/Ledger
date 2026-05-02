# TESTCOMMITTEE — Round 3 Adversarial Closure Check on `proposal_v3.md`

**Reviewers.** Beck, Hughes, Fowler, Feathers, Lamport.
**Phase.** Round 3 verification of R2 closure — five voices, one suite.
**Independence.** Written against `proposal_v3.md` directly without taking §15.6 closure record on faith. Cross-checked R2 testcommittee findings line-by-line against the v3 file.

---

## VERDICT

**PARETO_REACHED.**

Settlement Team has closed all three R2 BLOCKING items (B-1 TLA+ at v2/v3 fidelity §13.6.2; B-4 mutation testing 80%/100% §13.6.3; B-5 v10.3 regression gate §11.6) and all three remaining MAJOR items (M-2 fairness regime, M-4 v10.3 characterisation tests, M-6 bitemporal honesty). Of the six new R2 issues introduced by us (N-1..N-6), all are addressed: WS-11 split into 11a/11b (N-3); shrink lattice corrections for `gen_partial_chain_depth` and `gen_corporate_action_in_window` (N-2, N-4); TA-DS-12 added for `attempt_seq` durability (N-5); `gen_recon_scenario` property generator added for DS3 (N-6); the TLA+ rewrite with v2/v3 ontology closes N-1.

The patches are not merely stamped but substantive: §13.6.2 names variables, fairness annotations per action, sizing including `|trades|=4`, bitemporal axes as separate clocks, and 15 encoded invariants (DS19 included). §13.6.3 enumerates the four DS1 mutations explicitly and acknowledges the SQL-projection-mutation gap with a §12.1.1-typed mitigation argument. §11.6 is a 20-row table with explicit verdicts (PASS / RESTATED / PASS-STRENGTHENED / RESTATED-WITH-CAVEAT) plus six named `char_1`..`char_6` characterisation tests committed to CI. §11.A bitemporal honesty pin commits to option (a): every restatement is a `t_known` update creating a new immutable L_15 row.

Two residual TLC-run obligations remain (PO-8 TLC execution, ~3 days workstation time; LedgerReferenceInterpreter scaffolding ~3 person-weeks) — these are **execution debt**, not specification debt, and per §13.2 are owed for v11.0 release, not for spec sign-off. We accept this distinction.

No new BLOCKING issues introduced by v3. The minor observations in the New-issues section below are flagged for the implementer's record but do not block Pareto.

---

## R2 CLOSURE TABLE (testcommittee findings only)

| R2 finding | Status | Evidence in v3 | Verdict |
|---|---|---|---|
| **R2-B-1** TLA+ rewritten at v2/v3 fidelity | **CLOSED** | §13.6.2 ships variables (`PSS_payable, PSS_receivable, PS_payable, PS_receivable, L_15_state, witness_log, clock`); fairness (WF on `discharge_step`, SF on `csdr_penalty_accrual`, none on watchdog/signals); sizing (`\|W\|=4, \|U\|=2, \|trades\|=4, depth=8` → 10⁵–10⁶); D_max=2 confirmed; bitemporal axes as separate clocks; 15 invariants encoded (incl. DS19 + Conservation Lifting Theorem absolute form) | LAMPORT ACCEPT |
| **R2-B-4** Mutation testing 80%/100% + query-shape gap | **CLOSED** | §13.6.3 commits 80% overall + 100% on DS1 class with four enumerated DS1 mutations; SQL-projection-mutation gap acknowledged with §12.1.1 phantom-typed mitigation argument; verification gate in `L_7^P.MutationCoverageReports` | FEATHERS ACCEPT |
| **R2-B-5** v10.3 P1–P20 regression gate | **CLOSED** | §11.6 ships 20-row table with PASS / RESTATED / PASS-STRENGTHENED / RESTATED-WITH-CAVEAT verdicts; six `char_1..char_6` characterisation tests named with P-coverage mapping and CI commitment | FOWLER ACCEPT |
| **R2-M-2** Fairness regime per action | **CLOSED** | §13.6.2 fairness paragraph explicit: WF on discharge_step, SF on csdr_penalty_accrual, none (adversarial) on watchdog/signals | LAMPORT ACCEPT |
| **R2-M-4** Six v10.3 characterisation tests | **CLOSED** | §11.6 names `char_1..char_6` with v10.3 P-axis coverage mapping; CI gate committed | FEATHERS ACCEPT |
| **R2-M-6** Bitemporal model — option (a) honesty | **CLOSED** | §11.A bitemporal honesty note commits to option (a): every restatement is a t_known update, creates a new L_15 row, original is immutable; option (b) considered and rejected | LAMPORT ACCEPT |
| **R2-N-1** TLA+ doubly stale after wallet refactor | **CLOSED** | §13.6.2 variable list uses v3 wallet ontology; signed cpty_virtual scheme is the surface variable structure; no v1 stale fields | LAMPORT ACCEPT |
| **R2-N-2** `gen_partial_chain_depth` shrinks to 0 | **CLOSED** | §13.4.4 shrink target updated to 1, with "boundary-case shrink discipline" stated as v3 generator policy | HUGHES ACCEPT |
| **R2-N-3** WS-11 conflates DvP-reject types | **CLOSED** | §13.3 split into WS-11a (symmetric) and WS-11b (asymmetric, with κ-dispatch verification predicate per `L_16.ReferenceMaster`) | BECK ACCEPT |
| **R2-N-4** `gen_corporate_action_in_window` shrinks to none | **CLOSED** | §13.4.4 shrink target updated to "1 CA event"; same boundary-case shrink discipline as N-2 | HUGHES ACCEPT |
| **R2-N-5** `attempt_seq` durability across CaN+failover | **CLOSED** | §13.5 TA-DS-12 added; detection signal: collision on `(business_event_id, tx_id)` primary-key uniqueness violation in L_13 | LAMPORT ACCEPT |
| **R2-N-6** DS3 verified at 2 points; needs property test | **CLOSED** | §13.4.4 `gen_recon_scenario` generator added with type signature, shrink target (minimum non-trivial scenario), 1000+ scenarios per invocation | HUGHES ACCEPT |

**Closure score:** 12 of 12 testcommittee R2 items closed. Two execution-debt items remain (TLC run; reference interpreter scaffolding) but these are not specification gaps — they are scheduled engineering work that v3 commits to in §13.6.

---

## SPECIFIC SCRUTINY (per the prompt)

### LAMPORT — §13.6.2 PO-8 TLA+ at v3 fidelity?
**Yes.** Variables match v3 ontology: `PSS_payable / PSS_receivable / PS_payable / PS_receivable` are explicitly described as **two surface views over the signed cpty_virtual storage**, which is the correct way to encode the v3 collapse-to-3-classes design while preserving the model-checker's view of side-as-sign. `L_15_state` is the closed-sum FSM. `witness_log` is ordered by `(t_obs, dedup_key)`. `clock` is discrete-tick. **Bitemporal axes**: `t_obs` and `t_known` modelled as separate clocks per envelope — `Envelope.ts_obs` is asserted by source (free over input), `Envelope.ts_known` is `clock` at intake (monotone). Replay scenarios introduce `ts_obs < ts_known` per envelope; the model checker exercises both ordering options. **Fairness regime**: weak on `discharge_step`, strong on `csdr_penalty_accrual`, no fairness (adversarial scheduler view) on watchdog/signal arrivals — the right calibration. **Sizing**: `|W|=4, |U|=2, |trades|=4, depth=8` → 10⁵–10⁶ reachable; tractable on workstation in minutes. **D_max=2 pinned** with the explicit verification that the model exercises `D_max=0,1,2,3` and verifies the >2 path is taken. **15 invariants encoded** including DS19 and the absolute-form Conservation Lifting Theorem. PO-8 TLC run is scheduled (3 days) — this is execution debt, not specification debt. R2-B-1, M-2, M-6, N-1 all closed.

### BECK — §13.3 WS-11 split into WS-11a/WS-11b?
**Yes.** §13.3 row WS-11a covers symmetric DvP-reject (both legs rejected together) with verification: sese.024 inbound on both `o_sec` and `o_cash`; both FSMs to Failed; DS7 (no real-wallet move on either leg); CSDR penalty obligation spawns on the failing leg per CSD-attribution rules. WS-11b covers asymmetric DvP-reject (one settled, other failed — the leg-inconsistent G4 case): sese.025 inbound on `o_sec` (Discharged) AND sese.024 inbound on `o_cash` (Failed); `tx_status(tx) == Mixed`; `wf-confirm-break` opens; per-CSD κ table (G4) determines whether to manual-revert via CORRECTION. The κ-dispatch verification predicate from R2 N-3 is now pinned via `L_16.ReferenceMaster`. R2-N-3 closed. The §13.3 statement "Each test runs as an end-to-end integration test under the property generator framework (§13.4.4). Sign-off prerequisite: all 12 [now 13 with the split] pass at every release boundary" is the right discipline.

### HUGHES — §13 generators — failure_reason closed sum exhaustive? Boundary-case shrinks?
**Yes (closed sum) and yes (shrinks).** §12.1.4 `failure_reason` closed sum: `DeadlineMissed | NoCover | NoFunds | CounterpartyDefault of Lei.t | CsdReject of Csd_reject_code.t | LegInconsistent of which_leg | Manual of Operator_id.t`. Seven cases; per-CSD ISO 20022 reason codes mapped via PO-5 normalisation table. The closed-sum-with-typed-payloads structure is what the spec needed (vs a free string).

**Boundary-case shrink discipline.** §13.4.4 v3 update is exactly right: "Generators whose name encodes a presupposition (`_in_window`, `_chain`, `_with_X`) MUST shrink toward the minimum-non-trivial value of that presupposition. Shrinking toward zero in such generators is a Hypothesis anti-pattern (the 'shrink-collapses-the-test' failure mode). Code review hard-fails on any generator that violates this discipline." This is the general principle behind R2 N-2 / N-4 and is the right level of generality. Concrete fixes for `gen_partial_chain_depth` (shrinks to 1) and `gen_corporate_action_in_window` (shrinks to 1 CA event) are pinned. R2-N-2, N-4 closed.

**`gen_recon_scenario` (R2 N-6).** §13.4.4 ships the DS3 property-test generator with type signature, narrative spec ("(real_wallet, ccy_or_ISIN, time-window) triple with random in-window cpty_virtual contras, random in-flight states, random CSD-mirror events"), shrink target (minimum non-trivial: 1 cpty contra, 1 in-flight, 0 mirror events), and 1000+ generated scenarios per invocation. R2-N-6 closed. DS3 is now a property, not a worked example.

### FOWLER — §11.6 v10.3 P1–P20 regression gate present?
**Yes.** §11.6 is a 20-row table covering P1..P20 with explicit verdict per row (PASS unchanged / RESTATED / PASS-STRENGTHENED / RESTATED-WITH-CAVEAT) and a `Where` column citing the v3 section that carries the migration. Verdicts are well-distributed: 14× PASS unchanged (P2, P3, P4, P7, P8, P11–P15 as a row, P16, P17, P18, P19, P20), 4× RESTATED (P1→DS2, P5→DS6, P6→DS5, P9→DS16), 1× PASS-STRENGTHENED (P10 strengthened by DS1 phantom-typed enforcement), 1× RESTATED-WITH-CAVEAT (P6 with G5 caveat under Reading (a)). The migration verdict definitions are explicitly stated. Six characterisation tests `char_1`..`char_6` are named with their v10.3 P-axis coverage mapping. PASS gate for v3 release: all six characterisation tests green AND all 11 DS invariants green AND v10.3 P1..P20 regression-gate green. R2-B-5 closed.

### FEATHERS — Six v10.3 characterisation tests included?
**Yes — though by reference, not by full body.** §11.6 names all six: `char_1` (single-trade buy/sell round-trip, exercises P1, P2, P5, P10), `char_2` (two-trade SBL flow, P11..P15), `char_3` (collateral call cascade, P16, P18), `char_4` (recall + buy-in, P17, P20), `char_5` (close-out chain, bitemporal P9 + CORRECTION), `char_6` (multi-day fail aging, P5, P9, monotonicity). Each is committed to run with deferred-settlement primitives composed in (cpty_virtual / csd_virtual extension loaded). CI gate is committed. The R2 M-4 ask was the six tests as **golden-file diff tests pinning v10.3 silent assumptions** — the v3 spec commits to that pattern by naming the six and committing them to CI without modification (i.e., they MUST pass against the extended algebra; if the deferred-settlement extension perturbs a v10.3 silent assumption, one of the six fails). R2-M-4 closed at the spec level. Test-body delivery is execution debt; the v10.3 tests already exist (the spec says "v10.3 ships with six characterisation tests" — they're inherited).

### Mutation testing 80% overall + 100% on DS1 — stated explicitly in §13.6.3?
**Yes.** §13.6.3 commits explicitly: "**80% overall** mutation kill rate on the deferred-settlement extension code base" with named tooling (`mutmut`, `cosmic-ray`, `mutool`) and named scope (§5 FSM step function, §4 recon engine, §6.5 saga code, §10.9 CORRECTION validators, §12.1 type-level boundary code). "**100% on the DS1 mutation class**" with four enumerated DS1 mutations (real↔cpty_virtual swap; emit_trade writer mutation; phantom-class constructor leak; PnL projection read-site mutation). All four MUST be killed by the property tests; failure = release blocker. **SQL-projection-mutation gap acknowledged**: "Hypothesis (and other Python property-test frameworks) cannot mutate raw SQL strings" — and the mitigation is exactly the §12.1.1 phantom-typed wallet handles forcing PnL-bearing reads through a typed projection function (`Position.read_real_wallet : real_wallet wallet_handle -> Position`). The mutation surface moves from raw SQL to typed code where mutators apply. Verification gate stored in `L_7^P.MutationCoverageReports`. R2-B-4 closed.

---

## NEW ISSUES (R3-introduced, all minor — non-blocking)

### N-R3-1 (LAMPORT) — TLA+ variable `PSS_payable / PSS_receivable / PS_payable / PS_receivable` is a four-way decomposition over what is described as signed cpty_virtual storage; verify the model homomorphism

§13.6.2 declares four variables (`PSS_payable, PSS_receivable, PS_payable, PS_receivable`) as "two surface views over the signed cpty_virtual securities-leg storage" and "two surface views over the signed cpty_virtual cash-leg storage." If these are surface views (i.e., projections from a single signed `cpty_virtual` value), the TLA+ model should encode the projection homomorphism explicitly: e.g., `PSS_payable[us, gs, isin] := max(0, -cpty_virtual_signed[us, gs, isin])` and `PSS_receivable[us, gs, isin] := max(0, cpty_virtual_signed[us, gs, isin])`. The current §13.6.2 prose leaves ambiguous whether the model has one underlying signed variable or four surface variables that can drift. **Action.** Pin in §13.6.2 either (a) the four surface variables as the storage layer (with an invariant `PSS_payable * PSS_receivable = 0` per key, i.e., at most one is non-zero), OR (b) one signed `cpty_virtual` variable as the storage with the four surface views as TLA+ definitions (`==`), not state variables. **Severity.** Minor — both encodings are correct; pinning prevents a future model-checking ambiguity.

### N-R3-2 (HUGHES) — `gen_recon_scenario` shrink target "minimum non-trivial scenario (1 cpty contra, 1 in-flight, 0 mirror events)"

The shrink lattice for `gen_recon_scenario` is "1 cpty contra, 1 in-flight, 0 mirror events". This is reasonable for the recon-identity property at the (cpty_virtual, in-flight) boundary. **But mirror events are part of the recon identity** — §4.1 identity binds cpty_virtual ↔ csd_virtual mirror movements. Shrinking mirror events to 0 means the minimal counterexample to a recon-identity violation involving mirrors will collapse out of the mirror regime. By the same boundary-case-shrink discipline §13.4.4 names, mirror events should shrink to 1 (one mirror event) as the minimum non-trivial value when the test class is recon identity. **Action.** Update `gen_recon_scenario` shrink target to "1 cpty contra, 1 in-flight, 1 mirror event" — three minimum-non-trivial dimensions. **Severity.** Minor — this is the same shape as R2-N-2 and R2-N-4 and the same fix; one line of generator code.

### N-R3-3 (FEATHERS) — Six characterisation tests `char_1..char_6` are inherited by reference; v3 does not certify their currency

§11.6 says "v3 commits that **every one** runs unchanged in the deferred-settlement extension as part of CI." The implicit claim is that v10.3 ships with `char_1`..`char_6`. v3 inherits them by reference. **But the v10.3 spec page from which they are inherited is not cited.** If the v10.3 file does not in fact ship six named tests under those exact names, the inheritance fails and v3 owes the test bodies. **Action.** §11.6 add a one-line citation: "Source: v10.3 §X.Y test-suite manifest, items 1–6." If v10.3 does not actually ship under these names, v3 owes the bodies (six small fixed scenarios). **Severity.** Minor — pure documentation pin; closure assumes good faith on the v10.3 inheritance.

### N-R3-4 (BECK) — WS-11 row count: §13.3 shows 12 rows but split-N-3 makes it 13

§13.3 prose says "v2 lists all 12 as sign-off prerequisites" and "Sign-off prerequisite: all 12 pass at every release boundary." After R2-N-3 split, the row count is 13 (WS-1 through WS-12 with WS-11 split into WS-11a + WS-11b). The prose "all 12" should be "all 13." **Severity.** Cosmetic. **Action.** Update row-count prose in §13.3.

### N-R3-5 (LAMPORT) — Sizing `|trades|=4` covers exactly one of each scenario class; symmetry-reduced state space implies finite branching but not necessarily the relevant counterexamples

§13.6.2 sizing: `|trades|=4` (one BUY, one SELL, one partial chain, one fail-then-buyin). This is one of each class — adequate for exercising each path **once**. The interleaving between trades (concurrent partial chain WHILE fail-then-buyin processes) is implicit in the saga semantics but not explicitly named in the sizing. With `depth=8` and concurrent saga steps, the model checker will exercise interleavings up to depth bound. **Action.** Add to §13.6.2 a sentence pinning that interleavings are part of the search: "TLC explores all interleavings of saga signal arrivals across the 4 trades under the named fairness regime." **Severity.** Minor — likely already implicit in the action set, but explicit naming prevents reviewer confusion.

---

## PARETO JUDGMENT

**Pareto IS reached on the testcommittee axis.**

Twelve R2 items closed (3 BLOCKING + 3 MAJOR + 6 NEW R2-issues, all closed). All five R2 specific scrutiny questions answered affirmatively (TLA+ at fidelity, WS-11 split, generators with discipline, regression gate present, characterisation tests committed, mutation targets stated). Four R3 minor observations (N-R3-1..N-R3-5) are flagged for the implementer but do not block — they are documentation / shrink-target / row-count refinements, no architecture impact, ~half-day of patch work each, can roll into v3.1 patch or be deferred to first-implementation review.

**Execution-debt items** (PO-8 TLC run; LedgerReferenceInterpreter ~3 person-weeks; v10.3 char-test currency citation): these are scheduled engineering work, not specification gaps. v3 commits to all of them in §13.6 with stated ETAs. Per the Pareto rule, "specification complete" requires the spec to pin what gets built; "implementation complete" is a downstream gate. The R3 spec is complete on the testcommittee axis.

**The patch round delivered the goods.** The TLA+ rewrite at v3 fidelity (§13.6.2), the mutation testing stanza with the four-mutation enumeration and SQL-gap mitigation argument (§13.6.3), the 20-row regression gate table (§11.6), the characterisation-test mapping (§11.6 char_1..char_6), the bitemporal honesty pin to option (a) (§11.A), the WS-11 split, and the boundary-case shrink discipline as a v3 generator policy (§13.4.4) collectively close every R2 testcommittee finding. The closure record §15.6 honestly tabulates each item with explicit cross-reference to the v3 section that carries the patch.

The new-issues list is short and minor. No blocking. No unmitigated major.

---

## RECOMMENDATION

**PARETO_REACHED.**

The five R3 minor observations (N-R3-1..N-R3-5) are non-blocking. Forward to FORMALIS arbiter or Pareto-declaration phase. If FORMALIS arbiter wants tighter spec on §13.6.2 variable encoding (N-R3-1) or on `gen_recon_scenario` shrink target (N-R3-2), a v3.1 patch round of <1 day delivers all five fixes — but this is below the threshold for a Round 4.

After Pareto declaration: schedule the TLC run (3 days), the LedgerReferenceInterpreter scaffolding (3 person-weeks), and the v10.3 char-test inheritance certification (1 hour, just confirm the v10.3 file ships them) as Phase-4 implementation tasks.

---

*Five voices, one suite, one verdict. Beck reads the WS-1..WS-13 list and accepts the table-of-thirteen. Hughes signs off the boundary-case-shrink-discipline as the right *general* principle behind R2 N-2/N-4. Fowler accepts the 20-row regression gate with explicit verdicts and the six characterisation tests as the v10.3 silent-assumption pin. Feathers accepts the four-mutation DS1 enumeration and the SQL-gap mitigation argument as the right shape — typed code is the new mutation surface. Lamport signs off the TLA+ at v3 fidelity with fairness regime, sizing, bitemporal axes as separate clocks, and 15 encoded invariants — the model is now written, the TLC run is scheduled, the bitemporal honesty is on the page.*

*"Tests are the ultimate specification."* — TESTCOMMITTEE
*"Clean code that works — and the tests now refuse the wrong implementation at four named DS1 mutation sites."* — Beck
*"Boundary-case shrink discipline as policy is better than three boundary-case shrink fixes — generalising is what spec rounds are for."* — Hughes
*"Twenty rows with verdicts, six characterisation tests with P-coverage. The v10.3 → v11.0 migration is now enumerated, not asserted."* — Fowler
*"Four DS1 mutations enumerated; the typed projection IS the mutation surface. Mutation testing has a target now."* — Feathers
*"PO-8 TLC run is owed. The model is written. Execution debt is not specification debt. Pareto."* — Lamport
