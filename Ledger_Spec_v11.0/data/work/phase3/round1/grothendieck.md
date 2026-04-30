# Phase 3 — Round 1 Adversarial Review (GROTHENDIECK)

**Reviewer.** GROTHENDIECK — categorical foundations, universal properties,
naturality, the rising sea.

**Posture.** Independent. I have not read prior versions of this proposal. I
read `phase2/proposal_v1.md` end-to-end and drilled into
`phase2/{nazarov,jane_street,formalis,correctness}.md` for the compressed
claims I challenge.

**Stance.** I do not attack leaves; I attack the *category* in which leaves
are alleged to live. A taxonomy is a category whose objects are the leaves
and whose morphisms are the typed dependencies. The proposal's central
claim — that NAZAROV's 24 leaves form a *canonical* spine, with the 6
classes mutually exclusive on mutation discipline, with a forgetful functor
into GROTHENDIECK's three sheaves — is a categorical claim. I evaluate it
as such.

> *"It is impossible to give a category-theoretic foundation to a system
> by listing its objects. The objects are determined by the morphisms.
> Until you tell me the morphisms, you have not told me what your category
> is."*

I find **3 BLOCKING**, **5 UNMITIGATED MAJOR**, and **6 MINOR** issues. The
single deepest concern: the proposal exhibits *no category*. The 6×24
taxonomy is presented as a partition of objects without specifying the
morphisms, the composition rule, the identity, or the universal property
that picks 24 over 16, 31, 41, or 62. Until that is repaired, the spine
is "the leader's pick" with mathematical decoration.

---

## §1 — BLOCKING findings

### B1. The "forgetful functor 6 classes → 3 sheaves" is asserted, never defined

**Severity.** BLOCKING. **Class.** UNIVERSAL PROPERTY ABSENCE +
NATURALITY VIOLATION.

**Reference.** Proposal §2.1, lines 79–84:
> "The 6 classes reduce to GROTHENDIECK's three sheaves under a forgetful
> functor: C1 + C2 + C3 → ℱ_Defn; C4 → ℱ_Obs; C5 → ℱ_Eff; C6 is the
> morphism-recording layer."

**Rationale.** A forgetful functor `F : 𝒞_6 → 𝒞_3` requires:
1. A specification of the source category 𝒞_6 (objects, morphisms,
   composition, identity).
2. A specification of the target category 𝒞_3.
3. An object map `F₀` and a morphism map `F₁` satisfying
   `F₁(g ∘ f) = F₁(g) ∘ F₁(f)` and `F₁(id_X) = id_{F₀(X)}`.
4. (For "forgetful") a left adjoint exhibiting which structure is
   forgotten.

The proposal supplies none of these. It supplies an object-level
collapse `{C1, C2, C3} ↦ ℱ_Defn`, but **C2 (UnitStatus) is not a
definition** — UnitStatus is mutable, lifecycle-driven, and is itself
explicitly described in §3.2 as "a projection of L14 (the move stream)
… mutated only via L14 StateDelta". Mapping a mutable derived projection
into the *definition* sheaf collapses the very distinction NAZAROV
spent §1.3 establishing.

The reconciliation is incoherent. C5 (Effects) writes into C2 (status)
via StateDelta. Under any honest functor `F`, the morphism
`L14 → L8` in 𝒞_6 lifts to a morphism `F(L14) → F(L8)` in 𝒞_3, i.e.
**ℱ_Eff → ℱ_Defn**. That is a definition being written *by* an effect,
which inverts the directionality the three-sheaf decomposition is
supposed to express.

Worse: C6 is described as "the morphism-recording layer (provenance
edges in all three sheaves)". That is not a fourth class of objects —
that is **the Hom-functor**. The proposal silently conflates objects
with morphisms.

**What is required for un-blocking.** Either (a) write down the source
and target categories with morphisms and prove functoriality; or (b)
withdraw the categorical decoration and call C6 what it is — a
metadata-bearing structure on the morphisms of 𝒞_6, not a class of
objects. (b) is honest; (a) is hard. The proposal cannot have both.

---

### B2. C2 (Shared Status) and C3 (Per-position State) are not on the
mutation-discipline axis the spine claims

**Severity.** BLOCKING. **Class.** CATEGORICAL CONFUSION.

