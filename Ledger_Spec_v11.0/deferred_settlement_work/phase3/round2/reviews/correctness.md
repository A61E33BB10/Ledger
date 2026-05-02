# Round 2 Adversarial Review — Correctness Architect

**Subject.** `proposal_v2.md` — Phase 3 Round 2 Settlement Team revision of the Deferred-Settlement specification.
**Reviewer.** Correctness Architect (Will Wilson, deterministic-simulation lens).
**Date.** 2026-04-30.
**Scope.** Verification of R1 closure (B-1..B-6 from this reviewer + the cross-cutting blocking themes) and adversarial pass on new material (§0, §3.X, §4.5, §6.5, §7.5, §10.7, §13.4, §13.5).

---

## Verdict

**ACCEPT_WITH_CHANGES.** Pareto NOT reached, but the gap is small.

The Settlement Team has done the structural work. R1 blockers in **my** domain (correctness, B-1..B-6) are **5 of 6 closed and 1 substantively closed but with a load-bearing residual** (B-1 — the property catalogue). The new sections — §0 notation, §3.X SELL example, §4.5 envelope, §6.5 workflow specification, §7.5 Conservation Lifting Theorem, §13.4 Goodhart traps, §13.5 trust registry — are competently constructed and adversarially honest. §6.5.5 commutativity table and §6.5.7 saga compensation tower in particular are the kind of pinned-down work that distinguishes a spec that *can* be implemented from one that *will* be argued about for six more weeks.

**Why not Pareto.** Two new blocking findings (one technical, one specification-discipline) and three new majors emerged in the v2 review:

1. **N-B-1 (NEW BLOCKING).** §3.6 conservation table is in **delta** form, but §7.5 Conservation Lifting Theorem asserts conservation in **absolute** form. The 1M USD pre-trade `w_us(USD)` has no source wallet inside the named constant universe. Either the theorem must restrict to deltas (and §2.6 must be restated), or the constant universe must include a prior-counterparty wallet that sources the float. As written, §3.6 satisfies the theorem only by sleight of hand. This is a Goodhart trap exemplar — the table looks clean because it sums deltas; the theorem looks clean because it sums absolutes; nobody verified they speak the same language.

2. **N-B-2 (NEW BLOCKING).** The R1-mandated property *DS19 — Witness-Identity Determinism* (B-1.f from this reviewer) is **not in §11**. It is named in passing in §6.5.6 (envelope dedup) and §13.5 TA-DS-1, but it is not a numbered DS invariant. Without DS19, DS4 (No Discharge Without Witness) is conditional on an unwitnessed assumption. This is the precondition gap I flagged in R1 and it remains.

R1-MAJOR closure is satisfactory. R1-MINOR closure is satisfactory.

---

## R1 closure table — by R1 finding ID

