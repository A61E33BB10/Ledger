# Phase 2 — Temporal Workflow Synthesis for the Data Layer (v2)

**Author:** Arjun Mehta (Temporal.io discipline)
**Phase:** 2, Revision Round 2 (response to R1 adversarial review of v1)
**Date:** 2026-04-30
**Supersedes:** `phase2/temporal.md` (v1, 2026-04-29).
**R1 inputs read:**
- `phase3/round1/R1_consolidated_findings.md` (T8, T9, T11, T12 + Singletons 3, 5, 13)
- `phase3/round1/temporal.md` (own-discipline review by independent instance: 3 BLOCKING + 15 MAJOR + 8 MINOR)
- `phase2/temporal.md` (v1)

---

## 0. Changes from v1

This revision is not a polishing pass. v1 named six awkward-fit categories without bounding three of them, declared an idempotency-key algebra that contained a layer-1 soundness bug, and treated compensation as an activity. v2 addresses each finding by ID. Convergence requires concrete mechanisms, not labels, so I have replaced labels with mechanisms throughout.

**Changes by finding (all R1 IDs from `phase3/round1/temporal.md` unless prefixed):**

| Finding (R1 own-discipline) | Change in v2 | Section |
|---|---|---|
| **B-1** Bitemporal-restatement orchestration unspecified | New §6 `RestatementWatchWorkflow` shape ruling | §6 |
| **B-2** `tx_id` includes Temporal `run_id` | Corrected formula: `tx_id = hash(business_event_id, attempt_seq)` | §1, §7 |
| **B-3** Late-discharge race unspecified | Per-obligation-kind policy table | §8.3 |
| **M-1** Calendar orchestrator state/fan-out/timer policy | Bounded state + paginated unit set + mode-1 pin | §6, §9.1 |
| **M-2** Kalman `ContinueAsNew` cadence/payload schema | K=200 ceiling + frozen schema + replay-cost CI | §9.5 |
| **M-3** SBL cascade-recall deadline arithmetic | Front-loaded 0.5-bd budget per level + N_max=5 | §9.6 |
| **M-4** Namespace topology unspecified | Single global namespace + entity isolation rule | §11 |
| **M-5/M-8** Canonical serialisation not pinned | RFC 8785 JCS for JSON; Protobuf canonical for binary | §1, §3.1 |
| **M-6** `business_event_id` namespace tagging | All keys carry namespace prefix `BE:cdm:` / `BE:syn:` | §7 |
| **M-7** Signal dedup unbounded | Bounded set + retention + out-of-workflow dedup table | §10 |
| **M-9** `GetVersion` gate inventory | Per-leaf gate inventory in §12 | §12 |
| **M-10** Valuation FSM state location | FSM is workflow state, not external store | §3.4 |
| **M-11** Signal ordering for ValuationRecord | `cycle_seq` in payload; receiver sorts | §3.4, §13 |
| **M-12** Compensations as workflows | All non-trivial compensations are child workflows | §8.1 |
| **M-13** Compensation-failure tower | Three-tier tower with terminal escalation | §8.2 |
| **M-14** Task-queue topology unspecified | Topology specified | §11 |
| **M-15** Heartbeat policy + signal-driven wait | Signal-driven pattern preferred for waits >5min | §13 |
| **R1-T8** L21 canonicalisation algorithm | Pinned RFC 8785 JCS + Protobuf canonical with field-tag pin | §1.4 |
| **R1-T8** Per-leaf idempotency-key classification | Content-addressed vs mint-on-arrival per leaf | §7.4 |
| **R1-T8** Drop wall-clock from L13 key | `(calibrated_object_id, model_id, input_snap_id, attempt_seq)` | §7.3 |
| **R1-T8** Drop `version_seq` from L1 key | Producer-supplied; L1 key is content-addressed | §7.2 |
| **R1-T9** RestatementWatchWorkflow specification | Full subscription discipline + paginated `ContinueAsNew` | §6 |
| **R1-S5** Calendar amendment cascade | Folded into RestatementWatchWorkflow generalisation | §6 |
| **R1-S13** Saga compensation pattern | Compensation tower §8 — child workflows with terminal escalation | §8 |
| **R1-S3** Late-discharge race | Per-kind policy + reasoning + property test | §8.3 |
| **R1-T9.5** Awkward-fit rulings | Per-category ruling: Temporal / out-of-Temporal / discipline | §9 |
| **m-1 to m-8** | Resolved or accepted — see §14 | §14 |

**One v1 claim explicitly retracted.** v1 §7's `tx_id = hash(source_lifecycle_event_id, source_workflow_run_id, attempt_seq=0)` is **wrong** and produces silent double-commits on `ContinueAsNew`. I caught this only because the R1 reviewer (a separate instance) flagged it. The corrected formula is in §7.2 and is binding.

---

## 1. Notation, conventions, and the canonicalisation pin

### 1.1 Workflow / activity / signal / query terminology

I follow Temporal SDK terminology throughout. **Workflow** = orchestration code, deterministic, replayable. **Activity** = side-effecting unit of work, retryable. **Signal** = asynchronous external input to a workflow. **Query** = synchronous read of workflow state without mutation. **Update** = request-response interaction (mention only; v11.0 does not use Updates in the data layer).

### 1.2 Three-class taxonomy

Carries from v1:
- **Definitions** ($\mathcal{F}_{\text{Defn}}$) — append-only versioned. ProductTerms, Reference, Party, legal agreements, calendars.
- **Observations** ($\mathcal{F}_{\text{Obs}}$) — bitemporal append-only. Raw market, calibrated, fixings, CA announcements.
- **Effects** ($\mathcal{F}_{\text{Eff}}$) — append-only by construction. Moves, transactions, BusinessEvents, obligations.

### 1.3 Identifiers used throughout

- `cdm_v` — pinned CDM version captured at ingest (axis of L21).
- `snap_id` — content-addressed snapshot identifier (see §1.4).
- `tx_id` — executor commit identifier; **layer-1** of three-layer idempotency.
- `business_event_id` — namespace-tagged CDM event identifier; **layer-2**.
- `obligation_id` — workflow-ID-bearing obligation identifier.
- `wf_id` — Temporal workflow ID, deterministic from business key.
- `run_id` — Temporal-assigned per-run ID. **Never used in business-layer keys.**

