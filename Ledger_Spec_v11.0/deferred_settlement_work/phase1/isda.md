# Deferred Settlement in the Ledger Framework — ISDA / Regulatory-Reporter Proposal

**Author role:** isda-board-advisor (acting as regulatory-reporter)
**Phase:** 1 (independent proposal, no cross-talk)
**Target output:** `deferredSettlement.tex`
**Date:** 2026-04-30

---

## Framing

The deferred settlement gap is not a corner case — it is the single largest source of reconciliation breaks, regulatory fines, and capital inefficiency in cash equities. The 2024 US move to T+1, and the announced UK/EU move to T+1 in October 2027, shrink the open window but do not eliminate the structural problem: **economic exposure begins at trade date, custody movement completes at settlement date, and the Ledger must represent both faithfully without conflating them**.

The Ledger v10.3 already states the principle (§13 *Self-Consistency*: "trade-date accounting per §1") and asserts the FSM `EXECUTED → INSTRUCTED → SETTLED | FAILED` (§13.7). What is missing is an explicit, CDM-cross-walked, conservation-preserving representation of the **open settlement obligation as a first-class object** of the Ledger, with its own state, invariants, and reconciliation ladder. This document supplies that representation.

The ISDA position, supported by the DRR roadmap and the ESMA 2025 call-for-evidence response, is unambiguous: the open obligation must be **machine-representable from a single golden source**, never re-interpreted by each downstream consumer (PnL, regulatory, treasury, capital). Every duplicate representation is a divergence vector. Every bespoke field map is a fine waiting to happen. CSDR alone has cost the industry ~€100M+ in cash penalties since Feb 2022, with a long tail of buy-in administrative cost; in the US, FINRA Reg SHO 204 fines for FTD close-out failures continue to accumulate.

---

## 1. State Representation

### 1.1 The Three-Map Locus

The 3-map StatesHome ruling (v10.3 Addendum A1) gives us the storage discipline. Deferred settlement state attaches **only** to maps that already exist; we do not introduce a new sector.

| Field | Map | Key | Rationale |
|---|---|---|---|
| `lifecycle_stage` ∈ {EXECUTED, INSTRUCTED, PARTIALLY_SETTLED, SETTLED, FAILED, BOUGHT_IN, CANCELLED} | `UnitStatus` (when the unit IS a transaction-bound obligation, i.e. an OTC trade, see §1.3) — OR — carried on the **transaction record** in `MoveStream` (L₁₃) for fungible-unit trades | tx_id | `EXECUTED → SETTLED` is one-per-transaction, not one-per-(w,u). Sharing required by both counterparties' reconciliation against the same CSD instruction. |
| `intended_settlement_date` (ISD) | Transaction metadata in L₁₃ | tx_id | Pure CDM `settlementDate`; immutable once instructed. |
| `actual_settlement_date` (ASD) | `ExternalConfirmation` (L₁₁) inbound | (tx_id, message_id) | Written only on `sese.025` inbound. |
| `open_obligation_qty` (per leg) | `Obligation` (L₁₅) — FSM `Pending → Discharged | Compensated | Defaulted` | obligation_id keyed to (tx_id, leg) | Discharge-by-attestation (matched ISO 20022 confirmation). One obligation per settleable leg per side. |
| Open delivery exposure as a position | virtual wallet `w_csd_inflight` (per CSD, per CCP, per omnibus account) | (w_inflight, u) | The mechanism by which trade-date economic state and settlement-date custody state coexist without double-counting. |
| Penalty accrual (CSDR) | `Obligation` payload + `PolicyConfiguration` (L₇ᴾᵇ) penalty schedule | obligation_id | Per-day late, per-instrument bps; book to penalty wallet on T+ISD+1, T+ISD+2, … until discharge. |

### 1.2 The Inflight Virtual Wallet (the load-bearing mechanism)

We introduce a virtual wallet **per CSD per omnibus account per book**: `w_csd_inflight[CSD, omnibus, book]`. It sits between our portfolio wallet and the counterparty (or CCP) virtual wallet. It is a **virtual wallet** in the v10.3 §2 sense — included in conservation, has no PnL of its own — but it represents the bilateral *settlement obligation* rather than a real custody position.

- At T (trade date): securities move FROM the counterparty/CCP virtual wallet TO our portfolio wallet (economic position recognised); cash moves the other way. **Trade-date accounting is preserved.**
- The CDM `BusinessEvent` payload retains the ISD; an obligation L₁₅ row is opened for the settlement instruction.
- At T+ISD (settlement-confirmed): when `sese.025` SETTLED is received, **no balance moves** — the trade-date positions are already correct. The obligation is `Discharged`. The reconciliation attests that depot now matches. This is the v10.3 §13.7 rule and we keep it.
- At T+ISD if FAILED: the position is unchanged (correct), the obligation is still `Pending`, penalty accrual begins, and a virtual-wallet break is registered against the depot.

