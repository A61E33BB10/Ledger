# Deferred Settlement on Cash Equities — Accounting and Audit View

**Author**: Reginald Ashworth, Senior Partner, Banking Assurance
**Phase**: 1 (independent proposal, no cross-talk)
**Date**: 30 April 2026
**Subject**: Representation of the open settlement obligation between trade date $T$ and settlement date $T+2$ for cash-equity trades, framed by the audit and balance-sheet substantiation an external auditor will demand.

---

## Executive Position

Cash-equity trades on listed venues are **regular-way trades** under both IFRS 9 (B3.1.3) and US GAAP (ASC 320-10-25-3). The framework MUST default to **trade-date accounting**. Settlement-date accounting is permitted as a policy election but creates a discontinuity between economic exposure and book recognition that is unacceptable for any entity with a Pillar 3 reporting obligation, an FVTPL trading book, or a daily PnL discipline. The Ledger's "trade as atomic transaction" primitive already encodes trade-date accounting; the deferred-settlement representation must preserve and substantiate this.

The open obligation between $T$ and $T+2$ is **a recognised receivable / payable, settlement-pending**, not an off-balance-sheet item. It must be visible in the move stream from $T$, reconcilable to the nostro/depot at $T+2^+$, and degenerate gracefully across all variants (T+1, T+0, fail, partial, short, recall, corporate action, cross-currency, DvP).

---

## 1. State Representation

### 1.1 Core construct

The deferred-settlement obligation is represented by a **per-counterparty, per-leg pending-settlement virtual wallet**, paired with the real-side position in `own`. The naming convention:

- `w_{CSD,B}` — virtual wallet representing the buyer's position at the central securities depository (CSD) leg, before CSD confirmation. *Receives securities at* $T+2^+$.
- `w_{CSD,S}` — seller's CSD virtual wallet. *Releases securities at* $T+2^+$.
- `w_{cash,B}` — buyer's cash nostro virtual wallet. *Releases cash at* $T+2^+$.
- `w_{cash,S}` — seller's cash nostro virtual wallet. *Receives cash at* $T+2^+$.

### 1.2 The four position elements at any time $t \in [T, T+2^+]$

For a buy of $Q$ shares at price $p$, settlement currency $\mathrm{ccy}$:

| Wallet/Coordinate | At $T^+$ | At $T+2^-$ | At $T+2^+$ |
|---|---|---|---|
| `own(w_B, ISIN)` (buyer real) | $+Q$ | $+Q$ | $+Q$ |
| `own(w_S, ISIN)` (seller real) | $-Q$ | $-Q$ | $-Q$ |
| `own(w_B, ccy)` (buyer cash real) | unchanged | unchanged | $-Q \cdot p$ |
| `own(w_S, ccy)` (seller cash real) | unchanged | unchanged | $+Q \cdot p$ |
| `pending_in(w_{CSD,B}, ISIN)` | $+Q$ | $+Q$ | $0$ |
| `pending_out(w_{cash,B}, ccy)` | $-Q \cdot p$ | $-Q \cdot p$ | $0$ |

The economic position (`own`) is true from $T^+$. The settlement-pending state is carried in the virtual-wallet legs that close out at $T+2^+$.

### 1.3 Why this is not a new coordinate

I considered proposing a seventh coordinate on the GPM vector (`pending_in`, `pending_out`). I reject it. The Single-Coordinate Move Principle (Principle 13.2 of v10.3) is load-bearing; introducing a stored "in-flight" coordinate per (entity, unit) creates a regime-dependent semantics for `own` (does in-flight count for PnL? for collateral haircut? for recall?) and reintroduces the Minsky denormalisation trap rejected in the StatesHome ruling.

Instead, **in-flight quantities live in the per-relationship CSD virtual wallet**, exactly as the StatesHome addendum places it (`w^{virtual}_{A↔B}` pattern, §13.5). The PositionState row is `(w_real, ISIN)`; the in-flight contra is a (CSD-virtual-wallet, ISIN) row. Both are first-class in the 3-map schema; neither requires a new map.

### 1.4 Settlement status as `UnitStatus` on the trade unit

Per ledger v10.3 §8.6 (sese.025/camt.054 confirmation return path), each trade carries a **settlement-status lifecycle**:

```
EXECUTED  -->  INSTRUCTED  -->  SETTLED
                          -->  FAILED  -->  PARTIAL_SETTLED
                                       -->  RE_INSTRUCTED
                                       -->  CANCELLED  (CSDR buy-in close-out)
```

This is a `UnitStatus` field on the trade-as-unit (trade-id is itself a unit-of-event in the move stream). It is shared across both counterparties' views of the same trade. Mutation is restricted to the settlement-confirmation handler (C11 writer-cap discipline).

---

## 2. Move Sequence — Move(...) blocks at $T$, $T+1$, $T+2^-$, $T+2^+$

### 2.1 BUY 100 XYZ @ $50, USD, T+2

#### At $T$ (trade execution)

Single atomic transaction — both legs commit or neither:

```
Transaction(type=SETTLEMENT, status=EXECUTED, settlement_date=T+2):
  -- Securities leg (economic recognition, T-date)
  Move(from: w_{CSD,S}, to: w_B,
       unit: ISIN_XYZ, quantity: 100,
       timestamp: T,
       source: "trade_id_42",
       metadata: "EQUITY_BUY_SHARES_T_RECOGNITION")

  -- Cash leg (economic recognition, T-date)
  Move(from: w_B, to: w_{cash,S},
       unit: USD, quantity: 5000,
       timestamp: T,
       source: "trade_id_42",
       metadata: "EQUITY_BUY_CASH_T_RECOGNITION")
```

