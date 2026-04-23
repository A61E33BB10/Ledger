# R1 — MINSKY: Where Does Unit State Live?

**Question.** Should state live on the unit, on the wallet, or on the `(wallet, unit)` pair?
**Stance.** Make illegal states unrepresentable. Everything else follows.

---

## 1. The four alternatives, against the four test cases

Let `U` be a unit id, `W` a wallet id. Write:

- `UnitState(U)` = a value keyed by unit.
- `WalletState(W)` = a value keyed by wallet.
- `PositionState(W,U)` = a value keyed by the pair.

We evaluate each alternative by enumerating states it permits that have no economic meaning.

### A. State-on-unit ONLY (`state : U -> S_u`)

Works for: bonds (coupons paid, matured), equities (cum-div), listed option terms.
Fails for:

1. **Futures `accumulated_cost`.** A single unit-level number would conflate wallets; the invariant `sum_w accumulated_cost(w) = 0` cannot even be *expressed* because there is no `w`. The map `U -> Decimal` can hold ANY value — there is no structural constraint tying it to wallet balances.
2. **Managed account (HWM, benchmark, mandate).** A managed account is a *wallet* concept. To attach HWM to the unit is a category error: the same unit (e.g., AAPL) can be held by a drawdown-limited account and an unconstrained one simultaneously.
3. **QIS trading futures.** The QIS strategy unit has per-unit state (weights, last rebalance). But the *sub-instruments* it trades (the futures legs) still need per-wallet `accumulated_cost`. A unit-only model must either duplicate the futures state inside the QIS unit (breaks locality — the futures smart contract can no longer read its own state) or crash.
4. **Never-traded instrument.** Works fine: the unit exists in the Unit Store with default product state. No wallet dimension, no emptiness problem.

**Illegal states representable:** per-wallet economic quantities mis-shared across wallets. **Unrepresentable at type level:** none of the wallet-specific ones.

### B. State-on-wallet ONLY (`state : W -> S_w`)

Works for: HWM, mandate, benchmark, drawdown limit, risk budget.
Fails for:

1. **Futures accumulated_cost.** Expressible (key by wallet) but loses the *contract* dimension — a wallet holding two different futures would need a map-inside-the-state. Possible, but equivalent to `PositionState` in disguise.
2. **Managed account.** Natural fit.
3. **QIS.** The QIS unit's shared state (current weights, barrier-triggered flag) is a property of the *unit*, not of any holder. Pushing it to wallet-level means every subscriber re-invents the same state — and they can now *disagree*. Two holders of the same QIS unit could carry different `triggered_barrier` flags. That is an illegal state that wallet-only allows.
4. **Never-traded instrument.** Cannot represent. There is no `w` to key on. Either default, `Option`, or absence — see §3.

**Illegal states representable:** disagreement across holders about the objective state of a shared contract; untyped lifecycle for never-traded units.

### C. State-on-(wallet, unit) ONLY (`state : (W,U) -> S_{w,u}`)

Works for: futures accumulated_cost, per-wallet margin, CCP routing per client.
Fails for:

1. **Shared per-contract fields** (`last_settlement_price`, `multiplier`, `currency`, `lifecycle_stage`). Replicating these across every `(w,u)` entry permits them to *diverge* — a bug-class equivalent to database denormalisation. Two wallets holding the same contract could carry different `last_settlement_price`; the type system would not complain. That is precisely an illegal state.
2. **Managed account.** The HWM applies to the wallet *regardless of which units it holds*; keying by `(w,u)` forces an arbitrary choice of `u` — a category error in the opposite direction from §A.
3. **QIS.** Same shared-field divergence problem as futures, worse: the `current_weights` vector duplicated per holder.
4. **Never-traded instrument.** Has no `(w,u)` entry at all — must rely on absence as the "state". That makes "not yet traded" indistinguishable from "lost the entry". A reader cannot tell.

**Illegal states representable:** divergence of objectively-shared fields across replicas.

### D. Explicit hybrid with typed split (RECOMMENDED)

Three disjoint state channels, each with its own accessor and its own product-specific type:

```
UnitState     : U       -> ProductUnitState
WalletState   : W       -> WalletMandateState
PositionState : (W,U)   -> ProductPositionState
```

Each product's smart contract declares, via its type, which channels it uses. `get_unit_state(u)`, `get_wallet_state(w)`, and `get_position_state(w, u)` are three total functions, each returning a well-typed value (or a typed default — see §3).

This is the only alternative where the compiler rejects every one of the illegal states above:

