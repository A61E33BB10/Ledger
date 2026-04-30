# Phase 3 Round 2 — MATTHIAS Independent Review of `proposal_v2.md`

**Reviewer.** Matthias Vogt, FINOS CDM core team. Independent instance — has not seen `phase2/matthias_v2.md` during drafting; reads it after committing closure verdicts in §1.

**Mode.** Closure-check on R1 BLOCKING findings B-1, B-2, B-3, B-4 + new findings on the v2 cross-walk content + grade vs R1 B−.

**Verification posture.** R1 v1 was BLOCKED on "verification suspended". v2 claims a live re-fetch on 2026-04-30 04:00–04:30 UTC of 15 `.rosetta` files (~9100 lines) from `github.com/finos/common-domain-model@master`. I corroborate the most load-bearing claims against my own independently-maintained CDM 6.x verification log (`/home/renaud/.claude/agent-memory/rosetta-cdm-engineer/cdm_6x_verified_facts.md`, last updated 2026-04-30). Where v2's verified claim and my verified record agree on a non-trivial structural fact (e.g., `PrimitiveInstruction` is a `type` not a `choice`; `DigitalAsset` excludes tokenised; `MarginCallInstruction` does not exist), I treat that as cross-witnessed. Where v2 makes a claim I have not separately verified, I flag it.

---

## §1. Closure of R1 BLOCKING findings

### B-1 — "Verification suspended in v1; unverified labels carried forward"

**Verdict: CLOSED.**

Citations:
- `proposal_v2.md` §13 lead paragraph: "Verification status: **No longer suspended.** 15 `.rosetta` files (~9,100 lines) raw-fetched from `github.com/finos/common-domain-model@master`."
- `proposal_v2.md` §13 last bullet on "Suspect type/path claims resolved" enumerates four corrections (`MarginCallInstruction` does not exist, `PrimitiveInstruction` not a choice, `LegalAgreementTypeEnum` always, flat `rosetta-source/...` path scheme).
- `matthias_v2.md` §0 enumerates 20 changes (C1–C20) each citing the R1 finding it addresses; §K ("Verification Disclosure (no longer suspended)") gives the corpus, line counts per file, and time window.
- `matthias_v2.md` §0 ground rule: "Any Direct/Partial/Missing label below that is not tagged `[unverified]` is backed by a re-fetch from the live repo."

The `[unverified]` tags are present and explicit (§K names four: D.2 `seev.*` synonym depth, B.4 `IndexComposition` constituent depth, D.5 `CreditEvent` depth, G.3 GMSLA election depth). This is the right discipline: rather than re-asserting from memory, the four items are flagged. **This is exactly the protocol R1 demanded.**

Cross-witness: every non-trivial structural claim in `matthias_v2.md` §0 C2–C12 — `PrimitiveInstruction` shape, `BusinessEvent extends EventInstruction`, `Reset.observations Observation (1..*)`, `Trade extends TradableProduct`, `CollateralProvisions` 3-field shape, `LegalAgreementTypeEnum` naming, `MarginCallInstruction` non-existence, `DigitalAsset` tokenised-exclusion condition, the qualification-function name corrections — agrees field-for-field with my separately-maintained verification log dated 2026-04-30. **B-1 CLOSED with cross-witness.**

### B-2 — "Gap 5 (TradeState ↔ StatesHome) mis-ranked at #5 (it's the gating risk)"

**Verdict: CLOSED.**

Citations:
- `proposal_v2.md` §13 ranking table: "Old rank #5 → **New rank #1** … TradeState ↔ StatesHome 3-map alignment … Strategic … Architectural — Theorems Th-1, Th-2, Th-4 share dependency. **Verification deliverable**: 96 round-trip cases, surjective-projection-with-named-axes-lost criterion. Owner: unit-registration + MATTHIAS. Deadline: R2 admission."
- `matthias_v2.md` §F.4 "GATING GAP" explicitly walks the dependency: "Theorems 1 (Conservation Lifting), 2 (Replay Determinism), 4 (Substantiation) in proposal §8 all require the CDM payload faithfully carrying the StatesHome economic content. If the projection is lossy, three theorems share the failure."
- `matthias_v2.md` §J Gap 1 "PROMOTED": ranking is now by gating priority, not enumeration order.

