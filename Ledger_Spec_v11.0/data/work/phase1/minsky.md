# Ledger v11.0 Data Specification — Phase 1 (Minsky)

**Discipline.** Type-driven design. Parse, don't validate. Make illegal states
unrepresentable. Total functions only at the boundary between parsed and
unparsed worlds. The compiler catches before the runtime explains.

**Mandate per item.** Seven core fields (canonical name, definition, minimum
field set, identity, provenance, temporal semantics, failure consequences) plus
three Minsky riders: **(a)** the parse-don't-validate boundary; **(b)** which
fields would degrade to *booleans-and-comments* in a weak design and how the
type catches that; **(c)** where a closed enumeration replaces a free string.

**Sources read in full.** `ledger/ledger_v10.3.tex` (Tier 3 unit registry §3,
state §7.3, conservation §2.4, settlement projection §8, CDM mapping §9, GPM /
SBL §15, obligation liveness §14.7), `ledger/ledger_v10.3_addendum_stateshome.tex`
(StatesHome 3-map ruling, C1–C12), `valuation/ledger_valuation_v1.0.tex`
(valuation FSM, ValuationRecord, Pricing DAG, Kalman calibration, Greeks).

---

## §0 Argument with the floor taxonomy

The six floor categories are a useful first cut but contain redundancy, a
misnamed bucket, two missing top-level homes, and one subsumption error. I
ship the floor as given, but I argue four edits before enumerating items.

### §0.1 "Static" is the wrong name

There is almost no truly static data in a financial system. Day-count
conventions, holiday calendars, business-day adjustment rules, jurisdiction
codes, regulatory regimes — every one of these mutates on a multi-year cadence
under regulatory pressure (CSDR penalty rates, IFRS 9 classification rules,
EMIR Refit field set). What the floor calls *Static* is in fact **System
Invariant** (rare: reference currency designation, decimal precision, the
identity of the system itself) plus **Slow-Reference** (everything else).
Conflating them is dangerous: it suggests "Static = no version field needed,"
which is exactly the v10.3 Section 7.7 mistake that the StatesHome addendum
C6 (versioned `ProductTerms`) corrects.

**Ruling.** I split *Static* into two: **System Invariant** (truly hard-coded,
≤ 10 facts in the entire system, never versioned, set at deploy) and
**Slow-Reference** (versioned, externally-sourced, but slow-moving — day-count
library, calendar, jurisdiction registry). Slow-Reference belongs under
*Reference*, not *Static*.

### §0.2 "Listed-instrument detail" is subsumed by Reference

The floor promotes *Listed-instrument detail* to a top-level category. This
is asymmetric: there is no parallel *OTC-instrument detail* or
*Structured-product detail* category. The v10.3 Tier 1 (Reference Data) §3.3.1
already houses contract specifications uniformly; the only thing exchange
listings add is a richer set of fields (exchange MIC, contract month code,
tick size, lot size, settlement convention) — but these are still reference
data with the same provenance discipline (vendor feed, versioned, signed by
exchange). Promoting them creates two homes for instrument terms, splits the
parser, and forces every consumer to discriminate "is this listed?" — exactly
the wildcard-discrimination antipattern that StatesHome §0.3 rejects when it
collapses the would-be `WalletState` sector into `PositionState[w, u_MA]`.

**Ruling.** Subsume *Listed-instrument detail* under *Reference*. Treat
ListedContractSpec as a refinement of `ProductTerms` — same map, same
discipline, additional fields. The exchange-vs-OTC discrimination is then a
constructor of a sum type (`Venue = Listed { exchange, ccp } | OTC { csa }`),
not a category boundary.

### §0.3 Missing: Party / Identity

LEI, BIC, MIC, wallet ID, custodian account, CSD participant ID — none of
these are market data, none are oracle attestations, none are
smart-contract-emitted. They are **identity assertions** about real-world
legal and operational entities, with their own provenance (GLEIF for LEI,
SWIFT for BIC, ISO 10383 for MIC), their own versioning (LEI status:
ISSUED | LAPSED | RETIRED | MERGED), and their own validation gates
(LEI checksum, LEI-status check). Folding them into *Reference* is workable
but loses a discrimination: instrument reference data is *what* trades;
identity reference data is *who* and *where*. The valuation document and
v10.3 §8 settlement-projection both depend on identity data orthogonal to
instrument data.

**Ruling.** Add **Identity / Party** as a top-level category. It cuts cleanly
across Reference and Oracle.

### §0.4 Missing: Legal / Agreement

The framework references — but the floor does not enumerate — **legal
agreements** as data. CSA terms (threshold, MTA, eligible collateral schedule,
haircut schedule, governing law), GMSLA Schedule consents (rehyp permitted,
title transfer vs security interest), ISDA Master Agreement amendments,
mandate text, fee schedules, prospectus, term sheet. v10.3 Tier 1 mentions
"OTC unit identity = CDM Trade including Collateral" — Collateral is
*pointing to a legal agreement that lives elsewhere*. That elsewhere has no
home in the floor. The StatesHome addendum recognises this implicitly when
it places *mandate text, fee schedule, benchmark identity* in
`ProductTerms[u_MA]`, but the data category itself is unnamed.

**Ruling.** Add **Legal / Agreement** as a top-level category. It feeds the
*Reference* tier (terms data) and the *Oracle* tier (amendment events) but
is itself a third thing: the corpus of binding contracts that the smart
contract executes against.

### §0.5 Missing: Time / Calendar

Timestamps, business day conventions, holiday calendars, knowledge-vs-effective
time, FSM staleness thresholds, the obligation deadline `t_d`, the cadence of
each pricing workflow — all temporal scaffolding. Burying this in Reference
hides that **dual-timestamp discipline** (economic timestamp vs booking
timestamp, v10.3 §8.4) is a load-bearing invariant. A weak design uses one
`datetime` field and a comment.

**Ruling.** Add **Time / Calendar** as a top-level category. Three irreducible
items live there.

### §0.6 The post-edit floor

```
1. System Invariant      (was: Static, narrowed)
2. Reference             (now subsuming Listed-instrument detail and Slow-Reference)
3. Identity / Party      (new)
4. Legal / Agreement     (new)
5. Time / Calendar       (new)
6. Market                (unchanged)
7. Oracle                (unchanged, scope clarified below)
8. Smart-contract execution  (unchanged)
9. State                 (new — ProductTerms / UnitStatus / PositionState are data the framework manages, not consumes)
10. Obligation           (new — first-class object per v10.3 §14.7, neither market nor oracle nor execution output)
```

Ten categories, no overlap, every item below has exactly one home. The original
floor's six become 7 + 3 = 10 by splitting and adding; nothing is dropped.

---

## §1 System Invariant

### 1.1 ReferenceCurrency

1. **Canonical name.** `ReferenceCurrency`
2. **Definition.** The single ISO 4217 code in which portfolio value `V_t` is
   denominated and against which `P_t(USD) = 1` per Definition §4.1 of v10.3.
3. **Minimum field set.** `code: Iso4217Code`, `decimal_precision: Nat`
   (typically 18), `set_at: SystemEpoch`.
4. **Identity.** Singleton: there is exactly one per ledger instance.
5. **Provenance.** Set at system inception by governance ceremony; never
   amended without a parallel ledger run.
6. **Temporal semantics.** Set-once, immutable for the lifetime of the
   instance. A change requires a new ledger.
7. **Failure consequences.** Catastrophic. Every PnL number, every settlement
   instruction, every regulatory report is denominated against this constant.
   A silent change corrupts every historical value.

- **(a) Parse boundary.** At system bootstrap, parse a config entry into a
  refined type `Iso4217Code` whose constructor rejects anything not in the
  closed enumeration of ISO 4217 codes. There is no reparsing; the bootstrap
  is the only entry.
- **(b) Booleans-and-comments antipattern.** A weak design stores
  `reference_currency: str = "USD"` as a global. Type catch: a singleton
  module-level value of type `Iso4217Code` (sealed) with no setter; every
  consumer takes it by reference, not by string lookup.
- **(c) Closed enumeration.** ISO 4217 itself. Not a free string under any
  circumstance.

### 1.2 SystemId

1. **Canonical name.** `SystemId`
2. **Definition.** The unique identifier of the ledger instance, used to
   distinguish virtual ledgers (§5) from the real ledger (§5) and as the
   tamper-evident anchor for the move stream hash chain (Invariant 4).
3. **Minimum field set.** `id: Uuid128`, `is_virtual: bool`, `parent: Option<SystemId>`.
4. **Identity.** Singleton per instance.
5. **Provenance.** Generated at instance creation; signed by the governance key.
6. **Temporal semantics.** Set-once.
7. **Failure consequences.** Loss of replay determinism across instances;
   collision in a multi-ledger reconciliation.

- **(a) Parse boundary.** Bootstrap, identical to 1.1.
- **(b) Antipattern catch.** A weak design uses an unsigned string. Refine to
  `Uuid128` whose constructor enforces 128-bit canonical form and rejects
  the empty string at compile time (newtype pattern).
- **(c) Closed enum.** None applies (UUID is structural, not enumerated). The
  *companion* `is_virtual` discriminator must be a sum type
  `LedgerKind = Real | Virtual { parent: SystemId }`, not a `bool`.

### 1.3 DecimalPrecisionPolicy

1. **Canonical name.** `DecimalPrecisionPolicy`
2. **Definition.** Per v10.3 §5.1: the fixed-precision decimal arithmetic
   contract. `quantity_precision: 18`, `price_precision: 18`,
   `rounding_mode: BankersHalfToEven`.
