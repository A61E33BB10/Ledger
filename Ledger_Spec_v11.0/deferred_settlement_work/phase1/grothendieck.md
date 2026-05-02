# GROTHENDIECK — Phase 1 proposal: deferred settlement

**Question.** How should the Ledger represent the open settlement obligation
between T and T+2 for cash equities, in a way that already absorbs the floor
cases — buy/sell at T+2 or T+1, fail (CSDR), partial, recon lead-lag,
short-sell composition, recall, corporate action over the window,
cross-currency (Herstatt), DvP atomicity?

**Method.** I do not propose a new mechanism. I claim the framework already
has every piece — `Obligation` (L_15), bitemporal axes, the Λ_13 liveness
closure, the Λ_3 Settlement-Move closure, the EXECUTED→INSTRUCTED→
SETTLED|FAILED status lifecycle, the GPM `(own, onloan, borr, …)` vector,
the valuation FSM with its PROPOSED/PRICING transient states, the
ExternalConfirmation leaf — and the right abstraction is the one that
identifies them. The deferred-settlement window is not a new object. It is
**the comma category over the discharge predicate of an Obligation that has
been recognised but not yet realised**; trade-time recognition is the unit
of an adjunction between the *recognised* category and the *realised*
category; settlement is the counit; reconciliation is the gluing of two
sheaves on a common cover. Once the universal property is named, T+1 vs
T+2, partial, fail, recall, corporate action and Herstatt collapse into
coordinates on a single lifting that the framework already supports.

This is a long document. It is structured so that the **categorical
diagnosis is the first half** and the seven required sections are the
second half — but the second half is corollaries, not new construction.

---

## Part I — The universal property

### I.1 The five places the same structure already appears

The Ledger framework, in v10.3 + StatesHome + valuation v1.0 + data v1.0,
already carries five constructions of *“an obligation that has been
recognised but not yet realised”*:

| # | Surface name | Carrier | Recognition event | Realisation event | Open-window state |
|---|---|---|---|---|---|
| 1 | Forward / unsettled OTC trade | Trade is the unit; `PositionState[w,u_trade]` | execution → economic exposure on books | settlement at maturity / next coupon | `lifecycle_stage = ACTIVE` *and* settlement not reached |
| 2 | SBL on-loan / borrow gap | GPM coordinates `onloan, borr` (≠ `own`) | loan-initiation 4-move saga commits | recall return / loan termination | `onloan > 0 ∧ avail = own − onloan + borr` |
| 3 | CSA collateral in transit | `coll_post`, `coll_recv` rise on the call; `coll_rehyp` lags | margin call computed (Obligation `Pending`) | wire confirmed by `ExternalConfirmation` | `coll_post > 0` but counterparty `coll_recv` not yet `INSTRUCTED→SETTLED` |
| 4 | Valuation FSM `PRICING` (analogue of PROPOSED) | `ValuationRecord` with `quality ∈ {INDICATIVE, APPROXIMATE}`, FSM in `Pricing`/`Priced`/`Explaining` | pricer dispatched | PnL-explain passes → `Explained` (FIRM) | non-`Explained`, but a price exists |
| 5 | Cash equity settlement at T..T+2 | this proposal | execution at T → trade-date PnL on books | CSD confirmation at T+2 (`SETTLED`) | `EXECUTED` or `INSTRUCTED` but not `SETTLED` |

These are not five mechanisms. They are five instances of one categorical
construction.

### I.2 The category, the objects, the morphisms

Work in the category **Lg** of *ledger states*:

- objects: tuples `(ProductTerms, UnitStatus, PositionState, MoveStream,
  Obligation, ExternalConfirmation)` satisfying StatesHome C1–C12, the
  bitemporal axes `(t_obs, t_known)`, and the closure laws Λ_1, …, Λ_15
  of the data spec;
- morphisms: **state deltas** — atomic, balanced, conservation-preserving
  transitions emitted by handlers (StatesHome C2–C3).

A state delta is the unit of composition. Composition is associative
because `MoveStream` is hash-chained and state is a deterministic fold of
the chain (Theorem 1, Conservation Lifting; Theorem 2, Replay Determinism).
Identity is the empty delta. **Lg** is a category, and an event-driven one:
it is the free category on the LifecycleOracle alphabet (L_10’s
eighteen-constructor closed sum) modulo the executor’s admissibility
predicate.

Now consider the *fibration over time*:

$$
\pi : \mathbf{Lg} \longrightarrow \mathbf{Bitemp},
\qquad
\mathbf{Bitemp} = (\mathrm{ObsTime} \times \mathrm{KnownTime}, \le_{\mathrm{obs}}, \le_{\mathrm{known}})
$$

Each ledger state lives over a $(t_o, t_k)$ point; the fibre over a point
is the ledger as it was *known at* $t_k$ to be true *at* $t_o$. The two
projections give the two query modes the data spec already names: `as_of`
and `with_corrections_through`.

This is the rising sea. The whole settlement story is a story about
sections of $\pi$ over an interval $[T, T+2]$ in `ObsTime`, while
`KnownTime` advances along its own axis as confirmations arrive.

### I.3 Recognition, realisation, and the adjunction

Define two categories:

- **Rec** — the category of *recognised* events: pairs (economic obligation
  $o$, recognition timestamp $t_o$) with morphisms = settlement-preserving
  amendments. Concretely, an object is an `Obligation` in state `Pending`
  glued to a balanced transaction in `MoveStream`.
- **Real** — the category of *realised* events: triples (obligation $o$,
  realisation timestamp $t_o^{\mathrm{settle}}$, external witness
  $\xi \in \mathrm{ExternalConfirmation}$). An object is an `Obligation`
  in state `Discharged` glued to its `ExternalConfirmation` row.

There is a **forgetful functor** $U : \mathbf{Real} \to \mathbf{Rec}$ —
forget the witness, forget the realisation timestamp, retain the
obligation and the recognition.

**Claim.** $U$ has a left adjoint $F : \mathbf{Rec} \to \mathbf{Real}$
defined exactly when the obligation’s discharge predicate
(`L_15.discharge_predicate`, one of `ByDeadline | ByMatch | ByAttestation
| ByCondition`) is total over the closed enumeration `EventClass × ObligationKind`
(this is hypothesis D-COMP-TOTAL of Theorem 3, Liveness Lifting).

The adjunction is

$$
\mathrm{Hom}_{\mathbf{Real}}(F(\,\mathrm{rec}\,), \mathrm{real})
\;\;\cong\;\;
\mathrm{Hom}_{\mathbf{Rec}}(\mathrm{rec}, U(\,\mathrm{real}\,))
\quad\text{naturally in } \mathrm{rec}, \mathrm{real}.
$$

In English: **a recognised obligation is exactly the data of a future
realisation up to the witness**. Trade-time recognition (the move stream
entry at T) and settlement-time realisation (the external confirmation at
T+2) are the unit and counit of this adjunction. The open T..T+2 window is
the data of an unverified realisation — it sits in `Real` only after the
counit fires.

### I.4 The deferred-settlement endofunctor

Define $D : \mathbf{Lg} \to \mathbf{Lg}$ as the **deferred-settlement
endofunctor**:

$$
D(\,\mathrm{state}\,) \;=\; \mathrm{state} \;+\; \{\,\text{open obligations gathered from } L_{15}\,\}
$$

with the two key properties:

1. **Idempotent on closed obligations.** If every obligation in the state
   is `Discharged` or `Compensated` or `Defaulted`, then
   $D(\mathrm{state}) = \mathrm{state}$. (This is exactly Λ_13.)
2. **Functorial in time.** For any state delta $\delta : s \to s'$,
   $D(\delta)$ exists and commutes with the executor: settlement-status
   transitions and economic transitions compose without cross-talk.

$D$ is a **monad on Lg** with unit
$\eta : 1 \Rightarrow D$ being recognition (every economic event becomes
its own one-step open obligation) and multiplication
$\mu : D \circ D \Rightarrow D$ being **the merging of obligations across
the recall / cascade / partial-fill chain**. The Kleisli category of $D$
is exactly the category whose morphisms are *event sequences with
deferred settlement absorbed*.

**This is the abstraction.** Once it is named, every floor case is a
coordinate on $D$.

### I.5 The site and the sheaf — reconciliation as gluing

Take the site whose objects are *partial views* of the world:

- $\mathcal{V}_{\mathrm{ledger}}$ — what the Ledger believes;
- $\mathcal{V}_{\mathrm{nostro}}$ — what the custodian / nostro reports;
- $\mathcal{V}_{\mathrm{ccp}}$ — what the CCP / clearing house reports;
- $\mathcal{V}_{\mathrm{ext}}$ — what the counterparty confirms via L_11.

Cover an `Obligation` $o$ by these views; the open T..T+2 window is
exactly the time during which the views *do not yet agree*. The
reconciliation lead-lag is the gluing data: each view agrees on
the *intersection* (the trade economics, captured at T) but disagrees on
the *union* (whether the legs have moved on the external books).

A sheaf on this site is precisely a settlement-aware ledger state. The
gluing condition is exactly Λ_3 (Settlement-Move Closure: every external
confirmation maps to one $L_{13}$ segment) and Λ_8 (Replay Determinism:
the gluing is reproducible). A *sheaf failure* — when the views cannot be
glued into a consistent global section — **is what a CSDR fail is**.
Reconciliation breaks (`L_18 BreakRegister` rows) are obstructions to
gluing; the BreakRegister FSM (`Open → Investigating → … → Closed-{Clean
| Adj | Waived}`) is a small-step refinement of the cocycle calculation.

In this picture, an **internal reconciliation** is gluing two views
inside the same ledger; the framework already makes this structurally
unreachable (one source of truth). **External reconciliation** is gluing
across $\mathcal{V}_{\mathrm{ledger}}$ and $\mathcal{V}_{\mathrm{nostro}}$;
the lead-lag is exactly $t_k - t_o$ on the relevant rows.

### I.6 The minimal generalisation: settlement-status as a sub-state on `Obligation`

The framework already has `L_15 Obligation` with the FSM
`Pending → Discharged | Compensated | Defaulted`. The proposal in one
line:

> **A deferred-settlement leg is an `Obligation` whose `discharge_predicate`
> is `ByMatch{ matcher = settlement_status_match(EXECUTED → INSTRUCTED →
> SETTLED) }` and whose `compensation_handler` is `NonTrivialChildWorkflow{
> CSDRBuyInWorkflow, tower_depth = 2 }`.**

That is the entire mechanism. Everything else is consequence:

- The EXECUTED → INSTRUCTED → SETTLED|FAILED status lifecycle of v10.3
  §11.7 is a refinement of `Pending → Discharged|Defaulted`.
- The `ExternalConfirmation` leaf $L_{11}$ is the matcher input.
- Λ_13 (Obligation Liveness) gives mandatory closure within
  $\delta_h \le T_{\max}$ — i.e., the buy-in deadline.
- Λ_3 (Settlement-Move Closure) ties the discharge to the `MoveStream`.
- The bitemporal axes give the two readings: “what we believed at T+1”
  vs “what is now true about T+1 given the T+3 buy-in”.
- The `BreakRegister` $L_{18}$ FSM with aging timers `T+1, T+3, T+5`
  is the CSDR penalty schedule it has been all along — and the data spec
  already names this in §IPV/CSDR.

Once stated this way, T+1 vs T+2 is a parameter on the deadline; partial
is the same Obligation split into two via the monad’s
multiplication $\mu$; recall is an Obligation that propagates the
predicate down the on-lending chain (cascade-recall saga from v10.3
§14.7); corporate action over the window is a re-fibring of the
`ProductTerms` leaf via the C8 two-track amendment; cross-currency /
Herstatt is the **two views fail to glue temporally** — same sheaf
pattern, different cover.

---

## Part II — The required structure, redescended to concrete moves

The categorical view dissolves the floor cases. This part recovers what
implementers need: state shape, move sequence, invariants, recon
read-out, CDM cross-walk, failure modes, worked example.

### II.1 State representation

**No new leaves are created.** Deferred settlement uses, in this order:

1. **`L_13 MoveStream`.** The trade is captured at T as a single balanced
   transaction with `event_class = TRADE` (a conservative class) and
   `tx.cdm_payload.settlement_date = T+2`. *Conservation holds at T already.*
2. **`L_6 PositionState`.** Updated at T as the executor commits the
   transaction. The buyer’s `own` increases by 100, the seller’s `own`
   decreases by 100. **The economic recognition is at T, not T+2.**
3. **`L_15 Obligation`.** Two new `Obligation` rows are emitted by the
   trade handler — one per leg, both `Pending`:
   ```
   Obligation(
     id            = (tx_id, leg='securities'),
     deadline      = T+2 EOD,
     predicate     = ByMatch(securities_settlement_status == SETTLED),
     compensation  = NonTrivialChildWorkflow(CSDRBuyInWorkflow,
                                             tower_depth=2),
     state         = Pending,
     bound_to      = (tx_id, move_indexes=[securities_leg])
   )
   Obligation(
     id            = (tx_id, leg='cash'),
     deadline      = T+2 EOD,
     predicate     = ByMatch(cash_settlement_status == SETTLED),
     compensation  = NonTrivialChildWorkflow(CSDRBuyInWorkflow,
                                             tower_depth=2),
     state         = Pending,
     bound_to      = (tx_id, move_indexes=[cash_leg])
   )
   ```
   The two are linked by a **DvPGroup** identifier (a content-addressed
   join key, not a new leaf). Atomic discharge of the group requires
   *both* predicates to evaluate true at T+2; partial is exactly the case
   where one resolves and the other becomes a new compensating Obligation.
4. **`L_11 ExternalConfirmation`.** Inbound `sese.025` for securities and
   `camt.054` for cash drive the predicate evaluation. Each carries a
   `transaction_id_ref → L_13` resolution (Φ_11^W).
5. **`L_5 UnitStatus`.** *Unaffected* by the open window; the unit (e.g.
   the equity ISIN) has no per-instrument state that depends on whether
   *this* trade has settled. (Cf. v10.3 line 1034 phrasing: equity unit
   state is shared, position state is per (w, u). Open-leg state is
   per-trade, hence belongs on the per-trade `Obligation`, not on the
   per-unit `UnitStatus`.)
6. **No new field on `PositionState`.** The temptation to add an
   `unsettled_qty` or a “pending” sub-coordinate must be rejected. It
   would duplicate Obligation data, violate the StatesHome
   minimum-basis-of-three argument, and re-introduce the per-(w,u) trap
   the addendum already closed.

**The lifting on top of the GPM.** For lendable securities the GPM
already separates economic ownership (`own`) from possession-by-others
(`onloan`, `borr`). For deferred settlement the analogous split is
between *economic ownership* (`own`, increased at T) and *external
settlement status* (lives on the `Obligation`, not on `PositionState`).
The two splits are not the same axis — `onloan/borr` is a possession axis
while `Obligation.state` is a witness axis — but they are the two
projections of the same monad $D$ onto two different leaves: the GPM
projection for legal-vs-physical custody, the Obligation projection for
internal-vs-external truth.

### II.2 Move sequence with conservation

Cash equity buy of 100 XYZ @ \$50, T+2 cycle. Buyer wallet $w_B$, seller
wallet $w_S$. Both real wallets in the same Ledger for clarity; for
external-counterparty trades $w_S$ is a virtual wallet per v10.3 §2.5.

