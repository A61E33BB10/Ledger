# Halmos Phase 1 — Data Category Enumeration for Ledger v11.0

**Reviewer:** HALMOS (mathematical exposition, notation, clarity)
**Inputs read end-to-end:**
- `ledger/ledger_v10.3.tex` (7314 lines)
- `ledger/ledger_v10.3_addendum_stateshome.tex` (490 lines)
- `valuation/ledger_valuation_v1.0.tex` (1525 lines)

**Output discipline.** Every category below carries the seven mandatory fields. Names are coined for `\ref{}`-readability: each label is a unique short kebab-case anchor with the prefix `data:` to live in its own namespace and not collide with the existing v11.0 corpus (which uses `sec:`, `def:`, `princ:`, `eq:`, `inv:`, `prop:`, `rem:`, `tab:`, `thm:`, `app:`, `fig:`). I have audited the existing label list — no `data:*` labels currently exist in v11.0.

---

## 0. Notation table (designed before writing)

The corpus already names three state maps (`ProductTerms`, `UnitStatus`, `PositionState`) and a registry sidecar (`WalletRegistry`). I adopt these verbatim — they are the destination, not a source. The data categories below are the *origin* side: where bits enter the system before any `StateDelta` is applied.

| Symbol      | Meaning (from corpus)                                          | Source       |
|-------------|----------------------------------------------------------------|--------------|
| `u`         | unit (CDM Trade for OTC; contract spec for listed; etc.)       | v10.3 §3     |
| `w`         | wallet                                                         | v10.3 §2.1   |
| `Σ`         | StateDelta                                                     | StatesHome   |
| `P_t(u)`    | dirty price function                                            | val §3       |
| `Θ`         | model parameters (martingale)                                   | val §4.1     |
| `O`         | observables                                                    | val §4.1     |
| `σ(u)`      | valuation FSM state                                             | val §2       |
| `tx_id`     | transaction id                                                 | v10.3 §10    |

Categories below use `D1, …, D14` as numeric mnemonics and `data:<short-name>` as canonical labels. Per Halmos Rule 2, I never start a sentence with a symbol; per Rule 6, terminology is fixed once and reused.

---

## 1. The corpus already names six data-shaped concepts. Cite first, coin only the gap.

Before enumerating, I cite by name every existing v11.0 noun that is data-shaped, so a fresh coinage cannot accidentally duplicate it:

- **Move Stream** — `\label{sec:ledger}` and `\label{sec:implementation}`. Append-only canonical internal record.
- **Unit Store** (three tiers: Reference Data / Product Registry / Unit Registry) — `\label{sec:unit-store}`, `\label{sec:unit-registration}`, `\label{sec:unit-validation}`.
- **WalletRegistry** — `WalletMetadata` sidecar, addendum §2. KYC, permissions, audit cursor.
- **ProductTerms / UnitStatus / PositionState** — addendum §2. The three state homes.
- **ValuationRecord** — `\label{def:valuation-record}`, val §3. Per (unit, t, model) tuple.
- **Calibration State** `x_t` — `\label{def:cal-state}`, val §5.1. Latent parameter vector under Kalman.
- **Pricing DAG** — `\label{def:pricing-dag}`, val §6.
- **Snapshot / Market data snap** — val §3 (the `market_data_snap: SnapshotId` field on `ValuationRecord`) and v10.3 §7.4 (deterministic oracle as ``versioned snapshot with source, timestamp, fallback chain'').
- **Obligation Store** — `\label{def:obligation-store}`, v10.3 §13.18.
- **Standing Settlement Instructions (SSIs)** — v10.3 §11.2 (settlement-layer-owned).
- **Reference Data feed** — v10.3 §3.3.1 (Tier 1 of Unit Store; ``read from external sources, the Ledger does not create reference data; it consumes it'').

Anything below that overlaps one of these reuses the existing name verbatim and adds a `data:` label only as an `\ref{}` anchor; coinages appear only where the corpus has no name.

---

## 2. The fourteen data categories

Each entry is laid out identically: `Canonical name` (`\label`) → seven fields. Definitions stay short by Halmos Rule 5 (resist symbols) and Rule 7 (consistent terminology).

---

### D1. Static Reference Data — `\label{data:static-reference}`

(Corpus name: **Tier 1 of Unit Store**, v10.3 §3.3.1. I adopt that name for the body and use `data:static-reference` only as the `\ref{}` anchor.)

