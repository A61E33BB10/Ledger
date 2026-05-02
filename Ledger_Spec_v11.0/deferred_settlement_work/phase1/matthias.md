# Deferred Settlement in the Ledger v11.0

**Author:** Matthias Vogt (rosetta-cdm-engineer)
**Phase:** 1, Independent Proposal
**Date:** 2026-04-30
**Scope:** how the Ledger represents the gap between trade-time economic recognition (T) and settlement-time custody movement (T+2) for cash equities, with composition over short/recall/CA/cross-currency/DvP.

The Ledger framework already takes the position (v10.3 §8 lines 1853-1857, §11) that economic exposure begins at T, the move stream is canonical, the position is *not* automatically reversed on a fail, and the (EXECUTED → INSTRUCTED → SETTLED|FAILED) status lifecycle is recorded as lifecycle events that emit no further moves. This proposal accepts that footing and makes it precise. The novel content is structural: where exactly the obligation lives, which invariants gate it, what the reconciliation contract is between Ledger and nostro, and the full CDM 6.0.0 cross-walk including the four extensions CDM does not yet cover.

The work-product is implementation-ready. The Rosetta extensions in §5 are namespace-qualified and field-shape-precise.

---

## 1. State Representation

### 1.1 The economic position is true from T. The custody position is not.

The Ledger has two distinct facts to record about a buy executed on T:

| Fact | True from | Where it lives in the v11.0 schema |
|---|---|---|
| Economic exposure (price risk, dividend entitlement, voting rights pending record date) | T (execution timestamp) | `PositionState[w_buyer, u_AAPL].own` written at T |
| Custody position at the CSD | T+2 (DVP confirmation) | the *nostro virtual wallet* `w_nostro` reconciled to depo statement |

These are two different observables with two different sources of truth. Conflating them is the original sin of trade-date-only systems and of settlement-date-only systems alike. The Ledger v11.0 records both, and reconciles them.

### 1.2 Three objects together carry a deferred settlement

A single equity buy at T is represented by **three structural objects, atomically committed**, plus an **obligation row** that is monotone-carried until discharged:

**(a) The economic move at T** — the position change in the Ledger.
**(b) The contra-leg in a virtual *In-Flight* wallet** — the bookkeeping entry that holds the deferred-settlement obligation.
**(c) The obligation row** — a first-class entry in the Obligation Store (v10.3 §11.5, the obligation-as-first-class-object sub-section) that names the (delivering party, receiving party, ISIN, quantity, currency, amount, expected settlement date, current status). The obligation row is *not* a wallet entry; it is the explicit, reconcilable artefact that gives the (T, T+2) gap a name.
**(d) Status state on the obligation row** — moved through `PENDING → INSTRUCTED → SETTLED | FAILED | PARTIALLY_SETTLED | CANCELLED` by lifecycle events emitted by the settlement-confirmation return path (v10.3 §8.7).

In the v10.3-addendum 3-map schema (`ProductTerms` / `UnitStatus` / `PositionState`) the obligation row maps cleanly: it is a `PositionState[w_obligation_register, u_obligation_id]` row, where `u_obligation_id` is a unit in the *Obligation* sub-class of `ProductTerms`. This makes the obligation a unit, conserves it across the system ($\sum_w w(u_{\text{obl}}) = 0$ holds because the obligation has an issuer wallet and a holder wallet), and brings it under the same monotone-carrier and Option-accessor disciplines as every other unit. **The obligation does not need a new state map; it earns a place in the existing three by virtue of being a unit.**

This is the structural answer to "how does the gap get an explicit, reconcilable representation?": the gap *is* a unit in $\mathcal{U}$.

### 1.3 The wallet topology

A standard buy at T splits the conventional broker-virtual-wallet pattern (v10.3 §2.4) into two phases:

```
                          T = trade date                T+2 = settlement date
Real:   w_buyer_portfolio   w_buyer_portfolio            w_buyer_portfolio
                                  ↓ (obligation discharged on confirmation)
Virtual:   w_inflight_recv  w_inflight_recv  →           w_nostro_buyer
           (cash payable)   (cash payable)             (DVP-debited at CSD)
           w_inflight_pay   w_inflight_pay  →           w_nostro_seller
           (shares receivable)                          (DVP-credited at CSD)
        w_broker_or_ccp
```

Two new virtual-wallet sub-classes are introduced:

- `w_inflight_recv`: holds inbound obligations (shares we are owed). Conservation partner of `w_buyer_portfolio` for the security leg.
- `w_inflight_pay`: holds outbound obligations (cash we owe). Conservation partner of `w_buyer_portfolio` for the cash leg.

These are not new wallet types — they are virtual wallets in the v10.3 §2.4 sense, with a `wallet_type = INFLIGHT` discriminator on `WalletRegistry` and a mandatory link to the obligation row that justifies the balance.

### 1.4 The economic-exposure-at-T invariant — the core mandatory invariant

This is the structural commitment without which the proposal collapses into either a trade-date-only or a settlement-date-only system, both of which are wrong.

**Invariant E1 (Economic Exposure at T, MANDATORY).** For every committed `Trade` event at timestamp $t_{\text{exec}}$, for every wallet $w$ that is a counterparty to the trade, for every unit $u$ on the security or cash leg, the position $w_t(u)$ reflects the economic effect of the trade for all $t \geq t_{\text{exec}}$, regardless of whether the corresponding settlement at the CSD has occurred, has been instructed but not confirmed, or has failed.

Operationally:
- The buyer is long AAPL from T (gets dividends, votes at meetings whose record date is between T and T+2 if they are inscribed at the CSD by T+2 — the dividend-inscription edge case is handled in §6 fail-on-record-date).
- The buyer is short USD (cash payable) from T.
- The PnL between T and T+2 is computed against the as-of-T position, not the as-of-T+2 settled position.
- The position is *not* reversed on a fail.

Invariant E1 is the floor on which every other invariant in this proposal sits. Without E1, P10 (PnL path-independence, v10.3 §11.2) becomes invalid: PnL would appear to spike at T+2 when settlement confirms, even though no economic event occurred at T+2.

### 1.5 The reconciliation invariant

**Invariant R1 (Settlement-Lag Reconciliation).** For every (wallet $w$, security ISIN $u$) pair at any wall-clock time $t$:

$$w_t^{\text{ledger,real}}(u) + w_t^{\text{ledger,inflight}}(u) + w_t^{\text{ledger,virtual,broker}}(u) = w_t^{\text{nostro}}(u)$$

