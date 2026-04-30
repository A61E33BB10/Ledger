# Phase 3 Round 1 — FEYNMAN adversarial review of `proposal_v1.md`

**Reviewer.** FEYNMAN (independent, no Phase-1/Phase-2 prior context).
**Discipline.** First principles; multiple independent representations; honest validation.
**Mode.** Adversarial. The aim is to break this proposal, not to confirm it.

> *"What I cannot create, I do not understand."*
> *"The first principle is that you must not fool yourself — and you are the easiest person to fool."*

I read `proposal_v1.md` end-to-end and drilled into `correctness.md` (laws + boundaries + faults), `formalis.md` (per-leaf invariants), `nazarov.md` (taxonomy), `jane_street.md` (vetoes), and `temporal.md` (workflow shapes) where compressed claims are load-bearing. Findings below.

The headline answer to the four questions in the brief:

1. **Could I build a working data layer from the proposal alone?**  No. There are at least eight gaps where I would have to invent something — and one of those (snapshot canonicalisation) is the determinism boundary, so my invention would silently break replay against any other implementer's invention. I list each gap as BLOCKING-G* below.
2. **For each leaf, is there a second way to compute the same thing?**  Partial. The proposal asserts "L8 UnitStatus and L9 PositionState are projections of L14 MoveStream" (§0 anchor 2). That is the canonical second representation. But the *fold function itself* is nowhere stated, and the proposal never asserts that it must be defined per-leaf. Without that fold, the cross-check is rhetorical. Detail in BLOCKING-F1.
3. **Are the cross-layer laws testable in two independent ways?**  Some yes (L2 replay; L9 forgetful functor; L11 metamorphic relations) — for these, the proposal already names two angles. Some no (L1 lineage; L4 bitemporal; L8 master determinism; L13 obligation liveness — the four laws CORRECTNESS itself flags as unwitnessed). The proposal proposes "surrogates" but never defines what makes a surrogate *equivalent* to a witness. Detail in BLOCKING-X1.
4. **Where does the proposal substitute jargon for understanding?**  Three serious places: "realism budget" (the C-A* assumptions are treated as labels, not as decidable failure conditions); "thin sidecar" (used as a reconciliation device for V8/V9/V10/V11 with no quantitative meaning); and "monotone-carrier with Option accessor" (the *operational* distinction between `None` and `Some(zero)` is asserted but never given a behavioural test). Detail in MAJOR-J1, MAJOR-J2, MAJOR-J3.

---

## §A — BLOCKING findings

A blocking finding means: I would refuse to start an implementation against this proposal in its current form because the resulting code would either not compile, not run identically across two implementations, or pass tests while being wrong.

### BLOCKING-G1 — `canonical_serialise` is undefined and load-bearing

The proposal makes content-addressing structural in at least nine places: `unit_id = hash(canonical(terms_blob))` (jane-street P3), `snap_id = hash(canonical_serialise(payload_set))` (L19), `tx_id` derivation (L18), `attest_id`, `agreement.document_hash` (FORMALIS L3 T2), the hash-chain `prev_hash` (L22), the `(observable_id, source, t_observed, t_known)` snapshot key (TEMPORAL §3.1), the `obligation_id`, and the idempotency token namespace prefixes (L20).

**Nowhere is `canonical_serialise` specified.** Two implementations choosing different canonical forms (key ordering, integer width, decimal normalisation, Unicode normal form, line endings, set vs list ordering, `null` handling, default-value omission, signature inclusion-or-exclusion) will produce different hashes for the same logical payload. Every cross-implementation verifier — including the multi-replica determinism check that L8 (master) relies on — will then disagree forever, with no diagnostic better than "the hashes don't match".

CORRECTNESS B10 names "Hash algorithm / canonicalisation" as a determinism boundary captured by "Algorithm-stable canonicalization rule" but does not specify the rule. FORMALIS L8 T4 says `integrity_hash = SHA256(canonical(observations))` — same word, no definition.

This is not a polishing item; it is the foundation of U3, U4, U5, U8 simultaneously. **Required fix:** name a specific canonicalisation (e.g., RFC 8785 JCS, or Protobuf canonical encoding with explicit field-tag ordering, or a CBOR profile per RFC 8949 §4.2.1, with explicit handling of decimals, signatures, and elided defaults) and pin it with a `canonicalisation_version` enum that participates in `L21 VersionPin`. Then state which leaves are bound to which canonicalisation. **Until this is resolved, every replay claim in the proposal is rhetorical.**

