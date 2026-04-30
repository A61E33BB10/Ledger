# Phase 1 — Independent Data Enumeration (Correctness-Architect Stance)

**Author role:** Correctness Architect (system-level correctness, deterministic
simulation testability, property coverage, fault injection).
**Sources read:** `ledger_v10.3.tex`, `ledger_v10.3_addendum_stateshome.tex`,
`ledger_valuation_v1.0.tex` (data-touching sections).
**Stance:** A datum exists for me iff it crosses a determinism boundary that I
must inject in a deterministic-simulation harness, OR it carries a conservation
or consistency invariant that the system must preserve, OR it bounds a
property-based generator universe. I enumerate each independently of any
storage mapping — placement is a Phase 2 question.

For each item, the seven mandatory fields are followed by:
- **(a) Determinism class:** {DET-INPUT | NON-DET-INPUT | CLOCK-BOUND |
  EXTERNAL-ORACLE | DERIVED}
- **(b) Fault catalogue:** which of {missing, late, duplicated, contradicted,
  mis-attributed, silent-corruption} apply
- **(c) End-to-end consistency law:** the invariant the datum carries through
  the system (linked to ledger invariants P1–P10, addendum conditions C1–C12,
  and valuation FSM where relevant).

---

## Floor-Category Audit (before enumeration)

The floor categories given are: **1. Static, 2. Reference, 3. Market, 4. Oracle,
5. Smart-contract execution, 6. Listed-instrument detail.**

I argue the following **before** enumerating items:

- **"Static" vs "Reference" overlap.** "Static" (immutable contractual params)
  and "Reference" (instrument/party masters) are not orthogonal in the source
  documents. The StatesHome ruling treats *ProductTerms* (versioned
  append-only) as the unifying carrier — terms ARE the unit's reference master.
  I keep both categories but mark "Static" as the **per-unit immutable terms
  schedule** and "Reference" as the **shared cross-unit master data** (parties,
  calendars, currencies, ISIN registries). Items collapsing into both are
  flagged.

