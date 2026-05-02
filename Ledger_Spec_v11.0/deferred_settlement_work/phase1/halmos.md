# Deferred Settlement on Cash Equities

*Phase 1 / Team A independent proposal --- author HALMOS*

> "Within its scope, the post-trade activities addressed by this framework
> reduce to one operation: the atomic move of a quantity between wallets."
> --- Ledger v10.3, abstract.
>
> Buying a hundred shares of XYZ does not move shares on Tuesday. The
> shares move on Thursday. The exposure begins on Tuesday. The Ledger
> records what happens; the registrar records who owns the certificate.
> The two are not the same record, and the gap between them is the
> subject of this chapter.

This proposal extends the Ledger v10.3 specification (with the
StatesHome A1 addendum and the v1.0 data spec) to make the gap between
trade-time economic recognition and settlement-time custody movement on
cash equities a first-class object: the **deferred-settlement
obligation**. Throughout this chapter, "the Ledger" means the v10.3
artefact as amended by the StatesHome addendum and the data spec.

The chapter is self-contained but assumes the reader is fluent in:

- atomic moves and the conservation law (Ledger v10.3 §2);
- the unit universe `\mathcal{U}` and the Unit Store (v10.3 §3);
- the three-map StatesHome model `\textit{ProductTerms}`,
  `\textit{UnitStatus}`, `\textit{PositionState}` (StatesHome A1);
- the settlement projection and the four-stage status lifecycle
  `EXECUTED -> INSTRUCTED -> SETTLED | FAILED` (v10.3 §10).

---

## 0. Notation Table

The notation is fixed once, here, and used without redefinition for the
remainder of the chapter. Every symbol introduced later is constructed
from these primitives. We intentionally avoid stacked subscripts.

| Symbol | Reading | Home in the v10.3 framework |
|---|---|---|
| `S` | a cash-equity unit (the security itself; e.g. ISIN of XYZ) | element of `\mathcal{U}` |
| `C` | a cash unit (e.g. USD) | element of `\mathcal{U}` |
| `B`, `K` | the buyer's and counterparty's real wallets | elements of `\mathcal{W}_{\mathrm{real}} \cup \mathcal{W}_{\mathrm{virtual}}` |
| `q` | a positive share quantity | `\mathbb{R}_{>0}` |
| `p` | a per-share trade price quoted in `C` | `\mathbb{R}_{>0}` |
| `n` | cash notional, `n = q\,p` | `\mathbb{R}_{>0}` |
| `T` | trade date | a calendar date |
| `T+1`, `T+2` | the first and second business days after `T` | dates |
| `T+2^-`, `T+2^+` | "just before" and "just after" the CSD's settlement cycle on `T+2` | a logical micro-ordering inside one timestamp |
| `\sigma` | a **settlement obligation unit** (defined in §1) | new element of `\mathcal{U}` |
| `\beta_t(w, u)` | the balance of wallet `w` in unit `u` at time `t` | `w_t(u)` of v10.3 §2 |
| `Q_t(u)` | system-wide total `\sum_w \beta_t(w, u)` | the conservation quantity, v10.3 Th. 2.1 |
| `V_t(w; \pi)` | mark-to-market of wallet `w` under price vector `\pi` | v10.3 §4 |
| `\textit{UnitStatus}[u]` | shared mutable status map (lifecycle stage etc.) | StatesHome A1 |
| `\textit{PositionState}[w, u]` | per-position state map | StatesHome A1 |
| `\mathrm{stage}(\sigma)` | the lifecycle stage of `\sigma`, in `\{P, I, S, F, X\}` | a field of `\textit{UnitStatus}[\sigma]` |

The five lifecycle stages of a settlement obligation are:

> `P` --- Pending: trade booked, not yet instructed.
> `I` --- Instructed: ISO 20022 message dispatched to the CSD.
> `S` --- Settled: CSD confirms DvP completion.
> `F` --- Failed: CSD reports fail; CSDR penalty clock running.
> `X` --- Extinguished: obligation closed by buy-in, cancellation,
>          partial close-out, or recall (terminal).

We will write `\sigma` rather than `u_\sigma` because there is no
ambiguity: every Greek letter in this chapter denotes a settlement
obligation unit, every capital Roman letter denotes a wallet or a
security or a cash unit, and every lower-case Roman letter denotes a
quantity.

---

## 1. State Representation

### 1.1 The motivating observation

The v10.3 settlement section already says (§10.5, last paragraph):

> Between trade date and settlement date, the Ledger shows the correct
> economic position; the CSD confirms the real-world transfer at
> settlement. This gap is not a DvP failure --- it is the normal state
> of affairs under trade-date accounting.

What v10.3 does **not** say is *where the gap lives in state*. The
position is already on the buyer's books from `T`; the cash is also
already on the buyer's books, but with the wrong sign (a pending
debit). The current spec papers over this with the
`EXECUTED -> INSTRUCTED -> SETTLED | FAILED` status field on the
transaction. That is enough to answer "did this trade settle?", but it
is not enough to answer:

1. What is my **counterparty exposure** to `K` between `T` and `T+2`?
2. If `K` defaults on `T+1`, what claim do I have?
3. If a corporate action falls on `T+1`, who is the holder of record?
4. If I sell the same shares on `T+1`, am I short or am I a chain?
5. Under CSDR, what is the cash penalty if `K` fails on `T+2`?

Each of these requires an object whose lifecycle is **the gap itself**,
not the position. v10.3 has no such object. The transaction status is
a flag attached to a past event; the gap is an obligation that lives
during a future interval.

