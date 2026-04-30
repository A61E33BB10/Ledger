# Phase 3 Round 2 — Independent jane-street-cto Closure Check on `proposal_v2.md`

**Reviewer.** Independent jane-street-cto instance (fresh context). I have not seen `phase2/jane_street_v2.md`.
**Inputs read.** `phase3/round2/proposal_v2.md` (654 lines), `phase3/round1/R1_consolidated_findings.md` (597 lines).
**Scope.** Verify closure of R1 jane-street BLOCKING findings B1–B6; audit per-veto truth conditions in §3.2; audit §15 reconciliations; audit ADR register §16; issue new findings; grade vs v1's C+.

---

## §A. Closure verdicts on the six R1 jane-street BLOCKING findings

### B1 — "24 leaves was 3.4× creep over 7-sector ceiling"

**Verdict: closed.**

Citation. `proposal_v2.md` §0 headline ("Leaf count 24 → **19** (jane-street's V7 conceded)"); §4.1 "rules the **minimalist path**: collapse to FORMALIS-aligned 16 + 3 ADR-sanctioned additions = **19 leaves**"; §4.4 final 19-leaf catalogue; §15.1 D1 resolution "19 leaves"; V7 in §3.2 table reset to ceiling 20 with CI test `count_check.py::test_leaf_count_le_20`.

Note. R1 jane-street's veto literally said 7 sectors. v2 keeps **19** leaves and concedes V7 by re-pegging the ceiling at 20 (jane-street's own §1A in v2). I would have preferred a literal honoring of the 7-sector ceiling, but the count is now defended structurally (FORMALIS-aligned 16 + 3 ADRs), no longer rhetorically. The `≤20` ceiling is enforced by named CI rather than by exhortation. That is closure on the *substance* of B1 (no leaf-count creep without ADR), even if not on the *number* originally cited.

### B2 — "L24 OrchestrationState re-admitted V11 with FORMALIS invariants and CORRECTNESS L10 participation"

**Verdict: closed.**

Citation. §4.2 v1→v2 disposition table: "L24 OrchestrationState — **Deleted from spine** — V11 violation; not economic data; opaque to invariants." §4.4 catalogue contains no L24. V11 in §3.2 retains its falsifying predicate "Economic invariants reference workflow state" with CI mechanism `arch_test.py::test_no_econ_orch_dep`. There is no L24 in the 19-leaf catalogue; no FORMALIS invariant family Φ refers to it; no Λ# in §6 references workflow state.

This is the cleanest of the six closures. L24 is gone, not laundered.

### B3 — "L5 SSI re-admitted V10 with `ssi-ingest` workflow inside the Ledger"

**Verdict: closed (with semantic shift to flag).**

Citation. v2's L5 is **UnitStatus**, not SSI (§1 definitions table; §4.4 catalogue). SSI as a leaf has been removed. V10 in §3.2 keeps its falsifying predicate "Ledger has SSI write API" with CI mechanism `arch_test.py::test_no_ssi_write`. C-A4 (§10.2) treats SSI explicitly as boundary input owned by settlement-operations.

Caveat. The R1 finding referenced "L5 SSI" because v1 had numbered SSI as L5; v2 reuses the slot L5 for UnitStatus. A reviewer skim-comparing labels could be misled. The **substance** of B3 — no `ssi-ingest` workflow authoring SSI inside the Ledger — is honored.

### B4 — "L7 Policy re-admitted V9 with `≤30 fields cap` unenforced"

**Verdict: closed.**

Citation. §1 leaf table partitions L7P into L7Pa (firm currency / decimals / rounding), L7Pb (tolerance thresholds), L7Pc (capability schema, version pins, retention). V9 in §3.2 has explicit falsifying predicate "L7P partition exceeds 30 fields per partition" with CI mechanism `count_check.py::test_l7p_field_cap`. ADR-12 (§16) records the partition + ≤30 cap as a deliberate ruling.

The cap moves from "wish in prose" to "named CI test against named partitions." That is enforcement.

### B5 — "L21 VersionPin re-created V8 violation"

**Verdict: closed.**

