# Round 1 Adversarial Review — cartan

**Reviewer.** Cartan (Mathematical Documentation Architect, Bourbaki ethos).
**Object of review.** `Ledger_Spec_v11.0/deferred_settlement_work/phase3/round1/proposal_v1.md`.
**Standpoint declared.** I authored the Phase 1 case for first-class obligation units (`u^circ`). The proposal rejects that case in §1 (¶ "First-class unit"). I therefore review with the additional duty to *steel-man the proposal* against my own prior preference, and to flag handwaving even where I would prefer the conclusion.

---

## Verdict

**ACCEPT_WITH_CHANGES.**

The proposal is implementation-ready in spirit and the rejection of first-class units is *operationally* defensible. It is not yet *mathematically* defensible: the formal apparatus that would make the rejection a *theorem* rather than a vote is missing. The Conservation Lifting claim, the homomorphism F, the DS1 quantification, and the per-leg / per-transaction relationship are stated in prose with symbols sprinkled through them; none is stated as a Theorem-with-hypotheses-and-proof. The 18 invariants contain at least three pairs whose independence is not established and at least one (DS5) whose statement is ill-typed.

These are correctable in Round 2 by the Settlement Team without re-architecting. The accept-with-changes verdict therefore conditions on the **Blocking** items below being addressed before the Pareto-arbiter ruling closes Phase 2. **None of the changes I demand reverses the per-counterparty-PS/PSS-plus-L_15 architectural choice.** I am persuaded on the architecture; I am not persuaded on the rigour.

---

## 1. Blocking (must close in Round 2 before Pareto ruling)

### B1. The "First-class unit was rejected" argument is recorded as a vote, not a proof

**Where.** §1 ¶ "First-class unit `u^circ`".

**Defect.** The rejection of `u^circ` rests on three operational claims:

  (i) *"doubles unit-master cardinality"*;
  (ii) *"every consumer of `PositionState` must opt out for obligation units"*;
  (iii) *"duplicates state already in L_15"*.

Each of these is *stated*. None is *proven*. As written, an equally-qualified panel could invert the verdict by re-weighting the same three terms. That is precisely what happened between Phase 1 (where five reviewers preferred `u^circ`) and Phase 2 (where the team withdrew it).

**What I do not contest.** I accept that (i) is empirically real (one new unit row per obligation; for a tier-1 dealer at 250k trades/day that is ~50M obligation-unit rows/year added to `UnitRegistry`). I accept that (ii) is real (price function on `u^circ` is degenerate; consumers must dispatch on `unit_type`). I accept (iii) only conditionally — the L_15 row carries the *lifecycle* but not the *quantitative ledger position* of "how many obligations of this kind are open"; under `u^circ` the quantitative count *is* the row count, and that is not duplicated state, that is the *primary* representation. The proposal collapses my Phase 1 distinction here.

**What must change.** Either:

  (a) State a **Proposition** of the form

  > *Let $\Phi$: (PS/PSS + L_15) → (`u^circ`-representation) be the natural map sending each open virtual-wallet contra-row plus its companion L_15 row to a single obligation-unit row. Then $\Phi$ is a bijection on states satisfying conservation; in particular every theorem provable about `u^circ` representation is provable about (PS/PSS + L_15) by transport.*

  with a proof. This makes the rejection an *engineering preference between two equivalent representations*, which is what the team actually means and which is defensible. **OR**

  (b) Identify a property the `u^circ` representation has that (PS/PSS + L_15) does *not* have, and show that the missing property is operationally undesirable. The proposal alludes to this in (ii) — degenerate price function — but does not formalise it.

Either is acceptable. The current state — a list of three engineering bullets — is not.

**Why this is Blocking and not Major.** §15.2 ¶ 2 says "*The two representations would map 1-to-1 with no loss in a future where Gap 10 is upstream.*" That sentence is the bijection $\Phi$ in disguise. Either it is true (and must be proven), or it is false (and the rejection of first-class units is an irreversible architectural choice, not a deferral). Phase 2 cannot leave this Schrödinger.

### B2. The Conservation Lifting Theorem is not stated

**Where.** §2.6.

**What is there.** A single equation

$$\sum_{w \in \mathcal{W}_{\text{real}} \cup \mathcal{W}_{\text{virtual}}} \Delta w_t(u) = 0$$

with the assertion *"per move pair. PS/PSS wallets are full participants in $\mathcal{W}_{\text{virtual}}$ and contribute to the sum by construction (v10.3 §2.5 + §2.4). No conservation carve-out."*

