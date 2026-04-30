# Phase 1 Data Enumeration — Temporal.io Discipline

**Author:** Arjun Mehta (Temporal workflow design, determinism, replay safety)
**Phase:** 1 (independent enumeration, prior to Phase 2 Data Team consolidation)
**Date:** 2026-04-29
**Source documents read:**
- `Ledger_Spec_v11.0/ledger/ledger_v10.3.tex` (skimmed end-to-end; deep reads on §1–§3, §7 lifecycle, §10 Temporal, §10A obligation liveness)
- `Ledger_Spec_v11.0/ledger/ledger_v10.3_addendum_stateshome.tex` (full)
- `Ledger_Spec_v11.0/valuation/ledger_valuation_v1.0.tex` (full structural read; deep reads on §2 FSM, §3 ValuationRecord, §4 Greeks, §5 Kalman, §6 DAG, §7 workflows)

---

## 0. Reader's note: viewing the Ledger through a Temporal lens

The framework's correctness rests on **deterministic replay of an immutable log** — the same principle Temporal uses for workflow histories. This produces a clean separation: every datum that enters the system must either (a) be **captured into the workflow history** at the moment of arrival (signal payload, activity result, timer fire) so that replay produces the same execution, or (b) be **read from a versioned external store via an activity** that returns a snapshot-identified value, and the snapshot ID — not the value — is what gets memoised by Temporal.

If a datum violates this constraint, replay diverges and the entire chain of guarantees collapses — conservation, idempotency, time travel, PnL path-independence. The discipline below classifies every data category by this criterion.

A consequence I want to state up front, because it shapes the whole table: **`workflow.Now()` and any direct read of system clocks are forbidden** in workflow code. All "time" used in business logic — coupon dates, expiry, settlement dates, observation windows — must come from either CDM `EconomicTerms` (captured at unit registration), Temporal timer fires (captured in history), or activity-returned timestamps (captured as activity results). The temporal posture of every datum below is fixed by this rule.

---

## 1. Argument with the proposed floor categories

The floor categories I was given are: 1. Static, 2. Reference, 3. Market, 4. Oracle, 5. Smart-contract execution, 6. Listed-instrument detail.

I have three structural disagreements with this taxonomy, which I list before the enumeration so the table that follows is read against the right backdrop.

**(D1) "Listed-instrument detail" is not a peer of the others — it is a sub-category of Reference.** The Ledger spec deliberately treats listed and OTC distinctly only at the level of *unit identity* (§3.2, fungibility): listed instruments are identified by contract specification; OTC by the full CDM Trade including Collateral. But the *data* describing both lives in Tier 1 (reference) and Tier 3 (unit registry). Promoting "listed-instrument detail" to a floor category implies OTC-instrument detail is missing or different — it isn't; OTC instrument detail is just the CDM Trade body, which is also reference data once executed. I will fold "listed-instrument detail" into **Reference** as a sub-class and add a parallel **OTC-instrument detail** sub-class to make the symmetry explicit.

**(D2) "Static" and "Reference" overlap dangerously.** What does "static" mean that "reference" does not? The StatesHome addendum (v10.3 A1) makes this precise: `ProductTerms[u]` is *immutable and versioned* — that is the truly static layer. `UnitStatus[u]` is *mutable and shared* — that is what reference systems normally call "reference data updates" (corporate action announcements, lifecycle stage changes, superseded_by pointers). The proposed taxonomy collapses what the spec carefully separates. I will use **Static = ProductTerms-class data** (immutable, append-only versioned) and **Reference = UnitStatus-class data plus environment data not specific to any unit** (calendars, holidays, FX cross codes, ISO 20022 schemas, regulatory thresholds).

**(D3) "Smart-contract execution" is not a *data* category — it is a *processing* category.** Smart contracts produce moves and state deltas as outputs; they consume data of the other categories as inputs. Putting "smart-contract execution" alongside "market" and "oracle" mixes a verb with nouns. I will replace it with **Lifecycle execution outputs** (the moves, state deltas, and obligations that flow *out* of pure lifecycle functions back into the executor and the obligation store) — these are real data with provenance and idempotency keys, and they need a category. I will also add **Smart-contract code & versioning** as part of category 1 (Static), because the code itself is immutable, versioned, and identified.

**(D4) "Oracle" needs splitting.** The valuation document distinguishes *raw market observables* (spot, deposit rates, option prices) — what it calls "Attestations" in §5.7 — from *calibrated parameter estimates* (Kalman posterior means, certified yield curves, vol surface coefficients). They have different temporal semantics, different idempotency keys, different replay disciplines. Treating them as one category hides the most important determinism boundary in the entire valuation stack. I will keep one floor category labelled **Oracle / Market data** but split it explicitly into **4a Raw observables** and **4b Calibrated parameters**.

I have therefore enumerated **38 data items across 9 sub-categories** below, mapped against the 6 floor categories with the structural revisions above. I have also added **two categories that the floor list omits entirely**: **7. Obligation data** and **8. Workflow orchestration data** — both are first-class data in the v10.3 + valuation v1.0 spec and are silently load-bearing for liveness and replay.

---

## 2. The mandatory seven fields per item — plus the three Temporal fields

Every item below has the seven mandatory fields plus three Temporal-discipline fields:

1. **Canonical name**
2. **Definition**
3. **Minimum field set**
4. **Identity** (key by which the item is uniquely addressed)
5. **Provenance** (where it comes from)
6. **Temporal semantics** (point-in-time / as-of / bitemporal / append-only)
7. **Failure consequences** (what breaks if this datum is wrong, missing, or non-replayable)
8. **(a) Temporal entry pattern** — signal / query / activity / scheduled / timer fire / pre-registered
9. **(b) Determinism posture under replay** — immutable snapshot vs. live activity call vs. memoised activity result
10. **(c) Idempotency key construction** — exact key shape for de-dup at workflow and activity boundaries

---

## 3. Category 1 — Static (ProductTerms-class: immutable, versioned, append-only)

### 1.1 ProductTerms

