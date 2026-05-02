# Phase 4 Settlement Team Sign-off — ISDA

**Verdict: APPROVED**

## Rationale

The §9.5 definitive matrix (lines 1402–1426) covers the eight live regimes with content-addressed dedup keys and bitemporal restatement: MiFIR Art 26/RTS 22 (T at trade-time, T+1 NCA-local), EMIR Refit Art 9 with `auth.030` and `cdm_payload` (DRR-generation-ready), CSDR Art 7 (`sese.024/025/027` + `semt.044`, penalty as deterministic function, buy-in via `Failed → BoughtIn|Compensated`), SFTR Art 4 (`auth.052` T+1 dual-sided), FINRA SLATE Rule 6500, Reg SHO (locate at T, FTD EOD T+3), Pillar 3/BCBS 239 (XBRL FINREP/COREP Q+45), IFRS 9/IAS 1/IAS 32 (iXBRL ESEF). T+1 is correctly framed as a parameter (`ProductTerms[u].settlement_cycle`); T+0 falls out by degeneracy via discharge-predicate substitution to an on-chain finality oracle (§7.2) — the load-bearing test passes. Trade-date accounting is mandated under IFRS 9 B3.1.3 and CRR Art 325 (FRTB) / Art 274 (SA-CCR); CRR Art 378–380 capital ramp is wired into the Pillar 3 aggregation. CORRECTION discipline implements IAS 8.42 bitemporally with four-eyes preconditions. The CDM 6.0.0 cross-walk and the four non-breaking PRs (Gaps 6/8/9/10) are the right posture.

One observation, not a blocker: §9.5 should carry an explicit DRR-coverage column (live: EMIR EU/UK; in progress: MIFID, SFTR; out of scope: CSDR, SLATE, Reg SHO) so the golden-source posture is visible to a Pillar 3 auditor. Defer to v11.1.

— Olivier Vantard, Senior Independent Advisor to ISDA Board
  2026-05-02
