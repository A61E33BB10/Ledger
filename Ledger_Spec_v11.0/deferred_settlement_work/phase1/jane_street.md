# Deferred Settlement on Cash Equities — Jane Street CTO Proposal

**Phase 1, Team A, independent.**
**Author role: CTO, Jane Street.**
**Stance: ship.** Engineering pragmatism over elegance. Reject anything requiring a research project. Build for ops at 03:00, not for journals.

---

## 0. The lesson Jane Street learnt the hard way

The cash-equity book at any serious firm is **not** a position store with a settlement appendage. It is two coupled state machines running at different clocks:

1. **Economic state** — what we own *for the purpose of risk, PnL, capital, margin*. Updates at fill (`EXECUTED`).
2. **Custody state** — where the certificates / book-entries actually sit. Updates at CSD acknowledgment (`SETTLED`).

The window between them is normally 1–2 days. In a US T+1 world it is one overnight. In a CSDR-stressed European book it can be a week before a buy-in fires. Every bug we have ever shipped in the cash-equity stack came from one of three places:

- **Conflating the two clocks.** Risk system reads the back-office position (custody), back-office reads risk (economic), one of them is wrong, recon never closes.
- **Reversing economic state on a fail.** A counterparty fails to deliver; some helpful service "unwinds" the trade in our books. We are now flat on the risk system, long on the street, and short on margin — at exactly the moment we needed clarity.
- **Letting the fail desk patch state directly.** A senior trader emails ops at T+5 to "just adjust it." Two months later auditors find a position that exists in three systems and a fourth where it doesn't.

The Ledger v10.3 corpus already has the right architectural answer (§16 settlement projection, §16.5 confirmation return path, FAQ Q5). My job is to (a) state explicitly what is already implicit, (b) close two specific gaps, (c) refuse the speculative scope.

---

## 1. State representation

### 1.1 What is already in the corpus and is correct

The corpus already establishes:

- **Trade-date accounting at the Ledger level** (§16.5, §16.6 settlement timing). The economic position is recognised at fill. This is non-negotiable.
- **The settlement projection** (§16.1) is a pure function `Transaction → SettlementInstruction | None`. Stateless, deterministic, idempotent. Custody is downstream.
- **The status lifecycle** (§16.7): `EXECUTED → INSTRUCTED → SETTLED | FAILED`. This is **per-transaction**, not per-position.
- **Virtual wallets** (§2.5) make the counterparty present *inside* the closure. The trade is two atomic moves: cash → counterparty-virtual, security ← counterparty-virtual.
- **Obligations as first-class objects** (§13). The obligation store (`L_15`, data v1.0) is a typed FSM `Pending → Discharged | Compensated | Defaulted` with discharge predicate `D` and compensation `κ`.

That foundation is sound. **Do not rewrite it.**

### 1.2 The one piece that is implicit and needs to be made explicit

The settlement-status FSM (§16.7) lives "on the transaction" but is not given a home in the data layer (`ledger_data_v1.0`) or the StatesHome 3-map ruling (addendum). This is the gap.

**Ruling.** Settlement status is a **per-transaction obligation**, not unit state. It belongs in the obligation store `L_15`, with `obligation_kind = SETTLEMENT_INSTRUCTION` (already enumerated at v10.3 §13.2 Table, line 3106: "Settlement instruction | Unit | Settlement-type transaction | Failed settlement"). The proposal is to take what the table already says and follow it through.

**State carrier (drop-in into L_15):**

```
type SettlementObligation = {
    obligation_id    : Id           # = transaction_id  (deterministic)
    transaction_id   : TxnId        # the SETTLEMENT-type Tx
    intended_settle  : Date         # T+N from CDM payload, fixed at fill
    status           : Pending | Discharged | Compensated | Defaulted
    discharge_pred   : ByMatch { sese.025 / camt.054 against transaction_id }
    compensation_κ   : SettlementFailHandler   # see §6
    csdr_clock       : Optional[CsdrClock]     # populated only on FAILED
}
```

That is one new closed-sum variant on `DischargePredicateKind` (already a closed sum in `L_15`) and one new variant on `CompensationHandlerKind`. **No new sector. No new map. Reuse what exists.**

### 1.3 The economic position is unaffected by settlement state

This is the single most important sentence in the document.

> Position balances `w(u)` and unit state `PositionState[w, u]` are functions of the **trade-date** event stream only. Settlement status changes never write to balances.

Mechanically: the `EXECUTED → INSTRUCTED → SETTLED | FAILED` FSM is recorded as **state-only transactions** (§13.2 corpus, §lifecycle move-less events) attached to the settlement obligation. Zero moves. Conservation discharges trivially. No cross-coupling between custody and economics.