| R1 finding | v2 status | v2 location | Reviewer verdict |
|---|---|---|---|
| **B-1.a** Cross-trade finality path-independence | Partial | §6.5.5 commutativity table (last row "Cross-trade signals (different `tx_id`) — independent") | **PARTIAL.** Independence asserted; not stated as a DS invariant. The R1 finding asked for a property test for two trades touching the **same `(w, u)`** with interleaved finality; v2 names cross-`tx_id` independence which is the easy case. The hard case (same `(w, u)`, different `tx_id`s, interleaved finality witnesses) is not explicitly asserted. **Stricter coverage required**: add a property under DS5/PO-8 covering same-`(w,u)`-multi-trade interleaving. |
| **B-1.b** PnL invariance across discharge boundary | **CLOSED** | §3.7 PnL trace + §3.X.5 SELL verification + DS1 + the implicit corollary that `w_us.own` does not move at finality (DS7 / §6.5.3) | DS1's economic-exposure-at-T plus DS7's failure-non-reversal plus the §3 worked example showing `w_us.own(USD) = 995,000` from T+1 through T+2⁺ together imply this. Acceptable. |
| **B-1.c** Recon identity at every partial checkpoint | Partial | DS11a (§11) + §6.4 partial table | **MOSTLY CLOSED.** DS11a names per-step conservation (`q_remaining + q_settled = q_initial`). The recon-identity-at-each-partial-step is implied by DS3 + DS11a, but is not explicitly listed. **Add as a property test in PO-1 wording**: "DS3 + DS11a hold at every partial checkpoint." Worth pinning explicitly to forestall a generator that only checks endpoints. |
| **B-1.d** Compensation κ-totality compile-time | Partial | §12.1.4 closed-sum `failure_reason` + §13.2 PO-5 deferred | **PARTIAL.** v2 closes the type-level closed sum on `failure_reason`. But the κ-matrix `EventClass × ObligationKind` (the cell-by-cell handler grid) is NOT made compile-time exhaustive in v2. PO-5 (per-CSD failure-reason mapping) is explicitly deferred. This is a real open. **Acceptable as deferred** but the proposal should explicitly state that until PO-5 closes, the framework has a documented witness-launderer trapdoor on novel `Csd_reject_code` values. |
| **B-1.e** Partial cascade termination at D_max | **CLOSED** | DS11b clause 3 ("Termination: chain terminates within $D_{\max} = 2$") + §6.4 ("beyond `D_max` cascade transitions to `Failed → Compensated`") | Clean. |
| **B-1.f** Witness-identity determinism (DS19) | **NOT CLOSED** | Mentioned in §6.5.6 dedup_key + §13.5 TA-DS-1, but not a numbered DS | **NEW BLOCKING (N-B-2).** This is the load-bearing precondition for DS4 idempotency. v2 talks around it but does not assert it. See N-B-2 below. |
| **B-2** Two non-deterministic boundaries unenumerated | **CLOSED** | §6.5.1 `tx_id` formula uses content-addressed `business_event_id` (no collision under partial-restatement); §6.5.5 commutativity table has explicit row for `correction_tx vs sese.025` race | The two specific R1 boundaries are now addressed: (a) `tx_id` collision under partial-restatement is solved by `business_event_id = "final:" || referenced_tx_id || ":" || msg_id_set` which is content-addressed on the inbound message ID set; (b) sese.025-vs-CORRECTION race is named in §6.5.5 last row with explicit precedence "terminal absorbs". Closed. **Caveat:** I would prefer a §11.bis or §13.bis enumerating ALL non-deterministic boundaries as a single table, rather than scattered through §6.5. See M-1 below. |
| **B-3** Generators (3 sub-blockers) | Partial | §13.4.4 generator type signatures + §13.4 Goodhart traps | **MOSTLY CLOSED.** B-3.a (multiset, all permutations) — closed by `gen_witness_arrival_perm :: List Witness -> Gen Permutation`. B-3.b (failure-reason closed sum) — closed by `gen_failure_reason :: Gen FailureReason` with closed sum from §12.1.4. B-3.c (pathological CAs in window) — closed by `gen_corporate_action_in_window :: Gen CorpAction`. **However:** the type signatures alone are not generators; an implementer can write an unsound `Gen FailureReason` that always returns `DeadlineMissed`. The shrink lattice helps but does not prevent a generator that ignores some inhabitants. **Strong recommendation:** add a coverage gate to PO-8 — every inhabitant of every closed sum MUST be exercised at least once per test class run. See M-2. |
| **B-4** Differential testing oracle | Not closed | Not addressed | **NEW BLOCKING-LIKE FINDING (M-3 elevated to top-of-major).** v2 has no §13 / §15 entry naming the **naive sequential reference interpreter** that any high-performance implementation must produce bit-identical state against. PO-8 names a TLA+ model check (good but different — TLA+ checks the model, not the implementation). Without a sequential reference, "the implementation passes its own property tests" is a circular oracle. The CDM forgetful functor F as differential oracle (B-4.b) is now correctly named as lossy non-faithful (§8.4) which strengthens it conceptually but the v2 does not commit to F as a test oracle. **Strong recommendation:** §13 PO-11 (new): "A reference sequential interpreter is implemented; every property test additionally checks bit-identical state against the reference; F-projection equality also checked on `Lg_econ`." |
| **B-5** Fault catalogue (network split, Byzantine clock, bugification, forged envelope) | Partial | §4.5 (forged envelope); §13.5 TA-DS-1, TA-DS-5 (Byzantine clock); G8 cluster outage (mitigated, not closed) | **PARTIAL.** Forged envelope: §4.5.1 Ed25519 sig + verify at L_11 ingest closes this. TA-DS-5 (clock skew bounded ≤ 5s) names Byzantine clock as a trust assumption, not a fault test — i.e., it is *assumed* uncompromised, not *injected* as a fault. **Network split**: not enumerated anywhere. G8 (prolonged Temporal cluster outage) is "not closable by formal proof; mitigated by multi-region replication + external watchdog" — that is mitigation, not fault-injection. **Bugification** (FoundationDB-style legal-but-pathological CSD behaviour) — not named. The R1 ask was an explicit bugification operator; v2 has none. See M-4. |
| **B-6** Goodhart traps G-DS-1/2/3 | **CLOSED** | §13.4 G-DS-1, G-DS-2, G-DS-3 | All three named. G-DS-1 (quick-finality bias) — empirical-distribution sampling pinned in `L_7^P.GeneratorDistributionPin`; uniform draws forbidden. G-DS-2 (per-class conservation) — per-`(unit_class, wallet_class)` assertions auto-generated. G-DS-3 (record-and-replay) — generators hand-authored from spec, not from prod traces; LLM-assisted refactoring allowed for implementation only. **This is the single most thorough closure in v2.** Genuine credit. The G-DS-1 mitigation in particular is exemplary — pinning the empirical distribution as a versioned artefact in `L_7^P` is the right move. |

**Subtotal:** 3 fully closed, 3 partially closed, 0 missed (B-1.f is partially closed via §6.5.6/§13.5 mention but the load-bearing DS19 invariant is missing — graded as NEW BLOCKING N-B-2).

