# TESTCOMMITTEE — Round 1 Adversarial Review of `proposal_v1.md`

**Reviewers.** Beck, Hughes, Fowler, Feathers, Lamport.
**Phase.** Round 1 Team A adversarial review of the Settlement Team's Phase 2 unified design.
**Independence.** Written without consulting the formalis or jane-street-cto reviews.
**Stance restated.** Tests are normative. The proposal stands or falls on whether its 18 invariants, 7 fault-injection classes, and TLA+/property/walking-skeleton harness can refuse to accept a wrong implementation.

---

## VERDICT

**ACCEPT_WITH_CHANGES.**

The proposal absorbs almost all of the Phase 1 testcommittee programme — the load-bearing economic-exposure-at-T invariant (DS1) survives intact, partial-fill recursion has a named bound (PO-9), DvP atomicity is structural (DS18), witness-discipline is unambiguous (DS4). The architectural choice to demote `pending_in / pending_out` from stored coordinates to projections is defensible and the testcommittee does **not** block on this — but the test seam needs to be explicitly redesigned for that choice; it is currently inherited from the Phase 1 stored-coordinate model and that inheritance is brittle. The TLA+ programme (PO-8) is named but its model is sketched at 2024 fidelity, not 2026 fidelity — the proposal points at testcommittee §8.5 as the spec, which means **it has not modelled its own additions** (PSS/PS dual-wallet split, CSDR penalty obligation as obligation-of-obligation, BoughtIn/Compensated/Defaulted leaf semantics, MAX-projection lattice). That is the single largest gap. Five blocking items, six unmitigated majors, eight minors. Recommend Round 2 revisions before Round 2 implementation.

---

## BLOCKING (B-1 .. B-5)

### B-1 (LAMPORT) — TLA+ model in PO-8 is under-specified for what was added in Phase 2

The proposal commits to TLC at $|W|=3, |U|=2, \mathrm{depth}=8$ with all 18 invariants encoded (PO-8, §13.2; §15.1 known weakness 7). It cites "testcommittee §8.5" as the model. The Phase 1 model encoded six variables: `own, pending_in, pending_out, status, obligation, clock`. The Phase 2 design has changed the **state representation** in ways that the Phase 1 model does not cover:

1. PSS/PS family is now a **wallet-cardinality** variable (`PS_payable[w, cpty, ccy]`, `PSS_receivable[w, cpty, ISIN]`, etc.) — five wallet sub-classes, indexed by `(real_wallet, cpty, ccy_or_ISIN, side)`. State-space explosion is now a function of `|cpty| × |unit| × 2` per real wallet. At `|W_real|=3, |cpty|=3, |unit|=2`, the wallet count balloons to ≥ 39 wallets (3 real + 4 × 3 × 3 × 2 virtual sub-wallets, lower bound). The "10^5–10^6 states" estimate is from the Phase 1 model and is **stale**. Re-estimate.
2. The MAX projection lattice `Settled > PartiallySettled > Failed > BoughtIn > Instructed > Executed > Cancelled` (§5.1) has not been encoded as a TLA+ predicate. The 7-state observable is a *projection* — TLC must verify the projection is a homomorphism (preserves transitions in the per-leg lattice). This is not in §8.5.
2. The 3-leaf closed sum `Pending → Discharged | Compensated | Defaulted` versus the 7-state observable — the proposal claims the observable is the MAX projection (§2.4, §5.1) but the model never encodes both layers. **Inv4 (status monotonicity) on the per-leg layer ≠ Inv4 on the observable layer.** Either both are stated and TLC checks both, or one is a derived invariant of the other and the proposal must say so.
3. CSDR penalty obligations (§6.3) are a *child obligation of an obligation* — the L_15 row spawns a new L_15 row of kind `CSDR_PENALTY` whose discharge predicate is `ByDeadline(buy_in_resolution_date)`. This is an obligation graph, not a flat set. The Phase 1 model assumed flat. Re-spec.
4. Witness-driven discharge (DS4) requires that the model carry a *cryptographic envelope* parameter; the Phase 1 action `ReceiveConfirmation(tx, kind)` did not. To rule out DS4 violations the model must distinguish `Discharge_with_witness` (legal) from `Discharge_by_inference` (illegal); the latter must be a counterexample-producing action that TLC explores.
5. PartiallySettled → child obligation spawn (§6.4) — TLC must terminate; PO-9 has D_max but is not pinned numerically. **Liveness checking with unpinned recursion is undecidable.** D_max must be bound *before* TLC runs.

