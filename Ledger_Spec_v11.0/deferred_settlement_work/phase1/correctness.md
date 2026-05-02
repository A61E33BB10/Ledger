# Deferred Settlement: Correctness, Properties, Oracles, Generators, Faults

**Author role**: correctness-architect
**Phase**: 1 (independent proposal — no cross-talk with Team A)
**Scope**: Cash-equity T → T+2 deferred settlement, fully composed with v10.3
ledger, v10.3 StatesHome addendum (3-map ruling), valuation v1.0, and
ledger\_data v1.0 (19 leaves, 15 cross-layer laws Λ1–Λ15, 17 determinism
boundaries B1–B17, three-tier saga compensation tower, CSDR penalty schema).

The thesis: **deferred settlement is not a new primitive — it is a property
problem on top of the existing primitives** (move stream + virtual wallets +
SETTLEMENT-typed transactions + Obligation L_15 + StatesHome
PositionState/UnitStatus + lifecycle FSM EXECUTED → INSTRUCTED → SETTLED|FAILED).
The deliverable in this file is *what must be true*, *how it is observed*, *how
it is generated under random and adversarial inputs*, and *how a fail at T+2
replays bit-identically from a recorded seed*.

Everything below references existing v11.0 artefacts by name; no new map, no new
storage shape, no new conservation law is invented. **If a property cannot be
restated in terms already in v10.3 + StatesHome + L_15, that is a red flag —
either the property is overspecified or the existing framework has a gap, and
the gap must be named, not papered over.**

---

## 0. State Representation (cross-reference)

The deferred-settlement window between T and T+2 is encoded in the
**existing** state shape, with one obligation per pending settlement leg. No
new fields required; everything earns its place through Karpathy substitution.

| Fact | Home (per StatesHome 3-map ruling) | Mutation |
|---|---|---|
| Trade economic position (own +Q at T, cash -Q·P at T) | `PositionState[w_holder, u_isin]`, `PositionState[w_holder, USD]` | written by Trade handler at T |
| Counterparty contra-entry (virtual broker wallet) | `PositionState[w_broker_virtual, u_isin] = -Q`, `PositionState[w_broker_virtual, USD] = +Q·P` | written by Trade handler at T |
| Pending settlement obligation (one per leg) | `L_15` Obligation, kind = `SETTLEMENT` (cash leg + securities leg or single DvP) | created at T, atomic with Trade |
| Settlement lifecycle status | `UnitStatus[u_settlement_instr].lifecycle_stage ∈ {EXECUTED, INSTRUCTED, SETTLED, FAILED, PARTIALLY_SETTLED}` | shared across counterparties |
| Custodian/CSD external position (for reconciliation) | `PositionState[w_custodian_virtual, u_isin]` | written by `sese.025` confirmation handler at T+2⁺ |
| CSDR penalty (if FAILED past intended settlement date) | `L_15` Obligation, kind = `CSDR_PENALTY`, schema `(rate_bps, days, source_lei, currency)` | created when fail attestation arrives; saga-compensated per Tier 1/2/3 |

**Critical design point.** The economic position lives in
`PositionState` from T, **independently** of settlement status.
`UnitStatus.lifecycle_stage` and the settlement Obligation are the
*reconciliation handle* against the external world; they do not gate position
recognition. This is the trade-date-accounting principle (v10.3 §2.6,
§8.5) made structural.

A cleaner restatement: **PnL at T is a function of `PositionState` only;
PnL at T does not read settlement status.** This is itself a property
(see P-PnLSep below).

---

## 1. The Property Catalogue (the heart of this document)

Properties are organised on the **property ramp** (Universal → Structural →
Safety → Domain → Speculative). Every property has: a precise statement, a
generator strategy, an oracle, a fault profile that should make it fail, and
an existing v11.0 anchor (the law/leaf/invariant it composes with). Properties
that compose with an existing v11.0 law are tagged with that law in
parentheses.

### 1.1 Universal (no system should ever fail these)

**P-NoCrash**: under any sequence of generated trade, fail, partial, recall,
corp-action, finality, retraction, network-reorder events, the ledger does
not panic; every move attempt produces either a committed transaction with
journaled `tx_id` or a typed rejection. *Anchor*: Section 11 P0 of v10.3.

**P-Total-Handler**: for every (lifecycle\_stage, signal) pair in the
deferred-settlement FSM, the handler is total — either a typed accept (with
state delta) or a typed reject (with reason code). No (stage, signal) pair
produces "silent no-op" or undefined behaviour. *Anchor*: StatesHome C2
(per-event-class structural zero-sum is total over `EventClass`).

### 1.2 Structural (algebraic invariants of the ledger)

**P-Cons-T (Conservation at T)**: for the Trade transaction at T, for each
unit `u`, `Σ_w Δw(u) = 0`. Cash `(- Q·P)` from holder cancels `(+ Q·P)` to
virtual broker; security `(+Q)` to holder cancels `(-Q)` from virtual broker.
*Anchor*: Λ5 (per-event-class conservation).

**P-Cons-Through-Window**: for every committed transaction `τ` in the open
window `[T, T+2⁻]` (rate change, mark-to-market, partial fill, recall,
corp action, FX revaluation), `Σ_w Δw(u) = 0` per unit `u`. *Anchor*: Λ5.

**P-Cons-T+2 (Conservation at finality)**: when a `sese.025` confirmation is
processed, the move set that **does not change** ledger PnL but **does**
update the custodian virtual wallet to match the CSD's record satisfies
`Σ_w Δw(u) = 0`. (See P-PnLSep below for why PnL is unchanged.)

**P-Cons-Fail**: when a `sese.024` settlement-fail status arrives, **no
moves are emitted that change `PositionState[w_holder, u_isin]`** — the
economic position is not reversed. The only state delta is to
`UnitStatus[u_settlement_instr].lifecycle_stage` (EXECUTED → FAILED) and the
optional creation of a CSDR penalty Obligation. *Anchor*: v10.3 §8.5.

**P-Λ3-Settlement-Move-Closure**: every `SettlementInstruction` produced by
the deferred-settlement projection maps to **exactly one move-stream
segment** in `L_13`. *Anchor*: Λ3.

**P-Λ15-Novation-Bridge**: if the trade is novated to a CCP (T+0 novation,
common in CSDR-eligible products), the obligation decomposes as either
(i) a union-scope conservation event over the original counterparty +
the CCP, or (ii) two transactions linked by a `NovationBridge` Obligation.
**This is the only place where deferred settlement intersects multi-CCP
conservation; it must not be glossed.** *Anchor*: Λ15.

**P-Reg-Integrity**: every move in any transaction during the window
references existing `wallet_id` and `unit_id` in the registry; the
settlement Obligation's `source` field references the originating
`tx_id`; the originating tx must be present in `L_13` before the
Obligation can be reached by the workflow. *Anchor*: v10.3 invariant 3.

**P-Log-Mono**: `L_13` is append-only over the window; no retroactive
mutation of pre-T+2 transactions when a fail or partial arrives at T+2.
A correction is a **new** transaction with `class = CORRECTION`, never
an in-place edit. *Anchor*: v10.3 invariant 4 + ADR-7.

### 1.3 Safety (correctness under adversarial timing & ordering)

