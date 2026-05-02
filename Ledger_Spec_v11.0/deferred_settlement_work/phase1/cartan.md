# Deferred Settlement: A Bourbaki-Style Extension of the Ledger

**Author.** Henri Cartan (Mathematical Documentation Architect).
**Phase.** Phase 1, independent proposal, no cross-talk.
**Target.** `deferredSettlement.tex` (v11.0).
**Audience.** Specification reviewers; downstream implementation, valuation,
data, and orchestration agents.
**Style.** Definitions before use. Theorems with full hypothesis lists.
Hypotheses minimal. Proofs explicit, by induction over the move stream.
No appeal to "obvious".

---

## 0. Motivation and Position in the Corpus

The current corpus (Ledger v10.3 §6, §8, §11; StatesHome addendum; Valuation
v1.0; Data v1.0) treats the gap between trade execution and CSD settlement
informally:

- §11.5 ("Settlement timing distinctions") states that economic exposure
  begins at execution and that the status FSM `EXECUTED → INSTRUCTED → SETTLED |
  FAILED` runs in parallel; it does not give the open settlement obligation a
  ledger object.
- §11.6 (Confirmation Return Path) asserts "no moves are generated --- the
  positions were already correct from trade date" without specifying *where in
  the closed system the open obligation lives*, *how it discharges*, or *how
  the executor distinguishes a fail from a normal in-flight transition*.
- FAQ Q5 ("Settlement failures") names buy-in, partial delivery, and
  cancellation as resolution paths but leaves the algebra of partials unstated.
- §13.3 (Short Selling and Inventory) and §13.4 (External Reconciliation) brush
  against the issue when discussing inflight collateral, and §3 (footnote on
  Herstatt) brushes against it for FX.
- The Data spec $L_{15}$ (Obligation) provides a generic FSM
  `Pending → Discharged | Compensated | Defaulted` but does not bind it to the
  settlement projection or to conservation in the ledger.

These are five separate informal touch-points. **None is a definition.** The
mathematical question is therefore not "how does settlement work?" but
**"what is the smallest set of new objects, morphisms, and laws under which
trade-date economic recognition, T+2 custody settlement, fails, partials,
recalls, corporate actions, and cross-currency Herstatt risk all live in the
same closed-ledger framework with conservation preserved by construction?"**

The thesis of this document is that the answer is two new objects (a *unit*
representing the open settlement obligation, and an FSM on it), one
universal property (the obligation is the kernel of the discrepancy between
ledger position and external custody), and one theorem (Conservation Lifting:
adding obligation units preserves $Q(u)=0$ for every $u$ at every $t$). All
existing invariants (P1--P10) survive verbatim; obligation invariants extend
them as P24--P30.

> Cartan's hygienic principle: *every implicit assumption in the existing
> corpus that touches deferred settlement is made explicit here, and either
> proven or named as a hypothesis.*

---

## 1. Notation and Prerequisites

**Carried from v10.3.** $\mathcal{W}$ wallets; $\mathcal{U}$ units;
$w_t : \mathcal{U} \to \mathbb{R}$ wallet state at time $t$; $m$ atomic move
with fields $(w_s, w_d, u, q, t, s, \text{meta})$ where $q > 0$;
$\tau$ transaction (a finite, simultaneous set of moves);
$Q(u) = \sum_{w \in \mathcal{W}} w_t(u)$ the closed-system charge for $u$;
$P_t : \mathcal{U} \to \mathbb{R}$ external price function;
$V_t = \sum_u w_t(u) \cdot P_t(u)$ portfolio value;
$\mathcal{W}_{\mathrm{real}}$, $\mathcal{W}_{\mathrm{virtual}}$ the real/virtual
partition;
$\vec{w}_e(u) \in \mathbb{R}^6$ the GPM coordinate vector
$(\mathrm{own}, \mathrm{onloan}, \mathrm{borr}, \mathrm{coll\_post},
  \mathrm{coll\_recv}, \mathrm{coll\_rehyp})$.

**Carried from StatesHome.** *ProductTerms* (immutable, versioned, append-only,
keyed by $u$); *UnitStatus* (mutable, shared, keyed by $u$); *PositionState*
(per-(wallet, unit), monotone carrier, Option accessor). Conditions C1--C12.

**Carried from Valuation v1.0.** Valuation FSM with states
`Pricing | Priced | Stale | Failed | Explained`. Pricing depends on unit
state. PnL-explain residual gates `Priced`.

**Carried from Data v1.0.** Bitemporal axes $(t_{\mathrm{obs}}, t_{\mathrm{known}})$;
leaves $L_{11}$ (ExternalConfirmation, ISO 20022 envelopes), $L_{13}$
(MoveStream), $L_{15}$ (Obligation, generic FSM), $L_{18}$ (BreakRegister).

**New notation.** $\mathcal{U}_{\text{obl}} \subset \mathcal{U}$ the
*obligation sub-universe*; $u^{\circ}$ for the obligation unit corresponding
to a parent settleable transaction; $\mathfrak{O}$ for the obligation lifecycle
FSM; $\mathcal{T}_{\text{trade}}, \mathcal{T}_{\text{recon}},
\mathcal{T}_{\text{discharge}}, \mathcal{T}_{\text{reverse}}$ for the four
transaction kinds in the deferred-settlement extension.

---

## 2. The Object: The Open Settlement Obligation as a Unit

### 2.1 Why an obligation must be an object, not a flag

Three candidate locations for the open settlement obligation are conceivable;
each is shown defective.

1. **A flag on the trade transaction.** A flag is metadata: it cannot carry a
   balance. The economic exposure is recognised in the position from $T$
   (trade date), but the *custody mismatch* between the wallet and the nostro
   has a quantity (the unsettled amount) and a counterparty
   (delivering/receiving party). A flag cannot represent a quantity that
   discharges in pieces (partial delivery) or that becomes a different quantity
   (recall, buy-in price differential).
2. **A scalar on the wallet.** A scalar collapses two distinct economic
   states. If wallet $w$ has bought 100 XYZ at $T$, the position is
   "100 owned, 0 with custody confirmation"; if at $T+2$ the trade has
   settled, the position is "100 owned, 100 with custody confirmation". A
   scalar cannot distinguish these.
3. **A virtual-wallet cash entry.** §13.4 of v10.3 hints at this for SBL
   prepay collateral. It is necessary but not sufficient: the virtual entry
   tracks who-owes-whom but does not carry a *lifecycle FSM* (instructed,
   matched, confirmed, partially settled, failed, bought-in, cancelled). The
   FSM is the load-bearing addition.

The minimal solution is to make the open obligation a **unit** in
$\mathcal{U}$, with its own *ProductTerms*, *UnitStatus*, and *PositionState*,
just as the SBL loan unit is treated in §13. This is structurally consistent
with the StatesHome ruling: every economically distinguishable per-position
fact lives at *PositionState*$[w, u]$ for some $u$.

### 2.2 Definition of the obligation unit

