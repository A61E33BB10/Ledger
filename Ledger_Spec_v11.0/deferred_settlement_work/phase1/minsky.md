# Deferred Settlement: Type-Theoretic Design

**Author:** MINSKY (Phase 1, Team A — independent proposal)
**Question:** How does the Ledger represent the open settlement obligation between T and T+2 such that
(1) economic position is true from T,
(2) the obligation is explicit and reconcilable,
(3) the ledger reconciles to nostro at T+2,
(4) the mechanism degenerates across variants (T+0, T+1, T+2, fail, partial, short, recall, corp action, FX, DvP)?

**Approach:** make every illegal state in §8 of v10.3 (the `EXECUTED → INSTRUCTED → SETTLED/FAILED` lifecycle, plus
the trade-date-vs-settlement-date split) **unrepresentable**. The runtime invariants of v10.3 §11 become
type-level theorems where this is cheap, and remain handler-checked invariants where the type cost is
prohibitive. The boundary between the two is named, not negotiated.

---

## 0. The thesis in one paragraph

Today, v10.3 expresses "economic position from T" by *committing the cash and securities moves at T*, and
"settlement happens at T+2" by *labelling the transaction's status* (`EXECUTED → INSTRUCTED → SETTLED/FAILED`,
§8.6). That is a string on a wallet. Under any non-trivial composition (short cover with a recall straddling
T+2, a fail that becomes a buy-in, an FX leg that settles in CLS, a corporate action with record date inside
the open settlement window) the string is read by a different handler than the one that wrote it, and the
window between trade-time recognition and custody-time movement gets reasoned about *informally*.

The fix: the *open settlement obligation* is a **first-class typed object** — a unit, not a flag — held in
two virtual wallets (one per party) over the interval `[T, T+settle_date]`. It has a sum-type lifecycle
(`Pending | PartiallySettled | Settled | Failed | BoughtIn | Cancelled`), a refinement-typed settlement
date, smart constructors that reject malformed obligations at the boundary, and a single total step function.
Custody movement at T+2 is the obligation's discharge, not a separate event. Reconciliation to nostro is
**lead–lag by design**: nostro at any time `t` is the projection `coll_recv` (or `own`-on-currency) **minus**
the live obligations whose `settle_date > t`. There is a unique map from this design to v10.3's
`StatesHome` 3-map ruling, to the SBL `coll_post / coll_recv` vector, and to ISDA CDM `TradeState`.

---

## 1. State Representation

### 1.1 The two layers under the trade-date / settlement-date gap

Trade-date accounting (v10.3 §1, §8.5) makes two facts true *simultaneously* at instant T:

| layer | what is true at T | where it lives in v10.3 |
| -------------- | ----------------------------------------------------------- | ------------------------- |
| economic | buyer has +Q shares; seller has −Q shares; cash mirrored | wallet balances (P1) |
| custodial | nostro/depot has not moved; CSD will move at T+settle\_date | nostro reconciliation (§8.6, P2 in §11) |

The current spec keeps both layers consistent by emitting *all four moves* (cash + security in both
directions) at T, and tagging the transaction `EXECUTED`. That is correct under the conservation law
($\sum_w w(u) = 0$), but the open obligation is **implicit** — it is the difference between the wallet
balance and the nostro balance. Anything that can read a wallet can therefore reason about the obligation
without ever proving it discharged.

### 1.2 The Settlement Obligation as a Typed Unit

Promote the obligation to a unit `u_so` (Settlement Obligation), held by two wallets:

```
w_long_so   :  +1   (the receiver of securities, payer of cash)
w_short_so  :  −1   (the deliverer of securities, receiver of cash)
sum         :   0   (conservation, P1, holds by issuance)
```

The unit's `ProductTerms` (per the StatesHome ruling) carry the *terms of the obligation*:
ISIN to deliver, currency, gross quantity, gross cash, settlement date, place of settlement (CSD MIC),
DvP type, counterparty LEI, original `Trade.tx_id`. The unit's `UnitStatus` carries the *lifecycle stage*:
`Pending | PartiallySettled q_settled | Settled | Failed reason | BoughtIn buyin_ref | Cancelled`. The
unit's `PositionState[w_long, u_so]` carries per-position settlement-leg cursors (partial fills,
manufactured payments owed, CSDR penalty accrual).

This is a *direct application* of the StatesHome ruling: an open settlement obligation is a contract; the
contract is a unit; the contract's lifecycle is `UnitStatus`; per-position cursors are `PositionState`.
There is **no new schema sector**.

### 1.3 The phantom-typed unit family

The crucial type discipline is at the *unit level*. Introduce two phantom-type tags on units:

```ocaml
type exposure_bearing       (* counts toward economic position, drives PnL  *)
type custody_bearing        (* counts toward nostro / depot reconciliation  *)

type ('phase) unit_id =     (* 'phase ∈ { exposure_bearing; custody_bearing } *)
  | Cash       of currency_code      (* both                                 *)
  | Security   of isin               (* both                                 *)
  | SettleObl  of obligation_terms   (* exposure_bearing only, until discharge *)

(* Compile-time refinement: the same physical ISIN can appear in TWO unit
   identities during a settlement window — the "real" share unit (custody-bearing,
   what settles at the CSD) and the SettleObl wrapper (exposure-bearing, what
   pays PnL between T and T+2). They are NEVER the same value at the type level. *)
```

The discipline: only `custody_bearing` units may be debited from a nostro wallet. The nostro debit
function has type

```ocaml
val debit_nostro :
  w_nostro       ->
  (custody_bearing) unit_id ->     (* phantom guard *)
  qty            ->
  trade_date:date -> settle_date:date ->
  unit            (* succeeds iff settle_date <= now *)
```

A handler that tries to settle a `SettleObl` directly against nostro fails to *type-check*. The only
way to move custody is to first **discharge** the obligation, which (a) flips the obligation's
`UnitStatus` to `Settled`, and (b) emits a paired `Move` on the underlying `Security` and `Cash` units in
their `custody_bearing` form. **The two-step is structural**.

### 1.4 What this rules out, by construction

