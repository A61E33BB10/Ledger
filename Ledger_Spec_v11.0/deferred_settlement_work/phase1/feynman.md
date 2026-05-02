# `deferredSettlement.tex` --- Phase 1 Proposal (FEYNMAN, independent)

**Author role.** FEYNMAN. The discipline: every quantity that matters must be
computable in at least *two* independent ways and the answers must agree. If
they disagree, one of the methods is lying. If they cannot disagree by
construction, then the agreement is a theorem, not a check.

**Question.** How does the Ledger represent the gap between trade-time
economic recognition (T) and settlement-time custody movement (typically T+2,
sometimes T+1, sometimes never if the trade fails)?

The corpus already gives us the bones --- v10.3 §11 settlement layer,
"trade-date accounting" in §11.2, futures `accumulated_cost` in §6, the
six-coordinate GPM in §13, the StatesHome 3-map ruling, the data spec's
$L_{15}$ Obligation FSM. None of these objects, as currently written, owns
the T → T+2 gap *as a first-class concept*. They each touch it. None
*encloses* it. That is what `deferredSettlement.tex` must fix.

The Feynman test before writing a line: *if a stranger asks "what does the
firm own at T+1?", does the spec produce one unambiguous answer, derivable
three different ways?* If not, it has not been understood.

---

## 1. The plain-language story (explain it to a first-year)

You buy 100 shares of XYZ on Monday at \$50. In the cash-equity world, the
*trade* happens Monday (T), but the *custody transfer* happens Wednesday
(T+2). On Tuesday (T+1) the price moves to \$52. Question: *what is your
PnL on Tuesday, before any cash or shares have moved at the custodian?*

Answer: +\$200. Path-Independent PnL Theorem (v10.3 §4.4) demands it, and
common sense agrees --- you bought low, the price went up, you have an
economic claim worth more today than yesterday. That this claim has not yet
*settled* at the CSD is a *custody* fact, not an *economic* fact.

So: **on Monday the firm acquires an economic position; on Wednesday the
firm acquires the corresponding custody position. Between Monday and
Wednesday, the firm holds a *receivable* against the seller (for shares) and
*owes* a deliverable (cash). The sum of (custody position) + (receivable) =
economic position --- always, every day, by construction.**

That is the entire content of deferred settlement. Everything below makes
this idea bulletproof.

---

## 2. State representation --- the unbundling

The naive scalar wallet
$w(u) \in \mathbb{R}$
collapses two distinct things into one number: *what you own economically*
and *what you have in custody*. For futures the corpus already split state
into ledger balance + `accumulated_cost`. For SBL it split into the
six-coordinate GPM `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)`.
Cash equities need the same surgical move applied to the T → T+2 axis.

### 2.1 The minimum extension

I propose **two new coordinates in the GPM, plus a per-trade obligation
record**. The two coordinates are mandatory; the obligation record is
authoritative source.

```
Position vector for a settleable security (extends GPM §13):

    own_settled    -- shares actually credited to depot at the CSD
    own_inflight   -- net of pending receivables (+) and deliverables (-)
                      from trades executed but not yet settled
    onloan, borr, coll_post, coll_recv, coll_rehyp   -- as before

  Definitional identity (the 'avail' analogue for settlement):
    own_economic := own_settled + own_inflight
```

`own_economic` is the *invariant* projection that downstream readers (PnL,
risk, mandate breach checks) consume. `own_settled` is what reconciles to
the custodian. `own_inflight` is the visible, type-safe representation of
the T → T+2 gap.

For cash, the same split:

```
    cash_settled    -- ledger cash that has cleared at the bank
    cash_inflight   -- net of pending cash receivables and payables
                       from unsettled trades
    cash_economic := cash_settled + cash_inflight
```

This is *exactly* the futures `accumulated_cost` pattern (v10.3 §6) applied
to cash equities: an extra explicit-state coordinate that absorbs the
economic-vs-custody divergence so the conservation law and the PnL theorem
both stay clean. **It is the same trick. There is no second trick.** That
is the strongest possible evidence the architecture is right: a problem
that *looks* new turns out to be solved by reusing the existing pattern
with one extra coordinate.