**Auditor's tie-out**: trade confirmation (FIX 8=ExecRpt or equivalent), execution venue (MIC), counterparty LEI, contract note. CDM `BusinessEvent` of type `EXECUTION` with `before=null, after=Trade(ACTIVE)` stored in transaction payload. ISA 500 — sufficient appropriate audit evidence.

**Why both legs at $T$, not just the security leg**: under IFRS 9.B3.1.3 and ASC 320-10-25-3, regular-way trades are recognised at trade date *as a single transaction*. The cash payable is a recognised liability from $T$, not an executory contract.

#### At $T+1$ (instruction confirmation, no economic move)

```
StatusUpdate(trade_id_42):
  settlement_status: EXECUTED  -->  INSTRUCTED
  external_ref: sese.023 instruction MsgId
  timestamp: T+1
```

No Move primitive fires. This is a `UnitStatus` mutation only. The economic position is unchanged.

**Auditor's tie-out**: outbound `sese.023` Securities Settlement Instruction (or pacs.008 cash leg) acknowledgement from CSD. Linked by `EndToEndId = trade_id_42`.

#### At $T+2^-$ (just before settlement window opens)

No moves. Position unchanged. ECL assessment runs (see §3.2 below).

#### At $T+2^+$ (CSD confirmation)

The CSD confirms DvP. Two compensating moves close out the virtual wallets:

```
Transaction(type=SETTLEMENT_CONFIRMATION, links_to=trade_id_42):
  -- Close out the securities pending leg
  Move(from: w_{CSD,B}, to: w_{CSD,S},
       unit: ISIN_XYZ, quantity: 100,
       timestamp: T+2,
       source: "trade_id_42",
       metadata: "SETTLEMENT_CONFIRMED_SECURITIES",
       external_ref: "sese.025_msg_id")

  -- Close out the cash pending leg
  Move(from: w_{cash,S}, to: w_{cash,B},
       unit: USD, quantity: 5000,
       timestamp: T+2,
       source: "trade_id_42",
       metadata: "SETTLEMENT_CONFIRMED_CASH",
       external_ref: "camt.054_msg_id")

StatusUpdate(trade_id_42):
  settlement_status: INSTRUCTED  -->  SETTLED
```

**Critical note**: the $T+2^+$ moves do **not** change the buyer's or seller's *real* `own` balances on ISIN or cash. They only close the CSD/nostro virtual-wallet contras. The economic position recognised at $T$ stays put. This is the design's load-bearing feature: **the settlement confirmation is reconciliation, not recognition**.

---

## 3. Invariants — Mandatory Economic-Exposure-at-T

### 3.1 Invariant DS-1: Trade-date economic recognition (mandatory)

For every regular-way cash-equity trade, the buyer's `own(ISIN)` increases by $Q$ and the seller's `own(ISIN)` decreases by $Q$ at timestamp $T$ (trade-execution time), not at $T+2$.

**Standard reference**: IFRS 9.3.1.1 (initial recognition); IFRS 9.B3.1.3 (regular-way trade exception); ASC 320-10-25-1 / 25-3 (trade date accounting); ASC 326-20-30-2 (initial recognition basis for receivables).

**Why mandatory**: settlement-date accounting (also permitted under IFRS 9.B3.1.5) creates a two-day window where market-risk exposure exists but is invisible to the trading book. For any FVTPL classification, this breaks the Day 1 P&L recognition (IFRS 13.B5.1.2A, ASC 820-10-30-3A) and makes the ledger's path-independent PnL theorem inconsistent with the firm's official records. **The Ledger does not support a settlement-date election**. Firms wishing to report settlement-date for held-to-collect (HTC) instruments must do so as a downstream reporting projection, not as a ledger primitive.

### 3.2 Invariant DS-2: Conservation across the open window

For all $t \in [T, T+2^+]$ and for the ISIN unit:

$$\sum_w w_t(\text{ISIN}) = 0$$

This is enforced by the conservation law of v10.3 §2.4 unmodified. The inclusion of the CSD virtual wallets as full participants in the conservation sum is the mechanism that allows the buyer's `own = +Q` to coexist with the seller's `own = -Q` *and* the in-flight contras.

### 3.3 Invariant DS-3: Lead-lag reconciliation by design

For all $t < T+2^+$ on a successfully settled trade:

$$\text{Ledger nostro projection}(w_{cash,B}, t) \neq \text{External nostro statement}(t)$$

is the **expected and normal** state. The reconciliation must be parameterised by settlement status:

$$\text{Reconciled}(t) \iff \forall \text{trade}: \text{status}(t) = \text{SETTLED} \implies \text{Ledger}(t) = \text{External}(t)$$

A break detected for a trade with `status = INSTRUCTED` is **not a reconciliation failure**. A break detected for a trade with `status = SETTLED` is a **Stage 1 break** requiring immediate investigation.

### 3.4 Invariant DS-4: Receivable measurement (audit-significant)

The settlement receivable carried in `pending_in(w_{CSD,B}, ISIN)` and the settlement payable carried in `pending_out(w_{cash,B}, ccy)` are **not** measured at fair value through P&L during the open window. They are measured at the contract amount (notional). This is consistent with their nature as short-dated counterparty exposures, not financial instruments held for trading.