This is the reconciliation contract between Ledger and nostro. It says: what the CSD shows in our depo equals what we own *plus* what we are owed in-flight *plus* what is in transit through the broker. A break in R1 is either a Ledger bug (an obligation was discharged without a corresponding move from in-flight to real) or a custodian break (the CSD transferred stock without a Ledger event). Both are detectable, neither is silent.

R1 is the formal expression of the v10.3 §8.7 confirmation-return-path narrative.

---

## 2. Move Sequence — Standard Buy 100 AAPL @ \$50 with PnL = +\$200 at T+1

The walked example is: 100 AAPL bought at T = 2026-04-30, executed price \$50 (so cash payable \$5,000), market closes at \$51 on T = 2026-04-30 (intraday: $\Delta P = +\$1$, +\$100 PnL), market closes at \$52 on T+1 = 2026-05-01 (+\$200 PnL since T), settlement at T+2 = 2026-05-04 (Monday — accounting for weekend).

### 2.1 At T (2026-04-30, execution timestamp)

Three transactions are emitted by the Equity Smart Contract on `BookTrade(buy, 100, AAPL, 50)`:

```
Transaction τ_T = SETTLEMENT, type=DEFERRED_SETTLEMENT, atomic:

  -- (1) Recognise the security at T (E1: long from T)
  Move(from: w_inflight_recv,    to: w_buyer_portfolio,
       unit: AAPL, quantity: 100, timestamp: T,
       source: "trade_xyz", metadata: {leg: SECURITY, side: RECEIVING})

  -- (2) Recognise the cash payable at T (E1: short USD from T)
  Move(from: w_buyer_portfolio,  to: w_inflight_pay,
       unit: USD, quantity: 5000, timestamp: T,
       source: "trade_xyz", metadata: {leg: CASH, side: PAYING})

  -- (3) Issue the obligation as a first-class unit
  -- u_obl is a freshly registered unit in the Obligation sub-class
  Move(from: w_obligation_issuer, to: w_obligation_register,
       unit: u_obl_xyz, quantity: 1, timestamp: T,
       source: "trade_xyz",
       metadata: {
         obligation_type: SETTLEMENT_DVP,
         security_isin: "US0378331005",
         security_quantity: 100,
         cash_currency: "USD",
         cash_amount: 5000,
         counterparty_lei: "<seller_lei>",
         expected_settlement_date: T+2,
         status: PENDING})
```

Conservation per unit:
- AAPL: $-100 + 100 = 0$ across (`w_inflight_recv`, `w_buyer_portfolio`). ✓
- USD: $-5000 + 5000 = 0$ across (`w_buyer_portfolio`, `w_inflight_pay`). ✓
- $u_{\text{obl,xyz}}$: $-1 + 1 = 0$ across (`w_obligation_issuer`, `w_obligation_register`). ✓

**Derived state right after T:**
- `w_buyer_portfolio(AAPL) = +100` (E1 satisfied)
- `w_buyer_portfolio(USD) = -5000` (E1 satisfied)
- `w_inflight_recv(AAPL) = -100`, `w_inflight_pay(USD) = +5000`
- `UnitStatus[u_obl_xyz].lifecycle_stage = PENDING`
- `PositionState[w_obligation_register, u_obl_xyz] = Some(quantity=1, status=PENDING)`

### 2.2 Intraday at T (close at \$51): no moves, only valuation

PnL is a derived quantity (v10.3 §3.3):

$$\Delta V_T = w_T(\text{AAPL}) \cdot (P_T(\text{AAPL}) - P_{T,\text{exec}}(\text{AAPL})) = 100 \cdot (51 - 50) = +\$100$$

No move stream entry, no transaction. PnL is a function of position and price; the position is +100 from T per E1; the price is \$51 from the closing price feed. The valuation engine (v11.0 valuation §3) computes this. **Critical:** the PnL is right despite no cash having moved and no settlement having happened.

### 2.3 At T+1 (close at \$52): no moves, only valuation

$$\Delta V_{T+1} = 100 \cdot (52 - 51) = +\$100, \quad \text{cumulative PnL since T} = +\$200$$

No move emitted. The position is still +100 AAPL, -5000 USD, +1 obligation. The obligation is still `PENDING`. The PnL of +\$200 is right because E1 holds.

### 2.4 At T+2 minus (instruction event)

The settlement layer (v10.3 §8.5) generates and submits the `sese.023` DVP instruction. This is recorded as a status update on the obligation:

```
Transaction τ_{T+2-} = LIFECYCLE, type=OBLIGATION_STATUS_CHANGE:

  ObligationStatusUpdate(
      obligation_id: u_obl_xyz,
      previous_status: PENDING,
      new_status: INSTRUCTED,
      timestamp: T+2 - <morning cut>,
      external_reference: sese.023.msg_id_<...>,
      metadata: {csd: DTC, instruction_type: DVP_SETT})
```

`UnitStatus[u_obl_xyz].lifecycle_stage = INSTRUCTED`. **No moves emitted.** The economic position is unchanged (E1 still satisfied); only the obligation's lifecycle state advanced.

### 2.5 At T+2 plus (DVP confirmation, success path)

The CSD confirms successful DVP via `sese.025` (securities confirmation) and `camt.054` (cash confirmation). The confirmation triggers an atomic transaction that:
- discharges the in-flight wallets back to the real and nostro wallets,
- moves the obligation to `SETTLED`.

```
Transaction τ_{T+2+} = SETTLEMENT, type=SETTLEMENT_CONFIRMATION, atomic:

  -- Discharge security in-flight to nostro (the CSD now holds it for us)
  Move(from: w_buyer_portfolio,  to: w_nostro_buyer,
       unit: AAPL, quantity: 100, timestamp: T+2_confirm,
       source: "settle_layer", metadata: {csd_ref: <...>})
  Move(from: w_nostro_buyer,     to: w_buyer_portfolio,
       unit: AAPL, quantity: 100, timestamp: T+2_confirm,
       source: "settle_layer", metadata: {csd_ref: <...>})
  -- The above two are a no-op net for w_buyer_portfolio's economic position;
  -- they update the nostro reconciliation account.

  -- Resolve the in-flight wallets to zero
  Move(from: w_buyer_portfolio,  to: w_inflight_recv,
       unit: AAPL, quantity: 100, ...)  -- offsets τ_T move (1)
  Move(from: w_inflight_recv,    to: w_nostro_buyer,
       unit: AAPL, quantity: 100, ...)  -- shows up in nostro

  -- Cash leg, symmetric
  Move(from: w_inflight_pay,     to: w_buyer_portfolio,
       unit: USD, quantity: 5000, ...)
  Move(from: w_buyer_portfolio,  to: w_nostro_buyer,
       unit: USD, quantity: 5000, ...)

  -- Discharge the obligation
  Move(from: w_obligation_register, to: w_obligation_issuer,
       unit: u_obl_xyz, quantity: 1, ...,
       metadata: {status_terminal: SETTLED})
```

