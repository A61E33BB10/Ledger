# Phase 1 Data Enumeration — Matthias Vogt (CDM / Rosetta DSL Discipline)

**Author role:** Principal Engineer, FINOS CDM core team. Reviewer of the Rosetta product, event, legal-agreement, and collateral models. Author of FpML synonym mappings. CDM 6.0.0 expert.

**Scope:** Phase 1, independent enumeration. Every Ledger v11.0 data category, viewed through the CDM/Rosetta lens. Each item carries the seven mandatory Phase-1 fields plus an eighth field — **CDM cross-walk** — naming the exact CDM 6.0.0 type and path, mapping status (direct / partial / missing), and a Rosetta-syntax extension sketch where a gap requires it.

**Floor categories I argue for (with disagreements logged):**
1. Static (Reference Data) — kept, but **subsumes "Reference"**.
2. ~~Reference~~ — **redundant against Static**; collapsed.
3. Market — kept, but **split into raw Observable and Calibrated** (the v1.0 Valuation doc forces this).
4. Oracle (Attestation) — kept, but **re-scoped** to "external authoritative claim" (custodian, CSD, exchange, regulator, counterparty, vendor, Kalman-filter output).
5. Smart-contract execution — kept, but **renamed to "Smart Contract & Lifecycle Execution"** because the v10.3 spec treats the contract program AND its emitted moves AND its unit-state transitions as one execution corpus.
6. Listed-instrument detail — kept, but **demoted to a sub-sector of Static**; it is not its own floor. Argued in §0.

I add **one new floor**:

7. **Legal & Agreement** — the ISDA Master, CSA, GMSLA, MSFTA, Confirmation, Definitions Booklet bundle. v10.3 §6.4, §10.3, §17 lean on it heavily; v10.3 §10.6 says "Trade.collateral references CDM CollateralProvisions"; this data has nowhere else to live. CDM has a dedicated `cdm-legalagreement-lib`. Folding it into "Static" (where the v0 floor categorisation likely had it) loses the version semantics, the governing-law axis, and the netting-set perimeter.

I also add an **eighth floor for completeness**, which the v0 list omitted:

8. **Identity, Provenance & Audit** — the move-stream metadata, transaction-id, EndToEndId, UTI, USI, LEI, BIC, MIC, ISIN, CUSIP, transaction provenance chain, correction-link metadata, hash-chained log entries. v10.3 §8 (substantiation), §9 (CDM mapping), §11 (settlement) all treat this as load-bearing but the v0 floor categories nowhere named it.

That gives **eight floors**, not six. The remainder of this document enumerates one item per data category, organised by floor.

---

## §0 Floor-Category Disputes

| Original floor | Verdict | Reason |
|---|---|---|
| 1 Static | Keep | Tier-1 of the Unit Store. CDM `TransferableProduct` / `NonTransferableProduct`. |
| 2 Reference | **Collapse into Static** | Every example that v0 placed under "Reference" (issuers, exchange calendars, holiday tables, accrual conventions) is either an attribute of `AssetBase` / `ProductIdentifier` / `BusinessCenters` (Static) or a calibration input (Market/Calibrated). Maintaining a separate "Reference" floor doubles the registration surface for no gain. |
| 3 Market | **Split** | Ledger Valuation v1.0 §6 (Kalman) makes raw quotes and calibrated parameter-vectors structurally distinct objects with different mutation disciplines. They cannot share a category. |
| 4 Oracle | Keep but **re-scope** | An "oracle" in this framework is any external authoritative claim arriving at the ledger boundary: custodian statements, CSD confirmations, exchange settlement prices, FpML confirmations, ISO 20022 messages, regulatory acknowledgements, and Kalman-certified parameters. The v0 sense (price feed) is too narrow. |
| 5 Smart-contract execution | Keep but **rename** | The execution corpus is: contract program, emitted moves, unit-state transitions, and `BusinessEvent` payloads. Calling this just "execution" hides three of the four. |
| 6 Listed-instrument detail | **Demote to Static sub-sector** | An `ExchangeContractSpec` is a Tier-1 Static record. It is not a separate floor; it is one row class inside the Unit Store's Tier-1. Promoting it to a floor inflates the taxonomy and obscures the OTC/Listed unit-identity dichotomy that is in fact governed by the `Trade` layer (v10.3 §3.2, App B §6). |
| **NEW: 7 Legal & Agreement** | **Add** | CDM `cdm-legalagreement-lib` is its own library because legal data is a distinct discipline (governing law, version, fungibility predicates, netting-set boundary). Ledger v10.3 attaches this at `Trade.collateral` and `Trade.contractDetails`, both of which point into agreement objects. Without this floor, the CSA, GMSLA, ISDA Master, and Confirmation have no canonical home. |
| **NEW: 8 Identity, Provenance & Audit** | **Add** | The move-stream metadata schema (v10.3 Def 2.3) carries `tx_id`, `source` (contract ref), `timestamp` (economic + booking), `corrects` (correction-link), and external references (UTI, EndToEndId). v10.3 §1.2 Property 6 (Time Travel) and §8 (Substantiation) cannot operate without this floor. CDM partially covers it (`TradeIdentifier`, `EventIdentifier`, `MetaFields`); the rest is Ledger-native. |

---

## Item Format

Each item below has the eight mandatory fields:

1. **Canonical name**
2. **Definition**
3. **Minimum field set**
4. **Identity** (how a row is uniquely keyed)
5. **Provenance** (where the data originates, who authoritatively owns it)
6. **Temporal semantics** (mutation discipline: immutable / append-only / mutable / shared / monotone-carrier; effective-time vs booking-time)
7. **Failure consequences** (what breaks in the ledger if this item is wrong, missing, or stale — keyed to the v10.3 invariant register P1–P23)
8. **CDM cross-walk** — exact CDM 6.0.0 type and path, mapping status (direct / partial / missing), with a Rosetta-syntax sketch where the gap requires extension.

All Rosetta snippets use CDM 6.0.0 / Rune DSL conventions: `PascalCase` types, `camelCase` fields, `(min..max)` cardinalities, `[metadata key]` annotations, `EnumName.VALUE` enum literals.

---

# Floor 1 — Static (Reference Data, including Listed-Instrument Detail)

These data items are Tier-1 of the Unit Store (v10.3 §3.3.1). They map to CDM `AssetBase`, `TransferableProduct`, `NonTransferableProduct`, and the `*Identifier` / `*Taxonomy` types. Their mutation discipline is `ProductTerms` (StatesHome addendum): **immutable, versioned, append-only, registration-total**. Conditions C5, C6, C7, C8, C10 of the addendum apply directly to every item in this floor.

---

### 1.1 Currency Unit (Cash)

1. **Canonical name:** `CurrencyUnit`
2. **Definition:** A fungible cash unit identified by ISO 4217 currency code. Constitutes the bulk of every wallet's economic surface.
3. **Minimum field set:** `currencyCode` (ISO 4217), `minorUnitDigits` (typically 2 for fiat, 8+ for crypto-like cash), `legalTender` flag, `centralBankIssuer` (LEI of issuing central bank, optional for non-fiat).
4. **Identity:** `currencyCode` is the deterministic key. All USD balances net.
5. **Provenance:** ISO 4217 registry. Pre-registered at system inception (v10.3 §3.4 channel 1).
6. **Temporal semantics:** Immutable. Lifecycle stage permanently `ACTIVE`. Currency redenominations (e.g., a hypothetical EUR-2 introduction) are handled by C8's *Breaking* track: allocate fresh `unit_id`, stamp `SupersededBy` on the old.
7. **Failure consequences:** Wrong `minorUnitDigits` produces rounding violations in instruction generation (v10.3 §5.1 fixed-precision requirement). Missing `currencyCode` blocks all cash settlement projections (v10.3 §11). Conservation P1 still holds (because the move primitive is currency-agnostic), but DvP atomicity downstream breaks.
8. **CDM cross-walk:**
   - **Type:** `Cash` extends `AssetBase`. Path: `cdm-product-lib/src/main/rosetta/product/asset/Asset.rosetta` — `Cash` is one branch of the `Asset` choice.
   - **Status:** **Direct.** `Cash.currency` (FieldWithMeta<string>) carries the ISO 4217 code; `AssetBase.identifier AssetIdentifier (1..*)` and `AssetBase.taxonomy Taxonomy (0..*)` provide the keys.
   - **Gap:** None.

---

### 1.2 Listed Equity (ISIN-keyed Security)

