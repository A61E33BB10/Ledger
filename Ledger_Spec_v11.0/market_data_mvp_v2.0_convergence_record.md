# market_data_mvp_v2.0 — Reviewer Convergence Record (iter2 final)

**Document:** `market_data_mvp_v2.0.tex` (63 KB source, 318 lines)
**PDF:** `market_data_mvp_v2.0.pdf` (15 pages of a 15-page user-relaxed hard cap)
**Date converged:** 2026-05-10
**Audience:** data engineering team (SQL / ETL / warehouse)

## Document shape (iter2 final)

The user reviewed iter1 of v2.0 (11 pages) and requested four content changes. iter2 is a structural revision that:
1. Removed the pedantic "Audience and purpose" paragraph; surviving framing folded into an unnumbered preamble.
2. Added per-concept CDM mapping prose for every catalogue concept (Rosetta type, source filename under `rosetta-source/src/main/rosetta/`, notable fields/cardinalities — all verified live against `finos/common-domain-model@master`).
3. Added a new §5 "Loading for the pricing library" between bitemporal storage and CDM-as-wire, naming six concrete access patterns, the bitemporal-indexing implication, and the materialised-current-projection pattern as a cache (not a system-of-record replacement).
4. Filled the user-relaxed 15-page budget (cap raised from 10 mid-orchestration).

The document covers three things:
1. **CDM as the wire vocabulary** for concepts where CDM defines a type; gaps logged.
2. **Provenance and traceability** via `source`, `t_obs`, `t_known`, `restates_ref` on every record.
3. **Bitemporal storage** with two query modes; restatements are new rows.

## Phase 0 binding rulings — all honoured

- SBL events out-of-scope (named explicitly in §7 and in the lifecycle concept).
- External confirmations folded into Lifecycle as `kind=confirmation_received`.
- Admission `status` enum preserved as closed list `consensus | single_source | quarantined`.
- CCP-margin schedules dropped from MVP.
- On-chain obligations: one line in the OTC products concept.

## Round 2 (iter2) grades

| Reviewer | Lens | iter1 R1 | iter2 R2 | Δ |
|---|---|---:|---:|---:|
| nazarov-data-architect (**PRIMARY**) | Data engineering reality | 8.2 | 8.6 | +0.4 |
| rosetta-engineer | Rosetta DSL fidelity | 8.2 | 7.4 | -0.8 |
| rosetta-cdm-engineer | CDM data-model mapping | 7.8 | 8.2 | +0.4 |
| banking-auditor | IFRS / audit / controls | 7.8 | 8.4 | +0.6 |
| isda-board-advisor | ISDA market practice | 7.6 | 8.6 | +1.0 |
| finops-architect | Operational feasibility (scope re-expanded) | 8.0 | 8.5 | +0.5 |
| formalis | Convergence arbiter | 8.2 | 8.6 | +0.4 |
| **Mean** | | **8.0** | **8.33** | **+0.33** |

**Convergence rule (orchestration §5):** all seven reviewers ≥ 7.0/10 in the same round, no blocking items outstanding.
**Convergence reached at iter2 R2.** Lowest grade 7.4 (rosetta-engineer); zero blocking items across the panel.

The primary grader (nazarov-data-architect) graded all four iter2 content changes as **GOOD**:
- Audience paragraph dropped: GOOD — preamble still finds its reader.
- Per-concept CDM mapping added: GOOD — concrete Rosetta type / filename / cardinality detail; catches v1 divergences (e.g., `floatingrateindex-enum.rosetta` does not exist; actual is `base-staticdata-asset-rates-enum.rosetta`).
- §5 fast-loading: GOOD — six concrete access patterns, indexes, pricing-flow motivation.
- 15-page count earned: YES (not padding).

## Iter2 R2 → iter2 polish closures

R2 surfaced 6 confirmed-factual CDM errors against live `finos/common-domain-model@master` (5 from rosetta-engineer as majors; 2 corroborated by rosetta-cdm-engineer). One polish round closed all 6 majors plus 5 minor refinements via character-bounded text swaps; net-zero line change; document remains 15 pages.