### 1.4 Canonicalisation pin (resolves R1-T8, M-5, M-8)

The serialisation algorithm used to compute content-addressed identifiers is **pinned** at the L21 axis `canonicalisation_version` (new axis added in this revision; tracked alongside `cdm_version`, `model_version`, `component_version`, `refdata_version`).

**Two algorithms, two payload classes:**

1. **JSON-bearing payloads** (CDM JSON, attestation envelopes, signal payloads): **RFC 8785 (JSON Canonicalization Scheme, JCS)**. Specifically the I-JSON profile with NFC Unicode normalisation, sorted-key dictionaries, and the JCS number-formatting rules.

2. **Protobuf-bearing payloads** (gRPC ingress, executor commit binary protocol): **Protobuf canonical encoding** with field-tag order ascending, no unknown fields permitted, and explicit zero-suppression rules (default values omitted).

A third option (CBOR per RFC 8949 §4.2.1 with deterministic flag) was considered but rejected: the data-layer payloads are already either JCS-friendly JSON (CDM) or Protobuf (executor wire), and adding a third canonicalisation creates a hash-collision-test surface that buys nothing.

**`canonicalisation_version` enum.**
```
canonicalisation_version ∈ {
    "JCS-RFC8785-v1",      // initial pin
    "PROTOBUF-CANONICAL-v1",
    // future versions append; never repurpose
}
```
**The L21 axis is bumped only with a documented migration test** (round-trip a corpus of 10k CDM payloads through old and new canonicalisation; assert delta is zero or fully accounted by the migration). A bump is a CDM-uplift-equivalent event for replay-determinism purposes.

**Why this is load-bearing.** Every content-addressed identifier (`unit_id`, `snap_id`, `tx_id`, `business_event_id` when synthesised, `obligation_id`, `attest_id`, `prev_hash`) is computed from canonicalised bytes. Two implementations that disagree on canonicalisation produce two different IDs for the same logical payload — this is the cross-implementation-replay correctness hole that v1 left open.

### 1.5 Six-field schema per leaf (carries from v1)

Per leaf, I specify: ingress shape, idempotency key (with classification — see §7.4), replay-determinism boundary, failure/retry/heartbeat policy, downstream split, versioning posture.

---

## 2. Class **Definitions** — append-only versioned

This section carries from v1 with two corrections: (i) the L1 idempotency key (drop `version_seq`); (ii) calendar amendment policy folded into RestatementWatchWorkflow (§6). I do not re-list every leaf — see v1 for unchanged entries (2.5 Party, 2.6 Legal, 2.7 SSI, 2.8 RegRulesets, 2.9 Tax). What changed:

### 2.1 ProductTerms (revised)

- **Idempotency key (corrected).** `unit_id = "U:" || canonicalisation_version || ":" || hash_jcs(canonical_terms_blob)` — content-addressed. **`version_seq` is producer-supplied and is not in the key.** Concurrent submission of the same TermsVersion blob produces the same `unit_id`; the executor's StateDelta layer rejects on duplicate by `unit_id`. Version sequence is a *property* of the unit, not a *key*. (Resolves R1-T8 L1 key.)
- **Replay boundary, failure, downstream, versioning:** unchanged from v1.

### 2.4 Calendar definitions (revised)

