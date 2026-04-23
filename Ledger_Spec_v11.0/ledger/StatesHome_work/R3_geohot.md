# R3 — GEOHOT: radical simplicity pass on the three-map proposal

*"The code you delete is the code that can never have bugs."*

The committee converged on three typed maps: `UnitState[u]`, `WalletState[w]`, `PositionState[w,u]`. Everyone cites Minsky's "illegal states unrepresentable" argument and Jane Street's "junior on-call at 3am" argument. Both are real. But the proposal is still carrying fat it inherited from CDM and from trying to please a reviewer who wanted category theory.

## Attack

**1. Is WalletState necessary, or is it `PositionState[w, u_self]` in disguise?**
Dirac proposed exactly this and FORMALIS destroyed it: a self-contract unit per wallet bloats `U` by `|W|`, and `w_self` has no counterparty for `Σ_w w(u) = 0`. So no — WalletState cannot collapse into PositionState without breaking conservation or creating sentinels. Keep it.

**2. Is UnitState necessary, or is it just the Unit Store?**
This is the unexamined bloat. Static product terms (`multiplier`, `expiry`, `strike`) are **immutable** — they live in the Unit Store at registration, set once, never mutated. Calling them "state" is a category error. The *mutable* per-unit state (`lifecycle_stage`, `last_settlement_price`, `paid_coupons`) is genuinely distinct but small. Jane Street caught this in passing (§"static vs mutable unit state"); nobody made it the headline. **Rename "UnitState" to `UnitStatus[u]` and scope it to mutable per-unit fields only.** Static terms belong to the Unit record, period.

**3. Line count.**
Three `Mapping[K, V]` fields on a `View` dataclass. That is fifteen lines including the product-specific ADTs. The machinery is already minimal. The cost is in the prose, not the code.

**4. Do scalar-only instruments (bond, equity, never traded) pay the three-map tax?**
No — empty maps are free. A bond in `UnitState`, no `WalletState`, no `PositionState` rows. This is the correct shape. Untraded listed unit sits in `UnitState` with zero `PositionState` rows. No bloat.

**5. Could one map `state: (w|None, u|None) → dict` work?**
Yes — and it is the stringly-typed universe-wallet idea reheated. You lose the thing that made Minsky win: *the type of the value depends on which axis you are on*. `PositionState` carries `accumulated_cost: Decimal`; `WalletState` carries `hwm: Decimal`; `UnitStatus` carries `lifecycle_stage: Enum`. One untyped `dict` discards the compile-time guarantee. Reject.

## Toy implementation (31 lines)

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

WalletId = str; UnitId = str

@dataclass(frozen=True, slots=True)
class Unit:                              # immutable product terms
    id: UnitId; kind: str; terms: dict   # multiplier, strike, expiry ...

@dataclass(frozen=True, slots=True)
class UnitStatus:                        # mutable per-unit
    lifecycle: str = "ACTIVE"
    last_settle: Decimal | None = None
    paid: frozenset[str] = frozenset()

@dataclass(frozen=True, slots=True)
class WalletStatus:                      # mutable per-wallet
    hwm: Decimal = Decimal(0)
    mandate: str | None = None

@dataclass(frozen=True, slots=True)
class PositionStatus:                    # mutable per-(w,u)
    accumulated_cost: Decimal = Decimal(0)

@dataclass(frozen=True, slots=True)
class View:
    units:     Mapping[UnitId, Unit]
    status_u:  Mapping[UnitId, UnitStatus]
    status_w:  Mapping[WalletId, WalletStatus]
    status_wu: Mapping[tuple[WalletId, UnitId], PositionStatus]
    # accessors: total, default-by-construction. Missing (w,u) => zero position.
```

Four cases check: futures lands in `status_wu`; managed account lands in `status_w`; QIS has rules in `Unit.terms`, mutable `current_weights` in `status_u`, futures in `status_wu`; untraded listed unit lives in `units` + `status_u` only.

## Verdict

**Keep three maps. But fold UnitState's immutable half back into the Unit record.**

The committee named three axes; correct. They accidentally smuggled in a fourth thing — static product terms — by calling them "state". Delete that framing. Product terms are not state. State is what mutates.

## The one simplification I insist on

Rename `UnitState` → `UnitStatus` and restrict it to *mutable* per-unit fields (`lifecycle`, `last_settle`, `paid_coupons`). Move static product terms (`multiplier`, `strike`, `expiry`, `currency`) out of any "state" map and into the `Unit` record where they always belonged. This kills the "is `multiplier` state?" confusion that §7 line 1034 currently invites, and makes the invariant clean: **state = what transitions on events; terms = what the smart contract was born with.**

One map per axis of mutation. Zero maps for immutability. That is the minimal set.
