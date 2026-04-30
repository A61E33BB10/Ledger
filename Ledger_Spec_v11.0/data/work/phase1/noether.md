# Phase 1 Data Enumeration --- NOETHER

**Lens:** Symmetries determine conservation laws. Each datum is classified by the symmetry it carries (so the system is closed under that symmetry's group action) and by the Noether current that breaks if the datum is corrupted, missing, or asynchronous.

**Notation.**
- "Σ_w w(u) = 0" is the v10.3 quantity-conservation law (Inv. P1).
- "value invariance" is the v10.3 lifecycle value invariance for deterministic events.
- "PnL path-independence" is V_{t1} - V_{t0} (v10.3 §4.3).
- "FSM" refers to the valuation lifecycle FSM (valuation v1.0 §2).
- "C1...C12" refer to the StatesHome addendum conditions.

The mandatory seven-field structure for every datum:

> 1. Canonical name | 2. Definition | 3. Minimum field set | 4. Identity | 5. Provenance | 6. Temporal semantics | 7. Failure consequences.

---

## 0. Master symmetry register

Before the data enumeration, the symmetries the Ledger relies on. Each subsequent datum is a *carrier* of one or more of these.

| ID | Symmetry / invariance | Conservation law / Noether current |
|----|-----------------------|------------------------------------|
| S1 | Wallet-relabelling invariance (no preferred wallet) | Σ_w w(u) = 0 |
| S2 | Permutation invariance of independent moves within a transaction | Atomic commit / batch totals |
| S3 | Time-translation invariance of contractual rules (rules are time-independent functions of state) | Time-travel / replay determinism (Inv. P8, P9) |
| S4 | Replay invariance under checkpointing (apply_all(events[:k]) ++ events[k:] ≡ apply_all(events)) | Monotone PositionState carrier; deterministic replay |
| S5 | Counterparty-symmetry (issuance: every +1 has a -1) | Σ_w w(u) = 0 for issued contracts |
| S6 | Calendar-equivalence (two calendars merge by intersection) | Schedule determinism |
| S7 | Currency rescaling covariance (FX: V is covariant under simultaneous rescaling of price vector and reporting currency) | Real value preservation across base ccy choice |
| S8 | Forgetful homomorphism F: CDM → Ledg preserving composition (referentially independent events) | Conservation under translation; report = projection of ledger |
| S9 | Single-Coordinate Move (SBL) — every atomic move touches exactly one coordinate of one unit per entity | own-conservation / available-inventory identity |
| S10 | Parameter martingale (model parameters expected stationary) | PnL explain residual ≡ unexplained ⇒ model error |
| S11 | Bid-ask / measurement symmetry on Kalman observations | Innovation-gating; calibration certifiability |
| S12 | Fungibility equivalence relation on units | Unit identity / netting correctness |

Ten core data categories follow. The author's six "floor categories" are covered, with three additions (Time, Identity-and-Party Reference, Calibration State / Latent-Parameter) and one structural disagreement (the floor split between Static and Reference Data is partly subsumed by the Unit Store's three tiers and by ProductTerms — but the disagreement is shallow; see §11).

---

## 1. Static data (post-issuance immutable contractual terms)

**Carries:** S3 (time-translation), S5 (issuance counterparty symmetry), S12 (fungibility), S8 (CDM forgetful map).
**Home in v10.3:** *ProductTerms[u]* — versioned `NonEmptyList[TermsVersion]`, append-only (StatesHome C6/C7).

### 1.1 ProductTerms (per registered unit u)

1. **Canonical name.** `ProductTerms[u]`.
2. **Definition.** The immutable, versioned contractual specification of unit u. The append-only `NonEmptyList[TermsVersion]` records every preserving amendment (StatesHome C8, C6).
3. **Minimum field set.**
   - `unit_id`, `unit_type` ∈ {CASH, EQUITY, LISTED_DERIV, OTC_DERIV, BOND, STRUCTURED, MA_MANDATE, QIS_STRATEGY, SBL_LOAN, TOKENIZED}.
   - `currency`, `multiplier?`, `expiry?`, `notional_basis?`, `lot_size?`.
   - For listed deriv: `(exchange, underlier_ref, option_type | future_kind, strike?, expiry, settlement_type)`.
   - For OTC: full CDM `Trade.tradableProduct.product` + `Trade.collateral` (CSA reference, eligible-collateral schedule, threshold, MTA).
   - For bond: `coupon_schedule`, `day_count_convention_ref`, `business_day_adjustment_ref`, `roll_convention`, `redemption_terms`.
   - For QIS / MA: mandate text hash, fee schedule (`mgmt_rate`, `perf_rate`, hurdle methodology, crystallisation frequency), benchmark-unit reference, max-position predicate, fungibility predicate `is_fungibility_preserving` (StatesHome C8).
   - `cdm_version_id` (Sec 10.3 — required for CDM coexistence).
   - `is_fungibility_preserving : TermsAmendment → {Preserving, Breaking}`.
4. **Identity.** Deterministic injective hash of CDM object: listed = hash(contract spec); OTC = CDM Trade metadata key (UTI + Collateral); Mandate/QIS = manager + version + mandate-text hash.
5. **Provenance.** Created-by tx_id at unit registration; CDM source message (FpML/FIX/ISO 20022) preserved in event-log payload; `cdm_version_id` recorded.
6. **Temporal semantics.** **Append-only versioned (bitemporal-lite).** Every `TermsVersion` carries `effective_date` (business time) and `recorded_at` (system time). Re-registration is a hard error (StatesHome C10). Breaking amendment ⇒ fresh u_new + `SupersededBy` (C8).
7. **Failure consequences.**
   - Wrong `multiplier` / `notional_basis` ⇒ Trade-handler `accumulated_cost` delta computation breaks Σ_w accumulated_cost(w,u)=0 (futures conservation, v10.3 §7.5).
   - Wrong `expiry` / `coupon_schedule` ⇒ liveness violation (P21): the obligation never registers a timer ⇒ silent failure to pay coupon.
   - Wrong `is_fungibility_preserving` ⇒ a breaking amendment is appended in place ⇒ historical positions silently re-priced ⇒ value invariance broken AND P6 (immutability of terms) violated.
   - Mid-life mutation ⇒ S3 (time-translation symmetry) broken ⇒ time-travel and replay diverge ⇒ Inv. P8 fails.