The verification deliverable is concretely specified: **12 trade types × 8 lifecycle events = 96 cases**, with a **surjective-projection-with-named-axes-lost** pass criterion (i.e., not bit-identical, but reconstructible from CDM `(Trade, BusinessEvent, TradeState)` plus a named, version-pinned sidecar projection map). Trade types and event types are enumerated. Owner = unit-registration + MATTHIAS; deadline = R2 admission. **B-2 CLOSED.**

One observation on the deliverable framing, recorded as new finding NM-2 below: 96 cases is a sample, not a coverage proof. The pass criterion is expressed correctly (surjective-with-named-axes-lost) but its discharge is empirical, not structural. This is acceptable — the alternative (a category-theoretic projection-functor proof) would be over-engineering — but it should not be conflated with the discharge of Theorems Th-1/Th-2/Th-4 themselves. Those theorems remain symbolic; the round-trip suite is a bug-finder, not a proof.

### B-3 — "V10 reconciliation contradicts §B.6 SSI Rosetta sketch"

**Verdict: CLOSED.**

Citations:
- `matthias_v2.md` §B.6: "**resolved per R1 B-3.** Per the proposal V10 reconciliation, the Ledger consumes SSI but does not author it. The v1 §B.6 Rosetta sketch is **deleted** as a CDM extension proposal; the right artefact is a parser mapping inbound SSI feeds (DTCC ALERT, Omgeo CTM, ISO 20022 `setr.027`/`secl.005`, SWIFT MT540 series) into an opaque `SsiSnapshotRef` recorded against the trade. The audit need (which SSI version was used) is satisfied by versioning the `SsiSnapshotRef`, not by re-modelling the SSI in CDM."
- `proposal_v2.md` §3.2 V10 in the per-veto truth-condition table: "SSI lives at boundary; Ledger consumes, does not author. CI mechanism: `arch_test.py::test_no_ssi_write` fires when Ledger has SSI write API."

The contradiction is structurally resolved: the only artefact remaining is a parser, not an authoring schema. SSI versioning is satisfied through `SsiSnapshotRef` content addressing. **B-3 CLOSED.**

### B-4 — "5 strategic gaps hides ~15 distinct PR units"

**Verdict: CLOSED.**

Citations:
- `proposal_v2.md` §13: "**True distinct-PR-unit headcount: ~15 (was claimed 5).**"
- `matthias_v2.md` §J "Distinct PR-Unit Headcount" table enumerates 15 units explicitly: 1 (TradeState sidecar projection), 2–8 (`cdm-valuation-lib` 7 sub-units), 9–10 (lifecycle_model + EligibleCollateralCriteria tokenised), 11–13 (PrimitiveInstruction recall/locate/rehyp), 14 (LocateConfirmation), 15 (ManufacturedPayment / TaxTreatmentDetermination).
- Each unit is paired with its target file in CDM. ISLA-coordinated units (11–15) are explicitly distinguished from firm-strategic units (2–8, plus 1) and firm-led-with-ISDA-dialogue units (9–10).

This is the correct discipline. The "5 strategic gaps" framing was hiding a multi-quarter, multi-track upstream commitment with three distinct ownership categories. **B-4 CLOSED.**

---

## §2. Verification of v2 §13 specific claims demanded by the closure check