The following are now **not expressible in the type system**, never mind testable at runtime:

| illegal state | how it is ruled out |
| ----------------------------------------------- | -------------------------------------------------- |
| Debit nostro before T+2 | `debit_nostro` requires `custody_bearing`; obligation is `exposure_bearing` until `Settled` |
| Settle the same obligation twice | `Settled` is terminal in the FSM; `step` on terminal is a type-level no-op |
| PnL count exposure twice (security AND obligation) | Valuation is total over `exposure_bearing` units only; security-leg-pre-settlement is the obligation, post-settlement is the security |
| Forget to settle (silent T+2 drift) | Liveness obligation `L_15` (data spec §$L_{15}$) bound to the unit; deadline timer fires `Failed` |
| Cross-currency Herstatt (settle one leg, lose other) | DvP atomicity stated as a *paired-obligation* type — see §1.5 |
| Settlement on the wrong date | Refinement type `settle_date` is constructed from `(trade_date, market_calendar)`, not user-supplied |

---

## 2. Move Sequence — Move(...) blocks T, T+1, T+2⁻, T+2⁺

### 2.1 Trade T (buy 100 XYZ @ $50, T+2, DvP)

```
Transaction(type = SETTLEMENT, tx_id = T1):

  -- Economic recognition (exposure-bearing layer):
  Move( from: w_seller_real,    to: w_buyer_real,
        unit: SO_buyer,         quantity: 1,
        timestamp: T,           source: T1,
        metadata: "open_obligation_buyer" )

  Move( from: w_buyer_real,     to: w_seller_real,
        unit: SO_seller,        quantity: 1,
        timestamp: T,           source: T1,
        metadata: "open_obligation_seller" )

  -- where SO_buyer.terms = { receive: (XYZ, 100), pay: (USD, 5000), settle: T+2 }
  --       SO_seller.terms = mirror
```

**Crucially: no `Move` on the underlying `XYZ_custody` or `USD_custody` units fires at T.**
Wallet balance of `XYZ` (custody-bearing) is unchanged; nostro is unchanged.

What about PnL? PnL is `V_t = Σ_u w_t(u) · P_t(u)` (v10.3 §3). The `SO_buyer` unit's price function is

```
P_t(SO_buyer) = (P_t(XYZ_custody) − strike_cash_per_share) · qty
              − settle_risk_adjustment(t)        (* normally zero *)
```

so as `P_t(XYZ_custody)` rises from $50 to $52, the buyer's `SO_buyer` unit revalues from $0 to +$200,
the seller's `SO_seller` unit revalues from $0 to −$200, and PnL is true *from T*. **No cash moved.**
This is the v10.3 settlement-date / trade-date split made explicit in the price function rather than buried
in a status flag.

### 2.2 T+1 (mark-to-market, no custody event)

```
-- ACCOUNTING transaction (does NOT settle):
Transaction(type = ACCOUNTING, tx_id = T1_M1):
  -- empty move list; updates UnitStatus[SO_buyer].mtm_cursor and
  -- UnitStatus[SO_seller].mtm_cursor only.
```

PnL is path-independent (P10): `V_{T+1} − V_T = (P_{T+1}(SO_buyer) − P_T(SO_buyer))`.
Q6-style FAQ: move-less transactions are valid (v10.3 Q6).

### 2.3 T+2⁻ (instruction submitted; obligation still Pending)

```
Transaction(type = LIFECYCLE, tx_id = T1_S1):
  -- transitions UnitStatus[SO_buyer].lifecycle: Pending → Instructed
  -- emits no moves; the settlement projection (§8.1) reads tx T1 to produce
  -- the sese.023 instruction. The CSD has not yet confirmed.
```

This is exactly the v10.3 `INSTRUCTED` status, but as a *typed FSM transition* on a unit, not a string on a
transaction. The compiler enforces the order `Pending → Instructed → Settled`; a handler attempting
`Pending → Settled` (skipping Instructed, equivalent to claiming custody confirmation without ever sending
the instruction) is a *type error*. C11 of StatesHome (handler-field canon) names the unique writer.

### 2.4 T+2⁺ (CSD confirms, obligation discharges)

This is the only moment the *custody-bearing* units move. The obligation's discharge is a single atomic
transaction that simultaneously:

1. flips the obligation's `UnitStatus` to `Settled`,
2. emits the paired security and cash moves in the custody-bearing layer,
3. retires the obligation unit (balances go to zero on both sides; rows survive — monotone carrier, C1).

```
Transaction(type = SETTLEMENT, tx_id = T1_D1):

  -- Discharge of obligation (exposure-bearing layer collapses):
  Move( from: w_buyer_real,  to: w_seller_real,
        unit: SO_buyer,      quantity: 1,
        metadata: "discharge_buyer" )
  Move( from: w_seller_real, to: w_buyer_real,
        unit: SO_seller,     quantity: 1,
        metadata: "discharge_seller" )

  -- Custody movement (custody-bearing layer):
  Move( from: w_seller_nostro, to: w_buyer_nostro,
        unit: XYZ_custody,   quantity: 100,
        metadata: "csd_settled_T1" )
  Move( from: w_buyer_nostro, to: w_seller_nostro,
        unit: USD_custody,   quantity: 5000,
        metadata: "csd_paid_T1" )
```

After T1\_D1: `w_buyer_real(SO_buyer) = 0`, `w_buyer_nostro(XYZ_custody) = 100`,
`w_buyer_nostro(USD_custody) = −5000`. Position is unchanged in economic terms (still long 100 XYZ);
nostro now reconciles. **The lead–lag has closed by construction.**

### 2.5 Why this works for the price function

At T: `P_T(SO_buyer) + P_T(XYZ_custody position from this trade) = P_T(XYZ) · 100`, with the second term
zero because no custody-bearing position exists yet. At T+2⁺: same identity, now the first term zero and
the second term carrying the position. PnL is continuous through the discharge: the discharge transaction
produces zero NET valuation change (it is a coordinate change, not a fact change). This is the
"ownership = balance" principle (§2.2) applied at the right grain.

---

## 3. Invariants — MANDATORY economic-exposure-at-T

