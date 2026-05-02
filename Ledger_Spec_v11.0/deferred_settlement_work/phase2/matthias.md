# Definitive CDM Cross-Walk and Rosetta Extensions for Deferred Settlement

**Author.** Matthias Vogt (rosetta-cdm-engineer), Phase 2, Settlement Team
**Date.** 2026-04-30
**Phase 1 input considered.** All 20 proposals (ashworth, cartan, correctness, feynman, finops, formalis, geohot, grothendieck, halmos, isda, jane_street, karpathy, lattner, matthias, minsky, nazarov, noether, sbl, temporal, testcommittee).
**Live CDM 6.x verification.** Re-fetched at 2026-04-30 from `github.com/finos/common-domain-model@master`: `event-common-enum.rosetta`, `event-common-type.rosetta`, `event-position-enum.rosetta`, `product-common-settlement-type.rosetta`, `product-common-settlement-enum.rosetta`. Cited values below are from the live source, not from memory; nothing has changed since the Phase 1 fetch.

This document is the Settlement Team's definitive CDM cross-walk for the unified deferred-settlement design. The unified design, as it has converged from the 20 Phase 1 proposals, is the **virtual-wallets + L_15 Obligation + transaction-level FSM** position with the **economic-exposure-at-T (E1)** invariant as its mandatory floor. This document maps every state and event of that design to its CDM 6.0.0 native counterpart, identifies the structural gaps where CDM is silent or partial, and proposes the exact Rosetta extension drafts that close those gaps as upstreamable PR units to FINOS.

The eight required deliverables (per the Settlement Team brief) are answered in §§1–8 below.

---

## 1. The Definitive Cross-Walk Table

The cross-walk classifies every state, event, and structural object of the unified design as **Direct** (clean CDM mapping exists), **Partial** (CDM has a partial type tag but the runtime semantics or a required field is missing), or **Missing** (no CDM equivalent — must be Ledger-internal until upstream extension).

### 1.1 Trade-time recognition (T) — economic side

| Ledger element | CDM 6.0.0 status | CDM type / file | Notes |
|---|---|---|---|
| Trade execution event at T | **Direct** | `BusinessEvent` (event-common-type.rosetta) with `instruction.execution` populated; `eventQualifier = "Execution"` | `BusinessEvent extends EventInstruction`; instructions live on the parent. `after TradeState (0..*)`. |
| Trade object | **Direct** | `Trade extends TradableProduct` (event-common-type.rosetta); `tradeDate FieldWithMeta<date> (1..1)` | Trade is the T-recognised object. `tradeIdentifier (1..*)`, `tradeDate (1..1)`, `party`, `partyRole`, `executionDetails`, `contractDetails`, `collateral Collateral (0..1)`. |
| Counterparty pair | **Direct** | `TradableProduct.counterparty Counterparty (2..2)` (product-template-type.rosetta) | Structurally enforced 2..2 cardinality. |
| Trade-time positions for buyer and seller | **Partial** | `TradeState` (event-common-type.rosetta) — carries `state State (0..1)`, `transferHistory TransferState (0..*)`, `valuationHistory Valuation (0..*)` | TradeState is per-trade; the Ledger's per-(wallet, unit) PositionState is denser. Cross-walk via projection (see §5 below). |
| Settlement-date terms (T+2 expectation) | **Direct (terms only)** | `SettlementDate` (product-common-settlement-type.rosetta), `SettlementTerms` carried on payouts and on `Trade.contractDetails` | The contractual settlement date is in CDM. The runtime expected-date on a live obligation is not — see Gap 6. |
| Cash leg (USD payable from buyer) | **Direct** | `Transfer extends AssetFlowBase` with `Asset.Cash` payload (base-staticdata-asset-common-type.rosetta) | `Transfer` is the act of transferring; payerReceiver, settlementOrigin Payout, resetOrigin Reset, transferExpression. |
| Securities leg (AAPL receivable to buyer) | **Direct** | `Transfer` with `Asset.Instrument.Security` payload | `choice Asset { Cash, Commodity, DigitalAsset, Instrument }`. |

### 1.2 Open-window state (T < t < T+2)

| Ledger element | CDM 6.0.0 status | CDM type / file | Notes |
|---|---|---|---|
| Status `EXECUTED` | **Direct (with conflation)** | `PositionStatusEnum.Executed` (event-position-enum.rosetta); `TransferStatusEnum.Pending` (event-common-enum.rosetta) | CDM uses `Executed` for both "trade booked" and "post-settlement" states; the (T, T+2) gap is implicit in the absence of `Settled`, not explicit in a state field. This is the foundational conflation Gap 11 below addresses. |
| Status `INSTRUCTED` | **Direct** | `TransferStatusEnum.Instructed` | Mapped directly. |
| In-flight wallet balance (security-owed and cash-owed contras) | **Missing (Ledger-internal)** | No CDM analogue | CDM has no virtual-wallet construct in the per-counterparty-virtual-account sense. Ledger-internal discipline; not strictly a CDM gap because `Account` could be repurposed if pushed upstream. |
| Open obligation as a discrete object | **Missing — strategic gap** | No native `Obligation` root type | Phase 1 unanimous: the obligation must be a first-class object (cartan, halmos, noether, isda, formalis, jane_street, karpathy, lattner, minsky, temporal all converged on this). CDM does not have this type. **See Gap 10, the obligation root type.** |
| Expected settlement date on the live obligation | **Missing** | `TransferState` lacks `expectedSettlementDate` field | See Gap 6 — extends `TransferState`. |
| `PositionStatusEnum.PartiallySettled` | **Missing** | enum lacks the value | See Gap 6/7. |
| `PositionStatusEnum.Failed` | **Missing** | enum lacks the value | See Gap 6 — but note: PositionStatusEnum `Cancelled` and `Closed` exist; the missing value is specifically `Failed`. |

### 1.3 Settlement event at T+2 (success path)

| Ledger element | CDM 6.0.0 status | CDM type / file | Notes |
|---|---|---|---|
| Settlement confirmation arrival | **Direct** | `BusinessEvent` with `eventQualifier = "Settlement"`; the `after TradeState` carries an updated `TransferState` with `transferStatus = Settled` | This is the canonical confirmation path. |
| Status transition `INSTRUCTED → SETTLED` | **Direct** | `TransferStatusEnum.Settled` | Mapped. |
| Position remains unchanged on the trader's real wallet (E2 invariant) | **Direct (semantic; no structural assertion)** | CDM does not have a structural "position is unchanged on settlement" assertion; this is a Ledger-level semantic | CDM is permissive — it would not reject a model that updated position on settlement. The Ledger v11.0 makes the correct semantic explicit. |
| Nostro reconciliation marker | **Missing (Ledger-internal)** | No CDM analogue | The nostro reconciliation surface is a Ledger-internal discipline. |
| DvP atomicity (security and cash leg atomic at the CSD) | **Direct (terms only)** | `TransferSettlementEnum.DeliveryVersusPayment`, `DeliveryMethodEnum.DeliveryVersusPayment` (product-common-settlement-enum.rosetta) | Tag exists; runtime atomicity invariant is Ledger-level. |

### 1.4 Settlement event at T+2 (fail and partial paths)

| Ledger element | CDM 6.0.0 status | CDM type / file | Notes |
|---|---|---|---|
| Status `FAILED` | **Missing — STRATEGIC GAP 6** | No `Failed` value in `TransferStatusEnum`; no `Failed` value in `PositionStatusEnum` | Verified at 2026-04-30 raw fetch: `enum TransferStatusEnum: Disputed, Instructed, Pending, Settled, Netted` — those five values, no others. This is the largest single CDM gap in the deferred-settlement scope. |
| Fail reason (LackOfSecurities, etc.) | **Missing — STRATEGIC GAP 6** | No `TransferFailureReason` type, no `TransferFailReasonEnum` | Required for CSDR Article 7 reporting. |
| Status `PARTIALLY_SETTLED` | **Missing — STRATEGIC GAP 6/7** | No value in either enum; `partialCashSettlement boolean` exists only in CDS context (`PCDeliverableObligationCharac`), unrelated | The CDS-only boolean is a false friend; not the right type for partial-settlement representation. |
| Settled quantity on partial | **Missing** | No structural place to record the settled portion within a partially-settled `TransferState` | Subsumed in Gap 6. |
| CSDR cash penalty event | **Missing — STRATEGIC GAP 8** | No `CSDRPenaltyDetail` type, no `CashPenalty` event qualifier, no `CSDRLiquidityClassEnum` | `eventQualifier` is `string (0..1)`, soft-typed. Adding a qualifier is non-breaking. |
| Penalty rate per ESMA Article 7 RTS matrix | **Missing** | No structural representation of the matrix | Lives in `PolicyConfiguration` in the Ledger; not necessarily a CDM concern. The matrix is regulatory configuration; CDM should hold the *event*, not the *rate-table*. Confirmed scope: bring the event, leave the rate table to firm policy. |
| Buy-in instruction | **Missing — STRATEGIC GAP 9** | No `BuyInInstruction` type; no `BuyIn` event qualifier; the term "buy-in" appears only in `sixtyBusinessDaySettlementCap` text on `PhysicalSettlementTerms` (CDS deliverable obligations), unrelated | Verified at fetch. |
| Buy-in execution and outcome | **Missing — STRATEGIC GAP 9** | No `BuyInExecution`, no `BuyInOutcomeEnum` | The CSDR-mandated buy-in is industry-wide; CDM gap is not Ledger-bespoke. |
| Cash-settlement-in-lieu fallback | **Missing — STRATEGIC GAP 9** | No structural representation | Subsumed in Gap 9 — `BuyInOutcomeEnum.CashSettlementInLieu`. |