**P-Atomic-DvP-Ledger-Level**: the trade transaction at T contains *both*
the cash leg and the securities leg (or a marker that this is a cash-only
or FOP transfer). The executor commits all moves atomically — both apply
or none do, observable as a single `StateDelta`. *Anchor*: v10.3
invariant 2 + StatesHome C3.

**P-Idem-Trade**: applying the same Trade transaction twice (by `tx_id`)
has zero incremental effect. *Anchor*: Λ10 (`tx_id =
hash_jcs(business_event_id, attempt_seq)` independent of `run_id`).

**P-Idem-Finality**: applying the same `sese.025` confirmation twice (by
`(instruction_id, csd_message_id)`) has zero incremental effect on
`UnitStatus`, `PositionState`, the custodian virtual wallet, and any
downstream Obligation. *Anchor*: v10.3 invariant 5/6 + B12 (signal
idempotency key per signal).

**P-Idem-Fail**: applying the same `sese.024` fail-status twice has zero
incremental effect on `UnitStatus`, the CSDR penalty Obligation (no
double-creation), and the move stream.

**P-Idem-Partial**: applying the same partial-delivery confirmation twice
produces no extra position deltas. The partial state machine is
`PARTIALLY_SETTLED → PARTIALLY_SETTLED → SETTLED`, totalised so that a
duplicate partial of size `q` is detected by `(instruction_id, partial_seq)`.

**P-Reorder-Robust**: for any permutation `π` of arrival order across
{trade-confirm, fail, partial-1, partial-2, recall, corp-action,
retraction, finality}, the **terminal** ledger state (after all events
have been applied and all deadlines have either fired or been
discharged) is **bit-identical** for any two permutations `π_1, π_2`
that reach a terminal `UnitStatus.lifecycle_stage`. *Anchor*: Λ8 (replay
determinism). **This is the single most load-bearing safety property
in this section. It is also the one most likely to fail in a naive
implementation.**

**P-Reorder-Out-of-Order-Tolerated-or-Quarantined**: if a `sese.025`
finality arrives **before** the originating Trade transaction is in
`L_13` (cross-system clock skew, network reorder), the system either
(a) buffers the finality keyed by `(counterparty_lei, instruction_id)`
and applies it once the trade arrives, **or** (b) rejects the finality
into the Break Register `L_18` with `wf-confirm-break` workflow. Both
are acceptable; what is NOT acceptable is silently creating an unmoored
finality record that can never be reconciled. *Anchor*: B12 +
Section 8.7 confirmation return path.

**P-Finality-Then-Retraction**: if a `sese.025` SETTLED confirmation is
followed by a CSD-issued retraction (rare but real, e.g. trade
mistakenly settled to wrong account, or "as-of" correction window
inside DTC), the system emits a `CORRECTION` transaction; it does
not in-place mutate the original `L_13` entry. The new transaction
satisfies conservation per Λ5 and produces a new `BreakRegister`
entry FSM-walked to `Closed-Adj` or `Closed-Waived`. *Anchor*: ADR-7,
v10.3 invariant 4, L_18 FSM.

**P-Cross-Currency-Herstatt**: for a USD-vs-EUR equity-cash trade, the
two currency legs may settle in different time zones. The **economic**
PnL at T is computed against the trade rate; intermediate FX
revaluation between T and T+2 is *unrealised PnL*, not a conservation
violation. The two settlement legs are tracked as **two distinct
Obligations** keyed by `(currency, settlement_window)`. The composite
Obligation's discharge predicate is `both currency legs SETTLED ∨ both
FAILED`; mixed states (one SETTLED, one FAILED) trigger the Tier-2
escalation workflow because one leg must be unwound. *Anchor*:
v10.3 §2.6 settlement-timing-and-Herstatt-risk paragraph.

**P-Late-Discharge-Race** (CRITICAL): if a discharge signal arrives
**after** the deadline timer fired, the saga compensation tower's
"late-discharge race policy" decides per obligation kind. For
`SETTLEMENT` (the deferred-settlement obligation kind): **cancel
compensation if compensation has not externalised; otherwise
queue-and-reconcile**. *Anchor*: ledger\_data v1.0
§ Operational-Saga, "Late-discharge race policy" paragraph. **This
property must be exercised by adversarial generators** (see §3).

### 1.4 Domain (deferred-settlement-specific oracles)

**P-PnLSep (PnL Separability)**: `PnL(t) = V(t, P_t) - V(t_0, P_{t_0})`
where `V` reads only `PositionState[*][own]` and price `P`; `V` does
**not** read `UnitStatus.lifecycle_stage`. **Therefore PnL at any
intermediate time `T ≤ t ≤ T+2` is identical whether the trade is
EXECUTED, INSTRUCTED, or SETTLED**, holding price constant. This is
the property that operationalises trade-date accounting.

**P-PnLSep-Fail**: `PnL` is **also** identical at the same `t` and `P_t`
when the trade transitions EXECUTED → FAILED. Failed settlements do not
reverse position. The ledger does not represent settlement risk as a
write-down to ownership; it represents it as a continued position with
a Break Register entry and (if applicable) a CSDR penalty Obligation.

**P-NetZero-WindowSpan**: two trades by the same holder in the same ISIN
with the same counterparty and same settlement date that net to zero
quantity must produce **zero net cash obligation across the window**.
Specifically: `(buy 100 XYZ @ $50, sell 100 XYZ @ $50)` issued at the
same `T` produces `Obligation_buy + Obligation_sell` whose composite
DvP cash leg is `-5000 + 5000 = 0` and securities leg is
`+100 - 100 = 0`. The two settlement instructions must net (per
v10.3 §8.6 netting rules) to a single zero-instruction or two
opposing instructions with opposite signs. *Anchor*: Λ5 + v10.3 §8.6.

**P-NetZero-WindowSpan-WithProfit**: `(buy 100 XYZ @ $50, sell 100 XYZ
@ $52)` at the same `T` produces **zero net securities obligation**
(quantity nets) but a **net cash obligation of -$200** (the realised
profit, owed *to the holder*). At T+2, custodian cash-leg net delta
is +$200 from the broker virtual wallet, matching the realised PnL.
**This is the worked-example oracle**: end-of-window conservation
must reconcile to the recorded P&L.

**P-PartialFill-Conservation**: for a partial settlement of `q_partial`
out of `Q`, `PositionState[w_holder, u_isin]` is **unchanged** (full
position still recognised at T); `UnitStatus.lifecycle_stage` advances
EXECUTED → INSTRUCTED → PARTIALLY_SETTLED; the **custodian virtual
wallet** delta increments by `q_partial` (ledger-vs-CSD reconciliation
gap shrinks). The **remaining** `Q - q_partial` is wrapped in a
follow-on Obligation with a new deadline (per CSDR mandatory buy-in
schedule, T+4 to T+7 depending on instrument liquidity).

**P-CSDR-Penalty-Schema**: when a settlement is FAILED past intended
settlement date, the CSDR penalty Obligation is created with schema
`(rate_basis_points, days, source_lei, currency)` per ledger\_data
v1.0 §Operational-CSDR. The penalty rate is selected from the
versioned CSDR rate table (not hard-coded), pinned by
`VersionPinSidecar`. *Anchor*: ledger\_data v1.0 § CSDR Penalty
Schema.

**P-Recall-Composes-with-SBL**: if the holder simultaneously has a
recallable SBL loan on the same ISIN and a pending settlement
delivery, recalling the loan to fulfill the settlement is two
**separate** atomic transactions: (i) recall return: SBL coordinates
update per Section 13 of v10.3; (ii) settlement delivery: trade
moves. P11 (SBL conservation) and Λ5 (per-class conservation) compose;
neither is bypassed. *Anchor*: v10.3 §13 + L_15 Obligation kind
`SBL_RECALL`.

**P-Corp-Action-During-Window**: a corporate action with record date in
`(T, T+2)` (typical example: dividend record date, holder is buyer,
trade is "cum-dividend") creates a manufactured-payment obligation
on the seller. The obligation is registered atomically with the
record-date event detection and is a separate L_15 entry, **not**
folded into the original settlement Obligation. *Anchor*: v10.3 §8.4
+ obligation taxonomy `SBL_MANUF_DIVIDEND` (extended to spot equities).

**P-FSM-Totality**: the settlement FSM is total — for every (state,
event) pair in `{EXECUTED, INSTRUCTED, SETTLED, FAILED,
PARTIALLY_SETTLED, RETRACTED} × {confirm, fail, partial, retract,
correction, deadline-fire}`, the transition is either explicitly
defined or is an explicit reject. **The "no edge" case is
forbidden.** *Anchor*: StatesHome C2 (κ-totality).

### 1.5 Speculative (observed regularities — violations should trigger
investigation, not necessarily failure)

**P-Spec-FailRateDist**: empirically, in normal market conditions,
~98% of trades reach SETTLED on T+2 day, ~2% are FAILED or partial.
A test run that produces 0% fails on a 10,000-trade simulation is
suspicious — the generator is biased toward the happy path. Track this
ratio per CI run and gate on it (per ledger\_data v1.0 §Goodhart-3:
"first-class coverage targets per stratum: 5% near-arbitrage-boundary,
10% deadline-near-fire, ...").

**P-Spec-CSDFinalityLatency**: median CSD finality message arrives
within 2 hours of intended settlement. P99 is within 8 hours.
A simulation where every finality arrives within 1 second is
unrealistic — it will not stress the deadline-near-fire codepaths.

**P-Spec-PartialSizeDist**: when partials occur, the partial fraction
is roughly uniform on `[0.1, 0.9]` of original quantity (with
occasional 99%+ "near-complete" partials). A generator producing only
50% partials misses the boundary cases.

---

## 2. Generators (the input space)

Properties without generators are aspirations. Below is the generator
taxonomy. Every domain type has a generator; every generator is
**deterministic** under a seeded PRNG (B2). All time inputs come from
the simulator clock (B1, sourced from `L_19` ClockAuthority pinned
snapshot).

### 2.1 Primitive generators

```python
# Hypothesis-style strategies, sketch only