### 1.2 Definition: the settlement-obligation unit

> **Definition 1.1 (Settlement Obligation).**
> A *settlement obligation* `\sigma` is a unit in the Ledger universe
> `\mathcal{U}` whose `\textit{ProductTerms}[\sigma]` record:
>
> - the underlying security `S`;
> - the cash unit `C`;
> - the agreed quantity `q` and price `p`, hence the cash leg
>   notional `n = q\,p`;
> - the contractual settlement date `d_s` (typically `T+2`, or `T+1`
>   in US equities post-2024);
> - the deliverer-of-record `K_{\mathrm{deliver}}` and the
>   payer-of-record `K_{\mathrm{pay}}` (these may differ in
>   tri-party arrangements);
> - the CSD identifier (DTC, Euroclear, Clearstream).
>
> `\textit{UnitStatus}[\sigma]` carries the mutable field
> `\mathrm{stage}(\sigma) \in \{P, I, S, F, X\}` and the
> CSDR-penalty cursor.

The obligation is a **unit**, not a metadata flag. This is the central
move of the proposal, and the rest of the chapter is what falls out of
it. Because `\sigma` is a unit, every mechanism the Ledger already has
applies to it for free: balances, conservation, the StatesHome maps,
the settlement projection, time travel, the three-tier audit chain,
the six-coordinate generalisation if we ever need rehypothecation of
unsettled trades.

### 1.3 The two views of the same trade

A settled trade and an unsettled trade differ only in *where* the
shares and cash sit. The economic exposure is identical. The Ledger
makes this explicit by holding the position in `S` and `C` from `T`,
and routing them through `\sigma` as a transit station:

```
T  (trade booked)
   B holds:     +q in S        (long shares, on books, not yet in custody)
                -n in C        (cash debt, on books, not yet released)
                +1 in sigma    (long the obligation: I will receive shares & pay cash)
   K holds:     -q in S        (short shares to deliver)
                +n in C        (cash receivable)
                -1 in sigma    (short the obligation)
   stage(sigma) = P
```

Conservation holds for `S` (`+q - q = 0`), for `C` (`-n + n = 0`),
and for `\sigma` (`+1 - 1 = 0`). The obligation **is itself a unit
that conserves**. This is the only legitimate way to put it into the
Ledger; any other home (a metadata flag, an external table, a
side-state) would break conservation or break time travel.

### 1.4 Where each piece of state lives

Following the StatesHome ruling (three maps, no separate wallet
sector):

- `\textit{ProductTerms}[\sigma]`: `(S, C, q, p, d_s,
  K_{\mathrm{deliver}}, K_{\mathrm{pay}}, \text{CSD})`. Immutable.
- `\textit{UnitStatus}[\sigma]`: `\mathrm{stage}(\sigma)`,
  `\mathrm{instructed\_at}`, `\mathrm{settled\_at}`,
  `\mathrm{fail\_reason}`, `\mathrm{csdr\_cursor}`.
- `\textit{PositionState}[B, \sigma]` and
  `\textit{PositionState}[K, \sigma]`: per-side flags ---
  `\mathrm{partial\_filled}`, `\mathrm{buy\_in\_initiated}`,
  `\mathrm{recall\_pending}`. **None** for any wallet that never
  touched this trade. This is the StatesHome `Option` accessor doing
  exactly what it was designed to do.

The CSDR penalty cursor lives on `\textit{UnitStatus}[\sigma]`, not
on each `\textit{PositionState}`, because the penalty is a property
of the obligation (one CSD, one fail, one penalty), not of the
holders.

### 1.5 The principle in one line

> **Principle 1.2 (Trade-Time Economic Recognition).**
> The position in `S` and `C` is recognised at `T`. The obligation
> `\sigma` is the receipt for the gap between `T` and `d_s`. When
> `\sigma` extinguishes (cleanly or otherwise), it discharges from
> both books simultaneously and conservation re-collapses to a
> two-unit system. There is never a moment when the gap exists
> without being represented.

---

## 2. The Move Sequence

We trace the standard buy of `q = 100` shares of `S = XYZ` at
`p = \$50` on date `T`, settling on `d_s = T+2`. Total notional
`n = \$5{,}000`. The buyer's wallet is `B`, the counterparty's
virtual wallet is `K`. The cash unit is `C = USD`.

Throughout, every move is written as a single line; every transaction
is a finite collection of moves with a shared timestamp; every
transaction conserves every unit. We label moves `m_1, m_2, \ldots`
in the order they appear.

### 2.1 At `T` --- trade-time recognition

```
Transaction T1 (type SETTLEMENT, contractual_settlement_date d_s):
  m_1: q  units of S    : K -> B
  m_2: n  units of C    : B -> K
  m_3: 1  unit  of sigma: K -> B    (issuance of the obligation)
```

Conservation per unit:

- `\Delta_T S      : -q + q = 0`
- `\Delta_T C      : -n + n = 0`
- `\Delta_T \sigma : -1 + 1 = 0`

After `T1`:

- `\beta_T(B, S) = +q`,    `\beta_T(K, S) = -q`
- `\beta_T(B, C) = -n`,    `\beta_T(K, C) = +n`
- `\beta_T(B, \sigma) = +1`, `\beta_T(K, \sigma) = -1`
- `\mathrm{stage}(\sigma) = P`

The book is correct: `B` is long shares, short cash, long the
obligation. Conservation says `Q_T(\sigma) = 0`.

