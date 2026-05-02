# Deferred Settlement: A Noetherian Reading

**Author role:** NOETHER (Phase 1, Team A, independent)
**Question:** How should the Ledger represent the open settlement obligation between trade-time T and settlement-time T+2 on cash equities?
**Method:** Symmetry first. Identify the invariances, derive the conservation laws, prove the Ledger preserves them across the open window, and locate the broken symmetries that quantify operational risk.

---

## 0. The proper question, reframed

The Ledger v10.3 conservation law $\sum_w w(u) = 0$ governs a *closed* system, where every move has both a source and a destination wallet. Deferred settlement looks, at first glance, like an *open* obligation: between T and T+2 there is something owed, something not yet delivered, and the seller has surrendered economic exposure but not custody. The reflex is to model this as a half-edge — a one-sided promise — and to break closure.

That reflex is wrong. The conservation law does not need to be relaxed; it needs to be **lifted onto the right unit universe**. The seller's economic exposure ceases at T regardless of custody; therefore there must already be, at T, a counter-position somewhere that absorbs the exposure. The architectural question is: *what is that counter-position, and what symmetry does it respect?* Once the symmetry is identified, the unit, the wallet, and the move sequence write themselves.

> *"If one proves the equality of two numbers a and b by showing first that a ≤ b and then that a ≥ b, it is unfair; one should instead show that they are really equal by disclosing the inner ground for their equality."*

The inner ground is this: the trade is a transfer, never a creation. Every symmetry of the transfer must be respected at every intermediate state. We will not argue settlement-time and trade-time recognition are *eventually* consistent (a ≤ b and b ≤ a). We will exhibit the conserved current.

---

## 1. State representation

### 1.1 The fundamental tension

A cash-equity trade at T has two economic facts that the Ledger must hold simultaneously:

1. **Economic fact (immediate, T):** The seller no longer bears price risk on the security; the buyer bears it. Mark-to-market PnL accrues to the buyer from T onward.
2. **Custody fact (deferred, T+2):** Legal title and CSD-level positions transfer at T+2. Until then, the seller is the legal owner and the buyer is owed delivery.

The Ledger v10.3 spec confronts this with the `EXECUTED → INSTRUCTED → SETTLED/FAILED` status lifecycle (§13.7) and trade-date accounting (§13.5). What it lacks — and what this proposal supplies — is the **algebraic carrier** of the open obligation: an honest unit on which conservation is closed at every instant.

### 1.2 Two units, one trade

Introduce a derived unit at trade execution: the **deferred-delivery claim**

$$
u^{\,\text{def}}_{S,\,T+2} \in \mathcal{U}
$$

parameterised by the security $S$ and the contractual settlement date $T+2$. This unit is registered in the Unit Store (Tier 3) at trade time. It has:

- **ProductTerms** (immutable, per StatesHome addendum §2): underlying security $S$, settlement date $T+2$, settlement venue (CSD), DvP type, currency leg amount, counterparties.
- **UnitStatus** (mutable, shared): `lifecycle_stage ∈ {OPEN, INSTRUCTED, SETTLED, FAILED, PARTIAL, CANCELLED}`.
- **PositionState** $[w, u^{\,\text{def}}]$: per-(wallet, claim) state, monotone carrier.

Each position $u^{\,\text{def}}$ is held in equal and opposite quantity by buyer and seller during the open window. The cash leg is symmetric: a deferred cash claim $u^{\,\text{cash},\text{def}}_{T+2}$ in the trade currency.

### 1.3 The decomposition law (homomorphism)

Let $S$ denote the security and $C$ the cash currency. At settlement, the deferred claims **redeem** into the underlying units via the unique factoring:

$$
u^{\,\text{def}}_{S,\,T+2} \;\xrightarrow{\;\rho_S\;}\; S, \qquad u^{\,\text{cash},\text{def}}_{C,\,T+2} \;\xrightarrow{\;\rho_C\;}\; C
$$

These redemption maps $\rho$ are unit homomorphisms: they take a quantity $q$ of the deferred claim to the same quantity $q$ of the underlying. Crucially, $\rho$ preserves conservation per unit because it acts identically on both legs of the buyer/seller pair.

**This is the inner ground.** The deferred claim is not a new asset; it is the *right* to the asset, held during the gap. Settlement is the redemption of a right into the underlying. A trade is a transfer; a settlement is a coordinate change.

---

## 2. Move sequence with conservation at every state

### 2.1 The four phases

Let $w_B$ = buyer wallet, $w_S$ = seller wallet, $w_{\text{CSD}}$ = CSD virtual wallet (the boundary). Trade: 100 XYZ at \$50, T+2.

#### Phase T (trade-time recognition): the open window opens

A single atomic transaction $\tau_T$ of four moves issues the deferred claims and extinguishes the trade legs at the trade-time level:

```
tau_T = Transaction(type = ECONOMIC_RECOGNITION, t = T):

  # Securities deferred claim (issuance pair: seller is "issuer", buyer "holder")
  Move 1: w_seller_issuance → w_B,  unit = u_def_XYZ_T+2,  qty = +100
  Move 2: w_seller_issuance → w_S,  unit = u_def_XYZ_T+2,  qty = -100   # seller is short the claim

  # Cash deferred claim (issuance pair: buyer is "issuer", seller "holder")
  Move 3: w_buyer_issuance → w_S,   unit = u_def_USD_T+2,  qty = +5000
  Move 4: w_buyer_issuance → w_B,   unit = u_def_USD_T+2,  qty = -5000  # buyer is short the cash claim
```

