# Phase 2 — Settlement Team Section: Regulatory Footprint

**Author seat:** ISDA Board Advisor (regulatory-reporter)
**Companion sections (other Settlement Team members):** State / FSM (transaction-level), Obligation Object (L₁₅), Conservation invariants, Move sequences, CDM cross-walk, Tests
**Date:** 2026-04-30
**Convergence anchor:** virtual wallets + L₁₅ Obligation + transaction-level FSM, with the **mandatory invariant Economic Exposure at T (E1)**.

---

## 0. Position relative to the Phase 1 corpus

Twenty Phase 1 proposals were submitted. They converge on a small structural answer that is also the answer ISDA has spent fifteen years pushing into industry practice:

- The economic position is recognised at T. Settlement-date accounting is rejected as a primary mode (Ashworth was emphatic; Jane Street, Geohot, Lattner, Karpathy, Feynman, Cartan, Halmos, Noether, Formalis, Matthias all concurred).
- The open obligation is a first-class object — an L₁₅ Obligation row, paired with a virtual-wallet contra-entry, plus a per-transaction `settlement_status` lifecycle FSM (`EXECUTED → INSTRUCTED → SETTLED | FAILED | PARTIAL | CANCELLED | BOUGHT_IN`).
- No new conservation law is introduced. Conservation holds at every state in the open window because virtual wallets close the books, and lifecycle transitions emit no moves.
- The mechanism degenerates by parameter to T+1, T+0, atomic DLT settlement, and cross-currency PvP. **Hardcoding T+2 is technical debt with a known expiration date.**

The role of this section is not to re-derive the architecture. It is to anchor the architecture in the regulatory reality — what the Ledger MUST emit, when, in which format, with which dedup discipline, against which rule set — and to document where ISDA has already shipped the golden-source code (DRR) that should be the only interpretation layer permitted between the move stream and the regulator's mailbox.

The unifying principle, which I will repeat throughout this section: **every emission is a deterministic projection of the move stream + L₁₇ rule-set version pin. There is no firm-specific reinterpretation. There is no manual mapping. This is the position ISDA, IIF and GFMA submitted in the March 2026 BCBS machine-readable Pillar 3 response, and it applies to every regulatory regime that touches the deferred-settlement window.**

---

## 1. The Definitive Regulatory Matrix

The following matrix is authoritative for the deferred-settlement extension. It defines, for each in-scope regime, what the Ledger MUST emit, when, in which format, the dedup key, the idempotency contract, and the versioning discipline. **Every row is implementable today; every row maps to an L₁₇ RegulatorySubmission row generated as a deterministic projection of L₁₃ (MoveStream) + L₁₅ (Obligation) + the pinned rule-set code.**

| Regime | Trigger | What MUST be emitted | Format | Cadence / Deadline | Dedup key (idempotency) | Rule-set pin | DRR status |
|---|---|---|---|---|---|---|---|
| **MiFIR Art 26 (RTS 22)** | New trade in scope (EU/UK/CH listed equity, derivative on equity) | Transaction report incl. ISIN, MIC, LEI buyer/seller, qty, price, exec ts, trader ID | RTS 22 XML via ARM → ESMA / FCA | T+1 by 23:59 local of NCA | `(reporting_lei, internal_tx_id, version)` → `transactionReferenceNumber` | MiFIR/RTS 22 v3 (post-2025 review) | **In progress (EU/UK MIFID on DRR roadmap; not live)** |
| **EMIR Refit Art 9** | New OTC derivative (incl. equity TRS, equity options, single-name CDS); lifecycle event | Trade report + lifecycle reports incl. UTI, UPI, LEI, action type, event type | ISO 20022 auth.030 (or XML) → DTCC / REGIS-TR / KDPW | T+1 (T+2 in UK from 30 Sep 2024 for some events) | `(reporting_LEI, UTI, action_type, event_type, sequence_number)` | EMIR Refit RTS 2022/1855 + ESMA validation rules | **LIVE (Apr 2024 EU; Sep 2024 UK)** |
| **CSDR Art 7 (settlement discipline)** | Settlement instruction; daily fail status; monthly penalty cycle | Daily fail register; monthly `semt.044` penalty advice (received from CSD); buy-in instruction (where re-introduced) | ISO 20022 `sese.024/025/027`, `semt.044` inbound; CSD-side outbound | Daily T+ISD+1 …; monthly penalty cycle | `EndToEndId` on `sese.023` outbound; `MessageId` on inbound | CSDR RTS 2018/1229 (penalty calc) + 2024 amendment | **Not in DRR** (CSDR is settlement, not transaction reporting; ISDA position: the DRR engine should still be the audit-trail anchor for fail attribution) |
| **SFTR Art 4** | New SFT (repo, sec lending, BSB, margin lending) | Trade report incl. UTI, action type, principals, collateral schedule | ISO 20022 auth.052 → REGIS-TR / DTCC | T+1 dual-sided | `(reporting_LEI, UTI, action_type, event_date)` | SFTR RTS 2019/356 | **In progress (in DRR roadmap; ISDA position: keep dual-sided until reform delivered, then migrate)** |
| **FINRA SLATE (Rule 6500)** | New SBL or covered loan; modifications; close-outs | Loan-level report incl. CUSIP, qty, rate, collateral, term, lender/borrower | XML to FINRA SLATE | Same-day for new loans (T = trade); modifications T+1 | `loan_id` (FINRA-assigned) + `event_seq` | FINRA Rule 6500 series (effective Jan 2026) | **Not in DRR** (FINRA scope; should be added) |
| **Reg SHO (Rule 200, 203, 204)** | Short sale; locate; FTD past T+3 (T+5 MM) | Locate record (internal); FTD report; threshold securities list | SEC EDGAR + FINRA OATS-equivalent | T (locate); EOD T+3 (FTD); daily threshold | `(broker, CUSIP, trade_date, locate_id)` | SEC Rule 200/203/204 + Reg SHO | **Not in DRR** |
| **Pillar 3 / BCBS 239 (settlement-fail metrics)** | Quarterly aggregate; capital aged buckets per CRR Art 379 | Failed-trade aggregate by ageing bucket (5/16/31/46+ days), gross/net, by counterparty class | XBRL (FINREP/COREP); machine-readable Pillar 3 (proposed) | Q+45 calendar days | `(reporting_lei, period_end, taxonomy_version, line_item_code)` | CRR Art 378–380; BCBS Pillar 3 (CD Mar 2026) | **Proposed: ISDA/IIF/GFMA Mar 2026 response advocates DRR/CDM template** |
| **MAR Art 16 (suspicious orders & transactions)** | Trade or order with abnormal pattern | STOR report | Free-form structured to NCA | "Without delay" upon detection | `(detector_id, ts, internal_alert_id)` | MAR RTS 2016/957 | **Not in DRR** (alert-driven, not deterministic projection; out of scope) |
| **IFRS 9 / IAS 1 / IAS 32 (financial statements)** | Periodic; settlement-fail material balance | Notes disclosure incl. settlement receivables, ECL, large exposures | iXBRL (ESEF) | Quarterly / Annual | `(entity_lei, period_end, taxonomy_version)` | IFRS 9.5.1.3, 5.5.5; IAS 1.55; IFRS 7.6 | **Cross-walk — accounting projection from move stream + obligation register** |

**Two design points the matrix encodes that are non-negotiable:**

1. **Every dedup key is content-addressed** on `(LEI, UTI/EndToEndId/transactionReferenceNumber, version)`. This is Λ10 (replay determinism) at the regulatory boundary. The regulator's TR / ARM acknowledgement (acknowledged-sum match) is the discharge predicate of the L₁₅ regulatory-submission obligation. **This makes the Trade Repository the natural reconciliation oracle for our regulatory completeness invariant** — exactly the discipline ISDA codified in the EMIR Refit DRR project, which delivered 100% TR acknowledgement under MAS rules and 98.2% under EMIR Refit (Capgemini/ISDA Industry Perspectives, Nov 2025).

2. **Versioning is bitemporal.** Rule sets change (the Mar 2024 CSDR penalty recalibration; the Sep 2025 ESMA validation table update; the Apr 2024 EMIR Refit go-live; the upcoming UK T+1 reformatting). The L₁₇ row carries the rule-set version pin (the ADR-9 / B9 boundary). A restatement (correction to a previously submitted report) carries the new version pin and references the prior submission. **There is no "regulatory time travel" outside this discipline** — and there is no need for one, because the move stream is bitemporally indexed by `(t_obs, t_known)` already. Every restatement is a deterministic projection of the move stream as it is now known to have been at the obs date.

---

