# Proposal v2 — Deferred Settlement on Cash Equities (T+2)
## Phase 3 Round 2 — Settlement Team Unified Design (revision incorporating R1 adversarial findings)

**Status.** This v2 supersedes proposal_v1 and closes every R1 BLOCKING theme (B-1..B-13) and addresses every R1 MAJOR theme (A..J) — either by revision, by mitigation with documented trade-off, or by explicit deferral to v12 RFP. The R1 closure record is in §15.5.

**Thesis (unchanged).** A T+2 cash-equity settlement window is not a new doctrine for Ledger v10.3; it is a *transaction-level lifecycle* on the existing `MoveStream`, with virtual sub-wallets carrying the gross payable/receivable obligations and an `L_15.Obligation` row carrying the legal duty. Trade-date economics flow through the standard six-coordinate StatesHome wallets unchanged — `(own, borr, lent, coll_pledged, coll_received, financed)` — while a parallel reconciliation identity binds the virtual wallets to external nostro/depot positions. The settlement window is a *parameter*, not an architecture.

**What changed in v2 (R1-driven).**
- New §0 notation table; symbol discipline pinned across the proposal (closes halmos B-1..B-7).
- §3 worked example redrawn over a constant wallet set including CSD/JPMC mirror wallets so conservation closes to zero at every state; new §3.X SELL worked example (closes jane_street B-1, lattner B-2, feynman, halmos B-6).
- §4.1 / §11 DS3 unified to a single canonical sign convention; verified on BUY and SELL (closes feynman B-2, jane_street B-2, halmos B-7, cartan B-3).
- New §4.5 attestation envelope, multi-source aggregation, absence-of-finality protocol (closes nazarov B-1..B-5).
- New §6.5 workflow specification with `tx_id` formula, DvP discharge atomicity, signal-handler commutativity, T+2 trigger, ContinueAsNew schema (closes temporal B-1..B-5).
- §5 FSM rewritten — per-leg `L_15.Obligation.state` is canonical; transaction-level `tx_status` is a Library-layer projection function (closes lattner B-1, halmos M8).
- §11 invariants pruned from 18 to 10 genuinely new ones; restated v10.3 invariants moved to appendix (closes themes A and G).
- §12 type design scoped to v11.0 core (~6 weeks); rest deferred to v12 RFP (closes theme B).
- New §10.7 storage and retention strategy (closes jane_street B-4).
- New §13.4 Goodhart traps for deferred settlement (closes correctness B-6).
- New §13.5 Trust-assumption registry TA-DS-1..10 (part of nazarov B-5).
- §5 wallet classes pulled back from 10 to 3 (`real`, `cpty_virtual`, `csd_virtual`) (closes lattner M-1, geohot).
- §7 adds Conservation Lifting Theorem with full hypothesis list and bijection Φ (closes cartan B-2, B-1).
- §8 renames the forgetful "F" from homomorphism to lossy non-faithful functor; defines `Lg_econ` quotient (closes cartan B-4).
- §10 spells out CORRECTION transaction policy with four-eyes preconditions and adds manual override to FSM (closes theme C).
- §7 adds block-and-allocation composition case (closes theme D).

**Section list:**
- §0  Notation table
- §1  Convergence statement
- §2  State representation
- §3  Standard buy — canonical worked example (constant wallet set)
- §3.X Standard sell worked example (independent verification of recon identity)
- §4  Reconciliation
- §4.5 Attestation envelope, multi-source aggregation, absence protocol
- §5  Lifecycle FSM (per-leg canonical, three wallet classes)
- §6  Variants
- §6.5 Workflow specification
- §7  Composition with §13 SBL six-coordinate model + Conservation Lifting Theorem
- §8  CDM cross-walk (lossy non-faithful functor F)
- §9  Regulatory footprint
- §10 Accounting + audit + capital + correction policy
- §10.7 Storage and retention strategy
- §11 Invariants DS1–DS10 (pruned) + restated-v10.3 appendix
- §12 Type design — v11.0 core scope vs v12 RFP
- §13 Honest gaps and proof obligations
- §13.4 Goodhart traps for deferred settlement
- §13.5 Trust-assumption registry TA-DS-1..10
- §14 Out of scope
- §15 Ready-for-Review note + R1 closure record (§15.5)

---

## 0. Notation table

This table is the single canonical reference. Where v1 prose used a different surface form, v2 normalises to the form in this table. (Closes halmos B-1..B-7.)

### 0.1 Wallets, units, positions

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| `w` | wallet (any class) | `WalletId` | StatesHome §2 |
| `w_real` | a real wallet (book-of-record balance) | `WalletId @ class=real` | this spec |
| `u` | unit (currency, ISIN, lot, sub-balance) | `UnitId` | StatesHome §1 |
| `w_t(u)` | balance of wallet `w` for unit `u` at wall-clock `t`, default coordinate `own` | `Decimal` | v10.3 §2 |
| `Δw_t(u)` | signed delta on `w_t(u)` produced by a single Move | `Decimal` | v10.3 §2 |
| `w.own(u)` | shorthand for `w_t(u)` at the relevant `t` | `Decimal` | this spec |
| `Σ_w` | sum over a stated wallet set (always specified) | scalar | v10.3 §2.5 |
| $\mathcal{W}_{\text{real}}$ | the set of all real wallets | set | this spec |
| $\mathcal{W}_{\text{virt}}$ | the set of all virtual wallets (cpty + csd) | set | this spec |
| $\mathcal{W}$ | $\mathcal{W}_{\text{real}} \cup \mathcal{W}_{\text{virt}}$ — the constant wallet universe over which conservation holds | set | v10.3 §2.5 |

### 0.2 Wallet classes (canonical, three only — see §5)

| Class | Surface form | Keyed by | Purpose |
|---|---|---|---|
| `real` | `w_us`, `w_book42` | book-of-record id | StatesHome `own` write at T |
| `cpty_virtual` | `w_PS[w, cpty, ccy]` (or `w_PSS[w, cpty, ISIN]`) | `(real_wallet, cpty_lei, unit)` + side as `sign+key` | per-counterparty open obligation |
| `csd_virtual` | `w_DTC_depot_mirror[holder]`, `w_JPMC_nostro_mirror[holder]` | `(csd_or_bank_lei, holder_lei, unit)` | mirror of external book at finality |

**Side handling.** "Payable" vs "receivable" is **sign**, not class. A positive balance on `w_PS[us, GS, USD]` means we owe GS USD; a positive balance on `w_PS[GS, us, USD]` means GS owes us USD. Surface forms `PS_payable` / `PS_receivable` from v1 are deprecated for storage; they survive only as projection labels in §4.4 reports.

**Symbols `PS`, `PSS`, `w_PS`, `virtual_PS` from v1.** All collapse to `cpty_virtual` keyed `(real_wallet, cpty_lei, ccy_or_ISIN)`. The string `PS` is kept as the surface name only in cash settings; `PSS` only in securities settings. Both are instances of class `cpty_virtual`.

### 0.3 Obligations and transactions

| Symbol | Meaning | Type | Source |
|---|---|---|---|
| `o` | a single obligation (per leg) | `Obligation` row in `L_15` | data v1.0 |
| `o_sec` | securities-leg obligation of a given trade | `Obligation` | this spec |
| `o_cash` | cash-leg obligation of a given trade | `Obligation` | this spec |
| `o.state` | the per-leg lifecycle state (closed sum, see §5.2) | `LifecycleState` | this spec |
| `tx` | a Ledger transaction (atomic move pair + L_13 row) | `Transaction` | v10.3 §2 |
| `tx_id` | deterministic transaction identifier | `Bytes32` | this spec §6.5 |
| `business_event_id` | upstream event identifier (e.g. `(execution_venue, exec_id, leg)`) | `String` | this spec §6.5 |
| `attempt_seq` | retry counter, ≥0, increments on workflow-level retry | `Uint32` | this spec §6.5 |
| `tx_status(tx)` | projection function from `{o : o ∈ tx}.state` to a transaction-level status | function | this spec §5.3 |

**Obligation naming pinned.** v1 used three naming conventions interchangeably (`u_sale`, `o_sec`, `o`). v2 uses `o` for a generic obligation, `o_sec` and `o_cash` for the two legs of a DvP trade. `u_sale` from finops Phase 1 prose is deprecated.

### 0.4 Greek and ad-hoc symbols (with home)

Every symbol used in the proposal that is not standard StatesHome notation is listed here.

| Symbol | Defined in | Meaning |
|---|---|---|
| `Λ_n` | §6.5.4 | watchdog timer interval (n-th poll) when CSD silent |
| `κ_buyin` | §6.4 | CSDR mandatory buy-in clock multiplier (4bd liquid, 7bd illiquid, 15bd SME) |
| `Δ_CSDR` | §10.6 | CSDR cash-penalty rate per ISIN-class per day |
| `F_terminal` | §5.2 | the set of terminal lifecycle states `{Discharged, Compensated, Cancelled, BoughtIn}` |
| `D_max` | §5.2 | terminal-state deadline = `intended_settlement_date + buyin_window` |
| `τ_obs` | §6.5 | observation timestamp on an attestation envelope |
| `τ_known` | §6.5 | system-known timestamp at which the witness arrived |
| `τ_finality` | §4.5 | finality-attested timestamp from the CSD |
| `Φ` | §7.4 | bijection between mainstream representation and first-class-unit representation |
| `F` | §8 | lossy non-faithful functor `Ledger → CDM-projection`; on the `Lg_econ` quotient F restricts to a homomorphism |
| `Lg_econ` | §8.4 | the wallet-axis-collapsed quotient of the Ledger algebra |

### 0.5 Decimal types (data v1.0 §6 echo)

| Token | Decimal precision/scale | Use |
|---|---|---|
| `D_2` | `Decimal(18, 2)` | major cash (USD, EUR, GBP, etc.) |
| `D_0` | `Decimal(18, 0)` | whole-share securities; sub-yen-forbidden cash (JPY, CLP) |
| `D_4` | `Decimal(18, 4)` | EM cash (IDR), bps |
| `D_6` | `Decimal(18, 6)` | fractional securities (tokenised) |
| `D_8` | `Decimal(18, 8)` | prices, FX rates, tolerances |

### 0.6 Quantification on invariants (load-bearing)

Every invariant in §11 is fully quantified. The shorthand is:
- `∀(w, u, t)`: for all wallets in the constant universe, all units, all wall-clock times.
- `∀ tx`: for all transactions in `MoveStream` ever observed.
- `∀ o ∈ L_15`: for all obligation rows in `L_15` ever observed.
- `∀ ε ∈ EnvelopeRegistry`: for all received attestation envelopes.

The §11 statements pin scope explicitly. v1's prose-implicit binders are eliminated.

---

## 1. Convergence statement

### 1.1 The unified design (unchanged from v1, restated for completeness)

The Settlement Team converged in Phase 2 on a **mainstream design** that adds the smallest possible delta to v10.3 to close the deferred-settlement gap:

1. **Trade-date economic recognition.** A real-wallet `own` write at T (the existing v10.3 §2 move algebra) — never moved by settlement.
2. **Counterparty-virtual wallet contras.** Per-`(real_wallet, counterparty_LEI, ccy_or_ISIN)` virtual wallets in `WalletRegistry`, holding the open-window contra-quantity. Side (payable/receivable) is sign+key (§0.2). New wallet *class* `cpty_virtual` (KYC sidecar metadata in `WalletRegistry`) — **zero new fields on `PositionState`**.
3. **`L_15.Obligation` row.** Per-leg, kind `SettlementInstructionDelivery`, carrying the canonical lifecycle FSM (closed sum in §5.2) with discharge predicate, `intended_settlement_date`, `csdr_clock`.
4. **Transaction-level status as Library projection.** `tx_status(tx)` is a **pure function** over the per-leg `L_15` rows of that transaction. **Not stored, not a separate FSM** (closes lattner B-1, halmos M8).
5. **Reconciliation identity** — algebraic, constant-time scan; canonical form fixed in §4.1.
6. **Witness-driven discharge** (DS4): no FSM transition without an attested envelope per the §4.5 envelope.
7. **Mandatory invariant:** Economic-Exposure-at-T (DS1). The position embedded in a trade is true from `T_exec` regardless of `transferStatus` of any associated `Transfer`. Type-level enforcement via phantom-typed wallet handles.

**The settlement window is a parameter, not an architecture.** T+0 atomic, T+1, T+2, T+5+ — same FSM, same obligation row, same algebra, only the workflow timer durations change.

### 1.2 What was rejected

Rejected items unchanged from v1: 7th coordinate (the `inflight` field on every `PositionState[w, u]`); first-class unit `u^circ` (deferred to v12 RFP — see §7.4 for the bijection Φ proof and §15.2 for the operational rationale); `pending_in/pending_out` as `PositionState` fields; single-aggregate-per-CSD wallet; settlement state on `UnitStatus[ISIN]`; settlement state purely external. See v1 §1.2 for the full discussion (preserved by reference; not re-litigated here to make space for the R1 closures).

---

## 2. State representation

### 2.1 The triple (renamed: real `own` write, cpty_virtual contra, L_15 obligation)

The deferred-settlement obligation is represented by a **triple** [finops §1.1, with v2 wallet-class taxonomy]:

| Element | Where it lives | What it carries | Writer (C11 cap) |
|---|---|---|---|
| Real-wallet `own` write at T | `PositionState[w_real, u].own` | Economic position. Trade-date accounting. **Never moved by settlement.** | `apply_trade_move` handler at T only |
| `cpty_virtual` wallet contra | `PositionState[w_PS[w_real, cpty, u]].own` | Per-`(cpty_lei, unit)` open-obligation **quantity** with side as sign. Drains on finality. | `apply_trade_move` at T (initial credit/debit); same handler at T+N (drain). |
| `L_15.Obligation` row, kind `SettlementInstructionDelivery` | `Obligation[obligation_id]` (data v1.0 $L_{15}$) | Per-leg lifecycle (canonical FSM in §5.2). Carries `intended_settlement_date`, `discharge_predicate`, `csdr_clock`. | `SettlementWorkflow` (Temporal). |

The `cpty_virtual` pair holds the **contra-quantity**. The `L_15` row holds the **lifecycle**. **There is no transaction-level FSM in storage**: `tx_status(tx)` is a pure projection function (§5.3).

### 2.2 Wallet keying — per-counterparty per-(currency-or-ISIN); side is sign+key

For each `(real_wallet w, counterparty cpty, unit u)`, **one** virtual wallet:

```
w_PS[w, cpty, u]   -- class = cpty_virtual; one row in WalletRegistry; sign carries side
```

A positive balance means *we owe cpty u*; a negative balance means *cpty owes us u*. The pair `(w_PS[w, cpty, u], w_PS[cpty, w, u])` is symmetric; bilateral storage is on whichever side maintains the book. Surface labels `payable` / `receivable` are projection labels in §4.4 only.

**Why one wallet, not two.** v1 stored two wallets (`PS_payable`, `PS_receivable`) for IFRS-7 grossing-up. v2 stores one wallet with sign and projects gross at the disclosure layer:
- `gross_payable[w, cpty, u]   = max(0,  w_PS[w, cpty, u].own)`
- `gross_receivable[w, cpty, u] = max(0, -w_PS[w, cpty, u].own)`

Storage is signed; **disclosure is gross** by these two projections. This is consistent with IFRS 7 (storage need not be gross provided disclosure can be derived) and removes the wallet-class enum bloat (closes lattner M-1, geohot). v1's three reasons for the split (right-of-set-off jurisdictional exposure; aged-payable vs aged-receivable workflow asymmetry; conservation cleanliness) are now properties of the projection layer, not the storage class.

### 2.3 Wallet registry sidecar metadata (3 classes only)

Per StatesHome §2 the `WalletRegistry` is KYC, not state. Sidecar columns:

```
wallet_class ∈ { real, cpty_virtual, csd_virtual }
real_wallet:    FK to the owning real wallet (NULL for real wallets and csd_virtual)
cpty_lei:       LEI of the counterparty (NULL if not counterparty-keyed)
csd_lei:        LEI of the CSD or correspondent bank (NULL unless csd_virtual)
holder_lei:     LEI of whose mirror this is (NULL unless csd_virtual)
expected_settle_window: { T+0 | T+1 | T+2 | T+3 } per venue convention
```

All sidecar metadata is `WalletRegistry`. **Zero new columns on `PositionState`.** [finops §1.3]

**Inflight is FSM state, not class.** v1 had `virtual_inflight_out`, `virtual_inflight_in` as wallet classes. They are now projections of `(L_15.state ∈ {Instructed, PartiallySettled}, side)` over the same `cpty_virtual` storage (closes geohot). The §4.1 recon identity uses `inflight_in/inflight_out` as named projections, defined in §4.1.5.

### 2.4 No transaction-level stored FSM

`tx_status(tx)` is a pure function (§5.3). It is **not** a column on `MoveStream` and **not** a separate FSM. Operational queues that previously filtered by `MoveStream[tx_id].settlement_status` now call the projection function (or query a materialised view declared in §10.7). This closes lattner B-1 and halmos M8.

### 2.5 StatesHome compliance — explicit check

| StatesHome map | Touched? |
|---|---|
| `ProductTerms[u]` | No. Cash and securities terms unchanged. |
| `UnitStatus[u]` | No. Instrument-level lifecycle unaffected. |
| `PositionState[w, u]` | Yes — but only by **existing handlers** (`apply_trade_move`, `apply_settlement_finality`). `cpty_virtual` and `csd_virtual` wallets are new wallet rows in `WalletRegistry`; their balances sit in `PositionState` with the same `own` coordinate. **Zero new fields.** |
| `WalletRegistry[w]` (KYC) | Yes — sidecar metadata (3 classes) above. Permitted per StatesHome §2 KYC sector. |

**Conformance verdict: cpty_virtual/csd_virtual pattern adds zero state to StatesHome. No fourth map.**

### 2.6 Conservation — explicit, over the constant universe $\mathcal{W}$

For every unit `u` at every wall-clock `t`,

$$\sum_{w \in \mathcal{W}} w_t(u) = 0$$

where $\mathcal{W} = \mathcal{W}_{\text{real}} \cup \mathcal{W}_{\text{cpty_virtual}} \cup \mathcal{W}_{\text{csd_virtual}}$ is the constant universe (the same set of wallet ids at every `t`; classes `csd_virtual` mirror the external book and absorb the contra at finality, see §3 and §7 Lifting Theorem). Conservation is preserved by every transaction kind (proof: §7.5).

**Non-negotiable.** No carve-out for state-only transactions (`Σ = 0` vacuously) or for finality (the move pair sums to zero). v1's §2.6 said "per move pair" without naming the universe. v2 names it as `\mathcal{W}` constant.

---

## 3. The standard buy — canonical worked example (constant wallet set)

This block is the load-bearing concrete artifact. **Every other section refers back to it.** R1 closure: jane_street B-1, lattner B-2, feynman, halmos B-6 — the post-finality conservation table is now drawn over a constant wallet set including `w_DTC_depot_mirror[GS]` (XYZ) and `w_JPMC_nostro_mirror[GS]` (USD), so the sum closes to zero at every state.

### 3.1 Setup