This is the **direction of travel** ISDA has set out in the post-trade vision: economic recognition decoupled from custody completion, both cleanly representable, both reconcilable, neither reinterpreted at the boundary.

### 1.3 Unit Identity Across Settlement

For listed equities (the floor case), **the unit identity is the ISIN**, not the trade. The trade is a transaction in `MoveStream`; the obligation L₁₅ entry is keyed to `tx_id`. The `lifecycle_stage` of *settlement* therefore lives on the transaction record / L₁₅ obligation, **not** on the unit. This is the correct CDM cross-walk: CDM `TradeState.state` carries the lifecycle of the *trade*, not of the security.

For OTC instruments where the unit IS the trade (CDM Trade including Collateral), `UnitStatus[u]` carries the same `lifecycle_stage` because tx and unit collapse. The data layer L₅ already supports this.

---

## 2. Move Sequence — Standard T+2 Buy

Buy 100 XYZ @ $50 on T (Mon), settle T+2 (Wed). Counterparty CSD is Euroclear via broker B.

### T (trade date) — atomic transaction `tx_BUY_XYZ`, type=`SETTLEMENT`

```
Move(  -- securities leg, economic recognition
    from:  w_broker_virtual,
    to:    w_portfolio,
    unit:  XYZ_ISIN,
    quantity: 100,
    timestamp: T,
    source: contract_equity_dvp,
    metadata: { cdm_event: ExecutionEvent, isd: T+2, leg: "securities" }
)
Move(  -- cash leg, economic recognition
    from:  w_portfolio,
    to:    w_broker_virtual,
    unit:  USD,
    quantity: 5000,
    timestamp: T,
    source: contract_equity_dvp,
    metadata: { cdm_event: ExecutionEvent, isd: T+2, leg: "cash" }
)
-- Conservation: ΔXYZ_total = +100 - 100 = 0;  ΔUSD_total = +5000 - 5000 = 0 ✓
```

Side effects (atomic, same `StateDelta`, condition C3):
- `MoveStream[tx_BUY_XYZ].status = EXECUTED`
- `Obligation[obl_securities] = Pending` (discharge-by-attestation = matched sese.025 IN)
- `Obligation[obl_cash] = Pending` (discharge-by-attestation = matched camt.054 IN)

**MiFIR transaction reporting trigger (RTS 22, T+1):** the trade fact is reported to the FCA/ESMA MiFIR archive on T+1 morning. Not at T+2. This is a Ledger emission obligation independent of settlement.

### T+1 (price = $52, no cash moved, status unchanged)

PnL on the open position: +$200 by mark-to-market of the *trade-date* position. The Ledger does *not* emit any move at T+1 unless something happens (settlement confirmation, fail, partial). PnL is computed on the existing position from the move stream, not from any settlement-date proxy.

### T+2⁻ (settlement instructed and pending)

Settlement layer has projected the transaction (§9 settlement projection), enriched with SSI, generated `sese.023` outbound message, sent to CSD. Status transitions:

```
MoveStream[tx_BUY_XYZ].status: EXECUTED → INSTRUCTED   (lifecycle event, no moves)
```

This is a state-only `LIFECYCLE` transaction — emits no balance moves, but is recorded in the move stream (per v10.3 §10.7) so the FSM trail is auditable.

### T+2⁺ (CSD confirms settlement)

```
sese.025 SETTLED inbound → ExternalConfirmation L₁₁ row
MoveStream[tx_BUY_XYZ].status: INSTRUCTED → SETTLED    (lifecycle event, no moves)
Obligation[obl_securities].state: Pending → Discharged
Obligation[obl_cash].state: Pending → Discharged
```

**No balance moves.** Positions are already correct from T. The depot reconciliation now matches. This is the precise v10.3 §13.7 statement; we are preserving it.

---

## 3. Invariants

### MANDATORY: Economic Exposure at T (E1)

```
∀ tx ∈ MoveStream where tx.type ∈ {SETTLEMENT, COLLATERAL}:
   ∀ wallet w, unit u:
      balance(w, u, t)  for any t ≥ tx.timestamp
   reflects the trade-date moves immediately,
   regardless of settlement status.
```

**Corollary:** the PnL function (v10.3 §3) computes from move-stream-derived positions; it never branches on `lifecycle_stage`. Mark-to-market between T and T+ISD is the same code path as steady-state.

### Conservation Preservation Across the Open Window (E2)

```
For every transaction tx of type SETTLEMENT:
   Σ_w Δ balance(w, u) = 0  ∀ u  at commit time (T, not T+ISD).
   The lifecycle events EXECUTED → INSTRUCTED → SETTLED add NO new moves;
   conservation is therefore preserved trivially across these transitions.
```

