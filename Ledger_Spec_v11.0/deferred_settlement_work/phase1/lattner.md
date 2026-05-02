# Deferred Settlement: An Architectural Proposal

**Author role:** Chris Lattner (architectural review).
**Phase:** 1 of v11.0 orchestrated specification effort.
**Independent proposal — no cross-talk with other Team A members.**

---

## 0. The architectural question, sharpened

The user asked: *how should the Ledger represent the open settlement obligation between T and T+2?*

I am going to refuse the framing as posed. The interesting question is not "how do we represent the gap." The interesting question is: **does deferred settlement deserve a primitive in the closed-system, or is it a library on top of primitives that already exist?** Get that wrong and we will be re-litigating it in every release for ten years.

My answer, defended below: it is a **library**, almost entirely. The closed-system already has the primitives needed (atomic moves, virtual wallets, the Obligation type, the SBL six-coordinate vector, the StatesHome 3-map ruling, the L_15 leaf). What is missing is the *composition* — a thin module that ties them together with a name. We are not adding a new sector; we are naming a pattern that already lives in the framework's vocabulary.

The architectural failure mode I am writing this document to prevent is the seductive alternative: introducing a new sector ("PendingSettlements"), a new state coordinate ("unsettled"), a new lifecycle stage on units, or — worst of all — a new conservation carve-out for "trade-date but not settlement-date." Every one of those is a v10.x line that we will spend the next decade unwinding. Stop.

---

## 1. State representation

### 1.1 The single-screen rule

A reader who has internalised v10.3 plus the StatesHome addendum should be able to fit deferred settlement into one mental screen. Anything more and we have a leaky module.

The one screen:

```
A buy of 100 XYZ @ $50 settling T+2 is, at trade date T, an atomic
ledger transaction containing two moves:

   Move 1: w_buyer.own        += 100 XYZ      (own coordinate)
   Move 2: w_settle_buy_T+2.own -= 100 XYZ    (virtual wallet, contra)

   Move 3: w_settle_buy_T+2.own += 5,000 USD  (virtual wallet, contra)
   Move 4: w_buyer.own        -= 5,000 USD    (own coordinate)

The transaction registers an Obligation o_settle:
   type        = SETTLEMENT_DELIVERY  (DvP, two-leg)
   deadline    = T+2 17:00 (CSDR-aligned)
   discharge   = sese.025 confirms both legs
   compensation= CSDR penalty + buy-in workflow
```

That is it. Conservation holds for **both** XYZ and USD, by the same `src -= q; dst += q` algebra that holds for every other transaction. PnL recognition starts at T because `own` updates at T. Custody movement — what happens at the CSD, in the real world — is the responsibility of the settlement projection, the obligation handler, and the confirmation return path, all of which already exist.

There is no new sector. There is no new coordinate. There is no new conservation law. There is one new *unit type* (the per-(security, settlement-date) pending-settlement virtual wallet, which is a wallet, not a unit; see §1.3) and one new *obligation kind* in the L_15 closed sum.

### 1.2 What the pending-settlement virtual wallet is

`w_settle_buy_T+2[security, settle_date, counterparty]` is a virtual wallet. Virtual wallets are already in v10.3 §2.5. They are not a special kind of object; they are a wallet whose `is_virtual` flag is true and whose external identifier resolves to the relevant CSD participant + counterparty pair.

The naming discipline I propose:

- **Pending-buy wallet** `w_PEND_BUY[security, settle_date, cpty_LEI]`: receives the security obligation owed to us.
- **Pending-sell wallet** `w_PEND_SELL[security, settle_date, cpty_LEI]`: holds the security obligation we owe.
- **Pending-cash wallet** `w_PEND_CASH[ccy, settle_date, cpty_LEI]`: the cash side, named symmetrically.

These are constructed deterministically from trade metadata. They are **named, not magical** — any consumer of the framework can reconstruct their identifiers from the trade. That matters for the Library-vs-Language question (§4 below).

### 1.3 The Obligation as the canonical state carrier

The state of "this trade has been executed but not yet settled" lives in **L_15 Obligation**, not in unit state, not in position state, not in a new sector. Specifically:

```
Obligation:
  id            = hash(tx_id, "settle_obligation")
  kind          = SettlementDelivery {
                     security_leg : (unit, qty, deliverer, receiver),
                     cash_leg     : (ccy, amt, payer, receiver),
                     dvp_atomic   : Bool
                  }
  deadline      = settle_date_eod (CSDR Article 5)
  discharge     = ByMatch { matcher: sese025_confirmation_matcher }
  compensation  = NonTrivialChildWorkflow {
                     workflow_ref: CsdrFailWorkflow,
                     tower_depth : 2
                  }
  source        = tx_id of the originating trade transaction
```

The discharge predicate is **bitemporal-aware** by L_15's $\Phi_{15}^W$. The compensation handler is a saga (§6 below).

This is exactly the obligation framework already specified in v10.3 §17 + L_15. No extension required to the Obligation *type*; only an additional *constructor* in the closed sum on `kind`. That distinction is load-bearing — see §3.

### 1.4 What I refuse to add

- No new "pending" or "unsettled" coordinate on the SBL six-vector. The vector is already at the right granularity for ownership-vs-possession. Adding a seventh coordinate for trade-vs-settlement breaks the invariant that every coordinate corresponds to a distinct *physical* action; "executed-but-not-settled" is a *temporal* status, not a physical action. Conflating them is the kind of mistake that makes a system unmaintainable. (Compare: in LLVM IR, we resisted for years adding a new Value kind for "potentially-deleted-in-this-pass." It is a status of the analysis, not a property of the value. Same lesson here.)
- No new lifecycle stage on the *security* unit. The security has not changed. What has changed is the *trade*, and the trade is captured in the move stream and the Obligation.
- No new conservation carve-out. Conservation holds at trade-date with the virtual wallets present. If you find yourself writing `if not is_pending_wallet(w): sum += w.balance` you have already lost.
- No bitemporal split between "trade-date world" and "settlement-date world." The bitemporal type in L_19/$\texttt{Bitemporal}\langle T\rangle$ exists for *restatements* (vendor corrections, late confirms). It is not the right hammer for normal-path settlement timing.

---

## 2. Move sequence with conservation: T, T+1, T+2⁻, T+2⁺

I will work the canonical case (buy 100 XYZ @ $50 settling T+2) and verify conservation at every snapshot.

### 2.1 At T: trade execution

One atomic transaction $\tau_{\text{exec}}$ of four moves.

```
tau_exec @ T = Transaction(type = SETTLEMENT, dvp = true):
  Move 1: w_buyer.own[XYZ]            += 100
  Move 2: w_PEND_BUY[XYZ,T+2,cpty].own[XYZ] -= 100   (contra)

  Move 3: w_PEND_BUY[XYZ,T+2,cpty].own[USD] += 5000  (contra)
  Move 4: w_buyer.own[USD]            -= 5000
```

Plus: register Obligation `o_settle` (per §1.3).

**Conservation at T (immediately after tau_exec):**

Per-unit sums across all wallets (real + virtual):

- $\Delta Q(\text{XYZ}) = +100 + (-100) = 0$ ✓
- $\Delta Q(\text{USD}) = +5000 + (-5000) = 0$ ✓

The buyer's wallet now reads `own[XYZ] = 100, own[USD] = -5000`. The negative USD is fine: it is the unsettled cash obligation, sitting on the buyer's books exactly as a margin loan would. The economic exposure to XYZ is **immediate**: $V_T$ now includes $100 \cdot P_T(\text{XYZ})$.

**This is the mandatory invariant.** Economic exposure begins at T. No exception. No "accrual." No "pending PnL bucket." This is what Path-Independent PnL and State-Sufficiency mean. If the proposed mechanism cannot deliver this, throw it out.

### 2.2 At T+1: nothing

`clone_at(T+1)` is identical to the state immediately after `tau_exec`, with prices updated. The ledger does not "know" anything new at T+1 unless an external event arrives (recall, corporate action, restatement). PnL between T and T+1 is purely $100 \cdot (P_{T+1} - P_T)$. The Obligation is in `Pending` state, its workflow timer is durable, and no moves have fired.

