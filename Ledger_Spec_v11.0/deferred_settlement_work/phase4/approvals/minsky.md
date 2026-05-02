# Phase 4 Approval — MINSKY

**Document:** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/deferredSettlement.tex`
**Date:** 2026-05-02

## Verdict: APPROVED

## Rationale

1. **Phantom wallet handles** (§sec:implementation-types, lines 1763–1788): `real_wallet | cpty_virtual_wallet | csd_virtual_wallet` parameterising `wallet_handle` makes `emit_discharge` on a real wallet a type error — DS1/DS17 enforced by the compiler, not by review.
2. **PairedObligation** (lines 1793–1814): abstract type, sole constructor `pair`, closed-sum `pairing_error` with five constructors (`Different_trade_id`, `Different_settle_dates`, `Mirrored_qty_mismatch`, `Same_side_pairing`, `Wrong_leg_units`); no public path from a single `Obligation.t` to discharge — DvP-E atomicity is a type property.
3. **Lifecycle closed sum** (lines 268–298): 8-constructor `LifecycleState` with explicit terminal set; transitions enumerated, exhaustive match in step function, no wildcards.
4. **FailureReason closed sum** (lines 290–298): 7 constructors; `NoCover`/`NoFunds` split is sharper than a single underflow case.
5. **Newtype dates + scoping**: `TradeDate.t` and `SettleDate.t` distinguished at the API surface (`emit_trade`, `Different_settle_dates`); full newtype hierarchy and phantom accounting basis deferred to v11.1 with documented reason (line 2029). Scope held to the v11.0 core five items; §2.8 explicitly rejects the seventh GPM coordinate, fresh per-obligation units, single-aggregate wallets, and external-only state.

## Sign-off

The compiler will refuse to skip T+2. Approved for Phase 5.

— MINSKY, Phase 4 Settlement Team, 2026-05-02