> **Silent-corruption flag.** Wrong `multiplier` is the canonical Σ_w = 0 silent killer for futures and listed derivatives. It cannot be detected by post-trade conservation checks because both legs use the same wrong multiplier and net to zero — but every value computation is wrong by a constant factor.

### 1.2 EconomicTerms / Schedule sub-structure

The CDM-derived schedules embedded in ProductTerms (coupon dates, reset dates, exercise window). Deserves separate entry because corruption mode is structurally distinct.

1. **Name.** `Schedule[u]` (CDM `EconomicTerms.calculationPeriodDates`, `paymentDates`, `resetDates`, `exerciseDates`).
2. **Definition.** Generated date sequence for periodic events.
3. **Minimum fields.** `start_date`, `end_date`, `frequency`, `roll_convention`, `business_day_convention_ref`, `business_centers_ref`, `day_count_fraction_enum`, `dateRelativeTo` references.
4. **Identity.** Sub-key `(u, schedule_role ∈ {COUPON, RESET, FEE_CRYSTALLISATION, EXERCISE, MARGIN_CALL, REBALANCE})`.
5. **Provenance.** Deterministic derivation from ProductTerms via CDM `ResolveAdjustableDate` + holiday calendars. The derivation function ID and version are recorded.
6. **Temporal semantics.** Resolved schedule = function(ProductTerms, BusinessCenters, current calendar version). On calendar amendment, schedules are *recomputed deterministically* — the immutable input is the calendar version pin.
7. **Failure consequences.** Wrong roll convention or missing holiday ⇒ payment date shifts ⇒ obligation timer wrong ⇒ liveness gap (P21). Critically: a date that *was* a holiday at deal time but is reclassified later ⇒ historical recomputation diverges ⇒ time-travel breaks unless calendar version is pinned.

### 1.3 Counterparty / Party binding (sticky to OTC unit identity)

1. **Name.** `Parties[u_OTC]`.
2. **Definition.** For OTC units, the bilateral parties whose identities partly determine fungibility (a USD-CSA trade ≠ EUR-CSA trade).
3. **Minimum fields.** `lei_buyer`, `lei_seller`, `csa_ref`, `mca_ref`, `clearing_party?`, `clearing_status ∈ {BILATERAL, CLEARED}`.
4. **Identity.** Subset of CDM Trade metadata key.
5. **Provenance.** Trade-execution event (FpML / FIX / ISO 20022).
6. **Temporal semantics.** Immutable post-confirmation. Novation = breaking amendment (allocates u_new under C8) — it must NOT mutate `Parties[u_old]`.
7. **Failure consequences.** Wrong LEI ⇒ regulatory obligation (SFTR/EMIR) registered against wrong reporter ⇒ obligation completeness (Princ. 14.x) violated. Wrong CSA reference ⇒ CSAMargin smart contract reads wrong threshold/MTA ⇒ Σ_w cash conservation still holds, but counterparty-risk exposure miscomputed.

---

## 2. Reference data

Reference data has *two* distinct sub-classes that the v10.3 spec sometimes conflates. The Noetherian split is:

- **Reference-2A: Identity / classification reference** (LEI, ISIN, MIC, currency code, BIC). These are pure naming — they support S1 (wallet-relabelling invariance must hold under their substitution).
- **Reference-2B: Computational reference** (calendars, day-count enumerations, lot sizes, business-day conventions, CDM enums). These are *function-defining* — they enter directly into the CDM date-resolution chain and the schedule generation.

### 2.1 Identity and classification reference (Ref-2A)

1. **Name.** `IdentityRefData`.
2. **Definition.** Codes that establish identity of parties, instruments, venues, currencies.
3. **Minimum fields.** Per registry: code, status, effective dates, mapping links. Concretely:
   - LEI registry: `lei`, `legal_name`, `entity_status`, `parent_lei?`, `jurisdiction`.
   - ISIN registry: `isin`, `issuer_lei`, `cfi_code`, `issue_date`, `maturity_date`.
   - MIC registry: `mic`, `operating_mic`, `country`, `status`.
   - Currency code (ISO 4217): `code`, `precision`, `active`.
   - BIC (ISO 9362): `bic`, `bank_lei`, `branch`.
   - Regulatory class: `cfi_code`, `mifid_class`, `emir_class`, `sftr_eligibility`, `slate_eligibility`, `csdr_settlement_discipline_flag`.
4. **Identity.** Code itself.
5. **Provenance.** External authority: GLEIF (LEI), ANNA (ISIN), ISO MA (MIC, BIC, currency), regulatory taxonomy bodies.
6. **Temporal semantics.** **Bitemporal mandatory.** A LEI re-issued or merged, an ISIN restated, a MIC closed — all must preserve the (effective_date, recorded_at) pair. Time-travel "as we knew it at t" requires the recorded-at slice; "as we know now" requires the effective slice.
7. **Failure consequences.** Wrong LEI ⇒ regulatory misreport (SFTR/EMIR/SLATE) ⇒ obligation defaulted (P21 compensated as regulatory penalty). Wrong ISIN ⇒ unit-identity collision ⇒ S12 (fungibility) violated ⇒ two non-fungible positions silently nettable ⇒ Σ_w w(u) = 0 holds vacuously while economic exposure is wrong. Currency code precision wrong ⇒ rounding asymmetry ⇒ structural penny breaks.

### 2.2 Calendars and conventions (Ref-2B)

