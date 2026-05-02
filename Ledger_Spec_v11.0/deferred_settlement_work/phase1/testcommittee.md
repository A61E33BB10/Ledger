# Phase 1 — TESTCOMMITTEE proposal: `deferredSettlement.tex`

**Author panel.** Beck, Hughes, Fowler, Feathers, Lamport.
**Brief.** Test-strategy sign-off for the Ledger v11.0 deferred-settlement extension.
**Stance.** Tests are normative. The behaviour of the deferred-settlement window between T and T+2 is defined by what the test suite refuses to accept, not by the prose.
**Independence.** Written without consulting any other Team A member.

---

## 0. Premise: what the test corpus must define

The deferred-settlement extension is the first place in v11.0 where four things diverge that the v10.3 spec keeps confounded:

1. economic recognition (T, instant)
2. position quantity in the GPM6 vector (T, instant)
3. external custody of the asset (T+2, asynchronous)
4. external availability of the cash (T+2, asynchronous, possibly asymmetric)

The v10.3 spec Q5 ("settlement failures handled without reversing positions") and §`sec:settlement-confirmation` (the `EXECUTED → INSTRUCTED → SETTLED|FAILED` lifecycle) gesture at this gap. They do not test it. The tests below are what fixes that.

The test suite exists to **make the gap a first-class object** rather than an afterthought of Q5.

---

## 1. State representation — what a test must be able to observe

Beck, Lamport, Feathers concur. Five observables. If the implementation does not expose all five, the suite cannot be written.

| Observable | Type | Where it lives (StatesHome ruling) | Test access |
|---|---|---|---|
| `econ_qty(w, u)` | Decimal | `PositionState[w, u].own` (six-coord; degenerate scalar for cash) | `view.position_state(w, u).own` |
| `pending_in(w, u)` | Decimal | `PositionState[w, u].pending_in` (NEW coord, additive) | `view.position_state(w, u).pending_in` |
| `pending_out(w, u)` | Decimal | `PositionState[w, u].pending_out` (NEW coord, additive) | `view.position_state(w, u).pending_out` |
| `obligation` | tuple | `L_15.Obligation`, kind `SettlementInstructionDelivery` | `obligation_store.get(o_id)` |
| `tx_status` | enum | `UnitStatus` projection on the trade unit | `view.trade_status(tx_id)` |

`pending_in`/`pending_out` are non-negative; conservation-by-class as in the StatesHome addendum's C2.

**Why two new pending coordinates rather than overloading `own`.** Beck ("the smallest test that doesn't lie"): if the test cannot distinguish "I own 100 shares, custody confirmed" from "I own 100 shares, custody pending" it cannot test the failure path. The test for `tx_status == FAILED` must be independent of the test for `econ_qty`, otherwise the two are entangled and a regression in one masks a bug in the other. **An independent test requires an independent observable.**

The `available_for_settlement(w, u) = own − onloan + borr − pending_out` projection is the test seam between economic-position invariants (Section 2 Layer A) and settlement-flow invariants (Layer B). This separation is what makes property-based tests over the two layers compose.

---

## 2. Move sequence and conservation — the smallest test that demonstrates a buy

### 2.1 Beck's walking-skeleton test (`test_buy_T2_happy_path_minimal`)

The smallest end-to-end test for the standard cash-equity buy. **One** assertion bundle per phase. No mocks.

```
def test_buy_100_xyz_at_50_T2_happy_path():
    # Given: a fresh ledger, two parties, prefunded cash
    L = Ledger.empty()
    L.seed(buyer_w,  USD, 5_000)
    L.seed(seller_w, XYZ, 100)

    # When: trade at T
    tx_T = L.execute_buy(buyer=buyer_w, seller=seller_w,
                         unit=XYZ, qty=100, price=50,
                         settle_date=T+2, type=DvP)

    # Then: at T (economic recognition)
    assert L.econ_qty(buyer_w, XYZ)     == +100   # ownership transferred
    assert L.econ_qty(seller_w, XYZ)    == -100   # i.e. own=0 after seed -100
    assert L.pending_in(buyer_w, XYZ)   == +100   # custody pending
    assert L.pending_out(seller_w, XYZ) == +100
    assert L.pending_out(buyer_w, USD)  == 5_000
    assert L.pending_in(seller_w, USD)  == 5_000
    assert L.tx_status(tx_T)            == EXECUTED
    assert L.conservation_holds()                  # P1
    assert L.economic_exposure_at_T(buyer_w, XYZ) == +100  # MANDATORY

    # When: T+1, market closes at $52
    L.advance_to(T+1); L.set_price(XYZ, 52)
    assert L.pnl(buyer_w) == +200                 # mark-to-market
    assert L.cash_moved(buyer_w) == 0             # NO cash movement yet

    # When: T+2 minus epsilon, instruction is sent
    L.advance_to(T2_minus); L.send_instruction(tx_T)
    assert L.tx_status(tx_T) == INSTRUCTED

    # When: T+2 plus epsilon, CSD confirms
    L.advance_to(T2_plus); L.receive_confirmation(tx_T, SETTLED)
    assert L.tx_status(tx_T)            == SETTLED
    assert L.pending_in(buyer_w, XYZ)   == 0       # pending cleared
    assert L.pending_out(seller_w, XYZ) == 0
    assert L.pending_out(buyer_w, USD)  == 0
    assert L.pending_in(seller_w, USD)  == 0
    assert L.econ_qty(buyer_w, XYZ)     == +100   # UNCHANGED across SETTLED
```

This test fits on one screen. **It is the specification of the standard buy.** Anyone reimplementing the deferred-settlement extension from this test alone will produce something correct; that is Beck's measure of normativity.

