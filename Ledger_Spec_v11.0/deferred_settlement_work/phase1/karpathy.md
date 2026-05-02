# Deferred Settlement: Building It Move by Move

**Author:** karpathy (Phase 1, independent proposal)
**Question:** How should the Ledger represent the open settlement obligation between T and T+2 such that
(a) economic position is true from T,
(b) the obligation is explicit and reconcilable,
(c) the ledger reconciles to the custodian (nostro) at T+2,
(d) the mechanism degenerates across variants — short, recall, corporate action, fail, partial, cross-currency, DvP atomicity?

The right way to attack this is to *build it*. We start with a single buy of 100 XYZ at \$50, write down the moves, verify conservation line by line, then add complexity one variant at a time. Every variant must be motivated by something the simpler model could not handle.

---

## 0. Ground rules from the corpus

Five facts from v10.3 + StatesHome + data v1.0 are non-negotiable. Anything I propose must be expressible inside them.

1. **A move is `src -= q; dst += q`.** Conservation holds *per move*, not at end of day (§2.3, §2.4).
2. **Trade-date accounting.** The economic position exists at T; the framework "models this by recording the trade as an atomic transaction at trade time (capturing economic intent) and tracking settlement status per leg via unit state or move metadata" (§2.6 last paragraph; §11.4 ¶ Settlement timing distinctions).
3. **The settlement projection is a *read*, not a *commit*.** `settle_projection : Transaction -> SettlementInstruction` is a pure, stateless function over an *already committed* transaction (§11.1). It does not generate a second transaction at T+2.
4. **Status lifecycle EXECUTED → INSTRUCTED → SETTLED | FAILED** is metadata on the original transaction; no moves are generated when a confirmation arrives (§11.7).
5. **State homes (StatesHome ruling).** Three maps: `ProductTerms[u]`, `UnitStatus[u]` (shared, mutable), `PositionState[w,u]` (per-position, monotone, Option accessor). There is no `WalletState` sector. Whatever we add must fit.

Two lemmas follow immediately:

**Lemma A (no double-write of the real wallet).** If we want PnL to be correct at T *and* at T+2 with no jump, the real wallet must be touched *exactly once* per trade. The settlement event therefore cannot move shares from `nowhere` to `real_wallet` at T+2; it must move them from one virtual wallet to another.

**Lemma B (the obligation must be a wallet balance, not a flag).** A flag on the transaction (`status=INSTRUCTED`) is sufficient for tracking *what stage the message is in*, but it cannot answer "how many shares does our broker owe us at end of day Tuesday?" That is a *quantity*, and quantities live in wallets.

Lemma B is the load-bearing claim of this proposal. Every floor case below tests it.

---

## 1. Strawman: trade-date accounting in the simplest form

Before writing any new machinery, let me try the textbook v10.3 pattern and see where it breaks.

**Setup.** Our portfolio buys 100 XYZ at \$50, T+2 settlement.

```
Wallets:
  w_port           -- real, our portfolio
  w_broker_v       -- virtual, the broker/CCP

Initial:
  w_port(USD)  = 100,000;  w_port(XYZ)  = 0
  w_broker_v(USD) =      0; w_broker_v(XYZ) = 0  (virtual; opens at zero, §2.5)
```

**At T = trade date**, we write the standard trade transaction (§2.5 example):

```
Transaction tx_T (type=SETTLEMENT, settlement_date=T+2):
  Move 1: from=w_port,     to=w_broker_v,  unit=USD, q=5,000
  Move 2: from=w_broker_v, to=w_port,      unit=XYZ, q=100
```

**Conservation, line by line.**
- Move 1: `Q(USD) += -5000 + 5000 = 0`. ✓
- Move 2: `Q(XYZ) += -100 + 100 = 0`. ✓

**Balances at T+ε (after commit, before any settlement).**
- `w_port(USD) = 95,000`, `w_port(XYZ) = +100`.
- `w_broker_v(USD) = +5,000`, `w_broker_v(XYZ) = -100`.

**PnL test.** Suppose price moves \$50 → \$52 between T and T+2, and we revalue at T+1 close.
```
V(w_port) = 95,000 + 100 × 52 = 100,200
PnL       = 100,200 − 100,000 = +200    ✓
```
Right answer (+\$200), and *no cash has moved from our nostro yet*. Good.

**Now ask the hard question.** It is end-of-day Tuesday (T+1). The risk manager asks: *"How many XYZ does our broker owe us tonight?"* The auditor asks: *"What is the cash we are committed to deliver tomorrow?"* The reconciliation engine asks: *"What should the depot show tomorrow morning?"*

I read `w_broker_v(XYZ) = -100` and `w_broker_v(USD) = +5,000`. These two numbers are exactly the open obligation: the broker owes us 100 XYZ, we owe the broker 5,000 USD. Wonderful — the obligation is already a wallet balance. **This is the entire trick.** Trade-date accounting represents the open obligation as a *negative balance in the counterparty's virtual wallet* on the security side, and a *positive balance in the counterparty's virtual wallet* on the cash side. No new primitive is required.

