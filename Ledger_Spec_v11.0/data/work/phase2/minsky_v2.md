# Ledger v11.0 Data Specification — Phase 2 (MINSKY) — v2

**Discipline.** Type-driven design at the data layer. Parse, don't validate.
Make illegal states unrepresentable. Total functions over typed inputs.
Closed sums everywhere a free string is tempting. Refinements over bare
scalars. Sum types over booleans-and-comments. **No ellipsis in any
sum-type listing.**

**Idiom.** OCaml-flavoured pseudocode for nominal sums and refinements.
Where Rust's `Result` / refinement traits or Python's runtime checker
discipline maps more cleanly, I note it. The Python deployment target
matters: nominal phantom types in Python are runtime-erased, so every
phantom-typed witness in this document is paired with a runtime checker
fired at the unique constructor site (T10).

---

## §0 — Changes from v1

R1 reviewers (MINSKY-fresh-instance, CORRECTNESS, TESTCOMMITTEE,
NAZAROV, FEYNMAN) found 6 BLOCKING + several MAJOR items in the v1
deliverable. v2 is a structural rewrite, not a polish. Material changes:

| § | v1 → v2 change | R1 finding addressed |
|---|---|---|
| §0 | Added "Changes from v1" log (this section). | (housekeeping) |
| §0.6 | Witness types upgraded to T10-aware: every phantom-typed witness has a named **runtime checker** that fires at construction; existential assertion stated. | T10 (witness-laundering), F13 |
| §0.8 | New: parser totality contract. Per parser: input domain, success domain, closed `parse_error` algebra, totality claim. | F9, T8 |
| §0.9 | New: `canonical_serialise` deferred to T8 (TEMPORAL handles canonicalisation pin) but with this document's witnessing obligations stated. | F10, T8 |
| §1.1 | `unit_kind`: ellipsis closed; constructors enumerated explicitly. | F8 |
| §1.2 | `is_fungibility_preserving: TermsVersion -> bool` removed. Replaced by `TermsVersion = FungibilityPreserving { … } \| FungibilityBreaking { … }` sum. `amend_unit` returns the sum-tagged version directly. | F4 (BLOCKING) |
| §1.5 | `LifecycleIntent` constructors enumerated; ellipsis closed. | F8 |
| §2.3 | `LifecycleEvent` (CDM-mapped) closed sum with all eight constructors. `corporate_action`, `credit_event`, `barrier_observation`, `exercise_notice`, `settlement_outcome`, `regulatory_threshold`, `force_majeure`, `locate_event` listed. | F8 |
| §2.5 | `gating_outcome` / `arbitrage_certification_status` collapsed into `CalibrationOutcome = Rejected { gate; reason } \| Accepted { posterior; certificate }`. The Kalman posterior is reachable only inside the `Accepted` branch. | F2 (BLOCKING) |
| §3.1 | `move` retained `quantity : positive_decimal`. **New:** §3.1a `BalancedTransaction` smart constructor; `Transaction = NonEmpty<Move>` carrier exists at parse time but only `BalancedTransaction` may enter the move stream. | F5 (BLOCKING) |
| §3.4 | `quality` flat enum upgraded to `ValuationQuality` closed sum carrying typed payload per case (Firm / Indicative{reason} / Approximate{strategy,bound} / Stale{stale_inputs,first_stale_at} / Failed{mode}). | F1 (BLOCKING) |
| §3.5 | `obligation_kind`: ellipsis closed; constructors enumerated. | F8 |
| §3.5 | `discharge_predicate` / `compensation_handler` lifted to `DischargePredicateKind` and `CompensationHandlerKind` closed sums. | F6 (BLOCKING) |
| §4.2 | UnitStatus `triggered-barrier flag` (bool+comment) replaced by `BarrierState` closed sum carrying attestation evidence. | F3 (BLOCKING) |
| §4.3 | `position_vector` smart-constructor refinement: `coll_rehyp ≤ coll_recv`, `borr ≥ 0`, `coll_post ≥ 0`, `coll_recv ≥ 0`, `on_loan ≥ 0`. | F11 |
| §5 | `wallet`, `legal_entity` writer-cap alphabet enumerated (replaces former phantom-open). | F14 |
| §6 | New: `idempotency_key` as closed sum `IdempotencyKey = ⊕_{i=1..9} K_i` with named namespace tag. | T8 / F19, finding 8 |
| §7 | Capability decomposed; field-tag alphabet closed. L18 IdentityKeys folded into L21 / L22 (constants module, not data leaf). L22 HashChainAnchor folded into Transaction (field, not leaf). | findings 14, 15 |
| §8 | New: witness type construction inventory (T10). Per witness: constructor site, consumers, existential assertion, runtime checker, adversarial Hypothesis test. | T10, F13, finding 9, 10 |
| §9 | Updated boolean-and-comment death list (count: 18 — added 4 sums introduced in v2). | (consistent with §3 upgrades) |

This document remains scoped to Minsky's brief (the data-layer type
discipline). Where R1 findings extend beyond that scope (T1 leaf-count
ruling; T2 theorem rewrite; T3 notation table; T4 operational floor;
T5 regulatory submission leaf; T6 CDM re-fetch; T11 trust-registry
ownership; T12 clock-authority leaf), v2 stays in lane: it provides the
type discipline that any chosen ruling can rest on, and notes deferrals
in §11.

---

## §1 — Cross-cutting refined-type registry (size: 27)

These appear repeatedly; defined once, used everywhere. Every one is a
*newtype* whose constructor is private and whose only public introduction
is the named parser.

```ocaml
(* §1.1 — Identifiers (closed registries) *)
type iso4217      = private string  (* ISO 4217, ~180 codes *)
type iso3166_a2   = private string  (* ISO 3166-1 alpha-2,  ~250 codes *)
type lei20        = private string  (* ISO 17442, MOD-97-10 checksum *)
type bic_8_or_11  = private string  (* ISO 9362 *)
type mic          = private string  (* ISO 10383, ~3,000 codes *)
type isin12       = private string  (* ISO 6166, MOD-10 checksum *)
type cusip9       = private string
type figi12       = private string  (* OpenFIGI *)
type uti          = private string  (* ISO 23897, jurisdiction-prefixed *)
type upi12        = private string  (* ANNA-DSB *)
type cfi6         = private string  (* ISO 10962 *)
type uuid128      = private string

(* §1.2 — Quantities *)
type positive_decimal = private decimal       (* > 0 *)
type non_negative_decimal = private decimal   (* >= 0 *)
type bounded_01       = private decimal       (* in [0, 1] *)
type positive_nat     = private int           (* > 0 *)
type sha256           = private bytes         (* exactly 32 bytes *)

(* §1.3 — Time *)
type timestamp = private { utc_ns : int64 }
type date      = private { y : int; m : int; d : int }

type dual_timestamp = private {
  effective : timestamp;
  knowledge : timestamp;
  (* invariant enforced in constructor: knowledge >= effective *)
}

(* §1.4 — Composite refined containers *)
type 'a non_empty       = { head : 'a; tail : 'a list }
type 'a non_empty_set   = private 'a list
type ('k, 'v) total_map = private { keys : 'k non_empty_set;
                                     value : 'k -> 'v }

(* §1.5 — Outcome / failure *)
type ('a, 'e) result = Ok of 'a | Error of 'e
type 'a option       = None | Some of 'a
```

**Registry size: 27 refined types** (12 ID + 5 quantity + 3 time + 4
composite + 2 outcome + 1 sha256-aliased-as-witness-input).

### §1.6 — Witnesses (proof-carrying refinements; T10-aware)

