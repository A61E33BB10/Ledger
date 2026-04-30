# FORMALIS Phase 1: Independent Data Enumeration

*Committee: Leroy (Chair), Coquand, Huet, Paulin-Mohring, de Moura, Avigad*

> "Programs are proofs; data are propositions; types are specifications. We do not ask what data the system *uses* — we ask what predicates the system *requires to hold*."
> — Xavier Leroy, opening the Phase 1 deliberation

This is an **independent enumeration** from the discipline of formal verification. It is **not** a convergence document. It states what the data layer must contain, what each datum is typed as, what invariant it must satisfy, and what totality means for any function defined over it. We work bottom-up from the Ledger v10.3 + StatesHome addendum + Valuation v1.0 specifications.

---

## §0 — Critique of the Floor Categories

The user-supplied floor categories are:

1. Static
2. Reference
3. Market
4. Oracle
5. Smart-contract execution
6. Listed-instrument detail

**FORMALIS finding (Coquand, Avigad concurring):** This taxonomy is *typed by source*, not *by semantics*. From a verification standpoint that is the wrong axis. Three substantive defects:

- **(a) "Static" subsumes "Reference" and "Listed-instrument detail."** All three are mutation-discipline-equal: once registered, append-only with versioning; never destructively mutated. Calling them three categories invites three implementations and three drift modes. They are one category (`ProductTerms`-class data) parameterised by *what kind of identity the unit carries*.
- **(b) "Market" and "Oracle" are not disjoint.** Every market datum used by the ledger arrives *through* an oracle (vendor feed, exchange tick, broker quote). The relevant axis is not source vs. interpretation but **raw observable** vs. **certified parameter** (Calibration Manifesto Axiom A4–A5). Conflating them obscures the Kalman-filter boundary (Valuation §5).
- **(c) "Smart-contract execution" is not a data category — it is *event* data.** Lumping execution traces into the data taxonomy without distinguishing **transactional event** (immutable, append-only, journal-class) from **derived projection** (re-computable, cache-class) breaks the substantiation argument of Ledger §8: if execution data is the *same kind of thing* as reference data, then "the balance sheet IS the ledger" loses its meaning.

**FORMALIS counter-taxonomy** (used below; the seven mandatory fields are filled for every item under both schemes):

| Tier | Mutation discipline | Examples |
|---|---|---|
| **D1. Identity & Terms** | append-only, versioned, registration-total | ISIN, contract spec, CDM Trade, mandate text, fee schedule, day-count conv. |
| **D2. Shared Status** | mutable per-key, single-writer-per-field | `lifecycle_stage`, `last_settlement_price`, `nav_index`, `triggered_barrier` |
| **D3. Per-Position State** | monotone-carrier, Option-accessor, single-writer-per-field | `accumulated_cost`, `borr`, `coll_post`, `entry_nav`, `hwm`, `ccp_binding` |
| **D4. Raw Observables** | append-only, time-stamped, bitemporal, never overwritten | bid/ask ticks, settlement prints, vendor feeds, oracle attestations |
| **D5. Certified Parameters** | Kalman posterior, point-in-time-as-of (knowledge time), supersession only via append | calibrated curves, vol surface coefficients, hazard rates |
| **D6. Events / Moves** | strictly append-only, hash-chained, immutable | every move, every state delta, every CDM `BusinessEvent` payload |
| **D7. Derived Projections** | re-computable, cache-class, must be regenerable from D1–D6 | wallet balances, $V_t$, $\mathrm{avail}(e,u)$, PnL, settlement instructions |
| **D8. Obligations** | append-only registry of typed obligations with deadline + discharge predicate + compensation | CSA-VM, SBL-recall, coupon-due, locate-confirm, regulatory-report |
| **D9. Workflow / Orchestration State** | Temporal-history-class (append-only, replayable, distinct from event log) | activity invocations, retry counts, FSM positions, signal channels |
| **D10. Capability / Identity (actors)** | append-only registry with revocation events | `WalletRegistry`, KYC, permissions, signer keys, role grants |

We retain the user's six floors as a *secondary* index but enforce D1–D10 as the *primary* discipline. The mapping floor→tier is many-to-many and is shown explicitly in §11.

The cardinality fact is decisive: under D1–D10 every datum has *exactly one* mutation rule, *exactly one* totality story, and *exactly one* failure mode. Under (1)–(6) several items have to be split across categories or duplicated. Cf. Leroy's CompCert dictum: "if the same datum lives in two categories, you will eventually mutate one and forget the other."

---

## §1 — Schema for Every Item

For every item below we provide the seven mandatory fields, then three FORMALIS additions:

```
(1) Canonical name                       — the name we will use everywhere
(2) Definition                           — what proposition this datum encodes
(3) Minimum field set                    — irreducible record schema
(4) Identity                             — how two values are deemed equal
(5) Provenance                           — what produces it; what authority signs it
(6) Temporal semantics                   — point-in-time / as-of / bitemporal / append-only
(7) Failure consequences                 — what breaks downstream if missing/corrupt

(a) Invariant                            — predicate the data layer must enforce
(b) Where enforced                       — type-level / runtime / property-test
(c) Totality of accessors                — what "total" means for read functions
```

We use `Option[T]` (Maybe) for partiality, `NonEmpty[T]` for non-empty lists, `Decimal` for exact arithmetic (never float; cf. Ledger §5.1 determinism requirement), `Map[K, V]` for total maps over registered keys.

---

## §2 — Tier D1: Identity & Terms

Subsumes user floors 1 (Static), 2 (Reference), and 6 (Listed-instrument detail). These are identity-anchored, append-only, versioned.

### D1.1 — UnitId

1. **Canonical name:** `UnitId`
2. **Definition:** A nominal token identifying an element of $\mathcal{U}$ (Ledger §2.1, §3). The proposition encoded is "this is a distinct economic instrument."
3. **Minimum field set:** `{kind: UnitKind, payload: UnitIdPayload}` where `UnitKind ∈ {CASH, EQUITY, LISTED_DERIV, OTC_DERIV, BOND, STRUCTURED, MANDATE, STRATEGY, SBL_LOAN, TOKENIZED, LOCATE}` and `payload` is kind-specific (currency code; ISIN; contract-spec hash; CDM Trade metadata key; etc.).
4. **Identity:** Structural equality on `(kind, payload)`. Required injective from CDM/spec source (Ledger §3.4 line 417).
5. **Provenance:** Derived deterministically at registration from CDM object or contract spec. Never user-supplied directly.
6. **Temporal semantics:** Append-only; `UnitId` once minted is permanent. C10 (re-registration is a hard error).
7. **Failure consequences:** ID collision ⇒ catastrophic — two distinct instruments collapse, conservation P1 trivially false. Missing ID ⇒ referential integrity P3 fails; executor must reject the move.

(a) **Invariant:** `∀ u₁, u₂ ∈ UnitStore. u₁.id = u₂.id ⇒ u₁.terms_v0 = u₂.terms_v0` (registration determinism).
(b) **Enforced:** Type-level — make `UnitId` a closed sum with deterministic constructors; registration is the *only* introduction rule. Runtime: hash collision check at Tier-3 unit-store registration.
(c) **Totality:** `lookup : UnitStore × UnitId → Option[UnitEntry]` is total over `UnitId`; `Some` iff registered. The accessor `terms : RegisteredUnitId → ProductTerms` is total by construction (Paulin-Mohring: refine `UnitId` to `RegisteredUnitId` at the type level once registration is observed).

### D1.2 — ProductTerms (versioned)

