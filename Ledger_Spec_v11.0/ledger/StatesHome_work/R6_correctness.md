# R6 — Correctness Architect: Adversarial Reconciliation (HWM placement, map count, C8)

*Target: reconcile R5_managed_account (HWM at `WalletState[w].overlays[u_MA]`) vs R5_qis (HWM at `PositionState[w, u_QIS]`). Decide the map count. Confirm C8 two-track amendment rule.*

---

## 1. Collapse or keep? — **COLLAPSE. Ship 3 maps.**

**The structural argument is decisive.** Every field R5_managed_account places on `WalletState[w_C]` is, on careful reading, already `(w, u_mandate)`-keyed:

| Alleged wallet-only field | True key | Evidence |
|---|---|---|
| `HWM`, `hwm_date` | `(w_C, u_MA)` | R5_qis Q4: Karpathy substitution — if `w_C` holds `u_QIS1` and `u_QIS2`, one scalar collapses two distinct marks. Same argument for `u_MA1` + `u_MA2` overlay on §6 of R5_managed_account. |
| `accrued_mgmt_fee`, `accrued_perf_fee` | `(w_C, u_MA)` | R5_managed_account §6 itself concedes: multi-mandate forces `overlays : Map[u_MA_id → OverlayState]`. That map *is* `PositionState[w, u_MA]`. |
| `benchmark_nav_at_inception` | `(w_C, u_MA)` | Baseline is relative to *this* mandate's benchmark pointer; swap mandates → different baseline. |
| `subscription_cursor`, `redemption_cursor` | `(w_C, u_MA)` | S/R events are *for this mandate*. Two mandates on one wallet have two S/R streams. |
| `mandate_breach_flags` | `(w_C, u_MA)` | Constraints are declared in `ProductTerms[u_MA]`; breach state is per-mandate-instance. |

R5_managed_account §6 already ruled that multi-mandate requires overlay-keyed `WalletState`. An overlay map keyed by `u_MA_id` on a wallet is structurally `PositionState[w, u_MA]` — a sparse, `Option`-returning, monotone-carrier map over `(w, u)`. Two names for the same object is a Minsky denormalisation trap waiting to happen.

**Remaining "wallet-only" state (ownership, KYC, capability, `manager_reference` tag) is metadata, not economic state.** It does not participate in conservation laws, is not mutated by event handlers, and does not need atomic multi-map `StateDelta` discipline (C3). Put it in a registry (`WalletRegistry[w]`) outside the state algebra — same tier as `ProductTerms`'s "immutable registration" — not a state sector.

**Ruling:** ship **three state maps** — `ProductTerms[u]`, `UnitStatus[u]`, `PositionState[w, u]` — plus a non-state `WalletRegistry[w]` for metadata. R5_managed_account's "overlay-keyed WalletState" and `PositionState[w, u_MA]` are the same map.

## 2. Idempotency — **3-map wins cleanly.**

Under 3 maps every lifecycle event is `(w, u)`-keyed, so idempotency is **uniformly** per-`(w, u)` on the three-point lattice `None ≤ Some(zero_P) ≤ Some(v)` (R4 C1). Re-applying a fee-crystallisation event on `(w_C, u_MA)` is a lattice fixed-point; the handler compares delta-witness to current row state.

Under 4 maps, wallet-level events are `(w)`-keyed but emit deltas into `(w, u)` PositionState — two different idempotency key spaces composed at handler level, with cross-space deduplication obligations. Every HWM ratchet event needs *both* a `WalletState[w_C]` idempotency witness *and* a `PositionState[w_C, u_MA]` witness. Extra proof burden, no benefit.

**Hypothesis property (3-map):**
```python
@given(event=events(), state=states())
def test_handler_idempotent(event, state):
    once = apply(state, event)
    twice = apply(once, event)
    assert twice == once  # per-(w,u) lattice fixed-point
```

## 3. Conservation laws — **distinction does NOT justify a separate sector.**

R5_qis correctly observes that **only `(w, u)`-fields conserve across wallets**: `Σ_w Δ ac(w, u) = 0`, `Σ_w Δ balance(w, u) = 0` (R4 C2). HWM, fee accruals, breach flags are single-wallet invariants; they do not participate in cross-wallet sums.

But **non-conserved fields can still live in `PositionState`**. Conservation is a per-field predicate declared on the field, not a map-level invariant. R4 C2 says "every conserved field satisfies `Σ_w Δ = 0` per event class" — fields without the `conserved` marker discharge vacuously. HWM is a `PositionState[w, u_MA]` field with `conserved = False`. No sector split required.

**Declaration discipline (proposed):**
```python
@dataclass(frozen=True)
class FieldSpec:
    name: str
    conserved: bool          # participates in Σ_w Δ = 0
    monotone: bool           # e.g. HWM ratchets up only
    handler: HandlerId       # canonical writer (R5_qis §3 recommendation)
```

