# Deferred Settlement on Cash Equities — finops-architect proposal

**Author role:** finops-architect (Phase 1, Team A, independent)
**Scope:** how the Ledger represents the gap between trade-time economic recognition and settlement-time custody movement on cash equities (and degenerate variants).
**Anchored to:** v10.3 §2 (closed ledger), §6 (managed accounts), §8 (settlement projection), §11 (invariants), §13 (SBL six-coordinate); v10.3 StatesHome 3-map ruling; valuation v1.0 FSM; data v1.0 leaves L11 (ExternalConfirmation), L13 (MoveStream), L15 (Obligation), L18 (BreakRegister).

---

## 0. The one-paragraph thesis

> The economic position is correct from the moment of trade. The settlement obligation is a **separately addressable, balanced double-entry** in the same closed ledger, carried in a **per-counterparty per-currency Pending Settlement (PS) wallet pair** for cash and a **per-counterparty per-ISIN Pending Settlement Securities (PSS) wallet pair** for stock. Each unsettled trade contributes one row to PS and one to PSS, both indexed by `transaction_id` and `expected_settlement_date`. At T+2⁺, finality oracle attestations (sese.025 / camt.054 from `L11.ExternalConfirmation`) drive a **balanced contra-transaction** that drains the PS/PSS rows and credits the nostro/depot virtual wallets. Reconciliation to the nostro is the algebraic identity `nostro_cash_external == own_cash_internal − Σ unsettled_cash_payable + Σ unsettled_cash_receivable + inflight`. **Lead-lag during T ≤ t < T+2 is not a break: it is a structurally expected, monotonically draining contra-balance with a known horizon.** A break is the same identity violated *outside* that contra.

This costs us four things and zero new primitives:

1. Two new wallet **classes** (PS-cash, PSS-securities) with naming convention but identical move semantics.
2. One new **Obligation** kind (`SettlementFinality`) with a finality predicate keyed off `L10.LifecycleOracle / L11.ExternalConfirmation`.
3. One new **transaction type** marker `SETTLEMENT_FINALITY` (a sub-class of `SETTLEMENT`, drives the contra-transaction).
4. One new **morning-recon report shape** keyed off `expected_settlement_date − today`.

It costs us **no** changes to: the move primitive, the conservation law, the StatesHome three-map schema, the settlement projection, or the CDM cross-walk (`L11` already carries `sese.023/sese.025/camt.053/camt.054`).

---

## 1. State representation

### 1.1 Earning the place of every addition

Before adding any storage I apply the **Karpathy substitution test** (StatesHome §4) and the **physical-action test** (v10.3 §13.2):

| Candidate | Earns its place? | Reason |
|---|---|---|
| `expected_settlement_date` on the trade transaction's CDM payload | YES, but not new | already present in `L11.ExternalConfirmation` and the CDM `Trade.tradeDate / settlementDate`. Read from the move stream, not stored as PositionState. |
| `settlement_status` ∈ {EXECUTED, INSTRUCTED, SETTLED, FAILED, PARTIALLY_SETTLED, CANCELLED} | YES — it is the existing v10.3 §8.4 settlement-status lifecycle. Lives on the **transaction**, not on the position. Already implied by §8.7. |
| Pending Settlement wallets (PS/PSS) | YES — these are **virtual wallets** in the v10.3 §2.5 sense. They earn their place because the receivable/payable between T and T+2 is a real economic claim against a specific counterparty and must be addressable for reconciliation, novation, netting, and CSDR penalty attribution. Without them, a single trade collapses into the broker virtual wallet and is no longer per-trade addressable. |
| A new `unsettled_qty` PositionState coordinate | NO — fails the physical-action test. There is no physical action that touches `unsettled_qty` and only `unsettled_qty`; every action also touches `own` (trade) or the CSD's depot (settle). It is a **projection** over the move stream filtered by `settlement_status ∈ {EXECUTED, INSTRUCTED}`. |
| A new `pending_cash` PositionState scalar | NO — same reason. It is `Σ over PS wallets keyed to this counterparty`. Projection. |
| A new `cum/ex` flag on PositionState | NO — derived from record-date snapshot of `(w, u)` rows that have non-zero `own` at record-date observation time. Bitemporal projection over `L13.MoveStream`. |

**Net new storage: zero new PositionState fields.** The PS/PSS wallets are wallets, not state; the `settlement_status` field is on the transaction (which is already in `L13.MoveStream`); the `expected_settlement_date` is on the CDM payload (already in `L11`). Everything else is a projection.

This is a *finops* not an *architect* point but it is load-bearing: **a reconciliation engineer who has spent five years chasing breaks will tell you that the difference between a clean recon and a swamp is whether each unsettled trade is individually addressable in the books.** Collapsing them into a single counterparty receivable is the legacy mistake that creates "the gross-net break" — operations cannot tell you which of 412 trades against Goldman is 13 cents off the nostro.

### 1.2 The Pending Settlement (PS) wallet pair — formal definition

For each (real_wallet `w`, counterparty `cpty`, currency `ccy`), the framework introduces **two** virtual wallets:

```
PS_payable[w, cpty, ccy]      -- "we owe cpty: cash leaving w"
PS_receivable[w, cpty, ccy]   -- "cpty owes w: cash arriving"
```

For each (real_wallet `w`, counterparty `cpty`, ISIN `s`), symmetrically:

```
PSS_payable[w, cpty, s]    -- "we owe cpty: securities leaving w"
PSS_receivable[w, cpty, s] -- "cpty owes w: securities arriving"
```

Naming convention: `PS:{w_id}:{cpty_lei}:{ccy}:payable`. These are virtual wallets in the sense of v10.3 §2.5 — they participate in conservation, they are reconcilable, they have an external_id (the CSD account / SSI), but they hold no real cash.

**Why the payable/receivable split** (not a single signed wallet)? Three operational reasons:

1. Right-of-set-off is jurisdiction- and ISDA/GMSLA-master-agreement-dependent. A single signed wallet would silently net a payable in one master agreement against a receivable under another. Operations needs the breakdown to compute exposure-at-default correctly; risk needs it for SFTR Article 15 and for IFRS 7 disclosures.
2. Aged-payable and aged-receivable trigger different ops workflows (CSDR penalties hit payables that fail to deliver; buy-in clocks affect receivables that fail to deliver).
3. Conservation is cleaner when both sides are non-negative — the standard convention used by every general ledger since 1494.

### 1.3 Why two PS wallet families, not one universal "settlement queue"

A single global "settlement queue" wallet would lose the per-counterparty reconcilability. Per-counterparty PS is the **primary** key for recon against custodian / CSD reports, which arrive sliced by counterparty and currency. SSIs (standing settlement instructions) are also per-counterparty per-currency. **Recon shape drives wallet shape.** This is a finops veto on any flatter design.

### 1.4 Mapping into the StatesHome three-map schema

The PS/PSS wallets are *wallets*, and StatesHome was emphatic: **there is no WalletState sector.** Conformance to StatesHome:

| StatesHome map | Touched by deferred settlement? |
|---|---|
| `ProductTerms[u]` | No. Cash and securities terms unchanged. |
| `UnitStatus[u]` | No. The instrument's lifecycle stage is unaffected by per-trade settlement state. |
| `PositionState[w, u]` | Yes — but only by **the same handlers as before**. The PS/PSS wallets are added to the wallet axis; their balances are PositionState rows with the same `own` coordinate. Only `settle/trade` handlers (C11) write to them. **Zero new fields.** |
| `WalletRegistry[w]` | Yes — three new metadata fields: `wallet_class ∈ {real, virtual_cpty, virtual_PS_payable, virtual_PS_receivable, virtual_nostro}`, `cpty_lei` (for PS variants), `expected_settle_window`. These are KYC-class metadata, not state. Permissible per StatesHome §2 ("KYC, permissions, audit cursor, NOT state"). |

**Conformance verdict:** the proposal is StatesHome-compliant. We do not introduce a fourth map. The `wallet_class` enum lives in `WalletRegistry`, which is by ruling not a state sector. The break-FSM (`L18.BreakRegister`) and the obligation FSM (`L15.Obligation`) absorb the lifecycle complexity that one might naively want to put on PositionState.

### 1.5 The settlement_status lifecycle stays on the transaction

v10.3 §8.7 already defines `EXECUTED → INSTRUCTED → SETTLED | FAILED`. I extend this minimally to absorb partial settlement:

```
EXECUTED ──→ INSTRUCTED ──→ SETTLED
                    │   ╲
                    │    ╲──→ PARTIALLY_SETTLED ──→ SETTLED  (residual settles)
                    │                       │
                    │                       └────→ FAILED
                    └─→ FAILED ──→ INSTRUCTED   (re-instructed, e.g. after buy-in)
                            │
                            └──→ CANCELLED  (CORRECTION transaction)
```

The status lives on the transaction record in `L13.MoveStream`, not on PositionState. This matches the existing v10.3 §8 design and the data v1.0 `L11` reconciliation pair. **Zero new state, zero new map.**

---

## 2. Move sequence — standard buy T+2 (CORE-1)

**Setup.**
- Real wallet: `w_us` (our portfolio).
- Counterparty: Goldman Sachs broker, virtual wallet `w_GS_broker` (LEI `784F5XWPLTWKTBV3E584`).
- CSD: DTC, virtual wallet `w_DTC_depot` for securities and `w_DTC_cash` for cash; nostro at JPMC `w_JPMC_nostro_USD`.
- Trade: buy 100 XYZ @ $50 = $5,000, T = 2026-04-30 14:32 UTC, settlement T+2 = 2026-05-04.
- Decimal handling: prices in `Decimal(10,4)`, quantities in `Decimal(18,6)`, cash amounts in `Decimal(18,2)`. **No floats anywhere on the cash leg.**

### 2.1 At T (trade execution): economic position becomes true

Two transactions, in a single `BusinessEvent`:

```
Transaction T1 [type=ECONOMIC_RECOGNITION, tx_id=BUY-100-XYZ-T0]:

  -- Securities leg (the economic position changes immediately)
  Move 1: from=PSS_receivable[w_us, GS, XYZ]   to=w_us             unit=XYZ  qty=100
  -- Cash leg (the economic obligation crystallises immediately)
  Move 2: from=w_us                              to=PS_payable[w_us, GS, USD] unit=USD  qty=5000.00

  metadata: {
    expected_settlement_date: 2026-05-04,
    cdm_event: ExecutionEvent,
    cpty_lei: GS_LEI,
    settlement_status: EXECUTED,
    venue_mic: XNYS
  }
```

Conservation (per unit):
- `Σ_w w(XYZ) = 0`: PSS_recv goes from 0 to −100, w_us from 0 to +100. Sum = 0. ✓
- `Σ_w w(USD) = 0`: w_us from x to (x − 5000), PS_payable from 0 to +5000. Sum = 0. ✓

### 2.1.1 Why the securities leg credits PSS_receivable to (−100), not depot directly

This is the load-bearing decision. Three alternatives were considered:

**(a) Credit `w_us` from `w_GS_broker` directly** (the v10.3 §2.5 example).
- Pro: simplest.
- Con: at T+2⁻ when DTC reports finality, there is no contra-balance to drain; the only hint that something needs reconciling is the transaction's `settlement_status` field. Recon to nostro requires reconstructing the unsettled set by replaying the move stream filtered by `status ∈ {EXECUTED, INSTRUCTED}` *every morning*. **This is the legacy industry pattern and it is the source of half of all settlement breaks.** Recon engineers cannot tell whether "this $5,000 in JPMC nostro" belongs to Trade 412 or Trade 871.

**(b) Credit `w_us` from a single global pending wallet.**
- Pro: still simple.
- Con: loses per-counterparty per-trade reconcilability; the "reserved bucket" anti-pattern from v10.3 §13.6.

**(c) Credit `w_us` from `PSS_receivable[w_us, GS, XYZ]`** (this proposal).
- Pro: the PSS wallet's balance equals the *physical* outstanding receivable from GS, by construction. Recon to GS's confirmation file is a single-row lookup. No replay required.
- Con: more wallet identities. Negligible at scale (`O(open trades × counterparties)` is bounded in the millions, far below `L13.MoveStream` cardinality).

**(c) wins on operational grounds.** Finops veto on (a) and (b).

### 2.1.2 Sign convention

The PSS_receivable wallet is **negative** between T and T+2: the counterparty owes us 100 XYZ but has not delivered. This matches the GP physical interpretation of `Σ_w w(u) = 0` (v10.3 §2.4): the "missing" 100 shares in our books are exactly the −100 owed to us by GS, which will be cancelled by GS's contra-credit at finality. From our perspective the receivable is a **claim**: we already economically own the shares (`w_us.own(XYZ) = +100`), but custody has not arrived. This is what trade-date accounting *means* (v10.3 §1, §8.6).

### 2.2 At T+1 (no event)

If nothing happens — no instruction, no fail, no price move processed — **no moves are emitted.** The position is correct. The PS/PSS wallets carry their non-zero balances. The status remains `EXECUTED` (or `INSTRUCTED` if the settlement layer has fired the sese.023). Conservation holds trivially: no transaction = no change.

PnL on T+1 (XYZ → $52): see §7. PnL is +$200 by valuation, which reads `w_us.own(XYZ) = 100` and the new price; the PS/PSS wallets do not affect PnL because cash has unit price 1 and `w_us.own(USD)` already reflects the −5,000.

### 2.3 At T+2⁻ (instruction sent, before finality)

The settlement layer projects the trade transaction (v10.3 §8.1) to a `SettlementInstruction`. The settlement layer fires the ISO 20022 messages (`sese.023` securities, `pacs.009` cash). The Ledger records a **state-only** transaction that updates `settlement_status` from `EXECUTED → INSTRUCTED`:

```
Transaction T2 [type=ACCOUNTING, tx_id=BUY-100-XYZ-T2-instructed]:
  -- No moves. State-only.
  metadata: {
    refers_to_tx: BUY-100-XYZ-T0,
    new_settlement_status: INSTRUCTED,
    ssi_used: hash(SSI),
    iso20022_msg_id: sese.023.001-...
  }
```

State-only transactions are explicitly permitted by v10.3 FAQ Q6 ("Move-less events are valid lifecycle events"). Conservation: 0 = 0 trivially.

### 2.4 At T+2⁺ (finality oracle delivers)

DTC reports DvP finality via `sese.025` (securities) and `camt.054` (cash). These arrive on `L11.ExternalConfirmation`. The settlement orchestration workflow consumes the signal and emits the **finality contra-transaction**:

```
Transaction T3 [type=SETTLEMENT_FINALITY, tx_id=BUY-100-XYZ-T2-final]:

  -- Securities: drain the PSS_receivable, credit DTC depot virtual wallet
  Move 1: from=w_DTC_depot                      to=PSS_receivable[w_us, GS, XYZ] unit=XYZ qty=100
  -- (this brings PSS_receivable from -100 back to 0; DTC depot goes from 0 to -100,
  --  representing "DTC holds 100 shares for us")

  -- Cash: drain PS_payable, debit JPMC nostro
  Move 2: from=PS_payable[w_us, GS, USD]        to=w_JPMC_nostro_USD             unit=USD qty=5000.00
  -- (PS_payable goes from +5000 to 0; nostro from x to x-5000, mirroring the real cash leaving)

  -- Symmetric counterparty-side moves are recorded by the broker if they too run this ledger.
  -- For us, GS is a virtual wallet outside our scope; we do NOT emit moves on their behalf.

  metadata: {
    refers_to_tx: BUY-100-XYZ-T0,
    new_settlement_status: SETTLED,
    iso20022_inbound: sese.025.001-..., camt.054.001-...,
    finality_attestation_lei: DTC_LEI,
    finality_timestamp: 2026-05-04T19:32:00Z
  }
```

Conservation per unit:
- XYZ: `Δ(w_DTC_depot) = -100`, `Δ(PSS_receivable) = +100`. Sum = 0. ✓
- USD: `Δ(PS_payable) = -5000`, `Δ(w_JPMC_nostro) = -5000`. Wait — both negative? Let me reread.

Actually I had a sign error. Let me restate Move 2 correctly:

```
  Move 2: from=PS_payable[w_us, GS, USD]  to=w_JPMC_nostro_USD  unit=USD  qty=5000.00
```

Move semantics (v10.3 §2.3): `from -= q`, `to += q`. So:
- `Δ(PS_payable) = -5000` (was +5000, now 0)
- `Δ(w_JPMC_nostro) = +5000` (was 0, now +5000)

But this is wrong because the **nostro is showing money LEAVING us at finality**. The nostro is *our* account at JPMC; if money leaves *our portfolio* to go to GS via JPMC's correspondent network, the nostro should DECREASE.

Correct treatment: the nostro is **a virtual mirror of an external account.** A debit to the nostro represents cash leaving JPMC's books on our behalf. Move semantics requires us to move from the nostro to a virtual wallet representing the external recipient (the JPMC-internal "outgoing wires" wallet `w_JPMC_outgoing`). Let me correct:

```
Transaction T3' [type=SETTLEMENT_FINALITY, tx_id=BUY-100-XYZ-T2-final]:

  -- Securities leg
  Move 1: from=w_DTC_depot  to=PSS_receivable[w_us, GS, XYZ]  unit=XYZ  qty=100

  -- Cash leg: cash leaves the nostro toward GS via the correspondent
  Move 2: from=w_JPMC_nostro_USD            to=PS_payable[w_us, GS, USD]  unit=USD  qty=5000.00

  -- After Move 2: Δ(nostro) = -5000, Δ(PS_payable) = +5000
  -- But PS_payable was already +5000 from T0! Now it is +10000?

  -- Wrong. The PS_payable is the PROMISE; it must drain at finality.
  -- The nostro reduction is the PHYSICAL cash leaving.
  -- These are DIFFERENT moves on DIFFERENT pairs.

  -- The correct two moves on the cash leg:
  Move 2a: from=w_us                         to=PS_payable[w_us, GS, USD]  unit=USD  qty=5000   (this was at T0!)
  Move 2b: from=PS_payable[w_us, GS, USD]    to=w_JPMC_outgoing_USD        unit=USD  qty=5000   (at T+2)

  -- And for the nostro decrement, JPMC reports the debit via camt.053/054:
  Move 2c: from=w_JPMC_nostro_USD            to=w_JPMC_outgoing_USD        unit=USD  qty=5000   (at T+2)
```

