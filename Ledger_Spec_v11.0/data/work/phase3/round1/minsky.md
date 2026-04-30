# Phase 3 Round 1 — MINSKY adversarial review of `proposal_v1.md`

**Reviewer.** Independent MINSKY (type-driven design); fresh context. Has not read `phase2/minsky.md`. Treats it as input via the proposal's compressions.
**Target.** `phase2/proposal_v1.md`.
**Discipline.** Make illegal states unrepresentable. Closed sums, refined newtypes, parsing at the boundary, total functions, exhaustive matches. Validation that does not produce a typed witness is not validation.

The proposal claims (P7, P9, P10) to make illegal states unrepresentable, to close enums everywhere a free string is tempting, and to reach polymorphism only through sum types. These are the clauses the proposal will be held to. Where the proposal does not honour them, this review issues a finding.

---

## Findings index

| # | Severity | Title |
|---|----------|-------|
| F1 | **BLOCKING** | `quality ∈ {FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED}` is a flat enum that should be a sum carrying a typed witness per case |
| F2 | **BLOCKING** | `gating_outcome` and `arbitrage_certification_status` survive as untyped tags on L13 instead of as `Result`-shaped witnesses |
| F3 | **BLOCKING** | `triggered-barrier flag` on L8 is a `bool` + comment; should be `BarrierState = NotMonitored \| Armed \| Triggered { evidence: AttestationId }` |
| F4 | **BLOCKING** | `is_fungibility_preserving: TermsVersion -> bool` is a partial predicate carrier; the proposal needs a refinement type witnessing fungibility, not a `bool` returned by a function |
| F5 | **BLOCKING** | L14 `Transaction ≈ NonEmpty<Move>` "with conservation refinement" — the conservation property is asserted but not encoded; it should be a smart-constructor refinement that produces a typed `BalancedTransaction` |
| F6 | **BLOCKING** | `discharge_predicate` on L16 is described in prose; if it is data, its representation is unspecified; if it is code, L21 version pinning is not enough — it must be a closed sum of named predicate kinds |
| F7 | **UNMITIGATED MAJOR** | Free-string surface remains at `attestor`, `vendor`, `source`, `topic`, `business_event_id`, `external_message_id`, `model_id` |
| F8 | **UNMITIGATED MAJOR** | "Closed enum `LifecycleIntent`" and "Sum type `LifecycleEvent = … \| …`" both end in ellipses — open or closed is not visible |
| F9 | **UNMITIGATED MAJOR** | "Refined newtype with private constructor" pattern is mentioned but the parser totality contract is absent — what is the documented input domain, and does parsing terminate on every element of it? |
| F10 | **UNMITIGATED MAJOR** | L19 Snapshot is "content-addressed" but the canonical-serialise function is not specified; without it, `snap_id` is not a function of the data |
| F11 | **UNMITIGATED MAJOR** | The `Move` sum is described as "single-coordinate constructor" but the six-coordinate vector `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` does not have its closure law encoded as a refinement |
| F12 | **UNMITIGATED MAJOR** | V12 ("no free-text `metadata`/`attributes`/`extensions`") is asserted at the principle level but not verified against any leaf; CDM payloads inside L14 `BusinessEvent` carry exactly the kind of open extension surface V12 forbids |
| F13 | **UNMITIGATED MAJOR** | Witness types (`arbitrage_certificate`, `snapshot_certificate`) are named but their construction sites and elimination sites are not enumerated; a witness type unused is decoration |
| F14 | MINOR | Phantom-typed writer caps on L8/L9 are mentioned but the phantom alphabet (the set of writer tags) is not closed in the proposal |
| F15 | MINOR | "Refined `Tolerance`" — refined how? The refinement predicate is the entire content |
| F16 | MINOR | Per-leaf invariant counts (e.g. "3T + 2W + 2C = 7") are summarised without indicating which are type-level vs runtime; the proposal explicitly says "type-level: registration totality, version monotonicity" only for L1, but every leaf should decompose this way |
| F17 | MINOR | "Errors are values" (P5) is asserted but the `Error` algebra is not enumerated; without a closed sum of error variants, "errors are values" is just "we return strings sometimes" |
| F18 | MINOR | L10 `RawQuote` parsed type is sketched but the eight-or-more sub-kinds (bid/ask/last/settle/swap-rate/CDS-spread/ATM-vol/risk-reversal/butterfly/FX/dividend forecast/borrow-fee/repo-rate) are not surfaced as a closed sum |
| F19 | MINOR | "Idempotency token with namespace prefix" — namespace prefix should itself be a closed sum, not a string convention |