### Reconciliation by Construction (E3)

```
At any t:
   depot(custodian, u)  ?=
      Σ_{w ∈ real} balance(w, u)  +  Σ_{tx open, leg in u} sign × tx.quantity
                                  -- "open" = INSTRUCTED ∧ ¬SETTLED ∧ ¬FAILED
```

This is the ledger-side identity. The depot lags by ISD-1 days **by design**; the open-tx adjustment is the explicit lag term. A break is *not* failure of E1 or E2 — it is failure of the depot-message integrity (out-of-sequence sese.025, missing camt.054, etc.) and is logged to `BreakRegister` L₁₈.

### Idempotency of Settlement Confirmations (E4)

Inbound `sese.025` carries the `EndToEndId` we generated. Idempotency token = `EndToEndId`. Any duplicate `sese.025` is a no-op once the obligation is `Discharged`. (Aligns with C2 idempotency contract on the executor.)

### Obligation Closure (E5, κ-totality)

```
Every settleable transaction of type SETTLEMENT or COLLATERAL
generates an Obligation L₁₅ row per leg.
Every Obligation row reaches a terminal state (Discharged | Compensated | Defaulted)
within the regulatory horizon T_max = 60 calendar days for cash equities.
```

This is the §13 obligation-liveness theorem applied to settlement.

### CSDR Cash Penalty Accrual (E6)

```
For every Obligation in state Pending at end-of-day t > ISD:
   accrue_penalty = qty × ref_price × bps_schedule(asset_class, t - ISD)
   book to wallet w_csdr_penalty_payable / w_csdr_penalty_receivable
```

Bps schedule is `PolicyConfiguration` L₇ᴾᵇ — versioned, governance-gated. The schedule changes (e.g. the 2024 ESMA recalibration) are restated bitemporally.

---

## 4. Reconciliation — Lead-Lag BY DESIGN

The Ledger leads. The depot follows by ISD business days.

| Reconciliation | Cadence | Tolerance | Break wallet | Owner |
|---|---|---|---|---|
| Custodian depot vs Ledger position + open inflight | Daily T+1 | 0 (whole shares) | `wf-position-break` | Middle office |
| Cash nostro vs Ledger USD virtual wallet for broker | Daily T+1 | 0 | `wf-cash-break` | Treasury ops |
| CSD `sese.024` participant statement vs Ledger open obligations | Daily | 0 (count, qty) | `wf-settlement-break` | Settlement ops |
| Trade Repository (DTCC, REGIS-TR) ack of MiFIR / EMIR Refit reports | T+1 | ack closed-sum match | `wf-regsub-break` | Regulatory ops |
| CSDR cash penalty advice vs accrued | Monthly | bps tolerance | `wf-csdr-penalty-break` | Settlement ops |

**The reconciliation formula** (the Ledger-side identity):

```
expected_depot(u, t) = balance(w_portfolio, u, t)
                     + Σ_{tx ∈ open_buys at t}    qty_securities  -- delivered to us, not yet in depot
                     - Σ_{tx ∈ open_sells at t}   qty_securities  -- left depot, not yet booked out
```

Equivalent and audit-friendly form using the inflight virtual wallet:

```
expected_depot(u, t) = balance(w_portfolio, u, t)
                     - balance(w_csd_inflight_buys, u, t)   -- this is negative; represents pending IN
                     + balance(w_csd_inflight_sells, u, t)  -- pending OUT
```

This second form is mechanical: a single SQL `SELECT SUM(quantity)` over the inflight virtual wallet, which by §2 conservation must always be a closed account. **No interpretation. No bespoke logic.** This is the kind of representation the DRR golden-source approach demands.

---

## 5. CDM Cross-Walk