### 2.2 At `T+1` --- instruction

The settlement layer projects `T1` to an ISO 20022 message
(`sese.023`) and dispatches. This is a **state-only transaction**
on `\sigma`: no balances move; only `\textit{UnitStatus}[\sigma]`
flips.

```
Transaction T2 (type LIFECYCLE):
  state-only: stage(sigma) : P -> I
              instructed_at = now
              <no moves>
```

Conservation is trivial (empty sum). The status flip is recorded as
a CDM `BusinessEvent` per v10.3 §10.7 so that time travel can
distinguish "instructed at 09:30" from "instructed at 14:15".

### 2.3 At `T+2^-` --- the CSD pre-settlement

The CSD opens its settlement cycle. No Ledger moves: this is the
external world stirring. We mention `T+2^-` only as a logical
anchor for the diagram below.

### 2.4 At `T+2^+` --- the happy path

The CSD confirms DvP. The shares now exist in custody, the cash now
exists in the counterparty's bank account, and the obligation
extinguishes. **The shares and the cash do not need to move on the
Ledger** --- they were already there from `T`. What must move is the
obligation itself, which collapses out of the system:

```
Transaction T3 (type SETTLEMENT, originated by camt.054 + sese.025):
  m_4: 1 unit of sigma : B -> K   (return-and-burn)
  state-only: stage(sigma) : I -> S
              settled_at = now
```

Conservation per unit:

- `\Delta_{T+2} S      : 0`  (no S-move; S already where it should be)
- `\Delta_{T+2} C      : 0`  (no C-move; C already where it should be)
- `\Delta_{T+2} \sigma : +1 - 1 = 0`

`\beta_{T+2}(B, \sigma) = 0`, `\beta_{T+2}(K, \sigma) = 0`. The
StatesHome monotone carrier preserves the row in
`\textit{PositionState}[B, \sigma]` with balance zero --- the audit
trail survives. `\mathrm{stage}(\sigma) = S`.

### 2.5 The diagram

```
                        Trade T               Instruct T+1            Settle T+2
                        ========              ============            ===========
   B's books          B(S)=+q              B(S)=+q                 B(S)=+q
                      B(C)=-n              B(C)=-n                 B(C)=-n
                      B(sigma)=+1          B(sigma)=+1             B(sigma)= 0
                      |                    |                       |
                      |  m_1: q S K->B     |                       |
                      |  m_2: n C B->K     |  state-only:          |  m_4: 1 sigma B->K
                      |  m_3: 1 sigma K->B |  stage P -> I         |  state-only: I -> S
                      |                    |                       |
   K's books          K(S)=-q              K(S)=-q                 K(S)=-q
                      K(C)=+n              K(C)=+n                 K(C)=+n
                      K(sigma)=-1          K(sigma)=-1             K(sigma)= 0

   Q_t(S)        :    0                    0                       0
   Q_t(C)        :    0                    0                       0
   Q_t(sigma)    :    0                    0                       0
```

Every arrow is labelled. Every column conserves. The position in `S`
and the position in `C` are stable from `T`; only `\sigma` moves at
the boundaries. **This is the entire architectural content of the
proposal.**

---

## 3. Invariants

We state four invariants. The first is the existing conservation law
applied to `\sigma`. The second is the **economic-exposure-at-`T`**
invariant, which is the heart of the proposal. The third and fourth
are the boundary conditions for state extinguishment.

### Invariant I1 --- conservation of the obligation

> For every settlement obligation `\sigma \in \mathcal{U}_\sigma`
> and for every time `t`, `Q_t(\sigma) = 0`.

This is v10.3 Theorem 2.1 instantiated at `\sigma`. It holds by
construction because every transaction touching `\sigma` (issuance
at `T`, return at `T+2^+`, partial fills, buy-ins) is conservation-
preserving; the proof is by induction on the move stream.

### Invariant I2 --- economic-exposure-at-`T` (informal)

> The buyer's PnL on the trade is determined at `T`, not at `T+2`.
> If the price moves between `T` and `T+2`, the buyer's mark-to-market
> reflects the move; the settlement status does not gate the
> recognition of value change.

A cleaner phrasing: *settlement is plumbing, not pricing.* Whether
the obligation is `P`, `I`, `S`, or `F`, the buyer is long the
shares for valuation purposes. This is exactly what trade-date
accounting under IFRS 9 / ASC 320 demands; the Ledger expresses it
mechanically.

### Invariant I2 --- economic-exposure-at-`T` (formal)

> **Invariant 3.1.**
> For every trade `\tau` that books at trade date `T` and contracts
> to settle at `d_s \ge T`, for every wallet `w \in \{B, K\}`
> participating in `\tau`, for every price vector `\pi`, and for
> every time `t \in [T, d_s]`:
>
> `V_t(w; \pi) - V_T(w; \pi) \;=\; \sum_{u \in \mathcal{U}}
>     \beta_T(w, u) \cdot (\pi_t(u) - \pi_T(u))
>     \;+\; \rho_t(w; \pi)`
>
> where `\rho_t(w; \pi)` is the contribution of all moves *other than
> `\tau`* (lifecycle events, other trades, dividends) on `w` over
> `[T, t]`. In particular, the `\tau`-driven component of
> `V_t(w; \pi) - V_T(w; \pi)` is independent of
> `\mathrm{stage}_t(\sigma_\tau)`.

