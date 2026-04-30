# Phase 3 Round 1 — Adversarial Review (chris-lattner)

**Reviewer.** Independent chris-lattner instance, fresh context.
**Target.** `work/phase2/proposal_v1.md` (Phase 2 Synthesis Proposal v1).
**Lens.** Decade-scale system architecture: 10-year survival, progressive disclosure of complexity, versioning model coherence, load-bearing decisions, modularity vs coupling.
**Mode.** Attack first, suggest second. Findings classified BLOCKING / UNMITIGATED MAJOR / MINOR.

---

## §0. Executive verdict

This proposal is **architecturally serious** and reflects unusual discipline. The MoveStream-as-canonical-record posture (V13), the bitemporal-mandatory rule (P4), the StatesHome 3-map ruling, content-addressed snapshots, and the realism budget are exactly the load-bearing decisions an LLVM-class infrastructure project gets right. The 6-class spine has the property I most care about: **a forgetful functor to a smaller, simpler model** (3 sheaves) and a refinement functor to richer models (62 sub-leaves). That is the signature of an architecture that can survive being used in ways its authors didn't anticipate.

That said, the proposal has **three blocking issues, four unmitigated major issues, and a basket of minors** that would, uncorrected, compromise the 10-year survival posture. The most important blocker is L21's versioning model: **it conflates five distinct version axes into a single "VersionPin" leaf without specifying the algebra of how they compose, restate, and migrate**. This is the exact error LLVM made with debug-info versioning circa 2008 and we're still paying for it today. A second blocker is the systemic conflation of **library-pin (V8 `cdm_version`)** with **enum-closed-by-construction**, which silently turns every CDM extension into a breaking change to the Ledger's data layer. A third blocker is **L24's reconciliation with V11** is rhetorical rather than structural — there is no architectural fence preventing economic invariants from leaking into orchestration state.

**Grade: B.** Strong enough to ship as v11.0 if the three blockers are addressed; not yet strong enough to claim 10-year survival.

---

## §1. BLOCKING issues (3)

### B1. L21 VersionPin lacks a versioning algebra; five axes are silently conflated

**Where.** §3.6 L21, §1.1 P4, §6 C-A5, §9.3.

**The problem.** L21 names five distinct version axes and treats them as a record:

1. **Component version.** `(component_name, git_sha, container_digest)` — for executor / lifecycle workers / pricers.
2. **CDM/ISO/FpML schema version.** `cdm_version`, `iso20022_version`, `fpml_version`.
3. **Smart-contract version.** `(contract_id, contract_version)` — bound into L1 ProductTerms.
4. **Model version.** `(model_id, model_version)` — for Kalman/pricing models that produce L13 / L15.
5. **Reference-data version** — implicit in L2/L3/L4 `version_seq`, but governed by upstream registries (GLEIF, SWIFT, ISO).

These five axes have **fundamentally different mutation disciplines, restatement semantics, and migration costs**:

- Component version: monotone-forward, deployment-pipeline-owned, never restated.
- Schema version: externally restated (CDM v6.0 → v6.1 → v7.0), with backward-compatibility windows of unknown length.
- Contract version: append-only-versioned within a `unit_id` (L1's `is_fungibility_preserving` predicate gates this), not deployment-controlled.
- Model version: independently versioned per (target_object, model_family), with calibration history that may or may not survive a model change.
- Reference-data version: bitemporally restated by external authority; the Ledger does not own the version-bump cadence.

**Why this is blocking.** The proposal's §1.1 P4 says "bitemporal where the world restates; single-axis 'as-of' elsewhere; conflating the two is a violation". The same principle should be applied **within** L21 — but the spec treats version-pin as a single record. Concrete failure modes that the current spec cannot answer:

(a) **CDM v6.0 → v6.1 deprecates a `BusinessEvent` enum value.** Does an L14 row written under v6.0 with that enum value still validate under v6.1? If we re-read the row at `t_known = now()` with the new schema, what does L9 (forgetful-functor composition) require? The proposal does not say.

(b) **A model is recalibrated with a methodology change** (e.g., switch Kalman noise prior). Are pre-change L13 rows still "certified"? The `model_id, model_version` pair tells us *which* model produced a row, but not *whether the certification predicate is the same predicate* across versions.

(c) **A `unit_id` references contract v3, contract v3 is later revoked.** L1's `is_fungibility_preserving` gates fungibility, but does not gate **legal validity** of past valuations. The proposal needs an explicit statement of which version axis governs which invariant.

(d) **What is the join key for replay?** §8 Theorem 2 says snapshot determinism + workflow-history determinism compose to time-travel. But replay needs **all five axes pinned simultaneously**; if the schema version has restated since the original execution, replay produces a different parse, even with the same snapshot. The proposal does not specify whether replay reuses original schema or current schema.

**What I want.** A short §3.6.1 "Versioning Algebra" subsection that:

1. Names the five axes explicitly with separate identifiers (`component_pin`, `schema_pin`, `contract_pin`, `model_pin`, `refdata_pin`).
2. For each axis: states the mutation discipline (monotone? bitemporally restated? append-only?), the restatement semantics (does the old row stay valid? does it migrate? does it require explicit re-attestation?), and the witness-of-correctness predicate.
3. States the **composition rule**: which axes must be pinned for which invariant (lineage closure needs schema + refdata; replay determinism needs all five; conservation needs only schema + contract).
4. States the **migration story**: when CDM v6 → v7 lands, what is the operator-facing procedure?

Without this, L21 is the seam where the system fragments in 5–7 years.

**Reference.** This is the same architectural error LLVM made with debug-info versioning before DWARF v5. We had a single `dwarf_version` integer for years; the moment per-CU mixed versions arrived, half the toolchain assumptions broke. The fix was per-axis version metadata with an explicit composition rule. Do this *now*, before there is data on disk.

---

### B2. V8 (CDM enum closure as library pin) silently turns CDM extensions into breaking ledger-data changes

**Where.** §1.2 V8, §9.2 reconciliation, §3.6 L21 (`cdm_version`).

**The problem.** §9.2 reconciles V8 by saying: "CDM enum closure is a *library version pin* (L21), not a stored data category. Generators consume it via `cdm_version` import, not via a queryable table." This is correct as a code-organisation rule but **silently catastrophic as a versioning rule**.

If a closed CDM enum (say `BusinessEventTypeEnum`) is consumed via library-pin, and CDM v6.1 adds a new variant, then:

- **L14 rows written under v6.0** carry a payload that *parses* under v6.1 (forward-compatible: old enum values are still valid).
- **L14 rows written under v6.1** with the new variant **do not parse under v6.0**.
- **Replay of a v6.1 row in a v6.0 worker** is a parse failure — i.e., a non-determinism trap that masquerades as a schema-validation error.
- **Forgetful-functor composition (CORRECTNESS L9)** is no longer well-defined across schema-pin boundaries.

The proposal acknowledges schema stability (C-A5) and assigns it to MATTHIAS. But C-A5 is stated as "schema stability **within version**" — the cross-version story is exactly what V8's reconciliation hand-waves.

**Why this is blocking.** Every interesting CDM use case will require an extension (Top-5 Gap #1 calibrated layer, Gap #2 SBL recall, Gap #3 tokenised collateral, Gap #4 oracle envelope). The proposal's posture is "extend CDM upstream eventually, live with Ledger-internal types meanwhile". This means:

- The Ledger ships with a hybrid model (some types are CDM-pinned; some are Ledger-internal extensions).
- When upstream CDM lands the official extension, the Ledger must migrate from the internal type to the official type.
- The migration is a **data-layer breaking change** — not a code-layer breaking change.

The spec does not have a story for this migration. It needs one.

**What I want.**

1. Replace "library version pin" with **"versioned closed enum with explicit migration rule"**. For every CDM-closed enum the Ledger uses, a migration table: `from_cdm_version, to_cdm_version, removed_variants, added_variants, renamed_variants, semantic_changes`.
2. State the policy: **renames and semantic changes require explicit migration of historical L14 rows** (or an explicit restatement record stating the old payload is interpreted under the old version). Pure additions are non-breaking.
3. State the policy for **Ledger-internal extensions vs. CDM upstream**: when does a Ledger-internal type get retired? What is the cutover procedure?
4. Add a `schema_pin_compat_window` to §6 realism budget: how many CDM versions must the executor be able to read concurrently?

Without this, every CDM extension becomes a flag day.

---

### B3. L24 reconciliation with V11 is rhetorical, not structural — no architectural fence

**Where.** §3.6 L24 + tension paragraph, §1.2 V11, §9.2 reconciliation.

**The problem.** V11 vetoes "Workflow / Orchestration State as ledger data". L24 keeps Orchestration State on the spine but says "replay-substrate only; not economic data." The reconciliation says "no economic invariant references L24 directly."

This is a policy statement, not an architectural constraint. There is no mechanism that **prevents** an economic invariant from being written that references L24. CORRECTNESS L10 (Workflow-History Replay Coherence) already references L24 + L14. Compositional Theorem 2 (replay determinism lifting) **structurally depends on** workflow-history determinism (C-A9). The reconciliation says "L24 is not referenced by economic invariants" but Theorem 2 references it.

**Why this is blocking.** The thing about "thin sidecar" leaves is they get fat. Without an architectural fence, in 5 years:

- Some lifecycle workflow will need to inspect retry counters to make a business decision.
- Some pricer will need to inspect activity timing for staleness gating.
- Some auditor will demand orchestration-state-derived evidence.

Each of these will look reasonable in isolation. Aggregated, they recreate the V11-vetoed state of the world: orchestration state is load-bearing economic data.

**What I want.** A structural fence:

1. **Type-level**: L24 is reachable only via an opaque handle type (`OrchestrationOpaque`) whose introspection methods are restricted to replay/audit roles. Economic-handler types cannot consume `OrchestrationOpaque`.
2. **Capability-level (L23)**: Economic-handler capabilities cannot include `read:OrchestrationState`. This is enforced by L23 capability scope, not by convention.
3. **Theorem-level**: Theorem 2 should be restated as "replay determinism lifting **conditional on** workflow-history determinism, **and** the lift is invertible: any economic projection can be reconstructed without L24 inspection." If this invertibility cannot be stated, V11 is not actually being honoured and L24 is load-bearing.

This is the same lesson as Swift's `_OpaqueExistential` types. If you don't make the privacy structural, conventions erode.

---

## §2. UNMITIGATED MAJOR issues (4)

### M1. Progressive disclosure of complexity is not designed in — it is hoped for

**Where.** §0, §3 (24 leaves), §4 (14 laws), §6 (8+10 realism), §8 (5 theorems).

**The problem.** A new engineer joining this project in 2027 needs to understand: 24 leaves × 7 specialist contributions × 14 cross-layer laws × 18 realism rules × 5 theorems × 14 vetoes × 9 idempotency shapes. Even with the file structure, this is not progressively disclosed — it is a wall.

The 6-class spine *is* the right abstraction, but the proposal does not commit to **a teaching order** or a **minimum viable subset**. What can a newcomer learn in their first week that is genuinely usable? What is the smallest meaningful slice — the equivalent of "write a Hello World pass for LLVM"?

**Why this matters at 10-year survival horizon.** Every infrastructure project lives or dies by its onboarding. LLVM has the mid-level IR + TableGen + a 15-page tutorial. Swift has playgrounds. Mojo has a single-file model. This proposal has 19 + 7 specialist files and a 544-line synthesis. **There is no on-ramp.**

**What I want.**

1. A §0.1 "**Minimum viable mental model**" subsection: what's the smallest set of leaves an engineer must understand to be productive? My read: L1 + L8/L9 + L14 + L19 + L21. That's the spine within the spine.
2. A §0.2 "**Reading paths**": for newcomer / type-system specialist / orchestration engineer / auditor / regulator. Each gets a different first 50 pages.
3. A worked example: one trade, end-to-end, through every leaf it touches. This becomes the first thing a new hire reads.

Without this, the system has no ceiling but also no floor. Lattner's rule: **if the simple case isn't simple, the design is wrong**.

---

### M2. The "is in the library or in the compiler/runtime" question is not asked of leaves

**Where.** §3 generally, §1.1 P10, §3.6 L23.

**The problem.** §1.1 P10 says "polymorphism by sum type, not inheritance". Good. But the spec does not ask the deeper Lattner question: **for each leaf, is it in the runtime/executor (privileged), or in user-extensible territory (library-class)?**

Concretely:

- L7 Policy: who can extend it? If only the policy-governance workflow can write it, but consumers anywhere can read it, and the schema is "≤30 fields", then L7 is **runtime-privileged**. That's fine, but it should be stated.
- L11 LifecycleEvent sum type: it currently lists 8 variants. What is the rule for adding a 9th? Does it require a Ledger version bump, or can a new variant be added by a library extension? If the latter, the sum type isn't really closed and most invariants reasoning over it is suspect.
- L1 ProductTerms: `terms_payload` is stated as "CDM `ContractualProduct` for OTC, partial for listed". This is the place users will most want to extend (new product types). Is extension first-class or privileged?

**Why this matters.** The Lattner caste-system principle: when the runtime does something users can't, you've created a permanent two-tier system that ossifies the design. If users cannot add new lifecycle event kinds without a Ledger release, then the Ledger becomes a bottleneck for every new product line.

**What I want.** For each leaf with a sum-type or enum: explicit statement of (a) is the variant set closed-by-Ledger or open-by-extension, (b) what is the extension mechanism, (c) what is the migration story for extensions that get upstreamed.

This is the same question Mojo asks of every type: "can a user build this themselves?" If the answer is no, justify it.

---

### M3. The "thin sidecar" budget is not enforced

**Where.** §3.1 L7 ("≤30 fields"), §3.6 L24 ("replay-substrate only"), §3.1 L5 ("boundary contract").

**The problem.** Three leaves are admitted with realism budgets that are policy assertions ("L7 should not exceed 30 fields"; "L5 lives outside the boundary"; "L24 is not economic data"). None of these have a **structural enforcement mechanism**.

Where will L7 grow first? Tolerance thresholds — every new product line wants its own. Where will L5 leak in? When a settlement-failure recovery needs SSI version-pinning evidence in an L14 row. Where will L24 leak in? The first time a regulator demands retry-count evidence for a SLA report.

**Why this matters.** Budgets stated as policy and enforced as discipline always erode. LLVM had this exact issue with `Module::ModuleID` — it started as "a small handful of metadata fields" and is now structurally load-bearing.

**What I want.**

1. L7 budget: structural cap (e.g., L7 schema is itself versioned, and the version-bump cadence is rate-limited; or a CI check that L7 schema length cannot exceed 30 without a documented exception).
2. L5 boundary: a precise statement of what the Ledger does and doesn't store about L5 (e.g., "the Ledger stores `ssi_version_id` as an opaque hash; it does not store SSI fields"). This is structural, not policy.
3. L24 fence: see B3.

---

### M4. Unwitnessed laws are not linked to monitoring posture

**Where.** §4 (laws table, 4 unwitnessed), §9.4.

**The problem.** §9.4 lists 4 unwitnessed laws (L1, L4, L8, L13) and says reviewers must rule on whether the surrogate strategies are accepted. The surrogates are sensible in principle. But **there is no statement of what production observability detects a surrogate violation in flight**.

If the Lineage Closure surrogate is "trust registry + threat model + multi-source consensus", then production must measure: consensus quorum width, vendor-honesty signal, surprise rate against the threat model. None of this is named.

**Why this matters.** An unwitnessed law is, in production, an *operational risk*, not a *correctness risk*. The proposal treats them as correctness items needing surrogates, but the operational story is missing. In 5 years when cosmic-ray bit flips happen (they will), the question won't be "is replay determinism witnessed?" — it will be "what did our monitoring detect, and how fast did we recover?"

**What I want.** For each of the 4 unwitnessed laws: production observability spec — what metric, what threshold, what alert, what runbook. This is not Phase 3 polish; this is the difference between a system that survives a decade and one that fails an audit.

---

## §3. MINOR issues (with trade-offs)

### m1. Idempotency-key schema diversity is not normalised

§3.6 L20 lists 9 canonical shapes. This is fine for now but invites the question: when the 10th shape is needed, does it require a Ledger version bump? Suggest a shape-registry pattern (a closed enum of shape constructors, each carrying its own field set) rather than a free-form list. **Trade-off:** more upfront design; less downstream flexibility for ad-hoc tokens.

### m2. The MoveStream is canonical but not all CDM `BusinessEvent` payloads are first-class

§3.5 L14 says "CDM `BusinessEvent` payload" but the proposal doesn't say what happens to fields in `BusinessEvent` that the Ledger doesn't model. Are they dropped? Preserved opaquely? Round-trip-required? **Trade-off:** explicit preservation is safer but bloats L14 rows.

### m3. Per-(w, u) writer-cap phantom types (L9) are clever but operationally fragile

§3.3 L9 specifies field-level writer-cap phantom types. This is correct type-theory but operational complexity is significant. When a new handler is added, type-level surgery is required. **Trade-off:** structural enforcement vs. operational agility. Suggest documenting the handler-addition workflow explicitly.

### m4. C-A8 "Closed-system boundary integrity" is named but not bounded

§6 lists C-A8 with owner "Architecture review board" but no scope. What constitutes a boundary breach? At what scale does the boundary contract break? **Trade-off:** specifying it forces hard choices; not specifying defers them.

### m5. Goodhart trap mitigation (§9.6) is one paragraph — needs §-treatment

The 4 traps named are real and well-known, but the mitigation reads as a checklist item. Each trap deserves a paragraph: what the trap looks like in practice, what the test program does to avoid it, what the failure-to-avoid signal is.

### m6. The 24-leaf canonical numbering is fragile under future evolution

If a 25th leaf is added (say, for tokenised assets reaching first-class status), the numbering scheme has no slot. Suggest leaf identifiers that are not sequential integers (e.g., `L_SETTLEMENT_INFRA` instead of L5). **Trade-off:** more typing; better long-run readability.

### m7. §8 Theorem 4 (Substantiation) conflates "balance sheet projection" and "audit-grade evidence"

These are different claims. The projection claim is mechanical (L14 → balance sheet view). The audit claim requires multi-replica verification. The theorem statement bundles them. Untangle.

### m8. §3.4 L13 `arbitrage_certification_status = certified` — what authority certifies?

Naming the field is not naming the certifier. Add a `certifier_id` and an audit trail.

---

## §4. Things this proposal got right (decade-scale)

These are noted because they are the architectural decisions I would not change:

1. **MoveStream-as-canonical (V13).** The single highest-leverage decision. Every system that does not have this rots into duplication and reconciliation hell.
2. **Bitemporal mandatory (P4).** Saves 15 years of data-archaeology pain.
3. **Content-addressed snapshots (L19, U3).** Content-addressing is the single technique that makes replay-determinism a property rather than a hope.
4. **Forgetful functor to 3 sheaves (§2.1).** This is the structural property that makes the system simplifiable when needed and refinable when needed.
5. **Realism budget with named owners (§6).** Most specs hide assumptions. Naming them is half the battle.
6. **Vetoes-as-spine (§1.2).** The decision to enumerate things you will *not* build is more architecturally important than enumerating things you will.
7. **Surfaced disagreements (§9).** The single most reviewable section. This is how good architecture gets built.

---

## §5. Grade

**B.**

Strong enough to merit Phase 3 iteration; not yet strong enough to claim 10-year survival. The three blockers (B1 versioning algebra, B2 CDM extension migration, B3 L24 structural fence) are tractable and should be resolvable in 2–4 rounds. The four majors (M1 progressive disclosure, M2 library-vs-runtime, M3 sidecar enforcement, M4 observability) are the difference between B and A.

If addressed, this becomes the strongest data-spec proposal of its kind I've seen for a regulated-finance ledger. I'd ship the v11.0 with confidence on the architecture, with caveats on the migration story.

**Convergence path:** Round 2 should target B1 + B3 (core architecture). Round 3 should target B2 + M2 (extension story). Round 4 should target M1 + M4 (operability). Rounds 5+ for minors.