| Ledger object | CDM object | Status | Notes |
|---|---|---|---|
| `tx_BUY_XYZ` (SETTLEMENT type) | `BusinessEvent` with `PrimitiveInstruction.Transfer` | **Direct** | The CDM Transfer carries payer, payee, quantity, asset, settlementDate. |
| ISD on the transaction | `Trade.tradeDate.adjustableOrRelativeDate` + `settlementTerms.settlementDate` | **Direct** | CDM date adjustment machinery handles holiday rolls. |
| `lifecycle_stage` on tx | `TradeState.state.positionState` enum | **Partial** | CDM enum covers `Formed/Active/Terminated`; settlement-fail granularity (CSDR `BoughtIn`, `PendingDelivery`) is a CDM gap; ISDA DRR has been working on this under SFTR/EMIR fail reporting workstream. |
| Open Obligation | `BusinessEvent.beforeAfter` chain plus `Obligation` (Ledger-native) | **Missing in CDM** | Ledger-internal; CDM has no first-class obligation object. This is on the CDM gap register; tracked by ISDA Post-Trade WG as part of the 2026-2027 expansion. |
| Inflight virtual wallet | No CDM equivalent | **Missing** | Ledger-native. Could be modelled as a CDM `Account` with role=`SETTLEMENT_PENDING` if we wanted to push it back to CDM. |
| `sese.023` outbound | ISO 20022 message | **Direct** via CDM synonym layer | DRR mappings already standardised. |
| `sese.025` inbound | ISO 20022 message | **Direct** via CDM synonym layer | Idempotency by `EndToEndId`. |
| CSDR penalty `semt.0xx` | ISO 20022 message | **Partial** | CDM has no penalty type; ISDA DRR penalty workstream pending. |
| Buy-in instruction (CSDR Art 7a) | No CDM equivalent | **Missing** | Even after the 2024 scaling-back, the buy-in regime is regulator-mandated for some cash equities; ISDA position is to retain optionality. |

**The CDM gap on settlement-fail granularity is real and consequential.** ISDA's DRR programme has shipped EMIR Refit (Apr 2024), UK EMIR (Sep 2024), JFSA (Apr 2024), MAS / ASIC (Oct 2024), and Canada (Jul 2025). The next horizon is EU/UK MIFID and EU/UK SFTR. SFTR coverage *will* introduce CDM types for open settlement obligations under SFTs — and the deferred-settlement representation we adopt here should anticipate that, not pre-empt it. **We extend CDM via Ledger-native objects, mark them `Missing` in the cross-walk, and contribute the gap upstream.** This is the FINOS contribution model.

---

## 6. Failure Modes per Floor Case

### 6.1 CORE: T+2 Buy (above), T+2 Sell (mirror)

Sell mirrors buy: securities move out at T, cash moves in at T, both legs `Pending` until `sese.025/camt.054`. Same reconciliation, same invariants. The FOP-only case (corporate action gift, reorg) sees only the securities leg open; cash side is `None` per the settlement projection.

### 6.2 T+1 (US since 28 May 2024; UK & EU target 11 October 2027)

**Structural status: parameter, not architecture.** ISD becomes T+1 instead of T+2; the reconciliation lag is one business day instead of two; everything else is identical. The Ledger reads `settlementCycle` from `ProductTerms[u]` per market venue (US listed equities = T+1 from 2024-05-28; non-US ≠ T+1 yet) — this is `CalendarConvention` L₄ data plus venue-specific override.

What changes operationally: pre-matching window collapses; Asia-Pacific operating-model becomes brittle (FX matching, dual-listed pairs). **The Ledger architecture absorbs this without modification because the ISD is a parameter on the settlement instruction, not an assumption baked into invariants.** This is the test of a CDM-native architecture: the rule change becomes a config change, not a re-architecture.

**ISDA position**: the move to T+1 in EU/UK is industry-supported, conditional on resolving the FX timing gap (a derivative-and-cash-equity issue) and the corporate-actions standard-setting work. The ESMA report of 7 February 2024 set the path; the FCA confirmed alignment in 2024.

### 6.3 Failed Settlement (CSDR — EU; Reg SHO Rule 204 — US; analogous regimes elsewhere)

```
Day ISD: sese.025 FAILED inbound
   → MoveStream[tx].status: INSTRUCTED → FAILED
   → Obligation[obl_*].state remains: Pending
   → No reversal of moves. Economic position is unchanged.
   → Penalty accrual begins under E6.
```

**CSDR cash penalty regime** (in force since 1 Feb 2022; recalibrated 2024; further refinements Q1 2026 expected via ESMA technical standards):
- bps × ref price × qty × calendar days late
- Booked daily to `w_csdr_penalty_*` virtual wallets
- Settled monthly via T2S net penalty advice
- Schedule lives in `PolicyConfiguration` L₇ᴾᵇ, versioned (rule-set axis of the v1.0 data spec versioning algebra)

**CSDR mandatory buy-in regime**: the original 2022 implementation was suspended; the 2024 review reinstated a discretionary regime for specific high-fail instruments. The Ledger emits a buy-in obligation when triggered:

```
On day ISD + buyin_trigger_days (default 4 for liquid equities):
   Obligation_buyin = NEW Obligation, type=BuyIn, terminal_deadline=ISD+10
   When buy-in executes: a NEW SETTLEMENT transaction is appended that:
     - cancels the original (CORRECTION type, idempotency by orig_tx_id)
     - settles the buy-in price differential as a CASH transfer
     - economic position is preserved (we still receive shares; price diff is the buy-in cost)
```