## 4. C8 amendment two-track — **confirmed, implementable, testable.**

The fungibility-predicate rule is well-posed:

```python
def amend(u: UnitId, amendment: Amendment) -> UnitId:
    pt = product_terms[u]
    if pt.fungibility_predicate(amendment):
        # append to NonEmptyList[TermsVersion] on same u
        product_terms[u] = pt.append_version(amendment)
        return u
    else:
        # allocate fresh u; emit SupersededBy edge
        u_new = fresh_unit_id()
        product_terms[u_new] = pt.with_amendment(amendment)
        unit_status[u].supersededby = u_new
        return u_new
```

**Testable as:**
- *Property P1 (fungibility preservation):* for every amendment `a` with `pred(a) = True`, existing `PositionState[w, u]` rows remain valid post-amendment (no key rewrites).
- *Property P2 (fungibility break):* for every amendment `a` with `pred(a) = False`, `u_new ≠ u_old`, and `SupersededBy(u_old → u_new)` edge exists.
- *Property P3 (determinism):* `pred` is pure and product-declared; identical inputs yield identical track.
- *Property P4 (no silent fungibility):* amendments with `pred = False` never write to `ProductTerms[u_old].versions`.

The predicate itself is where Goodhart can strike — a lax `pred` that returns `True` too often preserves `u_id` at the cost of real fungibility. Pair with a differential test against regulatory rules (ISDA CDM novation tests) and a speculative property: *if post-amendment cashflows differ by more than `ε` on any holder, `pred` should have returned `False`.*

## 5. Final ruling

| Decision | Ruling | One-sentence justification |
|---|---|---|
| (i) Number of maps | **3** — `ProductTerms[u]`, `UnitStatus[u]`, `PositionState[w, u]` + non-state `WalletRegistry[w]` | Every field on `WalletState` is already `(w, u_mandate)`-keyed once multi-mandate composition is admitted (R5_managed_account §6); retaining a separate `WalletState` duplicates the same keyspace under two names. |
| (ii) HWM placement | **`PositionState[w_C, u_MA]`** (R5_qis wins) | HWM varies with the mandate/strategy identity; Karpathy substitution forces the `(w, u)` key; R5_managed_account's "overlay-keyed WalletState" is structurally identical. |
| (iii) Amendment rule | **C8 two-track by fungibility predicate** | Fungibility-preserving → append to `ProductTerms[u].versions`; fungibility-breaking → fresh `u` with `SupersededBy` edge; predicate product-declared, pure, testable. |

## 6. Invariants (final list, post-R5)

- **I1 (PositionState totality):** accessor returns `Option<P>`; carrier monotone; `None ≤ Some(zero) ≤ Some(v)` lattice. (R4 C1.)
- **I2 (conservation, per-field per-event):** `Σ_w Δ f(w, u) = 0` for every field `f` with `f.conserved = True` under every event class touching `f`; vacuous otherwise. (R4 C2 generalised.)
- **I3 (atomic StateDelta):** every event applies as a single transaction across `ProductTerms`/`UnitStatus`/`PositionState`; partial application rejected. (R4 C3.)
- **I4 (capability-scoped reads):** cross-wallet `PositionState` reads forbidden; strategy-level exports flow through `UnitStatus[u]` only. (R4 C4.)
- **I5 (UnitStatus totality):** `UnitStatus[u]` total on registered `u`; product-declared defaults at registration. (R4 C5, R5_untraded C7.)
- **I6 (ProductTerms immutability):** no writer on `ProductTerms` except append-to-versions on fungibility-preserving amendment. (R4 C6.)
- **I7 (amendment two-track):** C8 fungibility predicate determines track; fungibility-breaking → fresh `u` + `SupersededBy`. (R5_untraded C8.)
- **I8 (vacuous conservation):** handlers on zero-holder units discharge `Σ_w Δ = 0` vacuously; totality on `holders_of(u) = ∅`. (R5_untraded C9.)
- **I9 (re-registration is error):** duplicate `u_id` at registration rejected. (R5_untraded C10.)
- **I10 (per-field handler canonicalisation):** every `PositionState` field declares its canonical writer handler; foreign-handler writes rejected. (R5_qis §3.)
- **I11 (first_touch immutability or derivation):** `first_touch_date` either set-once-never-updated with correction via `FirstTouchRevisionEvent`, or derived from event log; never silently overwritten. (R5_futures A3.)
- **I12 (monotone retention on CLOSED):** CLOSED/EXPIRED/SETTLED units retain `PositionState` rows with balance-projection 0; required for time-travel and tax lookback. (R5_qis Q6, R5_futures A4.)

**Final:** 3 maps; HWM at `PositionState[w, u_MA]`; C8 two-track by fungibility predicate.

— Correctness Architect, sealed.
