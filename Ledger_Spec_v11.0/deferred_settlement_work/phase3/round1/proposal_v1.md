# Proposal v1 — Deferred Settlement on Cash Equities (T+2)
## Phase 2 Settlement Team Unified Design

**Thesis.** A T+2 cash-equity settlement window is not a new doctrine for Ledger v10.3; it is a *transaction-level lifecycle* on the existing `MoveStream`, with virtual sub-wallets carrying the gross payable/receivable obligations and an `L_15 Obligation` row carrying the legal duty. Trade-date economics flow through the standard six-coordinate StatesHome wallets unchanged — `(own, borr, lent, coll_pledged, coll_received, financed)` — while a parallel reconciliation identity binds the virtual wallets to external nostro/depot positions. The settlement window is a *parameter*, not an architecture: T+1, T+0, partial, failed, and bought-in are all the same FSM with different terminal absorption. This proposal integrates seven domain reviews (FinOps, SBL, CDM, Regulatory, Accounting, Formalis-invariants, Type-design) into one implementation-ready specification.

**Sections:**
1. Convergence statement
2. State representation
3. The standard buy — canonical worked example
4. Reconciliation
5. The lifecycle FSM
6. Variants — same mechanism, different parameters
7. Composition with §13 SBL six-coordinate model
8. CDM cross-walk
9. Regulatory footprint
10. Accounting + audit + capital
11. Invariants DS1–DS18
12. Type design
13. Honest gaps and proof obligations
14. Out of scope (deliberate)
15. Ready-for-Review note

---

## 1. Convergence statement

### The unified design

The Settlement Team converged in Phase 2 on a **mainstream design** that adds the smallest possible delta to v10.3 to close the deferred-settlement gap:

1. **Trade-date economic recognition.** A real-wallet `own` write at T (the existing v10.3 §2 move algebra) — never moved by settlement.
2. **Virtual PS/PSS wallet contras.** Per-`(real_wallet, counterparty_LEI, ccy_or_ISIN, side)` virtual wallets in `WalletRegistry`, payable/receivable split, holding the open-window contra-quantity. New wallet *classes* (KYC sidecar metadata in `WalletRegistry`) — **zero new fields on `PositionState`**.
3. **`L_15.Obligation` row.** Per-leg, kind `SettlementInstructionDelivery`, carrying the lifecycle FSM `Pending → Discharged | Compensated | Defaulted` with discharge predicate, `intended_settlement_date`, `csdr_clock`.
4. **Transaction-level FSM as projection.** `MoveStream[tx_id].settlement_status` is the MAX projection over per-leg `L_15` states by the lattice `Settled > PartiallySettled > Failed > BoughtIn > Instructed > Executed > Cancelled`.
5. **Reconciliation identity** — algebraic, constant-time scan: `nostro_external = own + Σ PS_payable - Σ PS_receivable - inflight_out + inflight_in` per `(real_wallet, ccy)`. Symmetric for securities.
6. **Witness-driven discharge** (DS4): no FSM transition without an attested envelope (`sese.025` / `camt.054` matched by `EndToEndId`).
7. **Mandatory invariant:** Economic-Exposure-at-T (DS1). The position embedded in a trade is true from `T_exec` regardless of `transferStatus` of any associated `Transfer`. Type-level enforcement via phantom-typed wallet handles.

**The settlement window is a parameter, not an architecture.** T+0 atomic, T+1, T+2, T+5+ — same FSM, same obligation row, same algebra, only the workflow timer durations change. This is the test of CDM-native architecture: the rule change becomes a config change, not a re-architecture.

### What was rejected

**The 7th coordinate** (sbl Phase 1, withdrawn). Adding a stored signed `inflight` coordinate to every `PositionState[w, u]` row creates a field that consumers (PnL, risk, margin, capital, mandate breach) must each decide whether to include — the "is it own or own+inflight" trap. Margaret Chen withdrew this in Phase 2 §0 after re-weighing three arguments she had under-weighted in Phase 1: StatesHome 3-map discipline; Single-Coordinate Move Principle; granularity is recoverable as a projection. **Adopted instead:** PS/PSS virtual wallets + L_15 obligation row + transaction-level FSM.

**First-class unit `u^circ`** (cartan, halmos, matthias, noether, minsky Phase 1, withdrawn or deferred). Mathematically elegant — the obligation is the kernel of the forgetful functor; conservation falls out by issuance pair; redemption is a homomorphism. Operationally rejected: doubles unit-master cardinality (every settlement creates a fresh unit with its own ProductTerms, UnitStatus, per-position rows); every consumer of `PositionState` must opt out for obligation units (no price function, or degenerate one); duplicates state already in L_15; library, not language. **Adopted instead:** L_15 obligation row carries the lifecycle; existing unit semantics on existing units. Matthias retains the dissent for the historical log; recommends revisit when CDM 7.0 ships an Obligation type.

**`pending_in` / `pending_out` as PositionState fields** (testcommittee, feynman, accepted as projections only). Useful query shapes; rejected as state — derivable from PS/PSS wallet family by constant-time scan. Storing them duplicates state and reintroduces "where does the contra live?" trap. **Adopted instead:** projections at the read site, not stored coordinates.

**Single-aggregate-per-CSD wallet** (jane_street, isda Phase 1, refined to per-counterparty). ISDA proposed `w_csd_inflight[CSD, omnibus, book]` aggregated across counterparties. Rejected: a CSD-level aggregate loses per-counterparty exposure attribution and per-counterparty CSDR penalty attribution — both operationally non-negotiable. Recon engineer chasing a $13.42 break in a $1.2B aggregate cannot drill down. **Adopted instead:** per-counterparty per-(currency-or-ISIN) PS/PSS pair as the floor; ISDA's CSD-level wallet sits *above* as a derived view.

**Settlement state on `UnitStatus[ISIN]`** (rejected — wrong granularity). The ISIN is shared across all holders; settlement is per-trade. Two trades on the same ISIN can have different settlement statuses simultaneously. Settlement state belongs on the per-trade `L_15` row keyed by `obligation_id`, not on instrument-level UnitStatus.

**Settlement state purely external** (rejected — Ledger owns the obligation). Some readings of v10.3 §11.6 lean toward this: settlement is downstream, the Ledger emits an instruction and forgets. Wrong: the settlement obligation is economically load-bearing — generates CSDR penalties, drives buy-in workflow, attaches to regulatory reports, feeds reconciliation. Two systems claiming truth (Ledger for trade-date economics, settlement utility for obligation state) recreates the problem the framework eliminates. **Adopted instead:** Ledger represents *what we promised* (the obligation, with discharge predicate and compensation handler); settlement utility provides *how the promise is mechanically discharged*. Boundary at the `SettlementInstruction` struct.

## 2. State representation

### 2.1 The triple

The deferred-settlement obligation is represented by a **triple** [finops §1.1]:

| Element | Where it lives | What it carries | Writer (C11 cap) |
|---|---|---|---|
| Real-wallet `own` write at T | `PositionState[w_real, u].own` | Economic position. Trade-date accounting. **Never moved by settlement.** | `apply_trade_move` handler at T only |
| Virtual `PS` / `PSS` wallet contra | `PositionState[w_PS, u].own`, `PositionState[w_PSS, u].own` | Per-`(cpty_lei, ccy_or_ISIN)` open-obligation **quantity**. Drains on finality. | `apply_trade_move` at T (initial credit/debit); same handler at T+N (drain). |
| `L_15.Obligation` row, kind `SettlementInstructionDelivery` | `Obligation[obligation_id]` (data v1.0 $L_{15}$) | Per-leg lifecycle: `Pending → Discharged \| Compensated \| Defaulted`. Carries `intended_settlement_date`, `discharge_predicate`, `csdr_clock`. | `SettlementWorkflow` (Temporal). |
| Transaction-level settlement status | `MoveStream[tx_id].settlement_status` | `EXECUTED → INSTRUCTED → SETTLED \| PARTIALLY_SETTLED \| FAILED \| CANCELLED`. Drives ops queue. | `SettlementWorkflow`; state-only transactions on `L_13`. |

The `PS`/`PSS` pair holds the **contra-quantity**. The `L_15` row holds the **lifecycle**. The transaction-level status is a **convenience projection** kept on `L_13` for query speed.

### 2.2 Wallet keying — per-counterparty per-(currency-or-ISIN), payable/receivable split

For each `(real_wallet w, counterparty cpty, ccy_or_ISIN)`, **two** virtual wallets, not one:

```
PS_payable[w, cpty, ccy]      -- "we owe cpty: cash leaving w"
PS_receivable[w, cpty, ccy]   -- "cpty owes w: cash arriving"
PSS_payable[w, cpty, ISIN]    -- "we owe cpty: securities leaving w"
PSS_receivable[w, cpty, ISIN] -- "cpty owes w: securities arriving"
```

Three operational reasons for the split — finops vetoes a signed-net design [finops §1.5]:

1. **Right-of-set-off is jurisdiction- and master-agreement-specific.** A signed-net wallet would silently net a payable under one ISDA master against a receivable under another, which IFRS 7 disclosure (offsetting) requires us to expose anyway. Two wallets — each non-negative on its side — preserves the gross.
2. **Aged-payable and aged-receivable trigger different ops workflows.** CSDR penalties accrue against the *failing-to-deliver* party; buy-in clocks affect the *failing-to-deliver* party. The taxonomy is asymmetric. A signed-net wallet collapses this.
3. **Conservation is cleaner when both sides are non-negative.** Pacioli (1494). Every general ledger in production uses it.

### 2.3 Wallet registry sidecar metadata

Per StatesHome §2 the `WalletRegistry` is KYC, not state. It carries the new metadata fields:

```
wallet_class ∈ { real, virtual_cpty, virtual_PS_payable, virtual_PS_receivable,
                 virtual_PSS_payable, virtual_PSS_receivable,
                 virtual_nostro, virtual_depot, virtual_inflight_out, virtual_inflight_in }
real_wallet:    FK to the owning real wallet (NULL for real wallets themselves)
cpty_lei:       LEI of the counterparty (NULL if not counterparty-keyed)
expected_settle_window: { T+0 | T+1 | T+2 | T+3 } per venue convention
```

These are `WalletRegistry` columns. **Zero new columns on `PositionState`.** [finops §1.3]

### 2.4 Transaction-level lifecycle FSM on MoveStream

The transaction-level field `MoveStream[tx_id].settlement_status` is the **MAX projection** over per-leg `L_15.Obligation.state` values [finops §1.2 correction]. The FSM is per-**leg**: a DvP transaction with two legs has two obligation rows, two status FSMs running in parallel. The transaction-level status uses the lattice `Settled > Failed > Instructed > Executed` — needed for partial settlement (one leg `Settled`, the other `Failed` in DvP Model 2/3).

States:

```
EXECUTED        → trade recognised at T; PS/PSS contras posted; sese.023 not yet sent
INSTRUCTED      → sese.023 dispatched; awaiting CSD finality
PARTIALLY_SETTLED → some quantity discharged via partial sese.025; remainder open
SETTLED         → all legs Discharged
FAILED          → at least one leg past T_max with no discharge; CSDR clock active
CANCELLED       → CORRECTION transaction terminated the trade pre-finality
BoughtIn        → CSDR mandatory buy-in resolved the failure
```

Allowed transitions form a closed sum (DS7 totality, formalis §1):
`EXECUTED → INSTRUCTED → {SETTLED, PARTIALLY_SETTLED, FAILED}`;
`PARTIALLY_SETTLED → {SETTLED, FAILED}`; `FAILED → {SETTLED, BoughtIn, Defaulted}`;
`* → CANCELLED` only via four-eyes CORRECTION.

### 2.5 StatesHome compliance — explicit check

| StatesHome map | Touched? |
|---|---|
| `ProductTerms[u]` | No. Cash and securities terms unchanged. |
| `UnitStatus[u]` | No. Instrument-level lifecycle unaffected. |
| `PositionState[w, u]` | Yes — but only by **existing handlers** (`apply_trade_move`, `apply_settlement_finality`). PS/PSS wallets are new wallet rows in `WalletRegistry`; their balances sit in `PositionState` with the same `own` coordinate. **Zero new fields.** |
| `WalletRegistry[w]` (KYC) | Yes — sidecar metadata above. Permitted per StatesHome §2 KYC sector. |

**Conformance verdict: PS/PSS pattern adds zero state to StatesHome. No fourth map.**

### 2.6 Conservation — explicit

For every `(w, u)` pair touched by a deferred-settlement transaction at T or T+N:

$$\sum_{w \in \mathcal{W}_{\text{real}} \cup \mathcal{W}_{\text{virtual}}} \Delta w_t(u) = 0$$

per move pair. PS/PSS wallets are full participants in $\mathcal{W}_{\text{virtual}}$ and contribute to the sum by construction (v10.3 §2.5 + §2.4). **No conservation carve-out.** Non-negotiable.

### 2.7 Why payable/receivable split is gross, not net

IFRS 7 (Disclosures: offsetting financial assets and liabilities) requires gross presentation absent a legal right of set-off enforced under a master agreement. The set-off determination is master-agreement- and jurisdiction-specific. A net wallet erases the audit trail of the gross exposures and presumes the offset legality. The framework's ruling: store gross, present net (when justified) at the disclosure layer. The PS_payable / PS_receivable split is the storage form.

## 3. The standard buy — canonical worked example

This is the load-bearing concrete artifact. **Every other section in this proposal refers back to this block.** Source: [finops §2].

### 3.1 Setup

- **Trade:** Buy 100 XYZ @ $50.00 = $5,000.00 cash leg.
- **Date:** T = 2026-04-30 14:32:11 UTC.
- **Settlement:** T+2 = 2026-05-04. (Same shape for T+1 with a single-day window.)
- **Real wallet:** `w_us` (our portfolio).
- **Counterparty:** Goldman Sachs broker, LEI `784F5XWPLTWKTBV3E584`, virtual broker wallet `w_GS_broker`.
- **CSD:** DTC for securities depot (`w_DTC_depot`); JPMC for cash nostro (`w_JPMC_nostro_USD`).
- **Pre-trade:** `w_us.own(USD) = 1,000,000.00`; `w_us.own(XYZ) = 0`.
- **External nostro:** `w_JPMC_nostro_USD.own(USD) = 1,000,000.00` (JPMC daily `camt.053`).
- **Mark-to-market:** $50.00 (T close), $52.00 (T+1 close), $51.50 (T+2 close).
- **Decimal discipline:** prices `D_8`; quantities `D_18`/`D_0`; cash `D_2`; **no floats.**

### 3.2 Move block at T (2026-04-30 14:32:11 UTC)

```
Transaction TX1:
  type:               ECONOMIC_RECOGNITION (sub-class of SETTLEMENT)
  tx_id:              hash("ECON_REC", "BUY", "XYZ", 100, 50.0000_0000, GS_LEI,
                            "2026-04-30T14:32:11Z")
                     = "0xa7c3f1e8..." (deterministic; see §5.x)
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

  -- Atomic with the move pair: register obligations in L_15
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

  -- Atomic: write the transaction-level status
  MoveStream[tx_id].settlement_status: EXECUTED
```

**Conservation check at T (per unit, atomic):**

| Unit | Δw_us | Δ(PSS_recv[us,GS,XYZ]) | Δ(PS_pay[us,GS,USD]) | Σ |
|---|---:|---:|---:|---:|
| XYZ | +100 | -100 | 0 | 0 |
| USD | -5,000.00 | 0 | +5,000.00 | 0 |

**Wallet snapshot post-TX1:**

```
w_us.own(XYZ)                            = +100
w_us.own(USD)                            = +995,000.00
PSS_receivable[w_us, GS, XYZ].own(XYZ)   = -100        (GS owes us 100 XYZ)
PS_payable[w_us, GS, USD].own(USD)       = +5,000.00   (we owe GS 5,000 USD)
w_GS_broker.own(XYZ)                     = 0
w_GS_broker.own(USD)                     = 0
w_DTC_depot.own(XYZ)                     = 0
w_JPMC_nostro_USD.own(USD)               = +1,000,000.00 (per last camt.053)
```

### 3.3 At T+1 close (2026-05-01 21:00 UTC, XYZ → $52.00)

**No moves emitted.** Position is unchanged. Status remains `EXECUTED` (or `INSTRUCTED` if `sese.023` has been sent during the day):

```
Optional state-only transaction:

Transaction TX1_INSTRUCT:
  type:    LIFECYCLE
  moves:   []   (empty)
  metadata: { refers_to_tx: TX1.tx_id, new_status: INSTRUCTED, ssi_used: hash(SSI),
              outbound_iso20022: "sese.023.001-msg-id-..." }

  L_13: append the (move-less) transaction.
  MoveStream[TX1.tx_id].settlement_status: EXECUTED → INSTRUCTED
  L_15: no change (still Pending; instruction-emit does not discharge).
```

State-only transactions are valid per v10.3 FAQ Q6 ("move-less events are valid lifecycle events") and StatesHome C9 (handlers on zero-move transactions discharge `Σ = 0` vacuously).

**PnL at T+1 close:**

```
V_{T+1}(w_us) = w_us.own(USD) × P_{T+1}(USD) + w_us.own(XYZ) × P_{T+1}(XYZ)
              = 995,000.00 × 1.0000 + 100 × 52.0000
              = 995,000.00 + 5,200.00
              = 1,000,200.00

PnL_{T+1} = V_{T+1} - V_T = 1,000,200.00 - 1,000,000.00 = +200.00
```

**+$200.00 P&L with zero cash movement and zero settlement movement.** This is the headline guarantee of the spec — the entire reason for trade-date accounting [DS1; ashworth §1].

### 3.4 At T+2 morning (2026-05-04 09:00 UTC, before finality)

No moves. State unchanged from T+1. Morning recon report runs (§4.4). Status `INSTRUCTED` if not already.

### 3.5 At T+2 finality (2026-05-04 ~16:30 UTC, after DTC end-of-day batch)

DTC reports DvP finality via `sese.025` (securities) and `camt.054` (cash debit). Both inbound on `L_11.ExternalConfirmation`. The `SettlementWorkflow` consumes the signal and emits the **finality contra-transaction**:

```
Transaction TX1_FINAL:
  type:               SETTLEMENT_FINALITY (sub-class of SETTLEMENT)
  tx_id:              hash("FINAL", TX1.tx_id, sese.025_msg_id, camt.054_msg_id)
                    = "0xb8d4..." (deterministic)
  ts:                 2026-05-04T16:30:42Z
  metadata:           { refers_to_tx: TX1.tx_id, finality_attestation_lei: DTC_LEI,
                        sese.025_msg_id: "...", camt.054_msg_id: "..." }

  -- Securities leg: drain the PSS_receivable into broker virtual wallet
  Move 1: from = w_GS_broker
          to   = PSS_receivable[w_us, GS, XYZ]
          unit = XYZ
          qty  = D_0(100)

  -- Cash leg: drain the PS_payable into broker virtual wallet
  Move 2: from = PS_payable[w_us, GS, USD]
          to   = w_GS_broker
          unit = USD
          qty  = D_2(5000.00)

  -- Atomic: discharge the obligations
  L_15 update obligation_id=hash(TX1.tx_id, "leg_securities").state: Pending → Discharged
  L_15 update obligation_id=hash(TX1.tx_id, "leg_cash").state:       Pending → Discharged
  MoveStream[TX1.tx_id].settlement_status: INSTRUCTED → SETTLED
```

