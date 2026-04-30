# Phase 3 Round 1 — Adversarial Review (Temporal Discipline)

**Reviewer:** Arjun Mehta (independent temporal-engineer instance, fresh context)
**Date:** 2026-04-30
**Target:** `phase2/proposal_v1.md` (Phase-2 integrated synthesis), with the Phase-2 `temporal.md` as input.
**Mode:** adversarial. Author does not get the benefit of the doubt.
**Scope of attack (per brief):**
1. Are the 6 "awkward-fit" categories *addressed*, or merely *named*?
2. Per-leaf idempotency-key collision-freedom under realistic input.
3. Replay-determinism boundaries — clean or porous?
4. Saga compensation pattern for L16 obligations — correct?

I write findings before the summary. Findings are classified **BLOCKING** (must be resolved before convergence), **UNMITIGATED MAJOR** (substantive risk that the proposal does not currently bound), **MINOR** (improvable, trade-off acceptable).

---

## 1. Attack on §6 "awkward-fit" categories — addressed or just listed?

The Phase-2 `temporal.md` enumerates six awkward-fit categories. The integrated proposal §9.5 lifts the same list verbatim and asks Phase 3 reviewers to "rule on whether these architectural tensions are resolved." Reading both documents together, my finding is: **3 of 6 are genuinely addressed, 2 of 6 are stated but not bounded, 1 of 6 is hand-waved.**

### 1.1 Category 1 — Retroactive calendar amendments — **UNMITIGATED MAJOR (M-1)**

The Phase-2 mitigation is "a `CalendarUpdateOrchestratorWorkflow` per `(jurisdiction, market)` that holds the affected-unit set in workflow state and fans out updates as child workflows."

Three problems the proposal does not address:

**(a) The orchestrator's workflow state is unbounded.** The "affected-unit set" for a major jurisdiction (USD/G10) at a major firm is O(10^5) units. The orchestrator workflow's history (every `RegisterAffectedUnit` signal, every fan-out child completion, every child failure) will exceed Temporal's per-workflow history-size soft limit (50k events, 50 MB) within months of normal operations. The proposal does not specify a `ContinueAsNew` cadence for this orchestrator, nor does it specify how the affected-unit set is carried forward (the *list* itself can grow unboundedly).

**(b) Fan-out cardinality vs. workflow-task budget.** A retroactive holiday declaration that affects 100k units triggers 100k child workflows. Temporal's default per-namespace task-queue throughput is finite. The proposal does not size this and does not specify whether the fan-out is rate-limited by the orchestrator (using a semaphore activity) or by task-queue partitioning. **Unbounded fan-out is the most common production Temporal incident I have seen.**

**(c) Schedule-rebuild consistency.** When the orchestrator's child workflow re-runs `ResolveAdjustableDate` against the updated calendar version, it produces a *new* `schedule_version_seq`. The lifecycle workflow consuming the unit's schedule must (i) accept the new version atomically (not partially, not retroactively to already-fired timers), (ii) cancel and re-arm any in-flight timers that referenced the old schedule, (iii) reconcile already-discharged obligations under the *old* schedule against the new one. The proposal §3.1 L4 says only "workflow versioning + signal-driven schedule rebuild" — this is a label, not a mechanism. Specifically: **a retroactive holiday that *invalidates* a coupon timer that has already fired** is a bitemporal-replay bug Temporal cannot solve. The lifecycle workflow's history records that the coupon paid; the new calendar says it should not have. This is the kind of contradiction the data-layer spec must rule on, and §6.1 of the Phase-2 temporal does not.

**Required mitigation for convergence:**
- The `CalendarUpdateOrchestratorWorkflow` ContinueAsNew payload must be specified explicitly (affected-unit set carried as a paginated list ID, not inline).
- Fan-out rate-limiting policy must be specified (semaphore activity with concurrency cap, or task-queue partitioning by `(jurisdiction, market)`).
- A **timer-fired-before-amendment** policy is required: either (i) the calendar amendment cannot retroactively invalidate already-fired timers (the resolved schedule wins; the new calendar applies only to schedules resolved after the amendment knowledge timestamp — which is the bitemporal answer), or (ii) the amendment can invalidate, in which case a compensation chain must be specified for every obligation discharged under the old schedule. **The proposal must pick one.** The Phase-2 doc gestures at (i) without naming it.

### 1.2 Category 2 — High-frequency tick streams — **MINOR (m-1)**

