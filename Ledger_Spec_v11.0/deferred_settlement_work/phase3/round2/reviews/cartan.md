# Round 2 Adversarial Review — cartan

**Reviewer.** Cartan (Mathematical Documentation Architect, Bourbaki ethos).
**Object of review.** `Ledger_Spec_v11.0/deferred_settlement_work/phase3/round2/proposal_v2.md` (2192 lines, ~21k words).
**Standpoint.** Round 1 verdict was ACCEPT_WITH_CHANGES with 4 BLOCKING and 7 MAJOR rigour items. I review v2 against that closure list, with the same standing duty to steel-man.

---

## Verdict

**ACCEPT_WITH_CHANGES** — converging toward Pareto, but **not yet Pareto-reached** on rigour. Two of the four R1 blocking items are *substantively* closed; one is *partially* closed (§7.4 bijection Φ has a sketch, not a proof); one is *correctly restated but with a minor sign-defect* (§8.4 functoriality claim is locally inconsistent with the lossy/non-faithful body). The seven majors are mostly closed; two carry residual rigour debt (DS5 commutativity is given by table not theorem; DS4 still admits the wrong reading on `Failed`).

The proposal has materially improved. The architecture is unchanged and correct. The Bourbaki bar — every theorem stated with full hypotheses, every claim either proven or labelled "conjecture" — is now within reach but not crossed. **Round 2 closure of the items below would deliver Pareto in Round 3.** I would not block Round 3 entry; I would block Pareto declaration on §7.4 and §8.4 alone.

---

## 1. R1 Closure Table

Each row: R1 finding → v2 location → closure status → residual rigour debt (if any).

| R1 ID | v2 § | Closure | Residual debt |
|---|---|---|---|
| **B-1** Bijection Φ as Proposition | §7.4.1 + §7.4.2 | **PARTIAL.** Theorem statement present; carrier sets named; proof is *sketch* not proof. See **R2-B1** below. | Carrier set asymmetry; inverse $\Phi^{-1}$ never named; identity-on-composition not checked. |
| **B-2** Conservation Lifting Theorem | §7.5.1 + §7.5.2 | **CLOSED.** Hypotheses H1..H5 stated. Proof outline by induction on $|\Sigma_t|$ given. Conclusion correctly framed as "for every unit, every $t$". | Minor: H4 ("wallet universe constancy") needs qualifier — "new wallets enter at zero" is the *constructive* lemma, not an assumption; see **R2-m1** below. |
| **B-3** DS1 time-domain bug | §11 DS1 | **PARTIAL.** v1's "$[T, t_d^+] \cup [t_d^+, \infty)$" tautology removed; new statement quantifies on $[T_{\text{exec}}(\tau), \infty)$. *However* the equivalent reformulation (existence of no projection differing on $[T, t_d^-]$) is **still self-contradictory** with §10.1 settlement-date projections. See **R2-B3** below. |  |
| **B-4** F as homomorphism | §8.4.1 + §8.4.2 | **MOSTLY CLOSED.** Renamed "lossy non-faithful functor"; quotient $\mathbf{Lg}_{\text{econ}}$ defined; F restricted to quotient is a homomorphism. **One internal inconsistency:** §8.4.1 simultaneously asserts $F(\tau_1 \circ \tau_2) = F(\tau_1) \circ F(\tau_2)$ (functoriality, hence composition-preserving) AND that F is "non-faithful" with composition-information loss. *Both can be true* (functor + non-faithful is consistent), but the example given of non-faithfulness ("multi-leg atomicity F-projects to a CDM BusinessEvent that does not structurally enforce atomicity") is an *object-level* loss, not a *morphism-level* identification. See **R2-B4** below. |  |
| **M-1** Per-leg/tx projection as monotone functor | §5.3 (`tx_status` projection) | **MOSTLY CLOSED.** Projection $\pi$ defined as pure function; demoted from FSM. Monotonicity of $\pi$ across leg-state transitions is **asserted by structure, not proven** (no monotonicity lemma in §5.3). PO-8 (TLA+) is supposed to verify it; that is verification, not proof. See **R2-M1** below. |  |
| **M-2** DS5 over-quantification | §11.A (DS5 restated) + §6.5.5 commutativity table | **CLOSED in spirit.** DS5 promoted out of v11.0 invariant list; restated in §11.A as "replay determinism over multiset of finalised witnesses; restatements update `t_known` but `t_obs` preserved." Commutativity matrix in §6.5.5 enumerates non-commuting cases as "deterministic precedences." *Rigour residue:* the proposal has *replaced* a wrong universal quantifier with a *table*, not with a theorem. The commutativity table holds *by construction* of the FSM step function but is not stated as a lemma. See **R2-M2** below. |  |
| **M-3** 18→14 invariants pruning | §11 (10 invariants) + §11.A (restated v10.3) | **CLOSED.** Better than I demanded: 10 primitives + 7 restated v10.3 in appendix. DS6, DS13, DS11 split correctly handled. DS12 correctly relabelled as meta-invariant ("DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS17, DS18 hold without modification"). |  |
| **M-4** DvP-L/DvP-S/DvP-E | §6.5.3 + DS18 + §12.1.2 | **CLOSED.** Three names disambiguated; DS18 qualified as DvP-L; DvP-E pinned to PairedObligation; DvP-S pinned to CSD. |  |
| **M-5** DS4 + Failed witness requirement | §11 DS4 + §5.5 | **PARTIAL.** §5.5 narrative is correct ("watchdog triggers `wf-confirm-break`, NOT auto-FAIL"). §11 DS4 *statement* still omits `Failed` from the witness-required set: the implication arrow's RHS lists only `{Discharged, PartiallySettled, Compensated}`. The combined effect of §5.5 prose + DS4 invariant is correct *operationally*, but DS4 as a *formal* invariant still does not exclude time-based `Pending → Failed`. See **R2-M5** below. |  |
| **M-6** `attempt_seq` definition | §0.3 + §6.5.1 + §6.5.6 | **CLOSED.** Defined in §0.3 ("retry counter, ≥0, increments on workflow-level retry"). Pinned in §6.5.1 formula. Carried across CaN per §6.5.6. No more *deus ex machina*. |  |
| **M-7** PS/PSS keying choice | §0.2 + §2.2 | **CLOSED.** Per-counterparty per-(currency-or-ISIN) confirmed as floor; surface labels `PS`/`PSS` retained as projection labels in cash/securities settings; per-instruction keying not pursued. §4.3 constant-time scan claim now has a stable basis. |  |

