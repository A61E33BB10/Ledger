# Phase 1 — Independent Data Enumeration (Cartan)

**Author:** Henri Cartan, Mathematical Documentation Architect
**Discipline:** Bourbaki — definitions before theorems; minimum basis; explicit dependencies
**Corpus consulted:** `ledger_v10.3.tex`, `ledger_v10.3_addendum_stateshome.tex`, `ledger_valuation_v1.0.tex`
**No cross-talk with other Phase 1 reviewers.**

---

## 0. Method

I treat the Ledger framework as a formal system. Every datum the system manipulates must satisfy three meta-conditions:

1. **It is referenced by an axiom, definition, theorem, invariant, or operational pseudocode in the corpus** (existence by appeal to text);
2. **Two records can be tested for equality** (identity is decidable);
3. **Its temporal semantics are pinned**: at minimum, every datum is locatable on the bitemporal lattice (knowledge time × validity time) of `clone_at(t)` (cf. `ledger_v10.3.tex` §1.2 Property 6, §2 self-consistency).

I refuse the "data category" abstraction unless it survives the **Karpathy substitution test** (StatesHome addendum §6.1): two records that differ on a single field of the category must be operationally distinguishable. Categories that fail this test are merged. Categories that fragment under the test are split.

I name each category, not each field. A category is a *kind* of fact; the seven mandatory fields (canonical name, definition, minimum field set, identity, provenance, temporal semantics, failure consequences) are stated for each. Where a floor category masks a heterogeneous union, I split it and justify.

---

## 1. The Floor — and Why It Is Insufficient as Stated

The six floor categories in the Phase 1 brief are necessary but not exhaustive. Three additions are forced by the corpus:

- **F7. Lifecycle / event-stream data** — moves, transactions, business events, the immutable log itself. The corpus's central theorem (Path-Independent PnL, `ledger_v10.3.tex` §4.3) is a statement about the log, not about positions. The log is not "static," not "reference," not "market," not "oracle," not "execution input," not "listed-spec" data. It is its own genus.
- **F8. State data** — the three maps of the StatesHome ruling (*ProductTerms*, *UnitStatus*, *PositionState*). State data is neither static (UnitStatus mutates) nor reference (it is internal) nor market (it is contract-internal). The addendum makes its irreducibility a *theorem* (3 maps are the minimum basis — addendum §5.1).
- **F9. Valuation / pricing-internal data** — the ValuationRecord, the Pricing DAG topology, the FSM σ(u), Greeks, calibration state x_{t|t}. Distinct from market data: market data is *input* to the Kalman filter; calibration state is the *posterior* (`ledger_valuation_v1.0.tex` §4).

I also split two floor categories that are heterogeneous:

- **Floor 1 (Static) splits into F1a (immutable contractual terms) + F1b (versioned amendments)** — addendum C6/C8 forces this: `ProductTerms` is `NonEmptyList[TermsVersion]`, not a flat record. "Static" is a misnomer; the correct word is "append-only versioned."
- **Floor 5 (Smart-contract execution) splits into F5a (handler inputs) + F5b (handler outputs / StateDelta) + F5c (idempotency / deduplication keys)** — required by C2, C3, C11.

I additionally introduce:

- **F10. Regulatory and accounting projection data** — instrument classifications (FVTPL/FVOCI/AC under IFRS 9; ASC 815/820), reporting flags (SFTR reportable, EMIR Article 4, SLATE `slate_loan_id`, `sftr_uti`), and tax-lot lineage. These are neither pure reference data (they are firm-specific decisions) nor market data (they are policy outputs). `ledger_v10.3.tex` §10 makes them first-class.
- **F11. Identity and capability data** — wallet metadata, party LEI/BIC, capability scopes (C4), RACI assignments for amendment predicates (F2 of the StatesHome risk register). Distinct from "reference data" because identity is internal and authorisation-bearing.
- **F12. Reconciliation and external-attestation data** — confirmation-return-path status (`EXECUTED → INSTRUCTED → SETTLED/FAILED`, §12.7), virtual-wallet contra-balances against external statements, custodian depots. These are not oracle data (oracles cross the contract boundary; reconciliation crosses the *settlement* boundary). They are not lifecycle events (they confirm prior events).

**Total: 19 categories** (six floor, with two splits, plus six additions; see §10 below).

---

## 2. The Enumeration

For each category I give the seven mandatory fields. Where the corpus uses a specific symbol or label (e.g. `accumulated_cost`, `TermsVersion`, $P_t(u)$), I retain it.

### Category 1a — Immutable Contractual Terms (Static, Per-Issuance)

1. **Canonical name.** `ProductTerms[u].head` (the inception `TermsVersion`); ledger §3.3 "Tier 3 Unit Registry."
2. **Definition.** The set of contractual parameters fixed at the moment of issuance / registration that, by the C8 fungibility predicate, *do not move* without allocating a fresh unit identifier `u_new`. For listed `u`: contract specification (underlier, strike, expiry, multiplier, settlement type, exchange, CCP, currency). For OTC `u`: the full CDM `Trade` object including `Collateral` (CSA terms — addendum §4.1, ledger §3.2).
3. **Minimum field set.** `{unit_id, unit_type, identity_payload, currency, multiplier?, expiry?, issuer?, governing_doc_ref, fungibility_predicate}`. Identity payload is type-discriminated: `ISIN` for securities; `ContractSpec(exchange, underlier, type, strike, expiry, multiplier, settlement_ccy)` for listed derivatives; `CDM_Trade_metadata_key(including Collateral)` for OTC.
4. **Identity.** Two records are the same iff their `unit_id` is equal. The `unit_id` is *deterministically derived* from the identity payload (ledger §3.3): for listed, a hash of contract-spec fields; for OTC, the CDM Trade metadata key. The map (payload → unit_id) is **injective** by ledger §3.3 and Appendix `cdm-walkthrough`. C10 forbids re-registration.
5. **Provenance.** Listed: exchange / reference-data vendor / CSD (Tier 1, ledger §3.3.1). OTC: counterparty CDM `ExecutionEvent` payload, signed at execution. Cash: pre-registered at system inception (ledger §3.4 channel 1).
6. **Temporal semantics.** **Append-only versioned** (C6). The full history is `NonEmptyList[TermsVersion]`. *Bitemporal at the version level*: each `TermsVersion` carries a `valid_from` and a `recorded_at`. Identity (`unit_id`) is fixed for life (C10); content evolves only via Preserving amendments (C8 — `is_fungibility_preserving = true`).
7. **Failure consequences.** Mutating in place violates C6 → P6 (immutability of terms) reachable → audit trail destroyed → time-travel theorem `clone_at(t)` returns wrong terms → PnL replay diverges from historical truth. Misclassifying a Breaking amendment as Preserving violates C8 → silent fungibility break → conservation $\sum_w w(u_{old}) = 0$ silently transfers value to wrong-unit holders → the inverse mapping in F8 of the StatesHome risk register breaks irreversibly.

### Category 1b — Versioned Amendments (Append-Only Terms-History)

1. **Canonical name.** `ProductTerms[u].tail` — the sequence of post-inception `TermsVersion` rows for `u`.
2. **Definition.** A finite, ordered sequence of `TermsVersion` records each of which (i) was admitted to `ProductTerms[u]` by an event whose product-declared `is_fungibility_preserving(prev, new) = true`, (ii) is signed by an authorised amender per the F2 RACI table.
3. **Minimum field set.** `{terms_version_id, parent_version_id, valid_from, recorded_at, amender_lei, amendment_class ∈ {coupon_step_up | csa_eligible_collateral_change | fee_rate_band | rate_index_replacement | ...}, delta_payload, fungibility_predicate_eval, signature}`.
4. **Identity.** `(unit_id, terms_version_id)`. The pair is unique; the linked-list structure forbids duplicate `parent_version_id`.
5. **Provenance.** A CDM `BusinessEvent` of intent `AMENDMENT` (or product-specific equivalent — bond restructuring, CSA amendment); the event payload is stored in the move-stream transaction's CDM-payload column (ledger §9.4).
6. **Temporal semantics.** **Strict append-only** (C6). Bitemporal: `(valid_from, recorded_at)`. No deletion; no in-place mutation. Re-application of the same `terms_version_id` is rejected (idempotency by id).
7. **Failure consequences.** Skipping a version → state at time `t` is reconstructed under wrong terms → discount curves, accruals, exercise boundaries all wrong → PnL drift. Allowing in-place edit → C6 violated → P6 unreachable → regulatory reconstruction (MiFID II Art 16, MAR) impossible. Misordering versions → C8's two-track discipline silently fails on a later Breaking amendment.