**FINRA Reg SHO Rule 204 (US)** — close-out by T+3 for fails on borrowed-and-sold positions. Same architecture: a fail beyond T+3 triggers a forced buy-in transaction. Reportable to FINRA via SLATE (Securities Lending and Transparency Engine) for the SBL leg, and via Reg SHO threshold-list reporting for the equity leg.

### 6.4 Partial Settlement

Partial settlement is a CSDR-required feature for some markets (T2S enables it). Inbound `sese.025` may carry `partial_qty` < instructed_qty.

```
Original: tx_BUY 100 XYZ
ISD inbound: sese.025 PartiallySettled, qty=60
   → MoveStream[tx].status: INSTRUCTED → PARTIALLY_SETTLED
   → Two child obligations:
        Obligation_part1: Discharged (60 qty)
        Obligation_part2: Pending    (40 qty, deadline = original + extension)
```

**No new economic moves.** The trade-date position remains 100. The depot vs Ledger reconciliation now shows: 60 on depot, 40 still in `w_csd_inflight`. Conservation holds. CSDR penalty accrues only on the 40 remaining shares.

When the second tranche settles: `Obligation_part2.state = Discharged`. The original tx status moves `PARTIALLY_SETTLED → SETTLED`.

### 6.5 Reconciliation Break

Depot value diverges from Ledger expectation. Causes: missed `sese.025`, out-of-sequence message, custodian operational error, broker commingling.

```
Daily reconciliation activity:
   diff = depot - expected_depot
   if abs(diff) > tolerance:
      open BreakRegister L₁₈ row, state=Open
      assign owner (middle office)
      timer: T+1 → Aged-1, T+3 → Aged-3, T+5 → Aged-5, > T+5 → Escalated
```

**Critically: the break does NOT trigger a Ledger move.** The Ledger is the source of truth (v10.3 §2.7 self-consistency). The break is a discrepancy with the *external* world; resolution is by message replay, custodian inquiry, or exceptionally a `CORRECTION` transaction *if* an internal data error is identified.

### 6.6 Composition Cases

**Short sale (§13).** A short sale creates a negative `own` coordinate (GPM §13). Settlement still goes through inflight, but additionally consumes a `borr` coordinate via the SBL workflow. The settlement obligation is **two-sided**: deliver the borrowed shares to the buyer (T+2), and the borrow itself has its own term (open or fixed, T+0 same-day for opening, T+ISD for closing). The Ledger composes the two by entering two distinct obligations, each with its own ISD. **Reg SHO Rule 204** triggers off the failed delivery on the short side (T+3 close-out); **CSDR** triggers off the cash-settlement failure. **FINRA SLATE** reports the SBL leg same-day. All three regimes are emitted from the same move stream by separate DRR-generated reports.

**Recall (SBL).** A recall is a state transition on the SBL loan unit (`sec:sbl-state-machine`). It has its own settlement window, distinct from the underlying equity settlement: the borrower must return shares within `recall_period` (typically 3 BD, market-specific). The recall obligation L₁₅ has its own ISD and its own potential fail; if the borrower fails to return, the lender may issue a buy-in. Same machinery, different unit.

**Corporate action.** A corporate action observed between T and T+2 is the canonical hard case. The ISDA position is clear: **economic entitlement follows trade-date ownership, not settlement-date custody**. (Record date and ex-date are venue-specific; T+1 has shifted record dates by one day in the US.) If the dividend goes ex on T+1 and we are the buyer, the seller owes us a `manufactured dividend` for the period between T and ex-date — booked as a separate obligation against the seller. This is independent of the settlement of the equity itself. Fan-out workflow in v10.3 §11 handles this; we connect: the corporate-action manufactured-payment obligation is registered when the CA event lands and the original settlement is still open.

**Cross-currency (Herstatt).** A cross-currency cash equity buy (e.g. USD-denominated stock paid for in EUR via FX leg) has **two distinct settlement windows** that may not align. Herstatt is the asynchronous-settlement risk where one currency leg settles in Tokyo but the other has not yet settled in New York. The Ledger represents this with two SETTLEMENT transactions (or one SETTLEMENT with two cash legs in different currencies, but the projection emits two ISO 20022 messages). **CLS (Continuous Linked Settlement)** is the industry mitigant; the Ledger encodes "settlement venue = CLS" on the cash leg. v10.3 §2.7 already names this risk and the framework's modelling stance: represent the asynchrony explicitly via leg-level settlement status; do not model PvP atomicity unless CLS is the venue.

**DvP atomicity.** v10.3 §9.5 distinguishes Ledger-level DvP (transaction atomicity by construction) from settlement-level DvP (CSD guarantees). We preserve this: the *transaction* is atomic; the *settlement instructions* are processed by the CSD which enforces real-world DvP. The temporal gap between trade-date economic recognition and settlement-date custody movement is **the Ledger's primary representational task** for cash equities. We discharge it via the inflight virtual wallet + obligation pair.