**Action.** Rewrite the TLA+ model in this proposal at **Phase 2 fidelity**: (a) variables for the PSS/PS wallet family; (b) two-layer status (per-leg leaf + observable projection); (c) obligation-graph; (d) witness as action parameter; (e) D_max numerically pinned. State-space estimate at the rewrite must be re-derived; if `> 10^7`, propose model abstractions (canonical-form quotient on cpty / unit symmetry) before declaring TLC tractable.

### B-2 (BECK) — Walking-skeleton tests do not exist for 7 of the 12 §2.3 variants

§2.3 of the Phase 1 testcommittee proposal listed 12 variants with one walking-skeleton test each. The Phase 2 proposal §6 names six variants (T+1, T+0, Failed, Partial, Cancellation, plus implicit Buy/Sell happy in §3) and worked examples for some (§3, §6.4 partial, §6.5 cancel). It does **not** include walking-skeleton tests for:

- Sell T+2 happy (mirror of §3).
- T+1 happy variant (DS12 commitment is "parameter, not architecture" — must demonstrate by test).
- Reconciliation lag scenario (recon engine §4 must have a passing test, not just a SQL query and prose).
- Short-sale composition (§7.3 has worked numbers but no test; SBL composition is the most complex and most likely to leak invariant).
- Recall during open window (§7.4 — table is given, no test).
- Corporate action across the window (§13.1 G3 — named as gap and PO-4, but no walking-skeleton test exists).
- Cross-currency Herstatt (§9.3(a), §13.1 G10 — only worked example fragments; no end-to-end test).
- DvP CSD reject — not in §6 at all.

Each of these must have a Beck-style ≤30-line test in `proposal_v2.md`'s test annex. Worked examples in prose are not tests; they are not normative; they cannot fail in CI.

**Action.** Either ship the eight missing walking-skeleton tests in the next revision, or explicitly mark which scenarios are deferred to Phase 3 implementation with a named test_id placeholder per scenario.

### B-3 (HUGHES) — Property generators are not implementable from §3.3 alone

The Phase 2 proposal at §11 enumerates 18 invariants but does **not** include property-test generator code. The Phase 1 testcommittee proposal §3.3 had `TradeStream(seed, max_trades=200)` with explicit distribution choices. The Phase 2 proposal references the Phase 1 generator (PO-8, "per testcommittee §8.5") but the generator universe must now cover:

- **Wallet keying.** `(w_real, cpty_lei, ccy_or_ISIN, side)` — generator must produce LEIs (closed sum from a fixed pool, not free-form strings) and ISINs (closed sum from L_2 InstrumentMaster).
- **Settlement-window parameter** (DS12). settle_date must be drawn from `{T+0, T+1, T+2, T+3, T+5}` with weighting; T+2 cannot dominate or DS12 is not exercised.
- **Witness envelopes** (DS4). Generator must produce `sese.025`, `sese.024`, `camt.054` with `EndToEndId`; must also produce *malformed* witnesses (DS4 negative path).
- **Restated witnesses** (G5). Generator must produce CSD restatements (yesterday "100", today "60") to exercise the recommended Choice (a) — restatement-as-new-obligation.
- **Bitemporal corporate-action interleaving** (G3, PO-4). Generator must produce stock splits (2-for-1, 3-for-1, 1-for-2) interleaved with open-obligation deadlines.
- **Counterparty default** (DS15). Generator must produce a `CounterpartyDefault(t_def)` event; verify all open obligations against the defaulting cpty transition to `Compensated`.

The proposal needs, at minimum, the **generator type signatures** and the **shrink lattice for each new dimension**. Without them the property suite is not implementable; PO-8 is unrunnable.