### 2.3 At T+2⁻ (before settlement message arrives)

Same as §2.2, with `T+1` replaced by `T+2 morning`. The Obligation is still `Pending`. The settlement projection (v10.3 §10.1) has long since produced a `SettlementInstruction` from `tau_exec` and the settlement layer has emitted the wire message. None of that has changed any ledger state.

### 2.4 At T+2⁺ (after sese.025 success)

The L_11 ExternalConfirmation arrives. Its handler signals the obligation workflow's discharge channel. The discharge predicate matches; the obligation transitions `Pending → Discharged`. **No moves are emitted.** The positions were already correct from T.

Optionally — and this is a design choice the framework should expose, not bake in — an *accounting* transaction may be emitted to "settle" the virtual wallets. The cleanest version simply leaves them where they are: the settled virtual wallet has `own[XYZ] = -100` and `own[USD] = +5000`, balanced and inert. Garbage-collecting it is a separate concern (cf. F3 in the StatesHome risk register: monotone carrier compaction). My recommendation: **do not** emit an accounting transaction for the happy path. The virtual wallet stays. Reading `clone_at(t)` for any `t > T+2` gives the right answer because the obligation is `Discharged`, not because we re-shuffled positions.

### 2.5 Why I keep the virtual wallet around

Three reasons, and they are decisive:

1. **No special-case algebra.** Conservation reads identically before and after settlement.
2. **Time-travel for free.** `clone_at(T+1)` works because the virtual wallet *still has the obligation balance on it* at that knowledge time. Garbage-collecting it would force `clone_at` to reconstruct it on demand from the obligation log — a strictly more complex operation, with strictly more failure modes.
3. **Audit trail.** The virtual wallet *is* the trail. Operators looking at "what is unsettled with counterparty X on date D" run a wallet-balance query, not an obligation-table join.

This is the same reasoning that drove "monotone carrier" in the StatesHome ruling (C1, addendum §2.2). Same lesson: **storage discipline is cheaper than reconstruction discipline.**

---

## 3. Invariants

### 3.1 The mandatory economic-exposure-at-T invariant (P24)

**P24 — Trade-Date Recognition.** For every settlement-typed transaction $\tau$ committed at time $T$ with settle date $T_s \geq T$, the position vectors of the real wallets in $\tau$ reflect the post-trade economic state at $T$. Formally: for every unit $u$ in $\tau$ and every wallet $w$ that is a source or destination of a move in $\tau$,

$$\vec{w}(u)[\text{own}]_{T} = \vec{w}(u)[\text{own}]_{T^{-}} + \sum_{m \in \tau, m.\text{unit}=u, m.\text{coord}=\text{own}} \text{signed-delta}(m, w).$$

That is: the `own` coordinate moves at T, not at $T_s$.

This is the core economic invariant of deferred settlement. Everything else is mechanism.

### 3.2 P25 — Settlement-Obligation Liveness

For every settlement transaction $\tau$, an obligation $o_\tau \in L_{15}$ exists with `source = tx_id(τ)`, deadline `≤ T_s + grace_period`, and falls under P21 (obligation liveness). No settlement transaction commits without its obligation registered atomically (Principle 17.1, Obligation Completeness, lifted to settlement-typed transactions).

### 3.3 P26 — Pending-Wallet Closure

For every (security, settle_date, counterparty) triple at every time $t$,

$$\sum_{w \in \mathcal{W}_{\text{PEND}}(\text{security, settle\_date, cpty})} w(\text{security}) + \sum_{w \in \mathcal{W}_{\text{PEND}}(\text{security, settle\_date, cpty})} w(\text{ccy}) \cdot \text{sign\_convention}$$

equals the sum of unsettled trade obligations for that triple. This is a **definitional identity** — there is no path by which it can fail unless `tau_exec` has been ill-formed. It is testable by a single linear scan and serves as the headline reconciliation against the CSD's pending-instruction queue.

### 3.4 P27 — Settlement-Idempotency

