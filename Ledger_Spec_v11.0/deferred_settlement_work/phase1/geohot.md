# geohot.md — deferredSettlement, the radically minimal proposal

> *Phase 1, Team A, independent. No new wallets. No new coordinates. No new units.
> The open obligation between T and T+2 is **already in the ledger**.*

---

## Thesis (one sentence)

The unsettled obligation between trade-time and settlement-time is the
**custodian virtual-wallet contra-entry** that v10.3 already creates at T;
the only *new* thing the framework needs is a per-transaction
**`settlement_status`** field with the FSM v10.3 §11.6 already names
(`EXECUTED → INSTRUCTED → SETTLED | FAILED | PARTIAL`).

That's it. Everything else — T+1, T+2, CSDR fail, partial, recall,
corporate action across record-date, Herstatt, DvP atomicity — composes
out of mechanisms that are already in the spec. **deferredSettlement.tex
is therefore mostly a *deletion* document: it argues that the question
already has an answer, names it, and removes the temptation to invent
parallel machinery.**

If you remember nothing else, remember this:

```
Trade at T → atomic transaction → conservation holds → position is in the wallet.
                                                       ↑
                                       That is the economic recognition.

Custodian virtual wallet holds the contra-entry.
                                                       ↑
                                       That is the open settlement obligation.

settlement_status on the transaction tracks the real-world transfer.
                                                       ↑
                                       That is the gap.
```

Three things. All three are already in v10.3. Two of them you didn't have
to write a single new line for.

---

## 1. State representation — what is added

**Nothing structural.** The model already supports it.

### What the existing model gives us, for free

| Object | Where defined | What it carries about T → T+2 |
|---|---|---|
| `w_portfolio(AAPL)` | v10.3 §3.1 | Trade-date economic position. Set at T. |
| `w_custodian_virtual(AAPL)` | v10.3 §3.5 | Contra-entry (negative). The "we owe / are owed" leg. |
| `w_portfolio(USD)` | v10.3 §3.1 | Cash leg, set at T (negative for buy, positive for sell). |
| `w_custodian_virtual(USD)` | v10.3 §3.5 | Cash contra-entry. |
| `Transaction.cdm_payload.settlement_date` | v10.3 §11.1 (settle_projection) | T+2 (or T+1, T+0) as a data field. |
| `SettlementInstruction` | v10.3 §11 | Stateless projection of the transaction. |
| StatesHome `UnitStatus` & `PositionState` | addendum §2 | Already total, already monotone, already bitemporal-friendly. |

The only datum that is currently *informal* in v10.3 — appearing in
§11.6 prose and §11.6 lifecycle text but not lifted to schema — is the
status FSM per transaction.

### What is added — exactly one field

```
Transaction:
    ...existing fields...
    settlement_status : EXECUTED | INSTRUCTED | SETTLED | FAILED | PARTIAL
                                                          (default: EXECUTED)
```

Where it lives, by StatesHome rules: this is shared across all viewers of
the transaction, never per-(wallet, unit), never per-product. It is
attached to the **transaction** object (which is already a first-class
object in v10.3 §3.4). No new map. No new sector.

The FSM transitions are themselves moves: the confirmation return path
(v10.3 §11.6) emits a `LIFECYCLE` transaction whose only effect is to
flip the status field. Conservation is vacuously preserved (zero moves).
This is the C9 vacuous case from the StatesHome addendum — already covered.

### What is **rejected**

I considered and reject every one of these. The reader should reject any
Phase-1 proposal that contains them.

| Tempting addition | Why rejected |
|---|---|
| New "pending settlement" wallet type | Already exists: it's the custodian virtual wallet. |
| 7th coordinate `pending` on the position vector | Fails the physical-action test (v10.3 §13.2). "Pending" is a status of the contra-leg, not a physical action on the unit. |
| Synthetic unit `AAPL_PENDING_T+2` distinct from `AAPL` | Violates fungibility (Unit Identity, v10.3 §4.2). Two wallets holding "the same" AAPL would no longer net. Catastrophic. |
| Per-(wallet, unit) `pending_qty` field | StatesHome forbids per-wallet economic state outside `PositionState[w, u_MA]`. Settlement state isn't a relationship to a mandate. |
| Two-phase commit (move at T+2 only) | Breaks trade-date economic recognition. Wrong PnL. Wrong risk. Wrong VaR. Non-starter. |
| New "settlement layer ledger" | Redundant: §11 already specifies the projection. The settlement layer is **outside** the ledger and consumes the projection. |