## 2. CSDR Settlement Discipline — Cash Penalty, Discretionary Buy-in, Reporting Cadence

CSDR Art 7 in its current form (post-2024 review):

### 2.1 Cash penalty calculation (currently scaled-back regime)

The cash penalty is calculated **per failing instruction per business day in fail**, by the receiving CSD, and notified to participants via `semt.044` monthly:

```
penalty(instruction, day) = qty × ref_price × penalty_bps_rate(asset_class, fail_type, day - ISD)
```

where:
- `ref_price` = the late-matching reference price (closing price on day-of-fail or the last available, per CSDR RTS 2018/1229 Art 18);
- `penalty_bps_rate` is read from the asset-class table:
  - Liquid shares (continuously traded): 1.0 bps/day
  - Illiquid shares (other than SME-growth-market): 0.5 bps/day
  - SME-growth-market shares: 0.25 bps/day
  - Liquid sovereign debt: 0.10 bps/day
  - Other sovereign / corporate debt: 0.20 bps/day
  - Cash leg fail: ECB main refi rate × (days_late / 360), floored at 0
- The 2024 ESMA recalibration (Reg (EU) 2024/1623) refined the rates and tightened the cash-leg formula. Q1 2026 ESMA technical standards are expected to refine further.

**Ledger emission discipline:**
- The Ledger does **not** compute penalties autonomously. CSDs are the source of truth (T2S central penalty mechanism for the Eurosystem; bilateral CSDs for EU non-euro zone; UK CSDR is post-Brexit divergent but operationally aligned).
- The Ledger **records** the penalty as an L₁₅ Obligation of kind `CSDR_PENALTY` with payload `(rate_basis_points, days, source_lei, currency, semt044_msgId)`. This is exactly the schema in the data spec (ledger_data_v1.0 §Operational-CSDR — confirmed by the correctness-architect, finops, formalis, halmos, sbl proposals).
- The Ledger **reconciles** the CSD-issued penalty advice (`semt.044`) against the failing-day cursor on the open Obligation. A break (CSD bills us X; we accrued Y) opens a `wf-csdr-penalty-break` row in L₁₈.
- **PolicyConfiguration (L₇ᴾᵇ)** carries the bps schedule for the firm's own internal accrual estimate (used pre-`semt.044` arrival for capital and PnL). Versioned, bitemporally restateable.

**Dedup key for CSDR penalty messages:** `(csd_lei, semt044_msgId, settlement_date, instructing_party_lei)`. Idempotency: replay of `semt.044` is a no-op once the obligation is `Discharged`.

### 2.2 Discretionary buy-in framework

The original 2022 mandatory buy-in regime under CSDR Art 7(3) was suspended (Reg (EU) 2022/2554 amendment). The 2024 review reinstated a **discretionary** regime for specific high-fail instruments, enforceable via a new Art 7(3a). The Ledger MUST support both:

- **Buy-in trigger:** day `ISD + buyin_extension_days` (default 4 BD for liquid, 7 BD for SME-growth, 15 BD for illiquid). Configurable per CSD via L₄ (CalendarConvention) and L₁₆ (ReferenceMaster).
- **Buy-in agent:** external (CCP-facilitated or party-level). The Ledger emits a buy-in instruction (L₁₅ Obligation, kind `CSDR_BUYIN`) and consumes the buy-in execution as a fresh `SETTLEMENT` transaction with metadata linking to the original failed `tx_id`. Conservation is preserved by construction: the buy-in is a real trade; its moves live in L₁₃; the original failing trade is left in place (per E1).
- **Cash compensation (where buy-in is not feasible):** difference between the original price and the reference price (CSDR Art 7(7)) flows as a separate cash transaction. The original obligation transitions to `Compensated` (L₁₅ FSM terminal).

**Reporting cadence:**
- Daily fail register: `sese.024` inbound from CSD; the Ledger projects an internal aged-fail report visible to ops + risk.
- Monthly penalty cycle: `semt.044` inbound; the Ledger's L₁₇ `CSDR_PENALTY_CYCLE` submission is a reconciliation report (we received X penalties / paid Y), not a primary regulatory feed.
- **Annual CSDR ESMA-mandated penalty disclosure** in Pillar 3 (settlement risk section): aggregated by counterparty class, asset class, ageing band. This is the row that connects CSDR to the BCBS machine-readable Pillar 3 — and is exactly why ISDA's March 2026 IIF/ISDA/GFMA response argues for DRR/CDM as the template.

### 2.3 Trade Repository expectation

**The TR does not directly receive CSDR penalty data.** CSDR is a CSD/T2S regime; its primary repository is the central penalty mechanism (T2S CPM for the Eurosystem). However:
- **EMIR Refit** receives the **trade and lifecycle** data that lets the regulator reconstruct exposure on failed cleared/uncleared OTC equity derivatives.
- **MiFIR Art 26** receives the **transaction** for the underlying cash equity execution.
- The dedup key bridge is the `EndToEndId` on `sese.023` (outbound to CSD) which the firm SHOULD pin to `(reporting_lei, internal_tx_id)` and which the EMIR/MIFIR UTI maps to via the post-trade gateway. **This bridge is not standardised by ESMA**; it is operational practice. ISDA position: the bridge should be CDM-defined and versioned, eliminating per-firm interpretation.

---

## 3. T+1 Transition: Same Mechanism with Parameter, OR Genuinely Different?

### 3.1 The regulatory state of play

- **US:** T+1 since 28 May 2024 (DTCC; SEC Rule 15c6-1 amendment Feb 2023). **Done.**
- **UK:** Target 11 October 2027 (Accelerated Settlement Taskforce report, Mar 2024; FCA confirmation 2024).
- **EU:** Target 11 October 2027 (ESMA report 7 Feb 2024; Commission proposal Q4 2024 amending CSDR Art 5; co-decision 2025).
- **Switzerland (FINMA):** Aligned with EU/UK; SIX Swiss Exchange consultation 2025 → 2027 transition planned.
- **Asia-Pacific:** Mostly already T+2; some markets considering T+1 alignment but no firm dates as of Apr 2026.
- **India:** Already T+1 (since 2023); T+0 (optional) since 2024 for ~25 stocks.

### 3.2 Architectural answer: parameter, not architecture

**The Ledger architecture absorbs T+1 without modification because the ISD is a parameter on the settlement instruction, not an assumption baked into invariants.** This is the test of a CDM-native architecture: the rule change becomes a config change, not a re-architecture. Every Phase 1 proposal that addressed this point reached the same conclusion (Ashworth, Jane Street, Geohot, Karpathy, Lattner, Halmos, Cartan, Formalis explicitly).

The relevant parameter live in:
- `ProductTerms[u].settlement_cycle` (per ISIN × MIC), sourced from L₄ CalendarConvention + L₁₆ ReferenceMaster;
- `Trade.cdm_payload.settlementDate` (CDM-native, resolved at execution from venue/CSD data);
- L₁₅ Obligation `deadline` (computed at trade time);
- L₁₈ break-aging timers (`T+1, T+3, T+5, T+ISD+CSDR_buyin`).

**No code change** is required for the EU/UK move beyond the per-(MIC, ISIN) settlement-cycle table refresh and the CSDR penalty-window recalibration (the buy-in extension days collapse from `T+ISD+4` to `T+ISD+4` in absolute terms but operationally shorter from trade date).

### 3.3 But there ARE structural changes that matter

The architecture-vs-parameter argument is correct but incomplete. The T+1 transition surfaces structural changes that the Ledger architecture must *absorb* but that operational and risk machinery downstream must adapt to. ISDA's published positions on these:

**(a) FX cutoffs.** Cross-currency cash equities (US-domiciled buyer of EUR-denominated stock; CCP-cleared OTC equity TRS with USD-funded cash leg in EUR-denominated underlier). T+1 collapses the FX-funding window by half. CLS PvP cutoffs are 00:00 CET (00:00 GMT) for matching; participants must pre-fund or hedge same-day. **The Ledger represents this by tracking each currency leg as a distinct L₁₅ Obligation**, with `settlement_type=PvP` and the per-leg `csd_or_correspondent`. Herstatt risk is *named*, *quantified* (the asymmetric-state window = leg₁.SETTLED ∧ leg₂.non-terminal), but cannot be eliminated by ledger design alone. ISDA position (Aug 2025 industry report "Ready for Adoption, Time to Act"): tokenised collateral and atomic on-chain DvP are the long-run answer; CLS expansion is the medium-term answer. The deferred-settlement representation must compose with both.

