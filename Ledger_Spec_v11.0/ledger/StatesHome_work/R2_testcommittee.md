# R2 — TESTCOMMITTEE: Skeptical Testability Review

*Beck, Hughes, Fowler, Feathers, Lamport — reviewing the six proposals on where unit state lives.*

Framework: `ledger_v10.3.tex` Sec 11 (invariants P1–P10), §7.4 (futures `accumulated_cost`). Judged on (i) QuickCheck property, (ii) generator enumerability, (iii) surviving mutation, (iv) metamorphic oracle, (v) fault injection, (vi) change-safety.

---

## GROTHENDIECK — sheaf on H_t ⊆ W × U

**Property.** `prop_factorisation :: Gen (Unit, FieldName) -> Property` — read field's declared factorisation class; for irreducibly-per-pair assert `sum_{w in W_u} σ(w,u).φ = 0`; for p_U-pullback assert `∀w,w': σ(w,u).φ == σ(w',u).φ`. **Generators** finite only *after* the factorisation tag is fixed — which is not an enumerable type; the sheaf is semantic. Hughes: shrinker can't minimise across classes. **Surviving mutation**: "store `accumulated_cost` at p_U but return the trading wallet's value" survives for singleton W_u (case 4). **Metamorphic**: strong — the adjunction `(p_U)^* ⊣ (p_U)_*` gives a roundtrip oracle; dense vs compressed encodings must agree pointwise. **Fault injection**: sheaf gluing axiom has no executable sketch for out-of-order events. **Refactoring**: high in principle, nil in practice — tag lives in prose. **Verdict.** Conceptually strongest, operationally unrealised without Minsky's types.

---

## NOETHER — three sectors by symmetry (W, U, W×U)

**Property.** One per symmetry: `prop_SW_invariance :: Gen (UnitField, Perm W) -> Property` asserts `field(π·state) == field(state)` for p_U-fields; `prop_noether_current :: Gen Unit -> Property` asserts `sum_w ac(w,u) == 0`. Lamport: **only proposal directly yielding a small TLA+ spec** — three state vars σ_U, σ_W, σ_WU; actions partitioned by sector; P1, P6, P9 one-liners. **Generators** finite: random perms of small W, U; CDM-enum intents; per-sector ADTs. Shrinker bisects sector axis. **Surviving mutation**: "credit wallet B instead of A" — sum still zero but `prop_SW_equivariance` (permutation commutes with trade) fails; caught. Harder: swap HWM between two wallets — caught only with a "HWM depends on this wallet's history" assertion that Noether articulates but does not operationalise. **Metamorphic**: the permutation action *is* the relation `f(π·x) = π·f(x)`. World-class. **Fault injection**: duplicates clean per sector; out-of-order hits per-pair sector hardest (T-invariance fails). **Refactoring**: high; sectors cleave the code. **Verdict.** Best testability-per-page; smallest TLA+.

---

## MINSKY — typed split `UnitState | WalletState | PositionState`

**Property.** Three total accessors, three product-indexed ADTs — type signature *is* the property. No Option arm. `prop_conservation` built over `PositionState` alone. **Generators**: best of the six. `ProductSpec` declares `unit_state_type`, `position_state_type`, `zero_position` — exactly the `Arbitrary` instances QuickCheck needs. Input space a finite disjoint union indexed by CDM `ProductTypeEnum`. Structural enumerability. **Surviving mutation**: "credit wallet B" caught by conservation. "Widen WalletState with a unit key" caught at compile time (Beck's favourite test). Surviving: scalar-field swap inside one record (write `accumulated_cost` into `last_settlement_price`) — caught only by dedicated per-field properties. **Metamorphic**: `PositionState(w,u) == zero_position ⇔ w never traded u` — total, checkable biconditional; Feathers' change-safety handhold. **Fault injection**: default-by-construction makes case 4 total. Partial-lifecycle: three channels mutate independently — three generators must stay synced. **Refactoring**: very high — module-privacy localises invariants. **Verdict.** Most testable *in practice*; types do 60% of the work.

---

## DIRAC — single σ: W × U ⇀ S_u with `wallet_invariant` flag

**Property.** `prop_conservation` asserts `sum σ(w,u).ac == 0` when field metadata says `conserved=True`. `prop_wallet_invariance` asserts equality across `w ∈ W_u` for `wallet_invariant` fields. **Generators**: the synthetic `w_*` is a compression device and the partial `⇀` forces every test to pre-decide its domain. Hughes: partial functions reintroduce the Maybe arm Dirac claimed to eliminate. **Surviving mutation (the critical one)**: the reflexive-wallet trick HWM = `σ(w, u_∅)` admits *replace u_∅ with any other unit held by w* — the ledger type-checks, conservation holds, no structural test flags it. HWM "filed under AAPL." Needs a hand-written naming-convention test. **Metamorphic**: OK — canonical-at-w_* vs replicated must agree for wallet-invariant fields. **Fault injection**: out-of-order events desync `σ(w_*, u)` and `σ(w_trade, u)`; no type prevents it. **Refactoring**: moderate — `wallet_invariant` flag is data-level, not type-level. **Verdict.** Elegant; u_∅ is a testability tax. Critical gap.

---

## FINOPS — three keyed maps, reconciliation-first

**Property.** Minsky's, plus `prop_reconciliation :: Gen (Unit, Wallet) -> Property` asserting `PositionState(w,u)` projects to CCP SPAN / MT535 lines. P1 local: `sum_w PositionState(w,u).ac == 0` over one keyed map. **Generators**: finite, plus enumerable over the external-format axis (EMIR UTI, MT535, MT940) — external record formats *become* generator sources. Unique win. **Surviving mutation**: "credit wallet B" caught by reconciliation *and* conservation. Surviving: sub-cent rounding preserving the reconciliation projection — caught only by a decimal-arithmetic property test. **Metamorphic**: strongest of all six — `ledger ↔ CCP report ↔ regulator report` must agree. True oracle by construction. **Fault injection**: duplicates and partial lifecycle clean per-map; out-of-order is genuinely hard (reconciliation is end-of-day stateful). **Refactoring**: high, same as Minsky, with external contracts pinning behaviour. **Verdict.** Minsky plus oracles. Best for CHANGE SAFETY.

---

## ROSETTA — per-(w,u) default, per-unit as template

**Property.** Every `BusinessEvent` mutates some `TradeState`; P6 (lifecycle idempotency) local per `(w,u)`. **But** `sum_w ac(w,u) = 0` becomes a cross-TradeState scan keyed on product `u` — global, not local. Lamport: the TLA+ action grows a universal quantifier over all trades referencing `u`. **Generators**: CDM-enum-driven — native to Sec 11.5's generator universe; `EventIntentEnum` *is* the generator. **Surviving mutation**: "bond coupon paid to A but not to B's TradeState" caught (Rosetta's founding case). Surviving: template drift — mutating `multiplier` on the product template is caught only by a rarely-exercised `IndexTransitionInstruction` generator. **Metamorphic**: CDM `Qualify_*` functions *are* oracles. **Fault injection**: strongest on duplicates; weakest on case 4 (`unit_state` = Maybe). Beck: branch factor doubles. **Refactoring**: high inside CDM, costly outside (wallet-level CSA, QIS strategy state don't fit). **Verdict.** CDM alignment unique; makes `sum_w = 0` non-local and reintroduces the Maybe arm.

---

## Cross-cutting probes

**Global vs local invariants.** `sum_w ac(w,u) = 0` is global by nature. Minsky/FinOps/Noether/Grothendieck keep it *index-local* (scan one map keyed on `(·, u)`); Dirac adds w_* noise; Rosetta makes it cross-table. None reduce it to per-event without the `buyer_delta + seller_delta = 0` factoring (Minsky §2).

**Default vs Maybe for not-yet-traded.** All proposals → **default** (total accessor) except Rosetta → **Maybe**. Defaults halve test branching.

**Differential test vs v10.3.** Current v10.3 (per-unit dict + per-(w,u) futures) is **isomorphic** to Minsky and FinOps, isomorphic to Dirac modulo synthetic w_*, a **projection** of Grothendieck (drop factorisation tag), a **quotient** of Rosetta. Writable for Minsky/FinOps/Dirac; conceptual for Grothendieck; lossy for Rosetta and Noether's wallet sector.

**TLA+ feasibility.** Noether > Minsky ≈ FinOps > Dirac > Rosetta ≫ Grothendieck.

### Critical testability gaps

- **DIRAC** — `u_∅` reflexive-wallet trick admits mutations no structural test catches.
- **ROSETTA** — `sum_w ac(w,u) = 0` becomes non-local; Maybe arm doubles branches.
- **GROTHENDIECK** — factorisation tag not operationalised; untestable without Minsky's types.

---

## Ranking (best → worst, testability + change-safety)

1. **FINOPS** — Minsky's typed split plus external reconciliation oracles; strongest change-safety net.
2. **MINSKY** — types do the work; three total accessors; zero Maybe branches; best mutation coverage without external oracles.
3. **NOETHER** — symmetry gives free generators, free metamorphic relations, smallest TLA+ spec.
4. **ROSETTA** — CDM-native generator universe, but makes `sum_w = 0` non-local and adds Maybe arms.
5. **DIRAC** — elegant unification, but `u_∅` lets a class of mutations slip past structural tests.
6. **GROTHENDIECK** — conceptually strongest, operationally unrealised; testable only after importing Minsky's types.

**Verdict.** Adopt Minsky's three-channel split as the *implementation* substrate, FinOps's external-reconciliation oracles as the *test* substrate, Noether's symmetry properties as the *invariant* language.