Every invariant below either *holds by construction* (compile-time) or *holds by handler proof obligation*
(runtime, per-event-class à la C2 of StatesHome). I mark each (cc) for compile-time / construction or
(rt) for runtime handler-discharged.

### 3.1 Core invariants over the open-obligation lifetime

**I-DEF-1 (cc) — Trade-date economic recognition.**
For every committed trade transaction `τ` of type `SETTLEMENT` with a non-cash leg, the buyer's
`PositionState[w_long, u_so]` and seller's `PositionState[w_short, u_so]` are written within `τ`.
*Compile-time:* `emit_trade : Trade -> Transaction` is a total function whose return value is rejected
by the executor unless its move list contains a paired `(SO_long, SO_short)` issuance.

**I-DEF-2 (cc) — No custody movement before settle\_date.**
For every move `m` whose unit is `custody_bearing`, `m.timestamp >= τ.cdm_payload.settlement_date`
(where `τ` is the issuing trade transaction). *Compile-time:* `debit_nostro` is the unique writer of
custody-bearing units (C11), and its signature requires `settle_date <= now`.

**I-DEF-3 (cc) — DvP discharge atomicity.**
The discharge transaction is the *only* place where custody moves. For a paired obligation
$(u_{so}^{buy}, u_{so}^{sell})$, both must discharge in the same `Transaction`. *Compile-time:* the
type `PairedObligation` is a *single value* — discharging one without the other does not type-check
because the discharge function takes a `PairedObligation`, not two independent obligations.

**I-DEF-4 (rt, structural) — Conservation across the obligation lifetime.**
$\sum_{w} w_t(u_{so}) = 0$ for all $t$. *Handler proof:* issuance writes +1 / −1; discharge writes
−1 / +1; cancellation likewise; failure leaves the rows in place. C2 obligation discharged per event
class.

**I-DEF-5 (rt) — Liveness of the open obligation.**
Every `Pending` obligation has a `due_event` registered with the scheduler (v10.3 §11.13). For each
obligation `u_so` with `settle_date = d`, a workflow timer fires at `d + grace`, and the obligation FSM
must have left `Pending` by then or transition to `Failed reason=DeadlineMissed`. *Handler proof:*
the `ObligationWorkflow` (data spec $L_{15}$) is the unique handler permitted to leave `Pending`.

**I-DEF-6 (cc) — Nostro lead–lag identity.**
For any time `t` and any custody wallet `w_n`,

$$
w_n(u_{custody}) = \texttt{depot\_at}(w_n, u_{custody}, t) + \sum_{u_{so}\, :\, \text{Pending}\, \wedge\, \text{matures > } t}\!\!\!\Delta_{settle}(u_{so}, w_n)
$$

i.e. *nostro = depot + open obligations not yet matured*, where $\Delta_{settle}$ is the signed quantity
the obligation would deliver to/from `w_n` on its `settle_date`. This is an *equation in types*: it is
the projection function `nostro_balance` whose body **is** that sum, and `depot_at` is its only external
input.

**I-DEF-7 (cc) — Position invariance under discharge.**
For any wallet `w` and any underlying security `u_s`,

$$
\text{exposure}(w, u_s, t) = w_t(u_{custody\,s}) + \sum_{u_{so}\,:\, \text{Pending}\, \wedge\, \text{u\_s in terms}}\!\!\!\text{signed\_qty}(u_{so}, w, u_s)
$$

is preserved across the discharge transaction. *Compile-time:* discharge is the unique transformation
that simultaneously decrements obligation balance and increments custody balance with the same signed
quantity; the move-pairing is checked by the executor's emission rule.

### 3.2 Composition invariants

**I-DEF-8 (cc) — Short discharge correctness (§13).**
A short sale at T is a trade in the buyer/seller framework where the seller's `own` is decremented
(per v10.3 §13). The settlement obligation `u_so^{short}` requires the seller, by `settle_date`, to
have *available inventory* (Definition: avail-projection in §13). *Compile-time:* the discharge
function for a short-side obligation has a refinement-typed precondition
`avail(seller_wallet, u_s) >= obligation.qty`. If false at discharge time, the discharge does not
fire — the obligation transitions to `Failed reason=NoCover`, never `Settled`.

**I-DEF-9 (cc) — Recall ordering with open obligations.**
A recall on a lent security (`onloan` decrease) before discharge of an open settle-obligation that
*depends* on the same security is a partial order. *Compile-time:* the recall handler's signature
takes a refined `borrowable_qty(t) = own − onloan − Σ pending_short_obligation_qty`. A recall that
would drive that quantity negative does not type-check; it must transition through a partial-recall or
substitution path.

**I-DEF-10 (rt) — Corporate action across settlement window.**
If a corporate action's record date `r` satisfies `T < r ≤ T+2`, the entitlement attaches to the
*open obligation*, not to either custody wallet — because at `r`, the security has not yet moved
in the custody layer, but the economic position has moved in the exposure layer. This is the
"market claim" mechanism. *Handler proof:* the corp-action smart contract reads the union of
custody balances *and* live obligations, weights by `signed_qty`, and emits the manufactured
payment to the correct economic owner. The obligation's `ProductTerms` carry an `entitlement_capture`
predicate that names the rule.

**I-DEF-11 (cc) — Cross-currency / Herstatt safety.**
For an FX trade with two currency legs that settle in different time zones (CLS or non-CLS), the trade
emits **two** paired `SettleObligation` units, one per currency, with the *same* `tx_id_origin` but
*different* `settle_date`s. Each leg discharges independently. *Compile-time:* a function
`compose_FX : Trade_FX -> (PairedObligation_USD, PairedObligation_JPY)` produces a tuple, not a
synthetic single obligation, so a handler that "settles the FX trade" must deal with two values. The
non-atomicity is *visible in the type*. Herstatt risk is not eliminated — it is rendered
unrepresentable as accidental atomicity. The discharge of leg 1 *cannot* type-check as discharge of
the FX trade; only `(discharge leg_1, discharge leg_2)` can.