---

## Detailed findings

### F1 — BLOCKING — Valuation `quality` is a flat enum, not a sum

§3.5 L15:

> `quality ∈ {FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED}`

These five tags are not equivalent in shape. A `STALE` valuation must carry the `t_obs` of the inputs that went stale. A `FAILED` valuation must carry the failure mode (numerical, missing input, calibration not certified, model panic). An `APPROXIMATE` valuation must carry the approximation strategy and bound. An `INDICATIVE` valuation must carry the reason it is not firm. A flat string enum collapses all of this into a tag, then re-introduces the missing fields by convention elsewhere.

This is the canonical `bool + comment` pattern, scaled to five values. It violates P7 directly.

**Required form:**

```
ValuationQuality =
  | Firm
  | Indicative { reason: IndicativeReason }
  | Approximate { strategy: ApproxStrategy; bound: PriceBound }
  | Stale { stale_inputs: NonEmpty<InputRef>; first_stale_at: Timestamp }
  | Failed { mode: ValuationFailureMode }
```

Each constructor's payload is the data the consumer needs to react. A consumer pattern-matching on `ValuationQuality` cannot forget to handle the failure mode.

**Action.** L15 must specify `ValuationQuality` as a closed sum carrying the per-case payload. The proposal must list the constructors and their fields explicitly.

---

### F2 — BLOCKING — `gating_outcome` and `arbitrage_certification_status` are untyped on L13

§3.4 L13 lists three boundary fields:

> `input_snapshot_id` (FK to L19), `model_id`, `gating_outcome`, `arbitrage_certification_status`. Reaches consumers only when `certified = true`.

`gating_outcome` and `arbitrage_certification_status` are described in prose. The proposal claims "witness type `arbitrage_certificate`" exists, but the relationship between the prose status and the witness type is not stated.

The right shape is:

```
CalibrationOutcome =
  | Rejected { gate: WhichGate; reason: GateFailure }
  | Accepted { certificate: ArbitrageCertificate }
```

A consumer wanting to read `(x_{t|t}, P_{t|t})` is forced (by the type) to first destructure the outcome; the posterior is reachable only inside the `Accepted` branch, where the certificate is in scope and the no-arbitrage admissibility law (L12) has a witness.

The proposal as written keeps the Kalman posterior visible in both branches, then asks consumers to check `certified = true` by convention. This is exactly the validate-and-discard pattern that P5/P7 forbid.

**Action.** The L13 record must hide the posterior behind the `Accepted` constructor, not behind a sibling boolean.

---

### F3 — BLOCKING — `triggered-barrier flag` on L8 is a `bool` + comment

§3.2 L8 lists "triggered-barrier flag" among UnitStatus fields.

A barrier has at least three states: not monitored (this product has no barrier), armed (monitored, not triggered), triggered (with the attestation that triggered it). In some products there are multiple barriers (knock-in plus knock-out), and each can be in any of these states independently. A boolean field cannot represent any of this.

This is the precise shape the proposal's principle P10 ("polymorphism by sum type, not inheritance") and P7 are written to forbid. A `bool` for "triggered or not" survives only because UnitStatus is in a tabular framing inherited from the database. Once UnitStatus is a parsed type, the right shape is:

```
BarrierState =
  | NoBarrier
  | Armed { kind: BarrierKind; level: Price }
  | Triggered { kind: BarrierKind; evidence: LifecycleAttestationId; t_obs: Timestamp }
```

with a unit's `BarrierStatus = Map<BarrierId, BarrierState>` if multi-barrier.

**Action.** L8's barrier representation must be specified as a closed sum, not a flag.

---

### F4 — BLOCKING — `is_fungibility_preserving: TermsVersion -> bool`