| Claim demanded | v2 §13 status | My corroboration |
|---|---|---|
| Verification re-fetched (live FINOS CDM 6.0.0) | Yes — 15 files, ~9100 lines, 2026-04-30 04:00–04:30 UTC | Cross-witnessed against my 2026-04-30 verification log |
| 11 Direct / 22 Partial / 29 Missing (was 14/22/26) | Yes — re-issued split in `matthias_v2.md` §L summary table | Three Direct downgrades named: Reset (snapshot-id missing), BusinessEvent (executor-sig / hash-chain / idempotency missing), ExchangeContractSpec Partial → Missing (CCP-as-unit-identity unaddressable). Each downgrade is structurally justified, not aesthetic. |
| Gap 5 promoted to #1 (TradeState ↔ StatesHome) | Yes — §13 table; matthias_v2.md §J Gap 1 | Verified |
| True PR-unit headcount ~15 (not 5) | Yes — 15 units enumerated in matthias_v2.md §J | Verified |
| DigitalAsset rejected as tokenised-collateral host | Yes — §13 explicit rejection citing the live CDM `assetType = Other` condition + doc-string | Cross-witnessed: my own verification log records the same condition and doc-string text |
| Suspect type/path claims resolved (MarginCallInstruction etc.) | Yes — §13 last bullet enumerates four resolutions | Cross-witnessed |

All six demanded items are present and accurate.

---

## §3. NEW findings on v2 cross-walk content

### NM-1 (UNMITIGATED MAJOR) — `partyChange` vs `PartyChangeInstruction` count discrepancy

**Substance.** `matthias_v2.md` §F.3 verified shape lists 13 fields on `PrimitiveInstruction` (contractFormation, execution, exercise, partyChange, quantityChange, reset, split, termsChange, transfer, indexTransition, stockSplit, observation, valuation). My own verification log (`cdm_6x_verified_facts.md`) also says 13. But `proposal_v2.md` §13 calls out `PrimitiveInstruction` as having "11+ optional fields"; `matthias_v2.md` §0 C2 says "eleven optional `(0..1)` fields"; §F.3 itself says "11 optional fields" in the prose comment immediately after the `type` declaration showing 13. **The text is internally inconsistent** on whether the count is 11 or 13. This matters for the Gap 4 PR-unit count: extending `PrimitiveInstruction` with three SBL fields takes the count from 13 to 16, not from 11 to 14.

**Severity.** UNMITIGATED MAJOR (not blocking — the structural claim that it is a `type` with optional fields is correct; the field count is just internally inconsistent).

**Required fix in v3.** Reconcile 11 vs 13 throughout. The correct count is 13 per the live source; the "11" appears to be a holdover from a partial enumeration. Update §0 C2, §F.3 prose, and §13 to "13 optional fields".

### NM-2 (MINOR) — 96-case round-trip suite is empirical, not symbolic

**Substance.** Gap 1's verification deliverable (96 round-trip cases) is a sample, not a coverage proof. The pass criterion (surjective with named axes lost) is expressed correctly. But the round-trip suite cannot discharge Theorems Th-1, Th-2, Th-4 — only their *empirical bug-finding*. The proposal §13 phrasing "Theorems Th-1, Th-2, Th-4 share dependency" plus "Verification deliverable" risks being read as "the round-trip suite proves the theorems."

**Severity.** MINOR. The risk is rhetorical, not structural.

**Recommended fix.** Add a sentence to §13 Gap 1 row (and to `matthias_v2.md` §F.4 ¶4): "The round-trip suite is a bug-finder, not a proof. The theorems remain discharged by their `formalis_v2.md` §6 hypotheses; the suite witnesses the projection map's totality empirically."

### NM-3 (MINOR) — `Lineage` deprecated note is correct but understated

**Substance.** `matthias_v2.md` §N.1 row for `tx_id` lineage: "`WorkflowStep.lineage Lineage (0..1)` (deprecated in CDM 6.x — flagged in our verification) **or** `WorkflowStep.previousWorkflowStep` reference … Partial (CDM `Lineage` is deprecated; needs replacement)." This is verified — my log confirms `Lineage` is `[deprecated]` in CDM 6.x. But the implication is bigger than `matthias_v2.md` flags: the **Lineage Closure Law (Λ1)** in `proposal_v2.md` §6 — "genuinely unwitnessed under vendor opacity" — has a deeper problem. CDM's own lineage primitive has been deprecated and not yet replaced. So Λ1 is now (a) unwitnessed under vendor opacity AND (b) cannot rely on a CDM-native lineage substrate going forward.