Every witness type has three named obligations. Section §8 inventories
them.

```ocaml
type arbitrage_certificate = private {
  d_increasing       : witness_tag;       (* discount monotone *)
  w_positive         : witness_tag;       (* total variance >= 0 *)
  no_calendar_spread : witness_tag;
  no_butterfly       : witness_tag;
  certified_by       : signature;
  source_snapshot    : snapshot_id;
}

type snapshot_certificate = private {
  content_hash       : sha256;            (* h(canonical_serialise(payload_set)) *)
  sealer_signature   : signature;
  inputs_attested    : attestation_id non_empty_set;
}

type conserving_transaction = private {
  underlying : transaction;
  proof      : conservation_proof;        (* opaque carrier; runtime checker *)
}

type registered_unit_id = private {
  unit_id    : unit_id;
  registered : registration_witness;      (* opaque; runtime checker *)
}
```

**Why "private" matters in Python.** Phantom types in OCaml/Rust are
nominal at the type level *and* erased at runtime — a `private`
constructor is a compile-time wall. In Python, every phantom is
runtime-erased. The discipline that recovers the witness is:

1. The constructor is the *only* function that produces a value of the
   refined type; it is a regular Python class whose `__init__` is
   underscore-prefixed and whose validation logic is a runtime checker.
2. A `__post_init__`-style runtime checker is invoked at every
   construction site and at every *write* attempt to a field annotated
   as the refined type. Hypothesis tests adversarially attempt to
   construct invalid refined values; the test passes iff the checker
   raises.
3. The "no-laundering" property is checked by `mypy --strict` plus a
   custom AST linter that bans `cast(RefinedT, ...)` outside the
   constructor module. Any laundering becomes a CI failure.

Thus the type-system witness story discharges its obligation in Python
by being **type-level + runtime-checker + lint-rule**, never by typing
alone (T10).

### §1.7 — Capabilities (decomposed; closed alphabet)

R1 finding 14 demanded that L23 Capability close its field-tag alphabet
and decompose into structural sub-types.

```ocaml
type writer_tag =
  | LifecycleHandler
  | SettlementHandler
  | CalibrationHandler
  | TradeHandler
  | FeeCrystalliseHandler
  | CollateralHandler
  | RegulatoryReportingHandler
  | RiskHandler
  | CorrectionHandler
  | AdminRegistrationHandler

type writer_cap = private {
  tag        : writer_tag;
  scope      : write_scope;            (* see below *)
  granted_by : authority_id;
  granted_at : timestamp;
  expires_at : timestamp option;
}

and write_scope =
  | Field         of { field_id : closed_field_tag }
  | UnitClass     of { kind     : unit_kind_tag }
  | TransactionCl of { kind     : transaction_kind_tag }
  | StatePartition of { partition : state_partition_tag }

and closed_field_tag =
  | UnitStatus_LifecycleStage
  | UnitStatus_KindSpecific
  | UnitStatus_SupersededBy
  | PositionState_Vector
  | PositionState_KindSpecific
  | PositionState_TaxLots
  | Obligation_State
  | Obligation_Discharged
  | ProductTerms_VersionsTail
  | Calendar_Holidays

and state_partition_tag =
  | ProductTermsMap
  | UnitStatusMap
  | PositionStateMap
  | ObligationMap
  | TransactionLog
```

Every writer cap is a *closed* token referencing a *closed* alphabet of
fields, classes, partitions. There is no open `field_id : string`
admitted anywhere. A handler asks the registry for its `writer_cap` at
boot; the registry returns a value or refuses; no handler can construct
a cap.

---

## §2 — Boundary parsers and parser totality (F9)

**Totality contract.** Each parser is documented with:

1. **Input domain.** Subset of byte-strings the parser is contracted to
   accept. Stated as a regular language, an XSD reference, or a
   schema-pin.
2. **Output success type.** The refined type produced.
3. **Output error sum.** Closed sum of `parse_error` constructors.
4. **Totality claim.** "For every input in the input domain, this
   parser produces `Ok value` or `Error err` in finite time, with no
   panics, no infinite loops, no unhandled cases."

The error algebra is closed:

```ocaml
type parse_error =
  | BadLength       of { expected : int;       got : int }
  | BadCharset      of { allowed  : string;    got : string }
  | BadChecksum     of { algo     : string }
  | NotInRegistry   of { registry : registry_id; key : string }
  | OutOfRange      of { lo       : decimal;    hi  : decimal; got : decimal }
  | Conflict        of { existing : string;     got : string }
  | UnknownTag      of { tag      : string;     known : string list }
  | StructuralError of { path     : string;     reason : structural_reason }
  | SchemaMismatch  of { expected : schema_pin; got : schema_pin }

and structural_reason =
  | RequiredFieldMissing of { field : string }
  | UnexpectedField      of { field : string }
  | TypeMismatch         of { field : string; expected : string; got : string }
```

**The catalogue.** Per refined type and per external data class:

```ocaml
val parse_iso4217  : string  -> (iso4217,    parse_error) result
  (* domain: 3-character uppercase ASCII *)
val parse_lei      : string  -> (lei20,      parse_error) result
  (* domain: 20-character alphanumeric, MOD-97-10 valid *)
val parse_isin     : string  -> (isin12,     parse_error) result
val parse_uti      : string  -> (uti,        parse_error) result
val parse_quote    : envelope_bytes -> (raw_quote attested, parse_error) result
  (* domain: ISO 20022 / FpML / vendor-canonical envelope per registered schema_pin *)
val parse_cdm_event: envelope_bytes -> (lifecycle_event,    parse_error) result
  (* domain: CDM 6.0.0 BusinessEvent JSON per Rosetta canonical schema *)
val parse_csa      : signed_pdf_bytes -> (csa_terms,        parse_error) result
val parse_calendar : envelope_bytes -> (calendar attested,  parse_error) result
(* …roughly 60 parsers, one per refined type or external class… *)
```

**Per parser: a single totality test.** A parser is total iff
`Hypothesis-generated input from the documented domain returns either
Ok or Error; never raises an unrelated exception, never times out
beyond a stated budget`. This is a property test, mandatory at CI gate.

### §2.1 — `canonical_serialise` (T8 deferral)

R1 finding 13 / F10: this document defers the canonicalisation pin to
**TEMPORAL** (T8 in the consolidated findings). v2 records the witness
*obligation* the canonicalisation must discharge:

- `canonical_serialise : payload_set -> bytes` is total over its typed
  input.
- `forall p1 p2. (p1 = p2 logically) ⇒ canonical_serialise(p1) = canonical_serialise(p2) bytewise`
  (canonical-form determinism).
- `snapshot_certificate.content_hash = sha256(canonical_serialise(payload_set))`
  is the only construction site of `snapshot_certificate.content_hash`.

Any canonicalisation choice (CBOR per RFC 8949 §4.2.1, JCS per RFC 8785,
or bespoke) that meets these obligations is admissible. Pin lives in
TEMPORAL/T8.

---

## §3 — Definitions (NAZAROV class A)

The Definitions class is append-only, versioned, registration-total.

### §3.1 — `UnitId` and `unit_kind` (closed; ellipsis removed — F8)

