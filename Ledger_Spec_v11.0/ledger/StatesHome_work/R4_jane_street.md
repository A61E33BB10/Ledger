# R4 — Jane Street CTO: Shipping Review of the Four-Map Refinement

**Reviewer:** CTO, Jane Street. Adversarial, production lens.
**Under review:** four-map split (`ProductTerms[u]`, `UnitStatus[u]`, `WalletState[w]`, `PositionState[w,u]`), conservation discharged at the event handler.

I care about what the junior on-call sees at 3am when a reconciliation break arrives.

---

## 1. `PositionState`: Option vs Monotone

**Ruling: `Option<PositionState>`. Monotone-with-zero-row is a false economy.**

OCaml idiom: `(wallet_id * unit_id, position_state) Map.t` with `Map.find_opt` is the native shape. `Map.find` (raising) is avoided in Jane Street style for this exact reason — monotone recreates the raising-find footgun at the value level. Feynman's "never GC, always zero row" is not more total than `Option`; it *hides* the distinction that determines correctness.

Query-view shapes:

```ocaml
(* Option *)
val position : View.t -> wallet_id -> unit_id -> position_state option
val holders_of : View.t -> unit_id -> (wallet_id * position_state) Seq.t

(* Monotone-with-zero *)
val position : View.t -> wallet_id -> unit_id -> position_state   (* total *)
val holders_of : View.t -> unit_id -> (wallet_id * position_state) Seq.t
  (* ever-held? currently-open? Convention chosen. Callers forget. *)
```

Under monotone, `holders_of u` has a *chosen* semantics — ever-held vs currently-open — and both are load-bearing in different places (VM settlement wants ever-held-during-session; risk dashboard wants open). With `Option`, those are named indices. Foot-gun moves from explicit to implicit.

Audit question: "did wallet X ever hold Y?" The moves stream answers this authoritatively; state must **not** duplicate. That is exactly why monotone's "keep the zero row as a proof of history" is wrong: ops ends up with two answers to reconcile. Audit → event log. State → "what is true now." `Option` is the honest shape.

Operational-cost-of-bug. A missed `None` in `Option` is a compile error. A mistaken zero read under monotone is a silent $0 cost basis on a flat-but-previously-held position — a P1 that surfaces the first time a corporate action touches a ghost row.

---

## 2. Four-map vs three-map

**Ruling: Four maps. `ProductTerms[u]` is genuinely separate.**

Geohot's instinct — "static terms belong in the Unit record" — is right for listed and wrong as a universal rule. OTC contracts amend: ISDA amendments, novations, restructurings, coupon step-ups on credit events. Amendments mutate terms. "Terms" is *amend-only with audit trail*, a different discipline than `UnitStatus` (tick-by-tick). Two disciplines, two maps.

Why uniform four-map beats "three-map + terms-in-unit-record": one ledger serves both listed and OTC. If listed puts terms on the Unit record and OTC uses a versioned map, the core has two shapes and every generic query branches. Four maps — `ProductTerms` read-mostly, most products writing once at registration — gives one shape. Listed pays nothing extra (one write per unit, ever); OTC pays for the trail it actually needs.

Concretely: `ProductTerms[u] : Map[UnitId, NonEmptyList[TermsVersion]]`, current terms `.head`. Listed never appends after registration. OTC appends on `AmendmentEvent`, preserving "state = fold of events."

---

## 3. `WalletState` — does it earn its sector?

**It earns it, but not as currently typed. Make it sparse and overlay-keyed.**

Most wallets are trading books with no overlay. A universal `WalletState[w]` with `Option[HWM]`, `Option[Mandate]`, `Option[FeeAccrual]` is 90%-None rows.

Right type: sparse overlay map. A wallet has an entry iff at least one overlay contract is attached:

```python
@dataclass(frozen=True, slots=True)
class WalletOverlay:
    contracts: Mapping[ContractId, OverlayState]
    # OverlayState = ManagedAccount | CSAAgreement | SubscriptionLine | ...

wallet_state: Mapping[WalletId, WalletOverlay]  # absent = plain trading wallet
```

`view.wallet_overlay(w) -> WalletOverlay | None`; `None` = plain trading wallet (common case). Managed account = `Some({"mgmt_42": ManagedAccount(hwm=..., mandate=...)})`. Keeps the sector first-class (Karpathy is right: HWM has nowhere else to live) while paying only for wallets that use it. Keyed by `WalletId`, not `(wallet, contract)` — scattering a wallet's overlays across the keyspace makes "all overlays on w" a range scan.

---

## 4. Event-handler conservation: what enforces the contract?

Induction is sound. "Trust the author" is unshippable. Three enforcement layers:

```python
class EventHandler(Protocol[E]):
    def apply(self, view: View, event: E) -> StateDelta: ...

@dataclass(frozen=True, slots=True)
class StateDelta:
    unit_updates:     Mapping[UnitId, UnitStatusDelta]
    wallet_updates:   Mapping[WalletId, WalletOverlayDelta]
    position_updates: Mapping[tuple[WalletId, UnitId], PositionDelta]
    moves:            tuple[Move, ...]  # (unit, Mapping[WalletId, Decimal])
```

1. **Structural.** `Move.mk(u, mapping)` rejects at construction any mapping whose values do not sum to zero. `Move.mk(u, {w1: -d, w2: +d})` succeeds; `Move.mk(u, {w1: -d})` raises before the delta leaves the handler. This is the layer that catches the bug before storage.
2. **Runtime.** Before committing a `StateDelta`, the core re-verifies per-unit sum-zero. Cheap, unconditional, runs in production. Failure aborts the transaction.
3. **Property-test obligation.** A new `EventHandler` ships only with a generator test proving: for any generated event, `sum_w delta(w, u) == 0` per emitted unit. Bound on the *author*, checked in CI.

Layers 1+2 catch bugs; layer 3 documents intent. Trait-bound-only would be academic — you cannot encode an existentially quantified decimal sum in Python's type system.

---

## Ship / no-ship

**Ship. Minimum change to v10.3:**

1. Split §3 `UnitEntry.unit_state` into `ProductTerms[u]` (versioned, append-only) and `UnitStatus[u]` (mutable).
2. Add `WalletState[w]` as a **sparse overlay map**, not a dense per-wallet table.
3. `PositionState[w,u]` as `Option`, never default-zero. Delete any monotone-with-zero-row text.
4. Rewrite §7 around `Move.mk` structural zero-sum at construction + runtime recheck + property-test obligation.
5. Deprecate `view.get_unit_state(u)` as alias for `view.unit_status(u)` for one release; don't break.

Four ships. Three would be dishonest about OTC amendments.

— **Verdicts:** (i) `Option<PositionState>`. (ii) Four-map. (iii) **Ship.**