**The discipline: every claim that "we need a new X" must be defended
against the question "is X already implicit in (custodian virtual wallet,
settlement_status, settlement_date)?". In every case I tried, X was
already there.**

---

## 2. Move sequence — T, T+1, T+2⁻, T+2⁺

Worked for a buy of 100 XYZ @ $50, T+2 cycle, US equity.

### T (trade execution)

```
Transaction(type=SETTLEMENT, settlement_status=EXECUTED,
            timestamp=T, settlement_date=T+2):
    Move(from=w_custodian_v, to=w_portfolio,  unit=XYZ, qty=100,  ...)
    Move(from=w_portfolio,   to=w_custodian_v, unit=USD, qty=5000, ...)
```

Conservation: ΔXYZ_total = 0, ΔUSD_total = 0. Atomically committed. Done.

### T+1 (instruction sent)

```
Transaction(type=LIFECYCLE, timestamp=T+1):
    -- no moves --
    metadata: {ref=tx_T, status_to=INSTRUCTED, iso20022_msg_id=...}
```

Effect: `tx_T.settlement_status = INSTRUCTED`. Zero moves; conservation
vacuously preserved (C9). The settlement projection ran at T (or any
time after T) and produced an instruction; the wire send is what flips
the status.

### T+2⁻ (just before CSD settlement)

Nothing new in the ledger. The position has been in `w_portfolio` since T.
The contra-entry has been in `w_custodian_v` since T. PnL has been
computed against the position since T (path-independence theorem,
v10.3 §5.3 holds because nothing changed).

### T+2⁺ (CSD confirmation)

```
Transaction(type=LIFECYCLE, timestamp=T+2):
    -- no moves --
    metadata: {ref=tx_T, status_to=SETTLED, csd_ref=...}
```

Effect: `tx_T.settlement_status = SETTLED`. **Still no moves on the
real wallets.** The custodian virtual wallet's balance is correct;
external custody now matches it. The reconciliation that was
*possible* at T (and would have shown a break) is now *clean*.

This is the whole point. No move at T+2 inside the ledger. The position
was correct at T. The settlement layer is what catches up.

### Conservation across the four phases

For every unit `u`:

| Phase | Σ_w w_t(u) | Why |
|---|---|---|
| Pre-T | 0 | Closure invariant (v10.3 Thm 3.1) |
| T | 0 | Two moves; src −= q, dst += q |
| T+1 | 0 | Zero moves |
| T+2⁻ | 0 | Zero moves |
| T+2⁺ | 0 | Zero moves |

Conservation is trivially preserved because **the only place balances
change is at T**, and the rules at T are the standard ones.

---

## 3. Invariants

### Mandatory: Economic exposure at T

```
∀ tx ∈ SETTLEMENT, ∀ u ∈ tx.units:
    w_portfolio_{tx.timestamp + ε}(u) - w_portfolio_{tx.timestamp - ε}(u) = tx.Δ(portfolio, u)
```

In English: the portfolio's wallet reflects the trade *the instant after*
the trade timestamp — not the settlement timestamp. The position used
for PnL, risk, VaR, capital, and lookback is the post-T position.

This is **already an invariant of the existing model** — the move at T
puts the quantity in the wallet at T. Lifting it to a named invariant in
deferredSettlement.tex makes it auditable and forbids any future "fix"
that would move quantities at T+2. Call it **D1: trade-date recognition**.

### D2: Settlement-status totality

```
∀ tx ∈ SETTLEMENT ∪ COLLATERAL:
    settlement_status(tx) ∈ {EXECUTED, INSTRUCTED, SETTLED, FAILED, PARTIAL}
```

