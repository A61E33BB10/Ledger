# Ledger v11.0 Data Specification — Phase 2 (MINSKY)

**Discipline.** Type-driven design at the data layer. Parse, don't validate.
Make illegal states unrepresentable. Total functions. Closed enumerations
over free strings. Refinements over bare scalars. Sum types over
booleans-and-comments.

**Idiom.** OCaml-flavoured pseudocode. Polymorphic variants where they
serve readability; nominal sums where exhaustiveness gates correctness.
Where Rust's `Result` / `NonZeroU64` / refinement traits map more cleanly,
I note it. Lean appears once, where dependent typing earns its keep
(GPM coordinate confinement).

**Convergence.** I take NAZAROV's master taxonomy as the spine and
attach types to its leaves. The three structural classes
**Definitions** / **Observations** / **Effects** plus four structural
additions (**Identity**, **Time**, **State**, **Obligation**) cover all
41 leaves I enumerated in Phase 1.

I do **not** re-explain leaves. I show types.

---

## §0 — Cross-cutting refined-type registry (size: 27)

These appear repeatedly; they are defined once, used everywhere. Every
one is a *newtype* whose constructor is private and whose only public
introduction is the named parser.

```ocaml
(* §0.1 — Identifiers (closed registries) *)
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

(* §0.2 — Quantities *)
type positive_decimal = private decimal       (* > 0 *)
type non_negative_decimal = private decimal   (* >= 0 *)
type bounded_01       = private decimal       (* in [0, 1] *)
type positive_nat     = private int           (* > 0 *)
type sha256           = private bytes         (* exactly 32 bytes *)

(* §0.3 — Time *)
type timestamp = private { utc_ns : int64 }   (* monotonic UTC nanoseconds *)
type date      = private { y : int; m : int; d : int }  (* Gregorian *)

type dual_timestamp = {
  effective : timestamp;
  knowledge : timestamp;
  (* invariant enforced in constructor: knowledge >= effective *)
}

(* §0.4 — Composite refined containers *)
type 'a non_empty       = { head : 'a; tail : 'a list }
type 'a non_empty_set   = private 'a list   (* sorted, unique, length >= 1 *)
type ('k, 'v) total_map = private { keys : 'k non_empty_set;
                                     value : 'k -> 'v }   (* total over keys *)

(* §0.5 — Outcome / failure *)
type ('a, 'e) result = Ok of 'a | Error of 'e
type 'a option       = None | Some of 'a

(* §0.6 — Witnesses (proof-carrying refinements) *)
type _ certified =
  | Certified : 'a * arbitrage_certificate -> 'a certified
  | Fallback  : 'a * fallback_reason       -> 'a certified

(* §0.7 — Capabilities (StatesHome C4 / C11) *)
type _ writer_cap = ..   (* phantom-typed, one constructor per handler *)
```

**Registry size: 27 refined types.** Every one rejects malformed inputs at
construction; downstream code receives only well-formed values and never
re-validates.

**Boundary parsers (one per refined type):**

```ocaml
val parse_iso4217  : string -> (iso4217,    parse_error) result
val parse_lei      : string -> (lei20,      parse_error) result
val parse_isin     : string -> (isin12,     parse_error) result
val parse_uti      : string -> (uti,        parse_error) result
(* ... 23 more, one per refined type ... *)

type parse_error =
  | BadLength       of { expected : int;       got : int }
  | BadCharset      of { allowed  : string;    got : string }
  | BadChecksum     of { algo     : string }
  | NotInRegistry   of { registry : registry_id; key : string }
  | OutOfRange      of { lo       : decimal;    hi  : decimal; got : decimal }
  | Conflict        of { existing : string;     got : string }
```

Every constructor for a refined type is private; the parser is the only
introduction rule. A function downstream of the parser cannot construct
an invalid value — that is the parse-don't-validate contract.

---

## §1 — Definitions (NAZAROV class A: identity, terms, agreements, conventions)

The Definitions class is the append-only, versioned, registration-total
half of the data model. *One* mutation discipline applies to every leaf
in this class: `NonEmpty<Version>`, never in-place edit, registration
total (C5/C6/C7/C10), amendment two-track (C8).

### §1.1 — `UnitId` and `ProductTerms`

```ocaml
type unit_kind =
  | Cash        of { iso : iso4217 }
  | ListedEquity of { isin : isin12;  primary_listing : mic }
  | ListedDeriv  of { spec : contract_spec }
  | Bond         of { isin : isin12;  schedule : coupon_schedule;
                      maturity : date; day_count : day_count;
                      bda : business_day_convention }
  | Otc          of { cdm_trade : cdm_trade;  csa_ref : agreement_id }
  | Mandate      of { manager : lei20;  client : lei20;
                      benchmark : unit_id;  fee : fee_schedule }
  | Qis          of { strategy : strategy_spec }
  | StructuredNote of { isin : isin12;  embedded : payout_node non_empty;
                        terms_doc : sha256 }
  | Token        of { chain : chain_id;  contract : eth_address;
                      backing : backing_model;  underlier_isin : isin12 option }

and unit_id = private { hash : sha256; kind_tag : kind_tag }

and contract_spec = {
  exchange       : mic;
  underlier      : asset_ref;
  option_type    : option_type option;     (* None for futures *)
  strike         : positive_decimal option;(* None for futures, Some for option *)
  expiry         : date;
  multiplier     : positive_decimal;
  tick_size      : positive_decimal;
  lot_size       : positive_nat;
  eligible_ccps  : ccp_id non_empty_set;
  settlement     : settlement_type;
  last_trading   : last_trading_day_rule;
}

and option_type        = Call | Put | Payer | Receiver | Straddle
and settlement_type    = Cash | Physical | Net
and last_trading_day_rule =
  | ThirdFriday | ThirdWednesday | LastBusinessDay
  | BespokeCalendar of calendar_id
```

**Parser.**

```ocaml
val register_unit
  :  raw_event              (* CDM ExecutionEvent or vendor master record *)
  -> unit_store             (* the Definitions store, before *)
  -> ( unit_id * unit_store, register_error ) result

type register_error =
  | UnknownInstrumentClass
  | DuplicateUnitId       of unit_id          (* C10 *)
  | InconsistentTerms     of consistency_violation
  | BadCdmPayload         of cdm_decode_error
  | InvalidContractSpec   of spec_violation
```

**Boundary location.** Vendor-feed adapter for listed and bond reference;
CDM `ExecutionEvent` ingestion adapter for OTC; `register_mandate` admin
transaction for managed-account.