### 2.2 Where the obligation lives --- the Obligation Ledger

`own_inflight` is a *projection*, not a source of truth. Source of truth is
a per-trade record I will call a **PendingSettlement** instance, which fits
naturally into $L_{15}$ Obligation (data spec §3.15) under a new
`SettlementObligation` discharge predicate.

```
type SettlementObligation = {
    obligation_id     : OblId               -- = transaction_id of the trade
    trade_id          : TxId                -- pointer to trade in L_13
    trade_date        : Date                -- T
    intended_settle   : Date                -- T+2 (or T+1 per regime)
    securities_leg    : (ISIN, qty, deliver_party, receive_party)
    cash_leg          : (CCY, amt, payer, receiver)
    settlement_status : EXECUTED | INSTRUCTED | PARTIALLY_SETTLED |
                        SETTLED | FAILED | CANCELLED | BOUGHT_IN
    csdr_penalty_accrued : Decimal          -- 0 until intended_settle+1
    fail_days         : Int                 -- days past intended_settle
    discharge_predicate: ByMatch(sese.025 confirmation matcher)
                        |  ByDeadline(intended_settle + max_extension)
                        |  ByBuyIn(buy_in_outcome)
}
```

This satisfies the `Obligation FSM` of $L_{15}$:
$\textsc{Pending} \to \textsc{Discharged} \mid \textsc{Compensated} \mid
\textsc{Defaulted}$, and reuses the saga-compensation tower for buy-ins.

Three keys, three homes (StatesHome discipline): the *terms* of the
obligation are immutable on creation (`trade_id`, `trade_date`,
`intended_settle`, legs) and live in `ProductTerms`-shaped storage *of the
obligation as a unit*; the *status* (settlement_status, fail_days, accrued
penalty) lives in `UnitStatus`-shaped storage; per-(wallet, trade) state
that some custodial relationship demands lives in `PositionState`. In
practice the obligation is a singleton per trade, so `UnitStatus` carries
the status flags directly.

---

## 3. Move sequence with conservation --- the four canonical timestamps

Buy 100 XYZ at \$50, T+2 regime. The Ledger emits moves at four
timestamps. I write moves as
`(from, to, unit, qty)`; balanced transactions per $L_{13}$.

### 3.1 At T (trade execution)

```
Transaction tau_T (type = SETTLEMENT, settlement_status = EXECUTED):
    Move 1: w_seller_virtual.own_inflight  -= 100   [unit: XYZ]
    Move 2: w_us.own_inflight              += 100   [unit: XYZ]
    Move 3: w_us.cash_inflight             -= 5000  [unit: USD]
    Move 4: w_seller_virtual.cash_inflight += 5000  [unit: USD]

Side-effect: SettlementObligation row created with
    settlement_status = EXECUTED,
    intended_settle = T+2,
    fail_days = 0
```

Conservation per unit, per coordinate:
$\sum_w \Delta\,\text{own\_inflight}(w, \text{XYZ}) = -100 + 100 = 0$
$\sum_w \Delta\,\text{cash\_inflight}(w, \text{USD}) = -5000 + 5000 = 0$

**No move on `own_settled` or `cash_settled` at T.** That is the entire
content of "deferred". The economic position exists in `_inflight`; custody
state is unchanged.

### 3.2 At T+1 (overnight, no settlement event yet)

**Zero moves.** Status update only:
`SettlementObligation.fail_days` stays 0; if `intended_settle` is reached
without confirmation, the field becomes 1 the next day. Price moves to
\$52 and economic PnL of +\$200 *crystallises in the valuation layer*
(v10.3 §4.4, valuation §3) from the position
`own_economic = 0 + 100 = 100`. No ledger move. No cash, no shares.

### 3.3 At T+2$^-$ (just before CSD settlement window opens)