**Action.** Add §11.5 "Property generators" with type signatures and shrinking strategies for each of the 6 dimensions above. Hughes's rule: **counterexample to DS1 must shrink to ≤ 3 events; counterexample to DS2 must shrink to ≤ 2 events.** If shrinking does not deliver, the generator is wrong.

### B-4 (FEATHERS) — Mutation testing target ≥ 80% is not achievable for DS1 (target 100%) under the projection-only `pending_*` model

The proposal §15.1 weakness 8 references minsky's 14-week migration plan. Mutation testing is mentioned in §11 invariant register and PO-8 but **the mutation score targets are not in the proposal**. The Phase 1 testcommittee §9 set:

- DS1-targeted mutation: **100%** (the most important number).
- Overall: ≥ 80%.

The class of mutations that DS1 must catch is `pnl(w) = own × Δp` versus `pnl(w) = (own + pending_in) × Δp`. **Under the Phase 2 projection-only model, `pending_in` is not a stored field — it is a SQL projection over `WHERE wallet_class='virtual_PS_receivable' AND real_wallet=:w`.** A naive PnL implementation that joins `position_state` to `wallet_registry` and sums across all wallets in the family **will not be detectable as a mutation by a code-mutator** because it is *not a code mutation* — it is a *query-shape choice*. The mutation testing tool (mutmut, pitest) does not mutate SQL projections.

This is a real concern. Three options:

1. Hand-write a "PnL-shape audit" that asserts `pnl()` is computed only over `WHERE wallet_class='real'`. Run as a separate quality gate, not as mutation testing.
2. Wrap the PnL query in a typed projection (`pnl_trade_date_basis : RealWalletHandle -> Money.t` per minsky §12.6) and mutation-test the *type-checked* PnL function. Mutations that swap `RealWallet` to virtual handle become compile-time errors; mutation-survival rate against the typed boundary becomes the meaningful metric.
3. Accept the gap honestly: mutation testing covers ≥ 80% of *typed* code but **cannot** cover query-shape mutations. Document this in §11.

The proposal must pick one of these and state it. Otherwise the "mutation score 100% on DS1" target is not achievable, and the proposal claims a guarantee it cannot deliver.

**Action.** Add §11.4 "Mutation testing targets" with explicit numeric targets, the named gap on query-shape mutations, and minsky's typed-PnL approach (option 2) as the recommended mitigation. The proposal currently has neither the targets nor the gap acknowledged.

### B-5 (FOWLER) — Refactoring safety: v10.3 test suite regression gate not specified

§15.1 weakness 8 mentions the migration plan is "production-safe" in stages 1-4 but the proposal does **not** specify the regression-gate that v10.3 tests must pass. From Phase 1 testcommittee §8.3:

> The seam between v10.3 closed-system and the new mechanism is at the StateDelta boundary. The deferred-settlement extension introduces two new coordinates (`pending_in`, `pending_out`) on `PositionState`, ...

This was the Phase 1 design. The Phase 2 design has **no new coordinates on `PositionState`** (§2.5 conformance verdict). Instead, it has new wallet *classes* via WalletRegistry sidecar metadata (§2.3). This changes the regression seam:

- v10.3 tests that read `position_state(w, u).own` continue to read it — fine.
- v10.3 tests that **enumerate wallets** via `SELECT * FROM wallet_registry` will now see PS/PSS rows they did not see before, possibly breaking tests that assumed `len(wallets) = N` for some hardcoded N.
- v10.3 tests that **sum `own` across all wallets for a unit** will now sum over PS/PSS too. Conservation `Σ_w own(u) = 0` was a v10.3 invariant on real wallets only? Or all wallets? **The proposal does not say.** §2.6 says "PS/PSS wallets are full participants in W_virtual and contribute to the sum by construction" — meaning the sum is over `W_real ∪ W_virtual`. If v10.3 tests sum over `W_real` only, they regress.
- v10.3 reconciliation tests that check `nostro_external = w.own(ccy)` will break; the new identity is `nostro_external = own + Σ PS_payable - Σ PS_receivable - inflight_out + inflight_in`.

**This is a real regression risk.** Fowler's rule: every v10.3 test must pass without modification, OR the modification must be enumerated and approved.