### 2.2 Move sequence (formal)

At T (single atomic transaction, satisfies StatesHome C2 and conservation P1):

```
τ_T = SETTLEMENT-class transaction with the following per-class deltas:
  Move 1: pending_out += qty  on (seller, sec)
  Move 2: pending_in  += qty  on (buyer,  sec)
  Move 3: own         -= qty  on (seller, sec)   # economic transfer at T
  Move 4: own         += qty  on (buyer,  sec)
  Move 5: pending_out += cash on (buyer,  ccy)
  Move 6: pending_in  += cash on (seller, ccy)
  Move 7: own         -= cash on (buyer,  ccy)   # economic recognition at T
  Move 8: own         += cash on (seller, ccy)

Per-class conservation (each unit independently):
  ΔΣ own(XYZ)         = -qty + qty   = 0   ✓ P1
  ΔΣ own(USD)         = -cash + cash = 0   ✓ P1
  ΔΣ pending_in(XYZ)  = +qty                ↑ asymmetric: not a conservation class
  ΔΣ pending_out(XYZ) = +qty                ↑ paired with pending_in by ε-test below
```

`pending_in` and `pending_out` are **not** independently conserved; they are co-conserved by the **mirror invariant** (Section 3, P_DS_2). This is the new structural fact the v10.3 invariant catalogue does not contain.

At T+2 plus (single atomic transaction, contract `SettlementConfirmation`):

```
τ_T2+ = LIFECYCLE-class transaction:
  Move 1: pending_out -= qty  on (seller, sec)
  Move 2: pending_in  -= qty  on (buyer,  sec)
  Move 3: pending_out -= cash on (buyer,  ccy)
  Move 4: pending_in  -= cash on (seller, ccy)
  status: INSTRUCTED → SETTLED

No move on `own`. **PnL is path-independent (P10) across settlement confirmation.**
```

The fail path replaces τ_T2+ with `SettlementFailure` which:
- transitions status to FAILED,
- creates a follow-on `Obligation` (kind `SettlementBuyIn`, deadline = T+2 + CSDR-extension),
- does **not** alter `own`,
- does **not** alter `pending_*` (the obligation persists until cured).

### 2.3 Ledger lead, custody lag — the variant table

| Variant | Move at T | Status path | Move at T+1 | Move at T+2- | Move at T+2+ | Tests |
|---|---|---|---|---|---|---|
| Buy T+2 happy | τ_T | EXEC→INST→SETTLED | none | send instr | clear pending | §2.1 |
| Sell T+2 happy | τ_T (mirror) | EXEC→INST→SETTLED | none | send instr | clear pending | mirror of §2.1 |
| T+1 happy | τ_T (settle_date=T+1) | EXEC→INST→SETTLED | clear pending | n/a | n/a | property test, generator parameterised on settle_date |
| Fail (CSDR) | τ_T | EXEC→INST→FAILED | none | send instr | obligation registered, pending retained | §6.1 |
| Partial | τ_T | EXEC→INST→PARTIAL | none | send instr | partial clear, residual pending, residual obligation | §6.2 |
| Reconciliation lag | τ_T | EXEC→INST→SETTLED | recon match | n/a | n/a | §4 |
| Short | τ_T with SBL borrow at T-ε | EXEC→INST→SETTLED | none | send instr | clear pending | §6.4 + SBL invariants |
| Recall during open window | τ_T + recall obligation | EXEC→RECALLED→INST→SETTLED | none | send instr | clear pending; recall discharged | §6.5 |
| Corporate action across window | τ_T at T, CA at T+1 | EXEC→INST→SETTLED-with-CA | apply CA on `own` | send instr | clear pending | §6.6 |
| Cross-currency Herstatt | τ_T | EXEC→INST→PARTIAL_LEG_SETTLED→SETTLED | none | send instr (sec leg) | sec leg cleared, cash leg time-zone lag | §6.7 |
| DvP CSD reject | τ_T | EXEC→INST→DVP_REJECTED | none | rejected | reverse instruction, pending retained | §6.8 |

Every row is a Beck-style walking-skeleton test (≤30 lines), plus a Hughes generator slot, plus a Lamport state-space coordinate. Coverage is checklist, not probabilistic.

---

## 3. Invariants — MANDATORY economic-exposure-at-T

Hughes, Lamport, Feathers, Fowler agree: this is the load-bearing invariant. Without it the v11.0 spec is descriptive, not normative.

### 3.1 The mandatory invariant

```
P_DS_1 (Economic Exposure at T):
  ∀ trade τ executed at time T,
  ∀ t ∈ [T, T+settlement_lag],
  ∀ p ∈ ValidPriceVector:
    pnl(buyer, t, p) - pnl(buyer, T, p_T)
      ≡ econ_qty(buyer, sec_of(τ)) · (p(sec) - p_T(sec))

  Equivalently: PnL between T and settlement is fully explained by
  (econ_qty at T) × (price change), with no contribution from pending_*.
```

This is the invariant that says **the trade-date accounting model is real, not a slogan**. It is checkable on every state in the property-based suite. It is the inverse of the most likely bug class: implementations that compute mark-to-market off `own + pending_in` ("settled position") rather than `own` ("economic position"), thereby overstating PnL during the open window.

### 3.2 The full invariant register