Citation. §11 "Versioning algebra" replaces L21 monolith with a typed product over seven named axes (`component_pin`, `schema_pin`, `contract_pin`, `model_pin`, `refdata_pin`, `drr_rule_set_pin`, `canonicalisation_pin`), each with its own mutation discipline. Composition rule per Λ# stated: "for each Λ#, the proposal states which axes must be pinned for the invariant to hold under replay." V8 in §3.2 is reset: predicate "CDM enums stored as queryable table" with CI `schema_linter.py::test_no_cdm_enum_table` — i.e. CDM enum closure remains a library version pin, not a leaf. ADR-6 in §16 is the canonicalisation pin as version-pin axis.

The five-axes-collapsed-into-one criticism (R1 lattner B1, picked up by jane_street) is resolved structurally.

### B6 — "L24 in isolation is ceremony"

**Verdict: closed (subsumed by B2).**

L24 deleted (§4.2). Ceremony cannot persist where the leaf does not exist.

---

## §B. Audit of per-veto truth conditions (§3.2 V1–V14)

R1 finding (`cartan M6`, `jane_street M6`): vetoes had no falsifying predicates and no enforcement mechanisms ("no enforcement = wish").

Each row of v2 §3.2 carries (i) a falsifying predicate, (ii) a named CI test file:function. Spot audit:

- V1 `arch_test.py::test_unit_store_single_storage` — predicate "≥3 distinct ORM tables for Unit Store" — checkable mechanically.
- V4 `schema_linter.py::test_canonical_storage` — predicate "Storage layer has vendor-discriminated columns" — checkable.
- V7 `count_check.py::test_leaf_count_le_20` — checkable by static count.
- V9 `count_check.py::test_l7p_field_cap` — checkable.
- V11 `arch_test.py::test_no_econ_orch_dep` — predicate "Economic invariants reference workflow state" — checkable by import-graph analysis.
- V13 with ADR-1 carve-out for L5/L6 stored caches — explicit override, not silent.

Verdict. These are real CI mechanisms (not slogans). Each predicate is a Boolean over the codebase, not a vibes statement. **Whether the named test files actually exist in the repo is a separate audit (R3 admission gate)**; v2 has staked the claim correctly.

One residual concern. V14 "Obligation uniform" with predicate "Regulator-discriminated obligation tables" and CI `arch_test.py::test_obligation_uniform`. With the addition of L17 RegulatorySubmission, there is a real risk that submission-payload schemas get regulator-tagged in implementation. The CI test as named would catch *table* discrimination but not *payload-shape* discrimination. **Flag, not blocker.**

---

## §C. Audit of §15 reconciliations

R1 finding (`halmos M5`, `jane_street M2`, `geohot Worst Pattern`): "tension box" reconciliations were slogans, not rulings.

§15 in v2 explicitly states: "The §9.2 'tension box' pattern of v1 is **banned** in v2." Each of D1–D5 is given a one-paragraph **resolution** with citation:

- §15.1 D1 leaf count → 19; Strategy A. **Ruling.**
- §15.2 D2 tokenised collateral → `lifecycle_model = SmartContract` + `EligibleCollateralCriteria` extension; `DigitalAsset` rejected. **Ruling.** Concrete, testable, with ADR-10.
- §15.3 D3 surrogate-witness retreat → 1 genuinely unwitnessed (Λ1) + 3 witnessed-via-composition (Λ4, Λ8, Λ13). **Ruling.**
- §15.4 D4 C2/C3 elevation → L5/L6 are stored caches with single-writer invariants per StatesHome C11; ADR-1 V13 carve-out; cache-invalidation discipline CIv-1/CIv-2/CIv-3 per Th-4b. **Ruling.**
- §15.5 D5 compensations → non-trivial compensations are child workflows; three-tier saga tower. **Ruling.**

Verdict. Reconciliations are rulings, not tensions. **Closed.**

---

## §D. Audit of ADR register §16

R1 demanded each veto override be a documented ADR.

§16 contains exactly **12 ADRs** (ADR-1 through ADR-12). Each row has Title, Veto/Leaf, Justification. ADR-1 (V13 carve-out for L5/L6), ADR-2/3/4 (the three new leaves L17/L18/L19), ADR-5 (mode-1 calendar pin), ADR-6 (canonicalisation pin), ADR-7 (tx_id excludes run_id), ADR-8 (compensation workflows), ADR-9 (single-source admission via N8.2), ADR-10 (tokenised collateral framing), ADR-11 (verification keys append-only), ADR-12 (L7P field cap).