The status field is total on settling transactions. ACCOUNTING and
LIFECYCLE transactions never carry a status (None / not-applicable).
This is C5-style totality from StatesHome.

### D3: Status monotonicity (almost)

```
EXECUTED → INSTRUCTED → SETTLED is monotone (acyclic).
EXECUTED → INSTRUCTED → FAILED is monotone (terminal in failure mode).
FAILED → INSTRUCTED is the only legal regression (re-instruction after buy-in).
PARTIAL → INSTRUCTED is permitted (continue settling residual).
```

Implementation: a `set` of allowed (from, to) pairs, ~6 entries. Tests
exhaustively enumerate. Mutation kills sign/equality mutants.

### D4: Reconciliation identity (the load-bearing one)

```
∀ unit u, custodian c, time t:
    w_custodian_virtual(c, u)_t  ==  −(custody_depot(c, u)_t  −  inflight_to_c(u)_t)
```

Where `inflight = Σ qty over { tx : tx.counterparty=c, tx.unit=u,
tx.settlement_status ∈ {EXECUTED, INSTRUCTED, PARTIAL} }` (signed by leg
direction).

In words: **the virtual-wallet balance equals the negation of the custodian's
real depot, adjusted by the in-flight book.** When we hold the virtual
wallet at −1000 AAPL and the custodian's depot is 1000 AAPL with zero
in-flight, books match. If they don't, that is a reconciliation break,
and break-detection is a single subtraction.

This is the *only* invariant in the deferred-settlement story that is
new. It is also exactly the formula already given in v10.3 line 3538 for
SBL. So it isn't even new — it's the same equation applied without the
SBL coordinates.

### Conservation (P1) is unchanged

Conservation has nothing to say about settlement timing. It says
quantities are conserved per transaction. Every transaction in the
deferred-settlement story conserves by construction. No invariant is
strengthened, weakened, or contorted.

---

## 4. Reconciliation lead-lag

The custodian sees confirmations at T+2; we see the position at T. Lag
is structural, not pathological.

### What this implies operationally

| Time | What our ledger says | What the custodian says | Break? |
|---|---|---|---|
| T⁺ | `w_portfolio(XYZ) = +100`, `w_custodian_v(XYZ) = −100` | depot unchanged from pre-T | **Expected lag**, not a break, because `inflight_to_c(XYZ) = +100`. D4 holds. |
| T+2⁺ | unchanged | depot `+= 100` | D4 holds. |

### Bitemporal axes (data spec L_6, L_11)

The data spec already mandates `(t_obs, t_known)` on positions and on
inbound ISO 20022 messages. So a position can be queried as
"what was our recognised position at t=T+1, as known at t=T+1" (yes,
+100) versus "what was our recognised position at t=T+1, as known at
t=T+3" (still +100, because trade-date recognition does not retro-shift
on settlement confirmation). The bitemporal axes already in v1.0 of the
data spec are sufficient.

### Reconciliation pair

`L_6` already names the per-leaf reconciliation pair as
"(CCP daily statement, custodian, triparty agent; daily T+1; per-regime
tolerance; wf-position-break; middle-office reconciliation)". Add D4 as
the algebraic identity that the daily T+1 reconciliation tests. No new
operational structure required.

### CSDR penalty (L_18)

Already specified in `data/ledger_data_v1.0.tex` line 1393:
`obligation_kind = CSDR_PENALTY` with schema
`(rate_basis_points, days, source_lei, currency)`. The penalty fires
when `settlement_status = FAILED`. The existing obligation workflow
(v10.3 §10) discharges or compensates. No new CSDR object.

---

## 5. CDM cross-walk

CDM has the vocabulary, every term:

| Concept | CDM type | Where |
|---|---|---|
| Trade event | `TradeState` | already used in v10.3 |
| Settlement instruction | `Settlement` and `Transfer` | already used in v10.3 §11 |
| Settlement date | `SettlementDate` (with adjustment) | already used in v10.3 §16 |
| Settlement status | `SettlementStatus` enum | **CDM has it; v10.3 footnote in §11.6 implicitly uses it** |
| Settlement fail | `SettlementFailureReason` | CDM |
| Partial settlement | `Settlement.partialSettlement` | CDM (Partial setting) |
| Buy-in | `BuyIn` lifecycle event | CDM |

The deferred-settlement layer is **CDM-native** with zero gaps. The
mapping in v10.3 §16 already covers the static side (settlement date,
counterparty, MIC); the only addition is to flow `SettlementStatus`
back through the `sese.025` / `sese.024` confirmation path into the
transaction's status field.

In data-spec language: `L_11` (Confirmations) already maps `sese.025`
inbound; the FSM transition `EXECUTED → INSTRUCTED → SETTLED|FAILED`
*is* the consumption rule. No CDM extension required.

---

## 6. Failure modes

### F1 — Settlement fail (CSDR)

Counterparty cannot deliver at T+2.

```
Transaction(type=LIFECYCLE, timestamp=T+2):
    metadata: {ref=tx_T, status_to=FAILED, reason=...}

Obligation: CSDR_PENALTY{rate_bp, days_failed, source_lei, ccy}
            opened, accruing.
```

**No reversal of the trade.** The economic position remains: from T
onwards, our portfolio holds 100 XYZ, our PnL reflects it, and our
exposure to the failing counterparty is precisely the contra-balance in
the custodian virtual wallet. The exposure didn't appear at T+2 — it has
existed since T. This is correct and obvious under D1.

Resolution paths:
- buy-in (CSDR Article 7) → `FAILED → INSTRUCTED` after substitute trade
- bilateral cancellation → `CORRECTION` transaction reversing the
  original moves, with status `CANCELLED`
- partial → see F3

### F2 — T+1 (US post-2024)

Pure parameter change. `tx.settlement_date = T+1`. Same FSM, same moves,
same invariants. The deadline timer in `wf-confirm-break` shifts by one
day. No code change beyond the date arithmetic. **T+1 is T+2 with a
different parameter**, not a new architecture.

### F3 — Partial settlement

Custodian reports 60 of 100 shares delivered.

```
Transaction(type=LIFECYCLE, timestamp=T+2):
    metadata: {ref=tx_T, status_to=PARTIAL, settled_qty=60, residual_qty=40}
```

Optionally split into two child transactions if downstream reporting
needs it: tx_T_settled (60 shares, status=SETTLED) and tx_T_open (40
shares, status=INSTRUCTED). The split is a settlement-layer concern,
not a ledger concern — internal positions remain identical regardless of
the split. **A partial is a sequence of smaller settlements**, exactly
as the prompt suggested. No new mechanism.

### F4 — Reconciliation break

D4 fails: `w_custodian_v + custody_depot − inflight ≠ 0`. The break is
detected by the daily T+1 reconciliation activity, an obligation is
opened with `obligation_kind = wf-position-break`, and the BreakRegister
FSM (data §11) handles aging, escalation, and four-eyes close-out. None
of this is new.

### F5 — Recall of a lent share into a settlement window

Mid-settlement recall (StatesHome already covers this; SBL §13). The
recall changes only the SBL coordinates `onloan` / `borr`, never `own`.
The pending settlement of an earlier outright sale is unaffected because
the sale's contra-entry lives in the custodian virtual wallet, not in
the lent inventory pool. The two streams are orthogonal.

### F6 — Corporate action across the settlement gap

A dividend with record-date T+1 on a security bought at T:
- Trade-date accounting (D1) ⇒ we *own* it at T.
- Therefore we are entitled to the dividend.
- The CA contract emits a `LIFECYCLE` transaction at the ex-date crediting
  cash from the issuer's virtual wallet to our portfolio.
- The custodian's books may credit the *seller* if the trade hasn't
  settled at record date. That is a real claim/manufactured-payment
  situation: handled by the existing manufactured-payment obligation
  pattern (data §10, SBL §13.5).

