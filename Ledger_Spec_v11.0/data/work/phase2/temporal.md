# Phase 2 — Temporal Workflow Synthesis for the Data Layer

**Author:** Arjun Mehta (Temporal.io discipline)
**Phase:** 2 (Data-Team synthesis; ingest workflow shapes for every data leaf)
**Date:** 2026-04-29
**Phase 1 inputs read:** `cartan, correctness, feynman, finops, formalis, geohot, grothendieck, halmos, isda, jane_street, karpathy, lattner, matthias, minsky, nazarov, noether, sbl, temporal, testcommittee` (19 files).

---

## 0. Reading of the Phase-1 convergence

The 19 panels converge, with notational variation, on **three structural classes plus orthogonal cross-cutters**. I adopt this working taxonomy for Phase 2 and map every leaf into it:

| Class | Grothendieck | Geohot | Karpathy / Lattner | Mutation discipline |
|---|---|---|---|---|
| **Definitions** | $\mathcal{F}_{\text{Defn}}$ | D1, D2 | A, B, F | Append-only versioned |
| **Observations** | $\mathcal{F}_{\text{Obs}}$ | D3, D4 | C, D | Bitemporal append-only |
| **Effects** | $\mathcal{F}_{\text{Eff}}$ | D5–D9 | G | Append-only by construction |

