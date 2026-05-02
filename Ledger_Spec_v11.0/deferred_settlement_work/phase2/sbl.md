# Phase 2 — SBL Composition with Deferred Settlement

**Author:** Margaret Chen (sbl-specialist), Settlement Team
**Date:** 2026-04-30
**Document role:** the SBL composition section of `deferredSettlement.tex`. Argues, against my Phase 1 position, that the mainstream "virtual wallets + L_15 Obligation row + transaction-level lifecycle FSM" design is sufficient *for SBL composition* once three specific extensions are pinned. Migrates my Phase 1 composition arguments to the mainstream representation and walks every coordinate of the §13 six-tuple through the short-sale, recall, buy-in, and Herstatt cases.

---

## 0. Final position — I concede the 7th coordinate

I wrote in Phase 1 that the GPM should be extended from six coordinates to seven by adding a stored, signed `inflight` coordinate. After reading all 19 sister proposals (and re-reading my own argument with adversarial eyes), I concede.

**The mainstream design — virtual wallets representing settlement-pending positions, plus an `Obligation` row in $L_{15}$ keyed to the trade transaction, plus a per-transaction `lifecycle_stage` FSM `EXECUTED → INSTRUCTED → SETTLED | FAILED | PARTIALLY_SETTLED | CANCELLED | BOUGHT_IN` — is sufficient.**

I am persuaded by three arguments I did not weigh correctly in Phase 1:

1. **StatesHome 3-map discipline.** Adding a 7th coordinate creates a new field on `PositionState[w, u]` that must be mutated by both the trade handler and the settlement-confirmation handler — but those two handlers have disjoint capability tags under C11. Either I introduce a new capability (which itself needs C11 audit) or I let the settlement handler write to a position field, which is exactly the bug Jane Street's I-1 invariant is designed to forbid: *"the position function is independent of the settlement-status FSM."* My 7th coordinate would have created the very capability path that has caused real disasters at real firms.

2. **Conservation Lifting (Cartan, Theorem 5.1) and Single-Coordinate Move Principle.** If `inflight` is a stored coordinate, then a "move" that books an in-flight obligation has to write *two* coordinates on the same wallet (`own` and `inflight`) atomically — violating SCMP (v10.3 §13.2). My §1.2 argument that "instruction issuance modifies `inflight` alone" only works at the moment of issuance, not at the *trade* moment, where economic recognition writes `own` and the in-flight obligation books simultaneously. Cartan's framing — make the obligation a unit, not a coordinate — preserves SCMP because each unit's coordinate moves independently.

3. **Granularity is not lost in the mainstream design.** My §1.3 argument was that a virtual-wallet projection collapses to a net number. Wrong. The L_15 Obligation row is *per-instruction*, not per-(entity, unit). Cartan's $u^{\circ}(\tau)$ is per-trade. The inflight virtual wallet's contents are decomposable by `(obligation_id, leg)` because the move stream records the parent `tx_id` on every settlement move. The SQL aggregate `SELECT SUM(quantity) FROM moves WHERE wallet = w_inflight AND obligation_id = ?` recovers the per-instruction grain at no extra cost.

The remaining concern from Phase 1 — that the SBL composition cannot distinguish "lent and on-loan" from "lent and not yet settled" in a single read — is addressed in §2 below by showing that the GPM coordinates (`onloan`, `borr`) are themselves **post-settlement** counts, and the in-flight versions are tracked through *separate* obligation units, not by a 7th coordinate.

What I retain from Phase 1, and the team must accept:

- **The economic-exposure-at-T invariant is mandatory** (this is consensus). I labelled it P24; Cartan labels it P24; ISDA labels it E1; Jane Street labels it I-1; testcommittee labels it the load-bearing case. Same invariant. Adopt it.
- **Settlement state lives on the obligation, not on the position** (consensus, articulated most sharply by Jane Street §1.3 and Cartan §3.3).
- **Recall, locate, manufactured dividend, Herstatt, and CSDR fail compose without bespoke logic** (this is what §3 of this document proves in the mainstream representation).

---

## 1. Composition rules — the GPM six-tuple and the deferred-settlement state are orthogonal

### 1.1 The orthogonality claim

The GPM six-tuple of v10.3 §13 — $(\mathrm{own}, \mathrm{onloan}, \mathrm{borr}, \mathrm{coll\_post}, \mathrm{coll\_recv}, \mathrm{coll\_rehyp})$ — and the deferred-settlement state — `(virtual_wallet_balances, obligation_status, lifecycle_stage)` — are **structurally orthogonal**. A position's six-coordinate vector and the settlement state of any open instruction touching that position are independent dimensions. The only place they interact is at the *boundary*: when an instruction transitions to `SETTLED`, certain virtual-wallet balances zero out, but **no GPM coordinate on a real wallet moves at that boundary** (this is the v10.3 §13.7 "no moves at settlement" rule, preserved unchanged).

This orthogonality is what lets the same FSM run for cash-equity sales, SBL loan settlement, SBL collateral movements, and SBL recall returns. The smart contract dispatches on instruction type; the FSM is uniform.

### 1.2 Which coordinate does a deferred sale draw from?

A deferred cash-equity *sale* of $q$ shares of unit $u$ by entity $e$ at time $T$, settling $T+2$, draws from `own`:

$$
\Delta \mathrm{own}_e(u) = -q \quad \text{at } T.
$$

If $\mathrm{own}_e(u)$ before the trade is $\geq q$ (the seller is long), this is a clean reduction. If $\mathrm{own}_e(u) < q$ (the seller is short or partially short), `own` goes negative — **and this is correct.** The GPM allows negative `own` (v10.3 §13 explicitly addresses short selling via negative `own`). The locate Unit and the `avail` projection $\mathrm{avail} = \mathrm{own} - \mathrm{onloan} + \mathrm{borr}$ enforce the SSR/Reg-SHO covered-short discipline at the smart-contract guard level, *before* the move is admitted to the executor.

