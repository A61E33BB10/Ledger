# R4 — FORMALIS: Adversarial re-review of the four-map proposal

*Committee: Leroy (chair), Coquand, Huet, Paulin-Mohring, de Moura, Avigad.*
*Target: `ProductTerms[u]` (immutable) / `UnitStatus[u]` / `WalletState[w]` / `PositionState[w,u]`; conservation at the handler; per-CCP in `PositionState`.*

---

## 1. Option vs. Monotone: ruling

**Ruling.** `PositionState` is `Option<P>` at the accessor; carrier is **monotone** (rows, once created, are never GC'd). Lattner's type discipline plus Feynman's carrier rule. They compose, they do not conflict.

**Replay counter-example.** Trace `T1: buy(w_B, u); T2: sell(w_B, u); T3: VM-settle(u, p'')`. Under GC-on-zero-row: replay of `T1;T2` drops the row, `T3` skips `w_B`, loses the intrasession MTM the exchange actually posts. Under retain-zero-row without Option: `T1;T2` yields `Some(zero)`, `T3` credits correctly — but `Some(zero)` is now indistinguishable from an initial row that was never touched (no such row exists under this design, but once you introduce *any* zero-initialisation pathway, e.g. by a netting reset, you cannot distinguish). Under monotone + Option: `None` means "never an addressee of any event"; `Some(zero)` means "addressee, currently flat, eligible for session VM." Distinct. Observable. Deterministic.

**Is the distinction observable from outside state?** Yes, by scanning moves for any leg with `(w,u)`. But that is O(|moves|); carrying the `Option` is a memoisation with a proof of agreement, not redundant data. Admissible under Paulin-Mohring extraction.

**Concrete events that need "ever touched".** VM settle on currently-flat ex-holders; wash-sale / cumulative-tax lookbacks; corporate-action record-date entitlements where the wallet entered and exited within the window. None reduce to "current net quantity non-zero."

**Idempotency.** Option gives a three-point lattice `None ≤ Some(zero_P) ≤ Some(v)`; idempotency is "lattice point unchanged on re-apply" — structural. Pure-zero-row collapses the bottom two, forcing an arithmetic equality on `Decimal` plus an auxiliary proof that zero-row and absent-row coincide. **Option makes per-event idempotency easier to prove.**

## 2. Structural zero-sum at the handler — sufficient?

**Per-trade `buyer+seller=0` is necessary but not sufficient.** Generalise to: *every event handler's `StateDelta` satisfies `Σ_w Δac(w,u) = 0` for every conserved field, proved per event class.*

- **Non-trade lifecycle.** VM settle fans out to N holders; zero-sum follows from `Σ_w q(w,u) = 0` (balance-layer conservation) composed with the per-leg rule `Δac(w) = -q(w)·(p_new−p_old)·mult`. Coupon payments and dividends are not events on `ac`; the obligation is vacuous because `ac` is not touched. Index transitions and ISIN novations touch `ac` and require an explicit per-class proof.
- **N > 2 legs.** A K-leg rebalance or QIS turnover decomposes into K trade-legs, each with a two-leg zero-sum; induction on K preserves Σ_w = 0. No new machinery.
- **Corporate actions / resets.** Stock split multiplies every `ac(w,u)` by `1/n`; invariant preserved because 0 is a fixed point of scalar multiplication. Every new event class carries a proof obligation, discharged once, forever.

**Verdict on §7 text.** Restate as: "*Per-event, per-conserved-field, `Σ_w Δ = 0` structurally, proved per event class. The two-leg trade is the K=2 instance.*" The refined proposal's phrasing "per-trade structural zero-sum" is the K=2 case only.

## 3. Cross-sector atomicity

Yes, VM settle modifies `UnitStatus` (`last_settlement_price`) and every relevant `PositionState` row (`ac`). **The `StateDelta` must be applied as one transaction across all four maps; partial application is rejected by the core.** The current proposal names the handler output but does not mandate atomicity; make it explicit in §7.

## 4. Managed-account composition

QIS-as-wallet `w_Q` has its own `WalletState[w_Q]`. Client `w_C` holding `u_Q` units has `WalletState[w_C]`. **Cross-wallet reads are prohibited.** Strategy-level NAV and accruals are published by the QIS's handlers into `UnitStatus[u_Q]` — the single shared channel. `w_C`'s fee engine reads `WalletState[w_C]` and `UnitStatus[u_Q].NAV`; never `WalletState[w_Q]`. Enforcement: capability scoping at the accessor; `view.wallet_state(w)` takes `w` from the caller's authenticated context, not from arbitrary input. Without this, the schema leaks by default.

## 5. Untraded unit

`view.unit_status(u)` is **total** for every registered `u`. The Unit Store creates `UnitStatus[u]` at registration with product-declared defaults: `lifecycle = ACTIVE`, `last_settlement_price = None`, `paid_coupons = ∅`. The *inner* `Option<Decimal>` on `last_settlement_price` is product-level; the *outer* accessor never fails. `PositionState[w,u] = None` for every `w` until first touch. Lifecycle totality is preserved; the delist-same-day-never-traded replay case has a well-typed trajectory `ACTIVE → DELISTED`, fully idempotent.

---

## CONDITIONAL-PASS set

The refined four-map proposal PASSES conditional on all of:

- **C1 (Option + monotone).** `PositionState` accessor returns `Option<P>`. Rows, once created, are never GC'd. `None` and `Some(zero_P)` are distinct observable states.

- **C2 (handler-level conservation, generalised).** `Σ_w Δac(w,u) = 0` structurally per event class, proved for every class that touches `ac`. Two-leg trade is one case; K-leg rebalance, VM settle, corporate actions each carry explicit per-class proofs. Non-trade events that do not touch `ac` discharge vacuously.

- **C3 (atomic `StateDelta` application).** A single event's `StateDelta` is applied as one transaction across `UnitStatus`, `WalletState`, `PositionState`. Partial application rejected.

- **C4 (capability-scoped `WalletState`).** Cross-wallet `WalletState` reads are forbidden. Strategy-level exports flow through `UnitStatus` only.

- **C5 (`UnitStatus` totality).** `UnitStatus[u]` is total for every registered `u`; product-declared initial values at registration. Product-internal `Option` fields (e.g. `last_settlement_price`) are independent of accessor totality.

- **C6 (`ProductTerms` immutability by construction).** No writer on `ProductTerms` in the API surface. A product amendment allocates a new `u`.

Without C1 replay is non-deterministic across GC boundaries. Without C2 the global invariant is asserted, not proved. Without C3 cross-sector events are not atomic. Without C4 managed-account composition leaks. Without C5 lifecycle totality fails. Without C6 `ProductTerms` is just a renamed mutable field.

Files reviewed: `/home/renaud/A61E33BB10/output/v10.3/StatesHome_work/R1_*.md`, `R2_*.md`, `R3_*.md`.

— FORMALIS, sealed this day.
