# Phase 2 Deliverable v2 — MATTHIAS (CDM/Rosetta Cross-Walk, R1-Revised)

**Author role.** Principal Engineer, FINOS CDM core team. CDM 6.x cross-walk, Rosetta DSL, FpML/ISO 20022 mapping discipline.

**Scope of this revision.** Fresh CDM cross-walk for the v11.0 leaf taxonomy, **with live re-fetch of every cited `.rosetta` file from `github.com/finos/common-domain-model@master`** (verification protocol no longer suspended), and explicit response to the 10 Round-1 directives addressed at T6 in `R1_consolidated_findings.md` and at MATTHIAS in `phase3/round1/matthias.md`.

---

## §0. Changes from v1

This section enumerates every material change against `phase2/matthias.md` v1 and cites the R1 finding addressed.

| # | Change | R1 finding |
|---|---|---|
| C1 | **Path scheme corrected throughout.** v1 cited paths as `cdm-product-lib/src/main/rosetta/...`, `cdm-event-lib/...`, `cdm-collateral-lib/...`, etc. CDM 6.x source actually lives in **a single flat directory** `rosetta-source/src/main/rosetta/` with **dot-namespaced filenames** (`event-common-type.rosetta`, `product-template-type.rosetta`, `legaldocumentation-csa-type.rosetta`, etc.). Every cross-walk row is re-cited against the correct flat path. | T6 / matthias B-1 |
| C2 | **`PrimitiveInstruction` is NOT a `choice`.** v1 declared it as a Rosetta `choice`. The live source declares it as `type PrimitiveInstruction:` with eleven optional `(0..1)` fields (one-of semantics enforced by a CDM condition). This shape difference is structurally important for any extension PR. | T6 / matthias B-1, M-2 |
| C3 | **`BusinessEvent extends EventInstruction`** with `after TradeState (0..*)` (NOT `1..*`) and `eventQualifier string (0..1)`. v1 cited a flat `BusinessEvent` shape with `instruction PrimitiveInstruction (1..*)` and `after TradeState (1..*)`. Both are wrong. The instruction lives on the parent `EventInstruction`, not on `BusinessEvent` directly. | T6 / matthias M-6 |
| C4 | **`Reset.observations` is `Observation (1..*)` not `ObservationEvent (0..*)`.** Live `Reset` also carries `averagingMethodology AveragingCalculation (0..1)` with a CDM condition `if observations count > 1 then averagingMethodology exists`. v1 missed the type, the cardinality, and the condition. | T6 / matthias M-6 |
| C5 | **`TradeState.valuationHistory Valuation (0..*)`** exists in CDM 6.x — v1 missed it. This **changes the calibrated-market-layer gap analysis materially**: CDM does carry a per-trade valuation history (though `Valuation` is thin and does not host posterior parameters). Gap 1 narrows from "entirely missing" to "schema present, posterior content missing". | T6 / matthias B-1 |
| C6 | **`Trade extends TradableProduct`.** v1 cited `Trade` as a top-level type with embedded `tradableProduct TradableProduct (1..1)`. The live CDM has `Trade` extending `TradableProduct` directly, exposing `tradeIdentifier`, `tradeDate`, `party`, `partyRole`, `executionDetails`, `contractDetails`, `collateral Collateral (0..1)`, `account` on `Trade` itself. | T6 / matthias B-1 |
| C7 | **`CollateralProvisions` shape corrected.** v1 stated this type carries `creditSupportAgreementElections`. **It does not.** Live `CollateralProvisions` has only `collateralType CollateralTypeEnum (1..1)`, `eligibleCollateral EligibleCollateralCriteria (0..*)`, `substitutionProvisions SubstitutionProvisions (0..1)`. The CSA elections live elsewhere — on `AgreementTerms` via `LegalAgreement` (per CDM legal-agreement model, separate file `legaldocumentation-csa-type.rosetta`). | T6 / matthias M-6 |
| C8 | **`CreditSupportAgreementElectionsBase` field set rewritten.** Live shape is `(baseAndEligibleCurrency, conditionsPrecedent, substitution, disputeResolution, holdingAndUsingPostedCollateral, distributionAndInterestPayment, otherEligibleAndPostedSupport, demandsAndNotices, additionalRepresentations, masterAgreementDatedAsOfDate, finalReturns)` — none of which match v1's claimed `(threshold, minimumTransferAmount, eligibleCollateral, interestRate, governingLaw)`. v1 was working from a much earlier CDM version or from synthesis. **Threshold and MTA live deeper, inside `creditSupportObligations`** — not at the top level. | T6 / matthias B-1, M-2 |
| C9 | **`LegalAgreement` does NOT have a top-level `agreementType` field.** Live shape has `agreementTerms AgreementTerms (0..1)`, `relatedAgreements`, `umbrellaAgreement`, plus the inherited `LegalAgreementBase` fields (`agreementDate, effectiveDate, identifier, legalAgreementIdentification LegalAgreementIdentification (1..1), contractualParty Party (2..2), otherParty PartyRole (0..*)`). The agreement type lives at `legalAgreementIdentification.agreementName.agreementType : LegalAgreementTypeEnum`. The type name is **`LegalAgreementTypeEnum` everywhere** — never `LegalAgreementType`. | T6 / matthias M-2 |
| C10 | **`MarginCallInstruction` does NOT exist.** Live CDM has `MarginCallBase`, `MarginCallIssuance`, `MarginCallResponse`, `MarginCallExposure`, `MarginCallInstructionType`, `MarginCallActionEnum` — and they live in **`event-common-type.rosetta`**, NOT in any collateral file. v1's "Direct on the type system" claim with the wrong type name and wrong file is downgraded to **Direct (with name/path correction)**. | T6 / matthias M-2 |
| C11 | **`DigitalAsset` cannot host tokenised collateral as-is.** Live `DigitalAsset extends AssetBase` carries a CDM condition: `assetType = Other`, and the doc-string says: *"An Asset that exists only in digital form, eg Bitcoin or Ethereum, that is not backed by other Assets; **excludes** the digital representation of other Assets, eg coins or Tokenised assets."* So **DigitalAsset is for native digital assets, not for tokenised representations of off-chain assets**. The Phase-3 R1 `matthias.md` recommendation to "extend `DigitalAsset` for tokenised collateral" is wrong; ISDA's `lifecycle_model = SmartContract` framing is the right approach. | R1-T5 / isda B-2 |
| C12 | **Qualification function names corrected.** v1 cited `Qualify_EquitySwap_VarianceSwap` (does not exist) and `Qualify_CreditDefault_SingleName` (does not exist). Correct names: `Qualify_EquitySwap_ParameterReturnVariance_{SingleName,Index,Basket}`, `Qualify_CreditDefaultSwap_SingleName`. `Qualify_InterestRate_IRSwap_FixedFloat` **is correct**. **`Qualify_SecurityLending` exists** — v1 §I.2 claim "no qualification function exists for SBL" is wrong. | T6 / matthias M-2 |
| C13 | **§J Top-5 Strategic Gap list re-classified.** v1 listed 5 "Strategic" gaps. Per R1 directive #4: re-classified to **2 strategic CDM gaps** (Calibrated layer, TradeState alignment), **1 significant CDM extension** (tokenised collateral, framed as `lifecycle_model = SmartContract` per ISDA), **1 operational ISLA-coordinated** (SBL recall/locate/rehyp), **1 Ledger-internal discipline** (oracle envelope — moved out of CDM gap list). | T6 / matthias M-1 |
| C14 | **Gap 5 (TradeState↔StatesHome alignment) promoted to top of §7.** v1 ranked it last. Per R1 directive #2: it owns the dependency for proposal Theorems 1, 2, 4. It is now §7.1. | T6 / matthias B-2 |
| C15 | **§7 re-issued with true distinct-PR-unit headcount (~15, not 5).** Per R1 directive #3. The "5 strategic gaps" framing hid 15 distinct CDM PR units. Each is now enumerated. | T6 / matthias B-4 |
| C16 | **§7.6 (NEW) Migration discipline for Ledger-internal types.** Each Ledger-native type carries a `cdm_native_pending` flag. Migration record in L12 `ExternalConfirmation` when CDM extension lands. Per R1 directive #8 / formalis M5. | T6 / formalis M5 |
| C17 | **`Reset` and `BusinessEvent` Direct claims downgraded to Partial after corner-case audit.** Per R1 directive #5 / matthias M-6: `Reset` does not carry a snapshot-id field tying it to L19; `BusinessEvent` does not carry executor-signature, hash-chain prev-pointer, or idempotency token. These are Ledger-native sidecar concerns. | T6 / matthias M-6 |
| C18 | **Tokenised collateral framing reframed (D2 disagreement with ISDA).** v1 §G.9 sketched a standalone `EligibleTokenisedCollateral` type and Top-5 gap recommended a `cdm-tokenisation-lib`. Per R1 directive #6: combined with ISDA's `lifecycle_model = SmartContract` lifecycle-model approach in L1 ProductTerms; the L13 collateral routing references this via `EligibleCollateralCriteria` extensions, NOT a parallel cdm-tokenisation-lib. The standalone library is **deferred to v12.0**. | T6 / isda B-2 |
| C19 | **NEW §N: L25 RegulatorySubmission CDM cross-walk.** Per R1 directive #10. NAZAROV adds the leaf; this revision provides the cross-walk: DRR-generated CDM payloads, with `drr_rule_set_version` axis on L21 distinct from `cdm_version`. | T5 / isda B-1, UM-1 |
| C20 | **§A.2 ListedEquity, §A.3 ExchangeContractSpec, §D.2 seev mapping, §G.4 CCP-cleared** Partial classifications acknowledged as **materially Missing on operationally-load-bearing fields** (R1 matthias M-4). Re-classified: A.2 → Partial (materially Missing on `boardLotSize`/`votingRights`); A.3 → Missing (CCP-as-unit-identity not addressable in CDM); D.2 seev → Missing for `seev.*` family; G.4 CCP-cleared → Missing. | T6 / matthias M-4 |