### Category 2 — Reference Data (External-Authority Static Universe)

1. **Canonical name.** Tier 1 reference data (ledger §3.3.1).
2. **Definition.** Externally authoritative data describing the universe in which contracts are denominated, scheduled, identified, and classified, and which the Ledger *consumes* without authoring. Splits into seven sub-categories, each independently versioned.
3. **Minimum field set (per sub-category).**
   - **2.1 Calendars.** `{calendar_id, jurisdiction_or_exchange, holiday_dates_set, business_day_convention_default, source_authority}`.
   - **2.2 Day-count conventions.** `{convention_code ∈ {ACT/360, ACT/365F, 30/360, 30E/360, ACT/ACT-ISDA, ...}, formula_spec_ref}`.
   - **2.3 Currency metadata.** `{iso_4217_code, minor_unit_decimals, settlement_calendar_id, central_bank_lei, redenomination_history}`.
   - **2.4 Party identifiers.** `{lei (ISO 17442), bic (ISO 9362), mic (ISO 10383) for venues, cdm_party_role}`. Ledger §2.6 binds virtual-wallet identifiers to LEI + account suffix.
   - **2.5 Exchange / CCP / CSD metadata.** `{mic, ccp_lei, csd_bic, clearing_member_relationships, dvp_mechanism ∈ {DTC, Euroclear, Clearstream, ...}, settlement_cycle_default ∈ {T+0, T+1, T+2}}`.
   - **2.6 Regulatory classifications (external).** `{instrument_classification_ifrs9 (FVTPL|FVOCI|AC), accounting_treatment_us_gaap (ASC 815|320|321|820), mifid2_instrument_class, sftr_security_type, slate_eligibility, csdr_buy_in_class}`.
   - **2.7 Index / benchmark methodology.** `{benchmark_id (e.g. SOFR, ESTR, SPX, SX5E), administrator_lei, methodology_ref, fallback_waterfall, IBOR_replacement_clause}`. (Ledger §5 IRS, §6 managed-account benchmarks.)
4. **Identity.** Sub-category-specific natural keys — `(calendar_id, version)`; `(iso_4217_code, valid_from)`; LEI; MIC; etc. Versioning is **mandatory**: a calendar without a version is unusable for time travel.
5. **Provenance.** ISO maintainers (4217, 9362, 10383, 17442); ANNA (ISIN); FIX/CDM enum registries; central-bank gazettes; ISDA (definitions, supplements); benchmark administrators; regulators (ESMA, SEC, FINRA). Each provenance carries an attested-at timestamp and a fetch-at timestamp; the two are distinct.
6. **Temporal semantics.** **Bitemporal**, append-only. `(valid_from, valid_to)` for the external truth; `(recorded_at, superseded_at)` for the firm's knowledge. A holiday added after the fact (typhoon closure) increases `recorded_at` but `valid_from` precedes it.
7. **Failure consequences.** Missing holiday → `business_day_adjusted` reset / coupon date wrong → swap payment fires on a non-business day → conservation algebra holds (the move sums to zero) but the *external* settlement leg fails to clear → reconciliation break. Stale LEI → SFTR / EMIR submission rejected. Wrong day-count → DV01 and discount factors miscompute → PnL explain residual non-zero → FSM transitions to `Quarantined` (T6 of valuation FSM). Wrong CCP MIC → `clearinghouse` field on `ProductTerms` of futures unit is wrong → addendum §4.1 forces a *fresh* unit identity, but if the error is caught after positions are taken, conservation $\sum_w \texttt{ac}(w, u_{wrong}) = 0$ holds against the wrong unit and an irreversible cross-CCP mis-attribution results.

### Category 3 — Market Data (Raw Observables)

1. **Canonical name.** $y_t \in \mathbb{R}^{m_t}$ — the observation vector at knowledge time $t$ (`ledger_valuation_v1.0.tex` §4.3, eq. observation).
2. **Definition.** A vector of market-quoted observables stamped with a knowledge time, a venue, and a microstructure-derived noise profile $R_t$. Distinct from calibration state $x_{t|t}$ (Category 9b) which is the *posterior*.
3. **Minimum field set.** `{quote_id, observable_kind ∈ {spot, deposit_rate, swap_rate, future_price, option_price, cap_floor_price, fx_spot, fx_forward, dividend_estimate, borrow_fee, repo_rate, cds_spread, recovery_rate}, instrument_ref, venue_mic, side ∈ {bid, ask, mid, last, settlement}, value, currency, observation_time_utc, source_attestor, half_bid_ask, staleness_factor}`.
4. **Identity.** `(observable_kind, instrument_ref, venue_mic, side, observation_time_utc, source_attestor)`. Two quotes from the same venue at the same UTC nanosecond from the same attestor for the same instrument and side are the same record (idempotent ingestion). Identity *includes* attestor: two attestors disagreeing at the same time are distinct records, both retained.
5. **Provenance.** Exchange feeds (CME, ICE, LSE, ...), market-data vendors (Bloomberg, Refinitiv), inter-dealer-broker quotes, internal-trading-desk colour. Each carries a CDM-equivalent attestation envelope: `{attestor_lei, signature, raw_message_hash, ingest_timestamp}`. Section §3.4 valuation-doc ingest pipeline: oracle → Kalman → DAG.
6. **Temporal semantics.** **Append-only point-in-time stream**, indexed by knowledge-time. Bitemporal at the use-site (a back-dated correction enters with new `recorded_at` but the original observation at the original `valid_at` is *not* overwritten). Stale quotes are **not deleted**; their `staleness_factor` inflates $R_{ii}$ in the Kalman update (§4.3 valuation doc).
7. **Failure consequences.** Missing observation → Mahalanobis gate (§4.5 valuation) cannot be computed → calibration step skipped → DAG node stalls → downstream FSM transitions Explained → Stale (T8). Mislabelled venue → cross-venue arbitrage signals false-positive. Bad noise estimate $R_{ii}$ → Kalman gain misweights → calibration $x_{t|t}$ tracks noise → vol surface oscillates → unexplained PnL residual blows up → P10 (PnL path-independence) appears to fail when in fact the *price* function lost its martingale-on-parameters property (§3.2 valuation, Principle "martingale on parameters").

### Category 4 — Oracle Data (Cross-Boundary Attested Observations)

1. **Canonical name.** External attestations crossing the *contract execution* boundary (distinct from the *settlement* boundary of Category 18).
2. **Definition.** A datum produced by an external authority whose cryptographically- or institutionally-signed truth claim *is itself* the trigger for a deterministic smart-contract action. The Ledger does not re-evaluate the oracle's claim; it executes against it.
3. **Minimum field set.** `{oracle_event_id, oracle_kind ∈ {barrier_observation, knock_in_trigger, knock_out_trigger, exercise_notice, corp_action_confirmation, fixing_attestation, settlement_finality_attestation, regulatory_threshold_determination, default_declaration, force_majeure}, subject_unit_id, claim_payload, observation_time, attestor_lei, signature, attestation_chain, contract_predicate_evaluated, predicate_result ∈ {true, false}}`.
4. **Identity.** `(oracle_event_id, attestor_lei)`. Replays of the same `oracle_event_id` from the same attestor are idempotent (handler dedup). Two attestors making the *same* claim are distinct records; the smart contract's predicate decides which is authoritative (e.g., calculation-agent role per CDM `partyRole`).
5. **Provenance.** Calculation agent (CDM `partyRole = CalculationAgent`); index administrator (e.g., S&P for SPX close); CCP (default declaration); CSD (settlement-finality message under SFD Article 3); regulator (e.g., OFAC sanctions list trigger). Each carries an ISO 20022 / FpML / FIX message hash and the attestor's signature.
6. **Temporal semantics.** **Point-in-time, immutable on receipt**. Bitemporal because an oracle correction (e.g., a re-fixed LIBOR after an erroneous publication) is itself a *new* oracle event with its own `observation_time` and `recorded_at`; the original is retained, the correction is layered, and the contract's idempotency key (Category 5c) ensures the handler fires exactly once on the authoritative claim.
7. **Failure consequences.** Acting on an unsigned / unverified oracle claim → contract fires on bad data → moves are emitted that conservation accepts (sum to zero) but that have no real-world counterparty acceptance → FSM transitions T3 (Failed) at next reprice but *positions have already moved* → recovery requires a `CORRECTION` transaction (ledger §8.3). Missing the claim → barrier fails to trigger → option expires unexercised that should have settled → P5 (idempotency) is preserved but P10 (path-independence) fails because the *expected* lifecycle move was not emitted. Two contradicting attestors with no role-arbitration rule → handler is non-deterministic → C2 conservation proof obligation broken at the per-event-class level.

