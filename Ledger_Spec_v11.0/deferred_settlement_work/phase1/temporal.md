# Deferred Settlement: The Durable-Execution Section

**Author role:** temporal-engineer (Phase 1, Team A, independent draft)
**Question:** How should the Ledger represent the open settlement obligation between T and T+2 such that economic position is true from T, the obligation is explicit and reconcilable, the ledger reconciles to nostro at T+2, and the mechanism degenerates cleanly across variants?

This document answers that question from the durable-execution viewpoint. The move sequence and invariants are stated as the saga workflow sees them; reconciliation, failure modes, and the worked example are then derived.

The position taken throughout is the boundary stated in v10.3 §13: **the move sequence lives in the Ledger; the saga that produces and observes those moves lives in Temporal.** The deferred-settlement representation is therefore *two* artefacts that compose: (i) a state-augmented Ledger move log carrying a settlement-status lifecycle (`EXECUTED → INSTRUCTED → SETTLED | FAILED → …`), and (ii) a long-running `SettlementSaga` workflow that drives that lifecycle, observes the CSD, and either records finality or escalates compensation. Neither artefact is sufficient alone.

---

## 1. State Representation

### 1.1 What is "the open settlement obligation" as a typed object?

Following the v11.0 StatesHome 3-map ruling and §3013 Obligation taxonomy, the open settlement obligation is a first-class `SettlementObligation` row in the obligation store, paired with a `SettlementInstance` row that carries the runtime status. Both are append-only views over the event log.

```
SettlementObligation                   # registered at T atomically with the trade tx
  obligation_id    : "SO:" || hash_jcs(business_event_id, leg_index)
  type             : DVP_CASH | FOP_DELIVER | FOP_RECEIVE | CASH_ONLY
  source_tx_id     : tx_id of the trade transaction (for back-reference)
  settlement_date  : t_settle (calendar-resolved, BusinessCalendar pinned)
  legs             : [SecuritiesLeg] + [CashLeg]   # both populated for DVP
  cdsr_in_scope    : bool                          # CSDR Article 5 jurisdiction
  buyin_deadline   : t_settle + (4 | 7) business days   # CSDR mandatory buy-in cutoff
  state            : PENDING_INSTRUCT | INSTRUCTED | PARTIAL | SETTLED | FAILED | BUYIN | CANCELLED
                                                       (FSM, monotone except for re-instruction loops)

SettlementInstance                     # one per submission attempt
  instance_id      : ULID, durable at activity submit
  obligation_id    : back-reference
  csd_ref          : MessageReference assigned by CSD on accept (nullable until ACK)
  submitted_at     : durable wall-clock from activity (NOT workflow.Now())
  iso_message_hash : hash_jcs(canonicalised sese.023)
  finality_event   : sese.024/025 envelope, hash-pinned, attestation-bearing
```

`SettlementObligation` is the *what*. `SettlementInstance` is the *attempt log*. The trade-date economic position lives in `PositionState[w, u]` already and is **not** part of this object — that is the entire point of trade-date accounting.

### 1.2 Why a `(SettlementObligation, [SettlementInstance])` pair, not a single row

A single row collapses two distinct mutation disciplines: the obligation is bounded by the contract (one per legged trade leg, content-addressed on `business_event_id`) while instances multiply on each re-submission (partial, fail-and-retry, buy-in). Folding them produces a key that is no longer content-addressed and an FSM whose transitions are not monotone — both of which break replay determinism (memory: `ledger_v11_temporal.md` v2 §"Per-leaf idempotency-key classification").

### 1.3 What lives in the ledger event log vs. workflow history

```
Ledger event log (canonical economic record)
  - Trade transaction at T   :  Move(securities), Move(cash), state-only obligation creation
  - Status lifecycle entries :  state-only transactions (no moves) recording state transitions
  - CSD finality at T+2      :  state-only transaction (status -> SETTLED) + nostro-reconciliation marker
  - Fail event               :  state-only transaction (status -> FAILED)
  - Compensation             :  CORRECTION or BUYIN transaction with explicit anti-moves

Temporal workflow history (orchestration record)
  - Workflow start
  - Activity invocation: SubmitToCSD, RetrieveCSDStatus, ...
  - Timer set for t_settle, t_buyin_deadline
  - Signal received: csd_finality, csd_partial, ops_override
  - ContinueAsNew checkpoints
```

This is the v10.3 §10.3 "two audit trails" partition with nothing added.

---

## 2. Move Sequence — The T / T+1 / T+2⁻ / T+2⁺ Schedule

Worked at the level of one DVP cash-equity buy: 100 XYZ @ \$50, T+2 calendar, single counterparty `CP_A`, single CSD, USD cash.

### 2.1 T — Trade-date economic recognition (atomic, single transaction)

```
Transaction(type=SETTLEMENT, tx_id, ts=T, cdm_payload=..., status=EXECUTED):
    Move(from=w_market_proxy[CP_A]   ,  to=w_book                  ,  unit=u_XYZ ,  qty=+100)
    Move(from=w_book                 ,  to=w_market_proxy[CP_A]    ,  unit=USD   ,  qty=-5000)
    StateDelta:
        register_obligation(
            obligation_id    = "SO:" || hash(business_event_id, leg=0),
            type             = DVP_CASH,
            settlement_date  = T+2,
            buyin_deadline   = T+6 (= T+2 + 4 b.d., CSDR liquid),
            state            = PENDING_INSTRUCT,
            cdsr_in_scope    = true)
```

