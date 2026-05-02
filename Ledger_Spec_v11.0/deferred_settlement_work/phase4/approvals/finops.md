# finops approval
Verdict: APPROVED

The finops domain is faithfully represented end-to-end. PS/PSS surface forms of cpty_virtual are correctly bound to a single signed class (Def 3.2, Remark 3.3); L_15.Obligation owns lifecycle (Def 3.1, FSM Sec 3.6); the worked buy (Sec 4) and sell (Sec 5) verify per-unit conservation summing to zero at every state and reproduce the +$200 trade-date PnL with zero cash movement -- the headline that distinguishes the design from both strawmen. The boxed recon identity (Sec 7.1) verifies numerically on buy and sell at LHS=RHS=$1,000,000.00, hardened to a corollary of the Conservation Lifting Theorem (Sec 7.7, H1-H5). Decimal discipline (D_8/D_2/D_0, ROUND_HALF_EVEN, no floats, no implicit FX, per-ccy tolerances pinned in L_7^P) locked at Sec 4.1; idempotency structural via tx_id = hash_jcs(business_event_id, attempt_seq) (Sec 9.4) and dedup_key with schema_version (Sec 9.1, DS19 BLOCKING). DS3, DS4, DS7, DS18 correctly scoped at CRITICAL.

Specific drift if any:
- Minor (non-blocking): Sec 4.3 walks two valuation forms before boxing the disciplined active-set rule; the intermediate "discrepancy of $200" prose is pedagogically valuable but a fast reader could mis-extract the wrong form. Boxed rule and headline $200/$150 numbers land correctly.
- Minor (recorded for Phase 5): WS-1..WS-12 (Sec 9.10) do not include an explicit gross-disclosure projection assertion (max(0, +/-balance) per Sec 3.2 Remark). Acceptance documented; flag for walking-skeleton extension.
- Sign convention (positive = we owe; negative = they owe us) is consistently applied across PS/PSS, recon identity, and both buy and sell verifications.
- csd_virtual mirror keyed (csd_lei, holder_lei, u) ties one-to-one with camt.053 / sese.025 evidence; recon identity closes without a broker-virtual fudge.
- Conservation Lifting Theorem (Sec 7.7) subsumes the open-window invariant as a corollary; cleaner than asserting it independently.

Signoff: "As finops-architect, I APPROVE deferredSettlement.tex for publication."
