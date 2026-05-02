# FORMALIS — Phase 1 Independent Proposal: Deferred Settlement

**Author**: FORMALIS committee (Leroy chair; Coquand, Huet, Paulin-Mohring, de Moura, Avigad)
**Scope**: A formal-properties specification of how the Ledger represents the open settlement obligation between trade time `T` and settlement time `T+k`, focused on cash equities (k = 2, k = 1) but designed to subsume CSDR fails, partial delivery, short, recall, corporate action, cross-currency (Herstatt), and DvP atomicity as specialisations. The deliverable here is *invariants, totality, determinism, termination, proof obligations, gaps* — not narrative.

---

## 0. Position relative to the existing corpus

The Ledger v10.3 already commits to several pieces that constrain the design space:

1. **Trade-date accounting is canonical** (§2, §6 footnote on Herstatt; §11; FAQ Q2/Q3/Q5). Economic position changes at `T`, not at `T+k`. Reversing the position on a fail is forbidden — exposure was real, only custody movement is missing.
2. **Conservation holds per unit, per transaction, at every state** (§2 Conservation Law; §11 P1).
3. **Settlement is a projection, not a separate ledger** (§8 Settlement Layer Interface). `settle_projection` is pure, total on settlement-typed transactions, and idempotent.
4. **Status lifecycle is `EXECUTED → INSTRUCTED → SETTLED | FAILED`** (§8.6) — but this is *status on the transaction*, not a state object that participates in conservation.
5. **The settlement gap is acknowledged but not formalised**: §8.4 paragraph "The temporal gap" states that between trade and settlement the Ledger shows correct economic position and the CSD confirms transfer at settlement, with no reversal on fail. The mechanism by which the ledger reconciles to the nostro at `T+k` is *not* a stated invariant in v10.3. The §8.5 Herstatt paragraph (§2 line 296) waves at "unsettled receivable in the virtual wallet of the settling counterparty" but does not formalise it.
6. **StatesHome 3-map is canonical** (addendum, April 2026): `ProductTerms[u]` / `UnitStatus[u]` / `PositionState[(w,u)]`. Per-position state is the home for any per-(holder, unit) datum; status flags shared across holders live in `UnitStatus`. C1–C12 govern. No fourth `WalletState` map exists.
7. **Obligation is a first-class object** (§13 Liveness; §15 in `ledger_data_v1.0` taxonomy as $L_{15}$): tuple $(id, type, source, t_d, D, \kappa)$ with FSM `Pending → {Discharged, Compensated, Defaulted}` and Theorem~3.6 (Obligation Liveness, P21). This machinery already exists; deferred settlement should use it, not invent a parallel one.
8. **The Single-Coordinate Move Principle and the six-coordinate vector** (§13) give a vocabulary for "ownership without possession" that we can extend, by analogy, to "execution without custody confirmation".

A correct deferred-settlement specification must therefore *not* introduce a new ledger sector, *not* mutate `own` on a fail, *not* break conservation, and *not* require ad-hoc reconciliation logic. Everything below is constrained by these.

---

## 1. State representation

### 1.1 The settlement state of a transaction

A committed *settlement-typed* transaction $\tau$ carries a settlement status object stored in `UnitStatus`-discipline (mutable, shared across all parties to the transaction, single-writer-per-field per C11):

$$
\text{SettlStatus}(\tau) \in \mathcal{S} = \{\textsc{Executed}, \textsc{Instructed}, \textsc{PartiallySettled}, \textsc{Settled}, \textsc{Failed}, \textsc{BoughtIn}, \textsc{Cancelled}\}
$$

- `Executed`: $\tau$ committed in the ledger (T journaled). Settlement projection has run; instruction not yet at the CSD.
- `Instructed`: instruction submitted to the CSD; CSD has not confirmed.
- `PartiallySettled(q_settled, q_remaining)`: CSD reports partial delivery; an explicit non-terminal state with payload.
- `Settled`: CSD confirms the full quantity moved; nostro reconciles.
- `Failed`: CSD reports failure (insufficient securities, system error, counterparty rejection). Non-terminal — must transition.
- `BoughtIn`: CSDR mandatory buy-in executed; loop closed via market-side replacement plus cost attribution.
- `Cancelled`: a `CORRECTION` transaction with anti-moves has been committed; the original economic position is undone (this is rare and load-bearing — see §6 below).

`SettlStatus(\tau)` is **not** a coordinate in `PositionState` and **not** a wallet balance. It is a `UnitStatus`-class field on the transaction-as-unit (the transaction is a *unit instance* in the audit register, but its quantity-level state is already decomposed into the moves; what remains is purely a status flag and a few timestamps).

### 1.2 The deferred-settlement obligation

For each settlement-typed $\tau$ with intended settlement date $t_d$, a single obligation is registered atomically with the trade commit (per §13 Principle "Obligation Completeness"):

```
o_settle(τ) = Obligation(
    id            : "SETTLE_" + tx_id(τ),
    type          : SETTLEMENT_INSTRUCTION  -- per L_15 / §13 Table
    source        : τ
    deadline      : t_d                      -- the contractual settlement date (T+k for cash eq)
    discharge     : D_settle(τ)              -- defined below
    compensation  : κ_settle(τ)              -- defined below; failure-type-dispatched
)
```

The discharge predicate $D_{\text{settle}}(\tau)$ is a function on the bitemporal ledger state at $t > t_d$ checking that an external confirmation matching $\tau$ has been admitted into the move stream (via $L_{11}$ ExternalConfirmation):

$$
D_{\text{settle}}(\tau)(\sigma) = \exists\, c \in L_{11}(\sigma) : \text{matches}(c, \tau) \wedge c.\text{kind} \in \{\textsc{Sese025Confirmed}, \textsc{Camt054Credit}\}
$$

The compensation $\kappa_{\text{settle}}$ is a *closed sum* (per $L_{15}$ design) over failure types — see §6.

### 1.3 The open-window position representation

The economic position at $T$ is recorded as ordinary moves into `PositionState[(w, u)]` immediately. **No coordinate, no separate map, no new sector.** Trade-date accounting is preserved.

The unsettled status is carried by:

1. The `SettlStatus(\tau)` flag (§1.1) — a `UnitStatus` datum on the transaction.
2. The obligation `o_settle(\tau)` — an $L_{15}$ row.
3. A *virtual-wallet contra-entry* with the counterparty (§2 Virtual Wallets). This is where the open obligation is *quantitatively* visible — the counterparty's virtual wallet shows the unsettled receivable/deliverable balance.

This is the load-bearing modelling decision: **the open settlement obligation is not a new state object; it is the joint reading of (real position, virtual-wallet contra, status flag, obligation row).** The four are derivable from the move stream plus the obligation log — i.e., from data the framework already has — and no axiom of conservation is touched.

---

## 2. Move sequence (T, T+1, T+2⁻, T+2⁺)