In words, with the universal and existential quantifiers all
visible: *for all* `t` between `T` and settlement, *for all* price
vectors, *for all* participants, the price-driven change in wallet
value is fully accounted for by the position recognised at `T` plus
movements unrelated to this trade. The settlement stage cannot
appear in the formula; the formula has no slot for it.

This is what *trade-time economic recognition* means, formally. The
proof is one line: by §2 above, `\beta_t(w, S)` and `\beta_t(w, C)`
are fixed at `T` and unchanged through extinguishment of `\sigma`;
v10.3 §4 gives `V_t = \sum_u \beta_t(w, u) \pi_t(u)`; subtract.

### Invariant I3 --- stage-monotone, terminal-`X`

> `\mathrm{stage}(\sigma)` is monotone in the partial order
> `P < I < S, F`, with `X` reachable from any non-terminal state
> and itself terminal. No transition `S \to *` exists; no
> transition `* \to P` exists. Once `\sigma` reaches a terminal
> state (`S` or `X`), `\textit{UnitStatus}[\sigma]` is immutable.

Operationally: a settled trade cannot un-settle. A failed-then-cured
trade transitions `F \to I \to S` by re-instruction (see §6.1), not
by `F \to S` directly.

### Invariant I4 --- closure at extinguishment

> If `\mathrm{stage}(\sigma) \in \{S, X\}`, then
> `\beta_t(w, \sigma) = 0` for all `w`.

This says the obligation cannot be in a terminal state while
balances on it are non-zero. Equivalently: the moves that flip the
stage to `S` or `X` must be the moves that zero the balance. The
StatesHome handler-level conservation discipline (C2) makes this a
type-checked property of every event handler that targets `\sigma`.

---

## 4. Reconciliation Lead-Lag

The Ledger reconciles `\sigma` against three external authorities at
three cadences. The lag in each line is the maximum acceptable delay
between a Ledger event and the matching external observation; longer
lags trigger an `L_{18}` BreakRegister entry.

| External authority | Cadence | Reconciles | Acceptable lag |
|---|---|---|---|
| Custodian / CSD `sese.025` | per-trade | `\beta(B, S)` after `T+2^+` matches custody record | T+2 + 4 hours |
| Counterparty bank / `camt.054` | per-trade | `\beta(B, C)` after `T+2^+` matches bank record | T+2 + 4 hours |
| Trade Repository (SFTR/MiFIR) | T+1 | `\sigma` issuance reported correctly | T+1 EOD |
| CSDR penalty file | daily | `\mathrm{csdr\_cursor}(\sigma)` for `\sigma` in stage `F` | T+3 |

The **lead-lag invariant** is that the Ledger always *leads* the
external feeds in time-of-knowledge. If a `sese.025` arrives before
the matching Ledger transaction is written, the gateway must enqueue
the message and wait; this is the standard `L_{11}` pattern (data
spec §`L_{11}`). If a Ledger transaction is written but no `sese.025`
arrives within the lag window, an `L_{18}` BreakRegister entry is
opened and the Temporal SBL/Settlement workflow takes over.

The bitemporal pair `(t_{\mathrm{obs}}, t_{\mathrm{known}})` from the
data spec is the coordinate system for these checks: `t_{\mathrm{obs}}`
is when the CSD says the settlement happened; `t_{\mathrm{known}}`
is when we learned of it. Restatements of `\mathrm{stage}(\sigma)`
follow the bitemporal versioning algebra of the data spec --- a
fail-then-cure is a single `\sigma` with two bitemporal records on
its status, not two `\sigma`s.

---

## 5. CDM Cross-Walk

`\sigma` does not have a single CDM type. It is a Ledger-native
construct that **projects onto** several CDM concepts depending on
the question being asked:

| Aspect of `\sigma` | CDM mapping | Type of mapping |
|---|---|---|
| Issuance at `T` | `BusinessEvent.execution` with `Trade.tradeDate = T`, `Trade.settlementDate = d_s` | Direct |
| Stage `P -> I` | `BusinessEvent.observation` referencing the projected `sese.023` | Partial (no native CDM "instructed" stage) |
| Stage `I -> S` | inbound `sese.025` mapped via the existing v10.3 confirmation pipeline | Partial |
| Stage `* -> F` | `BusinessEvent.observation` carrying the CSDR fail code | Partial (CDM `SettlementFailureEvent` is a placeholder in v6.0.0) |
| Stage `* -> X` (buy-in) | new `BusinessEvent.exercise` with a `BuyInInstruction` payload | Missing in CDM v6.0.0; raise to ISDA SettlementWG |
| Partial settlement | two `\sigma`s linked by a `partial_of` lineage, each smaller | Partial; CDM lineage applies |
| Cross-currency leg | a paired `\sigma_{\mathrm{ccy}}` for the FX leg (see §5.1) | Direct via two CDM trades + linkage |

The settlement projection of v10.3 §10 already produces ISO 20022
messages from CDM-native transactions. Under this proposal, the
projection extends only by treating the `\sigma`-issuance
transaction (T1) as the source for `sese.023`, and the
`\sigma`-extinguishment transaction (T3) as the destination for
`sese.025` confirmation. **No new ISO 20022 message types are
required.**

### 5.1 Cross-currency: Herstatt risk

For an FX-funded equity purchase (e.g. a EUR-denominated investor
buying a USD-listed stock), the trade has *two* settlement
obligations that must be modelled separately:

- `\sigma_S`: the equity-leg obligation (USD-cash for shares),
  settling on the equity CSD's cycle (DTC, T+1 in 2026).