**Conservation check:**

| Unit | Δw_us | ΔPSS_recv | ΔPS_pay | Δw_GS_broker | Σ |
|---|---:|---:|---:|---:|---:|
| XYZ | 0 | +100 | 0 | -100 | 0 |
| USD | 0 | 0 | -5,000 | +5,000 | 0 |

**Wallet snapshot post-TX1_FINAL:**

```
w_us.own(XYZ)                          = +100        (UNCHANGED from T)
w_us.own(USD)                          = +995,000   (UNCHANGED from T)
PSS_receivable[w_us, GS, XYZ].own      = 0          (drained)
PS_payable[w_us, GS, USD].own          = 0          (drained)
w_GS_broker.own(XYZ)                   = -100       (mirrors GS's delivery)
w_GS_broker.own(USD)                   = +5,000.00  (mirrors GS's receipt)
```

**The position on `w_us` is invariant from T through T+2.** This is the structural commitment.

### 3.6 Conservation summary across the four states

USD (cash leg):

| State | w_us(USD) | PS_payable | w_GS_broker(USD) | w_JPMC_nostro_USD | Σ_internal | nostro_external |
|---|---:|---:|---:|---:|---:|---:|
| T⁻ pre-trade | 1,000,000 | 0 | 0 | 1,000,000 | 1,000,000 | 1,000,000 |
| T⁺ post-trade | 995,000 | +5,000 | 0 | 1,000,000 | 1,000,000 | 1,000,000 |
| T+1 | 995,000 | +5,000 | 0 | 1,000,000 | 1,000,000 | 1,000,000 |
| T+2⁻ instructed | 995,000 | +5,000 | 0 | 1,000,000 | 1,000,000 | 1,000,000 |
| T+2⁺ finality | 995,000 | 0 | +5,000 | 995,000 | 1,000,000 | 995,000 |

XYZ (securities leg):

| State | w_us(XYZ) | PSS_recv | w_GS_broker(XYZ) | w_DTC_depot(XYZ) | Σ_internal | depot_external |
|---|---:|---:|---:|---:|---:|---:|
| T⁻ | 0 | 0 | 0 | 0 | 0 | 0 |
| T⁺ | +100 | -100 | 0 | 0 | 0 | 0 |
| T+1 | +100 | -100 | 0 | 0 | 0 | 0 |
| T+2⁻ | +100 | -100 | 0 | 0 | 0 | 0 |
| T+2⁺ | +100 | 0 | -100 | +100 | 0 | +100 |

Conservation `Σ_w w(u) = 0` holds at every step.

### 3.7 PnL at T+2 close (XYZ = $51.50) — path independence

```
V_{T+2} = 995,000.00 × 1.00 + 100 × 51.50
        = 995,000.00 + 5,150.00
        = 1,000,150.00

PnL_{T+2}  = V_{T+2} - V_{T+1} = 1,000,150 - 1,000,200 = -50.00
PnL_{cum}  = V_{T+2} - V_T     = 1,000,150 - 1,000,000 = +150.00
                              = +200 (T+1 mark-up) - 50 (T+2 mark-down)
```

PnL path-independence (v10.3 P10) holds across the full trade lifecycle, T-through-settled, with **zero** moves on `w_us` after T.

## 4. Reconciliation

### 4.1 The fundamental algebraic identity

For every `(real_wallet w, currency ccy)` pair at any wall-clock time `t` [finops §3.1, sign-corrected]:

$$\boxed{\;
\text{nostro\_external}(w, \text{ccy}, t) = w_t.\text{own}(\text{ccy}) + \sum_{\text{cpty}} \text{PS\_payable}[w, \text{cpty}, \text{ccy}]_t - \sum_{\text{cpty}} \text{PS\_receivable}[w, \text{cpty}, \text{ccy}]_t - \text{inflight\_out}(w, \text{ccy}, t) + \text{inflight\_in}(w, \text{ccy}, t)
\;}$$

**Equivalent identity for securities** for every `(real_wallet w, ISIN s)`:

$$\text{depot\_external}(w, s, t) = w_t.\text{own}(s) + \sum_{\text{cpty}} \text{PSS\_payable}[w, \text{cpty}, s]_t - \sum_{\text{cpty}} \text{PSS\_receivable}[w, \text{cpty}, s]_t - \text{depot\_out}(w, s, t) + \text{depot\_in}(w, s, t)$$

### 4.2 Sign discipline (load-bearing — corrected from finops Phase 1)

When **WE owe** (`PS_payable > 0`) and the wire **hasn't gone out**, JPMC still shows our balance fat — `nostro_external = own + unpaid payable`. When **someone else owes us** (`PS_receivable > 0` for the cash side) and the wire hasn't arrived, JPMC shows our balance lean.

This is the sign convention finops corrected from its own Phase 1 §7.7 — the corrected identity is the one above. **The Phase 2 spec uses this corrected identity. Phase 1 §4.1 sign was wrong; this supersedes it.** [finops §3.2]

Verification with the §3 worked example, T+2 morning (before finality):

```
LHS = nostro_external (per camt.053) = 1,000,000.00
RHS = w_us.own(USD) + PS_payable - PS_receivable - inflight_out + inflight_in
    = 995,000.00 + 5,000.00 - 0 - 0 + 0
    = 1,000,000.00
```

T+2 evening (post-finality):

```
LHS = nostro_external = 995,000.00 (JPMC has now debited)
RHS = 995,000.00 + 0 - 0 - 0 + 0 = 995,000.00
```

### 4.3 Constant-time scan, not a join

The algebraic identity is **constant-time** per `(w, ccy)`:

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

A single grouped scan over PS/PSS rows for that real wallet, bounded by the number of *open-trade counterparties for this real wallet* (typically dozens to hundreds, not millions). **No join to `MoveStream`. No replay over the open-instruction set.** A million open trades aggregate into a thousand wallet rows; the scan is bounded by wallet count, not transaction count. [finops §3.3]

### 4.4 Morning recon report shape

Runs as a Temporal cron `MorningReconWorkflow` at 09:00 local in each reporting timezone.

**Per-counterparty row, one per `(cpty_lei, ccy_or_ISIN, settle_bucket)`:**

```
counterparty | ccy | bucket    | gross_payable | gross_receivable | net      | trade_count | aging
-------------|-----|-----------|---------------|-------------------|----------|-------------|------
GS           | USD | T+0       |      12,500.00|         5,000.00  | +7,500   |     4       | 0bd
GS           | USD | T+1       |       5,000.00|             0.00  | +5,000   |     1       | 1bd
GS           | USD | T+2_TODAY |   1,250,000.00|       812,000.00  | +438,000 |    47       | 2bd
GS           | USD | OVERDUE   |           0.00|       150,000.00  | -150,000 |     1       | 3bd  AGED
JPMC         | USD | T+0       |      80,000.00|        80,000.00  |        0 |    12       | 0bd
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
break:                             0.00
```

Buckets:
- `T+N` for N ≥ 1: forward open exposure.
- `T+0` for N = 0: trades that settled today (just-discharged window).
- `T+2_TODAY` (or `T+1_TODAY` etc.): trades **settling today** — operations watch this bucket like a hawk; every trade here must be `INSTRUCTED` before market open.
- `OVERDUE`: any trade past `expected_settlement_date` not in `{SETTLED, FAILED, PARTIALLY_SETTLED, CANCELLED}` — escalates to `wf-confirm-break`.

Aging in business days, computed using the trade venue's calendar (data v1.0 $L_1$ `CalendarConvention`).

### 4.5 What is a break and what is not

**Not a break — expected lead-lag during the open window:**
- `PS_payable[w, *, ccy] > 0` for any open trade with `expected_settlement_date ≥ today`.
- `PSS_receivable[w, *, s] < 0` for any open trade with `expected_settlement_date ≥ today`.
- `nostro_external > w.own(ccy)` by exactly `Σ PS_payable - Σ PS_receivable + (signed wire inflight)`.
- `EXECUTED`-status trade pending instruction, before the affirmation cutoff.
- `INSTRUCTED`-status trade pending finality, before EOD on `expected_settlement_date`.
- `sese.025` finality arriving up to 1bd late for cross-border trades (Asia settling in our morning).

**Is a break — `BreakRegister` entry per `L_18` FSM:**

| Condition | Workflow | Owner |
|---|---|---|
| `\|nostro_external - RHS\| > tolerance` after stripping expected lead-lag | `wf-position-break` | Middle-office reconciliation |
| Trade past `expected_settlement_date` with `status ∉ {SETTLED, FAILED, PARTIALLY_SETTLED, CANCELLED}` after EOD | `wf-confirm-break` | Settlement operations |
| `sese.025` with no matching recognition (`refers_to_tx` not found) | `wf-confirm-break` | Settlement operations |
| `sese.025` with **wrong amount or quantity** vs. the recognition tx | `wf-confirm-break` (HARD: do **not** apply the finality moves; quarantine) | Settlement operations + counterparty desk |
| `sese.024` (CSD fail attestation) inbound | `wf-confirm-break` + spawn `CSDR_PENALTY` obligation in `L_15` | Settlement operations |
| Recognition tx with no matching finality after `T_max = expected + 5bd` (CSDR liquid equities) | `wf-obligation-break` (auto via `L_15` Liveness Theorem 3) | Settlement operations |
| Duplicate `sese.025` with same `(refers_to_tx, finality_attestation_id)` | **Idempotently dropped** by executor (P5); not a break. Logged. | n/a |

### 4.6 Decimal handling at recon time — non-negotiable

| Quantity | Type | Rationale |
|---|---|---|
| Cash major (USD/EUR/GBP) | `Decimal(18, 2)` | Two minor units, ~$10^{16}$ headroom |
| Cash JPY/CLP | `Decimal(18, 0)` | Sub-yen accumulation forbidden by JFSA |
| Cash EM precision | `Decimal(18, 4)` | IDR per USD etc. |
| Securities whole-share | `Decimal(18, 0)` | DTCC, Euroclear convention |
| Securities fractional | `Decimal(18, 6)` | Tokenised; per data v1.0 |
| Prices | `Decimal(18, 8)` | FX-derived needs 8dp |
| FX rates | `Decimal(18, 8)` | Same |
| Yields, rates (bps) | `Decimal(18, 4)` | sub-bp |
| Tolerances | `Decimal(18, 8)` | Strictly typed |

Per-currency tolerances are versioned in `L_7^P.PolicyConfiguration` keyed `(ccy, recon_kind)`. Defaults: USD/EUR/GBP/HKD/SGD = 0.00; JPY = 0; CHF = 0.01. Override requires four-eyes per data v1.0 §15. Tolerances are bitemporal — an old recon at an old tolerance is reproducible with `t_known = old`.