| ID | Name | Formal statement | Severity |
|---|---|---|---|
| **P_DS_1** | **Economic-exposure-at-T (MANDATORY)** | PnL between T and T+settle = `own × Δp`; `pending_*` contributes nothing to MtM | **CRITICAL** |
| P_DS_2 | Mirror conservation of pending | `Σ_w pending_in(w,u) = Σ_w pending_out(w,u)` for every unit, every t | CRITICAL |
| P_DS_3 | Pending non-negativity | `pending_in ≥ 0 ∧ pending_out ≥ 0` always | HIGH |
| P_DS_4 | Pending bounded by transaction history | `pending_*` at t equals the sum of unsettled SETTLEMENT moves intersecting t | HIGH |
| P_DS_5 | Settlement idempotency | A confirmation message applied twice (same `external_message_id`) has no incremental effect | CRITICAL (composes with P5) |
| P_DS_6 | Status monotonicity | EXECUTED ≼ INSTRUCTED ≼ {SETTLED, FAILED, PARTIAL}; no back-transitions except via explicit CORRECTION | HIGH |
| P_DS_7 | Failure non-reversal | A FAILED status does not trigger reversal of `own`; only an explicit CORRECTION can do so | CRITICAL |
| P_DS_8 | Obligation registration on fail | Every transition to FAILED registers exactly one obligation in `L_15` of kind `SettlementBuyIn` or `SettlementCancellation`, with deadline ≤ CSDR mandatory buy-in deadline | HIGH (composes with Λ_13) |
| P_DS_9 | Monotonicity of obligation through partials | A PARTIAL settlement of qty q' from total q reduces `pending_*` by exactly q' and the residual obligation has size exactly q − q'; sum of partial obligations equals original residual | HIGH |
| P_DS_10 | Replay determinism across the window | Replaying the move stream from T to T+2+ε with the same snapshot reproduces bit-identical state at every t (composes with Λ_8) | CRITICAL |
| P_DS_11 | DvP atomicity (ledger-level) | Every SETTLEMENT-type τ_T contains both the cash and the security legs in the same Transaction; no Transaction with only one of the two is admissible | HIGH |
| P_DS_12 | DvP atomicity (settlement-level) | The pair (sec_clear_tx, cash_clear_tx) at T+2+ either both apply or neither does (CSD-witnessed; the framework gracefully handles asymmetric confirmations as PARTIAL_LEG_SETTLED) | MEDIUM |
| P_DS_13 | Path-independence of PnL across the window | P10 (v10.3) holds without modification: PnL(T, T+2+) = V(T+2+) − V(T) regardless of how many partial fills, recalls, or status updates occur in between | CRITICAL (regression invariant) |
| P_DS_14 | No negative free balance during window | `own − onloan − pending_out ≥ 0` for every (w, u) at every t (this is the locate/inventory invariant extended for the open window; it is the safeguard against double-spending the same security through two T+2 sales) | CRITICAL |
| P_DS_15 | Available-for-settlement projection | `available_for_settlement(w,u) = own − onloan + borr − pending_out` is a definitional identity, not a stored coordinate | LOW (StatesHome C-discipline) |

`P_DS_1`, `P_DS_2`, `P_DS_5`, `P_DS_7`, `P_DS_10`, `P_DS_13`, `P_DS_14` are the seven CRITICAL invariants. **A counterexample to any of these is a CRITICAL severity defect.**

### 3.3 Hughes — property-based formulation with generators

```
Generator: TradeStream(seed: int, max_trades: int = 200)
  -- draw counterparty pair from a fixed pool of 8
  -- draw unit from CDM TransferableProduct ∪ {USD,EUR,JPY,GBP,CHF}
  -- draw qty ~ LogNormal(2, 1) clipped to [1, 10_000]
  -- draw price ~ LogNormal(4, 0.5)
  -- draw settle_date ∈ {T+0, T+1, T+2, T+3} (T+0 is "atomic settle" baseline)
  -- draw outcome ∈ {SETTLED, FAILED, PARTIAL(0.0, 1.0)}
  -- draw confirmation_delay ~ Exp(λ=1/4h)

@property
def conservation_holds(stream):
    L = Ledger.empty()
    for ev in stream:
        L.apply(ev)
        for u in L.units():
            assert sum(L.own(w, u) for w in L.wallets()) == 0     # P1
            assert sum(L.pending_in(w,u) for w in L.wallets()) \
                == sum(L.pending_out(w,u) for w in L.wallets())   # P_DS_2

@property
def exposure_at_T(stream, price_path):
    L0, L1 = Ledger.empty(), Ledger.empty()
    for ev in stream: L0.apply(ev); L1.apply(ev)
    for w in L0.wallets():
        # economic exposure should equal own only
        own_only_pnl = sum(L0.own(w,u) * (p1[u]-p0[u]) for u in L0.units())
        actual = L1.pnl(w, p0=p0, p1=p1)
        assert actual == own_only_pnl                              # P_DS_1

@property
def replay_determinism(stream, snapshot_id):
    s1 = run(stream, snapshot_id)
    s2 = run(stream, snapshot_id)
    assert canonical(s1) == canonical(s2)                          # P_DS_10

@property
def idempotency_of_finality(stream, dup_index):
    L = run(stream)
    L.apply(stream[dup_index])           # second application of same confirmation
    L.apply(stream[dup_index])           # third
    assert L.state == run(stream).state                            # P_DS_5

@property
def monotonicity_of_obligation_through_partials(trade, partials):
    sort(partials, by=time)
    L = run([trade] + partials)
    sum_partials = sum(p.qty for p in partials)
    final_obligation = L.obligation_residual(trade.id)
    assert final_obligation == trade.qty - sum_partials            # P_DS_9
    # Monotone: at every intermediate t, residual is non-increasing
    for t in checkpoints:
        clone = L.clone_at(t)
        assert clone.obligation_residual(trade.id) >= L.obligation_residual(trade.id)
```

### 3.4 Hughes — shrinking strategies

