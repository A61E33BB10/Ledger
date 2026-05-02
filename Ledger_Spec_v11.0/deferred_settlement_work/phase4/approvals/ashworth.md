# Phase 4 Settlement Team Approval — Reginald Ashworth, FCA

**Document:** `Ledger_Spec_v11.0/deferredSettlement.tex`
**Date:** 2026-05-02

## Verdict: APPROVED

## Rationale (5 lines)

1. **Trade-date mandatory ruling** correctly grounded in IFRS 9.B3.1.3 (regular-way exception) with B3.1.5 properly excluded for FVTPL/dealer book; ASC 320-10-25-3, IFRS 13.B5.1.2A, CRR Art 274 (SA-CCR) and Art 325 (FRTB) capital rationale all cite-correct (lines 1304–1321).
2. **Balance-sheet substantiation** journal entries cross-foot independently: T (Dr FVTPL 5,000 / Cr Settlement payable 5,000), T+1 mark 100×($52−$50)=$200 (Dr 200 / Cr P&L 200), T+2 reclass at carrying 5,200 — all balanced; no P&L at finality preserves v10.3 P10 path-independence (lines 1323–1348).
3. **Five-document audit chain** (FIX 8=ExecRpt → sese.023 → sese.025 → camt.054 → CSD depot statement) is end-to-end with signature-verification and content-hashing; ISA 500.6 / ISA 505 / PCAOB AS 2310 / BCBS 239 P6 / SOX 404 / SOC 1 / IFRS 7.B11 stack is the correct authority chain (lines 1350–1369).
4. **CRR 378 / 379 / 380** verified: FoP 100% RW; CRR III ramp 100%/625%/937.5%/1,250% effective 1 Jan 2025; large-exposure 10% CET1 → Art 395; worked Pillar 3 arithmetic checks (€2m × 625% × 12% = €1.5m CET1 at T+16; €2m × 1,250% × 12% = €3m CET1 at T+46).
5. **CORRECTION four-eyes** enforced as framework-level validation, not procedure: requester_lei ≠ approver_lei rejected structurally; CROSS_CORRECTION ≥2 tx_ids; CORRECTION_OF_CORRECTION requires audit-committee attestation; bitemporal append preserves IAS 8.42 — meets SOX 404 ICFR segregation of duties (lines 1434–1474).

## Observations (non-blocking)

Materiality matrix not tabulated in §9 (covered by reference); cum/ex manufactured-payment cross-ref to §6.3 desirable in v11.1. Neither rises to materiality.

## Signoff

Reginald Ashworth, FCA — Senior Partner, Head of Banking Assurance — 2026-05-02