**Action.** Add §11.6 "v10.3 regression-gate" listing every v10.3 invariant (P1-P10) and SBL invariant (P11-P20) and certifying behaviour-preservation. For each, state: (a) test passes unchanged, (b) test passes after schema migration, or (c) test must be replaced — with the new test specified.

---

## UNMITIGATED MAJOR (M-1 .. M-6)

### M-1 (HUGHES) — `pending_in`/`pending_out` as projection makes property tests brittle

The Phase 1 testcommittee position was: store `pending_in`/`pending_out` as additive non-negative coordinates on `PositionState`. The Phase 2 proposal demotes them to projections (§1 "What was rejected" item 3, §4.3 SQL).

**Why projections suffice for tests:** the property assertions are on observable behaviour (PnL, conservation, recon identity), and a projection is a deterministic function of the stored state. As long as the projection is pure and idempotent, the property test does not care whether the value is stored or computed.

**Why projections are brittle as a test seam:**

1. **Test setup becomes harder.** The Phase 1 setup `L.assert pending_in(buyer_w, XYZ) == 100` becomes `L.assert PositionState[PSS_receivable[buyer_w, GS, XYZ]].own == -100` (or `+100`, depending on sign convention §2.7 and §4.2 — not an obvious expansion). Test readability degrades.
2. **Sign convention is now load-bearing in the projection.** §4.2 corrected finops's Phase 1 sign error. Every property test that asserts on `pending_*` must now use the corrected sign — and every old test that assumed the wrong sign is silently broken.
3. **Counterexample shrinking is harder.** Hughes's rule: counterexample to DS3 (recon identity) must shrink to ≤ 2 events. If the projection involves a SQL JOIN across `wallet_registry` and `position_state`, the shrinking machinery must traverse the join structure to find the minimal violating wallet-row pair. Property frameworks (Hypothesis, fast-check, Hedgehog) shrink over generated inputs, not over query structures. **Shrinking will produce the failing trade stream but not the failing wallet pair**, making counterexample diagnosis worse.

The testcommittee accepts the projection-only model (we do not block here) but flags the test-layer cost as real. Mitigation: add a `view.pending_in(w_real, u)` and `view.pending_out(w_real, u)` projection function in the test harness (NOT in the production schema) so test code reads the same shape as Phase 1. Document this as test-only scaffolding.

### M-2 (LAMPORT) — Liveness verification under bounded Temporal cluster outage (G8) is not formally argued

§13.1 G8 states: "Liveness is *eventual* under cluster outage, not instantaneous. ... Cannot eliminate — timer fires in workflow's logical time, regulatory deadlines tick wall-clock. Mitigated by multi-region replication, external watchdog, SLA on cluster availability."

The proposal accepts G8 as "not closable by formal proof." This is honest. But the proposal also commits to **DS9 (buy-in compensation closure)**, **Live1 (every instruction terminates)**, **Live2 (every fail-obligation terminates)** in PO-8. These are liveness invariants under fairness assumptions. **What are the fairness assumptions?**

- Weak fairness on `ReceiveConfirmation` per tx? Assumes CSD eventually responds.
- Strong fairness on `Tick`? Assumes wall clock advances.
- Weak fairness on `Discharge` for *every* obligation, including CSDR_PENALTY children?

If fairness is "weak fairness on every action enabled in every state," the model is over-fair and TLC may declare liveness counterexamples impossible by assumption. If fairness is "weak fairness on `ReceiveConfirmation` only," then a CSD that confirms but never sends `sese.024` for a fail leg can stuck the system — and TLC will find a counterexample.

**The proposal must state the fairness regime and justify it.** Either (a) commit to a specific fairness regime per action, with a one-line justification (e.g., "WF on ReceiveConfirmation: CSDR-required attestation"), or (b) downgrade the liveness invariants to *bounded liveness* (within bounded number of `Tick` actions, the obligation transitions to a non-terminal state) and verify with TLC bounded-liveness on a finite slice.

**Without this, "PO-8 passes TLC" is a meaningless claim.**

### M-3 (BECK) — The DvP-leg-asymmetric failure (G4) has no walking-skeleton test