1. **Canonical name:** `ProductTerms[u]`
2. **Definition:** The immutable, versioned, append-only contractual terms of a unit `u`. Per StatesHome addendum §2, this is one of the three state maps; `Map[UnitId, NonEmptyList[TermsVersion]]`, total on registered `u`.
3. **Minimum field set:** `{unit_id, version_seq, multiplier, currency, expiry, contract_spec | cdm_trade_ref, issuer, fee_schedule, mandate_text (if MA), benchmark_identity (if QIS), index_methodology (if QIS), is_fungibility_preserving: TermsAmendment → Bool, registration_timestamp, registered_by_tx_id}`
4. **Identity:** `unit_id` (deterministic from CDM object: ContractSpec hash for listed; CDM Trade UTI for OTC; freshly allocated UnitId for issued strategies/mandates)
5. **Provenance:** Reference data feed (listed), execution report / CDM Trade payload (OTC), Unit Store registration request (mandates, QIS), corporate action announcement (split, merger creating `u_new` via SupersededBy)
6. **Temporal semantics:** Append-only versioned. Each `TermsVersion` is point-in-time at its registration timestamp; the list as a whole is bitemporal (knowledge time = version sequence; valid time = the term contents)
7. **Failure consequences:** Wrong terms → wrong moves → wrong PnL → conservation may still hold (executor enforces) but state is economically wrong. Non-replayable terms → workflow replay divergence; lifecycle workflows that read terms from a non-versioned source produce different moves on replay. **Re-registration is a hard error (C10 of StatesHome).**
8. **(a) Temporal entry pattern:** Activity result, captured at unit registration. The lifecycle workflow's first activity reads `ProductTerms[u]` and the result is memoised in workflow history. Subsequent reads on replay return the memoised value.
9. **(b) Determinism posture:** Immutable snapshot — once read into the workflow on registration, never re-read. Long-running workflows (30-year bond) carry the relevant ProductTerms fields explicitly into `ContinueAsNew` payload to avoid re-querying.
10. **(c) Idempotency key:** `(unit_id, version_seq)`. For amendment two-track (C8 of StatesHome): preserving amendments append a TermsVersion (idempotency key extends to `(unit_id, new_version_seq)`); breaking amendments allocate `u_new` and emit an atomic re-subscription StateDelta, keyed by `(u_old, u_new, amendment_event_id)`.

### 1.2 Smart-contract code & version

1. **Canonical name:** `SmartContractRef`
2. **Definition:** The pure lifecycle function `f : (unit, state, market_data) → (moves, new_state, obligations)` for a product type, identified by reference and version.
3. **Minimum field set:** `{contract_id, code_hash, version, supported_event_intents: Set[CDM.EventIntentEnum], cdm_qualification: ProductQualification → Bool}`
4. **Identity:** `(contract_id, version)`
5. **Provenance:** Internal code repository, registered into Tier 2 product registry by the deploy pipeline.
6. **Temporal semantics:** Append-only. New versions are added; old versions are never modified. Workflows pin to a version via Temporal's `GetVersion` API (§10.13 of ledger spec).
7. **Failure consequences:** A workflow running against a different code version on replay than at original execution produces non-determinism error and aborts. This is the determinism contract of Temporal. The framework's purity principle (§7.7 of ledger) is the necessary but not sufficient condition; version pinning is the rest.
8. **(a) Temporal entry pattern:** Pre-registered. The worker's binary contains the code; the Temporal SDK records the code version in workflow history via `GetVersion`/`patched`.
9. **(b) Determinism posture:** Immutable snapshot — workflow code is the same on every replay because Temporal pins it.
10. **(c) Idempotency key:** N/A at the data level; idempotency lives in transaction-ID checks (Invariant 5) and lifecycle-event idempotency (Invariant 6) on the *output* of the contract.

### 1.3 ISO 4217 currency code, exchange code, CCP identifier (truly static enums)

1. **Canonical name:** `EnumeratedConstants`
2. **Definition:** Closed enumerations referenced by ProductTerms but maintained outside the unit (ISO 4217 currency codes, ISO 10383 MIC exchange codes, CCP identifiers, CDM enum universe).
3. **Minimum field set:** `{enum_name, value, iso_standard_version, effective_date, deprecation_date | None}`
4. **Identity:** `(enum_name, value)`
5. **Provenance:** ISO standard bodies, FINOS CDM release schedule, internal taxonomy maintenance.
6. **Temporal semantics:** Append-only with deprecation. New values are added; values are never removed (only deprecated with effective dates).
7. **Failure consequences:** A unit referencing a deprecated enum value will validate on registration and continue to operate; the framework does not retroactively reject. New enum values arriving via CDM release require the lifecycle state machine to handle them — Section 10.13 of ledger spec describes the coordination.
8. **(a) Temporal entry pattern:** Pre-registered in the worker; loaded at startup, captured into workflow history via `GetVersion` if the enum set changes mid-workflow.
9. **(b) Determinism posture:** Immutable snapshot per CDM/ISO version. Workflows that span CDM version boundaries (30-year bond) handle this via `patched`/`GetVersion` plus `ContinueAsNew` at version uplift.
10. **(c) Idempotency key:** `(cdm_version, enum_name, value)`.

### 1.4 Calendar definitions

1. **Canonical name:** `BusinessCalendar`
2. **Definition:** Holiday and business-day calendars referenced by CDM `BusinessDayAdjustments` to convert nominal dates into actual settlement / coupon / observation dates.
3. **Minimum field set:** `{calendar_id, jurisdiction, year, holiday_dates: Set[Date], weekend_convention, half_day_dates: Set[Date]}`
4. **Identity:** `(calendar_id, year)`
5. **Provenance:** Exchange / CSD publications, vendor reference data (ICE, Refinitiv).
6. **Temporal semantics:** As-of (the calendar known at knowledge time `t` may differ from the calendar known later if a jurisdiction announces a new holiday after the fact). Bitemporal in operational practice: most workflows use the calendar as-known at unit registration; corrections trigger a re-evaluation.
7. **Failure consequences:** A coupon timer fired on the wrong adjusted date violates the lifecycle obligation deadline and may cause settlement failure. Pure replay error mode: if the workflow reads the calendar as a live activity on every replay and the calendar has changed, the date computation diverges.
8. **(a) Temporal entry pattern:** Activity result captured at unit registration. The full coupon schedule is computed once (CDM `CalculationPeriodFrequency` + `BusinessDayAdjustments` + calendar) and the resulting list of adjusted dates is stored in workflow state. Calendar updates announced after registration are applied via a signal that triggers a schedule recalculation, with the new schedule replacing the old in workflow state.
9. **(b) Determinism posture:** Immutable snapshot post-registration; replay reads the captured schedule, not the live calendar.
10. **(c) Idempotency key:** `(calendar_id, jurisdiction, knowledge_timestamp)` for the calendar version; `(unit_id, schedule_version_seq)` for the workflow's stored schedule.

---

## 4. Category 2 — Reference (UnitStatus-class plus environment data)

### 2.1 UnitStatus

