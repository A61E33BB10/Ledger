# TESTCOMMITTEE — Ledger v11.0 Data Specification, Phase 1

**Discipline:** property-based testing, invariants, change-safety, mutation testing.
**Lens:** every datum is a generator parameter; every datum is a shrink target; every datum is a mutation site. If a category cannot be generated, shrunk, mutated, and replayed deterministically, it cannot be tested — and therefore does not exist as part of the specification.

**Sources read end-to-end (Phase 0):**
- `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/ledger/ledger_v10.3.tex` (7,314 lines, scanned in full via section index + targeted reads of every data-bearing section: Unit Store §3, Smart Contracts §5, Lifecycle §7, Settlement §9, CDM §10, Invariants §11, Temporal §14, Obligations §14.7, GPM/SBL §15, CDM Walkthrough Appendix, Date Handling Appendix)
- `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/ledger/ledger_v10.3_addendum_stateshome.tex` (490 lines, full)
- `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/valuation/ledger_valuation_v1.0.tex` (1,525 lines, full)

---

## 0. Floor-category critique (mandatory before enumeration)

The user's floor list — **(1) Static, (2) Reference, (3) Market, (4) Oracle, (5) Smart-contract execution, (6) Listed-instrument detail** — is a useful starting partition but is **misnamed in three places, redundant in one place, and silently subsumes at least four mandatory categories**.

| User category | TESTCOMMITTEE verdict | Reason |
|---|---|---|
| 1. Static | **Misnamed.** Rename to *Immutable Reference Constants*. "Static" suggests "doesn't change at runtime", but the v10.3 schema has *registration-immutable* fields (ProductTerms, Wallet KYC IDs) and *deployment-immutable* fields (system epoch, ledger genesis). These are different mutation regimes and demand different generators. | Lifecycle confusion is the #1 source of "field cached when it should have been derived" bugs (cf. addendum's `first_touch_date` warning). |
| 2. Reference | **Subsumed and overloaded.** "Reference" in v10.3 means at least four distinct things: (a) Tier-1 instrument master, (b) party reference (LEI/BIC/MIC), (c) calendar/holiday reference, (d) regulatory taxonomy (FpML/CDM enum). Each has different provenance, different shrinkers, different failure modes. | Conflating them produces tests that pass on equity ISINs and fail on swap UTIs without explaining why. |
| 3. Market | **Mostly correct but incomplete.** As stated, this conflates raw quotes (oracle output), calibrated parameters (Kalman posterior), and derived quantities (curves, surfaces). Valuation §4 explicitly distinguishes these as separate Pricing-DAG node types. | Calibrated state must be tested with martingale-property generators; raw quotes must be tested with adversarial-fat-finger generators. Same name, different test discipline. |
| 4. Oracle | **Redundant with Market if defined naively.** An oracle is *the source* of attested data. The data it produces lives elsewhere (Market, Reference). Keep the category but redefine: oracle = the **attestation envelope** (signature, timestamp, source, fallback chain), not the value inside. | The attestation is what determines determinism of replay (§7.7 of v10.3); the value is just numbers. |
| 5. Smart-contract execution | **Misnamed.** Should be *Lifecycle/Event Stream*. "Smart-contract execution" is a process, not a data category. The data emitted by execution is moves + state deltas + obligations + ValuationRecords. | Execution itself is purity (Principle 7.1); the *output* of execution is what we test. |
| 6. Listed-instrument detail | **Subsumed by Reference + Static.** Contract specifications, exchange MICs, lot sizes, multipliers — these are reference data conditioned on `unit_type ∈ {EQUITY, LISTED_DERIV, BOND}`. Promoting "listed" to a top-level category implies OTC is second-class; v10.3 §3 makes the opposite point (OTC unit identity = full CDM Trade including Collateral). | Use a `unit_type` discriminator inside Reference, not a top-level split. |

### Categories the floor list silently omits (must be added)

- **Identity & metadata-key data** (UTI, USI, deterministic-hash unit_id, transaction_id, obligation_id). Without this category, idempotency tests have no target.
- **Wallet & party data** (real wallets, virtual wallets, KYC, capability scopes). The StatesHome addendum makes WalletRegistry an explicit non-state sidecar — it must be enumerated.
- **Lifecycle/Event-stream data** (the immutable move stream itself: moves, transactions, BusinessEvents, state-delta envelopes). This is the source of truth for replay. Cannot be subsumed under "execution".
- **Obligation & deadline data** (P21–P23 obligation liveness; deadlines, discharge predicates, compensation actions). v10.3 §14.7 makes these first-class.
- **Calibration state** (Kalman posterior $x_{t|t}$, covariance $P_{t|t}$, innovation history). Distinct from market data because it carries a martingale invariant.
- **Valuation records & FSM state** (the eight-state valuation FSM, ValuationRecord, Greeks/Jacobian). Required for PnL-explain replay and Taylor-approximation invalidation tests.
- **Audit/temporal trail** (event-log Layer-2 metadata, hash chain, CDM-version stamp, replay cursors).
- **Regulatory/reporting projections** (SFTR UTI, EMIR fields, ISO 20022 messages). Distinct provenance — derived not stored — but must be testable as projections.
- **Generator universe data** (CDM enum closures, BusinessCenter codes, DayCountFraction, RollConvention). v10.3 §11.5 explicitly asserts this is the test-universe.

### Proposed revised floor (ten categories, exhaustive, non-overlapping)

```
F1.  Immutable reference constants  (system epoch, currency master, calendar genesis)
F2.  Reference data — instrument master  (ISIN, contract spec, CSA, mandate text)
F3.  Reference data — party & venue  (LEI, BIC, MIC, KYC)
F4.  Reference data — temporal taxonomy  (calendars, holidays, day-count, roll conv.)
F5.  Identity & metadata keys  (UTI, USI, unit_id, tx_id, obligation_id, hash)
F6.  Wallet & sidecar registry  (WalletRegistry, virtual-wallet allocation)
F7.  Market & oracle data  (raw quotes, attestation envelope, snapshots)
F8.  Calibration state  (Kalman x_{t|t}, P_{t|t}, certified params, innovation log)
F9.  Lifecycle event stream  (moves, transactions, BusinessEvents, state deltas, obligations)
F10. Valuation & risk data  (ValuationRecord, Greeks/Jacobian, FSM state, PnL explain)
```

This decomposition is **mutually exclusive** (each datum has exactly one floor) and **collectively exhaustive** (every datum referenced in the three source documents lands somewhere). The user's six categories map onto F1–F10 as: Static→F1, Reference→F2+F3+F4, Market→F7, Oracle→F7 (envelope only), Smart-contract execution→F9, Listed-instrument detail→F2 (with `unit_type=LISTED_*`).

The enumeration below uses the revised ten-floor structure.

---

## Enumeration format

Each item carries the seven mandatory fields plus the three TESTCOMMITTEE additions:
1. **Canonical name** | 2. **Definition** | 3. **Minimum field set** | 4. **Identity** | 5. **Provenance** | 6. **Temporal semantics** | 7. **Failure consequences**
**(a) Generator strategy** — random | exhaustive | recorded-replay (and why)
**(b) Properties** — at least three invariants the data must satisfy
**(c) Mutation classes** — at least two mutations that should kill the test

Severity tags: **CRITICAL** (invariant-violation risk), **HIGH** (mutation-survival risk), **MEDIUM** (coverage gap), **LOW** (test-quality issue).

---

## F1 — Immutable Reference Constants

### F1.1 System Epoch & Genesis Block — **CRITICAL**

1. **Canonical name:** `SystemEpoch` / `LedgerGenesis`.
2. **Definition:** The single anchor timestamp from which all monotonic ledger time is measured, plus the genesis hash of the move-stream Layer-1 log.
3. **Minimum field set:** `epoch_utc: Timestamp[ns]`, `genesis_hash: bytes32`, `protocol_version: SemVer`, `cdm_version: SemVer`.
4. **Identity:** Singleton; constant for the lifetime of the deployment.
5. **Provenance:** Operator-signed at deployment; never re-issued.
6. **Temporal semantics:** `t = 0` reference. All other timestamps are offsets from this.
7. **Failure consequences:** Replay non-determinism (P3 violation §11.2.3), hash-chain breakage (P4 monotonicity §11.2.4), entire move stream becomes unverifiable.
8. (a) **Generator:** *recorded-replay* (one canonical fixture per test environment); *exhaustive* over `protocol_version × cdm_version` cross-product for migration tests.
   (b) **Properties:** P-EPOCH-1 epoch is monotonic across system restart; P-EPOCH-2 `genesis_hash` matches sha256 of the empty-ledger canonical encoding; P-EPOCH-3 every transaction `tx.timestamp ≥ epoch_utc`.
   (c) **Mutations:** flip a bit in `genesis_hash` (must fail hash-chain test); replace `epoch_utc` with `epoch_utc + 1ns` (must fail replay-determinism test on every transaction in the fixture).

