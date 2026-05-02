# Phase 2 — finops contribution: Reconciliation, Double-Entry Shape, Operational Reality

**Author role:** finops-architect (Settlement Team seat)
**Phase:** 2 (Settlement Team synthesis input — finops domain)
**Date:** 2026-04-30
**Anchored to:** v10.3 §2 (closed ledger), §8 (settlement projection), §11 (invariants); v10.3 StatesHome 3-map ruling; data v1.0 leaves $L_{11}$ ExternalConfirmation, $L_{13}$ MoveStream, $L_{15}$ Obligation, $L_{18}$ BreakRegister; mainstream Phase 1 convergence summarised in the orchestration brief.

---

## 0. The one-paragraph thesis

> The economic position is a real-wallet `own` write at T and is **never moved** by settlement. The open obligation lives in **two virtual wallet families** — `PS` (Pending Settlement, cash) and `PSS` (Pending Settlement Securities) — keyed `(real_wallet, counterparty_LEI, ccy_or_ISIN, side)`. These carry the contra-balances. An `L_15.Obligation` row of kind `SettlementInstructionDelivery` is registered atomically with the trade and tracks per-leg liveness with bounded horizon $T_{\max}$. A transaction-level FSM (`EXECUTED → INSTRUCTED → SETTLED | PARTIALLY_SETTLED | FAILED | CANCELLED`) lives on the `MoveStream` transaction record. The morning reconciliation to the nostro/depot is a **constant-time scan** over `PS`/`PSS` rows producing one algebraic identity per `(real_wallet, ccy_or_ISIN)`. Lead-lag is by design; the BreakRegister fires only when the identity fails outside the expected open-window contra. Replay of `sese.025` / `camt.054` is idempotent by deterministic `tx_id` derivation. **No fourth StatesHome map. No new GPM coordinate. No new conservation carve-out.** Two new wallet *classes* (KYC metadata in `WalletRegistry`, not state). One existing `L_15` obligation kind. One existing `L_13` transaction-type marker. That is the entire delta.

This document is finops's binding contribution to the Settlement Team's synthesis. It takes a single position on every contested question, exhibits the canonical worked example to the cent, states the algebraic recon identity, the BreakRegister rule book, the idempotency and decimal discipline, and rejects by name the alternative designs my Phase 1 colleagues proposed.

---

## 1. Final position: state representation

### 1.1 Decision (binding)

The deferred-settlement obligation is represented by a **triple**:

| Element | Where it lives | What it carries | Writer (C11 cap) |
|---|---|---|---|
| Real-wallet `own` write at T | `PositionState[w_real, u].own` | Economic position. Trade-date accounting. Never moved by settlement. | `apply_trade_move` (handler), at T only |
| Virtual `PS` / `PSS` wallet contra | `PositionState[w_PS, u].own` and `PositionState[w_PSS, u].own` | Per-(cpty, ccy_or_ISIN) open obligation **quantity**. Drains on finality. | Same `apply_trade_move` at T (initial credit/debit). Same handler at T+N (drain). |
| `L_15.Obligation` row, kind `SettlementInstructionDelivery` | `Obligation[obligation_id]` (data v1.0 $L_{15}$) | Per-leg lifecycle: `Pending → Discharged | Compensated | Defaulted`. Carries `intended_settlement_date`, `discharge_predicate`, `csdr_clock`. | `SettlementWorkflow` (Temporal). |
| Transaction-level settlement status | `MoveStream[tx_id].settlement_status` | `EXECUTED → INSTRUCTED → SETTLED | PARTIALLY_SETTLED | FAILED | CANCELLED`. Drives ops queue. | `SettlementWorkflow`; state-only transactions in `L_13`. |

The `PS`/`PSS` wallet pair holds the **contra-quantity**. The `L_15` row holds the **lifecycle**. The transaction-level status is a **convenience projection** over the obligation, kept on `L_13` for query speed.

### 1.2 What I reject by name

- **sbl (Margaret Chen) — seventh GPM coordinate `inflight`.** Rejected. This adds a stored coordinate to every `PositionState[w, u]` row — every cash wallet and every security wallet now carries a signed scalar that is non-zero only during the open window. The cost of this is: (a) every consumer of `PositionState` (PnL, risk, margin, capital, mandate breach) must know what `inflight` means and decide whether to include it — which is exactly the "is it own or is it own+inflight" trap that ashworth correctly named (§1.3 of his proposal). (b) The recon identity becomes a join on the coordinate dimension rather than a constant-time scan over a wallet family. (c) StatesHome §13 *Single-Coordinate Move Principle* is at risk: the trade move now writes `own` and `inflight` simultaneously on the same wallet — sbl tries to repair this by routing the `inflight` write to the *broker's* virtual wallet, but then the buyer's wallet still has zero `inflight` while the broker's has $-100$, which loses the per-counterparty granularity for the buyer. (d) The seventh-coordinate proposal collides with §13 SBL: the SBL six-coordinate is already a stress on the model; making it seven is one indirection too far. Margaret correctly identified the gap; the PS/PSS virtual-wallet pattern (matthias's, mine, karpathy's, geohot's, ashworth's, finops Phase 1) closes it without paying the seventh-coordinate price.

- **cartan (Henri Cartan) / halmos / matthias / minsky — the obligation as a first-class *unit*** (`u_obligation`, conserved, with $\sum_w w(u_{obl}) = 0$). I have sympathy for this — it is the most mathematically elegant position. I reject it on operational grounds. **The Goodhart test:** if obligations are units, then every consumer of `PositionState` that iterates over units now iterates over the obligation universe too. This means: the PnL valuation function must opt out (obligations have no price function — or worse, a degenerate one); the risk system must opt out; the regulatory reporter must opt out; the mandate-breach checker must opt out. Each opt-out is a place a bug can hide. The obligation-as-unit treatment also doubles the unit-master cardinality: every settlement creates a fresh unit, with its own ProductTerms row, its own UnitStatus row, its own per-position rows. Cartan is correct that the conservation law extends; that does not make it operationally cheap. **The PS/PSS pattern uses *existing* wallet semantics on *existing* units (the underlying ISIN and the underlying currency) — no new universe, no new opt-outs, no new unit-master rows.** Conservation falls out unchanged because PS/PSS are virtual wallets in the v10.3 §2.5 sense.

- **testcommittee / feynman — `pending_in` and `pending_out` as separate observable PositionState fields.** Rejected as state, accepted as **projections**. `pending_in(w, u)` and `pending_out(w, u)` are useful query shapes — testcommittee is right that the test suite wants to assert on them independently. But they are derivable from the PS/PSS wallet family by a constant-time scan: `pending_in(w, u) = -Σ_{cpty} PSS_receivable[w, cpty, u].own` (when `u` is a security; symmetric when `u` is cash via PS_receivable). Storing them as additional `PositionState` fields (as testcommittee proposes) duplicates state and reintroduces the StatesHome trap of "where does the contra live?" — the contra would be implicit. Storing them only as projections means the test layer gets the observable it wants without paying the storage cost. **My ruling: testcommittee's tests are accepted; the underlying coordinates are not.**

- **jane_street / isda / ashworth — single-aggregate inflight wallet per CSD or per CCP.** Partially accepted, partially rejected. ISDA proposes `w_csd_inflight[CSD, omnibus, book]` (one per CSD, aggregated across counterparties). Jane Street is more permissive. **Ashworth correctly identifies the right granularity: per-counterparty per-leg.** A CSD-level aggregate loses per-counterparty exposure attribution and per-counterparty CSDR penalty attribution — both of which are operationally non-negotiable. The recon engineer chasing a $13.42 break in a $1.2B aggregate cannot drill down to the failing trade if the wallet is keyed at the CSD level. **Per-counterparty per-currency-or-ISIN PS/PSS pair is the floor.** ISDA's CSD-level wallet can sit *above* the PS/PSS as a derived view, but the source of truth is the per-counterparty grain.