1. **Canonical name:** `ListedEquity`
2. **Definition:** An exchange-listed share, fungible across all exchanges where it is dual-listed (subject to the same corporate-action stream).
3. **Minimum field set:** `isin`, `cusip`/`sedol` (alt identifiers), `issuerLEI`, `primaryExchange` (MIC), `listingCurrency`, `lotSize` (board lot), `votingRights`, `dividendPolicyRef`, `corporateActionFeedRef`.
4. **Identity:** `isin`. Two positions in the same `isin` net (v10.3 §3.2 unit-identity table).
5. **Provenance:** Exchange listing data + reference data vendor (Bloomberg, Refinitiv, ISO via ANNA). Tier-1 channel 2 (v10.3 §3.4).
6. **Temporal semantics:** Mostly immutable. Issuer changes (rebranding, LEI reassignment) are *Preserving* amendments → append `TermsVersion` (C8 Preserving). Spin-off / merger that produces a new ISIN is *Breaking* → fresh `unit_id` + `SupersededBy`.
7. **Failure consequences:** Wrong `lotSize` violates the lot-size physical-delivery logic (v10.3 §5.4) → buy-in cost. Wrong `isin` collapses non-fungible positions into one balance, violating P3 (referential integrity). Missing `corporateActionFeedRef` causes idempotency P5/P6 failure on dividend/split events.
8. **CDM cross-walk:**
   - **Type:** `Security` extends `Instrument` extends `AssetBase`. Listed equity uses `Security` with `securityType = SecurityTypeEnum.EQUITY`.
   - **Path:** `cdm-product-lib/src/main/rosetta/product/asset/Security.rosetta`.
   - **Status:** **Direct** for ISIN, issuer, currency. **Partial** for `lotSize` (CDM has no first-class `boardLot` field on `Security`), `votingRights`, `dividendPolicyRef`.
   - **Gap sketch:**
     ```rosetta
     type SecurityListingExtensions:
         security Security (1..1)
             [metadata reference]
         boardLotSize int (0..1)
         votingRights VotingRightsEnum (0..1)
         dividendPolicyReference DividendPolicy (0..1)
         corporateActionFeed string (0..1)
     ```
   - **Verification status:** I have not re-fetched `Security.rosetta` against the live `rosetta-models/common-domain-model` repository in this Phase-1 cycle. Confirm before merge.

---

### 1.3 Listed Derivative Contract Specification

1. **Canonical name:** `ExchangeContractSpec`
2. **Definition:** The full contract specification for an exchange-listed derivative — option series or futures contract — that establishes fungibility within the series.
3. **Minimum field set:** `exchange` (MIC), `productCode` (e.g., ES, NQ, SPXW), `underlier` (Observable), `multiplier`, `currency`, `expiry`, `strike` (option only), `optionType` (option only), `settlementMethod` (cash / physical), `lastTradeDate`, `firstNoticeDate` (futures only), `tickSize`, `lotSize`, `clearingHouse` (per v10.3 §7.4 *per-wallet* clearinghouse — also see StatesHome addendum §4.1).
4. **Identity:** Hash of (`exchange`, `productCode`, `expiry`, `strike` if any, `optionType` if any). Per v10.3 line 1168 and StatesHome addendum §4.1, **CME-ES and ICE-ES are distinct units**; CCP identity is part of the Static identity for CCP-segregated regulatory exposure (EMIR Art 4).
5. **Provenance:** Exchange contract specification feed (CME SPAN files, OCC reference files, Eurex contract directory). Tier-1.
6. **Temporal semantics:** Immutable after listing. Contract specification changes are *Breaking* (force a new contract series). Expiration is a `lifecycle_stage` transition in `UnitStatus`, not a `ProductTerms` change.
7. **Failure consequences:** Wrong `multiplier` invalidates every variation-margin computation (v10.3 §7.5 futures example: ES at 4530 with mult=50 settles at JPY 16,000; with mult=100 it settles at JPY 32,000 — a 100% PnL miscalculation). Missing `lastTradeDate` blocks the `EXPIRE` lifecycle transition. Wrong `clearingHouse` corrupts the per-CCP exposure aggregation required for EMIR.
8. **CDM cross-walk:**
   - **Type:** `ListedDerivative` extends `Instrument` (CDM 6.0.0). Path: `cdm-product-lib/src/main/rosetta/product/asset/`.
   - **Status:** **Partial.** v10.3 §3.10 explicitly flags this: *"CDM's listed derivative coverage is thinner than its OTC coverage: the same `NonTransferableProduct` type serves both, without a dedicated 'contract specification' type for exchange listings."* The `EconomicTerms` of a listed option/future are correct; the dedicated *catalogue-level* concept is missing.
   - **Gap sketch:**
     ```rosetta
     type ExchangeContractSpec:
         [metadata key]
         exchange ExchangeEnum (1..1)
         productCode string (1..1)
         underlier Observable (1..1)
         contractMultiplier number (1..1)
         settlementCurrency string (1..1)
         clearingHouse Party (1..1)
             [metadata reference]
         tradingTerms ListedTradingTerms (1..1)
         derivativeTerms NonTransferableProduct (1..1)
             [metadata reference]

     type ListedTradingTerms:
         lastTradingDate AdjustableDate (1..1)
         firstNoticeDate AdjustableDate (0..1)
         tickSize number (1..1)
         boardLotSize int (1..1)
         settlementMethod SettlementTypeEnum (1..1)
     ```
   - **Severity:** Significant. Discussed in FINOS CDM GitHub issues around exchange-traded coverage; partial extensions exist in `cdm-product-lib` but are not coherent at the catalogue level.

---

### 1.4 Bond / Fixed-Income Reference Terms

1. **Canonical name:** `BondTerms`
2. **Definition:** Static contractual terms of a debt instrument: face value, coupon schedule, day-count convention, redemption profile, callability, ranking.
3. **Minimum field set:** `isin`, `issuerLEI`, `faceValue`, `currency`, `couponRate` (or step-up schedule), `couponFrequency`, `dayCountFraction` (ACT/360, ACT/ACT, 30/360, etc.), `firstCouponDate`, `maturityDate`, `redemptionPrice`, `callSchedule` (optional), `seniority`.
4. **Identity:** `isin`. v10.3 §3.2 confirms "Bond — ISIN — All holdings of same ISIN net".
5. **Provenance:** Issuer prospectus → reference data vendor → ANNA / DTCC / Euroclear. Tier-1.
6. **Temporal semantics:** Mostly immutable. Coupon step-ups encoded as a schedule are *Preserving*. Restructuring (debt exchange, write-down) is *Breaking* per C8.
7. **Failure consequences:** Wrong `dayCountFraction` produces an incorrect accrued-interest computation (v10.3 §5.3 dirty/clean price split) → all bond valuations misstated. Missing `firstCouponDate` blocks the lifecycle scheduler (v10.3 §14.6 Due-Event Scheduler) from generating coupon-payment timers. Wrong `maturityDate` causes redemption to fail.
8. **CDM cross-walk:**
   - **Type:** `Bond` (in `cdm-product-lib/src/main/rosetta/product/asset/Security.rosetta` — Bond is a `securityType` discriminator, not a top-level type).
   - **Status:** **Partial.** CDM has good coverage of bond identifiers, issuer, ranking via `DebtType`. Coupon mechanics are modelled via a separate `InterestRatePayout` if treated as a contractual obligation — but a vanilla bond is conventionally just a `Security` with mostly-flat terms. **CDM does not natively model coupon schedules on plain bonds** as first-class structured data; it expects the lifecycle to be driven externally.
   - **Gap sketch:**
     ```rosetta
     type BondCouponSchedule:
         bond Security (1..1)
             [metadata reference]
         couponRate Rate (1..1)
         couponFrequency Frequency (1..1)
         dayCountFraction DayCountFractionEnum (1..1)
         firstCouponDate date (1..1)
         maturityDate date (1..1)
         redemptionPrice number (1..1)
         callSchedule CallableProvision (0..*)
     ```
   - **Severity:** Significant. Open issue in FINOS CDM GitHub on first-class debt-instrument coverage.

---

### 1.5 OTC Product Template (`NonTransferableProduct`)

1. **Canonical name:** `OTCProductTemplate`
2. **Definition:** The reusable, counterparty-agnostic, CSA-agnostic specification of an OTC derivative — payout logic + economic terms wrapper. *Not yet a unit*; becomes a unit only when bound to a `Trade`.
3. **Minimum field set:** `economicTerms` (which contains `payout (1..*)`, `effectiveDate`, `terminationDate`, `dateAdjustments`, `terminationProvision`, `calculationAgent`), `productIdentifier`, `productTaxonomy`.
4. **Identity:** Deterministic hash of `economicTerms` (the `[metadata key]` annotation on `NonTransferableProduct`). Two trades with identical economic terms reference the same template (v10.3 §16.4).
5. **Provenance:** Constructed at the moment a trade is captured (FpML confirmation → `NonTransferableProduct`) or during product registration (DRR / SDR feeds).
6. **Temporal semantics:** Immutable once registered (C6, C7). Amendments to underlying terms produce a new template via C8 Breaking-track.
7. **Failure consequences:** A malformed `EconomicTerms` (e.g., `payout` cardinality 0) causes the qualification function to fail and the unit registration to be rejected (v10.3 §3.5 correctness gate). Wrong `terminationDate` corrupts the lifecycle scheduler.
8. **CDM cross-walk:**
   - **Type:** `NonTransferableProduct`. Path: `cdm-product-lib/src/main/rosetta/product/template/NonTransferableProduct.rosetta`.
   - **Status:** **Direct.** This is the canonical CDM type for the concept. The `[metadata key]` is load-bearing.
   - **Rosetta excerpt** (from memory; verify against repo):
     ```rosetta
     type NonTransferableProduct:
         [metadata key]
         identifier ProductIdentifier (0..*)
         taxonomy ProductTaxonomy (0..*)
         economicTerms EconomicTerms (1..1)
     ```
   - **Gap:** None at this layer.

---

### 1.6 Calendar, Holiday, and Business-Day Convention Tables