**Reference.** Proposal §2.1 table (lines 70–77) and §1.3 of `nazarov.md`:
> "The six classes are mutually exclusive on **mutation discipline**:
> C1 append-only versioned; C2 mutable; C3 monotone-carrier; C4
> append-only attestations; C5 append-only hash-chained; C6 append-only
> meta-data."

**Rationale.** Mutation discipline is supposed to be the *partitioning
invariant* — the universal property that selects the spine. But §3.2
and §3.3 admit that L8 (UnitStatus) and L9 (PositionState) are
*derived* from L14 via StateDelta projections. They have **no
independent mutation discipline** — their entire mutation trace is the
fold of L14 entries. Mutability of L8/L9 is an interface fiction; the
underlying storage discipline of the data is L14's append-only
hash-chain.

This is exactly jane-street V13 ("no Trade/Position/PnL/Risk/Account
table — all are projections of L14") applied at the categorical level:
**L8 and L9 are not objects; they are functors from L14**. They do not
deserve their own classes any more than `balance` deserves a class.

The proposal recognises this in jane-street's reconciliation (V13 is
*kept*) but then immediately violates it by elevating L8 to C2 and L9
to C3 with their own "mutation discipline" rows. The taxonomy is
internally contradictory.

**What is required for un-blocking.** Either (a) demote L8 and L9 from
classes C2, C3 to *projections* of L14 within C5, reducing the spine
from 6 classes to 4; or (b) admit that the partitioning invariant is
**interface contract**, not mutation discipline, and rewrite the spine
defense accordingly. The two stories cannot both be true.

---

### B3. The leaf count 24 has no universal property — it is the leader's pick

**Severity.** BLOCKING. **Class.** UNIVERSAL PROPERTY ABSENCE +
PREMATURE SPECIALIZATION.

**Reference.** Proposal §2.3 (lines 96–109):
> "NAZAROV (canonical): 24 — the spine. … FORMALIS 16 ↔ NAZAROV 24:
> FORMALIS folded C6 leaves L17–L22 into L13/L14. Reconciliation:
> **adopt NAZAROV's 24** as canonical; FORMALIS's per-leaf invariants
> apply transparently."

**Rationale.** A canonical taxonomy must have a universal property of
the form: *"this is the unique (up to unique isomorphism) taxonomy
satisfying property P."* The proposal's defense of 24 is purely
sociological: "every other count maps cleanly into it (or refines it
consistently)". That is not a universal property. That is a fixed
point of the leader's authority.