---

## 7. Worked Example — 100 XYZ @ $50, T+1 mark to $52

### State table

| Time | tx state | XYZ pos (portfolio) | XYZ pos (broker virtual) | XYZ inflight (buys) | USD pos (portfolio) | USD pos (broker virtual) | depot(XYZ) | Open obligations | PnL |
|---|---|---|---|---|---|---|---|---|---|
| T-1 (pre) | — | 0 | 0 | 0 | 10000 | 0 | 0 | — | 0 |
| T (post-trade) | EXECUTED | **100** | -100 | -100 | 5000 | 5000 | 0 | obl_sec, obl_cash both Pending | 0 (just filled) |
| T+1 (px=$52, no events) | EXECUTED | 100 | -100 | -100 | 5000 | 5000 | 0 | both Pending | **+$200** (mark-to-market) |
| T+2⁻ (instructed) | INSTRUCTED | 100 | -100 | -100 | 5000 | 5000 | 0 | both Pending | +$200 if px holds |
| T+2⁺ (settled) | SETTLED | 100 | -100 | **0** | 5000 | 5000 | **100** | both Discharged | +$200 if px holds |

**Conservation check at T:**
ΔXYZ (real wallets) = +100; ΔXYZ (virtual wallets) = -100; sum = 0 ✓
ΔUSD (real wallets) = -5000; ΔUSD (virtual wallets) = +5000; sum = 0 ✓

**Reconciliation check at T+1:**
expected_depot(XYZ) = balance(portfolio) - balance(inflight_buys) = 100 - 100 = 0 ✓
actual_depot(XYZ) = 0 ✓ (custodian has not yet booked anything)

**Reconciliation check at T+2⁺:**
expected_depot(XYZ) = balance(portfolio) - balance(inflight_buys) = 100 - 0 = 100 ✓
actual_depot(XYZ) = 100 ✓ (custodian SETTLED)

**The price of XYZ moving from $50 to $52 on T+1 produced PnL of +$200 with zero cash movement and zero settlement movement.** This is what the Ledger must guarantee. Trade-date accounting is the rule; settlement-date timing is mechanics.

### What gets emitted, when

| Event | Where | When | Receiver | DRR rule-set |
|---|---|---|---|---|
| Trade booking | `MoveStream` L₁₃ | T (sub-second) | internal | — |
| MiFIR transaction report | `RegulatorySubmission` L₁₇ | T+1 EOD | FCA / ESMA | MiFIR RTS 22 |
| EMIR Refit report (only if equity is part of a derivative settlement, e.g. equity TRS underlier) | L₁₇ | T+1 EOD | TR (DTCC, REGIS-TR, KDPW) | EMIR Refit 2024 |
| `sese.023` outbound to CSD | settlement layer enrichment | T to T+ISD-1 | Euroclear / DTC / etc. | ISO 20022 |
| `sese.024` participant statement reconciliation | L₁₈ | Daily | internal | — |
| `sese.025` inbound | `ExternalConfirmation` L₁₁ | T+ISD | internal | — |
| CSDR penalty advice (`semt.0xx`) | L₁₁ | Monthly if any fails | internal → ESMA | CSDR Art 7 |
| Pillar 3 Operational Risk disclosure (failed-settlement aggregate) | L₁₇ | Quarterly | NCA | BCBS 2026 machine-readable |

**The unifying principle: every emission is a deterministic projection of the move stream + L₁₇ rule-set version pin.** The DRR golden-source code generates each of these reports from a single underlying truth. There is no firm-specific reinterpretation. There is no manual mapping. This is the position ISDA, IIF and GFMA submitted in the March 2026 BCBS machine-readable Pillar 3 response, and it applies directly to settlement reporting.

---

## 8. Regulatory Footprint — what the Ledger MUST emit and when

### 8.1 During the open window (T to T+ISD)

| Emission | Trigger | Cadence | Format | Regime |
|---|---|---|---|---|
| MiFIR transaction report | New trade | T+1 by 23:59 local | RTS 22 XML / ARM | MiFIR Art 26 (EU); FCA TR (UK); SEC CAT (US, equivalent rule) |
| Best execution / RTS 28 inputs | New trade | Quarterly aggregate | — | MiFID II (EU); FINRA Rule 5310 (US) |
| Pre-settlement matching status | sese.023 sent | T+1 to T+ISD | sese.024 reconcile | T2S settlement discipline (EU); CNS (US) |
| OFAC / EU sanctions screening | New trade with sanctioned LEI/jurisdiction | Pre-trade or T (block-and-report) | internal SAR feed + NCA | OFAC; EU sanctions reg |
| FINRA SLATE (if SBL leg involved) | T (same-day) | Same day | XML | FINRA Rule 6500 series |
| Short Sale Reporting (FINRA Rule 4560 / SEC Rule 13f-2 / EU SSR) | New short, T+1 net position | Daily/biweekly | XML / CSV | Reg SHO + SSR |