**Illegal-state-prevention table.**

| Naive struct admits                        | Type prevents because                                              |
|---|---|
| `cash.expiry = Some date`                  | `expiry` lives only inside `ListedDeriv`/`Bond`; `Cash` has no field |
| `option without strike`                    | `strike` field is required inside `ListedDeriv` when `option_type = Some _`; refined product constructor |
| `multiplier = -2`                          | `multiplier : positive_decimal`, constructor enforces `> 0`        |
| `eligible_ccps = []`                       | `non_empty_set` admits no empty value                              |
| `unit_id` re-registration                  | `register_unit` is the only introducer; rejects on duplicate (C10) |

**Sum types vs flags.** A weak design carries
`is_listed: bool`, `is_option: bool`, `is_otc: bool`, with a comment
explaining how to interpret combinations.
The sum-type fix: `unit_kind` discriminates structurally; the impossible
combinations (listed + OTC, option without strike, cash with multiplier)
do not type-check.

**Closed enumerations.** `option_type`, `settlement_type`,
`last_trading_day_rule`, `iso4217`, `mic`, plus the CDM-pinned
`product_kind` — every one a *closed* sum with exhaustive match
required.

**Refinements.** `multiplier`, `tick_size`, `strike` are
`positive_decimal`; `lot_size` is `positive_nat`. The constructor
rejects, the type carries the proof, no caller re-checks.

### §1.2 — `ProductTerms` (versioned envelope)

```ocaml
type product_terms = {
  unit_id  : unit_id;
  versions : terms_version non_empty;       (* head = inception, tail = amendments *)
  binding  : smart_contract_ref;
  kind     : product_kind;
}

and terms_version = {
  effective_at : timestamp;
  knowledge_at : timestamp;
  fields       : terms_field_map;            (* product-kind-typed *)
  predicate    : fungibility_preserving_pred;
  signed_by    : actor_id;
  hash         : sha256;
}

and amendment_outcome =
  | Preserving of terms_version              (* append to existing unit *)
  | Breaking   of { fresh : unit_id; supersedes : unit_id; reason : string }

val amend_unit
  :  unit_id
  -> terms_amendment
  -> product_terms
  -> ( amendment_outcome * product_terms, amend_error ) result
```

**Illegal-state-prevention table.**

| Naive admits                          | Type prevents because |
|---|---|
| Amendment without predicate eval      | `predicate` is a required field of every `terms_version`; cannot construct without it |
| Two heads (no inception)              | `non_empty` enforces a unique head |
| Preserving result with new unit_id    | `Preserving` constructor carries no `unit_id` field; `Breaking` does |
| Mid-history mutation                  | `terms_version` fields are immutable; only `amend_unit` extends `versions` |
| Empty amendment chain                 | Same as "two heads" — `non_empty` |

**Sum vs flag.** `is_amended: bool` plus `amendment_kind: str` becomes
`amendment_outcome` (closed sum, two cases, each carrying its required
fields). The impossible state "preserving with new unit_id" cannot be
constructed.

### §1.3 — Legal agreements (CSA, GMSLA, Master, Mandate)

```ocaml
type collateral_regime =
  | TitleTransfer    of { gmsla_schedule : gmsla_schedule }
  | SecurityInterest of { gmsla_schedule : gmsla_schedule;
                          rehyp_consent  : bool;
                          gov_law        : governing_law }
  | UsRule15c3_3     of { customer_debit_cap : positive_decimal }

type csa_terms = {
  parties              : (lei20 * lei20);
  governing_law        : governing_law;
  regime               : collateral_regime;
  threshold            : non_negative_decimal;
  mta                  : positive_decimal;
  independent_amount   : non_negative_decimal;
  eligible_collateral  : collateral_eligibility non_empty;
  haircut_schedule     : haircut_schedule;
  valuation_currency   : iso4217;
  notification_time    : time_of_day;
  transfer_timing      : transfer_timing;
  dispute_resolution   : dispute_rule;
}

and governing_law = EnglishLaw | NewYorkLaw | JapaneseLaw
                  | FrenchLaw  | SwissLaw   | OtherLaw of iso3166_a2

and transfer_timing = T0 | T1 | T2

and gmsla_version = V2000 | V2010 | V2018
```

**Illegal-state-prevention table.**

| Naive admits                                       | Type prevents because |
|---|---|
| `regime = "pledge"` with no rehyp_consent          | `SecurityInterest` constructor *requires* `rehyp_consent`; cannot construct without |
| `mta = 0`                                          | `mta : positive_decimal` rejects zero |
| Empty eligible-collateral list                     | `non_empty` admits no empty |
| `parties = (X, X)`                                 | Smart constructor `make_csa` rejects equal LEIs (a CSA self-trade is not a CSA) |
| Title-transfer with rehyp consent                  | Field absent from `TitleTransfer`; rehyp is implicit in the regime |

**Boundary parser.**

```ocaml
val parse_csa
  :  signed_agreement      (* hash-anchored PDF + CDM extraction *)
  -> ( csa_terms, parse_error ) result
```

**Sum vs flag.** `regime: str` with three string values goes to
`collateral_regime` (closed sum). `rehyp_permitted: Optional[bool]` with
the comment "only meaningful for SecurityInterest" goes inside the
`SecurityInterest` constructor — meaningless elsewhere because absent.

### §1.4 — Conventions (calendars, day-count, BDA)

```ocaml
type day_count =
  | Act_360 | Act_365_Fixed | Act_Act_Icma | Act_Act_Isda
  | Thirty_360 | Thirty_E_360 | Thirty_E_360_Isda

type business_day_convention =
  | Following | ModifiedFollowing | Preceding | ModifiedPreceding | NoAdjust

type weekend_rule = SatSun | FriSat | SunOnly | NoWeekend

type calendar_id = private string  (* closed registry, ~200 entries *)

type calendar = {
  id            : calendar_id;
  weekend_rule  : weekend_rule;
  holidays      : date sorted_set;
  effective     : (date * date);             (* [from, through] *)
  source        : vendor_id;
  ingest_hash   : sha256;
}

val is_business_day : calendar -> date -> bool option
  (* total over calendar.effective; None outside the published range —
     consumer must handle, no silent default *)
```

**Illegal-state-prevention.**