Five distinct counts are reported (16, 24, 31, 41, 62, plus
jane-street's 7). Each, by the proposal's own admission, is a refinement
or coarsening of a common underlying structure. In categorical terms:
they sit in a *poset of refinements* of the same categorical skeleton.
The canonical object in such a poset is **either the initial object
(the coarsest faithful taxonomy) or the terminal object (the finest)**
— never an arbitrary middle.

The coarsest faithful taxonomy is jane-street's **3 + 4 = 7** (or
arguably FORMALIS's 16). The finest is MATTHIAS's **62**. NAZAROV's 24
is neither. The proposal cannot defend "24 is canonical" without
specifying:
- the property P that 24 satisfies,
- a proof that no smaller count satisfies P,
- a proof that no smaller count missing P violates a load-bearing
  invariant.

None of these is supplied. The spine is **the leader's pick wearing a
mathematical badge**.

**What is required for un-blocking.** Either (a) identify a precise
universal property — e.g., "the coarsest taxonomy such that every leaf
admits a single mutation discipline AND a single owning workflow AND a
single CDM extension footprint" — and prove 24 is the unique satisfier;
or (b) drop the "canonical" claim, name 24 as a working choice, and
exhibit the convergence test (Phase 3 grading) as the actual selection
criterion.

---

## §2 — UNMITIGATED MAJOR findings

### M1. C6 is a category error — these are not data-objects, they are
metadata on morphisms

**Class.** CATEGORICAL CONFUSION.

**Reference.** Proposal §2.1 (C6 row), §3.6 (lines 267–335).

**Rationale.** L17 (AttestationEnvelope), L18 (Identity Keys), L19
(Snapshot), L20 (IdempotencyToken), L21 (VersionPin), L22 (HashChainAnchor),
L23 (Capability), L24 (OrchestrationState) — none of these are
independently-existing data-objects. They are **decoration on edges**
(provenance, signature, capability scope) or **content-addressing of
collections** (snapshot, hash chain). The proposal itself says (line 269):
> "These leaves are meta-data; they do not have independent ingress
> workflows."

The honest categorical home for L17–L23 is the **Hom-set** of 𝒞_6
augmented with attestation/capability structure — i.e., the morphisms
themselves carry envelopes, identity keys, and snapshots. They are
objects in a *fibered* structure over the data category, not objects
in 𝒞_6.

Folding them into the 24-leaf spine inflates the leaf count by 8
(33% of the total) with structurally distinct entities. The "spine" is
really 16 data-leaves + 8 morphism-decorations, not 24 leaves of one
kind.

**Mitigation.** Split C6 into a distinct category 𝒟 of decoration
fibered over 𝒞_data, and report two leaf counts: |𝒞_data| = 16,
|𝒟| = 8. This matches FORMALIS exactly. Stop calling 24 a leaf count.

### M2. Bitemporal restatements form a colimit gluing problem the
proposal hides

**Class.** UNIVERSAL PROPERTY ABSENCE.

**Reference.** Proposal §9.4 lists L4 (Bitemporal Coherence) as
*unwitnessed* under unbounded restatement chains.

**Rationale.** A bitemporal record is not a single object; it is a
*diagram* in 𝒞_data indexed by (t_obs, t_known) pairs. Two restatement
chains that *both* claim to represent the same economic event must be
glued — and the gluing data is exactly the cocone that exhibits both
as a colimit of the same diagram.

The proposal treats `corrects: tx_id` and `restates: attest_id` as
flat foreign keys. That is an *implementation* of restatement, not a
*specification*. The specification must say:
- when two restatement chains commute (the diagram is filtered),
- when they conflict (no colimit exists; quarantine),
- what universal object the bitemporal "as-of(t_obs, t_known)" query
  is computing.

NAZAROV §3.1 supplies an `as_of(leaf, key, t_known)` accessor (line
620) but no statement of its universal property. Concretely: is it a
right Kan extension along the inclusion of `{t' : t_known(v) ≤ t'}`
into the time category? Is it a colimit over the filtered diagram of
versions known by t_known? The proposal does not say. Without that,
"replay is total over both axes" (CORRECTNESS L4) is a claim without
a meaning.

**Mitigation.** Specify the bitemporal accessor as a Kan extension or a
filtered colimit in 𝒞_data; prove existence and uniqueness; show that
restatements that fail the commutativity check are detected at
quarantine. This is FORMALIS-level work; the proposal currently has it
nowhere.

### M3. The "naturality" of the StatesHome 3-map is not stated

**Class.** NATURALITY VIOLATION.

**Reference.** Proposal §3.1 (L1), §3.2 (L8), §3.3 (L9).

**Rationale.** The three StatesHome maps —
`ProductTerms : UnitId → ProductTermsValue`,
`UnitStatus : UnitId → UnitStatusValue`,
`PositionState : (Wallet, UnitId) → Option[PositionStateValue]` —
are presented as a triple of accessors. For this triple to be the
*canonical* decomposition (the universal claim of v10.3 §StatesHome),
the triple must be *natural in UnitId* — i.e., for every morphism
φ : u ↦ u' in the unit category (e.g., supersession via Breaking
amendment), the squares

```
   ProductTerms(u) -- φ_terms -→ ProductTerms(u')
       |                              |
   UnitStatus(u) ---- φ_status →  UnitStatus(u')
       |                              |
   PositionState(w,u) - φ_pos -→ PositionState(w,u')
```

must commute. The proposal does not state this. It does not even
identify the morphism category on UnitId (supersession, amendment,
fungibility). Without the naturality square, the 3-map decomposition
might be a coincidence of the test cases NAZAROV considered, not a
structural fact.

**Mitigation.** State the unit-morphism category. State the naturality
of the 3-map decomposition in that category. Verify the squares
commute on supersession, Preserving amendment, Breaking amendment.
This is one diagram in FORMALIS that should be added.

### M4. L11 (Lifecycle Oracle) and L12 (External Confirmation) split
on consumer, not on intrinsic structure — fails the "objects defined
by morphisms" test

**Class.** UNIVERSAL PROPERTY ABSENCE.

