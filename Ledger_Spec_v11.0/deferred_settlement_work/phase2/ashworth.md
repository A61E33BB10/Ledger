# Deferred Settlement — Accounting Treatment, Audit Trail, and Capital

**Author**: Reginald Ashworth, FCA, Senior Partner, Banking Assurance
**Phase**: 2 — Settlement Team unified design (Section: Accounting / Audit / Capital)
**Date**: 30 April 2026
**Companion to**: `deferredSettlement.tex` v11.0
**Mainstream convergence accepted**: virtual wallets + `L_15` `Obligation` + transaction-level FSM; mandatory invariant **economic-exposure-at-T**.

---

## 0. Reading guide for the audit / finance reader

The Settlement Team's mainstream design represents the open settlement obligation as:

1. A trade-date atomic ledger transaction recording the economic position in `own` at `T`;
2. A counterparty / CSD virtual-wallet contra-entry holding the in-flight delivery and cash legs;
3. A per-leg `L_15.Obligation` row carrying the lifecycle FSM `EXECUTED → INSTRUCTED → SETTLED | FAILED | PARTIALLY_SETTLED | CANCELLED | BOUGHT_IN`, discharged by attested external confirmation (`sese.025` / `camt.054`).

This section provides the **definitive accounting and audit reading** of that design. It is normative for all entities reporting under IFRS or US GAAP and supersedes any divergent treatment in earlier drafts. Where a Phase 1 proposal proposed a treatment inconsistent with this section, that treatment is rejected (§12).

The section is intentionally long because the audit and capital consequences of getting this wrong are large: the difference between trade-date and settlement-date accounting on a tier-1 trading book at year-end can be £400m–£2bn of disclosed receivables / payables, breach Pillar 3 large-exposure thresholds, and (in the audit-failure case) cause a qualified opinion. None of this is hypothetical.

---

## 1. The accounting-policy ruling — trade-date is mandatory

### 1.1 Normative ruling

**Ruling A1.** For every cash-equity, listed-debt, listed-derivative, and equivalent regular-way trade booked into the Ledger framework, **trade-date accounting is mandatory at the ledger primitive level**. The ledger move stream MUST recognise the economic position (`own` increment / decrement on the security leg; `own` increment / decrement on the cash leg) at the trade-execution timestamp `T`, not at the contractual settlement timestamp `T+k`.

Settlement-date accounting is **not** supported as a ledger primitive. Where a downstream consumer (a statutory entity reporting under a settlement-date convention; a fund-accounting platform; certain US GAAP held-to-maturity portfolios under ASC 320-10-25-3) requires a settlement-date view, that view is produced as a **reporting projection** over the move stream + the obligation FSM — never by deferring the underlying moves.

### 1.2 Standard-by-standard grounding

**IFRS 9.B3.1.3** (regular-way trade exception): "A purchase or sale of a financial asset under a contract whose terms require delivery of the asset within the time frame established generally by regulation or convention in the marketplace concerned … shall be recognised, as appropriate, using **trade date accounting** or settlement date accounting (see paragraphs B3.1.5 and B3.1.6)."

**IFRS 9.B3.1.5** clarifies that "the method used is applied consistently for all purchases and sales of financial assets that belong to the same category" (i.e., the four IFRS 9 measurement categories: amortised cost, FVOCI debt, FVOCI equity election, FVTPL).

**Consequence for the framework.** Within the trading-book / FVTPL classification — the dominant category for cash-equity activity in a tier-1 dealer — settlement-date accounting is permitted under IFRS 9 but produces a discontinuity between economic exposure (CRR Article 325 market-risk capital, FRTB sensitivities, IAS 1 mark-to-market presentation) and book recognition. The Ledger's atomic-transaction primitive embeds trade-date semantics; supporting settlement-date as a ledger primitive would require maintaining two parallel move streams — violating the "single source of truth" principle of v10.3 §1 and the StatesHome 3-map ruling.

**ASC 320-10-25-3** (US GAAP, available-for-sale and trading securities): "An entity should account for a regular-way security trade on either the trade date or the settlement date. The accounting method that is used should be applied consistently for all securities classified in the same category." Trading-securities classification under ASC 320-10-25 effectively defaults to trade-date for reporting purposes; settlement-date is permitted only for held-to-maturity (ASC 320-10-25-3a). The Ledger does not yet distinguish HTM as a first-class measurement category, so there is no ledger consumer requiring settlement-date.

**ASC 326-20-30-2** (CECL initial recognition): the allowance for credit losses on a financial asset is recognised at the **acquisition date**, which under trade-date accounting is the trade date. The CECL allowance for a settlement receivable therefore opens at `T`, not at `T+k`.

**IAS 32.42** (offsetting): financial assets and financial liabilities are offset only when there is a currently enforceable legal right of set-off and an intention either to settle on a net basis or simultaneously. The settlement receivable (long the security) and the settlement payable (short the cash) generally do **not** satisfy IAS 32.42 because they are obligations to different counterparties (the CSD for securities, the cash agent / counterparty for cash). They must be presented gross (IAS 1.32 prohibition on offsetting). The framework's separate treatment of the security leg and cash leg is therefore not optional — it is required for IAS 32 compliance.

**Single-Coordinate Move Principle (v10.3 §13.2 / Principle 13.1).** Each move alters one coordinate of one unit at one entity. Settlement-date accounting would require either deferring the `own` move to `T+k` (breaking trade-date economic recognition) or maintaining a parallel `own_settled` coordinate (violating the single-source-of-truth principle and the `accumulated_cost`-style discipline of v10.3). The Single-Coordinate Move Principle is the structural reason settlement-date accounting cannot be a ledger primitive.

### 1.3 Why settlement-date accounting is a downstream projection only

Three reasons settlement-date accounting must be projected from the move stream + obligation FSM, not stored:

1. **Regulatory capital is computed on trade-date positions** (CRR Article 325(2) FRTB sensitivities; CRR Article 274 SA-CCR exposure-at-default; US Federal Reserve Y-9C trading book schedule). A settlement-date ledger would understate market-risk capital during the open window by exactly the open-position notional. For a tier-1 dealer with £4bn of unsettled buys at year-end, this is a £400m–£800m RWA gap depending on volatility — a material misstatement.

2. **Day-1 P&L and Day-2 P&L recognition (IFRS 13.B5.1.2A; ASC 820-10-30-3A) requires the FVTPL position be marked from the moment of execution.** A settlement-date ledger would defer Day-1 P&L recognition by 1–2 days and produce a discontinuity at `T+k` when the position appears.

3. **The path-independent PnL theorem (v10.3 §3.3 / §4.3) is incompatible with settlement-date accounting.** The theorem requires PnL to depend only on position × price; if position is delayed, PnL becomes a function of CSD batch timing — a non-economic variable.

The downstream settlement-date projection (for entities that genuinely require it — typically fund-accounting platforms or certain pension portfolios) reads:

```
settled_position(w, u, t)
  := own(w, u, t) − Σ { signed_qty(o) : o ∈ open_obligations(w, u, t) }
```

This is computed on read, like the GPM `avail` projection. It carries no independent state and cannot drift.

### 1.4 Action for the engagement team

| Action | Owner | Standard |
|---|---|---|
| Document trade-date accounting policy in the entity's IFRS 9 / ASC 320 accounting-policy manual | CFO + Group Accounting Policy | IFRS 9.7.2.1; ASC 320-10-50 |
| Confirm consistent application across all FVTPL securities measurement categories | Group Accounting Policy | IFRS 9.B3.1.5 |
| Tie the ledger primitive to the disclosed accounting policy in the audit memorandum | Engagement Partner | ISA 250, ISA 540 |
| Verify no FVTPL trades are booked at settlement date (test of details) | Audit team | ISA 330 |

---

## 2. Balance-sheet substantiation across the open window

### 2.1 Worked example: BUY 100 XYZ @ $50, mark to $52, T+2 settlement

**Setup.** Entity is a dealer, FVTPL classification. Purchase 100 XYZ at $50 on Monday `T`, settling Wednesday `T+2`. Mark at $52 on Tuesday close.

#### At `T` (trade execution, Monday close)

The atomic settlement transaction emits:

```
Move 1: w_cpty_v   -> w_book      unit=XYZ  qty=+100   (security leg, economic recognition)
Move 2: w_book     -> w_cpty_v    unit=USD  qty=-5,000 (cash leg, economic recognition)
Register obligation o_sec = SettlementObligation(SecLeg, +100, due=T+2, status=Pending)
Register obligation o_cash = SettlementObligation(CashLeg, -5,000, due=T+2, status=Pending)
```

**Conservation per unit:** ΔXYZ = 0; ΔUSD = 0. **Trade-date economic exposure at T = +100 XYZ × $50 = $5,000 long.**

**Journal entry (IFRS 9 / ASC 320 trade-date basis):**

```
Dr Financial assets — FVTPL (XYZ)              5,000.00
   Cr Cash                                            5,000.00
```

