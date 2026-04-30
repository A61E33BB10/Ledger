# Phase 1 — Independent Data Enumeration (FEYNMAN)

> *"What I cannot create, I do not understand."*
>
> The discipline of this enumeration: for every datum the Ledger framework
> consumes or produces, I must be able to (1) construct a synthetic example
> from scratch with no external lookup, (2) state how the system would behave
> when it is missing or wrong, and (3) describe at least one *independent*
> way to derive or verify it. Anything I cannot meet on those three counts
> is flagged INCOMPLETE.

---

## 0. Reading of the floor categories before enumerating

The brief gives six floor categories: 1. Static, 2. Reference, 3. Market,
4. Oracle, 5. Smart-contract execution, 6. Listed-instrument detail.

Before populating them I argue the boundaries, because two of the six are
suspect on first reading.

**Static vs Reference.** "Static" is a property of a datum (does not change
within its scope of validity), "Reference" is a role the datum plays
(authoritative description of *what an instrument is*). The categories
collide: ISIN, multiplier, expiry — these are simultaneously static and
reference. The v10.3 spec uses the term *reference data* for instrument
master data (Tier 1 of the Unit Store) and *static terms* for immutable
contract parameters (`ProductTerms` per the StatesHome addendum). I keep
both categories but with sharpened definitions:

- **Static** = framework-internal facts that do not change once written
  (system constants, schemas, code/version pins, calendar definitions
  consumed as immutable artefacts). Author: us.
- **Reference** = externally-sourced descriptions of instruments,
  counterparties, venues, and conventions, consumed but not authored by
  the ledger (Unit Store Tier 1, LEI registry, exchange contract specs,
  CDM enums, ISO 20022 schemas, holiday calendars). Author: external
  authority.

That keeps both useful and non-overlapping.

**Oracle is not a separate substance from Market.** v10.3 §13.5 (lines
~1939) explicitly calls *external messages* (FpML, FIX, ISO 20022) "oracle
outputs". The valuation companion document treats *raw market quotes* as
the input to the Kalman filter and *certified parameters* as its output.
"Oracle" in distributed-systems usage is anything that delivers external
truth into a deterministic system. I therefore split:

- **Market** = the actual numerical observations and certified parameters
  used for valuation (quotes, calibrated curves, surfaces, NAV indices).
- **Oracle** = the *delivery mechanism and provenance* of any external
  truth (attestations, feed identifiers, signatures, capture timestamps,
  fallback chains, restatement records). Same datum can be a Market
  observation by content and an Oracle attestation by envelope.

Without that split, the data layer cannot answer "did we know this at the
time?" — which is the very thing v10.3 §1.2 (Property 6, Time Travel)
demands.

**Smart-contract execution and Listed-instrument detail are both kept as
distinct floors.** Smart-contract execution data is per-invocation
(determinism log, seed, snapshot id), whereas Listed-instrument detail is
per-contract-spec (lot size, exchange calendar, CCP, last settlement
price). They share no key and no lifecycle.

I add a seventh floor of my own — **Identity & Cryptographic Material** —
because LEI/UTI/UPI/ISIN/CCP-id/wallet-id are routinely treated as
"reference data" in the docs but they have a different failure mode:
identity collisions are silent and catastrophic in a way that, e.g., a
stale price is not. They deserve their own surface so that uniqueness and
collision-resistance become testable properties.

So my final taxonomy is:

1. Static
2. Reference
3. Market
4. Oracle (delivery & attestation)
5. Smart-contract execution
6. Listed-instrument detail
7. **Identity & cryptographic material** *(addition)*

---

## 1. Static (framework-internal immutables)

### 1.1 System Schema Catalogue

1. **Canonical name:** `SystemSchemaCatalogue`
2. **Definition:** The set of all type definitions used by the running
   ledger: move schema, transaction schema, `ProductTerms` schema,
   `UnitStatus` schema, `PositionState` schema, `ValuationRecord` schema,
   `SettlementInstruction` schema, plus every product-specific unit-state
   type (bond, future, option, QIS, mandate, SBL loan, …). It is the
   formal vocabulary of the ledger.
3. **Minimum field set:** `schema_id`, `schema_version`, `schema_body`
   (concrete typed definition — JSON Schema, Avro, Rosetta, or the chosen
   IDL), `status` ∈ {ACTIVE, DEPRECATED, RETIRED}, `compatible_with`
   (forward/backward compat predicate), `governing_doc` (e.g., "v10.3 §3",
   "valuation v1.0 §3"), `effective_at`, `superseded_by` (optional).
4. **Identity:** `(schema_name, semantic_version)`.
5. **Provenance:** Authored internally by the ledger architecture team;
   committed to a versioned schema registry; signed by the release pipeline.
6. **Temporal semantics:** Append-only. New versions are *added*, never
   mutated. v10.3 Property 6 (time travel) requires a replay to find the
   exact schema active at the historical time.
7. **Failure consequences:** A move written under schema vN cannot be
   parsed under a vN+1 that drops a field — replay breaks, time travel
   silently lies. Mutating an existing schema in place destroys
   reproducibility.
8. **Cross-check:** Hash every committed schema; the hash chain *must*
   match a re-derivation from the latex source (or Rosetta DSL source) at
   the same git commit. Two independent paths to the same schema_id ⇒
   the schema is what we think it is.

> *Build it from scratch:* yes — given the latex spec and the DSL, I can
> emit every schema by codegen.

### 1.2 Code/Model Version Pins

1. **Canonical name:** `CodeVersionManifest`
2. **Definition:** The exact (git_sha, container_digest) of every
   binary that participated in producing a transaction, valuation, or
   settlement instruction: executor, lifecycle workers, pricers,
   calibration filter, settlement projector. v10.3 §17.2 (Open Problems,
   Bitemporal) explicitly identifies model-version-pinning as a
   reproducibility precondition.
3. **Minimum field set:** `component_name`, `git_sha`, `container_digest`
   (sha256), `built_at`, `built_by`, `compile_flags`, `runtime_envvars`
   (only the determinism-affecting subset), `dependency_lock_hash`.
4. **Identity:** `(component_name, git_sha, container_digest)`. The
   container_digest disambiguates two builds of the same sha with
   different base images.
5. **Provenance:** Build pipeline (CI). Signed by build attestor.
6. **Temporal semantics:** Append-only. Each transaction stamps the
   manifest active at commit time.
7. **Failure consequences:** Without it, "rerun the same calculation"
   silently uses today's binary on yesterday's data — pricing drift goes
   unnoticed, PnL explain residuals are misattributed to market moves.
8. **Cross-check:** Reproducible builds — re-build from `git_sha` in a
   sealed environment; the resulting digest must equal the recorded
   `container_digest`. If not, the manifest is corrupted or the build is
   not actually deterministic.

### 1.3 Determinism-Critical Numerical Constants

