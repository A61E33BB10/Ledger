# R2 — Jane Street CTO Review: Where Does Unit State Live?

**Reviewer:** CTO, Jane Street. Adversarial. Production lens.
**Under review:** six R1 proposals in `/home/renaud/A61E33BB10/output/v10.3/StatesHome_work/`.
**Target doc:** `/home/renaud/A61E33BB10/output/v10.3/ledger_v10.3.tex`, §3, §6, §7, §10.

I optimise for the junior on-call at 3am. Mathematical elegance that doesn't compile to a short, total accessor is a liability.

---

## Grothendieck (sheaf on H_t)

Mathematical cosplay over a partial function. The "sheaf" never uses a single gluing axiom in the proposal — no cover, no equaliser, no descent. What is actually proposed is: `sigma : (W x U) -partial-> S_u` plus a per-field tag saying whether it depends on `w`, on `u`, or both. That is a partial function with a compression hint. Calling it a sheaf is noise. **Writable type?** Only as `dict[(W,U), S_u]` plus a `FactorisationClass` enum per field — i.e. exactly Dirac or Finops, with a category-theoretic preamble you delete before shipping. **Runtime cost:** identical to any other `(W,U)` map if you actually instantiate H_t; the "Kan extension" storage optimisation is a `Dict[U, S_u]` cache with a fallback — which is what everyone already writes. **Refactor cost:** §7 rewritten in sheaf prose. Every reader pays the tax. **30-min rule:** fails. A new engineer will not read "colim_W sigma = 0" and recognise `sum_w accumulated_cost = 0`. **10-year survival:** the abstraction rots the moment someone needs to add a per-(w,u,ccp) field and the `Loc` poset has to be re-derived. Reject. Not shippable as written.

## Noether (three-sector by symmetry)

The destination is right; the justification is theatre. "Symmetry under `Sym(W) x Sym(U)`" is just "the field depends on `w`, on `u`, on both, or on neither" — restated as group theory. The "forcing" argument is post-hoc: wallet-relabelling invariance does not *force* per-unit storage, it only forbids per-wallet-dependence. The actual engineering rule — *index by what the field actually varies over* — needs no representation theory. **Writable type?** Yes, and it's the same three-map split as Finops / Minsky. **Runtime cost:** three maps, identical to the others. **Refactor cost:** low; line 1034 becomes a three-way rule. **30-min rule:** fails if you keep the `Sym(W) x Sym(U)` language; passes if you say "field is keyed by its free variables". **10-year survival:** fine in practice, but the prose will be rewritten within a year because no production engineer will invoke Noether to decide a column name. Ship the conclusion, delete the derivation.

## Minsky (typed three-channel split)

This is the one I'd ship, with one correction. Three total accessors, each with product-specific types, each rejecting a concrete class of illegal states. The illegal-states table (§1) is the right way to argue a type design — it is the only R1 that enumerates bugs the compiler will now catch. **Writable type?** Yes, clean in all three languages:

```python
# Python + mypy strict
@dataclass(frozen=True, slots=True)
class View:
    unit_state:     Mapping[UnitId, UnitState]
    wallet_state:   Mapping[WalletId, WalletState]
    position_state: Mapping[tuple[WalletId, UnitId], PositionState]
```

```ocaml
type view = {
  unit_state     : (unit_id, unit_state) Map.t;
  wallet_state   : (wallet_id, wallet_state) Map.t;
  position_state : (wallet_id * unit_id, position_state) Map.t;
}
```