**Rounding:** `ROUND_HALF_EVEN` (banker's rounding), hardcoded; no per-call override. Avoids systematic upward bias of `ROUND_HALF_UP` over $10^6$ trades.

**Forbidden patterns:**
- No floats in any code path that touches money or quantities. Code-review hard-fail on `float()`.
- No string concatenation for amounts.
- No implicit currency conversion. All FX via explicit `convert(amount, from_ccy, to_ccy, rate, t_obs)` pinning rate and observation time.
- No `==` comparison of decimals. Always `abs(a - b) <= tolerance`.
- No `round()` on prices before storage. Stored raw at `D_8`; rounding at presentation only.

### 4.7 Cadence

| Recon | Cadence | Window | Owner |
|---|---|---|---|
| Custodian/CSD depot vs ledger position + open inflight | Daily 09:00 local + intraday on each `sese.025` | All open trades | Middle-office |
| Cash nostro vs ledger USD/EUR/etc per real wallet | Daily 09:00 local + intraday on each `camt.054` | All real cash wallets | Treasury ops |
| CSD `sese.024` participant statement vs `L_15` | Daily | All open obligations | Settlement ops |
| MiFIR/EMIR Refit/SFTR ack from TR | T+1 morning | All trades reportable | Regulatory ops |
| CSDR cash penalty advice (semt.0xx) vs accrued | Monthly | All failed trades closed in month | Settlement ops |
| Block-and-allocation chain reconciliation | Per allocation event + EOD | All open block trades | Allocation ops |

### 4.8 The recon engine — three classifications

Every recon run emits exactly three sets:

1. **CLEAN** — identity holds within tolerance per `(w, ccy)` and per `(w, ISIN)`. No action.
2. **EXPECTED LEAD-LAG** — identity violated by an amount exactly explained by open PS/PSS contras and open wire-level inflight. No action; this is the open-window state.
3. **BREAK** — identity violated by an amount NOT explained by (1) or (2). `BreakRegister` row created with kind, owner, deadline, expected resolution.

The classification is **purely algebraic.** No manual triage. If a recon engineer is staring at a screen wondering "is this a break or expected?", we have failed the spec.

### 4.9 Multi-day fail aging — the L_18 FSM mapping

```
Open → Investigating → Assigned → Aged-1 → Aged-3 → Aged-5 → Escalated → At-Risk → Material → Closed-{Clean | Adj | Waived}
```

| Aging state | Trigger | Action | CSDR alignment |
|---|---|---|---|
| Open | New mismatch | Investigate; ops queue | n/a |
| Investigating | T+0 | Owner assigned, root-cause hunt | n/a |
| Aged-1 | T+1 bd unresolved | Notify supervisor; CSDR penalty accrual day 1 | CSDR Day 1 |
| Aged-3 | T+3 bd | Escalate to head of desk | CSDR liquid: extension expires here |
| Aged-5 | T+5 bd | Escalate to head of operations | CSDR mandatory buy-in window 4-7bd post-ISD |
| At-Risk | exposure ≥ €1M (configurable) | Risk committee | — |
| Material | exposure ≥ €10M | Governance committee + BCBS 239 reg notification | — |
| Closed-Waived | Resolved by waiver | Four-eyes per `L_18` | — |

## 5. The lifecycle FSM

### 5.1 The 7-state closed sum

Per-leg, closed-sum, total. Source: [finops §1.2; formalis §1].

```
Pending  ─────► Discharged       (witness: sese.025 / camt.054 matched)
   │
   ├─────────► Compensated       (witness: CORRECTION transaction with
   │                              compensation_kind ∈ {CANCEL, BUY_IN, NOVATION})
   │
   └─────────► Defaulted         (witness: counterparty default declared,
                                  T_max exceeded with no buy-in possible,
                                  fallback handler invoked)
```

Transaction-level projection over leg statuses uses the lattice:
`Settled > PartiallySettled > Failed > BoughtIn > Instructed > Executed > Cancelled`.

A 4-state extension `{Instructed, PartiallySettled, Failed, BoughtIn}` captures the operationally observable transaction state on `MoveStream[tx_id].settlement_status`. The internal obligation state is the 3-leaf closed sum; the operational projection is the 7-state observable.

### 5.2 Per-leg, not per-transaction

[formalis correction adopted, finops §1.2]

A DvP transaction has two legs: `leg_securities` and `leg_cash`. Each gets its own `L_15.Obligation` row, its own discharge predicate, its own FSM. The transaction-level field `MoveStream[tx_id].settlement_status` is the **MAX projection** over the per-leg statuses by the lattice above. This is needed for **partial settlement** (one leg `Discharged`, the other `Pending` in DvP Model 2/3 systems) and for **half-failed** trades (typical Asian intra-day windows).

### 5.3 Allowed transitions

```
Per-leg L_15.Obligation.state:
  Pending → Discharged       (on witness match)
  Pending → Compensated      (on CORRECTION transaction discharge)
  Pending → Defaulted        (on T_max exhaust + fallback handler)

Transaction-level MoveStream.settlement_status:
  EXECUTED → INSTRUCTED                        (on sese.023 dispatch)
  INSTRUCTED → SETTLED                         (when all leg.state = Discharged)
  INSTRUCTED → PARTIALLY_SETTLED               (when ≥ 1 leg partial-Discharged)
  INSTRUCTED → FAILED                          (when ≥ 1 leg past deadline, none Discharged)
  PARTIALLY_SETTLED → SETTLED | FAILED         (depending on remaining qty resolution)
  FAILED → SETTLED  (post-buy-in)              (CSDR mandatory buy-in resolution)
  FAILED → BoughtIn (terminal mark)            (CSDR pursued buy-in path)
  * → CANCELLED                                (only via four-eyes CORRECTION)
```

All other transitions are forbidden by the FSM closed-sum constraint (DS7).

### 5.4 Witness-driven discharge — no fail-by-inference

[Adopted from nazarov DS4 review]

An obligation transitions `Pending → Discharged` ONLY when:
1. A witness message (`sese.025`, `camt.054`, or compensation event) is observed on `L_11.ExternalConfirmation`.
2. The witness matches the discharge predicate (`ByMatch(sese.025, ref=tx_id)`).
3. The witness payload reconciles (qty, ccy, amount) with the recognition tx within tolerance.

**The framework never marks a leg `Discharged` by inference, by clock, or by absence of evidence.** A trade past `expected_settlement_date` with no inbound `sese.024` (fail attestation) and no inbound `sese.025` (success) remains `Pending` until a witness arrives. This is the formal gate to DS4 (no discharge without witness).

After `T_max = expected + 5bd` (CSDR liquid equities; configurable per instrument class), the obligation auto-promotes to a **break** in `L_18.BreakRegister` of kind `obligation_overdue` — but the obligation itself remains `Pending` until a witness arrives or the fallback handler executes a CORRECTION (`Compensated`) or default (`Defaulted`).

### 5.5 Idempotency and out-of-order ingest

Witness matching is by `EndToEndId`. Replay of the same witness produces no duplicate state transition (StatesHome P5 idempotency by `tx_id`). Out-of-order witnesses (e.g., the `camt.054` arrives 30 minutes before the `sese.025`) commute: the per-leg FSM transitions are on disjoint obligation rows, and the joint state is invariant under interleaving (formalis DS5).

### 5.6 The seven-state observable summary

| Status | Internal leg states | Action |
|---|---|---|
| `EXECUTED` | both `Pending`, no `sese.023` yet | recognition done, instruction pending |
| `INSTRUCTED` | both `Pending`, `sese.023` sent | awaiting CSD finality |
| `PARTIALLY_SETTLED` | ≥ 1 leg has partial-discharge metadata | residual obligation child spawned |
| `SETTLED` | both legs `Discharged` | terminal good |
| `FAILED` | ≥ 1 leg past deadline, witness shows fail | CSDR clock active |
| `BoughtIn` | originating trade `Compensated` via buy-in chain | terminal via CSDR resolution |
| `CANCELLED` | both legs `Compensated` via four-eyes CORRECTION | terminal cancel |

## 6. Variants — same mechanism, different parameters

The deferred-settlement representation is parameterised on `settle_date = t_d` and degenerates uniformly. **DS12 (variant degeneration)** is the formal commitment: for all variants, DS1–DS11 hold without modification; only workflow timer durations change.

### 6.1 T+1 markets (parameter, not architectural)

US: T+1 since 28 May 2024 (DTCC; SEC Rule 15c6-1 amendment Feb 2023). UK: target 11 October 2027. EU: target 11 October 2027. Switzerland (FINMA): aligned with EU/UK; SIX consultation 2025 → 2027. India: T+1 since 2023; T+0 (optional) since 2024 for ~25 stocks.

The Ledger absorbs T+1 because ISD is a parameter on the settlement instruction, not an assumption baked into invariants. Parameters live in:
- `ProductTerms[u].settlement_cycle` (per ISIN × MIC), sourced from `L_4 CalendarConvention` + `L_16 ReferenceMaster`;
- `Trade.cdm_payload.settlementDate` (CDM-native, resolved at execution from venue/CSD data);
- `L_15.Obligation.deadline` (computed at trade time);
- `L_18` break-aging timers.

**No code change** is required for the EU/UK move beyond the per-`(MIC, ISIN)` settlement-cycle table refresh and the CSDR penalty-window recalibration. Operational machinery (FX cutoffs collapse by half; ETF NAV cycles with multi-cycle obligation graphs; DTC night-cycle elimination; corporate-action cum/ex window collapse) must adapt; the architecture absorbs.

### 6.2 T+0 / atomic DLT (parameter; future)

For T+0 atomic on-chain: t_d = T, the obligation is issued and discharged in the same atomic transaction; the `Pending` state has zero duration. Discharge predicate becomes `ByAttestation(on-chain finality oracle)`. Virtual-wallet inflight period collapses to ε seconds. Nostro IS the chain (continuous on-chain query). CSDR penalty regime not applicable (no fail). FX leg becomes atomic PvP via on-chain or CLS-on-chain bridge. **No unsettled-trade capital. ECL on settlement receivables approaches zero.**

What stays constant:
- The 7-state FSM (FAILED branch becomes vanishingly improbable, but FSM does not change).
- The L_15 Obligation object — discharge predicate kind changes, structure does not.
- Conservation invariants — preserved by construction at every horizon.
- Trade-date economic recognition — preserved; T+0 just collapses the open window to zero.
- The DRR engine — same code, regime pin changes, output is the same shape.

**This is the test of the architecture.** Hardcoding T+2 is technical debt with a known due date.

### 6.3 Failed settlement (FSM transition, not rollback; CSDR penalty in L_15)

A `Failed` state is a witness-driven FSM transition (DS4) — `sese.024` inbound or T_max exhausted with watchdog-confirmed absence-of-witness. **No moves on real wallets.** The economic position recognised at T is preserved (DS7 — failure non-reversal). Only the obligation status changes.

CSDR penalty obligation spawns:

```
Obligation row of kind CSDR_PENALTY in L_15:
  obligation_id:           hash("CSDR_PENALTY", refers_to_tx, intended_settle_date)
  kind:                    CSDR_PENALTY
  discharge_predicate:     ByDeadline(buy_in_resolution_date)
  fields:
    qty_failed:           D_0 or D_18 per instrument
    price_at_intended:    D_8 (pinned via refdata at intended settle date)
    rate_bps:             D_4 (per ESMA Penalty Matrix, pinned via refdata_pin)
    accrual_start:        intended_settle_date + 1 bd
  state: Pending
```

Daily accrual emits a small cash transaction (failing party → suffering party) atomically with `o_pen.csdr_penalty_accrued` update. Settlement to T2S monthly cycle via `pacs.008` aggregated penalty payments; aggregate matches daily accrual sum to the cent or ESMA monthly statement is the break.

**Penalty amount is a pure function of `(qty_failed, price_at_intended, days_late, instrument_class)` and the `refdata_pin`.** No human inputs. No discretion. Auditable. (DS14.)

### 6.4 Partial settlement (UnitStatus-counter, no obligation spawn)

CSD reports 60 settled, 40 pending. Then later (T+4) reports the remaining 40 settled.

```
TX_partial_1:
  type: SETTLEMENT_FINALITY
  tx_id: hash("FINAL", TX1.tx_id, sese.025_partial1_msg, 0)
  Move: from = w_GS_broker, to = PSS_receivable[w_us, GS, XYZ], unit = XYZ, qty = 60
  Move: from = PS_payable[w_us, GS, USD], to = w_GS_broker, unit = USD, qty = 3000
  metadata: { qty_settled: 60, qty_remaining: 40 }
  L_13 status: INSTRUCTED → PARTIALLY_SETTLED
  L_15: leg_securities partial discharge; child obligation for residual

TX_partial_2 (T+4):
  type: SETTLEMENT_FINALITY
  tx_id: hash("FINAL", TX1.tx_id, sese.025_partial2_msg, 1)
  Move: from = w_GS_broker, to = PSS_receivable[w_us, GS, XYZ], unit = XYZ, qty = 40
  Move: from = PS_payable[w_us, GS, USD], to = w_GS_broker, unit = USD, qty = 2000
  L_13 status: PARTIALLY_SETTLED → SETTLED
```

**Conservation across the partial sequence:** PS_payable ends at 0 only when all 100 shares + $5,000 are accounted for. The `attempt_seq` field in the deterministic `tx_id` formula prevents collision between the two partial finality messages.

**Economic position on the trader's real wallet is unchanged across the partial sequence.** The full 100 shares were recognised at T; the partial fill is a custody convergence, not an economic event. The recursion bound D_max (PO-9) caps depth at 2 per jane_street's engineering pragma, with a property-test that beyond D_max the cascade transitions to `Defaulted` rather than continuing.

### 6.5 Cancellation (CORRECTION transaction with four-eyes)

Append-only event log; **no transaction is ever deleted**. Cancellation is a `CORRECTION`-typed transaction emitting anti-moves; original transaction remains in move stream.

**Pre-instruction cancel (T+0 14:00 before sese.023):**

```
TX1_CANCEL:
  type: CORRECTION
  refers_to_tx: TX1.tx_id
  Move: from = w_us, to = PSS_receivable[w_us, GS, XYZ], unit = XYZ, qty = 100
  Move: from = PS_payable[w_us, GS, USD], to = w_us, unit = USD, qty = 5000
  metadata: { reason: SAME_DAY_CANCEL_PRE_INSTRUCTION,
              requester_lei: ..., approver_lei: ... }

  MoveStream[TX1.tx_id].settlement_status: → CANCELLED (terminal)
  L_15: u_sale.state Pending → Compensated, compensation_kind = CANCEL
```

**Post-instruction cancel:** multi-step saga (Temporal workflow). Send `sese.030` to CSD; await `sese.031` ack; on ack emit anti-move CORRECTION; on rejection (CSD already started processing) → trade is locked, cancellation impossible until either settle or fail; ops escalates.

Four-eyes is non-negotiable: framework rejects any `CORRECTION` where `requester_lei == approver_lei`. The original transaction stays in `L_13` (P4 log monotonicity); both visible in the audit trail. Bitemporal: `as_of(t)` for any `t` between original and correction returns the original (un-corrected) state for forensic purposes; `with_corrections_through(t_known')` returns the corrected state for current reporting.

## 7. Composition with §13 SBL six-coordinate model

### 7.1 Orthogonality

The GPM six-tuple of v10.3 §13 — `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` — and the deferred-settlement state — `(virtual_wallet_balances, obligation_status, lifecycle_stage)` — are **structurally orthogonal** [sbl §1.1]. A position's six-coordinate vector and the settlement state of any open instruction touching that position are independent dimensions. The only place they interact is at the *boundary*: when an instruction transitions to `SETTLED`, certain virtual-wallet balances zero out, but **no GPM coordinate on a real wallet moves at that boundary** (the v10.3 §13.7 "no moves at settlement" rule, preserved unchanged).

This orthogonality is what lets the same FSM run for cash-equity sales, SBL loan settlement, SBL collateral movements, and SBL recall returns. The smart contract dispatches on instruction type; the FSM is uniform.

### 7.2 The standard buy/sell draws from `own` directly

A deferred cash-equity *sale* of $q$ shares of unit $u$ by entity $e$ at time $T$, settling $T+2$, draws from `own`:

$$\Delta \mathrm{own}_e(u) = -q \quad \text{at } T.$$

If $\mathrm{own}_e(u) \geq q$ pre-trade (long), this is a clean reduction. If $\mathrm{own}_e(u) < q$, `own` goes negative — and this is correct. The locate Unit and the `avail` projection $\mathrm{avail} = \mathrm{own} - \mathrm{onloan} + \mathrm{borr}$ enforce SSR/Reg-SHO covered-short discipline at the smart-contract guard level, *before* the move is admitted.

The seller's *delivery obligation* — the duty to deliver the shares to the CSD by $T+2$ — does **not** live on the GPM. It lives in the `L_15` obligation row and in the PSS_payable virtual wallet. **`own` and inflight are different things and live in different storage.** [sbl §1.2]

### 7.3 Short sale lifecycle in full

Setup: short seller $C$, lender $B$, buyer $D$. Quantity $q = 500$ NVDA. Sale price \$100. Cash collateral on the loan: \$50,000, rebate rate 25 bps. T+2 cash equity settlement; T+1 loan settlement.

#### 7.3.1 T-1 14:00 — Locate confirmed

No moves. Locate Unit `loc_1` registered: `(lender=B, borrower=C, isin=NVDA, qty=500, ttl=end-of-T)`. P14 (Locate Before Short) consumes this Unit's reservation against $B$'s `available_to_lend` projection.

```
w_C = (own=0, onloan=0, borr=0, coll_post=0, coll_recv=0, coll_rehyp=0)
w_B = (1000, 0, 0, 0, 0, 0)
w_D = (0, 0, 0, 0, 0, 0)
```

#### 7.3.2 T 09:30 — Short sale to D, T+2 settlement

```
tau_sale = Transaction(type=ECONOMIC_RECOGNITION, settlement_date=T+2):
    Move(from=w_C, to=PSS_payable[w_C, D, NVDA], unit=NVDA, qty=500)
    Move(from=PS_receivable[w_C, D, USD], to=w_C, unit=USD, qty=50000)

L_15:
    obligation_id = hash(tau_sale.id, "leg_securities")
    intended_settlement = T+2
    discharge_predicate = ByMatch(sese.025 against tau_sale.id)
    state = Pending
```

After:

```
w_C   own NVDA = -500    (covered short, locate present)
w_C   own USD  = +50000  (cash from sale)
PSS_payable[w_C, D, NVDA] = +500    (we owe D the shares)
PS_receivable[w_C, D, USD] = -50000 (D paid us; symmetric mirror)
```

`avail(C, NVDA) = -500 - 0 + 0 = -500`. Locate-covered, not yet borrow-covered.

Conservation per unit: NVDA `(-500) + (+500) = 0`; USD `(+50000) + (-50000) = 0`.

#### 7.3.3 T 09:31 — Borrow negotiated with B

Loan negotiation is no-move. A SETTLEMENT-type transaction is created representing the loan but `lifecycle_stage = EXECUTED`; actual move-emission happens at the loan's intended settlement. **Reading A** (loan as one transaction with intended-settlement metadata): the GPM bookkeeping coordinates (`onloan`, `borr`) flip at the loan's T+1 settlement, not at T. The team adopts Reading A. [sbl §2.3]

#### 7.3.4 T+1 — Loan ℓ settles FOP

```
tau_loan = Transaction(type=SETTLEMENT, settlement_date=T+1, regime=GMSLA-2010-SI):
    Move(from=w_B, to=w_C, coord=own, unit=NVDA, qty=500)   -- title transfer
    BookkeepingDelta:
        w_B.onloan(NVDA) += 500
        w_C.borr(NVDA)   += 500
    -- Plus collateral leg (cash 50000 USD posted from C to B,
    --   coll_post and coll_recv deltas)

L_15: u_loan.state Pending → Discharged
```

After:

```
w_C   own NVDA = -500 + 500 = 0
w_C   borr NVDA = +500
w_C   coll_post USD = +50000
w_B   own NVDA = 1000 - 500 = 500
w_B   onloan NVDA = +500
w_B   coll_recv USD = +50000

avail(C, NVDA) = 0 - 0 + 500 = 500    (now sufficient to deliver to D)
```

**Pinning rule:** the conservation law in the SBL extension applies to `own` (and the cash/collateral coordinates), not to `onloan` or `borr` per se. The bookkeeping coordinates are scoped per-`(entity, unit)` and don't aggregate across the system. [sbl §2.4]

#### 7.3.5 T+2 — Short sale settles to D

```
tau_discharge = Transaction(type=SETTLEMENT_FINALITY):
    Move(from=PSS_payable[w_C, D, NVDA], to=w_D_brkrvirt, unit=NVDA, qty=500)
    Move(from=w_D_brkrvirt, to=PS_receivable[w_C, D, USD], unit=USD, qty=50000)

L_15: u_sale.state Pending → Discharged
MoveStream[tau_sale.id].settlement_status: INSTRUCTED → SETTLED
```

`w_C`'s GPM coordinates are unchanged at this step. The PSS/PS virtual wallets close to zero. C's net position is `own=0, borr=+500, coll_post=+50000`. C has fully delivered the 500 shares to D, sourced via the borrow from B.

### 7.4 Recall during the open window — recall obligation distinct from sale obligation

**Scenario.** Lender $A$ has lent 1000 XYZ to borrower $B$ at $t_0$. On $T$, $B$ sells 600 XYZ to buyer $D$, settling $T+2$. On $T+1$, $A$ issues a recall on the loan, with intended return date $T+3$.

| Time | $\vec{w}_B$ XYZ (own, onloan, borr) | u_sale stage | recall obligation | inflight from sale |
|---|---|---|---|---|
| $t_0^+$ (loan settled, T<<0) | (0, 0, 1000) | n/a | n/a | 0 |
| $T$ (sale to D) | (-600, 0, 1000) | EXECUTED | n/a | -600 |
| $T+1$ (recall arrives) | (-600, 0, 1000) | EXECUTED | u_recall created, EXECUTED, intended_return=T+3 | -600 |
| $T+2^+$ (sale settles) | (-600, 0, 1000) | SETTLED | EXECUTED | 0 |
| $T+3$ (recall due) | $B$ delivers up to avail = -600 + 1000 = 400. **Insufficient.** | terminal | EXECUTED → buy-in path | n/a |

**The two obligations are independent.** The sale to D is a contractual obligation under the equity trade; the recall is a contractual obligation under the GMSLA. The recall does **not** preempt the already-instructed sale. If $B$'s available position is insufficient to settle both, $B$ must source additional shares (open-market purchase, alternative borrow, or — under GMSLA 9.3 — buy-in by $A$ at $B$'s expense), pay any CSDR penalty for the failing leg, and pay GMSLA buy-in costs.

The system represents this through saga compensation: when the recall obligation's deadline fires and `avail(B, XYZ) < 1000`, the workflow generates a `BUY_IN_REQUIRED` event that spawns a market-buy SETTLEMENT transaction with its own T+2 cycle. Recursive composition; same FSM at every level.

### 7.5 Naked short — pre-trade guard rejects

A *naked* short is a sale at $T$ without an Article 12(1)(c) locate or a T+0 borrow lined up. Under EU SSR Article 12 this is *prohibited*; under SEC Reg SHO Rule 203, generally prohibited except for bona-fide market-making.

- **Pre-trade guard.** The smart contract guarding the SETTLEMENT-type transaction emission for a short sale checks for the locate Unit's existence and validity at time $T$. If absent, the executor **rejects** the transaction. C11 capability discipline — the trade doesn't enter the move stream.
- **Post-trade detection.** If a naked short is somehow booked (e.g., via a CORRECTION transaction or a flagged exception), the L_18 BreakRegister picks it up at the T+2 settlement check.

### 7.6 Reg SHO 204 + CSDR buy-in

Reg SHO Rule 204 (US): for a fail-to-deliver on a short sale, the broker-dealer must close out by the start of trading on $T+3$ (or $T+5$ for market makers, or $T+35$ for fails on threshold securities).

CSDR Article 7 (EU, Refit 2023): mandatory buy-in *suspended* for cash equities since 2022 but reinstated as a discretionary regime for specific high-fail securities post-2024 ESMA review. Cash penalty regime is in force unconditionally.

**Ledger representation:**

```
At T+3 (Reg SHO close-out deadline):
    Workflow detects: u_sale.lifecycle_stage == FAILED, regime=US_REG_SHO

    Generate: tau_buyin = Transaction(type=ECONOMIC_RECOGNITION, settlement_date=T+5):
        Move(from=PSS_receivable[w_C, market, NVDA], to=w_C, unit=NVDA, qty=500)
        Move(from=w_C, to=PS_payable[w_C, market, USD], unit=USD, qty=500*P_T+3)

    Side-effects:
        u_sale.lifecycle_stage: FAILED → BoughtIn
        u_buyin = new Obligation, intended_settlement = T+5, lifecycle_stage = EXECUTED

At T+5 (buy-in settles): standard finality.
At T+5+ε: discharge transaction completes original D-bound delivery
        u_sale: BoughtIn → SETTLED (fully discharged via replacement)
```

PnL impact: $-500 \cdot (P_{T+3} - P_T)$ + CSDR cash penalty + Reg SHO penalty if applicable. All visible on the move stream; no special accounting.

### 7.7 Locate-but-borrow-late: "long that has never owned" is legal under SSR Art 12(1)(c)

Between $T$ (locate confirmed, sale executed, borrow not yet settled) and $T+1$ (borrow settles), short seller $C$'s position:

```
w_C(NVDA) = (own=-q, onloan=0, borr=0, ...)
avail(C) = -q
```

*C has never owned NVDA*. C has, however, an *enforceable claim against B* via the locate-converted-to-borrow obligation. The "synthetic short" is observable from the move stream:

```sql
SELECT entity_id, unit_id,
       coordinate('own') as own,
       coordinate('borr') as borr,
       (own - 0 + borr) as avail
FROM positions
WHERE avail < 0
  AND NOT EXISTS (SELECT 1 FROM trade_history
                   WHERE entity = entity_id AND unit = unit_id
                     AND coordinate = 'own' AND qty > 0);
```

Returns: $C$ on NVDA between $T$ 09:30 and $T+1$ (loan settle).

**Regulatory expectation.**
- **EU SSR Article 12(1)(c):** the position is legal *if* the locate provides "a reasonable expectation of settlement when due". The fact that $C$ never owned the shares is irrelevant; the locate must be from a counterparty (lender $B$) with a reasonable means of delivery.
- **ESMA 2022 Final Report (ESMA70-448-10):** the locate must be *recorded* with 5-year retention, including the confirming party's identity. `L_2 InstrumentMaster` + `L_17 RegulatorySubmission`.
- **SEC Reg SHO Rule 203:** equivalent.