1. **Canonical name:** `UnitStatus[u]`
2. **Definition:** The shared, mutable, per-unit lifecycle state. Per StatesHome addendum §2: `Map[UnitId, UnitStatus]`, total on registered `u`, mutable, shared across all holders.
3. **Minimum field set:** `{unit_id, lifecycle_stage: {LISTED, ACTIVE, MATURED, TERMINATED, EXPIRED, SETTLED}, last_settlement_price | None, last_settlement_date | None, current_weights (QIS), nav_index (QIS), triggered_barrier: Bool, superseded_by: UnitId | None, vol_realised (QIS)}`
4. **Identity:** `unit_id`
5. **Provenance:** Lifecycle workflow activities (settlement events update `last_settlement_price`; barrier breach activities set `triggered_barrier`; corporate actions write `superseded_by`).
6. **Temporal semantics:** Point-in-time current; full history reconstructible from the event log (each mutation is a state-only transaction in the move stream — §7 of ledger).
7. **Failure consequences:** A pricing workflow that reads `last_settlement_price` from a stale `UnitStatus` view computes wrong VM. Conservation still holds (executor enforces per-event); but the *value* of moves is wrong.
8. **(a) Temporal entry pattern:** Activity result. Each lifecycle workflow invokes `view.unit_status(u)` as an activity; the result is memoised in workflow history. **Critical:** the workflow must not subscribe to `UnitStatus` as a long-lived observer — every read is a fresh activity call against the current state.
9. **(b) Determinism posture:** Activity result captured per invocation. On replay, Temporal returns the memoised value, not the current `UnitStatus`. This is correct: the original execution saw a specific value, and replay must reproduce it.
10. **(c) Idempotency key:** Mutations are keyed by the transaction ID of the state-only transaction that wrote them: `tx_id` (Invariant 5). Reads are not idempotency-keyed; they are pure projections.

### 2.2 Counterparty / party reference data

1. **Canonical name:** `PartyReference`
2. **Definition:** Identity and metadata for every counterparty modelled as a virtual wallet (§2.5 of ledger).
3. **Minimum field set:** `{party_id, lei, legal_name, jurisdiction, regulatory_classifications: Set[Classification], cdm_party_role, default_csa_id | None}`
4. **Identity:** `lei` (primary), `party_id` (internal alias)
5. **Provenance:** GLEIF for LEI authority; legal/onboarding for internal aliases; KYC data feeds for jurisdiction and classifications.
6. **Temporal semantics:** As-of / bitemporal. A party's classification can change (e.g., a fund's MiFID II classification reassessed); corrections require knowledge-time tracking.
7. **Failure consequences:** Wrong party data cascades into wrong CSA, wrong regulatory reporting, wrong settlement instructions. Affects SFTR/EMIR/SLATE reporting completeness (P16, P19 of ledger).
8. **(a) Temporal entry pattern:** Activity result. The lifecycle workflow reads party data on demand for events that depend on counterparty (margin call, settlement instruction generation).
9. **(b) Determinism posture:** Activity result memoised per invocation. **Replay sensitivity:** if a party's LEI is reassigned (rare, but documented), historical workflows must still reproduce the old LEI. Use bitemporal queries: `read_party(party_id, as_of_knowledge=workflow_start_time)`.
10. **(c) Idempotency key:** `(party_id, knowledge_timestamp)` for the bitemporal read.

### 2.3 ISDA Master Agreement / CSA terms

1. **Canonical name:** `MasterAgreementTerms`
2. **Definition:** The legal-agreement-level configuration that governs OTC trades between two parties (ISDA Master + CSA + Schedule).
3. **Minimum field set:** `{agreement_id, parties: Pair[lei], threshold, minimum_transfer_amount, eligible_collateral_schedule, posting_currency, valuation_methodology, IM_regime: {Reg-IM, AANA, exempt}, close_out_provisions, governing_law, version_seq}`
4. **Identity:** `agreement_id` (and version for amendments)
5. **Provenance:** Legal documentation; collateral management system; Sections 6.4, 14.6 of ledger spec.
6. **Temporal semantics:** Versioned append-only — same C8 amendment discipline as ProductTerms (preserving = append version; breaking = new agreement). Bitemporal in practice (knowledge time = when amendment was signed; valid time = when amendment takes effect).
7. **Failure consequences:** Wrong CSA terms → wrong margin call computation → wrong margin obligation → potential close-out netting on a healthy book. P12 (Collateral Sufficiency invariant) depends on accurate CSA reads.
8. **(a) Temporal entry pattern:** Activity result, read at margin call computation time. CSA terms don't change frequently; the activity result is stable. CSA amendments arrive as signals.
9. **(b) Determinism posture:** Activity result memoised. On replay of a historical margin computation, the CSA version-as-of-then is what matters.
10. **(c) Idempotency key:** `(agreement_id, version_seq)`; for the obligation it spawns: `(agreement_id, computation_date, "VM" | "IM")`.

### 2.4 Settlement infrastructure reference (CSD, custodian, CCP routing)

1. **Canonical name:** `SettlementVenueReference`
2. **Definition:** Mapping from internal wallet identity to external settlement endpoints (CSD account, custodian SSI, CCP clearing member).
3. **Minimum field set:** `{wallet_id, csd_account, custodian_lei, ssi: SettlementInstruction, ccp_clearing_member, default_cutoff_times: Map[Currency, Time], iso20022_routing_codes}`
4. **Identity:** `wallet_id`
5. **Provenance:** Settlement layer (§9 of ledger), operations team, CSD onboarding.
6. **Temporal semantics:** As-of. SSIs change; cutoff times change. The settlement projection must use the SSI valid at instruction-generation time.
7. **Failure consequences:** Wrong SSI → settlement instruction routes to wrong account → settlement fail or misallocation. Detected only at confirmation return path.
8. **(a) Temporal entry pattern:** Activity result inside `SettlementWorkflow` enrichment step (§10.5 of ledger).
9. **(b) Determinism posture:** Activity result memoised. Each settlement workflow captures the SSI used at that specific instruction generation; subsequent SSI changes do not retroactively alter the instruction.
10. **(c) Idempotency key:** `(wallet_id, knowledge_timestamp)`; the resulting settlement instruction is keyed by `(transaction_id, settlement_leg_index)`.

### 2.5 Regulatory thresholds and reporting jurisdictions

1. **Canonical name:** `RegulatoryRuleset`
2. **Definition:** Per-jurisdiction reporting deadlines and thresholds (SFTR T+1, EMIR T+1, SLATE T+1, MiFID II RTS 25, MiFIR clearing thresholds).
3. **Minimum field set:** `{jurisdiction, regime: {SFTR, EMIR, SLATE, MIFID, FINRA}, deadline_calculation_rule, threshold_amounts, reportable_event_types: Set[CDM.EventIntentEnum], effective_date, sunset_date | None}`
4. **Identity:** `(regime, jurisdiction, effective_date)`
5. **Provenance:** Regulatory bodies; legal team interpretation; configuration tables.
6. **Temporal semantics:** Bitemporal. A trade booked under MIFID I rules at `t` must be reported under those rules even after MIFID II takes effect.
7. **Failure consequences:** Missed regulatory deadline → fine. The obligation framework (P21–P23 of ledger §10A) creates a regulatory reporting obligation per reportable event; failure to discharge fires compensation = regulatory escalation.
8. **(a) Temporal entry pattern:** Activity result, read by the reporting workflow when it formats and submits the report.
9. **(b) Determinism posture:** Activity result memoised. Workflow ID encodes the reportable-event ID, so a single workflow per report = natural idempotency.
10. **(c) Idempotency key:** `(reportable_event_id, regime)` for the reporting workflow start.

