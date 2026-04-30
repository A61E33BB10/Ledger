# Phase 1 Data Enumeration — Lattner Lens

**Author:** Chris Lattner persona
**Scope:** Ledger v10.3 main spec + StatesHome addendum + Valuation v1.0
**Discipline applied:** system architecture, progressive disclosure, library-over-language, modularity, decade-scale design.

---

## 0. Reading of the floor categories before enumerating

The brief proposes six floor categories: Static, Reference, Market, Oracle, Smart-contract execution, Listed-instrument detail. From the perspective of "what data does this framework actually carry, and what does the API to it look like in 10 years," I disagree with the floor in three concrete ways. I will state the disagreement here and then enumerate the categories I actually believe are load-bearing.

### Disagreements with the proposed floor

1. **"Listed-instrument detail" is not a peer of the others — it is a sub-genre of Reference Data.** Listed-instrument contract specs (exchange, lot size, multiplier, expiry calendar, tick size) are reference data, fed by the same channels (exchanges, vendors, CSDs), with the same temporal semantics (slow-changing, point-in-time correct). Promoting it to a top-level category creates a privileged path that OTC instruments cannot use. That is exactly the "magic users can't replicate" red flag. Listed-instrument detail belongs as a typed sub-schema inside Reference Data with the same registration discipline. Compare: in LLVM we did not give "x86" its own category alongside "Target" — x86 is a `Target` subclass. The framework that survives is the one that puts listed and OTC reference data behind the same interface; the differences live in the leaf schemas, not in the top-level taxonomy.

2. **"Static" and "Reference" are bleeding into each other.** "Static" data (ProductTerms, immutable contract terms, ISO codes, day-count conventions, calendars) is a *property* (immutability + versioned append-only) of a class of reference data, not a peer of reference data. The StatesHome addendum already drew exactly this distinction inside the unit store: ProductTerms is append-only and versioned; UnitStatus is mutable and shared; PositionState is per-(w,u) economic state. The data taxonomy at the framework boundary should mirror that: separate **Reference** (what exists in the world) from **Convention** (how the world is described — calendars, day-count, business-day rules, holiday tables) from **ProductTerms** (the inside-the-system, versioned, append-only crystallisation of reference + convention into a unit). Calling all three "Static" hides the divergent versioning models.

3. **"Smart-contract execution" is a process, not a data category.** Smart contracts are pure functions; they don't *own* a data category — they *consume* market data, reference data, and unit state, and they *emit* moves and state-deltas. Treating "smart-contract execution" as a peer of Market and Reference data conflates the function with its IO. The actual data category that exists here is **Lifecycle Event Records** (the BusinessEvent payloads, the StateDelta artifacts, the executor commit records) — and that is a distinct first-class category that the original floor missed entirely. I will list it as such.

### Categories I actually carry forward

After applying the corrections above, the data categories the framework requires, in dependency order, are:

| # | Category | What it answers |
|---|---|---|
| 1 | Convention Data | "What rules describe the world?" (ISO codes, calendars, day-count, BDA rules, currency tables) |
| 2 | Reference Data | "What instruments and entities exist in the world?" (Tier 1 of Unit Store, LEI/BIC, ISIN, contract specs — listed *and* OTC sit here) |
| 3 | ProductTerms (Static-immutable, versioned) | "What is the inside-the-system, versioned crystallisation of a unit's contract?" (StatesHome map 1) |
| 4 | UnitStatus (Status, mutable, shared) | "What is the current shared lifecycle/observable status of this unit?" (StatesHome map 2) |
| 5 | PositionState (per (w, u)) | "What is each holder's per-position economic state?" (StatesHome map 3) |
| 6 | Wallet Balances (the move-stream projection) | "How much of each unit does each wallet hold *now*?" |
| 7 | Move Stream (Event Log) | "What economic moves have ever happened?" (canonical internal record) |
| 8 | Lifecycle Event Records (CDM BusinessEvent payloads + StateDelta artifacts) | "Why did each move happen, in CDM-native terms?" |
| 9 | Market Data — Raw Observables | "What did the market quote, and when?" |
| 10 | Market Data — Calibrated (Kalman filter posteriors, certified curves/surfaces) | "What is the no-arbitrage best estimate of the latent market state?" |
| 11 | Valuation Records | "What is each unit worth, under which model, with which Greeks, at which quality?" |
| 12 | Oracle Attestations | "What did external authority X assert at time T, and how do we trust it?" (signed wrapper over 1, 2, 9 from outside) |
| 13 | Settlement Instructions & Confirmations | "What was instructed externally and what came back?" (sese.023/025, pacs.008, camt.054) |
| 14 | External Account / SSI Data | "Where in the real world does a wallet map to?" (BIC, IBAN, custodian account, CSD participant ID, SSI) |
| 15 | Workflow / Orchestration State | "What lifecycle / settlement / saga workflows are in flight?" (Temporal histories) |
| 16 | Wallet Registry (KYC, permissions, capability scopes) | "Who is allowed to do what to which wallet?" (StatesHome non-state sidecar) |

Sixteen categories, against the floor's six. The floor's "Static" splits 3-ways (Convention / Reference / ProductTerms); "Listed-instrument detail" folds into Reference; "Smart-contract execution" disappears as a category and is replaced by **Lifecycle Event Records** (the data side) plus **Workflow State** (the orchestration side); and three categories the floor missed entirely are added: **Wallet Balances** (the projection), **Move Stream** (the canonical log), and **External Account / SSI Data** (the boundary).

The mandate also asked for floor coverage as 1.Static / 2.Ref / 3.Market / 4.Oracle / 5.SC-exec / 6.Listed:
- **Static** → covered by #1 Convention + #3 ProductTerms (with strictly different versioning models, made explicit).
- **Reference** → covered by #2 Reference Data, with **#6 Listed-instrument detail merged in** as a leaf schema (not a peer).
- **Market** → covered by #9 Raw Observables + **#10 Calibrated Market Data** (split because they have different temporal semantics, different versioning, different consumers).
- **Oracle** → covered by #12 Oracle Attestations, but reframed as a *wrapper protocol* over (Reference, Convention, Market), not a peer data class.
- **Smart-contract execution** → split into #8 Lifecycle Event Records (data) and #15 Workflow State (orchestration), because they live in different audit trails (the dual audit trail of v10.3 §10.3 is exactly this distinction).
- **Listed-instrument detail** → merged into #2 Reference Data.

The additions (Wallet Balances, Move Stream, Lifecycle Event Records, External Account/SSI, Workflow State, Wallet Registry, UnitStatus, PositionState, ProductTerms split out from raw Reference, Calibrated Market Data split from Raw Market) are all forced by reading the three documents end-to-end: the spec already carries every one of these as a distinct concern with distinct API and distinct versioning. The floor under-counts them because it groups by domain ("Market") rather than by *temporal/versioning discipline*, which is the axis that actually matters for a 10-year design.