§3.1 L1:

> `TermsVersion = { fields: Fields; is_fungibility_preserving: TermsVersion -> bool }`

A predicate-as-field is a smell. Either:
- fungibility is decided **at construction time**, in which case the type should witness it (`TermsVersion` is a sum `FungibilityPreserving | FungibilityBreaking`, or the next version is constructed by a smart constructor that returns a `TermsAmendment` carrying a witness), or
- fungibility is recomputed by callers, in which case it is a free function on `Fields`, not a field.

As written, the predicate's totality and determinism are unconstrained. A future version can supply any predicate; the type system cannot tell whether the predicate agrees with the version-monotonicity invariant.

**Action.** Replace the `bool`-valued field with one of: a sum-typed `TermsVersion`, a refinement-typed `FungibilityPreservingAmendment`, or an external pure function with a stated specification.

---

### F5 — BLOCKING — `Transaction ≈ NonEmpty<Move>` "with conservation refinement"

§3.5 L14:

> `Transaction ≈ NonEmpty<Move>` with conservation refinement

The "≈" is doing a great deal of work. Either:
- conservation is enforced by the constructor (`Transaction.of_moves : NonEmpty<Move> -> Result<BalancedTransaction, ConservationError>`), in which case `Transaction` and `BalancedTransaction` are different types, and only the latter can enter the move stream, or
- conservation is checked at validation, then forgotten, and the type system carries no proof.

The proposal needs the first. The whole point of L14 being canonical is that everything downstream relies on it being conservation-respecting. If conservation is a runtime check that produces no typed artefact, every downstream consumer must either repeat the check or trust by convention.

This is also where CORRECTNESS Law L5 (per-event-class conservation) crosses the type/runtime boundary. The proposal classifies L5 as "Witnessed (per-handler unit test)" — but the witness is the *test*, not the *type*. Type-level witnessing of conservation per Move's event-class would lift L5 into U1-territory.

**Action.** Specify `BalancedTransaction` as the only inhabitant that can be appended to the MoveStream, and make its constructor the unique site where conservation is checked.

---

### F6 — BLOCKING — L16 `discharge_predicate` representation unspecified

§3.5 L16 says ObligationStore carries:

> `discharge_predicate`, `compensation_handler`

If `discharge_predicate` is data, its grammar is unspecified, which means the data layer carries arbitrary opaque blobs that the runtime evaluates. That is a `string` survival in disguise.

If `discharge_predicate` is code (a function reference), L21 version-pinning is necessary but not sufficient: the predicate's input type must be specified, its totality must be claimed, and its identity must be a closed sum of named predicate kinds.

**Action.** Specify `DischargePredicateKind` as a closed sum (`SettlementMatched | OracleAttestationReceived | CounterPartyAcknowledged | CompensationApplied | …`) with each constructor carrying its parameters. Same for `compensation_handler`.

---

### F7 — UNMITIGATED MAJOR — Free strings at the boundary

The proposal lists, across leaves, the following fields without specifying their type:

| Field | Leaf | Risk |
|---|---|---|
| `attestor` | L1, L11 | Should be `AttestorId` — a closed registry of attestor identities pinned by L21 |
| `vendor` | L2, L10 | Should be `VendorId` — closed registry |
| `source` | L10 | Same as `vendor` or a refinement of it |
| `topic` | L10 implicit | High-frequency observation topic — should be a closed sum of observable kinds |
| `business_event_id` | L11 | At minimum a refined newtype; at best a hash of the canonical content of the event |
| `external_message_id` | L12 | Refined newtype with origin tag |
| `model_id` | L13, L15 | Closed registry — there is a finite, version-pinned list of pricing models |

V9 (closed enumerations everywhere a free string is tempting) is exactly the principle violated here. The proposal asserts the principle and then leaves the strings.

**Action.** Per leaf, name the closed registry and its version-pin owner. If the registry truly is open (a vendor universe that grows), specify the *namespace* as closed and leave only the leaf-id as opaque.

---

### F8 — UNMITIGATED MAJOR — Ellipses in sum-type listings

§3.1 L1:

> Closed enum `LifecycleIntent`.