**Defect.** This is the **conclusion** of a theorem, not the theorem. The theorem the proposal is invoking — and the one Phase 1 (Halmos, Noether, myself) put weight on — is roughly:

  > **Conservation Lifting (informal).** *Let v10.3's conservation property C2 (StatesHome) hold over the real-wallet sub-universe $\mathcal{W}_{\text{real}}$. Let the deferred-settlement extension introduce $\mathcal{W}_{\text{virtual}} \supset \mathcal{W}_{\text{virtual,prior}}$ — the new PS/PSS wallet classes. Suppose every transaction $\tau$ touching a PS/PSS wallet is balanced under the move algebra (every credit to `PS_payable[w,c,u]` is paired with a debit on a real or virtual wallet of the same unit, and dually). Then the conservation property C2' over $\mathcal{W}_{\text{real}} \cup \mathcal{W}_{\text{virtual}}$ holds, and its restriction to $\mathcal{W}_{\text{real}}$ recovers C2 on real wallets when no PS/PSS wallet has nonzero balance.*

The proposal's §2.6 asserts the conclusion. It does not state the hypotheses. In particular:

  (a) it does not state the hypothesis "*every transaction touching a PS/PSS wallet is balanced*" — this is exactly what `apply_trade_move`'s `Move 1` / `Move 2` pair *does* in §3.2, but the obligation-creation step ("*Atomic with the move pair: register obligations in L_15*") is outside the move algebra and the *proposal does not say whether the L_15 register step is conservation-relevant*;

  (b) it does not state "*restriction to $\mathcal{W}_{\text{real}}$ recovers v10.3 C2*" — which is the property that justifies calling the new design a *backward-compatible extension* of v10.3 rather than a replacement;

  (c) it does not state at what *granularity* conservation holds — per-move-pair, per-transaction, per-block, per-day, per-state. §3.6's table (USD/XYZ across the four states) suggests **per-state, restricted to the touched units**, but this is shown by example, not proven in general.

**What must change.** State Conservation Lifting as a numbered Theorem with explicit hypotheses, and prove it. The proof is short — one paragraph — but it must be there. The fact that §3.6's worked example *holds* is corroboration; it is not a proof.