**(b) ETF NAV cycle.** EU ETFs settling T+1 against underlying baskets that may settle T+2 (e.g., Asian underliers) introduces a **multi-cycle obligation graph**. The L₁₅ Obligation framework absorbs this: the ETF creation/redemption is a parent obligation whose discharge predicate is the conjunction of the basket-leg obligations' discharges. This is the same DvP-pair pattern Herstatt uses, generalised. ISDA, ICMA, EFAMA joint position (2025): industry-led harmonisation of basket-side settlement cycles where possible; legal carve-outs in CSDR Art 5 amendment for unavoidable mismatches.

**(c) DTC night cycle (US specific).** The US move to T+1 eliminated the DTC night cycle as a meaningful settlement window — affirmation/matching cutoffs collapsed to 9pm ET on T (or 11:30 AM ET on T+1 in the post-2024 cycle). For non-US firms operating into US markets, this means **affirmation must complete same-day from the firm's local time zone**. Operationally severe for Asia-Pacific desks. Architecturally, the Ledger absorbs this — it is a deadline parameter — but the workflow timer machinery must support per-jurisdiction calendars without manual override. v11.0 has this via L₄ + L₁₆ pinning.

**(d) Corporate actions standard-setting.** ESMA-recognised gap: cum/ex-date conventions, manufactured payments, and the cum-dividend trade window (a buy on T+0 cum-div with ex-date T+1 with record-date T+2 — under T+1, the buyer settles on record date, fundamentally changing entitlement chains). ISDA, AFME, and the European Post-Trade Industry Forum are working with ESMA on a 2026 RTS amendment. **The deferred-settlement architecture handles this via the manufactured-dividend obligation pattern (already in v10.3 §13)** — but the regulatory machinery for who pays whom is jurisdictionally fragmented and is the reason the EU/UK transition slipped from initial 2026 ambitions to October 2027.

**(e) EU/UK fragmentation.** Until October 2027, EU markets are T+2 and UK markets are T+2. From October 2027, both transition to T+1. From the architecture's perspective, this is settled by `ProductTerms[u].settlement_cycle` per (MIC, ISIN). From the regulator's perspective, this means the Ledger must support **per-trade per-leg per-jurisdiction** settlement cycles without conflation. The DRR coverage roadmap supports this: the Apr 2024 EMIR Refit DRR delivery was concurrent with the UK EMIR DRR (Sep 2024), with the per-jurisdictional rule pin done via `cdm_version` + `regime_pin`.

### 3.4 The summary

**The mechanism is the same; the parameters are different; the operational risk surface is materially different; the regulator-perceived risk is materially different.** The Ledger architecture is correct to model T+1 as a parameter. The deferredSettlement.tex companion document MUST explicitly state: "the architecture does not encode T+2; it encodes a horizon parameter sourced from CDM/L₄/L₁₆." This is the line that future-proofs the design against the next horizon shift (T+0 atomic).

**ISDA position summary:** the EU/UK move to T+1 is industry-supported, conditional on (i) FX timing reform, (ii) corporate-actions harmonisation, (iii) operational readiness on the buy-side and on Asia-Pacific operating models. Each of these has a workstream. The Ledger architecture is on the correct side of each.

---

## 4. T+0 / Atomic DLT Settlement — ISDA's Evolving Position

### 4.1 The direction of travel

ISDA's published positions are unambiguous: **tokenisation enables atomic DvP at T+0 by collapsing the settlement window. The technology is ready. The blockers are legal and regulatory.**

Workstreams that establish this:
- **2023 Digital Asset Derivatives Definitions** — provides the legal scaffolding for derivatives on tokenised securities and digital assets.
- **2023 Tokenised collateral model provisions for 2016 CSAs** — bilateral collateral on tokenised MMFs and other digital assets.
- **GDF Working Group (2024-2025)** — seven structures for tokenising MMFs analysed; Ireland and Luxembourg as primary jurisdictions for legal certainty on settlement finality.
- **ISDA / Ant International Project Guardian report (Jul 2025)** — tokenised bank liabilities for cross-border payments, with implications for CSA cash collateral.
- **DTCC Great Collateral Experiment (Apr 2025)** — proves end-to-end tokenised collateral mobilisation across CCP, CSD, and bilateral books with sub-second settlement.
- **CFTC GMAC Digital Assets Market Subcommittee recommendation (Sep 2025)** — remove cross-border MMF tokenised collateral restrictions; CFTC consultation on tokenised eligible collateral pending.
- **Aug 2025 industry report "The Impact of Distributed Ledger Technology in Capital Markets: Ready for Adoption, Time to Act"** — explicit industry call for action on the legal/regulatory path.
- **AI + CDM whitepaper (2025)** — LLM extraction of CSA clauses into CDM at >90% accuracy, demonstrating that AI is the extraction layer and CDM is the structured output for legal-document digitisation.

### 4.2 Specific blocking points (and ISDA's response on each)

- **Basel crypto-asset standard (scheduled Jan 2026, scaled-back Nov 2025).** ISDA / industry called for pause and recalibration: the original prudential capital regime treated tokenised securities as crypto-assets, attracting punitive capital. BCBS announced targeted review (Nov 2025); the revised regime is expected to distinguish between "tokenised traditional assets" (treated as the underlying) and "crypto-assets sensu stricto" (the original 1250%/SA-CR regime). **ISDA position: the deferred-settlement architecture should not be tied to a regulatory regime that is presumptively transitional.**