### 8.2 Open window exposure

The firm is exposed to the following risks during the open window — each must be quantified by the Ledger and surfaced to risk and treasury:

1. **Settlement risk (counterparty failure to deliver)**: capital charge under CRR Art 378–380 for unsettled transactions beyond ISD+4. Calculated as `qty × max(0, market_price - contract_price) × CRR_factor(days_late)`. Daily, at end-of-day, on the open obligation register.
2. **CSDR cash penalty exposure**: see E6. Material at scale; one mid-tier broker reported €15M annual penalty exposure pre-suppression.
3. **Mandatory buy-in cost (where applicable)**: market-price differential on forced replacement of failed delivery.
4. **Liquidity exposure**: funding cost of any cash sent against unsettled delivery. T+1 has reduced this versus T+2 by ~50%, but it is not zero.
5. **Reputational / regulatory escalation**: persistent fails feed into SREP supervisory review (EU CRR), the FRB's CCAR (US), and BCBS Pillar 2 capital add-ons.

The Ledger surfaces all five from a single object: the **open Obligation register**. Quantification is mechanical; downstream consumers (RWA engine, treasury liquidity dashboard, regulatory reporting) read the same data. **One golden source.**

### 8.3 Post-settlement reports (T+ISD onward)

| Emission | Trigger | Cadence | Regime |
|---|---|---|---|
| EMIR Refit (for derivatives that settle physically and reference equities, e.g. equity options, TRS) | T (with settlement linkage) | T+1 | EMIR Refit Art 9 — **DRR live as of Apr 2024** |
| SFTR (for any SFT leg attached) | T (NEWT) | T+1 | SFTR — **DRR coverage in progress; ISDA position: keep dual-sided reporting until reform delivered** |
| Pillar 3 settlement-fail disclosure | Quarterly aggregate | Q+45 days | BCBS Pillar 3 — **machine-readable in proposal stage; ISDA/IIF/GFMA Mar 2026 response advocates DRR-backed delivery** |
| FRTB reporting (settlement risk component of CVA) | Daily / monthly | various | Basel III Final |
| MMF stress / 2020 cash dash legacy reports | Quarterly | various | post-2020 G20 work; tokenisation of MMF collateral mitigates the structural problem |

### 8.4 The accounting-vs-reporting distinction

**IFRS 9 / IAS 39 (Europe), ASC 320 / 326 (US):** trade-date accounting is the standard for financial assets in trading books. Settlement-date accounting is permissible for some HTM portfolios and certain regulatory views, but is the exception, not the norm.

**Regulatory reporting:**
- MiFIR: **trade-date** (T+1 archive submission)
- EMIR Refit: **trade-date** for the `Trade` event; lifecycle events follow their own dates
- SFTR: **trade-date** for NEWT
- CSDR: **settlement-date** (penalty calc starts at ISD+1)
- BCBS Pillar 3 settlement-fail metrics: **as of report date**, accumulating from settlement-date triggers
- Capital (CRR for unsettled): **kicks in from ISD+4** (settlement-date triggered)

**Implication for the Ledger:** the move stream must support BOTH date axes simultaneously. Trade-date is the primary axis (when the move was committed). Settlement-date is a secondary index, derived from `obligation.terminal_state_date`. The data layer L₁₃ + L₁₅ + L₁₁ already supports this; the bitemporal model is `t_obs` for trade time, `t_known` for restatement. **There is no need to maintain two ledgers.** Multi-axis reporting is a query, not a duplicate truth.

This is the IFRS / regulatory dichotomy ISDA has made the central case for in successive position papers: **a single CDM-native source produces both views by deterministic projection**. Firms that maintain separate trade-date and settlement-date general ledgers are paying for duplication that the architecture does not require.

### 8.5 Tokenised securities settlement — the direction of travel

ISDA's position on tokenised securities (2025 GDF working group output; the Aug 2025 industry report "Ready for Adoption, Time to Act"; the DTCC Great Collateral Experiment Apr 2025; the CFTC GMAC subcommittee recommendation Sep 2025) is:

**Tokenisation enables atomic DvP at T+0** by collapsing the settlement window. The technology is ready. The blockers are legal (jurisdictional treatment of digital settlement finality; particularly Ireland and Luxembourg for tokenised MMF) and regulatory (Basel crypto-asset standard scheduled for Jan 2026, scaled-back Nov 2025; CFTC cross-border tokenised collateral consultation pending).

