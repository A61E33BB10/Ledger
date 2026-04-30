# Phase 2 — Data Team Synthesis (Jane Street CTO)

**Author posture.** I am the brake. The 19 Phase 1 enumerations between them
named hundreds of records, dozens of new "floors", at least one would-be
`MarketDataService`, two `UniversalSymbology` services, three independent
proposals to elevate the Pricing-DAG topology to a stored entity, and one
suggestion that we treat the CDM enum closure as a first-class data sector.
Most of those have to die before Phase 3.

The Phase 1 corpus did surface real signal. Almost every reviewer
independently arrived at the same five classes — append-only versioned
terms, mutable shared per-unit status, per-position state, an attested
external observation stream, and the immutable execution log. The user's
"~3 structural classes (Definitions / Observations / Effects) plus
additions" mapping is right. The job of this document is to keep us there
and to refuse the bloat.

I write this in three parts: the engineering principles the proposal must
obey; the anti-over-engineering veto list; and the simplest correct
architecture, plus a per-abstraction cost audit.

---

## 1. Engineering principles for the data layer

These are non-negotiable. Every record in the Phase 3 proposal must obey
all of them; if a record cannot, the record is wrong, not the principle.

### P1. Pure-functional ingest

Every transformation from external data to internal state is a pure
function of its captured inputs. `ingest(payload, snapshot_cursor) ->
record` is total, deterministic, and free of hidden reads. Side effects
live in the adapter ring at the very edge — the network call, the
signature verify, the disk write. The core is a fold. If a function
needs a clock, a counter, or a singleton, it takes them as arguments. No
ambient state. No "current snapshot" thread-local. The two principles
that follow are corollaries of this one, but they are easy to violate by
accident, so I state them anyway.

### P2. Append-only is the default; in-place mutation requires written justification

Every record is append-only unless the proposal explicitly argues that
its semantics demand mutation and that the resulting non-replayability
is bounded and acceptable. Of the 19 reviewers, 18 independently
declared that ProductTerms, the move stream, attestations, and
calibration history are append-only; the one outlier (an early geohot
draft) corrected itself in the same document. We adopt this without
debate. UnitStatus and PositionState are the two places mutation lives,
and both are reconstructible by fold of the move stream — they are
caches with strict invariants, not primary records.

### P3. Content-addressed identity wherever a deterministic derivation exists

`unit_id = hash(canonical(terms_blob))`. `tx_id = hash(prev_hash,
canonical(payload))`. `attest_id = hash(topic, value, t_obs, source)`.
Surrogate keys are forbidden where a content hash works. This is what
makes idempotent ingest free, replay deterministic, and tamper-evidence
structural rather than operational. Where a record genuinely has no
content (a wallet at onboarding) a UUID is acceptable, but it is the
exception.

### P4. Bitemporal where the world restates; single-axis everywhere else

The world axis (`valid_from`, `t_obs`) and the system axis (`system_time`,
`t_known`, `ingest_time`) are independent. Reference data and
attestations are bitemporal — vendors restate, exchanges add holidays
retroactively, GLEIF lapses LEIs. Move-stream events, ProductTerms
versions, and calibration runs are single-axis (their `valid_time` is
fixed at write time; corrections are new rows). Resist the temptation to
make everything bitemporal — it is the right tool only where the
upstream truly emits restatements.

### P5. Errors are values; failures are explicit; silence is forbidden

A missing reference record returns `Option[Record]`, never a default. A
calibration that fails the no-arbitrage gate returns
`Uncertified(reason)`, never silently substitutes the prior value. A
duplicate idempotency-key returns `AlreadyApplied(tx_id)`, never
re-fires. Every failure path is named in the type. The line in v10.3
about "wrong is far worse than missing" is the single most important
sentence in the spec; we will enforce it through types.

### P6. Snapshot pinning at every impure boundary

Any code that consumes attestations, calibrations, reference data, or
calendars consumes them through a snapshot cursor captured at the moment
the activity is dispatched. The cursor is a value (a tuple of
`(source_id, sequence_number)` or a content hash); it is recorded with
the resulting transaction; replay fetches by cursor, not by "latest".
This is what makes deterministic replay (P3 of v10.3 §11.5)
operationally true rather than aspirational.

### P7. Make illegal states unrepresentable at the type boundary