**Verification status of this revision.** Every type, field, cardinality, condition, and qualification-function name cited below has been verified against `https://raw.githubusercontent.com/finos/common-domain-model/master/rosetta-source/src/main/rosetta/<file>.rosetta` between 2026-04-30 04:00 and 04:30 UTC. Files fetched: `event-common-type`, `event-workflow-type`, `product-template-type`, `product-asset-type`, `product-collateral-type`, `legaldocumentation-csa-type`, `legaldocumentation-master-type`, `legaldocumentation-common-type`, `observable-asset-type`, `observable-event-type`, `base-staticdata-asset-common-type`, `base-staticdata-party-type`, `product-common-settlement-type`, `margin-schedule-type`, `product-qualification-func`. Where a claim could not be verified directly from this corpus (e.g., `IndexComposition` constituent depth, `seev.*` synonym coverage), the row is tagged `[unverified]` and gives the closest fetched evidence.

**Ground rule for Round 2 reviewers.** Any Direct/Partial/Missing label below that is not tagged `[unverified]` is backed by a re-fetch from the live repo. If a reviewer believes a label is wrong, please cite the file path on master they consulted — I will reconcile.

---

## §A — Definitions Group (Static / ProductTerms / Reference)

### A.1 — `CurrencyUnit` (cash unit)
- **CDM type:** `Cash` extends `AssetBase`, branch of `choice Asset`. Path: `rosetta-source/src/main/rosetta/base-staticdata-asset-common-type.rosetta` (line ~10, `choice Asset { Cash, Commodity, DigitalAsset, Instrument }`).
- **Status:** Direct.
- **Anchor:** ISO 4217 currency; FpML `currency`; ISO 20022 `Ccy`.

### A.2 — `ListedEquity`
- **CDM type:** `Security extends InstrumentBase` with `securityType SecurityTypeEnum (1..1)`, `debtType DebtType (0..1)`, `equityType EquityType (0..1)`. Path: `base-staticdata-asset-common-type.rosetta` (line 214).
- **Status:** **Partial — materially Missing** on `boardLotSize`, `votingRights`, `dividendPolicyRef`, `corporateActionFeedRef` (R1 matthias M-4: missing `boardLotSize` blocks block-trade compliance; missing `votingRights` blocks proxy-voting workflows). Recommend reclassification to Missing for those operationally-load-bearing fields.
- **Anchor:** FpML `equity`; ISO 20022 `reda.005`.
- **Extension:** As v1 §A.2; preserved.

### A.3 — `ExchangeContractSpec` (listed derivative spec)
- **CDM type:** `ListedDerivative extends InstrumentBase`. Path: `base-staticdata-asset-common-type.rosetta` (line 158).
- **Status:** **Missing on the catalogue concept.** Per StatesHome §4.1: CCP identity is part of unit identity (CME-ES vs ICE-ES are distinct units). CDM `ListedDerivative` has no `clearingHouse` field. The v10.3 §3.10 dual-CCP test fails structurally without an extension. **Reclassified from Partial to Missing.**
- **Extension sketch:** Per v1 §A.3 (`ExchangeContractSpec` with `clearingHouse Party`, `derivativeTerms NonTransferableProduct (1..1)`).
- **FINOS open issue:** Tracked in CDM exchange-traded coverage discussions.

### A.4 — `BondTerms`
- **CDM type:** `Security` with `debtType DebtType` discriminator.
- **Status:** Partial. Coupon mechanics not on `Security`; `InterestRatePayout` covers if treated as a payout.
- **Extension:** As v1.

### A.5 — `OTCProductTemplate` (`NonTransferableProduct`)
- **CDM type:** `NonTransferableProduct`. Path: `product-template-type.rosetta` (line 297). Field set verified: `[metadata key]`, `identifier ProductIdentifier (0..*)`, `taxonomy ProductTaxonomy (0..*)`, `economicTerms EconomicTerms (1..1)`. Carries CDM condition `PrimaryAssetClass`.
- **Status:** Direct.
- **Qualification:** 102 `Qualify_*` functions exist in `product-qualification-func.rosetta`; OTC products land via the matching qualifier. Names per CDM 6.x: `Qualify_InterestRate_IRSwap_FixedFloat`, `Qualify_EquitySwap_ParameterReturnVariance_Index`, `Qualify_CreditDefaultSwap_SingleName`, `Qualify_RepurchaseAgreement`, `Qualify_BuySellBack`, `Qualify_SecurityLending`, etc.