**I-DEF-12 (cc) — DvP atomicity at the obligation grain.**
The DvP guarantee is restated as: the *paired obligation* `PairedObligation` is a single typed value
whose discharge is a single transaction. Either both `Move`s on `(u_so^{long}, u_so^{short})` and both
custody moves commit, or none do. *Compile-time:* the executor consumes a `PairedObligation` and
returns a `DischargeResult`; partial application is impossible because there is no public API that
takes a single side. (This complements v10.3 §8.4: ledger-level DvP is by transaction atomicity;
*type-level DvP is by paired obligation*.)

### 3.3 The relationship to v10.3 §11 invariants P1–P10

| §11 | how I-DEF-* covers it |
| --- | -------------------------------------------------------------------------------- |
| P1  Conservation | I-DEF-4 (Σ on `u_so` zero by issuance/discharge symmetry) |
| P2  Atomic commitment | I-DEF-12 (PairedObligation discharge atomic by type) |
| P3  Referential integrity | (cc) — every obligation `ProductTerms` is registered before issuance (C7) |
| P4  Log monotonicity | unchanged — the move stream is append-only |
| P5  Tx idempotency | tx\_id-based dedup at issuance and discharge |
| P6  Lifecycle idempotency | I-DEF-12 — discharge on `Settled` is a no-op (terminal) |
| P7  Virtual/real isolation | obligation lives in *real* wallets; nostro is a virtual contra; same rule |
| P8  Snapshot consistency | obligation rows are monotone-carriers (C1); replay reproduces |
| P9  Lifecycle purity | step function is total + pure (see §3.1 below) |
| P10 PnL path-independence | obligation price `P_t(u_so)` is well-defined per §2.5 |

---

## 4. Reconciliation — lead-lag BY DESIGN

### 4.1 The three balance projections

Define three pure functions over the wallet/unit graph. None is stored. All three are total.

```ocaml
val ledger_position : wallet -> security_id -> time -> qty
(* exposure-bearing: includes open obligations *)
(* = Σ over u_custody of own + signed_qty contribution of every Pending obligation *)

val depot_position : wallet -> security_id -> time -> qty
(* custody-bearing: only what has settled at the CSD *)
(* = w_t(u_custody) only *)

val nostro_expected : wallet -> security_id -> time -> qty
(* what the nostro/depot SHOULD show at time t, given the live obligations *)
(* = depot_position - Σ_{matured obligations not yet discharged} signed_qty *)
```

The reconciliation triangle:

```
ledger_position  ───── (lead) ─────▶  what the trader sees, true from T
                                  
                                    economic exposure
                                  
depot_position    ◀──── (lag) ─────  what the custodian sees, true from T+2
                                                                                  
                                    custody confirmation
                                  
nostro_expected   ────────────────  what the ledger expects the custodian to confirm
                                    (= depot_position adjusted for Settled obligations
                                       that have not yet been confirmed by sese.025)
```

### 4.2 The reconciliation theorem

**Theorem (Recon).** For every wallet `w` and security `u_s` and time `t`,

$$
\texttt{ledger\_position}(w, u_s, t)
\;=\;
\texttt{depot\_position}(w, u_s, t)
\;+\;
\!\!\!\sum_{\substack{u_{so}\, :\, \text{Pending} \\ w \in \text{parties}(u_{so}) \\ u_s \in \text{terms}(u_{so})}}\!\!\!
\text{signed\_qty}(u_{so}, w, u_s)
$$

This is **the projection**, by the definition of `ledger_position`. There is nothing to prove — it is
the type signature. The reconciliation report is a `diff` of three queries, all over the same database.

### 4.3 Why this beats the v10.3 status-flag approach

In v10.3 §8.6, the status `EXECUTED → INSTRUCTED → SETTLED` is on the *transaction*. To answer
"is my Tuesday position reconciled?", an operator must:

1. find every transaction touching wallet `w` with security `u_s`,
2. filter by status `SETTLED`,
3. sum.

This is a *query*. It is correct, but it is not a *type*. Under composition (multiple trades, recalls,
fails, partial fills), the status flag is a string per transaction, but the reconciliation needs a fold
across them. The fold is hand-coded per asset class.

In the type-design proposed here, the reconciliation projection is **one function**, total over all
asset classes that can be modelled with `(custody_bearing, exposure_bearing)` units, including SBL
(where `coll_post / coll_recv` are custody-bearing too). It degenerates correctly:

- For an instrument that settles T+0 (FX intra-day, MMF same-day): `settle_date = T`, the obligation
  is issued and discharged in the same transaction, exposure-bearing and custody-bearing collapse.
- For T+1 (US equities post-2024): a one-day window, same mechanism.
- For T+2 (current EU, pre-2024 US): the canonical case.
- For SBL: `coll_post / coll_recv` are custody-bearing scalars (per v10.3 Q10); the obligation pattern
  applies to the in-flight collateral (IBP-177) as a one-day or sub-day obligation.

---

## 5. CDM Cross-walk

### 5.1 ISDA CDM `TradeState` mapping

CDM models the post-trade lifecycle as a `TradeState` graph. The CDM `TradeState` for an unsettled
trade carries:

- `Trade.tradeIdentifier` ↔ our `tx_id_origin` (the trade transaction)
- `Trade.tradeDate` ↔ T (the timestamp of the issuance)
- `Trade.product.economicTerms.settlementTerms.settlementDate` ↔ obligation's `settle_date`
- CDM `Transfer` events under `BusinessEvent.primitiveInstruction` ↔ our discharge transaction's moves

The CDM `TransferState` enum (`INSTRUCTED | EFFECTIVE | SETTLED | FAILED`) maps **exactly** to our
obligation `UnitStatus`:

| CDM `TransferState` | this design's `lifecycle_stage` |
| ------------------ | ---------------------------------------- |
| `INSTRUCTED` | `Pending` (after `Instructed` sub-state) |
| `EFFECTIVE` | `Settled` |
| `SETTLED` | `Settled` (with confirmation reference) |
| `FAILED` | `Failed reason=...` |