```ocaml
type unit_kind =
  | Cash         of { iso : iso4217 }
  | ListedEquity of { isin : isin12; primary_listing : mic;
                      board_lot : positive_nat;
                      voting : voting_rights }
  | ListedDeriv  of { spec : contract_spec }
  | Bond         of { isin : isin12; schedule : coupon_schedule;
                      maturity : date; day_count : day_count;
                      bda : business_day_convention }
  | Otc          of { cdm_trade : cdm_trade; csa_ref : agreement_id }
  | Mandate      of { manager : lei20; client : lei20;
                      benchmark : unit_id; fee : fee_schedule }
  | Qis          of { strategy : strategy_spec }
  | StructuredNote of { isin : isin12; embedded : payout_node non_empty;
                        terms_doc : sha256 }
  | Token        of { chain : chain_id; contract : eth_address;
                      backing : backing_model; underlier_isin : isin12 option;
                      lifecycle_model : lifecycle_model }
  | Loan         of { facility_ref : agreement_id; commitment : positive_decimal;
                      currency : iso4217; maturity : date }
  | Repo         of { underlying : unit_id; haircut : bounded_01;
                      maturity : date }

(* exhaustive: 11 constructors. No ellipsis. *)

and lifecycle_model =
  | OffChainBookkeeping
  | SmartContract of { contract_addr : eth_address }
```

This is a **closed sum**. A future extension (e.g. a CommercialPaper
constructor) requires a documented schema-pin update and an explicit
release; the parser at the boundary rejects unknown tags with
`UnknownTag { tag; known = [...11 cases...] }`.

### §3.2 — `ProductTerms` and amendment outcome (F4 fix — sum-typed `TermsVersion`)

R1 F4 BLOCKING: `is_fungibility_preserving: TermsVersion -> bool` is a
predicate-as-field. v2 fix: the predicate is decided **at construction
time** by `amend_unit` and the resulting `TermsVersion` is sum-typed.

```ocaml
type product_terms = {
  unit_id  : registered_unit_id;
  versions : terms_version non_empty;
  binding  : smart_contract_ref;
  kind     : product_kind;
}

and terms_version =
  | FungibilityPreserving of {
      effective_at : timestamp;
      knowledge_at : timestamp;
      fields       : terms_field_map;
      preservation_witness : preservation_witness;
        (* opaque; runtime checker in §8 *)
      signed_by    : actor_id;
      hash         : sha256;
    }
  | FungibilityBreaking of {
      effective_at : timestamp;
      knowledge_at : timestamp;
      fields       : terms_field_map;
      break_reason : break_reason;       (* closed sum *)
      signed_by    : actor_id;
      hash         : sha256;
    }

and break_reason =
  | UnderlierIdentityChange
  | StrikeTermsChanged
  | MaturityChanged
  | CashflowFunctionChanged
  | RegulatoryRecategorisation
  | CounterpartyAssignmentBreakingFungibility

type amendment_outcome =
  | Preserving of terms_version           (* must be FungibilityPreserving *)
  | Breaking   of { fresh : registered_unit_id;
                    supersedes : registered_unit_id;
                    new_inception : terms_version }

val amend_unit
  :  registered_unit_id
  -> terms_amendment
  -> product_terms
  -> ( amendment_outcome * product_terms, amend_error ) result
```

The previous `predicate : TermsVersion -> bool` field is *gone*. Tag
discriminates structurally; a consumer pattern-matching on
`terms_version` cannot read fungibility status incorrectly because the
status *is* the constructor.

### §3.3 — `LifecycleIntent` (closed sum; ellipsis removed — F8)

```ocaml
type lifecycle_intent =
  | Allocation
  | Cancellation
  | Clearing
  | Compression
  | Exercise
  | Formation
  | Increase
  | Novation
  | Observation
  | Open
  | PartialTermination
  | Termination
  | Transfer
  | Expire
  | Assign
  | Correction
  | EarlyTermination
  | Reallocation

(* exhaustive: 18 constructors. No ellipsis.
   Parser at boundary rejects unknown tag with
   UnknownTag { tag; known = [...18...] } — including future CDM
   `Restructure` until governance review admits it. *)
```

### §3.4 — Legal agreements

(Unchanged from v1; reproduced here for self-containment of the
boolean-and-comment death-list audit.)

```ocaml
type collateral_regime =
  | TitleTransfer    of { gmsla_schedule : gmsla_schedule }
  | SecurityInterest of { gmsla_schedule : gmsla_schedule;
                          rehyp_consent  : bool;
                          gov_law        : governing_law }
  | UsRule15c3_3     of { customer_debit_cap : positive_decimal }

type governing_law =
  | EnglishLaw | NewYorkLaw | JapaneseLaw
  | FrenchLaw  | SwissLaw   | OtherLaw of iso3166_a2
```

(`rehyp_consent` is intentionally bool-typed *here*: it is the regime's
own consent boolean. It is **not** a state. The "regime" itself is the
sum.)

---

## §4 — Observations (NAZAROV class B)

Append-only, bitemporal, source-attested. Calibrated state is *derived*
from observations and gets witness-typed treatment in §4.5.

### §4.1 — `RawQuote`

```ocaml
type quote_quality_tag =
  | Live | Indicative | Closing | Synthetic | Stale

type bid_ask =
  | OneSided of { side : side; value : decimal }
  | TwoSided of { bid  : decimal; ask : decimal }    (* invariant ask >= bid *)
  | Crossed  of { bid  : decimal; ask : decimal }

and side = Bid | Ask | Mid | Last | Settle

type raw_quote = {
  observable    : observable_ref;
  spread        : bid_ask;
  as_of         : dual_timestamp;
  source        : source_id;
  feed_seq      : int64;
  quality       : quote_quality_tag;
  attestation   : signature;
}
```

### §4.2 — `OracleAttestation` wrapper

```ocaml
type 'payload attested = {
  payload          : 'payload;
  payload_hash     : sha256;
  source           : source_id;
  signing_key_id   : key_id;
  source_signature : signature;
  publication_time : timestamp;
  ingestion_time   : timestamp;
  ingestion_sig    : signature;
  schema_version   : schema_version;
  mapping_version  : mapping_version option;
}

val verify : 'a attested -> trust_registry -> ( unit, attestation_error ) result
```

### §4.3 — `LifecycleEvent` (closed sum; F8 fix)