Worked schema for **buy 100 XYZ @ \$50, T+2**, party $A$ (us) buying from broker virtual wallet $B$. (The sell case is symmetric; T+1 is the same with $t_d - T = 1$ day; we abstract over $k$.)

### 2.1 At time $T$ (trade execution, ledger commit)

```
τ_trade = Transaction(type = SETTLEMENT, t = T, settlement_date = T+2):
    Move 1: Move(from=A_cash,    to=B_virt,    unit=USD,  q=5000)   -- cash leg
    Move 2: Move(from=B_virt,    to=A_equity,  unit=XYZ,  q=100)    -- securities leg
```

Atomically with this transaction:

```
register(o_settle(τ_trade))                  -- Obligation row in L_15, deadline = T+2
SettlStatus(τ_trade) := Executed             -- UnitStatus write
```

**Conservation per unit:**
- $\Delta Q(\text{USD}) = -5000 + 5000 = 0$ across $\{A_{\text{cash}}, B_{\text{virt}}\}$.
- $\Delta Q(\text{XYZ}) = -100 + 100 = 0$ across $\{B_{\text{virt}}, A_{\text{equity}}\}$.

**Verified.** Conservation holds *at* the open-window state, not merely on entry/exit. This is the non-negotiable property the standing constraint demands.

**State after T:**
- $A_{\text{equity}}(\text{XYZ}) = +100$ (real position, trade-date accounting).
- $B_{\text{virt}}(\text{XYZ}) = -100$ (broker owes us 100 XYZ).
- $A_{\text{cash}}(\text{USD}) = -5000$ relative to opening (we owe \$5000).
- $B_{\text{virt}}(\text{USD}) = +5000$ (broker is owed \$5000 by us).
- $\text{SettlStatus}(\tau_{\text{trade}}) = \textsc{Executed}$.
- One open `o_settle` row.

### 2.2 At time $T+1$ (no movement; only valuation crosses the day)

PnL for the day flows from the price change on the already-recorded position:

$$
\text{PnL}_A(T+1 - T) = w_A(\text{XYZ})\cdot(P_{T+1}(\text{XYZ}) - P_T(\text{XYZ})) = 100 \cdot (52 - 50) = +200
$$

**No moves.** The PnL is a derived quantity per the §3 PnL Path-Independence Theorem and the §4 valuation framework. The required worked-example PnL is recovered by construction.

The settlement workflow (per §11.5 Settlement Orchestration) is asleep on its Temporal timer until $t_d$. `SettlStatus(\tau_{\text{trade}}) = \textsc{Instructed}$ as soon as the settlement projection has handed the instruction to the CSD layer (typically same day).

**Conservation at $T+1$:** unchanged from $T$ — no moves, identity preserved trivially.

### 2.3 At time $T+2^-$ (deadline imminent, before CSD confirmation)

Still no moves. The state is the same as at $T$ + price drift. The obligation $o_{\text{settle}}$ is in `Pending` (or `Attempted` if the CSD has acknowledged receipt of the instruction). The Temporal timer at $t_d$ will fire if no `discharge_signal` arrives.

### 2.4 At time $T+2^+$ — three sub-cases

#### Case A: clean settlement

External confirmation $c = \textsc{Sese025Confirmed}(\tau_{\text{trade}}, q = 100)$ arrives (signal channel `discharge_SETTLE_<id>`). Predicate $D_{\text{settle}}$ fires.

```
τ_confirm = Transaction(type = LIFECYCLE, t = T+2):
    -- no moves
    state_delta:
        SettlStatus(τ_trade) := Settled
        o_settle(τ_trade).state := Discharged
```

**No moves.** Why: positions were correct from $T$ under trade-date accounting. The virtual-wallet contra-entry remains; it is now reconciled against the custodian's confirmed depot balance via the standard reconciliation projection (§4 below).

**Conservation at $T+2^+$:** unchanged. Identity holds.

#### Case B: fail (CSD reports `INSUFFICIENT_SECURITIES`)

```
τ_fail = Transaction(type = LIFECYCLE, t = T+2):
    -- no moves
    state_delta:
        SettlStatus(τ_trade) := Failed
        o_settle(τ_trade).state := Attempted     -- still non-terminal
```

The compensation handler $\kappa_{\text{settle}}$ then dispatches:

```
match failure_type:
  case INSUFFICIENT_SECURITIES   → spawn buy-in workflow, deadline t_d + n_csdr_days
  case PARTIAL                   → fork: discharge for q_settled, new τ_remainder for q_remaining
  case COUNTERPARTY_REJECTION    → emit τ_correction (anti-moves), SettlStatus := Cancelled
  case SYSTEM_ERROR              → re-instruct, retry up to bounded n
```

**Crucially: no anti-moves on fail.** The economic exposure is real; the Ledger does not reverse. This is correct per §8.4 and §FAQ Q5.

**Conservation at $T+2^+$:** unchanged. The fail event is move-less.

#### Case C: partial settlement

CSD reports $q_{\text{settled}} = 60$, $q_{\text{remaining}} = 40$.

```
τ_partial = Transaction(type = LIFECYCLE, t = T+2):
    -- no moves; the original 100/5000 are correct, only the status is split
    state_delta:
        SettlStatus(τ_trade) := PartiallySettled(60, 40)
        o_settle(τ_trade).state := Discharged              -- for the 60
        register(o_settle_remainder)                       -- new obligation, q=40, deadline t_d + n