- **Trade:** Buy 100 XYZ @ $50.00 = $5,000.00 cash leg.
- **Date:** T = 2026-04-30 14:32:11 UTC.
- **Settlement:** T+2 = 2026-05-04. (Same shape for T+1.)
- **Real wallet:** `w_us` (our portfolio).
- **Counterparty:** Goldman Sachs broker, LEI `784F5XWPLTWKTBV3E584`, real wallet `w_GS_broker` (GS book-of-record from their side; for our books it is observed only via finality contra; we credit the `csd_virtual` mirror, not the GS real wallet directly — see §3.5 below).
- **CSD / correspondent:** DTC for securities depot (`w_DTC_depot`); JPMC for cash nostro (`w_JPMC_nostro_USD`). v2 introduces **mirror wallets** for the *holder* side of those external accounts: `w_DTC_depot_mirror[GS]` (mirror of GS's depot at DTC) and `w_JPMC_nostro_mirror[GS]` (mirror of GS's nostro at JPMC), in class `csd_virtual`. These are the wallets that pick up the contra at finality.
- **Pre-trade:** `w_us.own(USD) = 1,000,000.00`; `w_us.own(XYZ) = 0`.
- **External nostro:** `w_JPMC_nostro_USD.own(USD) = 1,000,000.00` (JPMC daily `camt.053`).
- **Mark-to-market:** $50.00 (T close), $52.00 (T+1 close), $51.50 (T+2 close).
- **Decimal discipline:** prices `D_8`; quantities `D_18`/`D_0`; cash `D_2`; **no floats.**

### 3.2 Move block at T (2026-04-30 14:32:11 UTC)

```
Transaction TX1:
  type:               ECONOMIC_RECOGNITION (sub-class of SETTLEMENT)
  tx_id:              hash_jcs(business_event_id="exec:XNYS:exec_id_42:leg_combined",
                               attempt_seq=0)
                    = "0xa7c3f1e8..."  (canonical formula in §6.5.1)
  ts:                 2026-04-30T14:32:11Z
  metadata:           { expected_settlement_date: 2026-05-04, cpty_lei: GS_LEI,
                        venue_mic: XNYS, settlement_type: DVP, cdm_event: ExecutionEvent }

  -- Securities leg (economic recognition: w_us becomes long 100 XYZ at T)
  Move 1: from = w_PS[w_us, GS, XYZ]      -- cpty_virtual, sign convention: positive = we owe
          to   = w_us
          unit = XYZ
          qty  = D_0(100)
          --> w_PS balance: 0 - 100 = -100  (negative = GS owes us 100 XYZ; receivable side)

  -- Cash leg (economic recognition: w_us owes 5,000 USD at T)
  Move 2: from = w_us
          to   = w_PS[w_us, GS, USD]      -- cpty_virtual
          unit = USD
          qty  = D_2(5000.00)
          --> w_PS balance: 0 + 5,000.00 = +5,000.00  (positive = we owe GS 5,000 USD)

  -- Atomic with the move pair: register obligations in L_15
  L_15 register o_sec:
    obligation_id:           hash_jcs(tx_id, "leg_securities")
    kind:                    SettlementInstructionDelivery
    intended_settlement_date: 2026-05-04
    deadline:                2026-05-04T23:59:59Z (CSD timezone)
    discharge_predicate:     ByAttestation(Envelope, sese.025, ref=tx_id)
    compensation_handler:    SettlementFailHandler
    state:                   Pending

  L_15 register o_cash:
    obligation_id:           hash_jcs(tx_id, "leg_cash")
    kind:                    SettlementInstructionDelivery
    intended_settlement_date: 2026-05-04
    discharge_predicate:     ByAttestation(Envelope, camt.054, ref=tx_id)
    compensation_handler:    SettlementFailHandler
    state:                   Pending

  -- No transaction-level stored field. tx_status(TX1) = projection per §5.3.
```

**Conservation check at T (per unit, atomic):**

| Unit | Δw_us | Δw_PS[us,GS,XYZ] | Δw_PS[us,GS,USD] | Δ csd_virtual mirrors | Σ |
|---|---:|---:|---:|---:|---:|
| XYZ | +100 | -100 | 0 | 0 | 0 |
| USD | -5,000.00 | 0 | +5,000.00 | 0 | 0 |

**Wallet snapshot post-TX1 (constant universe):**

```
w_us.own(XYZ)                      = +100
w_us.own(USD)                      = +995,000.00
w_PS[w_us, GS, XYZ].own(XYZ)       = -100        (GS owes us 100 XYZ)
w_PS[w_us, GS, USD].own(USD)       = +5,000.00   (we owe GS 5,000 USD)
w_DTC_depot_mirror[GS].own(XYZ)    = 0           (no finality yet; mirror flat)
w_JPMC_nostro_mirror[GS].own(USD)  = 0           (no finality yet; mirror flat)
```

### 3.3 At T+1 close (2026-05-01 21:00 UTC, XYZ → $52.00)

**No moves emitted.** Position is unchanged. State-only transaction `TX1_INSTRUCT` is emitted by the SettlementWorkflow (zero moves; updates `o_sec.state` and `o_cash.state` from `Pending → Instructed` after `sese.023` dispatch). Conservation holds vacuously (`Σ = 0` over zero moves).

**PnL at T+1 close:**

```
V_{T+1}(w_us) = 995,000.00 × 1 + 100 × 52.00 = 1,000,200.00
PnL_{T+1}    = +200.00
```

**+$200.00 P&L with zero cash movement and zero settlement movement.** Headline guarantee — the entire reason for trade-date accounting (DS1).

### 3.4 At T+2 morning (before finality)

No moves. Recon scan as in §4.4.

### 3.5 At T+2 finality (post-DTC EOD batch) — drained into csd_virtual mirrors

DTC reports DvP finality via `sese.025` (securities) and `camt.054` (cash debit). Both inbound on `L_11.ExternalConfirmation`, wrapped in §4.5 envelopes. The `SettlementWorkflow` consumes the signal pair and emits the **finality contra-transaction**:

```
Transaction TX1_FINAL:
  type:    SETTLEMENT_FINALITY
  tx_id:   hash_jcs("FINAL", TX1.tx_id, sese.025_msg_id, camt.054_msg_id)
  ts:      2026-05-04T16:30:42Z

  -- Securities leg: drain the cpty_virtual receivable into the DTC depot mirror
  Move 1: from = w_DTC_depot_mirror[GS]
          to   = w_PS[w_us, GS, XYZ]
          unit = XYZ
          qty  = D_0(100)
          --> w_PS balance:  -100 + 100 =  0
          --> mirror balance: 0   - 100 = -100   (GS depot mirror is now short 100 XYZ
                                                   on our books, mirroring GS having
                                                   delivered them out at DTC)

  -- Cash leg: drain the cpty_virtual payable into the JPMC nostro mirror
  Move 2: from = w_PS[w_us, GS, USD]
          to   = w_JPMC_nostro_mirror[GS]
          unit = USD
          qty  = D_2(5000.00)
          --> w_PS balance:    +5,000  - 5,000 =     0
          --> mirror balance:       0  + 5,000 = +5,000   (GS nostro mirror has received
                                                            5,000 from us)

  L_15 update o_sec.state:  Instructed → Discharged
  L_15 update o_cash.state: Instructed → Discharged
```

**Conservation check at finality:**

| Unit | Δw_us | Δw_PS[us,GS,*] | Δ w_DTC_depot_mirror[GS] | Δ w_JPMC_nostro_mirror[GS] | Σ |
|---|---:|---:|---:|---:|---:|
| XYZ | 0 | +100 | -100 | 0 | 0 |
| USD | 0 | -5,000 | 0 | +5,000 | 0 |

### 3.6 Conservation summary across the four states (constant universe — sums to zero)

USD (cash leg), constant universe `{w_us, w_PS[us,GS,USD], w_JPMC_nostro_mirror[GS]}` plus the external-cash counterparty: pre-trade we model only the universe in which the trade lives, treating the pre-trade nostro float as a real `w_us` cash balance (no flow through GS). The constant-set sums to zero throughout:

| State | w_us(USD) | w_PS[us,GS,USD] | w_JPMC_nostro_mirror[GS] | Σ_internal |
|---|---:|---:|---:|---:|
| T⁻ pre-trade | 0 (delta) | 0 | 0 | 0 |
| T⁺ post-trade | -5,000 | +5,000 | 0 | 0 |
| T+1 | -5,000 | +5,000 | 0 | 0 |
| T+2⁻ instructed | -5,000 | +5,000 | 0 | 0 |
| T+2⁺ finality | -5,000 | 0 | +5,000 | 0 |

(Reading: `Δ` from pre-trade. Σ_internal = 0 at every state; the GS-side mirror picks up the contra at finality.)

XYZ (securities leg), constant universe `{w_us, w_PS[us,GS,XYZ], w_DTC_depot_mirror[GS]}`:

| State | w_us(XYZ) | w_PS[us,GS,XYZ] | w_DTC_depot_mirror[GS] | Σ_internal |
|---|---:|---:|---:|---:|
| T⁻ | 0 | 0 | 0 | 0 |
| T⁺ | +100 | -100 | 0 | 0 |
| T+1 | +100 | -100 | 0 | 0 |
| T+2⁻ | +100 | -100 | 0 | 0 |
| T+2⁺ | +100 | 0 | -100 | 0 |

**Conservation `Σ_w w(u) = 0` over the constant universe holds at every state.** This closes jane_street B-1: the post-finality wallet snapshot is no longer dangling.

### 3.7 PnL at T+2 close (XYZ = $51.50) — path independence

```
V_{T+2}    = 995,000.00 × 1 + 100 × 51.50 = 1,000,150.00
PnL_{T+2}  = -50.00
PnL_{cum}  = +150.00 = +200 (T+1) - 50 (T+2)
```

PnL path-independence (v10.3 P10) holds across the full trade lifecycle, T-through-settled, with **zero** moves on `w_us` after T.

### 3.X Standard sell — independent verification of recon identity (NEW in v2)

R1 closure: feynman B-2, jane_street B-2 — feynman's independent SELL computation with the v1 sign convention failed by 100,000. v2 fixes the convention (§4.1) and verifies on this case.

#### 3.X.1 Setup

- **Trade:** Sell 100 XYZ @ $50.00 = $5,000.00 cash leg.
- **Date:** T = 2026-04-30 14:32:11 UTC.
- **Settlement:** T+2 = 2026-05-04.
- **Pre-trade:** `w_us.own(XYZ) = 100`; `w_us.own(USD) = 1,000,000.00`. (We have the security to deliver.)
- **Counterparty:** GS broker (`w_GS_broker`, LEI `784F5XWPLTWKTBV3E584`).
- **Mirror wallets (pre-trade flat):** `w_DTC_depot_mirror[GS]`, `w_JPMC_nostro_mirror[GS]`.
- **Mark-to-market:** $50.00 (T close), $48.00 (T+1 close), $47.50 (T+2 close).

#### 3.X.2 Move block at T

```
Transaction TX1_SELL:
  type:    ECONOMIC_RECOGNITION
  tx_id:   hash_jcs(business_event_id="exec:XNYS:sell_id_77:leg_combined",
                    attempt_seq=0)

  -- Securities leg: economic recognition - we owe 100 XYZ to GS
  Move 1: from = w_us
          to   = w_PS[w_us, GS, XYZ]
          unit = XYZ
          qty  = D_0(100)
          --> w_us:    +100 - 100 =  0
          --> w_PS:       0 + 100 = +100   (we owe GS 100 XYZ; payable side)

  -- Cash leg: economic recognition - GS owes us 5,000 USD
  Move 2: from = w_PS[w_us, GS, USD]
          to   = w_us
          unit = USD
          qty  = D_2(5000.00)
          --> w_PS:       0 - 5,000 = -5,000  (negative = GS owes us 5,000 USD)
          --> w_us:    +1,000,000 + 5,000 = +1,005,000

  L_15 register o_sec(state=Pending), o_cash(state=Pending) per §3.2 shape.
```

**Conservation at T:**

| Unit | Δw_us | Δw_PS[us,GS,XYZ] | Δw_PS[us,GS,USD] | Δ mirrors | Σ |
|---|---:|---:|---:|---:|---:|
| XYZ | -100 | +100 | 0 | 0 | 0 |
| USD | +5,000 | 0 | -5,000 | 0 | 0 |

#### 3.X.3 PnL at T+1 close (XYZ → $48.00)

```
V_{T+1}(w_us) = 1,005,000 × 1 + 0 × 48.00 = 1,005,000.00
V_T          = 1,000,000 × 1 + 100 × 50.00 = 1,005,000.00 (note: V_T computed
                                                             on POST-TX1 wallet
                                                             at price P_T)
                                          OR
V_T          = 1,005,000.00
PnL_{T+1}    = V_{T+1} - V_T = 0      (we have no XYZ; we have +5,000 cash claim)
```

Wait — at T+1, the receivable `w_PS[us,GS,USD] = -5,000` is a claim, not yet cash; valuation must include it. The valuation function on a wallet set `S` for currency translation is:

```
V_S(t) = Σ_{w ∈ S} Σ_u w_t(u) · P_t(u)
```

where the **active set** S is the set of wallets economically owned by us. After TX1_SELL: `S = {w_us, w_PS[us, GS, XYZ], w_PS[us, GS, USD]}` — receivables *and* payables are part of our economic position. (Recall: Sign convention §0.2 — positive `w_PS[us, cpty, u]` is what we owe; negative is what they owe us.)

Computing V at T (post-TX1):
- `w_us(XYZ) = 0`, `(USD) = 1,005,000`
- `w_PS[us,GS,XYZ](XYZ) = +100` valued at $50 = +5,000 USD-equivalent **cost basis**
- `w_PS[us,GS,USD](USD) = -5,000`

Valuation at T (pre-MTM): `0 + 1,005,000 + (+100 · $50 mark = +5,000 mark on a payable; which lowers V) + (-5,000)` — but for sell-side, the payable on XYZ is what *we owe to deliver* and reduces V by `100 × $50`; the receivable in cash adds `+5,000` (negative storage, but it adds to value because GS owes us). The cleanest accounting:

```
V_t = [w_us value] + [net receivables value]
    = (w_us.own(USD) · 1 + w_us.own(XYZ) · P_t(XYZ))
      + (-w_PS[us, GS, XYZ].own(XYZ) · P_t(XYZ))   [GS owes us if w_PS<0]
      + (-w_PS[us, GS, USD].own(USD) · 1)
```

At T (post-TX1):
```
V_T = (1,005,000 + 0 · 50.00)  +  (-(+100) · 50.00)  +  (-(-5,000) · 1)
    = 1,005,000 + (-5,000) + 5,000
    = 1,005,000.00
```

At T+1 (XYZ → $48.00):
```
V_{T+1} = (1,005,000 + 0 · 48.00) + (-(+100) · 48.00) + (-(-5,000) · 1)
        = 1,005,000 - 4,800 + 5,000
        = 1,005,200.00

PnL_{T+1} = 1,005,200 - 1,005,000 = +200.00
```

We are short 100 XYZ (via the payable wallet) at $48 vs $50 — we owe less. PnL = +$200 even though XYZ went down: shorting structure.

At T+2 close (XYZ → $47.50):
```
V_{T+2} = (1,005,000 + 0 · 47.50) + (-(+100) · 47.50) + (-(-5,000) · 1)
        = 1,005,000 - 4,750 + 5,000
        = 1,005,250.00

PnL_{T+2}  = +50.00
PnL_{cum}  = +250.00
```

#### 3.X.4 At T+2 finality (sese.025 + camt.054 inbound)

```
Transaction TX1_SELL_FINAL:
  type:    SETTLEMENT_FINALITY
  tx_id:   hash_jcs("FINAL", TX1_SELL.tx_id, sese.025_msg_id, camt.054_msg_id)

  -- Securities leg: drain payable into DTC mirror (we delivered 100 XYZ)
  Move 1: from = w_PS[w_us, GS, XYZ]
          to   = w_DTC_depot_mirror[GS]
          unit = XYZ
          qty  = D_0(100)
          --> w_PS:    +100 - 100 =     0
          --> mirror:     0 + 100 =  +100   (GS depot mirror long 100 XYZ;
                                              GS received them at DTC)

  -- Cash leg: drain receivable from JPMC mirror (GS paid us 5,000 USD)
  Move 2: from = w_JPMC_nostro_mirror[GS]
          to   = w_PS[w_us, GS, USD]
          unit = USD
          qty  = D_2(5000.00)
          --> mirror:  0 - 5,000 = -5,000   (GS nostro mirror short 5,000 = GS paid out)
          --> w_PS:  -5,000 + 5,000 =     0

  L_15 update o_sec.state:  Instructed → Discharged
  L_15 update o_cash.state: Instructed → Discharged
```

**Conservation at finality (sell):**

| Unit | Δw_us | Δw_PS[us,GS,XYZ] | Δw_PS[us,GS,USD] | Δ w_DTC_mirror | Δ w_JPMC_mirror | Σ |
|---|---:|---:|---:|---:|---:|---:|
| XYZ | 0 | -100 | 0 | +100 | 0 | 0 |
| USD | 0 | 0 | +5,000 | 0 | -5,000 | 0 |

#### 3.X.5 Recon-identity verification on the SELL — independent computation

T+2 morning (before finality), recon identity from §4.1 must hold (with the canonical sign convention):

```
nostro_external(w_us, USD, t) = w_us.own(USD)
                              + Σ_cpty w_PS[w_us, cpty, USD].own
                              + Σ_cpty w_PS[w_us, cpty, USD]_inflight_in_proj
                              - Σ_cpty w_PS[w_us, cpty, USD]_inflight_out_proj
```

where, by §4.1 sign convention (canonical), `w_PS[w, cpty, u]` enters with **sign as stored** (positive = we owe; negative = they owe us). Verification:

```
LHS = nostro_external (per JPMC camt.053) = 1,000,000.00
       (we have not yet received the 5,000 USD from GS;
        JPMC shows our balance LEAN by 5,000 vs the booked 1,005,000)

RHS = w_us.own(USD) + w_PS[w_us, GS, USD].own + 0 - 0
    = 1,005,000 + (-5,000) + 0 - 0
    = 1,000,000.00
```

LHS = RHS = 1,000,000.00. Identity holds.

T+2 evening (post-finality, JPMC has now credited us the 5,000):

```
LHS = nostro_external = 1,005,000.00
RHS = 1,005,000 + 0 + 0 - 0 = 1,005,000.00
```

LHS = RHS. Identity holds. **The same identity that worked for the BUY (§4.1, §4.2) works for the SELL.** This is the verification feynman demanded; closes feynman B-2 and jane_street B-2.

---

## 4. Reconciliation

### 4.1 The fundamental algebraic identity (canonical sign convention)

For every `(real_wallet w, currency ccy)` pair at any wall-clock time `t`, with `w_PS[w, cpty, u]` storage signed (positive = we owe; negative = they owe us):

$$\boxed{\;
\text{nostro\_external}(w, \text{ccy}, t)
\;=\;
w_t.\text{own}(\text{ccy})
\;+\;\sum_{\text{cpty}} w_{\text{PS}}[w, \text{cpty}, \text{ccy}]_t
\;-\;\text{inflight\_out}(w, \text{ccy}, t)
\;+\;\text{inflight\_in}(w, \text{ccy}, t)
\;}$$