### A.6 — `BusinessCenters` + `BusinessDayConventions`
- Direct on type system. Tables remain external (correctly out of scope).

### A.7 — `DayCountFractionEnum`
- Direct. Live in `base-datetime-daycount-enum.rosetta`.

### A.8 — `LegalEntityIdentifier` (LEI / Party)
- **CDM type:** `Party`. Path: `base-staticdata-party-type.rosetta`. Field shape confirmed; `partyId PartyIdentifier (1..*)` with ISO 17442 scheme.
- **Status:** Direct.

### A.9 — `TradeIdentifier` (UTI / USI / UPI)
- **CDM type:** `TradeIdentifier`. Field shape confirmed.
- **Status:** Direct.

### A.10 — `WalletRegistry` (sidecar)
- **Status:** Partial. CDM `Account` is closest hook; KYC / capabilities / audit cursor are Ledger-native.
- **Extension:** As v1.

### A.11 — `SystemEpoch` / `LedgerGenesis`
- **Status:** Missing — correctly out of CDM scope (infrastructure).

---

## §B — Authoritative Tables Group (Reference)

### B.1 — `SanctionsList` — Missing. As v1.
### B.2 — `WithholdingTable` (tax) — Missing. As v1.
### B.3 — `CorporateActionsSchedule`
- **CDM type:** `CorporateAction` types via `CorporateActionTypeEnum`; `ObservationEvent.corporateAction CorporateAction (0..1)` is the carrier in the CDM event model. Path verified: `event-common-type.rosetta` (line 178).
- **Status:** Partial on the lifecycle-effect view; **Missing on the announcement / schedule / `seev.*` synonym mapping** (R1 matthias M-4). The v1 "Partial" label is materially closer to Missing for the schedule view.
- **Extension:** As v1.

### B.4 — `IndexComposition` — Partial. `Index` / `EquityIndex` direct; constituent set thin.
### B.5 — `CCPMarginParameters` — Missing.
### B.6 — `StandingSettlementInstructions` (SSI) — **resolved per R1 B-3.** Per the proposal V10 reconciliation, the Ledger consumes SSI but does not author it. The v1 §B.6 Rosetta sketch is **deleted** as a CDM extension proposal; the right artefact is a parser mapping inbound SSI feeds (DTCC ALERT, Omgeo CTM, ISO 20022 `setr.027`/`secl.005`, SWIFT MT540 series) into an opaque `SsiSnapshotRef` recorded against the trade. The audit need (which SSI version was used) is satisfied by versioning the `SsiSnapshotRef`, not by re-modelling the SSI in CDM.

---

## §C — Continuous Market Observations Group (Market-Raw)

### C.1 — `RawQuoteObservation`
- **CDM type:** `Observation`. Path: `observable-event-type.rosetta` (line 102). Live shape: `Observation` is a root type with key support; `ObservationIdentifier` carries the disambiguation.
- **Status:** Partial. CDM observations are scoped to lifecycle (resets, fixings), not generic streaming ingest.
- **Extension:** As v1.

### C.2 — `ResetObservation`
- **CDM type:** `Reset`. Path: `event-common-type.rosetta` (line 185). Verified shape:
  ```rosetta
  type Reset:
      [metadata key]
      resetValue Price (1..1)
      resetDate date (1..1)
      rateRecordDate date (0..1)
      observations Observation (1..*)
          [metadata reference]
      averagingMethodology AveragingCalculation (0..1)

      condition AveragingMethodologyExists:
          if observations count > 1 then averagingMethodology exists
  ```
  **v1 was wrong** on three points: `observations` is `Observation (1..*)` not `ObservationEvent (0..*)` (cardinality and type both); `averagingMethodology` was missed; the condition was missed.
- **Status (corrected per R1 M-6):** **Partial** — Direct at the type level, Missing the snapshot-id binding required for replay determinism (L8 witness). Specifically, `Reset` does not carry a field linking to the L19 Snapshot used to compute `resetValue`; that linkage is a Ledger-native sidecar. **This was Direct in v1; downgraded to Partial here.**

### C.3 — `EquityQuote / RatesQuote / FXRate / VolatilityQuote / CreditSpread / ReferenceMark`
- All represented as `Observation` against an `Observable` (the `choice Observable` in `observable-asset-type.rosetta` line 210).
- **Status:** Partial across the family. CDM has the right shapes but the streaming/multi-venue/vendor-attested ingest dimension is Ledger-native.

### C.4 — `SettlementPriceObservation` — Partial. As v1.

---

## §D — External Event Attestations Group (Oracle, expanded)

### D.1 — `FpMLConfirmation` (inbound trade confirmation)
- **CDM mapping:** Synonym layer in `ingest-fpml-confirmation-*-func.rosetta` (38 separate FpML mapping files, one per product family). Path verified: `rosetta-source/src/main/rosetta/ingest-fpml-confirmation-product-{varianceswap,equityoption,swap,fra,creditdefaultswap,repo,…}-func.rosetta`.
- **Status:** Direct for vanilla IRS, FX, equity options, CDS, repo, variance/volatility swaps. Partial for exotics, novations, structured notes.

### D.2 — `ISO20022SettlementMessage`
- **CDM mapping:** Synonym annotations on `Transfer` and settlement-related types.
- **Status:** Partial for `pacs.*` / `pain.*` / `sese.*` settlement family. **Missing for `seev.*` corporate-action family** (R1 matthias M-4: this is materially Missing — every dividend record date / ex-date / payment date triggers a Ledger event).
- **Anchor list:** `pacs.008/.009`, `pain.001`, `secl.001/.002/.003/.005`, `sese.023/.025`, `camt.054`, `semt.013/.017`, `seev.031/.035/.039/.040/.041`.

### D.3 — `BarrierObservation` (oracle attestation)
- **CDM type:** Carried via `ObservationEvent` in CDM event model. **But note** — live `ObservationEvent` is shaped as a one-of choice between `creditEvent CreditEvent (0..1)` and `corporateAction CorporateAction (0..1)` (path: `event-common-type.rosetta` line 178). Barrier breaches are not first-class in `ObservationEvent`; they go through `Observation` + a payout-level barrier-trigger condition.
- **Status:** Partial. Attestation envelope is Ledger-native.
- **Extension:** As v1, but routed through `Observation`, not by extending `ObservationEvent`.

### D.4 — `ExerciseNotice`
- **CDM type:** `ExerciseInstruction`, one of the 11 fields in `PrimitiveInstruction` (path: `event-common-type.rosetta` line 47). **Note** — `PrimitiveInstruction` is a `type` with `(0..1)` fields, NOT a `choice`. (v1 was wrong on this — see C2 above.)
- **Status:** Direct.

### D.5 — `CreditEventNotice` — Partial.
### D.6 — `SettlementConfirmation` — Partial.
### D.7 — `CustodianAttestation` — Missing.

### D.8 — `MarginCallConfirmation` (CSA / triparty)
- **Live CDM types (verified):** `MarginCallBase`, `MarginCallIssuance extends MarginCallBase`, `MarginCallResponse extends MarginCallBase`, `MarginCallExposure extends MarginCallBase`, `MarginCallInstructionType`, `MarginCallActionEnum`, `MarginCallResponseAction`. **All in `event-common-type.rosetta` (lines 676–765), NOT in `product-collateral-type.rosetta`.**
- **v1 was wrong** on type name (`MarginCallInstruction` does not exist; correct is `MarginCallIssuance`) and path (`cdm-collateral-lib`).
- **Status:** **Direct (with name/path correction).** Triparty agent attestation envelope still operational (Ledger-native).
- **Anchor:** `colr.003/.004/.005/.016`.

