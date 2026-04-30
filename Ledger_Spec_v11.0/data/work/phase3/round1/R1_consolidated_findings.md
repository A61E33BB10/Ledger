# R1 Consolidated Findings — Brief for Data Team

**Source.** Phase 3 Round 1 adversarial reviews of `phase2/proposal_v1.md` by 19 independent reviewers.
**Reviewer roster.** cartan, correctness, feynman, finops, formalis, geohot, grothendieck, halmos, isda, jane_street, karpathy, lattner, matthias, minsky, nazarov, noether, sbl, temporal, testcommittee.
**Author.** Phase-3 consolidation pass; not a re-review. Where a finding is convergent (≥3 reviewers), reviewers are listed in parentheses; where singular and load-bearing, the reviewer is named.

---

## §0. Round 1 verdict

### Grades

| Reviewer | Grade |
|---|---|
| cartan | C+ |
| correctness | B+ |
| feynman | B+ architectural / **D** constructive readiness (uses 2 axes) |
| finops | D+ |
| formalis | C+ |
| geohot | C+ |
| grothendieck | C+ |
| halmos | D+ |
| isda | B− (would rise to A− if B-1, B-2 fixed) |
| jane_street | C+ |
| karpathy | C+ |
| lattner | B |
| matthias | B− |
| minsky | C+ |
| nazarov | B− |
| noether | C+ |
| sbl | C+ |
| temporal | C− |
| testcommittee | C− |

### Summary statistics

- **Average grade.** Approximately **C+ / C+/B−** (numerically, on a 4-point scale where A=4, B=3, C=2, D=1, plus/minus = ±0.3): mean ≈ 2.18 (i.e., C+).
- **Distribution.** A: 0. B-range: 4 (correctness B+, feynman B+ on architectural axis, isda B−, lattner B, matthias B−, nazarov B−) = 6 if isda/matthias/nazarov B− counted as B-range. C-range: 11 (cartan, formalis, geohot, grothendieck, jane_street, karpathy, minsky, noether, sbl, temporal, testcommittee). D-range: 3 (finops D+, halmos D+, feynman constructive readiness D).
- **Modal grade. C+.** No reviewer awarded an A. Only one reviewer (lattner) gave a clean B; correctness gave B+ but with 4 BLOCKING findings stipulated.

### Convergence verdict (per FORMALIS arbiter criteria — zero blocking, zero unmitigated major)

**NOT CONVERGED.** Every reviewer who returned a count reports BLOCKING findings; the median reviewer reports 3-4 blocking findings and 6-7 unmitigated-major findings. By FORMALIS' own §6 ruling (in this round's review): "Convergence: not yet achievable." This is the dominant verdict. ISDA, finops, matthias, temporal, sbl, testcommittee, jane_street, geohot all explicitly state "convergence not achieved."

### Total finding counts (across all 19 reviewers, raw — duplicated themes counted once per reviewer)

| Severity | Count | Notes |
|---|---|---|
| **BLOCKING** | ≈ 79 | Range 2–8 per reviewer; finops 7, jane_street 6, feynman 8, matthias 4, temporal 3, formalis 7, testcommittee 7, etc. |
| **UNMITIGATED MAJOR** | ≈ 130 | Range 4–17 per reviewer; testcommittee 17, temporal 15, finops 9, formalis 6, sbl 7. |
| **MINOR** | ≈ 130 | Range 5–11 per reviewer. |

After convergence (themes raised by ≥3 reviewers), the load-bearing pattern collapses to **~12 convergent themes** + ~25 singletons. See §1.

---

## §1. Convergent themes (≥3 reviewers)

For each theme: name, reviewers raising it, max severity, concrete fix required for `proposal_v2.md`.

### T1. Leaf-count inflation; vetoes V8/V9/V10/V11 rhetorically laundered

**Reviewers (≥9).** geohot, jane_street, formalis, grothendieck, lattner, isda, matthias, halmos (B5 L-prefix collision related), nazarov (M-4 L24 instability).
**Max severity.** BLOCKING (geohot B1/B2/B3, jane_street B1/B2/B3/B4/B5/B6, formalis B7 implicit via L7/L23, grothendieck B3 "no universal property", lattner B3 "L24 fence rhetorical").
**Substance.** 24 leaves cannot be defended on a universal-property basis; jane_street's 7-sector ceiling is silently violated; FORMALIS independently lands at 16; the §9.2 reconciliations of V8 (CDM enum closure → L21 leaf), V9 (Policy → L7 leaf "≤30 fields" with no enforcement), V10 (SSI → L5 leaf with `ssi-ingest` workflow), V11 (orchestration → L24 leaf with 7 invariants and CORRECTNESS L10 participation) re-admit the abstractions the vetoes deleted. Pattern: name the veto, keep the leaf, attach qualifying language, declare reconciled.

**Required fix.** proposal_v2 MUST do one of:
1. **Collapse to ≤16 leaves** (FORMALIS-aligned). Specifically: delete L4 (fold into L2), L5 (boundary parser, not leaf), L7 (constants module + L21 pin), L17 (field on observations), L18 (field on L1), L20 (cross-cutting field), L22 (field on L14), L24 (V11; not economic). Reclassify L19 as a named view. **OR**
2. **Per-leaf ADR override.** For each leaf beyond the FORMALIS-16, produce an Architectural Decision Record citing a v10.3 / addendum / valuation claim that no member of the smaller set discharges. The ADR must name the rejected veto and justify the override.
3. **Delete the "tension box" / "thin sidecar" rhetorical pattern.** Per jane_street M2: "the tension box format is a forbidden output for proposal_v2."
4. **Enforce the ≤30-field cap on L7 structurally** (CI schema-length check) or remove the cap. Same for any other field-count budget.

### T2. Compositional theorems §8 are theorem-shaped, not theorems

**Reviewers (≥6).** cartan (B1, B2, B3), formalis (B1–B5), correctness (A.1–A.3 closure failures), grothendieck (M5 "calibration is an adjunction; theorem hides this"), noether (B2 "Conservation Lifting does not compose under three of seven fault classes"), matthias (M-5 "three theorems share Gap-5 dependency").

**Max severity.** BLOCKING.

**Substance.** Each theorem listed in §8 has at least one defect:
- **T1 Conservation Lifting:** circular — D-CONS as stated forbids issuance, but conclusion permits it (formalis B1, cartan B2). Does not compose under mis-attributed / silent-corruption / partition fault classes (noether B2). Does not handle multi-CCP novation (correctness A.2). Does not address P18 SBL buy-in carve-out (sbl Finding 13).
- **T2 Replay Determinism:** silently consumes E-WF (workflow determinism) as both axiom and conclusion (formalis B2). Cross-system property pretending to be a Ledger property (jane_street M4). Lattner notes the same on B3 / L24.
- **T3 Obligation Liveness:** ∀ t > t_d quantifier admitted unwitnessable in §9.4 — the theorem is therefore an axiom of the realism budget, not a theorem (cartan B2, formalis B3 κ-totality undefined).
- **T4 Substantiation:** restated as its own hypothesis (formalis B4 "definition, not theorem"). Conflates detection with recovery (correctness E.4). Conflates projection with audit-grade evidence (lattner m7).
- **T5 No-Arbitrage Pricing:** Θ_AF undefined as a closed type; model-version-specific (formalis B5).

**Required fix.** Each theorem re-issued with: (i) all hypotheses individually numbered and stated, (ii) all quantifier ranges explicit (universe, finiteness, time horizon), (iii) initial-state / base-case hypothesis explicit, (iv) the conclusion's equality predicate precisely defined (bit-equal vs decimal-equal vs observational), (v) any circular dependency on another theorem made explicit and resolved by cut-elimination or simultaneous induction, (vi) cross-system theorems explicitly framed as joint Ledger × Temporal properties. T3 must be either bounded by a horizon T_max or reclassified as an axiom. T4 must split into definitional T4a and theorem T4b (cache-vs-source-of-truth) with the cache invalidation discipline named.

### T3. Foundational layer missing — no formal definitions / ambient types / hypothesis lists / notation table

**Reviewers (≥6).** cartan (B1 "no formal definitions"), halmos (B1 "no notation table", B2 "forward references", B3 "bitemporal not defined"), formalis (Specification gate "Partial"), karpathy (M2 "bitemporal mandatory but never defined"), feynman (BLOCKING-G4 "bitemporal axes named but not arithmetic"), minsky (F9 parser totality, F10 canonical-serialise unspecified).

**Max severity.** BLOCKING.

**Substance.** The proposal is a navigation document, not a specification. There is no §0.5 Notation table. The L-prefix is overloaded **three** ways (NAZAROV L1–L24 leaves; CORRECTNESS L1–L14 laws; FORMALIS L1–L16 leaves), and the §3 "Part of L8" annotations refer to FORMALIS' L8, not NAZAROV's L8 UnitStatus (halmos B5). Bitemporal axes (`t_obs`, `t_known`) are invoked pervasively but never defined arithmetically — resolution, time zone, tie-break, restate-link discipline, query API are all missing (feynman BLOCKING-G4, karpathy M2, halmos B3). StatesHome C-indices (C2, C4, C11) are referenced authoritatively but defined only by external reference (halmos B4). Per-leaf "min fields" lists are ambiguous about completeness (cartan M5).