---

## §11 invariants pruned from 18 to 10 — completeness check

| v2 invariant | Status | Comment |
|---|---|---|
| DS1 Economic-Exposure-at-T | Present, hybrid CT+RT, CRITICAL | Load-bearing. Phantom-typed wallet handles + property test. Acceptable. |
| DS3 Reconciliation Identity | Present, RT, HIGH | Folds v1 DS13 (correct per cartan M-3). Sign convention canonical. |
| DS4 No Discharge Without Witness | Present, hybrid, CRITICAL | **Conditional on DS19 (B-1.f / N-B-2).** Without DS19, idempotency is faith. |
| DS7 Failure Non-Reversal | Present, hybrid, CRITICAL | Anti-rollback. Acceptable. |
| DS9 Buy-In Compensation Closure | Present, RT, HIGH | Acceptable. |
| DS10 Cross-Currency Herstatt Visibility | Present, RT, HIGH | Acceptable. |
| DS11a Partial-Settlement Per-Step Conservation | Present, RT, HIGH | Split from v1 DS11 (correct). |
| DS11b Partial-Settlement Monotonicity | Present, RT, HIGH | Split from v1 DS11 (correct). D_max=2 pinned. |
| DS12 Variant Degeneration | Present, structural, MEDIUM | Acceptable. The "DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS17, DS18 hold without modification" is correctly stated for the parameter `t_d`. |
| DS17 Capability Scoping | Present, CT, HIGH | Phantom typing on writer capability. Acceptable. |
| DS18 DvP Ledger-Level Atomicity (DvP-L) | Present, structural, CRITICAL | Disambiguated from DvP-S/DvP-E (good). Executor primitive. Acceptable. |

**Numbered: 11 invariants** (the table claims 10; counting DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS12, DS17, DS18 gives 11). Minor — likely the table title is "DS1–DS10 (pruned)" but DS11a+DS11b+DS18 push it to 11. Re-state as "10–11 numbered invariants" or update the title.

**Genuinely missing from v2 (R1 B-1.f reasserted):**

- **DS19 — Witness-Identity Determinism.** R1 ask: every confirmation message has a content-addressed identity such that two structurally-equivalent confirmations from the same CSD have identical IDs. v2 says `dedup_key = hash_jcs(payload, source_lei, ts_obs)` (§4.5.1) but does not assert as a DS invariant. **Add as DS19**:

```python
@given(ev=any_valid_envelope())
def test_witness_identity_determinism(ev):
    ev_canonical = jcs_canonicalise(ev.payload)
    h1 = hash_jcs(ev_canonical, ev.source_lei, ev.ts_obs)
    # Restate ev with re-ordered keys, identical semantic content:
    ev_restated = re_order_object_keys(ev)
    ev_restated_canonical = jcs_canonicalise(ev_restated.payload)
    h2 = hash_jcs(ev_restated_canonical, ev.source_lei, ev.ts_obs)
    assert h1 == h2  # JCS canonicalisation must collapse equivocation attempts
```

This is the precondition for DS4 / DS6 idempotency. Without it, CSD equivocation (TA-DS-2 in §13.5) is unobservable.

**Conservation `Σ_w w(u) = 0` (v1 DS2 → §11.A "corollary of §7.5"):** the demotion to corollary is correct given the theorem. But §3.6 conservation table operates on deltas, not absolutes. See N-B-1.

**Replay determinism (v1 DS5 → §11.A "restated"):** the demotion to restated is correct given the §6.5.5 commutativity table. But the multiset-replay form needs to be the test under PO-8. Acceptable.

---

## §6.5 workflow specification — non-determinism boundary closure check

R1 B-2 named two boundaries:

1. **`tx_id` collision under partial-restatement.** §6.5.1 fixes via `business_event_id = "final:" || referenced_tx_id || ":" || msg_id_set` and `attempt_seq` carried across CaN. **Critical question:** what is `msg_id_set` if the CSD restates partial 1 with a *new* message ID? Then `msg_id_set` differs between original and restated, the `business_event_id` differs, and the new `tx_id` is distinct — which is correct under Reading (a) of G5 (treat restatement as new obligation). **Closed.** But the proposal should call this out explicitly in §6.5.1 — currently the only way to follow the logic is to chase the §6.5.5 commutativity table row "restated sese.025".

2. **sese.025-vs-CORRECTION race.** §6.5.5 row "correction_tx(refers_to=tx_id) vs sese.025(tx_id)" with explicit precedence "terminal absorbs" — **closed.** The disambiguation between "cancellation has not yet been externalised" (cancel-compensation) and "externalised" (queue-and-reconcile) in §6.5.7 is precisely what was needed.

**New boundary in v2 not in R1's list, worth noting:**