```

The remaining 40 are a fresh open obligation under `o_settle_remainder`. **No anti-moves**, **no position change**, the broker's virtual wallet still shows $-100$ — the partial fill has not altered the economic substance, only the discharge state.

**Conservation at $T+2^+$:** unchanged.

---

## 3. Invariants

I now state the invariants, each labelled, each with a precondition / postcondition / termination argument where applicable. The standing list (§11 P1–P10, §13 P11–P20, §13 P21–P23) is extended; I number from `DS1` to avoid collision.

### DS1 (Mandatory) — Economic Exposure At T

For all settlement-typed transactions $\tau$ with execution time $T$ and settlement date $t_d$:

$$
\forall t \in [T, t_d^-] : w_A^{\text{after}(\tau)}(u) - w_A^{\text{before}(\tau)}(u) = q(\tau, u) \quad \forall u \in \text{units}(\tau)
$$

That is, the position vector for every party to $\tau$ reflects the full economic effect of $\tau$ from $T$ onwards, not from $t_d$. Equivalently: there exists no coordinate, no flag, and no aggregation function over the move stream whose value during $[T, t_d^-]$ differs from its value after $\tau$ in a Settled state.

**Why mandatory**: the question demands "economic position is true from T". DS1 is the formal version. Any design that updates `PositionState` only at $t_d$ violates DS1 and is rejected.

**Defence against counter-design**: a "settlement-pending" coordinate (think: $w_A^{\text{pending\_recv}}(u) = +100$, $w_A^{\text{own}}(u) = 0$ during the open window, switching at $t_d$) would *appear* to handle this — but breaks DS1 because PnL formulas, margin computations, MtM aggregation, and risk reports all read `own` and would understate exposure during the window. We discharge this counter-design in §8.

### DS2 — Conservation At Every State Including Open-Window States

For every unit $u$ and every time $t$ (including $t \in [T, t_d^-]$):

$$
Q(u)(t) = \sum_{w \in \mathcal{W}} \vec w_t(u)[\text{own}] + (\text{virtual contras}) = 0
$$

Restated: the open window does not require, anywhere, a partial or transient state in which conservation does not hold. Conservation is preserved by the move semantics + the algebraic identity $\sum_{\text{moves}} (\text{src}\mathrel{-=}q + \text{dst}\mathrel{+=}q) = 0$, exactly as in §2.4 of v10.3. **No new conservation argument is needed**; deferred settlement is a status overlay and an obligation overlay, not a quantity overlay.

This is non-negotiable per the standing project constraint.

### DS3 — Ledger ↔ Nostro Reconciliation Identity (Lead-Lag By Design)

For any unit $u$ and any holder $A$, at any time $t$:

$$
\underbrace{w_A(u)[\text{own}]}_{\text{ledger position}} = \underbrace{\text{depot}_A^{\text{custodian}}(u, t)}_{\text{nostro at } t} + \underbrace{\text{InFlight}_A(u, t)}_{\text{open obligations net}}
$$

where

$$
\text{InFlight}_A(u, t) = \sum_{\substack{\tau\,:\,A\in\text{parties}(\tau) \\ \text{SettlStatus}(\tau) \in \{\textsc{Executed}, \textsc{Instructed}, \textsc{Failed}, \textsc{PartiallySettled}\}}} \text{signed\_qty}(\tau, A, u)
$$

This is the lead-lag identity. The ledger leads by exactly the sum of open settlement obligations. Reconciliation against the custodian is then *not a free-form comparison* but an *algebraic identity*: if it fails, either a confirmation has not been ingested (operational), an obligation has been mis-registered (specification bug), or the custodian's record genuinely diverges (counterparty break, the only thing the ledger cannot prevent).

**Proof obligation** (DS3-PO): show that for every settlement-typed $\tau$, the contribution to `InFlight` is added at $T$ (as part of the `o_settle` registration delta) and removed exactly when `o_settle.state` transitions to `Discharged`. This is mechanical; the proof is by induction on the settlement workflow's Temporal history. It is verifiable by property-based test.

### DS4 — Obligation Liveness Specialised To Settlement

Apply §13 Theorem 3.6 (P21) to $o_{\text{settle}}$. For every $o_{\text{settle}}(\tau)$ registered at $T$ with deadline $t_d$:

$$
\forall t > t_d : \text{state}(o_{\text{settle}}(\tau)) \in \{\textsc{Discharged}, \textsc{Compensated}, \textsc{Defaulted}\}
$$

i.e., no open settlement obligation persists past $t_d$ in `Pending` or `Attempted`. The five-lemma proof from §13.2.7 carries over verbatim, with one substitution: Lemma 5 (handler totality) requires that the failure-type closed sum in $\kappa_{\text{settle}}$ is exhaustive — i.e., the CSD failure-reason enumeration is closed. **This is a real proof obligation** (DS4-PO): the CSDR / CSD failure-type enumeration must be sourced as a closed sum, not a free-text string. Otherwise totality is unprovable.

### DS5 — Replay Determinism Under Out-Of-Order Confirmations

Settlement confirmations from CSDs / nostros arrive asynchronously and out of order: a `sese.025` for $\tau_1$ submitted Tuesday may arrive Wednesday morning *after* the `camt.054` for $\tau_2$ submitted Wednesday. Replay must yield the same end state regardless of ingest interleaving.

**Statement**: For any two interleavings $\pi_1, \pi_2$ of the same multiset of confirmation messages,

$$
\text{apply}(\sigma_0, \pi_1) = \text{apply}(\sigma_0, \pi_2)
$$

restricted to the joint state of $(L_{13}, \text{SettlStatus}, L_{15})$.

**Proof sketch**:
1. Each confirmation $c$ carries an `external_ref` matching exactly one $\tau$. The matching is a pure function (per §8 Settlement Projection determinism + the §15.1 reconciliation pair contract).
2. The state delta for a confirmation $c$ matched to $\tau$ depends only on $\tau$ and $c$, not on the order in which other unrelated confirmations have been processed. This is because `SettlStatus` is keyed on $\tau$ alone, and `o_settle.state` transitions are keyed on the obligation $\tau$-id alone.
3. $L_{15}$ is a `Pending → terminal` FSM. Confirmation-driven transitions are commutative across distinct obligations: $\text{discharge}(\tau_1) \circ \text{discharge}(\tau_2) = \text{discharge}(\tau_2) \circ \text{discharge}(\tau_1)$ as state operators on the joint FSM, because they touch disjoint obligation rows.
4. Conservation is unaffected because confirmations emit no moves.

Hence the algebra is commutative on disjoint settlement workflows, idempotent on duplicates (per §13 P23, idempotency), and replay is deterministic.

**Caveat (DS5-Caveat)**: this fails if a confirmation is mis-routed (i.e., matches the wrong $\tau$). The confirmation-matching function must therefore itself be deterministic and total on a documented domain. It is not — in real markets, ambiguous matches occur (e.g., two trades with same ISIN, same counterparty, same date, same quantity, no UTI). This is a known and inherited limitation; the framework relies on UTI / EndToEndId discipline at instruction time. We name this gap explicitly in §8.

### DS6 — Idempotency Of Confirmation Ingestion

For any confirmation $c$ targeting $\tau$ with status $s = \text{SettlStatus}(\tau)$:

$$
\text{ingest}(c) \circ \text{ingest}(c) = \text{ingest}(c)
$$

i.e., re-presenting the same confirmation (same `MessageId`) twice has no incremental effect. This composes from §11 P5 (transaction idempotency on $\tau_{\text{confirm}}$), §13 P23 (obligation idempotency on $o_{\text{settle}}$), and §14 invariant $N_4$ (idempotency on replay).

### DS7 — Status Lifecycle Totality

The transition relation $\delta : \mathcal{S} \times \text{ConfirmationKind} \to \mathcal{S}$ (§1.1 status states × §15 confirmation kinds) is total and partial-function-free: every (state, event) pair has a defined successor or is rejected with a typed error. Concretely:

| from \ event | `Sese023Submitted` | `Sese025Confirmed` | `Sese025Failed` | `Camt054Credit` | `BuyInExecuted` | `Cancellation` |
|---|---|---|---|---|---|---|
| Executed | Instructed | Settled | Failed | Settled (cash) | — | Cancelled |
| Instructed | (idem.) | Settled | Failed | Settled | — | Cancelled |
| Failed | Instructed (re-instruct) | Settled | Failed (idem.) | Settled | BoughtIn | Cancelled |
| PartiallySettled | — | Settled | Failed (remainder) | Settled (remainder) | BoughtIn (remainder) | Cancelled |
| Settled | (rejected) | (idem.) | (rejected) | (idem.) | (rejected) | (rejected; needs CORRECTION) |
| BoughtIn (terminal*) | — | — | — | — | — | — |
| Cancelled (terminal*) | — | — | — | — | — | — |

*Truly terminal: no transitions out without a CORRECTION transaction, which itself spawns a fresh settlement workflow and obligation.

The empty cells with "—" are explicit type errors, not silent drops. This satisfies the §11 invariant 10 (Valid lifecycle transitions only) for the settlement sub-FSM.

### DS8 — Transaction-Status Atomicity

`SettlStatus(\tau)` transitions are atomic with the obligation-state transitions and any related move emissions (e.g., a buy-in transaction). This is C3 of StatesHome (atomic StateDelta across `ProductTerms` / `UnitStatus` / `PositionState`) extended to include $L_{15}$:

$$
\Delta(\text{SettlStatus}, L_{15}, L_{13}) \text{ commits as a single atomic unit, or not at all}
$$

A partially-applied confirmation (e.g., `SettlStatus := Settled` written but `o_settle.state := Discharged` not written) is structurally unrepresentable.

### DS9 — Capability Scoping On Settlement Status Writes (C11)

Per StatesHome C11, every `SettlStatus(\tau)` field has a *unique writer*: the `SettlementWorkflow` of §11.5. No other handler may mutate it. The post-trade gateway, the trader, the risk system, the regulatory reporter — none can write `SettlStatus`. They may *read* per their capability; writes are gated. This makes accidental status drift impossible by type.

### DS10 — Open-Window Cardinality And Absorbing States

State space induced by an open settlement obligation $o_{\text{settle}}(\tau)$:

- Status $\mathcal{S}$: 7 elements (§1.1).
- Obligation FSM: 4 elements `{Pending, Attempted, Discharged, Compensated, Defaulted}` (§13 def 3.1; the diagram in §13.2.1 shows 5 nodes).
- Joint product before terminal pruning: $7 \times 5 = 35$.
- Reachable subset (after pruning impossible combinations like `Settled × Pending`): on the order of 12 reachable states. **Finite.**
- **Absorbing states**: `(Settled, Discharged)`, `(BoughtIn, Compensated)`, `(Cancelled, Compensated)`, `(_, Defaulted)`. All four are terminal and unreachable from each other.

This is small enough to be model-checked by TLC or a similar finite-state checker. **Proof obligation (DS10-PO)**: produce a TLA+ or Alloy specification of the joint settlement / obligation FSM and exhaustively verify no path leaves the reachable region without entering an absorbing state. Tractable at $|\mathcal{W}|=3, |U|=2, \text{depth} \le 6$ per the StatesHome addendum's bound.

### DS11 — Forbidden Transitions

Stated as negative invariants (these must be unreachable):

- **DS11.a**: A move that mutates `own(u)` for any party as a *consequence of a settlement confirmation*. Forbidden because the move was already journaled at $T$. Exceptions: `BuyInExecuted` (a fresh trade with its own moves) and `CORRECTION` (anti-moves that are themselves a fresh trade). These two are not "consequences of confirmation"; they are independent transactions with their own moves and their own conservation discharge.
- **DS11.b**: A `SettlStatus := Settled` without a matching $L_{11}$ row. Forbidden — the discharge predicate $D_{\text{settle}}$ requires evidence; predicate-violation = type error.
- **DS11.c**: An open `o_settle` past $t_d + \Delta_{\text{CSDR}}$ without `Compensated` or `Defaulted`. Forbidden by DS4 + Theorem 3.6.
- **DS11.d**: A cross-currency leg pair settling on different `Settled` flags without a parent saga that aggregates them. Forbidden — Herstatt (§7 below) requires per-leg status with explicit parent join.

### DS12 — Deferred Settlement Degenerates Across Variants

Required by the question. The same machinery (§1, §2) must specialise to:

- **T+1**: identical, $t_d - T = 1$. No code change.
- **Cash equity sell**: signs flip; $\tau$ is symmetric.
- **DvP**: the trade is one $\tau$ with two legs (cash + securities); ledger-level atomicity (§8.4) is preserved by transaction atomicity (§11 P2). One `o_settle`, not two.
- **FOP / cash-only**: the settlement projection produces a single-legged instruction; one `o_settle` with a one-legged discharge predicate. No structural change.
- **CSDR fail / partial / buy-in**: the failure-type closed sum + κ_settle handles these in §6. Status `Failed → BoughtIn` is the CSDR mandatory buy-in path. **No new ledger primitives.**
- **Short** (§13): a borrowed-share sell at $T$ is a normal `own -= q` move on $\tau$. The borrow's own settlement obligation is a separate $o_{\text{settle}}^{\text{borrow}}$ whose discharge is the SBL settlement, not the cash-equity sell's settlement. The two obligations compose in parallel.
- **Recall**: recall's return obligation (§13 P21 specialised) is structurally the same as $o_{\text{settle}}$ — a deadline + discharge predicate + compensation. The cascade-recall saga (§11.6) already uses the obligation machinery.
- **Corporate action during the open window**: see §6.
- **Cross-currency**: see §7. Reduces to one parent obligation containing two child settlement obligations, one per currency leg. Settled iff both children Settled within their respective windows. The Herstatt risk is *named*, not eliminated.

The mechanism degenerates; the proof obligations specialise.

---

## 4. Reconciliation — lead-lag BY DESIGN

The DS3 identity:

$$
w_A(u)[\text{own}] = \text{depot}_A^{\text{custodian}}(u, t) + \text{InFlight}_A(u, t)
$$

is the reconciliation contract. At any time $t$, the ledger leads the nostro by exactly `InFlight`. At $t_d$, for a clean settlement, `InFlight` for that $\tau$ collapses to zero and the depot catches up.

### The reconciliation pair (per data-spec §15.1 cadence)

| field | source | comparison | tolerance | break-flag |
|---|---|---|---|---|
| $w_A(u)[\text{own}]$ vs $\text{depot}_A^{\text{custodian}}(u, t)$ | ledger vs nostro statement | $w_A(u)[\text{own}] - \text{depot}_A^{\text{custodian}}(u, t) - \text{InFlight}_A(u, t) \stackrel{?}{=} 0$ | 0 (no rounding) | `wf-settlement-break` |

Cadence: T+1 morning (intra-day cycle), and additionally upon each confirmation ingest. The reconciliation is *not* a free-form "compare and investigate"; it is the algebraic identity DS3 with three observable terms. If it fails:

1. Compute $\text{Diff} = w_A(u)[\text{own}] - \text{depot}_A(u) - \text{InFlight}_A(u)$.
2. If $\text{Diff} \ne 0$, exactly one of: (a) a confirmation has been emitted by the CSD but not ingested by the ledger (operational lag); (b) a transaction has been booked by the ledger but `o_settle` was mis-registered (specification bug — DS3-PO violation); (c) the custodian's record genuinely diverges (counterparty break — outside-the-ledger condition).
3. The taxonomy is closed. Each branch has a defined remediation. There is no fourth case where the ledger and the nostro "just disagree".

This is the lead-lag-by-design property: at $t_d^-$ the gap is *expected*, *quantified*, and *temporary*. It is not a break; it is the open obligation. Genuine breaks (case (c)) are the only ones that consume operational attention.

---

## 5. CDM cross-walk

| Ledger artefact | CDM artefact | Notes |
|---|---|---|
| $\tau_{\text{trade}}$ at T | `BusinessEvent` with `EventIntentEnum.OPEN` (execution); `Trade` with `tradeDate = T`, `settlementDate = t_d` | Standard. The settlement date is on the `Trade.tradableProduct.settlementTerms`. |
| `SettlementInstruction` at T (from `settle_projection`) | CDM `TransferState` and ISO 20022 `sese.023` (mapped via CDM synonyms) | The projection $\mu$ to `sese.023` is total on settlement-typed $\tau$ (§8). |
| `SettlStatus` lifecycle | CDM `TransferState.transferStatus` enum | The CDM enum is closed; mapping is total. |
| `o_settle` | **Not represented in CDM.** | Ledger-internal. $L_{15}$ obligation is acknowledged in `ledger_data_v1.0` §15.1 as "CDM cross-walk: Missing (Ledger-internal)". |
| Confirmation ingest | ISO 20022 `sese.025` / `camt.054`; CDM `BusinessEvent` with `transferStatusChange` primitive | The lifecycle event from the CSD enters as a CDM event and updates `SettlStatus`. |
| Buy-in transaction | CDM `BusinessEvent` for the buy-in trade itself; the cost-attribution is a separate CDM `Transfer` | Standard — buy-in is a fresh trade. |

The cross-walk is direct: every state we introduce maps to existing CDM constructs except $o_{\text{settle}}$ itself, and that gap is acknowledged framework-wide ($L_{15}$ has no CDM counterpart). The deferred-settlement design does not introduce a new CDM-shaped object beyond what the framework already lacks.

---

## 6. Failure modes per case

### CSDR fail (mandatory buy-in)

CSDR Article 7 mandates buy-in if a fail persists past T+4 (T+7 for SME-growth-market issuers) or T+15 (illiquid). The κ_settle handler dispatches:

```
κ_settle(τ, failure_type=INSUFFICIENT_SECURITIES) at deadline:
    if days_failed < n_csdr_extension:
        await SubmitToCSD(re_instruct(τ))
        SettlStatus(τ) := Instructed
        # remain on obligation, deadline pushed to next CSDR window
    else:
        buyin_τ = await ExecuteMarketBuyIn(τ.party, τ.unit, τ.qty)
        await ExecutorCommit(buyin_τ)
        # buyin_τ has its OWN settlement obligation, with its OWN deadline
        cost_attrib_τ = await AttributeBuyInCosts(τ, buyin_τ.cost_diff)
        await ExecutorCommit(cost_attrib_τ)
        SettlStatus(τ) := BoughtIn
        o_settle(τ).state := Compensated