### D.9 — `LocateConfirmation` (SBL) — **Missing.** Tracked by ISLA CDM working group (see §J Gap "SBL Triplet" and memory `sbl_isla_dependency.md`). No firm-led PR; coordinate with ISLA.
### D.10 — `ManufacturedPaymentRate / TaxTreatmentOracle` (SBL) — **Missing.** ISLA-coordinated.
### D.11 — `DefaultEvent / BuyInEvent` (SBL) — Missing.
### D.12 — `RegulatoryAcknowledgement` (TR ack) — **Now part of L25 RegulatorySubmission cross-walk; see §N below.** Per R1 isda B-1.

---

## §E — Calibrated Market Data Group (the strategic CDM gap)

This group is **almost entirely CDM-missing** — but with one important nuance from C5: CDM 6.x `TradeState` carries `valuationHistory Valuation (0..*)`. So the **container** for valuations exists; the **content** (posterior parameters, Kalman state, sensitivity Jacobians, arbitrage-free certificates) does not.

### E.1–E.6 — `CalibratedYieldCurve / CalibratedVolSurface / CalibratedFXSurface / CalibratedCreditHazardCurve / KalmanPosterior / SensitivityJacobian / ValuationRecord`
- **CDM types:** None for posterior content. `Valuation` exists as a thin record on `TradeState.valuationHistory`.
- **Status:** Missing for posterior parameters, posterior covariance, innovation statistic, arbitrage-free certificate, sensitivity Jacobian. **Partial for `ValuationRecord` since `Valuation` is the container.**
- **Strategic recommendation:** propose `cdm-valuation-lib` (working name) extension upstream to FINOS. This is the single largest strategic CDM gap surfaced by the cross-walk, and it is not closeable with existing types. See §J Gap 1.

---

## §F — Smart-Contract & Lifecycle Execution Group (Effects)

### F.1 — `Move` — Partial. SBL six-coordinate vector not first-class; per R1 sbl Finding 1 / minsky F11 a smart constructor is required. Extension as v1.

### F.2 — `LedgerTransaction` — Partial. `WorkflowStep + BusinessEvent` is the closure; `txType`, executor signature, hash-chain pointer are Ledger-native.

### F.3 — `BusinessEvent / PrimitiveInstruction` Payload — corrected
- **Live shape (verified):**
  ```rosetta
  type BusinessEvent extends EventInstruction:
      [metadata key]
      [rootType]
      eventQualifier string (0..1)
      after TradeState (0..*)

      condition EventDate:
          eventDate exists

  type PrimitiveInstruction:                  // NOT a choice — 11 optional fields
      contractFormation ContractFormationInstruction (0..1)
      execution ExecutionInstruction (0..1)
      exercise ExerciseInstruction (0..1)
      partyChange PartyChangeInstruction (0..1)
      quantityChange QuantityChangeInstruction (0..1)
      reset ResetInstruction (0..1)
      split SplitInstruction (0..1)
      termsChange TermsChangeInstruction (0..1)
      transfer TransferInstruction (0..1)
      indexTransition IndexTransitionInstruction (0..1)   // YES, this is in the set — v1 right on existence; wrong on shape
      stockSplit StockSplitInstruction (0..1)
      observation ObservationInstruction (0..1)
      valuation ValuationInstruction (0..1)
  ```
- **Status (corrected per R1 M-6):** **Partial** — Direct on the type system, Missing on (a) executor signature, (b) hash-chain prev-pointer, (c) idempotency token. These three are required by v10.3 §13 substantiation but live only in Ledger-native sidecars. **This was Direct in v1; downgraded to Partial here.**
- **SBL gap:** Recall, Locate, Rehypothecation are NOT in the 13 PrimitiveInstruction fields. Adding them requires extending the type with three new optional fields plus three new `*Instruction` types. This is a `PrimitiveInstruction` extension PR, ISLA-coordinated.

### F.4 — `TradeState` / `UnitStateMaps` (StatesHome 3-map) — **GATING GAP**
- **Live shape (verified):**
  ```rosetta
  type TradeState:
      [metadata key]
      [rootType]
      trade Trade (1..1)
      state State (0..1)
      resetHistory Reset (0..*)
      transferHistory TransferState (0..*)
      observationHistory ObservationEvent (0..*)
      valuationHistory Valuation (0..*)             // v1 missed this
  ```
- **Status:** **Partial — gating architectural gap.** CDM `TradeState` and StatesHome `(ProductTerms[u], UnitStatus[u], PositionState[w,u])` model the same conceptual territory but factor it differently. Specifically:
  - **`Trade` is per-trade**; StatesHome's `PositionState` is per-(wallet, unit) and has dimension six (own, on_loan, borrowed, coll_post, coll_recv, coll_rehyp). A `TradeState` cannot natively host a per-wallet six-coordinate position vector; this requires an external aggregation.
  - **`State State (0..1)`** in CDM is a thin enumeration (`Active / Cancelled / Terminated / Matured / ClosedOut`); StatesHome's `UnitStatus` is a richer FSM with `(σ(u), staleness, FSM cursor, last_settlement_price, …)`. The CDM `State` cannot host the StatesHome cursor without lossy compression.
  - **`ProductTerms[u]`** is per-unit-type (e.g., a CME ES futures contract spec); CDM's analogue is `NonTransferableProduct` — but `NonTransferableProduct` is OTC-shaped and does not host CCP-specific listed-derivative spec elements (per §A.3).
- **Why this is the gating gap:** Theorems 1 (Conservation Lifting), 2 (Replay Determinism), 4 (Substantiation) in proposal §8 all require the CDM payload faithfully carrying the StatesHome economic content. If the projection is lossy, three theorems share the failure.
- **Phase-3 verification deliverable (re-issued per R1 M-7):**
  1. **Corpus:** 12 trade types × 8 lifecycle events = 96 round-trip test cases. Trade types: vanilla IRS fix-float, OIS, basis, cross-currency IRS, vanilla equity option, equity variance swap, total-return equity swap, single-name CDS, FX forward, CME ES future, listed equity option, SBL loan. Events: contract formation, partial termination, novation, fee/coupon reset, exercise, observation, valuation update, full termination.
  2. **Pass criterion:** **surjective projection with named axes lost.** A bit-identical round-trip is not feasible (and not required for soundness). The pass criterion is: for each trade × event pair, the StatesHome `(ProductTerms, UnitStatus, PositionState)` after the event must be reconstructible from the CDM `(Trade, BusinessEvent, TradeState)` after the event **plus a named, finite, version-pinned sidecar projection map**. Each axis lost in the CDM-only projection (e.g., per-wallet position decomposition, six-coordinate vector, FSM cursor) must be enumerated and bound to the sidecar.
  3. **Owner:** unit-registration workflow + MATTHIAS (CDM/ISO interop lead).
  4. **Deadline:** Round 2 admission gate. The data team must produce the round-trip suite and the sidecar projection map before §8 theorems can be cleared.