Receiving the same `sese.025` confirmation twice (same `external_message_id`) discharges the obligation once and only once. This composes with P5 (transaction idempotency), P6 (lifecycle idempotency), P23 (obligation idempotency), and the L_11 well-formedness predicate $\Phi_{11}^W$. It is not a new mechanism; it is a name for the composition.

### 3.5 What I am *not* asserting

- I do not assert "settled positions equal trade-date positions" as an invariant, because that would conflate two epistemically distinct things (economic exposure vs. real-world custody). The Ledger boundary (v10.3 §13) is exactly the line between them.
- I do not assert any timing guarantee on T+2 settlement. CSDR can fail, the CSD can be down, the counterparty can default. The framework's job is to *represent* these eventualities, not to prevent them.
- I do not assert conservation between (real-wallet `own`) and (custodian-records `own`). That is a *reconciliation* task across the boundary, not an invariant within the closed system.

---

## 4. Library vs. language: my decisive recommendation

**Recommendation: deferred settlement is a library on top of existing primitives.**

### 4.1 The argument

A user (a smart contract author, an integrator, an internal tool) can already, with v10.3 + StatesHome + L_15:

1. Issue a transaction that places trade-date `own` deltas on real wallets and balancing entries on virtual wallets.
2. Register an L_15 obligation alongside, with arbitrary discharge predicate and compensation handler.
3. Consume confirmation messages via L_11 to discharge.
4. Run the settlement projection on `tau_exec` to get an ISO 20022 instruction (v10.3 §10.1 already handles this — no change required).

So the question is not "can we build deferred settlement out of primitives?" but "should we add deferred settlement *as* a primitive?" The answer is no.

### 4.2 Why it should be a library

This is the same argument I made for everything in the Swift standard library that could possibly live there. If the compiler does it specially and users can't replicate it, you have built a caste system: built-in operations are first-class, user operations are second-class. Eventually some user wants to build a third-class thing, and they cannot — they have to lobby for a language change.

In the Ledger context, this manifests as:

- **A user wants T+0 atomic DLT settlement.** Library: trivial — emit the same transaction with `T_s = T`, register an obligation with deadline `T + 1ms` and a different discharge matcher (an on-chain event instead of `sese.025`). Same algebra. Compiler: requires a new "settlement mode" in the executor, with all the testing and version-skew that implies.
- **A user wants partial-fail-then-buy-in.** Library: the obligation's compensation workflow handles it. New saga, no framework change. Compiler: requires partial-state extension on every transaction primitive.
- **A user wants T+1 / T+2 jurisdiction-mixed settlement** (US equity move to T+1, EU stays T+2). Library: the obligation deadline is computed from a per-jurisdiction rule. Compiler: requires every transaction to carry jurisdiction-dependent timing.
- **A user wants voluntary corporate action choices in the window.** Library: a separate obligation registers the choice deadline, with compensation = "default election." Compiler: requires extending the corporate action mechanism with mid-flight optionality.

In every one of these, the library version is a few dozen lines of smart-contract-author code and needs no executor change. The language version is a multi-quarter release.

### 4.3 What is "the library," concretely

A new module in the Ledger spec, call it **`DeferredSettlement`**, exporting:

- A function `register_settlement_obligation(tx, settle_date, dvp_kind) -> Obligation`. Pure. Total. Takes a transaction, returns an obligation suitable for atomic registration alongside the transaction.
- A constructor in the L_15 `kind` closed sum: `SettlementDelivery { security_leg, cash_leg, dvp_atomic, jurisdiction }`.
- A naming scheme for the pending-settlement virtual wallets (deterministic from trade metadata), exported as `pending_buy_wallet(security, settle_date, cpty)`, `pending_sell_wallet(...)`, `pending_cash_wallet(...)`.
- A workflow template `SettlementObligationWorkflow` parameterised over the discharge matcher and compensation kind.
- A reconciliation projection `pending_settlement_view(t, cpty) -> List[(security, settle_date, qty)]` that scans the pending virtual wallets — used for the daily T+1 reconciliation against the CSD's Counterparty Pending file.

That is the entire surface area. Five exports. Each is composable. Each is replaceable. None of them touch the executor, the conservation law, the move primitive, the SBL vector, the FSM, or the StatesHome 3-map ruling.

