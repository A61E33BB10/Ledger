# Phase 1 — Independent Data Enumeration (Jane Street CTO discipline)

**Source corpus.** `ledger_v10.3.tex`, `ledger_v10.3_addendum_stateshome.tex`,
`ledger_valuation_v1.0.tex`. Read end-to-end before writing.

**Reviewing posture.** Production code review. Pure functions first. Make
illegal states unrepresentable. Anti-over-engineering. The only abstractions
that survive are those that pay for themselves on day one against a concrete
claim already made by the framework — not against a plausible roadmap.

---

## 0. Floor-category critique (read this first)

Before enumerating, I challenge the six floor categories. They are not wrong,
but three of them are misnamed or overlap. I will keep the user's six as the
spine of the document, but I flag the issues here so that downstream phases
do not inherit the confusion.

| # | User name | Verdict | Problem |
|---|-----------|---------|---------|
| 1 | Static | **Rename.** Call it **ProductTerms**. | The framework already binds this name. "Static" is a tautology (everything in `ProductTerms[u]` is by definition static-or-versioned-append-only). The category is not "things that don't move", it is "the immutable, append-only versioned terms of a unit". Call it what it is. |
| 2 | Reference | **Keep, scope down.** | "Reference data" in the Ledger sense is exactly Tier-1 of the Unit Store: instrument master records, calendars, holiday tables, lot sizes. Anything else commonly bucketed under "reference data" (LEIs, CCP catalogues, party metadata) belongs in a **Party / Legal-Entity** sector that the framework currently lacks but needs (see additions §7). |
| 3 | Market | **Keep, but split conceptually.** | Two genuinely different things hide under one name: (a) raw observables — the ticks, quotes, fixings; (b) calibrated parameter vectors (curves, surfaces) that the Kalman filter produces from those observables. They have different update disciplines, different staleness semantics, and different consumers. Treat them as **3a Market.Observable** and **3b Market.Calibrated** in the enumeration below. |
| 4 | Oracle | **Subsumes 3a. Demote.** | An oracle is a *signed observation of an observable* — `(value, source, timestamp, signature)`. The signed envelope is the only thing that makes it an "oracle" rather than a "market value". The economically interesting payload is the same as Market.Observable. So Oracle is not a parallel category to Market; it is **the provenance discipline applied to Market.Observable** (and to a small set of non-market attestations: corporate-action declarations, settlement-price declarations, manufactured-dividend amounts). I keep it as a category, but I rename it **Attested observation** and explicitly state that Market.Observable is its dominant subclass. |
| 5 | Smart-contract execution | **Keep, but it is not "data".** | This is execution state, not data: `Move`, `Transaction`, `StateDelta`, FSM cursor, retry counter, idempotency key. It is what the Ledger and the Temporal layer write. It earns its sector because the spec already commits to event-sourcing — the move stream IS the source of truth (v10.3 §8). Without this category there is no audit trail. But naming it "execution data" would be more honest. |
| 6 | Listed-instrument detail | **Delete as a top-level floor.** | This is a redundant slice. Every field that distinguishes a listed instrument from an OTC one already lives in `ProductTerms[u]` (per the addendum's three-map ruling) — `clearinghouse`, `exchange`, `tick_size`, `lot_size`, `expiry`, `multiplier`, `cfi_code`. There is no "listed-instrument data" that is not Static/ProductTerms. Promoting it to a floor category creates a parallel hierarchy that re-introduces the per-unit/per-(w,u) split that C12 just collapsed. **Either fold it into category 1 (ProductTerms) as a tagged sub-schema for `unit_type ∈ {LISTED_DERIV, LISTED_EQUITY, BOND}`, or fold it into category 2 (Reference) as the Tier-1 instrument master. There is no third option that is not over-engineering.** I keep it in the enumeration only because the user asked, and I document explicitly which fields would relocate.

**Net.** The floor that survives critique is five categories, not six:
ProductTerms / Reference / Market (Observable + Calibrated) / Attested
observation / Execution. Listed-instrument detail is a sub-schema of
ProductTerms.

---

## 1. ProductTerms (renamed from "Static")

Sector key: `u` (UnitId). One `NonEmpty[TermsVersion]` per registered unit.
Per addendum C6/C7: registration-total, append-only, versioned.

### 1.1 ProductTerms — core record

1. **Canonical name.** `ProductTerms[u]`, current version
   `ProductTerms[u].current()` of type `TermsVersion`.
2. **Definition.** The immutable, append-only, versioned vector of contractual
   parameters that fix what unit `u` *is*. Every field is invariant under the
   product-declared `is_fungibility_preserving` predicate (C8). Any
   amendment that breaks fungibility allocates a fresh `u_new` and stamps
   `superseded_by` in `UnitStatus[u_old]`; it does NOT mutate `ProductTerms[u_old]`.
3. **Minimum field set.**
   - `unit_id : UnitId`
   - `unit_type : Enum{CASH, EQUITY, LISTED_DERIV, OTC_DERIV, BOND, STRUCTURED}`
   - `currency : Iso4217Code`
   - `terms : SumType` tagged on `unit_type` (the only place where instrument
     polymorphism is allowed to leak in — see §1.2)
   - `is_fungibility_preserving : (TermsAmendment) -> Preserving | Breaking`
     (C8; product-declared, total)
4. **Identity.** `unit_id` is a deterministic hash of the canonicalised
   `terms` for listed/cash/security units, or the CDM `Trade.metaData.key`
   (which already includes `Collateral`) for OTC units. v10.3 §3.3 already
   commits to deterministic injectivity. No surrogate keys. No re-derivation
   from "natural keys" at read time.
5. **Provenance.** Created by exactly one transaction: the registration
   transaction. C10 makes re-registration of the same `unit_id` a hard error.
   Tracked fields: `created_by : TxId`, `created_at : Timestamp`,
   `registered_via : Channel ∈ {CASH_INIT, REFDATA_FEED, OTC_EXEC}`.
6. **Temporal semantics.** `as_of(t).current()` returns the highest-versioned
   `TermsVersion` whose `effective_at <= t`. Past versions are reachable for
   audit / time travel. There is no notion of "future-dated terms" — an
   amendment with `effective_at > now()` is a *pending* event in the lifecycle
   workflow, not a row in `ProductTerms`.
7. **Failure consequences.** Missing `ProductTerms[u]` at trade time => the
   move references a unit that is not in `𝒰` => the executor rejects the
   transaction (v10.3 §3.6 referential-integrity invariant P3). This is the
   one failure mode that must be a hard reject, not a degraded-mode
   continuation. Anything else is a silent corruption of the universe.

   (a) **Delete.** Drop `is_fungibility_preserving` from the persisted record
   if and only if the framework allows the predicate to live in product code
   keyed by `unit_type` rather than per-unit. Reading 1034 of v10.3 and C8
   together, it does — the predicate is a property of the *product type*, not
   of each individual contract. Per-unit storage is over-engineering.
   (b) **Abstraction trap.** The temptation to give `terms` a shared abstract
   schema across all `unit_type`s. Resist. Use a sum type tagged on
   `unit_type` and let each variant be flat. Nothing is gained by a "common
   field set" except a strictly larger surface area for nullable misuse.
   (c) **Simplest ingest pattern.** A single `register(u, terms, defaults)`
   function that fails closed: validate `terms` against the type schema,
   compute `unit_id`, reject if `unit_id` already in `PT`, write atomically.
   No two-phase commit. No "draft" status. C10 + C7.

### 1.2 ProductTerms — tagged sub-schemas (this is where "Listed-instrument detail" lives)

The listed-instrument fields the user listed as a separate floor are *exactly*
the `unit_type=LISTED_DERIV` and `unit_type=LISTED_EQUITY` variants of
`ProductTerms[u].terms`:

| variant | fields | source |
|---------|--------|--------|
| `CASH` | `{}` (currency is on the parent record) | system init |
| `LISTED_EQUITY` | `isin, exchange_mic, board_lot_size, tick_size, voting_rights, country_of_listing` | reference data feed |
| `LISTED_DERIV` | `exchange_mic, ccp_id, underlier_unit_id, contract_type ∈ {FUT, OPT_CALL, OPT_PUT}, strike?, expiry, multiplier, settlement_style ∈ {CASH, PHYSICAL}, last_trading_day, first_notice_day?, delivery_month?` | exchange contract spec |
| `OTC_DERIV` | `cdm_trade_ref` (full CDM Trade incl. Collateral) | trade execution |
| `BOND` | `isin, issuer_lei, coupon_rate, coupon_freq, day_count_convention, maturity_date, face_value, seniority, callable_schedule?` | reference data feed |
| `STRUCTURED` | `isin, issuer_lei, payoff_program_ref, payoff_params, embedded_unit_refs : list[UnitId], maturity_date` | issuance feed |

(a) **Delete.** Drop `voting_rights`, `country_of_listing`, `seniority`,
`first_notice_day`, `delivery_month`, `callable_schedule` from the *minimum*
field set unless an existing claim in v10.3 or the valuation companion uses
them. The framework as written does not. They are reporting / regulatory
enrichment data — they belong in a Party/Legal sector that the spec has not
yet defined (§7), not in the per-unit minimum.
(b) **Abstraction trap.** "InstrumentMaster" as a unified row across all
listed types. This is exactly the Tier-1 trap the addendum already warns
against: forcing a flat schema across heterogeneous instruments produces a
table that is mostly null and validates nothing.
(c) **Simplest ingest.** One adapter per upstream feed
(`ExchangeRefdataAdapter`, `IsinSecurityMasterAdapter`, `OtcConfirmAdapter`),
each returning a typed `terms` variant. The adapters are the only impure
edge; the registration function consumes typed values.

---

## 2. Reference (Tier-1, scoped down)

Sector key: by entity, not by unit. This is the data that *exists in the
world* independent of any position the firm has.

### 2.1 Reference — instrument master

1. **Canonical name.** `InstrumentMaster[isin] : InstrumentRecord` (and
   parallel registries keyed by `(exchange_mic, contract_id)` for listed
   derivatives).
2. **Definition.** The vendor- or exchange-published catalogue of instruments
   that exist, regardless of whether the firm holds them. This is the
   *source* from which `ProductTerms` is constructed; it is not the same
   thing. v10.3 §3.5 makes this explicit: the Ledger consumes reference
   data, it does not author it.
3. **Minimum field set.** Same fields as the `ProductTerms.terms` variant for
   that instrument class, plus a `vendor_record_version` and `vendor_id`. The
   *firm-specific* fields (`unit_id`, smart-contract binding) belong to
   `ProductTerms`, not here.
4. **Identity.** `(vendor_id, vendor_record_id)` or `isin` where the vendor
   guarantees ISIN as primary key. ISIN alone is *not* sufficient when
   multiple vendors disagree (corporate actions in flight, preferred shares,
   re-issued bonds). Carry the vendor key.
5. **Provenance.** Vendor feed (Bloomberg BSYM, Refinitiv RIC, exchange
   contract specs, CSD records). Each row is `(received_at, source, payload,
   feed_seq_no)`.
6. **Temporal semantics.** Bi-temporal: `valid_time` (when the vendor says
   the data was effective) ≠ `system_time` (when we received it). Both
   axes are required. Corrections are *new rows* with the same
   `valid_time` and a later `system_time`. Never overwrite.
7. **Failure consequences.** A missing reference record at unit-registration
   time => `register()` fails closed for that instrument => no position can
   be taken => P&L pipeline shows `UNKNOWN` rather than mis-priced. This is
   the correct failure mode. **Silent fallback to a stale ref-data record is
   the cardinal sin of this category** — it produces wrong economics, not
   missing economics, and wrong is far worse than missing.

   (a) **Delete.** Anything that is purely descriptive narrative
   (`security_short_name`, `description`, `industry_classification`,
   `gics_sector`). These are display attributes, not economics. Keep them in
   a separate display-metadata table that the trading core does not depend on.
   (b) **Abstraction trap.** A "universal symbology service" that maps every
   identifier (ISIN/CUSIP/SEDOL/RIC/BBG/FIGI) to a canonical key. You will
   build it. Do not. The mapping problem is irreducibly messy and any
   service that pretends otherwise hides bugs. Store the vendor keys you
   actually receive; reject anything else; let the OMS adapter handle
   external translation.
   (c) **Simplest ingest.** Bi-temporal append-only `InstrumentMaster` table
   keyed by `(vendor_id, vendor_record_id, valid_from, system_time)`. Pure
   function `as_of(vendor_id, key, t_valid, t_system) -> Option[Record]`.
   No upserts. No mutable rows.

### 2.2 Reference — calendars and conventions

1. **Canonical name.** `BusinessCalendar[mic_or_currency] : Set[Date]`,
   `DayCountConvention : Enum`, `BusinessDayConvention : Enum`.
2. **Definition.** The non-trading days, day-count rules (ACT/360, 30/360,
   etc.), and roll conventions referenced by every coupon, reset, and expiry
   computation in §5 and §6 of v10.3.
3. **Minimum field set.**
   `calendar_id, holiday_date, source, valid_from, system_time`. Day-count
   conventions are a closed enum; they live in code, not data.
4. **Identity.** `calendar_id` (e.g., `MIC:XNYS`, `CCY:USD`).
5. **Provenance.** Exchange / clearinghouse / central-bank publication.
6. **Temporal semantics.** Bi-temporal. **Future holidays are routinely
   announced and revised** — a holiday added six months in advance must not
   change yesterday's accrual. `as_of(calendar_id, t_valid, t_system)`.
7. **Failure consequences.** Missing calendar => coupon date computation
   uses the wrong roll => coupon paid on the wrong date => settlement fail.
   Hard fail at unit registration if the referenced calendar is not present.

   (a) **Delete.** Nothing. This record is already minimal.
   (b) **Abstraction trap.** A `Calendar` class with methods like
   `next_business_day()` that close over a vendor-provided holiday list at
   construction time. This is impure (the list changes). Pass the calendar
   value into every pure function that needs it.
   (c) **Simplest ingest.** Bi-temporal table; pure functions
   `is_business_day(cal, date) -> bool`,
   `roll(cal, date, convention) -> Date`. Both are deterministic on
   `(cal_snapshot, date)`. The calendar snapshot is captured at lifecycle
   execution time per v10.3 §7.7 (deterministic oracle requirement).

### 2.3 Reference — Party / Legal Entity

1. **Canonical name.** `PartyRegistry[lei] : PartyRecord`. (Currently absent
   from v10.3 as a first-class sector — see additions §7.)
2. **Definition.** The legal entities that can be wallet-holders or unit
   issuers/counterparties: their LEI, jurisdiction, regulatory
   classification (FC/NFC under EMIR, dealer/end-user, etc.), and KYC
   anchor.
3. **Minimum field set.**
   `lei, legal_name, jurisdiction, lei_status, lei_next_renewal,
   parent_lei?, immediate_parent_lei?`.
4. **Identity.** LEI (ISO 17442). For entities without an LEI, the firm's
   internal counterparty ID — but flagged so that any externally-reportable
   trade against that ID fails closed.
5. **Provenance.** GLEIF Level 1 / Level 2 feeds. Bi-temporal as above.
6. **Temporal semantics.** Bi-temporal. LEIs lapse and renew; corporate
   parents change; entity status changes. All historical states must be
   reconstructible.
7. **Failure consequences.** Lapsed-LEI counterparty in an
   externally-reportable trade => regulatory reporting blocked => pre-trade
   gate. Missing LEI => trade blocked from execution against
   externally-reportable products. Wallet KYC gating per addendum
   `WalletRegistry`.

   (a) **Delete.** Address fields, contact information, "industry
   sector" narrative. Move to a separate KYC-detail store outside the
   trading-core read path.
   (b) **Abstraction trap.** Conflating `WalletRegistry` (per-wallet KYC,
   permissions, audit cursor) with `PartyRegistry` (per-legal-entity facts).
   One wallet ↔ one party in the simple case, but funds-of-funds, omnibus,
   and SMA structures break that 1:1. Keep them separate; relate them by
   foreign key.
   (c) **Simplest ingest.** GLEIF nightly drop, append-only bi-temporal load.
   `as_of(lei, t_valid, t_system) -> Option[PartyRecord]`.

---

## 3. Market

I split this into 3a (raw observables) and 3b (calibrated parameters)
because they have different lifetimes, different consumers, and different
failure modes.

### 3a. Market.Observable — raw quotes, ticks, fixings

1. **Canonical name.** `Observation[(symbol, observable_type, t)] :
   ObservedValue`.
2. **Definition.** A single timestamped numeric observation of a market
   variable: a top-of-book tick, an exchange settlement price, an official
   IBOR/SOFR fixing, a closing auction print, an FX rate snap. The atomic
   input to the Kalman filter (`y_t` in valuation companion §6).
3. **Minimum field set.**
   `symbol, observable_type ∈ {LAST, BID, ASK, OFFICIAL_SETTLE, FIXING,
   AUCTION_CLOSE, MARK}, value : Decimal, currency_or_unit, exchange_or_publisher,
   observation_time, ingest_time, source_id`.
4. **Identity.** `(source_id, sequence_number)` from the upstream feed. Do
   not derive identity from `(symbol, time)` — duplicate ticks with
   identical timestamps are common and you must keep them.
5. **Provenance.** Wire-protocol from market data feed handlers.
   `source_id` carries the feed; `ingest_time` is the firm's clock; an
   optional `signature` lifts an `Observation` into the Attested-observation
   sector (§4).
6. **Temporal semantics.** Single-axis event time (`observation_time`).
   Late ticks (out-of-order arrival) are common; reorder by
   `observation_time`, retain `ingest_time` as a separate field. There is no
   such thing as "correcting" a tick — a vendor correction is a *new*
   `Observation` with a later `ingest_time` and an `is_correction` flag,
   not an edit.
7. **Failure consequences.** Single missing or wrong tick => Kalman filter
   innovation gating (§6.5 of valuation companion) flags it; feed handler
   buffer underflow => calibration node falls back to last certified
   state with `STALE` flag => downstream pricing transitions FSM into
   `Stale`. **The framework's claim that all of this is mechanical depends
   on observations never being silently overwritten.** Any system that lets
   a tick replace another tick at the same `(symbol, time)` breaks replay.

   (a) **Delete.** Per-tick `display_format`, `lot_size_at_quote`, exchange
   condition codes that the Kalman observation model does not use. They
   bloat storage with zero economic content. Keep raw if compliance requires
   it, but in a separate cold archive — not on the read path.
   (b) **Abstraction trap.** A unified `Quote` class that mixes top-of-book,
   official prints, and fixings. They have utterly different semantics: a
   top-of-book tick is one of millions per second; an official settlement
   price is one per contract per day and is *load-bearing for futures
   variation margin*. Keep them as distinct `observable_type` enum values
   and route them to different storage tiers.
   (c) **Simplest ingest.** Append-only by `ingest_time`. Replay-determinism
   requires that the snapshot consumed by any pure lifecycle invocation be
   pinned to a `(source_id, sequence_number)` cursor — captured at
   invocation time per v10.3 §7.7. No pull-on-demand from a live feed.

### 3b. Market.Calibrated — curves, surfaces, parameter vectors

1. **Canonical name.** `Calibration[curve_id, t] : CertifiedState`.
2. **Definition.** The Kalman-filter posterior `x_{t|t}^{certified}` for a
   yield curve, vol surface, credit curve, or correlation matrix, after
   no-arbitrage projection. Valuation companion §6.6.
3. **Minimum field set.**
   `curve_id, calibration_time, parameter_vector : Vec[Decimal],
   covariance : Matrix[Decimal], innovation_chi2, certified : bool,
   inputs_cursor : (Set[(source_id, sequence_number)] | hash),
   model_id, calibration_engine_version`.
4. **Identity.** `(curve_id, calibration_time, calibration_engine_version)`.
5. **Provenance.** Kalman filter activity in the calibration workflow,
   consuming a frozen snapshot of `Observation` rows pinned by
   `inputs_cursor`. The cursor is what makes calibration *reproducible* —
   without it the `(model + observations) -> calibration` arrow is not a
   pure function, and the entire valuation companion's claim of
   determinism collapses.
6. **Temporal semantics.** Single axis: `calibration_time`. The
   calibrations themselves are append-only; corrections are re-runs against
   a corrected `Observation` set, producing a new row with later
   `calibration_time` and a back-reference to the original. Never edit.
7. **Failure consequences.** Innovation-gate rejection => calibration
   marked uncertified => DAG leaf signals `STALE` => downstream units
   transition to `Stale` per FSM T8. No-arbitrage projection failure =>
   reject the calibration => fall back to last certified state. **Silent
   acceptance of an arbitrageable surface is the cardinal sin** — it puts
   negative density in butterfly positions and produces "free money" in
   PnL explain that is actually a calibration bug.

   (a) **Delete.** Drop full per-step Kalman gain / innovation history from
   the persisted record; keep only `innovation_chi2` and a
   `kalman_run_log_ref` pointing to a separate diagnostic store. Storing
   covariance matrices is the minimum; storing every intermediate
   `(K_t, S_t, ν_t)` is over-engineering for the read path.
   (b) **Abstraction trap.** A unified `Curve` interface that hides whether
   the parameter vector is a yield curve, a vol surface kernel-coefficient
   vector, or a credit hazard curve. The Jacobian dimension and the
   no-arbitrage region differ by category; force the type system to track
   the distinction.
   (c) **Simplest ingest.** One Temporal workflow per `curve_id` (per
   valuation companion §11.3), writing append-only rows. Pure
   `kalman_step(prev_state, observations) -> next_state`. The workflow is
   the only impure container; the math is a fold.

---

## 4. Attested observation (renamed from "Oracle")

I argue this is not a parallel category to Market but the **provenance
discipline** applied to a small set of inputs. v10.3 §10.3 already makes
this point ("Mapping Layer as Oracle Interface": external messages are
oracle outputs).

1. **Canonical name.** `Attestation[(observable_id, t)] : Attested`.
2. **Definition.** A signed envelope around an external claim that the
   Ledger relies on for a *deterministic lifecycle decision*. The dominant
   subclass is `Market.Observable` for assets where price formation is
   external (almost everything). The minority but load-bearing subclass is
   non-market attestations: corporate-action declarations, official
   exchange settlement prices for variation margin, manufactured-dividend
   amounts in SBL, fixing pages for IBOR-replacement rates, knock-out /
   knock-in barrier confirmations.
3. **Minimum field set.**
   `observable_id, value, observed_at, source_id, source_pubkey,
   signature, ingest_time, attestation_chain_ref?`.
4. **Identity.** `(source_id, observable_id, observed_at, signature)`.
5. **Provenance.** Issuer / exchange / vendor signs; the Ledger verifies on
   ingest and persists the envelope. The signature is what makes this an
   *attestation* rather than a *quote*: it is non-repudiable evidence.
6. **Temporal semantics.** Single-axis `observed_at`. A re-statement is a
   new attestation that supersedes the old one by `observed_at`; the old
   one is retained for audit (P3 of §11.5 — replay must be deterministic).
7. **Failure consequences.** Signature-verification failure => reject; do
   not promote to `Observation`. Missing attestation for a
   *settlement-required* observable (e.g., end-of-day futures settle price
   on the day of variation margin) => the futures lifecycle workflow blocks,
   raising an obligation per v10.3 §14.7. **This must be a hard block, not
   a fallback to a screen-scraped value.** The settlement price is the
   contract.

   (a) **Delete.** For market-data quotes that are *not* used for a
   deterministic lifecycle decision (intraday ticks consumed only by
   approximate pricing), drop the signature requirement entirely. The
   attestation envelope earns its place only where the Ledger's behaviour
   depends on the value being non-repudiable. Otherwise it is friction.
   (b) **Abstraction trap.** A "universal Oracle service" that signs
   everything. The signing surface should be exactly the set of inputs to
   *deterministic lifecycle events* — settlement prices, fixings,
   corporate-action terms, barrier confirmations, dividend amounts. Every
   additional signed channel is a new key-management problem.
   (c) **Simplest ingest.** Per source: verify signature on receipt;
   reject-or-store. The verifier is a pure function
   `verify(envelope, pubkey) -> bool`. Persisted records are immutable.

---

## 5. Execution (renamed from "Smart-contract execution")

This is what the Ledger writes. It is the source of truth (v10.3 §8.1).

### 5.1 Move

1. **Canonical name.** `Move`.
2. **Definition.** v10.3 Definition 2.2: an atomic transfer of one
   `(unit, quantity)` from `src` to `dst` within a transaction.
3. **Minimum field set.**
   `from_wallet, to_wallet, unit_id, quantity : PositiveDecimal,
   timestamp, source_ref, metadata_tag`. Generalised position model adds
   `coordinate ∈ {own, onloan, coll_post, coll_recv, ...}` per §16.2.
4. **Identity.** `(transaction_id, move_index_within_tx)`.
5. **Provenance.** Emitted by exactly one smart-contract invocation
   `Contract(input, state, conditions) -> {Moves}` (v10.3 §5).
6. **Temporal semantics.** Single-axis `timestamp` = transaction commit
   time. Moves are never edited. Corrections are *new transactions* with
   reverse moves, per §8.1.
7. **Failure consequences.** Conservation violation
   `Σ_w Δq(u) ≠ 0` for any unit `u` referenced in the transaction =>
   reject the entire transaction (atomicity). C2 of the addendum is the
   structural prevention: handlers produce zero-sum `StateDelta`s by
   construction; conservation is checked at commit. **Silent acceptance of
   a non-conserving transaction is the death of the framework.** Every
   downstream property collapses.

   (a) **Delete.** Free-text `metadata` fields. Replace with a closed
   `metadata_tag : Enum` whose values are exactly the lifecycle event
   classes the framework already enumerates (PUT_PREMIUM, PUT_SETTLEMENT,
   IRS_NET_PAYMENT, COUPON, DIVIDEND_CASH, etc.). Free text is
   un-testable, un-replayable, and a magnet for one-off hacks.
   (b) **Abstraction trap.** A `Move` base class with virtual
   `apply(ledger)` methods, varying by subtype. Wrong direction. The Move
   is data; the *handler* (the smart contract) is behaviour. Keep the data
   inert and dispatch behaviour from the contract registry.
   (c) **Simplest ingest.** Append-only event log. `apply_move` is a pure
   function `(BalanceMap, Move) -> BalanceMap`. Replay is a fold. v10.3
   §11.5 P3.

### 5.2 Transaction

1. **Canonical name.** `Transaction`.
2. **Definition.** A list of `Move`s plus a closed-set classification (Trade,
   SettleVM, CorporateAction, MandateAmend, QISRebalance) with a
   conservation proof obligation per class (C2).
3. **Minimum field set.**
   `transaction_id, transaction_class, moves : List[Move], invoking_event_id,
   contract_ref, committed_at, idempotency_key`.
4. **Identity.** `transaction_id` (UUIDv7 or hash of payload + invoking
   event id; the latter is what enables idempotency).
5. **Provenance.** A single smart-contract activity invocation in the
   Temporal layer (v10.3 §14.5). The `invoking_event_id` chains it to the
   triggering lifecycle event or external trade message.
6. **Temporal semantics.** Single axis: `committed_at`. Atomic.
7. **Failure consequences.** Partial commit is impossible by construction
   (C3). Idempotency-key collision => the second attempt is a no-op
   (Invariant 5).

   (a) **Delete.** "User-defined attributes" map. If the framework needs a
   field, add it to the schema; if it doesn't, the field has no business
   in the trading core.
   (b) **Abstraction trap.** Nested transactions. Forbidden. Saga
   patterns (v10.3 §14.10) compose multiple atomic transactions through
   compensation, not nesting.
   (c) **Simplest ingest.** Single-writer per (wallet, unit) lattice
   (v10.3 §14.16). The Temporal workflow is the writer; nothing else.

### 5.3 PositionState row

Already defined in addendum §2 as one of the three maps. Restated here as
a data category for completeness:

1. **Canonical name.** `PositionState[(w, u)]`.
2. **Definition.** Per-position economic state (accumulated_cost, hwm,
   entry_nav, ccp_binding, accrued_fees, ...).
3. **Minimum field set.** Per-field; addendum C11 names the unique writing
   handler for each field. **The minimum is the closed set of fields named
   in the addendum's longtable §2.1, no more.**
4. **Identity.** `(WalletId, UnitId)`.
5. **Provenance.** Each field has exactly one mutating handler (C11).
6. **Temporal semantics.** Monotone carrier: rows are never garbage-collected,
   close-out leaves a `Some(zero)` row. `Option` accessor distinguishes
   "never held" from "held and flat" (C1).
7. **Failure consequences.** Cross-handler write to a field => type error
   (C11). Mutation of the carrier such that an existing key disappears =>
   replay-determinism violation (P3).

   (a) **Delete.** Anything that is *derivable* from the move stream on
   demand: `first_touch_date`, `last_trade_date`, `total_traded_quantity`,
   `realised_pnl_to_date`. These are folds, not state. The addendum
   already calls this out for `first_touch_date`. Be ruthless.
   (b) **Abstraction trap.** A "PositionAggregator" class that caches
   derived fields. The cache will go stale, and stale-cache bugs are
   indistinguishable from real economic differences in PnL. If you need
   the fold result fast, materialise it in a separate read model with
   explicit invalidation, never in `PositionState` itself.
   (c) **Simplest ingest.** Apply `StateDelta` per addendum §3.1. Pure
   function. Replay = fold.

### 5.4 UnitStatus

1. **Canonical name.** `UnitStatus[u]`.
2. **Definition.** Per-unit shared mutable state visible to every holder:
   `lifecycle_stage`, `last_settlement_price`, `last_settlement_date`,
   `current_weights` (QIS), `nav_index`, `triggered_barrier`,
   `superseded_by`.
3. **Minimum field set.** Closed by C5 (registration-total) and the
   addendum's longtable.
4. **Identity.** `UnitId`.
5. **Provenance.** Initialised at registration with
   product-declared defaults (C5); mutated by a single canonical handler per
   field (C11).
6. **Temporal semantics.** Mutable, but all mutations are `StateDelta`
   commits — point-in-time queries reconstruct historical `UnitStatus[u]`
   from the move/event stream by fold (v10.3 §4.2).
7. **Failure consequences.** Registration-totality violation (`UnitStatus[u]`
   missing for a registered `u`) => view function partial => downstream
   readers crash. C5 is what prevents this.

   (a), (b), (c) — same disciplines as PositionState.

### 5.5 Lifecycle FSM cursor (per unit)

1. **Canonical name.** `LifecycleFSM[u] : LifecycleStage`.
2. **Definition.** Per-unit coarse stage from v10.3 §3.4
   (`PENDING | ACTIVE | MATURED | TERMINATED | SETTLED`). Note this is the
   *contractual* lifecycle (units in `𝒰`); the *valuation* lifecycle FSM
   (`Unpriced | Pricing | Priced | Explaining | Explained | Quarantined |
   Stale | Failed`) is a separate, parallel FSM tracked in the valuation
   companion §3.
3. **Minimum field set.** `unit_id, stage, entered_at,
   prior_stage, transition_event_id`.
4. **Identity.** `unit_id` (lives inside `UnitStatus[u]`).
5. **Provenance.** Lifecycle workflow (v10.3 §14.5) emits the transitioning
   transaction.
6. **Temporal semantics.** Mutable scalar; full history derivable from the
   transaction stream.
7. **Failure consequences.** Move against a non-`ACTIVE` unit => executor
   reject (v10.3 §3.6).

   (a) **Delete.** Do not store both `LifecycleFSM[u].stage` and
   `UnitStatus[u].lifecycle_stage`. They are the same field. Pick one
   home (the addendum picks `UnitStatus`); delete the other.
   (b) **Abstraction trap.** Two parallel FSMs (contractual vs
   valuation) with overlapping state names. Use distinct enum types;
   never share a string.
   (c) **Simplest ingest.** State transitions are `StateDelta` updates to
   `UnitStatus`. There is no separate FSM table.

### 5.6 Idempotency key store

1. **Canonical name.** `IdempotencyLog[idempotency_key] : TxId`.
2. **Definition.** v10.3 §14.18 — the deduplication record that enforces
   Invariant 5 (idempotency).
3. **Minimum field set.** `idempotency_key, transaction_id, first_seen_at,
   ttl?`.
4. **Identity.** `idempotency_key` (typically `hash(invoking_event_id,
   contract_ref, payload)`).
5. **Provenance.** Written by the Temporal activity at commit.
6. **Temporal semantics.** Append-only; rows expire by TTL only after the
   regulatory retention horizon, never before.
7. **Failure consequences.** Premature TTL expiration + retried message
   => duplicate transaction. Hard rule: TTL ≥ max retry horizon (days,
   not minutes).

   (a) **Delete.** Storing the full payload alongside the key is bloat;
   the `transaction_id` reference is sufficient.
   (b) **Abstraction trap.** "Generic deduplication service" that
   spans wallets, units, sessions, and message types. The key space is
   different per producer; collisions across spaces silently swallow
   legitimate distinct events. One log per key namespace.
   (c) **Simplest ingest.** A KV store with conditional-put semantics.
   Pure check `is_duplicate(key) -> bool`.

---

## 6. Listed-instrument detail — folded

Per §0 critique: this is not a top-level floor. Every field listed under
this category by the user belongs to one of the variants of
`ProductTerms.terms` (§1.2) or to the Reference sector (§2.1). The
mapping:

| Field commonly called "listed-instrument" | Where it lives |
|--|--|
| `exchange_mic, ccp_id, contract_type, strike, expiry, multiplier, settlement_style, last_trading_day, tick_size` | `ProductTerms[u].terms` (LISTED_DERIV variant) |
| `isin, board_lot_size, country_of_listing` | `ProductTerms[u].terms` (LISTED_EQUITY variant) |
| Vendor master record from which the above is constructed | `Reference.InstrumentMaster` |
| Holiday calendar referenced by `last_trading_day, expiry` | `Reference.BusinessCalendar` |
| Last settlement price for VM | `UnitStatus[u].last_settlement_price`, fed from `Attestation` (settlement price is signed) |

**Verdict:** delete this floor. Promoting it creates a parallel hierarchy
that violates the addendum's three-map ruling.

---

## 7. Categories the framework currently lacks

Honesty pass. From the *Jane Street CTO* discipline ("does the code's
claim match the data the system actually needs?"), three sectors are
under-specified in v10.3 + addendum + valuation companion. Calling them
out here is part of Phase 1.

### 7.1 Party / Legal Entity (§2.3 above)

Already enumerated in §2.3. v10.3 §10.1 mentions "reference data model
for parties" but does not specify the schema. The addendum's
`WalletRegistry` is *not* a substitute — wallets and parties are
many-to-one, and KYC discipline is per-wallet while regulatory
classification is per-party.

### 7.2 Configuration / Policy

Things like: tolerance thresholds for PnL explain (valuation companion
§7.2 lists per-instrument-class tolerances *as data, not as code*),
cadence values per instrument class (§5.2), staleness factors (§5.7),
retry budgets, no-arbitrage projection tolerances. These are
*values* that govern lifecycle and valuation behaviour, they change over
time, they require audit trails, and the framework currently treats them
as if they live in code. They do not.

1. **Canonical name.** `PolicyConfig[policy_id, t] : PolicyValue`.
2. **Definition.** Bi-temporal versioned policy parameters consumed by
   pure lifecycle and valuation functions.
3. **Minimum field set.** `policy_id, value, valid_from, system_time,
   change_ticket_ref, approver_id`.
4. **Identity.** `(policy_id, valid_from, system_time)`.
5. **Provenance.** Risk / Product RACI (per addendum F2).
6. **Temporal semantics.** Bi-temporal. Replay-determinism requires that
   any historical lifecycle invocation read the policy value
   `as_of(t_invocation)`.
7. **Failure consequences.** Mutable code-resident config => replay
   non-determinism => the PnL explain pipeline cannot be reconstructed
   for an audit query => regulatory finding.

   (a) **Delete.** Anything that is universally constant (e.g., the cubic
   degree for the polynomial PnL framework) — those are framework
   axioms, not policy. Keep them in code.
   (b) **Abstraction trap.** "Feature flags" framework. Feature flags
   are control plane; policy values are data plane. Different audit
   discipline, different rollback semantics. Don't conflate.
   (c) **Simplest ingest.** Bi-temporal table; pure
   `policy(id, t) -> Option[Value]`.

### 7.3 Wallet / Account metadata (the addendum's WalletRegistry)

The addendum names this but does not enumerate fields. For Phase 1
completeness:

1. **Canonical name.** `WalletRegistry[wallet_id] : WalletMetadata`.
2. **Definition.** Per-wallet KYC, permissions, audit cursor — explicitly
   *not* economic state (addendum §2).
3. **Minimum field set.**
   `wallet_id, wallet_type ∈ {REAL, VIRTUAL, SYSTEM, REFERENCE},
   owner_party_lei?, kyc_status, kyc_completed_at, permissions :
   Set[Capability], audit_cursor, opened_at, closed_at?`.
4. **Identity.** `wallet_id`.
5. **Provenance.** Onboarding workflow.
6. **Temporal semantics.** Mutable scalar fields; full history via event
   stream.
7. **Failure consequences.** Move from a wallet whose KYC has lapsed =>
   pre-trade reject. Capability mismatch on a strategy export read =>
   reject (addendum C4).

   (a) **Delete.** Anything that is per-position rather than per-wallet
   (those collapse to `PositionState[w, u_MA]` per C12).
   (b) **Abstraction trap.** Storing economic facts here. The
   addendum is explicit: zero economic content in this sector. Enforce
   by schema.
   (c) **Simplest ingest.** Onboarding writes; pure read.

---

## 8. Disagreements with the proposed floor and additions, summarised

| # | Position | Status |
|---|----------|--------|
| D1 | Rename "Static" → "ProductTerms" | binding rename |
| D2 | Delete "Listed-instrument detail" as a top-level floor; fold into ProductTerms variants | request |
| D3 | "Oracle" → "Attested observation"; recognise it as a provenance discipline applied chiefly to Market.Observable, not a parallel data sector | request |
| D4 | Split "Market" into 3a Observable (raw) + 3b Calibrated (Kalman output); they have different temporal semantics and different failure modes | request |
| D5 | Add **Party / Legal Entity** as a new floor (currently absent) | addition |
| D6 | Add **Configuration / Policy** as a new floor (currently absent) | addition |
| D7 | Make explicit that `WalletRegistry` is a non-economic sidecar with a fully enumerated schema | clarification |
| D8 | "Smart-contract execution" → "Execution"; it is data the system writes, not a data category about the world | rename |

---

## 9. The single load-bearing claim, repeated

Every category above ingests via an append-only or bi-temporal store.
Every category above is read by pure functions parameterised by a
captured snapshot. **The instant any field on this list becomes a
mutable scalar updated in place, replay-determinism (P3) collapses for
that field's transitive closure of consumers.** The discipline is not
optional. It is the difference between a system that can be audited and
a system that has to be re-derived from operator memory.