**Zero moves.** State unchanged from T+1, except possibly
`settlement_status: EXECUTED → INSTRUCTED` once the settlement projection
fires (v10.3 §11.7), which is a status update on the obligation, *not* a
ledger move.

### 3.4 At T+2$^+$ (CSD confirms settlement, sese.025 inbound)

This is the only event where custody state moves.

```
Transaction tau_settle (type = SETTLEMENT_CONFIRMATION):
    Move 5: w_us.own_inflight              -= 100    [XYZ]
    Move 6: w_us.own_settled               += 100    [XYZ]
    Move 7: w_seller_virtual.own_inflight  += 100    [XYZ]
    Move 8: w_seller_virtual.own_settled   -= 100    [XYZ]
    Move 9: w_us.cash_inflight             += 5000   [USD]
    Move 10: w_us.cash_settled             -= 5000   [USD]
    Move 11: w_seller_virtual.cash_inflight -= 5000  [USD]
    Move 12: w_seller_virtual.cash_settled  += 5000  [USD]

Side-effect: SettlementObligation.settlement_status = SETTLED.
              The obligation row is retained (monotone carrier, StatesHome C1).
```

Each move touches *one coordinate of one unit per entity* (Single-Coordinate
Move Principle, GPM §13). Each pair is balanced (StatesHome C2). The
transaction is atomic (StatesHome C3). The economic projection is
unchanged through the settlement event:
$\text{own\_economic}(w_{us}, \text{XYZ})$ was $0 + 100 = 100$ before and
is $100 + 0 = 100$ after. **PnL on the settlement day is zero by
construction** --- as it must be, because settlement is a custody event,
not an economic event.

This is the strongest test that the design is right: *the move sequence
that records "the trade settled" produces no PnL*. If it did, we would
have introduced a phantom economic event.

---

## 4. Invariants --- mandatory economic-exposure-at-T

Six invariants are non-negotiable. I label them E1--E6 to keep them
distinct from $\Phi$/$\Lambda$/$P$ numberings already in the corpus; the
final tex will assign canonical numbers.

**E1 (Economic invariance through settlement).**
For every wallet $w$, every unit $u$, and every transaction $\tau$ of type
`SETTLEMENT_CONFIRMATION`,
$$
\Delta\,\text{own\_economic}(w, u) = 0
\quad\text{and}\quad
\Delta\,\text{cash\_economic}(w, u) = 0.
$$
Settlement does not move economic position. Provable by inspection of the
move pattern in §3.4: every `_inflight` decrement is matched by a `_settled`
increment in the same wallet for the same unit.

**E2 (Conservation per coordinate, per unit).**
For every transaction and every coordinate $c \in
\{\text{own\_settled}, \text{own\_inflight}, \text{cash\_settled},
\text{cash\_inflight}\}$,
$$
\sum_{w} \Delta\,c(w, u) = 0.
$$
This is StatesHome C2 lifted to per-coordinate. Proof: handler-level
structural, per event class.

**E3 (Inflight non-residual at terminal status).**
If `SettlementObligation.settlement_status \in \{SETTLED, CANCELLED, BOUGHT_IN\}`,
then the contribution of that obligation to `own_inflight` and
`cash_inflight` of every related wallet is exactly zero. Proof: every
transition out of `EXECUTED|INSTRUCTED|PARTIALLY_SETTLED|FAILED` zeroes the
inflight.

**E4 (Reconciliation identity at settled boundary).**
$\text{own\_settled}(w, u) \;\stackrel{?}{=}\; \text{Custodian depot}(w, u)
\;-\; \text{Custodian inflight}(w, u)$
where the right-hand side is the custodian's *settled-only* view. For our
inflight, the analogous identity:
$\text{own\_inflight}(w, u) \;\stackrel{?}{=}\;
\sum_{o \in \text{open obligations on }(w, u)} \text{signed\_qty}(o)$.