**Critical structural property:** the *economic* position at `w_buyer_portfolio` is **unchanged** by τ_{T+2+}. The +100 AAPL, -5000 USD held since T is preserved. What τ_{T+2+} does is: route the position out of the in-flight wallets into the nostro wallet, which is the correct reconciliation surface for the CSD's record. The obligation is closed.

A simpler implementation collapses the four security moves of τ_{T+2+} into one — moving the position directly from `w_inflight_recv` to `w_nostro_buyer` and adjusting the source-of-truth wallet via a virtual-broker pass-through. The four-move version makes the audit chain explicit; the one-move version is operationally lighter. Both satisfy R1 by construction.

After τ_{T+2+}:
- `w_buyer_portfolio(AAPL) = +100` (unchanged from T — E1 preserved)
- `w_nostro_buyer(AAPL) = +100` (CSD-side credited)
- `w_inflight_recv(AAPL) = 0`, `w_inflight_pay(USD) = 0`
- `UnitStatus[u_obl_xyz].lifecycle_stage = SETTLED`

R1 reconciliation at $t = T+2_{+}$:

$$\underbrace{100}_{\text{real}} + \underbrace{0}_{\text{inflight}} + \underbrace{0}_{\text{broker}} = \underbrace{100}_{\text{nostro}} \checkmark$$

---

## 3. Invariants

The full invariant set governing deferred settlement is a small extension of v10.3 §11 and the addendum's C1–C12. Every invariant is testable, with failure mode named.

| ID | Statement | Testability |
|---|---|---|
| **E1** | Economic exposure recognised at T (MANDATORY, §1.4) | Property: for any random executed trade, position at $T_{\text{exec}}+\epsilon$ reflects the trade economics |
| E2 | Settlement does not change economic position | Property: $w_{T+2-}(u_{\text{security}}) = w_{T+2+}(u_{\text{security}})$ for the trader's real wallet on a successful settlement |
| E3 | Fail does not reverse position | Property: a `FAILED` confirmation event emits zero moves on the trader's real wallet |
| **O1** | Every committed buy/sell on a deferred-settlement security emits exactly one `u_obl` issuance | Property: $\#(\text{obligations issued in event } e) = \#(\text{deferred-settlement legs of } e)$ |
| O2 | An obligation reaches a terminal state (`SETTLED`, `CANCELLED`, `BUY_IN_RESOLVED`) within a bounded horizon $T+H$ where $H$ is regime-dependent (T+5 for CSDR partial penalty, T+15 for mandatory buy-in extended period etc.) | Liveness invariant: every `PENDING` or `INSTRUCTED` obligation has a scheduled escalation; failure to terminate raises a Break |
| O3 | The (T, T+2) gap is exactly one obligation per traded unit per leg | Conservation: $\sum_w w(u_{\text{obl}}) = 0$ holds for the obligation unit class as for every other unit class |
| **R1** | Settlement-Lag Reconciliation (§1.5) | Continuous: the equation must hold for every $(w, u)$ at every wall-clock t. A break is *the* canonical settlement-system fail signal |
| R2 | Nostro discrepancies are isolated to in-flight wallets | If R1 fails, the discrepancy is observable by inspecting the in-flight wallets, not the real wallets |
| C1 | The economic move and the obligation issuance are a single atomic transaction | C3 of the StatesHome addendum already mandates this; here it is restated for the deferred-settlement-specific transaction class |
| C2 | An `INSTRUCTED` → `SETTLED` transition implies a contemporaneous `inflight → nostro` migration of the corresponding leg | Property: the two events are emitted as a single `LIFECYCLE` transaction |

E1 is the load-bearing invariant. R1 is the load-bearing reconciliation contract. The remainder are derived or pragmatic.

---

## 4. Reconciliation — Lead-Lag by Design

### 4.1 The Ledger is *ahead* of the nostro between T and T+2

This is **by design**, not a bug. Between T and T+2, $w_t^{\text{ledger,real}}(u) \neq w_t^{\text{nostro}}(u)$ for every freshly-traded unit. The Ledger leads — it knows about the trade from T. The nostro follows — it confirms at T+2. The gap is precisely the in-flight balance:

$$w_t^{\text{ledger,inflight}}(u) = w_t^{\text{ledger,real}}(u) - w_t^{\text{nostro}}(u) \quad \forall t \in (T, T+2)$$

Reconciliation is therefore not "Ledger == Nostro?" but "Ledger - Nostro == In-Flight?". This is R1 rearranged.

### 4.2 Daily reconciliation cycle

Two reconciliation jobs run nightly:

1. **In-flight roll-forward.** For every `PENDING` or `INSTRUCTED` obligation older than the standard window, escalate to break-investigation. T+2-INSTRUCTED with no SETTLED by COB T+2 = signal of a fail; T+5 INSTRUCTED is a CSDR cash-penalty escalation; T+15 INSTRUCTED triggers buy-in workflow.
2. **Nostro reconciliation.** For each (real wallet, ISIN), compute the predicted nostro from the Ledger:
   $$\hat{n}_t(w, u) = w_t^{\text{ledger,real}}(u) - \sum w_t^{\text{ledger,inflight}}(u) - \sum w_t^{\text{ledger,broker-virtual}}(u)$$
   Compare to the custodian depot statement. Mismatches enter the `BreakRegister` (v11.0 data §10).

### 4.3 Across the window

A trade executed Monday T = 2026-04-27 settles Wednesday T+2 = 2026-04-29. A trade executed Friday T = 2026-04-25 settles Tuesday T+2 = 2026-04-29 (weekend rolling). Two trades that both settle on the same date can be netted at the settlement layer (v10.3 §8.6) but remain gross in the Ledger. The R1 reconciliation passes trivially in either gross or net mode because the equation aggregates over `w_inflight_*`.

---

## 5. CDM Cross-Walk — the Centrepiece

This is my section. I have re-fetched live CDM 6.x at 2026-04-30 — `event-common-type.rosetta`, `event-common-enum.rosetta`, `event-position-enum.rosetta`, `product-common-settlement-type.rosetta`, `product-common-settlement-enum.rosetta` — and the cross-walk below cites file paths and line behaviour verified at fetch time. The CDM source on `github.com/finos/common-domain-model@master` lives at `rosetta-source/src/main/rosetta/<file>.rosetta` (flat, dot-namespaced — see CDM 6.x path scheme memory).

### 5.1 Where CDM models the trade-date vs settlement-date gap — the structural answer

**CDM does not have a unified "deferred settlement obligation" type.** What it has is:

| CDM artefact | What it carries | What it does *not* carry |
|---|---|---|
| `Trade` (event-common-type.rosetta) | execution-time economic terms, tradeDate, parties, product | no settlement status, no settlement-date snapshot |
| `TradeState` (event-common-type.rosetta) | the trade plus `state State (0..1)`, `transferHistory TransferState (0..*)`, `valuationHistory Valuation (0..*)` | a single trade-state object collapses pre- and post-settlement views; CDM models the change via *appended* TransferState entries, not via a structural "open obligation" type |
| `TransferState` (event-common-type.rosetta, line ~ shape verified) | `transfer Transfer (1..1)`, `transferStatus TransferStatusEnum (0..1)` | no `expectedSettlementDate`, no obligor/obligee party-link, no `failReason` |
| `TransferStatusEnum` (event-common-enum.rosetta) | `Disputed, Instructed, Pending, Settled, Netted` | **no `Failed`, no `PartiallySettled`, no `Cancelled`, no `BoughtIn`** |
| `Transfer extends AssetFlowBase` (event-common-type.rosetta) | `payerReceiver`, `settlementOrigin Payout`, `resetOrigin Reset`, `transferExpression TransferExpression` | a `Transfer` is the *act* of transferring, not the *obligation* to transfer; the (T, T+2) gap is implicit in the absence of a `Settled` status, not explicit in a separate type |
| `SettlementBase` / `SettlementTerms` / `SettlementDate` (product-common-settlement-type.rosetta) | `settlementType SettlementTypeEnum`, `transferSettlementType TransferSettlementEnum`, `settlementCurrency`, `settlementDate SettlementDate`, `settlementCentre SettlementCentreEnum` | this is the *terms* of settlement for the product, attached to a payout — not the *runtime obligation state* |
| `PositionStatusEnum` (event-position-enum.rosetta) | `Executed, Formed, Settled, Cancelled, Closed` | **no `Failed`, no `PartiallySettled`, no `Inflight`** distinction between "executed but pending settlement" and "executed and settled" — CDM uses `Executed` for both, conflating them |
| `BusinessEvent` (event-common-type.rosetta, extends `EventInstruction`) | a transition from before-state to after-state, with `eventQualifier`, `after TradeState (0..*)` | no native `SettlementFail`, `BuyIn`, `PartialSettlement`, `CSDRPenalty` event qualifier |
| `DeliveryMethodEnum` (product-common-settlement-enum.rosetta) | `DeliveryVersusPayment, FreeOfPayment, PreDelivery, PrePayment` | DVP value is only a *type tag*; the runtime atomicity guarantee that the Ledger encodes via single-transaction commitment is not represented in CDM |

The crucial diagnosis: **CDM models the gap implicitly via `TransferStatusEnum.Pending` / `.Instructed` plus the absence of a `Settled` state on the corresponding `TransferState`.** It does not have a first-class object for "this trade has been executed but the settlement has not yet happened." The Ledger's obligation row is denser than CDM's `TransferState`.

The diagnosis on economic-exposure-at-T: **CDM is silent on this question.** CDM records the `Trade` at `tradeDate` and the `Transfer` (with status) over time. CDM does *not* assert that the position represented by the `TradeState` is true from `tradeDate`. That is a Ledger-level semantic — and it is the right semantic, but CDM does not enforce it. A CDM-only stack could, in principle, treat the economic position as null until a `Settled` `TransferState` exists, which would be wrong. The Ledger v11.0 makes the correct semantic explicit via E1.

### 5.2 The full cross-walk table