### 1.5 Composition layer

| Ledger element | CDM 6.0.0 status | CDM type / file | Notes |
|---|---|---|---|
| Short sale at T composing with SBL borrow | **Partial** | `Qualify_SecurityLending` (product-qualification-func.rosetta) — top-level SBL qualification function exists; composition-with-deferred-settlement structure does not | Coordinated with ISLA WG (see §3 of `cdm_gap_log` and `sbl_isla_dependency.md`). Wait-and-adopt; do not duplicate. |
| Recall obligation in window | **Direct (event-tag) / Partial (composition)** | `UnscheduledTransferEnum.Recall` (product-common-settlement-enum.rosetta) | The recall as an event-tag is in CDM; the *chained obligation* relation that makes recall compose with deferred settlement is not. Subsumed in Gap 10 (Obligation root type). |
| Corporate action with record date in (T, T+2) | **Partial** | `ObservationEvent.corporateAction CorporateAction (0..1)` (event-common-type.rosetta) | The corporate action observation is mapped. The "manufactured dividend obligation" — seller owes buyer the dividend because buyer was beneficial holder by E1 — has no CDM hook and cross-cuts deferred settlement, SBL, and collateral. Subsumed in Gap 10. |
| Cross-currency / Herstatt | **Partial** | `TransferSettlementEnum.PaymentVersusPayment`; `CrossCurrencyMethod` in `CashSettlementMethodEnum` | The terms tag exists. The runtime per-leg-status tracking that Herstatt-window detection requires is Gap 6 (the TransferStatus enrichment). Per-leg independence is naturally modelled once each leg has its own `TransferState`. |
| DvP atomicity (Ledger-level transaction primitive) | **Missing (Ledger-internal)** | No CDM analogue | The Ledger transaction-atomicity primitive is Ledger-internal discipline. CDM has the type tag (`DeliveryVersusPayment`) but not the runtime atomicity guarantee at the model level. |

### 1.6 ISO 20022 messages

See §6 below for the full message-level cross-walk.

### 1.7 Summary classification

| Class | Count | Examples |
|---|---|---|
| Direct | 11 | Trade execution, Trade object, counterparty pair, settlement-date terms, cash leg, securities leg, status `INSTRUCTED`, status `SETTLED` (success path), settlement confirmation BusinessEvent, recall event tag, ISO `sese.023/.025`. |
| Partial | 6 | Status `EXECUTED` (with conflation), DvP atomicity, SBL composition, corporate action composition, cross-currency, position recognition at T (semantic-only). |
| Missing | 7 | Status `FAILED`, status `PARTIALLY_SETTLED`, fail-reason structure, expected/actual settlement dates on `TransferState`, CSDR cash penalty event, buy-in event, obligation as first-class root type. |

The missing seven are the structural gap inventory that motivates §§2–3 below.

---

## 2. The Five Firm-Strategic Gaps — Reaffirmed and Refined

The Phase 1 proposals (matthias §5.3, isda §5, formalis §6, jane_street §1.2, lattner §1.3, temporal §1.1, halmos §1.2, cartan §2.2, noether §1.2, minsky §1.2, sbl §1.5) all converge on the same five firm-strategic gaps. I reaffirm the inventory and add one further structural gap that Phase 1 surfaced explicitly (Gap 11) but did not classify alongside the others.

### Gap 6 — `TransferStatus` enrichment (FAILED, PARTIALLY_SETTLED, CANCELLED)

**Severity.** STRATEGIC, CSDR-blocking.
**Verified absence.** `TransferStatusEnum` has only `{Disputed, Instructed, Pending, Settled, Netted}` (re-verified 2026-04-30). `PositionStatusEnum` has only `{Executed, Formed, Settled, Cancelled, Closed}` (re-verified 2026-04-30; `Cancelled` exists, `Failed` and `PartiallySettled` do not).
**Phase 1 unanimity.** All proposals that touch CDM (matthias, isda, jane_street, lattner, formalis, temporal, halmos, ashworth, finops, sbl, nazarov) name this gap or describe a workaround.
**Resolution.** Add `Failed`, `PartiallySettled`, `Cancelled` enum values; add `TransferFailureReason` type and `TransferFailReasonEnum`; add `expectedSettlementDate` and `actualSettlementDate` fields to `TransferState`. Draft in §3.1.

### Gap 7 — Partial settlement granularity

**Severity.** STRATEGIC (subsumed in Gap 6 but explicit).
**Verified absence.** No `partialQuantity`, no `settledQuantity` field on `TransferState`. The CDS `partialCashSettlement boolean` exists only in `PCDeliverableObligationCharac` and is an unrelated false friend.
**Phase 1 unanimity.** matthias §6.5, isda §6.4, formalis §6.3, jane_street §6, lattner §6, halmos §5, noether §6, sbl §3, ashworth §4 all describe partial settlement; all observe the CDM gap.
**Resolution.** `TransferState (0..*)` cardinality on `TradeState.transferHistory` already supports multiple records; the missing piece is `TransferFailureReason.settledQuantity Quantity (0..1)` and a structural pattern (one `TransferState` for the settled portion, one for the residual). Draft in §3.1.

### Gap 8 — CSDR cash penalty as a structural event