- **formalis (Coq committee) — single closed-sum status FSM with seven nodes including `BoughtIn`.** Accepted as the lifecycle FSM, with one structural correction. Formalis is right that the status FSM must be a closed sum (DS7-totality), and right that `BoughtIn` and `Cancelled` are terminal. I accept the seven-state FSM. The structural correction is: the FSM is per-**leg** (one per security leg, one per cash leg) on the obligation, not per-transaction. A DvP transaction with two legs has *two* obligation rows, *two* status FSMs, both running in parallel. The transaction-level status field on `L_13` is the join (typically `MAX` over the leg statuses by the lattice `Settled > Failed > Instructed > Executed`). This is needed for partial settlement (one leg can be Settled while the other is Failed in DvP Model 2/3 systems).

### 1.3 Why this is StatesHome-compliant — explicit check

| StatesHome map | Touched by deferred settlement? |
|---|---|
| `ProductTerms[u]` | No. Cash and securities terms unchanged. |
| `UnitStatus[u]` | No. Instrument-level lifecycle unaffected. |
| `PositionState[w, u]` | Yes — but only by **the existing handlers** (`apply_trade_move`, `apply_settlement_finality`). The PS/PSS wallets are new wallets in `WalletRegistry`; their balances sit in `PositionState` rows with the same `own` coordinate as every other wallet. **Zero new fields.** |
| `WalletRegistry[w]` (KYC, NOT state) | Yes — three new metadata fields: `wallet_class ∈ {real, virtual_cpty, virtual_PS, virtual_PSS, virtual_nostro, virtual_depot}`, `cpty_lei` (for PS/PSS variants), `expected_settle_window`. Permitted per StatesHome §2 (KYC sector). |

**Conformance verdict: PS/PSS pattern adds zero state to StatesHome. No fourth map.**

### 1.4 Conservation — explicit check

For every `(w, u)` pair touched by a deferred-settlement transaction at T or T+N:

$$\sum_{w \in \mathcal{W}_{\text{real}} \cup \mathcal{W}_{\text{virtual}}} \Delta w_t(u) = 0$$

per move pair. The PS/PSS wallets are full participants in $\mathcal{W}_{\text{virtual}}$ and contribute to the sum by construction (v10.3 §2.5 + §2.4). **No conservation carve-out.** This is the one place I will not negotiate.

### 1.5 Why the PS/PSS payable/receivable split (not signed-net)

For each `(w, cpty, ccy_or_ISIN)`, two virtual wallets, not one:

```
PS_payable[w, cpty, ccy]      -- "we owe cpty: cash leaving w"
PS_receivable[w, cpty, ccy]   -- "cpty owes w: cash arriving"
PSS_payable[w, cpty, ISIN]    -- "we owe cpty: securities leaving w"
PSS_receivable[w, cpty, ISIN] -- "cpty owes w: securities arriving"
```

Three operational reasons for the split, all of them finops vetoes on a signed-net design:

1. **Right-of-set-off is jurisdiction- and master-agreement-specific.** A signed-net wallet would silently net a payable under one ISDA master against a receivable under another, which the legal department will object to and which IFRS 7 disclosure (offsetting) requires us to disclose anyway. Two wallets — one always non-negative on each side — preserves the gross.

2. **Aged-payable and aged-receivable trigger different ops workflows.** CSDR penalties accrue against the *failing-to-deliver* party; buy-in clocks affect the *failing-to-deliver* party. The taxonomy is asymmetric. A signed-net wallet collapses this distinction.

3. **Conservation is cleaner when both sides are non-negative.** The standard double-entry convention since Pacioli (1494). Every general ledger in production uses it.

---

## 2. The standard-buy double-entry shape — canonical worked example

This is the load-bearing concrete artifact. **Every other section of `deferredSettlement.tex` should refer back to this block.**

### 2.1 Setup