1. **Canonical name:** `BusinessCenters` + `BusinessDayConventions`
2. **Definition:** The set of named business centres (e.g., USNY, EUTA, GBLO, JPTO) and their daily calendar status (open / public-holiday). Required for every adjusted-date computation.
3. **Minimum field set:** `businessCenter` (enum), `holidayCalendar` (Map<date → status>), `businessDayConvention` (`MODFOLLOWING`, `FOLLOWING`, `PRECEDING`, `NONE`), `effectiveDate` per amendment.
4. **Identity:** `businessCenter` enum value.
5. **Provenance:** ISDA Definitions → vendor calendars (FINCAL, Bloomberg) → custodian published holiday lists. Authoritative source: ISDA 2021 Definitions for derivatives; CSD official-trading-day announcements for securities.
6. **Temporal semantics:** Append-only — holiday announcements are added forward; never retroactively removed. Each calendar entry has an `announcedDate` and an `effectiveDate`. v10.3 line 619 requirement of "fixed-precision decimal arithmetic" applies; calendar lookups must be deterministic.
7. **Failure consequences:** Wrong holiday entry shifts a coupon date by one business day → the lifecycle event fires on the wrong day → P5 (lifecycle idempotency) holds because the unit-state mark guards against re-firing, but the *correctness* of the cash flow date is wrong. Stale calendar (missing a newly-announced holiday) shifts settlement obligations.
8. **CDM cross-walk:**
   - **Type:** `BusinessCenters`, `BusinessCenterEnum`, `BusinessDayConventionEnum`. Path: `cdm-base-lib/src/main/rosetta/base/datetime/`.
   - **Status:** **Direct.** CDM has thorough coverage of business-day adjustment types and centres. CDM does *not* itself ship the holiday tables (which is correct — those are external authoritative data).
   - **Gap:** None on the type system. Operational gap on the data pipeline (which must be sourced and audited externally).

---

### 1.7 Day-Count Fractions / Accrual Conventions

1. **Canonical name:** `DayCountFractionEnum`
2. **Definition:** The convention for converting a calendar period into a year-fraction for accrual computations. Standard values: ACT/360, ACT/365.FIXED, ACT/ACT.ISDA, ACT/ACT.ICMA, 30/360.ISDA, 30E/360, 1/1.
3. **Minimum field set:** `enumValue` (one of the above), `definitionSource` (ISDA 2006 §4.16, ICMA Rule 251).
4. **Identity:** Enum value.
5. **Provenance:** ISDA / ICMA / FpML standards. Static.
6. **Temporal semantics:** Immutable. New enum values appended over time; existing values never repurposed.
7. **Failure consequences:** Wrong DCF on an IRS produces a payment that disagrees with the counterparty's by ~0.5–1.5 bp of notional → trade-confirmation break → CSA dispute. Property P9 (PnL path-independence) does not detect this because both sides use the same wrong DCF; the counterparty does not.
8. **CDM cross-walk:**
   - **Type:** `DayCountFractionEnum`. Path: `cdm-base-lib/src/main/rosetta/base/datetime/`.
   - **Status:** **Direct.**
   - **Gap:** None.

---

# Floor 2 — Calibrated Market Data (formerly part of "Market")

These are the Kalman-filter-output objects that feed the leaf nodes of the Pricing DAG (Valuation v1.0 §4 and §6). They are not raw observations; they are inferred parameter vectors with covariances and certification flags.

---

### 2.1 Calibrated Yield Curve

1. **Canonical name:** `CalibratedYieldCurve`
2. **Definition:** Bayesian-posterior parameter vector over zero rates at canonical tenors (1M, 3M, 6M, 1Y, …, 30Y), produced by a Kalman filter from raw deposit/futures/swap quotes, certified against no-arbitrage constraints.
3. **Minimum field set:** `currency`, `referenceIndex` (SOFR, ESTR, TONA), `valuationDate`, `tenorPoints` (Vector<(Tenor, ZeroRate)>), `posteriorCovariance` (Matrix), `innovationStatistic` (Mahalanobis distance), `arbitrageFreeCertified` (bool), `lastObservationTimestamp`, `kalmanWorkflowId`.
4. **Identity:** (`currency`, `referenceIndex`, `valuationDate`, `kalmanWorkflowId`).
5. **Provenance:** Kalman filter Temporal workflow output (Valuation v1.0 §6), feeding from raw quote attestations.
6. **Temporal semantics:** Append-only. Each Kalman update epoch produces a new versioned record; the "current" curve is the latest certified row. Stale-ness threshold per Valuation FSM (T8 transition).
7. **Failure consequences:** Stale curve → stale IRS PnL, stale bond DV01, stale SBL margin → P9 (PnL path-independence) holds for the ledger but the valuations themselves are stale, triggering FSM transition `T8 → STALE`. Arbitrage-violating curve corrupts every downstream price; certification gate (Valuation v1.0 §6.6) catches this before publish.
8. **CDM cross-walk:**
   - **Type:** Closest CDM type is `Curve` / `YieldCurveDefinition` — but **CDM does not model calibrated parameter vectors**, only the schedules of underlying instruments. The Calibration Manifesto and the Valuation v1.0 doc operate in a layer that CDM has not addressed.
   - **Status:** **Missing.** This is a real CDM gap.
   - **Gap sketch:**
     ```rosetta
     type CalibratedYieldCurve:
         [metadata key]
         currency string (1..1)
         referenceIndex InterestRateIndex (1..1)
             [metadata reference]
         valuationDate date (1..1)
         tenorPoints CurvePoint (1..*)
         posteriorCovariance CurveCovariance (1..1)
         innovationStatistic number (1..1)
         arbitrageFreeCertified boolean (1..1)
         kalmanWorkflowId string (1..1)
         lastObservationTimestamp zonedDateTime (1..1)

     type CurvePoint:
         tenor Period (1..1)
         zeroRate number (1..1)
     ```
   - **Severity:** Significant. CDM was never designed to be a calibration store; this is appropriately Ledger-native, but the contract should be documented as a CDM extension at this firm rather than left implicit.

---

### 2.2 Calibrated Volatility Surface

1. **Canonical name:** `CalibratedVolSurface`
2. **Definition:** Parameter vector for an equity / FX / commodity implied-vol surface, in the chosen vol model (Black–Scholes scalar, SABR 4-tuple, Heston 5-tuple, kernel-vol coefficient bundle, or local-vol grid).
3. **Minimum field set:** `underlier` (Observable), `valuationDate`, `volModelId`, `parameters` (model-specific), `posteriorCovariance`, `expirySlices` (per-expiry sub-surfaces), `dupireConsistent` (bool), `butterflyArbitrageFree` (bool), `calendarArbitrageFree` (bool), `kalmanWorkflowId`.
4. **Identity:** (`underlier`, `valuationDate`, `volModelId`, `kalmanWorkflowId`).
5. **Provenance:** Kalman filter Temporal workflow per surface (Valuation v1.0 §6.2).
6. **Temporal semantics:** Append-only. The "current" surface is the latest certified.
7. **Failure consequences:** Wrong surface produces wrong option deltas / vegas / Jacobians → wrong PnL explain → false QUARANTINED units → operational alert burst. Vanishing-vega problem (Valuation v1.0 §3.3) means the model identity must be tracked; mixing models in PnL explain produces spurious unexplained.
8. **CDM cross-walk:**
   - **Type:** None directly. CDM `VolatilityType`, `VolatilitySpecification` exist as observation references but not as calibrated objects.
   - **Status:** **Missing.**
   - **Gap sketch:**
     ```rosetta
     type CalibratedVolSurface:
         [metadata key]
         underlier Observable (1..1)
             [metadata reference]
         valuationDate date (1..1)
         volModelId VolModelEnum (1..1)
         parameters VolSurfaceParameters (1..1)
         posteriorCovariance VolSurfaceCovariance (1..1)
         dupireConsistent boolean (1..1)
         butterflyArbitrageFree boolean (1..1)
         calendarArbitrageFree boolean (1..1)
         certifiedAt zonedDateTime (1..1)

     enum VolModelEnum:
         BLACK_SCHOLES
         SABR
         HESTON
         LOCAL_VOL
         KERNEL_VOL
     ```
   - **Severity:** Significant.

---

### 2.3 Calibrated FX Rate / FX Vol Surface

1. **Canonical name:** `CalibratedFXSurface`
2. **Definition:** Triangulation-consistent FX spot, forward, and vol-surface bundle.
3. **Minimum field set:** `currencyPair`, `spot`, `forwardCurve`, `atmVolPerExpiry`, `riskReversal`, `butterfly`, `triangulationKey` (set of pairs).
4. **Identity:** (`currencyPair`, `valuationDate`).
5. **Provenance:** Kalman filter, joint across cross-currency pairs to enforce triangulation.
6. **Temporal semantics:** Append-only.
7. **Failure consequences:** Triangulation break in stored FX produces FX swap PnL leak that is detected only by external reconciliation (v10.3 §8.4 dual-valuation framework would surface the model–market gap).
8. **CDM cross-walk:**
   - **Type:** `ForeignExchangeRate` exists for spot reference; calibrated surfaces are not modelled.
   - **Status:** **Missing** for the calibrated artefact.
   - **Severity:** Significant.

---

### 2.4 Credit Hazard Curve