```
─────────────────────────────────── T (trade date) ───────────────────────────────────
tx_T = BalancedTransaction(
  event_class = TRADE,
  tx_id       = hash_jcs(business_event_id, attempt_seq),
  cdm_payload = { settlement_date = T+2, … },
  moves = [
    Move(from=w_B, to=w_S,  unit=USD, quantity=5000.00),   # cash leg
    Move(from=w_S, to=w_B,  unit=XYZ, quantity=100),       # securities leg
  ]
)
ExecutorCommit(tx_T)                                      # atomic, balanced
EmitObligation(O_sec  : Pending, deadline=T+2)
EmitObligation(O_cash : Pending, deadline=T+2)
DvPGroup.bind(O_sec, O_cash)
SettlementWorkflow.start(tx_T)                             # status: EXECUTED

Conservation at T (per unit):
  ΔUSD_total = -5000 + 5000 = 0           ✓
  ΔXYZ_total = -100  + 100  = 0           ✓
PositionState already reflects buyer.own = +100, seller.own = -100.
PnL at T already reflects mark-to-market on +100 XYZ.

────────────────────── T+1 (instruction & first reconciliation) ──────────────────────
SettlementWorkflow:
  enriched   = Enrich(SettleProjection(tx_T))
  message    = GenerateISO20022(enriched)            # sese.023, pacs.008
  submit_ref = SubmitToCSD(message)
  status: EXECUTED → INSTRUCTED                       # recorded as L_13 status row,
                                                      # NOT a new balanced transaction

Recon at T+1 EOD:
  L_ledger view : own(w_B, XYZ) = +100, own(w_S, XYZ) = -100, cash mirrored
  L_nostro view : pending instruction submitted, not yet settled
  Sheaf gluing  : agrees on amounts; disagrees on confirmation cell — expected

────────────── T+2⁻ (settlement window opens; pre-confirmation) ──────────────
SettlementWorkflow.Sleep(until=T+2 EOD).
Obligation.state remains Pending; deadline armed.

────────────── T+2⁺ (confirmation arrives, both legs) ──────────────
Inbound L_11 ExternalConfirmation (sese.025 securities + camt.054 cash):
  RecordConfirmation(tx_T, confirm_securities)
  RecordConfirmation(tx_T, confirm_cash)
  status: INSTRUCTED → SETTLED                        # status row, no balanced moves
  EvaluateDischarge(O_sec)  : Pending → Discharged
  EvaluateDischarge(O_cash) : Pending → Discharged
  DvPGroup.discharge(both)                            # atomic group close

NO ECONOMIC MOVES ARE EMITTED AT T+2.
Positions were already correct from T. Settlement is realisation, not recognition.
The L_13 entries at T+2 are status updates and Obligation discharges, not transfers.
```

The move sequence has **exactly one balanced transaction** (at T) for the
trade. T+1 and T+2 are not new transactions — they are state transitions
on already-emitted Obligations and on the EXECUTED→INSTRUCTED→SETTLED
status field. This is the **only** way to preserve the path-independent
PnL theorem (v10.3 §3.3): if a settlement event emitted economic moves,
PnL between T and T+3 would depend on whether settlement happened to
land within the interval — i.e. PnL would become path-dependent.

Conservation is not “held open” over T..T+2. **Conservation closes at T**;
what is open between T and T+2 is the *witness* of the settlement, not
the economics.

### II.3 Invariants — including the mandatory economic-exposure-at-T

I list the invariants in the order: **the load-bearing one first**, then
the standard StatesHome / Λ-laws specialised to deferred settlement.

