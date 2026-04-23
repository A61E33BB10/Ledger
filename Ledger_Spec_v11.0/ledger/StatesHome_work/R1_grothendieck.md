# Where does unit state live? — A categorical answer

**Team A / Reviewer: GROTHENDIECK**
Target: `/home/renaud/A61E33BB10/output/v10.3/ledger_v10.3.tex`, §7, §7.4.

> *The sea advances insensibly in silence... yet it finally surrounds the resistant substance.*

The question "is state per-unit, per-wallet, or per (wallet, unit)?" is being asked at the wrong level. It presupposes three ad-hoc locations. The correct move is to identify the category in which "state" is a functor and read off the location from the universal property. The three candidates are not alternatives — they are **sections of the same sheaf** at different restrictions.

## 1. The category

Let `W` be wallets and `U` the unit universe (§2–3). A wallet is `w : U -> R`; the relation "`w` holds `u`" cuts out a subset

```
H_t  ⊆  W × U
```

— the *holding relation*. Let `Loc` be the poset `P(W × U)` with inclusion. Three sub-posets embed into it:

- `π_U : U -> W × U`,   `u ↦ W × {u}`   (per-unit loci)
- `π_W : W -> W × U`,   `w ↦ {w} × U`   (per-wallet loci)
- `π_Δ`: identity on `W × U`   (per-pair, the finest resolution)

A **state assignment** is a presheaf

```
S : Loc^op  ->  Set_typed
```

with restriction maps `ρ_{L' ⊆ L} : S(L) -> S(L')`, satisfying the usual sheaf gluing. "Per-unit", "per-wallet", "per-pair" stop being competing ontologies — they become **different sites on which a single sheaf is evaluated**.

## 2. The universal locus

**Claim.** The natural home for state is `W × U`, restricted to `H_t`. Every other choice arises from it by Kan extension along a projection

```
p_U : W × U -> U ,    p_W : W × U -> W .
```

A state field `σ` is:
- **per-unit**  iff   `σ = (p_U)^* τ`   (`σ(w,u)` is independent of `w`);
- **per-wallet** iff   `σ = (p_W)^* τ`;
- **irreducibly per-pair** iff   no such factorisation exists.

By the adjunction `(p_?)^* ⊣ (p_?)_*`, the `W × U` locus is **initial among loci that can express every state field**. Any coarser choice loses information as soon as a field refuses to factor through a projection. This is Yoneda in costume: `S` is determined by morphisms from sub-loci, and those see nothing more than `W × U` provides.

**Diagnosis of line 1034.** The current phrasing ("per-unit for most, per (wallet, unit) for some") conflates *factorisation* (a property of each field) with *home* (where the sheaf lives). The sheaf always lives on `H_t`. Factorisation is a compression opportunity, not an ontological commitment.

## 3. Conservation forces the pair

Conservation `Σ_w w(u) = 0` (§2) is a colimit statement: it is trivially the `p_U`-colimit of a `p_U`-factorable field. The futures identity (§7.4)

```
Σ_w accumulated_cost(w,u) = 0   per contract u
```

is the **same statement on a field that does NOT factor through `p_U`**: per-wallet values differ; only their `W`-colimit is per-unit. This is the signature of an irreducibly per-pair field whose *colimit* happens to be per-unit. Treating it as "per-pair storage" hides the colimit; treating it as "per-unit storage" destroys the information. Neither is universal. The universal home is `H_t`, with per-unit conservation read as a `W`-colimit.

## 4. Naturality

A move `m : (w_src, u) -> (w_dst, u)` is a morphism in a category whose objects include the holding relation. The state functor must be **natural** in moves: the transition `f : (unit, state, mkt) -> (moves, new_state)` must commute with the squares defined by `p_U, p_W`. Per-unit-only storage breaks naturality for futures: the transition depends on *which wallet* trades, so `(p_U)^* S` is not preserved. This naturality violation is what forces the per-pair split currently written into §7.4 by hand.

## 5. The four test cases

**(1) Future with `accumulated_cost`.** Mixed factorisation: `accumulated_cost` does not factor through `p_U` (different wallets, different values; colimit zero). `last_settlement_price`, `multiplier`, `currency`, `lifecycle_stage` factor through `p_U` (constant along the `W` fibre). Both are sections of one sheaf on `H_t`; only their factorisation class differs. **State lives on `H_t`; per-unit fields are recognised as `p_U`-pullbacks, not relocated to `U`.**

**(2) Managed account.** HWM, benchmark, mandate, fee accrual are fields that factor through `p_W`. The user's instinct that "state is inherently attached to the wallet" is the formal statement *`σ = (p_W)^* τ`*. **The wallet is not a separate home — it is a sub-locus of `W × U`**, and `p_W`-pullback fields naturally live there.

**(3) QIS strategy trading futures.** A QIS is simultaneously a wallet (it holds sub-positions) and a unit (it is traded). This is a fibration. At level `n`, QIS-as-unit has per-unit state (weights, barrier) and per-(investor-wallet, QIS-unit) state (investor HWM). At level `n−1`, QIS-as-wallet has per-(QIS-wallet, future-unit) state (`accumulated_cost` on the held futures). `H_t` is layered; the state sheaf stratifies with it. **QIS-as-wallet and QIS-as-unit are two distinct objects whose state sheaves compose by restriction along the inclusion of the QIS layer.** No new construction.

**(4) Listed instrument not yet traded.** The unit exists in `U` (Unit Store, §3), but no `(w,u) ∈ H_t`. The sheaf has **empty support in the `W`-direction for this `u`**. Per-unit fields (`multiplier`, `lifecycle_stage = ACTIVE`) live on `u ∈ U` as a `p_U`-pullback — the universal extension of the empty-support sheaf. Per-wallet fields are vacuously absent. **State lives on `H_t`, which is empty in `W`; `U`-resident static data is the `p_U`-pullback of information attached to the unit itself.** This is the dual of (2): the sub-locus is `U` rather than `W`.

## 6. The degenerate scalar case

For fungible non-lendable instruments (equity, plain bonds), every field factors through `p_U`. The state sheaf satisfies

```
S  ≅  (p_U)^* (p_U)_* S
```

— the **unit of the adjunction** `(p_U)^* ⊣ (p_U)_*` evaluated at `S`. The scalar case is not a special construction; it is the locus at which this unit map is an **isomorphism, naturally and without choice**. The general case is recovered by instruments (futures) for which the unit map is not an iso. The degenerate case is therefore a **natural transformation** — the identity component — of the general case, not a separate model.

## 7. Recommendation

**State lives on `H_t ⊆ W × U`.** Implement the state dictionary as a typed sheaf on this locus. For each field, record its **factorisation class** (`p_U`-pullback, `p_W`-pullback, irreducibly per-pair) as type-level metadata — this is what §7 is reaching for but encoding as three storage shapes. Storage may still be optimised (share `p_U`-fields across the `W` fibre; avoid allocating per-pair rows until a holding appears) but the ontology is single.

Rewrite line 1034 as:

> *Unit state is a typed sheaf on the holding relation `H_t ⊆ W × U`. Each field declares its factorisation: per-unit fields (`multiplier`, `lifecycle_stage`) are pullbacks along `p_U`; per-wallet fields (HWM, mandate) are pullbacks along `p_W`; irreducibly per-pair fields (`accumulated_cost`) admit no factorisation. Conservation is the colimit `colim_W σ = 0` over the relevant fibre.*

All four test cases, the scalar degenerate case, and the QIS fibration dissolve in this framework.