**Standard reference**: IFRS 9.5.1.1 (financial assets measured at amortised cost); IFRS 9.5.1.3 (short-term receivables without significant financing component — measured at transaction price under IFRS 15); IAS 32.42 (offsetting criteria — generally not satisfied for settlement receivables/payables to different counterparties).

The market-risk exposure on the ISIN is captured entirely in `own`, which is FVTPL. The settlement leg carries only **counterparty credit risk**, not market risk.

### 3.5 Invariant DS-5: ECL on the settlement receivable (IFRS 9 only)

For a 2-day settlement receivable to a CCP-cleared counterparty (LCH, DTCC, Eurex Clearing, JSCC), **ECL is not zero but is de minimis**. IFRS 9.B5.5.30 permits short-dated trade receivables to use the simplified approach (lifetime ECL). For CCP-cleared trades, the lifetime PD over 2 days is in single-digit basis points and the LGD is reduced by default-fund mutualisation. The framework should:

(a) tag every settlement-pending leg with the counterparty LEI and the CCP LEI (where applicable);
(b) emit an ECL accrual move at $T$ of $\text{ECL}_T = Q \cdot p \cdot \text{PD}_{2d} \cdot \text{LGD}$ from the buyer's P&L to a `w_ECL_provision` virtual wallet;
(c) reverse the ECL accrual at $T+2^+$ on confirmed settlement.

**Standard reference**: IFRS 9.5.5.5 (12-month ECL, Stage 1); IFRS 9.B5.5.43 (Stage 2 trigger — significant increase in credit risk); IFRS 9.B5.5.30 (simplified approach for trade receivables).

**US GAAP equivalent**: ASC 326-20-30-2 (CECL initial recognition); ASC 326-20-30-7 (collective evaluation for similar risk characteristics — settlement receivables are evaluated as a pool).

For non-CCP bilateral settlements (rare for listed equities, common for OTC), the PD is materially higher and Stage migration may occur during the open window. CSDR fail extension (see §6.4) is a Stage 2 trigger.

### 3.6 Invariant DS-6: Capital treatment — counterparty credit risk

Under SA-CCR (CRR Article 274) and Basel III's 2017 amendments, **unsettled DvP transactions attract counterparty credit risk capital** during the contractual settlement window only on the basic approach (CRR Article 379). For trades:

- $T$ to $T+4$ (within contractual settlement period): no CCR capital, market-risk capital only on `own`.
- $T+5$ onward (failing trade): risk weight increases stepwise to 1250% by $T+46$ (CRR Article 379(2)).
- Free-delivery (non-DvP): different regime — exposure recognised from delivery date, capital from $T+1$.

The framework must support extraction of the failing-trade ageing buckets (5 days, 16 days, 31 days, 46+ days) for the COREP C 28.00 (CCR Settlement Risk) template.

---

## 4. Reconciliation — Lead-Lag by Design

### 4.1 The three-way tie-out an auditor will demand

For any $t$ in the window:

| Source | Content | Tie-out timing |
|---|---|---|
| Ledger `own(w_B, ISIN)` | $+Q$ from $T$ | T-date |
| Ledger `pending_in(w_{CSD,B}, ISIN)` | $+Q$ from $T$ to $T+2^-$, $0$ from $T+2^+$ | T-date in, T+2 out |
| External CSD depot statement | $0$ until $T+2^+$, $+Q$ thereafter | T+2 only |
| Counterparty trade confirmation | Trade detail, settlement instruction | T+1 (matching) |

The reconciliation is **not** "do these all agree"; it is "does the lead-lag pattern match the expected status profile". The status field is the parameter that makes the reconciliation tractable.

### 4.2 The break taxonomy

| Status | External depot shows | Ledger shows | Diagnosis |
|---|---|---|---|
| INSTRUCTED | nothing | `pending_in = +Q` | Normal; no break |
| INSTRUCTED | $+Q$ | `pending_in = +Q` | Early settlement (T+1 fast track); `auto-reconcile`, advance status |
| SETTLED | $+Q$ | `own = +Q`, `pending_in = 0` | Normal; no break |
| SETTLED | nothing | `own = +Q`, `pending_in = 0` | **Stage 1 break — false confirmation or depot lag**; investigate within 24h |
| FAILED | nothing | `own = +Q`, `pending_in = +Q` retained | Normal fail; CSDR penalty workflow |
| (any) | $+Q$ | `own = 0`, no `pending_in` | **Stage 2 break — booking failure**; escalate immediately |

The last row is a candidate fraud or control-failure indicator: the depot has shares the ledger does not know about. Per ISA 240, this requires immediate escalation to the engagement partner and consideration of management-override-of-controls risk.

### 4.3 Substantiation evidence package

For every settlement at $T+2^+$, the audit evidence chain is:

1. Original trade confirmation (FIX or equivalent) — **proves $T$-date economic event**.
2. Outbound `sese.023` instruction with `EndToEndId` — **proves instruction at $T+1$**.
3. Inbound `sese.025` confirmation with matching `EndToEndId` — **proves CSD settlement at $T+2^+$**.
4. Inbound `camt.054` cash debit notification with matching reference — **proves cash leg**.
5. CSD depot statement at $T+2^+$ — **independent third-party confirmation (ISA 505)**.
6. Counterparty contract compare (IBP-153/155 equivalent) — **bilateral matching**.

Each move in the ledger carries the `external_ref` field linking to all five external documents. This is the BCBS 239 Principle 6 (accuracy and integrity) lineage requirement, and the SOX 404 / SOC 1 controls evidence for the existence assertion.

---