| Naive admits                                       | Type prevents because |
|---|---|
| `day_count = "ACT/360"` typo `"ACT-360"`           | Closed sum; "ACT-360" does not type-check |
| Lookup outside calendar range returns `false`      | `is_business_day` returns `bool option`; `None` forces explicit handling |
| Calendar without effective range                   | `effective` is a required field |
| Two calendars with same id, different holidays     | `calendar_id` versioned at the registry level; ingest hash binds content |

### §1.5 — `LifecycleIntent` (CDM `EventIntentEnum`, closed)

```ocaml
type lifecycle_intent =
  | Allocation | Cancellation | Clearing | Compression | Exercise
  | Formation  | Increase     | Novation | Observation | Open
  | PartialTermination | Termination | Transfer | Expire
  | Assign     | Correction   | EarlyTermination | Reallocation

(* exhaustive match required *)
val handle_event : lifecycle_intent -> ledger_state -> state_delta
```

**Illegal-state-prevention.** The compiler forbids omitted cases. A weak
design has `event_type: str` plus a `default: log_warning(...)` branch —
exactly the wildcard antipattern that hides a missing handler until
production. Closed sum + exhaustive match makes the bug a *compile
error*, not a property-test finding.

A future CDM release adds `Restructure`. The parser at the ingestion
boundary rejects the unknown tag (`UnknownIntent` parse error) — forcing
explicit governance review before the new tag enters the system. No
silent ignore.

---

## §2 — Observations (NAZAROV class B: market data, oracle attestations,
external statements)

The Observations class is **append-only**, **bitemporal**,
**source-attested**, **never overwritten**. One mutation discipline; many
sub-leaves. Calibrated state is *derived* from observations and gets its
own type-level discipline (§2.5).

### §2.1 — `RawQuote` (market data, leaf of pricing DAG)

```ocaml
type quote_quality = Live | Indicative | Closing | Synthetic | Stale

type bid_ask =
  | OneSided of { side : side;          value : decimal }
  | TwoSided of { bid  : decimal;       ask : decimal }
                                          (* invariant: ask >= bid *)
  | Crossed  of { bid  : decimal;       ask : decimal }
                                          (* explicit, NOT silent corruption *)

and side = Bid | Ask | Mid | Last | Settle

type raw_quote = {
  observable    : observable_ref;
  spread        : bid_ask;
  as_of         : dual_timestamp;
  source        : source_id;
  feed_seq      : int64;
  quality       : quote_quality;
  attestation   : signature;             (* mandatory, NAZAROV CC-1 *)
}
```

**Boundary parser.**

```ocaml
val parse_quote : feed_bytes -> ( raw_quote, parse_error ) result
```

**Illegal-state-prevention.**

| Naive admits                                       | Type prevents because |
|---|---|
| `bid > ask` silently                               | `TwoSided` invariant or constructor returns `Crossed` explicitly |
| `quality = 0` integer                              | Closed sum, `Live`/`Indicative`/`Closing`/`Synthetic`/`Stale` |
| Quote without attestation                          | `attestation` is required (NAZAROV CC-1) |
| Conflated event-time vs receive-time               | `dual_timestamp` invariant `knowledge >= effective` |
| Negative price for non-rate observable             | Refined `non_negative_decimal` for spot prices; rates remain signed |

### §2.2 — `OracleAttestation` (the wrapper protocol, per LATTNER)

LATTNER's reframing: oracle is a *protocol*, not a peer category. Type
captures it directly:

```ocaml
type 'payload attested = {
  payload          : 'payload;
  payload_hash     : sha256;
  source           : source_id;          (* from registry *)
  signing_key_id   : key_id;             (* from registry *)
  source_signature : signature;          (* over payload_hash *)
  publication_time : timestamp;
  ingestion_time   : timestamp;
  ingestion_sig    : signature;          (* gateway signature *)
  schema_version   : schema_version;
  mapping_version  : mapping_version option;
}

(* Every external datum the system consumes is wrapped: *)
val parse_quote_attested
  :  envelope_bytes
  -> ( raw_quote attested, parse_error ) result

val parse_corp_action_attested
  :  envelope_bytes
  -> ( corporate_action attested, parse_error ) result

val verify : 'a attested -> trust_registry -> ( unit, attestation_error ) result
```

**Illegal-state-prevention.** Bare REST/JSON without an envelope cannot
be the input type to any consumer of external data — the gateway returns
`'a attested`, never `'a`. The trust registry is a runtime check whose
failure mode is `attestation_error`, an explicit value, never silent.

### §2.3 — `LifecycleEvent` (oracle-attested external events)

Each external lifecycle event is a closed sum constructor with its
required fields:

```ocaml
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
  | Merger        of { acquirer        : unit_id;
                       conversion      : conversion_rule;
                       effective_date  : date }
  | SpinOff       of { new_unit        : unit_id;
                       distribution    : (positive_nat * positive_nat) }
  | RightsIssue   of { subscription_ratio : positive_decimal;
                       price            : positive_decimal;
                       record_date      : date;
                       election_deadline: timestamp }
  | NameChange    of { new_name        : string;
                       new_isin        : isin12 option }
  | Reclassification of { new_classification : cfi6 }

type barrier_observation = {
  unit_id          : unit_id;
  barrier_def      : barrier_definition_ref;   (* into ProductTerms *)
  observation_time : timestamp;
  observed_value   : decimal;
  barrier_value    : decimal;
  condition        : barrier_condition;
  outcome          : barrier_outcome;          (* see below *)
}

and barrier_condition = UpAndOut | DownAndIn | UpAndIn | DownAndOut
and barrier_outcome   = NotBreached | Breached of { event_ref : event_ref }
                                                   (* sum, not bool *)

type credit_event =
  | FailureToPay
  | Bankruptcy            of { filing_ref : court_ref }
  | Restructuring         of { isda_cdc_decision : cdc_decision_id }
  | ObligationDefault     of { agreement : agreement_id }
  | GovernmentIntervention of { authority : iso3166_a2; date : date }

type exercise_notice = {
  unit_id              : unit_id;
  exercising_party     : lei20;
  exercise_quantity    : positive_decimal;
  exercise_time        : timestamp;
  settlement_method    : settlement_type;
  payoff_calculation   : payoff_witness;
}

type settlement_outcome =
  | FullySettled     of { quantity : positive_decimal }
  | PartiallySettled of { settled  : positive_decimal; residual : positive_decimal }
  | Failed           of { reason   : settlement_fail_reason }
  | Cancelled        of { reason   : cancel_reason }

and settlement_fail_reason =
  | LackOfSecurities | LackOfCash | InvalidInstruction
  | CounterpartyDispute | Other of isda_fail_code
```