---

## 5. Category 3 — Listed-instrument detail (sub-class of Reference; symmetric OTC sub-class)

I argued above (D1) that this is a sub-category of Reference. I list the items here for completeness but note the structural redundancy.

### 3.1 Exchange contract specification

1. **Canonical name:** `ContractSpec`
2. **Definition:** The full exchange-published specification of a listed contract (option series, futures contract).
3. **Minimum field set:** `{exchange_mic, product_id, underlier_id, contract_type: {OPTION_CALL, OPTION_PUT, FUTURE}, strike, expiry, multiplier, settlement_type: {PHYSICAL, CASH}, settlement_currency, last_trading_date, first_notice_date (futures), tick_size, lot_size}`
4. **Identity:** `(exchange_mic, product_id)` — this is what the unit_id hashes for listed instruments.
5. **Provenance:** Exchange contract specification feed (CME ClearPort, ICE, Eurex).
6. **Temporal semantics:** Append-only at the contract listing level; the spec is fixed once a contract is listed.
7. **Failure consequences:** Wrong multiplier in particular is catastrophic — every VM computation is off by orders of magnitude. Wrong expiry causes the exercise workflow to fire on the wrong date.
8. **(a) Temporal entry pattern:** Activity result captured at unit registration; thereafter the multiplier/expiry/strike are part of the workflow's frozen ProductTerms snapshot.
9. **(b) Determinism posture:** Immutable snapshot.
10. **(c) Idempotency key:** Folded into ProductTerms idempotency: `(unit_id, version_seq=1)` since contract specs do not version.

### 3.2 OTC trade detail (CDM Trade body)

1. **Canonical name:** `CDMTrade`
2. **Definition:** The full CDM `Trade` object that *is* the unit definition for OTC instruments (per §3 of ledger). Includes counterparty, EconomicTerms, Collateral.
3. **Minimum field set:** `{uti, mui, cdm_trade_payload: CDM.Trade, counterparty: Pair[lei], execution_timestamp, csa_reference, qualified_product_type}`
4. **Identity:** `uti` (Unique Trade Identifier)
5. **Provenance:** Execution venue / OMS / counterparty confirmation matched via CDM `BusinessEvent`.
6. **Temporal semantics:** Append-only. The CDM Trade object is canonical at execution; lifecycle events are recorded as separate `BusinessEvent`s, never as mutations.
7. **Failure consequences:** Mis-mapping of CDM Trade → wrong unit_id → conservation may still hold but on the wrong unit. Per §3.2, OTC fungibility is broken by counterparty + CSA, so unit_id collisions are economically wrong.
8. **(a) Temporal entry pattern:** Signal at execution time → workflow start. The full CDM Trade payload is passed as workflow input; idempotency via UTI prevents double-start.
9. **(b) Determinism posture:** Immutable snapshot — captured into workflow history at start.
10. **(c) Idempotency key:** `uti` at workflow level (Temporal rejects duplicate workflow IDs); `(uti, business_event_id)` at the lifecycle event level.

---

## 6. Category 4 — Market / Oracle (split into 4a Raw observables and 4b Calibrated parameters)

### 4a.1 Raw market observable

1. **Canonical name:** `MarketObservation`
2. **Definition:** A single attestation of an observable market quantity at knowledge time `t` from a specific source (per §5.7 of valuation: "Attestations" = raw quotes feeding the Kalman filter).
3. **Minimum field set:** `{observable_id, source: SourceIdentifier, observed_value: Decimal, observation_timestamp, knowledge_timestamp, source_quality_flag, raw_payload}`
4. **Identity:** `(observable_id, source, observation_timestamp, knowledge_timestamp)`
5. **Provenance:** Exchange feed, ECN, vendor (Bloomberg, Refinitiv, ICE).
6. **Temporal semantics:** **Bitemporal** — knowledge time (when we received it) and valid time (when the market produced it) must both be tracked. Vendor corrections and late fixes arrive with knowledge_timestamp later than observation_timestamp.
7. **Failure consequences:** Wrong observation feeds wrong calibration (4b) → wrong price → wrong VM → conservation still holds (executor) but the cash move is at the wrong price. Replay risk: if a workflow reads "current market data" via a non-versioned activity, replay produces a different value than the original execution.
8. **(a) Temporal entry pattern:** **This is the most replay-hostile data category.** Pattern: activity call that returns a `(SnapshotId, observed_value)` pair. The SnapshotId is what gets memoised; downstream activities re-read the value via SnapshotId, producing identical results on replay. **Never:** workflow code that calls `marketdata.get_spot(symbol)` directly — that breaks replay determinism.
9. **(b) Determinism posture:** Activity result with SnapshotId. The "deterministic oracle" requirement of §7.7 of ledger ("market data used by each lifecycle invocation is captured and stored at the time of execution"). Replay reads the stored snapshot, not the live feed.
10. **(c) Idempotency key:** `SnapshotId` (typically a hash of `(observable_id, source, observation_timestamp, knowledge_timestamp)`); the snapshot store is the idempotency boundary.

### 4a.2 Market data quality / staleness flags

1. **Canonical name:** `DataQualityFlag`
2. **Definition:** Per-observable quality metadata used by §10.13 of ledger ("Data quality gating") to defer lifecycle events when data is stale or fails cross-source validation.
3. **Minimum field set:** `{observable_id, source, freshness_seconds, cross_source_consistency: Bool, staleness_threshold, gating_decision: {ACCEPT, DEFER, REJECT}}`
4. **Identity:** `(observable_id, source, evaluation_timestamp)`
5. **Provenance:** Market data ingestion layer, internal consistency checker.
6. **Temporal semantics:** Point-in-time at evaluation. Re-evaluated each time a workflow checks freshness.
7. **Failure consequences:** A coupon payment computed against stale market data produces wrong accrual. The data-quality gate (§10.13) is the safety net; if it is wrong, the gate either fires too aggressively (deferring valid events past their deadline → P21 obligation default) or too laxly (using stale data → wrong moves).
8. **(a) Temporal entry pattern:** Activity result inside `RetrieveMarketData` activity (per §10.4 of ledger Bond example).
9. **(b) Determinism posture:** Activity result memoised. **Subtle:** the gating decision must be captured into workflow history, not recomputed on replay — otherwise a previously-deferred event might be re-decided differently on replay.
10. **(c) Idempotency key:** Same as 4a.1 — `SnapshotId` covers both value and quality flags.

