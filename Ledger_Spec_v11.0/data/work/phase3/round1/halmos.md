# HALMOS — Phase 3 Round 1 Adversarial Review

**Reviewer.** HALMOS (exposition, notation, the Halmos test).
**Target.** `phase2/proposal_v1.md` (Phase-2 Synthesis Proposal v1).
**Mode.** Cold reading. No prior context. Six-pass discipline.
**Verdict.** See grade at end.

---

## §0. The Halmos test, applied

> "Could a competent reader, reading this document end-to-end, with no access to the seven specialist files, build the artefact it describes?"

**Answer: No.** The document is a *table of contents* for seven other documents. It is not a self-contained specification. The Convention statement in the preamble — "where this document compresses a specialist's argument, the specialist file is the authoritative source" — is not a virtue; it is an admission. Every leaf entry in §3 is a six-line stub that names the source file and tells the reader to drill in.

This is a structural problem, not a stylistic one. Phase 3 reviewers are told the document is "the artefact Phase 3 reviewers will attack" (§10), but the actual artefact under review is in fact the seven specialist files. The proposal, as a stand-alone document, fails the implementability test (HALMOS Hierarchy Level 5: *Could someone implement from this document alone?* No.)

This is the dominant finding. Many lesser findings below are downstream.

---

## §1. BLOCKING findings

### B1. No notation table. (CRITICAL — Hierarchy Level 1)

The document introduces, without a single notation table, *at minimum* the following symbols on first use:

- `unit_id`, `tx_id`, `obligation_id`, `snap_id`, `snapshot_id`, `unit_type`, `version_seq`, `t_obs`, `t_known`, `attestor`, `signature` (§3.1 L1)
- `business_event_id`, `vendor_msg_id`, `external_message_id`, `transaction_id_ref` (§3.1, §3.4)
- `(w, u)`, `σ(u)`, `(x_{t|t}, P_{t|t})`, `Θ_AF`, `now()` (§3.2–§3.4, §4)
- `model_id`, `model_version`, `cdm_version`, `git_sha`, `container_digest`, `contract_id`, `contract_version`, `prev_hash`, `key-id` (§3.6)
- `(workflow_id, run_id)`, `(calibrated_object_id, certification_timestamp, model_id)` (§3.6 L20)
- The codes `U1–U8`, `C-A1–C-A10`, `P1–P10`, `V1–V14`, `N1–N12`, `C1–C6`, `L1–L24`, `L1–L14` (laws, *re-using* the L-prefix that names leaves), `T+W+C` (FORMALIS invariant counts), `T-W-C` (rest of doc).

A reader cannot discover these from the text. They are introduced as if previously agreed.

**The L-prefix collision is itself blocking.** §3 uses `L1–L24` for *leaves*; §4 uses `L1–L14` for *consistency laws*. A sentence like "L8 (replay)" in the §3 L1 entry refers to *law* L8, while "L8 UnitStatus" two paragraphs later refers to *leaf* L8. The reader cannot tell which without context, and the contexts are adjacent. This is the classic Halmos overload.

**Required fix.** Add §0.5 Notation, listing every symbol, type, and code prefix with its meaning and first-use section. Disambiguate the L-prefix: use **L#** for leaves and **K#** (or **Λ#**) for laws.

### B2. Forward references on first page. (CRITICAL — Hierarchy Level 5)

The Executive Summary (§0) references, before they are defined:
- "NAZAROV's six-class spine with 24 canonical leaves" (defined §2.1)
- "MoveStream", "L8 UnitStatus", "L9 PositionState", "L14 MoveStream" (defined §3)
- "bitemporal axis" with `t_obs` vs `t_known` (defined §3.4 implicitly; never explicitly)
- "CDM v6.0.0" (defined nowhere)
- "twelve-item data-quality bar (N1–N12)" (referenced but the items are not listed)
- "ten engineering principles (P1–P10) and fourteen vetoes (V1–V14)" (defined §1)
- "fault-clusters", "Cluster I", "Cluster VII" (defined §5 but used in §3)
- "v10.3 §7.6", "v10.3 §13.4", "v10.3 §10.6", "v10.3 P21–P23", "Property 6", "valuation v1.0 §5" (these refer to a document never identified in the bibliography)

**Required fix.** Either move §1 + §2 + a glossary before §0, or rewrite §0 to be self-contained at the cost of repetition. (Repetition is fine — Halmos endorses it.)

### B3. The `t_obs` vs `t_known` distinction is asserted, never defined. (HIGH)

