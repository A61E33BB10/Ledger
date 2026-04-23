# R5 — Untraded Units Stress Test

*Reviewer: Correctness Architect. Target: four-map proposal (`ProductTerms[u]`, `UnitStatus[u]`, `WalletState[w]`, `PositionState[w,u]`). Focus: units that EXIST but have NO holders.*

---

## The Partiality Story (Ruling)

| Map | Domain | Accessor returns | Totality |
|---|---|---|---|
| `ProductTerms[u]` | registered `u` | `ProductTerms` | **Total on registered `u`** |
| `UnitStatus[u]` | registered `u` | `UnitStatus` (product-declared defaults at registration) | **Total on registered `u`** |
| `PositionState[w,u]` | `(w,u)` ever touched by an event | `Option<PositionState>` | **Partial; accessor returns `Option`; carrier monotone** |
| `WalletState[w]` | `w` with overlay contract attached | `Option<WalletOverlay>` | **Partial; sparse; `None` = plain trading wallet** |

Three totality disciplines:
- **Registration-total** (`ProductTerms`, `UnitStatus`): registration is the induction base; defaults product-declared.
- **Monotone-partial** (`PositionState`): `None` = never addressee of any event on `(w,u)`; `Some(zero_P)` = addressee, currently flat. Once `None → Some`, never regresses.
- **Contract-sparse** (`WalletState`): present iff ≥1 overlay contract (CSA, managed account, subscription line) attached.

---

## Scenario-by-scenario

**(1) ES future listed, not yet traded.** `product_terms(u)` immediate. `unit_status(u) = {lifecycle=ACTIVE, last_settlement_price=None, clearinghouse=CME_CH_ID}` — `last_settlement_price` is an inner `Option<Decimal>`; the outer accessor is total. `position_state(w,u) = None` ∀ `w`. `holders_of(u) = ∅`.

**(2) OTC bond amendment, no desk trades.** `product_terms(u)` immediate with amended terms. `unit_status(u) = {lifecycle=ACTIVE, paid_coupons=∅, matured=False}`. First desk trades: `position_state(desk, u): None → Some(P_init)`. See Q3 for new-u vs versioned-terms.

**(3) Listed QIS certificate, subscriptions T+1.** `unit_status(u) = {lifecycle=ACTIVE, current_weights=defaults, last_rebalance=None}`. Rebalance events can fire day T and update `UnitStatus` without any `PositionState` row — strategy-level state lives on `UnitStatus[u_Q]`, not on any `(w, u_Q)` row. T+1 first subscriber: `position_state(w, u_Q): None → Some(P_init)`.

**(4) OTC swap confirmation pre-execution.** `unit_status(u)` defaults, `lifecycle=ACTIVE` (or `PENDING` if product declares a pre-exec stage). `position_state(w,u) = None` until execution. At execution, first touch creates `Some` for both counterparties.

All four are well-typed trajectories through `None ≤ Some(zero_P) ≤ Some(v)` (R4 Formalis §1).

---

## Direct answers

**Q1 (unit_status of untraded).** Fully initialised with product-declared defaults at registration. Total on registered `u`. Confirmed by R4 Formalis §5.

**Q2 (product_terms accessibility).** Yes, immediate at registration. Total on registered `u`. `ProductTerms` is the first write; registration is atomic (R4 Jane Street §2).

**Q3 (bond amendment: version history or new u_id?).** R4 Formalis C6 rules **new `u_id` per amendment**. R4 Jane Street §2 rules **`Map[UnitId, NonEmptyList[TermsVersion]]`** append-only. *The one live ambiguity.* Resolution — **two-track by fungibility predicate**: fungibility-preserving amendments (coupon step-up on credit event, CSA eligible-collateral change) append to `ProductTerms[u]`; re-allocating `u_id` would break `PositionState[w,u]` and force synthetic novation. Fungibility-breaking amendments (restructuring that re-ISINs the bond) allocate fresh `u` with a `SupersededBy(u_old → u_new)` edge on both `UnitStatus`. Fungibility predicate product-declared, checked at amendment time.

**Q4 (totality of accessors).** `unit_status(u)`, `product_terms(u)` **total on registered `u`**. `position_state(w,u)` returns **`Option`**. `wallet_state(w)` returns **`Option<WalletOverlay>`**. Confirmed.

**Q5 (first-touch semantics).** Row created **only on first touch** (monotone-partial). Catastrophic `|W| × |U|` avoided. `holders_of(u)` on an untraded `u` is the empty iterator. Before first touch: `None`; after first touch, position goes flat: `Some(zero_P)` — **not** `None` (monotone). Verified against R4 Formalis §1 replay counter-example.

**Q6 (ACTIVE → EXPIRED without any PositionState row).** Yes, permitted and correct. An untraded listed option can expire worthless: `UnitStatus[u]` transitions `ACTIVE → EXPIRED` via an `ExpiryEvent` handler that emits no moves (no `PositionState` rows to update, no cash legs). Conservation discharges vacuously (`Σ_w Δac = 0` over the empty set). The lifecycle state machine on `UnitStatus` is **independent** of the `PositionState` carrier — they evolve on separate channels joined only at event-handler time.

**Q7 (idempotent re-registration).** Re-registering the same `u_id` MUST be a **hard error**. A no-op hides caller confusion; a defaults-reset would clobber `UnitStatus` mutations (settlement prices recorded since initial registration) and violate §3.6 identity-immutability. Uniqueness enforced at registration (§3.5.1). Atomic-or-reject.

**Q8 (corporate action on un-held instrument).** Well-defined. Stock split on zero-holder `u`: handler fires, `UnitStatus[u]` updates (split ratio, adjusted contract-spec), no `PositionState` row mutates (none exist), conservation vacuous. Symmetric to Q6. Event recorded with full audit trail; if `u` later traded, split history queryable.

**Q9 (ambiguity or failure).** Ambiguity: Q3 amendment discipline. Failure mode to guard: a handler iterating `holders_of(u)` and assuming non-empty (e.g. dividend dividing by `|holders|`). Property obligation: every handler total on `holders_of(u) = ∅`.

---

## Adjustments to the refined proposal

1. **Add C7 (registration-total UnitStatus).** `UnitStatus[u]` is initialised at registration with product-declared defaults. Product type declares defaults in Tier-2 Product Registry; Unit Store applies them at Tier-3 registration.
2. **Add C8 (amendment discipline, two-track).** Fungibility-preserving amendments append to `ProductTerms[u]`; fungibility-breaking amendments allocate fresh `u` with `SupersededBy` edge. Fungibility predicate lives on the product.
3. **Add C9 (vacuous-conservation discharge).** Handlers firing on zero-holder units discharge `Σ_w Δ = 0` vacuously; explicit in the per-event-class proof obligation (extends C2).
4. **Add C10 (re-registration is error).** Duplicate `u_id` at registration is rejected, not tolerated.
5. **Add property obligation.** Every handler is total on `holders_of(u) = ∅`.

**Verdict:** The four-map proposal handles untraded units cleanly. Partiality story is three-tiered (registration-total, monotone-partial, contract-sparse) and fully specified. One live ambiguity on amendment discipline, resolved by fungibility-predicate two-track rule.

— Correctness Architect, sealed.
