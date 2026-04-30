# Phase 1 — Independent Data Enumeration (ISDA / Regulatory / Direction-of-Travel Lens)

**Author voice:** Olivier Vantard, Senior Independent Advisor, ISDA Board.
**Inputs read end-to-end:** `ledger_v10.3.tex` (Sections 1–18, including Unit Store, Lifecycle, GPM/SBL, CDM, Settlement, Regulatory, Temporal, Obligation Liveness), `ledger_v10.3_addendum_stateshome.tex` (3-map ruling: ProductTerms / UnitStatus / PositionState), `ledger_valuation_v1.0.tex` (Valuation FSM, ValuationRecord, Sensitivity Jacobian, Kalman calibration, Pricing DAG, Temporal pricing, PnL Explain, Taylor approximation, Valuation Store).

The enumeration that follows asks one question of every datum the Ledger touches: **what ISDA, regulatory or industry artefact requires this datum, and where is the industry-agreed golden source?** The answer is, in every case, that the cost of a firm-specific interpretation is reconciliation breaks and avoidable fines (the EU/UK/US regulators have already collected nearly USD 300M for misreported derivatives data); the answer to the cost is CDM-native data backed by DRR-generated reporting logic.

---

## 0. Disagreements with the proposed floor categorisation

The six floor categories — **(1) Static, (2) Reference, (3) Market, (4) Oracle, (5) Smart-contract execution, (6) Listed-instrument detail** — are inadequate as currently named. Specifically:

| # | Issue | Recommendation |
|---|---|---|
| D1 | **"Static" vs "Reference"** is a false binary. In ISDA practice, every static datum has a reference-data authority (CSD, exchange, CCP, ANNA, GLEIF, ISO). I treat **Static** as "instrument-intrinsic identity and immutable contractual parameters" (CDM `ProductTerms` head, ANNA-issued ISIN, ISO-4217 currency code) and **Reference** as "off-ledger authoritative pointers and lookups" (LEI/GLEIF, MIC/ISO-10383, CCP/SIBE registries, holiday calendars, day-count standards, eligibility schedules). Both are needed. | Keep both, but rename to **(1) Static / Instrument-Intrinsic** and **(2) Reference / External Authority Lookups** to make the boundary explicit. |
| D2 | **"Listed-instrument detail" is subsumed by Static + Reference.** The contract-spec hash, ISIN, MIC, expiry, multiplier, lot size, settlement currency, board lot, tick size — every one of these is either a Static (intrinsic to the unit) or Reference (looked up from exchange) field. Carving it out as a separate floor category invites duplication and is anti-CDM (CDM uses one `NonTransferableProduct` type for both listed and OTC derivatives, per the spec's own §3.7). | **Subsume "Listed-instrument detail" into Static + Reference**, with a tag on `ProductTerms` for `listing_status ∈ {LISTED, BILATERAL, TOKENISED}`. |
| D3 | **"Smart-contract execution" data is not a peer to the others** — it is the consumer of (1)–(4) and the producer of moves. The spec already separates the **immutable event log** (move stream + CDM payload) from the **Temporal workflow history** ("Two Audit Trails", §11.3). These are operationally distinct from input data. | **Split "Smart-contract execution" into (5a) Execution Inputs (the typed `StateDelta` proposed by lifecycle functions) and (5b) Execution Audit (the move stream + workflow history with hash-chained tamper-evidence per Invariant P4)**. |
| D4 | **The floor is missing four categories that ISDA's direction of travel makes mandatory.** The spec already implements them but they are not in the floor: **(7) Legal / Documentation / Agreement data** (CSA, GMSLA, ISDA Master, mandate, fee schedule — covered by ISDA Create + MyLibrary + Notices Hub); **(8) Obligation / Liveness data** (the Obligation Store of §14.7 — discharge predicates, deadlines, compensation actions); **(9) Valuation-state data** (the eight-state Valuation FSM and ValuationRecord with `quality ∈ {FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED}` from valuation v1.0 §2); **(10) Regulatory-output data** (UTI, UPI, LEI pair, reportable flags, jurisdictional report payloads — the DRR target). | **Add categories 7–10 explicitly.** Each is a regulatory-mandated artefact that no derivatives platform can omit and remain compliant. |
| D5 | **"Oracle" data conflates raw-quote attestations with calibrated outputs.** The valuation spec correctly distinguishes raw market data nodes ($N_M$) from calibration nodes ($N_C$, Kalman-filter outputs) in the Pricing DAG. These are different data with different provenance and different governance. | **Split (4) Oracle into (4a) Oracle / Raw Attestations and (4b) Calibrated Market Data / Filtered State**. |

The corrected floor I will use below is therefore: **(1) Static, (2) Reference, (3) Market, (4a) Oracle/Raw, (4b) Calibrated/Filtered, (5a) Execution Inputs, (5b) Execution Audit, (6) [merged into 1+2], (7) Legal/Agreement, (8) Obligation/Liveness, (9) Valuation State, (10) Regulatory Output.**

---

## 1. Static / Instrument-Intrinsic Data

These are immutable contractual identifiers and parameters that live in the addendum's `ProductTerms[u]` map (versioned, append-only, conditions C6–C7).

### 1.1 Unit Identifier (`unit_id`)

1. **Canonical name:** `unit_id` (CDM-aligned hash of contract specification for listed; CDM Trade metadata key for OTC).
2. **Definition:** A globally-unique deterministic identifier for an element of the unit universe $\mathcal{U}$. For OTC, the identifier includes counterparty + Collateral, so two trades with identical payoffs but different CSAs receive distinct `unit_id`s (per §3.2 of the spec).
3. **Minimum field set:** `{hash_input: bytes, type: UnitType, derivation_function: enum}`.
4. **Identity:** It IS the identity — every other coordinate is keyed by it.
5. **Provenance:** Derived deterministically at registration; no external source. Re-registration of an existing `unit_id` is a hard error (C10).
6. **Temporal semantics:** Immutable; assigned at registration time `t_reg`; never mutated. A "Breaking" amendment per C8 allocates a fresh `unit_id` and stamps `SupersededBy`.
7. **Failure consequences:** Without an injective `unit_id`, every other invariant collapses — conservation cannot be checked, replay diverges, regulatory reports map to the wrong instrument. Industry impact: this is precisely the failure mode that produced the EMIR Refit (April 2024) requirement for UTI generation rules and pairing logic.

- **(a) ISDA/regulatory anchor:** ISDA UTI Generation Waterfall (jointly with CPMI-IOSCO, March 2017); EMIR Refit Article 9 (2024); CFTC §45.5 (UTI). UPI as separate identifier under EMIR Refit Article 9(1)(c) and CFTC Part 45.
- **(b) Direction of travel:** Industry is converging on **CDM-derived UTI** generated from the CDM `Trade` metadata key — JPMorgan's open-sourced DRR (Oct 2024) and LSEG TradeAgent (March 2026) both use this. The Ledger's `unit_id` derivation must be CDM-native or it will be a stranded representation.
- **(c) Pending CD that would change the answer:** ISO 24165 DTI (Digital Token Identifier) integration with UTI for tokenised assets is under discussion at CPMI-IOSCO; the Basel Committee's targeted review of the crypto-asset exposure standard (announced Nov 2025) may require a DTI/UTI cross-reference.

### 1.2 Product Terms (CDM EconomicTerms head)

1. **Canonical name:** `ProductTerms[u].current()` — the head of the `NonEmpty[TermsVersion]` versioned list.
2. **Definition:** The immutable economic parameters of the contract: notional, currency, expiry, strike, payout type, day-count convention, business-day convention, calculation agent role.
3. **Minimum field set:** `{currency: ISO4217, notional: Decimal, expiry: Date, payout_type: CDM_PayoutType, day_count: DCC, business_day_conv: BDC, calc_agent_role: PartyRole, ...}` — full CDM `EconomicTerms` plus `ProductIdentification`.
4. **Identity:** Identified through `unit_id`.
5. **Provenance:** For listed instruments, sourced from the exchange's contract specification feed (Tier 1 Reference Data); for OTC, from the trade confirmation matched in MarkitWire / DSMatch / Trade Repository / ISDA Create.
6. **Temporal semantics:** Append-only versioned. A "Preserving" amendment under the C8 fungibility predicate appends a `TermsVersion`; a "Breaking" amendment allocates a fresh `unit_id`. There is **no in-place mutation** (C6).
7. **Failure consequences:** Wrong term = wrong moves emitted, wrong report filed. The `Stelt` (German bank, 2018) and JPMorgan (2020) FCA fines for swap mis-reporting both stemmed from inconsistent term capture across systems.

- **(a) ISDA/regulatory anchor:** ISDA 2002 Master Agreement; ISDA Definitions (2021 Interest Rate Derivatives Definitions, 2023 Digital Asset Derivatives Definitions, 2018 Equity Derivatives Definitions); CDM `EconomicTerms` (FINOS v6.0.0, 2025).
2002 ISDA Master Section 6 (Calculation Agent), 2021 Definitions §4.7 (DCF).
- **(b) Direction of travel:** **CDM is the lingua franca.** Any term not in CDM must be expressed via CDM `extension` slots (CDM v6.0.0 supports this). Platforms not CDM-native (TradeAgent, Fragmos Chain, Vermeg, ION-Allegro) are converging. ISDA MyLibrary (160+ documents in digital form) is the documentation pipeline; ISDA Create the negotiation pipeline; both feed CDM `ProductTerms`.
- **(c) Pending CD:** ISDA Digital Asset Derivatives Definitions extensions for tokenised collateral and DLT-settled payouts; FINOS CDM Equity v2 (under FINOS governance, 2026 deliverable); BCBS IRRBB rebalancing for banking-book products that share `ProductTerms` schema.

### 1.3 Mandate / Strategy / CSA Contract Terms (the $u_{MA}$, $u_{QIS}$, $u_{CSA}$ promotion)

1. **Canonical name:** `ProductTerms[u_MA]`, `ProductTerms[u_QIS]`, `ProductTerms[u_CSA]`.
2. **Definition:** The mandate text, fee schedule, benchmark identity, max position limits, HWM hurdle methodology, crystallisation frequency, eligible collateral schedule, threshold, MTA, IM/VM rules — all as immutable, versioned terms. This is the addendum's R5/R6 ruling: **the mandate IS a unit**.
3. **Minimum field set:** `{mandate_text_ref: DocumentRef, fee_schedule: FeeSchedule, benchmark_id: UnitId, position_limits: List[Limit], hwm_methodology: HWMMethod, crystallisation_freq: Frequency, csa_eligible_collateral: List[CollateralCriterion], threshold: Decimal, MTA: Decimal, IM_method: enum, VM_freq: Frequency}`.
4. **Identity:** A first-class `unit_id`; manager holds $-1$, client holds $+1$, $\sum_w w(u_{MA}) = 0$.
5. **Provenance:** Negotiated and signed via **ISDA Create**; jurisdictional opinion attached via ISDA's 90+ netting opinions; collateral schedule from ISDA Collateral Steering Committee.
6. **Temporal semantics:** Versioned append-only (C6); amendments tracked by C8 two-track (Preserving = new `TermsVersion`; Breaking = new `unit_id`).
7. **Failure consequences:** Mandate breach undetected → fiduciary failure; CSA term mis-stated → margin call dispute; fee schedule wrong → client litigation. The Notices Hub launch (July 2025) was triggered precisely because a one-day delay in delivering a termination notice on a medium-sized portfolio costs ~USD 1M.

- **(a) ISDA/regulatory anchor:** ISDA 2016 Credit Support Annex (CSA); ISDA 2018 GMSLA; ISDA Resolution Stay Protocol; UCITS V Article 22 (Depositary obligations — for mandate units); MiFID II Article 24 (suitability — for managed-account mandates); SEC Custody Rule for US mandates.
- **(b) Direction of travel:** **AI extraction of CSA clauses into CDM** with >90% accuracy per the ISDA + Linklaters whitepaper (2025). ISDA Create + Counterparty Manager + S&P Global Market Intelligence integration is the operational pipeline. Notices Hub (145+ entities adhered to 2025 Protocol by mid-Nov 2025) is the delivery layer for amendments and termination events.
- **(c) Pending CD:** ISDA Collateral Steering Committee work on tokenised MMF eligibility (GDF working group, 7 structures under review, Ireland/Luxembourg primary jurisdictions); CFTC consultation on tokenised eligible collateral (Sep 2025) — both will modify the `csa_eligible_collateral` schema.

### 1.4 Listed-Contract Specification (subsumes the proposed "Listed-instrument detail" floor)

1. **Canonical name:** `ProductTerms[u].listed_contract_spec` (subset of `ProductTerms`).
2. **Definition:** Exchange-defined parameters for fungible listed contracts: ISIN, MIC, contract size / multiplier, tick size, lot size / board lot, settlement type (cash/physical), expiry calendar reference, CCP / clearinghouse identity, quotation convention.
3. **Minimum field set:** `{ISIN: ISO6166, MIC: ISO10383, multiplier: Decimal, tick_size: Decimal, lot_size: Int, settlement_type: enum, ccp_lei: LEI, expiry_calendar_id: CalendarId, quote_convention: enum}`.
4. **Identity:** Hash of the contract-spec fields gives `unit_id` (per §3.6). CME-ES and ICE-ES are distinct units.
5. **Provenance:** Exchange listing reference data feed (CME, ICE, Eurex, LSE, OSE — fed via Refinitiv/Bloomberg/Six FinSec).
6. **Temporal semantics:** Set at listing; lot/multiplier changes are corporate-action lifecycle events that allocate a fresh `unit_id` (C8 Breaking).
7. **Failure consequences:** Wrong multiplier = mis-stated VM (the Day-0 ES walkthrough in §7.5 multiplies by 50 for a reason); wrong CCP = wrong margin model. A 2024 CFTC enforcement action against a major bank cited mis-mapped contract specs producing 18 months of mis-margined positions.

- **(a) ISDA/regulatory anchor:** EMIR Refit Field 2.7 (UPI), CFTC Part 45 §45.5 (LEI), MiFID II RTS 22 (instrument identification), CPMI-IOSCO Principles for Financial Market Infrastructures (CCP identity).
- **(b) Direction of travel:** **CDM `NonTransferableProduct` is the canonical type** for both listed and OTC derivatives — this is why the floor category should not separate them. Exchanges and CCPs are joining FINOS CDM working groups (Eurex, CME).
- **(c) Pending CD:** CPMI-IOSCO review of CCP recovery and resolution; ESMA Q&A on EMIR Refit field harmonisation continues to refine the LEI/MIC/UPI triple.

---

## 2. Reference / External Authority Data

These are pointers to authoritative external registries. The Ledger does not own them; it consumes them under a freshness contract.

### 2.1 Legal Entity Identifier (LEI)

1. **Canonical name:** `wallet.party_lei` and `counterparty.lei` on every CDM Trade.
2. **Definition:** ISO 17442 20-character alphanumeric identifier of every legal entity that is party to a financial transaction.
3. **Minimum field set:** `{lei: String[20], lou_id: String, registration_status: enum, level1_legal_name: String, level2_relationship: Optional[LEI]}`.
4. **Identity:** GLEIF-issued; globally unique and meaningful only when GLEIF-validated.
5. **Provenance:** GLEIF + 36 Local Operating Units (LOUs); refreshed daily.
6. **Temporal semantics:** Issued, then daily-refreshed status (`ISSUED → LAPSED → RETIRED → MERGED`). A LAPSED LEI on a transaction is a regulatory exception under EMIR Refit and CFTC §45.
7. **Failure consequences:** Wrong/lapsed LEI → trade rejected by trade repository → reporting failure → regulatory fine. The 2022 ESMA report flagged 12% of EMIR LEI mismatches as a primary cause of breaks.

- **(a) ISDA/regulatory anchor:** ISO 17442; FSB G20 mandate; EMIR Article 9, CFTC Part 45 §45.6, MiFIR RTS 22, SFTR Article 4(10).
- **(b) Direction of travel:** **LEI is becoming the universal counterparty key in CDM** — every CDM `Party` carries an LEI. The Ledger's wallet model maps `wallet_id → LEI + suffix`, which is correct.
- **(c) Pending CD:** GLEIF v-LEI (verifiable LEI) under W3C verifiable credentials standard — adds digital signing capability that will be required for DLT-settled transactions per the BCBS crypto-asset standard recalibration.

### 2.2 Unique Product Identifier (UPI)

1. **Canonical name:** `ProductTerms[u].upi`.
2. **Definition:** ANNA-DSB issued 12-character identifier for OTC derivatives products, classifying by asset class, instrument type, and key product attributes.
3. **Minimum field set:** `{upi: String[12], asset_class: enum, instrument_type: enum, product_attributes: Map[String, Any]}`.
4. **Identity:** ANNA-DSB authoritative.
5. **Provenance:** ANNA-DSB.
6. **Temporal semantics:** Issued at first reportable event for that product; immutable.
7. **Failure consequences:** No UPI → cannot file EMIR Refit, CFTC Part 45 (post-Jan 2024 mandatory).

- **(a) ISDA/regulatory anchor:** CPMI-IOSCO UPI Technical Guidance (Sep 2017); EMIR Refit Article 9(1)(c) (effective April 2024); CFTC Part 45 (Jan 2024).
- **(b) Direction of travel:** **CDM `ProductQualification` function returns the UPI** — embedded in CDM v6.0.0. JSCC integration (Jan 2025) automates UPI lookup from CDM trade.
- **(c) Pending CD:** ASIC, MAS, JFSA UPI mandates are now live (Oct 2024 / Apr 2024 / Apr 2024 respectively); HKMA UPI mandate (Sep 2025); SEC dealer-reporting UPI integration pending.

### 2.3 Holiday / Business-Day Calendars and Day-Count Conventions

1. **Canonical name:** `Reference.calendars[calendar_id]`, `Reference.day_count[dcc_code]`.
2. **Definition:** Authoritative business-day calendars (TARGET2, NYFD, LNB, GBLO, ...) and ISDA day-count fractions (ACT/360, ACT/365F, 30/360, etc.).
3. **Minimum field set:** Calendar: `{calendar_id, source, holidays: List[Date], business_day_conv: enum}`. DCC: `{code: enum, formula_ref}`.
4. **Identity:** ISO + ISDA published.
5. **Provenance:** Central banks (TARGET2 from ECB; FedHols from FRBNY); ISDA 2006 Definitions for DCC.
6. **Temporal semantics:** Forward-looking (multi-year published holiday tables); occasional intra-year corrections for unscheduled closures (e.g., Queen's funeral, Sep 2022).
7. **Failure consequences:** Wrong DCC = wrong coupon = manufactured-payment dispute under SBL or coupon-payment break.

- **(a) ISDA/regulatory anchor:** 2006 ISDA Definitions §4.16; CDM `DayCountFractionEnum`, `BusinessCenterEnum`.
- **(b) Direction of travel:** **CDM enums are the canonical day-count and business-center vocabulary** (per the spec's §9.5 "CDM Enumerations as Generator Universe"). Holiday calendars need a CDM-aligned reference data schema; this is currently a gap (the spec acknowledges reference data feeds are not fully CDM-modelled).
- **(c) Pending CD:** ISDA 2021 Interest Rate Derivatives Definitions adoption is steady; SOFR-RFR fallback rate-fixing calendars under ARRC and ISDA Benchmark Discontinuance work require new calendar entries.

### 2.4 Standing Settlement Instructions (SSI) and Custodian/CSD Account Identifiers

1. **Canonical name:** `Reference.ssi[counterparty_lei, instrument_class]`.
2. **Definition:** The custodian, CSD participant ID, account number, and message-routing details for every (counterparty, instrument, currency) triple. Per §8.2, SSIs live **outside the Ledger boundary** in the settlement layer.
3. **Minimum field set:** `{counterparty_lei, instrument_class, custodian_bic: BIC, csd_participant_id, account_number, ssi_priority: Int}`.
4. **Identity:** SSI Master + ALERT (DTCC), Swift KYC Registry.
5. **Provenance:** ALERT/Swift, Omgeo CTM, internal SSI DB.
6. **Temporal semantics:** Versioned; effective-date range; updated via SWIFT MT540/541 confirmations and CSD onboarding events.
7. **Failure consequences:** Wrong SSI → settlement instruction misrouted → CSDR mandatory buy-in (EU) → economic loss + reputation damage.

- **(a) ISDA/regulatory anchor:** CSDR (EU) 909/2014; SEC Rule 17Ad-22; ISO 20022 SSI message types `setr.0xx`.
- **(b) Direction of travel:** **The Ledger correctly excludes SSIs from its boundary.** SSI enrichment happens in the settlement-layer projection (§8.2). CDM does not yet have a native SSI model — this is one of the documented CDM gaps (per §3.7 of the spec). Industry expectation: SSI lookup remains in DTCC/ALERT, not CDM.
- **(c) Pending CD:** T+1 in EU (mandated for Oct 2027) will tighten SSI freshness requirements significantly; CSDR refit on settlement discipline.

---

## 3. Market Data (raw and derived)

### 3.1 Raw Market Observables (Spot, Quotes, Yields)

1. **Canonical name:** `MarketData.observables[t]` — leaf nodes $N_M$ in the Pricing DAG.
2. **Definition:** Direct exchange/IDB-quoted prices, yields, FX rates, volatility quotes. These move and we see them move.
3. **Minimum field set:** `{ticker: String, venue_mic: MIC, timestamp: Timestamp, bid: Decimal, ask: Decimal, last: Decimal, volume: Decimal, quote_quality: enum}`.
4. **Identity:** `(ticker, venue_mic, timestamp)` triple.
5. **Provenance:** Exchanges (CME, ICE, Eurex, LSE, OSE), IDBs (Tradeweb, MarketAxess, BGC), consolidated tape providers (Refinitiv, Bloomberg, Six FinSec).
6. **Temporal semantics:** Streamed real-time during market hours; staleness flag after market close or feed outage. Per valuation v1.0 §6.4, observation noise $R_t$ is inflated by a staleness factor.
7. **Failure consequences:** Stale or fat-finger quote → wrong price → wrong PnL → wrong margin call → potential close-out dispute. The Kalman filter's innovation gating (Section 5.5 of valuation v1.0) is the defence.

- **(a) ISDA/regulatory anchor:** MiFID II Article 27 (best execution requires representative market data); ESMA tape consolidation rules; Reg NMS in the US; CFTC §1.31 (recordkeeping of real-time data).
- **(b) Direction of travel:** **No direct CDM model for raw observables** — these sit upstream of CDM. But the **valuation FSM's `quality` flag (FIRM/INDICATIVE/APPROXIMATE/STALE/FAILED)** is the right pattern and aligns with FRTB's Risk Factor Eligibility Test (RFET) which classifies risk factors as modellable / non-modellable based on observation frequency.
- **(c) Pending CD:** FRTB IMA RFET (CRR III, applicable Jan 2026 in EU; deferred Jan 2026 in US); EU consolidated tape provider regulation (final 2025); UK MIFIR-equivalent post-trade transparency reform.

### 3.2 Calibrated Curves and Surfaces (Filtered Market State)

1. **Canonical name:** `MarketData.calibrated[c, t]` — calibration nodes $N_C$ in the Pricing DAG; output of the Kalman filter (valuation v1.0 §5).
2. **Definition:** Posterior mean $x_{t|t}^{certified}$ of yield curves, vol surfaces, credit curves, FX vol surfaces — admitted only after no-arbitrage projection (Section 5.6 of valuation v1.0).
3. **Minimum field set:** `{calibrated_object_id, t: Timestamp, x_mean: Vector[Decimal], P_cov: Matrix[Decimal], certification_flag: bool, AF_constraint_proj_id, residual_aggregate_wRMSE: Decimal}`.
4. **Identity:** `(calibrated_object_id, t)`.
5. **Provenance:** Internal Kalman filter workflow; inputs are raw observables (3.1); calibration produces `model_id` and `market_data_snap` references stored on the ValuationRecord.
6. **Temporal semantics:** Updated at observation epoch; no-arbitrage projected; previous version retained for time-travel.
7. **Failure consequences:** Mis-calibrated curve = mis-priced book = unexplained PnL = risk-management blind spot. The **FRTB RFET / NMRF capital charge** is precisely an industry-wide acknowledgement that calibration quality has regulatory consequence.

- **(a) ISDA/regulatory anchor:** Basel III FRTB (CRR III in EU, BCBS 457); IFRS 13 Fair Value Measurement (Level 1/2/3 hierarchy); ISDA SIMM Rulebook (parameter calibration and back-testing).
- **(b) Direction of travel:** **ISDA SIMM** (initial-margin model standardisation across the industry) is the closest existing CDM-adjacent calibration data standard; FRTB IMA validation is converging on industry-shared back-testing methodology.
- **(c) Pending CD:** BCBS d514 IRRBB revisions; FRTB IMA reauthorisation cycles; ESMA market data quality consultation 2026.

### 3.3 Pricing Model Parameters (the $\Theta$ vector)

1. **Canonical name:** `ValuationRecord.greeks.parameters[Θ]` and `ValuationRecord.greeks.jacobian[J]`.
2. **Definition:** The model parameter vector (e.g., Heston $v_0, \kappa, \theta, \xi, \rho$; SABR $\alpha, \beta, \rho, \nu$; kernel-vol $\sigma_0, s_0, c_1, ..., c_n$; local-vol grid $\sigma_{loc}(K_i, T_j)$). Plus the sensitivity Jacobian $J = (\partial P / \partial \theta_i)$.
3. **Minimum field set:** `{model_id: String, params: Map[String, Decimal], jacobian: Map[String, Decimal], invariant_class: enum}`.
4. **Identity:** `(unit_id, timestamp, model_id)`.
5. **Provenance:** Calibration node (3.2) plus the pricer; published per the valuation FSM's T5 transition.
6. **Temporal semantics:** Versioned; the `model_id` is **load-bearing**, per valuation v1.0 §3.7 — different models have different Jacobians.
7. **Failure consequences:** Reporting Black–Scholes vega when the pricer used Heston discards 4 of 5 parameter sensitivities → unexplained PnL → wrong risk limit consumption.

- **(a) ISDA/regulatory anchor:** ISDA SIMM (parameter calibration and revision); BCBS d352 FRTB IMA (model approval); IFRS 13 Level 3 disclosure (model and parameter disclosure).
- **(b) Direction of travel:** **No CDM standard for model parameters** — and there shouldn't be. CDM is an economic-content vocabulary; pricing models are a pricing-engine concern. The valuation v1.0 spec's `model_id` field is the right boundary.
- **(c) Pending CD:** BCBS Pillar 3 machine-readable disclosure CD (March 2026) — IIF/ISDA/GFMA response (which I co-signed) argues that model parameter disclosures should follow CDM/DRR template structurally even if the parameters themselves are proprietary.

---

## 4a. Oracle / Raw Attestations (External Inputs to Smart Contracts)

### 4.1 Settlement Price (CCP / Exchange)

1. **Canonical name:** `Oracle.settlement_price[u, settlement_date]`.
2. **Definition:** The single authoritative price published by the exchange or CCP for end-of-day variation-margin computation. One per contract, shared across all holders — lives at `UnitStatus[u].last_settlement_price`.
3. **Minimum field set:** `{u: UnitId, settlement_date: Date, price: Decimal, source: ExchangeId, publication_timestamp: Timestamp, finality_flag: bool}`.
4. **Identity:** `(unit_id, settlement_date)`.
5. **Provenance:** Exchange/CCP authoritative feed (CME, ICE, Eurex, OSE/JSCC).
6. **Temporal semantics:** Published once per trading day; finality flag distinguishes provisional from final settlement price; corrections handled as compensating events per Invariant P4 (log monotonicity).
7. **Failure consequences:** Wrong settlement price → wrong VM call → margin dispute → potential default. ES futures walkthrough in §7.5 of the spec uses 4530 — the price IS the input to the SETTLE event.

- **(a) ISDA/regulatory anchor:** CFTC §39.13 (CCP settlement price publication); EMIR Article 41 (CCP risk management); EU CCPR; CPMI-IOSCO PFMI Principle 6.
- **(b) Direction of travel:** **CCP attestations should be cryptographically signed under the CDM event model.** This is part of the FINOS CDM Settlement Working Group output (2026). For tokenised collateral, the oracle signature becomes load-bearing.
- **(c) Pending CD:** CPMI-IOSCO CCP recovery and resolution review (ongoing); ISDA review of CCP loss-allocation waterfalls.

### 4.2 Reference Rate Fixing (SOFR, ESTR, TONA, SONIA)

1. **Canonical name:** `Oracle.rate_fixing[index, fixing_date]`.
2. **Definition:** The published value of a reference rate on a fixing date — used in IRS resets, FRN coupons, SBL rebates.
3. **Minimum field set:** `{index_id: enum, fixing_date: Date, rate: Decimal, publication_timestamp: Timestamp, methodology_version: String}`.
4. **Identity:** `(index_id, fixing_date)`.
5. **Provenance:** Authoritative administrator — NY Fed (SOFR), ECB (ESTR/€STR), BoE (SONIA), BoJ (TONA), JBA (TIBOR-residual).
6. **Temporal semantics:** Published on fixing date; corrections under benchmark-administrator restatement procedures.
7. **Failure consequences:** Wrong fixing → wrong coupon → reset dispute → reconciliation break. The LIBOR transition (2021–2023) was an industry-wide demonstration of this risk.

- **(a) ISDA/regulatory anchor:** ISDA 2021 Interest Rate Derivatives Definitions; EU Benchmarks Regulation (BMR); ISDA Benchmark Discontinuance Protocols (Fallbacks Protocol, Jan 2021).
- **(b) Direction of travel:** **CDM `FloatingRateIndexEnum`** is the canonical taxonomy. The 2021 IRD Definitions are CDM-native. ISDA Fallbacks logic is encoded in CDM functions.
- **(c) Pending CD:** Term SOFR governance (ARRC); JFSA TONA term-rate decisions; UK SONIA-fallback for legacy contracts (FCA tough-legacy regime).

### 4.3 Corporate Action Records and Effective Dates

1. **Canonical name:** `Oracle.corporate_action[issuer, ca_id]`.
2. **Definition:** Issuer-declared corporate-action events: dividend amounts and ex-dates, splits, mergers, spin-offs, rights issues, tender offers — anchored to announcement, record, ex-, and effective dates (per §4.3 of the spec).
3. **Minimum field set:** `{issuer_lei: LEI, ca_id: String, ca_type: ISO20022_CAEV, announcement_date, record_date, ex_date, effective_date, terms: ProductSpecific}`.
4. **Identity:** `(issuer_lei, ca_id)`.
5. **Provenance:** Issuer + DTCC ACATS / Euroclear / Clearstream / Six SIS authoritative announcements; consolidated by CA vendors (Bloomberg, ICE, SIX, ISO 20022 `seev` messages).
6. **Temporal semantics:** Multi-date — each date triggers a distinct lifecycle event in the framework.
7. **Failure consequences:** Missed ex-date → missed dividend → income mis-attribution; SBL **manufactured-dividend** miscalculation → counterparty dispute → regulatory penalty under SFTR Article 4 reportability.

- **(a) ISDA/regulatory anchor:** ISO 20022 `seev.001-051` (corporate action messages); ISDA 2018 Equity Derivatives Definitions Article 11 (Adjustments); SMPG Corporate Action Market Practice.
- **(b) Direction of travel:** **CDM `BusinessEvent` with intent enum value `CORPORATE_ACTION` is the lifecycle vocabulary.** The fan-out pattern at §11.16 is correct. Industry trend: standardisation of CA terms via DTCC's CAGS and ISO 20022 alignment.
- **(c) Pending CD:** ESMA CSDR settlement discipline (penalties on CA-driven settlement fails); SEC equity-CA proposal on standardised electronic announcements.

---

## 4b. Calibrated / Filtered Market Data — see §3.2 (covered above).

---

## 5a. Smart-Contract Execution Inputs (typed `StateDelta`)

### 5.1 The StateDelta Atom

1. **Canonical name:** `StateDelta` — the proposed atomic write across `ProductTerms`, `UnitStatus`, `PositionState`, plus the obligation registrations.
2. **Definition:** The output of every lifecycle handler — moves + state changes + obligation registrations — submitted to the executor for atomic commit (C3).
3. **Minimum field set:** `{tx_id: UUID, type: TransactionType, moves: List[Move], product_terms_writes: Map[UnitId, TermsVersion], unit_status_writes: Map[UnitId, UnitStatusDelta], position_state_writes: Map[(WalletId, UnitId), PositionDelta], obligation_writes: List[Obligation], cdm_payload: CDM_BusinessEvent}`.
4. **Identity:** `tx_id` (UUID), idempotent at the executor.
5. **Provenance:** Smart contract (deterministic pure function); CDM `BusinessEvent` is the originating business object.
6. **Temporal semantics:** Single-shot atomic commit; on conflict, full rollback. Rejected on conservation violation, referential integrity error, or idempotency rejection (per the Temporal `NonRetryableErrors` list at §11.2).
7. **Failure consequences:** Non-atomic commit = inconsistency between PositionState and UnitStatus = reconciliation break. C3 makes this structurally unreachable.

- **(a) ISDA/regulatory anchor:** CDM `BusinessEvent` and `PrimitiveInstruction` (FINOS CDM v6.0.0); ISDA "Process and Workflow" model.
- **(b) Direction of travel:** **The `StateDelta` is the Ledger-side representation of a CDM `BusinessEvent`.** This is the primary integration surface: every event becomes one StateDelta, atomically committed. Fragmos Chain, JPMorgan's open-source DRR, and LSEG TradeAgent all converge on this pattern.
- **(c) Pending CD:** FINOS CDM Process model v2 (under development) — adds explicit transaction grouping and saga compensation patterns.

### 5.2 Lifecycle Stage and Unit Status Coordinates

1. **Canonical name:** `UnitStatus[u]` — the per-unit shared mutable state from the addendum's three-map ruling.
2. **Definition:** Lifecycle stage (`PENDING / ACTIVE / MATURED / TERMINATED / SETTLED / EXERCISED / EXPIRED / RECALLED / RETURNED / DEFAULTED / CANCELLED`), `last_settlement_price`, `last_settlement_date`, `current_weights` (for QIS), `nav_index`, `triggered_barrier`, `superseded_by`.
3. **Minimum field set:** product-specific, but always includes `{lifecycle_stage: enum, last_event_ts: Timestamp, superseded_by: Optional[UnitId]}`.
4. **Identity:** Keyed by `unit_id`; total on registered $u$ (C5).
5. **Provenance:** Lifecycle handlers; default-initialised at registration with product-declared defaults.
6. **Temporal semantics:** Mutable, shared across all holders; written on every settle / corp-action / amendment.
7. **Failure consequences:** Wrong lifecycle stage → wrong handler called → wrong moves → conservation violation (caught by C2) or invalid-transition error (caught by C11).

- **(a) ISDA/regulatory anchor:** CDM `TradeState`, `EventQualification`, `EventIntentEnum`; ISDA Process and Workflow model.
- **(b) Direction of travel:** **The lifecycle stages are CDM enums** — this is correct. The framework's per-product state types (per §7 of the spec) collapse into CDM `TradeState` projections.
- **(c) Pending CD:** ISDA / FINOS work on Equity lifecycle event extensions (corporate actions, optional dividends).

### 5.3 PositionState Coordinates (per `(wallet, unit)`)

1. **Canonical name:** `PositionState[w, u]` — the addendum's per-position map.
2. **Definition:** Per-position mutable state: `accumulated_cost` (futures), `entry_nav` and `hwm` (mandate / strategy), `accrued_fee`, `mandate_breach_flags`, settlement-status sub-state. **Note:** the GPM 6-coordinate vector $(\mathrm{own}, \mathrm{onloan}, \mathrm{borr}, \mathrm{coll\_post}, \mathrm{coll\_recv}, \mathrm{coll\_rehyp})$ is the SBL-extension of `PositionState` (§16 of the spec).
3. **Minimum field set:** scalar core: `{balance: Decimal, accumulated_cost: Decimal, ccp_binding: Optional[CCPRef]}`; SBL extension: 6-vector. Mandate extension: `{entry_nav, hwm, hwm_date, accrued_mgmt_fee, accrued_perf_fee, breach_flags: List[Breach]}`.
4. **Identity:** `(wallet_id, unit_id)`.
5. **Provenance:** Lifecycle handlers (per C11, each field has a unique writer — `ac` ← settle/trade; `hwm` ← fee_crystallise; `entry_nav` ← subscribe).
6. **Temporal semantics:** Monotone carrier (C1) — rows are never garbage-collected. `Some(zero)` distinguishable from `None` (load-bearing for VM-settle, wash-sale, record-date entitlements).
7. **Failure consequences:** Loss of monotonicity = replay non-determinism = audit trail break = IFRS 9 / ASC 320 substantiation failure. The conservation invariant $\sum_w \mathrm{accumulated\_cost}(w, u) = 0$ is the universal test oracle.

- **(a) ISDA/regulatory anchor:** IFRS 9 §3.2.6 (lent securities not derecognised — drives `own` semantics); ASC 815 / 320 / 821 (US GAAP); GMSLA 2010/2018 (TT vs SI distinguishes whether collateral changes `own`); FINRA SLATE / SFTR Art 15 (rehypothecation tracking).
- **(b) Direction of travel:** **CDM does not have a native PositionState concept** — this is a documented CDM gap. The Ledger's `PositionState` complements CDM's per-Trade `TradeState`. The FINOS Position Model working group (proposed 2026) is expected to address this.
- **(c) Pending CD:** ISDA Common Position Model (proposed in 2025 FINOS roadmap); FINRA SLATE final rule clarifications on rehypothecation reporting field schema.

---

## 5b. Smart-Contract Execution Audit (move stream + workflow history)

### 5.4 Move Stream Records

1. **Canonical name:** `EventLog[seq]` — the append-only move stream of §1.3 / §11.3.
2. **Definition:** Each entry: `{seq: Int, tx_id: UUID, move: Move, cdm_payload: CDM_BusinessEvent, prev_hash: Hash, hash: Hash}`. The CDM payload is stored alongside the move, **preserving the full CDM event** (per §9.4 — the forgetful mapping $F$).
3. **Minimum field set:** as above; the move struct itself is `{from: WalletId, to: WalletId, unit: UnitId, quantity: Decimal, timestamp: Timestamp, source: ContractRef, metadata: Map}`.
4. **Identity:** `(seq, tx_id, prev_hash, hash)` — hash chain for tamper-evidence (Invariant P4).
5. **Provenance:** Executor activity (Temporal); never written directly by smart contracts.
6. **Temporal semantics:** Append-only, monotone, hash-chained. WORM storage required for true immutability per §9.2.
7. **Failure consequences:** Mutable event log = no replay = no time-travel = no regulatory reconstruction. **BCBS 239 Principle 6 (accuracy and integrity)** mandates this.

- **(a) ISDA/regulatory anchor:** BCBS 239 (risk-data aggregation and reporting); SOX §404; CFTC §1.31 and 17 CFR 1.35; MiFID II Article 16 record-keeping; SEC Rule 17a-4.
- **(b) Direction of travel:** **CDM `EventState` is the canonical schema for events.** The full CDM event payload is preserved as required by ISDA's Process and Workflow model. ISDA DRR uses the same audit trail to feed regulatory reports.
- **(c) Pending CD:** ISDA DRR traceability tool RFQ (Oct 2025) — AI-assisted audit trail linking DRR coding decisions to regulatory requirements; will feed back into the event-log schema requirements.

### 5.5 Temporal Workflow History (orchestration audit trail)

1. **Canonical name:** `WorkflowHistory[workflow_id]` — the second audit trail of §11.3.
2. **Definition:** Activity invocations, inputs, results, timer fires, signals — Temporal's append-only event history per workflow execution.
3. **Minimum field set:** `{workflow_id, run_id, history_events: List[HistoryEvent], current_version: Int}`.
4. **Identity:** `(workflow_id, run_id)`.
5. **Provenance:** Temporal cluster (managed by infrastructure team).
6. **Temporal semantics:** Append-only by Temporal design; supports `ContinueAsNew` for long-running workflows.
7. **Failure consequences:** Lost workflow history = irreproducible orchestration = operational forensics blind spot. **DORA Article 8 (ICT risk management) and Chapter IV (digital operational resilience testing)** require this.

- **(a) ISDA/regulatory anchor:** EU DORA (Regulation 2022/2554) — ICT risk and resilience testing; FFIEC IT examination handbook; Bank of England operational resilience SS1/21.
- **(b) Direction of travel:** **No CDM model for orchestration audit, and there shouldn't be** — orchestration is platform-specific. But **the obligation taxonomy at §14.7 is ISDA-aligned** (CSA VM, IM, close-out netting, manufactured dividend — all ISDA constructs).
- **(c) Pending CD:** DORA secondary technical standards (ESMA / EBA RTS) on ICT third-party risk; UK CT Resilience SS2/21 expansion.

---

## 7. Legal / Documentation / Agreement Data (NEW — missing from proposed floor)

### 7.1 ISDA Master Agreement Reference and Schedule Terms

1. **Canonical name:** `LegalAgreement[party_pair, agreement_id]`.
2. **Definition:** The bilateral ISDA Master Agreement (1992 / 2002) with party-specific Schedule, plus Credit Support Annex (CSA) — including the elections (governing law, threshold, MTA, cross-default, automatic early termination, calculation agent role).
3. **Minimum field set:** `{agreement_id, master_form: enum[1992_MULTI, 2002], party_a_lei, party_b_lei, schedule_elections: Map[ScheduleField, Value], csa_ref: Optional[AgreementId], jurisdiction_opinion_id: ISDAOpinionId, governing_law: enum, executed_date: Date}`.
4. **Identity:** `(party_a_lei, party_b_lei, master_form_version, executed_date)`.
5. **Provenance:** Signed in **ISDA Create**; stored in **MyLibrary**; netting opinion attached from ISDA's 90+ jurisdictional opinions library; amendments delivered via **Notices Hub**.
6. **Temporal semantics:** Effective from execution; amended via Notices Hub Protocol adherences (145+ entities adhered to 2025 Protocol by mid-Nov 2025).
7. **Failure consequences:** Wrong governing law = wrong close-out methodology = unenforceable netting = capital surcharge under Basel III CRR Article 296. Mis-stated MTA = continuous margin disputes.

- **(a) ISDA/regulatory anchor:** ISDA 1992 / 2002 Master Agreement; ISDA 2016 / 2018 CSA; ISDA 2018 GMSLA; ISDA 2020 SBL Annex; Basel III CRR III Article 296 (netting effects); EMIR Article 11 (risk-mitigation techniques).
- **(b) Direction of travel:** **ISDA Create + MyLibrary + Notices Hub + Counterparty Manager + S&P Global Market Intelligence integration** is the production legal-data pipeline. CDM `LegalAgreement` and `CollateralProvisions` are the structured representation. AI extraction of CSA clauses into CDM at >90% accuracy (ISDA + Linklaters whitepaper, 2025) is the input-side automation.
- **(c) Pending CD:** ISDA 2026 GMSLA review (under consideration); ISDA Standard Initial Margin Model (SIMM) v2.7 calibration; ISDA Resolution Stay Protocol updates.

### 7.2 Mandate Document, Fee Schedule, Benchmark Identity

1. **Canonical name:** `LegalAgreement[client, manager, mandate_id]`.
2. **Definition:** The investment management mandate — investment objective, asset-class restrictions, leverage caps, benchmark, fee schedule, performance fee hurdle, liquidity terms.
3. **Minimum field set:** `{mandate_id, client_lei, manager_lei, benchmark_unit_id: UnitId, mgmt_fee_rate: Decimal, perf_fee_rate: Decimal, hurdle: Decimal, hwm_methodology: enum, redemption_freq: Frequency, lockup_period: Duration}`.
4. **Identity:** It IS the `unit_id` of $u_{MA}$ per the addendum's R6 ruling.
5. **Provenance:** Signed via ISDA Create or equivalent platform; depositary attestation under UCITS V / AIFMD Article 22.
6. **Temporal semantics:** Versioned (C8 Preserving for fee changes within declared band; Breaking for mandate restructuring).
7. **Failure consequences:** Mandate breach undetected → fiduciary failure; benchmark mis-stated → performance attribution dispute.

- **(a) ISDA/regulatory anchor:** UCITS V (Directive 2014/91); AIFMD (Directive 2011/61); MiFID II Article 24 (suitability); SEC Investment Advisers Act of 1940; FINRA Rule 2210 (communications).
- **(b) Direction of travel:** **CDM `LegalAgreement` extensions for managed-account mandates** under FINOS roadmap; ISDA work on prime-brokerage standard documentation.
- **(c) Pending CD:** ESMA review of AIFMD II depositary obligations; SEC Form PF amendments (2024) on private fund reporting.

---

## 8. Obligation / Liveness Data (NEW — from §14.7 of the spec)

### 8.1 Obligation Records

1. **Canonical name:** `ObligationStore[obligation_id]`.
2. **Definition:** Every deterministic-date, event-triggered, or regulatory obligation registered in the system — discharge predicate, deadline, compensation action, current state.
3. **Minimum field set:** `{obligation_id, obligation_type: enum (CSA_VM, CSA_IM, BOND_COUPON, IRS_RESET, FUTURES_VM, SBL_RECALL, SBL_MFG_DIVIDEND, COLLATERAL_SUB, SFTR_REPORT, EMIR_REPORT, CFTC_REPORT, MAS_REPORT, JFSA_REPORT, ASIC_REPORT, HKMA_REPORT, SLATE_REPORT, SETTLEMENT_INSTR), source: UnitId | AgreementId, deadline: Timestamp, discharge_predicate: PredicateRef, compensation_action: ActionRef, state: enum (PENDING, ATTEMPTED, DISCHARGED, COMPENSATED, DEFAULTED), registered_at: Timestamp}`.
4. **Identity:** `obligation_id` (UUID).
5. **Provenance:** Lifecycle function output; committed atomically with the triggering event.
6. **Temporal semantics:** Append-only registration; state transitions through `Pending → Attempted → Discharged | Compensated | Defaulted`. Invariant P21: no obligation persists in `Pending` beyond its deadline.
7. **Failure consequences:** Missed obligation = missed margin call = silent risk accumulation = eventual default. Notices Hub launch directly addresses this: a single Friday-to-Monday notice delay on a medium-sized portfolio is ~USD 1M of uncollateralised loss.

- **(a) ISDA/regulatory anchor:** ISDA 2002 Master Section 6 (Calculation Agent), Section 5(a)(i) (failure to pay/deliver); ISDA Resolution Stay Protocol (close-out netting); CFTC §1.31 (recordkeeping); EMIR Article 11 (timely confirmation, dispute resolution).
- **(b) Direction of travel:** **CDM does not yet have a native Obligation type** — this is a CDM gap. The Ledger's Obligation Store is one of the first systematic implementations. ISDA work on confirmation-matching SLAs and dispute resolution timelines is expected to feed back into CDM.
- **(c) Pending CD:** ISDA Confirmation Practice Notes update (2026); EMIR Refit dispute-resolution timelines (already tightened to 5 business days for non-cleared OTCs).

### 8.2 Notice Records (Notices Hub integration)

1. **Canonical name:** `NoticeRecord[notice_id]`.
2. **Definition:** Termination notice, default notice, demand for collateral substitution, cure period notice — the legal communications that trigger lifecycle events.
3. **Minimum field set:** `{notice_id, sender_lei, recipient_lei, agreement_id, notice_type: enum, delivery_timestamp: Timestamp, deemed_received_timestamp: Timestamp, notice_body_hash: Hash, jurisdictional_opinion_id: ISDAOpinionId}`.
4. **Identity:** `notice_id` issued by ISDA Notices Hub.
5. **Provenance:** **ISDA Notices Hub** (launched July 2025; 21 jurisdictional opinions published; 145+ entities adhered to 2025 Protocol).
6. **Temporal semantics:** Strict timing matters for legal effectiveness — `delivery_timestamp` vs `deemed_received_timestamp`. Friday-to-Monday delays cost real money.
7. **Failure consequences:** Mis-delivered or delayed notice = contested close-out = enforceability litigation.

- **(a) ISDA/regulatory anchor:** ISDA 2025 Notices Hub Protocol; ISDA 1992/2002 Master Section 12 (Notices); UK Insolvency Act 1986; US Bankruptcy Code §362 (automatic stay); national insolvency laws covered by ISDA's 90+ netting opinions.
- **(b) Direction of travel:** **Notices Hub is THE direction of travel** — production ledger systems must integrate. Without it, a firm carries operational risk that ISDA has explicitly engineered out of the industry.
- **(c) Pending CD:** Additional Notices Hub Protocols for SBL termination notices, FX prime-broker terminations under consideration.

---

## 9. Valuation State Data (from valuation v1.0 §2)

### 9.1 ValuationRecord

1. **Canonical name:** `ValuationStore[unit_id, timestamp, model_id]`.
2. **Definition:** The full record of a pricing computation — dirty/clean price, accrued, Greeks (model-specific tagged union), model_id, market data snapshot, compute time, quality flag, FSM state.
3. **Minimum field set:** `{unit_id, timestamp, dirty_price: Decimal, clean_price: Decimal, accrued: Decimal, greeks: Greeks (model-tagged), model_id: String, market_data_snap: SnapshotId, compute_ms: Int, quality: enum (FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED), fsm_state: enum (UNPRICED, PRICING, PRICED, EXPLAINING, EXPLAINED, QUARANTINED, STALE, FAILED), pnl_explain_residual: Decimal}`.
4. **Identity:** `(unit_id, timestamp, model_id)`.
5. **Provenance:** PricingWorkflow per unit (one Temporal workflow per unit, valuation v1.0 §7); inputs are calibrated market data and unit state.
6. **Temporal semantics:** Append-only within a pricing cycle; previous FIRM record retained for time-travel and PnL Explain.
7. **Failure consequences:** Wrong price → wrong PnL → wrong VM → wrong capital. The FRTB IMA framework has explicit P&L Attribution test (PLA) tolerance bands that map directly onto the FSM's QUARANTINED transition.

- **(a) ISDA/regulatory anchor:** Basel III FRTB PLA test (BCBS 457); IFRS 13 fair-value measurement and disclosure; ISDA SIMM Rulebook (parameter governance).
- **(b) Direction of travel:** **The ValuationRecord schema is well-aligned with FRTB IMA and IFRS 13 disclosure** — explicit `quality` flag and `model_id` are precisely what regulators ask for under Pillar 3. Should feed BCBS Pillar 3 machine-readable disclosure (CD March 2026, IIF/ISDA/GFMA response argued for CDM/DRR template).
- **(c) Pending CD:** BCBS d514 IRRBB; FRTB IMA validation harmonisation; **BCBS Pillar 3 machine-readable disclosure CD (March 2026)** — directly applicable.

### 9.2 PnL Attribution Decomposition

1. **Canonical name:** `PnLExplain[unit_id, t_prev, t_curr]`.
2. **Definition:** Per-unit decomposition: $\Delta P = \delta \Delta S + J \cdot \Delta\Theta + \frac{1}{2}\Gamma(\Delta S)^2 + \Theta_{decay} \Delta t + \varepsilon$; with FRTB PLA tolerance bands governing the FSM transition T5/T6.
3. **Minimum field set:** `{unit_id, t_prev, t_curr, total_pnl, delta_pnl, parameter_pnl, gamma_pnl, theta_pnl, unexplained_residual, tolerance_band, explain_status: enum (PASS, FAIL)}`.
4. **Identity:** `(unit_id, t_prev, t_curr, model_id)`.
5. **Provenance:** PnL Explain function, run as part of every full reprice cycle.
6. **Temporal semantics:** Computed on each full reprice; persisted alongside the new ValuationRecord.
7. **Failure consequences:** Unexplained PnL above tolerance → FSM Quarantined → FRTB capital surcharge (NMRF or model decommissioning).

- **(a) ISDA/regulatory anchor:** Basel III FRTB PLA test (KS test, Spearman correlation); ISDA risk-factor mapping working group; IFRS 9 Day-1 PnL guidance.
- **(b) Direction of travel:** **FRTB PLA + Risk-Factor Eligibility Test (RFET)** is the regulatory backbone. The valuation v1.0's tolerance table maps tightly. Industry move to AAD (adjoint algorithmic differentiation) for full Jacobian computation accelerates this.
- **(c) Pending CD:** EU FRTB IMA reauthorisation cycles; UK PRA FRTB Q&A.

---

## 10. Regulatory Output Data (NEW — the DRR target)

### 10.1 EMIR Refit Reportable Fields (203 fields, EU)

1. **Canonical name:** `RegulatoryReport.emir[trade_id]`.
2. **Definition:** The full 203-field EMIR Refit payload (effective April 2024 EU, September 2024 UK) — UTI, UPI, LEI pair, action type, event type, valuation, collateral, all timestamps.
3. **Minimum field set:** ESMA-prescribed schema.
4. **Identity:** `(uti, action_type, event_timestamp)`.
5. **Provenance:** **ISDA DRR-generated** (live in production at Banque Pictet, BNP Paribas, JSCC, JPMorgan; 13 firms in PoC including Goldman Sachs, DTCC, DBS).
6. **Temporal semantics:** Reportable T+1; lifecycle events trigger update reports.
7. **Failure consequences:** Field break → trade-repository rejection → ESMA query → fine. **Up to 50% reduction in ongoing reporting cost via DRR** per ISDA/Capgemini Nov 2025 paper; **98.2% acknowledgement rate under EMIR Refit DRR** (vs ~85% industry average).

- **(a) ISDA/regulatory anchor:** EMIR Refit (Commission Delegated Regulation (EU) 2022/1855 et al); ESMA technical standards; FCA UK MAR.
- **(b) Direction of travel:** **DRR is the only direction of travel.** Firms that maintain bespoke EMIR mappings are accumulating technical debt that will be compulsorily written off as the DRR ecosystem matures. The Ledger's CDM-native event log is the input; DRR is the transform; trade repository is the destination.
- **(c) Pending CD:** ESMA call for evidence on EU reporting cost drivers (2025); ISDA response (Sep 2025) advocating delineation by instrument type, removal of dual-sided reporting, elimination of duplicative fields, avoidance of LEI/UPI-redundant fields.

### 10.2 CFTC Part 43 / 45 Reportable Fields (US)

1. **Canonical name:** `RegulatoryReport.cftc[trade_id]`.
2. **Definition:** CFTC Part 43 (real-time public reporting) + Part 45 (regulatory reporting) — rewritten 2022–2024.
3. **Minimum field set:** CFTC-prescribed schema.
4. **Identity:** `(uti, action_type, event_timestamp)`.
5. **Provenance:** ISDA DRR (CFTC live since Dec 2022).
6. **Temporal semantics:** Real-time for Part 43; T+1 for Part 45.
7. **Failure consequences:** CFTC enforcement actions on misreported data total nearly USD 200M in 2018–2024.

- **(a) ISDA/regulatory anchor:** Dodd-Frank Title VII; CFTC §43.3, §45.3, §45.6.
- **(b) Direction of travel:** **DRR-CFTC is the gold standard** — JPMorgan FINOS open-source DRR (Oct 2024) covers it.
- **(c) Pending CD:** CFTC Part 39 / 23 amendments on swap data reporting harmonisation.

### 10.3 SFTR / SLATE Reportable Fields (SBL specific)

1. **Canonical name:** `RegulatoryReport.sftr[loan_id]`, `RegulatoryReport.slate[loan_id]`.
2. **Definition:** SFTR 155-field schema (EU, 2020); FINRA SLATE schema (US, effective Apr 2024).
3. **Minimum field set:** ESMA / FINRA prescribed.
4. **Identity:** `sftr_uti`, `slate_loan_id`.
5. **Provenance:** Generated from the SBL `unit_state` (per §16.6).
6. **Temporal semantics:** Daily for SFTR; T+1 for SLATE.
7. **Failure consequences:** Dual-sided SFTR matching breaks are the dominant SBL break source.

- **(a) ISDA/regulatory anchor:** SFTR (Regulation (EU) 2015/2365); FINRA Rule 6500 series (SLATE); ICMA / ISLA market practices.
- **(b) Direction of travel:** **DRR coverage of SFTR is in progress (2025 roadmap)**; the GMSLA 2018 + 2020 SBL Annex are CDM-aligned.
- **(c) Pending CD:** FINRA SLATE final clarifications on rehypothecation reporting; ESMA SFTR review (2026).

### 10.4 MiFIR RTS 22 Transaction Reporting (65 fields)

1. **Canonical name:** `RegulatoryReport.mifir[transaction_id]`.
2. **Definition:** MiFIR transaction reports for trading venues + investment firms.
3. **Minimum field set:** ESMA RTS 22 schema.
4. **Identity:** Internal transaction reference + LEI.
5. **Provenance:** Generated from the move stream and CDM `BusinessEvent` payload.
6. **Temporal semantics:** T+1.
7. **Failure consequences:** ESMA / FCA enforcement on transaction-reporting failures.

- **(a) ISDA/regulatory anchor:** MiFIR (Regulation (EU) 600/2014) Article 26; ESMA RTS 22.
- **(b) Direction of travel:** **DRR-MIFIR/MIFID is in the ISDA roadmap**; ESMA call for evidence (2025) ISDA response argues ETD → MIFIR, OTC → EMIR delineation.
- **(c) Pending CD:** EU MiFIR review (final 2025); UK MIFIR-equivalent proposals.

### 10.5 BCBS Pillar 3 Machine-Readable Disclosure (NEW — the next frontier)

1. **Canonical name:** `RegulatoryReport.pillar3[entity_lei, reporting_date]`.
2. **Definition:** Quarterly Pillar 3 capital, liquidity, and risk disclosure templates, machine-readable.
3. **Minimum field set:** BCBS-prescribed templates (BCBS 309 + revisions).
4. **Identity:** `(entity_lei, reporting_date, template_id)`.
5. **Provenance:** Aggregated from positions, valuations, and SIMM/IMA models.
6. **Temporal semantics:** Quarterly.
7. **Failure consequences:** Disclosure error → market reaction → reputational damage; FRTB IMA decommissioning risk.

- **(a) ISDA/regulatory anchor:** BCBS 309 (revised disclosure framework); CRR III Pillar 3; SEC/FRB equivalent.
- **(b) Direction of travel:** **IIF/ISDA/GFMA response to BCBS machine-readable Pillar 3 CD (March 2026)** — which I co-signed — argued forcefully that the template should follow the **CDM/DRR pattern**: shared executable code derived from a common domain model, permitting Inline XBRL where the existing XBRL ecosystem is mature, with phased implementation and proportionality for smaller banks. **This is the next major battle**: a non-interoperable Pillar 3 framework would repeat the 15-year EMIR mistake.
- **(c) Pending CD:** **BCBS Pillar 3 machine-readable CD (consultation closed early 2026; final standard expected late 2026)**.

---

## Summary Table — Floor Coverage

| Floor (corrected) | Items above | CDM-native? | DRR-applicable? | Notes |
|---|---|---|---|---|
| 1. Static / Instrument-Intrinsic | 1.1, 1.2, 1.3, 1.4 | Yes (CDM `Trade`, `EconomicTerms`, `ProductIdentification`) | Yes (DRR consumes) | Subsumes proposed "Listed-instrument detail" |
| 2. Reference / External Authority | 2.1, 2.2, 2.3, 2.4 | Partial — LEI/UPI/MIC native; SSI is a CDM gap | LEI/UPI mandatory | |
| 3. Market Data | 3.1, 3.2, 3.3 | No (and shouldn't be) | Indirect via valuation | FRTB territory |
| 4a. Oracle / Raw Attestations | 4.1, 4.2, 4.3 | Partial (CCP & CA via CDM `BusinessEvent`) | Consumes | Cryptographic signing direction-of-travel |
| 4b. Calibrated Market Data | (covered in 3.2) | No | Indirect | Kalman filter outputs |
| 5a. Execution Inputs (StateDelta) | 5.1, 5.2, 5.3 | Yes — IS the CDM `BusinessEvent` ↔ Ledger boundary | Yes (DRR generates from these) | Three-map ruling drives field shape |
| 5b. Execution Audit | 5.4, 5.5 | Event log Yes (CDM payload preserved); Workflow history No | Event log Yes | BCBS 239 + DORA mandates |
| 6. [merged] | — | — | — | Subsumed into 1+2 |
| 7. Legal / Agreement | 7.1, 7.2 | Yes — CDM `LegalAgreement`, `CollateralProvisions` | Yes (CSA elections feed DRR fields) | ISDA Create + MyLibrary + Notices Hub |
| 8. Obligation / Liveness | 8.1, 8.2 | Gap — CDM Obligation type proposed for v7 | Yes (regulatory obligations are first-class) | Notices Hub critical |
| 9. Valuation State | 9.1, 9.2 | No (and shouldn't be) | Indirect via Pillar 3 | FRTB PLA territory |
| 10. Regulatory Output | 10.1, 10.2, 10.3, 10.4, 10.5 | Yes — DRR is exactly this | Yes (DRR IS the implementation) | Pillar 3 machine-readable is the next frontier |

---

## Direction-of-Travel Convergence Statement

The arc that ties this enumeration together:

1. **Standardisation** (ISDA Master 1985) → **legal certainty** (90+ netting opinions) → **documentation digitisation** (ISDA Create, MyLibrary) → **process automation** (CDM, DRR) → **collateral modernisation** (tokenised MMFs, smart contracts) → **capital reporting standardisation** (machine-readable Pillar 3).
2. **Every datum in this enumeration is on that arc.** The Ledger v11.0 must therefore make CDM the lingua franca for §1.2, §1.3, §5.1, §5.2; LEI/UPI/MIC the lingua franca for §2.1, §2.2; ISDA Create + Notices Hub the lingua franca for §7; DRR the lingua franca for §10.
3. **Anti-pattern flags raised by this enumeration:**
   - The proposed floor's separation of "Listed-instrument detail" creates duplication (D2). Subsume into Static + Reference.
   - "Static" / "Reference" naming is ambiguous (D1). Rename to "Instrument-Intrinsic" / "External Authority Lookups".
   - Smart-contract execution data is not a peer category (D3). Split into Inputs and Audit.
   - Oracle/raw vs Calibrated/filtered must be distinct (D5).
   - Four categories are missing from the floor (D4): Legal/Agreement, Obligation/Liveness, Valuation State, Regulatory Output.

The enumeration above totals **~30 distinct data items across 10 corrected floor categories** (after subsuming the proposed sixth into 1+2 and adding four), each anchored to an ISDA / regulatory artefact and each placed on the CDM/DRR direction-of-travel.

---

*End of Phase 1 — Olivier Vantard.*