**E5 (Path-independent PnL preserved).**
$V_t = \sum_u \big(\text{own\_settled}(w, u) + \text{own\_inflight}(w, u)\big)
\cdot P_t(u) + \text{cash\_economic terms}$.
The PnL theorem (v10.3 §4.4) holds verbatim with `own_economic` substituted
for `w(u)`. **This is the crucial point: by valuing on the *economic*
projection, we get trade-date accounting for free, and our PnL on T+1 is
+\$200 regardless of whether settlement has occurred.**

**E6 (CSDR penalty additivity).**
$\text{csdr\_penalty\_accrued}(o) = \int_{\text{intended\_settle}}^{t}
\text{rate}(u) \cdot |\text{notional}(o)|\, ds$ (in the discrete daily
form: `rate(u) * |notional| * fail_days`). The *attribution* of the
penalty to a wallet is a single move per accrual period of magnitude
`rate * notional * 1 day` from the failing party's `cash_settled` to the
suffering party's `cash_settled`, recorded as a separate `SETTLEMENT`
transaction. The penalty is *not* an inflight item: it is a settled cash
flow at the moment it is debited.

---

## 5. Reconciliation lead-lag

Two views, three reconciliation pairs.

### 5.1 Trade-date view (internal authoritative)

Computed from $L_{13}$ MoveStream. Reads `own_economic` and `cash_economic`.
Available at T+0 once the executor commits. This is what the firm's risk
engine, mandate-breach checks, and FRTB sensitivities consume.

### 5.2 Settlement-date view (external reconcilable)

Computed from `own_settled` and `cash_settled`. Available T+2 after the
custodian confirms. This is what reconciles bit-for-bit with custodian
statements and CSDR/T2S messages.

### 5.3 Reconciliation pairs (anchoring to data spec §3.6)

| Pair | Internal | External | Cadence | Tolerance |
|---|---|---|---|---|
| RP-1 | `own_settled(w, u)` | Custodian depot daily | T+1 close | 0 |
| RP-2 | `own_inflight(w, u)` | $\sum$ open obligations from CCP/CSD pending instructions | Intraday + T+1 | 0 |
| RP-3 | $\sum_w \text{own\_economic}(w, u)$ | Reconstructed from internal trade blotter | Continuous | 0 |
| RP-4 | `csdr_penalty_accrued(o)` | T2S penalty file | Daily T+1 | 1 cent |

**The lead-lag is explicit.** Trade-date view leads by 0--2 business days.
Reconciliation pair RP-3 is *internal-only* and confirms self-consistency
within the Ledger. RP-1 and RP-2 are the external surfaces. RP-4 closes
the CSDR loop.

---

## 6. CDM cross-walk

| Concept | CDM type | Status |
|---|---|---|
| Trade at T | `BusinessEvent` (Execution) | Direct |
| `SettlementObligation` (terms) | `Trade` + `SettlementTerms` | Direct |
| `SettlementObligation` (state) | `TradeState` (with status enum) | Partial --- CDM has lifecycle states but the EXECUTED→INSTRUCTED→SETTLED enum is implicit, not explicit |
| Settlement confirmation | `BusinessEvent` (Transfer) + sese.025 | Direct via $L_{11}$ ExternalConfirmation |
| Partial settlement | `QuantityChange` on the obligation | Partial |
| Settlement fail | *No CDM equivalent* | **Gap.** Same level as the SBL gaps in v10.3 §13.13 |
| CSDR penalty | *No CDM equivalent* | **Gap.** Track under the ISLA/T2S CDM working item |
| Buy-in | `BusinessEvent` (Termination) plus replacement `Execution` | Partial; the *causal link* is missing |

The structural alignment is clean for happy-path. The gaps are the
fail/penalty/buy-in surface, which is a regulatory-domain hole, not a
design fault on our side.

---

## 7. Failure modes (the adversarial column)

I enumerate the failure modes I would attack a competing proposal with.
Each must have a forced answer.

### 7.1 Fail (CSDR settlement fail)