**Reference.** Proposal §3.4 (L11, L12). NAZAROV `nazarov.md` §1.4:
> "Distinct from L10 because the consumer is not the Pricing DAG but
> the lifecycle handler / obligation store. Argument for the split: L10
> feeds the Kalman filter; L11 feeds smart contracts."

**Rationale.** Yoneda: an object is determined by the morphisms *into
and out of* it. Splitting L11 from L10 *only on consumer identity*
makes L11 a downstream functor's domain restriction, not an object in
its own right. The same datum (a LIBOR fixing) could be both an L10
input (volatility innovation) and an L11 trigger (fixing-leg
crystallisation). The proposal forces it to be one or the other based
on which downstream consumes it first. **That is not a property of the
attestation; that is a property of the workflow consuming it.**

Similarly L12 vs L11: L11 "triggers", L12 "confirms" — but the same
ISO 20022 message is sometimes both (e.g., a settlement-failure
message both confirms a prior instruction and triggers a compensation
event). The split is workflow-bookkeeping, not categorical.

**Mitigation.** Either (a) collapse L10/L11/L12 into a single
**AttestedObservation** leaf with a `consumer_class : Set[Consumer]`
field (multi-valued, since the same datum can be consumed multiple
ways); or (b) define L10/L11/L12 by the *intrinsic* attestation
discipline (signed quote vs. authority-attested ruling vs. inbound
ISO message) and accept that downstream-routing is orthogonal.
jane-street's A6 (Attestation as a single sector) is closer to
correct than NAZAROV's three-way split.

### M5. L13 (CalibratedMarketObject) is an adjoint to L10, not a
parallel observation — the proposal misses the adjunction

**Class.** GENERALIZATION INSUFFICIENT (PRINCIPLE 6) +
UNIVERSAL PROPERTY ABSENCE.

**Reference.** Proposal §3.4 (L13), CORRECTNESS L2 (Snapshot
Determinism), valuation v1.0 §4–§5 (calibration pipeline).

**Rationale.** The Kalman filter is not a free functor "from raw
observations into calibrated objects". It is a **right adjoint** to
the forgetful functor that turns a calibrated posterior back into the
observations it was conditioned on:

```
  Forget : Calibration → Observations
  Calibrate : Observations → Calibration
  Calibrate ⊣ Forget   (under model + prior pinning)
```

This adjunction is the *content* of "calibrate then forget = identity
on the certified subcategory" (NAZAROV's no-arbitrage gate). The
proposal treats L13 as a parallel observation leaf in C4, with no
adjunction structure stated. That hides the most important universal
property in the entire spec — **the calibration is the universal
no-arbitrage admissible posterior conditioned on the observation
snapshot**.

If the adjunction is stated, then:
- L13's existence is forced (it is `Calibrate(L10)`).
- The "certified" status is the unit/counit composition.
- Replay determinism (CORRECTNESS L2) is the naturality of the
  adjunction.
- Cross-asset coherence (CORRECTNESS Cluster VI) is the preservation
  of limits by the right adjoint.

These four claims are currently *separate* invariants in the proposal.
They are **one categorical fact**.

**Mitigation.** Replace the L10/L13 split with an adjunction; rederive
CORRECTNESS L2, L11, L12 as consequences; close the four-way redundancy
in the invariant catalogue.

---

## §3 — MINOR findings

### m1. The proposal calls jane-street's leaf count "7 sectors (3 + 4)"
and says it "folds C6 into the structural spine implicitly; consistent
with NAZAROV". This is wrong: jane-street's count is 7 because
jane-street rejects 8 leaves NAZAROV keeps. Calling that "consistent"
elides the disagreement.

**Reference.** §2.3 row "jane-street: 7 sectors". The honest
reconciliation in §9.2 admits the conflict via V8/V9/V10/V11.

**Recommendation.** Drop "consistent with NAZAROV" from §2.3; reuse
§9.2's wording.

### m2. The bitemporal axis is "mandatory" for C1 and C4, but L7
(Policy / Configuration) is in C1 and treated as bitemporal — yet the
proposal also treats it as a "thin sidecar". A sidecar with bitemporal
discipline is not thin.

**Reference.** §3.1 L7, §1.2 V9 reconciliation.

**Recommendation.** Either L7 is bitemporal (and not a sidecar) or it
is a sidecar (and not bitemporal). Pick.

