# Round 1 Adversarial Review — Temporal-Engineering Lens

**Reviewer:** temporal-engineer
**Subject:** `phase3/round1/proposal_v1.md` (Phase 2 Settlement Team unified design)
**Date:** 2026-04-30
**Verdict:** **REJECT_REVISE.**

The proposal's *economic* model — trade-date `own` write at T, PS/PSS contras for the open-window, L_15 lifecycle, finality-as-virtual-wallet-rotation — is sound and convergent with my Phase 1 work. The structural commitments (DS1, DS2, DS7, DS18, the nostro recon identity §4.1) are correct. The CDM cross-walk and the type-design section (§12) are unusually precise.

But the proposal **routinely names "the SettlementWorkflow" as if it were a defined object** and then leans on it to discharge correctness obligations the spec does not actually pin down. Three of the eighteen invariants (DS5, DS6, DS9) are stated as runtime properties whose only justification is "Temporal will handle it" — a phrase that has no operational meaning. The `tx_id` shape in the canonical worked example is **inconsistent with PO-10 and with my v2 idempotency-key ruling**. The DvP atomicity guarantee at discharge time is **structurally unprovable** under the §3.5 finality formula, even though §12.2 (PairedObligation) exists in spec text — the §3.5 worked example and §12.2 type design contradict each other. Those are blocking.

The verdict is REJECT_REVISE rather than ACCEPT_WITH_CHANGES because the workflow specification is not present in the document; the proposal substitutes invocation of named workflows for specification of them. Without the workflow shapes pinned at the same level as the move algebra is pinned, "the architecture absorbs T+1 by parameter change" (§6.1) cannot be evaluated — the *parameter* is in the spec; the *architecture* is the unspecified Temporal layer.

Below in three tiers.

---

## BLOCKING (must fix before this proposal advances)

### B1. The `tx_id` formula in §3.2 is wrong, and contradicts PO-10.

§3.2 states:

> `tx_id = hash("ECON_REC", "BUY", "XYZ", 100, 50.0000_0000, GS_LEI, "2026-04-30T14:32:11Z")`

This is **content-addressed on a wall-clock-bearing tuple of trade essentials**. Three separate problems:

(a) It does not include the `business_event_id` namespace tag. My v2 ruling pins this: every business event must carry `"BE:cdm:..."` (upstream) or `"BE:syn:..."` (synthesised) namespace. Without that, two events from different sources whose payloads happen to canonicalise the same will silently collide.

(b) It does not include `attempt_seq`. PO-10 itself states "the `tx_id` derivation must NOT include `run_id` or any ContinueAsNew-ephemeral field." The corrected shape from my v2 work is `tx_id = hash_jcs(business_event_id, attempt_seq)` with `attempt_seq` carried through `ContinueAsNew` as a workflow-state field. The proposal's formula has neither.

(c) The wall-clock timestamp `"2026-04-30T14:32:11Z"` is fine *if and only if* it is the venue-supplied execution timestamp received as data from a deterministic source (e.g., the FIX 8=ExecRpt). If a workflow ever computes `tx_id` from `workflow.Now()` or any wall-clock read internal to the workflow, replay produces a different `tx_id` → executor-layer idempotency fails → silent double-commit. The spec must explicitly state the timestamp is venue-supplied, hash-pinned at ingress, never re-read.

The same issue infects §3.5:

> `tx_id = hash("FINAL", TX1.tx_id, sese.025_msg_id, camt.054_msg_id)`

This formula requires both inbound message IDs to be present at the moment the finality contra-transaction is emitted. **But sese.025 (securities) and camt.054 (cash) arrive on `L_11.ExternalConfirmation` independently and possibly out-of-order.** The proposal does not say:

- Does the workflow wait for both before emitting `TX1_FINAL`? (If so, the spec must say so, and DS5 must specify the bounded wait.)
- Does it emit two separate finality contra-transactions, one per leg? (If so, the formula is wrong; the txs must be `hash("FINAL_SEC", ...)` and `hash("FINAL_CASH", ...)`.)
- Or is `TX1_FINAL` actually two transactions presented as one in the worked example for clarity? (If so, the spec must say so explicitly.)

§3.5 is silent on this. §5.5 (idempotency and out-of-order ingest) says "the per-leg FSM transitions are on disjoint obligation rows, and the joint state is invariant under interleaving" — which implies *two separate finality transactions per leg*. **§3.5 and §5.5 contradict each other.** Either fix §3.5 to commit per-leg or fix §5.5 to acknowledge there is a coordination join.