- **`workflow_id = "settlement-saga:" || obligation_id`** (§6.5.2). This implies workflow IDs are content-addressed on `obligation_id`. If `obligation_id = hash_jcs(tx_id, leg_label)` (per §3.2) and `tx_id` is content-addressed (per §6.5.1), then the workflow ID is content-addressed — Temporal start-workflow becomes idempotent across retries. Good. **But:** if Temporal's workflow-already-exists semantics is invoked on a duplicate start, what is the dedup behaviour? The proposal says nothing. This is the *Temporal layer's* non-deterministic boundary that the spec inherits but does not enumerate. Add to §6.5: "Temporal `start_workflow` with already-existing `workflow_id` returns the existing workflow handle; no new workflow is started." Otherwise the property "obligation creation is idempotent" depends on a Temporal-version-specific behaviour.

**Determinism boundary catalogue — not consolidated.** R1 asked for a single table. v2 scatters this across §0.4 (Λ_n, ts_obs, ts_known), §6.5 (tx_id, attempt_seq, run_id excluded), §13.5 (TA-DS-5 clock skew), §4.5 (envelope dedup). **Recommendation:** add §13.6 — a single table enumerating every non-deterministic boundary, classified `injectable / not-injectable / mitigated-via-trust-assumption`. This is bookkeeping, not redesign.

---

## Generators (§13.4.4) — implementable now? Failure-reason closed sum exhaustive?

`gen_failure_reason :: Gen FailureReason` — references §12.1.4 closed sum:
```
DeadlineMissed | NoCover | NoFunds | CounterpartyDefault of LEI |
CsdReject of CsdRejectCode | LegInconsistent of WhichLeg | Manual of OperatorId
```

Seven inhabitants, fully exhaustive at the type level. The two parametric ones (`CounterpartyDefault of LEI`, `CsdReject of CsdRejectCode`, `Manual of OperatorId`, `LegInconsistent of WhichLeg`) require sub-generators. **Open question:** is `CsdRejectCode` itself a closed sum? §12.1.4 references "PO-5 normalisation table" which is *deferred*. So `CsdReject` cannot today be exhaustively generated. The generator can compile and run today against the current `CsdRejectCode` enum, but until PO-5 closes, the framework has the witness-launderer gap I flagged in R1 B-1.d. **Acceptable as documented deferred** but cite explicitly: "until PO-5 closes, `gen_failure_reason CsdReject` draws from a partial enum; this is a known limitation pinned in §13.2 PO-5."

`gen_settlement_window :: Gen SettlementWindow` — closed sum {T+0, T+1, T+2, T+3, T+5}; exhaustive; implementable.

`gen_finality_lag :: AssetClass -> Gen Duration` — empirical distribution per `L_7^P.GeneratorDistributionPin`. **Implementable today against a stub distribution; production-grade requires the distribution to be populated from prod data.** Footnote it.

`gen_witness_arrival_perm :: List Witness -> Gen Permutation` — implementable; Hypothesis `permutations()` strategy.

`gen_corporate_action_in_window :: Gen CorpAction` — generates ex_date ∈ (T, t_d]. Implementable; the closed sum on `ca_type` (dividend, split, spinoff, ...) needs to be exhaustively listed somewhere. §4.5.4 names `{dividend, split, spinoff, ...}` — the ellipsis is the gap. **Add a closed sum `CorpActionKind` enumerating cash dividend, stock dividend, forward split, reverse split, rights issue, spinoff, merger-cash, merger-stock, merger-mixed, capital reduction, redenomination, symbol change.** This is a v2-fixable nit.

`gen_partial_chain_depth :: Gen Int` — bounded by D_max=2; implementable.

**Verdict on generators:** implementable now for 5 of 6, with one (`gen_finality_lag`) requiring the L_7^P distribution to be populated. The `gen_failure_reason` exhaustiveness depends on PO-5. **Net: acceptable with documented deferrals.** See M-2 below for the missing coverage gate.

---

## Differential oracle (R1 B-4) — naive sequential reference interpreter

**Not named in v2.** The closest item is PO-8 (TLA+ model at `|W|=3, |U|=2, depth=8` with 10 invariants encoded). TLA+ is a model-level oracle; it is NOT a runtime differential oracle for the implementation. The CDM functor F (§8.4) is now correctly classified as "lossy non-faithful" — useful conceptually, but v2 does not commit to F as a test oracle.

**This is the most material gap in v2.** Without a reference sequential interpreter:
- "The implementation passes its own property tests" can be satisfied by a circular oracle.
- Replay determinism (DS5 / §11.A) is asserted; replaying against a *different* implementation is the falsification.
- The TLA+ model check is bounded; the implementation handles unbounded inputs.

**Concrete recommendation:** §13 PO-11 (new):

> **PO-11 — Reference Sequential Interpreter.** Implement a naive sequential interpreter that processes witnesses one-at-a-time, single-threaded, no Temporal, no caching. Every property test in PO-1..PO-10 additionally checks bit-identical state against the reference. Differential test against the F-projection on `Lg_econ` for every state. Owner: testcommittee. ETA: 2 weeks.