1. **Canonical name:** `ProductTerms[u]` (StatesHome §2 line 88).
2. **Definition:** The immutable contractual parameters of unit `u`. Encodes "this is what the contract says, evidenced as data."
3. **Minimum field set:** `NonEmpty[TermsVersion]` where each `TermsVersion` carries `{fields: TermsFields, effective_at: Timestamp, amendment_kind: Preserving | Breaking, fungibility_predicate: TermsAmendment → {Preserving, Breaking}, signer: ActorId, hash: Sha256}`. `TermsFields` is product-type-indexed: for futures `{multiplier, currency, expiry, ccp, exchange, product_id, lot_size}`; for OTC `{cdm_trade_object, csa_ref, collateral_terms}`; for mandate `{mandate_text_hash, fee_schedule, benchmark_id, max_position_limits, hwm_methodology, crystallisation_freq}`; for QIS `{vol_target, barrier, universe, share_class_index_start, weight_methodology}`; for bonds `{coupon_schedule, day_count, redemption_terms}`; etc.
4. **Identity:** `(unit_id, version_index)`. The current version is `tail.last` if non-empty else `head`.
5. **Provenance:** Issuer / ISDA confirmation / exchange specification / managed-account legal documentation. Each version signed.
6. **Temporal semantics:** **Append-only versioned.** C6: no in-place mutation. C7: registration-total — first version exists at registration. C8: amendments are two-track (Preserving appends; Breaking allocates a fresh `u_new`).
7. **Failure consequences:** Mutation in place ⇒ historical replay produces wrong moves (P3, P9 broken; CompCert-equivalent semantic preservation lost). Missing first version ⇒ `register` violates C7. Amendment misclassified ⇒ position state becomes ill-typed (a fungibility-breaking change pretending to be preserving silently corrupts every holder).

(a) **Invariant:** `is_fungibility_preserving(t_curr, t_new) = Preserving ⇒ payoff-equivalent for all states; = Breaking ⇒ allocate u_new and stamp SupersededBy(u_old → u_new)`. Append-only: `versions(t₂) ⊇ versions(t₁) for t₂ ≥ t₁`.
(b) **Enforced:** Type-level — `NonEmpty[TermsVersion]` makes "no terms exist" unrepresentable; `Preserving`/`Breaking` is a closed sum; the predicate `is_fungibility_preserving` is part of the product registration and is itself versioned (C8). Runtime: amendment handler invokes the predicate; mismatch is a hard error.
(c) **Totality:** `current_terms : RegisteredUnitId → TermsFields` is total (the head exists by `NonEmpty`). `terms_at(u, t) : RegisteredUnitId × Time → TermsFields` is total over registered `(u, t ≥ register_time(u))`; undefined before registration (encode as the precondition `t ≥ register_time(u)` at the type level via a refined timestamp).

### D1.3 — Reference Data (Tier-1)

1. **Canonical name:** `ReferenceData` (Ledger §3.3.1 Tier 1).
2. **Definition:** Instrument master data sourced from external authorities (exchanges, CSDs, vendors). Encodes "the external world's claim about the instrument."
3. **Minimum field set:** `{instrument_id: ExternalRef, issuer_lei: LEI, contract_spec: ContractSpec, listing_calendar: BusinessCalendar, day_count_conv: DayCount, settlement_calendar: BusinessCalendar, vendor_source: VendorId, vendor_timestamp: Timestamp, vendor_version: SourceVersion}`.
4. **Identity:** `(vendor_source, instrument_id, vendor_version)` for the *record*; the instrument identity is the contained `ExternalRef` (ISIN, CUSIP, contract code).
5. **Provenance:** External vendor / exchange feed. Authoritative outside the ledger boundary (Ledger §16).
6. **Temporal semantics:** **Bitemporal** — both *as-of-vendor-time* (when the vendor last updated this record) and *as-of-knowledge-time* (when we ingested it). Time travel must support both ("what we knew at $t$" vs. "with today's restated data"; Ledger §1.2 Property 6, §16 limitation 9).
7. **Failure consequences:** Stale or missing reference data ⇒ unit registration cannot complete (C5/C7 violated); existing units cannot be priced if their dependency leaves are missing.

(a) **Invariant:** Each reference record is monotone in `vendor_timestamp` per `(vendor_source, instrument_id)`. Bitemporal coherence: `as_of(t_know).vendor_timestamp ≤ t_know`.
(b) **Enforced:** Type-level — bitemporal pair `(KnownAt, EffectiveAt)` is a record type, not a single timestamp. Runtime: ingestion gate rejects records with future `vendor_timestamp` or duplicate `(source, id, version)` tuples.
(c) **Totality:** `current_ref(source, id) : (VendorId, ExternalRef) → Option[ReferenceData]`. Becomes total once a single record is ingested; remains `Option` because the ledger does not control vendor coverage.

### D1.4 — CalendarData

1. **Canonical name:** `BusinessCalendar`
2. **Definition:** A predicate `is_business_day : Date → Bool` parameterised by a finite holiday set + weekend rule. Required by every coupon/reset/expiry computation.
3. **Minimum field set:** `{calendar_id: CalendarId, weekend_rule: WeekendRule, holidays: SortedSet[Date], effective_range: (Date, Date), source: CalendarSource}`.
4. **Identity:** `calendar_id`.
5. **Provenance:** Exchange / CCP / regulator publishes; vendor packages; ledger ingests.
6. **Temporal semantics:** Append-only versioned (a calendar is republished as holidays are declared). Bitemporal in practice: a holiday declared *after* a coupon was scheduled must not silently reschedule the coupon.
7. **Failure consequences:** Missing calendar ⇒ business-day-adjusted dates undefined ⇒ coupon/reset workflows cannot fire (liveness P21 violated).

(a) **Invariant:** `effective_range` is a closed interval; for any date in range the predicate is total; calendars never retroactively delete a holiday already used by a settled event.
(b) **Enforced:** Runtime — sort + binary search; type-level encoding of `effective_range` as a refined date pair.
(c) **Totality:** `is_business_day : (CalendarId, Date) → Option[Bool]` (total only over `effective_range`).

### D1.5 — DayCountConvention

1. **Canonical name:** `DayCount`
2. **Definition:** Pure function `(Date, Date) → Decimal` returning the year fraction.
3. **Minimum field set:** Closed enum `{ACT_360, ACT_365, ACT_ACT_ICMA, THIRTY_360_BB, THIRTY_E_360, ...}` — finite, CDM-aligned.
4. **Identity:** Tag equality.
5. **Provenance:** ISDA / market convention.
6. **Temporal semantics:** Atemporal — pure mathematical objects.
7. **Failure consequences:** Wrong convention silently mis-prices every accrual; PnL drifts without unexplained-residual signal.

(a) **Invariant:** Each variant is a referentially transparent pure function. No I/O, no global state.
(b) **Enforced:** Type-level — closed sum + total pattern match (Coquand: "exhaustive coverage on a closed inductive type is a theorem").
(c) **Totality:** Total by construction.

### D1.6 — LegalAgreement

1. **Canonical name:** `LegalAgreement` (CSA, ISDA Master, GMSLA, MSLA, PBA, GMRA, mandate).
2. **Definition:** Reference to the legal contract governing a relationship between two or more parties. Hash-anchored to the signed document.
3. **Minimum field set:** `{agreement_id: AgreementId, kind: AgreementKind, parties: NonEmpty[LEI], document_hash: Sha256, effective_date: Date, termination_date: Option[Date], threshold: Option[Decimal], mta: Option[Decimal], eligible_collateral: Set[CollateralKind], rehyp_consent: RehypConsent, governing_law: Jurisdiction, signed_version: AgreementVersion}`.
4. **Identity:** `agreement_id`.
5. **Provenance:** Legal team / counterparty execution. Outside the ledger boundary; ingested as reference (Ledger §16).
6. **Temporal semantics:** Append-only versioned (amendments append). Bitemporal: when did we know about this amendment?
7. **Failure consequences:** Missing CSA ⇒ aggregate-MTM margin call cannot compute thresholds (Ledger §6.4 wallet-level CSA contract has no parameters); SBL legal regime mis-set ⇒ rehypothecation rules wrong, P19 violated; mandate text missing ⇒ mandate-as-unit (StatesHome §4.2 line 198) has no `ProductTerms`.
(a) **Invariant:** Every agreement is bound to a finite party set with valid LEIs (D10). Once an SBL loan or mandate cites an agreement version, that version is frozen for that loan/mandate (semantic preservation).
(b) **Enforced:** Type-level — bind agreement version into `ProductTerms[u_MA]` / `ProductTerms[u_loan]` so amendments require either Preserving (append) or Breaking (new unit) treatment via C8.
(c) **Totality:** `agreement_terms : (AgreementId, Date) → Option[AgreementVersion]`.