This is the cleanest of the six. The Phase-2 temporal §6.2 + §3.1 correctly states that ingest is *not* a workflow; feed handlers are stateless services writing into the snapshot store; workflows consume via `capture_snapshot(spec) -> snap_id`. Integrated proposal §3.4 L10 carries this through.

**Minor concern:** the proposal does not specify the snapshot store's **own** durability/replication contract. If the snapshot store is a single-region S3 bucket and a region fails between an activity's write of `snap_id` and the workflow's history persisting it, the snapshot exists in history but cannot be re-read on replay → silent replay failure. This is mitigatable (multi-region snapshot store) but should be named in the proposal as an **assumption owner**. Add to §6 conditional guarantees: **C-A11 — snapshot-store durability and replication discipline.**

### 1.3 Category 3 — Continuous bitemporal corrections — **BLOCKING (B-1)**

This is the most important finding in this review. The Phase-2 temporal §6.3 says, accurately: "Temporal's history is a single-axis append-only log of when events were processed; mapping bitemporal queries onto it requires application-level discipline." The integrated proposal §9.5 says "ruling required."

The proposal does not rule. It states the problem and moves on.

**Why this is BLOCKING.** A vendor restatement of a prior `t_obs` (e.g., a fixing publication corrected three days later) creates two bitemporal records `(t_obs, t_known_1)` and `(t_obs, t_known_2)`. The downstream consumers split into two classes:

1. **Workflows that already consumed `(t_obs, t_known_1)`** — their history records the value at the time of consumption. Replay returns the same value (correct). They must **not** re-fetch with the corrected `t_known_2` on replay (would be a determinism violation).
2. **Workflows that fetch the observation *after* `t_known_2` is published** — they get the corrected value. This is also correct.
3. **Workflows that need to be *retroactively recomputed* under `t_known_2`** — e.g., a P&L or regulatory report that was generated under `t_known_1` and now must be re-issued. This is **a new workflow run**, not a replay of the old one. The proposal does not say this.

The integrated proposal's L19 Snapshot is content-addressed by `t_observed_max, t_known_max`. A vendor restatement produces a *new* `snap_id`. This is correct mechanically. But the proposal does not specify the **trigger pattern** for retroactive recomputation:

- Is there a `RestatementOrchestratorWorkflow` that detects new `t_known` values for already-consumed `t_obs` and signals affected downstream workflows?
- Or is each downstream workflow expected to re-poll on its own cadence?
- Or is restatement-driven recomputation **out of scope** for the data layer and pushed to "regulatory reporting will reissue"?

Without an answer, the proposal allows three reviewers to read it three different ways. **This is BLOCKING because it is exactly the kind of cross-cutter where each leaf says "see the cross-cutter" and the cross-cutter does not exist.**

**Required mitigation:** The proposal must add a §4-equivalent subsection naming the bitemporal-restatement orchestration shape. My recommendation: a `RestatementWatchWorkflow` per `(observable_class, vendor)` that consumes the snapshot store's new-`t_known` events and fans out signals to subscribed downstream workflows; subscribers maintain their own subscription lists (workflow-state + `ContinueAsNew` carry). Each subscriber decides whether the restatement triggers a recomputation (e.g., regulatory report rerun) or is recorded for audit only. **The point is not that this specific design is right — the point is that the proposal cannot leave the question open.**

### 1.4 Category 4 — Pricing-DAG topology object — **ADDRESSED**

The Phase-2 temporal §6.4 + valuation companion's design (one workflow per unit, signal-driven graph traversal) is correct and sufficient. The integrated proposal §3 L13 carries this. No finding.

### 1.5 Category 5 — Kalman `ContinueAsNew` discipline — **UNMITIGATED MAJOR (M-2)**

The Phase-2 temporal §6.5 names the discipline: every `KalmanWorkflow` must `ContinueAsNew` every K certifications, carrying forward `(x_{t|t}, P_{t|t}, model_id, cdm_v, last_input_snapshot_set)`. Integrated proposal §3.4 L13 says "singleton long-running workflow per (target_object, model); `ContinueAsNew` on cadence."

This is **named but not bound.** The "cadence" K is not specified. The carry-forward set is named in the Phase-2 file but not in the integrated proposal. And the most dangerous failure mode is not addressed: **what happens when the KalmanWorkflow's history is so large that the next workflow task times out before the worker can replay**.

The proposal must specify:

**(a) An upper bound on history size triggering ContinueAsNew.** Not "on cadence" — a concrete event-count or wall-time bound. Industry experience: 10k events per workflow run is a reasonable ceiling for replay-tractability of state-bearing workflows. For Kalman, with maybe 50 events per certification (signal in, snapshot read, compute, gate, certify, publish), this is K ≈ 200 certifications.