**Closure summary.** 4 BLOCKING: 1 fully closed (B-2), 1 mostly closed with single defect (B-4), 2 partially closed (B-1, B-3). 7 MAJOR: 5 fully closed (M-3, M-4, M-6, M-7, M-1 mostly), 2 partial (M-2 by table, M-5 by narrative).

---

## 2. New Round-2 issues (issues created or surfaced by v2's revision)

### R2-B1 — §7.4 Bijection Φ is sketched, not proved

**Severity.** BLOCKING for Pareto declaration; MAJOR for Round 3 entry.

**Defect.** §7.4.2 has the heading "Proof sketch" — that is *the proposal's own admission* that the proof is incomplete. A bijection between two carrier sets requires:

  (i) a definition of the *carrier sets* $M$ and $C$ as sets (not as 4-tuples of "registries");
  (ii) a definition of $\Phi : M \to C$ as a *function* (defined for every $m \in M$, single-valued);
  (iii) a definition of $\Phi^{-1} : C \to M$ as a *function*;
  (iv) verification that $\Phi^{-1} \circ \Phi = \mathrm{id}_M$ and $\Phi \circ \Phi^{-1} = \mathrm{id}_C$.

The proposal supplies (i) loosely, (ii) for some elements only, (iii) implicitly via a "reconstruct" verb, and (iv) not at all.

