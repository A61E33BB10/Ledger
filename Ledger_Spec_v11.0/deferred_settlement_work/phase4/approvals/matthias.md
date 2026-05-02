# Phase 4 Approval — Matthias Vogt (rosetta-cdm-engineer)

**Verdict: APPROVED**

**Document:** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/deferredSettlement.tex` §10 (lines 1478-1607)
**Date:** 2026-05-02

**Rationale (5 lines):**
1. Cross-walk longtable PRESENT (lines 1489-1524): 24-row inventory with Direct 11 / Partial 6 / Missing 7 split; CDM 6.0.0 type names (`TransferStatus`, `Transfer`, `TradableProduct`, `settlementTerms.settlementDate`, `Party.partyId`) used correctly.
2. Five strategic gaps (Gap 6 TransferStatus enrichment, Gap 7 subsumed in 6, Gap 8 CSDRPenaltyDetail, Gap 9 BuyIn types, Gap 10 first-class Obligation) plus +1 doctrinal Gap 11 (economic-exposure-at-T, line 1518) — the 5+1 structure is exactly correct.
3. Four PR-sized Rosetta extension sketches with realistic line budgets (~80/120/150/200) and non-breaking sequencing — full Rosetta source correctly deferred to Phase 2 deliverable, doctrine carried in spec.
4. Proposition 1 (line 1545) proves F : Lg → CDM is a functor (id/composition preserved) but lossy (wallet-axis collapse) AND non-faithful (cpty_virtual-axis morphisms collapse to single BusinessEvent); economic quotient Lg_econ restoring faithfulness is the categorically-correct repair.
5. ISO 20022 witness substream mapped completely (sese.023/024/025/027, camt.053/054/056, pacs.004, semt.044, MT 54x); framing as witnesses-not-transitions is CDM-charitable; "what NOT to use" section correctly flags `partialCashSettlement` and `sixtyBusinessDaySettlementCap` as CDS-only false friends.

**Signed:** Matthias Vogt, Principal Engineer, FINOS CDM core team
