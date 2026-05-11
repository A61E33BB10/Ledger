# FORMALIS Sign-off Statement — market_data_mvp_v2.0 (iter2 final)

**Document:** `market_data_mvp_v2.0.tex` (15 pages of a 15-page user-relaxed hard cap)
**Date:** 2026-05-10
**Issued by:** FORMALIS, in its Phase 4 completeness-audit role per the v2 orchestration prompt §4.

---

## Statement

> **market_data_mvp_v2.0 is complete and consistent.**

## Basis

The Phase 4 audit verified all ten completeness dimensions against the v2 stated audience (data engineering team), the iter2-revised catalogue-first structure (with per-concept CDM detail and the new fast-loading section), and the user-relaxed 15-page hard cap. All ten dimensions returned **PASS**:

| # | Dimension | Result |
|---|---|---|
| 1 | Three pillars defended (CDM as wire vocabulary; provenance with `source`/`t_obs`/`t_known`/`restates_ref`; bitemporal storage with two query modes) | PASS |
| 2 | Catalogue actionable with worked examples (12+ concepts each with field list, carrier, first-principles "we need" justification, populated worked example, and factually-correct CDM mapping prose) | PASS |
| 3 | First-principles discipline (every requirement carries "we need X because [concrete consequence]") | PASS |
| 4 | Phase 0 rulings honoured (SBL out-of-scope; `confirmation_received` folded into Lifecycle; admission `status` enum `{consensus \| single_source \| quarantined}`; CCP-margin dropped; on-chain one line) | PASS |
| 5 | Tone constraints (no numbered rules; no "load-bearing claim"; no footnotes-to-parent; no category-theoretic vocabulary) | PASS |
| 6 | Out-of-scope items absent (no cryptographic apparatus; no VersionPin; no operating-envelope numeric SLAs; no tabulated CDM Direct/Partial/Missing mapping) | PASS |
| 7 | Iter2 content changes correctly landed (audience paragraph removed; per-concept CDM detail accurate after polish; new §5 fast-loading at correct level; 15 pages) | PASS |
| 8 | R3 polish closures verified verbatim (no `ForwardPayout`; `Observable` 3-branch with `Curve` deprecated-separate; `EventInstruction` in `event-workflow-type.rosetta` with `Instruction (0..*)`; `PrimitiveInstruction` as record with optional fields; `LegalEntity.jurisdiction` Ledger-local; CSA thresholds/MTAs on `CreditSupportObligationsBase`) | PASS |
| 9 | Page-count discipline (15 pages, at cap) | PASS |
| 10 | Compile cleanliness (zero errors, zero undefined refs, zero LaTeX warnings) | PASS |

## Convergence path summary

- **iter1 R1**: convergence reached (all 7 ≥ 7.0/10, mean 8.0, zero blocking).
- **iter1 polish**: closed 36 R1 items (10 majors + 7 multi-reviewer minors + 19 deferred minors; zero declined). 11 pages.
- **iter2** (user requested 4 content changes; cap raised 10 → 15): drop pedantic audience paragraph; per-concept CDM detail from live `github.com/finos/common-domain-model@master`; new §5 fast-loading section; fill 15 pages.
- **iter2 R2**: convergence reached again (all 7 ≥ 7.0/10, mean 8.33, zero blocking). rosetta-engineer flagged five confirmed-fictional CDM types as majors; rosetta-cdm-engineer corroborated two as majors.
- **iter2 polish (R3)**: closed all 6 major CDM corrections + 5 minor refinements via character-bounded text swaps; net-zero line change; document holds at 15 pages. Every cited Rosetta filename and type body re-verified against live master on 2026-05-10.

The four user-requested iter2 content changes all landed:
- Audience paragraph removed; surviving "three things" and "catalogue first" framing folded into an unnumbered preamble.
- Per-concept CDM mapping prose for every catalogue concept, with verified Rosetta types, filenames, and cardinalities — and no fictional types after the iter2 polish.
- New §5 "Loading for the pricing library" naming six concrete access patterns, the bitemporal-indexing implication, and the materialised-current-projection-as-cache pattern.
- 15-page budget filled without padding.

## Cosmetic residuals (do not affect sign-off)

- One unavoidable hyperref-driven non-warning under pdflatex; below normal-report thresholds.
- The fast-loading §5 sits between bitemporal storage and CDM-as-wire by design (load discipline references bitemporal indexing and feeds the CDM serialisation rule); stylistic placement defensible.

---

**FORMALIS Phase 4 audit (full):** `market_data_mvp_v2_work/phase4/formalis_phase4_audit_iter2.md`
**Reviewer Convergence Record:** `market_data_mvp_v2.0_convergence_record.md`

— Xavier Leroy, Chair, on behalf of the FORMALIS Committee
   2026-05-10