A `FAILED` settlement does **not** issue compensating moves. The trade stands. The compensation κ runs against the obligation, not against the position.

---

## 2. Move sequence with conservation (T → T+1 → T+2⁻ → T+2⁺)

US equities are now T+1 (since 28 May 2024). EU/UK remain T+2; UK confirmed for 11 Oct 2027, EU late 2027. The proposal works for any N. I use T+2 for clarity; substitute as needed.

**Setup.** Buy 100 XYZ @ $50, our wallet `w_us`, broker virtual wallet `w_bk`.

### T (trade date, fill received via FIX)

One transaction, type `SETTLEMENT`:

```
Tx_trade :
    Move(w_us, w_bk, USD,  -5000)        # cash leg
    Move(w_bk, w_us, XYZ,  +100)         # securities leg
```

**Conservation.** `Σ_w Δq(USD) = -5000 + 5000 = 0`. `Σ_w Δq(XYZ) = +100 - 100 = 0`. Both pass.

**Atomic.** Both moves commit together (executor §10). Ledger-level DvP holds *structurally* (§16.4 corpus).

**Obligation registered atomically.** The smart contract emits `SettlementObligation(id=Tx_trade.id, intended_settle = T+2, status = Pending)` in the same atomic commit. Principle 13.1 (Obligation Completeness, §13).

After T:
- Position: `w_us` is long 100 XYZ, short $5000. **Real economic state.**
- Obligation: `Pending`. Status `EXECUTED`.

### T+1 (instructed)

External signal: settlement layer has sent `sese.023` to DTC/Euroclear, received gateway ack. Inbound is an `L_11 ExternalConfirmation` event. The Ledger records a **state-only transaction**:

```
Tx_instructed:
    moves = []
    state_delta:
        SettlementObligation[Tx_trade.id].status_substate = INSTRUCTED
```

Zero moves. Conservation: vacuous. C9 of the StatesHome addendum applies (handlers on zero-move events discharge `Σ = 0` vacuously).

After T+1:
- Position: unchanged. Still long 100 XYZ, short $5000.
- Obligation: `Pending`, substate `INSTRUCTED`.

### T+2⁻ (settlement morning, custody not yet moved)

Identical to T+1 except the obligation timer is now active. The deadline `t_d = end-of-day T+2` is the discharge timer. No moves. Position unchanged.

### T+2⁺ (afternoon — happy path: SETTLED)

Inbound `sese.025` matches `Tx_trade.id`. State-only transaction:

```
Tx_settled:
    moves = []
    state_delta:
        SettlementObligation[Tx_trade.id].status = Discharged
```

After T+2⁺ on settle:
- Position: unchanged from T (this is the load-bearing point). Long 100 XYZ, short $5000. **Identical to trade date.**
- Obligation: `Discharged`. Terminal.
- Virtual wallet `w_bk` reconciles to flat against custodian statement of our DTC participant account.

**No PnL impact at settlement.** PnL was recognised at T. Settlement is custody, not economics.

### T+2⁺ (failed path: FAILED → buy-in path)

Inbound `sese.024` (instruction status with reason code `LACK`) or no `sese.025` by deadline. The obligation timer fires; discharge predicate is false:

```
Tx_failed:
    moves = []
    state_delta:
        SettlementObligation[Tx_trade.id].status_substate = FAILED
        SettlementObligation[Tx_trade.id].csdr_clock = CsdrClock(start=T+2, regime=EU_T2)
```

After T+2⁺ on fail:
- **Position unchanged.** Still long 100 XYZ, short $5000.
- Obligation: `Pending`, substate `FAILED`. Not terminal yet.
- A `BreakRegister` entry (`L_18`, `wf-position-break`) is opened against the virtual-wallet vs custodian-statement mismatch.

This is the corpus's existing answer (§16.4 final paragraph, FAQ Q5) and it is the right one. **Do not invent.**

---

## 3. Invariants — the economic-exposure-at-T invariant is mandatory

### I-1 (mandatory, load-bearing): **Economic exposure at T**

For every cash-equity trade `Tx_trade` executed at time `t_exec`:

```
∀ t ≥ t_exec :
    PositionState[w, u_security].balance(t) is a function of the event stream
    restricted to {events with timestamp ≤ t and type ∈ {SETTLEMENT(trade),
    LIFECYCLE(corporate-action), CORRECTION}}.

The settlement-status FSM transitions of Tx_trade do NOT appear in this
restriction.
```

In one sentence: *settlement-status transitions write to obligations, never to positions*.

