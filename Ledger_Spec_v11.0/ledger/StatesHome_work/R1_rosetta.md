# R1 — Where does unit state live? A CDM-aligned proposal

*Matthias Vogt, FINOS CDM core — review of `ledger_v10.3.tex` §3, §7, §10.*

## 1. The question, rephrased in CDM terms

The doc asks whether `state_t(u)` belongs on the wallet, on the unit, or on the `(wallet, unit)` pair. In CDM, that question does not exist in this shape — **CDM has no global wallet object, and state only ever lives on a `TradeState`**. The right translation:

| Ledger concept | CDM counterpart |
|---|---|
| Wallet | *no first-class type*; closest is `Account` / `Party`, neither carries economic state |
| Unit (listed) | `NonTransferableProduct` / `TransferableProduct` — product identity independent of any trade |
| Unit (OTC) | `NonTransferableProduct` wrapped by `Trade` — identity exists only once a `Trade` is formed |
| `(wallet, unit)` position | `Trade` + its evolving `TradeState` — per-counterparty, per-contract by construction |
| Unit state dict | fields on `TradeState` (`state`, `resetHistory`, `transferHistory`, `observationHistory`) |

The key observation: in CDM, the object whose state evolves is the `Trade`, and a `Trade` is intrinsically per-(counterparty-pair, contract). It is already a `(wallet, unit)`-shaped object. There is no CDM layer below it that carries mutable economic state, and no layer above it that aggregates across counterparties.

## 2. Precise CDM mapping per state category

**Per-unit (shared contractual) state.** Terms invariant across holders — multiplier, currency, expiry, strike, coupon schedule. These live in `EconomicTerms` on `NonTransferableProduct`, declared with `[metadata key]` so many `Trade`s reference the same product by key. Static after registration: changing it means a new product, not a state transition.

**Per-(wallet, unit) state.** Anything reflecting what has happened to this specific holder's position — fixings consumed, coupons already paid *to this holder*, resets applied, quantity after a partial unwind, accumulated cost on a futures book. These live on `TradeState`:
- `resetHistory Reset (0..*)` — realised floating-rate resets, variance accumulations
- `transferHistory TransferState (0..*)` — cashflows paid/received under this trade
- `observationHistory ObservationEvent (0..*)` — fixings recorded for this trade
- `trade.tradableProduct.tradeLot[*].priceQuantity` — mutated by `QuantityChangeInstruction`

`TradeState` is always per-`Trade`. CDM has no concept of "per-wallet state of a product independent of a trade".

## 3. "State on the wallet" — not expressible in CDM

CDM has `Party`, `Account`, and `PartyRole`. None carry economic state that evolves under a `BusinessEvent`. `Account` is reference data (identifier, type, servicing party); it does not hold a position, cost basis, or PnL baseline. The industry practice CDM encodes is: **state lives on trades; wallet-level quantities are a projection obtained by aggregating trades that reference a given party/account pair**.

So the doc's "state on the wallet" option is, strictly, not CDM-expressible. Any wallet-level state in the ledger (e.g. the CSA margin contract in §6.4) is either (a) an aggregation derivable from a set of `Trade`s and their `CollateralProvisions`, or (b) a ledger-specific extension sitting *alongside* CDM, not inside it.

## 4. The four test cases

### 4.1 Future with `accumulated_cost`

No CDM field named `accumulatedCost` exists. Nearest neighbours:

- **`TradeState.transferHistory`** — the full list of variation-margin cashflows. `accumulated_cost` is derivable as an algebraic reduction of `transferHistory` against `net_qty × price × mult`.
- **`tradeLot.priceQuantity`** — for a multi-fill position, `tradeLot (1..*)` with one entry per fill; a volume-weighted entry is derivable.

Layer mapping: `accumulated_cost` belongs on **`TradeState`**, not on the product template, not on static `Trade` fields, not on any wallet. It is per-`Trade`, which in this domain is *exactly* per-(clearing-member-account, contract, CCP). The doc's "per (wallet, unit) pair" is *the* CDM-aligned granularity for this field.

**CDM gap.** CDM 6.0.0 has no first-class listed-futures VM accumulator. `transferHistory` records cashflows but does not project them into an economic-value identity. The doc's `accumulated_cost` is a sound, lossless projection; keep it ledger-side as a derived field with an explicit reduction function over `transferHistory`.

### 4.2 Managed account

CDM has no `ManagedAccount` type. The ledger-side claim (§6) that every wallet is a managed account has, as closest CDM analogue, a **Total Return Swap** between the reference portfolio's owner and the Ultimate Beneficiary:

- `NonTransferableProduct.economicTerms.payout` contains a `PerformancePayout` whose `returnTerms` observes the reference wallet's value.
- The reference portfolio remains a set of distinct `Trade`s with their own `TradeState`s.
- The managed-account "state" (Perf baseline, last reset date) is the `resetHistory` of *the TRS trade*, not state on any wallet.