### Category 5a — Smart-Contract Handler Inputs (Executor Reads)

1. **Canonical name.** Handler input tuple at lifecycle-event time (ledger §7.3, addendum §2 C2 / C11).
2. **Definition.** The set of values an event handler $f$ reads atomically before producing a `StateDelta`. From the addendum: $f$ reads (`ProductTerms[u].current()`, `UnitStatus[u]`, `{PositionState[(w, u)]}_{w in holders(u)}`, market_data_snap, time_now, oracle_payload?). C4 (capability scoping) restricts which `(w, u)` rows the handler may read.
3. **Minimum field set.** `{handler_invocation_id, event_class ∈ {Trade, SettleVM, CorporateAction, QISRebalance, MandateAmend, Coupon, Dividend, Exercise, Expiry, BarrierHit, Reset, Subscription, Redemption, FeeCrystallise, MarginCall, ...}, unit_id, terms_version_at_read, unit_status_at_read, position_state_rows_at_read (capability-scoped), market_data_snapshot_id, oracle_event_ref?, time_now_utc, idempotency_key (see 5c)}`.
4. **Identity.** `handler_invocation_id` (UUID) is unique per attempt. `(event_class, unit_id, idempotency_key)` is the *semantic* identity: two invocations with the same triple must produce identical `StateDelta`s by C2's per-event-class structural proof.
5. **Provenance.** Synthesised at handler dispatch time by the executor (ledger §13 Temporal-as-executor). The market-data snapshot is a frozen reference to a Category-3 record set; the unit-status read is a frozen pointer to Category 8b's `UnitStatus` row.
6. **Temporal semantics.** **Snapshot-frozen at read**, immutable thereafter. The handler must be a pure function of this tuple (P9 lifecycle purity). Replay of the same tuple → same `StateDelta` (deterministic-replay invariant P3 of ledger §10.2).
7. **Failure consequences.** Reading a non-frozen reference (e.g., a live `UnitStatus` pointer rather than a value) → handler becomes non-deterministic → P9 violated → time travel `clone_at(t)` produces drift → Path-Independent PnL theorem fails on replay. Missing capability scope check → cross-`(w, u_MA)` overlay leak → C4 violated → mandate breach detection produces false negatives.

### Category 5b — Smart-Contract Handler Outputs (StateDelta)

1. **Canonical name.** `StateDelta` — the atomic mutation packet produced by a handler (addendum C3).
2. **Definition.** A finite, atomically-applied bundle of changes to the three state maps and the move stream, satisfying per-event-class structural conservation (C2). $\Delta = \{\Delta\text{ProductTerms}, \Delta\text{UnitStatus}, \Delta\text{PositionState (per row)}, \text{moves emitted}\}$. C3: partial application is rejected.
3. **Minimum field set.** `{delta_id, handler_invocation_id, terms_versions_appended ⊆ ProductTerms, unit_status_field_writes (fields tagged by C11 to this handler), position_state_row_diffs ({(w, u) → field-level diff}), moves_emitted (List[Move]), conservation_proof_obligation_discharged ∈ {2-leg, K-leg, VM-fan-out, vacuous}}`.
4. **Identity.** `delta_id` is a UUID; `(handler_invocation_id, sequence)` is the canonical key. By C3 atomicity, `delta_id` is *the* unit of commit.
5. **Provenance.** The single handler instance that produced it. C11 tags each `position_state_row_diffs` field with the unique handler authorised to mutate it; cross-handler writes are a type error.
6. **Temporal semantics.** **Append-only event in the move stream** (P4 log monotonicity, ledger §10.2). The `StateDelta` is the *atom* of state evolution; everything visible in the three maps is the cumulative fold of all `StateDelta`s up to time $t$.
7. **Failure consequences.** Partial application (some maps written, others not) violates C3 → atomic commitment P2 fails → reconciliation across maps becomes impossible → at the next replay, `apply_all(events)` diverges from `apply_all(events[:k]) ++ events[k:]`, breaking P3. Missing conservation discharge → C2 violated → conservation $\sum_w w(u) = 0$ silently breaks at the unit level → trading-system / GL divergence becomes reachable (the very failure mode the ledger architecturally precludes).

### Category 5c — Idempotency / Deduplication Tokens

1. **Canonical name.** Idempotency keys as a first-class data category (ledger §13 Idempotency Chain, P5).
2. **Definition.** A datum whose sole purpose is to make event handlers safe under duplicate delivery. Distinct from `delta_id`: an idempotency key is *issued before* dispatch and survives across retries; a `delta_id` is minted *after* successful application.
3. **Minimum field set.** `{idempotency_key, scope ∈ {transaction, handler_invocation, lifecycle_event, oracle_attestation, ccp_message}, key_payload (often (event_class, unit_id, business_date, sequence_in_class)), first_seen_at, last_seen_at, terminal_outcome ∈ {applied | rejected | quarantined | superseded}}`.
4. **Identity.** `idempotency_key` itself. Collisions across scopes are forbidden (a global namespace, partitioned by `scope` prefix).
5. **Provenance.** Either externally supplied (CDM `BusinessEvent` UTI; FpML `messageId`; FIX `ClOrdID`; ISO 20022 `EndToEndId` per ledger §11.6) or internally minted (lifecycle scheduler issues `(unit_id, due_date, event_kind)` for due-events; QIS rebalance issues `(strategy_id, rebalance_period_id)`).
6. **Temporal semantics.** **Append-only with terminal-state memoisation**. Once an idempotency key has a terminal outcome, replays return the memoised outcome, not a fresh execution. Bitemporal: a corrected event re-uses the *same* business-level key with a new `recorded_at` (`CORRECTION` transaction in ledger §8.3), preserving traceability.
7. **Failure consequences.** Missing key → duplicate-event delivery (Temporal at-least-once semantics, ledger §13.6) re-fires the handler → conservation still holds (each handler call still sums to zero) but P5 (transaction idempotency) and P6 (lifecycle idempotency) are violated → cash flows double, dividends double-paid, fees double-accrued. Key collision across scopes → wrong replay outcome served → silent state divergence on hot restart.

### Category 6 — Listed-Instrument Detail Data (Exchange-Published Specs)