- **"Listed-instrument detail" is subsumed.** A listed instrument is just a
  *NonTransferableProduct*/*TransferableProduct*-flavoured ProductTerms entry
  whose identity is derived from the contract specification (Section 3,
  Tier 1/Tier 3 of the Unit Store). Every field unique to listed instruments —
  exchange code, MIC, contract size, lot size, tick size, settlement style,
  exchange holiday calendar — is properly Reference (cross-instrument shared
  calendars) or Static (per-unit terms). I retain it as a category for
  Phase-2 indexing convenience but mark each item with its **truer home**.

- **A seventh category is missing: "Settlement / Custodial Plumbing".**
  Sections 8–9 (Settlement Layer Interface, ISO 20022) require SSI/CSD/BIC
  routing data that is neither static-contractual nor market-driven. Without
  it, no `SettlementInstruction` can be enriched into a wire message. I add it
  as **Category 7 — Settlement Infrastructure**.

- **An eighth category is missing: "Calibration / Latent State".** The
  valuation document introduces a Kalman-filtered latent state vector
  $x_{t|t}$ (yield curves, vol surface parameters) that is **neither raw market
  data nor a free oracle output** — it is a *stateful* derivation with its own
  noise structure $(Q, R_t)$, gating thresholds, and admissibility region
  $\Theta_{\mathrm{AF}}$. Conflating it with "Market" hides three distinct
  failure modes (bad observation noise model, bad process-noise tuning,
  no-arbitrage projection failure). I add it as **Category 8 — Calibrated
  Latent State**.

- **A ninth category is missing: "Workflow / Orchestration State".** Temporal
  workflow histories, freshness maps, retry counters, durable timers, and
  pricing-FSM state $\sigma(u)$ are **distinct from both move-stream events and
  unit state**. The ledger document explicitly maintains "two complementary
  audit trails" (Section 14.3) — and the second one is data the simulation
  harness must reconstruct. I add it as **Category 9 — Orchestration State**.

- **A tenth category is missing: "Test/Property Generators (the CDM enum
  universe)".** This is data — closed, finite, versioned, and falsifies
  completeness claims when CDM adds an enum value. Tracked separately because
  it bounds the generator input space for property-based testing (P1–P10) and
  must be co-versioned with the lifecycle handlers. I add it as **Category 10
  — Generator/Type Universe**.

- **An eleventh category is missing: "Provenance & Identity Cryptography".**
  Hash chains (Invariant 4), `EndToEndId`/`TxId` ISO-20022 identifiers,
  workflow IDs, idempotency tokens, UTI/USI/LEI, and `corrects`-chain
  back-references are first-class data with their own integrity invariants.
  Section 13.4 (move-stream integrity) explicitly mandates cryptographic
  hash chaining. Without enumerating identity/provenance separately, the data
  team will treat IDs as "free" and miss the catalogue of identifier
  collision, replay, and forgery faults. I add it as **Category 11 —
  Provenance & Identity**.

The enumeration below uses the **6 floor categories + 5 added categories =
11 categories**. Items mapping naturally to floor categories are kept there;
additions are clearly bracketed.

---

## Category 1 — Static (Per-Unit Immutable Contractual Terms)

These items are the body of *ProductTerms*[u] (versioned append-only,
**C6**, **C7**) and are immutable for the lifetime of the unit unless a
fungibility-preserving amendment appends a new `TermsVersion` (**C8**).

### 1.1 Product Identity
1. **Canonical name:** `unit_id`
2. **Definition:** A deterministic, system-wide unique identifier for a unit
   $u \in \mathcal{U}$. For listed instruments, hash of contract specification
   fields; for OTC, derived from the CDM Trade metadata key (UTI when
   present); for cash, the ISO 4217 code; for tokenized securities, contract
   address + chain ID + underlying ISIN.
3. **Minimum field set:** `{value: bytes, derivation_scheme: enum, version: int}`.
4. **Identity:** Itself — `unit_id` is the primary key for all
   *ProductTerms*, *UnitStatus*, and *PositionState* lookups.
5. **Provenance:** Generated at registration time (Section 3.4) by the Unit
   Store; never re-issued (**C10**).
6. **Temporal semantics:** Immutable, versioned only via the
   `SupersededBy(u_old → u_new)` mechanism for fungibility-breaking
   amendments.
7. **Failure consequences:** Any silent re-derivation of a different value for
   the "same" instrument shatters referential integrity (**P3**) and breaks
   conservation across the rename boundary.
- **(a)** DET-INPUT (deterministic function of CDM trade or contract spec).
- **(b)** Faults: collision (silent-corruption), re-registration with same id
  but different terms (contradicted), mis-attribution (LEI swap on virtual
  wallet), missing on retrieval, duplicated id with different `TermsVersion`
  history.
- **(c)** Referential-integrity invariant **P3**: every move and every
  *PositionState* row references an existing unit_id. **C10** forbids
  re-registration. **Property:** `derive_unit_id(cdm_obj_a) == derive_unit_id(cdm_obj_b) ⟺ economically_identical(a, b)`.

### 1.2 Product Terms Body (CDM EconomicTerms)
1. **Canonical name:** `product_terms`
2. **Definition:** The complete CDM `EconomicTerms` object (or
   institution-specific equivalent for non-CDM-native units) comprising
   payout structure, schedule, day-count, calculation agent, business-day
   adjustments, settlement type, exercise terms.
3. **Minimum field set:** `{payout: CDM.Payout, schedule: List[Date],
   day_count: DCFEnum, business_day_adj: BDAEnum, currency: ISO4217,
   settlement_type: SettlementEnum, exercise_terms: Option<ExerciseTerms>,
   notional_or_quantity: Decimal}`.
4. **Identity:** Identified by `(unit_id, terms_version_index)`.
5. **Provenance:** Trade execution (OTC) or reference-data feed (listed);
   ProductRegistry maps `EconomicTerms` to a smart-contract template via CDM
   `ProductQualification` (Section 3).
6. **Temporal semantics:** Versioned append-only (**C6**); fungibility
   predicate `is_fungibility_preserving` decides whether an amendment
   appends or allocates a fresh `unit_id` (**C8**).
7. **Failure consequences:** Wrong day-count, wrong business-day
   adjustment, wrong notional → wrong cash-flow amounts → conservation holds
   on quantities but value invariance (Property 5) violated.
- **(a)** DET-INPUT.
- **(b)** missing (term not loaded), contradicted (two channels disagree),
  silent-corruption (incorrect day-count silently changes accrual),
  mis-attributed (CSA mapped to wrong trade).
- **(c)** Determinism precondition: pure lifecycle function $f(\text{state}, \text{terms}, \text{mkt}) \to (\text{moves}, \text{state}')$ requires `terms` constant. Any in-place mutation breaks **P9** purity. **Property:** $\sum_w \Delta_q(w, u) = 0$ regardless of `terms`; value invariance under deterministic lifecycle requires `terms` correctness.

### 1.3 CDM Lineage Payload
1. **Canonical name:** `cdm_business_event_payload`
2. **Definition:** The full original CDM `BusinessEvent` (with `before`/`after`
   `TradeState`, `WorkflowStep` lineage, primitive instruction tree)
   stored alongside each transaction. This is what makes $F$ "forgetful but
   not destructive" (Section 9.4).
3. **Minimum field set:** `{cdm_version: SemVer, business_event: bytes (CDM),
   primitive_instructions: List[PrimitiveInstruction], workflow_lineage: List[WorkflowStep], event_intent: EventIntentEnum}`.
4. **Identity:** Joined to a transaction by `tx_id`.
5. **Provenance:** Inbound CDM-mapped message; or generated by a smart-contract
   for lifecycle-originated events (Section 8.5).
6. **Temporal semantics:** Immutable; co-immutable with the move stream
   (Invariant 4).
7. **Failure consequences:** Without it, regulatory reconstruction (DRR,
   EMIR Refit), audit, and full-fidelity time travel are impossible.
- **(a)** DET-INPUT (after CDM synonym mapping).
- **(b)** missing (mapping pipeline drop), late (event arrives after
  economic timestamp — distinguish booking vs economic time), duplicated,
  silent-corruption from CDM version drift.
- **(c)** **Composition restriction (Section 9.4)**: $F(e_2 \circ e_1) = F(e_2) \circ F(e_1)$ holds only for referentially-independent events; a missing payload prevents resolving cascades. **Property:** every committed transaction has a non-null CDM payload OR is explicitly tagged `LIFECYCLE_INTERNAL`.

### 1.4 Smart-Contract Binding
1. **Canonical name:** `smart_contract_ref`
2. **Definition:** Reference (by hash + version) to the deterministic
   move-generating function that governs the unit's lifecycle.
3. **Minimum field set:** `{contract_id, contract_version, code_hash,
   product_qualification_class}`.
4. **Identity:** Tier-2 ProductRegistry key.
5. **Provenance:** Bound at unit registration; immutable thereafter except
   by version migration.
6. **Temporal semantics:** Versioned; old versions retained for time-travel
   replay.
7. **Failure consequences:** Loss of binding → executor cannot invoke a
   handler → unit is operationally orphaned.
- **(a)** DET-INPUT.
- **(b)** missing (handler not deployed), contradicted (two registry entries
  for same product class), silent-corruption (wrong handler bound, wrong
  pure function executed).
- **(c)** Unit-Store guarantee (Section 3.6): "every registered unit has a
  bound smart contract that the executor can invoke for lifecycle events."
  **Property:** `code_hash(deployed_handler) == registered_code_hash(unit_id)`
  for every active unit.

### 1.5 Day-Count, Business-Day, Calendar Conventions (per-unit)
1. **Canonical name:** `convention_set`
2. **Definition:** Tuple `(DayCountFractionEnum, BusinessDayConventionEnum,
   CalendarRefSet)` driving every accrual, schedule, and reset computation.
3. **Minimum field set:** `{day_count: DCFEnum, bday_conv: BDCEnum,
   calendars: List[CalendarRef], roll_convention: RollEnum}`.
4. **Identity:** Embedded in `product_terms`; pointer to Reference Category
   for the holiday calendars.
5. **Provenance:** CDM `EconomicTerms`; for non-CDM units, institution
   reference.
6. **Temporal semantics:** Immutable per unit (under fungibility-preserving
   discipline).
7. **Failure consequences:** Wrong year fraction $\delta_k$ → wrong swap
   payments, wrong bond accrual, wrong schedule dates.
- **(a)** DET-INPUT.
- **(b)** mis-attributed (wrong calendar), missing (calendar not loaded for
  the day of valuation), silent-corruption.
- **(c)** **Property** (metamorphic): for IRS payment, swapping calendars
  with the same business-day set produces identical schedules; year-fraction
  is monotone in period length under a fixed convention.

---

## Category 2 — Reference (Cross-Unit, Cross-Party Master Data)

### 2.1 Party Master (LEI / BIC / ISO Party Identifier)
1. **Canonical name:** `party_master[lei]`
2. **Definition:** Authoritative identification of every legal entity that
   appears as wallet owner (real or virtual), counterparty, calculation agent,
   issuer, custodian, CCP, or settlement participant. Underpins virtual-wallet
   identity (Section 2.6) and ISO 20022 routing.
3. **Minimum field set:** `{lei: LEI, bic: Option<BIC>, legal_name: String,
   jurisdiction: ISO3166, party_role_capabilities: Set<RoleEnum>, status:
   {ACTIVE, LAPSED, RETIRED}, parent_lei: Option<LEI>}`.
4. **Identity:** LEI (ISO 17442); BIC where applicable.
5. **Provenance:** GLEIF for LEI; SWIFT for BIC.
6. **Temporal semantics:** Slowly mutable; LEI status changes (lapse,
   merger, transfer) must be timestamped.
7. **Failure consequences:** Mis-routed settlements; broken EMIR/SFTR/MiFIR
   reporting; counterparty-credit netting set built on stale LEI tree.
- **(a)** EXTERNAL-ORACLE (GLEIF feed).
- **(b)** missing (LEI lookup fails at trade time), late (status change not
  reflected), duplicated, contradicted (internal vs GLEIF disagree),
  mis-attributed (wrong LEI on a confirmation), silent-corruption.
- **(c)** **Property:** every virtual wallet has a party_master entry with
  status ACTIVE on the move's timestamp; every move's metadata's
  counterparty_lei resolves; netting-set membership is closed under
  parent_lei merger.

### 2.2 Account Master (BIC + IBAN + CSD Account)
1. **Canonical name:** `account_master[external_id]`
2. **Definition:** External account identifiers that the settlement
   projection needs to enrich `SettlementInstruction` into wire messages
   (Section 8.1.2).
3. **Minimum field set:** `{external_id: AccountId, owner_lei: LEI,
   bic: BIC, iban: Option<IBAN>, csd: Option<CSDIdentifier>,
   csd_participant_id: Option<String>, currency: ISO4217, account_type:
   {NOSTRO, VOSTRO, OMNIBUS, SEGREGATED, PROPRIETARY}}`.
4. **Identity:** `external_id` joined to wallet via the wallet→account
   mapping owned by the settlement layer (boundary-separation principle).
5. **Provenance:** SSI database (settlement layer); operationally maintained
   independently from the ledger.
6. **Temporal semantics:** Slowly mutable; SSI changes are versioned with
   effective-from/to dates.
7. **Failure consequences:** Wire instruction routed to wrong account →
   real-world settlement failure; CASS-6 segregation violation if account_type
   mis-classified.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing (wallet has no SSI on settlement date), late (SSI updated
  but stale cache), duplicated (two active SSIs for same counterparty),
  contradicted, mis-attributed.
- **(c)** **Property:** for every committed `SETTLEMENT` transaction, the
  enrichment step finds exactly one active SSI per leg per currency at the
  settlement timestamp.

### 2.3 Currency Reference (ISO 4217 + Holiday Calendars)
1. **Canonical name:** `currency_master`
2. **Definition:** Per-currency static + calendar bundle: ISO 4217 code, decimal
   precision (rounding), payment-system identifier, currency holiday calendar.
3. **Minimum field set:** `{iso4217: String(3), decimals: int,
   payment_system: PSEnum, holiday_calendar_ref: CalendarRef,
   intraday_cutoff: Time}`.
4. **Identity:** ISO 4217 code.
5. **Provenance:** ISO standard; calendar from financial-calendar provider.
6. **Temporal semantics:** Slowly mutable (currency redenomination, holiday
   updates published months in advance).
7. **Failure consequences:** Wrong rounding precision → silent fractional-cent
   accumulation breaking conservation at decimal level. Wrong holiday
   schedule → wrong business-day-adjusted payment dates.
- **(a)** EXTERNAL-ORACLE (ISO + provider).
- **(b)** missing (new currency not loaded), late, contradicted (two
  providers disagree on a holiday), silent-corruption (decimals field wrong).
- **(c)** **Property:** for every cash move, `quantize(quantity, decimals)
  == quantity`. **Property:** for every IRS payment date $t_k$,
  `bday_adjust(t_k_unadjusted, calendar) == t_k`.

### 2.4 Holiday / Business-Day Calendar
1. **Canonical name:** `calendar[ref]`
2. **Definition:** Set of non-business days for a venue, currency, or
   composite (e.g., `USD+EUR+TARGET`).
3. **Minimum field set:** `{calendar_ref: String, holidays: Set<Date>,
   weekend_pattern: WeekendEnum, valid_from: Date, valid_to: Date,
   provider: ProviderEnum}`.
4. **Identity:** `calendar_ref` (e.g., `USNY`, `EUTA`, `LON`).
5. **Provenance:** External provider (Refinitiv / Bloomberg / FpML
   `BusinessCenters`).
6. **Temporal semantics:** Annually published, occasional emergency
   amendments (royal funeral, sovereign default declaration).
7. **Failure consequences:** Wrong-day reset, wrong-day coupon, wrong-day
   settlement; under CDM, the entire `BusinessDayAdjustments` machine
   produces wrong adjusted dates.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing (date queried not in loaded range), late (emergency
  closure), duplicated, contradicted (cross-vendor), silent-corruption.
- **(c)** **Property:** `bday_adjust(d, cal)` is idempotent (already-adjusted
  date is fixed under the convention); composite calendars satisfy union
  semantics: `holidays(A∪B) = holidays(A) ∪ holidays(B)`.

### 2.5 ISIN / CUSIP / SEDOL Reference
1. **Canonical name:** `security_master[isin]`
2. **Definition:** Authoritative mapping from ISIN/CUSIP/SEDOL to issuer,
   security type, currency of denomination, exchange listing(s), corporate
   action history pointer.
3. **Minimum field set:** `{isin: ISIN, cusip: Option<CUSIP>, sedol:
   Option<SEDOL>, issuer_lei: LEI, security_type: SecTypeEnum,
   denomination_currency: ISO4217, primary_exchange_mic: MIC, status:
   {LIVE, MATURED, DELISTED, SUSPENDED}, lot_size: Decimal,
   corp_action_history_ref: Pointer}`.
4. **Identity:** ISIN (composite of country prefix + 9 digits + check).
5. **Provenance:** National Numbering Agency (NNA) / ANNA; vendor reference
   (Bloomberg, Refinitiv).
6. **Temporal semantics:** Slowly mutable but ISIN reuse is permitted under
   strict rules → time-travel must distinguish "ISIN at $t_1$" from "ISIN at
   $t_2$" when status changed.
7. **Failure consequences:** ISIN reuse silently relinks an old position to a
   new instrument → catastrophic mis-attribution in time-travel queries.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late (corporate action triggers ISIN change not yet
  ingested), duplicated (cross-jurisdiction conflict), contradicted,
  mis-attributed (vendor maps wrong CUSIP to ISIN), silent-corruption.
- **(c)** **Property:** `unit_id_listed(isin, t)` is stable across calls at
  the same $t$ regardless of vendor; ISIN-reuse events generate an explicit
  `SupersededBy` trail (**C8**).

### 2.6 Exchange / MIC / Trading-Venue Master
1. **Canonical name:** `venue_master[mic]`
2. **Definition:** Per-trading-venue static: MIC, trading hours, settlement
   cycle convention (T+1, T+2, T+0), tick size grids, lot size, contract
   specification template.
3. **Minimum field set:** `{mic: MIC(4), name: String, country: ISO3166,
   trading_hours: WeekSchedule, settlement_cycle: SettlementCycle,
   tick_grids: Map<InstrumentClass, TickGrid>, lot_grids: Map<InstrumentClass, LotGrid>}`.
4. **Identity:** MIC (ISO 10383).
5. **Provenance:** ISO + venue rulebooks.
6. **Temporal semantics:** Slowly mutable; tick-size regime changes
   announced in advance.
7. **Failure consequences:** Wrong tick → orders rejected; wrong settlement
   cycle → wrong economic vs settlement-date posting.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late (regime change not loaded), contradicted.
- **(c)** **Property:** every trade has `tick_grid(mic, class) ∋ price`; lot
  rounding identity holds (Section 5.4): $N = N_{\text{deliver}} +
  N_{\text{residual}}$ with $N_{\text{deliver}}$ a multiple of `lot_size`.

### 2.7 CCP / Clearing-Member Master
1. **Canonical name:** `ccp_master[ccp_id]`
2. **Definition:** Per-CCP static governing novation rules, margin
   methodology hooks, default-fund mechanics, position-account taxonomy.
3. **Minimum field set:** `{ccp_id, ccp_lei, jurisdictions: Set<ISO3166>,
   asset_classes: Set<AssetClass>, margin_methodology: MMEnum,
   position_account_types: Set<PAEnum>, member_id: ClearingMemberId}`.
4. **Identity:** CCP LEI + clearing-member ID composite.
5. **Provenance:** CCP rulebook; CFTC/ESMA registers.
6. **Temporal semantics:** Slowly mutable.
7. **Failure consequences:** Wrong margin model invocation; wrong default
   fund attribution; cross-CCP netting (EMIR Art. 4) computed against wrong
   netting set.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late, contradicted (member-status change not propagated),
  mis-attributed.
- **(c)** **Property:** every `CCP_VIRTUAL` wallet's owner_lei is in
  `ccp_master`; per-(wallet, contract, CCP) accumulated_cost rows obey
  $\sum_w \texttt{ac}(w, u_{\text{at-CCP}}) = 0$ within each CCP scope
  (Section 7.4).

### 2.8 Custodian / CSD / ICSD Master
1. **Canonical name:** `custodian_master[csd_id]`
2. **Definition:** Per-CSD/ICSD/custodian static enabling DvP settlement
   routing and reconciliation of virtual wallets against external statements.
3. **Minimum field set:** `{csd_id, lei, dvp_modes_supported: Set<DvPMode>,
   message_types_supported: Set<ISO20022MsgType>, cutoff_times: Map<Currency, Time>,
   reconciliation_endpoint: ConnectionRef}`.
4. **Identity:** LEI + ISO 20022 BIC.
5. **Provenance:** CPMI registry; SWIFT directory.
6. **Temporal semantics:** Slowly mutable.
7. **Failure consequences:** DvP atomicity claim (Section 8.7) is a function
   of CSD capability — wrong DvP mode → real-world Herstatt risk.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late, contradicted, silent-corruption.
- **(c)** **Property:** every `SETTLEMENT` transaction tagged DvP routes
  through a custodian whose `dvp_modes_supported` includes the requested
  mode at the settlement timestamp.

### 2.9 Wallet Registry (Metadata, Not State)
1. **Canonical name:** `wallet_registry[wallet_id]`
2. **Definition:** Per-wallet operational metadata: owner identity, KYC
   status, permission scopes, audit cursor (the StatesHome addendum
   explicitly calls this **non-state**, **non-financial** sidecar; cf.
   addendum line 96).
3. **Minimum field set:** `{wallet_id, type: {REAL, VIRTUAL}, owner_lei: LEI,
   sub_account: Option<String>, kyc_status: KYCEnum, capability_set:
   Set<CapabilityEnum>, audit_cursor: TxId}`.
4. **Identity:** `wallet_id`.
5. **Provenance:** Onboarding workflow; immutable post-creation except
   permissions.
6. **Temporal semantics:** Mostly stable; audit cursor advances with each
   read.
7. **Failure consequences:** Capability bypass (e.g., un-permissioned wallet
   acquires positions); KYC lapse undetected; mis-attributed virtual-wallet
   counterparty.
- **(a)** DET-INPUT (after onboarding).
- **(b)** missing, contradicted (capability set drifts from policy), silent
  corruption.
- **(c)** **C4** — capability-scoped reads. Cross-$(w, u_{\text{MA}})$
  overlay reads forbidden. **Property:** every move's source/destination
  wallet has the capability matching the unit class at the move's timestamp.

### 2.10 Mandate / Strategy as Unit (Per StatesHome Ruling)
1. **Canonical name:** `mandate_unit_terms[u_MA]`
2. **Definition:** When a managed account or QIS is treated as a CDM-issued
   contract (per StatesHome §4.2), its mandate text, fee schedule, benchmark
   identity, position limits, HWM methodology, crystallisation frequency are
   ProductTerms entries. The **client-specific** HWM value, accrued fee, and
   breach flags live at *PositionState*$[w_{\text{client}}, u_{\text{MA}}]$.
3. **Minimum field set:** `{mandate_text_ref: DocRef, fee_schedule:
   FeeSchedule, benchmark_unit_id: Option<UnitId>, position_limits:
   List<Limit>, hwm_methodology: HWMEnum, crystallisation_freq: Period,
   breach_predicates: List<Predicate>}`.
4. **Identity:** `unit_id` of the mandate contract.
5. **Provenance:** Onboarding contract.
6. **Temporal semantics:** Versioned ProductTerms (**C6**); fungibility
   predicate decides whether limit changes append a TermsVersion or
   require a new $u_{\text{MA}}$.
7. **Failure consequences:** Cross-mandate HWM collapse if not keyed on
   $(w, u_{\text{MA}})$; SFTR/EMIR reporting surface for mandate issuance
   not handled (R8/F5 in addendum risk register).
- **(a)** DET-INPUT.
- **(b)** missing, contradicted (Legal / Product / Risk version drift),
  mis-attributed.
- **(c)** **C12**: per-(w, mandate) economic state lives only at
  `PositionState[w, u_MA]`. **Property:** $w_{\text{manager}}(u_{\text{MA}}) +
  w_{\text{client}}(u_{\text{MA}}) = 0$ (issuance-conservation).

---

## Category 3 — Market (Raw Observables)

### 3.1 Price Feeds (Spot, Reference, Settlement)
1. **Canonical name:** `quote[feed, instrument, t]`
2. **Definition:** Time-stamped raw market quote — bid, ask, last, settlement,
   index level, deposit rate, swap rate, futures settlement price.
3. **Minimum field set:** `{instrument_ref, feed_id, timestamp,
   side: {BID, ASK, MID, LAST, SETTLE, INDEX}, price: Decimal,
   size: Option<Decimal>, condition_codes: Set<String>, snapshot_id:
   SnapshotId}`.
4. **Identity:** `(feed_id, instrument_ref, timestamp, side)`.
5. **Provenance:** Exchange / vendor (Bloomberg / Refinitiv / direct feeds).
6. **Temporal semantics:** Tick-level continuous; published settlement at
   exchange EOD (CME-ES Section 7.4 example).
7. **Failure consequences:** Section 13 explicitly mandates dual-timestamp
   (economic vs booking) for stale data; silent stale price → wrong margin
   call → real cash misdirected.
- **(a)** EXTERNAL-ORACLE; CLOCK-BOUND (snapshot timestamp).
- **(b)** missing (feed outage), late (replayed quote), duplicated, contradicted
  (NKY-SIMEX vs NKY-CME, Section 10), mis-attributed (wrong ISIN→quote
  mapping), silent-corruption (decimal-place drift).
- **(c)** Section 4 portfolio value $V_t = \sum_u w_t(u) \cdot P_t(u)$ — every
  quote propagated as $P_t(u)$ must be from the **stored snapshot at the time
  of the lifecycle invocation**, not a live feed (Section 7.7 deterministic
  oracle requirement). **Property:** `replay_at(t)` re-uses the same snapshot
  bytes — `snapshot_hash(t) == snapshot_hash(t)`.

### 3.2 Market Data Snapshot (Versioned Bundle)
1. **Canonical name:** `market_snapshot[snapshot_id]`
2. **Definition:** A frozen, content-addressed bundle of all quotes used by a
   given lifecycle invocation; the unit of determinism for replay (Section
   7.7).
3. **Minimum field set:** `{snapshot_id: ContentHash, captured_at: Timestamp,
   source: FeedRef, fallback_chain: List<FeedRef>, contained_quote_ids:
   List<QuoteId>}`.
4. **Identity:** Content hash (immutable address).
5. **Provenance:** Captured at lifecycle invocation; persisted before
   handler execution.
6. **Temporal semantics:** Two-axis: `captured_at` (when assembled) vs
   `as_of` (the reference time the snapshot is meant to represent). Both
   must be retained for "what we knew at $t$" vs "with corrected data"
   replay (Section 1, Property 6).
7. **Failure consequences:** No snapshot → handler is non-deterministic →
   **P9 purity invariant violated**.
- **(a)** DET-INPUT (after capture).
- **(b)** missing (capture failed), duplicated (two snapshots claim same
  hash from different content — collision), late (snapshot built after
  some quotes already moved), silent-corruption (storage rot on a
  long-tenor unit).
- **(c)** **Property** (replay determinism): for any committed transaction
  with a stored snapshot, re-executing the handler against that snapshot
  yields bit-identical moves and state delta. **Property** (vendor-correction
  separation): "as-known-at-$t$" replay and "with-corrected-data" replay
  use **different** snapshot ids; conflation is a Goodhart trap.

### 3.3 FX Rate Feed
1. **Canonical name:** `fx_rate[ccy_pair, t]`
2. **Definition:** Timestamped rate $r_{X/Y}(t)$ used to convert non-reference-
   currency cash to the reference currency for valuation only; multi-currency
   conservation operates per-currency, **not** at value level.
3. **Minimum field set:** `{ccy_pair: (ISO4217, ISO4217), timestamp,
   rate_type: {SPOT, FIXING, FORWARD, CLOSE}, rate: Decimal,
   source: FeedRef}`.
4. **Identity:** `(ccy_pair, timestamp, rate_type)`.
5. **Provenance:** ECB fixings, WM/Refinitiv 4pm fix, CCP fixings.
6. **Temporal semantics:** Continuous tick + designated fixings.
7. **Failure consequences:** Wrong rate at TRS reset → unexplained PnL
   (Section 6.7 price-consistency note explicitly warns).
- **(a)** EXTERNAL-ORACLE; CLOCK-BOUND.
- **(b)** missing, late, contradicted (cross-source for same fixing),
  mis-attributed (BRL/USD vs USD/BRL inversion), silent-corruption.
- **(c)** **Property:** $r_{X/Y}(t) \cdot r_{Y/X}(t) = 1$ within rounding;
  triangulation $r_{X/Z} = r_{X/Y} \cdot r_{Y/Z}$ holds within the
  spread tolerance (metamorphic).

### 3.4 Interest Rate / Yield Curve Observables
1. **Canonical name:** `curve_observables[curve_ref, t]`
2. **Definition:** Raw inputs to yield-curve construction — overnight
   indices (SOFR, ESTR), deposit rates, futures, swap rates, basis quotes.
3. **Minimum field set:** `{curve_ref, observation_set: List<{instrument_ref,
   tenor, rate, timestamp}>, conventions: ConventionSet}`.
4. **Identity:** `(curve_ref, observation_timestamp)`.
5. **Provenance:** Trading venues, IBA, ARRC, ECB.
6. **Temporal semantics:** Daily fixings; intraday for liquid tenors.
7. **Failure consequences:** Wrong observable → wrong calibrated curve →
   wrong IRS valuation → wrong CSA margin call.
- **(a)** EXTERNAL-ORACLE; CLOCK-BOUND.
- **(b)** missing (BMR cessation), late, contradicted, silent-corruption
  (decimal scaling).
- **(c)** Feeds Category 8 (Calibrated Latent State); the consistency law
  is the **innovation gate** $D_t^2 \le u_{m_t}$ from valuation §5.5.

### 3.5 Volatility Surface Observables
1. **Canonical name:** `vol_observables[surface_ref, t]`
2. **Definition:** Listed/OTC option mid prices and implied vols across
   strikes and expiries that drive vol-surface calibration.
3. **Minimum field set:** `{surface_ref, observation_set: List<{strike,
   expiry, option_type, mid_price, mid_iv, bid_ask_spread, timestamp}>}`.
4. **Identity:** `(surface_ref, observation_timestamp)`.
5. **Provenance:** Listed exchange option books; OTC indicative quotes.
6. **Temporal semantics:** Continuous; many strikes are illiquid.
7. **Failure consequences:** Bad vol → bad delta → bad hedge; bad bucket
   vega → unexplained PnL on local-vol or kernel-vol Jacobian.
- **(a)** EXTERNAL-ORACLE; CLOCK-BOUND.
- **(b)** missing (illiquid strike), late, contradicted (broker vs
  exchange), silent-corruption (interpolation hidden in vendor feed).
- **(c)** No-arbitrage feasibility — feeds Category 8.

### 3.6 Credit / Hazard / Default Observables
1. **Canonical name:** `credit_observables[entity_lei, t]`
2. **Definition:** CDS spreads, recovery rates, credit-event records that
   drive hazard-curve calibration and default lifecycle handling.
3. **Minimum field set:** `{entity_lei, observation_set: List<{tenor,
   spread, recovery, timestamp}>, credit_event_records:
   List<CreditEventRecord>}`.
4. **Identity:** `(entity_lei, observation_timestamp)`.
5. **Provenance:** ISDA Determinations Committee, broker quotes,
   IHS Markit / S&P Global.
6. **Temporal semantics:** Daily; credit events are point-in-time and
   irreversible.
7. **Failure consequences:** Missing credit event → CDS does not trigger;
   delayed credit-event ingestion → mass mis-valuation across the affected
   entity's instruments.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late (credit event lagged), duplicated (two DC rulings),
  contradicted, silent-corruption.
- **(c)** **Property** (binary-event monotonicity): once a credit event is
  recorded for $(\text{entity}, \text{event\_date})$, no later record can
  unrecord it without an explicit `CORRECTION` transaction with full lineage.

### 3.7 Settlement / Fixing Calendars
1. **Canonical name:** `settlement_calendar[ccy_or_index, t]`
2. **Definition:** Currency-/index-specific settlement and fixing calendars
   driving when payments and resets actually crystallise.
3. **Minimum field set:** `{calendar_ref: String, fixings: Map<Date,
   FixingValue>, settlement_dates: Set<Date>, valid_from, valid_to}`.
4. **Identity:** `calendar_ref + date`.
5. **Provenance:** Currency authorities, IBA, central counterparties.
6. **Temporal semantics:** Fixings are once-and-final; reissue requires
   `CORRECTION`.
7. **Failure consequences:** Reset uses wrong fixing → wrong swap payment.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late (overnight fixing not yet published when handler
  fires), contradicted, silent-corruption.
- **(c)** **Property:** for each reset $t_k$ in a swap schedule, exactly
  one fixing value is sourced; fixing immutability is a hard pre-condition
  for the lifecycle handler.

---

## Category 4 — Oracle (Externally-Determined Truths Beyond Pricing)

The ledger document uses "oracle" to mean any boundary input the system
treats as authoritative (Section 9.2 "Mapping Layer as Oracle Interface").
This category covers oracles that are **not** pure market data.

### 4.1 Corporate Action Records
1. **Canonical name:** `corp_action[isin, ann_date]`
2. **Definition:** Authoritative records of dividends, splits,
   reverse-splits, mergers, spin-offs, rights issues, redenominations,
   liquidations.
3. **Minimum field set:** `{isin, action_type: CorpActionEnum, announce_date,
   record_date, ex_date, payment_date, ratio_or_amount: Decimal,
   currency: ISO4217, source_lei: LEI, voluntary_election:
   Option<ElectionMatrix>, supersedes: Option<CorpActionId>}`.
4. **Identity:** `(isin, action_type, ex_date, sequence)`.
5. **Provenance:** Issuer announcements via Reuters, DTCC, custodians;
   normalised by vendors.
6. **Temporal semantics:** Multi-date timeline (announce → record → ex →
   pay); amendments (DTCC publishes superseding records frequently).
7. **Failure consequences:** Missed split → position quantity wrong by a
   factor of N → cascades to wrong delta, wrong margin, wrong settlement.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing (issuer announcement not picked up), late, duplicated
  (multiple vendors), contradicted (vendor vs DTCC), mis-attributed (wrong
  ISIN), silent-corruption (ratio as 2:1 vs 1:2).
- **(c)** **Property** (split conservation): for a 2-for-1 split, $\sum_w w_t(u_{\text{new}}) = 2 \cdot \sum_w w_{t-1}(u_{\text{old}})$; pre-record-date moves on $u_{\text{old}}$ replay through the corp-action handler to produce the post-ex-date $u_{\text{new}}$ position. **Property** (idempotency, **P5**): replaying the same corp-action record twice produces no incremental change.

### 4.2 Credit-Event Determinations (ISDA DC)
1. **Canonical name:** `credit_event_record[entity_lei, event_id]`
2. **Definition:** Authoritative ISDA Determinations Committee rulings on
   bankruptcy, failure-to-pay, restructuring; trigger CDS lifecycle.
3. **Minimum field set:** `{entity_lei, event_id, event_type: CreditEventEnum,
   determination_date, event_date, auction_date: Option<Date>,
   final_recovery: Option<Decimal>, dc_decision_url}`.
4. **Identity:** ISDA DC event id.
5. **Provenance:** ISDA DC website / FpML feed.
6. **Temporal semantics:** Determination + auction lag; can supersede.
7. **Failure consequences:** Section 11 covers credit reporting; missed
   credit event → CDS unsettled, balance-sheet wrong.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late, contradicted (DC re-decision), silent-corruption.
- **(c)** **Property:** at most one ACTIVE credit event per
  $(\text{entity\_lei}, \text{event\_type}, \text{event\_date})$ at any
  time $t$; supersession chain is acyclic.

### 4.3 Regulatory / Sanctions / KYC Status Oracles
1. **Canonical name:** `compliance_oracle[lei, t]`
2. **Definition:** OFAC, EU sanctions, FATF lists, beneficial-owner
   identification status.
3. **Minimum field set:** `{lei, status: ComplianceStatusEnum,
   listing_date, source, evidence_ref}`.
4. **Identity:** `(lei, source, observation_date)`.
5. **Provenance:** OFAC, EU OJ, FATF.
6. **Temporal semantics:** Effective-from/to per source.
7. **Failure consequences:** Settlement to a sanctioned party →
   regulatory breach.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing (delta not propagated), late, duplicated, contradicted,
  silent-corruption.
- **(c)** **Property:** every move's source and destination wallets'
  owner LEIs have status COMPLIANT at the move's timestamp.

### 4.4 Regulatory / Reference Identifier Oracles (UTI, USI, ISIN-Allocation)
1. **Canonical name:** `regulatory_id_oracle`
2. **Definition:** UTI generation rules (CPMI-IOSCO), USI generation,
   ISIN allocation, LEI parent-tree resolution.
3. **Minimum field set:** `{id_type: RegIdTypeEnum, generation_rules:
   ImmutableRules, version, valid_from}`.
4. **Identity:** `id_type + version`.
5. **Provenance:** CPMI, ANNA, GLEIF.
6. **Temporal semantics:** Versioned; ledger must store the rule version
   active at trade time for replay.
7. **Failure consequences:** Wrong UTI → reporting break → SFTR/EMIR fail.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late, contradicted (UTI prefix collision), silent-
  corruption.
- **(c)** **Property:** UTI uniqueness — `count_distinct_trades(uti) == 1`
  in the move stream.

### 4.5 Index / Benchmark Methodology Records
1. **Canonical name:** `benchmark_methodology[index_ref]`
2. **Definition:** Index sponsor's published methodology (constituents,
   weights, rebalance rules, fallback in case of cessation under EU BMR).
3. **Minimum field set:** `{index_ref, sponsor_lei, methodology_version,
   constituents: List<Constituent>, rebalance_schedule, fallback:
   FallbackProvision}`.
4. **Identity:** `(index_ref, methodology_version)`.
5. **Provenance:** Index sponsor (S&P, MSCI, ICE).
6. **Temporal semantics:** Versioned; BMR cessation triggers fallback.
7. **Failure consequences:** Wrong constituents → wrong basket-option
   payoff; missed BMR fallback → CDM `IndexCessation` not honored.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late, contradicted, mis-attributed (sponsor methodology
  vs vendor calculation differ).
- **(c)** **Property** (R5 basket-composition test from Section 7.6): time
  travel reproduces basket composition at $t_0$ and post-merger composition
  at $t_1$ from versioned methodology + corp-action records — never from a
  "current static file."

### 4.6 External Confirmation Messages (ISO 20022 Inbound)
1. **Canonical name:** `external_confirmation`
2. **Definition:** `sese.025`, `camt.054`, `pacs.002`, custodian breaks
   reports — these arrive as oracle inputs after settlement instruction.
3. **Minimum field set:** `{message_type, end_to_end_id, tx_id_ref,
   external_ref, status: SettStatusEnum, received_at,
   raw_message: bytes}`.
4. **Identity:** `(message_type, end_to_end_id)`.
5. **Provenance:** Custodian / CSD / counterparty.
6. **Temporal semantics:** Closes the EXECUTED → INSTRUCTED → SETTLED/FAILED
   lifecycle (Section 8.10).
7. **Failure consequences:** Missing confirmation → status stuck in
   INSTRUCTED → settlement-fail mis-classification.
- **(a)** EXTERNAL-ORACLE; LATE-ARRIVAL by definition.
- **(b)** missing, late, duplicated (re-sent), contradicted (success then
  fail then success), mis-attributed (`end_to_end_id` collision),
  silent-corruption.
- **(c)** **Property:** every settled transaction has at most one final
  confirmation per leg; idempotent ingestion (same `end_to_end_id` →
  same status).

---

## Category 5 — Smart-Contract Execution

This is the **handler-input/output** envelope. Most data here is structurally
already present in earlier categories; the items below are the
**execution-time** datums that exist only when a handler runs.

### 5.1 Pending Transaction (Handler Output)
1. **Canonical name:** `pending_tx`
2. **Definition:** The output of a pure lifecycle function: list of moves +
   list of state deltas + transaction-type tag, *before* the executor commits.
3. **Minimum field set:** `{tx_id: ContentHash, tx_type: {SETTLEMENT,
   COLLATERAL, LIFECYCLE, ACCOUNTING, CORRECTION}, moves: List<Move>,
   state_deltas: List<StateDelta>, idempotency_key, source_contract_ref,
   cdm_payload_ref, generated_at, generator_version}`.
4. **Identity:** `tx_id` (content hash of the immutable parts).
5. **Provenance:** Pure function emission; deterministic given (state, terms,
   snapshot).
6. **Temporal semantics:** Ephemeral until commit; on commit, becomes a
   fact in the move stream.
7. **Failure consequences:** Without a content-addressed `tx_id`,
   transaction-level idempotency (**P5**) cannot be enforced.
- **(a)** DERIVED (from pure handler).
- **(b)** missing (handler crashed before emit), duplicated (handler ran
  twice, two different `tx_id`s — should not happen if pure), contradicted
  (two replicas emit different bytes — purity violation),
  silent-corruption.
- **(c)** **C2** + **C3**: every event class proves $\sum_w \Delta f(w, u) = 0$ structurally; the executor rejects any pending_tx that violates conservation. **Property:** `tx_id == content_hash(moves ++ state_deltas)`; replay of the same handler on the same inputs produces the same `tx_id`.

### 5.2 Move (Atomic, with Provenance)
1. **Canonical name:** `move`
2. **Definition:** Source/destination wallets, unit, quantity, timestamp,
   source-contract reference, metadata. Defined Section 2.3.
3. **Minimum field set:** `{from: WalletId, to: WalletId, unit: UnitId,
   quantity: PositiveDecimal, timestamp: Timestamp, source: ContractRef,
   metadata: {event_desc, ext_refs: Map<String, String>}, position_coord:
   PositionCoordinateEnum (per GPM)}`.
4. **Identity:** `(tx_id, intra_tx_index)`.
5. **Provenance:** Smart-contract handler.
6. **Temporal semantics:** Immutable post-commit; corrections via
   compensating moves linked by `corrects` in metadata (Section 13.4).
7. **Failure consequences:** Negative quantity → conservation **P1** broken;
   missing source/destination → referential **P3** broken.
- **(a)** DERIVED.
- **(b)** missing, duplicated, silent-corruption (wallet id swap is the
  highest-impact silent fault).
- **(c)** **P1**: $\sum_w \Delta_q(w, u) = 0$ per move-pair semantic.
  **Single-Coordinate Move Principle** (Section 16): each move modifies
  exactly one coordinate of the position vector — for the GPM SBL model.
  **Property:** for every committed move, `from != to`, `quantity > 0`,
  `unit` resolvable, both wallets resolvable.

### 5.3 State Delta (Per-Field Mutation)
1. **Canonical name:** `state_delta`
2. **Definition:** The non-move side of a `pending_tx`: changes to
   *UnitStatus*[u] and *PositionState*[w, u] required by the lifecycle event.
3. **Minimum field set:** `{target_map: {UNIT_STATUS, POSITION_STATE},
   key: (Option<WalletId>, UnitId), field: FieldName, old_value, new_value,
   handler: HandlerName}`.
4. **Identity:** Embedded in `pending_tx`.
5. **Provenance:** Pure handler.
6. **Temporal semantics:** Atomic with the rest of the pending_tx (**C3**).
7. **Failure consequences:** Out-of-band field write breaks **C11**
   (handler-field canon).
- **(a)** DERIVED.
- **(b)** missing, contradicted (two handlers attempt same field write in
  one tx), silent-corruption.
- **(c)** **C11**: each PositionState field tagged with its unique-writer
  handler; writes by other handlers are type errors. **Property:**
  `delta.handler == FIELD_SPEC[delta.field].handler` for every applied
  delta.

### 5.4 Idempotency Key / Token
1. **Canonical name:** `idempotency_token`
2. **Definition:** Stable token per business intent: external-event id,
   workflow-signal id, trade reference. Distinct from `tx_id` (which is
   content-derived) — this is **intent-derived**.
3. **Minimum field set:** `{token, intent_ref, source_actor_lei,
   first_seen_at}`.
4. **Identity:** Token namespace + value.
5. **Provenance:** Inbound message or workflow signal.
6. **Temporal semantics:** Indefinitely retained (replay-resistant).
7. **Failure consequences:** Replay of the same external command twice →
   duplicate moves if not deduplicated.
- **(a)** DET-INPUT.
- **(b)** missing (caller didn't supply), duplicated (replay), collision
  (two distinct intents share token — silent-corruption).
- **(c)** **P5/P6** idempotency. **Property:** for each token, `count(processed_actions(token)) == 1` ever — even across worker restarts and replays.

### 5.5 Capability / Permission Check Result
1. **Canonical name:** `capability_check`
2. **Definition:** Result of a guard predicate evaluated by the handler
   before generating moves (mandate constraint, capability scope, lot-size,
   short-allowed flag, sufficient-balance-when-required).
3. **Minimum field set:** `{predicate_ref, evaluated_at, inputs_hash,
   result: {ALLOW, DENY}, reason_code: Option<DenyCodeEnum>}`.
4. **Identity:** Bound to the pending_tx that produced it.
5. **Provenance:** Pure predicate evaluation in the handler.
6. **Temporal semantics:** Ephemeral; logged for audit.
7. **Failure consequences:** Missing check → mandate breach not detected
   pre-commit; ledger may still be consistent but business intent violated.
- **(a)** DERIVED (deterministic given inputs).
- **(b)** missing, silent-corruption (predicate version drift), bypass
  (handler doesn't call it).
- **(c)** Section 6.5 (mandate constraints as guards). **Property:**
  every move is preceded by a successful capability check; deny causes
  rejection without state mutation.

---

## Category 6 — Listed-Instrument Detail (Subsumed; Retained for Phase-2 Indexing)

I argued above that this is mostly Static + Reference. The genuinely
distinct items are:

### 6.1 Contract Specification (Listed)
1. **Canonical name:** `contract_spec[mic, contract_class, expiry, ...]`
2. **Definition:** Full exchange contract specification — exchange MIC,
   underlier, contract size/multiplier, settlement style (physical / cash /
   index-settled), tick size, lot size, last-trading-day, first-notice-day
   (futures), exercise style (American / European), strike grid (for
   options), block-trade thresholds.
3. **Minimum field set:** `{mic: MIC, contract_class: String, underlier_ref,
   multiplier: Decimal, settlement_style: SettleStyleEnum, tick_size,
   lot_size, last_trade_date, first_notice_date: Option<Date>, exercise_style:
   Option<ExStyleEnum>, expiries: List<Date>, strikes: List<Decimal>}`.
4. **Identity:** Hash of the spec → derived `unit_id` for each (expiry,
   strike) instance.
5. **Provenance:** Exchange rulebook + contract listing feed.
6. **Temporal semantics:** Versioned; spec changes (e.g., E-mini ES
   multiplier change) are amendments — **C8** fungibility predicate must
   classify them.
7. **Failure consequences:** Wrong multiplier → wrong P&L magnitude (50× or
   100× error); wrong tick → orders rejected.
- **(a)** EXTERNAL-ORACLE / DET-INPUT (post-load).
- **(b)** missing, late, contradicted (vendor vs exchange), silent-
  corruption.
- **(c)** Section 7.4 ES futures example: `ac_alpha + ac_ch == 0` requires
  multiplier consistency. **Property:** for every wallet pair on a
  contract, `accumulated_cost = -signed_qty × price × multiplier` per
  trade.

### 6.2 Per-(Wallet, Contract, CCP) Binding
1. **Canonical name:** `ccp_binding`
2. **Definition:** When the same contract clears via multiple CCPs (e.g.,
   Eurodollar futures via CME and ICE), each (wallet, contract, CCP) triple
   carries its own *PositionState* row (Section 7.4 footnote).
3. **Minimum field set:** `{wallet_id, unit_id, ccp_id, exchange_id,
   member_id, position_account_type}`.
4. **Identity:** `(wallet_id, unit_id, ccp_id)`.
5. **Provenance:** Trade execution (clearing destination).
6. **Temporal semantics:** Immutable after first trade; novation between
   CCPs is a state transition.
7. **Failure consequences:** Cross-CCP netting (EMIR Art. 4) computed
   against the wrong scope.
- **(a)** DET-INPUT.
- **(b)** missing, mis-attributed.
- **(c)** Conservation holds **per CCP**: $\sum_w \texttt{ac}(w, u_{@\text{CCP}_i}) = 0$ for each CCP independently. **Property:** the regulatory aggregation is a strict superset of the per-CCP sums.

### 6.3 Settlement Cycle Convention (T+0/T+1/T+2)
1. **Canonical name:** `settlement_cycle[venue, asset_class]`
2. **Definition:** Drives the projection from trade-date moves to settlement
   instructions and the EXECUTED→INSTRUCTED→SETTLED lifecycle (Section 8.7).
3. **Minimum field set:** `{venue_mic, asset_class, t_plus_n: int,
   cutoff_time: Time, valid_from, valid_to}`.
4. **Identity:** `(venue_mic, asset_class, valid_from)`.
5. **Provenance:** Venue rulebook (US T+1 from May 2024, EU T+2).
6. **Temporal semantics:** Slowly mutable, regime change announced.
7. **Failure consequences:** Wrong settlement date → CSDR mandatory buy-in
   trigger.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late (regime-change effective date not loaded),
  contradicted.
- **(c)** **Property:** for each `SETTLEMENT` tx, `settlement_date == bday_adjust(trade_date + t_plus_n, calendar)`.

---

## Category 7 — Settlement Infrastructure (NEW — gap in floor categories)

### 7.1 Standing Settlement Instructions (SSI)
1. **Canonical name:** `ssi[counterparty_lei, currency, asset_class, t]`
2. **Definition:** Per-counterparty, per-currency, per-asset-class
   pre-agreed settlement routing. Required by `enrich(...)` step (Section 8.2).
3. **Minimum field set:** `{counterparty_lei, currency, asset_class,
   beneficiary: AccountId, intermediary: Option<AccountId>, csd_account:
   Option<CSDAccountId>, valid_from, valid_to, version}`.
4. **Identity:** `(counterparty_lei, currency, asset_class, valid_from)`.
5. **Provenance:** Bilateral counterparty exchange (CSA, master agreement).
6. **Temporal semantics:** Versioned; timed effective windows.
7. **Failure consequences:** Wrong wire routing; recipient bank rejects;
   funds suspended.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing, late (counterparty changed bank, didn't tell us),
  duplicated, contradicted, silent-corruption.
- **(c)** **Property:** for every committed `SETTLEMENT` tx, exactly one
  active SSI exists for each leg's `(counterparty_lei, currency,
  asset_class)` at `tx.settlement_date`.

### 7.2 ISO 20022 Wire Message (Outbound)
1. **Canonical name:** `iso20022_outbound[end_to_end_id]`
2. **Definition:** Generated wire message (sese.023, pacs.008, pacs.009,
   etc.) from `SettlementInstruction + enrichment`.
3. **Minimum field set:** `{message_type, end_to_end_id, tx_id, settlement_date,
   amount_or_qty, currency_or_isin, payer/payee, sender_bic,
   receiver_bic, raw_message: bytes, transmitted_at}`.
4. **Identity:** `end_to_end_id` (must match across confirmation reflows).
5. **Provenance:** Settlement-layer projection + enrichment.
6. **Temporal semantics:** Immutable post-transmission.
7. **Failure consequences:** Mis-formatted → CSD rejects; wrong
   `end_to_end_id` → reconciliation break.
- **(a)** DERIVED + EXTERNAL-ORACLE-rule-driven.
- **(b)** missing (transmission failed silently), duplicated, contradicted
  (two messages with same id but different bytes), silent-corruption.
- **(c)** **Property:** for every outbound message, `end_to_end_id ==
  derive(tx_id, leg_index)` is reproducible; ingestion of a confirmation
  with the same `end_to_end_id` deterministically updates the right tx.

### 7.3 Netting Group Membership
1. **Canonical name:** `netting_group[counterparty_lei, master_agreement_ref]`
2. **Definition:** Which trades net against each other for settlement
   purposes (Section 8.8 — netting at the settlement boundary, gross in
   the ledger).
3. **Minimum field set:** `{group_id, counterparty_lei, master_agreement_ref,
   eligible_asset_classes: Set<AssetClass>, settlement_date_basis: Enum,
   valid_from, valid_to}`.
4. **Identity:** `(group_id, valid_from)`.
5. **Provenance:** Master agreement (ISDA, GMSLA, GMRA).
6. **Temporal semantics:** Master-agreement effective period.
7. **Failure consequences:** Wrong netting set → inflated settlement
   exposure; CRR netting recognition denied.
- **(a)** DET-INPUT.
- **(b)** missing, contradicted (two MA versions valid simultaneously).
- **(c)** **Algebraic identity (Section 8.8):** for each `(security,
  counterparty, settlement_date)` group, $\sum_i \pm q_i^{\text{gross}} =
  q^{\text{net}}$. **Property:** this identity is a hard test on every
  netted instruction set.

---

## Category 8 — Calibrated Latent State (NEW — Kalman/calibration layer)

### 8.1 Kalman State Vector $x_{t|t}$
1. **Canonical name:** `calibrated_state[surface_or_curve_ref, t]`
2. **Definition:** Posterior-mean parameter vector after Kalman update —
   yield-curve zero rates, vol-surface kernel coefficients, hazard-curve
   nodes.
3. **Minimum field set:** `{surface_or_curve_ref, x: Vector, P:
   CovarianceMatrix, certified: bool, observation_window: TimeRange,
   model_version, anti_arbitrage_projection_applied: bool}`.
4. **Identity:** `(surface_or_curve_ref, t, model_version)`.
5. **Provenance:** Kalman filter (valuation §5).
6. **Temporal semantics:** Discrete update epochs; predict-update cycle
   is **stateful** — current state depends on previous state via $x_{t|t} =
   x_{t|t-1} + K_t \nu_t$.
7. **Failure consequences:** Bad calibration → bad price → bad PnL → bad
   margin → bad settlement.
- **(a)** DERIVED but **stateful** (not memoryless from the snapshot alone).
- **(b)** missing (filter didn't run), late, duplicated (split-brain
  filter replicas), contradicted (cross-asset coherence broken — valuation
  §5.8), silent-corruption (no-arbitrage projection skipped).
- **(c)** Martingale axiom A5 (calibration manifesto): $\mathbb{E}[x_t \mid
  \mathcal{I}_{t-1}] = x_{t-1}$. **Property** (innovation gating):
  $D_t^2 = \nu_t^\top S_t^{-1} \nu_t \sim \chi^2_{m_t}$ within the model.
  **Property** (admissibility): $x_{t|t}^{\text{certified}} \in \Theta_{\mathrm{AF}}$.

### 8.2 Innovation Statistics
1. **Canonical name:** `innovation_record[surface, t]`
2. **Definition:** Per-update innovation $\nu_t$, covariance $S_t$,
   Mahalanobis $D_t^2$, gating decision (accepted / down-weighted /
   rejected).
3. **Minimum field set:** `{surface_ref, t, innovation_vector, S_t,
   D_squared, gating_decision, threshold_used, rejected_observation_ids:
   List<Id>}`.
4. **Identity:** `(surface_ref, t)`.
5. **Provenance:** Kalman update step.
6. **Temporal semantics:** Append-only log; needed for forensics on
   degraded-mode calibrations.
7. **Failure consequences:** Without it, "the filter accepted a bad
   tick" is undiagnosable.
- **(a)** DERIVED.
- **(b)** missing, silent-corruption.
- **(c)** **Property:** total rejection-fraction in a window converges to
  the expected $\chi^2$-tail probability (long-run sanity).

### 8.3 No-Arbitrage Admissibility Region $\Theta_{\mathrm{AF}}$
1. **Canonical name:** `arbitrage_free_region[surface_class, t]`
2. **Definition:** The set of admissible parameter vectors satisfying
   no-arbitrage constraints (positive density, no calendar-spread
   arbitrage, non-increasing discount factors).
3. **Minimum field set:** `{surface_class, constraint_set: List<Constraint>,
   constraint_version}`.
4. **Identity:** `(surface_class, constraint_version)`.
5. **Provenance:** Theory + product-team curation.
6. **Temporal semantics:** Versioned.
7. **Failure consequences:** Pricing through arbitrage → unbounded fake PnL.
- **(a)** DET-INPUT.
- **(b)** missing, contradicted (loose vs tight constraint set), silent-
  corruption.
- **(c)** **Property:** every published `calibrated_state` has
  `certified == True` only if the post-projection vector lies in
  $\Theta_{\mathrm{AF}}$.

### 8.4 Process / Observation Noise Matrices $(Q, R_t)$
1. **Canonical name:** `noise_models[surface_or_curve_ref]`
2. **Definition:** Process noise $Q$ (governs adaptation speed) and
   observation noise $R_t$ (bid-ask-derived, staleness-inflated).
3. **Minimum field set:** `{surface_ref, Q: Matrix, R_t_construction_rule:
   Rule, version}`.
4. **Identity:** `(surface_ref, version)`.
5. **Provenance:** Calibration-team configuration.
6. **Temporal semantics:** Versioned.
7. **Failure consequences:** $Q$ too large → noise tracking; $Q$ too small
   → state stuck during regime change. $R_t$ wrong → over- or under-
   weighting of observations.
- **(a)** DET-INPUT.
- **(b)** missing, contradicted (two configurations co-resident),
  silent-corruption.
- **(c)** **Property:** $Q$ symmetric positive semi-definite; $R_t$
  symmetric positive definite for accepted observation sets.

---

## Category 9 — Orchestration State (NEW — Temporal workflow layer)

The ledger explicitly maintains "two complementary append-only records"
(Section 14.3): the move-stream **and** the workflow history. The
simulation harness must treat the second as first-class data.

### 9.1 Workflow History
1. **Canonical name:** `workflow_history[workflow_id]`
2. **Definition:** Append-only log of all activity invocations, signals,
   timer fires, and decisions for a workflow instance.
3. **Minimum field set:** `{workflow_id, history: List<HistoryEvent>,
   workflow_type, started_at, latest_event_id}`.
4. **Identity:** `workflow_id` (deterministic per unit / per per-day-cron).
5. **Provenance:** Temporal server.
6. **Temporal semantics:** Append-only; trimmed via `ContinueAsNew`
   (valuation §14.3).
7. **Failure consequences:** Workflow replay on worker restart depends on
   complete history; corruption breaks deterministic replay (analogous to
   ledger **P9** purity violation).
- **(a)** DET-INPUT (after capture).
- **(b)** missing, late, silent-corruption.
- **(c)** **Property:** workflow replay from history yields bit-identical
  decisions; non-determinism is detected as a workflow-task failure.

### 9.2 Durable Timer State
1. **Canonical name:** `durable_timer[workflow_id, timer_id]`
2. **Definition:** Persisted timer scheduled via `workflow.Sleep(until=t)`
   surviving process restarts. Section 14.1 makes this a first-class
   liveness primitive.
3. **Minimum field set:** `{workflow_id, timer_id, fire_at, status: {PENDING,
   FIRED, CANCELLED}, attempted_fires: int}`.
4. **Identity:** `(workflow_id, timer_id)`.
5. **Provenance:** Temporal cluster.
6. **Temporal semantics:** Created at workflow decision; fired exactly
   once.
7. **Failure consequences:** Lost timer → coupon never paid; double-fired
   timer → duplicate processing — but **P5** idempotency rescues it.
- **(a)** CLOCK-BOUND.
- **(b)** missing (timer lost), late (worker queue backed up), duplicated
  (double-fire), silent-corruption.
- **(c)** **Property:** for every scheduled lifecycle event date $t$,
  exactly one `FIRED` timer record exists; combined with **P6** lifecycle
  idempotency, end-to-end exactly-once.

### 9.3 Pricing-FSM State $\sigma(u)$
1. **Canonical name:** `valuation_fsm_state[unit_id]`
2. **Definition:** Current state in valuation-§4 FSM (UNPRICED, PRICING,
   PRICED, EXPLAINING, EXPLAINED, QUARANTINED, STALE, FAILED).
3. **Minimum field set:** `{unit_id, sigma: ValuationStateEnum,
   entered_at, retry_count, prev_record_ref: Option<ValRecRef>}`.
4. **Identity:** `unit_id` (one FSM per unit).
5. **Provenance:** PricingWorkflow.
6. **Temporal semantics:** Per-transition timestamped.
7. **Failure consequences:** Race between FSM and lifecycle handler →
   stale Greeks used for approximate pricing — Principle "Lifecycle-
   Before-Valuation" enforces ordering.
- **(a)** DERIVED (workflow-replayable).
- **(b)** missing, contradicted (two replicas claim different state),
  silent-corruption.
- **(c)** **Property** (T-table totality from valuation §4): every
  $(\sigma, \text{event})$ pair has exactly one outgoing transition or
  is explicitly disallowed. **Property** (T1 guard): no transition to
  PRICING unless market-data-fresh AND no pending lifecycle events.

### 9.4 Freshness Map per Workflow
1. **Canonical name:** `freshness_map[workflow_id]`
2. **Definition:** Per-workflow record of upstream-DAG-node last-fresh
   timestamps; gates entry to PRICING (T1).
3. **Minimum field set:** `{workflow_id, dependencies: Map<DepRef,
   FreshAt: Timestamp>}`.
4. **Identity:** `workflow_id`.
5. **Provenance:** Inbound signals from upstream workflows.
6. **Temporal semantics:** Continuously updated.
7. **Failure consequences:** Pricing fired on stale upstream → unexplained
   PnL.
- **(a)** DERIVED.
- **(b)** missing, late (signal arrives after workflow checked).
- **(c)** **Property:** $\forall \text{dep}, \text{freshness\_map[dep]} \ge
  t_{\text{cycle}} - \text{cadence}(\text{dep})$ before entering PRICING.

### 9.5 Retry / Backoff State
1. **Canonical name:** `retry_state[activity_invocation]`
2. **Definition:** Attempt counter, last-error class, next-attempt
   timestamp; consumed by Temporal RetryPolicy.
3. **Minimum field set:** `{invocation_id, attempt_count, last_error_class,
   next_attempt_at, max_attempts, non_retryable_errors: Set<ErrorEnum>}`.
4. **Identity:** `invocation_id`.
5. **Provenance:** Temporal worker.
6. **Temporal semantics:** Per-attempt updated.
7. **Failure consequences:** Retrying a non-retryable error (conservation
   violation) burns capacity and masks bugs.
- **(a)** DERIVED.
- **(b)** missing, contradicted.
- **(c)** **Property:** non-retryable error classes (ConservationViolation,
  ReferentialIntegrityError, IdempotencyRejection per Section 14.2.2)
  cause attempts to halt at 1.

### 9.6 Compensation / Saga State
1. **Canonical name:** `saga_state[parent_workflow_id]`
2. **Definition:** Compensating-action tracker for failed multi-step
   settlement workflows (Section 14 saga patterns).
3. **Minimum field set:** `{parent_workflow_id, completed_steps:
   List<Step>, compensation_pending: List<CompensationAction>,
   final_status}`.
4. **Identity:** `parent_workflow_id`.
5. **Provenance:** SettlementWorkflow.
6. **Temporal semantics:** Active until full completion or full
   compensation.
7. **Failure consequences:** Half-rolled-back saga → ledger has half the
   compensating moves, half not — **P2 atomic-commitment** is preserved
   per-tx but the saga-level invariant requires explicit modelling.
- **(a)** DERIVED.
- **(b)** missing, contradicted.
- **(c)** **Property:** every saga ends in either full success or full
  compensation; "half" is a detectable failure mode that triggers an
  alert.

---

## Category 10 — Generator / Type Universe (NEW — for property-based testing)

### 10.1 CDM Enum Universe
1. **Canonical name:** `cdm_enum_universe[cdm_version]`
2. **Definition:** All closed CDM enumerations (EventIntentEnum,
   OptionTypeEnum, ProductTypeEnum, PartyRoleEnum, BusinessDayConvention,
   DayCountFractionEnum, etc.) — the bounded input space for
   property-based test generators (Section 11.4).
3. **Minimum field set:** `{cdm_version: SemVer, enums: Map<EnumName,
   Set<Variant>>, valid_combinations: Map<(ProductType, EventIntent),
   bool>}`.
4. **Identity:** `cdm_version`.
5. **Provenance:** FINOS CDM repository.
6. **Temporal semantics:** Versioned; new enum values trigger updates to
   lifecycle handlers and test generators (Section 9.3).
7. **Failure consequences:** Test generator drifts from production CDM
   version → false-pass coverage; Goodhart trap if "100% coverage" is
   measured against a stale enum set.
- **(a)** EXTERNAL-ORACLE.
- **(b)** missing (new enum value not loaded), late (production handler
  ahead of test generator), contradicted, silent-corruption.
- **(c)** **Property:** for every (ProductType, EventIntent) marked valid,
  a transition exists in the lifecycle handler; for every invalid pair,
  the handler rejects (P10 — valid lifecycle transitions only). **Property**
  (completeness, Section 11.4.1): the generator covers the entire enum;
  no enum value is silently skipped.

### 10.2 Product-Specific State Schemas
1. **Canonical name:** `product_state_schema[product_class]`
2. **Definition:** Typed schema for each product family's `unit_state` /
   `position_state` (Section 7.3) — defines the legal-state space and
   serves as test-generator type.
3. **Minimum field set:** `{product_class, fields: Map<FieldName, FieldType>,
   field_writers: Map<FieldName, HandlerName>, illegal_combinations:
   List<Predicate>}`.
4. **Identity:** `product_class + schema_version`.
5. **Provenance:** Product team + correctness review.
6. **Temporal semantics:** Versioned; migration required for any change.
7. **Failure consequences:** Loose schemas allow nonsensical states (matured
   bond with pending coupons, exercised option still ACTIVE) — defeats the
   "structurally unrepresentable" guarantee.
- **(a)** DET-INPUT.
- **(b)** missing, contradicted, silent-corruption (schema migration with
  data loss).
- **(c)** **C11**: each field tagged with unique handler. **Property:**
  every reachable state in the FSM is a member of the schema; illegal
  combinations are unrepresentable.

### 10.3 Property Catalogue (P1–P10, P11–P20, P21–P23, addendum C1–C12)
1. **Canonical name:** `property_catalogue`
2. **Definition:** The full set of testable invariants — Section 11
   ten core, SBL P11–P20, obligation P21–P23, addendum C1–C12, valuation
   FSM table totality.
3. **Minimum field set:** `{property_id, statement: FormalText,
   generators: List<GeneratorRef>, postcondition: PredicateRef,
   coverage_target: Decimal}`.
4. **Identity:** `property_id`.
5. **Provenance:** Spec authors.
6. **Temporal semantics:** Versioned with the spec.
7. **Failure consequences:** Without an explicit catalogue, properties
   drift; "test count" becomes a Goodhart metric uncoupled from actual
   correctness.
- **(a)** DET-INPUT.
- **(b)** missing (property not implemented), contradicted (two
  formulations), mis-attributed.
- **(c)** **Meta-property:** every committed move stream is closed under
  every property in the catalogue; mutation-score $\geq 80\%$ overall
  per addendum §7.

---

## Category 11 — Provenance & Identity (NEW — IDs and integrity primitives)

### 11.1 Transaction ID (Content-Addressed)
1. **Canonical name:** `tx_id`
2. **Definition:** Content hash of the immutable parts of a transaction;
   used for **P5** transaction-level idempotency.
3. **Minimum field set:** `{algorithm: HashAlgEnum, value: bytes,
   inputs_canonical_form_version}`.
4. **Identity:** Itself.
5. **Provenance:** Hash function over canonicalized tx body.
6. **Temporal semantics:** Permanent.
7. **Failure consequences:** Hash collision is a probabilistic catastrophe;
   non-canonical inputs producing different hashes for the same intent
   defeats deduplication.
- **(a)** DERIVED.
- **(b)** silent-corruption (collision), contradicted (canonicalization
  bug — same intent, two hashes).
- **(c)** **P5**: ledger rejects already-committed `tx_id` re-submission.
  **Property:** canonicalization is deterministic; Section 5.1 handler
  purity → same inputs → same `tx_id`.

### 11.2 Hash Chain (Move-Stream Integrity)
1. **Canonical name:** `hash_chain_link[move_or_tx_index]`
2. **Definition:** Per-entry SHA over `(prev_hash, this_entry_canonical)`
   providing tamper-evidence for the immutable move stream
   (Section 13.4 + Invariant 4).
3. **Minimum field set:** `{prev_hash, this_hash, entry_canonical_hash,
   chain_position}`.
4. **Identity:** `chain_position`.
5. **Provenance:** Append handler.
6. **Temporal semantics:** Cumulative; integrity verified by full re-hash.
7. **Failure consequences:** Without it, the move-stream's "immutability"
   is unenforced.
- **(a)** DERIVED.
- **(b)** missing (chain broken), silent-corruption (single-entry
  rewrite).
- **(c)** **Property** (Section 13.4): `hash_chain_link[k].this_hash ==
  H(hash_chain_link[k-1].this_hash || entry[k])` for all $k$.

### 11.3 EndToEndId / TxId / ISO 20022 Identifiers
1. **Canonical name:** `wire_identifier`
2. **Definition:** ISO 20022 message-level identifiers binding outbound
   instructions to inbound confirmations (Section 8.3).
3. **Minimum field set:** `{end_to_end_id, instr_id, uetr, tx_id_ref}`.
4. **Identity:** `(message_type, end_to_end_id)`.
5. **Provenance:** Generated at message build (deterministically from
   `tx_id`).
6. **Temporal semantics:** Persistent for confirmation matching.
7. **Failure consequences:** Lost matching → reconciliation break.
- **(a)** DERIVED.
- **(b)** missing, duplicated (re-used across messages — silent-corruption),
  contradicted.
- **(c)** **Property:** `end_to_end_id` is unique per outbound message;
  inbound confirmation's `end_to_end_id` resolves to exactly one outbound.

### 11.4 UTI / USI / Regulatory Identifiers
1. **Canonical name:** `regulatory_id`
2. **Definition:** EMIR Refit UTI, CFTC USI, MiFIR transaction reference;
   each must be generated under the version of the rule active at trade
   time and linked to the underlying `tx_id` and `cdm_business_event_payload`.
3. **Minimum field set:** `{uti, usi, mifir_tx_ref, generation_rule_version,
   linked_tx_id}`.
4. **Identity:** UTI/USI value.
5. **Provenance:** Generation rule (CPMI-IOSCO).
6. **Temporal semantics:** Permanent.
7. **Failure consequences:** Reporting break; double-counted trades across
   regimes; UTI re-use across counterparties.
- **(a)** DERIVED + EXTERNAL-ORACLE-rule-driven.
- **(b)** missing, duplicated (UTI collision across counterparties),
  contradicted (counterparty generated different UTI), silent-corruption.
- **(c)** **Property:** UTI uniqueness in the move stream; cross-
  counterparty UTI agreement is a separate boundary-reconciliation.

### 11.5 Correction Chain (`corrects` Back-Reference)
1. **Canonical name:** `correction_link`
2. **Definition:** First-class metadata field linking a compensating
   transaction to the original it corrects (Section 13.4).
3. **Minimum field set:** `{compensating_tx_id, original_tx_id,
   correction_reason: ReasonEnum, evidence_ref: DocRef, supersedes:
   Option<correction_id>}`.
4. **Identity:** Composite of (`compensating_tx_id`, `original_tx_id`).
5. **Provenance:** CORRECTION-tagged transaction emission.
6. **Temporal semantics:** Permanent; chain may extend.
7. **Failure consequences:** Without `corrects`, replay cannot distinguish
   "real economic event" from "error correction" — opens a Goodhart trap
   where errors are silently absorbed.
- **(a)** DET-INPUT.
- **(b)** missing (raw move emitted without `corrects`), contradicted,
  silent-corruption.
- **(c)** **Property:** for every CORRECTION-typed transaction, its
  `original_tx_id` resolves to a committed transaction; correction
  chains are acyclic; replay distinguishes economic events from
  corrections.

---

## Cross-Cutting Determinism Audit

The following determinism boundaries are present across the categories
above and **must be injectable** in a deterministic-simulation harness
(Principle 1, my review framework):

| Boundary | Categories | Injection point |
|----------|-----------|-----------------|
| Wall-clock time | 3, 7, 9 | `Clock` interface; Temporal `workflow.Now()` |
| Random seeds (MC pricers) | 5, 8 | `seed = hash(market_data_snap, unit_id)` (valuation §10.4) |
| External feeds (price, FX, vol) | 3 | `MarketSnapshot` versioned bundle |
| External oracles (corp action, credit, sanctions) | 4 | Oracle adapter with synonym mapping |
| Reference data (LEI, ISIN, calendar) | 2 | Reference adapter, content-hashed at read |
| Settlement infrastructure (SSI, ISO 20022 in/out) | 7 | Boundary-mocked enrichment service |
| Calibration filter state | 8 | `calibrated_state[..., t]` content-addressed checkpoint |
| Workflow scheduling | 9 | Temporal test harness with virtual clock |
| CDM enum universe | 10 | Pinned `cdm_version` per test run |
| Hash algorithms / IDs | 11 | Algorithm-stable canonicalization |

Anything outside this list reaching a handler is a **non-deterministic
boundary I have failed to enumerate** — Phase-2 must close any gap.

---

## Summary Table — Counts Per Category

| # | Category | Items | Net new (vs floor) |
|---|----------|------:|-------------------:|
| 1 | Static (per-unit immutable) | 5 | 0 |
| 2 | Reference (cross-unit master) | 10 | 0 |
| 3 | Market (raw observables) | 7 | 0 |
| 4 | Oracle (non-pricing externalities) | 6 | 0 |
| 5 | Smart-contract execution | 5 | 0 |
| 6 | Listed-instrument detail | 3 | 0 |
| 7 | **Settlement infrastructure** (ADDED) | 3 | +3 |
| 8 | **Calibrated latent state** (ADDED) | 4 | +4 |
| 9 | **Orchestration state** (ADDED) | 6 | +6 |
| 10 | **Generator / type universe** (ADDED) | 3 | +3 |
| 11 | **Provenance & identity** (ADDED) | 5 | +5 |
| **Total** | | **57** | **+21** |

---

## Disagreements with the Floor Categorisation

1. **"Static" and "Reference" are not orthogonal.** Per StatesHome, terms
   (Static) collapse into ProductTerms, but the Reference-layer items
   (LEI, ISIN, calendars) are cross-unit shared masters. The split survives
   only as an indexing convenience.
2. **"Listed-instrument detail" is overwhelmingly subsumed** by Static +
   Reference. Only the contract-spec hash, the per-(wallet, contract, CCP)
   binding, and the settlement-cycle convention are genuinely listed-only.
3. **Settlement infrastructure is missing** as a floor category despite
   driving every wire message.
4. **Calibrated latent state is missing** as a floor category despite
   being the primary input to every pricing handler.
5. **Orchestration state is missing** as a floor category despite the
   ledger document explicitly defining "two complementary audit trails."
6. **Generators / type universe is missing** as a floor category despite
   being the bounded input space of the entire property-based test
   apparatus.
7. **Provenance & identity is missing** as a floor category despite
   driving idempotency (P5) and tamper-evidence (Invariant 4).

If Phase 2 retains only six floor categories, **at minimum** Settlement
Infrastructure (7) and Provenance & Identity (11) must be added — without
them, no deterministic-simulation harness can close the loop on settlement
or detect identifier-collision faults.

---

## End-of-Phase Note

This enumeration is independent of any specific storage mapping. The
StatesHome ruling decides where *PositionState* / *UnitStatus* /
*ProductTerms* live; this enumeration says *what data the system needs*,
in what determinism class, with what fault catalogue, and what consistency
law each datum must carry forward. Phase 2 will reconcile this list
against the panel members' enumerations and the StatesHome 3-map schema.

— Correctness Architect, Phase 1 (independent enumeration).