**Conservation holds at T.** $\sum_w \Delta\,\mathrm{own}(u_{\mathrm{XYZ}}) = 0$ and $\sum_w \Delta\,\mathrm{own}(\mathrm{USD}) = 0$. The market-proxy wallet `w_market_proxy[CP_A]` is the standard counterparty-side virtual wallet of v10.3 §2.5; its T+2 settlement is precisely the act of replacing the proxy edge with a custodian/CSD-side reality.

**There is no "pending" or "unsettled" coordinate** in the position vector. The position is the position. The pendingness of the *external* transfer is captured by the obligation's state field, not by the position arithmetic. This is the design that makes deferred settlement work as a thin layer on top of v10.3.

### 2.2 T (post-trade, asynchronous) — SubmitToCSD

```
ExecutorCommit(state-only):
    StateDelta: obligation[SO:...].state = PENDING_INSTRUCT -> INSTRUCTED
    StateDelta: instance[I_0] = SettlementInstance(submitted_at=now(), iso_hash=h)
```

This commit is driven by the saga workflow. Note: it is a *state-only* transaction. No moves. The economic position never moves between trade and CSD finality.

### 2.3 T+1 — Affirmation, allocations, intra-day status updates

If allocations or affirmation messages flow back, each is recorded as a state-only transaction updating obligation metadata. None of this changes the trade-date moves. If a partial-allocation event splits the obligation into two, this is two new `SettlementObligation` rows (with derived IDs) and a CORRECTION-style state-only transaction marking the original as `SUPERSEDED_BY [SO:..., SO:...]`. Conservation is trivial — only state changes.

### 2.4 T+2⁻ — The boundary just before finality

State at this instant: obligation row says `INSTRUCTED`. Position vector says +100 XYZ, -5000 USD. Nostro says: 0 XYZ delivered, 0 USD paid. **The discrepancy is the settlement obligation, materialised exactly.**

The reconciliation identity must hold at this instant (see §4):

$$
w_{\mathrm{nostro}}(u) \;+\; \sum_{\substack{o \in \mathcal{O} \\ o.\text{state} \in \{\text{INSTRUCTED, PENDING\_INSTRUCT}\} \\ o.\text{leg.unit} = u}} \mathrm{net}(o, w_{\mathrm{book}}) \;=\; w_{\mathrm{book}}(u)
$$

In words: book position = nostro position + algebraic sum of pending obligations. Lead-lag is **exactly the obligation set**, with no slop.

### 2.5 T+2⁺ — CSD finality message arrives

```
Transaction(type=SETTLEMENT, tx_id', ts=T+2, status=SETTLED, related_to=tx_id):
    -- THIS TRANSACTION HAS NO MOVES TO THE BOOK WALLETS.
    -- The book position was correct from T.
    -- Only the proxy/nostro split changes.
    Move(from=w_market_proxy[CP_A] ,  to=w_nostro_csd  ,  unit=u_XYZ ,  qty=+100)   -- nostro materialisation
    Move(from=w_nostro_csd          ,  to=w_market_proxy[CP_A] ,  unit=USD ,  qty=-5000)
    StateDelta: obligation[SO:...].state = INSTRUCTED -> SETTLED
    StateDelta: obligation[SO:...].finality_event = sese025_envelope
```

**The book position is unchanged.** What changes is which virtual wallet holds the offsetting position: at T it was the counterparty proxy; at T+2 it is the nostro proxy. Conservation holds in the second transaction independently — the proxy-to-nostro substitution is itself a zero-sum move, and the cash leg mirrors it.

This is the cleanest representation: **the T+2 transaction is a move *between virtual wallets*, never between the book wallet and a virtual wallet.** The book wallet's position is untouched.

### 2.6 Variant: Fail at T+2

```
Transaction(type=ACCOUNTING, ts=T+2, status=FAILED):
    -- No moves. Still no moves.
    StateDelta: obligation[SO:...].state = INSTRUCTED -> FAILED
    StateDelta: obligation[SO:...].fail_reason = INSUFFICIENT_SECURITIES
```

The book position remains +100 XYZ, -5000 USD — economically correct. The proxy wallet still carries the offsetting position. Reconciliation against nostro now shows a deficit *equal to the obligation*; the obligation row makes that deficit explicit and addressable.

---

## 3. Invariants

Five invariants characterise the deferred-settlement representation. The first is the mandatory economic-exposure-at-T invariant.

### 3.1 I-DS-1 — Economic-exposure-at-T (MANDATORY)

For every executed trade with `business_event_id = e`, executed at time $T$ with settlement date $t_s > T$:

$$
\forall t \in [T, t_s] \cup [t_s, \infty) : \quad w_{\mathrm{book}}(u) \;\big|_t \;=\; w_{\mathrm{book}}(u) \;\big|_T
$$

The book position at any time after $T$ equals the book position at $T$, regardless of the settlement outcome. **Settlement does not move the book.** A failed settlement does not "back out" the position. A successful settlement does not "create" the position. The position was created at $T$ and is not touched by any settlement-finality event.

This is the invariant that defines trade-date accounting. Every other rule must be consistent with it.

### 3.2 I-DS-2 — Conservation per transaction (inherited)

Each transaction at T, T+1, T+2⁻, T+2⁺ independently satisfies $\sum_w \Delta\,w(u) = 0$ for every unit. This is v10.3 P1 applied per transaction.

### 3.3 I-DS-3 — Obligation completeness