**Note:** under trade-date accounting on the FVTPL trading book, both legs are recognised at the contract notional at `T`. The cash credit reduces the entity's cash balance at `T` even though no cash physically leaves the nostro until `T+2`. This is correct because the entity has accepted the contractual obligation to pay cash on `T+2`; the receivable / payable presentation (gross, IAS 1.32) is the formal expression of this in the published balance sheet.

**Alternative balance-sheet presentation** (the more common dealer presentation, IAS 1.55 separate disclosure):

```
Dr Financial assets — FVTPL (XYZ)              5,000.00
   Cr Settlement payable to counterparty            5,000.00
```

This presentation defers the cash debit to `T+2` and shows the settlement liability separately. Both presentations are acceptable under IFRS, provided consistency is maintained. **My recommendation: use the second form**, because (a) the cash has not actually left the bank, (b) it presents the open settlement obligation as a discrete line item that auditors can trace to depot statements, and (c) it aligns with the regulatory CRR Article 379 settlement-risk disclosure.

#### At `T+1` (Tuesday close, mark to $52)

**No moves.** Pricing engine updates `P_{T+1}(XYZ) = 52`.

```
PnL_{T to T+1} = own(w_book, XYZ) × (P_{T+1} − P_T)
              = 100 × ($52 − $50) = +$200
```

**Journal entry (mark-to-market revaluation):**

```
Dr Financial assets — FVTPL (XYZ)               200.00
   Cr Other comprehensive income / Profit for the period   200.00
```

For FVTPL classification, the credit goes to P&L (IFRS 9.5.7.1). For FVOCI debt, credit goes to OCI (IFRS 9.5.7.10). Equity-instrument FVOCI elections (IFRS 9.5.7.5) credit to OCI with no recycling — uncommon in trading books.

**Settlement obligation status:** `o_sec.status = Instructed` after the settlement layer dispatches `sese.023`. The obligation is still outstanding; lifecycle stage advance carries no journal entry.

#### At `T+2` (Wednesday, CSD confirms settlement)

`sese.025` arrives. The settlement-confirmation transaction emits:

```
Move 3: w_cpty_v   -> w_csd_nostro  unit=XYZ  qty=+100   (depot materialises)
Move 4: w_csd_nostro -> w_cpty_v    unit=USD  qty=-5,000 (cash agent debits)
StateDelta: o_sec.status = Settled, o_cash.status = Settled
```

**No move on `w_book`.** The economic position recognised at `T` is unchanged.

**Journal entry at T+2** (closing the receivable / payable presentation — only required if §2.1 first-form was used; with the second form the entries below are the only `T+2` entries):

```
Dr Settlement payable to counterparty           5,000.00
   Cr Cash at custodian                              5,000.00
Dr Securities at custodian (sub-ledger)        5,200.00   [marked at T+2 price = $52]
   Cr Financial assets — FVTPL (XYZ, in transit)    5,200.00
```

The second pair of entries reclassifies the position from "FVTPL in transit" to "FVTPL settled at custodian" — an internal sub-ledger move, not a P&L event. **No PnL impact at settlement** (P10 path-independence).

### 2.2 Disclosure shape (IAS 1.55 / IFRS 7.6 / ASC 860)

The published balance sheet at any reporting date with material open settlements **must separately disclose** the settlement receivables and payables. The IAS 1.55 directive ("an entity shall present additional line items, headings and subtotals … when such presentation is relevant to an understanding of the entity's financial position") makes separate presentation mandatory above an entity-specific materiality threshold.

**Recommended balance-sheet line items for a tier-1 dealer:**

| Asset side | Liability side |
|---|---|
| Financial assets at FVTPL — settled at custodian | Financial liabilities at FVTPL — settled |
| **Financial assets at FVTPL — securities receivable in settlement** | **Settlement payables to counterparties / CCPs** |
| Trade and other receivables | Trade and other payables |
| Cash and cash equivalents | |

The bolded lines are the open-settlement disclosure. They are reconciled to the open `L_15.Obligation` register as at the reporting date.

**IFRS 7 requirements (mandatory):**

- **IFRS 7.31–35** (nature and extent of risks): risk concentration disclosure by counterparty for material settlement exposures.
- **IFRS 7.34(c)** (concentrations of risk): if any single CCP / custodian / counterparty represents > 10% of aggregate settlement receivables, named-counterparty disclosure.
- **IFRS 7.35F** (credit risk — Stage migration on impaired financial assets): if ECL Stage 2 migrations on settlement receivables exceed 5% of gross, separate disclosure.
- **IFRS 7.39** (liquidity risk maturity table): settlement receivables / payables in the 0–1 week maturity bucket.

**US GAAP equivalent (ASC 860-10-50, ASC 326-20-50):** settlement receivables disclosed in the trade-date / settlement-date reconciliation table, with aging, counterparty concentration, and CECL allowance.

### 2.3 Journal-entry summary table (canonical case, both presentations)

| Date | Form A: full cash debit at T | Form B: payable presentation |
|---|---|---|
| T | Dr FA-FVTPL 5,000 / Cr Cash 5,000 | Dr FA-FVTPL 5,000 / Cr Settlement payable 5,000 |
| T+1 | Dr FA-FVTPL 200 / Cr P&L 200 | Dr FA-FVTPL 200 / Cr P&L 200 |
| T+2 | (no entry on cash; XYZ moves into custody sub-ledger) | Dr Settlement payable 5,000 / Cr Cash 5,000 (+ sub-ledger reclass) |

**Form B is preferred** for tier-1 dealers because it preserves visibility of the open settlement obligation through the reporting window.

### 2.4 Aggregated open-settlement disclosure at year-end (illustrative, tier-1 dealer)

For a typical tier-1 dealer at calendar year-end:

| Line item | £m |
|---|---|
| Financial assets at FVTPL — settled | 285,400 |
| **Financial assets at FVTPL — securities receivable in settlement** | **4,180** |
| Cash and cash equivalents | 78,300 |
| **Settlement payables to counterparties / CCPs** | **(3,800)** |

The £4,180m gross receivable and £3,800m gross payable are **separately presented**, **not netted** (IAS 32.42 fails because counterparties differ). The net settlement exposure of £380m is itself disclosed in the IFRS 7 narrative as the firm's residual net unsettled position. **At this scale this is material to virtually every entity** — quantitative materiality (£25m–£100m for a tier-1 dealer per ISA 320) is exceeded by an order of magnitude, and qualitative materiality is triggered by the regulatory and counterparty-risk disclosure requirements.

---

## 3. The audit evidence chain

### 3.1 The five-document chain

For every cash-equity DvP settlement in the framework, an external auditor will demand a five-document evidence chain to substantiate the existence, completeness, valuation, rights-and-obligations, and cut-off assertions for the settlement receivable / payable at year-end. Each document maps to a specific framework artefact and to a specific audit standard.

| # | Document | Source | Framework artefact | Linked by |
|---|---|---|---|---|
| 1 | FIX 8=ExecRpt or equivalent execution report | Trading venue / order-routing system | `Transaction(type=SETTLEMENT, tx_id, ts=T)` in `L_13` `MoveStream` | `external_ref` field on the trade transaction |
| 2 | `sese.023` Securities Settlement Instruction (outbound) | Settlement layer → CSD | Status transition `EXECUTED → INSTRUCTED` on `o_sec` | `sese.023.EndToEndId = trade_id` + idempotency key |
| 3 | `sese.025` Securities Settlement Confirmation (inbound) | CSD → settlement layer | `o_sec.discharge_witness` + status `Settled` | `sese.025.RelatedRef = sese.023.EndToEndId` |
| 4 | `camt.054` Bank-to-Customer Debit/Credit Notification | Cash agent → settlement layer | `o_cash.discharge_witness` + status `Settled` | `camt.054.EndToEndId = trade_id` |
| 5 | CSD depot statement (daily / weekly) | CSD direct feed | Reconciliation against `w_csd_nostro` virtual wallet | Position-level tie-out at `t = T+2 EOD` |