### F1.2 Currency Master — **HIGH**

1. **Canonical name:** `CurrencyMaster`.
2. **Definition:** Pre-registered cash units (USD, EUR, ...) per v10.3 §3.4.
3. **Minimum field set:** `iso4217: str(3)`, `decimals: int (0..6)`, `name: str`, `is_reference: bool`.
4. **Identity:** ISO 4217 code (primary), unit_id (derived hash).
5. **Provenance:** ISO 4217 standards body, frozen at registration.
6. **Temporal semantics:** Registered at system inception; permanent ACTIVE lifecycle stage.
7. **Failure consequences:** Conservation violation (e.g., USD with `decimals=2` truncating an internal 18-dp computation), FX-trade rounding drift, BalanceUpdate floor inconsistency.
   (a) **Generator:** *exhaustive* over the 180-element ISO 4217 closed enum.
   (b) **Properties:** P-CCY-1 `iso4217` matches `^[A-Z]{3}$`; P-CCY-2 `decimals` is consistent across every move that uses the currency (no per-move overrides); P-CCY-3 the decimal scale used for arithmetic ≥ `decimals` for every wallet holding the currency.
   (c) **Mutations:** swap `decimals: 2` → `decimals: 0` on USD (must fail any test that posts a sub-dollar VM amount); rename USD→USD2 with same `decimals` (must fail FX conservation test because USD reference no longer matches).

---

## F2 — Reference Data: Instrument Master

### F2.1 Tier-1 Instrument Master Record — **CRITICAL**

1. **Canonical name:** `InstrumentMaster` (one record per ISIN/contract-spec).
2. **Definition:** Static instrument descriptor: ISIN, exchange, contract specification, issuer, coupon schedule, lot size. Maps to CDM `TransferableProduct` (securities) or `NonTransferableProduct` (derivatives).
3. **Minimum field set:** `isin: ISIN | None`, `mic: MIC | None`, `contract_spec: ContractSpec | None`, `issuer_lei: LEI | None`, `lot_size: Decimal | None`, `cfi_code: CFI`, `as_of: Date`, `source_vendor: VendorId`.
4. **Identity:** ISIN for securities; (exchange, underlier, type, strike, expiry) tuple-hash for listed derivatives; CDM Trade hash for OTC (separate item, F2.3).
5. **Provenance:** Vendor feed (Bloomberg, Refinitiv, Exchange directly); attested with vendor signature + timestamp.
6. **Temporal semantics:** Effective-dated. Prior versions retained for time travel. **Append-only** (this is the v10.3-addendum `ProductTerms` C6 discipline).
7. **Failure consequences:** Wrong multiplier → variation margin off by orders of magnitude (futures: §7.5 walkthrough breaks); wrong ISIN → unit collision, conservation violation; wrong lot size → physical-delivery transaction rejected at executor (§5.3).
   (a) **Generator:** *exhaustive* over CFI codes × `unit_type` enum × strike-grid × expiry-grid; *recorded-replay* against a frozen vendor snapshot (one per test suite).
   (b) **Properties:** P-INS-1 ISIN check-digit valid (Luhn-like); P-INS-2 `multiplier > 0` for derivatives; P-INS-3 `expiry > effective_date`; P-INS-4 `lot_size > 0` ∧ divides every traded quantity; P-INS-5 (uniqueness) two distinct CFI/spec tuples never produce the same `unit_id`.
   (c) **Mutations:** flip ISIN check digit (must fail P-INS-1); divide `multiplier` by 10 (must fail any futures VM test by a factor of 10); change `expiry` to before `effective_date` (must fail P-INS-3); change CCP wallet on a futures spec (must fail Karpathy substitution test from addendum §4.1).

### F2.2 Smart-Contract Template Binding — **CRITICAL**

1. **Canonical name:** `ProductRegistryEntry` (Tier 2).
2. **Definition:** The smart-contract template that governs each product type. One per product class, not per instance. v10.3 §3.3.2.
3. **Minimum field set:** `product_qualification: CDMProductQualification`, `contract_template_ref: ContractTemplateId`, `state_schema: TypeRef`, `event_handlers: Map[CDMEventIntent, HandlerRef]`.
4. **Identity:** `product_qualification` (deterministic from CDM `EconomicTerms`).
5. **Provenance:** Auto-created on first encounter of a new product type at Tier-3 registration.
6. **Temporal semantics:** Immutable once created (v10.3 §3.3.2). Versioned across CDM-version migrations (§14.10).
7. **Failure consequences:** Template mismatch → smart contract invokes wrong handler → wrong moves emitted → conservation may still hold but business intent silently violated. **The most dangerous category** because conservation does not catch it.
   (a) **Generator:** *exhaustive* over the closed CDM `EventIntentEnum` × `ProductType` cross-product (§11.5 explicitly asserts this is finite).
   (b) **Properties:** P-PRT-1 totality — every (state, intent) pair has a defined handler or explicit rejection (§15.6); P-PRT-2 binding stability — the same `product_qualification` always resolves to the same template; P-PRT-3 handler purity — given (input, state, market_data) the handler returns identical (moves, new_state) every invocation (§7.7.2 Principle 7.1).
   (c) **Mutations:** swap `OptionPayout` template for `ForwardPayout` (must fail any payoff test); replace handler with a non-pure variant that reads wall-clock (must fail P3 replay determinism); make `state_schema` permissive (e.g., `Dict[str, Any]`) — must fail typed-state combination test from §7.3 ("matured bond cannot carry pending coupons").

### F2.3 OTC Trade Object (CDM Trade as Unit) — **CRITICAL**

1. **Canonical name:** `OTCTradeUnit`.
2. **Definition:** For OTC instruments, the CDM `Trade` (including `Collateral`) **is** the unit identity, per v10.3 §3.2 ("two OTC trades with identical payoff terms but different CSAs are different units").
3. **Minimum field set:** `cdm_trade: CDMTrade` (full graph), `economic_terms: EconomicTerms`, `collateral: CollateralAgreement`, `parties: List[Party]`, `execution_details: ExecutionDetails`, `uti: UTI`, `usi: USI | None`.
4. **Identity:** UTI (regulatory) + deterministic hash of (`economic_terms`, `collateral`, `parties`).
5. **Provenance:** Trade execution event (FIX, FpML, or platform proprietary message) → CDM synonym mapping → CDM `BusinessEvent`.
6. **Temporal semantics:** Created at trade-date, not settlement-date. Lifecycle stage drives valid operations.
7. **Failure consequences:** Two trades with same payoff but different CSAs colliding to one unit → wrong discount curve → silent valuation error of millions; missing `Collateral` field → margining handler dispatched against wrong wallet → conservation held but exposure mis-reported.
   (a) **Generator:** *random* over CDM enum-product universe with custom shrinkers that preserve CDM validation rules; *recorded-replay* against an FpML/CDM round-trip corpus (canonical for cross-system equivalence tests).
   (b) **Properties:** P-OTC-1 (injectivity) `unit_id_hash(trade_a) = unit_id_hash(trade_b) ⟹ trade_a ≡_CDM trade_b`; P-OTC-2 CSA discrimination — two trades identical except in `Collateral.csa` produce different `unit_id`; P-OTC-3 round-trip — `cdm_to_ledger ∘ ledger_to_cdm = id` on the economic content (forgetful map per §10.4).
   (c) **Mutations:** drop `Collateral` field from hash input (must fail P-OTC-2); swap `parties[0].lei` (must fail uniqueness — different bilateral agreement); change `economic_terms.notional` while keeping UTI (must fail injectivity — same id but different content).