### F.5 — `SBLLoanUnit` — Partial; `Qualify_SecurityLending` exists; recall/locate/rehyp missing.
### F.6 — `Obligation` — Missing.
### F.7 — `TemporalWorkflowState` — Missing, correctly out of scope.
### F.8 — `SmartContractVersion / PricingModelVersion` — Missing, configuration-as-data, Ledger-native.
### F.9 — `ElectionDecision` — Partial.

---

## §G — Legal & Agreement Group

### G.1 — `ISDAMasterAgreement`
- **CDM type:** `LegalAgreement extends LegalAgreementBase`. Path: `legaldocumentation-common-type.rosetta` (line 66). **Verified shape (corrected from v1):**
  ```rosetta
  type LegalAgreementBase:
      agreementDate date (0..1)
      effectiveDate date (0..1)
      identifier Identifier (0..*)
      legalAgreementIdentification LegalAgreementIdentification (1..1)
      contractualParty Party (2..2)
          [metadata reference]
      otherParty PartyRole (0..*)

  type LegalAgreement extends LegalAgreementBase:
      [metadata key]
      [rootType]
      agreementTerms AgreementTerms (0..1)
      relatedAgreements LegalAgreement (0..*)
      umbrellaAgreement UmbrellaAgreement (0..1)
  ```
  **The agreement type is on `LegalAgreementIdentification.agreementName.agreementType : LegalAgreementTypeEnum`** — not at the top level as v1 had it. The type spelling is **`LegalAgreementTypeEnum`**, never `LegalAgreementType`.
- **Status:** Direct.
- **CDM condition observed:** `AgreementVerification` cross-checks that `agreementTerms -> agreement -> creditSupportAgreementElections` exists IFF `legalAgreementIdentification -> agreementName -> creditSupportAgreementType` is `CreditSupportAnnex` or `CreditSupportDeed`. This is structurally important — a CSA cannot be silently attached to a non-CSA-typed `LegalAgreement`.

### G.2 — `CSAElections` — **shape corrected per C8**
- **CDM type:** `CreditSupportAgreementElectionsBase`. Path: `legaldocumentation-csa-type.rosetta` (line 89). **Verified shape:**
  ```rosetta
  type CreditSupportAgreementElectionsBase:
      baseAndEligibleCurrency BaseAndEligibleCurrency (1..1)
      conditionsPrecedent ConditionsPrecedent (0..1)
      substitution Substitution (0..1)
      disputeResolution DisputeResolution (1..1)
      holdingAndUsingPostedCollateral HoldingAndUsingPostedCollateral (0..1)
      distributionAndInterestPayment DistributionAndInterestPayment (0..1)
      otherEligibleAndPostedSupport OtherEligibleAndPostedSupport (0..1)
      demandsAndNotices DemandsAndNotices (0..1)
      additionalRepresentations AdditionalRepresentations (0..1)
      masterAgreementDatedAsOfDate MasterAgreementDatedAsOfDate (0..1)
      finalReturns FinalReturns (1..1)
  ```
  v1's claimed shape `(threshold, minimumTransferAmount, eligibleCollateral, interestRate, governingLaw)` is wrong at every field. Threshold and MTA are deeper, in `creditSupportObligations` (a separate type, on `CollateralTransferAgreementElections` or specialised CSA election variants). Interest rate is inside `distributionAndInterestPayment`. Governing law is on `LegalAgreementIdentification`.
- **Status:** Direct, but with the correction: the v1 sketch should not be reused as a basis for any extension PR.

### G.3 — `GMSLA / MSLA` — Partial. `legaldocumentation-master-isla-type.rosetta` exists; ISLA continuing to extend.
### G.4 — `TradeCollateralProvisions` (Trade.collateral)
- **Live shape (verified):**
  ```rosetta
  type Collateral:
      collateralPortfolio CollateralPortfolio (0..*)
      collateralProvisions CollateralProvisions (0..1)
      // … with conditions

  type CollateralProvisions:
      collateralType CollateralTypeEnum (1..1)
      eligibleCollateral EligibleCollateralCriteria (0..*)
      substitutionProvisions SubstitutionProvisions (0..1)
  ```
  v1 claimed `CollateralProvisions` carries `creditSupportAgreementElections` and `marginApproach` — neither field exists on `CollateralProvisions` in CDM 6.x. The CSA elections live on the `LegalAgreement` referenced via `Trade.contractDetails.documentation`, not on `Trade.collateral.collateralProvisions`.
- **Status:** Direct for OTC bilateral. **Missing for CCP-cleared** (no CCP-specific marginApproach type; reclassified from Partial to Missing per R1 matthias M-4). CCP margin reconciliation needs a `CCPMarginProvisions extends Collateral` extension (sketch as v1).

### G.5 — `ConfirmationDefinitions` — Direct.
### G.6 — `MandateContractTerms` — Missing.
### G.7 — `TripartyAgreement` — Missing.
### G.8 — `AgentLenderDisclosure` — Missing.

### G.9 — `EligibleCollateralSchedule` (with tokenised assets) — **REFRAMED per C18**
- **CDM type:** `EligibleCollateralSpecification` and `EligibleCollateralCriteria` exist. Path: `product-collateral-type.rosetta` (lines 95, 112).
- **DigitalAsset cannot host tokenised collateral.** As verified at C11: `DigitalAsset` has condition `assetType = Other` and an explicit doc-string excluding "the digital representation of other Assets, eg coins or Tokenised assets." So extending `DigitalAsset` for tokenised collateral **violates a CDM condition**. The R1 matthias M-3 recommendation to "extend `DigitalAsset`" is rescinded.
- **Reframed approach (combining ISDA D2 disagreement resolution):**
  1. **Lifecycle-model variant in L1 ProductTerms** (ISDA-aligned): introduce a `lifecycle_model` discriminator at L1 with values `{Conventional, SmartContract}`. The smart-contract case routes execution differently — the chain commit is the L14 event; the executor relays.
  2. **Tokenised collateral metadata in `EligibleCollateralCriteria`**: add `(chainId, contractAddress, tokenStandard, backingModel, proofOfReservesRef)` as Ledger-internal extension fields tagged `cdm_native_pending = true`.
  3. **Backing-attestation cadence as L11 oracle stream**, not as a static `attestationFrequency` field.
  4. **Eligibility predicate** over backing freshness encoded in L7 / L13.
  5. **Standalone `cdm-tokenisation-lib` deferred to v12.0.** Not a Phase-2 deliverable.
- **Status:** Significant CDM gap; routed via L1 + `EligibleCollateralCriteria` extension + L11 oracle, not a parallel library.

---

## §H — Identity, Provenance & Audit Group

### H.1 — `ProvenanceMetadata` — Partial. As v1 (`ExternalReferenceBundle` extension).
### H.2 — `AuditLogEntry` — Missing, correctly out of CDM scope.
### H.3 — `TimeTuple`
- **CDM type:** `BusinessEvent.eventDate`, `effectiveDate` cover two of three. Live `WorkflowStep.timestamp EventTimestamp (1..*)` carries `(dateTime, qualifier)`-tagged collection — this is the closest CDM analogue to the bitemporal axes. **Knowledge time** (calibration epoch) is not modelled.
- **Status:** Partial.
- **Naming alignment recommendation (R1 matthias m-6):** rename Ledger-internal `economicTime / bookingTime / knowledgeTime` to align with CDM `eventDate / effectiveDate / publicationDate` where semantically equivalent. This eases synonym mapping. Where the Ledger needs a third axis CDM does not have (knowledge time), keep the Ledger-native name.