### D1.7 — TaxonomyEnums (CDM)

1. **Canonical name:** `CDMEnum_*` — all CDM closed enumerations: `EventIntentEnum`, `OptionTypeEnum`, `MarginCallInstructionTypeEnum`, etc. (Ledger §11.5).
2. **Definition:** Finite, formally defined sets used as both type universe and generator universe.
3. **Minimum field set:** Tag set + CDM version tag.
4. **Identity:** Tag equality, parameterised by CDM version.
5. **Provenance:** FINOS CDM release.
6. **Temporal semantics:** **Append-only across CDM versions.** Each event payload stores its CDM version (Ledger §10.3 line 1951). New enum values may be added in later versions; old payloads must replay under their original version.
7. **Failure consequences:** Missing variant in pattern match ⇒ totality of state-machine accessor breaks (Avigad: "the closed-world assumption is what makes induction over events sound").

(a) **Invariant:** Every state-machine handler exhausts every variant of every enum it pattern-matches on.
(b) **Enforced:** Type-level — closed sum with mandatory exhaustive match (compiler-checked); property-based testing draws from the full enum (Ledger §11.5 "completeness illustration") — combined static + property-test gate.
(c) **Totality:** Pattern-match accessors total by closed-world.

---

## §3 — Tier D2: Shared Mutable Status

Per StatesHome §2 ruling. One map keyed by `UnitId`, mutable, shared across all holders.

### D2.1 — UnitStatus[u]

1. **Canonical name:** `UnitStatus[u]` (StatesHome line 89).
2. **Definition:** The mutable shared lifecycle position of unit `u`. Encodes "where in its life this contract currently is."
3. **Minimum field set:** `{lifecycle_stage: LifecycleStage, last_settlement_price: Option[Decimal], last_settlement_date: Option[Date], superseded_by: Option[UnitId]}` plus product-specific extensions: futures `{}`; QIS `{current_weights, nav_index, vol_realised, triggered_barrier, last_rebalance_date, cumulative_return}`; bonds `{paid_coupons: Set[Date], matured: Bool}`; options `{}` (state-only ACTIVE → EXERCISED/EXPIRED/ASSIGNED); mandates `{benchmark_level_at_now}` (typically; benchmark may be its own unit per StatesHome §4.2).
4. **Identity:** Identity of the *map cell* is `UnitId`; identity of the *value* is the (`UnitId`, monotone version stamp) — every write increments a version.
5. **Provenance:** Written by the *unique* handler per field (C11): `last_settlement_price` ← settle handler; `triggered_barrier` ← barrier-observation handler; `superseded_by` ← amendment handler; etc.
6. **Temporal semantics:** **Mutable point-in-time, with full history reconstructible from the event log.** The current value is a projection of the move stream filtered to state-delta transactions.
7. **Failure consequences:** Wrong field-writer ⇒ P10 violated (handler-field canon). Two writers race on `lifecycle_stage` ⇒ non-determinism (Leroy: "single-writer per cell is necessary, not sufficient — but it is necessary"). Missing default at registration ⇒ C5 violated, accessor returns `None` for a registered unit ⇒ totality lost.

(a) **Invariant:** Each field has a unique writer; default is set at registration (C5); transitions follow the closed-enum state machine. Lifecycle monotonicity for terminal stages: `MATURED|EXPIRED|TERMINATED|SETTLED|CANCELLED|DEFAULTED` are absorbing.
(b) **Enforced:** Type-level — represent each field with a phantom-typed writer capability; closed-enum lifecycle stages with refined-state transition functions; product-specific status types so illegal field combinations are unrepresentable (Ledger §7.3 line 1045).
(c) **Totality:** `unit_status : RegisteredUnitId → UnitStatus` is total (C5: registration-total). For any specific field `f`, `f(unit_status(u))` is total when `u` is registered, returning the field's typed default if not yet written.

### D2.2 — NAV / Index Level Series

A specialisation of D2.1 carried by strategy/benchmark units. Worth singling out because it is the consumption point of the valuation layer for performance contracts.

1. **Canonical name:** `IndexNAV[u]`
2. **Definition:** The current published level of a strategy or benchmark unit; the proposition "the strategy is at this level."
3. **Minimum field set:** `{level: Decimal, level_date: Date, methodology_version: TermsVersion, last_publication_lag: Duration}`.
4. **Identity:** `(u, level_date, methodology_version)`.
5. **Provenance:** Strategy contract handler (for QIS) or benchmark vendor (for external indices, where the benchmark is itself a registered unit per StatesHome §4.3).
6. **Temporal semantics:** Bitemporal — `level_date` (as-of) and `level_publication_time` (knowledge time). Restatements append a new record; replays use the version specified by query.
7. **Failure consequences:** Wrong level ⇒ TRS settlement wrong (Ledger §6.7); HWM crystallisation wrong (StatesHome §4.2); manager fees wrong.
(a) **Invariant:** `level > 0` (NAVs are positive). Methodology version must be Preserving across the series unless an explicit Breaking event resets a fresh strategy unit.
(b) **Enforced:** Type-level — refined `Positive[Decimal]`; methodology-version pinning at publication time.
(c) **Totality:** `nav_at(u, t) : RegisteredUnitId × Time → Option[IndexNAV]`. `None` before first publication.

---

## §4 — Tier D3: Per-Position State

Per StatesHome §2 ruling. One map keyed by `(WalletId, UnitId)`, monotone-carrier, Option-accessor.

### D3.1 — PositionState[w, u] (scalar projection)