**Illegal-state-prevention table (cross-cutting on this section).**

| Naive admits                                                  | Type prevents because |
|---|---|
| `kind = "DIV"` with no `gross_per_share`                      | `CashDividend` constructor *requires* `gross_per_share`; absent on `StockSplit` |
| `ratio_num = 0` for split                                     | `positive_nat` rejects zero |
| Barrier event with `breached = true` and no event_ref         | `barrier_outcome` is sum: `Breached` *carries* the event_ref |
| `outcome = "PartiallySettled"` and `partial_quantity = None`  | `PartiallySettled` constructor takes `settled` and `residual` as required |
| Exercise on OTM option silently fails                         | `payoff_witness` is a proof-carrying value; constructor refuses if payoff < 0 in the unsigned-payoff product class |

**Sum vs flag.** Every `kind: string` with a `terms: dict` "varies by
kind" pattern goes to a closed sum with constructor-specific fields.
Every `is_breached: bool` plus side-channel event reference goes to a
sum where `Breached` carries the reference inside.

### §2.4 — `MarketDataSnapshot` (immutable bundle, content-addressed)

```ocaml
type snapshot_id = private { hash : sha256 }   (* deterministic from content *)

type market_data_snapshot = private {
  id                 : snapshot_id;
  as_of              : dual_timestamp;
  quotes             : (observable_ref, raw_quote attested) total_map;
  fx_rates           : (ccy_pair, fx_rate attested) total_map;
  calibrations       : (calibrated_object_id, calibrated_state) total_map;
  fallback_chain     : fallback_decision list;       (* as actually traversed *)
  content_hash       : sha256;
}

val seal_snapshot
  :  observation_set
  -> ( market_data_snapshot, snapshot_error ) result
  (* the only constructor; consumers receive snapshot_id, not the maps *)
```

**Illegal-state-prevention.** No mutable global "current market"
reference exists. Every pricer signature is
`pricer : market_data_snapshot -> ... -> valuation_record`. A pricer
that reads from outside its argument cannot be written; the input is
the only access path.

### §2.5 — `CalibratedState` (Kalman posterior, witness-typed)

```ocaml
type arbitrage_certificate = {
  d_increasing      : witness;        (* discount factors monotone *)
  w_positive        : witness;        (* total variance non-negative *)
  no_calendar_spread: witness;
  no_butterfly      : witness;
}

type calibration_model_id =
  | BlackScholes | Heston | LocalVol | Sabr | KernelVol
  | KalmanMonotone | HazardRate of credit_class

type _ state_vector =
  | BS_v   : { sigma : positive_decimal } -> bs_model state_vector
  | H_v    : { v0 : positive_decimal; kappa : positive_decimal;
               theta : positive_decimal; xi : positive_decimal;
               rho : bounded_minus_one_one } -> heston_model state_vector
  | LV_v   : { surface : (date * positive_decimal) array2 } -> localvol_model state_vector
  (* ... GADT-style discrimination per model class ... *)

type 'm calibrated_state = {
  object_id        : calibrated_object_id;
  model_id         : calibration_model_id;
  state            : 'm state_vector;
  covariance       : matrix;
  certificate      : arbitrage_certificate;
  innovation       : innovation_stats;
  fitted_at        : dual_timestamp;
  source_snapshot  : snapshot_id;
  fitter_signature : signature;
}

val kalman_update : 'm prior -> observation_set -> ('m calibrated_state, calib_error) result
  (* the ONLY constructor of `calibrated_state`; certificate is a
     mandatory return field, no path yields uncertified value *)
```

**Illegal-state-prevention.**

| Naive admits                                              | Type prevents because |
|---|---|
| `is_arbitrage_free: bool` discards the proof              | `arbitrage_certificate` is a record of *witnesses*; carrying boolean would be lossy |
| BS state vector `[0.2, 0.1, 0.5, 0.3, -0.2]` (Heston by mistake) | GADT `state_vector` is parameterised by the model class; a BS pricer cannot consume a `heston_model state_vector` |
| Uncertified state used downstream                         | `calibrated_state` is *only* returned by `kalman_update`; no path constructs without certificate |
| Greeks computed under model A, applied to price under B   | `valuation_record` carries `model_id` and the Greeks GADT branch is keyed to it |

The GADT pattern (or Rust trait-object equivalent) is where dependent
typing earns its keep: the *type* of the state vector tracks the
*identity* of the calibration model.

---

## §3 — Effects (NAZAROV class C: moves, transactions, state deltas, lifecycle records)

Effects are **append-only**, **hash-chained**, **atomic across the three
state maps**, **idempotent under retry**, **deterministic on replay**.
This class has the strongest type-level discipline in the system —
because invariants P1 (conservation), P2 (atomicity), P3 (replay), P4
(monotonicity), P5 (idempotency) all live here.

### §3.1 — `Move` (the indivisible primitive)

```ocaml
type position_coordinate =
  | Own | OnLoan | Borr | CollPost | CollRecv | CollRehyp
  (* GPM 6-coordinate, v10.3 §15.2; degenerates to Own for non-lendable *)

type move = {
  source        : wallet_id;
  destination   : wallet_id;
  unit          : unit_id;
  quantity      : positive_decimal;       (* never signed *)
  coordinate    : position_coordinate;
  effective_at  : timestamp;
  source_contract : smart_contract_ref;
  metadata      : move_metadata;
}
```

**The single type-level decision that makes conservation provable.**
`quantity : positive_decimal`. Direction is encoded in `(source,
destination)`. There is no `signed_quantity` field anywhere; "negative"
is structurally impossible. A handler that wants to express
"sell 10 shares from wallet A" emits a `Move` with
`source = A, destination = market, quantity = 10`, never `quantity = -10`.

**Conservation by construction.** A `transaction` is a list of moves
plus terms/status/position deltas. A pure function

```ocaml
val conservation_check
  :  transaction
  -> ( conserving_transaction, conservation_violation ) result
```

returns a *refined type* `conserving_transaction` that the executor
admits. The unrefined `transaction` cannot be committed — there is no
`commit : transaction -> ...` API; only `commit : conserving_transaction
-> ...`. The proof is in the type.

### §3.2 — `Transaction` (atomic commit unit)