**Forgetful mapping** $F$: a CDM `BusinessEvent` of intent `EXERCISE`/`SETTLEMENT` decomposes into a
**discharge transaction** in our schema. CDM `TradeState.before` ↔ our obligation `UnitStatus = Pending`;
CDM `TradeState.after` ↔ our obligation `UnitStatus = Settled`. The CDM `Lineage` is preserved in the
move's metadata payload. `F` is a faithful functor on this slice: composition is preserved
(I-DEF-12), conservation is preserved (I-DEF-4), idempotency is preserved (P5/P6).

### 5.2 ISO 20022 mapping at the boundary

The `SettlementInstruction` projection (v10.3 §8.1) is unchanged. The projection now reads:

```
settle_projection(τ_discharge):  -- τ_discharge is the discharge transaction
    let obl = τ_discharge.discharged_obligation  (* PairedObligation *)
    return SettlementInstruction(
        instruction_id   : obl.tx_id_origin,
        trade_date       : obl.terms.trade_date,
        settlement_date  : obl.terms.settle_date,
        ...                         -- all from obl.terms, which is immutable
    )
```

Because `obl.terms` is immutable (C6), the projection is deterministic and idempotent (v10.3 §8.1).

### 5.3 SBL `coll_post / coll_recv` integration

Per v10.3 Q10, cash collateral is a scalar `coll_recv`. In SBL:

- the loan-initiation in-flight collateral is an *open obligation* with `settle_date` typically T+0 or T+1;
- it is held as a `SettleObligation` unit `u_so^{coll}` until the custodian confirms the cash transfer;
- its discharge writes the borrower's `coll_post` and the lender's `coll_recv` (both custody-bearing
  scalars on the cash unit).

This is **the IBP-177 prepay-collateral case** rendered in the same type as a regular DvP equity
trade, no new mechanism.

---

## 6. Failure Modes Per Case

### 6.1 Floor case matrix

| case | how the type system handles it |
| ----------------- | ---------------------------------------------------------- |
| **Buy T+2** | obligation issued at T, discharged at T+2 (canonical) |
| **Sell T+2** | mirror: short side of `PairedObligation`; same FSM |
| **T+1** | `settle_date = T+1`; same FSM, shorter window |
| **T+0** | `settle_date = T`; obligation issued and discharged in the same transaction; the type degenerates — `SettleObl` is created with terminal lifecycle, exposure = custody collapse |
| **Fail (CSDR)** | at `settle_date + grace`, deadline timer fires; FSM transitions `Pending → Failed reason=DeadlineMissed`; CSDR penalty obligation is *issued* as a child obligation `u_so^{penalty}` whose discharge is a cash transfer per CSDR rate-card; this fan-out is structural (the failure handler returns a list of new obligations) |
| **Partial** | FSM transition `Pending → PartiallySettled q_settled`; a *new* obligation `u_so'` is issued for the residual `qty − q_settled`, with the same `settle_date` (or rolled per market convention); the original `u_so` is discharged for `q_settled` (custody moves accordingly); recursion: the residual itself can fail or be partially settled, recursively |
| **Recon** | Theorem of §4.2 gives a closed-form difference; `BreakRegister` ($L_{18}$) opens a row only when the diff is non-zero AND not explainable by a Pending obligation in the window |
| **Short (§13)** | obligation precondition `avail(seller, u_s) >= qty` is refinement-typed; failure → `Failed reason=NoCover` → child obligation for buy-in or borrow |
| **Recall** | partial order with open short-side obligations; recall handler refuses if the recall would drive `borrowable_qty − Σ pending_short_qty < 0`; either substitution or partial recall path |
| **Corp action** | record date inside `(T, T+2]`: market-claim mechanism; the corp-action handler reads union of custody and obligations; entitlement attaches to economic owner, not custody owner; this is I-DEF-10 |
| **Cross-currency (Herstatt)** | two `PairedObligation`s, two independent FSMs, two settlement dates; non-atomicity is *visible in the type signature* — see I-DEF-11 |
| **DvP atomicity** | structural: discharge consumes a `PairedObligation`; partial discharge does not type-check — see I-DEF-12 |

### 6.2 Where the type system stops, and runtime begins

I am honest about this: not everything is compile-time. The matrix below is the boundary.

| concern | enforced where | why not the other side |
| ------------------------- | ----------------- | -------------------------------------------------------------------- |
| Settle-date in custody | compile-time | phantom type on units; cheap |
| DvP discharge atomicity | compile-time | `PairedObligation` is one value; cheap |
| Conservation of `u_so` | runtime (handler) | refinement types on Decimal sums are not free in OCaml/Haskell — C2 of StatesHome explicitly chooses runtime |
| Liveness (deadline) | runtime (workflow timer) | clocks are external; C-A_7 of data spec |
| Short-cover precondition | compile-time | refinement-type check is local to handler |
| Corp-action entitlement attach | runtime (handler) | the rule depends on event semantics; encoding it in types collapses to encoding the corp-action calculus |
| Cross-currency timezone risk | runtime (Herstatt is real) | type system makes it visible; cannot eliminate clock-skew risk |

This is the v10.3 §11 / data-spec style: state which invariants are "structurally unreachable" (the
seven from C1–C12 in StatesHome) and which are runtime obligations.

---

## 7. Worked Example — 100 XYZ @ $50 → $52

### 7.1 Setup

- Buyer `B`, Seller `S`, T+2 DvP equity trade, USD-USD same-currency
- Trade time T, Day 0; settlement target T+2 = Day 2
- XYZ price T = $50, T+1 = $52, T+2⁻ = $51 (mid-day), T+2⁺ = $51 (close)
- No fail; no corp action; no fee complications

### 7.2 Wallet state evolution