Three cross-cutters that every panel surfaces independently: **Identity / cryptographic envelope** (provenance, attestation chain, signatures); **Obligation / liveness** (deadline-bearing duties, P21 of the ledger); and **Workflow / orchestration state** (Temporal histories themselves, the second of v10.3 §10.3's two audit trails). The valuation document already specifies a Temporal architecture for the FSM consuming this layer; the data layer's job is to deliver `(SnapshotId, value)` cleanly to it.

The valuation FSM's correctness rests on **deterministic replay of an immutable log** — exactly Temporal's history-replay model. Every leaf below is graded on whether (a) it is captured into history at arrival (signal payload, activity result, timer fire), (b) it is read via an activity that returns a snapshot identifier, or (c) the Temporal model is genuinely awkward and another mechanism is needed. The third bucket is small and I name it explicitly in §6.

---

## 1. Notation for the leaf table

For each leaf, I specify the six fields the brief asks for, in compact table form per leaf:

1. **Ingress shape** — `{Activity, Signal, ScheduledWorkflow, ChildWorkflow, Subscription, Pre-registered}`. "Subscription" means a long-lived workflow that polls or holds an open stream.
2. **Idempotency key** — exact key shape and where enforced (workflow ID / activity dedup table / business-key hash / SnapshotId).
3. **Replay-determinism boundary** — which fields are frozen at workflow start vs. fetched at replay-time via a memoised activity.
4. **Failure / retry / heartbeat** — retryable vs terminal errors; heartbeat needed Y/N; saga compensation Y/N.
5. **Downstream split** — what fires as Signal / Activity / Query for executor / valuation FSM / settlement projector.
6. **Versioning posture** — `{Schema-pin via header, GetVersion gate, ContinueAsNew at uplift, N/A}`.

I use `cdm_v` as the CDM version pin captured at ingest; `snap_id` as the content-addressed snapshot id; `tx_id` as the executor's transaction id; `obl_id` as the obligation id; `wf_id` as a workflow id derived deterministically from the relevant business key.

---

## 2. Class **Definitions** — append-only versioned

This is `ProductTerms[u]` in StatesHome, plus the firm-wide reference data, conventions, calendars, party / legal-entity master, and the legal agreement objects (CSA, ISDA, GMSLA, mandate). The Temporal posture is the same across the class: **read once via an activity at registration, capture the result into the workflow history, never re-read live.**

### 2.1 ProductTerms (per-unit) — listed, OTC, bond, mandate, QIS, SBL loan
- **Ingress:** activity result on a `RegisterUnitWorkflow`. The full `TermsVersion` payload (or its content-addressed reference) is captured into history at the registration event. Subsequent amendments are signals into the unit's lifecycle workflow that compute `is_fungibility_preserving(amendment)` as an activity → preserving = appended `TermsVersion` (atomic StateDelta); breaking = child workflow allocates `u_new` with `superseded_by`.
- **Idempotency key:** `(unit_id, version_seq)`. Workflow ID for the registration is `register-{unit_id}` so Temporal rejects double-starts. Activity dedup at the executor commit by `tx_id`.
- **Replay boundary:** the entire `TermsVersion` is **frozen at the registration tx**. Long-running lifecycle workflows (30y bond) carry the relevant fields explicitly into `ContinueAsNew` payload; the registry is **never** re-queried mid-flight for terms (would be a determinism violation under terms-restatement scenarios).
- **Failure / retry:** vendor / CDM-mapping errors are retryable with bounded backoff; CDM qualification mismatch is **NonRetryable** (terminal); re-registration of an existing `unit_id` is terminal per StatesHome C10.
- **Downstream:** **Activity** read via `view.product_terms(u)` from any lifecycle workflow; **Query** for ops dashboards (workflow query, no side effects); **never Signal** — there is no streaming "current terms" channel.
- **Versioning:** `cdm_v` schema-pinned at ingest; CDM uplift handled by `GetVersion` at the lifecycle workflow's amendment branch; long-running workflows uplift CDM at `ContinueAsNew` boundaries.

### 2.2 Smart-contract code & version (`SmartContractRef`)
- **Ingress:** Pre-registered. Workflow & worker bind to a (contract_id, code_hash) at deploy time; Temporal's `GetVersion`/`patched` API records the binding into history.
- **Idempotency:** `(contract_id, code_hash)` collision = deploy-pipeline error, not a runtime concern.
- **Replay boundary:** Code IS the workflow's history — Temporal pins the version per run.
- **Failure / retry:** N/A (deploy-time concern).
- **Downstream:** **Activity** dispatch only; lifecycle workflow calls the typed handler.
- **Versioning:** `GetVersion` for in-place changes during long workflows; **prefer `ContinueAsNew` at major version bumps** to keep histories clean.

### 2.3 ISO 4217 / 10383 / 17442 enums and CDM enum universe
- **Ingress:** Pre-registered at worker startup. CDM release uplift is a coordinated worker deploy.
- **Idempotency:** `(cdm_version, enum_name, value)`.
- **Replay:** Frozen per worker version. Long workflows pin via `cdm_v` captured at start.
- **Failure / retry:** Unknown enum value = terminal at the CDM-mapping boundary; the inbound message is dead-lettered with a quarantine activity.
- **Downstream:** Pure-function inputs to lifecycle activities.
- **Versioning:** `ContinueAsNew` at CDM uplift for any in-flight workflow whose handlers consume the changed enum.

### 2.4 Calendar definitions, day-count enums, business-day conventions
- **Ingress:** Activity result captured **at unit registration**: the full resolved schedule is computed once (CDM `ResolveAdjustableDate` against pinned calendar version) and stored in workflow state. Subsequent calendar updates arrive as Signals into a `CalendarUpdateWorkflow` that fans out to affected units (see §6 for the awkwardness).
- **Idempotency:** `(calendar_id, version_id)` for the calendar; `(unit_id, schedule_version_seq)` for the resolved schedule stored on the unit.
- **Replay boundary:** **The resolved schedule is captured, not the live calendar.** Calendar version is pinned. Replay reads the captured schedule.
- **Failure / retry:** Late-published holidays trigger an emergency signal-driven schedule recompute (saga: revert old schedule, append new, re-register affected obligations). Retryable.
- **Downstream:** **Activity** read of `view.schedule(u)` by lifecycle workflows; calendar update Signal → child workflow per affected `(jurisdiction, market)` set.
- **Versioning:** Bitemporal — calendar version pinned at unit registration; pin replayed deterministically.

### 2.5 Party / Legal Entity master (LEI / BIC / KYC classification)
- **Ingress:** Activity result, **bitemporal**: read returns `(party_record, knowledge_timestamp)`. The lifecycle workflow captures this on first reference and re-reads only on explicit signal-driven KYC refresh.
- **Idempotency:** `(party_id, knowledge_timestamp)` for the bitemporal read.
- **Replay boundary:** Captured per-invocation; replay returns the memoised value (correct: original execution saw a specific value). LEI lapse / merger events arrive as Signals into a long-running `PartyMonitorWorkflow` (one per party of interest), which fans out to affected lifecycle workflows.
- **Failure / retry:** GLEIF feed errors retryable; lapsed LEI in an externally-reportable workflow is terminal at the regulatory submission step (saga compensation = regulatory escalation).
- **Downstream:** **Activity** read by reporting / settlement workflows; **Signal** to lifecycle workflow on lapse/merger.
- **Versioning:** Bitemporal queries; no schema versioning.

### 2.6 Master Agreement / CSA / GMSLA / Mandate (legal agreement layer)
- **Ingress:** Activity result, append-only versioned (StatesHome C8 two-track). Amendment ingress = signal into the CSA/agreement workflow.
- **Idempotency:** `(agreement_id, version_seq)`.
- **Replay boundary:** Frozen at the moment the lifecycle workflow consumes it (e.g., at margin call computation). Subsequent amendments do not retroactively alter past computations.
- **Failure / retry:** Document parsing retryable; structural mismatch terminal.
- **Downstream:** **Activity** for margin computation; **Signal** for amendments.
- **Versioning:** C8 two-track at the data level; CDM-uplift via `GetVersion` only for the CDM payload field.

### 2.7 Settlement Venue / SSI / Custody Topology
- **Ingress:** Activity result, **bitemporal**, captured per `SettlementWorkflow` at instruction-generation time.
- **Idempotency:** `(wallet_id, knowledge_timestamp)`; the resulting `SettlementInstruction` is keyed by `(transaction_id, settlement_leg_index)`.
- **Replay boundary:** Captured at instruction generation; subsequent SSI changes never alter a generated instruction (an SSI restatement after the fact triggers a *new* compensating workflow, not a re-derivation).
- **Failure / retry:** SSI-not-found terminal (settlement cannot proceed); routes to ops queue via signal. Settlement confirmation timeout triggers saga compensation (cancel + reissue).
- **Downstream:** **Activity** read; **Signal** for SSI updates routed via `SsiUpdateWorkflow`.
- **Versioning:** Bitemporal, deeply non-trivial at the wire layer; pin SSI version on every instruction.

### 2.8 Regulatory rulesets (SFTR / EMIR / SLATE / MiFID thresholds)
- **Ingress:** Activity result. Each reportable event spawns a `RegReportingWorkflow` keyed by `reportable_event_id`.
- **Idempotency:** `(reportable_event_id, regime)` is the workflow ID.
- **Replay boundary:** Workflow input fully captures the regime version; ruleset changes do not retroactively alter in-flight reports.
- **Failure / retry:** Trade-repository rejections retryable (with field-fix activity); regime-violation (e.g., lapsed LEI) terminal → escalation.
- **Downstream:** **Activity** for submission; **Signal** for TR acknowledgement back-channel.
- **Versioning:** Bitemporal — old trades reported under their booking-time regime.

### 2.9 Tax status / withholding (FATCA / W-8BEN-E / treaty rates)
- **Ingress:** Activity result, bitemporal; refresh via signal on form expiry.
- **Idempotency:** `(counterparty_id, jurisdiction, knowledge_timestamp)`.
- **Replay:** Captured at the income event (manufactured-payment computation, dividend withholding).
- **Failure / retry:** Expired W-form is terminal at the manufactured-payment activity → saga compensation = under-withhold + true-up obligation.
- **Downstream:** **Activity** for tax computation; **Signal** for form-expiry refresh.
- **Versioning:** Bitemporal.

---

## 3. Class **Observations** — bitemporal append-only

This is the **most replay-hostile data class**. The discipline is uniform: *workflow code never calls `marketdata.get_spot(...)` directly; it calls an activity that returns `(snap_id, value)` and downstream activities read from the snapshot store keyed on `snap_id`.* The snapshot store is the determinism boundary.

### 3.1 Raw market observable (tick, quote, settlement print, fixing)
- **Ingress:** **Two-tier**. Bulk feed handlers run as standalone services that write attestation envelopes into the snapshot store; lifecycle workflows consume via an activity `capture_snapshot(spec) -> snap_id` that pins the relevant subset. **Workflows do not subscribe to feeds directly.**
- **Idempotency:** `snap_id = hash(observable_id, source, t_observed, t_known)`. Activity dedup at the snapshot store.
- **Replay boundary:** **Memoised `snap_id` is the only thing in workflow history**; the value is read via an activity keyed on `snap_id`. Replay returns the same value because the snapshot is content-addressed.
- **Failure / retry:** Vendor outage → fallback chain traversed in the activity; chain-exhausted = terminal → FSM transitions `STALE`. **Heartbeat: yes** for any long-running snapshot construction (multi-source aggregation).
- **Downstream:** **Activity** for valuation FSM consumption; **never Signal** — observation streams do not signal workflows directly. The valuation companion's pricing DAG mutation is signal-driven, but the signal carries `snap_id`, not values.
- **Versioning:** `snap_id` includes a schema-version field; vendor restatements are *new* snapshots with the same `(observable_id, t_observed)` and a later `t_known`.

### 3.2 Calibrated parameters (Kalman posterior — yield curves, vol surfaces, hazard curves)
- **Ingress:** Output of a dedicated `KalmanWorkflow` per calibrated object (one workflow per `(curve_id, model_id)`, valuation §5.7). Inputs: raw observation snapshots. Output: certified calibration record.
- **Idempotency:** `(calibrated_object_id, certification_timestamp, model_id)`. Workflow ID = `calibrate-{curve_id}-{model_id}` (singleton per curve, runs forever via `ContinueAsNew`).
- **Replay boundary:** The Kalman workflow's *prior posterior + input observation snap_ids* fully determine the next posterior — Kalman is deterministic. Long history → `ContinueAsNew` every N certifications.
- **Failure / retry:** Innovation-gate rejection = retain prior posterior, mark Stale (not a workflow failure); no-arbitrage projection failure = terminal at the certification activity. **Heartbeat: yes** for non-trivial Kalman-step compute.
- **Downstream:** **Signal** to subscribed `PricingWorkflow` instances on each new certified posterior (signal payload = `calibration_id` only; consumer reads via activity); **Activity** for ad-hoc reads.
- **Versioning:** `model_id` is part of the key; new model versions run as parallel Kalman workflows; cutover is a signal to consumers.

### 3.3 Pricing DAG snapshot
- **Ingress:** Pre-computed by `BuildPricingDAG` (valuation §6.1) at registration / mutation events; passed as input to each `PricingWorkflow` cycle.
- **Idempotency:** `(dag_version, topology_hash)`.
- **Replay boundary:** Frozen per cycle (a cycle always operates on a frozen topology, valuation §6.3).
- **Failure / retry:** Topology validation failure terminal; cycle aborted.
- **Downstream:** **Signal** to all `PricingWorkflow` instances at cycle boundaries; **Activity** for ad-hoc topology queries.
- **Versioning:** DAG version bumped at mutation; mid-cycle mutations are queued, applied next cycle.

### 3.4 ValuationRecord (output of pricing — also an input to the FSM and downstream consumers)
- **Ingress:** Activity result of `PublishValuationRecord` (valuation §7.4) inside the producer's `PricingWorkflow`. Read by downstream consumers via Signal-on-publish + Activity-fetch by id.
- **Idempotency:** `(unit_id, valuation_workflow_run_id, cycle_seq)`.
- **Replay:** Memoised in producer; consumers fetch by `valuation_record_id` (content-addressed).
- **Failure / retry:** Pricing failure transitions FSM to `Failed`; record still published with quality flag. Heartbeat for MC pricing **mandatory**.
- **Downstream:** **Signal** to subscribed pricing nodes; **Activity** for FSM consumption; **Query** for ops dashboards.
- **Versioning:** `model_id` in identity; model uplift = parallel records.

### 3.5 Sensitivity Jacobian (Greeks)
- **Ingress:** Activity result of `ComputeGreeks` (valuation §7.4), bump-and-revalue against the pinned snapshot.
- **Idempotency:** `(unit_id, model_id, cycle_seq)`.
- **Replay:** Deterministic given `snap_id` and `model_id`.
- **Failure / retry:** Bump computation failure → fall back to last cached Jacobian with stale flag; FSM transitions Approximate.
- **Downstream:** **Activity** for risk and PnL-explain; **Query** for risk-system dashboards.
- **Versioning:** Tied to `model_id`.

### 3.6 PnL-explain residual
- **Ingress:** Activity result of `PnLExplain` (valuation §7.4).
- **Idempotency:** `(unit_id, prev_valuation_id, current_valuation_id)`.
- **Replay:** Deterministic.
- **Failure:** PASS / FAIL drives FSM T5 vs T6 (Quarantined). Not retryable as such — failure is a *valid* outcome.
- **Downstream:** **Activity** for FSM transition; **Query** for explain dashboards.
- **Versioning:** Same as ValuationRecord.

### 3.7 Market data quality / staleness flags
- **Ingress:** Activity result inside the snapshot-construction activity; folded into `snap_id`.
- **Idempotency:** Same as 3.1.
- **Replay:** Captured with the snapshot.
- **Failure:** Gating decision (ACCEPT / DEFER / REJECT) **must be captured into history** — recomputing on replay would let a previously-deferred event be re-decided differently.
- **Downstream:** Read via the snapshot.
- **Versioning:** Schema fields on the snapshot envelope.

### 3.8 Corporate action announcements (oracle, multi-source)
- **Ingress:** Signal payload (signed envelope, multi-source) into a `CorpActionWorkflow` keyed by `(isin, ca_id)`. Vendor disagreements arrive as multiple signals; the workflow reconciles via timer + activity.
- **Idempotency:** `(isin, ca_id, vendor)`; the reconciliation produces a single canonical `(isin, ca_id)` record.
- **Replay:** Signal payload captured into history; reconciliation is deterministic on the captured set.
- **Failure / retry:** Inter-vendor disagreement → wait timer + manual override signal; threshold-exceeded reconciliation aborts to ops queue.
- **Downstream:** **Fan-out child workflows** to all open positions (classic fan-out/fan-in); `CorpActionWorkflow` waits on confirmations via signals from each child.
- **Versioning:** Vendor schema versions captured in signal payload; CA event types CDM-pinned.

### 3.9 FX rates (special-cased market data)
- **Ingress:** Same shape as 3.1; FX-set consistency is enforced at the snapshot construction level (S7 covariance — all FX rates used in a `V_t` must come from the *same* snapshot).
- **Idempotency:** Snap_id including the full FX cross-rate matrix subset used.
- **Replay:** Captured with snapshot.
- **Failure:** FX outage falls back to triangulation (in the activity, not the workflow); chain-exhausted = STALE.
- **Downstream:** Activity reads; FX-fixing publication is a signal into reset workflows.
- **Versioning:** Schema-pinned.

### 3.10 Reference-rate fixings (SOFR, ESTR, SONIA)
- **Ingress:** Signal into a `FixingPublicationWorkflow` per `(index, tenor)`; restated fixings = new signal with same `(index, fixing_date)` and `restate_link`.
- **Idempotency:** `(index, tenor, fixing_date)`; signal carries `idempotency_token`.
- **Replay:** Signal payload in history.
- **Failure / retry:** Late publication → reset workflow waits with timer; timer-fire-without-signal = STALE → fallback per ISDA / ARRC fallback waterfall (which is itself an activity).
- **Downstream:** **Signal** to subscribed reset workflows (IRS, FRN coupon).
- **Versioning:** Index methodology pinned at deal time (replays fall back to pinned methodology).

---

## 4. Class **Effects** — append-only by construction

The output of executor commits (moves, state deltas, transactions, lifecycle events) and the workflow histories themselves. Mutation discipline: **append-only by construction.** The Temporal posture is the natural one — most of these are activity outputs or Temporal-managed.

### 4.1 PendingTransaction (executor input — output of lifecycle function)
- **Ingress:** Activity result of the pure lifecycle function inside an activity wrapper; passed as input to the executor commit activity.
- **Idempotency:** `tx_id` (deterministic hash, layer 1 of the three-layer chain). Executor commit activity is **idempotent** — second commit of same `tx_id` returns success without re-applying.
- **Replay:** Memoised activity result.
- **Failure / retry:** Conservation violation = NonRetryable terminal; executor returns specific error → workflow fails fast. Idempotency rejection = success.
- **Downstream:** **Activity** to executor commit; commit activity output flows back to lifecycle workflow.
- **Versioning:** `cdm_v` captured.

### 4.2 Move and PositionState delta
- **Ingress:** Part of the executor's atomic commit (StatesHome C3 atomicity).
- **Idempotency:** Inherits `tx_id`.
- **Replay:** N/A — executor's append is the canonical record; workflow holds only `tx_id`.
- **Failure:** Atomic; partial commit structurally impossible.
- **Downstream:** Activity-mediated read of `view.position_state(w, u)` by lifecycle workflows.
- **Versioning:** Schema versioned at the move-stream level.

### 4.3 BusinessEvent / CDM lineage payload
- **Ingress:** Signal payload (external events: trade execution, exercise notice, locate confirmation, settlement confirmation, regulatory ack) **or** activity result (computed events: timer fires for coupon/expiry).
- **Idempotency:** `business_event_id` — layer 2 of the three-layer chain.
- **Replay:** Captured into workflow history at signal receipt or activity completion.
- **Failure:** Malformed CDM = NonRetryable; CDM version mismatch = retryable via mapping activity.
- **Downstream:** **Activity** to lifecycle handler that consumes the event.
- **Versioning:** `cdm_v` field on the payload; `GetVersion` for handler dispatch on uplift.

### 4.4 UnitStatus reads
- **Ingress:** Activity result inside lifecycle workflows. **Critical: never a long-lived subscription.** Each read is a fresh activity call and the result is memoised in history.
- **Idempotency:** Reads are not idempotency-keyed (pure projection); writes are keyed by the source `tx_id`.
- **Replay:** Activity result captured per invocation.
- **Failure / retry:** View read errors retryable; missing unit (not registered) terminal.
- **Downstream:** Read by lifecycle workflows, valuation FSM, settlement projector — all via activities.
- **Versioning:** Schema-pinned per CDM version.

### 4.5 Move stream / event log records
- **Ingress:** Output of executor commit activity — Temporal does not own this stream. The executor's storage is the canonical record; Temporal holds the activity result (`tx_id`).
- **Idempotency:** `tx_id`.
- **Replay:** Stream not replayed by Temporal; Temporal replays the workflow that *caused* the append.
- **Failure:** Append failure is treated as commit failure → workflow retries the entire executor commit activity.
- **Downstream:** Read by reporting workflows (via activity); **never via Signal** (the stream is not a Temporal queue).
- **Versioning:** Hash-chained with `cdm_v` field.

### 4.6 Obligation registry entries
- **Ingress:** Registered as part of the lifecycle activity's `PendingTransaction` (atomic with the triggering tx). Executor's post-commit hook spawns the `ObligationWorkflow` with workflow ID derived from `obligation_id`.
- **Idempotency:** `obligation_id` (workflow ID prevents duplicate spawning).
- **Replay:** Workflow ID is deterministic; the `ObligationWorkflow` itself is the durable timer + discharge listener.
- **Failure / retry:** Workflow start collision = obligation already registered (success). Discharge signal not received before deadline timer fires → `compensation_action` activity invoked.
- **Downstream:** **Signal** for discharge (carries `idempotency_token`, P23); **Activity** for compensation; **Query** for ops dashboards.
- **Versioning:** Obligation-kind enum CDM-versioned.

### 4.7 Discharge signals (counterparty / CSD / lifecycle confirmations)
- **Ingress:** Signal into the corresponding `ObligationWorkflow` carrying `(obligation_id, ledger_state_witness, idempotency_token)`.
- **Idempotency:** `idempotency_token` in the signal payload (per v10.3 §10.3 example).
- **Replay:** Captured into workflow history at receipt.
- **Failure:** Duplicate signals are silently dropped by the workflow's idempotency check.
- **Downstream:** Workflow internal state transition `Pending → Discharged`.
- **Versioning:** N/A.

### 4.8 Workflow history and workflow input (Temporal-managed)
- **Ingress:** Managed by Temporal; not application data.
- **Idempotency:** Workflow ID prevents duplicate starts; `(workflow_id, run_id)` for run-level.
- **Replay:** This *is* what Temporal replays.
- **Failure:** History corruption mitigated by Temporal's replication.
- **Downstream:** N/A (consumed by Temporal itself).
- **Versioning:** **`ContinueAsNew` payload is a first-class data contract** — every long-running workflow's continue payload is part of the data spec. For each workflow type the minimum carry-forward set must be specified; missing fields = silent state loss.

### 4.9 Activity timeouts and task queue identifiers (orchestration config)
- **Ingress:** Pre-registered.
- **Idempotency:** N/A.
- **Replay:** N/A — bound to invocation, not part of replay state.
- **Failure:** Misconfigured timeout = production incident. **HeartbeatTimeout missing on long activities** (settlement confirmation wait, MC pricing, multi-source CA reconciliation) = silent worker-death undetected.
- **Downstream:** N/A.
- **Versioning:** Versioned with deployment.

### 4.10 Search attributes (visibility / ops dashboards)
- **Ingress:** Workflow code calls `UpsertSearchAttributes`; result captured in history.
- **Idempotency:** N/A — search attributes are mutable.
- **Replay:** Captured; safe.
- **Failure:** Indexing lag = ops impact only (MTTR), not correctness.
- **Downstream:** Ops dashboards via Temporal Cloud / Elasticsearch.
- **Versioning:** Schema additions; never repurpose attribute keys.

---

## 5. Cross-cutting: Identity / cryptographic envelope and provenance edges

Every datum in classes 2 and 3 (Definitions and Observations) arrives in an attestation envelope (Nazarov CC-1). The envelope is verified at the ingress activity and the verified payload is what is captured into history. Three Temporal-specific consequences:

- **Verification is an activity, not workflow code.** Signature verification involves crypto libraries with non-deterministic implementations and must be activity-confined.
- **The envelope's `source_signature` is what the snapshot's content hash incorporates.** Restatements produce new envelopes with new signatures.
- **Key rotation** on the source side = a Signal into a `SourceKeyRotationWorkflow` (singleton per source) that updates the verifier's key set; existing in-flight workflows' replays use the key set as-of their start time (captured at start).

Provenance edges (lineage) are emitted as side-effects of activity completions and stored in the lineage store (Karpathy F.5 / Nazarov CC-7). Temporal does not own this store; it is queried by audit workflows but not in the hot path.

---

## 6. Where Temporal is genuinely awkward — call them out

### 6.1 Calendar updates that affect already-resolved schedules
A retroactive holiday declaration after unit registration affects every workflow that has a captured schedule. The clean Temporal path — signal each affected lifecycle workflow with a `recompute_schedule` request — explodes to **N workflows for N units**, each of which must re-validate its in-flight obligations and re-register timers. This is workable but high-friction. **Mitigation:** maintain a `CalendarUpdateOrchestratorWorkflow` per `(jurisdiction, market)` that holds the affected-unit set in workflow state and fans out updates as child workflows. Acceptable but the pattern is heavy. **The honest assessment: calendar amendment is the worst-fit data class for Temporal in the data layer.**

### 6.2 High-frequency raw market observation streams
A Temporal workflow per tick is absurd. The architectural answer (Phase-1 panel consensus) is: **ingest is not a workflow**. Feed handlers are stateless services that write attestation envelopes into the snapshot store; workflows consume via `capture_snapshot(spec) -> snap_id`. This is correct but worth flagging because new contributors will reach for `SignalWithStart` and discover Temporal's scaling limits the hard way.

### 6.3 Continuous bitemporal corrections (vendor restatements)
The "two-axis time travel" requirement (knowledge time vs. effective time) is something Temporal does not natively model. Temporal's history is a single-axis append-only log of when events were processed; mapping bitemporal queries onto it requires application-level discipline (carry both axes in every activity result, never collapse them in the snapshot store). This is a **data layer responsibility**, not a Temporal feature, and Phase 2 should not pretend Temporal solves it.

### 6.4 The Pricing DAG itself
A pricing graph with O(10^4) nodes is not naturally a Temporal workflow per node — the orchestration overhead per cycle would dominate. The valuation companion's design (one workflow per *unit*, signal-driven graph traversal) is the right answer; but the *DAG topology object* is not a workflow at all — it lives in a config store and changes through a coordinated `BuildPricingDAG` activity. Acceptable, but again worth being explicit.

### 6.5 Calibration warm-up after recovery
When a Kalman workflow's worker dies and recovers, Temporal replay reconstructs the latest posterior. But if the workflow has run for months with thousands of certifications, the history will be large unless aggressive `ContinueAsNew` is used. **Every `KalmanWorkflow` must `ContinueAsNew` every K certifications**, carrying forward `(x_{t|t}, P_{t|t}, model_id, cdm_v, last_input_snapshot_set)` into the new run. Forgetting to carry `P_{t|t}` is silent posterior corruption.

### 6.6 SBL cascade-recall topology
Cascade recalls (Bob recalls from Charlie because Alice recalled from Bob) are saga patterns spanning multiple workflows. Temporal handles this well in principle — a `CascadeRecallSagaWorkflow` waits on confirmations from child `RecallWorkflow` instances, with compensation = buy-in. The awkwardness: **deadline propagation**. A 2-business-day recall window must be subdivided across the cascade depth, and getting the sub-deadlines right under variable cascade depths is a property the saga must enforce explicitly. Mark this as a place where Temporal helps but does not solve the problem.

---

## 7. Idempotency-key algebra (the small canonical set)

The 19 panels surface the same small set, in different naming. Phase 2 should standardise:

| Key | Construction | Where enforced |
|---|---|---|
| `unit_id` | `hash(canonical_serialise(terms_blob))` (listed) / CDM Trade key (OTC) / mandate_id | Workflow ID for `RegisterUnitWorkflow`; StateDelta executor reject on duplicate |
| `tx_id` | `hash(source_lifecycle_event_id, source_workflow_run_id, attempt_seq=0)` | Executor commit activity dedup table |
| `business_event_id` | Stable from upstream CDM payload; or `hash(event_intent, source_unit_id, t_logical)` | Lifecycle workflow's processed-set state (carried via ContinueAsNew) |
| `obligation_id` | `hash(source, type, registered_at_tx_id)` | `ObligationWorkflow` workflow ID |
| `signal.idempotency_token` | Sender-generated UUID + timestamp | Workflow's signal-dedup set (carried via ContinueAsNew) |
| `snap_id` | `hash(observable_set, source_set, t_observed_max, t_known_max, schema_v)` | Snapshot store |
| `(unit_id, version_seq)` | Sequence-counter on TermsVersion | ProductTerms append-only invariant |
| `(workflow_id, run_id)` | Temporal-managed | Temporal cluster |
| `(calibrated_object_id, certification_timestamp, model_id)` | Kalman workflow output | Calibration store |

**Total: 9 canonical key shapes.** Every leaf in §2–4 is keyed by one of these.

---

## 8. Summary and counts

- **Total leaves covered:** 31 across 3 classes + 4 cross-cutters.
- **Distribution of ingress shape:**
  - Activity result: 18 (class 2 Definitions and most class 4 Effects)
  - Signal: 7 (corporate actions, fixings, discharge, calendar updates, key rotation, amendments, valuation publish)
  - ScheduledWorkflow / Singleton long-running: 3 (Kalman per object, party monitor, calendar update orchestrator)
  - ChildWorkflow fan-out: 2 (corporate-action processing, regulatory reporting)
  - Pre-registered: 4 (smart-contract code, CDM enums, ISO enums, activity options)
  - Direct subscription: 0 (intentionally — workflows do not subscribe to streams)
- **Awkward-fit categories named (§6):** 6 — calendar retroactive amendments; high-frequency tick streams; bitemporal correction semantics; pricing DAG topology object; Kalman ContinueAsNew discipline; SBL cascade-recall deadline propagation.
- **Canonical idempotency keys:** 9.
- **Replay-determinism risk register:** raw market observable, calibrated parameters, UnitStatus reads, ContinueAsNew payload completeness, party reference bitemporal LEI, BusinessEvent ID stability, calendar version pinning. Each requires the same discipline: **read once via activity, capture result (or `snap_id`) in history, read from history on replay.**
- **File path:** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/work/phase2/temporal.md`.

---

*End of Phase 2 Temporal synthesis.*