This is **graded as M-3 elevated** in this review. If the Settlement Team accepts it as a deferred R3 closure, that is acceptable; if they say "PO-8 covers it", I push back — TLA+ is a model, not a reference implementation.

---

## Fault catalogue (R1 B-5) coverage — network split, Byzantine clock skew, bugification, forged envelope

| Fault | v2 status | v2 location |
|---|---|---|
| CSD partial responses | **CLOSED** | §6.4 + DS11a + DS11b |
| Duplicate finality | **CLOSED** | §4.5.1 dedup_key + DS6 (§11.A) |
| Finality-then-retraction (G5) | **CLOSED** | §6.5.5 commutativity row "restated sese.025" + Reading (a) |
| Reorder of finality vs trade | **CLOSED** | §6.5.5 commutativity table; DS5 / §11.A |
| Network split | **NOT NAMED** | — |
| Byzantine clock skew | **TRUST ASSUMPTION**, not fault test | §13.5 TA-DS-5 (clock skew bounded ≤ 5s) — assumes uncompromised, doesn't inject |
| CSD silently double-debits nostro | **MITIGATED**, not tested | §4.4 recon catches via BREAK class; no property test |
| Forged envelope (signature failure) | **CLOSED** | §4.5.1 Ed25519 verify at L_11 ingest |
| Bugification (legal-but-pathological CSD behaviour) | **NOT NAMED** | — |

**Network split (still missing).** §13.5 TA-DS-5 names clock skew but not network partition. The proposal should add:
- A §13.5 TA-DS-11: "Ledger-CSD network connectivity is intermittent but eventually-consistent. During partition, inbound `sese.025` retries on reconnection; idempotent re-ingestion preserves DS6."
- A property test: "under simulated partition between Ledger and CSD, eventual reconnection produces the same final state as no-partition."

**Bugification (still missing).** No §13 / §13.4 entry for legal-but-pathological CSD behaviour. The R1 ask was specific:
- A CSD that always sends `sese.025` 10 seconds before the matching `camt.054`.
- A CSD that always partials at exactly the legal minimum.
- A CSD that always restates 1 share at end-of-day.
- A CSD that delays each `sese.025` by exactly the watchdog interval `Λ_4`.

**Concrete recommendation:** §13.4.5 (new) — Bugification operators:

```python
class BugificationOperator(Strategy):
    """Inject legal-but-pathological CSD behaviour."""
    def with_minimum_partial(self): ...   # always partials at minimum
    def with_eod_restatement(self): ...   # always restates 1-unit at EOD
    def with_max_legal_delay(self): ...   # always delays to last legal moment
    def with_inverted_leg_order(self): ...  # always camt.054 before sese.025
```

These are not fault-injection of *illegal* behaviour (which §4.5.1 envelope verify catches); they are fault-injection of *legal-but-adversarial* behaviour. This is the FoundationDB lesson and v2 has not absorbed it.

**Verdict on faults:** 5 of 9 closed; 2 partially mitigated; **2 still missing** (network split, bugification). M-4.

---

## §3 + §3.X worked example sign error checks — independent verification

I independently verified the §3 BUY arithmetic:
- T close: `V_T = 995,000 + 100 × 50.00 = 1,000,000`. ✓
- T+1 close: `V_{T+1} = 995,000 + 100 × 52.00 = 1,000,200`. PnL = +200. ✓
- T+2 close: `V_{T+2} = 995,000 + 100 × 51.50 = 1,000,150`. PnL_{T+2} = -50. PnL_{cum} = +150. ✓

I independently verified the §3.X SELL arithmetic:
- T post-TX1: `V_T = 1,005,000 + (-100 × 50) + 5,000 = 1,005,000`. ✓
- T+1: `V_{T+1} = 1,005,000 + (-100 × 48) + 5,000 = 1,005,200`. PnL = +200. ✓
- T+2: `V_{T+2} = 1,005,000 + (-100 × 47.50) + 5,000 = 1,005,250`. PnL_{T+2} = +50. PnL_{cum} = +250. ✓

I independently verified the §3 + §3.X recon identity:
- BUY at T+2⁻: LHS = nostro_external = 1,000,000; RHS = 995,000 + 5,000 + 0 - 0 = 1,000,000. ✓
- SELL at T+2⁻: LHS = nostro_external = 1,000,000; RHS = 1,005,000 + (-5,000) + 0 - 0 = 1,000,000. ✓

**Same canonical sign convention, both directions.** This closes feynman B-2 and jane_street B-2. **Solid.**

**However** — see N-B-1 below. The §3.6 conservation table is *delta*-based; the Conservation Lifting Theorem is *absolute*. The arithmetic is right within each frame but the framing is mixed.

---

## DS1 still load-bearing? Type-vs-runtime decomposition still honest?

**DS1 is still the load-bearing invariant.** §11 names it CRITICAL. §12.1.1 phantom-wallet-class enforces it structurally — `emit_discharge` cannot be passed a `real_wallet wallet_handle` so settlement-status mutation that touches `own` is structurally unrepresentable. This is a clean win.