The seller's *delivery obligation* — the duty to actually deliver the shares to the CSD by $T+2$ — does **not** live on the GPM at all. It lives in the L_15 obligation row and in the inflight virtual wallet. In wallet form:

$$
\text{w\_inflight\_sells}(u, e) \mathrel{+}= q \quad \text{(virtual wallet, contra to seller's nostro)}
$$

The seller's `own` reflects economic ownership (which is now $-q$ relative to pre-trade state). The seller's *custody obligation* is materialised in the inflight virtual wallet, retired by the discharge move at $T+2^+$. **`own` and inflight are different things and live in different storage.** This was my Phase 1 confusion: I wanted them in the same vector to get a "single read." The single read is recovered at the projection layer (see §1.4) without the storage cost.

### 1.3 Where does the seller of borrowed shares' settlement obligation live?

This is the canonical short-sale composition question and the place where I think my Phase 1 argument was *most* clarifying. Let me migrate it to the mainstream design.

A short seller $C$ at time $T$ executes:

1. **Locate** at $T-\epsilon$: a Unit registered against lender $B$ with TTL = end of $T$. No moves on either party's GPM. This is v10.3 §13.13 unchanged.
2. **Sale to buyer $D$** at $T$: a SETTLEMENT-type transaction with two legs. $C$'s `own($u$)` decrements by $q$; $D$'s `own($u$)` increments by $q$ (via $D$'s broker virtual wallet). Cash legs symmetric. An obligation $u^{\circ}_{\mathrm{sale}}$ is created with `lifecycle_stage = EXECUTED`, `intended_settlement = T+2`.
3. **Borrow $\ell$ from $B$** at $T+\epsilon$: a separate SETTLEMENT-type transaction. This is the SBL initiation per v10.3 §13.10. Settlement of the loan is typically T+0 or T+1 FOP. A *separate* obligation $u^{\circ}_{\mathrm{borrow}}$ is created with its own `lifecycle_stage` FSM.
4. **Loan settles** (say at $T+1$, FOP): $u^{\circ}_{\mathrm{borrow}}$ transitions to `SETTLED`. *At this moment*, the GPM coordinates move:
   - $B$'s $\mathrm{onloan}$ increments by $q$ (lender's lent quantity); $B$'s `own` is unchanged (title-transfer regimes shift this; under GMSLA 2010 SI v6.0 with title transfer, the lender's `own` actually drops and `onloan` rises — but this is a pre-existing v10.3 §13 question, not a deferred-settlement question).
   - $C$'s $\mathrm{borr}$ increments by $q$.
   - Collateral moves via the appropriate `coll_*` coordinates.
5. **Sale settles** at $T+2^+$: $u^{\circ}_{\mathrm{sale}}$ transitions to `SETTLED`. The inflight virtual wallets for the sale zero out. **No GPM coordinates on $C$ move at this step** — $C$'s `own` was $-q$ and stays $-q$; $C$'s `borr` is $+q$ from the loan settlement at $T+1$; $C$'s `avail = own - onloan + borr = -q - 0 + q = 0`, exactly the post-delivery state.

The settlement obligation for the *short sale* lives in $u^{\circ}_{\mathrm{sale}}$, distinct from the settlement obligation for the *borrow*, which lives in $u^{\circ}_{\mathrm{borrow}}$. The two obligations have independent FSMs. They do **not** merge.

This is what I argued in Phase 1 §7.1 and what I still argue. The only change: instead of tracking the open delivery obligation as a 7th coordinate on $C$'s wallet, it is tracked as a Unit (the obligation $u^{\circ}_{\mathrm{sale}}$) with `+1` at $C$'s wallet and `-1` at $D$'s broker virtual wallet, plus an inflight virtual-wallet record. Same information, different storage. **Cartan's universal-property argument (Proposition 2.5) is the proof that no information is lost in this translation.**

### 1.4 The reconciliation identity, restated

My Phase 1 P29 said: $\mathrm{own} + \mathrm{borr} - \mathrm{net\_outgoing\_inflight} = D$ (depot). In the mainstream design this becomes:

$$
\boxed{\;
\mathrm{own}_e(u) + \mathrm{borr}_e(u) - \mathrm{onloan}_e(u) \;-\; \sum_{i \in \mathrm{open}(e,u)} \mathrm{signed\_qty}(i) \;=\; D(e, u)
\;}
$$

where $\mathrm{open}(e,u) = \{i : \mathrm{lifecycle\_stage}(i) \in \{\text{INSTRUCTED}, \text{PARTIALLY\_SETTLED}, \text{FAILED}\}\,, i\text{ touches }(e,u)\}$ and $\mathrm{signed\_qty}(i)$ is positive for a receive obligation, negative for a deliver obligation.

The right-hand sum is a query over the L_15 Obligation table joined to the move stream — exactly the projection my Phase 1 §1.3 argued was operationally insufficient. I was wrong about the cost. At any reasonable index design (B-tree on `(counterparty_lei, settlement_status)`, hash on `(wallet, unit, settlement_status)`), this query is sub-second on $10^7$-row obligation tables. ISDA's §4 and Jane Street's §4.3 both make this case explicitly, with concrete benchmarks. I retract my §1.3 cost argument.

---

## 2. Short sale lifecycle in full

I walk every state, every move, every coordinate, with conservation explicit. Setup: short seller $C$, lender $B$, buyer $D$. Quantity $q = 500$ NVDA. Sale price \$100. NVDA at $T+1$ moves to \$102. Collateral on the loan: cash \$50,000, rebate rate 25 bps. T+2 cash equity settlement; T+1 (or earlier, FOP) loan settlement.

### 2.1 Time T-1, 14:00 — Locate confirmed

No moves. Locate Unit $\mathrm{loc}_1$ registered: `(lender=B, borrower=C, isin=NVDA, qty=500, ttl=end-of-T)`. P14 (Locate Before Short, v10.3 §13) consumes this Unit's reservation against $B$'s `available_to_lend` projection.

**Position vectors (NVDA only):**
- $\vec{w}_C = (0, 0, 0, 0, 0, 0)$
- $\vec{w}_B = (1000, 0, 0, 0, 0, 0)$ (lender holds 1000 NVDA available)
- $\vec{w}_D = (0, 0, 0, 0, 0, 0)$

### 2.2 Time T, 09:30 — Short sale to D, T+2 settlement

**Transaction $\tau_{\mathrm{sale}}$ (type=SETTLEMENT):**

```
Move 1: w_D_brkrvirt -> w_C, unit=NVDA, qty=500    (deliver obligation booked: C owes shares)
Move 2: w_C -> w_D, unit=USD, qty=50000            (C receives cash from D)
```

Wait — moves are signed by the deliverer, not the receiver. Restating in the v10.3 form:

```
tau_sale = Transaction(type=SETTLEMENT, settlement_date=T+2):
    Move(from=w_C, to=w_D_brkrvirt, unit=NVDA, qty=500)     -- C's own decrements 500
    Move(from=w_D_brkrvirt, to=w_C, unit=USD, qty=50000)    -- C's own increments 50000

Side-effects (atomic):
    Obligation u_sale created:
        obligation_id  = tau_sale.id
        leg_securities = (NVDA, 500, deliver_party=C, receive_party=w_D_brkrvirt)
        leg_cash       = (USD, 50000, payer=w_D_brkrvirt, receiver=C)
        intended_settlement = T+2
        lifecycle_stage = EXECUTED
        discharge_predicate = ByMatch(sese.025 against tau_sale.id)

    inflight virtual wallet entries (per ISDA §1.2 inflight pattern):
        w_inflight_buys (NVDA)  +=  500  -- C's pending delivery (negative for C)
        w_inflight_sells (USD)  -=  50000

(Sign convention: w_inflight_buys carries the count of incoming receives;
 a negative entry at the seller's index tracks an outgoing deliver. ISDA §4
 closed form holds.)
```

**Position vectors after $\tau_{\mathrm{sale}}$:**
- $\vec{w}_C = (-500, 0, 0, 0, 0, 0)$ — own goes negative (covered short, locate present)
- $\vec{w}_B$ unchanged — locate is no-move
- $\vec{w}_D$ via broker virtual = $(+500, 0, 0, 0, 0, 0)$

**Conservation per unit:**
- NVDA: $(-500) + (+500) = 0$ across real+virtual wallets. ✓
- USD: $(+50000) + (-50000) = 0$. ✓

**$\mathrm{avail}$ projection:**
- $\mathrm{avail}(C, \text{NVDA}) = -500 - 0 + 0 = -500$. C has negative available — locate-covered, not naked, but uncoveredby borrow-yet.
- $\mathrm{avail}(B, \text{NVDA}) = 1000 - 0 + 0 = 1000$ (unchanged; locate consumes `available_to_lend` projection but not `avail`).

### 2.3 Time T, 09:31 — Borrow $\ell$ negotiated with B

Loan negotiation is no-move (v10.3 §13.10 SBL Loan Initiation: "negotiation precedes the loan settlement transaction"). A SETTLEMENT-type transaction is created representing the loan but its `lifecycle_stage = EXECUTED` and the actual move-emission happens at the loan's intended settlement.

Wait — the v10.3 §13 SBL Loan Initiation text is explicit: the loan transaction *is* the settlement instruction. There are two readings:

- **Reading A** (loan is one transaction with intended-settlement metadata): the GPM coordinates `onloan` and `borr` flip at the *loan's* T+0/T+1 moment, not at the loan's T moment. This is the deferred-settlement reading and the one consistent with the rest of this section.
- **Reading B** (loan is two transactions — economic and settlement): same as cash-equity, with economic recognition at $T_{\ell}$ and custody movement at $T_{\ell}+1$.

The Settlement Team should adopt **Reading A** for SBL: the loan's economic recognition *is* the settlement, because the loan only exists once both parties have moved their assets. Negotiation is pre-economic. This is consistent with v10.3 §13's existing prose.

Under Reading A, at $T$ 09:31 nothing happens on the GPM. A pending-loan record is registered (this is the v10.3 §13.7 "PENDING loan" state).

### 2.4 Time T+1 — Loan $\ell$ settles FOP

**Transaction $\tau_{\ell}$ (type=SETTLEMENT, securities-leg only — collateral is a separate transaction):**

```
tau_loan = Transaction(type=SETTLEMENT, settlement_date=T+1):
    Move(from=w_B,   coordinate=onloan, unit=NVDA, qty=+500)   -- single-coord move per SCMP
    Move(from=w_B,   coordinate=own,    unit=NVDA, qty=-500)   -- (or unchanged if title-transfer)
    Move(from=w_C,   coordinate=borr,   unit=NVDA, qty=+500)

Wait — single-coordinate-move discipline (v10.3 §13.2) is per-move, not per-coordinate-per-wallet. Each move modifies one coordinate of one unit on the *destination* wallet (and the matching coordinate on the source). Restating:

    Move 1: lender's available NVDA decrements 500 (own -= 500)
    Move 2: lender's onloan NVDA increments 500
    Move 3: borrower's borr NVDA increments 500
```

This is three moves to handle one loan-settlement event because each touches a different coordinate. Conservation across NVDA: $-500 + 500 + 500 = +500$. **Wait — that doesn't conserve.** The issue is that under title-transfer GMSLA, the lent shares legally move from $B$ to $C$. The conservation law applies to the total count, but the count distribution across `own` and `borr` depends on the legal regime.

The clean reading from v10.3 §13:

- **Title-transfer regime (GMSLA 2010 SI):** Lender's `own` decrements by $q$; lender's `onloan` increments by $q$ (a record-keeping coordinate, not a real-asset coordinate). Borrower's `borr` increments by $q$. The actual NVDA shares move from B's depot to C's depot. Total NVDA across wallets: $\mathrm{own}_B - q + \mathrm{onloan}_B + q + \mathrm{own}_C + \mathrm{borr}_C + q = \mathrm{const} + q$. This breaks conservation unless `onloan` is treated as a *non-conserved* coordinate.

I've found a real issue. The v10.3 §13 GPM treats `onloan` as a tracking coordinate that does NOT participate in the asset-conservation sum; the conservation law sums over `own` only. Let me re-read the v10.3 abstract:

> "Available inventory is a projection computed on read: $\mathrm{avail}(e,u) = \mathrm{own} - \mathrm{onloan} + \mathrm{borr}$."

So `onloan` and `borr` are projection inputs, not conserved coordinates. Conservation is on `own`. Under title-transfer, $B$'s `own` drops by $q$ and $C$'s `own` rises by $q$; conservation holds. `onloan` rises on $B$ and `borr` rises on $C$ as **bookkeeping** entries that drive the `avail` projection. They don't sum to zero.

This is consistent with v10.3 §13 but worth pinning explicitly in the Settlement Team's spec: **the conservation law in the SBL extension applies to `own` (and the cash/collateral coordinates), not to `onloan` or `borr` or `coll_*` per se. The bookkeeping coordinates are scoped per-(entity, unit) and don't aggregate across the system.**

Restated $\tau_{\ell}$:

```
tau_loan = Transaction(type=SETTLEMENT, settlement_date=T+1, regime=GMSLA-2010-SI):
    Move(from=w_B,   to=w_C,   coordinate=own,    unit=NVDA, qty=500)   -- title transfer
    BookkeepingDelta:
        w_B.onloan(NVDA) += 500     -- single-coord delta on B
        w_C.borr(NVDA)   += 500     -- single-coord delta on C
```

Plus the collateral leg (not shown here for brevity; cash collateral 50000 USD posted from C to B, with `coll_post` and `coll_recv` deltas).

The obligation $u^{\circ}_{\ell}$ transitions `EXECUTED → SETTLED`.

**Position vectors after $\tau_{\ell}$:**
- $\vec{w}_C = (0, 0, +500, +50000, 0, 0)$ — `own = -500 + 500 = 0`; `borr = +500`; `coll_post = +50000` (cash posted)
- $\vec{w}_B = (+500, +500, 0, 0, +50000, 0)$ — `own = 1000 - 500 = 500`; `onloan = +500`; `coll_recv = +50000` (cash received as collateral)

Wait — $C$'s `own` was $-500$ at T+0 (post-sale) and $+500$ at T+1 (loan settlement). That's still `own_C = 0` net. $\mathrm{avail}(C) = 0 - 0 + 500 = 500$. C now has 500 NVDA available to deliver to D at T+2. ✓

### 2.5 Time T+2 — Short sale settles to D

$\tau_{\mathrm{discharge\_sale}}$ confirms the original sale:

```
tau_discharge = Transaction(type=LIFECYCLE, status: INSTRUCTED -> SETTLED):
    -- Inflight virtual wallets close out (ISDA §1.2 mechanism)
    Move(from=w_inflight_buys, to=w_D_nostro, coord=own, unit=NVDA, qty=500)
    Move(from=w_C_nostro, to=w_inflight_sells, coord=own, unit=NVDA, qty=500)  
    -- (Cash leg symmetric)
```

But — *the v10.3 §13.7 rule says no real-wallet moves at SETTLED*. The inflight wallets here are virtual, and the moves above are between virtual wallets. C's GPM is unchanged: `own = 0` (the -500 from sale and +500 from loan already netted at trade-time), `borr = +500`, etc.

The position vectors are stable from T+1 onward through the rest of the loan's life.

---

## 3. Recall during the open window

**Scenario.** Lender $A$ has lent 1000 XYZ to borrower $B$ at $t_0$. On $T$, $B$ sells 600 XYZ to buyer $D$, settling $T+2$. On $T+1$, $A$ issues a recall on the loan, with intended return date $T+3$ (assuming $A$ uses the standard 2-business-day notice; the actual minimum is set by IBP-328 — one hour before market cut-off, two business days back).

### 3.1 The state machine through every transition

| Time | $\vec{w}_B$ XYZ (own, onloan, borr) | $u^{\circ}_{\mathrm{sale}}$ stage | recall obligation | inflight contribution from sale |
|---|---|---|---|---|
| $t_0^+$ (loan settled, T<<0) | (0, 0, 1000) | n/a | n/a | 0 |
| $T$ (sale to D) | (-600, 0, 1000) | EXECUTED | n/a | -600 |
| $T+1$ (recall arrives) | (-600, 0, 1000) | EXECUTED | $u^{\circ}_{\mathrm{recall}}$ created, stage=EXECUTED, intended_return=T+3 | -600 |
| $T+2^+$ (sale settles to D) | (-600, 0, 1000) | SETTLED | EXECUTED | 0 |
| $T+3$ (recall return due) | $B$ must deliver 1000 XYZ to $A$. $\mathrm{avail}(B) = -600 - 0 + 1000 = 400$. **Insufficient.** | terminal | EXECUTED → buy-in path | n/a |

### 3.2 Recall vs sale priority — the regulatory expectation

**Does the recall take priority over the deliver to D?**

No. A recall does not preempt an already-instructed sale. The two obligations are independent. The sale to D is a contractual obligation under the equity trade; the recall is a contractual obligation under the GMSLA. Both must be settled, and if $B$'s available position is insufficient to settle both, $B$ must:

1. **Source additional shares** (open-market purchase, alternative borrow, or — under GMSLA 9.3 — buy-in by $A$ at $B$'s expense).
2. **Pay any CSDR penalty** for the leg that fails.
3. **Pay GMSLA buy-in costs** to $A$.

The system represents this through the saga compensation tower (data spec L_15): when the recall obligation's deadline fires and $\mathrm{avail}(B, \text{XYZ}) < 1000$, the workflow generates a `BUY_IN_REQUIRED` event, which spawns a market-buy SETTLEMENT transaction. The buy-in transaction is itself subject to T+2 settlement and has its own obligation row. Recursive composition; same FSM at every level.

**Regulatory expectation.** Under GMSLA 9.3 (and the ISLA Best Practice handbook IBP-328), the lender has the right to recall and to claim costs for non-delivery. Under CSDR, the failing party on the *D-bound sale* is liable for cash penalties (CSDR Article 7, recalibrated by ESMA 2024 RTS, with the 2023 Refit excluding mandatory buy-in for SFTs but **not** for cash equities — which is the relevant regime for the $B \to D$ leg). The recall return is itself an SFT leg and is exempted from CSDR mandatory buy-in (Refit 2023), but **CSDR cash penalties still apply** to FOP transfers per ESMA's clarification, with FOP specifically called out under the Refit's exemptions for "operations that are not considered trading" — verify with ESMA's current technical standards as the boundary is fuzzy.

### 3.3 The state walk through $T+2^+$ to $T+3$

At $T+2^+$, the sale to D settles. C's (sorry — B's, in this scenario) position is:

- $\vec{w}_B$ = (-600, 0, 1000, 0, 0, 0) — `own = -600, onloan = 0, borr = 1000`, no collateral on B's side because B is a borrower, not a lender, in this scenario. Wait — B is the borrower from A; collateral was posted by B to A. So $\vec{w}_B$ should include `coll_post = +50000` (cash collateral). Let me restate:

- $\vec{w}_B$ XYZ = (-600, 0, 1000); $\vec{w}_B$ USD coll = (-50000, 0, 0, +50000, 0, 0) [coll_post is the cash collateral posted to A].
- $\vec{w}_A$ XYZ = (0, 1000, 0); $\vec{w}_A$ USD coll = (-, 0, 0, 0, +50000, 0) [coll_recv is the collateral A holds].

At $T+3$, the recall must settle. The discharge action: $B$ delivers 1000 XYZ to $A$ and $A$ returns $50000 cash collateral. But $B$'s $\mathrm{avail} = -600 + 1000 = 400$. The workflow:

1. $B$ delivers 400 XYZ to $A$ (partial recall return). This is a partial settlement on $u^{\circ}_{\mathrm{recall}}$, not a full discharge. The obligation lifecycle stage moves to PARTIALLY_SETTLED.
2. The 600 XYZ shortfall is escalated. Buy-in invoice is issued by $A$ under GMSLA 9.3.
3. $B$ executes a market buy of 600 XYZ at the current price (potentially much higher than the original loan economics — short squeeze loss). New SETTLEMENT transaction with its own T+2 settlement window.
4. When the buy-in settles, $B$ delivers the additional 600 to $A$, completing $u^{\circ}_{\mathrm{recall}}$.
5. Cost differential charged to $B$.

Throughout this walk, the GPM coordinates evolve as expected. The conservation law on `own` holds because every move is paired. The bookkeeping coordinates (`onloan`, `borr`) are updated only at SETTLED moments. The inflight virtual wallets carry the in-flight states.

---

## 4. Naked short edge cases and CSDR mandatory buy-in (Reg SHO Rule 204 close-out)

### 4.1 Naked short

A *naked* short is a sale at $T$ without an Article 12(1)(c) locate or a T+0 borrow lined up. Under EU SSR Article 12 this is *prohibited*. Under SEC Reg SHO Rule 203, it is also generally prohibited except for bona-fide market-making activity and limited Rule 144A scenarios. The Ledger's role:

- **Pre-trade guard.** The smart contract guarding the SETTLEMENT-type transaction emission for a short sale checks for the locate Unit's existence and validity at time $T$. If absent, the executor **rejects** the transaction. This is C11 capability discipline — the trade doesn't enter the move stream.
- **Post-trade detection.** If a naked short is somehow booked (e.g., via a CORRECTION transaction or a flagged exception), the L_18 BreakRegister picks it up at the T+2 settlement check.

### 4.2 Buy-to-cover triggered by mandatory buy-in

Reg SHO Rule 204 (US): for a fail-to-deliver on a short sale, the broker-dealer must close out by the start of trading on $T+3$ (or $T+5$ for market makers, or $T+35$ for fails on threshold securities).

CSDR Article 7 (EU, Refit 2023): mandatory buy-in *suspended* for cash equities since 2022 but **not abolished** — reinstated as a discretionary regime for specific high-fail securities post-2024 ESMA review. Cash penalty regime is in force unconditionally.

**Ledger representation of the close-out:**

```
At T+3 (Reg SHO close-out deadline):
    Workflow detects: sale obligation u_sale.lifecycle_stage == FAILED, regime=US_REG_SHO

    Generate: tau_buyin = Transaction(type=SETTLEMENT, settlement_date=T+5):
        Move(from=w_market_virt, to=w_C, unit=NVDA, qty=500)
        Move(from=w_C, to=w_market_virt, unit=USD, qty=q*P_T+3)
    
    Side-effects:
        u_sale.lifecycle_stage: FAILED → BOUGHT_IN
        u_buyin = new Obligation, intended_settlement = T+5, lifecycle_stage = EXECUTED
    
At T+5 (buy-in settles):
    u_buyin.lifecycle_stage: INSTRUCTED → SETTLED
    Now C has 500 NVDA available to deliver.
    
    A separate discharge transaction completes the original D-bound delivery:
        Move(from=w_C, to=w_D_brkrvirt, unit=NVDA, qty=500)
        u_sale: BOUGHT_IN → SETTLED (fully discharged via replacement)
```

The PnL impact: $-500 \cdot (P_{T+3} - P_T) - \text{CSDR cash penalty} - \text{Reg SHO penalty if applicable}$. All visible on the move stream; no special accounting.

### 4.3 The regulatory reporting fan-out

A single naked-short-fail event triggers:

- **CSDR**: cash penalty obligation in EUR per ESMA 2017/389 schedule, accruing daily from $T+1$ until SETTLED. (Note: CSDR Refit 2023 excluded "operations that are not considered trading, such as free-of-payment collateral transfers" from cash penalties — but a sale fail is a trading operation, so the exemption does not apply.)
- **Reg SHO** (US): the failing position appears on the FINRA/SEC threshold securities list if certain thresholds are breached. Reportable.
- **SLATE / FINRA Rule 6500** (US, SBL leg): the borrow-to-cover, if it goes through a securities loan, is reportable to SLATE. The cover loan's FINRA Loan ID is distinct from the original borrow's.
- **MiFIR RTS 22** (EU/UK): the original sale is reportable. The buy-in execution is *also* a new MiFIR transaction reportable on $T+3+1$.
- **SFTR** (EU/UK, if borrow leg involves an SBL): the loan settlement is reportable; the recall (if any) generates a MODI; the loan termination at buy-in completion generates an ETRM.

The Ledger surfaces all of these from the same move stream + L_15 obligations + L_17 RegulatorySubmission leaf. Each regime has its own report identity. See §8 below.

---

## 5. Locate at T but borrow only clears T+1 — observable as "long that has never owned"?

Yes, and this is the canonical gotcha that I think the team should pin.

Between $T$ (locate confirmed, sale executed, borrow not yet settled) and $T+1$ (borrow settles), the short seller $C$'s position is:

$$
\vec{w}_C(\text{NVDA}) = (-q, 0, 0, \ldots).
$$

`own_C = -q` (from the sale). `borr_C = 0` (loan has not settled). $\mathrm{avail}(C) = -q$. *C has never owned NVDA*. C has, however, an *enforceable claim against B* (via the locate-converted-to-borrow obligation), which the v10.3 §13 SBL state captures as the pending loan. This "synthetic short" position is observable from the move stream:

```sql
SELECT entity_id, unit_id,
       coordinate('own') as own,
       coordinate('borr') as borr,
       (own - 0 + borr) as avail
FROM positions
WHERE avail < 0
  AND NOT EXISTS (SELECT 1 FROM trade_history WHERE entity = entity_id AND unit = unit_id AND coordinate = 'own' AND qty > 0);
```

Returns: $C$ on NVDA between $T$ 09:30 and $T+1$ (loan settle).

**What is the regulatory expectation?**

- **EU SSR Article 12(1)(c):** the position is legal *if* the locate provides "a reasonable expectation of settlement when due" (Article 12(1)(c)). The fact that $C$ never owned the shares is irrelevant; what matters is that the locate is from a counterparty (lender $B$) with a reasonable means of delivery.
- **ESMA 2022 Final Report (ESMA70-448-10):** the locate must be *recorded* with 5-year retention, including the confirming party's identity. This is an L_2 InstrumentMaster + L_17 RegulatorySubmission obligation in the data layer.
- **SEC Reg SHO Rule 203:** equivalent. The "locate" is a separate concept from the actual borrow; both must exist before delivery is required at settlement.

The Ledger correctly represents the temporary "long that has never owned" state through the negative `own` coordinate and the locate Unit. This is *not* a bug; it is the correct representation of a legal short-sale-with-locate position.

---

## 6. GMSLA/ISLA collateral movement during the window — collateral in transit while loan is in transit

Real scenario (this happens daily in EMEA SBL): a loan $\ell$ negotiated at $T_{\ell}$ with intended settlement $T_{\ell}+1$ FOP. Cash collateral pre-paid at $T_{\ell}$ (overnight, before the loan settles — IBP-177 prepay collateral). Both moves are in flight overnight.

### 6.1 Walk through the prepay scenario

At $T_{\ell}$ 16:00 (cash cut-off in the relevant currency):
- Borrower $C$ instructs cash collateral move: \$50,000 USD from $C$ to $B$.
- Loan $\ell$ is *not yet settled*; the securities have not yet moved.

This creates **a window of one-leg exposure**: $B$ has received cash collateral but has not yet delivered the 500 NVDA. If $B$ defaults overnight, $C$ has a claim against $B$ for the cash, but no securities. Under GMSLA close-out netting, this is resolvable, but operationally the exposure is real.

### 6.2 Ledger representation

Two separate transactions, each with its own obligation:

```
tau_collateral (type=SETTLEMENT, settlement_date=T_l):
    Move(from=w_C, to=w_B, coord=coll_post/coll_recv, unit=USD, qty=50000)
    Side-effect: u_collateral.lifecycle_stage = INSTRUCTED → SETTLED at T_l EOD

tau_loan (type=SETTLEMENT, settlement_date=T_l+1, depends_on=u_collateral):
    Move(from=w_B, to=w_C, coord=own, unit=NVDA, qty=500)
    BookkeepingDelta: w_B.onloan += 500, w_C.borr += 500
    Side-effect: u_loan.lifecycle_stage = EXECUTED → INSTRUCTED → SETTLED at T_l+1
```

Between $T_{\ell}$ EOD and $T_{\ell}+1$ EOD: $u_{\mathrm{collateral}}$ is SETTLED, $u_{\mathrm{loan}}$ is INSTRUCTED. The mismatch is visible in the L_15 obligation table. A risk system reads this and flags the one-leg exposure for $C$.

### 6.3 What the team should pin

- **Prepay collateral obligations are independent of the loan obligation.** They are not bundled into the same `u^{\circ}`. This matches the saga compensation tower (data spec): each obligation has its own discharge predicate and its own compensation handler.
- **The dependency graph is in the smart contract, not in the data model.** $\tau_{\mathrm{loan}}$'s smart contract guard checks `u_collateral.lifecycle_stage == SETTLED` before admitting the loan settlement; this is a precondition check, not a data join.
- **Failure to deliver the loan after collateral has settled triggers GMSLA 5.2 / 5.4 close-out netting.** Workflow:
  1. $u_{\mathrm{loan}}$ exceeds deadline.
  2. Compensation handler invoked: under GMSLA, the borrower (C) is entitled to the return of the collateral. A new SETTLEMENT transaction reverses the collateral move.
  3. Both obligations terminate: $u_{\mathrm{collateral}}$ → COMPENSATED (by reverse), $u_{\mathrm{loan}}$ → CANCELLED.

This is exactly the saga pattern in `ledger_data_v1.0` §Operational-Saga, with the deferred-settlement extension being one of the named obligation kinds.

---

## 7. SFTR, EMIR, CSDR, FINRA SLATE reporting interactions in the open window

### 7.1 The trade has multiple identifiers

A single short sale plus its supporting borrow generates reporting under three regimes simultaneously, each with its own identifier:

| Regime | Identifier | Where generated | Cadence |
|---|---|---|---|
| MiFIR RTS 22 | TRN (Transaction Reference Number) | Executing broker | T+1 EOD |
| SFTR | UTI (per ESMA waterfall, Article 4) | Both counterparties (per loan obligation) | T+1 |
| CSDR | CSD instruction reference | CSD itself (e.g. Euroclear T2S MsgId) | T to T+ISD |
| FINRA SLATE | Client Loan ID + FINRA Loan ID | Reporting member firm | Same-day per Rule 6500 schedule |
| Reg SHO threshold list | (no per-transaction ID; aggregate) | DTCC | Daily |

### 7.2 UTI generation — the gotcha

Under SFTR Article 4, the UTI is generated by one counterparty per a defined waterfall:
1. If one counterparty is a CCP, the CCP generates.
2. Otherwise, the seller (or the lender for SBL) per the bilateral identification.
3. In agency lending, the agent generates on behalf of the underlying lenders.

For our short-sale-plus-borrow: the **borrow obligation** has a UTI; the **cash sale** does not (sales are not SFTs). The UTI is reported in the SFTR NEWT message at $T_{\ell}+1$.

**The hidden issue:** SFTR reports the *trade date* and the *intended settlement date* of the loan. CSDR reports the *actual fail date* and the *penalty period*. If the loan fails settlement (rare but real), there are entries in both regimes for the same underlying event with different timestamps. The Ledger's bitemporal model in $L_{15}$ obligation (`t_obs` for trade time, `t_known` for restatement) handles this without conflating.

### 7.3 EMIR

EMIR Refit (Apr 2024) covers derivative reporting. SBL is not a derivative; SFTR covers SBL. **Cross-regime confusion:** equity TRS or equity options that *settle* in physical delivery referencing a deferred-settlement equity have the underlier's settlement reportable under EMIR Refit lifecycle events. ISDA's DRR maps this. For our cash-equity-plus-SBL composition, EMIR is silent unless the equity is a derivative underlier.

### 7.4 The tri-regime gotcha

A short sale + borrow + fail + buy-in produces:

- **MiFIR**: 2 transaction reports (original sale, buy-in).
- **SFTR**: NEWT (loan), MODI (recall if any), ETRM (loan termination on buy-in).
- **CSDR**: penalty advices (potentially two — one for the failed sale, one for the failed return if that fails too).
- **SLATE**: New Loan Event, Modification (recall), Termination (return / buy-in).
- **Reg SHO**: threshold list aggregation.

All of these are deterministic projections of the move stream + L_15 obligations + L_17 RegulatorySubmission. **The same underlying truth, multiple regulatory views.** This is the DRR golden-source position ISDA articulates and that I support.

### 7.5 What the team should pin

- **Each obligation row carries all relevant identifiers as metadata.** The L_15 schema needs fields: `mifir_trn`, `sftr_uti`, `csd_instruction_ref`, `slate_loan_id`, `slate_finra_loan_id`. These are populated by the settlement projection at outbound emission and reconciled at inbound confirmation.
- **The reporting fan-out is a workflow, not a data model concern.** Each regime has its own L_17 RegulatorySubmission row; they reference the same obligation_id but generate distinct payloads.
- **Bitemporal handling of restatements is mandatory.** If a CSDR penalty is later adjusted (e.g., ESMA recalibrates the rate retroactively), the L_15 obligation's `t_known` is updated; the original `t_obs` is preserved.

---

## 8. What I reject — and why

### 8.1 I reject "settlement state as a bare flag on the transaction"

This was my Phase 1 §1.3 argument and I retract part of it but not all. The flag-only approach (just a `lifecycle_stage` field on the `MoveStream` row) loses three properties that we need:

1. **Per-leg granularity for partial settlement.** If a SETTLEMENT-type transaction has both a securities and a cash leg (DvP), and one leg partial-settles while the other does not, the bare flag on the parent transaction cannot represent this. We need *per-leg* obligations. Cartan's $u^{\circ}(\tau)$ with `securities_leg` and `cash_leg` ProductTerms is correct; flag-only is not.

2. **CSDR penalty grain.** Penalty accrues per-instruction-day-of-fail (IBP-141). The flag-only approach forces a denormalised join. The L_15 obligation row holds the accrual directly.

3. **Buy-in linkage.** A buy-in is a new transaction that *replaces* the failed delivery. It is not a state change on the original. The L_15 obligation provides the linkage (`compensation_κ` references the buy-in transaction); the flag-only approach loses this.

So I reject **bare-flag-only**, and accept **L_15 obligation row + per-transaction flag as a projection**.

### 8.2 I reject the proposals that put settlement state on `UnitStatus[u]` keyed to the security ISIN

A few proposals (most explicitly Halmos and Ashworth's hybrid) place settlement_status on `UnitStatus[u]` where `u` is the ISIN. **This is wrong.** The ISIN is shared across all holders; settlement is per-trade. Two different trades on the same ISIN can have different settlement statuses simultaneously. ISDA's §1.3 makes this point directly; I support it.

The correct placement: `UnitStatus[u^{\circ}]` where `u^{\circ}` is the obligation unit (Cartan's construction). This is the only formulation consistent with the StatesHome 3-map ruling: each per-trade fact is keyed to a per-trade unit identifier.

### 8.3 I reject the seven-coordinate proposals (including my own Phase 1)

For the reasons in §0 above. My Phase 1 was wrong. Feynman's proposal (which independently arrived at a 2-coordinate split: `own_settled` / `own_inflight` plus the obligation register) is the closest to my Phase 1 and shares its defect: it conflates economic recognition (which is at trade date and writes `own`) with custody convergence (which is at settlement date and should not write any GPM coordinate). The mainstream design separates these cleanly.

### 8.4 I reject "settlement state is purely external; the Ledger doesn't model it"

Some readings of v10.3 §11.6 lean toward this: settlement is downstream, the Ledger emits an instruction and forgets. **This is also wrong.** The settlement obligation is an economically load-bearing entity: it generates CSDR penalties, drives the buy-in workflow, attaches to regulatory reports, and feeds reconciliation. If the obligation is purely external, we have two systems claiming truth (the Ledger for trade-date economic state, the settlement utility for obligation state) — and reconciliation between them is exactly the problem the framework is designed to eliminate. Jane Street's §9 makes this argument crisply; I support it.

The Ledger represents *what we promised* (the obligation, with its discharge predicate and compensation handler). The settlement utility provides *how the promise is mechanically discharged* (SSI lookup, ISO 20022 generation, CSD wire). Boundary at the `SettlementInstruction` struct.

### 8.5 What I want the team to pin against drift

1. **The obligation $u^{\circ}(\tau)$ is per-trade, not per-leg.** The legs live in ProductTerms. Multiple legs (e.g., DvP securities + cash) live in one obligation. This matches v10.3 §13's grain for cash-collateralised SBL.

2. **Partial settlement updates UnitStatus counters, does not spawn a new $u^{\circ}$.** Cartan's §4.5 has this right. Spawning per partial creates an unbounded obligation graph; Jane Street's §6 cap-at-2 is operationally sensible but the cleaner data-model answer is no-spawn-at-all and let the residual remainder be a UnitStatus-counter.

3. **The GPM bookkeeping coordinates (`onloan`, `borr`, `coll_*`) update at SETTLED, not at EXECUTED.** This is the v10.3 §13.7 "no moves at settlement" rule, restated as "no moves on `own`; bookkeeping deltas at SETTLED". Crucially, this means the SBL state machine's "ACTIVE" loan state corresponds to `lifecycle_stage = SETTLED` on $u^{\circ}_{\ell}$, not to EXECUTED.

4. **The locate Unit is registered against `available_to_lend`, not against the GPM directly.** Cartan and ISDA agree; my Phase 1 §8 was correct.

5. **Three regulatory IDs (TRN / UTI / CSD instruction reference / SLATE loan ID) are L_15 obligation metadata.** Not separate tables. One row, multiple columns, populated by the settlement projection.

6. **The recall obligation $u^{\circ}_{\mathrm{recall}}$ is distinct from the original loan obligation $u^{\circ}_{\ell}$ and from the recall-return delivery obligation $u^{\circ}_{\mathrm{recall\_delivery}}$.** Three obligations, each with its own FSM. The smart contract chains them via the dependency graph.

7. **The economic-exposure-at-T invariant (P24/E1/I-1) is a capability-level invariant, not just a logical one.** The settlement-confirmation handler must not have the capability to write `own` (or any GPM coordinate). This is enforced at compile-time via type-tagging per StatesHome C11. I align with Jane Street's §1.3 here without reservation.

---

## 9. The summary the team needs

The mainstream design — virtual wallets, L_15 obligation rows, transaction-level lifecycle FSM — is sufficient for SBL composition once we pin:

- The economic-exposure-at-T invariant (P24/E1/I-1) at the capability level.
- The obligation as a unit (Cartan's $u^{\circ}$) with per-trade granularity, per-leg ProductTerms, and per-instruction L_15 row.
- The GPM bookkeeping coordinates updating at SETTLED, not EXECUTED, so that `onloan`/`borr`/`coll_*` reflect *post-settlement* state.
- The reconciliation identity as a query over the move stream + obligation table, not as a stored coordinate.
- Three regulatory IDs (MiFIR TRN, SFTR UTI, CSDR instruction ref, SLATE loan ID) as obligation metadata.
- Saga-compensation tower for fail-paths: CSDR penalty, buy-in, GMSLA 9.3 close-out, Reg SHO close-out — each a named compensation handler, each a closed sum branch.

The seventh coordinate I argued for in Phase 1 is unnecessary. The composition arguments I made in Phase 1 §7 — short-sale-with-locate-and-late-borrow, recall-during-open-window, manufactured-dividend, Herstatt — all migrate cleanly to the mainstream design as walked through in §2-§7 above.

The one thing I retain from Phase 1 without compromise: **the lead-lag between Ledger position and CSD/depot position is a reportable scalar from a single arithmetic identity at every $t$.** That identity is now P29 in the form

$$
\mathrm{own}_e(u) + \mathrm{borr}_e(u) - \mathrm{onloan}_e(u) - \sum_{i \in \mathrm{open}(e,u)} \mathrm{signed\_qty}(i) = D(e, u)
$$

with `signed_qty` computed from the L_15 obligation table and the inflight virtual wallet. Same identity, different storage. I retract the storage claim; I retain the reporting requirement.

— Margaret Chen, sbl-specialist, Phase 2 Settlement Team