**Each document is signature-verified and content-hashed at ingress** (per the NAZAROV proposal's attestation discipline; mainstream-team accepted). Each appears in `L_11.ExternalConfirmation` with bitemporal `(t_obs, t_known)`. The framework's `external_ref` field on every Move and every obligation discharge links the ledger entry back to the document.

### 3.2 Mapping to v10.3 §11 ExternalConfirmation types

The Settlement Team's mainstream design exposes `L_11.ExternalConfirmation` as a closed-sum tagged union. Documents 2–4 above map directly:

| Document | `ExternalConfirmation` constructor | Verification function |
|---|---|---|
| `sese.023` outbound | `Sese023Submitted { msg_id, end_to_end_id, csd_lei }` | `verify_outbound_signature(csd_pubkey)` |
| `sese.024` status update | `Sese024Status { msg_id, ref, status_code }` | same |
| `sese.025` confirmation | `Sese025Confirmed { msg_id, ref, settled_qty, settled_amt }` | `verify_csd_envelope(csd_pubkey)` |
| `camt.054` cash credit/debit | `Camt054Notification { msg_id, end_to_end_id, currency, amount, dr_cr_indicator }` | `verify_bank_envelope(bank_pubkey)` |
| Depot statement | `DepotStatement { csd_lei, account, as_of_date, holdings[] }` | `verify_csd_envelope` + reconciliation tolerance |

Document 1 (FIX `ExecRpt`) is internal to the firm's trading infrastructure but is, per audit practice, treated as an **information-produced-by-entity (IPE)** record requiring its own completeness-and-accuracy testing under PCAOB AS 2110 / ISA 500.10.

### 3.3 Authority references

The five-document chain is required by:

- **ISA 500.6** (sufficient appropriate audit evidence): "The auditor shall design and perform audit procedures that are appropriate in the circumstances for the purpose of obtaining sufficient appropriate audit evidence." For a material settlement receivable, the five-document chain is the minimum sufficient evidence package.
- **ISA 505** (external confirmations): the `sese.025` and `camt.054` are external confirmations in the ISA 505 sense — independent of the firm and addressing the existence and rights-and-obligations assertions.
- **PCAOB AS 2310** (the auditor's confirmation procedures): same scope, US-listed entities; mandatory negative-confirmation procedures for material year-end settlement receivables.
- **BCBS 239 Principle 6** (accuracy and integrity): "Risk data should be aggregated on a largely automated basis so as to minimise the probability of errors." The deterministic chain — `tx_id` → `sese.023.EndToEndId` → `sese.025.RelatedRef` → `camt.054.EndToEndId` — is the BCBS 239 lineage record.
- **SOX 404 / SOC 1 control objective (settlement existence and completeness):** the chain is the control evidence that every recorded settlement obligation has an external counterparty acknowledgement.
- **IFRS 7.B11** (liquidity and credit risk disclosure): the chain supports the disclosure that settlement receivables are externally confirmed as opposed to internally assumed.

### 3.4 Audit testing approach

The audit team will:

1. **Select a sample** of 25–60 settlement receivables / payables from the year-end open-settlement register, stratified by counterparty, currency, settlement date, and CSD.
2. **For each item, trace** through the five-document chain:
   - confirm trade existence in the FIX archive;
   - confirm `sese.023` was emitted with matching `EndToEndId`;
   - confirm inbound `sese.025` (or `sese.024` fail-status, if applicable) with matching `RelatedRef`;
   - confirm `camt.054` cash debit / credit;
   - confirm CSD depot statement at `T+2+` shows the expected position.
3. **Reperform the reconciliation** identity (DS3 / I-ds-4):
   ```
   own(w, u, t) = nostro(w, u, t) + Σ { signed_qty(o) : o open at t }
   ```
   Confirmation that the identity holds is positive evidence for the existence and completeness assertions.
4. **Examine breaks** in the `L_18.BreakRegister`: every break that aged through the year-end window is a candidate for further investigation (potential cut-off, completeness, or fraud risk).
5. **Test the IPE controls** on the FIX archive (completeness of the trade population) per AS 2110 / ISA 500.10.
6. **Independent confirmation procedures** (ISA 505): direct confirmation requests to the CSD and the cash agent for a sample of year-end open positions, asking them to confirm the receivable / payable.

For a material year-end balance, expect:
- 25–40 sampled items for substantive testing of the open settlement balance;
- 100% testing of any single counterparty exceeding 10% of CET1 (CRR Article 392 large-exposure threshold);
- Walk-through of one settled trade and one failed trade end-to-end;
- Specific overweight on cross-currency / Herstatt exposures, partials, and items aged beyond 5 days.

---

## 4. IFRS 9 ECL on settlement receivables

### 4.1 Is there ECL on a 2-day settlement receivable?

**Short answer: yes, but the magnitude depends sharply on the counterparty class.**

**Standard reference.** IFRS 9.5.5.1 (general approach): "An entity shall recognise a loss allowance for expected credit losses on a financial asset that is measured in accordance with paragraphs 4.1.2 or 4.1.2A …" — i.e., financial assets at amortised cost or FVOCI debt. Settlement receivables, being short-dated trade receivables typically without a significant financing component (IFRS 9.5.1.3, IFRS 15 cross-reference), are eligible for the **simplified approach** (lifetime ECL throughout, without staging).

**IFRS 9.5.5.15** (simplified approach for trade receivables): "Despite paragraphs 5.5.3 and 5.5.5, an entity shall always measure the loss allowance at an amount equal to lifetime expected credit losses for: (a) trade receivables or contract assets that result from transactions that are within the scope of IFRS 15 …".

Settlement receivables are not strictly IFRS 15 receivables (they arise from financial-instrument transactions, not from contracts with customers), but the IASB has accepted in practice that the simplified approach is appropriate for short-dated, low-credit-risk trade receivables of this kind. The pragmatic position is: **apply IFRS 9.5.5.15 by analogy; lifetime ECL = 12-month ECL at this duration; provision is computed as PD × LGD × EAD.**

### 4.2 De minimis CCP, material bilateral — the decision matrix

| Counterparty class | 2-day PD | LGD (post-default-fund) | ECL on £100m exposure | Treatment |
|---|---|---|---|---|
| **CCP-cleared** (LCH, DTCC NSCC, Eurex, JSCC) | < 0.1 bp | 5–10% (after default-fund waterfall) | < £5,000 | **De minimis**; book at portfolio-pool level (IFRS 9.B5.5.30 collective evaluation) |
| **Tier-1 dealer counterparty** (LEI verified, investment-grade) | 0.5–2 bp | 30–40% | £15,000 – £80,000 | **Material at scale** but typically immaterial per trade; pool by counterparty rating |
| **Sub-investment-grade bilateral** | 5–20 bp | 40–60% | £200,000 – £1.2m | **Material**; track by name; reassess Stage on every quarterly review |
| **Failed bilateral, day 5+ post-IPD** | 50–500 bp (Stage 2 trigger) | 60–80% | £3m – £40m | **Stage 2 migration** under IFRS 9.B5.5.43 (significant increase in credit risk); lifetime ECL with curve based on actual cure / buy-in experience |

**De minimis threshold.** For CCP-cleared trades, the ECL is so small relative to even granular materiality (typically 1% of group materiality) that I recommend **booking at the portfolio level** (IFRS 9.B5.5.30 — "groups of similar financial assets evaluated collectively"). Per-trade tagging is unnecessary; the ECL is computed quarterly as a single pool charge based on (notional × PD × LGD).

**Material bilateral.** For non-CCP bilateral settlements (rare for listed equities; common for OTC bilateral DvP, cross-currency, EM markets), per-trade ECL tagging is required:

- Tag every settlement obligation with `counterparty_lei` and `ccp_lei` (where applicable).
- At trade time `T`, accrue ECL = `notional × PD_2d × LGD` from P&L to a `w_ECL_provision` virtual wallet.
- At settlement (`Settled`), reverse the ECL accrual: credit the provision wallet, debit P&L. (No P&L impact net.)
- At fail (`Failed`), retain the ECL accrual; reassess for Stage 2 migration.

### 4.3 CSDR fail extension as a Stage 2 trigger

**Standard reference.** IFRS 9.B5.5.43 (significant increase in credit risk indicators): "Significant increase in credit risk … includes: (a) significant changes in internal price indicators of credit risk … (h) actual or expected significant changes in the operating results of the borrower … (k) actual or expected significant adverse changes in regulatory, economic, or technological environment …". A CSDR fail extending past the contractual settlement date is, in my read, a **non-rebuttable Stage 2 trigger** for the bilateral counterparty (it is a substantive operational default).

**Operational workflow:**

1. At `t = T+2 + 1` business day (failure persisting beyond contractual settlement), trigger Stage 2 migration on the obligation's counterparty exposure.
2. Recalculate ECL using the Stage 2 model (lifetime ECL, with the lifetime defined as the longer of (a) the CSDR mandatory buy-in horizon (4 BD liquid / 7 BD illiquid) and (b) the empirical fail-cure tail).
3. Disclose under IFRS 7.35F (gross carrying amount of financial assets that have undergone a Stage 1 → Stage 2 migration during the period).
4. On cure (settlement eventually occurs), reverse the Stage 2 incremental ECL; on default → buy-in execution, write off the unrecoverable cost.

### 4.4 US GAAP equivalent (CECL)

**ASC 326-20-30-2** (initial recognition of CECL): "An entity shall measure expected credit losses … on the basis of relevant information about past events, current conditions, and reasonable and supportable forecasts." Settlement receivables under CECL are evaluated **collectively** (ASC 326-20-30-7 — "if the financial assets share similar risk characteristics") for CCP-cleared trades, and individually for failed / impaired trades.

**CECL vs IFRS 9 divergence on settlement receivables:**

| Dimension | IFRS 9 (simplified) | US GAAP CECL |
|---|---|---|
| Initial recognition | Lifetime ECL at trade date | Lifetime ECL at acquisition |
| Stage migration | Stage 1 / Stage 2 / Stage 3 | No staging (always lifetime) |
| Forward-looking macroeconomic adjustment | Required (IFRS 9.5.5.18) | Required (ASC 326-20-30-9) |
| De minimis threshold | Implicit via materiality | Implicit via collective evaluation pool |
| CCP-cleared treatment | Pool / portfolio | Pool / collective |

**For dual-reporters,** the ECL provision under CECL will typically be modestly higher than under IFRS 9 (CECL has no Stage 1 12-month limit), but the difference for short-dated settlement receivables is small (single-digit basis points of notional). The framework should emit IFRS 9 ECL as primary and project CECL as an alternative measure.

### 4.5 Recommendation

| Decision | Recommendation |
|---|---|
| Per-trade vs pooled tagging | CCP-cleared: pooled (B5.5.30); bilateral: per-trade |
| ECL computation timing | At `T` (trade date), reversed at `Settled` |
| Stage 2 trigger | CSDR fail beyond contractual settlement date = automatic Stage 2 |
| Disclosure threshold | IFRS 7.35F if Stage 2 migrations exceed 5% of gross settlement receivables |
| Dual-reporting | IFRS 9 primary; CECL as alternative measure projection |

---

## 5. CRR / Basel III capital treatment

### 5.1 The three CRR articles

**Article 378 — Free deliveries** (CRR 575/2013 as amended by CRR III 2024 entering into force 1 January 2025): when an entity has delivered (paid for) a security but not yet received the security (or vice versa), the institution shall apply **a 100% risk weight** to the current exposure (the delivered amount) until the second leg has effectively taken place.

For free-of-payment (FOP) settlements outside CSD-DvP, this article applies from the moment the entity has paid until the security is received.

**Article 379 — Settlement risk for transactions other than delivery-versus-payment** and the broader settlement-risk regime under the CRR III amendments: when a transaction has not settled by the **contractual settlement date** (typically 4 business days post-IPD on liquid markets), the institution shall apply a risk weight ramp:

| Days post-contractual-settlement-date | Risk weight on price-difference exposure |
|---|---|
| 5–15 days | 100% |
| 16–30 days | 625% |
| 31–45 days | 937.5% |
| 46+ days | 1,250% |

The exposure is `max(0, current_market_price − contract_price) × quantity` — i.e., the replacement-cost loss the entity would suffer if forced to buy in at current prices.

**Article 380 — Large exposures**: settlement receivables from a single counterparty that exceed 10% of the entity's CET1 trigger CRR Article 395 large-exposure reporting and the 25% CET1 cap on individual counterparty exposure. For a tier-1 dealer with CET1 of £20bn, this is £2bn per counterparty.

### 5.2 Aged-bucket capital schedule for failed settlements

The framework's reporting projection must extract the failed-trade ageing buckets per CRR Article 379 + COREP C 28.00 (CCR Settlement Risk template):

| Ageing bucket | Status in framework | Capital treatment |
|---|---|---|
| `T+0` to `T+4` (within contractual settlement period) | `o.status = Pending / Instructed` | No CCR settlement-risk capital; market-risk capital on `own` only |
| `T+5` to `T+15` (5–15 days post-IPD) | `o.status = Failed`, age ≥ 5d | **100% RW** on `max(0, MV − contract_price) × qty` |
| `T+16` to `T+30` | `o.status = Failed`, age ≥ 16d | **625% RW** on price-difference |
| `T+31` to `T+45` | `o.status = Failed`, age ≥ 31d | **937.5% RW** on price-difference |
| `T+46+` | `o.status = Failed`, age ≥ 46d | **1,250% RW** on price-difference (full deduction) |

**The framework must support extraction of these buckets** at every reporting date for COREP submission. This requires:

1. Per-obligation ageing computed deterministically from `(o.intended_settlement_date, current_business_date)`.
2. Per-obligation market-value snapshot for replacement-cost computation.
3. Aggregation by counterparty for Article 380 large-exposures reporting.
4. CCP-cleared flag (CCP-cleared exposures attract zero CCR settlement risk under CRR Article 305 — exempt).

### 5.3 Material capital impact at scale

For a tier-1 dealer with £4bn of bilateral failed settlements aged 5–15 days (a stressed-but-realistic scenario in a CSDR-triggered settlement crisis):

- 100% RW × £4bn replacement-cost exposure (assume 5% market move = £200m exposure) = £200m RWA.
- At 10% CET1 ratio target, this is £20m of incremental capital required.
- For an entity with 50 bp of market-move exposure on £4bn fails (more typical), it is £20m × 50bp/500bp = £2m — small in absolute terms but materially impactful in stress.

**The capital regime is a strong incentive to settle (or buy-in promptly).** The framework's automatic ECL Stage 2 migration + COREP C 28.00 reporting + CCR capital ramp creates a deterministic, auditable, regulatorily-compliant penalty structure for settlement fails.

### 5.4 CSDR cash penalty regime (separate from CRR capital)

CSDR Article 7 (Settlement Discipline Regime; in force since February 2022, recalibrated 2024 ESMA RTS, further refinement Q1 2026 expected) imposes a **daily cash penalty** on the failing party:

| Asset class | Penalty rate (basis points × MV per day late) |
|---|---|
| Liquid shares | 1.0 bp |
| Illiquid shares | 0.5 bp |
| Sovereign / supranational debt | 0.10 bp |
| Other public debt | 0.20 bp |
| Corporate debt | 0.20–0.25 bp |
| SME growth market | 0.25 bp |

Penalty is `MV × rate × days_late`, accrued daily, settled monthly via T2S net penalty advice. The framework treats this as a **separate `L_15.Obligation`** of kind `CSDR_PENALTY` with schema `(rate_basis_points, days, source_lei, currency)` (as proposed in correctness.md and aligned across the panel).

**Accounting treatment of CSDR penalties:**
- Failing party: charge to **operating expense** at accrual (IAS 1.85, "other operating expenses"). Not a deduction from interest income; treated as a regulatory fine / penalty.
- Receiving party: credit to **other operating income**.
- Disclosure threshold: aggregate penalties paid / received > £5m year-on-year disclosed in the IFRS 7.35 risk-management narrative.

### 5.5 Pillar 3 disclosure requirements

CRR Article 442 (Pillar 3 credit-risk disclosure) requires:

- **Failed settlement aggregate** by aged bucket (T+5..T+15, T+16..T+30, T+31..T+45, T+46+).
- **CSDR penalty paid / received** aggregate.
- **Counterparty concentration** if any single counterparty's failed exposure exceeds 5% of CET1.
- **Operational risk** narrative if material settlement failures correlate with internal operational events.

This is the BCBS Pillar 3 machine-readable disclosure track (under IIF / GFMA / ISDA proposals, Q1 2026 BCBS response). The framework's Pillar 3 projection must aggregate the open `L_15.Obligation` set + the discharged-but-failed history and produce the COREP C 28.00 / Pillar 3 schedule deterministically.

---

## 6. SOX / SOC 1 controls specific to deferred settlement

### 6.1 Key control objectives

For SOX 404 management certification (US-listed entities) and SOC 1 Type II reporting (third-party processing):

| Control objective | Control type | Test |
|---|---|---|
| **CO-1** Trade capture completeness: every executed trade enters the ledger | Preventive, automated | FIX message sequence-number reconciliation against `L_13` move stream; gap = control failure |
| **CO-2** Settlement instruction completeness: every committed `SETTLEMENT` transaction generates exactly one `sese.023` | Preventive, automated | 1:1 matching of `tx_id` → outbound message ID; aged-unmatched report |
| **CO-3** Settlement confirmation matching: every outbound `sese.023` matches inbound `sese.025` within SLA | Detective, automated | Aged-unmatched report; SLA = `T+2 + 1 BD` |
| **CO-4** Position reconciliation: daily three-way tie-out between ledger `own`, `pending` legs, and external CSD depot | Detective, manual | Daily T+1 reconciliation walk-through; signoff by middle office |
| **CO-5** Segregation of duties between trading and settlement | Preventive, organizational | Role-based access control review; no trader has settlement-instruction modification rights |
| **CO-6** CORRECTION transaction approval: every `CORRECTION` requires four-eyes + named approver | Preventive, automated | System enforcement; audit log review |
| **CO-7** Exception management: every break has an owner, SLA, and escalation path | Detective, manual | Aged-break aging report; >5 days = ops head escalation; >15 days = CFO |
| **CO-8** Settlement-status FSM enforcement: only the `SettlementWorkflow` may mutate `obligation.lifecycle_stage` | Preventive, structural | Capability-scope check (StatesHome C11); compile-time + runtime enforcement |

### 6.2 Segregation of duties — the load-bearing organizational control

**The single most important SOX control for deferred settlement.** Three roles must be structurally separated:

1. **Front office (trader)**: authorised to execute trades; cannot modify settlement instructions or confirmations.
2. **Settlement operations**: authorised to release `sese.023` instructions, ingest `sese.025`/`camt.054` confirmations, manage breaks; cannot execute trades or modify the original move stream.
3. **Middle office / accounting**: authorised to read settled / unsettled positions, reconcile to depot, and produce the financial statements; cannot modify positions or confirmations.

The framework's StatesHome C11 capability discipline (each `UnitStatus` field has a unique writer) is the structural enforcement of this segregation. Trader code paths cannot type-check against `obligation.lifecycle_stage`. Settlement-ops code paths cannot type-check against `Move(unit=ISIN, qty=...)`. Accounting code paths cannot mutate either. **This is auditor-friendly: it converts segregation of duties from a procedural assertion to a system property.**

### 6.3 Four-eyes on CORRECTION transactions

Every `CORRECTION` transaction (anti-moves reversing or adjusting an earlier trade) MUST require:

1. **Named requester** (typically settlement ops or operator on a trader's request);
2. **Named approver** (operator senior or risk officer);
3. **Justification text** (free text recorded in `cdm_payload.justification`);
4. **Reference to the originating transaction** (`replaces_id` or `corrects_id`);
5. **Audit log entry** with timestamps and identity attestations.

The framework rejects any `CORRECTION` lacking any of these five fields. **No path may bypass**: this is the key fraud-and-error mitigation.

### 6.4 Exception management

The aged-break workflow (`L_18.BreakRegister` FSM):

| Break age | Aging stage | Owner |
|---|---|---|
| 0–1 BD | `Open` | Settlement ops analyst |
| 2–3 BD | `Aged-1` | Settlement ops team lead |
| 4–5 BD | `Aged-3` | Operations head |
| 6–10 BD | `Aged-5` | Group operations head |
| 11+ BD | `Escalated` | CFO + CRO joint sign-off |

**Disclosure trigger**: at year-end, every break aged > 10 BD is reported to the audit committee with a remediation plan.

### 6.5 Evidence retention

**Standard:** SOX 404 / SEC Rule 17a-4(b)(4) requires 7 years for broker-dealer records; CSDR Article 12 requires 7 years for settlement records; FCA SUP 16 / MiFID II RTS 6 requires 7 years; IFRS does not specify but professional standards (IAASB) recommend the longer of 7 years or the regulatory requirement.

**Recommendation for the framework:** **7-year retention** of:
- Full `L_13` move stream;
- Full `L_15.Obligation` history including all status transitions;
- Full `L_11.ExternalConfirmation` envelopes (signature-verified);
- Full `L_18.BreakRegister` history including resolutions;
- All SOX / SOC 1 control evidence (test results, exceptions, remediations).

The framework's append-only event log + bitemporal `(t_obs, t_known)` makes this retention structurally satisfied: nothing is deleted; historical states are reconstructible by replay (Λ8 replay determinism).

### 6.6 ICFR (Internal Control over Financial Reporting) certification

For SOX 404(b) management certification, the CEO and CFO must certify:

1. The trade-date economic recognition is consistently applied;
2. The settlement obligation is fully and accurately reported on the balance sheet;
3. Material breaks are disclosed in the financial statements;
4. ECL provisions are computed in accordance with policy;
5. CRR / Basel III capital treatment is correctly applied.

**The framework's design supports each of these certifications because each is a deterministic projection over the move stream + obligation register + reconciled depot, not an assertion-based judgment.**

---

## 7. Materiality thresholds for fails

### 7.1 The disclosure-event matrix

| Threshold | Quantitative | Qualitative | Disclosure / action |
|---|---|---|---|
| Aggregate unsettled receivable > 1% of balance sheet | Triggered at ~£1.5bn for a typical tier-1 entity | n/a | Separately presented on face of balance sheet (IAS 1.55) |
| Single-counterparty unsettled receivable > 10% of CET1 | Triggered at ~£2bn for tier-1 dealer | Concentration risk | Large exposures reporting (CRR Article 392); Pillar 3 disclosure |
| Failed trade aged > 5 BD | Per-trade £100k+ | CSDR penalty accrual; CCR capital ramp | Risk committee report; COREP C 28.00 |
| Failed trade aged > 7–15 BD (CSDR mandatory buy-in) | Per-trade £1m+ | Mandatory buy-in process triggered (post-CSDR-Refit, 2024) | Buy-in workflow; counterparty escalation |
| ECL Stage 2 migration on settlement receivables > 5% of gross | n/a | Increased credit risk | IFRS 7.35F disclosure |
| Manufactured-dividend obligation unrecognised at year-end | Per-position £50k+ | Cum/ex audit trap | Provision under IAS 37.14 if probable and reliably measurable |
| Cross-currency open exposure > Herstatt limit | Per-leg £50m+ | Herstatt risk window | Risk committee escalation; Pillar 3 narrative |
| Repeat counterparty fails (> 3 fails per quarter, same LEI) | n/a | Counterparty operational quality | Counterparty review; potential trading-relationship action |
| Single fail > 25% of trading-day notional in that ISIN | Per-trade ISIN-specific | Liquidity / market-risk concentration | Risk committee + immediate market-quality review |

### 7.2 Quantitative materiality

Per ISA 320 (group materiality typically 0.5–1% of pre-tax profit, capped by net-asset materiality):

- Tier-1 dealer (£20bn CET1, £6bn pre-tax profit): group materiality typically £30–60m; clearly trivial misstatement threshold (CTMP) at 5% of materiality, i.e., £1.5–3m.
- A single failed trade > £3m is material to the engagement; aggregated fail population > £30m is materially misstated unless properly disclosed.

### 7.3 Qualitative materiality (regulatory escalation)

Even below the quantitative threshold, an item is materially relevant if:

- **CSD fines**: any CSD-imposed fine (regardless of amount) triggers regulatory disclosure (Pillar 3) and audit committee notification.
- **Regulatory escalation**: an FCA / SEC / ESMA inquiry into a fail pattern is material regardless of financial impact.
- **Repeat counterparty**: > 3 fails / quarter from the same LEI raises operational-risk concentration, requiring disclosure even if individually immaterial.
- **Cross-jurisdictional pattern**: fails concentrated in one CSD or jurisdiction may indicate operational issues with the firm's settlement infrastructure (e.g., a custodian relationship issue).
- **News-cycle exposure**: a high-profile fail (e.g., a meme-stock squeeze or a CSDR penalty headline) requires disclosure consideration even if financially small.

### 7.4 Reporting cadence

| Frequency | Report |
|---|---|
| Daily T+1 | Internal: aged break report; escalation triggers per §6.4 |
| Monthly | CSDR penalty advice reconciliation; Pillar 3 internal review |
| Quarterly | Fail-rate analysis by counterparty, currency, CSD; ECL Stage 2 migration review |
| Quarterly (Q+45 days) | Pillar 3 settlement-fail disclosure (CRR Article 442) |
| Annually (year-end) | Full balance-sheet open-settlement disclosure; ECL provision; CRR capital tie-out; SOX 404 ICFR certification |

---

## 8. Manual-override and CORRECTION transaction policy

### 8.1 When retroactive amendments are permitted

The Ledger framework's append-only event log means **no transaction is ever deleted**. Retroactive amendments are achieved exclusively through `CORRECTION`-typed transactions that emit anti-moves reversing the original transaction's effects. The original transaction remains in the move stream.

**Permitted scenarios:**

1. **Trade booking error** (e.g., wrong ISIN, wrong quantity, wrong side): `CORRECTION` reverses the original moves; new `SETTLEMENT` transaction books the corrected trade. Both transactions in the audit trail.
2. **Counterparty disputes the trade** (not the same as failed settlement): mutual agreement to bust the trade. `CORRECTION` reverses; status of original obligation transitions to `Cancelled`.
3. **CSD reports incorrect settled amount** (custodian-side error in the depot statement): `CORRECTION` adjusts the position to match the corrected depot reconciliation.
4. **Accounting policy correction at year-end** (e.g., reclassification from FVOCI to FVTPL): handled via journal entry, not a `CORRECTION` move (the underlying position is unchanged; only the classification changes).

**NOT permitted scenarios** (the "no-fly zone"):

1. **Hiding a failed settlement** by reversing the original trade post-fail. Forbidden — the economic exposure existed and must be retained.
2. **Pre-dating a trade** to optimise period-end allocation. Forbidden — the trade timestamp is set at execution and is immutable.
3. **Adjusting `own` to match a custodian's wrong record**. Forbidden — the custodian must be challenged; reconciliation breaks must be investigated, not papered over.
4. **Deleting a CORRECTION** (a "correction of correction" attempting to make the original CORRECTION disappear). Forbidden — append a new CORRECTION with proper rationale.

### 8.2 Approval and evidence retention

Every `CORRECTION` transaction MUST carry:

```
Transaction(type=CORRECTION):
  references: <original_tx_id>
  reason_code: <closed-sum: BOOKING_ERROR | CPTY_DISPUTE | CSD_RESTATEMENT | OTHER>
  justification: <free text, mandatory>
  requester_lei: <LEI of the person requesting the correction>
  approver_lei: <LEI of the person approving (must differ from requester)>
  approver_role: <closed-sum: OPERATIONS_HEAD | RISK_OFFICER | CFO_DELEGATE>
  approval_timestamp: <UTC>
```

**Four-eyes is non-negotiable.** The framework rejects any `CORRECTION` where `requester_lei == approver_lei`.

### 8.3 The audit trail survives

After a `CORRECTION`:

- The original transaction remains in `L_13.MoveStream` at its original `(t_obs, t_known)`.
- The CORRECTION transaction is appended at its own `(t_obs, t_known)`.
- The bitemporal query `as_of(t)` for any `t` between the original and the correction returns the original (un-corrected) state — for forensic purposes.
- The query `with_corrections_through(t_known')` returns the corrected state — for current reporting.

This is the IFRS 9 / IAS 8 prior-period restatement discipline (IAS 8.42 — material prior-period errors corrected by restating comparative information). The framework's bitemporal model is a structural implementation of IAS 8.

### 8.4 SOX implications

A CORRECTION transaction is a **change-management event** in the SOX ICFR sense:

- Triggers a control-evidence record;
- Reviewed by internal audit on a rolling sample;
- Aggregated for the audit committee quarterly;
- Material corrections (> CTMP) reviewed individually by the engagement audit team.

**Frequency thresholds:**

- > 10 CORRECTIONs per month from the same trader = control-environment red flag;
- Any CORRECTION reversing > £10m position = audit committee notification;
- Any CORRECTION of a year-end balance after the cut-off = potential restatement consideration (IAS 10 subsequent-events).

---

## 9. Year-end tie-out — what the external auditor will demand

### 9.1 The audit reconciliation

At year-end, the engagement auditor will require the firm to produce, for every wallet × unit × counterparty combination with material balance:

```
Opening balance (1 Jan)
+ Σ all SETTLED moves over the year (debit and credit, by type)
+ Σ all unsettled position changes (open at 1 Jan, settled / failed during year)
+ Σ all year-end open positions
= Closing balance (31 Dec)
```

The reconciliation is **per wallet, per unit, per counterparty**. It must tie:

- The opening balance to the prior year-end audited balance (forming the prior-year-end opinion-anchor).
- Each line of activity to the underlying `L_13.MoveStream` records and the `L_15.Obligation` history.
- The closing balance to the year-end depot statement (positive evidence) + the open-settlement register (the receivable / payable on the face of the balance sheet).

**Form of the reconciliation:**

| Line | Source | Amount |
|---|---|---|
| Opening balance — settled at depot | Prior-year audited | X |
| Opening balance — settlement receivable (open at 1 Jan) | Prior-year-end open obligations | Y |
| Trades executed during year (Σ buys − Σ sells) | `L_13` net | A |
| Settlements completed during year (Σ discharged obligations) | `L_15` discharged | A − Δ |
| Settlement fails during year (Σ failed, written off / bought-in) | `L_15` failed | Δ_fail |
| Closing balance — settled at depot | Computed; tied to `T+2+ε` depot statement | X' |
| Closing balance — settlement receivable / payable (open at 31 Dec) | Year-end open obligations | Y' |
| **Total closing** | **Tied to balance sheet line items** | **X' + Y'** |

### 9.2 The four-corner audit test

The auditor will trace a sample of items in four directions:

1. **Existence**: from balance sheet → general ledger → `L_13` → external confirmation (`sese.025` / depot statement). Confirms the asset exists.
2. **Completeness**: from external feed (FIX archive, CSD instruction file) → ledger. Confirms no transactions are missing.
3. **Cut-off**: trades executed close to year-end (last 2 BD of December and first 2 BD of January) tested individually. Confirms trades are recorded in the correct period.
4. **Valuation**: market price at 31 December applied to position; tied to Level 1 / Level 2 / Level 3 fair-value hierarchy disclosures.

### 9.3 IPE testing on the reconciliation report

Per PCAOB AS 2110 and ISA 500.10, the year-end reconciliation report itself is information produced by the entity (IPE) and must be tested for completeness and accuracy:

- **Reperformance**: re-derive the report from the raw `L_13` + `L_15` + depot statements; tie to the entity's official version.
- **Sample tie-out**: 25–40 items traced from report → underlying records → external confirmations.
- **Edge cases**: open settlements, cross-currency positions, partial fills, recent CORRECTIONs deliberately oversampled.

The framework's design — move stream as immutable source, status as a deterministic projection — makes this audit-friendly. The IPE evidence is **constructive** (re-derivable from primitives) rather than assertion-based.

### 9.4 Specific tie-out items

| Item | Tie-out method |
|---|---|
| Settled positions at depot | Depot statement at 31 Dec close; reconcile to `w_csd_nostro.own(ISIN)` |
| Unsettled receivables / payables | Open `L_15.Obligation` register at 31 Dec; reconcile to balance sheet line item |
| Cash at custodian | Bank statement; reconcile to `w_csd_cash.own(currency)` |
| Trade activity | FIX archive sequence-number completeness test |
| ECL provision | Recompute on sample; reconcile to balance sheet provision line |
| CSDR penalty paid / received | T2S monthly advice; reconcile to operating expense / income |
| CRR settlement-risk capital (Article 379) | Recompute on aged-failed obligations; reconcile to COREP C 28.00 submission |

### 9.5 Materiality of year-end open positions

For a tier-1 dealer:

- Total settled positions: ~£280bn at year-end (typical).
- Aggregate unsettled receivables: ~£4bn (typical, ~1.5% of balance sheet).
- Aggregate unsettled payables: ~£3.8bn.
- Net unsettled: ~£200–500m (depends on directional bias of unsettled trades).

The aggregate unsettled is **always material** to the balance sheet of a tier-1 dealer and **always requires** separate disclosure under IAS 1.55 + IFRS 7.

---

## 10. Cum/ex corporate action audit trail

### 10.1 The cum/ex problem

When a corporate action's record date falls within the open settlement window `[T, T+k]`:

- The **trade-date economic owner** (the buyer at `T`) is economically entitled to the corporate action.
- The **registered holder at record date** (the seller, who is still on the CSD register until `T+k`) receives the corporate action from the issuer.
- A **manufactured payment** must flow from seller to buyer to align economic and legal entitlement.

This is the source of countless audit issues, because:

1. Failure to recognise the buyer's entitlement at trade-date violates the trade-date accounting principle (a missing receivable at year-end);
2. Manufactured payments are easily lost in the operational pipeline (the seller benefits silently from a dividend they shouldn't keep);
3. Cum/ex fraud schemes (the German "cum/ex" scandal of 2007–2012) exploited exactly this gap — multiple parties claimed the same dividend's withholding-tax credit by exploiting the timing window between trade and settlement.

### 10.2 The audit trail

For every trade where `record_date ∈ (T, T+k]`, the framework MUST produce a per-trade record of:

| Field | Source | Audit purpose |
|---|---|---|
| Trade execution date `T` | `L_13` trade transaction | Economic entitlement timestamp |
| Settlement date `T+k` | `o.intended_settlement_date` | Legal title transfer timestamp |
| Corporate action ex-date | Reference data (Bloomberg / Refinitiv / issuer agent) | Cum-trade / ex-trade determination |
| Corporate action record date | Reference data | Holder-of-record snapshot |
| Cum-or-ex flag at trade time | Determined by `T` vs ex-date | Entitlement determination |
| Manufactured payment obligation | New `L_15.Obligation`, kind = `MANUFACTURED_PAYMENT` | Audit trail for the payment flow |
| Counterparty LEI | Trade record | Tax reclaim / withholding attribution |
| Tax-residency of buyer / seller | KYC reference data | Withholding tax determination |

### 10.3 Standard reference

- **IAS 32.AG36** (treatment of dividends on equity instruments).
- **IFRS 9.B3.2.13** (transfer of contractual rights — the buyer has acquired the contractual right to the dividend at `T`, even though legal title transfers at `T+k`).
- **IFRS 16 / IAS 18** (revenue recognition framework — for the issuer's perspective).
- **IAS 12** (income taxes — withholding tax attribution).

### 10.4 Common audit issues

The five recurring audit issues on cum/ex:

1. **Missed manufactured-payment claim** (silent under-payment to the buyer): the seller receives the dividend, the buyer's records do not show a receivable, the seller benefits silently. **Detection**: audit sample of trades where `record_date ∈ (T, T+k]`; trace to manufactured-payment obligation; if missing, raise as control deficiency.

2. **Double-counting of dividend entitlement** (cum/ex fraud): multiple parties claim the dividend's tax credit. **Detection**: dividend claim per ISIN per record date should sum to issued shares × dividend per share; deviations are red flags. The framework's deterministic event log + counterparty LEI tagging makes this auditable.

3. **Wrong cum/ex determination** at trade time (treating an ex-trade as cum or vice versa): typically caused by mis-timing of the venue's ex-date observation. **Detection**: tie venue ex-date to issuer agent ex-date; deviations are red flags.

4. **Manufactured-payment timing** (paying the manufactured dividend on the wrong date — typically too late): can trigger interest claims and reputational issues. **Detection**: aged manufactured-payment obligations; SLA at payment date + 5 BD.

5. **Withholding tax errors**: the seller (registered holder) suffers withholding at their tax-residence rate; the buyer (economic owner) may be entitled to a different rate; reclaim mechanisms vary by jurisdiction. **Detection**: tax-treaty residence verification on every cum/ex trade.

### 10.5 The cum/ex tax-fraud red flag

If the same trade pattern (same ISIN, same record date, same counterparty pair, same notional) appears repeatedly across tax jurisdictions with apparently optimised tax outcomes, this is a **cum/ex fraud red flag**. The 2007–2012 German cum/ex scandal involved multi-billion-euro losses to the German tax authority through such patterns.

**Audit response under ISA 240** (auditor's responsibilities relating to fraud):

- Identify the pattern through analytical procedures (concentration of trades around record dates; same counterparties; cross-jurisdictional flows).
- Escalate to the engagement partner.
- Consider regulatory-disclosure obligations (ML/STR reporting, tax-authority notification if jurisdiction requires).
- **Do not soften the finding** — this is a category of fraud the audit profession has been criticised for missing in the past.

---

## 11. Cross-currency accounting

### 11.1 FX revaluation timing

For cross-currency settlements (e.g., a USD-domiciled buyer purchasing EUR-denominated equity at Xetra, settling in EUR via Clearstream, with FX hedge):

**IAS 21 (Effects of Changes in Foreign Exchange Rates) framework:**

- **Monetary items** (cash, receivables, payables denominated in foreign currency): translated at the closing rate on each reporting date; FX gains / losses recognised in P&L (IAS 21.28).
- **Non-monetary items at FVTPL** (FVTPL equities denominated in foreign currency): translated at the closing rate on each reporting date; the entire change in fair value (including FX) recognised in P&L (IAS 21.30).
- **Non-monetary items at FVOCI** (equity FVOCI election): translated at closing rate; FX gain / loss reported in OCI (IAS 21.30).

**Embedded FX in equity trades.** When a USD entity buys EUR equity, the trade has two FX exposures:

1. **The equity itself** is denominated in EUR; mark-to-market gains and losses include FX.
2. **The settlement payable** (5,000 EUR owed to the seller at `T+2`) is a EUR monetary liability; revalued at each reporting date at the closing rate.

Both are translated at the same rate (closing) but their gain / loss recognition pattern differs slightly (the equity's full FV change including FX hits P&L for FVTPL; the payable's FX change hits P&L as a separate line).

### 11.2 Settlement-day FX

On settlement day `T+2`:

- The EUR cash leg settles in EUR (Clearstream / TARGET2);
- The USD entity's USD cash leg (the FX leg) settles in USD (Fedwire / CHIPS);
- These settle at different times, and at potentially different FX rates from the trade date.

**Journal entry pattern (US dealer, USD reporting):**

```
At T (trade in EUR):
  Dr Financial assets — FVTPL (EUR equity, USD-translated) X
  Cr Settlement payable — EUR                              X
  (X = 5,000 EUR × FX_T)

At T+1 (mark-to-market and FX revaluation):
  Dr / Cr FA-FVTPL by FV change × FX_T
  Dr / Cr FA-FVTPL by FX revaluation (closing rate − T rate) × position
  Dr / Cr Settlement payable by (FX_{T+1} − FX_T) × 5,000 EUR
  Net FX gain/loss to P&L

At T+2 (settlement):
  Dr Settlement payable — EUR    X' (at FX_{T+2})
  Cr Cash — USD                   X'
  (where X' = 5,000 EUR × FX_{T+2})
  + reclassify equity from "FVTPL in transit" to "FVTPL settled at custodian"
```

### 11.3 The Herstatt window

**The Herstatt window is the time period between the first and second leg of a cross-currency settlement when one leg has settled and the other has not.** During this window, the entity has paid out one currency but not yet received the other; if the counterparty defaults during the window, the entity loses the entire delivered leg.

**Example (USD/JPY trade):** USD entity buys JPY equity. JPY leg settles in TARGET2 / Tokyo morning; USD leg settles in Fedwire / NY afternoon. The Herstatt window is the 8–10 hours between the two.

**Mitigation: CLS (Continuous Linked Settlement)** for major currency pairs (USD, EUR, GBP, JPY, CHF, AUD, etc.) provides PvP atomicity within the CLS window. Non-CLS legs (most EM currencies, some minor majors) carry residual Herstatt risk.

**Disclosure:** CRR Article 442 + IFRS 7.B11 require disclosure of cross-currency settlement risk and any limits / mitigations. Pillar 3 narrative should disclose:

- Aggregate cross-currency open exposure;
- CLS-eligible vs non-CLS-eligible split;
- Largest single-counterparty Herstatt exposure;
- Internal Herstatt limits (per-counterparty, per-currency-pair).

### 11.4 IAS 21 monetary-vs-non-monetary classification

| Item | Class | Translation rate | Gain/loss recognition |
|---|---|---|---|
| Cash | Monetary | Closing rate | P&L (IAS 21.28) |
| Settlement receivable / payable | Monetary | Closing rate | P&L |
| FVTPL equity (foreign currency) | Non-monetary | Closing rate | P&L (IAS 21.30) |
| FVOCI debt (foreign currency) | Monetary | Closing rate | P&L for FX; OCI for FV change |
| FVOCI equity (foreign currency) | Non-monetary | Closing rate | OCI (IAS 21.30) |
| Inventory at cost | Non-monetary | Historic rate | n/a |

For settlement receivables / payables: **always monetary, always translated at closing rate, FX gains / losses always to P&L.** No other treatment is permitted.

### 11.5 Audit issues on cross-currency

The recurring cross-currency audit issues:

1. **FX hedge designation** (IFRS 9 hedge accounting): if the FX leg is designated as a cash-flow hedge of the foreign-currency settlement, hedge documentation must satisfy IFRS 9.6.4. Failures of effectiveness testing trigger de-designation and immediate P&L recognition.
2. **Embedded vs free-standing FX**: in dual-currency equity trades, the FX exposure is embedded in the FVTPL equity; the FX hedge is free-standing. The two should not be netted in disclosure.
3. **Herstatt window misalignment**: settlement timing assumptions (e.g., assuming both legs settle on the same calendar day) can produce misstatements at quarter-ends spanning multiple time zones.
4. **CLS effectiveness**: assuming CLS atomicity when one leg is non-CLS-eligible. Detection: tag every cross-currency obligation with its settlement venue.

---

## 12. What I reject from Phase 1 proposals on accounting grounds

In the spirit of the Phase 2 mandate, I name the Phase 1 positions I reject and explain why on accounting / audit grounds. Where the Settlement Team has converged on the mainstream design, these rejections affirm that convergence.

### 12.1 SBL.md (Margaret Chen) — seventh GPM coordinate `inflight`

**Position:** add `inflight` as a stored seventh coordinate on the position vector.

**Rejection on accounting grounds.** The seventh-coordinate proposal collapses the *economic position* and the *settlement-pending* dimensions into the same wallet read. This violates the IAS 32.42 offsetting prohibition and IAS 1.32 gross-presentation requirement: the receivable (long the security) and the payable (short the cash) are obligations to *different counterparties*, and must be presented gross. A single `inflight` coordinate aggregating receivables and payables breaks this structurally. **Mainstream-team accepted: keep position state on `own`; carry obligations in `L_15` and contra-entries in counterparty / CSD virtual wallets.**

### 12.2 Feynman.md — `own_economic = own_settled + own_inflight` projection

**Position:** split `own` into `_settled` and `_inflight` sub-coordinates with the same algebraic semantics.

**Rejection on accounting grounds.** While elegant in the futures-`accumulated_cost` style, this proposal makes PnL a function of the projection, which is a stored composite. For audit substantiation, `own` must be a single, directly-readable, auditor-tie-out-able number representing the economic position. The settlement-pending portion belongs in the obligation register, not as a sub-coordinate. **Settlement Team accepted: `own` is the position; the obligation is the open contra in `L_15`.**

### 12.3 Geohot.md — minimum-minimum: `settlement_status` as a transaction flag, no obligation row

**Position:** the minimum is a single `settlement_status` field on the transaction; obligation row is not load-bearing.

**Rejection on audit-and-capital grounds.** Capital reporting (CRR Article 379 aged-bucket schedule), CSDR penalty attribution, ECL Stage 2 migration, and BCBS 239 lineage all require **per-trade granularity of the settlement obligation lifecycle** with bitemporal history. A bare flag on the transaction cannot answer "what is the aged-bucket distribution of failed settlements at year-end?" without an aggregate scan, and cannot drive the COREP C 28.00 schedule or the CSDR penalty obligation. **Settlement Team accepted: `L_15.Obligation` is first-class.** (Geohot's deletion list was correct on what NOT to add; it under-specified what MUST be present for audit.)

### 12.4 Karpathy.md — two virtual wallets per leg + obligation row (overly fine granularity)

**Position:** `cpty_v` (counterparty) + `csd_v` (depot) per leg + obligation row per leg.

**Rejection on simplicity / audit grounds.** While operationally fine, the two-virtual-wallet split is more granularity than auditors need or can effectively test. The mainstream design uses a single counterparty virtual wallet pre-settlement and a CSD nostro virtual wallet post-settlement, with the rotation transaction at `T+2+`. This is consistent with v10.3 §2.5 and is sufficient for the reconciliation identity. The two-virtual-wallet split is operationally permissible (firms may implement it for break-investigation granularity) but should not be normative in the framework spec.

### 12.5 Cartan.md / Halmos.md — obligation as a unit (`u^circ` / `\sigma`)

**Partial acceptance.** Both proposals model the open obligation as a unit in the unit universe. **The Settlement Team has accepted this**: the `L_15.Obligation` is keyed by `obligation_id` derived deterministically from `(business_event_id, leg_index)`, satisfying the unit-identity discipline. **However**, on accounting grounds, the obligation is not "a security at issuance" — it is a **contractual obligation to deliver / pay**. Calling it a unit is technically correct (it earns a place in `\mathcal{U}` via StatesHome) but misleading: it has no fair value (other than CSDR penalty accrual) and is not FVTPL-classified. The accounting policy treats it as a memo-item / off-balance-sheet contractual obligation, with the underlying economic position fully reflected in `own`. The unit-status framing is operationally correct; the accounting framing is liability-and-receivable.

### 12.6 Settlement-date accounting as primary mode (universally rejected, but worth naming)

**No Phase 1 proposer advocated settlement-date accounting as primary,** but for the audit record I confirm: settlement-date accounting at the ledger primitive level is **rejected unanimously by accounting standards (IFRS 9.B3.1.3, ASC 320-10-25-3 default to trade-date for trading-book) and by capital regulation (CRR Article 325 trade-date market risk).** The framework does not support settlement-date as a primary mode; it is a downstream projection only.

### 12.7 Affirmation as discharge (NAZAROV correctly flagged this — preserved)

**Position rejected (correctly):** treating DTCC ITP CTM affirmation (`T+1` 9pm ET in T+1 regime) as discharge. This is a pre-finality milestone, not a settlement confirmation. **Settlement Team accepted: discharge requires `sese.025` (or `camt.054` for cash-only) attestation; affirmation is `AwaitingFinality` only.**

### 12.8 No fail-by-inference (NAZAROV — preserved as INV-DS-3)

**Position accepted (correctly):** transition to `Failed` requires positive attestation of fail (CSD-issued fail status), not absence of confirmation past deadline. Absence is `AwaitingFinality`. **Critical for SOX 404 control evidence — without a positive attestation, the firm cannot evidence that a settlement actually failed (vs. just being delayed).**

---

## 13. Deferred tax — brief note

Trade-date economic recognition affects timing differences for tax purposes, although the impact for short-dated cash-equity settlements is small.

**IAS 12 / ASC 740 framework:**

- **Trading book FVTPL gains/losses**: typically taxed as they accrue in the financial statements (i.e., trade-date), with no deferred tax timing difference in jurisdictions where tax follows accounting.
- **Capital gains regime jurisdictions** (some US treatment for HTM portfolios; certain individual investor regimes): tax may follow legal-title transfer (settlement date), creating a 1–2 day timing difference. For a tier-1 dealer's trading book, this is immaterial.
- **Withholding tax on dividends in cum/ex window** (§10): attribution of withholding tax follows the registered holder at record date (i.e., the seller), even if the buyer is the economic owner. The buyer may have a withholding-tax-reclaim entitlement under tax treaties; deferred tax recognition depends on whether the reclaim is virtually certain.

**For the framework**: the open settlement obligation does not generally create deferred tax timing differences for FVTPL trading book. The only material deferred tax issue is the cum/ex withholding-tax attribution, which is a reclaim accounting question (IAS 12.74 — recoverable amount) rather than a settlement-timing question.

**Disclosure**: per IAS 12.81, no specific deferred tax disclosure is required for settlement-pending balances; the underlying FVTPL gain/loss disclosure suffices.

---

## 14. Summary — what the Settlement Team's design must enforce

Distilling this section into the actionable list for `deferredSettlement.tex`:

| Item | Requirement | Standard reference |
|---|---|---|
| Trade-date economic recognition | MANDATORY at ledger primitive | IFRS 9.B3.1.3, ASC 320-10-25-3, Single-Coordinate Move Principle |
| Balance-sheet presentation | Gross receivable / payable; separately disclosed when material | IAS 1.55, IFRS 7.6, IAS 32.42 |
| Settlement-date accounting | Downstream projection only; never a ledger primitive | IFRS 9.B3.1.5 (consistent application) |
| Audit evidence chain | 5-document chain (FIX → sese.023 → sese.025 → camt.054 → depot) | ISA 500, ISA 505, BCBS 239 P6, SOX 404 |
| ECL on settlement receivables | De minimis for CCP; per-trade for material bilateral; CSDR fail = Stage 2 | IFRS 9.5.5.15, IFRS 9.B5.5.43, ASC 326-20 |
| CRR settlement-risk capital | Aged buckets per Article 379 (5–15d, 16–30d, 31–45d, 46+d) | CRR 575/2013 Article 378–380, COREP C 28.00 |
| CSDR penalty | Per-day accrual; separate `L_15.Obligation` of kind CSDR_PENALTY | CSDR Art. 7, Reg (EU) 2017/389 |
| SOX / SOC 1 controls | Segregation of duties (StatesHome C11); four-eyes on CORRECTION; 7-year retention | SOX 404, SEC Rule 17a-4, CSDR Art. 12 |
| Materiality thresholds | 1% balance-sheet aggregate; 10% CET1 single-counterparty; 5d aged fail; 5% Stage 2 | IAS 1.55, CRR Art. 392, IFRS 7.35F |
| Manual-override / CORRECTION | Append-only; four-eyes; bitemporal preserved; no in-place mutation | IAS 8.42, append-only event sourcing |
| Year-end tie-out | Per (wallet, unit, counterparty); opening + activity = closing; tied to depot statement | ISA 330, PCAOB AS 2310 |
| Cum/ex audit trail | Manufactured-payment obligation per cum/ex trade; ex-date / record-date attestation | IAS 32.AG36, IFRS 9.B3.2.13, ISA 240 |
| Cross-currency / Herstatt | Two obligations per cross-currency trade; CLS attestation where eligible; Pillar 3 disclosure | IAS 21.28–30, CRR Art. 442 |
| Deferred tax | Generally immaterial for FVTPL trading book; cum/ex withholding-tax reclaim is the live issue | IAS 12, IAS 12.74 |

---

## 15. Sign-off

This section is normative for the Settlement Team's `deferredSettlement.tex` v11.0 deliverable on accounting, audit, and capital matters. The treatment:

- Defaults to trade-date accounting at the ledger primitive level (mandatory; not optional);
- Specifies the gross balance-sheet presentation under IAS 1 / IFRS 7;
- Mandates the 5-document audit evidence chain with ISA 500 / 505 / BCBS 239 / SOX 404 grounding;
- Specifies the ECL treatment under IFRS 9 simplified approach with CCP de minimis and bilateral material thresholds;
- Specifies the CRR / Basel III aged-bucket capital schedule for failed settlements;
- Specifies the CSDR penalty regime as a separate `L_15.Obligation` with per-day accrual;
- Specifies the SOX / SOC 1 control framework with segregation of duties, four-eyes on CORRECTION, and 7-year evidence retention;
- Specifies materiality thresholds (quantitative and qualitative) for disclosure events;
- Specifies the manual-override and CORRECTION discipline (append-only, four-eyes, bitemporal preservation);
- Specifies the year-end tie-out the external auditor will demand;
- Specifies the cum/ex audit trail and the manufactured-payment obligation (cum/ex fraud red-flag);
- Specifies the cross-currency / Herstatt accounting treatment and disclosure requirements;
- Explicitly rejects (with reasoning) the Phase 1 positions inconsistent with this section.

The accounting and audit consequences of departing from this section's prescriptions are: financial statement misstatement (IFRS 9 / IAS 1), audit qualification (ISA 500 / 505), regulatory capital under-statement (CRR Article 379), SOX ICFR failure (Section 404), and — at the extreme — exposure to cum/ex fraud (IAS 12 / withholding tax). None of these is acceptable.

— Reginald Ashworth, FCA
Senior Partner, Banking Assurance
30 April 2026
