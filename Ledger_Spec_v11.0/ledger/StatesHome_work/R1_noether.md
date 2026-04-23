# Where Does Unit State Live?
## A Noetherian Analysis of the Ledger v10.3

> *"If one proves the equality of two numbers by showing a ≤ b and then b ≤ a, it is unfair; one should instead show that they are really equal by disclosing the inner ground for their equality."* — Emmy Noether

The question "where does state live?" is not a storage question. It is a **representation theory** question: under which group actions must a piece of state transform covariantly, and which must leave it invariant? Once we identify the symmetry group acting on the ledger, the location of state is forced, not chosen.

---

## 1. The Symmetry Group of the Ledger

The ledger carries (at least) four independent group actions:

| Symmetry | Group | Action |
|---|---|---|
| **S_W** — wallet relabelling | Sym(W) | permute wallet identifiers |
| **S_U** — unit relabelling | Sym(U) | permute unit identifiers |
| **T** — time translation | (R, +) | shift clock origin |
| **C** — currency/numeraire rescaling | (R+, x) | rescale numeraire unit |
| **G_W** — position gauge (for SBL 6-vector) | subgroup of GL(6) preserving "own + onloan − borr + coll_post − coll_recv = net" | internal rotations of the 6-vector |

For each symmetry, the Noether prescription is mechanical: **the state must transform under exactly the symmetries that touch its arguments, and be invariant under the rest.**

### 1.1 Noether currents already present

- **S_W invariance of the balance layer** → conservation of `sum_w w(u) = 0` per unit (the wallet-sum current).
- **T invariance of the lifecycle function `f`** → historical consistency: `f` has no hidden clock, so replaying events gives the same trajectory.
- **S_U invariance of booking mechanics** → structural closure: trades of AAPL and MSFT obey the same algebra.

These are the conservation laws already baked in. Now we ask the converse: *given a proposed state location, which symmetries does it respect?*

---

## 2. The Forcing Argument

State `s` is a function of some index set. The index set determines which group acts on it.

| State location | Transforms under | Invariant under |
|---|---|---|
| `s(u)` — per unit | S_U | S_W, wallet gauge G_W |
| `s(w)` — per wallet | S_W | S_U |
| `s(w, u)` — per pair | S_W x S_U | — |