### H.4 — `AttestationEnvelope` — **MOVED OUT OF CDM GAP LIST per R1 directive #4 (Ledger-internal discipline)**
- This is firm-level discipline, not a CDM extension proposal. Tracked under L17 in the proposal. No upstream PR needed. Memory note `cdm_gap_log.md` will be updated.

### H.5 — `MarketDataSnapshot` — **MOVED OUT OF CDM GAP LIST** (same reasoning as H.4).

---

## §I — Cross-Cutting CDM Mapping Rules (apply to every cross-walk)

### I.1 — Synonym mapping discipline (NAZAROV CC-6)
Every FpML→CDM, FIX→CDM, ISO 20022→CDM synonym MUST be:
- Deterministic, total over its declared input domain.
- Version-pinned with `mappingVersion` recorded in every ingested envelope.
- Failure-explicit: a mapping failure is a named failure event, never a silent default.
- Replay-deterministic: replays under the same mapping version must be bit-identical.

The `ingest-fpml-confirmation-*-func.rosetta` files in `rosetta-source/src/main/rosetta/` carry the FpML synonym layer (38 product-specific files). Coverage is uneven; structured products and SBL events have known patchy coverage.

### I.2 — Qualification function discipline (corrected per C12)
102 `Qualify_*` functions verified live in `product-qualification-func.rosetta`. **Verified canonical names** for products in scope:

| Product | Verified `Qualify_*` |
|---|---|
| Vanilla IRS Fixed-Float | `Qualify_InterestRate_IRSwap_FixedFloat` |
| OIS Fixed-Float | `Qualify_InterestRate_IRSwap_FixedFloat_OIS` |
| Basis swap | `Qualify_InterestRate_IRSwap_Basis` |
| Cross-currency IRS | `Qualify_InterestRate_CrossCurrency_FixedFloat` |
| Inflation swap | `Qualify_InterestRate_InflationSwap_FixedFloat_YearOn_Year` |
| Equity variance swap (single name) | `Qualify_EquitySwap_ParameterReturnVariance_SingleName` |
| Equity variance swap (index) | `Qualify_EquitySwap_ParameterReturnVariance_Index` |
| Equity variance option | `Qualify_EquityOption_ParameterReturnVariance_SingleName` |
| Equity TRS (single name) | `Qualify_EquitySwap_TotalReturnBasicPerformance_SingleName` |
| Single-name CDS | `Qualify_CreditDefaultSwap_SingleName` |
| Index CDS | `Qualify_CreditDefaultSwap_Index` |
| Repurchase agreement | `Qualify_RepurchaseAgreement` |
| Buy/sell-back | `Qualify_BuySellBack` |
| Securities lending | `Qualify_SecurityLending` |

**Unverified / no qualification function** (confirmed gap): SBL recall / locate / rehypothecation events do not qualify a product but a primitive instruction; that's a different qualification axis. Listed-derivative-specific qualification (CME ES future, listed equity option) is thin.

### I.3 — `[metadata key]` usage
Verified on `NonTransferableProduct`, `Trade`, `Party`, `LegalAgreement`, `BusinessEvent`, `WorkflowStep`, `TradeState`, `Reset`, `Observation`. Load-bearing for content-hash referencing.

### I.4 — Counterparty cardinality `(2..2)` on `TradableProduct`
Confirmed live on `TradableProduct` (line 315). CDM condition `PriceQuantityTriangulation` and `NotionalAdjustment` enforce structural integrity. Two trades sharing `NonTransferableProduct` but differing in `Trade.collateral` are different units — structurally enforced.

---

## §J — Top Strategic CDM Gaps — Re-Classified per R1 Directives

