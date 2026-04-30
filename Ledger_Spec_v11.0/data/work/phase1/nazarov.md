# Phase 1 Data Enumeration — NAZAROV (Data Layer Architect)

**Stance.** I hold the boundary. Every datum the Ledger framework consumes from outside its closed system must arrive with a verifiable signature, a timestamp, a named source, a freshness contract, an aggregation rule (where multi-source), a fallback chain, and a recorded as-traversed history. This document enumerates every data category the framework requires, classified by attestation discipline, freshness regime, and consequence-of-error class.

**Scope of this enumeration.** I enumerate data classes that cross the closed-system boundary, that the framework's pure functions consume as inputs, and that the framework's deterministic outputs depend on. I include both classical "feeds" and one class the brief's six floors do not name: external lifecycle observations and confirmation messages. I argue for floor restructuring at the end.

**Convention.** Each item carries the seven mandatory fields plus four NAZAROV-specific fields: (a) attestation requirement, (b) dispute-resolution posture, (c) point-in-time reconstructability, (d) failure-mode-when-absent. Thresholds expressed as `TBD<owner>` are placeholders requiring resolution by the named owner.

---

## Floor 1 — Static Data

Static data: data that does not change in normal operation; if it changes, the change is a governed amendment with full audit. Within the framework, ProductTerms (the immutable versioned half of unit identity, per the StatesHome three-map ruling) lives here, as does most legal-agreement metadata, identifier tables, and conventions.

### 1.1 Legal Entity Identifiers (LEIs) and Party Reference Data

1. **Canonical name.** `Party.LEI` — Legal Entity Identifier per ISO 17442.
2. **Definition.** A 20-character alphanumeric code uniquely identifying a legally distinct entity participating in financial transactions, issued by a Local Operating Unit (LOU) accredited by the Global LEI Foundation (GLEIF).
3. **Minimum field set.** `lei_code` (string, 20 chars, ISO 17442 conformant), `legal_name`, `entity_status` (ACTIVE | LAPSED | RETIRED | MERGED | DUPLICATE | ANNULLED | PENDING_VALIDATION | PENDING_TRANSFER | PENDING_ARCHIVAL), `legal_jurisdiction` (ISO 3166), `entity_category`, `registration_status`, `next_renewal_date`, `parent_lei` (Level 2), `gleif_last_update_date`, `lou_issuer_code`, `validation_authority`.
4. **Identity.** The LEI itself is the canonical identifier; uniqueness and global registration are the GLEIF guarantee.
5. **Provenance.** GLEIF Concatenated File (the global aggregated download) or a specific LOU's authoritative feed; ultimately rooted at `https://www.gleif.org/`. Within the system, the LEI Reference Service is the named ingestion gateway.
6. **Temporal semantics.** LEIs have validity windows (issue_date, expiry_date, status changes). The annual renewal status (ACTIVE vs LAPSED) is itself temporal data — a LEI's state at time `t` is not derivable from the LEI string alone.
7. **Failure consequences.** A move keyed to an unknown or LAPSED LEI risks (i) regulatory rejection (EMIR, MiFIR, SFTR all require valid LEIs), (ii) settlement instruction generation against a counterparty whose status has changed, (iii) sanctions screening miss if entity has been merged into a sanctioned successor.

(a) **Attestation requirement.** Two acceptable forms: (i) the GLEIF root-signed Concatenated File checksum and signature; (ii) a LOU's signed feed for LEIs the LOU itself issued. Both ingestion paths must verify the cryptographic root before acceptance. Bare HTTPS GETs of the GLEIF JSON without signature validation MUST NOT be admitted.

(b) **Dispute-resolution posture.** GLEIF is the system of record; within a dispute, the GLEIF Concatenated File of record at time `t` (with its signature) is dispositive for ledger-internal purposes. For legal disputes external to the framework, jurisdictional registries may override.

(c) **Point-in-time reconstructability.** REQUIRED. The system MUST snapshot daily GLEIF state with its signature and content-hash, retain indefinitely, and expose `lei_status_as_of(lei, t)`. Vendor restatements (LOUs occasionally re-state historical status) MUST create a new snapshot version, never overwrite.

(d) **Failure-mode-when-absent.** The Unit Store registration of any unit referencing this LEI as counterparty MUST be rejected. Existing positions with this LEI MUST not be invalidated (positions exist), but new moves to/from a wallet keyed to an unresolvable LEI MUST be blocked pending resolution. This is a hard-stop boundary check, not a graceful degradation.

---

### 1.2 Instrument Static Data — Securities (ISIN-Bearing)

1. **Canonical name.** `InstrumentMaster.SecurityRecord`.
2. **Definition.** The static contractual-and-identification record for a security identified by ISIN: equity, bond, ETF, listed structured note, or any other CSD-eligible instrument with a permanent identifier.
3. **Minimum field set.** `isin` (ISO 6166), `cusip` (where applicable), `sedol` (where applicable), `figi` (Bloomberg Open FIGI), `ticker`, `mic_primary_listing` (ISO 10383), `mic_other_listings`, `issuer_lei`, `issuer_country` (ISO 3166), `instrument_classification` (ISO 10962 CFI), `currency` (ISO 4217), `issuance_date`, `maturity_date` (bonds), `coupon_rate` (bonds), `coupon_frequency` (bonds), `day_count_convention` (bonds), `face_value`, `par_value`, `lot_size`, `tick_size`, `settlement_currency`, `settlement_cycle` (T+1, T+2, ...), `csd_primary` (DTC, Euroclear, Clearstream, ...), `csd_account_template`, `dividend_policy_type`, `voting_rights`, `tax_classification`.
4. **Identity.** ISIN is canonical; FIGI is the cross-vendor join key when ISIN is missing; CFI gives the type. The Ledger Unit Store derives `unit_id` deterministically from these (per §3.4 of the Ledger spec).
5. **Provenance.** Issuer-direct (rare), national numbering agency (ANNA / ANNA Service Bureau, the ISIN root), CSD reference data feeds (DTC, Euroclear, Clearstream), commercial vendors (Bloomberg, Refinitiv, S&P CapIQ, MarkitSERV), and exchange listing feeds. Each source has different latency and authority.
6. **Temporal semantics.** Static fields are immutable from issuance, but corporate actions, ratings changes, and regulatory reclassifications cause amendments. The amendment two-track applies (StatesHome C8): fungibility-preserving changes append a TermsVersion; fungibility-breaking changes allocate a fresh `unit_id` with a `SupersededBy` link. There is also a knowledge-time vs effective-time distinction: an amendment may be announced today, effective in three weeks, and only attested-arriving in the system tomorrow — three timestamps per record.
7. **Failure consequences.** Wrong static data corrupts every downstream computation: settlement instructions go to wrong CSD; coupon dates fire wrong; corporate actions misallocate; PnL is wrong. Wrong CFI classification causes wrong regulatory treatment.

(a) **Attestation requirement.** Per source, signed bundle: ANNA root for ISIN allocations; CSD signature for CSD-eligibility and account templates; issuer prospectus hash (where digitised) for terms. Multi-source aggregation: at minimum, ISIN must be confirmed by ANNA; CSD-eligibility must be confirmed by the named CSD; issuer-LEI cross-reference must be GLEIF-consistent. Discrepancies between sources flagged, never silently picked.

(b) **Dispute-resolution posture.** For bond terms, the issuer's published prospectus / final terms is dispositive (this is a legal document, not a data feed; the ledger consumes a prospectus *hash* as part of provenance). For settlement details, the CSD record wins. For ratings and classifications that vary by vendor (e.g., MSCI vs FTSE GICS classification), the firm's chosen authoritative vendor is named in the trust assumption registry; conflicts produce a flagged record, never a silent pick.

(c) **Point-in-time reconstructability.** REQUIRED. The Unit Store §3 already mandates per-version retention via TermsVersion. Knowledge-time attestation must accompany each version: `(unit_id, terms_version, knowledge_time, effective_time, source_signature_set)`.

(d) **Failure-mode-when-absent.** Unit Store registration MUST fail (per Ledger §3.5: registration validation includes term consistency). For an in-flight trade against an unknown ISIN, the trade booking MUST be blocked at the contract pre-condition, not silently rejected by the executor (this is a smart-contract author obligation per the ledger-spec). Late-arriving static data for an instrument already traded is a CORRECTION transaction with full audit.

---

### 1.3 Listed Derivative Contract Specifications

1. **Canonical name.** `InstrumentMaster.ListedDerivativeSpec`.
2. **Definition.** The static contract specification of an exchange-listed derivative — futures, listed options, listed swaps — defined by exchange product rules.
3. **Minimum field set.** `exchange_mic`, `product_code` (e.g., ES for E-mini S&P), `underlier_id` (FIGI / ISIN of the underlying or index code), `contract_type` (FUTURE | OPTION_CALL | OPTION_PUT | SWAP | ...), `strike` (options), `expiry_date`, `last_trading_date`, `delivery_date`, `multiplier`, `tick_size`, `tick_value`, `currency`, `settlement_type` (CASH | PHYSICAL), `settlement_method`, `clearinghouse_lei`, `daily_settlement_calc_method`, `final_settlement_calc_method`, `position_limit`, `block_minimum`, `option_exercise_style` (AMERICAN | EUROPEAN | BERMUDAN).
4. **Identity.** The derived `unit_id` is a hash of the canonicalised contract spec (per Ledger §3.4); the exchange product code + expiry uniquely names the listing.
5. **Provenance.** The exchange itself is the only authoritative source for its own product specifications. Derivatives clearing organisations (CME Clearing, ICE Clear, LCH, Eurex Clearing) confirm clearing terms.
6. **Temporal semantics.** Specifications are issued with the listing of each contract and are immutable for that specific contract. The product *family* (e.g., E-mini S&P) has rules that change over time and apply to newly listed contracts. Mid-life amendments to active contracts are rare but occur (CCP rule changes, regulatory mandates).
7. **Failure consequences.** Wrong multiplier means every variation-margin calculation for that contract is wrong by a constant factor — a uniform error invisible to internal cross-checks. Wrong settlement method corrupts physical-delivery vs cash-settlement logic at expiry.