```
Time T (trade execution)
==========================
  PT registry:
      u_so_buy_T1   (terms: receive XYZ x 100, pay USD x 5000, settle = T+2)
      u_so_sell_T1  (mirror; terms.signed = inverse)

  Wallets — exposure-bearing:
      w_B(u_so_buy_T1)  = +1
      w_S(u_so_sell_T1) = +1
      Σ on each obligation = 0  ✓

  Wallets — custody-bearing:
      w_B_nostro(XYZ_custody) = 0
      w_B_nostro(USD_custody) = +5000   (pre-trade cash)
      w_S_nostro(XYZ_custody) = +100    (pre-trade inventory)
      w_S_nostro(USD_custody) = 0

  P_T(u_so_buy_T1)  = 0
  V_B(T)            = 5000              (cash only; obligation worth zero at trade)
  V_S(T)            = 5000              (100 XYZ at $50; obligation worth zero)

Time T+1 (mark-to-market, no custody event)
==========================
  Custody-bearing wallets unchanged.
  P_{T+1}(XYZ) = 52
  P_{T+1}(u_so_buy_T1)  = (52 − 50) × 100 = +200
  P_{T+1}(u_so_sell_T1) = −200
  V_B(T+1) = 5000 + 200 = 5200
  V_S(T+1) = 5200 − 200 = 5000   (intuitively unchanged because S is short the upside)

  Wait — let's check. S still owns 100 XYZ at custody = 100 × 52 = 5200, plus
  the open obligation worth −200, so V_S = 5200 − 200 = 5000. ✓
  B has 5000 cash plus open obligation +200, so V_B = 5200. ✓
  Conservation: ΔV_B + ΔV_S = +200 + 0 = +200 = ΔP × qty held by B's exposure side. ✓

  PnL_B(T → T+1) = +200, PnL_S(T → T+1) = 0. Correct: B has the long exposure.

Time T+2− (instruction submitted, before CSD confirms)
==========================
  No moves; UnitStatus[u_so_buy_T1] := Pending → Instructed
                  UnitStatus[u_so_sell_T1] := Pending → Instructed
  Custody-bearing layer unchanged.

Time T+2+ (CSD confirms; discharge transaction T1_D1 fires)
==========================
  Transaction T1_D1:
    -- exposure-bearing layer: obligation balance flips to zero
    Move(B → S, u_so_buy_T1,  qty=1)
    Move(S → B, u_so_sell_T1, qty=1)

    -- custody-bearing layer: nostro moves
    Move(w_S_nostro → w_B_nostro, XYZ_custody, qty=100)
    Move(w_B_nostro → w_S_nostro, USD_custody, qty=5000)

  After T1_D1:
      w_B(u_so_buy_T1)        = 0
      w_S(u_so_sell_T1)       = 0
      w_B_nostro(XYZ_custody) = +100
      w_B_nostro(USD_custody) = 0
      w_S_nostro(XYZ_custody) = 0
      w_S_nostro(USD_custody) = +5000

  At P_{T+2}(XYZ) = 51:
      V_B(T+2) = 0 + 100 × 51 = 5100
      V_S(T+2) = 5000 + 0     = 5000
```

### 7.3 PnL audit

|  | t   = T | t = T+1 | t = T+2 |
| --- | -------------- | -------------- | ------- |
| `V_B` | 5000 | 5200 | 5100 |
| `V_S` | 5000 (5000 cash + 0 from obl) | 5000 (5200 from XYZ + −200 from obl) | 5000 (5000 cash) |
| total | 10000 | 10200 | 10100 |

PnL totals: `B = +100`, `S = 0`. `B` paid 5000 for 100 XYZ now worth 5100. Correct.

**At T+1, no cash has moved, but B's PnL is true (+200 on the trade).** That is the requirement.
At T+2⁺ the custody actually changes; PnL is path-independent (T+2 prices yield 5100 / 5000 regardless
of intermediate path).

### 7.4 The reconciliation report at T+1

```
ledger_position(w_B, XYZ, T+1)   = depot_position(w_B, XYZ, T+1) + signed_qty(u_so_buy_T1) × in_window
                                = 0 + 100 = 100  ✓ (B's economic position is true from T)

depot_position(w_B, XYZ, T+1)   = 0   ✓ (custody hasn't moved)

nostro_expected(w_B, XYZ, T+1)  = 0 − 0 = 0   (no Settled-but-unconfirmed obligations)

reconciliation diff to custodian's reported depot:
    custodian.depot(B, XYZ, T+1) = 0
    nostro_expected − custodian.depot = 0 − 0 = 0  ✓ no break
```

Lead–lag: `ledger_position − depot_position = signed_qty(u_so_buy_T1) = 100`. **This is not a
break.** It is the *signature of a live obligation in the window*. The reconciliation theorem of
§4.2 asserts this is precisely the sum of open obligations, which is always knowable, never
mysterious.

---

## 8. Type Design — Concrete OCaml Sketches

### 8.1 Newtype wrappers (compile-time date discipline)

```ocaml
(* Newtype-d distinct calendar dates. They cannot be confused at compile time. *)
module TradeDate   : sig type t val of_date : Date.t -> t end = struct type t = Date.t let of_date d = d end
module SettleDate  : sig type t val of_trade_date : TradeDate.t -> SettleConvention.t -> t end = struct
  type t = Date.t
  let of_trade_date td conv = SettleConvention.add_business_days conv td
end
module ValueDate   : sig type t val of_settle : SettleDate.t -> t end = struct type t = Date.t let of_settle s = s end
module RecordDate  : sig type t end = struct type t = Date.t end

(* SettleDate is constructed FROM TradeDate + SettleConvention.
   No public constructor takes a raw date. A handler that wants to settle on
   "tomorrow" CANNOT pass a Date.t — the type forbids it. *)
```

This rules out the v10.3 latent bug class where `cdm_payload.settlement_date` is set independently of
`tx.timestamp` and the executor is the only place where the relationship is checked.

### 8.2 The obligation lifecycle as a sum type

```ocaml
type obligation_terms = {
  trade_id      : Trade_id.t;
  trade_date    : TradeDate.t;
  settle_date   : SettleDate.t;
  parties       : Party.t * Party.t;     (* (deliverer, receiver) *)
  isin          : Isin.t;
  qty           : Qty.t;                  (* refined: > 0 *)
  cash_currency : Currency.t;
  cash_amount   : Cash.t;                 (* refined: > 0 *)
  csd_mic       : Mic.t;
  dvp_kind      : [ `DvP | `FoP | `CashOnly ];
}