§13.1 G4 names the gap: cash leg `Settled`, securities leg `Failed`. The proposal says "catalogue per CSD ... in `L_16.ReferenceMaster` and dispatch κ accordingly." This is correct. But §6 (variants) and §3 (worked example) do not include a test for this case.

**The G4 case is the single highest-risk failure mode** because:

1. It violates DS18 (DvP atomicity) at the discharge-time, which §12.2 PairedObligation is designed to prevent.
2. It is rare but real (CLS-non-eligible cross-currency, non-DvP CSDs).
3. Compensation routing is per-CSD and per-regime — a hot zone for off-by-one in the κ dispatch table.
4. minsky §12.2 gives `Confirmation_only_one_leg CashLegOnly` as the typed result. But the runtime test that this is observable, that no real-wallet move occurs, that the break workflow opens — is not in the proposal.

**Action.** Add a walking-skeleton test `test_dvp_asymmetric_csd_fail_securities_only_cash_settled` that:

- Constructs a paired obligation;
- Injects `sese.025` for cash, `sese.024` for security;
- Asserts `discharge` returns `Error (Confirmation_only_one_leg CashLegOnly)`;
- Asserts `w_us.own(USD)` and `w_us.own(XYZ)` are unchanged;
- Asserts `BreakRegister` row of kind `dvp_asymmetric_settlement`;
- Asserts κ dispatch fired the correct compensation for the CSD's regime per `L_16.ReferenceMaster`.

### M-4 (FEATHERS) — Characterisation tests against v10.3 not specified

Phase 1 testcommittee §8.4 named six characterisation tests:

1. `test_v10_3_pnl_uses_own_only`
2. `test_v10_3_recon_uses_settled_bucket`
3. `test_v10_3_clone_at_includes_obligations`
4. `test_v10_3_fail_does_not_reverse_position`
5. `test_v10_3_settle_projection_is_pure`
6. `test_v10_3_fail_resolution_is_closed_sum`

These pin v10.3 silent assumptions before the extension is allowed to land. None of them appear in proposal_v1. The proposal jumps directly to DS1-DS18 without first pinning v10.3 baseline.

**Risk.** v10.3 has known silent assumptions that the deferred-settlement extension will probabilistically hit:

- Implementer assumes `own` is the position for valuation but adds `pending_in` for "settled position" — DS1 silently violated.
- Implementer assumes "ledger == external" recon — DS3 silently violated during open window.
- Implementer adds "hold-and-retry" as a fail-resolution path — DS9 closure silently broken.

**Without characterisation tests, the regression-gate (B-5) is unenforceable.** Feathers's rule: "Code without tests is bad code." The corollary for legacy code: the test you don't write is the assumption that will silently break.

**Action.** Add §11.7 "v10.3 characterisation tests" enumerating the six tests above, each with a stub implementation showing what is golden-fixed. These are not assertion tests — they are golden-file diff tests, intentionally fragile, designed to detect *any* change in behaviour.

### M-5 (HUGHES) — DS5 (replay determinism) generator does not exercise CSD restatement

DS5: "For any two interleavings π_1, π_2 of the same multiset of confirmation messages applied to the same initial state σ_0: apply(σ_0, π_1) = apply(σ_0, π_2)."

This is verifiable by property test — generate a stream, permute, replay, compare canonical state. **But §13.1 G5 (CSD restatement) explicitly notes that `Discharged` obligations cannot be "un-Discharged."** The recommendation is choice (a): treat restatement as a new obligation. The DS5 generator must therefore produce **restatement events** (not just confirmation events) and verify that:

1. A restatement does not mutate the original obligation;
2. A new obligation row is appended with `parent_obligation_id` linking to original;
3. The bitemporal `as_of(t_known_orig)` query returns the original (pre-restated) state;
4. The `with_corrections_through(t_known_new)` query returns the corrected state.

Without this generator coverage, DS5 is verified only on the easy case (commutative confirmations) and not on the hard case (corrective confirmations). The hard case is where the bug lives.

**Action.** Add to §11.5 (B-3) generators a `RestatementEvent(orig_msg_id, restated_qty, t_known_new)` constructor and verify property bullets 1-4 above.

### M-6 (LAMPORT) — Bitemporal model checking is not in PO-8