1. **Name.** `BusinessCalendar[id]`, `DayCountFractionEnum`, `BusinessDayConventionEnum`, `RollConventionEnum`, `LotSize[isin]`.
2. **Definition.** The function-defining reference data that resolves contractual schedule abstractions to concrete dates and year fractions.
3. **Minimum fields.**
   - Calendar: `business_center_id` (USNY, GBLO, EUTA, JPTO...), `weekend_rule`, `holiday_set : Map[year, Set[date]]`, `version_id`, `published_by`, `published_at`.
   - DayCount enum: enumerated per CDM `DayCountFractionEnum` (ACT/360, ACT/365_FIXED, 30/360, ACT/ACT_ISDA, CAL_252, ...).
   - BD convention enum: FOLLOWING, MODFOLLOWING, PRECEDING, MODPRECEDING, NEAREST, NONE.
   - Lot size: `(isin, lot_size, board_lot_status, effective_date)`.
4. **Identity.** `(business_center_id, version_id)` for calendars; CDM enum value for conventions.
5. **Provenance.** Exchange / CSD publications, vendor (Copp Clark, Refinitiv) feeds, ISDA definitions.
6. **Temporal semantics.** **Bitemporal mandatory + version-pinned.** A holiday added retroactively (e.g., national mourning day declared after the fact) must NOT silently re-resolve historical schedules. The contract pins the calendar *version*, not just the calendar reference, at deal time.
7. **Failure consequences.**
   - **This is the second silent Σ_w killer.** Wrong holiday ⇒ adjusted payment date moves by one business day ⇒ obligation timer wrong ⇒ ledger and counterparty disagree on payment date ⇒ external reconciliation break that conservation cannot detect (Σ_w still holds; settlement is the symptom).
   - Wrong day-count ⇒ accrued interest wrong ⇒ dirty/clean price wrong ⇒ value invariance for bond coupon broken (the clean-price drop ≠ coupon paid).
   - Calendar version not pinned ⇒ S3 (time-translation symmetry) broken ⇒ time-travel diverges from "as we knew it at t".

> **C8 fungibility-predicate dependency.** Calendar versions are inputs to `is_fungibility_preserving`. Re-versioning a calendar in place silently re-classifies amendments ⇒ schema break.

---

## 3. Market data

### 3.1 Quotes / observed prices (raw, pre-Kalman)

1. **Name.** `Quote[u, source, t]` and `Fix[u, source, t]` (the latter for an authoritative settle/fixing).
2. **Definition.** A market observation of a price-like quantity for a unit at a wall-clock time, before calibration / cleaning.
3. **Minimum fields.** `unit_id` (or `observable_id` for non-unit observables), `source_id`, `quote_type ∈ {BID, ASK, MID, LAST, SETTLE, FIX, INDICATIVE}`, `price`, `size?`, `bid_ask_spread?`, `timestamp_observed`, `timestamp_received`, `liquidity_flag ∈ {ORDERLY, STRESSED, HALTED, STALE}`, `vendor_correction_id?`.
4. **Identity.** `(observable_id, source_id, t_observed)`.
5. **Provenance.** Exchange feed, IDB, vendor (Bloomberg, Refinitiv, MarketAxess, ICE), counterparty quote.
6. **Temporal semantics.** **Bitemporal mandatory + immutable per (source, t_observed).** Vendor corrections create a new record with `vendor_correction_id` and a back-pointer; the original is *never* overwritten. "Replay as known at t" uses the recorded-at slice; "replay with corrections" uses the effective slice (v10.3 §7.7).
7. **Failure consequences.**
   - Stale or wrong quote into futures EOD settle ⇒ VM = ac − target wrong ⇒ Σ_w accumulated_cost(w,u) = 0 still holds (settled offsets are symmetric) but value invariance is violated and counterparty cash transfers are wrong by exactly the price error × notional.
   - Quote into Kalman without correct R_t ⇒ innovation-gating mis-fires (S11 broken) ⇒ certified-state contamination ⇒ all downstream pricing wrong ⇒ FSM Quarantined cascade.
   - Mutating a historical quote in place ⇒ S3 broken ⇒ time-travel reconstructs prices that were never actually known.

### 3.2 Curves and surfaces (calibrated, certified)

1. **Name.** `Curve[id, t]`, `Surface[id, t]` (yield curve, vol surface, credit curve, FX vol, dividend curve, repo curve, basis curve).
2. **Definition.** The calibrated, no-arbitrage-certified parameter set produced by the Kalman filter (valuation §4) from raw quotes.
3. **Minimum fields.** `curve_id`, `curve_type`, `model_id`, `parameter_vector x_{t|t}^cert ∈ ℝ^d`, `posterior_covariance P_{t|t}`, `innovation_residuals ν_t`, `observation_set y_t`, `observation_noise R_t`, `arbitrage_certification_status`, `certification_residuals`, `certified_at`.
4. **Identity.** `(curve_id, certified_at, model_id)`.
5. **Provenance.** Kalman workflow (valuation §4); inputs are §3.1 quotes plus prior posterior. The `model_id` and Kalman parameter set are version-pinned.
6. **Temporal semantics.** **Bitemporal append-only.** Each successful certification is a new record. Failed certifications fall back to the last certified state with staleness flag (FSM `Stale`).
7. **Failure consequences.**
   - Mis-calibrated curve ⇒ Greek Jacobian wrong ⇒ PnL explain residual exceeds tolerance ⇒ FSM transitions Quarantined (T6). This is the *correct* failure path; it's a Noetherian-clean detection.
   - Calibration applied without arbitrage-region projection ⇒ negative discount factor or butterfly-arb surface ⇒ structured-product pricing produces negative time-value or non-monotone payoffs ⇒ value invariance broken silently.
   - Curve mutated in place (no bitemporal record) ⇒ S3 broken; "replay as we knew it at t" impossible.

### 3.3 Fixings (authoritative observation)