**Type-vs-runtime decomposition (§11 + §12.4):** Honest. The 11-row table at the end of §11 lists each invariant's mechanism. §12.4 names what is type-encoded and what is runtime-asserted with rationale ("First six are type-level because cost is one-time and benefit is on every read site"). The deferral to v12 RFP for smart-constructor-with-14-rejections, phantom accounting basis, and total-step-migration is honest.

**Single recommendation:** §11 should explicitly state: "DS1 is the single property whose violation invalidates the system. Every other DS exists to support DS1." This was an R1 minor I did not push hard on; v2 has it implicit but not explicit.

---

## NEW BLOCKING (v2-introduced)

### N-B-1. §3.6 conservation table is in DELTA form; §7.5 theorem is in ABSOLUTE form

**Issue.** §7.5 Conservation Lifting Theorem states $\sum_{w \in \mathcal{W}} w_t(u) = 0$ for every unit $u$ and every wall-clock $t$ — **absolute** balances over the constant universe $\mathcal{W}$.

§3.6 conservation table for USD shows:
```
T⁻ pre-trade | 0 (delta)  | 0      | 0      | 0
T⁺ post-trade| -5,000     | +5,000 | 0      | 0
T+2⁺ finality| -5,000     | 0      | +5,000 | 0
```
labelled "(Reading: `Δ` from pre-trade. Σ_internal = 0 at every state)".