1. **Canonical name:** `CalibratedCreditHazardCurve`
2. **Definition:** Hazard-rate term structure per reference entity, calibrated from CDS quotes.
3. **Minimum field set:** `referenceEntityLEI`, `seniority`, `restructuringClause`, `valuationDate`, `hazardRatesByTenor`, `recoveryRate`, `posteriorCovariance`.
4. **Identity:** (`referenceEntityLEI`, `seniority`, `restructuringClause`, `valuationDate`).
5. **Provenance:** Kalman filter from CDS/iTraxx quotes.
6. **Temporal semantics:** Append-only.
7. **Failure consequences:** Mis-calibrated hazard → wrong CDS PnL, wrong CVA, wrong default expectation. Corrupts every CSA exposure under collateral (v10.3 §6.4 CSA margin contract).
8. **CDM cross-walk:**
   - **Type:** `CreditCurveValuation` / related types exist for observation references; calibrated form is missing.
   - **Status:** **Missing** for the calibrated artefact.
   - **Severity:** Moderate (most ledgers price CDS via vendor curves).

---

### 2.5 Greeks / Sensitivity Jacobian Snapshot

1. **Canonical name:** `SensitivityJacobian`
2. **Definition:** The full parameter Jacobian (Valuation v1.0 §3.4) attached to a `ValuationRecord`. The dimension equals the model parameter count.
3. **Minimum field set:** `unitId`, `valuationTimestamp`, `modelId`, `observableSensitivities` (delta, gamma, theta, rho), `parameterJacobian` (Vector<(ParameterName, Sensitivity)>), `crossSensitivities` (vanna, volga, charm), `bucketVegas` (for local-vol / kernel-vol).
4. **Identity:** (`unitId`, `valuationTimestamp`, `modelId`).
5. **Provenance:** Pricing workflow's Greek-computation activity (Valuation v1.0 §3.7).
6. **Temporal semantics:** One row per pricing cycle. Cached for the duration of FSM `EXPLAINED`. Invalidated on material lifecycle event (Valuation v1.0 §13.3).
7. **Failure consequences:** Stale Jacobian → wrong Taylor approximation → APPROXIMATE prices that should not be trusted → official PnL contamination if FIRM-only rule (Valuation Principle 11.2) is bypassed. Wrong model attribution mixes Jacobians across models → spurious PnL-explain residual (Remark on model-consistency, §10.1).
8. **CDM cross-walk:**
   - **Type:** None. CDM tracks `Valuation` as an observation but does not model the structure of Greeks or the sensitivity Jacobian.
   - **Status:** **Missing.**
   - **Severity:** Moderate. This is appropriately a Valuation-layer concern, but a `cdm-valuation-lib` extension would benefit from an industry-standard Greek schema.

---

# Floor 3 — Raw Market Observations (the other half of v0's "Market")

These are the inputs to calibration, not its outputs. They are oracle-attested raw quotes — see Floor 4 for the Oracle treatment of how they enter the system. The reason this is its own row class is that the Kalman-filter discipline (Valuation §6.5 innovation gating) operates on raw observations, not on calibrated outputs. They live in their own immutable journal.

---

### 3.1 Raw Quote Observation

1. **Canonical name:** `RawQuoteObservation`
2. **Definition:** A single price/rate/quantity observation arriving from a market data oracle, with full metadata for innovation gating and replay.
3. **Minimum field set:** `instrumentId`, `quoteType` (BID/ASK/MID/TRADE/SETTLE/OFFICIAL_CLOSE), `value`, `quantity`, `currency`, `quoteTimestamp` (vendor-stamped), `arrivalTimestamp` (ledger-stamped), `sourceVenue` (MIC), `sourceVendor`, `bidAskSpread`, `staleness`.
4. **Identity:** (`instrumentId`, `sourceVendor`, `quoteTimestamp`, `quoteType`).
5. **Provenance:** Vendor data feed (Bloomberg B-Pipe, Refinitiv Elektron, vendor-direct exchange feed, IBOR fixings).
6. **Temporal semantics:** Append-only journal. Two timestamps: economic (`quoteTimestamp`) and booking (`arrivalTimestamp`) — same dual-stamp pattern as v10.3 §10.4 fault-tolerance for late events.
7. **Failure consequences:** Bad quote (fat-finger trade printed at $0.001) → if it slips past the Mahalanobis-distance gate (Valuation §6.5), it corrupts the Kalman posterior. The gate is the structural defence; without it, P9 (PnL path-independence) still holds but the value integral is meaningless.
8. **CDM cross-walk:**
   - **Type:** `Observation` and `MarketObservation` exist (in `cdm-event-lib`) but are scoped to lifecycle observations (e.g., reset rate observed at fixing time), not to a generic market-data ingest journal.
   - **Status:** **Partial.** CDM's `Price` type covers the value-and-currency content; `ObservationIdentifier` covers identity; the *streaming* ingest journal as a first-class concept is Ledger-native.
   - **Gap sketch:** Most of `RawQuoteObservation` can be modelled as `MarketObservation` extended with vendor and arrival metadata.

---

### 3.2 Reset Observation

1. **Canonical name:** `ResetObservation`
2. **Definition:** The fixing of a floating-rate index (SOFR, ESTR, TONA, EURIBOR, LIBOR-replacement) on a specific calendar date used to set a rate on an IRS, FRN, or related contract.
3. **Minimum field set:** `index`, `fixingDate`, `tenor`, `fixingValue`, `fixingSource` (e.g., NY Fed for SOFR; ECB for ESTR), `fallback` (RFR-fallback waterfall reference).
4. **Identity:** (`index`, `tenor`, `fixingDate`).
5. **Provenance:** Index administrator publication.
6. **Temporal semantics:** Append-only. Restated fixings (very rare) are dual-version: the original is preserved, the corrected entry references it via `corrects` metadata.
7. **Failure consequences:** Missing reset blocks the IRS reset event (v10.3 §5.6 Step 2) — the lifecycle workflow stalls. Wrong reset produces incorrect coupon → cash settlement break with counterparty.
8. **CDM cross-walk:**
   - **Type:** `Reset` (in `cdm-event-lib`) — a first-class CDM type.
   - **Status:** **Direct.** Exact match.
   - **Excerpt** (CDM 6.0.0):
     ```rosetta
     type Reset:
         resetValue Price (1..1)
         resetDate date (1..1)
         rateRecordDate date (0..1)
         calculationPeriod CalculationPeriod (0..1)
         observations ObservationEvent (0..*)
     ```
   - **Gap:** None.

---

# Floor 4 — Oracle / External Authoritative Claims

Re-scoped per §0. These are the messages, attestations, and confirmations crossing the ledger boundary. CDM coverage is uneven: ISO 20022 settlement messages are well-mapped via synonyms; FpML confirmations are well-mapped (and `rune-fpml` repository is dedicated to this); custodian/CSD attestations are partially modelled; Kalman certifications are not modelled at all.

---

### 4.1 FpML Trade Confirmation (inbound)

1. **Canonical name:** `FpMLConfirmation`
2. **Definition:** Inbound FpML 5.x trade confirmation from a trade-acceptance counterparty or affirmation platform (MarkitWire, DTCC GTR, OSTTRA).
3. **Minimum field set:** Full FpML message envelope + structured trade body. Must yield `Trade.tradeIdentifier`, `Trade.tradeDate`, `TradableProduct.tradeLot`, `Counterparty[1..2]`, `Trade.executionDetails`, `Trade.contractDetails`, `Trade.collateral` (if present in the message), and the underlying `NonTransferableProduct` via the synonym mapping.
4. **Identity:** FpML `messageId` + originating party's BIC.
5. **Provenance:** Counterparty (or affirmation platform on behalf of counterparties).
6. **Temporal semantics:** Append-only on the inbound channel. Cancel/replace messages reference originals via FpML `correlationId`.
7. **Failure consequences:** A confirmation that fails to map (synonym missing) blocks the unit registration. P3 (referential integrity) holds because the unit is rejected, but the trade is not in the ledger — operational risk only.
8. **CDM cross-walk:**
   - **Type:** Driven by `rune-fpml` repository — the synonym layer that maps FpML → CDM.
   - **Path:** `rosetta-models/rune-fpml/src/main/rosetta/` — synonym definitions per product type, e.g., `[synonym FpML_5_10 value "swap"]`.
   - **Status:** **Direct** for vanilla IRS, FX, equity options, credit defaults. **Partial / patchy** for exotic structured products, novations, compressions, structured notes.
   - **Verification status:** Confirmed against `rune-fpml` repository structure; specific synonym path coverage for less common products should be re-checked per-product.
   - **Gap:** Per-product, where missing.

---

### 4.2 ISO 20022 Settlement Message (outbound + inbound)