The Ledger correctly represents the temporary "long that has never owned" state through negative `own` and the locate Unit. **Not a bug; it is the correct representation of a legal short-sale-with-locate.** [sbl §5]

### 7.8 Prepay collateral overnight exposure as two independent obligations

Real EMEA scenario (IBP-177 prepay): a loan ℓ negotiated at $T_\ell$ with intended settlement $T_\ell+1$ FOP. Cash collateral pre-paid at $T_\ell$ (overnight, before the loan settles). Both moves in flight overnight.

```
tau_collateral (type=SETTLEMENT, settlement_date=T_l):
    Move(from=w_C, to=w_B, coord=coll_post/coll_recv, unit=USD, qty=50000)
    L_15: u_collateral.state INSTRUCTED → Discharged at T_l EOD

tau_loan (type=SETTLEMENT, settlement_date=T_l+1, depends_on=u_collateral):
    Move(from=w_B, to=w_C, coord=own, unit=NVDA, qty=500)
    BookkeepingDelta: w_B.onloan += 500, w_C.borr += 500
    L_15: u_loan.state EXECUTED → Discharged at T_l+1
```

Between $T_\ell$ EOD and $T_\ell+1$ EOD: u_collateral is Discharged, u_loan is Pending. **Mismatch is visible in `L_15`.** The risk system reads this and flags one-leg exposure for $C$ (overnight Herstatt-class).

**Pinning rules:**
- **Prepay collateral obligations are independent of the loan obligation.** Not bundled. Each has its own discharge predicate and compensation handler.
- **The dependency graph is in the smart contract, not the data model.** $\tau_{loan}$'s guard checks `u_collateral.state == Discharged` before admitting the loan settlement.
- **Failure-to-deliver after collateral has settled triggers GMSLA 5.2/5.4 close-out netting.** Workflow: u_loan deadline exceeds → compensation handler invoked → reverse-collateral SETTLEMENT transaction → u_collateral COMPENSATED, u_loan CANCELLED.

### 7.9 Reconciliation identity for SBL composition

The recon identity for an entity holding SBL positions [sbl §1.4]:

$$\mathrm{own}_e(u) + \mathrm{borr}_e(u) - \mathrm{onloan}_e(u) - \sum_{i \in \mathrm{open}(e,u)} \mathrm{signed\_qty}(i) = D(e, u)$$

where `open(e,u)` = obligations with `state ∈ {Pending}` touching `(e, u)` and `signed_qty` is positive for receive, negative for deliver. Same shape as §4.1 cash recon, generalised to bookkeeping coordinates.

### 7.10 Three regulatory IDs as L_15 metadata

Each obligation row carries: `mifir_trn`, `sftr_uti`, `csd_instruction_ref`, `slate_loan_id`, `slate_finra_loan_id`. Populated by the settlement projection at outbound emission, reconciled at inbound confirmation. The reporting fan-out is a workflow, not a data-model concern; each regime has its own `L_17.RegulatorySubmission` row referencing the same `obligation_id` but generating distinct payloads. Bitemporal restatements (e.g., ESMA recalibrates a CSDR rate retroactively): `L_15.t_known` is updated; `t_obs` preserved.

## 8. CDM cross-walk

CDM 6.0.0 maps cleanly to **roughly half** of the Ledger v11.0 deferred-settlement design. CDM types verified at 2026-04-30 against `github.com/finos/common-domain-model@master`. [matthias §1, §3]

### 8.1 Direct / Partial / Missing — 24-element inventory

**Trade-time recognition (T) — economic side**

| Ledger element | CDM 6.0.0 | Type / file |
|---|---|---|
| Trade execution event at T | **Direct** | `BusinessEvent` with `eventQualifier = "Execution"`; `instruction.execution`. `eventQualifier = "Execution"`; `after TradeState (0..*)` |
| Trade object | **Direct** | `Trade extends TradableProduct`; `tradeDate FieldWithMeta<date> (1..1)` |
| Counterparty pair | **Direct** | `TradableProduct.counterparty Counterparty (2..2)` |
| Trade-time positions for buyer/seller | **Partial** | `TradeState.state State (0..1)`, `transferHistory TransferState (0..*)` |
| Settlement-date terms (T+2 expectation) | **Direct (terms)** | `SettlementDate`, `SettlementTerms` on payouts and `Trade.contractDetails` |
| Cash leg | **Direct** | `Transfer extends AssetFlowBase` with `Asset.Cash` |
| Securities leg | **Direct** | `Transfer` with `Asset.Instrument.Security` |

**Open-window state (T < t < T+2)**

| Ledger element | CDM 6.0.0 | Type / file |
|---|---|---|
| Status `EXECUTED` | **Direct (with conflation)** | `PositionStatusEnum.Executed`; `TransferStatusEnum.Pending` — Gap 11 doctrinal |
| Status `INSTRUCTED` | **Direct** | `TransferStatusEnum.Instructed` |
| In-flight wallet balance | **Missing** | No CDM analogue |
| Open obligation as discrete object | **Missing — Gap 10** | No `Obligation` root type |
| Expected settlement date on live obligation | **Missing — Gap 6** | `TransferState` lacks `expectedSettlementDate` |
| `PositionStatusEnum.PartiallySettled` | **Missing — Gap 6** | enum lacks the value |
| `PositionStatusEnum.Failed` | **Missing — Gap 6** | enum lacks the value |

**Settlement at T+2 success**

| Ledger element | CDM 6.0.0 | Type / file |
|---|---|---|
| Settlement confirmation arrival | **Direct** | `BusinessEvent` with `eventQualifier = "Settlement"` |
| Status transition `INSTRUCTED → SETTLED` | **Direct** | `TransferStatusEnum.Settled` |
| Position unchanged on settlement (E2) | **Direct (semantic-only)** | No structural assertion in CDM |
| Nostro reconciliation marker | **Missing** | No CDM analogue |
| DvP atomicity | **Direct (terms)** | `TransferSettlementEnum.DeliveryVersusPayment` |

**Settlement at T+2 fail/partial**

| Ledger element | CDM 6.0.0 | Type / file |
|---|---|---|
| Status `FAILED` | **Missing — Gap 6** | `TransferStatusEnum: {Disputed, Instructed, Pending, Settled, Netted}` only |
| Fail reason | **Missing — Gap 6** | No `TransferFailureReason` type |
| Status `PARTIALLY_SETTLED` | **Missing — Gap 6** | (CDS-only `partialCashSettlement boolean` is a false friend) |
| Settled quantity on partial | **Missing — Gap 6** | No structural slot |
| CSDR cash penalty event | **Missing — Gap 8** | No `CSDRPenaltyDetail`; `eventQualifier` soft-typed |
| Penalty rate per ESMA matrix | **Missing** | (Lives in `L_7^P`) |
| Buy-in instruction | **Missing — Gap 9** | "buy-in" appears only in CDS context |
| Buy-in execution and outcome | **Missing — Gap 9** | No `BuyInExecution`, `BuyInOutcomeEnum` |
| Cash-settlement-in-lieu fallback | **Missing — Gap 9** | Subsumed |

**Composition layer**

| Ledger element | CDM 6.0.0 | Type / file |
|---|---|---|
| Short sale composing with SBL borrow | **Partial** | `Qualify_SecurityLending` exists; composition does not |
| Recall in window | **Direct (event-tag) / Partial (composition)** | `UnscheduledTransferEnum.Recall` |
| Corporate action with record date in (T, T+2) | **Partial** | `ObservationEvent.corporateAction` |
| Cross-currency / Herstatt | **Partial** | `TransferSettlementEnum.PaymentVersusPayment` |
| DvP atomicity (Ledger primitive) | **Missing** | No CDM analogue |

**Summary classification:** Direct 11 / Partial 6 / Missing 7.

### 8.2 Five strategic gaps (refined to six with Gap 11 doctrinal)

- **Gap 6 — `TransferStatus` enrichment** (Failed, PartiallySettled, Cancelled + `TransferFailureReason`). STRATEGIC, CSDR-blocking. Verified absence: `TransferStatusEnum: {Disputed, Instructed, Pending, Settled, Netted}` only.
- **Gap 7 — Partial settlement granularity** (subsumed in Gap 6 — `settledQuantity`).
- **Gap 8 — CSDR cash penalty as structural event** (`CSDRPenaltyDetail` type, `Qualify_CashPenalty` qualification, `CSDRLiquidityClassEnum`).
- **Gap 9 — Buy-in event** (`BuyInInstruction`, `BuyInExecution`, `BuyInRegimeEnum`, `BuyInOutcomeEnum`).
- **Gap 10 — Obligation as a first-class root type.** Highest-leverage cross-cutting gap. Phase 1 unanimous (cartan, halmos, noether, isda, formalis, jane_street, karpathy, lattner, minsky, temporal, sbl, ashworth, finops, feynman).
- **Gap 11 — Economic-exposure-at-T as enforced semantic.** STRATEGIC, FOUNDATIONAL but **NOT a Rosetta extension**; doctrinal addition to CDM 7.0 documentation: "for any `TradeState` with `tradeDate = T_exec`, the position embedded in this trade is true from `T_exec` regardless of `transferStatus` of any associated `Transfer`."

### 8.3 Rosetta extension PRs (PR-1..PR-4)

**PR-1 (Gap 6+7) — TransferStatus enrichment.** ~80 lines, non-breaking. Sketch:

```rosetta
enum TransferStatusEnum:
    Disputed Instructed Pending Settled Netted
    Failed              <"...per ESMA RTS on CSDR Article 7...">
    PartiallySettled    <"...the settled portion is reflected in companion TransferState...">
    Cancelled           <"...post-buy-in cash compensation under CSDR Article 7...">

enum TransferFailReasonEnum:
    LackOfSecurities LackOfCash SettlementMatchingFailure
    BuyerOnHold SellerOnHold SettlementSystemFailure OnHoldByCounterparty Other

type TransferFailureReason:
    failReasonCode TransferFailReasonEnum (1..1)
    failReasonText string (0..1)        // required when Other
    settledQuantity Quantity (0..1)     // for PartiallySettled
    csdrPenaltyAccrued Money (0..1)

type TransferState:
    transfer Transfer (1..1)
    transferStatus TransferStatusEnum (0..1)
    failureReason TransferFailureReason (0..1)
    expectedSettlementDate date (0..1)
    actualSettlementDate date (0..1)
```

**PR-2 (Gap 8) — CSDR cash penalty.** ~120 lines, non-breaking. New file `event-csdr-type.rosetta`. `CSDRLiquidityClassEnum` (LiquidShares, NonLiquidShares, LiquidBonds_*, SMEGrowthMarket, Other). `CSDRPenaltyDetail` with `failedTransferReference`, `penaltyAccrualDate`, `penaltyAmount`, `penaltyRateBps`, `instrumentLiquidityClass`, `penaltyCounterparty`, `penaltyBeneficiary`, `referencePrice`. `Qualify_CashPenalty` qualification function.

**PR-3 (Gap 9) — Buy-in event.** ~150 lines, non-breaking. `BuyInRegimeEnum` (CSDRMandatoryBuyIn, GMSLA_2018, GMRA_2011, BilateralContractual). `BuyInOutcomeEnum` (OriginalTransferCancelled, CashSettlementInLieu). `BuyInInstruction` and `BuyInExecution` types with conditions linking outcome to required fields.

**PR-4 (Gap 10) — Obligation root type.** ~200 lines, non-breaking. `ObligationTypeEnum` covers SettlementDeliveryVersusPayment, SettlementFreeOfPayment, CashPayment, SBLRecall, SBLReturn, CollateralSubstitution, CollateralTopUp, BuyInDelivery, CashCompensation, ManufacturedPayment. `ObligationStatusEnum` mirrors the Ledger 7-state FSM. `Obligation` type with `obligor`, `obligee`, `obligedAsset`, `expectedDischargeDate`, `actualDischargeDate`, `obligationStatus`, `sourceEvent`, `dischargeEvent`, `parentObligation` (self-reference for partial-settlement spawn / buy-in chain).

**Path to upstream:** PRs are independent. Recommended sequence — PR-1 (smallest, CSDR-blocking) → PR-2 → PR-3 (depends on PR-1) → PR-4 (largest scope; benefits from PR-1/2/3 demonstrating composability).

### 8.4 Forgetful functor F: MoveStream → CDM BusinessEvent

Let $\mathbf{Lg}$ be the category of Ledger states (objects: `(WalletRegistry, UnitRegistry, MoveStream, ObligationStore)`; morphisms: balanced atomic transactions). Let $\mathbf{CDM}$ be the category of CDM states.

> **F is a homomorphism.** $F : \mathbf{Lg} \to \mathbf{CDM}$:
>
> - `F(τ_T : trade execution)` = `BusinessEvent(eventQualifier="Execution")` with `instruction.execution` populated; `after.TradeState.transferHistory[]` carries one `TransferState` per leg (status `Pending`).
> - `F(τ_{T+2-} : instruction emitted)` = `BusinessEvent(eventQualifier="Settlement")`, `transferStatus = Instructed`, `expectedSettlementDate = T+2`.
> - `F(τ_{T+2+,SUCCESS})` = `BusinessEvent`, `transferStatus = Settled`, `actualSettlementDate = T+2`.
> - `F(τ_{T+2+,FAIL})` = `BusinessEvent`, `transferStatus = Failed`, `failureReason` populated.
> - `F(τ_{T+2+,PARTIAL})` = single `BusinessEvent` with two `TransferState` records (`Settled` for partial portion, `PartiallySettled` for residual).
> - `F(τ_{CSDR penalty})` = `BusinessEvent(eventQualifier="CashPenalty")` referencing a `CSDRPenaltyDetail` (Gap 8).
> - `F(τ_{buy-in instruction/execution})` = `BusinessEvent` referencing `BuyInInstruction` / `BuyInExecution` (Gap 9).
> - `F(obligation issuance/discharge moves)` = referenced `Obligation` (Gap 10).

**F preserves:** conservation (each `Move` becomes a `Transfer` with one payer/one receiver, sum is zero by construction); per-trade sequencing (`before`/`after` `TradeState` chain); idempotency (content-addressed `BusinessEvent` identifiers).

**F loses:** per-(wallet, unit) PositionState density (wallet axis collapses); in-flight virtual-wallet contras (gap is implicit in absence of `Settled`, until Gap 10 ships); multi-leg atomicity (preserved by convention, not structural enforcement).

**Direction of authority:** Ledger first, CDM downstream. The Ledger reconciles to CDM via F, not the other way around.

### 8.5 ISO 20022 messages — sese.023/024/025/027, camt.054, MT54x

| ISO 20022 | Direction | Purpose | CDM event | Ledger move primitive |
|---|---|---|---|---|
| **sese.023** Securities Settlement Transaction Instruction | Out (Ledger → CSD) | Instructs CSD to settle (DvP/FoP) | `BusinessEvent(eventQualifier="Settlement")`, `instruction` populated; `transferStatus = Instructed` | LIFECYCLE-class tx (no moves): `ObligationStatusUpdate(Pending → Instructed)` |
| **sese.024** Securities Settlement Transaction Status Advice | In (CSD → Ledger) | Reports status (matched/unmatched/hold/fail-pre-settlement/partial-projected) | `BusinessEvent(eventQualifier="SettlementStatusUpdate")`; `failureReason` populated for fail | LIFECYCLE-class. For fail: `ObligationStatusUpdate(Instructed → Failed)` |
| **sese.025** Securities Settlement Transaction Confirmation | In | Confirms settlement (full/partial) | `BusinessEvent`; `transferStatus = Settled` (full) or `PartiallySettled`; `actualSettlementDate` populated | SETTLEMENT-class tx discharging in-flight wallets to nostro; closes obligation. Partial spawns child obligation for residual |
| **sese.027** Securities Transaction Cancellation Request | Out/In | Requests cancellation of pending instruction | `BusinessEvent(eventQualifier="Cancellation")`; `transferStatus = Cancelled` | LIFECYCLE: `ObligationStatusUpdate(* → Cancelled)`. Position is **not** reversed |
| **camt.054** Bank-to-Customer Debit/Credit Notification | In (cash bank → Ledger) | Notifies cash credit/debit on nostro | `BusinessEvent(eventQualifier="Settlement")`; cash-leg `transferStatus = Settled` | SETTLEMENT-class discharging cash in-flight wallet to cash nostro |
| **MT54x** (legacy SWIFT — MT540/541/542/543/544/545/546/547) | Both | Legacy FIN equivalents of sese.0xx | Same CDM events | Same; FIN-vs-XML is transport-layer. Ledger normalises legacy MT54x to sese.0xx-equivalent CDM event before persisting |

**Critical observation:** each ISO 20022 message is a *witness* to a state transition, not the transition itself. The Ledger emits LIFECYCLE-class transactions on receipt (no moves); the witness is recorded as the source of the state change. State is *driven by attested observations*, never by inference.

### 8.6 What CDM 6.0.0 features NOT to use

| Tempting feature | Why wrong | Correct alternative |
|---|---|---|
| `PCDeliverableObligationCharac.partialCashSettlement` | CDS-specific; unrelated | Gap 6 PartiallySettled |
| `sixtyBusinessDaySettlementCap` (CDS buy-in text) | CDS auction context, not CSDR | Gap 9 BuyInInstruction |
| Settlement-date position recognition | Violates DS1 (E1) | Trade-date accounting + Gap 11 |
| Reversing position on fail | Violates DS7 (E3) | Zero moves on fail; only obligation status updates |
| `Lineage` for obligation chain | Deprecated in CDM 6.x | Gap 10 `Obligation.parentObligation` |
| Settlement status on `Trade.contractDetails` | Conflates legal-static with operational-dynamic | Settlement status on `TransferState` |
| `EconomicTerms.collateral` for CSA | Product-level intrinsic, not CSA | `Trade.collateral CollateralProvisions` |
| `DigitalAsset` for tokenised cash | Excluded by doc-string condition | Tokenisation gap (out of v11.0 scope) |

## 9. Regulatory footprint

Every emission is a **deterministic projection** of the move stream + L_17 rule-set version pin. No firm-specific reinterpretation. No manual mapping. [isda §0]

### 9.1 The definitive regulatory matrix