The single most important conceptual primitive in the document — bitemporality — is named in three places (§0 anchor 3, §1.1 P4, §6 U2) and is invoked as a discipline ("bitemporal mandatory") for half of the leaves. **It is never defined.** What event is `t_obs`? What event is `t_known`? Restated in whose books? With what tie-breaking on equality? A reader who does not already know the bitemporal pattern from prior context cannot reconstruct the design.

**Required fix.** A formal definition box before first use, in §1 or in a new §2.0.

### B4. "StatesHome" is referenced as canonical without being defined. (HIGH)

"StatesHome" appears on first use in §3.1 L1 as `(= StatesHome map 1)`, again at L8 (`map 2`), L9 (`map 3`). It is invoked authoritatively in §3.2 ("StatesHome C11"), §3.3 ("StatesHome C11"), §3.6 L23 ("StatesHome C4 capability scopes"), §6 ("StatesHome C11"), §8 ("StatesHome C2"). **The "C#" indices into StatesHome are nowhere defined.** The reader cannot know what C2, C4, C11 mean.

**Required fix.** Either include the StatesHome glossary in this document or state the canonical reference (with section numbers) at first use.

### B5. The "definition" of L4 is subtly inconsistent across two specialist sections. (HIGH — the requested check)

Cross-reading §3.1 L4 (Calendar/Convention) and §6:
- §3.1 L4 N: "Holiday calendars per `BusinessCenterEnum`, day-count fractions, business-day adjustment rules, roll conventions, weekend rules."
- §3.1 L4 F: "**Part of L2 ReferenceMaster**; bitemporal mandatory."
- §3.1 L7 F: "**Part of L2.**" (same phrasing — L7 is *also* "part of L2")
- §3.1 L5 F: "**Part of L2.**" (and L5 too)
- §6 U2: "Bitemporal indexing on every C1/C4 leaf."

So **three distinct leaves (L4, L5, L7) are simultaneously declared "part of L2"** in their FORMALIS slot. Either (a) FORMALIS folds L4/L5/L7 into L2 — but then the proposal's claim that "NAZAROV's 24 is canonical" is contradicted at the FORMALIS row; or (b) the phrasing "Part of L2" means something other than "is L2", but then what?

The same kind of folding happens at L10 ("Part of L8"), L11 ("Part of L8"), L12 ("Part of L8"), L17 ("Part of L8"), L19 ("Part of L8 + L15"), L21 ("Part of L16"), L22 ("Part of L1 + L10"), L23 ("Part of L14"), L18 ("Part of L1"). The reader is told FORMALIS uses 16 leaves while the proposal uses 24, but the mapping table in §2.3 only says "FORMALIS folded `(L17–L22)` into `L13 WorkflowHistory` and `L14 WalletRegistry/Capability/KeyRegistry`". That mapping does not match the per-leaf "Part of L2" / "Part of L8" annotations, which fold many *more* leaves than just L17–L22 and use FORMALIS-numbering (L1–L16) that is *also* re-using the L-prefix.

**This is a third L-prefix collision**: leaves (NAZAROV 1–24), laws (CORRECTNESS 1–14), and FORMALIS-leaves (1–16). The "F" line of every §3 entry refers to FORMALIS leaves but spells them as "L2", "L8", "L9", "L14"... numerals that *also* name NAZAROV leaves with completely different meanings. Reading "**F**: Part of L2" inside the §3.1 L4 entry, a competent cold reader will assume L2 = `Reference Data — Instrument Master` (the NAZAROV leaf two entries above). It is in fact FORMALIS leaf 2, which is something else.

**Required fix.** Disambiguate aggressively. Use `L#` for NAZAROV leaves only. Use `Λ#` for CORRECTNESS laws. Use `Φ#` for FORMALIS leaves. Re-do every cross-reference in §3 and §4.

---

## §2. UNMITIGATED MAJOR findings

### M1. §3 entries are too compressed to be specifications. (HALMOS Hierarchy Level 4 — Example Test)

Every leaf entry promises six lines (N, M, T, R, F, C). What the reader gets is six tag-lines, each a sentence fragment, each pointing to a different file. There are **no examples** for any leaf. A definition without an example is, per the Halmos test, *no definition*. What does an L1 ProductTerms instance actually look like? What is a concrete L14 MoveStream row? What does a `StateDelta` field-tagged writer phantom type look like in code? The reader cannot tell.

**Required fix.** One worked example per class C1–C6 (six examples total), inline in §3.

### M2. Section §5 (Fault catalogue) is one paragraph that points elsewhere. (Hierarchy Level 2 — Structure)

§5 promises a 49-cell matrix, then says "Detail in `correctness.md` §3." That is not a section; it is a stub. A reader who wants the fault catalogue must abandon this document.

**Required fix.** Inline at least the cluster-by-class skeleton, even if individual cells are deferred.

