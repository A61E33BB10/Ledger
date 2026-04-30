# Phase 1 — Independent Data Enumeration (Grothendieck)

> *"The sea advances insensibly in silence... yet it finally surrounds the resistant substance."*

The brief asks: *what data does the Ledger framework require?* I read the v10.3 spec, the StatesHome addendum, and the Valuation companion as a single corpus. My discipline is to refuse the question in its naive form and ask first **what category we are working in**, **what the universal properties of each candidate datum are**, and **whether the floor list is a presentation of fewer underlying functors**.

This phase has two passes:

1. **Pass A** — Floor enumeration in the user's vocabulary, exhaustive within each named category, with the seven mandatory fields per item.
2. **Pass B** — Structural collapse. I argue the floor categories are not the natural objects of the data category; they are presentations of three sheaves over a common base. Items are restated as objects of the structurally minimal classification.

Both passes are present. Pass A is the user's deliverable. Pass B is my discipline's contribution.

Conventions used throughout:

- **Identity** — the canonical key under which the datum is addressed; this is the *Yoneda probe*: the object IS the way it is addressed.
- **Provenance** — the morphism $\text{source} \to \text{datum}$ recording who emitted it.
- **Temporal semantics** — point-in-time (PIT), as-of, bitemporal, or append-only. Bitemporal means two time axes (economic / valid time *and* knowledge / booking time) are independently navigable.
- **Failure consequences** — the invariant or downstream functor that fails if this datum is missing or wrong.

Section/label references are to `ledger_v10.3.tex`, `ledger_v10.3_addendum_stateshome.tex`, and `ledger_valuation_v1.0.tex` unless noted.

---

# Pass A — Floor Enumeration (User's Vocabulary)

The floor is six categories: Static, Reference, Market, Oracle, Smart-contract execution, Listed-instrument detail. I cover each exhaustively. Where the spec is silent I extrapolate by structural necessity (clearly marked).

I number items globally **A1 … An** so Pass B can refer to them.

---

## 1. Static Data

*"Configuration that defines the Ledger's structure but is not itself a market or contractual fact."* In a category-theoretic reading these are the **objects of small categories** that index everything else: the wallet category, the unit-type category, the entity category, the calendar category, the model category. They change rarely; they are administered, not transacted.

### A1. Wallet Registry

1. **Canonical name** — `WalletRegistry` (StatesHome §2 explicitly carves this out: "non-state, non-financial sidecar").
2. **Definition** — The total function `WalletId → WalletMetadata` that names every wallet in the Ledger (real and virtual) and records the non-economic facts about it: who owns/controls it, what KYC status applies, what audit cursor has been reached. *Wallets themselves are mathematical partitions of position space (§2.1); this registry is the bookkeeping layer above them.*
3. **Minimum field set** — `wallet_id`, `wallet_type ∈ {REAL, VIRTUAL, BOOK_REFERENCE, CLEARINGHOUSE_VIRTUAL, CUSTODIAN_VIRTUAL, COLLATERAL, ESCROW, TREASURY, CLIENT_SUB, STRATEGY_OWN, MANDATE_BOOK}`, `display_name`, `parent_wallet_id` (optional, for sub-account hierarchies), `controlling_entity_id` (LEI or internal entity), `legal_status` (whether wallet represents a legal entity, a partition of one, or a virtual mirror of an external party), `external_account_mapping_ref` (pointer to A20).
4. **Identity** — `wallet_id`, an opaque internal identifier. Crucially **not** an external account number — the mapping to BIC/IBAN/CSD account lives in A20 (Settlement Mapping). The Yoneda probe: a wallet IS the totality of moves whose `from` or `to` field equals its id.
5. **Provenance** — Onboarding workflow (KYC / account opening for clients; internal administrative action for books and virtual mirrors). Every change to wallet metadata is itself an event.
6. **Temporal semantics** — Bitemporal append-only. The current state is a function of the registry event log; historical KYC states must be reconstructable for audit. C10 (StatesHome) prohibits silent re-registration; the analogous discipline applies here.
7. **Failure consequences** — Every move in the move stream becomes ungrounded: source/destination wallets cannot be resolved. P3 (referential integrity, §11) fails. Settlement projection (§9.1) cannot enrich the move because counterparty-side identifiers are unreachable.

### A2. Unit Registry — Tier 3 (UnitId → ProductTerms ⊕ UnitStatus)

1. **Canonical name** — `UnitStore.Tier3` realised as the StatesHome triple `(ProductTerms, UnitStatus, PositionState)`. The *static* portion is `ProductTerms`; the *mutable shared* portion is `UnitStatus`; the *per-position* portion is **not** static and appears under A30.
2. **Definition** — The total functor on registered unit ids that returns (i) immutable, versioned product terms (`NonEmptyList[TermsVersion]`, append-only, C6), and (ii) shared mutable status (lifecycle stage, last settlement price, current weights, etc.). The unit is whatever inhabits these two maps; conversely the maps are total on the unit set (C5, C7).
3. **Minimum field set** —
   - `unit_id`
   - `unit_type ∈ {CASH, EQUITY, LISTED_DERIV, OTC_DERIV, BOND, STRUCTURED, MANAGED_ACCOUNT_MANDATE, QIS_STRATEGY, SBL_LOAN, INDEX, BENCHMARK, TOKENIZED_SECURITY, LOCATE}`
   - **ProductTerms (NonEmpty list of TermsVersion):** `tv.version_id`, `tv.effective_from`, `tv.fields` (product-type-specific: e.g. `multiplier, currency, expiry, ccp, exchange, isin, strike, option_type, settlement_type, notional, fixed_rate, day_count, reset_schedule, fee_schedule, mandate_text, benchmark_unit_id, max_position_limits, hwm_methodology, crystallisation_frequency, ...`), `tv.is_fungibility_preserving` predicate (C8).
   - **UnitStatus:** `lifecycle_stage`, `last_settlement_price`, `last_settlement_date`, `current_weights`, `nav_index`, `triggered_barrier`, `superseded_by` (chain to successor unit on Breaking amendment), `cum_dividend`, `last_dividend_date`.
   - `product_ref` (pointer to Tier 2, A3); `smart_contract_ref` (pointer to A4).
   - `created_by_tx_id`, `created_at`.
4. **Identity** — `unit_id`, derived deterministically from the CDM object (§3.7): hash of contract spec for listed instruments, UTI / metadata key for OTC. The derivation is injective by §3.7. *This is the load-bearing fact: identity is determined by the morphism `Trade → unit_id`, not by an opaque label.*
5. **Provenance** — Listed: reference data feed (A11) at listing. OTC: trade execution (A24) — the CDM `Trade` object IS the unit definition. Cash: pre-registered at system inception. Mandates and QIS strategies: explicit `register` event. C10: re-registration of an existing `unit_id` is a hard error.
6. **Temporal semantics** — `ProductTerms`: append-only, versioned (C6). `UnitStatus`: mutable but per-write logged (so the projection at any historical $t$ is reconstructable from the event log). Together: bitemporal — the version chain gives valid time, the event log gives knowledge time.
7. **Failure consequences** — Without ProductTerms, no smart contract can fire (no schedule, no strike, no expiry). Without UnitStatus, lifecycle totality (C5) is broken: an untraded option cannot transition LISTED → ACTIVE → EXPIRED, and the LISTED defaults are missing. P6 (immutability of terms) and P7 (no in-place mutation of identity) both fail. The valuation FSM cannot transition out of UNPRICED because pricer dependencies cannot be resolved.

### A3. Product Registry — Tier 2

1. **Canonical name** — `UnitStore.Tier2` (Product Registry, §3.3.2).
2. **Definition** — Map from product-type qualification (a CDM `ProductQualification` result) to the smart-contract template that governs all units of that product type. One entry per product *type*, not per unit. *Categorically: this is the functor `ProductType → SmartContract` whose left adjoint is the unit-to-product-type qualification.*
3. **Minimum field set** — `product_type_id` (e.g. `EU_EQ_INDEX_OPTION_CASH_SETTLED`), `cdm_qualification_predicate` (which `EconomicTerms` patterns match), `smart_contract_template_ref`, `lifecycle_state_schema_ref` (the type of `unit_status` for this product), `position_state_schema_ref` (the type of `position_state` rows for this product), `valuation_dag_template` (which observables and parameters this product needs — links to A14, A15), `created_at`.
4. **Identity** — `product_type_id`. Created on first encounter of the qualification by Tier 3 registration.
5. **Provenance** — Auto-created from Tier 3 registration when a new qualification is encountered; thereafter immutable (§3.3.2).
6. **Temporal semantics** — Append-only, immutable per entry. (Versioning of templates themselves is governed by A6.)
7. **Failure consequences** — Tier 3 cannot bind a smart contract to a unit; the executor rejects every move on units of that product type as unbound. The CDM `BusinessEvent` cannot be mapped to ledger primitives because the lifecycle engine cannot dispatch.

### A4. Smart Contract Registry