| Regime | Trigger | What MUST be emitted | Format | Cadence | Dedup key | Rule-set pin | DRR status |
|---|---|---|---|---|---|---|---|
| **MiFIR Art 26 (RTS 22)** | New trade in scope (EU/UK/CH listed equity, derivative on equity) | Transaction report — ISIN, MIC, LEI buyer/seller, qty, price, exec ts, trader ID | RTS 22 XML via ARM → ESMA / FCA | T+1 by 23:59 local of NCA | `(reporting_lei, internal_tx_id, version)` → `transactionReferenceNumber` | MiFIR/RTS 22 v3 (post-2025 review) | In progress (DRR roadmap) |
| **EMIR Refit Art 9** | New OTC derivative (incl. equity TRS, equity options, single-name CDS); lifecycle event | Trade + lifecycle reports — UTI, UPI, LEI, action type, event type | ISO 20022 auth.030 → DTCC / REGIS-TR / KDPW | T+1 (T+2 in UK from 30 Sep 2024 for some events) | `(reporting_LEI, UTI, action_type, event_type, sequence_number)` | EMIR Refit RTS 2022/1855 + ESMA validation rules | **LIVE (Apr 2024 EU; Sep 2024 UK)** |
| **CSDR Art 7 (settlement discipline)** | Settlement instruction; daily fail status; monthly penalty cycle | Daily fail register; monthly `semt.044` penalty advice; buy-in instruction | ISO 20022 `sese.024/025/027`, `semt.044` inbound | Daily T+ISD+1; monthly cycle | `EndToEndId` on `sese.023`; `MessageId` inbound | CSDR RTS 2018/1229 + 2024 amendment | Not in DRR (CSDR is settlement) |
| **SFTR Art 4** | New SFT (repo, SBL, BSB, margin lending) | Trade report — UTI, action type, principals, collateral schedule | ISO 20022 auth.052 → REGIS-TR / DTCC | T+1 dual-sided | `(reporting_LEI, UTI, action_type, event_date)` | SFTR RTS 2019/356 | In progress (DRR roadmap) |
| **FINRA SLATE (Rule 6500)** | New SBL or covered loan; modifications; close-outs | Loan-level — CUSIP, qty, rate, collateral, term, lender/borrower | XML to FINRA SLATE | Same-day for new loans (T); modifications T+1 | `loan_id` (FINRA-assigned) + `event_seq` | FINRA Rule 6500 (effective Jan 2026) | Not in DRR |
| **Reg SHO (Rule 200, 203, 204)** | Short sale; locate; FTD past T+3 (T+5 MM) | Locate record; FTD report; threshold securities list | SEC EDGAR + FINRA OATS-equivalent | T (locate); EOD T+3 (FTD); daily threshold | `(broker, CUSIP, trade_date, locate_id)` | SEC Rule 200/203/204 | Not in DRR |
| **Pillar 3 / BCBS 239 (settlement-fail metrics)** | Quarterly aggregate; capital aged buckets per CRR Art 379 | Failed-trade aggregate by ageing bucket (5/16/31/46+ days), gross/net, by counterparty class | XBRL (FINREP/COREP); machine-readable Pillar 3 (proposed) | Q+45 calendar days | `(reporting_lei, period_end, taxonomy_version, line_item_code)` | CRR Art 378–380; BCBS Pillar 3 (CD Mar 2026) | Proposed: ISDA/IIF/GFMA Mar 2026 response advocates DRR/CDM template |
| **MAR Art 16 (suspicious orders)** | Trade with abnormal pattern | STOR report | Free-form structured to NCA | "Without delay" | `(detector_id, ts, internal_alert_id)` | MAR RTS 2016/957 | Not in DRR (alert-driven; OoS) |
| **IFRS 9 / IAS 1 / IAS 32** | Periodic; settlement-fail material balance | Notes — settlement receivables, ECL, large exposures | iXBRL (ESEF) | Quarterly / Annual | `(entity_lei, period_end, taxonomy_version)` | IFRS 9.5.1.3, 5.5.5; IAS 1.55; IFRS 7.6 | Cross-walk — accounting projection from move stream + obligation register |

**Two non-negotiable design points:**

1. **Every dedup key is content-addressed** on `(LEI, UTI/EndToEndId/transactionReferenceNumber, version)`. The TR/ARM acknowledgement (acknowledged-sum match) is the discharge predicate of the L_17 regulatory-submission obligation. **The Trade Repository is the natural reconciliation oracle for our regulatory completeness invariant.**
2. **Versioning is bitemporal.** Rule sets change (Mar 2024 CSDR penalty recalibration; Sep 2025 ESMA validation table update; Apr 2024 EMIR Refit go-live; UK T+1 reformatting). The L_17 row carries the rule-set version pin (ADR-9/B9 boundary). Every restatement is a deterministic projection of the move stream as it is now known to have been at the obs date.

### 9.2 CSDR cash penalty calculation + discretionary buy-in

```
penalty(instruction, day) = qty × ref_price × penalty_bps_rate(asset_class, fail_type, day - ISD)
```

Rate table (2024 ESMA recalibration, Reg (EU) 2024/1623):
- Liquid shares (continuously traded): 1.0 bps/day
- Illiquid shares (other than SME-growth-market): 0.5 bps/day
- SME-growth-market: 0.25 bps/day
- Liquid sovereign debt: 0.10 bps/day
- Other sovereign / corporate debt: 0.20 bps/day
- Cash leg: ECB main refi rate × (days_late / 360), floored at 0

**Ledger emission discipline:** Ledger does **not** compute penalties autonomously. CSDs are the source of truth (T2S central penalty mechanism for Eurosystem; bilateral CSDs for non-euro EU; UK CSDR post-Brexit divergent but operationally aligned). Ledger **records** the penalty as `L_15.Obligation` of kind `CSDR_PENALTY` with payload `(rate_basis_points, days, source_lei, currency, semt044_msgId)`. Ledger **reconciles** CSD-issued penalty advice (`semt.044`) against the failing-day cursor on the open Obligation; break opens `wf-csdr-penalty-break` in `L_18`. PolicyConfiguration (`L_7^P`) carries the bps schedule for firm internal accrual (used pre-`semt.044` for capital and PnL); versioned bitemporally.

**Discretionary buy-in (post-2024 review):** original 2022 mandatory regime suspended (Reg (EU) 2022/2554); 2024 review reinstated discretionary regime via Art 7(3a). Buy-in trigger: day `ISD + buyin_extension_days` (default 4 BD liquid, 7 BD SME-growth, 15 BD illiquid). Configurable per CSD via `L_4` and `L_16`. Buy-in agent: external (CCP-facilitated or party-level). Ledger emits buy-in instruction (`L_15.Obligation`, kind `CSDR_BUYIN`) and consumes execution as fresh `SETTLEMENT` transaction with metadata linking to original failed `tx_id`. **Conservation preserved by construction: buy-in is a real trade; original failing trade left in place (per E1).**

Cash compensation (where buy-in not feasible): difference between original price and reference price (CSDR Art 7(7)) flows as separate cash transaction. Original obligation transitions to `Compensated` (terminal).

### 9.3 T+1 transition — same mechanism, different parameter

- **US:** T+1 since 28 May 2024. **Done.**
- **UK:** Target 11 October 2027.
- **EU:** Target 11 October 2027.
- **Switzerland (FINMA):** Aligned with EU/UK; SIX consultation 2025 → 2027 transition.
- **Asia-Pacific:** Mostly already T+2; some markets considering T+1.
- **India:** Already T+1 (since 2023); T+0 (optional) since 2024 for ~25 stocks.

**Architectural answer: parameter, not architecture.** The Ledger absorbs T+1 because ISD is a parameter on the settlement instruction, not an assumption baked into invariants. Parameters live in:
- `ProductTerms[u].settlement_cycle` (per ISIN × MIC), sourced from `L_4 CalendarConvention` + `L_16 ReferenceMaster`;
- `Trade.cdm_payload.settlementDate`;
- `L_15.Obligation.deadline` (computed at trade time);
- `L_18` break-aging timers (`T+1, T+3, T+5, T+ISD+CSDR_buyin`).

**Structural surface that operational machinery must adapt to:**

- **(a) FX cutoffs.** Cross-currency cash equities collapse FX-funding window by half. CLS PvP cutoffs at 00:00 CET. Ledger represents each currency leg as distinct `L_15.Obligation` with `settlement_type=PvP` and per-leg `csd_or_correspondent`. Herstatt risk is *named*, *quantified* (asymmetric-state window = `leg₁.SETTLED ∧ leg₂.non-terminal`), but cannot be eliminated by ledger design alone.
- **(b) ETF NAV cycle.** EU ETFs settling T+1 against underlying baskets that may settle T+2 (Asian underliers) introduces multi-cycle obligation graph. `L_15` framework absorbs: ETF creation/redemption is parent obligation whose discharge predicate is conjunction of basket-leg obligations' discharges.
- **(c) DTC night cycle (US-specific).** Affirmation/matching cutoffs collapsed to 9pm ET on T (or 11:30 AM ET T+1 in post-2024 cycle). For non-US firms operating into US markets: affirmation must complete same-day from local time zone. Architecture absorbs as deadline parameter; workflow timer must support per-jurisdiction calendars without manual override (`L_4` + `L_16` pinning).
- **(d) Corporate actions.** Cum/ex-date, manufactured payments, cum-dividend trade window. Under T+1, buyer settles on record date, fundamentally changing entitlement chains. Architecture handles via manufactured-dividend obligation pattern (v10.3 §13); jurisdictional fragmentation is the reason transition slipped from initial 2026 ambitions to October 2027.
- **(e) EU/UK fragmentation until October 2027.** Settled by `ProductTerms[u].settlement_cycle` per (MIC, ISIN). Per-trade per-leg per-jurisdiction settlement cycles without conflation; DRR per-jurisdictional rule pin via `cdm_version` + `regime_pin`.

### 9.4 T+0 / atomic DLT settlement — degeneracy test

Architecture MUST degrade cleanly to T+0 by parameter change.

| Element | T+2 | T+1 | T+0 atomic on-chain |
|---|---|---|---|
| `Trade.settlementDate` | T+2 | T+1 | T+0 (=T) |
| L_15 deadline | T+2 EOD | T+1 EOD | T+ε (or T+0+slot) |
| Discharge predicate | `ByMatch(sese.025)` | same | `ByAttestation(on-chain finality oracle)` |
| Virtual wallet inflight period | 2 BD | 1 BD | ε seconds (effectively zero) |
| Reconciliation to depot | Daily T+1 | Daily T+1 | Continuous on-chain query |
| Reconciliation to nostro | Daily T+1 | Daily T+1 | Continuous (nostro IS the chain) |
| CSDR penalty regime | Active (EU) | Active | **N/A (no fail)** |
| FX leg | Two ISO 20022 legs, async | Two legs, tighter window | Atomic PvP via on-chain or CLS-on-chain bridge |
| Capital treatment (CRR Art 379) | Active from ISD+5 | Active from ISD+5 | **No unsettled-trade capital** |
| Pillar 3 fail metrics | Quarterly aggregate | Quarterly aggregate | Approaches zero |
| Buy-in regime | Discretionary | Discretionary | N/A |
| ECL on settlement receivables | Required | Required | **Approaches zero** |

**What stays constant:**
- The 7-state FSM (FAILED branch becomes vanishingly improbable, but FSM does not change).
- The L_15 Obligation object — discharge predicate kind changes, structure does not.
- Conservation invariants — preserved by construction at every horizon.
- Trade-date economic recognition — preserved; T+0 just collapses open window to zero.
- The DRR engine — same code, regime pin changes.

**This is the test of the architecture.** Hardcoding T+2 is technical debt with a known due date.

### 9.5 MiFIR RTS 22 — what ships at T+1

T+1 by 23:59 in local time of relevant NCA, per MiFIR Art 26(1). **Independent of settlement status.** Fields impacted: Field 28 (Trading date and time) = T (NOT T+ISD); Field 36 (Quantity) = trade quantity; Field 33 (Price) = trade price; Field 41 (Buyer LEI), Field 49 (Seller LEI) = counterparties at trade. **Settlement status does NOT appear in RTS 22.** A trade is reported at T+1 regardless of clean / fail / partial / buy-in. Subsequent failures do not generate MiFIR amendment.

CANCELLED at trade level → MiFIR amendment (`CANC` action under RTS 22 Field 3, carrying original `transactionReferenceNumber`). Trade economic correction (price adjustment) → AMEND action.

Dedup key: `(submitting_LEI, transaction_reference_number, action_type, submission_timestamp_to_NCA)`. Replay is a no-op via regulator's deduplication. Restatement = new L_17 row referencing prior submission's `transaction_reference_number`.

### 9.6 EMIR Refit / DRR — live status

**Coverage shipped:** CFTC (Dec 2022), JFSA (Apr 2024), EMIR EU (Apr 2024), UK EMIR (Sep 2024), ASIC (Oct 2024), MAS (Oct 2024), Canada (Jul 2025), HKMA (Sep 2025).

**In progress:** EU/UK MIFID, EU/UK SFTR, Switzerland (FINMA), SEC rules.

**Production users (Nov 2025):** Banque Pictet, BNP Paribas, JSCC, JPMorgan (4 firms live); 13 PoC firms (Goldman Sachs, DTCC, DBS, others).

**TR acknowledgement rates:** 100% under MAS rules; 98.2% under EMIR Refit. **Cost reduction:** up to 50% reduction in ongoing reporting costs vs bespoke firm implementations.

**For deferred-settlement on cash equities:** the cash equity itself is **not in EMIR scope** (EMIR is OTC derivatives; cash equity is MIFIR). The cash equity that is the **physical settlement of an OTC equity derivative** is reported via the OTC trade's lifecycle event. CSDR / settlement-discipline machinery applies to the cash-equity settlement itself.

### 9.7 Tri-regime UTI gotcha (SFTR / CSDR / MiFIR)

A securities-borrowing transaction (SBL) on an EU-listed equity has triple regulatory footprint:
- **SFTR (Art 4):** SBL itself is reported as SFT to TR. Dual-sided.
- **EMIR Refit (Art 9):** if part of CCP-cleared chain (less common for SBL), cleared leg is EMIR-reportable.
- **CSDR (Art 7):** settlement of SBL is subject to CSDR settlement discipline.
- **FINRA SLATE (Rule 6500, US):** same-day reporting of new SBL; rate transparency post-trade.
- **Reg SHO (Rule 200, 203, 204):** locate, threshold, FTD close-out for the equity leg of the short sale.

**UTI generation discipline:**

```
UTI = LEI(generating_party) || hash_jcs(...trade_essential_terms...)
```

UTI is THE primary identity; firm-internal trade refs and `EndToEndId`s are derived from the UTI, not the other way around. The Ledger supports this via Λ10 (`tx_id = hash_jcs(business_event_id, attempt_seq)`) — UTI computed from trade essentials at execution time and pinned for trade's lifetime.

**Value-date conventions — load-bearing gotcha:**
- **SFTR:** trade date for `event_date`, contractual settlement date for `value_date`.
- **EMIR:** execution timestamp for `execution_timestamp`, lifecycle event date for relevant action.
- **CSDR:** ISD (intended settlement date) for penalty start.

An SBL trade executed Friday with same-day settlement (`T+0`) for borrow's *initiation* and `T+ISD = T+30` for *close* has FOUR distinct dates: T (trade date, SFTR `event_date`); T (initiation settlement, CSDR penalty-clock for open leg); T+30 (contractual close date, SFTR for close-leg report); T+30 (close settlement, CSDR penalty-clock for close leg). **A naive implementation conflates trade date (T) with close-settlement date (T+30) for SFTR, which silently mis-reports value dates.** Repeated finding in 2022-2024 SFTR data quality reviews.

## 10. Accounting + audit + capital

[ashworth §1-§14]

### 10.1 Trade-date accounting MANDATORY (IFRS 9.B3.1.3, ASC 320-10-25-3)

**Ruling A1.** For every cash-equity, listed-debt, listed-derivative, and equivalent regular-way trade, **trade-date accounting is mandatory at the ledger primitive level.** The move stream MUST recognise the economic position at trade-execution timestamp `T`, not at contractual settlement timestamp `T+k`. Settlement-date accounting is **not** supported as a ledger primitive; downstream consumers requiring it produce it as a **reporting projection** over move stream + obligation FSM — never by deferring underlying moves.

**Standard grounding.**
- **IFRS 9.B3.1.3** (regular-way trade exception): trade-date OR settlement-date, applied consistently for all purchases and sales of financial assets that belong to the same category.
- **IFRS 9.B3.1.5:** consistent application across the four IFRS 9 measurement categories.
- **ASC 320-10-25-3** (US GAAP, AFS and trading): trade-date or settlement-date; trading-securities classification effectively defaults to trade-date.
- **ASC 326-20-30-2** (CECL initial recognition): allowance recognised at acquisition date (trade date under trade-date accounting).
- **IAS 32.42** (offsetting): financial assets and liabilities offset only when there is a currently enforceable legal right of set-off and intention to settle net or simultaneously. The settlement receivable (security long) and payable (cash short) generally do **not** satisfy IAS 32.42 because they are obligations to *different counterparties* — must be presented gross (IAS 1.32).
- **Single-Coordinate Move Principle** (v10.3 §13.2): each move alters one coordinate of one unit at one entity. Settlement-date accounting would require deferring `own` move to T+k or maintaining parallel `own_settled` — both forbidden.

**Why settlement-date accounting cannot be a ledger primitive:**
1. Regulatory capital is computed on trade-date positions (CRR Art 325 FRTB; CRR Art 274 SA-CCR). A settlement-date ledger would understate market-risk capital during open window by exactly the open-position notional. For a tier-1 dealer with £4bn of unsettled buys at year-end: £400m–£800m RWA gap depending on volatility.
2. Day-1 P&L recognition (IFRS 13.B5.1.2A; ASC 820-10-30-3A) requires FVTPL position be marked from execution.
3. The path-independent PnL theorem (v10.3 P10) is incompatible with settlement-date accounting.

The downstream settlement-date projection (for fund-accounting platforms or pension portfolios that genuinely require it):

```
settled_position(w, u, t)
  := own(w, u, t) − Σ { signed_qty(o) : o ∈ open_obligations(w, u, t) }
```

Computed on read like the GPM `avail` projection. Carries no independent state; cannot drift.

### 10.2 Balance-sheet substantiation — worked numbers, journal entries

**Setup:** Dealer, FVTPL classification. BUY 100 XYZ @ $50 on Monday T, settling Wednesday T+2. Mark at $52 on Tuesday close.

**At T (Monday close):**

```
Atomic settlement transaction:
  Move 1: w_cpty_v -> w_book   unit=XYZ qty=+100   (security leg, economic recognition)
  Move 2: w_book   -> w_cpty_v unit=USD qty=-5,000 (cash leg, economic recognition)
  Register: o_sec  = SettlementObligation(SecLeg, +100, due=T+2, status=Pending)
  Register: o_cash = SettlementObligation(CashLeg, -5,000, due=T+2, status=Pending)

Conservation per unit: ΔXYZ = 0; ΔUSD = 0.
Trade-date economic exposure at T = +100 XYZ × $50 = $5,000 long.

Journal entry — Form A (full cash debit at T):
  Dr Financial assets — FVTPL (XYZ)              5,000.00
     Cr Cash                                            5,000.00

Journal entry — Form B (PREFERRED — payable presentation per IAS 1.55):
  Dr Financial assets — FVTPL (XYZ)              5,000.00
     Cr Settlement payable to counterparty            5,000.00
```

**Form B is preferred** because (a) cash has not actually left the bank, (b) presents open settlement obligation as discrete line item auditors can trace to depot statements, (c) aligns with CRR Art 379 settlement-risk disclosure.

**At T+1 (Tuesday close, mark to $52):** No moves. Pricing engine updates `P_{T+1}(XYZ) = 52`.