For each generator, the shrink lattice must reduce to the **simplest counterexample**:

- `TradeStream` shrinks to the smallest prefix that violates the postcondition; shrinking respects causal order (don't drop a confirmation while keeping its trade).
- `qty` shrinks to the smallest power-of-10 boundary (1, 10, 100, …); decimal precision shrinks last.
- `confirmation_delay` shrinks to 0 (the boundary case).
- `outcome` shrinks via the lattice SETTLED ≺ PARTIAL(½) ≺ FAILED (failures are "more interesting" than successes; the QuickCheck convention).
- `price_path` shrinks to constant prices except for one perturbation (so PnL bugs surface as `+0.01` deltas).

Hughes's rule: **the printed counterexample for a P_DS_1 violation should be at most three trades, two prices, and one confirmation event**. If shrinking does not deliver that, the generator is wrong.

---

## 4. Reconciliation lead-lag

The Ledger leads custody by ≤ T+2; reconciliation between Ledger virtual wallets and CSD/custodian statements must therefore be **lead-lag aware**. Tests:

```
@property
def recon_lead_lag(stream, custodian_window):
    L = run(stream)
    custodian_state_at_t = simulate_custodian(stream, lag=custodian_window)
    for w_real, w_virtual in L.virtual_pairs():
        # Three-bucket recon: settled, in-flight, mismatch
        settled_match    = (L.own(w_real, u) - L.pending_in(w_real, u))
        in_flight_match  = L.pending_in(w_real, u)
        custodian_qty    = custodian_state_at_t.position(w_virtual, u)
        assert settled_match == custodian_qty            # external truth
        assert in_flight_match == sum_unsettled_in(L, w_real, u)
        # Mismatch bucket must be empty in the absence of injected faults
```

The reconciliation oracle is **not** "ledger == custodian"; it is "ledger.settled == custodian, ledger.pending == sum-of-instructions-not-yet-confirmed". Any test that uses the equal sign across the open window is wrong, and any implementation whose recon report uses the equal sign across the open window is wrong. **This is a regression seam Fowler insists on (§5).**

Fault-injection for reconciliation:

| Fault | Injected into | Expected behaviour |
|---|---|---|
| Custodian message lost | `sese.025` channel | After SLA timeout, status → STALE; obligation `RecaptureConfirmation` opened; recon flags `awaiting_confirmation`, not break |
| Custodian message duplicate | same | Idempotency on `external_message_id` (P_DS_5); no incremental state change |
| Custodian message out-of-order | same | The signal queue dedupes by `(tx_ref, sequence)`; reorders are absorbed into the workflow's selector |
| Custodian message retracted | corrective `sese.025` with `function = CANC` | Compensating CORRECTION; original confirmation lifecycle event remains in event log |
| CSD clock skew vs firm clock > 1s | `B_1` boundary | Replay determinism (P_DS_10) holds because `t_known` from `L_19` is captured, not wall-clock; tests validate that `t_obs` from CSD is recorded but never consumed by deterministic logic |
| CSD message arrives before our instruction is acknowledged | network reordering | Selector ordering is by `idempotency_key`, not arrival; test asserts state convergence regardless of arrival order |

---

## 5. CDM cross-walk — what the tests must check

CDM has the vocabulary; the tests must verify the **cross-walk is faithful**, not assumed.

| Ledger artefact | CDM artefact | Test |
|---|---|---|
| τ_T (atomic trade transaction) | `BusinessEvent` with primitive `Execution` | Round-trip: `cdm_to_ledger(ledger_to_cdm(τ_T)) ≡ τ_T` (modulo equivalence on metadata) |
| `pending_in/out` coordinates | (CDM gap — see below) | **Negative test**: a generator that produces `pending_in > 0` units that are not paired to any `Execution` event in CDM is rejected |
| `EXECUTED → INSTRUCTED` | `WorkflowStep` with `proposedEvent` populated | Mapping table tested by enumerating `WorkflowStep.action` |
| `INSTRUCTED → SETTLED` | inbound `sese.025` mapped to `BusinessEvent` with primitive `Transfer` | Round-trip; idempotency on `external_message_id` |
| `INSTRUCTED → FAILED` | inbound `sese.024`/CSDR notification mapped to `LifecycleOracle` event of kind `SettlementFailure` | Closed-sum extension test; new constructor `SettlementFailure` registered in `L_10` |
| Settlement obligation | Ledger-native `L_15.Obligation`, kind `SettlementBuyIn` | **CDM gap** — the suite asserts the gap is documented, not silently ignored |

Hughes's CDM-enum-as-generator convention: the `EventIntentEnum` set must include `SETTLEMENT_INSTRUCTION` and `SETTLEMENT_CONFIRMATION` for the generator to cover the open-window paths. **If the CDM enum is missing these, the suite has a documented coverage gap, not a passing test that means nothing.**

---

## 6. Failure modes — first-class tests

### 6.1 CSDR fail (`test_buy_T2_fail_csdr_buyin_path`)

```
def test_buy_T2_fail_csdr_buyin_path():
    L = setup_buy_100_xyz()
    L.advance_to(T2_plus); L.receive_confirmation(tx, FAILED, reason=COUNTERPARTY_NO_DELIVER)

    # Status
    assert L.tx_status(tx) == FAILED
    # Position UNCHANGED
    assert L.econ_qty(buyer, XYZ) == +100
    assert L.econ_qty(seller, XYZ) == -100
    # Pending RETAINED
    assert L.pending_in(buyer, XYZ) == 100
    assert L.pending_out(seller, XYZ) == 100
    # Obligation registered
    obs = L.obligations_for(tx)
    assert len(obs) == 1
    assert obs[0].kind == SettlementBuyIn
    assert obs[0].deadline == T2 + CSDR_BUYIN_EXTENSION  # 4 BD for liquid equities
    # Mark-to-market still uses econ_qty (P_DS_1)
    assert L.pnl(buyer) == 100 * (current_price - 50)
```

### 6.2 Partial settlement (`test_buy_T2_partial_then_buyin`)

Generator: total qty Q, partial fills at times t_1 < t_2 < ... < t_k with qtys q_1, ..., q_k summing to Q' < Q. Postcondition: at each t_i, `pending_in -= q_i`, residual obligation = Q − Σq_j (P_DS_9, monotone). The remaining `Q − Q'` is subject to buy-in at T+2+CSDR.

### 6.3 Recon mismatch (`test_recon_break_during_open_window`)

Inject a custodian count of `+99` against a Ledger `pending_in = 100`. Test: recon report flags **bucket** (which of settled / in-flight / mismatch); it must classify as MISMATCH only after the SLA window expires, not on first read.

### 6.4 Short sale composition (`test_short_sale_during_open_window`)

A short of 100 XYZ at T involves an SBL borrow at T-ε. Composition test: the GPM6 invariants P11–P20 must hold simultaneously with P_DS_1–P_DS_15. Specifically: `borr` is incremented at T-ε; `own` decremented at T (the sale); `pending_out` reflects the deliverable. The locate invariant (`avail ≥ 0`, P_DS_14) must hold across every state. **Test seam:** the SBL invariant suite and the deferred-settlement suite share a single conservation oracle.

### 6.5 Recall during the open window (`test_recall_during_open_window`)

A loan recall fired at T+1 on shares the lender has agreed to sell at T (with settlement at T+2): the recall obligation is registered, the cascade-recall sub-leaf (`L_6.2`) is engaged. Postcondition: the open-window settlement either completes from `borr` returning before T+2 or fails into the buy-in obligation lattice. **The two obligation types compose without violating Λ_13.**

### 6.6 Corporate action across the window (`test_dividend_during_open_window`)

Stock XYZ ex-div at T+1 with record date T+1. Two competing claims: the trade-date-accounting model says the buyer (long since T) is entitled; the legal-record-date model says the seller (still on register at T+1) is entitled until cash settlement T+2. The Ledger represents both: an internal economic-claim move at T+1, and an external claim-and-counter via a `manufactured_dividend` cash flow at T+2. **Test: the net cash flow to the buyer over T..T+3 equals the dividend, regardless of which mechanism delivers it.** This is the corporate action analogue of P_DS_1.

### 6.7 Cross-currency Herstatt (`test_fx_T2_herstatt_window`)

Buy 100 XYZ in EUR, with EUR cash leg settling in TARGET2 at 14:00 CET and USD cash leg (because the buyer is funded in USD) settling in Fedwire at 18:00 CET — these are not simultaneous. The Ledger represents this as a single SETTLEMENT τ_T (DvP at the security level) but with **two cash sub-legs**, each with its own `pending_*` and its own confirmation. Postcondition: between 14:00 and 18:00 CET on T+2, one cash leg is cleared and the other is not; the Ledger correctly records `PARTIAL_LEG_SETTLED`. The Herstatt window is a real risk that the test makes visible.

### 6.8 DvP CSD reject (`test_dvp_csd_rejects_instruction`)

The CSD (DTC, Euroclear) rejects the instruction at T+2-ε due to insufficient counterparty cash. Postcondition: status → DVP_REJECTED, **the instruction is reversed at the settlement layer**, but the Ledger position is unchanged (P_DS_7) and the CSDR fail clock starts.

---

## 7. Worked example

**Scenario.** Buy 100 XYZ at $50 on T. Price moves to $52 by T+1. Settle T+2 happy path.

| t | Event | `own(buyer, XYZ)` | `own(buyer, USD)` | `pending_in(b, XYZ)` | `pending_out(b, USD)` | `tx_status` | PnL | Cash moved |
|---|---|---|---|---|---|---|---|---|
| T-ε | Initial | 0 | 5_000 | 0 | 0 | — | 0 | 0 |
| T | Trade (τ_T atomic) | **+100** | **0** | **+100** | **+5_000** | EXECUTED | 0 | 0 |
| T+1 | Price → 52 | +100 | 0 | +100 | +5_000 | EXECUTED | **+200** | **0** |
| T+2− | Send instruction | +100 | 0 | +100 | +5_000 | INSTRUCTED | +200 | 0 |
| T+2+ | CSD confirms | +100 | 0 | **0** | **0** | SETTLED | +200 | (cash moved at custody, not in the buyer's pre-funded USD wallet — already debited at T) |

**The asserts:**

- `pnl == +200` ✓ — driven by `own × Δp`, not `(own + pending_in) × Δp` (P_DS_1).
- `cash_moved_during_T_to_T+1 == 0` ✓ — the buyer's `own(USD)` was debited at T economically, but the actual USD does not leave the firm's funding wallet until T+2 confirmation. (Implementation detail: the buyer's `own(USD)` going to 0 at T is correct under trade-date accounting; the `pending_out(USD) = 5_000` records the obligation to actually deliver the cash to the seller's funding wallet, which is settled at T+2.)
- conservation: `Σ own(XYZ) = 0`, `Σ own(USD) = 0`, `Σ pending_in = Σ pending_out` for both XYZ and USD at every t ✓.

Walking-skeleton test in §2.1 above is the executable form of this table. **The table and the test are the same artefact in two presentations.**

---

## 8. Testing-strategy sign-off

### 8.1 Beck — naming and the smallest test

Every test in the suite obeys a uniform name: `test_<actor>_<scope>_<scenario>_<outcome>`. Example: `test_buyer_T2_csdr_fail_buyin_path`. **No abbreviations.** A reviewer who doesn't know the codebase can read the name and the first 30 lines and know what is being asserted.

The smallest test that demonstrates the standard buy is §2.1: 30 lines, one screen, no mocks. **Anyone who proposes a test larger than that for the same scenario has not understood the scenario.** Any larger test in the suite is a sign of an unresolved design tension — it should be split.

### 8.2 Hughes — the property catalogue and shrinking

**Properties as the specification:** P_DS_1 through P_DS_15. Each has a formal generator (Section 3.3) and a shrink lattice (Section 3.4). The generator universe is finite-bounded (counterparty pool × CDM enum × outcome × delay); 100k+ random inputs per property per CI run.

**Shrinking minimality target:** every counterexample to P_DS_1 must shrink to ≤ 3 events. If a counterexample to P_DS_2 (mirror conservation) shrinks to a 50-event sequence, the generator is too coupled — fix the generator before shipping the property.

**Coverage criterion for the property suite:** combinatorial coverage of (settle_date × outcome × confirmation_delay × variant). With settle_date ∈ {T+0, T+1, T+2, T+3} (4), outcome ∈ {SETTLED, FAILED, PARTIAL_low, PARTIAL_high} (4), delay ∈ {0, normal, late, expired} (4), variant ∈ {buy, sell, short, recall, ca, fx, dvp_reject} (7), the combinatorial space is 448 cells. **Pairwise coverage** of these dimensions in 25 tests is the floor; full coverage in CI is 448 tests.

### 8.3 Fowler — refactoring safety and test seams

**The seam between v10.3 closed-system and the new mechanism is at the StateDelta boundary.** The deferred-settlement extension introduces two new coordinates (`pending_in`, `pending_out`) on `PositionState`, two new event-handler classes (`SettlementInstruction`, `SettlementConfirmation`), one new obligation kind (`SettlementBuyIn`), and one new lifecycle status path (`INSTRUCTED → PARTIAL_LEG_SETTLED → SETTLED`). The seam is: **all v10.3 tests must continue to pass without modification.** v10.3 tests that read `position(w, u).own` continue to read it; they never touch `pending_*`; therefore they cannot regress. Any v10.3 test that fails after the extension is a regression and the extension is wrong.

**Regression-prevention tests** (post-extension):

1. The existing 10 v10.3 invariants (P1–P10) — all must pass on the extended state. The extension adds rows (P_DS_*) but does not modify P1–P10.
2. The 10 SBL invariants (P11–P20) — must pass; deferred-settlement composes with SBL via the `borr` and `pending_out` interaction (§6.4).
3. The 3 obligation invariants (P21–P23) — must pass; the new `SettlementBuyIn` obligation kind extends the Λ_13 closure proof.

**Test pyramid shape.** The deferred-settlement suite is 60% unit (single move correctness, single status transition, generator-level invariants), 30% property (P_DS_1–P_DS_15), 8% integration (workflow + executor + obligation store, end-to-end against a real Temporal cluster), 2% characterisation/end-to-end (real custodian sandbox). **Anything heavier on integration than this means the unit/property tests are not load-bearing.**

### 8.4 Feathers — characterisation and silent assumptions

**Where does the existing v10.3 spec assume things the extension might silently violate?**

| v10.3 assumption (often implicit) | Risk under deferred settlement | Characterisation test required |
|---|---|---|
| `own(w, u)` is the position for valuation | If implementer "adds pending_in to own for risk display", P_DS_1 is violated | `test_v10_3_pnl_uses_own_only` — generates random states with non-zero pending and asserts PnL still tracks `own × Δp` |
| Reconciliation is "ledger == external" | Recon scripts assuming equality across the open window break | `test_v10_3_recon_uses_settled_bucket` — characterises the existing recon report shape and verifies it is upgraded, not bypassed |
| `clone_at(t)` returns a single state | With `pending_*`, replay must include obligation-store snapshots | `test_v10_3_clone_at_includes_obligations` — extension of P8/P_DS_10 |
| FAILED status reverses position (a frequent operator misconception) | Naive code does `if status==FAILED: undo_moves()` | `test_v10_3_fail_does_not_reverse_position` — asserts position unchanged on FAILED, MUTATION-tested by deliberately injecting a reversal and verifying the test catches it |
| The settlement projection reads only the transaction | Projection that reads `pending_*` from current state breaks idempotency | `test_v10_3_settle_projection_is_pure` — regression of the v10.3 §`sec:settlement-projection` purity claim |
| Q5 phrasing: "buy-in / partial / cancellation" is exhaustive | Implementer adds a fourth path ("hold-and-retry") that breaks Λ_13 | `test_v10_3_fail_resolution_is_closed_sum` — closed-sum gate, fails when a new resolution mode is silently added |

**Characterisation-test discipline.** Before any v10.3 file is modified to support the extension, the test suite must record the **current** behaviour of:
- `tx_status` lifecycle (its current set of valid transitions, even if incomplete),
- `Reconciliation Failure Taxonomy` outputs,
- the move sequences emitted by `equity_buy` and `equity_sell` smart contracts.

These characterisation tests pin down the v10.3 baseline. They are golden-file tests, not assertion tests — the goal is to detect any change, not to assert correctness. Once the extension lands, the golden files are diffed; reviewers approve diffs that correspond to deliberate extension behaviours and reject any other change.

### 8.5 Lamport — TLA+ and the open-window state machine

**The model.** Each (trade, leg) is a TLA+ process. Variables:

```
VARIABLES
    own,          \* function from (wallet, unit) to integer
    pending_in,   \* function from (wallet, unit) to non-negative integer
    pending_out,  \* function from (wallet, unit) to non-negative integer
    status,       \* function from tx_id to {EXEC, INST, SETTLED, FAILED, PART, REJ}
    obligation,   \* function from obligation_id to {PEND, DISCH, COMP, DEFAULT}
    clock         \* monotone integer
```

**Actions.** `Execute(tx)`, `SendInstruction(tx)`, `ReceiveConfirmation(tx, kind)`, `RegisterObligation(o)`, `DischargeObligation(o)`, `Compensate(o)`, `Tick`.

**Safety invariants** (the model checker must verify each, with the spec valid for `|W| ≤ 4, |U| ≤ 3, |trades| ≤ 6`):

- **Inv1 (Conservation):** `\A u \in U: SumOver(W, own(u)) = 0`
- **Inv2 (Mirror conservation):** `\A u \in U: SumOver(W, pending_in(u)) = SumOver(W, pending_out(u))`
- **Inv3 (Pending non-negative):** `\A w, u: pending_in(w,u) >= 0 /\ pending_out(w,u) >= 0`
- **Inv4 (Status monotonicity):** `[][status(tx)' ∈ Successors(status(tx))]_status` (a temporal safety property)
- **Inv5 (Failure-no-reversal):** `(status(tx)' = FAILED /\ status(tx) = INST) => own' = own` (no own-coordinate change on failure)
- **Inv6 (No double-spend):** `\A w, u: own(w,u) - pending_out(w,u) >= 0` (P_DS_14)

**Liveness invariants** (`<>` denotes "eventually"):

- **Live1 (Every instruction terminates):** `[]\A tx: status(tx) = INST => <>(status(tx) ∈ {SETTLED, FAILED, PART, REJ})`
- **Live2 (Every fail-obligation terminates):** `[]\A o: o.kind = SettlementBuyIn /\ o.state = PEND => <>(o.state ∈ {DISCH, COMP, DEFAULT})` (composes with Λ_13)
- **Live3 (No infinite stuttering of a single trade):** weak fairness on `ReceiveConfirmation` per tx.

**State-space sizing (Lamport's working number):** at `|W|=3, |U|=2, |trades|=4`, depth ≤ 8, the reachable state space is **estimated 10^5–10^6 states**, TLC-tractable on a workstation in minutes. Conservation and pending-mirror violations show up at depth ≤ 2; status-monotonicity violations at depth ≤ 4; liveness counterexamples at depth ≤ 8. **A spec that does not check these invariants in TLC is not specified, only described.**

The PlusCal version of the model (translated by the standard TLA+ tools) is the executable spec; it sits alongside the property tests in §3.3, and CI runs both. **TLA+ models the worst case across all schedules; property tests exercise the typical case across many random schedules. They are complementary, not redundant.**

---

## 9. Mutation testing — what survives the proposed suite

The Feathers/testcommittee threshold is **≥ 80% overall mutation score**, with category breakdowns:

| Mutation category | Expected score | Why the suite catches it |
|---|---|---|
| Sign / coefficient flip on quantity | 95% | Conservation P1, P_DS_2 |
| Boundary `>` ↔ `>=` on deadline | 75% | Need to add explicit boundary tests at `t = t_d` and `t = t_d − ε` (Hughes) |
| `pending_in` ↔ `pending_out` swap | 90% | P_DS_2 mirror catches; the few survivors are when the mirror holds by accident in symmetric scenarios |
| Drop a SETTLEMENT confirmation move | 85% | P_DS_5 idempotency catches some; status-monotonicity catches the rest |
| Reverse `own` on FAILED status | 99% | Dedicated test `test_fail_does_not_reverse_position` (Feathers); this one MUST score 100% |
| Replace `own` with `own + pending_in` in valuation | **target 100%** | P_DS_1 specifically targets this. **If this mutation survives, the suite is broken — the entire deferred-settlement extension's normative content is in this invariant.** |
| Off-by-one on partial-fill residual | 80% | P_DS_9 monotonicity-of-obligation-through-partials |
| Duplicate confirmation processing | 90% | P_DS_5 idempotency |
| Status FSM accepting back-transitions | 85% | P_DS_6 monotonicity (Lamport's Inv4) |
| Compensation handler returns null on a populated kappa-matrix entry | 70% | Needs explicit handler-totality test (StatesHome C9 + Λ_13) |

**Surviving-mutant categories the suite knowingly cannot catch (honest disclosure):**

- Mutations in code paths that depend on **wall-clock side effects** beyond the determinism boundary catalogue (`B_1`). E.g., a mutant that introduces a 200ms delay in instruction sending — undetectable as a unit/property test, requires production observability.
- Mutations that change **error message text** without changing semantics. The suite asserts on error class, not error string, deliberately.
- Mutations that introduce **race conditions across multiple Temporal workflow instances** — single-threaded handler discipline (B_15) prevents intra-handler races; cross-workflow races are a property-test scope gap covered only by the TLA+ liveness model.
- Mutations in the **serialisation/canonicalisation layer (`B_10`)** — the JCS-pinning test catches encoding mutations, but a mutation that corrupts a hash without changing its representation is invisible to test code.

These are the limits of the suite. **Coverage criteria honest about how much the suite can prove (Fowler's review gate):** 80% mutation, 100% on P_DS_1's targeted mutants, plus the four named gaps above. No more, no less.

---

## 10. Fault-injection scenarios specific to deferred settlement

Beyond the unit/property level, the suite must include integration-level fault-injection. Each scenario below has a named test and a named expected behaviour.

| Fault scenario | Injected at | Expected behaviour | Test |
|---|---|---|---|
| CSD `sese.025` lost | inbound message channel | After SLA, status → STALE; obligation `RecaptureConfirmation` opened | `test_csd_message_lost_within_sla`, `test_csd_message_lost_after_sla` |
| CSD `sese.025` duplicate | same | P_DS_5 idempotency on `external_message_id` | `test_csd_message_duplicate_idempotent` |
| CSD `sese.025` out-of-order (confirmation arrives before its prerequisite acknowledgement) | same | Workflow selector buffers and reorders by `idempotency_key`; final state convergent | `test_csd_message_out_of_order_converges` |
| CSD `sese.025` retracted via `function = CANC` | same | Compensating CORRECTION transaction; both events in event log | `test_csd_message_retracted_compensates` |
| Firm clock skewed +5s vs CSD clock | `B_1` | `t_known` from `L_19` snapshot is canonical; `t_obs` from CSD recorded but not consumed | `test_clock_skew_does_not_affect_replay` |
| CSD clock skewed +5s vs firm clock | `B_1` | Same; reconciliation flags the skew but does not break | `test_csd_clock_skew_logged_not_blocking` |
| Custodian batch arrives at T+2+ε with mixed SETTLED/FAILED outcomes for related trades | inbound | Each trade processed independently by `idempotency_key`; partial batch acceptance allowed | `test_custodian_batch_mixed_outcomes` |
| Two independent confirmations arrive for the same `tx_id` (one SETTLED, one FAILED — supplier/CSD disagree) | inbound | Conflict detected; obligation `ConfirmationConflict` opened; status STALE; manual escalation | `test_confirmation_conflict_escalates` |
| CSD reports `PARTIAL_LEG_SETTLED` for cross-currency, then stalls on the second leg | inbound | One pending pair cleared, the other retained; Herstatt window flagged | `test_herstatt_partial_leg_settle` |
| CSDR mandatory buy-in deadline approaches with no resolution | clock advance | Compensation handler fires; obligation → COMPENSATED; new buy-in transaction created | `test_csdr_buyin_deadline_compensates` |
| Operator manually transitions status (out-of-band) | UI / direct DB | Status FSM rejects; capability-scope check Λ_14 fires; audit event logged | `test_out_of_band_status_change_rejected` |

---

## 11. Coverage criteria — honest

| Layer | Target | Measurement |
|---|---|---|
| Line coverage of new code | ≥ 95% | `coverage.py` / equivalent |
| Branch coverage of new code | ≥ 90% | same |
| Mutation score, overall | ≥ 80% | mutmut / mutpy / equivalent |
| Mutation score, P_DS_1 mutants specifically | 100% | targeted; the single most important number |
| Property-test combinatorial coverage | pairwise of (variant × outcome × delay × settle_date) at minimum, full at CI nightly | `cover` decorators / equivalent |
| TLA+ state-space coverage at `|W|=3,|U|=2,|trades|=4,depth=8` | full reachable graph, no untreated states | TLC log |
| Characterisation tests passing on every PR | 100% (no diff against golden) | golden-file diff |
| v10.3 test suite still passing | 100% | full v10.3 suite as regression gate |

**What the suite cannot prove** (honesty gate):

- That the implementation correctly handles **CSDR mandatory buy-in deadlines for illiquid securities** (the deadline depends on liquidity classification — a regulatory parameter outside the model). The suite asserts the obligation deadline is set per `L_7^Pb` policy, not that the policy is correct.
- That **cross-CCP novation during the open window** preserves conservation (Λ_15 is witnessed only for single-CCP scope; cross-CCP is a Phase 3 problem).
- That **operator-initiated cancellations** without counterparty agreement are correctly handled — this is a legal-process question, not a software question; the suite asserts the FSM rejects them, not that the legal process is followed.
- That **settlement at clearing brokers (not direct CSD)** has the same fail semantics — the model abstracts the CSD; if a clearer reverses the chain, the model is incomplete by design.

These four are named, scoped, and deferred to later phases or to non-test controls. **Listing them is the discipline; pretending the suite covers them is the failure mode.**

---

## 12. Output discipline — the seven commandments, applied

1. **Tests are normative.** §2.1 IS the spec of the standard buy. §3 IS the spec of correctness during the open window.
2. **Invariants first.** §3 is the longest section. P_DS_1 is the load-bearing invariant.
3. **Property-based by default.** §3.3, §3.4. Generators over CDM enums; shrinking to ≤ 3 events.
4. **Composition over isolation.** §6.4–§6.7 test deferred settlement composed with SBL, CA, FX. No mocks in the walking skeleton (§2.1).
5. **Determinism is mandatory.** P_DS_10. Determinism boundaries B_1, B_8, B_10 explicitly tested.
6. **Failure modes are first-class.** §6 (eight scenarios, eight tests). §10 (eleven fault-injection scenarios). The fail path is at least as well-tested as the happy path.
7. **Automation is non-negotiable.** Every test in §2, §3, §4, §6, §10 is in CI. The TLA+ check (§8.5) runs on PR. The mutation suite (§9) runs nightly.

If any of these seven is unmet, the deferred-settlement extension is not specified — it is described, and `deferredSettlement.tex` is documentation, not specification.

---

*Five voices, one suite. Beck wrote the smallest test. Hughes generated the rest. Fowler drew the seam. Feathers pinned what would silently break. Lamport modelled what could go wrong across all schedules. Together they make the open window between T and T+2 — the place where every cash equity post-trade architecture has historically been wrong — a structurally testable, structurally bounded, structurally falsifiable artefact.*

*"Code without tests is bad code. It doesn't matter how well written it is."* — Feathers