**(b) The `ContinueAsNew` payload as a frozen schema.** Per FORMALIS theorem 2 (Replay Determinism Lifting), the ContinueAsNew payload IS the workflow's persistent state. If a future code version adds a field to the payload but a still-in-flight workflow continues with the old payload, the new field is silently default-initialised. For Kalman, this is the `P_{t|t}` corruption risk explicitly. The proposal needs a versioning rule: **KalmanWorkflow ContinueAsNew payload schema is bumped via `GetVersion` gates exactly like CDM payloads, never silently extended.**

**(c) Replay-cost bound on a fresh worker.** If a Kalman workflow has 9k events when its worker dies and a fresh worker picks up the new run, the new worker must replay the 9k events. If the replay-time exceeds `WorkflowTaskTimeout` (default 10s, max 60s), the worker is reaped, the task is retried, and the workflow is silently stuck. The proposal must specify a replay-cost test (CI-enforced) for the KalmanWorkflow.

### 1.6 Category 6 — SBL cascade-recall deadline propagation — **UNMITIGATED MAJOR (M-3)**

This is genuinely tricky. The Phase-2 temporal §6.6 names the issue and points to a `CascadeRecallSagaWorkflow` with compensation = buy-in. The integrated proposal §9.5 lists it.

The proposal does not specify the **deadline arithmetic**. A 2-business-day recall window subdivided across an N-deep cascade requires:

- An assignment policy: equal split? front-loaded (more time at the leaves)? back-loaded?
- A re-arming policy: when Charlie discharges to Bob at `t < deadline_charlie`, does Bob get the slack? (The buy-in compensation depends on this.)
- A failure-cascade policy: if Charlie defaults (compensation triggered), how is the deadline propagated upward? Bob's deadline is now strictly less than `deadline_bob_original` because Bob has lost time.

These are correctness questions Temporal cannot answer for the spec author. The proposal must rule on the deadline policy. My recommendation: **front-loaded with 0.5-business-day budget at each level, the residual at the leaf**. But the spec must pick one, write it, and identify a property test.

Additionally: cascade depth is not bounded. A pathological collateral chain could be 5+ deep. The proposal should specify a **maximum recall cascade depth N_max** (regulatory and operational; SFTR defaults to specific limits) and reject recalls deeper than that as a terminal saga error.

### 1.7 Categories not in the §6 list that the proposal also misses