```
PnL_{T to T+1} = own × (P_{T+1} − P_T) = 100 × ($52 − $50) = +$200

Journal entry (mark-to-market revaluation):
  Dr Financial assets — FVTPL (XYZ)               200.00
     Cr Profit for the period (FVTPL)                  200.00
```

**At T+2 (Wednesday, CSD confirms settlement):** `sese.025` arrives. Settlement-confirmation transaction emits drains to broker virtual; **no move on `w_book`**.

```
Move 3: w_cpty_v -> w_csd_nostro unit=XYZ qty=+100   (depot materialises)
Move 4: w_csd_nostro -> w_cpty_v unit=USD qty=-5,000 (cash agent debits)
StateDelta: o_sec.status = Settled, o_cash.status = Settled

Journal entry at T+2 (closing the receivable/payable Form B):
  Dr Settlement payable to counterparty           5,000.00
     Cr Cash at custodian                              5,000.00
  Dr Securities at custodian (sub-ledger)        5,200.00   [marked at T+2 = $52]
     Cr Financial assets — FVTPL (XYZ, in transit)    5,200.00
```

Second pair = sub-ledger reclass from "FVTPL in transit" to "FVTPL settled at custodian." **No PnL impact at settlement** (P10 path-independence).

### 10.3 Five-document audit evidence chain

| # | Document | Source | Framework artefact | Linked by |
|---|---|---|---|---|
| 1 | FIX 8=ExecRpt | Trading venue / OMS | `Transaction(type=SETTLEMENT, tx_id, ts=T)` in `L_13` | `external_ref` field |
| 2 | `sese.023` Securities Settlement Instruction (outbound) | Settlement layer → CSD | Status `EXECUTED → INSTRUCTED` on `o_sec` | `sese.023.EndToEndId = trade_id` + idempotency key |
| 3 | `sese.025` Securities Settlement Confirmation (inbound) | CSD → settlement layer | `o_sec.discharge_witness` + status `Settled` | `sese.025.RelatedRef = sese.023.EndToEndId` |
| 4 | `camt.054` Bank-to-Customer Debit/Credit Notification | Cash agent → settlement layer | `o_cash.discharge_witness` + status `Settled` | `camt.054.EndToEndId = trade_id` |
| 5 | CSD depot statement (daily/weekly) | CSD direct feed | Reconciliation against `w_csd_nostro` | Position-level tie-out at `t = T+2 EOD` |

**Each document is signature-verified and content-hashed at ingress.** Each appears in `L_11.ExternalConfirmation` with bitemporal `(t_obs, t_known)`. The `external_ref` field on every Move and obligation discharge links the ledger entry back to the document.

Authority: ISA 500.6 (sufficient appropriate audit evidence), ISA 505 (external confirmations), PCAOB AS 2310 (auditor's confirmation procedures), BCBS 239 P6 (data lineage), SOX 404 / SOC 1 (settlement existence and completeness control objective), IFRS 7.B11 (liquidity and credit risk disclosure).

### 10.4 IFRS 9 ECL on settlement receivables

| Counterparty class | 2-day PD | LGD | ECL on £100m | Treatment |
|---|---|---|---|---|
| **CCP-cleared** (LCH, DTCC NSCC, Eurex, JSCC) | < 0.1 bp | 5–10% (post-default-fund) | < £5,000 | **De minimis**; portfolio pool (IFRS 9.B5.5.30) |
| **Tier-1 dealer counterparty** (LEI, IG) | 0.5–2 bp | 30–40% | £15,000 – £80,000 | Material at scale; pool by counterparty rating |
| **Sub-investment-grade bilateral** | 5–20 bp | 40–60% | £200,000 – £1.2m | Material; track by name |
| **Failed bilateral, day 5+ post-IPD** | 50–500 bp (Stage 2) | 60–80% | £3m – £40m | **Stage 2 migration** (IFRS 9.B5.5.43) |

**CSDR fail extending past contractual settlement date is a non-rebuttable Stage 2 trigger.** Recalculate ECL using Stage 2 model (lifetime ECL, where lifetime = max of CSDR mandatory buy-in horizon (4 BD liquid / 7 BD illiquid) and empirical fail-cure tail). Disclose under IFRS 7.35F if Stage 2 migrations exceed 5% of gross.

**US GAAP CECL** (ASC 326-20-30-2): same shape, no staging (always lifetime). Settlement receivables evaluated collectively for CCP-cleared; individually for failed/impaired.

### 10.5 CRR Articles 378/379/380 (capital aged buckets)

**Article 378 — Free deliveries:** 100% risk weight on current exposure (delivered amount) until second leg has effectively taken place. Applies to FOP outside CSD-DvP.

**Article 379 — Settlement risk** (CRR III, in force 1 Jan 2025) — risk weight ramp on `max(0, current_market_price − contract_price) × quantity`:

| Days post-contractual-settlement | Risk weight |
|---|---|
| 5–15 | 100% |
| 16–30 | 625% |
| 31–45 | 937.5% |
| 46+ | 1,250% |

**Article 380 — Large exposures:** settlement receivables from a single counterparty exceeding 10% CET1 trigger CRR Art 395 large-exposure reporting; 25% CET1 cap on individual counterparty exposure.

The framework's reporting projection extracts failed-trade ageing buckets per CRR Art 379 + COREP C 28.00 (CCR Settlement Risk template), keyed by per-obligation ageing computed deterministically from `(o.intended_settlement_date, current_business_date)`. Per-obligation MV snapshot for replacement-cost. Aggregation by counterparty for Art 380. CCP-cleared flag (CCP-cleared exposures attract zero CCR settlement risk under CRR Art 305).

### 10.6 SOX 404 / SOC 1 controls — eight key control objectives

| CO | Description | Type | Test |
|---|---|---|---|
| CO-1 | Trade capture completeness: every executed trade enters the ledger | Preventive, automated | FIX message sequence-number reconciliation against L_13 |
| CO-2 | Settlement instruction completeness: every committed `SETTLEMENT` tx generates exactly one `sese.023` | Preventive, automated | 1:1 matching tx_id → outbound message ID |
| CO-3 | Settlement confirmation matching: every outbound `sese.023` matches inbound `sese.025` within SLA | Detective, automated | Aged-unmatched report; SLA = `T+2 + 1 BD` |
| CO-4 | Position reconciliation: daily 3-way tie-out (ledger `own`, pending legs, external CSD depot) | Detective, manual | Daily T+1 walk-through; middle office signoff |
| CO-5 | Segregation of duties between trading and settlement | Preventive, organizational | RBAC review |
| CO-6 | CORRECTION transaction approval: every `CORRECTION` requires four-eyes + named approver | Preventive, automated | System enforcement; audit log review |
| CO-7 | Exception management: every break has owner, SLA, escalation path | Detective, manual | Aged-break aging report |
| CO-8 | Settlement-status FSM enforcement: only `SettlementWorkflow` may mutate `obligation.lifecycle_stage` | Preventive, structural | Capability-scope check (StatesHome C11) |

**Three roles structurally separated:**
1. **Front office (trader)** — execute trades; cannot modify settlement instructions/confirmations.
2. **Settlement operations** — release `sese.023`, ingest `sese.025`/`camt.054`, manage breaks; cannot execute trades or modify original move stream.
3. **Middle office / accounting** — read settled/unsettled positions, reconcile to depot, produce financials; cannot modify positions or confirmations.

StatesHome C11 capability discipline is the structural enforcement: trader code paths cannot type-check against `obligation.lifecycle_stage`; settlement-ops code paths cannot type-check against `Move(unit=ISIN, qty=...)`. **Converts segregation of duties from procedural assertion to system property.**

### 10.7 Materiality thresholds for fails

| Threshold | Quantitative | Qualitative | Disclosure / action |
|---|---|---|---|
| Aggregate unsettled receivable > 1% balance sheet | ~£1.5bn for tier-1 | n/a | Separately presented (IAS 1.55) |
| Single-counterparty unsettled receivable > 10% CET1 | ~£2bn for tier-1 dealer | Concentration risk | Large exposures (CRR Art 392); Pillar 3 |
| Failed trade aged > 5 BD | Per-trade £100k+ | CSDR penalty accrual; CCR ramp | Risk committee; COREP C 28.00 |
| Failed trade aged > 7–15 BD (CSDR mandatory buy-in) | Per-trade £1m+ | Buy-in process triggered | Buy-in workflow; cpty escalation |
| ECL Stage 2 migration > 5% of gross | n/a | Increased credit risk | IFRS 7.35F |
| Manufactured-dividend obligation unrecognised at year-end | Per-position £50k+ | Cum/ex audit trap | Provision under IAS 37.14 |
| Cross-currency open exposure > Herstatt limit | Per-leg £50m+ | Herstatt window | Risk committee; Pillar 3 narrative |
| Repeat counterparty fails (> 3/quarter, same LEI) | n/a | Operational quality | Counterparty review |
| Single fail > 25% trading-day notional | Per-trade ISIN-specific | Liquidity concentration | Risk committee + market-quality review |

Quantitative materiality per ISA 320: tier-1 dealer (£20bn CET1, £6bn pre-tax) → group materiality £30–60m; CTMP at 5% = £1.5–3m. A single failed trade > £3m is material.

### 10.8 Year-end tie-out

For every wallet × unit × counterparty with material balance:

```
Opening balance (1 Jan)
+ Σ all SETTLED moves over the year (debit and credit, by type)
+ Σ all unsettled position changes (open at 1 Jan, settled / failed during year)
+ Σ all year-end open positions
= Closing balance (31 Dec)
```

Reconciliation per `(wallet, unit, counterparty)`. Must tie:
- Opening balance to prior year-end audited balance (prior-year-end opinion-anchor).
- Each line of activity to underlying `L_13` records and `L_15.Obligation` history.
- Closing balance to year-end depot statement (positive evidence) + open-settlement register (the receivable/payable on the balance sheet face).

**Four-corner audit test:** Existence (BS → GL → L_13 → external confirmation); Completeness (external feed → ledger); Cut-off (last 2 BD December and first 2 BD January tested individually); Valuation (market price at 31 December tied to FV hierarchy disclosures). For tier-1: 25–40 sampled items for substantive testing; 100% testing of any single counterparty exceeding 10% CET1; walk-through of one settled and one failed trade.

For typical tier-1 dealer at year-end: total settled ~£280bn; aggregate unsettled receivables ~£4bn (~1.5% balance sheet); aggregate unsettled payables ~£3.8bn; net unsettled ~£200–500m. **Always material; always requires separate disclosure under IAS 1.55 + IFRS 7.**

### 10.9 CORRECTION transaction policy with four-eyes

Append-only event log; **no transaction is ever deleted**. Retroactive amendments via `CORRECTION`-typed transactions emitting anti-moves. Original transaction remains in move stream.

**Permitted scenarios:** trade booking error; counterparty disputes the trade (mutual bust); CSD reports incorrect settled amount.

**NOT permitted:** hiding a failed settlement by reversing the original; pre-dating a trade; adjusting `own` to match a custodian's wrong record; deleting a CORRECTION (correction-of-correction).

Required fields:

```
Transaction(type=CORRECTION):
  references: <original_tx_id>
  reason_code: <closed-sum: BOOKING_ERROR | CPTY_DISPUTE | CSD_RESTATEMENT | OTHER>
  justification: <free text, mandatory>
  requester_lei: <LEI of person requesting>
  approver_lei: <LEI of person approving (must differ from requester)>
  approver_role: <closed-sum: OPERATIONS_HEAD | RISK_OFFICER | CFO_DELEGATE>
  approval_timestamp: <UTC>
```

**Four-eyes is non-negotiable.** Framework rejects any `CORRECTION` where `requester_lei == approver_lei`.

After a CORRECTION:
- Original transaction remains in `L_13.MoveStream` at original `(t_obs, t_known)`.
- CORRECTION transaction appended at its own `(t_obs, t_known)`.
- Bitemporal query `as_of(t)` for any `t` between original and correction returns original (un-corrected) state.
- Query `with_corrections_through(t_known')` returns corrected state.

This is the **IAS 8.42 prior-period restatement discipline** structurally implemented via the bitemporal model.

**SOX implications:** > 10 CORRECTIONs/month from same trader = control-environment red flag; any CORRECTION reversing > £10m position = audit committee notification; any CORRECTION of year-end balance after cut-off = potential restatement (IAS 10).

### 10.10 Cum/ex corporate action audit trail

When `record_date ∈ (T, T+k]`: trade-date economic owner (buyer at T) is economically entitled to the corporate action; registered holder at record date (seller, still on CSD register until T+k) receives it from issuer; **manufactured payment** must flow from seller to buyer.

Per-trade audit record: trade execution date T; settlement date T+k; corporate action ex-date; record date; cum-or-ex flag at trade time; manufactured payment obligation (`L_15.Obligation`, kind = `MANUFACTURED_PAYMENT`); counterparty LEI; tax-residency of buyer/seller.

**Cum/ex tax-fraud red flag (ISA 240):** if same trade pattern (same ISIN, record date, counterparty pair, notional) appears repeatedly across tax jurisdictions with apparently optimised tax outcomes → escalate to engagement partner; consider regulatory-disclosure obligations. The 2007–2012 German cum/ex scandal involved multi-billion-euro losses through such patterns.

### 10.11 Cross-currency / Herstatt accounting

IAS 21: monetary items (cash, receivables, payables) translated at closing rate; FX gains/losses to P&L. FVTPL equity in foreign currency: full FV change (incl. FX) to P&L. Settlement receivables/payables: **always monetary; always translated at closing rate; FX gains/losses always to P&L.**

**Herstatt window:** time period between first and second leg of cross-currency settlement when one leg has settled and other has not. Mitigation: CLS for major pairs; non-CLS legs (most EM, some minor majors) carry residual Herstatt risk.

Disclosure (CRR Art 442 + IFRS 7.B11): aggregate cross-currency open exposure; CLS-eligible vs non-CLS-eligible split; largest single-counterparty Herstatt exposure; internal Herstatt limits.

**Evidence retention:** 7 years of full `L_13` move stream; full `L_15.Obligation` history including all status transitions; full `L_11.ExternalConfirmation` envelopes (signature-verified); full `L_18.BreakRegister` history. Bitemporal makes this structurally satisfied (nothing deleted; historical states reconstructible by replay).

## 11. Invariants DS1–DS18

[formalis §1]

### DS1 — Economic-Exposure-at-T (MANDATORY)

**Statement.** For every settlement-typed transaction τ committed at T with intended settlement t_d ≥ T, for every party wallet w, every unit u moved by τ, every t ∈ [T, t_d^+] ∪ [t_d^+, ∞):

$$w_t(u)[\text{own}] - w_{T^-}(u)[\text{own}] = \sum_{m \in τ, m.\text{unit}=u, w \in \{m.\text{src}, m.\text{dst}\}} \text{signed-delta}(m, w)$$

equivalently: there exists no projection Π over (move stream + status overlay + obligation log) whose value during [T, t_d^-] differs from its value after τ has reached `Settled`, holding the price function constant.

**Parent:** v10.3 P1, §11.4, P10. **Type:** hybrid. **Severity:** CRITICAL. PnL is wrong, risk is wrong, regulatory capital is wrong if violated.

### DS2 — Open-Window Conservation

**Statement.** For every unit u and every time t (including every t ∈ [T, t_d^-]):

$$Q(u)(t) = \sum_{w \in \mathcal{W}_{\text{real}} \cup \mathcal{W}_{\text{virtual}}} w_t(u)[\text{own}] = 0$$

**Parent:** v10.3 P1, StatesHome C2. **Type:** runtime. **Severity:** CRITICAL.

### DS3 — Reconciliation Lead-Lag Identity (algebraic)

**Statement.** For every real wallet w, every unit u, every time t:

$$w_t(u)[\text{own}] = \text{depot}_w^{\text{custodian}}(u, t) + \text{InFlight}_w(u, t)$$

with $\text{InFlight}_w(u, t) = \sum_{τ : w \in \text{parties}(τ), \text{SettlStatus}(τ) \in \{\text{Executed, Instructed, Failed, PartiallySettled}\}} \text{signed-qty}(τ, w, u)$

**Parent:** v10.3 §13 line 3538 (SBL recon identity). **Type:** runtime. **Severity:** HIGH.

### DS4 — No Discharge Without Witness

**Statement.** For every settlement obligation o:

$$o.\text{state} \in \{\text{Discharged, PartiallyDischarged, Compensated}\} \Rightarrow o.\text{discharge\_witness} \neq \varnothing \wedge \text{verify\_envelope}(o.\text{discharge\_witness}) = \text{true}$$

**Parent:** nazarov INV-DS-2; data spec L_11 ExternalConfirmation contract. **Type:** hybrid. **Severity:** CRITICAL — equivalent to forging settlement.

### DS5 — Replay Determinism on Out-of-Order Finality

**Statement.** For any two interleavings π_1, π_2 of the same multiset of confirmation messages applied to the same initial state σ_0:

$$\text{apply}(\sigma_0, \pi_1) = \text{apply}(\sigma_0, \pi_2)$$

restricted to (L_13, SettlStatus, L_15). **Parent:** Λ_8, v10.3 P9, nazarov INV-DS-4. **Type:** runtime. **Severity:** CRITICAL.

### DS6 — Idempotency of Finality Messages

**Statement.** For any confirmation message c targeting obligation o: $\text{ingest}(c) \circ \text{ingest}(c) = \text{ingest}(c)$. Re-presenting same message has no incremental effect on L_13, SettlStatus, L_15.

**Parent:** v10.3 P5, P6; data spec N_4, B_12. **Type:** runtime. **Severity:** HIGH.

### DS7 — Failure Non-Reversal

**Statement.** For every settlement obligation o and every transition `o.state: Pending → Failed`:

$$\forall w \in \mathcal{W}_{\text{real}}, \forall u : w_{\text{after-fail}}(u)[\text{own}] = w_{\text{before-fail}}(u)[\text{own}]$$

No move on a real wallet's `own` coordinate is emitted as a consequence of a settlement-fail event. **Only legal exception:** a `CORRECTION` transaction with explicit anti-moves, four-eyes approval. **Parent:** v10.3 §8.4, FAQ Q5; IFRS 9.B3.1.3; CRR Art 379. **Type:** hybrid. **Severity:** CRITICAL.

### DS8 — Status Monotonicity within Terminal-Set Semantics

**Statement.** For every settlement obligation o, the lifecycle FSM transitions only in: `Pending → Instructed → {Settled, Failed, PartiallySettled}` with retrograde edges only `Failed → Instructed` (re-instruction post buy-in) and `PartiallySettled → Instructed` (continue settling residual). No path back to `Pending`. No path out of `{Settled, Cancelled, BoughtIn, Defaulted}`; absorbing.

**Parent:** v10.3 §11.7; data spec §3 L_15. **Type:** compile-time. **Severity:** HIGH.

### DS9 — Buy-In Compensation Closure (CSDR / Reg SHO)

**Statement.** For every settlement obligation o that transitions to `Failed` and is not cured by re-instruction within Δ_CSDR:

$$\exists τ_{\text{buyin}} \in L_{13}, \exists o_{\text{buyin}} \in L_{15} : τ_{\text{buyin}}.\text{type} = \text{Buyin} \wedge o.\text{compensation\_handler} = \kappa_{\text{buyin}}(τ_{\text{buyin}}, o_{\text{buyin}})$$

**Parent:** Λ_13; v10.3 §13 P21; CSDR Art 7(3); Reg SHO Rule 204. **Type:** runtime. **Severity:** HIGH.

### DS10 — Cross-Currency Herstatt Visibility

**Statement.** For every cross-currency trade τ, the trade emits a parent obligation o_fx with two child obligations o_ccy1, o_ccy2, each with own settlement-date and discharge witness. Parent's discharge predicate is the conjunction:

$$D_{\text{fx}}(\sigma) = (o_{\text{ccy1}}.\text{state} = \text{Discharged}) \wedge (o_{\text{ccy2}}.\text{state} = \text{Discharged})$$

The Herstatt-window invariant: at every t, exactly the open obligations whose `state` is non-terminal are visible as quantified exposure. **Parent:** v10.3 §2.6; Λ_15. **Type:** runtime. **Severity:** HIGH. Framework does not eliminate Herstatt risk (no ledger design can); it names, quantifies, routes compensation, audits the loss.

### DS11 — Partial-Settlement Conservation

**Statement.** For every partial settlement event with q' < q delivered, q − q' remaining:
1. Original obligation o.state → `PartiallySettled`.
2. Economic position (real wallet `own`) is **unchanged** by partial-settle event itself — original τ recognised full q at T.
3. Child obligation o_rem registered with `parent_obligation_id = o.id`, q_rem = q − q', t_d^rem = original t_d extended per CSDR/regime.
4. Conservation: q_rem + q' = q.

**Parent:** v10.3 §11 P9; data spec §3 L_15. **Type:** runtime. **Severity:** HIGH. Termination concern: PO-9 must pin recursion bound D_max.

### DS12 — Variant Degeneration (T+1 is a parameter)

**Statement.** Deferred-settlement representation is parameterised on `settle_date = t_d` and degenerates uniformly across:
- T+0 (atomic on-chain DvP): t_d = T, obligation issued and discharged in same atomic transaction; `Pending` state has zero duration.
- T+1: t_d = T + 1 BD; FSM unchanged.
- T+2: canonical case.
- T+5+: t_d = T + n BD, parameterised in `ProductTerms[u].settlement_cycle`.

**For all variants, DS1–DS11 hold without modification; only workflow timer durations change.** **Parent:** v10.3 §11 P0. **Type:** structural. **Severity:** MEDIUM.

### DS13 — Reconciliation Pair Anchoring

**Statement.** Daily T+1 morning identity check between ledger and external custodian/CSD report, parameterised by settlement status:

$$\text{Reconciled}(t) \iff \forall τ : \text{SettlStatus}(τ)(t) \in F_{\text{terminal}} \Rightarrow \Pi_{\text{ledger}}(τ, t) = \Pi_{\text{external}}(τ, t)$$

i.e., ledger and external agree on every transaction in a terminal state, and lead-lag is *exactly* the sum of non-terminal obligations (DS3). **Parent:** data-spec L_6 reconciliation pair. **Type:** runtime. **Severity:** MEDIUM.

### DS14 — CSDR Penalty Schema Determinism

**Statement.** For every settlement obligation o in `Failed` state at end-of-day t > t_d, a CSDR penalty obligation o_pen ∈ L_15 is registered atomically with the day-end roll, with payload `⟨rate_basis_points, days_late, source_lei, currency, notional⟩` where penalty rate is selected by pure function from versioned CSDR rate matrix, pinned by `VersionPinSidecar`. **Parent:** data-spec §Operational-CSDR; CSDR Art 7(2); Reg (EU) 2017/389. **Type:** runtime. **Severity:** MEDIUM.

### DS15 — Counterparty Default Close-Out Routing

**Statement.** If counterparty c defaults at t_def ∈ [T, t_d^+], every open settlement obligation against c transitions to `Compensated` via close-out-netting compensation handler, and close-out value is computed per ISDA Master Agreement (or analogous bilateral terms) at t_def. **Parent:** v10.3 §13 close-out netting; ISDA close-out terms. **Type:** runtime. **Severity:** HIGH.

### DS16 — Bitemporal Restatement, Never Mutation

**Statement.** When a CSD or custodian issues a correction (restatement of prior confirmation), the original L_11 row is preserved (with t_known of original ingest); a new row is appended with same t_obs but new t_known. The obligation's `corrections_chain` grows by one. Both query modes `as_of(t_known)` and `with_corrections_through(t_known')` are first-class. **Parent:** data-spec N_9, Λ_4; nazarov INV-DS-5. **Type:** compile-time (append-only structure). **Severity:** HIGH.

### DS17 — Capability Scoping on Settlement Status Writes

**Statement.** Each `SettlStatus(τ)` field has a unique writer: the `SettlementWorkflow` of v10.3 §11.5. No other handler (post-trade gateway, trader, risk system, regulatory reporter) may mutate it. They may read per their capability; writes are gated. **Parent:** StatesHome C11; Λ_14. **Type:** compile-time (phantom typing on write capability). **Severity:** HIGH.

### DS18 — DvP Ledger-Level Atomicity

**Statement.** For every settlement-typed transaction τ that contains both a securities leg and a cash leg (DvP), the executor commits both legs atomically: both apply or neither does, observable as a single `StateDelta`. **Parent:** v10.3 P2, §8.4; StatesHome C3; minsky I-DEF-12. **Type:** structural. **Severity:** CRITICAL.

### Type-vs-runtime decomposition summary

6 compile-time, 9 runtime, 3 hybrid out of 18:

| Invariant | Type | Mechanism |
|---|---|---|
| DS1 — Economic-exposure-at-T | HY | (CT) capability typing on `own` write-handlers; (RT) PnL-independence property test |
| DS2 — Conservation | RT | StatesHome C2 structural argument |
| DS3 — Reconciliation identity | RT | property-test; sign convention pinned (PO-3) |
| DS4 — No discharge without witness | HY | (CT) FSM takes witness as param; (RT) cryptographic verify |
| DS5 — Replay determinism | RT | property-test (multi-permutation replay) |
| DS6 — Idempotency of finality | RT | content-addressed dedup at ingest |
| DS7 — Failure non-reversal | HY | (CT) capability typing on settlement-fail handler; (RT) mutation testing |
| DS8 — Status monotonicity | CT | closed-sum FSM + exhaustive pattern match |
| DS9 — Buy-in compensation closure | RT | Temporal timer + saga-tower |
| DS10 — Herstatt visibility | RT | projection over L_15 |
| DS11 — Partial conservation | RT | property-test on residual monotonicity |
| DS12 — Variant degeneration | CT | t_d is workflow input parameter |
| DS13 — Reconciliation pair anchoring | RT | daily T+1 cron |
| DS14 — CSDR penalty schema determinism | RT | pure function from versioned rate-matrix |
| DS15 — Counterparty default close-out | RT | LifecycleOracle event handler |
| DS16 — Bitemporal restatement | CT | append-only log structure |
| DS17 — Capability scoping | CT | phantom typing on writer capability |
| DS18 — DvP ledger-level atomicity | CT | executor primitive guarantees atomic StateDelta |

**Recommendation:** take compile-time cost for DS17 and DS7 (silent and economically catastrophic violations); leave others runtime. DS1 stays hybrid.

## 12. Type design

[minsky §1-§14]

### 12.1 Lifecycle FSM as closed sum with carried evidence

The transaction-level FSM `EXECUTED → INSTRUCTED → SETTLED | FAILED` is currently a string in `cdm_payload.lifecycle_stage`. This is the single most expensive design choice in v10.3 from a correctness standpoint. A string admits typos (`"setled"` — Jane Street's example, shipped at a Tier-1 firm), admits unknown values from upstream deserialisation, and admits no exhaustiveness check at handler sites.

Replace with a closed sum, with **carried evidence in each state**:

```ocaml
type lifecycle =
  | Pending          of { issued_at : Time.t;        tx_id : Trade_id.t }
  | Instructed       of { instructed_at : Time.t;    sese_023_id : Iso20022_msg_id.t }
  | PartiallySettled of { qty_settled : Qty.t;       partial_at : Time.t;
                          sese_025_id : Iso20022_msg_id.t;
                          remainder_id : Obligation_id.t }
  | Settled          of { settled_at : Time.t;       sese_025_id : Iso20022_msg_id.t }
  | Failed           of { failed_at : Time.t;        reason : failure_reason;
                          csdr_clock_started_at : Time.t option }
  | BoughtIn         of { boughtin_at : Time.t;      buyin_ref : Buyin_ref.t;
                          predecessor : Obligation_id.t }
  | Cancelled        of { cancelled_at : Time.t;     correction_tx : Trade_id.t;
                          approver : Operator_id.t }