Day T+2 the CSD reports DELN ("delivery not received"). Status:
`EXECUTED → FAILED`. No moves on `_settled`. `_inflight` stays. Daily
penalty accrual (E6) starts T+3. The economic position is unchanged --- this
is correct (we own the shares economically; we just don't have them in
custody).

### 7.2 Partial settlement

CSD settles 60 of 100 at T+2; 40 fail.

```
Transaction tau_partial (settlement_status = PARTIALLY_SETTLED):
    own_inflight w_us  -=  60
    own_settled  w_us  +=  60
    cash_inflight w_us +=  3000   (60 * 50)
    cash_settled  w_us -=  3000
    + mirror moves on w_seller_virtual
    + new SettlementObligation residual for the 40 (or status update of
      the original to PARTIALLY_SETTLED with reduced quantities).
```
Conservation per coordinate per unit, fine. E1 holds (economic unchanged).

### 7.3 Recall on a stock-loan position bought-in via short cover

Composition with §13: if the unsettled buy is what would have been used to
return a recalled loan, the recall's deadline drives a buy-in obligation
that itself must settle T+2. Two settlement obligations, *both* visible in
`own_inflight`, neither double-counted because the obligation-id is the
key. The $L_{15}$ obligation FSM handles the dependency through the
saga-compensation tower (data spec §3.15).

### 7.4 Corporate action on an unsettled position

XYZ goes ex-dividend at T+1 with record date = T+1. The *economic owner* on
record date is the buyer (because they have economic exposure under
trade-date accounting). The *settled holder* at the CSD on record date is
the seller (because settlement has not happened). The CSD pays the dividend
to the seller; the seller is contractually obliged to remit it as a
*manufactured dividend* (v10.3 §13.4) to the buyer.

The Ledger handles this without surprise: it records two cash moves --- the
seller receives the dividend on `cash_settled`, and a manufactured-dividend
obligation is created from seller to buyer with `intended_settle` per the
market convention. The economic position of the buyer is correct
throughout: `own_economic = 100`, so the dividend accrual at the valuation
layer says they earn the dividend; the manufactured payment delivers it.

This is exactly the corporate-action pattern from §13.5; no new mechanism
needed. **This is the second strong test the design is right: a
deferred-settlement-corporate-action interaction reuses an existing
mechanism without modification.**

### 7.5 Cross-currency / Herstatt

The two cash legs settle in different time zones. Here the GPM split is
not enough; we need a *per-leg* `settled` flag on the obligation. I split
the cash leg into `cash_inflight_leg_A`, `cash_inflight_leg_B`. The
`SettlementObligation` carries two `intended_settle` timestamps. v10.3
§2.6 already names Herstatt as a "real-world timing risk that no ledger
design can eliminate, only represent and monitor". Our representation:
two confirmation events, two state transitions, an explicit window where
one leg is settled and the other is inflight. The `cash_economic` of each
counterparty is unchanged through the cross --- E1 still holds.

### 7.6 DvP atomicity

This is settlement-layer atomicity (v10.3 §11.5), not Ledger atomicity.
Our representation: at T+2$^+$ we receive *one* sese.025 message that
confirms both legs simultaneously (DvP via the CSD); we emit *one*
balanced transaction $\tau_{settle}$ with *all eight moves* (§3.4). If
DvP fails partway --- e.g., shares delivered, cash blocked --- we receive a
sese.024 status indicating partial failure and the obligation goes
`PARTIALLY_SETTLED`. The Ledger's atomicity guarantee is for the message
processing, not the underlying CSD mechanics.

### 7.7 Cancellation / unwind before settlement

`EXECUTED → CANCELLED` (e.g., trade error). Inflight moves reversed by a
compensating transaction (a `CORRECTION` per v10.3 §11.4). The obligation
row is retained at `CANCELLED` (StatesHome C1 monotone carrier) for audit.

### 7.8 Re-instruction after fail

`FAILED → INSTRUCTED` after operations resubmits or executes a buy-in. No
ledger moves; status update only.

---

## 8. Worked example (the spec's load-bearing test)

