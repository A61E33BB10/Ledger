# Phase 3 Round 1 — CARTAN review of `proposal_v1.md`

**Reviewer.** CARTAN (Bourbaki rigour: definitions before use, theorems with explicit proof obligations, axiomatic completeness).
**Object.** `Ledger_Spec_v11.0/data/work/phase2/proposal_v1.md` (synthesis), with drilling into `phase2/{nazarov,formalis,correctness,jane_street}.md` where compressed claims are challenged.
**Stance.** Adversarial. The proposal calls itself a "synthesis"; my task is to test whether it satisfies the foundational hygiene of a *specification*. A taxonomy is not a specification; a list of leaf labels with prose descriptions is not an axiomatic foundation; a "compositional theorem" without explicitly stated and individually labelled hypotheses is not a theorem.

I find the proposal **substantively correct in direction** and **structurally inadequate as a foundation**. The integration is clear, the disagreements are honestly surfaced (§9 is exemplary), and the scaffolding for proof is in place — but every load-bearing definition, every theorem, every "law" is presented in compressed prose without the ground-floor axiomatic apparatus a Bourbaki-style document requires. The 5 compositional theorems of §8 are *theorem-shaped objects*, not theorems.

---

## A. Findings — BLOCKING

### B1. The proposal contains no formal definitions; only prose descriptions of leaves.

**Reference.** §3 (Per-leaf integrated specification); cf. NAZAROV §1.4.

**Rationale.** A definition (Bourbaki sense) introduces *exactly one* concept, names every free variable, fixes its ambient type, and states the predicates that constitute membership. The proposal's leaf entries (e.g., L1 ProductTerms, L8 UnitStatus, L13 CalibratedMarketObject) give a one-line *description* and then list specialist *properties*. Nowhere is there a sentence of the form

> **Definition.** Let `U` be a unit set, `T` a time set, `H` a hash family, and `K` a key registry. A *ProductTerms record* is a tuple `(u, v, π, t_k, a, σ)` such that …

What appears instead is a min-field list (`unit_id`, `product_type`, `terms_payload`, `version_seq`, `t_known`, `attestor`, `signature`) embedded in prose, with the ambient sets (`UnitId`, `Time`, `Attestor`, `Signature`) never specified. The reader cannot verify that subsequent invariants are well-typed because the types they range over are not declared.

This is the foundational gap. Until the 24 leaves have formal signatures (set-theoretic or type-theoretic), the per-leaf invariants in FORMALIS §2 are *expressions over undefined symbols*, and the "compositional theorems" of §8 quantify over universes that have not been constructed.

**Resolution required.** Phase 3 must produce, before convergence, a `§Definitions` section (or appendix) introducing, for each of the 24 leaves: (i) ambient sets/types of every component; (ii) the leaf's carrier as a refinement, sum, or product over those types; (iii) the well-formedness predicate. FORMALIS' invariants then become *theorems about these defined objects* rather than informal annotations.

---

### B2. The five compositional theorems (§8) are stated without complete hypothesis lists.

**Reference.** §8.1–§8.5; cf. FORMALIS §6 Theorems 1–5.

**Rationale.** Each "theorem" of §8 lists *some* hypotheses (D-CONS, E-ATOM, D-IDX for Theorem 1; D-DET, D-CODE, E-WF for Theorem 2; etc.) and a conclusion. None states the *universe* over which the conclusion is quantified, the *initial-state hypothesis* required for induction, the *finiteness/measurability hypotheses* required for the sums to be defined, or the *temporal model* (continuous time? discrete event time? Lamport order?) on which `≤` is interpreted.

Concretely, Theorem 1 (Conservation Lifting) concludes

> ∀ t ≥ 0, ∀ u ∈ 𝒰. Σ_{w ∈ 𝒲} balance(w, u, t) = Σ_{w ∈ 𝒲} balance(w, u, 0) + Σ_{e ∈ Σ_{[0,t]}, e.type = ISSUANCE} Δ_e^ext.

Hypotheses missing from the proposal:
- `𝒲` is finite at every t (otherwise the LHS sum may diverge);
- `Σ_{[0,t]}` is finite (otherwise the RHS sum may diverge);
- `balance` is well-defined as a projection from `Σ` and `𝒰` (this is *itself* Theorem 4, so Theorems 1 and 4 are mutually dependent — a circularity the proposal does not acknowledge);
- the initial state is conservation-consistent (the base case of the induction);
- handler emission is *total* (every event admitted by ingestion produces a complete `(moves, state_deltas, obligations)` triple, not just the conservation-zero subset).