### 4b.1 Calibrated parameter vector (Kalman filter posterior)

1. **Canonical name:** `CalibratedParams`
2. **Definition:** The certified posterior mean `x_{t|t}^certified` of the Kalman filter for a calibrated object (yield curve, vol surface, hazard curve). Per §5.7 of valuation.
3. **Minimum field set:** `{calibrated_object_id, params_vector: Vector, posterior_covariance: Matrix, certification_timestamp, observations_consumed: Set[SnapshotId], no_arbitrage_certified: Bool, innovation_statistics: {mahalanobis_d2, gating_decision}, model_id}`
4. **Identity:** `(calibrated_object_id, certification_timestamp)`
5. **Provenance:** Dedicated Kalman filter Temporal workflow (§5.7) per calibrated object. Inputs: raw observations (4a.1).
6. **Temporal semantics:** Append-only at the certified-snapshot level. Each certification is point-in-time; the sequence is bitemporal because re-runs with corrected raw observations produce restated calibrations.
7. **Failure consequences:** Wrong calibration → wrong Greeks → wrong PnL explain → false QUARANTINED state → wasted retries → potential STALE drop and downstream risk teams alerted. Cross-asset coherence (§5.10): asynchronous calibrations mark composite products as INDICATIVE.
8. **(a) Temporal entry pattern:** Signal-driven. The Kalman workflow signals downstream pricing workflows when a new certified calibration is available (§5.7 footer: "exactly like a market data node in the Pricing DAG"). Pricing workflows subscribe via signal channel.
9. **(b) Determinism posture:** Activity result captured at the moment of pricing. The pricing workflow reads `CalibratedParams[id, certification_timestamp]` once per pricing cycle; replay reads the memoised value.
10. **(c) Idempotency key:** `(calibrated_object_id, certification_timestamp)`. The certification timestamp is monotone within a calibration object; combined with `observations_consumed` it gives full re-derivability.

### 4b.2 Pricing DAG snapshot

1. **Canonical name:** `PricingDAGSnapshot`
2. **Definition:** A frozen topology of `(N_U ∪ N_M ∪ N_C, E)` over which a single pricing cycle operates. Per §6.3 of valuation: "a single cycle always operates on a frozen topology."
3. **Minimum field set:** `{dag_version, topology_hash, nodes: Set[NodeId], edges: Set[(NodeId, NodeId)], topo_order: List[NodeId], frozen_at_timestamp}`
4. **Identity:** `(dag_version, topology_hash)`
5. **Provenance:** `BuildPricingDAG` (§6.1 of valuation), invoked at registration / mutation events.
6. **Temporal semantics:** Append-only at the version level. DAG mutations take effect on the next cycle.
7. **Failure consequences:** A cycle that processes mid-mutation reads an inconsistent topology → freshness checks become non-deterministic → workflows may proceed with stale upstream or block on non-existent dependencies.
8. **(a) Temporal entry pattern:** Pre-computed; passed as input to each `PricingWorkflow` cycle. Mutations propagated via signals to all `PricingWorkflow` instances at cycle boundaries.
9. **(b) Determinism posture:** Immutable snapshot per cycle.
10. **(c) Idempotency key:** `(dag_version, cycle_start_timestamp)`.

### 4b.3 ValuationRecord (output of pricing)

1. **Canonical name:** `ValuationRecord` (see Definition 3.1 of valuation)
2. **Definition:** The full pricing output — `dirty_price`, `clean_price`, `accrued`, `greeks`, `model_id`, `market_data_snap`, `quality`, `fsm_state`.
3. **Minimum field set:** see Definition 3.1; plus `valuation_workflow_run_id`, `prev_valuation_record_id` for chain.
4. **Identity:** `(unit_id, timestamp, valuation_workflow_run_id)`
5. **Provenance:** `PricingWorkflow.PublishValuationRecord` (§7.4 of valuation).
6. **Temporal semantics:** Append-only. Each FIRM record is an immutable snapshot; STALE / APPROXIMATE records reference earlier FIRM records by ID.
7. **Failure consequences:** A wrongly published record propagates to all downstream pricing nodes via DAG signalling; a non-FIRM quality flag triggers prudential haircuts but does not stop processing.
8. **(a) Temporal entry pattern:** Activity result of the `PublishValuationRecord` activity, read by downstream pricing workflows via signal.
9. **(b) Determinism posture:** Activity result memoised in the producer workflow; SnapshotId-style reference for consumers.
10. **(c) Idempotency key:** `(unit_id, valuation_workflow_run_id, cycle_seq)`.

### 4b.4 Sensitivity Jacobian

1. **Canonical name:** `SensitivityJacobian`
2. **Definition:** The full parameter-sensitivity row vector `J = (∂P/∂θ_1, ..., ∂P/∂θ_n)` for a unit under a specific model. Per §4.4 of valuation.
3. **Minimum field set:** `{unit_id, model_id, jacobian: Vector[n], parameter_labels: List[String], computed_at_timestamp, observable_basis_snapshot_id}`
4. **Identity:** `(unit_id, model_id, computed_at_timestamp)`
5. **Provenance:** `ComputeGreeks` activity within `PricingWorkflow` (§7.4 of valuation), via bump-and-revalue.
6. **Temporal semantics:** Point-in-time per pricing cycle.
7. **Failure consequences:** Wrong Jacobian → wrong PnL explain → false QUARANTINED → unnecessary retries.
8. **(a) Temporal entry pattern:** Activity result.
9. **(b) Determinism posture:** Memoised activity result; bump-and-revalue is deterministic given the parameter snapshot.
10. **(c) Idempotency key:** `(unit_id, model_id, cycle_seq)`.

### 4b.5 PnL explain residual

1. **Canonical name:** `PnLExplainResidual`
2. **Definition:** The unexplained PnL residual `ε = ΔP − (δ·ΔS + J·ΔΘ + ½Γ·(ΔS)² + Θ_decay·Δt)` per §8 of valuation.
3. **Minimum field set:** `{unit_id, prev_valuation_id, current_valuation_id, components: {delta_pnl, parameter_pnl, gamma_pnl, theta_pnl}, residual: Decimal, tolerance: Decimal, status: {PASS, FAIL}}`
4. **Identity:** `(unit_id, prev_valuation_id, current_valuation_id)`
5. **Provenance:** `PnLExplain` activity (§7.4 of valuation).
6. **Temporal semantics:** Point-in-time per cycle.
7. **Failure consequences:** Drives FSM transitions T5 (PASS → EXPLAINED) vs T6 (FAIL → QUARANTINED). False FAIL wastes retries; false PASS lets bad valuations through.
8. **(a) Temporal entry pattern:** Activity result.
9. **(b) Determinism posture:** Memoised activity result.
10. **(c) Idempotency key:** Same as identity.