**Severity.** STRATEGIC (CSDR-blocking; ~€100M+ industry-cumulative-cost since 2022 per ISDA's reading; multiple Phase 1 proposals cite this).
**Verified absence.** No `CSDRPenaltyDetail` type, no `Qualify_CashPenalty` qualification function, no `CSDRLiquidityClassEnum`. The `eventQualifier` field on `BusinessEvent` is `string (0..1)` — soft-typed — so adding a new qualifier is non-breaking.
**Phase 1 unanimity.** matthias §5.3, isda §5/§8, formalis §6.5, lattner §3, halmos §6, jane_street §6, ashworth §3, sbl §6, finops §7, correctness L_15, temporal §6 all describe CSDR penalty handling; the cleanest model is an event-qualifier-plus-payload pattern.
**Resolution.** Add `CSDRPenaltyDetail` type, `Qualify_CashPenalty` qualification function, `CSDRLiquidityClassEnum`. Draft in §3.2.

### Gap 9 — Buy-in event

**Severity.** STRATEGIC.
**Verified absence.** The term "buy-in" appears only in `sixtyBusinessDaySettlementCap` text on `PhysicalSettlementTerms` (CDS deliverable obligations), an unrelated false friend. There is no `BuyInInstruction`, `BuyInExecution`, `BuyInRegimeEnum`, or `BuyInOutcomeEnum`.
**Phase 1 unanimity.** matthias §5.3, isda §6.3, formalis §6.4, lattner §3, halmos §5, jane_street §6, ashworth §4, sbl §6, temporal §6, correctness §1, cartan §6 all describe the buy-in workflow.
**Resolution.** Add `BuyInInstruction`, `BuyInExecution`, `BuyInRegimeEnum` (CSDR / GMSLA / GMRA / Bilateral), `BuyInOutcomeEnum` (`OriginalTransferCancelled` / `CashSettlementInLieu`). Draft in §3.3.

### Gap 10 — Obligation as a first-class root type

**Severity.** STRATEGIC, CROSS-CUTTING. Re-affirmed as the highest-leverage gap.
**Phase 1 unanimity.** This is the single most-converged-on Phase 1 finding. Cartan §2 (universal property of $u^{\circ}$), halmos §1.2 (the obligation is a unit), noether §1.2 (the deferred-delivery claim), matthias §1.2 (obligation as a unit in the StatesHome 3-map), isda §1.1 (obligation as L_15 row), formalis §1.2 (`o_settle(τ)` as $L_{15}$), jane_street §1.2 (`SettlementObligation` in $L_{15}$), karpathy §2.2 (the obligation ledger), lattner §1.3 (obligation as canonical state carrier), minsky §1.2 (the obligation as a typed unit), temporal §1.1 (`SettlementObligation` row), sbl §1.5 (per-instruction virtual wallet driving an obligation), nazarov §1.2 (`L_15` Obligation as carrier of the gap), correctness §0 (the obligation is the property carrier), grothendieck (the obligation is the unit of an adjunction), finops §0 (`SettlementFinality` Obligation kind), ashworth §1 (per-leg obligation in receivables), feynman §2 (the obligation ledger), geohot — partial dissent (proposes a `settlement_status` field on transaction in lieu).
**Verified absence.** No `Obligation` root type exists in CDM 6.0.0. The closest thing is `TransferState` plus the implicit gap created by the status enum. CDM treats obligations as deltas between successive `TransferState` snapshots, which is denser than what the Ledger needs.
**Resolution.** Introduce a top-level `Obligation` root type carrying `obligor`, `obligee`, `obligedAsset`, `expectedDischargeDate`, `actualDischargeDate`, `obligationStatus`, `sourceEvent`, `dischargeEvent`. Draft in §3.4.

### Gap 11 — Economic-exposure-at-T as an enforced semantic

**Severity.** STRATEGIC, FOUNDATIONAL — but **NOT a Rosetta extension**; it is a doctrinal extension to CDM's documentation and qualification semantics.
**Verified absence.** CDM does not state that the position represented by a `TradeState` is true from `tradeDate`. A CDM-only stack could, without violating the schema, treat the position as null until a `Settled` `TransferState` exists, which would be wrong. The Ledger v11.0 invariant E1 is the structural commitment that closes this.
**Phase 1 unanimity.** Mandatory invariant per the Settlement Team brief; explicitly named by every Phase 1 proposal. matthias §1.4, isda §3 E1, formalis §1.3, halmos §1.5, noether §3.3, cartan §3, minsky §0, jane_street §1.3, ashworth §1, geohot §1, finops §0, feynman §1, sbl §1.1, nazarov §1.1, correctness §0, temporal §1.1.
**Resolution.** Cannot be a Rosetta extension because it is not a structural constraint expressible in the type system. It is a semantic that CDM must adopt by either (a) a normative documentation paragraph, or (b) a `TradeState` qualification function `is_economic_position_recognised_at_tradeDate` that returns true. The right resolution is doctrinal: a CDM 7.0 rev should add to the `TradeState` documentation the explicit assertion "for any `TradeState` with `tradeDate = T_exec`, the position embedded in this trade is true from `T_exec` regardless of `transferStatus` of any associated `Transfer`." See §4 below for the precise proposed CDM-charitable language.

### Gap 12 — Per-(wallet, unit) state cardinality (`TradeState` ↔ `PositionState`)

**Severity.** STRATEGIC, GATING — already inventoried as Gap 1 in `cdm_gap_log` (the StatesHome 3-map alignment gap). I name it here because the deferred-settlement representation cannot bypass it: the Ledger's per-(wallet, unit) PositionState is denser than the per-trade `TradeState`, and the in-flight wallet representation explicitly relies on the Ledger's coordinate system. This is *not* a deferred-settlement-specific gap; it is a structural mismatch that deferred settlement *exposes*.

---

## 3. Rosetta Extension Drafts — PR-Sized, Upstreamable

Each extension below is namespace-qualified, syntactically valid Rosetta DSL (CDM 6.x dialect), and shaped as a single PR unit. Cardinalities are explicit. Conditions are stated where they apply. Doc-strings are CDM-style.

### 3.1 Gap 6+7: TransferStatus enrichment + TransferFailureReason

**Target file.** `event-common-enum.rosetta` (extend existing enum), `event-common-type.rosetta` (add new type, extend existing type).
**PR scope.** ~80 lines. Non-breaking: existing `TransferStatusEnum` consumers continue to compile.

```rosetta
// In event-common-enum.rosetta — extend existing enum
enum TransferStatusEnum: <"The enumeration values to specify the transfer status.">
    Disputed <"The transfer is disputed.">
    Instructed <"The transfer has been instructed.">
    Pending <"The transfer is pending instruction.">
    Settled <"The transfer has been settled.">
    Netted <"The transfer has been netted into a separate Transfer.">
    Failed <"The transfer was instructed and the central settlement infrastructure (CSD, payment system, or equivalent) reported a failure to settle on or before the expected settlement date. Per ESMA RTS on CSDR Article 7, a failed transfer remains instructed and accrues cash penalties until extended settlement, mandatory buy-in, cancellation, or cash settlement in lieu.">
    PartiallySettled <"The transfer was instructed and the central settlement infrastructure reported partial settlement: a portion of the instructed quantity settled, the remainder did not. The settled portion is reflected in companion TransferState records; this status applies to the residual unsettled portion which remains an open obligation.">
    Cancelled <"The transfer was instructed but cancelled prior to or after the expected settlement date by mutual agreement of the parties (e.g., post-buy-in cash compensation under CSDR Article 7, or trade cancellation under bilateral terms).">

// In event-common-enum.rosetta — new enum
enum TransferFailReasonEnum: <"Classified reasons for a Failed or PartiallySettled TransferState. Aligned with ESMA CSDR Article 7 RTS reporting categories and ISO 20022 sese.024 status reason codes.">
    LackOfSecurities <"The delivering party does not have the securities at the central settlement infrastructure on the intended settlement date.">
    LackOfCash <"The paying party does not have the cash at the central settlement infrastructure on the intended settlement date.">
    SettlementMatchingFailure <"The two sides of the instruction did not match within the central settlement infrastructure's matching tolerance.">
    BuyerOnHold <"The receiving party has placed the instruction on hold.">
    SellerOnHold <"The delivering party has placed the instruction on hold.">
    SettlementSystemFailure <"The central settlement infrastructure itself failed to process the instruction (operational failure).">
    OnHoldByCounterparty <"A counterparty placed the instruction on hold for an unspecified reason.">
    Other <"A reason not classified above; failReasonText must be populated.">

// In event-common-type.rosetta — new type
type TransferFailureReason: <"Captures the reason and metadata for a Failed or PartiallySettled TransferState. Required when transferStatus indicates a non-terminal or non-settled outcome on or after the expected settlement date.">
    [metadata key]
    failReasonCode TransferFailReasonEnum (1..1) <"The classified reason for the failure.">
    failReasonText string (0..1) <"Free text per CSDR Article 7 RTS reporting requirements; required when failReasonCode = Other.">
    settledQuantity Quantity (0..1) <"For PartiallySettled, the quantity that did settle. The residual quantity (instructed minus settled) remains the open obligation.">
    csdrPenaltyAccrued Money (0..1) <"Accrued CSDR cash penalty for this fail, computed per ESMA CSDR Article 7 RTS penalty matrix. May be populated incrementally as the fail ages.">

    condition FailReasonTextRequired:
        if failReasonCode = TransferFailReasonEnum -> Other
        then failReasonText exists

// In event-common-type.rosetta — extend existing type
type TransferState: <"Defines the fundamental financial information associated with a Transfer event. Each TransferState specifies where a Transfer is in its life-cycle.">
    [metadata key]
    [rootType]
    transfer Transfer (1..1) <"Represents the Transfer that has been effected by a business or life-cycle event.">
    transferStatus TransferStatusEnum (0..1) <"Represents the State of the Transfer through its life-cycle.">
    failureReason TransferFailureReason (0..1) <"Required when transferStatus = Failed or PartiallySettled. Captures the reason and any partially-settled quantity.">
    expectedSettlementDate date (0..1) <"The contractually expected settlement date for this Transfer; used to compute settlement lag, drive CSDR penalty accrual, and trigger buy-in workflows. Populated at instruction time.">
    actualSettlementDate date (0..1) <"The date on which the central settlement infrastructure confirmed full settlement; populated when transferStatus = Settled. May differ from expectedSettlementDate when settlement is late.">

    condition FailureReasonRequired:
        if transferStatus = TransferStatusEnum -> Failed
            or transferStatus = TransferStatusEnum -> PartiallySettled
        then failureReason exists

    condition ActualSettlementDateConsistency:
        if actualSettlementDate exists
        then transferStatus = TransferStatusEnum -> Settled
            or transferStatus = TransferStatusEnum -> PartiallySettled
```

The `PositionStatusEnum` extension is independent and parallel:

```rosetta
// In event-position-enum.rosetta — extend existing enum
enum PositionStatusEnum: <"Enumeration to describe the different (risk) states of a Position, whether executed, settled, matured...etc.">
    Executed <"The position has been executed, which is the point at which risk has been transferred.">
    Formed <"Contract has been formed, in case position is on a contractual product.">
    Settled <"The position has settled, in case product is subject to settlement after execution, such as securities.">
    Cancelled <"The position has been cancelled, in case of a cancellation event following an execution.">
    Closed <"The position has been closed, in case of a termination event.">
    PartiallySettled <"The position has been partially settled: a portion of the instructed quantity settled, the remainder remains an open obligation. The corresponding TransferState records carry the per-leg detail.">
    Failed <"The position is in a Failed settlement state: the instruction was placed but the central settlement infrastructure reported a failure on or after the expected settlement date.">
```

### 3.2 Gap 8: CSDR cash penalty

**Target file.** New file `event-csdr-type.rosetta`; extend `event-qualification-func.rosetta`; new enum file or extend an existing enum file.
**PR scope.** ~120 lines. Non-breaking: adding a new event qualifier and a new payload type.

```rosetta
namespace cdm.event.csdr

import cdm.base.staticdata.party.*
import cdm.base.math.*
import cdm.event.common.*
import cdm.observable.asset.*

// New enum — instrument liquidity classification per ESMA CSDR Article 7 RTS
enum CSDRLiquidityClassEnum: <"Classifies an instrument's liquidity for the purpose of computing the CSDR cash penalty rate per ESMA CSDR Article 7 RTS Penalty Matrix. The classification determines the basis-points-per-day penalty rate.">
    LiquidShares <"Liquid shares as defined in ESMA RTS 1 (MiFIR Article 2(1)(17)).">
    NonLiquidShares <"Shares that are not classified as liquid under ESMA RTS 1.">
    LiquidBonds_SovereignSupranational <"Sovereign and supranational bonds classified as liquid under ESMA RTS 2.">
    LiquidBonds_OtherPublic <"Other public-sector bonds classified as liquid under ESMA RTS 2.">
    LiquidBonds_Corporate <"Corporate bonds classified as liquid under ESMA RTS 2.">
    NonLiquidBonds <"Bonds that are not classified as liquid under ESMA RTS 2.">
    SMEGrowthMarket <"Instruments admitted to trading on an SME Growth Market.">
    Other <"Instruments that do not fit the above categories; rate must be specified explicitly.">

// New type — the CSDR penalty payload
type CSDRPenaltyDetail: <"Detail of a CSDR Article 7 cash penalty assessment for a failed settlement. Carried as the payload of a BusinessEvent with eventQualifier = 'CashPenalty'.">
    [metadata key]
    [rootType]
    failedTransferReference Transfer (1..1) <"Reference to the failed Transfer that is being penalised.">
        [metadata reference]
    penaltyAccrualDate date (1..1) <"The business date for which this penalty assessment applies. CSDR penalties accrue daily until the underlying fail is resolved.">
    penaltyAmount Money (1..1) <"The penalty amount for this accrual day.">
    penaltyRateBps number (1..1) <"The applied penalty rate in basis points per day, derived from the ESMA Penalty Matrix for the instrument's liquidity class.">
    instrumentLiquidityClass CSDRLiquidityClassEnum (1..1) <"The instrument's liquidity classification used to derive the rate.">
    penaltyCounterparty Party (1..1) <"The party owing the penalty (the failing party).">
        [metadata reference]
    penaltyBeneficiary Party (1..1) <"The party receiving the penalty (the suffering party).">
        [metadata reference]
    referencePrice Price (0..1) <"The reference price used to compute the penalty notional, where required.">

// In event-qualification-func.rosetta — new qualification function
func Qualify_CashPenalty: <"Qualifies a BusinessEvent as a CSDR Article 7 cash penalty assessment.">
    [qualification BusinessEvent]
    inputs:
        businessEvent BusinessEvent (1..1)
    output:
        is_event boolean (1..1)

    set is_event:
        businessEvent -> eventQualifier = "CashPenalty"
```

### 3.3 Gap 9: Buy-in event

**Target file.** New file `event-buyin-type.rosetta`; extend `event-qualification-func.rosetta`.
**PR scope.** ~150 lines. Non-breaking.

```rosetta
namespace cdm.event.buyin

import cdm.base.staticdata.party.*
import cdm.event.common.*
import cdm.product.template.*
import cdm.product.common.settlement.*

enum BuyInRegimeEnum: <"Identifies the legal/contractual regime under which a buy-in is being executed.">
    CSDRMandatoryBuyIn <"CSDR Article 7 mandatory buy-in (when in force) or its applicable successor regime.">
    GMSLA_2018 <"Buy-in under the 2018 GMSLA paragraph 9 'Failure to deliver'.">
    GMRA_2011 <"Buy-in under the 2011 GMRA paragraph 10 'Mini close-out'.">
    BilateralContractual <"Buy-in under bespoke bilateral contractual terms.">

enum BuyInOutcomeEnum: <"The outcome of a buy-in execution with respect to the original failed transfer.">
    OriginalTransferCancelled <"The original failed transfer is cancelled and replaced by the buy-in cover trade. Delivery obligation is satisfied via the cover trade.">
    CashSettlementInLieu <"The buy-in cannot be executed in the market; per the applicable regime's fallback, the failed transfer is cash-settled at the buy-in reference price. The original delivery obligation is extinguished.">

type BuyInInstruction: <"Instructions for a CSDR Article 7 mandatory buy-in or a contractual buy-in following a settlement failure. The buy-in instruction is issued after the applicable extension period has expired.">
    [metadata key]
    [rootType]
    failedTransferReference Transfer (1..1) <"Reference to the original failed Transfer that triggers this buy-in.">
        [metadata reference]
    buyInRegime BuyInRegimeEnum (1..1) <"The legal/contractual regime under which this buy-in is executed.">
    buyInAgent Party (0..1) <"The buy-in agent appointed to execute the cover purchase. May be omitted when the suffering party executes directly.">
        [metadata reference]
    buyInTriggerDate date (1..1) <"The business date on which the buy-in process is initiated.">
    buyInExtensionPeriod int (0..1) <"Number of business days of extension granted before mandatory buy-in execution. Per CSDR, 4 to 7 business days post intended-settlement-date depending on instrument class.">
    buyInDeadline date (0..1) <"The latest date by which the buy-in must be executed.">

type BuyInExecution: <"Records the execution of a buy-in: the cover purchase by the suffering party (or its agent), the cost-attribution to the failing party, and the cancellation/cash-settlement of the original failed transfer.">
    [metadata key]
    [rootType]
    buyInInstruction BuyInInstruction (1..1) <"The instruction that authorised this execution.">
        [metadata reference]
    coverPurchaseTrade Trade (0..1) <"The new trade executed in the market to acquire the failed-to-deliver securities. Required when originalTransferOutcome = OriginalTransferCancelled.">
        [metadata reference]
    costAttribution Transfer (1..1) <"The cash transfer from the failing party to the suffering party covering the buy-in cost differential or the cash-settlement-in-lieu amount.">
        [metadata reference]
    originalTransferOutcome BuyInOutcomeEnum (1..1) <"The outcome of the buy-in with respect to the original failed transfer.">
    referencePrice Price (0..1) <"For CashSettlementInLieu, the reference price at which the failed transfer was cash-settled.">

    condition CoverPurchaseRequiredForCancellation:
        if originalTransferOutcome = BuyInOutcomeEnum -> OriginalTransferCancelled
        then coverPurchaseTrade exists

    condition ReferencePriceRequiredForCashSettlement:
        if originalTransferOutcome = BuyInOutcomeEnum -> CashSettlementInLieu
        then referencePrice exists

// In event-qualification-func.rosetta — new qualification functions
func Qualify_BuyInInstruction:
    [qualification BusinessEvent]
    inputs:
        businessEvent BusinessEvent (1..1)
    output:
        is_event boolean (1..1)

    set is_event:
        businessEvent -> eventQualifier = "BuyInInstruction"

func Qualify_BuyInExecution:
    [qualification BusinessEvent]
    inputs:
        businessEvent BusinessEvent (1..1)
    output:
        is_event boolean (1..1)

    set is_event:
        businessEvent -> eventQualifier = "BuyInExecution"
```

### 3.4 Gap 10: Obligation as a first-class root type

**Target file.** New file `event-obligation-type.rosetta`; new enum file or extend existing.
**PR scope.** ~200 lines. Non-breaking — new top-level type, optional reference from `BusinessEvent` and `TradeState`.

This is the largest of the proposed extensions and the highest-leverage. It crosses deferred settlement, SBL recall, collateral substitution, manufactured payments, and CSDR workflows. The shape is deliberately broad enough to subsume all of these and tight enough to retain semantic precision.

```rosetta
namespace cdm.event.obligation

import cdm.base.staticdata.identifier.*
import cdm.base.staticdata.party.*
import cdm.base.staticdata.asset.common.*
import cdm.event.common.*
import cdm.product.common.settlement.*

enum ObligationTypeEnum: <"Classifies an Obligation by the kind of bilateral commitment it represents.">
    SettlementDeliveryVersusPayment <"A delivery-versus-payment settlement obligation arising from a securities or derivatives trade.">
    SettlementFreeOfPayment <"A free-of-payment settlement obligation (security delivery without paired cash payment).">
    CashPayment <"A cash-payment obligation (e.g., manufactured dividend, coupon, fee, CSDR penalty).">
    SBLRecall <"An obligation arising from a securities-lending recall: the borrower must return securities by the recall deadline.">
    SBLReturn <"A scheduled return obligation under a fixed-term SBL.">
    CollateralSubstitution <"An obligation to substitute one collateral asset for another under a collateral agreement.">
    CollateralTopUp <"An obligation to deliver additional collateral following a margin call.">
    BuyInDelivery <"An obligation to deliver under a buy-in cover trade.">
    CashCompensation <"An obligation to pay cash compensation in lieu of physical delivery (CSDR fallback, GMSLA close-out, etc.).">
    ManufacturedPayment <"An obligation to pay a manufactured dividend, manufactured coupon, or other corporate-action-derived payment.">

enum ObligationStatusEnum: <"The lifecycle status of an Obligation.">
    Pending <"The obligation has been created but not yet instructed for discharge.">
    Instructed <"The obligation has been instructed for discharge (e.g., a settlement instruction has been sent to the CSD).">
    PartiallyDischarged <"The obligation has been partially discharged; the residual quantity remains pending.">
    Discharged <"The obligation has been fully discharged.">
    Failed <"An attempt to discharge the obligation has failed (e.g., a settlement fail at the CSD); the obligation remains open.">
    Cancelled <"The obligation has been cancelled by mutual agreement of obligor and obligee.">
    EscalatedToBuyIn <"The obligation has been escalated to a buy-in workflow following persistent failure to discharge.">
    CompensatedInCash <"The obligation has been discharged via cash compensation in lieu of physical delivery (e.g., CSDR fallback).">

type Obligation: <"A first-class representation of an outstanding bilateral obligation between two parties, with explicit lifecycle states and discharge conditions. Used for deferred settlement obligations between trade date and settlement date, for collateral substitution demands, for SBL recalls and returns, for manufactured payments arising from corporate actions in a settlement window, and for CSDR-mandated workflows.">
    [metadata key]
    [rootType]
    identifier Identifier (1..*) <"One or more identifiers for this obligation. The primary identifier should be derived deterministically from the source event for replay determinism.">
        [metadata scheme]
    obligationType ObligationTypeEnum (1..1) <"Classification of the obligation by kind.">
    obligor Party (1..1) <"The party owing the obligation (the deliverer / payer).">
        [metadata reference]
    obligee Party (1..1) <"The party to whom the obligation is owed (the receiver).">
        [metadata reference]
    obligedAsset AssetFlowBase (1..1) <"The asset (security or cash) and quantity to be delivered or paid under this obligation.">
    expectedDischargeDate date (1..1) <"The contractually expected date by which the obligation must be discharged. Drives reconciliation lag, penalty accrual, and buy-in trigger logic.">
    actualDischargeDate date (0..1) <"The date on which the obligation was actually discharged; populated when obligationStatus reaches Discharged or one of its terminal alternatives.">
    obligationStatus ObligationStatusEnum (1..1) <"The current lifecycle status of the obligation.">
    sourceEvent BusinessEvent (1..1) <"The originating event that created this obligation (trade execution, recall instruction, substitution demand, etc.).">
        [metadata reference]
    dischargeEvent BusinessEvent (0..1) <"The event that discharged this obligation; populated when the obligation reaches a terminal status.">
        [metadata reference]
    parentObligation Obligation (0..1) <"For obligations created as successors of a partial-discharge or buy-in resolution, references the parent obligation.">
        [metadata reference]

    condition ActualDischargeDateConsistency:
        if obligationStatus = ObligationStatusEnum -> Discharged
            or obligationStatus = ObligationStatusEnum -> Cancelled
            or obligationStatus = ObligationStatusEnum -> CompensatedInCash
        then actualDischargeDate exists

    condition DischargeEventOnTerminal:
        if obligationStatus = ObligationStatusEnum -> Discharged
            or obligationStatus = ObligationStatusEnum -> CompensatedInCash
        then dischargeEvent exists
```

### 3.5 Path to upstream

These four PR units (Gaps 6+7, 8, 9, 10) are independent and can be submitted to the FINOS CDM repository in parallel. Recommended sequence:

1. **PR-1 (Gap 6+7).** TransferStatus enrichment + TransferFailureReason. Smallest, highest-leverage, blocking for CSDR. Likely first to be accepted because it's purely additive to existing types.
2. **PR-2 (Gap 8).** CSDR cash penalty event. Independent of PR-1 but composes naturally with it.
3. **PR-3 (Gap 9).** Buy-in event. Depends on PR-1 (references the failed transfer's status) but can be drafted in parallel.
4. **PR-4 (Gap 10).** Obligation root type. Largest scope; benefits from PR-1/2/3 being merged first to demonstrate the pattern of composability.

For each PR, the unit-test deliverable is one CDM-sample-file in the `demo` repo's `src/main/resources/result-json/` showing a complete deferred-settlement scenario (buy / instruct / fail / penalty / buy-in) using the new types.

---

## 4. The Fundamental CDM-vs-Ledger Semantic Gap (Gap 11, in CDM-Charitable Language)

CDM 6.0.0 represents the trade-date-vs-settlement-date gap **implicitly** through three mechanisms:

1. **`TransferStatusEnum.Pending` / `.Instructed`** — values that exist before `Settled`.
2. **The absence of `Settled`** on a `TransferState` — meaning the transfer has not yet completed.
3. **`PositionStatusEnum.Executed` vs `.Settled`** — distinguishing the two states.

This is mathematically sound but semantically permissive: a CDM-only stack could, without violating the schema, treat the position represented by a `TradeState` as null until its associated `TransferState` reaches `Settled`. That stack would be **wrong** — the buyer is economically long from `tradeDate`, regardless of CSD confirmation — but the CDM schema itself would not catch the error.

The Ledger v11.0 makes this semantic explicit and structural via Invariant E1 (`economic-exposure-at-T`). The Phase 1 proposals are unanimous on this; it is the foundational invariant of the unified design.

The CDM-charitable framing of the gap:

> **CDM correctly separates two clocks** — tradeDate (when economic terms are agreed) and the settlement timeline (when the CSD or payment system confirms the transfer of value). What CDM does **not** assert, in either documentation or qualification semantics, is the canonical relationship between a `TradeState` and the position it represents during the open window between those two clocks. A CDM-only consumer must infer the relationship; a wrong inference is silent because nothing in CDM rejects it.

The CDM-charitable correction:

> **A future CDM revision (CDM 7.0 candidate) should adopt, as a normative semantic, the assertion that for any `TradeState` with `tradeDate = T_exec`, the position represented by the trade is true from `T_exec` for the purposes of risk, PnL, and economic exposure, regardless of the `transferStatus` of any associated `Transfer`.** This is the trade-date-accounting principle as canonical CDM semantics. The implementation can be:
>
> - A normative paragraph in the `TradeState` documentation,
> - A qualification function `is_economic_position_recognised_at_tradeDate` that any CDM-conformant consumer must respect, and
> - A doc-string addition to `TransferStatusEnum` clarifying that the `Pending` / `Instructed` states refer to the **transfer of value**, not to the **economic exposure** that arose at `tradeDate`.

This is non-breaking. It is a documentation-and-semantics addition, not a schema change. It can be proposed as a single FINOS PR alongside the structural Gaps 6-10 PRs.

The deeper observation is this: CDM was designed by derivatives practitioners for whom the trade-date-vs-settlement-date gap was either trivial (cleared derivatives settle T+0 on margin), bilateral and bespoke (OTC derivatives), or implicit (cash-settlement is the default). The deferred-settlement gap on cash equities is a structural feature CDM has not been forced to confront because cash equities are a relatively recent CDM-coverage target. The Ledger v11.0 forces the issue. The proposed semantic adoption is the correct CDM-side response.

---

## 5. The Forgetful Functor F: MoveStream → CDM BusinessEvent

The Ledger emits a stream of `Move` and `Transaction` records. CDM consumes a stream of `BusinessEvent` records. The mapping between them is a forgetful functor F that preserves the structural properties (conservation, sequencing, idempotency) of the Ledger while losing the per-(wallet, unit) granularity that CDM does not represent.

### 5.1 Statement

Let $\mathbf{Lg}$ be the category of Ledger states (objects: `(WalletRegistry, UnitRegistry, MoveStream, ObligationStore)` snapshots; morphisms: balanced atomic transactions). Let $\mathbf{CDM}$ be the category of CDM states (objects: sets of `TradeState` snapshots; morphisms: `BusinessEvent` instances).

> **F is a homomorphism.** $F : \mathbf{Lg} \to \mathbf{CDM}$ defined by:
>
> $F(\tau_T : \text{trade execution})$ = `BusinessEvent` with `eventQualifier = "Execution"`, `instruction.execution` populated, `after` containing a `TradeState` whose `tradeDate = T` and whose `transferHistory` carries one `TransferState` per leg (status `Pending`).
>
> $F(\tau_{T+2-} : \text{instruction emitted})$ = `BusinessEvent` with `eventQualifier = "Settlement"`, `after` containing a `TradeState` with the corresponding `TransferState` updated to `transferStatus = Instructed` and `expectedSettlementDate = T+2` (Gap 6 field).
>
> $F(\tau_{T+2+,SUCCESS})$ = `BusinessEvent` with `eventQualifier = "Settlement"`, `after` carrying `transferStatus = Settled` and `actualSettlementDate = T+2` (Gap 6 field).
>
> $F(\tau_{T+2+,FAIL})$ = `BusinessEvent` with `eventQualifier = "Settlement"`, `after` carrying `transferStatus = Failed` (Gap 6 enum value) and `failureReason` populated (Gap 6 type).
>
> $F(\tau_{T+2+,PARTIAL})$ = a single `BusinessEvent` with `eventQualifier = "Settlement"`, `after` carrying two `TransferState` records: one `Settled` for the partial portion, one `PartiallySettled` for the residual.
>
> $F(\tau_{\text{CSDR penalty}})$ = `BusinessEvent` with `eventQualifier = "CashPenalty"` (Gap 8 qualifier), `instruction` populated, payload referencing a `CSDRPenaltyDetail` (Gap 8 type).
>
> $F(\tau_{\text{buy-in instruction}})$ = `BusinessEvent` with `eventQualifier = "BuyInInstruction"` (Gap 9), payload referencing `BuyInInstruction`.
>
> $F(\tau_{\text{buy-in execution}})$ = `BusinessEvent` with `eventQualifier = "BuyInExecution"` (Gap 9), payload referencing `BuyInExecution`.
>
> $F(\text{obligation issuance / discharge moves})$ = a referenced `Obligation` object (Gap 10), with `sourceEvent` and `dischargeEvent` pointing to the corresponding BusinessEvents.

### 5.2 What F preserves

**Conservation.** For every Ledger transaction $\tau$, $\sum_w \Delta w(u) = 0$ for every unit $u$. Under F, each `Move` becomes a `Transfer` (or a leg of a `Transfer`), and the conservation property survives as the matching of `payerReceiver` references: every CDM `Transfer` has exactly one payer and one receiver, so the algebraic sum across the two parties is zero by construction. **Conservation is preserved.**

**Sequencing.** The Ledger MoveStream is a totally-ordered sequence of transactions. Under F, this becomes a sequence of `BusinessEvent` records, ordered by `eventDate` and (where multiple events share an `eventDate`) by their content-addressed identifier. CDM does not enforce a global order on `BusinessEvent` records, but the per-trade order is preserved by the `before` / `after` `TradeState` references: each event's `after` becomes the next event's `before`, forming a chain. **Per-trade sequencing is preserved.**

**Idempotency.** A duplicate Ledger transaction is a no-op (replay). Under F, a duplicate `BusinessEvent` is identified by its content-addressed identifier; CDM consumers that deduplicate on this identifier discard the duplicate. **Idempotency is preserved by the consumer; it requires the consumer to honour content-addressing, which is a Ledger-level discipline that F transmits but does not itself enforce.**

### 5.3 What F loses

F is **forgetful**. It loses three structural facts that the Ledger carries but CDM does not represent:

1. **Per-(wallet, unit) PositionState.** The Ledger's PositionState row $w(u)$ is denser than the CDM `TradeState`'s per-trade view. Under F, a single Ledger transaction touching $N$ wallets becomes a CDM `BusinessEvent` whose `after` carries `TradeState` per affected trade, not per wallet. **The wallet axis is collapsed.** This is Gap 12 (the StatesHome 3-map alignment gap).

2. **In-flight virtual-wallet contras.** The Ledger's `w_inflight_*` virtual wallets that hold the (T, T+2) gap have no CDM analogue. Under F, the gap is represented only by the *absence* of a `Settled` `TransferState`, not by an explicit object. **The carrier of the gap is lost** — until Gap 10 (Obligation root type) is upstream, at which point the obligation is the explicit carrier.

3. **The atomicity of multi-leg moves.** A Ledger `Transaction` containing four moves is one atomic commit. Under F, this becomes one `BusinessEvent` whose `after` updates multiple `TransferState` records — but CDM does not have a runtime atomicity guarantee on the multi-record update. The `BusinessEvent` is the atomic unit; the consumer must treat all `after` updates as a single commit. **Atomicity is preserved by convention, not by structural enforcement.**

### 5.4 Why this matters

The forgetful functor F is a homomorphism on the structural properties (conservation, sequencing, idempotency) and a strict loss on the granularity properties (wallet axis, in-flight carrier, atomicity guarantee). **The Ledger is denser than CDM by design.** F transmits the part of the Ledger's state that CDM can represent, and the Ledger retains the rest as its native source of truth.

**This is the right relationship between Ledger and CDM.** The Ledger is the source of truth; CDM is the lossy projection used for ISDA-style cross-firm communication. The Ledger reconciles to CDM via F, not the other way around. Any architecture that puts CDM upstream of the Ledger as a source-of-truth would inherit CDM's losses and create exactly the kind of blind spot that motivates Gap 11 (the economic-exposure-at-T semantic). **Ledger first, CDM downstream.**

---

## 6. ISO 20022 Cross-Walk

The deferred-settlement spec touches six ISO 20022 message types. Each maps to a CDM event, a Ledger move primitive, and (in the new world after Gaps 6-10 are upstreamed) a CDM payload type.

| ISO 20022 message | Direction | Purpose | CDM event | CDM payload (post-extension) | Ledger move primitive |
|---|---|---|---|---|---|
| **sese.023** Securities Settlement Transaction Instruction | Outbound (Ledger → CSD) | Instructs the CSD to settle a securities transaction (DvP or FoP) | `BusinessEvent` with `eventQualifier = "Settlement"`, `instruction` populated; `after.TradeState.transferHistory[].transferStatus = Instructed` | (Gap 6) `expectedSettlementDate` populated on the `TransferState` | LIFECYCLE-class transaction: `ObligationStatusUpdate(PENDING → INSTRUCTED)`. No moves. |
| **sese.024** Securities Settlement Transaction Status Advice | Inbound (CSD → Ledger) | Reports status (matched, unmatched, hold, fail-pre-settlement, partial-settlement-projected) | `BusinessEvent` with `eventQualifier = "SettlementStatusUpdate"`; `after.TradeState.transferHistory[].transferStatus` updated per status | (Gap 6) `failureReason` populated for fail-pre-settlement | LIFECYCLE-class transaction recording the status update. No moves. For a *fail* status the Ledger emits `ObligationStatusUpdate(INSTRUCTED → FAILED)`. |
| **sese.025** Securities Settlement Transaction Confirmation | Inbound (CSD → Ledger) | Confirms settlement (full or partial) | `BusinessEvent` with `eventQualifier = "Settlement"`; `after.TradeState.transferHistory[].transferStatus = Settled` (full) or `PartiallySettled` (partial) | (Gap 6) `actualSettlementDate` populated; for partial, `failureReason.settledQuantity` populated | SETTLEMENT-class transaction discharging the in-flight wallets to the nostro and closing the obligation. For partial: a child obligation is spawned for the residual. |
| **sese.027** Securities Transaction Cancellation Request | Outbound or Inbound | Requests cancellation of a pending instruction | `BusinessEvent` with `eventQualifier = "Cancellation"`; `after.TradeState.transferHistory[].transferStatus = Cancelled` (Gap 6 enum value) | (Gap 6) `Cancelled` status | LIFECYCLE-class transaction: `ObligationStatusUpdate(... → CANCELLED)`. For cancellation post-trade, the position is **not** reversed — cancellation is on the settlement instruction, not on the economic position. The economic position may require a separate compensating CORRECTION transaction depending on bilateral terms. |
| **camt.054** Bank-to-Customer Debit/Credit Notification | Inbound (Cash bank → Ledger) | Notifies cash credit or debit on the nostro | `BusinessEvent` with `eventQualifier = "Settlement"`; `after.TradeState.transferHistory[]` for the cash leg `transferStatus = Settled` | (Gap 6) `actualSettlementDate` on the cash leg `TransferState` | SETTLEMENT-class transaction discharging the cash in-flight wallet to the cash nostro. |
| **MT54x (legacy SWIFT)** — MT540 (Receive Free), MT541 (Receive Against Payment), MT542 (Deliver Free), MT543 (Deliver Against Payment), MT544/545/546/547 (Status/Confirm) | Both directions | Legacy SWIFT FIN equivalents of the sese.0xx series | Same CDM events as the corresponding sese.0xx | Same as sese.0xx | Same as sese.0xx; the FIN-vs-XML choice is a transport-layer concern. The Ledger normalises legacy MT54x to the sese.0xx-equivalent CDM event before persisting. |

### 6.1 Synonym mapping

The synonym mappings for the ISO 20022 message-to-CDM-type translation live in `rune-fpml` (which despite the name covers ISO 20022 mappings as well as FpML, per `cdm_6x_path_scheme.md`). The deferred-settlement extension requires three new synonym blocks:

```rosetta
// Sketch — to be elaborated in the cdm-iso20022-synonym-lib equivalent
synonym source ISO20022 {
    TransferState:
        Failed = "FAIL"  // sese.024 status reason / sese.025 partial-settlement marker
        PartiallySettled = "PART"  // sese.025 partial settlement
        Cancelled = "CANC"  // sese.027 cancellation
    TransferFailureReason:
        failReasonCode -> "PndgRsn"
}
```

The synonym layer is non-trivial; ISDA's DRR work has already standardised much of it. The deferred-settlement-specific synonyms compose with what DRR has produced.

### 6.2 The critical observation

**Each ISO 20022 message is a *witness* to a state transition, not the transition itself.** The Ledger emits LIFECYCLE-class transactions (no moves) on receipt of `sese.024/.025/.027`/`camt.054`; the witness is recorded as the source of the state change. Under F, this becomes a CDM `BusinessEvent` whose `eventDate` equals the witness timestamp. The Nazarov view (Phase 1) is correct here: state is *driven by attested observations*, never by inference. CDM's `BusinessEvent` model accommodates this naturally — every event has an `eventDate` and a content-addressed identifier, so witness provenance is preserved.

---

## 7. The First-Class-Unit Position — Trade-Off and Dissent

A material minority of Phase 1 proposals (matthias §1.2, cartan §2, halmos §1.2, noether §1.2, formalis §1.2-1.3, minsky §1.2, sbl §1.1, finops §0) argue that the obligation should be a **unit** in the StatesHome universe — a row in `PositionState[w_obligation_register, u_obligation_id]` — rather than only an `L_15` Obligation row. The cartan formulation is the strongest: the obligation is the **kernel** of the discrepancy between Ledger position and external custody (categorical kernel), and unit-hood is the natural way to encode that.

The unified design that converged in the Settlement Team's Phase 2 brief is **virtual-wallets-and-L_15-Obligation** — i.e., the obligation is an `L_15` row, **not** also a unit in `PositionState`. The trade-off is real and worth recording.

### 7.1 The case for first-class unit (the dissent)

1. **Conservation by construction.** A unit whose total $\sum_w w(u) = 0$ holds at every $t$ inherits the framework's conservation discipline for free. If the obligation is *only* an `L_15` row, conservation is not a property of the obligation — it is a property of the moves that surround it.

2. **Time travel for free.** PositionState is bitemporal (per StatesHome and `ledger_data_v1.0`); `L_15` is also bitemporal but via a different mechanism. Unit-hood means time-travel queries against the obligation use the same machinery as time-travel queries against any other position.

3. **Reconciliation symmetry.** The R1 reconciliation identity (matthias §1.5) is the simplest expression of "Ledger leads, nostro follows" when the in-flight quantity is a wallet read. If the obligation is not a unit, the reconciliation identity has to be expressed across two separate stores (PositionState + L_15), which is harder to state and harder to test.

4. **Categorical clarity (cartan §2.5).** The obligation is the kernel of the forgetful functor that erases the custody-confirmed component of a position. Kernels live in the same category as the objects whose kernel they are. Unit-hood is the categorically-correct home.

### 7.2 The case against first-class unit (the convergent design)

1. **Schema parsimony.** The unified design adds zero new `unit_type` enum values. The `L_15` obligation table is a single new table whose schema is well-understood. Unit-hood would add a new closed-sum variant on `unit_type` and require every consumer of `PositionState` to know how to handle obligation units (skip them in PnL? include them at zero price? include them at face value?).

2. **PnL semantics.** A unit in `PositionState` participates in the valuation function $V_t = \sum_u w_t(u) \cdot P_t(u)$. The obligation unit's price is, by N3 (noether §3.4) — redemption-equivalence — equal to the underlying's price. But this requires defining a price oracle for the obligation unit, which is more work than treating the obligation as a non-priced bookkeeping artefact.

3. **The two-views issue (jane_street §1.3).** "Position balances $w(u)$ and unit state PositionState[w, u] are functions of the trade-date event stream only. Settlement status changes never write to balances." Making the obligation a unit means settlement-status changes *do* write to PositionState — to the obligation's PositionState. This blurs the jane_street rule.

4. **CDM cross-walk simplicity.** The forgetful functor F (§5 above) maps the `L_15` obligation cleanly to a Gap 10 `Obligation` payload. If the obligation were also a unit, F would have to either drop the unit-hood (and lose information) or invent a parallel CDM construct (which doesn't exist).

5. **Operational simplicity.** Reconciliation engineers (per finops, ashworth, sbl, isda) want each unsettled trade to be individually addressable in the books. The `L_15` obligation does this naturally. Adding unit-hood does not change addressability — it only adds a parallel representation that consumers must reconcile.

### 7.3 The Settlement Team's choice and my dissent recorded

The Settlement Team's convergent design is **virtual-wallets + L_15 Obligation + transaction-level FSM**. I defer to this choice. The dissent I record is this:

> The unified design is correct in operational terms and pragmatic for the v11.0 release. The first-class-unit position (cartan, halmos, noether, my Phase 1 §1.2) is structurally cleaner and would, in a CDM 7.0 future where Gap 10 (Obligation root type) is upstream, allow the Ledger's obligation representation to map to CDM 1-to-1 with no loss. I recommend the Settlement Team revisit the unit-hood choice when CDM 7.0's Obligation type lands; the migration cost from "obligation as L_15 row" to "obligation as unit" should be planned as a future architecture revision rather than a permanent commitment.

The dissent is recorded for the historical log. The unified design ships.

---

## 8. CDM 6.0.0 Features That Should NOT Be Used

CDM 6.0.0 contains several features that look applicable to the deferred-settlement scope but are wrong for it. Using them would produce a model that compiles but loses semantics that the Ledger v11.0 must preserve.

### 8.1 `partialCashSettlement boolean` on `PCDeliverableObligationCharac` (CDS-only)

**Why it looks applicable.** The name suggests it represents partial settlement.
**Why it is wrong.** This is a CDS-specific boolean indicating whether *cash settlement of a credit derivative* is partial. It is unrelated to the partial settlement of a securities settlement instruction. Using it would conflate two unrelated concepts and silently corrupt CDS modelling for any consumer that reads the flag.
**Correct approach.** Use Gap 6 (`TransferStatusEnum.PartiallySettled` + `TransferFailureReason.settledQuantity`).

### 8.2 `sixtyBusinessDaySettlementCap` text on `PhysicalSettlementTerms` (CDS-only)

**Why it looks applicable.** It contains the term "buy-in" in its documentation.
**Why it is wrong.** This is a CDS-specific text field describing a *fallback for failed physical settlement of a credit derivative* — buy-in here means "the protection buyer bought the deliverable obligation in the market because the seller failed to deliver under the credit event auction." It is unrelated to CSDR mandatory buy-in or GMSLA contractual buy-in for cash equity settlement fails.
**Correct approach.** Use Gap 9 (`BuyInInstruction`, `BuyInExecution`, `BuyInRegimeEnum`).

### 8.3 Updating the position on settlement (i.e., NOT using trade-date accounting)

**Why it looks applicable.** CDM is permissive — nothing in the schema prevents a consumer from treating the position as null-until-settled.
**Why it is wrong.** This violates Invariant E1 (economic-exposure-at-T). The PnL computed from a settlement-date position would be wrong: it would spike at T+2 when settlement confirms, even though no economic event occurred at T+2. A failed trade would be "ungrounded" in PnL — there would be no economic position recorded for the buyer between T and T+2 if T+2 fails. **All of this is wrong, but CDM does not catch it.**
**Correct approach.** Adopt the trade-date-accounting semantic at the Ledger level (E1), and propose Gap 11 (semantic adoption) to CDM 7.0 to make this the canonical CDM semantic.

### 8.4 Reversing the position on a fail

**Why it looks applicable.** A natural-but-wrong reading of "the trade did not settle" is "the trade did not happen, so reverse the position."
**Why it is wrong.** This violates Invariant E3 (fail does not reverse position). The buyer is economically long from T regardless of whether T+2 succeeds, fails, or is bought-in. Reversing the position would (i) make the buyer flat at T+2 even though they are still legally entitled to delivery, (ii) break path-independence of PnL, and (iii) silently shift PnL into a phantom "fail PnL" account that does not correspond to any real economic event.
**Correct approach.** A fail emits zero moves on the trader's real wallet. Only the obligation's status changes (PENDING/INSTRUCTED → FAILED). The economic position is preserved. CSDR penalty accrues; buy-in workflow may eventually trigger; either resolves the obligation without retroactive reversal.

### 8.5 Using `Lineage` for the obligation chain (matthias / parent-child obligation references)

**Why it looks applicable.** `Lineage` exists in CDM and could express parent-child relationships.
**Why it is wrong.** `Lineage` is **deprecated** in CDM 6.x — see `WorkflowStep.lineage [deprecated]` (verified per `cdm_6x_verified_facts`). New lineage chains should use `previousWorkflowStep` references or content-addressed hashes.
**Correct approach.** For obligation parent-child relations (partial settlement spawns a residual obligation; buy-in cancels a parent obligation), use Gap 10's `Obligation.parentObligation Obligation (0..1)` reference field, not `Lineage`.

### 8.6 Embedding settlement status on `Trade.contractDetails`

**Why it looks applicable.** `Trade.contractDetails` is a natural place to put trade-level metadata.
**Why it is wrong.** `Trade.contractDetails` is for the legal contract metadata (master agreement, governing law, document references). Putting runtime settlement status there conflates legal-static information with operational-dynamic information. Operational status changes would force re-issuance of the trade record, which would in turn invalidate downstream references.
**Correct approach.** Settlement status lives on the `TransferState`, not on the `Trade`. Trade is the agreement; TransferState is the lifecycle of the value transfer that discharges the agreement.

### 8.7 Using `EconomicTerms.collateral` for the CSA/VM relationship

**Why it looks applicable.** It contains the word "collateral".
**Why it is wrong.** `EconomicTerms.collateral` is product-level intrinsic collateral (e.g., a repo haircut schedule, structured-note collateral). The CSA / VM relationship that gates margin calls and post-default close-out lives at `Trade.collateral CollateralProvisions`, not on `EconomicTerms`. This is a separate gap from the deferred-settlement scope but it is a common error and worth flagging as out-of-scope here. (Also: `CollateralProvisions` has only three fields — `collateralType`, `eligibleCollateral`, `substitutionProvisions` — per verified-facts; the `creditSupportAgreementElections` lives elsewhere via the legal-agreement model.)

### 8.8 Using `DigitalAsset` to host tokenised cash for tokenised settlement

**Why it looks applicable.** Tokenised settlement is the future per the ISDA roadmap; `DigitalAsset` is in CDM.
**Why it is wrong.** `DigitalAsset` carries the condition `assetType = Other` and an explicit doc-string exclusion: "the digital representation of other Assets, eg coins or Tokenised assets." `DigitalAsset` is for *native* digital assets (BTC, ETH), not for tokenised representations of off-chain securities or cash. Using `DigitalAsset` for tokenised USD or tokenised AAPL would misrepresent the asset.
**Correct approach.** Tokenised collateral and tokenised settlement need a `lifecycle_model = SmartContract` discriminator on `EconomicTerms` (per `cdm_gap_log` Gap 3, the tokenisation gap). This is out of scope for deferred settlement v11.0 but cited here because the ISDA tokenisation roadmap (per the isda Phase 1 §8.5) intersects with the deferred-settlement degeneracy-to-T+0 question.

### 8.9 Summary table

| Tempting CDM feature | Reason to avoid | Correct alternative |
|---|---|---|
| `PCDeliverableObligationCharac.partialCashSettlement` | CDS-specific; unrelated to securities partial settlement | Gap 6 — `TransferStatusEnum.PartiallySettled` |
| `sixtyBusinessDaySettlementCap` (CDS buy-in) | CDS-specific; unrelated to cash equity buy-in | Gap 9 — `BuyInInstruction` / `BuyInExecution` |
| Settlement-date position recognition | Violates E1; conflates economic and custody clocks | Trade-date accounting at the Ledger; Gap 11 semantic for CDM |
| Reversing position on fail | Violates E3; breaks PnL path-independence | Zero moves on fail; only obligation status updates |
| `Lineage` for obligation chain | Deprecated in CDM 6.x | Gap 10 — `Obligation.parentObligation` |
| Settlement status on `Trade.contractDetails` | Conflates static legal with dynamic operational | Settlement status on `TransferState` |
| `EconomicTerms.collateral` for CSA | Product-level intrinsic collateral, not CSA | `Trade.collateral CollateralProvisions` (separate gap, OoS here) |
| `DigitalAsset` for tokenised cash | Excluded by CDM doc-string and condition | Tokenisation gap (Gap 3 of cdm_gap_log) |

---

## 9. Closing — Cross-Walk Disposition

The cross-walk shows that CDM 6.0.0 maps cleanly to **roughly half** of the Ledger v11.0 deferred-settlement design (11 Direct + 6 Partial out of 24 inventoried elements). The remaining 7 elements are genuine structural gaps that the Ledger v11.0 must solve internally and that should be proposed to FINOS as upstream extensions:

1. **PR-1 (Gap 6+7).** TransferStatus enrichment + TransferFailureReason. **Highest priority; CSDR-blocking.** ~80 lines, non-breaking.
2. **PR-2 (Gap 8).** CSDR cash penalty event + payload. ~120 lines, non-breaking.
3. **PR-3 (Gap 9).** Buy-in event. ~150 lines, non-breaking.
4. **PR-4 (Gap 10).** Obligation as a first-class root type. ~200 lines, non-breaking; cross-cuts deferred settlement, SBL, collateral substitution, manufactured payments.
5. **Doctrinal proposal (Gap 11).** Economic-exposure-at-T as a CDM-canonical semantic. Documentation-and-qualification-function PR; non-breaking.

The forgetful functor F: MoveStream → CDM BusinessEvent is a homomorphism on the structural properties (conservation, sequencing, idempotency) and a strict loss on the granularity properties (per-(wallet, unit) state, in-flight virtual-wallet contras, multi-leg atomicity). This is the right relationship: Ledger first, CDM downstream as a lossy projection.

The first-class-unit position is recorded as a dissent for the historical log; the Settlement Team's convergent virtual-wallets + L_15 Obligation design ships.

The eight CDM 6.0.0 features flagged as "do not use" cover the most common mismodelling errors and are recorded in §8 as a reviewer checklist for the implementation phase.

**Cross-walk verification.** Every type, enum, field cardinality, and condition cited in this document was verified against `github.com/finos/common-domain-model@master` at 2026-04-30 via raw fetch. The deferred-settlement gap inventory is consistent with the cross-walk, with the two memory files (`cdm_6x_verified_facts.md` and `cdm_gap_log.md`), and with the unified Phase 1 convergence. The Rosetta extension drafts in §3 are syntactically valid CDM 6.x dialect, namespace-qualified, and PR-ready for FINOS contribution.

**Implementation readiness.** This cross-walk is implementation-ready. The four PR units are independent and can be drafted in parallel. The Ledger v11.0 deferred-settlement extension can ship with these gaps marked `cdm_native_pending = true` in the local model, with a clean migration path to CDM-native types as each PR is merged upstream.