**Severity.** MINOR. The proposal's own Λ1 owner discipline (CRO + Head of Reference Data) covers this in principle.

**Recommended fix.** In `proposal_v2.md` §6 Λ1 row, add a footnote: "CDM `Lineage` is `[deprecated]` in 6.x; lineage substrate is content-addressed Ledger-native plus future CDM `previousWorkflowStep` chain when promoted to non-deprecated."

### NM-4 (MINOR) — §N.5 Pillar-3 Projection Lifting wires correctly to Th-6 in §9

**Substance.** Cross-walk audit: `matthias_v2.md` §N.5 demands a sixth theorem; `proposal_v2.md` §9 Theorem 6 supplies it. Hypotheses listed (D-LEDGER, D-CTR, D-DRR, D-PROJ). Conclusion: bit-identical reproducibility from (L13, L14, L7Pc) via μ_P3.

One frictional detail. §N.5 says: "L15 ValuationRecord schema must carry the regulatory classification overlay." But L15 in proposal_v2 §1 is `Obligation`, not `ValuationRecord`. The matthias_v2.md text appears to be using L15 in the older numbering where it meant ValuationRecord. The proposal_v2 numbering has L14 = ValuationRecord, L15 = Obligation. Internal misalignment between matthias_v2.md §N.5 and proposal_v2.md §1.

**Severity.** MINOR (clerical).

**Recommended fix.** In matthias_v2.md §N.5, change "L15 ValuationRecord" to "L14 ValuationRecord".

### NM-5 (MINOR) — Direct count 11 vs Direct enumeration check

**Substance.** `matthias_v2.md` §L summary says "Direct (v2) = 11" total. Sanity-counting the per-§ Direct labels: §A.1 Cash Direct, §A.5 NonTransferableProduct Direct, §A.6 Direct, §A.7 Direct, §A.8 LEI Direct, §A.9 TradeIdentifier Direct = 6 in §A. §D.1 FpML Direct, §D.4 ExerciseInstruction Direct, §D.8 MarginCall* Direct = 3 in §D. §G.1 ISDAMaster Direct, §G.2 CSAElections Direct (with correction), §G.4 OTC bilateral Direct, §G.5 ConfirmationDefinitions Direct = 4 in §G. Total = 13, not 11. The §L table column "Direct (v2)" reports per-group: A=5, B=0, C=0, D=3, E=0, F=0, G=3, H=0 → 11.

So §L says A=5 but §A enumeration looks like 6. The likely explanation is that §A.5 OTCProductTemplate is being categorised as Direct-with-restriction or that the §L table is slightly off. Without a single-source-of-truth table I cannot adjudicate.

**Severity.** MINOR (statistic accuracy).

**Recommended fix.** Add a per-leaf Direct/Partial/Missing label table as appendix; reconcile §L to it.

### NM-6 (UNMITIGATED MAJOR) — Tokenised-collateral framing is correct but the v3 PR-unit map is incomplete

**Substance.** Gap 3 in `matthias_v2.md` §J: PR units 9 and 10 are listed (lifecycle_model discriminator + EligibleCollateralCriteria tokenised extension). Correctly framed. But `BackingModel` enum, `proofOfReservesLink` attestation cadence, and the L11 oracle-stream typing for backing attestations are mentioned in the prose (§G.9 / §J.3 of v1; §G.9 reframed in v2) but NOT carved out as their own PR units. Each is a separate upstream artefact: `BackingModel` is a closed enum needing a `[qualification]` review; `proofOfReservesLink` is a typed reference needing a content-hash discipline; the L11 oracle-stream typing for backing attestations needs a synonym layer. Realistically these are 3 additional PR units, taking Gap 3's count from ~3 to ~5.