1. **Canonical name:** `ISO20022Message`
2. **Definition:** Bidirectional ISO 20022 settlement message bundle: outbound `sese.023` (securities settlement instruction), `pacs.008` / `pacs.009` (cash payment); inbound `sese.025` (settlement confirmation), `camt.054` (cash credit/debit notification).
3. **Minimum field set:** Header (`MsgId`, `EndToEndId`, `CreDtTm`, `InstgPty`, `InstdPty`), securities/cash leg fields per message type, settlement date, counterparty BIC, custodian/CSD participant ID.
4. **Identity:** (`MsgId`, sender BIC).
5. **Provenance:** Outbound: produced by the settlement projection (v10.3 §11.1). Inbound: from custodians, CSDs, payment systems via SWIFT.
6. **Temporal semantics:** Append-only on both directions. Status lifecycle (v10.3 §11.7) tracks `EXECUTED → INSTRUCTED → SETTLED / FAILED`.
7. **Failure consequences:** Outbound message lost → settlement does not occur → `INSTRUCTED` state never advances → obligation-liveness alert (v10.3 §14.7) fires after deadline. Mismatched return confirmation → custodian-break boundary failure (detectable via virtual-wallet comparison).
8. **CDM cross-walk:**
   - **Type:** Synonym-mapped via CDM-to-ISO 20022 mapping layer (v10.3 §10.3, §11.6 mapping table).
   - **Path:** Synonym definitions in `cdm-product-lib` and related libraries; ISO 20022 mapping layer in CDM 6.0.0 is partial but growing.
   - **Status:** **Direct** for `sese.023` securities settlement → `Trade` + `Transfer` mapping. **Partial** for the corporate-action message families (`seev.*`).
   - **Gap:** Corporate-action message families are not fully synonym-mapped.

---

### 4.3 Custodian / CSD Attestation

1. **Canonical name:** `CustodianAttestation`
2. **Definition:** Authoritative external claim about positions, balances, or events from a custodian, CSD, or sub-custodian (DTC, Euroclear, Clearstream, Cedel, JASDEC, KSD).
3. **Minimum field set:** `custodianBIC`, `accountId`, `asOfDate`, `position` (Vector<(ISIN, Quantity)>), `cashBalance` per currency, `corporateActionDetails`, `pendingSettlement`.
4. **Identity:** (`custodianBIC`, `accountId`, `asOfDate`).
5. **Provenance:** Custodian SWIFT MT535/MT536 / ISO 20022 `semt.002` / proprietary extract.
6. **Temporal semantics:** Append-only daily snapshots. Used for boundary reconciliation against virtual-wallet balances (v10.3 §2.5, §8.3).
7. **Failure consequences:** Mismatch between custodian attestation and virtual-wallet balance → custodian break (v10.3 §8.3 reconciliation taxonomy). Cannot be eliminated; must be detected and resolved.
8. **CDM cross-walk:**
   - **Type:** None in CDM 6.0.0 directly. The closest is `Account` + `Statement` types in some peripheral libraries, but they are not authoritative.
   - **Status:** **Missing.** The custodian-statement object is Ledger-native; its mapping to CDM is via `Account`, `Party`, and `Position` references.
   - **Severity:** Moderate. Reconciliation pipelines do not require a CDM-native custodian-statement type, but it would improve cross-firm comparability.

---

### 4.4 Regulatory Acknowledgement (DRR / SFTR / EMIR / SLATE)

1. **Canonical name:** `RegulatoryAcknowledgement`
2. **Definition:** Inbound acknowledgement from a Trade Repository or regulatory submission gateway: ACK / NACK / pending-validation, with field-level error detail.
3. **Minimum field set:** `submittingFirmLEI`, `tradeRepositoryId`, `regime` (EMIR / SFTR / SLATE / CFTC P43 / MAS), `submissionId`, `referenceId` (UTI), `status`, `errorDetails`.
4. **Identity:** (`submissionId`, `tradeRepositoryId`).
5. **Provenance:** TRs (DTCC GTR, REGIS-TR, UnaVista, KDPW), regulatory APIs.
6. **Temporal semantics:** Append-only. Often dual-stamped (submission timestamp + ack timestamp).
7. **Failure consequences:** NACK creates an obligation to resubmit (v10.3 §14.7 regulatory-obligation row). Repeated NACK → regulatory penalty.
8. **CDM cross-walk:**
   - **Type:** ISDA DRR (Digital Regulatory Reporting) is the relevant CDM artefact. DRR generates the *outbound* report; the inbound ack is not modelled in CDM.
   - **Path:** ISDA DRR repositories sit alongside `common-domain-model` in the FINOS organisation.
   - **Status:** **Partial.** Outbound report = direct (DRR-generated). Inbound acknowledgement object = missing.
   - **Severity:** Moderate.

---

# Floor 5 — Smart-Contract & Lifecycle Execution

Renamed per §0. Covers contract program objects, emitted moves, unit-state objects, lifecycle `BusinessEvent` payloads, executor decisions, and Temporal workflow state.

---

### 5.1 Move (the core ledger primitive)

1. **Canonical name:** `Move`
2. **Definition:** v10.3 Definition 2.3. The atomic ledger modification — single-coordinate, one-unit, two-entity transfer.
3. **Minimum field set:** `from` (WalletId), `to` (WalletId), `unit` (UnitId), `quantity` (positive Decimal), `coordinate` (under GPM: own | onloan | borr | coll_post | coll_recv | coll_rehyp), `timestamp`, `source` (contract reference), `metadata` (event description, external references, `corrects` link if compensating).
4. **Identity:** Inherits from the enclosing transaction (`tx_id` + ordinal within transaction).
5. **Provenance:** Smart-contract emission, validated and committed by the Executor.
6. **Temporal semantics:** Immutable, append-only — invariant P4 (log monotonicity). Corrections are new moves, never mutations.
7. **Failure consequences:** Wrong `quantity` direction violates conservation P1 (caught by executor). Wrong `unit` violates referential integrity P3 (caught by executor). Missing `source` defeats traceability and P9 (path-independence) audit.
8. **CDM cross-walk:**
   - **Type:** Closest is `Transfer` (in `cdm-event-lib`). The Ledger `Move` is a *single-coordinate slice* of `Transfer`.
   - **Status:** **Partial / Direct depending on interpretation.** A non-SBL move maps directly. An SBL move (writing `onloan` or `coll_post`) does not because CDM has no first-class concept of a six-coordinate position vector.
   - **Gap:** SBL coordinate semantics (the GPM in v10.3 §17). Per v10.3 §17.18, *"Recall, Locate, Rehypothecation"* are explicit CDM gaps.
   - **Gap sketch:** Already developed in v10.3 §17.18; this Phase 1 inherits that.

---

### 5.2 Transaction

1. **Canonical name:** `LedgerTransaction`
2. **Definition:** v10.3 Definition 2.4. Atomic finite collection of moves sharing a timestamp, satisfying conservation per unit, classified by `TransactionType`.
3. **Minimum field set:** `txId`, `type` (SETTLEMENT | COLLATERAL | LIFECYCLE | ACCOUNTING | CORRECTION — v10.3 §11.3), `timestamp` (economic), `bookingTimestamp`, `moves` (List<Move>), `cdmPayload` (the originating `BusinessEvent`), `corrects` (link to original tx if CORRECTION), `unitStateDeltas`.
4. **Identity:** `txId` (UUID, deterministic from the originating CDM event).
5. **Provenance:** Smart contract → Executor commit.
6. **Temporal semantics:** Immutable on commit. Idempotent by `txId` — invariant P5.
7. **Failure consequences:** Conservation P1 failure → executor rejects → no commit. Idempotency P5 failure → double-spend / duplicate-coupon.
8. **CDM cross-walk:**
   - **Type:** Composite — corresponds to a `WorkflowStep` containing a `BusinessEvent` whose primitive instructions decompose into `Transfer` and state-change records.
   - **Status:** **Partial.** CDM's `WorkflowStep` carries the CDM-native form of the same concept; the Ledger's transaction is the closure of that workflow step plus the executor's commit metadata.
   - **Gap:** The `txType` enumeration above (SETTLEMENT / COLLATERAL / LIFECYCLE / ACCOUNTING / CORRECTION) is Ledger-native — CDM does not classify business events on this axis.

---

### 5.3 BusinessEvent / PrimitiveInstruction Payload