In practice the implementation is two issuance pairs (per §1.2 of the StatesHome addendum's mandate-as-unit pattern: $w(u_{\text{MA}}) = +1$ on holder, $-1$ on issuer, $\sum_w = 0$). Conservation at T:

$$
\sum_w w_T(u^{\,\text{def}}_{S}) \;=\; +100 + (-100) \;=\; 0,\qquad
\sum_w w_T(u^{\,\text{def}}_{C}) \;=\; +5000 + (-5000) \;=\; 0.
$$

The seller's underlying $S$ position is **untouched** at T; the seller remains the legal owner. What the seller has done is take a short position in the deferred-delivery claim against itself — it has *promised* delivery. Symmetric for buyer/cash.

This is the key move: the deferred claim is the carrier of the open obligation, and it is conserved at every instant of the open window. The Ledger never holds an unbalanced position.

#### Phase T+1 (the open window persists): no moves

No state transitions on the deferred claim. UnitStatus may transition `OPEN → INSTRUCTED` once the settlement layer (per §13.1 settle_projection) generates the ISO 20022 instruction, but this is a UnitStatus update with zero PositionState delta, hence vacuously conserves (StatesHome C9: handlers on zero-quantity-change events discharge $\sum_w \Delta = 0$ vacuously).

Mark-to-market between T and T+2 attaches to the underlying security $S$ via the price function $P_t(S)$, *not* to the deferred claim. The buyer's portfolio value $V_t$ rises with $P_t(S)$ because the buyer holds $+100$ of $u^{\,\text{def}}_S$, and the redemption homomorphism $\rho_S$ guarantees $P_t(u^{\,\text{def}}_S) = P_t(S)$ during the open window. (See Invariant N3 below.)

#### Phase T+2⁻ (just before settlement): redemption-equivalence holds

Just before the CSD movement, the deferred claims are still open. The Ledger view is identical to T+1 except for the price vector. Conservation per claim still holds; redemption-equivalence (N3) still holds.

#### Phase T+2⁺ (atomic redemption): the open window closes

A single atomic transaction $\tau_{T+2}$ of eight moves redeems both deferred claims into their underlying assets:

```
tau_T+2 = Transaction(type = SETTLEMENT, t = T+2):

  # Securities leg: redeem deferred claim into S
  Move 1: w_S → w_seller_issuance, unit = u_def_XYZ_T+2, qty = -(-100) = +100  # extinguish seller short
  Move 2: w_B → w_seller_issuance, unit = u_def_XYZ_T+2, qty = -100             # extinguish buyer long
  Move 3: w_S → w_CSD,             unit = XYZ,           qty = +100             # custody movement out
  Move 4: w_CSD → w_B,             unit = XYZ,           qty = +100             # custody movement in

  # Cash leg: redeem deferred claim into USD
  Move 5: w_B → w_buyer_issuance,  unit = u_def_USD_T+2, qty = -(-5000) = +5000
  Move 6: w_S → w_buyer_issuance,  unit = u_def_USD_T+2, qty = -5000
  Move 7: w_B → w_CSD,             unit = USD,           qty = +5000
  Move 8: w_CSD → w_S,             unit = USD,           qty = +5000
```

Conservation at T+2:
- $\Delta Q(u^{\,\text{def}}_S) = +100 - 100 = 0$ (claims extinguished, but conservation held throughout life).
- $\Delta Q(\text{XYZ}) = +100 - 100 = 0$ via the CSD virtual wallet.
- Symmetric for cash.

After $\tau_{T+2}$ commits, the deferred claims have zero balance everywhere; the underlying $S$ and $C$ positions reflect custody. By the StatesHome monotone carrier discipline, the PositionState rows for $u^{\,\text{def}}$ remain (with zero balance) for audit and time travel — they do not vanish, because Phase 6 (Time Travel) requires that the open-window state be reconstructible.

### 2.2 Atomicity guarantee at T+2

The eight moves of $\tau_{T+2}$ are a single atomic transaction. Either all eight commit or none. This is the **Ledger-level DvP guarantee** (§13.4): structural, not a runtime check. Settlement-level DvP at the CSD is an independent guarantee from the external infrastructure; the two reinforce each other but are independently sufficient.

---

## 3. Invariants — the symmetry-first reading

This is the centre of the proposal. **Mandatory: economic-exposure-at-T conservation.**

### 3.1 The symmetries

| # | Symmetry | Group action | Conserved current |
|---|----------|--------------|-------------------|
| **N1** | **Time-translation invariance of the open window** | $t \mapsto t + \Delta t$ for $t \in [T, T+2)$ | Open obligation quantity $Q(u^{\,\text{def}}_S) = 0$ at every $t$ |
| **N2** | **Trade-as-transfer invariance** (relabelling buyer↔seller) | $\sigma : \{B, S\} \to \{S, B\}$ on the deferred-claim issuance | Net economic exposure (sum of buyer + seller exposure) is zero |
| **N3** | **Redemption-equivalence (gauge invariance)** | $u^{\,\text{def}}_S \leftrightarrow S$ on price | Total portfolio value is invariant under whether the position is held as deferred claim or as redeemed underlying |
| **N4** | **Permutation invariance of independent trades** | $\pi$ on $\{\tau_1, \ldots, \tau_n\}$ same security, same settlement date, same counterparty | Net deferred-claim balance per (counterparty, security, date) — i.e., the netting algebraic identity (§13.6) |
| **N5** | **Cancellation symmetry** (composition algebra) | $\tau \circ \tau^{-1} \to \emptyset$ | Zero net deferred claim from offsetting trades |
| **N6** | **Currency-leg / security-leg symmetry** under DvP | swap $(S, C)$ legs | DvP atomicity: both legs settle or neither does |

### 3.2 Invariant N1 — Open-window conservation (MANDATORY)

> **For every $t \in [T, T+2]$ and for every deferred-delivery unit $u^{\,\text{def}}$:** $\sum_w w_t(u^{\,\text{def}}) = 0$.

**Symmetry source:** time-translation invariance during the open window. The open obligation does not "drift" in either direction as time advances inside the window; nothing changes its total quantity except the `OPEN → SETTLED` (or → FAILED) transition at $t = T+2$.

**Why it matters:** Without this invariant, the open obligation is an unaccounted half-edge. With it, the Ledger's closure property is preserved across the gap.

### 3.3 Invariant N2 — Economic-exposure conservation at T (MANDATORY)

> **For every trade transaction $\tau_T$ on security $S$ at price $p$ with quantity $q$:**
>
> $$\Delta\, \text{Exposure}_B(S) + \Delta\, \text{Exposure}_S(S) \;=\; 0 \quad \text{at } t = T,$$
>
> where $\text{Exposure}_w(S) = w(S) + w(u^{\,\text{def}}_S)$ is the buyer/seller's total economic exposure to $S$ across native holdings and deferred claims.

**Symmetry source:** the trade is a transfer, not a creation. The relabelling $\sigma : B \leftrightarrow S$ exchanges sign on every deferred claim and every cash leg. Under this Z/2 action, the trade is invariant up to relabelling — both parties' positions transform contravariantly. By Noether's theorem applied to discrete symmetries (Burnside-style averaging), there is a conserved bilinear form on $(B, S)$ exposure space: their sum.

**Worked check:** at T, seller's $S$ position is unchanged ($+0$) but seller is short the claim ($-100$ of $u^{\,\text{def}}_S$). So $\Delta \text{Exposure}_S(S) = 0 + (-100) = -100$ in claim-units, equivalent to $-100$ shares of price exposure. Buyer: $+0$ in $S$, $+100$ in $u^{\,\text{def}}_S$, so $\Delta \text{Exposure}_B(S) = +100$. Sum: $+100 - 100 = 0$. **Conserved.**

This is the precise expression of "the seller's exposure ceases at T regardless of custody". The seller's $S$ holding has not changed; what has changed is that the seller has issued a short position in the deferred claim, which acts as a price-equivalent debit on its exposure book. Mark-to-market PnL between T and T+2 hits the seller via the *negative* deferred claim, the buyer via the *positive* deferred claim. **The MTM moves through the claim, not the underlying, and it does so symmetrically.**

### 3.4 Invariant N3 — Redemption-equivalence

> **For every $t \in [T, T+2)$ and every deferred unit $u^{\,\text{def}}_S$:**
> $P_t(u^{\,\text{def}}_S) = P_t(S)$ in the trade currency.

**Symmetry source:** gauge invariance under the choice of representation (claim vs underlying). The portfolio value $V_t$ must not depend on whether the buyer holds 100 shares directly or 100 deferred claims redeeming 1-for-1. If $P_t(u^{\,\text{def}}_S) \neq P_t(S)$, an arbitrageur could transform between the two and extract value from the gauge change — violating no-arbitrage and the path-independence of PnL.

**Coupling to the valuation layer (Theorem 5):** the no-arbitrage pricing lifting in `ledger_data_v1.0.tex` §6.5 already requires that `arbitrage_certificate` witness the admissibility of model outputs. The deferred-claim unit must register $\rho_S$ as a *deterministic* redemption map; pricing against $u^{\,\text{def}}_S$ is then $P_t(S)$ by composition.

**Subtlety — funding cost.** Strictly, $P_t(u^{\,\text{def}}_S)$ should be $P_t(S)$ discounted by the residual funding cost over $[t, T+2]$ if the cash leg sits in an interest-bearing wallet. For a 2-day window at modern rates this is a 4–8 bp adjustment on a 1-week claim and negligibly small on a 2-day claim; in practice the framework can either (i) treat it as zero and accept a bp-level PnL noise, or (ii) introduce an explicit funding accrual on the cash deferred claim. Option (ii) preserves the symmetry exactly; option (i) accepts a small symmetry-breaking term we call $\varepsilon_{\text{funding}}$ and quantify it in §5.

### 3.5 Invariant N4 — Netting as permutation-invariance

> **For trades $\tau_1, \ldots, \tau_n$ in the same security, same settlement date, same counterparty:** the algebraic sum of deferred-claim quantities is invariant under permutation $\pi$ of the trades, and equals the net settlement instruction quantity.

**Symmetry source:** the permutation group $S_n$ acts trivially on the sum of independent trades. By Noether (commutative version), the sum is conserved under $S_n$.

**Already in the spec:** §13.6 defines the netting identity. The Noetherian content adds: this identity is *forced* by permutation symmetry, not chosen by convention. Any settlement-layer netting algorithm that violates it is, by Noether, violating a symmetry the trades themselves possess.

### 3.6 Invariant N5 — Composition algebra (cancellation homomorphism)

> **The map $F: (\text{Trades, composition}) \to (\text{Deferred Claims, addition})$ is a group homomorphism.**
>
> Specifically: if $\tau_1$ is a buy of $q$ shares and $\tau_2$ is a sell of $q$ shares, both for $T+2$, then $F(\tau_1) + F(\tau_2) = 0$ in the deferred-claim group, i.e., the buyer's net deferred-claim position is zero before settlement.

**Symmetry source:** trades form a free abelian group under composition; deferred claims form an abelian group under addition. The map is structure-preserving: the cancellation of two opposing trades produces zero net obligation in the open window, *before* any compression or cancellation messaging at the CSD.

**Worked check:** Buy 100 XYZ at \$50 (T+2), then sell 100 XYZ at \$52 (same T+2). After two `ECONOMIC_RECOGNITION` transactions:
- Securities deferred claim: $+100 + (-100) = 0$ at the buyer wallet ✓
- Cash deferred claim: $-5000 + 5200 = +200$ at the buyer wallet — this is the realised PnL, which **is not symmetric to zero**, and it should not be: PnL is real, not a phantom of double-counting.

**This is the deep content:** the *security* leg cancels (zero net delivery owed), but the *cash* legs do not cancel — they net to the realised PnL. The Ledger correctly carries this as a deferred cash claim of \$200 owed to the buyer, settling on T+2. The cash settlement is real even when the security settlement nets to zero. Both legs net independently because they are independent units; the asymmetry is the PnL, exactly. **No cash has moved, but \$200 of PnL has been recognised** — this is the worked-example invariant of §6 below.

### 3.7 Invariant N6 — DvP atomicity at redemption

> **The transaction $\tau_{T+2}$ that redeems both deferred claims is atomic: either all eight moves commit or none.**

**Symmetry source:** the security and cash legs are dual under the DvP symmetry. If only one leg redeems, conservation breaks: the buyer would hold $S$ but still hold $u^{\,\text{def}}_C$ (cash claim still open), or vice versa. Ledger-level DvP is the structural guarantee that prevents this asymmetry.

**Already in the spec:** §13.4 ("Ledger-level DvP"). The Noetherian content: this is not "atomicity as a feature" but "atomicity as the only configuration in which the open-window symmetries close consistently".

### 3.8 The full conservation table at every state

| State | $Q(S)$ | $Q(C)$ | $Q(u^{\,\text{def}}_S)$ | $Q(u^{\,\text{def}}_C)$ | Notes |
|-------|--------|--------|--------------------------|--------------------------|-------|
| Pre-T | 0 | 0 | n/a | n/a | Claim units not yet registered |
| T | 0 | 0 | 0 | 0 | Issuance pair: claims sum to zero |
| T+1 | 0 | 0 | 0 | 0 | UnitStatus update (`INSTRUCTED`); no PositionState delta |
| T+2⁻ | 0 | 0 | 0 | 0 | Identical to T+1 modulo price |
| T+2⁺ | 0 | 0 | 0 | 0 | Claims redeemed; underlyings transferred via CSD virtual wallet |

**Theorem (Open-Window Conservation Lifting).** *Conservation per unit (P1) holds at every state of the open window, for every unit (native or deferred), provided the deferred-claim issuance and redemption are committed via paired moves (§2.1) under E-ATOM.*

**Proof.** By induction on the move stream, identical in structure to the Conservation Lifting theorem of `ledger_data_v1.0.tex` §6.1. Issuance handlers (Phase T) emit a matched pair $(+q, -q)$ on the deferred claim. UnitStatus updates (Phase T+1) emit no PositionState delta. Redemption (Phase T+2) emits four paired moves: $(+q, -q)$ extinguishing the deferred claim and $(+q, -q)$ across the CSD virtual wallet for the underlying. Each step preserves $\sum_w = 0$. By induction, the property holds for the entire move stream. ∎

---

## 4. Reconciliation lead-lag

### 4.1 The two clocks

The Ledger has two natural clocks:

1. **Trade-time clock** $t_{\text{trade}}$: ticks at execution (T). This is the clock under which Invariant N2 (economic-exposure conservation at T) holds.
2. **Settlement-time clock** $t_{\text{sett}}$: ticks at CSD confirmation (T+2 nominal, but actually the timestamp of the `sese.025` confirmation message). This is the clock under which the underlying $S$ moves through the CSD virtual wallet.

The lead-lag $\Delta_{\text{lag}} = t_{\text{sett}} - t_{\text{trade}}$ is exactly the open window. Reconciliation must respect both clocks:

| Reconciliation surface | Clock | What is reconciled |
|------------------------|-------|---------------------|
| Internal: front-office vs accounting | $t_{\text{trade}}$ | Position in $u^{\,\text{def}}_S$ — same record (single-source) |
| External: ledger vs CSD | $t_{\text{sett}}$ | Position in $S$ at CSD vs $w_{\text{CSD}}$ virtual wallet |
| External: ledger vs counterparty | both | Open deferred claims (T+1) + settled positions (T+2) |

### 4.2 Reconciliation as a homomorphism

Define the reconciliation projection $\Pi$:

$$
\Pi : (\text{Ledger state at } t) \to (\text{External record at } t)
$$

For internal reconciliation (within scope of §1.10), $\Pi$ is the identity on the position set of $u^{\,\text{def}}_S$ and $S$ — no second source of truth exists, so reconciliation collapses to a tautology. **The lead-lag is not a reconciliation problem internally.**

For external reconciliation, $\Pi$ must be a homomorphism with respect to settlement state:

- At T to T+2⁻: external record (CSD) shows $S$ unchanged at the seller. Ledger virtual wallet for CSD shows the same. ✓
- At T+2⁺: external record shows $S$ moved. Ledger CSD virtual wallet shows the same. ✓

If $\Pi(\text{Ledger}) \neq \text{External}$ at any $t$, the discrepancy is **localised in time** (inside the open window) and **localised in scope** (to the $w_{\text{CSD}}$ virtual wallet for security $S$, counterparty $C$, settlement date $T+2$). The Ledger's design makes this discrepancy structurally narrow.

### 4.3 Failure-induced lead-lag amplification

When settlement fails, $t_{\text{sett}}$ is undefined or shifts to $t_{\text{sett}} + \delta$. The deferred claim does *not* extinguish at T+2; it persists past the contractual settlement date. The UnitStatus transitions `INSTRUCTED → FAILED`, but the PositionState rows on $u^{\,\text{def}}_S$ remain non-zero. **This is correct:** the obligation has not been discharged. Conservation still holds on $u^{\,\text{def}}_S$ throughout the failure period.

The CSDR mandatory buy-in (§13.7) is a compensation handler $\kappa$ in the obligation framework (§10.4 of v10.3). It either:
- discharges the claim by sourcing the security via buy-in (back to N1-conserving redemption), or
- compensates via cash payment (which is a relabelling of the security claim into a cash claim — *another homomorphism*: $\rho^{\text{buy-in}}: u^{\,\text{def}}_S \to u^{\,\text{def}}_C$ at cash-equivalent value).

Both outcomes preserve conservation on the deferred-claim unit. The buy-in cost is a real PnL impact carried through the cash leg.

---

## 5. Failure modes — the broken symmetries

Where symmetry breaks, operational risk lives. This is the most important Noetherian principle: **the cost of broken symmetry is exactly quantifiable.**

### 5.1 Settlement fail — broken time-translation symmetry (CSDR)

| | Symmetric (clean settlement) | Asymmetric (fail) |
|---|---|---|
| At $T+2^+$ | Claim redeems; $S$ flows | Claim persists; $S$ does not flow |
| Conserved? | Yes (all six symmetries) | N1, N2 still hold; N6 (DvP atomicity at the *contractual* date) is broken |
| Cost | None | CSDR penalty: 0.5 bps/day on equities; mandatory buy-in after T+4 |
| Compensation $\kappa$ | n/a | Buy-in (homomorphism $\rho^{\text{buy-in}}$) or cash compensation |

**Quantification:** the cost of broken N6 is exactly the CSDR penalty rate × claim notional × $\delta$ days. The Ledger captures this as an additional move on the cash deferred claim, charged from the failing party's wallet to the receiving party's wallet, accruing daily until discharge.

### 5.2 Partial settlement — broken atomicity, preserved closure

If only $q' < q$ shares deliver:

```
tau_T+2_partial:
  Move 1: w_S → w_seller_iss, u_def_XYZ, qty = +q'   # extinguish q' of seller's short
  Move 2: w_B → w_seller_iss, u_def_XYZ, qty = -q'   # extinguish q' of buyer's long
  Move 3: w_S → w_CSD,        XYZ,       qty = +q'
  Move 4: w_CSD → w_B,        XYZ,       qty = +q'
  ...similarly for cash, scaled to q' * p...
```

The remaining $q - q'$ stays open as $u^{\,\text{def}}$. **N6 (DvP atomicity at total) is broken; N6' (DvP atomicity at $q'$) holds, plus the residual claim is still N1-conserved.** This is the essential algebraic content of partial settlement: the deferred-claim group's quotient by the partial decomposes cleanly because of N4 (permutation invariance of independent quantity slices).

### 5.3 Recall (in SBL context) — broken composition order

A recall on a loaned security creates a return-by deadline that disrupts the seller's ability to deliver if the seller is short via SBL. The recall is itself a deferred obligation (§10.4: SBL recall return has type `SBL_RECALL_RETURN` with deadline $T_{\text{recall}}$).

**Symmetry broken:** the composition $\tau_{\text{loan}} \circ \tau_{\text{recall}}$ does not commute with $\tau_{\text{trade}}$ in general; the seller's $w(S)[\text{onloan}]$ may be insufficient to cover both. The cost is the buy-in to repurchase recalled shares at potentially adverse prices.

**Quantification:** $\text{cost} = (\text{buy-in price} - \text{loan price}) \times q$, plus operational fees. This is recorded as PnL on the cash deferred claim.

### 5.4 Cross-currency / Herstatt — broken time-translation across time zones

The deepest case. Two currency legs settle in different time zones with no PvP guarantee. Define two deferred cash claims:

$$
u^{\,\text{def}}_{\text{USD},\,T+2}, \qquad u^{\,\text{def}}_{\text{EUR},\,T+2}
$$

The trade is again two issuance pairs. Conservation per claim holds.

**Symmetry broken:** N6 (DvP/PvP atomicity) is broken across currencies. CLS (Continuous Linked Settlement) restores it for a subset of currencies; outside CLS, the atomic redemption $\tau_{T+2}$ becomes two non-atomic redemptions $\tau^{\text{USD}}_{T+2}$ and $\tau^{\text{EUR}}_{T+2}$, separated by hours.

**The Herstatt-risk window** is the time between the first leg redeeming and the second leg redeeming. During this window:
- N1 (open-window conservation) holds for *each* claim independently.
- N6 (cross-currency atomicity) is broken: a Herstatt-style counterparty default during the window leaves one leg redeemed and the other a defaulted claim.

**Quantification:** the Herstatt loss is the full notional of the unredeemed leg, mitigated by netting with the redeemed leg into a single counterparty claim. The Ledger captures this exactly: at default, the unredeemed claim becomes a defaulted obligation routed into close-out netting (compensation $\kappa = $ ISDA close-out for OTC, or claims process for spot FX).

**Architectural observation:** Herstatt risk *cannot* be eliminated by Ledger design (§2.7 of v10.3 already states this). What the deferred-claim model does is make the risk **explicit, conserved, and locally quantifiable** — the Herstatt exposure at any instant equals the sum of unredeemed deferred-claim notionals against the defaulting counterparty. This is a property the Ledger gives for free that legacy multi-source designs do not.

### 5.5 The cost-of-broken-symmetry table

| Broken symmetry | Operational manifestation | Cost (per unit notional) | Compensation $\kappa$ |
|-----------------|---------------------------|---------------------------|------------------------|
| N6 at $T+2$ (fail) | CSDR settlement fail | $0.5$ bps/day + buy-in slippage | Buy-in (§5.1) |
| N6 partial | Partial settlement | None directly; residual remains | Re-instruct residual |
| N5 cancellation | Bilateral cancel after T | Cancellation fee | `CORRECTION` transaction |
| N2 at T | Trade booking error | PnL discrepancy until reconciled | Manual correction |
| N6 cross-currency | Herstatt | Up to full notional | Close-out netting |
| N3 (price) | Stale or wrong $P_t(u^{\,\text{def}}_S)$ | PnL noise (FVA-like) | $\varepsilon_{\text{funding}}$ adjustment |

Every operational risk in deferred settlement maps to exactly one broken symmetry. **This is the gift of the Noetherian framing: it makes the operational risk taxonomy a corollary of the algebraic structure, not an empirical catalogue.**

---

## 6. CDM cross-walk

### 6.1 What CDM provides

CDM's `BusinessEvent` model already separates the trade event from the settlement event:

- `EventIntentEnum.OPEN` (or `EXECUTION`) — corresponds to the `ECONOMIC_RECOGNITION` transaction at T.
- `EventIntentEnum.TRANSFER` — corresponds to settlement-layer movements between $T$ and $T+2$.
- `Transfer` primitive (asset, payerReceiver, quantity) — natively atomic per the §9.4 mapping $F$.

CDM does *not* provide a native "deferred delivery claim" type. The existing `Transfer` primitive carries `settlementDate` as a future date, but the "open obligation" between trade and settlement is implicit in CDM, not modelled as a first-class object.

### 6.2 Mapping to the deferred-claim unit

| Ledger concept | CDM equivalent | Adapter needed? |
|----------------|----------------|------------------|
| $u^{\,\text{def}}_{S, T+2}$ ProductTerms | `Trade.product` + `settlementTerms.settlementDate` | None — derived from CDM `Trade` |
| $u^{\,\text{def}}_{S, T+2}$ UnitStatus | `BusinessEvent` chain: `OPEN` → `INSTRUCTED` (via `sese.023`) → `SETTLED` (via `sese.025`) | None — direct mapping |
| Issuance pair at T | `BusinessEvent.primitive.transfer` with `settlementDate = T+2` | The forgetful mapping $F$ extracts the move pair from the `Transfer` primitive |
| Redemption at T+2 | `BusinessEvent.primitive.transfer` triggered by settlement confirmation | Standard $F$ mapping |
| Failure at T+2 | `BusinessEvent` with `EventIntentEnum` not currently defined; closest is `CORRECTION` for cancellation | **CDM gap** — propose `EventIntentEnum.SETTLEMENT_FAIL` |
| Buy-in at T+4 | No direct CDM enum | **CDM gap** — propose `EventIntentEnum.BUY_IN` |

### 6.3 The forgetful mapping $F$ remains a homomorphism

Critically, the deferred-claim model **does not require modifying $F$**. It only requires that the Ledger's Unit Store register the deferred-claim unit at trade time, with `unit_id` derived deterministically from the CDM `Trade` and `settlementDate`. The mapping $F: \mathbf{CDM} \to \mathbf{Ledg}$ remains a forgetful homomorphism preserving conservation, sequencing, and idempotency.

### 6.4 ISO 20022 flow

The CDM-to-ISO 20022 synonym layer connects:
- $\tau_T$ (issuance) → `seev.031` allegement (or the trade confirmation `MT515` / `seev.031` depending on flow)
- UnitStatus `INSTRUCTED` → `sese.023` settlement instruction (one per leg: securities + cash)
- UnitStatus `SETTLED` → `sese.025` (securities) and `camt.054` (cash)
- UnitStatus `FAILED` → `sese.024`/`sese.027` (status advice)

The settlement layer's `settle_projection` (§13.1) maps the redemption transaction $\tau_{T+2}$ to the appropriate ISO instruction. **No change to settle_projection is required**: it already classifies moves by unit type and produces DvP/FOP/CASH correctly. The deferred-claim moves at T do not require ISO instructions (they are economic recognition, not settlement); only the redemption at T+2 does.

---

## 7. Worked example (mandatory): 100 XYZ at \$50 → \$52, PnL = +\$200, no cash moved

Setup: at $t = T$, the buyer's portfolio is empty; price $P_T(\text{XYZ}) = 50$. At $t = T+1$, $P_{T+1}(\text{XYZ}) = 52$.

The buyer executes a buy of 100 XYZ at \$50 with settlement T+2.

### 7.1 State at $t = T$ (post-trade)

PositionState rows:
- $w_B(u^{\,\text{def}}_{\text{XYZ},T+2}) = +100$
- $w_B(u^{\,\text{def}}_{\text{USD},T+2}) = -5000$ (buyer is short the cash claim — owes \$5000)
- $w_B(\text{XYZ}) = 0$ (no underlying yet)
- $w_B(\text{USD}) = 0$ (no cash moved yet)

Portfolio value:
$$
V_T = 100 \cdot P_T(u^{\,\text{def}}_{\text{XYZ}}) + (-5000) \cdot P_T(u^{\,\text{def}}_{\text{USD}}) = 100 \cdot 50 + (-5000) \cdot 1 = 5000 - 5000 = 0.
$$

The buyer's wealth is unchanged at trade-time: it has converted \$5000 of (anticipated) cash into a \$5000 claim on shares. Symmetric on the seller side.

### 7.2 State at $t = T+1$ (price has moved)

PositionState unchanged. Price changes:
$$
P_{T+1}(u^{\,\text{def}}_{\text{XYZ}}) = P_{T+1}(\text{XYZ}) = 52 \quad \text{(by N3, redemption-equivalence)}.
$$

Portfolio value:
$$
V_{T+1} = 100 \cdot 52 + (-5000) \cdot 1 = 5200 - 5000 = +200.
$$

**PnL = $V_{T+1} - V_T = 200 - 0 = +\$200$.** ✓

**No cash has moved.** No security has moved. The buyer has $+\$200$ of recognised PnL purely through the price movement of the deferred claim — exactly because N3 (redemption-equivalence) makes the deferred claim track the underlying.

### 7.3 Conservation check at every state

| State | $\sum_w w(\text{XYZ})$ | $\sum_w w(\text{USD})$ | $\sum_w w(u^{\,\text{def}}_{\text{XYZ}})$ | $\sum_w w(u^{\,\text{def}}_{\text{USD}})$ |
|-------|---|---|---|---|
| Pre-T | 0 | 0 | n/a | n/a |
| T | 0 | 0 | $+100 + (-100) = 0$ | $-5000 + 5000 = 0$ |
| T+1 | 0 | 0 | 0 | 0 |
| T+2⁺ | $+100 + (-100) = 0$ via CSD | $-5000 + 5000 = 0$ via CSD | 0 (extinguished) | 0 (extinguished) |

**All seven invariants (N1–N6 plus the global P1 conservation) hold at every state.** ✓

### 7.4 The seller side at T+1

At $t = T$, seller had $w_S(\text{XYZ}) = +100$, $w_S(u^{\,\text{def}}_{\text{XYZ}}) = -100$, $w_S(u^{\,\text{def}}_{\text{USD}}) = +5000$. At $t = T+1$ ($P = 52$):

$$
V^S_{T+1} - V^S_T = (100 \cdot 52 + (-100) \cdot 52 + 5000) - (100 \cdot 50 + (-100) \cdot 50 + 5000) = 0 - 0 = 0.
$$

Wait — the seller's PnL is zero?

**Yes, exactly.** The seller still holds the XYZ legally (it transfers at T+2), but it is *short* the deferred claim. The price gain on the held XYZ is exactly cancelled by the price loss on the short deferred claim. **The seller has economically transferred the asset at T**, and N2 (economic-exposure conservation at T) demands precisely this: the seller bears no further price risk after T, regardless of custody.

This is the cleanest possible illustration of why the deferred-claim unit is the right algebraic carrier: it makes the seller's economic indifference to price between T and T+2 a *theorem*, not a convention.

### 7.5 Buyer + seller PnL at T+1

$$
\Delta V^B + \Delta V^S = +200 + 0 = +200.
$$

**Where does the +\$200 come from?** From the underlying XYZ price appreciation: the asset gained \$200 in market value. The Ledger correctly attributes the entire gain to the buyer (who has economic exposure) and zero to the seller (who has transferred exposure). Sum to system PnL = +\$200, equal to $\Delta P \times Q$ on the underlying. Closure on PnL: ✓.

---

## 8. Drift in the existing spec — where the symmetry is at risk

### 8.1 The drift

Section 13 of v10.3 currently states:

> "Between trade date and settlement date, the Ledger shows the correct economic position (trade-date accounting per §1)..."

But it does not specify *the algebraic carrier of that economic position*. The section relies on the implicit understanding that "the buyer's $w(\text{XYZ})$ is incremented at T and the seller's at T". This implicit understanding **breaks Invariant N2 in worked detail**:

- If $w_B(\text{XYZ}) = +100$ at T (buyer's underlying balance increments at T), then at T+2 the move from $w_{\text{CSD}}$ to $w_B$ would *double-count* the position. The spec avoids this by not specifying the move sequence between T and T+2.
- If $w_B(\text{XYZ}) = 0$ at T (buyer's underlying balance increments only at T+2), then at T+1 the buyer's portfolio value $V_{T+1}$ reflects a zero XYZ position — and the Ledger does not capture the +\$200 economic PnL through a wallet move. The spec then has to define PnL via "trade-date accounting" as a separate principle, with a separate accounting for the open obligation.

Either choice violates one of the symmetries. **The deferred-claim unit resolves the dilemma** by providing the explicit carrier of the open obligation, with conservation closed at every state.

### 8.2 Specific drift in the obligation framework

The §10.4 obligation taxonomy lists:

> Settlement instruction & Unit & Settlement-type transaction & Failed settlement

This treats settlement as a single obligation per transaction. With the deferred-claim model, settlement decomposes into **two** obligations per trade leg (security delivery and cash payment), each with its own discharge predicate. Under DvP, both are discharged simultaneously by the redemption transaction $\tau_{T+2}$; under FOP or PvP failure, they discharge independently. The taxonomy should be updated:

| Obligation type | Scope | Trigger | Compensation $\kappa$ |
|-----------------|-------|---------|----------------------|
| Securities delivery | Unit ($u^{\,\text{def}}_S$) | At trade T | Buy-in (CSDR) |
| Cash payment | Unit ($u^{\,\text{def}}_C$) | At trade T | Cash penalty / counterparty close-out |
| DvP atomicity at T+2 | Trade (paired) | At T+2 | One-leg-only fail handling |

This is the symmetry that closes the drift: pair every trade with two obligations, dual under N6, redeemed together by $\tau_{T+2}$.

### 8.3 The fix in StatesHome terms

Per the StatesHome 3-map ruling, the deferred-claim unit slots in cleanly:

- **ProductTerms[$u^{\,\text{def}}_{S,T+2}$]**: immutable; underlying $S$, settlement date $T+2$, settlement venue, currency, DvP type, counterparties. Set at trade time. (C7: registration-total.)
- **UnitStatus[$u^{\,\text{def}}_{S,T+2}$]**: mutable, shared; `lifecycle_stage ∈ {OPEN, INSTRUCTED, SETTLED, FAILED, PARTIAL}`. Updated by the settlement orchestration workflow. (C5: registration-total with default `OPEN`.)
- **PositionState[$w$, $u^{\,\text{def}}_{S,T+2}$]**: per-(holder, claim); `quantity` field, plus `accrued_funding` if N3 funding adjustment is enabled. Monotone carrier; rows persist after redemption. (C1, C11.)

The handler-level conservation discipline (C2) requires that every event class on $u^{\,\text{def}}$ structurally zero-sums. The four event classes are:

1. **Issuance** (at T): the $(+q, -q)$ pair. Per StatesHome §3.2, this is the issuance discipline, and conservation is preserved by the standard issuance law. ✓
2. **InstructionAdvance** (at T to T+2): UnitStatus update, no PositionState delta. Vacuously zero-sum (C9). ✓
3. **Redemption** (at T+2): the $(-q, +q)$ pair on $u^{\,\text{def}}$ plus the $(+q, -q)$ pair on $S$ via $w_{\text{CSD}}$. Two paired events; each zero-sums. ✓
4. **Compensation** (at T+2 + δ on fail): buy-in or cash equivalent; the homomorphism $\rho^{\text{buy-in}}$ ensures the deferred claim extinguishes against an equivalent cash entry, preserving conservation on both units. ✓

All four event classes pass the C2 structural zero-sum test by construction.

---

## 9. Proposed Invariant additions (P24–P27)

To extend the v10.3 invariant catalogue (P1–P10 core, P11–P20 SBL, P21–P23 obligation):

- **P24 (Open-Window Conservation):** For every deferred-delivery unit $u^{\,\text{def}}$ and every $t \in [T, T+2]$, $\sum_w w_t(u^{\,\text{def}}) = 0$. *(N1)*
- **P25 (Economic-Exposure Conservation at T):** For every trade $\tau_T$ on security $S$, $\sum_{w \in \{B, S\}} \Delta\text{Exposure}_w(S) = 0$ at $t = T$. *(N2)*
- **P26 (Redemption-Equivalence):** For every $t \in [T, T+2)$, $P_t(u^{\,\text{def}}_S) = P_t(S)$ up to the funding-adjustment $\varepsilon_{\text{funding}}$. *(N3)*
- **P27 (DvP Atomic Redemption):** The redemption transaction $\tau_{T+2}$ is atomic across the security and cash legs; partial atomicity reduces to P27 on the redeemed slice plus open-window conservation on the residual. *(N6)*

These four extend the existing invariant chain. Each is testable by the existing property-based testing framework with generators drawn from CDM `Trade` × `settlementDate` × price path.

---

## 10. Summary — what the symmetry-first reading gives

1. **The open obligation is not a half-edge.** It is a deferred-claim unit, conserved at every instant.
2. **Economic-exposure conservation at T is N2.** The seller's exposure ceases at T regardless of custody, by the trade-as-transfer symmetry. This is a *theorem*, not a convention.
3. **Cancellation of opposing trades nets to zero in the security leg, exactly the realised PnL in the cash leg.** The map $F : \text{Trades} \to \text{DeferredClaims}$ is a homomorphism; the cash residual is the PnL.
4. **Conservation Lifting extends across the open window.** The proof structure of `ledger_data_v1.0.tex` Theorem 1 carries verbatim, with the deferred-claim unit included in the partition.
5. **Operational risks are broken symmetries.** Fails break N6 at the contractual date; partials break N6 at the total but preserve it at the slice; Herstatt breaks N6 across currencies; recalls break composition order. Each cost is exactly the value of the violated current.
6. **The existing spec drifts at §13.4.** It does not name the carrier of the open obligation. The deferred-claim unit closes the drift without modifying any of the other primitives — moves, conservation, valuation, settle_projection, or $F$.
7. **CDM gap is small.** Two new `EventIntentEnum` values (`SETTLEMENT_FAIL`, `BUY_IN`); the rest is direct mapping.
8. **Worked example (100 XYZ @ \$50 → \$52, +\$200 PnL, no cash moved):** the buyer's PnL is +\$200 entirely through the deferred claim; the seller's PnL is exactly zero (N2 demands this); the system PnL of +\$200 equals $\Delta P \times Q$ on the underlying — every conservation law is satisfied at every state.

The deferred-delivery claim is the conserved current of the open settlement window. Its quantity is conserved (N1), its dual to the underlying is invariant (N3), its signed pair preserves economic exposure (N2), it cancels under composition (N5), it nets under permutation (N4), and it redeems atomically under DvP (N6). Six symmetries, six conservation laws, one unit. That is the inner ground.

> *"My methods are really methods of working and thinking; this is why they have crept in everywhere anonymously."*

Find the symmetry, and the conservation law follows.