For every executed `SETTLEMENT`-typed transaction at T whose `cdm_payload.settlement_date > T`, an obligation row exists with derived ID `SO:hash(business_event_id, leg)`. No obligation is implicit. (This is v10.3 §13.2.5 Obligation Completeness Principle, narrowed to settlement.)

### 3.4 I-DS-4 — Obligation-FSM monotonicity (modulo loops)

The obligation FSM transitions only forward: `PENDING_INSTRUCT → INSTRUCTED → SETTLED | FAILED | PARTIAL`. From `FAILED` the only outgoing transitions are `FAILED → INSTRUCTED` (re-instruction after buy-in resubmission) and `FAILED → BUYIN → SETTLED | CANCELLED`. There is no path back to `PENDING_INSTRUCT` from any later state — re-submission creates a *new* `SettlementInstance` row, not an FSM regression.

### 3.5 I-DS-5 — Book/nostro reconciliation by lead-lag (see §4)

$$
w_{\mathrm{book}}(u) \;-\; w_{\mathrm{nostro}}(u) \;=\; \sum_{o \in \mathcal{O}_{\text{open}, u}} \mathrm{leg}(o, w_{\mathrm{book}}, u)
$$

The obligation set is *exactly* the lead-lag. If the equation does not balance, there is a break (in either direction).

---

## 4. Reconciliation — Lead-Lag by Design

The reconciliation between book (Ledger) and nostro (custodian/CSD authoritative record) is not an audit pass; it is an **algebraic identity** that holds at every instant.

```
For every (book wallet w_book, unit u, time t):
    w_book(u, t)  ==  w_nostro(u, t)  +  sum over open obligations o of leg(o, w_book, u)
```