```ocaml
type lifecycle_event =
  | LE_CorporateAction      of corporate_action
  | LE_Barrier              of barrier_observation
  | LE_Fixing               of fixing_observation
  | LE_Exercise             of exercise_notice
  | LE_Default              of credit_event
  | LE_Locate               of locate_event
  | LE_RegulatoryThreshold  of regulatory_threshold_event
  | LE_ForceMajeure         of force_majeure_event

(* exhaustive: 8 constructors. No ellipsis. *)

type corporate_action =
  | CashDividend  of { gross_per_share : positive_decimal;
                       currency        : iso4217;
                       record_date     : date;
                       payment_date    : date;
                       withholding     : withholding_treatment }
  | StockSplit    of { ratio_num       : positive_nat;
                       ratio_denom     : positive_nat;
                       ex_date         : date;
                       effective_date  : date }
  | Merger        of { acquirer        : registered_unit_id;
                       conversion      : conversion_rule;
                       effective_date  : date }
  | SpinOff       of { new_unit        : registered_unit_id;
                       distribution    : (positive_nat * positive_nat) }
  | RightsIssue   of { subscription_ratio : positive_decimal;
                       price            : positive_decimal;
                       record_date      : date;
                       election_deadline: timestamp }
  | NameChange    of { new_name        : string;
                       new_isin        : isin12 option }
  | Reclassification of { new_classification : cfi6 }

type barrier_observation = {
  unit_id          : registered_unit_id;
  barrier_def      : barrier_definition_ref;
  observation_time : timestamp;
  observed_value   : decimal;
  barrier_value    : decimal;
  condition        : barrier_condition;
  outcome          : barrier_outcome;
}

and barrier_condition = UpAndOut | DownAndIn | UpAndIn | DownAndOut
and barrier_outcome   = NotBreached | Breached of { event_ref : event_ref }

type credit_event =
  | FailureToPay
  | Bankruptcy            of { filing_ref : court_ref }
  | Restructuring         of { isda_cdc_decision : cdc_decision_id }
  | ObligationDefault     of { agreement : agreement_id }
  | GovernmentIntervention of { authority : iso3166_a2; date : date }
  | Repudiation           of { event_ref : event_ref }

type fixing_observation = {
  observable     : observable_ref;
  fixing_date    : date;
  fixed_value    : decimal;
  source         : source_id;
}

type locate_event = {
  lender         : lei20;
  borrower       : lei20;
  isin           : isin12;
  reservation_id : uuid128;
  reserved_qty   : positive_decimal;
  expiry         : timestamp;
  outcome        : locate_outcome;
}

and locate_outcome =
  | Granted | Refused | Lapsed | Cancelled of { reason : cancel_reason }

type regulatory_threshold_event = {
  regime         : regulatory_regime;
  threshold_kind : threshold_kind;
  level_crossed  : decimal;
  direction      : threshold_direction;
}

and threshold_kind =
  | DisclosureThreshold | ConcentrationLimit
  | LargePositionReporting | ShortSaleDisclosure

and threshold_direction = Crossed_Up | Crossed_Down

type force_majeure_event = {
  jurisdiction : iso3166_a2;
  market_ref   : mic;
  reason       : force_majeure_reason;
  effective    : dual_timestamp;
}

and force_majeure_reason =
  | NaturalDisaster | RegulatoryHalt | ExchangeOutage
  | TradingSuspension | InfrastructureFailure
```

### §4.4 — `MarketDataSnapshot`

```ocaml
type snapshot_id = private { hash : sha256 }

type market_data_snapshot = private {
  id                 : snapshot_id;
  certificate        : snapshot_certificate;
  as_of              : dual_timestamp;
  quotes             : (observable_ref, raw_quote attested) total_map;
  fx_rates           : (ccy_pair, fx_rate attested) total_map;
  calibrations       : (calibrated_object_id, calibration_outcome) total_map;
                                            (* outcome, not bare state — see §4.5 *)
  fallback_chain     : fallback_decision list;
  content_hash       : sha256;
}

val seal_snapshot
  :  observation_set
  -> ( market_data_snapshot, snapshot_error ) result
```

### §4.5 — `CalibratedState` and `CalibrationOutcome` (F2 BLOCKING fix)

R1 F2 BLOCKING: `gating_outcome` and `arbitrage_certification_status`
were untyped sibling tags. Fix: the Kalman posterior is reachable only
inside the `Accepted` branch.

```ocaml
type 'm calibration_outcome =
  | Rejected of {
      gate         : which_gate;
      reason       : gate_failure;
      offered_at   : dual_timestamp;
      source_snapshot : snapshot_id;
    }
  | Accepted of {
      posterior    : 'm calibrated_state;
      certificate  : arbitrage_certificate;
    }

and which_gate =
  | InnovationStatistic
  | NoArbitrageRegion
  | LikelihoodPlausibility
  | InputCompleteness
  | NumericalStability

and gate_failure =
  | InnovationOutOfBound  of { stat : decimal; threshold : decimal }
  | NoArbitrageViolated   of { which : arbitrage_violation }
  | LikelihoodImplausible of { aic : decimal; threshold : decimal }
  | MissingInput          of { observable : observable_ref }
  | NumericallyUnstable   of { detail : numerical_failure }

and arbitrage_violation =
  | DiscountNotMonotone | TotalVarianceNegative
  | CalendarSpreadFails | ButterflyFails

type 'm calibrated_state = private {
  object_id        : calibrated_object_id;
  model_id         : calibration_model_id;
  state            : 'm state_vector;     (* GADT-keyed *)
  covariance       : matrix;
  innovation       : innovation_stats;
  fitted_at        : dual_timestamp;
  source_snapshot  : snapshot_id;
  fitter_signature : signature;
}

val kalman_update : 'm prior
                 -> observation_set
                 -> ('m calibration_outcome, calib_error) result
  (* the ONLY constructor of `'m calibrated_state` is the `Accepted`
     branch's payload-construction site. No path produces an
     uncertified posterior. *)
```

A consumer wanting the posterior **must** destructure `Accepted`. The
`certificate` is in scope at every consumer site; type system enforces
it (T10: combined with §1.6 runtime checker).

The `calibrated_state` `private` constructor is invoked exactly once:
inside the `Accepted` branch's smart-constructor. The runtime checker
in §8 fires on every construction attempt and asserts the certificate
is non-null and signature-verifiable.

---

## §5 — Effects (NAZAROV class C)

Append-only, hash-chained, atomic across the three state maps,
idempotent under retry, deterministic on replay.

### §5.1 — `Move`

```ocaml
type position_coordinate =
  | Own | OnLoan | Borr | CollPost | CollRecv | CollRehyp

type move = private {
  source        : wallet_id;
  destination   : wallet_id;
  unit          : registered_unit_id;
  quantity      : positive_decimal;       (* never signed; sign in (src, dst) *)
  coordinate    : position_coordinate;
  effective_at  : timestamp;
  source_contract : smart_contract_ref;
  metadata      : move_metadata;
}
```

### §5.2 — `BalancedTransaction` (F5 BLOCKING fix)

R1 F5 BLOCKING: `Transaction ≈ NonEmpty<Move>` "with conservation
refinement" was assertion, not encoding. Fix: a smart constructor
turns a raw transaction into a `BalancedTransaction`, the only type
that may enter the move stream.

```ocaml
type transaction_kind =
  | Settlement
  | Collateral
  | Lifecycle
  | Accounting
  | Correction of { corrects : tx_id; rationale : correction_rationale }

(* unrefined transaction: parse-time carrier *)
type transaction = {
  tx_id                  : tx_id;
  kind                   : transaction_kind;
  moves                  : move list;
  terms_delta            : terms_amendment option;
  unit_status_delta      : (registered_unit_id, unit_status_delta) total_map;
  position_state_delta   : ((wallet_id * registered_unit_id), position_state_delta) total_map;
  obligations_created    : obligation list;
  obligations_discharged : obligation_id list;
  cdm_payload            : cdm_business_event;
  effective_at           : timestamp;
  committed_at           : timestamp;
  prev_hash              : sha256;
}

(* refined: only this enters the move stream *)
type balanced_transaction = private {
  underlying : transaction;
  proof      : conservation_proof;
}

(* the unique constructor *)
val balance
  :  transaction
  -> ( balanced_transaction, conservation_violation ) result

and conservation_violation =
  | UnitNotConserved      of { unit : registered_unit_id;
                               source_sum : decimal;
                               dest_sum   : decimal }
  | CoordinateClosureFails of { wallet : wallet_id;
                                unit   : registered_unit_id;
                                violated : closure_law }
  | DeltaNotAddingUp       of { unit : registered_unit_id;
                                expected : decimal; got : decimal }
  | EmptyMovesNotAccounting

(* and the only commit API: *)
val commit : balanced_transaction -> ledger_state
                                  -> ( committed_transaction, commit_error ) result
```

There is **no** `commit : transaction -> ...` API anywhere in the
system. The conservation proof is reified, not just asserted. The
runtime checker (§8) fires inside `balance` and adversarial Hypothesis
tests attempt every fault class identified by CORRECTNESS A.1 / A.2 /
B-4.

### §5.3 — `SettlementInstruction`

```ocaml
type settlement_leg_securities = {
  isin     : isin12;
  qty      : positive_decimal;
  csd      : csd_id;
  account  : csd_account_id;
}