- **CFTC cross-border tokenised collateral restrictions.** CFTC Sep 2025 consultation (open as of Apr 2026) on amending Reg 1.20–1.25 to permit cross-border MMF tokenised collateral. ISDA / industry response: support, with technical guard-rails on legal opinions per jurisdiction (the GDF working group's seven-structure analysis is the input).

- **Settlement finality opinions.** Tokenised securities require jurisdiction-specific legal opinions on (i) when the on-chain transfer is final under the local law; (ii) how it interacts with insolvency stays. Ireland and Luxembourg published model legislation in 2024-2025; UK FCA digital sandbox + the DSS regime (DAR 2024) provides a UK regime; Switzerland FINMA has a stance via the DLT Act (since 2021). EU MiCA + the DLT Pilot Regime (since 2023) provide a fragmented but functional regime. ISDA position: **publish a jurisdictional matrix of settlement-finality opinions, analogous to the close-out netting opinion library**. This is in scope for ISDA's 2026-2027 workplan.

- **Identity/KYC at the chain layer.** Permissioned-chain models (HQLAx, Onyx, Fnality, Project Guardian) have identity built-in. Permissionless models require a chain-bridged identity layer. ISDA position: deferred-settlement at T+0 atomic is a permissioned-chain story for the foreseeable future; permissionless is research, not infrastructure.

### 4.3 Architectural test: degeneracy to T+0

The framework MUST degrade cleanly to T+0 by parameter change. **What changes structurally vs what stays:**

| Element | T+2 | T+1 | T+0 atomic on-chain |
|---|---|---|---|
| `Trade.settlementDate` parameter | T+2 | T+1 | T+0 (=T) |
| L₁₅ Obligation `deadline` | T+2 EOD | T+1 EOD | T+ε (or T+0+slot) |
| Discharge predicate | `ByMatch(sese.025)` | `ByMatch(sese.025)` | `ByAttestation(on-chain finality oracle)` |
| Virtual wallet inflight period | 2 BD | 1 BD | ε seconds (effectively zero) |
| Reconciliation to depot | Daily T+1 | Daily T+1 | Continuous on-chain query |
| Reconciliation to nostro | Daily T+1 | Daily T+1 | Continuous (nostro IS the chain) |
| CSDR penalty regime | Active (EU); Reg SHO (US) | Active | **Not applicable** (no fail) |
| DRR generation | Same | Same | Same (regime tag changes) |
| FX leg (cross-currency) | Two ISO 20022 legs, async | Two legs, tighter window | Atomic PvP via on-chain or CLS-on-chain bridge |
| Capital treatment (CRR Art 379) | Active from ISD+5 | Active from ISD+5 | **No unsettled-trade capital** |
| Pillar 3 settlement-fail metrics | Quarterly aggregate | Quarterly aggregate | Approaches zero |
| Buy-in regime | Discretionary (CSDR 2024) | Discretionary | N/A |
| ECL on settlement receivables | Required (de minimis CCP-cleared) | Required (de minimis) | **Approaches zero** |

**What stays constant:**
- The FSM (`EXECUTED → INSTRUCTED → SETTLED | FAILED | …`) — the FAILED branch becomes vanishingly improbable, but the FSM does not change.
- The L₁₅ Obligation object — the discharge predicate kind changes, the structure does not.
- Conservation invariants (E2) — preserved by construction at every horizon.
- Trade-date economic recognition (E1) — preserved by construction; T+0 just collapses the open window to zero.
- The DRR engine — same code, regime pin changes, output is the same shape.

**This is the test of the architecture.** Any design that requires re-architecture for T+0 atomic has hardcoded the regulatory state of T+2. The Phase 1 convergence (virtual wallets + L₁₅ Obligation + transaction-level FSM) passes this test by design.

### 4.4 The five-year view

The deferred-settlement representation we adopt for cash equities at T+2 in 2026 must be the SAME machinery that handles T+0 atomic on tokenised representations in 2030. **This is the single most important degeneracy test of the architecture.** Hardcoding T+2 is technical debt with a known due date. The architecture passes the test.

---

## 5. MiFIR Transaction Reporting (RTS 22)

### 5.1 The deadline

T+1 by 23:59 in the local time of the relevant NCA, per MiFIR Art 26(1). **Independent of settlement status.** A trade reported at T+1 cannot be deferred until settlement.

### 5.2 Fields impacted by deferred settlement

Per RTS 22 v2 (current; v3 anticipated post-2025 review):

- **Field 28 (Trading date and time):** = T (execution timestamp). NOT T+ISD.
- **Field 36 (Quantity):** = trade quantity. Unaffected by partial settlement.
- **Field 33 (Price):** = trade price. Unaffected by settlement status.
- **Field 41 (Buyer LEI), 49 (Seller LEI):** counterparties at trade. Unaffected.
- **Field 7 (Transaction reference number):** firm-internal unique reference. Should match `EndToEndId` on `sese.023` outbound for traceability — but this is a firm convention, not an ESMA mandate.
- **Field 64 (Transmission of order indicator):** unaffected.
- **Field 65 (Transmitting firm ID for the buyer / seller):** unaffected.

**Settlement status does NOT appear in RTS 22.** A trade is reported at T+1 regardless of whether it settles cleanly, fails, partially settles, or is bought-in. **Subsequent failures do not generate a MiFIR amendment.** The trade fact is the trade fact. (The fail/buy-in is captured in the CSDR machinery, not MiFIR.)

**Correction (CANCELLED at trade level, not settlement level)** does generate a MiFIR amendment:
- Trade entered in error → CANCELLED action under RTS 22 Field 3 (action type = `CANC`). Carries the original `transactionReferenceNumber`.
- Trade economic correction (price adjustment) → AMEND action. Less common in cash equities; more common in FX/derivatives.

### 5.3 Idempotency and dedup

RTS 22 dedup key: `(submitting_LEI, transaction_reference_number, action_type, submission_timestamp_to_NCA)`. The ESMA validation gate rejects duplicates with the same `transaction_reference_number` and same action type. **An amendment carries a new submission timestamp.** Cancellations are amendments with action `CANC`.

**The Ledger emission discipline:** the L₁₇ row carries the MiFIR submission with its dedup key as content-addressed identity. Replay produces a no-op via the regulator's deduplication logic. Restatement (amendment) is a new L₁₇ row referencing the prior submission's `transaction_reference_number`. This composes cleanly with the L₁₅ Obligation `Pending → Discharged` discipline: the regulatory submission is itself an obligation with a discharge predicate (NCA acknowledgement) and a deadline (T+1 23:59).

### 5.4 ISDA position

MiFIR Art 26 + RTS 22 has been live since 2018 (MiFID II) and is functional. **The 2025 review is in progress** (Q4 2025 ESMA technical advice expected); ISDA's response (Sep 2025 to ESMA's call for evidence) recommended:
- delineate scope by instrument type (ETD → MIFIR, OTC → EMIR, SFTs → SFTR);
- eliminate fields already embedded in LEI/UPI/ISIN;
- remove dual-sided reporting where one side is an investment firm and the other is its client;
- adopt DRR as the single golden-source code for MiFIR generation when EU/UK MIFID DRR coverage ships (currently in progress on the DRR roadmap, post-EMIR/SFTR).

**For the deferred-settlement extension specifically:** MiFIR is unaffected. The trade fact is reported at T+1 and the rest of the lifecycle (CSDR fails, partials, buy-ins) is not in MiFIR scope.

---

## 6. EMIR Refit / DRR (Live Since April 2024)

### 6.1 DRR status

The Digital Regulatory Reporting (DRR) initiative is the centrepiece of ISDA's golden-source agenda. As of Apr 2026:

- **Coverage shipped:** CFTC (Dec 2022), JFSA (Apr 2024), EMIR EU (Apr 2024), UK EMIR (Sep 2024), ASIC (Oct 2024), MAS (Oct 2024), Canada (Jul 2025), HKMA (Sep 2025).
- **In progress:** EU/UK MIFID, EU/UK SFTR, Switzerland (FINMA), SEC rules.
- **Production users (as of Nov 2025):** Banque Pictet, BNP Paribas, JSCC, JPMorgan (4 firms live).
- **Proof-of-concept firms (13):** Goldman Sachs, DTCC, DBS, and others.
- **TR acknowledgement rates (Capgemini/ISDA Industry Perspectives Nov 2025):** 100% under MAS rules; 98.2% under EMIR Refit.
- **Cost reduction:** up to 50% reduction in ongoing reporting costs vs bespoke firm implementations.
- **Recent integrations:** LSEG TradeAgent DRR integration (Mar 2026, CDM-native post-trade platform); JPMorgan FINOS open-source DRR implementation (Oct 2024); JSCC DRR adoption (Jan 2025).

**This is the operational proof.** A consistent, multi-regime reporting layer is achievable from one CDM-native code base. Firms that adopt this representation are aligned with the direction of travel; firms that do not will accumulate the technical debt of every reporting-rule change as a discrete migration project.

### 6.2 Fields the Ledger emits for cleared vs OTC equity derivatives that physically settle

For an equity TRS (OTC), an equity option (OTC), or a single-name CDS that physically settles into the underlying equity at expiry:

**At trade (T):**
- UTI (generated by the firm or by the CCP for cleared trades; ISDA UTI guidelines applied via DRR)
- UPI (from ANNA/DSB)
- Counterparty LEIs
- Action type = `NEWT`
- Event type = `Trade`
- Action timestamp = T
- Reporting timestamp = T+1
- Asset class fields (underlying ISIN, strike, expiry, notional, day-count convention, etc.)

**At lifecycle (settlement event for the physically-settled OTC):**
- Action type = `MODI` (modification on settlement)
- Event type = `Settlement` (CDM EventIntentEnum mapping)
- The cash leg reflected as a MODI on the original trade's notional / payment schedule
- The securities leg projected as a separate `SETTLEMENT`-type Ledger transaction (cash equity-style; settlement reporting then runs through the cash-equity matrix in §1).

**Cleared vs OTC distinction:**
- Cleared (CCP novation at T+0): the original bilateral trade is reported as `NEWT` with subsequent `EROS` (early termination) on novation; the two CCP-side trades are reported as separate `NEWT`s. Each retains its UTI through novation per the ISDA UTI guidelines.
- OTC (uncleared): single `NEWT`; no CCP-side reports; settlement is bilateral.

**For deferred-settlement on cash equities specifically (NOT EMIR-reportable as a derivative trade):**
- The cash equity itself is **not in EMIR scope** (EMIR is OTC derivatives; cash equity is MIFIR).
- The cash equity that is the **physical settlement of an OTC equity derivative** is reported via the OTC trade's lifecycle event. CSDR / settlement-discipline machinery applies to the cash-equity settlement itself.
- This means the deferred-settlement extension's regulatory footprint on EMIR is **only** the lifecycle-event reporting of the physically settled equity leg of an OTC trade. The cash-equity leg has its own MIFIR transaction report (per §5) and its own CSDR settlement-discipline footprint (per §2).

### 6.3 Dedup key for EMIR Refit

`(reporting_LEI, UTI, action_type, event_type, sequence_number)`. ESMA's validation rules table (regularly updated; current version v2.1 as of Q4 2025) defines acceptance criteria. DRR-generated reports pass the validation table by construction; firm-coded reports pass at the cost of bespoke validation logic per firm.

### 6.4 ISDA position

The EMIR Refit DRR delivery is **the canonical example** of the golden-source approach. The Sep 2024 UK EMIR DRR delivered the exact same pattern with a different rule pin. The Oct 2024 ASIC and MAS deliveries demonstrated that the model scales to non-EU regimes. **The deferred-settlement architecture should generate EMIR Refit lifecycle reports via DRR; it should not generate them via firm-bespoke code.** This is non-negotiable for any Ledger v11.0 implementation that touches OTC equity derivatives.

---

## 7. SFTR ↔ EMIR ↔ CSDR Overlap for SBL Trades in the Open Window

### 7.1 The tri-regime gotcha