1. **Canonical name:** `PositionState[w, u]` (StatesHome line 90).
2. **Definition:** Per-position lifecycle and accumulated facts for the holder `w` of unit `u`. Encodes "what this wallet has experienced about this contract."
3. **Minimum field set:** Product-indexed; for futures `{accumulated_cost: Decimal, ccp_binding: WalletId}`; for OTC derivative `{per_position_cdm_trade_lifecycle: TradeLifecycle, csa_link: AgreementId}`; for mandate/strategy holding `{entry_nav: Decimal, hwm: Decimal, hwm_date: Date, accrued_mgmt_fee: Decimal, accrued_perf_fee: Decimal, mandate_breach_flags: Set[BreachKind], benchmark_nav_at_inception: Decimal, subscription_redemption_cursor: Cursor}`; for SBL loan unit holder `{}` (the loan unit's per-position state lives in `D3.2`); for tax-lots (open problem in Ledger §15) `{lots: List[TaxLot]}`.
4. **Identity:** `(WalletId, UnitId)`.
5. **Provenance:** The unique-writer handler per C11.
6. **Temporal semantics:** **Monotone-carrier with Option accessor** (C1 / StatesHome §2.2). Once created, a row is never deleted; close-out leaves a `Some(zero_P)` row; never-held returns `None`.
7. **Failure consequences:** Garbage-collected close-out row ⇒ wash-sale lookback, VM-settle replay, record-date entitlement reconstruction all broken (StatesHome §2.2). Missing `accumulated_cost` ⇒ futures P1 (sum-zero conservation per contract) cannot be checked.

(a) **Invariant:** For each *conserved* field `f`, `Σ_w f(w, u) = 0` per contract (C2 handler-level structural zero-sum, including the vacuous empty-holders base case C9). For non-conserved monotone fields (`hwm`), monotonicity in time. For each field, the unique-writer C11 holds.
(b) **Enforced:** Mostly runtime — refinement types on decimal sums are not free in production languages (StatesHome §2.3); enforcement is at the **event handler**, with proofs per event class. Type-level: handler-tagged field write, monotone-carrier as storage discipline, Option accessor as access discipline.
(c) **Totality:** `position_state : (WalletId, UnitId) → Option[PositionState]`. `None` ≢ `Some(zero)` — both are load-bearing readings (StatesHome §2.2).

### D3.2 — PositionVector (six-coordinate, generalised)

1. **Canonical name:** `PositionVector[e, u]` (Ledger §15.2).
2. **Definition:** $\vec{w}_e(u) \in \mathbb{R}^6 = (\mathrm{own}, \mathrm{onloan}, \mathrm{borr}, \mathrm{coll\_post}, \mathrm{coll\_recv}, \mathrm{coll\_rehyp})$. The wallet balance generalised for SBL.
3. **Minimum field set:** Six `Decimal` coordinates plus type-tag `is_lendable: Bool` (Ledger §15.3 collapse property).
4. **Identity:** `(EntityId, UnitId)`.
5. **Provenance:** Each coordinate has a unique-writer handler per the Single-Coordinate Move Principle (Ledger §15.2 Principle).
6. **Temporal semantics:** Append-only via the move stream; current vector is a projection of the move log filtered to that `(e, u)` pair.
7. **Failure consequences:** Coordinate confusion (e.g., a sell that touches `borr` instead of `own`) ⇒ P18 (Lender Ownership Invariance) and P11–P20 break; SBL conservation Proposition 15.7 fails.

(a) **Invariant:** Single-Coordinate Move Principle (one move, one coordinate, one unit, two entities); Proposition 15.7 conservation; for borrowers, `onloan ≤ borr + own` (an entity cannot re-lend more than it has + borrowed, Ledger §15.16). For non-lendable units, only `own` is non-zero (graceful degeneration, Remark 15.4).
(b) **Enforced:** Type-level — phantom-typed move constructor (`Move[Coordinate]`); the `avail` projection is *only* a function of three coordinates and is never stored (P20 holds by definition not by check); for non-lendable kinds, the type system reduces to a scalar variant via a kind-indexed family.
(c) **Totality:** `position_vector : (EntityId, UnitId) → Option[PositionVector]`. Projections (`avail`, `possess`, `encumb`) are total functions of the vector and cannot drift because they are never stored.

### D3.3 — PerLoanSettlementState (SBL & repo)

1. **Canonical name:** `LoanLifecycleState[u_loan]` (Ledger §15.7 unit state for SBL contract).
2. **Definition:** Per-loan-unit state tracked alongside the holder ($+1/-1$) entries. Carries `lender, borrower, term_type, maturity_date, fee_rate, rebate_rate, last_mark_date, accrued_fee, recall_date, recall_qty, sftr_uti, slate_loan_id`.
3. **Minimum field set:** As stated in Ledger §15.7 `SBLUnitState`.
4. **Identity:** `loan_id` (which is itself a `UnitId`).
5. **Provenance:** SBL smart contract handlers (initiation, mark, recall, return, rate-change, substitution).
6. **Temporal semantics:** Mutable shared status (D2.1 idiom) — but per-loan, since each loan is its own unit. Strictly speaking this is `D2.1` instantiated with `kind = SBL_LOAN`.
7. **Failure consequences:** Same as D2.1; additionally, mis-tracking `recall_date`/`recall_qty` ⇒ P14, P21 (obligation liveness) and IBP reconciliation break.

(a) **Invariant:** State-machine totality (Ledger §15.8 — every (state, event) pair is handled or rejected). `quantity` monotonically non-increasing across partial returns (P15).
(b) **Enforced:** Type-level — refined-state machine where transitions are typed; Tier D8 obligations register the deadlines.
(c) **Totality:** Total over registered loan units.

---

## §5 — Tier D4: Raw Observables

Subsumes user floor 3 (Market) at its raw level. These are the *uninterpreted* attestations that arrive from oracles.

### D4.1 — MarketTick / Quote / Print

1. **Canonical name:** `RawObservation`
2. **Definition:** A single raw attestation `y_t` (Valuation §5.3 observation model) carrying observable value(s) at a knowledge time. Encodes "the vendor reports this value at this moment."
3. **Minimum field set:** `{instrument_ref: ExternalRef | UnitId, observable_kind: ObservableKind, value: Decimal, value_unit: Unit, vendor: VendorId, vendor_timestamp: Timestamp, knowledge_timestamp: Timestamp, bid_ask: Option[(Decimal, Decimal)], side: Option[Side], staleness_factor: Decimal, signed_attestation: Option[Sig]}` where `ObservableKind ∈ {SPOT, BID, ASK, LAST, SETTLE, OPEN, CLOSE, OPTION_PREMIUM, SWAP_RATE, CDS_SPREAD, ATM_VOL, RR, BF, FX_RATE, ...}`.
4. **Identity:** `(vendor, instrument_ref, observable_kind, vendor_timestamp)` — unique per vendor publication. Multiple vendors may produce the same tick; they are distinct rows.
5. **Provenance:** Exchange tick / vendor feed / broker quote / OTC oracle. Outside the ledger boundary.
6. **Temporal semantics:** **Bitemporal, append-only.** `vendor_timestamp` (as-of) and `knowledge_timestamp` (when ingested). Restatements append; never overwrite. Raw observations are *never* mutated.
7. **Failure consequences:** Missing observation ⇒ Kalman observation model has nothing to update; pricing FSM stays in `Stale` (Valuation §2 T8). Stale observation accepted as fresh ⇒ value-dependent settlements (margin, TRS) produce incorrect moves (Ledger §9.4 fault-tolerance: market data quality gating).

(a) **Invariant:** Append-only; `knowledge_timestamp ≥ vendor_timestamp` (cannot ingest from the future); each observation carries a typed `ObservableKind` so calibration cannot mis-route a swap rate to a vol surface.
(b) **Enforced:** Type-level — `ObservableKind` is a closed sum; bitemporal pair refined into a record type; cryptographic signature optional but recommended (Huet: "if your trust boundary is implicit, your unification is unsound").
(c) **Totality:** `observations(instrument, kind, [t_lo, t_hi]) : (Ref, Kind, TimeRange) → List[RawObservation]`. Total — returns empty list when no data, never panics.

### D4.2 — OracleAttestation (signed)

1. **Canonical name:** `OracleAttestation`
2. **Definition:** A `RawObservation` whose authenticity is established by cryptographic signature from a trusted oracle (e.g., on-chain price feed, SOFR Administrator).
3. **Minimum field set:** D4.1 fields + `{oracle_id: OracleId, signature: Sig, attestation_payload_hash: Sha256, attestation_chain: Option[BlockchainRef]}`.
4. **Identity:** `(oracle_id, attestation_payload_hash)`.
5. **Provenance:** Trusted oracle authority; on-chain or off-chain.
6. **Temporal semantics:** Append-only, bitemporal as D4.1.
7. **Failure consequences:** Forged or unverifiable attestation ⇒ ingestion gate must reject; otherwise upstream state is poisoned (de Moura: "non-determinism plus forged inputs is the canonical broken-proof scenario").

(a) **Invariant:** Signature verification under the oracle's published key passes; key chain is established via D10 capability registry.
(b) **Enforced:** Runtime cryptographic check at ingestion; type-level `VerifiedAttestation` is a refined subtype that can only be constructed via the verifier.
(c) **Totality:** Verifier `verify : OracleAttestation × KeyRegistry → Option[VerifiedAttestation]` total.

### D4.3 — VendorSnapshot

1. **Canonical name:** `VendorSnapshot`
2. **Definition:** A coherent point-in-time bundle of `RawObservation`s used as the input to a deterministic replay (Valuation §6 "deterministic seed = hash(market_data_snap, unit_id)"; Ledger §7.7 deterministic oracle).
3. **Minimum field set:** `{snapshot_id: SnapshotId, knowledge_timestamp: Timestamp, observations: NonEmpty[RawObservation], coverage_manifest: CoverageManifest, integrity_hash: Sha256}`.
4. **Identity:** `snapshot_id`, with content-addressed `integrity_hash`.
5. **Provenance:** Snapshotted by the market-data ingestion service.
6. **Temporal semantics:** **Append-only, point-in-time-as-of.** Replay-by-snapshot-id is reproducible.
7. **Failure consequences:** Missing snapshot ⇒ replay is non-deterministic; Ledger §7.7 reproducibility violated; valuation cannot be re-run.

(a) **Invariant:** Snapshot content matches the integrity hash; `knowledge_timestamp ≥ max(o.knowledge_timestamp for o in observations)`.
(b) **Enforced:** Type-level — `VerifiedSnapshot` only constructible via hash check; runtime hash verification on read.
(c) **Totality:** `snapshot(id) : SnapshotId → Option[VendorSnapshot]`.

---

## §6 — Tier D5: Certified Parameters

The Kalman posterior. Derived from D4 by the calibration engine; consumed by the pricing DAG. Should not be confused with raw market data: this is the canonical FORMALIS critique of the user's "Market" floor.

### D5.1 — CalibratedCurve / CalibratedSurface

1. **Canonical name:** `CertifiedCalibration[c]` where `c` is a calibration object id (a yield curve, a vol surface).
2. **Definition:** Posterior mean $x_{t|t}^{\text{certified}}$ from the Kalman filter (Valuation §5.7), restricted to the no-arbitrage admissible region $\Theta_{AF}$.
3. **Minimum field set:** `{calibration_id: CalibrationId, state_vector: Vector[Decimal], covariance: Matrix[Decimal], posterior_timestamp: Timestamp, observation_window: TimeRange, model_id: ModelId, certification_status: {Certified, Stale, Failed}, no_arb_check: NoArbReport, residuals: Map[InstrumentRef, Decimal], wrmse: Decimal, snapshot_input: SnapshotId}`.
4. **Identity:** `(calibration_id, posterior_timestamp, model_id, snapshot_input)` — including the input snapshot is essential for reproducibility.
5. **Provenance:** Kalman filter workflow (Valuation §5.4 predict-update); innovation-gated (§5.5); no-arb-projected (§5.6).
6. **Temporal semantics:** **Point-in-time-as-of (knowledge time)**, append-only via the calibration history. Bitemporal under restatement: a Kalman re-run with corrected raw data appends a new certified state for the same `posterior_timestamp` with a later `published_at`.
7. **Failure consequences:** Uncertified output used ⇒ pricing under arbitrage; PnL explain residual gets large but the true source is calibration error (Calibration Manifesto A4); model risk reserve mis-stated.

(a) **Invariant:** `state_vector ∈ Θ_AF`; per-instrument residuals within tolerance; aggregate WRMSE within tolerance; covariance positive semi-definite; for the kernel vol model, butterfly-positivity translated to coefficient-level inequalities (Valuation §5.6).
(b) **Enforced:** Runtime — projection onto $\Theta_{AF}$ at the end of the update step; certification gate. Type-level — `Certified[Calibration]` is a refined subtype constructible only by the certifier.
(c) **Totality:** `current_calibration(c, t) : (CalibrationId, Time) → Option[Certified[Calibration]]`. `None` until first successful certification or after a permanent fallback to the last-known-good state with `Stale` flag.

### D5.2 — SensitivityJacobian

1. **Canonical name:** `Jacobian[u, model]`
2. **Definition:** $J = (\partial P / \partial \theta_1, \ldots, \partial P / \partial \theta_n)$ for unit `u` under model `model` (Valuation §3.4).
3. **Minimum field set:** `{unit_id: UnitId, model_id: ModelId, observable_sens: Map[ObservableKind, Decimal], parameter_sens: Map[ParameterKind, Decimal], cross_sens: Map[(ObservableKind, ParameterKind), Decimal], computation_method: {Analytical, Bump, AAD, Pathwise, LR}, base_price: Decimal, snapshot_input: SnapshotId, total_greeks: Bool}`.
4. **Identity:** `(unit_id, model_id, snapshot_input)`.
5. **Provenance:** Greek computation activity (Valuation §3.10).
6. **Temporal semantics:** Cycle-bound; valid for the snapshot it was computed against. Older Jacobians may be retained per the valuation store retention policy.
7. **Failure consequences:** Stale Jacobian used in PnL explain ⇒ residual mis-attributed to "unexplained"; using model A's J on model B's price change ⇒ spurious residual (Remark 3.13).

(a) **Invariant:** Dimension equals model parameter count; cross-sensitivities symmetric where mathematically required; computation method recorded for audit.
(b) **Enforced:** Type-level — `Jacobian` parameterised by `ModelId` so a Heston Jacobian cannot be applied to a Black-Scholes record (model-consistency, Remark 3.13).
(c) **Totality:** `jacobian_at(u, model, t) : (UnitId, ModelId, Time) → Option[Jacobian]`.

### D5.3 — ValuationRecord

1. **Canonical name:** `ValuationRecord` (Valuation §3 Definition 3.1).
2. **Definition:** The certified output of a pricing cycle: scalar `dirty_price` plus rich metadata (clean, accrued, Greeks, model_id, snapshot, quality, FSM-state).
3. **Minimum field set:** As Valuation §3.1.
4. **Identity:** `(unit_id, timestamp, model_id)`.
5. **Provenance:** PnL-explain-passing pricing workflow (Valuation §7).
6. **Temporal semantics:** Append-only within a pricing cycle; queryable point-in-time via `snapshot_at(t)`.
7. **Failure consequences:** Quality field incorrectly set to FIRM when it should be APPROXIMATE/STALE ⇒ official PnL contaminated by approximate prices.

(a) **Invariant:** `dirty_price = clean_price + accrued`; `quality = FIRM ⇒ fsm_state = Explained`; PnL explain passed; `model_id` matches the Jacobian's `model_id`.
(b) **Enforced:** Type-level — `Quality` closed sum, `fsm_state` closed sum; refined subtype `FirmRecord` constructible only after PnL explain pass.
(c) **Totality:** `latest_firm(u) : UnitId → Option[FirmRecord]`. Total over all consumers; `None` ⇒ unit has never had a successful priced-and-explained cycle.

---

## §7 — Tier D6: Events / Moves

The journal. Subsumes user floor 5 (smart-contract execution).

### D6.1 — Move

1. **Canonical name:** `Move` (Ledger §2.3 Definition 2.2).
2. **Definition:** An atomic ledger modification transferring quantity from one wallet to another.
3. **Minimum field set:** `{move_id: MoveId, src: WalletId, dst: WalletId, unit: UnitId, qty: Decimal /* positive */, coordinate: Coordinate /* per Single-Coordinate Move Principle */, timestamp: Timestamp, source_contract: ContractRef, metadata: MoveMetadata, txn_id: TxnId}`.
4. **Identity:** `move_id`. Within a transaction, ordered by sequence index.
5. **Provenance:** Smart contract emits proposal; executor commits.
6. **Temporal semantics:** **Strictly append-only, immutable, hash-chained** (Ledger §11.2 P4 with cryptographic hash chaining).
7. **Failure consequences:** Mutation of a committed move ⇒ entire framework collapses. Missing `txn_id` ⇒ atomicity P2 unverifiable. Duplicate `move_id` ⇒ conservation P1 over-counts.

(a) **Invariant:** Conservation per `(txn_id, unit)` (Ledger §2.4 Theorem). `qty > 0`. Single-coordinate per move (Ledger §15.2 Principle). Hash-chained: each entry includes hash of previous (P4).
(b) **Enforced:** Type-level — `Coordinate` is a phantom type indexing the move; refined `Positive[Decimal]` for qty. Runtime: hash chain verified on append; conservation check at executor commit.
(c) **Totality:** `move_at(move_id) : MoveId → Option[Move]`. Stream replay `apply_all(moves[:k])` is total.

### D6.2 — Transaction

1. **Canonical name:** `Transaction` (Ledger §2.4 Definition 2.3).
2. **Definition:** A finite collection of simultaneous moves satisfying conservation per unit.
3. **Minimum field set:** `{txn_id: TxnId, type: TxnType /* SETTLEMENT | COLLATERAL | LIFECYCLE | ACCOUNTING | CORRECTION */, moves: NonEmpty[Move] | Empty /* state-only */, state_deltas: List[StateDelta], cdm_payload: CDMBusinessEvent, timestamp: Timestamp, sequence_in_timestamp: Int, originator_contract: ContractRef, corrects: Option[TxnId], cdm_version: CdmVersion}`. (State-only transactions allowed for pure status updates such as barrier-knockout, lifecycle stage changes — Ledger §17 Q1.)
4. **Identity:** `txn_id`.
5. **Provenance:** Smart contract emits; executor stamps + commits atomically.
6. **Temporal semantics:** Append-only; `sequence_in_timestamp` provides a total order within ties (Ledger §2.4).
7. **Failure consequences:** Same as D6.1 plus: missing `corrects` link ⇒ correction algebra (Ledger §15 open problem) breaks; missing `cdm_payload` ⇒ regulatory reporting projection (DRR) loses business context.

(a) **Invariant:** Conservation per unit; atomicity (P2); referential integrity (P3); single-writer per state-delta field (C11). For `CORRECTION` type: `corrects ≠ None` and the original txn exists. For state-only: `moves = Empty` is permitted iff `state_deltas ≠ []`.
(b) **Enforced:** Type-level — `TxnType` closed sum with refined records per case so `CORRECTION` requires `corrects: TxnId`. Runtime: executor's atomic commit gate.
(c) **Totality:** `txn(id) : TxnId → Option[Transaction]`; replay total.

### D6.3 — StateDelta

1. **Canonical name:** `StateDelta`
2. **Definition:** A typed record describing a state change to D2/D3 storage. Encodes "this field on this key changed by this amount, by this handler."
3. **Minimum field set:** `{key: (Option[WalletId], UnitId), field: FieldId, old: FieldValue, new: FieldValue, writer_handler: HandlerId, txn_id: TxnId}`.
4. **Identity:** `(txn_id, key, field, sequence)`.
5. **Provenance:** Lifecycle handler proposes; executor commits as part of `Transaction`.
6. **Temporal semantics:** Append-only via the transaction stream.
7. **Failure consequences:** Wrong `writer_handler` ⇒ C11 violated. Missing `old` ⇒ replay cannot verify monotonicity invariants.

(a) **Invariant:** `writer_handler` matches the unique-writer of `field` (C11). For monotone fields, `new ≥ old` (Avigad: "induction over event stream relies on per-step monotonicity proofs").
(b) **Enforced:** Type-level — `FieldId` indexed by writer-handler; phantom-typed access tokens.
(c) **Totality:** Replay total.

### D6.4 — CDM BusinessEvent Payload

1. **Canonical name:** `CDMBusinessEvent`
2. **Definition:** The full CDM event record stored in the transaction's metadata (Ledger §10.4 forgetful mapping `F`).
3. **Minimum field set:** CDM-defined; carries `before` / `after` `TradeState`, `EventIntentEnum`, lineage.
4. **Identity:** CDM event id.
5. **Provenance:** External (FpML/FIX/ISO 20022 via synonym) or internal contract emission.
6. **Temporal semantics:** Append-only, embedded in transactions.
7. **Failure consequences:** Loss of CDM payload ⇒ regulatory reporting (DRR) and audit reconstruction broken (Ledger §10.4 "what F preserves" argument depends on the payload being retained).

(a) **Invariant:** `cdm_version` recorded; `EventIntentEnum` value is in the version's enum set.
(b) **Enforced:** Type-level — closed enum per version; runtime: validation against CDM schema.
(c) **Totality:** Closed-world pattern match per CDM version.

---

## §8 — Tier D7: Derived Projections (cache class)

These are *not* primary data. They are functions of D1–D6 and must be regenerable. Listing them is essential because mistaking them for primary data is the canonical multi-source-of-truth bug (Ledger §1).

### D7.1 — WalletBalance

`balance(w, u, t) = w_0(u) + Σ moves m: m.unit=u, m.time≤t [+m.qty if dst=w, −m.qty if src=w]`. Cache, never primary. Total when prefix of stream is total.

### D7.2 — PortfolioValue $V_t$

`V_t(w) = Σ_u own(w,u) · P_t(u)`. Pure projection; depends on D2/D3 (positions) and D5.3 (FIRM ValuationRecord).

### D7.3 — `avail`, `possess`, `encumb` (Ledger §15.5)

Pure functions of `D3.2`; never stored.

### D7.4 — SettlementInstruction

`settle_projection : Transaction → Option[SettlementInstruction]` (Ledger §9). Pure; total over `SETTLEMENT|COLLATERAL` types.

### D7.5 — RegulatoryReport (SFTR/SLATE/EMIR/MiFIR fields)

Projection of D6 + D1 + D5; bound by DRR-generated mappings.

(For all D7 items, the invariant is "regenerable from D1–D6"; enforced by property-based testing — recompute the projection from a clean replay and assert equality with the cached value.)

---

## §9 — Tier D8: Obligations (first-class)

Per Ledger §14.7 the user's framework has lifted obligations from "implicit in workflow code" to a first-class data category. FORMALIS treats this as a primary tier.

### D8.1 — Obligation

1. **Canonical name:** `Obligation` (Ledger §14.7 Definition 14.10).
2. **Definition:** `o = (id, type, source, t_d, D, κ)` — id, obligation-type-tag, source (unit or agreement), deadline, discharge predicate, compensation action.
3. **Minimum field set:** As stated, plus `{state: ObligationState, retry_count: Nat, idempotency_token: TokenId}`.
4. **Identity:** `o.id`, derived deterministically from source event + obligation type.
5. **Provenance:** Registered atomically with the triggering event (Principle 14.13 obligation completeness) or at unit registration (deterministic-date class).
6. **Temporal semantics:** **Append-only registry**, with state transitions recorded as state-only transactions in the event log.
7. **Failure consequences:** Missing obligation ⇒ liveness P21 violated (margin not delivered, recall not pursued, regulatory report not filed); silent default with no audit trail.

(a) **Invariant:** P21 (liveness): `∀ t > t_d. o.state ∈ {Discharged, Compensated, Defaulted}`. P22 (conservation of discharge moves). P23 (idempotency: discharge predicate gates re-emission).
(b) **Enforced:** Type-level — closed `ObligationState` sum with absorbing terminal states; runtime — Temporal durable timer at `t_d` (Lemma 4 of §14.7.5); typed return-type of obligation-creating handlers must include the obligation list (Principle 14.13). Property-based testing for completeness (test 11).
(c) **Totality:** `obligations_for(source) : SourceRef → List[Obligation]` total. Handler totality (Lemma 5): every (state, trigger) pair reaches a terminal state.

### D8.2 — DischargePredicate

1. **Canonical name:** `D : LedgerState → Bool`
2. **Definition:** Pure predicate parametrically defined per obligation type.
3. **Minimum field set:** Function reference + serialised parameters (must be content-hashable for replay).
4. **Identity:** `(obligation_type, predicate_hash)`.
5. **Provenance:** Defined by the obligation-creating contract.
6. **Temporal semantics:** Versioned via D1 (lives in `ProductTerms` of the source unit/agreement).
7. **Failure consequences:** Wrong predicate ⇒ false discharge, missed default.

(a) **Invariant:** Pure (no I/O); deterministic; total over all reachable ledger states.
(b) **Enforced:** Type-level — predicate has no side-effecting positions; runtime — re-evaluation on the state at discharge attempt.
(c) **Totality:** Total by typing.

### D8.3 — CompensationAction

1. **Canonical name:** `κ : Obligation → PendingTransaction`
2. **Definition:** Deterministic function producing the compensating moves when the deadline passes without discharge.
3. **Minimum field set:** Function reference + serialised parameters.
4. **Identity:** `(obligation_type, compensation_hash)`.
5. **Provenance:** As D8.2.
6. **Temporal semantics:** Versioned via D1.
7. **Failure consequences:** Wrong compensation ⇒ default cannot be cleanly resolved; close-out netting wrong amounts.

(a) **Invariant:** Output transaction satisfies conservation (P22); idempotent under retry.
(b) **Enforced:** Same gates as D6.2 (executor checks conservation on commit).
(c) **Totality:** Total by typing.

---

## §10 — Tier D9: Workflow / Orchestration State

Distinct from the event log (Ledger §14.4 "Two Audit Trails"). This is Temporal's append-only history.

### D9.1 — WorkflowHistory

1. **Canonical name:** `WorkflowHistory[wf_id]`
2. **Definition:** Append-only sequence of orchestration decisions: timer fires, signal receives, activity invocations + results, FSM transitions, child-workflow spawns, `ContinueAsNew` checkpoints.
3. **Minimum field set:** `{wf_id: WorkflowId, run_id: RunId, events: NonEmpty[WorkflowEvent], cdm_version: CdmVersion, ledger_version: LedgerVersion}`.
4. **Identity:** `(wf_id, run_id)`.
5. **Provenance:** Temporal cluster.
6. **Temporal semantics:** **Append-only**, replayable — distinct from D6 (event log records *economic* content; D9 records *orchestration* sequencing).
7. **Failure consequences:** History loss ⇒ in-flight workflows cannot recover; saga compensation paths uncomputable; liveness gap reopens.

(a) **Invariant:** Append-only; deterministic replay produces identical FSM traces from the same history (Ledger §14.10 alignment).
(b) **Enforced:** Temporal SDK; the *workflow code itself* must be deterministic (no random, no clock, no I/O outside activities) — Coquand: "the replay trace is the proof object; non-determinism in the proof is unsound."
(c) **Totality:** `replay(history) : WorkflowHistory → WorkflowState` total under workflow-code determinism.

### D9.2 — ActivityResult

1. **Canonical name:** `ActivityResult`
2. **Definition:** Memoised result of a Temporal activity invocation, recorded in the workflow history.
3. **Minimum field set:** `{activity_id: ActivityId, input_hash: Sha256, output: ActivityOutput | ErrorCode, retry_count: Nat, completed_at: Timestamp}`.
4. **Identity:** `(wf_id, activity_id, input_hash)`.
5. **Provenance:** Temporal worker.
6. **Temporal semantics:** Append-only within a workflow run.
7. **Failure consequences:** Replay non-determinism if activity is non-pure or its output is not memoised.

(a) **Invariant:** For pure activities, `(input_hash, output)` is a function — same input always memoises to same output.
(b) **Enforced:** Activity contract: idempotency by `input_hash` plus executor's transaction-id check.
(c) **Totality:** Memoised lookup is total over recorded activities.

### D9.3 — FSMState (per unit, per workflow)

1. **Canonical name:** `ValuationFSMState[u]` (Valuation §2 — eight-state FSM) and analogously the obligation FSM, the SBL state machine, etc.
2. **Definition:** Workflow-local current state in the typed FSM.
3. **Minimum field set:** State tag plus per-state metadata (e.g., `prev_record` in `Explained`).
4. **Identity:** `(workflow_id, unit_id, run_id)`.
5. **Provenance:** Workflow code, persisted via Temporal history.
6. **Temporal semantics:** Mutable workflow-local; reconstructible by history replay.
7. **Failure consequences:** Drift ⇒ same FSM transitions traversed in different order on replay (workflow non-determinism).

(a) **Invariant:** Transitions confined to the FSM's transition relation (Valuation §2 T1–T12); guards are pure predicates.
(b) **Enforced:** Type-level — closed-sum state tag with refined transition functions (each transition function takes a precondition proof object).
(c) **Totality:** `next_state(σ, e)` total iff `(σ, e)` is in the transition relation; otherwise rejected explicitly (no implicit fall-through).

---

## §11 — Tier D10: Capability / Identity (actors)

Listed in Ledger §15 open problem 11 ("Access control and actor attribution"). FORMALIS lifts this into a primary tier because every move and every transition presupposes an authorised actor.

### D10.1 — WalletRegistry / WalletMetadata

1. **Canonical name:** `WalletRegistry` (StatesHome line 96 — explicitly NOT state, but registry).
2. **Definition:** Per-wallet metadata: KYC, permissions, audit cursor, classification (real vs. virtual; Ledger §2.6).
3. **Minimum field set:** `{wallet_id: WalletId, classification: {Real, Virtual}, owner: Option[LegalEntity], parent_book: Option[BookId], external_account_map: Map[ExternalSystem, ExternalAccountId], permissions: PermissionSet, audit_cursor: EventStreamCursor, kyc_state: KycRecord, registered_at: Timestamp}`.
4. **Identity:** `wallet_id`.
5. **Provenance:** Onboarding workflow; KYC team.
6. **Temporal semantics:** Append-only versioned (KYC re-attestations append).
7. **Failure consequences:** Permission absent ⇒ executor cannot decide whether to accept a move proposed under a capability. Real/virtual misclassified ⇒ PnL wrong scope (Ledger §2.6).

(a) **Invariant:** Every wallet referenced in a move is registered; classification immutable (fix at registration).
(b) **Enforced:** Type-level — `RegisteredWallet` refined subtype; classification phantom-tagged.
(c) **Totality:** `wallet_meta(w) : WalletId → Option[WalletMetadata]`.

### D10.2 — ActorIdentity / SignerKey / Capability

1. **Canonical name:** `Actor` and `Capability`
2. **Definition:** Authenticated identity (human or service) and the typed capability object granting it the right to invoke a specific handler on a specific scope.
3. **Minimum field set:** Actor `{actor_id, role, organisation, signing_key_chain}`; Capability `{capability_id, holder: ActorId, granted_handlers: Set[HandlerId], granted_scope: ScopeRef, expiry: Option[Timestamp]}`.
4. **Identity:** `actor_id` and `capability_id`.
5. **Provenance:** Onboarding + role grant by IAM. Outside the ledger boundary in source-of-truth, but mirrored via attestations.
6. **Temporal semantics:** Append-only registry of grants and revocations.
7. **Failure consequences:** No actor attribution ⇒ no non-repudiation; maker-checker collapses; regulatory P9 capability scoping (C4 cross-overlay reads forbidden) cannot be enforced.

(a) **Invariant:** Every move and every state-delta carries a verified actor reference; revoked capabilities cannot mint new moves; capability scope respected (C4).
(b) **Enforced:** Type-level — moves and obligations carry a phantom-typed `Authorized[Capability]` token; runtime — signature verification on the executor entry path.
(c) **Totality:** `current_capability(actor, handler, scope, t)` total.

### D10.3 — KeyRegistry (cryptographic)

The signing key chain that validates oracle attestations, actor signatures, hash-chain integrity. Append-only, with revocation events.

---

## §12 — Mapping: User Floors ↔ FORMALIS Tiers

Demonstrates the redundancy/subsumption argument of §0:

| User floor | Maps to FORMALIS tier(s) | Note |
|---|---|---|
| 1. Static | D1 (Identity & Terms), partially D1.7 (Taxonomy enums) | Subsumed entirely by D1. |
| 2. Reference | D1.3, D1.4, D1.5, D1.6, D10 | Reference data is a *source* axis, not a *kind*. |
| 3. Market | D4 (raw observables), D5 (certified parameters) | The user's "Market" lumps together two tiers with very different mutation disciplines. |
| 4. Oracle | D4.2 (oracle attestation), D10.3 (key registry), D5 (Kalman intermediate) | Oracle is a *trust mechanism*, not a data category. |
| 5. Smart-contract execution | D6 (events/moves/state-deltas/CDM payload), D9 (workflow history), D8 (obligations) | The user's "execution" lumps together three tiers (event log, orchestration log, obligation registry) — exactly the conflation Ledger §14.4 warns against. |
| 6. Listed-instrument detail | D1.2 + D1.3 with `kind = LISTED_DERIV` or `EQUITY` | A specialisation of D1, not a separate floor. |

**FORMALIS recommendation:** retain the user's six floors as *secondary* presentation labels for non-technical readers, but use D1–D10 as the *primary* discipline-axis. Any tool, schema, audit, or property test should assert tier membership and tier-invariants.

---

## §13 — Cross-Cutting Invariants the Data Layer Must Enforce

Compiled here as a checklist for Phase 3 arbitration. Every entry has (a) the predicate, (b) the enforcement locus, (c) the totality consequence.

| # | Invariant | Locus | Totality consequence |
|---|---|---|---|
| I1 | **Conservation per unit per transaction** ($\sum_w \Delta w_t(u) = 0$) | Executor (D6.2 commit gate); proof per event class (C2) | `apply_txn` total iff conservation holds; otherwise rejected. |
| I2 | **Atomic commit** | Executor + WAL | `commit_txn` total under crash recovery. |
| I3 | **Referential integrity** (every `UnitId`, `WalletId`, `LegalAgreementId` resolves) | Executor + Unit Store (D1.1) | Move accessor partial without registration; total post-registration. |
| I4 | **Append-only event log + hash chain** | D6 storage layer | Integrity check total. |
| I5 | **Append-only ProductTerms; versioned amendments via Preserving/Breaking** (C6/C8) | D1.2 type system | `current_terms` total over registered units. |
| I6 | **UnitStatus registration-totality** (C5) | D2 registration handler | `unit_status` total over registered units. |
| I7 | **PositionState monotone-carrier + Option accessor** (C1) | D3 storage layer | `position_state` returns Option; `Some(zero)` ≠ `None`. |
| I8 | **Single-writer per field** (C11) | Type system + StateDelta typing (D6.3) | Field accessor total; writes from non-canonical handlers fail compile/runtime. |
| I9 | **Single-Coordinate Move Principle** (Ledger §15.2) | Move type (D6.1) parameterised by `Coordinate` | Conservation projection (`avail`) total by definition. |
| I10 | **Discharge predicate + compensation total** for every obligation (P21–P23) | D8 type system + Temporal liveness | Every obligation reaches a terminal state. |
| I11 | **Bitemporal coherence** (`vendor_time ≤ knowledge_time`; replay-by-snapshot reproducible) | D4 ingestion gate | Time-travel total over both axes. |
| I12 | **Calibration certification gate** ($x^* \in \Theta_{AF}$, residuals + WRMSE within tolerance) | D5 calibrator | `current_calibration` returns `Option[Certified]`. |
| I13 | **Model-consistent Jacobian + Valuation** (Remark 3.13) | D5 type system | PnL explain total under same `model_id`. |
| I14 | **CDM enum closed-world** at every pattern match | Closed enum types per CDM version | All handler accessors total. |
| I15 | **Capability scope respected** (C4 cross-overlay reads forbidden) | D10 type system + executor authz gate | Reads partial under wrong capability; total under correct scope. |
| I16 | **Determinism of arithmetic** (exact `Decimal`, never IEEE 754) | Numeric library choice (Ledger §5.1) | Replay produces bit-identical outputs. |
| I17 | **Deterministic oracle for replay** (D4.3 snapshots) | Snapshot store | Replay-by-snapshot total. |
| I18 | **Workflow code determinism** | Temporal contract | History replay total. |
| I19 | **Conservation of mandate-as-unit** ($w_{\mathrm{manager}}(u_{MA}) + w_{\mathrm{client}}(u_{MA}) = 0$, StatesHome §4.2) | Mandate registration handler | Standard issuance law total. |
| I20 | **Lifecycle stage monotonicity to absorbing terminal states** | D2 type system + state machine | `lifecycle_stage` evolution acyclic toward terminals. |

---

## §14 — Items the Specifications Currently Underspecify (FORMALIS gaps to flag)

Listed without claiming they break correctness today; they limit *what* invariants we can state and *where*.

1. **Tax-lot data** (Ledger §15 open). No tier currently houses it. FORMALIS recommends a sub-tier of D3 keyed by `(WalletId, UnitId, LotId)` with explicit identification methods (FIFO, LIFO, specific) declared at lot creation. Interaction with the futures `accumulated_cost` net-cost approach must be reconciled (the two are not commensurate without an explicit projection).
2. **XVA (CVA, DVA, FVA, MVA, KVA) adjustments.** No tier; not naturally a wallet move. FORMALIS recommends a separate tier D5.4 (`AdjustmentBucket`) keyed by `(LegalEntity, Counterparty, AdjustmentKind)`, conserved as moves between firm and an `xva_reserve` virtual wallet, with PnL clearly tagged.
3. **Impairment / ECL** (Ledger §15 open). Same shape as XVA — non-transfer accounting events. FORMALIS recommends a virtual `impairment_reserve` wallet and explicit moves so conservation P1 holds without bypass.
4. **Reference data lineage / vendor-version coexistence.** D1.3 declares it bitemporal; the spec does not state how `effective_at` from competing vendors is reconciled (e.g., if Bloomberg and ICE disagree on a holiday). FORMALIS recommends per-(source) registries with an explicit consensus or primary-source rule, and bitemporal tracking on each.
5. **PII / GDPR data class** (Ledger §15 open problem 9). FORMALIS recommends explicit tier D11 ("personal-data shadow store") separate from the immutable D6, with crypto-shredding key registry in D10.3 — as the user's open-problem text hints.
6. **Multi-entity / inter-company eliminations** (Ledger §15 open). No data category for the consolidation projection; FORMALIS recommends a derived projection in D7 with explicit elimination rules versioned in D1.
7. **Repo lifecycle data** (Ledger §15 open). The SBL six-coordinate vector covers part of it, but GMRA-specific terms (open-leg/close-leg pricing, substitution rights, buy-sell-back vs classic) are not yet typed. Cleanly fits D1.2 with `kind = REPO`.
8. **Pre-trade limit data** (Ledger §15 open). Constraint registry not in any tier today. FORMALIS recommends D1 sub-tier "LimitContract" — versioned, append-only, signed by Risk.
9. **Locate state** (Ledger §15.16). Two approaches sketched; neither is enforced by typing. FORMALIS recommends the time-limited-Unit approach and adds an explicit obligation D8 entry for locate-expiry.

---

## §15 — Verification Stance (statement of standards)

Per FORMALIS test (final passages of the system prompt), every category above is to be assessed against:

- **Specification:** Each datum has a stated proposition (the "Definition" line). No datum is included without one.
- **Types:** Each datum has either a closed sum, a refined record, a phantom-typed indexing, or a runtime-checked refinement (the "(b) Where enforced" line). No category is defended by mere convention.
- **Invariants:** Each tier has tier-level invariants and per-item invariants. Twenty cross-cutting invariants are compiled in §13.
- **Totality:** Every accessor's totality is stated either as unconditional (D1.5, D1.7, D8.2/3 predicates), conditional on registration (D1, D2), or explicitly partial via `Option` (D3, D4, D5, D7).
- **Determinism:** I16 (Decimal arithmetic), I17 (snapshot replay), I18 (workflow code) capture all three loci.
- **Composition:** D7 projections from D1–D6 are stated as pure functions; the substantiation argument (Ledger §8) holds iff each projection is regenerable from the journal — this is the per-item "regenerable from D1–D6" assertion.

— end of independent enumeration —