Theorem 2 (Replay Determinism) concludes "Replay(t) = Original(t) bit-identically" but does not state what `Replay` is as a function, what its domain is (a workflow history? a snapshot id? a (history, snapshot, version-pin) triple?), or what equality on its codomain means (byte-equal? observationally equal modulo timestamps? equal up to the equivalence relation of Decimal canonical form?). The proof sketch handwaves "decomposition pass-by-pass"; in a Bourbaki text this is a lemma chain (L_1 → L_2 → ... → L_n) with each lemma proving determinism of one boundary, and the theorem composing them.

Theorem 3 (Obligation Liveness) is the most exposed: its conclusion is a `∀ t > t_d` claim, but the proposal acknowledges in §9.4 that this law is **unwitnessed** "over unbounded futures" with surrogate "bounded-horizon test + structural induction". A theorem whose conclusion the authors admit cannot be tested over its stated quantifier range is **not a theorem**; it is a *hypothesis* the system is *designed to satisfy*. The proposal must either (a) restate the conclusion with explicit horizon `T_max` and prove it for `t ∈ (t_d, T_max]`, or (b) classify L13 as an *axiom* of the realism budget rather than a theorem.

**Resolution required.** Each of Theorems 1–5 must be re-issued with: (i) all hypotheses individually numbered and stated; (ii) all quantifier ranges (universe, finiteness conditions) explicit; (iii) the initial-state / base-case / boundary-condition hypothesis explicit; (iv) the conclusion's equality predicate (bit-equal, decimal-equal, observational) precisely defined; (v) any circular dependency on another theorem made explicit and resolved by cut-elimination or simultaneous induction. Theorem 3 must additionally either bound its horizon or be reclassified.

---

### B3. The "consistency laws" L1–L14 (§4) include four laws labelled "unwitnessed" that are nonetheless treated as load-bearing.

**Reference.** §4 (table with "Witness?" column); §9.4; CORRECTNESS §1 L1, L4, L8, L13.

**Rationale.** A consistency law is, in formal terms, a closed sentence `φ` that the data layer is required to satisfy. If `φ` is *unwitnessed by any finite test suite*, then either (i) `φ` is decidable and finite witnessing means "we have not yet exhibited the witness" (in which case the obligation is to exhibit it), or (ii) `φ` is undecidable in the model under consideration (in which case calling it a "law" without a corresponding axiom is a category error — it is not a *consequence* of the system; it is a *postulate*), or (iii) `φ` quantifies over an infinite universe (unbounded futures, vendor opacity, cosmic-ray bit flips) for which no finite test can be conclusive (in which case, again, it is a postulate of the realism model, not a theorem).

The proposal blurs these three cases. L1 (lineage closure) under "vendor opacity" is undecidable because the vendor's internal state is not observable — it is a trust assumption (correctly named C-A3). L4 (bitemporal) over "unbounded restatement chains" is decidable for any *finite* restatement chain — the issue is *unbounded chains*, which are an architectural choice (retention horizon C-A10), not a mathematical impossibility. L8 (replay determinism) under "cosmic-ray bit flips" is decidable modulo a hardware-fault model (C-A1, C-A2). L13 (obligation liveness) over "unbounded futures" is decidable modulo a finite-horizon assumption.

In every case, the "surrogate strategy" the proposal sketches is the actual statement of the law: the law is `φ ∧ ψ` where `ψ` is the bound (retention horizon, threat model, time horizon). The unbounded `φ` alone is a postulate.

**Resolution required.** The four "unwitnessed" laws must be restated in the form `φ holds under hypothesis H`, where `H` is one of the named conditional assumptions C-A1–C-A10. Once so restated, they are theorems (witnessed by tests that verify `H` holds and that `φ` holds within the bounds H imposes). The proposal's current framing — calling them "laws" while admitting they cannot be witnessed — is a Bourbaki anti-pattern (the unmarked assumption: hypotheses appearing mid-proof not stated in the theorem).

---

## B. Findings — UNMITIGATED MAJOR

### M1. Notation collision: leaf identifiers `L1, ..., L16` (FORMALIS) and `L1, ..., L24` (NAZAROV/proposal) coexist with cross-cutting laws `L1, ..., L14` (CORRECTNESS) using the same prefix.

**Reference.** §2.3 leaf-count reconciliation table; §4 14-law table; FORMALIS §1 leaf list; CORRECTNESS §1.