## 5. CDM Cross-Walk

| Ledger Concept | CDM Construct | Notes |
|---|---|---|
| Trade execution at $T$ | `BusinessEvent` with `intent = EXECUTION`, primitives include `Transfer` | The full Trade object is the unit identity per v10.3 §3.2 |
| Settlement-pending state | `TradeState` lifecycle stage = `EXECUTED` (CDM enum) | Maps to Ledger settlement_status `EXECUTED → INSTRUCTED` |
| Settlement instruction outbound | `SettlementInstruction` (CDM 6.0) → `sese.023` ISO 20022 | Per v10.3 §8.7 |
| Settlement confirmation inbound | `BusinessEvent` with `intent = TRANSFER` settled | Closes the lifecycle |
| Settlement fail | `BusinessEvent` with `intent = OBSERVATION`, `correctionType = FAIL` | New CDM 6.x extension; partial coverage today |
| CSDR penalty | Not directly modelled in CDM; firm extension required | See data layer §15 (operational floor — CSDR penalty schema, $L_{17}$) |
| Partial settlement | `BusinessEvent` with `intent = PARTIAL_TERMINATION` on settlement leg | CDM has hooks; framework must specify decomposition |
| Manufactured corporate-action payment during the window | `BusinessEvent` with `intent = OBSERVATION`, primitive `Transfer` | Existing pattern — see v10.3 SBL §13.21 manufactured dividend |

The CDM `EventIntentEnum` does not yet have a first-class `SETTLEMENT_FAIL` value. The data layer companion's CDM gap analysis ($L_{17}$ break register, §15) should propose this as one of the ~15 PR-sized CDM extensions.

---

## 6. Failure Modes per Case

### 6.1 BUY T+2 (canonical case)

Covered in §2 above. Degenerate when settlement_status = SETTLED at $T+2^+$.

### 6.2 SELL T+2