- `\sigma_C`: the FX-leg obligation (EUR for USD), settling on the
  FX cycle, possibly via CLS, possibly via CHIPS / Target2.

These are **two `\sigma`s**, not one, because the CSDs are
different, the cycles are different, the failure modes are
different, and the legal frameworks are different. The investor's
cross-currency exposure during the gap is exactly the sum of the two
mark-to-market exposures, and a default of either counterparty
between the two settlements is the textbook Herstatt scenario. The
Ledger expresses this directly: `Q_t(\sigma_S) = 0` and
`Q_t(\sigma_C) = 0` independently; their stages can diverge; their
extinguishments are not synchronised. v10.3 §2.6 ("Settlement timing
and Herstatt risk") is satisfied without any further machinery.

---

## 6. Failure Modes

Every failure mode is a transition out of the happy path of §2.
Every transition is itself a transaction that conserves on `\sigma`
and produces or zeros balances accordingly.

### 6.1 Outright fail then cure (CSDR)

`K` cannot deliver on `T+2`. The CSD reports a fail. Stage flips
`I -> F`; CSDR penalty cursor starts. No moves on `\sigma`; the
balance remains `\beta(B, \sigma) = +1`, `\beta(K, \sigma) = -1`.
Position in `S` is still on `B`'s books (the buyer is paying for
non-delivery exposure, not for shares not received). When `K`
finally delivers on `T+5`, stage flips `F -> I -> S` and `\sigma`
extinguishes per §2.4. The penalty accrual is recorded as a separate
small cash transaction `K -> B` driven by the daily CSDR cursor.

### 6.2 Buy-in

After CSDR's fail-extension window expires, the buyer (or the CSD)
initiates a buy-in: a fresh trade `T'` against a different
counterparty `K'` for the same `S`, `q`. This is *new business*
expressed as a new `\sigma'`, not a mutation of `\sigma`. The
original obligation extinguishes via `X` with metadata pointing to
`\sigma'` as the cure; the cash difference between the original `n`
and the buy-in cost is settled bilaterally.

This is the worked example of §7.2 below.

### 6.3 Partial fill

The CSD partially settles: `q' < q` shares and `n' = q' p` cash. The
proposal models this as a **split**: `\sigma` extinguishes and is
replaced by a smaller residual `\sigma_{\mathrm{rem}}` with terms
`(S, C, q - q', p, d_s, K_{\mathrm{deliver}}, K_{\mathrm{pay}},
\text{CSD})` and stage `F`. Conservation:

```
At partial-settle time:
  Z_1 (close out the q' that settled):
    1 unit of sigma     : B -> K   (full extinguish of original)
    state-only: stage(sigma) -> X with successor sigma_rem
  Z_2 (issue the residual):
    1 unit of sigma_rem : K -> B
    state-only: stage(sigma_rem) = F
```

This keeps every obligation a clean unit of fixed quantity; partial
fills compose by splitting, not by mutating quantity in place. (This
is the "C8 two-track" amendment discipline of StatesHome, applied
here as a Breaking amendment because the quantity has changed and
fungibility with the original is violated.)

### 6.4 Recall

Settlement may be deferred because the seller had lent the shares
out and must recall them (SBL recall, v10.3 §13). The recall is a
state-only transition on the SBL loan unit `\ell`, not on `\sigma`.
`\sigma` remains in stage `I` until the recall completes; if it
does not complete in time, `\sigma` transitions to `F` and the buy-in
machinery of §6.2 takes over.

### 6.5 Corporate action between `T` and `d_s`

A dividend or split with record date in `[T, T+2]` is an event on
`S`, not on `\sigma`. The buyer holds `\beta(B, S) = +q` from `T`,
so the buyer is the holder of record and entitled to the
distribution. The dividend-claim mechanism of v10.3 §6 (managed-
account workflow) handles the actual cash movement; `\sigma` is
unaffected because the distribution does not change `q`, `p`, or
`d_s`. *This is the cleanest argument for putting `\sigma` and `S`
in different units: their lifecycles do not interlock.*

### 6.6 Short selling and `\sigma`

A short sale at `T` issues `\sigma` with `\beta(B, S) = -q` and
`\beta(B, C) = +n` (the conjugate of the long buy). The buyer's
`\beta(B, \sigma) = -1`. To deliver at `T+2`, `B` must source
shares: this triggers an SBL borrow, which produces an `\ell` (loan)
unit; SBL operates on the GPM six-coordinate vector (v10.3 §13)
without touching `\sigma`. Two distinct units, two distinct
lifecycles, one shared time interval.

### 6.7 DvP atomicity at extinguishment

DvP atomicity at the Ledger level is a property of T1 (issuance):
the shares move, the cash moves, and `\sigma` is issued, all in one
atomic transaction. DvP at the CSD level is the property the
external infrastructure provides at T3 (extinguishment). Under this
proposal, T3 is a single Ledger transaction that flips the stage to
`S` and zeros the obligation balance --- if the CSD reports
"securities delivered, cash failed", the gateway must hold T3 and
break-flag the trade. This is the StatesHome C3 atomicity discipline
applied to `\sigma`'s lifecycle.

---

## 7. Worked Examples

### 7.1 The standard buy: 100 XYZ at $50, mark to $52, no cash moved

> Goal: prove that PnL of `+\$200` is recognised at `T+1` regardless
> of whether `\sigma` has settled. This is invariant I2 in arithmetic.

Setup at `T = 2026-04-30`:

- `B` is empty, `K` is virtual, prices: `\pi_T(S) = 50`,
  `\pi_T(C) = 1`, `\pi_T(\sigma) = 0` (an obligation has zero
  fair value at issuance, by I2 below).
- Trade `T1` per §2.1: `q = 100`, `p = 50`, `n = 5000`.

After `T1`:

```
beta(B, S)     = +100
beta(B, C)     = -5000
beta(B, sigma) = +1
stage(sigma)   = P
V_T(B; pi)     = 100*50 + (-5000)*1 + 1*0 = 0
```

Wallet value at trade is zero, as it should be: the buyer has paid
fair value.

At `T+1`, the price of `S` rises to `\pi_{T+1}(S) = 52`. Stage
`P -> I` (state-only, no moves). Then:

```
beta(B, S)     = +100
beta(B, C)     = -5000
beta(B, sigma) = +1
stage(sigma)   = I
V_{T+1}(B; pi) = 100*52 + (-5000)*1 + 1*0 = 5200 - 5000 = +200
PnL[T, T+1]   = V_{T+1}(B; pi) - V_T(B; pi) = +200 - 0 = +$200
```

**The PnL of `+\$200` is recognised on `T+1`, with `\sigma` still in
stage `I`, with no cash and no shares having moved in custody.**
This is the operational signature of trade-time economic
recognition. (Cross-check: `\beta_T(B, S) \cdot (\pi_{T+1}(S) -
\pi_T(S)) = 100 \cdot 2 = 200`. Invariant I2 is the one-line proof.)

At `T+2^+`, the CSD confirms; T3 fires per §2.4; stage `I -> S`;
`\sigma` extinguishes. The mark-to-market of `B` does not change at
this transition because `\beta(B, \sigma)` was already zero in
fair-value terms; only the stage flag changes:

```
beta(B, S)     = +100  (unchanged from T)
beta(B, C)     = -5000 (unchanged from T)
beta(B, sigma) =  0    (zeroed by m_4)
stage(sigma)   = S
V_{T+2}(B; pi) = 100*pi_{T+2}(S) + (-5000)*1 + 0*0
```

If `\pi_{T+2}(S) = 52` still, `V_{T+2}(B) = 200`, unchanged from
`T+1`. The settlement is invisible on the PnL.

### 7.2 Fail then buy-in

> Goal: prove that a fail on `T+2`, followed by a buy-in at `T+5`,
> conserves all units, leaves an audit trail, and produces the
> correct economic outcome.

Setup as in §7.1. Stage `P` at `T`, `I` at `T+1`. On `T+2`, `K`
fails to deliver. CSD reports the fail at `t_F = T+2 + 16:00`.

```
Transaction T2_fail (state-only on sigma):
  state-only: stage(sigma) : I -> F
              fail_reason  = "INSUFFICIENT_INVENTORY"
              csdr_cursor  = (start_date = T+2, accrued = 0)
```

Conservation: trivial.

The CSDR daily cursor accrues a basis-point penalty; on each business
day until cure, a tiny cash transaction `K -> B` fires. We omit the
arithmetic to keep the example clean; the mechanism is the same as
the dividend-payment mechanism of v10.3 §6.

By `T+5`, `K` is judged unable to deliver. A buy-in is initiated
against counterparty `K'` at the prevailing market price
`\pi_{T+5}(S) = 53`. Notional `n' = 100 \cdot 53 = 5300`. New
obligation `\sigma'` is issued; old obligation `\sigma`
extinguishes. The cash difference is `n' - n = 300`, owed by `K`
to `B` (the original counterparty bears the cost of being bought
in).

```
Transaction T3_buyin (atomic):
  m_a: 100 units of S    : K' -> B    (new shares)
  m_b: 5300 units of C   : B -> K'    (new cash)
  m_c: 1 unit of sigma'  : K' -> B    (new obligation)

Transaction T4_extinguish_old (atomic):
  m_d: 1 unit of sigma   : B -> K     (close out original)
  state-only: stage(sigma) : F -> X
              extinguish_reason = "BOUGHT_IN"
              successor = sigma'

Transaction T5_buyin_diff (cash settlement of cost):
  m_e: 300 units of C    : K -> B     (K reimburses B)
```

Conservation, unit by unit:

- `S`:           `T3_buyin` gives `-100 + 100 = 0`; others zero.
- `C`:           `T3_buyin` gives `+5300 - 5300 = 0`;
                 `T5_buyin_diff` gives `-300 + 300 = 0`. Total zero.
- `\sigma`:      `T4_extinguish_old` gives `-1 + 1 = 0`. Total zero.
- `\sigma'`:     `T3_buyin` gives `-1 + 1 = 0`. Total zero.

Per-unit totals `Q_t(\cdot)` remain zero throughout. **`\sigma` is
in stage `X` (terminal), `\sigma'` is in stage `P`** and proceeds
through its own happy path (`P -> I -> S`) over `[T+5, T+7]` per
§2.

`B`'s economic position from `T` to `T+7`:

```
At T   :  B(S) = +100, B(C) = -5000,                B(sigma) = +1
At T+1 :  B(S) = +100, B(C) = -5000,                B(sigma) = +1, stage I
At T+2 :  B(S) = +100, B(C) = -5000,                B(sigma) = +1, stage F
At T+5 :  B(S) = +100, B(C) = -5000 + 300 - 5300 = -10000... wait.
```