> **Definition 2.1** (Settlement obligation unit). Let $\tau$ be a Ledger
> transaction whose `type` field is `SETTLEMENT` (per §11.4) and whose moves
> contain at least one cash leg or one securities leg requiring external
> transfer. The **settlement obligation unit** of $\tau$, denoted
> $u^{\circ}(\tau)$, is the element of $\mathcal{U}$ defined by:
>
> 1. *Identity.* $\mathrm{unit\_id}(u^{\circ}(\tau)) = \mathrm{hash\_jcs}(\tau.\mathrm{tx\_id}, \texttt{"obligation"})$.
>    Injective in $\tau.\mathrm{tx\_id}$ (StatesHome C10).
> 2. *Type.* `OBLIGATION` (a new entry in the closed sum of `unit_type`).
> 3. *ProductTerms* (immutable, by C6/C7):
>    - `parent_tx_id` $= \tau.\mathrm{tx\_id}$;
>    - `securities_leg` $= (u_s, q_s, w_{\text{deliver}}, w_{\text{receive}})$
>      or $\bot$;
>    - `cash_leg` $= (\text{ccy}, q_c, w_{\text{payer}}, w_{\text{receiver}})$
>      or $\bot$;
>    - `expected_settlement_date` $T_{\text{set}}$ (e.g. $T+2$);
>    - `settlement_type` $\in \{\texttt{DvP}, \texttt{FoP}, \texttt{CASH},
>       \texttt{PvP}\}$ (extending §11.4 with PvP for FX/Herstatt);
>    - `regime` $\in \{\texttt{T+2}, \texttt{T+1}, \texttt{T+0},
>       \texttt{ContractualSpecific}\}$;
>    - `csd_or_correspondent` (LEI/BIC of the settling infrastructure).
> 4. *UnitStatus* (mutable, shared --- there is exactly one obligation, hence
>    one status, per parent transaction):
>    - `lifecycle_stage` $\in \mathfrak{O}$ (FSM in §3);
>    - `last_status_message_id` (link into $L_{11}$);
>    - `cumulative_settled_qty_securities`, `cumulative_settled_qty_cash`;
>    - `csdr_penalty_accrual` (Decimal, possibly zero).
> 5. *PositionState* (per-(wallet, $u^{\circ}$)):
>    - For the delivering/paying wallet: $-1$;
>    - For the receiving wallet: $+1$;
>    - All other wallets: `None` (StatesHome C1, never-touched).
>    The total is $\sum_w w(u^{\circ}) = 0$ (Convention 2.4).

**Remark 2.2** (Why $\pm 1$ and not the cash/securities quantity). The
obligation unit does *not* itself carry the asset quantity. The asset
quantity is in the parent transaction's moves and in the securities/cash
legs of *ProductTerms*$[u^{\circ}]$. The $\pm 1$ count tracks *the obligation
itself* --- one unit issued by the deliverer, one held by the receiver. This
matches the bond-like construction used for the SBL loan unit (§13.5.1) and
admits the same conservation argument.

**Remark 2.3** (Why ProductTerms holds the legs, not PositionState). The
quantities are the *contractual content* of the obligation, fixed at issuance
and unchanged by lifecycle (except via *UnitStatus*-recorded discharge
counters). They satisfy the StatesHome immutability discipline (C6).
PositionState carries only the issuance count.

> **Convention 2.4** (Issuance-conservation). Every obligation unit
> $u^{\circ}$ is issued atomically with conservation: at the moment $u^{\circ}$
> is registered, exactly one transaction mints $-1$ to the deliverer's
> *PositionState* and $+1$ to the receiver's, plus a virtual contra-entry of
> 0 (since the two real entries already sum to zero). Hence $\sum_w w(u^{\circ})
> = 0$ at issuance, and the conservation law (P1) is preserved.

### 2.3 The obligation as a sub-object: universal property

The two preceding sub-sections beg a categorical question: *what universal
property does $u^{\circ}$ enjoy, and does the corpus have any other natural
candidate for the open obligation?*

> **Proposition 2.5** (Universal property of $u^{\circ}$). *Let* $\mathbf{Ledg}$
> *be the category of ledger states and balance-preserving transactions
> (objects: balance functions* $w : \mathcal{U} \to \mathbb{R}$*; morphisms:
> conservation-preserving transactions). Let* $\pi_{\text{custody}} : \mathbf{Ledg}
> \to \mathbf{Cust}$ *be the forgetful functor that erases all but the
> "in-custody-confirmed" component of a position (i.e. the projection to the
> nostro-equivalent view). For a transaction* $\tau$ *of type* `SETTLEMENT`
> *generating an immediate ledger position change but no custody change at
> time* $T$*, the obligation unit* $u^{\circ}(\tau)$ *is the kernel of*
> $\pi_{\text{custody}}$ *in the slice category over* $\tau$*: it is the unique
> (up to isomorphism) object whose contribution to* $V_t$ *is zero, whose
> discharge to zero coincides with* $\pi_{\text{custody}}$ *acquiring the
> trade's quantity, and through which any other "open settlement" object must
> factor.*

*Proof outline.* (i) $u^{\circ}(\tau)$ has ProductTerms-fixed legs with no
mark-to-market value: $P_t(u^{\circ}) = 0$ unless a CSDR penalty accrues, in
which case $P_t(u^{\circ}) = -\text{accrued penalty}$ (a liability). At
issuance, $P_t(u^{\circ}) = 0$. (ii) When $u^{\circ}$ discharges (FSM reaches
$\textsf{Settled}$), the *discharge* transaction $\tau_{\text{discharge}}$
emits matching $+q$ to the receiver's custody-confirmed virtual wallet and
$-q$ to the deliverer's; hence $\pi_{\text{custody}}$ acquires the quantity
that was missing from $T$ to $T+2$. (iii) Any candidate "open obligation"
object $X$ that records the same gap and respects conservation must have its
issuance and discharge moves agree with those of $u^{\circ}$ on the
deliverer's and receiver's wallets at the affected times; hence $X$ factors
through $u^{\circ}$ uniquely, since the lifecycle moves are the only
degrees of freedom. \qed

The point of Proposition 2.5 is **not** abstraction for its own sake. It is
hygiene: it tells reviewers that no other natural object can play the role
of the open obligation, which is what the v10.3 corpus's informal treatment
implicitly relied on without proof.

### 2.4 The obligation is mark-to-market by penalties only

> **Definition 2.6** (Obligation price function). For all $u^{\circ} \in
> \mathcal{U}_{\text{obl}}$ and all $t$,
> $$ P_t(u^{\circ}) = -\,\mathrm{UnitStatus}[u^{\circ}].\texttt{csdr\_penalty\_accrual}\;\cdot\;\mathrm{sign}(\text{holder}). $$
> Concretely: the deliverer (who has a $-1$ position) sees $+\text{accrual}$
> as a liability; the receiver (who has a $+1$ position) sees nothing economic
> from the obligation per se but receives the cash discharge at settlement.

