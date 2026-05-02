# Round 2 Adversarial Review — Temporal-Engineering Lens

**Reviewer:** temporal-engineer
**Subject:** `phase3/round2/proposal_v2.md` (Settlement Team v2 incorporating R1 findings)
**Date:** 2026-04-30
**Verdict:** **ACCEPT_WITH_CHANGES.** Pareto NOT yet reached for the workflow layer; 2 unresolved issues survive into v2 (one new) plus 4 partial closures that need one more pass. None rise to BLOCKING. The §6.5 work is genuine; the workflow specification has moved from "named and leaned on" in v1 to "shape pinned" in v2. The remaining gaps are scope creep that v2 swept under the existing prose rather than confronting.

The single most important thing v2 got right: §6.5.1 commits to `tx_id = hash_jcs(business_event_id, attempt_seq)` everywhere (with `business_event_id` namespaced, with `attempt_seq` carried across ContinueAsNew, with `run_id` explicitly excluded). That was the load-bearing fix and it landed. §6.5.3's per-leg discharge with `tx_status` emergence is the correct model. §6.5.5 commutativity table is the right shape and the explicit non-commuting precedences ("terminal absorbs"; "contradictions quarantine") are deterministic step-function precedences, not race-condition fudge.

What v2 got wrong or did not address: M-1 enforcement locus (executor vs workflow) is asserted by adverb ("framework rejects") not by section pin; M-2 MorningRecon overlap policy and fan-out shape are silently absent; M-3 CsdrPenaltyAccrualWorkflow shape is silently absent (the `CSDR_PENALTY` Obligation row is specified, but the *workflow that emits the daily accrual transaction* is not); M-4 RestatementWatchWorkflow is now resolved by §6.5.5 Reading-(a) but the *trigger* is unspecified; M-7 visibility / search attributes is **completely silent in v2**; M-9 child workflows are mentioned in passing but `parent_close_policy=ABANDON` and the catalogue of named compensation children are not pinned. There is also one new issue: §6.5.4's watchdog `sleep_loop` in workflow code is non-deterministic as written.

This is ACCEPT_WITH_CHANGES rather than REJECT_REVISE because the BLOCKING items did close; the workflow is implementable. But the remaining gaps mean operations cannot run the system without resolving them, and Pareto cannot be declared without a v2-supplement or a §6.5 amendment in R3.

---

## R1 Closure Table

Note: the Settlement Team renumbered R1 temporal blockers `B-1..B-5` as `B-8..B-12` in their consolidated B-1..B-13 list. I track them under the original temporal numbering for fidelity to my R1 review.

### BLOCKING (originally B-1..B-5)