**Required fix.** proposal_v2 MUST include:
1. **§0.5 Notation table.** Every symbol, type, and code prefix with meaning and first-use section. Disambiguate L-prefix: `L#` (NAZAROV leaves) ≠ `Λ#` (CORRECTNESS laws) ≠ `Φ#` (FORMALIS leaves).
2. **§Definitions** appendix (cartan B1). For each leaf: ambient sets/types of every component; the leaf's carrier as refinement / sum / product; the well-formedness predicate.
3. **§Bitemporal definition.** `Bitemporal<T>` type with concrete axis types, tie-breakers, restate-link discipline, query API. 5-line normative definition with one worked restatement example (karpathy M2).
4. **§Glossary** for StatesHome C-indices, NOETHER, GROTHENDIECK, pricing DAG, mandate-as-unit, QIS, KIKO, FpML vs CDM relationship (karpathy m4, halmos m5).

### T4. Operational floor missing — reconciliation pairs, break-management FSM, audit-trail lineage cursor, retention horizons, IPV, SLAs

**Reviewers (≥4).** finops (B1–B7 entire BLOCKING set), isda (B-1 regulatory submission, UM-3 dual-sided reporting), nazarov (M-1 trust registry artefact, M-6 malformed envelope), lattner (M4 unwitnessed laws unlinked to monitoring posture).

**Max severity.** BLOCKING.

**Substance.** §3 leaf entries describe what each leaf *is* but not what it *reconciles to*, with what cadence, under what tolerance, owned by whom. There is no break-management state machine (finops B2). Audit-trail traceability from L14 to source attestations is asserted (Theorem 4) but no queryable lineage cursor is specified (finops B3). Retention horizons (SOX 7y, MiFIR 5y, CFTC Part 49 "life of swap + 5y", BCBS 239 through-the-cycle, GDPR conflict) are folded into a single C-A10 (finops B4). IPV / FRTB AVA / fair-value-level field absent from L15 (finops B5). T+1 / T+0 SLA constraints unaddressed (finops B6). CSDR penalty regime has no first-class home (finops B7). Trust-assumption registry described as deliverable but artefact unspecified (nazarov M-1). Malformed L17 envelope handling unspecified (nazarov M-6).

**Required fix.** proposal_v2 MUST add:
1. **§3.X Reconciliation pair** line on every leaf in C1, C4, C5 + L8, L9, L16: `(external_authoritative_source, cadence, tolerance, break_management_workflow_id, control_owner)`.
2. **L25 BreakRegister** (or merge into L16) with full FSM `OPEN → INVESTIGATING → ASSIGNED → AGED-1/3/5 → ESCALATED → AT-RISK → MATERIAL → CLOSED-CLEAN | CLOSED-ADJ | CLOSED-WAIVED`, mandatory four-eyes on `CLOSED-WAIVED`.
3. **§4.X Lineage Cursor.** Typed graph projection over (L14 ⊕ L13 ⊕ L10 ⊕ L11 ⊕ L19 ⊕ L17 ⊕ L21 ⊕ L23) with materialised forward and reverse edges.
4. **§6.X Retention matrix.** Per-leaf × per-regulation table with horizon, hot/archival, deletion conditions, GDPR-conflict resolution rule. Bind to L21 so retention-policy change is itself versioned.
5. **§4.Y Tempo and SLA matrix.** Per-leaf p50/p99 ingress SLA, degraded-mode behaviour, DORA RTO/RPO.
6. **L15 ValuationRecord schema extension.** Add `(fair_value_level ∈ {1,2,3}, ipv_status, ipv_variance, ipv_source_id, prudent_valuation_adjustment_components: {market_price_uncertainty, close_out_cost, model_risk, concentrated_position, future_admin_costs, early_termination, operational_risk}, unobservable_inputs[], unobservable_input_sensitivity[])`.
7. **Trust-assumption registry contract.** Schema, review cadence, kill-switch per assumption (nazarov M-1).
8. **CSDR penalty.** Either explicit `obligation_type = CSDR_PENALTY` with full schema, or named gap with owner.

### T5. Regulatory submission / DRR layer entirely absent — direction-of-travel misalignment

**Reviewers (≥4).** isda (B-1, UM-1, UM-3, UM-4), finops (B1 implicit via reconciliation, B4 retention), matthias (B-2 Gap-5 mis-ranking architectural), sbl (Finding 2 BLOCKING — SFTR/SLATE rejected today).

**Max severity.** BLOCKING.