**Six major CDM corrections (all closed):**
- **P-CDM-1**: Fictional `ForwardPayout` removed from the Payout branch list. Authoritative 8 branches are `AssetPayout`, `CommodityPayout`, `CreditDefaultPayout`, `FixedPricePayout`, `InterestRatePayout`, `OptionPayout`, `PerformancePayout`, `SettlementPayout`. Forward settlement uses `SettlementPayout`.
- **P-CDM-2**: File split corrected — the `choice Payout` declaration is in `product-template-type.rosetta`; the interest-rate / credit / commodity leaf bodies live in `product-asset-type.rosetta`.
- **P-CDM-3**: `Observable` choice rewritten as a 3-branch choice (`Asset | Basket | Index`); `Curve` is a separate, deprecated top-level type, not a branch — which is precisely why calibrated curves have no CDM-native home.
- **P-CDM-4**: Event-layer location and typing corrected — `EventInstruction` lives in `event-workflow-type.rosetta` (not `event-common-type.rosetta`); `EventInstruction.instruction` is `Instruction (0..*)` (not `PrimitiveInstruction`); `PrimitiveInstruction` is a record with optional sub-instruction fields (not a choice). "Branches" language replaced with "fields, not choice variants".
- **P-CDM-5**: `LegalEntity.jurisdiction` removed — `LegalEntity` carries only `name` and `entityIdentifier` on master. Jurisdiction has no CDM home and is now stated as a Ledger-local field (ISO 3166 country code).
- **P-CDM-6**: CSA elections corrected — `eligibleCollateral` rides on `CollateralProvisions` (which itself lives in `product-collateral-type.rosetta`, not the `legaldocumentation-csa-*` family); thresholds and minimum-transfer amounts ride on `CreditSupportObligationsBase` and its `CreditSupportObligationsInitialMargin / VariationMargin / Legacy` specialisations.

**Five minor refinements (all closed):**
- `BusinessCenters` carries `BusinessCenter (0..*)` wrappers (not `BusinessCenterEnum` directly).
- `LegalAgreementIdentification` carries `vintage : int`, not a "version string".
- `PartyIdentifier` uses `identifierType : PartyIdentifierTypeEnum` and `[metadata scheme]` annotation, not a "source" attribute.
- `ObservationIdentifier` field list now includes `informationSource : InformationSource (0..1)` — the CDM-native carrier for NDF fixing-source (KFTC18, etc.).
- `transfer` field correction on `PrimitiveInstruction` — the field references `TransferInstruction` carrier with underlying `Transfer extends AssetFlowBase`.

## Iter1 R1 closures preserved through iter2

iter1 closed 36 R1 items (10 P-items + 7 multi-reviewer minors + 19 deferred single-reviewer minors, zero declined). banking-auditor's iter2 R2 review confirms all four iter1 majors (admission criteria for `status`; source-conflict deferred; carve-out narrowed; `document_hash` verification) HOLD through iter2. isda-board-advisor's iter2 R2 review confirms all three iter1 majors (IRS leg conventions; calendar controlling-purpose; lifecycle events `cash_settlement_amount_determined` and `index_cessation_fallback`) HOLD through iter2.

## Process integrity (verified by FORMALIS Phase 4 audit)

- **Forbidden vocabulary** (load-bearing claim, monoid, morphism, functor, presheaf, leaf class, mutation discipline, smart constructor, closed sum, veto register, Goodhart, Pareto): **zero occurrences**.
- **Numbered named rules / definitions environments**: zero.
- **Footnotes to parent corpus**: zero.
- **Cryptographic signing apparatus**: zero (appears only in two explicit out-of-scope statements).
- **VersionPin / version-axis machinery**: zero.
- **Operating-envelope numeric SLAs**: zero (access patterns and order-of-magnitude sizing are present and in scope; specific latency / throughput SLAs are not).
- **Tabulated CDM Direct/Partial/Missing mapping**: zero (per-concept CDM prose is in scope; a tabulated mapping is not).
- **First-principles discipline**: every requirement carries "we need X because [concrete consequence]" — verified by FORMALIS audit.
- **Worked examples**: every catalogue concept carries at least one populated worked example.
- **Page count**: 15 pages (at the user-relaxed cap; no headroom).
- **Compile cleanliness**: zero pdflatex errors, zero undefined references, zero LaTeX warnings.

## FORMALIS Phase 4 audit verdict

**"market_data_mvp_v2.0 is complete and consistent."**

All ten audit dimensions PASS (three-pillar defensibility; catalogue actionability with worked examples; first-principles discipline; Phase 0 rulings; tone constraints; out-of-scope absence; iter2 content changes landed; R3 polish closures; page-count discipline; compile cleanliness).

Audit file: `market_data_mvp_v2_work/phase4/formalis_phase4_audit_iter2.md`.
Standalone sign-off: `market_data_mvp_v2.0_formalis_signoff.md`.
