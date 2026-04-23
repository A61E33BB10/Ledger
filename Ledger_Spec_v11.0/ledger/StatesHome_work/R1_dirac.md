# R1 — DIRAC: Where does unit state live?

*"A physical law must possess mathematical beauty."* — Dirac

## 1. The diagnosis: a notational accident

Line 1034 bifurcates: "per-unit for most instrument types... per (wallet, unit) pair" for futures. This one sentence forces two accessors, two typing schemes, two conservation proofs. The framework has already paid for elegance in the balance layer — $w_t : \mathcal{U} \to \mathbb{R}$ is uniform across cash, equity, OTC. Nobody writes "balance is per-unit except for futures." The balance layer does not bifurcate because the bifurcation is not real. The same unification must exist for state.

## 2. The candidate: state is a function on the product $\mathcal{W} \times \mathcal{U}$

Define

$$\sigma_t : \mathcal{W} \times \mathcal{U} \rightharpoonup \mathcal{S}_u$$

a partial function from (wallet, unit) pairs to the product-specific state type $\mathcal{S}_u$ bound to $u$ via its smart contract. This is the object. Every other formulation is a projection of it.

Why this? The balance layer already lives on $\mathcal{W} \times \mathcal{U}$: the ledger's fundamental datum is $w_t(u)$, a scalar per (wallet, unit) cell. State is the non-scalar generalisation — every cell carries a quantity *and* a state record. That the quantity is one-dimensional is accidental; state is the rest of the fibre.

## 3. Per-unit and per-wallet are two projections of the same object

Let $\Pi_u : \sigma_t(\cdot, u) \to \mathcal{S}_u$ and $\Pi_w : \sigma_t(w, \cdot) \to \prod_u \mathcal{S}_u$ be the two slices.

A state field $\phi$ is called **wallet-invariant at $u$** iff

$$\sigma_t(w, u).\phi = \sigma_t(w', u).\phi \quad \forall w, w' \in \mathcal{W}_u$$

where $\mathcal{W}_u = \{w : w_t(u) \neq 0\} \cup \{w_{\text{universe}}\}$ is the carrier of $u$. Wallet-invariant fields (bond `"coupon_2026-03-15": "paid"`, option `EXPIRED`, QIS `current_weights`) are the *degenerate case where the wallet-slice is constant*. Wallet-varying fields (`accumulated_cost`, HWM, mandate) are the generic case.

Storage exploits this: a wallet-invariant field is stored once at the universe wallet $w_\star$, and `state(w, u).φ` dereferences to `state(w_\star, u).φ`. The physics is $\mathcal{W} \times \mathcal{U}$; the representation compresses along invariant directions — exactly as zero wallet balances cost nothing to "store" without breaking the uniform signature of $w_t$. A bond's `"matured"` flag is wallet-invariant; futures' `accumulated_cost` is wallet-varying. Same object, two projections.

## 4. The four test cases, unified

| Case | State object | Carrier | Projection |
|---|---|---|---|
| 1. Futures accumulated_cost | $\sigma_t(w, u).\texttt{acc\_cost}$ | wallet-varying on $\mathcal{W}_u$ | full $\mathcal{W} \times \{u\}$ fibre |
| 2. Managed account (HWM, mandate) | $\sigma_t(w, u_\varnothing).\{\texttt{hwm}, \texttt{mandate}\}$ | wallet-varying on $\{w\}$ | degenerate *unit* axis: $u_\varnothing$ is the wallet's self-contract |
| 3. QIS strategy + sub-positions | $\sigma_t(w, u_{\text{QIS}}).\texttt{weights}$ (strategy-level) <br> $\sigma_t(w, u_{\text{fut}}).\texttt{acc\_cost}$ (sub-position) | each its own $\mathcal{W} \times \mathcal{U}$ cell | coexist by construction; no special glue |
| 4. Untraded unit in universe | $\sigma_t(w_\star, u).\phi$ only | wallet-invariant fields only | wallet axis trivially $\{w_\star\}$ |

Case 2 is the beautiful one: a managed-account wallet's HWM and mandate are state on $(w, u_\varnothing)$, where $u_\varnothing$ is the wallet's own managed-account-contract unit, registered in Tier 3 like any other unit. "Wallets are managed accounts" (Sec. 6.1) is already a structural identity; the state model inherits it.

Case 4 is free: before any trade, $\mathcal{W}_u = \{w_\star\}$. State at registration lives in the canonical cell; the first trade creates wallet-varying fibres lazily. Case 3 needed no special treatment: the product structure handles coexistence for free.

## 5. The unified signature

```
state : (Wallet, Unit) -> ProductState[Unit]          # total conceptually
get_state(view, w, u)    -> ProductState[Unit]        # accessor
set_state(tx, w, u, s')  -> tx'                       # update
```

**Reduction to today's doc:**

- *Per-unit case (bond, option, QIS):* fields carry `wallet_invariant=True`. Storage keeps one copy at $(w_\star, u)$; `get_state(w, u)` returns the same object for all $w$. This is today's `view.get_unit_state(unit)` verbatim — no call-site change.
- *Futures case:* `accumulated_cost` carries `wallet_varying=True`. One value per $(w, u)$. This is today's per-(wallet, unit) dictionary verbatim.

The invariant $\sum_w \sigma_t(w, u).\texttt{acc\_cost} = 0$ (line 1220) becomes a *field-level* property: any field with `conserved=True` carries a $\sum_w = 0$ obligation; wallet-invariant fields satisfy it trivially.

## 6. Beauty check (the DIRAC test)

1. *Inevitable structure?* Yes — state lives where balance lives: on $\mathcal{W} \times \mathcal{U}$.
2. *Minimal notation?* One accessor `state(w, u)` replaces two.
3. *Predict without solving?* Yes — invariance under the wallet slice predicts which fields compress, which must conserve, which can be written by whom.
4. *Unified opposites?* Per-unit and per-wallet are two projections of one fibre.
5. *Trust the formalism?* The "strange" prediction — a managed account's HWM is state on $(w, u_\varnothing)$ for a reflexive contract-unit — is not a hack; it is the structural identity (Sec. 6.1) made literal.
6. *Every symbol necessary?* $\sigma$, $\mathcal{W}$, $\mathcal{U}$ already exist. We added only the product.

## 7. Recommendation

**Delete the bifurcation. State is $\sigma_t : \mathcal{W} \times \mathcal{U} \rightharpoonup \mathcal{S}_u$. Per-unit state is the wallet-invariant special case, stored canonically at the universe wallet. Per-wallet state of a managed account is state on $(w, u_\varnothing)$ where $u_\varnothing$ is the wallet's own smart-contract unit.**

One object. Two projections. Zero special cases.