| R1 Blocker | v2 Section | Status | Notes |
|---|---|---|---|
| **B-1** `tx_id` formula `hash_jcs(business_event_id, attempt_seq)`; `attempt_seq` carried across ContinueAsNew | §6.5.1, §6.5.6 | **CLOSED** | Formula present verbatim. `business_event_id` is content-addressed on stable upstream namespace (`exec:`, `final:`, `buyin:`, `correction:`). `attempt_seq` is a workflow-state field carried in `WorkflowInput` payload across CaN. `run_id` explicitly excluded (§6.5.6: "`run_id` is **not** in the payload"). `L_13.tx_id` as primary key handles dedup. The §6.4 partial-fill examples have been updated to the new formula. |
| **B-2** DvP atomicity at discharge: independent arrival of sese.025/camt.054; per-leg discharge with all-legs-settled flag spelled out | §6.5.3 | **CLOSED** | Per-leg discharge unambiguously committed: "Each `L_15.Obligation` leg is **independently** transitioned by its own witness arrival. There are TWO `L_13` transactions in the typical DvP discharge path." Transaction-level all-legs-settled emerges from the `tx_status(tx)` projection function (§5.3, not stored). DvP-L / DvP-S / DvP-E disambiguation (closes theme H) is a clean conceptual win — DvP atomicity is now three distinct claims at three distinct loci, not one ambiguous one. Leg-inconsistent failure is observable in `tx_status(tx) == Mixed` and routed to `wf-confirm-break` per per-CSD κ table. |
| **B-3** DS5 replay determinism: signal-handler commutativity table | §6.5.5 | **CLOSED with caveats** | Commutativity matrix is present, covering eight signal-pair scenarios. Three non-commuting cases (cancel-vs-discharge; sese.024-vs-sese.025; correction-vs-discharge) are correctly identified as deterministic precedences ("terminal absorbs"; "contradictions quarantine"). The cross-trade row covers per-workflow isolation. **Caveat 1:** the `attempt_seq`-ordered commutativity claim for partial fills is correct only if `attempt_seq` is producer-monotonic from the CSD source — not derived from arrival order. The spec implies this but does not pin it; cross-reference with §6.5.1 where `attempt_seq` is described as "monotonic uint32 within (business_event_id)" suggests workflow-side, not producer-side. **This needs one sentence of pinning** (see new issue N-1 below). **Caveat 2:** the table is by signal-pair only; three-or-more-signal interleavings are property-tested in PO-8 but no symbolic argument that pairwise commutativity composes to multi-way commutativity is given. For closed-sum FSMs this composition is generally fine if precedences are total-orderable, but the proof obligation is not stated. Acceptable for v2; flag for R3 supplement. |
| **B-4** T+2 trigger: deadline timer with watchdog fallback | §6.5.4 | **CLOSED with one new issue** | Phase 1 watchdog design is restored. Primary timer + fallback poll loop + `await first_of([primary_timer, witness_signal_arrival])` is correct shape. **Λ_n cadence is pinned** (§4.5.3: `Λ_0=0`, `Λ_1=30min`, `Λ_2=2h`, `Λ_3=EOD`, `Λ_4=+1bd`). The watchdog is named idempotent via `(obligation_id, watchdog_seq)` dedup_key. Closure is real but the *implementation form* of the watchdog as written (`workflow.sleep_loop(Λ_n) { on each tick: ... }`) is determinism-suspect — see new issue N-2 below. |
| **B-5** Workflow ID granularity: per-obligation; ContinueAsNew payload schema | §6.5.2, §6.5.6 | **CLOSED** | `workflow_id = "settlement-saga:" || obligation_id`. One workflow per L_15 obligation row. DvP trade with two legs = two workflow instances coordinating via signals. `WorkflowInput` schema is fully specified (§6.5.6, eight fields, all deterministic-across-CaN). PS/PSS wallet keying is correctly identified as a separate axis (per-counterparty per-(currency-or-ISIN) per §2.2; concurrent sagas on the same PS/PSS wallet are serialised by the executor). This is the right pin. |

**Summary:** all five R1 BLOCKERS close. Two carry caveats (B-3 producer-monotonic claim; B-4 implementation form) which I expand below as new issues N-1 and N-2.

### MAJOR (originally M-1..M-10)