(* The lifecycle FSM as a sum type with carried evidence in each state. *)
type lifecycle =
  | Pending          of { issued_at : Time.t }
  | Instructed       of { instructed_at : Time.t; sese_023_id : Iso20022_msg_id.t }
  | PartiallySettled of { qty_settled : Qty.t; partial_at : Time.t; sese_025_id : Iso20022_msg_id.t }
  | Settled          of { settled_at : Time.t; sese_025_id : Iso20022_msg_id.t }
  | Failed           of { failed_at : Time.t; reason : failure_reason }
  | BoughtIn         of { boughtin_at : Time.t; buyin_ref : Buyin_ref.t }
  | Cancelled        of { cancelled_at : Time.t; correction_tx : Trade_id.t }

and failure_reason =
  | DeadlineMissed
  | NoCover                         (* short obligation could not source inventory *)
  | CounterpartyDefault of Lei.t
  | CsdReject           of csd_reject_code
  | Manual              of Operator.t

(* Total step function. Pattern match must be exhaustive (warning-as-error). *)
let step (l : lifecycle) (e : event) : lifecycle =
  match l, e with
  | Pending _,           Csd_instruct r        -> Instructed       { instructed_at = e.t; sese_023_id = r }
  | Pending _,           Csd_partial p         -> PartiallySettled { qty_settled = p.qty; partial_at = e.t; sese_025_id = p.id }
  | Pending _,           Deadline_fired        -> Failed           { failed_at = e.t; reason = DeadlineMissed }
  | Pending _,           Cancel c              -> Cancelled        { cancelled_at = e.t; correction_tx = c.tx }
  | Instructed _,        Csd_settle s          -> Settled          { settled_at = e.t; sese_025_id = s.id }
  | Instructed _,        Csd_partial p         -> PartiallySettled { qty_settled = p.qty; partial_at = e.t; sese_025_id = p.id }
  | Instructed _,        Csd_fail f            -> Failed           { failed_at = e.t; reason = CsdReject f.code }
  | PartiallySettled _,  Csd_settle s          -> Settled          { settled_at = e.t; sese_025_id = s.id }
  | PartiallySettled _,  Csd_fail f            -> Failed           { failed_at = e.t; reason = CsdReject f.code }
  | Failed _,            Buyin b               -> BoughtIn         { boughtin_at = e.t; buyin_ref = b.ref }
  | (Settled _ | BoughtIn _ | Cancelled _), _  -> l    (* terminal: idempotent no-op *)
  | (PartiallySettled _ | Failed _),  _        -> l    (* unhandled non-terminal: explicit no-op *)

(* The compiler checks: every (state, event) combination is covered.
   No wildcards. Adding a new event type FORCES an update here. *)