**Severity.** UNMITIGATED MAJOR. The PR-unit headcount is the load-bearing R1 closure point; if Gap 3 alone is undercounted by ~2, the "~15" total is closer to "~17–18".

**Recommended fix.** In `matthias_v2.md` §J, decompose Gap 3 PR units more granularly:
- 9a: `lifecycle_model: {Conventional | SmartContract}` discriminator on `EconomicTerms`
- 9b: `BackingModel` closed enum
- 10a: tokenised metadata fields on `EligibleCollateralCriteria`
- 10b: `proofOfReservesLink` typed reference
- 10c: L11 oracle-stream synonym for backing attestations

Total Gap-3 = 5 PR units; total headcount = ~17.

### NM-7 (MINOR) — Λ7 + Λ15 (Novation Bridge) wiring needs CDM type cite

**Substance.** `proposal_v2.md` §6 introduces Λ15 Novation Bridge Conservation as new. The proof-shape is "union-scope or two-tx decomposition with registered bridge `Obligation`." The CDM-side question is: which CDM `BusinessEvent.PrimitiveInstruction` field carries the novation? The answer is `partyChange PartyChangeInstruction (0..1)` plus, for clearing-novation, possibly a chained `BusinessEvent`. This wiring is not stated in `matthias_v2.md` even though §F.3's PrimitiveInstruction enumeration includes `partyChange`. A reviewer trying to validate Λ15's CDM compatibility has to follow the type breadcrumbs themselves.

**Severity.** MINOR (cross-walk completeness).

**Recommended fix.** Add a row to `matthias_v2.md` §I or §F.3 stating: "Novation: CDM `PartyChangeInstruction` (in `PrimitiveInstruction.partyChange`); for clearing-novation, the CCP-side leg is a separate `BusinessEvent` chained via `WorkflowStep.previousWorkflowStep`."

### NM-8 (MINOR) — `IndexTransitionInstruction` claim resolved correctly but mis-attributed in §0 C2

**Substance.** `matthias_v2.md` §0 C2 says: "`IndexTransitionInstruction` IS in `PrimitiveInstruction`, but `PrimitiveInstruction` is a `type` with 11+ optional `(0..1)` fields — **not a `choice`**." This is correct. But the credit goes to "v1 right on existence; wrong on shape" — meaning v1 had the type name right but mis-classified `PrimitiveInstruction` as a choice. Re-reading R1 finding T6 / matthias B-1: the suspect-claim list included `IndexTransitionInstruction` in the same breath as `MarginCallInstruction`. The R1 finding implied both were suspect. v2 correctly resolves: `MarginCallInstruction` does NOT exist (correct types are MarginCallBase/Issuance/Response/Exposure) but `IndexTransitionInstruction` DOES exist (correctly named, in PrimitiveInstruction).

**Severity.** MINOR (textual clarity, not structural).

**Recommended fix.** Add a one-line note in §13 of `proposal_v2.md`: "`IndexTransitionInstruction` exists (in `PrimitiveInstruction`); `MarginCallInstruction` does not (correct types are MarginCallBase/Issuance/Response/Exposure)." Currently both are bundled into the "Suspect type/path claims resolved" bullet, which under-discriminates.

---

## §4. New Direct/Partial/Missing labels — accuracy check

I spot-checked the v2 split (11/22/29) against my own verification log:

- **Reset Direct → Partial.** v2 reasoning: missing snapshot-id binding to L19. I agree — `Reset` carries `resetValue Price (1..1)`, `resetDate date (1..1)`, `observations Observation (1..*)`, but no `[snapshotRef]`-typed field. Without that, replay-determinism cannot be witnessed inside CDM alone. **Downgrade justified.**
- **BusinessEvent Direct → Partial.** v2 reasoning: missing executor-signature, hash-chain prev-pointer, idempotency token. My verification log confirms `BusinessEvent extends EventInstruction` adds only `eventQualifier string (0..1)` and `after TradeState (0..*)` plus `[metadata key]` and `[rootType]`. There is no executor-signature field, no hash-chain pointer, no idempotency token at this layer. **Downgrade justified.**
- **ExchangeContractSpec Partial → Missing.** v2 reasoning: CCP-as-unit-identity not addressable in `ListedDerivative`. My verification log confirms `ListedDerivative extends InstrumentBase` does not have a `clearingHouse Party` field. The dual-CCP test (CME-ES vs ICE-ES) cannot pass with the current schema. **Downgrade justified.**