1. **Canonical name.** Static Reference Data (Tier 1).
2. **Definition.** The instrument-master facts that are immutable for the life of an instrument and authored *outside* the Ledger by exchanges, CSDs, ISINs allocators, or vendors.
3. **Minimum field set.** `isin | cusip | sedol`, `mic` (exchange MIC), `instrument_class` (CDM `TransferableProduct` or `NonTransferableProduct`), `currency` (ISO 4217), `issuer_lei`, `multiplier` (listed derivs), `expiry`, `lot_size`, `quotation_convention`, `as_of` (vendor publication timestamp).
4. **Identity.** `(source_authority, primary_identifier, instrument_class)`. The same ISIN published by two vendors is one identity if `source_authority` is the issuing CSD; vendor-specific enrichments are D2.
5. **Provenance.** Authority chain: CSD or exchange → vendor feed → Ledger ingest. The triple `(source_authority, vendor, vendor_message_id)` must be stored with every record so a downstream auditor can trace any field to a specific upstream message.
6. **Temporal semantics.** *Bitemporal.* Effective time = the date the instrument's static fact takes effect (e.g., listing date). Knowledge time = ingest timestamp. Vendor restatements (e.g., late ISIN reassignments) are bitemporal corrections, never in-place mutation.
7. **Failure consequences.** The Unit Store cannot create a Tier 3 unit registry entry without Tier 1 (`\ref{sec:unit-registration}` requires the contract spec). Missing static data ⇒ `register()` raises `C7`/`C10` per addendum §2; the ledger refuses to book trades on an unknown instrument. A wrong static field (wrong multiplier, wrong currency) silently corrupts every trade and every `accumulated_cost`; this is the highest-blast-radius data class in the system.

---

### D2. Counterparty and Legal-Entity Reference Data — `\label{data:counterparty-reference}`

(Subsumes the v10.3 phrase ``Party reference, LEI, BIC'' used throughout §2 and §10. The corpus has no single name for this; it is implicit in `wallet.external_id`, `WalletMetadata`, and CDM `Party`.)

1. **Canonical name.** Counterparty Reference Data.
2. **Definition.** The static identification, classification, and routing facts for every legal entity that can stand at the source or destination of a move — internal entities, external counterparties, custodians, CCPs, CSDs, agents.
3. **Minimum field set.** `lei`, `bic`, `legal_name`, `jurisdiction`, `entity_type` (CDM `PartyTypeEnum`), `parent_lei`, `regulatory_classifications` (FC/NFC under EMIR; SD/MSP under CFTC; SBL counterparty classification), `kyc_status`, `kyc_renewal_date`.
4. **Identity.** `lei` is canonical; `(bic, jurisdiction)` is the fallback for non-LEI'd entities. A wallet's `external_id` (v10.3 §2.4) keys into this table.
5. **Provenance.** GLEIF for LEI; SWIFT for BIC; internal KYC system for classifications. The `(authority, retrieved_at)` pair is mandatory.
6. **Temporal semantics.** *Bitemporal.* Mergers, name changes, lapsed LEIs all need both effective and knowledge time. An LEI that lapsed three months ago but only got reported today must produce reports as-of its lapse date, not today.
7. **Failure consequences.** SFTR/EMIR/MiFIR reports require LEI; missing or stale LEI ⇒ regulatory reject. Wallet→`external_id` join breakage ⇒ virtual wallet reconciliation (v10.3 §2.4) cannot run, so external break detection silently degrades. F2 and F5 in the addendum risk register both name this class.

---

### D3. Instrument Terms — `\label{data:instrument-terms}`

(Corpus name: **`ProductTerms`**, addendum §2, line 88. I cite directly; this entry is the *inbound* instance prior to write.)

1. **Canonical name.** Instrument Terms (the inbound payload that becomes a `TermsVersion` in `ProductTerms`).
2. **Definition.** The full set of contractual parameters that, together with `unit_id`, define the economics of a single unit at a specific version.
3. **Minimum field set.** Varies by `instrument_class`:
   - Listed deriv: strike, expiry, exercise style, settlement style, multiplier, contract month.
   - Bond: coupon rate, schedule, day count, redemption, ranking, callability.
   - OTC deriv: full CDM `Trade` object including `Collateral` (CSA terms make it a unit, v10.3 §3.2).
   - QIS / managed account: mandate text, fee schedule (mgmt + perf), benchmark identity, hurdle methodology, max-position limits, fungibility predicate `is_fungibility_preserving` (C8).
