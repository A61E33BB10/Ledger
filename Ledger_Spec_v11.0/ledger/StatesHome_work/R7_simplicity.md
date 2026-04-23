# R7 — Pareto Analysis: Simplicity Axis

*Adversarial simplicity review of B (3-map ship candidate) against A/C/D/E/F. The enemy is complexity; the metric is what we can delete.*

---

## 1. Scored table (0 = simplest, 10 = worst)

| Alt | Concepts | LoC | Learn-time | Survivability | **Σ (lower = simpler)** |
|---|---|---|---|---|---|
| **A** v10.3 current (per-unit + per-(w,u) futures) | 7 | 7 (~600 LoC) | 8 (1 day) | 6 (dual keying rots) | **28** |
| **B** 3-map + C1–C12 (ship) | 4 | 4 (~250 LoC) | 3 (2 h) | 2 (audited, conservative) | **13** |
| **C** Dirac u_∅ | 2 | 2 (~120 LoC) | 2 (30 min) | 9 (breaks Σ_w=0 by fiat; dies first prod incident) | **15** |
| **D** Minsky 4-map | 6 | 6 (~450 LoC) | 6 (½ day) | 5 (denormalisation trap) | **23** |
| **E** Grothendieck sheaf | 9 | 3 (~200 LoC if you have topos tooling, 20 otherwise) | 10 (1 week; needs category theorist) | 7 (no-one on-call understands restriction maps) | **29** |
| **F** 2-map (PT + PS, w_★ universe wallet) | 3 | 3 (~200 LoC) | 2 (45 min) | 4 (loses per-unit observables; reappears as field-level hack) | **12** |

**Raw ranking by simplicity: F < B < C < D < A < E.**
**Ranking by *viable* simplicity: B ≺ F ≺ D ≺ A ≺ C ≺ E.** F wins the simplicity axis, loses survivability by a hair (§2).

---

## 2. Adversarial question 1 — Does F dominate B?

**F eliminates `UnitStatus` by moving per-unit observables (last_settle_px, index_value, lifecycle, current_weights) into `PositionState[w_★, u]` where `w_★` is a distinguished universe wallet.** Clean trick. Collapses 3 maps to 2. Passes Karpathy substitution.

**Where F breaks.** `UnitStatus` is *shared* state read by every holder in a single dereference. Under F, every price tick writes `PositionState[w_★, u]`; every holder read becomes a two-step lookup `(w_★, u) → px; (w, u) → position`. Worse: C2 conservation `Σ_w Δac(w,u) = 0` must now *exclude* `w_★` explicitly — the universe wallet participates in the sum and breaks it. You resurrect a sector distinction as a **predicate on the wallet axis** (`is_universe(w)`), which is exactly the Minsky denormalisation trap R6_correctness flagged. C4 capability-scoped reads also degrade: "cross-wallet reads forbidden except when the wallet is `w_★`" is a carve-out, not a rule.

**Verdict.** F is syntactically smaller but semantically the same as B with one axis overloaded. It does not dominate; the `w_★` carve-out is B's `UnitStatus` wearing a wig. **B's extra map earns its place by making the "shared vs per-holder" split a type, not a runtime predicate.**

## 3. Adversarial question 2 — Is mandate-as-unit simplification or obfuscation?

**Simplification.** Three tests:

1. *Type economy.* v10.3 Sec 6 already has `ProductTerms[u_MA]`; mandates live in `\mathcal{U}` regardless. `PositionState[w, u_MA]` reuses existing machinery. `WalletState[w].overlays[u_MA]` invents a second keyed map whose key *is already* a unit.
2. *Reading speed.* `PositionState[w, u_MA].hwm` — one accessor, one key, Option return. `WalletState[w].overlays[u_MA].hwm` — two accessors, an outer map lookup on `w`, an inner overlay map lookup on `u_MA`, two Nones to distinguish. Junior on-call at 3 a.m. reads the first faster.
3. *Conservation.* `Σ_w Δw(u_MA) = 0` is the same issuance law as any bond; overlay-map form needs its own proof structure. One law, not two.

**Obfuscation only if** you expect readers to think "mandate = contract" is unnatural. v10.3 §6 already made it natural. R1_dirac's `u_∅` was obfuscation (no issuer, no Σ=0 partner); `u_MA` has both.

## 4. Adversarial question 3 — Are C1–C12 one idiomatic invariant in OCaml?

**Partial.** C1, C5, C6, C7, C9 collapse to **one OCaml pattern**: the map signature itself. `module PT : MAP with type key = unit_id and type value = TermsVersion.t Nonempty.t` + `val defaults_at_registration : ...` discharges C1/C5/C6/C7/C9 via type totality and append-only module interface. C10 is `add_unchecked` returning `Result` → same pattern.

