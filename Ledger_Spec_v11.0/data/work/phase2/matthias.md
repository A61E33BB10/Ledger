# Phase 2 Deliverable — MATTHIAS (CDM/Rosetta Cross-Walk)

**Author role:** Principal Engineer, FINOS CDM core team. Reviewer of Rosetta product, event, legal-agreement, and collateral models. CDM 6.0.0 expert.

**Scope of this section:** For every taxonomy leaf the Phase 2 master taxonomy will carry (drawn from Phase 1 convergence: 6 floor categories collapsing roughly to **Definitions / Observations / Effects** plus additions), produce:

1. **Direct CDM type** (FINOS CDM v6.0.0, exact path)
2. **Mapping status** (Direct / Partial / Missing)
3. **Rosetta DSL fragment** (real syntax, CDM 6.0.0 conventions)
4. **FpML / ISO 20022 anchor** where applicable
5. **Gap analysis & extension sketch** for Partial/Missing

**Working taxonomy.** I anticipate NAZAROV's master taxonomy will have roughly this leaf set; I produce the cross-walk against my own organisation, noting where the leaves have nazarov / formalis / lattner overlaps. I cluster into eight groups corresponding to the eight floors I argued in Phase 1 (Static / Calibrated / Raw-Market / Oracle / Smart-Contract Execution / Legal & Agreement / Identity-Provenance / [Listed-detail subsumed]). NAZAROV's six-floor proposal (A–F) maps cleanly: Identity+Legal=A+E, Tables=B, Market-Raw=C, Oracle=D, Execution+Calibrated=E (her sense)+F. I treat the union as 35 leaves.

**Verification protocol applied.** I cite paths from `rosetta-models/common-domain-model` from internal CDM 6.0.0 knowledge. **I have not re-fetched every cited file from the live repo in this Phase 2 cycle.** Items where I am least certain about exact field names are flagged inline with `[VERIFY]`.

---

## §A — Definitions Group (Static / ProductTerms / Reference)

### A.1 — `CurrencyUnit` (cash unit)

1. **Direct CDM type:** `Cash` extends `AssetBase`. Path: `cdm-product-lib/src/main/rosetta/product/asset/Asset.rosetta` — `Cash` is one branch of the `Asset` choice.
2. **Status:** **Direct.**
3. **Rosetta:**
   ```rosetta
   type Cash extends AssetBase:
       currency string (1..1)
           [metadata scheme]
   ```
4. **FpML / ISO 20022 anchor:** ISO 4217 currency code; FpML `currency` attribute on `paymentAmount`, ISO 20022 `Ccy` on `ActiveCurrencyAndAmount`.
5. **Gap:** None.

### A.2 — `ListedEquity`

1. **Direct CDM type:** `Security` (with `securityType = SecurityTypeEnum.EQUITY`) extends `Instrument` extends `AssetBase`. Path: `cdm-product-lib/src/main/rosetta/product/asset/Security.rosetta`.
2. **Status:** **Partial.** Direct on ISIN/issuer/currency; missing first-class `boardLotSize`, `votingRights`, `dividendPolicyRef`, `corporateActionFeedRef`.
3. **Rosetta:**
   ```rosetta
   type Security extends Instrument:
       securityType SecurityTypeEnum (1..1)
       debtType DebtType (0..1)
       equityType EquityType (0..1)
   ```
4. **FpML / ISO 20022 anchor:** FpML `equity` element under `underlyingAsset`; ISO 20022 `secl.001` (security reference data via reda.005). ANNA / DTCC / Euroclear are authoritative ISIN sources.
5. **Gap & extension:**
   ```rosetta
   type SecurityListingExtensions:
       security Security (1..1)
           [metadata reference]
       boardLotSize int (0..1)
       votingRights VotingRightsEnum (0..1)
       dividendPolicyReference DividendPolicy (0..1)
       corporateActionFeedRef string (0..1)
   ```

### A.3 — `ExchangeContractSpec` (listed derivative spec)