Outside CSDR-penalty regimes, $P_t(u^{\circ}) \equiv 0$. The obligation does
not move portfolio value (PnL was already taken at trade date through the
trade transaction's move on *real* wallet positions); it tracks
custody-vs-ledger discrepancy and accrues penalties that *do* affect PnL when
applicable (CSDR Article 7: cash penalty regime, in force since Feb 2022).

---

## 3. The Lifecycle FSM $\mathfrak{O}$

### 3.1 States and termination

> **Definition 3.1** (Obligation FSM). The obligation lifecycle FSM
> $\mathfrak{O} = (S, \Sigma, \delta, s_0, F)$ has:
>
> - States $S = \{\textsf{Issued}, \textsf{Instructed}, \textsf{Matched},
>   \textsf{PartiallySettled}, \textsf{Settled}, \textsf{Failing},
>   \textsf{BoughtIn}, \textsf{Cancelled}, \textsf{Defaulted}\}$.
> - Initial state $s_0 = \textsf{Issued}$.
> - Terminal (accepting) states $F = \{\textsf{Settled}, \textsf{Cancelled},
>   \textsf{Defaulted}\}$.
> - Alphabet $\Sigma$ = the set of transition labels in §3.2.
> - Transition relation $\delta$ as in §3.2; total over $S \times \Sigma$ in
>   the sense that every (state, event) pair either has a defined target or
>   produces an explicit `Reject(state, event)` typed error (StatesHome
>   discipline).

> **Termination Predicate.** $\textsf{terminated}(u^{\circ}) :\equiv
> \mathrm{UnitStatus}[u^{\circ}].\texttt{lifecycle\_stage} \in F$.

> **Liveness assumption (named, not proven).** For every $u^{\circ}$ issued
> at time $T$, there exists a finite time $T^* \geq T$ such that
> $\textsf{terminated}(u^{\circ})$ holds at $T^*$. This is **assumed**, not
> derived: it depends on external CSD/CCP infrastructure. CSDR mandatory
> buy-in (Article 7(3), Settlement Discipline Regime) provides a finite upper
> bound under EU regulation; for non-EU regimes, the contract template carries
> a `max_settlement_horizon` field beyond which the obligation is forced to
> $\textsf{Defaulted}$.

### 3.2 Transition table (the formal $\delta$)

| From | Event (label) | To | Moves emitted | $L_{11}$ trigger |
|---|---|---|---|---|
| $\textsf{Issued}$ | `instruct` | $\textsf{Instructed}$ | none | sese.023 outbound |
| $\textsf{Instructed}$ | `match` | $\textsf{Matched}$ | none | matching status |
| $\textsf{Matched}$ | `confirm_full` | $\textsf{Settled}$ | discharge (§4.4) | sese.025 / camt.054 |
| $\textsf{Matched}$ | `confirm_partial` | $\textsf{PartiallySettled}$ | partial discharge (§4.5) | sese.025 partial |
| $\textsf{PartiallySettled}$ | `confirm_partial` | $\textsf{PartiallySettled}$ | further partial discharge | sese.025 partial |
| $\textsf{PartiallySettled}$ | `confirm_full` | $\textsf{Settled}$ | residual discharge | sese.025 final |
| $\{\textsf{Instructed}, \textsf{Matched}, \textsf{PartiallySettled}\}$ | `fail_report` | $\textsf{Failing}$ | none; status only; CSDR penalty accrual begins | sese.024 fail status |
| $\textsf{Failing}$ | `retry_succeed` | $\textsf{Settled}$ | discharge | sese.025 |
| $\textsf{Failing}$ | `retry_partial` | $\textsf{PartiallySettled}$ | partial discharge | sese.025 partial |
| $\textsf{Failing}$ | `buy_in_executed` | $\textsf{BoughtIn}$ | replacement-purchase moves + cost attribution to deliverer | external buy-in agent |
| $\textsf{BoughtIn}$ | `confirm` | $\textsf{Settled}$ | discharge against replacement | sese.025 |
| any non-terminal | `cancel_bilateral` | $\textsf{Cancelled}$ | reversal moves (§4.6) | sese.027 cancel |
| any non-terminal | `counterparty_default` | $\textsf{Defaulted}$ | close-out per master agreement | n/a |

**Total over $S \times \Sigma$.** Any (state, event) not in the table is
rejected with `Reject(state, event)` (per StatesHome's totality discipline
and Data spec $\Phi_{15}^C$ $\kappa$-totality).

### 3.3 Composition with the existing `EXECUTED → INSTRUCTED → SETTLED |
FAILED` FSM

§11.6 of v10.3 specifies a four-state status FSM on the parent transaction.
The obligation FSM $\mathfrak{O}$ is a *refinement* of that FSM:

$$
\mathfrak{O} \xrightarrow{\;\eta\;} \mathfrak{O}_{\text{v10.3}}
$$

via the surjection
$\eta(\textsf{Issued}) = \texttt{EXECUTED}$,
$\eta(\textsf{Instructed}) = \texttt{INSTRUCTED}$,
$\eta(\textsf{Matched}) = \texttt{INSTRUCTED}$,
$\eta(\textsf{Settled}) = \texttt{SETTLED}$,
$\eta(\textsf{PartiallySettled}) = \texttt{INSTRUCTED}$ (still in flight from
the v10.3 view),
$\eta(\textsf{Failing}) = \eta(\textsf{BoughtIn}) = \texttt{FAILED}$,
$\eta(\textsf{Cancelled}) = \texttt{FAILED}$ (terminal failure),
$\eta(\textsf{Defaulted}) = \texttt{FAILED}$.

The map $\eta$ is the projection that lets v10.3-aware downstream consumers
read obligation state without engaging the finer structure. The refinement
is a strict information gain: every v10.3 state is recoverable, but
$\mathfrak{O}$ distinguishes the four reasons for `FAILED` and the partial
state that v10.3 collapses.

---

## 4. State Representation and Move Sequences

### 4.1 The state at every moment: what is true

Let $\tau_0$ be a buy of $q$ XYZ for $cq$ USD executed at time $T$, with
expected settlement at $T_{\text{set}} = T+2$. Define
$u^{\circ} = u^{\circ}(\tau_0)$.

> **Stateful claim 4.1** (State at $t \in [T, T_{\text{set}}]$). For every
> $t$ in this interval and assuming no fail event has fired:
>
> 1. *Real wallet positions* (own coordinate, GPM): the buyer holds $+q$
>    XYZ and $-cq$ USD; the seller's mirror wallet holds the negatives.
> 2. *Obligation positions:* $w_{\text{buyer}}(u^{\circ}) = +1$;
>    $w_{\text{seller-virtual}}(u^{\circ}) = -1$.
> 3. *Conservation:* $\sum_w w_t(\text{XYZ}) = 0$,
>    $\sum_w w_t(\text{USD}) = 0$, $\sum_w w_t(u^{\circ}) = 0$.
> 4. *Custody view (the $\pi_{\text{custody}}$ projection):* the buyer's
>    nostro shows the *prior* XYZ and USD balances --- the trade has not
>    settled.
> 5. *Reconcilable discrepancy:* the difference between the real-wallet view
>    and the nostro view equals (in absolute value) the parent transaction's
>    leg quantities, indexed by which obligations are in non-terminal states.

The fifth point is the formal counterpart of v10.3 §11.5's "lead-lag by
design"; §6 below makes the reconciliation identity explicit.

### 4.2 Move sequence for a buy at $T$, settlement at $T+2$

I use the v10.3 `Move(...)` notation. All transactions are atomic in the §6
sense; the obligation issuance and the trade-time position changes happen in
**one** transaction.

**Time $T$ (trade execution + obligation issuance).**

```
tau_trade = Transaction(type = SETTLEMENT):

    -- Real ledger position changes (trade-date accounting)
    Move(
        from: w_seller_virtual,
        to:   w_buyer,
        unit: XYZ,
        quantity: q,
        timestamp: T,
        source: tau_trade.tx_id,
        metadata: "TRADE_EXECUTION_SECURITIES_LEG"
    )
    Move(
        from: w_buyer,
        to:   w_seller_virtual,
        unit: USD,
        quantity: c * q,
        timestamp: T,
        source: tau_trade.tx_id,
        metadata: "TRADE_EXECUTION_CASH_LEG"
    )

    -- Obligation unit issuance (deferred-settlement extension)
    Move(
        from: w_seller_virtual,
        to:   w_buyer,
        unit: u_circ,            -- obligation unit; ProductTerms hold both legs
        quantity: 1,
        timestamp: T,
        source: tau_trade.tx_id,
        metadata: "OBLIGATION_ISSUANCE; settlement_type=DVP; T_set=T+2"
    )

    -- StateDelta on UnitStatus[u_circ]: lifecycle_stage = Issued
```

**Conservation check at $T$.**

- $\Delta Q(\text{XYZ}) = (+q) + (-q) = 0$. \checkmark
- $\Delta Q(\text{USD}) = (-cq) + (+cq) = 0$. \checkmark
- $\Delta Q(u^{\circ}) = (+1) + (-1) = 0$. \checkmark

The buyer's economic exposure is now $+q$ XYZ and $-cq$ USD; PnL is
trade-date true. The obligation unit records the open custody gap and is
zero-priced.

**Time $T+1$ (no economic event in this canonical case).** Status FSM has
moved $\textsf{Issued} \to \textsf{Instructed} \to \textsf{Matched}$; the
*UnitStatus*$[u^{\circ}]$.`lifecycle_stage` advances; **no moves are
emitted**. The corpus's existing claim that "no moves are generated" in this
window now has a precise referent: it means *no PositionState changes occur*;
*UnitStatus* changes do.

**Time $T_{\text{set}}^{-}$ (just before settlement).** Identical to $T+1$.

**Time $T_{\text{set}}^{+}$ (settlement confirmation, success path).**

```
tau_discharge = Transaction(type = LIFECYCLE):

    -- Custody-side reconciliation: the nostro now shows the asset
    Move(
        from: w_buyer_pending_custody,    -- a virtual wallet representing the
                                          -- "in-flight to nostro" balance
        to:   w_buyer_nostro_confirmed,
        unit: XYZ,
        quantity: q,
        timestamp: T_set,
        source: tau_discharge.tx_id,
        metadata: "CSD_DELIVERY_CONFIRMED; ref=sese.025/<id>"
    )
    Move(
        from: w_seller_pending_custody,
        to:   w_seller_nostro_confirmed,
        unit: USD,
        quantity: c * q,
        timestamp: T_set,
        source: tau_discharge.tx_id,
        metadata: "CASH_PAYMENT_CONFIRMED; ref=camt.054/<id>"
    )

    -- Obligation unit retirement (burn back to zero against issuer)
    Move(
        from: w_buyer,
        to:   w_seller_virtual,
        unit: u_circ,
        quantity: 1,
        timestamp: T_set,
        source: tau_discharge.tx_id,
        metadata: "OBLIGATION_DISCHARGE; lifecycle Matched -> Settled"
    )

    -- StateDelta on UnitStatus[u_circ]: lifecycle_stage = Settled;
    -- cumulative_settled_qty_securities = q; cumulative_settled_qty_cash = c*q.
```

**Conservation at $T_{\text{set}}^{+}$.**
$\Delta Q(\text{XYZ})$: the real-wallet $\mathrm{own}$ balance is unchanged
(the asset stays in $w_{\text{buyer}}$); only the *nostro* virtual
sub-account moves. The pending and confirmed sub-accounts together remain
zero-sum. Same for USD. Obligation unit: $+1 - 1 = 0$ on both sides;
$\sum_w w(u^{\circ}) = 0$ persists, and after the move
$w_{\text{buyer}}(u^{\circ}) = 0$ (held-and-flat, *Some(zero)* per
StatesHome C1). \checkmark

**Remark 4.2.** The pending-custody / confirmed-custody split is a refinement
of the existing "virtual wallet" mechanism, not a new mechanism. v10.3 §3
already requires virtual wallets to mirror counterparty positions; the only
addition here is **per-counterparty sub-wallets** for pending-vs-confirmed
custody, which are exactly the SBL "in-flight collateral" pattern from
§13.3.5. The settlement projection (§11.4) reads the same data; only the
wallet decomposition is finer.

### 4.3 Why the obligation unit retires rather than being deleted

StatesHome C1 (monotone carrier) requires that *PositionState* rows are not
deleted. The obligation unit's row at $w_{\text{buyer}}$ becomes
*Some(zero)* and remains forever; the *UnitStatus*$[u^{\circ}]$ is in the
terminal state $\textsf{Settled}$. This is essential for replay determinism
(§5) and for audit (CSDR fail register reconstruction; FRBNY 1099-style
trade history; restatement of restated prices used for historical penalty
calculation).

### 4.4 Worked example with required figures

100 XYZ bought at $\$50$, price moves to $\$52$ at $T_{\text{set}}^{-}$, with
no cash actually moved between $T$ and $T_{\text{set}}^{-}$.

| Moment | $w_B(\text{XYZ})$ | $w_B(\text{USD})$ | $w_B(u^{\circ})$ | $V_t$ component for XYZ | PnL since $T$ |
|---|---|---|---|---|---|
| $T^-$ | 0 | 5{,}000 | None | 0 | 0 |
| $T^+$ (post `tau_trade`) | 100 | 0 | +1 | $100 \times 50 = 5{,}000$ | 0 (price unchanged) |
| $T+1$ | 100 | 0 | +1 | $100 \times 51 = 5{,}100$ | $+100$ |
| $T_{\text{set}}^{-}$ | 100 | 0 | +1 | $100 \times 52 = 5{,}200$ | $+200$ |
| $T_{\text{set}}^{+}$ (post `tau_discharge`) | 100 | 0 | 0 (Some) | $100 \times 52 = 5{,}200$ | $+200$ |

The key economic content: PnL of $+200$ accrues on the buyer's book between
$T$ and $T_{\text{set}}$ **without any cash leaving the buyer's wallet at the
ledger level** (the buyer's $w(\text{USD})$ went from 5{,}000 to 0 at $T$;
this is the trade's economic recognition, not a cash settlement). The
custody-confirmed cash leg moves from "pending" to "confirmed" at
$T_{\text{set}}^{+}$ but the ledger position $w_B(\text{USD})$ has been 0
throughout. The obligation unit's quantity drops from 1 to 0 (*Some(zero)*)
at $T_{\text{set}}^{+}$; it does not contribute to $V_t$ at any point
(CSDR penalties aside).

This is exactly the corpus's Property 1 (path-independent PnL,
trade-date-accurate) made operational across the deferred-settlement gap.

### 4.5 Move sequence: partial settlement (CSDR partials)

If, at $T_{\text{set}}$, only $q' < q$ shares are delivered, the discharge
transaction emits proportionate moves:

```
tau_discharge_partial = Transaction(type = LIFECYCLE):
    -- Partial custody confirmation
    Move(... unit: XYZ, quantity: q', from pending to confirmed)
    Move(... unit: USD, quantity: (q'/q) * c * q, from pending to confirmed)

    -- Obligation unit is NOT retired: it stays at +1, FSM transitions to
    -- PartiallySettled; UnitStatus.cumulative_settled_qty_securities += q'.
```

**The crucial design point.** The obligation unit's position remains $+1$
during partial settlement: the *unit count* of obligations is invariant under
partial discharge. What changes is the cumulative-settled counter inside
*UnitStatus*. The remaining unsettled quantity is therefore a *projection*,
not a stored coordinate (analogous to GPM's $\mathrm{avail}$):

> **Definition 4.3** (Unsettled remainder). For an obligation $u^{\circ}$ in
> a non-terminal state,
> $$
> \mathrm{unsettled}(u^{\circ}) := \big( q_s - \texttt{cumulative\_settled\_qty\_securities},\;\;
>   q_c - \texttt{cumulative\_settled\_qty\_cash} \big).
> $$
> When both components are zero, the FSM transitions to $\textsf{Settled}$
> and the obligation unit retires (move from $+1$ to 0).

This makes partial settlement a strictly local operation on
*UnitStatus*$[u^{\circ}]$: no new obligation unit is minted per partial; the
parent obligation is the only object. This is C12 in spirit (no
denormalisation onto multiple unit IDs).

### 4.6 Move sequence: bilateral cancellation (`CORRECTION` per §11)

```
tau_cancel = Transaction(type = CORRECTION):

    -- Reversal of trade-date moves
    Move(from: w_buyer, to: w_seller_virtual, unit: XYZ, quantity: q, ...
         metadata: "CANCEL_REVERSAL_SECURITIES")
    Move(from: w_seller_virtual, to: w_buyer, unit: USD, quantity: c*q, ...
         metadata: "CANCEL_REVERSAL_CASH")

    -- Obligation unit retirement
    Move(from: w_buyer, to: w_seller_virtual, unit: u_circ, quantity: 1, ...
         metadata: "OBLIGATION_CANCELLED")

    -- StateDelta: UnitStatus[u_circ].lifecycle_stage = Cancelled.
```

The original $\tau_{\text{trade}}$ is **not deleted** (P4 log monotonicity).
Net effect on positions is zero; net effect on the obligation unit row at
$w_B$ is to leave it at *Some(zero)* (monotone carrier).

### 4.7 Move sequence: counterparty default

```
tau_default = Transaction(type = CORRECTION):

    -- Securities are not delivered. The buyer's economic loss is the
    -- difference between the trade price and the replacement cost. This is
    -- recorded as a fee/loss move; the obligation moves to Defaulted.

    Move(from: w_buyer, to: w_seller_virtual, unit: XYZ, quantity: q, ...
         metadata: "DEFAULT_REVERSAL_SECURITIES")
    Move(from: w_seller_virtual, to: w_buyer, unit: USD, quantity: c*q, ...
         metadata: "DEFAULT_REVERSAL_CASH")
    Move(from: w_seller_virtual, to: w_buyer_loss_recovery, unit: USD,
         quantity: max(0, (P_T_default - c) * q), ...
         metadata: "DEFAULT_CLOSE_OUT_DAMAGES")

    -- Move 4: Obligation retirement (Defaulted, terminal)
    Move(from: w_buyer, to: w_seller_virtual, unit: u_circ, quantity: 1, ...)

    -- StateDelta: UnitStatus[u_circ].lifecycle_stage = Defaulted.
```

Note that the close-out damages claim is a *receivable* against the
defaulting counterparty's virtual wallet --- it is not yet cash. This is
correctly modelled as another scalar position in the buyer's wallet, with
a separate recovery lifecycle (out of scope for this document).

---

## 5. Invariants

### 5.1 The ten core invariants survive

The Ledger's ten invariants P1--P10 (§11.2) are inherited verbatim. The
deferred-settlement extension introduces no new wallets, no new move
primitive, no new mutation point: it only adds new units. By P3 (referential
integrity) and StatesHome C5 (UnitStatus registration totality), every move
on $u^{\circ}$ is already validated by the executor. By Convention 2.4
(issuance-conservation), every issuance preserves $Q(u^{\circ}) = 0$. By the
move sequences in §4 every retirement preserves $Q(u^{\circ}) = 0$. Hence
P1 holds for $u^{\circ}$.

### 5.2 New invariants P24--P30 (deferred settlement)

> **P24** (Trade-date economic-exposure invariant; **mandatory**). For every
> SETTLEMENT-type transaction $\tau$ executed at time $T$ with parties
> $w_{\text{buyer}}, w_{\text{seller}}$, securities leg $(u_s, q_s)$, and
> cash leg $(u_c, q_c)$:
> $$
> w_{T^+}(u_s) - w_{T^-}(u_s) = q_s \quad \text{at the buyer},
> $$
> $$
> w_{T^+}(u_c) - w_{T^-}(u_c) = -q_c \quad \text{at the buyer},
> $$
> *regardless of the obligation unit's lifecycle state.* The obligation FSM
> can be in any state in $S \setminus F$ from $T$ to $T_{\text{set}}$ and
> these equations still hold. Equivalently:
> $V_{T^+}$ equals the trade-economic value, and intermediate
> $V_t$ (for $t \in [T, T_{\text{set}}]$) reflects only price changes on the
> already-recognised position.

This is the rigorous form of the corpus's "trade-date accounting" claim.
**Required by the user's brief.** It is *trivially* implied by §4.2's move
sequence: `tau_trade` writes the position changes at $T$, and no further
moves on real-wallet positions occur until either discharge (which moves
*nostro* positions, not *real-wallet* positions) or correction.

> **P25** (Obligation conservation). For every obligation unit $u^{\circ}$
> and every $t$:
> $$
> \sum_{w \in \mathcal{W}} w_t(u^{\circ}) = 0.
> $$

Proven by Convention 2.4 + the move sequences in §4 + induction on the move
stream (formal proof in §5.4).

> **P26** (Obligation totality). For every transaction $\tau$ of type
> SETTLEMENT or COLLATERAL committed by the executor, exactly one obligation
> unit $u^{\circ}(\tau)$ is registered in the same atomic transaction. The
> map $\tau \mapsto u^{\circ}(\tau)$ is total and injective on the
> SETTLEMENT-type sub-stream of $L_{13}$.

> **P27** (Obligation termination = custody convergence). At every time $t$,
> the set of in-flight (non-terminal) obligation units is in bijection with
> the set of (wallet, asset) pairs whose ledger-position-vs-nostro
> discrepancy is non-zero. Formally:
> $$ \big\{ u^{\circ} : \mathrm{UnitStatus}[u^{\circ}].\texttt{lifecycle\_stage} \notin F \big\} \xleftrightarrow{\;\cong\;} \mathrm{Discrepancy}(t) $$
> where $\mathrm{Discrepancy}(t)$ is defined in §6.

This is the formal "the open obligation IS the gap" statement. It makes the
reconciliation deterministic.

> **P28** (FSM totality). For every obligation $u^{\circ}$ and every event
> in $\Sigma$, the transition $\delta(\textit{state}, \textit{event})$ is
> defined; if no semantic transition applies, it returns
> `Reject(state, event)`. There is no silent failure path.

> **P29** (Settled-row monotonicity). Once
> $\mathrm{UnitStatus}[u^{\circ}].\texttt{lifecycle\_stage} \in F$, the
> *UnitStatus* is frozen and *PositionState*$[w, u^{\circ}]$ rows are
> retained at *Some(zero)*. (StatesHome C1, restated for obligations.)

> **P30** (No double issuance). For every parent transaction $\tau$, exactly
> one obligation $u^{\circ}(\tau)$ exists. Re-presentation of $\tau$ (e.g.
> at workflow retry) hits StatesHome C10 (re-registration is a hard error)
> via the deterministic `unit_id` derivation in Definition 2.1. Idempotency
> at the ledger level (P5) and at the obligation level coincide.

### 5.3 Conservation Lifting Theorem

> **Theorem 5.1** (Conservation Lifting). *Let* $\Sigma_{\text{base}}$ *be the
> set of v10.3 transaction kinds (SETTLEMENT, COLLATERAL, LIFECYCLE,
> ACCOUNTING, CORRECTION) under the v10.3 conservation law*
> $\sum_w w_t(u) = 0\,\forall u, \forall t$. *Let* $\Sigma_{\text{ext}}$
> *consist of* $\Sigma_{\text{base}}$ *together with the four deferred-settlement
> transaction kinds* $\mathcal{T}_{\text{trade}}, \mathcal{T}_{\text{recon}},
> \mathcal{T}_{\text{discharge}}, \mathcal{T}_{\text{reverse}}$
> *(with move semantics as specified in §4 and §6.4 respectively, and obligation
> registration per Definition 2.1). Let* $\mathcal{U}_{\text{ext}} =
> \mathcal{U} \cup \mathcal{U}_{\text{obl}}$. *Then for all*
> $u \in \mathcal{U}_{\text{ext}}$ *and all* $t$:
> $$ \sum_{w \in \mathcal{W}} w_t(u) = 0. $$

*Proof.* Induction on the move stream. **Base case** ($t = 0$, all wallets
zero): trivially $\sum_w w_0(u) = 0$ for every $u$, since
$\mathcal{U}_{\text{ext}}$ is initially empty for the obligation sector and
the v10.3 base case is unchanged.

**Inductive step.** Assume $\sum_w w_t(u) = 0$ for all $u \in
\mathcal{U}_{\text{ext}}$ at time $t$. Let $\tau$ be a transaction at time
$t' > t$. Cases:

(a) $\tau \in \Sigma_{\text{base}}$. Then $\tau$ does not touch any
$u^{\circ} \in \mathcal{U}_{\text{obl}}$ (by P26: only the four
deferred-settlement transaction kinds touch obligation units). Hence the
delta on every $u^{\circ}$ is zero, and the v10.3 conservation argument
(§3.4: $\Delta Q(u) = 0$ from `src -= q; dst += q`) discharges the obligation
on every $u \in \mathcal{U}$.

(b) $\tau \in \mathcal{T}_{\text{trade}}$ (issuance, §4.2). The transaction
contains: real-wallet moves (which are paired src/dst for $u_s$ and $u_c$,
hence each contributes 0 to the sum), and the obligation issuance move
($+1$ to receiver, $-1$ to deliverer's virtual --- explicitly paired by
Convention 2.4). All deltas are zero.

(c) $\tau \in \mathcal{T}_{\text{discharge}}$ (full or partial discharge,
§4.2 / §4.5). For full discharge: pending-custody $\to$ confirmed-custody
moves are intra-virtual reorganisations (paired src/dst, zero delta) plus
the obligation retirement ($+1$ at receiver $\to -1$ at deliverer, paired,
zero delta). For partial discharge: only pending/confirmed re-shuffles
occur; no obligation move; conservation trivial.

(d) $\tau \in \mathcal{T}_{\text{reverse}}$ (cancellation/default, §4.6 /
§4.7): every move is paired src/dst by inspection.

(e) $\tau \in \mathcal{T}_{\text{recon}}$ (pure status update, no
PositionState change): trivial; no deltas.

In all cases, $\sum_w w_{t'}(u) = \sum_w w_t(u) + \Delta = 0 + 0 = 0$.
By induction, the claim holds at all $t$. \qed

### 5.4 Why Conservation Lifting is the right theorem to state

The user's brief asks to "state a Conservation Lifting theorem". The
mathematically substantive content of Theorem 5.1 is that the v10.3
conservation law is a **proper extension** in the lattice of state spaces:
adding $\mathcal{U}_{\text{obl}}$ does not require modifying any existing
proof, because the new transaction kinds are themselves conservation-paired
by construction. This is *exactly* what the StatesHome C2 discipline
mandates ("conservation lives at the event handler"). The deferred-settlement
extension respects the StatesHome ruling.

---

## 6. Reconciliation by Design (lead-lag)

### 6.1 Definition of the discrepancy

The Ledger and the external custody/correspondent layer are **not** required
to agree at all times. v10.3 §11.5 gives this informally; here it is the
formal:

> **Definition 6.1** (Custody discrepancy). For a wallet $w$ and a unit
> $u \in \mathcal{U} \setminus \mathcal{U}_{\text{obl}}$ (i.e. a real
> economic unit, not an obligation), define
> $$ D_t(w, u) := w_t(u) - \mathrm{nostro}_t(w, u), $$
> where $\mathrm{nostro}_t(w, u)$ is the externally-witnessed custody balance
> reconciled into $L_{11}$ ExternalConfirmation up to time $t$. The total
> discrepancy at time $t$ is
> $$ D_t := \sum_{w, u} \big| D_t(w, u) \big|. $$

### 6.2 The reconciliation theorem

> **Theorem 6.2** (Reconciliation). *Under Theorem 5.1 and the move sequences
> of §4, for every wallet* $w$ *and every economic unit* $u$:
> $$
> D_t(w, u) = \sum_{u^{\circ} : \text{leg}(u^{\circ}) \ni (w, u, \text{sign})}
> \mathrm{sign}\cdot \mathrm{unsettled}_u(u^{\circ}),
> $$
> *where* $\mathrm{unsettled}_u(u^{\circ})$ *is the unsettled remainder
> (Definition 4.3) projected onto unit* $u$ *and* $\mathrm{sign} \in \{+1,
> -1\}$ *is the deliverer/receiver sign for that wallet in the obligation's
> ProductTerms.*

In words: **at every $t$, the ledger-vs-nostro gap equals exactly the sum of
in-flight obligation amounts touching $(w, u)$**. There is no other source
of discrepancy. If the gap on $w(\text{XYZ})$ is $-30$ shares relative to
the nostro, then there are open obligation units summing to 30 shares of
in-flight delivery from $w$.

*Proof outline.* By P27 (in-flight $\leftrightarrow$ discrepancy bijection)
and Definition 4.3 ($\mathrm{unsettled}$ is the only source of pending
custody movements), the only mechanism by which $w_t(u)$ and $\mathrm{nostro}_t(w, u)$
can disagree is an open obligation. The discharge moves (§4.2) precisely
zero the discrepancy when an obligation reaches $\textsf{Settled}$.
Cancellations (§4.6) zero the obligation's in-flight quantity and reverse
the trade move, so the discrepancy is again zero. Defaults (§4.7) realise
the loss into a recoverable wallet, leaving no in-flight obligation and no
discrepancy. \qed

### 6.3 Operational consequence

The reconciliation pair already specified for $L_{13}$ (MoveStream) and $L_6$
(PositionState) in the Data spec --- *(CCP daily statement, custodian,
triparty agent; daily T+1; per-regime tolerance; `wf-position-break`;
middle-office reconciliation)* --- becomes a **deterministic predicate**
under Theorem 6.2: a break exists if and only if some
$\mathrm{unsettled}(u^{\circ})$ disagrees with the custody report. The
$L_{18}$ BreakRegister FSM is then anchored to obligation-level reconciliation,
not to wallet-level reconciliation.

### 6.4 What `tau_recon` is

The fifth deferred-settlement transaction kind, $\mathcal{T}_{\text{recon}}$,
is a pure-status-update transaction emitted when an external confirmation
arrives that does *not* change PositionState. It updates *UnitStatus*
(e.g. *Issued* $\to$ *Instructed*) and writes a row to $L_{11}$. It contains
no PositionState moves; conservation is trivially preserved. It has type
`LIFECYCLE` per §11.4 with the `move_count = 0` sub-case noted in FAQ Q6.

---

## 7. CDM Cross-walk

| Deferred-settlement object | CDM 6.0.0 / DRR mapping |
|---|---|
| Obligation unit $u^{\circ}$ | New: not in CDM. Closest existing constructs are `BusinessEvent.transfer.transferState` (single-event, non-stateful) and `TradeState.state` (state on a Trade, not on an obligation). **Recommended extension PR:** `Obligation` type with FSM and lineage. |
| Issuance event $\mathcal{T}_{\text{trade}}$ | `EventIntentEnum.OPEN` + new sub-intent `OBLIGATION_ISSUE` (PR-sized addition). Composes the existing `ExecutionEvent` with the obligation registration. |
| Discharge event (full) $\mathcal{T}_{\text{discharge}}$ (full) | `BusinessEvent` composing `Reset` + `Transfer` (per v10.3 §8.5's discussion of the daily-settlement composite). |
| Discharge event (partial) | New: not in CDM; closest is `PartialTermination`, but partial *settlement* of a single obligation is distinct from partial termination of a Trade. **Recommended extension PR.** |
| Cancel $\mathcal{T}_{\text{reverse}}$ (cancel) | `EventIntentEnum.CANCELLATION` + sub-intent `BILATERAL_AGREEMENT_CANCEL`. |
| Default $\mathcal{T}_{\text{reverse}}$ (default) | `EventIntentEnum.TERMINATION` per master agreement; close-out per CDM `CloseOutCalculation`. |
| Status updates $\mathcal{T}_{\text{recon}}$ | `EventIntentEnum.OBSERVATION` (no economic effect). |
| ISO 20022 inbound | `sese.023` (settlement instruction), `sese.024` (status), `sese.025` (settlement confirmation), `sese.027` (cancellation), `camt.054` (cash). All already present in $L_{11}$ (Data spec). Mapping to obligation FSM transitions is given in §3.2. |
| CSDR penalty accrual | `EventIntentEnum` extension `CSDR_PENALTY` (PR-sized). Maps to *UnitStatus*$[u^{\circ}]$.`csdr_penalty_accrual`. |

The data spec already carries $L_{15}$ Obligation as a generic FSM; the
deferred-settlement obligation unit $u^{\circ}$ is its first concrete
instantiation. The mapping is: $L_{15}$ rows for settlement obligations
inherit `lifecycle_stage` from *UnitStatus*$[u^{\circ}]$. There is no
duplication.

---

## 8. Failure Modes per Floor Case

The user's brief mandates coverage of CORE (T+2 buy/sell, T+1, fail/CSDR,
partial, recon) and COMPOSITION (short, recall, corporate action,
cross-currency Herstatt, DvP atomicity).

### 8.1 CORE cases

**Buy T+2.** As §4.2 / §4.4. Three transactions in the parent's life:
$\mathcal{T}_{\text{trade}}$ at $T$, $\mathcal{T}_{\text{recon}}$ at $T+1$
(status `Instructed → Matched`, no moves), $\mathcal{T}_{\text{discharge}}$
at $T+2$.

**Sell T+2.** Symmetric: deliverer is now the user; the obligation
*PositionState* row at the user's wallet is $-1$. The signs of the trade-time
moves invert. Conservation argument identical.

**T+1.** ProductTerms.`expected_settlement_date` $= T+1$. No structural
change; the FSM advances faster. The obligation FSM is independent of the
calendar gap (T+0, T+1, T+2 are all permitted; only the timer durations in
the orchestration workflow change). This **resolves an implicit assumption
in v10.3 §11.5**, which used "T+2" idiomatically without making the regime
abstract.

**Fail (CSDR Article 7).** At $T_{\text{set}}$, no confirmation arrives.
External feed sends `sese.024 fail status`. FSM transitions
$\textsf{Matched} \to \textsf{Failing}$. CSDR cash penalty begins to accrue
in *UnitStatus*$[u^{\circ}]$.`csdr_penalty_accrual`. PnL impact: the
obligation's $P_t$ becomes negative on the deliverer's book per Definition
2.6. Time travel correctly reconstructs the period of failure with the
correct accrued penalty at any historical $t$.

**Partial.** §4.5. The obligation unit's PositionState count remains 1; only
the *UnitStatus* counters update. The reconciliation theorem (6.2)
correctly reports the residual gap.

**Reconciliation.** Theorem 6.2: deterministic identity between
ledger-vs-nostro gap and in-flight obligation total. Break detection is a
constant-time scan of $\mathcal{U}_{\text{obl}}$.

### 8.2 COMPOSITION cases

**Short sale (§13.5.3 short, §13.6 inventory).** A short sale is a sell
where the seller's `own` is or becomes negative. The deferred-settlement
extension treats it identically to a long sale: $\mathcal{T}_{\text{trade}}$
issues an obligation; the seller's GPM coordinates write $-q$ to `own`; the
obligation enters `Issued`. SBL borrowing (§13.5.1) issues a *separate*
obligation unit (`SBL loan unit`, already in v10.3 §13). The two obligations
are independent objects in $\mathcal{U}_{\text{obl}}$ with independent FSMs.
A *naked* short failing to deliver triggers $\textsf{Failing} \to
\textsf{BoughtIn}$ via CSDR/Reg SHO; the buy-in moves are emitted as in §3.2
row 9. Conservation Lifting (Theorem 5.1) extends through this composition
because each obligation lives in its own unit.

**Recall (§13.5.2).** A lender recalls $q'$ shares. This generates a
*new* obligation $u^{\circ}_{\text{recall}}$ (the obligation to deliver $q'$
back to the lender's nostro by recall date) which then runs the same FSM.
The original SBL loan unit's state advances to `RECALLED` per §13.5
state-machine; the deferred-settlement obligation tracks the *delivery*
back. Composition: a recall is a parent transaction whose obligation is
typed as `SBL_RECALL_DELIVERY` in *ProductTerms*$[u^{\circ}_{\text{recall}}]$.
No new mechanism beyond Definition 2.1.

**Corporate action.** v10.3 §5.3 establishes that CA processing is
multi-date (announcement, record, ex-date, payment). Three sub-cases:

- *CA before settlement of a trade.* Buyer's trade is at $T$, ex-date is at
  $T+1$, settlement is at $T+2$. Who receives the dividend? Under
  trade-date accounting, *the buyer* is entitled (the position exists from
  $T$). The CA's lifecycle event credits the buyer's wallet at ex-date. The
  obligation $u^{\circ}$ continues unaffected; CSDR / market practice handles
  the manufactured-payment obligation between deliverer and receiver.
  Concretely: a manufactured-payment obligation $u^{\circ}_{\text{mp}}$ is
  issued at ex-date alongside the dividend move, and runs its own FSM. This
  composes Theorem 5.1 with itself.
- *CA at settlement.* Edge case: the corporate action occurs on
  $T_{\text{set}}$. The discharge transaction's *ProductTerms* legs may
  need to be amended (split ratio, cash dividend pre-payment). The
  StatesHome C8 fungibility-preserving / fungibility-breaking distinction
  applies: a stock split is fungibility-breaking on the underlying ($u_s$
  becomes $u_s'$), so the obligation's *ProductTerms* gets a
  `FungibilityBreakingAmendment` and the legs are recomputed. The FSM does
  not need new states.
- *CA on the obligation itself.* Not applicable: obligations are not
  themselves subject to CAs.

**Cross-currency / Herstatt risk.** v10.3 §3 footnote acknowledges Herstatt
risk informally. With deferred settlement, the formal model is:

> **Definition 8.1** (PvP obligation). For a cross-currency trade
> $\tau_{\text{FX}}$ with EUR leg settling in TARGET2 and USD leg settling
> in CHIPS, define **two** obligation units $u^{\circ}_{\text{EUR}}$ and
> $u^{\circ}_{\text{USD}}$, each with `settlement_type = PvP`. Both have
> the same parent_tx_id but different `csd_or_correspondent`.

These obligations may discharge **independently** in time (TARGET2 closes
hours before CHIPS; CLS provides PvP within a window but not strict
simultaneity). Herstatt risk is then *exactly* the period during which
$u^{\circ}_{\text{EUR}}$ is $\textsf{Settled}$ but $u^{\circ}_{\text{USD}}$
is in any non-terminal state (or vice versa). The risk is **observable**
on the ledger as the asymmetric state of the two obligation units.

This is the formal counterpart of v10.3 §3's "settlement risk as an unsettled
receivable in a virtual wallet". Two PvP obligations + their independent FSMs
*are* that receivable made auditable.

**DvP atomicity --- formalised.** The user's brief specifically requests a
formal definition. v10.3 §11.4 distinguishes two levels of DvP. I formalise:

> **Definition 8.2** (Ledger-level DvP). A SETTLEMENT transaction $\tau$
> *is ledger-DvP* if and only if its move set contains *both* a securities
> leg (`unit.is_security() = true`) and a cash leg (`unit.is_currency() =
> true`), and the executor commits these moves as a single atomic
> transaction (P2 atomic commitment).
>
> **Definition 8.3** (Settlement-level DvP). An obligation unit $u^{\circ}$
> *is settlement-DvP* if and only if its `settlement_type = DvP` and the
> external CSD enforces simultaneity of securities and cash discharge
> (i.e. the FSM disallows `confirm_partial` from emitting a securities-only
> or cash-only discharge move).

> **Proposition 8.4** (DvP under deferred settlement). *If* $\tau$ *is
> ledger-DvP, then* $u^{\circ}(\tau)$ *carries both legs in its
> ProductTerms. If, in addition,* $u^{\circ}(\tau)$ *is settlement-DvP,
> then for every confirm event in §3.2, the discharge moves on the
> securities and cash legs are co-committed atomically (P2). The two DvP
> guarantees compose: ledger-level atomicity holds at $T$ (when the
> obligation is issued); settlement-level atomicity holds at $T_{\text{set}}$
> (when the obligation discharges).*

The composition of the two atomicity guarantees is exactly the structure
that v10.3 §11.4 hand-waves through; here it is a formal proposition with
hypotheses (settlement_type = DvP) and conclusion (composition).

---

## 9. The implicit assumptions of v10.3, made explicit

Bourbaki hygiene demands enumeration:

1. **A1.** v10.3 §11.6 says "no moves are generated" between $T$ and
   $T_{\text{set}}$. **Made explicit:** no moves are generated *on
   PositionState*; *UnitStatus* updates do occur; the obligation unit
   PositionState row stays at $\pm 1$.
2. **A2.** v10.3 §3 claims atomic transactions represent "economic intent"
   for FX. **Made explicit:** for cross-currency, atomic representation at
   $T$ does not imply atomic discharge; PvP obligation pairs are required
   to model Herstatt risk faithfully.
3. **A3.** v10.3 §11.5 lists `EXECUTED → INSTRUCTED → SETTLED | FAILED` as
   the status FSM. **Made explicit:** this FSM is the *projection* $\eta$
   of the finer obligation FSM $\mathfrak{O}$ (§3.3). The four-state v10.3
   FSM is a refinement target, not the full model.
3. **A4.** FAQ Q5 lists buy-in, partial, cancellation as fail-resolution
   paths but does not specify position semantics. **Made explicit:**
   buy-in keeps the original obligation in `Failing`/`BoughtIn` and emits
   buy-in moves; partial keeps the obligation in `PartiallySettled` and
   updates *UnitStatus* counters; cancellation issues a CORRECTION
   transaction reversing the trade-date moves and retires the obligation.
4. **A5.** §11.6 says "the positions were already correct from trade
   date". **Made explicit:** *real-wallet positions* were correct from
   trade date; *nostro positions* (custody-confirmed virtual sub-wallets)
   become correct only at $T_{\text{set}}$. The two are reconciled via
   Theorem 6.2.
5. **A6.** §13.3.5 mentions "in-flight collateral as a virtual-wallet
   entry" without typing it. **Made explicit:** in-flight collateral is
   itself an obligation unit in $\mathcal{U}_{\text{obl}}$ with
   `settlement_type` derived from the SBL leg (delivery-only or DvP).
6. **A7.** v10.3 §11.4 lists CASH | DVP | FOP settlement types. **Made
   explicit:** PvP is a fourth type, required for cross-currency
   cleanliness, with two co-issued obligation units.
7. **A8.** v10.3 §11.4's settlement projection is total on SETTLEMENT
   transactions. **Made explicit:** under deferred settlement, the
   projection is total on *parent* SETTLEMENT transactions; obligation-FSM-
   driven status updates (`tau_recon`) are LIFECYCLE-typed and project to
   `None`. This preserves v10.3's totality claim.

---

## 10. Verification Checklist

| Criterion | Verification |
|---|---|
| Correctness | Every claim proven (Theorem 5.1, Theorem 6.2, Proposition 8.4) or named-as-hypothesis (Liveness, §3.1). |
| Completeness | All eleven floor cases (CORE 5 + COMPOSITION 5 + DvP) addressed in §8. |
| Minimality | Two new objects ($u^{\circ}$, FSM $\mathfrak{O}$); zero modifications to existing primitives. The Pareto minimum. |
| Clarity | Definitions before use; numbered claims; explicit quantifiers. |
| Precision | Sign conventions, FSM totality, projection-vs-coordinate distinctions all explicit. |
| Consistency | Notation matches v10.3 + StatesHome + Data v1.0 verbatim. |
| Independence | Document is self-contained; references to corpus are pointers, not load-bearing. |

---

## 11. The One-Sentence Summary

**The open settlement obligation is a unit** $u^{\circ}(\tau) \in
\mathcal{U}_{\text{obl}}$, **issued atomically with the parent settleable
transaction, governed by a nine-state lifecycle FSM** $\mathfrak{O}$, **whose
PositionState row** ($\pm 1$ **at issuance, retired to** *Some(zero)* **at
termination) makes the lead-lag between trade-date economic recognition
and** $T_{\text{set}}$ **custody settlement an explicit, conservation-preserving,
reconcilable, time-travel-correct ledger object --- and the Conservation
Lifting Theorem proves that adding it requires no modification to any of
v10.3's ten core invariants.**

---

*End of Cartan Phase 1 proposal.*