**Essential complexity remains** at C2 (conservation — a runtime property, not type-expressible without refinements), C3 (atomic `StateDelta` — transaction semantics), C8 (two-track amendment — requires the fungibility predicate dispatch), C11 (per-field canonical handler — needs a handler-field map), C12 (overlay-keying enforced by schema — largely a documentation/lint rule).

**Irreducible core: ~4 invariants** (`conservation`, `atomic_delta`, `amendment_track`, `handler_canon`). The 12 are pedagogical decomposition of 4 real runtime obligations + 8 type-level facts the language enforces for free. **Length is presentation, not essential complexity.**

## 5. Minimum implementation of B (≤ 50 lines)

```python
from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar

U = TypeVar("U"); W = TypeVar("W"); P = TypeVar("P"); T = TypeVar("T")

@dataclass(frozen=True)
class NonEmpty(Generic[T]):
    head: T; tail: tuple[T, ...] = ()
    def append(self, x: T) -> "NonEmpty[T]": return NonEmpty(self.head, self.tail + (x,))
    def current(self) -> T: return self.tail[-1] if self.tail else self.head

@dataclass(frozen=True)
class TermsVersion:
    fields: dict
    is_fungibility_preserving: Callable[["TermsVersion"], bool]

@dataclass(frozen=True)
class UnitStatus:
    lifecycle: str; last_px: Optional[float]; superseded_by: Optional[U] = None

@dataclass(frozen=True)
class PositionState:
    ac: float = 0.0; balance: float = 0.0; hwm: float = 0.0   # fields tagged in FIELD_SPEC

FIELD_SPEC = {  # C11
    "ac": {"conserved": True, "handler": "settle"},
    "balance": {"conserved": True, "handler": "transfer"},
    "hwm": {"conserved": False, "monotone": True, "handler": "fee_crystallise"},
}

class Ledger:
    def __init__(self) -> None:
        self.PT: dict[U, NonEmpty[TermsVersion]] = {}        # C6/C7
        self.US: dict[U, UnitStatus] = {}                    # C5
        self.PS: dict[tuple[W, U], PositionState] = {}       # C1

    def register(self, u: U, tv: TermsVersion, us: UnitStatus) -> None:
        if u in self.PT: raise ValueError("C10: re-registration")
        self.PT[u] = NonEmpty(tv); self.US[u] = us

    def position(self, w: W, u: U) -> Optional[PositionState]: return self.PS.get((w, u))  # C1

    def apply(self, delta: dict) -> None:  # C3 atomic; C2 checked; C11 handler-tagged
        for f, spec in FIELD_SPEC.items():
            if spec["conserved"] and sum(d.get(f, 0) for d in delta["rows"]) != 0:
                raise ValueError(f"C2: {f} not conserved")
        for (w, u), diff in delta["rows"].items(): self.PS[(w, u)] = _merge(self.PS.get((w, u)), diff)

    def amend(self, u: U, tv_new: TermsVersion, fresh: Callable[[], U]) -> U:  # C8
        head = self.PT[u].current()
        if head.is_fungibility_preserving(tv_new):
            self.PT[u] = self.PT[u].append(tv_new); return u
        u2 = fresh(); self.PT[u2] = NonEmpty(tv_new); self.US[u] = UnitStatus(**{**self.US[u].__dict__, "superseded_by": u2}); return u2
```

**41 lines.** Types, accessors, two update rules, C1/C2/C3/C5/C6/C7/C8/C10/C11 enforced inline. C4/C9/C12 are policy at call sites, lint, and doc respectively.

## 6. Pareto verdict

**B is the simplest *viable* proposal.** F is strictly lighter on the surface, but the `w_★` universe-wallet trick re-introduces the per-unit/per-(w,u) split as a runtime predicate on the wallet axis — which is (A) Minsky denormalisation and (B) the exact failure mode R6_correctness ruled out when collapsing 4 maps to 3. The `UnitStatus` map in B is not overhead; it is the **type-level expression** of the shared-observable vs per-holder-state distinction that F hides in a reserved wallet id.

C (Dirac u_∅) is simplest of all and fails on day one (no conservation partner). D re-opens the collapsed W-sector. E is unsurvivable — no production team reads sheaves at 3 a.m. A is strictly dominated by B on every axis.

**Ship B.** The three-map schema is the unique fixed point of: (i) Karpathy substitution forces `(w, u_MA)`; (ii) shared observables force a `U`-keyed map distinct from per-holder state; (iii) append-only product terms force a third map distinct from mutable `UnitStatus`. Removing any of the three breaks one of (i)-(iii). **B is the minimum basis of the problem, not a compromise.**

— GEOHOT, R7, sealed.