Then in §3.4 L11:

> `LifecycleEvent = CorporateAction | Barrier | Fixing | Exercise | Default | Locate | RegulatoryThreshold | ForceMajeure | …`

A closed sum cannot end in `…`. Either the eight constructors are exhaustive (and the ellipsis is a documentation bug), or there is a ninth that the proposal is hiding. The `LifecycleIntent` constructors are not listed at all.

**Action.** Each closed sum named in the proposal must list every constructor, with no trailing ellipsis. If the set is not yet closed, mark the type as `OpenEnum` with a documented reason and a roadmap to closure.

---

### F9 — UNMITIGATED MAJOR — Parser totality not specified

The proposal repeatedly asserts "parses from vendor-specific schema in the parser ring" (L2), "parsed from canonical-serialise output" (L19), "parsed from ISO 20022 envelope" (L12).

Each parser must answer two questions:
1. What is the documented input domain? (Which subset of byte-strings is the parser claimed to accept?)
2. Is the parser total over that domain? (For every input in the domain, does it produce either `Ok parsed` or `Err known_error`, with no panics, no infinite loops, no unhandled cases?)

Neither question is answered for any of the parsers. Without these, "parse, don't validate" reduces to "wrap a validator in a constructor", which is the validation pattern P5/P7 forbid.

**Action.** Per parser, specify the input domain (e.g. "ISO 20022 `sese.025.001.11` messages with valid XSD") and assert totality with a `Result<Parsed, ParseError>` return where `ParseError` is a closed sum.

---

### F10 — UNMITIGATED MAJOR — Canonical-serialise unspecified

§3.6 L19:

> `snapshot_id = hash(canonical_serialise(payload_set))`

The canonical-serialise function is the entire content-addressing claim. If it is unspecified:
- two implementations producing different byte-streams produce different snapshot ids on the same payload set
- replay determinism (CORRECTNESS L8) is unreachable

The proposal lists "C-A9 Workflow-history determinism" as TEMPORAL-owned, but content-addressing determinism is a separate assumption that needs an owner.

**Action.** Specify the canonical serialiser (e.g. CBOR with deterministic encoding per RFC 8949 §4.2, or a stated bespoke equivalent) and add a conditional assumption `C-A11 Canonical-serialiser stability`.

---

### F11 — UNMITIGATED MAJOR — Six-coordinate vector closure law not encoded

§3.3 L9:

> `PositionVector` with newtype-tagged six coordinates; sum-type `Move` with single-coordinate constructor.

The six-coordinate vector `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` has structural relations: `onloan ≤ own + borrowed_inventory_under_rehypothecation`; `coll_rehyp ≤ coll_recv` (you cannot rehypothecate more collateral than you received); `borr ≥ 0`; etc. These are PositionState invariants per CORRECTNESS Law L7 (per-CCP conservation scope).

A "newtype-tagged six coordinates" with a "single-coordinate `Move`" constructor encodes the *update* shape but not the *state* shape. Nothing prevents a `PositionVector` from arising in which `coll_rehyp > coll_recv`.

The right form is a smart-constructor `PositionVector.apply : PositionVector -> Move -> Result<PositionVector, ConsistencyError>` that fails when an update would violate the invariants, plus a refinement type witnessing the invariants.

**Action.** State the invariants of `PositionVector` and encode them as either refinement types (each coordinate carries the bound that depends on the others) or as a private constructor that runs the invariant check on every update.

---

### F12 — UNMITIGATED MAJOR — V12 not verified against L14 CDM payload

V12 forbids free-text `metadata`/`attributes`/`extensions`. CDM `BusinessEvent` (the L14 payload) has its own extension surface — `meta` blocks in CDM, custom fields in some FpML synonym sources, vendor-specific `extensions` arrays. The proposal does not specify how V12 is enforced against the CDM payload.

The two options are:
1. Project CDM payloads through a closed allowlist before they enter L14, dropping any extension fields not in the allowlist. The allowlist is L21-pinned per CDM version.
2. Accept extensions but wrap them in a closed sum `BusinessEventExtension = …` whose constructors are enumerated.

The proposal does neither.