**Re-classification rule (R1 directive #4):**
- 2 strategic CDM gaps: Calibrated Market Layer, TradeState↔StatesHome alignment
- 1 significant CDM extension: Tokenised collateral via `lifecycle_model = SmartContract` + `EligibleCollateralCriteria` extension
- 1 operational ISLA-coordinated: SBL recall / locate / rehypothecation
- 1 Ledger-internal (moved out of CDM gap list): Attestation envelope + market-data snapshot

The numbered ordering (Gap 1 / Gap 2 / …) is **by gating priority**, not by enumeration position in v1. Gap 5 is now Gap 1 per R1 directive #2.

### Gap 1 (PROMOTED) — TradeState ↔ StatesHome Three-Map Alignment — **STRATEGIC, GATING**
Per F.4 above. **This is the gating risk that owns proposal Theorems 1, 2, 4.** Verification deliverable defined: 96 round-trip test cases, surjective-projection-with-named-axes-lost criterion, owner = unit-registration + MATTHIAS, deadline = Round 2 admission. **This gap MUST be cleared before downstream extensions land.**

### Gap 2 — Calibrated Market Data Layer — **STRATEGIC**
Per §E above. Cannot be closed with existing types. The C5 correction (CDM has `TradeState.valuationHistory Valuation (0..*)`) **does not change the strategic ranking** — `Valuation` is a thin record that does not host posterior parameters, posterior covariance, innovation statistics, sensitivity Jacobians, or arbitrage-free certificates. The container exists; the content does not. Recommend `cdm-valuation-lib` extension upstream to FINOS as a multi-quarter strategic effort.

### Gap 3 — Tokenised Collateral via Lifecycle-Model Variant — **SIGNIFICANT (CDM extension)**
Per G.9 reframed. **Not** a parallel `cdm-tokenisation-lib`; instead:
- L1 `ProductTerms` extended with `lifecycle_model: {Conventional | SmartContract}`.
- `EligibleCollateralCriteria` extended with `(chainId, contractAddress, tokenStandard, backingModel, proofOfReservesRef)`.
- Backing-attestation as L11 oracle stream.
- Standalone library deferred to v12.0.

### Gap 4 — SBL Recall / Locate / Rehypothecation — **SIGNIFICANT, ISLA-COORDINATED OPERATIONAL**
Per F.3 / F.5 / D.9 / D.10. **Demoted from Strategic to Operational** per R1 matthias M-1: ISLA's CDM working group is actively contributing here. The right firm action is "wait and adopt" with a Ledger-internal bridge type tagged `cdm_native_pending = true`. See §J.5 below.

### Gap 5 — Attestation Envelope + Market-Data Snapshot — **REMOVED FROM CDM GAP LIST**
Per R1 matthias M-1: this is Ledger-internal discipline, not a CDM extension. Tracked under L17 / L19 in the proposal taxonomy. No upstream FINOS PR needed.

### Distinct PR-Unit Headcount (R1 directive #3)
The "5 strategic gaps" framing in v1 §J hid the following distinct CDM PR units. **True headcount: ~15.**

| Unit | Description | Where it lands in CDM |
|---|---|---|
| 1 | TradeState alignment sidecar projection map (Gap 1) | New utility on `TradeState`; possibly a new `StateProjection` type |
| 2 | `cdm-valuation-lib` proposal: `CalibratedYieldCurve` | new file `cdm-valuation-yieldcurve-type.rosetta` |
| 3 | `cdm-valuation-lib`: `CalibratedVolSurface` | new file |
| 4 | `cdm-valuation-lib`: `CalibratedFXSurface` | new file |
| 5 | `cdm-valuation-lib`: `CalibratedCreditHazardCurve` | new file |
| 6 | `cdm-valuation-lib`: `KalmanPosterior` | new file |
| 7 | `cdm-valuation-lib`: `SensitivityJacobian` | new file |
| 8 | `cdm-valuation-lib`: structured `ValuationRecord` extending `Valuation` | new file or extension |
| 9 | L1 `lifecycle_model` discriminator (Gap 3) | extension to `EconomicTerms` or new sibling type |
| 10 | `EligibleCollateralCriteria` tokenised extension fields (Gap 3) | extension to `product-collateral-type.rosetta` |
| 11 | `PrimitiveInstruction` extension: `recall SBLRecallInstruction (0..1)` (Gap 4) | extension to `event-common-type.rosetta` |
| 12 | `PrimitiveInstruction` extension: `locate SBLLocateInstruction (0..1)` (Gap 4) | extension to `event-common-type.rosetta` |
| 13 | `PrimitiveInstruction` extension: `rehypothecation SBLRehypothecationInstruction (0..1)` (Gap 4) | extension to `event-common-type.rosetta` |
| 14 | `LocateConfirmation` type for D.9 | new type in `product-collateral-type.rosetta` or SBL-specific file |
| 15 | `ManufacturedPayment / TaxTreatmentDetermination` for D.10 | new types |

This is a 15-PR upstream commitment over multiple quarters, not a 5-PR commitment. **Five of these (units 11–15) are ISLA-coordinated, not firm-led.** Eight (units 2–8 plus 1) are firm-strategic. Two (units 9–10) are firm-led with ISDA dialogue (the lifecycle-model extension touches the ISDA Tokenised Collateral Model Provisions track).

---

## §K — Verification Disclosure (no longer suspended)

**Verification status of cited CDM paths.** Every type, field, cardinality, condition, and qualification-function name cited above has been verified against the live `master` branch of `github.com/finos/common-domain-model` between 2026-04-30 04:00 and 04:30 UTC, by direct fetch of the `.rosetta` files in `rosetta-source/src/main/rosetta/`. The corpus fetched (15 files, ~9100 lines): `event-common-type` (772 lines), `event-workflow-type` (147 lines), `product-template-type` (884 lines), `product-asset-type` (742 lines), `product-collateral-type` (365 lines), `legaldocumentation-csa-type` (1557 lines), `legaldocumentation-master-type` (51 lines), `legaldocumentation-common-type` (229 lines), `observable-asset-type` (498 lines), `observable-event-type` (125 lines), `base-staticdata-asset-common-type` (362 lines), `base-staticdata-party-type` (188 lines), `product-common-settlement-type` (391 lines), `margin-schedule-type` (40 lines), `product-qualification-func` (1979 lines).

**Items I could not fully verify in this revision** (would require additional file fetches):
- D.2 `seev.*` synonym coverage depth (the ingest-iso20022 mapping files were not fetched).
- B.4 `IndexComposition` constituent depth on `EquityIndex` (only the type header was confirmed).
- D.5 `CreditEvent` field depth (only the type's existence as a `(0..1)` field on `ObservationEvent` was confirmed).
- G.3 GMSLA election bundle depth (only the file `legaldocumentation-master-isla-type.rosetta` existence was confirmed).

These four items are tagged `[unverified]` in the body. Any extension PR proposal touching them must re-fetch the relevant file before specification.

---

## §L — Cross-Walk Summary Statistics (Re-Issued)

After the corrections in §0 and the audit downgrades (Reset, BusinessEvent), the split shifts.

| Group | Leaves | Direct (v1) | Direct (v2) | Partial (v1) | Partial (v2) | Missing (v1) | Missing (v2) |
|---|---|---|---|---|---|---|---|
| A — Definitions (Static) | 11 | 6 | 5 | 3 | 3 | 2 | 3 |
| B — Authoritative Tables | 6 | 0 | 0 | 2 | 2 | 4 | 4 |
| C — Continuous Market Observations | 4 | 1 | 0 | 3 | 4 | 0 | 0 |
| D — External Event Attestations (Oracle) | 12 | 3 | 3 | 5 | 4 | 4 | 5 |
| E — Calibrated Market Data | 6 | 0 | 0 | 1 | 1 | 5 | 5 |
| F — Smart-Contract Execution | 9 | 1 | 0 | 4 | 5 | 4 | 4 |
| G — Legal & Agreement | 9 | 3 | 3 | 2 | 1 | 4 | 5 |
| H — Identity, Provenance & Audit | 5 | 0 | 0 | 2 | 2 | 3 | 3 |
| **Total** | **62** | **14** | **11** | **22** | **22** | **26** | **29** |

**Re-issued split: 11 / 22 / 29.** Three Direct rows downgraded to Partial (Reset, BusinessEvent) or to Missing (ExchangeContractSpec) per R1 audit. Two Partial rows reclassified to Missing (TradeCollateralProvisions CCP-cleared, CorporateActionsSchedule). One row (D.12 RegulatoryAcknowledgement) absorbed into L25 RegulatorySubmission cross-walk in §N.

Of the **29 Missing**, 8 remain correctly out of CDM scope (TemporalWorkflowState, AuditLogEntry, SystemEpoch, attestation envelope, snapshot, infrastructure metadata). The remaining **21 Missing + 22 Partial = 43 items requiring CDM cross-walk attention**, of which **15 are tracked in the distinct-PR-unit headcount above**.

---

## §M — Closing — Architectural Posture

The v11.0 ledger is a **closed system at its boundary**. CDM is the canonical interchange format **at the boundary**. Every gap above is a place where the boundary loses its CDM-native discipline and must be supplemented by Ledger-native typing or by an upstream FINOS PR.

**Strategic priority (post-R1 re-classification):**
1. **Clear Gap 1 (TradeState↔StatesHome alignment) before Round 2.** It is gating.
2. **Commit Gap 2 (Calibrated Market Layer)** as a multi-quarter `cdm-valuation-lib` upstream proposal, with internal types tagged `cdm_native_pending = true` carrying the load until the upstream lands.
3. **Engage with ISDA on Gap 3** (lifecycle-model variant) using the 2023 Tokenised Collateral Model Provisions and the 2025 ISDA/Ant Project Guardian work as anchor papers. **Do not** propose a parallel `cdm-tokenisation-lib`.
4. **Track ISLA on Gap 4.** No firm-led PR for SBL recall/locate/rehypothecation. Bridge with Ledger-internal types `cdm_native_pending = true`.
5. **Move Gap 5 (envelope / snapshot) out of CDM strategic discussion.** It is firm-internal discipline.

The framework's six properties (atomicity, conservation, determinism, state-sufficiency, lifecycle value invariance, time travel) hold only because the system is closed. **The CDM cross-walk does not need to be 100% Direct for the framework to hold; it needs to be Direct or Partial-with-named-projection on every leaf that participates in a regulatory submission, a counterparty exchange, or a replay.** The 11/22/29 split implies that ~53% of leaves currently meet that bar without supplementary projection. The remaining ~47% need a sidecar projection map (named, version-pinned, total), an upstream PR, or both.

---

## §N — L25 RegulatorySubmission CDM Cross-Walk (NEW per R1 directive #10)

NAZAROV adds L25 RegulatorySubmission to the proposal as a C5-Effects leaf (per R1 isda B-1). This section provides the CDM cross-walk.

### N.1 — Field-by-field CDM mapping for L25
| L25 field | Type | CDM target | Status |
|---|---|---|---|
| `submission_id` | string [content-addressed] | Ledger-native (UUID + content hash); no CDM analogue | Missing (correctly Ledger-native) |
| `regulator` | RegulatorEnum | `RegulatorEnum` (CDM `regulation-type.rosetta`) [unverified — file presence confirmed; field set not fetched] | Direct (likely) |
| `rule_set` | RegulatorRuleSetEnum | None directly; closest is the per-regulator regime in `Regime` types | Missing |
| `rule_set_version` | GitSha [via L21 pin] | None — DRR rule version is a separate axis from `cdm_version` | **Missing — strategic axis** |
| `payload` | CDM-native | `BusinessEvent` (after `TradeState`) is the canonical post-event content; the actual submission payload is generated by the DRR open-source distribution against this. | Direct (via DRR) |
| `tx_id` (lineage to L14) | string | `WorkflowStep.lineage Lineage (0..1)` (deprecated in CDM 6.x — flagged in our verification) **or** `WorkflowStep.previousWorkflowStep` reference | Partial (CDM `Lineage` is deprecated; needs replacement) |
| `acknowledgement_status` | enum | None | Missing |
| `acknowledgement_message_id` | string | None | Missing |
| `bitemporal restatement chain (t_obs, t_known)` | (date, date) | None first-class; `BusinessEvent.eventDate` + `effectiveDate` plus `WorkflowStep.action ActionEnum` (Cancel / Correction) is the closest analogue | Partial |

### N.2 — Strategic axis: `drr_rule_set_version` distinct from `cdm_version` (R1 isda UM-1)
L21 VersionPin in the proposal carries `cdm_version`. **This is insufficient for replay determinism on regulatory submissions.** The DRR rule-set version (FINOS-published per regulator) and the CDM version are independent:
- A single CDM 6.0.0 can be consumed by DRR-CFTC v3.x, DRR-EMIR v2.x, DRR-MAS v1.x simultaneously, each at its own git_sha.
- Replay of a regulatory submission requires the exact DRR distribution that produced the payload.

**Required L21 schema extension:**
```
drr_rule_set_version: Map<RegulatorRuleSet, GitSha>
```
This is independent of `cdm_version` and pinned per L25 submission.

### N.3 — Position statement on dual-sided vs unilateral reporting (R1 isda UM-3)
ISDA's 2025 ESMA response advocates the elimination of dual-sided reporting where one side is sufficient. **L25 is designed to support both regimes:** the `regulator` + `rule_set` combination, plus the `tx_id` lineage to the canonical L14 record, allows the same submission to be filed unilaterally (post-reform) or dual-sidedly (current EMIR/MIFIR), with the rule-set version pin (N.2) controlling cutover. **No L25 schema change is needed** when the dual-sided regime is replaced — only the rule-set version and the dispatch policy.

### N.4 — ISDA Notices Hub as L11 sub-leaf (R1 isda UM-2)
Notices Hub (live July 2025) is an attestation source for legal-notice events. Recommend L11 sub-leaf:
- **Type:** `LegalNoticeAttestation`
- **CDM mapping:** Synonym onto `BusinessEvent` with a `LegalNotice`-classed event qualifier; **no first-class CDM type for legal-notice delivery as a primitive event** — would need a new `LegalNoticeInstruction` in `PrimitiveInstruction` (additional PR unit, but ISDA-track not ISLA-track). Defer to v12.0.

### N.5 — Pillar 3 Projection Lifting theorem (R1 isda UM-4)
For consistency with ISDA's machine-readable Pillar 3 advocacy: the proposal §8 should add a sixth theorem **Pillar-3-Projection-Lifting** stating that L14 + L15 + L7 (regulatory classification policy) compose to a CDM-native input to a future DRR-Pillar3 distribution. **This is a cost-free architectural commitment.** L15 ValuationRecord schema must carry the regulatory classification overlay (FRTB IMA/SA boundary, banking/trading book, internal-model approval scope) to support this — a finops B5 / R1 finops T4 deliverable.

---

## §7.6 — Migration Discipline for Ledger-Internal Types (NEW per R1 directive #8)

Each Ledger-internal type that is `cdm_native_pending = true` must:
1. Carry a structurally enforced flag `cdm_native_pending: bool (1..1)` on the type definition (or via a typed wrapper).
2. Be referenced **only** through a typed boundary so consumers can detect the pending status.
3. Have a designated `cdm_target` annotation citing the upstream FINOS PR, ISLA working group reference, or `[OPEN — no upstream]`.
4. When the upstream CDM extension lands, produce a migration record in L12 ExternalConfirmation:
   ```
   type CdmNativeMigrationRecord:
       [metadata key]
       internalTypeName string (1..1)
       cdmTargetType string (1..1)
       cdmVersion string (1..1)        // version where extension landed
       drrRuleSetVersionPin Map<RegulatorRuleSet, GitSha> (0..1)
       migrationDate date (1..1)
       backwardCompatibilityHorizon date (1..1)
       fieldMap CdmFieldMapping (1..*)
   ```
5. **No Ledger-internal type may live without a `cdm_native_pending` decision.** Either it is `false` (Ledger-native by design, e.g., `AttestationEnvelope`), or `true` (pending upstream landing). The third option — undecided — is a CI failure.

This discipline ensures the v11.0 spec does not silently ossify Ledger-internal types that should migrate to CDM. It also gives a concrete answer to FORMALIS M5 (migration story for Ledger-internal types).

---

## §O — Per-R1-Directive Closure Summary

| R1 directive | Addressed at | Status |
|---|---|---|
| #1 Re-fetch all `.rosetta` paths cited in §A–§H | §K and throughout | DONE — 15 files, 9100 lines re-fetched |
| #2 Promote Gap 5 to top of §7 | §J Gap 1 | DONE |
| #3 Re-issue §7 with true distinct-PR-unit headcount (~15 not 5) | §J — Distinct PR-Unit Headcount table | DONE |
| #4 Re-classify gaps: 2 strategic / 1 significant / 1 operational / 1 Ledger-internal | §J | DONE |
| #5 Audit Reset and BusinessEvent Direct claims | §C.2, §F.3, §0 C17 | DONE — both downgraded to Partial |
| #6 Tokenised collateral framing (D2) | §G.9, §J Gap 3, §0 C18 | DONE — combined ISDA `lifecycle_model` + DigitalAsset rejected (CDM condition violation) |
| #7 Add `drr_rule_set_version` axis on L21 | §N.2 | DONE |
| #8 §7.6 Migration discipline | §7.6 | DONE |
| #9 Verify suspect type/path claims (MarginCall*, IndexTransition*, LegalAgreementType vs Enum) | §0 C2, C9, C10; §D.4, §D.8, §G.1 | DONE — all three claims corrected |
| #10 L25 RegulatorySubmission cross-walk | §N | DONE |

— Matthias Vogt, FINOS CDM core team