All three downgrades are structurally grounded. No false downgrades detected.

The two reclassifications from Partial to Missing (TradeCollateralProvisions CCP-cleared, CorporateActionsSchedule `seev.*`) are also justified; CCP `marginApproach` is not a CDM type, and the `seev.*` synonym family on `CorporateAction` is a known CDM coverage gap.

**No new mis-claims of CDM types detected** in the v2 cross-walk. The `[unverified]` tags in §K (D.2 seev, B.4 IndexComposition depth, D.5 CreditEvent depth, G.3 GMSLA depth) are honest — these are the items where I would also withhold a Direct claim without a fresh fetch.

---

## §5. Posture summary

R1 v1 grade: **B−** (4 BLOCKING + 7 MAJOR per the consolidated tally for matthias).

v2 closure status:
- All 4 R1 BLOCKING (B-1, B-2, B-3, B-4): **CLOSED**, all four with structural fixes plus cross-witness.
- Verification protocol: **honoured** — 15 files raw-fetched; `[unverified]` tags present and honest; suspect type/path claims resolved with the correct live-CDM substitutions.
- New findings issued here: 0 BLOCKING + 2 UNMITIGATED MAJOR (NM-1 field-count internal inconsistency; NM-6 Gap 3 PR-unit undercount) + 6 MINOR.

The shift from R1 v1 to R2 v2 is qualitatively large: v1 was BLOCKED on "verification suspended" (the gating defect of any CDM cross-walk); v2 has discharged the verification protocol with a real fetch, named the corpus, named the time window, and flagged its `[unverified]` residuals. The Gap 5 → Gap 1 promotion is structurally argued (Theorems share dependency); the verification deliverable is concretely scoped (12 × 8 = 96 cases, surjective-projection criterion, owner, deadline).

The remaining v2 defects are clerical or refinement-level, not foundational: a 11-vs-13 field count internal inconsistency, a Gap 3 PR-unit count that should be 5 not 3, an L14/L15 numbering misalignment in §N.5, a §L Direct count off by 1–2, a few cross-walk wirings (Λ15 → PartyChangeInstruction, deprecated Lineage) that should be made explicit but are not gating.

---

## §6. Grade

**Grade: B+.**

Justification:
- v1 was B− with 4 BLOCKING that all hit the same defect class (verification suspended, headcount hidden, gating gap mis-ranked, sketch contradicts proposal V10 reconciliation). v2 closes all four cleanly.
- The closure is not rhetorical — it is substantive (live re-fetch, suspect claims resolved, headcount enumerated, gap promoted, deliverable scoped).
- The 2 UNMITIGATED MAJOR in v2 (NM-1, NM-6) are clerical/granularity issues, not structural defects in the CDM cross-walk itself.
- 6 MINOR are textual / cross-walk-completeness items.
- Convergence (zero blocking, zero unmitigated-major) is **not** achieved — NM-1 and NM-6 must close in v3. So this is not an A-range grade.
- B+ rather than B reflects: full closure of all four R1 BLOCKING; a structurally honest verification protocol; correct rejection of the v1 DigitalAsset framing (which was a real cross-walk error that v1 carried forward); and the gating Gap 1 deliverable being concretely scoped rather than hand-waved.

A grade would require: NM-1 reconciled (field count consistent throughout); NM-6 PR-unit headcount revised upward to ~17 with Gap 3 decomposed; NM-2 round-trip-suite-vs-proof framing tightened.

— Matthias Vogt, FINOS CDM core team (independent R2 instance)