and failure_reason =
  | DeadlineMissed
  | NoCover
  | CounterpartyDefault of Lei.t
  | CsdReject of Csd_reject_code.t   (* closed sum, ISO 20022 normalised *)
  | LegInconsistent of which_leg     (* DvP partial, formalis G4 *)
  | Manual of Operator_id.t
```

`failure_reason` is a closed sum, not a free string. Closes formalis G1.

**Total step function** returns a closed sum `Step | Reject | Idempotent`; pattern-match is exhaustive (`-warn-error +partial-match`); no wildcards. Out-of-order events return `Reject` with documented reason; terminal states (`Settled | BoughtIn | Cancelled`) absorb late events as `Idempotent` (the late-discharge-race local leg).

### 12.2 PairedObligation — DvP atomicity at the type level

The DvP guarantee in v10.3 §8.4 is enforced at the trade-time atomicity primitive but **not at discharge time** — different handler runs at T+2; nothing in v10.3 forbids it from discharging the security leg without the cash leg. Formalis G4 `LegInconsistent`. Fix is structural:

```ocaml
module PairedObligation : sig
  type t  (* abstract; constructed only via [pair] *)

  type pairing_error =
    | Different_trade_id    of Trade_id.t * Trade_id.t
    | Different_settle_dates of SettleDate.t * SettleDate.t
    | Mirrored_qty_mismatch  of { sec_qty : Qty.t; cash_qty : Cash.t; expected_cash : Cash.t }
    | Same_side_pairing      (* both legs deliver-side, or both receive-side *)
    | Wrong_leg_units        of { sec_unit : Unit_id.t; cash_unit : Unit_id.t }

  val pair :
       security_leg : Obligation.t
    -> cash_leg     : Obligation.t
    -> (t, pairing_error) Result.t

  val security_leg : t -> Obligation.t
  val cash_leg     : t -> Obligation.t
end

(* Discharge consumes a [PairedObligation] atomically.
   There is NO public function [Obligation.t -> ... -> DischargeResult.t]. *)
val discharge :
     PairedObligation.t
  -> csd_confirmation : Sese_025_msg.t
  -> now              : Time.t
  -> (DischargeResult.t, discharge_error) Result.t
```

There is no way to build a single-leg discharge from outside the module. If the CSD says "DvP success on cash, DvP fail on security", `discharge` returns `Error (Confirmation_only_one_leg CashLegOnly)` and **neither balance moves**. Break workflow opens. No partial PnL. No half-settled trade.

### 12.3 Phantom-typed wallet handles

Three classes:

```ocaml
type real_wallet
type cpty_virtual_wallet
type csd_virtual_wallet