**Required fix.** Rewrite the `tx_id` shape uniformly across §3.2, §3.5, §5.5, §6.4, §6.5 as `tx_id = hash_jcs(BE_namespace || business_event_id, attempt_seq)`. State explicitly which transactions are committed per-leg (one `tx_id` per leg) vs. joint (one `tx_id` for the trade with both legs in a single executor commit). State when each is used.

---

### B2. DvP atomicity at discharge time (DS18) is contradicted by the §3.5 worked example.

§12.2 (PairedObligation) is correct: discharge is a function of `PairedObligation.t -> ... -> DischargeResult.t`; "There is NO public function `Obligation.t -> ... -> DischargeResult.t`." Good.

But §3.5's `TX1_FINAL` transaction:

```
Move 1: w_GS_broker -> PSS_receivable[w_us, GS, XYZ] (securities)
Move 2: PS_payable[w_us, GS, USD] -> w_GS_broker (cash)
L_15 update both legs to Discharged
```

This works **only if both `sese.025` and `camt.054` are present** at the moment `TX1_FINAL` is emitted. In production:

- DTC sends `sese.025` at 16:30:42.
- JPMC sends `camt.054` at 16:32:14 (or 17:15, or never if the cash agent failed).

The proposal does not specify what the workflow does between 16:30:42 and 16:32:14. Three possibilities, none specified:

1. **Wait for both.** Discharge is one transaction (per §3.5). Question: how long does the workflow wait before declaring half-failed (`LegInconsistent` per §12.1, formalis G4)? The spec does not pin a window. A 5-minute window is "obviously right" to a Temporal engineer but absent from the spec is a CSDR-penalty-clock attack surface (the cash leg is still failing during the wait). 

2. **Discharge per-leg.** The DvP-at-discharge structural property §12.2 is then a fiction: each `sese.025` and `camt.054` arrival is its own transaction discharging its own `Obligation.state Pending → Discharged`, and the `MoveStream[tx_id].settlement_status` becomes `PARTIALLY_SETTLED` between the two arrivals — a state that §5.6 reserves for *quantity*-partial discharges, not *leg*-partial. **Semantic clash.**

3. **Per-leg discharge with synthesised join transaction.** Each arrival commits its leg; a third transaction (`TX1_FINAL_JOIN` or similar) is emitted when both legs discharge to advance the transaction-level status. Three workflow transactions per trade discharge instead of one. Fine, but unstated.

Without picking one explicitly, the spec's DS18 (structural DvP atomicity) holds at trade-time T but not at discharge-time T+2. **§7.5 of v10.3 talked about this; the Phase 2 proposal forgot to.**

**Required fix.** Pick one of the three. If (1), specify the join-window timer (call it `dvp_join_window`, default 5 minutes, configurable per CSD). If (2), reconcile with §5.6's `PARTIALLY_SETTLED` semantics — likely by adding a `LEG_HALF_DISCHARGED` intermediate status. If (3), spell out the three transactions and their idempotency keys.

---

### B3. DS5 (replay determinism on out-of-order finality) is asserted but not testable.

DS5 statement (§11):
> For any two interleavings $\pi_1, \pi_2$ of the same multiset of confirmation messages applied to the same initial state $\sigma_0$: $\text{apply}(\sigma_0, \pi_1) = \text{apply}(\sigma_0, \pi_2)$.

This is the right property. But it is asserted with no specification of *the apply function*. The apply function is the SettlementWorkflow's signal handler. A Temporal signal handler that processes signals in arrival order is **not** a confirmative function unless every signal handler is itself idempotent and commutative.

Concretely: if `sese.025` (securities full discharge, qty 100) arrives after a `sese.025_partial` (qty 60) arrived earlier and was already processed:
- The workflow has spawned a child obligation for the residual 40.
- The full-discharge signal is logically *correct* but operationally a contradiction.
- The signal handler must reject the late full-discharge as `Idempotent` (per §12.1 step function).

But the proposal does not specify this rejection. §5.5 says "Replay of the same witness produces no duplicate state transition" — that's idempotency of the *same* signal, not commutativity of *different* signals against an evolving state. **DS5 is stronger than §5.5 specifies.**