**Rule (Noether's razor for state).** *State must live on the smallest index set whose symmetry group faithfully captures every transformation that can change its value.*

If `s` depends on a wallet's trade history, it **cannot** be invariant under S_W — relabelling wallets moves the history. Therefore per-unit storage `s(u)` is a category error: it pretends invariance that does not hold, and the first wallet-relabelling test would break it.

Conversely, if `s` is determined entirely by the contract specification (strike, maturity, coupon schedule), it **must** be invariant under S_W. Storing it per wallet would create |W| redundant copies, and the "which copy is canonical?" question has no symmetry-respecting answer.

**The choice is not a preference. It is dictated by which arguments the state functionally depends on.**

---

## 3. Conservation Laws That Force Location

### 3.1 Wallet-sum conservation ⇒ per-pair

Whenever a state field has a conservation law of the form

  `sum_w s(w, u) = const(u)`

the field **must** be stored per (w, u). This is the defining signature of a Noether current for S_W acting on that field. The futures `accumulated_cost` is exactly this: `sum_w accumulated_cost(w) = 0` per contract (v10.3 line 1149). This is not a stylistic choice — it is the only location compatible with the conservation law.

### 3.2 Unit-level immutables ⇒ per-unit

Fields like `multiplier`, `currency`, `maturity`, `last_settlement_price` are S_W-singlets: the clearinghouse fixes one value and every wallet sees the same one. Storing them per-pair would admit states where wallet A believes the multiplier is 100 and wallet B believes it is 1000 — an unrepresentable asymmetry, forbidden by S_W invariance. Per-unit is forced.

### 3.3 No conservation across wallets ⇒ per-wallet (not per-pair)

Managed-account fields like HWM, benchmark-value, mandate flags have **no** cross-wallet conservation. They are S_W-covariant but carry no sum-rule. These belong on the wallet alone, indexed by `w` — they are not even functions of `u`.

This is the piece the current doc does not name explicitly. The SBL 6-vector (`own, onloan, borr, coll_post, coll_recv, coll_rehyp`) already lives at `(w, u)` because each component satisfies its own conservation law per unit. Managed-account state lives at `(w)` because it satisfies none.

---

## 4. The Four Test Cases

### Case 1 — Future with `accumulated_cost`
- **S_W**: broken at the field level (each wallet has its own value), restored at the sum level (`sum_w = 0`).
- **S_U**: invariant (the field is defined per contract).
- **Forced location**: `(w, u)`. The conservation law `sum_w accumulated_cost(w, u) = 0` is a Noether current of S_W — identical in structure to the balance conservation `sum_w w(u) = 0`. Store it anywhere else and you lose the inner ground of the invariant.

### Case 2 — Managed account (benchmark, HWM, mandate flags)
- **S_W**: covariant (each wallet has its own HWM).
- **S_U**: **does not act** — these fields are not keyed by unit at all.
- **Forced location**: `(w)` alone. Attaching them to `(w, u)` would falsely introduce a unit dependence, breaking S_U invariance (relabelling units would have to leave HWM fixed, which a `(w,u)`-indexed field cannot guarantee without extra machinery). The current doc does not have a home for this; the framework needs a **wallet-state layer** distinct from unit state.

### Case 3 — QIS strategy trading futures
- Aggregator state (`current_weights`, `last_rebalance_date`, `triggered_barrier`) is S_W-invariant: the strategy definition is shared. → per-unit `s(u_QIS)`.
- Sub-position state (the futures' `accumulated_cost` inside the QIS wrapper) satisfies wallet-sum conservation. → per-pair `s(w, u_future)`.
- **Decomposition is unique**: the strategy factors into (contract-level) ⊗ (holder-level) state, exactly mirroring how a tensor decomposes into S_U-module and S_W-module parts. The current doc's hybrid handles this correctly **because** the two symmetry sectors are orthogonal.

### Case 4 — Listed-but-never-traded instrument
- Only per-unit fields exist (contract terms, lifecycle stage).
- **S_W acts trivially** — there is no wallet to relabel. `(w, u)` storage would be defined on an empty set of wallets; the pair table is vacuously consistent but carries no information.
- **Forced location**: per-unit. The Noetherian property matters here: the set of wallets holding `u` forms an ascending chain under trading events, and we need state to be well-defined at the empty bottom of the chain. Per-unit state gives the initial object; per-pair state only exists after the chain starts to grow.

---

## 5. Forced by Symmetry vs Arbitrary Choice

| Design decision | Status |
|---|---|
| `accumulated_cost` per `(w, u)` | **Forced** by wallet-sum conservation (Noether current of S_W). |
| `last_settlement_price` per `u` | **Forced** by S_W invariance (no per-wallet value could be consistent). |
| Bond coupon flags per `u` | **Forced** by S_W invariance. |
| QIS weights per `u`, sub-position per `(w, u)` | **Forced** by orthogonal decomposition of the two sectors. |
| Managed-account HWM | **Not yet placed**; forced to `(w)` — the current doc's two-level scheme cannot express it without introducing a fictitious unit. |
| "Most instruments per-unit, some per-pair" (line 1034) | **Not arbitrary**, but **incomplete**: the hybrid correctly reflects S_W covariance/invariance per field, but omits the wallet-only (w) sector and blurs the forcing principle. |

The current language reads as a pragmatic exception ("for instruments with per-wallet state ..."). The symmetry view reframes it: *every state field must declare which subgroup of `S_W x S_U` it transforms under, and the storage index set is determined by that declaration.* There is nothing hybrid about it — it is a single rule applied field by field.

---

## 6. Recommendation

**Adopt a three-sector state model indexed by the transformation type under `S_W x S_U`:**

1. **Per-unit `s(u)`** — for fields invariant under S_W (contract terms, settlement price, lifecycle stage).
2. **Per-pair `s(w, u)`** — for fields that are S_W-covariant with a cross-wallet conservation law (`accumulated_cost`, SBL 6-vector components, collateral allocations).
3. **Per-wallet `s(w)`** — for fields that are S_W-covariant with no unit index at all (HWM, benchmark, mandate flags, managed-account metadata).

**The rule to add to Section "Unit State as Explicit Object":**

> *Every state field declares its index set. The index set is the smallest one whose symmetry group acts faithfully on the field's value. Fields with a cross-wallet conservation law (Noether current of wallet relabelling) must be indexed per (w, u). Fields invariant under wallet relabelling must be per unit. Fields without a unit argument are per wallet.*

This replaces "per-unit for most, per-pair for some" with a principle that is symmetry-forced, decomposition-unique, and Noetherian (every field's index set is fixed and terminates at its correct sector — no ascending chain of "we'll extend this later").

Find the symmetry, and the location of state follows.
