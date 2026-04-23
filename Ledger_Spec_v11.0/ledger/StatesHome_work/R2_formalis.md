# FORMALIS — R2 Adversarial Review of StatesHome Proposals

*Committee: Leroy (chair), Coquand, Huet, Paulin-Mohring, de Moura, Avigad.*
*Target: the six R1 proposals in `/home/renaud/A61E33BB10/output/v10.3/StatesHome_work/`.*
*Principle: we do not check that the sheaves typeset; we check that the programs extracted from them are total, deterministic, and invariant-preserving.*

---

## Grothendieck (sheaf on H_t with factorisation classes)

The sheaf lives on `H_t = {(w,u) : w(u) ≠ 0}`, a **time-varying** carrier. This is the fatal move.
1. **Invariant breakage on close-out / re-open.** When wallet `w` trades out (futures net-zero) the pair `(w,u)` leaves `H_t`, so `σ(w,u).accumulated_cost` is no longer a section at `t`. But the invariant `Σ_w accumulated_cost(w,u) = 0` is a *colimit over `W` at fixed `u`*; dropping the zero-balance term silently **re-indexes the sum**. Counter-example: `w_A, w_B` hold opposite futures (ac = +5, -5). At `t+1` `w_B` closes; `H_t` now contains only `(w_A, u)` with ac = +5 and the colimit is +5, not 0. If `w_B` re-opens at `t+2`, the sheaf has no mechanism to **restore** its prior `accumulated_cost`; the proposal is silent on historical fibres. Non-determinism under replay: whether you see `0` or `+5` depends on whether you evaluate before or after garbage-collection of empty fibres.
2. **Factorisation-class is metadata, not a proof.** "Declare each field `p_U`-pullback or irreducibly per-pair" — but nothing in the sheaf prevents a developer from writing a `p_U`-tagged field whose value in fact depends on `w`. The sheaf condition is stated ("sections glue"), never verified. Hand-wavy: "Storage may still be optimised" defers the only engineering content.
3. **Unfalsifiable framing.** "Three candidates are sections of the same sheaf" is a *restatement*, not a choice. The proposal refuses to commit to a concrete `(key, value)` representation, so no implementation can fail its spec.

**Verdict: FAIL.** (The sheaf is correct mathematics and incorrect engineering. `H_t` must be replaced by a *monotone* carrier — the set of pairs ever held — if this framing is to support replay.)

---

## Noether (three-sector by S_W × S_U symmetry)

