# R3 — FEYNMAN: Verify by Sum Over Representations

*"If there's only one way to understand something, you don't really understand it."*

I compute the Sec 7.4 futures scenario three times. If the answer depends on the representation, the proposal is not verified. If it doesn't, the distinction is in which *illegal* states are representable.

Unit `u=ES` (mult 50). Wallets `ALPHA`, `CH`. Events: three trades + MTM@4530; plus close-out $E_5$ (hypothetical sell 7 @ 4530 flattening ALPHA).

- **A** — three typed maps `UnitState[u]`, `WalletState[w]`, `PositionState[w,u]`.
- **B** — Dirac collapse: all in `PositionState[w,u]`; per-unit at reserved `w_*`; per-wallet at reserved `u_self`.
- **C** — unit-centric: `UnitState[u]` with nested `holders : w -> {net_qty, ac}`; `WalletState` separate.

## State after each event

| After | A | B | C | =? |
|---|---|---|---|---|
| $E_0$ init | `PS[*,u]=⊥`; `US[u].ls=LISTED` | `PS[w_*,u].ls=LISTED` | `US[u].holders={}` | y |
| $E_1$ buy 10@4500 | `PS[ALPHA]=(+10,-2.25M)`, `PS[CH]=(-10,+2.25M)` | same keys | nested in `US[u].holders` | y |
| $E_2$ buy 5@4510 | $(+15,-3.3775M)/(-15,+3.3775M)$ | same | same | y |
| $E_3$ sell 8@4520 | $(+7,-1.5695M)/(-7,+1.5695M)$ | same | same | y |
| $E_4$ MTM@4530 | `ALPHA.ac=-1.5855M`; `US.last_settle=4530` | `PS[w_*].last_settle=4530` | `US.last_settle=4530` | y |

Observables agree exactly — null result. Conservation $\sum_w \text{ac}=0$ holds in all three. The choice is not about correctness on a known scenario; it is about footprint, invariant scans, and which mutations the compiler rejects.

### Footprint, invariants, close-out

| Axis | A | B | C |
|---|---|---|---|
| Bytes at 1M holders | `US:1 + PS:1M`, independently shardable | `PS: 1M+1` (extra hot `w_*` row) | mega-row `US[u]` with 1M-dict — serialises all holder writes |
| $\sum_w \text{ac}=0$ scan | filter `PS` on second key | filter **and** exclude `w_*`, `u_self` sentinels | local sum over dict |
| Rejects "two holders, different `last_settle`" | **yes** — field absent from `PS` type | **no** — every field is `Option` | **no** — `holders[w]` is a god-dict |
| CCP SPAN reconciliation (key `(client, contract)`) | direct | direct after sentinel filter | per-call projection |

**Close-out $E_5$ (ALPHA flat).** Keep or GC the `(0,0)` row? If GC on zero, **replay is non-deterministic under partial replay** — `E_1..E_4` holds the row, `E_1..E_5` doesn't. Rule for all three: **never GC, monotone carrier.** A applies this to one map. B must apply it *and* keep sentinel rows alive (extra rule). C applies it inside a nested dict under write contention. Cleanest: A.

## Untraded listed unit (0 holders)

| Slot | A | B | C |
|---|---|---|---|
| `UnitState[u]` | `{static, ls=LISTED}` | — | `{static, ls, holders={}}` |
| `PositionState` | no rows; accessor returns typed zero-default | requires `PS[w_*,u]` at registration, else no home for `last_settle` | no rows; `holders={}` |
| Ill-typed? | No; three total accessors | Yes in practice — every field must be `Option<T>` to let `w_*` row carry unit-only fields with no position (the illegal-state admission A eliminates) | No, but zero-default lives inside an empty-dict sentinel |

A carries state on the map whose key space naturally has an entry. B needs a sentinel wallet. C keeps a lockable row per unit regardless of trading.

## Physical argument (gauge / projection)

Let $G = \text{Sym}(\mathcal{W}) \times \text{Sym}(\mathcal{U})$ act by relabelling. Every state field is a tensor transforming under exactly one subrepresentation:

- $\mathbf{U}$ sector (invariant under $\text{Sym}\mathcal{W}$): `static`, `lifecycle_stage`, `last_settle`, `paid_coupons`.
- $\mathbf{W}$ sector (invariant under $\text{Sym}\mathcal{U}$): `mandate`, `HWM`, `drawdown`.
- $\mathbf{W\otimes U}$ sector: `net_qty`, `accumulated_cost`.

There is no fourth sector. **A stores each sector on its natural carrier — the irreducible decomposition.** $F_B:\text{A}\to\text{B}$ collapses $\mathbf{U}$ onto `PS[w_*,u]` and $\mathbf{W}$ onto `PS[w,u_\text{self}]` — a projection onto one carrier with reserved basis vectors. $F_C$ embeds $\mathbf{W\otimes U}$ inside $\mathbf{U}$ via a nested map. Both preserve scalar observables — **A, B, C are equivalent up to a projection at the value level**. They differ only in which fields are type-distinguishable.

$\sum_w \text{ac}(w,u)=0$ is the **Noether current of $\text{Sym}\mathcal{W}$ acting on the $\mathbf{W\otimes U}$ sector**; in A it lives inside one map. B requires subtracting an ill-defined `w_*` contribution; C is local but on a write-serialised row. **A decouples sectors that the symmetry already decouples; B and C re-couple them.** That coupling is information not in the physics — sentinel rows, `Option<T>` everywhere, god-dicts — and it is where bugs live.

## Verdict

**Ship A**, with two corrections:

1. **Monotone `PositionState` carrier.** Create on first touch, never GC. Close-out leaves `(0,0)`. Replay-deterministic.
2. **Conservation discharged at the event handler.** `Trade` emits `(buyer_delta, seller_delta)` with structural zero-sum; induction gives $\sum_w \text{ac}(w,u)=0$. No type system enforces an existentially-quantified decimal sum — no layout can. Proof obligation belongs on the handler.

A, B, C agree on the Sec 7.4 numbers — a null test A passes. A wins on the only axis representations legitimately differ: **the space of representable illegal states**. B and C reintroduce sentinel debt (`w_*`, `u_self`, `Option<T>`, god-rows) that A eliminates by separating sectors the symmetry group already separates.

*The answer did not change across representations. What changed was the size of the space of bugs.*