DS16 (bitemporal restatement, never mutation) is named as compile-time-enforced (append-only structure). But DS5 (replay determinism), DS6 (idempotency), DS13 (recon pair anchoring), and the corporate-action invariants (PO-4 / G3) all require *bitemporal* reasoning — `t_obs` versus `t_known`. The TLA+ model in Phase 1 §8.5 uses a single monotone `clock`. **One clock cannot model bitemporality.**

To verify DS16 + DS5 + G3 jointly, the model needs:

```
VARIABLES
    t_obs,        \* observed time
    t_known,      \* knowledge time (when we learned the fact)
    history,      \* function from (t_obs, t_known) to state
```

The action `RestateConfirmation(msg_id, new_qty, t_known')` writes `history[t_obs, t_known']` while preserving `history[t_obs, t_known]`. Append-only is structural; replay determinism becomes "for any two t_known projections, replay is consistent." This is a **harder** TLA+ model; the state space is larger (cross-product of t_obs × t_known).

The Phase 1 §8.5 model does not encode this. PO-8 cites the Phase 1 model. Therefore PO-8 as currently scoped does not verify DS16, and the bitemporal commitments of §10.9 are not formally checked.

**Action.** Either (a) accept that DS16 is structural only (append-only log = structural; not TLA+-checkable in the interesting sense), document this in §11 invariant register; or (b) extend the TLA+ model with bitemporality and check the joint property `DS5 ∧ DS16 ∧ G3`. Option (a) is the honest minimum.

---

## MINOR (m-1 .. m-8)

### m-1 (BECK) — Test naming convention from Phase 1 §8.1 not adopted

`test_<actor>_<scope>_<scenario>_<outcome>`. None of the proposal's test stubs follow this. Adopt or explicitly reject.

### m-2 (HUGHES) — Combinatorial coverage criteria from Phase 1 §8.2 absent

Pairwise of (variant × outcome × delay × settle_date) at minimum, full at CI nightly. The proposal does not state coverage criteria. Add §11.4.

### m-3 (FOWLER) — Test pyramid shape (60/30/8/2) absent

Phase 1 §8.3: 60% unit, 30% property, 8% integration, 2% characterisation/E2E. The proposal cannot be interpreted to enforce a pyramid shape. Add or reject.

### m-4 (FEATHERS) — Mutation-survivor categories absent

Phase 1 §9 listed four mutation-survivor categories the suite cannot catch (wall-clock side effects, error message text, cross-workflow races, hash-preserving serialization mutations). These are honesty-gate items. Reproduce in §11 or rebut.

### m-5 (LAMPORT) — `|trades|` parameter absent from PO-8

PO-8 specifies `|W|=3, |U|=2, depth=8` but not `|trades|`. The Phase 1 model used `|trades|=4`. Pin or justify omission.

### m-6 (BECK) — §3 worked example numbers are hand-checked, not test-asserted

The conservation tables in §3.6 are correct as far as I can verify by hand, but they are not presented as runnable tests. Convert to test fixtures in `proposal_v2.md`.

### m-7 (HUGHES) — `Decimal` precision in generators not pinned

§4.6 pins decimal precision per quantity type. Generator must produce values at the *correct precision* for the type — JPY at `D_2` is already a bug in the test fixture. State this in §11.5 generator definitions.

### m-8 (FEATHERS) — "Aged-1, Aged-3, Aged-5" L_18 FSM (§4.9) has no characterisation test

The aging table is operational. Each transition is keyed on `bd_count_since_intended_settle_date`. Off-by-one (one BD vs. one calendar day) is the most common bug class here. A characterisation test that pins the calendar convention (per `L_4 CalendarConvention`) is required.

---

## WHAT WORKS