### 4.4 The one thing I want in the "language" (closed-system) layer

One thing only: **the `kind` field of L_15 must be a closed sum, and `SettlementDelivery` must be one of its constructors at the framework level.** This is not because the framework needs it — it does not — but because the *test generator universe* needs it. Property-based testing per v10.3 §11 walks the closed sum and checks completeness. A library-defined obligation kind that the test generator does not know about is a coverage hole. Adding the constructor to the closed sum costs us one line of code and one dispatch case in the workflow factory, and buys us testability that survives forever.

This is the only "compiler" change. Everything else is library.

---

## 5. API surface: position with open obligations, not (position, list of obligations)

A separate but related question: when the rest of the framework reads a wallet, what does it see? Two options:

**Option A:** `position(w, u) → ScalarOrVector` — the existing API, returning ownership state only. Obligations are queried separately via `obligations_for(w, u)`.

**Option B:** `position(w, u) → (ScalarOrVector, List[Obligation])` — a single API returning both.

**My recommendation: Option A, unequivocally.**

### 5.1 Reasoning

Option B feels like progress. It is not. It violates separation of concerns: the position is a question about *what is owned*; the obligation list is a question about *what is promised*. They are answered by different stores (PositionState L_6 vs. Obligation L_15) with different mutation disciplines (monotone carrier vs. FSM-per-id). Bundling them in one API creates a join at every read site, which (a) confuses the cache story and (b) makes it impossible to extend obligations without changing the position API.

Option A keeps the existing position API stable and makes the obligation query a separate, optional concern. Code that does not care about obligations does not pay for them. Code that does care can call `obligations_for(w, u)` (or, more usefully, `obligations_for_tx(tx_id)`) and join in the application layer. The two queries are *composable*; the bundled API is *fused*, which is harder to refactor.

### 5.2 The "easy thing should be easy" test

The simplest deferred-settlement consumer is a PnL report that computes $V_t = \sum_u w(u) \cdot P_t(u)$. Under Option A, this report is *unchanged from v10.3*. The deferred settlement mechanism is invisible. This is correct: PnL does not care whether the position has settled, only whether it exists.

Under Option B, the report would need to pattern-match on the obligation list to decide whether to count the position, even though the answer is always "yes, count it." We have introduced complexity for the 99% of consumers who do not need it. That is the wrong direction.

### 5.3 Where the obligation list *is* the right answer

For three specific consumers:

- The settlement-status dashboard ("show me all unsettled trades for cpty X on date D").
- The CSDR-fail workflow ("which obligations are at risk of breaching the deadline?").
- The daily T+1 reconciliation against the CSD's pending file.

For these, the right query is *not* `position(w, u)` at all. It is `obligations_where(kind = SettlementDelivery, predicate = ...)`. A dedicated query, narrowly scoped. This is what Option A enables and Option B muddles.

---

## 6. Failure modes and diagnostics

### 6.1 The taxonomy

Settlement can fail in these distinct ways. Each must be representable, distinguishable from the others, and diagnosable from a single operator log line.

| Failure | Representation | Compensation |
|---|---|---|
| **CSDR fail (no delivery by T+2)** | Obligation timer fires; `Pending → Compensated` | Buy-in workflow + CSDR penalty accrual |
| **Partial fail (delivers 60 of 100)** | Obligation discharge predicate sees `sese.025` with `partial_qty < expected_qty`; child obligation registered for residual | Continue + new buy-in workflow on residual |
| **Counterparty default before T+2** | L_10 `LifecycleEvent.Default` arrives; compensation workflow elevated; obligation `Pending → Compensated` via close-out netting | ISDA close-out netting under Master Agreement |
| **Recall mid-window (SBL)** | Existing SBL recall workflow fires; new return-by deadline registered as separate obligation | Buy-in (GMSLA 9.3) |
| **Corporate action mid-window** | L_10 `CorporateAction` event signals affected pending settlements via fan-out (v10.3 §13.13) | Adjustment to `tau_exec` outcome via amendment transaction; obligation deadline may extend |
| **Cross-currency Herstatt** | Two separate obligations — one per currency leg — with non-aligned deadlines; PvP failure if one settles, other doesn't | CLS reconciliation; if not CLS, asymmetric exposure recorded explicitly |
| **DvP atomicity break (cash leg fails after stock leg succeeds)** | Two separate obligations under one `dvp_atomic = true` flag; obligation handler refuses to mark either Discharged unless both confirmed | Reverse the settled leg; or escalate per CSD rules |