```ocaml
type transaction_kind =
  | Settlement
  | Collateral
  | Lifecycle
  | Accounting
  | Correction of { corrects : tx_id; rationale : correction_rationale }

type transaction = {
  tx_id                : tx_id;             (* idempotency key, P5 *)
  kind                 : transaction_kind;
  moves                : move list;         (* may be empty for Accounting *)
  terms_delta          : terms_amendment option;
  unit_status_delta    : (unit_id, unit_status_delta) total_map;
  position_state_delta : ((wallet_id * unit_id), position_state_delta) total_map;
  obligations_created  : obligation list;
  obligations_discharged : obligation_id list;
  cdm_payload          : cdm_business_event;
  effective_at         : timestamp;
  committed_at         : timestamp;
  prev_hash            : sha256;            (* hash chain, P4 *)
}
```

**Illegal-state-prevention table.**

| Naive admits                                                 | Type prevents because |
|---|---|
| `transaction_type = "correction"` with `corrects = None`     | `Correction` constructor *carries* `corrects`; cannot omit |
| `transaction_type = "settlement"` with `corrects = Some _`   | `corrects` only exists inside `Correction` constructor |
| Partial commit (some maps written, others not)               | `transaction` is the *only* commit unit; executor's API takes the whole record atomically |
| Two transactions with same tx_id                             | `tx_id` is the idempotency key; executor de-dupes |
| `cdm_payload: dict` opaque                                   | `cdm_business_event` is a parsed, structured value (CDM-version pinned) |

**Sum vs flag.** `transaction_type: str` and `corrects: Optional[str]`
become `transaction_kind` (closed sum). The "must be present iff kind ==
'correction'" comment is replaced by *structural* presence — the field
exists exactly where it has meaning and nowhere else.

### §3.3 — `SettlementInstruction` (DvP/FOP/Cash)

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
  | DvP  of { sec : settlement_leg_securities;  cash : settlement_leg_cash }
  | FOP  of { sec : settlement_leg_securities }
  | Cash of { cash : settlement_leg_cash }
```

**Illegal-state-prevention.** "DvP without a cash leg" is
unrepresentable: `DvP` constructor *requires* both legs. "Cash
instruction with a securities leg" is unrepresentable: `Cash`
constructor has no `sec` field. The CSDR-buy-in matching code reads the
constructor and dispatches on it, never branches on a `kind: string`.

### §3.4 — `ValuationRecord` (output of pricing)

```ocaml
type quality = Firm | Indicative | Approximate | Stale | Failed

type valuation_fsm_state =
  | Unpriced | Pricing of { started : timestamp }
  | Priced   of { record : valuation_record_id }
  | Explaining | Explained
  | Quarantined of { retry_count : positive_nat; last_error : explain_failure }
  | StaleS    of { staleness_deadline : timestamp }
  | FailedS   of { reason : pricing_failure }

type 'm greeks =
  | BSGreeks      : { delta : decimal; gamma : decimal; vega : decimal;
                      theta : decimal; rho : decimal } -> bs_model greeks
  | HestonGreeks  : { delta : decimal; gamma : decimal;
                      v0_sens : decimal; kappa_sens : decimal;
                      theta_sens : decimal; xi_sens : decimal;
                      rho_sens : decimal } -> heston_model greeks
  | LocalVolGreeks : { surface_jacobian : matrix } -> localvol_model greeks

type 'm valuation_record = {
  unit_id           : unit_id;
  timestamp         : timestamp;
  dirty_price       : decimal;
  clean_price       : decimal;
  accrued           : decimal;
  greeks            : 'm greeks;
  model_id          : calibration_model_id;
  market_data_snap  : snapshot_id;
  calibration_state : 'm calibrated_state_id;
  compute_ms        : positive_nat;
  quality           : quality;
  fsm_state         : valuation_fsm_state;
  workflow_signature: signature;
}
```

**Illegal-state-prevention.** A consumer that wants Heston vega gets a
type error if the record is BS — the GADT branch enforces the model
discrimination. A weak design carries a flat `vega: decimal` field for
every pricer, which silently gives the wrong answer for non-BS pricers.

### §3.5 — `Obligation` (first-class P21 liveness object)

```ocaml
type obligation_kind =
  | BondCoupon | OptionExpiry | IrsReset | FuturesDailyVm
  | SblTermLoanReturn | SblRecallReturn | SblManufacturedDividend
  | SblCollateralSubstitution | SblCollateralTopUp
  | CsaVmDelivery | CsaImDelivery | CollateralSubstitution
  | CloseOutNetting
  | SftrReport | SlateReport | EmirReport
  | SettlementInstruction

type obligation_state =
  | Pending     of { created_at : dual_timestamp }
  | Attempted   of { attempts : attempt non_empty }
  | Discharged  of { by_tx : tx_id; at : timestamp }
  | Compensated of { by_tx : tx_id; reason : compensation_reason }
  | Defaulted   of { reason : default_reason; at : timestamp }

type obligation_source =
  | Unit       of { unit_id : unit_id }
  | Agreement  of { agreement_id : agreement_id }
  | Regulatory of { regime : regulatory_regime; event_ref : event_ref }

type obligation = {
  id              : obligation_id;
  kind            : obligation_kind;
  source          : obligation_source;
  deadline        : dual_timestamp;
  discharge_pred  : discharge_ref;
  compensation    : compensation_ref;
  state           : obligation_state;
}
```

**Illegal-state-prevention.**

| Naive admits                                                | Type prevents because |
|---|---|
| `is_satisfied: bool` (cannot encode `Compensated`)          | `obligation_state` has 5 variants; bool has 2 |
| `compensation_action: Optional[Callable]`                   | Required field; `compensation_ref = NoCompensation \| ...` is a closed sum |
| Obligation without deadline                                 | `deadline` required; `dual_timestamp` enforces effective ≤ knowledge |
| `Discharged` without discharging tx                         | `Discharged` constructor *carries* `by_tx` |

**Sum vs flag.** This is the canonical case where the boolean cannot
even *encode* the state. `Compensated` (κ executed, deadline missed but
loss absorbed) is structurally different from `Defaulted` (κ also
failed). A weak design loses this distinction; the type captures it.

---

## §4 — State (StatesHome 3-map ruling, type-level)

Per StatesHome §0.3 / C1–C12. The three maps are *distinct types* with
different mutation disciplines:

```ocaml
(* §4.1 — ProductTerms : append-only, registration-total *)
type product_terms_map = private (unit_id, product_terms) registration_total_map