- **DS1 (Economic-Exposure-at-T) survives intact** as MANDATORY CRITICAL. The Phase 1 testcommittee P_DS_1 is preserved verbatim. This is the single most important alignment.
- **DS18 (DvP ledger-level atomicity) is structural.** PairedObligation (§12.2) is a real type-system commitment, not an assertion.
- **DS4 (no discharge without witness) is unambiguous.** The framework "never marks a leg `Discharged` by inference, by clock, or by absence of evidence" (§5.4). This is the right rule.
- **DS12 (variant degeneration: T+1 is a parameter)** is the test of CDM-native architecture. The proposal commits to this clearly.
- **The 18 invariants are well-typed (§11.) and decomposed honestly into compile-time / runtime / hybrid (§11 type-vs-runtime summary).** The recommendation to take typing cost for DS17 + DS7 is sound.
- **§13 enumerates 12 gaps and 10 proof obligations honestly.** This is the discipline that distinguishes a specification from documentation. Each gap has a named owner and a closing constraint.
- **The seven critical fault-injection scenarios** (Phase 1 §10) are mostly preserved in the variants of §6 + §13.1. The mapping is implicit but recoverable.
- **Wallet split into payable/receivable (§2.7) preserves IFRS 7 gross presentation.** Pacioli's name is invoked correctly.
- **The CDM cross-walk (§8) is honest — Direct 11 / Partial 6 / Missing 7** — and the four Rosetta PRs (PR-1..PR-4) are appropriately scoped.

---

## SPECIFIC SCRUTINY (responding to the prompt)

### "Are projections sufficient for the test seam, or does the test layer become brittle?"

Sufficient with a test-harness `view.pending_in()` shim (M-1). The production model can stay projection-only; the test layer needs a stable surface. The proposal must add this shim or accept that test setup will become more verbose and tied to the wallet-keying schema.

### "Mutation testing target ≥ 80%; for DS1 mutation class, 100%. Is this achievable with the proposed state model?"

**Not without minsky's typed-PnL boundary** (B-4). Mutation tools cannot mutate SQL projections. The 100% target on DS1 requires the PnL function to take a `RealWalletHandle` (phantom-typed) — which is exactly minsky §12.6. If the typed boundary ships, the target is achievable; if not, the target is unattainable and the proposal should be honest about the gap.

### "The 18 invariants — which are testable as properties, which require model-checking, which only manual review?"

Verifying the §11 type-vs-runtime summary and applying our hierarchy (§Phase 1 §3.2):

| Invariant | Property test | Model-check (TLA+) | Manual review |
|---|---|---|---|
| DS1 — Economic exposure at T | YES (Hughes generator) | YES (Inv1 of TLA+) | — |
| DS2 — Conservation | YES | YES (Inv1) | — |
| DS3 — Recon identity | YES | partial (only on slice) | yes (sign convention manually verified once) |
| DS4 — Discharge without witness | YES (negative path) | YES (witness as parameter) | — |
| DS5 — Replay determinism | YES (permutation generator) | YES | — |
| DS6 — Idempotency | YES | YES | — |
| DS7 — Failure non-reversal | YES | YES (Inv5) | — |
| DS8 — Status monotonicity | YES (closed-sum exhaustive) | YES (Inv4) | — |
| DS9 — Buy-in closure | YES (compensation pairing) | YES (Liveness Live2) | — |
| DS10 — Herstatt visibility | partial (need cross-currency generator) | YES (asymmetric leg state) | — |
| DS11 — Partial conservation | YES (residual generator) | YES (with D_max) | — |
| DS12 — Variant degeneration | YES (parameter generator) | partial (modeled as input) | — |
| DS13 — Recon pair anchoring | YES (cron generator) | partial | yes (cadence) |
| DS14 — CSDR penalty determinism | YES (rate-table replay) | partial | yes (rate values) |
| DS15 — Counterparty default | YES (default event generator) | YES | yes (close-out value) |
| DS16 — Bitemporal restatement | YES (append-only generator) | needs bitemporal model | — |
| DS17 — Capability scoping | NO (compile-time only) | NO | YES (review of phantom types) |
| DS18 — DvP atomicity | YES (asymmetric injection) | YES | — |

13 of 18 are property-testable. 12 are model-checkable (with M-2, M-6 fixes). 4 require manual review (DS3 sign, DS13 cadence, DS14 rate values, DS17 type discipline).

### "7 critical fault-injection scenarios — does the proposal name enough or hide some?"