3. **Minimum field set.** `quantity_precision`, `price_precision`,
   `rounding_mode`, `arithmetic_library_version`.
4. **Identity.** Singleton per instance.
5. **Provenance.** Defined in spec; pinned at deploy.
6. **Temporal semantics.** Set-once. A change re-defines the meaning of
   "exact" in the conservation law.
7. **Failure consequences.** Cross-platform bit-divergence breaks
   reproducible time travel and CDM round-tripping (§9).

- **(a) Parse boundary.** Bootstrap; loaded into a `DecimalContext` value
  passed explicitly into every arithmetic site (no ambient default).
- **(b) Antipattern catch.** Float arithmetic with comment "// careful, USD
  has 2dp." Type catch: every quantity is `Decimal { ctx: DecimalContext }`,
  not `f64`.
- **(c) Closed enum.** `RoundingMode = HalfToEven | HalfUp | Floor | Ceiling`.
  Free string forbidden.

---

## §2 Reference

### 2.1 InstrumentReference (Tier 1, v10.3 §3.3.1)

1. **Canonical name.** `InstrumentReference`
2. **Definition.** Externally-sourced master data identifying tradable
   instruments. Houses ISIN, CUSIP, FIGI, ticker, exchange listing, contract
   spec, issuer, coupon schedule template — i.e., the immutable economic
   skeleton of a unit before any holder is attached.
3. **Minimum field set.**
   - `kind: InstrumentKind`
     `= Cash { iso4217 }`
     `| ListedEquity { isin, primary_listing: MIC }`
     `| ListedDerivative { exchange: MIC, contract_spec: ContractSpec }`
     `| Bond { isin, coupon_schedule, maturity, day_count, accrual_convention }`
     `| StructuredNote { isin, terms_doc_hash, embedded_payouts: [PayoutRef] }`
     `| Token { contract_address, chain_id, underlier_isin: Option<ISIN> }`
   - `as_of: VersionedTimestamp`
   - `vendor: VendorId`, `vendor_record_hash: Sha256`
4. **Identity.** Hash of the kind-specific identity tuple; for ListedDerivative
   the v10.3 §3.2 rule (exchange × underlier × type × strike × expiry) gives a
   deterministic key; CME-ES and ICE-ES become *distinct units*, as required
   by the StatesHome addendum §4.1.
5. **Provenance.** Reference data vendor (Bloomberg, Refinitiv, ANNA,
   exchange directly). Each record carries `vendor_record_hash` so that a
   replay can verify the bytes that produced the parsed value.
6. **Temporal semantics.** **Versioned append-only**, exactly per StatesHome
   C6 — applied here at the reference-data layer rather than only at
   `ProductTerms`. New ISIN re-issuance, exchange contract spec changes,
   coupon-step amendments append a `TermsVersion`. Re-registration of a
   `unit_id` is rejected (StatesHome C10).
7. **Failure consequences.** Stale or wrong reference data corrupts every
   downstream tier: pricer cannot find the strike, settlement projection
   cannot resolve the ISIN to a CSD identifier, regulatory reports fail
   field validation. Worse: two systems disagree on what `XYZ` *means*.

- **(a) Parse boundary.** `parse_instrument_reference: VendorBytes →
  Result<InstrumentReference, ParseError>` at vendor-feed ingest. Downstream
  code consumes only `InstrumentReference`, never raw vendor bytes. The
  parser enforces uniqueness, term consistency, and product qualification
  (v10.3 §3.5 — CDM `ProductQualification` returning a valid classification).
- **(b) Booleans-and-comments antipattern.**
  - `is_listed: bool` with no carrier of "which exchange." Type catch: the
    sum-type discriminator `Listed{exchange, ccp}` makes "listed without an
    exchange" structurally unrepresentable.
  - `expiry: Option<Date>` with the comment "// only meaningful for derivatives."
    Type catch: `expiry` lives inside `ListedDerivative` and `Bond` constructors,
    absent from `Cash` and `ListedEquity`. The compiler rejects
    `cash.expiry` at compile time.
  - `multiplier: Option<Decimal>` with the comment "// must be positive."
    Type catch: refined type `PositiveDecimal` whose constructor rejects
    `≤ 0`. No code downstream re-checks.
- **(c) Closed enumerations.**
  - `Iso4217Code` (cash currency).
  - `MIC` (ISO 10383, ~3,000 codes; closed registry, validated against a
    dated snapshot).
  - `OptionTypeEnum` (CDM: `CALL | PUT | PAYER | RECEIVER | STRADDLE`).
  - `DayCountFractionEnum` (CDM: `ACT_360 | ACT_365_FIXED | ACT_ACT_ICMA |
    THIRTY_360 | …`).
  - `BusinessDayConvention` (CDM: `FOLLOWING | MODIFIED_FOLLOWING | PRECEDING |
    NONE`).
  - `SettlementType` (CDM: `CASH | PHYSICAL | NET`).
  No free strings for any of these. Day-count and business-day-convention
  in particular: a string-typed field guarantees a wrong-method bug under
  property-based testing within ten generations.

### 2.2 ProductTerms (Tier 2 / Tier 3, v10.3 §3.3.2-3, plus StatesHome C6/C7)

1. **Canonical name.** `ProductTerms`
2. **Definition.** The immutable, versioned, append-only term sheet of a unit.
   Per StatesHome §3, this is one of the three state maps:
   `ProductTerms : Map[UnitId, NonEmptyList[TermsVersion]]`. Houses everything
   from the Tier 1 instrument plus product-binding (smart contract reference)
   plus per-unit static parameters (multiplier, currency, expiry, CCP, strike,
   ISIN, fee schedule, mandate text, benchmark identity, index methodology).
3. **Minimum field set.**
   - `unit_id: UnitId`
   - `versions: NonEmptyList<TermsVersion>` where each `TermsVersion` =
     `{ effective_at: Timestamp, fields: TermsFieldMap, predicate:
        FungibilityPreservingPredicate, signed_by: GovernanceKey }`
   - `smart_contract_ref: SmartContractRef`
   - `product_kind: ProductKind` (sum type discriminating Bond | Future |
     Option | IRS | TRS | Mandate | QIS | …)
4. **Identity.** `unit_id` (deterministic hash from CDM object per v10.3
   §3.3.3); a re-registration of the same `unit_id` is a hard error
   (StatesHome C10).
5. **Provenance.** Created by the `register_unit` transaction; subsequent
   versions appended by `amend_unit` transactions whose
   `is_fungibility_preserving` predicate returns `Preserving` (StatesHome C8).
   `Breaking` amendments allocate a fresh `unit_id` and stamp `superseded_by`.
6. **Temporal semantics.** Append-only; `current()` returns the head; replay
   at time `t` returns the latest version with `effective_at ≤ t`.
   Registration-total (StatesHome C7).
7. **Failure consequences.** A breaking amendment misrouted as preserving
   silently changes the meaning of every existing position; a preserving
   amendment misrouted as breaking creates a fresh `unit_id` and orphans
   existing positions. Both errors are economically severe and detectable
   only post-hoc.

- **(a) Parse boundary.** Built by `register_unit_handler` and
  `amend_unit_handler`. The handler is the only path; direct map writes are
  forbidden by capability scoping (StatesHome C4).
- **(b) Booleans-and-comments antipattern.**
  - `is_amended: bool`. Type catch: `NonEmptyList[TermsVersion]` carries the
    full chain; `is_amended = versions.tail.nonempty`.
  - `amendment_kind: str` with values `"preserving"` and `"breaking"`. Type
    catch: `AmendmentResult = Preserving { new_version: TermsVersion } |
    Breaking { new_unit_id: UnitId, supersedes: UnitId }`. No string match
    on the consumer side.
  - `is_fungibility_preserving: Optional[Callable]` with the comment
    "// must be set for amendable products." Type catch: required field on
    every `TermsVersion`; a `TermsVersion` without it does not type-check.
- **(c) Closed enumerations.**
  - `ProductKind` (closed sum across CDM `Product` choice branches).
  - `LifecycleEventIntent` (CDM `EventIntentEnum` — see 2.3 below for the
    full list).
  - `FeeKind` (`Management | Performance | EntryLoad | ExitLoad | Carry`).

### 2.3 LifecycleIntent (CDM `EventIntentEnum`)

1. **Canonical name.** `LifecycleIntent`
2. **Definition.** The closed CDM enumeration of business intents that drive
   state transitions. Listed in v10.3 §11.5: `ALLOCATION, CANCELLATION,
   CLEARING, COMPRESSION, EXERCISE, FORMATION, INCREASE, NOVATION,
   OBSERVATION, OPEN, PARTIAL_TERMINATION, TERMINATION, TRANSFER, EXPIRE,
   ASSIGN, CORRECTION, EARLY_TERMINATION, REALLOCATION`.
3. **Minimum field set.** Single tag.
4. **Identity.** The tag itself.
5. **Provenance.** FINOS CDM v6.0.0 schema, pinned at the integration boundary.
6. **Temporal semantics.** A new CDM release adds tags; the framework's
   handler table is exhaustive over the *pinned* version, with a parser
   that rejects unknown tags from a newer feed (forces explicit upgrade,
   not silent ignore).
7. **Failure consequences.** Wildcard-handling of intents is the default
   bug class. Per Lemma in v10.3 §11.5.2, a missing handler must surface as
   a property test failure, not a runtime no-op.

- **(a) Parse boundary.** `parse_event: CdmEvent → Result<LifecycleEvent,
  ParseError>` at the CDM ingestion layer. The parsed value is a closed sum.