**But.** The strawman fails three of the floor cases. Let me show why, then patch it minimally.

---

## 2. Where the strawman breaks

### 2.1 The reconciliation question (FAIL #1)

At T+2, the custodian sends a `sese.025` confirming 100 XYZ have been credited to our depot. What moves? The strawman has no answer. The shares are already in `w_port` from T. There is nothing left to do.

That sounds clean — but now answer the next question: **"At T+1 morning, what does the depot at our custodian hold for us?"** Zero. The shares have not arrived. But our ledger says we own 100. So `w_port(XYZ) ≠ depot(XYZ)`. The principal complains: "your ledger does not reconcile with the custodian." The §13 recon formula
```
own − onloan + borr + inflight  =  custodian_depot
```
needs an `inflight` term. In the strawman there is no place for it.

The fix v10.3 already hints at: there are *two* virtual wallets, not one. (§2.5 already separates "broker virtual" from "custodian virtual"; we now use that.)

### 2.2 The fail question (FAIL #2)

Suppose the broker fails to deliver on T+2 (CSDR territory). Per §11.4, "the economic position is *not* automatically reversed". OK — but how do I, the auditor, see *which* trades failed and how many shares are still owed? I need a positive list. The strawman gives me a single negative balance `w_broker_v(XYZ) = -100`, but if I have ten trades with the same broker, all I have is the *aggregate* -1000 — I have lost which trade failed. I cannot drive a CSDR penalty calculation off an aggregate.

The fix: the obligation is per-trade, so it must live in a per-trade structure (`PositionState` keyed at the granularity of the trade, or a dedicated `Obligation` leaf — `L_15` in data v1.0).

### 2.3 The cross-currency question (FAIL #3)

For an FX-funded equity buy (USD-funded purchase of EUR-denominated XYZ), the cash leg settles in one time zone and the security leg in another. Herstatt is real (§2.6). The strawman bundles both into one transaction, which is fine for *intent*, but the moment the USD leg settles and the EUR leg has not, we need to be able to say so. A single virtual wallet cannot track per-leg settlement status.

The fix: treat each settleable leg as its own settlement event with its own status, even though they live in the same transaction at trade date.

### 2.4 The short question (FAIL #4)

A short sale (§13.7): "Bob sells 400 borrowed VOD to Carol." Bob's `own` goes from 0 to -400. The strawman puts a negative balance on the broker virtual on the security side ("broker owes me −400 VOD") but that is exactly *Carol's* wallet, not the broker's. The trade and the settlement are *different counterparties*: trade is Bob→Carol, settlement is Bob→CSD via Bob's broker. The strawman has confused the two roles.

