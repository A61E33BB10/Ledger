# R5 — QIS Stress Test: 12m Momentum on US Index Futures

*Practitioner stress test. Check arbitrage (conservation), calibration (fit), dynamics (idempotence), hedging (handler correctness).*

## 1. Taxonomy (final)

Wallets: `w_Q` (strategy exec), `w_C` (client), `w_Mgr` (manager cash), `w_CME` (CCP).
Units: `u_QIS`, `u_ES`, `u_NQ`, `u_YM`, `USD`.

| Map | Key | Fields | Mutator |
|---|---|---|---|
| `ProductTerms[u]` | `u` | For `u_QIS`: `{rebalance_freq=M, vol_target=0.20, barrier=-0.30, universe={ES,NQ,YM}, sc_index_start=100.0, issue_date, lookback=12m}`. For `u_ES`: `{multiplier, expiry, tick}`. Immutable post-registration. | Unit Store at listing. |
| `UnitStatus[u]` | `u` | For `u_QIS`: `{lifecycle_stage ∈ {LISTED,ACTIVE,HALTED,CLOSED}, last_rebalance_date, current_weights: {ES: w_ES, NQ: w_NQ, YM: w_YM}, cumulative_return, nav_index, vol_realised_ex_ante, triggered_barrier, hwm_strategy}`. For `u_ES`: `{lifecycle_stage, last_settle_price}`. | Strategy-level lifecycle handler (`rebalance`, `barrier_check`, `daily_settle_index`). |
| `WalletState[w]` | `w` | For `w_C`: `{mandate, benchmark, fee_schedule, accrued_mgmt_fee, accrued_perf_fee, hwm_client}`. For `w_Q`: `{strategy_fee_accrual, manager_reference}` (small). | Wallet-level handlers (subscription, fee crystallisation). |
| `PositionState[w,u]` | `(w,u)` | For `(w_Q, u_ES)`, `(w_Q, u_NQ)`, `(w_Q, u_YM)`: `{accumulated_cost, ccp_binding=CME}`. For `(w_C, u_QIS)`: **None** in the generic case. | Trade / settlement handler. |

Option at accessor (`get_position` returns `None` for untraded `(w,u)`), Monotone at carrier (rows never deleted; CLOSED rows with balance 0 persist), Conservation at handler (`Σ_w Δac = 0`, `Σ_w Δ(QIS units) = 0` at mint/burn).

## 2. Answers

**Q1 — Who modifies `UnitStatus[u_QIS]` vs `PositionState[w_Q, u_ES]`?**

Same event, one transaction. The `rebalance` lifecycle function at month-end reads `(UnitStatus[u_QIS].current_weights, W(w_Q), market_prices)`, computes target futures notionals (with vol targeting), and emits a single atomic transaction:
- Moves: futures deltas between `w_Q` and `w_CME` for ES/NQ/YM.
- Position deltas: `Δac` written to `PositionState[w_Q, u_ES]` etc.
- Unit-status delta: `UnitStatus[u_QIS] ← {current_weights := new, last_rebalance_date := t, vol_realised := σ̂}`.

One `BusinessEvent`. Conservation checked once. Idempotent because `last_rebalance_date` guards re-execution.

**Q2 — Barrier-hit event.**

If `cumulative_return ≤ -0.30`, the handler emits **one transaction** with three kinds of deltas:
1. Unit-status: `lifecycle_stage: ACTIVE → HALTED`, `triggered_barrier: true`, `current_weights := 0`.
2. Moves: close all futures in `w_Q` against `w_CME` at the barrier-trigger price.
3. Position: `PositionState[w_Q, u_ES].ac` realises to cash and goes to 0.

One transaction, many moves. This is correct: barrier is a state transition and the trigger price must be the same across legs. Splitting it would let a partial failure leave the strategy mid-close — violating the Single-Coordinate Move Principle at the *aggregate* level.

**Q3 — Subscription.**

Client delivers cash at month-end NAV. One transaction:
- Move: `w_C → w_Q` of `N` USD.
- Mint: `w_Q → w_C` of `N / NAV_t` units of `u_QIS` (from a sentinel issuer wallet `w_issuer`, or via a signed mint primitive — either way, conservation holds because QIS unit supply is tracked).
- `WalletState[w_C].hwm_client` initialised (or updated if existing subscriber — see Q4).
- `UnitStatus[u_QIS]` **unchanged** (strategy-level state is subscriber-agnostic; follow-on rebalance handles new cash).