---

## 7. Category 5 — Smart-contract execution (renamed: Lifecycle execution outputs)

I argued above (D3) that smart-contract execution is processing, not data. The data outputs of execution are:

### 5.1 PendingTransaction (executor input)

1. **Canonical name:** `PendingTransaction`
2. **Definition:** The output of a lifecycle function — a list of moves and state deltas, plus obligations (per §10A of ledger). The input to the executor activity.
3. **Minimum field set:** `{tx_id, moves: List[Move], state_deltas: Map[(WalletId | UnitId), StateDelta], obligations: List[Obligation], source_lifecycle_event_id, source_unit_id, source_workflow_run_id, market_data_snapshot_id}`
4. **Identity:** `tx_id` (deterministic hash of `(source_lifecycle_event_id, source_workflow_run_id, attempt_seq=0)`)
5. **Provenance:** Pure lifecycle function inside a Temporal activity wrapper.
6. **Temporal semantics:** Point-in-time at workflow invocation; not persisted past executor commit (the moves and state deltas are persisted in the event log).
7. **Failure consequences:** Conservation violation in the moves → executor non-retryable rejection. Idempotency rejection (tx_id already committed) → executor returns success without re-applying — this is the desired behaviour.
8. **(a) Temporal entry pattern:** Activity result (lifecycle function) → activity input (executor commit).
9. **(b) Determinism posture:** Memoised activity result; on replay, the lifecycle function output is recovered from history without re-execution.
10. **(c) Idempotency key:** `tx_id` — Layer 1 of the three-layer idempotency chain (§10.10 of ledger).

### 5.2 Move (atomic ledger modification)

1. **Canonical name:** `Move`
2. **Definition:** Per §2.3 of ledger: source wallet, destination wallet, unit, quantity, timestamp, source contract, metadata.
3. **Minimum field set:** `{move_seq, from: WalletId, to: WalletId, unit: UnitId, quantity: Decimal (positive), coordinate (per §15 GPM): {own, onloan, borr, coll_post, coll_recv, coll_rehyp}, timestamp, source_tx_id, source_contract_id, metadata: Dict}`
4. **Identity:** `(source_tx_id, move_seq)` within the transaction; globally `(source_tx_id, move_seq)` is unique because tx_id is unique.
5. **Provenance:** Lifecycle function output via `PendingTransaction`.
6. **Temporal semantics:** Append-only — the move stream (Layer 1 per §9.1 of ledger) is the canonical immutable log.
7. **Failure consequences:** Conservation enforcement is at the executor level: any transaction whose moves do not satisfy `Σ Δ = 0` per coordinate is rejected (Invariant 1).
8. **(a) Temporal entry pattern:** Captured into the move stream as activity output of the executor commit; not separately addressed by Temporal.
9. **(b) Determinism posture:** Append-only on the ledger side; on the Temporal side, the executor's activity result (the committed `tx_id` plus any return values) is memoised.
10. **(c) Idempotency key:** Inherits `tx_id` from PendingTransaction.

### 5.3 PositionState delta (per StatesHome §2)

1. **Canonical name:** `PositionStateDelta`
2. **Definition:** The per-(wallet, unit) state-only mutation that may accompany a transaction. Per StatesHome C3: atomic across ProductTerms / UnitStatus / PositionState.
3. **Minimum field set:** `{(wallet_id, unit_id), field_diffs: Map[FieldName, FieldValue], handler_tag: String (per C11), source_tx_id}`
4. **Identity:** `(source_tx_id, wallet_id, unit_id)`
5. **Provenance:** Lifecycle function output.
6. **Temporal semantics:** Append-only at the event log level; the resulting `PositionState` map is point-in-time current with full reconstructability.
7. **Failure consequences:** Per C2, conservation must hold *per event class* (e.g., `Σ_w Δ accumulated_cost(w,u) = 0` per `Trade` and per `SettleVM`). Violation → executor rejects.
8. **(a) Temporal entry pattern:** Same as Move — part of the executor commit activity output.
9. **(b) Determinism posture:** Append-only.
10. **(c) Idempotency key:** Same as Move — `tx_id` covers both moves and state deltas (atomicity per C3).

### 5.4 Lifecycle event record / CDM BusinessEvent

1. **Canonical name:** `BusinessEvent`
2. **Definition:** The CDM `BusinessEvent` payload that triggered a transaction. Per §10 of ledger and §7 unit-state mapping.
3. **Minimum field set:** `{business_event_id, cdm_intent: CDM.EventIntentEnum, cdm_payload, source_unit_id, processed_at_timestamp, resulting_tx_id, cdm_version}`
4. **Identity:** `business_event_id`
5. **Provenance:** Either external (signal to the workflow) or internal (timer fire generating an event), wrapped in CDM by the lifecycle function.
6. **Temporal semantics:** Append-only.
7. **Failure consequences:** Lifecycle idempotency (Invariant 6) checks `business_event_id` against unit state; replay safety depends on the event log having a complete record.
8. **(a) Temporal entry pattern:** Signal payload (external events) or activity result (computed events).
9. **(b) Determinism posture:** Captured into workflow history as signal/activity result.
10. **(c) Idempotency key:** `business_event_id` — Layer 2 of the idempotency chain.

---

## 8. Category 6 — Listed-instrument detail

Folded into Category 2 / 3 (D1). Covered by 3.1 above.

---

## 9. Category 7 (added) — Obligation data

The v10.3 ledger spec dedicates §10A to obligations as a first-class object. The proposed floor categories miss this entirely. It is non-optional data.

### 7.1 Obligation

1. **Canonical name:** `Obligation` (per §10A.1 of ledger)
2. **Definition:** `o = (id, type, source, t_d, D, κ)` — a tuple specifying a deadline-bearing duty.
3. **Minimum field set:** `{obligation_id, type: ObligationType, source: {UnitId | AgreementId | EventId}, deadline_timestamp, discharge_predicate: LedgerState → Bool, compensation_action: Obligation → PendingTransaction, current_state: {Pending, Attempted, Discharged, Compensated, Defaulted}, registered_at_tx_id}`
4. **Identity:** `obligation_id` — deterministic from `(source, type, registered_at_tx_id)`.
5. **Provenance:** Lifecycle function output (per Principle 14.6.1 of ledger: obligation completeness — every obligation-creating event must register an obligation).
6. **Temporal semantics:** Append-only registry; state transitions are state-only transactions in the event log.
7. **Failure consequences:** A registered-but-unscheduled obligation defeats the liveness guarantee (P21). Lemma 2 of Theorem 14.6.7 requires deterministic spawning of an obligation workflow with a timer at `t_d`.
8. **(a) Temporal entry pattern:** Registered as part of the lifecycle activity's output (atomic with the triggering tx). The executor's post-commit hook spawns the `ObligationWorkflow` (§14.6.5) — workflow ID derived from `obligation_id`.
9. **(b) Determinism posture:** Activity result memoised; the obligation workflow is started with deterministic ID.
10. **(c) Idempotency key:** `obligation_id` (the workflow ID); discharge keyed by `(obligation_id, discharge_signal_id)`; compensation keyed by `(obligation_id, "compensation")`.