The fix: separate **counterparty** (the trade leg's other side) from **settlement venue** (the broker / CSD / custodian where the wire actually moves). This is what §11.2 calls "the settlement layer adds *how*" — but to make recon work we need the *how* to also be a wallet, not just a setting.

---

## 3. The minimal extension: two virtual wallets per leg, one obligation row per trade

I add the *minimum* mechanism that makes all four failures go away. Nothing more.

### 3.1 Two virtual wallets per leg

Replace the single `w_broker_v` with two: one **counterparty mirror** (the trade's other side, identified by LEI) and one **settlement venue mirror** (the CSD/custodian/nostro, identified by BIC). A standard equity DvP buy now uses four virtual wallets:

```
w_cpty_v           -- the executing counterparty (broker LEI)
w_csd_sec_v        -- our depot at the CSD (security side)
w_csd_cash_v       -- our nostro at the cash agent (cash side)
w_port             -- our real portfolio
```

This is consistent with §2.5 ("Each external counterparty is identified by a CDM party reference") and §11.2 ("custodian account identifiers, CSD connectivity"). The counterparty wallet tracks the trade obligation; the CSD wallets track the depot reality.

### 3.2 The Obligation row (L_15, per-trade)

A new `PositionState`-style row (or, equivalently, an `L_15.Obligation` instance, FSM `Pending → Discharged | Compensated | Defaulted`) carries:

```
Obligation:
  obligation_id           -- ULID
  parent_tx_id            -- the trade transaction
  cpty_lei                -- counterparty LEI
  csd_bic                 -- where the wire goes
  side                    -- {SECURITY, CASH}
  unit                    -- ISIN or currency
  quantity                -- positive
  direction               -- {DELIVER, RECEIVE}
  trade_date              -- T
  settlement_date         -- T+2 (or T+1, T+0)
  status                  -- {EXECUTED, INSTRUCTED, SETTLED, FAILED, PARTIAL}
  filled_quantity         -- 0 ≤ filled ≤ quantity
  external_msg_ids[]      -- sese.023/025/etc. references
  csdr_penalty_accrued    -- decimal, can be 0
```

This is *not* a new wallet sector. It is a sidecar tagged to the trade transaction, and it reads like every other obligation in the system (data v1.0 §3 leaf $L_{15}$, FSM `Pending → Discharged | Compensated | Defaulted`).

**The two layers are redundant on purpose.** The wallet balances enforce conservation and PnL; the Obligation rows enforce per-trade accounting and CSDR. Either one alone fails:
- wallet balances alone aggregate trades, losing per-trade granularity (FAIL #2);
- obligation rows alone do not enforce conservation and cannot drive PnL.

The redundancy is *checked*: at any time, for any (cpty, unit), the sum of pending obligations of a given direction must equal the corresponding virtual-wallet balance up to sign. This is invariant **I-ds-3** below.

---

## 4. The Move sequence — building up the standard buy

Now I rewrite the standard buy with the two-virtual-wallet model and verify conservation move by move. **This section is the heart of the proposal and reads like a tutorial.**

### 4.1 At T (trade date)

When the FIX execution report lands, the equity smart contract emits one transaction with two moves:

```
tx_T = Transaction(
    tx_id        = "tx_T_001",
    type         = SETTLEMENT,
    timestamp    = T,
    settlement_date = T+2,        -- in cdm_payload
    cdm_payload  = { cpty.lei, venue.mic, ... }
):
    Move m1: from=w_port,      to=w_cpty_v,   unit=USD, q=5000
    Move m2: from=w_cpty_v,    to=w_port,     unit=XYZ, q=100
```

**Plus** the smart contract creates two `Obligation` rows (one per leg):

```
Obligation o_cash:  parent=tx_T_001, side=CASH,     unit=USD,  q=5000, direction=DELIVER, status=EXECUTED
Obligation o_sec:   parent=tx_T_001, side=SECURITY, unit=XYZ,  q=100,  direction=RECEIVE, status=EXECUTED
```

Conservation per move:
| move | unit | source | dest | Δsrc | Δdst | sum |
|------|------|--------|------|-----:|-----:|----:|
| m1   | USD  | w_port | w_cpty_v | −5000 | +5000 | 0 ✓ |
| m2   | XYZ  | w_cpty_v | w_port | −100 | +100 | 0 ✓ |

Balances after `tx_T`:
```
w_port:    USD=95000,  XYZ=+100
w_cpty_v:  USD=+5000,  XYZ=−100
w_csd_cash_v: USD=0   (untouched — wire hasn't moved)
w_csd_sec_v:  XYZ=0   (untouched — depot hasn't moved)
```

Read off **the answer to "how many XYZ does the broker owe us tonight"**: `w_cpty_v(XYZ) = −100`. Read off **"what does the depot show"**: `w_csd_sec_v(XYZ) = 0`. Both questions answered, both with quantities, both immediately auditable.

### 4.2 At T+1 (no events)

Nothing happens on the books. The risk manager looks at the screen and sees:
```
Real position  w_port(XYZ) = 100         (PnL true)
Cpty owes us   w_cpty_v(XYZ) = −100      (open obligation: receivable)
Cpty owed by us w_cpty_v(USD) = +5000    (open obligation: payable)
Depot          w_csd_sec_v(XYZ) = 0      (wire not yet settled)
Recon          w_port(XYZ) = w_csd_sec_v(XYZ) + |w_cpty_v(XYZ)| = 0 + 100 = 100  ✓
```

The reconciliation identity I codify as a definition:

**Definition (Inflight Reconciliation Identity).**
For each (real wallet `w`, unit `u`):
$$
w(u) \;=\; w^{\mathrm{csd}}_v(u) \;+\; \mathrm{inflight}(w, u)
\quad\text{where}\quad
\mathrm{inflight}(w, u) \;=\; \sum_{\text{cpty } c} \bigl(-w^{\mathrm{cpty},c}_v(u)\bigr)
$$
i.e. *what we own = what the CSD shows us + what counterparties owe us*. This is exactly §13's `own + borr + inflight = custodian_depot` rearranged for the cash-equity case (no SBL, so `borr = 0`, and `own − inflight = depot` reads as `depot = own − inflight`, which I prefer in the form `own = depot + inflight`).

If this identity ever breaks, either the obligation row is missing or the CSD wallet is wrong — either way it is a P3 break (data v1.0 invariant `Φ_6^C`).

### 4.3 Just before settlement, T+2⁻ (instruction sent)

The settlement layer takes `tx_T_001`, runs `settle_projection`, and emits two ISO 20022 messages: a `sese.023` for the security leg (RECEIVE 100 XYZ vs payment) and the corresponding cash side (camt). The Obligation rows transition `EXECUTED → INSTRUCTED`. **No moves are generated.** Status is metadata.

### 4.4 At T+2⁺ (settlement confirmed)

The CSD reports DvP success on `sese.025`. The lifecycle handler emits one **internal-virtual-to-virtual transaction** that moves the receivable out of the counterparty wallet and into the depot:

```
tx_settle = Transaction(
    tx_id     = "tx_settle_001",
    type      = SETTLEMENT,
    timestamp = T+2 (settlement_time),
    parent_tx = tx_T_001,
    cdm_payload = { sese.025 message_id, ... }
):
    Move m3: from=w_csd_cash_v, to=w_cpty_v,    unit=USD, q=5000
    Move m4: from=w_cpty_v,     to=w_csd_sec_v, unit=XYZ, q=100
```

Conservation:
| move | unit | Δsrc | Δdst | sum |
|------|------|-----:|-----:|----:|
| m3   | USD  | −5000 | +5000 | 0 ✓ |
| m4   | XYZ  | −100  | +100  | 0 ✓ |

Balances after `tx_settle`:
```
w_port:        USD=95000,  XYZ=+100         (untouched — PnL stable)
w_cpty_v:      USD=0,      XYZ=0            (closed out — no open obligation)
w_csd_cash_v:  USD=−5000,  XYZ=0            (nostro debited)
w_csd_sec_v:   USD=0,      XYZ=+100         (depot credited)
```

Recon at T+2 close:
```
w_port(XYZ) = w_csd_sec_v(XYZ) + inflight = 100 + 0 = 100   ✓
w_port(USD) = w_csd_cash_v(USD) (sign-flipped) + bank_balance(USD)
```
The cash-side inflight has zeroed; the depot now holds the shares. The Obligation rows transition `INSTRUCTED → SETTLED`.

**The real wallet was touched once, at T (Lemma A holds).** The transition T+2⁻ → T+2⁺ is a virtual-to-virtual rotation — invisible to PnL by construction.

### 4.5 The whole picture (state diagram)

```
            T                       T+2⁻              T+2⁺
            │                          │                 │
 w_port     ├── +100 XYZ ──────────────┴─────────────────┤   (set once at T)
            │
 w_cpty_v   ├── −100 XYZ (receivable) ──┤
            │                          │
            │                          ├── 0 (closed at T+2⁺)
            │
 w_csd_sec_v├── 0 ──────────────────────┤
                                       │
                                       ├── +100 XYZ (settled)

 Obligation EXECUTED ────► INSTRUCTED ─► SETTLED
```

That is the entire mechanism. Two new virtual wallets, one Obligation row per leg per trade, one extra virtual-to-virtual transaction at settlement. Real wallets are inviolable from T onward.

---

## 5. Worked example: 100 XYZ @ \$50 → \$52, PnL = +\$200, no cash moved

This is the canonical floor case, written as a single coherent walkthrough so a developer can lift it directly into a unit test.

### 5.1 Setup
- T = Mon (trade date). Settlement = T+2 = Wed.
- Buy 100 XYZ at \$50.
- Mark-to-market on Tue close: \$52 (so unrealised PnL = +\$200).
- DvP success on Wed.

### 5.2 Move stream

```
# T (Mon, trade date)
tx_T:
  Move(from=w_port,      to=w_cpty_v,    unit=USD, q=5000, ts=Mon, source=tx_T)
  Move(from=w_cpty_v,    to=w_port,      unit=XYZ, q=100,  ts=Mon, source=tx_T)
+ Obligation o_cash(parent=tx_T, side=CASH,     unit=USD, q=5000, dir=DELIVER, status=EXECUTED, sd=Wed)
+ Obligation o_sec (parent=tx_T, side=SECURITY, unit=XYZ, q=100,  dir=RECEIVE, status=EXECUTED, sd=Wed)

# T+1 (Tue, no events). Mark price feeds in: P_Tue(XYZ) = 52.
# (no moves; no transactions)

# T+2⁻ (Wed morning, instruction sent). Status only.
o_cash.status = INSTRUCTED
o_sec.status  = INSTRUCTED

# T+2⁺ (Wed afternoon, sese.025 confirms DvP success)
tx_settle:
  Move(from=w_csd_cash_v, to=w_cpty_v,    unit=USD, q=5000, ts=Wed, source=tx_settle, parent=tx_T)
  Move(from=w_cpty_v,     to=w_csd_sec_v, unit=XYZ, q=100,  ts=Wed, source=tx_settle, parent=tx_T)
o_cash.status = SETTLED
o_sec.status  = SETTLED
```

### 5.3 Verification

**Conservation (every move, every step).** All four moves are `src -= q; dst += q`. Sum is 0 by construction. ✓

**Economic exposure at T.** The instant `tx_T` commits, `w_port(XYZ) = 100`. Mark-to-market value = `100 × P_T(XYZ) = 5000`. Total portfolio value = `w_port(USD) + 100 × P = 95000 + 5000 = 100000`, unchanged from before the trade. ✓ (No PnL at the moment of execution; only via mark-to-market.)

**PnL at T+1 close.**
```
V(T+1) = w_port(USD)·1 + w_port(XYZ)·P_Tue
       = 95000 + 100·52 = 100200
PnL    = V(T+1) − V(T_pre) = 100200 − 100000 = +200   ✓
```
*No cash has moved from our nostro.* `w_csd_cash_v(USD) = 0` on Tue close. The receivable is +5000 USD owed *to the broker*, but that is not a position in our nostro — it is a contractual obligation. The PnL comes entirely from the change in `P` × `w_port(XYZ)`.

**PnL at T+2 close.** Same. The `tx_settle` transaction moved nothing in `w_port`, so V is unchanged from just before `tx_settle` (modulo the Wed close price). The settlement event is *not* a PnL event. ✓

**Recon.** At every checkpoint:
```
T pre:     w_port(XYZ) = 0;    w_csd_sec_v(XYZ) = 0;   inflight(XYZ) = 0     ✓
T post:    w_port(XYZ) = 100;  w_csd_sec_v(XYZ) = 0;   inflight(XYZ) = 100   ✓ (100 = 0 + 100)
T+1:       same                                                                ✓
T+2 post:  w_port(XYZ) = 100;  w_csd_sec_v(XYZ) = 100; inflight(XYZ) = 0     ✓
```

### 5.4 What the three readers see

- **New engineer:** "Two virtual wallets per leg, one obligation row per leg per trade, one extra transaction at T+2⁺ that moves between virtuals only. Real wallet is touched once at T. I can build that on Monday."
- **Auditor:** "Each Obligation row has a `parent_tx_id`, an `external_msg_ids[]`, and a status. I can trace any open balance to the trade that created it and to the wire that closed it. Reconciliation identity is one line of code."
- **Risk manager at T+1:** "I read three numbers: `w_port(XYZ) = 100` (my position, drives PnL), `w_cpty_v(XYZ) = −100` (my receivable from broker), `w_csd_sec_v(XYZ) = 0` (depot is not yet credited). All three are quantities, all three are wallet balances, all three reconcile."

---

## 6. State representation

Putting the proposal in the StatesHome 3-map vocabulary. Nothing new is needed at the *map* level; the existing maps absorb everything.

### 6.1 Where each fact lives

| Fact | Home | Justification |
|------|------|---------------|
| Standard settlement cycle for an instrument (T+2 / T+1 / T+0) | `ProductTerms[u].settlement_cycle` | Immutable per ISIN; versioned. |
| Per-counterparty SSI | not in ledger — settlement layer (§11.2). | Not state; not our problem. |
| Per-trade open obligation (q, sd, status, filled, penalty) | `L_15.Obligation` rows tagged by `parent_tx_id` | FSM is exactly `Pending → Discharged \| Compensated \| Defaulted`; dropdown populated from `EXECUTED, INSTRUCTED, SETTLED, FAILED, PARTIAL`. |
| Counterparty receivable/payable balance | `w_cpty_v(u)` (virtual wallet balance) | Quantity, must be in a wallet. |
| Depot balance | `w_csd_sec_v(u)`, `w_csd_cash_v(ccy)` | Quantity, must be in a wallet. |
| Settlement status of trade | move metadata + Obligation FSM | §11.7 says no moves on confirmation; status is metadata. |

The data v1.0 leaf taxonomy already covers this: `L_13` (MoveStream) for the moves, `L_15` (Obligation) for the per-trade obligation rows, `L_11` (ExternalConfirmation) for the wire references that close obligations. We do not need a 20th leaf.

### 6.2 The `t_economic` vs `t_settle` axis

Each Obligation row — and the parent transaction — carries two timestamps:
- `t_economic = T` (trade execution; when economic exposure begins).
- `t_settle = T+2` (intended; when the wire moves).

These are two distinct columns on the bitemporal axis (data v1.0 §2.2): `t_economic` is *valid time* (when the economic fact became true in the world), `t_settle` is *operational time* (when custody catches up). They are independent. PnL queries read `t_economic`; nostro reconciliation queries read `t_settle`. No state is duplicated; no view is special.

---

## 7. Invariants

### Mandatory: economic exposure at T

**I-ds-1 (Trade-date economic exposure).** For every committed `SETTLEMENT` transaction `tx` with `tx.timestamp = T`, the real-wallet effects of `tx` are visible from `T` onward. Concretely: for any time $t \geq T$ and any real wallet $w$, the balance $w(u, t)$ includes all moves of `tx` regardless of `settlement_status`.

> *In English:* PnL does not wait for the wire.

This is a property of the existing v10.3 framework (§2.6, §11.4). I am not adding it; I am *naming* it so it can be tested.

### Conservation across the obligation lifecycle

**I-ds-2 (Per-move conservation, across virtual-to-virtual transitions).** For every move `m` (including moves inside `tx_settle`), $\Delta_{\text{src}}(u) + \Delta_{\text{dst}}(u) = 0$. (Inherited from §2.4.)

### Wallet ↔ obligation cross-check

**I-ds-3 (Aggregate ↔ per-trade reconciliation).** For every (counterparty `c`, unit `u`):
$$
w^{\mathrm{cpty},c}_v(u) \;=\; \sum_{o \in \mathrm{open\_obligations}(c, u)} \mathrm{signed}(o)
$$
where $\mathrm{signed}(o) = +q$ if `o.direction = DELIVER` (we owe) and $-q$ if `o.direction = RECEIVE` (we are owed), summed over all obligations not yet `SETTLED` or `FAILED`. This is a property test — fails if either side gets out of sync.

### Inflight reconciliation

**I-ds-4 (Inflight identity).** For every (real wallet `w`, unit `u`):
$$
w(u) = w^{\mathrm{csd}}_v(u) + \mathrm{inflight}(w, u)
$$
Daily property test (data v1.0 reconciliation pair on `L_6`). This is exactly the §13 formula instantiated for cash-equity.

### Status monotonicity

**I-ds-5 (Status FSM is monotone forward unless explicitly reversed).** `EXECUTED → INSTRUCTED → SETTLED` is one-way; `INSTRUCTED → FAILED` is allowed; `FAILED → INSTRUCTED` is allowed (re-instruction); `SETTLED → *` is forbidden except by an explicit `CORRECTION` transaction. Inherited from §11.7.

### CSDR penalty composability

**I-ds-6 (CSDR accrual is a function of the obligation row alone).** `csdr_penalty_accrued(o, t)` is computed from `(o.status, o.settlement_date, o.filled_quantity, t)` by a pure function defined in `ProductTerms[u].csdr_regime`. No global state. (CSDR rates and product treatment are set per ISIN in `ProductTerms`, not per trade.)

---

## 8. Reconciliation — lead-lag by design

The architecture has **three points of reconciliation**, each at its natural lag:

| Pair | Lag | Tolerance | Source |
|------|----:|-----------|--------|
| `w_cpty_v` ↔ counterparty's confirmation | T (intraday) | exact | inbound `confirmation` (FpML/CDM) |
| `w_csd_sec_v` ↔ custodian depot statement | T+2 morning | exact | inbound `sese.025` / depot file |
| `w_csd_cash_v` ↔ nostro statement | T+2 day-of | exact | inbound `camt.053` / `camt.054` |

These three are *independent* and *staggered*. The lag is not a bug; it is the design. Trying to "force" the depot to match `w_port` at T is the conventional mistake (it is mathematically impossible — the wire has not moved). What we force instead is the *identity* I-ds-4. The identity is exact; the lag is in the underlying observations.

**Break taxonomy** (mapping to v10.3 §10.3 reconciliation failure types):
- `cpty_v ≠ confirmation`: trade booking error (front-office).
- `csd_sec_v ≠ depot`: depot break. Could be a missed/duplicate sese.025; a corp-action timing offset; a real fail.
- `inflight ≠ Σ open obligations`: cross-layer break — wallet drifted from obligation rows. Almost always a code bug; high severity.
- `T+2 + grace` and obligation still `INSTRUCTED`: CSDR fail. Trigger `failure handler` (§9 below).

Every break is a `BreakRegister` (`L_18`) entry. `wf-position-break` workflow already covers the lifecycle.

---

## 9. Failure modes per case

I now sweep through the floor cases and verify each is expressible. Each subsection is short — *only the cases that bend the model are spelled out at length*.

### 9.1 Standard buy T+2 (already done in §4–5)
Floor case. Move sequence in §4. Conservation, PnL, recon, status all verified. No additional machinery.

### 9.2 Standard sell T+2
Mirror. The seller's `w_port(XYZ)` decrements at T (real position drops); the receivable is +cash, the payable is −shares. Same four moves with sign flipped. The interesting point: the sell *removes the seller's economic exposure at T*. PnL is realised at T (= sale price − weighted-avg cost), not at T+2. The cost basis logic lives on the *sell* leg of the smart contract, not on settlement.

### 9.3 T+1 cycle
Same mechanism, `settlement_date = T+1` written into `ProductTerms[u].settlement_cycle` and into the Obligation row. The intermediate T+1⁻ checkpoint collapses; everything else is identical. **Degeneration test: passes.**

### 9.4 T+0 (same-day) and DvP atomicity
For T+0 / RvP at a single CSD, `tx_T` and `tx_settle` may collapse into a single transaction. The smart contract emits a 4-move transaction (cash leg between us and CSD-cash, security leg between us and CSD-sec) and bypasses the counterparty mirror entirely. The Obligation rows are created with `status = SETTLED` immediately. Conservation is per-move so this is uneventful. **Degeneration test: passes — and it is identical to the v10.3 §2.5 example.**

DvP atomicity at the *ledger* level is the transaction primitive (§11.5 ¶ Ledger-level DvP). DvP atomicity at the *real-world* level depends on the CSD. Our model does not *guarantee* the latter — but it represents a real-world DvP failure correctly: the security leg would arrive but not the cash leg, producing two Obligations in different statuses (`SETTLED` vs `FAILED`). The recon identity I-ds-4 detects the mismatch automatically.

### 9.5 Fail (CSDR)
At T+2 + close, no `sese.025` arrives. Status transitions:
```
o_sec.status:   INSTRUCTED → FAILED
o_cash.status:  INSTRUCTED → FAILED
```
**No moves are generated.** The economic position is unchanged. The receivable balance `w_cpty_v(XYZ) = −100` remains. CSDR penalty accrues per `ProductTerms[u].csdr_regime` daily, posted as a tiny cash move from `w_cpty_v` to `w_port` (or as a CSD-driven debit, depending on the regime — point is, it is just another move).

If the trade is later settled (buy-in or partial), a *new* `tx_settle_partial` transaction posts a partial move from `w_cpty_v` to `w_csd_sec_v`, and `o.filled_quantity` increments. The unfilled remainder stays in `w_cpty_v` until further settlement or cancellation.

If cancelled, a `CORRECTION` transaction reverses `tx_T` (§11.3 last paragraph). This is the only path that affects `w_port` after T.

### 9.6 Partial fill
Same as fail but with `filled_quantity > 0`. The settlement transaction is *split* into one move per partial fill:
```
tx_settle_partial:
  Move(from=w_csd_cash_v, to=w_cpty_v,    unit=USD, q=2500)   # half cash
  Move(from=w_cpty_v,     to=w_csd_sec_v, unit=XYZ, q=50)     # half shares
```
The Obligation row goes to `status = PARTIAL` with `filled_quantity = 50`. Recon identity I-ds-4 still holds: `w_port = w_csd_sec_v + inflight` ⇒ `100 = 50 + 50` ✓.

The DvP property *per partial* must still hold: each partial settlement must move both legs in the same proportion (or in separate transactions per side, with the matching ratio). This is a property of the CSD regime, not the ledger.

### 9.7 Reconciliation (sese.025 handling)
The settlement-layer adapter receives a `sese.025`, looks up the obligation by `external_msg_ids[]` ↔ `EndToEndId`, and either commits `tx_settle` (if no break) or files a `BreakRegister` entry (if mismatch). All ledger writes are normal moves through the executor.

### 9.8 Short — composition with §13
A short sale (Bob borrows 1000 NVDA from Alice, sells 500 to Carol on T):
- Borrow at T_borrow: Bob's `borr += 1000`, Alice's `onloan += 1000`. (§13.7.1.) Conservation via per-relationship virtual wallet.
- Sell at T to Carol: standard buy-side mechanism with **Carol** as the cpty mirror. Bob's `own −= 500`, Carol's `own += 500`. Two virtual wallets (`w_carol_v`, `w_csd_sec_v`) on Bob's side.
- At T+2: virtual-to-virtual settle (`w_carol_v(NVDA) → w_csd_sec_v(NVDA)`).

Bob's avail at T post-trade: `own − onloan + borr = −500 − 0 + 1000 = 500`. Bob's `w_csd_sec_v(NVDA)` at T = 0; at T+2⁺ = −500 (he physically delivered shares from the pool at T+2). The receivable from Carol on cash is in `w_carol_v(USD) = +(500·P)` until T+2.

The two settlements (Alice→Bob borrow, Bob→Carol short) are independent. Each has its own Obligation rows. Each runs its own status FSM. **Degeneration: yes — every leg is a standard equity DvP except `own` may go negative; the borrow virtual wallet handles the SBL contra-entry exactly as in §13.4.**

### 9.9 Recall
Lender recalls. State-only event (per §13.5 state machine, `recall: ACTIVE → RECALLED, moves = None`). Sets a deadline obligation (`L_15`). At `recall_settlement_date`, a `partial_return` or `full_return` event generates the standard return transaction (§13.5.2). This sits *on top of* deferred settlement: the return itself is T+2 (or whatever the regime says), so its Obligation rows go through `EXECUTED → INSTRUCTED → SETTLED` exactly like a buy.

The recall introduces a *second* settlement window (return) with its own T+2 cycle. The ledger has no problem with multiple concurrent open settlements per (cpty, unit); each is its own Obligation row.

### 9.10 Corporate action (T-straddling)
Worst case: ex-date falls between T and T+2. Per §6.3, the entitlement is determined by record date, which is typically several business days *after* ex-date. So the question is: does our open buy have entitlement?

Two regimes:
- **Cum-trade** (trade pre-ex, settle post-ex): we are entitled. The CA contract emits the entitlement move directly to `w_port` on payment date — *not* to `w_csd_sec_v`, because the corporate action processor's source data is the trade record, not the depot statement. No special-casing.
- **Ex-trade** (trade on/after ex): we are not entitled. The CA emits no move for our trade.
- **Claim case** (depot does not show us in time but we are entitled): a *market claim* is owed by the counterparty. Recorded as a separate Obligation row (`type = MARKET_CLAIM`) tagged to the original trade. Resolved by an inbound cash move from `w_cpty_v` to `w_port` on the claim date.

The corporate action machinery already handles this in v10.3 §6.3 (record date is the entitlement snapshot). My only addition: market claims are first-class Obligations, not flags. *This is the right design because §13's `inflight` recon formula needs them as quantities to be counted.*

### 9.11 Cross-currency / Herstatt
Two virtual wallets per leg becomes two virtual wallets *per currency leg*. A USD-funded buy of EUR-XYZ has:
```
w_cpty_v_USD     -- counterparty cash leg
w_cpty_v_EUR     -- counterparty security leg (and any EUR cash flow)
w_csd_cash_USD   -- USD nostro
w_csd_sec_v      -- EUR depot
```
The cash leg settles in NY (T+2 NY close); the security leg settles in EU (T+2 EU close, hours earlier). Each leg has its own Obligation row, status, settlement timestamp. Herstatt = the brief window where one leg has settled and the other has not. **The model represents this as two `tx_settle` transactions, one per leg, fired by independent confirmations.** Between them, `w_cpty_v_EUR(XYZ) = 0` but `w_cpty_v_USD(USD) = +5000` is still open. The risk manager queries this directly. No new machinery.

This is what §2.6 ¶ "Settlement timing and Herstatt risk" already gestures at — I am making it concrete: per-leg Obligation rows, per-leg `tx_settle` transactions, status fields per leg.

---

## 10. CDM cross-walk

Following §12 and data v1.0 §3 leaf cross-walks:

| Concept | CDM | Status |
|---------|-----|--------|
| `tx_T` (trade) | `BusinessEvent.intent = ContractFormation` + `Transfer`s | direct |
| `tx_settle` (settlement) | `Transfer`s with `transferStatus = settled` and `meta.externalKey = sese.025 EndToEndId` | direct |
| Obligation row | no direct CDM type — Ledger-native (`L_15`). | missing in CDM |
| Status FSM (`EXECUTED → INSTRUCTED → SETTLED \| FAILED \| PARTIAL`) | maps to CDM `TransferStatus` enum + `Transfer.transferState` | partial |
| Counterparty mirror balance | derivable from CDM `Account` + `Position` aggregations | partial |
| CSD depot | not in CDM — settlement layer concern (sese.* messages) | out of scope |
| Market claim | no CDM type; ISLA / corp-action industry standard | missing |

The `Obligation` row is the same `L_15` carrier already used for CSA margin calls, locate obligations, reset deadlines, etc. It is not new infrastructure; it is the existing obligation carrier in a cash-equity skin. Reuse is the point.

The CDM gap (no first-class Obligation type) is the same gap noted in data v1.0 `L_15` ("CDM cross-walk: Missing (Ledger-internal)"). Settlement state lives at the `Transfer.transferState` level in CDM but doesn't carry the per-trade FSM the framework needs for CSDR / partial / market claims; we extend internally and project at the boundary.

---

## 11. The three clarity tests

I close with the three tests Karpathy asks for explicitly.

**1. "Can a new engineer build from this on Monday?"**
Yes. The build list is:
- Add two virtual wallet types: `cpty_v` (keyed by LEI) and `csd_v` (keyed by BIC + side).
- Add one `Obligation` data structure with the fields in §3.2, FSM `EXECUTED → INSTRUCTED → SETTLED | FAILED | PARTIAL`, persisted in the existing `L_15` table.
- Modify the equity smart contract: `tx_T` now writes to `w_cpty_v` (not directly to `w_csd_sec_v`). Add an Obligation row per leg.
- Add a `settlement_confirmation_handler`: on inbound `sese.025` (or equivalent), look up the Obligation by `EndToEndId`, emit `tx_settle` (virtual-to-virtual), advance status.
- Add a `csdr_handler`: on T+2 + grace with status still `INSTRUCTED`, advance to `FAILED` and start CSDR penalty accrual.
- Wire two property tests: I-ds-3 (wallet ↔ obligation aggregation) and I-ds-4 (inflight identity).

About 500 lines of code. No new map. No new conservation rule.

**2. "Can an auditor check it?"**
Yes. Every open balance has a single source: a `parent_tx_id`. Every status change has a single source: an inbound `external_msg_id`. The reconciliation identity I-ds-4 is one line of code; auditors run it daily. Break workflow already exists (`L_18`, `wf-position-break`).

**3. "Can a risk manager say what is true at T+1?"**
Yes. Three numbers:
- `w_port(u)` — the position, drives PnL.
- `w_cpty_v(u)` (per LEI) — open receivable/payable, drives counterparty risk.
- `w_csd_v(u)` — depot balance, drives operational risk and recon.

All three are wallet balances. All three are queries. All three are quantities (not flags, not statuses). The risk manager does not need to read transaction logs to answer the question.

---

## 12. The one-paragraph summary

> The open settlement obligation lives as a *quantity in a counterparty virtual wallet*, not as a flag on a transaction. Trade-date accounting is preserved exactly: the real wallet is touched once at T, never again. Settlement at T+2 is an internal virtual-to-virtual rotation that moves the receivable from the counterparty mirror into the depot mirror — invisible to PnL, fully audited via `sese.025` references on the moves. Per-trade granularity (CSDR, partial, market claim) is carried by a per-leg `L_15` Obligation row, FSM `EXECUTED → INSTRUCTED → SETTLED \| FAILED \| PARTIAL`. Conservation holds per-move; the recon identity `own = depot + inflight` holds at every checkpoint. The mechanism degenerates: T+0 collapses `tx_T` and `tx_settle` into one transaction; non-cleared OTC has no `csd_v` wallet; SBL adds the `borr` coordinate but uses the same Obligation primitive for return windows; cross-currency uses one Obligation row per currency leg, naturally representing Herstatt as a transient asymmetric state. Build it on Monday with two new wallet types, one Obligation row per leg, and one new settlement-confirmation handler. The model survives every floor case in the spec without a new conservation law.