### 6.2 Why each is distinguishable

The compensation handler kind in L_15 is a closed sum. Each failure routes to a *named* handler:

```
type CompensationHandlerKind =
  | CsdrBuyIn { residual_qty }
  | CsdrPenaltyAccrual { rate, days }
  | CloseOutNetting { master_agreement_id }
  | SBLRecallBuyIn
  | CorporateActionAmendment { event_ref }
  | DvPAtomicityReversal { settled_leg_id }
  | HerstattAsymmetricExposure { unsettled_leg }
```

When a failure fires, the operator's log gets a single line:

```
[OBLIGATION o_settle_X3F2] Compensated via CsdrBuyIn{residual=40}.
  Source tx: tx_T_2026-04-28-XYZ-100. Cause: sese.026 received,
  partial settlement 60 of 100. Child obligation
  o_settle_X3F2_residual created for the remaining 40, deadline
  T+5 per CSDR Article 7.
```

That line answers four questions: what failed, what was attempted, what was paid for the failure, what happens next. **This is what good diagnostics look like.** A diagnostic that tells the operator something failed without telling them why is useless. A diagnostic that tells them why without telling them what is being done about it is worse — it implies they need to do something.

### 6.3 The four-eyes case

For the `Closed-Waived` state in L_18 BreakRegister: a fail that the operator has decided to close manually (because, e.g., the counterparty has paid the buy-in cost out of band). This requires four-eyes per L_18 $\Phi_{18}^W$. The deferred-settlement library does not need to add anything here — L_18 already enforces it. The library merely needs to ensure that obligations marked `Defaulted` produce a corresponding `BreakRegister.Open` entry.

### 6.4 Observability invariants

For every compensation event, the framework must expose:

- The originating transaction (`source` field of the obligation).
- The triggering external event (the `external_message_id` from L_11, if any).
- The compensation handler kind and its parameters.
- The child obligations or transactions emitted by the handler.

These are not a "monitoring layer." They are properties of the L_15 entry. The monitoring system is a *projection* over L_15, not an independent record. This is the same architectural move as the move stream being the source of truth for PnL: the compensation log is the source of truth for failure analysis. No second record to drift.

---

## 7. Worked example: 100 XYZ @ $50 → $52, no cash moved, PnL = +$200

### 7.1 Setup

- Buyer wallet: `w_B` (real). Initial: `own[USD] = 10000, own[XYZ] = 0`.
- Counterparty (broker) virtual wallet: `w_cpty`. Routes through CSD-DTC.
- Pending wallets (constructed deterministically): `w_PEND_BUY[XYZ, T+2, cpty_LEI]`.
- $P_T(\text{XYZ}) = 50$. $P_{T+1}(\text{XYZ}) = 52$.

### 7.2 At T (trade execution)

```
tau_exec @ T = Transaction(type = SETTLEMENT, dvp = true,
                            tx_id = "tx_T_buy100XYZ"):
  Move 1: w_B.own[XYZ]                    += 100
  Move 2: w_PEND_BUY[XYZ,T+2,cpty].own[XYZ] -= 100
  Move 3: w_PEND_BUY[XYZ,T+2,cpty].own[USD] += 5000
  Move 4: w_B.own[USD]                    -= 5000

  Obligation o_settle:
    id            = hash("tx_T_buy100XYZ", "settle")
    kind          = SettlementDelivery {
                       security_leg : (XYZ, 100, cpty, w_B),
                       cash_leg     : (USD, 5000, w_B, cpty),
                       dvp_atomic   : true,
                       jurisdiction : US
                    }
    deadline      = T+2 17:00 EST
    discharge     = ByMatch { matcher: sese025_matcher(tx_id) }
    compensation  = NonTrivialChildWorkflow {
                       workflow_ref: CsdrFailWorkflow,
                       tower_depth : 2
                    }
    source        = "tx_T_buy100XYZ"
```