### M3. Sentences begin with symbols. (MEDIUM — Halmos Rule 2)

Examples:
- §3.1 L1 N: "Min fields: `unit_id`, `product_type`, ..." — the convention "Min fields" begins a sentence with a fragment. (Many leaves.)
- §3.1 L1 M: "`ProductTerms = NonEmpty<TermsVersion>` with `TermsVersion = ...`" — a sentence beginning with a symbol.
- §3.4 L10 N: "Single attestation `y_t` of an observable..." — fragment, no verb.
- §3.6 L18 N: "Deterministic-hash derivation of `unit_id`, ..." — fragment.
- §3.6 L20 N: "Minted at workflow boundary..." — fragment without subject.

Most of §3 is in a telegraphic register that drops articles, verbs, and subjects. This may be acceptable in a contributor's working notes; it fails the test for an "artefact Phase 3 reviewers will attack" (§10) and certainly for a future LaTeX target (§8).

**Required fix.** Rewrite §3 in complete sentences. Halmos Rule 1: equations are sentences. Apply it.

### M4. Inconsistent identifier conventions. (MEDIUM — the requested check)

The reader is told identifiers are content-addressed (P3), but the conventions are inconsistent:
- `unit_id`, `tx_id`, `obligation_id`, `snap_id`, `snapshot_id` — `_id` suffix, lowercase. (`snap_id` and `snapshot_id` *both appear* — §3.6 L19 uses `snap_id`, §3.6 L18 uses `snapshot_id`. Are they the same? The reader cannot tell.)
- `vendor_msg_id`, `business_event_id`, `transaction_id_ref`, `external_message_id` — same pattern, sometimes with a role suffix.
- `UnitId`, `TxId`, `UTI`, `USI`, `ObligationId`, `SnapshotId` — PascalCase Minsky newtypes. The text alternates between snake_case (the field name) and PascalCase (the refined type) without saying which is the canonical token.
- `idempotency_key` (snake) vs `IdempotencyToken` (Pascal) — same object, two spellings.
- §3.6 L20: "9-shape canonical algebra: `unit_id`, `tx_id`, ... `(unit_id, version_seq)`, `(workflow_id, run_id)`" — tuples are written without saying that they are tuple-typed identifiers.

**Required fix.** State the convention in §0.5 Notation: "Identifiers are written `snake_case` for the field token and `PascalCase` for the refined type; one canonical spelling per object."

### M5. The reconciliation of jane-street vetoes is asserted, not argued. (MEDIUM)

§9.2 contains the most consequential negotiations in the document (V8/V9/V10/V11 vs L5/L7/L24). Each cell of the table contains a 1-sentence reconciliation. The actual argument — *why* "thin sidecar (≤30 fields)" defends V9, *why* "boundary contract" defends V10 — is asserted, not given. The document explicitly says "Phase 3 must validate that these reconciliations actually hold under the proposed structure". That is the right instruction; but a Phase 3 reviewer should not be the *first* person to argue them.

**Required fix.** Each reconciliation needs a paragraph explaining the structural reason it holds, not just the slogan.

### M6. The "M" line for L1 contains a forward-referenced semicolon-glued sentence. (MEDIUM)

§3.1 L1 M: "`ProductTerms = NonEmpty<TermsVersion>` with `TermsVersion = { fields: Fields; is_fungibility_preserving: TermsVersion -> bool }`. Closed enum `LifecycleIntent`. Refined `UnitId` newtype with private constructor."

`Fields` is undefined. `LifecycleIntent` is undefined here and never used again. `UnitId` will be defined three pages later. This is one example; similar problems run through the M-lines of L2, L3, L5, L9, L13.

---

## §3. MINOR findings

### m1. Halmos Rule 4 (small integers in words). (LOW)
"6 classes", "24 leaves", "7 specialists", "14 laws", "19 enumerations", "4 unwitnessed laws", "3 sheaves". Use words: "six classes", "twenty-four leaves", "seven specialists". Unless these are catalog numbers, they read as part of the running prose.

### m2. Repeated terminology drift. (LOW — Halmos Rule 6)
The MoveStream is variously called "the canonical record" (§0), "the source from which projections derive" (§3.5), "load-bearing role" (§3.5 F line), "single canonical record" (P8). Pick one phrase. (Halmos: "Use the same word for the same concept throughout.")

### m3. Theorems unnamed. (LOW — Halmos Rule 7)
§8 lists five compositional theorems by number ("Theorem 1, 2, 3, 4, 5") and gives each a label ("Conservation Lifting", "Replay Determinism Lifting", etc.). Good. But §4 lists 14 laws as "L1, L2, ..." with names tucked in the column. Cross-references like "L1 Lineage Closure" are right; bare "L1" (e.g., "L1, L4. Cluster I." in §3.1 L2 C-line) is wrong. Always cite by name.