**Specific gaps:**

  - **Carrier-set asymmetry.** $M = (W, U, P, L_{15})$ is a 4-tuple; $C = (W', U', P')$ is a 3-tuple — *correctly*, because $C$ collapses $L_{15}$ into $U'$. But this means $\Phi$ is a *function on 4-tuples* whose codomain elements are 3-tuples. The proof sketch says $W' = W \setminus \{w : \mathrm{class}(w) = \mathrm{cpty\_virtual}\}$ — but does *not* say what happens to `csd_virtual` wallets. Are they in $W'$? If yes, are they unchanged by $\Phi$? The proof is silent.
  - **$\Phi^{-1}$ is named "reconstruct" without a formula.** §7.4.2 says: "*given $(W', U', P')$, define $L_{15}$ as the set of $u^\circ_o \in U'$ with `UnitStatus.kind = Obligation`; reconstruct $(W, U, P)$ by collapsing each $u^\circ_o$ across its two holders into a `cpty_virtual` wallet pair.*" The verb "reconstruct" is doing all the work. *Define* the inverse explicitly: for each $u^\circ_o \in U' \setminus U$, identify the two holders $w_h, w_c$ and the qty $q = P'(w_h, u^\circ_o)$, and produce the `cpty_virtual` wallet $w_{PS}[w_h, w_c, u]$ with balance $\pm q$. This is a function; write it as one.
  - **Composition identities not checked.** No statement that $\Phi^{-1}(\Phi(m)) = m$ for arbitrary $m \in M$, no statement of the dual. The "Surjection" + "Injection" + "Conservation preservation" structure of the sketch shows *injectivity* and *surjectivity separately*, which together imply bijection — *but only on sets, not as morphisms of structured objects*. The structures here (with conservation, sign convention, FSM state on `UnitStatus`) are not transparent under bijection unless one verifies preservation explicitly.
  - **The state-of-the-obligation transports.** §7.4.1 says `u^\circ_o`'s `UnitStatus` carries the lifecycle state $s$. So $\Phi$ must *carry* the FSM state from $L_{15}$ into `UnitStatus[u^\circ_o]`. This is the load-bearing transport (it is what makes the bijection a *natural* equivalence rather than just a set bijection). Not stated as a lemma.

**What must change.** Promote §7.4.2 from "Proof sketch" to "Proof". Define:

  - $W$, $U$, $P$, $L_{15}$ as sets/functions explicitly.
  - $\Phi : M \to C$ by component: $\Phi(W, U, P, L_{15}) = (W', U', P')$ where each component is a definite formula of the inputs.
  - $\Psi : C \to M$ as the inverse: $\Psi(W', U', P') = (W, U, P, L_{15})$ similarly.
  - Lemma 7.4.2.a: $\Psi \circ \Phi = \mathrm{id}_M$. Brief proof.
  - Lemma 7.4.2.b: $\Phi \circ \Psi = \mathrm{id}_C$. Brief proof.
  - Lemma 7.4.2.c (Conservation transport): $\sum_{w \in \mathcal{W}} w(u) = 0 \iff \sum_{w' \in W'} w'(u') = 0$ when summing over corresponding wallet sets (with $u^\circ_o$ on the $C$ side replacing the cpty-virtual wallet pair on the $M$ side). The "when summing over corresponding wallet sets" needs a precise statement of the correspondence.

This is **half a page of additional rigour**. The architecture does not change. The result — that Φ is a bijection — is correct as stated; the proof is the missing piece.

**Why this is BLOCKING for Pareto.** The §7.4 result is the load-bearing claim that justifies §1.2's rejection of `u^circ` as *non-prejudicial deferral* rather than *irreversible architectural choice*. With the proof complete, the rejection rests on operational cost (§7.4.3) — a defensible Pareto stance. Without the proof, §15.2 line 2108 ("Closed" for Theme 12) overstates.

### R2-B3 — DS1 reformulation still self-contradictory with §10.1

**Severity.** BLOCKING for Pareto; MAJOR for Round 3 entry.

**Defect.** §11 DS1 has been correctly tightened on the time-domain quantifier. But the *equivalent reformulation* in DS1 line 1629 still reads:

  > "*equivalently: there exists no projection $\Pi$ over `(move stream + lifecycle states + obligation log)` whose value during $[T, t_d^-]$ differs from its value after $\tau$ has reached `Discharged`, holding the price function constant.*"

This is **the same defect I flagged in R1**. Settlement-date projections (`settled_position(w, u, t) := own − Σ open-obligation-signed-qty`) *exist*, are *constructed* in v10.3 §10.1 (note: v10.3 §10.1 reference; in v2 the analogue is §4.1.5 `inflight_in/inflight_out` named projections which by construction *do differ* during the open window). The universal quantifier over "no projection $\Pi$" is contradicted by §4.1.5's *named* projections that the proposal itself constructs.

**The intended reading.** What the team means is: "no projection over the *primary economic-position layer*" — i.e., the `own` coordinate of real wallets. Settlement-date projections operate on a *different* layer (the inflight overlay).

**What must change.** Replace the equivalent reformulation with:

  > "*equivalently: the primary projection $\mathrm{own}(w, u, \cdot)$ on real wallets is constant on $[T, t_d^-]$ (modulo other transactions). Settlement-date and inflight projections (§4.1.5) are non-primary by construction and are excluded from the universal quantifier; they are projections over $L_{15}$ overlay state, not over the `own` coordinate.*"

The fix is **3 lines**. The current statement remains a CRITICAL invariant containing a self-contradiction that any reader who reads §4.1.5 alongside §11 will detect.

**Why BLOCKING for Pareto.** A CRITICAL invariant cannot be self-contradictory with another section of the same document.

### R2-B4 — §8.4 internal inconsistency on the meaning of "non-faithful"

**Severity.** MAJOR (not blocking; the result is right; the wording is loose).

**Defect.** §8.4.1 says:

  - "*Functoriality.* F respects identities and composition: $F(\tau_1 \circ \tau_2) = F(\tau_1) \circ F(\tau_2)$."
  - "*Non-faithful.* F is not faithful: distinct $\mathbf{Lg}$-morphisms can map to the same $\mathbf{CDM}$-morphism."

These are mutually consistent (a functor can be non-faithful without violating composition). However, the *example* given of non-faithfulness is:

  > "*Specifically, multi-leg atomicity (one ledger transaction with three coordinated moves) F-projects to a CDM `BusinessEvent` that does not structurally enforce the atomicity (CDM treats it as convention).*"

This example is *not* a non-faithfulness witness as stated; it is a *structural-property loss on the image of a single morphism*, not "two distinct morphisms collapse to the same image." A proper non-faithfulness witness would be: "transactions $\tau_1, \tau_2$ with *different* wallet-axis content but *same* per-trade economic content satisfy $F(\tau_1) = F(\tau_2)$ as CDM business events." This is in fact what §8.4.2's quotient construction *is* — and it is the right witness — but §8.4.1's example does not point at it.

**What must change.** Replace the §8.4.1 non-faithfulness example with: "*two ledger transactions $\tau_1, \tau_2$ that differ only in which `cpty_virtual` wallet receives the contra (e.g., booked against the original counterparty vs. a give-up cpty post-clearing) F-project to the same `BusinessEvent` because CDM's per-trade `TransferState` does not record the wallet axis — i.e., $\tau_1 \neq \tau_2$ in $\mathbf{Lg}$ but $F(\tau_1) = F(\tau_2)$ in $\mathbf{CDM}$.*" This is a 2-line edit.

The composition identity claim ($F(\tau_1 \circ \tau_2) = F(\tau_1) \circ F(\tau_2)$) is also *unproven*. For a non-trivial $F$ between non-trivial categories, this is a lemma, not a definition. Stating it without proof is fine *if* the reader is expected to verify — but a Round-3 reviewer with a TLA+ model will want at least an argument: "*F preserves composition because the CDM `BusinessEvent` chain composition is a pushforward of the L_13 transaction sequence: F maps L_13 atoms to BusinessEvent atoms and the chain operation commutes with the atom map by construction of L_13's append-only semantics.*" One paragraph; not in the proposal.

**Why MAJOR not BLOCKING.** The result (F is a lossy non-faithful functor; F restricted to $\mathbf{Lg}_{\text{econ}}$ is a homomorphism) is correct. The internal inconsistency is in *example choice* and *unproven lemma*, not in the result itself.

### R2-M1 — Monotonicity of `tx_status` projection unproven

**Severity.** MINOR (verifiable by TLA+ in PO-8; not gating).

**Defect.** §5.3 defines `tx_status` as a pure function over leg-state vectors; v2 states (correctly) that this dispenses with a separate transaction-level FSM. But *monotonicity of $\pi = \mathtt{tx\_status}$ along the per-leg FSM partial order* — i.e., if leg $L_1$ steps from $s_1$ to $s_1'$ with $s_1 \le s_1'$ in the lifecycle partial order, then $\pi(\vec{s}) \le \pi(\vec{s}')$ in the transaction-view partial order — is **not proven**. It is asserted to fall out of PO-8 (TLA+).

The function as written has at least one suspicious branch: the `Mixed` outcome. If a legal sequence of single-leg transitions can lead the projection from `PartiallySettled` (line 1: `if any state == PartiallySettled: return PartiallySettled`) to `Mixed` (last line) — for example, leg $A$: `PartiallySettled → Failed`, leg $B$: still `Pending` — then $\pi$ has stepped *downward* in any reasonable transaction-view partial order. This is the canonical *DvP-half-failed* pathology I flagged in R1 M1.

**What must change.** Either:

  (a) Add a Lemma 5.3.1: "*$\pi$ is monotone with respect to the product partial order on leg-state vectors and the named partial order on `TransactionView`*", define both partial orders, and prove monotonicity by case analysis. **OR**
  (b) Acknowledge that `Mixed` is a *break-detection sink* outside the normal lattice and explicitly remove it from the monotonicity claim: "*$\pi$ is monotone on the sub-domain $\{\vec{s} : \pi(\vec{s}) \neq \mathrm{Mixed}\}$; the transition to `Mixed` is detected as an operational anomaly and routed to `wf-confirm-break`.*"

Currently the proposal does (b) implicitly (the comment "Mixed = operational anomaly — break") but not explicitly as a *theorem statement*.

### R2-M2 — DS5 commutativity table is not a theorem

**Severity.** MINOR.

**Defect.** §6.5.5's table enumerates 8 signal pairs and flags 3 as non-commuting with "deterministic precedence." This is correct *for the cases enumerated* but is **not exhaustive**. The space of signal-pair multisets at `|signals| ≥ 3` is not addressed. The proposal says PO-8 (TLA+ at depth 8) verifies multiset replay — this is *verification on a finite model*, not *theorem proof*.

**Recommendation.** Either:

  (a) State a Lemma 6.5.5: "*For any multiset $M$ of signals satisfying the well-formedness condition (single $tx\_id$; single obligation; no contradiction in primary witness payload), $\mathrm{apply}(\sigma, \pi_1) = \mathrm{apply}(\sigma, \pi_2)$ for any permutations $\pi_1, \pi_2$ of $M$.*" — and prove by induction on $|M|$ using the pairwise table as the base case. **OR**
  (b) Acknowledge that DS5 is a *property verified by TLA+ to depth 8*, not a theorem, and update §11.A's status accordingly ("verified by model-check, not by proof; soundness pending PO-8 completion").

Either is acceptable; the current state — table presented as if it were the proof — is one rung below Bourbaki standard.

### R2-M5 — DS4 statement still excludes `Failed` from witness-required set

**Severity.** MAJOR for soundness; MINOR for fix complexity.

**Defect.** §11 DS4 reads:

  > $o.\text{state} \in \{\text{Discharged}, \text{PartiallySettled}, \text{Compensated}\} \Longrightarrow \exists \varepsilon : \mathrm{verify}(\varepsilon) \wedge \mathrm{matches}(\varepsilon, o.\text{discharge\_predicate})$

`Failed` is **omitted from the LHS** of the implication. This is unchanged from v1. §5.5 prose says the framework never marks `Failed` by inference, by clock, or by absence of evidence — but DS4 *as a formal invariant* admits a model where `Pending → Failed` happens without any envelope, *and DS4 is satisfied*.

**What must change.** Add `Failed` to the LHS:

  > $o.\text{state} \in \{\text{Discharged}, \text{PartiallySettled}, \text{Failed}, \text{Compensated}\} \Longrightarrow \exists \varepsilon : \mathrm{verify}(\varepsilon) \wedge \mathrm{matches}(\varepsilon, o.\text{discharge\_predicate-or-fail-predicate})$

with `discharge_predicate` extended to admit fail-witness predicates (sese.024 or counterparty-default declaration or silence_attestation per §4.5.3). The §5.5 narrative is then a derived consequence rather than an unenforced norm.

This is a **5-line edit** to §11 DS4. The closure of M-5 in §15.4 is otherwise overstated.

---

## 3. Specific Bourbaki rigour scrutiny (per request)

### B-1 (revisit) — Bijection Φ in §7.4

**Verdict: SKETCH, NOT PROOF.**

- **Carriers identified?** Yes — but asymmetric. $M$ is 4-tuple `(W, U, P, L_15)`; $C$ is 3-tuple `(W', U', P')`. `csd_virtual` membership in $W'$ unstated.
- **Morphism $\Phi$ defined?** Partially. Real-wallet/inherited-unit values defined; obligation-axis $u^\circ_o$ values defined for "holder" and "counterparty" with sign disjunction `(or -q depending on side)` — *the side disjunction is unspecified*; this ambiguity is a defect.
- **Inverse $\Phi^{-1}$ defined?** Implicitly via "reconstruct"; not formula-defined.
- **Identity-on-composition checked?** No.
- **Conservation preservation stated?** Yes (sketch line 1174); transport not proved.

**Bourbaki status: insufficient.** Promote sketch to proof; ~½ page work. Remove the side-disjunction ambiguity by fixing a sign convention.

### B-2 (revisit) — Conservation Lifting Theorem in §7.5

**Verdict: PROVED, MODULO ONE QUALIFIER.**

- **Hypotheses H1..H5 present?** Yes.
- **Hypothesis list complete?** Substantially yes. H1 (move balance) ✓; H2 (virtual sign correctness) ✓; H3 (state-only moves vacuous) ✓; H4 (wallet universe constancy) ✓ but with the qualifier that "new wallets enter at zero" is the *operational construction*, not strictly an *assumption* — the wallet creation move-pair is itself balanced by H1 with both endpoints at zero, so H4 is *derivable* from H1 + the WalletRegistry creation discipline. State H4 as: "*Every wallet entering $\mathcal{W}$ at any $t$ has zero balance at the moment of entry; equivalently, wallet-creation transactions are zero-move state-only transactions covered by H3*." This makes H4 derivable rather than independent.
- **Proof by induction on transaction kinds present?** Induction is on $|\Sigma_t|$ (transaction count), not "transaction kinds" as I phrased it in R1. Both are valid; induction on count is cleaner.

**Bourbaki status: acceptable.** ~1-line tightening of H4.

### B-3 (revisit) — DS1 time-domain bug

**Verdict: PARTIALLY FIXED, STILL CONTAINS A SELF-CONTRADICTION.**

- v1's "$[T, t_d^+] \cup [t_d^+, \infty)$" tautology: **fixed.** Quantifier is now $[T_{\text{exec}}(\tau), \infty)$.
- v1's "no projection $\Pi$ differs" universal quantifier: **NOT fixed.** §4.1.5 constructs named inflight projections that differ during $[T, t_d^-]$ by *design*. The DS1 universal still contradicts §4.1.5 as I flagged in R1.

**Bourbaki status: insufficient.** ~3-line edit to disambiguate primary projection from overlay projections.

### B-4 (revisit) — F as functor on $\mathbf{Lg}$ vs homomorphism on $\mathbf{Lg}_{\text{econ}}$

**Verdict: STRUCTURALLY CORRECT, ONE LOOSE EXAMPLE.**

- **Correctness of "F is functor + lossy + non-faithful"**: structurally right.
- **Functoriality identity $F(\tau_1 \circ \tau_2) = F(\tau_1) \circ F(\tau_2)$**: stated, unproven.
- **Quotient $\mathbf{Lg}_{\text{econ}}$**: defined; equivalence relation $\sim$ given correctly.
- **F restricted to quotient is a homomorphism**: stated.

**Defect:** §8.4.1's non-faithfulness example is structurally an *object-level loss* (CDM does not enforce atomicity), not a *morphism-collapse* witness. This is a *example correctness* issue, not a result correctness issue.

**Bourbaki status: acceptable with edit.** ~2-line example replacement; ~1-paragraph functoriality argument.

---

## 4. Pareto judgment

**Pareto NOT yet reached on rigour grounds. Two BLOCKING-for-Pareto items remain:**

1. **R2-B1.** §7.4 bijection Φ is sketched, not proved. Promote to full proof with named inverse $\Phi^{-1}$, identity-on-composition lemmas, conservation transport lemma. (~½ page.)
2. **R2-B3.** DS1 equivalent reformulation contains universal quantifier contradicted by §4.1.5's own construction. Disambiguate primary vs overlay projections. (~3 lines.)

**Two BLOCKING-for-cleanliness items (gate Pareto declaration but not Round 3 entry):**

3. **R2-B4.** §8.4.1 non-faithfulness example is structurally wrong; replace with a wallet-axis morphism-collapse example. (~2 lines.) Functoriality identity stated without proof; supply a paragraph argument. (~5 lines.)
4. **R2-M5.** §11 DS4 LHS still omits `Failed` from witness-required set; §5.5 narrative does not bind the formal invariant. (~5 lines.)

**Two MINOR rigour items (recommended but not gating):**

5. **R2-M1.** Lemma 5.3.1 (`tx_status` monotonicity) — either prove or scope to non-`Mixed` sub-domain.
6. **R2-M2.** DS5 commutativity — either prove the multiset-replay lemma or label the table as model-checked-not-proved.

**One TIGHTENING:**

7. **B-2 H4 qualifier.** ~1-line edit on the wallet-universe-constancy hypothesis.

**Total residual rigour debt to Pareto: ~1 page of edits across 4 sections.** None requires architectural change.

---

## 5. Architectural endorsement (unchanged from R1)

The mainstream design — three wallet classes (`real`, `cpty_virtual`, `csd_virtual`); per-leg `L_15.Obligation.state` as canonical FSM; transaction-level status as projection function; conservation over a constant universe $\mathcal{W}$; DvP-L/DvP-S/DvP-E disambiguated; per-counterparty per-(currency-or-ISIN) keying; $D_{\max} = 2$ for partial-fill cascades — is *operationally* and *categorically* sound. v2's structural decisions are not at issue. The remaining rigour debt is *local rigour* in named theorems, not *architectural rigour*.

The proposal's discipline in §15.2/§15.3/§15.4 closure tables — naming each R1 finding, citing its v2 fix location, summarising the fix in one line — is **exactly** the discipline a Bourbaki-grade specification document needs. I commend it. The defect I flag is that *closure-table-self-assessment* does not equal *external-reviewer-confirmed closure*: the team has marked Theme 12 (cartan B-1) and Theme 10 (cartan B-2) as "Closed" in §15.3 line 2106-2108. Theme 10 is closed (B-2 above); Theme 12 is *partially* closed (B-1 above). The R3 panel should not interpret §15.3 as a Pareto certification.

---

## 6. Recommendation for Round 2 disposition

**Verdict: ACCEPT_WITH_CHANGES.**

- **Round 3 entry: Yes.** The architecture is settled. The specification is implementation-near-ready.
- **Pareto declaration: Not yet.** Items R2-B1, R2-B3, R2-B4, R2-M5 must close before Pareto. ~1 page of editing across 4 sections.
- **Settlement Team work plan for the gap to Pareto:** half a day's editing by the doc lead; no architecture change; no new section.

**Closing remark.** v2 is closer to Bourbaki standard than any prior phase artefact in this project. The remaining gap is between *correct architecture stated with mostly-correct theorems* and *correct architecture stated with fully-correct theorems with explicit hypotheses, named inverses, and verified composition identities*. This is the gap between an excellent engineering specification and a permanent mathematical reference document. The team is one editing pass from crossing it.

I would not block Round 3 entry. I would block Pareto declaration on R2-B1 and R2-B3.

— cartan