@composite
def trade_input(draw):
    side = draw(sampled_from(["BUY", "SELL"]))
    isin = draw(isin_strategy())  # 12-char alphanumeric, valid ISO 6166 checksum
    quantity = draw(decimals(min_value="1", max_value="1000000", places=0))
    price_ccy = draw(currency_code())  # ISO 4217 from CDM enum
    price = draw(decimals(min_value="0.01", max_value="100000", places=4))
    settlement_ccy = draw(currency_code())  # may differ — generates Herstatt cases
    counterparty_lei = draw(lei_strategy())
    settlement_date_offset = draw(sampled_from([1, 2, 3]))  # T+1 / T+2 / T+3
    venue_mic = draw(venue_mic_strategy())
    return TradeInput(...)

@composite
def fail_event(draw, instr_id):
    fail_reason = draw(sampled_from(CSDR_FAIL_REASONS))  # closed enum
    fail_ts_offset = draw(decimals(min_value="0", max_value="172800"))  # 0..2d
    return FailEvent(instr_id, fail_reason, fail_ts_offset)

@composite
def partial_event(draw, instr_id, original_qty):
    partial_qty = draw(decimals(min_value="0.01", max_value=str(original_qty - 1)))
    partial_seq = draw(integers(min_value=1))
    return PartialEvent(instr_id, partial_qty, partial_seq)

@composite
def csd_finality_message(draw, instr_id):
    ack_ts_offset = draw(timedeltas(min_seconds=0, max_seconds=86400 * 3))  # T+0..T+3
    csd_id = draw(sampled_from(["DTC", "EUROCLEAR", "CLEARSTREAM"]))
    return CSDFinality(instr_id, ack_ts_offset, csd_id)

@composite
def retraction_event(draw, instr_id):
    # rare — only generated 1-2% of the time as overlay, see §3
    correction_kind = draw(sampled_from(["WRONG_ACCOUNT", "AS_OF_REVERSAL", "AMOUNT_AMEND"]))
    return RetractionEvent(instr_id, correction_kind)
```

### 2.2 Compositional generators

```python
@composite
def settlement_window_history(draw):
    """Generate a complete T..T+2+epsilon event history for one trade."""
    trade = draw(trade_input())
    n_partials = draw(integers(min_value=0, max_value=4))
    partials = [draw(partial_event(...)) for _ in range(n_partials)]
    will_fail = draw(booleans(weight=0.05))   # P-Spec-FailRateDist
    will_retract = draw(booleans(weight=0.01))  # rare
    finality = draw(csd_finality_message(...))
    # …assemble the linear timeline; arrival ordering perturbed by §3
    return WindowHistory(...)

@composite
def cross_currency_window(draw):
    """USD-vs-EUR equity-cash, separate currency legs settling independently."""
    ...

@composite
def two_trades_netting(draw):
    """Two trades same holder, same ISIN, same counterparty, same settlement date —
       ranges over both 'net to zero' and 'net to ±qty' to exercise P-NetZero."""
    ...

@composite
def trade_with_corp_action(draw):
    """Trade whose settlement window straddles a corporate-action record date."""
    ...

@composite
def trade_with_recall(draw):
    """Holder has a pending SBL recall; settlement requires the recall to
       discharge before the settlement deadline."""
    ...
```

### 2.3 Bugified / pathological-but-legal generators

Per the Phase 2 mandate ("bugification is mandatory alongside legal-input
generators"), the following adversarial generators must be present.
Each one is *legal under the specification* but exercises edge cases:

```python
@composite
def adversarial_clock_skew_window(draw):
    """Multi-node simulation: each CSD message has a node-local timestamp drawn
       from N(true_ts, σ=clock_skew_seconds), σ in [0, 5000]."""

@composite
def adversarial_arrival_reorder(draw, history):
    """Permute the message arrival order at the workflow input.
       MUST cover: finality before trade, fail before finality (illegal),
       finality concurrent with deadline-fire, partial-2 before partial-1."""

@composite
def adversarial_duplicate_finality(draw, history):
    """Inject N copies of the same sese.025 over [T+2, T+5]. Tests P-Idem-Finality."""

@composite
def adversarial_finality_then_retraction(draw, history):
    """sese.025 SETTLED at T+2, then sese.025 RETRACTED at T+3.
       Tests P-Finality-Then-Retraction and saga Tier-2 escalation."""

@composite
def adversarial_message_loss(draw, history):
    """Drop one or more messages in the timeline. The system MUST recover via
       the deadline timer — no infinite Pending."""