**ECON-AT-T (mandatory).**
For every cash-equity trade transaction $\tau \in L_{13}$ with
`cdm_payload.settlement_date = T+2$, and for every wallet $w$ and every
price function $P_t$ defined on $[T, T+2]$:
$$
V_t(w) \;=\; \sum_u w_t(u) \cdot P_t(u) \quad \text{for all } t \in [T, T+2]
$$
where $w_t(u)$ already reflects the trade quantities at $t = T$.
**The trade contributes to portfolio value strictly from T**, not from
the settlement date. Equivalently: if a price moves from \$50 to \$52
between T and T+2, the buyer’s PnL increases by `+\$200 = 100 × \$2`
even though no cash has settled. *This is the statement that the floor
case in the prompt is correct by construction.*

Proof: by Theorem 1 (Conservation Lifting), `PositionState[w_B, u_XYZ]`
is updated at T as part of `ExecutorCommit(tx_T)`. By scalar
compatibility (valuation v1.0, Principle 3.2), $V_t = \sum w_t(u) \cdot
\texttt{dirty\_price}_t(u)$. Both sides are determined at T already.
Settlement status does not enter $V_t$.

**DvP-ATOM (Ledger level).**
For any trade transaction $\tau$ with both a securities leg and a cash
leg, the executor commits both moves or neither. This is the structural
consequence of the transaction primitive, not a runtime check. (v10.3
§11.4.) Settlement-level DvP — the simultaneous transfer on CSD books —
is provided by external infrastructure and lies outside the Ledger; it is
the matcher input to `O_sec` and `O_cash`, not a Ledger property.

**OBL-LIVE (Λ_13 specialisation).**
For every (`O_sec`, `O_cash`) pair emitted by a trade with deadline
$t_d = T+2 + \delta_{\mathrm{CSDR}}$ (the regulatory grace period), at
$t_d + \delta_h$ exactly one of `Discharged`, `Compensated`, `Defaulted`
holds. The grace period $\delta_{\mathrm{CSDR}}$ is `4 business days for
liquid equities` (CSDR Article 7); it lives on `L_7^Pb` (tolerance
sidecar), not on the Obligation type itself.

**SETT-MOVE (Λ_3 specialisation).**
Every inbound `sese.025` / `camt.054` resolves to exactly one $L_{13}$
status segment and at most one Obligation discharge. Multiple
confirmations for the same `(tx_id, leg)` are deduplicated by L_11’s
content-addressed key.

**RECOG-NEW (path-independence).**
PnL between $t_0$ and $t_1$ is $V_{t_1} - V_{t_0}$ regardless of the
settlement statuses of the open trades within $[t_0, t_1]$. Settlement
events emit no economic moves; therefore the path-independent PnL
theorem (v10.3 §3.3) extends across the open settlement window without
modification. This is the structural reason the framework can survive
T+0 → T+1 transitions in 2024 without rewriting valuation.

**MONOTONE-CARRIER (StatesHome C1).**
`PositionState` rows are not garbage-collected by deferred-settlement
events. A buyer who closes the position by selling out at T+1 leaves
*two* `Obligation` rows pending (one for the open buy, one for the open
sell), and *two* `PositionState` rows monotonically present. The two
trades net economically; the two settlements remain distinct external
obligations until both confirm. (This is exactly the case the prompt
labels “sell T+2 against an open buy” — and the right answer is *do
nothing special*: monotone carrier + per-trade Obligations handle it.)

**HANDLER-ATOM (StatesHome C3).**
The trade handler emits `(tx_T, O_sec, O_cash, DvPGroup)` as one
StateDelta; the executor admits the whole group or nothing. (No
intermediate state where the moves committed but the obligations did not.)

### II.4 Reconciliation lead-lag

The lead-lag is the gap between $t_o$ (observation: when the external
event occurred) and $t_k$ (knowledge: when the Ledger admitted the row).

For an open T..T+2 leg:

- $t_o$ for the trade itself = T (execution timestamp).
- $t_k$ for the trade = T (we admitted it as we executed it).
- $t_o$ for the *settlement* leg = T+2 (when the CSD books move).
- $t_k$ for the settlement leg = T+2 + $\Delta_{\mathrm{wire}}$ (when
  the `sese.025` ack arrives over SWIFT or the equivalent).

The bitemporal type carries both. The data spec already provides
`as_of(t_k)` and `with_corrections_through(t_o, t_k')`; for deferred
settlement the second mode answers the question
*“what was true on T+1 given that we now know about the T+3 fail?”* —
i.e., the regulatory restatement query.

**Lead-lag obstruction lives on `L_18 BreakRegister`.** A break opens at
the recon cadence (typically T+1 EOD) when the ledger view of `tx_T`
disagrees with the nostro view; ages through `Open → Investigating →
Aged-1 → Aged-3 → Aged-5 → Escalated`; closes on
`Closed-{Clean | Adj | Waived}`. The aging timers map directly to the
CSDR penalty schedule (the data spec already names this connection in
§CSDR Penalty Schema).

The **lead-lag is bounded** by Λ_4 (Bitemporal Coherence): restatement
chains are bounded by $\kappa_{\mathrm{restate}}$ (a `L_7^Pb` constant).
This is the formal statement that *we cannot still be reconciling
T-trades a decade later* — the framework forbids it structurally.

### II.5 CDM cross-walk

| Concept | CDM artefact | Status | Notes |
|---|---|---|---|
| Trade execution at T | `BusinessEvent` with `Execution` primitive | Direct | Stored in `tx.cdm_payload`. |
| Settlement instruction | CDM `Transfer` + `SettlementInstruction` | Direct in CDM 6.0; produced by `settle_projection`. |
| Open obligation T..T+2 | *no native CDM type* | **Missing** | CDM has `TradeState` lifecycle but no first-class `Obligation` carrier. The Ledger’s `L_15` is Ledger-native; this is one of the documented CDM gaps in the data spec §CDM Gap Analysis. |
| Status `EXECUTED→INSTRUCTED→SETTLED` | `TradeState` transitions | Partial | CDM tracks state transitions on the trade; Ledger reifies them on the Obligation. The two are isomorphic on this floor. |
| `sese.025` / `camt.054` ingest | CDM `Confirmation` synonyms | Direct | Per CDM synonym layer. |
| CSDR fail / partial | `BusinessEvent` with `Reset`/`Termination` for a corrective sub-trade | Partial | CDM can encode the buy-in trade itself but does not have a native “fail event” type. Compensating workflows close the gap. |
| Manufactured payment over window (corp action between T and T+2) | `CorporateActionEvent` | Direct on the event | The interaction with the open obligation (does the dividend follow trade-date or settlement-date?) is a smart-contract concern, not a CDM gap. Ledger answer: trade-date — the buyer has economic ownership at T and is entitled. The dividend Obligation is a *new* L_15 row with its own discharge predicate. |

The cross-walk obeys Λ_9 (Forgetful-Functor Composition): the projection
$F : \mathbf{CDM} \to \mathbf{Lg}$ from CDM events to Ledger states
factors through the Obligation extension; nothing CDM stores is lost.
Ledger stores the full CDM payload on `tx.cdm_payload`.

### II.6 Failure modes

Every failure mode is one of the closed forms below. There are no
others — the closed-sum discipline of `LifecycleEvent` (L_10’s 18
constructors) and `ObligationKind` enforces this.

| Failure | Surface | What happens in the model |
|---|---|---|
| **CSDR fail (insufficient securities)** | `sese.025` arrives with status = REJECTED/PEND-RECYCLE; or no confirmation by deadline | `O_sec` → `Compensated` via `CSDRBuyInWorkflow` (tower_depth = 2). The compensation child workflow opens a market buy-in trade; the buy-in’s own DvP Obligations are new `L_15` rows. The original PositionState is *not* reverted — the economic exposure existed from T. |
| **Partial settlement** | CSD reports partial delivery (e.g. 60 of 100) | `O_sec.Pending` is split via the monad multiplication $\mu$: one `Discharged` child for 60, one `Pending` child for 40 with the original deadline. Cash leg behaves symmetrically; DvPGroup is rebound to the matched 60/60 portion. Conservation holds because the split is purely on the witness, not on the moves. |
| **Counterparty rejection** | `pacs.002` reject | `O_cash` → `Compensated` via `CompensatingTransaction`: a `CORRECTION`-class transaction reverses the cash leg and the securities leg together (atomic). The original moves remain in the immutable `MoveStream` (N_9: mutable history forbidden); the correction is a *new* balanced transaction. |
| **Sell at T+1 against an open buy at T (covered short)** | not a failure, a composition | At T: long-buy Obligation `O_buy_sec, O_buy_cash` opens. At T+1: sell Obligation `O_sell_sec, O_sell_cash` opens. PositionState `own` returns to its pre-trade level via two monotone updates. *Both pairs of Obligations are open simultaneously*, with two different deadlines (T+2 and T+3). Each settles independently; the GPM `avail` projection is unaffected because `own` already moved on each side. **This is the case the prompt warns about; the framework absorbs it without special logic.** |
| **Naked short** | sell at T without `own ≥ Q` and without `borr` | The trade is admissible (PositionState can go negative — this is a short position; v10.3 §2.1). At T+2 the seller’s `O_sec` cannot discharge by `ByMatch` because the seller does not have securities to deliver. The Obligation triggers `CSDRBuyInWorkflow` immediately or at deadline; alternatively, the seller borrows via SBL before T+2 to make the delivery. **In the SBL composition: the sell at T emits `O_sec` Pending; the borrow at T+1 raises `borr`; at T+2 the delivery uses the borrowed inventory, `O_sec` discharges, and the SBL contract takes over — its own recall obligation is now alive in `L_15`.** |
| **Recall during open settlement window** | lender recalls at T+1 against shares lent and now sold | Cascade-recall saga from v10.3 §14.7 fires. The recalled position must close before T+2 to honour `O_sec`. If it does not, the buy-in saga from §14.7 (terminal fallback) attributes the cost. The deferred-settlement Obligation is *unchanged* — it still measures whether the original sale settles; the cascade is an upstream story on a separate Obligation chain. |
| **Corporate action between T and T+2** | dividend ex-date at T+1 | The `CorporateActionEvent` (an L_10 oracle event) fires. The action’s entitlement key is *trade date*, not settlement date — the buyer at T is the entitled holder. A new `O_div` Obligation opens for the dividend payment; it has its own deadline and its own discharge witness (the manufactured-payment confirmation if the original settlement fails). Conservation holds: the issuance handler emits a matched issuer-credit/debit pair (D-ISS in Theorem 1). |
| **Cross-currency, Herstatt** | EUR/USD trade where one currency settles in EU hours and the other in US hours | The two legs become two **separate Obligations** with different deadlines: `O_eur` at T+2 EU EOD, `O_usd` at T+2 US EOD. The DvPGroup binds them; the gap between them is **the Herstatt window**. The framework cannot eliminate Herstatt risk (v10.3 §2.6 already says so) but it can *represent* it: at any time during the gap, exactly one of the two Obligations is `Discharged` and the other is `Pending`. The gap is therefore a measurable, queryable property of the obligation set, not an off-ledger surprise. CLS / PvP integration is the matcher pattern that closes the gap externally; the Ledger already supports it via the same `L_11` channel. |
| **Reconciliation break** | nostro shows different position after T+2 | A `L_18 BreakRegister` row opens. The investigation closes via `Closed-Adj` (a `CORRECTION` transaction), `Closed-Clean` (the nostro is wrong; no Ledger change), or `Closed-Waived` (four-eyes governance). The Obligation state and the BreakRegister state are independent FSMs; the break can outlive the Obligation if the substance is material enough to escalate. |

A failure that is none of these is, by C1–C12 plus closed-sum discipline,
**unrepresentable**. This is the abstraction earning its keep.

### II.7 Worked example — 100 XYZ @ \$50, price moves to \$52, no cash moved

I run through the full timeline so the invariants are visible.

**Setup.** Buyer wallet $w_B$ (real), seller wallet $w_S$ (virtual, the
broker), cash equity unit $u_{\mathrm{XYZ}}$, T+2 settlement cycle.

**Initial state at T-.**
```
PositionState[w_B, u_XYZ].own = 0
PositionState[w_B, u_USD].own = 10_000.00
PositionState[w_S, u_XYZ].own = 0          (virtual; conservation partner)
PositionState[w_S, u_USD].own = 0
Obligation set                = ∅
ExternalConfirmation set      = ∅
V_{T-}(w_B) = 10_000.00
```

**Event 1 — Trade at T, price = \$50.**

Trade handler emits one `BalancedTransaction` with two moves and two
Obligations:
```
tx_T = BalancedTransaction(
  event_class = TRADE,
  tx_id       = h_T,
  cdm_payload = { settlement_date = T+2, trade_price = 50.00 },
  moves = [
    Move(from=w_B, to=w_S, unit=USD, qty=5000.00),
    Move(from=w_S, to=w_B, unit=XYZ, qty=100),
  ]
)
EmitObligation(O_sec  = (h_T,'sec') ,Pending, deadline=T+2)
EmitObligation(O_cash = (h_T,'cash'),Pending, deadline=T+2)
DvPGroup.bind(O_sec, O_cash)
```

State after T:
```
PositionState[w_B, u_XYZ].own = +100
PositionState[w_B, u_USD].own = +5_000.00     (10_000 - 5_000)
PositionState[w_S, u_XYZ].own = -100
PositionState[w_S, u_USD].own = +5_000.00
Obligation set                = { O_sec : Pending, O_cash : Pending }
Status(tx_T)                  = EXECUTED
```

PnL check at T (price still \$50):
$$
V_T(w_B) = 5\_000 + 100 \times 50 = 10\_000 \;=\; V_{T-}(w_B). \quad \checkmark
$$
The trade is value-neutral at T against the same price (zero spread).

**Event 2 — Price moves to \$52, no other event.**

This is purely a market-data move. No transaction is emitted. No
Obligation transitions. No status update on `tx_T`. The Ledger sees:
```
PositionState[w_B, u_XYZ].own = +100      (unchanged)
PositionState[w_B, u_USD].own = +5_000    (unchanged)
Obligation set unchanged.
```

Valuation:
$$
V(w_B) \;=\; 5\_000 + 100 \times 52 \;=\; 10\_200.00.
$$
$$
\boxed{\;\mathrm{PnL}(T_-, t) \;=\; V(w_B; t) - V(w_B; T_-) \;=\; 10\_200 - 10\_000 \;=\; +\$200.\;}
$$

This is the floor case. **PnL = +\$200, no cash moved.** The economic
exposure existed from the moment the trade was admitted at T; the price
move from \$50 to \$52 propagates through the path-independent PnL
theorem; the open settlement Obligations have no effect on $V$.

**Event 3 — T+1 EOD: instruction submitted.**

`SettlementWorkflow` advances `tx_T.status` from `EXECUTED` to
`INSTRUCTED`. This is recorded as a status row in `MoveStream` (a
`LIFECYCLE`-class transaction with no moves; it is non-conservative
because there is nothing to conserve — purely a witness update). The
Obligation set is unchanged.

PnL is still computed against PositionState; instruction submission has
no PnL impact.

**Event 4 — T+2 EOD: confirmations arrive, both legs settle.**

Inbound `sese.025` for the securities leg, `camt.054` for the cash leg.
Each is recorded as an `L_11 ExternalConfirmation` row; each triggers
`EvaluateDischarge`:
```
RecordConfirmation(tx_T, sec_confirm)
  → O_sec.state : Pending → Discharged
RecordConfirmation(tx_T, cash_confirm)
  → O_cash.state: Pending → Discharged
DvPGroup.discharge(O_sec, O_cash)
Status(tx_T) : INSTRUCTED → SETTLED
```
**No economic moves are emitted.** The position values are unchanged;
the only change is on the Obligation FSM and on the status field. Λ_3
(Settlement-Move Closure) holds vacuously: there is nothing to map to a
move because the move was already there from T.

State after T+2:
```
PositionState : unchanged from T
Obligation    : both Discharged (rows retained, monotone-carrier)
Status(tx_T)  : SETTLED
```

PnL between T and T+2 if price held at \$52:
$$
\mathrm{PnL}(T, T+2) \;=\; V(w_B; T+2) - V(w_B; T) \;=\; 10\_200 - 10\_000 \;=\; +\$200.
$$
Independent of the settlement events that happened during the interval.
This is path-independence working through the deferred window.

**Variant — fail at T+2.** If `sec_confirm` is missing at T+2 EOD:
```
deadline armed:
  selector.AddTimer(T+2 EOD, …)
on timer fire:
  HandleSettlementFailure(tx_T, submission_ref)
    case INSUFFICIENT_SECURITIES:
      buyin_tx = AttemptBuyIn(tx_T)
      ExecutorCommit(buyin_tx)              # NEW balanced transaction
      O_sec.state : Pending → Compensated   # discharged via compensation
      ResubmitToCSD(buyin_tx)               # opens new O_sec_bi
```
PositionState in $w_B$ is unchanged (the buyer still owns 100 XYZ
economically; that has not changed). What changed is *who is delivering*.
The BreakRegister opens a row aging through `T+1, T+3, T+5` per the
CSDR penalty schedule.

**Variant — sell at T+1 against the open buy.** At T+1, $w_B$ sells 100
XYZ at \$51 to a third party $w_X$:
```
tx_T1 = BalancedTransaction(...)
  Move(w_X → w_B, USD, 5_100.00)
  Move(w_B → w_X, XYZ, 100)
EmitObligation(O_sec_T1, deadline=T+3, Pending)
EmitObligation(O_cash_T1, deadline=T+3, Pending)
```
State at T+1:
```
PositionState[w_B, u_XYZ].own = 0          (+100 - 100)
PositionState[w_B, u_USD].own = +10_100    (5_000 + 5_100)
Obligation set = {O_sec_T : Pending (T+2),
                  O_cash_T : Pending (T+2),
                  O_sec_T1 : Pending (T+3),
                  O_cash_T1 : Pending (T+3)}
```
At T+2: original (O_sec_T, O_cash_T) discharge; the position is now flat
*both economically and on the books* — but $w_B$ owes 100 XYZ delivery
on T+3 from the open sale. `own = 0` is fine because `own` is economic
ownership. At T+3: (O_sec_T1, O_cash_T1) discharge. Each settlement
window is independent. Conservation holds at every step. PnL realised
across the in-and-out: $5\_100 - 5\_000 = +\$100$, captured at T+1 not
at T+3.

This is the case that breaks naive “unsettled inventory” designs and
**does not break this one**, because the framework never tries to track
“unsettled stock” as a separate quantity. Settlement status is on the
Obligation, not on the PositionState.

---

## Part III — Closing the rising sea

The framework already had:

- a `MoveStream` whose entries are conservation-balanced;
- an `Obligation` leaf with a Pending → Discharged | Compensated |
  Defaulted FSM;
- a Λ_13 liveness law guaranteeing closure within bounded horizon;
- a Λ_3 settlement-move closure law tying external confirmations to
  ledger transactions;
- a status lifecycle EXECUTED → INSTRUCTED → SETTLED|FAILED on every
  transaction;
- a bitemporal observation model with both `as_of` and
  `with_corrections_through` queries;
- an `L_11 ExternalConfirmation` channel for sese / camt / pacs ingest;
- a `BreakRegister` FSM with aging timers aligned to CSDR;
- a `CorporateActionEvent` constructor on `L_10`;
- the GPM splitting `own / onloan / borr` for divergence-of-possession;
- a valuation FSM with transient and degraded states (`Pricing`,
  `Stale`, `Quarantined`) that is itself an instance of the same
  unsettled-witness pattern;
- a Pareto-ratified StatesHome 3-map whose minimum basis is exactly
  `ProductTerms / UnitStatus / PositionState`.

The contribution of *deferred settlement* is **not** a new mechanism. It
is a structural identification:

> **The open T..T+2 window is the comma category of the recognition →
> realisation adjunction $F \dashv U$ between Rec and Real, instantiated
> by the deferred-settlement endofunctor $D$ on Lg, with two Obligation
> rows per trade as the unit of $D$ and `ExternalConfirmation` ingestion
> as the counit. Every floor case — T+1, T+2, fail, partial, recall,
> corporate action over the window, cross-currency Herstatt — is a
> coordinate on this lifting, decided by the choice of
> `discharge_predicate`, `compensation_handler`, and the binding pattern
> of `DvPGroup`.**

No new leaves. No new fields on `PositionState`. No new mutation
discipline. The `O_sec`/`O_cash` pair is a `L_15` instance with two
specific predicates; the DvPGroup is a content-addressed join key. The
addition fits inside the StatesHome 3-map without loosening C1–C12.

The economic-exposure-at-T invariant is preserved automatically because
the trade is a single balanced `MoveStream` entry at T; settlement is a
witness lifecycle on top of that. PnL between T and T+2 is
$V_{T+2} - V_T$ regardless of settlement status. The floor case 100 XYZ
@ \$50 → \$52 ⇒ PnL = +\$200 with no cash moved is the consequence.

The site-and-sheaf reading makes external reconciliation a gluing problem
on a cover; the lead-lag is the gluing data; CSDR fail is a sheaf
obstruction; BreakRegister rows are the cocycle. Because the framework
already records sufficient bitemporal data to compute every restriction
on every cover, the gluing is decidable — i.e. recon is, in the strong
sense the data spec promises, *witnessed*.

The slightly more abstract framing (adjunction, monad, sheaf) is what
forces the floor cases to collapse to one thing. The implementer-facing
artefact is small: two `Obligation` rows per trade, one DvPGroup, the
existing `SettlementWorkflow`. The abstraction exists not to be coded
but to be *proved against*: the right tests are the adjunction unit /
counit equations, the monad laws on $D$, the gluing condition on the
recon site. If those hold, every floor case in the prompt — and every
case the prompt did not anticipate — is automatically handled.

The rising sea has dissolved the problem.

— GROTHENDIECK