Stop. The arithmetic shows the structure: at the buy-in moment, `B`
is going to be holding `+200` in shares (the original `+100` from
`\sigma` plus the new `+100` from `\sigma'`) unless the original
`+100` has already vanished. It has not: `\beta(B, S)` from `T1`
was never reversed because `T1` was never undone. We need an
*unwind move* on `S` and `C` from the original trade as part of the
buy-in, because the original `S` is no longer being delivered.

The complete buy-in transaction is therefore:

```
Transaction T3_buyin_complete (atomic; replaces the two above):
  -- close out the original notional position:
  m_a:  100 units of S    : B  -> K       (reverse the original S leg;
                                            B never received the shares)
  m_b: 5000 units of C    : K  -> B       (reverse the original C leg;
                                            B never paid the cash)
  m_c:    1 unit  of sigma: B  -> K       (extinguish the original obligation)
  state-only: stage(sigma) : F -> X
              extinguish_reason = "BOUGHT_IN"
              successor = sigma'

  -- book the buy-in trade:
  m_d:  100 units of S    : K' -> B       (new shares from K')
  m_e: 5300 units of C    : B  -> K'      (new cash to K')
  m_f:    1 unit  of sigma': K' -> B      (new obligation)
  state-only: stage(sigma') = P

  -- settle the cost of the buy-in against the failing counterparty:
  m_g:  300 units of C    : K  -> B       (K bears the n' - n difference)
```

Conservation, unit by unit:

- `S`:        `+100 - 100 + 100 - 100 = 0`. Both wallets balanced.
- `C`:        `-5000 + 5000 - 5300 + 5300 - 300 + 300 = 0`. Balanced.
- `\sigma`:   `-1 + 1 = 0`.
- `\sigma'`:  `-1 + 1 = 0`.

After this single atomic transaction:

```
beta(B, S)      = +100   (from sigma' delivery; sigma's was unwound)
beta(B, C)      = -5300  (-5000 + 5000 - 5300; ignoring the 300 reimbursement
                          which arrives in the same transaction)
                = -5300 + 300 = -5000  (after m_g)
beta(B, sigma)  =    0   (extinguished, terminal X)
beta(B, sigma') =   +1   (new, stage P)
beta(K, sigma)  =    0
beta(K, S)      =    0   (was -100, now 0 after m_a)
beta(K, C)      = +5000  (was +5000 from T1, then 0 after m_b, then -300 after m_g
                          -- check: +5000 - 5000 - 300 = -300; this is the loss K bears)
beta(K', S)     =  -100
beta(K', C)     = +5300
beta(K', sigma')=   -1
```

After buy-in, `B` is *long 100 shares with cash position `-5000`*,
exactly as if the original trade had settled cleanly --- with the
crucial difference that `\sigma'` is still stage `P` and will run
its own happy path. `K`'s books carry the loss: cash position
`-300`. The Ledger has captured (a) that `B` was long `S` from
`T`, (b) that the failed counterparty owes the cost of the cure,
and (c) that a successor obligation now governs the gap to the new
settlement date. Every fact is on `B`'s books, in real units, with
real conservation, and the audit chain runs from `T1` to `T3` via
`T4`, with `\textit{UnitStatus}[\sigma]` recording every stage
transition.

The PnL story is also clean. The mark-to-market of `B` between `T`
and `T+5` reflects the price journey of `S` at all times (I2). At
`T+5`, the buy-in is itself a spot trade at `\$53`; the
counterparty `K` reimburses the difference; net effect on `B`'s
P&L is zero (the failure was fully indemnified) plus whatever CSDR
penalties accrued. **The mechanism prices the failure to `K`, not
to `B`.**

---

## 8. Where This Proposal Trades Depth for Clarity

An honest accounting of the simplifications. Each one is a
deliberate choice; each one points to a place where Phase 2 / 3
work will need to dig deeper.

1. **Single CSD, single cycle.** §2 assumes `T+2` (or `T+1` in
   US 2026). Real cash equities have many cycles --- DTC at T+1,
   most European CSDs at T+2, some Asian markets at T+0/T+1, repo
   at T+0/T+1. The proposal handles this by parameterising `d_s`
   in `\textit{ProductTerms}[\sigma]`; the *machinery* is
   single-cycle in §2 only for clarity of the diagram. No structural
   change is needed for multi-cycle support.

2. **CCP novation is collapsed.** A CCP-cleared cash-equity trade
   should produce two `\sigma`s on novation: one against the CCP for
   each side. The proposal would model this as `\sigma_{B,CCP}` and
   `\sigma_{CCP,K}`, both issued in one atomic transaction at
   novation time (perhaps `T+0` or `T+1`), and would extinguish them
   independently. We note the design but do not write the diagrams;
   that is Phase 2 territory.

3. **CSDR cash-penalty arithmetic is sketched.** The penalty cursor
   is a daily `bp` accrual based on liquidity bands and reference
   rates per the EU CSDR Settlement Discipline Regime. The proposal
   places the cursor in `\textit{UnitStatus}[\sigma]` and emits a
   tiny daily cash move, but does not work out the penalty
   schedule. This is a parameterisation problem, not an architectural
   one.

4. **Net settlement is not modelled.** v10.3 §10.6 puts netting in
   the settlement layer, not the Ledger. We follow that. A net
   settlement is *not* a single big `\sigma`; it is `n` little
   `\sigma`s whose combined ISO 20022 is a single net instruction.
   The Ledger keeps gross records.