- **Trade:** Buy 100 XYZ @ \$50.00 = \$5,000.00 cash leg.
- **Date:** T = 2026-04-30 14:32:11 UTC.
- **Settlement:** T+2 = 2026-05-04. (Same shape for T+1 with a single-day window.)
- **Real wallet:** `w_us` (our portfolio).
- **Counterparty:** Goldman Sachs broker, LEI `784F5XWPLTWKTBV3E584`, virtual broker wallet `w_GS_broker`.
- **CSD:** DTC for securities depot (`w_DTC_depot`); JPMC for cash nostro (`w_JPMC_nostro_USD`).
- **Pre-trade real-wallet state:** `w_us.own(USD) = 1,000,000.00`; `w_us.own(XYZ) = 0`.
- **External nostro state:** `w_JPMC_nostro_USD.own(USD) = 1,000,000.00` (JPMC reports our balance via daily `camt.053` end-of-day statement).
- **Mark-to-market:** $50.00 (T close), $52.00 (T+1 close, the prompt's specific mark), $51.50 (T+2 close).
- **Decimal discipline:** prices `D_8`, quantities `D_18` for fractional, `D_0` for whole-share equities, cash `D_2` for major currencies. **No floats anywhere.**

### 2.2 Move block at T (2026-04-30 14:32:11 UTC)

```
Transaction TX1:
  type:               ECONOMIC_RECOGNITION (sub-class of SETTLEMENT)
  tx_id:              hash("ECON_REC", "BUY", "XYZ", 100, 50.0000_0000, GS_LEI, "2026-04-30T14:32:11Z")
                    = "0xa7c3f1e8..." (deterministic; see §5)
  ts:                 2026-04-30T14:32:11Z
  metadata:           { expected_settlement_date: 2026-05-04, cpty_lei: GS_LEI,
                        venue_mic: XNYS, settlement_type: DVP, cdm_event: ExecutionEvent }

  -- Securities leg (economic recognition: w_us becomes long 100 XYZ at T)
  Move 1: from = PSS_receivable[w_us, GS, XYZ]
          to   = w_us
          unit = XYZ
          qty  = D_0(100)

  -- Cash leg (economic recognition: w_us owes 5,000 USD at T)
  Move 2: from = w_us
          to   = PS_payable[w_us, GS, USD]
          unit = USD
          qty  = D_2(5000.00)

  -- Atomic with the move pair: register the obligation in L_15
  L_15 register:
    obligation_id:           hash(tx_id, "leg_securities")
    kind:                    SettlementInstructionDelivery
    intended_settlement_date: 2026-05-04
    deadline:                2026-05-04T23:59:59Z (CSD timezone)
    discharge_predicate:     ByMatch(sese.025, ref=tx_id)
    compensation_handler:    SettlementFailHandler
    state:                   Pending

  L_15 register:
    obligation_id:           hash(tx_id, "leg_cash")
    kind:                    SettlementInstructionDelivery
    intended_settlement_date: 2026-05-04
    discharge_predicate:     ByMatch(camt.054, ref=tx_id)
    compensation_handler:    SettlementFailHandler
    state:                   Pending

  -- Atomic with the move pair: write the transaction-level status
  MoveStream[tx_id].settlement_status: EXECUTED
```

**Conservation check, per unit, atomically at T:**

| Unit | Δw_us | Δ(PSS_receivable[us,GS,XYZ]) | Δ(PS_payable[us,GS,USD]) | Σ |
|---|---:|---:|---:|---:|
| XYZ | +100 | -100 | 0 | 0 ✓ |
| USD | -5,000.00 | 0 | +5,000.00 | 0 ✓ |

**Wallet snapshot post-TX1:**

```
w_us.own(XYZ)                            = +100
w_us.own(USD)                            = +995,000.00
PSS_receivable[w_us, GS, XYZ].own(XYZ)   = -100        (GS owes us 100 XYZ)
PS_payable[w_us, GS, USD].own(USD)       = +5,000.00   (we owe GS 5,000 USD)
w_GS_broker.own(XYZ)                     = 0
w_GS_broker.own(USD)                     = 0
w_DTC_depot.own(XYZ)                     = 0
w_JPMC_nostro_USD.own(USD)               = +1,000,000.00 (per last camt.053; reconciles below)
```

Conservation across the whole system, USD: `995,000 + 5,000 + 0 + 1,000,000 = 2,000,000` (the doubling is because the nostro is a *mirror* of the same cash that lives in `w_us.own(USD)` — see §3.2 for the recon identity that ties these). XYZ: `100 + (-100) + 0 + 0 = 0` ✓.

### 2.3 At T+1 close (2026-05-01 21:00 UTC, XYZ → \$52.00)

**No moves emitted.** Position is unchanged. Status remains `EXECUTED` (or `INSTRUCTED` if the settlement layer has fired the `sese.023` during the day, which is the typical case for US T+2):

```
Optional state-only transaction at any time before T+2 morning:

Transaction TX1_INSTRUCT:
  type:    LIFECYCLE
  moves:   []   (empty)
  metadata: { refers_to_tx: TX1.tx_id, new_status: INSTRUCTED, ssi_used: hash(SSI),
              outbound_iso20022: "sese.023.001-msg-id-..." }

  L_13: append the (move-less) transaction.
  MoveStream[TX1.tx_id].settlement_status: EXECUTED → INSTRUCTED
  L_15: no change (still Pending; instruction-emit does not discharge).
```

State-only transactions are valid per v10.3 FAQ Q6 ("move-less events are valid lifecycle events") and per StatesHome C9 (handlers on zero-move transactions discharge `Σ = 0` vacuously).

**PnL at T+1 close:**

```
V_{T+1}(w_us) = w_us.own(USD) × P_{T+1}(USD) + w_us.own(XYZ) × P_{T+1}(XYZ)
              = 995,000.00 × 1.0000 + 100 × 52.0000
              = 995,000.00 + 5,200.00
              = 1,000,200.00

PnL_{T+1} = V_{T+1} - V_T = 1,000,200.00 - 1,000,000.00 = +200.00
```

**+\$200.00 P&L with zero cash movement and zero settlement movement.** This is the headline guarantee of the spec — the entire reason for trade-date accounting. The PS/PSS wallets carry their open balances; the obligation FSM remains `Pending`; the position is correct.

### 2.4 At T+2 morning (2026-05-04 09:00 UTC, before finality)

No moves. State unchanged from T+1. Morning recon report runs (§3.4). Status `INSTRUCTED` if not already.

### 2.5 At T+2 finality (2026-05-04 ~16:30 UTC, after DTC end-of-day batch)

DTC reports DvP finality via `sese.025` (securities) and `camt.054` (cash debit). Both inbound on `L_11.ExternalConfirmation`. The `SettlementWorkflow` consumes the signal and emits the **finality contra-transaction**:

```
Transaction TX1_FINAL:
  type:               SETTLEMENT_FINALITY (sub-class of SETTLEMENT)
  tx_id:              hash("FINAL", TX1.tx_id, sese.025_msg_id, camt.054_msg_id)
                    = "0xb8d4..." (deterministic; see §5)
  ts:                 2026-05-04T16:30:42Z
  metadata:           { refers_to_tx: TX1.tx_id, finality_attestation_lei: DTC_LEI,
                        sese.025_msg_id: "...", camt.054_msg_id: "..." }

  -- Securities leg: drain the PSS_receivable into broker virtual wallet
  Move 1: from = w_GS_broker
          to   = PSS_receivable[w_us, GS, XYZ]
          unit = XYZ
          qty  = D_0(100)
  -- After: PSS_receivable goes from -100 to 0; w_GS_broker goes from 0 to -100
  --        (GS now shows -100 XYZ in our books, mirroring their delivery)

  -- Cash leg: drain the PS_payable into broker virtual wallet
  Move 2: from = PS_payable[w_us, GS, USD]
          to   = w_GS_broker
          unit = USD
          qty  = D_2(5000.00)
  -- After: PS_payable goes from +5,000 to 0; w_GS_broker goes from 0 to +5,000

  -- Atomic with the moves: discharge the obligations
  L_15 update obligation_id=hash(TX1.tx_id, "leg_securities").state: Pending → Discharged
  L_15 update obligation_id=hash(TX1.tx_id, "leg_cash").state:       Pending → Discharged
  MoveStream[TX1.tx_id].settlement_status: INSTRUCTED → SETTLED
```

**Conservation check:**

| Unit | Δw_us | ΔPSS_receivable | ΔPS_payable | Δw_GS_broker | Σ |
|---|---:|---:|---:|---:|---:|
| XYZ | 0 | +100 | 0 | -100 | 0 ✓ |
| USD | 0 | 0 | -5,000 | +5,000 | 0 ✓ |

**Wallet snapshot post-TX1_FINAL:**

```
w_us.own(XYZ)                          = +100        (UNCHANGED from T)
w_us.own(USD)                          = +995,000   (UNCHANGED from T)
PSS_receivable[w_us, GS, XYZ].own      = 0          (drained)
PS_payable[w_us, GS, USD].own          = 0          (drained)
w_GS_broker.own(XYZ)                   = -100       (mirrors GS's delivery)
w_GS_broker.own(USD)                   = +5,000.00  (mirrors GS's receipt)
```

**The position on `w_us` is invariant from T through T+2.** This is the structural commitment. The PS/PSS wallets transit `0 → non-zero → 0` over the open window. The broker virtual wallet absorbs the post-finality contra. That contra reconciles bilaterally with GS's own books (if they run a compatible ledger; otherwise it is a derived view of the SWIFT/CDS message stream against GS).

### 2.6 Conservation summary across the four states

USD (cash leg):

| State | w_us(USD) | PS_payable[w_us,GS,USD] | w_GS_broker(USD) | w_JPMC_nostro_USD | Σ_internal | nostro_external |
|---|---:|---:|---:|---:|---:|---:|
| T⁻ pre-trade | 1,000,000 | 0 | 0 | 1,000,000 | 1,000,000 | 1,000,000 |
| T⁺ post-trade | 995,000 | +5,000 | 0 | 1,000,000 | 1,000,000 | 1,000,000 |
| T+1 | 995,000 | +5,000 | 0 | 1,000,000 | 1,000,000 | 1,000,000 |
| T+2⁻ instructed | 995,000 | +5,000 | 0 | 1,000,000 | 1,000,000 | 1,000,000 |
| T+2⁺ finality | 995,000 | 0 | +5,000 | 995,000 | 1,000,000 | 995,000 |

(Σ_internal = `w_us + PS_payable + w_GS_broker`, the closed-system internal sum, holds at $1,000,000 throughout. `nostro_external` is the JPMC-reported balance, which **leads** the internal cash-out by the open window — the recon identity in §3.1 ties these.)

XYZ (securities leg):

| State | w_us(XYZ) | PSS_recv[w_us,GS,XYZ] | w_GS_broker(XYZ) | w_DTC_depot(XYZ) | Σ_internal | depot_external |
|---|---:|---:|---:|---:|---:|---:|
| T⁻ | 0 | 0 | 0 | 0 | 0 | 0 |
| T⁺ | +100 | -100 | 0 | 0 | 0 | 0 |
| T+1 | +100 | -100 | 0 | 0 | 0 | 0 |
| T+2⁻ | +100 | -100 | 0 | 0 | 0 | 0 |
| T+2⁺ | +100 | 0 | -100 | +100 | 0 | +100 |

Conservation `Σ_w w(XYZ) = 0` holds at every step; the `w_DTC_depot(XYZ) = +100` post-finality is the depot's mirror of our holding (DTC holds the shares for us in our omnibus account).

### 2.7 PnL at T+2 close (XYZ = \$51.50)

```
V_{T+2} = 995,000.00 × 1.00 + 100 × 51.50
        = 995,000.00 + 5,150.00
        = 1,000,150.00

PnL_{T+2}  = V_{T+2} - V_{T+1} = 1,000,150 - 1,000,200 = -50.00
PnL_{cum}  = V_{T+2} - V_T     = 1,000,150 - 1,000,000 = +150.00 ✓
                              = +200 (T+1 mark-up) - 50 (T+2 mark-down)
```

PnL path-independence (v10.3 P10) holds across the entire trade lifecycle, T-through-settled, with **zero** moves on `w_us` after T.

---

## 3. The reconciliation identity — algebraic, not heuristic

### 3.1 The fundamental identity

For every `(real_wallet w, currency ccy)` pair at any wall-clock time `t`:

$$\boxed{\;
\text{nostro\_external}(w, \text{ccy}, t) \;=\; w_t.\text{own}(\text{ccy}) \;+\; \sum_{\text{cpty}} \text{PS\_payable}[w, \text{cpty}, \text{ccy}]_t \;-\; \sum_{\text{cpty}} \text{PS\_receivable}[w, \text{cpty}, \text{ccy}]_t \;-\; \text{inflight\_out}(w, \text{ccy}, t) \;+\; \text{inflight\_in}(w, \text{ccy}, t)
\;}$$

where:
- `w.own(ccy)` is the **internal** ledger view of our cash (already debited at trade time).
- `PS_payable` / `PS_receivable` are the open-window contra-balances (they sum across all open trades).
- `inflight_out` / `inflight_in` are *wire-level* in-flight amounts: cash sent to JPMC's outgoing wire queue but not yet acknowledged as debited (`inflight_out`), or cash credited via incoming wire but not yet posted (`inflight_in`). These are tracked in their own virtual wallet pair `w_JPMC_outgoing_USD` / `w_JPMC_incoming_USD` for completeness; they are typically zero outside an active wire window.

**Equivalent identity for securities** for every `(real_wallet w, ISIN s)`:

$$\text{depot\_external}(w, s, t) \;=\; w_t.\text{own}(s) \;+\; \sum_{\text{cpty}} \text{PSS\_payable}[w, \text{cpty}, s]_t \;-\; \sum_{\text{cpty}} \text{PSS\_receivable}[w, \text{cpty}, s]_t \;-\; \text{depot\_out}(w, s, t) \;+\; \text{depot\_in}(w, s, t)$$

### 3.2 The sign discipline (load-bearing)

When **WE owe** (`PS_payable > 0`) and the wire **hasn't gone out**, JPMC still shows our balance fat — `nostro_external` = internal `own` + the unpaid payable. When **someone else owes us** (`PS_receivable > 0`, recorded as a *negative* PSS balance internally — see §1.5; for the cash side `PS_receivable` is positive) and the wire hasn't arrived, JPMC shows our balance lean.

This is the sign convention I caught a bug on in my own Phase 1 §7.7 — the corrected identity is the one above. **The Phase 2 spec uses this corrected identity. Phase 1 §4.1 sign was wrong; this supersedes it.**

Verification with the §2 worked example, T+2 morning (before finality):

```
LHS = nostro_external (per camt.053) = 1,000,000.00
RHS = w_us.own(USD) + PS_payable - PS_receivable - inflight_out + inflight_in
    = 995,000.00 + 5,000.00 - 0 - 0 + 0
    = 1,000,000.00 ✓
```

T+2 evening (post-finality):

```
LHS = nostro_external = 995,000.00 (JPMC has now debited)
RHS = 995,000.00 + 0 - 0 - 0 + 0 = 995,000.00 ✓
```

### 3.3 Constant-time scan, not a join

The algebraic identity is **constant-time** per `(w, ccy)` because:

```sql
SELECT w_id, ccy,
       SUM(CASE WHEN wallet_class='virtual_PS_payable'
                 AND real_wallet=:w THEN balance ELSE 0 END) AS sum_payable,
       SUM(CASE WHEN wallet_class='virtual_PS_receivable'
                 AND real_wallet=:w THEN balance ELSE 0 END) AS sum_receivable
FROM   position_state ps
JOIN   wallet_registry wr ON ps.wallet_id = wr.wallet_id
WHERE  wr.real_wallet = :w
   AND ps.unit = :ccy
GROUP  BY w_id, ccy;
```

— a single grouped scan over the PS/PSS wallet rows for that real wallet, bounded by the number of *open-trade counterparties for this real wallet* (typically dozens to hundreds, not millions). **No join to `MoveStream`. No replay over the open-instruction set.** This is the operational point that distinguishes PS/PSS-as-wallet from inflight-as-projection-over-tx-log: a million open trades aggregate into a thousand wallet rows, and the scan is bounded by the wallet count, not the transaction count.

This is the finops veto that drives the entire design.

### 3.4 Morning recon report shape — T, T+1, T+2, T+3

The morning recon report runs as a Temporal cron workflow `MorningReconWorkflow` at 09:00 local in each reporting timezone. Output structure:

**Per-counterparty row, one row per `(cpty_lei, ccy_or_ISIN, settle_bucket)`:**

```
counterparty | ccy | bucket    | gross_payable | gross_receivable | net      | trade_count | aging
-------------|-----|-----------|---------------|-------------------|----------|-------------|------
GS           | USD | T+0       |      12,500.00|         5,000.00  | +7,500   |     4       | 0bd
GS           | USD | T+1       |       5,000.00|             0.00  | +5,000   |     1       | 1bd
GS           | USD | T+2_TODAY |   1,250,000.00|       812,000.00  | +438,000 |    47       | 2bd
GS           | USD | OVERDUE   |           0.00|       150,000.00  | -150,000 |     1       | 3bd  AGED
JPMC         | USD | T+0       |      80,000.00|        80,000.00  |        0 |    12       | 0bd
...
```

**Per-currency aggregate row, one per `(real_wallet, ccy)`:**

```
real_wallet:               w_us
ccy:                       USD
nostro_external_balance:   1,234,567.89   (camt.053 from L_11)
own_internal:              1,229,567.89
+ Σ PS_payable:                5,000.00
- Σ PS_receivable:                 0.00
- inflight_out:                    0.00
+ inflight_in:                     0.00
─────────────────────────────────────────
expected_nostro:           1,234,567.89
break:                             0.00 ✓
```

The bucket field is `expected_settlement_date - today` (in business days, using the venue calendar from data v1.0 $L_1$). Buckets:
- `T+N` for N ≥ 1: forward open exposure.
- `T+0` for N = 0: trades that settled today already (just-discharged window).
- `T+2_TODAY` (or `T+1_TODAY` for T+1 markets, etc.): trades **settling today** — operations watch this bucket like a hawk; every trade here must be `INSTRUCTED` before market open.
- `OVERDUE`: any trade past `expected_settlement_date` not in `{SETTLED, FAILED, PARTIALLY_SETTLED, CANCELLED}` — escalates to `wf-confirm-break`.

Aging in business days, computed using the trade venue's calendar (data v1.0 $L_1$ `CalendarConvention`).

### 3.5 What is a break and what is not

**Not a break — expected lead-lag during the open window:**

- `PS_payable[w, *, ccy] > 0` for any open trade with `expected_settlement_date ≥ today`. Expected.
- `PSS_receivable[w, *, s] < 0` for any open trade with `expected_settlement_date ≥ today`. Expected.
- `nostro_external > w.own(ccy)` by exactly `Σ PS_payable - Σ PS_receivable + (signed wire inflight)`. Expected.
- An `EXECUTED`-status trade pending instruction, before the affirmation cutoff (data v1.0 §11.5: 9pm ET T+0 for T+1 affirmation; venue-specific). Expected.
- An `INSTRUCTED`-status trade pending finality, before end-of-day on `expected_settlement_date`. Expected.
- A `sese.025` finality message arriving up to 1bd after `expected_settlement_date` for cross-border trades (Asia settling in our morning). Expected with a venue-specific grace.

**Is a break — `BreakRegister` entry created per `L_18` FSM (`Open → Investigating → Assigned → Aged-1 → ...`):**

| Condition | Workflow | Owner |
|---|---|---|
| `\|nostro_external - RHS\| > tolerance` after stripping expected lead-lag | `wf-position-break` | Middle-office reconciliation |
| Trade past `expected_settlement_date` with `status ∉ {SETTLED, FAILED, PARTIALLY_SETTLED, CANCELLED}` after end-of-business-day | `wf-confirm-break` | Settlement operations |
| `sese.025` finality with no matching recognition transaction (`refers_to_tx` not found) | `wf-confirm-break` | Settlement operations |
| `sese.025` arriving with **wrong amount or quantity** vs. the recognition tx | `wf-confirm-break` (HARD: do **not** apply the finality moves; quarantine) | Settlement operations + counterparty desk |
| `sese.024` (CSD fail attestation) inbound | `wf-confirm-break` + spawn `CSDR_PENALTY` obligation in `L_15` | Settlement operations |
| Recognition tx with no matching finality after `T_max = expected + 5bd` (CSDR liquid equities) | `wf-obligation-break` (auto via `L_15` Obligation Liveness Theorem 3) | Settlement operations |
| Duplicate `sese.025` with same `(refers_to_tx, finality_attestation_id)` | **Idempotently dropped** by the executor (P5); not a break. Logged. | n/a |

### 3.6 Decimal handling at recon time — non-negotiable

- **Cash:** `Decimal(18, 2)` for major currencies (USD, EUR, GBP, JPY-as-integer-yen-with-2dp-internal). `Decimal(18, 4)` for currencies with sub-cent ticks in some EM crosses. `Decimal(18, 0)` for true integer currencies (JPY when held without sub-yen accumulation; CLP).
- **Securities quantities:** `Decimal(18, 6)` for the framework default (allows fractional for tokenised). Native equities use `Decimal(18, 0)`.
- **Prices:** `Decimal(18, 8)` (`D_8` per the prompt's spec). Sub-tick precision for FX-derived prices.
- **Recon tolerance:** explicit per currency, **versioned in `L_7^P.PolicyConfiguration`** (data v1.0 anti-Goodhart §15). No magic numbers in code. Default: 0 USD (cents recon required for USD); 0 EUR; £0.01 GBP for low-volume; JPY rounding policy in `L_4` calendar/convention sidecar. Changes to tolerances require four-eyes per data v1.0 §15.
- **No floats in the recon pipeline.** Period. Any code path that decimal-to-float-to-decimal round-trips for any reason — ban at code review.
- **Rounding mode:** `ROUND_HALF_EVEN` (banker's). Hardcoded; no per-call override.
- **Currency conversion at recon:** forbidden. Recon is per-currency. Cross-currency (Herstatt) recon is a separate workflow (§4.5 below).

---

## 4. Reconciliation operational discipline

### 4.1 Cadence

| Recon | Cadence | Window | Owner |
|---|---|---|---|
| Custodian/CSD depot vs ledger position + open inflight | Daily 09:00 local + intraday on each `sese.025` | All open trades | Middle-office |
| Cash nostro vs ledger USD/EUR/etc per real wallet | Daily 09:00 local + intraday on each `camt.054` | All real cash wallets | Treasury ops |
| CSD `sese.024` participant statement vs L_15 open obligations | Daily | All open obligations | Settlement ops |
| MiFIR/EMIR Refit/SFTR ack from TR | T+1 morning | All trades reportable | Regulatory ops |
| CSDR cash penalty advice (semt.0xx) vs accrued | Monthly | All failed trades closed in month | Settlement ops |
| Block-and-allocation chain reconciliation | Per allocation event + EOD | All open block trades | Allocation ops |

### 4.2 The recon engine — one report, three breaks-categorisations

Every recon run emits exactly three sets:

1. **CLEAN** — identity holds within tolerance per `(w, ccy)` and per `(w, ISIN)`. No action.
2. **EXPECTED LEAD-LAG** — identity violated by an amount exactly explained by open PS/PSS contras and open wire-level inflight. No action; this is the open-window state.
3. **BREAK** — identity violated by an amount NOT explained by (1) or (2). `BreakRegister` row created with kind, owner, deadline, expected resolution.

The classification is **purely algebraic.** No manual triage. If a recon engineer is staring at a screen wondering "is this a break or expected?", we have failed the spec.

### 4.3 Multi-day fail aging — the L_18 FSM mapping

Per data v1.0 §10 ($L_{18}$), the `BreakRegister` FSM:

```
Open → Investigating → Assigned → Aged-1 → Aged-3 → Aged-5 → Escalated → At-Risk → Material → Closed-{Clean | Adj | Waived}
```

Aging in business days. Concrete attachment to settlement breaks:

| Aging state | Trigger | Action | CSDR alignment |
|---|---|---|---|
| Open | New mismatch | Investigate; ops queue | n/a |
| Investigating | T+0 | Owner assigned, root-cause hunt | n/a |
| Aged-1 | T+1 bd unresolved | Notify supervisor; CSDR penalty accrual day 1 | CSDR Day 1 |
| Aged-3 | T+3 bd | Escalate to head of desk | CSDR liquid: extension period typically expires here |
| Aged-5 | T+5 bd | Escalate to head of operations; auto-promote to obligation default candidate | CSDR mandatory buy-in trigger window for liquid equities (4-7 bd post-ISD per ESMA) |
| At-Risk | exposure ≥ €1M (configurable per `L_7^P`) | Risk committee | — |
| Material | exposure ≥ €10M | Governance committee + regulator notification per BCBS 239 | — |
| Closed-Waived | Resolved by waiver | Four-eyes per L_18 | — |

### 4.4 CSDR cash penalty accrual — pure-function discipline

For every `sese.024` fail attestation matching a recognition transaction:

1. Spawn `Obligation` row of kind `CSDR_PENALTY` in `L_15` (data v1.0 §10):
   ```
   obligation_id:           hash("CSDR_PENALTY", refers_to_tx, intended_settle_date)
   kind:                    CSDR_PENALTY
   discharge_predicate:     ByDeadline(buy_in_resolution_date)
   compensation_handler:    NonTrivialChildWorkflow (CSDR penalty payment workflow)
   fields:
     qty_failed:           D_0 or D_18 per instrument
     price_at_intended:    D_8 (pinned via refdata at intended settle date)
     ccy:                  ISO-4217
     attribution_lei:      LEI of failing party
     instrument_class:     CSDRLiquidityClassEnum (LiquidShares | NonLiquidShares | ...)
     rate_bps:             D_4 (per ESMA Penalty Matrix, pinned via refdata_pin)
     accrual_start:        intended_settle_date + 1 bd
   state: Pending
   ```

2. Each business day until discharge, the daily-CSDR-accrual workflow emits:
   ```
   Transaction TX_csdr_daily:
     type: SETTLEMENT
     tx_id: hash("CSDR_DAILY", obligation_id, accrual_date)
     Move: from = w_failing_cpty   (virtual broker wallet)
           to   = w_us
           unit = USD (or relevant ccy)
           qty  = D_2(qty_failed × price_at_intended × rate_bps × 1bd / 10_000)
   ```

3. Settlement to T2S monthly cycle: aggregated penalty payments via `pacs.008`. The aggregate matches the daily accrual sum to the cent or the ESMA monthly statement is the break.

**Penalty amount is a pure function of `(qty_failed, price_at_intended, days_late, instrument_class)` and the `refdata_pin`.** No human inputs. No discretion. Auditable.

### 4.5 Cross-currency / Herstatt — paired recon, asymmetric drain

Herstatt risk (the asymmetric-settlement of a USD/JPY trade where USD pays at NY morning and JPY confirms at Tokyo afternoon, leaving an open exposure overnight) is **not eliminable** at the framework level — it is a real-world timing risk between two CSDs (v10.3 §2.7).

What the framework **does**:

1. Each leg of a cross-currency trade is its own recognition transaction with its own PS/PSS pair.
2. The two legs share a `business_event_id` linking them (CDM `BusinessEvent`).
3. The morning recon report explicitly highlights `business_event_id` rows where one leg shows `PS_payable = 0` (settled) and the other shows `PS_payable > 0` (still open) — the **Herstatt indicator**.
4. Operations subscribes to the Herstatt indicator. At any non-zero indicator, the open exposure is the open leg's USD-equivalent cash amount × the FX volatility for the gap window. Risk system reads this as a separate exposure category.
5. CLS-eligible currencies: the FX leg is recorded with `settlement_venue = CLS` metadata; CLS PvP atomicity is external; the framework records the compound finality message that says both legs cleared together.

Cross-currency recon is **not** a single SQL identity; it is two single-currency identities + a Herstatt indicator. No conversion at recon.

---

## 5. Idempotency under replay — deterministic tx_id derivation

### 5.1 The deterministic `tx_id` formula

Every transaction's `tx_id` is computed deterministically from inputs that are **available at message-receipt time**, with no state-dependent components.

**Recognition transaction:**

```
tx_id = hash_sha256(
  "ECON_REC",                               -- transaction class
  side,                                     -- "BUY" | "SELL"
  isin,                                     -- ISIN of the security
  qty_canonical,                            -- D_18 canonical decimal repr
  price_canonical,                          -- D_8 canonical decimal repr
  ccy,                                      -- ISO-4217
  cpty_lei,                                 -- LEI of counterparty
  trade_timestamp_utc,                      -- RFC 3339 UTC, microsecond precision
  venue_mic,                                -- ISO 10383 MIC
  expected_settlement_date,                 -- ISO 8601 calendar date in venue tz
  external_trade_ref                        -- venue's trade reference (e.g., FIX ExecID)
)
```

The `external_trade_ref` is the load-bearing component for true uniqueness — without it, two trades with identical other fields collide. With it, replay of the same FIX execution report produces the same `tx_id`. **Critical: `external_trade_ref` must be present and globally unique within the venue's namespace, or the deterministic property fails.** This is the inherited limitation v10.3 acknowledges; in practice all venues guarantee unique ExecIDs.

**Finality transaction:**

```
tx_id = hash_sha256(
  "FINAL",
  refers_to_tx,                             -- the recognition tx_id
  attestation_message_id,                   -- the sese.025 / camt.054 EndToEndId
  attestation_attempt_seq                   -- 0 for first, 1 for re-confirmation, ...
)
```

**State-only lifecycle transaction (status update):**

```
tx_id = hash_sha256(
  "LIFECYCLE",
  refers_to_tx,                             -- the recognition tx_id
  new_status,                               -- "INSTRUCTED" | "PARTIAL" | "FAILED" | ...
  external_event_id                         -- e.g., sese.023 EndToEndId for INSTRUCTED, sese.024 for FAILED
)
```

### 5.2 The idempotency contract

Per v10.3 P5 (transaction idempotency by `tx_id`) plus the deterministic derivation:

1. The settlement orchestration workflow consumes a CSD message.
2. Computes the deterministic `tx_id` per §5.1.
3. Queries `L_13.MoveStream` for existing transaction with this `tx_id`.
4. If found: workflow exits no-op. **Replay is idempotent.**
5. If not: emits the transaction; commits atomically with `L_15` and `MoveStream` writes per StatesHome C3.

**A duplicate `sese.025` from a flapping CSD link does not create a duplicate finality.** Critical.

### 5.3 Out-of-order ingest — formalis DS5

Per formalis DS5 (replay determinism under out-of-order confirmations): the matching from confirmation → recognition tx is a pure function of the `EndToEndId`. The `L_15` FSM transitions on disjoint obligation rows commute, so the joint state is invariant under interleaving. Conservation is unaffected because lifecycle transitions emit no moves on real wallets.

### 5.4 No write-amplification

Replay-safety must not come at the cost of `L_13` write-amplification. The discipline:

- Every `sese.025` ingest: one `tx_id` query + one conditional write. **At most one new row per finality, per replay, regardless of how many times the message is replayed.**
- Every status transition: one `MoveStream` write (state-only) + one `L_15` write. **No retries amplify.**
- No update-in-place. All writes are appends to immutable logs (StatesHome C5 monotone carrier).

### 5.5 Message storms

10,000 `sese.025` messages arriving in 60 seconds (typical end-of-day batch from DTC for an active broker-dealer) are processed by Temporal child workflows in parallel. Each workflow is single-writer per `tx_id` namespace (per StatesHome C11); cross-workflow serialisation is on the `MoveStream` append. Throughput target: 1,000 transactions/sec on a single executor; T+0 morning batch must drain within 30 minutes. Beyond this scale, partition by `cpty_lei`.

---

## 6. Decimal / money / quantity discipline — explicit rules

### 6.1 The contract

| Quantity | Type | Rationale |
|---|---|---|
| Cash amounts (USD, EUR, GBP, etc.) | `Decimal(18, 2)` | Two minor units. 18 digits = up to ~$10^{16}, sufficient for any single trade. |
| Cash amounts (JPY) | `Decimal(18, 0)` | Yen is integer; sub-yen accumulation forbidden by JFSA. |
| Cash amounts (high-precision EM crosses) | `Decimal(18, 4)` | E.g., IDR per USD with 4dp internal. |
| Securities quantities (whole-share equity) | `Decimal(18, 0)` | DTCC, Euroclear convention. |
| Securities quantities (fractional / tokenised) | `Decimal(18, 6)` | Six decimal places for tokenised; per data v1.0. |
| Prices | `Decimal(18, 8)` | FX-derived prices need 8dp; equity tick sizes typically 4dp but stored at 8 for cross-asset. |
| FX rates | `Decimal(18, 8)` | Same. |
| Yields, rates (bps) | `Decimal(18, 4)` | One bp = 0.0001; 4dp gives sub-bp. |
| Tolerances | `Decimal(18, 8)` | Always strictly typed. |

### 6.2 Per-currency tolerances (versioned)

Stored in `L_7^P.PolicyConfiguration` keyed `(ccy, recon_kind)`. Default values for cash recon at the nostro:

```
USD: 0.00       (cents recon required)
EUR: 0.00
GBP: 0.00
JPY: 0          (integer; tolerance is an integer count of yen)
CHF: 0.01       (default; some custodians round)
HKD: 0.00
SGD: 0.00
EM crosses: per-pair, default 0.0001
```

Override requires four-eyes governance per data v1.0 §15. Tolerance changes are bitemporal — an old recon at an old tolerance is reproducible with `t_known = old`.

### 6.3 Rounding mode

`ROUND_HALF_EVEN` (banker's rounding, IEEE 754 default). Hardcoded at the framework boundary; no per-call override. Justification: avoids systematic upward bias of `ROUND_HALF_UP` over a large population of trades, which would create a statistically detectable drift over 10⁶ trades.

### 6.4 Forbidden patterns

- **No floats in any code path that touches money or quantities.** Code review hard-fail on any `float()` cast.
- **No string concatenation for amounts.** Always Decimal-to-Decimal arithmetic.
- **No implicit currency conversion.** All FX must go through an explicit `convert(amount, from_ccy, to_ccy, rate, t_obs)` call that pins the rate and the observation time.
- **No `==` comparison of decimals.** Always `abs(a - b) <= tolerance` with the tolerance per `L_7^P`.
- **No `round()` on prices before storage.** Prices are stored raw at `D_8`; rounding happens at presentation only.

---

## 7. Operational corner cases

These are the cases the other proposals may have understated. Each gets a binding ruling.

### 7.1 Late corrections — FIX 35=H corrections after T+1

A counterparty issues a correction the day after trade. The trade reference is the same; price or quantity is corrected.

**Ruling:** the original `tx_id` is **not** reused. A new transaction with `type = CORRECTION` is appended:

```
Transaction TX1_CORRECTION:
  type:    CORRECTION
  tx_id:   hash("CORRECTION", original_tx_id, correction_seq, correction_timestamp)
  metadata: { refers_to_tx: TX1.tx_id, correction_kind: PRICE | QTY | BOTH,
              old_price: 50.00, new_price: 50.05,
              old_qty: 100, new_qty: 100, ... }

  -- Anti-moves of the original (full reversal of TX1's economic moves)
  Move: from = w_us, to = PSS_receivable[w_us, GS, XYZ], unit = XYZ, qty = 100
  Move: from = PS_payable[w_us, GS, USD], to = w_us, unit = USD, qty = 5000

  -- New economic moves at the corrected price
  Move: from = PSS_receivable[w_us, GS, XYZ], to = w_us, unit = XYZ, qty = 100
  Move: from = w_us, to = PS_payable[w_us, GS, USD], unit = USD, qty = 5005
```

Net: position unchanged at `+100 XYZ`; PS_payable went from +5000 to +5005 ($5 correction). Original TX1 stays in `L_13` (P4 log monotonicity); both visible in audit trail.

PnL impact on the correction date: `+5.00` realised loss (we paid $5 more than originally booked). This hits `MoveStream`-based PnL on the correction date, not retrospectively. The intervening $200 mark-to-market PnL stays on the books at the original cost basis days; the $5 correction is a separate event.

### 7.2 Retroactive amendments — FIX 35=H received after T+2 settlement

A correction comes in *after* the original trade has already settled (rare but happens for late ATS reports).

**Ruling:** treat as a new *post-settlement* `CORRECTION` transaction. Anti-moves the *settled* form (which moved cash and securities into the broker virtual wallet); re-emits the correct settled form. The `BreakRegister` receives a Stage 2 entry (post-settlement adjustment) which requires four-eyes approval per `L_18` to close.

Operationally, a retroactive amendment after T+2 is *expensive* — it triggers a CSDR fail-fix cycle and possibly a wash trade on the cash leg. Operations should track the count and chase counterparties whose correction-rate exceeds 0.1% of trades.

### 7.3 Manual overrides — what the recon engineer can and cannot do

A recon engineer chasing a $13.42 break may need to override a wallet balance. **Hard rule:** they cannot. Position state is monotone; the only way to change `w.own(u)` is to emit a transaction. The override mechanism:

```
Transaction TX_MANUAL_RECON:
  type:    CORRECTION
  tx_id:   hash("MANUAL_RECON", break_id, four_eyes_id_pair, timestamp)
  metadata: { break_id: B-2026-04-30-001, reason: "INVESTIGATION_FOUND_BROKER_BUG",
              approver_lei: LEI1, approver_lei: LEI2, ... }
  Move: from = w_us, to = w_recon_provision, unit = USD, qty = 13.42
  -- (or any other correcting moves)
```

Four-eyes is enforced by `L_18.Closed-Waived` requirement (data v1.0 §10). Two distinct LEIs must sign. The transaction is in the immutable log; anyone can audit who approved what.

Manual override is a **last resort.** The recon engine should resolve >99.5% of breaks algebraically. If manual overrides exceed 0.5% of breaks in a month, the framework configuration is wrong and we revisit.

### 7.4 Golden-source disagreement — CSD says A, back-office says B

The CSD reports finality at quantity 100; our back-office (counterparty desk's confirmation system) shows 99. The framework's golden source is **the CSD** for settlement finality (per v10.3 §2.7 and ISDA's DRR golden-source position). The back-office is wrong. But:

**Ruling:** we DO NOT auto-apply the CSD's finality if it disagrees with our recognition. The finality is **quarantined** in `L_11.ExternalConfirmation` with `quarantine_reason = QTY_MISMATCH`. The recognition tx remains `INSTRUCTED`. A `wf-confirm-break` opens. Investigation determines (a) whether our recognition was wrong (price/qty correction needed — §7.1) or (b) whether the CSD is wrong (rare; counterparty confirmation matches us). In case (a), correction transaction; finality applies. In case (b), reject the finality, request re-confirmation from the CSD.

Quarantine is NOT a silent ignore. The break exists, has an owner, has a deadline. After 2 business days unresolved → escalate per `L_18` aging.

### 7.5 Block-and-allocation chains

A trader executes a block of 1,000 XYZ at $50 to fill orders for 4 sub-funds (250 each). The block books at T against `w_block_holding`; allocations at T+0 to T+1 split it into per-subfund allocations.

**Ruling:** the block recognition transaction at T uses the standard PS/PSS pattern against `w_block_holding`:

```
TX_block:
  Move: from = PSS_receivable[w_block, GS, XYZ], to = w_block_holding, unit = XYZ, qty = 1000
  Move: from = w_block_holding, to = PS_payable[w_block, GS, USD], unit = USD, qty = 50000
  metadata: { allocation_pending: true, allocations_count: 4 }
```

Allocations fire as separate ECONOMIC_RECOGNITION (sub-class `ALLOCATION`) transactions:

```
TX_alloc_sub1:
  type: ECONOMIC_RECOGNITION_ALLOCATION
  refers_to_block: TX_block.tx_id
  Move: from = w_block_holding, to = w_subfund_1, unit = XYZ, qty = 250
  Move: from = w_subfund_1, to = PS_internal[w_subfund_1, w_block, USD], unit = USD, qty = 12500
  -- The PS_internal is an internal-broker wallet pair tracking the block-to-subfund cash allocation.
  --   It drains at the same time as TX_block's external PS_payable drains (at finality).
```

At T+2 finality, the external `sese.025` triggers a finality for `TX_block`. The framework simultaneously drains both the external PS_payable on the block AND the internal PS_internal on each subfund (one finality, multiple internal drains). This is a single atomic transaction per StatesHome C3.

**Cardinality:** for an N-allocation block, the finality transaction has `1 (external) + N (internal)` move pairs. Manageable for typical N ≤ 20.

If allocations happen *after* T+2 (rare but legal in some jurisdictions), the block settles to `w_block_holding`; the allocations later drain `w_block_holding` to subfunds without re-touching the external PS.

### 7.6 Same-day cancellations — pre-instruction

A trade is cancelled at T+0 14:00, before any `sese.023` instruction has been sent. **Ruling:** still emit the `CORRECTION` transaction. The original recognition stays in `L_13` (P4). Some firms drop pre-instruction cancellations as if the trade never happened — this proposal does not. The audit trail preserves both the recognition and the cancellation. The PS/PSS balances net to zero.

```
TX1_CANCEL:
  type: CORRECTION
  refers_to_tx: TX1.tx_id
  Move: from = w_us, to = PSS_receivable[w_us, GS, XYZ], unit = XYZ, qty = 100
  Move: from = PS_payable[w_us, GS, USD], to = w_us, unit = USD, qty = 5000
  metadata: { reason: SAME_DAY_CANCEL_PRE_INSTRUCTION }
```

The `MoveStream[TX1].settlement_status` becomes `CANCELLED` (terminal). The `L_15` obligation rows transition `Pending → Compensated` with `compensation_kind = CANCEL`.

### 7.7 Same-day cancellations — post-instruction

Cancellation after `sese.023` has been sent: more complex. We need a counter-instruction `sese.030` to recall the instruction. The framework:

1. Sends `sese.030` to the CSD.
2. Awaits CSD acknowledgement (`sese.031` or equivalent).
3. On ack: emit the same anti-move CORRECTION as §7.6.
4. On rejection (CSD already started processing): the trade is locked; cancellation impossible until either settle or fail. Operations escalates.

This is a multi-step saga (Temporal workflow); idempotent under replay.

### 7.8 Partial settlements with sequenced finality

CSD reports 60 settled, 40 pending. Then later (T+4) reports the remaining 40 settled.

```
TX_partial_1:
  type: SETTLEMENT_FINALITY
  tx_id: hash("FINAL", TX1.tx_id, sese.025_partial1_msg, 0)
  Move: from = w_GS_broker, to = PSS_receivable[w_us, GS, XYZ], unit = XYZ, qty = 60
  Move: from = PS_payable[w_us, GS, USD], to = w_GS_broker, unit = USD, qty = 3000
  -- After: PSS_receivable = -40; PS_payable = +2000; w_GS_broker has 60 XYZ short and 3000 USD.
  metadata: { qty_settled: 60, qty_remaining: 40 }
  L_13 status: INSTRUCTED → PARTIALLY_SETTLED
  L_15: leg_securities partial discharge; spawn child obligation for remainder

TX_partial_2: (T+4)
  type: SETTLEMENT_FINALITY
  tx_id: hash("FINAL", TX1.tx_id, sese.025_partial2_msg, 1)
  Move: from = w_GS_broker, to = PSS_receivable[w_us, GS, XYZ], unit = XYZ, qty = 40
  Move: from = PS_payable[w_us, GS, USD], to = w_GS_broker, unit = USD, qty = 2000
  L_13 status: PARTIALLY_SETTLED → SETTLED
```

**Conservation across the partial sequence:** PS_payable ends at 0 only when all 100 shares + $5,000 are accounted for. The `attempt_seq` field in the deterministic `tx_id` formula prevents collision between the two partial finality messages.

### 7.9 Buy-in execution (CSDR mandatory buy-in)

If unsettled past `intended_settle_date + buy_in_period` (4 bd liquid equities), CSDR triggers buy-in:

1. Buy-in agent or CCP executes a market-buy for the failed quantity at current market price `P_buy_in`.
2. New ECONOMIC_RECOGNITION transaction in our books for the buy-in trade. Standard PS/PSS pattern. This trade has its own T → T+2 cycle.
3. CORRECTION transaction reversing the original failed trade.
4. Cash settlement of the differential: if `P_buy_in > P_original`, GS pays us the difference; if `<`, we pay GS. As a separate cash-only transaction.
5. CSDR penalty obligations (accrued daily from `intended_settle_date + 1 bd` to `buy_in_settle_date`) discharge per the standard penalty workflow.

**Ledger end-state after buy-in:** `w_us.own(XYZ) = +100` (now via the buy-in trade); original `BUY-100-XYZ-T0` in `CANCELLED` status; CSDR penalties accrued and credited; full saga preserved in `L_13` audit trail.

---

## 8. CDM cross-walk — what we need vs. what CDM has

(Brief; matthias's Phase 1 §5 is the authoritative deep version. I align with it.)

| Ledger element | CDM 6.x status | Action |
|---|---|---|
| Recognition transaction at T | Direct via `BusinessEvent.execution` + `Trade` | Use directly. |
| Finality transaction at T+2⁺ | Direct via `BusinessEvent` with `Transfer.transferState = Settled` | Use directly. |
| Transaction-level lifecycle FSM | Partial — `TransferStatusEnum` lacks `Failed`, `PartiallySettled`, `Cancelled` | Upstream PR per matthias §5.3 Gap 6. Until shipped: Ledger-internal field. |
| `L_15.Obligation` | Missing in CDM | Ledger-internal. Upstream as Gap 10 (Obligation as first-class type) per matthias. |
| PS/PSS virtual wallets | Missing — no analogue | Ledger-internal. Pattern is the v10.3 §2.5 virtual-wallet idiom. |
| `L_18.BreakRegister` | Missing | Ledger-internal. Same. |
| CSDR penalty | Missing | Ledger-internal. Upstream as Gap 8 per matthias. |
| Buy-in event | Missing | Ledger-internal. Upstream as Gap 9 per matthias. |

The Settlement Team should adopt matthias's full §5 cross-walk verbatim with the four CDM PRs (Gap 6, 8, 9, 10) marked as upstream-track-with-firm-strategic-priority.

---

## 9. What auditors and operations actually demand

### 9.1 Audit assertions and how the framework discharges each

| Assertion (PCAOB / ISA 500) | How the framework discharges |
|---|---|
| **Existence** | `L_13.MoveStream` is an immutable hash-chained log. Every position has a determining transaction; every transaction is signed and hash-chained. |
| **Completeness** | The recognition transaction is committed atomically with `sese.023` outbound queue (idempotency via `tx_id`); FIX execution reports tie 1:1 to recognition transactions. |
| **Valuation** | Position is `w.own(u)`; price is `P_t(u)` from `L_9.MarketObservation` with full lineage. PnL is `Σ w_t(u) · P_t(u)`. Path-independent (P10). |
| **Rights and obligations** | Per-position lineage to the originating execution + counterparty LEI + master agreement reference (in `L_5` party master). |
| **Cut-off** | Trade timestamp at sub-second precision; UTC explicitly. Pre/post cut-off bookings are separable by `t_obs`. |
| **Presentation/disclosure** | Aggregate unsettled receivable/payable: a single `SUM` over PS/PSS wallets per `(ccy)`. Aging buckets: `expected_settlement_date - today`. |

### 9.2 Operations daily artifacts

1. The morning recon report (§3.4). Gate to "books are clean today."
2. Settle-today watchlist (`bucket = T+N_TODAY`). Status counts: EXECUTED vs INSTRUCTED. All must be INSTRUCTED before market open.
3. The overdue list. Each is a CSDR penalty / buy-in clock.
4. Break dashboard. `L_18.BreakRegister` filtered by ownership team, aging, exposure.
5. Cancel/correct queue. Approved CORRECTIONs awaiting commit.
6. CSDR penalty register. Open `CSDR_PENALTY` obligations and accumulating cash impact.
7. Quarantine queue. Trades in `wf-confirm-break` awaiting investigation.

These are queryable views over `L_13`, `L_15`, `L_18`, and the PS/PSS wallet rows. **No new storage. No new schema. Just SQL.**

---

## 10. Summary — what the Settlement Team should adopt

1. **State representation:** PS/PSS virtual wallet pair per `(real_wallet, cpty_lei, ccy_or_ISIN)`, payable/receivable split, holding the open-window contra. **Reject:** seventh GPM coordinate (sbl); obligation-as-unit (cartan, halmos, matthias, minsky); aggregate per-CSD inflight wallet (jane_street, isda variant); pending_in/pending_out as PositionState fields (testcommittee, feynman). **Accept:** mainstream — PS/PSS virtual wallets + `L_15` obligation row + transaction-level FSM + state-only lifecycle transactions.

2. **Move shape:** at T, two moves (security leg + cash leg) into PS/PSS contras + atomic `L_15` register + status `EXECUTED`. At T+2, two moves draining PS/PSS into broker-virtual + atomic `L_15` discharge + status `SETTLED`. Conservation `Σ_w Δw(u) = 0` per unit at every step. The §2 worked example is the binding canonical block.

3. **Reconciliation identity:** `nostro_external = own + Σ PS_payable - Σ PS_receivable - inflight_out + inflight_in` per `(real_wallet, ccy)`. Constant-time scan, not a join. Lead-lag is by design; break is the residual after stripping the expected lead-lag. Three classifications: CLEAN / EXPECTED / BREAK.

4. **BreakRegister discipline:** per `L_18` FSM, aged in business days, four-eyes on `Closed-Waived`. CSDR penalty as `L_15` obligation kind, pure-function discharge.

5. **Idempotency:** deterministic `tx_id = hash(...)` over message-receipt-time inputs including `EndToEndId`. Replay produces no duplicates. Out-of-order ingest commutes per formalis DS5. No write amplification.

6. **Decimal discipline:** `D_2/D_4/D_8/D_18` per type; `ROUND_HALF_EVEN`; per-currency tolerances versioned in `L_7^P`; no floats; explicit FX conversion only.

7. **Operational corner cases:** corrections via new CORRECTION transactions with anti-moves; manual override via four-eyes CORRECTION; golden-source disagreement → quarantine + `wf-confirm-break`; block/allocation via internal-PS chain; partial settlement via sequenced finality; CSDR buy-in as new ECONOMIC_RECOGNITION + CORRECTION + cash-differential cycle.

8. **CDM:** adopt matthias §5 cross-walk verbatim. Four upstream PRs (Gap 6, 8, 9, 10) on the strategic track.

9. **No new StatesHome map.** No new GPM coordinate. No new conservation carve-out. Two new wallet *classes* (KYC metadata in `WalletRegistry`). One existing `L_15` obligation kind. One new transaction-type marker `SETTLEMENT_FINALITY` (sub-class of existing `SETTLEMENT`).

This is the smallest delta to v10.3 that closes the deferred-settlement gap operationally and audit-cleanly. Every alternative considered (Phase 1 proposals named) trades operational hygiene for theoretical elegance, and finops vetoes that trade.

— *finops-architect, Phase 2 Settlement Team contribution. Independent assessment, with explicit acceptance/rejection of named Phase 1 positions.*