A securities-borrowing transaction (SBL) on an EU-listed equity has a triple regulatory footprint:

- **SFTR (Art 4):** the SBL itself is reported as an SFT to the TR. Dual-sided reporting (lender + borrower).
- **EMIR Refit (Art 9):** if the SBL is part of a CCP-cleared chain (less common for SBL, but possible), the cleared leg is EMIR-reportable.
- **CSDR (Art 7):** the settlement of the SBL (open at T+0 same-day; close at T+ISD per the loan terms) is subject to CSDR settlement discipline; fails accrue cash penalties.

Plus, in the US:
- **FINRA SLATE (Rule 6500):** same-day reporting of new SBL; rate transparency post-trade.
- **Reg SHO (Rule 200, 203, 204):** locate, threshold, FTD close-out — applies to the equity leg of the short sale that the SBL is supporting.

### 7.2 UTI generation discipline

Each regime expects a UTI-equivalent identifier:
- **SFTR:** UTI per ESMA RTS 2019/356.
- **EMIR:** UTI per ESMA RTS 2017/104.
- **CSDR:** instructing-party reference (`EndToEndId` on `sese.023`).
- **FINRA SLATE:** `loan_id` assigned by FINRA on first submission.
- **Reg SHO:** broker-internal trade reference (no central UTI).

**The cross-regime mapping is operationally fraught and the source of recurring breaks.** ISDA's UTI guidelines (most recently Apr 2025 update) provide a uniform method for SFTR + EMIR via deterministic content-addressed generation:

```
UTI = LEI(generating_party) || hash_jcs(...trade_essential_terms...)
```

**The ISDA position:** the UTI is THE primary identity; firm-internal trade refs and `EndToEndId`s should be derived from the UTI, not the other way around. The Ledger architecture supports this directly via Λ10 (`tx_id = hash_jcs(business_event_id, attempt_seq)`) — the UTI is computed from the trade essentials at execution time and pinned for the trade's lifetime.

### 7.3 Value-date conventions — the load-bearing gotcha

**SFTR uses trade date for `event_date` and contractual settlement date for `value_date`.**
**EMIR uses execution timestamp for `execution_timestamp` and the lifecycle event date for the relevant action.**
**CSDR uses ISD (intended settlement date) for the penalty start; ISD is the contractual settlement date of the SBL leg.**

Where the gotcha lives: an SBL trade executed on Friday with same-day settlement (`T+0`) for the borrow's *initiation* and `T+ISD = T+30` for the *close* has FOUR distinct dates:

- T (trade date, in SFTR `event_date`)
- T (initiation settlement, in CSDR penalty-clock for the open leg)
- T+30 (contractual close date, in SFTR for the close-leg report)
- T+30 (close settlement, in CSDR penalty-clock for the close leg)

**A naive implementation conflates the trade date (T) with the close-settlement date (T+30) for SFTR, which silently mis-reports value dates.** This was a repeated finding in the 2022-2024 SFTR data quality reviews by ESMA.

**The Ledger architecture handles this** by treating the open and close legs as two distinct L₁₅ Obligations with separate `deadline` fields, separate `discharge_predicate`s, and separate L₁₁ ExternalConfirmation rows. The DRR-generated SFTR report reads from the obligation register, not from the trade transaction directly. **No bespoke field-mapping logic is required if DRR is used.**

### 7.4 The SBL-in-cash-equity-window composition (Phase 1 SBL proposal handles this)

A short sale at T uses an SBL borrow that itself settles same-day. Then the equity sale settles at T+2 (or T+1 post-transition). Three obligations are open simultaneously between T and T+2:

1. SBL borrow (settlement T+0, typically discharges fast)
2. Equity sale settlement (T+2)
3. SBL recall (open-ended, may fire mid-window)

**Each obligation has its own UTI / EndToEndId / loan_id.** Each is reportable to its own regime. The Ledger composes them by parallel obligations on the same underlying ISIN; no obligation is bypassed; the regulatory reports for each regime are independent projections of the relevant obligation's state.

### 7.5 ISDA position on dual-sided reporting

**ISDA's response to ESMA's 2025 call for evidence (Sep 2025):** delineate by instrument type, remove dual-sided reporting where the asymmetry is severe (one side is an investment firm and the other is its retail client), eliminate fields already embedded in LEI/UPI. **Do not reform SFTR until DRR is live for SFTR.** The regulatory burden of moving SFTR to single-sided before the DRR golden-source code is in place would create transition risk for limited benefit. Once DRR is shipped for SFTR, single-sided reporting becomes a configuration choice, not an implementation project.

---

## 8. FINRA SLATE Rule 6500 for Short Positions in the Window

### 8.1 SLATE in scope

FINRA Rule 6500 series (effective Jan 2026, with phased technical onboarding through Q3 2026) creates the Securities Lending and Transparency Engine (SLATE):
- All securities loans of US equities by FINRA member firms must be reported.
- Same-day reporting for new loans.
- T+1 reporting for modifications, terminations, and material amendments.
- Disclosure of rebate rates, term, collateral type — phased public dissemination beginning Q4 2026.

### 8.2 Interaction with Reg SHO

For a short sale of US equity backed by an SBL borrow:

- **At T (short sale execution):**
  - Locate (Reg SHO 203(b)) recorded internally; not externally reported but auditable by FINRA on inquiry.
  - The trade is MiFIR-equivalent reported via SEC CAT (US equivalent) at T+1.
  - The SBL borrow that supports the short is FINRA-SLATE reported same-day.

- **At T+1 (DTCC affirmation cutoff for T+1 settlement):**
  - Pre-settlement matching status; failed affirmation is a candidate for fail risk.

- **At T+2⁻ (one BD before settlement):**
  - Settlement instruction in flight at DTC; pre-CSDR the equivalent state.

- **At T+2 (US settlement) → fail:**
  - **Reg SHO Rule 204:** broker-dealer must close out the failed delivery by purchasing or borrowing securities of like kind and quantity by **start of the regular settlement of the third consecutive settlement day** (i.e., T+5 for non-MM, T+8 for MM); failure to close out triggers a strict liability buy-in.
  - **Threshold list (Rule 203(b)(3)):** if the security is on the threshold list (high FTD count), tighter close-out requirements apply.
  - **No equivalent of CSDR cash penalties in the US**; the close-out obligation is binary, not bps-based.

- **For the SBL leg specifically:**
  - SLATE close-out reporting fires when the SBL terminates (recall return, voluntary close, or buy-in).
  - The recall pattern (lender exercises right to recall) is handled by the SBL state machine; the recall has its own settlement deadline (typically 3 BD market-specific) and its own potential fail (lender may issue a buy-in if borrower fails to return). All three regimes (SLATE, Reg SHO, internal SBL state machine) are represented from the same move stream.

### 8.3 Dedup key

`(broker_lei, loan_id, event_seq, action_type)`. SLATE will return a `loan_id` on first submission; subsequent events use it as the primary key.

### 8.4 ISDA / ISLA position

ISDA + ISLA + AFME joint response (2024) on the SLATE NPRM advocated:
- alignment of SLATE reporting model with EMIR/SFTR (CDM-based);
- avoiding bespoke US-only field requirements;
- DRR coverage of SLATE as a 2026-2027 priority.

**As of Apr 2026, SLATE is live and DRR coverage is in scope but not shipped.** This is the highest-priority addition to the DRR roadmap from a US-equity-deferred-settlement perspective.

---

## 9. Pillar 3 / BCBS Machine-Readable Consultation

### 9.1 The consultation in scope

BCBS Consultative Document on machine-readable Pillar 3 disclosure (published Q1 2026; comment period closed Q1 2026). Industry response: IIF / ISDA / GFMA joint response (Mar 2026), positioning DRR + CDM as the natural template.

### 9.2 What this means for deferred-settlement disclosures

Pillar 3 disclosures relevant to the deferred-settlement window:

**(a) Failed-settlement quarterly aggregate.** Per CRR Art 379(2) ageing buckets (5 BD, 16 BD, 31 BD, 46+ BD), gross/net, by counterparty class (CCP-cleared vs bilateral), by asset class. **This is the single most important deferred-settlement Pillar 3 line.** Currently disclosed as XBRL; the BCBS proposal would migrate to machine-readable iXBRL with ESEF-aligned taxonomies.

**(b) Capital aged buckets per CRR Art 379.** Risk-weight progression on failing trades: 0% (T+0 through T+4); 9% (T+5–T+15); 50% (T+16–T+30); 100% (T+31–T+45); 1250% (T+46+). The Ledger surfaces all five buckets from a single object (the open Obligation register filtered by `lifecycle_stage = FAILED` and `days_past_ISD`).