**Rationale.** Three distinct numbering schemes share the prefix `L`. The proposal §3 uses `L1–L24` for NAZAROV's leaves; §4 uses `L1–L14` for cross-layer laws; FORMALIS §6 references "L9.T1", "L11.W1", "L12.C1" (FORMALIS' own leaf numbering, which is L1–L16, *not* NAZAROV's L1–L24). When the proposal cites "FORMALIS L9.T1" it means *FORMALIS' L9*, not *NAZAROV's L9 PositionState* (which is FORMALIS' L6). This is a Bourbaki anti-pattern (notation collision: same symbol with different meanings).

The proposal §3 attempts to harmonise but does not — entries cite FORMALIS by FORMALIS' own numbering ("Part of L8 (4T + 3W + 2C = 9 invariants for L8 RawObs/Oracle/Snap combined)" — FORMALIS' L8, not NAZAROV's L8 UnitStatus).

**Resolution required.** Adopt one canonical scheme. NAZAROV's `L1–L24` is canonical per §2.3. FORMALIS' invariants must be renumbered to NAZAROV's leaves (e.g., FORMALIS L9 → NAZAROV L13 CalibratedMarketObject), or the document must consistently prefix `LFM_*` for FORMALIS, `LCO_*` for CORRECTNESS, `LNZ_*` for NAZAROV. The current state is unnavigable to a careful reader.

### M2. The reduction "C1+C2+C3 → ℱ_Defn" (§2.1, attributed to GROTHENDIECK) is asserted without proof of functoriality.

**Reference.** §2.1, lines 79–83.

**Rationale.** The proposal claims a "forgetful functor" from the 6-class taxonomy to GROTHENDIECK's three sheaves: C1+C2+C3 → ℱ_Defn, C4 → ℱ_Obs, C5 → ℱ_Eff, with C6 as "morphism-recording layer". For this to be a functor in any serious sense, one needs: (i) the 6-class structure as a category (objects, morphisms, identity, composition); (ii) the three sheaves as a category; (iii) a map preserving identity and composition; (iv) the claim that this map is forgetful (i.e., not faithful, drops information). None of these are specified. C2 (UnitStatus, mutable) and C3 (PositionState, monotone-carrier) are operationally distinct from C1 (Definitions, append-only) — the proposal's own §1.3 emphasises this — yet the alleged functor collapses them. The collapse may be defensible, but it requires demonstration, not assertion.