**Substance.** The 24-leaf spine has no leaf for outbound regulatory submission (DRR-CFTC, DRR-EMIR, DRR-SFTR, MiFIR RTS 22, SLATE, FRTB Pillar 3). L21 VersionPin does not pin DRR rule-set version separately from `cdm_version`, breaking replay determinism for regulatory submissions. ISDA Notices Hub (live July 2025) and ISDA Create not surfaced in §3. Dual-sided vs unilateral reporting reform (ISDA's 2025 ESMA response) silently inherited as current dual-sided. SBL Top-5 Gap #2 (SBL Recall/Locate/Rehyp CDM-missing) has no runtime contract; SLATE 24-required-fields / SFTR Article 15 disclosures unsourced.

**Required fix.** proposal_v2 MUST add:
1. **L25 RegulatorySubmission** in C5 Effects: `submission_id, regulator, rule_set, rule_set_version (DRR git_sha pin via L21), payload (CDM-native), tx_id lineage to L14, acknowledgement_status, bitemporal restatement chain`. Realism class U1, U2, U4, U6.
2. **L21 schema extension.** Add `drr_rule_set_version: Map<RegulatorRuleSet, GitSha>` axis distinct from `cdm_version`.
3. **Position statement** on dual-sided vs unilateral reporting; design L25 to support cutover.
4. **Sixth compositional theorem** Pillar-3-Projection-Lifting (L14 + L15 + L7 → DRR-Pillar3 input). Cost-free architectural commitment; the omission concedes ground.
5. **ISDA Notices Hub** as L11 sub-leaf (or named TEMPORAL awkward-fit row).

### T6. CDM cross-walk verification was suspended; gap-rank inverted; "Direct" claims unverified

**Reviewers (≥3).** matthias (B-1 verification suspension, B-2 Gap-5 mis-ranked, B-4 PR-unit headcount, M-1 through M-6, M-7), isda (B-1 / UM-5 CDM-type granularity vs internal), feynman (BLOCKING-G1 canonicalisation feeds U3/U4/U5/U8 simultaneously), sbl (Finding 2 SFTR/SLATE).

**Max severity.** BLOCKING.

**Substance.** Phase-2 matthias.md closes with "I have not re-fetched every cited file from the live repo." The proposal §3 / §7 inherits Direct/Partial/Missing labels without flagging the suspension. Of the **5 strategic gaps**, only 2 are genuinely strategic CDM gaps; Gap 4 is a Ledger-internal discipline, Gap 2 is operational (ISLA-owned), Gap 3 is significant but partially closable with `DigitalAsset`. The headcount "5 strategic" hides a true distinct-PR-unit count of ~15. Gap 5 (TradeState ↔ StatesHome alignment) is the **gating** risk — Theorems 1, 2, 4 all share its dependency — but ranked last in §7. Suspect type/path claims include `MarginCallInstruction`, `IndexTransitionInstruction`, `LegalAgreementType` vs `LegalAgreementTypeEnum`. `Reset` and `BusinessEvent` Direct claims do not carry snapshot-id / executor-signature / hash-chain pointer; on corner-case audit they downgrade to Partial.

**Required fix.** proposal_v2 MUST:
1. **Re-fetch all `.rosetta` paths** cited in matthias.md §A–§H against live CDM 6.0.0; re-issue Status labels.
2. **Promote Gap 5 to top of §7.** Make admission conditional on NS1–7 re-mapping with named criteria: trade/event corpus to round-trip, projection-equivalence criterion (bit-identical vs surjective vs lossy-with-named-axes), owner, deadline.
3. **Re-issue §7 with true distinct-PR-unit headcount** (~15 not 5).
4. **Re-classify gaps:** 2 strategic CDM, 1 significant via DigitalAsset extension, 1 operational ISLA, 1 Ledger-internal.
5. **Audit `Reset` and `BusinessEvent`** for snapshot-id / executor-signature / hash-chain support; downgrade to Partial if confirmed.

### T7. L13 calibration consumes L10 with no aggregation gate; surrogate witnesses are retreats

**Reviewers (≥3).** nazarov (B-1 N8 gate missing; B-3 N5 dispute resolution insufficient for L1/L4/L8/L13), formalis (B6 "4 unwitnessed laws mis-classified"), correctness (A.1 L1 not closed under FSM × snapshot retention; B-1 silent-corruption fault no harness; D-3 no bugification), testcommittee (F15/F16 U1 and U2 recoverable via TLA+ / induction; surrender unearned), feynman (MAJOR-J5 surrogates not equivalent to laws), geohot (M1 surrogates are vocabulary trick), karpathy (M4 surrogate parameters absent), lattner (M4 unwitnessed laws unlinked to monitoring).

**Max severity.** BLOCKING.

**Substance.** Two distinct issues conflated:
1. **L13 ingest:** L10 rows admitted to a snapshot consumed by Kalman calibration are not gated on N8 multi-source aggregation. Single-source rows with valid envelopes pass; this is the silent vendor trust the bar forbids (nazarov B-1).
2. **Unwitnessed laws (L1, L4, L8, L13).** The proposal labels four laws "unwitnessed" and offers "surrogate strategies." Of the four:
   - **L13 (liveness)** and **L4 (bitemporal)** are *recoverable*: liveness via TLA+ Büchi automata or RuleBasedStateMachine; bitemporal as a safety property decidable by induction (testcommittee F15, F16; formalis B6).
   - **L8 (cosmic-ray)** is recoverable with explicit ε from storage primitives (formalis B6 reclassify as witnessable with bound ε).
   - **L1 (vendor opacity)** is genuinely unwitnessed; the surrogate is a *reduction* not a *witness* (formalis B6 Huet quote).

Surrogate parameters (consensus quorum, bounded chain length, erasure-coding `(n, k)`, bounded-horizon length) are nowhere specified (karpathy M4). No production observability is named for surrogate violation in flight (lattner M4).

**Required fix.** proposal_v2 MUST:
1. **N8 aggregation gate.** L10 rows admitted to L19 snapshots consumed by L13 MUST have passed multi-source aggregation OR carry an explicit `single_source_authority_assumption_ref` to the trust registry. Add `aggregation_outcome: {multi_source_consensus | unique_authority | quarantined}` to L19 canonical content (nazarov B-1).
2. **Restructure §9.4 / §5 unwitnessed laws** into:
   - *Genuinely unwitnessed (1 law):* L1. Surrogate is a reduction; named owners accept residual risk.
   - *Witnessed via composition (3 laws):* L4 (bounded by retention horizon, decidable by induction), L8 (bit-flip detection probability bounded by ε function of erasure-coding parameters), L13 (TLA+ liveness check + bounded-horizon simulation).
3. **Specify all surrogate parameters** (consensus quorum, retention horizon, erasure-coding `(n,k)`, bounded simulation horizon). Pin in L7 / L21.
4. **Production observability spec** per surrogate: metric, threshold, alert, runbook.

### T8. L21 VersionPin conflates 5 axes; canonicalisation undefined; idempotency keys inconsistent

**Reviewers (≥4).** lattner (B1 "five axes silently conflated"), feynman (BLOCKING-G1 canonical_serialise undefined; BLOCKING-G3 idempotency keys inconsistent; BLOCKING-G8 L7/L21 circular dependency), minsky (F10 canonical-serialise unspecified), temporal (M-5 / M-8 canonical serialisation algorithm not pinned, B-2 `tx_id` includes `run_id`), correctness (B.1 floating-point boundary B13, B.2 storage iteration order B14).

**Max severity.** BLOCKING.

**Substance.**
- **Five axes conflated:** L21 conflates (a) component version, (b) CDM/ISO/FpML schema, (c) smart-contract version, (d) model version, (e) reference-data version — each with different mutation discipline, restatement semantics, migration cost. No composition rule for replay states which axes must be pinned for which invariant (lattner B1).
- **canonical_serialise undefined:** load-bearing for `unit_id`, `snap_id`, `tx_id`, `attest_id`, `prev_hash`, snapshot key, idempotency-token namespaces. Two implementations diverging on JSON canonicalisation / Protobuf field-tag order / CBOR profile / decimal normalisation produce different hashes for the same logical payload. Every cross-implementation replay claim is rhetorical until pinned (feynman BLOCKING-G1).
- **Idempotency keys inconsistent:** L1 uses `version_seq` (producer-supplied → not idempotent under concurrent submission); L13 uses wall-clock `certification_timestamp` (cannot be content-addressed); L14 `tx_id` per temporal B-2 includes Temporal-assigned `run_id` (changes on ContinueAsNew → idempotency bypass).
- **L7 / L21 circular:** L7 is governed by L21 and L21's content (cdm_version, model_version, L7_version) is governed by L7. No bootstrap rule.

**Required fix.** proposal_v2 MUST:
1. **§3.6.1 Versioning Algebra.** Five axes named separately (`component_pin`, `schema_pin`, `contract_pin`, `model_pin`, `refdata_pin`), each with mutation discipline, restatement semantics, witness-of-correctness predicate. Composition rule per invariant. Migration story (e.g., CDM v6 → v7).
2. **Pin a specific canonicalisation** (RFC 8785 JCS / Protobuf canonical with field-tag pin / CBOR per RFC 8949 §4.2.1). Add `canonicalisation_version` enum to L21. Add `C-A11 canonical-serialiser stability` to realism budget (minsky F10).
3. **Per-leaf idempotency-key classification:** content-addressed vs mint-on-arrival. State which laws (L8, U3) tolerate which class. Fix L1 (drop `version_seq` from key), L13 (drop wall-clock timestamp), L14 `tx_id = hash(business_event_id, attempt_seq)` — no `run_id` (temporal B-2).
4. **Resolve L7/L21 bootstrap** via `L7@genesis` entry in L22 hash-chain anchor; later L7 updates as L14 transactions.
5. **Add boundaries B13 (floating-point determinism), B14 (storage iteration order), B15 (intra-handler concurrency), B16 (Unicode/locale), B17 (test-environment).** 12 → 17 boundaries, with structural-unreachability justification for any number lower (correctness §B).

### T9. §3 per-leaf entries compress sub-leaves; SBL collapses 14 sub-leaves to 2 lines

**Reviewers (≥3).** sbl (Finding 1 BLOCKING — 14 sub-leaves elided), karpathy (B1 "no end-to-end loader; B2 reading 7 files required"), halmos (M1 "no examples"), feynman (MAJOR-J4 "no minimum complete example").

**Max severity.** BLOCKING.

**Substance.** §3 entries are 6-line stubs (N/M/T/R/F/C) pointing at specialist files. For SBL, this elides 14 first-class data items (LocateReservationLedger, CascadeRecallState, RehypCapCounter, RegulatoryReportingCursor, BorrowFeeQuote, RebateRateFix, ManufacturedPaymentRate, RQVSnapshot, MMFNAV, LocateConfirmation with regulatory_basis, BuyInEvent, TripartyAgreement, AgentLenderDisclosure, P18 buy-in carve-out). For other classes, no end-to-end worked example exists from wire-format → parsed type → storage row → projection. A junior engineer cannot ship from this; reviewers cannot resolve disagreements without a shared concrete anchor.

**Required fix.** proposal_v2 MUST:
1. **One worked end-to-end example per class (C1–C6)** — concrete bytes / schemas at every step. Show wire-format → parsed type → storage row → projection round-trip (karpathy B1, halmos M1, feynman MAJOR-J4).
2. **§3.3a SBL sub-leaf register** lifting sbl.md §§1–6 entry-by-entry as numbered sub-leaves L9.1–L9.14 / L11.1–L11.7, with 5-line block per item (field set / CDM status / regulatory regime / lifecycle event / coordinate touched).
3. **Inline §5 Fault catalogue** (49 cells, currently a stub pointing at correctness.md).
4. **Resolve L8/L9/L15 boundary cases** (halmos D1–D3): nav index ownership; ObligationStateEnum case; ValuationRecord vs UnitStatus FSM ownership.

### T10. Goodhart traps named but not actually trapped

**Reviewers (≥3).** correctness (C.1 stub-swap not avoided, C.3 biased generators not avoided, C.5 NEW trap "type-system witness laundering"), testcommittee (C.2 mutation operators incomplete, C.3 BLOCKING — no per-stratum coverage targets, C.4 aggregation-masking not trapped), geohot (M1 "surrogate witnesses is a vocabulary trick").

**Max severity.** BLOCKING.

**Substance.**
- **Snapshot stub-swap:** P-L8 byte-identical replay tests the *generator's* snapshot, not the *production* snapshot store. Production stub-swap goes undetected (correctness C.1).
- **Biased generators:** no coverage targets per stratum; Hypothesis defaults under-explore arbitrage-near-boundary, deadline-near-fire, multi-CCP, cross-currency QIS with manufactured payments (correctness C.3, testcommittee F-06).
- **Type-system witness laundering (NEW):** Python phantom types are nominal at runtime; the type-witness story collapses to "we trust the developer" (correctness C.5). Witness types (`arbitrage_certificate`, `snapshot_certificate`) are named but their construction site, consumer obligations, elimination sites are not enumerated (minsky F13, karpathy B3).
- **Aggregation-masking:** §6 trap #4 named not trapped — no meta-property test (testcommittee C.4).
- **Mutation operators incomplete:** missing M-FAKE-CERT, M-AGGREGATE, M-DEFLATE, M-BIAS, M-SHRUG-RETRY (testcommittee C.2). No mutation-survivor reporting; no per-stratum kill rate.

**Required fix.** proposal_v2 MUST:
1. **Boundary-integrity production test.** Pull N committed transactions from production snapshot store; replay; assert byte-identical. (correctness C.1).
2. **Per-stratum coverage targets.** e.g., 5% of `gen_market_snapshot` near arbitrage boundary; 10% of `gen_obligation` deadline-within-current-sim-clock+δ; 10% multi-CCP; 5% manufactured-payment-cross-jurisdiction. Coverage targets are first-class assertions (correctness C.3).
3. **Witness type construction inventory.** Per witness type: constructor site, consumers, what witness existentially asserts. Runtime checker fires on every write attempt; Hypothesis test adversarially attempts violation (correctness C.5, minsky F13).
4. **Add mutation operators** M-FAKE-CERT, M-AGGREGATE, M-DEFLATE, M-BIAS, M-SHRUG-RETRY. Mutation-score reports must list survivors (testcommittee C.2).
5. **Aggregation-masking meta-property test** in property catalogue (testcommittee C.4).

### T11. Trust-assumption owners are job titles, not people; observability missing

**Reviewers (≥3).** nazarov (M-1 registry artefact unspecified, M-2 C-A1/C-A2 owners "TBD", §6 only 5 of 10 genuinely owned), jane_street (M5 realism budget owners cross system boundaries without explicit handoff; six of ten conditional guarantees owned outside Ledger team without operating contract), lattner (M4 unwitnessed laws unlinked to monitoring posture).

**Max severity.** UNMITIGATED MAJOR.

**Substance.** §6 lists C-A1–C-A10 with owners. Five are job titles ("head of cryptography (or external advisor)", "head of security operations", "per-vendor relationship owner", "identity-and-trust operations", "architecture review board"). For each conditional guarantee, the proposal names neither the **detection signal** that fires when the assumption is broken, nor the **compensating action** during the failure window, nor the **blast radius** (what economic invariants fail open). The trust-assumption registry is described as a deliverable but the artefact (schema, review cadence, kill-switch) does not exist. C-A9 is owned by "TEMPORAL" — a system, not a team.

**Required fix.** Per conditional assumption, proposal_v2 MUST add three fields beyond owner: (a) detection signal, (b) compensating action, (c) blast radius. Specify the trust-assumption-registry contract: schema, review cadence, kill-switch per assumption (nazarov M-1). For C-A1 / C-A2, either name an external interim ratifier with concrete identity, or mark OPEN with "production deployment blocked on assignment" (nazarov M-2). C-A9 owner must be a person on a team, not a tool.

### T12. Symmetry / clock authority / S3 carrier missing; bitemporal modes unspecified

**Reviewers (≥3).** noether (B1 Time/Clock authority not a leaf — S3 carrier missing; B4 holiday-calendar bitemporal mode unspecified), formalis (M2 retroactive calendar amendment incoherent), temporal (M-1 retroactive calendar policy not bound).

**Max severity.** BLOCKING.

**Substance.** Three bitemporal modes for retroactive calendar amendments (pin-at-deal-time, pin-at-projection-time, pin-at-now) are non-equivalent; only mode 1 preserves S3 (time-translation invariance of contractual rules). The proposal asserts S3-style replay determinism but does not commit to a mode. Time/Clock authority is the carrier of S3 — every `t_known` depends on a clock with no version pin, leap-second policy, NTP/PTP source, signed assertion (noether B1). The 12 master symmetries S1–S12 lack a registered carrier matrix.

**Required fix.** proposal_v2 MUST:
1. **L25 ClockAuthority** (or fold explicitly into L21): `(authority_id, source_kind ∈ {NTP, PTP, GNSS, atomic}, leap_second_policy_version, attested_offset, attestor_signature, t_known)`. Every `t_obs` and `t_known` references it.
2. **Pin mode-1** for calendar amendments. Encode `calendar_version_pin` in L1 ProductTerms; forbid amendments from changing already-pinned schedules; calendar republication produces new bitemporal record but does not invalidate prior pins.
3. **§2.4 Symmetry-to-leaf carrier matrix.** S1–S12 (or extended) on a page with named leaf carrier per symmetry.
4. **Calendar orchestrator** specification (temporal M-1): bounded ContinueAsNew payload (paginated affected-unit set), fan-out rate-limiting, timer-fired-before-amendment policy.

---

## §2. Per-section change list for `proposal_v2`

Ordered by severity within each section.

| Proposal section | Finding | Source reviewer | Severity | Required change |
|---|---|---|---|---|
| §0 Executive | "Every other count maps cleanly into 24" — anchor 1 unsupported | cartan m7, grothendieck B3, geohot M2, jane_street B1 | BLOCKING | Drop "canonical" claim or state universal property (T1) |
| §0 Executive | Anchor 5 vetoes-honoured claim is unaudited | jane_street M1 | UNMITIGATED MAJOR | Per-veto V1–V14 audit, with section reference per honour/violation |
| §0 Executive | Forward references to NAZAROV's spine, MoveStream, bitemporal, CDM v6.0.0, N1–N12, P1–P10, V1–V14, fault clusters, v10.3 paragraphs not yet introduced | halmos B2 | BLOCKING | Move §1+§2+glossary before §0 or rewrite §0 self-contained |
| §0.5 (NEW) | Notation table absent | halmos B1, cartan B1 | BLOCKING | Add notation table; disambiguate L-prefix three ways (T3) |
| §1 Principles | V_i without truth conditions (V1, V7, V12) | cartan M6, jane_street M6 | UNMITIGATED MAJOR | State falsifying predicate per veto; CI-enforce; "no enforcement = wish" |
| §1 Principles | "Errors are values" (P5) — Error algebra not enumerated | minsky F17 | MINOR | Closed sum of error variants per parser/operation |
| §2 Taxonomy | Forgetful functor 6→3 sheaves asserted; no source/target/morphisms | cartan M2, grothendieck B1 | BLOCKING | Define functor or withdraw categorical decoration |
| §2 Taxonomy | C2 (UnitStatus), C3 (PositionState) not on mutation-discipline axis (they project from C5 L14) | grothendieck B2 | BLOCKING | Demote L8/L9 to projections of L14 in C5, OR state partitioning is interface-contract not mutation-discipline |
| §2.3 leaf-count reconciliation | "No contradictions" without proof of refinement maps | cartan M3, grothendieck B3, geohot M2 | BLOCKING | Exhibit map per specialist count (TEMPORAL 31, MINSKY 41, MATTHIAS 62, FORMALIS 16) with predicate preservation |
| §2 Taxonomy | 24 → 7 (jane-street) / 16 (FORMALIS) collapse refused without universal property | jane_street B1, geohot B1, grothendieck B3 | BLOCKING | Either collapse to ≤16 leaves OR per-leaf ADR override (T1) |
| §3 Per-leaf | "Min fields" lists ambiguous about completeness | cartan M5 | UNMITIGATED MAJOR | Replace with explicit signature (total field list + types + optionality + well-formedness predicate) |
| §3 Per-leaf | 6-line stubs delegate to 7 specialist files; not self-contained | halmos B-class, geohot Beauty, karpathy B2, feynman MAJOR-J4 | BLOCKING | Inline specialist content OR mark proposal as table-of-contents with explicit page count for minimum reading set; add 6 worked examples (one per class) |
| §3.1 L1 ProductTerms | `is_fungibility_preserving: TermsVersion -> bool` is a predicate-as-field | minsky F4 | BLOCKING | Sum-typed `TermsVersion` or refined `FungibilityPreservingAmendment` |
| §3.1 L1 ProductTerms | `unit_type` polymorphism: closed sum not enumerated | karpathy B4 | BLOCKING | Enumerate the closed sum of `unit_type`; map to CDM enum |
| §3.1 L1 ProductTerms | `LifecycleIntent` undefined; constructors not listed | minsky F8 | UNMITIGATED MAJOR | List every constructor; remove ellipsis |
| §3.1 L2 InstrumentMaster | Missing inter-vendor reconciliation per N8 | finops B1, isda M-2 | BLOCKING | Add reconciliation pair line (T4) |
| §3.1 L2 InstrumentMaster | `boardLotSize`, `votingRights`, `dividendPolicyRef` missing | matthias M-4 | UNMITIGATED MAJOR | Add fields; reclassify §A.2 as Missing not Partial |
| §3.1 L3 Party/LEI | LEI restatement breaks aggregation homomorphism (S1) | noether M1 | UNMITIGATED MAJOR | Specify aggregation under bitemporal LEI mapping |
| §3.1 L3 Party | KYC/sanctions/PEP/W-8/W-9 absent | finops M3, finops M2 | UNMITIGATED MAJOR | Add KYCStatus, SanctionsScreeningRun, TaxClassification |
| §3.1 L4 Calendar | Retroactive amendment policy; market cut-off times absent | noether B4, formalis M2, temporal M-1, sbl Finding 3 | BLOCKING | Pin mode-1; add `dvp_cutoff`, `fop_cutoff`, `iso20022_cutoff`, `auto_partial_cutoff` per market_iso (T12) |
| §3.1 L5 SSI | V10 "boundary contract" rhetorically launders an `ssi-ingest` workflow | jane_street B3, geohot B1, matthias B-3 | BLOCKING | Delete L5 or accept thinly-authored with V10 override ADR |
| §3.1 L5 SSI | DTCC ALERT GoldenSource reconciliation not specified | finops B1 | BLOCKING | Reconciliation pair line |
| §3.1 L6 LegalAgreement | TripartyAgreement (8 agents) missing | sbl Finding 5 | UNMITIGATED MAJOR | Sub-leaf with field set |
| §3.1 L6 LegalAgreement | ISDA Notices Hub / ISDA Create / MyLibrary not surfaced | isda UM-2, isda M-2 | UNMITIGATED MAJOR | Sub-leaf of L11 for legal-notice attestations |
| §3.1 L7 Policy | "≤30 fields" cap unenforced; circular with L21 | jane_street B4, geohot B1, lattner M3, formalis M1, feynman BLOCKING-G8, karpathy M3, nazarov m-2 | BLOCKING | Delete L7 as separate leaf (fold into Reference family or L21), OR enforce cap via CI schema-length check + decompose L7 into L7a/L7b/L7c |
| §3.2 L8 UnitStatus | `triggered-barrier flag` is bool+comment | minsky F3 | BLOCKING | `BarrierState` closed sum with attestation evidence |
| §3.2 L8 UnitStatus | Reconciliation against external sources missing | finops B1 | BLOCKING | Reconciliation pair line |
| §3.3 L9 PositionState | 14 SBL sub-leaves elided (LocateReservationLedger, CascadeRecallState, RehypCapCounter, RegReportingCursor, etc.) | sbl Finding 1 | BLOCKING | Lift sub-leaves L9.1–L9.14 with field sets (T9) |
| §3.3 L9 PositionState | Six-coordinate vector closure law not encoded | minsky F11, sbl Finding 7 | UNMITIGATED MAJOR | Smart constructor enforcing `coll_rehyp ≤ coll_recv` etc. |
| §3.3 L9 PositionState | `accumulated_cost` / `hwm` reconciliation against CCP/admin/client missing | finops B1, finops M6 | BLOCKING | CCP-statement reconciliation + L16 daily T+1 obligation |
| §3.3 L9 PositionState | Client-asset segregation flag absent (CASS / 15c3-3) | finops M4 | UNMITIGATED MAJOR | `client_asset_flag`, `segregation_account_type` + segregation closure invariant |
| §3.3 L9 PositionState | Agent-lender LEI reallocation silent | sbl Finding 8 | UNMITIGATED MAJOR | Decide mutable-with-state-only-StateDelta vs close-and-reopen |
| §3.4 L10 RawObservation | `RawQuote` should be closed sum over observable kinds | minsky F18 | MINOR | Closed sum |
| §3.4 L10 RawObservation | Missing N8 aggregation gate before consumed by L13 | nazarov B-1 | BLOCKING | `aggregation_outcome` field; gate enforcement (T7) |
| §3.4 L10 RawObservation | BorrowFeeQuote, RebateRateFix duality, MMFNAV missing | sbl Findings 10/14 | UNMITIGATED MAJOR / MINOR | Add as L10 sub-leaves |
| §3.4 L11 LifecycleOracle | LifecycleEvent ends in ellipsis | minsky F8 | UNMITIGATED MAJOR | Close the sum |
| §3.4 L11 LifecycleOracle | ManufacturedPaymentRate, TaxTreatmentOracle missing | sbl Finding 4, finops M2, isda M-3 | UNMITIGATED MAJOR | Sub-leaves with field sets |
| §3.4 L11 LifecycleOracle | RQVSnapshot triparty cadence missing | sbl Finding 5 | UNMITIGATED MAJOR | Sub-leaf with field set |
| §3.4 L12 ExternalConfirmation | Affirmation status (T+1 9pm-ET-on-T+0) absent | finops M7 | UNMITIGATED MAJOR | Add `affirmation_status` enum + aging report |
| §3.4 L12 ExternalConfirmation | `is_csdr_fop_exempt` flag absent | sbl Finding 9 | MINOR | Add flag; document exemption logic |
| §3.4 L13 CalibratedObject | `gating_outcome` and `arbitrage_certification_status` are untyped tags | minsky F2 | BLOCKING | `CalibrationOutcome = Rejected | Accepted { certificate }` |
| §3.4 L13 CalibratedObject | Inter-vendor curve/surface IPV reconciliation missing | finops B5 | BLOCKING | IPV control specification (T4) |
| §3.4 L13 CalibratedObject | Q/R Kalman post-hoc edits unmodelled | noether M2 | UNMITIGATED MAJOR | Q, R as L21 pin or `CalibrationParameterPin` sub-leaf |
| §3.5 L14 MoveStream | Conservation refinement asserted not encoded | minsky F5 | BLOCKING | `BalancedTransaction` smart constructor |
| §3.5 L14 MoveStream | Permutation invariance S2 not enforced | noether M4 | UNMITIGATED MAJOR | Require disjoint moves OR drop S2 claim |
| §3.5 L14 MoveStream | No reconciliation against custodian / CCP / ISO 20022 inbound | finops B1 | BLOCKING | Reconciliation pair line |
| §3.5 L14 MoveStream | Fold function L14 → L8/L9 nowhere defined | feynman BLOCKING-G2 | BLOCKING | Per leaf, name fold as typed function with initial state, writer-tag schema, witnessed law `read(L8|L9, key, t) == fold(L14[≤t], key, init)` |
| §3.5 L15 ValuationRecord | `quality` is flat enum, should be sum carrying typed payload | minsky F1 | BLOCKING | `ValuationQuality` as closed sum |
| §3.5 L15 ValuationRecord | IPV / Fair-value-level / AVA components missing | finops B5 | BLOCKING | Schema extension (T4) |
| §3.5 L15 ValuationRecord | PnL-explain / FRTB PLA schema missing | finops M8 | UNMITIGATED MAJOR | Add `PnLAttributionRecord` |
| §3.5 L16 ObligationStore | `discharge_predicate` representation unspecified | minsky F6 | BLOCKING | `DischargePredicateKind` closed sum |
| §3.5 L16 ObligationStore | Reconciliation against CSA-call / AcadiaSoft / triResolve / TR / regulator-ack missing | finops B1 | BLOCKING | Reconciliation pair line |
| §3.5 L16 ObligationStore | Status enum case mismatch (uppercase vs PascalCase) | halmos D2 | UNMITIGATED MAJOR | Pick one spelling |
| §3.5 L16 ObligationStore | Cascade-recall topology mis-routed to L24 | sbl Finding 6 | UNMITIGATED MAJOR | Lift as L9 sub-leaf or L16 sub-kind |
| §3.6 L17 AttestationEnvelope | Should be field on observations, not separate leaf | geohot B1, grothendieck M1, jane_street B4 | BLOCKING | Fold into L1, L2, L3, L10, L11 inline (T1) |
| §3.6 L17 | Malformed envelope handling unspecified | nazarov M-6 | UNMITIGATED MAJOR | Gateway-attested failed-ingest record |
| §3.6 L18 IdentityKeys | Constants module, not data | geohot B1, grothendieck m3 | UNMITIGATED MAJOR | Move out of leaf list |
| §3.6 L19 Snapshot | Manifest vs bundle unspecified; cycle boundary unspecified | karpathy M6 | UNMITIGATED MAJOR | Specify shape and cycle definition |
| §3.6 L19 Snapshot | Should be view, not leaf (V13 selectivity) | geohot B3 | BLOCKING | Reclassify as named view, OR state V13 is selective and justify |
| §3.6 L20 IdempotencyToken | 9 shapes not closed-sum; namespace not enumerated | minsky m2/F19, feynman BLOCKING-G3 | UNMITIGATED MAJOR | Closed sum `IdempotencyKey = ⊕_{i=1..9} K_i`; namespace tag |
| §3.6 L21 VersionPin | 5 axes silently conflated; canonicalisation undefined | lattner B1, feynman BLOCKING-G1, minsky F10 | BLOCKING | Versioning Algebra subsection (T8) |
| §3.6 L21 VersionPin | DRR rule-set version axis missing | isda UM-1 | BLOCKING | Add `drr_rule_set_version: Map<RegulatorRuleSet, GitSha>` (T5) |
| §3.6 L21 VersionPin | CDM extension migration unspecified | lattner B2 | BLOCKING | Versioned closed enum with migration table |
| §3.6 L22 HashChainAnchor | Field on L14, not separate leaf | geohot B1 | UNMITIGATED MAJOR | Fold into L14 |
| §3.6 L23 Capability | Field-tag closed alphabet not enumerated; mutation discipline unspecified | minsky F14, formalis M1 | UNMITIGATED MAJOR | Decompose; close the alphabet |
| §3.6 L24 OrchestrationState | V11 reconciliation rhetorical; no architectural fence | jane_street B2/B6, lattner B3, nazarov M-4 | BLOCKING | Delete L24 from spine OR add type-level `OrchestrationOpaque` + L23 capability fence (T1) |
| §3 (NEW) | Add L25 RegulatorySubmission | isda B-1, finops T4 | BLOCKING | Specified leaf (T5) |
| §3 (NEW) | Add L25/L26 BreakRegister | finops B2 | BLOCKING | Specified leaf with FSM (T4) |
| §3 (NEW) | Add L25/L27 ClockAuthority | noether B1 | BLOCKING | Specified leaf (T12) |
| §4 Cross-cutting laws | 14 laws + 5 theorems dependency DAG missing | formalis M3 | UNMITIGATED MAJOR | DAG of axioms / lemmas / theorems |
| §4 Cross-cutting laws | L1 oracle too weak; constant-stub passes | testcommittee F-01 | BLOCKING | Strengthen oracle |
| §4 Cross-cutting laws | L4 oracle tests `read==read` not bitemporal predicate | testcommittee F-02 | BLOCKING | Test `t_v ≤ t_k` and restatement-version monotonicity |
| §4 Cross-cutting laws | L6 omits HWM-cross-mandate-collapse | testcommittee F-03 | BLOCKING | Add fixture |
| §4 Cross-cutting laws | L9 `referentially_independent` predicate undefined → vacuous pass | testcommittee F-04 | BLOCKING | Define predicate; partition by dependence-relation lattice |
| §4 Cross-cutting laws | L12 generator rejection-samples into Θ_AF then asserts in-region | testcommittee F-05 | BLOCKING | MCMC / Hamiltonian sampling, not rejection |
| §4 Cross-cutting laws | No per-stratum coverage targets | testcommittee F-06 | BLOCKING | First-class coverage assertions (T10) |
| §4 Cross-cutting laws | No declared test pyramid | testcommittee F-07 | BLOCKING | Pyramid declaration with target counts per layer |
| §4 (NEW) | Add Lineage Cursor specification | finops B3 | BLOCKING | Typed graph projection (T4) |
| §4 (NEW) | Add Tempo / SLA matrix | finops B6 | BLOCKING | Per-leaf p50/p99 (T4) |
| §5 Fault catalogue | Stub paragraph; 49 cells not inlined | halmos M2, karpathy m2 | UNMITIGATED MAJOR | Inline cluster-by-class skeleton |
| §5 Fault catalogue | No fault-injection harness for Cluster V silent-corruption | correctness B-4 / D-1 | BLOCKING | Test inserting corrupt byte; assert chain-verification flag |
| §5 Fault catalogue | No max_silence partition harness | correctness D-2 | UNMITIGATED MAJOR | Define max_silence; simulate partition; assert escalation |
| §5 Fault catalogue | No bugification | correctness D-3 | UNMITIGATED MAJOR | Adversarial-legal generators (zero-balance, leap-second, near-singular Hessians) |
| §5 Fault catalogue | No clock-skew harness for L4 | correctness D-4 | UNMITIGATED MAJOR | Out-of-order `(t_v, t_k)` interleaves |
| §6 Realism budget | C-A1, C-A2, C-A3, C-A7, C-A8, C-A9 owners are job titles | nazarov M-2, jane_street M5 | UNMITIGATED MAJOR | Detection signal + compensating action + blast radius per assumption (T11) |
| §6 Realism budget | Trust-assumption registry artefact unspecified | nazarov M-1 | UNMITIGATED MAJOR | Schema, cadence, kill-switch (T11) |
| §6 Realism budget | C-A8 not bounded; partition fault-handling unspecified | lattner m4, noether M5 | UNMITIGATED MAJOR | Split C-A8a / C-A8b |
| §6 Realism budget | C-A10 retention has no numeric horizon for perpetual units | nazarov m-5 | MINOR | Add horizon parameter; address perpetual issuance |
| §6 Realism budget | N7.3 graceful degradation does not bind downstream consumers | nazarov M-5 | UNMITIGATED MAJOR | Typed read API enforcing quality acceptance policy |
| §6 (NEW) | Add C-A11 canonical-serialiser stability | feynman BLOCKING-G1, minsky F10, noether m3 | BLOCKING | Pin canonicalisation (T8) |
| §6 (NEW) | Add C-A12 snapshot-store durability | temporal m-1 | UNMITIGATED MAJOR | Multi-region replication discipline |
| §7 CDM Gap analysis | Verification suspended; gap-rank inverted; PR-unit headcount ~15 not 5 | matthias B-1, B-2, B-4, M-1 | BLOCKING | Re-fetch all .rosetta paths; promote Gap 5; re-issue with true headcount (T6) |
| §7 CDM Gap analysis | Gap 4 (attestation envelope) is Ledger-internal not CDM gap | matthias M-1 | UNMITIGATED MAJOR | Move out of CDM gap list |
| §7 CDM Gap analysis | Gap 3 (tokenised collateral) misframed as descriptor not lifecycle model | isda B-2, matthias M-3 | BLOCKING | Reframe as `lifecycle_model = SmartContract` variant in L1 OR document v12.0 deferral |
| §7 CDM Gap analysis | Gap 2 SBL has no runtime contract for SFTR/SLATE | sbl Finding 2 | BLOCKING | Commit Ledger-internal types pinned at L21 + forward-migration path (T5) |
| §7 (NEW) | §7.6 Migration discipline for Ledger-internal types | formalis M5 | UNMITIGATED MAJOR | Internal type carries `cdm_native_pending` flag; migration record in L12 |
| §8 Compositional theorems | All 5 theorems theorem-shaped not theorems | cartan B2, formalis B1–B5, correctness A.1–A.3, noether B2, matthias M-5 | BLOCKING | Re-issue with full hypothesis lists (T2) |
| §8 (NEW) | Theorem 6: Pillar-3-Projection-Lifting | isda UM-4 | UNMITIGATED MAJOR | Add cost-free architectural commitment (T5) |
| §9 Surfaced disagreements | §9.2 reconciliations are slogans not arguments | halmos M5, jane_street M2, geohot Worst Pattern | BLOCKING | Per reconciliation: structural argument or ADR override (T1) |
| §9.2 vetoes | V8/V9/V10/V11 non-functional reconciliations | jane_street B2/B3/B4/B5, geohot B2 | BLOCKING | Either honour by deletion or override with documented ADR (T1) |
| §9.4 Unwitnessed laws | Mis-classified — 2 of 4 recoverable | testcommittee F-15/F-16, formalis B6 | BLOCKING | Restructure: 1 unwitnessed (L1), 3 witnessed-via-composition (L4, L8, L13) (T7) |
| §9.5 TEMPORAL awkward fits | 6 categories deferred; 3 are load-bearing | feynman MAJOR-J7, temporal B-1 / M-1 to M-4 | BLOCKING | Rule on each: Temporal / out-of-Temporal / application discipline only |
| §9.6 Goodhart traps | Named not trapped; missing fifth (type-system witness laundering) | correctness C.1–C.5, testcommittee C.1–C.4 | BLOCKING | Add detection mechanism per trap; add fifth trap (T10) |
| §10 Phase 3 instructions | "No minor improvement without trade-off" is a trap | formalis m5 | MINOR | Rephrase as accept/reject ruling with rationale |

---

## §3. Singleton findings (raised by 1 reviewer; BLOCKING)

The following BLOCKING findings appear in only one review but are load-bearing and must be addressed by the Data Team. Flagged for Data Team judgement; not deferrable on grounds of singularity.

1. **Multi-CCP novation breaks per-CCP conservation.** `correctness A.2`. CDM `BusinessEvent ∈ {Novation, ClearingNovation}` re-binds a contract from CCP_A to CCP_B in one atomic event; per-CCP closure fails by design. **Required:** add Novation Bridge Conservation invariant OR split novation into two atomic transactions with explicit bridge `Obligation`.

2. **HSM key rotation breaks B11 boundary.** `correctness A.3`. HSM custody discipline (C-A2) requires key destruction on rotation; replaying old envelope past rotation cannot re-verify. **Required:** state explicitly that public verification keys are append-only; rotation adds new key, never removes old.

3. **Late-discharge race policy unspecified.** `temporal B-3`. Discharge signal arriving after timer-fire and compensation begin: three options (reject / cancel-compensation / queue-and-reconcile). **Required:** rule per obligation kind. SBL recall: deadline sacrosanct; settlement: cancel acceptable; regulatory: queue-and-reconcile.

4. **`tx_id` includes Temporal `run_id` → idempotency bypass on ContinueAsNew.** `temporal B-2`. **Required:** `tx_id = hash(business_event_id, attempt_seq)` with no `run_id`.

5. **Bitemporal-restatement orchestration shape unspecified.** `temporal B-1`. Workflows already-consumed under `(t_obs, t_known_1)` vs newly-consumed under `(t_obs, t_known_2)` vs need-retroactive-recomputation. **Required:** name `RestatementWatchWorkflow` per `(observable_class, vendor)` shape with subscription discipline.

6. **L24 has no architectural fence; conventions erode.** `lattner B3`. **Required:** opaque handle type `OrchestrationOpaque` + L23 capability scope excluding `read:OrchestrationState` from economic-handler capabilities; theorem-level invertibility statement.

7. **No queryable lineage cursor.** `finops B3`. SOX §404 / BCBS 239 §3 / DORA Art 8 / IFRS 13 Level 3 require demonstrable balance-sheet → trial-balance → projection → MoveStream → BusinessEvent → snapshot → observations → vendor envelope path. **Required:** §4.X Lineage Cursor specification.

8. **CSDR penalty regime has no first-class home.** `finops B7`. Mandatory cash penalties under EU SDR; debit/credit on firm's books. **Required:** `obligation_type = CSDR_PENALTY` with rate/basis-points/days/source schema.

9. **T+1/T+0 SLA unaddressed.** `finops B6`. **Required:** §4.Y Tempo and SLA matrix.

10. **Six-coordinate vector closure law not encoded.** `minsky F11`. `coll_rehyp ≤ coll_recv`, `borr ≥ 0` etc. **Required:** smart constructor with refinement type encoding invariants.

11. **`PositionVector` invariants stated in prose, not types.** Combination of minsky F11 + sbl Finding 7 (RehypCapCounter / LocateReservationLedger). **Required:** lift as L9 sub-leaves with non-standard aggregation key (`bd_lei` for 15c3-3, `(lender_lei, isin)` for locate).

12. **P18 SBL buy-in carve-out unsurfaced in conservation lifting.** `sbl Finding 13`. Buy-in is the only SBL operation that writes lender's `own`. **Required:** FORMALIS L7 explicit guard or §8 Theorem 1 enumeration as exception.

13. **Compensations are activities, not workflows.** `temporal M-12 escalates to BLOCKING for sbl cascade-recall`. **Required:** non-trivial compensations are child workflows (multi-step buy-in, manufactured-payment under-withhold, regulatory-report escalation).

14. **Notation collision blocks review (L-prefix three ways).** `halmos B5`. Each "F: Part of L8" line in §3 means FORMALIS' L8, not NAZAROV's L8. **Required:** disambiguate aggressively to `L#` / `Λ#` / `Φ#`.

15. **L9 forgetful-functor composition test misnamed (round-trip vs generator-pair).** `feynman MINOR-4` (escalates to load-bearing for testcommittee F-04). **Required:** state actual test shape.

16. **Multi-replica verification protocol unspecified.** `feynman BLOCKING-G6`. FORMALIS Theorem 4 invokes "multi-replica verification" without specifying replica count, agreement primitive, disagreement handling. **Required:** name protocol, assumptions, witnessed property.

17. **Writer-tag architecture (move-side vs field-side) unstated.** `feynman BLOCKING-G7`. **Required:** state architecture and bind to CORRECTNESS L5/L6/L7.

18. **Manufactured-payment data not modelled** beyond a name. `sbl Finding 4`. Required fields: `corp_action_event_id`, `lender_country`, `borrower_country`, `treaty_rate`, `gross_amount`, `manufactured_amount`, `is_full_pass_through`. **Required:** L11 sub-leaves.

19. **Calibration adjunction (L10 ↔ L13) hidden.** `grothendieck M5`. Stating Calibrate ⊣ Forget collapses 4 separate invariants (Theorem 4 redundancy + CORRECTNESS L2, L11, L12) into one categorical fact. **Required:** state adjunction; rederive consequences.

20. **C-A8 partition fault-handling not bounded.** `noether M5`. CAP-style choice (refuse-or-stale-cache) unspecified. **Required:** split C-A8a / C-A8b.

21. **No build-order / minimum-viable-mental-model / reading paths.** `lattner M1`, `karpathy m5`. **Required:** §0.1 minimum-viable subset, §0.2 reading paths per role, build-order step sequence.

22. **No LoC complexity budget for implementation.** `geohot M5`. **Required:** core implementation ≤10,000 LoC excluding adapters/tests; if not, the spec is wrong.

23. **No structural rule for library-vs-runtime extensibility.** `lattner M2`. For each leaf with sum-type/enum: closed-by-Ledger or open-by-extension; extension mechanism; upstream-migration story.

24. **Mutation operators incomplete (M-FAKE-CERT, M-AGGREGATE, M-DEFLATE, M-BIAS, M-SHRUG-RETRY missing).** `testcommittee C.2 / D ranking`. **Required:** add operators; mutation-survivor reporting.

25. **Historical-bug regression fixtures absent (LIBOR cessation, manufactured-payment cross-jurisdiction, corporate-action cascade, tokenised-collateral chain reorg).** `testcommittee E.1, E.2, E.3, E.6`. **Required:** named fixture corpus as version-controlled artefact.

---

## §4. Disagreements between reviewers

### D1. Leaf count

- **jane_street:** 7 sectors (3 + 4) is the upper-bound *ceiling*; 24 violates V7.
- **geohot:** 16 leaves (FORMALIS-aligned); 24 is bookkeeping inflation.
- **formalis:** 16 leaves (its own count); folds C6 into L13/L14.
- **correctness:** doesn't dispute 24; focuses on closure failures.
- **matthias:** 24 is OK *internally*, but external API must match CDM-type granularity (~62 from MATTHIAS Phase-2). Hybrid story.
- **NAZAROV (Phase 2 author):** 24 is canonical.
- **Phase 3 NAZAROV:** doesn't redispute count; attacks the bar (B-1, B-2, B-3).
- **isda:** wants L25 RegulatorySubmission added on top.
- **sbl:** wants 14 sub-leaves added.
- **finops:** wants L25 BreakRegister, L25 ClockAuthority added.
- **noether:** wants L25 ClockAuthority added.

**Resolution prescription.** Data Team must decide one of:
1. **The minimalist path:** collapse to ≤16, add the load-bearing additions (L25 RegulatorySubmission, L25 BreakRegister, L25 ClockAuthority) — net ≈ 19 leaves. This satisfies geohot, formalis, jane_street (with overrides for the 3 net additions), grothendieck, and the operational additions.
2. **The maximalist path:** keep 24, add the 3 new leaves, add 14 SBL sub-leaves, document every veto override as ADR — net ≈ 41 leaves with sub-leaf register. This satisfies sbl, finops, isda, matthias, but explicitly rejects jane_street's V7 ceiling.

The Data Team must pick one. The current "tension box" middle path is rejected by every reviewer who flagged it.

### D2. Tokenised collateral framing

- **isda B-2:** lifecycle-model variant in L1 (`lifecycle_model = SmartContract`); the smart contract emits the move; the executor relays. NOT a descriptor extension.
- **matthias M-3:** extend `DigitalAsset` (already in CDM 6.0.0) with a chain-aware identifier sub-type; integrate under `EligibleCollateralSchedule`. The Phase-2 §G.9 standalone `cdm-tokenisation-lib` proposal would be rejected by FINOS.

**Resolution prescription.** These are compatible: ISDA describes the *internal* shape (lifecycle model in L1), matthias describes the *CDM-extension* shape (extend DigitalAsset). Combine: in L1, `lifecycle_model = SmartContract`; in CDM mapping, route via `DigitalAsset` extension under `EligibleCollateralSchedule`; defer `BackingModel` enum + `proofOfReservesLink` to attestation envelope.

### D3. Surrogate-witness retreat vs structural risk acceptance

- **geohot M1, feynman MAJOR-J5:** rename "surrogate witnesses" to "architectural risks accepted with named owners." Stop laundering through vocabulary.
- **formalis B6, testcommittee F-15/F-16:** disagree partially — 2 of 4 are *recoverable* (L4 by induction, L13 by TLA+). Don't accept the surrender for those.
- **karpathy M4:** specify surrogate parameters or admit deferred.
- **lattner M4:** link to monitoring posture (production observability).

**Resolution prescription.** All four positions converge: restructure §9.4 into 1 genuinely unwitnessed (L1 — accept as architectural risk with named owner per geohot/feynman) + 3 recoverable-via-composition (L4, L8, L13 — per formalis/testcommittee, with parameters per karpathy and observability per lattner). Stop using "surrogate witness" as a catch-all term.

### D4. C2/C3 elevation vs projection-of-L14

- **grothendieck B2:** C2 (UnitStatus), C3 (PositionState) are projections of L14 → demote out of independent classes; spine reduces to 4 classes.
- **jane_street M3:** V13 forbids Trade/Position/PnL tables; the proposal honours storage-layer V13 but L9 ships with own invariants and owner — defensible only if documented as ADR override of V13 due to StatesHome 3-map ruling.
- **sbl Finding 1:** L9 needs 14 sub-leaves with own field sets — strongly implies L9 is not "just a projection."
- **NAZAROV (Phase-2):** 24-leaf spine includes C2, C3 explicitly because StatesHome 3-map is canonical (per user memory).

**Resolution prescription.** Acknowledge L9 (and L8) as *stored caches with single-writer invariants* per StatesHome C11. Add ADR documenting V13 override for L8/L9 with citation to v10.3 StatesHome 3-map ruling. State the cache-invalidation discipline (per formalis B4 Theorem 4b) so the projection-vs-cache duality is explicit. This satisfies jane_street, sbl, NAZAROV; grothendieck's structural concern reduces to a categorical re-statement that doesn't change leaf count.

### D5. Compensations as activities vs workflows

- **temporal M-12:** non-trivial compensations are child workflows; the proposal's "compensation activity" is wrong.
- **proposal_v1 / formalis Theorem 3:** treats compensation as `κ : Obligation → PendingTransaction` (a function, hence activity-like).

**Resolution prescription.** temporal is right for non-trivial cases. Restate FORMALIS Theorem 3 with: `κ` may be a workflow with its own compensation tower; totality is preserved by structural induction over the closed list of (event_class, obligation_kind) pairs (formalis B3 remediation).

---

## §5. Recommendation to Data Team for `proposal_v2` structure

**Approach.** proposal_v2 should not be a polishing pass. The 79 BLOCKING and 130 UNMITIGATED MAJOR findings indicate the proposal needs substantial restructuring, not just additions. Three deliverable strategies that the Data Team should consider.

### Strategy A: "Foundation first" (recommended by formalis, cartan, halmos, karpathy, geohot, lattner)

Rewrite proposal_v2 as a *specification*, not a *navigation document*. Order:

1. **§0 Executive summary** (rewritten self-contained; no forward references).
2. **§0.5 Notation table** + glossary (T3) — BLOCKING fix.
3. **§1 Definitions appendix** (cartan B1; new section before principles): for every leaf, ambient sets/types, well-formedness predicate, signature.
4. **§2 Bitemporal definition** (new section): `Bitemporal<T>`, axes, tie-breakers, restate-link (T3).
5. **§3 Principles & vetoes** (kept; per-veto truth conditions added per cartan M6 + jane_street M6).
6. **§4 Master taxonomy with universal property** (T1): either ≤16 leaves with defended count, or per-leaf ADR overrides for 24+.
7. **§5 Per-leaf integrated specification** (rewritten): 1 worked example per class; 14 SBL sub-leaves lifted; reconciliation pair on every leaf.
8. **§6 Cross-cutting laws** with strengthened oracles (testcommittee F-01 to F-07) and dependency DAG (formalis M3).
9. **§7 Inlined fault catalogue** (49 cells visible; halmos M2).
10. **§8 Compositional theorems** with full hypothesis lists per cartan B2 / formalis B1–B5.
11. **§9 Realism budget** with detection/compensation/blast-radius per assumption (T11).
12. **§10 Versioning algebra** (T8) — new section.
13. **§11 Lineage cursor + tempo SLA + retention matrix + reconciliation matrix** (T4) — new sections; or three companion documents per finops §5.
14. **§12 CDM gap analysis** (re-fetched; promote Gap 5 to top; ~15 PR units; T6).
15. **§13 Surfaced disagreements** with structural arguments (not slogans).
16. **§14 ADR register.** Every veto override; every leaf-count exception; every mode-1 calendar pin; every storage-layer caching decision.

### Strategy B: "Companion documents + slim spine" (per finops §5, sbl §3)

Keep proposal_v2 lean (≤30 pages); produce three normative companions:
1. `reconciliation_matrix.md`
2. `retention_matrix.md`
3. `tempo_sla_matrix.md`

Plus a `regression_fixture_corpus.md` (testcommittee §E) and `versioning_algebra.md` (lattner B1). Each companion is normative; the spine is the table of contents.

### Strategy C: "Hold position; iterate vetoes" (NOT recommended)

Continue the §9.2 reconciliation pattern. Expected to fail another round.

### What NOT to do

- **Do not** retain the "tension box" output format. jane_street, geohot, halmos, finops all flag it as anti-pattern.
- **Do not** treat the §9.2 reconciliations as decided. Per jane_street M2: rule leaf-by-leaf or delete.
- **Do not** carry "Direct" CDM Status labels forward without re-verification. matthias B-1 is unambiguous.
- **Do not** add new leaves silently; every addition (L25/26/27 etc.) must be ADR-documented.
- **Do not** advance to FORMALIS-as-arbiter without addressing every BLOCKING finding by name. finops, matthias, formalis, temporal all explicitly state this.

### Recommended priority order for proposal_v2

1. **First pass — structural foundation (T1, T3, T8):** notation table; definitions; 16-vs-24 ruling; versioning algebra; canonicalisation pin. Without these, every other fix is on sand.
2. **Second pass — closure of theorems (T2, T7, T12):** rewrite §8; restructure §9.4; add ClockAuthority + symmetry-carrier matrix.
3. **Third pass — operational floor (T4, T5):** reconciliation matrix; break register; lineage cursor; retention matrix; SLA matrix; L25 RegulatorySubmission.
4. **Fourth pass — leaf-level fixes (T9, T11):** SBL sub-leaves; trust-registry contract; per-leaf typed witnesses (minsky F1–F13).
5. **Fifth pass — Goodhart hardening + CDM verification (T6, T10):** mutation operators; per-stratum coverage; CDM live re-fetch; gap re-rank.

---

## §6. Grade-level convergence path

### From C+ → B (unblock convergence)

Close all BLOCKING findings (≈79). The minimum viable B-grade requires resolution of every theme T1–T12 plus the 25 singleton blockers in §3. Specifically:

1. **T1 (leaf count):** rule on ≤16 vs 24+ADRs vs hybrid. No tension boxes.
2. **T2 (theorems):** all 5 theorems restated with full hypotheses; cross-system theorems explicitly framed.
3. **T3 (foundation):** notation table; definitions appendix; bitemporal arithmetic.
4. **T4 (operational floor):** reconciliation pair on every leaf; L25 BreakRegister; lineage cursor; retention matrix; tempo SLA matrix; IPV.
5. **T5 (regulatory):** L25 RegulatorySubmission; DRR rule-set version axis in L21.
6. **T6 (CDM):** re-fetch all paths; Gap 5 promoted; PR-unit headcount; reclassify gaps.
7. **T7 (surrogates):** restructure §9.4; specify all parameters; production observability.
8. **T8 (versioning):** §3.6.1 Versioning Algebra; pin canonical_serialise; fix idempotency keys.
9. **T9 (leaf detail):** 6 worked examples; SBL sub-leaf register.
10. **T10 (Goodhart):** boundary-integrity production test; per-stratum coverage targets; mutation operator additions.
11. **T11 (ownership):** detection/compensation/blast-radius per C-A; trust registry artefact.
12. **T12 (clock/symmetry):** L25 ClockAuthority; mode-1 pinned; symmetry carrier matrix.
13. **Singletons:** address all 25 in §3.

This is a substantial proposal_v2 — likely 3-5x the current document length, or a reorganisation into 5-6 normative documents.

### From B → A (accept for arbiter handoff)

After unblocking, close all 130 UNMITIGATED MAJOR findings. Specifically:

1. Per-leaf typed witnesses (minsky F1–F13).
2. Theorem dependency DAG (formalis M3).
3. Calibration adjunction (grothendieck M5).
4. Closed sums for every enum, no ellipses (minsky F8).
5. Closed-system boundary fault handling (noether M5).
6. Compensation tower with terminal escalation (temporal M-12, M-13).
7. Task-queue topology (temporal M-14).
8. Heartbeat policy + signal-driven wait pattern (temporal M-15).
9. GetVersion gate inventory per leaf (temporal M-9).
10. Cross-namespace orchestration ruling (temporal M-4).
11. Historical-bug regression fixture corpus (testcommittee E.1–E.6).
12. Aggregation-masking meta-property (testcommittee C.4).

A-grade also requires:
- Build-order / reading paths (lattner M1, karpathy m5).
- LoC complexity budget (geohot M5).
- Library-vs-runtime extensibility per leaf (lattner M2).

### From A → A+ (Beck "specification is the test suite")

Close every minor; produce regression fixture corpus as version-controlled artefacts; promote testcommittee §E.1–E.6 to release-gate properties; complete the §0.1 minimum-viable-mental-model; ship one 2-page worked end-to-end example as the new-hire onboarding artefact.

---

## §7. Closing observation

Three strands must hold simultaneously for proposal_v2 to converge:

1. **The mathematical strand** (cartan, formalis, grothendieck, noether, halmos, minsky): make the theorems theorems, define the types, name the symmetries, encode the invariants type-level rather than prose-level.
2. **The engineering strand** (jane_street, geohot, lattner, karpathy, feynman, temporal): cut the leaf count, kill the rhetorical reconciliations, pin the canonical-serialiser, fix the idempotency keys, specify the boundaries, build it in ≤10K LoC.
3. **The operational strand** (finops, isda, matthias, sbl, nazarov, correctness, testcommittee): add the reconciliation pairs, the break FSM, the lineage cursor, the retention matrix, the regulatory-submission leaf, the IPV controls, the SBL sub-leaves, the per-stratum coverage, the mutation operators, the historical-bug fixtures.

The Data Team has been asked to write `proposal_v2`, not `proposal_v1.1`. Per FORMALIS' close: "*A theorem whose hypothesis contains its conclusion is not a theorem. A totality whose precondition is not enforced is not totality. A witness whose surrogate is itself unwitnessed is not a witness. We have found all three.*"

Round 1 says: do not converge yet. Round 2 of the same document, lightly polished, will reach the same verdict.

---

*End R1 Consolidated Findings.*