- **(b) Booleans-and-comments antipattern.** `event_type: str` with a
  switch that has a `default: log_warning(...)` branch. Type catch:
  exhaustive `match` on the closed enum; the compiler refuses to compile
  if a new case is added without handling.
- **(c) Closed enumeration.** This *is* the closed enumeration. Free strings
  are how the bug class enters.

### 2.4 ContractSpec (subsumed listed-instrument detail)

1. **Canonical name.** `ContractSpec`
2. **Definition.** The exchange contract specification refinement of
   `InstrumentReference.kind = ListedDerivative`. Houses MIC, contract
   month code, tick size, lot size, settlement convention, daily price
   limits, last trading day rule, settlement price methodology, eligible
   CCP set.
3. **Minimum field set.** `exchange: MIC`, `underlier: AssetRef`,
   `option_type: Option<OptionTypeEnum>`, `strike: Option<PositiveDecimal>`,
   `expiry: Date`, `multiplier: PositiveDecimal`, `tick_size: PositiveDecimal`,
   `lot_size: PositiveNat`, `eligible_ccps: NonEmptySet<CcpId>`,
   `settlement: SettlementType`, `last_trading_day_rule: LastTradingDayRule`.
4. **Identity.** Hash of the tuple `(exchange, underlier, option_type, strike,
   expiry)` per v10.3 §3.2; CME-ES vs ICE-ES are distinct.
5. **Provenance.** Exchange reference data feed (CME DataMine, ICE Connect,
   Eurex feed); versioned per exchange-published spec amendment.
6. **Temporal semantics.** Versioned append-only (rolls into ProductTerms
   via the InstrumentReference parse).
7. **Failure consequences.** Wrong tick size → all VM calculations off by
   a tick-rounding error; wrong lot size → settlement projection emits
   non-deliverable instructions (v10.3 §5.4 lot-size constraints).

- **(a) Parse boundary.** Within `parse_instrument_reference`. A
  `ContractSpec` is constructed only by the parser; any failed validation
  rejects the whole InstrumentReference.
- **(b) Antipattern catch.**
  - `tick_size: float = 0.01` with the comment "// per exchange convention."
    Type catch: `PositiveDecimal` (constructor enforces `> 0`); the field is
    required, not a default.
  - `eligible_ccps: List[str]` with comment "// at least one." Type catch:
    `NonEmptySet<CcpId>` — empty list is not constructible.
- **(c) Closed enumerations.**
  - `LastTradingDayRule = ThirdFriday | ThirdWednesday | LastBusinessDay |
    BespokeCalendar { ref: CalendarRef }`.

### 2.5 SmartContractRef

1. **Canonical name.** `SmartContractRef`
2. **Definition.** Pointer to the deterministic move-generator function
   bound to a unit at registration. The function signature is
   `(input, state, conditions) → Moves` per v10.3 §5.1.
3. **Minimum field set.** `module_id`, `function_name`, `version: SemVer`,
   `code_hash: Sha256`.
4. **Identity.** `(module_id, function_name, version)`.
5. **Provenance.** Compiled and signed; the registry maps version to
   `code_hash` and a Tier-2 product-kind mapping (v10.3 §3.3.2).
6. **Temporal semantics.** Versioned; a unit is bound to a specific version
   at registration, never re-bound (rebinding implies fresh `unit_id`).
7. **Failure consequences.** A code-hash mismatch on replay produces
   non-deterministic moves and breaks Property 6 (time travel).

- **(a) Parse boundary.** `link_smart_contract_ref` at unit registration —
  resolves the ref to a callable, verifies the hash, fails fast if the
  registry has been rebuilt without the version.
- **(b) Antipattern catch.** `pricing_model: str = "BSM_v3"`. Type catch:
  newtype with explicit `code_hash` carry; a function call site holds the
  resolved callable, not a name.
- **(c) Closed enumeration.** Not applicable (open extension by product team),
  but the *category* `ProductKind` to which a `SmartContractRef` binds is
  closed.

---

## §3 Identity / Party

### 3.1 LegalEntityIdentifier

1. **Canonical name.** `LegalEntityIdentifier` (LEI per ISO 17442).
2. **Definition.** The 20-character GLEIF-issued identifier of every legal
   counterparty referenced in CSA, ISDA Master, GMSLA, trade execution,
   regulatory report.
3. **Minimum field set.** `code: Lei20` (refined: 20 chars, MOD-97-10
   checksum), `status: LeiStatus`, `parent_lei: Option<LegalEntityIdentifier>`,
   `as_of: VersionedTimestamp`.
4. **Identity.** `code`.
5. **Provenance.** GLEIF concatenated file (CDF, daily); `as_of` is the
   GLEIF publish time.
6. **Temporal semantics.** Status-versioned. An LEI in `LAPSED` or `RETIRED`
   status at the trade-date check is a hard rejection for new trades; for
   existing positions the status is informational.
7. **Failure consequences.** EMIR Refit, MiFIR RTS 22, SFTR all require
   valid LEI on every report; an invalid LEI fails repository submission.

- **(a) Parse boundary.** `parse_lei: str → Result<Lei20, ParseError>` —
  enforces 20 characters and ISO 17442 checksum at ingest. The string never
  re-enters the system after parsing.
- **(b) Antipattern catch.** `lei: str` with a comment "// GLEIF check at
  report time." Type catch: refined `Lei20` rejects at parse; consumers
  cannot construct an invalid LEI.
- **(c) Closed enumeration.** `LeiStatus = ISSUED | LAPSED | PENDING_VALIDATION
  | RETIRED | MERGED | ANNULLED | DUPLICATE`. Free string is the GLEIF
  feed's default and the bug source.

### 3.2 BankIdentifierCode

1. **Canonical name.** `BankIdentifierCode` (BIC per ISO 9362).
2. **Definition.** The 8-or-11-character SWIFT BIC used to route ISO 20022
   messages (v10.3 §8.7).
3. **Minimum field set.** `code: Bic8or11`, `kind: BicKind` (`Connected |
   NonConnected`), `as_of: VersionedTimestamp`.
4. **Identity.** `code`.
5. **Provenance.** SWIFT BICDirectory, monthly snapshot.
6. **Temporal semantics.** Snapshot-versioned; routing decisions use the
   snapshot effective at message-emission time.
7. **Failure consequences.** Incorrect BIC → settlement instruction fails
   at the gateway; wrong-kind BIC → routing falls back to manual.

- **(a) Parse boundary.** `parse_bic: str → Result<Bic8or11, ParseError>`.
- **(b) Antipattern catch.** `bic: str` with downstream regex. Type catch:
  refined type at parse; downstream cannot construct invalid.
- **(c) Closed enumeration.** `BicKind = Connected | NonConnected`. Country
  codes within BIC are ISO 3166 (closed).

### 3.3 MarketIdentifierCode (MIC per ISO 10383) — already covered under 2.4 but stated here for taxonomic completeness; same parse and type discipline apply.

### 3.4 WalletId

1. **Canonical name.** `WalletId`
2. **Definition.** The internal identifier of a wallet (v10.3 §2.1).
   A wallet is the bearer of position state; per StatesHome §0, *the
   wallet has no economic state of its own* — only `WalletRegistry`
   metadata (KYC, permissions, audit cursor).
3. **Minimum field set.** `id: Uuid128`, `kind: WalletKind = Real { external_id:
   ExternalAccountId } | Virtual { contra_for: AgreementOrUnitRef } |
   Reference { book_id }`, `parent_book: Option<BookId>`.
4. **Identity.** `id`.
5. **Provenance.** Allocated by the `register_wallet` admin transaction;
   never reused.
6. **Temporal semantics.** Set-once; a wallet is closed (lifecycle stage
   `CLOSED`) but not deleted.
7. **Failure consequences.** Misrouted moves → conservation violation
   (caught at executor, hard error) or a quiet leak into a virtual contra
   (caught at reconciliation, late).

- **(a) Parse boundary.** `register_wallet` returns a `WalletId`; no other
  construction path exists.
- **(b) Antipattern catch.** `is_virtual: bool` with side-table for
  external mappings. Type catch: `WalletKind` sum carries the contra
  reference inside the `Virtual` constructor — a virtual wallet without a
  contra is unrepresentable.
- **(c) Closed enumeration.** `WalletKind` (sum), `WalletStatus = ACTIVE |
  FROZEN | CLOSED`.

### 3.5 PartyMetadata

1. **Canonical name.** `PartyMetadata`
2. **Definition.** The non-state, non-economic metadata of v10.3 §2 read
   through StatesHome's `WalletRegistry`: KYC status, permissions, audit
   cursor, regulatory classification, jurisdiction, counterparty rating.
3. **Minimum field set.** `lei`, `kyc_status: KycStatus`, `jurisdiction:
   Iso3166Alpha2`, `counterparty_classification: CdmPartyRole`,
   `permissions: Set<Permission>`, `audit_cursor: MoveStreamPosition`.
4. **Identity.** `lei` (canonical); secondary keys `wallet_id` per ledger
   instance.
5. **Provenance.** Onboarding system; updates carry a signed change record.
6. **Temporal semantics.** Mutable, append-history-of-versions. Per
   StatesHome: this is **not** state; it is sidecar metadata.
7. **Failure consequences.** Trade is admitted to a counterparty that has
   lapsed KYC; regulatory report carries the wrong classification; access
   control bypassed.

- **(a) Parse boundary.** `parse_party_metadata` at onboarding. Updates go
  through a `update_party_metadata` handler with capability check.
- **(b) Antipattern catch.** `permissions: List[str]`. Type catch:
  `Set<Permission>` with `Permission` a closed sum; a misspelled string is
  a compile error.