Maps touched: balances, `WalletState[w_C]`, `UnitStatus[u_QIS].current_weights` **only if** subscription triggers immediate re-weighting (typically deferred to next rebalance — cleaner).

**Q4 — Redemption and HWM.**

Client-specific HWM for performance fee is a scalar over *the client's P&L in this strategy*. Two candidate homes:

- `WalletState[w_C].hwm_client` — plain wallet-level scalar.
- `PositionState[w_C, u_QIS].hwm` — per-holding.

**RULING: HWM lives in `PositionState[w_C, u_QIS]`**, not `WalletState[w_C]`.

Reasoning (Karpathy substitution rule applied strictly): HWM depends on *which strategy* the client holds. If `w_C` subscribes to both `u_QIS1` and `u_QIS2`, a single `WalletState[w_C].hwm` collapses two distinct economic marks into one. HWM varies over `(w, u)` — therefore it belongs on `(w, u)`.

This resolves the earlier Karpathy framing (R3) which put HWM on `W`. That was correct **only** when the wallet's mandate binds to a single strategy. For a multi-strategy subscriber, HWM is a per-position mark and `PositionState[w_C, u_QIS]` is its home. The "mandate" itself (benchmark, fee schedule definition) stays on `WalletState[w_C]` because the schedule is client-level; the *mark* is per-holding.

This overrides the R3 line "HWM is a scalar over the account's performance" — the account-level HWM is a projection: `hwm_account(w) = Σ_u hwm(w, u) · balance(w, u) · NAV_u`. When only one strategy is held, the projection equals the per-position value, and R3 is a correct shortcut.

**Q5 — Manager's aggregate book.**

Under the 4-map scheme, manager aggregate exposure is a **pure query**, not stored:
```
manager_exposure(u_ES) = Σ_{w : manager_reference(w)=Mgr} (balance(w, u_ES) · multiplier · P(u_ES))
```
with `manager_reference` a tag on `WalletState[w_Q]`. No extra map. No reconciliation between `ManagerBook` and underlying wallets — the projection *is* the book. This is exactly the self-consistency principle (tex §2.7): aggregates are derived, not stored.

**Q6 — Full wind-down.**

`UnitStatus[u_QIS].lifecycle_stage → CLOSED` after final NAV strike + cash redemption. For every client `w_C` holding QIS units:
- Burn transaction: `balance(w_C, u_QIS) → 0` in exchange for final NAV cash.
- `PositionState[w_C, u_QIS]`: **kept as a row**, balance-projection = 0, status = CLOSED, last_hwm frozen for audit. *Do not delete the row.*

Monotone carrier: rows are append-only. This is required for time travel (R3 §Time Travel). A cloned view at any earlier `t` must see the row with the correct historical HWM. If we deleted rows at CLOSED, `clone_at(t)` would be undefined on that key.

## 3. Where the 4-map proposal gets ambiguous

**The friction point: mid-month subscriptions and per-subscriber cost basis.**

The proposal says `PositionState[w_C, u_QIS] = None for most cases`. But HWM forces it to be populated for every subscriber. That is fine. The real ambiguity is this:

**When a client subscribes mid-month at NAV = 112.3, whose state captures the entry price?**

Candidates:
(a) `PositionState[w_C, u_QIS].entry_nav` — per-position cost basis. Natural.
(b) `WalletState[w_C].cost_basis[u_QIS]` — a dict keyed by `u` on the wallet. This is `PositionState` in disguise.
(c) Reconstruct from the move stream — pure derivation.

The 4-map proposal implicitly picks (a), and that is consistent. But HWM vs cost-basis have **different update rules**: cost basis is set once at subscription and persists through redemption; HWM ratchets on each NAV observation. Two per-position fields with different write frequencies sharing `PositionState[w_C, u_QIS]` is fine structurally, but the handler contract must be explicit about which event writes which field. Otherwise we repeat the Minsky trap: a field living in the right *map* but mutated by the wrong *handler*.

**Recommendation:** tag each field in `PositionState` with its canonical handler (`entry_nav ← subscription_handler`, `hwm ← nav_strike_handler`). This is discipline at the handler layer, not the storage layer — consistent with R3's thesis that invariants live in handlers.

## 4. Verdict

The 4-map scheme handles the QIS cleanly on all six questions. One clarification earned: **HWM is `(w, u)`-indexed, not `w`-indexed**. Otherwise no breakage. Ship it.