Verdict. 12 entries as specified. Every load-bearing R1-flagged override is named.

---

## §E. New findings on v2 (BLOCKING / MAJOR / MINOR)

### NEW-MAJOR-1. Two distinct meanings of `T#` collide in §0 notation table.

The notation table (line 17 area) lists `T#` for "Convergent theme from R1 consolidation" and again for "Goodhart trap". The exact same prefix is overloaded. v2 ostensibly disambiguates everything else aggressively (the whole point of §0), so this is a self-inflicted regression of the same class as R1 halmos B5. Fix: rename Goodhart traps to `GT#` (which §14 already uses inline — the table just disagrees with §14). Severity: **MAJOR** because v2's own §0 thesis is "disambiguate aggressively."

### NEW-MAJOR-2. Leaf count 19 vs leaf-count-cap 20: only 1 unit of slack before next inflation cycle.

V7 in §3.2 sets the CI ceiling at 20. v2 ships 19. One additional ADR-justified leaf consumes the slack. Either (a) commit to ≤19 in V7 or (b) explicitly justify why the cap is 20-not-19 (e.g. anticipated cost of a known future addition). Otherwise the next R# cycle will burn 20 too. Severity: **MAJOR** but easily fixed.

### NEW-MAJOR-3. L7P partition cap is "≤30 fields per partition" not "≤30 fields total."

V9 originally read as a global Policy-fields cap. v2 §3.2 V9 reads "L7P partition exceeds 30 fields per partition." With three partitions (L7Pa/b/c) the global Policy-fields cap is now effectively 90, not 30 — a 3× expansion of the original veto. ADR-12 codifies this. The expansion is deliberate but should be **acknowledged in the ADR justification**, not buried in the predicate phrasing. Severity: **MAJOR (transparency, not correctness)**.

### NEW-MAJOR-4. V14 "obligation uniform" CI does not catch payload-shape discrimination.

See §B above. With L17 RegulatorySubmission carrying regulator-specific payloads, there is a real risk that *payload schemas* (DRR per regulator) become de-facto regulator-discriminated tables disguised as one Obligation table. CI as named (`test_obligation_uniform`) only catches table-name discrimination. Sharpen the predicate to "regulator-tagged columns or per-regulator payload schemas in `Obligation` storage." Severity: **MAJOR**.

### NEW-MAJOR-5. ADR-1 cache-invalidation discipline relies on Th-4b, which itself depends on E-ATOM.

ADR-1 (the V13 carve-out) cites CIv-1/CIv-2/CIv-3 per Th-4b. Th-4b's hypothesis E-ATOM (atomic StateDelta commit) is shared with Th-1. If the executor commit semantics differ between L13 append and L5/L6 cache write, **the carve-out collapses**. v2 should state explicitly that the executor commit is a single transaction across L13 append + L5/L6 cache writes (matches v10.3 StatesHome ruling), with the corresponding boundary in §7 (B-class). Currently §7 has no boundary explicitly named "executor atomicity." Severity: **MAJOR**.

### NEW-MINOR-1. ADR-9 single-source admission is the only ADR without a CI test reference.

ADR-9 (single-source admission via N8.2 explicit assumption ref) has no named CI test in §3.2 or §16. This is the only ADR override that depends on prose discipline ("vendor honesty C-A3 named assumption"). Add a CI predicate: "every L9 row with `aggregation_outcome = unique_authority` carries a non-null `single_source_authority_assumption_ref`." Severity: **MINOR**.

### NEW-MINOR-2. §0 last paragraph overlaps with the per-leaf appendix in §1.

§0 carries the StatesHome C-indices listing; §1 carries leaf well-formedness. The two are close enough that a reader will not know which is normative for "what fields does L1 carry?" Tighten cross-reference. Severity: **MINOR**.

### NEW-MINOR-3. Goodhart trap GT5 (type-system witness laundering) — the AST lint rule banning `cast` outside ctor module.

§14 GT5 lists three layers of defence including "custom AST lint banning `cast` / `__new__` outside ctor module." This is a specific, testable claim. It does **not** appear in §3.2's CI mechanism column for any V#. If this lint is the workhorse against witness laundering (which v2 claims), it deserves a named CI mechanism alongside V1–V14. Severity: **MINOR** but architecturally clarifying.