- **(c) Closed enumerations.** `KycStatus = NEW | INPROGRESS | APPROVED |
  EXPIRED | REJECTED`, `Iso3166Alpha2`, `CdmPartyRole` (CDM closed enum).

---

## §4 Legal / Agreement

### 4.1 CsaTerms

1. **Canonical name.** `CsaTerms`
2. **Definition.** Per v10.3 §6.4: the bilateral Credit Support Annex
   governing collateral on a counterparty pair. Per StatesHome, the CSA is
   itself a unit (`u_CSA`) issued by no one and held by both parties as a
   shared term sheet, but with the practical structure of a wallet-level
   smart contract.
3. **Minimum field set.** `parties: Pair<Lei20>`, `governing_law:
   GoverningLaw`, `regime: CollateralRegime`, `threshold: Decimal`,
   `mta: PositiveDecimal`, `independent_amount: Decimal`,
   `eligible_collateral: NonEmptyList<CollateralEligibility>`,
   `haircut_schedule: HaircutSchedule`, `valuation_currency: Iso4217Code`,
   `discount_rate_curve: CurveRef`, `notification_time: TimeOfDay`,
   `transfer_timing: TransferTiming`, `dispute_resolution: DisputeRule`.
4. **Identity.** Hash of `(parties, governing_law, signature_date,
   amendment_chain)`.
5. **Provenance.** Negotiated bilateral; signed; stored as PDF + structured
   extraction (CDM `CollateralProvisions`).
6. **Temporal semantics.** Versioned append-only; amendments are
   `TermsVersion` appends.
7. **Failure consequences.** Wrong threshold → margin call short by the
   threshold amount; wrong eligibility → posted collateral rejected at the
   custodian; wrong governing law → close-out netting unenforceable.

- **(a) Parse boundary.** `parse_csa: SignedAgreement → Result<CsaTerms,
  ParseError>` — extracts and validates against a CDM-aligned schema.
- **(b) Antipattern catch.**
  - `regime: str` with values `"title transfer"`, `"pledge"`, `"15c3-3"`.
    Type catch: `CollateralRegime = TitleTransfer { gmsla_schedule } |
    SecurityInterest { gmsla_schedule, rehyp_consent: bool } | UsRule15c3_3
    { customer_debit_cap }` — each variant carries its own required fields,
    eliminating "pledge with no rehyp_consent flag" as a representable state.
  - `mta: float` with comment "// must be positive." Type catch:
    `PositiveDecimal`.
  - `eligible_collateral: List[str]` with the comment "at least one."
    Type catch: `NonEmptyList`.
- **(c) Closed enumerations.** `CollateralRegime` (sum), `GoverningLaw`
  (closed enum: `EnglishLaw | NewYorkLaw | JapaneseLaw | …`),
  `TransferTiming = T0 | T1 | T2`.

### 4.2 GmslaSchedule

1. **Canonical name.** `GmslaSchedule`
2. **Definition.** The schedule to a GMSLA Master Agreement (v10.3 §15.7,
   referencing GMSLA 2010 vs 2018) — selects rehypothecation, default
   waterfall, manufactured payment basis.
3. **Minimum field set.** `master_version: GmslaVersion = V2000 | V2010 |
   V2018`, `rehyp_consent: bool` (only meaningful in `SecurityInterest`
   regime — but here genuinely a `bool` flag), `default_waterfall:
   WaterfallSpec`, `applicable_jurisdiction: Iso3166Alpha2`.
4. **Identity.** Hash of fields.
5. **Provenance.** ISLA Best Practice templates; per-counterparty negotiation.
6. **Temporal semantics.** Versioned append-only.
7. **Failure consequences.** Wrong default waterfall → close-out fails to
   apply correct loss attribution.

- **(a) Parse boundary.** `parse_gmsla_schedule`.
- **(b) Antipattern catch.** `master_version: str = "GMSLA 2010"`. Type
  catch: closed `GmslaVersion` enum, used as a discriminator on the
  schedule parser.
- **(c) Closed enumerations.** `GmslaVersion`, `WaterfallStep` (each step
  in the waterfall is a closed sum).

### 4.3 MandateTerms

1. **Canonical name.** `MandateTerms`
2. **Definition.** Per StatesHome §4.2: the mandate is itself a unit
   `u_MA`, with `ProductTerms[u_MA]` housing mandate text, fee schedule,
   benchmark identity, max position limits, HWM hurdle methodology,
   crystallisation frequency.
3. **Minimum field set.** `manager_lei`, `client_lei`, `benchmark_unit:
   UnitRef`, `fee_schedule: FeeSchedule`, `crystallisation: Crystallisation`,
   `hwm_methodology: HwmMethod`, `quantitative_constraints: List<MandateConstraint>`,
   `qualitative_constraints: List<QualitativeConstraint>`,
   `subscription_redemption: NavStrike`.
4. **Identity.** Hash of fields, included in the `unit_id` derivation for `u_MA`.
5. **Provenance.** Signed mandate document; extracted to CDM where possible.
6. **Temporal semantics.** Versioned append-only via `ProductTerms[u_MA]`.
7. **Failure consequences.** Wrong fee schedule → wrong crystallised
   performance fee at every reset; wrong constraint → trade admitted that
   should have been rejected (v10.3 §6.5).

- **(a) Parse boundary.** `parse_mandate`.
- **(b) Antipattern catch.**
  - `concentration_limit_pct: float = 0.1` with comment "10% per name."
    Type catch: `MandateConstraint = ConcentrationLimit { unit_kind,
    pct: Bounded01 } | LeverageCap { ratio: PositiveDecimal } |
    CurrencyExposureLimit { ccy, pct: Bounded01 } | …`. Constraints are a
    closed sum with each variant carrying its required fields.
  - `qualitative_notes: str`. Type catch: model `QualitativeConstraint`
    explicitly — even if its evaluator is human-in-the-loop, the field has
    a structured shape (e.g., `BestExecutionStandard | SuitabilityStandard
    | PrudentPersonStandard`).
- **(c) Closed enumeration.** `MandateConstraint` and
  `QualitativeConstraint` are closed sums.

### 4.4 IsdaMaster (sketched; same discipline)

Houses the ISDA Master Agreement structure, election schedule, additional
provisions. Identity: hash; versioning: append-only; failure consequence:
incorrect netting set boundary → wrong close-out value. Closed enums:
`MasterVersion = V1992 | V2002`, election variants.

---

## §5 Time / Calendar

### 5.1 Calendar

1. **Canonical name.** `Calendar`
2. **Definition.** Holiday calendar for a jurisdiction or financial centre
   (e.g., LON, NYC, TOK, TARGET). Used by every business-day adjustment.
3. **Minimum field set.** `id: CalendarId` (closed enum of recognised
   calendars — *not* a free string), `holidays: SortedSet<Date>`,
   `weekend_rule: WeekendRule`, `as_of: VersionedTimestamp`,
   `valid_from: Date`, `valid_through: Date`.
4. **Identity.** `(id, as_of)`.
5. **Provenance.** Vendor (Bloomberg CDR, Refinitiv); each ingest carries
   a hash.
6. **Temporal semantics.** **Two timestamps**: `as_of` is when this snapshot
   was published (knowledge time); `valid_from`/`valid_through` is the
   business-day domain it covers (effective time). Per v10.3 §8.4 dual-time
   discipline.
7. **Failure consequences.** Wrong calendar → coupon date mis-shifted →
   accrued interest off by one day → cash settlement off by the day's
   accrual → conservation holds, but value is wrong; post-hoc detection
   is the only catch.

- **(a) Parse boundary.** `parse_calendar` at vendor ingest. The parsed
  value is immutable; updates are new versions.
- **(b) Antipattern catch.** `is_holiday: dict[Date, bool]` with comment
  "covers 2020-2030, refresh by 2029." Type catch: refined `CalendarId`
  + explicit `valid_through`; lookup outside the valid range raises
  `OutOfRange`, not `KeyError default False`.
- **(c) Closed enumerations.** `CalendarId` (closed registry, ~200 entries),
  `WeekendRule = SatSun | FriSat | None`, `BusinessDayConvention` (closed,
  CDM).

### 5.2 KnowledgeTime / EffectiveTime pair (DualTimestamp)

1. **Canonical name.** `DualTimestamp`
2. **Definition.** Per v10.3 §8.4: every event carries two timestamps —
   `effective_time` (when the economic event happened) and `knowledge_time`
   (when the system learned about it).
3. **Minimum field set.** `effective: Timestamp`, `knowledge: Timestamp`,
   with invariant `knowledge ≥ effective`.
4. **Identity.** Per-event field; not stored separately.
5. **Provenance.** `effective` from the event source (CDM
   `BusinessEvent.effectiveDate`); `knowledge` from the executor at commit.
6. **Temporal semantics.** Both fields are immutable per event; replay-as-known-at-time
   `t` filters by `knowledge ≤ t`; replay-as-of-time `t` filters by
   `effective ≤ t`.
7. **Failure consequences.** A single-timestamp design conflates "what
   happened" with "when we learned about it" — every late-booked trade
   produces wrong historical PnL.

- **(a) Parse boundary.** Constructed at the event-ingestion adapter; the
  `DualTimestamp` constructor enforces `knowledge ≥ effective`.
- **(b) Antipattern catch.** `event_time: datetime` with comment "// is this
  trade time or booking time?" Type catch: refined struct rejects
  ambiguous use; consumers select `effective` or `knowledge` explicitly.
- **(c) Closed enumeration.** `ReplayMode = AsOfEffective | AsKnownAt | Now`
  (the read-side dual).