```

**Conservation**: the buy-in transaction is a fresh trade with its own conservation discharge. The cost-attribution moves cash between buyer and failed counterparty's virtual wallet — also conservation-preserving. The original $\tau$'s moves are *never* reversed. Position remains correct from $T$.

### Partial settlement

Already in §2.4 case C. Discharge for the settled tranche; spawn $o_{\text{settle\_remainder}}$ for the rest. No anti-moves. Recursive: a remainder can itself partially settle.

### Recon mismatch (operational)

DS3 + the §15.1 reconciliation pair locate the discrepancy. The remediation is:
- Missing confirmation → ingest from CSD or chase via standard ops queue.
- Mis-registered obligation → fix the obligation via a `CORRECTION` to the obligation row (this is allowed; obligations are mutable per $L_{15}$ FSM, in contrast to the move stream).
- Genuine counterparty break → escalation, dispute resolution, eventual `Cancelled` or external legal process.

### Counterparty rejection

```
κ_settle(τ, failure_type=COUNTERPARTY_REJECTION):
    correction_τ = ComputeCancellation(τ)        # anti-moves
    await ExecutorCommit(correction_τ)
    SettlStatus(τ) := Cancelled
    o_settle(τ).state := Compensated
```

The original $\tau$ stays in the move stream. The `correction_τ` carries `replaces_id = tx_id(τ)` in metadata. PnL between $T$ and $t_d$ on the cancelled trade is real and stays in the books — the trade was on, then off; the economic exposure is what it is.

### Short (§13 composition)

A borrowed-share sell is a normal trade with a normal $o_{\text{settle}}$. The borrow is a separate SBL contract with its own obligations (§13 P11–P20). The two compose by parallel obligations on the same underlying unit. **Conservation holds per-leg**; the joint state is verified by §13 Proposition 13.4 (Conservation in the Generalised Model).

If the sell's settlement fails *and* the SBL borrow's recall arrives in the same window: cascade. The recall's compensation triggers a buy-in; the sell's compensation also triggers (potentially the same) buy-in. **Idempotency** at the buy-in deduplicates: a single buy-in transaction services both compensations.

### Recall (§13)

Symmetric to the sell-fail case. The recall's $o_{\text{recall\_return}}$ has the same shape as $o_{\text{settle}}$ with deadline = recall date. The discharge predicate is "borrower's `borr` decreased by $q$ AND lender's `onloan` decreased by $q$ AND collateral released" — a more elaborate predicate but structurally the same.

### Corporate action during the open window

Suppose a stock split is announced effective $t_e$ with $T < t_e < t_d$. The trade $\tau$ recorded at $T$ has $w_A(u)[\text{own}] += 100$. The corporate-action smart contract emits a separate `LIFECYCLE` transaction at $t_e$:

```
τ_split = Transaction(type = LIFECYCLE, t = t_e):
    Move: w_A(u)[own] += 100        # 2-for-1: another 100 added to A's own
    Move: B_virt(u)   -= 100        # contra at the broker virtual wallet for the in-flight portion