| R1 Major | v2 Section | Status | Notes |
|---|---|---|---|
| **M-1** CORRECTION enforcement locus (executor capability guard, not workflow) | §10.9 | **PARTIAL** | §10.9 states "Framework rejects any CORRECTION where `requester_lei == approver_lei`, OR ..." (four bullets of rejection conditions). But "framework rejects" is adverbial — it does not pin whether the rejection is a C11 capability check at the executor (compile-time / structural) or a workflow precondition (runtime / `CorrectionWorkflow` activity). DS17 (§11) says writer-capability is compile-time (phantom typing); §10.6 CO-6 lists "four-eyes CORRECTION" as a SOX control. None of these explicitly says: "the rejection is a pre-emission C11 capability check inside the executor; the `CorrectionWorkflow` workflow is a UX wrapper that gathers signatures and the rejection happens in the executor when it cannot type-check the capability witness." This is the sentence I asked for in R1 M-1. **Action for R3 supplement:** one sentence in §10.9.3 stating "Rejection is structurally enforced via the executor's CORRECTION-type tx admission guard (a compile-time C11 capability check, per DS17). The `CorrectionWorkflow` workflow is a UX wrapper that gathers the two signatures and submits the tx; the executor rejects on capability-witness mismatch. The workflow does not enforce four-eyes; it could be bypassed by a malicious workflow author and the executor would still reject." Without this sentence, CO-6's SOX test plan ("system enforcement") is ambiguous. |
| **M-2** MorningReconWorkflow overlap policy and fan-out shape | §4.4, §6.5.8 | **NOT CLOSED** | §6.5.8 catalogue row says: "Trigger: Temporal cron 09:00 local. Body: (1) for each `(real_wallet, ccy_or_ISIN)`, scan §4.1 identity; (2) classify per §4.8 ...; (4) for BREAKs, spawn `wf-position-break` per kind." This pins the trigger and the body. **What is missing:** (a) overlap policy — Skip / BufferOne / BufferAll / AllowAll / Terminate? My R1 recommendation was Skip with out-of-band alert; v2 does not state. (b) Fan-out shape — single activity scanning all wallets vs fan-out workflow vs scheduled per-wallet workflow? The "for each `(real_wallet, ccy_or_ISIN)`" is loop-syntax in spec prose, not a Temporal pattern commitment. (c) Per-region task queue topology — "in each reporting timezone" is mentioned in v1 §4.4 (no longer in v2 §4.4 prose); is there one Schedule per timezone? Are these on different task queues? **Action for R3 supplement:** §6.5.8 row needs three additional fields: `overlap_policy`, `fan_out_pattern` (with activity timeout / heartbeat), `task_queue`. For tier-1 dealers with thousands of real wallets, fan-out shape is a production-readiness question, not a scope-creep nit. |
| **M-3** CsdrPenaltyAccrualWorkflow shape (per-obligation vs daily fan-out, idempotency key, accrual-vs-settlement separation) | §6.3 | **NOT CLOSED** | §6.3 specifies the `Obligation` row of kind `CSDR_PENALTY` with all required fields (qty_failed, price_at_intended, rate_bps, accrual_start). It says "Daily accrual emits a small cash transaction atomically with `o_pen.csdr_penalty_accrued` update. Penalty amount is a pure function of (qty_failed, ...)." That's the *what*. **What is missing:** (a) The workflow that emits the daily accrual is not named. §6.5.8 catalogue lists three workflows (`SettlementSaga`, `BuyInWorkflow`, `MorningReconWorkflow`); CsdrPenaltyAccrualWorkflow is absent. (b) Cron vs long-lived per-fail vs daily fan-out is unstated. R1 M-3 recommendation: daily-cron `CsdrPenaltyAccrualWorkflow` with overlap-policy `Skip`, fan-out across all `FAILED` obligations active at EOD. (c) Idempotency key for the daily accrual transaction not pinned. R1 M-3 recommendation: `tx_id = hash_jcs(business_event_id="csdr_accrue:" || obligation_id || ":" || accrual_date, attempt_seq)`. (d) Accrual-vs-settlement separation: daily accrual goes against an *accrual* virtual wallet; monthly `semt.044` settles against the accrual sum. v2 says "Daily accrual emits a small cash transaction atomically" but does not say between which wallets; "atomic with `o_pen.csdr_penalty_accrued` update" suggests a state-only update plus a virtual-wallet move, but the wallet keying is not specified. **Action for R3 supplement:** add §6.5.9 "CSDR Penalty Accrual Workflow" with the same shape as §6.5.8 catalogue rows. Without this, the spec's "Penalty amount is a pure function" claim has no driving workflow. |
| **M-4** RestatementWatchWorkflow for G5 | §6.5.5 (commutativity row), §13.1 G5 | **PARTIAL** | §6.5.5 commutativity table row 4 covers `sese.025(tx_id)` vs `restated sese.025(tx_id, q')` under Reading (a): "treat as new obligation". §13.1 G5: "**Closed in v2 §6.5.5** under Reading (a): treat restatement as new obligation (clean separation; new `attempt_seq`)." Closure of the *semantics* is good. **What is missing:** the *trigger* is unspecified. Who detects that an inbound `sese.025` is a restatement of a previously-discharged obligation? Reading (a) says we open a new obligation row — but the inbound side that creates it is unspecified. Three candidates: (i) L_11 ingestion side detects via `(tx_id, sequence_number)` arrival pattern; (ii) a `RestatementWatchWorkflow` polls completed obligations for restatement notifications; (iii) a new field on `L_15.Obligation` carries `corrections_chain` consumed by ingestion. v2 picks none. The original SettlementSaga has terminated by the time the restatement arrives, so it cannot route the signal — Temporal does not deliver signals to terminated workflows. **Action for R3 supplement:** one sentence in §6.5 catalogue or §4.5 ingestion: "Restatement detection occurs at L_11 ingest time. When an envelope's `dedup_key` matches a previously-processed envelope but the payload differs, the ingestion handler creates a new `L_15.Obligation` with `parent_obligation_id = original_obligation_id` and `kind = RESTATEMENT`, and starts a fresh SettlementSaga on the new obligation. The original (terminated) saga is not signaled." Without this sentence, Reading (a) is a semantic claim without a mechanism. |
| **M-5** Signal-dedup TTL for long-lived FAILED → BoughtIn cascades | §6.5.6 | **PARTIAL** | §6.5.6 specifies `envelope_history_dedup` is "bounded (n=4096, TTL=30 days) per PO-10. Older entries are GC'd; a duplicate envelope arriving past TTL routes to `wf-confirm-break` for human inspection." The structural fix (route past-TTL duplicates to a break-handler instead of silently re-processing) is correct and resolves the late-arrival hazard for the original SettlementSaga. **What is missing:** for FAILED → BoughtIn cascades that span 45–60 days, the original SettlementSaga's dedup window may TTL out before the buy-in workflow's chained replacement-trade discharge propagates back to update the original `o.state` to `BoughtIn`. v2's §6.5.8 says BuyInWorkflow has "parent_obligation_id = original `o`" and "on completion, transition original `o → BoughtIn`" — but if the original SettlementSaga has terminated (per the ContinueAsNew schema, only one workflow per obligation_id is active at a time), the BoughtIn transition is from the BuyInWorkflow itself signaling some other handler. The capability writer for `o.state` per DS17 is "the SettlementSaga workflow" — but the saga has terminated. **Action for R3 supplement:** one sentence resolving whether (a) SettlementSaga ContinueAsNew's into a long-lived "wait for buy-in" mode and stays alive for 45-60 days with TTL extended, or (b) SettlementSaga terminates on entry to FAILED state, BuyInWorkflow becomes the writer for the original `o.state → BoughtIn` transition (in which case DS17's "unique writer = SettlementSaga" is false). I lean (a): SettlementSaga ContinueAsNew's at FAILED with new TTL = `T_max + max_buyin_extension + 1bd`. v2 should pick. |
| **M-6** GetVersion gate inventory for CSDR rate-matrix versioning | (none) | **NOT ADDRESSED** | §1346 mentions "Versioning is bitemporal." TA-DS-10 (§13.5) specifies "CSDR rate schedule pinned via L_7^P versioning." But the **workflow-side** versioning question — does the in-flight SettlementSaga re-read the CSDR rate table on each accrual day, or does it pin the rate at obligation creation? — is not addressed. This was R1 M-6 verbatim. The two answers imply different `GetVersion` strategies. v2's §13.5 TA-DS-10 ("rate schedule pinned via L_7^P versioning") suggests refdata-pin, but the workflow read pattern (`as_of(t_known_at_obligation_creation)` vs `as_of(t_known_at_accrual_day)`) is not committed. **Action for R3 supplement:** one paragraph in §6.5 (or §13.1 G3 expansion): pin rate-table read pattern; list `GetVersion` gates the SettlementSaga uses; specify cutover semantics for retroactive ESMA recalibration. R1 recommendation stands: refdata-pin under `as_of(t_obligation_creation)`. |
| **M-7** Visibility / search attributes | (none) | **NOT ADDRESSED** | grep for "search attribute", "visibility", "search_attribute", "SearchAttribute" in proposal_v2.md returns **only** §13.5 ("ISO 20022 schema pinned via versioning") and §1356 ("Versioning is bitemporal") — neither related. **The §11.5 visibility section I requested in R1 M-7 was not added.** This is the most surprising gap in v2. Without search attributes (`obligation_id`, `business_event_id`, `counterparty_lei`, `csd`, `currency`, `settlement_date`, `buyin_deadline`, `state`, `fail_reason`, `notional_usd`), §4.5.3 absence-of-finality protocol cannot be operated — the watchdog spawns `wf-confirm-break`, but operations cannot find all open `wf-confirm-break` workflows for a given counterparty / CSD / currency without scanning the application database, which §4.3 forbids. Search attributes are the operational interface to durable execution; without them, DS4 / DS5 / DS9 / DS17 are correctness theatre. **Action for R3 supplement:** add §6.5.9 "Visibility" with a per-workflow-type table of required search attributes; specify Temporal Cloud advanced visibility vs. self-hosted Elasticsearch dependency; commit at least the ten search attributes I listed in R1 M-7. **This is the strongest reason this review is ACCEPT_WITH_CHANGES rather than ACCEPT.** |
| **M-8** Watchdog non-determinism (activity-result vs signal) | §6.5.4 | **PARTIAL with new issue** | §6.5.4 implementation pseudocode has a `workflow.sleep_loop(Λ_n)` block that runs "on each tick: if obligation.state ∈ {Pending, Instructed} AND now() > intended_settlement_date + Λ_n_threshold: emit silence_attestation envelope; spawn wf-confirm-break". Two subtle problems: (a) `now()` in workflow code is non-deterministic unless it is `workflow.Now()` (deterministic, returns workflow-time, replay-safe); the pseudocode is ambiguous. (b) `obligation.state` read inside the loop must be the workflow's local state copy (replay-safe), not a fresh read from L_15 — if it is the latter, replay produces a different state read and a different decision path. (c) `sleep_loop` is not a Temporal primitive; the user means a chained `workflow.sleep` series. The semantics are right, the form is ambiguous. **Action for R3 supplement:** rewrite §6.5.4 pseudocode as: `for n in 1..4: workflow.sleep(Λ_n - Λ_(n-1)); if local_state ∈ {Pending, Instructed}: ExecuteActivity(emit_silence_attestation, obligation_id, watchdog_seq=n); StartChildWorkflow(wf-confirm-break, obligation_id, parent_close_policy=ABANDON)`. Activities and child workflows are deterministic ingest points; sleep durations are Temporal timers; local state is workflow memory. See new issue N-2 below. |
| **M-9** Compensation as child workflow (not activity, not saga branch); `parent_close_policy=ABANDON`; named compensation children | §6.5.7, §6.5.8 | **PARTIAL** | §6.5.7 specifies the saga compensation policy table entry (SETTLEMENT class: cancel-compensation if not externalised; queue-and-reconcile if externalised). §6.5.8 catalogue lists `BuyInWorkflow` as a child workflow with parent_obligation_id linkage. **What is missing:** (a) `parent_close_policy=ABANDON` is not stated for BuyInWorkflow (or for any compensation child). Without ABANDON, parent termination cancels the compensation child — exactly the wrong semantics for a 45-day buy-in. (b) The compensation child catalogue is incomplete: BuyInWorkflow is named; CancelWorkflow is referenced ("`Cancelled` and the late discharge ...") but not specified as a workflow; CsdRestatementWorkflow is implied by Reading (a) but not catalogued (M-4 above); CounterpartyDefaultWorkflow is referenced in DS15 but not catalogued. (c) Each compensation child should have its own task queue (decoupled from the main settlement task queue for scaling), retry policy, deadline budget — none are specified. **Action for R3 supplement:** §6.5.8 catalogue extended to the full compensation-child catalogue; each row pinned with `parent_close_policy`, `task_queue`, `retry_policy`, `deadline_budget`. |
| **M-10** ContinueAsNew payload schema for SettlementSaga | §6.5.6 | **CLOSED** | Eight-field `WorkflowInput` schema is fully specified. `obligation_id`, `business_event_id`, `attempt_seq`, `state_snapshot`, `envelope_history_dedup`, `watchdog_seq`, `parent_obligation_id`, `cancel_compensation_token`. `run_id` explicitly excluded. The schema is sufficient for deterministic replay across CaN. The only refinement (which I would push if R3 happens): `cdm_v` and `canonicalisation_v` are not in the schema; under CDM 6.x → 7.x migration, replay of a CaN'd saga across the version boundary needs a pinned canonicalisation version. Acceptable to defer to v12 schema migration; flag for visibility. |

**Summary:** of the 10 R1 MAJORs, 2 close cleanly (M-9 partial → M-10 closed), 5 close partially (M-1, M-3, M-4, M-5, M-8), 3 are not addressed (M-2, M-6, M-7). M-7 (search attributes) is the most operationally severe.

---

## New Issues in v2

### N-1. (B-3 caveat 1) Producer-monotonicity of `attempt_seq` is implied but not pinned.

§6.5.1 defines `attempt_seq` as "monotonic uint32 within (business_event_id); starts at 0, increments on workflow-level retry." This is *workflow-side* monotonicity. The §6.5.5 commutativity table for partial-fill ordering (`sese.025(partial q1)` then `sese.025(partial q2)` commutes "via `attempt_seq` ordering on leg balance state") implicitly assumes the `attempt_seq` was set by the **producer** (the CSD), so that out-of-order arrivals at the workflow are sortable.

But the §6.5.1 definition pins `attempt_seq` as workflow-side. If the workflow assigns `attempt_seq` on receive-order, then "commutes via `attempt_seq` ordering" is circular: the ordering depends on arrival order.

**Resolution:** add one sentence in §6.5.1: "For partial-fill signals, `attempt_seq` is the producer-supplied sequence number from the CSD source (e.g., `sese.025.PartialSettlementInd.SettlementSequence`), not assigned by the workflow. The workflow sorts inbound partials by producer-monotonic `attempt_seq` before applying. Workflow-side `attempt_seq` increments only on workflow-initiated retries (e.g., re-emission of `sese.023` after timeout)."

This unifies the two senses of `attempt_seq` and makes the partial-fill commutativity claim formal.

### N-2. (B-4 / M-8) §6.5.4 watchdog `sleep_loop` is determinism-suspect as written.

§6.5.4 pseudocode:
```
let watchdog = workflow.sleep_loop(Λ_n) {
  on each tick:
    if obligation.state ∈ {Pending, Instructed} AND
       now() > intended_settlement_date + Λ_n_threshold:
      emit silence_attestation envelope (§4.5.3)
      spawn wf-confirm-break(obligation_id)
}
```

Three issues: (a) `sleep_loop` is not a Temporal primitive; the user intends a chained `workflow.sleep` series. The semantics are clear but the form invites mis-implementation. (b) `now()` is ambiguous: must be `workflow.Now()` (deterministic, replay-safe) not `time.Now()` (non-deterministic). (c) `obligation.state` read inside the loop must be from workflow-local memory (replay-safe), not a fresh L_15 query (non-deterministic).

**Resolution:** §6.5.4 rewritten:
```
for n in [1, 2, 3, 4]:
    workflow.sleep(Λ_n - Λ_{n-1})
    if local_obligation_state in {Pending, Instructed}:
        await workflow.execute_activity(emit_silence_attestation,
            obligation_id, watchdog_seq=n,
            options={start_to_close_timeout=30s, retry_policy=...})
        await workflow.start_child_workflow(wf_confirm_break,
            obligation_id, watchdog_seq=n,
            options={parent_close_policy=ABANDON})

# Or: race the watchdog against signal arrival
match workflow.select([
    workflow.signal_received("witness_arrived"),
    workflow.timer(intended_settlement_date + Λ_4 - now())
]) ...
```

Activities and child workflows are deterministic ingest points; sleep durations are Temporal timers; local state is workflow memory. Without this rewrite, replay non-determinism is a latent bug.

### N-3. SettlementSaga writer-uniqueness (DS17) vs. BuyInWorkflow's writes to original obligation.

§11 DS17: "each `o.state` field has a **unique writer**: the `SettlementSaga` workflow." §6.5.8 catalogue: BuyInWorkflow "(5) on completion, transition original `o → BoughtIn`."

These are inconsistent unless either (a) the SettlementSaga is still alive when BuyInWorkflow completes, and BuyInWorkflow signals the SettlementSaga to perform the `o → BoughtIn` transition, or (b) BuyInWorkflow is granted writer capability for the specific transition `Failed → BoughtIn` (which contradicts DS17's "unique writer").

R1 M-5 raised this and v2 §6.5.6 / §6.5.8 do not resolve it. This is the same issue as M-5 above; calling it out as a structural inconsistency between DS17 and §6.5.8.

**Resolution:** pick (a). Specify that SettlementSaga ContinueAsNews into a "wait for buy-in" mode on entry to FAILED state, with extended TTL. BuyInWorkflow signals the parent SettlementSaga on completion; the SettlementSaga performs the `o → BoughtIn` transition. DS17 stays correct.

### N-4. Cross-workflow signal communication for two-leg DvP (referenced in §6.5.2 but not specified).

§6.5.2: "A DvP trade with two legs has two `L_15.Obligation` rows and two workflow instances. They communicate via signals (§6.5.5) when atomicity at discharge is required (§6.5.3)."

But §6.5.3 then specifies that there is **no atomic trade-level discharge transaction**: each leg discharges independently, transaction-level all-legs-settled emerges from `tx_status` projection. So the two workflows do *not* need to communicate via signals for discharge.

What signals do they exchange, then? The text in §6.5.2 implies coordination; §6.5.3 implies independence. **The §6.5.5 commutativity table covers cross-trade signals as "independent; per-workflow isolation".**

**Resolution:** §6.5.2 sentence about cross-workflow signals should be deleted or rewritten to say: "The two legs of a DvP trade are paired at trade construction via `PairedObligation` (§12.2). The workflows operate independently and do not exchange signals; the trade-level `tx_status` is computed by external observers via the projection function (§5.3)." This removes a phantom mechanism reference.

---

## Pareto Judgment

**Pareto NOT REACHED** for the workflow layer. Eight items remain after v2:
- 4 partial closures: M-1, M-3, M-4, M-5
- 1 full miss: M-7 (search attributes)
- 2 carry-overs from MAJOR: M-2 overlap policy, M-6 GetVersion inventory
- 4 new issues: N-1, N-2, N-3, N-4 (N-3 is the same root cause as M-5)

None rise to BLOCKING. The R1 BLOCKERS (B-1..B-5) all close. The proposal is implementable. But the operational surface is incomplete: search attributes (M-7) are the operational interface; without them, the system cannot be operated by humans without circumventing the spec's own constraints (§4.3 forbids application-database joins).

The right next step is a **§6.5 supplement** (not a full v3 revision) addressing the eight items above. Recommended structure:

- §6.5.9 "Workflow catalogue (full)" — extends §6.5.8 with CsdrPenaltyAccrualWorkflow, CancelWorkflow, RestatementWatchHandler (or L_11 ingestion handler), CounterpartyDefaultWorkflow. Each row carries: trigger, body, `task_queue`, `parent_close_policy`, `retry_policy`, `deadline_budget`, `overlap_policy` (where applicable).
- §6.5.10 "Visibility / search attributes" — per-workflow-type search-attribute table (10 attributes minimum), Temporal Cloud advanced visibility commitment.
- §6.5.11 "Workflow versioning" — rate-table read pattern (`as_of(t_obligation_creation)` recommended), GetVersion gate inventory.
- §6.5.12 "Cross-workflow communication" — clarify §6.5.2/§6.5.3 inconsistency on DvP-leg coordination.
- §6.5.4 corrigendum — rewrite watchdog pseudocode in deterministic form (N-2).
- §6.5.1 corrigendum — add producer-monotonic `attempt_seq` sentence (N-1).
- §6.5.6 corrigendum — pin SettlementSaga ContinueAsNew on FAILED with extended TTL (M-5 / N-3).

Estimated work: 1–2 person-days. After the supplement, Pareto is reachable in the workflow layer.

---

## What v2 Got Right (read this first if reviewing the supplement)

- §6.5.1 `tx_id` formula. Genuinely closes B-1. The `business_event_id` namespace prefix design (`exec:`, `final:`, `buyin:`, `correction:`) is the right shape — it's content-addressed, source-stable, and survives replay.
- §6.5.3 DvP-L / DvP-S / DvP-E disambiguation. This is a conceptual win across the whole document (closes theme H). The per-leg discharge with `tx_status` emergence is a clean model and resolves the v1 §3.5 / §5.5 contradiction I flagged in R1 B-2. **The single best part of v2.**
- §6.5.5 commutativity table. The structural commitment that non-commuting cases are *deterministic precedences* (terminal absorbs; contradictions quarantine) — not race-condition fudge — is the correct framing. PO-8's TLA+ check at $|\mathcal{W}|=3, |U|=2, \text{depth}=8$ will verify multiset-replay against this table.
- §6.5.6 ContinueAsNew payload schema. Eight fields, all deterministic-across-CaN, `run_id` explicitly excluded. Closes M-10 cleanly.
- §6.5.7 saga compensation policy. Pins SETTLEMENT class entry as `cancel-compensation if not externalised; queue-and-reconcile if externalised`. Versioned bitemporally in `L_7^P.SagaCompensationPolicy`. Good.
- The Settlement Team accepted the new temporal-engineer seat. R1 recommended this; v2 delivered §6.5 — substantive and correct on the load-bearing items.
- §13.5 trust-assumption registry TA-DS-1..10 includes TA-DS-5 (clock skew ≤5s) jointly owned by jane_street + temporal — this is the right pairing for a determinism-vs-clock concern.

The economic model continues to hold. The §3 / §3.X conservation tables sum to zero over the constant universe. The §4.1 sign convention is consistent. The §12 type design migration is appropriately scoped to v11.0 core.

---

## Recommendation

**ACCEPT_WITH_CHANGES.** All five R1 BLOCKERS close. Workflow layer is implementable. Supplement §6.5 with the eight items above (estimated 1–2 person-days) before R3 Pareto check. Specifically prioritise:

1. **M-7 search attributes** — single highest-impact gap; spec is unrunnable without this.
2. **M-3 CsdrPenaltyAccrualWorkflow** — the `CSDR_PENALTY` Obligation row needs a workflow that emits its daily accrual.
3. **N-3 / M-5 BuyInWorkflow ↔ SettlementSaga writer relationship** — DS17's "unique writer" claim is currently inconsistent with §6.5.8's BuyInWorkflow row.
4. **N-2 watchdog determinism** — pseudocode rewrite avoids a latent replay bug.
5. **M-2 MorningRecon overlap and fan-out** — production readiness for tier-1 dealer scale.

Items 6–8 (M-1 enforcement locus pin; M-4 restatement trigger; M-6 GetVersion inventory; N-1 producer-monotonic seq; N-4 cross-workflow signal clarification) are one-sentence pins each.

The proposal is ready for R3 supplement, then Pareto. The Settlement Team's R1 closure work was substantive; the residual gaps are scope-creep (operational surface, not core correctness) that v2 swept under the existing prose. One more pass and the workflow layer is done.

— temporal-engineer