### m4. Appendix A is incomplete. (LOW)
Appendix A lists 7 specialist files but does not list the 19 Phase-1 enumerations individually. The proposal claims "Phase 1's 19 independent enumerations" converge; a reader who wants to verify cannot find them by name.

### m5. "FpML / CDM" alternation. (LOW)
The relationship between FpML and CDM is referenced but never explained ("Direct for many fields via FpML / CDM `Asset` types" — §3.1 L2 R). The reader is left to wonder whether they are the same, layered, or different.

### m6. The Phase-3 "drill in when challenged" instruction reverses the reviewer's burden. (LOW, but worth flagging)
§10 step 2 instructs reviewers to drill into specialist files when challenging compressed claims. Halmos: the *writer* should anticipate difficulties; the *reviewer* should not have to assemble the argument from sources. This is the M2 problem in another form.

---

## §4. The "subtly different definition" check (the requested gem)

The user asked: where is the *definition* subtly different across two specialist sections?

I find at least three:

**D1. UnitStatus / PositionState boundary.** §3.2 L8 N puts `weights (QIS)` and `nav index` in *UnitStatus* (per-unit). §3.3 L9 N puts `entry_nav`, `accumulated_cost`, `hwm`, `accrued_mgmt_fee`, `accrued_perf_fee`, `benchmark_nav_at_inception` in *PositionState* (per-(w,u)). But for a QIS mandate, the `nav index` is per-unit *and* the per-position carriers depend on it. The split is asserted, not motivated. A reader cannot tell whether `nav index` (in L8) and `entry_nav`/`benchmark_nav_at_inception` (in L9) are the same observable indexed differently or two distinct quantities. This *is* the kind of subtle definition drift HALMOS warns about.

**D2. ObligationStore status enum.** §3.5 L16 N: `status ∈ {PENDING, DISCHARGED, COMPENSATED, DEFAULTED}` (uppercase). §3.5 L16 M: `Sum type ObligationState = Pending | Discharged | Compensated | Defaulted` (PascalCase). Same four states, two spellings, same paragraph. Either the data field uses uppercase tokens *and* the type-system spelling is PascalCase (then say so), or they are the same and the document is inconsistent.

**D3. ValuationRecord quality enum vs. valuation FSM.** §3.5 L15 N: `quality ∈ {FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED}` plus "valuation FSM state". §3.2 L8 N: "valuation FSM state σ(u)" (per-unit). So the FSM state lives in *both* L8 and L15. Which is the writer? `σ(u)` is per-unit; the L15 record is per-(unit, t, model). Are these two FSMs, or one FSM whose history is L15 and whose current value is L8? The proposal does not say.

---

## §5. The Halmos test, reprised

| # | Halmos test item | Pass/Fail |
|---|---|---|
| 1 | Notation table exists, designed in advance | **Fail** |
| 2 | Every symbol defined before first use | **Fail** (B1, B2, B3, B4) |
| 3 | Every definition has at least one example | **Fail** (M1) |
| 4 | Structure apparent from table of contents | Pass (the §-numbering is clear) |
| 5 | Read six times (multiple revision passes) | Cannot tell — but the residual inconsistencies (B5, M4, D1–D3) suggest fewer than six passes |
| 6 | Implementable from this document alone | **Fail** (the document explicitly defers to seven other documents) |

Four of six fail. The proposal has the right *bones* — the §-numbering, the §9 disagreements section, the explicit Phase-3-targets list. It does not have the *flesh*.

---

## §6. Grade

**Grade: D+ (low pass, must remediate before Phase 3 substantive review).**

Rationale. The structural skeleton is sound (§§0, 1, 2, 9, 10 are well-organised; §9 surfaces disagreements honestly). The expository content of §§3–8 is unfit for adversarial review by a cold reader: notation is undefined, the L-prefix is overloaded three ways, definitions drift across sections, and §3 is a directory of stubs. The Halmos test fails on four of six criteria.

**Recommendation to Data Team.** Before the next round of substantive Phase-3 attack, produce a v1.1 that:
1. Adds §0.5 Notation (B1, M4).
2. Disambiguates the L-prefix (B1, B5).
3. Defines bitemporality, StatesHome indices, and FpML-vs-CDM (B3, B4, m5).
4. Inlines one example per class (M1).
5. Inlines the §5 fault skeleton (M2).
6. Reconciles the L8/L9/L15 boundary cases (D1, D2, D3).

These are mechanical, not architectural. None blocks the design; all block the *review* of the design.

---

**End of HALMOS Round 1.**
