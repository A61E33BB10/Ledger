# R3 — LATTNER: The Three-Map Proposal as a Decade-Scale API

*Library-first. Progressive disclosure. Modular. Infrastructure extended by people not yet hired.*

The converging R1+R2 proposal (UnitState[u], WalletState[w], PositionState[w,u], invariants discharged by event handlers) is the right substrate. My job: make the shipping shape survive a decade of instrument types nobody has pitched yet.

## 1. Evaluation on the six criteria

**1. Progressive disclosure.** The three-map split leaks into the newcomer's path. A developer implementing a corporate bond must not have to know `PositionState` exists. A `ProductSpec` declaring only `unit_state_type` still forces the reader to see `get_position_state` returning `()`. That fails "simple things are simple." Fix: the product-author-facing surface exposes **one** `ProductSpec` trait with opt-in slots; the three maps are the **implementation** surface used by the core, not the authoring surface.

**2. Library-over-compiler.** Dirac's `w_*` is compiler-magic — a reserved wallet the persistence layer must special-case. Reject. The Minsky/Finops three-map shape has no sentinels, no reserved ids, no caste system. Pass — provided we do not backslide on "universe wallet" or `u_∅` cleverness in implementation.

**3. Extensibility / ABI.** Tighten here. The three maps are generic over payload. Adding CO2 credits, tokenised securities, insurance-linked notes must extend the **sum of payload types**, not the three-map shape. Rules:
   - Payloads are associated types on `ProductSpec`, not a closed sum.
   - Callers iterate typed via `view.units_of(P) -> Iterator[(UnitId, P.UnitState)]`.
   - New instrument families ship as new modules implementing `ProductSpec`; no core change.
   - **ABI rule**: payload types are opaque across module boundaries. Callers use product-declared accessors, never structural destructuring. This is the LLVM opaque-pointer lesson — callers reaching into internal representations is a decade-long mistake.

**4. Diagnostics.** `get_position_state(w, u)` when `w` never held `u` must not silently return a zero. The error (when the caller expected an existing position) must say: `no PositionState at (w=…, u=…); wallet has never held this unit. Did you mean open_position, or positions_of(w)?` Precise source locations and actionable suggestions are core functionality, not polish.

**5. Modularity.** Can the core be built without `PositionState`? Yes, and it must. A ledger handling only cash + equities + bonds should run without `PositionState` loaded at all. Products that need per-pair state pay the tax; products that don't, don't. LLVM principle: `MachineFunctionPass` is not loaded if you don't target codegen. Concretely: the core exposes a state-shape trait; `PositionState` is gated by product declaration.

**6. Additive migration.** v10.3's `view.get_unit_state(unit)` single slot must not break. The additive path:
   - Keep `get_unit_state(u)` working, as deprecated alias for `view.unit_state(u)`.
   - Add `view.wallet_state(w)` and `view.position_state(w, u)` as new methods.
   - The two-arg form `view.get_unit_state(wallet, contract)` already on line 2287 remaps to `view.position_state` with a deprecation warning for one release.
   - Products with no per-pair state see zero change. Futures authors opt in by declaring `position_state_type`.

## 2. Shipping API signature

```python
# One product = one ProductSpec. Only UnitState is required.
class ProductSpec(Protocol):
    product_id: ClassVar[ProductId]
    UnitState:     type              # required
    WalletState:   type = type(None) # opt-in: managed account, CSA
    PositionState: type = type(None) # opt-in: futures, SBL

    @staticmethod
    def initial_unit_state(u: UnitId, terms: ProductTerms) -> UnitState: ...
    @staticmethod
    def on_event(view: View, event: Event) -> StateDelta: ...
        # returns typed deltas; handlers never write directly.

# Ledger view: three accessors. PositionState is an Option.
class View(Protocol):
    def unit_state(self, u: UnitId) -> ProductUnitState: ...
        # Total. Unknown unit -> LedgerError.UnknownUnit.

    def wallet_state(self, w: WalletId) -> WalletState | None: ...
        # None iff wallet has no wallet-scoped state declared.

    def position_state(self, w: WalletId, u: UnitId) -> PositionState | None: ...
        # None iff (w,u) has never been held. NOT a zero default.

    def positions_of(self, w: WalletId) -> Iterator[(UnitId, PositionState)]: ...
    def holders_of(self,   u: UnitId)   -> Iterator[(WalletId, PositionState)]: ...
        # Two secondary indices; production query shapes require both.

# Writes go through typed deltas. Core applies atomically; checks per-event sum-zero.
class StateDelta:
    unit_updates:     Mapping[UnitId, UnitStateDelta]
    wallet_updates:   Mapping[WalletId, WalletStateDelta]
    position_updates: Mapping[(WalletId, UnitId), PositionDelta]
    moves:            Sequence[Move]   # sum-zero per unit, structurally
```

## 3. `PositionState`: Option, not default-zero

**Ship `Option<PositionState>`.** Three extension-driven reasons:

   1. **"Never held" vs "held and flat" is semantically distinct and will stay so.** Formalis's counter-example — VM settlement must touch every wallet that held `u` during the session, including currently-flat ones — is real, and the distinction recurs for instrument families not yet built (post-expiry clawback, staking lookback, insurance reinstatement). A total zero-default cannot recover it.
   2. **Iteration contracts are a decade-scale concern.** With a total function, `{w : position_state(w,u) != zero}` drifts as products redefine zero. With `Option`, `{w : Some}` is stable — extension cannot silently change the iterator's contents.
   3. **Arithmetic zero is a product concern, not an API concern.** The product may still declare `PositionState.zero` for conservation checks and netting. That zero is used by handlers internally, not surfaced through the accessor. Separate the two: `Option` at the accessor, `zero` in the algebra.

This is the Swift `Optional` discipline: never conflate "absence" with "zero value." Conflating them creates bug classes that surface years later on the worst on-call shift.

## 4. Reject / defer

**Reject.**
   - **`w_*` universe wallet and `u_∅` self-contract (Dirac).** Reserved sentinels the persistence and ACL layers must special-case. P1 waiting to happen. Beauty in the equations, ugly in the exports.
   - **Sheaf factorisation-class as the type discipline (Grothendieck).** Unchecked metadata tags are not a type system.
   - **"Forbid state on the wallet" / managed-account as synthetic TRS (Rosetta §4).** Over-fits OTC to listed markets. Managed-account HWM is genuinely wallet-scoped.
   - **`WalletState` keyed by mandate-class (Minsky §5).** Premature quotient. Ship keyed by `WalletId`; introduce a mandate type when a second mandate class actually appears.

**Defer.**
   - **Capability-scoped `PositionState` access (Finops adversarial).** Important, but layer it over the three-map shape in v10.4.
   - **External-reconciliation-as-oracle framing (Finops test substrate).** Good test discipline, not a v10.3 API concern.

The three-map split is right. Ship it. Make `PositionState` optional. Keep the authoring surface single-accessor for the scalar case. Never invent a reserved wallet.

— *"Build infrastructure that becomes invisible through ubiquity."*