1. **Canonical name.** `ContractSpec` (ledger §3.2 unit-identity table; addendum §4.1 example).
2. **Definition.** The exchange-published specification that *defines* a listed unit's identity (multiplier, lot, tick, expiry, last trading day, first notice day, delivery month code, strike-listing rules, settlement type). Tier 1 reference data per ledger §3.3.1, but elevated to a separate category because for listed instruments the `ContractSpec` *is the unit identity* (ledger §3.2 fungibility rule).
3. **Minimum field set.** `{exchange_mic, product_root (e.g. ES, NQ, CL), contract_month_code, expiry_date, last_trading_day, first_notice_day, settlement_type ∈ {cash, physical, financially_settled}, multiplier, tick_size, tick_value, lot_size, board_lot, strike_listing_rule (for options: ATM-spacing, OTM-spacing, listing-band predicate), delivery_specification (for physical: deliverable grade, location, par-grade adjustments), block_trade_threshold, daily_price_limit, position_limit, ccp_lei, settlement_calendar_id, listing_date, delisting_date?}`.
4. **Identity.** `(exchange_mic, product_root, contract_month_code, [strike, option_type] if option, ccp_lei)`. **CME-ES and ICE-ES are different units** (addendum §4.1) — the `ccp_lei` is part of identity for futures because it is part of `ProductTerms` and cross-CCP fungibility does not hold.
5. **Provenance.** Exchange's official contract-specifications document; reference-data vendors (e.g., CFI codes from ANNA-DSB for OTC, SecDef messages on FIX for listed).
6. **Temporal semantics.** **Bitemporal**. A spec change (e.g., tick reduction) creates a new `(spec_id, valid_from)` row; old positions remain governed by the old spec via terms-version pinning (Category 1b). Strike-listing rules evaluate at observation time, not historically — but the *listing* of a new strike creates a fresh unit (`ProductTerms[u_new]`) and is itself an append-only event.
7. **Failure consequences.** Wrong multiplier → futures `accumulated_cost = -qty × price × mult` is wrong (ledger §7.5 exactness theorem) → conservation $\sum_w \texttt{ac}(w, u) = 0$ holds *within the wrong arithmetic* → the bug is invisible to conservation but causes immediate PnL drift at the next settle. Wrong lot size → physical-delivery residual computation in ledger §5.5 fan-outs to wrong cash leg → DvP atomicity guaranteed at ledger level but the settlement instruction (Category 18 below) is rejected by the CSD. Missing first-notice-day → futures roll fires late → auto-liquidation at adverse price → unexplained PnL.

### Category 7 — Lifecycle / Event-Stream Data (The Move Stream)

1. **Canonical name.** The immutable move stream — the canonical ledger object (ledger §1.2 Property 6, §10 invariant P4).
2. **Definition.** The totally-ordered, append-only sequence of `Transaction` records, each containing a finite list of `Move` records and an associated CDM `BusinessEvent` payload. *This is the single source of truth from which all balances, PnL, balance sheets, and reports are projections* (ledger §1.2 Property 6, §6.10 substantiation).
3. **Minimum field set.** Per `Move`: `{from_wallet, to_wallet, unit, quantity, timestamp, source_contract_ref, metadata}` (ledger §2.3). Per `Transaction`: `{transaction_id, timestamp, total_order_seq_within_timestamp, transaction_type ∈ {SETTLEMENT, COLLATERAL, LIFECYCLE, ACCOUNTING, CORRECTION}, moves ⊆ Moves, cdm_payload, prev_hash (hash-chain tamper-evidence per P4), state_delta_ref (link to Category 5b)}`.
4. **Identity.** `transaction_id` (UUID). Idempotency under re-application is provided by Category 5c keys; identity equality is by `transaction_id` exact match.
5. **Provenance.** The single executor (ledger §7.6 single-writer-by-construction; §13.5 single-writer Temporal worker). Every transaction is signed by the executor's key; the hash chain (P4) makes any retroactive insertion detectable.
6. **Temporal semantics.** **Append-only, hash-chained, totally ordered**. Knowledge time = `recorded_at`; validity time = `timestamp` (the economic event time). Re-statements (corrections of prior facts) are *new* `CORRECTION` transactions, not edits; the original is preserved (P4). `clone_at(t)` selects all transactions with `recorded_at ≤ t` (point-in-time-of-knowledge) or `timestamp ≤ t` (point-in-time-of-event); the two queries are different and must be exposed as such (ledger §1.2 Property 6 distinction "what we knew at time t" vs "with today's corrected data").
7. **Failure consequences.** Loss of monotonicity (an edit, a deletion) → P4 violated → time travel produces inconsistent histories → forensic reconstruction impossible → regulatory MAR / record-keeping rules breached. Loss of total order on same-timestamp transactions → intermediate margin calculations differ between replays → P3 (deterministic replay) violated → P10 (path-independence) holds at the *endpoints* but reproducibility fails for any intermediate audit slice.

### Category 8a — `ProductTerms` State (Versioned Contract Map)

1. **Canonical name.** `ProductTerms : Map[UnitId, NonEmptyList[TermsVersion]]` (addendum §2 ruling).
2. **Definition.** The first of the three state maps. Total on registered `u` (C7); append-only versioned (C6); the carrier of all immutable contractual content per unit. Already enumerated decompositionally as 1a + 1b; here it is enumerated as a *map structure* with its own integrity rules.
3. **Minimum field set.** `{unit_id → NonEmpty(head: TermsVersion, tail: tuple[TermsVersion])}` plus map-level invariants: registration totality (C7), no re-registration (C10).
4. **Identity.** Identity of the *map* is implicit (singleton per ledger instance); identity of a *value* is the `(unit_id, terms_version_id)` pair.
5. **Provenance.** Populated at `register(u, tv, us)` (addendum §10 reference impl); appended to by `amend(u, tv_new)` when fungibility-preserving (C8).
6. **Temporal semantics.** **Append-only versioned**, never deleted, never mutated in place. Total on registered units; `view.product_terms(u)` is total for all `u ∈ Unit Store`.
7. **Failure consequences.** As 1a / 1b. Additionally: a re-registration attempt (`register` on an existing `u`) must raise (C10 — addendum §2). Silent overwrite breaks the `unit_id` injectivity guarantee from ledger §3.3 → fungibility is no longer well-defined.

### Category 8b — `UnitStatus` State (Shared-Mutable Per-Unit Map)