The ledger and the custodian disagree on entitlement during the window —
*correctly so*, because trade-date accounting and settlement-date
accounting genuinely differ on this point. The reconciliation pair
captures the discrepancy as a tracked claim, not a break.

### F7 — Cross-currency / Herstatt

One leg in USD settles in New York, one leg in EUR settles in Frankfurt.
At T, both legs are committed atomically inside the ledger (this is the
*economic* atomicity guaranteed by §3.4). At settlement-time, the legs
hit two different CSDs at different clock times. The two settlements
are two separate ISO 20022 instructions with potentially independent
statuses:

```
tx_T ⇒ Instruction_USD (status=INSTRUCTED → SETTLED at 14:00 NY)
       Instruction_EUR (status=INSTRUCTED → SETTLED at 09:00 FFT next day)
```

Multi-leg `settlement_status` is a vector, not a scalar — but the
**state lives at the instruction level**, not the transaction level.
Per leg, the FSM is the same. The transaction is `SETTLED` only when
all legs are SETTLED; otherwise it sits at `PARTIAL` or `FAILED`.

Herstatt risk = the wedge `Instruction_EUR.SETTLED ∧ ¬ Instruction_USD.SETTLED`.
The framework **represents** this honestly — it does not eliminate it,
because no ledger can. CLS membership is a settlement-layer integration,
not a ledger feature.

This is exactly what v10.3 line 296 already says about Herstatt. No new
machinery.

### F8 — DvP atomicity

Inside the ledger: the trade is a single transaction with both legs.
Atomic by §3.4 (executor commits all moves or none). Real-world DvP is
the CSD's job (DTC, T2S, Euroclear). Our representation honestly says:
"economically atomic at T, mechanically atomic at the CSD". The
`SettlementInstruction.settlement_type = DvP` field already exists in
v10.3 §11.

### F9 — Short sale into the window

Already in §13. Short sale at T writes `own −= q` for the seller. The
seller's contra-entry is the custodian virtual wallet, exactly like a
long sale. The SBL coordinates handle the borrowed-share dimension; the
deferred-settlement dimension is orthogonal and uses the same custodian
virtual wallet mechanism. **The short sale is already deferred-settled
by composition.** Zero new mechanism.

---

## 7. Worked example — 100 XYZ @ $50 → $52

Buy 100 XYZ at T for $50, mark at T+1 to $52, no cash has moved, settle
T+2.

### T (buy, $50)

Pre-T: `w_portfolio(XYZ)=0, w_portfolio(USD)=20000, w_custodian_v(XYZ)=0,
w_custodian_v(USD)=−20000` (initialised so closure holds).

```
Transaction(type=SETTLEMENT, settlement_status=EXECUTED,
            settlement_date=T+2):
    Move(w_custodian_v → w_portfolio, XYZ, 100)
    Move(w_portfolio   → w_custodian_v, USD, 5000)
```

Post-T:
- `w_portfolio(XYZ) = 100`
- `w_portfolio(USD) = 15000`
- `w_custodian_v(XYZ) = −100`
- `w_custodian_v(USD) = −15000`

Conservation: ΔXYZ_total = +100 + (−100) − 0 − 0 = 0. ΔUSD_total similarly.

### T+1 mark to $52

```
PnL_T+1 = w_portfolio(XYZ) · 52 + w_portfolio(USD) − V_T
        = 100 · 52 + 15000 − (100·50 + 15000)
        = 5200 − 5000
        = +200
```

**+$200, no cash has moved.** Cash is still 15000 in our wallet (the buy
happened at T against the custodian contra-entry; the cash move at T was
to the contra-leg, not "out" of the closed system). The value gain comes
entirely from `w_portfolio(XYZ) · ΔP = 100 · (52−50) = +200`. PnL is
path-independent (v10.3 §5.3). Recognised at T+1 against trade-date
positions established at T.

The status FSM at T+1 might be `INSTRUCTED` (instruction sent overnight)
or `EXECUTED` (instruction not yet sent). PnL is independent of status —
it depends only on the wallet balances, which were fixed at T.

### T+2 (settle)

