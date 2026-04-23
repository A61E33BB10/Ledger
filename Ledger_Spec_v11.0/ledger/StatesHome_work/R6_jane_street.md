# R6 — Jane Street CTO: Ship Decision, 3 vs 4 Maps

**Reviewer:** CTO, Jane Street. Production lens. The junior on-call at 3am is the ultimate arbiter.
**Under review:** collapse `WalletState` into the unit sectors; ship 3 maps.

---

## 1. Three maps vs four

**Ruling: 3 maps.** R5 is unambiguous. The two per-wallet economic fields we stress-tested — HWM/fees/mandate in the SMA case (R5_managed_account), HWM in the QIS case (R5_qis) — both landed on a **unit key**, not a wallet key:

- SMA: mandate lives in `ProductTerms[u_MA]`; HWM/fees/breach flags live in `WalletState[w_C].overlays[u_MA]` — i.e., *already keyed by a unit*, just with a wallet-indexed outer map.
- QIS: R5_qis explicitly overturns R3_karpathy: HWM is `PositionState[w_C, u_QIS]`, not `WalletState[w_C]`. Multi-strategy subscribers prove the `(w,u)` key is required.

Once `WalletState` is universally an overlay-map keyed by a mandate unit, the outer wallet layer is decoration. `PositionState[w, u_MA]` is the same shape, already keyed the right way. Collapsing removes a sector that in every stress test resolved to "indexed by a unit anyway."

**Dev-experience test.** "Declare which sectors you use: `ProductTerms` + `UnitStatus` + optional `PositionState`" is genuinely simpler than a fourth optional sector whose contents turn out to be unit-indexed. A new instrument family's author writes one decision table per unit type and one handler; no "and do I need a WalletState row?" fork.

**Non-economic metadata.** Permissions, KYC, audit cursor, authenticated-identity binding are **not financial state**. They belong in a separate wallet-registry table (akin to the Unit Store for units), read by capability-scoped accessors. This is not a sidecar hack — it is the correct separation. Financial state is what handlers read to price, settle, and enforce conservation. KYC does not enter a `StateDelta`. Splitting the wallet registry off the financial state model **strengthens** C4 (capability-scoped cross-wallet reads, R4_formalis).

## 2. "Mandate is a unit" — structurally required, and natural

v10.3 Sec 6 already says "Wallets as Managed Accounts" and "CSA margin as a wallet-level smart contract." Both are smart contracts; every smart contract lives in `\mathcal{U}`. R5_managed_account §2 makes this explicit and enumerates the payoff: amendments get a `ProductTerms` audit trail; 500 SMAs on one template share one unit (no denormalisation).

Counter-example search: a regulatory mandate like "no short-selling during market turmoil" is system-wide — a global handler precondition, not per-wallet state. It does not need a home in this model. Every mandate that carries per-wallet state is contractual, hence a unit. **No hack.**

## 3. Final type signature — verdict

```python
ProductTerms:  Map[UnitId, NonEmptyList[TermsVersion]]   # total on registered u, append-only
UnitStatus:    Map[UnitId, UnitStatus]                   # total on registered u, mutable
PositionState: Map[tuple[WalletId, UnitId], PositionState]  # monotone carrier, Option accessor
```

**Approved as shipping signature.** Three disciplines, three maps. `NonEmptyList` (not `List`) in `ProductTerms` — registration guarantees v0 exists; makes `.head` total. Accessor contract:

- `product_terms(u) -> NonEmptyList[TermsVersion]` — total on registered `u`.
- `unit_status(u) -> UnitStatus` — total on registered `u`, product-declared defaults at registration (C5, C7).
- `position(w, u) -> PositionState | None` — partial; `None` distinct from `Some(zero_P)` (C1).

`holders_of(u)` returns currently-present rows (monotone carrier, `Some` including `Some(zero_P)`); naming it `addressed_holders_of(u)` in the API avoids the ever-vs-currently ambiguity R4_jane_street flagged.

## 4. Amendment rule (C8): two-track by fungibility predicate — accept

**Accept.** R5_untraded Q3 resolution is correct. The predicate lives in the `ProductTerms` smart contract — each product type declares its own fungibility rule, because what counts as fungibility-preserving is product-specific (coupon step-up on CDS trigger vs. bond restructuring vs. CSA eligible-collateral change).

Signature:

```python
class ProductTerms(Protocol):
    def is_fungibility_preserving(
        self, proposed: TermsVersion
    ) -> bool: ...
```

Called at amendment time on the current head (`self` is the `TermsVersion` in force). `True` → append to `ProductTerms[u]`. `False` → allocate fresh `u_new`, emit `SupersededBy(u_old -> u_new)` on both `UnitStatus` rows, force synthetic novation of open positions. Predicate is a pure method; no side effects, no I/O.

## 5. Final call

**SHIP. 3 maps.**

Final map count: **3**.

Shipping signature:
```
ProductTerms:  Map[UnitId, NonEmptyList[TermsVersion]]     # total, append-only
UnitStatus:    Map[UnitId, UnitStatus]                     # total, mutable
PositionState: Map[(WalletId, UnitId), PositionState]      # monotone carrier, Option accessor
```

Conditions C1–C10 from R4/R5 carry forward unchanged except C4 (capability-scoped wallet reads now applies to the wallet-registry table, not this financial state model). Wallet registry (permissions, KYC, audit cursor) is a separate concern with its own accessor, explicitly out of scope for `StateDelta`.

— Jane Street CTO, sealed.