1. **Symmetry is not enforced; it is declared.** "Every field declares which subgroup it transforms under" is a social convention. No type-level mechanism prevents a developer from putting a `w`-dependent value (e.g. a wallet's mandate class) into the `s(u)` sector. Counter-example: store `preferred_ccp(u)` per-unit; two wallets with opposing CCP routing will silently share one entry and the next `f(unit, state, md)` call becomes non-deterministic in wallet identity. S_W invariance was *asserted*, not *proved*.
2. **The Noether current is not structurally maintained.** Claim (§3.1): "if `Σ_w s(w,u) = const(u)` then store per `(w,u)`". The reverse direction is the one needed: storing per `(w,u)` does **not** make the sum conserved. Consider `accumulated_cost` indexed by `(w,u)` and an event handler that credits `w_A` without debiting anyone — the Noether argument does not detect it. Conservation is an obligation on *event handlers*, not on the storage key; the proposal conflates the two.
3. **QIS fibration unaddressed.** "A QIS is both wallet and unit" is waved through ("the two sectors are orthogonal"). They are not orthogonal: the QIS's `triggered_barrier` is a field of `s(u_QIS)` whose *value* is set by moves on `s(w_QIS_exec, u_future)`. Cross-sector write dependency breaks the `S_W × S_U`-module decomposition.

**Verdict: CONDITIONAL** — conditional on (a) a schema-level check that rejects field declarations inconsistent with their symmetry class, and (b) an explicit statement that conservation is proved at the event handler, not the storage layer.

---

## Minsky (typed split: UnitState / WalletState / PositionState)

Closest to correct. The flaws are at the seams.
1. **`get_position_state(w, u)` totality is bought with a `zero_position` default that is itself a specification hole.** For a futures unit `u`, the declared `zero_position` is `accumulated_cost = 0`. But this *silently creates a `(w,u)` row* semantically indistinguishable from "`w` traded in and out leaving ac = 0". Composition hazard: a lifecycle event that iterates "all wallets with non-zero state" cannot distinguish "never traded" (should be skipped) from "flat after round-trip" (may have downstream obligations, e.g. pending VM). Counter-example: a VM settlement on settlement date must touch every wallet that held `u` during the session, including those now flat. `zero_position` merges these two sets.
2. **Three disjoint channels re-introduce the very divergence Minsky condemns.** Per-wallet `WalletState[Managed]` and per-position `PositionState[u]` can both legitimately store fee accruals (management fee is `w`-scoped; performance fee on a sub-position is `(w,u)`-scoped). Nothing in the type signature prevents a developer from double-booking fees across channels. The compiler rejects illegal *types*; it does not reject illegal *duplications*.
3. **`WalletState` keyed by `mandate_class`, not by wallet.** This is an unannounced quotient: two wallets with identical mandate class share a `WalletState` instance? If yes, HWM cross-contaminates; if no, the indexing contradicts the signature `WalletState : W -> WalletMandateState`. The §5 signature is ambiguous on whether the keying is `W` or the mandate class.

**Verdict: CONDITIONAL** — conditional on (a) distinguishing `absent` from `zero` in `PositionState` (use `Option<ProductPositionState>` *with* a declared zero used only for arithmetic, not for iteration), and (b) resolving the `W` vs `mandate_class` keying.

---

## Dirac (single σ : W × U ⇀ S_u, partial)

1. **`u_∅` is a hack dressed as beauty.** Claiming managed-account HWM lives at `σ(w, u_∅)` where `u_∅` is "the wallet's own contract unit" requires *every* wallet to carry its own synthetic unit in `U`. This collides with `Σ_w w(u) = 0` conservation: is `w(u_∅) = 0`? By whose balancing counterparty? The "self-contract" has no counterparty and therefore violates the very conservation law Dirac praises. The reflexive identity "wallets are managed accounts" (Sec 6.1) is an *isomorphism*, not a *licence to reify* each wallet as a unit inside `U`.
2. **Partiality hides determinism holes.** `σ : W × U ⇀ S_u` is explicitly partial; the accessor `get_state(w,u)` is promised "total conceptually" by compression to `σ(w_⋆, u)`. But `w_⋆` (the universe wallet) has no formal definition — is it a distinguished element of `W` or a symbolic projection? If the former, `Σ_w w(u) = 0` breaks (what is `w_⋆(u)`?); if the latter, `get_state(w,u)` is not a function in the ledger's type discipline, and replay depends on whether the compression layer was applied before or after the event.
3. **`wallet_invariant=True` is unchecked metadata** — same attack as on Grothendieck's factorisation-class. The "physics is `W × U`, representation compresses along invariants" argument is unfalsifiable: any compression bug is diagnosed as a representation issue, not a physics issue.

**Verdict: FAIL.** The `u_∅` device breaks conservation; the partial-function signature smuggles in a non-deterministic totalisation.

---

## Finops (three keyed maps, CDM-flavoured)

1. **Cross-wallet leakage at the `PositionFields` layer.** The schema `W × U → PositionFields` is a single global map; nothing in the signature prevents the futures smart contract from reading `PositionFields(w', u)` for `w' ≠ w`. Counter-example: a margin-netting smart contract iterates `{w' : PositionFields(w',u) ≠ ⊥}` and leaks positions across unrelated clients. The §8 "schema" is a database, not a capability.
2. **`Σ_w ac(w,u) = 0` is *not* checked by the model, only *expressible*.** §5 argues "conservation is structurally a `(w,u)` property". Expressibility ≠ preservation. A `QuantityChangeInstruction` that updates one `PositionFields` row without the compensating row passes the type check. The proposal points at the invariant and calls it discharged.
3. **Idempotency keying is ambiguous for cross-axis events.** A corporate action (per-unit) generates cashflows (per-position). §3 says unit events store `state[u].paid_coupons[date] = True`; but replay must also be idempotent on the *moves* emitted to each `(w,u)`. If the move stream is replayed, the per-unit flag is set (no-op), but if the per-`(w,u)` emission is not separately guarded, it double-credits. Counter-example: two concurrent executors process the coupon event, both see `paid_coupons[date] = False`, both emit the moves.

**Verdict: CONDITIONAL** — conditional on (a) per-wallet capability scoping on `PositionFields` access, (b) making conservation a handler-level post-condition with a verified Lyapunov argument, (c) explicitly joining per-unit and per-`(w,u)` idempotency under a single event-id key.

---

## Rosetta (CDM-native: per-(w,u) default, per-unit for template only)

1. **Untraded listed unit has no state at all** — §4.4 explicitly says `unit_state` "should be empty/N/A" for a listed option never traded, and then claims `ACTIVE` is "a category error". This destroys lifecycle totality: `f(unit, state_t, md)` is now undefined on `(u, ⊥, md)` for every freshly listed `u`, which means the first trade cannot be validated against lifecycle stage. Counter-example: an option is listed, delisted the same day (corporate action), never traded. Under this proposal the lifecycle stage transitions from *undefined* to *undefined* with no state trajectory — a replay of the delist cannot be detected as idempotent.
2. **"Per-(w,u) by default" double-counts immutable terms.** CDM `EconomicTerms` on `NonTransferableProduct` is shared-by-key, but the proposal's §6 recommendation inverts the default and pushes bond `paid_coupons[date]` to per-`(w,u)`. Counter-example: a bond held by 10 wallets has 10 parallel `paid_coupons` maps; a coupon payment event must update 10 rows atomically. Any failure mid-iteration leaves the ledger in a state where wallet A thinks the coupon is paid and wallet B does not — exactly the divergence Minsky §C forbids, now introduced *by design*.
3. **"Two holders can disagree on whether their coupon was paid" is real, but the proposal solves it by *denying a canonical answer*.** Economically, `paid_coupons[date]` on the *issuer's schedule* is a fact about the instrument, not a fact about the holder. The holder-specific datum is "did I receive my share?" — that is an accounts-receivable question, not a product-state question. Conflating them denies the ledger a single source of truth for the instrument and forces reconciliation to resolve it — breaking the §2.6 single-source-of-truth rule the ledger claims.

**Verdict: FAIL.** Inverting the default destroys per-unit immutability and breaks the single-source-of-truth invariant. Rosetta is correct that `TradeState` is per-`Trade`; it is wrong that *all* mutable state must follow suit.

---

## Summary

| Proposal      | Verdict      | Binding condition |
|---------------|--------------|-------------------|
| Grothendieck  | FAIL         | (carrier must be monotone; storage must be concrete) |
| Noether       | CONDITIONAL  | schema-level symmetry check + handler-level conservation proof |
| Minsky        | CONDITIONAL  | distinguish `absent` from `zero`; fix `W` vs mandate-class keying |
| Dirac         | FAIL         | `u_∅` breaks conservation; partial σ smuggles non-determinism |
| Finops        | CONDITIONAL  | capability scoping + handler-level invariant preservation + unified event-id idempotency |
| Rosetta       | FAIL         | untraded units lose lifecycle totality; default inversion breaks SSOT |

*The common pathology: every proposal states an invariant and points at the storage shape as if the shape discharged it. Storage shapes are necessary, not sufficient. Conservation, idempotency, and determinism are obligations on event handlers, and no committee member should accept a proposal that does not name the handler-level proof obligation.*

— FORMALIS, sealed this day.