A `unit_type` is a closed enum, never a string. A `Currency` is a
refinement of ISO 4217. A `PositionState` is `Option[Some]`, where
`None` and `Some(zero)` are operationally distinct (addendum C1). A
`StateDelta`'s `position_state_row_diffs` carry a `field_writer_tag`
matching the C11 handler-uniqueness invariant — cross-handler writes are
a compile error, not a runtime check. The schema is the first line of
defence; we do not push to runtime what the type system can prove.

### P8. One canonical record; everything else is a derived view

The move stream is the canonical record. ProductTerms (the head),
UnitStatus, PositionState, wallet balances, valuation records,
obligations — all are folds. The proposal must name, for every
non-canonical record, the deterministic fold function that reconstructs
it. If there is no such function, the record is canonical and must be
treated as such (with all that entails: hash chain, WORM storage,
retention floor). If there is, the record is a cache — explicit
invalidation, recompute-on-loss, never "source of truth" semantics.
geohot's instinct here is correct and we adopt it as policy.

### P9. Closed enumerations everywhere a free string is tempting

`unit_type`, `transaction_class`, `event_class`, `metadata_tag`,
`lifecycle_stage`, `valuation_fsm_state`, `quality`, `wallet_type`,
`obligation_kind` — all closed. Adding a value is a deliberate schema
change that requires a property-test update. Free-text "metadata" maps
are the single worst pattern in production trading systems and we do
not import them. This includes "extension fields", "custom attributes",
"tags" — all forbidden.

### P10. Polymorphism by sum type, not by inheritance

`ProductTerms.terms` is a sum type tagged on `unit_type`. The
`PositionState` field map is product-polymorphic via the smart
contract's `FIELD_SPEC` (addendum C11). Greeks are
`Vector[Decimal]` discriminated by `model_id`, not `HestonGreeks <:
GreeksBase` with virtual methods. There is no `InstrumentMaster` base
class. There is no `Quote` interface with `EquityQuote`,
`FxQuote`, `OptionQuote` subclasses. Sum types let the compiler check
exhaustivity; class hierarchies bury polymorphism in vtables and
silently allow new subclasses to skip handlers.

---

## 2. Anti-over-engineering veto list

Each veto names: the over-engineering pattern; the Phase 1 source(s)
that proposed or invited it; the reason it must be deleted before
Phase 3.

### V1. The three-tier Unit Store presented as three storage entities