@composite
def adversarial_message_reorder_with_loss(draw, history):
    """Combination of loss and reorder. The terminal state must still be
       deterministic from the surviving message set + timer fires."""

@composite
def near_deadline_burst(draw, history):
    """All messages compressed into the last 60s before the deadline.
       Tests race conditions in the saga compensation cancel-or-queue rule."""

@composite
def csdr_buy_in_window(draw, history):
    """FAILED at T+2; mandatory buy-in scheduled at T+4 (or T+7 for illiquid).
       Tests CSDR penalty Obligation creation, Tier-1 → Tier-2 saga escalation,
       and the eventual buy-in transaction satisfying P-Cons-Through-Window."""
```

### 2.4 Coverage targets (CI gates)

Per ledger\_data v1.0 §Goodhart-3, the following per-stratum coverage
targets are CI-asserted, not aspirational:

| Stratum | Target % of generated cases |
|---|---|
| Happy path (no fail, no partial, no reorder) | ≤ 60% |
| Settlement fail | ≥ 5% |
| Partial fill (1+ partials) | ≥ 10% |
| Cross-currency / Herstatt | ≥ 10% |
| Recall composition | ≥ 5% |
| Corporate action during window | ≥ 5% |
| Finality-then-retraction | ≥ 1% |
| Near-deadline burst | ≥ 5% |
| Out-of-order finality | ≥ 5% |
| Two-trades netting (incl. zero-net) | ≥ 5% |

The CI gate fails if any stratum is under-represented. **This prevents
the Goodhart trap of "999/1000 happy-path traces means we're done."**

### 2.5 Shrinkers

Hypothesis ships shrinkers for primitive types automatically. The
*compositional* shrinkers needed:
- Drop messages: shrink toward the empty timeline (with the trade preserved).
- Coalesce partials: replace `(partial_q1, partial_q2)` with
  `(partial_q1 + partial_q2)`.
- Compress timestamps: pull all events toward `T` to find the smallest
  time window that still violates the property.
- Reduce quantity: shrink `Q` while keeping the move structure.
- Reduce counterparty count: shrink to a single counterparty.
- Reduce currency leg count: shrink Herstatt cases to single-currency.

A failure should shrink to a *minimal counterexample* of the form
"one trade, one message, one failed property" — anything more
complex is a sign the shrinker is incomplete.

---

## 3. Oracles (how a property is decided)

Each property has at least one oracle. Oracles fall into four classes:

### 3.1 Algebraic oracles (cheapest, strongest)

Run after every committed transaction in the event stream:

```python
def oracle_conservation(state_before, tx, state_after):
    for unit in units_touched(tx):
        delta = sum(w[unit] for w in state_after) - sum(w[unit] for w in state_before)
        assert delta == 0, f"Conservation violated for {unit}"
```

```python
def oracle_log_monotonicity(state_before, state_after):
    assert state_after.move_stream[:len(state_before.move_stream)] == state_before.move_stream, \
        "L_13 prefix mutated"
```

```python
def oracle_pnl_separability(state, t, price_vec):
    # PnL must be a function of PositionState and price only
    pnl_a = compute_pnl(state, t, price_vec)
    state_alt = state.with_lifecycle_stage_perturbed(t)  # twiddle UnitStatus
    pnl_b = compute_pnl(state_alt, t, price_vec)
    assert pnl_a == pnl_b, "PnL depends on settlement status — P-PnLSep violated"
```

### 3.2 Replay-determinism oracles (Λ8 anchor)

```python
def oracle_replay_determinism(history):
    """Run the full window twice from the same seed, the same L_19 snapshot,
       and the same input message permutation. Bit-compare the resulting L_13."""
    state_run_1 = run_window(history, seed="abc", l19_snap="snap-001")
    state_run_2 = run_window(history, seed="abc", l19_snap="snap-001")
    assert hash_jcs(state_run_1.L_13) == hash_jcs(state_run_2.L_13)
```

```python
def oracle_reorder_robustness(history):
    """Different arrival orders, same terminal state."""
    s_a = run_window(permute(history, key="arrival_a"))
    s_b = run_window(permute(history, key="arrival_b"))
    # Wait for both to reach a terminal lifecycle_stage
    # (eventually-quiescent oracle — may need a bounded simulator step cap)
    assert canonical_terminal_state(s_a) == canonical_terminal_state(s_b)
