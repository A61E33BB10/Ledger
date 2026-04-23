# R5 — Managed Account Stress Test of the Four-Map Proposal

*Test case 2. SMA at manager A for client C: long-only global equity, 5% single-name cap, MSCI ACWI benchmark, 2% mgmt + 20% perf over HWM. Trades cash equities, index futures, FX forwards.*

**Proposal:** `ProductTerms[u]`, `UnitStatus[u]`, `WalletState[w]`, `PositionState[w,u]`. `Option`/accessor, monotone/carrier, conservation/handler.

---

## 1. Field taxonomy

Let `w_C` be C's SMA wallet, `w_C_cash` its cash sub-wallet, `u_bench` the ACWI benchmark unit, `u_MA` the managed-account contract unit (see §2), `u_ES` a CME future, `u_FX` an OTC FX forward.

| Field | Home | Why |
|---|---|---|
| `u_ES.{multiplier, ccp, expiry, tick_size}`; ACWI methodology | `ProductTerms[u]` | Static; set at registration. |
| SMA mandate text (5% cap, long-only, universe), fee schedule (2%/20% HWM), benchmark pointer = `u_bench` | `ProductTerms[u_MA]` | Mandate **is** a smart contract (§2). Versioned append-only; amendment allocates new `u_MA'`. |
| `u_ES.{lifecycle_stage, last_settlement_price}`; `u_bench.index_value_t` | `UnitStatus[u]` | Exchange/index publishes one value per day, shared across all holders. |
| `HWM`, `hwm_date`, `accrued_mgmt_fee`, `accrued_perf_fee` | `WalletState[w_C]` | Scalar over the account's performance; `u` absent from definition. |
| `benchmark_nav_at_inception` | `WalletState[w_C]` | Per-wallet baseline snapshot (see §5). |
| `subscription_cursor`, `redemption_cursor` | `WalletState[w_C]` | Idempotent ordering of S/R events for this account (see §4). |
| `mandate_breach_flags : Map[ConstraintId → {clean, breached, cured}]` | `WalletState[w_C]` | Compliance state of the wallet, not any unit. |
| `ac(w_C, u_ES)`, per-CCP binding | `PositionState[w_C, u_ES]` | `Σ_w ac(w, u_ES) = 0` expressible only here (R4 FORMALIS C2). |
| `u_FX` per-trade lifecycle (fixing paid, etc.) | `PositionState[w_C, u_FX]` | OTC trade = unique `u`; lifecycle is per-holder-per-trade. |
| Cash equity (AAPL, etc.) balances | ledger balance `w_C(u_AAPL)` | Base layer. Equities carry nothing beyond balance. |

## 2. Is the mandate itself a unit? **Ruling: YES.**

Sec 6 treats MA wrappers as smart contracts; every smart contract lives in `\mathcal{U}` with a `ProductTerms` row. The mandate — 5% cap, long-only, fee schedule, benchmark pointer, HWM hurdle — is exactly `ProductTerms[u_MA]`.

1. **Amendments need a home.** Cap 5%→7%, benchmark swap, universe carve-out are ISDA-style amendments. R4 Jane Street's reason for splitting `ProductTerms` from `UnitStatus` — "terms is amend-only with audit trail" — is exactly the SMA mandate's discipline.
2. **Sharing works.** Manager A runs 500 SMAs on the same template. Mandate in `WalletState` → 500 copies consistent under amendment (denormalisation bug; R1 MINSKY). Mandate in `ProductTerms[u_MA]` → 500 wallets point at one unit; amendment allocates `u_MA'` and affected wallets re-subscribe atomically.
3. **`WalletState[w_C]` stores only C's instance data:** HWM, fee accruals, breach flags, baseline, cursors. Personal counters, not contract terms.
4. Sec 6.5 ("Mandate Constraints as Smart Contract Guards") already reads this way. The ruling formalises Sec 6.

The mandate **contract** is a unit; the mandate **state for this client** is `WalletState[w_C].overlays[u_MA]` — R4 Jane Street's overlay shape.

## 3. HWM and performance fee crystallisation

**HWM lives in `WalletState[w_C]`** (one scalar; R3 KARPATHY). Not in `ProductTerms` (terms define the *rule*, not the value); not in `PositionState[w_C, u_MA]` (single holder; `(w,u)` key adds nothing).

**Crystallisation `StateDelta` at quarter-end `t_k`** — three maps, one atomic commit (R4 FORMALIS C3): `WalletState[w_C]` writes `hwm ← max(hwm, NAV_{t_k})`, `accrued_perf_fee ← 0`; `moves` emits one cash leg `w_C_cash → w_A_cash` for the fee (structural zero-sum at `Move.mk`); `PositionState` untouched.