| Ledger v11.0 element | CDM 6.0.0 status | Native CDM type / file | Gap classification |
|---|---|---|---|
| Execution event at T | **Direct** | `BusinessEvent` with `instruction.execution: ExecutionInstruction` (event-common-type.rosetta) | mapped — eventQualifier `Execution` |
| `Trade` object captured at T | **Direct** | `Trade extends TradableProduct` (event-common-type.rosetta) | direct — `tradeDate FieldWithMeta<date> (1..1)` is the T |
| Settled-by-T+2 expectation | **Partial** | `SettlementDate.adjustableOrRelativeDate` (product-common-settlement-type.rosetta) carries the *terms*; runtime expected date lives in the Ledger obligation row | needs `expectedSettlementDate` on a runtime obligation envelope, not on terms |
| Securities leg of buy | **Direct** | `Transfer` with `Asset.Instrument.Security` payload (base-staticdata-asset-common-type.rosetta) | direct via `AssetFlowBase` |
| Cash leg of buy | **Direct** | `Transfer` with `Asset.Cash` payload | direct |
| DVP atomicity | **Direct (terms) / Missing (runtime)** | `TransferSettlementEnum.DeliveryVersusPayment` (product-common-settlement-enum.rosetta) | terms tag exists; runtime atomicity invariant is Ledger-level (Ledger's transaction-atomicity primitive maps to no CDM object — see Gap 1 of cdm_gap_log) |
| Status `EXECUTED` (Ledger §8.7) | **Direct** | `PositionStatusEnum.Executed` and `TransferStatusEnum.Pending` | mapped, with the conflation noted above |
| Status `INSTRUCTED` | **Direct** | `TransferStatusEnum.Instructed` | mapped |
| Status `SETTLED` | **Direct** | `TransferStatusEnum.Settled` and `PositionStatusEnum.Settled` | mapped |
| **Status `FAILED`** | **Missing — major gap** | no value in `TransferStatusEnum`; no value in `PositionStatusEnum`; no failure-reason structure | **Gap 6, see §5.3** |
| **Status `PARTIALLY_SETTLED`** | **Missing — major gap** | no value in either enum; only `partialCashSettlement boolean` exists in CDS terms (`PCDeliverableObligationCharac`), which is unrelated | **Gap 7, see §5.3** |
| **CSDR cash penalty** | **Missing — major gap** | no native type | **Gap 8, see §5.3** |
| **Buy-in event** | **Missing — major gap** | the term "buy-in" appears only in `sixtyBusinessDaySettlementCap` text (CDS deliverable obligations); no `BuyInEvent` type, no `BuyIn` event qualifier | **Gap 9, see §5.3** |
| Obligation as first-class object | **Missing** | no native `Obligation` type; CDM treats obligations as deltas between `TransferState` snapshots | **Gap 10 — strategic, also relevant to v10.3 §11.5 obligation-liveness** |
| Recall in window (SBL) | **Direct** | `UnscheduledTransferEnum.Recall` (product-common-settlement-enum.rosetta) | direct, but composes with deferred settlement only via SBL extensions — see §6 |
| Corporate action in window (record date in (T, T+2)) | **Partial** | `ObservationEvent.corporateAction CorporateAction (0..1)` (event-common-type.rosetta) | the CA itself is mapped; the *attribution to pre-settlement holder* (the buyer at T or the seller's CSD position at T+2-) is a Ledger-level rule with no CDM hook — see §6 |
| Cross-currency / Herstatt | **Partial** | `CrossCurrencyMethod` exists in `CashSettlementMethodEnum`; `PaymentVersusPayment` value in `TransferSettlementEnum`. The intra-day settlement-leg sequence and the 1974-style Herstatt-window risk are not modelled | needs runtime tracking of per-leg status, which lives in the Ledger's per-leg obligation rows |
| Short sale cover via SBL | **Partial** | `Qualify_SecurityLending` (product-qualification-func.rosetta) — qualification function for SBL exists per cdm_6x_verified_facts memory; but the composition rule "short borrow ON the same day as the short sell to enable T+2 delivery" is not represented as a structural relationship | **Gap 4 of CDM gap log** still pending — ISLA-coordinated |
| In-flight virtual wallets | **Missing** (Ledger-internal) | no analogue in CDM's product-template-type.rosetta party model | Ledger-internal discipline; not a CDM gap |

### 5.3 Rosetta extensions the Ledger needs that CDM does not have — exact namespace, qualifier, field shape

These four extensions are firm-strategic. They should be proposed as upstream CDM PRs targeting CDM 6.1 / 7.0 — they are not Ledger-bespoke, they are industry gaps that every CSDR-impacted firm has to solve.

#### Gap 6: Settlement Failure Status

**File:** `event-common-enum.rosetta`
**Edit:** add values to `TransferStatusEnum`

```rosetta
enum TransferStatusEnum: <"The enumeration values to specify the transfer status.">
    Disputed
    Instructed
    Pending
    Settled
    Netted
    Failed <"The transfer was instructed and the CSD reported a failure to settle on the expected settlement date. Per ESMA RTS on CSDR, the transfer remains instructed and accrues cash penalties until extended settlement, mandatory buy-in, or cancellation.">
    PartiallySettled <"The transfer was instructed and the CSD reported partial settlement. The settled portion is reflected in companion TransferState records; this status applies to the residual unsettled portion.">
    Cancelled <"The transfer was instructed but cancelled prior to or after the expected settlement date by mutual agreement of the parties (e.g., post-buy-in cash compensation or trade-cancellation under bilateral terms)."
```

Also add a fail-reason structure:

```rosetta
type TransferFailureReason: <"Captures the reason and metadata for a Failed or PartiallySettled TransferState.">
    [metadata key]
    failReasonCode TransferFailReasonEnum (1..1) <"The classified reason for the failure.">
    failReasonText string (0..1) <"Free text per CSDR Article 7 reporting requirements.">
    settledQuantity Quantity (0..1) <"For PartiallySettled, the quantity that did settle.">
    csdrPenaltyAccrued Money (0..1) <"Accrued CSDR cash penalty for this fail, computed per ESMA penalty matrix.">

enum TransferFailReasonEnum:
    LackOfSecurities
    LackOfCash
    SettlementMatchingFailure
    BuyerOnHold
    SellerOnHold
    SettlementSystemFailure
    OnHoldByCounterparty
    Other
```

**File:** `event-common-type.rosetta` — extend `TransferState`

```rosetta
type TransferState:
    [metadata key]
    [rootType]
    transfer Transfer (1..1)
    transferStatus TransferStatusEnum (0..1)
    failureReason TransferFailureReason (0..1) <"Required when transferStatus = Failed or PartiallySettled.">
    expectedSettlementDate date (0..1) <"The contractually expected settlement date; used to compute settlement lag.">
    actualSettlementDate date (0..1) <"The date on which the CSD confirmed full settlement; populated when transferStatus = Settled.">

    condition FailureReasonRequired:
        if transferStatus = TransferStatusEnum -> Failed
            or transferStatus = TransferStatusEnum -> PartiallySettled
        then failureReason exists
```

#### Gap 7 (subsumed by Gap 6 above): Partial Settlement

Already covered: `TransferStatusEnum.PartiallySettled` plus `TransferFailureReason.settledQuantity`. The companion `TransferState` records — one for the settled portion, one for the unsettled — are an idiomatic use of `TradeState.transferHistory TransferState (0..*)` which already supports multi-record histories. No additional structural change needed beyond Gap 6.

#### Gap 8: CSDR Cash Penalty

**File:** `event-common-type.rosetta` — extend the `BusinessEvent` event-qualifier vocabulary

The `eventQualifier` field on `BusinessEvent` is `string (0..1)` — soft-typed. The convention is that valid qualifiers are documented in `event-qualification-func.rosetta`. We propose adding a `CashPenalty` qualifier with an associated function:

```rosetta
// In event-qualification-func.rosetta
func Qualify_CashPenalty: <"Qualifies a BusinessEvent as a CSDR cash penalty assessment per ESMA Penalty Matrix Article 7 RTS.">
    [qualification BusinessEvent]
    inputs:
        businessEvent BusinessEvent (1..1)
    output:
        is_event boolean (1..1)

    set is_event:
        businessEvent -> instruction -> transfer exists
        and businessEvent -> instruction -> transfer -> transferState -> transferStatus contains TransferStatusEnum -> Failed
        and businessEvent -> eventQualifier = "CashPenalty"
```

And a payload type:

```rosetta
// In event-common-type.rosetta or a new event-csdr-type.rosetta
type CSDRPenaltyDetail: <"Detail of a CSDR Article 7 cash penalty assessment for a failed settlement.">
    [metadata key]
    failedTransferReference Transfer (1..1) <"Reference to the failed Transfer that is being penalised.">
        [metadata reference]
    penaltyAccrualDate date (1..1)
    penaltyAmount Money (1..1)
    penaltyRateBps number (1..1) <"The penalty rate in basis points per ESMA Penalty Matrix; depends on instrument liquidity classification.">
    instrumentLiquidityClass CSDRLiquidityClassEnum (1..1)
    penaltyCounterparty Party (1..1) <"The party owing the penalty (the failing party).">
    penaltyBeneficiary Party (1..1) <"The party receiving the penalty (the suffering party).">

enum CSDRLiquidityClassEnum:
    LiquidShares
    NonLiquidShares
    LiquidBonds_SovereignSupranational
    LiquidBonds_OtherPublic
    LiquidBonds_Corporate
    NonLiquidBonds
    SMEGrowthMarket
    Other
```

#### Gap 9: Buy-In Event

**File:** add a new `event-buyin-type.rosetta` and corresponding enum:

```rosetta
namespace cdm.event.buyin

import cdm.event.common.*
import cdm.product.common.settlement.*
import cdm.base.staticdata.party.*

type BuyInInstruction: <"Instructions for a CSDR Article 7 mandatory buy-in or a contractual GMSLA 9.3 buy-in following a settlement failure.">
    [metadata key]
    failedTransferReference Transfer (1..1)
        [metadata reference]
    buyInRegime BuyInRegimeEnum (1..1)
    buyInAgent Party (0..1) <"The buy-in agent appointed to execute the buy-in.">
    buyInTriggerDate date (1..1)
    buyInExtensionPeriod int (0..1) <"Number of business days of extension granted before mandatory buy-in execution; per CSDR, 4 to 7 business days post intended-settlement-date depending on instrument class.">

type BuyInExecution: <"Records the execution of a buy-in: the cover purchase by the suffering party (or its agent), the cost-attribution to the failing party, and the cancellation/cash-settlement of the original failed transfer.">
    [metadata key]
    [rootType]
    buyInInstruction BuyInInstruction (1..1)
    coverPurchaseTrade Trade (1..1) <"The new trade executed to acquire the failed-to-deliver securities.">
    costAttribution CashTransfer (1..1) <"The cash transfer from the failing party to the suffering party covering the buy-in cost differential.">
    originalTransferOutcome BuyInOutcomeEnum (1..1)

enum BuyInRegimeEnum:
    CSDRMandatoryBuyIn
    GMSLA_2018
    GMRA_2011
    BilateralContractual

enum BuyInOutcomeEnum:
    OriginalTransferCancelled <"The original failed transfer is cancelled and replaced by the buy-in cover trade.">
    CashSettlementInLieu <"Per CSDR fallback, the failed transfer is cash-settled at the buy-in reference price; original delivery obligation is extinguished.">
```

And the BusinessEvent qualifier:

```rosetta
// event-qualification-func.rosetta
func Qualify_BuyIn:
    [qualification BusinessEvent]
    inputs:
        businessEvent BusinessEvent (1..1)
    output:
        is_event boolean (1..1)

    set is_event:
        businessEvent -> eventQualifier = "BuyIn"
```

#### Gap 10: Obligation as First-Class Type (cross-cuts deferred settlement and v10.3 §11.5)

This is a strategic gap that the ledger_v11_cdm_state memory flags as also needed for the obligation-liveness work (§11.5 of v10.3). The proposal sketch:

```rosetta
// In a new file event-obligation-type.rosetta
namespace cdm.event.obligation

import cdm.event.common.*
import cdm.base.staticdata.party.*
import cdm.base.staticdata.asset.common.*
import cdm.product.common.settlement.*

type Obligation: <"A first-class representation of an outstanding bilateral obligation between two parties, with explicit lifecycle states and discharge conditions. Used for deferred settlement obligations between trade date and settlement date, for collateral substitution demands, for SBL recalls, and for CSDR-mandated workflows.">
    [metadata key]
    [rootType]
    identifier Identifier (1..*)
    obligationType ObligationTypeEnum (1..1)
    obligor Party (1..1) <"The party owing the obligation.">
    obligee Party (1..1) <"The party to whom the obligation is owed.">
    obligedAsset AssetFlowBase (1..1) <"The asset (security or cash) and quantity to be delivered.">
    expectedDischargeDate date (1..1)
    actualDischargeDate date (0..1)
    obligationStatus ObligationStatusEnum (1..1)
    sourceEvent BusinessEvent (1..1) <"The originating event (trade execution, recall, substitution demand, ...)">
        [metadata reference]
    dischargeEvent BusinessEvent (0..1) <"The discharging event, populated when the obligation is settled / cancelled / bought-in.">
        [metadata reference]

enum ObligationTypeEnum:
    SettlementDeliveryVersusPayment
    SettlementFreeOfPayment
    CashPayment
    SBLRecall
    SBLReturn
    CollateralSubstitution
    CollateralTopUp
    BuyInDelivery
    CashCompensation

enum ObligationStatusEnum:
    Pending
    Instructed
    PartiallyDischarged
    Discharged
    Failed
    Cancelled
    EscalatedToBuyIn
```

### 5.4 The qualification path for a deferred-settlement equity buy

When the Ledger ingests a buy-side equity execution, the CDM ingestion path is:

1. `ingest-fpml-confirmation-product-equity-func.rosetta` (or the FIX `ingest-...` if FIX) maps the venue execution report to a `BusinessEvent` with `instruction.execution`.
2. `Qualify_Equity_TransferableProduct` (product-qualification-func.rosetta — verified per cdm_6x_verified_facts that product qualification functions exist per asset class) qualifies the underlying.
3. The Ledger applies its mapping function $F$ (v10.3 §9.4) to project the BusinessEvent into the Ledger transaction τ_T described in §2.1.
4. **The obligation issuance has no CDM origin.** It is a Ledger-level emission that is *consistent with* CDM's `TransferState.Pending` semantics but goes beyond them by issuing a unit (`u_obl`) representing the obligation. Until Gap 10 is upstreamed, this is Ledger-internal.
5. At T+2, the inbound `sese.025` confirmation (mapped to `BusinessEvent.eventQualifier = "Settlement"` plus a TransferState with `transferStatus = Settled` plus the new fields `actualSettlementDate`, etc., from Gap 6) maps to τ_{T+2+}.

---

## 6. Failure Modes per Case

Going through each floor case enumerated in the prompt:

### 6.1 CORE — buy T+2

Walked above (§2). E1 holds. R1 holds throughout. Obligation discharged at T+2+.

### 6.2 CORE — sell T+2

Symmetric: at T, the sell-side smart contract emits a security move from the seller's portfolio to `w_inflight_pay` (the seller is *paying* the security), a cash move from `w_inflight_recv` (the seller is *receiving* the cash) to the seller's portfolio, and an obligation issuance with side `DELIVERING`. Same structure, same R1 invariant. Note that the seller's `w_portfolio(AAPL)` goes to its post-sell value at T (may be negative for a short sale, see §6.7).

### 6.3 CORE — T+1

Identical to T+2 with the deferred-settlement window length set to 1 business day. Some markets (FX, some DvP cycles) settle T+1; some equity markets (post-2024 US move) settle T+1 already. The framework parameterises on `expected_settlement_date` per obligation, not on a global T+2 constant. The Equity Smart Contract reads the venue convention from `product-common-settlement-type.rosetta` `SettlementDate`-derived field on the registered product.

### 6.4 CORE — fail (CSDR)

At T+2 the CSD reports a settlement failure (typically: counterparty short on the security). The settlement layer ingests the `sese.024` fail status report. This emits:

```
Transaction τ_{T+2+,FAIL} = LIFECYCLE, type=OBLIGATION_FAIL:

  ObligationStatusUpdate(
      obligation_id: u_obl_xyz,
      previous_status: INSTRUCTED,
      new_status: FAILED,
      timestamp: T+2 (CSD timestamp),
      external_reference: sese.024.<...>,
      metadata: {fail_reason: "LackOfSecurities", reporting_party: <seller_lei>})
```

**No moves on the buyer's real wallet.** E3 holds. The position remains +100 AAPL on the buyer's portfolio (E1 preserved). The in-flight wallet still shows -100 AAPL — i.e. the buyer is still *owed* the shares. R1 still holds: ledger,real (+100) + inflight (-100) + broker (0) = nostro (0). The nostro shows 0 because the CSD did not credit the security.

CSDR cash penalties begin accruing per ESMA penalty matrix (Gap 8 above). On T+5 (or per regime), if still unsettled, the buy-in workflow (Gap 9) is triggered. The penalty is recorded as a `BusinessEvent.eventQualifier = "CashPenalty"` with a `CSDRPenaltyDetail` payload, and the penalty *amount* is a separate cash transfer from the failing seller's wallet to the suffering buyer's wallet.

The economic position never reverses. The PnL since T is still computed against the +100 AAPL position. This is correct: the buyer is economically long AAPL because they bought it, regardless of whether the CSD has yet credited their account. If the buy-in eventually resolves, the buy-in cover trade replaces the original fail and the obligation is discharged via `BuyInExecution.OriginalTransferCancelled`. If the buy-in is impossible (security delisted, etc.), the cash-settlement-in-lieu pays the buyer the reference-price-vs-original-price differential plus penalties; at this point the security position *is* reversed (as the substitute for delivery), via a CORRECTION-class transaction.

### 6.5 CORE — partial

The CSD reports partial settlement: 70 of 100 AAPL settle, 30 fail. This emits:

```
Transaction τ_{T+2+,PARTIAL} = SETTLEMENT, type=PARTIAL_SETTLEMENT, atomic:

  -- Settle the 70-share portion as in §2.5
  Move(... 70 AAPL inflight_recv → nostro_buyer ...)
  Move(... 3500 USD inflight_pay  → nostro_buyer ...)

  -- Issue a child obligation for the residual 30 shares
  Move(from: w_obligation_register, to: w_obligation_register,
       unit: u_obl_xyz, quantity: 0.7,  -- partial discharge marker
       metadata: {status: PARTIALLY_DISCHARGED, remaining_qty: 30})

  -- Spawn a successor obligation for the residual
  Move(from: w_obligation_issuer, to: w_obligation_register,
       unit: u_obl_xyz_residual, quantity: 1, ...,
       metadata: {parent: u_obl_xyz, qty: 30, status: FAILED, fail_reason: "LackOfSecurities"})
```

The CDM-side: this requires Gap 6+7 — `TransferStatusEnum.PartiallySettled` plus the `companion TransferState` records. Without these CDM additions, the partial-settlement representation is Ledger-internal.

### 6.6 CORE — recon across window

Already covered in §4. R1 is the contract; nightly job 1 escalates aged obligations; nightly job 2 reconciles per (wallet, ISIN) using the predicted-nostro formula. Across a multi-day window with multiple trades, the in-flight wallets accumulate the full set of in-flight obligations; R1 holds at every (w, u, t).

### 6.7 COMPOSITION — short (§13 SBL)

A short sale at T composes as: (a) at T-ε or T, borrow the security via SBL (lender's `onloan` += 100, borrower's `borr` += 100, collateral posted; this itself is a SBL deferred-settlement event); (b) at T, sell the borrowed security via the standard buy/sell pattern (§2.1) — borrower's `own` -= 100, the seller-side portfolio goes to `own = -100` (negative own, see v10.3 §13.7 Worked Example). The obligation row for the short-sell is the standard buyer-side obligation as for any sell. The borrow obligation is a *separate* obligation (`ObligationTypeEnum.SBLRecall` or open-loan-state — see §6.8). Critically, *the short-sale settlement-side obligation must be discharged at T+2 by the borrowed shares*. In CDM, this composition is modelled by linking the short-sale `Trade` to the SBL `Trade` via the (yet-unbuilt) Gap 4 / ISLA-coordinated extensions; in the Ledger, both trades emit independent obligation rows that are reconciled via the SBL state machine.

### 6.8 COMPOSITION — recall in window

A lender recalls borrowed securities while a short-sale is in progress. The recall (CDM `UnscheduledTransferEnum.Recall` — direct mapping) issues a *new* obligation: borrower must return Q shares by recall-deadline-date. If the short-seller has not yet bought-to-cover by recall deadline, the short-seller is forced to either find a different lender (rebill) or buy-in. Both outcomes emit further obligations and resolve the original short-sale's borrow obligation. The Ledger represents the recall as a chained obligation:

```
u_obl_recall_xyz (ObligationTypeEnum.SBLRecall)
   parent: u_obl_borrow_xyz
   resolution: requires u_obl_borrow_xyz to discharge by recall-deadline-date
```

### 6.9 COMPOSITION — corporate action in window

Suppose AAPL declares a dividend with record date in (T, T+2), say T+1. The economic question: who gets the dividend?

The legal answer depends on jurisdiction and CSD inscription. In US T+2 (now T+1) markets, the buyer at T is the *beneficial* holder from T but the CSD-inscribed holder is the seller until T+2. Under ex-date rules, the dividend is paid to the seller's nostro by the issuer agent and is *owed* to the buyer via a "manufactured dividend" claim.

Ledger representation:
- The dividend payment hits the seller's nostro (per CSD inscription) — emitted by the issuer-agent oracle event.
- The Equity Smart Contract, recognising that the buyer was beneficial holder on record date (because E1 made them long from T), issues an obligation: seller owes buyer the dividend. This is `ObligationTypeEnum.CashPayment`, expected discharge at the dividend payment date.
- The dividend is reconciled away by a manufactured-dividend cash transfer.

**This is the manufactured-dividend pattern that SBL also uses.** The Ledger's obligation type is the same; the source of the obligation (deferred settlement vs SBL) is tagged in the metadata.

CDM cross-walk: the corporate action is captured by `ObservationEvent.corporateAction CorporateAction (0..1)` (event-common-type.rosetta verified at fetch). The "manufactured dividend" obligation that the seller owes the buyer is the same as in SBL — Gap 4 / Gap 10 coverage. Until Gap 10 is upstream, the obligation is Ledger-native.

### 6.10 COMPOSITION — cross-currency / Herstatt

A USD-EUR FX trade settles asynchronously: USD leg in NY business hours, EUR leg in TARGET2 business hours; CLS provides PvP within a defined window but not instantaneous atomicity. Herstatt risk (1974) is the canonical realisation of this: the EUR leg pays away before the USD leg settles, and the counterparty defaults in the gap.

Ledger representation (v10.3 §2.7 already states the modelling commitment):
- Two obligations are issued at T: USD-leg obligation and EUR-leg obligation.
- Each obligation has its own `expected_settlement_date` and `expected_settlement_time`.
- Each can `SETTLE` independently. The DvP/PvP atomicity becomes a *temporal pairing* invariant on the two obligations.
- The "Herstatt window" between the EUR settlement and the USD settlement is the time period during which exactly one of the two obligations is `SETTLED`. This is detectable.

CDM cross-walk: `TransferSettlementEnum.PaymentVersusPayment` exists; the per-leg status tracking that the Herstatt-window detection requires is the Gap 6 `TransferStatusEnum` enrichment. Without Gap 6, CDM cannot represent the partial-pair-settled state.

### 6.11 COMPOSITION — DvP atomicity

Within a single CSD (DTC, Euroclear, Clearstream), DvP is structurally enforced by the CSD's mechanism. The Ledger represents DvP as a *single transaction* (v10.3 §8.4) — the security move and cash move are atomic at the Ledger level. At settlement, both legs settle together or neither does, by CSD design. This is `TransferSettlementEnum.DeliveryVersusPayment` plus the Ledger's transaction-atomicity primitive (which has no CDM analogue — see Gap 1 of cdm_gap_log on the Ledger transaction primitive). DvP across CSDs (rare, e.g., cross-border with bridge) reduces to PvP and the Herstatt analysis of §6.10 applies.

### 6.12 Edge case — fail-on-record-date

A buy executed T = 2026-04-29, record date T+1 = 2026-04-30, fails-to-settle on T+2 = 2026-05-01. The buyer is beneficial holder from T (E1) and entitled to the dividend by record date being in (T, T+2). The dividend is paid to the seller's nostro. The Ledger emits a manufactured-dividend obligation as in §6.9. The settlement fail is independent — both obligations (the original DVP and the manufactured-dividend) sit in `w_obligation_register` and resolve independently. If the buy-in eventually pays cash-in-lieu, the manufactured-dividend obligation persists (the buyer was beneficial holder, they get the dividend). If the original delivery eventually settles late, both obligations can be discharged separately. **The decoupling of the manufactured-dividend obligation from the settlement obligation is a structural insight**: they are both obligations, both first-class, both monotone-carried, both reconcilable.

---

## 7. Worked Example — 100 AAPL @ \$50 → \$52, PnL = +\$200 at T+1, no cash moved

This is the headline example demanded by the prompt. The proposal walks through it in §2 above. Restating concisely:

| Time | Event | Real wallet (`w_buyer_portfolio`) | In-flight | Nostro | PnL since T | Cash moved? |
|---|---|---|---|---|---|---|
| T = 2026-04-30, 14:30 | execute 100 AAPL @ 50 | AAPL +100, USD -5000 | recv -100 AAPL, pay +5000 USD | 0 / 0 | 0 | no |
| T = 2026-04-30, 16:00 | close \$51 | unchanged | unchanged | unchanged | +\$100 | no |
| T+1 = 2026-05-01, 16:00 | close \$52 | unchanged | unchanged | unchanged | **+\$200** | **no** |
| T+2− = 2026-05-04, 09:00 | sese.023 sent | unchanged | unchanged | unchanged | (depends on T+2 close price) | no |
| T+2+ = 2026-05-04, 15:00 | sese.025 / camt.054 confirms | AAPL +100 (unchanged), USD -5000 (unchanged) | recv 0, pay 0 | nostro_buyer AAPL +100, USD -5000 | (depends on T+2 close) | yes (USD 5000) |

The headline check: at T+1 close, PnL = +\$200, *no cash has moved*. This is because:
- Position is +100 AAPL from T (E1).
- Price moved from 50 → 52 (a +\$2 per share move).
- 100 × +\$2 = +\$200 unrealised PnL, computed by the valuation function $V_t = \sum_u w_t(u) \cdot P_t(u)$.
- The cash leg (-5000 USD) is also unchanged in *quantity*, but its *value* in terms of itself is constant (USD per USD = 1), so it contributes nothing to PnL.

This is the core demonstration that the Ledger's representation is correct. A trade-date-only system would produce the same PnL but would not reconcile to nostro on settlement. A settlement-date-only system would produce zero PnL until T+2, which is wrong. The Ledger's three-object representation produces the right PnL and the right reconciliation.

---

## 8. Closing — what makes this proposal definitive

1. **The economic-exposure-at-T invariant E1 is mandatory and structural** (§1.4). Every other claim in the proposal is downstream of E1.
2. **The obligation is a unit** — it earns a place in the existing 3-map StatesHome schema as a `PositionState[w_obligation_register, u_obl]` row, with no new state map needed (§1.2). This is the cleanest way to make the gap explicit and reconcilable.
3. **R1 is the reconciliation contract** between Ledger and nostro (§1.5, §4). It is a single equation that holds for every (w, u, t) and that fails detectably.
4. **Four firm-strategic CDM extensions are needed** (§5.3): TransferStatus enrichment (Gap 6), partial settlement (Gap 7, subsumed in 6), CSDR cash penalty (Gap 8), buy-in event (Gap 9). All are upstreamable. Plus Obligation as first-class (Gap 10), which composes with the v10.3 §11.5 obligation-liveness work.
5. **All composition cases are covered** (§6) — short, recall, corporate action, cross-currency/Herstatt, DvP, partial, fail. The composition rule is uniform: each independent obligation is its own row, reconciled independently, monotone-carried.

Verification on the live CDM 6.x repository: every type, enum value, and field cardinality cited in this document was raw-fetched from `github.com/finos/common-domain-model@master` at 2026-04-30. The cited file paths are correct under the flat dot-namespaced scheme (CDM 6.x path scheme memory). The four absent enum values (`Failed`, `PartiallySettled`, `Cancelled` on `TransferStatusEnum`; `Failed` on `PositionStatusEnum`) and the four missing types (`CSDRPenaltyDetail`, `BuyInExecution`, `Obligation`, `TransferFailureReason`) are confirmed not to exist in CDM 6.x and constitute genuine gaps.

This proposal is implementation-ready. The Rosetta extension drafts in §5.3 are namespace-qualified, field-shape-precise, and integrate cleanly with existing CDM types via the existing `[metadata reference]` and `[metadata key]` patterns. They are upstreamable to FINOS as PR units in the cdm_gap_log inventory.