This is enforced by **type-tagging** (cf. C11 of the StatesHome addendum: each PositionState field has a unique handler authorised to mutate it). Field `balance` is mutable only by `apply_trade_move` and `apply_corporate_action_move`. Settlement-status handlers don't have the capability. Compile-time enforcement.

If you take one thing from this proposal, take this. Every disaster I have seen on a cash-equity desk traces to a violation of I-1.

### I-2 Conservation across T and T+2

Trivially holds. Settlement-status state changes are zero-move transactions; conservation discharges vacuously (C9). No violation possible.

### I-3 Settlement-projection idempotency

`settle_projection(Tx) = settle_projection(Tx)` for committed `Tx`. Already in the corpus (§16.1). The projection is pure; running it twice is the identity.

### I-4 Status monotonicity (with the one exception)

Within the obligation FSM, status moves forward only:

```
EXECUTED → INSTRUCTED → SETTLED       (terminal)
EXECUTED → INSTRUCTED → FAILED → INSTRUCTED → SETTLED   (re-instruct)
EXECUTED → INSTRUCTED → FAILED → COMPENSATED  (terminal: cancellation/buy-in completes)
```

`FAILED → INSTRUCTED` is the **only** retrograde edge, and it represents a re-instruction (post buy-in or post extension), not a state revert. It is recorded as a **new substate transition**, not as a rewrite. The append-only log preserves the full trail. (This is the same shape as L_18 BreakRegister aging in `ledger_data_v1.0`.)

### I-5 Virtual-wallet ↔ custodian reconciliation closure

For every (counterparty LEI, security ISIN, business date) tuple:

```
balance(w_counterparty_virtual, u) measured at end-of-day T+N
=
algebraic sum of (custodian statement entries with that ISIN against
that counterparty for that settle date)
```

This is the §17 reconciliation matrix line `L_6` (CCP/custodian/triparty, daily T+1). **The reconciliation is at the virtual-wallet boundary, not at the position.** Critical: positions never need to reconcile to custody because they answer different questions (economic exposure vs custody).

### I-6 Obligation completeness for SETTLEMENT

Every committed `Tx` of type `SETTLEMENT` has exactly one `SettlementObligation` registered atomically. This is just Principle 13.1 (Obligation Completeness) instantiated for the settlement kind. Property-test generator: enumerate `EventIntentEnum`, restrict to settlement-emitting kinds, assert obligation present in lifecycle function output.

### What I refuse to make an invariant

- **"Position equals custody at T+2."** False. They diverge legitimately on fails. Demanding equality forces position-reversal on fail, which is the bug we are trying to forbid.
- **"DvP atomicity at the real-world level."** Outside the Ledger boundary. The CSD provides it. We cannot promise what we do not control.
- **"Herstatt is eliminated."** It isn't. It is *represented* (§2.7 corpus). No ledger design fixes Herstatt.

---

## 4. Reconciliation lead-lag

### 4.1 Where the lag actually lives

| Cadence       | Source                          | Target                     | Tolerance       | Owner        |
|---------------|---------------------------------|----------------------------|-----------------|--------------|
| Intraday      | sese.024 / sese.032 (hold/fail) | Obligation substate        | 0 (closed sum)  | Settlement ops |
| EOD T+0       | OMS / FIX exec reports          | Ledger move stream         | 0 (we own both) | Front office |
| EOD T+1       | Custodian intraday (DTC SDFS)   | Virtual wallet `w_bk`      | Per-regime      | Middle office |
| Morning T+2   | CSD pre-matching report         | Obligation substate        | 0               | Settlement ops |
| EOD T+2       | DTC settlement report           | Virtual wallet + obligation | 0               | Middle office |
| Daily         | Cross-vendor IM                 | L_2 InstrumentMaster       | 0 (quarantine)  | Refdata ops |
| Continuous    | BreakRegister L_18              | self                       | aging FSM       | Ops mgmt     |

This map already exists in `ledger_data_v1.0` §17.1 (Reconciliation Matrix). I am not proposing a change. I am pointing out **where settlement reconciliation fits**: lines 2 and 5 above. Both are at the **virtual-wallet boundary**, not at position.

### 4.2 Lead-lag rule

Reconciliation runs **lagging** the move stream, never **leading**. The Ledger is the source of truth for what we believe. The custodian is the source of truth for what the street believes. Mismatch = open BreakRegister entry, never automatic adjustment.

The temptation, always, is to "auto-correct" the Ledger from the custodian. **Refuse it.** The custodian can be wrong (we have seen it: a misposted manuf-dividend at a Tier-1 prime broker took 11 days to unwind). Auto-correction destroys the audit chain. Manual amendment via `CORRECTION` transaction (corpus §11.2) is the correct path, with named approver and break-ticket reference in the `cdm_payload`.