4. **Identity.** `(unit_id, terms_version_index)`. Append-only; identity never reused (C6, C10).
5. **Provenance.** Trade booking system for OTC; reference-data feed for listed; mandate-document workflow for MA/QIS. Every `TermsVersion` carries `signed_by`, `effective_date`, `source_doc_uri`.
6. **Temporal semantics.** *Append-only versioned* (`NonEmptyList[TermsVersion]`). Effective time is contractual; knowledge time is when the version was written. A C8 ``Preserving'' amendment appends; a ``Breaking'' amendment allocates a fresh `unit_id` and stamps `SupersededBy`.
7. **Failure consequences.** A wrong term inside `ProductTerms` is a regulatory and economic disaster: payouts compute against it, settlements project from it, lifecycle handlers fire on its expiry. C6 (no in-place mutation) and C10 (no re-registration) are the only structural defences.

---

### D4. Unit Lifecycle Status (inbound) — `\label{data:unit-status-feed}`

(Corpus name: **`UnitStatus`**, addendum §2. This entry is the *inbound* feed: settlement-price prints, lifecycle-stage transitions, barrier observations, weight publications, NAV strikes.)

1. **Canonical name.** Unit Status Feed.
2. **Definition.** The shared-across-all-holders mutable observables that every event handler reads but that do not depend on which wallet holds the unit.
3. **Minimum field set.** `last_settlement_price`, `last_settlement_date`, `lifecycle_stage` (`LISTED|ACTIVE|MATURED|TERMINATED|SETTLED|EXPIRED|EXERCISED|ASSIGNED|NOVATED|CLOSED`), `current_weights` (QIS), `nav_index`, `triggered_barrier` flag, `last_coupon_date`, `superseded_by`.
4. **Identity.** `(unit_id, observation_timestamp)`.
5. **Provenance.** Exchange settlement prices for listed; CCP for cleared OTC; index publisher for benchmarks; QIS rebalance engine for weights; coupon calendar for fixed income. Every status update carries `(source_authority, message_id, received_at)`.
6. **Temporal semantics.** *Point-in-time* on the feed (each tick is one `(t, value)`); the *map* `UnitStatus[u]` is *as-of* the latest applied tick. Replay must restore the value as known at any historical time, so the feed log itself is *append-only* even when the projection is mutable.
7. **Failure consequences.** A missed settlement-price tick fails the EOD VM calculation (v10.3 §5.4) and stalls the futures lifecycle workflow (v10.3 §11.3.1). A wrong lifecycle-stage transition (e.g., premature `EXPIRED`) blocks valid moves at the executor (`\ref{sec:unit-validation}`). Stale NAV strikes propagate to F-tier subscriptions and produce wrong unit issuance.

---

### D5. Position State (inbound deltas) — `\label{data:position-deltas}`

(Corpus name: **`PositionState`**, addendum §2. Inbound = the per-event `StateDelta` rows before atomic apply.)

1. **Canonical name.** Position-State Deltas.
2. **Definition.** The per-`(w, u)` field changes proposed by handlers (`Trade`, `SettleVM`, `CorporateAction`, `QISRebalance`, `MandateAmend`, `SBL.*`) before the executor commits.
3. **Minimum field set.** `(wallet_id, unit_id, field_name, delta_value, handler_id, event_intent)`. Field names are the closed set tagged with their writer in C11: `accumulated_cost` (settle/trade), `hwm` (fee_crystallise), `entry_nav` (subscribe), `accrued_mgmt_fee`, `accrued_perf_fee`, `mandate_breach_flags`, `benchmark_nav_at_inception`, `ccp_binding`, the six SBL coordinates (`own`, `onloan`, `borr`, `coll_post`, `coll_recv`, `coll_rehyp`).
4. **Identity.** `(tx_id, wallet_id, unit_id, field_name)`. The `tx_id` is the executor-assigned transaction identifier (P5).
5. **Provenance.** A handler — never a human, never a feed. Every delta carries the handler's identity (one of the unique writers per C11) and a CDM `EventIntent`.
6. **Temporal semantics.** *Append-only* (the move stream is immutable, P4). The map `PositionState[w,u]` is the *fold* of all deltas with key `(w,u)`; under monotone carrier discipline (C1) rows are never garbage-collected.
7. **Failure consequences.** A delta that violates C2 (handler-class structural zero-sum) is rejected by the executor. A delta written to a field by the wrong handler (C11 violation) is a type error. A swallowed delta breaks P1 (conservation) and P2 (atomic commitment) and corrupts P9 (path-independent PnL) downstream.

---

### D6. Wallet Registry — `\label{data:wallet-registry}`