5. **No restatement of pre-existing trades.** The proposal applies
   to trades booked under v11.0 going forward. Migrating in-flight
   v10.3 trades to the `\sigma` model is a one-time backfill: every
   open transaction with status `EXECUTED` or `INSTRUCTED` becomes a
   `\sigma` in the corresponding stage at the migration cutover.
   The arithmetic is straightforward; the operational risk is
   non-trivial. F1 in the StatesHome A1 risk register applies
   directly.

6. **Six-coordinate position vectors are scalar here.** §1.4 uses
   the scalar form for `\sigma` because the obligation is not
   lendable in the SBL sense. If the market ever invents
   "obligation rehypothecation" (pre-settlement assignment of
   unsettled trades), `\sigma` will need the GPM treatment; we
   leave the door open by living in the same `\mathcal{U}` that GPM
   already covers.

7. **Bilateral fail tolerance is a policy parameter.** "How long
   does a fail wait before becoming a buy-in?" is a CSDR policy
   knob, not a framework decision. The proposal places it in
   `L_7^{\mathrm{Pb}}` (tolerance thresholds) and proceeds.

8. **CDM `SettlementFailureEvent` is a placeholder in v6.0.0.**
   §5 acknowledges this. Until ISDA's SettlementWG produces a real
   type, the Ledger uses the closed-sum `LifecycleEvent.BuyIn` and
   stamps stage `F` itself. The `LifecycleOracle` cross-walk on
   `BuyIn` is already labelled "Missing" in the data spec
   (`L_{10}`).

---

## 9. Exercises

These exercises are the test plan. A reader who can do them has
absorbed the proposal.

> **Exercise 9.1.** Trace the standard buy of §7.1 step by step.
> At each timestamp `T`, `T+1`, `T+2^-`, `T+2^+`, write down the
> state vector
> `(\beta(B, S), \beta(B, C), \beta(B, \sigma),
>   \beta(K, S), \beta(K, C), \beta(K, \sigma),
>   \mathrm{stage}(\sigma))`
> and verify `Q_t(u) = 0` for `u \in \{S, C, \sigma\}`. Confirm
> that PnL of `+\$200` is recognised at `T+1` independently of
> stage.

> **Exercise 9.2.** A second trade `\tau_2` sells the same `q = 100`
> shares of `S` at `\$53` on `T+1`, settling on `T+3`. This issues
> a second obligation `\sigma_2`. Trace the joint state of
> `\{S, C, \sigma_1, \sigma_2\}` from `T` to `T+3`. Confirm that
> `\sigma_1` and `\sigma_2` extinguish independently and that the
> realised PnL of `+\$300` is recognised at `T+1`. (Hint: at no
> point in the gap does `B` hold `\beta(B, S) = 0`; the *position*
> in `S` is non-zero throughout, even though both obligations
> remain open.)

> **Exercise 9.3.** Modify §7.2 so that `K` partially delivers
> `q' = 60` shares on `T+2` and fails on the remaining `40`. Show
> that `\sigma_1` extinguishes (stage `X`) into a residual
> `\sigma_{1,\mathrm{rem}}` covering `40` shares with stage `F`, and
> that conservation holds across the split. Then continue: `K`
> finally delivers the remaining `40` on `T+4`. Verify
> `\sigma_{1,\mathrm{rem}}` flows `F \to I \to S` and extinguishes.

> **Exercise 9.4 (Herstatt).** A EUR-domiciled `B` buys `100` USD-
> denominated shares on `T`. Two obligations issue: `\sigma_S`
> (USD cash for shares, T+1) and `\sigma_C` (EUR for USD, T+1).
> Suppose `\sigma_S` settles on `T+1` morning London time but
> `\sigma_C` fails because the FX counterparty defaults at noon
> Tokyo time on `T`. What is `B`'s exposure between trade and the
> default? Write it down using only the Ledger's vocabulary.

> **Exercise 9.5 (Corporate action).** A `\$1` cash dividend is
> declared on `S` with record date `T+1` and pay date `T+10`. `B`
> buys `100` `S` on `T` settling `T+2`. Show that `B` is the
> holder of record (because `\beta(B, S) = +100` from `T`) and
> that the dividend cash flow is unaffected by the stage of
> `\sigma`. Verify that this is *because* `\sigma` and `S` live in
> different units in `\mathcal{U}`.

---

## 10. Summary

> **The deferred-settlement obligation `\sigma`** is a unit in
> `\mathcal{U}` whose lifecycle stage represents the gap between
> trade-time economic recognition and settlement-time custody
> movement. It is issued at `T` in the same atomic transaction
> that books the position, lives through stages
> `P \to I \to S | F | X` until the CSD confirms (or the buy-in
> machinery cures), and extinguishes by burning the obligation
> balance --- never by mutating the underlying position in `S` or
> in `C`. The position itself is recognised at `T` and stays put;
> the stage of `\sigma` is a property of the obligation, not of
> the position. **PnL is determined at `T` by the price vector
> alone**, and Invariant 3.1 makes this a one-line theorem.

The mechanism reuses every existing primitive of the Ledger ---
moves, conservation, the StatesHome three-map model, the settlement
projection, the v10.3 confirmation status lifecycle, the bitemporal
versioning of the data spec, the CDM `BusinessEvent` synonym layer
--- and adds exactly one new thing: a class of units `\mathcal{U}_\sigma
\subset \mathcal{U}` whose `\textit{ProductTerms}` always include a
contractual settlement date and whose `\textit{UnitStatus}` always
includes a stage in `\{P, I, S, F, X\}`. Everything else falls out.