### 4.3 The recon must finish in minutes, not hours

Performance reality: at our scale (~10⁷ trades / day across the firm) the open settlement window is ~2× daily volume = 2·10⁷ obligations live at any moment. Recon must:

- Be **incremental**: process only obligations whose substate or virtual-wallet leg changed in the last batch. Append-only event log makes this a trivial cursor over `(t_known, t_obs)`.
- Use the **bitemporal index** from `ledger_data_v1.0` directly (mandatory on `L_11`, `L_13`, `L_18`).
- Be **parallel by counterparty LEI**. Recon partitions cleanly by virtual wallet (no shared state). Embarrassingly parallel.

Target: full daily recon ≤ 15 minutes wall clock at 10⁷-trade scale on commodity hardware. We have benchmarks at ~3 µs per obligation lookup with `Map[(WalletId, UnitId), …]` (StatesHome addendum, F3 risk register; benchmark before merge). 2·10⁷ × 3 µs = 60 s lookups, plus ~5 minutes for break workflow drainage. Fits.

---

## 5. CDM cross-walk

The corpus already maps `BusinessEvent → Transaction` (§9). For settlement specifically:

| CDM concept                         | Ledger concept                               | Notes |
|-------------------------------------|----------------------------------------------|-------|
| `Transfer` (settle leg)             | `Move` inside SETTLEMENT-type Tx             | Direct |
| `TradeState.state` settlement field | `SettlementObligation.status` substate       | Note: CDM keeps this on the trade; we keep it on the obligation. The two are one-to-one keyed by `transaction_id`. |
| `EventIntentEnum.Settlement`        | `Transaction.type = SETTLEMENT`              | Direct |
| `SettlementInstruction` (CDM internal) | `SettlementInstruction` struct of §16.1   | Direct, same name |
| ISO 20022 `sese.023/024/025`        | Inbound `L_11 ExternalConfirmation`          | Already mapped (`L_11` cross-walk Partial) |
| ISO 20022 `camt.053/054`            | Inbound cash confirmation (`L_11`)           | Direct |
| CSDR penalty notification           | New `obligation_kind = CSDR_PENALTY`, child of failed settlement obligation | Extension; one new variant |

**Gap to flag.** CDM 6.0.0 does not natively model the *fail / buy-in / extension* cycle as a sub-state of `TradeState`. The closest is `EventIntentEnum.Settlement` plus a free-text `reasonCode`. This is the same gap `ledger_data_v1.0` §10 (CDM Gap Analysis) identifies. Treatment: per-leaf cross-walk classifies SettlementObligation as **Missing** in CDM; one Rosetta extension PR to add a `SettlementSubState` enum. Manageable. Not blocking.

---

## 6. Failure modes — every one with a named handler

| Mode                     | Detection                              | Compensation κ                               | Position effect | Audit trail |
|--------------------------|----------------------------------------|----------------------------------------------|-----------------|-------------|
| **Counterparty fail (LACK)** | `sese.024` reason `LACK`           | Open break, start CSDR clock, retry per regime | None            | BreakRegister + obligation substate |
| **Our fail (own short)**     | `sese.024` reason `LACK` against us | Trigger SBL borrow workflow (corpus §14)     | None            | Cross-link obligation to SBL contract |
| **Partial delivery**         | `sese.025` with partial qty        | Discharge fraction; new obligation for remainder; spawn child obligation | None on the original; new obligation tracks remainder | Obligation tree |
| **CSDR mandatory buy-in (T+4 EU equities)** | CSDR clock fires    | Buy-in instruction issued; on success → `Compensated`; on failure → `Defaulted` | Original position **stands**; buy-in trade is a new SETTLEMENT Tx | Two transactions, original + buy-in, both visible |
| **Cancellation (mutual)**    | `sese.027` cancellation request    | `CORRECTION` Tx with anti-moves (§11.2)      | **Position reversed** via explicit CORRECTION (only place positions move from settlement) | Compensating Tx with named approver |
| **Trade amendment (qty/price)** | `sese.028` modification         | Forbidden post-settlement; pre-settlement = atomic CORRECTION + new SETTLEMENT pair | Net change visible | Two Txs |
| **Late correction (T+5+)**   | Post-recon manual entry            | `CORRECTION` Tx with four-eyes (`L_18` Closed-Waived rule from data v1.0) | Net change visible | Mandatory approval |
| **CSD vs back-office disagreement** | Recon break               | Open BreakRegister, NEVER auto-resolve; ops investigates | None until resolved | BreakRegister escalation per `L_18` FSM |
| **Cross-currency Herstatt window** | FX leg settled, securities leg pending (or vice versa) | Each leg is its own obligation; settle independently | Each leg's economics already booked at T | Per-leg substate |
| **Recon itself missing data** | Custodian feed silent              | Stale-feed timer fires; obligations not falsely closed; ops paged | None             | Incident ticket via L_18 |
| **Manual override**          | Trader/ops emails request          | Forbidden direct write; route through `CORRECTION` Tx with mandatory four-eyes (`L_18`) and timestamped justification | Visible | Full chain |
| **Restated ref data**        | InstrumentMaster restatement (`L_2`) | Bitemporal restatement (`ledger_data_v1.0` §6) | None on already-settled; affects in-flight obligations only via re-projection | bitemporal indexing |