**Required fix.** State the apply function explicitly. Specify which signal handlers are commutative (most aren't), which are idempotent-only-against-the-same-signal, and which require ordering enforcement. For the ones requiring ordering, specify the producer-monotonic sequence number per my v2 ruling ("every signal-driven cross-workflow communication that depends on monotonicity needs a producer-monotonic sequence in payload, sorted at receiver"). Add a property test that fuzzes signal arrival orderings and verifies the final state.

This is not negotiable for DS5 to be machine-checked. Right now DS5 is a hope, not a property.

---

### B4. The T+2 trigger mechanism is not specified (signal-driven? timer-driven? both?).

The proposal in §3.4 says "T+2 morning (2026-05-04 09:00 UTC, before finality) — no moves" and in §3.5 "T+2 finality (2026-05-04 ~16:30 UTC, after DTC end-of-day batch)." Implicit: a workflow is asleep waiting.

But asleep on what?

- **A timer firing at `intended_settlement_date` EOD?** That is the Phase-1 design (`with wf.with_deadline(payload.t_settle)`). It produces a deadline-based fallback poll if no signal arrives.
- **Pure signal-driven (no timer)?** Then if the CSD silently drops the message, the workflow waits forever. Not acceptable.
- **Daily ticker timer?** Wakes up daily at EOD to check status. Adds replay history but bounded.

Phase 1 §7.2 picked option 1 and added a `query_csd_status` activity as fallback. The Phase 2 proposal silently dropped this.

This matters because:
- §6.3 says "T_max exhausted with watchdog-confirmed absence-of-witness" — that is option-1 plus an external watchdog (Phase 1 §13 §G8 acknowledged this is a liveness gap; the spec must close it explicitly here).
- DS9 buy-in compensation closure asserts "Temporal timer + saga-tower" — but the timer is in the SettlementSaga, the saga-tower is the Phase 1 BuyInWorkflow. Neither is specified in proposal_v1.

**Required fix.** Pin the trigger explicitly in §5.x. The text I expect: "SettlementSaga workflow runs from T to settlement; primary path is signal-driven on `csd_finality` signal; fallback timer fires at `intended_settlement_date + dvp_join_window` (default `t_d` + 5 min) and triggers a `query_csd_status` activity; if status query returns `Settled`/`Failed`, workflow advances FSM accordingly; if status is still `Instructed` at T_max, the workflow opens a `wf-obligation-break` in L_18 and continues to await a witness." Then DS9 has an executable mechanism.

---

### B5. PO-10 internal contradiction with §15.2 (per-counterparty vs per-instruction PS/PSS keying).

PO-10 commits to "`SettlementSaga` is implemented as signal-driven workflow with timer (per temporal §7.2)." Phase 1 §7.2 keys the workflow ID as `"SET:SO:" || hash_jcs(business_event_id, leg_index)` — i.e., **per (trade leg)**.

But §15.2 says per-counterparty per-(currency-or-ISIN) PS/PSS wallet keying is "the floor; per-instruction is permitted as a derived view." This is wallet keying, not workflow keying — but the workflow needs to know which wallet to debit/credit on signal arrival.

Two scenarios:
- **One SettlementSaga per trade leg** (Phase 1 design): each saga touches `PS_payable[w, cpty, ccy]` shared with N other concurrent sagas for the same `(w, cpty, ccy)` triple. This is fine as long as the executor is the single writer and serialises moves, but it means each PS_payable balance is the sum of N saga effects — debugging "why is PS_payable wrong" requires aggregating N saga histories.

- **One SettlementSaga per `(w, cpty, ccy)` bucket** (collapsed): the saga lives for the duration of *all* open trades against that counterparty in that currency. History grows unboundedly; ContinueAsNew becomes mandatory. Workflow ID is no longer trade-leg-content-addressed and the dedup story changes.

The spec must pick one. I expect the answer is "per trade leg" (Phase 1) but the proposal does not pin it. Without that pin, multiple PO-10 properties (workflow ID stability, dedup-set sizing, ContinueAsNew necessity) are unspecifiable.

**Required fix.** Add to §5 (lifecycle FSM): "Workflow ID is `SET:` + `obligation_id` per leg. There is one SettlementSaga per L_15 obligation row. The PS/PSS wallet keying is a separate axis (per-counterparty per-currency-or-ISIN); concurrent SettlementSagas operating on the same PS/PSS wallet pair are serialised by the executor's atomic-tx primitive."

---

## MAJOR (must fix before Round 2 implementation)

### M1. CORRECTION transaction four-eyes: enforcement locus unspecified.

§6.5 and §10.9 both say "framework rejects any CORRECTION where `requester_lei == approver_lei`." Both also say "four-eyes is non-negotiable." But where is this enforced?

Three candidate loci:
1. **In a workflow** (e.g., `CorrectionWorkflow` that signals require both approver and requester before emitting the CORRECTION tx). Adds latency, durable, auditable.
2. **In the executor** (the smart contract guard rejects on `requester_lei == approver_lei`). Compile-time / capability-typed; cleanest.
3. **In a pre-trade gateway activity** (validation activity in front of CORRECTION tx submission). Activity can be retried, must be idempotent, must not be the *only* check.

The spec does not pick. PO-10 mentions only `SettlementSaga`. CO-6 (§10.6) says "every CORRECTION requires four-eyes + named approver" but the test description is "system enforcement; audit log review" — implies (2). DS17 (§11) says capability scoping is compile-time, which also suggests (2).

I read this as **(2) is intended but not specified**. Required fix: explicitly say "the executor's CORRECTION-type tx admission guard rejects the tx if `requester_lei == approver_lei`. This is a pre-emission C11 capability check, not a workflow concern." Then `CorrectionWorkflow` is just a UX/orchestration wrapper that gathers the two sigs, not the enforcement point. Otherwise CO-6 fails its SOX test plan.

---

### M2. MorningReconWorkflow (§4.4) — overlap policy and fan-out shape unspecified.

§4.4 says "Runs as a Temporal cron `MorningReconWorkflow` at 09:00 local in each reporting timezone." Two unspecified concerns:

(a) **Overlap policy.** If yesterday's recon takes longer than 24 hours (rare but possible during major restatement events), what happens at 09:00 today? Skip, BufferOne, BufferAll, AllowAll, or Terminate? The right choice is `Skip` with an out-of-band alert (because otherwise a bad day chains forward). But this is not stated.

(b) **Fan-out shape.** §4.3 says "constant-time scan, not a join" — but constant-time-per-real-wallet implies a fan-out across all real wallets in scope. Is this:
- One activity that scans all real wallets for the recon? (Bounded; needs heartbeats if > seconds; CPU-bound on large books.)
- A fan-out workflow that spawns one child per real wallet? (Independently retriable; observable; standard Temporal fan-out/fan-in pattern.)
- A scheduled per-real-wallet workflow? (Parallel by default; complicates aggregation.)

For tier-1 dealers with thousands of real wallets, choice matters. Pick one and specify heartbeat / activity timeout.

Also: §4.4 mentions "in each reporting timezone" — multiple time zones means multiple Schedules. Are these on different task queues (`wf-recon-emea`, `wf-recon-apac`, `wf-recon-amer`)? Or one global `wf-recon` queue with locale tag? My v2 ruling on task queue topology says: per-domain queue, no per-region split unless latency-driven. Pin this.

---

### M3. CSDR penalty accrual workflow is referenced but never specified.

§6.3 says "Daily accrual emits a small cash transaction (failing party → suffering party) atomically with `o_pen.csdr_penalty_accrued` update. Settlement to T2S monthly cycle via `pacs.008`."

Three workflow-shaped questions, none answered:

(a) **Per-obligation or batched?** Phase 1 §7.4 said "fan-out scheduled workflow (Temporal Schedule, overlap policy `Skip`)." Phase 2 silently drops this. If batched, idempotency of the batch becomes the whole point — what's the dedup key? `hash_jcs(accrual_date, obligation_id)`?

(b) **Long-lived per-fail vs daily fan-out?** A long-lived `CSDRPenaltyAccrualWorkflow` started when an obligation enters `FAILED` and lives until the obligation closes (`SETTLED`, `BoughtIn`, `Compensated`, `Defaulted`) is one design. Daily fan-out scanning all `FAILED` obligations is another. Each has different ContinueAsNew implications.

(c) **Cash penalty as a real Move pair or a state-only transaction?** §6.3 says "a small cash transaction" but does not say between which wallets. If `failing_party.own → suffering_party.own`, then real-wallet cash moves between firms during the penalty window — but the *penalty* is paid in T2S monthly batch, not daily. So the daily accrual must be against an *accrual* virtual wallet, with a monthly settlement via `pacs.008` matched against the accrual. This is unstated.

**Required fix.** Add §6.3a "CSDR penalty workflow shape" that specifies (a) one daily-cron `CsdrPenaltyAccrualWorkflow` with overlap-policy `Skip`, fan-out across all `FAILED` obligations active at EOD, idempotency key `hash_jcs(accrual_date, obligation_id)`; (b) accrual is to a virtual `accrued_csdr_penalty[failing_party, suffering_party, ccy]` wallet; (c) monthly `pacs.008` reconciliation matches accrual sum to ESMA statement.

---

### M4. Restatement of finality (G5) interacts with completed workflows; the fix is not described.

G5 (§13.1) acknowledges: "A CSD may restate ... Settlement workflow that already concluded on yesterday's confirmation cannot be 'un-concluded' — Temporal histories are append-only and idempotent in the forward direction, not reverse." Recommendation (a): treat restatement as a *new* obligation. Good choice.

But the recommendation is not architecturally specified. To implement (a) you need:
- A `RestatementWatchWorkflow` (per my v2 work) that observes restated CSD confirmations.
- For each restatement: emit a CORRECTION tx against the original obligation (`Pending → Compensated, kind=CSD_RESTATEMENT`) plus a *new* obligation row carrying the restated qty.
- The new obligation gets a fresh SettlementSaga with its own deadline.

This is multi-step orchestration crossing the original (completed) workflow boundary. The spec must specify **who triggers the watch.** L_11 ingestion side? An out-of-workflow detector? A new field on `L_15.Obligation` carrying `corrections_chain` (DS16) consumed by the watch?

Required fix. Either pin the `RestatementWatchWorkflow` shape or add G5 to §15.1 known weaknesses with explicit Phase-3-Round-2 closure.

---

### M5. Bounded signal-dedup TTL (PO-10) too short for FAILED→BoughtIn cascades.

PO-10 specifies "Dedup set (`processed_signals`) bounded (n=4096, TTL=30 days)." Reasonable for the standard 2–7-day saga.

But:
- A `FAILED` obligation can sit in CSDR penalty-accrual mode for 30+ days waiting for either re-instruction, buy-in confirmation, or default declaration.
- A buy-in cascade (per §7.6) chains: original `FAILED` at T+2; buy-in instructed at T+3; buy-in settles at T+5; original `BoughtIn → SETTLED` at T+5+ε. That's 5+ days but if the buy-in itself fails and retries, the cascade extends.
- The `attestation` register for CSDR `semt.044` arrives **monthly**.

Some of these are handled by spawning a child workflow (BuyInWorkflow has its own dedup set), but the parent SettlementSaga must continue to receive late discharge messages for the *original* obligation right up to terminal state. 30-day TTL might be violated.

**Required fix.** Either lift the TTL to `T_max + max_buyin_extension + 1bd` (trade-class-dependent; ~45–60 days for liquid equities; longer for illiquid), or move the dedup set to an out-of-workflow dedup table. My v2 work allowed both; Phase 2 should pick.

---

### M6. Workflow versioning when CSDR rules change retroactively.

§9.2 mentions "ESMA recalibrates a CSDR rate retroactively" and §11 DS14 commits to "pure function from versioned CSDR rate matrix, pinned by `VersionPinSidecar`." Good.

But what does the SettlementSaga do when ESMA publishes a recalibration on day t_now that applies to obligations created on day t_now − 6 months?

Two scenarios:
- **In-flight obligations carry their rate-table version pinned at obligation creation.** Then the recalibration applies only to obligations created after `t_known_new`. (Mode-1 bitemporal, my v2 ruling for calendar amendments.)
- **In-flight obligations re-read the rate table on each accrual.** Bitemporal-state-function (per G3 / PO-4). Then a calendar amendment causes accrual amounts to change retroactively for ongoing obligations.

The proposal doesn't pick. Different choices imply different `GetVersion` strategies. From my v2 inventory of GetVersion gates, this is the right place for `gate_settlement_csdr_penalty_v3`. The proposal mentions Phase 1's gates but does not commit to them.

Also: the related question — **CSDR penalty rate is a refdata pin (CDM `Trade.cdm_payload`) or a workflow input parameter?** If it's refdata, it's pinned at trade creation and reads under `as_of(t_known)`. If it's a workflow parameter, it's written into the workflow input at start and survives ContinueAsNew. Different storage stories. Specify.

**Required fix.** Add a §11.4a "Versioning" subsection: list the GetVersion gates the SettlementSaga uses, pin the rate-table read pattern (refdata-pin under `as_of` is my recommendation), state the cutover semantics for retroactive amendments.

---

### M7. Visibility / search attributes silently dropped.

Phase 1 §9 enumerated:
```
obligation_id, business_event_id, counterparty_lei, csd, currency,
settlement_date, buyin_deadline, state, fail_reason, notional_usd
```

Proposal_v1 does not specify any. This is operationally critical: without search attributes, ops cannot run the queries §4.5 implies ("`wf-confirm-break` for trade past expected_settlement_date with no witness") without going to the application database — which §4.3 explicitly forbids ("No join to MoveStream").

**Required fix.** Add §11.5 "Visibility": list required search attributes per workflow type (`SettlementSaga`, `BuyInWorkflow`, `MorningReconWorkflow`, `CsdrPenaltyAccrualWorkflow`). Specify Temporal Cloud advanced visibility vs. self-hosted Elasticsearch dependency. **Search attributes are the operational interface; without them DS4-DS9 are correctness theatre.**

---

### M8. "Watchdog-confirmed absence-of-witness" (§6.3) is non-deterministic.

§6.3 says a `Failed` state is "witness-driven FSM transition (DS4) — `sese.024` inbound or T_max exhausted with watchdog-confirmed absence-of-witness."

The watchdog is presumably an external system that polls the L_11 store and asserts "no witness for obligation X exists at time t." That assertion has to enter the workflow — either as a signal or as an activity result. Both are non-deterministic in subtle ways:

- **As an activity result:** the watchdog activity reads at workflow time `T_max`. On replay, the activity result is replayed from history, so determinism is preserved. But the activity must be idempotent on re-invocation — it can return different results across genuine retries (the witness might arrive between attempts). The first successful return is the one cached. **OK if the activity is the single source of truth at T_max.**

- **As a signal:** the watchdog signal is durable, but the workflow's reaction to it depends on the signal arrival time relative to other signals (a witness arriving at T_max + ε vs the watchdog signal arriving at T_max + ε — race). DS4 says no discharge without witness, but if the watchdog signal arrives first the workflow promotes to FAILED, then the late witness arrives — what now?

The spec needs to pick. Recommendation: activity-result, because workflow ordering is then deterministic by replay. The activity itself can be retried with backoff up to T_max + grace_window; if any retry returns a witness, the witness is processed; if all retries up to grace_window return no-witness, the workflow promotes to FAILED. Late witness arriving after FAILED promotion is rejected (per DS4 — discharge already fired) or queued (per the late-discharge race policy in my v2 work — `SETTLEMENT = cancel-compensation if not externalised; otherwise queue-and-reconcile`).

This whole dance is unstated in the proposal.

**Required fix.** Pin the watchdog mechanism in §6.3. Activity-driven, with retry policy and grace window. State the late-discharge race policy for the FAILED state explicitly (it is already in PO-2; promote to inline spec text rather than open obligation).

---

### M9. Compensation is named but its boundary (saga vs activity vs workflow) is unspecified.

The proposal repeatedly names "compensation handler" (§6.5: `compensation_handler: SettlementFailHandler`; §11 DS9: "Λ_13"; §15.2: "Late-discharge race policy table"). Three different shapes are possible:

- **Compensation activity** (single executor call). Trivial cases only; cannot run multi-step compensation with its own deadlines.
- **Compensation child workflow** (e.g., `BuyInWorkflow`, `CancelWorkflow`). Runs independently of the parent saga; its own deadlines, retries, search attrs. **This is what my v2 ruling pinned.**
- **In-saga compensation branch** (the saga itself chooses `Failed → Compensated` via `wf.execute_activity(emit_correction)`).

§6.5 ("Post-instruction cancel: multi-step saga (Temporal workflow)") implies compensation child workflow. §11 DS7 ("Failure non-reversal") implies in-saga (no compensation moves except CORRECTION). §13.1 G4 (DvP leg-inconsistent failure compensation) implies a per-CSD κ catalogue of compensation handlers. **Three different shapes are alluded to without picking one.**

My v2 ruling says: non-trivial compensation is a child workflow, period. Activities cannot run multi-step compensation. The proposal must adopt this.

**Required fix.** State in §5 and §6: each compensation handler is a child workflow, named (`BuyInWorkflow`, `CancelWorkflow`, `CsdRestatementWorkflow`, `CounterpartyDefaultWorkflow`). Each has its own task queue, deadline budget, retry policy, search attributes. Each is started with `parent_close_policy=ABANDON` so the parent SettlementSaga can `ContinueAsNew` or terminate without orphaning the compensation.

---

### M10. ContinueAsNew not addressed for SettlementSaga.

Phase 1 §12 acknowledged: "A `SettlementSaga` typically runs 2–7 calendar days. History size is bounded — a few hundred events at most. ContinueAsNew is not a normal-path concern." Proposal_v1 does not address this at all.

But under FAILED → BoughtIn cascades that span 30–60 days, and under ContinueAsNew chains (parent → BuyInWorkflow → CSDR escalation), the history can grow. More important: **what is the ContinueAsNew payload schema?** My v2 work pinned `attempt_seq`, `processed_signals`, `cdm_v`, `canonicalisation_v`, `obligation_id` as the minimum. Phase 2 must inherit this.

**Required fix.** Add a §11.6 "ContinueAsNew Discipline." State whether SettlementSaga ContinueAsNews. If yes, specify the frozen payload schema. If no, state the bound (e.g., "if obligation enters FAILED state, the workflow `start_child_workflow(BuyInWorkflow, parent_close_policy=ABANDON)` and terminates; the buy-in workflow has its own ContinueAsNew discipline").

---

## MINOR (should fix; do not block)

### m1. §6.4 attempt_seq trailing 0/1 in tx_id is redundant and confusing.

The example `hash("FINAL", TX1.tx_id, sese.025_partial1_msg, 0)` and `hash("FINAL", TX1.tx_id, sese.025_partial2_msg, 1)` includes a trailing `0` / `1` plus the message ID. The message ID alone is sufficient for uniqueness. Either drop the trailing seq (since the message ID is content-addressed) or use the seq alone (and not the message ID for the hash). Don't double-protect — it implies one of them is unreliable, which raises questions.

### m2. "sese.025" used as both message identifier and singular-singular event class.

The proposal sometimes uses `sese.025_msg_id` as a unique identifier and sometimes as a class name. Be consistent — use `sese.025.MessageId` for the field; `sese.025` as the message-class name.

### m3. §11 DS-table mixes type-system and runtime mechanisms in a single phrase.

DS1: "(CT) capability typing on `own` write-handlers; (RT) PnL-independence property test." Two mechanisms; both sound. But the cell mixes them — the table reader has to parse "CT|RT" then the parenthesised text. Split into two columns: `CT mechanism`, `RT mechanism`.

### m4. §3.5 finality conservation table has the right answer but the wrong wallet labels.

The §3.5 table shows ΔPSS_recv goes from -100 (post-T) to +100 (post-finality) i.e. ΔΔ = +100. That's consistent with `Move 1: w_GS_broker -> PSS_receivable[w_us, GS, XYZ]`. Fine. But the textual setup before the table says "Drain the PSS_receivable into broker virtual wallet" — which would suggest direction is from PSS_receivable, not into. The text and the move directions disagree. Reconcile.

### m5. §11 DS18 (DvP atomicity) parented on "v10.3 P2, §8.4; StatesHome C3; minsky I-DEF-12." But the §8.4 reference is *trade-time* atomicity. DS18 covers *discharge-time* atomicity — see B2 above. Reparent or redraft.

### m6. §15.2 lists "Per-counterparty vs per-instruction PS/PSS wallet keying" as not-converged. This is fine to defer — but the SettlementSaga's workflow ID design depends on this. **Block-then-convene:** can the team decide one keying for v11.0 with the other listed as future work? My recommendation: per-counterparty per-(currency-or-ISIN) per-side, four virtuals per `(w, cpty, ccy_or_ISIN)`. Per-instruction is a derived view.

### m7. PO-9 (D_max recursion bound) is left at 2 (jane_street) vs recursive (sbl/temporal/karpathy). I leaned recursive in Phase 1 but reading the §6.4 partial-fill cascade more carefully, **2 is enough** for liquid equities; 3 might be needed for illiquid CSDR cascades. Recommendation: D_max=3, configurable by `regime_pin`. Beyond D_max → Defaulted.

### m8. §9.2 mentions `pacs.008` for monthly CSDR penalty settlement. `pacs.008` is a customer credit transfer; the standard CSDR penalty cycle is `semt.044`. Verify this with isda; might be a mis-citation.

---

## What works

- The PS/PSS gross-payable/gross-receivable split is exactly right. IFRS 7 grounding is correct; the operational reasons (right-of-set-off jurisdictionality, asymmetric CSDR penalty taxonomy, conservation cleanliness) are sufficient; finops's veto of signed-net is sound.
- The reconciliation identity §4.1 is algebraic and constant-time. The sign correction over Phase 1 finops is helpful and well-explained.
- The "no fourth StatesHome map" claim in §2.5 is verifiable. PS/PSS are wallet rows in WalletRegistry; balances live in PositionState by `own` coordinate; no new fields. **This is the architectural test the proposal passes cleanly.**
- §12 type design is excellent. PairedObligation as the only path to discharge is the right structural enforcement. Phantom-typed wallet handles enforce DS1 at compile time. Newtype dates close G7. The 14 malformed-obligation rejections in §12.5 are concrete and testable. Migration cost is acknowledged (~14 weeks); it's worth it.
- §3.7 path-independent PnL across the trade lifecycle is the right hill to die on. Three columns (T, T+1, T+2) and the cumulative arithmetic is the load-bearing demonstration.
- §11 DS-invariant register is well-organized; the parent citations to v10.3 / data-spec / Phase-1 dissents are useful for reviewers; the type-vs-runtime decomposition (6 CT, 9 RT, 3 hybrid) is honest.
- §13 honest gaps (G1–G12) is properly disciplined. Each gap is named, owned, and either closable in Phase-2 or acknowledged as external.
- §10 accounting / audit / capital section is unusually concrete. The Form-A vs Form-B journal entry distinction (§10.2) is the right call.
- The CDM cross-walk (§8) and the four Rosetta extension PRs are the kind of structural deliverables that will move the industry.

---

## Recommendation

**REJECT_REVISE.** The economic specification is sound; the workflow specification is largely missing. Five blocking items:
1. Fix the `tx_id` shape uniformly (B1).
2. Pin DvP discharge atomicity mechanism — wait-for-both vs per-leg vs three-tx-join (B2).
3. Specify the apply function for DS5 (which signals are commutative, which require ordering, signal-dedup mechanics) (B3).
4. Specify the T+2 trigger (signal-driven primary, fallback timer + status-query activity, watchdog grace window) (B4).
5. Pin the SettlementSaga workflow ID granularity (per-leg vs per-bucket) (B5).

Ten major items requiring closure before Round 2 implementation:
- CORRECTION enforcement locus (executor guard, not workflow) (M1).
- MorningReconWorkflow overlap policy and fan-out shape (M2).
- CsdrPenaltyAccrualWorkflow shape (M3).
- RestatementWatchWorkflow for G5 (M4).
- Signal-dedup TTL for long-lived FAILED states (M5).
- GetVersion gate inventory for CSDR rate-matrix versioning (M6).
- Visibility / search attributes (M7).
- Watchdog mechanism for "absence-of-witness" (M8).
- Compensation as child workflow (not activity, not saga branch) (M9).
- ContinueAsNew payload schema (M10).

After these are addressed, the proposal becomes ACCEPT_WITH_CHANGES against minor items (m1–m8). Recommend the Settlement Team circulate a `proposal_v2.md` with §5 expanded into a "Workflow Architecture" section (~6 pages) covering: workflow types (one bullet each: SettlementSaga, BuyInWorkflow, CancelWorkflow, CsdrPenaltyAccrualWorkflow, MorningReconWorkflow, RestatementWatchWorkflow, CounterpartyDefaultWorkflow), workflow IDs, task queues, signal channels, search attributes, ContinueAsNew schemas, GetVersion gates, deadline budgets, retry policies. Without this, "the architecture absorbs T+1 by parameter change" is a claim about a layer that hasn't been written down.

The Phase-2 process correctly converged on the economic model. The Temporal layer was not convened — and it is the layer where DS5, DS6, DS9, DS17, and DS18 are actually enforced. Round 1 is the right gate for this discovery; Round 2 should be implementation against a fully-pinned workflow spec, not against §5's eight bullet points.

— temporal-engineer