**Resolution required.** Either (a) provide the categorical structure and prove (or cite GROTHENDIECK's `phase2/grothendieck.md` proof of) functoriality, or (b) downgrade the claim to "an analogy" / "a parallel" and remove the functor language. Currently the reader is asked to accept an act of mathematical vocabulary without its mathematical content.

### M3. The leaf-count reconciliation table (§2.3) asserts "no contradictions" without proving the alleged refinements are non-contradictory.

**Reference.** §2.3, lines 97–109; §9.7 ("Specialist contributions that did not integrate cleanly. None.").

**Rationale.** The table claims TEMPORAL's 31 leaves "refine, do not contradict" NAZAROV's 24; MINSKY's 41 are "consistent"; MATTHIAS' 62 are "non-contradictory"; FORMALIS' 16 *fold* L17–L22 into L13/L14 and the resolution is "adopt NAZAROV's 24". A refinement is non-contradictory iff there exists a function from the finer partition to the coarser one such that the coarser predicates are projections of the finer predicates. *No such function is exhibited* for any of the four reconciliations. The proposal asserts "every other count maps cleanly into [NAZAROV's 24] (or refines it consistently)" (§0 anchor 1) without demonstrating the maps.

In FORMALIS' case the situation is worse: FORMALIS *folds* what NAZAROV *splits* (L17 AttestationEnvelope, L18 IdentityKeys, L19 Snapshot, L20 IdempotencyToken, L21 VersionPin, L22 HashChainAnchor are folded into FORMALIS' L8 RawObs/Oracle/Snap and L14 WalletRegistry/Capability/KeyRegistry). This is not a refinement — it is a *coarsening* in one direction and a *refinement* in another. Whether NAZAROV's invariants on L17–L22 are preserved under FORMALIS' coarsening is not shown.

**Resolution required.** Exhibit, for each of the four specialist counts (TEMPORAL 31, MINSKY 41, MATTHIAS 62, FORMALIS 16), an explicit map to NAZAROV's 24 leaves, plus a verification that the predicates each specialist asserts on its partition are preserved (or equivalently re-stated) under the map. §9.7's "None" claim is unsupported until this is done.

### M4. The §9.2 reconciliations of jane-street vetoes V8/V9/V10/V11 against NAZAROV/FORMALIS/CORRECTNESS leaves are asserted without verification under the proposed structure.

**Reference.** §9.2; §1.2 V1–V14; §3.1 L5/L7 tensions; §3.6 L24 tension.

**Rationale.** The proposal explicitly admits (§9.2 closing paragraph): *"Phase 3 must validate that these reconciliations actually hold under the proposed structure. If any reconciliation collapses under adversarial review, the corresponding leaf must be deleted."* This is correct, but the proposal then calls itself converged on these points (§0 anchor 5). The reconciliations are claims, not derivations:

- V9 vs L7 ("L7 admitted as a thin sidecar, ≤30 fields"): no analysis shows that L7's content (firm currency, decimal precision, rounding mode, tolerance thresholds, accounting class map, capability schema, version pins) actually fits in ≤30 fields without each policy growing a hierarchy.
- V10 vs L5 ("L5 lives at the boundary, Ledger consumes but does not own"): the actual Ledger handler `ssi-ingest` (NAZAROV §1.4 L5) does write L5 records into Ledger storage at projection time, which is precisely "ownership" by another name.
- V11 vs L24: the claim that "no economic invariant references L24" contradicts CORRECTNESS L10 (Workflow-History Replay Coherence), which explicitly ties L24 to L14 and is listed as *witnessed* (i.e., tested in the economic test suite).

**Resolution required.** Each reconciliation must produce a checkable predicate (bound on field count for L7; explicit storage-vs-reference distinction for L5; explicit list of economic invariants and proof that none reference L24). Until then, V8–V11 stand as live tensions, not resolved ones.

### M5. The "minimum field set" lists in §3 are ambiguous about completeness.

**Reference.** §3 (every leaf entry's `**N**` line).

**Rationale.** Each leaf gives a "min fields" list (e.g., L1: `unit_id`, `product_type`, `terms_payload`, `version_seq`, `t_known`, `attestor`, `signature`). "Minimum" is undefined: minimum to satisfy *what*? The DQ bar? The CDM crosswalk? The FORMALIS invariants? The reader cannot determine whether a record with only these fields is well-formed or whether there are required fields not listed. (E.g., L1 lists `t_known` but not `t_obs`, despite §1.1 P4 requiring bitemporal indexing on every C1 leaf.)

**Resolution required.** Replace "min fields" with an explicit *signature* (total field list with types and optionality), with a clearly stated *well-formedness predicate*. If a "minimum sufficient subset" is intended, name what it is sufficient *for* (e.g., "minimum to satisfy N1–N12 + L21 version pinning").

### M6. §1.2 vetoes V1–V14 are stated as imperatives without truth conditions.

**Reference.** §1.2.

**Rationale.** A veto like V12 ("Free-text `metadata`, `attributes`, `extensions` — Closed schemas only") is enforceable; V7 ("Resist count creep; collapse on mutation discipline") is a slogan. V1 ("The 'tier' is a query lens, not three databases") is a design directive without a falsifying test. A specification permits the question "has this veto been violated?" to have an answer. Several V_i do not.

**Resolution required.** For each V_i, state the predicate over the structure of the data layer such that V_i is violated iff the predicate holds. V_i without such a predicate must be moved to a `§Design Maxims` section and removed from the normative spine.

---

## C. Findings — MINOR

### m1. The "realism budget" labels (U1–U8 unconditional, C-A1–C-A10 conditional) are introduced without a formal model of what "guaranteed" means.

**Reference.** §6.

A guarantee is, formally, a sentence of the form "for every execution of system S satisfying condition C, predicate P holds". Without a formal execution model the labels U1–U8 are incantations. *Minor* because the specialist files (FORMALIS §5 Determinism Postconditions, §6 Theorems) provide enough structure to formalise them; the proposal need only cite that structure rather than restate it informally.

### m2. The §4 14-law table column "Witness?" mixes "Witnessed (replay test)", "Witnessed", and "Witnessed (per-handler unit test)" without distinguishing the witnessing strength.

**Reference.** §4 table.

A property-based test is a different witness from a unit test is a different witness from a metamorphic test. The 10 "witnessed" laws are not equally witnessed. *Minor* because CORRECTNESS §4 (testing program) likely disambiguates; the proposal's table loses that information.

### m3. The proposal uses "if and only if" exactly once (§3.6 L23 implicit), "if" extensively, and never makes the if/only-if distinction explicit at the boundary contracts (e.g., when is a record *accepted*? when is it *rejected*?).

**Reference.** §3 throughout; cf. NAZAROV §2 N3, N7.

**Resolution.** Each ingress workflow's acceptance predicate should be stated as `record is accepted iff (clause 1 ∧ clause 2 ∧ ...)`. This is implicit in NAZAROV's bar but the proposal compresses it away.

### m4. §3 leaf entries cite specialists by single-letter handles (`N`, `M`, `T`, `R`, `F`, `C`) but the legend in §3 line 117 is easily missed, and `R` (MATTHIAS) clashes with the conventional `R` for "result" in PL contexts.

**Reference.** §3 line 117–123.

*Minor* but a Bourbaki text would either spell out the specialist on each line or reserve the single-letter handles for first-order objects (sets, types).

### m5. §3.5 L14 MoveStream's "F" line says "F: 4T + 5W + 2C = 11 invariants — the highest count, reflecting load-bearing role". Counting invariants as evidence of importance is a Goodhart trap.

**Reference.** §3.5 L14.

The number of invariants is a function of how finely they are decomposed, not of importance. *Minor* but a Bourbaki text would not write this sentence.

### m6. §7 strategic gap #1 ("Calibrated Market Data Layer is CDM-missing") is correctly identified but the fallback ("seed `cdm-valuation-lib` upstream proposal") is not a fallback — it is a hope.

**Reference.** §7 row 1; §9.3.

The proposal must specify the *Ledger-internal* representation that holds in the absence of CDM extension landing, with a migration path. §9.3 names the risk but does not commit to the internal representation. *Minor only because* the fallback ("Ledger-internal until CDM catches up") is conventional.

### m7. The §0 executive summary claim "every other count maps cleanly into [NAZAROV's 24] (or refines it consistently)" is the same claim as M3; restating it in the summary without proof reinforces the unsupported assertion.

**Reference.** §0 anchor 1.

*Minor* given M3 covers it.

### m8. The proposal cites itself as "the Phase 2 Synthesis Proposal" but the document is a *digest of seven specialist files*. A synthesis would resolve disagreements; this document admirably *surfaces* them (§9). The label "synthesis" is mildly aspirational.

*Minor*; consider relabelling "integration proposal" or "Phase 2 hand-off".

---

## D. Grade

**Grade: C+ (Major Revision Required).**

### Justification

A Bourbaki-style specification has four layers, each presupposing the previous: (1) ambient types and notation; (2) definitions; (3) elementary properties; (4) theorems with proofs. The proposal has layer 4 (compositional theorems §8) and a sketch of layer 3 (per-leaf invariants in FORMALIS §2, cited in proposal §3), but layers 1 and 2 are missing — the proposal reads as if the foundational definitions exist *somewhere* in the specialist files, but FORMALIS §0 explicitly disclaims foundational typography ("FORMALIS speaks as a Data Team author, not as the Phase 3 convergence arbiter"), MINSKY's parsed types are sketched, and NAZAROV's leaf catalogue gives prose descriptions, not signatures.

The proposal is **directionally correct**: NAZAROV's 24-leaf spine is plausible, the bitemporal axis is correctly mandatory, the MoveStream-as-canonical-record posture is sound, the realism budget separates unconditional from conditional guarantees in the right places, and §9's honest surfacing of unresolved tensions is the document's strongest feature.

The proposal is **foundationally unfinished**: there are no formal definitions, the theorems are theorem-shaped without complete hypothesis lists, four "laws" are admitted unwitnessed without being reclassified as postulates, and four jane-street vetoes are reconciled by assertion rather than verification. These are not finishing-touches; they are the foundation that the rest of the specification rests on.

A grade of **B** would require resolution of B1–B3 (the blocking findings). A grade of **A** would require additionally resolving M1–M6 (the unmitigated majors), at which point the document would constitute a defensible Phase 2 deliverable. The minor findings m1–m8 are minor precisely because they do not threaten foundational soundness.

---

## E. Closing remark

The proposal succeeds in what Phase 2 was scoped to do: integrate seven specialist views and surface the disagreements honestly. It does not succeed at being a *specification* in the Bourbaki sense, and it should not pretend to. Phase 3's job, on this reading, is to (a) construct the missing foundational layer (definitions, signatures, ambient model), (b) discharge the theorem-shaped obligations into theorems, and (c) reclassify what cannot be witnessed as postulates of the realism model. With those three steps done, the proposal becomes a foundation. Without them, it is an excellent Phase-2 hand-off whose load-bearing claims are deferred.

*Rigour is not the enemy of understanding; it is its foundation.*

— CARTAN