(Corpus name: **`WalletRegistry`**, addendum §2 line 96. Cited verbatim.)

1. **Canonical name.** Wallet Registry.
2. **Definition.** Per-wallet metadata that is *not* state and carries no economic content: KYC, permissions, audit cursor, real-vs-virtual flag, mapping to D2's LEI.
3. **Minimum field set.** `wallet_id`, `is_virtual` (real vs virtual, v10.3 §2.4), `external_lei`, `account_type` (book, sub-account, CCP mirror, custodian mirror, CSA collateral), `permissions`, `kyc_status`, `audit_cursor`.
4. **Identity.** `wallet_id`, drawn from a global namespace where virtual wallets are deterministically constructed from `(counterparty_lei, account_suffix)` (v10.3 §2.4).
5. **Provenance.** Account-opening workflow; for virtuals, derived deterministically from D2.
6. **Temporal semantics.** *Bitemporal* (KYC renewal dates, permissions changes, account closures all have effective dates separate from booking dates).
7. **Failure consequences.** A missing wallet ⇒ executor rejects every move citing it (P3 referential integrity). Wrong `is_virtual` flag ⇒ silent inter-entity break (P7 isolation invariant). Stale KYC ⇒ regulatory exposure but no data-correctness failure.

---

### D7. Move Stream — `\label{data:move-stream}`

(Corpus name: **Move Stream**, v10.3 §10.1. Cited verbatim.)

1. **Canonical name.** Move Stream.
2. **Definition.** The append-only, immutable canonical internal record of every atomic move with full provenance.
3. **Minimum field set.** `move_id`, `tx_id`, `from_wallet`, `to_wallet`, `unit_id`, `quantity` (positive), `economic_timestamp`, `booking_timestamp`, `source_contract`, `metadata` (CDM event payload, ISO 20022 ids, counterparty refs, `corrects` ref for compensating moves).
4. **Identity.** `move_id`, lexicographically unique across the lifetime of the deployment. `tx_id` groups simultaneous moves into a transaction.
5. **Provenance.** The executor and only the executor (v10.3 §7.4.1). Hash-chained per Invariant 4 (log monotonicity).
6. **Temporal semantics.** *Append-only with dual timestamp* — economic time (when it happened) and booking time (when we learned about it). Late events and corrections are new appends, never edits (v10.3 §10.4 ``Corrections as events'').
7. **Failure consequences.** Loss of any prefix of the stream destroys time travel (P8); detection of mid-stream corruption (hash chain break) requires write-locked re-derivation from upstream sources. The move stream is the source of truth: balances, PnL, and reports are projections from it.

---

### D8. Market-Data Snapshot — `\label{data:market-data-snapshot}`

(Corpus name: **Market data snap** — val §3 `market_data_snap: SnapshotId` field on `ValuationRecord`, and v10.3 §7.4 ``versioned snapshot with source, timestamp, fallback chain''.)