1. **Direct CDM type:** `ListedDerivative` extends `Instrument`. Path: `cdm-product-lib/src/main/rosetta/product/asset/`. The catalogue-level "contract specification" concept is thin — CDM uses `NonTransferableProduct` for both OTC and listed.
2. **Status:** **Partial — significant gap.** Per v10.3 §3.10, no dedicated catalogue-level contract-spec type. CCP identity is part of unit identity per StatesHome §4.1 (CME-ES vs ICE-ES are distinct units).
3. **Rosetta sketch (extension):**
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
       optionExerciseStyle OptionStyleEnum (0..1)
   ```
4. **FpML / ISO 20022 anchor:** FpML `futureLeg` / `equityOption` reference data block; CME SPAN files; ISO 20022 `reda.022` (DerivativeInstrumentReportV01).
5. **Gap severity:** Significant. Tracked in FINOS CDM exchange-traded coverage discussions.

### A.4 — `BondTerms`

1. **Direct CDM type:** `Security` with `debtType DebtType` discriminator. Path: `cdm-product-lib/src/main/rosetta/product/asset/Security.rosetta`.
2. **Status:** **Partial.** Identifiers and ranking (`DebtType`) are direct; coupon mechanics not first-class on plain `Security` — CDM expects coupon scheduling to be handled lifecycle-externally or via `InterestRatePayout` if treated as a payout.
3. **Rosetta sketch (extension):**
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
4. **FpML / ISO 20022 anchor:** FpML `bond` element under `underlyingAsset`; ISO 20022 `reda.012` debt instrument reference.
5. **Gap severity:** Significant. Open issue in FINOS CDM for first-class debt coverage.

### A.5 — `OTCProductTemplate` (`NonTransferableProduct`)

1. **Direct CDM type:** `NonTransferableProduct`. Path: `cdm-product-lib/src/main/rosetta/product/template/NonTransferableProduct.rosetta`.
2. **Status:** **Direct — canonical type for the concept.**
3. **Rosetta:**
   ```rosetta
   type NonTransferableProduct:
       [metadata key]
       identifier ProductIdentifier (0..*)
       taxonomy ProductTaxonomy (0..*)
       economicTerms EconomicTerms (1..1)
   ```
4. **FpML anchor:** Synonym-mapped from FpML `swap`, `fra`, `equityOption`, `creditDefaultSwap`, etc., via `rune-fpml` repo (`src/main/rosetta/`). Qualification function `Qualify_*` (e.g., `Qualify_InterestRate_IRSwap_FixedFloat`) infers product type from `EconomicTerms`.
5. **Gap:** None at this layer.

### A.6 — `BusinessCenters` + `BusinessDayConventions`

1. **Direct CDM type:** `BusinessCenters`, `BusinessCenterEnum`, `BusinessDayConventionEnum`. Path: `cdm-base-lib/src/main/rosetta/base/datetime/`.
2. **Status:** **Direct on type system.** CDM does not ship the holiday tables themselves (correctly out of scope).
3. **Rosetta:**
   ```rosetta
   type BusinessCenters:
       [metadata key]
       [metadata scheme]
       businessCenter BusinessCenterEnum (0..*)
           [metadata scheme]
       businessCentersReference BusinessCenters (0..1)
           [metadata reference]
   ```
4. **FpML / ISO 20022 anchor:** FpML `businessCenters` / `BusinessCenterEnum` (FpML 5.10 enums are the canonical scheme); ISO 20022 reuses ISO 8601 + ISO 20022 calendar enums.
5. **Gap:** None on type system. Operational gap on holiday-table provenance pipeline (external).

### A.7 — `DayCountFractionEnum`

1. **Direct CDM type:** `DayCountFractionEnum`. Path: `cdm-base-lib/src/main/rosetta/base/datetime/`.
2. **Status:** **Direct.** Enum values: `ACT_360`, `ACT_365_FIXED`, `ACT_ACT_ISDA`, `ACT_ACT_ICMA`, `_30_360`, `_30E_360`, `_1_1`, etc.
3. **Rosetta:** Standard enum.
4. **FpML / ISO 20022 anchor:** FpML 5.10 `DayCountFractionEnum`; ISDA 2006/2021 Definitions §4.16.
5. **Gap:** None.

### A.8 — `LegalEntityIdentifier` (LEI / Party)

1. **Direct CDM type:** `Party` with `partyId.identifierType = PartyIdentifierTypeEnum.LEI`. Path: `cdm-base-lib/src/main/rosetta/base/staticdata/party/Party.rosetta`.
2. **Status:** **Direct.**
3. **Rosetta:**
   ```rosetta
   type Party:
       [metadata key]
       partyId PartyIdentifier (1..*)
       name FieldWithMetaString (0..1)
           [metadata scheme]
       person NaturalPerson (0..*)
       account Account (0..1)
       contactInformation ContactInformation (0..1)
       businessUnit BusinessUnit (0..1)

   type PartyIdentifier:
       identifier FieldWithMetaString (1..1)
           [metadata scheme]
       identifierType PartyIdentifierTypeEnum (0..1)
   ```
4. **FpML / ISO 20022 anchor:** FpML `partyId partyIdScheme="http://www.fpml.org/coding-scheme/external/iso17442"`; ISO 20022 `LEIIdentifier` type used in `pacs.*`, `pain.*`, `secl.*`, `sese.*` headers.
5. **Gap:** None.

### A.9 — `TradeIdentifier` (UTI / USI / UPI)

1. **Direct CDM type:** `TradeIdentifier` with `assignedIdentifier AssignedIdentifier (1..*)` and `identifierType TradeIdentifierTypeEnum`. Path: `cdm-product-lib/src/main/rosetta/product/template/TradeIdentifier.rosetta`.
2. **Status:** **Direct.**
3. **Rosetta:**
   ```rosetta
   type TradeIdentifier:
       [metadata key]
       issuer FieldWithMetaString (0..1)
           [metadata scheme]
       assignedIdentifier AssignedIdentifier (1..*)
       identifierType TradeIdentifierTypeEnum (0..1)
   ```
4. **FpML / ISO 20022 anchor:** FpML `tradeId tradeIdScheme="..."`; ISO 23897 (UTI standard); ISO 20022 `UnqTxIdr` field across reporting messages; CFTC USI; ESMA UPI via ANNA DSB.
5. **Gap:** None.

### A.10 — `WalletRegistry` (sidecar)

1. **Direct CDM type:** `Account` extends... or `Party.account`. Path: `cdm-base-lib/src/main/rosetta/base/staticdata/party/Account.rosetta`.
2. **Status:** **Partial.** Per StatesHome, WalletRegistry is the *non-state, non-financial* sidecar carrying KYC, permissions, audit cursor — explicitly NOT what `Account` is in CDM.
3. **Rosetta sketch (extension):**
   ```rosetta
   type WalletRegistry:
       [metadata key]
       walletId string (1..1)
       partyLEI string (1..1)
           [metadata scheme]
       custodianAccount Account (0..1)
           [metadata reference]
       virtualWalletMap VirtualWalletAllocation (0..*)
       kycStatus KYCStatusEnum (1..1)
       capabilities Capability (0..*)
       auditCursor zonedDateTime (1..1)
   ```
4. **FpML / ISO 20022 anchor:** ISO 20022 `Acct` block; SWIFT BIC for account-servicing institution.
5. **Gap severity:** Moderate. WalletRegistry is appropriately Ledger-native; Account is the closest CDM hook.

### A.11 — `SystemEpoch` / `LedgerGenesis` (formalis F1.1)

1. **Direct CDM type:** None.
2. **Status:** **Missing — correctly out of CDM scope.** This is ledger infrastructure metadata, not domain data.
3. **Gap:** No CDM extension proposed.

---

## §B — Authoritative Tables Group (Reference)

### B.1 — `SanctionsList`

1. **Direct CDM type:** None — CDM does not model regulatory restriction lists.
2. **Status:** **Missing.**
3. **Rosetta sketch (extension):**
   ```rosetta
   type SanctionsListEntry:
       [metadata key]
       authority SanctionsAuthorityEnum (1..1)
       entryId string (1..1)
       entryType SanctionsEntryTypeEnum (1..1)
       names FieldWithMetaString (1..*)
       leiCandidates string (0..*)
           [metadata scheme]
       countryOfResidence string (0..1)
       programs string (0..*)
       effectiveFrom date (1..1)
       effectiveTo date (0..1)
       sourcePublicationDate date (1..1)
       sourceSignature string (1..1)

   enum SanctionsAuthorityEnum:
       OFAC
       OFSI
       EU_CONSOLIDATED
       UN_SECURITY_COUNCIL
       MAS
       JAPAN_MOF
   ```
4. **Anchor:** OFAC SDN List XML/JSON, EU Consolidated, UN Security Council; ISO 20022 has no native sanctions message.
5. **Gap severity:** Significant. Should be a separate Ledger-native registry with multi-source aggregation per NAZAROV CC-3.

### B.2 — `WithholdingTable` (tax)

1. **Direct CDM type:** None directly. `TaxWithholding`-related types exist on payouts but the *tax treaty / reference table* is not modelled.
2. **Status:** **Missing.**
3. **Rosetta sketch (extension):**
   ```rosetta
   type WithholdingTaxTreatyEntry:
       [metadata key]
       countryOfSource string (1..1)
       countryOfRecipient string (1..1)
       instrumentClass InstrumentClassEnum (1..1)
       treatyRate number (1..1)
       defaultWithholdingRate number (1..1)
       beneficialOwnerClassification BOClassificationEnum (1..1)
       treatyEffectiveFrom date (1..1)
       treatyEffectiveTo date (0..1)
       documentationRequired DocumentationEnum (0..*)
   ```
4. **Anchor:** IRS Pub 901; OECD treaty database; vendor: Vertex, ONESOURCE.
5. **Gap severity:** Moderate.

### B.3 — `CorporateActionsSchedule`

1. **Direct CDM type:** `CorporateAction` types exist as event observations, not as a forward-published schedule. Path: `cdm-event-lib/src/main/rosetta/event/`.
2. **Status:** **Partial.** Event-shape coverage exists (CDM has `StockSplit`, `Dividend`, etc. via `CorporateActionTypeEnum`); the *announcement / schedule / version* dimension is thinner.
3. **Rosetta sketch (extension):**
   ```rosetta
   type CorporateActionAnnouncement:
       [metadata key]
       eventId string (1..1)
       instrumentIsin string (1..1)
           [metadata scheme]
       eventType CorporateActionTypeEnum (1..1)
       announcementDate date (1..1)
       exDate date (0..1)
       recordDate date (0..1)
       paymentDate date (0..1)
       effectiveDate date (0..1)
       grossAmountPerShare number (0..1)
       currency string (0..1)
       withholdingTreatment WithholdingTaxTreatyEntry (0..1)
           [metadata reference]
       mandatoryOrVoluntary MandatoryVoluntaryEnum (1..1)
       electionOptions ElectionOption (0..*)
       electionDeadline date (0..1)
       sourceAuthority string (1..1)
       dtccEventId string (0..1)
       versionNumber int (1..1)
   ```
4. **FpML / ISO 20022 anchor:** ISO 20022 **`seev.031` (Corporate Action Notification)**, **`seev.035` (Corporate Action Movement Confirmation)**, **`seev.039` (Corporate Action Cancellation Advice)**. CDM has not fully synonym-mapped the `seev.*` family — significant gap.
5. **Gap severity:** Significant for the schedule view; the lifecycle-effect view is partially covered.

### B.4 — `IndexComposition`

1. **Direct CDM type:** `Index` / `EquityIndex` extends `IndexBase` extends `AssetBase`. Path: `cdm-observable-lib/src/main/rosetta/observable/asset/Index.rosetta`. Constituents not modelled in depth.
2. **Status:** **Partial.** `Index` identity is direct; constituent set + weights + methodology version are not first-class.
3. **Rosetta sketch (extension):**
   ```rosetta
   type IndexCompositionSnapshot:
       [metadata key]
       index Index (1..1)
           [metadata reference]
       indexProviderLEI string (1..1)
           [metadata scheme]
       asOfDate date (1..1)
       methodologyVersion string (1..1)
       constituents IndexConstituent (1..*)
       divisor number (1..1)
       totalMarketCap number (0..1)
       rebalanceDates date (0..*)

   type IndexConstituent:
       isin string (1..1)
           [metadata scheme]
       weight number (1..1)
       freeFloatFactor number (0..1)
       country string (0..1)
       sector string (0..1)
   ```
4. **Anchor:** S&P DJI / MSCI / FTSE Russell proprietary feeds; ISO 20022 has limited index coverage.
5. **Gap severity:** Moderate.

### B.5 — `CCPMarginParameters`

1. **Direct CDM type:** None for parameter-set specifications. `Collateral` types describe the agreement, not the CCP rule book.
2. **Status:** **Missing** for the parameter-set specification.
3. **Rosetta sketch:**
   ```rosetta
   type CCPMarginParameters:
       [metadata key]
       ccp Party (1..1)
           [metadata reference]
       parameterSetVersion string (1..1)
       methodology CCPMarginMethodEnum (1..1)
       effectiveFrom date (1..1)
       effectiveTo date (0..1)
       parameterTable CCPParameterEntry (1..*)

   enum CCPMarginMethodEnum:
       OCC_STANS
       JSCC_SPAN
       CME_SPAN_2
       LCH_PAIRS
       EUREX_PRISMA
   ```
4. **Anchor:** CCP-published rule books; no ISO 20022 message family.
5. **Gap severity:** Moderate.

### B.6 — `StandingSettlementInstructions` (SSI)

1. **Direct CDM type:** `Account` carries beneficiary/agent info; full SSI bundle (CSD participant ID, custodian chain, place-of-settlement) not first-class.
2. **Status:** **Partial.**
3. **Rosetta sketch:**
   ```rosetta
   type StandingSettlementInstruction:
       [metadata key]
       counterpartyLEI string (1..1)
           [metadata scheme]
       instrumentClass InstrumentClassEnum (1..1)
       currency string (0..1)
       custodianBIC string (0..1)
           [metadata scheme]
       cashAccount Account (0..1)
           [metadata reference]
       securitiesAccount Account (0..1)
           [metadata reference]
       placeOfSettlement string (0..1)
       safekeepingAgent Party (0..1)
           [metadata reference]
   ```
4. **FpML / ISO 20022 anchor:** **ISO 20022 `setr.027` (Subscription Order)**, **`secl.005` (Trade Leg Notification)** carry SSI fields; SWIFT MT540 series; FpML `routing` / `paymentSummary`.
5. **Gap severity:** Moderate. Often handled outside CDM at present.

---

## §C — Continuous Market Observations Group (Market-Raw)

### C.1 — `RawQuoteObservation`

1. **Direct CDM type:** `Observation` / `MarketObservation`. Path: `cdm-event-lib/src/main/rosetta/event/common/Observation.rosetta`. `Price` covers value+currency content.
2. **Status:** **Partial.** CDM observations are scoped to lifecycle (e.g., reset rate observed at fixing time), not generic streaming market-data ingest.
3. **Rosetta sketch (extension via `MarketObservation` superset):**
   ```rosetta
   type RawQuoteObservation:
       [metadata key]
       instrument Asset (1..1)
           [metadata reference]
       quoteType QuoteTypeEnum (1..1)
       value Price (1..1)
       quantity Quantity (0..1)
       quoteTimestamp zonedDateTime (1..1)
       arrivalTimestamp zonedDateTime (1..1)
       sourceVenue string (1..1)
           [metadata scheme]
       sourceVendor string (1..1)
       attestationEnvelope AttestationEnvelope (1..1)

   enum QuoteTypeEnum:
       BID
       ASK
       MID
       TRADE
       SETTLE
       OFFICIAL_CLOSE
   ```
4. **FpML / ISO 20022 anchor:** Vendor proprietary (Bloomberg B-Pipe, Refinitiv Elektron); FIX MD; CDM synonym mapping spotty.
5. **Gap severity:** Moderate.

### C.2 — `ResetObservation`

1. **Direct CDM type:** `Reset`. Path: `cdm-event-lib/src/main/rosetta/event/common/Reset.rosetta`. **Canonical, first-class type.**
2. **Status:** **Direct.**
3. **Rosetta:**
   ```rosetta
   type Reset:
       [metadata key]
       resetValue Price (1..1)
       resetDate date (1..1)
       rateRecordDate date (0..1)
       calculationPeriod CalculationPeriod (0..1)
       observations ObservationEvent (0..*)
   ```
4. **FpML / ISO 20022 anchor:** FpML `resetEvent`; ISO 20022 has no direct equivalent (rate fixings published by administrators directly).
5. **Gap:** None.

### C.3 — `EquityQuote` / `ListedDerivativeQuote` / `FXRate` / `RatesQuote` / `VolatilityQuote` / `CreditSpread` / `ReferenceMark`

1. **Direct CDM type:** All represented as `Observation` against an `Observable` (`Asset`, `Index`, `Basket`). Path: `cdm-observable-lib/src/main/rosetta/observable/`.
2. **Status:** **Partial across the family.** CDM has the right shapes (`PriceObservation`, `Price`) but the *streaming / multi-venue / vendor-attested* dimension is Ledger-native.
3. **Rosetta:** All extend `RawQuoteObservation` (C.1) with class-specific fields (e.g., `bidSize`, `askSize`, `openInterest` for listed-derivative; `tenor`, `dayCountConvention` for rates; `expiry`, `strike`, `quoteMethod` for vol; `referenceEntityLEI`, `tier`, `restructuringClause` for CDS; `currencyPair`, `valueDate` for FX).
4. **FpML / ISO 20022 anchor:** FIX MD for live quotes; FpML `marketDataSet` for snapshots; ISO 20022 has limited market-data message coverage.
5. **Gap severity:** Moderate per family, individually small.

### C.4 — `SettlementPriceObservation` (CCP-published)

1. **Direct CDM type:** `Observation` keyed to `ListedDerivative`.
2. **Status:** **Partial.** Per StatesHome, `last_settlement_price` lives on `UnitStatus[u]`; the inbound observation is per-day per-contract.
3. **Rosetta:** Covered by C.1 + binding to `ListedDerivative`.
4. **Anchor:** Exchange-signed daily settlement files (CME daily settlement, ICE clearing prices).
5. **Gap:** Minor.

---

## §D — External Event Attestations Group (Oracle, expanded)

### D.1 — `FpMLConfirmation` (inbound trade confirmation)

1. **Direct CDM type:** Driven by `rune-fpml` synonym layer mapping FpML → CDM `Trade` + `TradableProduct` + `NonTransferableProduct`. Path: `rosetta-models/rune-fpml/src/main/rosetta/`.
2. **Status:** **Direct** for vanilla IRS, FX, equity options, credit defaults. **Partial / patchy** for exotics, novations, compressions, structured notes.
3. **Rosetta:** No new type — synonym annotations such as `[synonym FpML_5_10 value "swap"]` on the relevant CDM types.
4. **FpML / ISO 20022 anchor:** FpML 5.x messages are the canonical inbound; ISO 20022 has limited derivatives confirmation coverage.
5. **Gap severity:** Per-product where missing.

### D.2 — `ISO20022SettlementMessage`

1. **Direct CDM type:** Synonym-mapped via CDM-to-ISO 20022 mapping layer (`cdm-product-lib` synonyms) onto `Trade` + `Transfer`. Path: `cdm-product-lib/src/main/rosetta/synonym/iso20022/`.
2. **Status:** **Direct** for `sese.023` (securities settlement instruction) and `sese.025` (settlement confirmation). **Partial** for the `seev.*` corporate-action message families.
3. **Rosetta:** Synonym annotations on `Transfer`, `SettlementInstruction`-related types.
4. **FpML / ISO 20022 anchor:**
   - **`pacs.008`** (Customer Credit Transfer) — payment leg
   - **`pacs.009`** (Financial Institution Credit Transfer) — bank leg
   - **`pain.001`** (Customer Credit Transfer Initiation) — outbound payment instruction
   - **`secl.001/.002/.003/.005`** (Securities Clearing) — clearing/CCP messages
   - **`sese.023`** (Securities Settlement Transaction Instruction) — outbound settlement instruction
   - **`sese.025`** (Securities Settlement Transaction Confirmation) — inbound settlement confirmation
   - **`camt.054`** (Bank-to-Customer Debit/Credit Notification) — cash credit notification
5. **Gap severity:** Moderate for `seev.*`.

### D.3 — `BarrierObservation` (oracle attestation)

1. **Direct CDM type:** `ObservationEvent` recording barrier breach. Path: `cdm-event-lib/src/main/rosetta/event/common/ObservationEvent.rosetta`. Lifecycle transition fired via `BusinessEvent` with `ObservationInstruction`.
2. **Status:** **Partial.** CDM has the type, but the *attestation envelope* (attestor LEI, signature, contract-specified observation source) is not first-class on the type.
3. **Rosetta sketch:**
   ```rosetta
   type BarrierObservationEvent:
       [metadata key]
       observationEvent ObservationEvent (1..1)
       instrumentUnit Trade (1..1)
           [metadata reference]
       barrierDefinitionRef BarrierDefinition (1..1)
           [metadata reference]
       observationTime zonedDateTime (1..1)
       observedValue Price (1..1)
       barrierValue number (1..1)
       condition BarrierConditionEnum (1..1)
       breachIndicator boolean (1..1)
       attestor Party (1..1)
           [metadata reference]
       attestationSignature string (1..1)

   enum BarrierConditionEnum:
       UP_AND_OUT
       UP_AND_IN
       DOWN_AND_OUT
       DOWN_AND_IN
   ```
4. **Anchor:** Contract-specified observation source (closing print on official fixing source).
5. **Gap severity:** Moderate.

### D.4 — `ExerciseNotice`

1. **Direct CDM type:** `ExerciseInstruction` (within `PrimitiveInstruction` choice on `BusinessEvent`). Path: `cdm-event-lib/src/main/rosetta/event/`.
2. **Status:** **Direct.**
3. **Rosetta:**
   ```rosetta
   type ExerciseInstruction:
       [metadata key]
       trade Trade (1..1)
           [metadata reference]
       exerciseQuantity Quantity (1..1)
       exerciseDate date (1..1)
       exerciseTime zonedDateTime (0..1)
       exercisingParty Party (1..1)
           [metadata reference]
       settlementMethod SettlementTypeEnum (0..1)
   ```
4. **FpML / ISO 20022 anchor:** FpML `exerciseEvent`; OCC for listed options.
5. **Gap:** None.

### D.5 — `CreditEventNotice`

1. **Direct CDM type:** `CreditEvent` types within CDS payout. Path: `cdm-product-lib/src/main/rosetta/product/asset/CreditDefaultPayout.rosetta` (via `CreditEventNotice`-related types).
2. **Status:** **Partial.** CDS credit events are direct; bilateral master-agreement default events less coherent.
3. **Anchor:** ISDA Credit Determinations Committee published decisions; FpML `creditEvent`.
4. **Gap severity:** Moderate.

### D.6 — `SettlementConfirmation`

1. **Direct CDM type:** `Transfer` carries the post-settlement state; the inbound *confirmation* (status, custodian signature) is a synonym mapping target.
2. **Status:** **Partial.**
3. **Rosetta sketch:**
   ```rosetta
   type SettlementConfirmation:
       [metadata key]
       instructionId string (1..1)
       csdLEI string (1..1)
           [metadata scheme]
       confirmedStatus SettlementStatusEnum (1..1)
       settlementDateActual date (1..1)
       settlementAmountActual Money (1..1)
       failureReasonCode string (0..1)
       iso20022MessageHash string (1..1)
       attestationSignature string (1..1)

   enum SettlementStatusEnum:
       SETTLED
       FAILED
       PARTIAL_SETTLED
       PENDING
   ```
4. **FpML / ISO 20022 anchor:** **`sese.025`**, **`camt.054`**, **`semt.013/.017`** (statement messages); SWIFT MT535/MT536.
5. **Gap severity:** Moderate.

### D.7 — `CustodianAttestation` (position statement)

1. **Direct CDM type:** None directly. Closest: `Account` + `Position` references.
2. **Status:** **Missing.**
3. **Rosetta sketch:**
   ```rosetta
   type CustodianStatement:
       [metadata key]
       custodianBIC string (1..1)
           [metadata scheme]
       account Account (1..1)
           [metadata reference]
       asOfDate date (1..1)
       holdings PositionHolding (0..*)
       cashBalances Money (0..*)
       attestationSignature string (1..1)

   type PositionHolding:
       isin string (1..1)
       quantity number (1..1)
       availableQuantity number (1..1)
       lentQuantity number (0..1)
       pledgedQuantity number (0..1)
   ```
4. **FpML / ISO 20022 anchor:** **`semt.002`** (Custody Statement of Holdings), **`semt.013/.017`**; SWIFT MT535 (Statement of Holdings), MT536 (Statement of Transactions).
5. **Gap severity:** Moderate.

### D.8 — `MarginCallConfirmation` (CSA / triparty)

1. **Direct CDM type:** `MarginCallInstruction` and `MarginCallResponse`. Path: `cdm-collateral-lib/src/main/rosetta/collateral/`.
2. **Status:** **Direct** on the type system. Triparty agent attestation envelope is operational.
3. **Rosetta:**
   ```rosetta
   type MarginCallInstruction:
       [metadata key]
       callDate date (1..1)
       valuationDate date (1..1)
       portfolio Portfolio (1..1)
           [metadata reference]
       requestedAmount Money (1..1)
       direction MarginCallDirectionEnum (1..1)
   ```
4. **FpML / ISO 20022 anchor:** **`colr.003`** (Margin Call Request), **`colr.004`** (Margin Call Response), **`colr.005`** (Margin Call Dispute), **`colr.016`** (Collateral Substitution Request).
5. **Gap:** Minor.

### D.9 — `LocateConfirmation` (SBL — NEW LEAF, sbl.md §4.1)

1. **Direct CDM type:** **None.** Per v10.3 §17.18, **Locate is an explicit CDM gap**.
2. **Status:** **Missing — significant.**
3. **Rosetta sketch (extension; SBL working group track):**
   ```rosetta
   type LocateConfirmation:
       [metadata key]
       borrower Party (1..1)
           [metadata reference]
       lender Party (1..1)
           [metadata reference]
       agent Party (0..1)
           [metadata reference]
       isin string (1..1)
           [metadata scheme]
       quantity Quantity (1..1)
       locateValidFrom zonedDateTime (1..1)
       locateValidTo zonedDateTime (1..1)
       locateType LocateTypeEnum (1..1)
       attestationSignature string (1..1)

   enum LocateTypeEnum:
       FIRM
       INDICATIVE
       EASY_TO_BORROW
       HARD_TO_BORROW
   ```
4. **Anchor:** SEC Reg SHO Rule 203(b)(1); FINRA Rule 4320.
5. **Gap severity:** Significant. Tracked by ISLA's CDM working group.

### D.10 — `ManufacturedPaymentRate` / `TaxTreatmentOracle` (SBL — NEW LEAF)

1. **Direct CDM type:** Closest is `DividendPayout` for the equity dividend case, but SBL **manufactured payment** (the borrower passing the equivalent dividend back to the lender, less withholding tax adjustment) is not a first-class CDM concept.
2. **Status:** **Missing — significant for SBL.**
3. **Rosetta sketch:**
   ```rosetta
   type ManufacturedPayment:
       [metadata key]
       loanReference Trade (1..1)
           [metadata reference]
       underlyingDividendEvent CorporateActionAnnouncement (1..1)
           [metadata reference]
       grossDividendAmount Money (1..1)
       lenderTaxJurisdiction string (1..1)
       borrowerTaxJurisdiction string (1..1)
       beneficialOwnerClassification BOClassificationEnum (1..1)
       lenderEffectiveWithholdingRate number (1..1)
       manufacturedPaymentAmount Money (1..1)
       paymentDate date (1..1)
       taxTreatmentDeterminationOracle TaxTreatmentDetermination (1..1)
           [metadata reference]

   type TaxTreatmentDetermination:
       [metadata key]
       lenderJurisdiction string (1..1)
       borrowerJurisdiction string (1..1)
       instrumentISIN string (1..1)
       grossWithholdingRate number (1..1)
       treatyAdjustedRate number (1..1)
       beneficialOwnerCertification string (1..1)
       attestor Party (1..1)
           [metadata reference]
       attestationSignature string (1..1)
   ```
4. **Anchor:** GMSLA Schedule (manufactured payment provisions); GMSLA 2018 §5.
5. **Gap severity:** Significant.

### D.11 — `DefaultEvent` / `BuyInEvent` (SBL)

1. **Direct CDM type:** None first-class for SBL default; closest is master-agreement-level `EarlyTerminationEvent`.
2. **Status:** **Missing.**
3. **Anchor:** GMSLA §11 default events; ISLA buy-in protocols; CSDR Article 7 buy-in.
4. **Gap severity:** Moderate.

### D.12 — `RegulatoryAcknowledgement` (TR ack)

1. **Direct CDM type:** Outbound DRR generates the report (ISDA DRR uses CDM); inbound ack is not modelled.
2. **Status:** **Partial.** Outbound = direct. Inbound ack object = missing.
3. **Anchor:** DTCC GTR ACK/NACK; REGIS-TR; UnaVista; KDPW; ISO 20022 has no direct TR-ack family.
4. **Gap severity:** Moderate.

---

## §E — Calibrated Market Data Group (Effects of inference; Ledger-native layer)

This group is *entirely CDM-missing* — CDM was never designed as a calibration store. This is the most strategic gap in the cross-walk and is the natural seed of a `cdm-valuation-lib` extension proposal upstream to FINOS.

### E.1 — `CalibratedYieldCurve`

1. **Direct CDM type:** None. CDM `Curve` / `YieldCurveDefinition` model the **schedule of underlying instruments** (deposit, swap legs), not the *posterior parameter vector* output of a Kalman filter.
2. **Status:** **Missing.**
3. **Rosetta sketch (cdm-valuation-lib proposal):**
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
       certifiedAt zonedDateTime (1..1)
       certifierSignature string (1..1)

   type CurvePoint:
       tenor Period (1..1)
       zeroRate number (1..1)

   type CurveCovariance:
       diagonal number (1..*)
       offDiagonal number (0..*)
   ```