### Over-engineering audit (specifically requested).

The user asked: "any over-engineering that crept in (e.g., 19 leaves still feels too many; new veto-launderings)?"

- **19 leaves: is it still too many?** I judge no. 16 (FORMALIS) + 3 (ClockAuthority, BreakRegister, RegulatorySubmission) is structurally defended. ClockAuthority is the S3 carrier and was missing from v1; not optional. BreakRegister has SOX/BCBS/DORA mandates; not optional. RegulatorySubmission is the only spine-level load-bearing addition and is justified by Pillar 3 / SFTR / SLATE / RTS 22 obligations with Theorem 6 (Pillar-3-Projection-Lifting) doing real work. The cut from 24 to 19 was the right call; further cutting would damage either S3 or operational floor.
- **New veto-launderings.** None spotted. ADR-1 (V13 carve-out for L5/L6) is the closest candidate, but it cites StatesHome C11, names cache-invalidation discipline, and stakes a theorem (Th-4b) — that is an honest override with structural backing, not a slogan.
- **§7 boundary count 12 → 17.** All 5 new boundaries (B13–B17) are real engineering concerns (FP determinism, iteration order, intra-handler concurrency, locale, test seed). Not bloat.
- **§8 49-cell fault matrix.** Could collapse to a smaller set if I were strict, but the 7×7 frame is defensibly cluster-orthogonal. Not bloat.
- **§9 6 theorems.** Th-6 (Pillar-3-Projection-Lifting) is the only addition vs v1's 5; it carries the L17 RegulatorySubmission's audit obligation. Justified.

I find no veto-laundering and no leaf-count creep in v2.

---

## §F. What v2 did well (briefly, since it bears on the grade)

- The V# table format with falsifying predicate + named CI test (§3.2) is exactly the right pattern. This is the model R3 reviewers should hold every other reviewer's vetoes to.
- The ADR register at §16 is concise, named, and load-bearing.
- The notation table at §0 (modulo the `T#` collision in NEW-MAJOR-1) is the artefact R1 halmos and cartan demanded.
- §11 Versioning algebra is structurally correct: seven axes, mutation discipline per axis, composition rule per Λ#. This is genuine progress over v1.
- §12 operational floor matrices (reconciliation, retention, SLA, IPV/AVA) move v2 from architecture-document to specification.
- L24 deletion is unambiguous. No ceremony.

---

## §G. Verdict and grade

**Verdict: APPROVE WITH CONDITIONS (NEEDS DISCUSSION on NEW-MAJOR-1 through NEW-MAJOR-5).**

All six R1 BLOCKING findings (B1–B6) are closed. Per-veto truth conditions are real CI mechanisms, not slogans. §15 reconciliations are rulings, not tensions. §16 ADR register has the requested 12 entries. Five new MAJOR findings issued (one notation collision, one cap-slack issue, one transparency issue, one CI-precision issue, one boundary-naming gap) and three MINOR. None of the new MAJORs are blocking because each has an obvious one-line fix.

**Grade: B (was C+).**

The jump from C+ to B is justified by:
- Six BLOCKING closures, none rhetorical.
- The veto-truth-condition pattern is the right primitive and is applied uniformly.
- L24 deletion (B2/B6) is the most difficult of the six and was done cleanly.
- Operational floor and Versioning Algebra are structurally correct.

Why not B+ or A-:
- NEW-MAJOR-1 (T# collision) repeats the exact disambiguation failure that R1 halmos B5 raised against v1 — within the very table that exists to prevent this.
- NEW-MAJOR-3 (3× expansion of V9 cap) is honest but unacknowledged.
- NEW-MAJOR-5 (executor atomicity not named as a boundary) is the kind of gap a 3am incident would expose.
- The 19/20 leaf-cap slack of 1 (NEW-MAJOR-2) is a known failure mode in this exact codebase.
- I would want a working CI repository (V1–V14 tests actually existing and green) before going above B.

R3 admission gate. Address NEW-MAJOR-1 through NEW-MAJOR-5 in `proposal_v3.md`. None require structural rework; all five are within one editor-pass. If addressed, B → B+ is reachable in R3 without further substantive changes.

---

**End of independent jane-street-cto closure check, Phase 3 Round 2.**