```

### 3.3 Differential / metamorphic oracles (where applicable)

Differential testing alternatives:
- **Against CDM**: the deferred-settlement workflow's `BusinessEvent` chain
  must round-trip through CDM `Trade → SettlementInstruction → BusinessEvent
  (TransferState delta)`. A divergence between the ledger's
  `SettlementInstruction` and the CDM-projected one is a bug in either the
  projection (Λ3) or the CDM mapping (Λ9).
- **Against ISO 20022**: the `sese.023` message generated from the projection
  must, after the settlement-layer enrichment (SSI lookup, CSD account,
  priority), round-trip through a reference ISO 20022 validator (e.g.
  Swift's MyStandards or a local ISO20022 schema validator). Schema-invalid
  output is a Goodhart-1 trap (snapshot-stub-swap) — guard against it
  with the boundary CI test.
- **Against bookkeeping reference (worked example)**: a single
  hand-computed example (the §6 worked example below) is regression-pinned;
  any code change that perturbs its byte-identical output triggers
  manual review.

Metamorphic relations:
- **Time translation**: if the entire history is shifted by `Δt`, the
  terminal state should be identical modulo timestamp shift. (This
  composes with Λ8 time-translation invariance.)
- **Sign flip**: a sell at `+P` and a buy at `+P` for the same quantity
  should have opposite signs in `PositionState[*][own]` and opposite
  cash flows.
- **Currency relabel**: relabelling USD as a fictive currency (preserving
  the FX rate identity) should not change conservation; it should change
  only the per-leg currency tags.
- **Quantity scaling**: scaling all quantities by `λ > 0` should scale
  all moves by `λ` and preserve conservation.
- **Two-trades netting**: `trade(buy 100) + trade(sell 100) ≡ no-op`
  modulo the trade record (this is the P-NetZero oracle).

### 3.4 Reference / characterisation oracles

A frozen corpus of ≥ 40 hand-curated regression fixtures (per
ledger\_data v1.0 § Test Pyramid Declaration). Each fixture is a
recorded message timeline + expected terminal state hash. Any change
to the terminal state of a regression fixture is a Goodhart-1 alert.

---

## 4. Determinism Boundaries (per B1–B17)

Every non-deterministic input touched by deferred settlement must be
injectable. Below, the relevant boundaries from the v11.0 catalogue and
the **specific** injection point for deferred settlement:

| Boundary | What enters via this boundary in deferred settlement | Injection point |
|---|---|---|
| B1 wall-clock | Trade timestamp `T`, intended-settlement-date computation, deadline timestamps, `now()` reads in retry logic | `clock` parameter on `SettlementWorkflow`; in tests, `Clock.frozen_at(T)` advanced manually |
| B2 PRNG | None expected (settlement is deterministic given inputs); but if any retry jitter or load-shedding stochasticity exists, it must be seeded | Workflow input field `prng_seed` |
| B3 price feeds | Mark-to-market during window, FX rate for cross-currency revaluation | `L_19`-pinned snapshot of `L_9`/`L_12` per workflow start |
| B4 external oracles | CSD confirmation, CSD fail attestation, custodian status feed | All ingress goes through `signal_idempotency_key` (B12); no direct external reads |
| B5 reference data | ISIN/LEI/MIC/calendar data | bitemporal `as_of` query at workflow start |
| B6 settlement infra | SSI database, CSD account map | `SsiSnapshotRef` versioned per workflow run |
| B8 workflow scheduling | Temporal-managed; deadline timer fire is deterministic per Temporal replay | Temporal test server in CI |
| B9 CDM enum universe | `EventIntentEnum`, `OptionTypeEnum`, settlement-type enums | `cdm_version` pinned per workflow input |
| B10 hash / canonicalisation | `tx_id` derivation, message hash for idempotency | RFC 8785 JCS; CI test pins this |
| B12 network reorder | All inbound messages | per-message `signal_idempotency_key`; OOO buffering with deterministic merge order (lex on `(t_known, message_id)`) |
| B13 floating-point | FX revaluation, MTM aggregation, CSDR penalty rate × days × notional | pinned BLAS/threads; IEEE 754 `fp:strict`; all monetary arithmetic in `Decimal` not `float` |
| B14 storage iteration | Position aggregation across wallets for reconciliation | sorted iteration on `(wallet_id, unit_id)` |
| B15 intra-handler concurrency | Settlement workflow handler | single-threaded per workflow; canonical-order reduction over signal completions |
| B19 (implicit) Holiday/Calendar | Settlement-date arithmetic uses business-day calendars | `L_4` CalendarConvention with mode-1 amendment pin (ADR-5) |

**Goodhart trap to avoid (GT-1)**: a "deterministic" simulator that quietly
re-reads `wall_clock` from the host inside the workflow body is a
snapshot-stub-swap. The CI must include a boundary-integrity production
test: pull N committed transactions from the production snapshot store,
replay through the simulator, assert byte-identical `tx_id` chain.

---

## 5. Fault Catalogue (the 7×7 deferred-settlement harness)

Each entry: **fault** × **case** matrix. Each cell names a harness (a
test fixture or a chaos-engineering injection), not just an English
description. Cells marked `—` are inapplicable for that case (e.g.
"corporate action" does not apply to a pure cash-only payment).

| Fault \ Case | T+2 buy | T+2 sell | T+1 | Fail (CSDR) | Partial | Recon | Cross-ccy |
|---|---|---|---|---|---|---|---|
| **Crash-stop (worker)** | h-crash-buy | h-crash-sell | h-crash-t1 | h-crash-fail | h-crash-partial | h-crash-recon | h-crash-xccy |
| **Crash-recover (worker)** | h-recover-buy | h-recover-sell | h-recover-t1 | h-recover-fail | h-recover-partial | h-recover-recon | h-recover-xccy |
| **Network partition (CSD ↔ ledger)** | h-partition-buy | h-partition-sell | h-partition-t1 | h-partition-fail | h-partition-partial | h-partition-recon | h-partition-xccy |
| **Clock skew (cross-node, σ ≤ 5s)** | h-skew-buy | h-skew-sell | h-skew-t1 | h-skew-fail | h-skew-partial | h-skew-recon | h-skew-xccy |
| **Message duplicate (×N copies)** | h-dup-buy | h-dup-sell | h-dup-t1 | h-dup-fail | h-dup-partial | — | h-dup-xccy |
| **Message reorder (random perm)** | h-reord-buy | h-reord-sell | h-reord-t1 | h-reord-fail | h-reord-partial | — | h-reord-xccy |
| **Message loss + retry** | h-loss-buy | h-loss-sell | h-loss-t1 | h-loss-fail | h-loss-partial | — | h-loss-xccy |

Each `h-*` is a Hypothesis stateful test (or a Temporal test-server
chaos scenario) that:
1. Runs the case end-to-end with the named fault injected.
2. Asserts the universal + structural + safety properties at the end.
3. Asserts the case-specific domain property at the end.
4. Records the seed and the input message timeline so the failure is
   replayable bit-identically.

**Composition cases (must also be in the harness)**:
- `h-short-recall-fail`: short sell + recall arrives + recall fails buy-in.
- `h-corp-action-during-fail`: corp action at T+1, settlement fails at T+2,
  who owes the manufactured payment.
- `h-novation-mid-window`: trade novated to CCP at T+1, who owns the
  Obligation.
- `h-cross-ccy-leg-asymmetric-fail`: USD leg SETTLED at T+2 NY close, EUR
  leg FAILED at T+2 London close (Herstatt morning).
- `h-finality-then-retraction-near-deadline`: SETTLED at T+1.99,
  RETRACTED at T+2.01 just as the deadline timer fires.

**Ground-truth statement on fault coverage**: a fault that produces a
non-replayable failure is a higher-priority bug than a fault that
produces an incorrect result, because the latter at least admits
post-hoc analysis.

---

## 6. Reproducibility Constraint

A failure in any property at any point in the T → T+2 window must
satisfy the following constraints simultaneously:

1. **Seed**: the entire run is parameterised by a single PRNG seed (B2)
   and a single `L_19` clock snapshot (B1).
2. **Input freezing**: all inbound messages (trade, fail, partial,
   finality, retraction, recall, corp-action) are recorded with
   `(arrival_order, message_id, message_payload, idempotency_key)`
   tuples.
3. **Snapshot**: the full reference-data context (ISIN/LEI/calendar/CDM
   version/SSI snapshot) is content-addressed (B5, B6, B9).
4. **Replay function**: there exists a function `replay(seed, l19_snap,
   inputs, refdata_snap) → final_state` such that running this function
   on the same arguments at any time, on any machine, in any order
   relative to other tests, produces a byte-identical `final_state`
   (Λ8 + Λ10).
5. **Bug report bundle**: a failing test produces a `repro.zip`
   containing all five of the above plus the property that failed and
   the shrunk minimal counterexample.

**Auditability claim**: this is what we present to an auditor when
asked "how do you know your settlement workflow is correct under
adversarial conditions?" The auditor receives the fault matrix, the
property catalogue, the per-stratum coverage targets, and a CI run
showing all properties pass on every commit. They can request any
of the ≥ 40 regression fixtures and run them locally. The auditor
does not need to read the implementation; the properties **are** the
specification, and the property suite proves the implementation
satisfies the specification on any input drawn from the bounded enum
universe.

---

## 7. Witness-Laundering Pitfalls

Per ledger\_data v1.0 GT-5 ("Type-system witness laundering"). Three
specific pitfalls in deferred settlement where the type system might
"pass" while the runtime invariant could still be broken:

**WL-1: `SettlementInstruction` constructed via `dataclass.replace()` or
`__post_init__` bypass.** The instruction's invariants — exactly one
securities leg, exactly one cash leg (or marker for FOP/CASH), counterparty
LEI present, settlement date >= trade date — are checked at construction.
If a downstream code path uses `dataclasses.replace(instruction,
settlement_date=...)` without re-running validation, an invalid
instruction can flow into the settlement layer.

**Mitigation**: closed witness inventory. `SettlementInstruction` has
exactly one construction site (`settle_projection`), and any other
constructor (including `replace`) is banned by AST lint. A runtime
checker re-validates on every read.

**WL-2: `Obligation` discharge predicate mutation.** The discharge
predicate is a `Callable`, often a closure capturing wallet IDs. If the
closure captures a *mutable* wallet reference rather than a frozen
`(wallet_id, unit_id)` tuple, late binding can change what discharge
"means" between obligation creation and timer fire.

**Mitigation**: the `discharge_predicate` field is restricted to closed
sum types `DischargePredicateKind = ByDeadline | ByMatch | ByAttestation
| ByCondition`, each with frozen-tuple keys. A free-form `Callable` is
not admissible. (This is already in the v11.0 spec for L_15; the
deferred-settlement extension must respect it.)

**WL-3: `tx_id` formula drift.** Per Λ10, `tx_id =
hash_jcs(business_event_id, attempt_seq)`, **not** including
`workflow_run_id`. A naive implementation that includes the run_id
will silently break idempotency on `ContinueAsNew`, double-spending
the cash leg if the workflow restarts mid-window. This is the
ADR-7 risk made concrete.

**Mitigation**: a CI test that reflects on the `tx_id` derivation
function and asserts its argument list does not contain `run_id`,
`worker_id`, `host_id`, or any other ephemeral identifier.

---

## 8. Worked Example (the regression-pinned case)

**Setup**.
- Holder `w_H`, broker virtual `w_B`, custodian virtual `w_C`.
- ISIN: `XYZ` (US-listed equity, T+2 settlement).
- Initial balances: `w_H[USD] = 10000`, all others zero.
- Trade: buy 100 XYZ @ \$50 at `T = 2026-04-30T09:30:00Z`, settlement
  date = `T+2 business days = 2026-05-04`.
- Price at `T+1` = \$52 (mark-to-market only; no transaction).

**T (trade time, 2026-04-30T09:30:00Z), Trade transaction**:

```
Move(from: w_H,    to: w_B,    unit: USD, quantity: 5000,    source: tx_T)
Move(from: w_B,    to: w_H,    unit: XYZ, quantity: 100,     source: tx_T)
StateDelta:
  PositionState[w_H, USD][own]   = 10000 - 5000 = 5000
  PositionState[w_B, USD][own]   = 0    + 5000 = 5000
  PositionState[w_H, XYZ][own]   = 0    + 100  = 100
  PositionState[w_B, XYZ][own]   = 0    - 100  = -100
  UnitStatus[u_settlement_instr_T].lifecycle_stage = EXECUTED