type settlement_leg_cash = {
  ccy      : iso4217;
  amount   : positive_decimal;
  payment_system : payment_system_id;
  bic      : bic_8_or_11;
}

type settlement_instruction =
  | DvP  of { sec : settlement_leg_securities; cash : settlement_leg_cash }
  | FOP  of { sec : settlement_leg_securities }
  | Cash of { cash : settlement_leg_cash }
```

### §5.4 — `ValuationRecord` and `ValuationQuality` (F1 BLOCKING fix)

R1 F1 BLOCKING: `quality ∈ {FIRM, INDICATIVE, APPROXIMATE, STALE,
FAILED}` was a flat enum. Fix: each tag carries the data the consumer
needs to react.

```ocaml
type valuation_quality =
  | Firm
  | Indicative  of { reason : indicative_reason }
  | Approximate of { strategy : approx_strategy;
                     bound    : price_bound }
  | Stale       of { stale_inputs   : input_ref non_empty;
                     first_stale_at : timestamp }
  | Failed      of { mode : valuation_failure_mode }

and indicative_reason =
  | ModelDisagreementUnderTolerance
  | InputBidAskWidening
  | LowLiquidityFlag
  | OffMarketHours

and approx_strategy =
  | LinearInterpolation
  | NearestNeighbour
  | TaylorExpansion of { order : positive_nat }
  | KalmanFallback  of { last_certified : calibration_object_id }

and price_bound =
  | AbsoluteBound of { min : decimal; max : decimal }
  | RelativeBound of { centre : decimal; rel_pct : bounded_01 }
  | UnknownBound

and valuation_failure_mode =
  | MissingInput              of { observable : observable_ref }
  | CalibrationNotCertified   of { object_id  : calibrated_object_id }
  | NumericalPanic            of { detail     : numerical_failure }
  | ModelPanic                of { reason     : string }
  | StalenessExceededBudget

type valuation_fsm_state =
  | Unpriced | Pricing of { started : timestamp }
  | Priced   of { record : valuation_record_id }
  | Explaining | Explained
  | Quarantined of { retry_count : positive_nat;
                     last_error  : explain_failure }
  | StaleS    of { staleness_deadline : timestamp }
  | FailedS   of { reason : valuation_failure_mode }

type 'm valuation_record = {
  unit_id           : registered_unit_id;
  timestamp         : timestamp;
  dirty_price       : decimal;
  clean_price       : decimal;
  accrued           : decimal;
  greeks            : 'm greeks;          (* GADT-keyed by model *)
  model_id          : calibration_model_id;
  market_data_snap  : snapshot_id;
  calibration_state : 'm calibrated_state_id;
  compute_ms        : positive_nat;
  quality           : valuation_quality;
  fsm_state         : valuation_fsm_state;
  workflow_signature: signature;
}
```

A consumer pattern-matching on `valuation_quality` cannot forget to
handle the failure mode — every tag carries its own payload, and there
is no path that constructs `Failed` without a `valuation_failure_mode`.

### §5.5 — `Obligation` (F6 BLOCKING fix; F8 ellipsis fix)

R1 F6 BLOCKING: `discharge_predicate` and `compensation_handler` were
prose-described. Fix: closed sum of named predicate kinds.

R1 F8: `obligation_kind` ellipsis closed.

```ocaml
type obligation_kind =
  | BondCoupon
  | OptionExpiry
  | IrsReset
  | FuturesDailyVm
  | SblTermLoanReturn
  | SblRecallReturn
  | SblManufacturedDividend
  | SblCollateralSubstitution
  | SblCollateralTopUp
  | CsaVmDelivery
  | CsaImDelivery
  | CollateralSubstitution
  | CloseOutNetting
  | SftrReport
  | SlateReport
  | EmirReport
  | MifirReport
  | SettlementInstructionDischarge
  | CsdrPenalty
  | BuyInExecution
  | LocateExpiry
  | RehypothecationCapMonitor
  | TaxWithholdingPass

(* exhaustive: 23 constructors. No ellipsis. *)

type discharge_predicate_kind =
  | SettlementMatched          of { match_target : settlement_match_ref }
  | OracleAttestationReceived  of { observable_ref : observable_ref;
                                    threshold      : oracle_threshold }
  | CounterpartyAcknowledged   of { ack_kind : ack_kind }
  | CompensationApplied        of { compensation_id : compensation_id }
  | RegulatoryReceiptIssued    of { regulator : regulator_id;
                                    rule_set  : regulatory_rule_set }
  | TimerFired                 of { deadline : timestamp;
                                    grace    : duration }
  | InternalBookkeepingClose   of { closing_tx : tx_id }

(* exhaustive: 7 constructors. No ellipsis. *)

type compensation_handler_kind =
  | NoCompensation
  | BuyInWorkflow              of { ccp_or_csd : authority_id }
  | ManufacturedPaymentApply   of { rate_source : rate_source_id }
  | EscalateToHumanQueue       of { queue : queue_id }
  | RegulatoryRefilingWorkflow of { regulator : regulator_id }
  | LiquidationWorkflow        of { authority : authority_id }
  | CashSettleAtMid            of { mid_source : source_id }

(* exhaustive: 7 constructors. No ellipsis. *)

type obligation_state =
  | Pending     of { created_at : dual_timestamp }
  | Attempted   of { attempts : attempt non_empty }
  | Discharged  of { by_tx : tx_id; at : timestamp }
  | Compensated of { by_tx : tx_id; reason : compensation_reason }
  | Defaulted   of { reason : default_reason; at : timestamp }

type obligation_source =
  | Unit       of { unit_id : registered_unit_id }
  | Agreement  of { agreement_id : agreement_id }
  | Regulatory of { regime : regulatory_regime; event_ref : event_ref }

type obligation = {
  id              : obligation_id;
  kind            : obligation_kind;
  source          : obligation_source;
  deadline        : dual_timestamp;
  discharge_pred  : discharge_predicate_kind;
  compensation    : compensation_handler_kind;
  state           : obligation_state;
}
```

The two former opaque carriers (`discharge_predicate`,
`compensation_handler`) are now closed sums. A future predicate kind
requires a sum extension and a CI-checked migration; the parser at
ingestion rejects unknown tags.

---

## §6 — State (StatesHome 3-map)

### §6.1 — `UnitStatus` and `BarrierState` (F3 BLOCKING fix)

R1 F3 BLOCKING: UnitStatus carried a "triggered-barrier flag" — bool +
comment. Fix: closed sum carrying attestation evidence; kept inside
the constructors that have barriers.

```ocaml
type lifecycle_stage =
  | Pending | Listed | Active | Matured | Terminated
  | Settled | Defaulted | Closed | Exercised | Assigned

type barrier_state =
  | NoBarrier
  | Armed     of { kind        : barrier_kind;
                   level       : decimal;
                   monitored_since : timestamp }
  | Triggered of { kind        : barrier_kind;
                   level       : decimal;
                   evidence    : lifecycle_attestation_id;
                   t_obs       : timestamp;
                   confirming_event_ref : event_ref }

and barrier_kind =
  | KnockIn  of { observation : barrier_observation_rule }
  | KnockOut of { observation : barrier_observation_rule }

and barrier_observation_rule =
  | ContinuousObservation
  | DailyClose
  | TimeWindow of { start_t : timestamp; end_t : timestamp }