Buy 100 XYZ on Monday at \$50. Tuesday price = \$52. Wednesday settles
clean.

I will compute three things --- (a) the firm's economic position on Tuesday
afternoon, (b) PnL Mon→Tue, (c) the moves on Wednesday --- in **three
different ways** and confirm they agree.

### 8.1 PnL on T+1 (\$200) computed three ways

**Method M1: move-by-move ledger trace.**
Replay $L_{13}$. Moves through Monday end:
- `w_us.own_inflight(XYZ)` = +100
- `w_us.cash_inflight(USD)` = $-5000$
- `w_us.own_settled(XYZ)` = 0; `w_us.cash_settled(USD)` = (initial, say) 1{,}000{,}000

$V_{T} = (0 + 100 \cdot 50)\,\text{XYZ value} + (1{,}000{,}000 - 5{,}000)\,\text{cash} = 5000 + 995000 = 1{,}000{,}000$.

$V_{T+1} = (0 + 100 \cdot 52) + (1{,}000{,}000 - 5{,}000) = 5200 + 995000 = 1{,}000{,}200$.

PnL = $1{,}000{,}200 - 1{,}000{,}000 = +200$. ✓

**Method M2: cumulative balance summation, restricted to positions that
moved.**
Initial holdings: 0 XYZ, \$1{,}000{,}000.
After T: 100 XYZ economically, \$995{,}000 cash economically (5{,}000 inflight).
$V_T = 100 \cdot 50 + 995{,}000 + (-5{,}000) = 5000 + 995000 - 5000 + 5000 = 1{,}000{,}000$.
[Cleaner form: `cash_economic = cash_settled + cash_inflight = 1{,}000{,}000 + (-5{,}000) = 995{,}000`; `own_economic = own_settled + own_inflight = 0 + 100 = 100`. $V_T = 100 \cdot 50 + 995{,}000 = 1{,}000{,}000$.]
$V_{T+1} = 100 \cdot 52 + 995{,}000 = 1{,}000{,}200$.
PnL = +200. ✓

**Method M3: trade-date accounting view (open the trade record directly).**
Trade blotter says: bought 100 at 50, current mark 52, no other trades.
Mark-to-market PnL = $100 \cdot (52 - 50) = +200$. ✓

**Method M4 (sanity): the settlement-date accounting view.**
At T+1, no shares have settled, no cash has moved. *Naive* settlement-date
view says PnL = 0. **This disagrees with M1, M2, M3.** The disagreement
is the entire reason we need the design: settlement-date accounting *is
the wrong economic story for trading book PnL*. The Ledger uses
trade-date accounting (v10.3 §1.1, Property 5) and the inflight
coordinates make it explicit. M4 *should* disagree --- and the disagreement
is exactly the receivable/payable book that sits in `_inflight`.

### 8.2 Position at T+2$^-$, three ways

**P1: from wallet structure (`own_economic = own_settled + own_inflight`).**
$0 + 100 = 100$.

**P2: from the trade record alone.**
Sum of signed quantities in $L_{13}$ moves filtered on XYZ to $w_{us}$:
$+100$ (one move). Total = 100.

**P3: from the obligation register.**
One open `SettlementObligation` with `signed_qty = +100`. Sum = 100.

All three agree. ✓ This is E4 of §4.

### 8.3 Moves on T+2$^+$ (no economic move; only custody)

Eight moves of §3.4 fire. Verification:
- Conservation per coordinate per unit: trivial pair-cancellation.
- $\Delta\,\text{own\_economic}(w_{us}, \text{XYZ}) = -100 + 100 = 0$. ✓ (E1)
- $\Delta\,V = 0$. (Settlement is a custody event.)
- PnL on T+2 = $V_{T+2} - V_{T+1+}$ which equals the price change
  $100 \cdot (P_{T+2} - P_{T+1})$ alone --- the settlement contributes
  nothing.

### 8.4 The fail variant (forward and backward pricing of the receivable)

Suppose at T+2 the CSD reports DELN. Status `EXECUTED → FAILED`.