### 7.3 Conservation at T

- `Q(XYZ) = +100 + (-100) = 0` ✓
- `Q(USD) = +5000 + (-5000) = 0` ✓
- Obligation registered: 1 ✓
- P24 satisfied: `w_B.own[XYZ] = 100` *at T*, not at T+2.

### 7.4 Portfolio value computation

At T:
$$V_T(w_B) = w_B(\text{USD}) \cdot 1 + w_B(\text{XYZ}) \cdot P_T(\text{XYZ}) = 5000 + 100 \cdot 50 = 10000.$$

At T+1:
$$V_{T+1}(w_B) = 5000 + 100 \cdot 52 = 10200.$$

PnL between T and T+1:
$$\text{PnL} = V_{T+1} - V_T = 10200 - 10000 = +200.$$

**No cash has moved between T and T+1.** The PnL is entirely the price appreciation on the 100 XYZ that the buyer's `own` coordinate already reflects. This is the headline result.

### 7.5 At T+2⁺ (sese.025 success)

L_11 ExternalConfirmation arrives with `external_message_id = "DTC-conf-XYZ-2026-04-30-001"`, matching `tx_id = tx_T_buy100XYZ`. Handler signals `discharge_o_settle` channel. Obligation workflow's discharge predicate evaluates: `sese.025.success = true ∧ qty = 100 ∧ ccy = USD ∧ amt = 5000`. True. Transition `Pending → Discharged`. **No moves emitted.**

State of buyer at T+2⁺:
- `w_B.own[XYZ] = 100` (unchanged from T).
- `w_B.own[USD] = 5000` (unchanged from T).

State of pending virtual wallet:
- `w_PEND_BUY.own[XYZ] = -100` (unchanged).
- `w_PEND_BUY.own[USD] = +5000` (unchanged).

The pending wallet is now *inert*. It will accumulate further pending-settlement entries on subsequent trades but is never garbage-collected. P26 still holds: the sum across all pending wallets equals the sum of `Pending` obligations, which is now zero for this (XYZ, T+2, cpty) triple.

### 7.6 The decade test on this example

Read this in 2036. Can the reader extend it without rewriting?

- **T+1 settlement (US equity 2024 transition).** Change one parameter in the obligation: `deadline = T+1 17:00`. Done. Recompile the discharge workflow. No move-stream change. ✓
- **DLT atomic settlement (T+0).** Change deadline to `T + 1ms`, change discharge matcher from `sese025_matcher` to `chain_event_matcher`. Done. ✓
- **Partial fail on this trade.** Confirmation arrives with `qty = 60`. The discharge predicate fails strict match. Compensation handler fires for `residual = 40`, registers a new obligation. Done. The original `tau_exec` is unchanged in the move stream. ✓
- **Mid-window corp action (2-for-1 split T+1).** L_10 CorporateAction event triggers fan-out to all pending settlements on XYZ. The fan-out workflow emits an amendment transaction adjusting the security_leg of `o_settle` from `(XYZ, 100)` to `(XYZ_new, 200)` and adjusts the pending-wallet balance accordingly. Conservation holds across the amendment (the 2-for-1 split itself conserves, by C8 of StatesHome). ✓

In each case, the change is **localised**: one parameter, one workflow ref, one discharge matcher. No section of the existing spec needs to be touched. That is what "modular" means.

---

## 8. Sanity checks I ran on this proposal

These are the questions I forced myself to answer before recommending. If a reviewer disagrees with any answer, the design needs to change.

**Q1.** *Does the simple case stay simple?* Yes. A buy/sell of an equity for cash is one transaction with four moves and one obligation. Reading PnL never requires knowing about the obligation. The pending wallet is named and inspectable but invisible to consumers who don't ask.

**Q2.** *Does each variant add what it needs and nothing more?* Yes — see the matrix in §6.1. Each failure mode adds exactly one compensation handler kind. Composition is by handler dispatch, not by pervasive change.