---

## 1. Convention Data

1. **Canonical name:** `Convention` (sub-types: `Calendar`, `DayCountFraction`, `BusinessDayAdjustment`, `RoundingRule`, `CurrencyMetadata`, `ISOCodeTable`).
2. **Definition:** The rules of the language in which financial contracts are described. Holiday calendars, day-count conventions (ACT/360, 30/360, ACT/ACT), business-day adjustment rules (Following, ModifiedFollowing, Preceding), rounding rules (banker's), ISO 4217 currency table, ISO 17442 LEI format spec, ISO 20022 message schemas.
3. **Minimum field set:** `convention_id`, `convention_kind` (enum), `effective_from` date, `effective_to` date or `None`, `definition_payload` (kind-specific schema), `source` (e.g., "ISDA 2006", "ISO 4217:2024"), `source_version`.
4. **Identity:** `(convention_kind, convention_id, effective_from)` triple. A calendar is `("calendar", "USD-NewYork", 2026-01-01)`. Identity is *not* the natural-language name alone — calendars are amended (a new bank holiday is added), and the amendment must produce a new identity instance, not silently mutate.
5. **Provenance:** External standards body (ISDA, ISO, exchange) → vendor feed (Reuters, Bloomberg, ICMA) → ingestion adapter → Convention Registry. Each ingestion is signed with source attribution and ingestion timestamp.
6. **Temporal semantics:** Bi-temporal. `effective_from / effective_to` on the world axis (when does this convention apply), plus an ingestion timestamp on the system axis (when did we know about it). A holiday added to next year's calendar three months in advance must be queryable by both axes — "the calendar as of today" and "the calendar as known six months ago".
7. **Failure consequences:** Wrong day-count → wrong coupon accrual → wrong cashflow → P5 lifecycle value invariance violated. Wrong calendar → coupon fires on the wrong date → liveness violation cascading into late-payment regulatory breach. **Severity: high.** Conventions silently parameterise everything downstream; they are the bedrock and a bug here propagates to every product family.

**(a) Extension story:** New convention kinds enter through a registered `ConventionKind` enum + a kind-specific schema. Adding a new day-count fraction is purely additive: register the kind, supply the schema, supply the calculator function. No core code changes. New regional calendars are pure data — they don't even require code. The framework's conventions registry is itself a unit-store-like three-tier object: kind catalogue (Tier 1), schema registry (Tier 2), instance registry (Tier 3).

**(b) Versioning model:** Append-only, versioned, immutable. Mirror of `ProductTerms` discipline (C6 of StatesHome): `NonEmptyList[ConventionVersion]`. A calendar amendment appends; it never mutates. This is the *only* correct model — anything else makes time-travel to "the calendar as we knew it on date X" unreliable, which breaks the "what we knew at time t" leg of v10.3's time-travel principle.

**(c) Progressive disclosure:** Simple case (90% of users): a smart contract calls `dcf("ACT/360", t1, t2)` and gets a number. Complex case: a fixed-income desk needs a custom day-count for an emerging-market sovereign with quirky conventions — they register a new `DayCountFraction` instance with their own calculator, no core changes. Expert case: backtesting a historical trade against the calendar as it was known on the trade date (correcting for a holiday added retroactively) — they query `convention_at(kind, id, world_time, system_time)`.

**Decade-load-bearing decision:** Make conventions *first-class data*, not hardcoded. ISDA reissues SIMM annually. SOFR replaced LIBOR. ESMA periodically amends T2S settlement calendars. Every one of these is a convention change; if conventions are baked into code, every change is a release. Bake them into data and a release is a `convention_registry.append()` call.

---

## 2. Reference Data

1. **Canonical name:** `ReferenceData` (Tier 1 of v10.3 Unit Store §3.3.1). Sub-schemas: `SecurityRef`, `ContractSpecRef` (listed derivatives — formerly the floor's "Listed-instrument detail"), `LegalEntityRef` (LEI), `AccountRef` (BIC/IBAN), `IndexRef`, `IssuerRef`.
2. **Definition:** The catalogue of *what exists in the external world*: instruments (ISIN, CUSIP, contract spec), legal entities (LEI), accounts (BIC/IBAN), indices, issuers, exchanges, CCPs, CSDs. Drawn from external authorities; the ledger consumes but does not author.
3. **Minimum field set:** `ref_id` (the external natural key), `ref_kind` enum, `ref_payload` (kind-specific schema), `source_authority` (e.g., "GLEIF", "ANNA-ISIN", "CME"), `as_of` date, `valid_from`, `valid_to`, `ingest_ts`.
4. **Identity:** `(ref_kind, ref_id)`. ISIN identifies a security; LEI identifies a legal entity; (exchange MIC, contract spec) identifies a listed derivative. Reference data identity is the *natural* key from the issuing authority, never a synthetic one — this is the only way reconciliation against external statements works.
5. **Provenance:** External authorities (GLEIF for LEI, ANNA for ISIN, exchange contract listings, vendor feeds: Refinitiv, Bloomberg, S&P) → ingestion adapter → reference registry. Each record carries `source_authority` and `ingest_ts`; conflicting sources are surfaced, never silently merged.
6. **Temporal semantics:** Bi-temporal again. World axis: `valid_from / valid_to` (an ISIN is issued on a date, possibly retired). System axis: `ingest_ts` (when did we learn about it). Vendor restatements are first-class: the record is versioned, never overwritten.
7. **Failure consequences:** Wrong contract spec → wrong multiplier → wrong notional → conservation still holds (because moves balance) but value is wrong. Wrong LEI → reporting goes to the wrong counterparty under EMIR/SFTR → regulatory breach. Stale ISIN → corporate-action processing fires against a retired security → orphan moves. **Severity: high to medium** depending on sub-schema.

**(a) Extension story:** A new instrument family is added by registering a new `ref_kind` and its leaf schema. Adding tokenized equities (v10.3 §9.x) means registering `ref_kind = "TokenizedSecurity"` with fields `(contract_address, chain_id, underlying_isin)`. No changes to the rest of the system. **Listed-instrument detail enters here as the `ContractSpecRef` leaf schema, not as a top-level category.** Same registration channel, same versioning, same tooling.

**(b) Versioning model:** Append-only, bi-temporal. A vendor restatement (the official ISIN issuance date is corrected by ANNA two months after the fact) appends a new version with new `ingest_ts` but the same `ref_id`. Time-travel queries pick the version current at the requested system time. Critically: reference data is *consumed*, not authored — the ledger is not the source of truth, GLEIF is. Versioning preserves what we believed, when.

**(c) Progressive disclosure:** Simple case: `ref.lookup("ISIN", "US0378331005")` returns the latest known record. Complex case: a tokenized security with both an underlying ISIN and a token contract address — the leaf schema carries both, and the higher-level "what is this thing" query follows the schema. Expert case: an audit at year-end needs the LEI registry as it was known on 2025-12-31; they query with both world and system time.

**Decade-load-bearing decision:** Sub-schemas must be a *registered, versioned, declarative type*, not hard-coded variants. New asset classes (NFTs, CBDCs, tokenized RWAs, prediction markets, climate-credit instruments) will appear over the next decade. Each one needs a leaf schema. If the schema set is hardcoded, each new class is a major release. If it's data-driven (kind enum + schema registry), each new class is a configuration change. **The same principle that made LLVM target-independent must apply here: do not bake the leaf taxonomy into the core.**

---

## 3. ProductTerms (Static-Immutable, Versioned)

1. **Canonical name:** `ProductTerms[u]`, per StatesHome §2 ruling.
2. **Definition:** The inside-the-system, versioned, append-only crystallisation of a unit's immutable contract terms. Distinct from reference data: reference data describes *the external thing*; ProductTerms describes *the unit-as-registered* with the precision the executor needs. Examples: multiplier, currency, expiry, CCP, strike, ISIN, fee schedule, mandate text, benchmark identity, index methodology, CSA collateral schedule (for OTC).
3. **Minimum field set:** `unit_id`, `terms_version_list : NonEmptyList[TermsVersion]`, where each `TermsVersion` carries `(version_id, fields : dict, is_fungibility_preserving : Predicate, registered_at, registered_by)`.
4. **Identity:** `unit_id`. A version chain is *always* attached to a `unit_id`; you cannot create a `TermsVersion` without one. Re-registration of a `unit_id` is a hard error (StatesHome C10).
5. **Provenance:** Synthesised at unit registration from (Reference Data + Convention + originating event — for OTC, the CDM `Trade`; for listed, the contract spec; for SBL, the loan terms). Provenance is the originating CDM payload + the ingest transaction id.
6. **Temporal semantics:** Append-only on the system axis. Each `TermsVersion` carries its own `registered_at`. The current terms are the tail of the list. World-axis amendments produce new TermsVersions (preserving fungibility, C8) or fresh `unit_id` (breaking fungibility, C8 again). **Never in-place mutation.**
7. **Failure consequences:** In-place mutation of terms → past computations no longer reproducible → time-travel collapses → audit chain destroyed. Mistaking a breaking amendment for a preserving one → silent fungibility violation → `Q(u) = 0` invariant becomes meaningless. **Severity: critical.** This is foundational; a bug here is a foundational bug.

**(a) Extension story:** New product families register a new typed `TermsSchema` (subschema of the `fields` dict). The framework provides composition: a structured note's TermsSchema *includes* the embedded option's TermsSchema. Each product type has its own typed schema where illegal combinations are unrepresentable (StatesHome §2.4: typed by product class). Adding a product family = registering its TermsSchema + its `is_fungibility_preserving` predicate + binding to the smart contract template (Tier 2 of Unit Store).

**(b) Versioning model:** Append-only `NonEmptyList[TermsVersion]`. C6+C7: registration-total, no in-place mutation. C8 two-track for amendments: preserving = append; breaking = fresh unit + `superseded_by` link.

**(c) Progressive disclosure:** Simple: `product_terms(u).current()` returns the latest. Complex: an OTC swap notional increase is an amendment — the `is_fungibility_preserving` predicate (declared per-product) decides preserve-vs-break, and the appropriate path runs. Expert: a structured-product issuer needs to step a coupon up (preserving fungibility) — they configure the predicate to allow coupon edits within a band; out-of-band edits trigger the breaking path automatically.

**Decade-load-bearing decision:** The fungibility predicate is itself versioned and ungoverned without explicit RACI (StatesHome F2). For a system that lasts a decade, the predicate cannot be a free function changeable at any time. It must be a versioned policy artefact owned by Legal/Product/Risk together. **This is the single most fragile part of the schema, and it must be governed at design time, not at runtime.**

---

## 4. UnitStatus (Mutable, Shared Across Holders)

1. **Canonical name:** `UnitStatus[u]`, per StatesHome §2.
2. **Definition:** Per-unit mutable status, shared across all holders of the unit. One row per registered unit, total over registered units (C5).
3. **Minimum field set:** `unit_id`, `lifecycle_stage` (PENDING | ACTIVE | MATURED | TERMINATED | EXPIRED | EXERCISED | SETTLED | LISTED | …), `last_settlement_price : Option[Decimal]`, `last_settlement_date : Option[Date]`, `current_weights : Option[Vector]` (QIS), `nav_index : Option[Decimal]` (QIS), `triggered_barrier : Option[Bool]` (knock-in/out), `superseded_by : Option[UnitId]` (for breaking amendments).
4. **Identity:** `unit_id`. One UnitStatus per unit, always.
5. **Provenance:** Initialised at unit registration with product-declared defaults (C5). Mutated only by lifecycle event handlers (with C11 handler tagging — every field has exactly one handler that may write it).
6. **Temporal semantics:** Mutable on the system axis. For time-travel, the value at world-time t is reconstructed by replaying the move-stream + UnitStatus deltas up to t. Each mutation is recorded as a delta in the event log; the current map is a projection of those deltas. **C3: every mutation is part of an atomic StateDelta across all three maps.**
7. **Failure consequences:** Wrong lifecycle stage → executor accepts moves it should reject (e.g., trade against a MATURED unit) → orphan moves. Stale `last_settlement_price` → variation margin computed against wrong target → wrong VM cash flow → conservation still holds but value is wrong. Missing `triggered_barrier` flag update on a knock-out → P&L explain residual. **Severity: high.** UnitStatus is what gates whether the executor will accept a move at all.

**(a) Extension story:** New product families add new fields to their UnitStatus subschema (typed per product class, like ProductTerms — C11 handler tags follow). A new lifecycle stage is added by registering it in the product's stage enum and providing the transition guards.

**(b) Versioning model:** Mutable, but every mutation is an event in the move stream — replayable. Effectively this is event-sourced state; the `UnitStatus` map is a cache; the source-of-truth is the move-stream-plus-StateDeltas. C3 enforces atomicity with the other two maps.

**(c) Progressive disclosure:** Simple: `unit_status(u).lifecycle_stage` answers "is this thing live". Complex: a barrier option workflow polls `triggered_barrier` once per observation cadence. Expert: cross-asset products check the source unit's status for cascade triggers.

**Decade-load-bearing decision:** The C11 handler-canon (each field has exactly one writer) is what makes this auditable in a decade. Without it, the field becomes a free-for-all and 5 years from now you have no idea who can mutate `last_settlement_price`. With it, every mutation is reviewable through a single code path.

---

## 5. PositionState (Per-(wallet, unit) economic state)

1. **Canonical name:** `PositionState[w, u]`, per StatesHome §2 ruling.
2. **Definition:** Per-(wallet, unit) economic state for the holder's relationship to the unit. Examples: `accumulated_cost` (futures), `ccp_binding`, `entry_nav` (QIS subscription), `hwm` (managed account), `accrued_mgmt_fee`, `accrued_perf_fee`, `benchmark_nav_at_inception`, `mandate_breach_flags`, OTC per-position lifecycle.
3. **Minimum field set:** `(wallet_id, unit_id)`, plus product-typed economic-state fields. Each field is C11-tagged with its unique writer.
4. **Identity:** `(wallet_id, unit_id)`.
5. **Provenance:** Created on first touch (first move into the (w,u) pair). Mutated only by C11-tagged handlers. Recorded as deltas in the move stream.
6. **Temporal semantics:** Monotone carrier (C1, StatesHome): once a row is created, it is never garbage-collected. Close-out leaves a `Some(zero)` row, never a `None`. Accessor returns `Option[PositionState]`: `None` = "this wallet has never held this unit"; `Some(zero)` = "held once, currently flat". Both readings are load-bearing (VM-settle, wash-sale lookback, record-date entitlements). **The Option/Monotone duality is non-negotiable.**
7. **Failure consequences:** Collapsing `None` and `Some(zero)` → record-date entitlement misallocation → dividend paid to wrong wallets → conservation holds (because dividends are moves) but holders get wrong amounts. Garbage-collecting closed-out rows → tax reporting (1099-B, wash-sale) collapses. Two strategies sharing a flat per-wallet HWM → fees computed against the wrong baseline → revenue leakage. **Severity: high to critical.**

**(a) Extension story:** Each product class declares its own `PositionStateSchema` with C11-tagged fields. A new product family = a new schema. Mandate/strategy state lives at `PositionState[w, u_MA]` / `[w, u_QIS]` (C12 — no flat per-wallet scalars), so multi-mandate / multi-strategy clients are handled natively without schema growth.

**(b) Versioning model:** Mutable in the same event-sourced sense as UnitStatus, but the C12 keying (always `(w, u)` or `(w, u_MA)`) prevents schema drift over time — no field ever has to migrate from "wallet-keyed" to "(w,u)-keyed" because there is no wallet-keyed economic state.

**(c) Progressive disclosure:** Simple: `position(w, u)` returns `Option[PositionState]`. Complex: a structured note position carries embedded option-state inside its PositionState; queries follow the schema. Expert: a multi-mandate client carries multiple `(w, u_MA)` rows with their own HWMs; a single API query returns them all without special-casing.

**Decade-load-bearing decision:** **C12 — collapsing the W-sector — is the single highest-leverage architectural decision in the framework's data model.** It eliminates an entire class of "per-wallet override" hacks that would have accumulated for 10 years. The mandate-as-unit pattern is exactly the kind of move (Library Over Language: push wallet-overlay state into the unit lattice) that compounds over time.

---

## 6. Wallet Balances

1. **Canonical name:** `Balance[w, u]`.
2. **Definition:** The current quantity of unit `u` held by wallet `w`. In the scalar model, a single number; in the generalised position model (v10.3 §gpm), the six-coordinate vector $(\mathrm{own}, \mathrm{onloan}, \mathrm{borr}, \mathrm{coll\_post}, \mathrm{coll\_recv}, \mathrm{coll\_rehyp})$.
3. **Minimum field set:** `(wallet_id, unit_id)`, `quantity` (scalar or 6-vector), `as_of_ts`. (For derived availability: `avail = own - onloan + borr` — a projection, not a field.)
4. **Identity:** `(wallet_id, unit_id)`.
5. **Provenance:** A pure projection of the move stream + position-state-deltas filtered to (w,u). **Never a primary record.**
6. **Temporal semantics:** Time-indexed. `balance_at(w, u, t)` is well-defined for any t in [genesis, now]. Cached snapshots accelerate queries; the source-of-truth is always the move stream.
7. **Failure consequences:** If treated as a primary record (i.e., written-to independently of the move stream): you have just rebuilt the multi-source-of-truth disaster the framework was designed to eliminate. **The single most dangerous error is to make this category writable.** Severity: catastrophic, by definition — it is the architectural bug the framework prevents.

**(a) Extension story:** Generalised position model (scalar → 6-vector) is the precedent. A future extension (e.g., adding a 7th coordinate for, say, "pledged-but-not-rehypothecable") follows the same pattern: introduce the coordinate, define the Single-Coordinate Move Principle for it, define its conservation law, default the existing units' value to a degenerate case. Critically: existing scalar units must continue to look scalar at the API boundary (graceful degeneration, v10.3 §gpm).

**(b) Versioning model:** No versioning — balances are always reconstructable. The scalar-vs-vector representation is a *schema* version; existing code reading scalar balances of non-lendable units does not break when SBL is introduced (graceful degeneration is the test).

**(c) Progressive disclosure:** Simple: `balance(w, u)` returns a scalar (or `own` coordinate, transparently). Complex: SBL desk uses `position(w, u)` to get the 6-vector. Expert: builds a custom projection (e.g., concentration-weighted exposure across a counterparty's pledged collateral) using the same primitives.

**Decade-load-bearing decision:** **Balances must remain a projection, forever.** The temptation will arise — under performance pressure, under a sloppy refactor, under a "we just need to fix this one balance" exception — to write directly. Resist permanently. The single-source-of-truth property is what every other property in v10.3 stands on.

---

## 7. Move Stream (Event Log)

1. **Canonical name:** `MoveStream`.
2. **Definition:** Immutable, append-only chronological log of every atomic move and StateDelta. The canonical internal record from which all other categories (#3, #4, #5, #6) are projections.
3. **Minimum field set per move:** `move_id`, `transaction_id`, `from_wallet`, `to_wallet`, `unit_id`, `coordinate` (for 6-vector), `quantity` (Decimal, fixed precision), `economic_ts`, `booking_ts`, `source_contract_ref`, `metadata` (event description, ext refs), `tx_type` (SETTLEMENT | COLLATERAL | LIFECYCLE | ACCOUNTING | CORRECTION), `corrects_tx_id` (for compensating transactions), `cdm_payload_ref` (link to #8).
4. **Identity:** `move_id` (unique within stream); `transaction_id` (groups moves into atomic transactions).
5. **Provenance:** Authored by the executor and only the executor (v10.3 §7.7.1 — confining mutation to a single component is an explicit design decision).
6. **Temporal semantics:** Append-only. **Dual timestamps** are critical: economic_ts is when the event happened in the world; booking_ts is when we learned about / committed it. Late events arrive with old economic_ts and current booking_ts. Both are queryable; conflating them destroys time-travel ("what did we know at time t?" vs "what was true at time t?" — v10.3 §1.2 makes both required).
7. **Failure consequences:** Mutation of past entries → time-travel breaks → audit chain destroyed → regulatory exposure under BCBS 239, MiFID II RTS-25, EMIR Article 11. Loss of an entry → balances become wrong → conservation violated (apparent). Lack of cryptographic chaining → tampering undetectable. **Severity: catastrophic.** This is the single most important data category in the framework. Invariant 4 (log monotonicity) is non-negotiable.

**(a) Extension story:** New move types (e.g., a new transaction type for a regulatory regime not yet imagined) are added by extending the `tx_type` enum and registering the corresponding handler. Existing readers do not break (open enum reading discipline). The 6-coordinate move structure is precedent: it was added without breaking the scalar model.

**(b) Versioning model:** The stream itself is never versioned; it is the source. Schema evolution of the move record (e.g., adding new optional metadata fields) follows protobuf-style backward-compatible discipline: append fields, never reorder, never repurpose tags. Old entries remain readable forever.

**(c) Progressive disclosure:** Simple: most consumers query via Wallet Balances or Lifecycle Event Records, not directly from the stream. Complex: balance sheet substantiation queries the stream filtered by (wallet, time-range, tx_type). Expert: forensic auditors read the stream raw, follow `corrects_tx_id` chains, verify hash-chain integrity end-to-end.

**Decade-load-bearing decisions:**
- **Cryptographic hash-chaining from day one.** Retrofitting tamper-evidence into a 10-year-old log is impossible; it must be there at genesis.
- **Decimal precision committed at design time** (e.g., 18 decimal places). Floating point is not negotiable: it breaks determinism, breaks time-travel, breaks idempotency. v10.3 §5.1 already specifies fixed-precision decimal.
- **Total ordering within timestamp** (sequence number) is mandatory for deterministic replay.
- **External replication discipline** — synchronous multi-site, WORM storage, or distributed consensus — must be a deployment-time decision, not retrofitted.

---

## 8. Lifecycle Event Records (CDM BusinessEvent payloads + StateDelta artifacts)

1. **Canonical name:** `LifecycleEventRecord` (CDM `BusinessEvent` payload + StateDelta artifact).
2. **Definition:** The full CDM `BusinessEvent` (with `before` / `after` TradeStates, primitive instructions, exercise terms, workflow lineage) attached to each transaction in the move stream, plus the StateDelta artifact (the C2/C3 atomic three-map mutation tuple) that the executor applied.
3. **Minimum field set:** `event_id`, `transaction_id` (back-link to #7), `cdm_business_event_payload` (full original-form CDM), `cdm_version`, `state_delta` (the three-map atomic delta — ProductTerms append?, UnitStatus diff, PositionState diff), `event_intent` (CDM `EventIntentEnum`), `idempotency_token`, `originating_workflow_run_id`.
4. **Identity:** `event_id`; one-to-one with `transaction_id`.
5. **Provenance:** Authored by the smart contract that generated the moves; stored alongside (not inside) the move record so the move stream stays algebraically clean. Carries the CDM-version stamp.
6. **Temporal semantics:** Append-only. CDM-version stamping is critical: events stored under CDM v6.0.0 must remain replayable when CDM is at v9.0.0. The lifecycle engine must either process old-version events natively or apply a version migration before processing (v10.3 §9.3).
7. **Failure consequences:** Loss of CDM payload → cannot reconstruct *why* a move happened, only *what* moved → audit defence collapses. Wrong CDM-version stamp → replay applies new-version semantics to old-version events → silent semantic drift. Idempotency token loss → re-processing a SBL recall signal → cascade recall fires twice → real economic loss. **Severity: high.**

**(a) Extension story:** New CDM event intents arrive (CDM is actively developed). Each new intent must trigger an update to the relevant product's transition table; the property-based generator (#9 of the v10.3 spec, EventIntentEnum-driven) surfaces missing transitions automatically. New non-CDM event types (e.g., a regulatory regime that mandates a new event class) wrap as a CDM-extension or as a parallel Lifecycle Event subschema with its own version namespace.

**(b) Versioning model:** Each record carries `cdm_version`. Migration from CDM-vN to CDM-v(N+1) is a deterministic transformation, applied at read time or at lazy migration. Old payloads remain stored in original form forever.

**(c) Progressive disclosure:** Simple: most readers query "what type of event was this" → `event_intent`. Complex: regulatory reporting (DRR) reads the full CDM payload to populate EMIR Refit fields. Expert: an auditor reconstructing the workflow lineage walks the chain via `originating_workflow_run_id` (cross-references to #15).

**Decade-load-bearing decision:** **Storing the full CDM payload (not just an extracted summary)** is the choice that pays off for a decade. The forgetful mapping F (v10.3 §9.4) deliberately discards business intent from the move stream — but the addendum keeps the original CDM record alongside. New regulatory regimes, new analytics, new attribution schemes will arrive over the next decade and they will all need information that today seems irrelevant. Keep the payload. Storage is cheap; reconstructable history is priceless.

---

## 9. Market Data — Raw Observables

1. **Canonical name:** `RawMarketObservation`.
2. **Definition:** Time-stamped raw quotes/prints/observations from external venues: exchange ticks, dealer quotes, broker indications, reference fixings (SOFR, EURIBOR), index publications.
3. **Minimum field set:** `observation_id`, `instrument_ref` (link to #2 ReferenceData), `quote_kind` (BID | ASK | MID | LAST | SETTLE | INDEX | FIXING), `value` (Decimal), `currency`, `event_ts` (when did the venue publish), `ingest_ts` (when did we receive), `venue` (MIC code or vendor), `source_attestation` (oracle signature, see #12).
4. **Identity:** `observation_id`; uniqueness by `(instrument_ref, quote_kind, event_ts, venue)`.
5. **Provenance:** Exchange feeds, vendors (Bloomberg, Refinitiv), broker quotes, internal fixing aggregators. Each carries `venue` + `source_attestation` for provenance chain.
6. **Temporal semantics:** Bi-temporal. `event_ts` (world axis: when the venue published) and `ingest_ts` (system axis: when we received). Vendor restatements (a print is corrected post-hoc) append a new observation; the original is not overwritten. **This is critical for the v10.3 §7.7.2 distinction** between "replay as known at time t" and "replay with corrected data".
7. **Failure consequences:** Stale observations driving live valuations → wrong VM, wrong margin, wrong managed-account settlement. Wrong `event_ts` → time-travel queries return the wrong snapshot. Lost source attestation → cannot defend valuation in a dispute. Single-source dependence → outage propagates. **Severity: high** for value-dependent operations.

**(a) Extension story:** New venues, new quote kinds, new instrument coverage are pure data — register the venue, register the quote-kind enum extension, supply the schema. New asset classes (e.g., on-chain DEX prints) wrap into the same schema with venue = "uniswap-v3" and a chain-specific event_ts.

**(b) Versioning model:** Append-only on both axes. Restatements append; originals stay. Each observation also carries an oracle-attestation wrapper (#12) for defensible provenance.

**(c) Progressive disclosure:** Simple: `last_print(instrument)` returns the most recent. Complex: pricing DAG (#10) consumes a structured snapshot $y_t$ at observation epoch t. Expert: a dispute resolution queries `print_at(instrument, world_ts, system_ts)` for "what we would have used had we priced strictly at t under the data we then had".

**Decade-load-bearing decision:** **Capture and store the raw observations forever, not just the calibrated outputs.** Calibration models change; if you keep only calibrated outputs, you cannot rebackfill. With raw observations preserved, any future model can re-calibrate the past. This is the pricing analogue of "keep the move stream, not just the balances".

---

## 10. Market Data — Calibrated (Kalman posteriors / certified curves & surfaces)

1. **Canonical name:** `CalibratedMarketState`.
2. **Definition:** Posterior parameter estimates from the Kalman filter (valuation §5): yield curves, volatility surfaces, credit hazard curves, FX vol surfaces — certified against the no-arbitrage admissible region $\Theta_{AF}$.
3. **Minimum field set:** `calibration_id`, `calibrated_object_kind` (CURVE | VOL_SURFACE | CREDIT_CURVE | FX_SURFACE | ...), `state_vector` $x_{t|t}$, `state_covariance` $P_{t|t}$, `world_ts`, `system_ts`, `source_observations` (links to #9 records used), `model_id`, `certification_status` (CERTIFIED | INDICATIVE | REJECTED), `innovation_stats` (Mahalanobis $D_t^2$), `arbitrage_check_passed : Bool`.
4. **Identity:** `calibration_id`; uniqueness by `(calibrated_object_kind, calibration_target_id, world_ts, system_ts, model_id)`.
5. **Provenance:** Kalman filter workflow consuming raw observations (#9) and prior posterior (recursive). Each record links its input observations and its prior.
6. **Temporal semantics:** Bi-temporal. Each posterior is a function of `system_ts` (when calibrated) and `world_ts` (the latent market state at that world time). Re-calibration with restated data produces a new record with new `system_ts`, same `world_ts`.
7. **Failure consequences:** Uncertified posterior driving pricing → arbitrageable prices reported, FVA wrong, regulatory capital wrong. Lost source-observation links → cannot reproduce the calibration → audit collapse. Stale posterior → quality flag on Valuation Records (#11) wrong → official PnL flows on stale data. **Severity: high.**

**(a) Extension story:** New calibrated object kinds (e.g., funding-vol surface, dual-curve discount) register as new sub-kinds. New filter implementations (UKF for non-linear observation models) replace the Kalman activity; the data shape stays.

**(b) Versioning model:** Append-only with versioned `model_id`. The same world_ts may have many posterior records (one per `system_ts`, per `model_id`) — they coexist. The "current best" is selected by policy, not by overwrite.

**(c) Progressive disclosure:** Simple: `curve(USD, world_ts).discount_factor(tenor)` for a vanilla pricing call. Complex: a multi-model consensus (valuation §4.10) reads multiple posteriors and computes ModelReserve. Expert: a Calibration Manifesto-style analyst queries innovation history $D_t^2$ across time to detect regime change.

**Decade-load-bearing decision:** **Raw observations and calibrated states are separate categories** with separate provenance chains. The temptation to fold calibrated state into "market data" as a single category collapses two distinct temporal disciplines. Vendors restate raw prints; calibration model versions evolve. Both must time-travel independently, and the only way is to keep them as separate, linked categories.

---

## 11. Valuation Records

1. **Canonical name:** `ValuationRecord`, per Valuation §3.
2. **Definition:** The output of a pricing computation for a unit at a time, including base price, full Greeks Jacobian, model identity, market-data snapshot identity, FSM state, and quality flag. The `dirty_price` field IS $P_t(u)$ of the Ledger framework.
3. **Minimum field set:** `unit_id`, `valuation_ts`, `dirty_price`, `clean_price`, `accrued`, `greeks` (model-tagged-union: BSGreeks | HestonGreeks | LocalVolGreeks | SABRGreeks | KernelVolGreeks | IRSGreeks | BondGreeks | ...), `model_id` (load-bearing: tells you which Jacobian dimension), `market_data_snap` (link to #10), `compute_ms`, `quality` (FIRM | INDICATIVE | APPROXIMATE | STALE | FAILED), `fsm_state` (one of 8 states from valuation §2), `pnl_explain_residual` (when applicable), `unit_state_ref` (link to #4 + #5 versions used).
4. **Identity:** `(unit_id, valuation_ts, model_id)`.
5. **Provenance:** Authored by the PricingWorkflow per unit (one workflow per unit, valuation §6.1). Carries `market_data_snap`, `unit_state_ref`, `model_id` — the complete reproducibility tuple.
6. **Temporal semantics:** Append-only on `valuation_ts` (world axis). Each unit has many ValuationRecords across time. Multi-model coexistence: per `(unit_id, valuation_ts)` there may be many records, one per `model_id` (primary, secondary for model risk, stress for capital).
7. **Failure consequences:** Wrong `model_id` stamp → cross-model PnL explain (Remark 4.1 in valuation) → spurious unexplained residual blamed on traders. Quality flag wrong → stale price treated as FIRM → official PnL flows on bad data. Lost `unit_state_ref` → cannot reproduce → time-travel breaks. **Severity: high** (medium for non-FVTPL).

**(a) Extension story:** New models register a new Greeks tagged-union variant. The PricingWorkflow is generic; the per-model Jacobian is hot-pluggable. Approximate-pricing fallback (Taylor) is structural, not per-model.

**(b) Versioning model:** Append-only per (unit, time, model). Restated models (a model bug fix, a recalibration window correction) produce *new* ValuationRecords; the originals are retained for "what we knew at time t" replay.

**(c) Progressive disclosure:** Simple: `value(u, t)` returns the FIRM price under the primary model. Complex: a risk view requests delta under primary + delta under stress model + delta under secondary, all from the same query. Expert: PnL Explain queries the full Jacobian against parameter changes between $t_{n-1}$ and $t_n$.

**Decade-load-bearing decision:** **The Greeks field as a tagged union (Heston ≠ BS ≠ LocalVol)** is the right call and the StatesHome-style decision applied to valuation. Forcing all Greeks into a flat scalar schema (the Bloomberg "single vega" convention) discards information the moment it's collected. Tagged union preserves model-specific structure, costs nothing today, and pays off the moment you migrate from BS to local-vol.

---

## 12. Oracle Attestations

1. **Canonical name:** `OracleAttestation`.
2. **Definition:** A signed wrapper carried with any externally-sourced fact (Reference Data, Market Observation, regulatory return, settlement confirmation) attesting *who* asserted *what* *when* and *under what authority*. **Reframed from the floor's "Oracle category": Oracle is a wrapper protocol, not a peer data class.**
3. **Minimum field set:** `attestation_id`, `attested_payload_ref` (link to the wrapped record in #2, #9, #13, etc.), `attestor_id` (LEI of the attesting authority), `signing_key`, `signature`, `attestation_ts`, `policy_ref` (which policy/standard the attestation operates under, e.g., GLEIF policy version, exchange feed contract).
4. **Identity:** `attestation_id`.
5. **Provenance:** External attesting authority. The attestation IS the provenance — it is what makes the wrapped data legally and operationally defensible.
6. **Temporal semantics:** Append-only. Re-attestation (e.g., a vendor restating a print) produces a *new* attestation linked to the *new* version of the underlying data record.
7. **Failure consequences:** Lost attestation → cannot defend in regulatory dispute. Forged attestation → contaminated reference data. Single-attestor dependence (no multi-source quorum on critical facts) → systemic exposure to one vendor outage or one fraud event. **Severity: high** for legally-significant data, medium for merely useful data.

**(a) Extension story:** New attestor authorities, new signing schemes (post-quantum signatures eventually), new quorum policies (M-of-N attestations for critical fixings) all extend the wrapper schema, never the wrapped data. Crucially: **the same Oracle wrapper applies to every external category.** Reference data is oracle-attested. Market observations are oracle-attested. Settlement confirmations are oracle-attested. Regulatory acknowledgements are oracle-attested. One protocol, many wrapped categories.

**(b) Versioning model:** Append-only. Each attestation is immutable once signed; restatements are new attestations.

**(c) Progressive disclosure:** Simple: most readers ignore the attestation and just consume the payload. Complex: a regulatory report attaches the full attestation chain. Expert: a dispute resolution traces the attestation graph end-to-end.

**Decade-load-bearing decision:** **Oracle is a protocol, not a category.** A common signing/wrapper scheme over all external data categories beats per-category bespoke provenance hacks. In ten years there will be data sources we don't anticipate (CBDCs, on-chain oracles, AI-generated proxies); they all need the same wrapper. Treating Oracle as a peer data class would force every new source into a separate provenance regime; treating it as a protocol means every new source plugs in for free.

---

## 13. Settlement Instructions and Confirmations

1. **Canonical name:** `SettlementInstruction` and `SettlementConfirmation`.
2. **Definition:** Outbound: the deterministic projection of a SETTLEMENT/COLLATERAL transaction into an external instruction (sese.023, pacs.008, …) plus enrichment (SSI, CSD account, priority). Inbound: the confirmation/failure return path (sese.025, camt.054).
3. **Minimum field set:** `instruction_id` (= transaction_id at projection time), `settlement_type` (DVP | FOP | CASH), `securities_leg`, `cash_leg`, `counterparty_lei`, `execution_venue_mic`, `settlement_date`, `csd_participant_id` (added at enrichment), `submission_ref`, `status` (EXECUTED | INSTRUCTED | SETTLED | FAILED), `iso20022_message_blob`, `confirmation_payload`.
4. **Identity:** `instruction_id` for outbound, `confirmation_id` for inbound; linked back to `transaction_id`.
5. **Provenance:** Outbound: authored by the SettlementWorkflow as a projection of a committed transaction. Inbound: arrives from CSD/correspondent, ingested via the ISO 20022 adapter. Both carry oracle attestations (#12).
6. **Temporal semantics:** Append-only with status transitions tracked as lifecycle events (#8). Status lifecycle EXECUTED → INSTRUCTED → SETTLED/FAILED is itself a tracked state machine.
7. **Failure consequences:** Lost outbound instruction → settlement fails → real economic loss + CSDR mandatory buy-in cost. Mismatched confirmation → undetected break with custodian → reconciliation failure (boundary, not internal). **Severity: high** in the settlement window.

**(a) Extension story:** New ISO 20022 message types or new CSD protocols (T2S evolutions, cross-border DLT settlement) plug in as new generators/parsers. The intermediate `SettlementInstruction` struct (valuation §settlement) is the stable interface; both sides evolve independently.

**(b) Versioning model:** Append-only. Each status transition is a new lifecycle event record (#8) with the new status; the original instruction is never mutated.

**(c) Progressive disclosure:** Simple: most readers query `transaction.settlement_status`. Complex: a CSDR-buy-in workflow walks the full confirmation/failure chain. Expert: a netting reconciler verifies the algebraic gross-vs-net identity (v10.3 §settlement-netting).

**Decade-load-bearing decision:** **The SettlementInstruction is the stable shared data type between Ledger and Settlement Layer.** Keep it minimal, add to it only what every settlement infrastructure needs. Resist adding settlement-layer-specific fields (CSD participant ID is the borderline case — accept it, but no further).

---

## 14. External Account / SSI Data

1. **Canonical name:** `ExternalAccountMapping` / `SettlementInstruction (Standing)`.
2. **Definition:** The mapping from internal wallet identifiers to external real-world accounts: BIC, IBAN, custodian account number, CSD participant ID, nostro/vostro account references, SSI (Standing Settlement Instructions).
3. **Minimum field set:** `mapping_id`, `internal_wallet_ref`, `external_account_kind` (BANK | CUSTODY | CCP_CLEARING | CSD_PARTICIPANT | NOSTRO | VOSTRO), `external_account_id`, `swift_bic`, `iban_or_account`, `valid_from`, `valid_to`, `effective_purpose` (cash payments | securities settlement | margin | …), `priority` (when multiple SSIs apply).
4. **Identity:** `mapping_id`; uniqueness by `(internal_wallet_ref, external_account_kind, effective_purpose, valid_from)`.
5. **Provenance:** Operational onboarding (Treasury / Operations function), counterparty SSI exchange (industry SSI tools like ALERT/Omgeo). Carries oracle attestations from the registering party.
6. **Temporal semantics:** Bi-temporal. SSIs change over time (a counterparty switches custodian) — versioned with `valid_from / valid_to` on the world axis plus `ingest_ts` on the system axis. Time-travel queries reconstruct "which SSI was effective at the time of trade settlement".
7. **Failure consequences:** Wrong SSI → cash sent to the wrong account → real economic loss + recovery operations. Missing SSI at settlement time → settlement fails. Stale SSI → fraud risk window. **Severity: high.** This is the single largest source of settlement-layer ops cost in real institutions.

**(a) Extension story:** New external-account kinds (e.g., on-chain wallet addresses for tokenized settlement) extend the kind enum. New SSI exchange standards plug in as new ingestion adapters.

**(b) Versioning model:** Append-only, bi-temporal. SSI restatements append.

**(c) Progressive disclosure:** Simple: `ssi_for(wallet, purpose)` returns the active SSI. Complex: a multi-leg settlement queries multiple SSIs (cash-side and securities-side) with priority resolution. Expert: a forensics request reconstructs the SSI as it was on a specific historical settlement date.

**Decade-load-bearing decision:** **External account data lives in the settlement layer, not the ledger** (per v10.3 §settlement-boundary). The ledger holds only the internal_wallet_ref → external_id pointer; the rich SSI table belongs to the settlement layer. The ledger must not pretend to own it. **Explicit boundary > implicit ownership** — the categories that look most tempting to absorb (because they're "needed at settlement time") are the categories that erode the ledger's purity if absorbed.

---

## 15. Workflow / Orchestration State (Temporal histories)

1. **Canonical name:** `WorkflowState` / `WorkflowHistory` (Temporal-native).
2. **Definition:** Per v10.3 §10.3 (Two Audit Trails): the orchestration audit trail recording activity invocations, inputs, results, timer fires, signals, retries, and saga compensations. Distinct from the move stream (#7), which records economic content.
3. **Minimum field set:** `workflow_run_id`, `workflow_type`, `workflow_id` (semantic, e.g., `bond-coupon-{unit_id}`), `event_history` (Temporal-native append-only event list), `current_state`, `started_at`, `completed_at` or `None`, `task_queue`, `cdm_version_at_start`.
4. **Identity:** `workflow_run_id`.
5. **Provenance:** Authored by the Temporal cluster as workflows execute. Linked to the move stream via the `originating_workflow_run_id` carried on Lifecycle Event Records (#8) and the `transaction_id` carried on activity completions.
6. **Temporal semantics:** Append-only event history per workflow run. ContinueAsNew creates a new run with a hand-off; the chain is reconstructable.
7. **Failure consequences:** Loss of workflow history → cannot diagnose why a settlement was delayed / why a margin call was retried / why a saga compensated. Liveness gap re-emerges if the durable timer infrastructure is compromised. **Severity: medium-high.** The economic content is in the move stream and is preserved; orchestration state is operational forensics.

**(a) Extension story:** New workflow types (new lifecycle products, new saga patterns) register and run on the same Temporal infrastructure. The data shape is fixed by Temporal; what extends is the workflow code.

**(b) Versioning model:** Workflow versioning is Temporal-native (`getVersion` API). Each long-running workflow that survives a code deployment carries its starting version; deterministic replay uses the version-matched code path.

**(c) Progressive disclosure:** Simple: most users never look at it. Complex: ops investigations query workflow history filtered by workflow_id pattern. Expert: a code-deployment-driven incident reconstruction replays workflow history against multiple code versions to identify when a logic change took effect.

**Decade-load-bearing decision:** **Two audit trails, kept structurally separate and structurally linked.** Ledger event log answers "what happened economically"; workflow history answers "how was it sequenced". Conflating them — even under "simplicity" — destroys both. The economic chain must remain auditable independent of orchestration; orchestration must remain debuggable independent of economic semantics. The link is via IDs, not via merger.

---

## 16. Wallet Registry (KYC, permissions, capability scopes — non-state sidecar)

1. **Canonical name:** `WalletRegistry` (StatesHome §2's explicit non-state sidecar).
2. **Definition:** Per-wallet metadata: KYC status, permitted operations, capability scopes (which lifecycle events can target this wallet), audit cursors, real-vs-virtual classification, owning entity (for real wallets), counterparty LEI link (for virtual wallets), book/desk/account taxonomic membership.
3. **Minimum field set:** `wallet_id`, `wallet_kind` (REAL | VIRTUAL), `owning_entity_lei`, `kyc_status` (CLEARED | PENDING | EXPIRED), `permission_scopes` (set of operation enum values), `capability_grants` (per StatesHome C4 — capability-scoped reads), `book_ref`, `audit_cursor_ts`, `created_at`, `last_kyc_review`.
4. **Identity:** `wallet_id`.
5. **Provenance:** Operational onboarding (KYC, compliance approvals). KYC artefacts (proof-of-identity, sanctions screening results) are linked but stored externally.
6. **Temporal semantics:** Mutable on the system axis; each mutation is itself an event (audit cursor pattern). KYC status has a world-axis effective period; permission scopes change with operational policy.
7. **Failure consequences:** Wrong permission scope → wallet receives moves it should not (KYC-failed wallet receiving cash) → AML breach. Lost capability grant → legitimate operation rejected → liveness failure on a margin call. **Severity: high** for compliance, medium for ops.

**(a) Extension story:** New permission kinds, new capability scopes, new KYC regimes are pure data. New wallet kinds (e.g., "tokenized custody wallet" with on-chain provenance) extend the kind enum.

**(b) Versioning model:** Mutable but event-sourced (every mutation is logged). World-axis effective periods on KYC status.

**(c) Progressive disclosure:** Simple: `can(wallet, operation)` returns Bool. Complex: capability grants for cross-(w, u_MA) overlay reads (StatesHome C4) gate sensitive queries. Expert: a compliance officer reconstructs the wallet's permission history end-to-end for a regulatory request.

**Decade-load-bearing decision:** **Wallet Registry is explicitly *not* economic state.** StatesHome is unambiguous: the W-sector collapses for *economic* state; KYC and capabilities are operational, non-financial, and they live here as a sidecar. Resist the temptation to fold them into PositionState (it would defeat C12) or into a "WalletState" map (it would resurrect the W-sector). They are operational metadata; keep them separate.

---

## Summary

**Count:** 16 categories.

**Floor coverage:**
- Static → split into Convention (#1) and ProductTerms (#3) with explicit different versioning disciplines.
- Reference → #2 ReferenceData; **Listed-instrument detail merged in as a leaf schema**, not a peer.
- Market → split into Raw Observables (#9) and Calibrated (#10) with separate temporal disciplines.
- Oracle → reframed as a wrapper protocol (#12), not a peer.
- Smart-contract execution → split into Lifecycle Event Records (#8, data) and Workflow State (#15, orchestration); per the v10.3 dual-audit-trail principle.
- Listed-instrument detail → merged into #2.

**Additions beyond floor:** UnitStatus (#4), PositionState (#5), Wallet Balances (#6), Move Stream (#7), External Account/SSI (#14), Wallet Registry (#16). These were forced by the StatesHome 3-map ruling, the move-stream-as-source-of-truth principle, and the explicit settlement-layer boundary.

**Disagreements:** Three substantive ones, listed in §0. (i) Listed-instrument detail is not a peer; (ii) "Static" hides three different versioning disciplines and must split; (iii) Smart-contract execution is a process, not a data category, and must be replaced by the data it actually emits.

**File path:** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/work/phase1/lattner.md`