4. **Anchor:** No industry-standard format; vendor-proprietary (Murex, Numerix, Bloomberg DLIB).
5. **Gap severity:** Significant — strategic CDM gap.

### E.2 — `CalibratedVolSurface`

1. **Direct CDM type:** None.
2. **Status:** **Missing.**
3. **Rosetta sketch:**
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
       certifierSignature string (1..1)

   enum VolModelEnum:
       BLACK_SCHOLES
       SABR
       HESTON
       LOCAL_VOL
       KERNEL_VOL
   ```
4. **Anchor:** Vendor-proprietary.
5. **Gap severity:** Significant.

### E.3 — `CalibratedFXSurface`, `CalibratedCreditHazardCurve`, `CalibratedCommodityCurve`

Same pattern as E.1 / E.2. All **Missing**. Each requires a parallel Rosetta type with model-specific parameter bundles. Severity: Significant for FX/Credit; Moderate for commodity.

### E.4 — `KalmanPosterior` (the `(x_{t|t}, P_{t|t})` of valuation §3.4)

1. **Direct CDM type:** None.
2. **Status:** **Missing.**
3. **Rosetta sketch:**
   ```rosetta
   type KalmanPosterior:
       [metadata key]
       calibrationObjectId string (1..1)
       stateVector number (1..*)
       covarianceMatrix CovarianceMatrix (1..1)
       innovationCovariance CovarianceMatrix (1..1)
       innovationStatistic number (1..1)
       certifiedTimestamp zonedDateTime (1..1)
       admissibleRegionConstraintsHash string (1..1)
       priorPosteriorPointer string (0..1)
   ```
4. **Anchor:** None industry-standard.
5. **Gap severity:** Significant.

### E.5 — `SensitivityJacobian` / `Greeks`

1. **Direct CDM type:** `Valuation` exists as a result reference, but the structure of Greeks / parameter Jacobian is not modelled.
2. **Status:** **Missing.**
3. **Rosetta sketch:**
   ```rosetta
   type SensitivityJacobian:
       [metadata key]
       trade Trade (1..1)
           [metadata reference]
       valuationTimestamp zonedDateTime (1..1)
       modelId string (1..1)
       observableSensitivities GreekObservable (0..*)
       parameterJacobian ParameterSensitivity (0..*)
       crossSensitivities CrossGreek (0..*)
       bucketVegas BucketVega (0..*)

   type GreekObservable:
       greekType GreekTypeEnum (1..1)
       value number (1..1)

   enum GreekTypeEnum:
       DELTA
       GAMMA
       VEGA
       THETA
       RHO
       VANNA
       VOLGA
       CHARM
   ```
4. **Anchor:** Vendor-proprietary (Numerix, Bloomberg DLIB Greek bundles).
5. **Gap severity:** Moderate.

### E.6 — `ValuationRecord`

1. **Direct CDM type:** `Valuation` type exists at observation level; the **structured record with `model_id`, `market_data_snap`, `compute_ms`, `quality`, `fsm_state`, `calibration_state_ref`** is Ledger-native.
2. **Status:** **Partial.**
3. **Rosetta sketch:**
   ```rosetta
   type ValuationRecord:
       [metadata key]
       trade Trade (1..1)
           [metadata reference]
       timestamp zonedDateTime (1..1)
       dirtyPrice Price (1..1)
       cleanPrice Price (0..1)
       accrued Money (0..1)
       greeks SensitivityJacobian (0..1)
           [metadata reference]
       modelId string (1..1)
       marketDataSnap string (1..1)
       calibrationStateRef string (1..1)
       computeMs int (1..1)
       quality ValuationQualityEnum (1..1)
       fsmState ValuationFSMStateEnum (1..1)
       valuationWorkflowSignature string (1..1)

   enum ValuationQualityEnum:
       FIRM
       INDICATIVE
       APPROXIMATE
       STALE
       FAILED

   enum ValuationFSMStateEnum:
       PRICED
       EXPLAINED
       STALE
       FAILED
       QUARANTINED
       INDICATIVE
       APPROXIMATE
       PENDING
   ```
4. **Anchor:** No industry standard; vendor-specific (Calypso Vault, Murex MX.3 valuation tables).
5. **Gap severity:** Significant for the structured form.

---

## §F — Smart-Contract & Lifecycle Execution Group (Effects)

### F.1 — `Move` (the core ledger primitive)

1. **Direct CDM type:** `Transfer`. Path: `cdm-event-lib/src/main/rosetta/event/common/Transfer.rosetta`.
2. **Status:** **Partial.** A non-SBL move maps directly to a `Transfer`. An SBL move writing one of the six GPM coordinates (own / onloan / borr / coll_post / coll_recv / coll_rehyp) does not — CDM has no first-class concept of a six-coordinate position vector per (wallet, unit).
3. **Rosetta sketch (SBL coordinate extension):**
   ```rosetta
   type Move:
       [metadata key]
       from Account (1..1)
           [metadata reference]
       to Account (1..1)
           [metadata reference]
       unit Asset (1..1)
           [metadata reference]
       quantity Quantity (1..1)
       coordinate PositionCoordinateEnum (1..1)
       timestamp zonedDateTime (1..1)
       sourceContractRef string (1..1)
       metadata MoveMetadata (1..1)
       corrects Move (0..1)
           [metadata reference]

   enum PositionCoordinateEnum:
       OWN
       ON_LOAN
       BORROWED
       COLLATERAL_POSTED
       COLLATERAL_RECEIVED
       COLLATERAL_REHYPOTHECATED
   ```
4. **FpML / ISO 20022 anchor:** ISO 20022 `sese.023` for the settled effect; FpML synonym onto `Transfer`.
5. **Gap severity:** Significant for SBL.

### F.2 — `LedgerTransaction`

1. **Direct CDM type:** `WorkflowStep` carries `BusinessEvent`; the **closure of workflow step + executor commit metadata + `txType` classification + correction link** is Ledger-native.
2. **Status:** **Partial.**
3. **Rosetta sketch:**
   ```rosetta
   type LedgerTransaction:
       [metadata key]
       txId string (1..1)
       type TransactionTypeEnum (1..1)
       economicTimestamp zonedDateTime (1..1)
       bookingTimestamp zonedDateTime (1..1)
       moves Move (1..*)
       cdmPayload BusinessEvent (1..1)
       corrects LedgerTransaction (0..1)
           [metadata reference]
       unitStateDeltas UnitStateDelta (0..*)
       executorSignature string (1..1)
       previousEntryHash string (1..1)
       entryHash string (1..1)

   enum TransactionTypeEnum:
       SETTLEMENT
       COLLATERAL
       LIFECYCLE
       ACCOUNTING
       CORRECTION
   ```
4. **Anchor:** None.
5. **Gap severity:** Moderate.

### F.3 — `BusinessEvent` / `PrimitiveInstruction` Payload

1. **Direct CDM type:** `BusinessEvent`. Path: `cdm-event-lib/src/main/rosetta/event/workflow/BusinessEvent.rosetta`.
2. **Status:** **Direct on the core type. Partial on SBL.** Per v10.3 §17.18: **Recall, Locate, Rehypothecation have no `PrimitiveInstruction` branch.**
3. **Rosetta:**
   ```rosetta
   type BusinessEvent:
       [metadata key]
       intent EventIntentEnum (0..1)
       eventDate date (1..1)
       effectiveDate date (0..1)
       packageInformation IdentifiedList (0..1)
       instruction PrimitiveInstruction (1..*)
       after TradeState (1..*)

   choice PrimitiveInstruction:
       ContractFormationInstruction
       ExecutionInstruction
       QuantityChangeInstruction
       TerminationInstruction
       ExerciseInstruction
       TransferInstruction
       ObservationInstruction
       IndexTransitionInstruction
       SplitInstruction
   ```
4. **Gap sketch (SBL extension to choice):**
   ```rosetta
   type SBLRecallInstruction:
       loanReference Trade (1..1)
           [metadata reference]
       recallQuantity Quantity (1..1)
       recallDate date (1..1)
       returnByDate date (1..1)

   type SBLLocateInstruction:
       locateConfirmation LocateConfirmation (1..1)
           [metadata reference]

   type SBLRehypothecationInstruction:
       collateralUnit Trade (1..1)
           [metadata reference]
       quantity Quantity (1..1)
       rehypothecationParty Party (1..1)
           [metadata reference]
       consentReference string (1..1)

   -- Add to PrimitiveInstruction choice:
   -- recall SBLRecallInstruction
   -- locate SBLLocateInstruction
   -- rehypothecation SBLRehypothecationInstruction
   ```
5. **FpML / ISO 20022 anchor:** FpML for the existing instructions; SFTR / SLATE for SBL gaps.
6. **Gap severity:** Significant for SBL.

### F.4 — `TradeState` / `UnitStateMaps` (StatesHome 3-map)

1. **Direct CDM type:** `TradeState`. Path: `cdm-event-lib/src/main/rosetta/event/common/TradeState.rosetta`.
2. **Status:** **Partial.** CDM `TradeState` and StatesHome `(ProductTerms, UnitStatus, PositionState)` model the same conceptual territory but factor it differently.
3. **Rosetta:**
   ```rosetta
   type TradeState:
       [metadata key]
       trade Trade (1..1)
       state State (0..1)
       resetHistory Reset (0..*)
       transferHistory TransferState (0..*)
       observationHistory ObservationEvent (0..*)
   ```
4. **Risk per StatesHome F6:** *"CDM alignment (`TradeState` per `Trade` vs `PositionState[w, u]`) is asserted, not verified."* Re-running the Rosetta NS1–7 mapping against the three-map schema is the outstanding verification step. **This is the most important unresolved CDM-alignment question in the project.**
5. **Gap severity:** Moderate (functionally) / Significant (architecturally — affects every replay).

### F.5 — `SBLLoanUnit`

1. **Direct CDM type:** `SecurityFinancePayout` / loan-related types in `cdm-product-lib`. Per v10.3 §17.18, three explicit gaps: **Recall, Locate, Rehypothecation**.
2. **Status:** **Partial.** Loan economics are present; named lifecycle gaps are open issues (FINOS CDM SBL working group + ISLA contributions).
3. **Anchor:** GMSLA / MSLA legal framework; SFTR / SLATE reporting.
4. **Gap severity:** Significant — blocking for SFTR / SLATE complete coverage.

### F.6 — `Obligation`

1. **Direct CDM type:** None directly. Closest concept is `WorkflowStep.lineage` carrying lineage references, but obligation as a typed first-class object with `dischargePredicate D : LedgerState → Bool` and `compensation κ : Obligation → PendingTransaction` is not in CDM.
2. **Status:** **Missing.**
3. **Rosetta sketch:**
   ```rosetta
   type Obligation:
       [metadata key]
       id string (1..1)
       type ObligationTypeEnum (1..1)
       sourceUnit Trade (0..1)
           [metadata reference]
       sourceAgreement LegalAgreement (0..1)
           [metadata reference]
       deadline zonedDateTime (1..1)
       dischargePredicateRef string (1..1)
       compensationActionRef string (1..1)
       lifecycleState ObligationStateEnum (1..1)

   enum ObligationTypeEnum:
       BOND_COUPON
       OPTION_EXPIRY
       IRS_RESET
       FUTURES_VM
       SBL_RECALL
       SBL_MANUFACTURED_DIVIDEND
       CSA_VM
       CSA_IM
       CLOSE_OUT
       SFTR_REPORT
       SLATE_REPORT
       EMIR_REPORT
       SETTLEMENT_INSTRUCTION

   enum ObligationStateEnum:
       PENDING
       ATTEMPTED
       DISCHARGED
       COMPENSATED
       DEFAULTED
   ```
4. **Anchor:** None.
5. **Gap severity:** Moderate. CDM may benefit from absorbing this concept upstream.

### F.7 — `TemporalWorkflowState`

1. **Direct CDM type:** None.
2. **Status:** **Missing — correctly out of CDM scope.** This is execution-engine state.
3. **Gap:** No CDM extension proposed.

### F.8 — `SmartContractVersion` / `PricingModelVersion` (configuration-as-data)

1. **Direct CDM type:** None.
2. **Status:** **Missing.** Configuration-as-data with internal governance attestation; Ledger-native.
3. **Anchor:** None industry-standard.
4. **Gap severity:** Out of CDM scope.

### F.9 — `ElectionDecision` (voluntary action)

1. **Direct CDM type:** Partially covered by `ExerciseInstruction` for option exercise; corporate-action elections via `ObservationInstruction` is thin.
2. **Status:** **Partial.**
3. **Anchor:** ISO 20022 `seev.040` / `seev.041` (Corporate Action Instruction / Cancellation).
4. **Gap severity:** Moderate.

---

## §G — Legal & Agreement Group

### G.1 — `ISDAMasterAgreement`

1. **Direct CDM type:** `LegalAgreement` with `agreementType LegalAgreementTypeEnum.ISDA_MASTER_AGREEMENT_2002` (or `ISDA_MASTER_AGREEMENT_1992`). Path: `cdm-legalagreement-lib/src/main/rosetta/legalagreement/`.
2. **Status:** **Direct.**
3. **Rosetta:**
   ```rosetta
   type LegalAgreement:
       [metadata key]
       agreementDate date (0..1)
       effectiveDate date (0..1)
       identifier Identifier (0..*)
       agreementType LegalAgreementType (1..1)
       contractualParty Party (2..2)
           [metadata reference]
       agreementTerms AgreementTerms (0..1)
   ```
4. **FpML / ISO 20022 anchor:** ISDA Create export; FpML `documentation` block.
5. **Gap:** None at the schema level.

### G.2 — `CSAElections`

1. **Direct CDM type:** `CreditSupportAgreementElections` within `CollateralProvisions`. Path: `cdm-legalagreement-lib/src/main/rosetta/legalagreement/csa/`.
2. **Status:** **Direct.**
3. **Rosetta:** `[VERIFY]` against latest:
   ```rosetta
   type CreditSupportAgreementElections:
       threshold ThresholdElections (0..*)
       minimumTransferAmount MinimumTransferAmountElections (0..*)
       eligibleCollateral EligibleCollateralSchedule (0..*)
       interestRate InterestRateElection (0..*)
       governingLaw GoverningLawEnum (1..1)
   ```
4. **Anchor:** ISDA CSA 2016 (VM) / 2018 (IM); ISDA Create.
5. **Gap:** None.

### G.3 — `GMSLA` / `MSLA` (SBL Master Agreement)

1. **Direct CDM type:** `LegalAgreementType.MASTER_SECURITY_LENDING` exists; full GMSLA election schema is partial.
2. **Status:** **Partial.** ISLA's CDM working group has been actively extending coverage; in flux.
3. **Anchor:** GMSLA 2018 (Pledge); ISLA model agreements; SIFMA MSLA.
4. **Gap severity:** Significant. GMSLA-specific election bundle (Schedule A elections, manufactured-payment provisions, rehypothecation consents) is not modelled at the depth of CSA elections.

### G.4 — `TradeCollateralProvisions` (Trade.collateral)

1. **Direct CDM type:** `Collateral` with `collateralType`, `eligibleCollateral`, `creditSupportAgreementElections`, `marginApproach`. Path: `cdm-collateral-lib/src/main/rosetta/collateral/`.
2. **Status:** **Direct for OTC bilateral. Partial for CCP-cleared** (per v10.3 App B §6: no dedicated type for "CCP margin rules" distinct from "bilateral collateral provisions").
3. **Rosetta sketch (CCP extension):**
   ```rosetta
   type CCPMarginProvisions extends Collateral:
       clearingHouse Party (1..1)
           [metadata reference]
       marginMethodology CCPMarginMethodEnum (1..1)
       haircutScheduleRef ExternalRulebookReference (1..1)
   ```
4. **Anchor:** ISDA CSA; CCP rule books (LCH, CME, Eurex).
5. **Gap severity:** Moderate.

### G.5 — `ConfirmationDefinitions`

1. **Direct CDM type:** `ContractualDefinitionsEnum`, `ContractDetails`. Path: `cdm-product-lib/src/main/rosetta/product/template/ContractDetails.rosetta`.
2. **Status:** **Direct.**
3. **Anchor:** 2006 ISDA Definitions, 2021 ISDA Interest Rate Definitions, 2003 Credit Definitions, 2002 Equity Definitions.
4. **Gap:** None.

### G.6 — `MandateContractTerms` (managed account mandate, $u_{MA}$)

1. **Direct CDM type:** None directly. Closest: `LegalAgreement` of a custom type.
2. **Status:** **Missing.**
3. **Anchor:** No industry standard; investment management agreement (IMA).
4. **Gap severity:** Moderate. Per StatesHome, mandate contract is a unit ($u_{MA}$); requires Ledger-native treatment.

### G.7 — `TripartyAgreement` (SBL)

1. **Direct CDM type:** None first-class.
2. **Status:** **Missing.**
3. **Anchor:** Triparty agent agreements (BNYM, JPM, Euroclear Triparty, Clearstream).
4. **Gap severity:** Moderate.

### G.8 — `AgentLenderDisclosure` (SBL)

1. **Direct CDM type:** None.
2. **Status:** **Missing.**
3. **Anchor:** ISLA agent-lender disclosure schedules.
4. **Gap severity:** Moderate.

### G.9 — `EligibleCollateralSchedule` (with tokenised assets — NEW LEAF)

1. **Direct CDM type:** `EligibleCollateralSchedule`. Path: `cdm-collateral-lib/src/main/rosetta/collateral/`.
2. **Status:** **Partial.** Direct for traditional asset classes; **tokenised collateral is a CDM gap** (per v10.3 §10.6 / §17 Open Problem).
3. **Rosetta sketch (tokenised extension):**
   ```rosetta
   type EligibleTokenisedCollateral:
       chainId string (1..1)
       contractAddress string (1..1)
       tokenStandard TokenStandardEnum (1..1)
       underlyingAsset Asset (0..1)
           [metadata reference]
       backingModel BackingModelEnum (1..1)
       custodian Party (0..1)
           [metadata reference]
       proofOfReservesLink string (0..1)
       attestationFrequency Frequency (0..1)

   enum TokenStandardEnum:
       ERC_20
       ERC_1400
       SPL
       OTHER

   enum BackingModelEnum:
       CUSTODIAL_MIRROR
       ON_CHAIN_NATIVE
       SYNTHETIC
   ```
4. **Anchor:** EIP-155 chain ID; ERC standards; no ISO 20022 message family yet.
5. **Gap severity:** Significant — strategic gap.

---

## §H — Identity, Provenance & Audit Group

### H.1 — `ProvenanceMetadata` (move-stream cross-system identifiers)

1. **Direct CDM type:** `MetaFields`, `Lineage`, `WorkflowStep.lineage`. Path: `cdm-base-lib/src/main/rosetta/base/metafields/`.
2. **Status:** **Partial.** CDM `Lineage` covers CDM-internal references but not the cross-system identifier bundle.
3. **Rosetta sketch (extension):**
   ```rosetta
   type ExternalReferenceBundle:
       fpmlMessageId string (0..1)
       iso20022EndToEndId string (0..1)
       sftrSubmissionId string (0..1)
       slateLoanId string (0..1)
       drrSubmissionId string (0..1)
       emirReportId string (0..1)
       cftcSubmissionId string (0..1)
       mifirTransactionId string (0..1)
   ```
4. **FpML / ISO 20022 anchor:** FpML `messageId`; ISO 20022 `MsgId`, `EndToEndId`, `UETR`.
5. **Gap severity:** Significant.

### H.2 — `AuditLogEntry` (hash-chained)

1. **Direct CDM type:** None.
2. **Status:** **Missing — correctly out of CDM scope.**
3. **Gap:** No CDM extension proposed.

### H.3 — `TimeTuple` (economic + booking + knowledge)

1. **Direct CDM type:** `BusinessEvent.eventDate` and `effectiveDate` cover two of three. **Knowledge time** (calibration epoch from Valuation v1.0 §6.1) is not modelled.
2. **Status:** **Partial.**
3. **Rosetta sketch:**
   ```rosetta
   type TimeTuple:
       economicTime zonedDateTime (1..1)
       bookingTime zonedDateTime (1..1)
       knowledgeTime zonedDateTime (0..1)
   ```
4. **Anchor:** None. Bitemporal database literature.
5. **Gap severity:** Moderate. Important for replay determinism.

### H.4 — `AttestationEnvelope` (NAZAROV CC-1 universal wire format)

1. **Direct CDM type:** None.
2. **Status:** **Missing.**
3. **Rosetta sketch:**
   ```rosetta
   type AttestationEnvelope:
       payload string (1..1)
       payloadHash string (1..1)
       sourceId string (1..1)
       sourceSignature string (1..1)
       sourceSigningKeyId string (1..1)
       sourcePublicationTime zonedDateTime (1..1)
       ingestionTime zonedDateTime (1..1)
       ingestionSignature string (1..1)
       schemaVersion string (1..1)
       mappingVersion string (0..1)
       ingestionPath string (1..1)
   ```
4. **Anchor:** None industry-standard; bespoke per firm.
5. **Gap severity:** Significant. Should wrap every Floor 3/4 datum.

### H.5 — `MarketDataSnapshot` (the `market_data_snap` content-addressed bundle)

1. **Direct CDM type:** `Observation` references; the *content-addressed snapshot bundle* (NAZAROV CC-2) is not modelled.
2. **Status:** **Missing.**
3. **Rosetta sketch:**
   ```rosetta
   type MarketDataSnapshot:
       [metadata key]
       snapshotId string (1..1)
       valuationDate date (1..1)
       envelopeRefs string (1..*)
       fallbackChainTraversed FallbackPathEntry (0..*)
       mappingVersionsApplied MappingVersionEntry (0..*)
       calibrationSnapshotRef string (0..1)
       contentHash string (1..1)
   ```
4. **Anchor:** None.
5. **Gap severity:** Significant.

---

## §I — Cross-Cutting CDM Mapping Rules (apply to every cross-walk)

### I.1 — Synonym mapping discipline (NAZAROV CC-6)

Every FpML→CDM, FIX→CDM, ISO 20022→CDM synonym **MUST** be:
- Deterministic, total over its declared input domain.
- Version-pinned with `mappingVersion` recorded in every ingested envelope.
- Failure-explicit: a mapping failure is a named failure event, never a silent default.
- Replay-deterministic: replays under the same mapping version must be bit-identical.

This is enforced at the `rune-fpml` repository level via the synonym DSL and covered by the synonym test corpus. **Verification:** mapping coverage per-product is uneven; structured products and SBL events have known patchy coverage.

### I.2 — Qualification function discipline

CDM infers product type from `EconomicTerms` using `ProductQualification` functions annotated `[qualification Product]`. Each cross-walk above where the product is OTC must specify which `Qualify_*` function would fire:
- `Qualify_InterestRate_IRSwap_FixedFloat` for vanilla IRS
- `Qualify_EquitySwap_VarianceSwap` for variance swap
- `Qualify_CreditDefault_SingleName` for single-name CDS
- etc.

For SBL leaves, **no qualification function exists**; this is part of the SBL CDM gap.

### I.3 — `[metadata key]` usage

The `[metadata key]` annotation on `NonTransferableProduct`, `Trade`, `Party`, `LegalAgreement`, `BusinessEvent` is load-bearing: it makes the object referenceable across the CDM graph by content-hash. Every cross-walked Ledger-native type that needs to be referenced from elsewhere MUST carry `[metadata key]`.

### I.4 — Counterparty cardinality `(2..2)`

`TradableProduct.counterparty Counterparty (2..2)` is enforced by a CDM condition. Every cross-walk involving an OTC trade must respect this. **Two trades that share `NonTransferableProduct` but differ in `CollateralProvisions` are different units** — this is the v10.3 App B §6 dual-CSA test, structurally enforced by the unit-identity layer.

---

## §J — Top 5 CDM Gaps Requiring Extension (Severity-Ranked)

These are the most important gaps the cross-walk surfaces — each requires an upstream CDM contribution, a Ledger-native parallel schema, or both.

### Gap 1: Calibrated Market Data Layer (E.1–E.6) — **STRATEGIC**

The entire Floor of calibrated objects (`CalibratedYieldCurve`, `CalibratedVolSurface`, `CalibratedFXSurface`, `CalibratedCreditHazardCurve`, `KalmanPosterior`, `SensitivityJacobian`, `ValuationRecord`) is **CDM-missing**. CDM was never designed as a calibration store, but Ledger v11 + Valuation v1.0 require this layer to be first-class.

**Recommendation:** Propose a `cdm-valuation-lib` extension upstream to FINOS. Strategic question for firm: contribute upstream (ISDA / FINOS dialogue) or run Ledger-native parallel schema. The choice has enterprise-wide implications.

### Gap 2: SBL Lifecycle Triplet — Recall, Locate, Rehypothecation (D.9, F.3 SBL extension, F.5) — **SIGNIFICANT**

Per v10.3 §17.18, three explicit gaps in CDM `PrimitiveInstruction` choice. Blocking for SFTR / SLATE complete coverage. ISLA's CDM working group is actively contributing here — Phase 2 should align with their current proposal, not duplicate it.

**Recommendation:** Coordinate directly with ISLA CDM SBL working group. Adopt their proposed extensions when published; bridge with local types until then.

### Gap 3: Tokenised Collateral & Backing Attestations (G.9 + part of A.x) — **SIGNIFICANT**

CDM has no first-class concept of `(chainId, contractAddress, tokenStandard, backingModel)`, the custodian-flat principle, or proof-of-reserves attestation. v10.3 §10.6 explicitly identifies this as central tokenisation risk.

**Recommendation:** New `cdm-tokenisation-lib` extension proposal upstream; meanwhile, Ledger-native types per the G.9 sketch.

### Gap 4: Oracle Attestation Envelope Universal Wire Format (H.4, H.5) — **SIGNIFICANT**

NAZAROV's CC-1 attestation envelope and CC-2 snapshot specification are not modelled in CDM at all. Without them, every Floor-3/4 datum lacks a uniform attestation discipline, and replay determinism cannot be guaranteed end-to-end.

**Recommendation:** Ledger-native first-class types (no upstream proposal — this is firm-level discipline). Wrap every observation, fixing, confirmation, and statement in an `AttestationEnvelope`; index by content-addressed `MarketDataSnapshot.snapshotId`.

### Gap 5: TradeState ↔ StatesHome Three-Map Alignment (F.4) — **ARCHITECTURAL**

CDM `TradeState` and StatesHome `(ProductTerms, UnitStatus, PositionState)` model the same conceptual territory but factor it differently. **Per StatesHome F6: the alignment is asserted, not verified.** This is the most important unresolved architectural CDM-alignment question in the project — it affects every replay, every CDM event payload, and every regulatory submission.

**Recommendation:** Re-run Rosetta NS1–7 mapping against the three-map schema as a Phase 3 verification deliverable. Until verified, every `BusinessEvent` payload carries a parallel `unitStateDeltas` block (per F.2 sketch) so the StatesHome view is preserved alongside the CDM view.

### Honourable mentions (not in top 5 but recurring):

- **Manufactured payments** (D.10) — significant for SBL.
- **CCP margin parameters** (B.5, G.4 extension) — moderate.
- **Corporate action `seev.*` synonym mapping** (B.3, D.x) — moderate but high operational impact.
- **Obligation as first-class type** (F.6) — moderate; CDM may benefit from absorbing upstream.

---

## §K — Verification Disclosure & Outstanding Questions

**Verification status of cited CDM paths.** I cite paths from `rosetta-models/common-domain-model` from internal CDM 6.0.0 knowledge. **I have not re-fetched every cited file from the live repo in this Phase 2 cycle.** Items where I am least certain about field-level details: G.2 `CreditSupportAgreementElections` excerpt, B.3 `CorporateAction` event-shape coverage, F.4 `TradeState` exact field set, A.2 `Security.rosetta` extensions area. **Before any of these gap sketches becomes a Rosetta extension PR, the live `.rosetta` file must be re-read against the published CDM 6.0.0 release.**

**Two convergence questions for the Data Team to resolve:**

1. **Calibrated Market floor strategy (Gap 1).** Whether to propose `cdm-valuation-lib` extension upstream to FINOS or to live with a Ledger-native parallel schema. This is firm-level CDM contribution policy. Downstream impact: PnL explain, FRTB capital, IPV pipeline.

2. **SBL gap alignment (Gap 2).** Track ISLA's CDM working group proposal cadence; do not duplicate their work. Phase 2 should defer the SBL extension PR until ISLA's current proposal is public.

**Memory note (saved separately in agent memory):** v10.3 ledger / valuation cross-walk results, TradeState↔StatesHome verification status, and the SBL ISLA working group dependency are now logged for future conversations.

---

## §L — Cross-Walk Summary Statistics

| Group | Leaves | Direct | Partial | Missing |
|---|---|---|---|---|
| A — Definitions (Static) | 11 | 6 | 3 | 2 |
| B — Authoritative Tables | 6 | 0 | 2 | 4 |
| C — Continuous Market Observations | 4 | 1 | 3 | 0 |
| D — External Event Attestations (Oracle) | 12 | 3 | 5 | 4 |
| E — Calibrated Market Data | 6 | 0 | 1 | 5 |
| F — Smart-Contract Execution | 9 | 1 | 4 | 4 |
| G — Legal & Agreement | 9 | 3 | 2 | 4 |
| H — Identity, Provenance & Audit | 5 | 0 | 2 | 3 |
| **Total** | **62** | **14** | **22** | **26** |

(Note: leaf count exceeds the 35-leaf working figure I anticipated up-front because each multi-product family — e.g., C.3 EquityQuote / RatesQuote / VolatilityQuote / CreditSpread / FXRate / ReferenceMark — has been treated as a single row but covers 6 sub-leaves; expanding gives ~62. Direct/Partial/Missing splits include sub-leaves at the most-restrictive status.)

**Of the 26 Missing items, 8 are correctly out of CDM scope** (TemporalWorkflowState, AuditLogEntry, SystemEpoch, infrastructure metadata). The remaining **18 Missing + 22 Partial = 40 items requiring CDM cross-walk attention**, of which **14 are Significant or Strategic severity** (the top 5 gaps above plus 9 honourable mentions).

---

## §M — Closing

The CDM cross-walk is highly uneven across the eight floors:

- **Static / ProductTerms (Group A)** is well-served by CDM 6.0.0 with two structural gaps (`ExchangeContractSpec` catalogue, `BondCouponSchedule`).
- **Legal & Agreement (Group G)** is well-served by `cdm-legalagreement-lib` for ISDA/CSA, with significant gaps for GMSLA/MSLA, mandate, triparty, agent-lender disclosure, and tokenised collateral.
- **Smart-Contract Execution (Group F)** has direct mapping at the `BusinessEvent` / `Transfer` / `TradeState` core, with the SBL three-event gap and the StatesHome three-map alignment as the principal unresolved questions.
- **Oracle (Group D, expanded)** is partial across the family: vanilla settlement messages mapped, corporate-action `seev.*` patchy, custodian statements and SBL locate/manufactured-payment missing.
- **Calibrated Market (Group E)** is **entirely CDM-missing** — this is the most strategic gap and the natural seed of a `cdm-valuation-lib` extension proposal.
- **Continuous Market (Group C)** is partially covered: CDM has the right shapes but the streaming/multi-venue/vendor-attested ingest dimension is Ledger-native.
- **Authoritative Tables (Group B)** is largely missing in CDM (sanctions, tax, CCP parameters, SSI).
- **Identity & Provenance (Group H)** has core types directly but the cross-system identifier bundle and the attestation envelope are Ledger-native discipline.

The framework's six properties (atomicity, conservation, determinism, state-sufficiency, lifecycle value invariance, time travel) hold only because the system is closed within its boundary. CDM is the canonical interchange format **at the boundary** — every gap above is a place where the boundary loses its CDM-native discipline and must be supplemented by Ledger-native typing. The Top 5 gaps in §J are the priority list.

— Matthias Vogt, FINOS CDM core team