1. **Canonical name** — `SmartContractRegistry`.
2. **Definition** — Versioned catalogue of the deterministic move-generating programs (§5.1). One entry per (contract template, version). Each entry is a pure function specification: signature, code reference, dependencies, version pin.
3. **Minimum field set** — `contract_id`, `contract_version` (semver-style), `code_ref` (artefact pointer to the deterministic implementation), `signature` (input/output schema, including which `ProductTerms` fields, which `UnitStatus` fields, which market-data nodes and which `PositionState` rows it reads/writes), `field_writer_map` (C11: the unique handler permitted to mutate each `PositionState` field), `cdm_event_intents_supported`, `arithmetic_precision_spec` (decimal places, rounding rule — Bankers'/round-half-to-even per §5.1), `idempotency_token_strategy`, `published_at`, `superseded_by` (optional).
4. **Identity** — `(contract_id, contract_version)`. Versioning is mandatory because reproducible time travel requires version-pinning of the contract code (§17.2 limitation 9).
5. **Provenance** — Engineering release process; subject to C8-style fungibility predicate when amending: Preserving amendments add a new version that handles the same product type identically; Breaking amendments require a new `contract_id`.
6. **Temporal semantics** — Append-only versioned. A unit registered against `(contract_id, vN)` continues to be processed by `vN` even when `vN+1` exists, unless explicit migration. Replay must select the contract version that was bound at the original event time (CDM coexistence, §10.10).
7. **Failure consequences** — Replay non-determinism: `apply_all(events)` produces different results on different days because the contract code drifted. P3 (replay determinism) fails; P9 (lifecycle purity) fails. Time travel becomes a fiction.

### A5. Entity / Counterparty Master

1. **Canonical name** — `EntityMaster` (or `LegalEntityRegistry`).
2. **Definition** — Authoritative record of every legal entity that appears in the system: own legal entities, counterparties, custodians, exchanges, CCPs, regulators, agent lenders, beneficial owners, prime brokers, triparty agents. Distinct from `WalletRegistry` (A1) — wallets are *partitions of position space*; entities are *legal persons*. A single entity can control many wallets; a single wallet always belongs to (or mirrors) one entity.
3. **Minimum field set** — `entity_id` (internal), `lei` (ISO 17442 LEI when applicable), `bic` (when applicable), `legal_name`, `entity_type ∈ {OWN, CLIENT, COUNTERPARTY, CCP, CUSTODIAN, EXCHANGE, REGULATOR, AGENT_LENDER, TRIPARTY_AGENT, PRIME_BROKER, BENEFICIAL_OWNER, ISSUER}`, `jurisdiction`, `parent_entity_id` (group hierarchy), `mifid_classification`, `consent_flags` (rehyp consent, etc.), `kyc_status`, `kyc_expiry`.
4. **Identity** — `entity_id`. LEI is the global Yoneda probe (the way the entity is addressed by every other system). Where LEI is unavailable (e.g. retail clients), an internal id is canonical.
5. **Provenance** — Onboarding (clients, counterparties); GLEIF (LEI lookup); ANNA (BIC); regulatory registries (CCPs, exchanges).
6. **Temporal semantics** — Bitemporal. The fact "Entity X had LEI Y" must be queryable as-of any historical $t$ for SFTR / EMIR / SLATE reporting (which uses the LEI at trade time, not today's LEI after a corporate action on the entity itself).
7. **Failure consequences** — Counterparty identity in trades and settlement instructions becomes ungrounded; SFTR Article 4 reporting fails; UTI generation (which depends on counterparty LEI in the ESMA waterfall) fails; settlement enrichment cannot resolve `counterparty.lei` (§9.1 lists this as required for `SettlementInstruction`).

### A6. Calendar / Holiday Definitions

1. **Canonical name** — `CalendarRegistry`.
2. **Definition** — Per-jurisdiction / per-financial-centre holiday calendars used by the CDM date adjustment machinery (§10.4.2 references `CalculationPeriodFrequency`, `BusinessDayAdjustments`, `DayCountFractionEnum`). Coupon dates, reset dates, settlement dates, and obligation deadlines are all functions of these calendars.
3. **Minimum field set** — `calendar_id` (e.g. `USNY`, `EUTA`, `JPTO`, `LON`), `holiday_dates` (set of `Date`), `weekend_definition` (Sat-Sun by default but Fri-Sat in MENA), `business_day_convention_supported`, `effective_from`, `version`.
4. **Identity** — `calendar_id`. Composite calendars (e.g. `USNY+LON`, intersection) derive their id from their components.
5. **Provenance** — Vendor (e.g. ICAP, FpML calendar, central bank publications) plus a manual override channel.
6. **Temporal semantics** — Bitemporal. A holiday added retroactively (rare but possible: monarch's funeral, emergency declaration) must not retroactively shift coupon dates that have already paid. The combination of valid-time and knowledge-time is necessary to record "we now know date X is a holiday but at the time we processed the coupon we did not."
7. **Failure consequences** — Coupon and reset dates drift; idempotency keys for scheduled events lose their meaning; the due-event scheduler (§10.7) either misses an event or fires it on the wrong date. Lifecycle replay diverges between historical and current calendars.

### A7. FX Reference Currency Configuration

1. **Canonical name** — `ValuationConfig.ReferenceCurrency` (and the related FX rate-source policy).
2. **Definition** — Designation of the reference currency in which $V_t = \sum w_t(u) P_t(u)$ is denominated (§4.1) and the policy for FX rates used to translate non-reference-currency positions. Multiple parallel reference-currency configurations are supported (USD-base PnL, local-base PnL).
3. **Minimum field set** — `config_id`, `reference_currency` (ISO 4217), `fx_source_policy` (which curves / which observation time), `multi_currency_disclosure` (whether to maintain separate currency-bucket valuations).
4. **Identity** — `config_id`.
5. **Provenance** — Governance committee / accounting policy; rarely changes.
6. **Temporal semantics** — Versioned, append-only. A change to reference currency requires explicit reasoning about what historical PnL means.
7. **Failure consequences** — Multi-currency PnL becomes ambiguous; the path-independence theorem still holds *per currency* but the aggregate is undefined.

### A8. Valuation Tolerance & Quality Policy

1. **Canonical name** — `ValuationPolicy`.
2. **Definition** — Per-instrument-class numeric tolerances and policy parameters governing the FSM (Valuation §2): PnL-explain tolerance per unit, staleness multiplier, retry budgets, model-priority list, prudential-haircut function for STALE/APPROXIMATE prices.
3. **Minimum field set** — `policy_id`, `unit_class`, `pnl_explain_tolerance`, `staleness_threshold_multiplier_of_cadence`, `max_retries`, `model_priority` (primary, secondary, stress — Valuation §3.10), `haircut_curve` (function of staleness).
4. **Identity** — `policy_id`. One policy per instrument class; per-unit overrides are permitted.
5. **Provenance** — Risk / Model-validation governance.
6. **Temporal semantics** — Bitemporal. A historical PnL-explain pass/fail must use the tolerance that applied at the time, not today's tolerance.
7. **Failure consequences** — FSM transitions T5/T6 (Valuation §2.2) are undefined; the FIRM/INDICATIVE/APPROXIMATE/STALE/FAILED quality flag becomes meaningless; PnL explain becomes a permissive rubber stamp or an over-strict blocker.

### A9. Capability / Permission Schema

1. **Canonical name** — `CapabilityRegistry`.
2. **Definition** — The schema for capability-scoped reads (C4) and writes — which subjects (users, services) can read which `(w, u)` overlays, which can submit which event classes, which can mutate which `PositionState` field (C11). §17.2 lists access control as an open problem; nevertheless the schema for it is data the framework requires.
3. **Minimum field set** — `capability_id`, `subject_type`, `subject_id`, `resource_pattern` (e.g. `position_state[w_C, u_QIS]`, `executor.commit(EventClass)`), `permission ∈ {READ, WRITE, EMIT}`, `expires_at`.
4. **Identity** — `capability_id`.
5. **Provenance** — Authorisation administration; cryptographic non-repudiation eventually (§17.2 open problem).
6. **Temporal semantics** — Bitemporal append-only. "Who could read what at time $t$" is auditable.
7. **Failure consequences** — Cross-mandate overlay reads (forbidden by C4) become possible; segregation (§6.3) loses its enforcement; no actor attribution on moves.

### A10. Versioning / Coexistence Policy

1. **Canonical name** — `VersioningPolicy`.
2. **Definition** — The policy that pins versions of CDM, smart contracts, calibration models, market-data snapshots, and reference data at the time of every event (§10.10, §17.2 limitation 9). Events stored in the move stream carry their own version pins; this registry records what each pin means.
3. **Minimum field set** — `pin_id`, `domain ∈ {CDM, SmartContract, Model, RefData, Calendar}`, `version`, `effective_from`, `effective_to`, `migration_function_ref`.
4. **Identity** — `pin_id`.
5. **Provenance** — Engineering release process.
6. **Temporal semantics** — Append-only.
7. **Failure consequences** — Replay determinism (P3) silently broken: same event stream produces different ledger states on different days as upgrades happen behind the scenes.

---

## 2. Reference Data

*"Industry-standard descriptions of instruments, parties, and venues that the Ledger consumes from external authorities."* In the spec this corresponds to Tier 1 of the Unit Store (§3.3.1: "the Ledger does not create reference data; it consumes it"). Reference data is **the boundary** between the Ledger's closed world and the external authoritative world.

### A11. Instrument Master (Tier 1)

1. **Canonical name** — `UnitStore.Tier1`.
2. **Definition** — Per-instrument master record sourced from exchanges, CSDs, and reference-data vendors (§3.3.1). Listed instruments enter the universe at listing, *before* any position is taken — reference data has independent lifecycle from positions.
3. **Minimum field set** — `instrument_id`, `isin`, `cusip`, `sedol`, `figi`, `mic` (exchange MIC), `contract_spec` (for listed derivatives: underlier, strike, expiry, multiplier, settlement currency, settlement type, listing date, last trading date, lot size), `issuer_lei`, `coupon_schedule` (for bonds), `corporate_action_history`, `cfi_code`, `mifir_classification`, `priips_kid_ref`, `vendor_record_id`, `vendor_source`, `as_of`.
4. **Identity** — `(isin)` for securities and bonds; `(exchange_mic, contract_spec_hash)` for listed derivatives; `(contract_address, chain_id)` plus `underlying_isin` for tokenized (§3.2). Note this is the *external* identity; the internal `unit_id` (A2) is derived from it.
5. **Provenance** — Reference-data vendor (Bloomberg, Refinitiv, ICE Data Services), exchange feed, ANNA, GLEIF.
6. **Temporal semantics** — As-of (vendor publishes a snapshot timestamp) and bitemporal at the Ledger boundary (the Ledger records both the vendor's `as_of` and the Ledger's `received_at`). Late corrections from the vendor (a wrong coupon schedule republished) are first-class events, not silent updates.
7. **Failure consequences** — Tier 3 registration is impossible (no contract spec, no ISIN). Settlement projection fails (`SecurityIdentification.ISIN` missing). PRIIPs/MiFID disclosure obligations broken at trade onboarding.

### A12. Lot-Size and Tick-Size Tables

1. **Canonical name** — `MarketMicrostructure.LotTick`.
2. **Definition** — Per-instrument board lot, minimum order size, tick size — needed for physical-delivery lot rounding (§5.4 Q7) and for settlement instruction validity.
3. **Minimum field set** — `instrument_id`, `lot_size`, `tick_size`, `min_order_size`, `effective_from`.
4. **Identity** — `instrument_id` plus `effective_from` (these change occasionally, e.g. tick-size pilot programmes).
5. **Provenance** — Exchange.
6. **Temporal semantics** — As-of.
7. **Failure consequences** — Lot-rounding logic produces invalid quantities; settlement instructions rejected at the CSD.

### A13. CDM Synonym / Mapping Tables

1. **Canonical name** — `CDMSynonyms`.
2. **Definition** — The ISDA-published synonym layer mapping FpML / FIX / ISO 20022 to CDM objects (§10.3). Versioned by CDM release.
3. **Minimum field set** — `synonym_id`, `cdm_version`, `external_format ∈ {FpML, FIX, ISO20022, FRTB-DRR}`, `mapping_rules`, `published_by`, `published_at`.
4. **Identity** — `(synonym_id, cdm_version)`.
5. **Provenance** — FINOS / ISDA distribution.
6. **Temporal semantics** — Append-only versioned. Stored events carry their CDM version pin (A10) and dispatch through the synonym layer that was current at the time.
7. **Failure consequences** — Inbound message ingest fails or, worse, silently mis-maps. Outbound ISO 20022 generation produces malformed or rejected messages.

### A14. Market Microstructure & Trading Schedule Reference

1. **Canonical name** — `VenueSchedule`.
2. **Definition** — Per-venue trading hours, settlement cut-off times, auction windows, holiday calendar binding. Used by the Temporal cron schedules (§10.5.1: "Cron schedule at exchange EOD time") and by the obligation-liveness deadlines.
3. **Minimum field set** — `venue_mic`, `trading_hours_local`, `eod_settlement_time_utc`, `calendar_ref` (A6), `auction_windows`, `effective_from`.
4. **Identity** — `venue_mic`.
5. **Provenance** — Exchange / venue rulebook.
6. **Temporal semantics** — Bitemporal — schedule changes (DST, market-hours adjustments) must be queryable as-of historical $t$.
7. **Failure consequences** — Daily settlement workflow (§10.5.1) fires at the wrong UTC time; futures variation margin is computed on stale prices; obligation deadlines drift.

### A15. CSD / Settlement-System Reference

1. **Canonical name** — `SettlementInfrastructureRegistry`.
2. **Definition** — Per-CSD identity, participant id, settlement mechanism (DvP model 1/2/3), supported message types. Used by the settlement layer and for SettlementInstruction enrichment (§9.2).
3. **Minimum field set** — `csd_id`, `name`, `country`, `dvp_model`, `supported_iso_messages` (sese.023, sese.025, pacs.008/009, camt.054, …), `cut_off_times`, `our_participant_id`.
4. **Identity** — `csd_id`.
5. **Provenance** — Industry registries; manual onboarding.
6. **Temporal semantics** — As-of.
7. **Failure consequences** — `SettlementInstruction` cannot be routed; confirmation messages cannot be parsed.

### A16. Regulatory Reporting Field Schema

1. **Canonical name** — `RegReportingSchema`.
2. **Definition** — The schema and validation rules for SFTR (ESMA), EMIR, MiFIR/MiFID II RTS 25, SEC SLATE (§14.10), CSDR, Reg SHO. Tells the Ledger which fields each report needs and where they come from.
3. **Minimum field set** — `regime`, `version`, `effective_from`, `field_definitions`, `validation_predicates`, `submission_endpoint_ref`.
4. **Identity** — `(regime, version)`.
5. **Provenance** — Regulator / trade repository publications.
6. **Temporal semantics** — Bitemporal versioned.
7. **Failure consequences** — Regulatory submissions fail validation or, worse, silently misreport. F5 (StatesHome risk register) is the explicit acknowledgement that mandate-as-unit creates new SFTR/EMIR surface that must be schema-mapped.

### A17. ISIN / LEI / UTI Allocation Authority Bindings

1. **Canonical name** — `IdentifierAuthorityBindings`.
2. **Definition** — How the Ledger obtains and verifies external identifiers: ISIN allocation (NNA), LEI allocation (LOU), UTI generation per the ESMA waterfall (§14.10), CFI codes.
3. **Minimum field set** — `identifier_type`, `authority_ref`, `lookup_endpoint`, `our_credentials_ref`.
4. **Identity** — `identifier_type`.
5. **Provenance** — Authority registries.
6. **Temporal semantics** — As-of.
7. **Failure consequences** — UTI cannot be generated → SFTR NEWT report cannot be filed → loan operationally exists but is regulatorily invisible.

---

## 3. Market Data

*"Quantities directly observed in the market; the inputs to pricing."* I include both raw observables (prices, rates, volatilities as quoted) and curated/calibrated products (yield curves, vol surfaces, hazard curves) — the user's "Market data" category covers both, but Pass B will distinguish them.

### A18. Price Tick / Quote (Raw Observable)

1. **Canonical name** — `RawQuote`.
2. **Definition** — A single observation of a market price: trade print, top-of-book bid/ask, mid, last settlement, dealer indicative. The atomic unit of market input. *Categorically: an element of the input space of the Kalman filter (Valuation §4.3).*
3. **Minimum field set** — `quote_id`, `instrument_id` (or `observable_id`), `quote_type ∈ {TRADE, BID, ASK, MID, MARK, SETTLE, INDICATIVE}`, `price`, `quantity` (where applicable), `timestamp_venue`, `timestamp_received`, `venue_mic`, `feed_source`, `sequence_number_at_source`.
4. **Identity** — `(feed_source, sequence_number_at_source)` — globally unique within the source. The Ledger's internal `quote_id` is derived but the feed pair is canonical.
5. **Provenance** — Market-data feed (Refinitiv, Bloomberg, exchange direct, dealer quote).
6. **Temporal semantics** — Append-only with two timestamps: `timestamp_venue` (economic time) and `timestamp_received` (knowledge time). The two are independently load-bearing — late ticks must not silently rewrite history (§9.4 fault-tolerance: late events get both timestamps).
7. **Failure consequences** — Pricing FSM cannot transition `Unpriced → Pricing` (T1 guard); Kalman filter starves; PnL explain lacks the market-move inputs (`market_moves` argument, Valuation §7.2).

### A19. Calibrated Curve / Surface

1. **Canonical name** — `CalibratedMarketObject`.
2. **Definition** — The Kalman-filter posterior at observation epoch $t$: yield curve (zero rates at tenors), vol surface (kernel coefficients $\beta = (\sigma_0, s_0, c_1, \ldots)$), credit hazard curve, FX vol surface, correlation matrix. The certified posterior $x_{t|t}^{\text{cert}}$ — only the certified version is consumed downstream.
3. **Minimum field set** — `calibration_id`, `target_object` (e.g. `USD_OIS_curve`, `SPX_vol_surface`), `as_of_timestamp`, `state_vector` $x_{t|t}$, `covariance_matrix` $P_{t|t}$, `model_id` (which Kalman model produced it), `process_noise_Q_ref`, `observation_noise_R_summary`, `inputs_used` (set of `quote_id` from A18), `mahalanobis_d2`, `chi2_threshold_pass` (boolean), `arbitrage_certification_status`, `weighted_rmse`, `certified` (boolean: true only if all gates pass).
4. **Identity** — `(target_object, as_of_timestamp, model_id)`.
5. **Provenance** — Kalman filter activity (Valuation §4); the input set links back to A18.
6. **Temporal semantics** — Append-only per epoch; the *latest certified* per `target_object` is the live curve, but historical epochs are preserved for time travel and PnL-explain reconstruction.
7. **Failure consequences** — Pricing DAG nodes that depend on this calibration stall in `Pricing`; structured products and exotics cannot be priced; PnL-explain $J \cdot \Delta\Theta$ term (Valuation §3.5) cannot be computed.

### A20. Reference Rate Fixings

1. **Canonical name** — `RateFixing`.
2. **Definition** — Authoritative published fixings of reference rates: SOFR, EURIBOR, SONIA, TONA, FX fixings (WMR, ECB), commodity reference prices. Used by IRS resets (§10.5.4), FX forwards, and floating-rate bonds.
3. **Minimum field set** — `rate_id` (e.g. `USD-SOFR`), `fixing_date`, `value`, `publication_timestamp`, `publisher_id`, `methodology_version`.
4. **Identity** — `(rate_id, fixing_date)`.
5. **Provenance** — Rate administrator (NY Fed for SOFR, EMMI for EURIBOR, Bank of England for SONIA, ECB for ECB FX).
6. **Temporal semantics** — As-of with restatement support: rate administrators occasionally republish corrected fixings; the Ledger must record both original and corrected values with the correction's effective date (bitemporal).
7. **Failure consequences** — Swap reset (§10.5.4) fires with a guess or stalls; CSA margin (which uses overnight rates for compounding) becomes wrong; SOFR-linked products de-anchor.

### A21. Settlement / Closing Price (Official)

1. **Canonical name** — `OfficialClosingPrice`.
2. **Definition** — The exchange-published official settlement price used for variation margin (futures) and end-of-day mark (equities, options). Distinct from raw quotes (A18) — this is a *single, authoritative, named* number.
3. **Minimum field set** — `instrument_id`, `trade_date`, `settlement_price`, `publication_timestamp`, `exchange_mic`, `methodology_version`.
4. **Identity** — `(instrument_id, trade_date, exchange_mic)`.
5. **Provenance** — Exchange.
6. **Temporal semantics** — As-of; restatements rare but supported.
7. **Failure consequences** — Futures daily settlement (§7.5) cannot fire; the variation margin equation $\text{VM} = \text{accumulated\_cost} - (-\text{net\_qty} \times P_{\text{settle}} \times \text{mult})$ is undefined.

### A22. Index Level (Benchmark / Strategy Index Source)

1. **Canonical name** — `IndexLevel`.
2. **Definition** — Daily (or higher-frequency) published index levels: SPX, SX5E, custom strategy indices, QIS reference indices, benchmark NAV indices. Distinguished from A18 because indices are *derived* (computed by an index administrator from constituents) and from A19 because they are *published* (not calibrated by us).
3. **Minimum field set** — `index_id`, `level_type ∈ {OPEN, CLOSE, INTRADAY}`, `value`, `as_of`, `publisher_id`, `methodology_ref`.
4. **Identity** — `(index_id, level_type, as_of)`.
5. **Provenance** — Index administrator (S&P, MSCI, FTSE, ICE BofA, internal strategy index administrator).
6. **Temporal semantics** — As-of with restatement.
7. **Failure consequences** — Benchmark NAV at QIS/MA inception cannot be set (StatesHome §3.3 places this in `PositionState[w_C, u_MA]`); QIS strategy `nav_index` (`UnitStatus`) cannot be updated; performance attribution diverges from official benchmark.

### A23. Corporate-Action Announcement

1. **Canonical name** — `CorporateActionAnnouncement`.
2. **Definition** — Formal announcement of a corporate action (dividend, split, merger, spin-off, rights issue, name change, ISIN change) with announcement / record / ex / payment / effective dates and ratios.
3. **Minimum field set** — `ca_id`, `affected_isin`, `ca_type`, `announcement_date`, `record_date`, `ex_date`, `pay_date`, `effective_date`, `ratio_or_amount`, `optional_election_window`, `tax_treatment_hint`, `publisher_id`.
4. **Identity** — `ca_id` (issuer-published) plus internal mapping.
5. **Provenance** — Issuer (via SWIFT MT564 / 566 / 568, vendor announcements, exchange notices).
6. **Temporal semantics** — Bitemporal append-only. Late amendments to an announced corporate action are common (ratio adjustments) and must not silently rewrite already-processed positions.
7. **Failure consequences** — Time-travel challenge (3) (§7.7) — the system cannot explain the share-count jump from 100 to 200 across a split. The corporate-action workflow (§10.5.5) cannot fan out.

### A24. Volatility Quote / Implied Vol Observation

1. **Canonical name** — `VolQuote`. (A subspecies of A18 elevated for clarity because it is the dominant input for Kalman calibration of vol surfaces.)
2. **Definition** — Observation of an implied volatility, typically as bid/ask/mid for an option at a given strike-expiry, or as an ATM vol or risk-reversal/butterfly construct.
3. **Minimum field set** — As A18 plus `strike`, `expiry`, `option_type`, `quote_in_vol_units` (true for OTC FX vol; false for listed option price).
4. **Identity** — As A18.
5. **Provenance** — Inter-dealer brokers, vendor consensus, exchange option markets.
6. **Temporal semantics** — As A18.
7. **Failure consequences** — Vol surface calibration (A19) starves; vega and Jacobian computations stale; PnL-explain residual blows up.

### A25. Market-Data Snapshot

1. **Canonical name** — `MarketDataSnapshot`.
2. **Definition** — A *consistent cut* across all market-data inputs at a designated valuation point: all leaf-node values used for one full DAG repricing cycle. The reproducibility primitive (§17.2 limitation 9: "time travel and replay produce identical results only when the same versions of market data snapshots, reference data, and pricing model parameters are used").
3. **Minimum field set** — `snapshot_id`, `as_of_timestamp`, `composition` (list of `(observable_id, quote_id_or_calibration_id)`), `purpose ∈ {OFFICIAL_EOD, INTRADAY_RISK, REGULATORY, AD_HOC}`.
4. **Identity** — `snapshot_id`. The composition is content-addressable: same set of pinned inputs ⇒ same snapshot.
5. **Provenance** — Snapshot service that listens to A18/A19 streams.
6. **Temporal semantics** — Append-only.
7. **Failure consequences** — Replay non-determinism: same event log produces different valuations because intermediate snapshots disagree.

---

## 4. Oracle Data

The brief lists Oracle as a separate floor category. The spec treats *every* external authority as an oracle: §10.2 ("Mapping Layer as Oracle Interface"), the settlement-confirmation return path (§9.7), the Kalman observation model (Valuation §4.3). I read "Oracle data" as **inbound external attestations that drive Ledger state transitions but are not market data**: confirmations, eligibility certifications, regulatory acknowledgements, custody attestations, KYC attestations.

### A26. Settlement Confirmation Inbound Message

1. **Canonical name** — `SettlementConfirmation`.
2. **Definition** — Inbound ISO 20022 message (`sese.025` for securities, `camt.054` for cash) confirming that a previously instructed settlement has occurred or failed (§9.7). The state-transition oracle for `EXECUTED → INSTRUCTED → SETTLED|FAILED`.
3. **Minimum field set** — `confirmation_id`, `corresponds_to_instruction_id`, `external_reference`, `confirmation_status ∈ {SETTLED, PARTIALLY_SETTLED, FAILED, REJECTED}`, `failure_reason_code` (if applicable), `actual_settled_quantity`, `actual_settled_amount`, `csd_timestamp`, `received_at`, `raw_message`.
4. **Identity** — `confirmation_id`. Linked back to instruction by `corresponds_to_instruction_id` (which equals the original `tx_id` per §9.1).
5. **Provenance** — CSD / payment system; the `received_at` knowledge-time is recorded by the Ledger gateway.
6. **Temporal semantics** — Append-only, bitemporal (CSD timestamp vs received timestamp).
7. **Failure consequences** — Settlement status lifecycle stalls; trades remain perpetually `INSTRUCTED`; reconciliation against custodian breaks accumulate.

### A27. Custodian / Depot Attestation

1. **Canonical name** — `CustodianAttestation`.
2. **Definition** — Periodic attestation from custodians of held positions: depot statements, EU equivalent of "stock record". Used for §15.10's external reconciliation: $\text{avail}(L,u) + \text{onloan} + \text{inflight} \stackrel{?}{=} \text{Custodian depot}(u)$.
3. **Minimum field set** — `attestation_id`, `custodian_entity_id`, `account_id`, `as_of_timestamp`, `position_lines` (list of `{instrument_id, quantity}`), `valuation_lines` (optional), `received_at`.
4. **Identity** — `(custodian_entity_id, account_id, as_of_timestamp)`.
5. **Provenance** — Custodian (via `semt.002` / `semt.003` reports, file feeds, or proprietary formats normalised at the gateway).
6. **Temporal semantics** — As-of (custodian's view) plus knowledge time (when received).
7. **Failure consequences** — External reconciliation cannot run; virtual-wallet drift goes undetected; CSDR penalty attribution fails.

### A28. Counterparty Confirmation (Trade-Level)

1. **Canonical name** — `TradeConfirmation`.
2. **Definition** — Inbound trade confirmation from a counterparty (e.g. via DTCC MarkitWire, Acadia, CTM): the counterparty's record of the trade terms, used for matching.
3. **Minimum field set** — `confirmation_id`, `counterparty_lei`, `counterparty_internal_ref`, `our_internal_ref`, `cdm_trade_payload`, `match_status ∈ {PROPOSED, MATCHED, ALLEGED, REJECTED, AMENDED}`, `received_at`.
4. **Identity** — `confirmation_id`.
5. **Provenance** — Counterparty confirmation platform.
6. **Temporal semantics** — Append-only with state transitions in match status.
7. **Failure consequences** — Bilateral OTC trades cannot become economically active; the unit is registered (Tier 3) but the counterparty disagrees and SFTR / EMIR matching fails.

### A29. Locate Confirmation

1. **Canonical name** — `LocateConfirmation`.
2. **Definition** — Pre-trade attestation from a lender that securities are available for borrow (§15.7). EU SSR Art 12(1)(c) and US Reg SHO Rule 203(b)(1) requirement. Distinct from a borrow because no shares move; distinct from a market-data quote because it is a *commitment*.
3. **Minimum field set** — `locate_id`, `requesting_short_seller_entity_id`, `lender_entity_id`, `instrument_id`, `quantity`, `requested_at`, `confirmed_at`, `expires_at`, `status ∈ {REQUESTED, CONFIRMED, EXPIRED, CONVERTED, DECLINED}`, `confirmation_method ∈ {EASY_TO_BORROW_LIST, HARD_TO_BORROW_QUOTE, MANUAL}`.
4. **Identity** — `locate_id`.
5. **Provenance** — Lender / locate-provider system.
6. **Temporal semantics** — Bitemporal append-only with TTL. §15.7 mandates 5-year retention (ESMA 70-448-10).
7. **Failure consequences** — P14 (Locate-Before-Short) cannot be enforced; short sales rejected by the executor; or worse, allowed without locate, exposing the firm to regulatory penalties.

### A30. Margin Call / Collateral Demand Inbound

1. **Canonical name** — `CollateralCall`.
2. **Definition** — Inbound margin call from a counterparty under a CSA, GMSLA, GMRA, or CCP rules; or a triparty agent's RQV instruction (§15.5 IBP-189). The oracle for "collateral substitution demand" obligation events.
3. **Minimum field set** — `call_id`, `counterparty_entity_id`, `csa_or_master_agreement_ref`, `call_type ∈ {VM, IM, INDEPENDENT_AMOUNT, RQV, SUBSTITUTION_DEMAND}`, `direction ∈ {DELIVER, RECEIVE}`, `amount`, `eligible_collateral_filter`, `value_date`, `deadline`, `received_at`.
4. **Identity** — `call_id`.
5. **Provenance** — Counterparty / triparty agent.
6. **Temporal semantics** — Bitemporal append-only with deadline enforcement.
7. **Failure consequences** — Collateral obligation cannot be created; obligation-liveness invariant P21 fails; CSA segregation breaks; close-out netting paths bypassed.

### A31. Regulatory Acknowledgement / Rejection

1. **Canonical name** — `RegulatoryAck`.
2. **Definition** — Inbound acknowledgement from a Trade Repository (DTCC GTR, REGIS-TR, KDPW), regulator, or FINRA SLATE submission gateway: "your report was accepted / rejected / requires resubmission."
3. **Minimum field set** — `ack_id`, `corresponds_to_report_id`, `regime`, `status ∈ {ACK, NACK, PENDING_REPLY}`, `error_codes`, `received_at`.
4. **Identity** — `ack_id`.
5. **Provenance** — Trade repository / regulator.
6. **Temporal semantics** — Append-only.
7. **Failure consequences** — Regulatory submission status is unknown; the firm believes a report has filed when it has been silently rejected.

### A32. KYC / AML / Sanctions Attestation

1. **Canonical name** — `KYCAttestation`.
2. **Definition** — Periodic refresh of the KYC, AML, and sanctions status of an entity (A5) from an internal compliance team or external screening provider.
3. **Minimum field set** — `attestation_id`, `entity_id`, `kyc_level`, `aml_risk_rating`, `sanctions_match_status`, `screening_source`, `attested_at`, `valid_until`.
4. **Identity** — `attestation_id`.
5. **Provenance** — Compliance.
6. **Temporal semantics** — Append-only with explicit expiry.
7. **Failure consequences** — A real wallet's controlling entity is no longer KYC-current; trades emitted into that wallet should be gated but cannot be.

### A33. Eligibility Schedule Attestation

1. **Canonical name** — `EligibilitySchedule`.
2. **Definition** — Triparty agent or CSA-defined schedule of which collateral types are eligible, with concentration limits, haircuts, and ratings cut-offs. Periodically attested by the agent.
3. **Minimum field set** — `schedule_id`, `csa_or_master_agreement_ref`, `eligible_units` (set of unit-type predicates), `haircut_table`, `concentration_limits`, `effective_from`, `attested_by_entity_id`.
4. **Identity** — `schedule_id`.
5. **Provenance** — Triparty agent / CSA negotiator.
6. **Temporal semantics** — Bitemporal append-only.
7. **Failure consequences** — Collateral substitution generates ineligible posts; margin sufficiency invariant P13 is structurally broken.

### A34. Vendor Reference-Data Attestation Receipt

1. **Canonical name** — `RefDataVendorAttestation`.
2. **Definition** — The "vendor said this on this day" record paired to every Tier-1 reference datum (A11–A17). Conflates with provenance but is a first-class datum because audit needs to point to the precise vendor message that justified an internal field value.
3. **Minimum field set** — `attestation_id`, `vendor_entity_id`, `target_record_id`, `vendor_message_hash`, `vendor_published_at`, `received_at`.
4. **Identity** — `attestation_id`.
5. **Provenance** — Reference-data vendor feed.
6. **Temporal semantics** — Append-only.
7. **Failure consequences** — Cannot defend a position to an auditor: "we marked this bond at 92.50 because Bloomberg said the coupon was 4% on 2026-03-12" requires the attestation pointer to be retrievable.

---

## 5. Smart-Contract Execution Data

*"Data produced by the Ledger's own machinery as smart contracts execute and the move stream advances."* This is the heart of the spec. Pass A treats it concretely; Pass B will reorganise it.

### A35. Move Stream

1. **Canonical name** — `MoveStream`.
2. **Definition** — The append-only log of every atomic move (§2.3 Definition). The canonical internal record. The single source of truth from which all balances are projected (§8.1).
3. **Minimum field set** — Per move: `move_id`, `from_wallet_id`, `to_wallet_id`, `unit_id`, `quantity`, `coordinate` (`own | onloan | borr | coll_post | coll_recv | coll_rehyp | scalar` per §15), `economic_timestamp`, `booking_timestamp`, `transaction_id` (link to A36), `source_contract_ref` (`(contract_id, contract_version)` from A4), `cdm_event_payload` (full CDM `BusinessEvent`), `metadata` (event description, external references, ISO 20022 ids), `prev_hash` (hash chaining per §8.4 invariant 4), `corrects_tx_id` (optional, for compensating transactions per §8.4).
4. **Identity** — `move_id`. The pair `(transaction_id, sequence_within_tx)` is also a useful natural key.
5. **Provenance** — Smart-contract execution via the executor; corrections; oracle-driven lifecycle events. Every move records its `source_contract_ref` and (eventually) its `actor_id`.
6. **Temporal semantics** — **Append-only with bitemporal timestamps.** Both `economic_timestamp` and `booking_timestamp` are load-bearing (§8.4: late events). Replay is a fold over this stream — this is the canonical structural property.
7. **Failure consequences** — Loss of any move breaks all downstream projections. Mutation of a past move breaks tamper-evidence (P4). Loss of `source_contract_ref` or `cdm_event_payload` breaks audit; balance still computable but business meaning gone.

### A36. Transaction Stream

1. **Canonical name** — `TransactionStream`.
2. **Definition** — The list of transactions (§2.4 Definition); each transaction is a finite collection of moves that share a timestamp and commit atomically. The container for conservation: $\sum_w \Delta w(u) = 0$ holds *per transaction per unit*.
3. **Minimum field set** — `transaction_id`, `transaction_type ∈ {SETTLEMENT, COLLATERAL, LIFECYCLE, ACCOUNTING, CORRECTION}`, `economic_timestamp`, `booking_timestamp`, `committed_at`, `move_ids` (ordered list), `cdm_business_event_ref`, `idempotency_token`, `originating_workflow_id` (Temporal workflow run id), `actor_id` (who/what authorised this), `parent_correction_tx_id` (optional).
4. **Identity** — `transaction_id`. Used as the executor's idempotency key (Invariant 5).
5. **Provenance** — Smart-contract execution. The atomic commit boundary (§8.2 Algorithm).
6. **Temporal semantics** — Append-only, bitemporal.
7. **Failure consequences** — Atomic-commitment invariant (P2) loses its scope; partial commits become possible; replay grouping is broken.

### A37. State Delta (Atomic Across Three Maps)

1. **Canonical name** — `StateDelta` (StatesHome §1, C3).
2. **Definition** — The atomic change unit that updates `ProductTerms`, `UnitStatus`, and `PositionState` simultaneously per event (StatesHome C3: "Partial application rejected"). The structurally indivisible thing that passes through the executor.
3. **Minimum field set** — `delta_id`, `transaction_id`, `product_terms_changes` (typically empty except on amendment events), `unit_status_changes` (per affected `unit_id`), `position_state_changes` (per affected `(wallet_id, unit_id)`), `field_writer_assertions` (each field tagged with the handler that mutated it, per C11).
4. **Identity** — `delta_id` (1-to-1 with `transaction_id` in practice, but kept distinct so multi-delta transactions remain expressible).
5. **Provenance** — Lifecycle function output; consumed by executor.
6. **Temporal semantics** — Append-only.
7. **Failure consequences** — C3 violated; the three-map model loses its atomicity and consistency contract; per-class structural zero-sum proof obligations become unverifiable.

### A38. Unit Status (Mutable Shared) — Live Snapshot

1. **Canonical name** — `UnitStatus` (StatesHome §1).
2. **Definition** — The current value of `lifecycle_stage`, `last_settlement_price`, `current_weights`, `nav_index`, `triggered_barrier`, `superseded_by` per registered unit. Total on registered units (C5). Logically a projection of the move stream, but materialised because read patterns demand it.
3. **Minimum field set** — Listed under A2 (this is the *live snapshot* whereas A2 is the *registry function* — same datum, different consumer).
4. **Identity** — `unit_id`.
5. **Provenance** — Initialised at registration with product-declared defaults; updated by handler `StateDelta`s.
6. **Temporal semantics** — Mutable but with a logged history reconstructable from the move stream. Bitemporal queries supported via clone_at($t$).
7. **Failure consequences** — Lifecycle-state-dependent pricing (Valuation §13.2: $P_t(u) = P(u, \text{state}_t(u), \text{market\_data}_t)$) becomes wrong; idempotency check (P5) breaks.

### A39. Position State (Per (Wallet, Unit))

1. **Canonical name** — `PositionState` (StatesHome §1).
2. **Definition** — The per-position carrier `Map[(WalletId, UnitId), PositionState]`. Two orthogonal disciplines (StatesHome C1): *Option accessor* (None means "never held") and *monotone carrier* (rows never garbage-collected; closed-out positions leave a `Some(zero)` ghost row).
3. **Minimum field set** —
   - The six coordinates from §15.2: `own`, `onloan`, `borr`, `coll_post`, `coll_recv`, `coll_rehyp`. (For non-lendable units these collapse to `own` only.)
   - Position-level economic accumulators: `accumulated_cost` (futures), `entry_nav`, `hwm`, `hwm_date` (mandate / QIS), `accrued_mgmt_fee`, `accrued_perf_fee`, `mandate_breach_flags`, `benchmark_nav_at_inception`, `ccp_binding`, `subscription_redemption_cursor`.
   - Per-handler-mutation tag (C11) — each field carries the unique writer.
   - `first_seen_at`, `last_modified_at`, `last_modifying_tx_id`.
4. **Identity** — `(wallet_id, unit_id)`.
5. **Provenance** — Created by handler `StateDelta`s on the first event touching the pair; updated atomically thereafter.
6. **Temporal semantics** — Mutable carrier, monotone (row never deleted). Bitemporally reconstructable: `clone_at(t)` produces the projection at $t$.
7. **Failure consequences** — Conservation per event class (C2) cannot be verified; portfolio valuation $V = \sum w_t(u) P_t(u)$ is wrong; tax-lot / wash-sale reconstruction (an open problem, §17.2) is impossible.

### A40. Lifecycle Event Log (CDM `BusinessEvent` Stream)

1. **Canonical name** — `LifecycleEventLog`.
2. **Definition** — The stream of CDM `BusinessEvent`s that drove ledger transactions. Stored in full inside the move's `cdm_event_payload` but also queryable as its own stream for business / regulatory / replay use.
3. **Minimum field set** — `event_id`, `cdm_version` (A10), `cdm_event_type`, `cdm_event_intent`, `before_trade_state_ref`, `after_trade_state_ref`, `lineage_predecessors`, `effective_date`, `business_day_adjustments_applied`, `produced_transaction_id`.
4. **Identity** — `event_id`.
5. **Provenance** — Either external (synonym-mapped from FpML / FIX / ISO 20022) or internal (lifecycle function output).
6. **Temporal semantics** — Append-only. Bitemporal at the event/booking boundary.
7. **Failure consequences** — Audit cannot answer "why"; regulatory submissions lose business-meaning context; the forgetful functor F (§10.4) cannot be inverted because the discarded business intent is no longer accessible.

### A41. Settlement Status Lifecycle Per Transaction

1. **Canonical name** — `SettlementStatusLog`.
2. **Definition** — Per-transaction lifecycle in `EXECUTED → INSTRUCTED → SETTLED|FAILED` (§9.7). One status row per state transition.
3. **Minimum field set** — `status_log_id`, `transaction_id`, `previous_status`, `new_status`, `transition_at`, `external_reference` (CSD instruction ref), `reason_code` (for FAILED).
4. **Identity** — `status_log_id`.
5. **Provenance** — Settlement workflow + inbound confirmations (A26).
6. **Temporal semantics** — Append-only.
7. **Failure consequences** — Settlement state cannot be reasoned about; FAILED trades not flagged for buy-in; CSDR penalty attribution wrong.

### A42. Workflow History (Temporal)

1. **Canonical name** — `WorkflowHistory` (Temporal's append-only event history per workflow).
2. **Definition** — The complementary audit trail (§10.3): records orchestration decisions, signal deliveries, timer fires, activity invocations and retries, ContinueAsNew transitions. Distinct from the move stream — orchestration vs economics.
3. **Minimum field set** — `workflow_id`, `run_id`, `event_history` (Temporal's native event format: `WorkflowExecutionStarted`, `ActivityTaskScheduled`, `ActivityTaskCompleted`, `TimerFired`, `WorkflowExecutionSignaled`, …), `worker_identity`, `task_queue`.
4. **Identity** — `(workflow_id, run_id)`.
5. **Provenance** — Temporal cluster.
6. **Temporal semantics** — Append-only by Temporal's own design.
7. **Failure consequences** — Operational forensics blind: "why did this margin call fire / not fire" becomes unanswerable. Liveness investigation impossible (§10.7).

### A43. Idempotency Token Set

1. **Canonical name** — `IdempotencyTokens`.
2. **Definition** — The set of `idempotency_token`s already processed per workflow / per signal channel. Used by the workflow `processed.add(token); if token in processed: return` pattern (§10.5.5, §10.6).
3. **Minimum field set** — `(workflow_id, signal_channel, token, first_seen_at)`.
4. **Identity** — `(workflow_id, signal_channel, token)`.
5. **Provenance** — Workflow execution.
6. **Temporal semantics** — Append-only with optional eviction beyond a retention horizon.
7. **Failure consequences** — Duplicate signal handling: a recall fires twice, a margin call posts double collateral, a coupon pays twice.

### A44. Snapshot / Checkpoint

1. **Canonical name** — `BalanceSnapshot`.
2. **Definition** — Materialised projection of wallet balances and `UnitStatus` / `PositionState` at a designated $t$, used to make balance queries $O(k)$ where $k$ is moves since the last snapshot (§8.4).
3. **Minimum field set** — `snapshot_id`, `as_of_tx_id` (the watermark transaction), `as_of_timestamp`, `balances`, `unit_status_projection`, `position_state_projection`, `mvcc_cursor`.
4. **Identity** — `snapshot_id`.
5. **Provenance** — Snapshot service.
6. **Temporal semantics** — Append-only; never authoritative — a derived cache.
7. **Failure consequences** — Performance: balance queries become $O(n)$. Correctness only fails if a snapshot is treated as authoritative when the move stream and snapshot disagree; conservation says the move stream wins.

### A45. Obligation Object (First-Class)

1. **Canonical name** — `Obligation` (§14.7 obligation-liveness).
2. **Definition** — A first-class object representing a contractually-required *future event* with a deadline: a margin delivery deadline, a recall response deadline, a substitution deadline, a buy-in deadline, an SFTR submission deadline, a stale-price escalation deadline (Valuation §6.6). The unit on which liveness invariants P21–P23 operate.
3. **Minimum field set** — `obligation_id`, `obligation_type`, `obligor_wallet_id`, `obligee_wallet_id`, `triggering_event_id`, `deadline`, `discharge_event_id` (filled when satisfied), `compensation_workflow_ref` (what fires on breach), `status ∈ {OPEN, DISCHARGED, BREACHED, COMPENSATED}`, `created_at`, `closed_at`.
4. **Identity** — `obligation_id`.
5. **Provenance** — Created by handlers that emit obligations (loan initiation creates margin-delivery obligations, etc.); discharged by satisfying transactions; breached by deadline expiry.
6. **Temporal semantics** — Append-only with monotone status transitions.
7. **Failure consequences** — Liveness gap (the open problem of §17.2 "Liveness guarantees" in v10.0, resolved in v10.3): contractually-required events fail silently; margin not delivered → no error.

### A46. Valuation Record

1. **Canonical name** — `ValuationRecord` (Valuation §3).
2. **Definition** — The full output of one pricing cycle for one unit: `(dirty_price, clean_price, accrued, greeks, model_id, market_data_snap, compute_ms, quality, fsm_state)`. The scalar `dirty_price` IS the $P_t(u)$ of the path-independence theorem; the rest is metadata that risk and PnL-explain consume.
3. **Minimum field set** — `valuation_record_id`, `unit_id`, `as_of_timestamp`, `model_id` (links to A47), `market_data_snapshot_id` (A25), `dirty_price`, `clean_price`, `accrued`, `greeks` (model-tagged union: BS / Heston / SABR / LocalVol / IRS / Bond / Cash / KernelVol — Valuation §3.10), `compute_ms`, `quality ∈ {FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED}`, `fsm_state` (Valuation §2 states), `pnl_explain_residual` (when state is `Explained` or `Quarantined`), `published_at`.
4. **Identity** — `(unit_id, as_of_timestamp, model_id)`.
5. **Provenance** — `PricingWorkflow` activity (Valuation §6).
6. **Temporal semantics** — Append-only per (unit, timestamp, model).
7. **Failure consequences** — PnL attribution impossible; risk pipeline blind; intraday TRS settlements (§6.7) wrong; CSA aggregate MTM wrong.

### A47. Pricing Model Specification

1. **Canonical name** — `PricingModelSpec`.
2. **Definition** — Per-model (BS, Heston, SABR, local-vol, kernel-vol, etc.) specification of: observables consumed, parameters $\Theta$, price function reference, sensitivity / Greek computation method (analytical / bump / AAD / pathwise), per-model arbitrage constraint set $\Theta_{AF}$ (Valuation §4.6).
3. **Minimum field set** — `model_id`, `model_class`, `parameter_schema`, `observable_schema`, `code_artifact_ref`, `version`, `validation_doc_ref`, `default_method`, `arbitrage_constraint_ref`.
4. **Identity** — `(model_id, version)`.
5. **Provenance** — Model validation / model risk team.
6. **Temporal semantics** — Append-only versioned.
7. **Failure consequences** — Replay determinism broken at the pricer layer: same `MarketDataSnapshot` produces different prices because model code drifted.

### A48. Pricing DAG Topology

1. **Canonical name** — `PricingDAGTopology`.
2. **Definition** — Per-cycle, frozen DAG of pricing dependencies (Valuation §5.1): unit nodes, market-data leaf nodes, calibration nodes, and edges. The data structure that the workflow signalling layer (Valuation §6.3) traverses.
3. **Minimum field set** — `dag_id`, `as_of_cycle_id`, `nodes`, `edges`, `topological_order`, `acyclicity_certificate`.
4. **Identity** — `(dag_id, as_of_cycle_id)`.
5. **Provenance** — Built from `UnitStore` + `PricingModelSpec` at the start of each cycle.
6. **Temporal semantics** — Per-cycle frozen; mid-cycle mutations apply on the next cycle.
7. **Failure consequences** — Cycles in dependencies cause infinite loops; missing edges cause stale-input pricing; pricing-FSM `T1 guard` ("all upstream nodes have a FIRM price") fails.

### A49. PnL Explain Result

1. **Canonical name** — `PnLExplainResult`.
2. **Definition** — Per-unit, per-period output of the explain function (Valuation §7): total PnL, attributed PnL ($\delta \cdot \Delta S + J \cdot \Delta\Theta + \tfrac{1}{2}\Gamma(\Delta S)^2 + \theta \Delta t + \text{cashflows}$), unexplained residual, pass/fail vs tolerance, FSM transition triggered.
3. **Minimum field set** — `explain_id`, `unit_id`, `from_valuation_record_id`, `to_valuation_record_id`, `total_pnl`, `attribution` (component map), `unexplained`, `tolerance_at_check`, `status ∈ {PASS, FAIL}`, `fsm_transition` (T5 or T6), `produced_at`.
4. **Identity** — `explain_id`.
5. **Provenance** — `PnLExplain` activity.
6. **Temporal semantics** — Append-only.
7. **Failure consequences** — PnL-explain gate (the verification step before publishing as FIRM) cannot fire; no quality assurance on prices; toxic-product diagnosis (Valuation §3.10) blind.

### A50. Compensation / Correction Linkage

1. **Canonical name** — `CorrectionLink`.
2. **Definition** — The first-class metadata linking each compensating transaction to the original transaction it corrects (§8.4: "The compensating transaction must reference the original transaction identifier via a `corrects` field in its metadata, creating an explicit correction chain"). The data needed by a future formal correction algebra (open problem §17.2).
3. **Minimum field set** — `link_id`, `original_tx_id`, `correcting_tx_id`, `correction_kind ∈ {CANCEL, AMEND, RESTATE}`, `reason`, `created_at`, `created_by_actor_id`.
4. **Identity** — `link_id`.
5. **Provenance** — Correction workflow.
6. **Temporal semantics** — Append-only.
7. **Failure consequences** — Auditor cannot distinguish economic events from error corrections; compensating chains become indistinguishable from independent activity; reconstructing "what we believed at $t$" loses fidelity.

### A51. Locate Live State

1. **Canonical name** — `LocateState`.
2. **Definition** — Live state of every unexpired locate: which lender confirmed how many shares to which short seller, with TTL countdown and conversion / expiry status. Distinguished from A29 (the inbound confirmation event) — this is the *live aggregate* used for over-location prevention (§15.7).
3. **Minimum field set** — `locate_id`, `aggregated_outstanding_per_(lender,instrument)`, `ttl_remaining`.
4. **Identity** — `locate_id`.
5. **Provenance** — Materialised from A29 + executor decrements at conversion / expiry.
6. **Temporal semantics** — Mutable but reconstructable; effectively bitemporal via the underlying log.
7. **Failure consequences** — Over-location possible: more shares pre-committed than the lender owns.

### A52. Fee Accrual Log

1. **Canonical name** — `FeeAccrualLog`.
2. **Definition** — Per-position daily accrual of management / performance fees, SBL fees, financing costs (§15.6 IBP-163, §6 mandate fee schedules). Lives logically as a derived projection but materialised for performance.
3. **Minimum field set** — `accrual_id`, `position_state_key (w, u)`, `accrual_date`, `accrual_basis`, `fee_rate`, `accrued_amount`, `crystallisation_event_ref` (when applicable), `cumulative_accrued`.
4. **Identity** — `accrual_id`.
5. **Provenance** — Daily accrual workflow.
6. **Temporal semantics** — Append-only; crystallisation moves it from accrued to settled in `PositionState.accrued_*_fee`.
7. **Failure consequences** — Fee crystallisation is wrong; HWM updates are wrong; managed-account economics drift.

---

## 6. Listed-Instrument Detail Data

The user lists this as a separate floor category. From a structural reading the bulk of "listed-instrument detail" is a *specialisation of Reference Data* (A11, A12, A14) — exchange-mediated, fungible, CCP-novated, with the exchange acting as oracle for settlement prices and corporate actions. There is, however, real listed-specific content not subsumed elsewhere. I list it.

### A53. Contract Specification

1. **Canonical name** — `ContractSpec`.
2. **Definition** — The exchange-published contract specification document for a listed derivative or future: underlier, strike-grid, expiry-grid, multiplier, settlement type (cash/physical), settlement currency, last-trading-date rule, first-notice date for physicals, daily settlement methodology. (§3.2 establishes that for listed derivatives the unit is *the contract specification*; this is the data backing that.)
3. **Minimum field set** — `contract_spec_id`, `exchange_mic`, `product_code` (e.g. `ES`, `NQ`, `SPX`), `underlier_instrument_id`, `multiplier`, `currency`, `option_strike_grid` (where applicable), `option_expiry_grid` (where applicable), `last_trading_date_rule`, `first_notice_date_rule` (physical futures), `settlement_methodology`, `tick_size_table` (links to A12), `effective_from`.
4. **Identity** — `contract_spec_id`. The hash of the spec backs the `unit_id` derivation (§3.7).
5. **Provenance** — Exchange.
6. **Temporal semantics** — Bitemporal — historical contract specs must be queryable for time-travelled valuations on expired listings.
7. **Failure consequences** — Derived `unit_id`s drift; CCP novation cannot identify the canonical contract; physical-delivery logic missing first-notice and last-trading dates.

### A54. CCP Membership and Cleared-Universe Mapping

1. **Canonical name** — `CCPClearingScope`.
2. **Definition** — Per-CCP, the set of products cleared and the per-product CCP virtual-wallet identity. Needed because the same listed contract cleared through different CCPs is different `unit_id`s (StatesHome §3.1: "CME-ES and ICE-ES are *distinct units*").
3. **Minimum field set** — `ccp_entity_id`, `cleared_contract_spec_ids`, `our_clearing_member_id`, `ccp_virtual_wallet_id` (per product), `default_fund_contribution_basis_ref`.
4. **Identity** — `(ccp_entity_id, contract_spec_id)`.
5. **Provenance** — CCP rulebooks; clearing-member onboarding.
6. **Temporal semantics** — As-of.
7. **Failure consequences** — `clearinghouse` field on per-position state cannot be set; cross-CCP exposure aggregation (EMIR Art 4) wrong; default-fund attribution impossible.

### A55. Daily Settlement Methodology

1. **Canonical name** — `SettlementMethodology`.
2. **Definition** — Per-listed-product, the specific algorithm by which the exchange computes the daily settlement price (last-trade, VWAP-final-N-minutes, theoretical-from-options, etc.). Necessary to reconstruct historical settlements deterministically.
3. **Minimum field set** — `methodology_id`, `contract_spec_id`, `algorithm_description_ref`, `effective_from`.
4. **Identity** — `methodology_id`.
5. **Provenance** — Exchange.
6. **Temporal semantics** — Bitemporal.
7. **Failure consequences** — Replay of historical futures settlement diverges from exchange records.

### A56. Listed Corporate Action Mechanism

1. **Canonical name** — `ListedCorpActionMechanism`.
2. **Definition** — Per-exchange-listed-instrument rules for how corporate actions (split, dividend, merger, contract adjustment for options) propagate through listed derivatives — the OCC adjustment memos for US options, the LME contract-adjustment notices for commodities. Specialisation of A23 to listed-derivative-aware semantics.
3. **Minimum field set** — `mechanism_id`, `affected_contract_spec_id`, `adjustment_type`, `adjustment_ratio`, `effective_date`, `publisher_id`.
4. **Identity** — `mechanism_id`.
5. **Provenance** — OCC / LME / NYSE / Nasdaq / exchange notices.
6. **Temporal semantics** — Bitemporal.
7. **Failure consequences** — Adjusted option strikes drift from market; "100 contracts of AAPL Jun 200 Call" no longer means the same thing pre- and post-adjustment.

### A57. Position-Limit / Reportable-Position Threshold

1. **Canonical name** — `PositionLimitSchedule`.
2. **Definition** — Per-listed-product, the regulatory and exchange-imposed position limits and reportable-position thresholds (CFTC for US futures, MiFID II for commodity derivatives). Needed for pre-trade guard (§17.2 open problem) and for regulatory reporting cadence.
3. **Minimum field set** — `limit_id`, `contract_spec_id`, `regime`, `limit_type ∈ {SPECULATIVE, REPORTABLE}`, `limit_value`, `aggregation_basis`, `effective_from`.
4. **Identity** — `limit_id`.
5. **Provenance** — Regulator / exchange.
6. **Temporal semantics** — Bitemporal.
7. **Failure consequences** — Position-limit breaches fire late; reportable-position notification missed.

---

This closes Pass A at **57 items** (A1–A57) covering all six floor categories:

- **Static**: A1–A10 (10 items)
- **Reference**: A11–A17 (7 items)
- **Market**: A18–A25 (8 items)
- **Oracle**: A26–A34 (9 items)
- **Smart-Contract Execution**: A35–A52 (18 items)
- **Listed-Instrument Detail**: A53–A57 (5 items)

---

# Pass B — Structural Collapse

The user asked: *are these the right objects, or are they presentations of fewer underlying sheaves/functors?*

My discipline forces a separate pass. The floor categories are **operational presentations**, useful for engineering teams and for negotiations with vendors and regulators. They are **not the natural objects of the data category**. Sliced differently the same items reveal a much smaller, much cleaner classification.

## B.1 — The Right Question

What is the category? Let me name it:

- **Objects:** facts the Ledger needs to answer questions about.
- **Morphisms:** *how a fact is obtained from prior facts.* That is — the provenance arrows.
- **Composition:** sequential provenance — "the calibrated curve was derived from quotes which were attested by a vendor which received them from an exchange."
- **Identity morphism:** "this fact is itself" — i.e. the Yoneda probe.

In this category the floor cuts are accidental: they are presentations along three orthogonal axes that happen to be conflated in the user's vocabulary. The three axes are:

### Axis 1 — Origin (where does the fact come from?)

- **(O.A) External Authoritative** — outside the Ledger boundary; the Ledger consumes, never authors. (Reference data, raw quotes, calendars, CSD confirmations, vendor attestations, regulator acknowledgements, contract specs, settlement-methodology documents.)
- **(O.I) Internal Authoritative** — born inside the Ledger; the Ledger is the source of truth. (Move stream, transaction stream, state delta, position state, lifecycle event log, settlement status log, idempotency tokens, correction links, valuation records.)
- **(O.D) Derived / Calibrated / Projected** — computed from prior data of either origin; not authoritative on its own. (Calibrated curves, snapshots, balance projections, fee accrual log, locate live state, PnL explain results, pricing DAG topology, the current `UnitStatus` and `PositionState` insofar as they are projections of the move stream.)

### Axis 2 — Mutation Discipline (how can it be written?)

- **(M.IM) Immutable** — once written, never modified. (Move stream, transaction stream, lifecycle event log, calibrated-curve epoch, valuation record, snapshot, idempotency tokens, correction links, oracle inbound messages.)
- **(M.AV) Append-only Versioned** — a non-empty list of versions; new versions append; old versions queryable. (`ProductTerms`, `SmartContractRegistry`, `CDMSynonyms`, `RegReportingSchema`, `PricingModelSpec`, `CalendarRegistry`, `EligibilitySchedule`, `ValuationPolicy`, `VersioningPolicy`.)
- **(M.MT) Mutable Total** — current value addressable directly, with bitemporal log behind it for reconstruction. (`UnitStatus`, `PositionState`, `WalletRegistry`, `EntityMaster`, `LocateState`, `BalanceSnapshot`, `ObligationStatus`, `SettlementStatusLog`'s current status.)
- **(M.AC) Accumulator** — append-only event stream feeding a derived totaliser. (`FeeAccrualLog`.)

### Axis 3 — Temporal Frame (what time axes does the fact carry?)

- **(T.PIT) Point-in-time** — one timestamp; the fact happened at $t$ and that is the whole story. (Raw quotes' venue timestamps in isolation; intraday calibration epochs in isolation.)
- **(T.AS)  As-of** — one logical "as of" timestamp meaning "valid at this time"; restatements rewrite. (Vendor reference data, official closing prices, calendar entries.)
- **(T.AO)  Append-only** — the stream is the history; no separate timestamp axis needed. (Move stream, lifecycle event log, transaction stream.)
- **(T.BT)  Bitemporal** — economic / valid time and knowledge / booking time independently navigable. (Most things at the boundary: rate fixings, corporate actions, KYC attestations, oracle confirmations; the move stream itself per §8.4.)

The product of these axes is the natural classification — **3 × 4 × 4 = 48** cells, but only a handful are populated.

## B.2 — The Three Sheaves

When I push past the axis dissection and ask *what is the minimal set of sheaves on a single base?*, the spec resolves into **three** fundamental sheaves over the base $\mathcal{B} = \mathcal{W} \times \mathcal{U} \times \mathcal{T}$ (wallets × units × time). The StatesHome ruling is the local statement of this global structure.

### Sheaf $\mathcal{F}_{\text{Defn}}$ — the Definition Sheaf (what things ARE)

A presheaf on $\mathcal{U} \times \mathcal{T}$, valued in append-only versioned types. Sections describe *what kind of thing inhabits each unit slot*. This subsumes:

- A2 ProductTerms — the unit-side `TermsVersion` history
- A3 Product Registry
- A4 Smart Contract Registry
- A6 Calendar Registry
- A11 Instrument Master
- A12 Lot/Tick
- A13 CDM Synonyms
- A47 PricingModelSpec
- A48 Pricing DAG Topology (per cycle)
- A53 Contract Specification
- A54 CCP Clearing Scope
- A55 Settlement Methodology
- A56 Listed Corporate Action Mechanism
- A57 Position-Limit Schedule
- A1 (partially) WalletRegistry — definitional metadata
- A5 Entity Master
- A7 Valuation Reference-Currency Config
- A8 Valuation Tolerance Policy
- A9 Capability Schema
- A10 Versioning Policy
- A14 Venue Schedule
- A15 CSD Reference
- A16 Reg Reporting Schema
- A17 Identifier Authority Bindings
- A33 Eligibility Schedule (slow-mutating definitional layer)

The unifying property: **every section is a versioned mathematical object describing the domain of discourse**. C6 / C7 / C8 / C10 from StatesHome are the local mutation discipline. The user's "Static" + "Reference" + "Listed-instrument detail" categories are jointly a *presentation* of $\mathcal{F}_{\text{Defn}}$. The axes that distinguish them — internally administered vs externally sourced, generic vs listed-specific — are properties of *sections* of $\mathcal{F}_{\text{Defn}}$ at specific stalks, not of distinct sheaves.

### Sheaf $\mathcal{F}_{\text{Obs}}$ — the Observation Sheaf (what is happening *to* the world)

A presheaf on $\mathcal{T}$ (and partially on $\mathcal{U}$), bitemporal append-only. Sections are *attestations from external authorities about external states of the world*. This subsumes:

- A18 Raw Quote
- A19 Calibrated Market Object (a derived layer of $\mathcal{F}_{\text{Obs}}$ — see B.3 on derived sheaves)
- A20 Rate Fixings
- A21 Official Closing Prices
- A22 Index Levels
- A23 Corporate Action Announcements
- A24 Vol Quotes (a sub-species of A18)
- A25 Market Data Snapshots
- A26 Settlement Confirmations
- A27 Custodian Attestations
- A28 Trade Confirmations
- A29 Locate Confirmations
- A30 Collateral Calls
- A31 Regulatory Acks
- A32 KYC Attestations
- A34 Vendor Reference-Data Attestation Receipts

The unifying property: **every section is an external attestation; the Ledger is an oracle-consuming functor with respect to $\mathcal{F}_{\text{Obs}}$**. The user's "Market data" and "Oracle data" categories are jointly a presentation of $\mathcal{F}_{\text{Obs}}$. The axis on which they split — "is this priced data or is this an event attestation?" — is a typology of the *codomain* of $\mathcal{F}_{\text{Obs}}$'s sections, not a categorical axis. The same Kalman-filter machinery (Valuation §4) that ingests A18 ingests A20 and could ingest A22 — the only difference is the observation matrix $H_t$.

### Sheaf $\mathcal{F}_{\text{Eff}}$ — the Effect Sheaf (what HAS happened *in* the Ledger)

A presheaf on $\mathcal{W} \times \mathcal{U} \times \mathcal{T}$, append-only by construction. Sections are *moves and the structures derived from them*. This subsumes:

- A35 Move Stream — the canonical sheaf section
- A36 Transaction Stream — the local atomicity envelope
- A37 State Delta — the per-event-class commit unit
- A38 UnitStatus (live snapshot — the colimit projection of $\mathcal{F}_{\text{Eff}}$ along $\mathcal{W}$)
- A39 PositionState (live snapshot — the local section over $(w, u)$)
- A40 Lifecycle Event Log (the CDM payload faithfully preserved)
- A41 Settlement Status Log
- A42 Workflow History (the orchestration sibling)
- A43 Idempotency Tokens
- A44 Snapshots
- A45 Obligation
- A46 Valuation Record
- A49 PnL Explain Result
- A50 Correction Link
- A51 Locate Live State
- A52 Fee Accrual Log

The unifying property: **the move stream is the universal section; everything else is a colimit, projection, or auxiliary index over it**. This is exactly the spec's claim: §8.1 ("the move stream is an immutable, chronological log... To substantiate a balance sheet at time $t$, aggregate the move stream"). StatesHome makes the same claim three-ways: `UnitStatus`, `PositionState`, even `ProductTerms` (versioned by amendment events) are projections of the lifecycle event log, which is a projection of $\mathcal{F}_{\text{Eff}}$.

The user's "Smart-contract execution data" category IS $\mathcal{F}_{\text{Eff}}$.

## B.3 — Why Three?

This is not a free choice. Three sheaves are forced by *three independent universal properties*:

1. **The category of objects of discourse** (Yoneda argument): without $\mathcal{F}_{\text{Defn}}$ no question of the form "what is a unit / wallet / product type / contract / regulator?" can be posed. Without it the Ledger cannot type its own events.

2. **The category of inbound attestations** (oracle adjunction): the Ledger sits in a comma category over the external world; the $\mathcal{F}_{\text{Obs}}$ sheaf is the right adjoint to the inclusion of the closed Ledger into the open world. Without $\mathcal{F}_{\text{Obs}}$ no fact about the external world can enter — the Ledger becomes a closed but useless system.

3. **The category of internal events** (free monoid argument): $\mathcal{F}_{\text{Eff}}$ is the free monoid on the alphabet of moves, modulo conservation. Without it the Ledger has no history and no economic content.

These three universal properties are independent: removing any one collapses the framework. **This is exactly the StatesHome argument repeated at the global level** — StatesHome derives three maps (`ProductTerms`, `UnitStatus`, `PositionState`) from three independent forcing constraints (Karpathy substitution, shared observables, append-only-vs-mutable). Pass B says the global framework decomposes into three sheaves for the same structural reasons.

## B.4 — Disagreements with the Floor

### B.4.1 — "Reference data" is not a category

It is a *property of provenance* (external authoritative) attached to sections of $\mathcal{F}_{\text{Defn}}$. Treating it as a separate category obscures the fact that A11 (Instrument Master, "reference") and A2 (Unit Registry Tier 3, "static") are facts of the *same kind* (definitional) at adjacent points in a provenance pipeline. The Ledger consumes A11 and emits A2, and the only meaningful structural distinction is which side of the boundary the section was authored on.

### B.4.2 — "Market data" and "Oracle data" are the same category

Both are inbound attestations. The cleanest formal account merges them into $\mathcal{F}_{\text{Obs}}$ and discriminates their codomains (numeric quote vs status event vs textual eligibility schedule) as a property, not as a category. This unification has a concrete consequence: the same calibration-with-Kalman-filter / innovation-gating / certification machinery (Valuation §4) is the right ingestion pipeline for *all* oracle inputs, not just market data. The framework already implicitly uses this — §10.2: "External messages are oracle outputs; synonym mappings are deterministic transforms... CDM functions then drive transition contracts and emit moves." That sentence is the unification. The floor list does not yet reflect it.

### B.4.3 — "Listed-instrument detail" is a sub-stalk, not a category

A53–A57 are sections of $\mathcal{F}_{\text{Defn}}$ at the stalks where `unit_type ∈ {LISTED_DERIV, EQUITY listed on exchange, ...}`. They are **specialised sections**, not a separate sheaf. Promoting them to a top-level category invites schema duplication (e.g. corporate actions appear once in A23 / A56 — these should be one datum with a listed-derivative-aware projection function).

### B.4.4 — "Smart-contract execution" is not parallel to the others; it IS the system

The other five floor categories are *inputs* and *configuration*; the sixth is *output*. The proper structural picture is:

```
   F_Defn (config + ref) ──┐
                            ├──► [ Ledger machinery ] ──► F_Eff (moves & all derivatives)
   F_Obs  (oracles)    ────┘
```

Treating $\mathcal{F}_{\text{Eff}}$ as one of six co-equal categories misrepresents the architectural shape. Pass A respected the user's framing because it was asked to; Pass B notes that the floor classification is therefore not a partition into peer kinds.

### B.4.5 — Items I added beyond the obvious

In Pass A I added items the spec implies but does not always name as separate data categories:

- **A8 Valuation Tolerance Policy** — without it the FSM (Valuation §2) is undefined.
- **A9 Capability Schema** — open problem in §17.2 but the *schema* is a current data requirement.
- **A10 Versioning Policy** — explicit prerequisite of replay determinism.
- **A25 MarketDataSnapshot as a first-class object** — in the spec it is implicit; making it explicit is required for time-travel reproducibility.
- **A37 StateDelta** — StatesHome introduces this term; treating it as data (not as a transient computation) lets C2/C3/C11 be schema-enforced.
- **A45 Obligation** — §14.7 establishes obligations as first-class objects; this elevates them to a data item.
- **A50 CorrectionLink** — §8.4 mandates the link is "a first-class metadata requirement, not an informal convention."
- **A52 FeeAccrualLog** — implicit in mandate / SBL economics; not previously named.

## B.5 — What This Buys

Stating the framework as three sheaves over one base buys four things:

1. **A single conservation argument**: every conservation invariant (P1, P21, P11–P20 for SBL, the StatesHome zero-sum-per-handler-class) is the statement that the colimit functor $\mathcal{F}_{\text{Eff}} \to (\text{aggregate balances})$ commutes with the conservation gauge group. One theorem, many specialisations.

2. **A single replay theorem**: $\text{apply\_all}(\text{events}[:k]) \cdot \text{apply\_all}(\text{events}[k:]) \equiv \text{apply\_all}(\text{events})$ is the statement that $\mathcal{F}_{\text{Eff}}$ is a fold (free monoid) on its alphabet — *given* that the same sections of $\mathcal{F}_{\text{Defn}}$ and $\mathcal{F}_{\text{Obs}}$ are pinned. Time-travel, idempotent retries, and snapshot consistency become corollaries of one structural statement.

3. **A single oracle-validation theorem**: the Kalman-filter machinery (innovation gating, $\chi^2$ acceptance, no-arbitrage projection — Valuation §4) is the canonical functor for ingesting any section of $\mathcal{F}_{\text{Obs}}$. This says the same architecture validates a vendor LEI lookup and an SOFR fixing and a settlement confirmation — they differ only in $H_t$ and $R_t$.

4. **A clean schema-evolution story**: amendments to $\mathcal{F}_{\text{Defn}}$ (a new product type, a new CDM version, a new regulatory regime) are extensions of the sheaf along $\mathcal{T}$; they never invalidate sections of $\mathcal{F}_{\text{Eff}}$ at earlier times because $\mathcal{F}_{\text{Eff}}$ is indexed by the version of $\mathcal{F}_{\text{Defn}}$ pinned at event time. C8 (the fungibility predicate) is the local statement of this in StatesHome; the global statement is sheaf naturality.

## B.6 — The One-Sentence Restatement

**The Ledger needs three sheaves over $\mathcal{W} \times \mathcal{U} \times \mathcal{T}$ — what things ARE ($\mathcal{F}_{\text{Defn}}$, append-only versioned), what is ATTESTED to it ($\mathcal{F}_{\text{Obs}}$, bitemporal append-only), and what HAPPENED inside it ($\mathcal{F}_{\text{Eff}}$, append-only by construction) — and every one of the user's 57 floor items is a section of one of these three at a specific stalk with a specific provenance.**

The floor categorisation is correct as a vendor-negotiation taxonomy; it is wrong as a structural architecture.