**Q3.** *Is the new module replaceable?* Yes. Every export is a pure function, a closed-sum constructor, a workflow template, or a deterministic naming scheme. Each can be swapped for a better implementation.

**Q4.** *Does the type system help or hinder?* Helps. The closed sum on `kind` makes the test generator universe complete. The `dvp_atomic` Bool is a single bit of information that disambiguates two-leg obligations. The `jurisdiction` field is what carries CSDR vs SEC vs APAC timing rules without polluting the obligation deadline computation.

**Q5.** *What is the ownership story?* The obligation is owned by the originating transaction's smart contract (via `source = tx_id`). It is freed (transitioned to terminal state) by the discharge predicate or compensation handler. There is no shared mutable state. There are no races: the obligation workflow is single-writer per `o.id` (Temporal workflow ID = `o.id`).

**Q6.** *Does this scale in complexity?* I claim yes. The proof: the entire deferred-settlement mechanism fits in the §1.1 single screen plus a five-export library. Adding a new failure mode adds one constructor to a closed sum. Adding a new jurisdiction adds one entry to a deadline-computation table. Adding T+0 changes one parameter. None of these touch any other part of the spec.

**Q7.** *Are we meeting users where they are?* Yes. Existing CDM `BusinessEvent` semantics already distinguish `ExecutionEvent` from `TransferEvent`. Existing ISO 20022 `sese.023`/`sese.025` flows already cover the message round-trip. Existing CSDR/SEC frameworks already define the deadlines and the buy-in mechanics. The Ledger module is a *naming and composition* layer on top of vocabulary the user already knows.

**Q8.** *Will this support cases nobody has thought of yet?* The four hypothetical extensions in §7.6 (T+0 DLT, T+1 transition, partial-fail composition, corp-action-in-window) all reduce to parameter changes or compensation-handler additions. I cannot prove no future case will require a deeper change. I can claim that the cases I can articulate today reduce to library calls. That is the best I can do, and it is the bar the proposal must clear.

---

## 9. What I want from Phase 2 / 3

A specialist (likely a settlement engineer with CSDR + SEC experience) should:

1. Verify that my five exports cover every observable settlement workflow they have shipped, or enumerate what is missing.
2. Verify that the `CompensationHandlerKind` closed sum in §6.1 is exhaustive over the failure cases CSDR Article 7 actually tests.
3. Stress-test my claim that the `pending_settlement_view` projection (§4.3) reconciles bit-identically against the DTC, Euroclear, and Clearstream pending files. If it doesn't, the projection is incomplete.
4. Provide concrete numerical tolerances on the daily T+1 reconciliation against the CSD pending file (per the L_6 reconciliation pair in the data spec).

A formalist should:

5. Verify that P24, P25, P26, P27 are independent and that none of them are derivable from existing P1–P23.
6. Verify that the `kind` extension to L_15 does not break any of the 6 existing $\Phi_{15}$ invariants.
7. Run a TLA+ or Alloy model of the 7-row failure matrix in §6.1 against the obligation FSM and check that every (start_state, failure_kind) pair reaches a terminal state in bounded steps.

A test committee member should:

8. Generate property-based tests over (CDM event intent × jurisdiction × dvp_atomic × failure_kind) and verify that the deferred-settlement workflow handles all combinations or rejects them with a typed error.

---

## 10. The summary, as one sentence

**Deferred settlement is a 5-export library on top of v10.3's closed-system primitives + StatesHome 3-map ruling + L_15 Obligation, requiring exactly one extension to the closed-system layer (a new constructor in L_15.kind), preserving every existing invariant, satisfying the new mandatory P24 (economic exposure at T) plus P25/P26/P27 (liveness, pending-wallet closure, settlement-idempotency), and supporting T+0 / T+1 / T+2 / future-jurisdiction settlement uniformly via parameterisation rather than carve-outs.**

This is the design that, in ten years, the next Lattner-equivalent rereading the Ledger spec is least likely to want to throw out. That is the bar.

---

*— Chris Lattner, architectural review, Phase 1, v11.0.*