**Where:**
- `w_book(u, t)`: the Ledger's book position at time t.
- `w_nostro(u, t)`: the corresponding nostro wallet position at time t (a virtual wallet mirroring the custodian's record).
- `sum`: signed by direction of the obligation. A buy obligation contributes positively (the book carries a security claim that hasn't materialised), a sell obligation negatively.

This identity is testable as a property:

```python
@property_test
def lead_lag_holds(t: Timestamp):
    for (w, u) in book_wallets:
        book_qty   = ledger.position(w, u, at=t)
        nostro_qty = ledger.position(nostro_wallet_for(w), u, at=t)
        oblig_qty  = sum(o.leg_signed(w, u) for o in open_obligations(w, u, at=t))
        assert book_qty == nostro_qty + oblig_qty
```

**Why this matters:** in many production systems, "book vs custodian reconciliation" is a daily operations process that produces breaks, ages them, escalates them. In this design, breaks are *defined* as violations of the identity — and because the obligation set is generated atomically with each trade, a break can only mean (i) a CSD finality event has been recorded but the obligation FSM not advanced, (ii) an obligation was created without a matching trade leg (impossible under I-DS-3), or (iii) the nostro wallet diverged from the custodian's actual record (a real ops break).

This is the v10.3 §13.4 "Reconciliation Failure Taxonomy" specialised to settlement.

### 4.1 What changes at T+2⁺ on success

At the moment the CSD finality is recorded:

- `obligation.state: INSTRUCTED → SETTLED` (the obligation leaves the open set)
- `w_market_proxy[CP_A](u)` decrements by +100 (offsetting was here; now it isn't)
- `w_nostro_csd(u)` increments by +100 (offsetting is now here)

The identity continues to hold. Both sides decreased their pending-obligation contribution by 100 and both sides updated their corresponding wallets. The book wallet did not move.

### 4.2 What changes at T+2⁺ on fail

- `obligation.state: INSTRUCTED → FAILED` (the obligation **stays in the open set** for reconciliation purposes — `FAILED` is a member of the open set, it just has different escalation properties)
- No wallet moves.

The identity continues to hold trivially. The lead-lag is unchanged because the obligation is still open.

### 4.3 What changes at the buy-in cutoff

- `obligation.state: FAILED → BUYIN` (state-only)
- A *new* trade transaction is generated by the BuyInWorkflow on a different counterparty. This new trade has its own `business_event_id`, its own obligation row, its own T+2 settlement timeline. It replaces the original obligation's economic substance via a CORRECTION transaction that pairs the cancellation of the original obligation with the booking of the new one. Conservation holds in each transaction independently.

---

## 5. CDM Cross-Walk

| Phase                       | CDM construct                                          | Notes                                                  |
|-----------------------------|--------------------------------------------------------|--------------------------------------------------------|
| T trade                     | `BusinessEvent` with `ExecutionPrimitive`, `TradeState` ACTIVE | Direct                                                 |
| Obligation registration     | None — Ledger-internal                                 | **CDM gap** (settlement-failure orchestration is not modelled comprehensively in CDM 6.0.0) |
| Settlement instruction      | `SettlementInstruction` (extracted from trade `TradeState`) → ISO 20022 `sese.023` | Direct via the synonym layer                                          |
| Affirmation / allocation    | `BusinessEvent` with `AllocationPrimitive`             | Direct (state changes only)                            |
| Finality (success)          | `BusinessEvent` with `TransferPrimitive`, status SETTLED | Direct                                                 |
| Finality (fail)             | None — Ledger-internal status code                     | **CDM gap** — propose `SettlementFailureEvent` extension |
| Partial settlement          | `BusinessEvent` with `PartialPrimitive` (CDM 6.x)      | Partial — schema is present but workflow not          |
| Buy-in                      | None — covered by external `ContractFormation` only    | **CDM gap** — already noted in v10.3 Table at §13.13   |
| Cancellation                | `BusinessEvent` with `CancelPrimitive`                 | Direct                                                 |

The three CDM gaps (settlement-failure orchestration, mandatory buy-in primitive, formal partial-settlement workflow) are precisely those flagged in v10.3 §13.13. This proposal does not introduce new gaps.

---

## 6. Failure Modes per Case (the floor cases)

### 6.1 CORE — buy T+2

Standard path. T trade → T+2 finality → SETTLED. Covered above.

### 6.2 CORE — sell T+2

Symmetric. The obligation's `legs[SecuritiesLeg]` carries direction `DELIVER`; `legs[CashLeg]` direction `RECEIVE`. The lead-lag identity sign flips for the sale leg. Otherwise identical.

### 6.3 CORE — buy T+1

The settlement-date field is T+1, not T+2. The Temporal timer fires one day earlier. **No representational change.** The obligation FSM, the lead-lag identity, the move sequence are unchanged. This is the desired degeneracy: T+1 vs T+2 vs T+0 vs T+5 are scheduling parameters, not representational distinctions.

### 6.4 CORE — fail (CSDR)

`obligation.state: INSTRUCTED → FAILED` at T+2. Position remains. The CSDR penalty (cash penalty per business day past intended settlement date, currently EUR-area) is computed by a separate `CsdrPenaltyWorkflow` reading the obligation's age and emitting an accruing accrual transaction. The mandatory buy-in cutoff (T+2 + 4 b.d. for liquid, T+2 + 7 b.d. for illiquid) is a deadline carried on the obligation; when the deadline timer fires, the buy-in saga (§7.4) starts.

### 6.5 CORE — partial settlement

CSD reports 60 of 100 delivered. The saga splits the obligation into two rows:
- `SO:original` → `state: PARTIAL`, with `legs.qty = 60`, transitions to `SETTLED`
- `SO:remainder` → newly created with `state: INSTRUCTED`, `legs.qty = 40`, fresh deadline

Two CSD finality events will eventually be recorded, one per child obligation. The lead-lag identity continues to hold because the sum of child legs equals the parent leg. Conservation is preserved transaction-by-transaction; the split is itself a state-only transaction.

### 6.6 CORE — recon

Reconciliation is the lead-lag identity (§4). Breaks materialise as `BreakRecord` rows in the BreakRegister (data spec L18) with type `wf-settlement-break`. Aging timers run independently of the obligation FSM; an aged-out break escalates to manual ops.

### 6.7 COMPOSITION — short (§13)

Selling a borrowed position. The trade transaction at T modifies `onloan` and `borr` coordinates (per the Single-Coordinate Move Principle). The obligation that arises is on the borrowed unit, with a delivery date driven by the shorter SBL recall window (T+2 calendar regardless). The settlement obligation is a **separate row** from the SBL recall obligation; they are linked by `obligation.related_to` but tracked by different sagas (`SettlementSaga` vs the `SBLLoanWorkflow` in v10.3 §13.5). This separation is essential — collapsing them would conflate two distinct deadlines and two distinct compensation actions.

### 6.8 COMPOSITION — recall

A recall during the T-to-T+2 window. The recall is a signal to the SBL workflow; it produces a return obligation with its own deadline (typically T+2 from recall date). If the borrowed position has been onward-sold, the seller has both a delivery obligation (settlement saga) and a recall obligation (SBL saga); both must discharge by their own deadlines. Failure of either triggers buy-in independently.

### 6.9 COMPOSITION — corporate action

A corporate action with record date inside the T-to-T+2 window. The CDM `CorporateActionEvent` carries the entitled-holders snapshot taken on record date. Trades whose settlement has not occurred by record date are governed by market convention: the buyer is generally entitled (cum-dividend through to ex-dividend date); the obligation row's `legs` are augmented with a manufactured-payment leg (per v10.3 §13.5 SBL manufactured-dividend pattern, here applied between the trading parties via the CSD's claims process). The point: the obligation's leg set can grow as corporate actions land on it. The FSM is unchanged.

### 6.10 COMPOSITION — cross-currency (Herstatt)

A cross-currency trade has two cash legs in two currencies, settling in two CSDs/payment-systems with different cut-off times. The Herstatt risk — the risk that you pay out in Tokyo before you receive in New York — is handled by **two obligation rows** for the same trade, each with its own settlement-date and finality timer. CLS-eligible currency pairs collapse to a single PvP obligation; non-CLS pairs remain two independent obligations. The book position at T already reflects both legs (conservation); the Herstatt risk is an *operational* risk on the open obligation set, surfaced as a `herstatt_exposure` projection over `SettlementObligation` (one cash leg `SETTLED`, the matching cash leg still `INSTRUCTED`).

### 6.11 COMPOSITION — DvP atomicity

Internal DvP atomicity is guaranteed at T by the executor's transaction primitive (v10.3 §2.4). External DvP atomicity is guaranteed at T+2 by the CSD (DTC, Euroclear, Clearstream). The deferred-settlement representation does not weaken either guarantee: the T transaction is atomic; the T+2 finality message asserts CSD-side DvP and updates both legs' obligation rows in a single ledger transaction.

---

## 7. The Settlement Saga — Concrete Workflow Code

### 7.1 Workflow boundary — what is in Temporal vs. what is in the Ledger

**In the Ledger (no Temporal needed):**
- The trade transaction at T (atomic, executor-committed).
- The obligation row registration (atomic with the trade).
- All state-only transactions advancing the obligation FSM.
- The lead-lag reconciliation identity (a pure algebraic property over the ledger).
- The corrections / anti-moves on cancellation.

**In Temporal (saga orchestration):**
- The wait for the CSD finality message (durable, may span days).
- The deadline timer for buy-in cutoff.
- The retry loop on transient submission failures.
- The split of partial settlements into child obligations.
- The escalation tower (settlement → buy-in → terminal default).
- The CSDR penalty accrual scheduled workflow.
- The cross-saga coordination (settlement × SBL, settlement × corporate action).

The decisive boundary: **the move sequence is in the Ledger; the orchestration that decides which moves to commit and when is in Temporal.** This is consistent with v10.3 §10.3 ("two audit trails"), and with my prior project memory's Class-of-three taxonomy (`Definitions` / `Observations` / `Effects` — settlement obligations are `Effects`).

### 7.2 The saga, end-to-end

```python
@workflow.defn
class SettlementSaga:
    """
    One saga per (business_event_id, leg_index).
    Workflow ID: "SET:" || obligation_id   (= "SET:SO:" || hash_jcs(business_event_id, leg))
    Idempotent on start by workflow ID.
    """

    @workflow.run
    async def run(self, payload: SettlementSagaInput) -> None:
        # ---------------------------------------------------------------
        # State that survives ContinueAsNew. Frozen schema, versioned.
        # ---------------------------------------------------------------
        self.obligation_id      = payload.obligation_id
        self.attempt_seq        = payload.attempt_seq           # carries across CAN; never run_id
        self.processed_signals  = bounded_dedup_set(payload.processed_signals, n=4096, ttl_days=30)
        self.cdm_v              = payload.cdm_v
        self.canonicalisation_v = payload.canonicalisation_v

        # ---------------------------------------------------------------
        # Step 1 : Project + enrich + submit.
        # ---------------------------------------------------------------
        # Activities; all I/O is here.
        # Idempotency keys: tx_id is content-addressed on (business_event_id, attempt_seq).
        instruction = await wf.execute_activity(
            settle_projection,
            args=[self.obligation_id],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(initial_interval=timedelta(milliseconds=500),
                                      backoff_coefficient=2.0,
                                      maximum_attempts=10,
                                      non_retryable_error_types=["ProjectionError"]))
        enriched   = await wf.execute_activity(enrich_with_ssi, instruction, ...)
        iso_msg    = await wf.execute_activity(generate_sese023, enriched, ...)
        ack        = await wf.execute_activity(submit_to_csd, iso_msg,
                       start_to_close_timeout=timedelta(seconds=30),
                       heartbeat_timeout=timedelta(seconds=10))

        # Advance obligation FSM atomically via executor activity.
        await wf.execute_activity(
            executor_advance_state,
            args=[self.obligation_id, "PENDING_INSTRUCT", "INSTRUCTED",
                  SettlementInstance(csd_ref=ack.csd_ref, iso_hash=hash_jcs(iso_msg))],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(non_retryable_error_types=[
                "ConservationViolation", "FsmIllegalTransition", "IdempotencyRejection"]))

        # ---------------------------------------------------------------
        # Step 2 : Wait for finality OR T+2 cutoff.
        #
        # Pattern: signal-driven workflow with timer. NOT a long-running
        # heartbeating activity. (Heartbeating a 24-72-hour activity is
        # an anti-pattern; ref. agent memory ledger_v11_temporal v2.)
        # ---------------------------------------------------------------
        finality_ch  = wf.signal_channel("csd_finality")     # sese.024 / sese.025
        partial_ch   = wf.signal_channel("csd_partial")      # partial fill
        ops_ch       = wf.signal_channel("ops_override")     # manual ops bypass

        finality: Optional[FinalityEvent] = None
        async with wf.with_deadline(payload.t_settle):
            try:
                async with wf.select() as sel:
                    sel.on(finality_ch.recv,  lambda e: e if self._dedup(e) else None)
                    sel.on(partial_ch.recv,   lambda e: e if self._dedup(e) else None)
                    sel.on(ops_ch.recv,       lambda e: e if self._dedup(e) else None)
                    finality = await sel.first()
            except wf.DeadlineReached:
                pass    # we will check status with the CSD below

        # Reached settlement date with no signal -> poll the CSD ourselves.
        if finality is None:
            csd_status = await wf.execute_activity(
                query_csd_status,
                args=[ack.csd_ref],
                start_to_close_timeout=timedelta(seconds=15))
            finality = FinalityEvent.from_csd_status(csd_status)

        # ---------------------------------------------------------------
        # Step 3 : Branch on finality outcome.
        # ---------------------------------------------------------------
        match finality.kind:
            case FinalityKind.SETTLED:
                await self._record_settled(finality)
                return

            case FinalityKind.PARTIAL:
                await self._split_obligation(finality.delivered_qty)
                # Spawn a child saga for the remainder; this saga records the partial and exits.
                await wf.start_child_workflow(
                    SettlementSaga,
                    args=[SettlementSagaInput.for_remainder(self.obligation_id, finality)],
                    id="SET:" + remainder_obligation_id(self.obligation_id),
                    parent_close_policy=ParentClosePolicy.ABANDON)
                return

            case FinalityKind.FAILED:
                await self._record_failed(finality)
                # Hand off to BuyInWorkflow as a child (compensation tier 1 per memory).
                # BuyInWorkflow has its own deadline budget (T+2 + 4 or 7 b.d.).
                await wf.start_child_workflow(
                    BuyInWorkflow,
                    args=[BuyInInput(self.obligation_id, finality.fail_reason,
                                     deadline=payload.buyin_deadline)],
                    id="BUY:" + self.obligation_id,
                    parent_close_policy=ParentClosePolicy.ABANDON)
                return

    # ----- helpers (omitted: _dedup, _record_settled, _record_failed,
    #                          _split_obligation, lookup activities)
```

### 7.3 The fail-then-buy-in path

```python
@workflow.defn
class BuyInWorkflow:
    """
    Compensation Tier 1 for a failed settlement obligation.
    Deadline budget: from T+2 to buyin_deadline (4 or 7 business days, CSDR).
    """

    @workflow.run
    async def run(self, payload: BuyInInput) -> BuyInResult:
        deadline = payload.deadline

        # Step 1: Issue the buy-in to a buy-in agent via the CCP/CSD.
        bi_ref = await wf.execute_activity(
            issue_buyin_request,
            args=[payload.obligation_id, payload.fail_reason],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=5))

        await wf.execute_activity(
            executor_advance_state,
            args=[payload.obligation_id, "FAILED", "BUYIN", BuyInInstance(bi_ref=bi_ref)])

        # Step 2: Wait for buy-in agent confirmation OR deadline.
        bi_confirm_ch = wf.signal_channel("buyin_confirm")

        try:
            async with wf.with_deadline(deadline):
                confirm = await bi_confirm_ch.recv()
                if not self._dedup(confirm):
                    confirm = await bi_confirm_ch.recv()
        except wf.DeadlineReached:
            # Late-discharge race policy for buy-in: REJECT (deadline sacrosanct).
            # Escalate to Tier 2 escalation workflow.
            await wf.start_child_workflow(
                BuyInEscalationWorkflow,
                args=[payload.obligation_id, "BUYIN_DEADLINE_BREACH"],
                id="ESC:" + payload.obligation_id)
            return BuyInResult.failed("deadline")

        # Step 3: Buy-in succeeded. Book the new trade against the buy-in agent;
        # cancel the original obligation; record the cost differential.
        new_tx = await wf.execute_activity(
            book_buyin_replacement_trade,
            args=[payload.obligation_id, confirm])
        await wf.execute_activity(
            executor_advance_state,
            args=[payload.obligation_id, "BUYIN", "CANCELLED", confirm])
        await wf.execute_activity(
            attribute_buyin_costs,
            args=[payload.obligation_id, confirm.cost_differential])
        return BuyInResult.success(new_tx.tx_id)
```

### 7.4 The CSDR penalty accrual

A separate scheduled workflow runs daily at the CSDR penalty cut-off, queries all obligations in `FAILED` state aged > 0 b.d., and emits an accrual transaction per obligation. This is a fan-out scheduled workflow (Temporal Schedule, overlap policy `Skip`) and is independent of the main saga — it must not block or be blocked by the saga's progress.

---

## 8. Concrete Replay-Determinism Risk Register for Settlement

From my agent memory's risk register, the items that bite settlement specifically:

| Risk | What goes wrong | Mitigation |
|---|---|---|
| `tx_id` formed from `run_id` | ContinueAsNew issues new `tx_id` for same logical event → executor double-commits | `tx_id = hash_jcs(business_event_id, attempt_seq)`. `attempt_seq` survives CAN. **Critical.** |
| Wall-clock reads in workflow code | Replay produces different timestamp on CSD-status query | All clock reads via activity (`now()` is an activity, not `workflow.Now()` for any externally-observable timestamp). Use `workflow.Now()` only for deterministic *durations*. |
| Live calendar read on replay | `t_settle = T + 2 b.d.` becomes stale-different if calendar amended | Calendar resolved once at `register_obligation`, pinned in `SettlementObligation.settlement_date`. Calendar amendment is a `RestatementWatchWorkflow` event, not a re-read. |
| Signal idempotency dedup unbounded | `processed_signals` set grows over multi-day saga | Bounded set (n=4096, 30-day TTL) + out-of-workflow dedup table for high-cardinality endpoints. |
| Long wait on CSD as activity-with-heartbeat | Worker drain on deploy times out activity, retry doesn't replay correctly | Use signal-driven workflow with timer (as written above). Never heartbeat a 24-hour activity. |
| ContinueAsNew during multi-day wait | Naive CAN drops in-flight finality signal | CAN payload schema includes `processed_signals` and `attempt_seq`; explicit unit test on CAN-then-signal scenario. |
| Cross-saga coordination (settlement × SBL) | Two workflows, one obligation, ordering surprises | Each saga owns its obligation; cross-references go via `related_to` field; signals between sagas carry monotonic sequence numbers, sorted at receiver. |

---

## 9. Visibility / Search Attributes — How Ops Asks "What's Failing Today?"

Each `SettlementSaga` workflow declares the following Temporal search attributes:

```
obligation_id        : keyword
business_event_id    : keyword
counterparty_lei     : keyword
csd                  : keyword             # DTC | Euroclear | Clearstream | ...
currency             : keyword             # USD | EUR | GBP | JPY | ...
settlement_date      : datetime
buyin_deadline       : datetime
state                : keyword             # PENDING_INSTRUCT | INSTRUCTED | ...
fail_reason          : keyword             # nullable
notional_usd         : double              # for prioritisation
```

Operations queries become:

```
WorkflowType = "SettlementSaga" AND state = "FAILED" AND settlement_date <= today
WorkflowType = "SettlementSaga" AND state = "INSTRUCTED" AND settlement_date < yesterday
WorkflowType = "SettlementSaga" AND counterparty_lei = "..." AND state IN ("FAILED", "PARTIAL")
WorkflowType = "BuyInWorkflow" AND ExecutionStatus = "Running"
```

This is what makes the obligation set *queryable* without bringing the application database into the operations dashboard. The same search attributes are surfaced in Grafana via the Temporal Visibility API.

**Do not encode mutable economic state in search attributes** — they are denormalised, eventually consistent, and not authoritative. The authoritative state is the obligation row in the ledger event log; search attributes are for operational filtering only.

---

## 10. Worker Architecture for Settlement

From the v2 14-queue topology in agent memory, the settlement-relevant queues are:

| Queue                        | Workers                                              | Scaling driver                       |
|------------------------------|------------------------------------------------------|--------------------------------------|
| `wf-settlement`              | `SettlementSaga`, `BuyInWorkflow`, escalation tower  | Daily settlement volume              |
| `act-settlement-csd-io`      | `submit_to_csd`, `query_csd_status`, ISO 20022 gen   | CSD throughput, network              |
| `act-executor-state-only`    | `executor_advance_state` for status transitions      | Transaction throughput; CPU-bound    |
| `act-projection`             | `settle_projection`, `enrich_with_ssi`               | Trade volume; CPU-bound              |
| `wf-csdr-penalty`            | Daily cron-scheduled penalty accrual workflow         | EU regulatory volume                  |

**The decision to shard:** a single global namespace (memory: v2 namespace ruling). Sharding within is by *workflow ID prefix* — the `"SET:"` prefix routes to settlement workers; a high-volume CSD does not co-mingle with low-volume markets. Crucially, **do not shard by counterparty** — counterparty distributions are heavy-tailed and shard skew is severe. Shard by CSD (cleaner natural distribution) and use Temporal's built-in workflow cache stickiness for warm-replay.

---

## 11. Versioning — When CSDR Rules Change or T+1 Rolls Out

Two distinct version axes touch the settlement saga:

**Schedule axis:** T+2 → T+1 transition (US equities, May 2024; EU equities, October 2027). The settlement-date field is data, not code. A workflow that has already started under T+2 carries its T+2 deadline through to completion; new workflows started after the cutover use T+1. **No `GetVersion` gate is required** because the deadline is in the workflow input payload, not in the code.

**Logic axis:** CSDR penalty rate change, mandatory buy-in window change, fail-reason taxonomy expansion. These *are* code changes and require `GetVersion` gates:

```python
v = wf.get_version("settlement_buyin_window_v2", DefaultVersion, 1)
if v == DefaultVersion:
    deadline = settlement_date + 4_business_days     # legacy
else:
    deadline = settlement_date + 7_business_days_for_illiquid_else_4   # CSDR refit
```

Old `SettlementSaga` instances continue with their original logic until they `ContinueAsNew` past the gate. New starts use the new logic.

The naming convention from v2 agent memory is `gate_settlement_{logical_name}_v{n}`. Inventory of the gates pinned for settlement:

- `gate_settlement_buyin_window_v2`
- `gate_settlement_csdr_penalty_v3`
- `gate_settlement_partial_split_v1`

---

## 12. ContinueAsNew Discipline

A `SettlementSaga` typically runs 2–7 calendar days. History size is bounded — a few hundred events at most. **`ContinueAsNew` is not a normal-path concern for `SettlementSaga`.**

It *is* a concern for the long-running parents that this saga interacts with:
- `SBLLoanWorkflow` (covered in v10.3 §13.5)
- `RestatementWatchWorkflow` for calendar amendments (covered in v10.3 §13)
- `CsdrPenaltyAccrualWorkflow` (a long-running daily-cron parent that may live for years)

For the `CsdrPenaltyAccrualWorkflow`, the v2 ContinueAsNew payload schema is mandatory. It must carry: `last_processed_obligation_cursor`, `accrual_rate_table_version`, `cdm_v`, `canonicalisation_version`, `bounded_dedup`. Forgetting any of these is a silent state loss.

---

## 13. What Temporal Does Not Solve (be honest)

From my agent memory's awkward-fit list, the settlement-specific items:

1. **Cross-CSD PvP (Herstatt) coordination across non-CLS pairs.** Temporal can run two parallel sagas with cross-signals; it cannot make the actual cross-currency PvP atomic. CLS solves this externally; non-CLS pairs carry residual Herstatt risk that surfaces operationally as the `herstatt_exposure` projection, not as a Temporal feature.

2. **CSD finality message ordering across siblings.** If two trades on the same instrument settle close in time, the CSD may emit finality messages in either order. Each saga handles its own; the lead-lag identity is order-agnostic. But **do not** introduce cross-saga ordering invariants — Temporal does not give you that for free.

3. **The economic correctness of the compensation.** Temporal will run the `BuyInWorkflow` reliably. It has nothing to say about whether the buy-in is *the right compensation* for a particular failure type. That is contract logic in CDM and ISDA/GMSLA, not orchestration.

4. **Aged break aging policies.** The aging FSM (T+1, T+3, T+5 escalation) is a `BreakRegister` (data-spec L18) state machine. Temporal could implement it but the data-spec already has it; a separate `BreakAgingWorkflow` would duplicate state. Use the BreakRegister.

---

## 14. Worked Example — 100 XYZ @ \$50 → \$52, PnL = +\$200, no cash moved

**Setup.** Day T (Monday). Book wallet `w_book`, market proxy wallet `w_market_proxy`, CSD nostro wallet `w_nostro`. Settlement T+2 = Wednesday.

### T (Monday)

Trade transaction commits atomically:
```
tx_1 = Transaction(type=SETTLEMENT, ts=Mon 09:30, status=EXECUTED):
    Move(w_market_proxy[CP_A] -> w_book      , XYZ , +100)
    Move(w_book               -> w_market_proxy[CP_A], USD , -5000)
    Register obligation SO:1 (state=PENDING_INSTRUCT, t_settle=Wed)
```

Positions:
```
w_book        : XYZ +100, USD -5000
w_market_proxy: XYZ -100, USD +5000
w_nostro      : XYZ    0, USD     0
```

`SettlementSaga` started, workflow ID `SET:SO:1`.

### T (Monday, post-trade)

Saga runs `settle_projection → enrich → generate_sese023 → submit_to_csd`. Each is an activity. The CSD acknowledges with `csd_ref = REF12345`.

```
tx_2 = Transaction(type=ACCOUNTING, ts=Mon 09:31, status=INSTRUCTED):
    StateDelta: SO:1.state = PENDING_INSTRUCT -> INSTRUCTED
    StateDelta: SO:1.instances += [SettlementInstance(csd_ref=REF12345, ...)]
```

No moves. Position unchanged.

### T+1 (Tuesday): Mark-to-market — XYZ trades to \$52

This is *not* a settlement event. The valuation layer reads:
```
PnL_Mon_to_Tue = (P_Tue - P_Mon) × w_book(XYZ) = (52 - 50) × 100 = +200 USD
```

The PnL is real — the position has been on the books since Monday. **No cash has moved.** This is the entire point of trade-date accounting: economic recognition begins at T, not at T+2.

The saga is asleep, waiting on the `csd_finality` signal channel with a deadline of Wed.

### T+2 (Wednesday) — finality

The CSD sends `sese.025` confirming successful settlement. The signal handler activates:

```
signal csd_finality := FinalityEvent(kind=SETTLED, csd_ref=REF12345, ...)

tx_3 = Transaction(type=SETTLEMENT, ts=Wed 11:15, status=SETTLED, related_to=tx_1):
    Move(w_market_proxy[CP_A] -> w_nostro, XYZ , +100)
    Move(w_nostro -> w_market_proxy[CP_A], USD , -5000)
    StateDelta: SO:1.state = INSTRUCTED -> SETTLED
    StateDelta: SO:1.finality_event = sese025_envelope_pinned
```

Positions:
```
w_book        : XYZ +100, USD -5000   (unchanged from T)
w_market_proxy: XYZ    0, USD     0   (proxy retired)
w_nostro      : XYZ +100, USD -5000   (now matches custodian's record)
```

Conservation per transaction: $\sum_w \Delta\,\mathrm{own}(\mathrm{XYZ}) = 0$, $\sum_w \Delta\,\mathrm{own}(\mathrm{USD}) = 0$. Lead-lag identity at this instant: $\mathrm{w\_book}(\mathrm{XYZ}) - \mathrm{w\_nostro}(\mathrm{XYZ}) = 100 - 100 = 0$, and the open-obligation set is empty. The identity holds.

The saga workflow completes.

### Counter-factual: T+2 fail

If the CSD instead sends `sese.024` "fail":

```
signal csd_finality := FinalityEvent(kind=FAILED, fail_reason=INSUFFICIENT_SECURITIES)

tx_3' = Transaction(type=ACCOUNTING, ts=Wed 11:15, status=FAILED):
    StateDelta: SO:1.state = INSTRUCTED -> FAILED
    StateDelta: SO:1.fail_reason = INSUFFICIENT_SECURITIES
```

No moves. Position remains:
```
w_book        : XYZ +100, USD -5000   (unchanged from T)
w_market_proxy: XYZ -100, USD +5000   (proxy still bears the offsetting position)
w_nostro      : XYZ    0, USD     0
```

The lead-lag identity: $100 - 0 = 100$, and the open-obligation set carries one row with `legs[XYZ] = +100`. Identity holds.

PnL accounting on the fail day: the position is still on the books at \$52, so the cumulative PnL is +\$200. The settlement failure does not back out the PnL; the failure produces a *reconciliation break* (book has +100, custodian has 0) which is the obligation row, made explicit. No accounting reversal of any kind.

The `BuyInWorkflow` starts as a child saga, with its own deadline at T+2 + 4 b.d. (Tuesday of the next week).

---

## 15. Summary — The One-Sentence Answer

**The deferred-settlement representation is a `SettlementObligation` row written atomically with the trade transaction at T, advanced through a monotone FSM by a long-running `SettlementSaga` Temporal workflow, observed against the nostro wallet via an algebraic lead-lag identity that is *exactly* the open-obligation set, and discharged at T+2 by a virtual-wallet rotation that never moves the book wallet.** The economic position is true from T (I-DS-1, mandatory). The obligation is explicit (a typed object, queryable via Temporal search attributes). Reconciliation is by design (the lead-lag identity is property-testable). The mechanism degenerates to T+1, T+0, and same-day settlement without representational change. Failure is not rollback — it is FSM transition to `FAILED` with the position preserved and the saga handing off to `BuyInWorkflow` as compensation.

The move sequence lives in the Ledger. The saga lives in Temporal. They share an `obligation_id`, a `tx_id` algebra, and the discipline that **trade-date accounting and durable execution are the two halves of the same answer**.
