# Phase 4 Approval — SBL Composition

**Reviewer:** Margaret Chen (sbl-specialist)
**Target:** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/deferredSettlement.tex` §7.1 (ll.1036-1054), with refs to §6.4 (CSDR), §10 (regulatory matrix), §12 (WS-6/WS-7).
**Date:** 2026-05-02

## Verdict: APPROVED

## Rationale (5 lines)

1. **GPM six-coordinate orthogonality (PASS):** ll.1039-1052 correctly state the orthogonality — six-tuple `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` with `avail = own - onloan + borr` lives on PositionState; seller delivery obligation lives on L_15 + cpty_virtual; "no interaction" between SBL coordinates and settlement FSM. No 7th coordinate (consistent with Phase 2 concession).
2. **Short-sale lifecycle (PASS):** Negative `own` under SSR Article 12(1)(c) locate is the correct legal-economic representation; locate Unit + `avail` projection enforce SSR/Reg-SHO at smart-contract guard level pre-admission. WS-6 covers the happy path.
3. **Recall in window (PASS):** ll.1054 — independent L_15 obligation processed on SBL settlement cycle; if `avail < obligation qty`, buy-in saga spawns. Matches GMSLA 9.3. WS-7 covers the test.
4. **Naked short / Reg SHO 204 / CSDR (PASS):** SSR 12(1)(c) cited; Reg SHO locate + FTD T+3 in matrix l.1421 (covers Rule 203/204 trigger points); CSDR Art 7 fully operationalised via `CSDR_PENALTY` L_15 row in §6.4 with deterministic ID; no real-wallet move on `Failed` preserves DS1.
5. **UTI gotcha (PASS):** SFTR Art 4 row l.1419 specifies dual-sided T+1 with dedup key `(reporting_LEI, UTI, action_type, event_date)`; borrow-leg-only UTI scope implicit in SFTR/MiFIR row separation; bitemporal trade-date vs fail-date subsumed by DS3.

## Sign-off

Margaret Chen — sbl-specialist — 2026-05-02
APPROVED