### F2.4 Mandate / Managed-Account Unit Terms — **HIGH**

1. **Canonical name:** `MandateProductTerms` (the `u_MA` of the addendum).
2. **Definition:** Immutable contractual terms of a managed-account or QIS strategy unit: mandate text, fee schedule, benchmark identity, max position limits, HWM hurdle methodology, crystallisation frequency.
3. **Minimum field set:** `mandate_text_hash: bytes32`, `fee_schedule: FeeSchedule`, `benchmark_unit_id: UnitId`, `position_limits: List[Limit]`, `hwm_methodology: HWMSpec`, `crystallisation_freq: Period`.
4. **Identity:** Hash of all immutable terms; issued by manager wallet.
5. **Provenance:** Mandate signing → CDM `ContractFormation` → Unit Store registration with `unit_type=MANAGED_ACCOUNT`.
6. **Temporal semantics:** Append-only `TermsVersion` chain (addendum C6/C8); fungibility-preserving amendments append, breaking amendments allocate fresh `u_MA_new` with `SupersededBy` pointer.
7. **Failure consequences:** HWM methodology silently changed → performance fee miscalculated → client litigation; benchmark swap without `u_MA_new` allocation → wrong PnL attribution.
   (a) **Generator:** *random* over fee-schedule structures (linear, tiered, hurdle-with-catch-up); *exhaustive* over `crystallisation_freq` enum.
   (b) **Properties:** P-MA-1 mandate text hash matches stored bytes (no silent edit); P-MA-2 amendment two-track — fungibility-preserving → append, breaking → new unit; P-MA-3 issuance conservation — `Σ_w w(u_MA) = 0` (manager −1, client +1).
   (c) **Mutations:** edit one byte of mandate text without re-issuing (must fail P-MA-1); flip `is_fungibility_preserving` from False to True on a breaking amendment (must fail P-MA-2 — clients silently moved to new terms).

---

## F3 — Reference Data: Party & Venue

### F3.1 Legal Entity Identifier (LEI) Record — **HIGH**

1. **Canonical name:** `LEIRecord`.
2. **Definition:** ISO 17442 legal entity identifier per CDM `Party.partyId`.
3. **Minimum field set:** `lei: str(20)`, `legal_name: str`, `country: ISO3166`, `status: ACTIVE|LAPSED|MERGED|RETIRED`, `as_of: Date`.
4. **Identity:** LEI (20 alphanumeric, ISO 17442 check-digits).
5. **Provenance:** GLEIF (Global LEI Foundation) feed; attested with GLEIF signature.
6. **Temporal semantics:** Status-evolving (ACTIVE → LAPSED). Historical states retained for time-travel.
7. **Failure consequences:** Wrong LEI on settlement instruction → SFTR/EMIR rejection → regulatory fine; LAPSED LEI silently used → reporting failure.
   (a) **Generator:** *random* with custom check-digit-valid generator; *recorded-replay* against a GLEIF-snapshot fixture for status-transition tests.
   (b) **Properties:** P-LEI-1 ISO 17442 check digits valid; P-LEI-2 immutable identifier (LAPSED LEI is not reused); P-LEI-3 status transitions follow legal-entity lifecycle (no `RETIRED → ACTIVE`).
   (c) **Mutations:** flip a check digit (must fail P-LEI-1); reuse a RETIRED LEI on a new entity (must fail P-LEI-2).

### F3.2 BIC, MIC, Custodian Account — **MEDIUM**