**Redemption:** HWM *preserved* on partial redemption (standard: no reset for residual NAV). On full redemption + re-subscription, the monotone carrier keeps `WalletState[w_C]` live; HWM persistence is encoded in `ProductTerms[u_MA].redemption_hwm_policy`, not a storage question.

## 4. Subscription/redemption cursor

**`WalletState[w_C]`-keyed, not `(w_C, u_cash)`-keyed.** The cursor orders S/R events for *this account*; it does not vary with `u`. Keying by `(w, u_cash)` forces a separate cursor per currency — wrong discretisation. A subscription is a cash move `w_C_sub_ext → w_C_cash`; the cursor is a property of the SMA's S/R processor, not any cash position. R1 FINOPS §3: per-holder lifecycle events are keyed on `w`.

## 5. Benchmark: dual residency is fine

`UnitStatus[u_bench].index_value_t` (shared, one level/day) and `WalletState[w_C].benchmark_nav_at_inception` (C's baseline) are different fields on different keys. `index_value_t` is a per-`u` observable; copying into `WalletState` would be R1 MINSKY's "disagreement across holders" bug. `benchmark_nav_at_inception` is a per-`w` scalar snapshot taken by the MA handler at SMA opening — not a copy of the live index. Relative performance is computed at handler time from both inputs.

R3 FEYNMAN gauge argument: `U` sector (index level) and `W` sector (inception snapshot) are distinct subrepresentations; `WalletState` and `UnitStatus` preserve the separation.

## 6. One ambiguity: multi-mandate overlays

Four-map handles one mandate per wallet cleanly. **Ambiguity arises with two mandate contracts on one wallet** — e.g., C layers a "no Russia" overlay mandate atop the base mandate. Both `u_MA_base` and `u_MA_overlay` attach to `w_C`. Where does `accrued_perf_fee` live?

- (a) One `WalletState[w_C].accrued_perf_fee` scalar → two handlers write the same field; structural uniqueness lost.
- (b) `WalletState[w_C].overlays : Map[u_MA_id → OverlayState]` (R4 Jane Street's sparse overlay map). Then `overlays[u_MA_base].perf_fee` and `overlays[u_MA_overlay].perf_fee` are handler-local and distinct.

**Verdict:** no failure of the four-map proposal, but R4 Jane Street's overlay-keyed refinement must be **promoted from recommendation to requirement**. Flat scalars on `WalletState` will break the first time a master-overlay structure ships. This is the single concrete gap surfaced by the SMA stress test.

## 7. Relation to Sec 6.1

**Formalises; does not conflict.** Sec 6.1 ("every wallet is a managed account") reads Reference Portfolio performance off `w_{ref}` to emit settlement moves. The four-map proposal makes this precise:

- "Reference Portfolio" = `w_{ref}` with `PositionState[w_{ref}, u]` rows.
- "Managed-account smart contract" = `u_MA` with `ProductTerms[u_MA]` (mandate + fees) and handler emitting `StateDelta`.
- "Ultimate Beneficiary link" = `WalletState[w_{ref}].overlays[u_MA].beneficiary = w_UB`.
- "Observe–Crystallise–Reset" = the `u_MA` handler's atomic four-map `StateDelta` at each reset.

"Every wallet is a managed account" reads as: every wallet *may* have a managed-account overlay; plain trading book is the `None` case. Sec 6.5's guards become preconditions in the `u_MA` handler reading `WalletState[w].overlays[u_MA]` and `ProductTerms[u_MA]`, rejecting breaching `StateDelta`s.

---

## Return summary

**Field taxonomy.** `ProductTerms[u]`: mandate terms, fee schedule, benchmark identity, product statics (multipliers, ccp, expiry, index methodology). `UnitStatus[u]`: shared mutable observables (last settle price, index level, lifecycle stage). `WalletState[w]`: HWM, fee accruals, breach flags, benchmark NAV at inception, S/R cursors — **overlay-keyed by `u_MA`**. `PositionState[w, u]`: futures accumulated cost, per-trade OTC lifecycle. Ledger balances: cash equities.

**Mandate-as-unit ruling: YES.** The mandate is a smart contract; every smart contract is a `u` with `ProductTerms`. `WalletState[w_C].overlays[u_MA]` carries holder instance data. This formalises Sec 6 and matches R4 FORMALIS C4 + R4 Jane Street sparse-overlay discipline. The one caveat — multi-mandate composition requires overlay-keyed `WalletState`, not flat scalars — is promoted from recommendation to requirement.