type unit_status_kind =
  | FuturesStatus  of { last_settle_price : decimal option;
                        last_settle_date  : date option }
  | OptionStatus   of { exercised_state : exercise_state;
                        barriers : (barrier_id, barrier_state) total_map }
  | BondStatus     of { paid_coupons : date sorted_set;
                        matured : bool }
  | QisStatus      of { current_weights : weight_vector;
                        nav_index       : positive_decimal;
                        barriers        : (barrier_id, barrier_state) total_map;
                        last_rebalance  : date }
  | MandateStatus  of { benchmark_level : decimal }
  | EquityStatus   of unit
  | StructuredNoteStatus of { barriers : (barrier_id, barrier_state) total_map;
                              fixings  : (fixing_id, decimal) total_map }
  | LoanStatus     of { drawn : non_negative_decimal;
                        accrued_interest : non_negative_decimal }
  | RepoStatus     of { open_qty : non_negative_decimal;
                        accrued_repo_interest : non_negative_decimal }
  | TokenStatus    of { onchain_state : onchain_state_ref }
  | CashStatus     of unit

type unit_status = {
  unit_id          : registered_unit_id;
  lifecycle_stage  : lifecycle_stage;
  kind_specific    : unit_status_kind;
  superseded_by    : registered_unit_id option;
  as_of            : dual_timestamp;
}
```

`barrier_state` is now a closed sum carrying — in the `Triggered`
constructor — the attestation evidence (`lifecycle_attestation_id`,
`t_obs`, `confirming_event_ref`). The bool plus side-channel
attestation is structurally impossible.

A unit may have multiple barriers (KIKO has both KI and KO); each
barrier is a key in the per-status `barriers` map. Each map value is
independently a `barrier_state`.

### §6.2 — `PositionState` and `position_vector` closure law (F11 fix)

R1 F11 / finding 11: the six-coordinate vector lacks a closure law.
Fix: `position_vector` is private with smart-constructor refinement.

```ocaml
type position_vector = private (* must be Gpm6 or Scalar; see constructor *)
  | Scalar of { own : decimal }
  | Gpm6   of { own        : decimal;
                on_loan    : non_negative_decimal;
                borr       : non_negative_decimal;
                coll_post  : non_negative_decimal;
                coll_recv  : non_negative_decimal;
                coll_rehyp : non_negative_decimal }
                                              (* invariant: coll_rehyp <= coll_recv;
                                                            on_loan   <= own + borrowed_inventory *)

(* the unique constructors *)
val mk_scalar : decimal -> position_vector
val mk_gpm6
  :  own:decimal
  -> on_loan:decimal
  -> borr:decimal
  -> coll_post:decimal
  -> coll_recv:decimal
  -> coll_rehyp:decimal
  -> ( position_vector, position_vector_violation ) result

and position_vector_violation =
  | RehypExceedsRecv of { coll_rehyp : decimal; coll_recv : decimal }
  | NegativeBorr     of { borr : decimal }
  | NegativeCollPost of { coll_post : decimal }
  | NegativeCollRecv of { coll_recv : decimal }
  | NegativeOnLoan   of { on_loan   : decimal }
  | OnLoanExceedsCapacity of { on_loan : decimal;
                                capacity : decimal }

(* updates go through smart constructor too *)
val apply_move
  :  position_vector
  -> move
  -> ( position_vector, position_vector_violation ) result
```

There is **no** path that produces a `Gpm6` violating the closure
law. A move whose application would violate is rejected at
`apply_move`; the rejection is also caught by `balance` in §5.2,
since `balance` calls `apply_move` for every move.

Other position-state fields:

```ocaml
type position_state_kind =
  | FuturesPosition of { accumulated_cost : decimal;
                         ccp_binding      : ccp_id }
  | EquityPosition  of unit
  | OptionPosition  of { entry_premium : decimal }
  | BondPosition    of { tax_lots : tax_lot non_empty }
  | QisHolderPosition of { entry_nav : positive_decimal;
                           hwm       : positive_decimal;
                           hwm_date  : date;
                           accrued_mgmt_fee : non_negative_decimal;
                           accrued_perf_fee : non_negative_decimal }
  | MandatePosition of { benchmark_nav_at_inception : positive_decimal;
                         breach_flags : breach_flag list }
  | LoanHolderPosition of { drawn : non_negative_decimal }
  | RepoHolderPosition of { open_qty : non_negative_decimal }
  | TokenHolderPosition of { onchain_balance : non_negative_decimal }
  | CashPosition  of unit

type position_state = {
  wallet_id      : wallet_id;
  unit_id        : registered_unit_id;
  vector         : position_vector;
  kind_specific  : position_state_kind;
  as_of          : dual_timestamp;
}
```

The accessor `get_position : ... -> position_state option` is total
over its keys' domain and returns `None` for never-held wallet/unit
pairs (StatesHome C1 distinction vs Some-of-zeros).

---

## §7 — Identity, Idempotency, Auxiliary

### §7.1 — Wallets / parties (unchanged from v1)

```ocaml
type lei_status =
  | Issued | Lapsed | PendingValidation | Retired
  | Merged | Annulled | Duplicate

type wallet_kind =
  | Real      of { external_id : external_account_id }
  | Virtual   of { contra_for  : agreement_or_unit_ref }
  | Reference of { book_id     : book_id }

type wallet_status = Active | Frozen | Closed
```

### §7.2 — `IdempotencyKey` (closed sum; finding 8, F19)

R1 finding 8: `IdempotencyToken` had 9 shapes. Fix: closed sum with
named namespace.

```ocaml
type idempotency_namespace =
  | Ns_RawObservation
  | Ns_LifecycleEvent
  | Ns_ExternalConfirmation
  | Ns_CalibratedObject
  | Ns_Transaction
  | Ns_ValuationRecord
  | Ns_ObligationDischarge
  | Ns_RegulatorySubmission
  | Ns_AdminRegistration

(* exhaustive: 9 namespaces. *)

type idempotency_key =
  | K_Observation         of { ns : idempotency_namespace;
                               source : source_id;
                               feed_seq : int64 }
  | K_LifecycleEvent      of { ns : idempotency_namespace;
                               event_hash : sha256 }
  | K_ExternalConfirmation of { ns : idempotency_namespace;
                                external_message_id : external_message_id }
  | K_Calibration         of { ns : idempotency_namespace;
                               object_id : calibrated_object_id;
                               source_snapshot : snapshot_id }
  | K_Transaction         of { ns : idempotency_namespace;
                               business_event_id : business_event_id;
                               attempt_seq : positive_nat }
                               (* explicitly NO Temporal run_id;
                                  closes finding 4 / temporal B-2 *)
  | K_Valuation           of { ns : idempotency_namespace;
                               unit_id : registered_unit_id;
                               snapshot : snapshot_id;
                               model_id : calibration_model_id }
  | K_ObligationDischarge of { ns : idempotency_namespace;
                               obligation_id : obligation_id;
                               attempt_seq : positive_nat }
  | K_RegulatorySubmission of { ns : idempotency_namespace;
                                regulator : regulator_id;
                                rule_set : regulatory_rule_set;
                                tx_id : tx_id }
  | K_AdminRegistration   of { ns : idempotency_namespace;
                               admin_op : admin_op_kind;
                               request_uuid : uuid128 }

(* invariant: k.ns matches k's constructor by parser construction.
   Smart constructor checks; runtime checker in §8. *)