(a) **Attestation requirement.** Exchange-signed reference data feed (most major exchanges publish signed FIX-MD or similar); CCP cross-confirmation for clearing terms. Bare PDF-rule-book scraping is prohibited.

(b) **Dispute-resolution posture.** Exchange product-rule document hash is dispositive within ledger scope. CCP rule book governs the clearing layer.

(c) **Point-in-time reconstructability.** REQUIRED. Each listed contract's spec at the time of any move against it MUST be recoverable as `(unit_id, spec_version, exchange_signature, ingestion_time)`. The futures variation-margin calculation in v10.3 §7.5 critically depends on `multiplier` being immutable per `unit_id`; any history must be reconstructable from ProductTerms.

(d) **Failure-mode-when-absent.** Block Unit Store registration. For mid-life amendment (e.g., CME re-rules a holiday calendar), apply the StatesHome C8 amendment two-track: fungibility-preserving (e.g., calendar tweak) appends a TermsVersion; fungibility-breaking is rare and triggers a fresh `unit_id` with `SupersededBy`.

---

### 1.4 OTC Trade Static Data — CDM Trade Object (with Collateral)

1. **Canonical name.** `CDMTrade.StaticTerms` — the immutable CDM `Trade` object including `EconomicTerms`, `Counterparty`, `CollateralProvisions`.
2. **Definition.** Per Ledger §3.2, the unit identity of an OTC instrument is the full CDM `Trade` object (counterparty, payouts, schedules, settlement terms, governing CSA). Two trades with identical payoffs but different CSAs are distinct units.
3. **Minimum field set.** Full CDM `Trade` including `tradeIdentifier` (UTI / USI), `tradeDate`, `parties` (each with LEI), `tradableProduct.product`, `tradableProduct.priceQuantity`, `executionDetails` (venue MIC, executing broker, clearing status), `collateral.collateralProvisions` (CSA reference, threshold, MTA, eligible collateral schedule, governing law), `documentation` (master agreement reference and version), `cdm_version`.
4. **Identity.** UTI is the global identifier per ISO 23897; the system's `unit_id` is a deterministic hash of the canonicalised CDM `Trade` (Ledger §3.4) and is identity-equivalent to the trade's UTI in ledger scope.
5. **Provenance.** The trade itself is the artefact, signed by both counterparties (or by their executing systems on their behalf), confirmed by the platform of execution (SEF/MTF/OTF) or by a confirmation platform (MarkitSERV, ICE Link, DTCC Trade Information Warehouse, post-trade matching engines), and ultimately by the trade repository (for reportable trades) and the CCP (for cleared trades).
6. **Temporal semantics.** Execution time, knowledge time (when our system saw it), and effective economic time may all differ. Pre-allocation block trades have an additional allocation timestamp. Confirmation arrival is a separate event from execution.
7. **Failure consequences.** Wrong counterparty LEI in the CSA reference means wrong margin calculation portfolio. Wrong collateral schedule means wrong eligibility checks (substitution demands fire wrong, IBP-170). Wrong governing law / jurisdiction means wrong close-out behaviour on default.