**Sources:** v10.3 §3.3 itself ("Tier 1 Reference Data / Tier 2 Product
Registry / Tier 3 Unit Registry"); reproduced approvingly by
GROTHENDIECK (A2/A3/A4), CARTAN (Cat 1a/1b/2.1), and TESTCOMMITTEE
(F2.1, F2.2). geohot called this out explicitly as "three indices over
the same data, with synchronisation cost that scales with squared
corner-case count". He is right. **Veto:** the Phase 3 proposal will
present Unit Store as exactly two maps — `ProductTerms[u]` (versioned
append-only) and a vendor-keyed `InstrumentMaster` (bitemporal,
external-authored). Tier 2 (Product Registry, smart-contract template
binding) is a single field on the unit's `ProductTerms`, not a map.
Tier 1 reference data is `InstrumentMaster`. There are not three tiers;
there are two records and a foreign key.

### V2. "Listed-instrument detail" as a top-level data category

**Sources:** the user's own floor; defended by NAZAROV, expanded by
ISDA. **Veto:** every reviewer who actually thought it through (cartan,
correctness, feynman, geohot, halmos, jane_street, karpathy, lattner,
matthias, minsky, testcommittee — eleven of nineteen) folded it into
ProductTerms variants or Reference. Phase 3 will not have a top-level
"Listed" category. The fields live in `ProductTerms.terms` tagged on
`unit_type`. Listed vs OTC is a sum-type variant, not a hierarchy
boundary.

### V3. The "universal symbology service"

**Sources:** GROTHENDIECK (A11+A13), MATTHIAS (Floor 8), several others
implicit. **Veto:** mapping ISIN/CUSIP/SEDOL/RIC/BBG/FIGI to a canonical
internal key is irreducibly messy and any abstraction that pretends
otherwise hides bugs in production. Store the vendor key the data
arrives with; reject what the firm cannot resolve at registration; let
the OMS adapter handle external translation. The trading core consumes
already-resolved `unit_id`s.

### V4. Per-vendor typed schemas in market-data storage

**Sources:** MATTHIAS (Floor 6 sub-types per CDM observable kind),
NAZAROV (3.1–3.8 separate quote schemas), FINOPS (Floor 6 broken into
six subcategories). **Veto:** geohot is right — store the raw payload
as bytes, index on `(topic, t_known)`, normalise lazily at consumption
in pure functions inside the calibration layer. Vendor-specific fields
do not enter the storage schema. One ingest path; one row format.

### V5. Per-model typed Greek schemas

**Sources:** MATTHIAS (separate Heston/SABR/BlackScholes blocks), CARTAN
(9c with model-discriminated tagged union but one row per model),
several others. **Veto:** Greeks are `Vector[Decimal]` plus a
`model_id`. The model code interprets the vector. The store does not.
The Vanishing Vega Principle in the valuation companion is exactly
about not letting the store schema impose a single geometry.

### V6. The Pricing DAG topology as a stored, versioned entity

**Sources:** CARTAN (Cat 9d), TEMPORAL (4b.2), partially LATTNER. The
DAG is a derivable view of `ProductTerms` ∪ `UnitStatus` rebuilt
per-cycle. **Veto:** do not store it. Materialise a per-cycle
in-memory snapshot; record only the cycle id on each `ValuationRecord`.
A versioned DAG schema is a database for something that costs
microseconds to recompute.

### V7. The "12-floor" / "14-category" / "19-category" inflation

**Sources:** FINOPS (12 floors), HALMOS (14), CARTAN (19). **Veto:**
the spec needs ~3 structural classes (Definitions, Observations,
Effects) plus a small number of cross-cutting additions. The reviewers
who used 14–19 categories were enumerating *fields* and *concerns*, not
*data classes*. Phase 3 collapses these back to 3 + 4 = 7 sectors at
most. Anything more is bookkeeping cosmetics.

### V8. CDM enum universe / "generator universe" as a data category

**Sources:** CORRECTNESS (Category 10), TESTCOMMITTEE (recurring).
**Veto:** these are *types*, pinned by `cdm_version` and `protocol_version`
fields on the system epoch record. They do not need their own data
sector. The pin is in code (or in a 4-line bootstrap config); the
property-test framework references it. Treating the closed enum
universe as data invites runtime mutation of types, which is exactly
what we are forbidding.

### V9. "Configuration / Policy" as a load-bearing first-class sector

**Sources:** my own Phase 1 §7.2; FEYNMAN; FINOPS. I withdraw the
broad version. **Veto:** the small set of policy values that must be
audit-trailable (PnL-explain tolerances, staleness factors, retry
budgets) live in a single bitemporal `PolicyConfig[id]` map with one
row format and one ingest path. They do not get a sector with
sub-categories per policy class. A "feature flags framework" is
forbidden.

### V10. A separate "settlement-layer" data sector

**Sources:** CORRECTNESS (Cat 7), CARTAN (Cat 14), FINOPS (Floor 11),
SBL (1.3, 1.8). **Veto:** `SettlementInstruction` is a deterministic
projection of the move stream, not a stored authoritative record.
Inbound confirmations are attestations of a particular kind. SSI
enrichment data is a bitemporal reference table no different in
discipline from a calendar. Three things, three homes already
covered. No new sector.

### V11. "Workflow / Orchestration State" as ledger data

**Sources:** CORRECTNESS (Category 9), TEMPORAL (Category 8). **Veto:**
Temporal workflow histories live in Temporal. They are operational
infrastructure, not framework data. Where the ledger needs them for
audit (workflow-id on a transaction), it stores a foreign key, not the
history. The dual audit trail of v10.3 §10.3 is two systems, not one
system with two data sectors.

### V12. Free-text `metadata`, `attributes`, `extensions` everywhere

**Sources:** several Phase 1 enumerations included `metadata: Json` or
"user-defined attributes" maps on `Move`, `Transaction`, `WalletRegistry`.
**Veto:** every such field is replaced by a closed enum and a typed
field set. If the framework needs a value, the schema names it. If it
does not, the value has no business in the trading core. This is not
optional.

### V13. A "Trade", "Position", "PnL", "Risk", or "Account" table

**Sources:** the natural assumption of every legacy-system reviewer;
geohot called it out by name. **Veto:** these are folds of the move
stream and do not get tables of their own. A trade is a transaction
class; a position is `apply(D7)` projected on `(w, u)`; PnL is
`V_t1 − V_t0`; risk is a query over PositionState and ValuationRecord;
an account is a wallet plus a settlement-layer mapping. Each
materialisation is a cache, never a source of truth.

### V14. Per-regulator obligation kinds

**Sources:** ISDA (10.1–10.3 by jurisdiction), MATTHIAS (8.x by regime),
SBL (per-regulation buckets). **Veto:** the `obligation_kind` enum
reflects what discharge requires (margin call, recall return,
settlement fail), not which regulator cares. Regulatory taxonomy is
a projection on top, not a partitioning of the obligation store.

---

## 3. Simplest correct architecture (≤300 words)

Three structural classes plus four cross-cutting sectors. Seven sectors
total.

**Definitions** (append-only versioned, content-addressed):
- `ProductTerms[u] : NonEmpty[TermsVersion]` — what unit `u` *is*.
  `terms` is a sum type tagged on `unit_type`. Listed-instrument fields
  are the `LISTED_*` variants. C5/C6/C7/C8/C10 from the addendum apply.

**Observations** (append-only event streams, snapshot-pinned for replay):
- `Attestation` — every external claim entering the system: ticks,
  fixings, settlement prices, corporate-action declarations, custodian
  statements. One stream, one row format, signature optional and
  required only where deterministic-lifecycle decisions depend on it.
- `Calibration[curve_id, t]` — Kalman posterior. Pure function of an
  attestation cursor and a model.

**Effects** (the canonical record, append-only, hash-chained):
- `MoveStream` — `Transaction`s, each a list of `Move`s plus a closed
  `transaction_class` and a CDM payload reference. Conservation
  enforced at commit (C2/C3). This is the only sector for which loss
  is unrecoverable from anything else inside the system.

**Cross-cutting** (small, sharply scoped):
- `UnitStatus[u]` — shared mutable per-unit state. Cache; reconstructible
  by fold of MoveStream. C5 keeps it total.
- `PositionState[(w,u)]` — per-position mutable state. Cache; monotone
  carrier with `Option` accessor (C1); C11 names the unique writer per
  field.
- `WalletRegistry[w]` — non-economic sidecar (KYC, capabilities, audit
  cursor). Mutable but rarely; no balances; bitemporal.
- `Reference` — a single bitemporal table family for vendor-authored
  external truth: `InstrumentMaster`, `Calendar`, `Party (LEI)`,
  `PolicyConfig`. Same discipline, four leaf schemas, one ingest path
  per leaf.

**What earns its place.** Definitions / Observations / Effects are
forced by C2, C6, P3 of v10.3 §11.5, and the Kalman discipline of the
valuation companion. UnitStatus and PositionState are forced by the
addendum's three-map ruling. WalletRegistry is forced by C4 and KYC
boundary. Reference is forced by external-authority bitemporality.

**What would be over-engineering.** A Pricing-DAG entity, a Settlement
sector, a Workflow sector, an Identity-and-Provenance sector, a
"Lifecycle Schedule" materialised view, an Obligation sector with its
own taxonomy. Obligations live as a typed sub-stream inside MoveStream
events with the same conservation discipline; due-event scheduling is a
projection of `ProductTerms` onto a calendar — a function call, not a
table. ValuationRecord is a sub-stream of Effects (an append-only
record per `(unit, t, model)`), not its own sector.

**Sector count.** Three structural classes + four cross-cutting = 7. If
the proposal returns to me at 10, 12, or 14, it is wrong.

---

## 4. Cost-per-abstraction audit

Cost score is qualitative: schema/code surface, ongoing operational
burden, failure-mode opacity, drift risk against the spec. Verdict is
**KEEP** (earns its place today), **CUT** (over-engineering, delete),
**DEFER** (interesting, no concrete claim today, revisit when one
appears).

| # | Abstraction | Cost | Verdict | Justification |
|---|---|---|---|---|
| A1 | `ProductTerms[u]` versioned append-only | Medium | **KEEP** | Forced by C6/C8 fungibility discipline. Without versioning, terms-amendment replay collapses. |
| A2 | `UnitStatus[u]` shared mutable map | Low–Medium | **KEEP** | Forced by addendum three-map ruling and C5 registration-totality. Cache, not source. |
| A3 | `PositionState[(w,u)]` monotone carrier with `Option` accessor | Medium | **KEEP** | Forced by C1 (None ≠ Some(zero)) and C11 single-writer. Cannot collapse to per-`u` or per-`w` (Karpathy substitution). |
| A4 | `WalletRegistry[w]` non-economic sidecar | Low | **KEEP** | Forced by C4 capability-scoping and KYC gating. Tiny schema, three or four fields. |
| A5 | `MoveStream` hash-chained append-only log | Medium | **KEEP** | Canonical record. Every other map is a fold. The single highest-value 120 LoC in the framework. |
| A6 | `Attestation` single stream for all external observations | Low | **KEEP** | Replaces five would-be sectors (market raw, oracle, fixings, corporate-action, settlement-confirmation). One ingest path. Signature optional, required only on deterministic-lifecycle inputs. |
| A7 | `Calibration[curve_id, t]` Kalman posterior store | Medium | **KEEP** | Forced by valuation companion §6. Reproducibility requires the inputs cursor, which is the only thing that makes calibration a pure function. |
| A8 | `ValuationRecord[(unit, t, model)]` | Medium | **KEEP** | Append-only stream, content-addressed by `(u, t, model)`. Caching policy is aggressive: keep last-FIRM hot, archive the rest, recompute from D6+D7. Storage is a perf optimisation, not a correctness requirement. |
| A9 | Three-tier Unit Store with separate Tier-1/Tier-2/Tier-3 storage | High | **CUT** | V1. Two records and a foreign key, not three indices. |
| A10 | "Listed-instrument detail" top-level sector | High | **CUT** | V2. Sum-type variant of `ProductTerms.terms`. |
| A11 | Universal symbology service | High | **CUT** | V3. Adapter problem, not core data. |
| A12 | Per-vendor market-data schema | Very High | **CUT** | V4. Bytes + topic index; normalise in pure functions. |
| A13 | Per-model Greek schema hierarchy | Medium | **CUT** | V5. `Vector[Decimal]` + `model_id`. |
| A14 | Pricing-DAG topology as stored entity | Medium | **CUT** | V6. Per-cycle in-memory snapshot. |
| A15 | "Configuration / Policy" sector | Medium | **CUT** (broad form) / **KEEP** (narrow `PolicyConfig` table) | V9. Single bitemporal table inside Reference, not a sector. |
| A16 | Settlement-instruction sector | High | **CUT** | V10. Projection of MoveStream, not a stored authoritative record. |
| A17 | Workflow-history sector | High | **CUT** | V11. Lives in Temporal, not in the ledger data layer. |
| A18 | `Obligation` first-class store | Low–Medium | **KEEP** (as sub-stream) / **CUT** (as separate sector with per-regulator taxonomy) | Forced by v10.3 §14.7 liveness. Lives as a typed sub-stream of MoveStream events, not a parallel sector with its own schema layers. |
| A19 | `IdempotencyLog` keyed dedup store | Low | **KEEP** | Forced by Invariant 5. Single KV store with conditional-put. One log per key namespace, never a "generic deduplication service" (V11-adjacent). |
| A20 | Bitemporal `Reference` family (Instrument, Calendar, Party, PolicyConfig) | Medium | **KEEP** | One discipline, four leaf schemas. Earns its place as the boundary against external authority restatement. |
| A21 | "Identity & Provenance" sector | Medium | **DEFER** | The substantive content (UTI, USI, hash chain, EndToEndId) lives on existing records as fields. No concrete claim today demands a separate sector. Revisit if a regulator forces a parallel registry. |
| A22 | "Reconciliation / external-attestation" sector | Medium | **DEFER** | CARTAN's Cat 12 is real, but the schema is just `Attestation` with `attestation_kind=SETTLEMENT_CONFIRMATION`. If volume + retention turn out to demand a partition, partition then. Not now. |
| A23 | "Generator / type universe" sector (CDM enums) | Low–Medium | **CUT** | V8. Pinned in code via `cdm_version` on the system epoch. |
| A24 | "Audit / lineage / sidecar" sector | Medium | **DEFER** | What CARTAN's Cat 19 wants is already on every record (`created_by_tx`, signatures, hash chain). Adding a separate sector duplicates that. If regulators demand a notary projection, build that projection then. |

**Audit summary.** Eight kept (the core), eight cut hard, four
deferred until a concrete claim appears. The proposal that arrives in
Phase 3 must justify any sector outside this list against the same
test: what concrete claim already in the corpus does it discharge?

---

## 5. Closing position

The 19 Phase 1 enumerations are healthier than I expected. Every
reviewer landed on the same load-bearing structure (the three maps, the
move stream, the attestation stream, the calibration posterior); the
disagreements are at the cosmetic boundary. The risk for Phase 3 is not
that we will miss a category — it is that we will keep ten when seven
suffice.

The brake stays on. If MINSKY proposes a 5-layer parser hierarchy, no.
If MATTHIAS proposes a CDM-native runtime registry, no. If TEMPORAL
proposes 50 workflow types as data, no. The smallest set of records
that discharges every named claim in v10.3 + addendum + valuation is
what ships. Everything else is over-engineering and we delete it before
it ships, not after.