1. **Canonical name.** `UnitStatus : Map[UnitId, UnitStatus]` (addendum §2).
2. **Definition.** The second state map. Total on registered `u` (C5 — product-declared defaults at registration). Mutable; shared across all holders of `u`. Carries: `lifecycle_stage`, `last_settlement_price`, `last_settlement_date`, `current_weights` (for QIS), `nav_index`, `triggered_barrier`, `superseded_by`, plus the valuation FSM state `σ(u)` (`ledger_valuation_v1.0.tex` §2 Definition val-states), and the staleness timer state (T8 of valuation FSM).
3. **Minimum field set.** Per `u`: `{lifecycle_stage ∈ {LISTED, ACTIVE, EXPIRED, MATURED, TERMINATED, SETTLED, CLOSED, DEFAULTED, ...}, last_settlement_price?, last_settlement_date?, current_weights? (for QIS), nav_index?, triggered_barrier_flag?, superseded_by?, valuation_fsm_state ∈ {Unpriced, Pricing, Priced, Explaining, Explained, Quarantined, Stale, Failed}, valuation_fsm_last_transition_at, retry_count, staleness_timer_expires_at}`.
4. **Identity.** `unit_id` (the map key). The `UnitStatus` row for `u` is a *single* entity over its lifetime; mutations replace the in-memory value but are recorded in the move stream as `StateDelta`s (Category 5b).
5. **Provenance.** Initialised at `register(u, tv, us)` with product-declared defaults (C5). Mutated only by handlers tagged authoritative for the specific field (C11 generalised to UnitStatus fields — e.g., `last_settlement_price` is mutated only by `SettleVM`; `valuation_fsm_state` only by the valuation workflow's state machine).
6. **Temporal semantics.** **Mutable but reconstructible**. The current value is the right-fold of all `StateDelta.unit_status_field_writes` for `u` over the move stream. `clone_at(t)` rebuilds the value as of `t` by replaying. Bitemporal at the field level: `(field_name, value, valid_from)` is the natural log unit.
7. **Failure consequences.** Direct mutation outside a handler (no `StateDelta`) → not reconstructible by replay → time travel breaks → P3 violated. Default not applied at registration → `view.unit_status(u)` becomes partial → C5 violated → an untraded option fails the lifecycle totality test (addendum §4.4 "Lifecycle totality"). FSM state inconsistency between persistence and Temporal workflow history → on workflow reset, the unit is double-priced or skipped → Pricing DAG misfires.

### Category 8c — `PositionState` State (Per-Holder, Per-Unit Map)

1. **Canonical name.** `PositionState : Map[(WalletId, UnitId), PositionState]` (addendum §2; C1 + C9 + C11).
2. **Definition.** The third state map. *Monotone carrier* (rows never deleted) with *Option accessor* (`None` ≠ `Some(zero)`); the two disciplines are orthogonal and both required (C1). Carries per-position economic state: `accumulated_cost`, `ccp_binding`, `entry_nav`, `hwm`, `accrued_{mgmt,perf}_fee`, `benchmark_nav_at_inception`, `mandate_breach_flags`, `subscription_redemption_cursor`, plus the SBL six-coordinate position vector (ledger §15 — `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)`).
3. **Minimum field set.** Per `(w, u)`: `{accumulated_cost (signed Decimal), ccp_binding?, entry_nav?, hwm?, hwm_date?, accrued_mgmt_fee?, accrued_perf_fee?, benchmark_nav_at_inception?, mandate_breach_flags?, position_vector ∈ ℝ^6 (SBL: own, onloan, borr, coll_post, coll_recv, coll_rehyp; degenerates to scalar `own` for non-lendable), per_field_handler_tag (C11), last_handler_invocation_id_per_field}`.
4. **Identity.** `(wallet_id, unit_id)` — the map key. `None` means "this `(w, u)` has never been touched"; `Some(zero_P)` means "touched, currently flat" — the two are operationally distinct (addendum C1) for VM-settle, wash-sale lookback, and record-date entitlement.
5. **Provenance.** Created by the first handler that touches `(w, u)` (typically a `Trade` event); mutated thereafter only by handlers whose C11 tag matches the field.
6. **Temporal semantics.** **Monotone (rows never garbage-collected) + bitemporal at the field level**. Replay is a literal fold (`apply_all(events)`); checkpoint boundaries do not affect outcome (P3). `Some(zero)` rows are retained for tax-lot lineage, wash-sale, 1099-B reconstruction (addendum §4.1 "Settled positions retain their rows").
7. **Failure consequences.** Garbage-collecting a flat row → wash-sale lookback breaks → tax reporting wrong → IRS reconciliation fails. Collapsing `None` to `Some(zero)` → record-date entitlement misfires (the wallet receives a dividend it should not, or fails to receive one it should) → P10 fails *and* an external reconciliation break opens. Direct cross-handler write (e.g., `settle` writes `hwm`) → C11 violated → field becomes non-deterministic → mutation testing (addendum §6) catches the bug, but in production it manifests as an irreproducible PnL anomaly. Mutating a closed-out (`Some(zero)`) row's `accumulated_cost` → conservation holds locally but the historical tax-lot ledger silently drifts.

### Category 9a — Valuation Records (`ValuationRecord`)

1. **Canonical name.** `ValuationRecord` (`ledger_valuation_v1.0.tex` §3 Definition val-record).
2. **Definition.** The output of one valuation cycle for unit `u` at time `t`. Distinct from market data (Cat 3) and from calibration state (9b): a `ValuationRecord` is the *result* of running the pricer on a market-data snapshot under a model.
3. **Minimum field set.** `{unit_id, timestamp, dirty_price, clean_price, accrued, greeks (model-tagged union — see 9c), model_id, market_data_snap_id, compute_ms, quality ∈ {FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED}, fsm_state, prev_record_ref (for chained PnL explain), unexplained_residual?, explain_pass?}`.
4. **Identity.** `(unit_id, timestamp, model_id)` — explicit because multiple models coexist (`ledger_valuation_v1.0.tex` §3.10 consensus; one record per `(unit, timestamp, model)`).
5. **Provenance.** The `PricingWorkflow(unit_id)` Temporal workflow (`ledger_valuation_v1.0.tex` §6 workflow pseudocode); the workflow's signed identity is the record's attestor.
6. **Temporal semantics.** **Append-only**, indexed by `timestamp` and `model_id`. APPROXIMATE records are computed from the FIRM record's Greeks; STALE records are flagged but retained (no overwrite of the underlying FIRM).
7. **Failure consequences.** Using an APPROXIMATE record where FIRM is required (official PnL, regulatory reports) → Principle "FIRM-Only PnL" violated → end-of-day flash diverges from official PnL → reconciliation break against accounting. Mixing models in PnL explain (using $\mathcal{M}_1$'s Greeks to explain $\mathcal{M}_2$'s price change) → spurious unexplained residual → FSM falsely transitions to Quarantined → cascading staleness on dependent DAG nodes.

### Category 9b — Calibration State ($x_{t|t}^{\text{certified}}$)

1. **Canonical name.** Posterior calibration state — the certified Kalman estimate (`ledger_valuation_v1.0.tex` §4).
2. **Definition.** The latent parameter vector $x_t \in \mathbb{R}^d$ representing the current market state, after Kalman update, after no-arbitrage projection (Calibration Manifesto Axiom A4 + A7). Examples: zero-rate vector at fixed tenors; ATM-vol + skew + curvature coefficients $(\sigma_0, s_0, c_1, ..., c_n)$ for the kernel-vol model; hazard-rate term-structure.
3. **Minimum field set.** `{calibration_object_id (e.g. USD_OIS_curve, SPX_vol_surface_2026Q2), tenor_or_strike_grid, x_t_t (mean, ℝ^d), P_t_t (covariance, d×d PSD), Q (process noise, d×d), R_t (observation noise, m×m), innovation_nu_t, mahalanobis_D2_t, gate_decision ∈ {accept, downweight, reject}, no_arbitrage_projection_applied ∈ {true, false}, certification_status ∈ {certified, fallback, stale}, fitted_at, fits_observation_set_ref}`.
4. **Identity.** `(calibration_object_id, fitted_at)` — one certified calibration per object per fit-time.
5. **Provenance.** A dedicated calibration Temporal workflow (`ledger_valuation_v1.0.tex` §4.7); inputs are Cat 3 quotes; signature is the calibration workflow's identity.
6. **Temporal semantics.** **Append-only point-in-time**. The current best estimate is the most recent certified fit; older fits are retained for replay and for back-testing the gate decision (Cat 5c idempotency on `calibration_object_id`).
7. **Failure consequences.** Using a non-certified estimate downstream → no-arbitrage violations propagate into prices → P10 fails for cross-asset products → stale-but-flagged is *better* than fresh-but-uncertified (the addendum's "Two Disciplines" parallel: visibility of state matters as much as the state itself). Cross-asset coherence loss (`ledger_valuation_v1.0.tex` §4.9) → SPX-SX5E spread option price drifts → unexplained residual on the spread itself even though both legs are "fresh."

### Category 9c — Greeks (Sensitivity Jacobians)

1. **Canonical name.** Greeks tagged-union, model-discriminated (`ledger_valuation_v1.0.tex` §3.13 Greeks-by-instrument-class).
2. **Definition.** A model-specific bundle of partial derivatives of price with respect to observables and parameters, at the current $(O, \Theta)$. Dimension $= |\text{observables}| + |\text{parameters}|$, model-dependent (the Vanishing Vega Principle — `ledger_valuation_v1.0.tex` §3.3).
3. **Minimum field set.** `{model_id, invariant_label (e.g. "sigma_imp", "heston_params", "sigma_loc_surface", "kernel_params"), method ∈ {ANALYTICAL, BUMP, AAD, PATHWISE, LIKELIHOOD_RATIO}, bump_size?, observable_sensitivities {delta, gamma, theta, rho, ...}, parameter_jacobian (dim = |Θ|), cross_sensitivities {vanna, volga, charm, ...} (for total-Greek computation per `ledger_valuation_v1.0.tex` §3.7)}`.
4. **Identity.** Embedded in the parent `ValuationRecord` identity (Cat 9a); not an independent record.
5. **Provenance.** The Greeks-computation Temporal activity (`pricing-greeks` task queue, `ledger_valuation_v1.0.tex` §6.6); the `method` field carries the computation discipline.
6. **Temporal semantics.** **Snapshot, frozen** at the parent `ValuationRecord.timestamp`. Used for Taylor approximation in state Explained until the next FIRM cycle.
7. **Failure consequences.** Reporting scalar "vega" for a Heston-priced option → a 5-vector projected onto one axis → 4 dimensions of risk become unexplained PnL → P10 fails diagnostically (the residual is real risk, not noise). Using `partial` Greeks where `total` Greeks (smile-adjusted, `ledger_valuation_v1.0.tex` §3.7) are required → hedge error equal to `(δ_total - δ_partial) · ΔS = Σ_i (∂P/∂θ_i)(∂θ_i/∂S) ΔS` (Remark "Unexplained PnL as parameter martingale violation").

### Category 9d — Pricing DAG Topology

1. **Canonical name.** $G = (N, E)$ where $N = N_U \cup N_M \cup N_C$ (`ledger_valuation_v1.0.tex` §5 Definition pricing-dag).
2. **Definition.** The directed acyclic graph of pricing dependencies: market-data leaf nodes → calibration nodes → unit nodes. Acyclicity is enforced at unit registration (`ledger_valuation_v1.0.tex` §5 Invariant acyclicity).
3. **Minimum field set.** `{nodes ⊆ {(node_id, node_type ∈ {MARKET, CALIBRATION, UNIT}, payload_ref)}, edges ⊆ N×N, topological_order, frozen_at_cycle (the cycle on which this topology snapshot operates)}`.
4. **Identity.** `(dag_snapshot_id, frozen_at_cycle)` — DAG mutates between cycles only (`ledger_valuation_v1.0.tex` §5.3 DAG mutation).
5. **Provenance.** Built by `BuildPricingDAG(unit_store)` (`ledger_valuation_v1.0.tex` §5.1); edges come from each unit's `smart_contract.pricing_dependencies()`.
6. **Temporal semantics.** **Frozen-per-cycle**; new units extend the next cycle's DAG; terminated units are removed. The DAG itself is a derived view of `ProductTerms ∪ UnitStatus`, but it is materialised because acyclicity is a global property and must be checked at each rebuild.
7. **Failure consequences.** Cycle in the DAG → infinite loop in topological evaluation → liveness violation → no prices published → all downstream FSMs go Stale. Mid-cycle mutation → some DAG nodes operate on old topology, others on new → cross-asset consistency lost.

### Category 10 — Regulatory and Accounting Projection Data

1. **Canonical name.** Internal classification and reporting overlays (ledger §10 regulatory).
2. **Definition.** Firm-internal classifications and reporting flags that *project* a unit or position into a regulatory or accounting frame. Distinct from external regulatory reference data (Cat 2.6) because these are *the firm's* decisions about how to apply the rules, signed by the relevant control function.
3. **Minimum field set.** `{accounting_classification ∈ {FVTPL, FVOCI, AC} per IFRS 9 / ASC 815-321-820, hedge_designation_ref?, sftr_reportable, sftr_uti, slate_loan_id, emir_uti, emir_article_4_eligible, mifid_post_trade_eligible, csdr_buy_in_class, basel_risk_weight_class, cass_segregation_class, tax_lot_lineage_ref, transfer_pricing_arrangement_ref}`.
4. **Identity.** `(unit_id, classification_kind, valid_from)` for unit-level; `(wallet_id, unit_id, classification_kind, valid_from)` for position-level.
5. **Provenance.** Control function (Risk, Finance, Tax, Compliance) at unit registration or position opening; signed by the relevant function head per the F2 RACI table (StatesHome risk register). Some values are derivable from Cat 2.6 + product type (e.g. EMIR Article 4 eligibility from product class + counterparty class); the *derivation* is recorded.
6. **Temporal semantics.** **Bitemporal**. Re-classifications are common (an FVOCI debt instrument failing the SPPI test must be re-classified to FVTPL) and are themselves recordable lifecycle events.
7. **Failure consequences.** Wrong IFRS 9 classification → fair-value changes flow to wrong P&L line → economic PnL (path-independent, ledger §4.3) is correct but accounting PnL diverges → audit failure. Missing UTI on an SFTR-reportable transaction → submission rejected → ESMA fine. Missing tax-lot lineage on a partially-closed position → wash-sale adjustments wrong → IRS Form 8949 incorrect.

### Category 11 — Identity, Capability, and Wallet Metadata

1. **Canonical name.** `WalletRegistry : Map[WalletId, WalletMetadata]` (addendum §2 — "non-state, non-financial sidecar").
2. **Definition.** The fourth map of the StatesHome ruling — explicitly *not state*. Carries identity, KYC, permissions, audit cursor; never participates in conservation.
3. **Minimum field set.** `{wallet_id, wallet_kind ∈ {real, virtual, custodian, ccp_clearing, treasury, broker_omnibus, client_subaccount, mandate_account, qis_strategy_account, sbl_pool, collateral_segregated, ...}, owning_entity_lei?, kyc_status, capability_scope (which units / which event classes this wallet may participate in — C4), audit_cursor, external_account_mappings (custody, settlement, regulatory reporting), parent_book_ref?, mandate_unit_ref? (binds wallet to a managed-account u_MA), policy_version}`.
4. **Identity.** `wallet_id`. Stable across the wallet's lifetime; never reused.
5. **Provenance.** Registered at wallet onboarding (real wallets: KYC-driven; virtual wallets: minted from CDM party reference + LEI + account suffix per ledger §2.4).
6. **Temporal semantics.** **Bitemporal mutable** — KYC status, capability scope, and external account mappings change; each change is an append-only event. The wallet identity (`wallet_id`) is permanent.
7. **Failure consequences.** Capability scope leak → handler with too-broad scope reads cross-mandate state → C4 violated → mandate breach detection produces false negatives → fiduciary breach undetected. Wallet-id reuse after retirement → time travel returns wrong owner → audit chain broken.

### Category 12 — Reconciliation and External-Attestation Data

1. **Canonical name.** Settlement-status lifecycle and external-statement reconciliation (ledger §8.7 confirmation return path; §6.4 reconciliation taxonomy).
2. **Definition.** Data crossing back from external systems (CSDs, custodians, CCPs, counterparties, regulators) confirming or contradicting the ledger's record. Distinct from oracle data: oracles *trigger* contracts; reconciliation data *confirms* prior actions.
3. **Minimum field set.** `{reconciliation_event_id, settlement_status ∈ {EXECUTED, INSTRUCTED, SETTLED, FAILED, PARTIALLY_SETTLED, CANCELLED}, transaction_id_ref, external_message_id (ISO 20022 sese.025, camt.054), external_attestor_lei, recorded_at, settled_at?, fail_reason?, virtual_wallet_balance_at_recon, external_balance_at_recon, break_amount = ledger_balance - external_balance, break_classification ∈ {custodian_break, nostro_vostro, counterparty_dispute, csdr_fail, none}}`.
4. **Identity.** `(transaction_id, external_message_id)`; reconciliation is many-to-one (a settlement instruction may produce several confirmations: instruction-receipt, settlement-confirmation, settlement-fail, partial-fill).
5. **Provenance.** External counterparty (custodian camt.053, sese.025; CCP confirmation; CSD settlement confirmation). Each carries a wire signature; the ledger stores the raw message and a parsed projection.
6. **Temporal semantics.** **Append-only**, bitemporal. A `FAILED` confirmation can be followed by a `SETTLED` confirmation after buy-in or extension; both are retained.
7. **Failure consequences.** Missing reconciliation → ledger balances diverge from custodian → break undetected → on next custodian statement, gross discrepancy is found with no incremental audit trail. Mis-mapped external message → wrong transaction marked SETTLED → real-world settlement fail goes unmarked → counterparty default risk realised without forewarning. Note: the corpus argues (ledger §1.3, §2.6) that internal reconciliation is structurally unreachable; *external* reconciliation remains and lives in this category.

### Category 13 — Lifecycle-Schedule / Due-Event Data

1. **Canonical name.** Due-event scheduler state (ledger §13.4 due-event scheduler — "resolving the liveness gap").
2. **Definition.** The scheduled but not-yet-fired lifecycle events: coupons due, resets due, expiries pending, margin calls due, recall deadlines under SBL, fee crystallisation dates. Required for *liveness* — without this category, the system has no way to know that a coupon needs to fire on a Sunday.
3. **Minimum field set.** `{schedule_id, unit_id, event_kind ∈ {coupon, reset, expiry, mtm, margin_call, recall_deadline, fee_crystallisation, subscription_cutoff, redemption_cutoff, corp_action_record_date, corp_action_pay_date, ...}, due_at, business_day_adjusted_due_at, calendar_id_ref, status ∈ {scheduled, fired, missed, superseded, cancelled}, idempotency_key, retry_count}`.
4. **Identity.** `(unit_id, event_kind, due_at, sequence)` — the sequence disambiguates re-scheduled events.
5. **Provenance.** Computed at unit registration from `ProductTerms` (the schedule is a *projection* of the immutable terms onto a calendar) and stored as a materialised view to permit efficient liveness scanning. Mutated by amendments (Cat 1b) — a Preserving amendment that changes a coupon date emits a `StateDelta` that updates Schedule rows.
6. **Temporal semantics.** **Materialised projection of `ProductTerms` × Calendars × business-day rules**. Append-only at the row level (a re-scheduled coupon is a new row referencing the old by `superseded_by`). Mutable status field per row.
7. **Failure consequences.** Missing schedule → coupon never fires → bondholder unpaid → P5 / P6 idempotency vacuously hold but the lifecycle theorem (Property 5 — value invariance for deterministic events) fails because the deterministic event never happened. Late firing → double-payment risk if the reconciliation re-fires the handler without idempotency. Wrong calendar reference → schedule shifts under regional holiday additions — see Cat 2.1 failure mode.

### Category 14 — Settlement-Layer Projection Data

1. **Canonical name.** `SettlementInstruction` (ledger §8.1 Definition).
2. **Definition.** The deterministic projection of a `SETTLEMENT` or `COLLATERAL` transaction into a settlement-layer wire-message struct. Distinct from the move stream (Cat 7) — moves are economic; instructions are operational. Distinct from reconciliation data (Cat 12) — instructions go *out*; reconciliation comes *in*.
3. **Minimum field set.** `{instruction_id (= transaction_id), trade_date, settlement_date, settlement_type ∈ {DVP, FOP, CASH}, security_isin?, security_quantity?, delivering_party?, receiving_party?, cash_currency?, cash_amount?, cash_payer?, cash_receiver?, counterparty_lei, execution_venue_mic, ssi_lookup_ref (settlement-layer enrichment), csd_account (enrichment), priority_tier (enrichment)}`.
4. **Identity.** `instruction_id` = `transaction_id` (1:1 with the originating transaction). Idempotency: re-projecting the same transaction yields a bit-identical instruction (the projection is pure — ledger §8.1).
5. **Provenance.** `settle_projection(tx)` (ledger §8.1 pseudocode); enrichment fields come from settlement layer's SSI database / CSD account map.
6. **Temporal semantics.** **Derived projection** of Cat 7. Re-derivable from the source transaction; not stored as authoritative source. Bitemporal at the *enrichment* layer (SSI may change; the historical instruction must be reconstructible against the historical SSI).
7. **Failure consequences.** Projection non-determinism → rerun produces different instruction → settlement layer rejects on duplicate-with-different-content → trade unsettled. Missing enrichment → instruction emitted incomplete → CSD rejection → settlement fail recorded as Cat 12.

### Category 15 — SBL-Specific Data

1. **Canonical name.** `SBLUnitState` and the six-coordinate position vector (ledger §15).
2. **Definition.** The data introduced by the Generalised Position Model where the scalar balance is insufficient (ownership ≠ possession). Carried as part of `PositionState[(w, u)]` (Cat 8c) but enumerated separately because (i) it adds five new coordinates per `(w, u)`, and (ii) the SBL loan unit itself (`u_loan`) has its own dedicated state schema.
3. **Minimum field set.**
   - **Position-vector coordinates (per `(e, u)` for lendable `u`):** `{own, onloan, borr, coll_post, coll_recv, coll_rehyp}` — each in $\mathbb{R}$, each modified only by single-coordinate moves.
   - **`SBLUnitState` (per loan `u_loan`):** `{loan_id, lender, borrower, agent, isin, quantity, original_qty, term_type ∈ {open, term}, maturity_date?, fee_rate, rebate_rate, collateral_type ∈ {cash, non_cash, equity_basket, gov_bond_basket}, margin_pct, haircut_pct, collateral_ccy, triparty_agent?, legal_regime ∈ {GMSLA_2010, MSLA, OSLA, GMRA, jurisdiction-specific}, rehyp_consent ∈ {yes, no, capped(pct)}, lifecycle_stage ∈ {PENDING, ACTIVE, RECALLED, PARTIALLY_RETURNED, RETURNED, CANCELLED, DEFAULTED}, settlement_status, recall_date?, recall_qty?, sftr_uti, slate_loan_id, execution_ts, trade_date, last_mark_date, accrued_fee, fee_accrual_log}`.
4. **Identity.** Loan unit: `loan_id`. Position-vector coordinates: `(entity_id, unit_id)`.
5. **Provenance.** SBL smart contract on `loan_settled` event (ledger §15.6); modifications by SBL state-machine transitions (ledger §15.5 state-machine table).
6. **Temporal semantics.** Same as Cat 8c — monotone carrier, append-only at the field level. The `SBLUnitState.fee_accrual_log` is itself an append-only sub-stream.
7. **Failure consequences.** Coordinate conflation (e.g., debiting `own` instead of `onloan` on lend) → conservation holds (ledger §15 Single-Coordinate Move Principle) but lender's PnL collapses by 40% as in the corpus's motivating example → IFRS 9 §3.2.6 violated → audit failure. Missing `legal_regime` → close-out netting on default uses wrong regime → recovery wrong → counterparty dispute → P11–P20 (SBL-specific invariants per ledger §15) violated.

### Category 16 — Virtual-Ledger and TRS Data

1. **Canonical name.** Virtual ledger $\mathcal{L}_v$ (ledger §6.5 Definition; §6.6 TRS).
2. **Definition.** A *complete second instance* of the ledger framework, in which every wallet is virtual. It carries its own move stream, unit state, conservation. Connected to the real ledger only by TRS contracts which observe $V_t^v$ and emit real-ledger settlement moves. *No move ever crosses* (P7 isolation).
3. **Minimum field set.** Inherits *all* categories above (1–15) — recursively. Plus the binding metadata: `{virtual_ledger_id, real_ledger_anchor_trs_contract_ref, observation_price_vector_source, performance_basis ∈ {gross, net_of_fees}, isolation_attestation}`.
4. **Identity.** `virtual_ledger_id`; one $\mathcal{L}_v$ per simulated strategy / index / basket. Multiple TRS contracts can reference the same $\mathcal{L}_v$.
5. **Provenance.** Created administratively (a strategy decision); destroyed administratively (subject to retention rules — see F8 of StatesHome risk register).
6. **Temporal semantics.** Same bitemporal lattice as the real ledger; isolated event stream.
7. **Failure consequences.** Isolation violation (a move crosses) → P7 violated → virtual simulation contaminates real positions. Price-vector mismatch between $\mathcal{L}_v$ valuation and TRS settlement (ledger §6.6 "Price consistency") → settlement diverges from reported performance → unexplained PnL on the TRS itself.

### Category 17 — Mandate / Strategy Configuration

1. **Canonical name.** `ProductTerms[u_MA]` and `ProductTerms[u_QIS]` for managed-account / strategy units (addendum §4.2, §4.3).
2. **Definition.** The mandate-as-unit and strategy-as-unit pattern from the addendum. Mandate text, fee schedule, benchmark identity, position limits, HWM hurdle methodology, crystallisation frequency — all live at `ProductTerms[u_MA]`. Strategy-level (vol target, barrier, universe, share-class index start, rebalance rule) live at `ProductTerms[u_QIS]`. Per-client values (HWM value, accrued fees, breach flags) live at `PositionState[(w_client, u_MA)]` (Cat 8c).
3. **Minimum field set (terms-side, complementing 1a):** `{mandate_text_hash, fee_schedule (mgmt, perf, hurdle), benchmark_id (links to Cat 2.7), max_position_limits, max_concentration_limits, max_leverage, currency_restrictions, eligible_universe, hwm_methodology, hwm_hurdle, crystallisation_frequency, lockup, gating_rules, redemption_notice_period, vol_target?, barrier_methodology?, rebalance_rule?, share_class_index_start_date?, share_class_index_start_value?}`.
4. **Identity.** `u_MA` (mandate unit id) or `u_QIS` (strategy unit id). C8 fungibility predicate decides whether amendments are Preserving (HWM tweak within band) or Breaking (benchmark swap).
5. **Provenance.** Mandate document (signed by client + manager); QIS rule-book (signed by strategy committee). The hash is anchored in the move stream at unit registration.
6. **Temporal semantics.** Same as Cat 1a/1b — append-only versioned, with fungibility-preserving / breaking discipline.
7. **Failure consequences.** Mandate-amend without C8 evaluation → silent fungibility break across multi-mandate clients → addendum §4.2's "two HWMs" pattern collapses into one → fees mis-crystallised. Missing benchmark ref → performance attribution undefined → fees uncomputable.

### Category 18 — Obligation-Liveness Data

1. **Canonical name.** Obligation tracking under the liveness framework (ledger §13.7 obligation liveness).
2. **Definition.** Open obligations whose discharge has a deadline, and whose breach triggers a compensating event (close-out netting, mandatory buy-in under CSDR, default declaration). Examples: CSA margin calls, recall returns under SBL, settlement fails approaching CSDR penalty thresholds. Distinct from due-event schedule (Cat 13) — schedule is firm-internal; obligation liveness is bilateral / external.
3. **Minimum field set.** `{obligation_id, obligation_kind ∈ {csa_margin_call, sbl_recall_return, settlement_fail_csdr, manufactured_payment, dividend_record_to_pay, ...}, obligor_lei, obligee_lei, due_at, grace_period_end, close_out_handler_ref, status ∈ {open, discharged, breached, escalated, closed_out}, P21_P23_invariant_state}`.
4. **Identity.** `obligation_id` (UUID); `(obligation_kind, contract_ref, due_at)` is the semantic key.
5. **Provenance.** Created by the contract that imposes the obligation (CSA margin contract, SBL contract); status mutations come from confirmation events (Cat 12) or compensation handlers.
6. **Temporal semantics.** Append-only event stream per obligation; current status is a fold.
7. **Failure consequences.** Missed deadline without escalation → P21–P23 violated → counterparty exposure unmanaged → default-event handling kicks in late → close-out value sub-optimal → real economic loss. Closing an obligation without confirmation → balance-sheet looks clean but the external counterparty still believes the obligation is open → bilateral dispute.

### Category 19 — Audit / Provenance / Lineage Sidecars

1. **Canonical name.** Audit cursor and lineage metadata.
2. **Definition.** The data the system maintains *about its own data* — workflow lineage, approval chains, control-function sign-offs, the full CDM `BusinessEvent` payloads stored alongside transactions, the iteration-log style provenance the addendum itself preserves under `StatesHome_work/`.
3. **Minimum field set.** `{lineage_event_id, target_record_kind, target_record_id, action ∈ {created, amended, classified, signed_off, escalated, audited, replayed}, actor_lei_or_workflow_id, actor_role, attached_evidence_hashes, approval_chain (ordered list of (signer_lei, signed_at, signature)), workflow_step_id (CDM `WorkflowStep`), recorded_at}`.
4. **Identity.** `lineage_event_id`.
5. **Provenance.** Self-attesting (the audit cursor is itself audit-trailed by the next layer — eventually anchored in a hash chain or cryptographic notary).
6. **Temporal semantics.** Strictly append-only; never deletable; subject to retention floor (regulatory minimum, typically 7+ years for trade data per MiFID II Art 16).
7. **Failure consequences.** Missing lineage → "who decided this and when" cannot be answered → MAR record-keeping fail → regulatory penalty. Audit-cursor desync → on disaster recovery, the system replays from a stale cursor and re-emits events that have already been confirmed externally → double-spending into reality.

---

## 3. Disagreements with the Floor (Explicit)

I flag four explicit disagreements with the Phase 1 floor as stated:

**D1. Floor 1 ("Static data") is misnamed.** Nothing in the Ledger framework is "static" in the strict sense. Even the most immutable data — the `unit_id` itself — is governed by an append-only versioning discipline at the `TermsVersion` layer (C6, C8). The correct discipline is *append-only versioned*. The word "static" invites in-place mutation under operational pressure ("just patch the multiplier"); "append-only versioned" is a constant explicit reminder that C6 forbids it. **Recommendation: rename Floor 1 to "Immutable per-issuance terms (append-only versioned)" and split into 1a/1b as I have done.**

**D2. Floor 4 ("Oracle data") and Floor 3 ("Market data") share a definitional ambiguity.** Both are externally attested. The corpus distinguishes them: market data feeds the *Kalman filter* (a statistical inference); oracle data feeds *contract predicates* (a deterministic firing decision). The dividing line is whether the datum is *aggregated and smoothed* (market: yes; oracle: no — a barrier hit cannot be Kalman-smoothed). I have kept them separate; my Cat 3 / Cat 4 retain the floor's intent but pin the distinction explicitly: **Cat 3 = $y_t$ feeding $H_t$**; **Cat 4 = oracle event firing a contract predicate**.

**D3. Floor 5 ("Smart-contract execution data") is a single bucket for three things that fail the Karpathy substitution test.** Handler inputs (5a), handler outputs / `StateDelta` (5b), and idempotency tokens (5c) have *different identities*, *different provenance*, and *different failure consequences*. Conflating them is the Minsky denormalisation trap (addendum §6 Pareto analysis on F).

**D4. Floor 6 ("Listed-instrument detail data") subsumes part of Floor 2 (reference data) and part of Floor 1 (static). I have kept it as Cat 6 because for *listed* instruments specifically, the `ContractSpec` *is* the unit identity (ledger §3.2)** — distinct from the rest of reference data, which is universe-level rather than instance-level. But it is genuinely a sub-genus of reference data, and a sound alternative architecture would absorb it into a more granular Floor 2 (which is what my Cat 2 sub-categorisation already does). The independent presence of Floor 6 in the brief is redundant *unless* the intent is to emphasise that contract-spec data has its own ingestion pipeline (vendor reference data → SecDef → unit registry), which is operationally true. **I retain it but flag the redundancy.**

---

## 4. Bourbaki Hygiene Notes

The enumeration is *not* a database schema. It is a *minimum basis* of the data the framework manipulates, in the sense of the addendum's "minimum basis of the problem" (§5.1, "three independent forcing constraints"). Removing any category breaks at least one of:

- the Karpathy substitution test (positions, handlers, statuses are not collapsible);
- the temporal-discipline test (append-only versus mutable versus monotone cannot share a map);
- the conservation-proof obligation (C2 must hold per event class, which forces 5a/5b/5c separation);
- the boundary-crossing direction test (oracles fire in; reconciliation comes back; settlement projection goes out — three categories, three directions).

Adding a category requires the same justification. I have added six (F7 lifecycle/event-stream, F8 state, F9 valuation/pricing-internal, F10 regulatory/accounting projection, F11 identity/capability, F12 reconciliation/external attestation), plus three sub-splits (F1a/F1b, F5a/F5b/F5c). For each, the justification is named above.

I have *not* added speculative categories (e.g., "machine-learning model artefacts," "feature store data") because the corpus does not require them. They may be needed in implementation but are out of scope for the data the *framework* requires.

---

## 5. Verification Against the Bourbaki Checklist

| Criterion | Verification |
|---|---|
| Correctness | Every category cited to a corpus label or section. |
| Completeness | All hypotheses and identity rules stated. Bitemporal vs append-only vs monotone discipline explicit per category. |
| Minimality | No category can be merged without violating a named test (Karpathy / temporal / conservation / direction). |
| Clarity | Definition precedes minimum field set precedes identity precedes failure mode in every entry. |
| Precision | Every CDM enum, every map name, every invariant referenced by its corpus label. |
| Consistency | The three StatesHome maps are the ground truth; valuation FSM is grafted onto `UnitStatus`; CDM payload is grafted onto the move stream. No symbol collisions. |
| Independence | The document's category list is self-contained: no category appeals to a definition not present in the seven mandatory fields of another category. |

---

*Document compiled 2026-04-29. No cross-talk with other Phase 1 reviewers. Discipline: Bourbaki rigour applied to a financial-system data ontology.*