1. **Canonical name.** Market-Data Snapshot.
2. **Definition.** A versioned, immutable bundle of the *raw* observables `O = {S, r, FX, quoted vols, quoted credit spreads, …}` captured at a specific time and made addressable by `SnapshotId`.
3. **Minimum field set.** `snapshot_id`, `as_of_timestamp` (intended observation time), `captured_at` (wall-clock receipt time), `source` per observable (vendor, exchange feed, internal aggregator), `fallback_chain` per observable, `quote_quality` (firm/indicative/stale), `bid`, `ask`, `last`, `quote_size`, `microstructure_metadata` (for D10's noise model).
4. **Identity.** `snapshot_id`, deterministically derived from `(as_of_timestamp, source_set, content_hash)` so two captures with identical content collapse to one identity.
5. **Provenance.** Per-field source authority; the `(source, vendor_message_id, timestamp)` triple is mandatory. The Ledger does not create market data (v10.3 §3.3.1: ``read from external sources''); it stores what arrived and from whom.
6. **Temporal semantics.** *Bitemporal.* `as_of_timestamp` answers ``what was the market at this moment''; `captured_at` answers ``when did we receive it''. Vendor restatements (``corrected close'') produce a new snapshot bitemporally indexed against the original. Time travel ``to what we knew at $t$'' uses the snapshot whose `captured_at ≤ t`; time travel ``to $t$ with corrected data'' uses the latest restated snapshot for `as_of = t` (v10.3 §7.4).
7. **Failure consequences.** Stale or missing snapshot stalls `\ref{sec:fsm}` transitions T1/T9; the FSM enters `\textsc{Stale}` and consumers apply prudential haircuts (val §2.1). A wrong snapshot used for VM ⇒ wrong cash transfer ⇒ broken conservation (P1) at the cash level; a wrong snapshot used for valuation ⇒ wrong PnL (P10) but quantities still conserve.

---

### D9. Calibrated Market-Data Object — `\label{data:calibrated-market-data}`

(Corpus name: **Calibration State** `x_t`, val §5.1, def `\ref{def:cal-state}`. The data category is the *published* output of the Kalman filter, not the running filter state itself.)

1. **Canonical name.** Calibrated Market-Data Object (the curve, surface, or correlation matrix consumed by pricers).
2. **Definition.** A no-arbitrage-consistent parameter object derived by Bayesian filtering (val §5) from the raw snapshot D8, ready to feed the Pricing DAG as an upstream node.
3. **Minimum field set.** `calibration_id`, `object_kind` (yield curve / vol surface / hazard curve / correlation matrix / FX vol cube), `state_vector` `x_{t|t}`, `covariance` `P_{t|t}`, `producing_filter_id`, `input_snapshot_id` (FK to D8), `model_id` (which arbitrage-respecting representation: kernel-vol, SVI, Hagan-SABR, monotone-spline curve), `calibration_timestamp`, `gating_outcome` (accept / down-weight / reject per innovation gate).
4. **Identity.** `(calibration_id, object_kind, model_id, calibration_timestamp)`.
5. **Provenance.** The Kalman pipeline of val §5; ultimately upstream snapshot D8 plus filter prior. The triple `(input_snapshot_id, filter_id, gating_outcome)` is mandatory so a regulator can demand: ``show me which raw quotes built this curve.''
6. **Temporal semantics.** *Bitemporal.* `as_of` is the snapshot's `as_of_timestamp`; `published_at` is when the calibration ran. Re-calibrations of the *same* `as_of` (e.g., late vendor correction triggers a rerun) produce a new `calibration_id` indexed bitemporally.
7. **Failure consequences.** A non-arbitrage-free curve poisons every `ValuationRecord` consuming it; the FSM should catch this via PnL-explain (T6 → `\textsc{Quarantined}`) but the corruption can persist for one full cycle. A rejected snapshot (D8 `gating_outcome = REJECT`) leaves the prior calibration in place, freezing the FSM until fresh data arrives.

---

### D10. Oracle Feed — `\label{data:oracle-feed}`

(Coined; the corpus uses ``oracle'' loosely in v10.3 §7.4 (``deterministic market data oracle'') and §9.2 (``mapping layer as oracle interface'') without a single named data class. I argue for *one* category that subsumes both, distinct from D8/D9.)

1. **Canonical name.** Oracle Feed.
2. **Definition.** A non-pricing external observation that the Ledger consumes as authoritative input to a deterministic decision: corporate-action announcements, FX fixing publications, index methodology rulings, barrier-observation rulings, locate-confirmation messages, settlement confirmations (sese.025, camt.054), CCP novation confirmations, regulatory MRA outcomes.
3. **Minimum field set.** `oracle_id`, `oracle_kind` (corporate-action | fixing | barrier-observation | settlement-confirmation | locate | mra | …), `subject_unit_id` or `subject_tx_id`, `payload` (CDM-typed where possible, e.g., `BusinessEvent` for corporate actions), `observation_time`, `received_at`, `signature` (where the oracle is cryptographically attested), `chain_of_custody` (for non-attested).
4. **Identity.** `(oracle_id, oracle_kind, subject_id, observation_time)`.
5. **Provenance.** Issuer agent (corp actions); fixing publisher (FX); CSD (settlement confirmation); CCP (clearing/novation); locate provider (SBL); regulator/repository (MRA outcomes). Mandatory triple `(authority, message_id, received_at)`.
6. **Temporal semantics.** *Append-only*. Each oracle event is a fact-as-of-an-observation-time; corrections are new oracle events with `corrects` reference. The Ledger never edits an oracle event in place (same discipline as D7).
7. **Failure consequences.** Missing oracle event ⇒ a lifecycle handler that ought to have fired does not (a missed corporate-action, an unbooked settlement). The obligation-store / liveness machinery (`\ref{def:obligation}`) was designed precisely to detect this class of miss. A *wrong* oracle event (mis-rounded fixing, mis-ratio'd split) propagates through the lifecycle as an authoritative input and is hard to reverse: a CORRECTION transaction is required (v10.3 §10.4).

**Argument for D10 not collapsing into D8.** D8 is *prices*; D10 is *facts about lifecycles*. The discriminator is what the consumer does with it: D8 feeds the Pricing DAG and the FSM (val §2); D10 feeds the obligation store and lifecycle handlers (v10.3 §13). A single category that mixes ``the closing price of AAPL'' with ``AAPL announced a 4-for-1 split'' would defeat the C11 handler-tagging discipline.

---

### D11. Smart-Contract Execution Data — `\label{data:contract-execution}`

(Coined, but anchors on existing concepts: the executor's audit trail (v10.3 §7.4.1), Temporal workflow history (v10.3 §11.7), and the ``two audit trails'' of v10.3 §11.4. The corpus has no single data-class name for the inputs/outputs of contract evaluation.)

1. **Canonical name.** Smart-Contract Execution Data.
2. **Definition.** The recorded inputs, outputs, and decision provenance of every smart-contract evaluation — the data that makes the pure-function lifecycle replayable bit-for-bit.
3. **Minimum field set.** `execution_id`, `unit_id`, `contract_id`, `contract_version_hash` (deterministic hash of the executable contract), `event_intent` (CDM enum), `input_view_snapshot_id` (the cloned read-only view, v10.3 §7.7), `input_market_data_snap` (FK to D8), `input_oracle_events` (FK list to D10), `proposed_moves`, `proposed_state_deltas`, `executor_decision` (commit | reject | quarantine), `temporal_workflow_id`, `temporal_run_id`, `replay_seed` (for any nominally-stochastic contract, e.g., Monte Carlo MC handlers).
4. **Identity.** `(execution_id, contract_version_hash)` — the version hash makes the identity survive contract code upgrades.
5. **Provenance.** The executor (v10.3 §7.4.1) and the Temporal worker (v10.3 §11.2). Each execution carries its full upstream FK closure so a regulator can reconstruct: ``which contract, on which inputs, decided this move?''
6. **Temporal semantics.** *Append-only*. A re-evaluation of the same contract on the same inputs produces a new `execution_id` *only if* the result changed; otherwise idempotency (P5/P6) suppresses it. Versioning across contract upgrades is the v10.3 §11.10 CDM-coexistence discipline.
7. **Failure consequences.** Missing execution data destroys deterministic replay (v10.3 §7.6, §11.9), which is the keystone audit property. A wrong `contract_version_hash` (e.g., the contract was edited and hash not rotated) breaks the executor's purity guarantee silently — every downstream invariant (P9, P10) becomes unprovable. This category is the technical substrate for DORA Article 8 ICT-tools testing (v10.3 §12).

---

### D12. Listed-Instrument Detail Data — `\label{data:listed-instrument-detail}`

(The user's floor category 6. The corpus already covers the *static-master* part of this in Tier 1 of the Unit Store. I argue that ``listed-instrument detail'' is a *strict superset* of D1 and is best split into D1 (static-master) and a new category D12 covering the dynamic-listing-state that is neither static reference (D1) nor product status (D4).)

1. **Canonical name.** Listed-Instrument Detail.
2. **Definition.** The per-listing, per-trading-day operational facts published by an exchange or its symbology vendor that are neither immutable static-master (D1) nor per-instrument status flags (D4). Examples: tick-size schedules, lot-size overrides, trading hours and circuit-breaker states, settlement price methodology overrides, market-on-close auction rules, expiry calendars, lot-class roll calendars, mini/micro contract specifications.
3. **Minimum field set.** `listing_id` (FK to D1), `mic`, `as_of_session`, `tick_size_table`, `lot_size_override`, `circuit_breaker_state`, `auction_schedule`, `settlement_methodology_id`, `expiry_calendar_id`, `holiday_calendar_id`, `corporate_action_pending` (yes/no flag pointing into D10).
4. **Identity.** `(listing_id, as_of_session)`.
5. **Provenance.** Exchange notice, symbology vendor (Bloomberg OPRA, Refinitiv, ICE Connect). Mandatory `(authority, notice_id, received_at)`.
6. **Temporal semantics.** *Bitemporal*. Effective time = the trading session the rule applies to; knowledge time = receipt. A late-published holiday or a same-day circuit-breaker change must produce historically-consistent replay.
7. **Failure consequences.** Wrong tick size ⇒ price inputs to D8 fail validation, propagating to D9 and the FSM. Wrong lot size ⇒ physical-delivery exercises (v10.3 §17.1.7) emit moves the CSD will reject. Wrong circuit-breaker state ⇒ the executor lets through trades that the venue has actually halted. CDM coverage here is thin (v10.3 §3.10 acknowledges ``CDM does not model exchange reference data feeds''), so this category is largely vendor-dependent and brittle.

---

### D13. Obligation State — `\label{data:obligation-state}`

(Corpus name: **Obligation Store**, `\ref{def:obligation-store}`, v10.3 §13.18. Cited verbatim. I list this as a data category because Phase 1's enumeration must include the liveness-bearing data class that v10.3 added in §13.)

1. **Canonical name.** Obligation State.
2. **Definition.** The set of currently-live, currently-due, and recently-discharged obligations (CSA VM calls, SBL collateral substitutions, manufactured-dividend pass-throughs, recall returns) with their deadlines.
3. **Minimum field set.** `obligation_id`, `obligation_kind` (per the taxonomy of `\ref{tab:obligation-types}`), `obligor_wallet`, `obligee_wallet`, `subject_unit_id`, `due_at`, `created_at`, `discharged_at`, `discharging_tx_id` (FK to D7).
4. **Identity.** `obligation_id`, deterministic from `(obligation_kind, subject, parties, created_at)`.
5. **Provenance.** Either a smart contract (D11) created it as a side effect of a trade or lifecycle event, or an oracle (D10) created it on receipt of an external trigger. `created_by_execution_id` is mandatory.
6. **Temporal semantics.** *Bitemporal* (effective `due_at` separate from booking-knowledge time) and *append-only* on the discharge log (each discharge is a new entry, never an in-place mutation).
7. **Failure consequences.** A missing obligation ⇒ the liveness invariants `\ref{inv:obligation-liveness}` and `\ref{thm:obligation-liveness}` are unprovable for the affected event class; downstream that means a missed margin call, an unfulfilled recall, or a missed manufactured-dividend pass-through. This was the gap v10.3 §13 was written to close.

---

### D14. Settlement Routing Data — `\label{data:settlement-routing}`

(Corpus name: **Standing Settlement Instructions (SSIs)** and the enrichment block in v10.3 §11.2.)

1. **Canonical name.** Settlement Routing Data.
2. **Definition.** The operational routing facts the settlement layer needs to turn a `SettlementInstruction` (v10.3 §11.1) into a wire message: SSIs, CSD account ids, payment-system BIC routing, priority rules, cut-off calendars.
3. **Minimum field set.** `ssi_id`, `counterparty_lei` (FK to D2), `unit_class` (security or currency), `csd_account`, `bic_chain`, `nostro_account`, `priority_class`, `cutoff_calendar_id`, `effective_from`, `effective_to`.
4. **Identity.** `(counterparty_lei, unit_class, csd_or_currency, effective_from)`.
5. **Provenance.** Counterparty SSI exchange (omgeo / DTCC ALERT / SwiftRef); internal treasury for nostros. Mandatory `(authority, version, retrieved_at)`.
6. **Temporal semantics.** *Bitemporal*. SSIs change; a trade settling next week needs the SSI as published *today* and as effective on settlement date — the bitemporal join is non-negotiable.
7. **Failure consequences.** Wrong SSI ⇒ wire goes to the wrong account; recovery is slow and operationally expensive. The boundary discipline of v10.3 §11.1 keeps this class out of the Ledger's correctness surface (the Ledger emits `SettlementInstruction`; the settlement layer enriches), but a wrong SSI produces a real-world break that virtual-wallet reconciliation will eventually surface (v10.3 §10.5).

---

## 3. Floor-category coverage and arguments

The user's six floor categories map to my fourteen as follows. I argue each disagreement explicitly.

| Floor category                       | My categories         | Argument                                                                                                    |
|--------------------------------------|-----------------------|-------------------------------------------------------------------------------------------------------------|
| 1. Static data                       | **D1**                | One-to-one. ``Static'' = Tier 1 of Unit Store.                                                              |
| 2. Reference data                    | **D2, D6, D14**       | The floor name is too coarse: counterparty-reference, wallet-registry-as-reference, and SSI-routing all have *different temporal semantics* (D2 and D14 bitemporal; D6 bitemporal but governance-driven, not market-driven). Collapsing them into one category breaks Halmos Rule 6 (consistent terminology). |
| 3. Market data                       | **D8, D9**            | D8 is *raw* (the snapshot); D9 is *calibrated* (the curve/surface). The corpus's val §5 makes this distinction load-bearing — same `as_of`, different identities, different failure consequences, different provenance discipline. They must be separate categories, not one. |
| 4. Oracle data                       | **D10**               | One-to-one, but I argue (above) that ``oracle'' must explicitly *exclude* market data; the corpus's loose use of ``oracle'' for the FpML/CDM mapping (v10.3 §9.2) is a metaphor, not a category. |
| 5. Smart-contract execution data     | **D11**               | One-to-one.                                                                                                 |
| 6. Listed-instrument detail data     | **D1 + D12**          | I split. Static-master (ISIN, multiplier, expiry) is D1 — same temporal discipline as bond reference data. Operational listing-detail (tick table, circuit breaker, auction schedule) is D12 — bitemporal at the *session* grain, not the *life-of-instrument* grain. Conflating them puts a daily-cadence feed in the same governance class as a once-per-life ISIN issuance, which is a Halmos Rule 6 violation and an operational footgun. |

**Coverage that the floor list *omits*** and that I add:

- **D3 (Instrument Terms inbound)** — distinct from D1 because it is the *contractual* data class (CDM `Trade` for OTC, mandate text for MA), governed by C8 fungibility predicates, append-only versioned. Without it, the inbound side of `ProductTerms` has no name.
- **D4 (Unit Status inbound)** — distinct from D8 because it is *contract-mutable status*, not market price. A barrier-trigger flag is not a price; an exchange settlement price is not a status. Both feed `UnitStatus` but along different governance paths.
- **D5 (Position-State Deltas)** — the inbound side of `PositionState`. The addendum names the destination (`PositionState`); Phase 1 must name the inbound payload separately because its provenance is exclusively handlers (never feeds), and that is a structural property worth a named category.
- **D7 (Move Stream)** — the spine of the system. Astonishing if Phase 1 omitted it; it is data, it is point-of-truth, it has identity, provenance, and temporal semantics. The user's floor list does omit it, presumably because the user takes it for granted, but I include it for completeness — Phase 1 should not be silent on the canonical record.
- **D13 (Obligation State)** — the v10.3 §13 addition. Without it, the SBL collateral-substitution liveness invariant is unprovable; this is a data category with a name, a store, and a temporal discipline.

---

## 4. Summary of disagreements with the floor list

1. **``Reference data'' is one floor entry but three data classes.** Counterparty (D2), wallet registry (D6), and settlement-routing (D14) have different authorities, different bitemporal disciplines, and different failure modes. They should never share a single category name.
2. **``Market data'' is one floor entry but two data classes.** Raw snapshot (D8) and calibrated object (D9) are joined by a Bayesian filter, not by identity. Conflating them defeats the FSM's `\textsc{Quarantined}` semantics (val §2.2 transition T6 is over D9, not D8).
3. **``Listed-instrument detail data'' should not be its own floor category.** Its static part is D1 (already there); its operational part is D12 (a different temporal grain). Keeping it as a single floor category is a category error.
4. **The floor list omits four categories that v11.0 already names or relies on:** the Move Stream itself (D7), Instrument Terms inbound (D3), Unit Status inbound (D4), Position-State Deltas inbound (D5), and Obligation State (D13). Without these, Phase 1 cannot honestly claim coverage of v10.3 + addendum + valuation.

---

## 5. The HALMOS test, applied to this enumeration

1. **Notation table exists?** Yes — §0.
2. **Define before use?** Every symbol used (`u`, `w`, `Σ`, `P_t`, `Θ`, `O`, `σ(u)`, `tx_id`) is defined in §0 before any data category references it.
3. **Examples?** Each category has a concrete example in its `Minimum field set` and in cross-references to the corpus.
4. **Structure apparent?** §0 (notation) → §1 (corpus citations) → §2 (fourteen categories, identical seven-field shape) → §3 (floor mapping table) → §4 (disagreements summary) → §5 (this checklist).
5. **Read six times?** Drafted, restructured to put existing-name citations *before* coinages so no name is invented when the corpus already has one, then re-read for terminology consistency (``snapshot'' is D8 only; ``calibrated object'' is D9 only; ``status'' never refers to settlement status, etc.).
6. **Implementable?** Each category gives field set, identity, provenance, temporal semantics, and failure mode — sufficient to design a schema, an ingest pipeline, and a reconciliation suite. Phase 2 should be able to start from this document without re-reading the corpus.

---

*Document compiled 2026-04-29 for Phase 1 of the Ledger v11.0 data specification. All `\label{data:*}` anchors verified non-colliding against the union of label sets in v10.3, the StatesHome addendum, and valuation v1.0.*