1. **Canonical name:** `CDMBusinessEventPayload`
2. **Definition:** The full CDM `BusinessEvent` carried alongside the ledger transaction (v10.3 §10.4 forgetful-functor design — the ledger extracts moves; the full CDM record is preserved in the transaction's log payload).
3. **Minimum field set:** `instruction` (`PrimitiveInstruction (1..*)` — choice over `ContractFormation`, `Quantity Change`, `TermsChange`, `Reset`, `Transfer`, `Exercise`, `Observation`, `IndexTransition`, `Split`), `after` (`TradeState (1..*)`), `eventDate`, `effectiveDate`, `intent` (`EventIntentEnum`).
4. **Identity:** Deterministic hash of the event — `[metadata key]` annotation on `BusinessEvent`.
5. **Provenance:** Generated by the smart contract or ingested from upstream system.
6. **Temporal semantics:** Immutable, log-resident, replayable.
7. **Failure consequences:** Missing `BusinessEvent` payload destroys the audit-explanation layer (v10.3 §1.2 Time-Travel property cannot reconstruct *what the position meant*, only what the balances were).
8. **CDM cross-walk:**
   - **Type:** `BusinessEvent`. Path: `cdm-event-lib/src/main/rosetta/event/workflow/`.
   - **Status:** **Direct.**
   - **Gap:** None at the type level. Per v10.3 §17.18, the `Recall`, `Locate`, and `Rehypothecation` SBL events have no CDM `PrimitiveInstruction` branch.
   - **Gap sketch (SBL):**
     ```rosetta
     type SBLRecallInstruction:
         loanReference Trade (1..1)
             [metadata reference]
         recallQuantity Quantity (1..1)
         recallDate date (1..1)
         returnByDate date (1..1)

     -- Add to PrimitiveInstruction choice:
     -- recall SBLRecallInstruction (0..1)
     ```

---

### 5.4 Unit State (`ProductTerms` / `UnitStatus` / `PositionState`)

1. **Canonical name:** `UnitStateMaps` (the StatesHome three-map schema)
2. **Definition:** Per StatesHome addendum §2:
   - `ProductTerms : Map[UnitId, NonEmptyList[TermsVersion]]` — immutable, append-only, versioned, registration-total.
   - `UnitStatus : Map[UnitId, UnitStatus]` — mutable, shared across holders, registration-total.
   - `PositionState : Map[(WalletId, UnitId), PositionState]` — monotone carrier, Option accessor, per-(holder, unit).
3. **Minimum field set:** Per StatesHome §2.1 worked table — too long to enumerate exhaustively here; key fields by map:
   - `ProductTerms`: multiplier, currency, expiry, CCP, strike, ISIN, fee schedule, mandate text, benchmark identity, index methodology, fungibility predicate (C8).
   - `UnitStatus`: `lifecycle_stage`, `last_settlement_price`, `last_settlement_date`, `current_weights`, `nav_index`, `triggered_barrier`, `superseded_by`.
   - `PositionState`: `accumulated_cost`, `ccp_binding`, per-position OTC lifecycle, `entry_nav`, `hwm`, `accrued_{mgmt,perf}_fee`, `benchmark_nav_at_inception`, `mandate_breach_flags`.
4. **Identity:** As keyed.
5. **Provenance:** Set at unit registration; mutated only by canonical handlers per C11.
6. **Temporal semantics:** Per StatesHome C1–C12. Twelve conditions, summarised in addendum §2.4.
7. **Failure consequences:** Per StatesHome §6, seven of ten core invariants (P1, P3, P5, P6, P7, P9, P10) become structurally unreachable when C1–C12 hold. Violations of C2 (handler-level conservation) → P1 violation. C8 amendment-track violation → P7 violation.
8. **CDM cross-walk:**
   - **Type:** CDM `TradeState` is the rough analogue but is structured per-`Trade`, not as the three-map split.
   - **Status:** **Partial.** CDM and StatesHome model the same conceptual territory but factor it differently. The StatesHome split is more general; CDM `TradeState` is a flat record per trade.
   - **Risk per StatesHome F6:** *"CDM alignment (`TradeState` per `Trade` vs `PositionState[w, u]`) is asserted, not verified."* Re-running the Rosetta NS1–7 mapping against the three-map schema is an outstanding verification step.

---

### 5.5 SBL Loan Unit (Securities Lending Loan)

1. **Canonical name:** `SBLLoanUnit`
2. **Definition:** A unit representing a single SBL loan with bond-like fee accrual semantics (v10.3 §17.7).
3. **Minimum field set:** `loanId`, `lender`, `borrower`, `agent`, `isin`, `quantity`, `originalQty`, `termType` (OPEN/TERM), `maturityDate`, `feeRate`, `rebateRate`, `collateralType` (CASH/NON_CASH), `marginPct`, `haircutPct`, `collateralCcy`, `tripartyAgent`, `legalRegime` (TITLE_TRANSFER / SECURITY_INTEREST / US_15C3_3), `rehypConsent`, `lifecycleStage`, `settlementStatus`, `recallDate`, `recallQty`, `sftrUti`, `slateLoanId`, `executionTs`, `tradeDate`, `lastMarkDate`, `accruedFee`, `feeAccrualLog`.
4. **Identity:** `loanId` (UTI under SFTR; `slateLoanId` under SLATE).
5. **Provenance:** SBL trading platform / direct bilateral negotiation / agent lender.
6. **Temporal semantics:** Per `SBLState` machine (v10.3 §17.7): `PENDING → ACTIVE → {RECALLED, PARTIALLY_RETURNED, RETURNED, CANCELLED, DEFAULTED}`.
7. **Failure consequences:** Wrong `legalRegime` produces incorrect rehypothecation logic → P12 / P15 invariant violation. Wrong `feeRate` produces fee mis-accrual → cash settlement break.
8. **CDM cross-walk:**
   - **Type:** `SecurityLendingPayout`-related types in CDM are partial. Per v10.3 §17.18 mapping table, three explicit gaps exist: **Recall, Locate, Rehypothecation have no CDM equivalent**.
   - **Path:** `cdm-product-lib/src/main/rosetta/product/asset/` — Security types; agreement types in `cdm-legalagreement-lib`; collateral types in `cdm-collateral-lib`.
   - **Status:** **Partial.** Loan economics are present; the named lifecycle gaps are open issues (FINOS CDM SBL working group).
   - **Severity:** Significant — these are blocking for SFTR / SLATE complete coverage.

---

### 5.6 Obligation (Liveness Object)

1. **Canonical name:** `Obligation`
2. **Definition:** v10.3 §14.7 first-class obligation object: a deadline-bounded duty whose discharge or compensation is enforced by the Temporal scheduler.
3. **Minimum field set:** `id`, `type` (per Table 14.1: bond-coupon, option-expiry, IRS-reset, futures-VM, SBL-recall, SBL-manuf-div, CSA-VM, CSA-IM, close-out, SFTR-report, SLATE-report, EMIR-report, settlement-instruction), `source` (unit | agreement | regulatory event), `deadline` (`t_d`), `dischargePredicate` (`D`), `compensation` (`κ`).
4. **Identity:** Deterministic hash of source event + obligation type.
5. **Provenance:** Created by the registering smart contract or by an event-trigger handler.
6. **Temporal semantics:** Lifecycle `Pending → Attempted → {Discharged, Compensated, Defaulted}`. Terminal states absorbing.
7. **Failure consequences:** P21–P23 (obligation-liveness invariants per v10.3 §14.7.4) violated if obligation forgotten / deadline missed without compensation. CSA close-out, SFTR penalty, settlement fail.
8. **CDM cross-walk:**
   - **Type:** None directly in CDM. Closest concept is `WorkflowStep.lineage` carrying obligation references, but the obligation as a typed first-class object is not present.
   - **Status:** **Missing.** Genuinely Ledger-native.
   - **Severity:** Moderate. CDM may benefit from absorbing this concept; obligation tracking is implicit in much of the event model already.

---

### 5.7 Lifecycle Workflow State (Temporal)

1. **Canonical name:** `TemporalWorkflowState`
2. **Definition:** Per-unit, per-agreement, or per-portfolio durable workflow state (PricingWorkflow per Valuation §7.1, lifecycle workflow per v10.3 §14.5, settlement saga per §14.6).
3. **Minimum field set:** `workflowId`, `runId`, `taskQueue`, `localState`, `pendingSignals`, `pendingTimers`, `historySize`, `continueAsNewCounter`.
4. **Identity:** (`workflowId`, `runId`).
5. **Provenance:** Temporal cluster.
6. **Temporal semantics:** Continuously updated; `ContinueAsNew` resets every N cycles to bound history (Valuation §15.3).
7. **Failure consequences:** Workflow loss via Temporal cluster failure → recoverable from event history. Workflow-versioning inconsistencies → deterministic-replay failure (v10.3 §14.10).
8. **CDM cross-walk:**
   - **Type:** None. This is execution-engine state, not domain data.
   - **Status:** **Missing** (correctly so — outside CDM scope).

---

# Floor 6 — Listed-Instrument Detail (DEMOTED)

Per §0, this is folded back into Floor 1. No items listed here. The `ExchangeContractSpec` row (1.3) and the listed-equity row (1.2) cover the entire content of the original "Listed-instrument detail" floor.

---

# Floor 7 — Legal & Agreement (NEW)

Argued in §0. CDM has a dedicated `cdm-legalagreement-lib` and `cdm-collateral-lib`. v10.3 §6.4, §10.6, §17.5 attach to these. Folding them into Static loses the version semantics, governing-law axis, and netting-set perimeter.

---

### 7.1 ISDA Master Agreement Reference

1. **Canonical name:** `ISDAMasterAgreement`
2. **Definition:** The bilateral ISDA Master Agreement (1992 or 2002) governing OTC derivatives between two counterparties.
3. **Minimum field set:** `agreementType` (`ISDA_2002_MASTER` | `ISDA_1992_MASTER`), `parties[2]` (LEIs), `executedDate`, `governingLaw` (`NEW_YORK` | `ENGLISH`), `terminationCurrency`, `nettingProvisions`, `crossDefaultThreshold`, `automaticEarlyTermination` flags, `splitNotionalProvisions`, `additionalTerminationEvents`.
4. **Identity:** (`partyA LEI`, `partyB LEI`, `agreementType`, `executedDate`).
5. **Provenance:** Negotiated and executed bilaterally; stored in the Legal Agreement library.
6. **Temporal semantics:** Append-only versioning. Amendments produce new `LegalAgreementVersion` records.
7. **Failure consequences:** Wrong `governingLaw` → wrong close-out methodology → CSA dispute. Wrong `nettingProvisions` → over- or under-stated regulatory exposure (CRR, EMIR).
8. **CDM cross-walk:**
   - **Type:** `LegalAgreement` with `agreementType LegalAgreementTypeEnum`. Path: `cdm-legalagreement-lib/src/main/rosetta/legalagreement/`.
   - **Status:** **Direct.**
   - **Gap:** None at the schema level.

---

### 7.2 Credit Support Annex (CSA) Elections

1. **Canonical name:** `CSAElections`
2. **Definition:** Bilateral CSA elections — threshold, MTA, eligible collateral, interest rate, governing law — that govern variation margin and (post-UMR) initial margin between two counterparties.
3. **Minimum field set:** `csaType` (`CSA_2016_VM` | `CSA_2018_PHASE5_IM` | `EU_2014_CSA` | `JPA_CSA`), `governingLaw` (`NEW_YORK` | `ENGLISH` | `JAPANESE`), `threshold` per party, `minimumTransferAmount` per party, `eligibleCollateral` per party (asset class, currency, haircut schedule), `interestRate` per cash currency, `valuationAgent`, `disputeResolution`, `notificationTimes`.
4. **Identity:** (`partyA LEI`, `partyB LEI`, `csaType`, `executedDate`).
5. **Provenance:** Bilateral negotiation. Stored in Legal Agreement library and referenced by every `Trade.collateral.creditSupportAgreementElections`.
6. **Temporal semantics:** Append-only versioning. Most CSAs amended at quarterly review.
7. **Failure consequences:** Wrong `eligibleCollateral` → ineligible collateral posted → counterparty rejection → margin shortfall → dispute. Wrong `interestRate` → wrong overnight cash collateral rebate → settlement break. Wrong CSA attached at `Trade.collateral` → unit identity wrong (v10.3 App B §6 dual-CSA test): two trades that should be different units appear as one.
8. **CDM cross-walk:**
   - **Type:** `CreditSupportAgreementElections` (within `CollateralProvisions`). Path: `cdm-legalagreement-lib/src/main/rosetta/legalagreement/csa/`.
   - **Status:** **Direct.**
   - **Excerpt** (from memory; verify):
     ```rosetta
     type CreditSupportAgreementElections:
         threshold ThresholdElections (0..*)
         minimumTransferAmount MinimumTransferAmountElections (0..*)
         eligibleCollateral EligibleCollateralSchedule (0..*)
         interestRate InterestRateElection (0..*)
         governingLaw GoverningLawEnum (1..1)
     ```
   - **Gap:** None.

---

### 7.3 GMSLA / MSLA Master Agreement (SBL)

1. **Canonical name:** `GMSLAAgreement`
2. **Definition:** Global Master Securities Lending Agreement (2000, 2010, 2018) governing securities lending, or US MSLA equivalent.
3. **Minimum field set:** `agreementType` (`GMSLA_2000` | `GMSLA_2010` | `GMSLA_2018_PLEDGE` | `MSLA`), `governingLaw`, `parties[2]`, `defaultEvents`, `closeOutMethodology`, `manufacturedPaymentObligations`, `taxIndemnification`, `rehypothecationConsent` (per GMSLA Schedule).
4. **Identity:** (`partyA LEI`, `partyB LEI`, `agreementType`, `executedDate`).
5. **Provenance:** Bilateral; ISLA / SIFMA model agreements as templates.
6. **Temporal semantics:** Append-only versioning.
7. **Failure consequences:** Wrong `agreementType` → wrong title/security-interest treatment of collateral (v10.3 §17.10) → coordinate-coordinate misclassification (own vs coll_recv) → P12 violation. Wrong `closeOutMethodology` → wrong default-handling.
8. **CDM cross-walk:**
   - **Type:** `MasterAgreementType.SECURITY_LENDING` exists; full GMSLA election schema is partial.
   - **Status:** **Partial.** ISLA's CDM working group has been actively extending CDM SBL coverage; this is in flux. Verification required.
   - **Gap:** GMSLA-specific election bundle (Schedule A elections) is not modelled at the depth that CSA elections are.

---

### 7.4 Trade-Level Collateral Provisions

1. **Canonical name:** `TradeCollateralProvisions`
2. **Definition:** v10.3 line ~107 / App B §6: the `Trade.collateral` field on a CDM Trade, of type `Collateral`, which references the governing CSA and specifies trade-level collateral terms.
3. **Minimum field set:** `collateralType` (`CASH_COLLATERAL` | `SECURITY_INTEREST` | `TITLE_TRANSFER`), `marginApproach`, `creditSupportAgreementElections` (link to §7.2), `eligibleCollateralSchedule` (potentially trade-overriding).
4. **Identity:** Embedded in `Trade.collateral`.
5. **Provenance:** Set at trade execution; references the master CSA.
6. **Temporal semantics:** Trade-immutable except via amendment (CDM `TermsChangeEvent`).
7. **Failure consequences:** Per the v10.3 dual-CSA test (App B §6): two otherwise-identical trades with different `Trade.collateral.creditSupportAgreementElections` are *different units*. If the ledger collapses them, P3 (referential integrity) fails at the unit-identity layer.
8. **CDM cross-walk:**
   - **Type:** `Collateral` with `collateralType`, `eligibleCollateral`, `creditSupportAgreementElections`, `marginApproach`. Path: `cdm-collateral-lib/src/main/rosetta/collateral/`.
   - **Status:** **Direct** for OTC bilateral. **Partial** for CCP-cleared (per v10.3 App B §6: *"CDM v6.0.0 does not have a dedicated type for 'CCP margin rules' as distinct from 'bilateral collateral provisions'"*).
   - **Gap sketch (CCP margin):**
     ```rosetta
     type CCPMarginProvisions extends Collateral:
         clearingHouse Party (1..1)
             [metadata reference]
         marginMethodology CCPMarginMethodEnum (1..1)
         haircutScheduleRef ExternalRulebookReference (1..1)

     enum CCPMarginMethodEnum:
         OCC_STANS
         JSCC_SPAN
         CME_SPAN_2
         LCH_PAIRS
     ```

---

### 7.5 Confirmation / Definitions Booklet Reference

1. **Canonical name:** `ConfirmationDefinitions`
2. **Definition:** The trade Confirmation document (long-form or short-form) under the master agreement, plus the ISDA Definitions booklet versions referenced (2006 ISDA Definitions, 2021 ISDA Interest Rate Definitions, 2003 ISDA Credit Definitions, 2002 ISDA Equity Definitions).
3. **Minimum field set:** `confirmationDate`, `definitionsBookletVersion`, `additionalTerms`, `electionsOverride`, `legalDocumentReference`.
4. **Identity:** Trade-specific; embedded in `Trade.contractDetails`.
5. **Provenance:** Confirmation platform (MarkitWire, ICELink) or manual confirmation exchange.
6. **Temporal semantics:** Append-only versioning per amendment.
7. **Failure consequences:** Wrong `definitionsBookletVersion` → wrong fallback waterfall (e.g., LIBOR fallback under 2021 ISDA Definitions) → wrong reset values post-cessation event.
8. **CDM cross-walk:**
   - **Type:** `ContractualDefinitions` enum, `ContractDetails` carrying confirmation references. Path: `cdm-product-lib/src/main/rosetta/product/template/ContractDetails.rosetta`.
   - **Status:** **Direct.**
   - **Gap:** None at the type level.

---

# Floor 8 — Identity, Provenance & Audit (NEW)

Argued in §0. The metadata schema is load-bearing for v10.3 §1.2 Property 6 (Time Travel), §8 (Substantiation), §9 (CDM mapping), §11 (Settlement). Without an explicit floor, this disappears into transaction metadata fields without governance.

---

### 8.1 UTI / USI (Unique Trade Identifier)

1. **Canonical name:** `UniqueTransactionIdentifier`
2. **Definition:** The unique identifier per traded contract per regulatory regime. UTI under EMIR / SFTR; USI under CFTC P43/P45.
3. **Minimum field set:** `utiPrefix` (LEI of generating party per the ESMA waterfall), `utiSuffix`, `regime`, `generatingParty`.
4. **Identity:** `(utiPrefix, utiSuffix)`.
5. **Provenance:** Generated by the trade-execution platform per the regulatory waterfall (CCP > confirmation platform > seller > etc.).
6. **Temporal semantics:** Immutable for the life of the trade; preserved across amendments and corrections.
7. **Failure consequences:** Wrong UTI → SFTR/EMIR pairing failure with counterparty → regulatory rejection → SFTR/EMIR penalty. v10.3 §17.18 SBL row obliges per-loan UTI generation.
8. **CDM cross-walk:**
   - **Type:** `TradeIdentifier` with `assignedIdentifier AssignedIdentifier (1..1)` and `identifierType TradeIdentifierTypeEnum`. Path: `cdm-product-lib/src/main/rosetta/product/template/TradeIdentifier.rosetta`.
   - **Status:** **Direct.**
   - **Gap:** None.

---

### 8.2 LEI (Legal Entity Identifier)

1. **Canonical name:** `LegalEntityIdentifier`
2. **Definition:** ISO 17442 20-character alphanumeric identifier for a legal entity, registered with GLEIF / Local Operating Units.
3. **Minimum field set:** `lei` (20 chars), `entityName`, `entityCategory` (FUND / SUB_FUND / CORPORATE / ETC), `registrationStatus`, `registrationAuthority`, `registrationDate`.
4. **Identity:** `lei`.
5. **Provenance:** GLEIF.
6. **Temporal semantics:** Mostly immutable. Status (`ACTIVE` / `LAPSED` / `RETIRED`) updates via GLEIF feed.
7. **Failure consequences:** Lapsed LEI → regulatory reporting rejection (EMIR / SFTR). Wrong LEI → mis-attributed trade.
8. **CDM cross-walk:**
   - **Type:** `Party.partyId` with `partyIdScheme = "LEI"`. Path: `cdm-base-lib/src/main/rosetta/base/staticdata/party/`.
   - **Status:** **Direct.**
   - **Gap:** None.

---

### 8.3 Move / Transaction Provenance Chain

1. **Canonical name:** `ProvenanceMetadata`
2. **Definition:** The full provenance and lineage trail attached to every move and every transaction: source contract reference, originating CDM event, external message identifiers (FpML messageId, ISO 20022 EndToEndId, SFTR submission id), and correction-link metadata (`corrects` field referencing original tx for compensating transactions).
3. **Minimum field set:** `txId`, `sourceContractRef`, `originatingCDMEventHash`, `fpmlMessageId` (if any), `iso20022EndToEndId` (if any), `sftrSubmissionId` (if any), `slateLoanId` (if any), `correctsTxId` (if compensating), `bookingTimestamp`, `economicTimestamp`.
4. **Identity:** Embedded in `Transaction.metadata`.
5. **Provenance:** Set at each layer of the pipeline: smart contract sets `sourceContractRef`; mapping layer sets `originatingCDMEventHash`; ingest sets external references; correction handler sets `correctsTxId`.
6. **Temporal semantics:** Immutable per transaction.
7. **Failure consequences:** Missing `sourceContractRef` defeats traceability and audit. Missing `correctsTxId` breaks the formal correction algebra (v10.3 §10.4). Missing `originatingCDMEventHash` breaks the CDM-to-Ledger reverse mapping required for DRR consistency.
8. **CDM cross-walk:**
   - **Type:** `MetaFields`, `Lineage`, `WorkflowStep.lineage` (in `cdm-base-lib`). Path: `cdm-base-lib/src/main/rosetta/base/metafields/`.
   - **Status:** **Partial.** CDM `Lineage` covers CDM-internal references but not the cross-system identifier bundle (FpML, ISO 20022, SFTR, SLATE).
   - **Gap sketch:**
     ```rosetta
     type ExternalReferenceBundle:
         fpmlMessageId string (0..1)
         iso20022EndToEndId string (0..1)
         sftrSubmissionId string (0..1)
         slateLoanId string (0..1)
         drrSubmissionId string (0..1)
     ```

---

### 8.4 Hash-Chained Audit Log Entry

1. **Canonical name:** `AuditLogEntry`
2. **Definition:** Per v10.3 invariant P4: each entry in the move stream includes the hash of the previous entry, providing tamper-evidence.
3. **Minimum field set:** `entryIndex`, `entryHash`, `previousEntryHash`, `txId` reference, `commitTimestamp`.
4. **Identity:** `entryIndex`.
5. **Provenance:** Generated by the Executor at commit time.
6. **Temporal semantics:** Strict append-only by `entryIndex`.
7. **Failure consequences:** Hash mismatch on replay → tamper detection → log integrity invariant violation → ledger rejection of subsequent commits until human resolution.
8. **CDM cross-walk:**
   - **Type:** None. This is infrastructure metadata.
   - **Status:** **Missing** (correctly so — outside CDM scope).

---

### 8.5 Time Tuple (Economic + Booking + Knowledge)

1. **Canonical name:** `TimeTuple`
2. **Definition:** Three timestamps per material event: economic time (when the event happened in the world), booking time (when the ledger learned about it), knowledge time (when the calibration / market data observation was certified).
3. **Minimum field set:** `economicTime`, `bookingTime`, `knowledgeTime` (Valuation v1.0 §6.1 — calibration epoch).
4. **Identity:** Per transaction / per `ValuationRecord`.
5. **Provenance:** Set at ingest, set at commit, set at calibration certification.
6. **Temporal semantics:** All three are immutable once set. v10.3 §10.4 *"events arriving after their economic timestamp are recorded with both an economic timestamp and a booking timestamp."*
7. **Failure consequences:** Conflating economic with booking time → wrong financial-statement reporting at period-end (P9 path-independence theorem still holds but the reporting convention is wrong). Conflating with knowledge time → time-travel reconstructs ledger state with the wrong market-data snapshot.
8. **CDM cross-walk:**
   - **Type:** CDM `BusinessEvent.eventDate` and `effectiveDate` cover two of the three. The knowledge-time concept is Valuation-stack-specific.
   - **Status:** **Partial.**

---

# Cross-Floor Summary Table

| # | Item | Floor | CDM Status | Severity if Gap |
|---|---|---|---|---|
| 1.1 | CurrencyUnit | Static | Direct | – |
| 1.2 | ListedEquity | Static | Partial | Significant |
| 1.3 | ExchangeContractSpec | Static | Partial | Significant |
| 1.4 | BondTerms | Static | Partial | Significant |
| 1.5 | OTCProductTemplate | Static | Direct | – |
| 1.6 | BusinessCenters | Static | Direct | – |
| 1.7 | DayCountFractionEnum | Static | Direct | – |
| 2.1 | CalibratedYieldCurve | Calibrated | Missing | Significant |
| 2.2 | CalibratedVolSurface | Calibrated | Missing | Significant |
| 2.3 | CalibratedFXSurface | Calibrated | Missing | Significant |
| 2.4 | CalibratedCreditHazardCurve | Calibrated | Missing | Moderate |
| 2.5 | SensitivityJacobian | Calibrated | Missing | Moderate |
| 3.1 | RawQuoteObservation | Market raw | Partial | Moderate |
| 3.2 | ResetObservation | Market raw | Direct | – |
| 4.1 | FpMLConfirmation | Oracle | Direct (per-product) | Moderate |
| 4.2 | ISO20022Message | Oracle | Direct (settlement) / Partial (corp action) | Moderate |
| 4.3 | CustodianAttestation | Oracle | Missing | Moderate |
| 4.4 | RegulatoryAcknowledgement | Oracle | Partial | Moderate |
| 5.1 | Move | Execution | Partial (SBL coords) | Significant |
| 5.2 | LedgerTransaction | Execution | Partial | Moderate |
| 5.3 | CDMBusinessEventPayload | Execution | Direct (except SBL) | Significant |
| 5.4 | UnitStateMaps | Execution | Partial (alignment unverified — F6) | Moderate |
| 5.5 | SBLLoanUnit | Execution | Partial (3 known gaps) | Significant |
| 5.6 | Obligation | Execution | Missing | Moderate |
| 5.7 | TemporalWorkflowState | Execution | Missing (correctly out of scope) | – |
| 7.1 | ISDAMasterAgreement | Legal | Direct | – |
| 7.2 | CSAElections | Legal | Direct | – |
| 7.3 | GMSLAAgreement | Legal | Partial | Significant |
| 7.4 | TradeCollateralProvisions | Legal | Direct (OTC) / Partial (CCP) | Moderate |
| 7.5 | ConfirmationDefinitions | Legal | Direct | – |
| 8.1 | UTI | Identity | Direct | – |
| 8.2 | LEI | Identity | Direct | – |
| 8.3 | ProvenanceMetadata | Identity | Partial | Significant |
| 8.4 | AuditLogEntry | Identity | Missing (out of scope) | – |
| 8.5 | TimeTuple | Identity | Partial | Moderate |

**Total items:** 32 (across 7 active floors; floor 6 demoted; new floors 7 and 8 added).
**CDM gaps total:** 17 (Missing: 8; Partial: 9; including out-of-scope items 5.7 and 8.4 not counted as gaps).
**Significant-severity gaps:** 9.
**Listed-instrument detail items:** all subsumed into Static floor.

---

# Verification and Disclosure

Throughout this enumeration I cite CDM types from CDM 6.0.0 from internal knowledge of the schema. **I have not re-fetched every cited file from `rosetta-models/common-domain-model` in this Phase 1 cycle.** Two specific items where I called this out explicitly: §1.2 `Security.rosetta` field set; §7.2 `CreditSupportAgreementElections` excerpt. Before any of these gap sketches becomes a Rosetta extension PR, the live `.rosetta` file must be re-read against the published CDM 6.0.0 release.

Per StatesHome F6 risk: **the alignment between CDM `TradeState` and the StatesHome three-map schema (`ProductTerms`, `UnitStatus`, `PositionState`) is asserted, not verified.** This is an outstanding Phase 2 / Phase 3 item, not resolvable inside Phase 1 enumeration alone.

For Phase 2 I will surface two convergence questions to the Data Team:

1. The Calibrated-Market floor (Floor 2) is *entirely* CDM-missing. Whether to propose a `cdm-valuation-lib` extension upstream to FINOS, or whether to live with a Ledger-native parallel schema, is a strategic question that touches firm-level CDM contribution policy.
2. The SBL gaps (Recall, Locate, Rehypothecation) are tracked by ISLA's CDM working group. Phase 2 should align with whatever the ISLA group's current proposal is, not duplicate it.

---

*End of independent Phase 1 enumeration. — Matthias Vogt*
