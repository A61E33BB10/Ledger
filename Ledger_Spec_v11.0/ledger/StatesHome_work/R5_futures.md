# R5 — Futures lifecycle stress test of the four-map proposal

*Reviewer: GATHERAL. Target: `ProductTerms[u]` (immutable) / `UnitStatus[u]` / `WalletState[w]` / `PositionState[w,u]` (Option at accessor, monotone at carrier). Conservation: `Σ_w Δac(w,u) = 0` per event class, discharged at the handler.*

---

## 1. Sec 7.4 re-run (ALPHA, CH, ES, mult=50)

Notation: `ac` = `accumulated_cost`, `Δ` = handler delta. `pos` is a ledger balance, not state — shown for context.

| Event | `ProductTerms[ES]` | `UnitStatus[ES]` Δ | `WalletState[w]` Δ | `PositionState[ALPHA,ES]` Δ (ac) | `PositionState[CH,ES]` Δ (ac) | Σ_w Δac |
|---|---|---|---|---|---|---|
| Init (registration) | {mult=50, ccy=USD, expiry, product_id} frozen | stage=ACTIVE, last_px=None, last_dt=None | — (ALPHA, CH both plain trading) | None | None | 0 |
| T1 buy 10 @ 4500 | — | — | — | None → Some(ac=−2,250,000, first_touch=D0) | None → Some(ac=+2,250,000, first_touch=D0) | 0 ✓ |
| T2 buy 5 @ 4510 | — | — | — | −1,127,500 (→ −3,377,500) | +1,127,500 (→ +3,377,500) | 0 ✓ |
| T3 sell 8 @ 4520 | — | — | — | +1,808,000 (→ −1,569,500) | −1,808,000 (→ +1,569,500) | 0 ✓ |
| Settle @ 4530 | — | last_px=4530, last_dt=D0 | — | −16,000 (ac → −1,585,500); cash +16,000 in | +16,000 (ac → +1,585,500); cash −16,000 out | 0 ✓ |

Every row's `PositionState` deltas sum to zero structurally (two-leg trade = K=2 case of C2; VM settle = N-leg case, reduces to Σ_w q·Δp·mult=0 via ledger-balance conservation Σ_w q=0). `UnitStatus` is touched only on settle; `WalletState` not touched at all (no overlays). Handler emits one atomic `StateDelta` (C3).

## 2. Extended scenarios

### (a) Cross-CCP: ES@CME vs ES@ICE

**Ruling: `ccp` belongs to `ProductTerms`, not `PositionState`; the two listings are distinct units.** CME's ES and ICE's equivalent mini are separate instruments — different product specs, different deliverable pool, different settle prices published by different CCPs at different cutoffs. "Same product name" is a marketing fact, not a ledger fact. Model them as `u_CME` and `u_ICE`, each with its own `ProductTerms` (`clearinghouse`, `exchange`, `product_id`) and its own `UnitStatus` (including `last_settlement_price`). `PositionState[w, u_CME]` and `PositionState[w, u_ICE]` are independent; fungibility and regulatory netting (EMIR Art.4) happen at a higher aggregation layer over these two units — *not* inside unit state. This is exactly what §7.4 already says ("this is a per-wallet field" is misleading text; the correct statement is **per-unit, with different units per CCP**). See §5 adjustment A1.

### (b) EOM roll (ESM26 expires, ESU26 begins)

Each contract month is a distinct `u`: `ESM26`, `ESU26`. `ProductTerms` differ (expiry, first-notice date, product_id). `PositionState[w, ESM26]` persists across its lifetime, terminates with final-settlement VM that flushes `ac` to zero, then `UnitStatus[ESM26].lifecycle_stage` transitions ACTIVE→EXPIRED→SETTLED. The row is **not** deleted (monotone carrier): `Some(ac=0, first_touch=…)` remains, which is the honest state and supports tax-lookback and wash-sale audits. The roll trade is two independent trades — sell `ESM26`, buy `ESU26` — producing two `PositionState` touches on two different keys. Conservation holds per unit independently. ✓

### (c) Partial close then reopen (Option-at-accessor, monotone-at-carrier)

Trajectory for `(w=ALPHA, u=ES)`:
- t0: `None`
- t1 buy 10: `Some(ac=−a, first_touch=t1)`
- t2 sell 10: `Some(ac=0, first_touch=t1)` — flat but present
- t3 buy 5: `Some(ac=−a', first_touch=t1)` — `first_touch` is idempotent under re-touch
- t4 VM on flat session holders: accessor returns `Some(0)`, eligible for session MTM; `None` would skip incorrectly