```

### §7.3 — Folded leaves (findings 14, 15)

Per R1, two former v1 leaves are demoted from leaves to fields of
existing leaves:

| v1 leaf | v2 placement | rationale |
|---|---|---|
| L18 IdentityKeys | Folded into L21 VersionPin / constants module. Not a data leaf. | Constants, not data. (geohot B1, grothendieck m3.) |
| L22 HashChainAnchor | Folded into Transaction.`prev_hash` field. | Field, not leaf. (geohot B1.) |

Their content (signing key registry, hash anchor) survives; only the
leaf classification changes.

---

## §8 — Witness type construction inventory (T10)

R1 T10 finding 9: per witness, list (constructor site, consumers,
existential assertion, runtime checker, adversarial test). Inventory
size: **5 witness types**.

### W1 — `arbitrage_certificate`

| Aspect | Specification |
|---|---|
| Constructor site | `kalman_update` returns `Accepted { certificate; … }`. The certificate's *only* construction site is inside the smart constructor of `Accepted`, gated on all four sub-witnesses passing. |
| Consumers | `pricer<'m>` requires `'m calibrated_state` from the `Accepted` branch (impossible to read posterior without certificate). `seal_snapshot` admits `calibration_outcome` directly (preserves the tag). `commit` of a transaction touching a calibration consumes the `Accepted` payload. |
| Existential assertion | "There exists a tuple of four sub-witnesses (`d_increasing`, `w_positive`, `no_calendar_spread`, `no_butterfly`) sealed by `certified_by` over `source_snapshot`, each verifying its named no-arbitrage property by construction-time numeric check." |
| Runtime checker | Constructor body re-runs each of the four numeric checks against `source_snapshot.content_hash` and the posterior; raises `CertificateForged` on mismatch. Lint rule bans `cast(ArbitrageCertificate, ...)` outside this constructor module. |
| Adversarial Hypothesis test | Generator produces a posterior that violates one of the four properties; asserts that `kalman_update` returns `Rejected`, never `Accepted`. Mutation operator `M-FAKE-CERT` flips the certificate; runtime checker must catch it on first downstream consumer. |

### W2 — `snapshot_certificate`

| Aspect | Specification |
|---|---|
| Constructor site | `seal_snapshot` (the *only* sealing site). Computes `content_hash = sha256(canonical_serialise(payload_set))` and signs. |
| Consumers | Every pricer takes `market_data_snapshot`, whose `certificate` is intrinsic. `commit` requires the sealed snapshot's certificate to be reachable from `tx.cdm_payload.snapshot_ref`. |
| Existential assertion | "There exists a `payload_set` whose canonical serialisation hashes to `content_hash`, and which was sealed by `sealer_signature` at time `as_of.knowledge` over inputs `inputs_attested`." |
| Runtime checker | Constructor body recomputes `sha256(canonical_serialise(payload_set))` and asserts equal to the sealed `content_hash`. Verifies `sealer_signature`. Verifies every `attestation_id` in `inputs_attested` exists in the trust registry. |
| Adversarial Hypothesis test | Mutation operator `M-AGGREGATE` swaps out a single quote post-seal; assert recomputed hash mismatches and verifier rejects. T8/F10 canonicalisation fault is detected. |

### W3 — `conserving_transaction` / `balanced_transaction`

| Aspect | Specification |
|---|---|
| Constructor site | `balance : transaction -> Result<balanced_transaction, conservation_violation>` — the only constructor. |
| Consumers | `commit : balanced_transaction -> ...` is the only commit API. The unrefined `transaction` cannot be committed; type system rejects. |
| Existential assertion | "Across all moves in `underlying.moves`, per unit, sum-of-source-quantities equals sum-of-destination-quantities, modulo issuance/retirement events whose tag is in the issuance whitelist (NAZAROV D-CONS exception list)." Plus: every `apply_move` succeeds. |
| Runtime checker | Constructor body computes per-unit conservation tally; verifies `coll_rehyp ≤ coll_recv` and `borr, coll_post, coll_recv, on_loan ≥ 0` post-application; raises `ConservationViolation` on first mismatch. |
| Adversarial Hypothesis test | Generator produces transactions with unbalanced moves; asserts `balance` returns `Error`. Mutation operators `M-DEFLATE` (drop a move post-balance) and `M-BIAS` (perturb a quantity) attempt to slip a violation through; assert runtime checker catches at any point of read. |

### W4 — `registered_unit_id`

| Aspect | Specification |
|---|---|
| Constructor site | `register_unit : raw_event -> unit_store -> Result<(registered_unit_id, unit_store), register_error>`. |
| Consumers | Every `unit_id` field in every leaf is `registered_unit_id`, never bare `unit_id`. ProductTerms, UnitStatus, PositionState, Move, Obligation source — all carry the registered form. |
| Existential assertion | "This unit has been admitted to the unit_store at some `t_known ≤ now`; the admission was witnessed by a `register_unit` call whose return value is sealed in the L14 transaction history." |
| Runtime checker | Constructor body verifies the unit is a key in the live unit_store. Lint rule bans `cast(RegisteredUnitId, ...)` outside the constructor module. |
| Adversarial Hypothesis test | Generator attempts to construct a `registered_unit_id` from a non-registered unit; asserts construction fails. Mutation: rename `register_unit` to bypass; assert all downstream consumers' type checks fail. |

### W5 — `'m calibrated_state` (GADT-keyed by model)

| Aspect | Specification |
|---|---|
| Constructor site | Inside `Accepted { posterior; certificate }` of `kalman_update`'s return. Posterior cannot be constructed without certificate. |
| Consumers | `pricer<'m>` admits only the matching model class (BS pricer cannot consume Heston state — GADT type error in OCaml/Rust; runtime model_id check in Python). |
| Existential assertion | "There exists an observation set against which a Kalman filter of model class `'m` produced this posterior, with covariance, innovation statistics, and a bound-checked likelihood; sealed by `fitter_signature`." |
| Runtime checker | Constructor verifies `state_vector`'s structure matches `model_id`. Lint rule bans cross-model casts. |
| Adversarial Hypothesis test | Mutation: feed a `bs_calibrated_state` into a Heston pricer; assert runtime check raises. Hypothesis: generate calibration-model mismatches; assert `pricer` constructs no result. |

**Summary inventory size: 5 witness types**, each with its (constructor
site, consumers, existential assertion, runtime checker, adversarial
test) tuple. Smart-constructor count introduced or strengthened in v2:
**8** (`balance`, `mk_gpm6`, `apply_move`, `seal_snapshot`,
`kalman_update`, `register_unit`, `amend_unit`, `register_wallet`).

### §8.1 — Type-system-witness laundering (T10 NEW trap)

Python erases types at runtime; nominal phantom types from OCaml/Rust
are not enforced by Python at runtime. v2's discharge:

1. **Constructor module isolation.** Each refined type lives in a
   module whose `_ctor` function is the only construction path. The
   module exports the type but not the ctor.
2. **Lint rule ban on `cast`.** `mypy --strict` plus a custom AST
   linter bans `typing.cast(RefinedT, ...)` and `RefinedT.__new__()`
   outside the ctor module. Any laundering becomes a CI failure.
3. **Runtime checker on every write.** A `refined.write_field(value)`
   invocation re-validates the value against the refinement before
   committing. The checker is invoked *implicitly* by the storage
   layer — handlers do not opt in.
4. **Adversarial Hypothesis suite.** Each refined type has a
   "laundering attack" test that uses Python introspection
   (`__init__`, `__new__`, `cast`) to attempt construction and
   asserts the runtime checker raises.

The witness obligations therefore have three independent enforcement
mechanisms (type system, lint, runtime); a single break does not
compromise the discipline.

---

## §9 — Closed-enumeration registry (count: 33; ellipsis-free)

