# R7 — Pareto Analysis: Testability Axis

*Committee: Beck, Hughes, Fowler, Feathers, Lamport. Scope: evaluate R6 ship-candidate against five alternatives on TESTABILITY, CORRECTNESS, SIMPLICITY. Score 0–10.*

---

## 1. Scored table

| Alt | Shape | TEST | CORR | SIMP |
|---|---|---:|---:|---:|
| **A** | v10.3 per-unit dict + per-(w,u) futures | 4 | 5 | 4 |
| **B** | 3 maps, Option+Monotone, C1–C12 | **9** | **9** | **8** |
| **C** | Dirac σ: W×U ⇀ S_u, `u_∅` sentinel | 7 | 3 | 7 |
| **D** | Minsky 4-map (pre-R6) | 7 | 7 | 5 |
| **E** | Grothendieck sheaf on H_t ⊆ W×U | 8 | 9 | 2 |
| **F** | 2 maps (PT + PS), UnitStatus folded via `w_star` | 5 | 6 | 6 |

Rubric. TEST = enumerable generators + local invariants + shrinkability + replay determinism. CORR = illegal states unrepresentable + atomic commit tractable. SIMP = primitive concepts + 30-min learnability + LOC.

---

## 2. Pareto frontier

`x` is on the frontier iff no `y` weakly dominates with one strict.

| Alt | Vector | Dominated by? | Frontier |
|---|---|---|---|
| A | (4, 5, 4) | B strict on all | no |
| B | (9, 9, 8) | — | **yes** |
| C | (7, 3, 7) | — (alone at CORR=3) | yes (weak) |
| D | (7, 7, 5) | B strict on all | no |
| E | (8, 9, 2) | B (9>8, 9=9, 8>>2) | no |
| F | (5, 6, 6) | B strict on all | no |

**Frontier = {B, C}.** C survives only because its catastrophic CORR=3 makes it incomparable on that axis. Under ship gate `CORR >= 7`, **B is the unique Pareto-optimum.**

### ASCII projection (TEST vs SIMP; parenthesis = CORR)

```
SIMP
 10 |
  8 |                               B(9)   <- ship
  7 |              C(3)
  6 |                      F(6)
  5 |                    D(7)
  4 |        A(5)
  2 |                                        E(9)
  0 +------------------------------------------
    0   1   2   3   4   5   6   7   8   9  10
                         TEST
```

---

## 3. Does B dominate A? Yes, strictly.

- TEST: B has uniform `(w,u)` generator (Hughes); A branches per-unit-class, futures a special case.
- CORR: B's C3 is atomic across 3 maps; A fragments with per-(w,u) futures carve-out.
- SIMP: B has 3 uniform maps; A has "dict + futures exception".

B strictly dominates A on all three axes.

## 4. Does B dominate D? Yes, strictly.

- TEST: D has two idempotency key spaces (`w`-keyed wallet events emitting into `(w,u)` PositionState); every HWM ratchet needs two witnesses. B collapses to one `(w,u)` lattice — one-line fixed-point property.
- CORR: D admits Karpathy denormalisation (R6_correctness §1): two `u_QIS` overlays on one `w_C` collapse into one wallet-scalar HWM. B forbids by type.
- SIMP: D has 4 maps + cross-map dedup obligation.

B strictly dominates D.

## 5. Is F a Pareto improvement over B? No — F is strictly dominated.

F folds `UnitStatus` into `PositionState` keyed on sentinel `w_star`.

- TEST: sentinel `w_star` leaks into every generator. `st.tuples(wallets(), units())` must either exclude it (breaks shrinking) or admit it (illegal rows representable). Beck: direct violation of "illegal states unrepresentable". TEST=5.
- CORR: untraded-unit totality (R5_untraded C7) becomes a convention ("exists a `w_star` row") not a type invariant. I8 (vacuous conservation) becomes untestable as a pure property. `Σ_w Δw(u)=0` either excludes `w_star` (special case) or breaks. CORR=6.
- SIMP: saves one map (3→2) but adds sentinel + domain-exclusion in every conservation proof. SIMP=6 < B's 8.

**F is strictly dominated by B on all three axes.** The "clean untraded-unit story" argument is decisive: Feathers' characterization tests for dormant units want `UnitStatus[u]` as a free total surface, which F destroys.

## 6. Why E is dominated by B

E's restriction maps make local→global automatic; gluing gives conservation for free. But SIMP=2 is brutal — no on-call engineer reasons about presheaves on a site at 3am. B achieves the same local→global reduction (per-`(w,u)` lattice is a coarse sheaf) with 3 primitive concepts. B dominates E: 9≥8, 9=9, 8≫2. E's elegance is unrealisable without nonexistent libraries.

## 7. Why C is frontier-but-unshippable

C has SIMP=7 (single map) but fails CORR catastrophically: `u_∅` has no issuer, breaking `Σ_w w(u_∅)=0` by fiat (FORMALIS R6 §3). A sentinel with no conservation partner is a counterexample Hughes' shrinker eats immediately. On the frontier by weakness (no alt matches SIMP=7 at CORR<4), off the ship-table by CORR gate.

---

## 8. Verdict

**B is Pareto-optimal under ship constraint `CORR >= 7`.**

- B strictly dominates A, D, F on all three axes.
- B dominates E (trades 0 TEST for +6 SIMP, CORR equal).
- C is frontier-adjacent but fails the CORR ship gate.

**Iteration has converged.** No alternative in `{A, C, D, E, F}` Pareto-dominates B on the testability axis. Ship B: 3 maps (`ProductTerms[u]`, `UnitStatus[u]`, `PositionState[w,u]`), Option+Monotone accessor, C1–C12.

— TESTCOMMITTEE (Beck, Hughes, Fowler, Feathers, Lamport), R7, sealed.
