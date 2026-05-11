# market_data_mvp_v1.0 — Reviewer Convergence Record

**Document:** `market_data_mvp_v1.0.tex` (10 pages, 38,554 bytes source)
**PDF:** `market_data_mvp_v1.0.pdf` (10 pages, 519 KB)
**Date converged:** 2026-05-10
**Audience:** data engineering team (SQL / Avro / Protobuf / ETL)

## Three load-bearing claims defended

1. **CDM as wire vocabulary** (FINOS Common Domain Model 6.0.0). Wire formats and reference identifiers conform to CDM types. Every cited Rosetta filename verified live against `finos/common-domain-model@master` on 2026-05-10.
2. **Provenance and attestation envelope.** Every record carries a signed envelope containing attestor LEI, payload hash, signature, source / gateway IDs, idempotency token, and bitemporal timestamps. Nothing is overwritten; restatement is a new bitemporal row.
3. **Bitemporal storage with first-class time-travel queries.** Two query modes (`as_of(t_known)` and `with_corrections_through(t_obs, t_known')`); explicit primary key, uniqueness, covering index, and tie-break semantics; worked EUR/USD restatement fixture demonstrates both modes against documented expected values.

## Phase 0 binding rulings — all honoured in v1.0
- R1 RawMarketObservation admission-outcome English invariant: present (Rule 8).
- R2 No `TradeState.valuationHistory` citation: zero occurrences.
- R3 Rosetta filenames cited not docs URLs: eleven `.rosetta` filenames, all verified live.
- R4 AttestationEnvelope as one named field-set: explicit at L99; tuple at L102–106.
- R5 Trust Registry first-class: catalogue row at L231 with full PK, sibling AuthorityAssumption table.
- R6 §A and §C as single tables; two worked queries: 15-row catalogue is one table; §5 contains both query modes against shared fixture.

## Round-by-round grades

| Reviewer | Lens | R1 | R2 | Δ | R1 blocking | R2 blocking |
|---|---|---:|---:|---:|---:|---:|
| rosetta-engineer | Rosetta DSL fidelity | 4.5 | 8.7 | +4.2 | 1 | 0 |
| rosetta-cdm-engineer | CDM data-model mapping | 6.7 | 8.4 | +1.7 | 1 | 0 |
| banking-auditor | IFRS / audit / ICFR | 7.8 | 8.6 | +0.8 | 0 | 0 |
| isda-board-advisor | ISDA market practice | 7.4 | 8.0 | +0.6 | 0 | 0 |
| nazarov-data-architect | Data engineering reality | 7.4 | 8.6 | +1.2 | 0 | 0 |
| finops-architect | Operational cost / feasibility | 6.4 | 7.6 | +1.2 | 2 | 0 |
| formalis | Convergence arbiter | 8.0 | 8.7 | +0.7 | 0 | 0 |
| **Mean** | | **6.46** | **8.37** | **+1.91** | | |

**Convergence rule (orchestration §5):** "all seven reviewers assign a grade of at least 7.0/10 in the same round, with no blocking items outstanding from any reviewer."
**Convergence reached at Round 2.** Lowest R2 grade: 7.6 (finops-architect). Total blocking items in R2: 0.

## R1 → R2 closures

**Three R1 blocking items, all closed in v0.2:**
- B1 (rosetta-engineer + rosetta-cdm-engineer): Three of four pinned Rosetta filenames returned HTTP 404 against `finos/common-domain-model@master`. Closed by re-verifying eleven filenames live and rewriting §3 plus every affected table cell.
- B2 (finops-architect): No volumetrics, retention horizon, or cost envelope. Closed by adding the "Operating envelope" subsection in §5 with quantitative SLAs.
- B3 (finops-architect): Signature verification path undefined as hot vs. batch. Closed in the same operating-envelope subsection (in-process LRU key cache, p99 ≤ 500µs verification SLA, fail-closed cache miss).

**Twenty-nine R1 majors:** all closed in v0.2 except four PARTIAL closures, each promoted to a P-item and closed in the v0.3 polish round.

## R2 → v0.3 polish closures

R2 surfaced engineering concerns that did not block convergence but warranted a polish round before sealing v1.0. All nine P-items closed in v0.3:

- **P-1** (nazarov M-R2-1): Trust Registry PK coherence defect — single-LEI PK collided with append-only key rotation. Fixed via PK `(attestor_lei, key_valid_from)` with partial uniqueness on currently-live key.
- **P-2** (nazarov M-R2-2): `authority_assumption_ref` target shape undefined — sibling `AuthorityAssumption` table introduced.
- **P-3** (banking-auditor MA1): Online queryability throughout retention — explicit clause added.
- **P-4** (banking-auditor MA2): 60-second revocation propagation window admitting compromised-key records — closed via dual-gate revocation: snapshot-time re-evaluation against authoritative registry quarantines records signed by keys revoked at any time prior to consumption.
- **P-5** (banking-auditor MA3): Cache-miss fail-open vs fail-closed — fail-closed mandated with typed rejection event.
- **P-6** (isda M-ISDA-R2-1): LegalAgreement Master / Schedule / CSA / Para-11 override walk — promoted from catalogue cell to numbered Rule with explicit head-to-tail walk.
- **P-7** (rosetta-cdm R2-MAJ-1): CalibratedMarketObject field list — five mandatory fields specified with cardinalities.
- **P-8** (finops M-R2-1): Calibrated curves storage policy — knot-point representation with content-hash dedup.
- **P-9** (finops M-R2-2): 10x burst gateway sizing — verifier-thread count specified (≈4 threads / gateway, two gateways minimum).

Six cheap minors also closed: glossary `payload_hash`, axis-count phrasing uniform, undefined-tie routes to break register, residual-envelope canonicalisation pin, `gateway_time ≡ t_known` default, 33rd-restatement diversion path. Zero items declined.

## Final reviewer sign-off positions

Each reviewer's R2 sign-off condition either was already met by v0.2 or was closed by v0.3 polish:

- **rosetta-engineer** (R2: 8.7) — "None blocking; the four minor items are documentation polish and can be folded into the next routine pin-bump cycle without re-review."
- **rosetta-cdm-engineer** (R2: 8.4) — Sign-off condition was R2-MAJ-1 (CalibratedMarketObject field list); closed as P-7 in v0.3.
- **banking-auditor** (R2: 8.6) — Sign-off condition was MA1 + MA2 (online queryability + revocation hole); closed as P-3 + P-4 in v0.3.
- **isda-board-advisor** (R2: 8.0) — Sign-off condition was the LegalAgreement override Rule (M-ISDA-R2-1); closed as P-6 in v0.3.
- **nazarov-data-architect** (R2: 8.6) — Sign-off condition was M-R2-1 + M-R2-2 (Trust Registry coherence + AuthorityAssumption shape); closed as P-1 + P-2 in v0.3.
- **finops-architect** (R2: 7.6) — Sign-off condition for 8.0+ was M-R2-1 + M-R2-2 (calibrated-curve dedup + verifier-thread sizing); closed as P-8 + P-9 in v0.3.
- **formalis** (R2: 8.7) — "Signed off at 8.7. The three R1 Majors are closed; M-AT-4 is closed; cross-coupling between payload_hash, signature scope, VersionPin's canonicalisation axis, and the bitemporal PK is internally consistent."

## Process integrity

- Forbidden vocabulary (monoid, morphism, functor, presheaf, leaf class, mutation discipline, smart constructor, closed sum, veto register, Goodhart, Pareto): **zero occurrences** in v1.0, audited at every round.
- First-principles discipline: every concrete requirement carries a "we require X because, in absence of X, [picturable failure]" justification — verified by FORMALIS Phase 4 audit.
- 10-page hard cap: **10 pages exactly** in v1.0 (= cap; zero headroom).
- Compile cleanliness: zero pdflatex errors, zero LaTeX warnings, zero undefined references. One cosmetic 2.4pt Overfull hbox in the catalogue longtable, below normal-report thresholds.

## FORMALIS Phase 4 audit verdict

**market_data_mvp_v1.0 is complete and consistent.** All nine audit dimensions (three-claim defensibility, first-principles discipline, Phase 0 R1–R6 honoured, internal consistency, forbidden-vocabulary absent, audience contract, parent-corpus faithfulness, page-count discipline, compile cleanliness) PASS.

Sign-off written to `market_data_mvp_work/phase4/formalis_phase4_audit.md`.