**Forward pricing of the receivable.** The 100 XYZ receivable on
Wednesday morning, valued at $P_{T+2} = 53$, is worth $100 \cdot 53 =
5300$. Less the obligation to pay 5{,}000 cash → net receivable value
\$300. This already sits in `own_economic - own_settled = 100$ shares + $-5000$ inflight cash, which marked is $100 \cdot 53 - 5000 = 300$. ✓

**Backward pricing.** The receivable was *worth* 0 at $T$ (priced at the
trade price by definition of the trade) and will be worth `current_value -
0 = +300` at $T+2$ if nothing else changes. The cumulative PnL from $T$
to $T+2$ on this receivable is therefore $+300$, which equals the sum of
daily mark-to-market increments $100 \cdot (\Delta P)$ over the two days.
The fail does not break this; it just keeps the receivable open.

**Carrying cost of a fail.** Under E6, daily CSDR penalty starts $T+3$ at,
say, 1 bp on notional: $0.0001 \cdot 5000 = 0.50$ per day, debited from
seller's `cash_settled` to buyer's `cash_settled`. Forward and backward
pricings agree: the buyer's net economic position is improved by the
penalty stream while the fail persists; the seller's is worsened by an
exactly offsetting amount. Conservation. ✓

---

## 9. Internal contradictions found in the corpus

I owe the reviewer a list. Each is small; each must be resolved by
`deferredSettlement.tex`.

**C-1 (v10.3 §11.6).** "If settlement fails (counterparty cannot deliver),
the Ledger records a settlement failure event. The economic position is
*not* automatically reversed --- the exposure remains until the failure is
resolved." This is correct, but the same section never tells us where the
economic position *lives* during the gap. In the current scalar model
$w(u)$ holds it implicitly --- but $w(u)$ is also used by the GL view, which
is wrong (GL view should see settled state). The contradiction is small
but real: one number is being asked to do two jobs. Our split fixes it.

**C-2 (v10.3 §11.7 confirmation lifecycle).** The status enum
`EXECUTED → INSTRUCTED → SETTLED|FAILED` is described as a *transaction
status*. It is in fact a per-obligation status: a single trade with
partial settlement enters `PARTIALLY_SETTLED` for *the residual obligation*,
not for the original transaction (which is immutable in $L_{13}$). The
data spec correctly puts the FSM under $L_{15}$ Obligation; v10.3 mixes
the levels. `deferredSettlement.tex` must say: the FSM is per-obligation,
not per-transaction.

**C-3 (StatesHome conservation and inflight).** StatesHome §2.4 declares
$\sum_w \text{accumulated\_cost}(w, u) = 0$ structural. The *inflight*
coordinates need the *same* declaration extended; otherwise the architecture
allows non-conservative inflight which would break E2. This is
mechanical to add, but it is not currently said anywhere and an
adversarial reviewer would catch it.

**C-4 (data spec $L_6$ "for non-lendable units the vector degenerates to a
scalar").** Cash equities are non-lendable in many books, so the
degenerate-scalar phrasing strictly applied would forbid the
inflight/settled split. Resolution: the GPM extension I propose is
*orthogonal* to lendability. Every settleable unit carries the
`(_settled, _inflight)` axis regardless of whether it carries the SBL
6-vector. The data spec wording needs an amendment in $L_6$ to make this
explicit.

**C-5 (v10.3 §1.1 vs §11.5 on DvP atomicity).** §1.1 asserts atomicity by
construction. §11.5 correctly notes settlement-level DvP depends on CSD
infrastructure outside our control. No actual contradiction once you read
both; but `deferredSettlement.tex` must be careful to repeat the
distinction --- ledger-level atomicity is structural, settlement-level
atomicity is contingent on the CSD.

---

## 10. Multi-representation discipline summary (FEYNMAN test)

For each load-bearing claim of the proposal I want at least *two
independent computational paths to the same answer*. Here they are
inventoried.

| Claim | Path A | Path B | Path C |
|---|---|---|---|
| PnL on T+1 = +\$200 | Move-by-move replay of $L_{13}$ + valuation | Wallet projection `own_economic * P` | Trade blotter MtM |
| Position at T+2$^-$ = 100 XYZ | `own_settled + own_inflight` | Sum of $L_{13}$ XYZ moves to wallet | Sum over open `SettlementObligation` |
| Settlement at T+2$^+$ produces no PnL | Eight-move pattern preserves `own_economic` | Valuation engine sees no projection change | Trade blotter has no new entry |
| Fail at T+3 carrying cost | E6 penalty rule | Forward priced as discounted obligation | Backward priced as cumulative MtM increments |
| Conservation per coordinate | StatesHome C2 (handler-level structural) | $\sum_w \Delta c(w,u) = 0$ inspection | Property test enumeration over CDM event types |
| Ownership at T+1 (the stranger's question) | `own_economic = own_settled + own_inflight = 100` from wallet | 1 open obligation in $L_{15}$ for +100 | Trade record in $L_{13}$ for +100 |

If any row has its three paths disagree, the spec is wrong and the design
must change. Right now they all agree. The agreement is the proof.

---

## 11. The one-paragraph answer to "what does the firm own at T+1?"

> The firm owns 100 shares of XYZ economically and is short \$5{,}000 USD
> economically. Custody-wise, the shares have not yet arrived and the
> cash has not yet left. The Ledger represents this as `own_settled = 0`,
> `own_inflight = +100`, `cash_settled = 1{,}000{,}000` (unchanged),
> `cash_inflight = -5{,}000`. The economic projection
> `own_economic = own_settled + own_inflight` reads 100, which is what
> drives valuation, PnL, risk, and mandate breach checks. The settled
> projection reads 0, which is what reconciles to the custodian. There is
> a single `SettlementObligation` row in $L_{15}$ with status `EXECUTED`
> and `intended_settle = T+2`, which discharges to `SETTLED` on confirmation
> and is the source-of-truth for the inflight projection. Three views
> (wallet structure, trade record, obligation register) compute the same
> 100 shares. The Ledger has one answer, and it has it three times.

---

## 12. Open questions I would push to Phase 2

1. **Per-coordinate naming convention.** I used `_settled` / `_inflight`.
   The corpus might prefer `_custody` / `_economic_minus_custody` for
   strict consistency with the `own_economic` projection name. Phase 2
   gate.

2. **Cash inflight aggregation.** Should we aggregate `cash_inflight`
   per (wallet, currency) or per (wallet, currency, obligation_id)? The
   former is cheaper; the latter is auditable per-trade. I suggest
   per-(wallet, currency) at the wallet level, with the obligation register
   carrying the per-trade granularity. This matches the trade-date
   accounting books many real systems run.

3. **Interaction with the Generalised Position Model.** If a unit is
   *also* lendable, it now carries
   `(own_settled, own_inflight, onloan, borr, coll_post, coll_recv,
   coll_rehyp)` --- seven coordinates. Phase 2 must verify the
   Single-Coordinate Move Principle still holds across all SBL events
   *and* settlement events without conflict.

4. **CSDR penalty mechanics in CDM.** Coordinate with $L_{17}$
   RegulatorySubmission and the ISLA CDM working group to either close the
   gap or document a Ledger-native extension.

5. **Continuous-time / intraday settlement (T+0, T+1).** The model
   handles arbitrary `intended_settle` per the obligation. Validate that
   T+0 markets (some FX, some futures variation) collapse cleanly to
   `_inflight = 0` at all times --- they should, because trade and
   settlement are simultaneous.

6. **Real-time gross settlement (RTGS) on the cash leg.** Where the cash
   leg settles RTGS through TARGET2/Fedwire and the securities leg
   settles T+2 at the CSD, we have *intra-trade* asynchronicity. The
   per-leg confirmation pattern of §7.5 covers this mechanically.

---

*End of Phase 1 proposal --- FEYNMAN, independent.*