The pattern is uniform: **detection in `L_11` or recon → state-only Tx on obligation → optional compensation Tx with explicit moves and approver chain**. No silent paths. No bare `except`. Every named handler is a closed-sum branch in `CompensationHandlerKind` (`L_15`).

The two failure modes that actually need the most engineering attention are:

1. **Partial deliveries causing obligation trees**. If you let partial obligations spawn arbitrary children, the obligation graph blows up. **Cap depth at 2** (parent fail → child remainder). After that, escalate to ops. This is a deliberate engineering choice; it is not principled. It is correct because partial-of-partial-of-partial is operationally indistinguishable from a broken counterparty and the right action is human intervention, not deeper recursion.

2. **CSDR penalty calculation**. The penalty is a function of the failing party, the asset class, the failure duration, and the reference price (`L_9 RawMarketObservation`). Owning that calculation in the Ledger is fine; arguing with the CSD about whose number is correct is not. The Ledger computes its own penalty; it reconciles to the CSD's penalty notification; on disagreement, **the CSD wins for the booking** but the Ledger's number remains in the audit trail (so we can dispute later).

---

## 7. Worked example — 100 XYZ @ $50 → $52, no cash moved

Setup. Real wallet `w_us`. Virtual broker wallet `w_bk`. Trade T = 2026-04-30 (Wednesday). EU equities, T+2 = 2026-05-04 (Monday).

### State just before T (no positions)

```
balance(w_us, USD)  = 100000     # we have $100k starting cash
balance(w_us, XYZ)  = 0
balance(w_bk, USD)  = 0
balance(w_bk, XYZ)  = 0          # broker virtual is symmetric
```

### T (2026-04-30, fill received via FIX)

`Tx_trade` (type SETTLEMENT) commits atomically:

```
Move(w_us → w_bk, USD, 5000)     # we pay
Move(w_bk → w_us, XYZ, 100)      # we receive (book entry)
```

Plus obligation registration:

```
SettlementObligation(
    obligation_id   = Tx_trade.id,
    transaction_id  = Tx_trade.id,
    intended_settle = 2026-05-04,
    status          = Pending,
    substate        = EXECUTED,
    discharge_pred  = ByMatch(sese.025 against Tx_trade.id),
    compensation_κ  = SettlementFailHandler(regime = EU_CSDR),
    csdr_clock      = None
)
```

State after T:

```
balance(w_us, USD)  = 95000
balance(w_us, XYZ)  = 100
balance(w_bk, USD)  = 5000
balance(w_bk, XYZ)  = -100        # broker is short 100 to us pending delivery
SettlementObligation status = Pending / EXECUTED
```

Conservation: `Σ_w Δq(USD) = -5000 + 5000 = 0`; `Σ_w Δq(XYZ) = +100 - 100 = 0`. ✓

**Economic exposure at T = +100 XYZ × $50 = $5000 long XYZ.** This is what the risk system reports, what margin is computed against, what enters PnL. No cash has moved at any custodian. We don't care.

### Price moves to $52 (still T)

No transaction. Pricing function `P_t` is external (corpus §3). PnL is computed:

```
V(t) = balance(w_us, USD) + balance(w_us, XYZ) × P_t(XYZ) + ...
     = 95000 + 100 × 52 = 100200
PnL  = 100200 − 100000 = +$200
```

PnL = +$200. **No cash moved.** Position-keeping and PnL-keeping have nothing to do with settlement state. This is the load-bearing case the user demanded; it works trivially because of trade-date accounting.

### T+1 (2026-05-01, Friday): instructed

`sese.023` ack received. State-only Tx:

```
Tx_instructed:
    moves = []
    SettlementObligation[Tx_trade.id].substate = INSTRUCTED
```

Balances unchanged.

### T+2 morning (2026-05-04): CSD pre-matching reports MATCHED

State-only Tx:

```
Tx_prematched:
    moves = []
    SettlementObligation[Tx_trade.id].substate = INSTRUCTED   # (no change, still pending settle)
```