```

This preserves conservation, preserves DS3, and means the open obligation $o_{\text{settle}}(\tau)$ now has a *modified* discharge predicate: the CSD will deliver $200$ shares (post-split) at $t_d$, not $100$.

**Proof obligation (DS-CA-PO)**: the discharge predicate for an open obligation must be re-evaluable under bitemporal restatement. Specifically, the `target quantity` field of the predicate must update under the corporate action's StateDelta. This requires the predicate to be a *function on bitemporal state*, not a snapshot value frozen at $T$. The data-spec's bitemporal type ($N_5, N_6, N_9$) supports this; the predicate must cite `with_corrections_through(t_o, t_k')` where $t_o = t_d$ and $t_k'$ is the latest knowledge time.

This is non-trivial and the framework has not been pressure-tested on this case. Named here as a real gap.

### Cross-currency / Herstatt

See §7.

### DvP atomicity

§2.4 already shows DvP at the *ledger* level: one $\tau$, two legs, atomic commit. Settlement-level DvP depends on CSD infrastructure (DTC, Euroclear, Clearstream). The framework guarantees that *if* the CSD delivers DvP, then the ledger's recording is consistent; *if* the CSD fails one leg, the κ_settle dispatches as for a fail.

**Corner case**: CSD reports cash leg `Settled`, securities leg `Failed`. This is a real-world DvP failure (rare but possible at non-DvP CSDs). The ledger's response: the cash and securities legs are part of the *same* $\tau$ and the *same* `o_settle`. The discharge predicate $D_{\text{settle}}$ is a *conjunction* over both legs. If only one leg confirms, $D_{\text{settle}}$ remains false; the obligation is `Attempted`, not `Discharged`; and the failure-type closed sum needs an explicit `LEG_INCONSISTENT` constructor with bespoke compensation (typically: reverse the partial leg via market trade and re-instruct, or escalate to the legal team).

**Proof obligation (DS-DvP-PO)**: the failure-type enumeration must include `LEG_INCONSISTENT`; the κ for it must be defined; totality in DS4 requires this.

---

## 7. Cross-currency (Herstatt) — composition

A USD/JPY FX trade: at $T$ we sell USD, buy JPY, with $t_d^{\text{USD}}$ in NY (afternoon NY) and $t_d^{\text{JPY}}$ in Tokyo (morning Tokyo). The Tokyo leg settles before the NY leg by the calendar; this is the Herstatt window.

### Representation

One $\tau$ at $T$ with two legs (USD leg, JPY leg). One *parent* obligation $o_{\text{fx}}(\tau)$ whose discharge predicate is "both child obligations Discharged":

```
o_fx_parent = Obligation(
    deadline    : max(t_d_USD, t_d_JPY)
    discharge   : o_fx_USD.state = Discharged ∧ o_fx_JPY.state = Discharged
    compensation: HerstattCompensation        # see below
)
o_fx_USD    = child obligation, deadline t_d_USD, discharge = sese.025/camt.054 for USD leg
o_fx_JPY    = child obligation, deadline t_d_JPY, discharge = sese.025/camt.054 for JPY leg
```

### Worked timing

- T (NY morning): trade $\tau$ committed. Both child obligations registered. Both $\tau$'s legs recorded as moves at trade-date.
- $t_d^{\text{JPY}}$ (Tokyo morning): JPY leg settles. `o_fx_JPY → Discharged`. Parent still `Pending`.
- *Herstatt window*: USD has not settled yet; JPY has settled. If the counterparty defaults *during this window* (Bankhaus Herstatt, 1974), USD will never settle, but JPY is already gone from us.
- $t_d^{\text{USD}}$ (NY afternoon): one of:
  - `o_fx_USD → Discharged` → parent → Discharged. Clean.
  - `o_fx_USD → Compensated` (counterparty default during window) → parent → Compensated via Herstatt-specific κ.

### Herstatt compensation

```
HerstattCompensation:
    if exactly one child Discharged and counterparty default observed:
        # We have lost the value of the Discharged leg
        register_loss(value of Discharged leg)
        attempt_recovery_via_insolvency_estate()
        SettlStatus(τ.parent) := Compensated_PartialLoss
```

**Conservation**: holds. The original moves at $T$ are not reversed. The "loss" is recognised by an additional `LIFECYCLE` transaction at the moment of compensation that moves the lost amount from a recovery virtual wallet to a write-off wallet (real, P&L-impacting). Conservation balances by construction.

**The framework cannot prevent Herstatt risk** — this is a real-world timing risk per §2 line 296. What it does:

1. **Names the risk** (the parent obligation makes the joint pendency explicit).
2. **Quantifies the exposure** during the window (via `InFlight` per leg).
3. **Routes the compensation** through the standard machinery.
4. **Audits the loss** at compensation time.

CLS / PvP infrastructure mitigates by changing the real-world settlement mechanism (eliminating the Herstatt window). The ledger model represents whichever real mechanism applies.

---

## 8. Counter-examples — designs that violate one of these properties

### Counter-example 1: "pending_recv coordinate"

*Proposal*: add a 7th coordinate `pending_recv` to the position vector. Trade at $T$ writes to `pending_recv` (not `own`). At $t_d$ on Settled, a `LIFECYCLE` transaction moves the quantity from `pending_recv` to `own`.

*Why it violates*: DS1 (economic exposure at T). PnL $= \sum_u w(u)[\text{own}] \cdot P_t(u)$ — `pending_recv` is excluded. So during $[T, t_d]$, PnL on the open position is zero. Wrong: the worked example demands $\text{PnL}(T+1) = +\$200$.

*Could we just include `pending_recv` in valuation?* Then we have created a *projection* equivalent to `own + pending_recv`, which is exactly `own` after a notational change — Occam's razor: don't introduce a coordinate that has to be re-summed back into `own` for every read. Worse: every margin computation, every risk aggregation, every regulatory report would need to know to include `pending_recv`. C12 (`PositionState[(w, u_MA)]` collapse) and the §13 graceful-degeneration property both forbid this: a coordinate must pass the physical-action test (§13 Principle 13.1) and be load-bearing on its own. `pending_recv` has no physical action that is not also a write to `own`. Reject.

### Counter-example 2: "reverse on fail"

*Proposal*: when `Settled` fails, emit anti-moves to undo $\tau$'s moves. The position reverts to pre-trade.

*Why it violates*: DS1 + §FAQ Q5. The economic exposure existed and existed. The trade was real. Reversing the position misrepresents the firm's economic state during $[T, \text{fail-time}]$ — PnL volatility is faked away, regulatory reports understate exposure, BCBS 239 traceability is broken. Also: which timestamp does the reversal carry? Any choice creates an inconsistent move stream.

The correct response is `Failed` status + κ-dispatched buy-in or cancellation, with the cancellation itself being a fresh transaction whose moves are timestamped at *cancellation time*, not retroactively. Reject.

### Counter-example 3: "single open-window object"

*Proposal*: a new top-level ledger object `OpenSettlement` with its own conservation law, separate from `PositionState` and `L_{15}`.

*Why it violates*: parsimony (StatesHome §3 — three maps, not four), C12 (`W`-sector collapse), and the §13 reasoning that no new sector is justified unless it carries a discipline distinct from the existing three. `OpenSettlement` would be either (a) a `UnitStatus` field on $\tau$ — already what `SettlStatus` is, or (b) an obligation row — already what $o_{\text{settle}}$ is. There is no third discipline. Reject.

### Counter-example 4: "settle the cash leg at T, defer the securities leg"

*Proposal*: split a DvP trade into two transactions. Cash settles immediately; securities at $t_d$.

*Why it violates*: DvP atomicity (§8.4). The conservation argument splits across two transactions, and atomicity (§11 P2) is broken — there exists a state where cash has moved but securities have not. The whole point of DvP at the ledger level is to prevent this. Reject.

### Counter-example 5: "obligation not registered until status change"

*Proposal*: register $o_{\text{settle}}$ only at `Instructed`, not at `Executed`.

*Why it violates*: DS4 (liveness) requires the obligation to exist as soon as a deadline can elapse. If the trade is committed at $T$ but no obligation row exists, an infrastructure failure between commit and instruction would leave a trade that has no liveness guarantee — exactly the gap §13 was written to close. Per Principle 13.5 (Obligation Completeness), the lifecycle function for the trade event must produce the obligation in its output. Reject.

### Counter-example 6: "InFlight stored, not computed"

*Proposal*: store `InFlight` as a coordinate or wallet, updated on every confirmation.

*Why it violates*: §13.1.4 (Definition of `avail` as projection): coordinates pass the physical-action test; projections do not. `InFlight` is fully determined by the obligation log + status flags. Storing it would create a cache that can drift out of sync with the determining state. Compute on read. Reject.

---

## 9. Honest list of unresolved properties (gaps)

These are properties I cannot prove without further constraints or further specification. Each is named, not waved away.

### G1. Closedness of the CSD failure-type enumeration

DS4 (liveness) requires κ_settle to be total over a closed sum of failure types. CSDs in practice publish failure reasons as ISO 20022 status codes, but the practical reason field (`Reason4Choice` etc.) is open-ended in some message variants and free-text in others. Until the framework pins a closed sum (e.g., a normalised internal enum with a residual `OTHER → ESCALATE_HUMAN` sink), DS4 is contingent on a manual-fallback path.

**Required action**: produce a normalised CSD-failure-reason closed sum, with a documented mapping from each CSD's enum, with `OTHER` mapped to a defined human-escalation κ. Pin the enum version (per `ledger_data_v1.0` §3 versioning algebra).

### G2. Confirmation matching in the absence of UTI

DS5 (replay determinism) requires confirmation-to-trade matching to be a *total deterministic function*. In the presence of UTI / EndToEndId discipline, this holds. In their absence (some markets, some failures of the issuer-side reporting), matching is heuristic: same-ISIN-same-counterparty-same-quantity-same-date. This is non-deterministic when multiple trades match. The framework can degrade gracefully (route ambiguous matches to a break register, $L_{18}$), but DS5 is then conditional on "all matches resolved by ingest time".

**Required action**: state the matching contract explicitly. If the contract requires UTI, reject and quarantine non-UTI confirmations to $L_{18}$ rather than forcing a match. Add a property test that ambiguous confirmations are quarantined, never silently mis-matched.

### G3. Bitemporal predicate evaluation under corporate action

§6 (corporate action during the open window) raised this. The discharge predicate $D_{\text{settle}}$ at registration time encodes "100 shares to be delivered". After a 2-for-1 split before $t_d$, the predicate must refer to "200 shares". If the predicate is a closed-over snapshot, the system mis-evaluates at $t_d$.

**Required action**: enforce that all $L_{15}$ discharge predicates are *bitemporal-state-functions*, not snapshot values, and that they read from the latest `with_corrections_through` knowledge time. This is a typing requirement on $L_{15}$ predicate kinds (per `ledger_data_v1.0` §15 `DischargePredicateKind`). Verify by property test: introduce a corporate action between obligation registration and obligation deadline; verify discharge fires correctly.

### G4. DvP leg-inconsistent failure compensation

§6 ("DvP atomicity") raised the `LEG_INCONSISTENT` failure type. The framework can name it but the *correct* compensation is genuinely contingent on the legal regime, the CSD, and operational practice. We cannot prove totality of DS7 (status lifecycle) without committing to a definition.

**Required action**: catalogue per CSD. For DTC: PvP-style — leg-inconsistency is rare and triggers a manual operations workflow. For non-DvP CSDs: more frequent; standard κ is reverse-the-partial-leg-by-market-trade. Capture per CSD in `ReferenceMaster` ($L_{16}$) and dispatch κ accordingly.

### G5. Replay determinism in the presence of restated confirmations

A CSD may restate a confirmation: yesterday "Settled, q=100"; today "Settled, q=60, the rest was a system error". The bitemporal apparatus ($N_9$, restate_link in `BitemporalRecord`) supports this in principle. But a *settlement workflow that already concluded* on yesterday's confirmation cannot be "un-concluded" — Temporal workflow histories are append-only and idempotent in the forward direction, not the reverse.

**Required action**: define how an obligation that has reached `Discharged` reacts to a corrective restatement of its discharging confirmation. Two design choices: (a) treat the restatement as a *new* obligation (clean separation); (b) extend the obligation FSM with a `Reopened` state. Choice (a) is simpler and aligns with append-only discipline; it is the recommendation, but it should be specified explicitly. DS5 currently does not cover this.

### G6. Cross-jurisdiction CSDR vs SEC/T+1 vs T+2

The deadline $t_d$ is jurisdiction-dependent (US T+1 since May 2024, EU T+2 currently, UK T+1 from 2027, Asia mostly T+2). For a global firm with a single ledger, the *same* security on the *same* trade date can have different $t_d$ depending on the venue/CSD. The discharge deadline is therefore a function of $\tau$'s execution venue and clearing path, not of the trade alone.

**Required action**: confirm $t_d$ is sourced from the CDM `tradableProduct.settlementTerms.settlementDate` as resolved by the venue / CSD reference data, not hardcoded. Verify by property test across the closed sum of `MIC × ISIN × CSD` triples.

### G7. The "true at T+2⁻" semantics

"Reconciles to nostro at T+2" in the question is sharp at $t_d^+$ (after the CSD has confirmed). At $t_d^-$ (the morning of T+2 before US/EU CSD batch), the nostro has not been updated; reconciliation at $t_d^-$ deliberately shows InFlight = quantity-of-the-pending-trade. This is *correct* but might surprise an auditor. We should commit to a documentation convention: the "reconciles at T+2" property holds at end-of-day T+2 in the relevant CSD's time zone, after the CSD's batch has run, not at the calendar boundary.

**Required action**: state the time-of-day convention explicitly, anchored to the relevant CSD's batch settlement time. Cite $L_{19}$ ClockAuthority.

### G8. Liveness under prolonged Temporal cluster outage

§13.2.8 already names this: liveness is *eventual* under cluster outage, not instantaneous. For a deferred-settlement obligation specifically, this means: if the cluster is down across $t_d$, the discharge timer fires after recovery, possibly past CSDR penalty windows. The framework cannot eliminate this — stated honestly, the timer fires in the workflow's logical time, not wall-clock time, and external regulatory deadlines tick in wall-clock time.

**Mitigation, not proof**: multi-region replication; an external watchdog (a non-Temporal check that Temporal timers are firing on schedule); an SLA on cluster availability. None of these is a proof; they are operational controls. The proof of DS4 explicitly assumes cluster availability at $t_d$.

---

## 10. Proof obligations the framework MUST discharge

Consolidated list, each tied to its statement above:

| ID | Obligation | Verification means | Status |
|---|---|---|---|
| DS3-PO | `InFlight` is added at T (with `o_settle` registration) and removed exactly on Discharged | Property-based test: random trade sequences; assert DS3 identity at every step | Specifiable |
| DS4-PO | CSD failure-type enumeration is closed | Closed-sum declaration + DRR / ISO 20022 mapping | **Open** (G1) |
| DS5-CM-PO | Confirmation-matching is a total deterministic function | UTI-required gate + $L_{18}$ quarantine for ambiguous | **Open** (G2) |
| DS-CA-PO | Discharge predicates are bitemporal-state-functions | Type discipline on `DischargePredicateKind`; property test | **Open** (G3) |
| DS-DvP-PO | `LEG_INCONSISTENT` failure type defined and compensated | Catalogue per CSD in $L_{16}$ | **Open** (G4) |
| DS5-RST-PO | Restatement of a discharging confirmation is handled | Spec choice (a)/(b) + property test | **Open** (G5) |
| DS-VEN-PO | $t_d$ sourced from CDM, not hardcoded; venue × CSD resolution total | Property test over closed sum of venue × CSD | Specifiable |
| DS10-PO | Joint settlement-status × obligation FSM has no unreachable absorbing path | TLA+ / Alloy model check at $|\mathcal{W}|=3, |U|=2, \text{depth} \le 6$ | Specifiable |
| DS-LIVE-CLUS | Liveness under bounded cluster outage | Multi-region + external watchdog + SLA; **not a proof** | Operational |
| DS-CONS-OPEN | Conservation holds at every state including open-window states | Direct from §11 P1 + move semantics; one-line proof per case in §2 | **Discharged** in §2 |

---

## 11. Worked example (the required one)

100 XYZ @ \$50, T+2. Price moves to \$52 at end-of-day T+1.

### T (trade execution)

```
τ_trade = Transaction(type=SETTLEMENT, t=T, settlement_date=T+2):
    Move: A_cash    → B_virt    USD 5000
    Move: B_virt    → A_equity  XYZ 100

register o_settle = Obligation(
    id="SETTLE_<tx_id>", type=SETTLEMENT_INSTRUCTION,
    deadline=T+2, discharge=Sese025Confirmed(τ, q=100),
    compensation=κ_settle
)
SettlStatus(τ) := Executed
```

State: $w_A(\text{XYZ})[\text{own}] = 100$. $w_A(\text{USD})[\text{own}] = -5000$ (relative). $B_{\text{virt}}(\text{XYZ}) = -100$. $B_{\text{virt}}(\text{USD}) = +5000$. Conservation: $\sum_w w(\text{XYZ}) = 100 - 100 = 0$. $\sum_w w(\text{USD}) = -5000 + 5000 = 0$. **Verified.**

### T+1 (price drift; no moves)

$P_T(\text{XYZ}) = 50, P_{T+1}(\text{XYZ}) = 52$.

$$
V_A(T+1) - V_A(T) = w_A(\text{XYZ}) \cdot (P_{T+1} - P_T) = 100 \cdot (52 - 50) = +200
$$

PnL = +\$200 by §3 Path-Independence Theorem applied to the single non-cash position. **No moves journaled.** State unchanged from T (modulo `SettlStatus(τ) := Instructed` which is journaled as a state-only transaction).

Conservation: trivially preserved (no moves). $\sum_w w(\text{XYZ}) = 0$. **Verified.**

### T+2⁻ (deadline imminent)

State: identical to T+1 modulo price. `SettlStatus = Instructed`. `o_settle.state = Pending`. `InFlight_A(\text{XYZ}) = +100, InFlight_A(\text{USD}) = -5000$.

DS3 reconciliation at T+2⁻:
$$
w_A(\text{XYZ})[\text{own}] = 100, \quad \text{depot}_A^{\text{custodian}}(\text{XYZ}, T+2^-) = 0, \quad \text{InFlight}_A(\text{XYZ}, T+2^-) = +100
$$
$$
100 - 0 - 100 = 0 \quad \checkmark
$$

The ledger leads the nostro by exactly the open obligation. By design.

### T+2⁺ (clean settlement)

Confirmation `sese.025` arrives, $q = 100$, matched to $\tau_{\text{trade}}$ via UTI. Discharge predicate fires.

```
τ_confirm = Transaction(type=LIFECYCLE, t=T+2):
    -- no moves
    state_delta:
        SettlStatus(τ_trade) := Settled
        o_settle(τ_trade).state := Discharged
```

DS3 at T+2⁺:
$$
w_A(\text{XYZ})[\text{own}] = 100, \quad \text{depot}_A^{\text{custodian}}(\text{XYZ}, T+2^+) = 100, \quad \text{InFlight}_A(\text{XYZ}, T+2^+) = 0
$$
$$
100 - 100 - 0 = 0 \quad \checkmark
$$

Reconciliation holds; the lead-lag has collapsed; the trade is settled.

Conservation across the entire workflow: every move journaled was conservation-preserving (the only moves were the two trade legs at T). The confirmation was move-less. Conservation at every state, including the open-window state at T+1 and T+2⁻, was preserved. **Verified.**

PnL between T and T+2⁺: +\$200 (price drift) + 0 (settlement is move-less) = +\$200. By construction.

---

## 12. Summary in one paragraph

Deferred settlement is a *status overlay and an obligation overlay* on the existing closed ledger, not a new ledger sector. The position vector reflects the trade at T (DS1, trade-date accounting). Conservation holds at every state including open-window states (DS2, by inheritance from the move semantics). The ledger leads the nostro by exactly $\text{InFlight}$, the algebraic sum of open settlement obligations (DS3, lead-lag by design). Every obligation reaches a terminal state by its deadline (DS4, by inheritance from §13 Theorem 3.6). Confirmations are commutative across distinct obligations and idempotent within (DS5, DS6). The status FSM is total and capability-scoped (DS7, DS9). The reachable joint state space is small and model-checkable (DS10). The mechanism degenerates: T+1 is T+2 with a different deadline; DvP is a single transaction with two legs; FOP drops the cash leg; CSDR fails dispatch through κ_settle to buy-in; partials fork the obligation; corporate actions update the discharge predicate bitemporally; cross-currency Herstatt is a parent obligation over per-leg children, naming but not eliminating the timing risk; short composes with SBL via parallel obligations; recall is structurally identical. **Six properties (DS4-PO, DS5-CM-PO, DS-CA-PO, DS-DvP-PO, DS5-RST-PO, DS-VEN-PO) are real proof obligations the framework must discharge before this design is sound; one (DS-LIVE-CLUS) is operational, not provable.** None of the six is a design defect; each is a specification gap that can be closed by committing to a closed sum, a typing rule, or a property-based test.

— FORMALIS, R. Delloye agent harness, Phase 1 (independent), no cross-talk.