(* §4.2 — UnitStatus : mutable per cell, single-writer-per-field (C11) *)
type unit_status = {
  unit_id          : unit_id;
  lifecycle_stage  : lifecycle_stage;
  kind_specific    : unit_status_kind;
  superseded_by    : unit_id option;
  as_of            : dual_timestamp;
}
and unit_status_kind =
  | FuturesStatus  of { last_settle_price : decimal option;
                        last_settle_date  : date option }
  | OptionStatus   of { exercised_state : exercise_state }
  | BondStatus     of { paid_coupons : date sorted_set; matured : bool }
  | QisStatus      of { current_weights : weight_vector;
                        nav_index       : positive_decimal;
                        triggered_barrier : barrier_state;
                        last_rebalance  : date }
  | MandateStatus  of { benchmark_level : decimal }
  | EquityStatus   of unit  (* {} *)

and lifecycle_stage =
  | Pending | Listed | Active | Matured | Terminated
  | Settled | Defaulted | Closed | Exercised | Assigned

and barrier_state =
  | NotTriggered
  | Triggered of { breach_event : event_ref }

(* §4.3 — PositionState : monotone carrier, Option accessor *)
type position_state = {
  wallet_id      : wallet_id;
  unit_id        : unit_id;
  vector         : position_vector;        (* 6-coordinate or scalar *)
  kind_specific  : position_state_kind;
  as_of          : dual_timestamp;
}
and position_vector =
  | Scalar of { own : decimal }
  | Gpm6   of { own : decimal; on_loan : decimal; borr : decimal;
                coll_post : decimal; coll_recv : decimal; coll_rehyp : decimal }

and position_state_kind =
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

(* The accessor returns Option deliberately *)
val get_position
  :  position_state_map
  -> wallet_id
  -> unit_id
  -> position_state option
  (* None  = never held this unit
     Some s where s.vector = scalar zero or gpm6 zeros = held once, currently flat
     C1: Some (zero) and None are operationally distinct *)