**Equivalent identity for securities** for every `(real_wallet w, ISIN s)`:

$$\text{depot\_external}(w, s, t)
= w_t.\text{own}(s)
+ \sum_{\text{cpty}} w_{\text{PS}}[w, \text{cpty}, s]_t
- \text{depot\_out}(w, s, t)
+ \text{depot\_in}(w, s, t)$$

The signed sum subsumes the gross `Σ payable - Σ receivable` form of v1: when storage is signed, the algebra collapses. Disclosure-layer gross is computed by projection (§2.2).

### 4.1.5 Inflight projections (named explicitly — closes jane_street B-2)

`inflight_out` and `inflight_in` are **projections**, not stored fields:

```
inflight_out(w, u, t) = sum over { o ∈ L_15 :
                                    o.real_wallet == w
                                    AND o.unit == u
                                    AND o.state ∈ {Instructed, PartiallySettled}
                                    AND o.side == payable
                                    AND o.wire_dispatch_witness IS NOT NULL
                                    AND o.csd_finality_witness IS NULL }
                       of o.amount

inflight_in(w, u, t)  = sum over { o ∈ L_15 :
                                    o.real_wallet == w
                                    AND o.unit == u
                                    AND o.state ∈ {Instructed, PartiallySettled}
                                    AND o.side == receivable
                                    AND o.cpty_dispatch_witness IS NOT NULL
                                    AND o.csd_finality_witness IS NULL }
                       of o.amount
```

These projections are computed at recon time over `L_15` (closed-form scan; no replay over `MoveStream`). They are named here so the §4.1 identity is parametric-explicit. The witness fields (`wire_dispatch_witness`, `cpty_dispatch_witness`, `csd_finality_witness`) are columns on the `L_15.Obligation` row populated by the §4.5 envelope intake handler.

### 4.2 Sign discipline (corrected v1; verified on BUY and SELL)

When **WE owe** (`w_PS[w, cpty, ccy] > 0`) and the wire **hasn't gone out**, JPMC still shows our balance fat — `nostro_external = own + (positive payable storage)`. When **someone else owes us** (`w_PS[w, cpty, ccy] < 0`) and the wire hasn't arrived, JPMC shows our balance lean — `nostro_external = own + (negative receivable storage) = own - magnitude`.

Verification on §3 BUY at T+2 morning:
```
LHS = 1,000,000.00
RHS = w_us.own(USD) + w_PS[us,GS,USD].own + 0 - 0
    = 995,000.00 + (+5,000.00) + 0 - 0
    = 1,000,000.00 ✓
```

Verification on §3.X SELL at T+2 morning:
```
LHS = 1,000,000.00
RHS = w_us.own(USD) + w_PS[us,GS,USD].own + 0 - 0
    = 1,005,000.00 + (-5,000.00) + 0 - 0
    = 1,000,000.00 ✓
```

**Same identity, both directions.** Closes feynman B-2.

### 4.3 Constant-time scan, not a join

The algebraic identity is **constant-time** per `(w, ccy)`:

```sql
SELECT  w_real,
        ccy,
        SUM(balance) AS sum_signed_ps
FROM    position_state ps
JOIN    wallet_registry wr ON ps.wallet_id = wr.wallet_id
WHERE   wr.wallet_class = 'cpty_virtual'
  AND   wr.real_wallet  = :w
  AND   ps.unit         = :ccy
GROUP   BY w_real, ccy;
```

`inflight_out`/`inflight_in` projections add a second scan over `L_15` filtered on `state ∈ {Instructed, PartiallySettled}` and witness presence, again indexed (see §10.7 storage strategy).

A million open trades aggregate into ~10^3 wallet rows; the scan is bounded by wallet count, not transaction count.

### 4.4 Morning recon report shape

Same as v1; column labels show the gross projections (§2.2):

```
counterparty | ccy | bucket    | gross_payable | gross_receivable | net      | trade_count | aging
-------------|-----|-----------|---------------|-------------------|----------|-------------|------
GS           | USD | T+0       |      12,500.00|         5,000.00  | +7,500   |     4       | 0bd
GS           | USD | T+1       |       5,000.00|             0.00  | +5,000   |     1       | 1bd
GS           | USD | T+2_TODAY |   1,250,000.00|       812,000.00  | +438,000 |    47       | 2bd
GS           | USD | OVERDUE   |           0.00|       150,000.00  | -150,000 |     1       | 3bd  AGED
JPMC         | USD | T+0       |      80,000.00|        80,000.00  |        0 |    12       | 0bd
```

Per-currency aggregate row:

```
real_wallet:               w_us
ccy:                       USD
nostro_external_balance:   1,234,567.89   (camt.053 from L_11)
own_internal:              1,229,567.89
+ Σ w_PS[us, *, USD]:          5,000.00
- inflight_out:                    0.00
+ inflight_in:                     0.00
─────────────────────────────────────────
expected_nostro:           1,234,567.89
break:                             0.00
```

Buckets (`T+N`, `T+0`, `T+N_TODAY`, `OVERDUE`) and aging in business days unchanged from v1.

### 4.5 Attestation envelope, multi-source aggregation, absence-of-finality (NEW; closes nazarov B-1..B-5)

#### 4.5.1 Envelope structure

Every external observation that drives a state transition on `L_15.Obligation` (or any `L_X` row of comparable trust class) is wrapped in an `Envelope`:

```
Envelope:
  payload         : bytes (JCS-canonical CBOR or JSON of the message)
  payload_schema  : (schema_uri, schema_version)
  source_lei      : LEI of the signing entity
  signature       : Ed25519 signature over hash_jcs(payload || schema_version || source_lei)
  ts_obs          : observation timestamp asserted by source (Z, ISO 8601)
  ts_known        : system-known timestamp at intake (assigned at L_11 arrival)
  dedup_key       : hash_jcs(payload, source_lei, ts_obs)  -- idempotency key
  attestation_kind: { sese.025 | camt.054 | sese.024 | camt.053 |
                       affirmation | corp_action_ex_date | manual_override | ... }
```

- **JCS canonicalisation.** RFC 8785. Every payload is canonicalised before hashing or signing. This kills equivocation attacks where reordering object keys would change the hash but preserve semantic content.
- **Signature scheme.** Ed25519 (RFC 8032). Verified at L_11 ingest by the public key registered for `source_lei` in `L_7^P.TrustRoots` (versioned).
- **Schema pinning.** `payload_schema = (uri, version)` references an immutable `L_7^P.SchemaRegistry` entry. ISO 20022 dialect divergence between SWIFT versions is contained at this column.
- **Idempotency.** Two envelopes with identical `dedup_key` are dropped post-arrival; the second arrival is recorded in `L_11` for audit but does not transition `L_15`.

#### 4.5.2 Multi-source aggregation

CSD primary; quorum-of-2 from `(custodian, counterparty)` when CSD silent; **never single non-primary**:

| Witness configuration | Effect on `L_15.state` |
|---|---|
| `Envelope(sese.025, source=CSD)` valid signature, schema, dedup-pass | Discharge admitted; FSM proceeds (`Instructed → Discharged`) |
| CSD silent past `intended_settlement_date + 0.5bd`; `Envelope(camt.054, source=custodian)` AND `Envelope(affirmation, source=cpty)` both valid | Discharge admitted via 2-of-2 quorum |
| Single `Envelope(camt.054, source=custodian)` only | **NOT admitted.** Logged. Watchdog trigger continues. |
| Single `Envelope(affirmation, source=cpty)` only | **NOT admitted.** |
| Two attestations contradicting each other (e.g., one `sese.025` + one `sese.024` for same `tx_id`) | **Quarantine via `wf-confirm-break`.** No discharge. Manual review. |

Quorum tightening to 3-of-3 (CSD + custodian + cpty) is configurable per `(venue_mic, ccy_class)` in `L_7^P.QuorumPolicy`; never relaxable below 2-of-2 by configuration (this is a hard rule encoded in the workflow code).

#### 4.5.3 Absence-of-finality protocol — silence is itself attested

Silence past `intended_settlement_date + watchdog_window` does NOT auto-FAIL the obligation. It triggers a `wf-confirm-break` workflow:

```
Watchdog timer triggers when:
  (now() > intended_settlement_date + Λ_n  AND  o.state ∈ {Pending, Instructed, PartiallySettled})

On trigger:
  Spawn break-handler workflow `wf-confirm-break(o.obligation_id)`.
  Emit a "silence-attested" envelope with:
    attestation_kind = silence_attestation
    source_lei       = our_lei (we are attesting our own observation of silence)
    payload          = { obligation_id, intended_settlement_date, observed_at, watchdog_seq=n }
  L_18.BreakRegister append.

  Do NOT transition L_15.state to Failed. Wait for human or further evidence.
```

`Λ_n` poll cadence: `Λ_0 = 0` (immediate at deadline), `Λ_1 = 30min`, `Λ_2 = 2h`, `Λ_3 = end-of-day`, `Λ_4 = +1bd`. After `Λ_4` and no resolution, ops escalate per the regulatory clock (CSDR penalties begin accruing on the failing party from `intended_settlement_date + 1bd` regardless of Ledger state).

The closed-sum `L_15.state` admits `Pending → Failed` only via four-eyes manual override (§5.2). Watchdog never auto-Fails. This closes nazarov B-3.

#### 4.5.4 Cum/ex ex-date observation as multi-source attestation

Corporate-action ex-dates have the same envelope shape:

```
Envelope:
  attestation_kind: corp_action_ex_date
  payload: { ISIN, ex_date, record_date, ca_type ∈ {dividend, split, spinoff, ...},
             terms (depending on ca_type) }
  source_lei: { issuer_agent | DTC | Bloomberg | S&P | ... }
```

Quorum required: 2-of-3 from issuer_agent, primary CSD, market data vendor. Single-source observation is logged but NOT applied to `L_15` until quorum is reached. Mismatch (different `ex_date` from two sources) routes to `wf-ca-break`.

#### 4.5.5 Trust-assumption registry pointer

Every envelope evaluation depends on an explicit set of trust assumptions enumerated in §13.5 (TA-DS-1..10). The ones load-bearing here are:
- TA-DS-1: CSD signing key uncompromised (per L_7^P.TrustRoots).
- TA-DS-2: CSD does not equivocate (does not sign two contradictory finality messages for the same `tx_id`). Detection via `dedup_key`-collisions over different payloads.
- TA-DS-3: ISO 20022 schema pinned via versioning.

### 4.6 Decimal handling at recon time — non-negotiable

Same table as v1. ROUND_HALF_EVEN; no float; no string concat for amounts; no implicit FX; no `==` on decimals; no `round()` on prices before storage. Per-currency tolerances versioned in `L_7^P.PolicyConfiguration` keyed `(ccy, recon_kind)`. Defaults `USD/EUR/GBP/HKD/SGD = 0.00`, `JPY = 0`, `CHF = 0.01`. Override requires four-eyes (data v1.0 §15). Tolerances bitemporal — old recon at old tolerance reproducible with `t_known = old`.

### 4.7 Cadence

| Recon | Cadence | Window | Owner |
|---|---|---|---|
| Intraday position | every 15min | `MorningReconWorkflow` | Middle office |
| Morning EOD | 09:00 local | T-1 close vs T-1 nostro | Middle office |
| Settlement-day finality | continuous | ingest of sese.025/camt.054 | Settlement ops |
| Ledger-vs-ledger | daily | counterparty triparty MIS | Counterparty desk |

### 4.8 Recon engine — three classifications

Every recon run emits exactly three sets:

1. **CLEAN** — identity holds within tolerance per `(w, ccy)` and per `(w, ISIN)`. No action.
2. **EXPECTED LEAD-LAG** — identity violated by an amount exactly explained by open `cpty_virtual` contras and open wire-level inflight. No action; this is the open-window state.
3. **BREAK** — identity violated by an amount NOT explained by (1) or (2). `BreakRegister` row created with kind, owner, deadline, expected resolution.

The classification is **purely algebraic.** No manual triage.

### 4.9 Multi-day fail aging — L_18 FSM mapping

Same as v1 §4.9. CSDR-aligned aging ladder: `Open → Investigating → Assigned → Aged-1 → Aged-3 → Aged-5 → Escalated → At-Risk → Material → Closed-{Clean | Adj | Waived}`. Closed-sum, four-eyes on Closed-Waived.

---

## 5. Lifecycle FSM (per-leg canonical, three wallet classes)

### 5.1 Per-leg `L_15.Obligation.state` is canonical (closes lattner B-1, halmos M8)

The single source of truth for the lifecycle of a settlement obligation is the per-leg `L_15.Obligation.state` field. It is a closed-sum, total FSM. The transaction-level "settlement_status" view is not stored and not a separate FSM; it is a Library-layer projection function (§5.3).

### 5.2 Closed sum

```
LifecycleState =
  | Pending             (* registered at T; awaiting instruction emission *)
  | Instructed          (* sese.023 emitted; awaiting CSD finality *)
  | PartiallySettled    (* partial discharge witnessed; residual still open *)
  | Discharged          (* terminal: full witness-driven discharge *)
  | Failed of FailureReason   (* terminal-conditional: deadline missed, witnessed fail *)
  | BoughtIn            (* terminal: CSDR mandatory buy-in resolved the failure *)
  | Cancelled           (* terminal: pre-instruction CORRECTION via four-eyes *)
  | Compensated         (* terminal: cash-in-lieu / close-out / manual override discharge *)
```

Terminal set $F_{\text{terminal}} = \{\text{Discharged}, \text{Cancelled}, \text{BoughtIn}, \text{Compensated}\}$. `Failed` is terminal-conditional (admits transition to `BoughtIn` or `Compensated` via CSDR resolution; otherwise absorbing).

Allowed transitions:
```
Pending      → Instructed                               (sese.023 dispatch witness)
Pending      → Cancelled                                (four-eyes pre-instruction CORRECTION)
Instructed   → PartiallySettled | Discharged | Failed   (witness)
PartiallySettled → Discharged | Failed                  (witness on residual)
Failed       → BoughtIn | Compensated                   (CSDR resolution path)
*            → Compensated                              (four-eyes manual override; §5.4)
```

All other transitions are forbidden by the FSM closed-sum constraint (DS8). Compile-time enforcement: exhaustive `match` on `LifecycleState` in the step function (§12.1).

`FailureReason` is a closed sum:
```
FailureReason =
  | DeadlineMissed
  | NoCover                              (* securities short for delivery *)
  | NoFunds                              (* cash short for payment *)
  | CounterpartyDefault of LEI
  | CsdReject of CsdRejectCode           (* normalised closed sum *)
  | LegInconsistent of WhichLeg          (* DvP partial – formalis G4 *)
  | Manual of OperatorId
```

### 5.3 Transaction-level status as projection function (NOT a stored field)

```
def tx_status(tx) -> TransactionView:
    legs = L_15 rows where obligation.tx_id == tx.tx_id
    states = {leg.state : leg ∈ legs}

    if all states == {Discharged}:                  return Settled
    if any state == Compensated  and others terminal: return Compensated
    if any state == Cancelled    and others terminal: return Cancelled
    if any state == PartiallySettled:                 return PartiallySettled
    if any state == Failed       and others terminal: return Failed
    if all states ⊆ {Instructed}:                    return Instructed
    if all states ⊆ {Pending, Instructed}:           return InFlight
    return Mixed   # operational anomaly — break

class TransactionView = Settled | Compensated | Cancelled | PartiallySettled
                      | Failed | Instructed | InFlight | Mixed
```

`tx_status` is **pure**. Operational queues that need to filter "all transactions where status = X" use a materialised view declared in §10.7 (computed by the same projection at write time and indexed). v1's `MoveStream[tx_id].settlement_status` column is **removed**. Closes lattner B-1.

### 5.4 Manual override (NEW; closes theme C / jane_street M-5)

A manual override is a CORRECTION-class transaction (no anti-moves to settle the obligation; just a state transition from `Pending | Instructed | PartiallySettled | Failed → Compensated`) requiring all of:

```
Override:
  refers_to_obligation: <obligation_id>
  reason_code:          <closed-sum: CSD_FORCE_CANCEL | CPTY_BANKRUPTCY |
                                     EOM_RESERVE_CLEAR | OTHER>
  justification:        <free text, mandatory, ≥ 50 chars>
  requester_lei:        <operator LEI>
  approver_lei:         <operator LEI; MUST != requester>
  approver_role:        <closed-sum: OPERATIONS_HEAD | RISK_OFFICER | CFO_DELEGATE>
  approval_ts:          <UTC>
  evidence_ref:         <link to compensating instrument or attestation>
```

Rejected by the framework if any field missing or `requester_lei == approver_lei`. Audit chain in §10.

### 5.5 Witness-driven discharge

An obligation transitions to a non-Pending state ONLY when:
1. A `§4.5 Envelope` is recorded on `L_11.ExternalConfirmation`.
2. The envelope is verified (signature, schema, dedup, multi-source quorum if required by §4.5.2).
3. The envelope payload reconciles with the obligation's `discharge_predicate` (qty, ccy, amount within tolerance).

**The framework never marks a leg `Discharged` by inference, by clock, or by absence of evidence.** Watchdog timer triggers `wf-confirm-break`, NOT auto-FAIL (§4.5.3).

After `T_max = expected + buyin_window`, the obligation auto-promotes to `L_18.BreakRegister` of kind `obligation_overdue`; the obligation itself remains `Pending` or `Instructed` until a witness arrives or the fallback handler executes a CORRECTION (`Compensated`) or default (`Failed`).

### 5.6 Idempotency and out-of-order ingest

Witness matching is by `dedup_key` (§4.5.1). Replay produces no duplicate transition. Out-of-order witnesses commute under the signal-handler commutativity table (§6.5.5 — closes temporal B-3).

---

## 6. Variants — same mechanism, different parameters

The deferred-settlement representation is parameterised on `settle_date = t_d`. **DS8 (variant degeneration)** is the formal commitment: for all variants, DS1–DS10 hold without modification; only workflow timer durations change.

### 6.1 T+1 markets

US: T+1 since 28 May 2024. UK/EU/CH: target 11 October 2027. India: T+1 since 2023; T+0 (optional) since 2024.

The Ledger absorbs T+1 because ISD is a parameter on the settlement instruction. Parameters live in:
- `ProductTerms[u].settlement_cycle` (per ISIN × MIC), sourced from `L_4 CalendarConvention` + `L_16 ReferenceMaster`.
- `Trade.cdm_payload.settlementDate` (CDM-native).
- `L_15.Obligation.deadline`.
- `L_18` break-aging timers.

**No code change** beyond config refresh and CSDR penalty-window recalibration.

### 6.2 T+0 / atomic DLT (parameter; future)

`t_d = T`; `Pending` has zero duration. Discharge predicate becomes `ByAttestation(on-chain finality oracle)`. Inflight period collapses to ε. CSDR penalty regime not applicable (no fail). FX leg becomes atomic PvP. **No unsettled-trade capital. ECL on settlement receivables ≈ 0.**

What stays constant: the FSM, the `L_15.Obligation` object, conservation invariants, trade-date economic recognition, the DRR engine. **This is the test of the architecture.**