**(c) Counterparty exposure during the open window (CRR Art 392).** Large exposures reporting on unsettled receivables that exceed thresholds. The Ledger already produces this from the move stream + L₁₅ register; the Pillar 3 line is an aggregate.

**(d) IFRS 9 ECL on settlement receivables (where IFRS-reporting).** De minimis for CCP-cleared; material for failed bilateral. Disclosed under IFRS 7.35F.

**(e) CSDR cash penalties paid/received.** Aggregated annually under CSDR Art 7 ESMA-mandated disclosure. Not currently a Pillar 3 line, but proposed for inclusion.

### 9.3 ISDA / IIF / GFMA position

The IIF / ISDA / GFMA Mar 2026 response made five points:

1. **Use CDM/DRR as the template.** Failed-settlement aggregates, Art 379 ageing buckets, and CSDR penalties are all derivable from the same underlying CDM Trade + Lifecycle event chain that DRR already reports for transaction-level data. **A separate XBRL taxonomy for Pillar 3 that re-implements the rule logic is duplication, not standardisation.** This is the same point as the deferred-settlement representation: every duplicate representation is a divergence vector.

2. **Permit Inline XBRL (iXBRL).** Allows human-readable disclosure with embedded structured data; reduces the burden on smaller banks who lack dedicated XBRL pipelines.

3. **Phased implementation.** Critical metrics (settlement-fail aggregates; CCR; LCR; NSFR) first; secondary metrics second. **Don't gate the delivery of high-value machine-readable on the lowest-priority taxonomy elements.**

4. **Proportionality for smaller banks.** Tier-2 / Tier-3 banks should have a simplified pathway; the full machine-readable burden is appropriate for Pillar 1 G-SIBs and large standardised banks.

5. **Co-design with industry.** The BCBS taxonomy should be developed in lockstep with FINOS-governed CDM extensions, not as a parallel proprietary taxonomy.

### 9.4 The Ledger architecture's footprint

The deferred-settlement Pillar 3 emission is a **single deterministic projection** of the move stream + L₁₅ Obligation register + L₁₇ rule-set version pin. The same projection produces:
- the regulatory Pillar 3 line (XBRL or iXBRL);
- the IFRS 9/IAS 1 disclosure note;
- the internal risk-engine settlement-fail metric;
- the CFO-deck quarterly KPI.

**One golden source. Multiple consumers. No reinterpretation.** This is the position ISDA has been making for fifteen years; the deferred-settlement extension makes it concrete for one of the highest-value Pillar 3 lines.

---

## 10. Capital Treatment under Basel III / CRR

### 10.1 SA-CCR for unsettled trades

**SA-CCR (Standardised Approach for Counterparty Credit Risk) per CRR Art 274 and Basel III's 2017 amendments:** for unsettled DvP transactions, the regime is on a different footing than for derivatives.

- **For DvP equity trades within the contractual settlement period (T to T+4):** no CCR capital. Market-risk capital applies on the trade-date position (per FRTB / CRR Title II of Part Three). This is the trade-date-vs-settlement-date capital question's answer for the inside-the-window case.
- **For DvP equity trades from T+5 onward (failing trade):** CRR Art 379 risk weights ramp stepwise:
  - Day 5–15: 9% (vs the gross unsettled amount)
  - Day 16–30: 50%
  - Day 31–45: 100%
  - Day 46+: 1250%
- **Free-of-payment (FoP):** different regime. Exposure recognised from delivery date; capital applies from T+1.
- **Cash-only payments:** treated as ordinary credit exposures.

### 10.2 The trade-date vs settlement-date capital question

**Trade-date** for market risk (FRTB): the position exists from T per E1; capital reflects the position from T.
**Settlement-date triggered** for counterparty credit risk on unsettled trades (CRR Art 379): kicks in only from T+5 (i.e., `ISD + 4` in business-day terms), so for the open window of T to T+ISD+4, no CCR capital is held against the unsettled DvP trade beyond its market-risk component. This is the intentional regulatory carve-out for normal-course settlement.

**Implication for the Ledger:** the move stream supports BOTH date axes simultaneously. Trade-date is the primary axis; settlement-date is a secondary index derived from the L₁₅ Obligation `deadline` field. Capital reports read from the secondary index; risk and PnL reports read from the primary index. Same data, two queries.

### 10.3 FRTB interaction

FRTB (Basel III Final, in force in EU as of Jan 2026 for SA, IMA expected Q3 2026) measures market risk on trade-date positions. The deferred-settlement window adds:
- **Settlement risk component of CVA** (where applicable): captured under the CVA framework's counterparty exposure at default.
- **Repo / SFT exposure under FRTB-NMRF or SBM:** for SFTs whose open and close legs straddle the FRTB observation window.

The Ledger architecture handles all of these from the same object (the open Obligation register); FRTB sensitivities are computed from trade-date positions; CVA reads counterparty exposure from the obligation register; SBM reads SFT term from the obligation's `deadline` field.

### 10.4 ISDA position on CRR Art 379

CRR Art 379 has been stable since the 2013 implementation. The 2024 CRR3 amendments (in force Jan 2025) refined the regime mainly for non-DvP and FoP scenarios; the DvP regime is unchanged. **No imminent reform on the horizon.** The regime is workable; the implementation cost is the issue.

The deferred-settlement architecture reduces the implementation cost by surfacing the failing-trade ageing buckets from a single source (the L₁₅ register filtered by `FAILED` and `days_past_ISD`). This eliminates the bespoke aged-trial-balance reports that most firms run today for COREP C 28.00 (CCR Settlement Risk template).

---

## 11. The Accounting-vs-Reporting Axis

### 11.1 The reality

| Regime | Date axis | Where it lives in the Ledger |
|---|---|---|
| IFRS 9 / IAS 39 (Europe) | **Trade-date** for trading-book equities (regular-way) | `PositionState[w, u].own` from T |
| ASC 320 / 326 (US GAAP) | **Trade-date** for trading securities and AFS | `PositionState[w, u].own` from T |
| MiFIR Art 26 | **Trade-date** (T+1 archive) | L₁₇ projection from L₁₃ at T |
| EMIR Refit Art 9 | **Trade-date** for `Trade` event; lifecycle events follow their own dates | L₁₇ projection from L₁₃ + L₁₅ |
| SFTR Art 4 | **Trade-date** for NEWT | L₁₇ projection from L₁₃ at T |
| CSDR Art 7 | **Settlement-date** (penalty calc starts at ISD+1) | L₁₅ Obligation `deadline` + days_past_ISD |
| BCBS Pillar 3 settlement-fail metrics | **As of report date**, accumulating from settlement-date triggers | L₁₅ register + ageing |
| CRR Art 379 (capital for unsettled) | **Settlement-date triggered** (kicks in from ISD+4) | L₁₅ Obligation + `days_past_ISD` filter |
| FRTB / market risk | **Trade-date positions** | L₁₃ + valuation engine |
| Statutory Acct (some entities, HTM) | **Settlement-date** (election for held-to-maturity bonds) | Projection (not primary) |

### 11.2 The architectural answer

**The move stream supports BOTH date axes simultaneously. Trade-date is the primary axis (when the move was committed). Settlement-date is a secondary index, derived from `obligation.deadline`. The data layer L₁₃ + L₁₅ + L₁₁ already supports this.**

The bitemporal model is `t_obs` for trade time, `t_known` for restatement. Multi-axis reporting is a **query**, not a duplicate truth.

**There is no need to maintain two ledgers.** Firms that run separate trade-date and settlement-date general ledgers are paying for duplication that the architecture does not require. ISDA's position (consistent across multiple position papers) is unambiguous: a single CDM-native source produces both views by deterministic projection.

### 11.3 The settlement-date-accounting election

Ashworth was emphatic in Phase 1: **the framework should not support settlement-date accounting as a primary mode.** I concur. Settlement-date accounting (IFRS 9.B3.1.5 election; ASC 320-10-25-3 for HTM) is permissible for some HTM portfolios but is the exception, not the norm. **Forcing this choice into the ledger primitives would require either:**
- (a) deferring all moves until T+ISD, breaking economic recognition (E1) and FRTB capital alignment; OR
- (b) maintaining two parallel move streams, violating Λ8 (replay determinism) and Λ10 (`tx_id` content-addressing).

Option (a) is unworkable for trading books. Option (b) violates the "single source of truth" design principle.

**The recommendation:** hard-code trade-date recognition in the move primitive; provide a downstream reporting projection that re-presents balances as "settled / unsettled" for any consumer requiring settlement-date views. This composes with the L₁₇ projection discipline used everywhere else.

---

## 12. ISDA Strategic Direction

