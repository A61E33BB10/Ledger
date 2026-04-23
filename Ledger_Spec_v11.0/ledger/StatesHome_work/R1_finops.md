# R1 — Where Does Unit State Live? A Fin-Ops Proposal

**Artefact under review:** `ledger_v10.3.tex` §2, §3, §6, §7
**Question:** Should state attach to the **unit**, the **wallet**, or the **(wallet, unit) pair**?

## 1. First-principles framing

Three orthogonal identity axes: **Unit `u`** (the contract — strike, expiry, CCP, CSA, ISIN; shared by all holders), **Wallet `w`** (the holder — book, client, CCP, custodian; spans every instrument the holder touches), **Pair `(w, u)`** (the position; the atom of lifecycle).

A field belongs on the axis it varies along. Per-position data on a unit collapses distinct positions, destroying conservation. Per-contract data on a wallet duplicates across holders and breaks idempotency at the next corporate action. Per-holder profile on `(w, u)` scatters across every contract the holder touches — the fee engine can't find it.

## 2. The four test cases

### 2.1 Futures

| Field | Axis |
|---|---|
| `multiplier`, `currency`, `expiry`, `tick_size`, `underlying`, `ccp` | **u** |
| `last_settlement_price`, `last_settlement_date`, `lifecycle_stage` | **u** |
| `accumulated_cost`, per-wallet CCP binding (multi-CCP case, §7 line 1168) | **(w, u)** |

The invariant `Σ_w ac(w, u) = 0` exists only if `ac` is keyed by `(w, u)`: on `u` alone there is nothing to sum; on `w` alone the contract context is lost.

### 2.2 Managed account

| Field | Axis |
|---|---|
| `mandate_id`, `reference_currency`, `client_lei`, `CSA_id`, fee schedule (HWM hurdle, mgmt bps, perf %) | **w** |
| `HWM`, `accrued_mgmt_fee`, `accrued_perf_fee`, `last_nav_strike_date`, `benchmark_weights_target`, `mandate_breach_flags`, `current_nav` | **w** |

HWM cannot live on a unit — it is a property of holder performance, not of any contract — nor on `(w, u)`, since the MA holds many units and HWM is one scalar across all of them. Canonical **wallet-scoped** case.

### 2.3 QIS trading futures, held inside a managed account

All three axes in play — the hardest case.

| Field | Axis |
|---|---|
| QIS `rule_id`, `universe`, `rebalance_schedule`, `leverage_cap`, `barrier_levels` | **u** (the QIS is itself a unit) |
| QIS `current_weights`, `last_rebalance_date`, `triggered_barrier`, `vol_target_state` | **u** |
| Client subscription balance in the QIS | `(w_client, u_QIS)` — i.e., the ledger balance |
| Futures `accumulated_cost` held by the QIS execution wallet | `(w_QIS_exec, u_ES)` |
| Client HWM, accrued fee on the MA wrapper | `w_client` |

Clients hold the QIS via a balance `w_client(u_QIS)`, not cloned copies of its futures. The QIS execution wallet's futures ac is keyed by `(w_QIS_exec, u_future)`, never duplicated into client wallets. §6–§7 already composes this correctly — but only because state is split across all three axes.

### 2.4 Listed option registered but never traded

On listing day the Unit Store holds `strike`, `expiry`, `type`, `multiplier`, `exchange`, `underlying`, `lifecycle_stage = ACTIVE` — all per-unit. **No `(w, u)` state exists for any wallet.** A `(w, u)` row materialises only when the first move lands.

Decisive case: if state were wallet-scoped, the system could not represent a contract that exists but nobody owns. ``The contract exists'' vs. ``someone has a position'' *is* the `u`-keyed vs. `(w, u)`-keyed distinction.

## 3. Idempotency of lifecycle events

Idempotency asks ``have I already processed event `e` for holder `h` of contract `u`?'' The lookup key equals the event's scope.

- **Per-unit events** (coupon announcement, option expiry, swap fixing, QIS rebalance): occur once per `u`. Apply-once keyed on `u` — e.g. `state[u].paid_coupons[date] = True`. The generated cash moves are `(w, u)`-scoped; per-holder idempotency is automatic because the immutable move stream already records `(source=u, event_id=e, dst=w)`.
- **Per-holder events** (CSA margin call, mandate breach, fee accrual): keyed on `w`. `state[w].last_margin_call_date = D` runs the CSA once per counterparty per day.
- **Per-position events** (futures VM settle): keyed on `(w, u)`. Reset of `ac(w, u)` to target; replay is a no-op (`ac - target = 0`).