| Illegal state | A | B | C | D |
|---|---|---|---|---|
| Per-wallet cost mis-shared across wallets | permitted | — | rejected | rejected |
| Per-holder divergence on shared contract field | — | permitted | permitted | rejected |
| Managed-account mandate keyed to a unit | permitted | rejected | permitted | rejected |
| QIS sub-instrument state folded into strategy | permitted | — | — | rejected |
| Never-traded unit with no well-typed state | rejected | permitted | permitted | rejected |

---

## 2. Can types enforce `sum_w accumulated_cost(w) = 0`?

No — not structurally in any type system a practical ledger will use. This invariant is *extensional*: it quantifies over a set of wallets whose cardinality is unknown at compile time, and whose sum uses decimal arithmetic the type system does not evaluate.

What types *can* do is stronger than it appears:

- Make `accumulated_cost` only mutable via a `Trade` or `Settle` event handler whose input/output is typed such that the **pair** `(buyer_delta, seller_delta)` sums to zero by construction. The per-event conservation is structural; the global invariant then follows by induction on the event stream.
- Ban direct writes to `PositionState` outside the futures smart contract (enforced by module privacy / opaque types).

**Conclusion:** the sum-zero invariant is a runtime-checked theorem, but the *only* way to violate it is to break a structurally enforced per-event invariant. That is the correct factoring.

---

## 3. Never-traded instrument: default, `Option`, or absence?

Three framings, one winner.

- **Absence.** "No entry" means the unit has never been traded. Bad: conflates "new unit" with "data loss"; forces callers to branch on existence before they can read lifecycle stage. Violates totality.
- **`Option<State>`.** Every read is `Option<S>`; callers pattern-match. Safe but boilerplate, and it mis-models the product: a freshly-listed ESZ6 future *does* have a lifecycle stage (`ACTIVE`), a multiplier, and a currency — all known at registration.
- **Typed default (RECOMMENDED).** The Unit Store creates the `UnitState` at registration with the product's initial state (stage `ACTIVE`, no settlements yet, empty coupon flags, etc.). `get_unit_state(u)` is total and never `None`. For `PositionState(w, u)` where wallet `w` has never touched unit `u`, return the product's *zero element* (e.g., `accumulated_cost = 0`). The zero element must be declared by the product's smart contract — no wildcard default.

Absence is reserved for the *unit* itself: if `u` is not in the Unit Store, the executor rejects the move. That is a different failure and deserves a different signal.

---

## 4. QIS: strategy-level vs sub-instrument state

The type system distinguishes them by keying channel:

- **Strategy-level** (`current_weights`, `last_rebalance_date`, `triggered_barrier`) lives in `UnitState(u_qis)`. One value per QIS unit, shared by all holders, invariant across holders by construction (only one entry exists).
- **Sub-instrument** (per futures leg's `accumulated_cost`) lives in `PositionState(w_strategy_wallet, u_future_leg)`, owned by the futures smart contract. The QIS smart contract *never* writes to it; it emits trade events that the futures contract handles.
- **Subscriber-level** (HWM, mandate constraints of the end client) lives in `WalletState(w_client)`.

This factoring is the single most important correctness property for composite products: the QIS contract cannot corrupt futures state, and vice versa, because they write to disjoint channels under disjoint module ownership.

The per-CCP clearinghouse caveat (line 1168) is the same pattern: `clearinghouse` is `PositionState(w, u)`, not `UnitState(u)`. The TeX is currently mis-filed; the fix is trivial under the hybrid.

---

## 5. Recommended type signatures

```
-- Three accessors. Each is TOTAL.
view.get_unit_state     : Unit              -> UnitState[u.product]
view.get_wallet_state   : Wallet            -> WalletState[w.mandate_class]
view.get_position_state : Wallet -> Unit    -> PositionState[u.product]

-- Each product's smart contract declares its three state types
-- (any of which may be the Unit type `()` when unused):
ProductSpec:
    unit_state_type     : Type              -- e.g. BondCouponFlags, QisWeights, ()
    position_state_type : Type              -- e.g. FuturesAccumCost, ()
    zero_position       : position_state_type   -- the "never traded" value
```

`WalletState` is indexed by a *mandate class* (managed, prop, omnibus), not by unit — it is structurally decoupled from `U`. A wallet-level HWM typed `WalletState[Managed]` cannot accidentally be keyed to AAPL.

---

## 6. Single recommendation

**Adopt alternative D: an explicit, typed three-channel split — `UnitState`, `WalletState`, `PositionState[(w,u)]` — with product-specific types on each channel and a declared `zero_position` for the never-traded case.** Current v10.3 (per-unit default, `(w,u)` for futures `accumulated_cost`) is alternative D in practice but under-documented: the `get_unit_state(unit)` accessor at line 1052 silently carries two keying regimes. Promote the split to first-class, give `PositionState` its own accessor, move `clearinghouse` out of the per-contract block, and the caveat at line 1168 disappears into the type system rather than sitting as prose.