- **Bitemporal mode pinned to mode-1 (resolves R1-T12, M-1c).** A retroactive holiday declaration produces a *new* bitemporal record `(calendar_id, t_published_new, t_known_new)` but does **not invalidate prior schedules already pinned at unit registration**. The lifecycle workflow's resolved schedule wins; the new calendar applies only to schedules resolved after `t_known_new`. This pin is what preserves S3 (time-translation invariance).
- **Operational consequence.** A timer that has already fired under the old calendar stays fired. The compensation chain question (M-1c option ii) does not arise — we have ruled it out.
- **Forward-looking schedules under amendment.** For schedules not yet fully resolved (e.g., a 30-year bond's coupon dates beyond the current year), the lifecycle workflow's `RegisterAffectedUnit` is signalled by the `RestatementWatchWorkflow` (§6); the workflow chooses to recompute forward dates only.
- **The `CalendarUpdateOrchestratorWorkflow` becomes a specialisation of `RestatementWatchWorkflow`.** See §6.

---

## 3. Class **Observations** — bitemporal append-only

Carries from v1, with three changes: (i) snapshot store durability (§3.1); (ii) Kalman ContinueAsNew explicit cadence and frozen payload (§3.2 + §9.5); (iii) ValuationRecord signal carries `cycle_seq` and FSM state location (§3.4).

### 3.1 Raw market observable (revised)

- **Snapshot store durability (resolves m-1).** The snapshot store MUST be multi-region replicated (or use a durable object-store equivalent with cross-region replication — S3 with CRR, GCS with multi-region, etc.). The replication is a precondition of replay determinism: a snapshot referenced in workflow history but unreadable on replay produces a non-recoverable deterministic-read failure. Add **C-A12** to the conditional guarantee list (named owner: head of platform engineering; detection signal: snapshot-store read latency p99 > 2× region-local baseline; compensating action: reroute reads to replica region; blast radius: any workflow that captured the affected `snap_id`).

### 3.2 Calibrated parameters (revised)

- **`ContinueAsNew` cadence pinned (resolves M-2, R1 awkward-fit Cat-5).** Every `KalmanWorkflow` MUST `ContinueAsNew` when **either** of these triggers fires:
  - **Event-count trigger:** workflow history reaches **8000 events** (below the 10k industry-tractability soft ceiling).
  - **Wall-time trigger:** 30 days since last `ContinueAsNew`.
- **Carry-forward payload (frozen schema).** The `ContinueAsNew` payload is the typed `KalmanContinuePayload` v1 (versioned schema; see §12). Mandatory fields: `(x_t_t, P_t_t, model_id, cdm_v, canonicalisation_version, last_input_snap_id_set, attempt_seq, certifications_in_run)`. Adding a field requires a `GetVersion` gate (§12). `P_t_t` is the posterior covariance — **forgetting it is silent posterior corruption**.
- **Replay-cost CI test.** Per-PR CI test: synthesise a `KalmanWorkflow` with 8000 events; replay against a fresh worker; assert replay completes within 60s (one `WorkflowTaskTimeout` budget). Replay-time exceeding budget = build failure.

### 3.4 ValuationRecord (revised) — FSM location ruling

- **The valuation FSM is a workflow state, not an external store (resolves M-10).** A long-running `ValuationFSMWorkflow` per unit holds the FSM state in workflow memory; transitions are workflow code. Reads of `UnitStatus`, `ValuationRecord`, and Greeks are activity-mediated and memoised. This is the only configuration that preserves replay-determinism for the FSM transition logic.
- **Why not external store?** External-store FSM requires read-modify-write with idempotency, which under retry can see stale state and produce non-deterministic transitions. The complexity tax is not worth the marginal scalability win.
- **`ContinueAsNew` for ValuationFSMWorkflow.** Same cadence as Kalman: 8000 events or 30 days. Carry-forward payload: `(unit_id, current_state, last_valuation_record_id, last_valuation_quality, last_pnl_explain_status, model_id, cdm_v, canonicalisation_version, attempt_seq)`.
- **Signal payload from PricingWorkflow carries `cycle_seq` (resolves M-11).** The signal envelope to subscribers is `(valuation_record_id, cycle_seq, producer_workflow_id, t_published)`. Receivers sort by `cycle_seq` per producer before applying. Out-of-order signals are queued in a small per-producer buffer (configurable, default 16 slots — sized so that a producer's burst cannot overwhelm). See §13.1 for the receive pattern.

---

## 4. Class **Effects** — append-only by construction

Carries from v1 with the corrected `tx_id` formula (§7.2) propagated throughout. The leaf entries 4.1–4.10 in v1 stand; the only substantive correction is replacing `tx_id` everywhere with the new formula.

---

## 5. Cross-cutting: Identity envelope and provenance edges

Unchanged from v1. Crypto verification is activity-confined; envelope's `source_signature` is part of the snapshot's content hash; key rotation is a `SourceKeyRotationWorkflow` Signal.

---

## 6. RestatementWatchWorkflow — bitemporal-restatement orchestration ruling (resolves B-1, R1-T9, R1-S5)

This section did not exist in v1. It is the most consequential addition of v2. The R1 review identified the bitemporal-restatement orchestration as a cross-cutter that no leaf can resolve in isolation; this section provides the ruling.

### 6.1 Shape

One **`RestatementWatchWorkflow`** per `(observable_class, vendor)` tuple, where `observable_class ∈ {raw_market, calibrated, fixing, corp_action, calendar, party_lei, ssi, tax_form}`. Vendor enumeration per `observable_class` is L21-pinned. Workflow ID format: `restate-watch:{observable_class}:{vendor}`.

Each workflow:
1. Subscribes via signal channel to "new-`t_known`-for-prior-`t_obs`" events from the snapshot store.
2. Holds a **subscriber list** in workflow state (paginated; see §6.4): each entry is `(subscriber_workflow_id, subscription_filter, last_acked_t_known)`.
3. On a new restatement event, fans out signals to matching subscribers, capped by a semaphore activity (§9.1).
4. Tracks acks; retries un-acked subscribers per a backoff policy.
5. `ContinueAsNew` per §6.4.

### 6.2 Subscription discipline

A downstream workflow that consumes an observable (e.g., a regulatory-report workflow that valued a position under `(t_obs=2026-04-01, t_known=2026-04-02)`) registers as a subscriber **at the moment of consumption**, via a signal to its `RestatementWatchWorkflow` carrying `(subscriber_workflow_id, subscription_filter)`. The subscription filter is a typed predicate (`{observable_id, t_obs_range}`) — a vendor restatement matches the filter if the restated `(observable_id, t_obs)` overlaps.

A subscriber chooses one of three stances on restatement:
- **Audit-only.** Logged, not acted upon (e.g., historical PnL reports already published).
- **Recompute-as-new-run.** A new workflow run is started with the corrected snapshot (e.g., regulatory report rerun under `(t_obs, t_known_2)`). The original run is **not replayed under the new value** — that would violate determinism.
- **Compensate-and-republish.** The original run's effect is reversed via a compensation workflow (§8) and a new run is started.

The stance is encoded in the subscription filter and is per-(subscriber, observable_class) policy. The `RestatementWatchWorkflow` does not decide; it routes.

### 6.3 Deadline propagation

A regulatory restatement may carry a deadline (e.g., "MiFIR re-submission required within 5 business days of restatement publication"). The signal payload carries `restatement_deadline`. Subscriber workflows that take stance "recompute-as-new-run" inherit a derived deadline `(restatement_deadline - 0.5 business day)` so the orchestration completes ahead of the regulatory cliff. The 0.5-business-day buffer is the same shape used for SBL cascade (§9.6); it is L21-pinned at the `compensation_buffer_bd` axis.

### 6.4 Cascade fan-out and `ContinueAsNew` discipline

**Subscriber list paginated.** The list is materialised in an external durable store (the same L19 snapshot store, keyed by `restate-watch:{observable_class}:{vendor}:subscribers:{page_id}`); the workflow holds only `subscriber_page_set: Set[page_id]`. Fan-out activity reads pages; the workflow does not. This bounds workflow history growth.

**`ContinueAsNew` cadence:** 8000 events or 30 days, whichever first. Carry-forward payload `RestatementWatchContinuePayload`:
```
{
    observable_class, vendor,
    canonicalisation_version,
    cdm_v,
    subscriber_page_set: Set[page_id],
    last_processed_restatement_seq: int,
    pending_acks: Map[subscriber_workflow_id, last_send_time],
    backoff_state: Map[subscriber_workflow_id, attempt_count],
    attempt_seq: int,
}
```

**Cascade fan-out rate-limiting.** A semaphore activity caps in-flight fan-outs at `restate_fanout_concurrency_limit` (L21-pinned, default 256). The workflow's fan-out loop awaits the semaphore before signalling each subscriber.

### 6.5 Retroactive recomputation contract

The proposal does **not** specify per-subscriber recomputation logic — that is the subscriber's responsibility. The proposal specifies only the *delivery contract*: at-least-once signal delivery, idempotency-token-deduped, with an out-of-workflow ack table (§10.2). Whether the subscriber re-computes is its policy.

### 6.6 Calendar amendments via RestatementWatchWorkflow

The v1 `CalendarUpdateOrchestratorWorkflow` is folded into `RestatementWatchWorkflow` for `observable_class = calendar`. This eliminates the ad-hoc orchestrator. Calendar restatements behave identically to vendor restatements: subscribers (lifecycle workflows) register at unit registration time; on a new calendar publication, matched subscribers are signalled; each subscriber decides recompute vs audit-only via the bitemporal mode-1 rule (forward schedules recomputed; already-fired timers untouched).

---

## 7. Idempotency-key algebra (revised, soundness bug fixed)

### 7.1 The corrected key set

Nine canonical key shapes; v1's `tx_id` shape was wrong. Revised:

| Key | Construction | Class | Where enforced |
|---|---|---|---|
| `unit_id` | `"U:" || canonicalisation_version || ":" || hash_jcs(canonical_terms_blob)` | content-addressed | RegisterUnitWorkflow workflow ID; executor StateDelta dedup |
| `tx_id` | **`hash_jcs(business_event_id, attempt_seq)`** | mint-on-arrival (per attempt) | Executor commit dedup |
| `business_event_id` | `"BE:cdm:" || cdm_event_id` (upstream) OR `"BE:syn:" || hash_jcs(event_intent, source_unit_id, t_logical)` | content-addressed (upstream) / mint-on-arrival (synth) | Lifecycle workflow processed-set; out-of-workflow dedup table (§10) |
| `obligation_id` | `hash_jcs(business_event_id, obligation_kind, obligation_seq)` | content-addressed | ObligationWorkflow workflow ID |
| `signal.idempotency_token` | Sender-generated UUID (RFC 4122 v4) + attempt_seq | mint-on-arrival | Out-of-workflow dedup table (§10) |
| `snap_id` | `"S:" || canonicalisation_version || ":" || hash_jcs(observable_set, source_set, t_observed_max, t_known_max, schema_v)` | content-addressed | Snapshot store |
| `(unit_id, version_seq)` | producer-supplied; not a hash key | mint-on-arrival | Append-only invariant |
| `(workflow_id, run_id)` | Temporal-managed | mint-on-arrival | Temporal cluster only — **never in business-layer keys** |
| `(calibrated_object_id, model_id, input_snap_id, attempt_seq)` | composite | content-addressed | Calibration store dedup |

### 7.2 The corrected `tx_id` (resolves B-2)

```
tx_id = hash_jcs(business_event_id, attempt_seq)
```

`business_event_id` is layer-2 idempotency from CDM (or namespace-tagged synthesised — §7.3). `attempt_seq` is workflow-internal counter, **incremented in workflow code**, carried via `ContinueAsNew`. The `run_id` MUST NOT be in any hash. v1 had this wrong.

**What this fixes.** Under v1's formula, a workflow that `ContinueAsNew`-ed mid-flight and re-emitted the same business event in the new run computed a different `tx_id` (because `run_id` differed across runs) → the executor accepted both as distinct → silent double-commit. Under v2's formula, the `run_id` is gone; the `tx_id` is identical across `ContinueAsNew` boundaries; the executor dedupes correctly.

**`attempt_seq` semantics.** Incremented in workflow code on each commit attempt. A retry of the executor commit activity (transient unavailability) re-sends the same `(tx_id, attempt_seq)`; the executor returns idempotent-success. A non-deterministic worker death between the activity start and the workflow history persist re-runs the same `attempt_seq` → same `tx_id` → idempotent-success. A new logical attempt (e.g., the lifecycle function recomputed and produced a different PendingTransaction) increments `attempt_seq` → new `tx_id`. **This is the correct three-axis idempotency: layer-1 (`tx_id`), layer-2 (`business_event_id`), layer-3 (`signal.idempotency_token` for inbound signals).**

### 7.3 Calibrated-object key (resolves R1-T8 L13)

v1 used `(calibrated_object_id, certification_timestamp, model_id)`. Wall-clock `certification_timestamp` cannot be content-addressed (non-deterministic across replay). The revised key is:

```
calibration_id = hash_jcs(calibrated_object_id, model_id, input_snap_id, attempt_seq)
```

`input_snap_id` is the content-addressed input snapshot used for the calibration step; `attempt_seq` is the Kalman workflow's internal counter. Wall-clock time is recorded as a *property* of the calibration record (auditable, not load-bearing).

### 7.4 Per-leaf classification (resolves R1-T8)

Two classes:

- **Content-addressed:** identifier is a hash of canonical bytes. Reproduces under replay. Suitable for laws L8, L13, U3 (L# in NAZAROV's spine). All snapshot-derived keys, `unit_id`, `obligation_id`, `tx_id`, `snap_id`, upstream `business_event_id`, `calibration_id`.

- **Mint-on-arrival:** identifier issued at first arrival, durably stored, not derivable from payload. Suitable for keys that must survive *across* replays where the payload alone is insufficient (e.g., `signal.idempotency_token` issued by an external sender; `(unit_id, version_seq)` where `version_seq` is producer-supplied counter). All mint-on-arrival keys MUST be persisted in an out-of-workflow dedup table to handle replay (§10).

Each leaf's classification is in §12's per-leaf table.

---

## 8. Saga compensation pattern — compensations are workflows (resolves M-12, M-13, B-3, R1-S13)

### 8.1 Compensation classification: trivial vs non-trivial

A compensation is **trivial** if it is a single-step idempotent state mutation (e.g., "flag this obligation as `EXPIRED` in the obligation registry"; "log to a queue"). A trivial compensation is implemented as an **activity** invoked from the obligation workflow's timer-fire branch.

A compensation is **non-trivial** if it has any of:
- Multiple steps with their own deadlines.
- Calls to external systems with their own retry/failure semantics.
- Need to reason about partial completion under failure.
- A discharge contract distinct from the original obligation's discharge.

**Non-trivial compensations are child workflows.** This is the M-12 ruling.

### 8.2 The compensation tower (resolves M-13)

Every non-trivial compensation has a three-tier tower:

**Tier 1 — Compensation workflow.** Started as a child workflow of the `ObligationWorkflow` on timer-fire. Has its own deadline budget (`compensation_deadline = original_deadline + compensation_horizon`), its own retry policy, its own discharge contract.

**Tier 2 — Escalated compensation.** If Tier 1 exhausts its retries or hits its deadline without completion, an **`EscalationWorkflow`** is started as a child of the Tier 1 workflow. Examples: a buy-in that cannot find liquidity escalates to a manual-ops queue + regulatory notification; a manufactured-payment under-withhold-then-true-up that fails escalates to tax authority correspondence. Tier 2 has its own deadline (typically days, not minutes/hours).

**Tier 3 — Terminal default.** If Tier 2 also exhausts, a **`TerminalDefaultWorkflow`** is started which records the obligation as `TERMINAL_DEFAULT`, fires regulatory disclosures, and waits indefinitely on a manual-ops signal to close. This tier never auto-discharges.

The tower is enumerated per obligation kind in §8.4. Every kind picks the depth of tower it needs (some kinds bottom out at Tier 1 because Tier 1 cannot fail in any meaningful sense; most need all three).

### 8.3 Late-discharge race policy (resolves B-3, R1-S3)

The race: a discharge signal arrives **after** the deadline timer fires and compensation has begun. The policy is **per obligation kind**:

| Obligation kind | Late-discharge policy | Reasoning |
|---|---|---|
| **SBL recall** | **Reject** (deadline sacrosanct) | Regulatory deadline (SFTR) is not extensible. Late discharge is logged for audit; compensation proceeds. |
| **Manufactured payment** | **Reject** | Tax-treaty / withholding deadlines are statutory. |
| **Settlement** | **Cancel-compensation if compensation has not begun externalising state; otherwise queue-and-reconcile** | Compensation = buy-in; if buy-in has not yet placed an external order, cancel; if it has, queue the late discharge until buy-in completes and reconcile (typically refund). |
| **Margin call** | **Cancel-compensation if compensation has not begun (no external default declaration); otherwise queue-and-reconcile** | Aligns with ISDA Master Agreement default-trigger mechanics. |
| **Regulatory submission ack** | **Queue-and-reconcile** | Trade Repository ack arriving late is common; treat as discharge if the prior reasonable-effort retry succeeded. |
| **Coupon / income event** | **Cancel-compensation** | If the event is the underlying paying late, it is the event itself, not a discharge of a separate obligation. |
| **Locate confirmation** | **Reject** (deadline sacrosanct) | Pre-trade locate is regulatory; cannot retroactively cure. |
| **Buy-in confirmation** | **Reject** (terminal) | The buy-in is itself a compensation for a prior settlement failure. |

**Implementation of late-discharge.** The `ObligationWorkflow` after timer-fire transitions to state `Compensating`. A late discharge signal is received and the policy lookup decides:
- Reject: the workflow appends an audit log entry and ignores the discharge state-transition.
- Cancel-compensation: the workflow signals the active `CompensationWorkflow` with `Cancel`; if the compensation acks the cancel before externalising, the obligation transitions to `Discharged`; otherwise, the discharge is queued.
- Queue-and-reconcile: the workflow appends to a `pending_late_discharges` list; on `CompensationWorkflow` completion, the workflow reconciles (typically: emit a corrective transaction).

The policy is L21-pinned per obligation kind. Adding a new obligation kind requires picking a policy.

### 8.4 Compensation tower per obligation kind (R1-S13)

| Obligation kind | Tier 1 (compensation) | Tier 2 (escalation) | Tier 3 (terminal) |
|---|---|---|---|
| Settlement (DvP) | `BuyInWorkflow` (multi-step: locate replacement → instruct → confirm → record) | `BuyInEscalationWorkflow` (manual ops, regulatory notification) | `TerminalSettlementDefaultWorkflow` |
| SBL recall | `CascadeRecallSagaWorkflow` (§9.6) → `BuyInWorkflow` if cascade fails | `RegulatoryEscalationWorkflow` (SFTR breach disclosure) | `TerminalSBLDefaultWorkflow` |
| Manufactured payment | `UnderWithholdWorkflow` + `TrueUpWorkflow` | `TaxAuthorityCorrespondenceWorkflow` | `TerminalTaxDefaultWorkflow` |
| Regulatory submission | `ResubmissionWorkflow` (with field-fix activity loop) | `ManualReviewWorkflow` (ops queue) | `RegulatoryEscalationWorkflow` (formal breach) |
| Coupon / income | `CouponMissedActivity` (trivial: flag missed, log) | n/a (Tier 1 cannot fail meaningfully) | n/a |
| Margin call | `DefaultDeclarationWorkflow` | `CloseOutNettingWorkflow` (ISDA Master Agreement §6) | `TerminalDefaultWorkflow` (litigation handoff) |
| Locate confirmation | `LocateRevocationActivity` (trivial: revoke trade) | n/a | n/a |
| Buy-in confirmation | n/a (Tier 0 — buy-in IS a compensation) | `BuyInEscalationWorkflow` | `TerminalSettlementDefaultWorkflow` |

Each Tier-N workflow has its own deadline, retry policy, and discharge contract. The contract for Tier-N → Tier-(N+1) transition is: Tier-N completes (success or fail) → Tier-N's parent (`ObligationWorkflow`) decides escalation per the kind's table.

### 8.5 Compensation determinism (resolves m-5 via M-12)

Compensation workflows read mutable state (UnitStatus, PositionState) via activities; activity results are memoised in the workflow history; replay reproduces the read values. The v1 issue (compensation activity reading mutable state directly without memoisation) is structurally eliminated because compensations are now workflows.

---

## 9. Awkward-fit category rulings (resolves R1-T9.5)

The six v1 categories receive explicit rulings: **Temporal (handle in Temporal)**, **out-of-Temporal (handle elsewhere)**, or **application discipline only (Temporal does not solve; documented as such)**.

### 9.1 Calendar retroactive amendments — RULING: **Temporal, via RestatementWatchWorkflow**

Folded into §6. Mode-1 bitemporal pin makes this tractable. The `CalendarUpdateOrchestratorWorkflow` is now a `RestatementWatchWorkflow` instance. Bounded state via paginated subscriber list. Fan-out semaphore caps in-flight signals.

### 9.2 High-frequency raw market observation streams — RULING: **out-of-Temporal**

Feed handlers are stateless services writing into the snapshot store. Workflows consume via `capture_snapshot`. Temporal does not orchestrate per-tick; that would be absurd. Documented as architectural answer; not a Temporal failure.

### 9.3 Continuous bitemporal corrections — RULING: **Temporal (via RestatementWatchWorkflow) + application discipline**

The orchestration shape is in Temporal (§6). The bitemporal *semantics* — two-axis time travel, restate-link discipline, knowledge-vs-effective collapse rules — are application discipline. Temporal carries the data; the application reasons about which stance (audit-only / recompute / compensate-and-republish) per restatement.

### 9.4 Pricing DAG topology object — RULING: **out-of-Temporal**

The DAG topology object is a config store updated by a coordinated `BuildPricingDAG` activity. Per-node workflow would orchestration-overhead-dominate. Workflows operate on a frozen topology per cycle. Documented; not a Temporal failure.

### 9.5 Kalman `ContinueAsNew` discipline — RULING: **Temporal, with concrete bound**

Resolved in §3.2: K=200 or 30d, frozen `KalmanContinuePayload` v1, `GetVersion` for schema bumps, replay-cost CI test. The discipline is in Temporal; the *parameter pin* (K=200) is L21.

### 9.6 SBL cascade-recall deadline propagation — RULING: **Temporal (saga shape) + application discipline (deadline arithmetic)**

The saga shape is a `CascadeRecallSagaWorkflow` per recall, with child `RecallWorkflow` per cascade level. Compensation = `BuyInWorkflow` (Tier 1 in §8.4). Deadline arithmetic is application:

- **Maximum cascade depth `N_max = 5`.** L21-pinned. Recalls deeper than 5 are rejected as terminal saga errors at registration.
- **Front-loaded budget per level.** Original 2-business-day window subdivides as: each level gets 0.5 business day at the head, residual at the leaf.
  - Depth 1 (Alice → Bob): Bob has 0.5bd to discharge or initiate level-2 recall.
  - Depth 2 (Bob → Charlie): Charlie has 0.5bd.
  - Depth 3, 4: 0.5bd each.
  - Depth 5 (leaf): residual = 2bd − 4×0.5bd = 0bd. Leaf discharges or fails.
- **Slack reclamation.** When level-N discharges at `t < deadline_N`, the slack `(deadline_N − t)` flows back to level-(N−1)'s residual and is added to its compensation budget. The workflow's deadline arithmetic carries `(deadline, slack_received_from_children)` per level.
- **Cascade-failure deadline propagation.** When level-N defaults (compensation triggered), level-(N−1)'s deadline is cut to `(deadline_N−1 − slack_consumed_by_level_N_failure)`. The `CascadeRecallSagaWorkflow` recalculates parent deadlines on each child failure.
- **Property test.** Generate cascade graphs of depths 1–5 with random discharge times; assert that for every successful chain, total elapsed ≤ 2bd; assert that for every failed chain, the failure level matches the deadline arithmetic.

---

## 10. Bounded signal-dedup discipline (resolves M-7)

Per-workflow signal-dedup sets cannot grow unboundedly. The discipline:

### 10.1 In-workflow bounded set + retention

Workflows hold a **bounded** signal-dedup set carried via `ContinueAsNew`. The set holds the last **N=4096** seen `idempotency_token` values per workflow, ordered by receipt; entries beyond 4096 are evicted. Retention horizon: **30 days** wall-time (entries older are evicted regardless of count). N and the horizon are L21-pinned.

A signal arriving with an `idempotency_token` already in the bounded set is a duplicate (silently dropped). A signal arriving with a token older than the retention horizon is treated as either:
- **Replay-of-stale** (rejected with audit log; counterparty must re-send with a new token), or
- **First-time** (accepted; the workflow's bounded set may be primed with old tokens from out-of-workflow dedup table — see §10.2).

### 10.2 Out-of-workflow dedup table

For high-cardinality signal endpoints (e.g., the `RestatementWatchWorkflow` with thousands of subscriber acks, or a regulatory-submission workflow), the bounded in-workflow set is insufficient. An **out-of-workflow dedup table** in the L19-equivalent durable store, keyed by `(workflow_id, idempotency_token)`, with retention managed separately from workflow lifetime.

A workflow's signal-receive path:
1. Activity: `check_and_set_dedup(workflow_id, idempotency_token, ttl)` → `is_duplicate`.
2. If duplicate, drop.
3. Otherwise, process; the activity has set the entry.

The cost is one extra activity per signal; this is acceptable for high-cardinality endpoints. For low-cardinality (most lifecycle workflows), the in-workflow set suffices.

### 10.3 Bloom filter as middle-ground

For some workflows, a Bloom filter is acceptable middle-ground. The trade-off: false-positive rate ε (configurable, e.g., 1% at 1M elements with k=7 hashes and 9.6 MB filter). False-positive = a non-duplicate is rejected. This is acceptable iff the upstream sender retries with a new token (i.e., idempotency tokens are minted-per-attempt, not minted-per-message). The Bloom filter is bumpable via `ContinueAsNew`.

The choice (set / dedup-table / Bloom) is per-workflow-kind and is documented in §12.

---

## 11. Task queue topology and namespace ruling (resolves M-4, M-14)

### 11.1 Namespace topology — RULING: **single global namespace, multi-tenant via search attributes**

Single Temporal namespace per Ledger deployment. Multi-tenancy (per legal entity, per region) is handled via:
- **Workflow ID prefix** by `tenant_id` (e.g., `tenant-{lei}-RegisterUnit-{unit_id}`).
- **Search attribute** `tenant_id` indexed for ops queries.
- **Authorisation activity** consulted on cross-tenant signal-send (an activity that consults L23 capabilities).

**Cross-region active-active:** Temporal Cloud Multi-Cluster Replication is **not** assumed in v11.0. Single-region deployment with disaster-recovery via cold-standby. Cross-region replication is a v12.0 candidate.

**Why not multi-namespace:** namespace isolation costs cross-namespace orchestration overhead (Nexus or external SDK calls), which the data layer's signal-heavy patterns cannot afford. The capability-based authorisation (L23) is the trust boundary, not the namespace boundary.

### 11.2 Task queue topology

| Task queue name | Purpose | Workers | Sticky cache |
|---|---|---|---|
| `lifecycle-orchestration` | Lifecycle workflow orchestration (RegisterUnit, lifecycle event handlers) | Workflow workers, low-latency tier | 10000 / 5GB |
| `lifecycle-activities-cpu` | CPU-bound lifecycle activities (snapshot construction, calibration step, MC pricing) | Activity workers, CPU-tier autoscale | n/a |
| `lifecycle-activities-io` | I/O-bound lifecycle activities (executor commit, view reads, vendor calls) | Activity workers, I/O-tier autoscale | n/a |
| `lifecycle-activities-crypto` | Crypto activities (signature verify, attestation envelope check) | Activity workers, dedicated tier | n/a |
| `obligation-orchestration` | ObligationWorkflow + CompensationWorkflow execution | Workflow workers, mid-latency tier | 5000 / 2GB |
| `kalman-orchestration` | KalmanWorkflow execution | Workflow workers, mid-latency tier | 2000 / 4GB |
| `kalman-activities` | Kalman compute step activities | Activity workers, CPU-tier (often GPU) autoscale | n/a |
| `pricing-orchestration` | PricingWorkflow + ValuationFSMWorkflow | Workflow workers, mid-latency tier | 10000 / 4GB |
| `pricing-activities` | Bump-and-revalue, PnL-explain, snapshot reads | Activity workers | n/a |
| `restate-watch-orchestration` | RestatementWatchWorkflow | Workflow workers, low-load tier | 200 / 500MB |
| `restate-watch-activities` | Subscriber-page reads, fan-out signal dispatch | Activity workers, I/O-tier | n/a |
| `regulatory-orchestration` | Regulatory submission and resubmission workflows | Workflow workers, mid-latency tier | 1000 / 1GB |
| `regulatory-activities` | TR ack, field-fix activities | Activity workers, I/O-tier | n/a |
| `escalation-orchestration` | All Tier-2 / Tier-3 compensation workflows | Workflow workers, low-load tier | 500 / 500MB |

**Why this topology:**
- Workflow vs activity separation per Temporal best practice (different scaling characteristics).
- CPU vs I/O activity separation prevents I/O-blocked activity workers from starving CPU-bound work.
- Crypto activities on a dedicated tier because signature-verify is bursty and HSM-bound.
- Kalman activities often GPU-attached; isolated for cost.
- Sticky caches sized per workflow's typical cycle count.

The topology is L21-pinned at the `worker_topology_version` axis. Adding a task queue or rebalancing is a coordinated deploy.

---

## 12. GetVersion gate inventory per leaf (resolves M-9)

Every workflow code path that **could change** in a way that alters the workflow's history shape requires a `GetVersion` gate. The inventory:

| Leaf | Code path | Gate name | When required |
|---|---|---|---|
| L1 ProductTerms | `is_fungibility_preserving` change | `gate_l1_fungibility_v2` | CDM uplift OR rule change |
| L1 ProductTerms | TermsVersion canonicalisation | `gate_l1_canonicalisation` | Canonicalisation algorithm bump |
| L4 Calendar | Schedule recompute on amendment | `gate_l4_amendment_handler` | Bitemporal mode change (we have pinned mode-1; future modes need gate) |
| L8 UnitStatus | New status enum case | `gate_l8_status_v2` | CDM enum extension |
| L9 PositionState | New coordinate added (e.g., new SBL sub-coordinate) | `gate_l9_coords_v{n}` | Schema extension |
| L10 RawObservation | New observable kind | `gate_l10_kind_v{n}` | Schema extension |
| L13 CalibratedObject | KalmanContinuePayload schema | `gate_l13_continue_v{n}` | New field in payload |
| L13 CalibratedObject | Innovation gate logic change | `gate_l13_gate_v{n}` | Algorithm change |
| L14 MoveStream | tx_id formula change | `gate_l14_txid_v{n}` | Formula bump (avoid; if needed, gate the workflow code that computes it) |
| L15 ValuationRecord | FSM transition logic | `gate_l15_fsm_v{n}` | New FSM state or transition |
| L15 ValuationRecord | PnL-explain threshold (L7 policy pin) | `gate_l15_threshold_v{n}` | Policy schema change |
| L16 ObligationStore | New obligation kind | `gate_l16_kind_v{n}` | New kind added (each kind has an entry in §8.4) |
| L16 ObligationStore | Late-discharge policy change | `gate_l16_policy_v{n}` | Policy table edit |
| L19 Snapshot | Snapshot envelope schema | `gate_l19_envelope_v{n}` | Envelope extension |
| L21 VersionPin | New pin axis | `gate_l21_axis_v{n}` | Adding `canonicalisation_version`, etc. |
| L23 Capability | Capability alphabet extension | `gate_l23_alpha_v{n}` | New field tag |

**Gate naming convention:** `gate_{leaf}_{logical_name}_v{n}`. Each version increment retains the previous branch in code; the workflow checks the gate value on its first relevant decision, captures the value, and follows the corresponding branch. Old workflows running on the old code path return the old gate value; new workflows return the new value.

**Deprecating gates.** A gate's old branch is kept until all workflows that recorded the old value have completed (or `ContinueAsNew`-ed past the gate). This is typically days to weeks for short-lived workflows; **months to years for long-running** (Kalman, ValuationFSM). Removal of a gate's old branch is itself a coordinated deploy.

---

## 13. Long-wait pattern: signal-driven workflows, not heartbeated activities (resolves M-15)

### 13.1 The signal-driven wait pattern

For any wait > 5 minutes (settlement confirmation, locate confirmation, regulatory ack, multi-vendor CA reconciliation, manufactured-payment confirmation), use a **signal-driven workflow**, not a long-running activity:

```
async def wait_for_external_event(wf_ctx, deadline, signal_chan):
    # Workflow-internal timer (durable; survives worker death without heartbeat)
    timer = wf_ctx.start_timer(deadline)

    # Wait for either signal or timer
    selected = await wf_ctx.select(
        signal_chan.receive(),
        timer
    )

    if selected is signal_chan:
        return signal_chan.value()
    else:
        # Timer fired; trigger compensation per §8
        return TimeoutResult()
```

This is the Temporal-idiomatic answer. No heartbeat; the timer is server-managed; the worker need not be running for the timer to fire. When the timer fires (or signal arrives), Temporal schedules a workflow task; any available worker picks it up.

### 13.2 Heartbeat policy for legitimately long activities

For activities that **are** legitimately long-running compute (snapshot construction, Kalman compute, MC pricing, multi-source CA reconciliation):

| Activity class | StartToCloseTimeout | HeartbeatTimeout | Heartbeat cadence |
|---|---|---|---|
| Snapshot construction (multi-source) | 30 min | 30 sec | 10 sec |
| Kalman compute step | 5 min | 30 sec | 10 sec |
| MC pricing | 60 min | 60 sec | 30 sec |
| CA reconciliation (multi-vendor) | 2 hours | 60 sec | 30 sec |
| Crypto: signature verify | 5 sec | n/a (short) | n/a |
| Executor commit | 10 sec | n/a (short) | n/a |
| TR submission | 30 sec | n/a (short) | n/a |

Heartbeat cadence is roughly 1/3 of `HeartbeatTimeout`. The activity must call `ctx.heartbeat()` regularly; missing heartbeat = worker presumed dead, activity rescheduled.

### 13.3 Application of the pattern

| Wait scenario | Pattern in v1 (wrong) | Pattern in v2 (correct) |
|---|---|---|
| Settlement confirmation (DvP wait) | Long-running activity with heartbeat | `SettlementConfirmationWorkflow` with timer + signal |
| Locate confirmation (SBL pre-trade) | Long-running activity with heartbeat | `LocateConfirmationWorkflow` with timer + signal |
| Regulatory ack (TR / regulator) | Long-running activity with heartbeat | `RegulatorySubmissionWorkflow` with timer + signal |
| CA reconciliation (multi-vendor) | Long-running activity with heartbeat | `CorpActionReconciliationWorkflow` with timer + per-vendor signals |
| Margin call confirmation | Long-running activity | `MarginCallWorkflow` with timer + signal |

Each is a workflow. Each has a deadline budget. Each has a discharge contract. Each integrates with the §8 compensation tower on timeout.

---

## 14. Disposition of MINOR findings

| ID | Disposition | Rationale |
|---|---|---|
| m-1 | **Resolved** in §3.1 | C-A12 added; multi-region replication required |
| m-2 | **Resolved** in §7.1 | `obligation_id` now derives from `business_event_id`, not `run_id` |
| m-3 | **Resolved** by §12 gate `gate_l15_threshold_v{n}` | Policy threshold pinned at workflow start |
| m-4 | **Resolved** in §3.2 | Kalman input is signal-driven from snapshot-store-watch; documented |
| m-5 | **Subsumed** by M-12 | Compensation is workflow → activity-mediated reads automatic |
| m-6 | **Resolved**: `WorkflowExecutionTimeout` policy = `obligation_deadline + sum(compensation_horizon_per_tier)` per kind, L21-pinned. For 30y bonds, this is 30y + ~1bd compensation budget. |
| m-7 | **Accepted**: workflow lifecycle deprecation policy = "final ContinueAsNew → final certification → graceful close" with explicit signal `RetireWorkflow` | Documented in §15 |
| m-8 | **Accepted**: ops dashboards read from search attributes, not from per-workflow queries; per-workflow queries rate-limited to 10 qps | Documented in §15 |

---

## 15. Operational policies (workflow lifecycle, query patterns)

**Workflow retirement.** Long-running workflows (Kalman, ValuationFSM, RestatementWatch, ObligationWorkflow for long-dated obligations) retire via:
1. External signal `RetireWorkflow` carrying `(reason, retirement_deadline)`.
2. Workflow completes any in-flight activity, performs a final `ContinueAsNew` with payload field `is_retiring=True`.
3. The new run's first decision: emit a final state record (audit), close gracefully.

**Search attribute design.** Every workflow indexes:
- `tenant_id`
- `workflow_kind` (e.g., "ObligationWorkflow", "KalmanWorkflow")
- `business_key` (e.g., unit_id, obligation_id, calibrated_object_id)
- `status` (workflow-internal status, mutable)
- `cdm_v`, `model_id`, `canonicalisation_version` (for ops query "which workflows on old version")

Ops dashboards query Temporal's visibility API (Elasticsearch-backed) on these attributes; never query workflows directly for bulk fetches.

**Query rate-limit.** Per-workflow query rate is capped at 10 qps via worker-side semaphore. A query above the cap returns `RESOURCE_EXHAUSTED`; the caller backs off.

---

## 16. Summary

- **R1 BLOCKING findings resolved:** B-1 (RestatementWatchWorkflow §6); B-2 (`tx_id` formula §7.2); B-3 (late-discharge policy §8.3).
- **R1 MAJOR findings resolved:** all 15. M-1 calendar (§6, §9.1); M-2 Kalman (§3.2, §9.5); M-3 SBL (§9.6); M-4 namespace (§11); M-5/M-8 canonicalisation (§1.4); M-6 BE namespace tagging (§7); M-7 dedup bounded (§10); M-9 GetVersion inventory (§12); M-10 FSM location (§3.4); M-11 signal ordering (§3.4, §13); M-12 compensations as workflows (§8); M-13 compensation tower (§8.2); M-14 task queue topology (§11.2); M-15 signal-driven wait pattern (§13).
- **R1 MINOR findings disposition:** see §14.
- **Awkward-fit categories ruled:** §9 — three Temporal, one out-of-Temporal, two with explicit application-discipline footprint.
- **Saga compensation:** workflows-not-activities, three-tier tower with terminal escalation, late-discharge policy per kind.
- **Canonicalisation:** RFC 8785 JCS for JSON, Protobuf canonical for binary, pinned in L21.
- **`tx_id` formula:** `hash_jcs(business_event_id, attempt_seq)` — no `run_id`.

**Total leaves covered:** 31 across 3 classes + 4 cross-cutters (unchanged from v1).
**Canonical idempotency keys:** 9 (corrected; per-leaf classification in §7.4).
**Awkward-fit categories ruled:** 6 (3 Temporal, 1 out-of-Temporal, 2 with named application discipline).
**File path:** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/work/phase2/temporal_v2.md`.

---

*End of Phase 2 Temporal Synthesis v2.*