### 5.3 Cadence / StalenessThreshold

1. **Canonical name.** `Cadence`
2. **Definition.** Per valuation §5.2 and §6.7: per-instrument-class pricing
   cadence and the staleness multiplier that defines `Stale` FSM transition
   T8.
3. **Minimum field set.** `instrument_class: InstrumentClass`,
   `cadence: Duration`, `staleness_factor: PositiveRational`,
   `max_attempts: PositiveNat`.
4. **Identity.** `instrument_class`.
5. **Provenance.** Operations team config; versioned.
6. **Temporal semantics.** Versioned; current = latest.
7. **Failure consequences.** Wrong cadence → exotic option priced too
   slowly → risk pipeline reads stale APPROXIMATE prices for hours →
   margin calls on wrong values.

- **(a) Parse boundary.** Config-file parser at startup; reload via signal
  with version bump.
- **(b) Antipattern catch.** `cadence_ms: int = 30000` flat per-system.
  Type catch: per-class structure with `InstrumentClass` closed enum.
- **(c) Closed enumeration.** `InstrumentClass = EquitySpot | VanillaOption |
  ExoticOption | Irs | Bond | StructuredNote | Calibration | …`.

---

## §6 Market

### 6.1 RawQuote (Tier-1 of Market)

1. **Canonical name.** `RawQuote`
2. **Definition.** An external market observation: a price, rate, or
   tenor-indexed quote sourced from an exchange feed, vendor, or ECN.
   Per valuation §4: this is the raw input to the Kalman filter.
3. **Minimum field set.** `observable: ObservableRef`, `value: Decimal`,
   `bid: Option<Decimal>`, `ask: Option<Decimal>`, `as_of: DualTimestamp`,
   `source: SourceId`, `feed_seq: u64`, `quality: QuoteQuality`.
4. **Identity.** `(observable, source, as_of.knowledge, feed_seq)`.
5. **Provenance.** Exchange feed (FIX market data, ITCH), vendor (Bloomberg
   B-Pipe, Refinitiv Real-Time), ECN. Hash-anchored.
6. **Temporal semantics.** Append-only stream; superseded but never deleted.
7. **Failure consequences.** Stale quote treated as fresh → Kalman gates
   it through → calibrated curve drifts → every dependent price is wrong
   for one cycle.

- **(a) Parse boundary.** Feed adapter parses bytes into `RawQuote`;
  validates spread non-negativity, value within `(0, ∞)` for non-rate
  quantities, value within `(-∞, ∞)` for rates.