### 7.2 Obligation discharge signal

1. **Canonical name:** `DischargeSignal`
2. **Definition:** External or internal signal carrying evidence that an obligation has been discharged.
3. **Minimum field set:** `{obligation_id, ledger_state_witness: LedgerStateRef, signal_timestamp, idempotency_token}`
4. **Identity:** `(obligation_id, idempotency_token)`
5. **Provenance:** Counterparty confirmation (collateral delivery), CSD confirmation (settlement), or internal lifecycle event.
6. **Temporal semantics:** Point-in-time signal payload; memoised in workflow history on receipt.
7. **Failure consequences:** Duplicate signals must not double-discharge (P23 obligation idempotency); missed signals cause the timer to fire at `t_d` and trigger compensation unnecessarily.
8. **(a) Temporal entry pattern:** Signal to the obligation workflow.
9. **(b) Determinism posture:** Captured into history at signal receipt.
10. **(c) Idempotency key:** `idempotency_token` carried in the signal payload (per §10.3 example: `signal.idempotency_token`).

---

## 10. Category 8 (added) — Workflow orchestration data

The proposed floor categories also miss the orchestration data plane entirely. Workflow histories are *data* — they are what the framework (and Temporal) replays. They have provenance, identity, and failure consequences.

### 8.1 Workflow history record

1. **Canonical name:** `WorkflowHistory`
2. **Definition:** Temporal's append-only event log for a workflow execution. Per §10.3 of ledger: "the orchestration record... answers 'how was the orchestration sequenced?'".
3. **Minimum field set:** `{workflow_id, run_id, namespace, task_queue, workflow_type, history_events: List[HistoryEvent], current_event_count, in_continue_as_new_chain: List[run_id]}`
4. **Identity:** `(namespace, workflow_id, run_id)`
5. **Provenance:** Temporal cluster.
6. **Temporal semantics:** Append-only. Sealed at workflow completion or `ContinueAsNew`.
7. **Failure consequences:** History corruption → workflow cannot replay → orchestration is unrecoverable. Mitigated by Temporal's own replication.
8. **(a) Temporal entry pattern:** Managed by Temporal; not application data.
9. **(b) Determinism posture:** Append-only by construction.
10. **(c) Idempotency key:** `workflow_id` (start), `(workflow_id, run_id)` (run-level).

### 8.2 Workflow input parameters

1. **Canonical name:** `WorkflowInput`
2. **Definition:** The serialised input to a workflow start, including all parameters needed to resume after `ContinueAsNew`.
3. **Minimum field set (per workflow type):** for `BondCouponWorkflow`: `{unit_id, coupon_schedule, current_unit_state, processed_event_ids, cdm_version}`. For `SBLLoanWorkflow`: `{loan_id, terms, current_state, processed_tokens}`. For `PricingWorkflow`: `{unit_id, cadence, dependencies, prev_valuation_record}`.
4. **Identity:** `(workflow_id, run_id)` of the run consuming the input.
5. **Provenance:** Either external (workflow start request) or internal (`ContinueAsNew` payload).
6. **Temporal semantics:** Point-in-time at run start; carried forward across `ContinueAsNew` chains.
7. **Failure consequences:** Wrong / incomplete `ContinueAsNew` payload → workflow loses state on next run boundary → silent correctness failure (e.g., processed_tokens not carried = lifecycle idempotency violated). This is a high-priority code-review checkpoint.
8. **(a) Temporal entry pattern:** Stored in workflow history.
9. **(b) Determinism posture:** Captured.
10. **(c) Idempotency key:** Workflow ID prevents duplicate starts (§10.3 example: `futures-settle-CME-2027-03-15`).

### 8.3 Activity timeout configuration

1. **Canonical name:** `ActivityOptions`
2. **Definition:** Per §10.8 of ledger: the seven Temporal timeouts plus retry policy per activity type.
3. **Minimum field set:** `{StartToCloseTimeout, ScheduleToCloseTimeout, ScheduleToStartTimeout, HeartbeatTimeout, RetryPolicy: {InitialInterval, BackoffCoefficient, MaximumInterval, MaximumAttempts, NonRetryableErrors: List[ErrorType]}, task_queue}`
4. **Identity:** `(activity_type, deployment_version)`
5. **Provenance:** Configuration code; reviewed against latency/availability SLOs.
6. **Temporal semantics:** Versioned with deployment.
7. **Failure consequences:** Per §10.8: "Getting them wrong is a production incident." Specifically:
   - `StartToCloseTimeout` too short → false failures, unnecessary retries
   - `HeartbeatTimeout` missing on long activities (settlement confirmation, MC pricing) → worker death goes undetected
   - `ScheduleToStartTimeout` too long → queue backlog hidden
   - `NonRetryableErrors` mis-configured → conservation violation gets retried 10 times before going to DLQ
8. **(a) Temporal entry pattern:** Pre-registered in worker code.
9. **(b) Determinism posture:** Bound to the activity invocation; not part of replay state.
10. **(c) Idempotency key:** N/A.

### 8.4 Task queue identifier

1. **Canonical name:** `TaskQueueId`
2. **Definition:** The routing target for activity tasks. Per §10.7 of ledger: separate task queues for `lifecycle-workflows`, `settlement-workflows`, `executor-activities`, `market-data-activities`, `iso20022-activities`, `reporting-activities`. Per §7.5 of valuation: `pricing-fast`, `pricing-analytical`, `pricing-mc`, `pricing-greeks`, `pricing-calibration`, `pricing-workflow`.
3. **Minimum field set:** `{queue_name, worker_pool_size, sticky_execution_enabled, scaling_driver}`
4. **Identity:** `queue_name`
5. **Provenance:** Configuration / deployment.
6. **Temporal semantics:** Stable across deployments; new queues introduced at version bumps.
7. **Failure consequences:** Mixing scaling profiles on one queue (e.g., MC pricing + lifecycle timers) → backlog of one starves the other. Sticky execution failure on a misconfigured queue → unnecessary replays, performance degradation but not correctness loss.
8. **(a) Temporal entry pattern:** Pre-registered.
9. **(b) Determinism posture:** Routing only; not replay-relevant.
10. **(c) Idempotency key:** N/A.