### 12.1 The arc

ISDA's strategic arc, stated as a single sentence: **standardisation (ISDA Master Agreement, 1985) → legal certainty (close-out netting opinions, 90+ jurisdictions) → documentation digitisation (ISDA Create, MyLibrary) → process automation (CDM, DRR) → collateral modernisation (tokenisation, smart contracts) → capital reporting standardisation (machine-readable Pillar 3).**

The deferred-settlement extension lives at the intersection of **process automation** (CDM-native reporting; DRR for the regulatory boundary) and **collateral modernisation** (tokenised settlement, T+0 atomic). It must align with both.

### 12.2 Tokenised securities settlement

Already covered in §4.1. The deferred-settlement architecture must degenerate cleanly to T+0 atomic on tokenised representations. Hardcoding T+2 is technical debt with a known due date. **The architecture passes this test by design** (the Phase 1 convergence is parameter-driven, not horizon-baked).

### 12.3 Atomic DvP via DLT

The 2025 GDF working group output, the DTCC Great Collateral Experiment (Apr 2025), Project Guardian, and the seven-structure analysis for tokenised MMFs collectively establish: **the technology is ready; the legal/regulatory blockers are tractable.** Specific blocking points (Basel crypto-asset standard, CFTC cross-border MMF, settlement-finality opinions per jurisdiction) are tracked workstreams with active ISDA participation.

The deferred-settlement representation we adopt today must compose with the tokenised T+0 representation we will adopt in 2030. **The L₁₅ Obligation discharge predicate `ByAttestation(on-chain finality oracle)` is the integration point.** No architectural change is required; only the predicate kind switches.

### 12.4 ISDA Notices Hub

Launched July 2025. 145+ entities adhered to the 2025 Protocol by mid-Nov 2025. 21 jurisdictional opinions published. The Notices Hub addresses a **different** layer of risk than deferred settlement: the time-criticality of legal notices (default, termination, recall, dispute) where the cost of a Friday-to-Monday delay on a single medium-sized portfolio is ~$1M of uncollateralised loss.

The connection to deferred settlement: a **counterparty default during the open window** triggers the notices machinery. The L₁₅ Obligation in `Failed` state with cause = `CounterpartyDefault` becomes the reconciliation anchor for the close-out calculation under the ISDA Master Agreement. The Notices Hub delivers the notice; the Ledger records the resulting close-out transaction. **The two systems are complementary; the deferred-settlement extension should expose a hook to the Notices Hub via the L₁₅ Obligation FSM.**

### 12.5 Machine-readable Pillar 3 and the strategic implication

The Mar 2026 BCBS consultation is an opportunity to extend the DRR model to capital reporting. **The deferred-settlement Pillar 3 lines (failed-settlement aggregates; Art 379 ageing buckets; CSDR penalty disclosures) are the natural starting set** because they are derivable from the same CDM Trade + Lifecycle chain that DRR already reports.

If BCBS adopts a proprietary or non-interoperable taxonomy, the Ledger must accommodate it via a separate L₁₇ projection — a real cost. If BCBS adopts CDM/DRR as the template, the Ledger's existing DRR projection extends without rewrite. **ISDA's advocacy is for the latter; the IIF/ISDA/GFMA Mar 2026 response is the formal industry position.**

---

## 13. What I Reject from Phase 1 Proposals on Regulatory Grounds

I reject the following Phase 1 design choices on regulatory or operational grounds. Each rejection is named and explained.

### 13.1 Geohot's "single new field on the transaction" minimalism

Geohot's proposal — that the entire deferred-settlement extension is **one field** (`settlement_status`) on the transaction object, with the open obligation living implicitly as a virtual-wallet contra-entry — is technically correct in the conservation sense but **operationally insufficient for the regulatory boundary.**

**The problem:** every regulatory regime in §1's matrix requires a per-trade per-leg per-event identifier (UTI, EndToEndId, loan_id, transaction_reference_number). A single `settlement_status` flag on the transaction provides no addressable handle for:
- CSDR penalty attribution (which of 412 trades against Goldman is failing today?);
- partial-fill tracking (the residual 40 shares of the 100-share order need their own discharge predicate);
- buy-in workflow (the buy-in obligation needs its own deadline, its own discharge, its own dedup);
- regulatory restatement (an EMIR amendment to a specific lifecycle event needs to find its anchor without a full move-stream replay).

**The L₁₅ Obligation as a first-class object resolves all of these.** Geohot's minimalism passes the conservation test but fails the regulatory-emission test.

**However:** Geohot is right that the StatesHome 3-map ruling does not need a fourth map. The L₁₅ Obligation row is a unit-class object in the existing taxonomy; it does not require a new sector. The right synthesis is **L₁₅ Obligation + virtual-wallet contra + transaction-level FSM**, which is the Settlement Team's convergence.

### 13.2 SBL specialist's "seventh coordinate" inflight on the GPM

The SBL proposal (Margaret Chen) extends the GPM 6-vector to a 7-vector by adding a stored `inflight` coordinate. Operational arguments are presented (recon engineering, CSDR penalty granularity, SBL composition).

**I reject this on regulatory grounds — but lightly.** The reason: per-instruction granularity is genuinely required for CSDR penalty attribution (CSDR computes per-instruction-day-of-fail). However, this granularity already exists in the L₁₅ Obligation register, keyed by `obligation_id` (which is content-addressed on `tx_id` + leg). **Adding it ALSO to the GPM as a stored coordinate creates two sources of truth** — exactly the divergence vector ISDA's golden-source advocacy is designed to eliminate.

The right answer is: the in-flight quantity is computed by projection over open L₁₅ obligations filtered by `(wallet, unit)`. Operations gets per-instruction granularity by querying the L₁₅ register, not by reading the seventh coordinate. **One source of truth (L₁₅), multiple consumers.**

The SBL proposal's per-instruction virtual-wallet pattern (sub-§1.5) is good and complementary; the seventh coordinate is duplicative.

### 13.3 Karpathy's two-virtual-wallet split (counterparty mirror vs settlement venue mirror)

Karpathy proposes splitting the broker-virtual-wallet pattern into two virtual wallets per leg: counterparty (LEI-keyed) and settlement venue (BIC-keyed). The argument is that recon to nostro requires both.

**I accept this for cash-equity DvP** but reject it as a **mandatory** architecture for all settlement modes. Reasons:
- For atomic DLT settlement (T+0), there is no nostro to reconcile against; the chain IS the depot. The two-wallet split is moot.
- For OTC bilateral collateral (CSA), the counterparty mirror IS the settlement venue (no CCP, no CSD). The split is unnecessary.
- For CCP-cleared trades, the counterparty mirror is novated to the CCP at T+0; the post-novation wallet topology is single-CCP, not bilateral. The split would track ghost wallets.

**The right discipline:** the wallet topology is **product-specific**, defined by the smart contract for that product. Cash-equity DvP uses Karpathy's split. CSA collateral uses a single counterparty wallet. CCP-cleared uses CCP-side wallets. **The deferred-settlement extension should not mandate a wallet topology that is product-agnostic.**

### 13.4 Cartan's universal-property abstraction as the primary specification

Cartan's proposal is a Bourbaki-style derivation of the obligation as a kernel of a forgetful functor in a slice category. The mathematics is correct.

**I reject it as the primary specification language for the regulatory boundary.** Reasons:
- Regulators do not write category theory.
- Auditors do not read universal-property proofs.
- Operations cannot tie out a CSDR penalty break to "the kernel of π_custody in the slice category over τ".
- DRR is generated from CDM (a JSON/Rosetta-DSL representation), not from categorical diagrams.

**Cartan's mathematics is welcome as an appendix** establishing the soundness of the obligation construction. But the primary specification — what flows to deferredSettlement.tex, what generates code, what regulators read — must be the operational form: L₁₅ Obligation + FSM + virtual wallets + move-sequence diagrams + the regulatory matrix in §1. **The Phase 2 doc should privilege the form that maps to ISO 20022, CDM, DRR, and Pillar 3 — not the form that maps to Springer Mathematische Annalen.**

### 13.5 Noether's "deferred-delivery claim as derived unit" with explicit redemption homomorphism

Noether's proposal introduces `u^def_S,T+2` as a new unit in U, redeemable via homomorphism ρ_S into the underlying. Beautiful symmetry argument.

**I reject this on regulatory grounds.** Reasons:
- The deferred-delivery claim is **not** a separate financial instrument under any regulatory regime. CSDR treats it as a settlement state of the underlying, not a derivative of it. EMIR does not treat it as a derivative. MiFIR does not treat it as a derivative. IFRS 9 treats the receivable as a short-term receivable at notional, not as a financial instrument with its own classification.
- Introducing a new unit class would force every regulatory report to map back to the underlying. **This is exactly the divergence-vector problem** the golden-source approach exists to eliminate.