**Why this is Blocking.** Conservation is the headline invariant the entire ledger rests on (v10.3 P1; StatesHome C2; this proposal's DS2). If a reviewer in Round 2 wants to know "*does adding PS/PSS wallets break v10.3's conservation guarantee?*", the answer must be a one-line citation, not a hunt through §3.6's tables.

### B3. DS1 — "regardless of custody state" is not formally quantified

**Where.** §11 DS1 (lines 1471–1479).

**The statement as written:**

  > *For every settlement-typed transaction τ committed at T with intended settlement t_d ≥ T, for every party wallet w, every unit u moved by τ, every t ∈ [T, t_d^+] ∪ [t_d^+, ∞):*
  >
  > $w_t(u)[\text{own}] - w_{T^-}(u)[\text{own}] = \sum_{m \in τ, m.\text{unit}=u, w \in \{m.\text{src}, m.\text{dst}\}} \text{signed-delta}(m, w)$

**Defect 1: ill-formed time domain.** $[T, t_d^+] \cup [t_d^+, \infty)$ is the union of two intervals sharing the right endpoint of one with the left of the other; it equals $[T, \infty)$. Either the author meant $[T, t_d^-) \cup [t_d^+, \infty)$ (excluding the discharge instant) or they meant $[T, \infty)$ and the union is redundant clutter.

**Defect 2: the equation is silent during $[T, t_d^-]$.** The right-hand side $\sum_{m \in \tau, ...} \text{signed-delta}(m, w)$ is the contribution of *transaction $\tau$'s* moves. During the open window, by hypothesis $\tau$'s discharge moves have not yet been emitted (they occur at $t_d$). So the equation is computing $w_{T^-}(u)[\text{own}] + \Delta_T = w_t(u)[\text{own}]$ at every $t \in [T, t_d]$ — which says the position is constant during the open window. That *is* the desired DS1 statement. But the formal equation as written *does not say this*: it says "the cumulative own-delta from $\tau$'s moves equals the difference $w_t - w_{T^-}$", which is true *trivially* once $\tau$'s only own-touching move is at $T$ — the equation is then a tautology that any move-stream satisfies.

**Defect 3: the equivalent reformulation hand-waves.**

  > *equivalently: there exists no projection Π over (move stream + status overlay + obligation log) whose value during [T, t_d^-] differs from its value after τ has reached `Settled`, holding the price function constant.*

This is too strong. It quantifies over *all projections* — but the point of §10.1 is that there *is* such a projection (the settlement-date projection): `settled_position(w, u, t) := own − Σ open-obligation-signed-qty`. That projection is *literally constructed* in §10.1 line 1255–1259 to differ from `own` during the open window. The proposal's own §10.1 contradicts the universal quantifier in DS1's reformulation.

**What must change.** Re-state DS1 as:

  > **DS1' (Economic-Exposure-at-T).** Let $\tau$ be a settlement-typed transaction executed at $T$ with intended settlement $t_d > T$. Let $w \in \mathcal{W}_{\text{real}}$ be a real wallet party to $\tau$. Then for every $t \in [T, t_d]$ at which no other transaction has touched $(w, u)$:
  >
  > $w_t(u)[\text{own}] = w_{T^+}(u)[\text{own}]$
  >
  > i.e. the real-wallet `own` coordinate established by $\tau$ at $T$ is invariant on the half-open window until either another transaction touches it or settlement discharges. Equivalently: the *primary projection* `own(w, u)` is a function of $\tau$'s state at $T$ alone, not of the obligation FSM state. Settlement-date projections are *non-primary* by definition (§10.1) and are excluded from the universal quantifier.

This separates the *primary* projection (DS1 binds) from *non-primary* projections (free to differ). The current formulation conflates them.

**Why this is Blocking.** DS1 is labelled MANDATORY and CRITICAL in §11. A CRITICAL invariant that is either tautological or self-contradictory cannot ship.

### B4. The forgetful functor F (§8.4) is not actually shown to be a homomorphism

**Where.** §8.4.

**Claim.** "*F is a homomorphism. F : Lg → CDM*."

**Defect.** A homomorphism between two categories (or between two algebraic structures over which categories sit) requires:

  (i) a definition of the **morphisms** of the source category, and
  (ii) a proof that F **preserves composition**: $F(\sigma_2 \circ \sigma_1) = F(\sigma_2) \circ F(\sigma_1)$.

The proposal defines objects of $\mathbf{Lg}$ as *"`(WalletRegistry, UnitRegistry, MoveStream, ObligationStore)`"* (a 4-tuple — i.e., **states**), and morphisms as *"balanced atomic transactions"*. So $\mathbf{Lg}$ is the *category of ledger states with transactions as morphisms*, where composition is sequencing of transactions.

The proposal then enumerates **the action of F on objects/transactions individually** — F sends a trade-execution τ to a `BusinessEvent("Execution")`, etc. This is the action on objects/morphisms; *it is not the homomorphism property*. No claim is made that

  $F(\tau_2 \circ \tau_1) = F(\tau_2) \circ F(\tau_1)$.

In fact the proposal admits in the next paragraph: *"F loses: per-(wallet, unit) PositionState density (wallet axis collapses); in-flight virtual-wallet contras (gap is implicit ...)*."

If F **loses** information, F is not a homomorphism — it is at best a *lossy projection*. The categorical name for what the proposal describes is a **functor that is not faithful**, possibly not even full. "Homomorphism" is the wrong word.

**What is actually true.** I believe what the team means is closer to: *F is a functor from Lg to CDM such that for every transaction τ in Lg, F(τ) is a CDM BusinessEvent that records the same trade-economic content modulo the wallet-axis collapse. The composition law $F(\tau_2 \circ \tau_1) = F(\tau_2) \circ F(\tau_1)$ holds modulo wallet-axis collapse, but does not hold strictly.*

**What must change.** Either:

  (a) Replace "*F is a homomorphism*" with "*F is a (lossy, non-faithful) functor*" and restate "*F preserves*" / "*F loses*" as *what is preserved by F* and *what is forgotten*. Drop the homomorphism claim. **OR**

  (b) Define a *weakened* category $\mathbf{Lg}_{\text{econ}}$ in which the morphisms are *trade-economic-equivalence-classes of transactions* (i.e., quotient out the wallet-axis information F discards), and prove F is a functor from $\mathbf{Lg}_{\text{econ}}$ to $\mathbf{CDM}$. Then F is a homomorphism on the quotient but not on the original.

**Why this is Blocking.** The proposal cites "F is a homomorphism" in a section labelled "CDM cross-walk" that engineers will quote downstream as *the* statement of the Ledger-CDM relationship. If F is not what the team claims, the entire downstream "*Ledger first, CDM downstream. The Ledger reconciles to CDM via F, not the other way around*" pivot rests on an incorrect mathematical claim. Round 2 implementers will write code against F's signature; if F is not a homomorphism the round-trip property they rely on (ledger → CDM → ledger) is not guaranteed.

---

## 2. Major

### M1. Per-leg vs per-transaction FSM — the categorical refinement is missing

**Where.** §2.4, §5.1, §5.2.

**Claim.** *"The transaction-level field `MoveStream[tx_id].settlement_status` is the MAX projection over per-leg `L_15.Obligation.state` values"* (§2.4); *"A 4-state extension {Instructed, PartiallySettled, Failed, BoughtIn} captures the operationally observable transaction state"* (§5.1).

**Defect.** The proposal asserts MAX-projection without saying:

  (a) what the lattice ordering is on the 7-state observable (it gives one — `Settled > PartiallySettled > Failed > BoughtIn > Instructed > Executed > Cancelled` — but does not show this is a *lattice*, in particular does not show it is well-defined when one leg has terminal `Cancelled` and the other has `Settled`);

  (b) whether the projection is a **functor** (does it preserve transitions: if leg L₁ steps from `Pending` to `Discharged`, does the transaction-level status step monotonically?);

  (c) whether the per-leg FSM (3-state closed sum {Pending, Discharged, Compensated, Defaulted} — actually 4-state) and the transaction-level FSM (7-state) form a **fibred structure**: the transaction-level state is a function of the leg-state vector, modulo cancellation.

The right framing is: the per-leg FSM is the *primitive*; the transaction-level FSM is its *quotient* under the equivalence "*same MAX-projected status*". A categorical statement of this would resolve all three defects at once. Without it, the proposal has *two independent FSMs* and merely asserts they are related — a future reviewer (especially Halmos) will ask: *"if I prove a property about the per-leg FSM, does it lift to the transaction-level FSM?"* The answer should be yes-by-construction; presently it is yes-by-assertion.

**Pathological case the proposal does not cover.** What is the transaction-level status when leg₁ = `Cancelled` (terminal-cancel) and leg₂ = `Discharged` (terminal-good)? The lattice in §5.1 puts `Settled > Cancelled`, so MAX = `Settled` — but the transaction is *not* settled in any reasonable sense; one leg was cancelled. This is the canonical DvP-half-cancelled pathology. Either the proposal forbids this configuration (by an invariant: cancellation is per-transaction, not per-leg) or the lattice is wrong.

**Recommendation.** State the per-leg FSM, the transaction-level FSM, the projection $\pi$: per-leg-state-vector → transaction-state, and prove $\pi$ is monotone (i.e., if $\vec{s}_1 \to \vec{s}_2$ in the leg-vector FSM then $\pi(\vec{s}_1) \le \pi(\vec{s}_2)$). Then DS8 (status monotonicity) becomes a *theorem*, not an axiom. Currently DS8 is asserted; with the projection result it would be derived from per-leg monotonicity.

### M2. DS5 ("Replay Determinism") is ill-typed

**Where.** §11 DS5 (line 1509).

**Statement.** "*For any two interleavings $\pi_1, \pi_2$ of the same multiset of confirmation messages applied to the same initial state $\sigma_0$: $\text{apply}(\sigma_0, \pi_1) = \text{apply}(\sigma_0, \pi_2)$, restricted to (L_13, SettlStatus, L_15).*"

**Defect.** Permutation-invariance under arbitrary interleaving is **stronger than the proposal can deliver**. Counterexample built from the proposal's own §3.5: a `sese.025` and a `sese.024` for the same obligation in opposite orders are *not* idempotently interchangeable — a `sese.025` arriving after a `sese.024` in the message stream is a restatement and falls under G5 (the open gap). The proposal recognises this in G5 and recommends "*treat restatement as a new obligation*", but that means `apply(σ, sese.024 ; sese.025) ≠ apply(σ, sese.025 ; sese.024)` — the first produces a Failed→Reopened/new-obligation pair, the second produces a Settled obligation directly.

DS5 as written contradicts G5's resolution. Either:

  (a) DS5 must restrict to *non-restating* messages (where the multiset of confirmations is "consistent" — no message contradicts another); or
  (b) DS5 must explicitly state that the post-state under permutation is equal *up to the corrections-chain isomorphism* (DS16); or
  (c) G5 must be closed differently.

**Recommendation.** Restate DS5 as:

  > **DS5'.** *Let $C = \{c_1, ..., c_n\}$ be a multiset of confirmation messages, all addressed to the same obligation $o$, all bearing the same primary witness payload (qty, ccy, EndToEndId match). Then for any permutations $\pi_1, \pi_2$ of $C$ applied to the same initial state $\sigma_0$:* $\text{apply}(\sigma_0, \pi_1) = \text{apply}(\sigma_0, \pi_2)$ *restricted to $(L_{13}, \text{SettlStatus}, L_{15})$.*

This is the *commutativity* statement actually wanted. The current statement is too strong.

### M3. The 18 invariants are not 18 distinct claims

**Where.** §11 DS1–DS18.

**Claim audit.**

  - **DS6 (idempotency of finality)** is a special case of **DS5 (replay determinism)**: idempotency is the case $|C|=2$ with $c_1 = c_2$ in DS5's notation. If DS5 holds, DS6 holds. The team can keep DS6 as a *named consequence* but should note the implication.

  - **DS13 (reconciliation pair anchoring)** is a special case of **DS3 (reconciliation lead-lag identity)**: it asserts that on the subset of trades in terminal state, the reconciliation residual is zero. DS3 with `InFlight = 0` (because the trade is terminal) gives exactly this. DS13 is DS3 evaluated at terminal states.

  - **DS18 (DvP atomicity)** at the ledger level and **DS17 (capability scoping)** are independent, but **DS18** is partly implied by the executor's transactional primitive in v10.3 §8.4 (the proposal cites this as the parent). It is not new; it is *re-stated* for the deferred-settlement context. That is fine, but the proposal should note it.

  - **DS11 (partial conservation)** has two sub-claims: (a) economic position unchanged on partial settlement, and (b) child obligation conservation $q_{\text{rem}} + q' = q$. Sub-claim (a) is **DS7** (failure non-reversal) extended to partial discharge; sub-claim (b) is the new content. They should be split.

  - **DS12 (variant degeneration)** is a *meta-invariant*: it asserts DS1–DS11 hold for variant settlement cycles. As such, it is not on the same logical level as the other invariants — it is a quantification over them. It belongs in a separate section, not in the same numbered list.

**What must change.** Re-state the invariant register as:

  - **Primitive invariants.** DS1, DS2, DS3, DS4, DS5, DS7, DS8, DS9, DS10, DS14, DS15, DS16, DS17, DS18.
  - **Derived invariants.** DS6 (DS5 with $|C|=2$, $c_1=c_2$); DS11 (DS7 + new partial-conservation sub-claim); DS13 (DS3 at terminal states).
  - **Meta-invariant.** DS12 (claims DS1–DS11 hold uniformly across $t_d \in \{T, T+1, T+2, T+5, ...\}$).

This is more honest. *Eighteen distinct claims* is a marketable count; the actual count of *primitive* claims is ~14. Mathematical rigour requires the distinction.

**Severity.** Major because it does not change architecture, but it changes the verification surface: a TLA+ model (PO-8) that proves the 14 primitives gets the 4 derived ones for free; the team should know which is which.

### M4. "DvP atomicity" is used in two different senses without disambiguation

**Where.** §1 ¶ "Trade-date economic recognition"; §11 DS18; §12.2 (PairedObligation).

**Sense 1 (trade-time atomicity).** At $T$, the move pair (cash leg + securities leg) commits as one StateDelta. v10.3 §8.4. *Already structurally guaranteed by the executor.*

**Sense 2 (settlement-time atomicity).** At $t_d$, the discharge move pair (drain PSS_receivable + drain PS_payable to broker virtual) commits as one StateDelta. *This is the §12.2 PairedObligation guarantee.* Currently NOT guaranteed in v10.3 — that is the §12.2 motivation: *"different handler runs at T+2; nothing in v10.3 forbids it from discharging the security leg without the cash leg."*

**Sense 3 (CSD-level atomicity).** The CSD's mechanism (T2S, DTC NSCC, Euroclear) provides DvP Model 1 / Model 2 / Model 3 atomicity over the cash and securities legs at the *external* settlement layer. *Outside the ledger.*

The proposal uses "DvP atomicity" without disambiguating these three. DS18's parent is *"v10.3 P2, §8.4; StatesHome C3; minsky I-DEF-12"* — that is Sense 1. §12.2's PairedObligation is Sense 2. §9.1's CSDR/DvP-Model-1 reference is Sense 3.

**What must change.** Define three distinct names — `DvP_TradeAtomic`, `DvP_DischargeAtomic`, `DvP_CSDLevel` — and use them consistently. DS18 as currently written invokes "DvP" without qualification; a Round 2 implementer will not know whether they need to satisfy Sense 1 (already satisfied), Sense 2 (requires §12.2's PairedObligation refactor), or Sense 3 (out of scope).

### M5. Witness-driven discharge (§5.4, DS4) does not handle the `sese.024`-without-witness case cleanly

**Where.** §5.4, DS4.

**Claim.** *"The framework never marks a leg `Discharged` by inference, by clock, or by absence of evidence."*

**Tension.** §5.4 then says: *"After T_max = expected + 5bd ... the obligation auto-promotes to a **break** in `L_18.BreakRegister` of kind `obligation_overdue`."*

The auto-promotion at T_max is *driven by absence of evidence* — exactly what the prior sentence forbids. The resolution is: *promotion to BREAK ≠ promotion to FAILED ≠ DISCHARGE*. The break is a *workflow signal*, not a state transition. But the proposal does not make this distinction precise.

**What must change.** State explicitly: an obligation *cannot* transition from `Pending` to `Failed` without a witness (`sese.024` or equivalent); auto-promotion at $T_{\text{max}}$ is to a *break in $L_{18}$* (which is workflow state, not obligation state); the obligation itself remains `Pending` until either (a) a witness arrives, (b) a CORRECTION discharges it, or (c) a counterparty default triggers DS15. This is the right behaviour but the proposal *says* it (§5.4 line 595) and then writes DS4 without the distinction.

DS4 should explicitly include the disjunction:

  > **DS4'.** *For every settlement obligation $o$ and every transition $o.\text{state}: \text{Pending} \to s$ where $s \in \{\text{Discharged}, \text{PartiallyDischarged}, \text{Compensated}\}$, there exists a witness envelope $e \in L_{11}.\text{ExternalConfirmation}$ such that $\text{verify\_envelope}(e) = \text{true}$ and $\text{matches\_predicate}(e, o.\text{discharge\_predicate})$. The state $\text{Failed}$ is reachable only via witness ($\text{sese.024}$ or counterparty-default declaration); time-based transitions are forbidden.*

Currently DS4 omits `Failed` from the witness-required set, leaving open the *wrong* reading "Failed can be reached without witness".

### M6. The `attempt_seq` in §6.4 partial-settlement `tx_id` is not defined

**Where.** §6.4 (line 687): *"The `attempt_seq` field in the deterministic `tx_id` formula prevents collision between the two partial finality messages."*

**Defect.** No formula `tx_id = hash(... attempt_seq ...)` is given. §3.2 line 168–169 defines `tx_id = hash("ECON_REC", ...)`; §3.5 line 273 defines `tx_id = hash("FINAL", TX1.tx_id, sese.025_msg_id, camt.054_msg_id)`. Neither carries `attempt_seq`. §9.7 line 1223 alludes to *"Λ10 (`tx_id = hash_jcs(business_event_id, attempt_seq)`)"* without defining what `attempt_seq` increments over.

**Recommendation.** Pin `attempt_seq` semantics in §3.2 (or wherever the canonical `tx_id` formula lives) and reference it from §6.4. Currently `attempt_seq` appears as a *deus ex machina* in §6.4.

### M7. The PS / PSS keying ambiguity (§15.2 ¶ 1) is left open as a Pareto-arbiter call, but is load-bearing for §4.3's constant-time recon

**Where.** §15.2 ¶ 1; §4.3.

**Tension.** §4.3 claims constant-time recon scan because *"a million open trades aggregate into a thousand wallet rows; the scan is bounded by wallet count, not transaction count."* This depends on **per-counterparty per-(currency-or-ISIN)** keying. If §15.2 ¶ 1's Pareto-arbiter ruling goes the other way — **per-instruction** keying — then the wallet count is *equal to* the open-trade count, and §4.3's claim collapses.

The proposal takes per-counterparty as the *floor* (§1, §2.2) but flags it as *not formally decided* (§15.2 ¶ 1). This is incoherent: either §4.3 is conditionally true (in which case so flag it), or the keying choice is decided (in which case §15.2 should not list it as open).

**Recommendation.** Resolve the keying choice in Phase 2 *before* the Pareto-arbiter ruling, since downstream sections (§4.3, §4.4, §10.6 audit) depend on it. The Pareto-arbiter should rule yes/no, not punt.

---

## 3. Minor

### m1. State representation §2.1 — "every entity has a place"

I checked: every entity in the §3 worked example has a place. `w_us`, `w_GS_broker`, `w_DTC_depot`, `w_JPMC_nostro_USD`, `PSS_receivable[w_us, GS, XYZ]`, `PS_payable[w_us, GS, USD]` — all in `WalletRegistry` or `PositionState`. Obligations live in $L_{15}$. Settlement status lives on `MoveStream[tx_id]`. Witnesses live in $L_{11}$. **Nothing is unhomed.** Good.

The one near-miss: `attempt_seq` (M6 above) and `tx_id` derivation across saga-replay are mentioned without a clear home — they are presumably in $L_{13}$ via the deterministic-id pin, but this should be stated.

### m2. §3.2 worked example: the L_15 register step is *atomic with the move pair* but the proposal does not say *how*

The text says *"Atomic with the move pair: register obligations in L_15"*. The mechanism by which L_15 register and the move pair commit atomically is the executor's transaction primitive — the same one v10.3 §8.4 uses for DvP. This is a **two-resource atomic commit** (move-stream + obligation-store), and the team should call it out and confirm StatesHome C3 covers it. Currently it is asserted without grounding.

### m3. §7.3.5 — "C's GPM coordinates are unchanged at this step"

The text says *"`w_C`'s GPM coordinates are unchanged at this step. The PSS/PS virtual wallets close to zero. C's net position is `own=0, borr=+500, coll_post=+50000`"*. This is true. But notice: the *original short sale* recognised `own = -500` at $T$ (§7.3.2). At $T+1$ after loan settles, `own = 0`. At $T+2$ after delivery to D, `own = 0` (unchanged). The economic position has changed; the *coordinate at this discrete moment* has not. This is a wording subtlety. Recommend rewording §7.3.5 to: *"`w_C`'s GPM coordinates are unchanged **between $T+1$ and $T+2$**"*.

### m4. §8.4 line 1059 — "F preserves: ... per-trade sequencing (`before`/`after` `TradeState` chain)"

Good claim, but it implies F preserves the *order* of transactions, which is part of being a functor (preserving composition). Restate as such: F preserves composition on the trade-history sub-category. (Connects to B4.)

### m5. §11 DS17 ("Capability Scoping") — the unique-writer claim should reference C11

DS17 says the SettlementWorkflow is the unique writer of `SettlStatus(τ)`. The parent citation is StatesHome C11; good. But the proposal does not say what happens if a non-Settlement-Workflow handler *attempts* to write SettlStatus — the executor must reject. State this: *"capability check rejects the transaction at admission"*, citing the C11 mechanism.

### m6. §13 G2 (UTI matching) — the proposal commits to "ambiguous → quarantine" but the type-system §12.8 row 14 has the right closed sum

The §12.8 closed sum `match_confirmation : confirmation -> [Unique | Ambiguous of list | Unmatched]` is the right primitive. §13 G2 should reference §12.8 rather than restate the constraint.

### m7. §11 DS9 — buy-in compensation closure existence claim

DS9 asserts *existence* of $\tau_{\text{buyin}}$ for every Failed obligation not cured within $\Delta_{\text{CSDR}}$. This is a *liveness* property; the proposal correctly classifies it as Runtime in §11's table. But the "exists" quantifier requires a *time bound*: when must $\tau_{\text{buyin}}$ exist? The CSDR window (4-7 BD post-ISD) is the practical answer; state it. Currently DS9 reads as *"exists at some point"*, which is unsound.

### m8. §12.5 "smart constructor rejecting 14 malformed cases" — case 5 is silent on currency mismatch

Case 5: *"`|qty × price − cash_amount| > rounding_tolerance(currency)`"*. This presumes a single currency on both sides; for a cross-currency trade the cash leg's currency may differ from the price's currency. State the type as `cash_currency = price_currency`, or carry FX rate explicitly.

### m9. §15 §15.2 ¶ 2 — "deferred, not killed" with the bijection promise

The proposal says *"The two representations would map 1-to-1 with no loss in a future where Gap 10 is upstream."* That is the bijection $\Phi$ I demanded in B1. Move it to §1's rejection rationale and state it as the *condition* under which the rejection is non-prejudicial.

---

## 4. What works (and works well)

The following deserves explicit recognition — both for the quality of the work and because Round 2 should not perturb these:

**W1.** §3 worked example. Best-in-class. Tables across four states, conservation check at every step, journal entries, PnL path-independence numerically demonstrated. This is the load-bearing artefact and it earns its load.

**W2.** §1 ¶ "What was rejected." All five rejection lines (7th coordinate; first-class units; pending_in/out as fields; CSD-level wallet; UnitStatus-level state) are *named with their proposers*, *named with their reasons for rejection*, and *named with what was adopted instead*. This is exactly the discipline an adversarial review needs to see; it permits a reviewer (me) to disagree on a specific point without re-litigating the entire decision tree.

**W3.** §4.3 constant-time recon. The SQL is right, the complexity argument is right (modulo M7 above on keying), the *not-a-join* point is the operationally important one. Recon engineers will quote this.

**W4.** §4.5 "What is a break and what is not." The classification table — expected lead-lag vs break, with the specific witness-message anomalies (sese.025 with wrong amount → HARD: do not apply, quarantine) — is operationally non-trivial and correctly captured.

**W5.** §6.2 T+0 atomic DLT degeneracy. The architecture-as-parameter case is made compactly and credibly. The framework absorbs T+0 by parameter change. This is the test the team correctly identifies and correctly passes.

**W6.** §10.1 trade-date accounting MANDATORY ruling. The reasons (IFRS 9.B3.1.3; ASC 320; CRR Art 325 capital implication; P10 path-independence; ECL on settlement receivables) are the right reasons in the right order.

**W7.** §12.2 PairedObligation. This is the type-level fix to the discharge-time atomicity gap — a real defect in v10.3 (M4 Sense 2). The proposed solution is the right one.

**W8.** §13.1 G1–G12 honesty. Twelve gaps named, with constraint and owner for each. *None of the gaps is a design defect* (§15.3) is the correct framing — they are all closable by closed-sum commitments, registries, or property tests. The gap register is what makes this proposal a Phase 2 deliverable rather than a research artefact.

**W9.** §11 type-vs-runtime decomposition table (line 1601–1622). The 6/9/3 split is *the* honest call; minsky's recommendation (*take the cost for DS17 + DS7, leave others runtime*) is the right Pareto trade-off. The proposal's acceptance of this without bikeshedding is mature engineering.

---

## 5. Recommendation

**Verdict: ACCEPT_WITH_CHANGES.**

The proposal converges on a defensible architecture (PS/PSS virtual wallets + L_15 obligation row + per-leg FSM + transaction-level projection). The architectural choice against my Phase 1 first-class-unit position is *operationally* sound — I am persuaded on the engineering. **I am not yet persuaded on the rigour.**

**Round 2 entry conditions (Blocking):**

  1. **B1.** State the bijection $\Phi$: (PS/PSS + L_15) ↔ ($u^{\circ}$-representation) as a Proposition with proof, OR identify the property the two representations differ on and the operational reason the difference matters. (~½ page; the §15.2 ¶ 2 sentence is the proposition; promote it.)
  2. **B2.** State Conservation Lifting as a Theorem with hypotheses. (~½ page; the proof is one paragraph.)
  3. **B3.** Re-state DS1 with corrected time-domain quantifier and primary-vs-projection-projection distinction. (~10 lines.)
  4. **B4.** Replace "F is a homomorphism" with the correct categorical claim — either *F is a (lossy, non-faithful) functor* with explicit "preserves" / "loses" lists, or *F is a homomorphism on the wallet-axis-collapsed quotient $\mathbf{Lg}_{\text{econ}}$*. (~½ page.)

**Round 2 entry conditions (Major, before Pareto ruling):**

  5. **M1.** Per-leg-to-transaction projection $\pi$ stated as monotone functor; DS8 derived from per-leg monotonicity. (~½ page.)
  6. **M2.** Re-state DS5 as commutativity over consistent-multiset confirmations; reconcile with G5. (~5 lines.)
  7. **M3.** Audit DS1–DS18 for derived vs primitive vs meta; mark accordingly. (~10 lines edit.)
  8. **M4.** Disambiguate DvP-atomicity Sense 1/2/3 with three names. (~10 lines.)
  9. **M5.** Re-state DS4 with `Failed` in the witness-required set; clarify break-vs-state distinction. (~5 lines.)
  10. **M6.** Pin `attempt_seq` semantics. (~3 lines.)
  11. **M7.** Resolve PS/PSS keying choice (per-counterparty vs per-instruction) before §4.3 ships. (Pareto ruling.)

**Round 2 entry conditions (Minor):** address inline; none is blocking.

**Pareto-arbiter ruling I support:**

  - Per-counterparty per-(currency-or-ISIN) PS/PSS keying as floor; per-instruction as derived view. **Confirmed yes.**
  - $D_{\max} = 2$ for partial-fill recursion. **Confirmed yes** — jane_street's pragma is right; deeper cascades are pathological and should auto-promote to `Defaulted`.
  - Type-discipline scope: take the cost for DS17 and DS7; leave others runtime; DS1 hybrid. **Confirmed yes.**

**Closing remark.** The Settlement Team has produced a proposal that is *implementation-ready* in the sense that an engineer can build to it. It is *not yet specification-ready* in the Bourbaki sense — too many theorems are stated as bullet points. Round 2 is the right place to upgrade the rigour without disturbing the architecture. The team should not read my Blocking items as a re-litigation of the first-class-unit question; I have lost that argument and I accept the loss. I am asking the team to write down *why I lost it* with the precision that distinguishes a converged specification from a vote.

— cartan