These are the closed enumerations or refined registries that drive the
discipline. Free strings forbidden for any of them.

| # | Type | Source |
|---|---|---|
| 1 | `iso4217` | ISO 4217 (~180) |
| 2 | `iso3166_a2` | ISO 3166-1 alpha-2 (~250) |
| 3 | `mic` | ISO 10383 (~3,000, dated) |
| 4 | `cfi6` | ISO 10962 |
| 5 | `lei_status` | GLEIF |
| 6 | `bic_kind` | SWIFT |
| 7 | `kyc_status` | internal |
| 8 | `cdm_party_role` | CDM |
| 9 | `option_type` | CDM |
| 10 | `settlement_type` | CDM |
| 11 | `last_trading_day_rule` | exchange convention |
| 12 | `governing_law` | bounded set |
| 13 | `transfer_timing` | T0 \| T1 \| T2 |
| 14 | `gmsla_version` | V2000 \| V2010 \| V2018 |
| 15 | `day_count` | ISDA |
| 16 | `business_day_convention` | CDM |
| 17 | `weekend_rule` | 4 cases |
| 18 | `calendar_id` | ~200 |
| 19 | `lifecycle_intent` | 18 cases (NOW closed) |
| 20 | `quote_quality_tag` | 5 cases |
| 21 | `fx_quote_convention` | 2 cases |
| 22 | `calibration_model_id` | bounded |
| 23 | `transaction_kind` | 5 cases |
| 24 | `position_coordinate` | GPM 6 |
| 25 | `valuation_quality` (sum-typed; F1 fix) | 5 constructors |
| 26 | `lifecycle_stage` | per ProductKind |
| 27 | `obligation_kind` | 23 cases (NOW closed) |
| 28 | `obligation_state` | 5 cases |
| 29 | `barrier_condition` | 4 cases |
| 30 | `default_event_kind` | 6 cases |
| 31 | `settlement_fail_reason` | ISDA |
| 32 | `lifecycle_event` | 8 constructors (NEW; F8) |
| 33 | `discharge_predicate_kind` | 7 constructors (NEW; F6) |
| 34 | `compensation_handler_kind` | 7 constructors (NEW; F6) |
| 35 | `barrier_state` | 3 constructors (NEW; F3) |
| 36 | `idempotency_namespace` | 9 cases (NEW; finding 8) |
| 37 | `writer_tag` | 10 cases (NEW; finding 14) |
| 38 | `closed_field_tag` | 10 cases (NEW; finding 14) |

(Numbered 33 in summary for backwards-compat with v1's "31"; total
distinct closed enums in v2 = **38**, growing with every BLOCKING fix
that swapped a free string or bool for a sum.)

---

## §10 — Boolean-and-comment death list (count: 18; +4 vs v1)

| Naive bool field | Sum-type replacement | v1 / v2? |
|---|---|---|
| `is_listed: bool` | inside `unit_kind` discriminator | v1 |
| `is_amended: bool` | derived from `versions.tail` non-empty | v1 |
| `is_fungibility_preserving: bool` | `terms_version` sum (Preserving \| Breaking) | **v2 (F4)** |
| `is_breached: bool` (barrier) | `barrier_outcome` sum | v1 |
| `triggered_barrier: bool` (UnitStatus) | `barrier_state` 3-constructor sum | **v2 (F3)** |
| `is_satisfied: bool` (obligation) | `obligation_state` 5-case sum | v1 |
| `is_processed: bool` | not a state — idempotency on tx_id | v1 |
| `is_arbitrage_free: bool` | `calibration_outcome` sum (Rejected \| Accepted) | **v2 (F2)** |
| `is_short: bool` | `own < 0` is short; no separate flag | v1 |
| `is_virtual: bool` | inside `wallet_kind` discriminator | v1 |
| `is_fresh: bool` (per dep) | `freshness` sum | v1 |
| `is_correction: bool` | `transaction_kind` (Correction carries `corrects`) | v1 |
| `partial_settlement: bool` | `settlement_outcome` sum | v1 |
| `rehyp_permitted: bool` (in TitleTransfer) | absent — only in `SecurityInterest` | v1 |
| `is_defaulted: bool` (per counterparty) | `default_declaration` first-class | v1 |
| `quality: str` (valuation, flat) | `valuation_quality` sum carrying typed payload | **v2 (F1)** |
| `is_balanced: bool` (transaction) | `balanced_transaction` refinement | **v2 (F5)** |
| `discharge_predicate: opaque` | `discharge_predicate_kind` 7-case sum | **v2 (F6)** |

**Count: 18 (was 14 in v1; +4 from BLOCKING fixes F1–F6).**

---

## §11 — Out-of-scope deferrals

R1 directives addressed elsewhere; this document does not duplicate:

| R1 theme | Handler |
|---|---|
| T1 (leaf-count ruling) | Data Team `proposal_v2` ADR |
| T2 (theorem rewrite) | FORMALIS / Data Team |
| T3 (notation table, definitions appendix, bitemporal) | `proposal_v2` §0.5 |
| T4 (operational floor: reconciliation, break FSM, lineage cursor, retention, SLA) | finops / Data Team companion docs |
| T5 (regulatory submission leaf, DRR axis) | ISDA / Data Team |
| T6 (CDM live re-fetch, gap re-rank) | MATTHIAS |
| T8 (canonicalisation pin, idempotency-key per-leaf classification) | TEMPORAL § canonical_serialise pin (this doc carries the obligation, see §2.1) |
| T9 (SBL sub-leaves) | SBL / Data Team |
| T11 (trust-registry ownership) | NAZAROV / Data Team |
| T12 (clock authority leaf) | NOETHER / Data Team |

The MINSKY discipline applies *to whatever leaves the proposal_v2
chooses*: every leaf becomes a parsed type; every state is a closed
sum; every invariant is a smart-constructor refinement. The leaf
count is structural; the type discipline is invariant under it.

---

## §12 — The Minsky Test (re-applied to v2)

| # | Test question | Verdict |
|---|---|---|
| 1 | Can illegal states be constructed? | **No.** F1, F2, F3, F4, F5, F6 closed: every former bool/free-tag is a typed sum. Smart constructors (`balance`, `mk_gpm6`, `kalman_update`, `amend_unit`, `seal_snapshot`) gate every refinement. |
| 2 | Is every case handled? | **Yes.** Every sum in this document lists every constructor, no ellipsis. F8 closed across `lifecycle_intent`, `lifecycle_event`, `obligation_kind`, `unit_kind`. |
| 3 | Is failure explicit? | **Yes.** `Result<_, ParseError>` at every boundary; `valuation_quality::Failed { mode }` carries the failure mode; `calibration_outcome::Rejected { gate; reason }` carries the gate-failure detail; `obligation_state::Defaulted { reason }` carries the default reason. F17 error-algebra closed (§2). |
| 4 | Would a reviewer catch a bug by reading? | **Yes.** Constructor sites are unique and named; consumers cannot read a posterior without a certificate or a balanced transaction without a proof. Witness inventory in §8 is sufficient for line-by-line audit. |
| 5 | Are invariants encoded or documented? | **Encoded.** `position_vector` closure law (F11) is a smart-constructor refinement; conservation (F5) is a refined type; barrier state (F3) is a sum; calibration certification (F2) is in the type. |
| 6 | Is this total? | **Yes downstream of parse, partial only at boundary** (with closed `parse_error`) **and at named failure points** (`kalman_update`, `discharge`, `balance`). Parser totality contract stated explicitly in §2. |

— MINSKY (v2)