Symmetric to BUY. Seller's `own(ISIN)` decreases by $Q$ at $T$. The seller's pending leg is `pending_out(w_{CSD,S}, ISIN) = -Q` (equivalently, the CSD virtual wallet shows $+Q$ owed to the buyer's chain). Cash leg reverses: `pending_in(w_{cash,S}, ccy) = +Q·p`.

**Audit-specific note**: for a seller with a LONG `own` position before the trade, this is straightforward. For a short sale (see §6.7), the `own` goes negative at $T$. **Naked short selling without a prior locate is a regulatory violation (SEC Reg SHO Rule 203, EU SSR Article 12)**, but the ledger representation is the same — the regulatory check happens upstream of move generation.

### 6.3 T+1 settlement (US transition, May 2024 onward)

Mechanically identical, with the window halved. The CSD virtual wallets exist for one day instead of two. ECL computations scale linearly. **The framework must not hardcode "T+2"** — settlement_date is a per-trade field (sourced from the venue's settlement convention). The data-layer leaf $L_{1}$ (calendars and conventions) holds the per-(MIC, ISIN) settlement-cycle table.

### 6.4 Settlement fail (CSDR Article 7)

At $T+2^+$, the CSD reports `sese.024` settlement-status fail (or absence of `sese.025`). The framework:

1. `settlement_status: INSTRUCTED → FAILED` (UnitStatus mutation).
2. **Economic position retained** (per v10.3 §8.6 paragraph 5): `own` remains as recognised at $T$. This is correct under IFRS 9 — the financial asset has been recognised; failure to settle does not cause derecognition.
3. **CSDR cash penalty accrual**: per Article 7(2) and Commission Delegated Regulation (EU) 2017/389, the failing party owes a daily cash penalty (basis-point penalty rate × market value × days late). The ledger must:
   - Detect which counterparty is failing (the buyer if `sese.024` cites cash insufficiency; the seller if it cites securities insufficiency).
   - Accrue penalty as a Move from failing party to non-failing party at end of each day in fail.
   - Generate `pacs.008` for the penalty payment per the CSD's penalty cycle (typically monthly aggregation).
4. **Mandatory buy-in** (CSDR Article 7(3)) was suspended via Regulation (EU) 2022/2554 amendment but the framework must support it. After the buy-in extension period (4 business days for liquid instruments), the buyer may execute a market buy and recover the cost differential from the failing seller.
5. **ECL Stage migration**: a fail extending beyond the contractual settlement period is a Stage 2 trigger under IFRS 9.B5.5.43 (significant increase in credit risk). Lifetime ECL applies. For US GAAP, the CECL allowance is recalibrated using the longer expected lifetime.
6. **Capital treatment**: from day 5 of the fail, CRR Article 379 risk weights apply, ramping to 1250% by day 46. The framework's reporting projection must extract this for COREP.

### 6.5 Partial settlement

The CSD delivers some but not all of $Q$. Say $Q_s$ settle, $Q_f = Q - Q_s$ fail. The framework:

1. Generate the SETTLEMENT_CONFIRMATION transaction for $Q_s$ (close out the corresponding pro-rata virtual-wallet entries).
2. Retain the residual virtual-wallet contras for $Q_f$.
3. Set `settlement_status: INSTRUCTED → PARTIAL_SETTLED` and create a child instruction reference for the unsettled remainder.
4. Continue CSDR penalty accrual on the unsettled $Q_f$ only.

**Cash leg**: typically settles atomically with the securities leg in DvP. Under DvP Model 1 (LCH, DTC, T2S), partial settlement of securities means partial settlement of cash, pro-rata. Under DvP Model 2/3 systems, deviations are possible — the framework must verify cash and securities partials are equal-and-opposite. **An auditor will tie cash partial to securities partial line-for-line**.

### 6.6 DvP atomicity

DvP is provided at two levels (v10.3 §8.5):
- **Ledger level**: the trade transaction is atomic — both moves commit or neither does. This is structural.
- **Settlement level**: the CSD's DvP mechanism provides atomicity at the real-world level. T2S, Fedwire/DTC, Euroclear/Clearstream all provide DvP Model 1 (gross, real-time, atomic) for in-scope securities.

**Herstatt risk does not arise on same-CSD DvP** (DvP Model 1). It arises on:
- Cross-CSD trades requiring inter-CSD links;
- Free-of-payment (FOP) transfers where the cash leg settles separately;
- **Cross-currency cash equity trades** (a US trader buying EUR-denominated stock on Xetra) — the EUR settlement at Clearstream and the FX leg at correspondent banks do not settle simultaneously.

For the Herstatt case (§6.9), the ledger must explicitly model the two legs as two separate transactions, not one DvP transaction.

### 6.7 Short sale (composition with §13 GPM)

A short sale executed at $T$ with a borrowed share locate:

```
At T-ε (locate, no movement, just reserved capacity):
  active_locates(seller, ISIN) += Q
  -- Reduces available_to_lend, no Move

At T (short execution):
  Move(from: w_{CSD,seller_borrow}, to: w_buyer,
       unit: ISIN, quantity: Q, ...)
  -- Seller's own coordinate: 0 → -Q (per §13.7 short selling)

At T+1 (borrow settles, depending on locate-vs-borrow timing):
  -- Standard SBL initiation transaction (§13.10 Loan Initiation)
  -- Lender onloan += Q, Borrower borr += Q, collateral posted

At T+2 (short sale settles):
  -- Standard close-out of pending legs (as §2.1)
```

The "deferred settlement" gap on the *short* sale is identical to the long sale gap — same $T$ to $T+2$ window, same `pending_out(w_{CSD,S}, ISIN)` representation. The complication is that `own = -Q` for the seller during the window. **An auditor will ask: does the seller hold enough borrowed shares to deliver at $T+2$?** The answer is in the locate plus the borrow record, not in `own`.

**Failed short sale**: this is the FTD (Failure To Deliver) case — Reg SHO Rule 204 (US) requires close-out by $T+3$ (or $T+5$ for market makers); CSDR penalty (EU) accrues. The framework's representation is identical to the long-side fail (§6.4) plus the SBL-specific wind-down.

### 6.8 Corporate action during the open window (record date $\in [T, T+2]$)

This is the hardest case. Consider a buy on $T$ where the dividend record date is $T+1$ (so ex-date is $T+0$ or $T-1$). Two scenarios:

**Cum-dividend trade** (trade date < ex-date): the buyer is entitled to the dividend even though the trade has not settled. The CSD/issuer pays the dividend to whoever is on the register at record date — which is the **seller** (because the seller is still the registered holder until $T+2$). The seller must therefore pay a **manufactured dividend** to the buyer.

**Ex-dividend trade** (trade date $\geq$ ex-date): the buyer is not entitled. The seller keeps the dividend. The trade price is already adjusted to reflect this.

The framework's representation:

```
At record date (T+1, while trade pending):
  -- Real dividend pays to the registered holder (the seller)
  Move(from: w_issuer, to: w_S,
       unit: USD, quantity: dividend_amount,
       metadata: "DIVIDEND_AS_OF_RECORD_DATE")

At T+2 (settlement) -- IF cum-div:
  -- Manufactured dividend from seller to buyer
  Move(from: w_S, to: w_B,
       unit: USD, quantity: dividend_amount,
       metadata: "MANUFACTURED_DIVIDEND_DEFERRED_SETTLEMENT")
```

**Standard reference**: IAS 32.AG36 (treatment of dividends on equity instruments); IFRS 9.B3.2.13 (transfer of contractual rights — the buyer has acquired the contractual right to the dividend at $T$, even though legal title transfers at $T+2$).

**Audit risk**: this is an area of frequent error. Trade-date economic recognition means **the buyer's `own` position includes entitlement to dividends with record dates $\geq T$ regardless of settlement timing**. Failure to track this manifests as a missed manufactured-dividend claim (usually only the seller benefits — silently). Auditors should sample-test trades where `record_date ∈ [T, T+2]`.

For more complex actions (splits, mergers, rights offerings, dividend-in-kind), the same principle applies: the buyer is economically entitled to anything with a record date $\geq T$. Stock splits handled cleanly by the lifecycle event mechanism at the issuer-virtual-wallet level (v10.3 §5.3 corporate actions).

### 6.9 Cross-currency (Herstatt) DvP

A US-domiciled buyer purchases 100 shares of a Xetra-listed German equity at EUR 50, settlement T+2 in EUR via Clearstream, with an FX hedge.

This is **not** a single DvP transaction; it is two sequential transactions:

```
At T (trade executes):
  Transaction(type=SETTLEMENT, settlement=T+2):
    Move(from: w_{CBF,S}, to: w_B, unit: ISIN_DE, quantity: 100)
    Move(from: w_B_EUR, to: w_{CBF,S_cash}, unit: EUR, quantity: 5000)

At T (FX hedge — separate transaction, separate settlement):
  Transaction(type=SETTLEMENT, settlement=T+2):
    Move(from: w_B_USD, to: w_FX_cpty, unit: USD, quantity: USD-equiv-of-5000-EUR)
    Move(from: w_FX_cpty, to: w_B_EUR, unit: EUR, quantity: 5000)
```

**The Herstatt risk is real and not eliminated** — the two transactions settle independently. v10.3 §2.6 paragraph 4 states this explicitly: "Herstatt risk is a real-world timing risk that no ledger design can eliminate, only represent and monitor."

**Mitigation in scope**: the CLS (Continuous Linked Settlement) mechanism provides PvP for major currency pairs. For CLS-eligible legs, the FX transaction's `external_ref` should carry the CLS settlement reference and the framework should track a CLS-settled status. For non-CLS legs, settlement-fail risk on the FX leg is a counterparty credit exposure that requires Pillar 3 disclosure (CRR Article 442).

**Standard reference**: IFRS 7.B11 (liquidity and credit risk disclosures); IFRS 9.5.5.17 (impairment for financial assets in foreign currency).

### 6.10 Recall during the open window

If the underlying shares were on loan (per §13 SBL) and are recalled during $[T, T+2]$ for a sale at $T$, the recall must complete before $T+2$ to deliver. The ledger represents this as:

```
At T (sale executes):
  -- Standard sell transaction; seller's own decreases
  -- BUT seller has no available inventory because shares are on loan

  -- Therefore at T-ε or T+0 (within the ledger's discipline):
  recall_trigger(loan_id) → SBL state machine: ACTIVE → RECALLED

At T+2 (deadline):
  IF recall settled in time:
    -- borrower returns shares to lender's onloan position
    -- lender's onloan -= Q, own unchanged
    -- shares now available for delivery to buyer
    -- standard settlement at T+2 proceeds

  ELSE (recall fail):
    -- the original sale fails per §6.4
    -- AND the loan goes into default per §13.SBL state machine (BUY_IN trigger)
```

This is a composition test: the deferred-settlement representation must compose with the SBL state machine without bespoke logic. The `own` coordinate is unchanged by the recall; only `onloan` and `borr` move. The settlement obligation on the original sale is independent.

---

## 7. Worked Example — 100 XYZ @ $50 → $52, PnL = +$200, no cash moved

### 7.1 Setup

- $T$ = day 0, 09:30:00 EST, NYSE
- Buyer: $w_B$ (real, US trader, USD reference currency)
- Seller: $w_S$ (real, market maker, virtualised as `w_{MM,virtual}`)
- Trade: BUY 100 XYZ at $50.00, settlement DTCC, T+1 (US post-May 2024 cycle — the example also works mutatis mutandis for T+2)
- Mark-to-market price at end of day $T$: $52.00

### 7.2 Move sequence

```
At T = 2026-04-30 09:30:00.000:
  Transaction(tx_id=42, type=SETTLEMENT, settlement_date=T+1):
    Move(from: w_{DTCC,S}, to: w_B, unit: XYZ, quantity: 100,
         timestamp: T, source: trade_42, metadata: "BUY_T_RECOGNITION")
    Move(from: w_B, to: w_{DTCC,S_cash}, unit: USD, quantity: 5000,
         timestamp: T, source: trade_42, metadata: "BUY_T_CASH_RECOGNITION")

  StatusUpdate(trade_42): EXECUTED

At T (later same day, EOD valuation):
  -- No moves. Pricing engine (v1.0 valuation companion FSM) updates P_T(XYZ) = 52.00.
  -- Position w_B(XYZ) = +100 (from the move at 09:30).
  -- Valuation: V_B(T, EOD) = 100 × 52 + cash position
  -- PnL since T_open: +$200 from the price move (52-50)*100
```

### 7.3 Position vector (using v10.3 §13 GPM notation; non-lendable test case so degenerates to scalar `own`)

| Wallet | `own(XYZ)` | `own(USD)` | Settlement status |
|---|---|---|---|
| $w_B$ at $T^+$ | $+100$ | unchanged | INSTRUCTED |
| $w_{DTCC,B}$ (CSD virtual) | $+100$ pending | $-5000$ pending | INSTRUCTED |
| $w_S$ at $T^+$ | $-100$ | unchanged | INSTRUCTED |
| $w_{DTCC,S}$ | $-100$ pending | $+5000$ pending | INSTRUCTED |

Conservation: $(+100) + (+100) + (-100) + (-100) = 0$ for XYZ. Cash: $0 + (-5000) + 0 + (+5000) = 0$. **Both conservation laws hold from $T^+$, before any cash has moved at the bank.**

### 7.4 PnL between $T_{open}$ and $T_{EOD}$

$$V_B(T_{EOD}) - V_B(T_{open}) = (\text{own}_B \cdot P_T)_{EOD} - (\text{own}_B \cdot P_T)_{open}$$

where $P_T$ uses the $T_{EOD}$ price = 52.00 and $\text{own}_B(XYZ) = 100$ at $T_{EOD}$.

$$\text{PnL}_{T_{EOD}} = 100 \cdot 52 - 100 \cdot 50 = +200$$

**This is the PnL on a position whose cash has not yet moved.** The cash leg of the trade only settles at $T+1^+$. But the economic exposure on the 100 shares — the $200 mark-to-market gain — is recognised at $T_{EOD}$, accurately, against `own` only.

The **cash payable** of $5,000 carried in `pending_out(w_{DTCC,B}, USD)` is unaffected by the price move. It is a fixed-amount short-dated obligation at notional, not an FVTPL item.

### 7.5 Audit assertion

If this trade were a sample item in a year-end FVTPL trading book test:

| Assertion | How verified |
|---|---|
| Existence | Move stream entry at $T$ + FIX confirmation + counterparty match |
| Completeness | Reconciliation of T-date positions to FX trade blotter |
| Valuation | $P_T(XYZ) = 52.00$ tied to a Level 1 market data source per IFRS 13.81 |
| Rights and obligations | DTCC contract note showing the trade | 
| Cut-off | Trade timestamp before cut-off; pre/post cut-off booking test |
| Presentation/disclosure | FVTPL classification per IFRS 9.4.1.4; settlement receivable separately disclosed under IFRS 7.20(c) if material |

**Materiality threshold**: assume this is an entity with materiality of $\pm$£25m. A single 100-share trade is immaterial individually. The auditor's interest is in the **population of unsettled trades at year-end**: e.g., on 31 December, the firm has open settlement legs aggregating to £4.2bn buy-side and £3.8bn sell-side. The net unsettled receivable of £400m **is material** and must be:

1. Separately disclosed (IFRS 7.6, Statement of Financial Position presentation under IAS 1.55);
2. Aged by counterparty and CCP (CRR Article 379 + COREP C 28.00 inputs);
3. ECL-assessed if IFRS 9 reporting (de minimis for CCP-cleared, material for bilateral or failed);
4. Tied to depot statements at $T+2$ (or $T+1$) post year-end, providing positive evidence for the trade-date recognition (subsequent events, IAS 10.9).

---

## 8. Accounting Policy Default — Trade-Date Mandatory

I take an explicit view: the framework should not support settlement-date accounting as a primary mode.

**Reasoning**:
1. The Ledger's atomic-transaction primitive embeds trade-date semantics. A settlement-date election would require either (a) deferring all moves until $T+2$, breaking economic recognition; or (b) maintaining two parallel move streams. Option (a) is unworkable for trading books. Option (b) violates the "single source of truth" design principle.
2. IFRS 9.B3.1.5 permits the choice but requires consistent application within each measurement category. Forcing this choice into the ledger would multiply the testing matrix.
3. US GAAP (ASC 320-10-25-3) effectively defaults to trade-date for trading securities and AFS, with settlement-date allowed only for held-to-maturity. The Ledger does not yet model HTM with the same primacy as trading book.
4. Regulatory capital (CRR, Basel III, FRTB) measures market risk on **trade-date positions**. A settlement-date ledger would produce inconsistent capital reports.
5. **Auditor preference**: trade-date accounting is the dominant practice for tier-1 banks; an auditor will challenge a settlement-date election on a trading book aggressively.

**Where settlement-date accounting genuinely matters**:
- Loan portfolio originations (HTC under IFRS 9, AC under US GAAP) — but these settle "T-date" anyway in the sense that drawdown = recognition.
- Some pension fund and insurance investment portfolios using legacy accounting — outside the trading-book scope of this framework.

**My recommendation**: hard-code trade-date recognition in the move primitive. Provide a downstream reporting projection that re-presents balances as "settled / unsettled" for any consumer requiring settlement-date views (regulator, statutory accounts of certain entity types, fund accounting).

---

## 9. Materiality and Disclosure Triggers

| Threshold | Required action |
|---|---|
| Aggregate unsettled receivable > 1% of balance sheet | Separately presented on face of balance sheet (IAS 1.55) |
| Unsettled receivable to single counterparty > 10% of CET1 | Large exposures reporting (CRR Article 392), Pillar 3 disclosure |
| Failed trade > $T+5$ days | CCR capital under CRR Article 379; report to risk committee |
| Failed trade > 7 trading days | CSDR Article 7 mandatory buy-in process triggered (when active) |
| ECL Stage 2 migration on settlement receivables exceeds 5% of gross | Disclosure under IFRS 7.35F |
| Manufactured dividend obligation unrecognised at year-end | Provision under IAS 37.14 if probable and reliably measurable |
| Cross-currency open exposure > Herstatt limit policy | Risk committee escalation; Pillar 3.5 narrative |

---

## 10. SOX / SOC 1 Control Evidence — What an Auditor Will Test

### 10.1 Key controls

1. **Trade capture completeness** (preventive): every executed trade enters the ledger within minutes of execution. Test: reconcile FIX message sequence numbers to ledger transactions; gap = control failure.
2. **Settlement instruction generation** (preventive): every committed `SETTLEMENT` transaction generates exactly one `sese.023`. Test: 1:1 matching of transaction IDs to outbound message IDs.
3. **Confirmation matching** (detective): every outbound `sese.023` matched to inbound `sese.025` within SLA (e.g., $T+2+1$ business day). Test: aged-unmatched report.
4. **Position reconciliation** (detective): daily three-way tie-out at $T+2^+$ between ledger `own`, ledger `pending_in/out` closure, and external CSD depot. Test: walkthrough of a SETTLED trade and a FAILED trade.
5. **Segregation of duties**: the trader who executes the trade cannot modify the settlement instruction. The settlement-ops team cannot modify the original move stream (event sourcing — corrections are new events, v10.3 §7.10).
6. **Exception management**: every break carries an owner, an SLA, and an escalation path. Test: aged break aging (>5 days = escalation to operations head; >15 days = CFO).

### 10.2 Information-produced-by-entity (IPE) testing

Under PCAOB AS 2110 and ISA 500, any report used as audit evidence must be tested for completeness and accuracy. The settlement-status report (the population of `INSTRUCTED`, `SETTLED`, `FAILED`, `PARTIAL_SETTLED` trades at year-end) will be tested by:

1. Reperformance: re-running the report from raw move stream and tying to the entity's official version.
2. Sample tie-out: 25-40 items traced from report → move stream entry → external confirmation.
3. Edge case: failed trades, cross-currency trades, partial settlements deliberately oversampled.

The framework's design — move stream as immutable source, status as a deterministic projection — makes this audit-friendly. The IPE evidence is **constructive** (re-derivable from primitives), not assertion-based.

---

## 11. BCBS 239 Implications

BCBS 239 Principles 3 (accuracy and integrity), 4 (completeness), 5 (timeliness), and 6 (adaptability) demand:

- **Lineage**: every settlement-related disclosure must be traceable to underlying moves, with the immutability of the lead-lag period preserved. The framework's append-only move stream + status updates as new events satisfies this.
- **Timeliness**: regulatory reporting (e.g., SFTR, EMIR Refit) reflects T-date positions. The framework's T-date economic recognition is structurally aligned with this.
- **Aggregation**: aggregations across legal entities, currencies, and CCPs must be reproducible. The framework's deterministic projections from the move stream (v10.3 §7.10) enable this.

The audit committee should require a **BCBS 239 self-assessment** specifically covering the deferred-settlement representation, with assertion-level controls mapped to each principle.

---

## 12. Summary — What the Framework Must Implement

| Item | Requirement | Rationale |
|---|---|---|
| Trade-date economic recognition | MANDATORY; embedded in move primitive | IFRS 9.B3.1.3, ASC 320-10-25-3, regulatory capital |
| Settlement-pending state | CSD/nostro virtual wallets, NOT a 7th GPM coordinate | Preserves StatesHome 3-map invariants; SCMP unchanged |
| Settlement status lifecycle | `EXECUTED → INSTRUCTED → {SETTLED, FAILED, PARTIAL_SETTLED}` as UnitStatus | Audit trail; reconciliation tractable |
| Settlement receivable measurement | At notional, not FVTPL | IFRS 9.5.1.3, short-term receivables |
| ECL on settlement receivables | Required (de minimis for CCP-cleared) | IFRS 9.5.5.5; CECL ASC 326-20-30-2 |
| Lead-lag reconciliation | Status-parameterised, not equality-based | Real-world cash and securities flows are asynchronous |
| External evidence chain | Move `external_ref` field links to FIX/sese/camt/depot | ISA 500, BCBS 239 Principle 6 |
| CSDR penalty representation | Daily accrual move from failing party | CSDR Article 7(2), Reg (EU) 2017/389 |
| Capital treatment of fails | Aged buckets per CRR Article 379 | COREP C 28.00 |
| Cross-currency / Herstatt | Two separate transactions, not one DvP | Real-world atomicity boundary |
| Cum-div trades | Manufactured dividend at $T+2$ if record_date ∈ $[T, T+2]$ | IAS 32.AG36, IFRS 9.B3.2.13 |
| Materiality thresholds | Aggregate unsettled disclosure trigger | IAS 1.55, IFRS 7.6 |

---

## 13. Open Questions for Phase 2 Adversarial Review

1. **Do we model `pending_in/out` as virtual-wallet entries or as a transaction-level metadata field?** I have proposed virtual wallets to maintain SCMP discipline; an alternative would be a `settlement_pending` flag on the transaction with no separate wallet rows. The tradeoff is reconciliation transparency vs. wallet sprawl.
2. **Should the settlement-status lifecycle be a `UnitStatus` field on the trade-as-unit, or a separate `TransactionStatus` map?** v10.3 §8.6 implies the former; the StatesHome ruling does not have an explicit precedent for transaction-as-unit.
3. **CSDR penalty: who issues it?** The CSD reports it; the framework needs an oracle leaf ($L_{12}$ in the data layer's external-confirmations leaf). I have not specified the oracle integration.
4. **For T+0 (atomic on-chain DvP, e.g., HQLAx, Onyx Coin Systems) the framework should degenerate to a single transaction at $T$ with no virtual-wallet contras**. Verify this composes.
5. **Repurchase agreements (repo)** — open leg / close leg with similar deferred-settlement gap on each leg. Out of scope for cash equities but the design should accommodate it.
6. **Tokenised equities** (v10.3 §10.7-ish; NVDA worked example) — atomic on-chain DvP changes the gap to seconds, not days. Does the framework retain the same primitives or short-circuit them?
7. **IFRS 9 vs. CECL divergence on the ECL accrual**: should the framework emit ECL moves under both bases simultaneously (dual reporting) or pick one and project the other? My recommendation: emit IFRS 9 ECL primary, project CECL as an alternative measure (IFRS 9 is more granular).

---

## Sign-off

This proposal:
- Defaults to trade-date accounting, as required by IFRS 9 and US GAAP for regular-way trades on trading-book equities.
- Represents the open obligation as recognised, on-balance-sheet, and reconcilable.
- Composes with the GPM short-sale, recall, corporate-action, and Herstatt cases without bespoke logic.
- Generates the audit evidence chain external auditors will demand for existence, completeness, valuation, cut-off, and presentation assertions.
- Aligns with CRR/Basel capital treatment, CSDR penalty, and BCBS 239 lineage requirements.
- Is implementation-ready: move-block templates, status machine, reconciliation logic, ECL hooks, and CDM cross-walk are all specified.

I have flagged the 7 open questions above for Phase 2 adversarial review. None of them invalidates the core design.

— Reginald Ashworth, FCA, Senior Partner Banking Assurance