1. **Name.** `Fixing[index, t]` (SOFR fixing, EURIBOR fixing, equity index closing fix, FX fix).
2. **Definition.** An authoritative, contractually-binding observation produced by a designated administrator at a designated time.
3. **Minimum fields.** `index_id`, `tenor`, `fixing_date`, `value`, `administrator_id` (e.g., FRBNY for SOFR), `publication_timestamp`, `restated_flag`, `restate_link?`.
4. **Identity.** `(index_id, tenor, fixing_date)`.
5. **Provenance.** Administrator publication (BBA, ICE Benchmark Administration, FRBNY, exchanges).
6. **Temporal semantics.** **Bitemporal mandatory.** Restated fixings are a recorded-at-newer record pointing at the original. The IRS reset workflow consumes the as-of-fixing-time value, not the as-of-now value, unless it is contractually a "restated" reset.
7. **Failure consequences.** Wrong fixing ⇒ IRS net payment wrong ⇒ Σ_w cash conservation still holds (the wrong amount flows symmetrically) but value invariance violated. Restated fixing applied retroactively without the bitemporal split ⇒ S3 broken ⇒ replay produces a different cash flow than what actually settled.

### 3.4 FX rates

1. **Name.** `FxRate[ccy_pair, t]`.
2. **Definition.** The exchange rate between two currencies at time t, used to express V_t in a chosen reporting currency (S7 covariance).
3. **Minimum fields.** `pair`, `bid`, `ask`, `mid`, `source`, `t`, `quote_basis ∈ {SPOT, TOM, T+1, T+2}`, `is_fixing`.
4. **Identity.** `(pair, t, source)`.
5. **Provenance.** FX venues, CLS, central-bank fixings (ECB 14:15 CET fixing, FRBNY noon fix).
6. **Temporal semantics.** Same as §3.1 (point-in-time, bitemporal under restatement).
7. **Failure consequences.** Wrong FX ⇒ the choice-of-reporting-currency PnL is wrong; quantity conservation still holds (each currency conserved separately, v10.3 §9.1) but the reporting layer is corrupted. Critically, S7 covariance only holds *if all FX rates used in V_t come from the same snapshot* — mixing snapshots silently breaks reporting equivalence.

### 3.5 Dividend and corporate-action data

1. **Name.** `DividendForecast[isin, ex_date]`, `AnnouncedCorporateAction[isin, action_id]`.
2. **Definition.** Forecast / announced future cash and stock distributions, ratios, ex-dates, record dates, payment dates.
3. **Minimum fields.** `isin`, `action_type ∈ {CASH_DIV, STOCK_DIV, SPLIT, MERGER, SPINOFF, RIGHTS_ISSUE, BUYBACK}`, `announcement_date`, `record_date`, `ex_date`, `payment_date`, `ratio_or_amount`, `currency`, `tax_treatment`, `confirmed ∈ {FORECAST, ANNOUNCED, CONFIRMED, PAID}`.
4. **Identity.** `(isin, action_id)` — vendor-assigned (e.g., Markit, Bloomberg DVD).
5. **Provenance.** Issuer announcement, vendor (Markit, IHS Markit, custodian).
6. **Temporal semantics.** **Bitemporal append-only.** A forecast becomes confirmed; a confirmed action may be cancelled or revised. Each version recorded.
7. **Failure consequences.**
   - Missing record-date entitlement ⇒ corporate-action workflow snapshot wrong ⇒ entitled holders missed ⇒ Σ_w w(u) = 0 *broken* if shares are paid out without offsetting issuer-virtual-wallet move (this is a real silent violator).
   - Wrong split ratio ⇒ position quantities wrong post-action ⇒ Σ_w broken.
   - Wrong manufactured-dividend amount in SBL chain ⇒ P14 (SBL income equivalence) broken; lender economic-ownership invariant violated.

### 3.6 Borrow / repo / financing data

1. **Name.** `BorrowRate[isin, t]`, `RepoRate[isin, term, t]`, `GeneralCollateralRate[ccy, term, t]`.
2. **Definition.** Cost of borrowing a security (SBL fee), repo financing rate (special and GC), used in SBL fee accrual and structured-note discounting.
3. **Minimum fields.** `isin?`, `currency?`, `tenor`, `rate`, `quote_type ∈ {BID, OFFER, FIX}`, `source`, `t`, `is_special_flag`.
4. **Identity.** `(isin, tenor, t, source)` or `(currency, tenor, t, source)`.
5. **Provenance.** SBL desks, repo IDBs, vendor (DataLend, IHS Markit Securities Finance), CCP repo benchmarks.
6. **Temporal semantics.** Point-in-time bitemporal.
7. **Failure consequences.** Wrong borrow rate ⇒ SBL accrued fee wrong ⇒ P_t(u_loan) = accrued fee wrong ⇒ value invariance for fee crystallisation broken (clean→dirty drop ≠ cash paid). Wrong repo curve ⇒ structured-note discount wrong ⇒ FSM Quarantined.

### 3.7 Credit and recovery data

1. **Name.** `CreditCurve[entity_lei, t]`, `RecoveryRate[entity_lei, seniority, t]`.
2. **Definition.** Hazard rates / CDS spreads and assumed recovery for credit-sensitive instruments (corporate bonds, CDS, structured notes with credit overlay).
3. **Minimum fields.** `entity_lei` (or sovereign CC), `seniority`, `tenor_grid`, `hazard_rates`, `recovery_assumption`, `source`, `t`.
4. **Identity.** `(entity_lei, seniority, t, source)`.
5. **Provenance.** CDS markets (Markit, ICE), rating agency / desk override.
6. **Temporal semantics.** Point-in-time bitemporal; recovery is typically a fixed assumption (40% senior unsec) recorded as a curve attribute.
7. **Failure consequences.** Wrong hazard ⇒ bond/CDS price wrong ⇒ FSM quarantined or (worse) silently passing because tolerance is wide. Recovery is binary: at default it determines payout — a wrong recovery rate at default is an outright cash-conservation event because the smart-contract-emitted moves carry the wrong number.

---

## 4. Oracle data (external attested observations crossing the contract boundary)