The wallet's "managed-account state" is not on the wallet — it is on the `TradeState` of a synthetic TRS. §6.7 already says this. That is the CDM-aligned home.

### 4.3 QIS strategy trading futures

A QIS strategy is expressed in CDM as either a **`PerformancePayout`** (strategy is the underlier of a swap/note) or as a **book of individual `Trade`s** (the futures legs) with a managing smart contract on top. Strategy-level state — `last_rebalance_date`, `current_weights`, `triggered_barrier` — lives on:

- if the QIS is an underlying of a structured product: `PerformancePayout.returnTerms` + `TradeState.observationHistory` of the wrapping trade.
- if the QIS is internal strategy bookkeeping: **outside CDM**, on a ledger-specific strategy-state record. CDM does not model portfolio-level strategy state as a first-class object.

Qualification: a strategy-note wrapper qualifies via `Qualify_EquitySwap_PriceReturnBasicPerformance_*`; a raw book of futures does not qualify as a single CDM product at all.

### 4.4 Instrument registered but not yet traded

The cleanest case. For a listed option in the security master before any position is opened:

- A **`NonTransferableProduct`** (contract specification) exists: `economicTerms`, `productIdentifier`, `productTaxonomy`.
- No `Trade`, no `TradableProduct`, no `TradeState` exists.
- No CDM `BusinessEvent` applies yet. The lifecycle state machine is empty until the first execution.

Consequence: the Unit Store's Tier 1/2 entry exists, but `unit_state` should be **empty / N/A**, not `ACTIVE`. `ACTIVE` is a property of a position, not of a contract specification. Confusing "listed on exchange" with "ACTIVE in the lifecycle sense" is the classic over-reach. The doc's Unit Store (§3, line 408) puts `unit_state: ProductSpecificState` on the unit entry — for listed units this is a category error unless interpreted strictly as static template terms.

## 5. Which `BusinessEvent`s change which state

| CDM `PrimitiveInstruction` | Changes template? | Changes per-`TradeState`? |
|---|---|---|
| `ContractFormationInstruction` | no | **yes** — creates a new `TradeState` |
| `ExecutionInstruction` | no | **yes** — tradeLot, priceQuantity |
| `QuantityChangeInstruction` | no | **yes** — priceQuantity, transferHistory |
| `TerminationInstruction` | no | **yes** — state → terminated |
| `ExerciseInstruction` | no | **yes** — transferHistory + state |
| `TransferInstruction` | no | **yes** — transferHistory |
| `ObservationInstruction` | no | **yes** — observationHistory |
| `IndexTransitionInstruction` | **yes (rare)** — benchmark replacement | also yes on every affected `TradeState` |

Per-unit (template) state only mutates under `IndexTransitionInstruction` and genuine product amendments. Everything else is per-`TradeState`.

## 6. Recommendation

**Attach state to the `(wallet, unit)` pair by default, reserve per-unit state strictly for immutable contractual terms, and forbid "state on the wallet" as a modelling option.**

1. `TradeState` is the only CDM object that mutates under `BusinessEvent`s, and it is structurally per-`Trade`, i.e. per-(counterparty-pair, contract) — exactly the ledger's `(wallet, unit)`.
2. Per-unit mutable state is a false economy: the only CDM event that legitimately mutates a shared product template is `IndexTransitionInstruction`, which is rare and version-scoped. Everything else the doc currently lists as per-unit state (bond coupon-paid flags, equity last-dividend-date, QIS rebalance date) is actually *per-position*: two holders of the same bond can disagree on whether "their" coupon has been paid if one transferred cum-dividend.
3. "State on wallet" is not expressible in CDM and would force the ledger to invent a layer CDM does not have. The doc's CSA and managed-account "wallet-level smart contracts" are correctly modelled as *aggregations* over per-`Trade` state, not as native wallet state.

**Concrete edits implied:**

- **§7, line 1034.** Invert the default: "Unit state is per-(wallet, unit). For terms invariant across holders (multiplier, currency, expiry, coupon schedule), static terms live on the product template and do not participate in the state machine." Per-wallet should be the rule, not the futures exception.
- **§3, line 408.** Split `unit_state` on `UnitEntry`: `product_template_terms` (static, `EconomicTerms`-aligned) stays on the Unit Store; `position_state` (mutable, `TradeState`-aligned) moves to a separate `(wallet, unit) → PositionState` map. This avoids the "listed option not yet traded has an `ACTIVE` state" category error.
- **§7 state examples.** Re-home every example: bond coupon-paid flags → per-(wallet,unit); equity last-dividend-date → per-(wallet,unit); QIS last-rebalance-date → per-(wallet,unit) if it's a position, per-template only if it's a true contract-wide parameter (e.g. a protocol-level rebalancing calendar).
- **§7 CDM mapping table.** Add a column stating, for each transition, whether it touches the template (rare, index transitions only) or the `TradeState` (everything else).

This is the minimal change that makes the ledger's state model a faithful projection of CDM, rather than an idiosyncratic superset.
