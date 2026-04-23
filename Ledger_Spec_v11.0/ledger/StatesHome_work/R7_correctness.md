# R7 — Correctness Architect: Pareto Evaluation of State-Home Alternatives

*Review scope: A (v10.3 current), B (3 maps + Option/Monotone + C1–C12 — SHIP CANDIDATE), C (Dirac σ/u_∅), D (Minsky 4-map), E (Grothendieck sheaf), F (Minimal 2-map).*
*Benchmark: 10 core invariants P1–P10 from ledger_v10.3.tex §11.*

---

## 1. Structural impact on P1–P10

| Inv. | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| P1 Conservation | check | **unreachable**¹ for `conserved=True` fields | check (but σ/u_∅ breaks Σ_w w(u_∅)=0) | check | check | check |
| P2 Atomicity | check (n maps) | check (3-way C3) | check (1 map) | check (4-way, widest TCB) | check (functorial limit) | check (2-way, narrowest) |
| P3 Referential integrity | check | **unreachable** via typed (w,u) key | check | check | check | check |
| P4 Log monotonicity | check | check | check | check | check | check |
| P5 Tx idempotency | check | **unreachable** per-(w,u) lattice (C1) | check | check (cross-space dedup) | check | check |
| P6 Lifecycle idempotency | check | **unreachable** per-(w,u) (C1) | check (scalar) | check (split keys) | check | check |
| P7 Virtual/real isolation | check | **unreachable** via C4 capability | check | check | check | check |
| P8 Snapshot consistency | check | check (monotone retain, C12/I12) | degraded (σ erases u-identity) | check | check | check |
| P9 Lifecycle purity | check | **unreachable** via C11 canonical writer + pure predicate | check | fragile (dual writers on HWM) | check | check |
| P10 Valid transitions | check | **unreachable** via UnitStatus total + C5 | check | check | check | check |

¹ "Unreachable" = structurally impossible to express a violation in the type system; writer discipline or key discipline forecloses the bug class before runtime.

B makes **7 of 10 invariants structurally unreachable**; no other candidate exceeds 3.

---

## 2. Axis scores (0–10)

| Candidate | Invariant coverage | Determinism | Type safety | Compositionality | Reconciliation | Total |
|---|---|---|---|---|---|---|
| A v10.3 current | 5 | 7 | 5 | 6 | 6 | 29 |
| **B 3-maps+C1–C12** | **9** | **9** | **9** | **9** | **9** | **45** |
| C Dirac σ/u_∅ | 4 | 8 | 3 | 5 | 4 | 24 |
| D Minsky 4-map | 7 | 7 | 6 | 5 | 6 | 31 |
| E Grothendieck sheaf | 8 | 8 | 8 | 4 | 7 | 35 |
| F Minimal 2-map | 6 | 9 | 5 | 8 | 7 | 35 |

**Pareto frontier: {B}.** B dominates A, C, D on every axis. B dominates E on compositionality (sheaf gluing forces non-local reasoning per event; B is per-(w,u) local — Adya 1999 G2 analysis). B dominates F on invariant coverage and type safety: F folds `ProductTerms` into `PositionState`, losing C6 append-only immutability and C10 re-registration rejection as structural guarantees (they regress to checkable-at-runtime).

---

## 3. Adversarial question: does `PositionState[w, u_MA]` confuse mandate with tradable position?

**No — provided C11 (canonical handler) and C4 (capability-scoped reads) hold.** The ProductTerms row `ProductTerms[u_MA]` carries a `ProductType = MANDATE` tag; the handler dispatcher routes by `product_terms(u).type`. Conservation Σ_w w(u_MA)=0 holds structurally (manager issues −1, client holds +1). A tradable equity `u_AAPL` and a mandate `u_MA` differ only by their `ProductType` tag; both live in the same map but dispatch to disjoint handler sets.

Residual risk: an event handler authored against `ProductType=EQUITY` accidentally accepting a `u_MA` row. **Mitigation (must ship):**

```python
@given(event=events(), u=unit_ids())
def test_handler_dispatch_exclusive(event, u):
    pt = product_terms(u)
    assert handler_for(event, pt).product_type == pt.type  # C11 strengthened
```

Plus a speculative property: "no handler ever reads a row of a `ProductType` it does not declare in its accepted-type set." Violations → structural handler-authoring bug, caught in CI.

The collapse is **safe**. It is **not** the Minsky denormalisation hazard; the hazard is instead parked in the handler-type-tag system, where it is cheaper to test (finite ProductType enum × finite handler set = closed coverage, per §11.4).

---

## 4. Gap search: does any of C/D/E/F close a B gap?

- **C (Dirac):** regresses P1 (σ loses conservation counterparty) and P8 (σ erases u-identity in snapshots). Closes nothing.
- **D (4-map separate WalletState):** offers nothing economic (R6_formalis §2 shows W-sector is empty). Widens TCB for C3. Introduces cross-space idempotency obligation for HWM ratchets — **regresses P5/P6**.
- **E (sheaf):** rigorous but demands gluing checks per event — compositionality drops from per-(w,u) local to global coherence. Operational cost without a correctness gain B lacks. Closes nothing B does not.
- **F (2-map):** simpler C3 (2-way commit). Loses C6 (ProductTerms immutability no longer structural — amendments can silently mutate terms via position-row writes). **Regresses P9 purity** because the fungibility predicate must now live on a mutable row. Net loss.

**No candidate closes a gap in B.**

---

## 5. Correctness property B provides that none of C/D/E/F provide

**Unified per-(w,u) idempotency lattice** (C1 `None ≤ Some(zero_P) ≤ Some(v)`) **combined with** atomic 3-way C3 **combined with** product-declared fungibility predicate (C8) **combined with** canonical-writer discipline (C11). The conjunction makes P5, P6, P9, P10 simultaneously structurally unreachable in a way that:
- C cannot (no PositionState → idempotency keyspace is global, not per-(w,u))
- D cannot (dual keyspace for HWM breaks uniform lattice)
- E cannot (sheaf sections must reconcile — not a fixed-point on a single lattice)
- F cannot (2-map fuses ProductTerms writes into PositionState → C6/C8 purity lost)

This is the load-bearing correctness property of B.

---

## 6. Verdict

**B is Pareto-optimal on correctness. Convergence confirmed.**

Blockers before merge (none are alternative-driven; all internal to B):

1. Ship C11 as a type-level handler/product-type predicate, not a runtime tag check. Property test `test_handler_dispatch_exclusive` above.
2. Generator for `ProductType × EventIntentEnum` covering the closed cross-product (§11.4 — coverage-as-checklist).
3. Shrinker on `PositionState[(w, u)]` rows paired with the generator (Claessen-Hughes; MacIver/Hypothesis).
4. Differential test: for every fungibility-preserving amendment, cashflow stream on every holder is ε-invariant; else `pred` must have returned `False` (Goodhart trap on a lax predicate).
5. Metamorphic property on mandate issuance: `Σ_w w(u_MA) = 0` pre and post every amendment (R6_formalis §3).

No alternative dominates B. Ship.

— Correctness Architect, sealed.