This is the data category the v10.3 spec underspecifies. CDM synonyms are positioned as the "oracle interface" (§9.2), but the *attestation discipline* is missing. Oracle data is the strict subset of market data that contractually triggers a smart-contract state transition.

### 4.1 Attested oracle observation

1. **Name.** `OracleAttestation[oracle_id, observation_id, t]`.
2. **Definition.** A signed external observation accepted by the executor as the authoritative input that crosses the contract boundary — the contractual fixing, the barrier observation, the corporate-action confirmation, the credit-event determination.
3. **Minimum fields.**
   - `oracle_id` (unique attesting entity — administrator, exchange, ISDA Determinations Committee, CCP, custodian).
   - `observation_id` (e.g., `(SOFR, 2026-04-29)`, `(SX5E, 2026-04-29, 16:00 CET)`, `(VOD.L, knock-out-barrier-check, 2026-04-29)`, `(DC, Lehman, credit-event-2008-09-15)`).
   - `value` (typed: scalar, boolean, enum).
   - `attestation_signature` (cryptographic or attestor-process equivalent: vendor signed feed, exchange Press Release, DC ruling).
   - `attestation_chain_id` (for replay determinism).
   - `t_observed`, `t_attested`, `t_received_at_executor`.
   - `fallback_chain` (ordered list of secondary oracles with priority).
   - `pre_image_data?` (raw quotes from which a fixing was computed).
   - `restated_flag`, `restate_link?`.