Mono-axis designs fail: unit-only cannot answer ``did this holder's fee run?''; wallet-only forces the coupon question `|W|` times instead of once.

## 4. Audit trail and balance-sheet substantiation

External records are keyed differently: CCP statements (SPAN/TIMS) and custodian positions (MT535) are `(w, u)`; prime-broker margin is `w`-aggregated; exchange contract-spec feeds and issuer coupon notices are `u`-only; client NAV statements are `w`-only.

**Internal state must be keyed at the same granularity as the external record it reconciles against.** Putting `accumulated_cost` on `u` alone breaks CCP reconciliation (one line per member per contract). Putting `expiry` on `w` forces custodian feeds to carry expiry on every line (they don't) — a join through a reference database, i.e. the multi-source-of-truth break §2.6 forbids.

## 5. Double-entry conservation

`Σ_w ac(w, u) = 0` is expressible only if `ac` is indexed by `(w, u)`. Same for `Σ_w w(u) = 0` — the column-sum of the `(w, u)` balance matrix at fixed `u`. **Conservation is structurally a `(w, u)` property on any quantity that obeys it** — the strongest first-principles argument for position-level state at `(w, u)`.

## 6. Regulatory reporting

EMIR UTI, SFTR, MiFID II RTS 22, CFTC Part 45 — every trade report carries product identity (ISIN, UPI, contract spec) and reporting party (LEI). The report is by construction a `(w, u)` object. Clean axis separation — product terms on `u`, counterparty profile on `w` — reduces reporting to a join. Mixed axes force de-duplication and consistency checks that create breaks.

## 7. Concrete signatures by product family

```
Bond            u: isin, coupon_schedule, maturity, currency, lifecycle_stage,
                   paid_coupons[date]->bool, matured
                w: —     (w,u): —  (position = balance; cash derivable from moves)

Equity          u: isin, exchange, lifecycle_stage, last_div_ex_date, div_history
                w: —     (w,u): —

Listed future   u: contract_spec, multiplier, expiry, ccp,
                   last_settlement_price, last_settlement_date, lifecycle_stage
                w: —     (w,u): accumulated_cost, ccp_binding (multi-CCP)

OTC swap (IRS)  u: cdm_trade_ref (counterparty + CSA), notional, fixed_rate,
                   schedule, paid_fixings[date]->bool
                w: —     (w,u): —  (OTC trade = unique unit)

TRS             u: trade_ref, reference_virtual_ledger_id, notional,
                   financing_spread, reset_dates, last_reset_nav
                w: —     (w,u): —

Managed acct    u: n/a   (w is the product)
                w: mandate_id, HWM, accrued_mgmt_fee, accrued_perf_fee,
                   last_nav_date, benchmark_weights, breach_flags,
                   fee_schedule_terms, csa_ref, current_nav
                (w,u): per-position state of whatever the MA holds

QIS strategy    u: rule_id, universe, rebalance_schedule, current_weights,
                   last_rebalance_date, triggered_barrier, vol_target, leverage_cap
                w: — (client uses MA fields)
                (w,u): redemption-gate flags; QIS exec wallet holds
                       (w_qis_exec, u_future): accumulated_cost separately
```

## 8. Recommendation

**Adopt a three-keyed state model and make the key part of the type system.** Every field declares its key at definition time: `UnitState[u]`, `WalletState[w]`, `PositionState[w, u]`. Accessors take the appropriate key; fields cannot be silently promoted or demoted across axes.

v10.3 already does this in substance but states it loosely in §7.3 (``per-unit for most instrument types. For instruments with per-wallet state, the state dictionary is per (wallet, unit) pair''). Replace with:

> Product state is a tagged union of three keyed maps: `U → UnitFields`, `W → WalletFields`, `W × U → PositionFields`. The lifecycle function becomes `f : (u, w?, UnitState[u], WalletState[w]?, PositionState[w,u]?, md) → (moves, ΔUnit, ΔWallet, ΔPosition)`, with `w` optional for per-unit-only events and required for per-position events.

This preserves every existing invariant, eliminates the ad-hoc qualifier, makes the MA/QIS/TRS composition of §6 a schema consequence rather than an exception, and aligns internal state keys with the natural keys of external reconciliation sources — discharging §8's substantiation mandate by construction.