The pre-trade absolute balances are `w_us.own(USD) = 1,000,000`, `w_PS[us,GS,USD].own = 0`, `w_JPMC_nostro_mirror[GS].own = 0`. Absolute sum = +1,000,000 ≠ 0. The constant universe `\mathcal{W}` does NOT include the wallet whose `own(USD)` is -1,000,000 (the source of the pre-trade float — a counterparty, prior depositor, or the system's "void / external" wallet).

**Why this matters.** §7.5.1 H4 states "wallet universe constancy: `\mathcal{W}` is fixed across t". §3.6 satisfies the theorem only by sleight of hand — the universe in §3.6 is *not* `\mathcal{W}`; it is a *partial* universe that evades the theorem's hypothesis.

**Either fix:**

1. **Restate §3.6 as absolute conservation** by explicitly including the prior counterparty / depositor in the constant universe. Add `w_external_USD_source` (or whatever the conventional name is) with pre-trade balance -1,000,000. Then the absolute sum is zero pre-trade and remains zero throughout.

2. **OR restate the theorem as delta conservation:** $\sum_{w \in \mathcal{W}} \Delta w_t(u) = 0$ for every transaction. This is the local version (every move pair sums to zero); the absolute statement is only true if the universe is closed.

The sleight-of-hand in v2 is the worst kind of correctness issue: the worked example looks clean, the theorem looks clean, both are right within their own frame, and the spec's correctness depends on the reader not noticing the framing mismatch. **This is a Goodhart trap exemplar** — the spec asserts conservation; the test asserts conservation; both agree because both are framing differently. A property test that mechanically reads the §3.6 table will pass; a property test that mechanically applies the §7.5 theorem will fail on the same data. **Block on this.**

### N-B-2. DS19 (Witness-Identity Determinism) still missing as a numbered DS invariant

Restated from R1 B-1.f. v2 mentions `dedup_key = hash_jcs(payload, source_lei, ts_obs)` in §4.5.1 and TA-DS-1/2 in §13.5. None of these is a numbered DS invariant.

**Why this matters.** DS4 (No Discharge Without Witness) requires witness-identity determinism as a precondition. §6.5.5 commutativity table assumes `sese.025(tx_id)` is well-identified for the dedup. If two structurally-equivalent inbound `sese.025` envelopes from the same CSD produce *different* `dedup_key`s (e.g., due to JSON key reordering, whitespace, schema-version drift), DS4 idempotency breaks silently.

**Add as DS19:**

> **DS19 — Witness-Identity Determinism.** $\forall \varepsilon_1, \varepsilon_2 \in \text{EnvelopeRegistry}$ with $\varepsilon_1, \varepsilon_2$ structurally equivalent (same payload modulo JCS canonicalisation, same `source_lei`, same `ts_obs`):
> $$\text{dedup\_key}(\varepsilon_1) = \text{dedup\_key}(\varepsilon_2)$$
> Equivalently: JCS canonicalisation collapses all permissible serialisation variants of a single semantic message to a single hash.
>
> **Parent.** RFC 8785 (JCS); §4.5.1; data-spec Λ_10. **Type.** runtime (property test on hash function over a generator of structurally-equivalent envelopes). **Severity.** CRITICAL — precondition for DS4 idempotency.

**Block on this.**

---

## Remaining MAJOR (M-N, v2)

### M-1. Non-determinism boundary catalogue is scattered, not consolidated

R1 B-2 asked for a single §11.bis or §13.bis table enumerating all non-deterministic boundaries with `injectable / not-injectable / mitigated-via-trust-assumption` classification. v2 scatters this across §0.4, §6.5, §13.5. **Add §13.6 — single table.** Bookkeeping, not redesign. ~2 hours of work.

### M-2. Generator coverage gate missing

§13.4.4 names the generator type signatures but does not enforce that every inhabitant of every closed sum is exercised in every test class. A `gen_failure_reason` that always returns `DeadlineMissed` will type-check and pass and find zero `CsdReject` bugs.

**Concrete addition to PO-8:** "Coverage gate: every test-class run produces (and the framework checks) a histogram showing every inhabitant of every closed sum (`LifecycleState`, `failure_reason`, `CsdRejectCode`, `SettlementWindow`, `CorpActionKind`) is exercised at least once. CI fails if any inhabitant has zero hits across the test class."

This is the property-coverage-instead-of-line-coverage criterion. Without it, B-3 is closed in letter, not spirit.

### M-3. Differential testing oracle (R1 B-4) — elevated. Reference sequential interpreter not named.

See "Differential oracle" section above. **PO-11 needed.**

### M-4. Fault catalogue: network split + bugification still missing

See "Fault catalogue" section above. **§13.5 TA-DS-11 (network partition) + §13.4.5 bugification operators.**

### M-5. Temporal `start_workflow` idempotency on duplicate `workflow_id` not specified

§6.5.2 names per-obligation workflow IDs. The Temporal-version-specific behaviour on duplicate-start is not pinned. Add to §6.5.2: "Temporal `start_workflow` with already-existing `workflow_id` returns the existing workflow handle; framework relies on this for cross-replay idempotency."

### M-6. `CorpActionKind` ellipsis in §4.5.4

§4.5.4 names `{dividend, split, spinoff, ...}`. The ellipsis is the gap. Add a closed sum enumerating cash dividend, stock dividend, forward split, reverse split, rights issue, spinoff, merger-cash/stock/mixed, capital reduction, redenomination, symbol change. v2-fixable nit.

### M-7. R1 B-1.a partial closure — same-(w,u)-multi-trade interleaving

§6.5.5 last row "Cross-trade signals (different `tx_id`) — independent" is the easy case. The hard case is two trades touching the same `(real_wallet, unit)` but different `tx_id`s, with finality witnesses interleaved. This affects DS3 recon identity (the two `cpty_virtual` wallets share state through the `+ Σ_cpty` sum). Add a property test under PO-8.

---

## Minor (m-N, v2)

**m-1.** §11 invariant count is "10" in the title but counts to 11 (DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS12, DS17, DS18). Re-title or re-count.

**m-2.** §13.2 PO-9 says "**Closed in §6.4 + DS11b**: D_max = 2"; §11 DS11b also says "$D_{\max} = 2$". §0.4 says "`κ_buyin` (recursion bound, §0.4) for partial → buy-in → partial cascades is `D_max = 2`". One symbol is `κ_buyin`, another is `D_max`; §0.4 conflates them. They are not the same: `κ_buyin` is the CSDR clock multiplier (4bd / 7bd / 15bd per asset class); `D_max` is the partial-fill recursion depth bound. **Disambiguate** — they are both pinned but mean different things.

**m-3.** §3.7 PnL trace is single-path; the property test for path-independence (R1 B-1.b) is implied via DS1+DS7 but not explicitly listed. The §3.X SELL example helps. Add to PO-1: "PnL invariance verified across both directions and across discharge boundary."

**m-4.** §10.7.4 index strategy lists `(business_event_id, attempt_seq)` as primary key. Good. But the partition key is `(year_month(intended_settlement_date), hash_prefix_8(business_event_id))` — `intended_settlement_date` is a function of trade-time inputs; partitioning is stable. Acceptable. **However:** `intended_settlement_date` itself is computed by `SettleDate.of_trade_date(TradeDate, SettleConvention, CalendarPin)`. If `CalendarPin` is updated after partition is materialised, no row movement. Confirm partitioning is immutable post-write.

**m-5.** §13.4.4 generator `gen_corporate_action_in_window` shrinks to "no-CA case". For property tests that *require* a CA in window (e.g., manufactured-payment property), shrinking to no-CA produces a vacuous test. Add a property-aware shrinker that respects test prerequisites.

**m-6.** §15.5 names 4 open items as R2 follow-on. Three are owed-but-tractable (PO-5, PO-8 TLC run, PO-6); one (PO-4 / G3 bitemporal predicate under CA) is open with mitigation pinned. Acceptable for v2 acceptance, but add explicit "these are R3-blocking for production rollout, not v2-blocking for spec convergence" — currently §15.5 says they don't block v2 acceptance, which is correct, but a downstream consumer reading §15.5 in isolation might miss the bound.

**m-7.** §13.4.4 generator type signatures use Haskell-flavoured pseudocode. Internal consistency with §12.1's OCaml? Decide one and stick. Mixed surface forms confuse property-test authors — particularly a concern when LLM-assisted implementation is *forbidden* for generators (G-DS-3) and hand-authoring is required.

---

## What works (genuine strengths in v2 — credit where due)

1. **§13.4 Goodhart trap closure is exemplary.** G-DS-1's empirical-distribution-pinned-in-`L_7^P` mechanism is exactly right. G-DS-2's per-`(unit_class, wallet_class)` decomposition catches sign-swap bugs the global sum misses. G-DS-3's hand-authored-not-LLM-derived rule with code-review enforcement on `learn_from_traces(...)` patterns is the correct discipline. **This is the single most thorough section in v2 from the correctness perspective.**

2. **§6.5.5 commutativity table.** Eight rows; each `(A, B)` pair has a determined precedence; non-commuting cases are deterministically resolved (terminal absorbs; contradictions quarantine). This is the bookkeeping that distinguishes a spec from prose.

3. **§6.5.7 saga compensation tower.** "If externalised: queue-and-reconcile" is the right design; the alternative (force-rollback the externalisation) is what dooms FoundationDB-class systems. Pinned in `L_7^P.SagaCompensationPolicy`. Bitemporally versioned. Clean.

4. **§7.5 Conservation Lifting Theorem.** Stated in theorem form with explicit H1..H5 hypotheses and inductive proof outline. Modulo N-B-1 (the absolute-vs-delta framing confusion with §3.6), this is the right level of formality.

5. **§4.5.1 Ed25519 + JCS canonicalisation envelope.** The signature scheme is named (RFC 8032), canonicalisation is named (RFC 8785), and equivocation attacks are explicitly excluded. The dedup_key formula is content-addressed. Good.

6. **§4.5.3 absence-of-finality protocol.** "Silence past intended_settlement_date does NOT auto-FAIL the obligation. It triggers a wf-confirm-break workflow." This is the correctness commitment — never fail-by-inference. Restated cleanly.

7. **§12.1.1 phantom wallet class.** Three types, three constructors, `emit_discharge` cannot take a `real_wallet wallet_handle`. DS1 is structurally enforced. The migration plan (§12.2) is honest about cost (6 weeks, 1.5 engineers) and stages.

8. **§3 + §3.X paired BUY/SELL examples.** Both fully numerically derived; both verified against the same canonical sign convention; recon identity holds in both directions. The Settlement Team has done the arithmetic the reviewer would have done.

9. **§15.2 R1 closure record.** A 13-row table mapping every R1 blocker to its v2 closure section with one-line summary. **This is what every Phase 3 Round 2 spec should contain.** It saves the R2 reviewer ~30 minutes per blocker.

10. **§13.5 trust-assumption registry.** TA-DS-1..10 with named owners, detection signals, and quarterly review cadence. The shape is right. **Add TA-DS-11 (network partition) per M-4** and the registry is complete.

---

## Pareto judgment

**Pareto NOT reached.** Two new blockers (N-B-1, N-B-2) and four substantive majors (M-2 generator coverage gate, M-3 differential oracle, M-4 fault-catalogue completion, M-7 R1 B-1.a residual) prevent zero-blocking-zero-major status.

**However:** the gap between v2 and Pareto is small. N-B-1 is a 1-paragraph clarification (delta vs absolute framing). N-B-2 is a single DS19 paragraph. M-2 is a coverage-gate paragraph. M-3 is one new PO-11. M-4 is one TA-DS-11 + one §13.4.5 paragraph. M-7 is one property test. **Total: ~3 person-days of work to reach Pareto.**

**Recommended R3:**
- One revision pass closing N-B-1, N-B-2, M-1, M-3 (the four high-leverage items).
- M-2, M-4, M-5, M-6, M-7 absorbed in the same pass.
- Minor m-1..m-7 absorbed in a copy-edit pass.
- R3 panel: 5-6 reviewers (correctness, jane_street, testcommittee, formalis, halmos). Should converge in a single round.

**Verdict.** ACCEPT_WITH_CHANGES. The Settlement Team has internalised the R1 review at depth; the remaining gaps are correctness-discipline, not architectural. The v2 architecture is sound. The v2 testing posture is 90% sound.

**Single most important item to close before R3:** N-B-1 (the delta-vs-absolute framing in §3.6 / §7.5). This is a Goodhart trap exemplar and the kind of correctness issue that, left in place, will produce a downstream bug the spec authors will never see because both the spec and the test agree by construction.

**Single most important property in the catalogue (unchanged from R1):** DS1 (Economic-Exposure-at-T). Every other DS exists to support it. v2 makes DS1 type-enforced via phantom wallet handles — the strongest possible mitigation. Credit.

---

*Reviewer: Correctness Architect. Adversarial focus per R2 brief. Cross-referenced ledger_data_v1.0.tex (L_15, Λ_13, Φ_15, witness inventory W_1–W_5, GT_1–GT_5) and proposal_v1 + R1 consolidated findings.*