The Phase 1 §10 listed eleven fault-injection scenarios. The Phase 2 proposal references them implicitly through §4.5 (BreakRegister kinds), §5.5 (idempotency), §6 (variants). It does not enumerate them as a discrete fault-injection inventory. Hidden / missing:

- **Confirmation conflict** (two independent confirmations: one SETTLED, one FAILED, supplier/CSD disagree). Phase 1 §10 row 8. Not in proposal.
- **Operator out-of-band status change** (manual DB write to mutate `lifecycle_stage`). Phase 1 §10 row 11. Implicit in §10.6 CO-8 but no test.
- **CSD clock skew** (firm vs CSD timing). Phase 1 §10 rows 5-6. Implicit in G7 but no test.
- **Custodian batch with mixed outcomes**. Phase 1 §10 row 7. Not in proposal.

**Action.** Add §11.8 "Fault-injection inventory" with eleven named scenarios from Phase 1 §10, four of which are already listed above as missing. Each gets a test name.

### "Does §13 honestly enumerate the gaps?"

Yes, with one item that warrants escalation:

- **PO-9 (D_max)** is named "jane_street caps at 2; sbl/temporal/karpathy allow recursion." This is a **decision deferred**, not a gap. The TLA+ liveness check (PO-8) cannot run without D_max pinned (B-1, item 5). **PO-9 is a Round 2 prerequisite, not a Round 2 deliverable.** Escalate to Pareto-arbiter immediately, before TLC. The proposal §15.3 lists this as a Pareto-arbiter ruling — agreed; flag urgency.

The other gaps (G1-G12) are honest. G6 (cross-jurisdiction T+1/T+2) is the most operationally consequential and is correctly framed as parameter-driven. G8 (Temporal cluster outage) is correctly framed as not-closable-in-ledger; M-2 above asks the proposal to be precise about *what fairness regime* it does commit to.

---

## RECOMMENDATION

**ACCEPT_WITH_CHANGES** — proposal is structurally sound and absorbs the Phase 1 testcommittee programme on the load-bearing items. Round 2 cannot proceed until five blocking items are addressed:

1. **B-1.** Rewrite TLA+ model at Phase 2 fidelity (PSS/PS family, two-layer status, obligation graph, witness parameter, D_max bound). Re-estimate state space; adopt symmetry abstractions if needed.
2. **B-2.** Ship walking-skeleton tests for the 8 missing variants (Sell happy, T+1 happy, recon-lag E2E, short, recall, CA, FX Herstatt, DvP CSD-reject).
3. **B-3.** Add §11.5 "Property generators" with type signatures and shrink lattices for 6 dimensions.
4. **B-4.** Add §11.4 "Mutation testing targets" with explicit numerics, named query-shape mutation gap, and minsky §12.6 typed-PnL as mitigation.
5. **B-5.** Add §11.6 "v10.3 regression-gate" certifying behaviour-preservation for P1-P10 + P11-P20.

Six unmitigated majors (M-1 .. M-6) are real but not Round-2-blocking. Eight minors (m-1 .. m-8) are bookkeeping.

**Pareto-arbiter escalation:** PO-9 D_max numeric bound is a **prerequisite** to PO-8 TLC run, not a parallel proof obligation. Resolve before Round 2, not during.

After these fixes, the proposal is implementation-ready and the deferred-settlement extension is *normative* — what the test suite refuses to accept defines the spec.

---

*Five voices, one suite, one verdict. Beck wants the eight missing tests on a screen. Hughes wants the generator types signed before the property suite is buildable. Fowler wants the v10.3 regression gate locked before any line of new code lands. Feathers wants the silent v10.3 assumptions golden-pinned before the extension is permitted to perturb them. Lamport wants the TLA+ model rewritten at Phase 2 fidelity, with fairness made explicit, before "PO-8 passes" means anything.*

*"A unit test that takes 1/10th of a second is a slow unit test."* — Feathers
*"Don't write tests. Generate them — but only after you have specified what they generate."* — Hughes (paraphrased)
*"If you're thinking without writing, you only think you're thinking."* — Lamport
*"Clean code that works — but only after the test refuses to accept the wrong implementation."* — Beck
*"The whole point of the test pyramid is to remind us that broad scope tests should be rare."* — Fowler