Wait, I have made this needlessly tangled. Let me restart this leg cleanly. **The issue is that I conflated two contra-balances in my head:** (1) the internal contra (PS_payable cancels at T+2) and (2) the external nostro (which mirrors JPMC's external view of our cash).

Clean restatement:

```
At T  (trade time):
  Move A1: w_us            → PS_payable[w_us, GS, USD]   USD  5000   [INTERNAL recognition]
  Move A2: PSS_receivable[w_us, GS, XYZ] → w_us           XYZ   100   [INTERNAL recognition]

At T+2 (finality):
  -- The cash physically leaves our nostro at JPMC. JPMC issues a camt.054 debit confirmation.
  -- That confirmation translates into:
  Move B1: PS_payable[w_us, GS, USD] → w_GS_broker_virtual  USD  5000   [DRAINS internal payable]
  -- (PS_payable was +5000, becomes 0; w_GS_broker_virtual was 0, becomes +5000)

  -- The shares physically arrive at our DTC depot. DTC issues sese.025.
  Move B2: w_GS_broker_virtual → PSS_receivable[w_us, GS, XYZ]  XYZ  100   [DRAINS internal receivable]
  -- (w_GS_broker was 0 in XYZ, becomes -100; PSS_receivable was -100, becomes 0)
```

Now check the GS broker virtual wallet balance after T+2:
- USD: +5000 (we paid them)
- XYZ: −100 (they gave us shares)
- Net economic value: +5000 − 100×($52 at T+2) = +5000 − 5200 = −200, mirroring our +200 PnL. ✓

The **nostro** (`w_JPMC_nostro_USD`) is a *separate* virtual wallet that reflects what JPMC reports as our balance there. It is reconciled — see §4 — but it is **not** the same wallet as `PS_payable` and **not** the same as `w_GS_broker_virtual`. The "outgoing wire" is JPMC's internal accounting; the framework's view is that JPMC reports debits via `camt.053` against the nostro, and we record those debits as moves between `w_JPMC_nostro_USD` and a `w_JPMC_outgoing_virtual` wallet. In the steady state, `w_JPMC_outgoing_virtual` and `w_GS_broker_virtual` reconcile against each other via SWIFT message tracking.

For the purposes of this proposal I will keep the wire-level mechanics separate from the trade-settlement contra-transaction. **The minimum viable shape is the (Move B1, Move B2) pair, with nostro reconciliation as a daily algebraic identity (§4).**

### 2.5 Conservation summary across the four states

For the standard buy (cash leg only, USD):

| State | `w_us(USD)` | `PS_payable[w_us,GS,USD]` | `w_GS_broker(USD)` | Σ |
|---|---:|---:|---:|---:|
| T⁻ (pre-trade) | x | 0 | 0 | x |
| T⁺ (post-trade) | x − 5000 | +5000 | 0 | x |
| T+1 | x − 5000 | +5000 | 0 | x |
| T+2⁻ (instructed) | x − 5000 | +5000 | 0 | x |
| T+2⁺ (final) | x − 5000 | 0 | +5000 | x |

The total `Σ_w w(USD)` is `x` (the system's USD baseline) at every step. ✓
The PS_payable column is the headline finops report: it is non-zero **only** between T and T+2, and its non-zero value is **expected** during that window.

For the securities leg (XYZ):

| State | `w_us(XYZ)` | `PSS_receivable[w_us,GS,XYZ]` | `w_GS_broker(XYZ)` | Σ |
|---|---:|---:|---:|---:|
| T⁻ | 0 | 0 | 0 | 0 |
| T⁺ | +100 | −100 | 0 | 0 |
| T+1 | +100 | −100 | 0 | 0 |
| T+2⁻ | +100 | −100 | 0 | 0 |
| T+2⁺ | +100 | 0 | −100 | 0 |

Conservation `Σ_w w(XYZ) = 0` at every step. ✓ The negative `w_GS_broker(XYZ)` at T+2⁺ is the GS short position from their perspective (they delivered shares they owed).

---

## 3. Invariants

### Invariant E1 (mandatory: economic-exposure-at-T)

For every executed buy/sell transaction `tx` with trade time `T(tx)`, recognised in the ledger via the `ECONOMIC_RECOGNITION` transaction type:

> The wallet balance `w_us.own(u)` at any time `t ≥ T(tx)` includes the economic effect of `tx`, **regardless of `settlement_status(tx)`**.

Equivalently: `w_us.own(u)` is path-independent of settlement outcome between T and T+2. PnL `V_t = Σ w_t(u) · P_t(u)` therefore reflects the trade from `T` onwards, not from the settlement timestamp.

**Proof:** the economic recognition transaction at T executes `Move(PSS_receivable → w_us, XYZ, 100)` and `Move(w_us → PS_payable, USD, 5000)`. The finality transaction at T+2 emits *new* moves that touch only PS, PSS, broker virtual, and nostro wallets — it never touches `w_us.own(XYZ)` or `w_us.own(USD)` directly. Hence `w_us.own(u)` is invariant between T and T+2. □

This invariant is the **headline guarantee** of the proposal. Every other invariant supports it.

### Invariant E2 (PS/PSS contra-balance well-formedness)

For every `(w, cpty, ccy)` triple, define `PS_net[w, cpty, ccy] = PS_payable[...] - PS_receivable[...]`. Then at any time `t`:

> `PS_net[w, cpty, ccy] = Σ over open settlement transactions tx with cpty matching: (cash_leg_amount × side_sign(tx, w))`

where `side_sign(tx, w) = +1` if `w` is paying, `−1` if receiving. Equivalently: PS_net is the algebraic sum of the cash legs of all unsettled trades against `cpty`, with sign reflecting direction. This is an **inductive invariant**: it holds at T⁻ (vacuously, both sides zero), is preserved by every recognition transaction (which adds an open trade), and is preserved by every finality transaction (which closes an open trade). Property-based test: random sequences of recognition and finality, check identity holds at every step.

Symmetric invariant for PSS_net on securities.

### Invariant E3 (finality contra-transaction structure)

A `SETTLEMENT_FINALITY` transaction `tx_F` for a trade `tx_T`:

1. Refers to exactly one prior `ECONOMIC_RECOGNITION` transaction via `metadata.refers_to_tx`.
2. Touches **only** PS/PSS, counterparty-broker virtual, and (optionally) nostro/depot virtual wallets — never `w_us` or any other real wallet.
3. The cash and securities quantities equal the original recognition transaction's quantities (modulo partial settlement, see §6.5).
4. The transaction is balanced: `Σ moves = 0` per unit.
5. Idempotency: applying the same `tx_F` twice (same `tx_id`) is a no-op. (v10.3 P5.)

This is a **structural** invariant on the transaction class. The smart contract that emits `SETTLEMENT_FINALITY` is constrained at compile time to satisfy (1)–(5).

### Invariant E4 (lead-lag is bounded)

For every open trade with `settlement_status ∈ {EXECUTED, INSTRUCTED, FAILED, PARTIALLY_SETTLED}`:

> `|today − expected_settlement_date| ≤ T_max`

where `T_max` is product- and venue-specific (e.g., 5 business days for US equities post-CSDR with mandatory buy-in cap; 7 for cross-border). Beyond `T_max`, the open obligation is auto-promoted to `BreakRegister` (`L18`) at state `Aged-5`. Aging timers in v11.0 data layer §11.2 already provide this mechanism; we just register the obligation kind.

### Invariant E5 (CSDR-attribution determinism)

For every settlement-fail attestation arriving from the CSD on `L11.ExternalConfirmation`, the CSDR penalty obligation (`obligation_kind = CSDR_PENALTY`) is determined as a **pure function** of:
- `(qty_failed, price_at_intended_settlement, days_late, instrument_class)`
- the CSDR rate matrix (Reg (EU) 2017/389 Annex), pinned via `refdata_pin`.

No human inputs. No discretion. The penalty cash move is emitted automatically when the obligation discharges.

### Invariant E6 (no double-counting at the recon boundary)

For any `(w, ccy)` pair:

> `nostro_external_balance(w, ccy)`<br>
> ≡ `w.own(ccy) − Σ PS_payable[w, *, ccy] + Σ PS_receivable[w, *, ccy] + inflight_wires(w, ccy)`

This is the **morning recon identity**. It must hold daily at the cash recon time (typically 09:00 local, after overnight settlement). A break is `|LHS − RHS| > tolerance`, where tolerance is per-currency (e.g., 1 USD for major currencies, 0.01 USD if a strict cents recon is required). See §4.

Symmetric identity for securities: `depot_external_balance(w, s) ≡ w.own(s) + Σ PSS_payable[w, *, s] − Σ PSS_receivable[w, *, s] + inflight_securities(w, s)`.

### Invariants from prior corpus that compose unchanged

- v10.3 P1 (conservation): `Σ_w w(u) = 0`. Every PS/PSS wallet is a virtual wallet, contributes to the sum, and the contra-transactions preserve `Σ = 0`.
- v10.3 P2 (atomic commitment): the recognition and finality transactions each commit atomically. **The recognition and finality are not the same transaction** (they are separated in time by T+2 days); each is internally atomic.
- v10.3 P5 (transaction idempotency): finality_tx is keyed by `(refers_to_tx, finality_attestation_id)`; replaying the same finality is a no-op.
- v10.3 P10 (PnL path-independence): trivially preserved because `w_us.own(u)` is invariant under finality moves (E1).
- StatesHome C1 (Option accessor + monotone carrier): PS/PSS rows survive at zero after settlement (monotone). `view.position_state(PS_payable[w, GS, USD])` returns `Some(zero)` for an inactive PS pair, `None` if no trade has ever been recognised against this counterparty in this currency.
- StatesHome C2 (handler-level conservation): the ECONOMIC_RECOGNITION handler proves `Σ Δ = 0` per unit (2-leg structure); the SETTLEMENT_FINALITY handler proves the same.
- StatesHome C3 (atomic StateDelta): each transaction commits as one atomic StateDelta. Partial recognition or partial finality = rejected.

---

## 4. Reconciliation

### 4.1 The fundamental recon identity

```
nostro_external(w, ccy)  ≡  w.own(ccy)
                         −  Σ_{cpty}  PS_payable[w, cpty, ccy]
                         +  Σ_{cpty}  PS_receivable[w, cpty, ccy]
                         +  inflight(w, ccy)
```

where `inflight(w, ccy)` is the sum of in-flight wire amounts (sent but not confirmed by the receiving correspondent), tracked as a separate virtual wallet pair per the same pattern. For most days, `inflight = 0` outside the active settlement window.

### 4.2 Morning recon report shape — T, T+1, T+2, T+3

The morning recon report is the most operationally important artifact of this proposal. It is generated daily at 09:00 local from a Temporal cron workflow (`MorningReconWorkflow`).

**Report structure** (one row per (counterparty, currency, expected_settlement_bucket) tuple):

```
counterparty | ccy | bucket    | gross_payable | gross_receivable | net | trade_count | aging
-------------|-----|-----------|---------------|-------------------|-----|-------------|------
GS           | USD | T+0       |       12,500  |          5,000.00 | +7,500.00 | 4 | 0d
GS           | USD | T+1       |        5,000  |              0.00 | +5,000.00 | 1 | 1d
GS           | USD | T+2_today |    1,250,000  |          812,000  | +438,000  | 47| 2d
GS           | USD | overdue   |            0  |          150,000  | -150,000  | 1 | 3d  ⚠ AGED
JPMC         | USD | T+0       |       80,000  |          80,000   |        0  | 12| 0d
...
```

The **bucket** field is `expected_settlement_date − today`. Buckets `T+0` and `T+1` are normal forward exposure. Bucket `T+2_today` is the trades settling today — **operations watch this bucket like a hawk**. Bucket `overdue` = trades past their expected_settlement_date that have not yet hit `BreakRegister.Aged-5`. Aging is in business days.

**For each currency, the report also publishes:**

```
nostro_external_balance:    1,234,567.89   (from L11 camt.053)
internal_check:             1,234,567.89
                            = own_cash − Σ PS_payable + Σ PS_receivable + inflight
recon_break:                       0.00    ✓
```

If `recon_break` is non-zero, **trading is allowed to continue** but operations is paged immediately. v10.3 §11 P1 is *not* violated by a recon break (conservation holds internally); what is violated is the assumption that our internal world matches the external custodian's world. That is investigated via `wf-position-break` per `L18`.

### 4.3 What is a break and what is not

**Not a break (expected lead-lag during the open settlement window):**
- `PS_payable > 0` for trades with `expected_settle_date ≥ today`
- `PSS_receivable < 0` for trades with `expected_settle_date ≥ today`
- nostro_external < own_cash by exactly the sum of `(PS_payable − PS_receivable)` over the window
- Any trade in `EXECUTED` status before its `expected_settle_date`
- Any trade in `INSTRUCTED` status before its `expected_settle_date + 1` business day grace

**Is a break:**
- nostro_external ≠ (own_cash − Σ PS_payable + Σ PS_receivable + inflight) by more than tolerance — investigation required.
- Any open trade with `expected_settle_date < today` *and* `settlement_status ∉ {SETTLED, FAILED, PARTIALLY_SETTLED, CANCELLED}` — escalate.
- A `sese.025` finality message with no matching recognition transaction (`unmatched_finality`) — escalate.
- A recognition transaction with no matching finality after `T_max` — escalate (this is the CSDR fail path).
- A finality with **wrong amount or quantity** — escalate; this triggers the `wf-confirm-break` workflow.

### 4.4 Decimal handling discipline at recon time

Decimal handling is non-negotiable. Specifically:

- All cash amounts: `Decimal(18, 2)` for major currencies, `Decimal(18, 4)` for currencies with sub-cent ticks (some EM crosses).
- All securities quantities: `Decimal(18, 6)` (allows fractional shares for tokenised instruments; native equities use `Decimal(18, 0)`).
- Recon tolerance: explicit per currency, **never** a percentage. Hard-coded magic numbers banned (data v1.0 anti-Goodhart §15). Tolerances live in `L7^P.PolicyConfiguration`, versioned, with `four_eyes_required` on changes.
- **No floats in the recon pipeline.** Period.
- Rounding mode: `ROUND_HALF_EVEN` (banker's rounding, IEEE 754 default).
- Currency conversion at recon: forbidden. Recon is done **per currency**. Cross-currency recon is a separate workflow (§5.10).

### 4.5 Why per-counterparty per-currency, not a single aggregate

A single aggregate `total_unsettled_cash_USD` is a **finops anti-pattern**. Operations cannot resolve a $13.42 break in a $1.2B aggregate. Per-counterparty per-currency lets ops drill down to the specific (cpty, currency, trade) cell where the break originates. The recon engineer's lookup time goes from O(|trades|) to O(|trades_in_break_cell|) — typically 1 to 10 trades.

---

## 5. CDM cross-walk

### 5.1 Recognition transaction (T)

| Field | CDM source |
|---|---|
| transaction_id | CDM `BusinessEvent.eventQualifier` || hash(execution report) |
| trade_date | CDM `Trade.tradeDate` |
| expected_settlement_date | CDM `Trade.settlementDate` (computed from `tradeDate + settlementOffset` per CDM date conventions, cf. v10.3 §15.7) |
| cpty_lei | CDM `Party.partyId` filtered to `lei` |
| security ISIN | CDM `Trade.product.transferableProduct.identifier` |
| quantity | CDM `Trade.tradableProduct.tradeLot.priceQuantity.quantity` |
| price | CDM `Trade.tradableProduct.tradeLot.priceQuantity.price` |
| side | CDM `Trade.tradableProduct.counterparty[role=BUYER/SELLER]` |
| venue_mic | CDM `Trade.executionDetails.executionVenue` |
| settlement_type | CDM `SettlementTerms.settlementType ∈ {CASH, PHYSICAL, NET}` |

CDM `BusinessEvent` shape: `eventIntent = OPEN`, `before.tradeState = ∅`, `after.tradeState = EXECUTED`. The framework's recognition transaction is the ledger image of this BusinessEvent under the forgetful functor F (v10.3 §9.4).

### 5.2 Finality transaction (T+2⁺)

CDM `BusinessEvent` shape: `eventIntent = TRANSFER` (cash & securities legs of the actual settlement). CDM has the building blocks (`Transfer` primitive) and the message-level cross-walk (`sese.025`, `camt.054`) lives in `L11.ExternalConfirmation`. The Ledger emits the finality transaction as the F-image of this CDM event.

### 5.3 Status updates as ACCOUNTING transactions

`EXECUTED → INSTRUCTED`: state-only ACCOUNTING transaction with `cdm_event = TransitionToInstructed` (no native CDM intent — this is a Ledger-internal status; data v1.0 §9.7 acknowledges this gap).

`INSTRUCTED → FAILED`: state-only ACCOUNTING transaction triggered by inbound CSD failure attestation on `L11`. Spawns CSDR penalty Obligation (`L15`).

`FAILED → INSTRUCTED` (re-instruction after buy-in extension): state-only ACCOUNTING.

`* → CANCELLED`: a CORRECTION transaction (v10.3 §8.3 transaction type table) that emits **anti-moves** of the original recognition. Specifically:

```
Transaction T_cancel [type=CORRECTION, tx_id=BUY-100-XYZ-T0-cancel]:
  Move 1: w_us → PSS_receivable[w_us, GS, XYZ]   unit=XYZ  qty=100
  Move 2: PS_payable[w_us, GS, USD] → w_us       unit=USD  qty=5000
  metadata: refers_to_tx: BUY-100-XYZ-T0, reason: CANCELLED
```

After `T_cancel`, all PS/PSS wallets return to zero **and** `w_us.own(XYZ)` returns to zero, `w_us.own(USD)` returns to its pre-trade level. The recognition tx remains immutably in `L13.MoveStream` (v10.3 P4 log monotonicity). PnL between T and T_cancel is **realized** as a cancellation P&L (the 100 XYZ between $50 and price-at-cancel is on us).

### 5.4 CDM gaps

The data v1.0 §9 cross-walk reports:
- `L11`: Partial CDM coverage on inbound `sese.023/sese.025/camt.053/camt.054`. ✓
- `L15.Obligation`: Missing from CDM (Ledger-internal). The SettlementFinality obligation kind is one we own.
- `L18.BreakRegister`: Missing from CDM. Same.
- Status lifecycle (EXECUTED/INSTRUCTED/SETTLED/FAILED) is **not** native CDM but maps onto `WorkflowStep` chains; the cross-walk goes through DRR for regulatory reporting (`L17.RegulatorySubmission`).

These gaps are pre-existing. Deferred settlement does not introduce new ones.

---

## 6. Failure modes — floor cases

### 6.1 Floor 1 — Standard buy T+2 (CORE)

Covered exhaustively in §2.

**Ledger end-state at T+2⁺:**
- `w_us.own(XYZ) = +100`
- `w_us.own(USD) = x − 5000`
- All PS/PSS zero.
- `w_GS_broker.own(XYZ) = -100`, `w_GS_broker.own(USD) = +5000`.
- `settlement_status(BUY-100-XYZ) = SETTLED`.

### 6.2 Floor 2 — Standard sell T+2

Symmetric. Sell 100 XYZ @ $52.

```
T0:   Move 1: w_us → PSS_payable[w_us, GS, XYZ]    XYZ  100   (PSS_payable = +100; w_us.own(XYZ): -100)
      Move 2: PS_receivable[w_us, GS, USD] → w_us  USD  5200  (PS_receivable: -5200; w_us.own(USD): +5200)
T+2:  Move 1: PSS_payable[w_us, GS, XYZ] → w_GS_broker  XYZ  100  (PSS_payable: 0; w_GS_broker.own(XYZ): +100)
      Move 2: w_GS_broker → PS_receivable[w_us, GS, USD]  USD  5200  (PS_receivable: 0)
```

Watch the signs: PS_receivable was credited *negative* at T0 (reflecting "GS owes us $5,200"), and at T+2 the inbound cash drains it back to zero. The sell shows PS_receivable behaves as a contra-asset between T and T+2.

**Ledger end-state at T+2⁺:** `w_us.own(XYZ) = -100`, `w_us.own(USD) = x + 5200`, all PS/PSS zero. PnL = +$200 captured at T (price $52 - cost basis $50, on the assumption we owned 100 at $50).

### 6.3 Floor 3 — T+1 markets

Identical mechanics, smaller `T_max`. The only differences:
- Recon report drops the `T+1` bucket; only `T+0` (settling today) and `T+1+` (overdue) buckets exist.
- Operational pressure: instructions must be sent same-day. T+0 affirmation cutoff (data v1.0 §11.5: 9pm ET T+0 for T+1 affirmation, 11:30am ET T for T+0 settlement) is hard.
- CSDR penalties accrue from `expected_settle_date + 1` business day, so failure detection must be near-real-time.

The PS/PSS structure is regime-agnostic. No changes to the ledger.

**Architectural argument for the proposal:** the same mechanism degenerates correctly across T+0, T+1, T+2 markets. T+0 collapses the open window to zero (recognition and finality in the same transaction, which the executor commits atomically — a single transaction containing both legs). For T+0, the PS/PSS wallets transit from 0 to non-zero to 0 within microseconds; **monotone carrier (StatesHome C1) preserves the audit trail; option accessor preserves "have we ever traded with this cpty in this ccy" semantics.**

### 6.4 Floor 4 — Failed settlement (CSDR penalties, buy-in clock)

Settlement fails: at T+2 the CSD reports `sese.024` fail attestation. The settlement orchestration workflow:

```
On L11.ExternalConfirmation matching (refers_to_tx=BUY-100-XYZ-T0, status=FAILED):

  Transaction T2_failed [type=ACCOUNTING]:
    -- No moves. State-only.
    metadata:
      refers_to_tx: BUY-100-XYZ-T0
      new_settlement_status: FAILED
      fail_reason: ISIP    -- Insufficient securities
      fail_attestation_id: sese.024.001-...

  Spawn ObligationWorkflow (L15):
    obligation_id: csdr-BUY-100-XYZ-T0
    obligation_kind: CSDR_PENALTY
    discharge_predicate: ByDeadline { buy_in_extension_period_end }
    compensation_handler: NonTrivialChildWorkflow
    fields: {
      qty_failed: 100,
      price_at_fail: 52.00,
      rate_basis_points: 50,    -- per CSDR Annex for liquid equities
      currency: USD,
      attribution_lei: GS_LEI
    }

  Each business day until resolution, MorningReconWorkflow emits:
    Transaction T_csdr_daily [type=SETTLEMENT, tx_id=csdr-BUY-100-XYZ-T0-day-N]:
      Move: w_GS_broker → w_us  USD  (100 × 52 × 0.0050)   -- daily CSDR penalty
```

**Critical:** `w_us.own(XYZ) = +100` does **not** revert. The economic exposure persists. The PS/PSS wallets stay at their non-zero values reflecting the still-open obligation. PnL marks at the still-open price, recognising further P&L moves.

**Buy-in clock.** Per CSDR mandatory buy-in (where applicable; status under EU 2024 review): on day `expected_settle_date + buy_in_period_end`, the CCP/CSD initiates a buy-in. This is recognised as:

1. A new `ECONOMIC_RECOGNITION` transaction in our books for the **buy-in** trade (the CCP buys 100 XYZ on our behalf in the market at current market price). The PS/PSS wallets for this buy-in trade go through their own T → T+2 cycle.
2. A `CANCELLATION` transaction reversing the original failed trade.
3. A cash-settled reimbursement: if buy-in price > original price, GS pays us the difference; if <, we pay GS. Recognition through standard cash moves.

**Ledger end-state after buy-in:** `w_us.own(XYZ) = +100` (now via the buy-in trade); the original BUY-100-XYZ-T0 transaction is in CANCELLED status with anti-moves applied. CSDR penalties from `expected_settle_date` to `buy_in_settle_date` accrued and credited. The audit trail preserves the entire saga.

### 6.5 Floor 5 — Partial settlement

The CSD reports `sese.025` for 60 of the 100 shares; the remaining 40 fail.

```
On L11.ExternalConfirmation:
  qty_settled: 60, qty_failed: 40

  Transaction T_partial [type=SETTLEMENT_FINALITY, tx_id=BUY-100-XYZ-T2-partial]:
    -- Securities leg: only 60 shares
    Move 1: w_DTC_depot → PSS_receivable[w_us, GS, XYZ]    XYZ  60
    -- (PSS_receivable goes from -100 to -40; DTC depot goes from 0 to -60)

    -- Cash leg: pro-rata cash for the 60 shares
    Move 2: PS_payable[w_us, GS, USD] → w_GS_broker        USD  3000  (= 60 × $50)
    -- (PS_payable goes from +5000 to +2000)

    metadata:
      refers_to_tx: BUY-100-XYZ-T0
      new_settlement_status: PARTIALLY_SETTLED
      qty_settled: 60
      qty_remaining: 40
      cash_settled: 3000
      cash_remaining: 2000

  Open obligation for the residual 40 shares: ObligationWorkflow extends.
```

Subsequent finality (`sese.025` for the remaining 40, days later) emits a second `SETTLEMENT_FINALITY` transaction draining the residual. **Conservation across the partial sequence: PS_payable ends at 0 only when all 100 shares + $5,000 are accounted for.**

Operationally this is the cleanest design: **partial settlement is just multiple finality transactions sharing the same recognition reference.** No special partial-settlement state on the position; the position is correct from T regardless. The PS/PSS contra-balances simply drain in pieces.

### 6.6 Floor 6 — Reconciliation to nostro across the open window

Covered in §4 in full.

**Key finops principle:** lead-lag is by design, not a break. The morning recon report has a column for "expected lead-lag" which is computed as `Σ over all open trades: signed_cash_amount`. The break is `nostro_external − (own_cash + expected_lead_lag) − inflight`. **A break can only be raised on this residual, never on the lead-lag itself.**

### 6.7 Floor 7 — Short sale composing with §13 SBL six-coordinate model

A short sale is a sell where the seller does not own the shares — they have borrowed them from a lender (Bob lends 1000 NVDA to Alice, Alice sells 500 NVDA to Carol).

Per v10.3 §13, the short sale is a single move on Alice's `own` coordinate:

```
At trade time (Alice sells 500 NVDA @ $100 to Carol):

  T0_borrow (already happened): Alice borrows 1000 NVDA from Bob — sets Alice's borr=1000.
  T0_sell  (the short sale itself):

  Transaction T0_sell [type=ECONOMIC_RECOGNITION, tx_id=SELL-500-NVDA-T0]:
    -- Securities leg
    Move 1: w_Alice → PSS_payable[w_Alice, Carol, NVDA]    NVDA  500   (one coordinate: own)
    -- Wait: which coordinate does Move 1 touch on Alice?
```

This is where we have to be careful and respect §13.

§13.6 ("Short Selling and Inventory") says: *"The sell writes only own. The borr coordinate is not touched."* So the sell is `Alice.own -= 500`. But then we need a contra: who receives the +500? The PSS_payable for Carol, which is a virtual wallet whose `own` coordinate goes negative (representing "Alice owes Carol 500 NVDA on settlement").

Restated cleanly with the six-coordinate model in mind:

```
Transaction T0_short_sell [type=ECONOMIC_RECOGNITION]:
  -- Securities leg (touches own coordinate of Alice and PSS_payable wallet)
  Move 1: w_Alice.own → PSS_payable[w_Alice, Carol, NVDA].own    NVDA  500
  -- After: Alice.own(NVDA) goes from 0 to -500 (consistent with §13.6)
  --        PSS_payable.own(NVDA) goes from 0 to +500

  -- Cash leg
  Move 2: PS_receivable[w_Alice, Carol, USD].own → w_Alice.own   USD  50000
  -- After: w_Alice.own(USD) += 50000
  --        PS_receivable.own(USD) goes from 0 to -50000 (Carol owes us $50k)

At T+2 settlement:
  Move 1: PSS_payable[w_Alice, Carol, NVDA] → w_Carol_broker_virtual    NVDA  500
  -- (PSS_payable drains to 0; Carol's broker virtual wallet shows the delivered shares)

  Move 2: w_Carol_broker → PS_receivable[w_Alice, Carol, USD]           USD  50000
  -- (PS_receivable drains to 0; cash arrives at Alice's nostro)

  -- Where do the shares come from? From Alice's borrowed inventory. But borr is not
  -- touched by the sell! borr remains at +1000 because the obligation to return to
  -- Bob is unchanged. The settlement of the short sale draws on Alice's owned inventory
  -- (which is now -500, because she sold short).
```

**Composition with §13 invariants:**

- §13's `avail = own − onloan + borr` for Alice: at T (post-sell), `avail = -500 − 0 + 1000 = 500`. ✓ Alice can still cover. (She still has 500 borrowed shares she hasn't sold.)
- After T+2 settlement: `Alice.own(NVDA) = -500` (the short position is now also settled in custody), `Alice.borr(NVDA) = 1000` (still owe Bob). Net `avail = 500`.
- When Alice eventually buys back to cover: she goes long 500 with PS/PSS through the buy mechanism (§2). Her `own` returns to 0. Her `borr` is still 1000 until she returns to Bob. When she returns, it's a separate SBL transaction (§13.7 return).

**Composition is clean.** The short sale uses our PS/PSS pattern on the short leg; the borrow/return uses the §13 SBL state machine on the lending leg. **The two are orthogonal because they touch different wallets (Alice vs. Carol vs. Bob) and partially different coordinates (own vs. onloan/borr).** No interference.

### 6.8 Floor 8 — Recall during the window

Bob recalls 400 NVDA from Alice while Alice's short sale is in T+0..T+2 settlement window.

Per §13 SBL state machine: recall is a notification (state goes `ACTIVE → RECALLED`), no moves until return.

In our window:

- The recall does **not** touch any PS/PSS wallet. PS/PSS reflects only Alice ↔ Carol settlement.
- The recall **does** start a clock on Alice to return 400 NVDA to Bob.
- If Alice cannot return 400 NVDA (her `avail = -500 - 0 + 1000 = 500` post-sell — actually 500 is still ≥ 400, so she can return 400 from her remaining borrowed inventory).
- If Alice's `avail < 400`: a **buy-in** is initiated by Bob (§13.7), creating new ECONOMIC_RECOGNITION transactions for Alice to buy 400 NVDA in the market. Those go through the standard PS/PSS cycle.

**The recall is a §13 lifecycle event that may *induce* a new market trade. The market trade then goes through the standard deferred settlement mechanism.** No special interaction. Composition by sequential triggers, not by shared state.

### 6.9 Floor 9 — Corporate action in the window (cum/ex, entitlement under economic-exposure-at-T)

A dividend on XYZ has record date `T+1` (between trade T and settlement T+2). Question: does the buyer (us) or the seller (GS) receive the dividend?

**Economic-exposure-at-T principle (Invariant E1):** the buyer is the economic owner from T onward. The buyer is entitled to the dividend.

But the **legal ownership** at the CSD on the record date — which determines who appears on the issuer's register and who the issuer pays — is the seller. The market handles this with **the cum/ex split**: trades between (announcement_date - n) and (ex_date - 1) are "cum" (buyer entitled); trades on/after ex_date are "ex". The exchange/CSD performs an automatic adjustment via a **manufactured dividend** payment from seller to buyer for cum trades that haven't settled by record date.

Ledger treatment:

```
At T (trade): record `entitlement_status = CUM` on the trade's metadata.

At record date T+1:
  Transaction T_cum_entitlement [type=ACCOUNTING]:
    Snapshot: w_us.own(XYZ) = +100. PSS_receivable[w_us, GS, XYZ] = -100.
    Compute entitlement: w_us economically owns 100 shares of XYZ on record date.
    Spawn: dividend_due_to_w_us = 100 × dividend_per_share.

At ex_date T+1 (or the relevant pay date):
  Issuer pays dividend to legal owners (still GS at the CSD).
  Issuer dividend recognition:
    Move: w_issuer_virtual → w_GS_broker  USD  (100 × dividend_per_share)
    -- (because GS is on the legal register on record date)

  Manufactured payment (CDM ManufacturedPayment, L10):
    Transaction T_manufactured [type=SETTLEMENT_FINALITY-style]:
      Move: w_GS_broker → w_us    USD   (100 × dividend_per_share)
      -- (GS passes the dividend through to us, the economic owner)
```

This composes with the standard dividend flow (v10.3 §5.3) and the manufactured-payment pattern (v10.3 §13.10 on SBL manufactured dividends). **The economic-exposure-at-T principle is preserved: the buyer gets the dividend, mediated by the manufactured payment mechanism.**

What if the trade gets cancelled before record date? The cum entitlement reverses with the cancellation. What if it fails settlement past record date? The manufactured payment still flows (the buyer was the economic owner during record date regardless).

**This case is the strongest argument for trade-date accounting + economic-exposure-at-T.** It is also the one where naive "settlement-date" accounting systems silently misallocate dividends and run into reconciliation hell with custodians who *do* honour cum/ex by trade date.

### 6.10 Floor 10 — Cross-currency (Herstatt)

We buy 100 XYZ (a Tokyo-listed equity, settles JPY) for $5,000 USD equivalent at trade T. The ISIN is JPY-denominated; the cash leg is JPY at the JPY price. We separately hold a USD/JPY FX leg to fund the JPY cash.

**Two trades, two PS/PSS sets.**

```
Trade 1 (equity, JPY): buy 100 XYZ @ ¥75,000 = ¥7,500,000.
  At T:
    Move 1: PSS_receivable[w_us, JP_broker, XYZ] → w_us  XYZ  100
    Move 2: w_us → PS_payable[w_us, JP_broker, JPY]  JPY  7,500,000
  At T+2 (Tokyo): JPY DvP at JPCSD.

Trade 2 (FX): buy ¥7,500,000 vs sell $50,000 USD (at ¥150/$).
  At T:
    Move 1: PS_receivable[w_us, FX_cpty, JPY] → w_us  JPY  7,500,000
    Move 2: w_us → PS_payable[w_us, FX_cpty, USD]  USD  50,000
  At T+2 (CLS-eligible): atomic via CLS.
```

**Herstatt risk** is real: between T and T+2, our USD leg might pay (settle in NY morning) while the JPY leg fails (Tokyo afternoon would already be next day). The framework cannot eliminate this — it is timing risk between two CSDs (cf. v10.3 §2.7).

What the framework **does** is:
- Track each leg independently in its own PS pair.
- Make the asymmetric settlement **visible** in the recon report: if USD leg has settled but JPY hasn't, that asymmetry shows as a PS_payable (USD) at zero but PS_payable (JPY) at non-zero, with `wf-confirm-break` flagging the mismatch.
- For CLS-settled FX, the atomicity is *external* (CLS PvP); the ledger just records the compound finality on both legs.

**Recommendation:** book FX trades as **single business events with two transactions** that share a `business_event_id` but each generates its own PS pair, exactly as the existing CDM `BusinessEvent` per v10.3 §9 supports. Operations watches the cross-leg recon: a non-zero residual after both legs' nominal settlement = Herstatt incident.

### 6.11 Floor 11 — DvP atomicity — what "atomic" means when recognition is at T and clearance at T+2

This is the philosophical question and the answer is precise:

- **Atomic at recognition (T):** the two moves of the recognition transaction (securities recv + cash payable) are atomic. The executor commits them as one transaction. If the cash leg cannot be debited (insufficient cash, mandate breach), the securities leg is rolled back. v10.3 §8.5 ledger-level DvP.

- **Atomic at finality (T+2):** the two moves of the finality transaction (securities depot credit + nostro debit) are atomic. CSD-level DvP guarantees the *real-world* atomicity (DTC, Euroclear, Clearstream all provide DvP). v10.3 §8.5 settlement-level DvP.

- **NOT atomic in time:** recognition and finality are **deliberately separated** by 2 days. This is the *whole point* of trade-date accounting. The economic exposure exists from T; the custody movement happens at T+2; they are not, and should not be, the same event.

- **What "atomic" does NOT mean:** "settlement happens at T". That would be a synchronous-settlement system (T+0 with full DLT), which is a different operating model. v10.3 explicitly supports both T+0 and T+N; in T+0 the recognition and finality transactions are scheduled on the same `tx_id_chain` and may even commit in the same `BalancedTransaction` (two `Transaction` objects in one `BusinessEvent`).

**In all cases, the atomicity boundaries respect transaction boundaries**, never blurred across them. This is the StatesHome C3 atomicity guarantee inherited unchanged.

---

## 7. Worked numerical example

**Setup:**
- T = 2026-04-30 09:30 ET
- Buy 100 XYZ @ $50.00, expected settle 2026-05-04 (T+2).
- Pre-trade: `w_us.own(USD) = 1,000,000.00`, `w_us.own(XYZ) = 0`.
- Price evolution: $50.00 (T), $52.00 (T+1 close), $51.50 (T+2 close).

### 7.1 At T (2026-04-30 09:30)

```
Transaction TX1 [type=ECONOMIC_RECOGNITION, tx_id=BUY-100-XYZ-2026-04-30]:
  Move 1: PSS_receivable[w_us,GS,XYZ] → w_us   unit=XYZ  qty=100
  Move 2: w_us → PS_payable[w_us,GS,USD]       unit=USD  qty=5,000.00
  metadata: { expected_settle: 2026-05-04, status: EXECUTED }

Wallet snapshot post-TX1:
  w_us.own(USD)                       =   995,000.00
  w_us.own(XYZ)                       =       100
  PS_payable[w_us,GS,USD].own(USD)    =     5,000.00
  PSS_receivable[w_us,GS,XYZ].own(XYZ)=      −100
  Σ_w w(USD) = 995000 + 5000 = 1,000,000 ✓ (conservation)
  Σ_w w(XYZ) = 100 + (-100) = 0 ✓
```

**PnL at T (immediately post-trade):**
```
V_T = w_us.own(USD)    × P_T(USD)   + w_us.own(XYZ)   × P_T(XYZ)
    = 995,000           × 1.0        + 100             × 50.00
    = 995,000 + 5,000
    = 1,000,000.00
```
Same as pre-trade `V_{T-}` = 1,000,000. **PnL on the trade itself: 0.** This is correct — a fair-priced trade at execution has zero P&L, matching v10.3 §3 path-independent PnL.

The PS_payable contributes 5,000 × 1.0 = 5,000 to its wallet's value, and PSS_receivable contributes -100 × 50.00 = -5,000 to its wallet's value. Net contribution of the contra wallets to OUR portfolio = 0 (they are virtual; we don't include them in `V_us`). The portfolio-level valuation reads only **real** wallet balances, consistent with v10.3 §2.5.

### 7.2 At T+1 close (2026-05-01, XYZ → $52.00)

No transactions emitted. Position unchanged. New valuation:

```
V_{T+1} = w_us.own(USD) × P_{T+1}(USD) + w_us.own(XYZ) × P_{T+1}(XYZ)
        = 995,000 × 1.0 + 100 × 52.00
        = 995,000 + 5,200
        = 1,000,200.00

PnL_{T+1} = V_{T+1} - V_T = 1,000,200 - 1,000,000 = +200.00
```

**PnL is +$200.00 at T+1 even though no cash has moved.**

This is the headline. The ledger is correct because:
- `w_us.own(XYZ) = 100` from T onward (Invariant E1).
- The valuation function reads `own`, not `settled_qty`.
- The PS_payable (5,000.00) and PSS_receivable (-100 shares) contribute zero to `V_us` because they're not real.

A naive settlement-date-accounting system would show `V_{T+1} = V_T = 1,000,000` (no XYZ on the books yet) and a $200 surprise on T+2. **That is the bug we are designing against.**

### 7.3 At T+2⁻ (2026-05-04 09:00, instruction sent)

State-only ACCOUNTING transaction:

```
Transaction TX2 [type=ACCOUNTING]:
  -- No moves
  metadata: { refers_to: TX1, new_status: INSTRUCTED }
```

Position and valuation unchanged.

### 7.4 At T+2 settlement (2026-05-04 16:30, finality)

```
Transaction TX3 [type=SETTLEMENT_FINALITY, tx_id=BUY-100-XYZ-2026-04-30-final]:
  Move 1: PS_payable[w_us,GS,USD] → w_GS_broker  unit=USD  qty=5,000.00
  Move 2: w_GS_broker → PSS_receivable[w_us,GS,XYZ]  unit=XYZ  qty=100
  metadata: { refers_to: TX1, new_status: SETTLED, sese.025: ..., camt.054: ... }

Wallet snapshot post-TX3:
  w_us.own(USD)                         =   995,000.00
  w_us.own(XYZ)                         =       100
  PS_payable[w_us,GS,USD]               =         0.00
  PSS_receivable[w_us,GS,XYZ]           =         0
  w_GS_broker.own(USD)                  =     5,000.00   (the cash they got from us)
  w_GS_broker.own(XYZ)                  =      −100      (the shares they gave us)

  Σ_w w(USD) = 995000 + 5000 = 1,000,000 ✓
  Σ_w w(XYZ) = 100 - 100 = 0 ✓
```

`w_us.own(XYZ)` and `w_us.own(USD)` are **unchanged from T+0** (Invariant E1 verified).

### 7.5 At T+2 close (XYZ = $51.50)

```
V_{T+2} = 995,000 × 1.0 + 100 × 51.50
        = 995,000 + 5,150
        = 1,000,150.00

PnL_{T+2} = V_{T+2} - V_{T+1} = 1,000,150 - 1,000,200 = -50.00   (mark-down on T+2)
PnL cumulative = V_{T+2} - V_T = 1,000,150 - 1,000,000 = +150.00 ✓
                              = +200 (T+1 mark-up) − 50 (T+2 mark-down)
```

PnL path-independence (P10) holds across the entire trade lifecycle, T-through-settled.

### 7.6 Decimal arithmetic check

Every computation above used `Decimal(18,2)` for cash, `Decimal(18,0)` for shares. No float arithmetic. Tolerances: zero — every figure reconciles to the cent.

### 7.7 Recon at T+2 morning (before finality)

09:00 ET 2026-05-04 (before DTC reports finality). Suppose JPMC nostro reports `nostro_external = 995,000.00` (the cash hasn't left yet). Recon identity:

```
LHS: nostro_external = 995,000.00
RHS: w_us.own(USD) − Σ PS_payable + Σ PS_receivable + inflight
   = 1,000,000 − 5,000 + 0 + 0   ... wait, w_us.own(USD) = 995,000 already.
   = 995,000.00 − 0 + 0 + 0
```

I had a brain-glitch. Let me rebuild this carefully:

After the recognition at T, `w_us.own(USD) = 995,000` (the trade already debited our internal cash). Before finality at T+2, the actual cash hasn't left JPMC (the nostro still shows 1,000,000 from JPMC's external view, or wherever it was). So:

```
LHS: nostro_external (per JPMC camt.053)  = 1,000,000.00
RHS: w_us.own(USD) − Σ PS_payable + Σ PS_receivable + inflight
   = 995,000 − 5,000 + 0 + 0
   = 990,000 ❌
```

Hmm, that's a $10,000 discrepancy. Where's the bug?

The bug is in the sign convention of the recon identity. Let me restate carefully:

- `w_us.own(USD)` is what the **internal ledger** says we have.
- `nostro_external` is what **JPMC** says we have.
- Internal already reflects the trade: `w_us.own = 995,000`. The other 5,000 is "in flight to GS via JPMC" — sitting in `PS_payable[w_us,GS,USD] = +5,000`.
- JPMC has not yet debited our nostro: `nostro_external = 1,000,000`.

So the relationship is:

```
nostro_external  =  w_us.own  +  PS_payable_owed_by_us_not_yet_disbursed  −  PS_receivable_owed_to_us_not_yet_received  +  inflight_outbound

       1,000,000  =  995,000   +  5,000                                    −  0                                      +  0
```

Yes: when **WE owe** (PS_payable > 0) and the wire **hasn't gone out**, JPMC still shows our balance fat. So PS_payable adds to JPMC's view. PS_receivable (someone owes us, hasn't paid yet) reduces JPMC's view. Inflight (we wired but recipient hasn't confirmed) reduces JPMC's view further.

**Corrected recon identity:**

```
nostro_external(w, ccy)  =  w.own(ccy)  +  Σ PS_payable[w, *, ccy]  −  Σ PS_receivable[w, *, ccy]  −  inflight_outbound(w, ccy) + inflight_inbound(w, ccy)
```

(The signs flipped from §4.1; updating Invariant E6.) Verify with the example:
- T+2 morning: 1,000,000 = 995,000 + 5,000 − 0 − 0 + 0 = 1,000,000. ✓
- T+2 evening (post-finality): nostro_external = 995,000 (JPMC has now debited). RHS = 995,000 + 0 − 0 − 0 + 0 = 995,000. ✓

This corrected identity is now Invariant E6 (revised). The sign error in §4.1 is corrected here. **Lesson: the Decimal discipline is non-negotiable AND so is the sign discipline. I caught my own bug in the worked example; this is exactly why these examples must be traced numerically.**

### 7.8 What the morning recon report looks like at each phase

**Morning of T+1 (2026-05-01 09:00 local):**

```
COUNTERPARTY  | CCY | BUCKET | GROSS_PAYABLE | GROSS_RECEIVABLE | NET     | TRADES | AGING
GS            | USD | T+1    |      5,000.00 |             0.00 | +5,000  | 1      | 1bd
                                                                                       (= 5d remaining
                                                                                       in window)

Reconciliation to JPMC nostro USD:
  nostro_external (camt.053):    1,000,000.00
  w_us.own(USD):                   995,000.00
  + Σ PS_payable:                    5,000.00
  − Σ PS_receivable:                     0.00
  − inflight_out:                        0.00
  + inflight_in:                         0.00
  ─────────────────────────────────────────────
  expected nostro:               1,000,000.00
  break:                                 0.00 ✓

Open trades by aging:
  T-1 day: 1 trade, $5,000 payable, all status=EXECUTED (waiting for INSTRUCTED)
  Overdue: 0 trades  ← this is the column ops watches
```

**Morning of T+2 (2026-05-04 09:00 local, before finality):**

```
COUNTERPARTY  | CCY | BUCKET     | GROSS_PAYABLE | GROSS_RECEIVABLE | NET     | TRADES | AGING
GS            | USD | T+2_TODAY  |      5,000.00 |             0.00 | +5,000  | 1      | 2bd

Reconciliation to JPMC nostro USD:
  nostro_external (camt.053):    1,000,000.00
  RHS:                           1,000,000.00
  break:                                 0.00 ✓

Watchlist: 1 trade settling today (T+2_TODAY bucket), 100% with status INSTRUCTED. ✓
Overdue: 0 trades. ✓
```

**Morning of T+3 (2026-05-05 09:00 local, post-finality):**

```
All buckets empty. No open exposure to GS.

Reconciliation to JPMC nostro USD:
  nostro_external (camt.053):      995,000.00
  RHS:                             995,000.00
  break:                                 0.00 ✓
```

**This is the morning recon shape.** It is the central operational artifact. Every break that fires here is real. Every non-break (no break) is the *expected* lead-lag.

---

## 8. What the BreakRegister sees and does NOT see

### 8.1 Does NOT see (during normal lead-lag)

- An open PS_payable for a trade with `expected_settle ≥ today`. Expected.
- An EXECUTED status trade pending instruction. Expected unless past affirmation cutoff (then `wf-confirm-break`).
- An INSTRUCTED status trade pending finality. Expected until end-of-day on `expected_settle_date`.
- A non-zero `(w_us.own - nostro_external + Σ PS_payable - Σ PS_receivable)` aggregate. Expected; this is the lead-lag.
- A finality message arriving up to `T+settle_buffer` after `expected_settle_date`. Expected on cross-border (e.g., Asian markets settling in our European morning).

### 8.2 DOES see

- Recon residual `≠ 0` after stripping out the expected lead-lag. Investigate: either own-cash off, nostro mis-reported, or PS/PSS off. Goes to `wf-position-break`, owner: middle-office reconciliation.
- Trade past `expected_settle_date` with `status ∉ {SETTLED, FAILED, PARTIALLY_SETTLED, CANCELLED}`. Auto-aged at T+1bd → `Aged-1`. `wf-confirm-break`, owner: settlement operations.
- A `sese.024` (fail attestation) inbound. Spawns CSDR_PENALTY obligation; `wf-obligation-break` if penalty cash flow doesn't materialise.
- A `sese.025` arriving with **wrong amount** vs. expected. Hard break: `wf-confirm-break`, owner: settlement operations, do NOT apply the finality moves; quarantine and investigate.
- A `sese.025` arriving with **no matching recognition transaction** (`tx_id_ref` not found). `wf-confirm-break`. Possibly a counterparty error or a duplicate. Quarantine.
- A duplicate `sese.025` (same `(tx_id_ref, finality_attestation_id)`). **Idempotently dropped** by the executor (P5); not a break.

### 8.3 Aging policy (composes with `L18` FSM)

| Aging state | Trigger | Action |
|---|---|---|
| Open | New mismatch | Investigate manually; ops queue |
| Investigating | T+0 | Owner assigned |
| Assigned | T+0 | Owner working |
| Aged-1 | T+1 bd unresolved | Notify supervisor |
| Aged-3 | T+3 bd | Escalate to head of desk |
| Aged-5 | T+5 bd | Escalate to head of operations |
| At-Risk | exposure ≥ €1M | Risk committee |
| Material | exposure ≥ €10M | Governance committee, regulator notification per BCBS 239 |

### 8.4 Idempotency under replay of CSD finality messages

The `tx_id` of a finality transaction is `hash(refers_to_tx, finality_attestation_id, attempt_seq)`. Replaying the same `sese.025`:

1. Settlement orchestration workflow reads the CDS message.
2. Computes `(refers_to_tx, finality_attestation_id)`.
3. Queries `L13.MoveStream` for an existing transaction with this key.
4. If found: workflow exits no-op. P5 idempotency.
5. If not: emits the finality transaction.

This works because of v10.3 P5 (transaction idempotency by tx_id) plus the deterministic `tx_id` derivation. **A duplicate sese.025 from a flapping CSD link does not create a duplicate finality.** Critical.

### 8.5 Replay across CSD message storms

If 10,000 `sese.025` messages arrive in 60 seconds (e.g., end-of-day batch finality from DTC), the settlement orchestration workflow processes them as Temporal signals (data v1.0 §11.2). Each spawns an idempotent finality activity. The executor commits each finality transaction sequentially (single-writer per workflow) but in parallel across distinct workflows. End-of-day reconciliation report runs after all settlement workflows have drained their queues.

---

## 9. What auditors and operations actually demand

### 9.1 What auditors ask

From a Big Four audit perspective (PwC/EY/KPMG/Deloitte cash-equity audit):

1. **Transaction completeness.** "Show me every trade executed on date X." Answer: filter `L13.MoveStream` for `transaction_type = ECONOMIC_RECOGNITION` and `trade_date = X`. **Single source of truth** (v10.3 §2.7 self-consistency).
2. **Settlement-status reconciliation.** "Show me unsettled trades at the audit cutoff date." Answer: trades with `status ∈ {EXECUTED, INSTRUCTED, PARTIALLY_SETTLED, FAILED}` and `expected_settle_date ≤ cutoff < today`. Tie to PS/PSS wallet balances.
3. **Audit trail for every status change.** Every state transition is its own immutable transaction (`L13.MoveStream`, append-only, hash-chained). v10.3 P4.
4. **Tie internal cash to the bank/custodian statement.** That is exactly the recon identity (E6).
5. **Reasonableness of accruals (CSDR penalties).** Every `CSDR_PENALTY` obligation has `discharge_predicate.fields = {qty, price, rate_bp, days, currency, lei}`. Computed by pure function; no human discretion (E5).
6. **Going-concern of failed trades.** What trades failed in period, what's the resolution status, what's the cumulative penalty? `L18.BreakRegister` query.
7. **IFRS 9 derecognition.** Was anything derecognised before settlement? **No** — economic-exposure-at-T means we recognise from T, derecognise at the same point as the sell trade is recognised (i.e., at the sell's T). Settlement is operational, not accounting (Invariant E1). This is GAAP-aligned for trade-date accounting and IFRS 9 §3.2.6 aligned for SBL.

The audit gates pass because **every state has a determining event in the move stream, and every event is an immutable record.** v10.3 §11 P4 and P9.

### 9.2 What operations needs daily

1. **The morning recon report (§4.2).** Gate to "books are clean for the day."
2. **The settle-today watchlist.** Trades in `T+2_TODAY` bucket, status counts (EXECUTED vs. INSTRUCTED). All must be INSTRUCTED before market open or there's a problem.
3. **The overdue list.** Any unsettled trade past `expected_settle_date`. Each one is a ticking clock for CSDR penalties and buy-in.
4. **The break dashboard.** `L18.BreakRegister` filtered by ownership team, aging, and exposure.
5. **The cancel/correct queue.** Approved cancellations awaiting CORRECTION transaction.
6. **The CSDR penalty register.** Open `CSDR_PENALTY` obligations and their accumulating cash impact.
7. **The fix-broken-trade queue.** Trades quarantined by `wf-confirm-break`, awaiting investigation.

These are queryable views over `L13.MoveStream`, `L15.Obligation`, `L18.BreakRegister`, and the PS/PSS wallets. **No new storage required**; just new SQL/Datalog queries (the lineage cursor of data v1.0 §11.7 supports them).

---

## 10. Underspecification I am flagging

The corpus is strong but a few corners need ruling, IMO. I give my best answers; mark the corpus-vs-finops gap.

### 10.1 Bilateral netting at T+2 between us and a single counterparty

If we have 50 trades vs. GS settling on the same day, all in USD:
- Sum payable: $X. Sum receivable: $Y.
- The CCP/counterparty nets: only `|X − Y|` actually moves.

Per v10.3 §8.6, netting is settlement-layer, not Ledger. The Ledger's gross records are authoritative. **My ruling:** PS_payable and PS_receivable wallets stay gross. Each finality transaction drains its own row. The net wire that hits the nostro is captured separately (in `inflight` initially, then in the nostro debit). The **algebraic identity** `Σ_individual_finality_cash = nostro_aggregate_debit` is checked by an additional recon row in §4.2.

This creates a small operational bookkeeping load but **preserves per-trade traceability**, which is non-negotiable for ops. If the corpus wants strict netting at finality, the PS pair would need to be supplemented by per-CCP-day net wallets — possible but more state. **My recommendation: stay gross.**

### 10.2 Same-day cancellation before instruction

If a trade is cancelled at T+0 14:00 before any instruction, the cancellation is effectively a void. **My ruling:** still emit the CORRECTION transaction (§5.3). The original recognition tx remains in the move stream (P4). Some firms drop pre-instruction cancellations entirely; this proposal does not. The audit trail includes both the recognition and the cancellation. The PS/PSS balances net to zero.

### 10.3 Soft-fail vs hard-fail

CSDs distinguish **lack-of-cash fails** (LACK), **lack-of-securities fails** (ISIP), **other** (CONA, OTHR). Each triggers different penalty rates and different remediation playbooks. **My ruling:** capture as a typed enum on the FAILED status: `fail_reason ∈ {LACK, ISIP, CONA, OTHR}`. Pure projection over the inbound `sese.024`. Drives the obligation kind sub-classification and the CSDR penalty rate selection.

### 10.4 Cross-border settlement timezone math

A US equity trade at T = 16:30 ET on 2026-04-30 has `expected_settle_date = 2026-05-04` per US T+2. Same trade booked from a London desk at T = 21:30 BST on 2026-04-30 (= 16:30 ET) is *also* `expected_settle_date = 2026-05-04`. The London ops sees it in their morning recon on 2026-05-01 already in `T+1` bucket (because for London, "today" is 2026-05-01). **My ruling:** every recon report is timestamped with `local_date` and `reporting_timezone`, and the bucket is computed in the reporting timezone. The expected_settle_date is pinned to the venue's CSD timezone. Both timezones are explicit; no implicit conversions. Data v1.0 invariant: "All timestamps must be explicitly UTC or have time zone attached." We comply.

### 10.5 Fee, commission, and other anciliaries

A real cash-equity trade has:
- Brokerage commission ($5–$50).
- SEC fee, FINRA TAF (US), stamp duty (UK), FTT (FR/IT) — venue-specific.
- Custodian charges.

These are **separate cash legs** in the same `BusinessEvent`, each with its own (small) PS_payable. The recognition transaction at T thus includes 1 securities + N+1 cash legs. **My ruling:** keep them as additional moves in the recognition transaction. Do NOT bundle into the principal. This makes recon to broker statements per-leg precise. Some firms net fees into the principal — but this loses fee-attribution recon and is a finops anti-pattern. **Recommendation: stay unbundled.**

### 10.6 What if recognition and settle currencies differ on a single trade?

E.g., a Tokyo-listed ADR traded in USD, settled in JPY. The USD price → JPY cash conversion happens at the venue's FX rate. **My ruling:** recognition emits the JPY cash leg per the venue convention. Pre-trade USD/JPY hedge if any is a separate trade. Cross-currency P&L attribution is the valuation v1.0 problem (Greeks under FX), not deferred-settlement.

### 10.7 Multi-allocation trades (street → block → allocations to N sub-accounts)

A block trade allocates to N internal sub-funds. The block executes at T; allocations happen at T+0 to T+1; settlement at T+2 per allocation.

**My ruling:** the block is a single recognition transaction against `w_block_holding`. The allocation is N transactions from `w_block_holding` to `w_subfund_i` at the allocation moment. Each allocated subfund has its own PS_payable derivation? No — the cash moves between sub-funds and the broker-virtual stay at the block level until settlement, then drain to per-subfund PS/PSS at finality. This is involved enough that I am flagging it for Phase 2: how the block→allocation→settlement chain composes with PS/PSS deserves a dedicated worked example. **Not solved here.**

---

## 11. What I am *not* claiming

- This proposal does not eliminate Herstatt risk (it can't; Herstatt is a real-world timing risk between two CSDs).
- This proposal does not handle FX swaps or repo (those are §13/§14 territory + their own Phase work).
- This proposal does not propose changes to the StatesHome three-map ruling. Strict compliance.
- This proposal does not propose changes to the conservation law, the move primitive, the lifecycle FSM, or the transaction-type enum (except adding `SETTLEMENT_FINALITY` as a sub-class of `SETTLEMENT`).
- I have not modelled the failure of the ledger system itself (correlated outage between Temporal and `L13.MoveStream`). That's a DORA Article 8 concern, not a deferred-settlement design concern.
- The wallet identities I introduced (PS, PSS, nostro, depot, etc.) follow v10.3 §2.5 "virtual wallet" semantics; I have not introduced a new wallet *type*.
- I have not enumerated the full ISO 20022 message catalog beyond `sese.023/024/025`, `camt.053/054`, `pacs.009`. Operations will need the full set in implementation.

---

## 12. The one-paragraph summary, redux

**Standard buy T+2 in our books, T-by-T:**

```
At T:    w_us.own(XYZ): 0 → +100;  w_us.own(USD): m → m-5000
         PSS_recv = -100;          PS_payable = +5000
         Status: EXECUTED. Economic exposure recognised. Conservation holds.

At T+1:  Nothing moves. PnL marks at +200 because price went $50→$52.
         The PS/PSS wallets still carry their open balances.
         Status: INSTRUCTED (after morning batch).

At T+2-: Status: INSTRUCTED, all wallets unchanged from T+1.
         CSD has the instructions. Custody movement scheduled.

At T+2+: PSS_recv: -100 → 0;  PS_payable: +5000 → 0
         w_GS_broker.own(XYZ): 0 → -100;  w_GS_broker.own(USD): 0 → +5000
         w_us.own(XYZ): unchanged at +100.   ← THE INVARIANT.
         w_us.own(USD): unchanged at m-5000. ← THE INVARIANT.
         Status: SETTLED.
         Recon: nostro = m-5000 = w_us.own(USD).  Break = 0.
```

The PS_payable wallet balance over the lifecycle traces a step function: `0 → +5000 (at T) → +5000 (during T+1) → +5000 (during T+2-) → 0 (at T+2+)`. Operations watches this profile. A non-zero PS_payable past `expected_settle_date + 1bd` is a break. A zero PS_payable matching a SETTLED status is the happy path.

**This is what the framework should look like for cash-equity deferred settlement.** Same mechanism degenerates to T+1 (smaller window), T+0 (zero window, recognition and finality merge). Same mechanism extends to short sales (composes with §13 own coordinate), to corporate actions (manufactured payments per §13.10 pattern), to cross-currency (independent PS pairs per leg + Herstatt monitoring), to failures (CSDR_PENALTY obligation per §11.5 of data v1.0). No special cases. No new primitives. Operations and audit get exactly the artifacts they need: per-counterparty per-currency reconciliable contra-balances, immutable status lifecycle, deterministic finality contra-transactions, and a daily morning recon that ties internal own-cash to external nostro through an algebraic identity.

**Disagreement, flagged:** I revised my own Invariant E6 sign in §7.7. The corrected identity is `nostro_ext = w.own + Σ PS_payable − Σ PS_receivable − inflight_out + inflight_in`. The sign discipline matters and this is the kind of bug that takes recon teams months to find in production.

---
*— finops-architect, Phase 1, Team A. Independent. No cross-talk consulted.*