Balances unchanged.

### T+2 EOD: settled

`sese.025` arrives, matches `Tx_trade.id`. State-only Tx:

```
Tx_settled:
    moves = []
    SettlementObligation[Tx_trade.id].status   = Discharged
    SettlementObligation[Tx_trade.id].substate = SETTLED
```

Balances unchanged. Reconciliation: `w_bk` against custodian statement of our DTC participant account → match. No break.

**Final state:**

```
balance(w_us, USD)  = 95000
balance(w_us, XYZ)  = 100
PnL = +$200 (if XYZ still at $52)
SettlementObligation = Discharged   (terminal)
```

**The position never changed because of settlement.** It changed once, at T, because of the trade. Settlement is metadata on the obligation; it is not economics.

### Variant: T+2 fails (counterparty short)

At T+2 EOD, no `sese.025`. Obligation timer fires.

```
Tx_failed:
    moves = []
    SettlementObligation[Tx_trade.id].substate = FAILED
    SettlementObligation[Tx_trade.id].csdr_clock = CsdrClock(start=2026-05-04, regime=EU_CSDR)
BreakRegister[Tx_trade.id] = Open against w_bk vs custodian on 2026-05-04
```

**Our position is still long 100 XYZ at $52 = $5200.** The trade stands. CSDR penalty accrual begins. At T+4 (2026-05-06) under EU CSDR, mandatory buy-in is initiated by the CCP. When the buy-in completes, a new SETTLEMENT Tx delivers the shares from the buy-in counterparty (different virtual wallet); the original obligation transitions to `Compensated`. Our economic position is unchanged throughout. The street's books may have temporarily disagreed; ours did not need to.

### Variant: trade is cancelled at T+1 (e.g., bust)

Mutual cancellation requires explicit `CORRECTION`:

```
Tx_correction (type CORRECTION):
    Move(w_bk → w_us, USD, 5000)     # reverse cash
    Move(w_us → w_bk, XYZ, 100)      # reverse securities
    cdm_payload.references = Tx_trade.id
    cdm_payload.approver  = "ops_lead_uuid"
    cdm_payload.reason    = "MUTUAL_BUST_REASON_X"
SettlementObligation[Tx_trade.id].status = Compensated
SettlementObligation[Tx_correction.id]   = Discharged (immediate)
```

Position now flat. Original Tx still in the log. Audit trail complete. **Both** transactions are visible at all `t_obs`.

---

## 8. Make illegal states unrepresentable — but only where it's cheap

Arguing both sides, as requested.

### Where it pays

- **`Transaction.type` is a closed sum.** A SETTLEMENT Tx without a `SettlementObligation` on the same commit is a type error, not a runtime check. C3 of StatesHome (atomic StateDelta).
- **Settlement substate is a closed sum**. Not a string. We have shipped bugs from `"setled"` typos. Compile-time enum.
- **Compensation κ is a closed-sum**, mirroring `L_15`. No "or anything else the workflow author thinks of."
- **Position-mutating capability is type-tagged** (C11). Settlement-status handlers literally cannot type-check against `balance`. This is the cheapest type-system investment we will ever make. Required.

### Where it doesn't pay

- **CSDR clock as a refinement type** ("must be in the future, must be in business days, must respect the regime calendar"). Refinement types in production Python are not free. We are not Lean. Clock construction goes through a smart constructor, validation lives in the constructor, the rest of the code reads a plain `Date`. Same correctness, 100× less rope.
- **"Settlement state machine as a Petri net"**. Tempting. Don't. A closed sum + `Map[Status, Set[Status]]` transition table is enough, runs in production, and is greppable.
- **Arbitrary obligation tree depth.** As stated, cap at 2. Past 2, escalate. This is engineering, not principle. It is right because it matches the operational reality that very deep partial-fail trees mean the counterparty is broken and the right answer is human attention.

The rule we use at Jane Street: types stop ~80% of the bugs at ~20% of the cost. The remaining 20% live in tests. The next 1% lives in incident response. Don't chase the 1% with the type system.

---

## 9. The Ledger / settlement-utility boundary

The corpus has the right boundary (§16.2):

> The Ledger provides what needs to settle: the parties, the securities, the quantities, the dates. The settlement layer provides how: SSIs, custodian account identifiers, CSD connectivity, ISO 20022 message generation, and exception management.

**Where exactly is the boundary?** At the `SettlementInstruction` struct (`SettlementProjection` output) and the `L_11 ExternalConfirmation` ingress.

This proposal **respects** that boundary because:

- It does not put SSIs in the Ledger. They live in the settlement layer enrichment step.
- It does not put CSD connectivity in the Ledger. That is operational infra.
- It does not put ISO 20022 generation in the Ledger. That is the settlement layer.
- It puts `SettlementObligation` (status FSM, deadline, discharge predicate, compensation) **in the Ledger**, because:
  1. The Ledger is the system of record for "what we promised";
  2. The discharge predicate and compensation are economically load-bearing;
  3. Putting them in the settlement utility recreates the trading-system / GL split (§2.6 Self-Consistency Principle) which is the architectural sin we are explicitly trying to avoid.

That last point is the philosophical anchor. If `SettlementObligation` lived in a separate "settlement utility" alongside its own state, we would have two systems claiming truth about the same fact, requiring reconciliation between them. Self-consistency forbids that. The obligation is in the Ledger; instruction generation, CSD wire, and message formatting are not.

---

## 10. Operational corner cases that academic proposals miss

The proposal fails the 03:00 test if it cannot answer these. Each is addressed.

| Case | Answer |
|------|--------|
| Trader emails ops at 04:00 saying "qty was 1100 not 1000" | `CORRECTION` Tx, four-eyes, named approver, full bitemporal trail. **No direct edits.** Email goes in `cdm_payload.justification`. |
| Custodian sends sese.025 with wrong qty | Open BreakRegister at `Material` if > $1M; ops calls custodian; resolution is either custodian re-sends correct sese.025 (replaces in `L_11`, bitemporal restatement) or `CORRECTION` Tx. **Never auto-update from custodian.** |
| Settlement date moves due to local-market holiday declared late | `L_4 CalendarConvention` restated bitemporally; `intended_settle` is **not** rewritten; the obligation timer shifts via `t_known` axis update on the calendar; obligation deadline derived. |
| Same trade arrives twice from FIX gateway | Idempotency key on the executor (`tx.transaction_id`); duplicate is a no-op. P5 of corpus invariants. |
| Late confirmation (sese.025 arrives at T+10 because counterparty's nostro was broken) | If trade was previously marked FAILED, transition `FAILED → SETTLED` via discharge predicate match. CSDR clock stops. Penalty accrual halts at point of effective settlement. |
| Counterparty defaults at T+1 (Lehman scenario) | Default event triggers close-out netting workflow (corpus §13.2 Table). Open settlement obligations transition to `Compensated` per ISDA close-out terms; net amount becomes a single new obligation. **This is exactly why settlement state lives in the obligation, not in the position** — close-out is an obligation-level operation. |
| Reg-imposed retroactive reclassification (e.g., short-sale flag added at T+3) | Bitemporal restatement of CDM payload. Position unchanged (it was a short to begin with, just not flagged). Reporting submission (`L_17`) restates. |
| CSD outage for 6 hours during settlement window | Obligation timer extends per regulatory holiday handling. No automatic state change. Ops monitors. |
| Counterparty disputes the trade three days after fill | Open break, status remains `Pending/INSTRUCTED` until resolved. If resolution is "the trade was never agreed", a `CORRECTION` Tx with mutual sign-off. |
| Manual override request from senior trader | **Always rejected.** Override is implemented via `CORRECTION`, never via direct state edit. The request becomes the `cdm_payload.justification`, the trader becomes the `requester`, ops sign-off becomes the `approver`. Audit trail intact. This is the rule you regret breaking. |

---

## 11. Performance reality

State must be queryable in real-time by ops. Concrete numbers:

- **Open-obligation lookup by trade-id**: O(1) hashmap. P50 ≤ 1 µs.
- **Open obligations by counterparty LEI** (the question ops asks 100× a day): index on `(counterparty_lei, status=Pending)`. Maintained as part of the obligation store. P50 ≤ 10 ms for 10⁴ open obligations against any single counterparty.
- **Obligations by status / aging bucket**: secondary index. ≤ 100 ms.
- **Daily recon batch**: see §4.3, target ≤ 15 minutes at 10⁷ trades/day.
- **Time-travel query** (corpus §6, "what did the open settlement window look like at 14:35 last Tuesday"): bitemporal index on `(t_obs, t_known)`. Worst case linear in obligations open at that t. Acceptable; ops queries on time-travel are rare (incidents, audits).

Storage. The monotone carrier (StatesHome C1) gives us the property that `SettlementObligation` rows are never deleted. At 10⁷ trades/day × 365 × 7 years = 2.5 × 10¹⁰ rows. At ~200 bytes/row this is ~5 TB. Single-table-on-modern-storage territory. Risk F3 of StatesHome (key-space growth) applies; tombstone-compaction policy on terminal-state obligations older than retention horizon (CSDR mandates 5 years; we keep 7).

---

## 12. The single most important property to enforce — and the one we can live without

### Most important: **trade-date accounting is sealed against settlement state.**

If you enforce one thing, enforce that the position function is independent of the settlement-status FSM. This is invariant I-1 and capability C11. Enforced at the type level, not at the test level.

Reason: every cash-equity disaster I have seen at any firm ultimately reduces to "someone wrote to the position because settlement told them to." Once that path exists, it gets used. Once it gets used, your books are wrong and you don't know it.

This is non-negotiable. It is the reason to do this work at all.

### Can live without: **CSDR penalty calculation in the Ledger.**

It is nice to have. It is not load-bearing. The CSD will tell us the penalty. We will pay it. We will reconcile against our own number where we have one, but if the CSD's number wins for booking purposes, we live. Compare to disclosing a wrong position to risk: that is unrecoverable.

If the project is over-budget at 60% of plan, drop CSDR penalty calculation. Keep settlement obligations as first-class objects with FSM and discharge/compensation. That gets you the 80% that matters.

---

## 13. What this proposal explicitly does not do (anti-overengineering)

In keeping with `ledger_data_v1.0` §V (Anti-Over-Engineering Vetoes):

- **Does not** add a fourth StatesHome map. The proposal lives entirely inside `L_15` (`Obligation`) plus the existing `Transaction`/`SettlementInstruction` types.
- **Does not** add a "Settlement Sector" or any new architectural tier.
- **Does not** invent a new event type. Settlement-status changes are state-only transactions, an existing pattern (corpus FAQ Q6, §lifecycle).
- **Does not** model real-world DvP atomicity. CSDs do that. We represent intent.
- **Does not** model intra-CSD settlement mechanics (NSCC CNS, Euroclear daylight credit, etc.). Out of scope.
- **Does not** prescribe whether settlement instruction generation runs in the Ledger or in a custodian system (corpus FAQ Q4 is right: framework is silent).
- **Does not** add a parallel "settlement state" sector that would force two-place writes for every status change.

---

## 14. Implementation plan — small team, finite time

Phase 1 (8 weeks, 2 engineers):
- `SettlementObligation` variant in `L_15`.
- One new closed-sum case on `DischargePredicateKind` and `CompensationHandlerKind`.
- `EXECUTED → INSTRUCTED → SETTLED | FAILED` substate FSM.
- Discharge predicate `ByMatch(sese.025/camt.054)` against `transaction_id`.
- Wiring from `L_11 ExternalConfirmation` ingress to obligation discharge.

Phase 2 (4 weeks, 2 engineers):
- Compensation κ for `SettlementFail` (re-instruct, partial, buy-in).
- BreakRegister wiring at the virtual-wallet boundary.
- Property tests: invariants I-1 through I-6. Mutation kill-rate ≥ 80% per StatesHome §8 thresholds.

Phase 3 (4 weeks, 1 engineer + 1 quant):
- CSDR penalty calculation. Cross-walk to CSD penalty notifications. Reconciliation tolerance.
- Operational runbook.

Phase 4 (2 weeks, 1 engineer):
- Cross-currency / Herstatt handling: per-leg obligations. Verify FX trades book two obligations.
- SBL recall-on-fail wiring (corpus §14 cascade).
- Documentation for ops, including the 03:00 runbook for fails.

**Total: 18 person-weeks, ~5 calendar months at 4 engineers worst case.** Realistic for a small team. No research project. Every component has prior art in the corpus.

---

## 15. Verdict

**APPROVE the architecture, with the following load-bearing amendments to the corpus:**

1. Add `SettlementObligation` as a `L_15` variant; the corpus already names it as a row in Table 13.2. Promote that row to a first-class definition.
2. State invariant I-1 explicitly: settlement-status transitions never write to positions. Enforce via C11 capability tagging.
3. Pin the per-status reconciliation cadence in §17.1 of `ledger_data_v1.0` to virtual-wallet-vs-custodian (not position-vs-custodian).
4. State explicitly: every cancellation goes through `CORRECTION`, four-eyes, named approver. No direct state edits, ever.
5. Cap obligation tree depth at 2 (parent + remainder). Past that, escalate to ops.

What was done well in the corpus already: trade-date accounting (§16.5), settlement projection purity (§16.1), virtual wallets for closure (§2.5), obligations as first-class objects (§13), self-consistency principle (§2.6), monotone carrier (StatesHome C1), capability-tagged mutation (StatesHome C11). This proposal stands on those shoulders. It does not invent.

The rule that is going to save us at 03:00 in three years: **the position is what we believe; settlement state is what the street has acknowledged so far. Never confuse the two.**

— CTO, Jane Street