**Action.** Specify the V12 enforcement boundary against L14 CDM payloads and against L17 envelope metadata. Until this is specified, V12 is principle without practice.

---

### F13 — UNMITIGATED MAJOR — Witness types named but not threaded

`arbitrage_certificate` and `snapshot_certificate` are named in the proposal. A witness type earns its keep by:
- being constructible only at one named site (the certifier)
- being required as a parameter at every consumer site (no consumer can read the certified object without the witness)

The proposal does not enumerate the construction site (which workflow signs the certificate? what is the closed set of certificate-issuing authorities?) or the consumer obligations (which functions take an `arbitrage_certificate` parameter?). Without both, the witness is decoration: a field on the record that the type system does not require anyone to inspect.

**Action.** Per witness type, specify (constructor site, consumers, what the witness existentially asserts). If a witness has no consumer obligations, delete it.

---

### F14–F19 — MINOR

These are below the BLOCKING/MAJOR bar but should be tracked.

- **F14.** Phantom writer-cap alphabet not closed: per L8/L9, the proposal needs to enumerate `WriterTag = LifecycleHandler | SettlementHandler | CalibrationHandler | …` exhaustively.
- **F15.** "Refined `Tolerance`" — specify the refinement (e.g. `Tolerance = { value: PositiveFloat; unit: ToleranceUnit; scope: ToleranceScope }`).
- **F16.** Per-leaf invariant T+W+C breakdown should distinguish type-level (compiler-enforced) from runtime (predicate-checked) for every leaf, not just L1.
- **F17.** P5 ("errors are values") needs an enumerated `Error` algebra. A closed sum of error variants per parser/operation is the typical form.
- **F18.** L10 `RawQuote` should be a closed sum over the dozen-plus observable kinds, with per-constructor required fields.
- **F19.** Idempotency-token namespace prefix should be a closed sum `TokenNamespace = …`, not a string convention.

---

## The Minsky Test, applied

| # | Test question | Verdict |
|---|---|---|
| 1 | Can illegal states be constructed? | **Yes** — see F1, F3, F5, F11. The proposal validates rather than parses for several core types. |
| 2 | Is every case handled? | **Unclear** — F8 leaves sums open with ellipses. |
| 3 | Is failure explicit? | **Partially** — F1 ValuationQuality and F2 CalibrationOutcome collapse failure modes into tags rather than typed payloads; F17 lacks an enumerated error algebra. |
| 4 | Would a reviewer catch a bug by reading? | **Often no** — F4 (predicate-as-field) and F6 (unspecified discharge_predicate grammar) require running the system to know what shape arrives. |
| 5 | Are invariants encoded or documented? | **Mostly documented** — F11 PositionVector invariants are stated in prose, not in the type. F5 conservation is asserted, not constructed. |
| 6 | Is this total? | **Unknown** — F9 the parser totality contract is missing for every parser the proposal names. |

The proposal asserts the right principles. The realisation does not yet meet them.

---

## Grade

**C+ (provisional). Conditionally rejectable; correctible without architectural rework.**

The structural choices (six classes, MoveStream as canonical, bitemporal mandatory, CDM as vocabulary, NAZAROV's 24-leaf spine) are sound. The type-driven design *intent* is present in the principles. But:

- Six BLOCKING findings (F1–F6) point to specific places where the proposal accepts a `bool`-or-string-or-flat-enum surface that its own P7/P9/P10 forbid.
- Six UNMITIGATED MAJOR findings (F7–F12) point to surfaces where the boundary contract is asserted but not constructed (free strings, open ellipses, parser totality, canonical-serialise, vector closure, V12 enforcement).
- One UNMITIGATED MAJOR finding (F13) points to witness types that are named but not threaded — a common failure mode where the type-system claim outruns the actual encoding.

The path to A is mechanical: for each F1–F13, write down the closed sum / refined newtype / smart-constructor / typed witness in concrete form, and verify by inspection that the consumer obligations follow. None of these require redesign; they require finishing the type-driven design that the proposal has begun.

**Specifically blocking re-issue:** F1, F2, F3, F4, F5, F6 must be addressed in `proposal_v2.md` before this reviewer can lift the BLOCKING.