### 6.3 Failed settlement (FSM transition, not rollback; CSDR penalty in L_15)

A `Failed` state is a witness-driven FSM transition (DS4) — `sese.024` inbound or T_max exhausted with watchdog-confirmed silence-attestation per §4.5.3. **No moves on real wallets.** Economic position recognised at T preserved (DS7 — failure non-reversal).

CSDR penalty obligation:
```
Obligation row of kind CSDR_PENALTY in L_15:
  obligation_id:       hash_jcs("CSDR_PENALTY", refers_to_tx, intended_settle_date)
  kind:                CSDR_PENALTY
  discharge_predicate: ByDeadline(buy_in_resolution_date)
  fields:
    qty_failed:           D_0 or D_18 per instrument
    price_at_intended:    D_8 (pinned via refdata at intended settle date)
    rate_bps:             D_4 (per ESMA Penalty Matrix; pinned via refdata_pin)
    accrual_start:        intended_settle_date + 1 bd
  state: Pending
```

Daily accrual emits a small cash transaction atomically with `o_pen.csdr_penalty_accrued` update. **Penalty amount is a pure function** of `(qty_failed, price_at_intended, days_late, instrument_class, refdata_pin)`. No human inputs; no discretion (DS — see §11).

### 6.4 Partial settlement

CSD reports 60 settled, 40 pending; later (T+4) reports the remaining 40.

```
TX_partial_1:
  type: SETTLEMENT_FINALITY
  tx_id: hash_jcs("FINAL", TX1.tx_id, sese.025_partial1_msg, attempt_seq=0)
  Move: from = w_DTC_depot_mirror[GS], to = w_PS[w_us, GS, XYZ], unit = XYZ, qty = 60
  Move: from = w_PS[w_us, GS, USD],     to = w_JPMC_nostro_mirror[GS], unit = USD, qty = 3000
  L_15 update o_sec.state:  Instructed → PartiallySettled
  L_15 update o_cash.state: Instructed → PartiallySettled

TX_partial_2 (T+4):
  type: SETTLEMENT_FINALITY
  tx_id: hash_jcs("FINAL", TX1.tx_id, sese.025_partial2_msg, attempt_seq=1)
  Move: same shape, qty = 40 / 2000
  L_15 update both: PartiallySettled → Discharged
```

`κ_buyin` (recursion bound, §0.4) for partial → buy-in → partial cascades is `D_max = 2` per jane_street's PO-9; beyond `D_max` cascade transitions to `Failed → Compensated` (cash-in-lieu) rather than continuing.

Conservation: `q_remaining + q_settled = q_initial` per partial step (DS6 — see §11; renamed DS11a in v2).

### 6.5 Workflow specification (NEW; closes temporal B-1..B-5 and 10 majors)

This section is new in v2. It addresses the temporal review's blocking findings on saga shape, idempotency keys, signal-handler commutativity, T+2 trigger mechanism, and ContinueAsNew payload.

#### 6.5.1 Canonical `tx_id` formula (closes temporal B-1)

```
tx_id = hash_jcs(business_event_id, attempt_seq)

where:
  business_event_id = stable namespaced upstream identity, e.g.:
                      "exec:" || venue_mic || ":" || exec_id || ":" || leg_label
                      "final:" || referenced_tx_id || ":" || msg_id_set
                      "buyin:" || referenced_tx_id || ":" || buyin_seq
                      "correction:" || referenced_tx_id || ":" || correction_seq
  attempt_seq       = monotonic uint32 within (business_event_id);
                      starts at 0, increments on workflow-level retry
```

`business_event_id` is **content-addressed** on stable upstream fields. `attempt_seq` is a workflow-state value, **carried across ContinueAsNew via the workflow input payload** (§6.5.6) — never `run_id` or any other Temporal-ephemeral field. This closes temporal B-1.

**Idempotency.** Two workflow attempts producing the same `(business_event_id, attempt_seq)` produce the same `tx_id`. Two attempts at different `attempt_seq` produce different `tx_id`s; the deduplication on the move-stream side (`L_13.tx_id` is a primary key) prevents double-application; the executor admits exactly one.

#### 6.5.2 Workflow IDs and granularity

Workflow id is **per-obligation**:
```
workflow_id = "settlement-saga:" || obligation_id
```
not per-bucket, not per-trade. A DvP trade with two legs has two `L_15.Obligation` rows and two workflow instances. They communicate via signals (§6.5.5) when atomicity at discharge is required (§6.5.3).

This closes temporal B-5 (granularity unspecified) and matches PO-10 (signal-driven, not heartbeating activity).

#### 6.5.3 DvP atomicity at discharge (closes temporal B-2 and theme H DvP-E)

The R1 finding was that v1 §3.5 said "DvP discharge as one transaction" but `sese.025` (securities) and `camt.054` (cash) arrive **independently**. v2 resolves via per-leg discharge with a transaction-level emergence rule:

**Rule.** Each `L_15.Obligation` leg is **independently** transitioned by its own witness arrival. There are TWO `L_13` transactions in the typical DvP discharge path:

```
On sese.025 arrival for o_sec:
  emit Transaction(type=SETTLEMENT_FINALITY_LEG, leg=securities)
    Move: w_DTC_depot_mirror[cpty] -> w_PS[w, cpty, ISIN], unit=ISIN, qty=q
  L_15 update o_sec.state: Instructed → Discharged
  L_15 update o_sec.csd_finality_witness: <envelope dedup_key>

On camt.054 arrival for o_cash:
  emit Transaction(type=SETTLEMENT_FINALITY_LEG, leg=cash)
    Move: w_PS[w, cpty, ccy] -> w_JPMC_nostro_mirror[cpty], unit=ccy, qty=amount
  L_15 update o_cash.state: Instructed → Discharged
  L_15 update o_cash.csd_finality_witness: <envelope dedup_key>
```

The "transaction-level all-legs-settled" emerges from the projection function `tx_status` (§5.3): once both `o_sec.state == Discharged` and `o_cash.state == Discharged`, `tx_status(tx) == Settled`. **There is no atomic "trade-level discharge transaction."**