This is exactly FORMALIS's counter-example from R4. The monotone-carrier + Option-accessor composition yields the right semantics. ✓

### (d) Limit-up / limit-down

Exchange caps the move at `±Δ_max`; the settle price **is** the limit price (by rule, not by clamp inside our code). `UnitStatus.last_settlement_price` stores whatever the CCP publishes — the limit price on locked days. The handler's formula `VM = ac − (−q·P_settle·mult)` is agnostic to whether `P_settle` reflects a free market or a circuit-breaker rule. **State is unaffected; the source-of-truth stays the published settle.** No special case. ✓ (Caveat: on consecutive limit days, the *economic* exposure diverges from the marked exposure — a risk-management fact, not a state-correctness fact.)

### (e) Vol-selling: 100 ES straddles, same wallet

Two units: `u_call_K`, `u_put_K`. Each straddle leg has its own `PositionState[w, u_leg]` carrying `ac`. Per-unit `UnitStatus` carries exercise/expiry/settlement-style, which is option-specific (American exercise flag, early-exercise stamps). Portfolio-level straddle-ness is an aggregation, not a unit. Conservation is per-unit; the two units are independent. ✓

## 3. Invariants

For every event above, `Σ_w Δac(w, u) = 0` per unit, structurally, discharged at the handler — K=2 for trades, K=N for VM settle via `Σ_w q(w,u) = 0`, vacuous for non-`ac`-touching events (stage transitions, price-only `UnitStatus` writes). Invariant `Σ_w ac(w, u) = 0` holds at every snapshot (including units with only a clearinghouse counterparty). ✓

## 4. Failure case search

**Found one — minor but real: the `PositionState.first_touch_date` field under replay-from-events.**

Definition: "date of first event on `(w,u)`." Under pure event-fold reconstruction from the move stream, this is deterministic. But under the refined proposal, `PositionState` is a state carrier, not a view over events — so `first_touch_date` is a cached projection. The failure mode: **a late-arriving trade correction for an earlier date can change `first_touch_date`**. The snapshot cached in the monotone carrier is now inconsistent with the authoritative event log. This is not an arbitrage or conservation failure, but it violates the "state = fold of events" discipline stated in R4 (Jane Street §2).

This is not a reason to reject the proposal; it is a reason to tighten the spec. See A3.

## 5. Recommended adjustments (futures-specific)

- **A1 (cross-CCP).** Rewrite the §7.4 `clearinghouse` bullet: **`clearinghouse`, `exchange`, `product_id` are fields of `ProductTerms[u]` — CME-ES and ICE-ES are distinct units.** Delete the misleading "per-wallet field" phrasing. Regulatory cross-CCP netting is a higher-layer aggregation, explicitly out of unit-state scope.
- **A2 (UnitStatus on listed).** `last_settlement_price: Option[Decimal]` and `last_settlement_date: Option[Date]` live in `UnitStatus[u]` (shared across all holders of that unit). This is a one-line clarification to §7.4's per-contract state block, with no semantic change, just consistent naming against the four-map schema.
- **A3 (first_touch immutability).** `first_touch_date` in `PositionState` is set on the `None → Some` transition and never updated thereafter, even on correction. Corrections flow through a `CorrectionEvent` that rewrites `ac` but preserves `first_touch`; if the correction predates the current `first_touch`, the handler emits a dedicated `FirstTouchRevisionEvent` with its own audit trail. Alternative (simpler): **drop `first_touch_date` from `PositionState` and derive it from the event log when needed** — consistent with "state = fold of events, not a cache of derived facts."
- **A4 (expiration → monotone retention).** On `ESM26` final-settle, transition `UnitStatus.lifecycle_stage` to `SETTLED` but **do not** delete `PositionState` rows. Downstream tax, P&L attribution and 1099-B generation need the flat-with-history row. This matches monotone-carrier discipline.
- **A5 (handler emits one atomic StateDelta for VM settle).** The VM handler writes `UnitStatus.last_*` and every touched `PositionState[w,u].ac` in a single `StateDelta`, committed atomically (C3 from R4-FORMALIS). Explicit in §7.4 text.
- **A6 (intraday trade = state-only, no moves).** §7.4 already says intraday trades emit no cash moves; make it explicit that they still emit a `StateDelta` touching `PositionState` only. Conservation check (layer 2) still runs — on `ac` deltas, not on cash.

No failure on arbitrage, conservation, or static-arbitrage-analogue invariants. The proposal survives the futures stress test with the six adjustments above.

— GATHERAL.