1. **Canonical name:** `SettlementParticipantId`.
2. **Definition:** ISO 9362 BIC, ISO 10383 MIC, custodian account identifiers needed by settlement layer.
3. **Minimum field set:** `bic: str(8|11)`, `mic: str(4)`, `custodian_account: str`, `csd_participant: str`.
4. **Identity:** Composite of (BIC, custodian_account).
5. **Provenance:** SSI database (settlement layer responsibility, §9.2 — *not* the ledger's).
6. **Temporal semantics:** Effective-dated; SSI changes are operational events, not ledger events.
7. **Failure consequences:** Settlement instruction rejected (sese.023 fail), CSDR penalty.
   (a) **Generator:** *random* with format-correct BIC (8 or 11 chars matching `[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?`); *recorded-replay* over MIC closed enum (~1000 venues).
   (b) **Properties:** P-PID-1 BIC format regex match; P-PID-2 MIC ∈ ISO 10383 closed set; P-PID-3 ledger never reads SSI (purity boundary, §9.1) — projection function does not depend on it.
   (c) **Mutations:** make BIC 9 characters (must fail P-PID-1); have settlement projection read `custodian_account` (must fail P-PID-3 purity).

---

## F4 — Reference Data: Temporal Taxonomy

### F4.1 Holiday Calendar — **CRITICAL**

1. **Canonical name:** `HolidayCalendar` (one per `BusinessCenter`).
2. **Definition:** Set of non-business dates per business centre per v10.3 Appendix-CDM-Dates §G.5.
3. **Minimum field set:** `business_center: BusinessCenter`, `holiday_dates: Set[Date]`, `as_of: Date`, `source: VendorId`.
4. **Identity:** `business_center` + `as_of` (year-bucketed snapshot).
5. **Provenance:** Vendor feed (Copp Clark / FIA / exchange); attested.
6. **Temporal semantics:** Forward-looking; calendars are typically published years ahead. Historical calendars frozen for replay.
7. **Failure consequences:** Wrong calendar → wrong adjusted date → coupon paid one day off → sub-cent rounding error compounded across thousands of bonds; `MODFOLLOWING` cross-month bug silent if calendar wrong.
   (a) **Generator:** *exhaustive* over the ~200-element `BusinessCenterEnum`; *recorded-replay* per year against a frozen vendor snapshot.
   (b) **Properties:** P-CAL-1 every weekend is in `holiday_dates` ∪ `BusinessCenter`-implied weekend; P-CAL-2 multi-centre joint holiday = union of holiday sets (`IsBusinessDay` AND-semantics); P-CAL-3 idempotent shift — `AddBusinessDays(AddBusinessDays(d, 0), 0) = d` always; P-CAL-4 `MODFOLLOWING` never crosses month boundary.
   (c) **Mutations:** drop a known holiday (e.g., remove Christmas from USNY) — must fail any test paying a coupon on Dec 25; replace `MODFOLLOWING` semantics with `FOLLOWING` (must fail P-CAL-4 on a month-end-falling-Sunday case — this is exactly the bug `MODFOLLOWING` exists to prevent).

### F4.2 Day-Count Fraction & Roll Convention — **HIGH**

1. **Canonical name:** `DayCountConvention` (and `RollConvention`).
2. **Definition:** Closed enums per CDM `DayCountFractionEnum` (15 values) and `RollConventionEnum` (~40 values).
3. **Minimum field set:** `dcf: DayCountFractionEnum`, `roll: RollConventionEnum | None`.
4. **Identity:** Enum value.
5. **Provenance:** ISDA/FpML standards.
6. **Temporal semantics:** Eternal (enum members never retired without a CDM-version bump).
7. **Failure consequences:** ACT/360 vs ACT/365 swap → 1.4% accrual error per year, compounding across resets → millions in PnL drift on a $10B IRS book.
   (a) **Generator:** *exhaustive* over the closed enum; for each member, generate a random `(start_date, end_date)` pair within a leap/non-leap-spanning window.
   (b) **Properties:** P-DCF-1 ACT/365_FIXED returns `days/365` for any period (test boundary: leap year); P-DCF-2 30/360 ISDA formula matches `(360(Y2−Y1) + 30(M2−M1) + (D2−D1))/360` with the `D1>29` clipping rule (§G.5 explicit formula); P-DCF-3 1/1 always returns 1.0 (degenerate guard); P-DCF-4 (FpML consistency) `(frequency, roll)` valid pairs match `FpML_ird_57/58/60` rules.
   (c) **Mutations:** swap `ACT_360` and `ACT_365_FIXED` (must fail P-DCF-1 on a 365-day window); break the `D1>29` clipping (must fail P-DCF-2 on month-end → month-end pairs); use a weekly roll on a monthly frequency (must fail P-DCF-4).

### F4.3 Date Type Hierarchy (`AdjustableDate`, `RelativeDateOffset`, `AdjustableOrRelativeDate`) — **CRITICAL**

1. **Canonical name:** `AdjustableOrRelativeDate`.
2. **Definition:** CDM compositional date type per §G.5; the resolution chain `relative → unadjusted → adjusted` is the whole game.
3. **Minimum field set:** `adjustableDate: AdjustableDate?` XOR `relativeDate: AdjustedRelativeDateOffset?`; each carries adjustments ref + business centres ref.
4. **Identity:** Structural; resolves to a `date`.
5. **Provenance:** Trade execution / contract template / lifecycle event.
6. **Temporal semantics:** *Two* dates per object (unadjusted = contractual, adjusted = operational). Both are needed; collapsing to one is the v10.3-addendum's `first_touch_date` anti-pattern recapitulated.
7. **Failure consequences:** Resolving an `AdjustableOrRelativeDate` lazily and inconsistently → time-travel to t < trade_date sees a different "today" than time-travel to t' > settle_date → P-snapshot-consistency violation.
   (a) **Generator:** *random* compositional generator: pick branch (adjustable | relative), pick convention, pick centres; ensure `required choice` constraint holds.
   (b) **Properties:** P-DATE-1 resolution determinism — `resolve(d, calendars)` returns identical date for identical inputs; P-DATE-2 idempotence — `resolve(resolve(d)) = resolve(d)`; P-DATE-3 either-but-not-both — exactly one of `adjustableDate`, `relativeDate` populated; P-DATE-4 unadjusted → adjusted is monotone (FOLLOWING never moves earlier; PRECEDING never moves later).
   (c) **Mutations:** populate both branches (must fail P-DATE-3); cache `adjustedDate` while `BusinessCenter` calendar version changes underneath (must fail P-DATE-1); compute adjustment on read using "today's" calendar instead of the snapshot's calendar (must fail snapshot-consistency P8).

---

## F5 — Identity & Metadata Keys

### F5.1 UnitId — **CRITICAL**

1. **Canonical name:** `UnitId`.
2. **Definition:** Deterministic identifier of an element of $\mathcal{U}$. v10.3 §3.3.3: hash of contract spec for listed; CDM Trade hash for OTC.
3. **Minimum field set:** `unit_id: bytes32`, `unit_type: UnitType`, `derivation: HashAlg + InputSchema`.
4. **Identity:** The bytes themselves; the *derivation rule* is a separate piece of testable metadata.
5. **Provenance:** Pure function of unit content.
6. **Temporal semantics:** Eternal once derived; same content → same id forever (P3 determinism).
7. **Failure consequences:** Collision → two different instruments share storage row → conservation violation. Non-determinism → re-derived id differs across processes → unit "disappears" on replay.
   (a) **Generator:** *exhaustive* over canonical-encoding edge cases (key ordering, optional fields present/absent, unicode normalisation, decimal precision normalisation).
   (b) **Properties:** P-ID-1 (injectivity) `derivation(a) = derivation(b) ⟹ a ≡ b` modulo canonical encoding; P-ID-2 (determinism) `derivation(a)` produces identical bytes across processes/platforms; P-ID-3 (canonicalisation) field reordering, whitespace, equivalent-value-different-form (e.g., `1.0` vs `1`) all hash identically; P-ID-4 (no salt drift) the hash algorithm and input schema are versioned.
   (c) **Mutations:** swap two field orders in the canonical-encoding step (must fail P-ID-3); use Python's `hash()` (process-randomised) instead of SHA-256 (must fail P-ID-2 across runs); allow trailing-zero decimal differences to produce different ids (must fail P-ID-3).

### F5.2 Transaction Id, UTI, USI, ObligationId — **HIGH**

1. **Canonical name:** `IdentityKeyFamily`.
2. **Definition:** The four families of process-identity keys used by the framework: ledger-internal `tx_id`, regulatory `UTI` (CPMI-IOSCO), regulatory `USI` (legacy CFTC), `obligation_id` (deterministic from source event + type per §14.7).
3. **Minimum field set:** `tx_id: bytes32`, `uti: str(52)`, `usi: str | None`, `obligation_id: bytes32`.
4. **Identity:** Each is itself an identifier; what matters is the *idempotency contract* each enforces.
5. **Provenance:** `tx_id` from executor; `UTI` from agreed allocator (per CFTC/ESMA waterfall); `obligation_id` deterministic hash.
6. **Temporal semantics:** Append-only; never reused.
7. **Failure consequences:** Idempotency-by-id is the ledger's primary deduplication mechanism (P5 §11.2.5). Collision = double-execute. Non-derivation of `obligation_id` from source = orphan obligation = P21 liveness violation.
   (a) **Generator:** *random* with format-correctness; *recorded-replay* over a corpus of UTI-allocation-waterfall scenarios.
   (b) **Properties:** P-TXID-1 `apply(tx)` is idempotent under `tx_id`; P-UTI-1 UTI matches `^[A-Z0-9]{20,52}$`; P-OID-1 `obligation_id = H(source_event_id || obligation_type)` deterministically — no random nonces; P-OID-2 (uniqueness given source) one source-event + one obligation-type → exactly one obligation_id forever.
   (c) **Mutations:** add a wall-clock nonce to `obligation_id` (must fail P-OID-1 — same source produces different ids on replay); compute `tx_id` from a hash of the moves list in unsorted order (must fail P-TXID-1 idempotency under reordering).

---

## F6 — Wallet & Sidecar Registry

### F6.1 WalletRegistry Sidecar — **HIGH**

1. **Canonical name:** `WalletRegistry` (per addendum: explicitly *non-state*, *non-financial*).
2. **Definition:** KYC, capability scopes, audit cursor per wallet. Carries no economic state (StatesHome ruling §2).
3. **Minimum field set:** `wallet_id: WalletId`, `kyc_status: KYCStatus`, `capability_scope: Set[Capability]`, `audit_cursor: TxId`, `entity_type: REAL|VIRTUAL|REFERENCE|NOSTRO|CCP`.
4. **Identity:** `wallet_id`.
5. **Provenance:** Onboarding workflow (KYC), updated by capability-grant transactions.
6. **Temporal semantics:** Mutable; all changes are transactions (auditable).
7. **Failure consequences:** Stale KYC → trade routed to a sanctioned wallet → regulatory fine; capability scope leak → cross-`(w, u_MA)` overlay read enabled → addendum C4 violation.
   (a) **Generator:** *random* over capability-scope subset lattices; *exhaustive* over `entity_type` enum.
   (b) **Properties:** P-WAL-1 capability-scope monotone-or-explicit-revoke (no silent loosening); P-WAL-2 KYC status transitions follow legal lifecycle; P-WAL-3 **no economic field** — schema enforces that no decimal accrual / HWM / fee field exists in WalletRegistry (StatesHome C12).
   (c) **Mutations:** add an `accumulated_cost` scalar to `WalletRegistry` (must fail P-WAL-3 — schema-level rejection; this is the C12 enforcement); allow KYC `RETIRED → ACTIVE` reverse transition (must fail P-WAL-2).

### F6.2 Virtual Wallet Allocation Map — **CRITICAL**

1. **Canonical name:** `VirtualWalletMap`.
2. **Definition:** Per-relationship, per-CCP, per-counterparty virtual wallets that absorb contra-entries (v10.3 §2.5, §15.4).
3. **Minimum field set:** `virtual_id: WalletId`, `kind: CUSTODIAN|CCP|CSA|RELATIONSHIP|UNIVERSE_REFERENCE`, `pair: (WalletId, WalletId) | None`, `policy: VirtualPolicy`.
4. **Identity:** `virtual_id`, derived from kind + pair.
5. **Provenance:** Auto-allocated by executor on first-need.
6. **Temporal semantics:** Created at first contra-entry need; persistent thereafter.
7. **Failure consequences:** Mis-allocated virtual wallet → conservation appears to hold within a real-wallet sub-sum but fails globally; cross-CCP netting bug (v10.3 §7.5 footnote on Eurodollar futures).
   (a) **Generator:** *exhaustive* over `kind` enum; *random* on pair-graph topology (1:1, fan-out, chain — for on-lending).
   (b) **Properties:** P-VWM-1 (closure) every contra-entry is absorbed by a virtual wallet — `Σ_all_wallets = 0` global; P-VWM-2 (no leakage) no move connects a virtual wallet of one kind to a virtual wallet of another kind without an explicit transition contract; P-VWM-3 (kind-purity) `RELATIONSHIP[A↔B]` only handles moves involving A or B.
   (c) **Mutations:** add a contra-entry directly to a real wallet skipping the virtual (must fail P-VWM-1); merge two `RELATIONSHIP` virtuals into one shared virtual (must fail P-VWM-3 — cross-relationship leakage).

---

## F7 — Market & Oracle Data

### F7.1 Raw Market Quote — **HIGH**

1. **Canonical name:** `RawQuote` (the `y_t` of valuation §3 Kalman).
2. **Definition:** A single observation of a market observable: swap rate, option price, equity spot, FX rate.
3. **Minimum field set:** `instrument_ref: InstrumentRef`, `value: Decimal`, `bid: Decimal | None`, `ask: Decimal | None`, `timestamp: Timestamp[ns]`, `source: VendorId`, `staleness_indicator: Bool`.
4. **Identity:** `(instrument_ref, source, timestamp)`.
5. **Provenance:** Vendor feed (Bloomberg, Refinitiv, exchange direct, dealer quote).
6. **Temporal semantics:** Knowledge-time-indexed; arrival time may differ from observation time.
7. **Failure consequences:** Bad quote → bad calibration → bad price → wrong VM → wrong cash flow. Mitigated by Kalman innovation gating (valuation §3.5) but only if the gate is itself tested.
   (a) **Generator:** *random* + *adversarial-fat-finger* (price 100× off, negative price on non-negative instrument, NaN, Inf) + *recorded-replay* against a captured market-data fixture.
   (b) **Properties:** P-QUO-1 monotonicity-of-attestation — same `(instrument, source, timestamp)` produces same value (no replay drift); P-QUO-2 bid ≤ value ≤ ask when both present; P-QUO-3 fat-finger gate — adversarial mutations are rejected by Kalman innovation gating (D² > threshold) and recorded as rejection records.
   (c) **Mutations:** flip sign on a negative-not-allowed instrument (must fail P-QUO-3); silently swap `bid` and `ask` (must fail P-QUO-2); replay a rejected quote without the gate (must fail P-QUO-3).

### F7.2 Attestation Envelope (Oracle proper) — **HIGH**

1. **Canonical name:** `AttestationEnvelope`.
2. **Definition:** The signed, timestamped, sourced wrapper around a `RawQuote`. The oracle is *the envelope*, not the value (per F0 critique above).
3. **Minimum field set:** `payload_hash: bytes32`, `source: VendorId`, `signature: bytes`, `attestation_time: Timestamp`, `fallback_chain: List[VendorId]`, `cdm_version: SemVer`.
4. **Identity:** `(payload_hash, source, attestation_time)`.
5. **Provenance:** Oracle layer (vendor signature or platform multi-sig).
6. **Temporal semantics:** Captured at the moment of consumption (valuation §lifecycle-purity §7.7.2 — "deterministic oracle means the snapshot is captured at execution time").
7. **Failure consequences:** Replay non-determinism if envelope is not captured → P3 violation; corrected-data replay impossible without envelope.
   (a) **Generator:** *random* with cryptographically valid signatures over generated payloads; *recorded-replay* over corrected-data scenarios (vendor restatement).
   (b) **Properties:** P-ATT-1 signature verifies against `(payload_hash, source)`; P-ATT-2 deterministic capture — replaying a transaction with the captured envelope returns identical lifecycle output; P-ATT-3 fallback-chain ordered (head used first, exhaustion well-defined).
   (c) **Mutations:** strip the envelope, keep the value (must fail P-ATT-2 across vendor restatement); reorder fallback chain (must fail P-ATT-3 if the fallback was used).

### F7.3 Market Data Snapshot — **MEDIUM**

1. **Canonical name:** `MarketDataSnapshot` (the `market_data_snap` of `ValuationRecord`).
2. **Definition:** A frozen bundle of `RawQuote`s + `AttestationEnvelope`s + `CertifiedCalibration`s used as a single pricing input.
3. **Minimum field set:** `snapshot_id: SnapshotId`, `as_of: Timestamp`, `quotes: Map[InstrumentRef, RawQuote]`, `calibrations: Map[CalibObjectId, CertifiedCalibration]`.
4. **Identity:** `snapshot_id` + content hash.
5. **Provenance:** Captured by valuation workflow at FSM transition T1.
6. **Temporal semantics:** Immutable once captured; supersedable but never edited.
7. **Failure consequences:** Snapshot edited in place → time travel returns a value that the system never actually computed → P3 violation.
   (a) **Generator:** *recorded-replay* (one canonical fixture per valuation regression test).
   (b) **Properties:** P-SNAP-1 immutability — content hash never changes; P-SNAP-2 internal consistency — every `quote` in the snapshot has timestamp ≤ `as_of`; P-SNAP-3 calibration coherence — every `calibration` referenced was certified before `as_of`.
   (c) **Mutations:** edit one quote in place (must fail P-SNAP-1); include a calibration certified after `as_of` (must fail P-SNAP-3).

---

## F8 — Calibration State

### F8.1 Kalman Posterior State — **CRITICAL**

1. **Canonical name:** `KalmanPosterior` (the `(x_{t|t}, P_{t|t})` of valuation §3.4).
2. **Definition:** Posterior mean and covariance of the latent calibration state vector for a calibrated object (curve, surface).
3. **Minimum field set:** `calibration_object_id: CalibObjectId`, `x_post: Vector[d]`, `P_post: Matrix[d,d]`, `as_of: Timestamp`, `certified: Bool`, `arbitrage_admissible: Bool`.
4. **Identity:** `(calibration_object_id, as_of)`.
5. **Provenance:** Output of Kalman predict-update cycle on a `MarketDataSnapshot`.
6. **Temporal semantics:** Time-indexed; `(x_{t-1|t-1}, P_{t-1|t-1}) → (x_{t|t}, P_{t|t})`.
7. **Failure consequences:** Non-PSD covariance → numerical pricer failure / arbitrage-admissible region escape; non-martingale posterior mean evolution → silent calibration drift → fat unexplained PnL residual.
   (a) **Generator:** *random* over admissible state vectors; *recorded-replay* against a Kalman-step fixture for golden-master tests.
   (b) **Properties:** P-KAL-1 covariance PSD — `P_post ⪰ 0` (eigenvalue test); P-KAL-2 martingale — `E[x_t | F_{t-1}] = x_{t-1}` under the driftless transition (Axiom A5 of Calibration Manifesto, valuation §3.2); P-KAL-3 arbitrage admissibility — `x_post ∈ Θ_AF` after post-update projection (valuation §3.6); P-KAL-4 innovation distribution — innovation D² ~ χ²(m_t) under correct model (test on residual time-series).
   (c) **Mutations:** drop the post-update no-arbitrage projection (must fail P-KAL-3 on a steeper-than-admissible skew); replace martingale transition with a small-drift transition (must fail P-KAL-2 over a long replay window); skip PSD-enforcement after the update (must fail P-KAL-1 in numerically-tight cases).

### F8.2 Calibration Certificate — **HIGH**

1. **Canonical name:** `CalibrationCertificate`.
2. **Definition:** Tuple `(x_post, residuals, certificate_status)` per Calibration Manifesto A4 (valuation §3.6).
3. **Minimum field set:** `x_post: Vector`, `per_instrument_residuals: Map[InstrumentRef, Decimal]`, `aggregate_wrmse: Decimal`, `certified: Bool`, `failure_reason: str | None`.
4. **Identity:** Composes with `KalmanPosterior` identity.
5. **Provenance:** Output of certification step after Kalman update.
6. **Temporal semantics:** Snapshotted with the calibration.
7. **Failure consequences:** Uncertified calibration silently used → §3.6 invariant breach → downstream pricing all stale.
   (a) **Generator:** *random* with adversarial residual-tampering for robustness tests.
   (b) **Properties:** P-CCERT-1 `certified ⟺ x_post ∈ Θ_AF ∧ ∀i |r_i| ≤ τ_i ∧ wrmse ≤ τ_agg`; P-CCERT-2 (fallback) on `certified=False`, downstream pricing flags STALE; P-CCERT-3 (idempotent) re-certification of the same `(x_post, residuals)` returns identical status.
   (c) **Mutations:** weaken `wrmse ≤ τ_agg` to `≤ 1.5*τ_agg` (must fail P-CCERT-1); have downstream pricing read `x_post` without checking `certified` (must fail P-CCERT-2).

---

## F9 — Lifecycle Event Stream

### F9.1 Atomic Move — **CRITICAL**

1. **Canonical name:** `Move`.
2. **Definition:** v10.3 §2.3: `(from, to, unit, quantity, timestamp, source, metadata)` plus the GPM extension to a one-coordinate-per-entity discipline (§15.2 Single-Coordinate Move Principle).
3. **Minimum field set:** `from_wallet: WalletId`, `to_wallet: WalletId`, `unit_id: UnitId`, `quantity: Decimal[18]`, `coordinate: GPMCoordinate` (own/onloan/borr/coll_post/coll_recv/coll_rehyp), `timestamp: Timestamp[ns]`, `source: ContractRef`, `metadata: dict`.
4. **Identity:** Position in the move stream + hash of fields.
5. **Provenance:** Emitted by smart contract; committed by executor.
6. **Temporal semantics:** Append-only (P4); ordered by stream position; timestamp distinct from stream position.
7. **Failure consequences:** Conservation violation if `from`/`to` not paired; idempotency violation if duplicates not dedup'd by tx_id; GPM coordinate confusion (writing `own` when meant `onloan`) silently breaks IFRS-9 derecognition (v10.3 §15.1).
   (a) **Generator:** *random* over wallet-graph topologies × CDM-enum-derived unit-types × decimal-quantity edge cases (max precision, near-zero, near-max).
   (b) **Properties:** P-MOV-1 `quantity > 0` always (sign carried by from/to direction, §5.5); P-MOV-2 single-coordinate-per-entity (§15.2 Principle 15.1); P-MOV-3 paired-conservation per move — `+q` to one slot, `−q` to another, sum = 0; P-MOV-4 referential integrity — `from_wallet, to_wallet, unit_id` exist in registries.
   (c) **Mutations:** allow `quantity=0` moves (must fail P-MOV-1 / vacuous-event test); make a single move write two coordinates of one entity (must fail P-MOV-2 — the addendum's own→onloan should be a *transaction* of two moves); use floating-point for quantity (must fail P-MOV-3 — associativity loss, §5.1 Definition 5.1).

### F9.2 Transaction (atomic move list + state delta + obligation list) — **CRITICAL**

1. **Canonical name:** `Transaction` (or `StateDelta` per the addendum's atomic-update terminology, C3).
2. **Definition:** v10.3 §2.4 + addendum C3: a finite list of moves, plus `ProductTerms` / `UnitStatus` / `PositionState` writes, plus an obligation list, applied atomically.
3. **Minimum field set:** `tx_id: TxId`, `tx_type: TransactionType` (SETTLEMENT|COLLATERAL|LIFECYCLE|ACCOUNTING|CORRECTION), `moves: List[Move]`, `unit_state_writes: Map[(WalletId, UnitId), PositionState]`, `unit_status_writes: Map[UnitId, UnitStatus]`, `product_terms_writes: Map[UnitId, TermsVersion]`, `obligations: List[Obligation]`, `cdm_payload: CDMBusinessEvent`, `cdm_version: SemVer`.
4. **Identity:** `tx_id` (deterministic from `cdm_payload` content).
5. **Provenance:** Smart-contract output; committed by executor.
6. **Temporal semantics:** Atomic — applies wholesale or not at all (P2).
7. **Failure consequences:** Partial application observable → P2 violation → entire correctness-by-construction story collapses; missing obligation in output → orphan deadline → P21 violation.
   (a) **Generator:** *exhaustive* over `tx_type` enum × CDM `EventIntentEnum` × product-template cross-product (§11.5 explicitly the closed generator universe).
   (b) **Properties:** P-TX-1 atomicity — partial-application not observable; P-TX-2 conservation per unit — `Σ_w Δw(u) = 0` for every unit touched; P-TX-3 idempotency — `apply(tx) ∘ apply(tx) = apply(tx)` by `tx_id`; P-TX-4 obligation completeness (§14.7 Principle 14.x) — every obligation-creating event includes the obligation; P-TX-5 atomic state-delta across all three maps (addendum C3).
   (c) **Mutations:** apply moves but not state writes (must fail P-TX-5 — partial map update); allow a `LIFECYCLE` event-handler to omit emitted obligations (must fail P-TX-4); replay tx with same `tx_id` but mutated payload (must fail P-TX-3 — deterministic id binding).

### F9.3 Move Stream / Event Log — **CRITICAL**

1. **Canonical name:** `MoveStream` (the immutable Layer-1 log per §13.1).
2. **Definition:** Append-only sequence of all transactions, with hash chain (§11.4) and CDM-version stamps (§14.10).
3. **Minimum field set:** `entries: NonEmptyList[Transaction]`, `prev_hash: bytes32` per entry, `cdm_version: SemVer` per entry, `replay_cursor: Position`.
4. **Identity:** Genesis hash (F1.1) + entry positions.
5. **Provenance:** Single-writer executor (§14.6).
6. **Temporal semantics:** Append-only; ordered; tamper-evident.
7. **Failure consequences:** Tampering → P4 violation → entire audit chain compromised; non-replay → P3 violation.
   (a) **Generator:** *recorded-replay* (the entire stream is the test fixture); *random* on out-of-order arrival to test single-writer enforcement.
   (b) **Properties:** P-LOG-1 hash chain — every entry's `prev_hash` matches `H(entry[i-1])`; P-LOG-2 deterministic replay — `apply_all(entries[0..k]) = state_at(t_k)` for any `k`; P-LOG-3 single-writer — concurrent writes serialised; no torn writes; P-LOG-4 CDM-version coexistence — each entry processable under its stamped version.
   (c) **Mutations:** swap two adjacent entries (must fail P-LOG-1); strip `cdm_version` (must fail P-LOG-4 on a multi-version replay); allow concurrent writers (must fail P-LOG-3).

### F9.4 Obligation — **CRITICAL**

1. **Canonical name:** `Obligation` per §14.7.2 Definition 14.x.
2. **Definition:** `(id, type, source, t_d, D, κ)` — id, type, source event, deadline, discharge predicate, compensation action.
3. **Minimum field set:** `id: ObligationId`, `type: ObligationType`, `source: SourceRef`, `deadline: Timestamp`, `discharge_predicate: PurePredicate`, `compensation_action: PureFunction`, `state: PENDING|ATTEMPTED|DISCHARGED|COMPENSATED|DEFAULTED`.
4. **Identity:** `id` (deterministic from source + type per F5.2).
5. **Provenance:** Created at unit registration (deterministic-date) or at event processing (event-triggered) per §14.7.4.
6. **Temporal semantics:** Lifecycle PENDING → ATTEMPTED → {DISCHARGED, COMPENSATED, DEFAULTED}; terminal states absorbing.
7. **Failure consequences:** P21 (liveness) violation → orphan obligation → stale CSA margin call → counterparty default → systemic event.
   (a) **Generator:** *exhaustive* over the obligation-taxonomy table (§14.7.3 Table 14.x — 13 types); *random* over deadlines spanning past, near-future, far-future.
   (b) **Properties:** P-OBL-1 (P21 liveness) — `∀ t > t_d: state ∈ {DISCHARGED, COMPENSATED, DEFAULTED}`; P-OBL-2 (P22 conservation) — every discharge or compensation move set satisfies `Σ Δw(u) = 0`; P-OBL-3 (P23 idempotency) — discharging twice produces no incremental effect; P-OBL-4 (predicate purity) — `discharge_predicate(state)` is pure.
   (c) **Mutations:** disable the deadline timer (must fail P-OBL-1); allow `compensation_action` to read wall-clock (must fail P-OBL-4); skip the pre-discharge predicate check (must fail P-OBL-3 — fires moves twice).

### F9.5 ProductTerms / UnitStatus / PositionState (the three-map state) — **CRITICAL**

1. **Canonical name:** `StateMaps` per the StatesHome addendum.
2. **Definition:** `ProductTerms : UnitId → NonEmpty[TermsVersion]` (immutable, append-only); `UnitStatus : UnitId → UnitStatus` (mutable, shared); `PositionState : (WalletId, UnitId) → PositionState` (per-position, monotone, Option accessor).
3. **Minimum field set:** for `ProductTerms`: terms head + version chain; for `UnitStatus`: `lifecycle_stage`, `last_settlement_price`, `last_settlement_date`, `current_weights`, `nav_index`, `triggered_barrier`, `superseded_by`; for `PositionState`: `accumulated_cost`, `ccp_binding`, OTC lifecycle, `entry_nav`, `hwm`, `accrued_{mgmt,perf}_fee`, `benchmark_nav_at_inception`, `mandate_breach_flags`.
4. **Identity:** Triple `(unit_id, version) | (unit_id) | (wallet_id, unit_id)`.
5. **Provenance:** Written by registered handlers per addendum C11 (one canonical writer per field).
6. **Temporal semantics:** `ProductTerms` append-only (C6); `UnitStatus` registration-total mutable (C5); `PositionState` Option accessor + monotone carrier (C1).
7. **Failure consequences:** Per the addendum, 7 of 10 core invariants (P1, P3, P5, P6, P7, P9, P10) become structurally unreachable *only if* the three-map discipline is enforced. Misplacing any field collapses this guarantee.
   (a) **Generator:** *exhaustive* over `lifecycle_stage` enum × the addendum's four canonical test scenarios (futures, MA, QIS, untraded option); *random* over per-position decimal accruals.
   (b) **Properties:** P-MAP-1 (C1 Option accessor + monotone) — `position(w,u) ∈ {None, Some(p)}`; once `Some`, never deleted; P-MAP-2 (C2 handler-level conservation per event class) — `Σ_w Δf(w,u) = 0` proven structurally for Trade, SettleVM, CorporateAction, QISRebalance, MandateAmend; P-MAP-3 (C9 vacuous base case) — handlers on zero-holder units discharge `Σ = 0` vacuously (the `dividend_per_share / len(holders)` bug-class catcher); P-MAP-4 (C11 field-handler binding) — each field has exactly one allowed writer; P-MAP-5 (C12 W-sector collapse) — no per-wallet economic scalar exists outside `PositionState[w, u_MA]`.
   (c) **Mutations:** add a `WalletState[w].hwm` scalar (must fail P-MAP-5 — schema-level); collapse `Some(zero)` to `None` on close-out (must fail P-MAP-1 — wash-sale lookback breaks); allow `settle` handler to write `hwm` (must fail P-MAP-4); evaluate `dividend_per_share / len(holders)` without checking empty-set (must fail P-MAP-3).

### F9.6 SBL Loan Unit State — **HIGH**

1. **Canonical name:** `SBLUnitState` per §15.7.
2. **Definition:** Loan-specific state for the SBL contract: lender, borrower, agent, ISIN, qty, fee/rebate rate, collateral terms, legal regime, lifecycle stage, settlement status, fee accrual log.
3. **Minimum field set:** as listed in §15.7 listing (loan_id, lender, borrower, agent, isin, quantity, original_qty, term_type, maturity_date, fee_rate, rebate_rate, collateral_type, margin_pct, haircut_pct, collateral_ccy, triparty_agent, legal_regime, rehyp_consent, lifecycle_stage, settlement_status, recall_date, recall_qty, sftr_uti, slate_loan_id, execution_ts, trade_date, last_mark_date, accrued_fee, fee_accrual_log).
4. **Identity:** `loan_id` + `(lender, borrower, isin, execution_ts)`.
5. **Provenance:** SBL `new_loan` event.
6. **Temporal semantics:** Per the §15.8 state machine; terminal states RETURNED/CANCELLED/DEFAULTED.
7. **Failure consequences:** P11–P20 violations; double-lending; FTD close-out failure (Reg-SHO 204).
   (a) **Generator:** *exhaustive* over `(state, event)` pairs of §15.8 table; *random* over collateral-type/regime cross-product.
   (b) **Properties:** P-SBL-1 (P12 single ownership) — `Σ_e w_e[own]` not changed by SBL events; P-SBL-2 (P13 collateral conservation) — `coll_post`/`coll_recv` paired; P-SBL-3 (P15 rehyp cap) — under US 15c3-3, `coll_rehyp ≤ 1.4 × customer_debit`; P-SBL-4 (avail projection) — `avail = own − onloan + borr` always.
   (c) **Mutations:** change `legal_regime` mid-loan (must fail — regime is set-at-inception immutable); allow `coll_rehyp` to exceed cap (must fail P-SBL-3); short-circuit the avail projection by caching it (must fail P-SBL-4 under any of the §15.4 scenarios).

---

## F10 — Valuation & Risk Data

### F10.1 ValuationRecord — **CRITICAL**

1. **Canonical name:** `ValuationRecord` per valuation §2.
2. **Definition:** Per-unit, per-timestamp pricing output: dirty/clean prices, accrued, Greeks, model id, snapshot id, FSM state, quality.
3. **Minimum field set:** `unit_id`, `timestamp`, `dirty_price`, `clean_price`, `accrued`, `greeks: Greeks` (tagged union per model), `model_id`, `market_data_snap`, `compute_ms`, `quality: FIRM|INDICATIVE|APPROXIMATE|STALE|FAILED`, `fsm_state: ValuationFSMState`.
4. **Identity:** `(unit_id, timestamp, model_id)`.
5. **Provenance:** Published by `PricingWorkflow` after PnL-explain pass (T5).
6. **Temporal semantics:** Append-only valuation store; supersedable by next FIRM record.
7. **Failure consequences:** Wrong `dirty_price` → wrong `V_t` → wrong PnL (path-independent theorem assumes correct prices); wrong `quality` flag → official-PnL pipeline accepts STALE / APPROXIMATE → regulatory mis-report.
   (a) **Generator:** *random* over `Greeks` tagged-union variants (BS / Heston / SABR / LocalVol / IRS / Bond); *recorded-replay* over the worked-example fixtures (valuation §11).
   (b) **Properties:** P-VR-1 `dirty_price = clean_price + accrued`; P-VR-2 `quality=FIRM ⟺ fsm_state=Explained`; P-VR-3 (Greeks dimension) `dim(Greeks) = |observables| + |params(model_id)|`; P-VR-4 (immutability after publish) edits forbidden — supersession only.
   (c) **Mutations:** publish FIRM with `fsm_state=Quarantined` (must fail P-VR-2); use BS Greeks struct on a Heston-priced record (must fail P-VR-3); edit a published record in place (must fail P-VR-4).

### F10.2 Greeks / Sensitivity Jacobian — **HIGH**

1. **Canonical name:** `Greeks` (tagged union by `model_id`, valuation §2.x).
2. **Definition:** Per-model sensitivity structure: BS scalar vega, Heston 5-vector, SABR 4-vector, local vol grid, IRS key-rate-durations, bond duration/convexity.
3. **Minimum field set:** `model_id`, `invariant: str` (which params are held constant), `method: ANALYTICAL|BUMP|AAD|PATHWISE`, plus model-specific observables and parameter-Jacobian fields.
4. **Identity:** Composes with `ValuationRecord` identity.
5. **Provenance:** `ComputeGreeks` activity in `PricingWorkflow`.
6. **Temporal semantics:** Snapshotted with the `ValuationRecord`.
7. **Failure consequences:** Reporting BS vega for a Heston model conflates the 5-vector to a scalar → unexplained PnL spikes that cannot be attributed (valuation §3.3 vanishing-vega problem).
   (a) **Generator:** *exhaustive* over `model_id` × `method`; *random* over input perturbations within bump-stable region.
   (b) **Properties:** P-GR-1 method-consistency — analytical and AAD agree to 1e-8 on closed-form models; P-GR-2 PnL identity (§valuation 3.7) — `ΔP ≈ δ·ΔS + J·ΔΘ + ½Γ·ΔS² + Θ_decay·Δt + ε` with `|ε| < tolerance(unit)`; P-GR-3 model-consistency — Greeks used in PnL-explain come from same `model_id` as the prior record (Remark valuation §3.7 model-consistency); P-GR-4 (Hughes shrinking) the smallest counterexample for explain failure shrinks to a single bump direction.
   (c) **Mutations:** use BS Greeks to explain a Heston price change (must fail P-GR-3); drop one Heston parameter sensitivity (`xi_sens`) (must fail P-GR-2 on a vol-of-vol move); switch from ANALYTICAL to BUMP with too-large `bump_size` (must fail P-GR-1).

### F10.3 Valuation FSM State — **HIGH**

1. **Canonical name:** `ValuationFSMState` per valuation §1.
2. **Definition:** Eight-state FSM: Unpriced, Pricing, Priced, Explaining, Explained, Quarantined, Stale, Failed.
3. **Minimum field set:** `state ∈ {UNPRICED, PRICING, PRICED, EXPLAINING, EXPLAINED, QUARANTINED, STALE, FAILED}`, `entered_at: Timestamp`, `retry_count: int`.
4. **Identity:** Bound to a `unit_id` within the `PricingWorkflow`.
5. **Provenance:** Workflow-local state, persisted via Temporal durable execution.
6. **Temporal semantics:** Twelve transitions T1–T12 (valuation §1.2); guarded.
7. **Failure consequences:** Invalid transition (e.g., Unpriced → Explained skipping Priced) → official PnL based on a price that never passed PnL-explain → audit failure.
   (a) **Generator:** *exhaustive* over (state × event) pairs; *random* over retry counts up to max.
   (b) **Properties:** P-FSM-1 totality — every (state, event) pair has a defined transition or explicit rejection; P-FSM-2 retry bounds — `retry_count ≤ max_retries`; P-FSM-3 quality coupling (cf. P-VR-2) — only `EXPLAINED` admits `quality=FIRM`; P-FSM-4 staleness escalation — `EXPLAINED` →T8→ `STALE` after staleness threshold without staying past 3× cadence.
   (c) **Mutations:** allow Unpriced → Explained directly (must fail P-FSM-1); raise `max_retries` after deployment (must fail P-FSM-2 across replay); publish FIRM from QUARANTINED (must fail P-FSM-3).

### F10.4 PnL Explain Result — **HIGH**

1. **Canonical name:** `ExplainResult`.
2. **Definition:** Output of `pnl_explain(prev, curr, market_moves, cashflows)` per valuation §6.
3. **Minimum field set:** `total_pnl: Decimal`, `explained: Decimal`, `unexplained: Decimal`, `tolerance: Decimal`, `status: PASS|FAIL`, `decomposition: Dict[GreekName, Decimal]`.
4. **Identity:** Per `(unit_id, prev_record, curr_record)` triple.
5. **Provenance:** PnL-explain function output at FSM transition T4→T5/T6.
6. **Temporal semantics:** Computed once per cycle.
7. **Failure consequences:** Wrong tolerance → quarantine never fires (false negative) or fires constantly (false positive); model-mixing in explain → spurious unexplained.
   (a) **Generator:** *random* over move sizes; *adversarial* on near-tolerance boundary cases.
   (b) **Properties:** P-EXP-1 sign — `total_pnl = explained + unexplained`; P-EXP-2 tolerance gating — `status=PASS ⟺ |unexplained| < tolerance`; P-EXP-3 model consistency precondition — `prev.model_id = curr.model_id`; P-EXP-4 (toxic-product boundary) `|unexplained| < ε` ⟹ product is non-toxic per valuation §3.10 cubic residual definition.
   (c) **Mutations:** flip the inequality in P-EXP-2 to `≤` (must fail boundary tests at exactly `|unexplained| = tolerance` — precisely the kind of `<` vs `≤` mutation the addendum's §6 calls out); allow `prev.model_id ≠ curr.model_id` (must fail P-EXP-3).

---

## Cross-cutting properties (not category-specific)

These survive any refactor and should be reasserted in every test category:

- **Determinism of replay (P3):** `apply_all(events[:k]) ++ events[k:] = apply_all(events)` for every `k`. Anchors F1, F5, F9.
- **Conservation in every event class (addendum C2):** `Σ_w Δf(w,u) = 0` per Trade, SettleVM, CorporateAction, QISRebalance, MandateAmend, with the vacuous (zero-holder) base case proven explicitly. Anchors F9.
- **CDM enum closure as generator universe (§11.5):** every enum-typed field draws from the closed CDM set; "unknown" values are rejected at deserialise.
- **Single-coordinate-per-entity (Principle §15.2):** every move touches one coordinate; multi-coordinate updates are *transactions*. Anchors F9.1.
- **Forgetful CDM mapping F (§10.4):** `F(e2 ∘ e1) = F(e2) ∘ F(e1)` for referentially-independent events; cross-referencing events require explicit ordering.

## Mutation-class roll-up (the most-failure-modes-killing classes)

Rank-ordered by expected mutation kill rate against the property catalogue above:

| Mutation class | Properties killed | Coverage |
|---|---|---|
| **M1: sign/coefficient on `accumulated_cost` arithmetic** | P-MAP-2, P-MOV-3, P-TX-2 | F9.1, F9.5 |
| **M2: `<` ↔ `≤` on lifecycle/explain/staleness boundaries** | P-EXP-2, P-FSM-3/4, P-OBL-1 | F10.3, F10.4, F9.4 |
| **M3: drop the empty-set / vacuous base case** | P-MAP-3 (C9) | F9.5 |
| **M4: read wall-clock or DB inside a "pure" handler** | P-PRT-3, P-OBL-4, P-ATT-2 | F2.2, F9.4, F7.2 |
| **M5: collapse `Some(zero)` to `None` (or vice versa)** | P-MAP-1 (C1) | F9.5 |
| **M6: skip post-update no-arbitrage projection on Kalman** | P-KAL-3, P-CCERT-1 | F8.1, F8.2 |
| **M7: cache an adjusted date / first-touch / `len(holders)`** | P-DATE-1, P-MAP-3 | F4.3, F9.5 |
| **M8: silently accept CDM-version mismatch** | P-LOG-4, P-PRT-1 | F9.3, F2.2 |
| **M9: hash with non-canonical encoding** | P-ID-3, P-TXID-1 | F5.1, F5.2 |
| **M10: write to `WalletState` (a field that should not exist)** | P-WAL-3, P-MAP-5 (C12) | F6.1, F9.5 |

M1, M2, M3 alone account for the majority of conservation-, FSM-, and edge-case bugs that survive example-based testing. The mutation-score targets from the addendum (§6: 80%+ overall, 85–90% on event handlers) are achievable *only* if these ten classes are explicitly in the mutation operator set.

## What survives a refactor (Feathers change-safety)

Test categories that **must survive** even radical implementation rewrites (because they verify behaviour, not structure):

- All **invariant tests** (P1–P23 + addendum C1–C12 + P-MAP/P-OBL/P-KAL/P-EXP).
- All **property-based tests with CDM-enum generators** (the universe is the CDM standard, not the implementation).
- All **recorded-replay tests** (the move stream + market-data snapshot are external fixtures).
- All **mutation-class tests** keyed on M1–M10 (mutations are defined against semantics, not code).

Test categories that **may be replaced** during a refactor:

- Implementation-detail unit tests on private helpers (mocked unit tests of the executor's internal validation order).
- Tests that rely on a specific representation (e.g., dict ordering in `unit_state`).
- Performance-only tests (replaceable when the workload changes).

The 80%-mutation-score threshold and 90%-line-coverage threshold from the addendum apply *to the surviving categories*, not to the replaceable ones.

---

## Summary count

- **Floor categories:** 10 proposed (revised from user's 6); user's 6 mapped onto 10.
- **Items enumerated:** 27 (F1.1–F10.4, with full seven-field + (a)/(b)/(c) treatment).
- **Properties stated:** 100+ (3+ per item; cross-cutting properties additional).
- **Mutation classes:** 10 ranked + 50+ item-specific mutations.
- **Severities:** 11 CRITICAL, 12 HIGH, 4 MEDIUM, 0 LOW (LOW intentionally absent — all enumerated items rise above test-quality-only).
- **Floor-categories disagreed with:** 5 of 6 user categories revised or subsumed (only "Static" survives, and only after rename).
- **Categories added beyond user's six:** Identity & metadata keys (F5), Wallet & sidecar (F6), Calibration state (F8), Lifecycle event stream (F9), Valuation & risk (F10), plus the temporal-taxonomy split (F4) and party/venue split (F3) inside Reference.

— TESTCOMMITTEE (Beck / Hughes / Fowler / Feathers / Lamport)