### 8.5 Search attributes (visibility)

1. **Canonical name:** `WorkflowSearchAttributes`
2. **Definition:** Indexed fields on a workflow execution for visibility queries (§ Visibility note in my baseline knowledge; the ledger spec implicitly uses this for operations dashboards).
3. **Minimum field set:** `{unit_id, counterparty_lei, settlement_date, cdm_event_intent, fsm_state, csa_id, lifecycle_stage, regime}`
4. **Identity:** `(workflow_id, run_id)`
5. **Provenance:** Set by workflow code; indexed by Temporal Cloud / Elasticsearch.
6. **Temporal semantics:** Point-in-time current; updated mid-workflow via `UpsertSearchAttributes`.
7. **Failure consequences:** Operations cannot find a stuck workflow → MTTR balloons; not a correctness issue.
8. **(a) Temporal entry pattern:** Workflow code calls; result captured in history.
9. **(b) Determinism posture:** Captured.
10. **(c) Idempotency key:** N/A — search attributes are mutable.

---

## 11. Determinism risk register — items with the worst replay posture

The following items are **the highest-risk for replay determinism** and require the strictest discipline at code review:

| Rank | Item | Risk |
|------|------|------|
| 1 | **4a.1 MarketObservation** | Live activity calls without SnapshotId capture = guaranteed replay divergence |
| 2 | **4b.1 CalibratedParams** | Same risk pattern as 4a.1; compounded because parameters are computed from observations |
| 3 | **2.1 UnitStatus reads** | Tempting to query mid-workflow; must be activity-mediated and memoised |
| 4 | **8.2 WorkflowInput at ContinueAsNew** | Forgetting `processed_tokens` or current state = silent idempotency loss |
| 5 | **2.2 PartyReference** with bitemporal LEI changes | Easy to read "current LEI" instead of "as-of LEI" |
| 6 | **5.4 BusinessEvent** | If event ID is non-deterministic (e.g., new UUID per replay), Layer-2 idempotency fails |
| 7 | **1.4 BusinessCalendar** | Live read = different adjusted dates on replay if calendar was updated |

For each, the required discipline is the same: **read once via an activity, capture the result (or a snapshot ID) in workflow history, and read from history on replay**.

---

## 12. Floor category coverage

| Floor category | Status | Items |
|----|----|----|
| 1. Static | Covered (with redefinition per D2) | 1.1 ProductTerms, 1.2 SmartContract, 1.3 EnumeratedConstants, 1.4 BusinessCalendar |
| 2. Reference | Covered (with redefinition per D2) | 2.1 UnitStatus, 2.2 PartyReference, 2.3 MasterAgreementTerms, 2.4 SettlementVenueReference, 2.5 RegulatoryRuleset |
| 3. Listed-instrument detail | Covered (folded as sub-class per D1; OTC sub-class added) | 3.1 ContractSpec, 3.2 CDMTrade |
| 4. Market / Oracle | Covered (split per D4) | 4a.1 MarketObservation, 4a.2 DataQualityFlag, 4b.1 CalibratedParams, 4b.2 PricingDAGSnapshot, 4b.3 ValuationRecord, 4b.4 SensitivityJacobian, 4b.5 PnLExplainResidual |
| 5. Smart-contract execution | Covered (renamed to Lifecycle execution outputs per D3) | 5.1 PendingTransaction, 5.2 Move, 5.3 PositionStateDelta, 5.4 BusinessEvent |
| 6. Listed-instrument detail | Folded into Reference (D1) | — |
| **+7. Obligation data (added)** | New category | 7.1 Obligation, 7.2 DischargeSignal |
| **+8. Workflow orchestration data (added)** | New category | 8.1 WorkflowHistory, 8.2 WorkflowInput, 8.3 ActivityOptions, 8.4 TaskQueueId, 8.5 WorkflowSearchAttributes |

**Item count: 24 distinct data items.**

(Note: the table above lists each item once; items like ProductTerms or UnitStatus subsume many sub-fields, but the *data category* is one item.)

---

## 13. Notes for Phase 2 consolidation

These are observations from the Temporal lens that may matter when the Data Team aggregates inputs from multiple disciplines:

1. **The bitemporal items are a small, tractable set.** Only 2.2 PartyReference, 2.3 MasterAgreementTerms, 2.5 RegulatoryRuleset, 4a.1 MarketObservation, and 1.4 BusinessCalendar require explicit knowledge-time tracking. Other items are point-in-time or append-only-versioned. The bitemporal subset deserves a dedicated retrieval API: `read(id, as_of_knowledge=t_k)`.

2. **The idempotency keys form a small algebra.** `tx_id`, `business_event_id`, `obligation_id`, `signal.idempotency_token`, `SnapshotId`, `(unit_id, version_seq)`, `(workflow_id, run_id)`, `(calibrated_object_id, certification_timestamp)`. Phase 2 should specify the canonical hash construction for each — they are load-bearing for the three-layer idempotency chain (§10.10 of ledger).

3. **`ContinueAsNew` is a data contract.** Every long-running workflow's `ContinueAsNew` payload is part of the data spec. The minimum field set per workflow type (8.2 above) should be elevated to a first-class schema, version-managed alongside the workflow code.

4. **The valuation document introduces "Attestation" terminology** (§5.7) that does not appear in the main ledger doc. I have used the more common term "MarketObservation"; the Phase 2 team should pick one and stick with it.

5. **Cross-namespace data flow is not in v10.3.** If the platform later runs SBL and equity-trading in separate Temporal namespaces (a reasonable deployment pattern), data items 5.1 PendingTransaction and 7.1 Obligation will need cross-namespace identifiers (Nexus or signals). Out of Phase 1 scope but worth flagging.

---

## 14. Open determinism question for Phase 2

Per §10.13 of ledger: "the market data used by each lifecycle invocation is captured and stored at the time of execution (e.g., as a versioned snapshot with source, timestamp, and fallback chain)."

The spec asserts the discipline but does not specify the snapshot store's identity rules, retention, or interface. From the Temporal side, the snapshot store *is* the determinism boundary for category 4. Phase 2 needs a complete SnapshotId specification: hash construction, retention horizon (must outlive the longest-running workflow — 30 years for some bonds), back-fill rules for vendor corrections.

Without this, the chain of guarantees has a gap: Temporal memoises activity results, but the activity result is `(SnapshotId, value)` — and the snapshot store must remain authoritative for `SnapshotId → value` for the entire workflow lifetime.

---

*End of Phase 1 enumeration.*