Obligation L_15 created:
  id          = "SETTLE-XYZ-T-001"
  type        = SETTLEMENT
  source      = tx_T
  deadline    = 2026-05-04T??:??:??Z (CSD cut-off)
  discharge   = sese.025 SETTLED message received for instruction tx_T
  compensation = CSDR_BUY_IN at T+4 if liquid, T+7 otherwise
```

**Conservation at T**: ΔUSD = `-5000 + 5000 = 0` ✓; ΔXYZ = `+100 - 100
= 0` ✓. **P-Cons-T satisfied.**

**T+1 (mark-to-market, 2026-05-01)**: no transaction. Price moves to
\$52. Valuation at T+1:
- `V(T+1, P_{T+1}) = 100 × $52 + $5000 = $10200`
- `V(T,   P_T)     = 100 × $50 + $5000 = $10000`
- `PnL              = $10200 - $10000 = +$200`

**P-PnLSep test**: perturb `UnitStatus[u_settlement_instr_T].lifecycle_stage`
artificially to FAILED. Recompute `V(T+1, P_{T+1})`. Must equal $10200.
**P-PnLSep satisfied.**

**T+2 (settlement, 2026-05-04, CSD cut-off)**: `sese.025` arrives.
Settlement transaction (custodian reconciliation, **zero PnL impact**):

```
Move(from: w_C, to: w_B, unit: USD, quantity: 5000, source: tx_T+2_cash, class=CORRECTION)
Move(from: w_B, to: w_C, unit: XYZ, quantity: 100,  source: tx_T+2_secs, class=CORRECTION)
StateDelta:
  PositionState[w_C, USD][own]   = 0  - 5000   (custodian now holds the cash)
  PositionState[w_B, USD][own]   = 5000 + 5000 = 10000  (wait — this can't be right)
```

**Hold on.** The above is wrong. Let me redo it carefully — and **this
is itself an oracle**: the worked example must self-check, otherwise
the spec is unclear.

The corrected T+2 reconciliation: at T, the broker virtual wallet
absorbed both the cash receipt (-\$5000 from holder) and the
securities delivery (+100 XYZ to holder, mirrored as -100 XYZ in the
broker virtual). At T+2 the **custodian** is what actually reflects
the real-world transfer. The clean restatement:

- The broker virtual wallet `w_B` is a **placeholder for an
  unsettled obligation**. It carries `+5000 USD` and `-100 XYZ` from
  T to T+2.
- At T+2, the actual cash and securities movement is *between the
  broker and the custodian* (or, more precisely, between the holder's
  bank and the custodian's bank, but the ledger sees this as a
  custodian virtual wallet update).
- The settlement confirmation does **not** add a new economic move;
  it adds a **reconciliation move** that zeroes the broker virtual
  wallet and credits/debits the custodian virtual wallet.

```
T+2 reconciliation transaction (class = SETTLEMENT_CONFIRMATION):
Move(from: w_B, to: w_C, unit: USD, quantity: 5000, source: tx_T+2)
Move(from: w_C, to: w_B, unit: XYZ, quantity: 100,  source: tx_T+2)
After this:
  PositionState[w_B, USD][own]   = 5000 - 5000 = 0       (broker virtual cleared)
  PositionState[w_B, XYZ][own]   = -100 + 100 = 0        (broker virtual cleared)
  PositionState[w_C, USD][own]   = 0 + 5000  = 5000       (custodian received cash)
  PositionState[w_C, XYZ][own]   = 0 - 100   = -100       (custodian delivered shares)
  UnitStatus[u_settlement_instr_T].lifecycle_stage = SETTLED
Obligation L_15 "SETTLE-XYZ-T-001" → DISCHARGED
```

**Conservation at T+2**: ΔUSD = 0; ΔXYZ = 0. **P-Cons-T+2 satisfied.**

**P-PnLSep across the window**: PnL at T+2 with `P_{T+2} = $52` is
still `+$200`, regardless of `lifecycle_stage`. The settlement
transaction has zero net effect on `PositionState[w_H, *]`.

**The fail variant (regression case)**. Replace the T+2 confirmation
with a `sese.024` FAILED message. The new state:

```
StateDelta:
  PositionState[w_H, *]          unchanged  (P-Cons-Fail)
  PositionState[w_B, *]          unchanged  (still carrying the unsettled obligation)
  PositionState[w_C, *]          unchanged  (no actual transfer occurred)
  UnitStatus[u_settlement_instr_T].lifecycle_stage = FAILED
  L_15 "SETTLE-XYZ-T-001" remains in PENDING (per the saga policy "deadline sacrosanct"
       for SBL recall, but per "queue-and-reconcile" for SETTLEMENT — see late-discharge
       race policy in the saga compensation tower).
  L_15 "CSDR-PENALTY-XYZ-T-001" created with schema (rate_bps, days_late=0, source_lei,
       USD).
  Break Register L_18: new entry "wf-confirm-break", state = Open.
Mark-to-market PnL at T+2: still +$200. (P-PnLSep-Fail satisfied.)
```

**The audit-grade claim**: under all 7 fault rows × 7 case columns,
plus all composition cases, the terminal `(PositionState, UnitStatus,
L_15, L_18, L_13)` tuple is a deterministic function of `(seed,
l19_snap, refdata_snap, message_arrival_set)`. Running the worked
example above through any of the harnesses produces a known terminal
hash; deviations are immediate and replayable.

---

## 9. CDM Cross-Walk

The deferred-settlement workflow **must** decompose into CDM
`BusinessEvent` chains for cross-walk to DRR (regulatory reporting,
Λ9 forgetful functor):

| Ledger artefact | CDM artefact |
|---|---|
| Trade transaction at T | `BusinessEvent.eventQualifier = Execution`, `before = ∅`, `after = TradeState{ status: Executed, settlementInstructions: [...] }` |
| `SettlementInstruction` projection | CDM `Transfer` primitive (payer, payee, quantity, unit, settlementDate) |
| `UnitStatus.lifecycle_stage = INSTRUCTED` transition | CDM `BusinessEvent.eventQualifier = Allocation` (or `Settlement`-precursor) |
| `sese.025 SETTLED` transition | CDM `BusinessEvent.eventQualifier = Settlement`, `after.status = Settled` |
| `sese.024 FAILED` transition | CDM `BusinessEvent.eventQualifier = SettlementFail` (NB: CDM coverage incomplete; documented in ledger\_data v1.0 § CDM Gap Analysis as a strategic gap to flag) |
| Partial fill | CDM `BusinessEvent.eventQualifier = PartialSettlement` (also incomplete in CDM) |
| Retraction | CDM `BusinessEvent.eventQualifier = Cancellation` linked via lineage |
| CSDR penalty | **No CDM equivalent**; ledger-internal Obligation kind |
| Recall during window | CDM `BusinessEvent.eventQualifier = Recall` (via SBL extension) |

The **gaps** above (settlement fail, partial settlement, CSDR penalty) are
witnessed by the data spec's CDM Gap Analysis and are accepted under the
same vendor-coverage assumption as Λ1. The ledger's representation is
canonical; the CDM cross-walk is best-effort and pinned to a specific
`cdm_version` per ADR-9 / B9.

---

## 10. Coverage Criteria for Audit

What would convince an auditor that the deferred-settlement extension is
tested? The acceptance package:

1. **Property pass log**: every property in §1 (P-NoCrash through
   P-Spec-PartialSizeDist) passes on the latest CI build, with
   per-property generator counts and timing.
2. **Coverage report**: per-stratum coverage targets in §2.4 are met or
   exceeded. The CI artifact records the exact stratum distribution.
3. **Mutation kill rate**: applying the 15 mutation operators (CONS, BND,
   VAC, CLK, CCH, NPJ, CAN, CDM, CAP, LAT, FCT, AGG, DFL, BIA, SHR) to
   the deferred-settlement code yields per-cluster kill rates per
   ledger\_data v1.0 Table tab:mutation-floors:
   - For Λ5/Λ7/Λ15 cluster: ≥ 95% on CONS, AGG; ≥ 90% on VAC, CCH, DFL.
   - For Λ8 (replay determinism — particularly relevant): ≥ 95% on CCH;
     ≥ 80% on all others.
   - For Λ13 (obligation liveness — covers our settlement obligations):
     ≥ 95% on LAT; ≥ 90% on SHR.
4. **Fault matrix completion**: every cell in §5 has a passing harness;
   every harness produces a `repro.zip` for failure reproduction.
5. **Worked example**: §8 is a regression fixture; its terminal hash
   is pinned and any change to it is reviewed.
6. **Boundary integrity**: every B1–B17 boundary touched by the
   workflow has its CI test passing (per ledger\_data v1.0 Table
   tab:boundaries).
7. **Goodhart hardening**: GT-1 through GT-5 detection mechanisms are
   active (see §11).
8. **Differential pass**: CDM round-trip and ISO 20022 schema validation
   pass on a corpus of ≥ 40 fixtures.

A missing item from any of (1)–(8) is a blocker for sign-off.

---

## 11. Goodhart Traps Specific to Deferred Settlement

Beyond the five traps named in ledger\_data v1.0 § Goodhart-Hardening,
deferred settlement has three specific traps to watch:

**G-DS-1: "All-finality-arrives-quickly" generator bias.** A generator
that produces every `sese.025` within 1 second of the deadline never
exercises the late-discharge race policy or the saga Tier-2
escalation. Detection: P-Spec-CSDFinalityLatency must enforce a
minimum P50 / P99 latency in the generator output distribution.

**G-DS-2: "Conservation-passes-globally-but-not-per-class" trap.**
A common implementation bug: the global conservation `Σ_w Δw(u) = 0`
holds because two unrelated transactions cancel each other out, even
though one of them has an internal class-level conservation
violation. Detection: P-Cons-Per-Class (Λ5 directly) — the per-class
sum must be zero for every transaction individually, not just over
the aggregate.

**G-DS-3: "AI-generated test that asserts the implementation back to
itself"**. The classical Goodhart trap with property-based testing in
the AI era: a generated test that calls the implementation, captures
its output, and asserts that calling the implementation again
produces the same output. This is **not** a property test — it is a
record-and-replay equivalence test. Detection: every property in §1
is stated *independently* of the implementation, in terms of the
abstract state space (PositionState, UnitStatus, L_15, L_13). A test
that does not reduce to one of these abstract assertions is rejected
in code review.

---

## 12. Concrete Test Cases the Implementation MUST Pass

Below is a checklist of test cases. Each is a Hypothesis stateful test
or a fixture-based regression. **These are not negotiable.** The
implementation must pass all of them; failing one is a release blocker.

1. **TC-Buy-T+2-HappyPath**: §8 worked example, settles cleanly. Asserts
   P-Cons-T, P-Cons-T+2, P-PnLSep, P-Idem-Trade.
2. **TC-Sell-T+2-HappyPath**: mirror of TC-1 with sell direction.
3. **TC-T+1-HappyPath**: same as TC-1 with `settlement_date_offset = 1`.
4. **TC-Buy-T+2-Fail**: §8 fail variant. Asserts P-Cons-Fail,
   P-PnLSep-Fail, P-CSDR-Penalty-Schema.
5. **TC-Buy-T+2-Partial-2-Tranches**: 60% partial at T+1, 40% partial at
   T+2. Asserts P-PartialFill-Conservation,
   P-Cons-Through-Window.
6. **TC-Buy-T+2-Reorder**: arrival order `[finality, partial]` permuted
   to `[partial, finality]`. Asserts P-Reorder-Robust.
7. **TC-Buy-T+2-Duplicate-Finality**: `sese.025` duplicated 5×. Asserts
   P-Idem-Finality.
8. **TC-Buy-T+2-Finality-Then-Retraction**: SETTLED at T+2.0,
   RETRACTED at T+2.1. Asserts P-Finality-Then-Retraction.
9. **TC-Net-Zero-Same-T**: buy 100 + sell 100 same ISIN, same
   counterparty, same T. Asserts P-NetZero-WindowSpan.
10. **TC-Net-PnL-PlusTwoHundred**: §8 plus a counter-trade making PnL
    +\$200 at T+2. Asserts P-NetZero-WindowSpan-WithProfit.
11. **TC-Cross-Currency-Buy**: buy USD-denominated equity, settle EUR
    cash leg. Asserts P-Cross-Currency-Herstatt with both legs SETTLED.
12. **TC-Cross-Currency-Asymmetric-Fail**: USD leg SETTLED, EUR leg
    FAILED. Asserts P-Cross-Currency-Herstatt with mixed-state escalation
    to Tier 2.
13. **TC-Recall-Composes**: holder is short an SBL position; the recall
    must discharge before settlement. Asserts P-Recall-Composes-with-SBL.
14. **TC-Corp-Action-During-Window**: dividend record date at T+1 with
    holder as buyer. Asserts P-Corp-Action-During-Window and
    manufactured-payment Obligation creation.
15. **TC-Late-Discharge-Race**: `sese.025` arrives 100ms after deadline
    timer fired. Per saga policy `cancel-compensation if not
    externalised`, asserts the compensation transaction is not
    committed and the discharge is queued.
16. **TC-Late-Discharge-Race-Externalised**: `sese.025` arrives 100ms
    after compensation has already externalised (e.g. CSDR buy-in
    submitted). Per saga policy `queue-and-reconcile`, asserts both
    transactions are recorded and a `Closed-Adj` BreakRegister entry
    is created.
17. **TC-CSDR-Buy-In-Schedule**: failed liquid equity, buy-in scheduled
    at T+4. Asserts the buy-in transaction is generated and conserves
    quantity.
18. **TC-Out-of-Order-Finality-Before-Trade**: `sese.025` arrives before
    the originating Trade is in `L_13`. Asserts the system either
    buffers (per B12) or routes to `L_18 BreakRegister`; in either
    case no unmoored finality record exists.
19. **TC-Replay-Determinism**: any of TC-1 through TC-18, run twice from
    same seed and snapshot, byte-identical `L_13`. Asserts Λ8.
20. **TC-Time-Translation-Invariance**: shift the entire history of TC-1
    by `Δt`. Terminal state identical modulo timestamp shift. Asserts
    Λ8 + metamorphic relation §3.3.
21. **TC-Worker-Crash-Mid-Window**: kill the worker after Trade
    transaction commit but before T+2. Recover. Asserts the workflow
    resumes from Temporal history; deadline timer fires correctly;
    P-Reorder-Robust and Λ8 hold.
22. **TC-Network-Partition-Custodian**: simulate a 30-minute partition
    between the ledger and the CSD around T+2. Asserts the deadline
    timer fires; FAILED is recorded; CSDR penalty Obligation created;
    upon partition heal, the `sese.025` (if it arrives) routes through
    the late-discharge race policy correctly.
23. **TC-Clock-Skew-Cross-Node**: simulate σ=2s clock skew between the
    workflow worker and the ingress message parser. Asserts canonical
    ordering of messages by `(t_known, message_id)` (B12 + B14)
    produces deterministic results.

Each TC has a test name `test_TC_<id>_<description>`, runs in CI on
every commit, and reports its full property-pass set in the CI
artifact bundle.

---

## 13. Blockers and Open Questions for Phase 2

Items that the correctness-architect cannot resolve unilaterally and
that the panel must surface in Phase 2 adversarial review:

**B-Q-1 (CDM gap)**: CDM has incomplete coverage of partial-settlement
and settlement-fail events. Either the panel treats this as accepted
under Λ1 vendor-opacity (with a named owner), or the panel commits to
proposing a CDM extension. Owner: rosetta-cdm-engineer.

**B-Q-2 (Saga policy verification)**: the late-discharge race policy
is pinned per obligation kind via `VersionPinSidecar`. The
correctness-architect must verify that the deferred-settlement entry
in this policy table is set to `cancel-compensation if not
externalised` (per the saga compensation tower paragraph), but I have
not confirmed the policy table actually has a `SETTLEMENT` entry —
I have inferred it. Owner: institutional-brake to confirm or push back.

**B-Q-3 (T+0 settlement under DTCC 2024 cutover)**: US equities settled
T+0 as of 2024 DTCC cutover. The 11:30 AM ET cutoff (per ledger\_data
v1.0 § Service-Level-Matrix) makes the deferred window much
narrower. Does the correctness story above need a separate "T+0"
section? Probably yes, but the floor cases listed in the question
specify T+1 / T+2; this is a Phase 2 panel decision.

**B-Q-4 (Position limits / regulatory threshold breach during the
window)**: if the holder's pending settlement would, when combined
with existing position, breach a regulatory short-selling limit (e.g.
SSR uptick rule, Reg SHO), is the trade rejected at T or accepted
with downstream remediation? The ledger does not enforce this; the
smart contract guard does. Phase 2 panel should clarify whether the
deferred-settlement spec needs a hook for this. Owner: jane-street-cto.

**B-Q-5 (Idempotency of the regulatory-reporting Obligation across the
window)**: every settlement event creates a regulatory-reporting
Obligation (SFTR for SBL legs, EMIR Refit / MiFIR for the trade,
CSDR for the fail). If a fail is recorded at T+2 and then a
retraction at T+3, do we report the fail anyway, or do we issue an
amendment? Different regimes have different rules. Owner:
regulatory-architect / ssirius.

---

## 14. Summary

What this document does:

1. **Refuses to invent new state**. Deferred settlement is encoded in
   existing v11.0 primitives (PositionState, UnitStatus, L_15
   Obligation, L_13 move stream, SETTLEMENT-typed transactions).
2. **Names every property** with a precise statement, an oracle, a
   generator, a fault profile, and an anchor to an existing
   v11.0 cross-layer law.
3. **Names every non-deterministic boundary** by reference to B1–B17
   and explains how each is injected for deferred settlement.
4. **Names a 7×7+composition fault matrix** with one harness per cell.
5. **Names 23 concrete test cases** the implementation must pass.
6. **Names 3 deferred-settlement-specific Goodhart traps** beyond the
   five named in the data layer.
7. **Names 5 open questions** for Phase 2 panel resolution.
8. **Reproducibility-from-seed is the load-bearing claim**. If a
   failure is not byte-replayable from `(seed, l19_snap, refdata_snap,
   inputs)`, the spec has not been satisfied — regardless of whether
   any individual property has passed.

What this document does **not** do:
- It does not propose a new map or storage shape (the StatesHome 3-map
  ruling is canonical and was deliberately respected).
- It does not propose a new conservation law (Λ5 + Λ15 are
  load-bearing; if a property cannot be derived from them, that's a
  spec gap to escalate, not a license to add a new law).
- It does not propose new boundaries beyond B1–B17 (none are needed;
  every non-determinism in the deferred-settlement window maps to an
  existing boundary).

The unyielding correctness requirement: **no property may be elided on
the grounds that it would slow CI or that the implementation team
"thinks they handled it." Every property in §1 must pass every CI
build, on every commit, with the per-stratum coverage targets
in §2.4 satisfied. Anything less is the absence of a property, not a
weak property.**

Goodhart's Law applies: if the test count or coverage % is the gate
rather than the per-property pass + per-stratum coverage, the gate is
gameable and the spec is undefended.

— correctness-architect