**Runtime cost:** 10k positions in one wallet → 10k entries in `position_state` keyed on a tuple, a few entries in `wallet_state`. 1M wallets holding one unit → one `unit_state` entry (static terms shared), 1M `position_state` entries (necessarily — each holder's cost basis is genuinely different). No worse than any alternative; strictly better than Dirac's "store at w_star" trick, which adds a reserved sentinel wallet the persistence layer must special-case. **Refactor cost:** low. §7 line 1034 goes from prose-qualifier to type-system. §3's `UnitEntry.unit_state` gets split into static `product_terms` and `unit_state` for true per-unit mutable state (lifecycle_stage, last_settlement_price). §6 managed-account state moves to `wallet_state` — which is where it always belonged and where the current doc has no clean home. **30-min rule:** passes. Three accessors, three keys, done. **10-year survival:** excellent. The correction: Minsky's claim that `WalletState` is indexed by mandate-class is over-design — ship `WalletState` keyed purely by `WalletId` with an optional mandate field; introduce a mandate-class type only when a second mandate type actually appears.

**On "is PositionState the primary map and the others derived?"** No. The three are independent. `accumulated_cost` is not derivable from unit terms. `last_settlement_price` is not derivable from positions (it comes from an exchange feed and is the same for all holders — storing it per-position invites drift). HWM is not derivable from either. These are three disjoint ontologies; treating one as primary is exactly the error the current doc makes in the other direction.

## Dirac (single sigma on W x U, universe wallet w_star)

Beautiful; unshippable. The "universe wallet" `w_star` is operational debt. Every persistence layer, every ACL check, every reconciliation job now has a reserved wallet-id that means "not really a wallet". The managed-account-as-`u_empty` trick is worse: you invent a fictitious unit per wallet so that HWM can ride on `(w, u_empty)`. Now every unit-iterating query must filter out `u_empty`s, and the Unit Store has 10M entries for managed accounts that aren't products. **Writable type?** Yes — `dict[(W,U), S]` — but the type tells you nothing about which fields are shared versus per-holder. You re-derive it at runtime via `wallet_invariant` flags, which is where the class of bugs Minsky forbids statically reappear. **Runtime cost:** 1M wallets holding one unit → the "store once at w_star" optimisation is a read-through cache; correct, but every writer must check the invariant flag or corrupt shared data. Minsky's split makes that impossible by construction. **30-min rule:** passes for the equation, fails for the operational gotchas (`w_star`, `u_empty`). **10-year survival:** the `w_star`/`u_empty` sentinels will ship a P1 within two years when a ledger export dumps them as real rows. Reject.

## Finops (three keyed maps)

Substantively identical to Minsky's recommendation. Stronger on external-reconciliation grounding (CCP, MT535, MiFID II) — that argument alone should settle it: **internal state must be keyed at the granularity of the external record it reconciles against**, and that granularity is `(w,u)` for positions, `w` for mandates, `u` for contract terms. No theory required. **Writable type?** Same signatures as Minsky. **Double-entry checked how?** This is the weakness: the doc says "make the key part of the type system" but the `sum_w ac(w,u) = 0` invariant is run-time — no type system a ledger will use enforces an existentially-quantified decimal sum. Minsky is explicit about this (§2 of R1_minsky): compile-time enforcement is on the *per-event* pair `(buyer_delta, seller_delta)`; the global sum follows by induction. Finops should adopt that framing. **Refactor cost:** same as Minsky. **30-min rule:** passes easily — the product-family table (§7 of R1_finops) is the clearest document in the set. **10-year survival:** excellent. Ship Minsky's type discipline + Finops' product-family table as the §7 rewrite.

## Rosetta (CDM-aligned, per-(w,u) default + per-unit for template)

Strongest critique of the current v10.3, most dangerous recommendation. The insight that `TradeState` is the only CDM object that mutates, and it is per-(counterparty,product), is correct and important. But the "forbid state on the wallet" edict is over-fitted to OTC where there is no wallet. A managed-account HWM as a synthetic TRS `TradeState` is the exact cleverness I distrust: it invents a phantom trade to fit a data model that doesn't have a wallet layer. §4.4 correctly nails the category error of `lifecycle_stage = ACTIVE` on an untraded unit — that edit is right and should land. But listed markets have security-master realities (exchange lifecycle: LISTED / HALTED / DELISTED; corporate actions; per-unit last_settlement_price consumed by every holder's VM calc) that are genuinely per-unit mutable state, not "rare IndexTransitionInstruction edge cases". **Writable type?** Yes, CDM-aligned, but the "per-(w,u) default" pushes shared fields into per-position storage and invites drift — Minsky's illegal-state class C exactly. **Runtime cost:** 1M wallets holding one unit × per-holder copies of `last_settlement_price` = 1M redundant cells updated every settlement. Unacceptable. **30-min rule:** passes for CDM-literate readers; fails otherwise. **10-year survival:** the "HWM as synthetic TRS" will be reverted within a release cycle the first time ops has to debug it. Adopt the §4.4 listed-untraded correction; reject the wallet-state ban.

---

## What none of them got right

**1. Persistence and indices.** All six proposals argue ontology; none of them address that `position_state` needs two indices (`by_wallet`, `by_unit`) because the 10k-positions-in-a-wallet query and the 1M-wallets-holding-a-unit query both have to be O(log) or O(1). Minsky/Finops's `Map[(W,U), S]` is a logical type; the production shape is two covering indices plus a write-path that updates both atomically. Pick an ordered map keyed by `(wallet, unit)` plus a secondary `(unit, wallet)` index.

**2. Event-level conservation, not state-level.** Every proposal frames `sum_w accumulated_cost(w, u) = 0` as a state invariant. It is not enforceable at that layer. It is a *theorem* that follows from per-event structural zero-sum — the `Trade` event handler must produce `(buyer_delta, seller_delta)` summing to zero by construction. Only Minsky says this. Make it the center of §7, not a footnote.

**3. Static vs mutable unit state.** `multiplier`, `currency`, `expiry` are static product terms; `last_settlement_price`, `lifecycle_stage`, `paid_coupons` are mutable per-unit state. These should be two different types on two different tables, not one `UnitState` blob. Rosetta is half-right here (template vs TradeState); none of the others separate the two. §3's `UnitEntry.unit_state` is currently doing both jobs, and that is the root ambiguity driving the whole debate.

**4. Idempotency keys.** Only Finops mentions them. In production, the question "did I already apply coupon C to wallet W holding unit U?" is answered by a key, and that key's shape decides where state lives more decisively than any ontology argument.

---

## Ranking (best → worst for shipping)

1. **Minsky.** The only proposal that argues via illegal states a compiler rejects. Types, not prose. Ship this.
2. **Finops.** Same destination, additional grounding in external reconciliation; product-family table is the clearest §7 rewrite artifact. Ship alongside Minsky.
3. **Rosetta.** Correct on untraded-unit lifecycle, correct that `TradeState` is the CDM home for per-position mutable state. Partially adopt; reject the wallet-state ban and the synthetic-TRS managed-account trick.
4. **Noether.** Right answer, wrong derivation. Keep the three-sector conclusion; delete the group-theory prose.
5. **Dirac.** Seductive unification, two fatal sentinels (`w_star`, `u_empty`). Reject.
6. **Grothendieck.** Category-theoretic restatement of a partial function. Unshippable. Reject.

**Shipping recommendation:** adopt Minsky's typed three-channel split, use Finops's product-family table as the concrete §7 body, apply Rosetta's §4.4 correction to §3 (split static `product_terms` from mutable `unit_state`), and add an explicit §7 subsection on per-event structural zero-sum as the mechanism by which cross-wallet conservation is enforced.