### BLOCKING-G2 — The fold function from L14 to L8/L9 is nowhere defined

§0 anchor 2 declares: *"L8 UnitStatus and L9 PositionState are projections of L14 MoveStream. Wallet balances, P&L, and the balance sheet are derived views, never independently stored."*  Jane-street P8 says *"the proposal must name, for every non-canonical record, the deterministic fold function that reconstructs it. If there is no such function, the record is canonical."*

The proposal does not name the fold. It does not say which leaves of L8 / L9 are folds of which subset of L14, in which order, with which initial state, with which conflict-resolution rule. FORMALIS §6 Theorem 4 ("Substantiation: the balance-sheet IS the ledger") is asserted with the structure *"L14 hash-chained move stream + L18 deterministic identity + multi-replica verification compose to substantiation"* but there is no fold there either.

Without the fold I cannot:
- write the cache-invalidation rule when a `corrects` move is appended;
- write the test that compares stored L8/L9 against `fold(L14_prefix)`;
- bound the cost of replay (is it O(N) over all moves, or O(N_u) over the unit's moves?);
- decide whether the L8 single-writer constraint is *enforced* by the fold (it could be encoded as a writer-tag in the move) or *enforced separately* (and therefore at risk of inconsistency).

**Required fix:** for L8 and L9, name the fold as a typed function, name its initial state, name the writer-tag schema on each move, and state the law `read(L8|L9, key, t) == fold(L14[≤t], key, init)` as a witnessed property test. Without this, the "second representation" claim is empty.

### BLOCKING-G3 — `idempotency_key` definitions are inconsistent across leaves

Per the brief (Principle 2), identical content should yield identical identity. The proposal's idempotency keys do not all obey this:

- L1 ProductTerms: `idempotency_key = hash(unit_id, version_seq)` — depends on the *new* `version_seq`, which the producer supplies. Two producers concurrently submitting the same amendment will produce different `version_seq`s and therefore different keys. Idempotency fails.
- L10 RawObservation: `hash(topic, t_obs, source, value)` — but value is a Decimal; how is `1.0000` vs `1` vs `1e0` resolved? See BLOCKING-G1.
- L13 CalibratedMarketObject: `(calibrated_object_id, certification_timestamp, model_id)` — `certification_timestamp` is wall-clock at certification time, so two replays will produce different keys. This *cannot* be content-addressed by construction.
- L14: `tx_id` "derived from canonical content" — content includes signature? signer's wall clock? executor commit timestamp?
- L20 names "9 shapes" of idempotency token but does not state which shapes are content-addressed and which are not. The mixture is itself the bug.

**Required fix:** for each leaf, classify the key as either **content-addressed** (deterministic from logical content) or **mint-on-arrival** (provenance-bearing, non-deterministic, gates on prior-mint check). State which laws (L8 replay; U3 deterministic identity) tolerate which class. Right now the proposal claims U3 across all of C6 but L13 plainly violates it.

### BLOCKING-G4 — Bitemporal axes are named but not arithmetic

P4 (jane-street) says "bitemporal where the world restates"; FORMALIS L8 T1 says `vendor_timestamp ≤ knowledge_timestamp`; CORRECTNESS L4 says "vendor_time ≤ knowledge_time; replay is total over both axes". This is necessary but woefully insufficient.

Open questions an implementer must invent:
- What is the resolution of each axis? (microsecond? nanosecond? per-source? CORRECTNESS L4 gives no answer.)
- What time zone? (FpML / ISO 20022 typically use UTC + offset; the proposal does not pin this.)
- Are the timestamps **continuous** or **discrete tick counts**? Continuous breaks `==` testing across implementations; discrete needs an epoch and tick.
- How do you query `read(id, as_of_knowledge=t_k, as_of_vendor=t_v)` when *both* are equal to a tie-broken instant of multiple restatements within one knowledge tick? The proposal gives no tie-breaker.
- How is a vendor restatement of a prior `t_obs` distinguished from a new observation at a later `t_obs`? Answer: the message must carry a `restate_link` (TEMPORAL §3.10 mentions this for fixings only). Bitemporal coherence as a *system property* requires every C1/C4 leaf to have it. The proposal does not state that.

**Required fix:** specify a `Bitemporal<T>` type with concrete axis types, tie-breakers, restate-link discipline, and a query API. Then re-derive L4 (Bitemporal Coherence) as a witnessed property test of that API.

### BLOCKING-G5 — The L8 master determinism law's "witness" relies on a property that is not itself testable

CORRECTNESS L8 says: *"Re-executing the same handler against the same pinned inputs produces a `pending_tx` T' with `tx_id(T') == tx_id(T)` and bit-identical moves and state deltas. Witnessing: replay every committed transaction; assert bit-identical re-emission. Decidable."*

This is decidable **only if `tx_id` is a function of the bytes**, and the bytes are produced by a `canonical_serialise` (BLOCKING-G1) — *and* the handler does not consume any of B1–B12 boundaries unmediated. The proposal lists 12 such boundaries; for each, the boundary capture is nominally specified, but two are inadequate:

- B7 (calibration filter state): "produces bit-identical posterior under Decimal arithmetic; Mahalanobis-zero within MC tolerance otherwise". The "otherwise" branch is not bit-identical and therefore breaks `tx_id == tx_id`. If `tx_id` depends on a price computed downstream of an MC pricer, the master law fails. The proposal does not say which leaves *can* depend on MC outputs and which cannot.
- B11 (operator/human): "the captured attestation is replayed; the human's uncaptured deliberation is not." Fine — but if the *hash of the attestation envelope* depends on a captured wall clock that the human supplied (governance approval timestamp), the canonicalisation must define how that field participates. See BLOCKING-G1.

**Required fix:** state, per leaf, whether its hash-input includes any field downstream of an MC pricer or a human signer's wall clock. If yes, the leaf cannot satisfy U3/L8 in their strong form and the surrogate must be named (e.g., "`tx_id` includes only the pricer's `model_id` and `seed`, not the floating-point output").

### BLOCKING-G6 — Multi-replica verification is named but not specified

FORMALIS Theorem 4 invokes "multi-replica verification" as a constituent of the substantiation theorem. The proposal mentions it again in §9.4 as a surrogate for L8 under cosmic-ray bit flips ("content-addressing + erasure coding + cross-replica verification"). Nowhere is the protocol stated:

- How many replicas? Two? `2f+1` Byzantine? `3f+1`?
- What is the agreement primitive? Quorum read? Atomic broadcast? Gossip + reconciliation?
- What happens on disagreement? Halt? Majority wins? Quarantine?
- Is the verification synchronous (read-time) or asynchronous (audit pass)?

This is not fastidious detail — replica disagreement *is* the cosmic-ray surrogate that FORMALIS leans on. If unspecified, the surrogate has no operational meaning and L8 collapses to "we content-addressed it; trust the storage".

**Required fix:** name the replication and verification protocol, state its assumptions (synchrony / failure model), and bind it to a witnessed property.

### BLOCKING-G7 — The "writer-tag" / "writer-cap phantom" mechanism for L8 / L9 single-writer-per-field is asserted but its enforcement path is ambiguous

FORMALIS L5 W1 and L6 W1 state single-writer-per-field "type-level via phantom-typed writer capability; runtime cross-check at executor commit". MINSKY §4 says "field-level writer-cap phantom types". V13 (jane-street) says no separate Position/PnL/Account table. P7 says illegal states unrepresentable.

But the proposal never makes one critical choice: **does the writer-tag live on the move (i.e., the move says "I am a fee-handler write to `accrued_perf_fee`"), or on the field (i.e., the schema says "field `accrued_perf_fee` accepts only writes from handler X")?** These are different enforcement architectures with different failure modes:

- On the move → enforced at fold time → a malformed move is silently absorbed if the fold function is wrong (BLOCKING-G2 again).
- On the field → enforced at write time → moves are conservative on emission but the fold has no information about who wrote what.
- Both → redundant but defensible if the cross-check is itself a witnessed law.

**Required fix:** state the architecture and bind it to one of CORRECTNESS L5/L6/L7. Right now CORRECTNESS L5 cites "structural enforcement if C11 single-writer-per-field is enforced" — *if* is doing too much work.

### BLOCKING-G8 — The proposal contains a circular dependency between L7 (Policy) and L21 (Version Pin) that nothing breaks

L7 holds tolerance thresholds, rounding modes, accounting classifications, **and the version-pinning policy**. L21 records the pinned versions, *including the `cdm_version`, `model_version`, and L7's own version*. So L21's content is governed by L7, and L7's version is recorded in L21. Now: which one do you read at boundary time? If you read L7 to know which L21 you trust, you have to know which L7. If you read L21 to know which L7 you trust, you have to know which L21.

In practice this is solvable (the bootstrap policy is a single hard-coded `L7@genesis` plus an L22 anchor), but the proposal does not state the bootstrap, does not name the chicken-and-egg solver, and CORRECTNESS L8 quietly assumes both are pinned. This will become a real bug at the first L7 schema change.

**Required fix:** state the bootstrap. Make `L7@genesis` an entry in L22 (the hash-chain anchor), and make every later L7 update a transaction in L14. This collapses the loop into the standard chained-update pattern.

---

## §B — UNMITIGATED MAJOR findings

A major finding is one I would refuse to ship without resolving, but where I can imagine an implementation pushing forward and discovering the issue mid-build rather than failing at start.

### MAJOR-J1 — "Realism budget" treats failure conditions as labels, not as decidable predicates

§6 distinguishes 8 unconditional U-guarantees from 10 conditional C-A* assumptions. Each C-A* has a name, scope, owner, "violation consequence", and "detection signal". This is good organisationally but reads like a status board, not an engineering input. For an implementer to build a data layer:

- C-A1 (cryptographic primitive soundness) — what is the *test* I run today to convince myself C-A1 holds? The conventional answer is "use vetted primitives + key rotation", but the proposal does not say that and does not bind it to a property in the test catalogue.
- C-A3 (vendor honesty) — "per attested vendor". Per-vendor what? Trust score? Cryptographic anchor? A multi-source consensus rule? CORRECTNESS L1 *names* "trust-assumption registry + threat model + multi-source consensus" but does not define the registry schema or the consensus rule.
- C-A6 (calibration model soundness) — owned by "Model-validation team". What is the artifact they sign? The proposal does not say. Is it `(model_id, model_version, certificate)` ? See BLOCKING-G3 — without an answer, L11 is rhetorical.
- C-A9 (workflow-history determinism) — "TEMPORAL" is an owner *and* a tool *and* a person. The proposal does not name what TEMPORAL hands to the data layer. (TEMPORAL itself in `temporal.md` §6 is honest about six awkward fits.)

**Required fix:** for each C-A*, name (a) the artefact that the owner produces, (b) the schema of that artefact (is it a row in L7? a signed envelope? a pin?), (c) the property test that verifies it. Until then "realism budget" is a presentation device, not a contract.

### MAJOR-J2 — "Thin sidecar" is the load-bearing reconciliation of four jane-street vetoes against four NAZAROV leaves, and it has no quantitative meaning

§9.2 reconciles V8/V9/V10/V11 against L7/L5/L24 by declaring the leaves "thin sidecar" or "boundary contract level only". The L7 reconciliation says "the realism budget is 'small sidecar, not a parallel data spine'... the veto is honoured by refusing to let L7 grow beyond ~30 fields." 30 fields is not derivable from anything in the proposal; it is a number from prose.

This matters because the precise reason `jane-street` says "Configuration / Policy is not load-bearing" is that policy fields *do* end up driving downstream logic (rounding modes, tolerances, accounting classifications), and once they do, every law that references "tolerance" implicitly references L7 — which means L7 *is* load-bearing whether we admit it or not.

**Required fix:** drop "thin sidecar" as a reconciliation device. Replace with: "L7 is load-bearing. Every law that references a tolerance must declare which L7 field it references and which L21 pin governs that field." Then the V9 concern reduces to a code review of which fields are referenced by laws (the answer should be small, but it should be explicitly enumerable).

### MAJOR-J3 — `Some(zero) ≠ None` is a behavioural distinction asserted without a behavioural test

FORMALIS L6 T1 / MINSKY §4 / NAZAROV §3.3 all assert:
- `position_state(w, u) = Some(zero_P)` iff w has held u and closed out;
- `position_state(w, u) = None` iff w has never held u.

This is the StatesHome §2.2 monotone-carrier. The proposal asserts it as a type-level fact. But the *operational distinction* — what queries and laws change behaviour between the two states — is not enumerated. The hint "load-bearing for wash-sale lookback, VM-settle replay, record-date entitlement reconstruction" (FORMALIS L6 C1) names the use cases but not the laws. Specifically: *which CORRECTNESS law fails if a closed-out row is deleted?*

If the answer is "L8 (replay)", then it's a determinism issue: deletion changes the fold output. State that.
If the answer is "L1 (lineage)", state that and write the property test.
If the answer is "no law fails directly, but downstream tax / regulatory queries break", then the spec needs a regulatory query layer, which the proposal does not have.

**Required fix:** add to the property test catalogue a witnessed test of the form: "for every closed-out (w, u), the row remains and `Some(zero) != None` is observable through a named query whose output is law-relevant." Without this, the type-level distinction has no operational consequence and could silently regress.

### MAJOR-J4 — The proposal lacks a "minimum complete leaf example" for end-to-end sanity

I would expect, at this stage, **one** end-to-end worked example: a single trade, one ProductTerms registration, one snapshot, one calibrated curve, one valuation record, one move, one obligation, and the resulting projection — with concrete bytes (or at least concrete schemas) at each step. The proposal has none. Per Feynman Principle 3 ("what I cannot create, I do not understand"), I cannot at this stage *build* the toy and verify it composes.

This is not "polish". The Phase 1 enumerations were necessarily abstract; Phase 2 is meant to integrate to the point an implementer can start. Without one concrete example, every reviewer is unable to test their understanding against a single shared anchor. The disagreements in §9 cannot be resolved without one.

**Required fix:** add §11 "Minimum complete example" — one OTC IRS or one listed equity, walked from refdata ingest through registration through the first valuation cycle through one settlement, with concrete records at each leaf. Then state which laws are touched at each step.

### MAJOR-J5 — The "unwitnessed laws" surrogates are not equivalent to the laws

§9.4 acknowledges 4 of 14 laws are unwitnessed and offers surrogates. But none of the surrogates is shown to be **sound** (proves the law) or **complete** (catches every law violation). For example:

- L13 obligation liveness over unbounded futures → surrogate "bounded-horizon test + structural induction". Bounded horizon catches *bounded* failures. Structural induction is a paper proof, not a runtime witness. The combination would be sound only if the structural-induction step can be discharged in a proof assistant *against the actual implementation* (FORMALIS Coq or similar). The proposal does not require this.
- L1 lineage closure under vendor opacity → "trust-assumption registry + threat model + multi-source consensus". This is a process, not a property. It is unfalsifiable as written.

**Required fix:** for each unwitnessed law, state (a) the soundness argument (why the surrogate implies the law), (b) the failure mode the surrogate cannot catch (i.e., what would still slip through), and (c) the named owner who *accepts* the residual risk. The honest answer for L1, L4, L8, L13 may be "we accept the residual risk; here is the named owner". That is fine, but it must be on paper.

### MAJOR-J6 — The settlement-layer reconciliation (V10 ↔ L5) leaks a freshness contract the Ledger cannot enforce

§3.1 L5 says SSI lives outside the Ledger boundary; the Ledger consumes at projection time and records the version used. C-A4 names "Settlement-layer SSI freshness" with owner "Settlement-operations team". But: at projection time, the Ledger emits a settlement instruction. If the SSI was stale at projection, the instruction goes to the wrong account. The Ledger has *recorded* the version it used, but the resulting move-stream entry is wrong. Replay is deterministic-but-wrong.

The proposal frames this as "the settlement layer's contract", but the Ledger's substantiation theorem (FORMALIS Theorem 4) claims the move stream is the canonical record. If a deterministic-but-wrong move is committed, substantiation does not save us. This is a real gap, not a labeling one.

**Required fix:** either (a) elevate L5 freshness to an unconditional U-guarantee (which contradicts V10), or (b) state explicitly that L5 staleness is a defect class the Ledger does not catch, name the compensating control, and bind it to an obligation in L16. The current "boundary contract" framing hides this.

### MAJOR-J7 — TEMPORAL's six awkward-fit categories are deferred without a resolution rule

§9.5 lists six categories where Temporal is "genuinely awkward" (retroactive calendars; tick streams; bitemporal restatements; pricing-DAG topology; Kalman ContinueAsNew; SBL cascade-recall). The proposal defers resolution to Phase 3. But these are not ranked-list items — categories 1, 2, 3, 5, 6 each correspond to *load-bearing data leaves* (L4, L10, L2/L3/L4, L13, L16). If any one of them stays awkward, the corresponding leaf ingress shape is undecided, and an implementer cannot start.

**Required fix:** rule on each of the six. Acceptable rulings: "Temporal", "Out-of-Temporal service writing into Temporal-readable store", "Application discipline only — Temporal does not help here, and we accept that". The third is fine but must be stated.

---

## §C — MINOR findings

These are points where I would push back during review but would not block the build.

- **MINOR-1.** The `ContinueAsNew` payload completeness for L13 (TEMPORAL §6.5) is named as a known issue but no completeness check is named. A property test of the form "the post-CAN payload + `(snap_id, model_id)` reproduces the pre-CAN state to within ε" would close it.
- **MINOR-2.** §3.1 L4 says NOETHER flagged calendar versioning as a silent conservation violator. The fix ("snapshot-pin calendar reads at every `now()`") is one sentence; the proposal does not check off whether L4 is currently snapshot-pinned in the proposed types. State explicitly.
- **MINOR-3.** §3.5 L14 invariant count "4T + 5W + 2C = 11" is the highest in the proposal; FORMALIS calls this "load-bearing role". Reasonable, but no proof obligation is attached: which of the 11 are *witnessed* and which are *paper invariants*? Tag each.
- **MINOR-4.** §4 says L9 forgetful-functor composition is "Witnessed (round-trip test)". But composition is `F(e2 ∘ e1) = F(e2) ∘ F(e1)`, which is a generator-pair test, not a round-trip. State the actual test shape.
- **MINOR-5.** §5 (fault catalogue) is 7 × 7 = 49 cells but the §3 detail tables I sampled only enumerate 7 fault classes per cluster, not 7 × 7 cells. Confirm the matrix is fully populated in `correctness.md` or call out cells that are intentionally empty.
- **MINOR-6.** §7 names "5 strategic gaps" in CDM but Top-5 #5 ("TradeState ↔ StatesHome alignment — asserted but not verified") is itself a Phase-3 deliverable, not a CDM gap. This is a categorisation issue; move it.
- **MINOR-7.** §1.2 V12 vetoes "free-text metadata, attributes, extensions" but L11's `LifecycleEvent` sum (MINSKY §2.3) includes "RegulatoryThreshold" and "ForceMajeure" — these will tempt a free-text payload field. State explicitly that each constructor's fields are closed.
- **MINOR-8.** §3.6 L20 lists 9 idempotency-token shapes; one is `(workflow_id, run_id)` which has *Temporal-internal* meaning — not a content-addressed idempotency token in the same sense as `tx_id`. Mark which of the 9 are content-addressed (BLOCKING-G3 cross-reference).
- **MINOR-9.** §8 Theorem 5 (no-arbitrage pricing lifting) requires "L11 admissible no-arbitrage projection" but the projection operator $\Theta_{AF}$ is named only in CORRECTNESS L12. Pull the operator's signature into the proposal proper.
- **MINOR-10.** The proposal nowhere states the **retention horizon** that bounds C-A10. v10.3 long-tenor units imply 30y+ (TEMPORAL §3.1 mentions). State explicitly; affects every snapshot-store and audit-pass cost estimate.

---

## §D — Multiple-representation cross-check

I evaluated each of the 24 leaves against the question: "is there a *second* independent way to compute this leaf's value or to verify it?" The good news is that the proposal does have the building blocks; the bad news is that the second way is rarely *named*.

| Leaf | Stored / canonical form | Independent verification path | Named in proposal? |
|---|---|---|---|
| L1 ProductTerms | append-only versions | content-addressed `unit_id` recomputation from `terms_blob` | **Implicit** (BLOCKING-G1 dependency) |
| L2 InstrumentMaster | bitemporal vendor records | multi-vendor reconciliation (NAZAROV CC-3) | Yes |
| L3 Party / LEI | bitemporal records | GLEIF as authority + check-digit | Partial |
| L4 Calendar | bundle | cross-vendor calendar diff + holiday-as-of replay | Partial |
| L5 SSI | external | NOT CHECKED — L5 lives outside; this is MAJOR-J6 | No |
| L6 Legal Agreement | hash-anchored | counterparty co-signature verify | Yes |
| L7 Policy | versioned config | bootstrap pin vs L21 records | **No** (BLOCKING-G8 dependency) |
| L8 UnitStatus | mutable state | fold of L14 | **No** (BLOCKING-G2 dependency) |
| L9 PositionState | mutable state | fold of L14 | **No** (BLOCKING-G2 dependency) |
| L10 RawObservation | bitemporal log | snapshot replay + signature reverify | Yes |
| L11 LifecycleOracle | signed envelope | source authority cross-check | Partial |
| L12 ExternalConfirmation | ISO 20022 inbound | end-to-end-id back-walk to instruction | Yes |
| L13 CalibratedObject | certified posterior | Kalman replay from input snapshot | Yes (modulo BLOCKING-G3) |
| L14 MoveStream | hash-chained log | cross-replica content compare; chain re-hash | Partial (modulo BLOCKING-G6) |
| L15 ValuationRecord | per-(unit, t, model) | re-price from `(snap_id, model_id, model_version)` | Yes |
| L16 ObligationStore | child workflow + timer | timer fire vs discharge move correlation | Yes |
| L17 AttestationEnvelope | signature + key-id | re-verify against historical key registry | Yes |
| L18 IdentityKeys | derived hash | re-derive from canonical content | **Implicit** (BLOCKING-G1 dependency) |
| L19 Snapshot | content-addressed bundle | content re-hash | **Implicit** (BLOCKING-G1) |
| L20 IdempotencyToken | mixed | per-shape (BLOCKING-G3) | No |
| L21 VersionPin | pinned tuple | git/container/CDM authority lookup | Yes |
| L22 HashChainAnchor | chain | re-hash from genesis | Yes |
| L23 Capability | sum-typed grant | per-read/write audit | Partial |
| L24 OrchestrationState | Temporal history | Temporal replay | Yes |

**Of 24 leaves, 7 have a second representation that the proposal explicitly names; 8 are partial; 4 are implicit (depend on the missing canonicalisation); 5 are not named at all.** Roughly 1/3 of leaves do not currently have an independent verification path. That is too many.

---

## §E — Where the proposal substitutes jargon for understanding (Feynman Principle 4)

These are not blocking, but they are warning signs.

1. **"Realism budget"** (§6) — covered in MAJOR-J1.
2. **"Thin sidecar"** (§9.2) — covered in MAJOR-J2.
3. **"Monotone-carrier with Option accessor"** — covered in MAJOR-J3.
4. **"Forgetful functor"** (CORRECTNESS L9) — actually well-defined in the source (`F(e2 ∘ e1) = F(e2) ∘ F(e1)`), but in the proposal compresses to a name. State the equation in the synthesis.
5. **"Witnessed by property test"** — used uniformly across CORRECTNESS L2, L3, L5, L6, L7, L9, L10, L11, L12, L14. But "witnessed by property test" is not a uniform claim: a property test that passes 10⁶ runs is statistical evidence, not a proof. State the witness strength: "deterministic exhaustive over a finite generator universe", "statistical at 10⁶ Hypothesis examples", "model-checked", "Coq proof". The four classes have different operational confidence.
6. **"Realism class U1 + U2 + C-A3"** notation per leaf in §3 — concise but the meaning of "carrying" a U-guarantee is not precisely defined. Does L10's "U1, U2 + C-A3" mean L10 *provides* U1 and U2, or that L10 *requires* upstream code to satisfy them? Both are consistent with the prose; only the first is testable.

---

## §F — Grade

I distinguish two grades: **architectural soundness** (the model in the head, after I have read everything) and **constructive readiness** (could I start writing code that another implementer's code would interoperate with).

- **Architectural soundness:** B+. The 6-class spine is defensible; the 24-leaf decomposition resolves cleanly against the 7 specialist views; the realism budget and the cross-layer-laws structure are the right shape. Compared to a from-scratch design effort I would expect this to come out in the upper third.
- **Constructive readiness:** **D**. I cannot start a build without inventing ≥ 8 things, of which one (canonicalisation, BLOCKING-G1) silently breaks any cross-implementation interoperation. With the eight blocking findings closed, this would rise to a B-.

**Summary score (Phase 3 vocabulary):**
- 8 BLOCKING (G1–G8)
- 7 UNMITIGATED MAJOR (J1–J7)
- 10 MINOR (M1–M10)

**Recommendation.** Do not proceed to Phase 3 Round 2 without resolving the 8 BLOCKING findings. Revisions to the major findings can be deferred to Round 3 if the data team explicitly accepts the residual risk on J5 and J6 with named owners.

---

**End of Phase 3 Round 1 — FEYNMAN review.**