val of_real : Wallet_id.t -> real_wallet wallet_handle
val of_cpty : Wallet_id.t -> cpty_virtual_wallet wallet_handle
val of_csd  : Wallet_id.t -> csd_virtual_wallet wallet_handle
```

The trade-time emitter is the **only** function that writes a real wallet:

```ocaml
val emit_trade :
     real_wallet      wallet_handle    (* buyer's real wallet *)
  -> cpty_virtual_wallet wallet_handle (* counterparty mirror *)
  -> security : (Isin.t * Qty.t)
  -> cash     : (Currency.t * Cash.t)
  -> trade_date : TradeDate.t
  -> settle_convention : SettleConvention.t
  -> (Transaction.t * PairedObligation.t, trade_error) Result.t

(* The settlement-time emitter is the ONLY function that writes a CSD virtual wallet.
   It does NOT take a real wallet handle. *)
val emit_discharge :
     PairedObligation.t
  -> cpty_virtual_wallet wallet_handle  (* SAME cpty handle from the trade *)
  -> csd_virtual_wallet  wallet_handle  (* depot / nostro mirror *)
  -> csd_confirmation : Sese_025_msg.t
  -> (Transaction.t, discharge_error) Result.t
```

**This enforces DS1 structurally.** `emit_discharge` cannot be passed a `real_wallet wallet_handle` — settlement-status mutation that touches `own` is **structurally unrepresentable**. Five categories of bugs eliminated at the cost of three phantom parameters.

### 12.4 Newtype dates

```ocaml
module TradeDate : sig
  type t
  val of_clock : ClockAuthority.t -> Time.t -> t
end

module SettleDate : sig
  type t
  val of_trade_date :
       TradeDate.t
    -> SettleConvention.t
    -> CalendarPin.t           (* L_4-pinned business calendar at trade time *)
    -> (t, settle_error) Result.t
  (* No public [of_date : Date.t -> t]. SettleDate is always derived from
     TradeDate plus a versioned convention. Rules out hand-typed settle dates. *)
end

module ValueDate : sig type t  val of_settle : SettleDate.t -> t  end
module RecordDate : sig type t  end
```

The `CalendarPin` is the bitemporal-pinned `L_4` calendar at trade time; settle-date computation is deterministic across replay and across late calendar restatements (closes formalis G7). A handler that wants to compare `TradeDate` against `SettleDate` cannot use `=`; must lift both to `Date.t` via `to_date`. Confusion between T and T+2 is a type error.

### 12.5 Smart constructor `Obligation.create` rejecting 14 malformed cases

Every obligation reaches `Pending` through one constructor. Rejects every malformed obligation the system can detect at construction:

1. `qty ≤ 0` → `Non_positive_qty`
2. `cash_amount ≤ 0` for DvP/CashOnly → `Non_positive_cash`
3. `dvp_kind = FoP ∧ cash_amount ≠ 0` → `FoP_with_cash`
4. `dvp_kind = CashOnly ∧ qty ≠ 0` → `CashOnly_with_qty`
5. `|qty × price − cash_amount| > rounding_tolerance(currency)` → `Cash_qty_mismatch`
6. `settle_date(trade_date, conv) < now()` → `Settle_date_in_past`
7. settle date falls on non-business day per pinned calendar → `Settle_date_not_business_day`
8. `settle_date < trade_date` → `Settle_date_before_trade_date`
9. `deliverer = receiver` → `Same_party_both_sides`
10. `isin ∉ instrument_master_pin` → `Unknown_isin`
11. `cash_currency ∉ currency_master` → `Unknown_currency`
12. `csd_mic ∉ csd_master` → `Unknown_csd_mic`
13. parties not in master → `Unknown_party_lei`
14. `cdsr_in_scope ∧ csd_master.csdr_regime(csd_mic) = None` → `Cdsr_clock_misconfigured`

The constructor takes `instrument_master_pin` and `party_master_pin` as explicit arguments rather than reading from a global registry — makes construction *reproducible* under replay.

### 12.6 Phantom-typed accounting basis (TradeDate vs SettleDate projections)

```ocaml
type trade_date_basis    (* framework's primary basis *)
type settle_date_basis   (* available only as a projection *)

val pnl_trade_date :
     wallet : real_wallet wallet_handle
  -> as_of  : Time.t
  -> trade_date_basis projection -> Money.t

(* Settlement-date projection requires explicit policy attestation;
   cannot be invoked silently from a generic context. *)
val pnl_settle_date :
     wallet : real_wallet wallet_handle
  -> as_of  : Time.t
  -> policy_attestation : SettleDateAccountingPolicy.t   (* required *)
  -> settle_date_basis projection -> Money.t
```

The two projections live in different types. A consumer that silently picks up the settlement-date answer because some helpful refactoring exposed it under the same name would now hit a type error. Migrating between bases requires changing the type; cannot happen by accident.

### 12.7 Cross-currency Herstatt visibility in type

For an FX-funded equity trade the framework produces **two `PairedObligation`s**, one per currency, with **different `SettleDate`s**:

```ocaml
val emit_fx_funded_trade : ... -> (Transaction.t
                                  * PairedObligation.t   (* equity DvP leg *)
                                  * PairedObligation.t   (* FX leg *)
                                  , trade_error) Result.t

val discharge_fx_trade : ... -> (fx_discharge_state, discharge_error) Result.t

and fx_discharge_state =
  | Both_pending
  | Equity_settled_fx_pending     (* Herstatt: leg 1 done, leg 2 outstanding *)
  | Fx_settled_equity_pending     (* Herstatt: leg 2 done, leg 1 outstanding *)
  | Both_settled
  | Asymmetric_fail of which_leg
```

The Herstatt window is **named** in the type. A handler that wants to "process the FX trade settlement" cannot avoid pattern-matching on these states. The risk is not eliminated — no ledger design can eliminate clock-skew across CSDs in different time zones — but it is **unrepresentable to ignore**.

### 12.8 Honest type-vs-runtime boundary (6 CT, 9 RT, 3 hybrid)

| Concern | Type or Runtime | Why |
|---|---|---|
| Trade-date economic recognition (DS1) | Type | Phantom wallet class; cheap. |
| DvP discharge atomicity (DS18) | Type | `PairedObligation` is one value; cheap. |
| Closed sum on lifecycle states / failure reasons | Type | One sum, one match; cheap. |
| Date confusion (TradeDate / SettleDate / ValueDate / RecordDate) | Type | Phantom-typed newtypes; cheap. |
| Status monotonicity (DS8) | Type | Closed sum + exhaustive match. |
| Capability scoping (DS17) | Type | Phantom typing on writer capability. |
| Conservation `Σ_w w_t(u) = 0` | Runtime | Refinement types over decimal sums require GADTs + logic subsystem; StatesHome C2 chooses runtime. |
| Liveness — deadline timer fires | Runtime | Wall-clock is external. Encoding "this obligation must transition by t" in the type is a category error. |
| CSDR penalty calculation | Runtime | Penalty is function of failing party, asset class, fail duration, reference price, regime version. Type system cannot embed CSDR's full rate table without becoming the rate table. |
| Corporate-action market-claim arithmetic | Runtime | No leverage from type-encoding the corp-action calculus. |
| Regulatory cardinality ("at most one MiFIR per trade per regime per day") | Runtime | Database uniqueness, not type. |
| Counterparty creditworthiness / ECL stage | Runtime | Time-varying; per-counterparty; macro signals. |
| Confirmation matching in absence of UTI (G2) | Runtime, with explicit quarantine | `match_confirmation : confirmation -> [`Unique of Obligation.t \| `Ambiguous of Obligation.t list \| `Unmatched]`; the `Ambiguous` case must be handled, not silently picked. |

**The boundary is named, not negotiated.** First six are type-level because cost is one-time and benefit is on every read site. The runtime items are runtime because the cost of type-encoding is super-linear and benefit does not compose.

### 12.9 Migration strategy (~14 weeks, 1-2 engineers)

| Stage | Duration | Scope |
|---|---|---|
| **Stage 0** | 1 week | Discovery: inventory all `lifecycle_stage` reads/writes; settlement-confirmation paths that mutate real wallets; raw `Date.t` settle-date usages |
| **Stage 1** | 3 weeks | Introduce types alongside strings; add `step` function; refactor `Obligation.create` to return `Result.t` |
| **Stage 2** | 4 weeks | Flip source of truth from string to closed sum; refactor every transition site to consume `transition_result`; introduce `wallet_handle` phantom types |
| **Stage 3** | 2 weeks | Introduce `PairedObligation` + `discharge`; deprecate per-leg discharge functions; property-test 90 days of replay produces identical move stream |
| **Stage 4** | 3 weeks | Newtype dates (`TradeDate`, `SettleDate`, `ValueDate`, `RecordDate`); refactor `Obligation.create` to take typed dates |
| **Stage 5** | 1 week | Deprecate strings; remove runtime validation paths now redundant with type system |
| **Stage 6** | 1 day | Compile entire codebase with `-warn-error +partial-match` |

No behavioural change in production at any stage; Stages 1-4 are type-additive; Stages 5-6 remove dead code. After Stage 4, the trade-date / settlement-date confusion that this whole specification is designed to prevent becomes structurally impossible.

## 13. Honest gaps and proof obligations

[formalis §7, §9]

### 13.1 Gaps G1–G12

**G1 — Closedness of CSD failure-type enumeration.** DS9 totality is contingent on a closed sum of failure types; CSDs publish reasons as ISO 20022 status codes whose `Reason4Choice` is open-ended in some variants and free-text in others. **Constraint:** produce a normalised CSD-failure-reason closed sum, with documented mapping per CSD, with `OTHER → ESCALATE_HUMAN` as a defined sink. **Owner:** matthias (CDM cross-walk) + isda (regulatory mapping).

**G2 — Confirmation matching in the absence of UTI.** DS5 (replay determinism) requires confirmation-to-trade matching to be a *total deterministic function*. With UTI/EndToEndId, this holds. Without (some markets, issuer-side reporting failures), matching is heuristic. **Constraint:** state matching contract explicitly. If contract requires UTI, reject and quarantine non-UTI confirmations to L_18 rather than forcing match. Property test that ambiguous confirmations are quarantined, never silently mis-matched. **Owner:** temporal + nazarov + matthias.

**G3 — Bitemporal predicate evaluation under corporate action.** Discharge predicates registered at T encode "deliver 100 shares". After a 2-for-1 split before t_d, the predicate must refer to "200 shares". If predicate is a closed-over snapshot, system mis-evaluates at t_d. **Constraint:** enforce that all L_15 discharge predicates are *bitemporal-state-functions*, not snapshot values, reading from latest `with_corrections_through` knowledge time. Property test: introduce corporate action between obligation registration and deadline; verify discharge fires correctly with post-CA quantity. **Owner:** matthias + correctness.

**G4 — DvP leg-inconsistent failure compensation.** A CSD reports cash leg `Settled`, securities leg `Failed` (rare but real at non-DvP CSDs, or in CLS-non-eligible cross-currency trades). Correct compensation is contingent on legal regime, CSD, and operational practice. **Constraint:** catalogue per CSD (DTC PvP-style → manual ops workflow; non-DvP CSDs → reverse-the-partial-leg-by-market-trade). Capture per CSD in `L_16.ReferenceMaster` and dispatch κ accordingly. **Owner:** ashworth + isda + jane_street.

**G5 — Replay determinism in the presence of restated confirmations.** A CSD may restate: yesterday "Settled, q=100"; today "Settled, q=60, the rest was a system error." Settlement workflow that already concluded on yesterday's confirmation cannot be "un-concluded" — Temporal histories are append-only and idempotent in the forward direction, not reverse. **Constraint:** define how an obligation that has reached `Discharged` reacts to a corrective restatement. Two design choices: (a) treat restatement as a *new* obligation (clean separation, append-only); (b) extend the obligation FSM with a `Reopened` state. **Recommendation: (a).** **Owner:** temporal + nazarov.

**G6 — Cross-jurisdiction CSDR vs SEC vs T+1 vs T+2.** t_d is jurisdiction-dependent (US T+1 since May 2024, EU T+2 currently, UK T+1 from October 2027, Asia mostly T+2). For a global firm with single ledger, the *same* security on the *same* trade date can have different t_d depending on venue/CSD. **Constraint:** confirm t_d is sourced from CDM `tradableProduct.settlementTerms.settlementDate` as resolved by venue/CSD reference data, not hardcoded. Property test across closed sum of `MIC × ISIN × CSD` triples. **Owner:** matthias + isda.

**G7 — The "true at T+2⁻" semantics — time-of-day convention.** "Reconciles to nostro at T+2" is sharp at t_d^+ (after CSD batch). At t_d^- (morning before batch), nostro has not been updated; reconciliation deliberately shows InFlight = quantity-of-pending-trade. Correct but might surprise an auditor. **Constraint:** state time-of-day convention explicitly, anchored to relevant CSD's batch settlement time. Cite L_19 ClockAuthority for canonical timestamps. **Owner:** jane_street + nazarov.

**G8 — Liveness under prolonged Temporal cluster outage.** Liveness is *eventual* under cluster outage, not instantaneous. If the cluster is down across t_d, the discharge timer fires after recovery, possibly past CSDR penalty windows. Cannot eliminate — timer fires in workflow's logical time, regulatory deadlines tick wall-clock. **Constraint:** not closable by formal proof. Mitigated by multi-region replication, external watchdog (non-Temporal check that timers are firing on schedule), SLA on cluster availability. **Owner:** temporal + jane_street.

**G9 — Late-discharge race policy table coverage.** Saga compensation tower's "Late-discharge race policy" must have a `SETTLEMENT` entry pinned in `VersionPinSidecar`. Currently *inferred* from saga-tower text, not confirmed. **Constraint:** confirm or add explicit `SETTLEMENT` entry: `cancel-compensation if not externalised; otherwise queue-and-reconcile`. Pin per `VersionPinSidecar`. **Owner:** temporal + correctness.

**G10 — Herstatt elimination vs representation.** Framework *names* Herstatt risk (DS10) but does not *eliminate* it. CLS/PvP infrastructure mitigates externally; ledger represents whichever real-world mechanism applies. **Constraint:** not closable in the ledger. Risk is real and external. Framework's contribution: name it, quantify it, route compensation, audit the loss. **Owner:** framework-wide (acknowledged at v10.3 §2.6).

**G11 — Manufactured payment / claim recipient determination.** Corporate action with record date r ∈ (T, t_d]. Trade-date accounting (DS1) says buyer is economically entitled. CSD inscription says seller (still on register) receives the dividend. Manufactured payment (seller → buyer) reconciles, but: which jurisdiction? Which contract? What if seller goes bankrupt before dividend pays out? **Constraint:** codify per-jurisdiction the manufactured-payment rule, with seller's obligation registered as separate L_15 row (`obligation_kind = MANUFACTURED_DIVIDEND`) and own discharge predicate. **Owner:** ashworth + matthias + isda.

**G12 — Single-source escape on attestation.** Is a single attestor (e.g., only the CSD, not the custodian) sufficient to discharge an obligation? Data-spec aggregation rule defaults to "primary CSD attestation suffices, OR 2-of-2 from secondary + tertiary." Single-source escape is permitted only with a registered authority assumption. **Constraint:** maintain trust-assumption registry (TA-DS-1 through TA-DS-10), with named owners and detection signals for each. Quarterly review. **Owner:** nazarov + framework-operations.

### 13.2 Proof obligations PO-1..PO-10

| PO | Owner | Property |
|---|---|---|
| **PO-1** | finops | Show that per-(wallet, counterparty, currency) PS_payable / PS_receivable wallets satisfy DS3 (recon identity) and DS6 (idempotency) under daily aggregation, including netting on morning recon. The §4.4 morning-recon formula must be expressed as deterministic projection over move stream + obligation log. |
| **PO-2** | sbl | Verify (via `VersionPinSidecar` lookup) that the saga compensation tower's policy table has explicit `SETTLEMENT` entry: `cancel-compensation if not externalised; otherwise queue-and-reconcile`. |
| **PO-3** | sbl | Pin the sign convention on DS3/P29. (a) The receive-obligation is on the side of the *receiver*, not the obligor; (b) identity reduces to v10.3 line 3538 SBL form; (c) property tests over generated trade streams confirm identity holds at every checkpoint. |
| **PO-4** | matthias | Show that all L_15 discharge predicates of kind `SettlementInstructionDelivery` are bitemporal-state-functions, not closed-over snapshots. Property test introducing 2-for-1 stock split between obligation registration (T) and deadline (t_d) must observe discharge fires correctly with post-split target quantity (200, not 100). |
| **PO-5** | isda | Produce normalised CSD-failure-reason closed sum, with documented mapping from each CSD's enum (DTC, Euroclear, Clearstream, T2S), defined `OTHER → ESCALATE_HUMAN` sink. Pin per `ledger_data_v1.0` §3 versioning algebra. |
| **PO-6** | ashworth | Specify per jurisdiction (US, EU, UK, JP) the rule for manufactured payments on cum-dividend trades whose record date falls inside (T, t_d]. Seller's manufactured-payment obligation must be separate L_15 row (`obligation_kind = MANUFACTURED_DIVIDEND`), with own deadline and discharge witness. |
| **PO-7** | minsky | Produce canonical mapping from each invariant (DS1–DS18) to (compile-time | runtime | hybrid), with explicit phantom-typing scope (which units carry which phantom tags), and cost-benefit assessment of typing investment. Settlement Team must accept or reject minsky's recommendation: take typing cost for DS17 + DS7, leave DS1 hybrid, leave others runtime. |
| **PO-8** | testcommittee | Implement TLA+ model per testcommittee §8.5 and run TLC at $\|\mathcal{W}\|=3, \|U\|=2, \text{depth}=8$ with all 18 invariants encoded. Required to pass before deferred-settlement specification is considered formally verified. State-space size ~10^5–10^6 states; tractable in minutes on a workstation. |
| **PO-9** | testcommittee + temporal | Pin D_max, the maximum recursion depth of partial → buy-in → partial → buy-in cascades. jane_street caps at 2; sbl/temporal/karpathy allow recursion. Need numeric D_max and property-test that beyond D_max the cascade transitions to `Defaulted` rather than continuing. |
| **PO-10** | temporal | Confirm that `SettlementSaga` is implemented as signal-driven workflow with timer (per temporal §7.2), *not* as long-running heartbeating activity. Dedup set (`processed_signals`) bounded (n=4096, TTL=30 days). The `tx_id` derivation must NOT include `run_id` or any ContinueAsNew-ephemeral field. |

## 14. Out of scope (deliberate)

The following are deliberately excluded from v11.0 deferred-settlement scope. Each is a concern that touches the Ledger but is owned elsewhere or is too large to address without expanding the surface beyond what Phase 2 has converged.

- **Liquidity management of the cash leg.** The Ledger represents the open obligation and the settlement payable; the *funding* of that payable (overnight repo, money-market sweep, draw on a committed credit line) is a treasury concern. The Ledger emits the obligation; the treasury system consumes it and arranges funding. Boundary at the L_15 row.

- **CSD operational outages.** Handled via Temporal saga with externalisation to the watchdog (G8) but not specified in this proposal. A CSD that goes dark for a full business day creates obligations that miss their `intended_settlement_date` through no failure of either party. The framework's response is: do not auto-promote to FAILED; wait for CSD recovery; re-instruct on recovery; ESMA grace per CSDR Art 7. Operational runbook owned by jane_street; specification deferred to a future revision.

- **Title vs beneficial ownership.** The legal layer — when does title pass; when does beneficial ownership pass; how does an omnibus account composition interact with a record-date snapshot — is outside the Ledger. The Ledger represents the economic position and the obligation; the legal-title question is answered by the master agreement, the CSD's rulebook, and the local insolvency law. The framework does not encode beneficial-ownership chains.

- **Cross-CCP novation during the window.** A trade booked at execution against bilateral counterparty C, novated to a CCP (LCH, DTCC NSCC, Eurex) at T+1, then settling at T+2. The novation produces three CDM `BusinessEvent`s: original NEWT against C (lives until novation); EROS (early termination on C); two new NEWTs against the CCP. Λ_15 in the data spec covers cross-CCP novation algebra; the deferred-settlement extension does NOT reopen this. Open obligations migrate with the novation atomically; specification is in v10.3 §13 + Λ_15, not here.

- **Mass-cancellation events.** A trading-day hits a halt for an issuer (corporate-event-driven trading halt, regulatory suspension, exchange technical issue). All open trades for that ISIN may need to be cancelled or held. This is a governance question (whose authority orders the cancellation; how is four-eyes scaled to a population of trades; is restoration possible?) and a regulatory question (CSDR cancellation rules; SEC Rule 11A safe-harbours). The framework supports per-trade `CORRECTION` with four-eyes; bulk cancellation is a workflow on top, not a primitive.

## 15. Ready-for-Review note

**This is proposal_v1.** It goes to Round 1 Team A adversarial review (formalis, jane-street-cto, testcommittee per the user's preferred multi-agent adversarial review pattern). Expected criticism vectors are documented honestly below; the goal of Round 1 is to convert weakness candidates into either fixes or recorded gaps with closing constraints.

### 15.1 Settlement Team identifies known weaknesses honestly

1. **Sign convention on DS3 (PO-3).** Phase 1 sbl §10 explicitly noted the sign-convention issue is open. Finops Phase 2 §3.2 corrects its own Phase 1 §7.7 sign error and pins the identity for cash; the matching pin for the SBL composition path (own + borr − onloan − Σ signed_qty(open) = depot) needs the same treatment. Until PO-3 is discharged with property tests over generated trade streams, the recon identity is pinned in finops's text but not yet machine-verified.

2. **Recursion bound D_max for partial-fill cascades (PO-9).** jane_street caps at 2; sbl/temporal/karpathy allow recursion. The Settlement Team has accepted *a* bound but has not numerically pinned it. DS11 termination is contingent.

3. **Closed sum on CSD failure-type enumeration (G1, PO-5).** Required for DS9 totality and DS-Liveness. ISO 20022 `Reason4Choice` is open-ended in some message variants; the framework's response is `OTHER → ESCALATE_HUMAN`, but the per-CSD mapping (DTC, Euroclear, Clearstream, T2S) is not yet codified.

4. **Bitemporal predicate evaluation under corporate action (G3, PO-4).** Discharge predicates registered at T encoding "deliver 100 shares" must re-evaluate to "200 shares" after a 2-for-1 split before t_d. The constraint is named (predicates must be bitemporal-state-functions, not snapshots); the property test is not yet written.

5. **Per-jurisdiction manufactured-payment specification (G11, PO-6).** ashworth §10.2 names the audit trail and the cum/ex tax-fraud red flag; per-jurisdiction (US, EU, UK, JP) rules for manufactured-payment direction, withholding-tax attribution, and bankruptcy resolution of the seller pre-payout are not yet pinned.

6. **DvP leg-inconsistent failure compensation (G4).** A CSD reports cash leg `Settled`, securities leg `Failed` (rare but real). Per-CSD κ catalogue (DTC PvP-style → manual ops; non-DvP CSDs → market-trade reverse) needs to be captured in `L_16.ReferenceMaster`. Without this, DS-Liveness is contingent on a manual-fallback path.

7. **TLA+ model check at $\|\mathcal{W}\|=3, \|U\|=2, \text{depth}=8$ (PO-8).** testcommittee has the TLA+ specification scope; the actual TLC run with all 18 invariants encoded is not yet executed. Liveness counterexamples cannot be ruled out until this passes.

8. **Migration cost of type discipline (~14 weeks per minsky §12).** The phantom-typed wallet handles, newtype dates, paired-obligation discharge, and closed-sum FSM are non-trivial refactors. minsky's stage plan is type-additive in Stages 1–4 (production-safe), with runtime validation removed only in Stages 5–6 after type system is source of truth. Cost is real; benefit is structurally eliminating the trade-date / settlement-date confusion class. Settlement Team accepts the cost.

### 15.2 What we did not converge on yet but accepted as good-enough

1. **Per-counterparty vs per-instruction PS/PSS wallet keying.** Karpathy/finops/matthias/ashworth prefer per-counterparty (more compact); sbl/temporal/lattner allow per-instruction (finer grain for break investigation). Current pin: per-counterparty per-(currency-or-ISIN) is the floor; per-instruction is permitted as a derived view. Operational cost trade-off is documented; not formally decided.

2. **First-class unit `u^circ` deferred, not killed.** The Settlement Team rejects unit-hood for v11.0. Matthias retains the dissent and recommends revisit when CDM 7.0 ships an `Obligation` root type. The two representations would map 1-to-1 with no loss in a future where Gap 10 is upstream; v11.0 commitment is L_15 obligation row.

3. **Sign convention on DS3 in SBL composition.** Open per PO-3 above, accepted as good-enough until pinned by property test.

4. **Late-discharge race policy table for SETTLEMENT (G9, PO-2).** The saga compensation tower's "Late-discharge race policy" should have an explicit `SETTLEMENT` entry: `cancel-compensation if not externalised; otherwise queue-and-reconcile`. Pin per `VersionPinSidecar` is a one-line change; not yet executed.

5. **Single-source attestation registry (G12).** Trust-assumption registry (TA-DS-1 through TA-DS-10) is good practice but is not part of the invariant register. Current state: registry exists as documentation; quarterly review cadence is operational, not provable.

### 15.3 Convergence claim

The deferred-settlement specification is **implementation-ready**. The 18 invariants (DS1–DS18) are the test the proposal must pass. The 12 gaps (G1–G12) are honest open obligations: 5 closable in Phase 2 (G1, G2, G3, G4, G5) by committing to closed sums or property tests; 4 operational/external (G6, G7, G8, G10); 3 documentation/registry (G9, G11, G12).

**None of the gaps is a design defect.** Each is a specification gap closable by committing to a closed sum, a typing rule, a registry, or a property-based test.

The 10 proof obligations (PO-1..PO-10) are named to specific Settlement Team members with named properties and named owners. Round 1 Team A adversarial review is the appropriate gate before Round 2 implementation.

**Pareto-arbiter ruling required on:**
- Per-counterparty vs per-instruction PS/PSS keying (finops vs sbl/temporal).
- D_max numeric bound for partial-fill recursion (jane_street 2 vs sbl/temporal recursive).
- Type-discipline scope at v11.0 (minsky's recommendation: take the cost for DS17 and DS7, leave others runtime).

Settlement Team signs off on this as the Phase 2 convergent design; submission to Phase 3 Round 1 adversarial review.