Status flips to `SETTLED`. **Zero moves** in the ledger. Custody depot
now holds 100 XYZ; cash account at the bank now reflects −5000; the
custodian virtual wallet still holds (−100, −5000) but now agrees with
external books per D4.

PnL at T+2 (mark $52 still): unchanged, +$200. As required by trade-date
accounting.

### Settlement-fail variant

If at T+2 the custodian reports FAIL: status `FAILED`, CSDR penalty
obligation opens, **PnL still +$200** (the mark is still $52 and we
still hold 100 XYZ economically), and our exposure to the failing
counterparty is the (−100 XYZ, −5000 USD) sitting in the custodian
virtual wallet — visible, monitorable, contra-entry-paired.

This is the right answer. The economic exposure existed from T regardless
of settlement outcome; the framework does not retroactively erase it
because the wire failed.

---

## What I am deleting from the proposal space

I will close with the deletion list — the things a committee would add
that this proposal refuses:

1. **No** new wallet kind (custodian virtual wallet already does the
   job, defined v10.3 §3.5).
2. **No** seventh coordinate on the position vector (would fail the
   physical-action test, §13.2).
3. **No** parallel settlement ledger (the settlement projection §11
   already specifies the boundary; the settlement layer is *outside*
   the ledger by design).
4. **No** synthetic "T+2 unit" type (would break fungibility under
   §4.2; AAPL bought yesterday and AAPL bought five years ago are the
   same unit; transferring through a settlement window does not make
   them different).
5. **No** new map in StatesHome (the addendum's three maps —
   `ProductTerms`, `UnitStatus`, `PositionState` — already absorb
   everything; status is a transaction property, not a unit-state
   property, and lives on the transaction object).
6. **No** retroactive position adjustment on settlement (D1 forbids it;
   that is the entire point of trade-date accounting).
7. **No** new lifecycle stage on units (`pending` is not a stage of the
   security; it is a stage of the transaction).
8. **No** new event-handler pattern (the confirmation return path,
   v10.3 §11.6, already specifies the pattern: a zero-move LIFECYCLE
   transaction that updates a status field).
9. **No** elaborate failure taxonomy (FAILED is FAILED; reasons live in
   metadata; CSDR penalty kind already exists in data §10).
10. **No** new CDM extension (CDM has every type we need;
    `data/L_11` already maps the relevant ISO 20022 messages).

If the deferredSettlement.tex deliverable contains any of items 1–10,
it is overengineered. The simple statement is sufficient and
strictly necessary.

---

## The one-line answer

> **The Ledger represents the open settlement obligation as the
> contra-entry already standing in the counterparty's virtual wallet,
> tagged by a single `settlement_status` field on the transaction; the
> obligation opens at T and closes at SETTLED, FAILED, or CANCELLED,
> with conservation, PnL, and economic exposure tied to T throughout.**

That is one new field on an existing object, one new invariant (D4)
which is in fact the same algebraic identity already given for SBL
in §13, and zero new sectors of the StatesHome schema. The deferred-
settlement document should be short. If it is long, it has gone wrong.

---

## Geohot test, applied to this proposal

| Test | Answer |
|---|---|
| Simplest possible? | Yes — adds one field. Anything less omits the status FSM. |
| Obviously correct? | Yes — D1 follows from the move-at-T pattern; D4 is the SBL identity reused. |
| Beautiful? | The model already knew how to do this; we are merely *naming* the answer. |
| Hackable in an afternoon? | Yes — five-state FSM, one transaction-level field, three new lines in `Transaction` and one new invariant. |
| Proven? | Conservation by induction; D1 by construction; D4 by direct substitution; failure modes by cases F1–F9 above. |
| What can be deleted? | If anything, the entire `settlement_status` field is debatable: it is not strictly required for **economic** correctness — only for **operational** reconciliation. The minimum-minimum proposal is therefore: zero new fields, the status FSM lives in the BreakRegister (data §11) keyed by transaction id. I retain `settlement_status` only because it's load-bearing for CSDR penalty triggering, and the cost of the field is one enum. |

Ship it.