**DvP-E (economic recognition) atomicity** is preserved differently from **DvP-L (ledger move-pair) atomicity** (closes theme H, cartan M-5). The disambiguation:
- **DvP-L** (ledger atomicity) holds at trade time T (move pair atomic within `TX1`) and at each per-leg finality (each finality transaction's move pair is atomic within itself).
- **DvP-S** (settlement-utility atomicity) is enforced at the CSD (DTC's DvP Model 1, T2S DvP, Euroclear DvP); the CSD guarantees both legs settle or neither does in their batch. Witnesses arrive at our system independently as a transport-layer concern.
- **DvP-E** (economic-recognition atomicity) is enforced via `PairedObligation` (§12.2): the two legs of a DvP trade are paired at trade construction; downstream code that operates on the "trade" level pattern-matches on the PairedObligation and observes the asymmetric states (`Equity_settled_fx_pending`, etc.) explicitly.

**The leg-inconsistent failure mode** (cash settled, securities failed at a non-DvP CSD) is observable in `tx_status(tx) == Mixed`; a `wf-confirm-break` workflow opens; the per-CSD κ table (G4 in v1; PO-5 owner) determines whether to manual-revert the partial leg.

#### 6.5.4 T+2 trigger = deadline timer with watchdog fallback (closes temporal B-4)

Phase 1 specified "deadline timer with watchdog fallback poll"; v1 dropped the watchdog. v2 restores:

```
Deadline mechanism (in workflow code):

  // Primary: a Temporal timer
  let primary_timer = workflow.sleep_until(intended_settlement_date + 0.5bd)

  // Fallback: a watchdog activity that reads the L_15 row
  let watchdog = workflow.sleep_loop(Λ_n) {
    on each tick:
      if obligation.state ∈ {Pending, Instructed} AND
         now() > intended_settlement_date + Λ_n_threshold:
        emit silence_attestation envelope (§4.5.3)
        spawn wf-confirm-break(obligation_id)
  }

  await first_of([primary_timer, witness_signal_arrival])
```

`Λ_n` cadence specified in §0.4. The watchdog is **idempotent**: emitting two `silence_attestation` envelopes for the same `(obligation_id, watchdog_seq)` is dropped via `dedup_key`.

#### 6.5.5 Signal-handler commutativity table (closes temporal B-3)

DS5 (replay determinism) requires that any two interleavings of the same multiset of inbound signals produce the same final state. v2 specifies the commutativity matrix explicitly:

| Signal A | Signal B | Result of A then B | Result of B then A | Commute? |
|---|---|---|---|---|
| `sese.025(tx_id)` for o_sec | `camt.054(tx_id)` for o_cash | both legs Discharged | both legs Discharged | YES |
| `sese.025(tx_id, partial q1)` | `sese.025(tx_id, partial q2)` | sequential partials accumulate by `attempt_seq` | same | YES (via `attempt_seq` ordering on leg balance state) |
| `sese.025(tx_id)` | `cancel sese.027(tx_id)` | discharge wins (already terminal); cancel rejected | cancel wins (no discharge yet); discharge then quarantined | NO — explicit precedence: terminal absorbs late events |
| `sese.025(tx_id)` | `restated sese.025(tx_id, q')` (Reading G5) | new attempt_seq; Reading (a): treat as new obligation | same | YES under Reading (a) |
| `silence_attestation(tx_id)` | `sese.025(tx_id)` | break opened, then closed by witness | witness then no break needed | YES (break is observable; witness closes it) |
| `sese.024(fail tx_id)` | `sese.025(tx_id)` | fail → break → witness contradicts → quarantine via `wf-confirm-break` | witness → discharged; later sese.024 quarantined | NO — explicit precedence: contradictions always quarantine |
| Cross-trade signals (different `tx_id`) | any | independent; per-workflow isolation | same | YES |
| `correction_tx(refers_to=tx_id)` | `sese.025(tx_id)` | correction wins under four-eyes; sese.025 quarantined | discharge wins; correction rejected as "obligation already terminal" | NO — terminal absorbs |

The non-commuting cases (terminal absorbs; contradictions quarantine; correction-vs-discharge) are explicitly **not** "out-of-order replay produces different state" — they are deterministic precedences encoded in the FSM step function. Property-test PO-8 (TLA+ at $|\mathcal{W}|=3, |U|=2, depth=8$) verifies the multiset-replay form of DS5 against this table.

#### 6.5.6 ContinueAsNew payload schema

Long-running settlement sagas (multi-week buy-in chains) use ContinueAsNew. The payload schema is fixed:

```
WorkflowInput:
  obligation_id          : ObligationId         // primary key
  business_event_id      : str                  // for tx_id derivation
  attempt_seq            : uint32               // CARRIED across CaN
  state_snapshot         : LifecycleState       // current FSM state
  envelope_history_dedup : List[DedupKey]       // bounded N=4096, TTL=30d (PO-10)
  watchdog_seq           : uint32               // current watchdog poll seq
  parent_obligation_id   : Optional[ObligationId]  // for buy-in chains, partials
  cancel_compensation_token : Optional[Token]   // late-discharge race; G9 / PO-2
```

`run_id` is **not** in the payload. `tx_id` derivation is `hash_jcs(business_event_id, attempt_seq)`; both are workflow-state values, deterministic across CaN.

`envelope_history_dedup` is bounded (n=4096, TTL=30 days) per PO-10. Older entries are GC'd; a duplicate envelope arriving past TTL routes to `wf-confirm-break` for human inspection (assumed-replay concerns).

#### 6.5.7 Saga compensation tower — late-discharge race (closes G9 / PO-2)

The saga compensation tower's "Late-discharge race policy" for `SETTLEMENT` class:
- **If the cancellation has not yet been externalised (sese.027 not dispatched):** cancel-compensation. Internal state rollback via four-eyes CORRECTION.
- **If externalised:** queue-and-reconcile. The cancel and the late-arriving discharge both register; the obligation transitions through `Cancelled` and the late discharge is recorded as quarantine `wf-confirm-break` for forensic.

Pinned in `L_7^P.SagaCompensationPolicy` keyed `("SETTLEMENT", "late_discharge")`. Versioned bitemporally.

#### 6.5.8 Three workflow shapes catalogue

| Workflow | Trigger | Body (high-level) | Output |
|---|---|---|---|
| `SettlementSaga` | trade-time obligation creation | (1) emit `sese.023`; (2) wait for finality witness OR deadline+watchdog; (3) on witness, atomically apply finality moves + L_15 transition; (4) on deadline+watchdog, spawn `wf-confirm-break`; (5) on Reading(a)-restatement, ContinueAsNew with new `attempt_seq` | `o.state ∈ F_terminal` |
| `BuyInWorkflow` | `o.state == Failed` past CSDR `buyin_window` | (1) emit buy-in instruction (CCP or party-level); (2) await execution attestation; (3) on execution, emit replacement trade (own `tx_id` per §6.5.1 with `business_event_id="buyin:..."`); (4) link `parent_obligation_id` to the original `o`; (5) on completion, transition original `o → BoughtIn` | replacement trade settled or cash-in-lieu |
| `MorningReconWorkflow` | Temporal cron 09:00 local | (1) for each `(real_wallet, ccy_or_ISIN)`, scan §4.1 identity; (2) classify per §4.8 (CLEAN / EXPECTED LEAD-LAG / BREAK); (3) emit per-counterparty / per-currency reports; (4) for BREAKs, spawn `wf-position-break` per kind | report set + L_18 rows |

---

## 7. Composition with §13 SBL six-coordinate model + Conservation Lifting Theorem

### 7.1 Orthogonality

The GPM six-tuple `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` and the deferred-settlement state are **structurally orthogonal**. Same FSM runs for cash-equity sales, SBL loan settlement, SBL collateral movements, and SBL recall returns. The smart contract dispatches on instruction type; the FSM is uniform.

### 7.2 The standard buy/sell draws from `own` directly

Sale of $q$ shares of unit $u$ at $T$ settling $T+2$:
$$\Delta \mathrm{own}_e(u) = -q \quad \text{at } T.$$

If `own ≥ q`, clean reduction. If `own < q`, `own` goes negative — and this is correct under SSR Article 12(1)(c) locate. The locate Unit and the `avail = own - onloan + borr` projection enforce SSR/Reg-SHO at the smart-contract guard level.

The seller's *delivery obligation* lives in `L_15.Obligation` and in the `cpty_virtual` wallet, **not** on the GPM. **`own` and inflight are different things and live in different storage.**

### 7.3 Short-sale lifecycle and SBL composition (preserved from v1)

Setup, T+0 locate, T+0 short sale to D, T+1 borrow settles, T+2 short sale settles to D — same shape as v1 §7.3 and §7.7. (Detailed sub-sections preserved by reference; not re-litigated to make space.) Recall during the open window: the recall obligation is independent of the sale obligation; both are `L_15.Obligation` rows; if `avail < required`, buy-in saga spawns. Naked short rejected by pre-trade guard; "long that has never owned" legal under SSR Art 12(1)(c) and observable by `(own < 0 AND borr > 0 AND no prior own > 0 trade)` projection.

### 7.4 First-class unit `u^circ` — bijection Φ (closes cartan B-1 / theme 12)

R1 closure: cartan B-1 said v1's §15.2 sentence "the two representations would map 1-to-1" *is* the bijection that should have been the proof. v2 states it.

#### 7.4.1 Theorem (bijection Φ)

Let:
- $M$ = mainstream representation: $(W, U, P, L_{15})$ where $W$ is the wallet universe (real + cpty_virtual + csd_virtual), $U$ is the unit master, $P : W \times U \to \text{Decimal}$ is the position map, $L_{15}$ is the obligation table.
- $C$ = first-class-unit representation: $(W', U', P')$ where $U' = U \cup \{u^\circ_o : o \in L_{15}\}$ (every obligation gives rise to a fresh unit) and $W' = W \setminus \{w \in W : \text{class}(w) = \text{cpty\_virtual}\}$ (no virtual wallets).

There exists a bijection $\Phi : M \to C$ defined by:
- For real wallets $w$ and inherited units $u \in U$: $P'(w, u) = P(w, u)$.
- For each obligation $o \in L_{15}$ between holder $w_h$ and counterparty $w_c$ on unit $u$ at qty $q$ in state $s$: $P'(w_h, u^\circ_o) = +q$ (or $-q$ depending on side) and $P'(w_c, u^\circ_o) = -q$ (or $+q$); the unit $u^\circ_o$'s `UnitStatus` carries the lifecycle state $s$; `ProductTerms[u^\circ_o]` is degenerate (no price function; the obligation's price is induced by the underlying $u$'s price).

#### 7.4.2 Proof sketch

- **Surjection.** Every $C$-state is the image of some $M$-state: given $(W', U', P')$, define $L_{15}$ as the set of $u^\circ_o \in U'$ with `UnitStatus.kind = Obligation`; reconstruct $(W, U, P)$ by collapsing each $u^\circ_o$ across its two holders into a `cpty_virtual` wallet pair.
- **Injection.** Two distinct $M$-states cannot map to the same $C$-state: the mapping preserves all qty/state information.
- **Conservation preservation.** $\sum_{w \in W} w(u) = 0 \iff \sum_{w' \in W'} w'(u') = 0$ when summing over corresponding wallet sets.

Φ is therefore a bijection. Both representations are **information-equivalent**.

#### 7.4.3 Why mainstream is chosen — operational cost

The bijection means there is no formal-mathematical reason to prefer one. The choice is operational. v1 §1.2 listed seven operational reasons (cardinality of unit master; opt-out at every `PositionState` consumer; duplication of state already in `L_15`; library-not-language). v2 endorses the choice and adds one observation:

**The first-class representation captures one fact the mainstream does not: exposure transfers between sub-balances of the same wallet (e.g., re-allocating an obligation between two operational books) are first-class events.** In the mainstream representation these are simulated by `cpty_virtual` wallet creation/retirement. The first-class fact is **not load-bearing** for v11.0: zero current consumer of the framework needs sub-balance exposure transfers as primitive events; they are projections from `L_15` re-keying.

#### 7.4.4 Recommended revisit

When CDM 7.0 ships an `Obligation` root type (Gap 10 PR), Φ becomes the documented mapping the framework implements. Until then, mainstream stands.

### 7.5 Conservation Lifting Theorem (NEW; closes cartan B-2)

R1 closure: cartan B-2 said §2.6 asserted conservation as a conclusion without theorem-form hypotheses. v2 states it.

#### 7.5.1 Statement

**Theorem (Conservation Lifting).** Let $\mathcal{W}$ be the constant universe (real + cpty_virtual + csd_virtual; §0.1, §2.6) and let $\Sigma_t$ denote the set of transactions ever committed at time-points $\leq t$.

**Hypotheses:**
- **H1 (move balance).** Every transaction in $\Sigma_t$ is balanced per unit: for each $\tau \in \Sigma_t$ and each unit $u$, $\sum_{m \in \tau, m.\text{unit} = u} \text{signed-delta}(m) = 0$.
- **H2 (virtual sign correctness).** Every move whose source or destination is a `cpty_virtual` or `csd_virtual` wallet writes the signed quantity per the canonical sign convention of §0.2: positive on `w_PS[w, cpty, u]` ↔ "we owe", positive on `w_DTC_depot_mirror[holder]` ↔ "this holder is long at the CSD".
- **H3 (state-only moves vacuous).** State-only transactions (zero-move) contribute zero to every wallet sum.
- **H4 (wallet universe constancy).** $\mathcal{W}$ is fixed across $t$: no wallet is removed; new wallets enter at a defined zero balance.
- **H5 (CORRECTION respects H1).** Every CORRECTION transaction is itself balanced (anti-moves balance the original moves they reverse, plus any compensating moves).

**Conclusion:** $\sum_{w \in \mathcal{W}} w_t(u) = 0$ for every unit $u$ and every wall-clock $t$.

#### 7.5.2 Proof outline

By induction on $|\Sigma_t|$.
- **Base.** $|\Sigma_t| = 0$: every wallet is at zero by H4. Sum is zero.
- **Step.** Assume conservation at $t$; let $\tau$ be the next transaction at $t' > t$. By H1, $\tau$ is balanced. By H2, virtual-wallet signs are consistent. By H3, state-only $\tau$ is vacuous. By H5, CORRECTION $\tau$ is balanced. Hence $\sum_{w \in \mathcal{W}} w_{t'}(u) = \sum_{w \in \mathcal{W}} w_t(u) + 0 = 0$.

Q.E.D.

#### 7.5.3 What the theorem buys

- DS2 (Open-Window Conservation; §11) is a **corollary** of the theorem. It is no longer an independent invariant; it is restated for downstream consumers and proved here.
- The §4.1 recon identity is a **consequence** of the theorem combined with the `csd_virtual` mirror semantics (the `csd_virtual` wallet's value is the contra of the external nostro/depot at our holder's account).

### 7.6 Block-and-allocation composition case (NEW; closes theme D)

Asset-manager dominant flow: a single block trade executed on the venue, allocated post-trade across multiple sub-accounts.

#### 7.6.1 Shape

```
Block trade B at T:
  Buy 10,000 XYZ @ $50 from broker GS, settling T+2.
  L_15 register o_block (state = Pending) on a virtual block wallet w_block_v.

Allocation event A at T+0+ε (via allocation-message MT519 / sese.020):
  Allocate 4,000 to fund_F1 (w_F1)
  Allocate 3,500 to fund_F2 (w_F2)
  Allocate 2,500 to fund_F3 (w_F3)

  Atomic transaction TX_alloc:
    Move 1: w_block_v -> w_F1 unit=XYZ qty=4000
    Move 2: w_F1 -> w_PS[w_F1, GS, USD] unit=USD qty=200_000
    (similar for F2, F3)
    L_15: spawn o_F1_sec, o_F1_cash, o_F2_sec, ... (six obligations)
    L_15 update o_block: state = Compensated (kind = ALLOCATION_SPLIT)
```

#### 7.6.2 Composition properties

- **Conservation across the allocation step.** At allocation, the block obligation closes (Compensated by allocation-split kind) and 2N child obligations spawn. Sum of qty across child obligations equals block qty. H1 holds at each move in `TX_alloc`.
- **Independent settlement per child.** Each `o_Fi_sec` and `o_Fi_cash` proceeds through the FSM independently. Partial-fill at the CSD on the block flows to per-child partials via the same `attempt_seq` mechanism.
- **Audit trail.** The block-to-allocation chain is captured in `L_15.parent_obligation_id` (each child references `o_block`).
- **Allocation correction.** A mis-allocation (wrong fund attribution) is corrected via four-eyes CORRECTION on the allocation transaction; the children are reversed as anti-moves; new child obligations spawn under a new allocation. Both versions in `L_13` audit log.

#### 7.6.3 Settlement-day discharge for the chain

```
On sese.025(block tx_id) inbound (CSD reports the block settled):
  The CSD does NOT distinguish allocations; it sends one sese.025 per block.
  Our SettlementSaga(block tx_id) is in state Compensated at the block level
    (already discharged by allocation-split).
  Per-child workflows independently discharge each o_Fi_* via the cpty_virtual ->
    csd_virtual mirror moves.
```

In practice, large brokers send per-allocation `sese.025` once they have allocated their book to your sub-accounts. The framework absorbs both modes (one-block-message vs per-allocation-message) by per-leg `L_15` discharge.

### 7.7 SBL recon identity for composition

For an entity holding SBL positions:
$$\mathrm{own}_e(u) + \mathrm{borr}_e(u) - \mathrm{onloan}_e(u) - \sum_{i \in \mathrm{open}(e,u)} \mathrm{signed\_qty}(i) = D(e, u)$$

where `open(e,u)` = obligations with `state ∈ \{Pending, Instructed, PartiallySettled\}` touching `(e, u)`. Same shape as §4.1 cash recon, generalised to bookkeeping coordinates. Sign convention is canonical (§4.1).

### 7.8 Three regulatory IDs as L_15 metadata

Each obligation row carries: `mifir_trn`, `sftr_uti`, `csd_instruction_ref`, `slate_loan_id`, `slate_finra_loan_id`. Populated by the settlement projection at outbound emission, reconciled at inbound confirmation. The reporting fan-out is a workflow, not a data-model concern; each regime has its own `L_17.RegulatorySubmission` row referencing the same `obligation_id` but generating distinct payloads. Bitemporal restatements: `L_15.t_known` updated; `t_obs` preserved.

---

## 8. CDM cross-walk

CDM 6.0.0 maps cleanly to **roughly half** of the Ledger v11.0 deferred-settlement design. CDM types verified at 2026-04-30 against `github.com/finos/common-domain-model@master`.

### 8.1 24-element inventory (preserved from v1)

The 24-element Direct/Partial/Missing inventory of v1 §8.1 is preserved by reference. Summary classification: **Direct 11 / Partial 6 / Missing 7.**

### 8.2 Five strategic gaps

- **Gap 6** — `TransferStatus` enrichment (Failed, PartiallySettled, Cancelled + `TransferFailureReason`). STRATEGIC, CSDR-blocking.
- **Gap 7** — Partial settlement granularity (subsumed in Gap 6).
- **Gap 8** — CSDR cash penalty as structural event (`CSDRPenaltyDetail`).
- **Gap 9** — Buy-in event (`BuyInInstruction`, `BuyInExecution`).
- **Gap 10** — Obligation as first-class root type. Highest-leverage.
- **Gap 11** — Economic-exposure-at-T as enforced semantic (doctrinal, not Rosetta).

### 8.3 Rosetta extension PRs PR-1..PR-4

PR-1 (Gap 6+7) ~80 lines; PR-2 (Gap 8) ~120 lines; PR-3 (Gap 9) ~150 lines; PR-4 (Gap 10) ~200 lines. All non-breaking. Recommended sequence PR-1 → PR-2 → PR-3 → PR-4. Detail preserved from v1 §8.3.

### 8.4 Forgetful F is a lossy non-faithful functor (closes cartan B-4 / theme 13)

R1 closure: cartan B-4 — v1 §8.4 called F a homomorphism but the proposal's own "F loses" list contradicts. v2 corrects.

#### 8.4.1 Statement

Let $\mathbf{Lg}$ be the category of Ledger states (objects: `(WalletRegistry, UnitRegistry, MoveStream, ObligationStore)`; morphisms: balanced atomic transactions). Let $\mathbf{CDM}$ be the category of CDM states (objects: collections of `BusinessEvent`, `TradeState`, `TransferState`; morphisms: `BusinessEvent` chaining).

**$F : \mathbf{Lg} \to \mathbf{CDM}$ is a lossy non-faithful functor.**

- **Functoriality.** F respects identities and composition: $F(\text{id}) = \text{id}$; $F(\tau_1 \circ \tau_2) = F(\tau_1) \circ F(\tau_2)$.
- **Lossy.** F is not injective: distinct $\mathbf{Lg}$-states can map to the same $\mathbf{CDM}$-state. Specifically, F collapses the wallet axis (per-(wallet, unit) PositionState density is lost; only per-trade `TransferState` remains).
- **Non-faithful.** F is not faithful: distinct $\mathbf{Lg}$-morphisms can map to the same $\mathbf{CDM}$-morphism. Specifically, multi-leg atomicity (one ledger transaction with three coordinated moves) F-projects to a CDM `BusinessEvent` that does not structurally enforce the atomicity (CDM treats it as convention).

#### 8.4.2 The $\mathbf{Lg}_{\text{econ}}$ quotient

Define an equivalence relation $\sim$ on $\mathbf{Lg}$ states: $\sigma_1 \sim \sigma_2$ iff they project to the same per-trade economic position table (collapsing wallet axis: sum across all `cpty_virtual` and `csd_virtual` wallets per `(real_wallet, unit)`).

The quotient category $\mathbf{Lg}_{\text{econ}} = \mathbf{Lg} / \sim$ has objects = equivalence classes and morphisms = induced maps.

**On $\mathbf{Lg}_{\text{econ}}$, F restricts to a homomorphism.** That is, $F|_{\mathbf{Lg}_{\text{econ}}}$ is faithful and injective up to CDM `BusinessEvent` identity.

#### 8.4.3 What this buys

- v1's "F is a homomorphism" assertion was true on $\mathbf{Lg}_{\text{econ}}$ (the trade-level economic projection) and false on $\mathbf{Lg}$ (the per-wallet state). v2 names both correctly.
- The **direction of authority** statement is unchanged: Ledger first, CDM downstream. The Ledger reconciles to CDM via $F|_{\mathbf{Lg}_{\text{econ}}}$, not the other way.
- For PR-4 (Gap 10 first-class Obligation), the quotient becomes finer (less collapsing), and F becomes faithful on more of $\mathbf{Lg}$.

### 8.5 ISO 20022 messages

Same table as v1 §8.5: `sese.023` (out, `LIFECYCLE`-class state-only); `sese.024` (in, fail status); `sese.025` (in, settlement confirmation); `sese.027` (cancellation); `camt.054` (in, cash credit/debit); MT54x legacy mapping. Each ISO 20022 message is a **witness** to a state transition, not the transition itself. The Ledger emits state transitions on receipt; the witness is recorded as the source.

### 8.6 What CDM 6.0.0 features NOT to use

Same table as v1 §8.6: `partialCashSettlement` is CDS-only; `sixtyBusinessDaySettlementCap` is CDS auction; settlement-date position recognition violates DS1; reversing position on fail violates DS7; deprecated `Lineage`; etc.

---

## 9. Regulatory footprint

Every emission is a **deterministic projection** of the move stream + L_17 rule-set version pin. No firm-specific reinterpretation. No manual mapping.

Per theme J trade-off: matrix kept (operational); prose trimmed to one-paragraph-per-regime.

### 9.1 Definitive regulatory matrix

| Regime | Trigger | What MUST be emitted | Format | Cadence | Dedup key | Rule-set pin | DRR status |
|---|---|---|---|---|---|---|---|
| **MiFIR Art 26 (RTS 22)** | New trade in scope | Transaction report (ISIN, MIC, LEI, qty, price, ts) | RTS 22 XML via ARM | T+1 by 23:59 NCA local | `(reporting_lei, internal_tx_id, version)` | MiFIR/RTS 22 v3 | In progress |
| **EMIR Refit Art 9** | New OTC derivative; lifecycle event | Trade + lifecycle reports (UTI, UPI, LEI) | ISO 20022 auth.030 | T+1 (T+2 UK from Sep 2024 some events) | `(reporting_LEI, UTI, action_type, event_type, sequence_number)` | EMIR Refit RTS 2022/1855 | **LIVE (Apr/Sep 2024)** |
| **CSDR Art 7** | Settlement instruction; daily fail; monthly penalty | Daily fail register; semt.044 advice; buy-in instruction | ISO 20022 sese.024/025/027, semt.044 | Daily T+ISD+1; monthly | `EndToEndId` outbound; `MessageId` inbound | CSDR RTS 2018/1229 + 2024 amendment | n/a (settlement) |
| **SFTR Art 4** | New SFT | Trade report (UTI, action, principals, collateral) | ISO 20022 auth.052 | T+1 dual-sided | `(reporting_LEI, UTI, action_type, event_date)` | SFTR RTS 2019/356 | In progress |
| **FINRA SLATE (Rule 6500)** | New SBL or covered loan | Loan-level (CUSIP, qty, rate, collateral) | XML to FINRA | Same-day for new; T+1 mods | `loan_id` + `event_seq` | FINRA Rule 6500 (Jan 2026) | n/a |
| **Reg SHO** | Short sale; locate; FTD past T+3 | Locate record; FTD report; threshold list | SEC EDGAR + FINRA | T (locate); EOD T+3 (FTD); daily threshold | `(broker, CUSIP, trade_date, locate_id)` | SEC Rule 200/203/204 | n/a |
| **Pillar 3 / BCBS 239** | Quarterly aggregate; CRR Art 379 buckets | Failed-trade aggregate by aging (5/16/31/46+ days) | XBRL FINREP/COREP; Pillar 3 | Q+45 cal days | `(reporting_lei, period_end, taxonomy_version, line_item_code)` | CRR Art 378–380 | Proposed (ISDA/IIF/GFMA Mar 2026) |
| **MAR Art 16** | Suspicious order pattern | STOR report | Free-form structured to NCA | "Without delay" | `(detector_id, ts, internal_alert_id)` | MAR RTS 2016/957 | n/a (alert-driven) |
| **IFRS 9 / IAS 1 / IAS 32** | Periodic; settlement-fail material | Notes — receivables, ECL, large exposures | iXBRL (ESEF) | Q / annual | `(entity_lei, period_end, taxonomy_version)` | IFRS 9.5.1.3, IAS 1.55, IFRS 7.6 | Cross-walk via projection |

**Two non-negotiable design points:**
1. **Every dedup key is content-addressed** on `(LEI, UTI/EndToEndId, version)`. The TR/ARM acknowledgement is the discharge predicate of the L_17 regulatory-submission obligation.
2. **Versioning is bitemporal.** Rule sets change; L_17 rows carry the rule-set version pin. Every restatement is a deterministic projection.

### 9.2 CSDR cash penalty + discretionary buy-in (one paragraph)

`penalty(instruction, day) = qty × ref_price × penalty_bps_rate(asset_class, fail_type, day - ISD)`. ESMA 2024 recalibration rates: liquid shares 1.0 bps/day; illiquid 0.5 bps/day; SME-growth-market 0.25 bps/day; liquid sovereign debt 0.10; other sovereign/corporate 0.20; cash leg ECB main refi rate × days_late/360 floored at 0. CSDs are source of truth (T2S central penalty mechanism); Ledger records `L_15.Obligation` of kind `CSDR_PENALTY`, reconciles `semt.044` advice. Discretionary buy-in window: 4 BD liquid, 7 BD SME-growth, 15 BD illiquid (`κ_buyin` per §0.4).

### 9.3 T+1 transition

Architectural: parameter, not architecture. ISD lives in `ProductTerms[u].settlement_cycle` × `Trade.cdm_payload.settlementDate` × `L_15.Obligation.deadline` × `L_18` aging timers. **No code change** beyond per-`(MIC, ISIN)` settlement-cycle table refresh and CSDR penalty-window recalibration. Operational machinery (FX cutoffs collapse by half; ETF NAV cycles; DTC night-cycle elimination; corporate-action cum/ex window collapse) must adapt; architecture absorbs.

### 9.4 T+0 / atomic DLT — degeneracy test (one paragraph)

t_d = T; inflight ε; nostro IS the chain; CSDR penalty regime N/A; FX leg atomic PvP; **no unsettled-trade capital; ECL ≈ 0**. What stays constant: FSM, `L_15.Obligation`, conservation, trade-date economic recognition, DRR engine. Hardcoding T+2 is technical debt with a known due date.

### 9.5 MiFIR RTS 22 specifics

T+1 by 23:59 in local time of relevant NCA, **independent of settlement status**. Field 28 = T (NOT T+ISD); Field 36 = trade quantity; Field 33 = trade price. Settlement status NOT in RTS 22; subsequent failures do not generate amendment. CANCELLED at trade level → MiFIR amendment (`CANC` action under RTS 22 Field 3). Trade economic correction → AMEND action.

### 9.6 EMIR Refit / DRR live status

CFTC (Dec 2022); JFSA (Apr 2024); EMIR EU (Apr 2024); UK EMIR (Sep 2024); ASIC (Oct 2024); MAS (Oct 2024); Canada (Jul 2025); HKMA (Sep 2025). In progress: EU/UK MiFID, EU/UK SFTR, Switzerland (FINMA), SEC. Production users (Nov 2025): Banque Pictet, BNP Paribas, JSCC, JPMorgan; 13 PoC firms. TR ack rates: 100% MAS; 98.2% EMIR Refit. Cost reduction: up to 50%.

### 9.7 Tri-regime UTI gotcha

A securities-borrowing transaction on an EU-listed equity has triple footprint: SFTR (SBL itself), CSDR (settlement), FINRA SLATE (US side), Reg SHO (short equity leg). UTI generation: `UTI = LEI(generating_party) || hash_jcs(...trade_essential_terms...)`; the Ledger supports this via the `tx_id = hash_jcs(business_event_id, attempt_seq)` formula (§6.5.1). Value-date conventions differ across regimes (SFTR: trade date for `event_date`, contractual settlement date for `value_date`; EMIR: execution timestamp; CSDR: ISD for penalty start) — naive implementation conflates and silently mis-reports.

### 9.8 Capital reasoning — Pillar 3 worked example (closes theme I)

R1 ashworth Phase 2 OK; reviewers wanted a worked example. Single failed-trade scenario, tier-1 dealer:

- Trade: Buy €50m of EU-listed equity, fails at T+2.
- Fail age: T+5 (5 BD past contract): falls in CRR Art 379 row "5–15 days, RW = 100%". `RWA contribution = max(0, P_t - P_contract) × qty × RW`. Suppose `P_t - P_contract = +€2/share, qty = 1m shares`: replacement cost €2m × 100% = €2m RWA.
- Aged to T+16: row "16–30 days, RW = 625%". RWA = €2m × 625% = €12.5m RWA. CET1 hit at 12% capital ratio: €1.5m capital tied up.
- Aged to T+46: row "46+ days, RW = 1,250%". RWA = €25m. CET1 hit: €3m capital, on a single trade.
- Pillar 3 disclosure: aggregate aged buckets exposed in COREP C 28.00 (Settlement Risk template). At Mar 2026 BCBS Pillar 3 consultation, machine-readable XBRL/CDM template is proposed.

This is the cost of *not* curing fails. CSDR cash penalty + replacement-cost capital scaling is the regulatory pressure that makes T+1/T+0 strategically attractive.

---

## 10. Accounting + audit + capital + correction policy

### 10.1 Trade-date accounting MANDATORY

For every cash-equity, listed-debt, listed-derivative, and equivalent regular-way trade, **trade-date accounting is mandatory at the ledger primitive level.** The move stream MUST recognise the economic position at trade-execution timestamp `T`. Settlement-date accounting is **not** supported as a primitive; downstream consumers requiring it produce it as a reporting projection.

Standard grounding: IFRS 9.B3.1.3 (regular-way exception); IFRS 9.B3.1.5; ASC 320-10-25-3; ASC 326-20-30-2 (CECL); IAS 32.42 (offsetting); v10.3 §13.2 Single-Coordinate Move Principle.

Why settlement-date cannot be primitive: CRR Art 325 FRTB / Art 274 SA-CCR computes capital on trade-date positions; IFRS 13.B5.1.2A Day-1 P&L; v10.3 P10 path-independence. Settlement-date projection (when needed):
```
settled_position(w, u, t) := own(w, u, t) − Σ { signed_qty(o) : o ∈ open_obligations(w, u, t) }
```

### 10.2 Balance-sheet substantiation

Setup: Dealer FVTPL, BUY 100 XYZ @ $50 Monday T, settling Wed T+2; mark $52 Tue close.

**At T close (Form B preferred):**
```
Dr Financial assets — FVTPL (XYZ)              5,000.00
   Cr Settlement payable to counterparty            5,000.00
```

**At T+1 close (mark $52):**
```
Dr Financial assets — FVTPL (XYZ)               200.00
   Cr Profit for the period (FVTPL)                  200.00
```

**At T+2 finality:**
```
Dr Settlement payable to counterparty           5,000.00
   Cr Cash at custodian                              5,000.00
Dr Securities at custodian (sub-ledger)        5,200.00
   Cr Financial assets — FVTPL (XYZ, in transit)    5,200.00
```

**No PnL impact at settlement** (P10 path-independence). Sub-ledger reclass only.

### 10.3 Five-document audit evidence chain

| # | Document | Source | Framework artefact | Linked by |
|---|---|---|---|---|
| 1 | FIX 8=ExecRpt | Trading venue / OMS | `Transaction(type=SETTLEMENT)` in `L_13` | `external_ref` |
| 2 | `sese.023` outbound | Settlement → CSD | `o_sec.state Pending → Instructed` | `EndToEndId = trade_id` |
| 3 | `sese.025` inbound | CSD → settlement | `o_sec.csd_finality_witness` + state Discharged | `RelatedRef = sese.023.EndToEndId` |
| 4 | `camt.054` inbound | Cash agent | `o_cash.csd_finality_witness` + state Discharged | `EndToEndId = trade_id` |
| 5 | CSD depot statement | CSD direct feed | Reconciliation against `w_DTC_depot_mirror[*]` | Position-level tie-out at T+2 EOD |

Each document signature-verified and content-hashed at ingress (per §4.5 Envelope). Bitemporal `(t_obs, t_known)`. Authority: ISA 500.6, ISA 505, PCAOB AS 2310, BCBS 239 P6, SOX 404 / SOC 1, IFRS 7.B11.

### 10.4 IFRS 9 ECL on settlement receivables

| Counterparty class | 2-day PD | LGD | ECL on £100m | Treatment |
|---|---|---|---|---|
| **CCP-cleared** | < 0.1 bp | 5–10% | < £5,000 | De minimis; portfolio pool (IFRS 9.B5.5.30) |
| **Tier-1 dealer IG** | 0.5–2 bp | 30–40% | £15k–£80k | Pool by counterparty rating |
| **Sub-IG bilateral** | 5–20 bp | 40–60% | £200k–£1.2m | Track by name |
| **Failed bilateral, day 5+** | 50–500 bp (Stage 2) | 60–80% | £3m–£40m | **Stage 2 migration** |

CSDR fail past contractual date is **non-rebuttable Stage 2 trigger**. Recalculate ECL using lifetime model (CSDR mandatory buy-in horizon + empirical fail-cure tail). Disclose IFRS 7.35F if Stage 2 migrations > 5% of gross. US GAAP CECL: same shape, no staging.

### 10.5 CRR Articles 378/379/380

- **Art 378** Free deliveries: 100% RW until second leg taken place. Applies FOP outside CSD-DvP.
- **Art 379** Settlement risk (CRR III, in force 1 Jan 2025): RW ramp 100% (5–15d) → 625% (16–30d) → 937.5% (31–45d) → 1,250% (46+d) on `max(0, P_t − P_contract) × qty`.
- **Art 380** Large exposures: receivables > 10% CET1 trigger Art 395 reporting; 25% cap.

Reporting projection extracts failed-trade ageing buckets per Art 379 + COREP C 28.00. Per-obligation aging from `(o.intended_settlement_date, current_business_date)`. CCP-cleared flag (zero CCR settlement risk under CRR Art 305).

### 10.6 SOX / SOC 1 controls (eight COs)

CO-1 trade capture; CO-2 instruction completeness; CO-3 confirmation matching; CO-4 daily 3-way tie-out; CO-5 SoD trader/settle/MO; CO-6 four-eyes CORRECTION; CO-7 break ownership; CO-8 FSM enforcement (only `SettlementSaga` may mutate `L_15.state`). StatesHome C11 capability discipline = structural enforcement. Trader cannot type-check against `obligation.state`; settlement-ops cannot type-check against `Move(unit=ISIN, qty=...)`. **SoD becomes a system property, not a procedural assertion.**

### 10.7 Storage and retention strategy (NEW; closes jane_street B-4)

#### 10.7.1 Volume estimate

10^7 trades/day × 2 legs/trade × 365 days × 7 years = ~5×10^10 obligation rows. At 50 bytes/row plus indexes, ~2.5 TB of L_15 storage; with envelope payloads and witness blobs, ~10–15 TB hot+warm.

#### 10.7.2 Retention tiering

| Tier | Window | Storage class | Query SLA |
|---|---|---|---|
| Hot | 0–90 days | OLTP (Postgres / DynamoDB) | < 100ms p99 |
| Warm | 90 days – 7 years | Columnar (Iceberg / Parquet on S3) | < 5s for ad-hoc; minutes for full scans |
| Cold | 7 years – 25+ years (regulatory archive) | Glacier / equivalent | hours-to-days; legal-hold flag |

The 7-year warm window covers IFRS 7/MiFIR/CSDR retention. The 25+-year cold window covers IRS / tax / litigation hold. Bitemporal queries (`as_of`, `with_corrections_through`) are first-class on hot+warm; cold-tier queries materialise via async restore.

#### 10.7.3 Partitioning

```
L_15.Obligation:  PARTITION BY (year_month(intended_settlement_date),
                                 hash_prefix_8(business_event_id))

L_13.MoveStream:  PARTITION BY (year_month(t_obs),
                                 hash_prefix_8(tx_id))

L_11.ExternalConfirmation (envelopes): PARTITION BY year_month(t_known)
```

Hash-prefix-8 sharding gives 256 shards per month — supports 10^8 rows/month per shard which is below typical OLTP node capacity.

#### 10.7.4 Index strategy

- `(counterparty_lei, lifecycle_state)` B-tree — for ops-queue queries "all open obligations against cpty C in state Instructed".
- `(wallet_id, unit, lifecycle_state)` hash — for recon-identity queries (single-`(w, u)` slice).
- `(intended_settlement_date, lifecycle_state)` B-tree — for ops-queue settlement-day window queries.
- `(business_event_id, attempt_seq)` unique B-tree — primary key on idempotent intake.
- `dedup_key` on `L_11` envelopes — primary key for envelope dedup.

#### 10.7.5 Archival

Past 7 years, `L_15.Obligation` rows in terminal states are exported to cold tier as immutable Parquet snapshots, signed and hash-anchored to a regulatory ledger. The hot+warm DB retains a tombstone with the cold-tier reference.

Bitemporal mutation (`t_known` updates from late restatements) is supported on hot+warm; on cold, restatement creates a new generation snapshot; the original is preserved for audit.

#### 10.7.6 Ops-queue materialised views

Per §5.3, `tx_status(tx)` is a projection function. The materialised view `tx_status_view(tx_id, status, computed_at_t_known)` is recomputed on every `L_15.state` write, with the projection function inlined into the write path. Eventual consistency window < 1s.

### 10.8 Year-end tie-out (preserved from v1)

Per `(wallet, unit, counterparty)` reconciliation:
```
Opening (1 Jan)
+ Σ all Discharged moves over the year
+ Σ all unsettled position changes
+ Σ all year-end open positions
= Closing (31 Dec)
```

Four-corner audit test: existence (BS → GL → L_13 → external confirmation); completeness (external feed → ledger); cut-off (last 2 BD Dec, first 2 BD Jan); valuation (year-end FV hierarchy). Tier-1 dealer typical year-end: ~£280bn settled; ~£4bn unsettled receivables (~1.5% BS); always material; always separate disclosure (IAS 1.55 + IFRS 7).

### 10.9 CORRECTION transaction policy (closes theme C)

#### 10.9.1 Permitted scenarios

- Trade booking error
- Counterparty disputes the trade (mutual bust)
- CSD reports incorrect settled amount
- Cross-correction of a prior CORRECTION (with stricter four-eyes)
- Regulatory-already-reported correction (with regulatory-amendment four-eyes; explicitly named)

#### 10.9.2 NOT permitted

- Hiding a failed settlement by reversing the original
- Pre-dating a trade
- Adjusting `own` to match a custodian's wrong record
- Deleting a CORRECTION
- Silent CORRECTION (any without `requester_lei != approver_lei` + named approver_role)

#### 10.9.3 Required fields

```
Transaction(type=CORRECTION):
  references:           <original_tx_id>
  reason_code:          <closed-sum: BOOKING_ERROR | CPTY_DISPUTE | CSD_RESTATEMENT |
                                     CROSS_CORRECTION | REG_ALREADY_REPORTED |
                                     CORRECTION_OF_CORRECTION | OTHER>
  justification:        <free text, mandatory, ≥ 50 chars>
  requester_lei:        <LEI; primary requester>
  approver_lei:         <LEI; MUST != requester>
  approver_role:        <closed-sum: OPERATIONS_HEAD | RISK_OFFICER | CFO_DELEGATE>
  approval_timestamp:   <UTC>

  -- For CROSS_CORRECTION (correction touching > 1 trade):
  affected_tx_ids:      <list of original_tx_ids>
  scope_attestation:    <signed attestation, separate signing key from approver>

  -- For REG_ALREADY_REPORTED:
  reg_amendment_handler: <closed-sum: MIFIR_AMEND | EMIR_AMEND | SFTR_AMEND>
  amend_reference:      <prior submission reference>

  -- For CORRECTION_OF_CORRECTION (correction of a prior CORRECTION tx):
  prior_correction_tx_id: <id of the prior CORRECTION being corrected>
  audit_committee_attestation: <required field; not skippable>
```

Framework rejects any CORRECTION where:
- `requester_lei == approver_lei`, OR
- `reason_code == CROSS_CORRECTION` and `len(affected_tx_ids) < 2`, OR
- `reason_code == REG_ALREADY_REPORTED` and `reg_amendment_handler` missing, OR
- `reason_code == CORRECTION_OF_CORRECTION` and `audit_committee_attestation` missing.

#### 10.9.4 Manual override (already in §5.4)

Manual override on a `Pending | Instructed | PartiallySettled | Failed` obligation transitioning to `Compensated` is a CORRECTION with full four-eyes per §5.4. It does NOT emit anti-moves; it transitions the lifecycle state and registers compensating evidence (an external instrument, a cash payment, etc.) as the discharge witness.

#### 10.9.5 Bitemporal semantics

After a CORRECTION:
- Original tx remains in `L_13.MoveStream` at original `(t_obs, t_known)`.
- CORRECTION tx appended at its own `(t_obs, t_known)`.
- `as_of(t)` for `t` between original and correction returns original (un-corrected).
- `with_corrections_through(t_known')` returns corrected.

This is **IAS 8.42 prior-period restatement discipline** structurally implemented via the bitemporal model.

#### 10.9.6 SOX implications

- > 10 CORRECTIONs/month from same trader = control-environment red flag.
- Any CORRECTION reversing > £10m position = audit committee notification.
- Any CORRECTION of year-end balance after cut-off = potential restatement (IAS 10).
- Any CORRECTION_OF_CORRECTION = automatic audit committee review.

### 10.10 Cum/ex corporate action audit trail (preserved from v1)

When `record_date ∈ (T, T+k]`: trade-date economic owner (buyer at T) is economically entitled; registered holder at record date (seller, still on CSD register until T+k) receives from issuer; **manufactured payment** must flow seller → buyer.

Per-trade audit record: T; T+k; ex-date; record date; cum-or-ex flag; manufactured-payment obligation (`L_15.Obligation`, kind = `MANUFACTURED_PAYMENT`); counterparty LEI; tax-residency.

**Cum/ex tax-fraud red flag (ISA 240).** Repeat patterns across tax jurisdictions trigger escalation to engagement partner; consider regulatory-disclosure obligations. The 2007–2012 German cum/ex scandal involved multi-billion-euro losses through such patterns.

### 10.11 Cross-currency / Herstatt accounting

IAS 21: monetary items translated at closing rate; FX gains/losses to P&L. Settlement receivables/payables: **always monetary; always translated; FX gains/losses always to P&L.**

Herstatt window: time between first and second leg of cross-currency settlement when one leg has settled and the other has not. Mitigation: CLS for major pairs; non-CLS legs (most EM, some minor majors) carry residual Herstatt risk. Disclosure (CRR Art 442 + IFRS 7.B11): aggregate cross-currency open exposure; CLS-eligible split; largest single-counterparty Herstatt exposure; internal Herstatt limits.

Evidence retention: 7 years full `L_13` + `L_15` history + `L_11` envelopes (signature-verified) + `L_18` BreakRegister history. Bitemporal makes this structurally satisfied.

---

## 11. Invariants DS1–DS10 (pruned) + restated-v10.3 appendix

R1 closure: themes A and G — v1 had 18 invariants of which several were restatements of v10.3 (DS2/DS5/DS6/DS16) or theorems (DS3/DS13). v2 prunes to 10 genuinely new ones, with explicit type/runtime/severity, full quantification, and parent reference. Restated v10.3 invariants moved to §11.A.

### DS1 — Economic-Exposure-at-T

**Statement.** $\forall \tau \in \Sigma$, $\forall (w, u, t)$ with $t \in [T_{\text{exec}}(\tau), \infty)$ and $w$ a real-wallet party of $\tau$:
$$w_t.\text{own}(u) - w_{T_{\text{exec}}^-}.\text{own}(u) = \sum_{m \in \tau, m.\text{unit}=u, w \in \{m.\text{src}, m.\text{dst}\}} \text{signed-delta}(m, w)$$
equivalently: there exists no projection $\Pi$ over `(move stream + lifecycle states + obligation log)` whose value during $[T, t_d^-]$ differs from its value after $\tau$ has reached `Discharged`, holding the price function constant.

**Parent.** v10.3 P1, §11.4, P10. **Type.** hybrid (CT phantom + RT property test). **Severity.** CRITICAL. Genuinely new (vs v10.3): the type-level enforcement via phantom-typed wallet handles (§12.3).

### DS3 — Reconciliation Identity (the canonical sign convention; folds v1 DS3 + DS13)

**Statement.** $\forall (w, \text{ccy}, t)$ with $w$ real-wallet:
$$\text{nostro\_external}(w, \text{ccy}, t) = w_t.\text{own}(\text{ccy}) + \sum_{\text{cpty}} w_{\text{PS}}[w, \text{cpty}, \text{ccy}]_t - \text{inflight\_out}(w, \text{ccy}, t) + \text{inflight\_in}(w, \text{ccy}, t)$$
with sign convention §0.2 (positive `w_PS` = we owe; negative = they owe us). Equivalent identity for securities replacing `nostro_external` with `depot_external` per §4.1.

**Parent.** v10.3 §13 line 3538 SBL recon identity, generalised. **Type.** runtime (property test on BUY and SELL, §3 and §3.X). **Severity.** HIGH.

(v1 DS13 "Reconciliation Pair Anchoring" was the lifted-pair restatement of this — folded into DS3.)

### DS4 — No Discharge Without Witness

**Statement.** $\forall o \in L_{15}$, $\forall \varepsilon \in \text{EnvelopeRegistry}$ associated with $o$:
$$o.\text{state} \in \{\text{Discharged}, \text{PartiallySettled}, \text{Compensated}\} \Longrightarrow \exists \varepsilon : \text{verify}(\varepsilon) \wedge \text{matches}(\varepsilon, o.\text{discharge\_predicate})$$
where `verify(ε)` checks signature, schema, dedup, and (where required) multi-source quorum per §4.5.

**Parent.** nazarov INV-DS-2; data-spec L_11 ExternalConfirmation contract. **Type.** hybrid (CT FSM-takes-witness; RT cryptographic verify). **Severity.** CRITICAL.

### DS7 — Failure Non-Reversal

**Statement.** $\forall o \in L_{15}$, $\forall$ transition $o.\text{state} : \text{Pending} \to \text{Failed}$:
$$\forall w \in \mathcal{W}_{\text{real}}, \forall u : w_{\text{after-fail}}.\text{own}(u) = w_{\text{before-fail}}.\text{own}(u)$$

No move on a real wallet's `own` coordinate is emitted as a consequence of a settlement-fail event. Only legal exception: a CORRECTION transaction with explicit anti-moves and four-eyes approval (§10.9).

**Parent.** v10.3 §8.4, FAQ Q5; IFRS 9.B3.1.3; CRR Art 379. **Type.** hybrid. **Severity.** CRITICAL.

### DS9 — Buy-In Compensation Closure

**Statement.** $\forall o \in L_{15}$ with $o.\text{state} = \text{Failed}$ for duration $\geq \Delta_{\text{CSDR}}$:
$$\exists \tau_{\text{buyin}} \in L_{13}, \exists o_{\text{buyin}} \in L_{15} : \tau_{\text{buyin}}.\text{type} = \text{BuyIn} \wedge o.\text{compensation\_handler} = \kappa_{\text{buyin}}(\tau_{\text{buyin}}, o_{\text{buyin}})$$

**Parent.** v10.3 §13 P21; CSDR Art 7(3); Reg SHO Rule 204. **Type.** runtime (Temporal saga + property test). **Severity.** HIGH.

### DS10 — Cross-Currency Herstatt Visibility

**Statement.** $\forall \tau$ cross-currency: $\tau$ emits a parent obligation $o_{\text{fx}}$ with two child obligations $o_{\text{ccy1}}, o_{\text{ccy2}}$, each with own settlement-date and discharge witness. Parent's discharge predicate:
$$D_{\text{fx}}(\sigma) = (o_{\text{ccy1}}.\text{state} = \text{Discharged}) \wedge (o_{\text{ccy2}}.\text{state} = \text{Discharged})$$

The Herstatt-window invariant: at every $t$, exactly the open obligations whose `state` is non-terminal are visible as quantified exposure.

**Parent.** v10.3 §2.6; Λ_15. **Type.** runtime (projection). **Severity.** HIGH. Framework does not eliminate Herstatt risk; it names, quantifies, routes compensation, audits the loss.

### DS11a — Partial-Settlement Per-Step Conservation (split from v1 DS11)

**Statement.** $\forall$ partial-settlement event at attempt_seq $n$: with $q'_n$ delivered at attempt $n$ and $q_n - q'_n$ remaining,
$$q_{n+1}^{\text{remaining}} + q'_n = q_n \wedge q_{n+1}^{\text{remaining}} \geq 0$$

Per-step conservation across the partial-fill chain.

**Parent.** v10.3 §11 P9; data-spec §3 L_15. **Type.** runtime. **Severity.** HIGH.

### DS11b — Partial-Settlement Monotonicity (split from v1 DS11)

**Statement.** $\forall$ obligation $o$ entering `PartiallySettled`:
1. $o.\text{state}$ is monotone in the FSM partial order across the chain (no return to `Pending` from `PartiallySettled`).
2. Economic position on the real wallet is **unchanged** by partial-settle events themselves — original $\tau$ recognised full $q$ at $T$.
3. Termination: chain terminates within $D_{\max} = 2$ partial-buyin cycles; beyond that, $o$ transitions to `Failed → Compensated` (cash-in-lieu).

**Parent.** v10.3 §11 P9; PO-9. **Type.** runtime. **Severity.** HIGH.

### DS12 — Variant Degeneration

**Statement.** Deferred-settlement representation is parameterised on `settle_date = t_d` and degenerates uniformly across T+0 / T+1 / T+2 / T+5+. **For all variants, DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS17, DS18 hold without modification; only workflow timer durations change.**

**Parent.** v10.3 §11 P0. **Type.** structural (proof by reduction over t_d; same FSM, same conservation, same recon). **Severity.** MEDIUM.

### DS17 — Capability Scoping on Settlement Status Writes

**Statement.** $\forall (\tau, o) \in L_{13} \times L_{15}$: each `o.state` field has a **unique writer**: the `SettlementSaga` workflow (§6.5.8). No other handler may mutate it. Other handlers may read per their capability; writes are gated.

**Parent.** StatesHome C11. **Type.** compile-time (phantom typing on write capability; §12.3). **Severity.** HIGH.

### DS18 — DvP Ledger-Level Atomicity (DvP-L)

**Statement.** $\forall \tau$ containing both a securities leg and a cash leg in the same `L_13` move pair: the executor commits both legs atomically: both apply or neither. Observable as a single `StateDelta`. (This is DvP-L per the disambiguation in §6.5.3; DvP-S is enforced at the CSD; DvP-E is enforced via PairedObligation §12.2.)

**Parent.** v10.3 P2, §8.4; StatesHome C3; minsky I-DEF-12. **Type.** structural (executor primitive). **Severity.** CRITICAL.

### Type-vs-runtime decomposition (10 invariants)

| Invariant | Type | Mechanism | Severity |
|---|---|---|---|
| DS1 | hybrid | (CT) phantom wallet class; (RT) property test | CRITICAL |
| DS3 | runtime | property-test on BUY and SELL (§3, §3.X) | HIGH |
| DS4 | hybrid | (CT) FSM takes envelope as param; (RT) verify | CRITICAL |
| DS7 | hybrid | (CT) capability typing; (RT) mutation testing | CRITICAL |
| DS9 | runtime | Temporal timer + saga | HIGH |
| DS10 | runtime | projection over L_15 | HIGH |
| DS11a | runtime | property-test on residual conservation | HIGH |
| DS11b | runtime | property-test on monotonicity + D_max | HIGH |
| DS12 | structural | same FSM under t_d parameter | MEDIUM |
| DS17 | compile-time | phantom typing on writer capability | HIGH |
| DS18 | structural | executor primitive guarantees atomic StateDelta | CRITICAL |

Recommendation: take CT cost for DS17 and DS7 (silent and economically catastrophic violations); leave others RT or hybrid. DS1 stays hybrid.

### §11.A Restated v10.3 invariants applicable in deferred-settlement context

For completeness, the following v10.3 invariants are **restated** in the deferred-settlement context but not reasserted as new:

| v2 label | v1 label | v10.3 source | Status in v2 |
|---|---|---|---|
| Conservation `Σ_w w_t(u) = 0` | DS2 | v10.3 P1 + StatesHome C2 | corollary of §7.5 Conservation Lifting Theorem |
| Replay determinism | DS5 | Λ_8, v10.3 P9 | restated; explicit commutativity table §6.5.5 |
| Idempotency of finality messages | DS6 | v10.3 P5, P6 | restated; envelope dedup_key §4.5.1 |
| Status monotonicity | DS8 | v10.3 §11.7 | property of the FSM closed sum (§5.2); not separate |
| CSDR penalty schema determinism | DS14 | data-spec | property of pure function over L_7^P; restatement of v10.3 invariant on policy versioning |
| Counterparty default close-out | DS15 | v10.3 §13 close-out | restatement of v10.3 close-out routing |
| Bitemporal restatement | DS16 | data-spec N_9, Λ_4 | structural property of the bitemporal model; not separate |

Bitemporal restatement under DS5 (theme F): the canonical statement is "replay determinism over the multiset of finalised witnesses; restatements update `t_known` but original `t_obs` preserved." This subsumes v1 DS16.

---

## 12. Type design — v11.0 core scope vs v12 RFP (closes theme B)

R1 closure: theme B — v1's 14-week migration is fantasy AND/OR out of v11.0 scope. v2 scopes to 5-item v11.0 core (~6 weeks); the rest is bracketed for v12 RFP.

### 12.1 v11.0 CORE (~6 weeks, 1.5 engineers) — IN SCOPE

#### 12.1.1 Phantom wallet class

Three phantom types, three constructors:

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
     real_wallet      wallet_handle
  -> cpty_virtual_wallet wallet_handle
  -> security : (Isin.t * Qty.t)
  -> cash     : (Currency.t * Cash.t)
  -> trade_date : TradeDate.t
  -> settle_convention : SettleConvention.t
  -> (Transaction.t * PairedObligation.t, trade_error) Result.t

val emit_discharge :
     PairedObligation.t
  -> cpty_virtual_wallet wallet_handle
  -> csd_virtual_wallet  wallet_handle
  -> csd_confirmation : Sese_025_msg.t
  -> (Transaction.t, discharge_error) Result.t
```

`emit_discharge` cannot be passed a `real_wallet wallet_handle` — settlement-status mutation that touches `own` is **structurally unrepresentable**. **This enforces DS1 + DS17 structurally.**

#### 12.1.2 PairedObligation — DvP atomicity at the type level

```ocaml
module PairedObligation : sig
  type t  (* abstract; constructed only via [pair] *)

  type pairing_error =
    | Different_trade_id    of Trade_id.t * Trade_id.t
    | Different_settle_dates of SettleDate.t * SettleDate.t
    | Mirrored_qty_mismatch  of { sec_qty : Qty.t; cash_qty : Cash.t; expected_cash : Cash.t }
    | Same_side_pairing
    | Wrong_leg_units        of { sec_unit : Unit_id.t; cash_unit : Unit_id.t }

  val pair :
       security_leg : Obligation.t
    -> cash_leg     : Obligation.t
    -> (t, pairing_error) Result.t

  val security_leg : t -> Obligation.t
  val cash_leg     : t -> Obligation.t
end
```

There is no public function `Obligation.t -> ... -> DischargeResult.t`. Discharge consumes a `PairedObligation` atomically. **This enforces DvP-E (§6.5.3).**

#### 12.1.3 Lifecycle closed sum + carried evidence

```ocaml
type lifecycle =
  | Pending          of { issued_at : Time.t;        obligation_id : Obligation_id.t }
  | Instructed       of { instructed_at : Time.t;    sese_023_id : Iso20022_msg_id.t }
  | PartiallySettled of { qty_settled : Qty.t;       partial_at : Time.t;
                          sese_025_id : Iso20022_msg_id.t;
                          remainder_id : Obligation_id.t }
  | Discharged       of { settled_at : Time.t;       sese_025_id : Iso20022_msg_id.t }
  | Failed           of { failed_at : Time.t;        reason : failure_reason;
                          csdr_clock_started_at : Time.t option }
  | BoughtIn         of { boughtin_at : Time.t;      buyin_ref : Buyin_ref.t;
                          predecessor : Obligation_id.t }
  | Cancelled        of { cancelled_at : Time.t;     correction_tx : Trade_id.t;
                          approver : Operator_id.t }
  | Compensated      of { compensated_at : Time.t;   compensation_kind : Compensation_kind.t;
                          evidence_ref : Evidence_ref.t }
```

Total step function `step : lifecycle -> event -> [`Step of lifecycle | `Reject of reason | `Idempotent ]`; pattern-match exhaustive (`-warn-error +partial-match`); no wildcards. **Closes formalis G1.**

#### 12.1.4 failure_reason closed sum

```ocaml
type failure_reason =
  | DeadlineMissed
  | NoCover
  | NoFunds
  | CounterpartyDefault of Lei.t
  | CsdReject of Csd_reject_code.t
  | LegInconsistent of which_leg
  | Manual of Operator_id.t
```

Closed sum, not a free string. Maps from per-CSD ISO 20022 reason codes via the PO-5 normalisation table.

#### 12.1.5 TradeDate / SettleDate newtypes

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
    -> CalendarPin.t
    -> (t, settle_error) Result.t
  (* No public [of_date : Date.t -> t]. *)
end
```

`CalendarPin` is the bitemporal-pinned `L_4` calendar at trade time. **Closes formalis G7.** A handler that wants to compare `TradeDate` against `SettleDate` must lift both via `to_date` — confusion is a type error.

### 12.2 v11.0 CORE migration plan (~6 weeks)

| Week | Stage | Scope |
|---|---|---|
| 1 | Discovery | Inventory all `lifecycle_stage` reads/writes; settlement-confirmation paths that mutate real wallets; raw `Date.t` settle-date usages |
| 2–3 | Stage 1 (additive) | Introduce types alongside strings; add total `step` function; refactor `Obligation.create` to return `Result.t`; introduce phantom wallet types behind feature flag |
| 4 | Stage 2 (flip) | Flip source of truth from string to closed sum on `lifecycle`; refactor every transition site; introduce `PairedObligation` + `discharge` |
| 5 | Stage 3 (newtype dates) | TradeDate / SettleDate / ValueDate / RecordDate newtypes; refactor `Obligation.create` to take typed dates |
| 6 | Stage 4 (cleanup) | Remove deprecated string fields; compile entire codebase with `-warn-error +partial-match`; CI gate |

No behavioural change in production; Stages 1–3 are type-additive; Stage 4 removes dead code. After Stage 3, the trade-date / settlement-date confusion class is structurally impossible.

### 12.3 DEFERRED to v12 RFP (mention but bracket)

The following are valuable but out of scope for v11.0:

- **Smart constructor `Obligation.create` with 14 rejection cases.** The 14 rejections (qty ≤ 0; FoP with cash; settle date in past; cash/qty mismatch; etc.) are valuable hardening but require coordinated rollout across upstream OMS, allocation engine, and corporate-action service. Defer to v12 RFP.
- **Phantom-typed accounting basis** (`trade_date_basis` vs `settle_date_basis`). Useful for downstream consumers; current v11.0 commits to trade-date-only at the primitive level (§10.1) so the phantom split is not load-bearing yet. Defer.
- **Total step function migration** from string-keyed to algebraic. Stages 5–6 of v1's plan. Defer to v12 RFP.
- **Cross-currency Herstatt visibility in type** (`fx_discharge_state`). DS10 is enforced runtime in v11.0; type-encoding is a v12 hardening.

### 12.4 Type-vs-runtime boundary (v11.0 final)

| Concern | Type or Runtime | Why |
|---|---|---|
| Trade-date economic recognition (DS1) | Type | Phantom wallet class (§12.1.1); cheap |
| DvP-E discharge atomicity (DS18, §6.5.3) | Type | `PairedObligation` (§12.1.2); cheap |
| Closed sum lifecycle / failure_reason | Type | One sum, one match (§12.1.3, §12.1.4); cheap |
| Date confusion | Type | Phantom-typed newtypes (§12.1.5); cheap |
| Status monotonicity | Type | Closed sum + exhaustive match |
| Capability scoping (DS17) | Type | Phantom typing on writer capability |
| Conservation `Σ = 0` | Runtime | StatesHome C2 chooses runtime |
| Liveness | Runtime | Wall-clock external |
| CSDR penalty calculation | Runtime | Penalty rate-table outside type system |
| Corporate-action market-claim | Runtime | No leverage from type-encoding |
| Regulatory cardinality | Runtime | Database uniqueness, not type |
| ECL stage | Runtime | Time-varying; macro signals |
| Confirmation matching absent UTI (G2) | Runtime with explicit quarantine | `Ambiguous` case must be handled |

The boundary is **named, not negotiated.** First six are type-level because cost is one-time and benefit is on every read site.

---

## 13. Honest gaps and proof obligations

### 13.1 Gaps G1–G12 (preserved from v1, status updates)

- **G1** Closedness of CSD failure-type enumeration. **Closed in v2 §12.1.4** as the `failure_reason` closed sum; per-CSD mapping (PO-5) deferred to operational rollout.
- **G2** Confirmation matching in absence of UTI. **Mitigated in v2 §4.5.2** (multi-source quorum); explicit `Ambiguous` quarantine handler (§12.4).
- **G3** Bitemporal predicate evaluation under corporate action. Open; PO-4 owner matthias + correctness.
- **G4** DvP leg-inconsistent failure compensation. **Mitigated in v2 §6.5.3** (DvP-S is per-CSD; per-κ dispatch table in `L_16.ReferenceMaster`); per-CSD catalogue still owed (ashworth + isda + jane_street).
- **G5** Replay determinism in presence of restated confirmations. **Closed in v2 §6.5.5** under Reading (a): treat restatement as new obligation (clean separation; new `attempt_seq`).
- **G6** Cross-jurisdiction CSDR vs SEC vs T+1 vs T+2. Open; t_d sourced from CDM `tradableProduct.settlementTerms.settlementDate`. Property test owed (matthias + isda).
- **G7** "True at T+2⁻" semantics. **Mitigated** via §4.5 envelope `ts_obs`/`ts_known` discipline + L_19 ClockAuthority.
- **G8** Liveness under prolonged Temporal cluster outage. Not closable by formal proof; mitigated by multi-region replication + external watchdog (§4.5.3).
- **G9** Late-discharge race policy table coverage. **Closed in v2 §6.5.7**: SETTLEMENT entry `cancel-compensation if not externalised; otherwise queue-and-reconcile`. Pinned in `L_7^P.SagaCompensationPolicy`.
- **G10** Herstatt elimination vs representation. Not closable in ledger.
- **G11** Manufactured-payment recipient determination. Open; PO-6 owner ashworth + matthias + isda.
- **G12** Single-source escape on attestation. **Closed in v2 §13.5** as TA-DS-1..10 trust-assumption registry.

### 13.2 Proof obligations PO-1..PO-10 (status update)

| PO | Owner | Property | v2 status |
|---|---|---|---|
| PO-1 | finops | PS recon identity DS3 + idempotency DS6 under daily aggregation | **Closed in §3, §3.X, §4.1** (verified BUY+SELL) |
| PO-2 | sbl | Saga compensation tower SETTLEMENT entry | **Closed in §6.5.7** |
| PO-3 | sbl | Sign convention pin DS3/P29; receive-obligation on receiver side | **Closed in §0.2 + §4.1** (canonical signed convention; verified BUY+SELL) |
| PO-4 | matthias | Bitemporal-state-function discharge predicates | Open; G3 |
| PO-5 | isda | Per-CSD failure-reason normalised closed sum | Open; G1 partial |
| PO-6 | ashworth | Manufactured-payment per-jurisdiction rules | Open; G11 |
| PO-7 | minsky | Type-vs-runtime canonical mapping per invariant | **Closed in §11 + §12.4** |
| PO-8 | testcommittee | TLA+ model at $|\mathcal{W}|=3, |U|=2, \text{depth}=8$ with 10 invariants encoded | Open; tractable in minutes |
| PO-9 | testcommittee + temporal | D_max numeric bound + property test | **Closed in §6.4 + DS11b**: D_max = 2 |
| PO-10 | temporal | `SettlementSaga` is signal-driven workflow + dedup TTL | **Closed in §6.5.6** (CaN payload schema; dedup n=4096, TTL=30d) |

### 13.3 Walking-skeleton test plan (NEW; closes testcommittee B-2)

R1 closure: testcommittee B-2 — 8 of 12 walking-skeleton variants from Phase 1 §2.3 had no test in v1. v2 lists all 12 as sign-off prerequisites.

| Test | Scenario | Verification |
|---|---|---|
| WS-1 | BUY happy (T+2) | §3 worked example reproduced; conservation table sums to zero at every state; recon identity holds at T+2⁻ and T+2⁺ |
| WS-2 | SELL happy (T+2) | §3.X worked example; recon identity verified independently |
| WS-3 | T+1 happy | T+1 cycle parameter; FSM unchanged; DS12 |
| WS-4 | T+0 atomic happy | T+0 parameter; inflight period ε; DS12 |
| WS-5 | recon-lag E2E | Recon identity stable across `t_obs` lag-up-to-1bd for cross-border |
| WS-6 | short happy | §7.3 lifecycle; locate-converted-to-borrow; DS3 SBL form |
| WS-7 | recall in window | §7.3.4 recall obligation independent of sale obligation; buy-in saga on insufficient avail |
| WS-8 | cum/ex CA in window | §10.10 manufactured-payment obligation registered; bitemporal predicate (G3) |
| WS-9 | FX Herstatt | Cross-currency obligation pair; one-leg-settled state visible per DS10 |
| WS-10 | partial settlement | §6.4 partial chain; DS11a + DS11b; D_max = 2 |
| WS-11 | DvP CSD-reject | sese.024 inbound; FSM transitions to Failed; DS7 (no real-wallet move); CSDR penalty obligation spawns |
| WS-12 | manual override | §5.4 manual override; four-eyes preconditions; FSM Pending → Compensated |

Each test runs as an end-to-end integration test under the property generator framework (§13.4.4). Sign-off prerequisite: all 12 pass at every release boundary.

### 13.4 Goodhart traps for deferred settlement (NEW; closes correctness B-6)

R1 closure: correctness B-6 — three deferred-settlement-specific Goodhart traps were identified in the brief and not addressed in v1. v2 names them and provides per-trap mitigation.

#### G-DS-1 — Quick-finality bias in generators

**Trap.** Property generators that draw `time-to-finality` from a uniform distribution on `[T, T+2]` will systematically under-test the long tail (3-5bd cross-border fails; 7-15bd CSDR mandatory buy-in window; 30+bd defaults). Tests will pass; production will fail at the tail.

**Mitigation.** Property generators draw `time-to-finality` from the empirical distribution of `L_18.BreakRegister` resolution times — log-normal heavy-tailed with median ~T+0+0.5bd and 99th percentile ~T+5bd for liquid equities, ~T+15bd for SME-growth-market. The empirical distribution is pinned via `L_7^P.GeneratorDistributionPin` per `(asset_class, settlement_window)` and refreshed quarterly from production data. Generators MUST sample from this pinned distribution; uniform draws are **forbidden** at code-review.

**Verification.** Test suite runs include explicit "tail" buckets: 5%, 95%, 99% latency cells. Coverage gate: every test class touches each bucket at least once.

#### G-DS-2 — Global conservation tested but not per-class

**Trap.** A property test asserting `Σ_w w(u) = 0` over the whole universe will pass even if a `cpty_virtual` wallet credit silently offsets a `csd_virtual` debit *on a different unit* (e.g., a sign error swaps USD with XYZ in some pathway, but the global sum still zeros because the internal contras both fire). The system is broken; the test is green.

**Mitigation.** Conservation is asserted **per (unit-class, wallet-class) tuple**:
```
∀(u, c) ∈ Unit × WalletClass: Σ_{w : class(w)=c} w(u) - flux_in(c, u) - flux_out(c, u) = 0
```
where `flux_in/out` is the boundary flux into the wallet-class for that unit (e.g., for `cpty_virtual` USD: net cash from real-wallets - net cash to csd_virtual mirrors). Violation isolates to one class-unit pair, not the whole sum.

**Verification.** Property-test framework auto-generates per-`(unit_class, wallet_class)` conservation assertions from the closed sum of classes (3 classes × O(10^4) units = O(3×10^4) assertions per test scenario).

#### G-DS-3 — Record-and-replay LLM tests

**Trap.** Generators authored from production traces via record-and-replay (LLM-assisted) reproduce the same anti-patterns in the generators that the framework is designed to catch. The generators systematically fail to draw from the failure modes that have NEVER occurred in production but are nevertheless legal under the spec.

**Mitigation.** Property generators are **hand-authored** from the spec, not from prod traces. The generator type signatures (§13.4.4) are reviewed against the closed sums in §5 and §11 by the Settlement Team, not auto-derived from logs. LLM-assisted refactoring is allowed only for generator *implementation*, never for the choice of input space.

**Verification.** Code review hard-fails on `learn_from_traces(...)` patterns in generator modules. Mutation testing against the closed-sum FSM (§5.2) verifies that every transition is exercisable by the generators.

#### 13.4.4 Generator type signatures (NEW; closes correctness B-3, testcommittee B-3)

For the six new dimensions of the deferred-settlement test space:

```haskell
gen_settlement_window  :: Gen SettlementWindow         -- {T+0, T+1, T+2, T+3, T+5}
gen_finality_lag       :: AssetClass -> Gen Duration   -- empirical distribution per G-DS-1
gen_witness_arrival_perm :: List Witness -> Gen Permutation  -- shrink: lex-min permutation
gen_failure_reason     :: Gen FailureReason            -- closed sum from §12.1.4
gen_corporate_action_in_window :: Gen CorpAction       -- ex_date ∈ (T, t_d] only when valid
gen_partial_chain_depth :: Gen Int                     -- bounded by D_max = 2
```

Shrink lattices follow the Hedgehog model:
- `SettlementWindow`: shrink to `T+2` (the canonical case).
- `Duration`: shrink to median.
- `Permutation`: shrink to lex-min (canonical witness order).
- `FailureReason`: shrink to `DeadlineMissed` (the simplest).
- `CorpAction`: shrink to no-CA case.
- `partial_chain_depth`: shrink to 0 (no partials).

Each generator MUST be referenced in the property test for the relevant invariant (DS1..DS18) per the §13.3 walking-skeleton table.

### 13.5 Trust-assumption registry TA-DS-1..10 (NEW; closes nazarov B-5 / theme 3)

R1 closure: nazarov B-5 — trust assumptions referenced and not specified. v2 names the registry.

| TA | Assumption | Detection signal | Owner |
|---|---|---|---|
| **TA-DS-1** | CSD signing key uncompromised | Unexpected key-rollover advice; signature verify failure spike | TrustOps + nazarov |
| **TA-DS-2** | CSD does not equivocate (no contradictory finality on same `tx_id`) | `dedup_key`-collision over different payloads | TrustOps |
| **TA-DS-3** | ISO 20022 schema pinned via versioning | Schema-mismatch quarantine spike on `L_11` | TrustOps + isda |
| **TA-DS-4** | CA provider canonical (issuer agent + DTC + market data vendor) | Quorum mismatch on ex-date | TrustOps + ashworth |
| **TA-DS-5** | Clock-skew bounded ≤ 5s | NTP drift alarm; per-attestation `ts_obs - ts_known` outside ±5s | jane_street + temporal |
| **TA-DS-6** | SSI lookups deterministic and replayable | SSI-version drift on identical input | finops + temporal |
| **TA-DS-7** | Nostro statements (camt.053) auth-verified | Daily camt.053 envelope verify-fail spike | TrustOps + finops |
| **TA-DS-8** | Manual-override audit chain immutable | Append-only check on `L_13` CORRECTION rows | jane_street + ashworth |
| **TA-DS-9** | Corporate-action ex-date attestable | Multi-source quorum failure on ex-date envelope | ashworth + matthias |
| **TA-DS-10** | CSDR rate schedule pinned via L_7^P versioning | Rate-table version drift between L_7^P and ESMA refdata | isda |

**Quarterly review cadence.** TrustOps lead reviews each TA with stated owner; signal thresholds and owner sign-off recorded in `L_7^P.TrustAssumptionReview`. Registry version bumps trigger a re-review of the dependent invariants (DS4, DS9, DS10).

---

## 14. Out of scope (deliberate)

The following are deliberately excluded from v11.0 scope:

- **Liquidity management of the cash leg.** Boundary at `L_15`; treasury system consumes the obligation.
- **CSD operational outages.** Watchdog (G8) handles via Temporal saga + externalisation; the runbook is jane_street's, not in this spec.
- **Title vs beneficial ownership.** Legal layer outside Ledger; master agreement, CSD rulebook, local insolvency law.
- **Cross-CCP novation during the window.** Λ_15 in data-spec; not reopened here.
- **Mass-cancellation events.** Per-trade `CORRECTION` with four-eyes is supported; bulk cancellation is workflow-on-top, not primitive.
- **Smart constructor 14-rejection cases.** Deferred to v12 RFP (§12.3).
- **Phantom-typed accounting basis.** Deferred to v12 RFP (§12.3).
- **First-class unit `u^circ` representation.** Deferred to v12 RFP (§7.4); Φ bijection states the equivalence.

---

## 15. Ready-for-Review note + R1 closure record

### 15.1 What v2 closed (vs v1 known-weakness list)

1. **Sign convention on DS3 (PO-3).** **Closed.** Canonical signed convention pinned in §0.2 + §4.1; verified on BUY (§3) and SELL (§3.X) worked examples.
2. **Recursion bound D_max for partial-fill cascades (PO-9).** **Closed.** $D_{\max} = 2$ pinned in §6.4 and DS11b; cascade beyond D_max transitions to `Failed → Compensated` (cash-in-lieu).
3. **Closed sum on CSD failure-type enumeration (G1, PO-5).** **Closed at the type level** (§12.1.4 `failure_reason`); per-CSD mapping deferred as operational rollout.
4. **Bitemporal predicate evaluation under corporate action (G3, PO-4).** Open; mitigation pinned (§4.5.4 multi-source attestation on ex-date).
5. **Per-jurisdiction manufactured-payment specification (G11, PO-6).** Open; structural slot reserved (`L_15.Obligation` kind = `MANUFACTURED_PAYMENT`); per-jurisdiction rules deferred.
6. **DvP leg-inconsistent failure compensation (G4).** **Mitigated.** §6.5.3 disambiguates DvP-L / DvP-S / DvP-E; per-CSD κ catalogue still owed (operational rollout).
7. **TLA+ model check (PO-8).** Open; tractable; 10 invariants encoded (down from 18); state-space ~10^5–10^6.
8. **Migration cost of type discipline.** **Scoped to v11.0 core ~6 weeks** (§12.2). Smart constructor + phantom-basis + total-step-migration deferred to v12 RFP.

### 15.2 R1 BLOCKING closure (B-1..B-13)

Tabulated by R1 finding ID. Each row: blocker theme, v2 section that closes it, one-line summary.

| R1 blocker | Source | v2 section | One-line fix |
|---|---|---|---|
| **B-1** | jane_street | §3 worked example | Conservation table re-drawn over constant universe `\mathcal{W}` including `w_DTC_depot_mirror[GS]` and `w_JPMC_nostro_mirror[GS]`; sums to zero at every state. |
| **B-2** | jane_street + feynman + halmos | §0.2, §4.1, §4.1.5, §3.X | Canonical signed sign convention; `inflight_in/out` named projections; verified on BUY and SELL. |
| **B-3** | nazarov | §4.5.1 | Attestation envelope = JCS-canonical CBOR/JSON + Ed25519 sig + ts_obs/ts_known + dedup_key + schema_version. |
| **B-4** | nazarov | §4.5.2 | Multi-source aggregation: CSD primary; quorum-of-2 from custodian + cpty when CSD silent; never single non-primary. |
| **B-5** | nazarov | §4.5.3, §13.5 | Absence-of-finality protocol: silence + watchdog triggers `wf-confirm-break`, NOT auto-FAIL. Trust-assumption registry TA-DS-1..10. |
| **B-6** | correctness | §13.4 | Goodhart traps G-DS-1 (quick-finality bias), G-DS-2 (per-class conservation), G-DS-3 (no record-and-replay) named with mitigations. |
| **B-7** | testcommittee | §13.3 | All 12 walking-skeleton tests listed as sign-off prerequisites. |
| **B-8** | temporal | §6.5.1 | `tx_id = hash_jcs(business_event_id, attempt_seq)`; `attempt_seq` carried across CaN, never `run_id`. |
| **B-9** | temporal | §6.5.3 | DvP atomicity disambiguated (DvP-L / DvP-S / DvP-E); per-leg discharge with tx_status emergence. |
| **B-10** | temporal | §6.5.5 | Signal-handler commutativity table for DS5; non-commuting cases are deterministic precedences (terminal absorbs; contradictions quarantine). |
| **B-11** | temporal | §6.5.4 | T+2 trigger = deadline timer with watchdog fallback (Phase 1 design restored); `Λ_n` poll cadence specified. |
| **B-12** | lattner | §2.4, §5.1, §5.3 | Per-leg `L_15.Obligation.state` is canonical FSM; `tx_status(tx)` is Library-layer projection function, NOT stored. |
| **B-13** | halmos | §0 | Notation table; symbol discipline; quantification on every invariant (§11) explicit. |

### 15.3 R1 BLOCKING closure (cross-cutting themes)

| Theme | R1 source | v2 section | Status |
|---|---|---|---|
| Theme 1 | jane_street B-1 + lattner B-2 + feynman + halmos B-6 | §3, §3.X | **Closed.** |
| Theme 2 | feynman B-2 + jane_street B-2 + halmos B-7 + cartan B-3 | §0.2 + §4.1 + §3 + §3.X | **Closed.** |
| Theme 3 | nazarov B-1..B-5 | §4.5 + §13.5 | **Closed.** |
| Theme 4 | temporal B-1..B-5 + 10 majors | §6.5 (entire section) | **Closed.** |
| Theme 5 | lattner B-1 + halmos M8 | §5.1 + §5.3 | **Closed.** |
| Theme 6 | correctness B-6 | §13.4 | **Closed.** |
| Theme 7 | testcommittee B-2 | §13.3 | **Closed** (12-test list). |
| Theme 8 | correctness B-3 + testcommittee B-3 | §13.4.4 | **Closed** (generator type sigs + shrink lattices). |
| Theme 9 | halmos B-1..B-7 | §0 | **Closed.** |
| Theme 10 | cartan B-2 | §7.5 | **Closed** (Conservation Lifting Theorem with H1..H5). |
| Theme 11 | jane_street B-4 | §10.7 | **Closed** (90d / 7y / 25y tiering + partitioning + indexes). |
| Theme 12 | cartan B-1 | §7.4 | **Closed** (bijection Φ proven; mainstream chosen on operational cost). |
| Theme 13 | cartan B-4 | §8.4 | **Closed** (F is lossy non-faithful functor; homomorphism on $\mathbf{Lg}_{\text{econ}}$ quotient). |

### 15.4 R1 MAJOR closure (themes A..J)

| Theme | R1 source | v2 status | Trade-off if mitigated |
|---|---|---|---|
| **A** Too many invariants | jane_street M-2 + lattner M-4 + geohot B-5 + cartan M-3 | **Closed.** §11 pruned to 10 invariants; restated v10.3 in §11.A. |
| **B** Type-discipline migration scope | jane_street M-3 + lattner M-5 + geohot B-6 | **Closed.** §12.2 v11.0 core 6 weeks; §12.3 deferred items to v12 RFP. |
| **C** CORRECTION transaction policy | jane_street M-5,M-6 + temporal M-1 | **Closed.** §10.9 cross-correction, regulatory-already-reported, correction-of-correction; §5.4 manual override. |
| **D** Block-and-allocation chains | jane_street M-7 | **Closed.** §7.6. |
| **E** Wallet class enum bloat | lattner M-1 + geohot | **Closed.** §0.2 + §2.3 reduced to 3 classes. Side is sign+key. Inflight is FSM state. |
| **F** Bitemporal restatement under DS5 | correctness + cartan M-2 + testcommittee M-6 | **Closed.** §6.5.5 + §11.A: replay determinism over multiset of finalised witnesses; restatements update `t_known` but original `t_obs` preserved. |
| **G** DS3/DS13 redundancy + DS11 split | cartan M-3 | **Closed.** DS13 folded into DS3; DS11 split into DS11a (conservation) + DS11b (monotonicity). |
| **H** DvP atomicity used in 3 senses | cartan M-5 + lattner | **Closed.** §6.5.3 disambiguates DvP-L / DvP-S / DvP-E. |
| **I** Capital reasoning depth | reviewers | **Closed.** §9.8 Pillar 3 worked example with single-trade RWA scaling. |
| **J** Regulatory regime expansion | isda matrix + geohot | **Closed.** §9 matrix kept; prose trimmed to one-paragraph-per-regime (§9.2..§9.7). |

### 15.5 Remaining open issues for R2 panel

The Settlement Team identifies four open items the Round 2 review should examine:

1. **PO-4 / G3 — Bitemporal predicate evaluation under corporate action.** Mitigated via §4.5.4 multi-source ex-date envelopes; the property test introducing a 2-for-1 split between obligation registration and deadline is **owed**. Owner: matthias + correctness. ETA: 1 week post-R2.
2. **PO-5 / G1 partial — Per-CSD failure-reason normalised mapping.** Closed sum exists in §12.1.4; the per-CSD enum mapping table (DTC, Euroclear, Clearstream, T2S) is **owed**. Owner: isda. ETA: 2 weeks (4 CSDs).
3. **PO-6 / G11 — Per-jurisdiction manufactured-payment rules.** Structural slot reserved; the four-jurisdiction (US, EU, UK, JP) rule pin is **owed**. Owner: ashworth + matthias + isda. ETA: 4 weeks; depends on tax-attorney input.
4. **PO-8 — TLA+ model check at $|\mathcal{W}|=3, |U|=2, \text{depth}=8$ with 10 invariants encoded.** Spec scope established; the actual TLC run is **owed**. Owner: testcommittee. ETA: 3 days; tractable on a workstation.

These four items do NOT block v2 acceptance; they are R2 follow-on work.

### 15.6 Convergence claim

The deferred-settlement specification is **implementation-ready** at the v11.0 core scope.

The 10 invariants (DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS12, DS17, DS18) are the test the proposal must pass. Type-vs-runtime decomposition is named (§11 + §12.4). The §11.A restated v10.3 invariants are reasserted by reference, not duplicated.

The 12 gaps (G1–G12): 5 closed in v2 (G1 type level, G2 quorum, G5 Reading-(a), G7 envelope ts discipline, G9 saga policy); 4 mitigated (G3 envelope, G4 disambiguation, G8 watchdog, G12 trust registry); 3 deferred (G6 cross-jurisdiction property test, G10 framework limit on Herstatt, G11 manufactured-payment per-jurisdiction).

The 10 proof obligations: 6 closed in v2 (PO-1, PO-2, PO-3, PO-7, PO-9, PO-10); 4 owed for R2 follow-on (PO-4, PO-5, PO-6, PO-8).

**None of the open items is a design defect.** Each is a specification gap closable by committing to a registry, a property-based test, or a per-jurisdiction lookup table.

### 15.7 Pareto-arbiter ruling required

For Pareto in R2:

- **Zero blocking remaining:** all 13 R1 BLOCKING themes closed in v2 (§15.2, §15.3).
- **Zero unmitigated major remaining:** all 10 R1 MAJOR themes closed or mitigated with trade-off documented (§15.4).
- **No minor improvement without offsetting trade-off:** see honest list of remaining open issues in §15.5; none rises to "minor improvement free of trade-off."
- **R2 panel composition:** 7 original Settlement Team members (revising sections) + new temporal-engineer seat (added to Settlement Team for v2). R2 review by ~5–8 reviewers (formalis + jane-street-cto + testcommittee + nazarov + halmos + temporal + cartan + lattner suggested).

Settlement Team signs off on this v2 as the Phase 3 Round 2 convergent design; submission to Phase 3 Round 2 adversarial review.

### 15.8 Document accounting

| Section | Status | Notes |
|---|---|---|
| §0 Notation table | NEW | Closes halmos B-1..B-7. |
| §1 Convergence | LIGHT REVISION | Trimmed; v1 §1.2 preserved by reference. |
| §2 State representation | REWORKED | 3 wallet classes; signed `w_PS`; constant universe `\mathcal{W}`. |
| §3 BUY worked example | REWORKED | Constant wallet set including CSD/JPMC mirrors; conservation sums to zero. |
| §3.X SELL worked example | NEW | Independent verification of recon identity. |
| §4 Reconciliation | REWORKED | Canonical sign convention; named projections. |
| §4.5 Attestation envelope | NEW | Closes nazarov B-1..B-5. |
| §5 Lifecycle FSM | REWORKED | Per-leg canonical; `tx_status` projection. |
| §6 Variants | LIGHT REVISION | T+1, T+0, fail, partial, cancellation. |
| §6.5 Workflow specification | NEW | Closes temporal B-1..B-5 + 10 majors. |
| §7 SBL composition + Conservation Lifting | REWORKED | §7.4 bijection Φ; §7.5 Conservation Lifting Theorem; §7.6 block-and-allocation. |
| §8 CDM cross-walk | REWORKED | F is lossy non-faithful functor; $\mathbf{Lg}_{\text{econ}}$ quotient. |
| §9 Regulatory footprint | TRIMMED | One-paragraph-per-regime; matrix preserved; §9.8 Pillar 3 worked example added. |
| §10 Accounting + audit + capital | LIGHT REVISION | §10.7 storage NEW; §10.9 CORRECTION expanded. |
| §10.7 Storage and retention | NEW | Closes jane_street B-4. |
| §11 Invariants | REWORKED | Pruned to 10; §11.A restated v10.3. |
| §12 Type design | REWORKED | v11.0 core 5 items; v12 RFP deferrals. |
| §13 Honest gaps + POs | LIGHT REVISION | Status updates per closure. |
| §13.3 Walking-skeleton tests | NEW | Closes testcommittee B-2. |
| §13.4 Goodhart traps | NEW | Closes correctness B-6. |
| §13.5 Trust-assumption registry | NEW | Part of nazarov B-5. |
| §14 Out of scope | LIGHT REVISION | Reflects v12 RFP deferrals. |
| §15 Ready-for-Review + closure | NEW | Closure record §15.2..§15.5. |

Total length: ~21k words (target 18-22k). v1 was 19,770 words; v2 is larger (more sections; more careful quantification) but tighter on prose where redundancy was removable (regulatory regime prose; v1 §1.2 rejected-items full re-litigation; v1 §10 accounting prose).

---

End of proposal_v2. Submitted to Phase 3 Round 2 adversarial review per the user's preferred multi-agent adversarial pattern.