4. **Identity.** `(oracle_id, observation_id)`. Within the canonical oracle, `observation_id` is unique; a restatement is a new attestation linked back.
5. **Provenance.** Designated by the smart contract at unit registration: barrier observations from venue closing prints, fixings from administrator, credit events from ISDA DC, corporate actions from custodian / issuer agent, manuf-dividend amounts from issuer, settle prices from exchange.
6. **Temporal semantics.** **Append-only bitemporal with attestation-chain anchoring.** The smart contract stores `(oracle_id, observation_id) ↦ attestation_chain_id` at the point of consumption, so that replay reconsumes the *same* attestation, not a re-derived one (v10.3 §7.7 deterministic-oracle requirement).
7. **Failure consequences.**
   - **This is the dominant category that silently breaks lifecycle value invariance.** A wrong oracle attestation passes the executor's checks (it is well-formed, signed, on-time) and produces moves that conserve quantity but transfer the wrong amount of cash. Σ_w cash = 0 still holds; value invariance breaks by exactly the oracle error × notional.
   - A *missing* attestation fails-open (the lifecycle event silently doesn't fire) ⇒ liveness invariant P21 broken.
   - A *re-attested* observation consumed under the original ID without bitemporal indirection ⇒ replay produces different moves than the actual ledger ⇒ S3 broken ⇒ time-travel diverges.
   - Two different oracles disagree (e.g., SOFR primary vs FRBNY backup feeds differ) without a deterministic fallback chain ⇒ executor non-determinism ⇒ S4 broken ⇒ cloned-replay invariant fails.

> **Symmetry alert.** The oracle attestation is the formal carrier of "an external truth we agree to trust". Any time-symmetry violation in this category cannot be detected by Σ_w = 0, by tx-id idempotency, or by lifecycle idempotency. Property-based testing is structurally blind to it. The only defence is *attestation-chain version pinning at the point of consumption*.

---

## 5. Smart-contract execution data (executor inputs at event time)

Per the StatesHome 3-map decomposition, this is `view.unit_status(u)` ∪ `view.position_state(w,u)` plus the lifecycle-event payload.

### 5.1 UnitStatus (mutable, shared, registration-total)

1. **Name.** `UnitStatus[u]`.
2. **Definition.** Shared mutable state observable by every holder of u (StatesHome §2).
3. **Minimum fields.** `lifecycle_stage`, `last_settlement_price`, `last_settlement_date`, `current_weights` (QIS), `nav_index` (QIS/MA-bench), `triggered_barrier`, `superseded_by`, `current_benchmark_level` (where the unit is itself a benchmark observable).
4. **Identity.** `unit_id`.
5. **Provenance.** Settle, rebalance, barrier, supersede handlers (each tagged C11).
6. **Temporal semantics.** **Mutable point-in-time with snapshot-via-event-log.** The current value is the latest write; historical values are reconstructed by replaying the event log (Inv. P8). UnitStatus is registration-total (StatesHome C5).
7. **Failure consequences.** Wrong `last_settlement_price` ⇒ next VM target wrong ⇒ Σ_w accumulated_cost(w,u) = 0 algebraically still holds because the same number is used by every wallet, but value miscomputed by the exact error. Wrong `triggered_barrier` ⇒ knock-out fires when it shouldn't (or fails to fire when it should) ⇒ the entire payoff structure inverts ⇒ value invariance grossly violated. `lifecycle_stage` racing with handler-tag (C11) ⇒ a settled option re-exercised ⇒ duplicate moves ⇒ Σ_w broken.

### 5.2 PositionState (per (w,u), monotone carrier, Option accessor)

1. **Name.** `PositionState[w, u]`.
2. **Definition.** Per-position state (StatesHome §2).
3. **Minimum fields.** `accumulated_cost (ac)`, `ccp_binding`, `entry_nav` (QIS), `hwm`, `hwm_date`, `accrued_mgmt_fee`, `accrued_perf_fee`, `benchmark_nav_at_inception`, `mandate_breach_flags`, OTC `lifecycle_local_state`.
4. **Identity.** `(w, u)`.
5. **Provenance.** Trade, settle, fee-crystallise, subscribe, redeem, mandate-amend handlers (per-field C11 tag).
6. **Temporal semantics.** **Monotone carrier (StatesHome C1):** rows never deleted; close-out leaves Some(zero). Option accessor distinguishes None ("never held") from Some(zero) ("held and flat"). Snapshot-via-event-log.
7. **Failure consequences.** Wrong `accumulated_cost` ⇒ silent break of Σ_w ac(w,u) = 0 (StatesHome C2 violated at the handler). Wrong `hwm` ⇒ wrong perf fee ⇒ Σ_w cash = 0 still holds (fee paid one way) but value invariance broken on the client-side. Garbage-collected row ⇒ S4 (replay invariance) broken — apply_all over a checkpointed key set diverges from apply_all over the full set.

### 5.3 Wallet balance (the Σ_w object itself)

1. **Name.** `WalletBalance[w, u]` — also known as `w_t(u)`.
2. **Definition.** The conserved scalar (or 6-coordinate vector under SBL) that satisfies Σ_w w(u) = 0.
3. **Minimum fields.** scalar `q` for non-lendable units; the 6-coordinate vector `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` for lendable.
4. **Identity.** `(w, u)`.
5. **Provenance.** Move stream replay (state-sufficiency, v10.3 §4.2). NEVER set directly; only by Move semantics.
6. **Temporal semantics.** Derived from move stream by fold; trivially bitemporal because the stream is append-only.
7. **Failure consequences.** This is the symmetry's direct carrier — corruption is structurally impossible if all writes go through the executor (Σ_w = 0 by construction). Detection of any divergence is the conservation check itself.

### 5.4 Move and Transaction (the fundamental atom and its grouping)

1. **Name.** `Move`, `Transaction`.
2. **Definition.** v10.3 §2.3, §2.4.
3. **Minimum fields.**
   - Move: `from`, `to`, `unit`, `quantity`, `timestamp`, `source_contract_id`, `metadata`, `coordinate?` (SBL), `cdm_event_payload_ref`.
   - Transaction: `tx_id`, `type ∈ {SETTLEMENT, COLLATERAL, LIFECYCLE, ACCOUNTING, CORRECTION}`, ordered move list, total_order_seq within timestamp, `cdm_business_event_payload`.
4. **Identity.** `tx_id` (deterministic; carries idempotency under Inv. P5).
5. **Provenance.** Smart contract → executor → event log; CDM business event preserved.
6. **Temporal semantics.** **Strictly append-only (Inv. P4: log monotonicity).** Hash-chained for tamper-evidence.
7. **Failure consequences.** Move conservation breakage = structural execution failure. tx_id collision under different content = Inv. P5 broken (idempotency). Out-of-order replay under same timestamp without total_order_seq ⇒ S2 violated for *non-commutative* event sequences (e.g., barrier + trade on same instrument).

### 5.5 StateDelta (atomic per-event-class envelope)

1. **Name.** `StateDelta`.
2. **Definition.** The unit-of-work submitted to the executor: a transaction's moves plus the per-(w,u)/per-u state changes (StatesHome C3).
3. **Minimum fields.** `tx`, `unit_status_changes : Map[u, UnitStatusDelta]`, `position_state_changes : Map[(w,u), PositionStateDelta]`, `obligation_registrations : List[Obligation]`.
4. **Identity.** Same as the embedded `tx_id`.
5. **Provenance.** Lifecycle function output.
6. **Temporal semantics.** Atomic; partial application rejected (C3).
7. **Failure consequences.** A handler that mutates only some of the three maps ⇒ C3 violated ⇒ split-brain between UnitStatus and PositionState (e.g., barrier triggered in UnitStatus but PositionState rows not closed). This is the v10.3 atomicity invariant.

### 5.6 Obligation (event-triggered or scheduled liveness contract)

1. **Name.** `Obligation`.
2. **Definition.** v10.3 §14.7 Def. 14.x.
3. **Minimum fields.** `id`, `type` (taxonomy in Table 14.x), `source`, `deadline t_d`, `discharge_predicate D`, `compensation_action κ`, `state ∈ {Pending, Attempted, Discharged, Compensated, Defaulted}`.
4. **Identity.** `obligation.id` deterministic from source event.
5. **Provenance.** Lifecycle function output (per Princ. obligation-completeness).
6. **Temporal semantics.** State transitions logged in event log; append-only.
7. **Failure consequences.** Missing obligation registration ⇒ liveness P21 broken silently ⇒ contractual obligation never discharged. Wrong deadline ⇒ compensation κ fires too early/late ⇒ wrongful default.

---

## 6. Listed-instrument detail data (exchange-published specs)

This is a *strict subset* of static + reference data; calling it out separately is justified by its single-authority provenance discipline.

### 6.1 ContractSpec (exchange-listed deriv / future)

1. **Name.** `ContractSpec[exchange, root, expiry, [strike, type]]`.
2. **Definition.** The exchange-published machine description of a listed series, mapped 1:1 to a unit_id under the Tier-1/Tier-3 separation.
3. **Minimum fields.**
   - Universal: `exchange_mic`, `product_root`, `expiry`, `multiplier`, `tick_size`, `currency`, `settlement_type ∈ {CASH, PHYSICAL}`, `last_trade_date`, `first_notice_date?`, `last_delivery_date?`.
   - Option-specific: `option_type ∈ {CALL, PUT}`, `strike`, `exercise_style ∈ {EUROPEAN, AMERICAN, BERMUDAN}`, `auto-exercise threshold`.
   - Future-specific: `delivery_month`, `quality_spec?`, `contract_size_in_underlier`.
   - CCP binding: `clearinghouse_lei`, `clearing_member_account_id?`.
   - Lot / round-lot: `board_lot`, `delivery_lot`.
4. **Identity.** Deterministic hash of the contract-spec fields (per v10.3 §3.4).
5. **Provenance.** Exchange reference data feed (CME, ICE, Eurex, OSE) at listing time.
6. **Temporal semantics.** **Append-only; correction only via re-issuance.** A re-listed contract gets a new unit_id (StatesHome C8 breaking) — never an in-place edit.
7. **Failure consequences.**
   - Wrong `multiplier` ⇒ Σ_w ac silent break (canonical, see §1.1).
   - Wrong CCP binding ⇒ clearing-flow misroutes ⇒ external custodian disagreement ⇒ a boundary failure conservation cannot detect.
   - Same root listed on two CCPs without distinct unit_ids ⇒ S12 fungibility broken (CME-ES and ICE-ES collapse) ⇒ Σ_w = 0 holds vacuously while economic exposure is wrong.

### 6.2 Exchange and CCP calendars

A specialisation of §2.2; called out because exchange holiday calendars differ from sovereign business-day calendars and govern futures EOD settlement.

1. **Name.** `ExchangeCalendar[mic]`.
2. **Definition.** Per-exchange trading days, EOD timestamps, half-day rules, holiday list.
3. **Minimum fields.** `mic`, `version_id`, `trading_days`, `eod_settle_time`, `half_days`, `weekend_rule`.
4. **Identity / provenance / temporal / failure consequences.** As §2.2 with `mic` as primary key. Wrong EOD time ⇒ futures VM fires against wrong settle price ⇒ value invariance break.

---

## 7. Time and clock data (proposed addition)

The v10.3 spec is silent on how wall-clock time is sourced. Yet S3 (time-translation invariance), liveness (P21), and replay determinism (S4) all depend on it.

1. **Name.** `TimeAuthority[clock_id, t]`.
2. **Definition.** The authoritative source of "what time is it" used by the executor and the Temporal scheduler.
3. **Minimum fields.** `clock_id` (NTP source, hardware TSC, exchange timestamp authority), `monotonic_offset`, `last_drift_correction`, `precision_ns`.
4. **Identity.** `clock_id`.
5. **Provenance.** NTP / PTP / GPS / atomic-clock peer.
6. **Temporal semantics.** The clock IS the temporal axis. Drift events are recorded as bitemporal corrections.
7. **Failure consequences.** Two events given the same timestamp without `total_order_seq` ⇒ replay non-deterministic when handlers are non-commutative (e.g., barrier + trade) ⇒ S4 broken. Clock skew between executor and Temporal worker ⇒ obligation deadlines fire early/late ⇒ P21 false default. Backwards-running clock ⇒ append-only invariant breaks.

> **Floor-category disagreement.** The original floor category list omits Time. Time is not "static", "reference", "market", "oracle", "execution", or "listed-instrument". It is a primary symmetry-defining datum and must be enumerated separately.

---

## 8. Calibration state / latent-parameter data (proposed addition)

The Kalman filter (valuation §4) maintains a latent state `x_{t|t}` and posterior covariance `P_{t|t}` that is *neither* raw market data nor a final certified curve — it is a memoised filter state. It is the carrier of S10 (parameter martingale) and S11 (innovation symmetry).

1. **Name.** `KalmanState[calibrated_object_id, t]`.
2. **Definition.** The filtered posterior of the calibration FSM, between observation epochs.
3. **Minimum fields.** `object_id`, `state_vector x_{t|t}`, `covariance P_{t|t}`, `process_noise Q`, `transition_matrix A` (typically I), `observation_model H_t`, `observation_noise R_t`, `last_innovation`, `last_mahalanobis_D2`, `chi2_threshold`, `last_certification_status`.
4. **Identity.** `(object_id, t)`.
5. **Provenance.** Kalman workflow recursion: `(x_{t-1|t-1}, P_{t-1|t-1}, y_t, R_t) → (x_{t|t}, P_{t|t})`.
6. **Temporal semantics.** **Recurrent state with deterministic checkpoint.** Each `(t, object_id)` pair stored; replay re-derives by deterministic recursion from any prior checkpoint (same observations + same noise model).
7. **Failure consequences.** Loss of `P_{t|t}` ⇒ next innovation gating wrong-scaled ⇒ S11 broken ⇒ bad data slips through certification or good data is rejected ⇒ FSM Stale cascade. Mutating Q post-hoc ⇒ historical innovation residuals re-interpret ⇒ S3 broken.

> **Floor-category disagreement.** The Kalman state is intermediate between raw market data (§3.1) and certified curves (§3.2). The original floor enumeration places it in neither; it must be its own category because its corruption mode is distinct from both.

---

## 9. Identity / party reference (cross-cutting; proposed addition or floor #2 split)

Floor category 2 ("Reference data --- calendars, conventions, currency/entity/venue identifiers, regulatory classes") bundles two distinct data classes with different temporal semantics and different conservation footprints. The Noetherian split is into Ref-2A (this section) and Ref-2B (§2.2). The identity-and-party class is enumerated explicitly here because:

- It is the carrier of Σ_w ranging set: the very *names of wallets* live here.
- LEI restatement (e.g., entity merger with LEI rolloff) is a non-trivial event that wallet-relabelling (S1) must absorb.

(Field structure already enumerated in §2.1; flagged here so it is not lost in the floor-2 catch-all.)

---

## 10. Settlement-feedback / external-record data

Not in the original floor list but materially needed: confirmations from the boundary that re-enter the ledger as state events (sese.025, camt.054, custodian statements, CCP margin reports).

1. **Name.** `SettlementConfirmation[instruction_id, t]`, `CustodianBalance[(custodian, w_external_id, isin, t)]`, `CCPMarginReport[(ccp, member, t)]`.
2. **Definition.** External records that the boundary delivers back into the ledger as state-only events (v10.3 §8.6).
3. **Minimum fields.** `instruction_id`, `external_ref`, `status ∈ {INSTRUCTED, SETTLED, FAILED, PARTIAL}`, `settlement_date`, `delivered_quantity`, `delivered_amount`, `failure_reason?`.
4. **Identity.** `(external_authority, external_ref)`.
5. **Provenance.** CSD (DTC, Euroclear), correspondent bank, CCP margin engine.
6. **Temporal semantics.** Append-only state-events on the corresponding transaction (EXECUTED → INSTRUCTED → SETTLED/FAILED).
7. **Failure consequences.** Lost confirmation ⇒ the ledger's "INSTRUCTED" status is permanent; a virtual-wallet reconciliation eventually shows a break — this is the one boundary failure that *cannot* be made structurally unreachable. Wrong external balance reported ⇒ virtual-wallet vs custodian-record reconciliation flags it.

---

## 11. Floor coverage and disagreements

| Floor # | Floor name | Covered by §§ | Disagreement |
|---|---|---|---|
| 1 | Static | §1 (ProductTerms, Schedule, Parties) | None — but Schedule is materially distinct and deserves the sub-section. |
| 2 | Reference | §2 (split into 2A identity, 2B computational), §6.2 | The floor merges two classes that have different temporal disciplines. The Noetherian discipline forces the split. |
| 3 | Market | §3 (quotes, curves, fixings, FX, dividends, borrow, repo, credit, recovery) | None. |
| 4 | Oracle | §4 | Floor underspecified: oracle is *attestation-bearing market data*; the discriminating feature is contract-boundary crossing + signature, not the data values. |
| 5 | Smart-contract execution | §5 (UnitStatus, PositionState, WalletBalance, Move/Tx, StateDelta, Obligation) | None. The StatesHome 3-map ruling makes this rich. |
| 6 | Listed-instrument | §6 | A subset of §1 + §2.2 with a single-authority provenance discipline. Deserves separation. |

**Three additions:**
- **§7 Time / clock authority** — floor list omits the very axis of S3.
- **§8 Calibration state (Kalman)** — distinct from raw market (§3.1) and certified curves (§3.2).
- **§10 Settlement-feedback / external records** — the boundary return path is data, not a sub-class of any floor item.

**One soft disagreement:** Floor 1 (Static) and Floor 2 (Reference) overlap heavily — calendars, conventions, lot sizes are *referenced from* static terms but live in shared reference data. The StatesHome 3-map already handles this (ProductTerms versions point at calendar version IDs). The Noetherian split is along temporal-discipline lines (point-in-time vs versioned-immutable vs bitemporal-mandatory), not along the static/reference axis.

---

## 12. Silent Σ_w = 0 conservation-law violators (executive summary)

The data items whose corruption cannot be detected by any conservation check, lifecycle idempotency, or property-based test in v10.3, and which therefore demand the strongest provenance / version-pinning discipline:

| Datum | Symmetry it carries | How corruption escapes detection |
|---|---|---|
| `multiplier` (ProductTerms / ContractSpec) | S5 | Both legs use the same wrong multiplier; Σ_w cancels. |
| Calendar version (§2.2) | S3, S6 | Σ_w holds; settlement-date mismatch surfaces only at boundary. |
| Day-count convention | S3 | Σ_w cash holds; accrued-vs-cash equivalence breaks. |
| Oracle attestation pre-image | S3, S4 | Σ_w holds; cash flows in wrong amounts symmetrically. |
| FX rate snapshot consistency | S7 | Per-currency conservation holds; mixed-snapshot V_t is wrong. |
| Manufactured-dividend rate (SBL) | S5, S9 | Conservation holds; lender economic-equivalence fails. |
| Calibration `Q` / `R` post-hoc edit | S10, S11 | Innovation gating false-passes / false-rejects; everything downstream contaminated. |
| `is_fungibility_preserving` predicate | S12, S3 | Wrong amendment classification leaves units silently merged or split. |
| Holiday calendar bitemporal mode | S3 | Replay regenerates schedules with a calendar that didn't exist at deal time. |
| LEI restatement without bitemporal split | S1 | Counterparty identity silently changes under replay. |

Each of these is a *Noether-current break* that the data layer must defend against by structural means (version pinning, attestation-chain anchoring, bitemporal mandatory) because no executor check or property-based test will catch them.

---

## 13. Summary of every datum with its symmetry

| § | Datum | Primary symmetry | Conservation broken on corruption |
|---|---|---|---|
| 1.1 | ProductTerms | S3, S5, S12 | Σ_w w(u) = 0 (via multiplier); P6 immutability |
| 1.2 | Schedule | S3, S6 | Liveness P21; value invariance |
| 1.3 | Parties | S5, S8 | Regulatory obligation completeness |
| 2.1 | Identity ref data | S1, S12 | Σ_w via unit-identity collision |
| 2.2 | Calendars / conventions / lot | S3, S6 | Schedule determinism; value invariance |
| 3.1 | Quotes / fixes | S11 | Calibration certification; value invariance |
| 3.2 | Curves / surfaces | S10, S11 | PnL explain residual; arbitrage-free pricing |
| 3.3 | Fixings | S5, S3 | Value invariance for IRS/floating instruments |
| 3.4 | FX rates | S7 | Reporting-currency PnL invariance |
| 3.5 | Dividends / corporate actions | S5, S2 | Σ_w w(u) = 0 directly (record-date entitlement) |
| 3.6 | Borrow / repo | S5 | SBL fee value invariance; structured-note pricing |
| 3.7 | Credit / recovery | S5 | Default-payout cash conservation |
| 4 | Oracle attestation | S3, S4, S5 | Lifecycle value invariance (silent); liveness |
| 5.1 | UnitStatus | S3, S4, C5 | StateDelta atomicity; barrier/lifecycle integrity |
| 5.2 | PositionState | S4, C1, C2 | Σ_w accumulated_cost = 0 (silent at handler level) |
| 5.3 | WalletBalance | S1 | Σ_w w(u) = 0 directly |
| 5.4 | Move / Transaction | S2, S5 | Atomicity P2; idempotency P5 |
| 5.5 | StateDelta | C3 | Cross-map split-brain |
| 5.6 | Obligation | --- (liveness) | P21 obligation liveness |
| 6.1 | ContractSpec | S5, S12 | Σ_w via multiplier or CCP-collision |
| 6.2 | Exchange / CCP calendar | S3, S6 | EOD settle determinism |
| 7 | Time / clock | S3, S4 | Replay determinism; obligation deadlines |
| 8 | KalmanState | S10, S11 | Calibration certifiability |
| 10 | Settlement feedback | --- (boundary) | Virtual-wallet reconciliation |

---

*"The symmetry a datum carries is the conservation law its corruption breaks. To know what to defend, find the symmetry."*