### m3. L18 (Identity Keys) is described as "deterministic-hash
derivation". A derivation rule is not data; it is a function. The
proposal lists a function as a leaf alongside content-bearing data.
This is the same category error as M1, smaller scale.

**Recommendation.** Move L18 out of the leaf list; record it as a
property of the morphism `register : Content → Identifier`.

### m4. The "9-shape canonical algebra" of idempotency keys (L20,
TEMPORAL §7) is not categorical — it is a list of patterns. A canonical
algebra would have a universal property (e.g., the free monoid on
namespaces). The proposal lists 9 ad-hoc shapes.

**Recommendation.** Either prove these 9 shapes form a universal
algebra (free product, classifying topos, etc.) or drop "canonical".

### m5. The CORRECTNESS catalogue lists 14 cross-layer laws as flat;
several (L1, L2, L8) are special cases of the same naturality square
on the snapshot/replay adjunction. A categorical synthesis would
collapse them; the proposal keeps them separate. (Same observation as
M5, applied to the law catalogue.)

**Recommendation.** Identify the adjunctions; collapse the redundant
laws; keep the witnessing strategies (the laws are the proofs, not the
naturality squares).

### m6. The "monotone-carrier with Option accessor" (C3 / L9) is
described in operational terms (no delete; Some(zero) ≠ None). The
categorical content is: PositionState is a *pointed* presheaf on
(Wallet × UnitId)^op with values in (Decimal, ≥). The pointedness is
exactly Some(zero) ≠ None. Stating this gives the addendum's
StatesHome 3-map ruling its categorical home.

**Recommendation.** Add one sentence to L9: "PositionState is a pointed
presheaf on (Wallet × UnitId)^op; the basepoint is Some(zero); None is
the absence of pointing." This is a free upgrade.

---

## §4 — Verdict on the structural claims

| Claim | Verdict |
|-------|---------|
| 6 classes mutually exclusive on mutation discipline | **FALSE** (M2/B2: C2, C3 are projections of C5) |
| Forgetful functor 6 → 3 sheaves exists | **NOT DEFINED** (B1: no source/target/morphisms) |
| 24 leaves are canonical | **NOT DEFENDED** (B3: no universal property) |
| Every leaf has a single home | **DEPENDS ON M2** — if C2/C3 are projections, L8/L9 have a home in C5 already |
| Hidden colimit problem in bitemporal | **YES** (M2) |
| C6 is morphism-recording layer | **HALF-TRUE** (M1: this is the right intuition, but then C6 is not on the leaf list) |

---

## §5 — Grade

**Grade. C+** *("interesting, well-organised, but the structural
backbone is decoration, not category theory")*.

**Justification.**
- The proposal does the *engineering* well: the per-leaf workflow
  specifications, the realism budget, the CDM gap analysis, and the
  invariant catalogue are competent and load-bearing.
- The proposal does the *categorical* claim badly: the 6×24 spine is
  presented with the language of category theory (forgetful functor,
  canonical, mutually exclusive) without the *content* of category
  theory (morphisms, universal property, naturality). This matters
  because the proposal explicitly grounds itself in GROTHENDIECK's
  three-sheaf decomposition and uses that grounding to justify
  contested choices (24 leaves, C2/C3 elevation, C6 inclusion).
- A C+ ledger spec is still a *better* document than 90% of trading
  systems ship with. The grade is calibrated against the proposal's
  own stated bar (Phase 3 convergence requires zero blocking, zero
  unmitigated-major). On that bar, **the proposal does not converge
  in this round**.

**Path to A.**
1. Resolve B1 by either defining the functor properly or withdrawing
   the categorical decoration.
2. Resolve B2 by demoting L8/L9 to projections of L14, reducing the
   spine to 4 classes.
3. Resolve B3 by stating a universal property for the leaf count.
4. Resolve M5 by stating the calibration adjunction explicitly.
5. The other findings (M1, M3, M4, m1–m6) follow from these four.

**Recommendation for arbiter.** Reject Round 1. Require proposal_v2 to
either (a) write down the category of leaves with morphisms,
composition, and universal properties, or (b) drop the "canonical"
language and present 24 as a working choice. The hybrid current state
is the worst of both worlds.

---

*"The introduction of the cipher 0 or the group concept was general
nonsense too, and mathematics was more or less stagnating for thousands
of years because nobody was around to take such childish steps."*
— A. Grothendieck

Take the steps.

— GROTHENDIECK