**Cross-namespace orchestration.** The integrated proposal does not say whether a single Temporal namespace serves the entire Ledger or multiple namespaces (per legal entity, per region, per regulatory regime). This matters because:
- Cross-namespace workflow signals require Nexus or external SDK calls — both have higher latency than in-namespace.
- A multi-tenant regulatory regime (a global broker-dealer with US, EU, UK, APAC entities) typically requires namespace isolation.
- Cross-region active-active replication (Temporal Cloud's Multi-Cluster Replication) introduces conflict-resolution semantics for signals — which the spec does not mention.

This is an **UNMITIGATED MAJOR (M-4)**. The proposal must either (a) declare single-namespace scope and document the consequence (loss of regulatory isolation) or (b) specify the namespace topology.

---

## 2. Per-leaf idempotency-key collision-freedom under realistic input

The Phase-2 temporal §7 names 9 canonical idempotency-key shapes. Integrated proposal §3 L20 endorses them. I attack each shape under realistic adversarial input.

### 2.1 `unit_id = hash(canonical_serialise(terms_blob))`

**Risk: collision under canonical-serialisation drift.** `canonical_serialise` is a verb, not a function. Concretely: JSON canonicalisation (RFC 8785), Protobuf canonical encoding, or CBOR deterministic encoding all differ. The proposal does not specify which. If the serialisation algorithm is changed (CDM library uplift, Rosetta extension), a unit registered under v1 produces a different `unit_id` under v2 → silent re-registration possible.

**MAJOR (M-5).** The proposal must (a) name the canonical serialisation (RFC 8785 JCS, or CBOR with deterministic flag, or Protobuf with field-order pin), (b) version-pin the algorithm via L21, (c) write a property test that round-trips through CDM payload → canonical bytes → unit_id and asserts stability across CDM library uplifts within a major version.

**Minor:** for OTC trades, the proposal also accepts "CDM Trade key" as an alternative `unit_id` derivation (Phase-2 §7). These two derivations can produce the **same** key for different products if the CDM Trade key happens to be 32 bytes hex (it is). Lexical collision is impossible only if the namespaces are tagged. The proposal must mandate a namespace prefix: `unit_id = "U:" || version || ":" || hash(...)` or equivalent.

### 2.2 `tx_id = hash(source_lifecycle_event_id, source_workflow_run_id, attempt_seq=0)`

**This is wrong in subtle and dangerous ways.**

`source_workflow_run_id` is Temporal-assigned and changes on `ContinueAsNew`. If a lifecycle workflow `ContinueAsNew`s mid-flight and then re-emits the same `source_lifecycle_event_id` (because the event was signalled in the new run rather than the old), the `tx_id` differs across the two attempts despite being the *same* business transaction. This is a **layer-1 idempotency bypass**: the executor accepts a duplicate commit because the layer-1 key changed.

**BLOCKING (B-2).** `tx_id` must be derived **only** from data the lifecycle workflow can compute deterministically *across `ContinueAsNew` boundaries* and across worker process boundaries. The right shape is:

`tx_id = hash(business_event_id, attempt_seq=0)`

where `business_event_id` is the layer-2 idempotency key (from CDM) and `attempt_seq` is the workflow-internal retry counter (carried via ContinueAsNew). The `source_workflow_run_id` MUST NOT be in the hash. The Phase-2 doc has this wrong; the integrated proposal inherits the error.

`attempt_seq` further: if the lifecycle workflow retries the executor commit (e.g., on transient executor unavailability), `attempt_seq` advances. Each attempt has a distinct `tx_id`, which is correct because each attempt is a distinct commit attempt; the executor uses `tx_id` to dedupe. **But** if a non-deterministic retry happens (worker dies between commit and history persist), the same `attempt_seq` re-runs and the executor returns idempotent-success. This is correct as long as `attempt_seq` is incremented from workflow state, not from anything Temporal-managed.

### 2.3 `business_event_id`

The Phase-2 doc says: "Stable from upstream CDM payload; or `hash(event_intent, source_unit_id, t_logical)`."

The "or" is the problem. If the upstream CDM payload provides a stable ID, we use it; if not, we synthesise one. **What guarantees the synthesised ID does not collide with an upstream-provided one?** Nothing in the proposal.

**MAJOR (M-6).** The synthesised form must be namespace-tagged: `business_event_id = "BE:syn:" || hash(...)` vs. upstream `business_event_id = "BE:cdm:" || cdm_id`. Without this, two events from different sources can produce the same key.

Additionally: `t_logical` is the wall-clock time the event is intended to take effect (e.g., a coupon's pay-date). This is fine for events with a designated effective date, but for events triggered by a market observation (barrier breach) `t_logical` is the observation timestamp — and two distinct barrier breaches against the same underlying within the same observation could collide. The proposal needs `event_intent` to be granular enough: `event_intent = "barrier-breach:UB:put:strike=120"` (full barrier specification), not just `"barrier-breach"`.

### 2.4 `obligation_id = hash(source, type, registered_at_tx_id)`

**This is correct in principle but must specify "source".** If `source` is the lifecycle workflow's run_id, we have the same `ContinueAsNew` problem as `tx_id`. If `source` is a stable business identifier (e.g., the CDM `BusinessEvent` that registered the obligation), we are fine.

**MINOR (m-2).** The proposal must clarify that `source` is `business_event_id`, not `workflow_run_id`. Likely intent; not stated.

### 2.5 `signal.idempotency_token`

"Sender-generated UUID + timestamp." Fine. The risk is the receiver workflow's de-duplication state: the proposal says it is "carried via ContinueAsNew" in workflow state.

**MAJOR (M-7).** A workflow's signal-dedup set grows unboundedly with the number of signals received. A workflow that receives 10k signals has a 10k-element set in workflow memory and ContinueAsNew payload. Carrying this verbatim across ContinueAsNew is wasteful and eventually breaks the payload size limit (Temporal hard limit: 4 MB per payload). The proposal must specify:

(a) A retention horizon (signals older than X are dropped from the dedup set; replay of signals older than X is non-idempotent and treated as a terminal error).
(b) A compaction policy (Bloom filter for dedup, with false-positive risk that must be explicitly bounded).
(c) Or an out-of-workflow dedup table keyed by `idempotency_token` (activity to check/set), at the cost of an extra activity round-trip per signal.

Without this, every workflow that receives signals is a long-tail production failure.

### 2.6 `snap_id`

Content-addressed. Strong if the canonical serialisation is pinned (see 2.1). Same concern: the proposal does not specify which canonicalisation. **MAJOR (M-8), inherits M-5.**

### 2.7 `(unit_id, version_seq)` and `(workflow_id, run_id)` and `(calibrated_object_id, certification_timestamp, model_id)`

These are tuple keys; collision-free by construction provided the components are stable. No new findings.

### 2.8 Summary of idempotency-key findings

- 1 BLOCKING (B-2: `tx_id` includes Temporal-assigned `run_id`)
- 5 MAJOR (M-5 canonicalisation, M-6 BE namespace, M-7 signal dedup unbounded, M-8 inherits M-5; plus the unbounded affected-unit list under the calendar orchestrator from §1.1)
- 1 MINOR (m-2 obligation_id source)

---

## 3. Replay-determinism boundaries — clean or porous?

The proposal asserts replay determinism in many places. I attack the boundaries.

### 3.1 The "reads must be snapshot-pinned" rule (proposal §3 L8 UnitStatus)

Phase-2 §4.4 says reads are activity-mediated and memoised. Integrated proposal §3.2 L8 says "reads must be snapshot-pinned for replay determinism." **These are not the same statement.**

An activity-mediated read is memoised in workflow history → replay returns the same value. ✓
A snapshot-pinned read requires a snapshot ID resolved at workflow start (or at registration) → replay reads the snapshot store keyed on that ID. ✓

For UnitStatus, neither is sufficient. UnitStatus is **mutable per-unit**. If workflow W reads UnitStatus at time t1 (gets value v1, captured in history), and then continues running, and a later workflow task at t2 needs UnitStatus, the replay-correct behaviour is: the workflow re-executes the activity at t2 (gets v2, captured separately in history). So far so good.

But consider: workflow W reads UnitStatus at t1, decides `if status == LIVE then path A else path B`, takes path A, completes path A which involves several more reads. The history records:
- t1: read UnitStatus → v1 (LIVE)
- t1+ε: read UnitStatus → v1' (still LIVE)
- t1+2ε: read UnitStatus → v1'' (now SUSPENDED)

Path A computed under (v1, v1', v1'') is captured deterministically. Replay reproduces the path. ✓

But: if the workflow code is updated to add a fourth read between t1+ε and t1+2ε (e.g., a new validation), replay against the old history sees three reads in history but the new code wants four → determinism error → workflow stuck. This is the standard `GetVersion` problem; the proposal mentions `GetVersion` but does not name **which leaves require gates**. My finding:

**MAJOR (M-9).** The proposal must add a *replay-determinism gate inventory* — for each leaf that admits read activities inside lifecycle workflows (L8, L9, L4 calendar reads, L10 raw obs (only via snap_id), L13 calibrated, L23 capability, L7 policy), the proposal must specify which code paths require `GetVersion` gates. A blanket "use GetVersion when needed" is a license to introduce silent determinism bugs on every code change.

### 3.2 The "valuation FSM consumes via Activity" rule (proposal §3.4 L15)

The valuation document specifies a per-unit FSM that consumes ValuationRecord. Phase-2 temporal §3.4 says "Activity for FSM consumption."

The boundary question: **is the FSM state itself a Temporal workflow's state, or is it a separate store?**

If the FSM state is workflow state (long-running per-unit `ValuationFSMWorkflow`), then transitions are workflow code and consumption is replayable. ✓
If the FSM state is in a separate store (e.g., the UnitStatus L8), then the workflow reads it via activity, decides the transition, and writes back via activity. **The decision logic in the workflow is replayed deterministically only if the read-then-write is single-attempt-or-idempotent.** A retry of the write activity could see stale FSM state on retry → non-determinism.

The proposal does not say which. **MAJOR (M-10).** This must be ruled.

### 3.3 The "PnL-explain residual drives FSM transition" path (proposal §3.4 L15)

PnL-explain PASS/FAIL is a deterministic computation (Phase-2 §3.6). Its output drives FSM transition T5 vs T6. The transition itself is workflow code → captured in history → replays correctly. ✓

But: the *threshold* for PASS/FAIL is L7 Policy. Policy is bitemporally pinned at unit registration (per the proposal's reconciliation of V9). So the threshold used in the comparison must be **the threshold as-of the unit's registration time**, not the current threshold. The proposal does not say. **MINOR (m-3) escalates to MAJOR if the policy is changed mid-flight.** Add to the replay-determinism risk register.

### 3.4 Cross-workflow signals carrying ValuationRecord IDs (proposal §3.4 L15)

The producer workflow publishes a `ValuationRecord` and signals subscribers with the `valuation_record_id`. Subscribers fetch via activity. ✓

Risk: **signal ordering**. Two near-simultaneous publications produce two signals into a subscriber. Temporal does not guarantee strict signal ordering across senders. The subscriber processes them in arrival order, which may differ from the publication order. If the subscriber's logic depends on monotonic ordering (e.g., "process the latest valuation first, ignore earlier"), this is a bug.

**MAJOR (M-11).** The proposal must specify the ordering discipline at signal receipt. Recommended: every publication carries a producer-monotonic `cycle_seq` in the signal payload; the subscriber sorts by `cycle_seq` before processing. The proposal §3.4 L15 says `cycle_seq` is in the idempotency key but does not say it is in the signal.

### 3.5 The KalmanWorkflow's dependency on input snapshot IDs (proposal §3.4 L13)

Phase-2 §3.2 says "Kalman is deterministic" given prior posterior + input observation snap_ids. ✓

But: the KalmanWorkflow's input is the *set* of new observations since the last certification. How is the set assembled? If by polling the snapshot store via activity, the set captured at time t1 is correct under replay (activity result memoised). If by signal subscription (the snapshot store signals the Kalman workflow on each new observation), signal arrival is non-deterministic at the millisecond level, but Temporal captures arrival order in history → replay reproduces. ✓

Caveat: the subscription must be a workflow-managed subscription (signal channel), not an external pub-sub callback. The proposal does not specify. **MINOR (m-4).** Specify "signals from snapshot-store-watch workflow → Kalman" rather than implicit pub-sub.

### 3.6 The replay-determinism risk register

The Phase-2 §8 lists 7 items. The integrated proposal §9.5 inherits the list. With my findings above, the register should be expanded to include:

- M-5 canonical serialisation algorithm pin
- M-9 GetVersion gate inventory per leaf
- M-10 valuation FSM state location
- M-11 signal ordering discipline
- m-3 policy threshold pinning at unit registration
- m-4 Kalman input subscription channel

**Updated register: 13 items, not 7.**

---

## 4. Saga compensation pattern for L16 obligations — correct?

The Phase-2 temporal §4.6 + §4.7 + integrated proposal §3.5 L16 describe:

- `ObligationWorkflow` per obligation, spawned on registration.
- Durable timer for deadline.
- Discharge signal completes the workflow.
- Timer-fire-without-discharge → compensation activity.

This is the standard Temporal saga pattern. I attack it under realistic failure modes.

### 4.1 The compensation activity must itself be a workflow

The proposal says "compensation activity invoked." This is wrong for non-trivial compensations. Examples:

- A failed settlement obligation triggers compensation = buy-in. Buy-in is itself a multi-step process: notify counterparty, source replacement assets, instruct settlement, confirm, record. This is a workflow, not an activity.
- A failed manufactured-payment obligation triggers compensation = under-withhold + true-up. Multi-step, with deadlines of its own.
- A failed regulatory-report obligation triggers compensation = escalation → manual review → potential resubmission. Long-running.

**MAJOR (M-12).** The proposal must specify that **non-trivial compensations are child workflows, not activities**. The ObligationWorkflow's timer-fire branch starts a `CompensationWorkflow` (typed by obligation kind) as a child, with its own deadline budget, its own retry policy, and its own discharge contract. The current shape collapses this.

### 4.2 Compensation failure handling

If the compensation itself fails (e.g., buy-in fails because there is no liquidity), what happens? The proposal does not say. In every saga literature, this is the "compensation failure escalation" question.

The Temporal-correct answer is: **the compensation workflow has its own terminal-failure contract that, on exhaustion, signals a higher-order escalation workflow** (operations queue, regulatory reporting, etc.). The point is that there must be a finite tower: compensation → escalated compensation → manual ops → terminal default. **MAJOR (M-13).** The proposal must specify the top of the tower for each compensation kind.

### 4.3 Idempotent discharge under retries

The discharge signal carries `idempotency_token` (Phase-2 §4.7). The workflow's signal-dedup set (covered above, M-7) handles duplicate discharges.

But: what if a discharge signal arrives **after** the deadline timer has fired and compensation has begun? This is a race condition. Realistic: counterparty's confirmation arrives 100ms after timer-fire; the ObligationWorkflow has already kicked off the compensation child workflow.

**BLOCKING (B-3).** The proposal does not specify the late-discharge policy. Three options:
- Reject the late discharge (the obligation has compensated; the late discharge is logged but ignored). This is the "deadline is sacrosanct" answer.
- Cancel the compensation and accept the discharge. This is racy and risks two concurrent state-changes (e.g., the buy-in has already settled when the original discharge arrives → now we have over-collateralisation).
- Queue the late discharge until the compensation completes; reconcile at compensation-completion. This is the most correct but most complex.

**The proposal must rule** because each obligation kind may want a different policy. SBL recall: deadline is sacrosanct (regulatory). Settlement: cancel-compensation may be acceptable. Regulatory submission: queue-and-reconcile.

### 4.4 Compensation determinism vs. workflow state

The compensation handler (call it `compensate(obligation_state)`) must be a pure function of obligation state for replay. If the compensation handler reads UnitStatus (mutable), it must do so via activity (per L8). If the compensation handler queries L9 PositionState (as buy-in must, to know how much to buy back), it must do so via activity at the moment of compensation, captured in history. ✓ if disciplined; ✗ if not.

The proposal does not require the compensation handler to be a workflow with its own activity-mediated reads. **MINOR (m-5) escalates to MAJOR via M-12.** Once compensation is a workflow (M-12), this is automatic; until then, the proposal allows compensation activities that read mutable state directly → silent determinism bugs.

### 4.5 Obligation deadline relative to workflow timeout

A 30-year bond's coupon obligation has a 6-month deadline. The ObligationWorkflow has a timer for 6 months. Temporal supports timers of any duration, but worker uptime must span the timer (workers do not need to be running for the timer to fire — the server fires it — but they must be available to deliver the timer-fired event to the workflow).

`WorkflowExecutionTimeout` for the ObligationWorkflow must be longer than the deadline + compensation budget. The proposal does not specify. **MINOR (m-6).** Specify `WorkflowExecutionTimeout` policy per obligation kind: deadline + 5x compensation horizon, or `unlimited` with a structural-bound retention policy from L7 (Phase-2 temporal §6 already mentioned this for Kalman; same applies here).

### 4.6 Summary of saga findings

- 1 BLOCKING (B-3: late-discharge policy)
- 2 MAJOR (M-12 compensations are workflows; M-13 compensation-failure tower)
- 2 MINOR (m-5, m-6)

---

## 5. Other issues found incidentally

### 5.1 Worker fleet sizing and task-queue partitioning — **MAJOR (M-14)**

The proposal does not specify the task-queue topology. Realistic Temporal deployments require:
- Separate task queues for workflow workers vs activity workers (they scale differently).
- Separate task queues per activity class with distinct latency characteristics (snapshot-build is CPU-heavy; signature-verify is fast; settlement-instruction-emit is I/O-bound).
- Sticky-execution caches sized appropriately.

Without explicit task-queue architecture, the deployment will mix workflow scheduling latency with activity execution latency and produce unpredictable tail latency. **The proposal must include a task-queue topology specification** (probably as part of L24 OrchestrationState or as a new sub-spec).

### 5.2 Heartbeat policy for long-running activities — **MAJOR (M-15)**

The proposal mentions heartbeats for snapshot construction (§3.1) and Kalman compute (§3.2) and MC pricing (§3.4 L15). It does not mention heartbeats for:
- Settlement confirmation wait (L12 — can be hours)
- Locate confirmation wait (L11 — can be hours)
- Regulatory ack wait (L11 — can be days)
- Multi-vendor CA reconciliation (L13/L11 — can be hours)

Each of these is a long-running activity (or should be a long-running workflow with internal timer; the proposal does not say which). Without heartbeating, a worker death goes undetected until `StartToCloseTimeout` fires. The proposal §4.9 says "missing heartbeat = silent worker-death undetected" but does not enforce it.

**Required mitigation:** A heartbeat-policy table per activity class. Or, preferably, a re-architecting of the wait-for-external-confirmation pattern to use a *signal-driven workflow* (the workflow waits with a timer and a signal channel; no long-running activity needed). The latter is the Temporal-idiomatic answer.

### 5.3 Workflow versioning posture — **MINOR (m-7)**

The proposal mentions `GetVersion` and `ContinueAsNew` but does not specify the deprecation policy for old workflow versions. When a Kalman model is retired, the corresponding `KalmanWorkflow` must terminate cleanly (final ContinueAsNew → final certification → graceful close). The proposal does not say. Add a workflow lifecycle section.

### 5.4 Cross-workflow query patterns — **MINOR (m-8)**

The proposal frequently uses "Query for ops dashboards" (§3.1, §3.4 L15, §3.5 L16). Temporal queries are synchronous; they bypass history but require the workflow's worker to be available. For ops dashboards covering 100k+ workflows, query throughput is a constraint. The proposal should specify:
- Whether dashboards query workflows directly or read from search attributes.
- If queries are used, query rate limits per workflow.

---

## 6. Findings summary

| ID | Class | Title | Section |
|----|-------|-------|---------|
| B-1 | BLOCKING | Bitemporal-restatement orchestration shape unspecified | 1.3 |
| B-2 | BLOCKING | `tx_id` includes Temporal-assigned `run_id` (idempotency bypass on ContinueAsNew) | 2.2 |
| B-3 | BLOCKING | Late-discharge race policy unspecified | 4.3 |
| M-1 | MAJOR | Calendar orchestrator unbounded state + fan-out + retroactive-timer policy | 1.1 |
| M-2 | MAJOR | Kalman ContinueAsNew cadence/payload schema/replay-cost not bound | 1.5 |
| M-3 | MAJOR | SBL cascade-recall deadline arithmetic unspecified | 1.6 |
| M-4 | MAJOR | Namespace topology / cross-namespace orchestration unspecified | 1.7 |
| M-5 | MAJOR | Canonical serialisation algorithm not pinned for `unit_id`/`snap_id` | 2.1 |
| M-6 | MAJOR | `business_event_id` namespace tagging missing | 2.3 |
| M-7 | MAJOR | Signal idempotency-token dedup set unbounded | 2.5 |
| M-8 | MAJOR | `snap_id` canonicalisation (inherits M-5) | 2.6 |
| M-9 | MAJOR | `GetVersion` gate inventory missing | 3.1 |
| M-10 | MAJOR | Valuation FSM state location unspecified (workflow state vs external) | 3.2 |
| M-11 | MAJOR | Signal-ordering discipline missing for ValuationRecord publication | 3.4 |
| M-12 | MAJOR | Compensations as activities, not workflows | 4.1 |
| M-13 | MAJOR | Compensation-failure escalation tower unspecified | 4.2 |
| M-14 | MAJOR | Task-queue topology + worker-fleet partitioning unspecified | 5.1 |
| M-15 | MAJOR | Heartbeat policy missing for long-wait activities; signal-driven pattern preferred | 5.2 |
| m-1 | MINOR | Snapshot-store durability assumption (C-A11) not named | 1.2 |
| m-2 | MINOR | `obligation_id` source clarification | 2.4 |
| m-3 | MINOR | Policy threshold pinning at unit registration | 3.3 |
| m-4 | MINOR | Kalman input subscription channel specification | 3.5 |
| m-5 | MINOR | Compensation determinism (subsumed by M-12) | 4.4 |
| m-6 | MINOR | Obligation `WorkflowExecutionTimeout` policy | 4.5 |
| m-7 | MINOR | Workflow-version deprecation policy | 5.3 |
| m-8 | MINOR | Query rate limit / dashboard-via-search-attributes policy | 5.4 |

**Tally: 3 BLOCKING, 15 UNMITIGATED MAJOR, 8 MINOR.**

---

## 7. Grade

**C-.**

Rationale:
- The Phase-2 temporal synthesis is structurally correct: the three-class taxonomy is right, the activity/workflow boundary is drawn correctly for the leaves it describes, and the snapshot-pinning discipline for observation reads is the right answer.
- However: the proposal **names** awkward-fit categories without **bounding** them, and the integrated proposal §9.5 explicitly defers them to Phase-3 ruling.
- Three BLOCKING issues mean convergence cannot be claimed at this round. B-2 in particular (tx_id includes run_id) is a **layer-1 idempotency soundness bug** that, undetected, would produce silent double-commits in production under a worker-restart-during-ContinueAsNew scenario. This is exactly the kind of subtle correctness violation that Temporal's discipline is supposed to prevent and that the spec is supposed to make unrepresentable.
- The 15 UNMITIGATED MAJORs are not individually fatal but collectively indicate the proposal trusts the data-team-specialist (Phase-2 temporal author) to have specified the discipline at a level of detail the document does not in fact reach. The integrated proposal compresses the temporal specialist's work without fully internalising its consequences.
- The MINOR class is largely about details the spec should pick up before going to a LaTeX target.

**Convergence verdict: NOT CONVERGED.** Resolve B-1, B-2, B-3 before proceeding. Address the 15 MAJORs in proposal_v2 with concrete mechanisms (not labels). Disposition the 8 MINORs with documented accept/reject/defer.

Re-issue as `proposal_v2.md` with explicit answers to each finding ID. I will re-review.

---

*End of Phase 3 Round 1 Temporal adversarial review.*