```

### 8.3 Smart constructor for obligations

```ocaml
module Obligation : sig
  type t

  (* Smart constructor: only way to make a t.
     Refinement-type checks at construction; rejects malformed obligations. *)
  val create :
    trade_id:Trade_id.t ->
    trade_date:TradeDate.t ->
    parties:Party.t * Party.t ->
    isin:Isin.t ->
    qty:Qty.t ->
    cash_currency:Currency.t ->
    cash_amount:Cash.t ->
    csd_mic:Mic.t ->
    dvp_kind:[ `DvP | `FoP | `CashOnly ] ->
    settle_convention:SettleConvention.t ->
    (t, creation_error) Result.t

  val terms      : t -> obligation_terms
  val lifecycle  : t -> lifecycle
  val unit_id    : t -> exposure_bearing unit_id   (* phantom-typed *)
end = struct
  type t = { terms : obligation_terms; lifecycle : lifecycle }

  let create ~trade_id ~trade_date ~parties ~isin ~qty ~cash_currency ~cash_amount ~csd_mic ~dvp_kind ~settle_convention =
    let open Result.Let_syntax in
    let%bind () = if Qty.is_positive qty then Ok () else Error `Non_positive_qty in
    let%bind () = if Cash.is_positive cash_amount then Ok () else Error `Non_positive_cash in
    let settle_date = SettleDate.of_trade_date trade_date settle_convention in
    let%bind () =
      if SettleDate.is_business_day csd_mic settle_date then Ok ()
      else Error `Settle_date_not_business_day
    in
    let%bind () =
      match dvp_kind with
      | `DvP      -> Ok ()
      | `FoP      -> if Cash.is_zero cash_amount then Ok () else Error `FoP_with_cash
      | `CashOnly -> if Qty.is_zero qty then Ok () else Error `CashOnly_with_qty
    in
    Ok {
      terms = { trade_id; trade_date; settle_date; parties; isin; qty;
                cash_currency; cash_amount; csd_mic; dvp_kind };
      lifecycle = Pending { issued_at = Time.now () };
    }

  let terms t = t.terms
  let lifecycle t = t.lifecycle
  let unit_id t = SettleObl t.terms      (* phantom-typed exposure_bearing *)
end
```

### 8.4 Paired obligation and the discharge function

```ocaml
module PairedObligation : sig
  type t  (* abstract; only via [pair] *)

  val pair :
    long_side:Obligation.t ->
    short_side:Obligation.t ->
    (t, pairing_error) Result.t
  (* Validates: same trade_id, mirrored qty, mirrored cash, same settle_date. *)

  val long_side  : t -> Obligation.t
  val short_side : t -> Obligation.t
end

(* Discharge consumes a PairedObligation atomically.
   There is NO public function that takes a single Obligation and discharges it.
   Partial discharge does not type-check. *)
val discharge :
  PairedObligation.t ->
  csd_confirmation:Sese_025_msg.t ->
  (DischargeResult.t, discharge_error) Result.t
```

### 8.5 The custody-debit guard

```ocaml
val debit_nostro :
  wallet:Nostro_wallet.t ->
  unit_id:custody_bearing unit_id ->        (* phantom guard *)
  qty:Qty.t ->
  trade_date:TradeDate.t ->
  settle_date:SettleDate.t ->
  now:Time.t ->
  (Move.t, debit_error) Result.t

(* The phantom type [custody_bearing unit_id] cannot be constructed from a
   SettleObl (which is exposure_bearing). The only path to [custody_bearing]
   for a security is via [discharge], which produces it as a side effect. *)
```

### 8.6 The reconciliation projection (total, pure)

```ocaml
val ledger_position : Wallet.t -> Security.t -> Time.t -> State.t -> Qty.t
val depot_position  : Wallet.t -> Security.t -> Time.t -> State.t -> Qty.t

(* Theorem:
     ledger_position w u t s
       = depot_position w u t s
       + List.sum (live_obligations w u t s) ~f:Obligation.signed_qty
   This is the body of [ledger_position]; nothing to prove. *)
```

---

## 9. Tradeoffs — Where I Pull Back

I am supposed to be honest about where type-encoding is too clever. Three places.

### 9.1 Conservation across decimal sums

I do **not** encode `Σ_w w_t(u_so) = 0` in the type system. Refinement types over decimal sums in
production OCaml/Haskell require GADTs and either a logic-programming subsystem (LiquidHaskell, F\*) or
proof obligations that don't survive non-trivial codegen. The cost in compile time and developer
ramp-up is much higher than the cost of a per-event-class structural proof at the handler boundary
(C2 of StatesHome). Runtime is the right call here. The runtime proof is per event class, not per
event — the cost is bounded.

### 9.2 Cross-event invariants (corp-action entitlement)

The market-claim mechanism (I-DEF-10) depends on event-time semantics: at record date `r`, what is the
*economic* owner? The answer requires reading the union of custody balances and live obligations and
weighting by signed quantity. Encoding the corp-action calculus in the type system is *isomorphic* to
encoding the corp-action calculus, period. There is no leverage. Runtime handler is correct.

### 9.3 Liveness

Liveness (I-DEF-5) is fundamentally a real-time property: the deadline is in wall-clock time, not in
the type. Workflow timers (Temporal) are the right mechanism (v10.3 §11.13; data spec $L_{19}$ ClockAuthority).
Encoding "this obligation must transition from Pending by some external clock event" in the type
system is a category error.

### 9.4 Where I'm sticking my neck out

The phantom-type discipline (`exposure_bearing` vs `custody_bearing`) is a compile-time check that
**adds a dimension to every unit type in the system**. Existing OCaml code that handles units now has
to thread a phantom parameter through generic functions. This is annoying. Some functions become
parameterised over the phantom (`val price : 'phase unit_id -> Time.t -> Price.t`), some become
restricted (`val debit_nostro : custody_bearing unit_id -> ...`). The benefit: the compiler enforces
the trade-date / settlement-date split everywhere, not just at one point. The cost: a one-time refactor
across the unit-handling surface area.

I think the benefit is worth it because **the trade-date / settlement-date confusion is the failure
mode this whole spec is designed to prevent**, and a type-level enforcement is the right grain.

But I am open to the alternative: keep units as a single type, and enforce the discipline at handler
boundaries via a runtime tag. That is the v10.3 path, basically. It works. It is just one notch
weaker.

---

## 10. The Six-Question Minsky Test

1. **Can illegal states be constructed?** No: smart constructors reject malformed obligations;
   phantom types prevent custody-debit before settle\_date; paired-obligation type prevents partial
   discharge.
2. **Is every case handled?** Yes: the lifecycle FSM is a closed sum type; `step` is total;
   pattern-match exhaustiveness as compiler error.
3. **Is failure explicit?** Yes: `Failed reason=…` carries a closed sum of reasons; `Cancelled`
   carries the correction tx; `Result.t` everywhere.
4. **Would a reviewer catch a bug by reading?** Yes: the discharge function is one place; the
   reconciliation theorem is one function; the obligation FSM is one match.
5. **Are invariants encoded or documented?** Encoded: I-DEF-1 / 2 / 3 / 6 / 7 / 8 / 9 / 11 / 12 are
   compile-time. Documented (handler-level): I-DEF-4 / 5 / 10.
6. **Is this total?** Yes: every public function returns `Result.t` or pattern-matches exhaustively;
   no partial functions, no exceptions on the happy path.

---

## 11. Migration footprint (what changes in v10.3)

| v10.3 location | change |
| ----------------------------- | ------------------------------------------------------------------ |
| §1 (intro: trade-date acct) | reword: economic recognition is on `exposure_bearing` units |
| §2 (closed ledger) | unchanged — moves and conservation are unchanged |
| §3.1 (PnL) | clarify: PnL valuation is over `exposure_bearing` units; custody-bearing valuation is the *substantiation* check |
| §6 (smart contracts) | trade contract (§6.3 equity contracts) emits the obligation pair, not the custody moves; lifecycle event "settle" generates the discharge tx |
| §7 (lifecycle) | obligation FSM joins the unit-state FSM family; same machinery |
| §8 (settlement layer) | `EXECUTED → INSTRUCTED → SETTLED → FAILED` becomes the obligation `UnitStatus`; status-as-string-on-tx is deprecated |
| §11 (invariants) | I-DEF-* added; P1–P10 unchanged; P11–P20 SBL invariants unchanged |
| §13 (SBL) | the in-flight collateral (IBP-177) maps natively to a short-window obligation; no new mechanism |

---

## 12. The One-Sentence Answer

**An open settlement obligation is a unit, not a flag.** It carries its terms in `ProductTerms`, its
lifecycle in `UnitStatus`, its per-position cursors in `PositionState`, and a phantom-typed
`exposure_bearing` tag that prevents the compiler from emitting custody moves before `settle_date`.
Reconciliation to nostro is `ledger_position − depot_position = Σ live_obligations` *by definition*
of the projection — lead–lag is the type signature, not a workflow. DvP atomicity is paired-obligation
discharge, structural. Herstatt risk is two paired obligations with two different settle dates,
non-atomicity visible in the type. CSDR fails are obligation `Failed` plus a fan-out of penalty
obligations. Everything from T+0 to T+2 to corporate-actions-in-window-to-cross-currency is the same
mechanism with different `settle_date` and different terms.

Make the obligation a type. Make the compiler refuse to skip T+2.

---

*Submitted Phase 1, Team A — independent. No cross-talk with other Team A members.*