**Architectural implication for the deferred-settlement representation:** the framework must degenerate cleanly to T+0 atomic. In our representation, T+0 atomic settlement means:
- `tx.timestamp = T = ISD`
- `obligation.discharge_predicate = ByAttestation` with an on-chain settlement-finality oracle
- The inflight virtual wallet exists for zero seconds; the obligation is `Discharged` in the same atomic transaction that creates it
- Reconciliation with the chain depot is moot because the chain IS the depot

This is the v10.3 §1.6 statement on tokenised units (NVDA vs NVDA_TOKEN are distinct units) carried forward. **The deferred-settlement representation we adopt for cash equities at T+2 must be the SAME machinery, with the obligation horizon as a parameter.** This is the single most important degeneracy test: if the spec works for T+2 *and* T+0 atomic by changing one number, we have built it correctly. Otherwise we have hardcoded a regulatory state of affairs into the architecture, and we will pay for that hardcoding in 5 years.

### 8.6 ISDA / IIF / GFMA aligned views

- **DRR as the golden source for settlement-related reporting.** The Apr 2024 EMIR Refit DRR delivery and subsequent expansions (Sep 2024 UK EMIR; Oct 2024 ASIC / MAS; Jul 2025 Canada; Sep 2025 HKMA) demonstrate that consistent, multi-regime reporting is achievable from one CDM-native code base. Banque Pictet, BNP Paribas, JSCC, JPMorgan are live in production; 13 firms in PoC. The next horizon explicitly includes EU / UK MIFID and EU / UK SFTR — both of which touch the deferred-settlement representation directly.

- **ESMA call-for-evidence (Sep 2025 ISDA response).** Deferred settlement is not the headline of this paper, but the underlying argument applies: the firm that maintains its own bespoke interpretation of "settlement obligation" will incur the duplication cost. The firm that adopts CDM + DRR will not.

- **BCBS machine-readable Pillar 3 (Mar 2026 IIF / ISDA / GFMA response).** Failed-settlement aggregates are a candidate Pillar 3 disclosure. Our position: deliver these via DRR / CDM, not via a bespoke XBRL taxonomy that re-implements the rule logic. This is the same point: every duplicate representation is a divergence vector.

- **Tokenised collateral and settlement (ISDA GDF + Project Guardian).** The end-state of cash-equity settlement is T+0 atomic on tokenised representations. The deferred-settlement architecture must converge on this asymptotically. Hardcoding T+2 is technical debt with a known due date.

---

## Summary

The deferred-settlement representation is implementation-ready and consists of:

1. **An inflight virtual wallet per (CSD, omnibus, book)**, fully inside the closed-ledger conservation system (v10.3 §2). Carries the open delivery exposure.
2. **A per-leg `Obligation` L₁₅ row** with FSM `Pending → Discharged | Compensated | Defaulted`, discharge-by-attestation against the matched ISO 20022 confirmation.
3. **`lifecycle_stage` on the transaction**, FSM `EXECUTED → INSTRUCTED → PARTIALLY_SETTLED → SETTLED | FAILED → BOUGHT_IN | CANCELLED`. Lives on `MoveStream[tx]`, never on the security unit.
4. **Six invariants (E1–E6)**: economic-exposure-at-T, conservation across the open window, reconciliation by construction, idempotency on confirmations, obligation closure, CSDR penalty accrual.
5. **A single reconciliation identity** between Ledger and depot, expressible as one SQL aggregate over the inflight virtual wallet — no interpretation.
6. **CDM cross-walk**: direct on the trade and settlement instruction; partial on lifecycle state granularity (a known CDM gap that ISDA DRR is closing); missing on Obligation and inflight wallet (Ledger-native, contributable upstream to FINOS).
7. **Failure modes covered**: T+2 buy/sell (canonical), T+1 (parameter-only change), CSDR fail with cash penalty + buy-in, partial settlement, recon break, short sale composing with SBL recall, corporate action with manufactured payment, Herstatt / cross-currency, DvP atomicity at both Ledger and CSD level.
8. **Regulatory footprint**: every emission is a projection of the move stream + L₁₇ rule-set version pin. MiFIR T+1, EMIR Refit T+1, CSDR penalty monthly, Pillar 3 quarterly, FINRA SLATE same-day. **One golden source.**
9. **Degeneracy to T+0 atomic** (tokenised settlement): the same machinery, with obligation horizon as a parameter, no architectural change. This is the test.

The architecture aligns with ISDA's published position, with the DRR coverage roadmap, and with the BCBS / IIF / GFMA position on machine-readable disclosure. Firms that adopt this representation are aligned with the direction of travel; firms that do not will accumulate the technical debt of every settlement-cycle change, every regulatory regime, and every tokenisation roadmap as discrete migration projects rather than configuration changes.

**Ship it.**