The L₁₅ Obligation is the right level: it is internal (Ledger-native), it is bitemporally indexed, it is conservation-preserving, but it does NOT proliferate the unit universe. Noether's symmetry is preserved by L₁₅'s discharge predicate (`ρ` is just `discharge_predicate.ByMatch(sese.025)`); it is not preserved by introducing a new unit.

### 13.6 Test Committee's `pending_in` / `pending_out` as new GPM coordinates

Test Committee proposes two new GPM coordinates `pending_in` and `pending_out` to make the test seam between economic-position invariants and settlement-flow invariants explicit.

**I reject this for the same reason as the SBL seventh coordinate.** Stored coordinates create duplication; the same information is available as a projection over the L₁₅ register. Test access to the projection is straightforward via a derived view (`view.position_state(w, u).pending_in() := projection(L_15, ...)`); test access does not require a stored coordinate.

The Test Committee's underlying argument — that an independent observable is required to test independently — is correct. But the observable can be a derived view over a single source of truth, not a duplicate stored field.

### 13.7 What I accept across the board

- Ashworth's IFRS 9 / IAS 32 / IAS 1 / CRR Art 379 / SOX 404 / BCBS 239 framing: accept fully.
- Jane Street's "ship it" pragmatism + the L₁₅ Obligation as the carrier: accept.
- Lattner's "library, not new sector" architectural discipline: accept.
- Halmos's settlement-obligation unit + FSM: accept the structure, reject only the "unit in U" framing in favor of Obligation-row in L₁₅.
- Formalis's invariants DS1-DS12 + proof obligations: accept.
- Correctness-architect's properties P-NoCrash through P-Spec-PartialSizeDist + 7×7 fault matrix: accept.
- Feynman's multi-representation discipline (three independent paths to the same answer): accept as the audit-grade test discipline.
- Grothendieck's Λ_3 / Λ_13 / Λ_8 anchors and bitemporal sheaf interpretation: accept as appendix-level rigour.
- Matthias's CDM 6.0.0 cross-walk + Rosetta extensions: accept; this is the level the regulatory boundary sits at.
- Nazarov's zero-trust-at-the-boundary discipline + closed-sum FSM states: accept.
- Minsky's phantom-typed `(custody_bearing | exposure_bearing)` discipline: accept as a code-level type-safety hint, not as the primary specification.
- Temporal's saga + workflow split between Ledger event log and Temporal history: accept.
- FinOps's PS / PSS wallet pair pattern: accept for cash-equity DvP, with the per-product caveat.
- SBL's per-instruction virtual wallet (sub-§1.5): accept; reject only the seventh coordinate.

---

## 14. Summary

The deferred-settlement extension is regulatory-ready and aligned with ISDA's published direction of travel:

1. **The regulatory matrix** (§1) is authoritative. Every emission is a deterministic projection of L₁₃ + L₁₅ + the rule-set version pin. Every dedup key is content-addressed. Every restatement is bitemporally controlled. **One golden source. Multiple consumers. No reinterpretation.**

2. **CSDR settlement discipline** (§2) is implementable today. The cash penalty calculation is parameterised by the asset-class table in PolicyConfiguration L₇ᴾᵇ, versioned bitemporally. The discretionary buy-in regime is supported by the L₁₅ Obligation `Compensated` terminal state. The reporting cadence (daily fail register, monthly penalty cycle) is a direct projection. **CSDR is not yet in DRR scope; ISDA position: the DRR engine should still be the audit-trail anchor for fail attribution.**

3. **T+1 transition** (§3) is parameter, not architecture — but the operational risk surface is materially different (FX cutoffs, ETF NAV, DTC night cycle, corporate actions, EU/UK fragmentation). The architecture absorbs the parameter; the operational machinery downstream must adapt. **ISDA position: the EU/UK move to T+1 (October 2027) is industry-supported, conditional on FX, corporate-actions, and ops-readiness reform.**

4. **T+0 / atomic DLT settlement** (§4) — the framework MUST degrade cleanly to T+0 by parameter change. The Phase 1 convergence (virtual wallets + L₁₅ Obligation + transaction-level FSM) passes the degeneracy test. **What changes:** discharge predicate kind (ByMatch → ByAttestation), inflight virtual-wallet period (collapses to ε), reconciliation cadence (continuous), CSDR/buy-in (N/A), capital aged buckets (zero). **What stays:** the FSM, the L₁₅ structure, conservation invariants, trade-date economic recognition (E1), the DRR engine.

5. **MiFIR transaction reporting** (§5) — T+1 deadline; settlement status does not appear in RTS 22; only trade-level cancellations/amendments generate MiFIR amendments. **Settlement-discipline events (CSDR fails, buy-ins, partials) are NOT MiFIR-reportable.**

6. **EMIR Refit / DRR** (§6) — live since April 2024; 4 firms in production; 13 in PoC; 100% MAS / 98.2% EMIR Refit acknowledgement rates. **The deferred-settlement architecture should generate EMIR Refit lifecycle reports via DRR, not via firm-bespoke code. This is non-negotiable for any v11.0 implementation that touches OTC equity derivatives.**

7. **SFTR ↔ EMIR ↔ CSDR overlap** (§7) — UTI generation discipline is the load-bearing answer (ISDA UTI guidelines, Apr 2025 update). Value-date conventions are jurisdictionally distinct; DRR-generated reports avoid the field-mapping gotchas by construction. **Dual-sided SFTR reporting is the current state; ISDA position: do not reform SFTR until DRR is live for SFTR.**

8. **FINRA SLATE Rule 6500** (§8) — live as of Jan 2026 (phased through Q3 2026); same-day reporting for new SBL; T+1 for modifications. **DRR coverage is not yet shipped; this is the highest-priority addition to the DRR roadmap from a US-equity-deferred-settlement perspective.** Reg SHO 204 close-out (T+5/T+8) is the US analog of CSDR buy-in, with strict liability (no bps).

9. **Pillar 3 / BCBS machine-readable** (§9) — IIF/ISDA/GFMA Mar 2026 response advocates DRR/CDM as the template. The deferred-settlement Pillar 3 lines (failed-settlement aggregates; Art 379 ageing buckets; CSDR penalty disclosures) are derivable from the same CDM Trade + Lifecycle chain that DRR already reports. **A separate proprietary XBRL taxonomy would re-create the divergence-vector problem at the Pillar 3 layer.**

10. **Capital treatment** (§10) — SA-CCR / CRR Art 379 risk weights (9% T+5–15, 50% T+16–30, 100% T+31–45, 1250% T+46+) are surfaced from the L₁₅ register filtered by `FAILED` and `days_past_ISD`. **Trade-date for market risk (FRTB); settlement-date triggered for unsettled-trade CCR (Art 379). Both axes from one move stream.**

11. **Accounting-vs-reporting axis** (§11) — IFRS 9 and US GAAP both default to trade-date for trading-book equities. CSDR / Pillar 3 / Art 379 use settlement-date triggers. **The framework supports BOTH from the same move stream via projection.** No need to maintain two ledgers; firms that do are paying for duplication.

12. **ISDA strategic direction** (§12) — the deferred-settlement extension lives at the intersection of process automation (CDM, DRR) and collateral modernisation (tokenisation, T+0). It must align with both. Hardcoding T+2 is technical debt with a known due date; the architecture passes the degeneracy test by design. **ISDA Notices Hub provides the legal-notice machinery for counterparty default during the open window; the Ledger should expose a hook to it via the L₁₅ Obligation FSM.**

13. **Phase 1 rejections** (§13) — I reject Geohot's minimalism (insufficient for regulatory boundary), the SBL seventh coordinate (duplication), Karpathy's mandatory two-wallet split (product-specific, not universal), Cartan's primary-language category theory (regulator/auditor-illegible), Noether's deferred-delivery claim as a unit (doesn't match any regulatory regime), and Test Committee's stored pending_in/pending_out coordinates (duplication of L₁₅).

The architecture aligns with ISDA's published positions, with the DRR coverage roadmap, with the CDM 6.0.0 cross-walk, and with the BCBS / IIF / GFMA position on machine-readable disclosure. **Firms that adopt this representation are aligned with the direction of travel; firms that do not will accumulate the technical debt of every settlement-cycle change, every regulatory regime, and every tokenisation roadmap as discrete migration projects rather than configuration changes.**

**Ship it.**

— Olivier Vantard, ISDA Board Advisor (regulatory-reporter seat), Phase 2 Settlement Team