(a) **Attestation requirement.** Both-counterparty confirmation: dual-signed CDM `Trade` (each counterparty's system signs the canonical trade payload), or single-sign-by-confirmation-platform with attestation chain back to both LEIs. The synonym mapping from FpML / FIX to CDM is itself part of the attestation surface (Ledger §10): the mapping must be deterministic, version-pinned, and total over its declared input domain. Mapping failures MUST be explicit failure events, never silent defaults — this is a NAZAROV-required hard rule.

(b) **Dispute-resolution posture.** The dual-confirmed CDM `Trade` is dispositive within ledger scope. For external regulatory disputes, the trade-repository record (DTCC TIW, Tabb Forum) is the regulator's reference. For legal disputes, the underlying ISDA Master + CSA + confirmation chain is the legal artefact (the framework consumes its hash).

(c) **Point-in-time reconstructability.** REQUIRED — and given particular weight by the Ledger §11 immutability invariant (P6) and the StatesHome C6 (ProductTerms versioned append-only). The CDM `BusinessEvent` event log payload (Ledger §10.4) preserves the full trade record. Synonym-mapping version MUST be recorded with each ingested event so replays are bit-identical (Ledger §10.3).

(d) **Failure-mode-when-absent.** Trade booking blocks at smart-contract pre-condition. There is no "best-effort" booking of an unconfirmed OTC trade — confirmation is the gate. Pending-confirmation trades may sit in a quarantine queue with explicit STATE = PENDING_CONFIRMATION, but no moves are emitted.

---

### 1.5 Calendars, Day-Count Conventions, and Business-Day Adjustments

1. **Canonical name.** `Calendar.HolidaySchedule` and `DayCount.ConventionTable`.
2. **Definition.** Holiday calendars per jurisdiction / market venue, business-day convention rules, and day-count fraction conventions (ACT/360, ACT/365, 30/360, ACT/ACT, ...).
3. **Minimum field set.** Calendar: `calendar_id` (e.g., USNY, GBLO, EUTA, CME holidays, NYSE holidays), `valid_from`, `valid_to`, `holiday_dates[]`, `partial_holidays[]` (early closes), `source_authority`. Conventions: `convention_code`, `definition_reference` (ISDA Definitions §, FpML enum), `algorithm_pseudocode_hash`.
8. **Identity.** Calendar codes follow industry conventions (FpML `BusinessCenterEnum`).
9. **Provenance.** Exchanges (NYSE, CME, LSE, ICE) publish their own; central banks publish national settlement calendars; ISDA publishes the consolidated FpML business-centre table. The framework should consume signed exchange / central-bank feeds where available, not scraped HTML.
10. **Temporal semantics.** Calendars are forward-published (typically a year out, sometimes more) with occasional in-year amendments (added unanticipated closures: e.g., national mourning, severe weather, COVID closures). Past calendars are stable; forward calendars are not.
11. **Failure consequences.** Wrong calendar means wrong reset date, wrong settlement date, wrong business-day-adjusted coupon date, wrong notional accrual period — silent corruption of every IRS, every FRA, every bond accrual, every futures settlement.

(a) **Attestation requirement.** Source-authority signed feed where available; otherwise, the firm's named calendar provider (commercial: Refinitiv, ISDA, Bloomberg) under a documented trust assumption. Day-count algorithms MUST be implemented from the ISDA-published reference (or the FpML enum) and the implementation hash recorded with each computation.

(b) **Dispute-resolution posture.** Exchange or central-bank publication is dispositive for that calendar. For day-count, ISDA Definitions are dispositive; in case of confirmation-document override (e.g., a specific trade names a non-standard convention), the trade confirmation governs.

(c) **Point-in-time reconstructability.** REQUIRED. Each calendar version (with its valid window) and each day-count algorithm version MUST be recoverable. A coupon paid in 2024 under day-count v3.1 must replay in 2026 under v3.1, not under v3.2 even if v3.2 is "more correct". This is the bitemporal property the Ledger Open Problem section names.

(d) **Failure-mode-when-absent.** Smart contracts that schedule cash flows MUST fail at registration if their referenced calendar is not present. There is no default calendar.

---

### 1.6 Master Agreement and Legal Document Metadata

1. **Canonical name.** `MasterAgreement.Reference` (ISDA Master, GMSLA, GMRA, etc.).
2. **Definition.** Metadata about the legal master agreement governing a bilateral relationship: type, version, governing law, schedule terms (CSA / Annex), and the document hash.
3. **Minimum field set.** `agreement_type` (ISDA_MASTER_2002, GMSLA_2010, GMSLA_2018, GMRA_2011, ...), `parties` (two LEIs, with role), `effective_date`, `governing_law` (ISO 3166), `jurisdiction_of_disputes`, `schedule_summary` (key thresholds, MTA, eligible collateral schedule reference), `csa_reference`, `document_hash` (SHA-256 of the executed PDF or CDM `LegalAgreement` object), `executed_signatures` (each party's authorised signatory), `archived_location`, `cdm_legal_agreement_ref`.
4. **Identity.** A composite key of `(agreement_type, parties, effective_date)` — within ledger scope, agreement is the granularity for CSA portfolios.
5. **Provenance.** The agreement is a legal artefact between the two counterparties; the framework consumes its existence and hash. The system of record is typically a contracts management system (Icertis, DocuSign CLM) or, increasingly, ISDA Create.
6. **Temporal semantics.** Agreements are amended over time (CSA amendments, Schedule changes); each amendment carries its own effective date and document hash.
7. **Failure consequences.** Wrong CSA reference on a trade routes it to the wrong margin pool; wrong governing law materially alters close-out outcome on default; wrong threshold or MTA causes wrong margin calls.

(a) **Attestation requirement.** Either ISDA Create signed-document export or contracts-management-system signed export, with a verifiable hash to the executed document. Bare "we have a Master with them" claims without document hash MUST NOT be admitted.

(b) **Dispute-resolution posture.** The executed document (with both counterparties' signatures) is the legal artefact and dispositive in any legal dispute. Within ledger scope, the document hash is the verifiable reference.

(c) **Point-in-time reconstructability.** REQUIRED. The CSA in force at time `t` for a given counterparty pair must be recoverable, including its amendment chain.

(d) **Failure-mode-when-absent.** OTC trade registration that depends on a Master/CSA reference MUST be blocked. There is no "use the default ISDA Master" — explicit Master-attribution is mandatory.

---

### 1.7 Tokenised Asset Identifiers and Backing Attestations

1. **Canonical name.** `TokenisedAsset.Reference`.
2. **Definition.** The cross-domain identifier and backing attestation for a tokenised security (per Ledger §10.6 and Open Problem §17): chain ID, contract address, plus either a custodial-backing record or an on-chain mirror commitment.
3. **Minimum field set.** `chain_id` (EIP-155 or non-EVM equivalent), `contract_address`, `token_standard` (ERC-20 / ERC-1400 / SPL / ...), `underlying_isin` (where backed), `backing_model` (CUSTODIAL_MIRROR | ON_CHAIN_NATIVE | SYNTHETIC), `custodian_lei` (where backed), `backing_account_reference`, `backing_attestation_signature`, `proof_of_reserves_link`, `attestation_frequency`.
4. **Identity.** `(chain_id, contract_address)` is canonical on-chain; `underlying_isin` joins to the off-chain reference data.
5. **Provenance.** The chain itself (signed blocks) for on-chain identity; the custodian for backing attestations; an attestor (e.g., a Big-4 audit firm or a programmatic proof-of-reserves protocol) for periodic backing confirmations.
6. **Temporal semantics.** On-chain state has a per-block freshness contract (≤ N blocks behind tip). Backing attestations have their own (typically daily or per-event) cadence. The relationship between the two is itself temporal.
7. **Failure consequences.** Untracked backing breaks → undetected double-counting (Ledger §10.6 explicitly identifies this as the central tokenisation risk). Stale on-chain state causes incorrect ownership reads. Cross-chain bridges introduce a "which chain is canonical" attestation question.

(a) **Attestation requirement.** Two-source minimum: (i) on-chain block-signature verification (a light client or a signed RPC attestation from a trusted node); (ii) custodian's backing-statement signature for the period covering the read. For programmatic proof-of-reserves (e.g., Merkle-tree-published ledger), the verification is on-chain and is acceptable.

(b) **Dispute-resolution posture.** For on-chain ownership, the chain (with finality threshold) is dispositive. For backing, the custodian's signed attestation governs; if it conflicts with on-chain, the custodian-is-flat principle (Ledger §10.6.4) determines which side carries the imbalance.

(c) **Point-in-time reconstructability.** REQUIRED. Block height / block hash anchored to wall time must be recorded. Attestation chains must be retained with their hash.

(d) **Failure-mode-when-absent.** No tokenised asset MAY enter the unit universe without a documented backing model. Open positions in a tokenised asset whose backing attestation has not arrived in window MUST flag the asset's `UnitStatus` to a quarantine value; trading against it MUST be blocked.

---

## Floor 2 — Reference Data

Reference data: data that changes (unlike static), is not market-priced, and is consumed as a published authoritative table or feed. This floor overlaps Floor 1 in practice — the ledger spec uses "reference data" in §3 to mean the Tier 1 of the Unit Store. I treat Floor 1 as the slow-moving record-of-record and Floor 2 as authoritative tables with regular updates.

### 2.1 Sanctions and Watch Lists

1. **Canonical name.** `Compliance.SanctionsList`.
2. **Definition.** The aggregated sanctions, embargo, and watch lists from official authorities (OFAC SDN, EU Consolidated Financial Sanctions, UK OFSI, UN Security Council Consolidated List, jurisdiction-specific lists) and any internal restricted-counterparty lists.
3. **Minimum field set.** `list_authority`, `entry_id`, `entry_type` (SDN_INDIVIDUAL | SDN_ENTITY | VESSEL | AIRCRAFT | ...), `names[]` (with aliases), `lei_match_candidates[]`, `country_of_residence`, `programs[]`, `effective_from`, `effective_to`, `source_publication_date`, `source_signature`.
4. **Identity.** Authority + entry_id is canonical; name-matching to LEIs / counterparties is a fuzzy-match operation downstream.
5. **Provenance.** OFAC, OFSI, EU, UN, MAS, etc. publish authoritative feeds; commercial aggregators (Refinitiv World-Check, Dow Jones Risk & Compliance) provide cleansed and matched feeds.
6. **Temporal semantics.** Updates are continuous and event-driven (a designation can be made at any time and is immediately effective). Knowledge-time vs effective-time matters: a 09:00 designation seen by us at 11:00 — what state was the system in between?
7. **Failure consequences.** Trading or settling with a sanctioned entity is a regulatory offence with criminal exposure for individuals. Latency in detection (knowledge-time gap) is itself a regulatory finding.

(a) **Attestation requirement.** Authority-signed feed where the authority publishes one (OFAC offers signed feeds); commercial-aggregator signed bundle otherwise, with a documented trust assumption naming the aggregator and the SLA. Multi-source aggregation: any authority match flags the counterparty; aggregator-only matches require an additional confirmation step before action. NEVER silent fallback.

(b) **Dispute-resolution posture.** The original authority's published designation is dispositive. Aggregator misses are operational risk borne by the firm; aggregator false positives can be over-ridden after manual verification, with the verification recorded.

(c) **Point-in-time reconstructability.** REQUIRED. The sanctions state at time `t` (what was published, what was known to us) MUST be recoverable for audit and for litigation defence. Both authority publication time and our knowledge time must be retained.

(d) **Failure-mode-when-absent.** The system MUST default to FAIL-CLOSED on sanctions data unavailability: if the latest authority feed has not arrived within `TBD<Compliance>` (typical: 1 hour), new bookings against any non-internal counterparty MUST be blocked. This is one of the few areas where strict fail-closed is mandatory — fail-open is a regulatory finding.

---

### 2.2 Tax and Withholding Reference Data

1. **Canonical name.** `Tax.WithholdingTable`.
2. **Definition.** Tax treaty rates, withholding-tax schedules, beneficial-owner classifications (W-8BEN, W-8BEN-E, W-9, CRS), and FATCA / CRS reportable-jurisdiction tables.
3. **Minimum field set.** `country_of_source`, `country_of_recipient`, `instrument_class`, `treaty_rate`, `default_withholding_rate`, `beneficial_owner_classification`, `treaty_effective_from`, `treaty_effective_to`, `documentation_required[]`, `irs_or_local_authority_reference`.
4. **Identity.** Composite key of (source country, recipient country, instrument class, effective date).
5. **Provenance.** Tax authorities (IRS, HMRC, etc.) publish treaty rates; Big-4 firms publish curated tax-data products; tax-engine vendors (Vertex, ONESOURCE) supply integrated feeds.
6. **Temporal semantics.** Treaties have effective dates; rates change with tax-year-boundaries; per-counterparty W-8 attestations expire.
7. **Failure consequences.** Wrong withholding on a coupon payment = either short-paid recipient or under-withheld (tax-authority claim against the firm). FATCA misclassification is a reporting failure.

(a) **Attestation requirement.** Authority-signed where published (rare); otherwise, named-vendor signed feed under documented trust assumption.

(b) **Dispute-resolution posture.** The relevant tax authority's published treaty / regulation is dispositive.

(c) **Point-in-time reconstructability.** REQUIRED for audit.

(d) **Failure-mode-when-absent.** Coupon / dividend payments to a counterparty whose tax classification cannot be resolved MUST be blocked at smart-contract pre-condition; fall-back to maximum withholding is acceptable only with explicit governance flag.

---

### 2.3 Corporate Actions Calendar

1. **Canonical name.** `CorporateActions.Schedule`.
2. **Definition.** Announced corporate actions (dividends, splits, spin-offs, mergers, rights issues, tender offers, name/ISIN changes) with their key dates: announcement, ex-date, record date, payment date / effective date.
3. **Minimum field set.** `event_id` (issuer-published or vendor-assigned), `instrument_isin`, `event_type` (CASH_DIVIDEND | STOCK_DIVIDEND | SPLIT | REVERSE_SPLIT | MERGER | SPIN_OFF | RIGHTS_ISSUE | TENDER | NAME_CHANGE | ...), `announcement_date`, `ex_date`, `record_date`, `payment_date`, `effective_date`, `terms` (per-share amount, ratio, new-ISIN, etc.), `currency`, `gross_amount_per_share`, `withholding_treatment`, `mandatory_or_voluntary`, `election_options[]` (voluntary), `election_deadline`, `source_authority`, `dssk_dtcc_event_id`, `version_number`.
4. **Identity.** Vendor or DTCC event ID; final authority is the issuer's own announcement.
5. **Provenance.** Issuer announcements (the legal source), exchanges' corporate actions feeds, DTCC GCAH (Global Corporate Actions Hub), Euroclear / Clearstream feeds, commercial vendors (Bloomberg DCAH, Refinitiv, ISO 20022 `seev` messages).
6. **Temporal semantics.** Corporate actions are *amended* in flight: a dividend may be announced, revised in amount, then revised in date, then finally paid. The vendor sequence number / version is critical.
7. **Failure consequences.** Wrong ex-date: wrong holders entitled. Wrong amount: wrong dividend payments fan-out. Missed amendment to a flat-share split: inflated holdings. Tax treatment errors at corporate-action time cascade to year-end reporting.

(a) **Attestation requirement.** Issuer-signed (rare) or DTCC-signed (for US) authoritative; for cross-vendor coverage, multi-source aggregation with disagreement flagging. ISO 20022 `seev.031`/`seev.035`/`seev.039` messages from authoritative sources MUST be retained with their digital signature where present.

(b) **Dispute-resolution posture.** The issuer's own announcement (with its hash and timestamp) is the legal authority. DTCC's record governs US settlement; the local CSD governs in other jurisdictions.

(c) **Point-in-time reconstructability.** REQUIRED — and particularly important. The Ledger fan-out pattern (§14.10) for corporate-action processing depends on knowing exactly which version of the event was applied. Replays must be bit-identical: vendor restatement after the fact does NOT mutate the historical event; it is a CORRECTION transaction (Ledger §11).

(d) **Failure-mode-when-absent.** A unit whose corporate action has been announced but not received in our system MUST receive a `pending_corporate_action` flag in `UnitStatus`; trading against the unit may continue, but the position is flagged for downstream reconciliation. Late-arrival of a missed corporate action is a CORRECTION transaction with full lineage.

---

### 2.4 Index Constituent Data

1. **Canonical name.** `Index.Composition`.
2. **Definition.** The constituent membership and weights of indices used as underliers (S&P 500, EuroStoxx 50, FTSE 100, etc.) and as benchmarks (managed-account benchmarks, QIS strategy benchmarks).
3. **Minimum field set.** `index_id` (e.g., SPX), `index_provider_lei`, `as_of_date`, `methodology_version`, `constituents[]` (each: ISIN, weight, free-float factor, country, sector), `divisor`, `total_market_cap`, `rebalance_dates[]`.
4. **Identity.** `(index_id, as_of_date, methodology_version)` is canonical.
5. **Provenance.** Index providers (S&P DJI, MSCI, FTSE Russell, STOXX, etc.) — each with proprietary methodologies and licensed feeds.
6. **Temporal semantics.** Indices are recomputed continuously; constituent lists are formally updated on rebalance dates; methodology versions change rarely but materially.
7. **Failure consequences.** Wrong constituent set in a QIS strategy means wrong target weights, wrong rebalance trades, wrong tracking error. Wrong divisor = wrong index level = wrong PnL on index-linked instruments.

(a) **Attestation requirement.** Index-provider signed feed; methodology document hash retained for reproducibility. License terms typically constrain redistribution but not internal use.

(b) **Dispute-resolution posture.** Index provider's published value / composition is dispositive.

(c) **Point-in-time reconstructability.** REQUIRED. As-of-date attribution is part of the ProductTerms for index-linked units.

(d) **Failure-mode-when-absent.** A QIS strategy that cannot resolve its current target index composition MUST not rebalance; existing positions are held; the rebalance event is a deferred obligation that fires on data arrival.

---

### 2.5 Day-Count and FpML Convention Tables (cross-reference)

Captured under Floor 1.5; listed here so Floor 2 is internally complete: the framework consumes these tables AS reference data, even though their values are static-by-design.

---

## Floor 3 — Market Data

Market data: continuous-time observations of market prices, rates, volatilities, and spreads. The price vector $P_t$ of the Ledger spec (§4.1, §15) is the high-level abstraction; reality is many sub-classes with different attestation, freshness, and aggregation regimes. The Kalman filter (Valuation §5) sits BETWEEN raw market data and the calibrated parameters consumed by pricing — confirming that statistical filtering is downstream of attestation, not a substitute for it.

### 3.1 Equity and ETF Price Quotes

1. **Canonical name.** `MarketData.EquityQuote`.
2. **Definition.** Bid, ask, last-trade, and reference prices for equities and ETFs from exchange and ATS sources.
3. **Minimum field set.** `instrument_id` (ISIN / FIGI), `venue_mic`, `bid_price`, `bid_size`, `ask_price`, `ask_size`, `last_trade_price`, `last_trade_size`, `last_trade_time`, `quote_time`, `condition_codes[]`, `consolidated_indicator` (CT vs SIP vs venue-direct), `currency`, `sequence_number`.
4. **Identity.** `(instrument_id, venue_mic, sequence_number)` for tick-level; `(instrument_id, as_of_time)` for snapshots.
5. **Provenance.** Direct exchange feeds (NYSE, Nasdaq, LSE Group, Euronext, Deutsche Börse, ...); SIPs / CT (Consolidated Tape providers); ATSs and dark venues; commercial aggregators (Refinitiv, Bloomberg, IEX Cloud).
6. **Temporal semantics.** Sub-millisecond exchange-time vs ingestion-time; sequence-number gaps are first-class signals; "last trade" can be hours stale outside trading hours.
7. **Failure consequences.** Mark-to-market error → wrong PnL → potentially wrong margin calls (CSA), wrong settlements (TRS), wrong VaR. A frozen feed produces stale prices that pass spot checks but fail PnL explain.

(a) **Attestation requirement.** Exchange-signed FIX-MD or PITCH where available; CT / SIP signed feed for consolidated. For commercial aggregators, the gateway signs the ingestion record under a documented trust assumption (the aggregator's TLS endpoint is NOT sufficient on its own). Multi-venue aggregation: at least two independent venues for any actively-traded equity used in mark-to-market; disagreement beyond `TBD<Risk>` bps flags an alert.

(b) **Dispute-resolution posture.** For US listed equities, the SIP / CT print is the regulatory reference at end-of-day. For PnL-explain disputes, the consolidated last-trade at the firm's chosen pricing time is dispositive.

(c) **Point-in-time reconstructability.** REQUIRED. The Valuation companion §3 already mandates that ValuationRecord carries `market_data_snap: SnapshotId` — a content-addressed hash binding the valuation to the exact data set used. The snapshot MUST be retained at content-addressed granularity sufficient to reproduce that valuation. Vendor restatements (rare for tick data, common for end-of-day reference prices) create a new snapshot version; the original is retained.

(d) **Failure-mode-when-absent.** FSM transitions T1 / T9 (entering PRICING) are guarded by "market data fresh AND all upstream DAG nodes have FIRM price". Stale data beyond cadence threshold transitions the unit to STALE; beyond `TBD<Risk> × cadence` raises an obligation-liveness alert. APPROXIMATE pricing (Taylor expansion from last FIRM) is acceptable for intraday risk monitoring but explicitly NOT for official PnL or regulatory reports (Valuation §10).

---

### 3.2 Listed-Derivative Quotes

1. **Canonical name.** `MarketData.ListedDerivativeQuote`.
2. **Definition.** Bid, ask, last-trade, and (critically) settlement prices for listed futures, listed options, and listed swaps.
3. **Minimum field set.** All of 3.1 plus `open_interest`, `daily_volume`, and per-contract `theoretical_settlement_price` and `final_settlement_price`. For options: `implied_volatility_quoted` (where the venue publishes), `underlying_price_at_quote`.
4. **Identity.** `(contract_unit_id, venue_mic, quote_time)`.
5. **Provenance.** Exchanges (CME, ICE, Eurex, OSE, HKEX, ...) directly; DCO / CCP for settlement prices.
6. **Temporal semantics.** Daily settlement price is a discrete event published per-product per-day at exchange close; it has its own publication time which differs from the close itself.
7. **Failure consequences.** Wrong daily settlement = wrong VM call (Ledger §7.5 futures lifecycle). Wrong implied vol = wrong vega = wrong vol-PnL.

(a) **Attestation requirement.** Exchange-signed daily-settlement publication is mandatory for futures variation-margin computation. The Ledger §7.5 futures lifecycle exactness proof depends on `accumulated_cost` being computed against an attested settlement price.

(b) **Dispute-resolution posture.** Exchange's published daily-settlement price is dispositive (this is the price the CCP uses for VM; any deviation in our system is our error).

(c) **Point-in-time reconstructability.** REQUIRED. UnitStatus[u].last_settlement_price (StatesHome ruling) is the per-unit shared field; its history must be reconstructable per UnitStatus version.

(d) **Failure-mode-when-absent.** No daily VM may be processed without an attested settlement price. The settle-event handler MUST block, not fall back. Late arrival is a CORRECTION transaction.

---

### 3.3 Yield Curves and Interest-Rate Inputs

1. **Canonical name.** `MarketData.RatesQuote` and `MarketData.YieldCurveInput`.
2. **Definition.** Deposit rates, futures rates (Eurodollar / SOFR futures / etc.), swap rates, OIS rates, FRA rates — the building blocks of yield curve construction.
3. **Minimum field set.** `index_code` (e.g., SOFR, ESTR, EURIBOR_3M), `tenor`, `quoted_rate`, `quote_type` (BID | ASK | MID | INDEX_FIXING), `quote_time`, `source_venue`, `currency`, `day_count_convention`, `business_day_convention`.
4. **Identity.** `(index_code, tenor, quote_time, source_venue)`.
5. **Provenance.** Reference-rate administrators (NY Fed for SOFR; ECB for ESTR; EMMI for EURIBOR; ICE Benchmark Administration for SONIA, US LIBOR retired); SEFs / MTFs for swap quotes (Tradeweb, Bloomberg SEF); inter-dealer brokers; CCPs publish their own curves used for clearing (LCH, CME).
6. **Temporal semantics.** Index fixings are once-per-day, published at a specific time per administrator (e.g., 8am ET for SOFR); intra-day swap quotes are continuous; CCP curves published at end-of-day.
7. **Failure consequences.** Wrong fixing on an IRS reset = wrong cash flow on potentially many trades. Wrong yield curve shape = wrong calibrated parameters → wrong derivative valuations across the entire IR book.

(a) **Attestation requirement.** Reference-rate administrator signed publication is mandatory for fixings (this is the input to a contractual cash flow, not a soft mark). For curve-construction inputs (deposit / futures / swap), multi-source: at least two of (CCP curve, IDB feed, SEF tape).

(b) **Dispute-resolution posture.** Administrator-published fixing is the contractual reference. Curve-construction inputs are firm choices; the firm's named primary source is the dispositive choice subject to its multi-source disagreement protocol.

(c) **Point-in-time reconstructability.** REQUIRED. The bitemporal property (Ledger Open Problem) is particularly acute here: a fixing restated by the administrator (rare but historically real) requires a `(knowledge_time, effective_time)` distinction.

(d) **Failure-mode-when-absent.** No IRS reset processes without its attested fixing; the reset event is deferred until the fixing arrives. Curve construction failures prevent FSM transitions T1 / T9 for any unit depending on that curve.

---

### 3.4 Volatility Surfaces and Volatility Quotes

1. **Canonical name.** `MarketData.VolatilityQuote`.
2. **Definition.** Implied volatility quotes per (underlier, expiry, strike) cell; ATM vol quotes; volatility surface inputs feeding the calibration node of the pricing DAG.
3. **Minimum field set.** `underlying_id`, `expiry`, `strike` (or moneyness), `implied_vol_quoted`, `bid_vol`, `ask_vol`, `quote_time`, `source_venue`, `quote_method` (LISTED_OPTION_QUOTE | OTC_BROKER_RUN | STRUCTURED_DEALER_QUOTE | CONSENSUS), `vega_normalized`.
4. **Identity.** `(underlying_id, expiry, strike, quote_time, source)`.
5. **Provenance.** Listed option markets (CBOE, CME, Eurex options, ...); OTC vol markets via dealer runs aggregated by brokers (Marex, GFI, BGC); commercial aggregators (Bloomberg OVDV, Refinitiv, Markit Totem for consensus monthly marks).
6. **Temporal semantics.** Continuous in liquid listed markets; discrete dealer-run cadence in OTC; monthly consensus snapshots.
7. **Failure consequences.** Wrong implied vol surface → wrong calibrated parameters → wrong Greek Jacobian (Valuation §4) → wrong PnL explain. Surface-level errors propagate quadratically.

(a) **Attestation requirement.** Listed option quotes attested per 3.2. OTC dealer runs require the broker's signature; multi-broker aggregation flags disagreement. Consensus marks (Markit Totem) are accepted only with the consensus-document signature and a documented trust assumption naming the consensus protocol's contributor list.

(b) **Dispute-resolution posture.** For listed options, exchange close. For OTC marks, the firm's primary OTC source under its named trust assumption — disputes route to the FVA / IPV process (independent price verification, an external attestation regime that overlays the data layer).

(c) **Point-in-time reconstructability.** REQUIRED. The Kalman filter input snapshot (§3 of Valuation) plus the calibrated state $x_{t|t}^{certified}$ MUST be retained; replay reproduces the same calibration.

(d) **Failure-mode-when-absent.** Calibration node fails → all dependent unit nodes blocked (T1/T9 guard). Last-certified-state fallback is acceptable for INDICATIVE pricing but NOT for FIRM (Valuation §11).

---

### 3.5 Credit Spreads and CDS Curves

1. **Canonical name.** `MarketData.CreditSpread`.
2. **Definition.** CDS quotes per reference entity per tenor, used for credit-curve calibration, structured-product valuation, and CVA computation.
3. **Minimum field set.** `reference_entity_lei`, `tier` (SENIOR_UNSECURED | SUBORDINATED | ...), `currency`, `tenor`, `coupon_convention` (100bp / 500bp / par-spread), `quoted_spread_or_upfront`, `recovery_assumption`, `quote_time`, `source_venue`.
4. **Identity.** `(reference_entity_lei, tier, currency, tenor, quote_time, source)`.
5. **Provenance.** ISDA-published credit events; CDS market via SEFs and IDBs; CCPs (ICE Clear Credit, LCH CDSClear) publish their own curves; commercial aggregators (Bloomberg, S&P, Markit/IHS).
6. **Temporal semantics.** Continuous in CDX/iTraxx index space; less liquid in single-name; index roll dates are discrete events.
7. **Failure consequences.** Wrong credit spread = wrong CVA / DVA / FVA = wrong fair-value adjustments and regulatory capital.

(a) **Attestation requirement.** Per 3.4 — multi-source for OTC, signed CCP curves where available.

(b) **Dispute-resolution posture.** CCP curve is the regulatory reference for cleared CDS; OTC subject to firm-named primary source.

(c) **Point-in-time reconstructability.** REQUIRED.

(d) **Failure-mode-when-absent.** CVA / DVA computation disabled; positions flagged as "missing credit input" and excluded from XVA reporting until restored.

---

### 3.6 FX Rates

1. **Canonical name.** `MarketData.FXRate`.
2. **Definition.** Spot FX rates and forward rates per currency pair, plus FX vols per pair / tenor / strike.
3. **Minimum field set.** `currency_pair` (e.g., EURUSD, USDJPY), `bid`, `ask`, `mid`, `quote_time`, `source_venue`, `tenor` (SPOT | TOM | ON | 1W | 1M | ...), `value_date`, `fixing_indicator` (e.g., WMR 4pm London).
4. **Identity.** `(currency_pair, tenor, quote_time, source_venue)`.
5. **Provenance.** EBS / Refinitiv FXAll / CLS tape / WMR (for benchmark fixings); commercial aggregators.
6. **Temporal semantics.** Continuous; benchmark fixings are discrete events (WMR 4pm London is the most consequential single fixing in global finance).
7. **Failure consequences.** Multi-currency portfolio valuation depends entirely on FX. Wrong WMR fixing on a benchmark NAV strike = wrong NAV = wrong subscriptions / redemptions.

(a) **Attestation requirement.** WMR / fixing-administrator signed publication for benchmark fixings; multi-source for continuous quotes.

(b) **Dispute-resolution posture.** WMR (London 4pm) governs benchmark NAV strikes; intra-day disputes route to firm primary source.

(c) **Point-in-time reconstructability.** REQUIRED.

(d) **Failure-mode-when-absent.** NAV strike that depends on a missing fixing MUST be deferred. Multi-currency valuation falls back to last-known-good FX with explicit STALE flagging.

---

### 3.7 Index Levels (cross-reference)

Index levels (S&P 500 level, EuroStoxx 50 level, etc.) are quoted as market data for instruments that reference them. Constituent data (Floor 2.4) and current level data (this section) are distinct categories: 2.4 governs what constitutes the index; 3.7 governs its current observed value. Per StatesHome, the level lives in `UnitStatus[u_index]`; the constituent set is part of `ProductTerms[u_index]`.

(Same attestation regime as 3.1.)

---

### 3.8 Trade-Adjacent Reference Marks (Closing Prices, NAV Strikes)

1. **Canonical name.** `MarketData.ReferenceMark`.
2. **Definition.** Officially published reference prices used for accounting marks, regulatory marks, and contractual settlement: exchange close, exchange settlement, fund NAV, benchmark fixings.
3. **Minimum field set.** As 3.1 plus `mark_type` (EXCHANGE_CLOSE | OFFICIAL_SETTLEMENT | NAV | BENCHMARK_FIXING), `mark_authority`, `publication_time`.
4. **Identity.** `(instrument_id, mark_type, valuation_date, mark_authority)`.
5. **Provenance.** Authority-direct: exchange for closes, fund administrator for NAV, benchmark administrator for fixings.
6. **Temporal semantics.** Discrete daily / per-event events with their own publication times that often lag the underlying close.
7. **Failure consequences.** Wrong NAV = wrong managed-account performance crystallisation (Ledger §6) = wrong client cash settlement = client claims and regulatory filings.

(a) **Attestation requirement.** Authority-signed publication mandatory for any mark used in contractual cash flow or regulatory report. Mid-market vendor "close" without authority signature is acceptable for indicative use only.

(b) **Dispute-resolution posture.** The named mark authority's published value is dispositive. NAV restatements are CORRECTION transactions, never silent overwrites.

(c) **Point-in-time reconstructability.** REQUIRED. The performance-amount calculation for a managed-account smart contract (Ledger §6.2) reads NAV at $t_{k-1}$ and $t_k$; both must be the marks-known-at-that-time, not their post-restatement values.

(d) **Failure-mode-when-absent.** Performance crystallisation deferred (an obligation under §14.7) until the mark arrives; if the mark fails to arrive within `TBD<FundOps>`, manual override with explicit governance flag.

---

## Floor 4 — Oracle (External Lifecycle Observations and Confirmations)

The brief names "Oracle" but does not define it; I interpret it as: data attesting to externally-observed events that drive the framework's lifecycle state machine. This is distinct from market-data observation (Floor 3) — these are discrete events whose absence would leave the system in a wrong lifecycle state.

### 4.1 Index Fixings and Reference-Rate Fixings

Captured under 3.3 (rate fixings) and 3.7 (index levels) since they are continuously published and discrete events; oracle-class attestation is what makes them admissible.

### 4.2 Barrier-Breach Observations

1. **Canonical name.** `Oracle.BarrierObservation`.
2. **Definition.** A signed assertion that, at a specified observation time, the observed value of a contractual barrier was breached / not breached. Drives knock-in / knock-out lifecycle events for barrier-bearing structured products (Ledger §16 FAQ Q1).
3. **Minimum field set.** `instrument_unit_id`, `barrier_definition_ref` (a reference to the contractual barrier rule in ProductTerms), `observation_time`, `observed_value`, `barrier_value`, `condition` (UP_AND_OUT | DOWN_AND_IN | ...), `breach_indicator`, `attestor_lei`, `signature`.
4. **Identity.** `(instrument_unit_id, observation_time)`.
5. **Provenance.** The contract-specified observation source: typically the underlying-asset's official fixing source (e.g., closing print). The framework is agnostic to who attests; the contract terms specify it.
6. **Temporal semantics.** Per-observation-date events; discrete; once the barrier is breached, the lifecycle transition is immediate (subject to confirmation).
7. **Failure consequences.** Missed knock-out = continued exposure on a terminated product = capital and risk-system inconsistency. Spurious knock-in = wrongly active position.

(a) **Attestation requirement.** Contract-specified attestor must sign. The attestor's signing key is part of the trust assumption registry, with named owner. NEVER accept a barrier observation from an unsigned source. For multi-source observations (some structured products specify "best of three references"), all three must be signed and the aggregation rule applied.

(b) **Dispute-resolution posture.** The contractual attestor's signed observation is dispositive; in case of dispute, the calculation-agent role under the master agreement governs.

(c) **Point-in-time reconstructability.** REQUIRED. The state-only transaction recording the breach (Ledger §16 FAQ Q1) MUST carry the full attestation in its CDM event payload.

(d) **Failure-mode-when-absent.** No barrier transition fires without attestation. Attestation late-arrival → backdated CORRECTION transaction with full lineage. The ledger's state-only-transaction primitive (§16 Q1) handles this cleanly.

---

### 4.3 Exercise Notices and Election Confirmations

1. **Canonical name.** `Oracle.ExerciseNotice`.
2. **Definition.** A signed notification that an option, warrant, or other elective contract is being / has been exercised. Drives lifecycle transition ACTIVE → EXERCISED (Ledger §7).
3. **Minimum field set.** `instrument_unit_id`, `exercising_party_lei`, `exercise_quantity`, `exercise_time`, `exercise_settlement_method` (CASH | PHYSICAL), `payoff_calculation`, `confirmation_party_lei`, `signature`.
4. **Identity.** `(instrument_unit_id, exercising_party_lei, exercise_time)`.
5. **Provenance.** The exercising party's authorised system or, for listed options, the OCC / clearing house. For OTC, ISDA Master + confirmation chain governs; the document is itself the attestation.
6. **Temporal semantics.** Discrete; deadlines per contract terms.
7. **Failure consequences.** Missed exercise = ITM option expires worthless → economic loss. Invalid exercise on an OTM option = disputed cash flow.

(a) **Attestation requirement.** Both-counterparty acknowledgement on OTC; OCC-signed for listed-option exercise / assignment.

(b) **Dispute-resolution posture.** Confirmation-platform signed exercise notice (or OCC for listed); dispute escalates per master agreement.

(c) **Point-in-time reconstructability.** REQUIRED.

(d) **Failure-mode-when-absent.** Exercise lifecycle event blocks; alert raised via obligation-liveness framework if exercise notice is contractually due but absent.

---

### 4.4 Default and Credit-Event Notices

1. **Canonical name.** `Oracle.CreditEvent`.
2. **Definition.** A signed notification of a credit event under a CDS or under master-agreement default provisions: bankruptcy filing, failure to pay, restructuring, government intervention.
3. **Minimum field set.** `reference_entity_lei`, `event_type`, `event_date`, `evidence_reference[]`, `attestor_lei`, `isda_credit_determinations_committee_decision_id` (where applicable), `signature`.
4. **Identity.** `(reference_entity_lei, event_type, event_date, attestor_lei)`.
5. **Provenance.** ISDA Credit Determinations Committee (the canonical authority for CDS credit events); counterparties for bilateral default notices; courts for bankruptcy filings (where digitally accessible).
6. **Temporal semantics.** Discrete; event-driven; legal effective time may differ from notice-receipt time.
7. **Failure consequences.** Missed credit event = continued accrual of premium against a defaulted reference entity = wrong PnL → unwinds at recovery time. Spurious credit event = wrongful close-out triggering legal liability.

(a) **Attestation requirement.** ISDA CDC published decision (signed) for CDS; counterparty-signed for bilateral default; court / liquidator publication (with hash) for bankruptcy.

(b) **Dispute-resolution posture.** ISDA CDC governs CDS credit events; ISDA Master Agreement Section 6 governs bilateral close-out.

(c) **Point-in-time reconstructability.** REQUIRED. The Open Problem "default management" (Ledger §17) is partly a data-layer problem: clean attestation makes the close-out waterfall machine-executable.

(d) **Failure-mode-when-absent.** Close-out cannot fire without attestation; obligation-liveness framework flags the missing notice as a deferred obligation with compensation per master agreement.

---

### 4.5 Settlement Confirmations and Settlement Status Updates

1. **Canonical name.** `Oracle.SettlementConfirmation`.
2. **Definition.** Confirmation messages from the settlement layer (CSD, payment system, clearing house) attesting that a settlement instruction has settled, failed, or is in a particular intermediate state. Maps to ISO 20022 `sese.025`, `camt.054`, etc. (Ledger §8.7).
3. **Minimum field set.** `instruction_id` (referencing the EndToEndId from the projection), `csd_lei`, `confirmed_status` (SETTLED | FAILED | PARTIAL_SETTLED | PENDING), `settlement_date_actual`, `settlement_amount_actual`, `failure_reason_code` (where FAILED), `iso20022_message_hash`, `signature`.
4. **Identity.** `(instruction_id, csd_lei, status, confirmation_time)`.
5. **Provenance.** CSDs (DTC, Euroclear, Clearstream); payment systems (CHIPS, Fedwire, TARGET2); clearing houses; custodian banks at the boundary.
6. **Temporal semantics.** Per-instruction-status events; arrival time often differs from settlement time.
7. **Failure consequences.** Without confirmation, the system cannot transition trade status from INSTRUCTED to SETTLED (Ledger §8.7). Missed FAILED notice means the system thinks something settled that did not.

(a) **Attestation requirement.** CSD signature on the ISO 20022 message; the message hash is recorded in the ledger as part of the lifecycle event payload.

(b) **Dispute-resolution posture.** CSD record is dispositive within the settlement system's books; nostro reconciliation against the firm's custodian's records is the cross-check.

(c) **Point-in-time reconstructability.** REQUIRED — the trade-status lifecycle (EXECUTED → INSTRUCTED → SETTLED / FAILED) is itself a sequence of attested transitions per Ledger §8.7.

(d) **Failure-mode-when-absent.** Trade remains in INSTRUCTED status with explicit settlement-pending flag; nostro reconciliation detects the gap (Ledger §15.10 / §16.5); resolution is via partial settlement, buy-in, or CORRECTION transaction.

---

### 4.6 Margin Call and Collateral Movement Confirmations

1. **Canonical name.** `Oracle.CollateralConfirmation`.
2. **Definition.** Per-counterparty confirmation that a margin movement (CSA VM/IM, SBL collateral substitution / top-up, CCP margin call) has been delivered.
3. **Minimum field set.** `obligation_id` (linking to the obligation-liveness framework, §14.7), `counterparty_lei`, `csa_or_loan_reference`, `expected_amount`, `delivered_amount`, `currency`, `delivery_time`, `triparty_agent_lei` (where applicable), `signature`.
4. **Identity.** `(obligation_id, counterparty_lei, delivery_time)`.
5. **Provenance.** Counterparty's collateral system; triparty agents (BNYM, JPM, Euroclear Triparty, Clearstream); CCPs.
6. **Temporal semantics.** Per-call discrete events; deadlines material (T+1 for CSA VM, intraday for some IM).
7. **Failure consequences.** Missed margin delivery without detection = unsecured exposure. Spurious delivery confirmation = false sense of security.

(a) **Attestation requirement.** Counterparty system signature OR triparty agent signature; CCP signature for cleared margin.

(b) **Dispute-resolution posture.** Triparty agent's signed RQV (Required Quantity Value) record is dispositive when triparty is in scope; otherwise, bilateral signed confirmation.

(c) **Point-in-time reconstructability.** REQUIRED. The obligation-liveness framework P21-P23 (§14.7) depends on attested discharge / non-discharge to drive state to DISCHARGED / COMPENSATED.

(d) **Failure-mode-when-absent.** Obligation deadline timer fires; compensation action (κ) executes (close-out under ISDA, recall / default under GMSLA). This is the canonical use case the obligation-liveness framework is designed for.

---

### 4.7 Custodian Position Statements (External Holdings Reconciliation)

1. **Canonical name.** `Oracle.CustodianStatement`.
2. **Definition.** A signed statement from the custodian as to the firm's holdings in a custodian account at end-of-day. Used for external reconciliation (Ledger §15.10).
3. **Minimum field set.** `custodian_lei`, `account_id`, `as_of_date`, `holdings[]` (each: ISIN, quantity, available_quantity, lent_quantity, pledged_quantity), `cash_balances[]` (per currency), `signature`.
4. **Identity.** `(custodian_lei, account_id, as_of_date)`.
5. **Provenance.** The custodian itself (issuing the statement); ISO 20022 `semt.017`, `semt.013` messages; SWIFT MT535 / MT536 statements.
6. **Temporal semantics.** Per-day end-of-day events.
7. **Failure consequences.** No custodian statement = no boundary reconciliation = nostro break detection delayed = shorts not detected = potential settlement failures cascade.

(a) **Attestation requirement.** Custodian signature on the ISO 20022 / SWIFT message.

(b) **Dispute-resolution posture.** Custodian record vs ledger record difference is a nostro break; resolution is bilateral with custodian; the custodian's record is authoritative for what is in their book.

(c) **Point-in-time reconstructability.** REQUIRED.

(d) **Failure-mode-when-absent.** Reconciliation deferred; nostro-break alerts gated on attestation arrival within `TBD<Operations>`.

---

## Floor 5 — Smart-Contract Execution

I read this floor as: data exchanged at the smart-contract / executor interface — both inputs the smart contracts consume that are not market data (e.g., schedules, election decisions, governance signals) and outputs the smart contracts produce that downstream consumers need (e.g., the moves themselves as attestations to outside systems).

### 5.1 Smart Contract Bytecode / Pure-Function Versioning

1. **Canonical name.** `SmartContract.Version`.
2. **Definition.** The deterministic content-hash and version identifier of each smart contract (lifecycle pure function) deployed in the framework. The Ledger spec mandates that smart contracts are deterministic pure functions (§5, §7.6); their identity must be attested.
3. **Minimum field set.** `contract_id`, `contract_class` (FUTURES_LIFECYCLE | SBL_CONTRACT | CSA_MARGIN | OPTION_PAYOUT | ...), `code_hash` (SHA-256 of canonical bytecode / source), `version`, `deployed_at`, `deployed_by`, `governance_approval_ref`, `cdm_version_compat`.
4. **Identity.** `(contract_class, code_hash)`.
5. **Provenance.** Internal governance — the contract is approved by Risk + Product + Legal; signed by the deployment authority.
6. **Temporal semantics.** Each version has a deployment time; Mid-trade-life version transitions are restricted to backwards-compatible changes; breaking changes require migration (Ledger §14.11 versioning and CDM coexistence).
7. **Failure consequences.** Replay determinism (Ledger Property 6, P3, P9) requires that a historical event is replayed under the contract version that was active at that time. If contract code is mutated in place, replays diverge.

(a) **Attestation requirement.** Internal deployment-authority signature on every contract version. The version is recorded in the move stream metadata (smart contract source field, Ledger §2.3) for every move it generates.

(b) **Dispute-resolution posture.** The deployed version's code hash is dispositive for reproducing historical behaviour.

(c) **Point-in-time reconstructability.** REQUIRED.

(d) **Failure-mode-when-absent.** A move whose contract version cannot be resolved CANNOT be replayed deterministically — this is a hard failure of the framework's foundational replay property.

---

### 5.2 Pricing Model Bytecode and Calibration State

1. **Canonical name.** `PricingModel.Version` and `Calibration.CertifiedState`.
2. **Definition.** The pricing-model code and the calibrated parameter state at any time `t` (output of the Kalman filter, §5 of the Valuation companion).
3. **Minimum field set.** Model: `model_id`, `model_class` (BLACK_SCHOLES | HESTON | LOCAL_VOL | KERNEL_VOL | ...), `code_hash`, `version`, `compute_method` (ANALYTICAL | BUMP | AAD | PATHWISE). Calibration: `calibrated_object_id` (e.g., "USD_yield_curve_v2026_03"), `state_vector_hash`, `covariance_hash`, `certification_timestamp`, `admissible_region_constraints_hash`, `kalman_history_pointer`.
4. **Identity.** `(model_id, version)` for the model; `(calibrated_object_id, certification_timestamp)` for the state.
5. **Provenance.** Internal model-governance signature on the model; Kalman-filter-workflow signature on each certified state.
6. **Temporal semantics.** Models are versioned; calibrations are continuous with per-update certification.
7. **Failure consequences.** Reproducibility of historical valuations requires both model version and calibration state at time `t` (Open Problem in Ledger §17).

(a) **Attestation requirement.** Both signed by their respective workflows; the ValuationRecord (Valuation §3) carries `model_id` AND `market_data_snap` AND a calibration-state pointer — the full triple must be attested.

(b) **Dispute-resolution posture.** Internal model governance authority is dispositive; for IPV, the price-verification authority's mark wins by policy.

(c) **Point-in-time reconstructability.** REQUIRED — and explicitly named as an Open Problem.

(d) **Failure-mode-when-absent.** Model unavailable → ValuationRecord cannot be produced → unit transitions FAILED in FSM. Calibration unavailable → upstream calibration node is not FRESH → T1/T9 guard blocks pricing.

---

### 5.3 Valuation Records (output of pricing) — when consumed downstream

1. **Canonical name.** `ValuationRecord.Snapshot` (defined in Valuation §3).
2. **Definition.** The output of a successful pricing cycle, consumed by PnL explain, by approximate-pricing cache, by risk reporting, and (when at official valuation point) by the Ledger's `V_t` computation.
3. **Minimum field set.** Per Valuation §3: `unit_id`, `timestamp`, `dirty_price`, `clean_price`, `accrued`, `greeks`, `model_id`, `market_data_snap`, `compute_ms`, `quality`, `fsm_state`. PLUS (NAZAROV addition) `calibration_state_ref`, `valuation_workflow_signature`.
4. **Identity.** `(unit_id, timestamp, model_id)`.
5. **Provenance.** The pricing workflow (Valuation §6); the workflow's signature attests that the record is the deterministic output of the named model on the named data snapshot.
6. **Temporal semantics.** Per-cycle events; staleness regime defined by FSM state (FIRM / INDICATIVE / APPROXIMATE / STALE / FAILED).
7. **Failure consequences.** Downstream consumers (XVA, regulatory capital, FRTB, official PnL) take ValuationRecord as fact. A wrongly-attributed mark (e.g., quality flag missing) leads to APPROXIMATE prices being used in official PnL — a regulatory finding.

(a) **Attestation requirement.** Workflow signature mandatory; quality flag mandatory; the consumer MUST verify quality before deciding admissibility (e.g., FRTB capital requires FIRM only).

(b) **Dispute-resolution posture.** ValuationRecord is the system's output; disputes against external IPV / consensus are resolved per IPV process.

(c) **Point-in-time reconstructability.** REQUIRED — every ValuationRecord is content-addressed by `(unit_id, timestamp, model_id, market_data_snap, calibration_state_ref)`.

(d) **Failure-mode-when-absent.** Per the FSM, downstream consumers fall back to last FIRM with STALE quality; or to APPROXIMATE for intraday risk only.

---

### 5.4 Move Stream Entries (the system's own outputs, when consumed by external systems)

1. **Canonical name.** `Move` and `Transaction` (the system's own emissions).
2. **Definition.** The system's own move-stream entries, when consumed by external systems (regulatory reporting, settlement-instruction generation, client statements, audit downloads). Each is a transaction the framework EMITS — but external consumers treat these as data they ingest.
3. **Minimum field set.** Per Ledger §2.3: full transaction including all moves, the CDM event payload, the smart-contract version reference, the executor signature.
4. **Identity.** `transaction_id` (deterministic from the source event).
5. **Provenance.** The framework's executor; signed by the executor's authentication key.
6. **Temporal semantics.** Append-only; immutable post-commit.
7. **Failure consequences.** External consumers that cannot verify the executor signature are at risk of accepting forged ledger data.

(a) **Attestation requirement.** Executor signature on every committed transaction; hash chain to the previous transaction for tamper-evidence (Ledger Invariant 4 / P4).

(b) **Dispute-resolution posture.** The signed move-stream entry is the system's authoritative record.

(c) **Point-in-time reconstructability.** GUARANTEED BY DESIGN — this IS the canonical record.

(d) **Failure-mode-when-absent.** Not applicable — the system always emits.

---

### 5.5 Election and Voluntary Action Decisions

1. **Canonical name.** `SmartContract.ElectionDecision`.
2. **Definition.** Inputs to smart contracts driving voluntary corporate-action elections, voluntary exercise decisions, novation consents, and similar governance signals from authorised actors within the firm.
3. **Minimum field set.** `decision_id`, `unit_id`, `event_reference`, `election_choice`, `actor_lei` / authorised-user-id, `decision_time`, `governance_approval_ref`, `signature`.
4. **Identity.** `(unit_id, event_reference, decision_time)`.
5. **Provenance.** Internal — authorised maker / checker workflow per the firm's governance.
6. **Temporal semantics.** Per-event; deadlines per the underlying corporate-action terms.
7. **Failure consequences.** Wrong decision = wrong economic outcome; missed deadline = default decision applied; impersonated decision = fraud risk (Ledger Open Problem §17 access-control / actor-attribution).

(a) **Attestation requirement.** Authorised actor signature with cryptographic non-repudiation; maker-checker workflow with two distinct signatures where governance demands.

(b) **Dispute-resolution posture.** Internal governance authority resolves; signed audit trail is dispositive.

(c) **Point-in-time reconstructability.** REQUIRED for audit and litigation defence.

(d) **Failure-mode-when-absent.** Default election applied (per the corporate-action terms); the smart contract MUST NEVER fabricate a decision in the absence of attested input.

---

## Floor 6 — Listed-Instrument Detail

I read this floor as: data specific to listed-instrument operations beyond what Floors 1-5 cover. I argue below that this floor is largely subsumed by other floors and propose a restructuring.

### 6.1 Exchange Trading Sessions and State

1. **Canonical name.** `Exchange.SessionState`.
2. **Definition.** Trading-session state per venue: open / close / halt / lulu / reopen events, per-product trading status.
3. **Minimum field set.** `mic`, `session_state`, `session_state_change_time`, `affected_products[]`, `halt_reason_code`, `signature`.
4. **Identity.** `(mic, session_state_change_time)`.
5. **Provenance.** Exchange itself.
6. **Temporal semantics.** Continuous state with discrete state-change events.
7. **Failure consequences.** Trading during a halt = wrong execution; pricing using stale post-close marks during a halt-extension = wrong PnL.

(a) **Attestation requirement.** Exchange-signed event publication.

(b) **Dispute-resolution posture.** Exchange's state record is dispositive.

(c) **Point-in-time reconstructability.** REQUIRED.

(d) **Failure-mode-when-absent.** Trading in the affected product MUST be blocked at smart-contract pre-condition; pricing transitions to STALE.

---

### 6.2 Open Interest and Volume Aggregates

1. **Canonical name.** `Exchange.OpenInterest`.
2. **Definition.** Per-contract open interest and aggregate volume at end-of-day, used for liquidity assessment, position-limit monitoring (Dodd-Frank Title VII, EMIR Article 9), and concentration risk.
3. **Minimum field set.** `contract_unit_id`, `as_of_date`, `open_interest`, `total_volume`, `top_n_position_holders` (where reportable), `signature`.
4. **Identity.** `(contract_unit_id, as_of_date)`.
5. **Provenance.** Exchange / DCO.
6. **Temporal semantics.** Per-day end-of-day.
7. **Failure consequences.** Position-limit breach undetected = regulatory finding; concentration risk understated.

(a-d) Same regime as 3.2; this is essentially a derivative of listed-derivative quotes data.

---

### 6.3 CCP Risk-Margin Inputs

1. **Canonical name.** `CCP.MarginParameters`.
2. **Definition.** CCP-published margin parameters: initial-margin parameters (SPAN / VaR-IM), variation-margin formulas, default-fund contribution rules, haircut tables.
3. **Minimum field set.** `ccp_lei`, `parameter_set_version`, `effective_from`, `parameter_table[]`, `signature`.
4. **Identity.** `(ccp_lei, parameter_set_version)`.
5. **Provenance.** CCP itself (LCH, CME Clearing, Eurex Clearing, etc.).
6. **Temporal semantics.** Per-version with effective dates; updated periodically; emergency updates during stress.
7. **Failure consequences.** Wrong IM expectation = wrong cash-flow planning; wrong default-fund call = funding gap.

(a) **Attestation requirement.** CCP signature on parameter publications.

(b) **Dispute-resolution posture.** CCP's published parameters are dispositive for cleared positions.

(c) **Point-in-time reconstructability.** REQUIRED.

(d) **Failure-mode-when-absent.** IM forecasts unreliable; the firm SHOULD apply conservative buffers; affected workflows enter a HEIGHTENED_UNCERTAINTY state with explicit flagging.

---

## Floor Restructuring Argument

The brief's six floors are workable but mix two orthogonal taxonomic axes: (i) what kind of mutation discipline the data has (Floors 1–2), and (ii) what kind of system-of-origin produces it (Floors 3–6). This is a classification weakness, not a fatal one.

**Specifically:**

1. **Floor 6 (Listed-Instrument Detail) is largely subsumed.** §6.1 (session state) is a special case of Oracle (Floor 4) — exchange-published lifecycle events. §6.2 (open interest) is a derivative of listed-derivative market data (Floor 3.2). §6.3 (CCP margin parameters) is reference data (Floor 2) with a particular authority (the CCP). I would absorb Floor 6 into 2 / 3 / 4 along these lines.

2. **Floor 5 (Smart-Contract Execution) mixes two distinct concerns.** Smart-contract code (5.1) and pricing-model code (5.2) are configuration-as-data with internal governance attestation; election decisions (5.5) are governance-attested human inputs; ValuationRecords (5.3) and move-stream entries (5.4) are system OUTPUTS that downstream consumers ingest. Outputs deserve their own floor — call it "system-emitted attestations" — distinct from inputs.

3. **The Oracle floor (4) needs to subsume more than the brief implies.** Lifecycle observations (barrier breaches, fixings, exercises, defaults), settlement confirmations, and external position statements are all oracle-class data — they are external attestations of events that drive lifecycle state. The brief's Floor 4 should be expanded to cover all of these explicitly.

**Proposed structure (without renumbering the deliverable above):**

- A: **Identity and legal-document data** (Floor 1) — the unchanging-by-design tier; what the StatesHome ruling calls ProductTerms-class plus party identifiers.
- B: **Authoritative tables** (Floor 2) — sanctions, tax, calendars, index constituents, corporate-action schedules, CCP parameter tables.
- C: **Continuous market observations** (Floor 3) — quotes, fixings, marks; the input to the calibration node of the pricing DAG.
- D: **External event attestations** (Floor 4 expanded) — barrier breaches, exercise notices, credit events, settlement confirmations, custodian statements, collateral confirmations.
- E: **Internal configuration and governance signals** (Floor 5 narrowed) — smart-contract code, model code, election decisions, version pinnings.
- F: **System-emitted attestations** (new floor) — ValuationRecords, transaction-stream entries, settlement instructions; the OUTPUTS the framework signs and external systems consume.

This restructure preserves all categories the brief enumerates and fixes the three classification weaknesses.

---

## Cross-Cutting Requirements (apply to every datum above)

These are the NAZAROV-mandated invariants. Phase 2 work is expected to detail per-class implementations; here they are stated once.

### CC-1: Attestation Envelope (Universal Wire Format)

Every datum entering the system MUST arrive in an attestation envelope of the form:
```
{
  payload: <canonicalised data>,
  payload_hash: <sha256 of canonicalised payload>,
  source_id: <named source from registry>,
  source_signature: <signature over payload_hash>,
  source_signing_key_id: <key reference into key-registry>,
  source_publication_time: <monotonic, source-attested>,
  ingestion_time: <local clock, gateway-attested>,
  ingestion_signature: <gateway signature over the entire envelope>,
  schema_version: <data-class schema version>,
  mapping_version: <if synonym mapping was applied; else null>,
  ingestion_path: <which gateway / route admitted this>
}
```

Bare REST / JSON without this envelope MUST NOT be admitted past the ingestion gateway.

### CC-2: Snapshot Specification

A SNAPSHOT is the content-addressed hash of the canonicalised set of attestation envelopes covering all data needed to reproduce a deterministic output. The Ledger's `clone_at(t)` and the Valuation's `market_data_snap` are concrete instantiations.

The snapshot MUST include:
- The set of envelopes covering all upstream Floor 1–5 data needed at time `t`.
- The fallback chain *as actually traversed* when the snapshot was constructed (not the configured chain).
- The mapping versions applied during ingestion.
- Cross-references to other snapshots (e.g., the calibration snapshot referenced by a market-data snapshot).

Snapshots are immutable. Vendor restatements create new snapshot versions; the original is retained (this is the bitemporal property the Ledger Open Problem §17 names).

### CC-3: Aggregation Protocol (per-datum-class)

For every datum class admitting multiple sources, an aggregation rule MUST be specified:
- Aggregation function (median / volume-weighted mid / consensus quorum).
- Disagreement threshold beyond which the aggregation produces a flagged output, never a silent pick.
- Quorum requirement (minimum live sources to produce a FIRM aggregate).
- "Aggregation failed" event semantics — explicit downstream signal.

### CC-4: Fallback Chain Protocol

For every datum class, an ordered fallback chain MUST be specified:
- Primary, secondary, tertiary, last-known-good with staleness flag, hard stop.
- Each transition is a recorded event in the snapshot.
- Hard-stop is mandatory for sanctions data (CC-1) and for cash-flow-driving fixings (3.3); other classes may degrade more gracefully.

### CC-5: Freshness Contract (per-datum-class)

For every datum class, a freshness contract MUST be specified:
- Maximum staleness tolerated.
- Update trigger (heartbeat / deviation / event / pull-on-demand).
- Latency budget from source observation to consumer availability.
- Behaviour at the boundary (what happens at exactly the threshold; clock-skew handling).

### CC-6: Mapping Layer Contract

Every synonym mapping (FpML→CDM, FIX→CDM, ISO 20022→CDM, vendor-specific→internal) MUST be:
- Deterministic, total over its declared input domain.
- Version-pinned with the mapping version recorded in every ingested envelope.
- Failure-explicit: a mapping failure is a named failure event, never a silent default.
- Replay-deterministic: replays under the same mapping version must be bit-identical.

### CC-7: Trust Assumption Registry

Every named source (vendor, internal gateway, attestor key) MUST appear in a trust assumption registry with:
- Unique trust-assumption-id.
- Scope (which datum classes does this trust apply to?).
- Owner (named individual / role).
- Violation consequence (what breaks if this trust is violated?).
- Detection signal (how do we know the trust has been violated?).
- Renewal cadence (key rotation, vendor-relationship review).

### CC-8: Threat Model

Five attacker classes; each must have a documented mitigation per datum class:
- Malicious vendor (signs malicious data with a legitimate key) — mitigation: multi-source aggregation, innovation-gate filtering downstream of attestation.
- Malicious gateway (legitimate gateway signs forged data) — mitigation: source-of-source signature check; gateway is not the bottom turtle.
- Malicious operator (insider with deployment access) — mitigation: maker-checker for governance signals; HSM-rooted signing keys for envelope ingestion.
- Malicious consumer (downstream system tampers with envelopes after ingestion) — mitigation: hash chain on the move stream (Ledger Invariant 4 / P4); Merkle anchoring optional for stronger guarantees.
- Network adversary — mitigation: out-of-band signature verification; replay-resistance via monotonic source-publication-time + ingestion-time pair.

### CC-9: Key Management

Every signing key in the boundary MUST have a documented:
- Generation procedure (HSM-rooted; key-ceremony attendance).
- Storage policy.
- Rotation schedule.
- Revocation procedure with explicit downstream impact.
- Recovery procedure for lost-but-not-compromised cases.
- Compromise-recovery procedure (how does the system reconstruct after a key compromise?).

---

## Verification Approach (for an auditor checking compliance)

For any proposed data-layer implementation against this enumeration, an auditor checks:

1. For each datum class enumerated, does the implementation provide a documented attestation envelope conformant with CC-1?
2. Is the snapshot specification (CC-2) implemented for every consumer of these data classes?
3. Are aggregation rules (CC-3) and fallback chains (CC-4) per-datum-class documented and tested?
4. Is the freshness contract (CC-5) enforced at the gateway boundary, not assumed by consumers?
5. Are all synonym mappings (CC-6) version-pinned, and does the replay test pass bit-identically across mapping versions?
6. Is the trust assumption registry (CC-7) populated, current, and reviewed?
7. Does the threat model (CC-8) cover all five attacker classes per datum class?
8. Are key-management procedures (CC-9) documented, exercised in drills, and audited?

Any "no" is a finding; any "trust me" is a finding. The boundary is held only when every "no" is resolved and every trust is explicit.

---

## Closing

The Ledger framework's six properties (atomicity, conservation, determinism, state-sufficiency, lifecycle value invariance, time travel) hold only because the system is closed within its boundary. Every datum I have enumerated above is a place where the boundary is touched. The framework's guarantees can be no stronger than the discipline at the touch points. Floor 1 governs identity, Floor 2 governs the rules of the world, Floor 3 governs continuous observations, Floor 4 governs discrete event attestations, Floor 5 governs the system's own configuration and inputs, and (per the restructuring argument) the system's outputs deserve their own floor.

I hold the boundary.

— NAZAROV