- **(b) Antipattern catch.**
  - `bid_ask_spread: Optional[float]` with comment "// negative means
    crossed." Type catch: refined `BidAsk = OneSided { side, value } |
    TwoSided { bid, ask, invariant: ask ≥ bid }`. Crossed quote is
    `Crossed { bid, ask }`, not silent corruption.
  - `quality: int = 0`. Type catch: closed `QuoteQuality = Live |
    Indicative | Closing | Synthetic`.
- **(c) Closed enumerations.** `QuoteQuality`, `SourceId` (closed registry of
  approved sources).

### 6.2 CalibratedCurve / CalibratedSurface

1. **Canonical name.** `CalibratedState` (parameterised: `CurveState`,
   `SurfaceState`, `HazardState`).
2. **Definition.** Per valuation §4: the Kalman filter posterior — a
   no-arbitrage-certified parameter vector for a yield curve, vol surface,
   credit hazard curve.
3. **Minimum field set.** `object_id: CalibratedObjectId`,
   `state_vector: Vector`, `covariance: Matrix`,
   `observation_window: ObservationWindow`,
   `arbitrage_certificate: ArbitrageCertificate`,
   `as_of: DualTimestamp`,
   `model_id: CalibrationModelId`,
   `kalman_innovation_stats: InnovationStats`.
4. **Identity.** `(object_id, model_id, as_of.knowledge)`.
5. **Provenance.** The Kalman calibration workflow (§4); innovation gating
   (§4.5) decides which observations entered.
6. **Temporal semantics.** Append-only; latest-as-of-knowledge-time is the
   read.
7. **Failure consequences.** Uncertified state used in pricing → arbitrage-
   admitting prices → PnL explain fails on dependents.

- **(a) Parse boundary.** Constructed only by `kalman_update`; the
  certificate must be present (refinement type `CalibratedState` requires
  `arbitrage_certificate.is_certified == true` — there is no path that
  yields an uncertified value with this type).
- **(b) Antipattern catch.**
  - `is_arbitrage_free: bool` with the comment "checked at calibration."
    Type catch: the `ArbitrageCertificate` is a witness type (it carries
    the constraints satisfied — `D_increasing | W_positive |
    NoCalendarSpread | …`). A `bool` discards the proof.
  - `state_vector: List[float]` with comment "Heston: 5 dim, BS: 1." Type
    catch: parametric `Vector<n>` or sum-typed `StateVector =
    BlackScholes { sigma } | Heston { v0, kappa, theta, xi, rho } | …`.
- **(c) Closed enumerations.** `CalibrationModelId` (closed registry),
  `CalibratedObjectKind = YieldCurve | VolSurface | CreditCurve | FxSurface |
  CorrelationMatrix`.

### 6.3 MarketDataSnapshot

1. **Canonical name.** `MarketDataSnapshot`
2. **Definition.** Per valuation §3: the immutable market context used by a
   single pricing invocation. The `market_data_snap` field on the
   ValuationRecord points here. Required for reproducibility (v10.3
   §7.7.2).
3. **Minimum field set.** `snapshot_id: SnapshotId`,
   `as_of: DualTimestamp`,
   `quotes: Map<ObservableRef, RawQuote>`,
   `calibrations: Map<CalibratedObjectId, CalibratedState>`,
   `fx_rates: Map<CcyPair, FxRate>`,
   `content_hash: Sha256`.
4. **Identity.** `snapshot_id` (deterministic from content hash).
5. **Provenance.** Captured at the entry to each pricing workflow; stored
   in the snapshot store.
6. **Temporal semantics.** Immutable; reproducibility key.
7. **Failure consequences.** Replay diverges from original; PnL explain
   compares apples to oranges.

- **(a) Parse boundary.** `seal_snapshot(quotes, calibrations) → SnapshotId`
  computes the hash and registers; consumers receive the id, not the
  mutable map.
- **(b) Antipattern catch.** Pricer reads from a global "current market"
  reference. Type catch: every pricer signature takes `&MarketDataSnapshot`
  explicitly; ambient global is unrepresentable.
- **(c) Closed enumeration.** Not applicable at this level (the components
  carry their own closed enums).

### 6.4 FxRate

1. **Canonical name.** `FxRate`
2. **Definition.** A spot FX rate between two ISO 4217 currencies at an
   observation time, used to denominate non-reference-currency quantities.
3. **Minimum field set.** `pair: CcyPair`, `rate: PositiveDecimal`,
   `as_of: DualTimestamp`, `source: SourceId`, `convention:
   FxQuoteConvention`.
4. **Identity.** `(pair, source, as_of.knowledge)`.
5. **Provenance.** Vendor (WMR fixings, ECB reference rates, Bloomberg).
6. **Temporal semantics.** Append-only stream.
7. **Failure consequences.** Wrong convention (BASE/QUOTE inverted) →
   FX trade conserves quantity but values are off by `rate^2`.

- **(a) Parse boundary.** `parse_fx_quote`.
- **(b) Antipattern catch.** `rate: float` with comment "EUR/USD = how many
  USD per EUR." Type catch: `CcyPair = CcyPair { base: Iso4217Code, quote:
  Iso4217Code }` with the rate constructor enforcing the convention.
- **(c) Closed enumeration.** `FxQuoteConvention = Quote_Per_Base | Base_Per_Quote`.

---

## §7 Oracle

I narrow the scope of *Oracle* to **externally-attested events** — assertions
by a trusted external party that something happened in the world. This is
*not* market data (which is observation, not attestation about a discrete
event), and not smart-contract execution (which is the framework's own
output). The valuation document's "Attestations" box (§4.7) sits here.

### 7.1 ExecutionReport

1. **Canonical name.** `ExecutionReport`
2. **Definition.** External attestation that a trade was executed (FIX 4.4
   ExecRpt, FpML message, exchange post-trade feed). Triggers the
   `OPEN`/`FORMATION` lifecycle event.
3. **Minimum field set.** `external_trade_id: ExternalTradeId`,
   `execution_venue: MIC`,
   `execution_timestamp: Timestamp` (with venue-attested microsecond
   resolution per MiFID II RTS 25),
   `parties: ExecutionParties`,
   `cdm_trade: CdmTrade`,
   `attesting_signature: Signature`,
   `received_at: Timestamp`.
4. **Identity.** `external_trade_id`.
5. **Provenance.** Exchange / SEF / OTF / ECN; signed by the venue's
   reporting system.
6. **Temporal semantics.** Append-only inbound stream; the `cdm_trade`
   carries its own effective time.
7. **Failure consequences.** Missed report → trade not booked → exposure
   not captured. Duplicate report → idempotency check prevents re-booking
   (Invariant 5).

- **(a) Parse boundary.** `parse_execution_report: VenueBytes → Result<
  ExecutionReport, ParseError>` at venue adapter; CDM synonym mapping
  applied here. The signature is verified at parse.
- **(b) Antipattern catch.**
  - `is_processed: bool` flag on the report. Type catch: idempotency lives
    on the executor side via `external_trade_id`; the report itself is an
    immutable inbound message.
  - `execution_timestamp: datetime = received_at`. Type catch: distinct
    fields with the invariant `received_at ≥ execution_timestamp` enforced
    at construction.
- **(c) Closed enumeration.** `ExecutionVenueKind = ExchangeMatched | OtcSef |
  Otf | Ecn | DealerVoice` (subset of MiFID II venue taxonomy).

### 7.2 SettlementConfirmation

1. **Canonical name.** `SettlementConfirmation`
2. **Definition.** External confirmation that a settlement instruction has
   completed (`sese.025` for securities, `camt.054` for cash).
   Per v10.3 §8.10: the confirmation triggers the
   `INSTRUCTED → SETTLED|FAILED` status transition.
3. **Minimum field set.** `instruction_ref: SettlementInstructionId`,
   `outcome: SettlementOutcome`,
   `settled_quantity: Decimal`,
   `settled_value: Decimal`,
   `csd_or_payment_system: SettlementSystemId`,
   `settlement_time: Timestamp`,
   `attesting_signature: Signature`.
4. **Identity.** `(instruction_ref, settlement_system_id)`.
5. **Provenance.** CSD (DTC, Euroclear, Clearstream), payment system
   (TARGET2, Fedwire, CHIPS).
6. **Temporal semantics.** Inbound stream; `settlement_time` is the CSD's
   posting time.
7. **Failure consequences.** Lost confirmation → ledger and custody drift
   undetected; misclassified outcome → wrong status, wrong CSDR penalty
   attribution.

- **(a) Parse boundary.** ISO 20022 schema validation + signature check at
  the gateway adapter.
- **(b) Antipattern catch.**
  - `outcome: str = "settled"`. Type catch: `SettlementOutcome = FullySettled
    { quantity } | PartiallySettled { quantity, residual } | Failed {
    reason: SettlementFailReason } | Cancelled { reason }`.
  - `partial_quantity: Optional[Decimal]` only meaningful when outcome ==
    "PartiallySettled" — comment-managed. Type catch: partial quantity
    lives inside the `PartiallySettled` constructor; constructor of
    `FullySettled` does not have the field.
- **(c) Closed enumerations.** `SettlementOutcome` (sum),
  `SettlementFailReason = LackOfSecurities | LackOfCash | InvalidInstruction
  | CounterpartyDispute | Other { code: IsdaFailReasonCode }`.

### 7.3 CorporateActionAnnouncement

1. **Canonical name.** `CorporateActionAnnouncement`
2. **Definition.** External attestation of a corporate action: dividend,
   split, merger, spin-off, rights issue. Carries the multi-date schedule
   per v10.3 §5.3 (announcement / record / ex / payment).
3. **Minimum field set.** `event_id: ExternalCaeId`,
   `kind: CorporateActionKind`,
   `subject: UnitRef`,
   `announcement_date: Date`,
   `record_date: Date`,
   `ex_date: Date`,
   `effective_date: Date`,
   `terms: CorporateActionTerms`,
   `source: CaeSourceId`,
   `attesting_signature: Signature`.
4. **Identity.** `event_id`.
5. **Provenance.** Issuer (via DTCC ISO 20022 CA messages), data vendor
   (Refinitiv, Bloomberg) — multi-source for cross-validation.
6. **Temporal semantics.** Each date is an explicit field; the lifecycle
   engine schedules timers per date.
7. **Failure consequences.** Missed record date → wrong entitlement
   snapshot; wrong ratio → split applied incorrectly to all holders.

- **(a) Parse boundary.** Multi-source ingest with reconciliation; the
  parser fails if sources disagree on the ratio or the dates beyond
  tolerance.
- **(b) Antipattern catch.**
  - `kind: str` with values `"DIV"`, `"SPLT"`, … Type catch:
    `CorporateActionKind = CashDividend { gross_per_share: PositiveDecimal,
    currency } | StockSplit { ratio_num, ratio_denom: PositiveNat } |
    Merger { acquirer: UnitRef, conversion: ConversionRule } | SpinOff {
    new_unit: UnitRef, distribution_ratio } | RightsIssue { … } | …`.
  - `terms: dict` with comment "varies by kind." Type catch:
    `CorporateActionTerms` is the same closed sum, with each variant
    carrying its required fields — a `StockSplit` has no
    `gross_per_share`, period.
- **(c) Closed enumeration.** `CorporateActionKind` (CDM-aligned closed sum).

### 7.4 DefaultDeclaration

1. **Canonical name.** `DefaultDeclaration`
2. **Definition.** External attestation that a counterparty has defaulted
   under the relevant master agreement (ISDA, GMSLA, GMRA), triggering
   close-out netting per the obligation taxonomy (v10.3 Table 14.7).
3. **Minimum field set.** `defaulting_party: Lei20`,
   `affected_agreements: List<AgreementRef>`,
   `event_kind: DefaultEventKind`,
   `declaration_time: Timestamp`,
   `notice_reference: NoticeRef`,
   `attesting_signature: Signature`.
4. **Identity.** `(defaulting_party, declaration_time)`.
5. **Provenance.** Trustee, ISDA Determinations Committee, court, central
   bank.
6. **Temporal semantics.** Single event; downstream obligations are
   triggered with their own deadlines.
7. **Failure consequences.** Late detection → continued exposure to a
   defaulted counterparty; wrong-kind classification → wrong close-out
   waterfall.

- **(a) Parse boundary.** Manual or feed-driven, with a mandatory dual-sign
  check at parse.
- **(b) Antipattern catch.** `is_defaulted: bool` per counterparty.
  Type catch: `DefaultDeclaration` is a first-class object; counterparty
  state is a derived projection over the declaration stream.
- **(c) Closed enumeration.** `DefaultEventKind = FailureToPay |
  Bankruptcy | RestructuringCreditEvent | ObligationDefault | … `
  (ISDA-aligned).

### 7.5 IndexLevel / BenchmarkObservation

(Brief — same discipline.) Per valuation §6 Pricing DAG: index publishers
attest official index levels (SX5E, SPX, NKY closes). Identity:
`(index, fixing_date, source)`. Provenance: index calculation agent.
Failure: wrong fixing → wrong settlement at exercise. Closed enum:
`FixingSource = Official | Pre-publication | Reuters | Bloomberg`.

---

## §8 Smart-contract execution

This category houses the framework's *output* — what smart contracts emit
and what the executor commits.

### 8.1 Move

1. **Canonical name.** `Move`
2. **Definition.** Per v10.3 §2.3: the indivisible primitive operation —
   transfer of a quantity of a unit from one wallet to another. Under GPM
   (§15), refined: a move modifies exactly one coordinate of one unit per
   entity (Single-Coordinate Move Principle).
3. **Minimum field set.** `source: WalletId`,
   `destination: WalletId`,
   `unit: UnitId`,
   `quantity: PositiveDecimal`,
   `coordinate: PositionCoordinate` (under GPM; under the scalar model,
   degenerates to `Own`),
   `effective_at: Timestamp`,
   `source_contract: SmartContractRef`,
   `metadata: MoveMetadata`.
4. **Identity.** Position in the move stream + transaction id.
5. **Provenance.** Emitted by a smart contract; committed by the executor.
6. **Temporal semantics.** Append-only.
7. **Failure consequences.** Misrouted move → conservation violation
   (caught) or wrong wallet (silent until reconciliation).

- **(a) Parse boundary.** `Move` is constructed only by the smart contract
  function; the executor checks the input is well-typed before applying.
- **(b) Antipattern catch.**
  - `quantity: Decimal` permitting negative values, with comment "negative
    = reverse direction." Type catch: `quantity: PositiveDecimal`; the
    direction is encoded in `(source, destination)`. Negative quantity is
    unrepresentable.
  - `coordinate: str = "own"`. Type catch: closed enum `PositionCoordinate
    = Own | OnLoan | Borr | CollPost | CollRecv | CollRehyp`.
- **(c) Closed enumeration.** `PositionCoordinate` (six values).

### 8.2 Transaction

1. **Canonical name.** `Transaction`
2. **Definition.** Per v10.3 §2.4: a finite collection of moves, possibly
   accompanied by unit registrations and state changes, that satisfies
   conservation atomically. Per StatesHome C3: atomic across `ProductTerms`
   / `UnitStatus` / `PositionState`.
3. **Minimum field set.**
   - `transaction_id: TxId`
   - `kind: TransactionKind`
   - `moves: NonEmptyList<Move>` *(unless kind is `Accounting`-only)*
   - `terms_delta: Option<TermsAmendment>`
   - `unit_status_delta: Map<UnitId, UnitStatusDelta>`
   - `position_state_delta: Map<(WalletId, UnitId), PositionStateDelta>`
   - `obligations_created: List<Obligation>`
   - `obligations_discharged: List<ObligationId>`
   - `cdm_payload: CdmBusinessEvent`
   - `effective_at: Timestamp`, `committed_at: Timestamp`
4. **Identity.** `transaction_id` (UUID; idempotency key per Invariant 5).
5. **Provenance.** Smart contract → executor → move stream.
6. **Temporal semantics.** Atomic commit; durable.
7. **Failure consequences.** Partial commit (a state map updated, moves
   not posted) is the worst possible bug — it breaks every invariant at
   once. C3 atomicity is a structural defence.

- **(a) Parse boundary.** Constructed by smart contract; the executor
  validates *and* converts to the durable form. No field updates after
  commit.
- **(b) Antipattern catch.**
  - `transaction_type: str`. Type catch: closed `TransactionKind = Settlement
    | Collateral | Lifecycle | Accounting | Correction { corrects: TxId }`.
  - `corrects: Optional[str]` — required iff kind == "Correction". Type
    catch: `corrects: TxId` lives inside the `Correction` constructor;
    the field cannot be present on other kinds and cannot be missing on
    `Correction`.
  - `cdm_payload: dict` with comment "stores the original CDM event."
    Type catch: `CdmBusinessEvent` is a parsed, structured value (per the
    pinned CDM version), not opaque JSON.
- **(c) Closed enumerations.** `TransactionKind`, `LifecycleIntent` inside
  `cdm_payload`, `CorrectionRationale`.

### 8.3 SettlementInstruction (Settlement-projection output, v10.3 §8.1)

Already specified per v10.3. Closed enum: `SettlementType = DvP | FOP |
CASH`. Sum-type catch: each constructor carries its required leg(s); a
`DvP` has both legs, `FOP` has only the securities leg, `CASH` has only
the cash leg — making "DvP without a cash leg" unrepresentable.

### 8.4 ValuationRecord (valuation §3)

Already specified. Closed enum: `Quality = FIRM | INDICATIVE | APPROXIMATE
| STALE | FAILED`; `ValuationFsmState` (8 states); `Greeks` is itself a
closed sum (BSOptionGreeks, HestonOptionGreeks, LocalVolGreeks, …)
parametric on `model_id`. Antipattern catch:
- `vega: float` for any model. Type catch: `vega` lives only inside the
  `BSOptionGreeks` constructor; consumers must match on the `Greeks` sum
  to access it.

### 8.5 ExplainResult (PnL explain, valuation §8)

1. **Canonical name.** `ExplainResult`
2. **Definition.** The output of `pnl_explain(prev, curr, market_moves,
   cashflows)` — drives FSM T5/T6.
3. **Minimum field set.** `status: ExplainStatus`,
   `total_pnl: Decimal`,
   `explained_components: ExplainedDecomposition`,
   `unexplained_residual: Decimal`,
   `tolerance_used: Decimal`,
   `prev_record: ValuationRecordId`,
   `curr_record: ValuationRecordId`.
4. **Identity.** `(prev_record, curr_record)`.
5. **Provenance.** PnL explain activity (Temporal).
6. **Temporal semantics.** One per pricing cycle.
7. **Failure consequences.** Status `Pass` on a wrong-input explain →
   bad price published; status `Fail` on a correct explain → unnecessary
   quarantine.

- **(a) Parse boundary.** Output of a pure function; not parsed from
  bytes.
- **(b) Antipattern catch.** `status: bool` (passed/failed). Type catch:
  closed `ExplainStatus = Pass | FailWithinTolerance |
  FailToleranceExceeded | ModelMismatch | InsufficientData`.
- **(c) Closed enumeration.** `ExplainStatus`.

---

## §9 State

Per StatesHome §0.3 — the three-map ruling. These are not data the framework
*ingests*, they are data the framework *manages*; but for any data spec,
they must be enumerated, because every external consumer (analytics, risk,
reporting) reads from them.

### 9.1 ProductTerms — already specified at 2.2 (this is a State map keyed by `UnitId` whose value type is the `ProductTerms` of 2.2). Storage discipline: append-only, registration-total, versioned.

### 9.2 UnitStatus

1. **Canonical name.** `UnitStatus`
2. **Definition.** Per StatesHome: shared, mutable, per-unit state. One
   value per registered unit. Houses `lifecycle_stage`,
   `last_settlement_price`, `last_settlement_date`, `current_weights`,
   `nav_index`, `triggered_barrier`, `superseded_by`.
3. **Minimum field set (kind-discriminated).**
   - `unit_id: UnitId`
   - `lifecycle_stage: LifecycleStage`
   - `kind_specific: UnitStatusKind` (sum on `ProductKind`)
   - `superseded_by: Option<UnitId>`
   - `as_of: DualTimestamp`
4. **Identity.** `unit_id`.
5. **Provenance.** Mutated by the executor only, on transactions whose
   handler is named for the field per StatesHome C11.
6. **Temporal semantics.** Mutable; registration-total (StatesHome C5).
7. **Failure consequences.** Lifecycle stage drift → trade admitted on a
   matured unit; superseded link broken → orphan position on the old `u`.

- **(a) Parse boundary.** `init_unit_status` at registration creates a
  default per the product-declared schema; further mutation only via
  handlers.
- **(b) Antipattern catch.**
  - `lifecycle_stage: str = "ACTIVE"`. Type catch: closed enum
    `LifecycleStage = Pending | Listed | Active | Matured | Terminated |
    Settled | Defaulted | Closed`.
  - `triggered_barrier: bool` for QIS-only field stored on every unit.
    Type catch: `kind_specific: UnitStatusKind` sum — `triggered_barrier`
    lives inside `QisStatus`, absent from `BondStatus`.
  - `current_weights: Optional[Dict]` with comment "QIS only." Type catch:
    inside `QisStatus`.
- **(c) Closed enumerations.** `LifecycleStage`, `UnitStatusKind`,
  `BarrierState = NotTriggered | Triggered { breach_event: EventRef }`.

### 9.3 PositionState

1. **Canonical name.** `PositionState`
2. **Definition.** Per StatesHome §0.2: per-`(WalletId, UnitId)` state. Houses
   `accumulated_cost`, `ccp_binding`, per-position OTC lifecycle,
   `entry_nav`, `hwm`, `accrued_{mgmt,perf}_fee`,
   `benchmark_nav_at_inception`, `mandate_breach_flags`.
3. **Minimum field set (kind-discriminated).**
   - `wallet_id: WalletId`
   - `unit_id: UnitId`
   - `accumulated_cost: Option<Decimal>` *(only when `ProductKind` is one
     for which it is meaningful)*
   - `kind_specific: PositionStateKind` (sum)
   - `as_of: DualTimestamp`
4. **Identity.** `(wallet_id, unit_id)`.
5. **Provenance.** Mutated only by the executor; field-level handler-tag
   per C11 (e.g., `accumulated_cost` ↔ `settle | trade`; `hwm` ↔
   `fee_crystallise`; `entry_nav` ↔ `subscribe`).
6. **Temporal semantics.** **Monotone carrier** (StatesHome C1): once
   created, never garbage-collected. Closed-out leaves a `zero` row.
   The accessor returns `Option<PositionState>`: `None` means *never
   held*, `Some(zero)` means *held once, currently flat*; both readings
   are load-bearing.
7. **Failure consequences.** Garbage-collected zero row → wash-sale
   lookback misses prior holding → tax reporting wrong; collapse of
   `None` and `Some(zero)` → entitlement on a record date is missed.

- **(a) Parse boundary.** Created by the executor on first touch; the
  accessor is `view.position_state(w, u) → Option<PositionState>`. No
  other path.
- **(b) Antipattern catch.**
  - `position_exists: bool` parallel to `position_value`. Type catch:
    `Option<PositionState>` collapses both into one type whose match is
    exhaustive.
  - `accumulated_cost: Decimal = 0` for instruments where it is meaningless.
    Type catch: lives inside the `FuturesPositionState` constructor, absent
    from `EquityPositionState`.
  - `hwm: Optional[Decimal]` with comment "for QIS holders." Type catch:
    inside `QisHolderState`.
- **(c) Closed enumerations.** `PositionStateKind` (sum across product kinds).

### 9.4 PositionVector (under GPM, v10.3 §15.2)

1. **Canonical name.** `PositionVector`
2. **Definition.** The six-coordinate vector in `ℝ^6`:
   `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)`. For
   non-lendable instruments, only `own` is non-zero (graceful degeneration).
3. **Minimum field set.** Six `Decimal` coordinates plus an
   `instrument_lendability: Lendability` discriminator.
4. **Identity.** `(WalletId, UnitId)` — same key as `PositionState`.
5. **Provenance.** Per-coordinate writes, one move per coordinate per
   transaction.
6. **Temporal semantics.** Monotone carrier.
7. **Failure consequences.** Coordinate confusion (writing to `own` when
   `onloan` was meant) → conservation holds locally but global
   reconciliation breaks.

- **(a) Parse boundary.** Coordinate writes are made by smart contract
  handlers; the move's `coordinate` field discriminates.
- **(b) Antipattern catch.**
  - `available: Decimal` stored alongside `own`. Type catch: `available`
    is computed `own − onloan + borr` on read, never stored. Two-source-of-
    truth bug eliminated.
  - `is_short: bool`. Type catch: `own < 0` *is* short; no separate flag.
- **(c) Closed enumerations.** `Lendability = Lendable | NotLendable`,
  `PositionCoordinate` (six values).

### 9.5 FsmState (valuation lifecycle FSM)

1. **Canonical name.** `ValuationFsmState`
2. **Definition.** The eight-state FSM: `Unpriced, Pricing, Priced,
   Explaining, Explained, Quarantined, Stale, Failed`.
3. **Minimum field set.** Tag + per-state guard data (e.g., `retry_count`
   on `Quarantined`, `staleness_deadline` on `Stale`).
4. **Identity.** Per-unit FSM state in the pricing workflow.
5. **Provenance.** Workflow-local; persisted via Temporal durable execution.
6. **Temporal semantics.** Mutable through declared transitions only.
7. **Failure consequences.** Skipping a transition → APPROXIMATE price
   published as FIRM (severe).

- **(a) Parse boundary.** `apply_transition(fsm, trigger) → Result<Fsm,
  FsmError>` is the only mutator; transitions are exhaustively enumerated
  per valuation §2.2 (T1–T12).
- **(b) Antipattern catch.** `fsm_state: str` switch. Type catch: closed sum
  with each variant carrying its required guard data.
- **(c) Closed enumeration.** Eight states.

### 9.6 FreshnessMap (valuation §6.4)

Per `PricingWorkflow`: `Map<DependencyRef, Option<FreshnessTimestamp>>`.
Antipattern: `is_fresh: bool` flag per dependency. Type catch: monotone
timestamps with a `Cadence`-driven freshness predicate.

---

## §10 Obligation

Per v10.3 §14.7: a first-class data category that is neither market nor
oracle nor (yet) execution output — an obligation registered atomically
with the event that creates it, tracked by the obligation workflow until
discharge or compensation.

### 10.1 Obligation

1. **Canonical name.** `Obligation`
2. **Definition.** The tuple `(id, type, source, t_d, D, κ)` per v10.3
   Definition 14.7.1, with state machine `Pending → Attempted → Discharged
   | Compensated | Defaulted`.
3. **Minimum field set.**
   - `id: ObligationId` (deterministic from source and type)
   - `kind: ObligationKind`
   - `source: ObligationSource = Unit { unit_id } | Agreement { agreement_ref }
     | Regulatory { regime, event_ref }`
   - `deadline: DualTimestamp` (effective + knowledge)
   - `discharge_predicate: DischargeRef`
   - `compensation_action: CompensationRef`
   - `state: ObligationState`
4. **Identity.** `id`.
5. **Provenance.** Created by the lifecycle handler that emitted the
   triggering event (StatesHome C2 ensures structural conservation;
   Obligation Completeness Principle 14.7.4.4 ensures the obligation is
   in the handler output).
6. **Temporal semantics.** Append-only state transitions; the obligation
   store is a view over the move stream filtered to obligation entries.
7. **Failure consequences.** Missed obligation → P21 (Liveness) violated
   silently; compensation action absent → manual recovery only.

- **(a) Parse boundary.** Constructed by the lifecycle handler;
  registered atomically in the same transaction as the triggering event.
- **(b) Antipattern catch.**
  - `is_satisfied: bool`. Type catch: `ObligationState = Pending | Attempted
    | Discharged | Compensated | Defaulted` (five terminal/non-terminal
    cases) — the boolean cannot encode the `Compensated` case at all.
  - `deadline: datetime`. Type catch: `DualTimestamp` per 5.2 — replay-as-
    of-effective vs replay-as-known-at preserve their meanings.
  - `compensation_action: Optional[Callable]` with the comment "if absent,
    raise default." Type catch: `compensation_action: CompensationRef` is
    required; the `kind` discriminator may carry `NoCompensation` as an
    explicit variant for `OptionExpiry` (auto-expire) per v10.3 Table.
- **(c) Closed enumeration.** `ObligationKind` (closed sum from v10.3
  Table 14.7.2.1: `BondCoupon | OptionExpiry | IrsReset | FuturesDailyVm |
  SblTermLoanReturn | SblRecallReturn | SblManufacturedDividend |
  SblCollateralSubstitution | CsaVmDelivery | CsaImDelivery |
  CollateralSubstitution | SblCollateralTopUp | CloseOutNetting |
  SftrReport | SlateReport | EmirReport | SettlementInstruction`),
  `ObligationState` (five values).

---

## §11 Cross-cutting refinement: invariants encoded in types

The seven mandatory fields above name the *what*; the Minsky discipline is
the *how*. Three invariants from v10.3 §11.2 and StatesHome C1–C12 are
load-bearing across every category and deserve type-level statement:

1. **Conservation by construction (Invariant 1, StatesHome C2).** The
   `Move` constructor takes `(source, destination, unit, quantity)` —
   *not* `(account, unit, signed_quantity)`. The dual-entry pattern is
   in the type. A handler that produces a list of moves can be type-tagged
   `ConservingMoves<n>` only if a per-event-class proof obligation is
   discharged at compile time (or, in dynamically typed implementations,
   discharged by an injected witness from the conservation oracle of C2).
2. **Atomicity (StatesHome C3).** A `Transaction` is the only commit unit.
   No path exists to "apply moves and then update state separately."
   The `apply_all` API takes a single `StateDelta` whose constructor
   enforces simultaneity across all three state maps.
3. **Field-level handler tagging (StatesHome C11).** Each
   `PositionStateField` is tagged `WrittenBy<Handler>`. A type-level
   capability makes mutation by any other handler a compile error; in
   dynamically typed implementations, the executor refuses the write.

These three invariants are cross-cutting; they apply to every item above.
A weak design lists them in a comment block at the top of the file. The
Minsky design names a refined type for every one of them and refuses to
compile around them.

---

## §12 Summary table

| # | Category | Item | Identity | Storage map | Closed enum highlight |
|---|----------|------|----------|-------------|------------------------|
| 1.1 | System Invariant | ReferenceCurrency | singleton | bootstrap | Iso4217Code |
| 1.2 | System Invariant | SystemId | UUID | bootstrap | LedgerKind sum |
| 1.3 | System Invariant | DecimalPrecisionPolicy | singleton | bootstrap | RoundingMode |
| 2.1 | Reference | InstrumentReference | hash | versioned append-only | InstrumentKind sum |
| 2.2 | Reference | ProductTerms | unit_id | StatesHome ProductTerms | ProductKind, AmendmentResult |
| 2.3 | Reference | LifecycleIntent | tag | CDM-pinned enum | EventIntentEnum |
| 2.4 | Reference | ContractSpec | hash | nested in 2.1 | LastTradingDayRule |
| 2.5 | Reference | SmartContractRef | (module, fn, ver) | code registry | ProductKind binding |
| 3.1 | Identity | LegalEntityIdentifier | code | GLEIF mirror | LeiStatus |
| 3.2 | Identity | BankIdentifierCode | code | SWIFT mirror | BicKind |
| 3.3 | Identity | MarketIdentifierCode | code | ISO 10383 | (referenced in 2.4) |
| 3.4 | Identity | WalletId | UUID | wallet registry | WalletKind sum, WalletStatus |
| 3.5 | Identity | PartyMetadata | LEI | wallet registry sidecar | KycStatus, CdmPartyRole |
| 4.1 | Legal | CsaTerms | hash | versioned append-only | CollateralRegime sum |
| 4.2 | Legal | GmslaSchedule | hash | versioned | GmslaVersion |
| 4.3 | Legal | MandateTerms | hash | inside ProductTerms[u_MA] | MandateConstraint sum |
| 4.4 | Legal | IsdaMaster | hash | versioned | MasterVersion |
| 5.1 | Time | Calendar | (id, as_of) | calendar registry | CalendarId, BusinessDayConvention |
| 5.2 | Time | DualTimestamp | per-event | (every event) | (refinement) |
| 5.3 | Time | Cadence | instrument_class | config | InstrumentClass |
| 6.1 | Market | RawQuote | (obs, src, t, seq) | append-only stream | QuoteQuality |
| 6.2 | Market | CalibratedState | (obj, model, t) | append-only | CalibrationModelId |
| 6.3 | Market | MarketDataSnapshot | content hash | snapshot store | (composite) |
| 6.4 | Market | FxRate | (pair, src, t) | stream | FxQuoteConvention |
| 7.1 | Oracle | ExecutionReport | external_trade_id | inbound stream | ExecutionVenueKind |
| 7.2 | Oracle | SettlementConfirmation | (instr, sys) | inbound stream | SettlementOutcome sum |
| 7.3 | Oracle | CorporateActionAnnouncement | event_id | inbound stream | CorporateActionKind sum |
| 7.4 | Oracle | DefaultDeclaration | (party, t) | inbound stream | DefaultEventKind |
| 7.5 | Oracle | IndexLevel | (idx, date, src) | stream | FixingSource |
| 8.1 | Execution | Move | stream pos | move stream | PositionCoordinate |
| 8.2 | Execution | Transaction | tx_id | move stream | TransactionKind sum |
| 8.3 | Execution | SettlementInstruction | tx_id | derived | SettlementType sum |
| 8.4 | Execution | ValuationRecord | (unit, t, model) | valuation store | Quality, FsmState |
| 8.5 | Execution | ExplainResult | (prev, curr) | derived | ExplainStatus |
| 9.1 | State | ProductTerms (map) | unit_id | StatesHome | (see 2.2) |
| 9.2 | State | UnitStatus (map) | unit_id | StatesHome | LifecycleStage, UnitStatusKind |
| 9.3 | State | PositionState (map) | (w, u) | StatesHome monotone | PositionStateKind |
| 9.4 | State | PositionVector | (w, u) | GPM | PositionCoordinate, Lendability |
| 9.5 | State | ValuationFsmState | per unit | workflow-local | 8 states |
| 9.6 | State | FreshnessMap | per workflow | workflow-local | (refinement) |
| 10.1 | Obligation | Obligation | obligation_id | obligation store (view) | ObligationKind, ObligationState |

**Count: 41 distinct items across 10 categories.**

**Floor coverage.** All six original floor categories covered, plus four
added (Identity, Legal, Time, State) and one renamed/narrowed (System
Invariant from Static). One subsumed (Listed-instrument detail folded into
Reference).

**Convergence with StatesHome.** Items 9.1–9.6 implement the 3-map ruling
verbatim; the Obligation category (10.1) is the v10.3 §14.7 first-class
object; ProductTerms versioning (2.2) and InstrumentReference versioning
(2.1) honour C6/C7/C8/C10.

**Open question.** Whether `Calendar` (5.1) should be parameterised by the
*subscriber's* applicable jurisdiction set or treated as a system-wide
union. The valuation FSM uses calendar lookups in cadence calculation;
the lifecycle engine uses them in coupon-date schedule generation. A
shared calendar with subscription gating is simpler; per-product
calendars are more accurate. I recommend the shared model with explicit
`Calendar` references on `ProductTerms`.