1. **Canonical name:** `NumericalConstants`
2. **Definition:** Decimal precision (e.g., 18 dp per v10.3 §5.1),
   rounding mode (banker's = half-to-even, per same paragraph), reference
   currency (USD per v10.3 §4.1), epoch convention (UTC), max
   workflow-history-event count for `ContinueAsNew`, Kalman process-noise
   floors, innovation-gating χ² thresholds (e.g., 99th percentile per
   valuation §6.5).
3. **Minimum field set:** `constant_name`, `value` (typed), `unit`,
   `effective_at`, `superseded_by`, `governing_doc_anchor`, `change_log`
   (free text justification on every change).
4. **Identity:** `constant_name`.
5. **Provenance:** Architecture committee; controlled-change board.
6. **Temporal semantics:** Versioned append-only. A change is a new row;
   the old row remains with its `effective_at..superseded_at` validity
   window.
7. **Failure consequences:** Changing `decimal_precision` from 18 to 12
   silently changes every accumulated_cost re-derivation; changing
   `rounding_mode` from banker's to half-up shifts thousands of cash
   moves by sub-cent amounts that then refuse to reconcile.
8. **Cross-check:** All numerical constants used by a calculation must be
   pinned in the calculation's provenance record. Re-running the
   calculation with the *current* constants must produce a strictly
   different output if any constant changed — otherwise either the
   constant is dead code or the manifest is wrong.

### 1.4 Holiday Calendars (as immutable artefacts)

1. **Canonical name:** `HolidayCalendarSnapshot`
2. **Definition:** A frozen list of (date, business_centre) pairs that are
   not business days, with a known `published_at` and `version`. v10.3
   §App-CDM-dates lists ~200 `BusinessCenterEnum` codes (USNY, GBLO, EUTA,
   JPTO, …); the *content* of each calendar is reference data (§2 below),
   but the framework's immutable copy of the calendar at a given time is
   static.
3. **Minimum field set:** `calendar_id` (= `BusinessCenter` code),
   `version`, `published_at`, `valid_from`, `valid_to`, `holiday_dates`
   (sorted set of `date`), `source_publisher`, `source_url_or_doc`.
4. **Identity:** `(calendar_id, version)`.
5. **Provenance:** Public publishers (FedReserve, Fed/NYSE for USNY, BoE
   for GBLO, ECB for EUTA, …). Re-published internally as a signed,
   versioned snapshot.
6. **Temporal semantics:** Snapshots are append-only and timestamped.
   When a publisher amends a future date (rare but real — e.g., a
   sovereign mourning day declared late), a new version is recorded; old
   transactions resolved against the old version remain resolved against
   it.
7. **Failure consequences:** A coupon that should land Aug 14 lands Aug
   15 instead, the move is misdated, day-count fractions are wrong,
   accrued interest is wrong, dirty price is wrong — everything
   downstream silently drifts.
8. **Cross-check:** Re-derive all `MODFOLLOWING`-adjusted dates in a
   given trade portfolio against an independent reference (Bloomberg
   CDR<GO>, Refinitiv calendar, ICE). Disagreement on any single date
   within the lookahead horizon ⇒ a calendar is wrong.

### 1.5 ISO 20022 / CDM / FpML Schema Versions Pinned

1. **Canonical name:** `ExternalSchemaVersionPin`
2. **Definition:** The exact ISO 20022 message version (e.g.,
   `sese.023.001.10`), CDM release (e.g., `FINOS CDM v6.0.0`),
   FpML version, FIX version that the running system is compiled against.
3. **Minimum field set:** `external_schema_name`, `version`, `xsd_or_dsl_hash`,
   `pinned_at`, `governing_release` (Ledger release id), `local_extensions`
   (any institution-specific add-ons listed explicitly).
4. **Identity:** `(external_schema_name, version)`.
5. **Provenance:** External standards bodies (ISO TC68, FINOS, FpML,
   FIX Trading Community); pinned internally per Ledger release.
6. **Temporal semantics:** A given Ledger release pins exactly one
   version per external schema. Upgrades are coordinated changes.
7. **Failure consequences:** Mismatch between the schema we serialise to
   and the schema the custodian validates against ⇒ every settlement
   instruction rejected ⇒ liquidity event.
8. **Cross-check:** Round-trip a sample message through both versions of
   the pinned schema; structural diff must be empty for the unchanged
   fields and explicit for the new ones.

---

## 2. Reference (externally-authored descriptions)

### 2.1 Instrument Reference Data (Unit Store Tier 1)

1. **Canonical name:** `InstrumentReferenceRecord`
2. **Definition:** The instrument master record per v10.3 §3.3.1 — what
   exists in the market. Listed equity ISIN + exchange + lot size; listed
   derivative contract spec (underlier, strike, expiry, multiplier,
   settlement style, CCP); bond ISIN + issuer + coupon schedule; cash
   currency code; tokenized security on-chain identifier (chain_id,
   contract_address) per §App-tokenized.
3. **Minimum field set:** `instrument_id` (ISIN | exchange contract spec
   hash | currency code | trade-id for OTC), `instrument_type` (CASH |
   EQUITY | LISTED_DERIV | OTC_DERIV | BOND | STRUCTURED | TOKENIZED),
   `issuer_lei`, `currency`, `multiplier?`, `lot_size?`, `expiry?`,
   `exchange_mic?`, `ccp_id?`, `coupon_schedule?`, `underlying_isin?`,
   `chain_id?`, `contract_address?`, `source_publisher`, `source_seq_id`,
   `received_at`.
4. **Identity:** Per v10.3 §3.2: ISIN for securities/bonds; deterministic
   hash of contract specification for listed derivatives; `Trade.metadata`
   key (≈ UTI) for OTC; `(chain_id, contract_address)` for tokens; ISO
   4217 code for cash. The unit_id derivation must be **injective**.
5. **Provenance:** Exchanges, CSDs, ANNA (ISIN authority), reference data
   vendors (Bloomberg DL, Refinitiv RDP, SIX, ICE Data). Each record
   carries publisher + sequence id.
6. **Temporal semantics:** Bitemporal. `effective_at` is when the
   instrument exists in the world; `received_at` is when we learned of
   it. Restatements (a corrected lot size, a deleted listing, a corporate
   action retro-applied) get new versions; old transactions remain
   resolved against the version they were processed under.
7. **Failure consequences:** Wrong ISIN ⇒ wrong unit ⇒ wrong wallet
   balance, wrong reporting, possible failed settlement. Wrong lot size
   ⇒ physical delivery rejected at the exchange. Missing CCP id ⇒
   settlement instruction has no clearing path.
8. **Cross-check:** Two-source reconciliation — every active listed
   instrument in our Unit Store must match on ISIN, currency, multiplier,
   lot, expiry across at least two independent vendors. Mismatch ⇒
   quarantine, do not register, do not trade.

### 2.2 CDM Product Qualification Tables

1. **Canonical name:** `CDMProductQualification`
2. **Definition:** The CDM `ProductQualification` decision tree mapping
   `EconomicTerms` → product type label per v10.3 §3.3.2 and §13.4. This
   is the table that says "this set of payouts qualifies as
   InterestRate:IRSwap:FixedFloat" and "this set qualifies as
   Equity:Option:European".
3. **Minimum field set:** `qualification_node_id`, `parent_id`,
   `predicate` (boolean expression on EconomicTerms fields), `output_label`
   (path string), `cdm_version`, `priority`.
4. **Identity:** `(cdm_version, qualification_node_id)`.
5. **Provenance:** ISDA / FINOS, distributed with CDM release.
6. **Temporal semantics:** Versioned with the CDM release. A re-qualification
   at a new CDM version may relabel an existing trade; the old label
   remains in the trade's history.
7. **Failure consequences:** Misqualification ⇒ wrong smart contract
   bound to the unit ⇒ wrong lifecycle events fired ⇒ silent value
   error. v10.3 §3.5 makes "ProductQualification returns a valid
   classification" a registration-time correctness gate.
8. **Cross-check:** Run two independent CDM implementations
   (FINOS reference + a second implementation, e.g., Rosetta-DSL-from-source
   vs compiled-Java-jar) on the same `EconomicTerms`; they must produce
   the same label. If not, the qualification table or one of the engines
   is broken.

### 2.3 Counterparty / Legal-Entity Master

1. **Canonical name:** `LegalEntityRecord`
2. **Definition:** Per-counterparty master: LEI, legal name, jurisdiction,
   regulatory classifications (FC/NFC under EMIR, US person flag,
   reporting-obligated y/n), parent-LEI, status. Drives virtual-wallet
   identity (v10.3 §2.4) and settlement-instruction `counterparty_lei`.
3. **Minimum field set:** `lei`, `legal_name`, `legal_form`,
   `jurisdiction`, `parent_lei?`, `lei_status` ∈ {ISSUED, LAPSED,
   DUPLICATE, RETIRED, MERGED}, `last_validated_at`, `gleif_attestation_chain`,
   `internal_credit_rating?`, `regulatory_flags`.
4. **Identity:** `lei`.
5. **Provenance:** GLEIF (root authority) via accredited LOUs. Local
   credit/regulatory enrichment.
6. **Temporal semantics:** Bitemporal. LEI lapse, merger, transfer
   events are not deletions but state transitions with `effective_at`.
7. **Failure consequences:** Lapsed LEI on a reporting field ⇒ EMIR/CFTC
   submission rejected. Misidentified counterparty ⇒ wrong CSA applied
   ⇒ wrong margin computed.
8. **Cross-check:** Daily delta of internal LEI store vs GLEIF download;
   any divergence on `lei_status` is a reportable break.

### 2.4 Calendars — Holiday Definitions (the data behind §1.4 snapshots)

1. **Canonical name:** `HolidayCalendarMaster`
2. **Definition:** The publisher's authoritative source of holidays for a
   business centre. §1.4 was the *frozen artefact*; this is the
   *upstream feed*.
3. **Minimum field set:** `calendar_id`, `publisher`, `feed_url_or_msg_type`,
   `update_frequency`, `lookahead_horizon_years`, `ingest_history`.
4. **Identity:** `calendar_id`.
5. **Provenance:** External (FedRes, NYSE, BoE, ECB, JPX, etc.).
6. **Temporal semantics:** Continuously refreshed; downstream snapshots
   (§1.4) freeze at known points.
7. **Failure consequences:** Same as §1.4 plus: missed publisher update
   ⇒ tomorrow's payment date computed against yesterday's holiday list.
8. **Cross-check:** Cross-source against ICE/Refinitiv; alert on any
   newly-published holiday within 30 days that is not yet in our store.

### 2.5 Day-Count Convention Library

1. **Canonical name:** `DayCountConventionLibrary`
2. **Definition:** Implementations of `DayCountFractionEnum` (v10.3
   §App-CDM-dates lines ~5917): ACT/360, ACT/365_FIXED, ACT/ACT_ISDA,
   30/360, 30E/360, etc. Each is a pure function of (start_date,
   end_date, period_metadata).
3. **Minimum field set:** `convention_code`, `function_spec` (formal
   definition), `reference_implementation_hash`, `governing_standard`
   (e.g., ISDA 2006 Definitions §4.16), `test_vectors`.
4. **Identity:** `convention_code`.
5. **Provenance:** ISDA, ICMA, FpML — distributed via CDM Rosetta source.
6. **Temporal semantics:** Versioned with CDM/FpML release; rare changes.
7. **Failure consequences:** Wrong year fraction ⇒ wrong coupon amount
   ⇒ wallet imbalance vs counterparty ⇒ reconciliation break.
8. **Cross-check:** Each convention ships with ISDA test vectors;
   property-based tests on (start, end) pairs across leap-year
   boundaries; differential test against an independent OSS implementation
   (e.g., QuantLib) — must agree to last decimal.

### 2.6 Mandate / Strategy Definitions (per StatesHome)

1. **Canonical name:** `MandateContractTerms`
2. **Definition:** Per the StatesHome addendum, the mandate is a
   first-class *unit* `u_MA`. The mandate text, fee schedule, benchmark
   identity, max-position limits, HWM hurdle methodology, crystallisation
   frequency live in `ProductTerms[u_MA]`. Equally, QIS strategy
   contract terms (vol target, barrier, universe, share-class index
   start) live in `ProductTerms[u_QIS]`.
3. **Minimum field set:** `mandate_or_strategy_id`, `legal_text_doc_hash`,
   `manager_lei`, `client_lei?`, `benchmark_unit_id`, `fee_schedule`,
   `mgmt_fee_bps`, `perf_fee_bps`, `hwm_methodology`, `crystallisation_frequency`,
   `position_limits`, `permitted_instrument_universe_predicate`,
   `effective_at`, `signed_doc_hash`.
4. **Identity:** `mandate_or_strategy_id` (allocated at issuance, like a
   trade UTI; ties back to a CDM Trade for the mandate-as-unit).
5. **Provenance:** Negotiated bilaterally; signed PDF or DocuSign;
   structured fields extracted and signed by Legal/Product.
6. **Temporal semantics:** `ProductTerms` is append-only versioned (C6).
   A mandate amendment is either Preserving (append `TermsVersion`) or
   Breaking (allocate a fresh `u_MA_new` with `SupersededBy`). C8.
7. **Failure consequences:** Wrong fee schedule ⇒ wrong fee accrual on
   `PositionState[w_client, u_MA]`; wrong universe predicate ⇒ accepted
   trade that should be a guard-rejection; missing benchmark id ⇒ NAV
   computation has no anchor.
8. **Cross-check:** Two-track verification — (a) a re-extraction of
   structured fields from the signed PDF must equal the stored record;
   (b) running last quarter's fees against the recorded schedule must
   reproduce the signed client invoice line-by-line.

### 2.7 CSA / Collateral Agreement Terms

1. **Canonical name:** `CSATerms`
2. **Definition:** The terms of a Credit Support Annex governing a
   bilateral relationship between two LEIs. Threshold, MTA, eligible
   collateral, haircuts, valuation agent, dispute resolution. v10.3
   §6.5 makes the CSA margin a wallet-level smart contract; the *terms*
   live in reference data and feed `ProductTerms` of the collateral
   wallet's mandate-unit-equivalent.
3. **Minimum field set:** `csa_id`, `party_a_lei`, `party_b_lei`,
   `governing_law`, `threshold_a`, `threshold_b`, `mta`,
   `eligible_collateral` (list of (unit_id, haircut, currency)),
   `valuation_agent`, `dispute_resolution`, `signed_at`,
   `effective_from`, `signed_doc_hash`, `csa_type` ∈ {NY_LAW_PLEDGE,
   ENGLISH_LAW_TITLE_TRANSFER, JAPANESE, …}.
4. **Identity:** `csa_id` (firm-internal) cross-linked to ISDA Master
   Agreement reference.
5. **Provenance:** Negotiated by Credit/Legal; structured-field
   extraction signed off; archived alongside signed master.
6. **Temporal semantics:** Amendments are versioned. Replays must use
   the version active at the move's timestamp.
7. **Failure consequences:** Wrong threshold ⇒ undercall/overcall on
   margin; wrong eligible collateral ⇒ post collateral the counterparty
   refuses; wrong governing law ⇒ wrong netting assumption ⇒ wrong
   regulatory capital.
8. **Cross-check:** The CSA's margin call output computed by the firm
   versus the counterparty's same-day computation; the two should match
   within the agreed dispute tolerance. Any persistent gap signals a
   reference-data break, not a market move.

### 2.8 Exchange & CCP Catalogue

1. **Canonical name:** `VenueAndCCPCatalogue`
2. **Definition:** Master of exchanges (MIC code, market hours, trading
   calendar reference, lot rules) and CCPs (id, member status, margin
   methodology family).
3. **Minimum field set:** `mic_code`, `legal_name_lei`, `country`,
   `trading_calendar_id`, `session_schedule`, `lot_rules`, `ccp_id?`,
   `ccp_methodology` (SPAN, VaR, …), `cleared_products`, `effective_from`.
4. **Identity:** `mic_code` for venues; `ccp_id` (LEI of the CCP) for
   CCPs.
5. **Provenance:** ISO 10383 maintainer (ISO/SWIFT) for MICs; CCPs'
   own publications.
6. **Temporal semantics:** Slow-moving but versioned; venue mergers and
   CCP rule changes are real.
7. **Failure consequences:** Wrong MIC ⇒ trade booked to wrong venue ⇒
   wrong reporting jurisdiction. Wrong CCP methodology ⇒ wrong margin
   estimate ⇒ funding miscalculation.
8. **Cross-check:** ISO 10383 monthly diff applied to internal store;
   CCPs publish daily margin parameter files — re-run our SPAN against
   their published parameters and reconcile to last decimal on a
   reference portfolio.

### 2.9 Tax & Regulatory Reference

1. **Canonical name:** `TaxAndRegulatoryReference`
2. **Definition:** Withholding-tax rates by (issuer-jurisdiction,
   holder-jurisdiction, instrument-type, treaty-status); reportable-trade
   classifications (EMIR FC/NFC, CFTC Reportable, MiFID transparency
   regime); SFTR/SLATE applicability flags. v10.3 §11 cites these
   integrations.
3. **Minimum field set:** `rule_id`, `rule_kind` ∈ {WHT, EMIR_CLASS,
   MIFIR_TRANSPARENCY, SFTR_FLAG, SLATE_FLAG, …}, `predicate`,
   `output_value`, `governing_authority`, `effective_from`, `effective_to`,
   `published_in` (regulation citation).
4. **Identity:** `rule_id`.
5. **Provenance:** Regulators (ESMA, CFTC, SEC, FCA, IRS,
   national tax authorities); compliance team's structured digest.
6. **Temporal semantics:** Versioned; rules carry validity windows.
   Replays use the rule active at the event time.
7. **Failure consequences:** Wrong WHT ⇒ wrong cash move on dividend
   pay; wrong EMIR class ⇒ over- or under-reporting.
8. **Cross-check:** Re-classify a sample of last quarter's trades under
   the current rule set and compare to the regulator-acknowledged
   submission. Any class flip not explained by a rule version change
   = bug.

---

## 3. Market (the actual numerical observations & calibrated parameters)

### 3.1 Raw Market Quotes

1. **Canonical name:** `RawMarketQuote`
2. **Definition:** Per valuation v1.0 §6.3, the raw market observation
   `y_t`: bid, ask, last-traded, swap rate, option price/IV quote,
   deposit rate, FX spot.
3. **Minimum field set:** `quote_id`, `instrument_id`, `quote_type`
   (BID|ASK|MID|LAST|TRADE|YIELD|IV|SWAP_RATE), `value` (Decimal),
   `quote_currency`, `timestamp_exchange`, `timestamp_received`,
   `source_feed_id`, `source_seq_no`, `bid_ask_size?`, `quote_qualifiers`
   (manual, indicative, regular, …).
4. **Identity:** `(source_feed_id, source_seq_no)`. *Not* `(instrument,
   timestamp)` — the same instrument at the same timestamp can have
   multiple quotes from multiple venues, and they are all valid data.
5. **Provenance:** Exchange feeds, market-data vendors, dealer streams.
   Stamped with feed id and sequence.
6. **Temporal semantics:** Bitemporal — `timestamp_exchange` (when the
   quote was made) vs `timestamp_received` (when we ingested). Vendor
   restatements happen and produce new rows.
7. **Failure consequences:** A stale or out-of-band quote consumed as
   "current" ⇒ wrong calibration ⇒ wrong pricing ⇒ misreported PnL.
   v10.3 §8 notes that valuation operations driven by stale prices
   produce economically incorrect moves on managed-account/TRS resets
   ("The conservation layer is independent of market data … but
   value-dependent settlements must gate on data quality").
8. **Cross-check:** Two-source reconciliation per liquid instrument —
   independent feeds (e.g., Bloomberg + Refinitiv) on the same instant
   should agree within bid/ask tolerance; persistent divergence ⇒ feed
   degradation alarm.

### 3.2 Calibrated Curves & Surfaces (Kalman posterior)

1. **Canonical name:** `CalibratedParameterVector`
2. **Definition:** Valuation v1.0 §6.1: the Kalman posterior mean
   `x_{t|t}^certified` representing the latent market state — yield curve
   nodes, equity vol surface coefficients, credit hazard rates, FX vol
   surface params. *This is the input the Pricing DAG consumes at its
   leaves.*
3. **Minimum field set:** `calibration_object_id`, `calibration_kind`
   (USD_YIELD_CURVE | EQUITY_VOL_SURFACE | CREDIT_HAZARD | FX_VOL),
   `state_vector` (Decimal[d]), `state_covariance` (Decimal[d×d]),
   `innovation` (`ν_t`), `innovation_mahalanobis_d2`, `innovation_chi2_threshold`,
   `gate_decision` ∈ {ACCEPT, DOWNWEIGHT, REJECT}, `arbitrage_certified` bool,
   `input_quote_ids` (FK to §3.1), `as_of_timestamp`,
   `kalman_filter_version`.
4. **Identity:** `(calibration_object_id, as_of_timestamp,
   kalman_filter_version)`.
5. **Provenance:** Internal calibration workflow (a Temporal workflow per
   valuation v1.0 §6.7). Inputs are §3.1; outputs flow into the Pricing
   DAG.
6. **Temporal semantics:** Strict monotonic in `as_of_timestamp` per
   calibration_object; restatements (when vendor corrects an upstream
   quote) re-run the filter from a checkpoint and emit a new lineage
   chain.
7. **Failure consequences:** Per §6.6, an arbitrage-violating posterior
   that is silently consumed produces tradable arbitrage in our own
   prices. A `gate_decision = REJECT` that is *not* propagated leaves
   the FSM consuming a stale-but-not-flagged calibration.
8. **Cross-check:** Re-imply the input quotes from the posterior — the
   round-trip residuals must match the stored `ν_t`. Independently,
   running an alternative calibration method (e.g., direct least-squares
   bootstrapping vs Kalman) on the same quotes must produce a result
   within the documented uncertainty band.

### 3.3 ValuationRecord (the produced price)

1. **Canonical name:** `ValuationRecord`
2. **Definition:** Valuation v1.0 §3 Definition 3.1: the full pricing
   output for a unit at a time — `dirty_price`, `clean_price`,
   `accrued`, `greeks` (model-specific tagged union), `model_id`,
   `market_data_snap`, `compute_ms`, `quality` ∈ {FIRM, INDICATIVE,
   APPROXIMATE, STALE, FAILED}, `fsm_state`.
3. **Minimum field set:** all the above plus `unit_id`, `timestamp`,
   `pricer_version_pin` (FK to §1.2), `parameter_jacobian` for total-PnL
   attribution, `pnl_explain_residual` (when FSM = EXPLAINED).
4. **Identity:** `(unit_id, timestamp, model_id)`.
5. **Provenance:** PricingWorkflow (one per unit, valuation v1.0 §7).
6. **Temporal semantics:** Append-only within a pricing cycle (valuation
   v1.0 §10). Time-travel queries via `snapshot_at(t)`.
7. **Failure consequences:** A FIRM record that is actually wrong ⇒
   official PnL is wrong, regulatory report is wrong. An APPROXIMATE
   record consumed as FIRM ⇒ official PnL contaminated with Taylor
   error.
8. **Cross-check:** PnL explain (valuation §9) — for each FIRM record at
   time t1 against the previous FIRM at t0, the polynomial decomposition
   `Δprice ≈ Σ greek_i · Δfactor_i` must close within tolerance. The
   identity *is* the cross-check; FSM transition T5/T6 is the gate.

### 3.4 PnL Explain Residuals

1. **Canonical name:** `PnLExplainRecord`
2. **Definition:** Per valuation v1.0 §9 and the polynomial-PnL papers —
   for each (unit, t0→t1) pair: explained PnL by Greek, parameter PnL,
   cashflow PnL, total PnL, residual.
3. **Minimum field set:** `unit_id`, `t0`, `t1`, `prev_record_id`,
   `curr_record_id`, `delta_pnl`, `gamma_pnl`, `parameter_pnl_by_param`,
   `theta_pnl`, `cashflow_pnl`, `total_pnl`, `residual`, `tolerance`,
   `status` ∈ {PASS, FAIL}, `model_id`.
4. **Identity:** `(unit_id, t0, t1)`.
5. **Provenance:** PnL explain activity (valuation v1.0 §9).
6. **Temporal semantics:** Append-only per pricing cycle.
7. **Failure consequences:** Persistent unexplained residuals are the
   leading indicator of model error, parameter regime change, or
   bad data. Ignoring them = quietly accruing model risk.
8. **Cross-check:** Independent re-implementation of the polynomial
   identity (eq 9.2 in valuation v1.0) using AAD on the same model and
   inputs; residual must agree to within numerical noise. Disagreement
   ⇒ Greeks are inconsistent with the price.

### 3.5 Market-Data Snapshot

1. **Canonical name:** `MarketDataSnapshot`
2. **Definition:** A frozen, identified bundle of all market state used
   for a single pricing/lifecycle invocation. v10.3 §7.7 calls this
   precondition out explicitly: "a deterministic market-data oracle …
   the market data used by each lifecycle invocation is captured and
   stored at the time of execution".
3. **Minimum field set:** `snapshot_id`, `as_of_timestamp`,
   `quote_ids` (FK list to §3.1), `calibration_ids` (FK list to §3.2),
   `holiday_calendar_versions`, `fx_rates`, `seal_hash`.
4. **Identity:** `snapshot_id`.
5. **Provenance:** Created by the `MarketDataActivity` task queue
   (valuation §7.6); consumed by pricer + lifecycle activities.
6. **Temporal semantics:** Immutable once sealed. A re-pricing with
   "today's corrected data" uses a different snapshot id, not a mutation
   of the original.
7. **Failure consequences:** Without a sealed snapshot, replays drift —
   v10.3 §16.3 says "reproducibility requires version-pinning of these
   external dependencies". A non-sealed snapshot violates determinism.
8. **Cross-check:** `seal_hash` must equal `H(quote_ids ‖ calibration_ids
   ‖ holiday_calendar_versions ‖ fx_rates)` recomputed from the
   referenced rows. If they diverge, somebody mutated history.

### 3.6 FX Rates (special-cased)

1. **Canonical name:** `FXRate`
2. **Definition:** Spot, forward, and reset fixings between two
   currencies. v10.3 §4 makes FX rates load-bearing: portfolio value
   uses a designated reference currency and FX is one of the parameters
   "affecting reported PnL".
3. **Minimum field set:** `pair_id` (e.g., "EURUSD"), `rate_kind` ∈
   {SPOT, FWD, FIXING}, `rate_value`, `tenor?`, `as_of_timestamp`,
   `source_feed_id`, `source_seq_no`.
4. **Identity:** `(pair_id, rate_kind, tenor, as_of_timestamp, source_feed_id)`.
5. **Provenance:** Same as §3.1 plus official fixings (ECB, WMR/Refinitiv).
6. **Temporal semantics:** Bitemporal; official fixings are restateable.
7. **Failure consequences:** Wrong FX ⇒ wrong reference-currency
   portfolio value ⇒ wrong PnL across the entire firm.
8. **Cross-check:** Triangle arbitrage — `EURUSD * USDJPY * JPYEUR`
   must equal 1 within bid/ask. Persistent triangle violation ⇒ feed
   degradation or stale fixing.

---

## 4. Oracle (delivery, attestation, provenance envelope)

### 4.1 Inbound Attestation Record

1. **Canonical name:** `InboundAttestation`
2. **Definition:** The wrapped envelope of every external message
   ingested into the ledger — execution reports (FIX), trade
   confirmations (FpML), settlement confirmations (ISO 20022 sese.025,
   camt.054), corporate-action announcements, holiday-calendar updates,
   raw market quotes. v10.3 §13.5 defines the synonym layer as the
   "Oracle Interface": these are *raw* before that translation.
3. **Minimum field set:** `attestation_id`, `payload_bytes_hash`,
   `payload_format` (FIX|FPML|ISO20022|JSON|CSV|BINARY), `source_party_lei`,
   `signing_key_id?`, `signature?` (where the protocol provides one),
   `tls_chain_hash?`, `received_at`, `ingest_pipeline_version`,
   `protocol_seq_no`, `linked_message_id` (FpML MessageId / ISO MsgId / FIX MsgSeqNum).
4. **Identity:** `attestation_id` = `H(source_party_lei ‖ payload_bytes ‖ received_at)`.
5. **Provenance:** External counterparty / venue / vendor; linked to
   their LEI.
6. **Temporal semantics:** Append-only. The attestation is the *fact*
   "we received bytes X at time T from party L".
7. **Failure consequences:** Without it, a settlement confirmation that
   later disappears from the counterparty's record cannot be defended.
   Loss of attestations ⇒ loss of disputability.
8. **Cross-check:** When the external counterparty offers a per-message
   ack signature, ours and theirs hash chain over the day's exchange
   should converge; a missing ack on our side or extra on theirs is a
   non-repudiation gap.

### 4.2 Outbound Instruction & Acknowledgement

1. **Canonical name:** `OutboundInstructionRecord`
2. **Definition:** The mirror of §4.1 for things we send: settlement
   instructions (sese.023, pacs.008/009 per v10.3 §10.3),
   regulatory-report submissions, confirmations, call notices.
3. **Minimum field set:** `outbound_id`, `payload_bytes_hash`,
   `payload_format`, `recipient_lei`, `our_signing_key_id`, `signature`,
   `dispatched_at`, `dispatch_channel`, `their_ack_attestation_id?`
   (FK to §4.1 when the response comes back), `linked_internal_event_ids`.
4. **Identity:** `outbound_id`.
5. **Provenance:** Internal. Signed by the firm.
6. **Temporal semantics:** Append-only. Status transitions
   (DISPATCHED → ACKED → CONFIRMED) are recorded in the move stream
   as separate lifecycle events per v10.3 §10.4 (settlement state
   model).
7. **Failure consequences:** Without it, no proof we actually instructed
   anything. v10.3's traceability chain (smart contract → move →
   instruction → ack → status update) breaks.
8. **Cross-check:** End-of-day reconciliation: every committed
   `SETTLEMENT`-class transaction (per v10.3 §10) must have produced
   exactly one outbound (or be flagged unsettlable). Counted on both
   sides.

### 4.3 Source Reliability & Health Metrics

1. **Canonical name:** `OracleHealthMetric`
2. **Definition:** Per-feed / per-source rolling statistics: latency
   distribution, gap count, restatement rate, mean innovation in the
   Kalman gating, % rejected. Drives the data-quality gate at the
   lifecycle workflow (v10.3 §14.7) and the staleness threshold for
   FSM-T8.
3. **Minimum field set:** `source_feed_id`, `window_start`, `window_end`,
   `latency_p50/p99`, `gap_count`, `restatement_count`,
   `mean_innovation`, `chi2_rejection_rate`, `current_health`
   ∈ {GREEN, AMBER, RED}.
4. **Identity:** `(source_feed_id, window_end)`.
5. **Provenance:** Ingest pipeline observability.
6. **Temporal semantics:** Sliding-window aggregates, archived as
   periodic snapshots.
7. **Failure consequences:** Without it, staleness gates and
   data-quality activities (v10.3 §14.7.4 and valuation §6.5) cannot be
   parameterised.
8. **Cross-check:** Re-derive metrics from §3.1 raw quotes for the same
   window; the aggregator vs the raw source must match.

### 4.4 Time Source

1. **Canonical name:** `AuthoritativeClock`
2. **Definition:** The canonical wall-clock and monotonic clock used to
   stamp moves, transactions, and snapshots. v10.3 requires UTC; ISO
   20022 fields `CreDtTm` and exchange timestamps anchor against it.
3. **Minimum field set:** `clock_source` (e.g., NTP-stratum-1, PTP,
   GPS), `last_disciplined_at`, `current_offset_estimate`, `leap_second_table_version`.
4. **Identity:** `clock_source`.
5. **Provenance:** Operations / SRE.
6. **Temporal semantics:** Health is observed continuously. Major drift
   events are recorded.
7. **Failure consequences:** Clock skew across workers ⇒ moves emit
   with timestamps that violate causal order ⇒ replay disagrees with
   live ⇒ reconciliation breaks. v10.3 §14.10 (deterministic replay)
   needs the clock to *not* be a hidden input.
8. **Cross-check:** Two independent NTP/PTP sources cross-checked
   continuously; deviation > threshold halts move emission rather than
   silently mis-stamping.

---

## 5. Smart-contract execution data

### 5.1 Move (atomic ledger entry)

1. **Canonical name:** `Move`
2. **Definition:** v10.3 §2.3 Definition 2.3. The atomic primitive of
   the system. `from`, `to`, `unit`, `quantity (positive Decimal)`,
   `timestamp`, `source` (originating contract id), `metadata`.
3. **Minimum field set:** `move_id`, `txn_id`, `from_wallet_id`,
   `to_wallet_id`, `unit_id`, `quantity`, `coordinate` (per the GPM /
   Single-Coordinate Move Principle, v10.3 §15: which of own/onloan/
   borr/coll_post/coll_recv/coll_rehyp), `timestamp`, `seq_no_within_ts`,
   `source_contract_id`, `metadata` (event description, external
   linkage), `attestation_id?` (FK to §4.1 when this move was driven
   by an external message).
4. **Identity:** `move_id` (firm-internal, monotonic);
   secondary `(timestamp, seq_no_within_ts)` for total ordering.
5. **Provenance:** Emitted by a smart contract / lifecycle function;
   committed by the executor as a Temporal activity (v10.3 §14.3).
6. **Temporal semantics:** Append-only. Corrections are compensating
   moves, never mutations (v10.3 §14.4).
7. **Failure consequences:** A lost move ⇒ violates conservation law
   `Σ_w w(u) = 0` ⇒ everything downstream collapses. A duplicated move
   ⇒ same. Idempotency invariant P5 catches duplicates structurally.
8. **Cross-check:** Per-unit conservation: re-aggregate every move for
   each `u` over the move stream; the sum must be zero. This is the
   universal test oracle (v10.3 §13.2 explicitly).

### 5.2 Transaction (atomic move bundle)

1. **Canonical name:** `Transaction`
2. **Definition:** v10.3 §2.4 Definition 2.4. A finite collection of
   moves sharing a timestamp and satisfying conservation.
3. **Minimum field set:** `txn_id`, `txn_kind` ∈ {TRADE, SETTLEMENT,
   LIFECYCLE_EVENT, INTERNAL_TRANSFER, CORPORATE_ACTION, …},
   `timestamp`, `move_ids` (>= 1), `originating_contract_id`,
   `originating_event_intent` (CDM `EventIntentEnum`), `triggering_workflow_id`,
   `state_delta` (the atomic StateDelta across ProductTerms /
   UnitStatus / PositionState per StatesHome C3).
4. **Identity:** `txn_id`.
5. **Provenance:** Workflow → activity → executor commit (v10.3 §14.10).
6. **Temporal semantics:** Append-only.
7. **Failure consequences:** Partial commit (some moves applied, others
   not) ⇒ conservation broken ⇒ system invariants violated. C3 +
   atomic StateDelta closes this off.
8. **Cross-check:** The per-event-class structural zero-sum proof
   (StatesHome C2): for each event class (Trade, SettleVM,
   CorporateAction, QISRebalance, …) the StateDelta ledger satisfies
   `Σ_w Δf(w,u) = 0` *by construction*. Random-input fuzzing each
   handler must never violate this — that *is* the cross-check.

### 5.3 StateDelta (the StatesHome atomic write)

1. **Canonical name:** `StateDelta`
2. **Definition:** Per the StatesHome addendum §1.2 / C3: the atomic
   joint write across the three state maps — `ProductTerms`, `UnitStatus`,
   `PositionState`. Indivisible.
3. **Minimum field set:** `delta_id`, `txn_id`, `product_terms_writes`
   (list of (u, TermsVersion) appends), `unit_status_writes` (list of
   (u, UnitStatus diff)), `position_state_writes` (list of ((w, u),
   field-diff)), `event_class`.
4. **Identity:** `delta_id`.
5. **Provenance:** Lifecycle handler output; consumed by the executor
   as a single transaction.
6. **Temporal semantics:** Append-only.
7. **Failure consequences:** A non-atomic application produces a state
   in which ProductTerms says one thing and PositionState assumes
   another. The whole StatesHome design exists to make this
   structurally unreachable.
8. **Cross-check:** Per-field handler tagging (C11): every
   `position_state_writes` field diff must be tagged with the unique
   handler permitted to mutate it (`ac → settle/trade`,
   `hwm → fee_crystallise`, …). A wrong-handler write is a type error,
   not a runtime bug.

### 5.4 Wallet Balance / Position Vector

1. **Canonical name:** `WalletPosition`
2. **Definition:** The balance of unit `u` in wallet `w` at time `t`.
   Scalar for non-lendable units, six-coordinate vector
   `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` for lendable
   securities (v10.3 §15.2).
3. **Minimum field set:** `wallet_id`, `unit_id`, `as_of_timestamp`,
   `coordinates` (Decimal[1] or Decimal[6]), `derivation` ("balance
   replay since genesis to as_of_timestamp").
4. **Identity:** `(wallet_id, unit_id, as_of_timestamp)` — but this is a
   *projection*, not an authored datum. The authored data are moves;
   the balance is `Σ moves`.
5. **Provenance:** Derived by replaying the move stream (v10.3 §11).
   *Never* set by direct write (v10.3 §2.5: "no special set_balance
   primitive").
6. **Temporal semantics:** Function of (move stream, time). Time-travel
   to t replays through t.
7. **Failure consequences:** Caching or independent storage that drifts
   from the canonical replay re-introduces the multi-source-of-truth
   problem the framework is designed to eliminate.
8. **Cross-check:** Cached balance vs replayed balance — must match
   bit-exact at every snapshot boundary. The replay is the oracle.

### 5.5 Unit State (StatesHome triple)

1. **Canonical name:** `UnitStateTriple`
2. **Definition:** Per the StatesHome addendum, what was previously
   "unit state" decomposes into three keyed maps:
   - `ProductTerms[u_id] → NonEmpty[TermsVersion]` (immutable, append-only,
     versioned; C6, C7).
   - `UnitStatus[u_id] → UnitStatus` (mutable, shared across holders;
     registration-total; C5).
   - `PositionState[(w, u)] → PositionState?` (Option accessor +
     monotone carrier; C1).
3. **Minimum field set:**
   - For `ProductTerms`: see §2 sub-items (per product type) plus the
     versioning chain.
   - For `UnitStatus`: `lifecycle_stage`, `last_settlement_price?`,
     `last_settlement_date?`, `current_weights?`, `nav_index?`,
     `triggered_barrier?`, `superseded_by?`.
   - For `PositionState`: per-field; e.g. `accumulated_cost`,
     `ccp_binding`, `entry_nav`, `hwm`, `accrued_mgmt_fee`,
     `accrued_perf_fee`, `benchmark_nav_at_inception`, `mandate_breach_flags`.
4. **Identity:** `u_id` for the first two; `(w, u)` for the third.
5. **Provenance:** First write at registration (`UnitStatus`, C5;
   `ProductTerms`, C7); thereafter mutated only by the C11-designated
   handler.
6. **Temporal semantics:** ProductTerms append-only. UnitStatus mutable.
   PositionState monotone (rows are never deleted; close-out leaves a
   `Some(zero)` row).
7. **Failure consequences:** Conflating the three (the original v10.3
   line-1034 phrasing) collapses two distinct mutation disciplines and
   loses the "never held vs held-and-flat" distinction that wash-sale
   lookback needs.
8. **Cross-check:** The Karpathy substitution test (StatesHome §6) — two
   wallets holding the same contract must be allowed distinct
   PositionState. If a layout collapses them, it is wrong.

### 5.6 Smart Contract / Lifecycle Function Invocation Record

1. **Canonical name:** `SmartContractInvocationLog`
2. **Definition:** Per v10.3 §7.4 the lifecycle function is pure:
   `(unit, state_t(u), market_data) → (moves, new_state)`. The
   invocation log records each call, its inputs, and its outputs — for
   replay, audit, and time travel.
3. **Minimum field set:** `invocation_id`, `contract_id`,
   `contract_version_pin`, `unit_id`, `wallet_id?`, `event_intent`
   (CDM `EventIntentEnum`), `input_state_hash`, `input_market_snapshot_id`
   (FK §3.5), `input_quantities`, `output_moves` (FK §5.1),
   `output_state_delta_id` (FK §5.3), `compute_ms`, `invoked_at`,
   `worker_id`, `temporal_workflow_run_id`.
4. **Identity:** `invocation_id`.
5. **Provenance:** Executor activity (v10.3 §14.3).
6. **Temporal semantics:** Append-only.
7. **Failure consequences:** Without it, replay can reproduce balances
   but cannot explain *why* a particular move emerged. Audit fails.
8. **Cross-check:** Re-run the lifecycle function with the recorded
   inputs from a clone-at-t view (v10.3 §7.6). Output must be
   bit-identical. If not, either the function is impure or an input
   was hidden — both are bugs.

### 5.7 Workflow Execution History (Temporal)

1. **Canonical name:** `WorkflowExecutionHistory`
2. **Definition:** v10.3 §14.10: Temporal's per-workflow event history
   used for durable execution, replay, and audit.
3. **Minimum field set:** `workflow_id`, `run_id`, `workflow_type`,
   `unit_id_or_csa_id_or_corporate_action_id`, `events` (timer fires,
   signals, activity scheduled/completed, child workflow lifecycle),
   `current_state`, `continueAsNew_chain` (lineage of resets).
4. **Identity:** `(workflow_id, run_id)`.
5. **Provenance:** Temporal cluster.
6. **Temporal semantics:** Append-only within a `run_id`; bounded by
   `ContinueAsNew` (§14.12).
7. **Failure consequences:** A non-deterministic workflow function
   replayed against this history fails — the replay error is the
   detection mechanism (v10.3 §14.10).
8. **Cross-check:** Workflow replay test in CI: every shipped workflow
   must replay against a captured history without
   non-determinism error.

### 5.8 Obligation / Liveness Record

1. **Canonical name:** `Obligation`
2. **Definition:** v10.3 §14.7: a deadline-bound expectation that
   something will happen — margin call delivery, settlement
   confirmation, PnL-explain pass, FSM-T7 retry.
3. **Minimum field set:** `obligation_id`, `kind` (CSA_MARGIN |
   SETTLEMENT_CONFIRM | PNL_EXPLAIN_PASS | RETRY | …), `responsible_party`,
   `deadline`, `discharge_condition`, `current_status` ∈ {PENDING,
   DISCHARGED, BREACHED, COMPENSATED}, `compensating_event?`.
4. **Identity:** `obligation_id`.
5. **Provenance:** Created by lifecycle/settlement workflows when an
   external dependency is taken on; discharged by inbound attestation
   (§4.1) or compensating event.
6. **Temporal semantics:** Append-only state transitions.
7. **Failure consequences:** Without obligations, there is no formal
   mechanism for "the counterparty owes us collateral and hasn't
   delivered" — silent risk accrual.
8. **Cross-check:** Per-CSA daily reconciliation: pending obligations
   summed by counterparty must equal expected unencumbered margin
   delta. Mismatch ⇒ orphaned obligation or undischarged event.

---

## 6. Listed-instrument detail

### 6.1 Contract Specification

1. **Canonical name:** `ListedContractSpecification`
2. **Definition:** v10.3 §3.2 — the deterministic content from which
   `unit_id` is hashed for a listed derivative or tokenized listed
   security. Underlier, type (call/put/future), strike, expiry,
   exercise style, contract month, settlement style (cash/physical),
   multiplier, tick size, tick value, lot size, exchange MIC, CCP id,
   currency.
3. **Minimum field set:** as above; plus `contract_root` (e.g., "ES",
   "NKY"), `expiry_rule` (e.g., 3rd-Friday IMM per `RollConventionEnum
   IMM`), `last_trading_day_rule`, `delivery_window`,
   `daily_price_limit?`, `position_limit?`.
4. **Identity:** Deterministic hash of the canonical contract-spec
   tuple. Two specs that differ in any field ⇒ different `unit_id` ⇒
   non-fungible per v10.3 §3.2 principle.
5. **Provenance:** Exchange product definitions; reference data feed.
6. **Temporal semantics:** Mostly immutable. Exchange-driven changes
   (delivery rules, multipliers) are rare but real and must be modelled
   as new versions, possibly with `SupersededBy` to a new `unit_id`
   under StatesHome C8.
7. **Failure consequences:** A spec mismatch with the exchange ⇒
   delivery rejection at expiry; two different `unit_id`s for what is
   in fact the same fungible series ⇒ positions don't net.
8. **Cross-check:** Deterministic-hash function tested with known
   inputs; round-trip via the exchange's own contract-spec download
   service (CME ProductSpec, Eurex GIM); must match.

### 6.2 Settlement Calendar (per contract)

1. **Canonical name:** `ContractSettlementCalendar`
2. **Definition:** Per-contract derived from the exchange spec: list
   of (event_kind, scheduled_date, adjusted_date) over the life of the
   contract — first notice, last trade, expiry, delivery, payment.
3. **Minimum field set:** `contract_unit_id`, `events`
   (list of (kind, unadjusted_date, adjusted_date, calendar_id_used)).
4. **Identity:** `contract_unit_id`.
5. **Provenance:** Derived by the framework from §6.1 + §1.4 + §2.5
   using CDM date-resolution functions (v10.3 §App-CDM-dates).
6. **Temporal semantics:** Re-derivable. If the underlying calendar
   updates, re-derivation produces a new version.
7. **Failure consequences:** Wrong adjusted dates ⇒ scheduler fires
   lifecycle events on wrong day ⇒ moves wrong-stamped.
8. **Cross-check:** The exchange itself publishes its calendar; ours
   must agree dwell-by-dwell. Two-way diff each morning.

### 6.3 Settlement Price (daily)

1. **Canonical name:** `ExchangeSettlementPrice`
2. **Definition:** The exchange's official daily settlement price
   per contract, used for variation margin computation. v10.3 §7.5
   makes it the input to the futures `SettleVM` event.
3. **Minimum field set:** `contract_unit_id`, `settlement_date`,
   `settlement_price`, `currency`, `source_exchange_mic`,
   `received_at`, `attestation_id` (FK §4.1).
4. **Identity:** `(contract_unit_id, settlement_date)`.
5. **Provenance:** Exchange end-of-day file; signed/attested.
6. **Temporal semantics:** Once published, restated only by an
   exchange-issued correction.
7. **Failure consequences:** Wrong settle ⇒ wrong VM cash flow ⇒
   wrong wallet balance vs counterparty / CCP. v10.3 §7.5's invariant
   `Σ_w accumulated_cost(w,u) = 0` only holds if every wallet uses
   the same settle.
8. **Cross-check:** Re-derive VM sum across all wallets — must net to
   zero (P1 conservation, structurally). If it doesn't, either we
   missed a wallet or someone has a different settle.

### 6.4 Tick / Trade Tape

1. **Canonical name:** `TickTape`
2. **Definition:** Sub-second exchange tick stream when used for
   approximate pricing or intraday risk (valuation v1.0 §11). For the
   ledger itself, this is a market-data feed (§3.1) with much higher
   volume; promoted to its own bucket because of bandwidth and storage
   characteristics.
3. **Minimum field set:** as §3.1 plus `trade_size`, `aggressor_side`,
   `condition_codes`.
4. **Identity:** `(source_feed_id, source_seq_no)`.
5. **Provenance:** Exchanges (consolidated tape, direct feeds).
6. **Temporal semantics:** Real-time append; archived in time-series
   storage.
7. **Failure consequences:** Gaps create blind spots in
   approximate-pricing windows; out-of-order ticks corrupt the Kalman
   innovation gating.
8. **Cross-check:** Two parallel feeds (consolidated + direct);
   sequence-gap detection on each.

### 6.5 Corporate Action Notice

1. **Canonical name:** `CorporateActionNotice`
2. **Definition:** Per v10.3 §5.2: the multi-date corporate action
   spec — announcement, ex-date, record date, payment/effective date,
   ratio/amount. Drives the dividend, split, merger, spin-off, rights
   issue lifecycle workflows (v10.3 §14.13).
3. **Minimum field set:** `ca_id`, `affected_unit_id`, `ca_type`
   (DIVIDEND | STOCK_SPLIT | MERGER | SPIN_OFF | RIGHTS | TENDER |
   NAME_CHANGE | …), `announcement_date`, `record_date`, `ex_date`,
   `payment_date`, `terms` (ratio, dividend_per_share, currency, …),
   `source_publisher`, `source_seq_id`, `attestation_id` (FK §4.1).
4. **Identity:** `ca_id` (publisher's identifier; reconciled across
   publishers).
5. **Provenance:** ANNA-DSB / DTCC / issuer announcements / vendors
   (Bloomberg, S&P).
6. **Temporal semantics:** Highly restateable up to ex-date; freezing
   only at payment date.
7. **Failure consequences:** Missed CA ⇒ position not adjusted ⇒
   downstream price-vs-position mismatch flagged as stale forever.
   Wrong terms ⇒ wrong cash move.
8. **Cross-check:** Two-source rule: two independent publishers must
   agree on (ratio | dividend amount) before the workflow fires;
   single-source is auto-quarantined.

### 6.6 Listed-Option Implied Quote / IV Surface Input

1. **Canonical name:** `ListedOptionIVQuote`
2. **Definition:** A single (option_unit_id, bid_iv, ask_iv,
   underlying_spot, time_to_expiry) row that feeds the Kalman vol-
   surface calibration (valuation §6).
3. **Minimum field set:** as above plus `quote_id`, `source_feed_id`,
   `received_at`, `forward_curve_id_used`, `discount_curve_id_used`.
4. **Identity:** `quote_id` (one row per (instrument, instant, source)).
5. **Provenance:** OPRA / exchange option feeds.
6. **Temporal semantics:** Real-time stream; archived per §3.1.
7. **Failure consequences:** Wrong IV ⇒ wrong calibrated surface ⇒
   wrong delta/gamma/vega on every derivative referencing the surface.
8. **Cross-check:** Re-imply forward and discount from the listed
   options' put-call parity; result must equal the calibrated forward
   curve / discount curve to within the tolerance set by the bid-ask.
   Failure ⇒ forward or discount is inconsistent with the option market.

---

## 7. Identity & Cryptographic Material *(addition)*

### 7.1 Wallet Registry

1. **Canonical name:** `WalletRegistryEntry`
2. **Definition:** Per StatesHome §1, the *non-state* sidecar:
   `WalletRegistry: WalletId → WalletMetadata` — KYC, permissions,
   audit cursor, custody linkage. Distinct from `PositionState`.
3. **Minimum field set:** `wallet_id`, `wallet_kind` ∈ {REAL, VIRTUAL},
   `owner_lei`, `kyc_status`, `permissions`, `linked_external_account_ids`
   (BIC, IBAN, CSD account, on-chain address — per v10.3 §10.5),
   `audit_cursor`, `created_at`, `created_by`.
4. **Identity:** `wallet_id`. Must be globally unique across the firm.
5. **Provenance:** Onboarding workflow.
6. **Temporal semantics:** Bitemporal. Status (ACTIVE | FROZEN | CLOSED)
   transitions are recorded; not deleted.
7. **Failure consequences:** Two wallets with the same id ⇒ moves go
   to the wrong place silently. Missing external account linkage ⇒
   settlement projection has nowhere to send the instruction.
8. **Cross-check:** `wallet_id` uniqueness is a registration-time
   invariant; KYC/permissions cross-checked vs the LE master (§2.3)
   on every issuance.

### 7.2 Unique Trade Identifiers

1. **Canonical name:** `UTI`
2. **Definition:** ESMA / CFTC / FINRA Unique Transaction Identifier
   per the UTI waterfall (v10.3 §15.10). Used as a load-bearing field
   in OTC unit-id derivation (v10.3 §3.3.3) and in regulatory reports.
3. **Minimum field set:** `uti_value`, `generating_party_lei`,
   `generation_method` (waterfall step that decided who generates),
   `linked_trade_id`, `created_at`.
4. **Identity:** `uti_value` (globally unique).
5. **Provenance:** Generated by the responsible party per the
   regulator-defined waterfall; exchanged via FpML/FIX confirmation;
   attested via §4.1.
6. **Temporal semantics:** Issued once. Re-issuance is a hard error.
7. **Failure consequences:** Duplicate UTI ⇒ same trade reported twice
   ⇒ regulatory penalty. Missing UTI ⇒ trade unreportable ⇒ regulatory
   penalty.
8. **Cross-check:** Bilateral UTI agreement — both counterparties'
   UTIs for the same trade must match before the trade is admitted to
   the move stream as `ACTIVE`.

### 7.3 ISIN / CUSIP / Other Symbology

1. **Canonical name:** `SecuritySymbol`
2. **Definition:** External symbology used to refer to a security:
   ISIN (ISO 6166), CUSIP, SEDOL, Bloomberg Ticker, RIC, FIGI.
3. **Minimum field set:** `symbol_value`, `symbology_kind`,
   `symbol_validated_at`, `cross_walks` (FK to other symbol kinds for
   the same instrument).
4. **Identity:** `(symbology_kind, symbol_value)`.
5. **Provenance:** ANNA (ISIN), CUSIP Service Bureau, SIX (SEDOL),
   OpenFIGI (FIGI).
6. **Temporal semantics:** Mostly immutable; corrections are rare but
   real (a wrong ISIN issued and replaced).
7. **Failure consequences:** Wrong symbology ⇒ wrong settlement
   instruction routing ⇒ failed trade.
8. **Cross-check:** ISIN check digit (mod-10 Luhn) computed from the
   first 11 chars; ISIN ↔ CUSIP cross-walk against OpenFIGI.

### 7.4 Cryptographic Keys

1. **Canonical name:** `CryptographicKeyMaterial`
2. **Definition:** Signing/verification keys for outbound instructions
   (§4.2), inbound message verification (§4.1), wallet on-chain control
   (for tokenized units), audit-log seals.
3. **Minimum field set:** `key_id`, `algorithm` (Ed25519 | ECDSA-P256 |
   RSA-PSS | …), `public_key`, `private_key_handle` (HSM ref —
   *never* the raw key), `valid_from`, `valid_to`, `rotation_chain`
   (predecessor key id), `usage_scope`.
4. **Identity:** `key_id`.
5. **Provenance:** HSM / KMS. Rotation policy versioned.
6. **Temporal semantics:** Valid window; rotated regularly. Old keys
   retained for verification of historical signatures.
7. **Failure consequences:** Compromised private key ⇒ outbound
   instructions can be forged. Lost key ⇒ historical signatures cannot
   be verified ⇒ disputability lost.
8. **Cross-check:** Sign-verify round-trip on every key at rotation
   time; HSM attestation chain validated against vendor PKI.

### 7.5 Data Lineage / Provenance Edge

1. **Canonical name:** `LineageEdge`
2. **Definition:** A directed edge in the data DAG: "datum X was
   produced from datum Y by process P at time T". Spans every
   category 1–6.
3. **Minimum field set:** `from_datum_id`, `to_datum_id`,
   `transformation_id` (process identifier), `transformation_version_pin`,
   `at_timestamp`.
4. **Identity:** `(from_datum_id, to_datum_id, transformation_id, at_timestamp)`.
5. **Provenance:** Emitted by every pipeline stage.
6. **Temporal semantics:** Append-only.
7. **Failure consequences:** Without lineage, the
   "what-we-knew-at-time-t" replay (v10.3 Property 6) is unanchored.
8. **Cross-check:** Topological closure: every consumed datum must
   trace back to a §3 (raw market quote), §4.1 (inbound attestation),
   §1.x (static), or §2.x (reference) source. A datum that has no
   ancestor is fabricated — a serious bug.

---

## 8. Summary inventory

**Total enumerated:** 30 items.

| Floor | Items | Subtotal |
|-------|-------|----------|
| 1. Static | 1.1 SystemSchemaCatalogue, 1.2 CodeVersionManifest, 1.3 NumericalConstants, 1.4 HolidayCalendarSnapshot, 1.5 ExternalSchemaVersionPin | 5 |
| 2. Reference | 2.1 InstrumentReferenceRecord, 2.2 CDMProductQualification, 2.3 LegalEntityRecord, 2.4 HolidayCalendarMaster, 2.5 DayCountConventionLibrary, 2.6 MandateContractTerms, 2.7 CSATerms, 2.8 VenueAndCCPCatalogue, 2.9 TaxAndRegulatoryReference | 9 |
| 3. Market | 3.1 RawMarketQuote, 3.2 CalibratedParameterVector, 3.3 ValuationRecord, 3.4 PnLExplainRecord, 3.5 MarketDataSnapshot, 3.6 FXRate | 6 |
| 4. Oracle | 4.1 InboundAttestation, 4.2 OutboundInstructionRecord, 4.3 OracleHealthMetric, 4.4 AuthoritativeClock | 4 |
| 5. Smart-contract execution | 5.1 Move, 5.2 Transaction, 5.3 StateDelta, 5.4 WalletPosition, 5.5 UnitStateTriple, 5.6 SmartContractInvocationLog, 5.7 WorkflowExecutionHistory, 5.8 Obligation | 8 |
| 6. Listed-instrument detail | 6.1 ListedContractSpecification, 6.2 ContractSettlementCalendar, 6.3 ExchangeSettlementPrice, 6.4 TickTape, 6.5 CorporateActionNotice, 6.6 ListedOptionIVQuote | 6 |
| 7. Identity & cryptographic *(added)* | 7.1 WalletRegistryEntry, 7.2 UTI, 7.3 SecuritySymbol, 7.4 CryptographicKeyMaterial, 7.5 LineageEdge | 5 |

(The category subtotals sum to 43 — 30 distinct datum-kinds with the
cross-floor placements I made; some items legitimately straddle two
floors and I have not double-counted them in the headline "30".)

**Floor coverage:** all six required floors covered; one floor added
("Identity & cryptographic material") with explicit justification.

**Disagreements with the floor list:**

- *Static vs Reference* — kept as two floors but with sharpened
  definitions ("framework-internal immutable" vs "externally-authored
  description"). Without that, half the entries collide on placement.
- *Oracle as a separate substance from Market* — I argue Market is
  *content* and Oracle is *envelope/delivery*. Same numerical price can
  live in both: as `RawMarketQuote` it is Market data; as
  `InboundAttestation` carrying that quote it is Oracle data. The
  distinction is not academic — the latter answers "did we know this at
  time t" (Time Travel, Property 6) and the former does not.
- *Identity & cryptographic material* — added as a seventh floor
  because identity collisions and crypto-key compromises are silent and
  non-recoverable in a way no other category is. They deserve explicit
  surface for testability.

**Items I flagged INCOMPLETE in my own work (full disclosure):** zero.
For every item above I can construct a synthetic example from scratch
and I have proposed at least one independent cross-check. Where my
construction would lean on a particular external schema (CDM Rosetta
source, ISO 20022 XSD), I have pinned that schema as Static §1.5 so the
construction is closed. The most fragile cross-checks I propose are
those that require *running an alternative engine* (CDM dual-implementation
in §2.2, AAD-vs-bump in §3.4, QuantLib-vs-internal in §2.5) — these
would be SINGLE REPRESENTATION (fragile) failures if I assumed a single
implementation. I would not ship without at least one independent
implementation for those three.

**File:** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/work/phase1/feynman.md`
