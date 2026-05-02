# CARTAN Phase 4 Completeness Audit

**Artefact:** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/deferredSettlement.tex`
**Author (sole):** KARPATHY  **Length:** 2151 lines  **Date:** 2026-05-02

## Verdict: **PASS**

## 1. Section Architecture (12 required)

All twelve substantive sections present, in the canonical pedagogical order:

1. The Problem (sec:problem)
2. Why the Naive Solutions Fail (sec:strawmen)
3. The State Model (sec:state-model)
4. The Standard Buy, in Full (sec:standard-buy)
5. The Standard Sell (sec:standard-sell)
6. Variants (sec:variants)
7. Composition Cases (sec:composition)
8. Reconciliation to the Nostro and Depot (sec:reconciliation)
9. Accounting and Regulatory Footprint (sec:accounting)
10. CDM Mapping (sec:cdm)
11. Implementation Notes (sec:implementation)
12. Invariants DS1--DS19 (sec:invariants)

Plus Out of Scope, Glossary, Closing, Bibliography. Cross-references resolve.

## 2. Floor Cases

**CORE:** T+2 buy (Sec.4, full move-by-move), T+2 sell (Sec.5), T+1 (Sec.6.1),
fail/CSDR (Sec.6.4 + CSDR_PENALTY row), partial (Sec.6.3, D_max=2), recon (Sec.8).

**COMPOSITION:** short with SBL six-coordinate (Sec.7.1), recall (wire-recall Sec.6.6;
SBL recall Sec.7.1), CA in window (Sec.7.3, manufactured payment), x-ccy/Herstatt (Sec.7.4),
DvP (DS18 + PairedObligation type Sec.11.7). All present.

## 3. Primary Invariants (12 required as `\begin{invariant}` blocks)

DS1 (line 1899), DS3 (1905), DS4 (1911), DS7 (1917), DS9 (1923), DS10 (1929),
DS11a (1935), DS11b (1941), DS12 (1947), DS17 (1953), DS18 (1959), DS19 (1965).
All twelve present as numbered invariant blocks with Type and Severity tags.
Restated v10.3 invariants (DS2/5/6/8/14/15/16) listed by reference at line 1996.

## 4. Conservation Lifting Theorem (H1-H5)

Theorem at line 1270 with all five named hypotheses: H1 (move balance), H2
(virtual sign correctness), H3 (state-only moves vacuous), H4 (universe
constancy), H5 (CORRECTION respects H1). Inductive proof complete.

## Sign-off

CARTAN completeness criteria satisfied without remainder.
Henri Cartan / Bourbaki desk -- 2026-05-02
