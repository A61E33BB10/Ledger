# R6 — FORMALIS: Final ruling on map count and amendment discipline

*Committee: Leroy (chair), Coquand, Huet, Paulin-Mohring, de Moura, Avigad.*
*Adversarial pass R6 over R4_formalis + R5_{managed_account, qis, futures, untraded}.*

---

## 1. Field taxonomy by key

- **Type U**: `ProductTerms[u]` (multiplier, ccp, expiry, mandate text, fee schedule, benchmark pointer, index methodology); `UnitStatus[u]` (lifecycle, last_settle_px, index_value, current_weights, nav_index, strategy-level HWM where product-defined).
- **Type (W,U)**: `accumulated_cost`, per-position `ccp_binding`, per-trade OTC lifecycle, per-subscriber `entry_nav`, `hwm`, `accrued_perf_fee`, `accrued_mgmt_fee`, `benchmark_nav_at_inception`, `mandate_breach_flags`.
- **Type W** (economic, u-agnostic): candidates enumerated below.
- **Global**: price vector, clock, config — out of scope.

## 2. Economic Type-W candidates: disposition

| Candidate | R5 home | Disposition |
|---|---|---|
| `HWM` (client) | R5_mgd §1 W; R5_qis Q4 `(w, u_QIS)` | **Collapses to (W,U).** Multi-strategy subscriber makes W-keying wrong; Karpathy-substitution settles it. |
| `accrued_{mgmt,perf}_fee` | R5_mgd §1 W | **Collapses to (W, u_MA).** R5_mgd §6 itself promotes overlay-keying to requirement under multi-mandate composition. |
| `benchmark_nav_at_inception` | R5_mgd §1 W | **Collapses to (W, u_MA).** C's inception snapshot of *this* mandate; another mandate on same W gets its own. |
| `mandate_breach_flags` | R5_mgd §1 W | **Collapses to (W, u_MA).** Flags are per-mandate-constraint. |
| `subscription_cursor`, `redemption_cursor` | R5_mgd §4 W | **Collapses to (W, u_MA).** Defined only where `u_MA` is attached; plain trading wallet has no S/R channel. |
| wallet permissions, audit cursor | — | **System state, not economic.** Out of scope of ledger schema. |

**Result.** Every economic W-candidate is `(W, u_MA)`-keyed or is a system-layer fact. **The W sector is empty of economic state.**

## 3. `u_MA` survives R1_dirac's objection

R1_dirac's `u_∅` had no issuer, no conservation partner — broke `Σ_w w(u) = 0` by fiat. `u_MA` is structurally different:

- Real smart contract with `ProductTerms[u_MA]` row (Sec 6; R5_mgd §2).
- Issued by manager `w_A`, held by client `w_C`: `w_C(u_MA)=+1`, `w_A(u_MA)=−1`, `Σ_w w(u_MA)=0`. Standard issuance.
- Amendment allocates `u_MA'` with atomic re-subscription: `Σ_w Δw(u_MA) = Σ_w Δw(u_MA') = 0`.

Type-correct, conservation-preserving. Placing per-mandate instance state at `PositionState[w, u_MA]` is sound.

## 4. Decision: **3 maps, not 4**

Collapse `WalletState` into `PositionState`. Schema:

- `ProductTerms[u]` — versioned append-only (C8).
- `UnitStatus[u]` — shared mutable per-unit observables.
- `PositionState[w, u]` — all per-(holder,unit) economic state, overlay-keyed by `u_MA` / `u_QIS` / `u_futures` / etc.

Justification: §2 eliminates every economic W-candidate; §3 legitimises `u_MA`. W-sector was a redundant axis. Coquand: definitionally equal keyings should not produce distinct maps. Leroy: C3 atomic commit reduces from 3-way to 2-way, shrinking TCB.

## 5. Amendment rule: fungibility predicate IS implementable

Signature (total over product-declared metadata):

```
is_fungibility_preserving :
    ProductTerms[u] × TermsAmendment → {Preserving, Breaking}
```

Decision procedure: each `ProductType` (bond, future, swap, QIS, MA) declares the predicate as a finite classifier over the amendment's mutated field set against a product-declared allow-list. Examples (R5_untraded Q3): coupon step-up on credit event → Preserving; CSA eligible-collateral change → Preserving; bond restructuring with new ISIN → Breaking; MA benchmark swap → Breaking; MA fee-rate tweak within declared band → Preserving.

- **Preserving** → append `TermsVersion` to `ProductTerms[u]`; `PositionState[w,u]` untouched; audit retained.
- **Breaking** → allocate `u_new`; `SupersededBy(u_old → u_new)` on both `UnitStatus`; atomic re-subscription `StateDelta` moves `(w, u_old) → (w, u_new)` preserving Σ_w.

Total, deterministic, decidable. C6 reinterprets as versioned append-only monotone extension.

## 6. Final condition list (C1–C12)

- **C1 (Option + monotone).** `PositionState` accessor returns `Option<P>`; monotone carrier; `None` vs `Some(zero_P)` distinct.
- **C2 (handler-level conservation, per event class).** `Σ_w Δac(w,u) = 0` per class touching `ac`; `Σ_w Δw(u_MA) = 0` on mandate issuance/amendment; two-leg, K-leg, VM-settle, corporate actions each carry explicit proofs; vacuous on empty holder set.
- **C3 (atomic `StateDelta` across the 3 maps).** One transaction across `ProductTerms` / `UnitStatus` / `PositionState`; partial rejected.
- **C4 (capability-scoped reads).** Cross-(w, u_MA) overlay reads forbidden; strategy exports flow only through `UnitStatus`.
- **C5 (`UnitStatus` registration-totality).** Total on every registered `u`; product-declared defaults at registration.
- **C6 (`ProductTerms` versioned-append-only).** No in-place mutation; `NonEmptyList[TermsVersion]`.
- **C7 (`ProductTerms` registration-totality).** Total on every registered `u`; first write at registration.
- **C8 (amendment two-track by fungibility predicate).** Preserving → version append; Breaking → fresh `u` + `SupersededBy`. Predicate product-declared and total (§5).
- **C9 (vacuous-conservation discharge).** Handlers on zero-holder units discharge Σ_w Δ = 0 vacuously; explicit per-class obligation.
- **C10 (re-registration is a hard error).** Duplicate `u_id` rejected atomically; never silently tolerated.
- **C11 (per-field canonical handler).** Each `PositionState[w,u]` field (`entry_nav`, `hwm`, `first_touch`, `accrued_*`) tagged with the unique handler allowed to mutate it (R5_qis §3; R5_futures A3).
- **C12 (overlay-keyed, not flat).** All per-(w, mandate/strategy) economic state at `PositionState[w, u_MA]` / `PositionState[w, u_QIS]`. No flat W-scalars for economic state. W-sector collapse enforced by schema.

---

## Return summary

- **Final map count: 3** — `ProductTerms[u]`, `UnitStatus[u]`, `PositionState[w, u]`. `WalletState` collapses into `PositionState` via overlay-keying on `u_MA`.
- **Final conditions: C1–C12** as above.

— FORMALIS, R6, sealed.