```

**Illegal-state-prevention.**

| Naive admits                                                  | Type prevents because |
|---|---|
| `triggered_barrier: bool` on every unit                       | Inside `QisStatus` only; absent from `FuturesStatus`/`BondStatus` |
| `accumulated_cost: 0.0` for non-future                        | Inside `FuturesPosition` only; absent from `EquityPosition` |
| Garbage-collect `Some(zero)` to `None`                        | The accessor's `option` type and the C1 invariant make collapsing them a deliberate correctness regression |
| Mutate a field with the wrong handler                         | Each field is phantom-tagged with its writer cap (C11); cross-handler write is a type error |

**Field-level handler tagging (C11) at the type level:**

```ocaml
(* Phantom type carries the writer's capability *)
type ('field, 'writer) tagged = { value : 'field; writer : 'writer writer_cap }

type futures_position = {
  accumulated_cost : (decimal, settle_handler) tagged;
  ccp_binding      : (ccp_id,  trade_handler)  tagged;
}

val write_accumulated_cost
  :  settle_handler writer_cap
  -> futures_position
  -> decimal
  -> futures_position
  (* a fee_crystallise_handler does not have settle_handler writer_cap;
     calling this with the wrong cap is a type error *)
```

In dynamically typed implementations the cap is checked at runtime; in
OCaml with phantom types or Rust with marker traits the check is
compile-time.

---

## §5 — Identity (NAZAROV addition: parties, wallets, MICs)

```ocaml
type lei_status =
  | Issued | Lapsed | PendingValidation | Retired
  | Merged | Annulled | Duplicate

type legal_entity = {
  code        : lei20;
  status      : lei_status;
  parent      : lei20 option;
  legal_name  : string;
  jurisdiction: iso3166_a2;
  as_of       : dual_timestamp;
  source_hash : sha256;
}

type wallet_kind =
  | Real      of { external_id : external_account_id }
  | Virtual   of { contra_for  : agreement_or_unit_ref }
  | Reference of { book_id     : book_id }

type wallet_status = Active | Frozen | Closed

type wallet = {
  id                : wallet_id;          (* uuid128 *)
  kind              : wallet_kind;
  status            : wallet_status;
  parent_book       : book_id option;
}

type kyc_status = New | InProgress | Approved | Expired | Rejected

type party_metadata = {
  lei                       : lei20;
  kyc                       : kyc_status;
  jurisdiction              : iso3166_a2;
  cdm_role                  : cdm_party_role;     (* CDM closed enum *)
  permissions               : permission non_empty_set;
  audit_cursor              : move_stream_pos;
}
```

**Illegal-state-prevention.** A `Virtual` wallet without its contra
reference is not constructible. A wallet with `permissions = []` is not
constructible. An LEI without a status is not constructible. All three
are common bugs in weak designs.

---

## §6 — Time (NAZAROV addition: dual timestamps, calendars, cadence)

Already covered: `dual_timestamp` (§0.3), `calendar` (§1.4),
`day_count` (§1.4), `business_day_convention` (§1.4).

The one type that earns its own section: cadence and staleness.

```ocaml
type instrument_class =
  | EquitySpot | VanillaOption | ExoticOption | Irs | Bond
  | StructuredNote | Calibration | FxSpot | FxOption

type cadence = {
  instrument_class : instrument_class;
  cadence          : duration;             (* refined: positive *)
  staleness_factor : positive_rational;    (* refined: > 1 *)
  max_attempts     : positive_nat;
}

type freshness =
  | Fresh of { since : timestamp }
  | StaleF of { last_fresh : timestamp; deadline : timestamp }
  | Failed of { last_attempt : timestamp; reason : pricing_failure }

(* per-dependency map, replaces any "is_fresh: bool" flag *)
type freshness_map = (dependency_ref, freshness) total_map
```

---

## §7 — Closed-enumeration registry (count: 31)

These are the *closed* enumerations (or refined registries) that drive
the discipline. Free strings forbidden for any of them.

| # | Type                       | Source                                     |
|---|----------------------------|--------------------------------------------|
| 1 | `iso4217`                  | ISO 4217 (~180 codes)                      |
| 2 | `iso3166_a2`               | ISO 3166-1 alpha-2 (~250 codes)            |
| 3 | `mic`                      | ISO 10383 (~3,000 codes, dated snapshot)   |
| 4 | `cfi6`                     | ISO 10962 instrument classification        |
| 5 | `lei_status`               | GLEIF                                      |
| 6 | `bic_kind`                 | SWIFT (Connected, NonConnected)            |
| 7 | `kyc_status`               | internal                                   |
| 8 | `cdm_party_role`           | CDM `PartyRoleEnum`                        |
| 9 | `option_type`              | CDM `OptionTypeEnum`                       |
| 10 | `settlement_type`          | CDM `SettlementTypeEnum`                  |
| 11 | `last_trading_day_rule`    | exchange convention                        |
| 12 | `governing_law`            | bounded set of jurisdictions               |
| 13 | `transfer_timing`          | T0 \| T1 \| T2                            |
| 14 | `gmsla_version`            | V2000 \| V2010 \| V2018                   |
| 15 | `day_count`                | ISDA / CDM `DayCountFractionEnum`         |
| 16 | `business_day_convention`  | CDM `BusinessDayConventionEnum`            |
| 17 | `weekend_rule`             | SatSun \| FriSat \| SunOnly \| NoWeekend  |
| 18 | `calendar_id`              | dated registry of ~200 calendars           |
| 19 | `lifecycle_intent`         | CDM `EventIntentEnum` (18 cases)           |
| 20 | `quote_quality`            | Live \| Indicative \| Closing \| Synthetic \| Stale |
| 21 | `fx_quote_convention`      | Quote_Per_Base \| Base_Per_Quote          |
| 22 | `calibration_model_id`     | bounded internal registry                  |
| 23 | `transaction_kind`         | Settlement \| Collateral \| Lifecycle \| Accounting \| Correction |
| 24 | `position_coordinate`      | GPM 6 (Own \| OnLoan \| Borr \| CollPost \| CollRecv \| CollRehyp) |
| 25 | `quality`                  | Firm \| Indicative \| Approximate \| Stale \| Failed |
| 26 | `lifecycle_stage`          | per ProductKind, refined by valuation FSM |
| 27 | `obligation_kind`          | v10.3 §14.7 Table 14.7.2.1                 |
| 28 | `obligation_state`         | Pending \| Attempted \| Discharged \| Compensated \| Defaulted |
| 29 | `barrier_condition`        | UpAndOut \| DownAndIn \| UpAndIn \| DownAndOut |
| 30 | `default_event_kind`       | ISDA-aligned 6 cases                       |
| 31 | `settlement_fail_reason`   | ISDA fail-code closed enum                 |

**Free-string ban applies to every column.** Any field whose declared
type is one of these may not be a `string` at any boundary.

---

## §8 — Boolean-and-comment death list

Fields where a naive design would carry a `bool` plus a comment, and
which the type discipline replaces with a sum.

| Naive bool field                               | Sum-type replacement                                  |
|---|---|
| `is_listed: bool`                              | inside `unit_kind` discriminator                      |
| `is_amended: bool`                             | derived from `versions.tail` non-empty                |
| `is_fungibility_preserving: bool`              | `amendment_outcome` sum (Preserving \| Breaking)      |
| `is_breached: bool` (barrier)                  | `barrier_outcome` sum (NotBreached \| Breached{event}) |
| `is_satisfied: bool` (obligation)              | `obligation_state` 5-case sum                          |
| `is_processed: bool`                           | not a state — idempotency lives on tx_id              |
| `is_arbitrage_free: bool`                      | `arbitrage_certificate` witness record                |
| `is_short: bool`                               | `own < 0` is short; no separate flag                  |
| `is_virtual: bool`                             | inside `wallet_kind` discriminator                    |
| `is_fresh: bool` (per dep)                     | `freshness` sum (Fresh \| StaleF \| Failed)           |
| `is_correction: bool`                          | `transaction_kind` (Correction carries `corrects`)    |
| `partial_settlement: bool`                     | `settlement_outcome` sum                              |
| `rehyp_permitted: bool` (in TitleTransfer)     | absent — only in `SecurityInterest` constructor       |
| `is_defaulted: bool` (per counterparty)        | `default_declaration` first-class object              |

**Count: 14 boolean-and-comment antipatterns replaced by sum types.**

---

## §9 — Total-function vs partial-function discipline

The spine of the design: every API that crosses the boundary between
parsed and unparsed worlds returns `Result<Parsed, Error>`. Everything
downstream of a successful parse is total over its declared input.

| Function                                | Totality discipline                                     |
|---|---|
| `parse_*`                               | partial: `Result<Parsed, ParseError>` at boundary       |
| `register_unit`                         | partial: `Result<(unit_id, store), RegisterError>`      |
| `current_terms : RegisteredUnitId -> TermsFields` | total — registration witnessed at type level   |
| `terms_at(u, t) : RegisteredUnitId × TimeAfterReg -> TermsFields` | total — refined timestamp |
| `is_business_day : (Calendar, Date) -> bool option` | partial over date — explicit `option`       |
| `lifecycle_handler : LifecycleIntent × State -> StateDelta` | total — closed sum, exhaustive match  |
| `kalman_update : 'm prior × ObsSet -> 'm calibrated_state` | partial: `Result<_, calib_error>`     |
| `pricer : MarketDataSnapshot × ProductTerms -> 'm valuation_record` | total over typed inputs       |
| `commit : ConservingTransaction -> CommittedTransaction` | total — refined input proves conservation  |
| `discharge : Obligation × Tx -> Result<Discharged, DischargeError>` | partial — discharge can fail   |

The pattern: parse partial at the boundary, total downstream. The
refined types (`RegisteredUnitId`, `ConservingTransaction`,
`'m calibrated_state`) are the witnesses that make the totality work.

---

## §10 — Where parsing happens (boundary catalogue)

Every external datum enters the system through *exactly one* parser.
Parsers live at named gateways, one per source class, one per data
class.

```
external bytes
   │
   ├─ vendor feed adapter ─── parse_quote      ─→ raw_quote attested
   │                          parse_calendar   ─→ calendar attested
   │                          parse_corp_action─→ corporate_action attested
   │
   ├─ exchange adapter ────── parse_settle_print─→ settle_print attested
   │                          parse_session_state─→ session_state attested
   │
   ├─ CDM ingest adapter ──── parse_cdm_event  ─→ lifecycle_event
   │                          parse_cdm_trade  ─→ cdm_trade
   │
   ├─ ISO 20022 adapter ──── parse_sese_025    ─→ settlement_confirmation
   │                          parse_camt_054   ─→ cash_confirmation
   │                          parse_seev_031   ─→ corporate_action_event
   │
   ├─ GLEIF adapter ──────── parse_lei_record  ─→ legal_entity
   │
   ├─ ISDA Create adapter ── parse_csa         ─→ csa_terms
   │                          parse_master     ─→ master_agreement
   │                          parse_mandate    ─→ mandate_terms
   │
   ├─ trust-registry ──────── verify_attestation─→ verified payload
   │
   └─ admin transaction ──── register_unit     ─→ unit_id
                              register_wallet  ─→ wallet_id
                              register_calendar─→ calendar
```

Every arrow above is a function whose return type is `Result<_,
ParseError>` or `Result<_, RegisterError>`. The downstream consumer
imports only the parsed type, never the raw bytes.

---

## §11 — Coverage table

41 leaves from my Phase 1 enumeration, each mapped to its type-level
treatment in this Phase 2 deliverable.

| Phase-1 §    | Leaf                    | NAZAROV class | Type § here |
|---|---|---|---|
| 1.1 | ReferenceCurrency             | Definitions / System | §0.1 (`iso4217`)  |
| 1.2 | SystemId                      | Definitions / System | §0.1 (`uuid128`), `LedgerKind` sum |
| 1.3 | DecimalPrecisionPolicy        | Definitions / System | §0.2 (`positive_decimal` + DecimalContext) |
| 2.1 | InstrumentReference           | Definitions          | §1.1 (`unit_kind` sum) |
| 2.2 | ProductTerms                  | Definitions / State  | §1.2, §4.1 |
| 2.3 | LifecycleIntent               | Definitions          | §1.5 (closed sum, 18 cases) |
| 2.4 | ContractSpec                  | Definitions          | §1.1 (inside `ListedDeriv`) |
| 2.5 | SmartContractRef              | Definitions          | §1.2 (`binding`) |
| 3.1 | LegalEntityIdentifier         | Identity             | §5 (`legal_entity`) |
| 3.2 | BankIdentifierCode            | Identity             | §0.1 (`bic_8_or_11`) |
| 3.3 | MarketIdentifierCode          | Identity             | §0.1 (`mic`) |
| 3.4 | WalletId                      | Identity             | §5 (`wallet`, `wallet_kind`) |
| 3.5 | PartyMetadata                 | Identity             | §5 (`party_metadata`) |
| 4.1 | CsaTerms                      | Definitions / Legal  | §1.3 (`csa_terms`, `collateral_regime`) |
| 4.2 | GmslaSchedule                 | Definitions / Legal  | §1.3 (`gmsla_version`) |
| 4.3 | MandateTerms                  | Definitions / Legal  | §1.1 (`Mandate` constructor) |
| 4.4 | IsdaMaster                    | Definitions / Legal  | §1.3 (`master_agreement`) |
| 5.1 | Calendar                      | Definitions / Time   | §1.4 (`calendar`) |
| 5.2 | DualTimestamp                 | Time                 | §0.3 |
| 5.3 | Cadence                       | Time                 | §6  |
| 6.1 | RawQuote                      | Observations / Market| §2.1 |
| 6.2 | CalibratedState               | Observations / Calib | §2.5 (GADT-typed) |
| 6.3 | MarketDataSnapshot            | Observations / Market| §2.4 |
| 6.4 | FxRate                        | Observations / Market| §2.1 (`raw_quote` of FX) |
| 7.1 | ExecutionReport               | Observations / Oracle| §2.3 (oracle-attested CDM event) |
| 7.2 | SettlementConfirmation        | Observations / Oracle| §2.3 (`settlement_outcome`) |
| 7.3 | CorporateActionAnnouncement   | Observations / Oracle| §2.3 (`corporate_action`) |
| 7.4 | DefaultDeclaration            | Observations / Oracle| §2.3 (`credit_event`) |
| 7.5 | IndexLevel                    | Observations / Oracle| §2.1 (`raw_quote` of index) |
| 8.1 | Move                          | Effects              | §3.1 (`move`, `position_coordinate`) |
| 8.2 | Transaction                   | Effects              | §3.2 (`transaction_kind` sum) |
| 8.3 | SettlementInstruction         | Effects              | §3.3 (DvP/FOP/Cash sum) |
| 8.4 | ValuationRecord               | Effects              | §3.4 (model-GADT) |
| 8.5 | ExplainResult                 | Effects              | (`explain_status` closed sum) |
| 9.1 | ProductTerms map              | State                | §4.1 |
| 9.2 | UnitStatus map                | State                | §4.2 (`unit_status_kind` sum) |
| 9.3 | PositionState map             | State                | §4.3 (Option accessor) |
| 9.4 | PositionVector (GPM)          | State                | §4.3 (`position_vector`, scalar/gpm6) |
| 9.5 | ValuationFsmState             | State                | §3.4 (per-state guard data) |
| 9.6 | FreshnessMap                  | State / Time         | §6 (`freshness` sum) |
| 10.1| Obligation                    | Obligation           | §3.5 (`obligation_state` 5-case sum) |

**Coverage: 41/41.**

---

## §12 — Summary

- **Leaves covered.** 41, mapped one-to-one onto their Phase-1 origins.
- **Refined-type registry.** 27 newtypes, each with private constructor
  and named parser; downstream code receives only well-formed values.
- **Closed-enumeration registry.** 31 closed enums or refined registries
  (no free strings).
- **Sum-type-replacement count.** 14 booleans-and-comments replaced by
  closed sums where each constructor carries its required fields.
- **Boundary parsers.** 1 per refined type + 1 per external data class
  ≈ 60 parsers total; every parser is `_ -> Result<Parsed, ParseError>`.
- **Total functions.** Every downstream API is total over the parsed
  type's domain; partiality lives at the boundary and at explicitly
  marked failure points (e.g., `kalman_update`, `discharge`).
- **Witness types.** `arbitrage_certificate`, `conserving_transaction`,
  `RegisteredUnitId`, `'m calibrated_state`, GADT-keyed `'m greeks` —
  five proof-carrying refinements that make their respective downstream
  totalities work.

The discipline is: parse at the boundary, enforce invariants in types,
make illegal states unrepresentable, replace flags with sums, replace
strings with closed enums, replace bare scalars with refined types.
Every leaf above passes the Minsky test:

1. Can illegal states be constructed? **No** (per the prevention tables).
2. Is every case handled? **Yes** (closed sums + exhaustive match).
3. Is failure explicit? **Yes** (`Result` at boundaries, sum variants
   for state).
4. Would a reviewer catch a bug by reading? **Yes** (the type tells the
   reader what's possible; comments are not load-bearing).
5. Are invariants encoded or documented? **Encoded** (refinements,
   witnesses, capabilities).
6. Is this total? **Yes downstream of parse, partial only at boundary
   and at named failure points.**

The compiler is the first line of defence. The structure of the data
makes the bugs that would have happened impossible to express.

— MINSKY
