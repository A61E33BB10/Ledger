# Phase 2 — Data Team Synthesis: NAZAROV section

**Author role.** NAZAROV — data-layer architect. Owns the boundary, the
attestation discipline, and the dispute-ready posture for the Ledger v11.0 data
specification.

**Purpose.** This section of the Phase-2 synthesis proposal contributes:
(1) a master taxonomy that deduplicates Phase 1; (2) the NAZAROV minimum
data-quality bar that every workflow must satisfy; (3) per-leaf workflow
specifications that satisfy the bar; (4) the realism budget separating
unconditional from conditional guarantees.

**Out of scope (other team members).** CDM cross-walks (MATTHIAS), Temporal
workflow shapes (TEMPORAL), type design (MINSKY), invariants and proofs
(FORMALIS), test/property generators (TESTCOMMITTEE / CORRECTNESS), regulatory
direction-of-travel (ISDA), category-theoretic structure (GROTHENDIECK), the
SBL six-coordinate semantics (SBL specialist), per-token-detail loaders
(KARPATHY), beauty/delete-test (GEOHOT). Where my taxonomy interlocks with
these owners, I cite the interface, not the implementation.

---

## §1 Master taxonomy

### §1.1 Convergence found in Phase 1

Reading 19 Phase-1 enumerations end-to-end, **strong convergence** appears on
the following structural points; I adopt them as the spine.

1. **The three StatesHome maps are non-negotiable** — `ProductTerms`,
   `UnitStatus`, `PositionState` — and every Phase-1 reviewer (Cartan,
   Correctness, Feynman, Finops, Formalis, Grothendieck, Halmos, ISDA,
   Jane Street, Karpathy, Lattner, Matthias, Minsky, Noether, SBL, Temporal,
   Testcommittee, Geohot, Nazarov) preserves them. Grothendieck's three-sheaf
   structure parallels them exactly.
2. **The MoveStream is the canonical record.** Every reviewer who enumerated
   it (most of them) called it source-of-truth; Geohot named omitting it
   "the most serious error in the proposed taxonomy"; Lattner, Cartan,
   Halmos, Jane Street, Testcommittee make it foundational. The three
   StatesHome maps are projections of this stream.
3. **Market data must be split into raw and calibrated.** Eight Phase-1
   reviewers (Correctness, Feynman, Geohot, Halmos, ISDA, Jane Street,
   Lattner, Matthias, Minsky, Noether, Temporal, Testcommittee) split this
   explicitly; the rest treat it as one category but acknowledge the Kalman
   boundary is load-bearing. **Split is mandatory.**
4. **The "Listed-instrument detail" floor category is rejected as a top-level
   peer.** Eleven reviewers explicitly fold it into ProductTerms or
   Reference (Geohot, Cartan, Correctness, Feynman, Formalis, Grothendieck,
   Halmos partial, ISDA, Jane Street, Karpathy, Lattner, Matthias, Minsky,
   SBL, Testcommittee). Listed-vs-OTC is a discriminator on a unit's
   ProductTerms variant, not its own data class.
5. **The "Static" vs "Reference" floor split is renamed.** Almost every
   reviewer rejects "Static" as a meaningful axis; the better axis is
   *mutation discipline* (immutable-versioned vs slow-mutable vs append-log).
6. **The floor list silently omits at least four mandatory categories** —
   reviewer convergence on adding: **(a) Settlement Infrastructure** (SSI,
   custody mapping, CSD/CCP routing, BIC chains); **(b) Calibrated Latent
   State** (Kalman posterior, certified curves/surfaces, `(x_{t|t}, P_{t|t})`);
   **(c) Orchestration State** (Temporal workflow histories, FSM cursors,
   timer state); **(d) Party / Legal-Entity** identity (LEI, BIC, MIC,
   regulatory classifications); **(e) Policy / Configuration** (firm
   reference currency, decimal precision, tolerance policy, accounting
   classification map); **(f) Provenance / Audit** (hash chain, attestation
   envelopes, idempotency keys, CDM-version pins).
7. **Obligation Store is first-class.** Per v10.3 §14.7 and reviewer
   consensus (Cartan, Formalis, Geohot, Grothendieck, Halmos, ISDA, Lattner,
   Matthias, Minsky, Noether, Temporal, Testcommittee). Liveness without it
   is unprovable.

### §1.2 Deduplication rules I applied

Where Phase-1 reviewers used different names for the same thing, I picked the
canonical name by these rules, in priority order:

- **R1.** If v10.3 + StatesHome addendum + valuation v1.0 already binds a
  name (`ProductTerms`, `UnitStatus`, `PositionState`, `MoveStream`,
  `WalletRegistry`, `ValuationRecord`, `ObligationStore`, `Pricing DAG`),
  use it verbatim.
- **R2.** Where two Phase-1 reviewers name the same object differently
  (e.g., "Unit Reference Data" vs "Tier-1 Instrument Master" vs
  "InstrumentMaster"), pick the name that most clearly states the
  *mutation discipline* and *authoritative source*.
- **R3.** Where one reviewer splits and another conflates (e.g.,
  "Calibration State" alone vs "Raw Quote + Calibrated Surface"), prefer
  the **finer split** when the temporal/mutation semantics differ.
- **R4.** Where a Phase-1 reviewer adds a category that is genuinely a
  *projection* (`WalletBalance` is a fold of MoveStream), demote it to a
  query, not a leaf.
- **R5.** Where a Phase-1 reviewer adds a category that is a
  *processing artefact* (workflow-internal retry counters, FSM
  transitions), keep it under Orchestration State, distinct from the
  economic-data spine.

### §1.3 The taxonomy

I propose **6 structural classes** (the "spine") with **24 leaves**. Each
leaf has one canonical name, one precise definition, one owning workflow.

```
SPINE (6 structural classes, mutation-discipline-distinct)
├── C1. DEFINITIONS — append-only versioned, registration-total
│   ├── L1.  ProductTerms (= StatesHome map 1)
│   ├── L2.  Reference Data — Instrument Master       (Tier-1 input to ProductTerms)
│   ├── L3.  Reference Data — Party/Legal-Entity      (LEI, BIC, regulatory class)
│   ├── L4.  Reference Data — Calendar/Convention     (holidays, day-count, BD-conv)
│   ├── L5.  Reference Data — Settlement Infrastructure (SSI, CSD, custody, CCP routing)
│   ├── L6.  Legal Agreement                          (ISDA Master, CSA, GMSLA, mandate text)
│   └── L7.  Policy / Configuration                   (ref currency, decimals, tolerances, accounting class)
│
├── C2. SHARED STATUS — mutable per-unit, single-writer-per-field, shared across holders
│   └── L8.  UnitStatus (= StatesHome map 2)
│
├── C3. PER-POSITION STATE — monotone-carrier with Option-accessor, per (w, u)
│   └── L9.  PositionState (= StatesHome map 3, including SBL six-coordinate vector)
│
├── C4. OBSERVATIONS — append-only attestations, bitemporal mandatory
│   ├── L10. Raw Market Observation                   (quote, tick, settle print, fixing, FX rate)
│   ├── L11. Lifecycle/Oracle Attestation             (corporate action, barrier ruling, exercise notice, default declaration, locate confirmation)
│   ├── L12. External Confirmation/Reconciliation     (sese.025/camt.054/sese.023 settlement-status messages)
│   └── L13. Calibrated Market Object                 (Kalman posterior, certified curve/surface — output of L10 through filter)
│
├── C5. EFFECTS — append-only, hash-chained, immutable, the canonical record
│   ├── L14. MoveStream                               (the chronological log of all transactions and moves)
│   ├── L15. ValuationRecord                          (per (unit, t, model) — output of valuation FSM)
│   └── L16. ObligationStore                          (per v10.3 §14.7 — first-class liveness object)
│
└── C6. PROVENANCE & ORCHESTRATION — meta-data and replay-substrate
    ├── L17. Attestation Envelope                     (signature, key-id, timestamps, chain-of-custody)
    ├── L18. Identity & Metadata Keys                 (unit_id, tx_id, UTI, USI, obligation_id, snapshot_id)
    ├── L19. Snapshot                                 (content-addressed bundle of L10+L13 used for replay)
    ├── L20. Idempotency Token                        (CDM EndToEndId, ClOrdID, internal-mint keys)
    ├── L21. Version Pin                              (CDM version, smart-contract version, model version, schema version)
    ├── L22. Hash-Chain Anchor                        (Layer-1 log integrity, genesis hash, prev-hash links)
    ├── L23. Capability/Permission                    (C4 capability scopes from StatesHome — non-economic)
    └── L24. Orchestration State                      (Temporal histories, FSM cursors, timer state — replay-substrate, not economic)
```

**Class-to-floor mapping (for traceability):**

| Phase-1 floor                   | Spine class      | Notes                                                      |
| ------------------------------- | ---------------- | ---------------------------------------------------------- |
| Static                          | C1 (split L1–L7) | "Static" is renamed; finer split by mutation discipline    |
| Reference                       | C1 (L2–L7)       | Distinguished by authoritative source                      |
| Market                          | C4 (L10 + L13)   | Mandatory split: raw observation vs calibrated posterior   |
| Oracle                          | C4 (L11) + C6 (L17) | Lifecycle/non-price oracles + envelope discipline       |
| Smart-contract execution        | C5 (L14, L15)    | Execution outputs are MoveStream + ValuationRecord         |
| Listed-instrument detail        | (rejected)       | Folded into L1 ProductTerms as a `unit_type` variant       |

**Why six classes, not three.** Grothendieck argues for three sheaves
(definitions/observations/effects). I extend to six because:
- C2 and C3 are operationally distinct from C1 (different mutation discipline,
  different writer-canon C11, different totality story); collapsing them
  re-introduces the StatesHome 3-map confusion.
- C6 is not economic data but is required for replay determinism, dispute
  resolution, and the boundary contract; folding it into observations or
  effects loses the attestation invariant.

The six classes are mutually exclusive on **mutation discipline**:

| Class | Mutation discipline                                                   |
| ----- | --------------------------------------------------------------------- |
| C1    | Append-only versioned; registration-total                             |
| C2    | Mutable; single-writer-per-field; per-unit                            |
| C3    | Monotone-carrier; Option accessor; per-(wallet, unit)                 |
| C4    | Append-only attestations; bitemporal mandatory                        |
| C5    | Append-only hash-chained; immutable                                   |
| C6    | Append-only meta-data; bound to instances of C1–C5                    |

Every leaf has exactly one home; no leaf needs to live in two classes.

### §1.4 Leaf catalogue (one canonical name, one precise definition, one owning workflow)

Each leaf below has the form `Lk. Canonical name — owning workflow — definition`.
The "owning workflow" identifies who attests/writes; per-leaf workflow
specifications follow in §3.

**C1 Definitions (append-only versioned)**

- **L1. ProductTerms** — owner: `unit-registration` and `terms-amendment`
  workflows (TEMPORAL). The immutable, versioned-append-only specification
  of what a unit *is* (per StatesHome §2 + C6/C7/C8/C10).

- **L2. Reference Data — Instrument Master** — owner: `refdata-ingest`
  workflow. Externally-authored instrument descriptors (ISIN, contract spec,
  exchange listing, issuer LEI binding, bond terms, tokenized-asset
  metadata). Tier-1 of the v10.3 Unit Store. *Input* to L1 at registration;
  not a duplicate of L1.

- **L3. Reference Data — Party/Legal-Entity** — owner: `party-ingest`
  workflow. Authoritative party identification: LEI, BIC, MIC, jurisdiction,
  regulatory classifications (FC/NFC, EMIR class, MiFIR class, US Person,
  sanctions status). Sourced from GLEIF, SWIFT, ISO, and internal KYC.

- **L4. Reference Data — Calendar/Convention** — owner: `calendar-ingest`
  workflow. Holiday calendars per `BusinessCenterEnum`, day-count fractions,
  business-day adjustment rules, roll conventions, weekend rules. Sourced
  from exchanges, central banks, ISDA, vendors.

- **L5. Reference Data — Settlement Infrastructure** — owner:
  `ssi-ingest` workflow. SSIs, CSD participant IDs, custodian account
  hierarchies, BIC routing, CCP clearing-member bindings, cut-off times.
  *Lives outside the Ledger boundary* per v10.3 §9; the Ledger consumes
  but does not author.

- **L6. Legal Agreement** — owner: `legal-ingest` workflow. ISDA Master,
  CSA, GMSLA, MSLA, GMRA, OSLA, mandate documents — keyed by `agreement_id`
  and version. Hash-anchored to the signed document. Bound into L1
  ProductTerms when an OTC trade is registered (its `Collateral` field is
  part of `unit_id`).

- **L7. Policy / Configuration** — owner: `policy-governance` workflow.
  Firm reference currency, decimal precision policy, rounding mode,
  tolerance thresholds (PnL-explain, reconciliation, conservation alert),
  accounting classification map (FVTPL/FVOCI/AC), capability schema (C4),
  versioning policy (CDM/contract/calendar version pins).

**C2 Shared status (mutable, per-unit, shared)**

- **L8. UnitStatus** — owner: lifecycle handlers (one per field, by C11).
  Per StatesHome §2: lifecycle stage, last settlement price, last settlement
  date, current weights (QIS), nav index (QIS), triggered-barrier flag,
  superseded-by pointer, valuation FSM state `σ(u)`, staleness timer.

**C3 Per-position state (monotone-carrier, per-(w, u))**

- **L9. PositionState** — owner: the unique-writer handler per field
  (C11). Per StatesHome §2 + v10.3 §15 (SBL): `accumulated_cost`, `hwm`,
  `entry_nav`, `accrued_mgmt_fee`, `accrued_perf_fee`, `mandate_breach_flags`,
  `benchmark_nav_at_inception`, `ccp_binding`, plus the SBL six-coordinate
  vector `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)`.

**C4 Observations (append-only attestations, bitemporal mandatory)**

- **L10. Raw Market Observation** — owner: `market-data-ingest` activity.
  Single attestation `y_t` of an observable: bid/ask/last/settle/open/close/
  swap-rate/CDS-spread/ATM-vol/risk-reversal/butterfly/FX-rate/dividend
  forecast/borrow-fee/repo-rate. Carries `t_obs`, `t_known`, `source`,
  `signature`. Bitemporal mandatory.

- **L11. Lifecycle/Oracle Attestation** — owner: `oracle-ingest` activity
  (per oracle kind). Signed external assertion that triggers a deterministic
  contract action: corporate-action announcement, barrier-observation
  ruling, fixing publication (LIBOR/SOFR/EURIBOR/€STR/SONIA/TONA), exercise
  notice, default declaration, locate confirmation, regulatory-threshold
  determination, force-majeure declaration. *Distinct from L10* because
  the consumer is not the Pricing DAG but the lifecycle handler /
  obligation store. Argument for the split: L10 feeds the Kalman filter;
  L11 feeds smart contracts. Same envelope discipline, different downstream
  semantics.

- **L12. External Confirmation/Reconciliation** — owner: `confirmation-ingest`
  activity. Inbound ISO 20022 / SWIFT messages confirming or contradicting
  prior outbound action: `sese.025`/`sese.023` settlement confirmations,
  `camt.053`/`camt.054` cash account statements, custodian depot statements,
  CCP clearing confirmations, virtual-wallet contra-balance attestations.
  Distinct from L11 because L11 *triggers* contracts; L12 *confirms* prior
  effects.

- **L13. Calibrated Market Object** — owner: `calibration` workflow
  (Kalman pipeline per valuation v1.0 §4–§5). The certified Bayesian
  posterior `(x_{t|t}, P_{t|t})` for a target object (yield curve, vol
  surface, hazard curve, FX vol cube, correlation matrix). Carries
  `input_snapshot_id` (FK to L19), `model_id`, `gating_outcome`,
  `arbitrage_certification_status`. Reaches consumers only when
  `certified = true`.

**C5 Effects (append-only, hash-chained)**

- **L14. MoveStream** — owner: the executor (single-writer by construction
  per v10.3 §7.6, §13.5). Append-only sequence of `Transaction` records,
  each containing a list of `Move` records, hash-chained, dual-timestamped
  (economic time, knowledge time), CDM-payload-bearing. *The canonical
  record from which L8, L9, and all balances are projections.*

- **L15. ValuationRecord** — owner: `pricing` workflow (per valuation v1.0
  §6). Per (unit, t, model) tuple: dirty price, clean price, accrued,
  Greeks, `quality ∈ {FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED}`,
  `attestation_snap` (FK to L19), valuation FSM state.

- **L16. ObligationStore** — owner: lifecycle handlers (registration) +
  obligation-discharge workflow. Per v10.3 §14.7: pending discharge
  requirements with deadlines, discharge predicates, compensation actions.
  Carries `obligation_id`, `kind`, `created_by_tx_id`, `deadline`,
  `discharge_predicate`, `compensation_handler`, `status ∈ {PENDING,
  DISCHARGED, COMPENSATED}`.

**C6 Provenance & orchestration (meta-data and replay-substrate)**

- **L17. Attestation Envelope** — owner: ingestion gateway (per source).
  The signature/timestamp/chain-of-custody wrapper around any datum
  crossing the boundary. Required on L10, L11, L12 by NAZAROV bar.

- **L18. Identity & Metadata Keys** — owner: deterministic-derivation rules
  in code. Unit IDs, transaction IDs, UTIs, USIs, obligation IDs, snapshot
  IDs, attest IDs. Each key is a deterministic hash of its content; the
  derivation rule itself is version-pinned (L21).

- **L19. Snapshot** — owner: `snapshot-build` activity invoked by pricing
  workflow at each valuation epoch. Content-addressed bundle of (L10 ∪ L13)
  rows used for one reproducible computation cycle. Identified by
  `snapshot_id = hash(canonical_serialise(payload_set))`.

- **L20. Idempotency Token** — owner: minted by issuing workflow (internal)
  or carried in inbound messages (CDM `EndToEndId`, FpML `messageId`,
  FIX `ClOrdID`, ISO 20022 `EndToEndId`). Per v10.3 §13 idempotency chain.

- **L21. Version Pin** — owner: deployment pipeline + governance.
  `(component_name, git_sha, container_digest)` for executor / lifecycle
  workers / pricers; `cdm_version` for CDM enums and synonyms;
  `(contract_id, contract_version)` for smart contracts; `(model_id,
  model_version)` for Kalman/pricing models.

- **L22. Hash-Chain Anchor** — owner: executor (writes); auditor (verifies).
  Genesis hash, per-transaction `prev_hash` links, periodic checkpoints
  for tamper-evidence per Invariant P4 of v10.3.

- **L23. Capability/Permission** — owner: capability administration
  workflow. C4 capability scopes from StatesHome — which subjects (users,
  services) can read which `(w, u)` overlays, write which `PositionState`
  field, emit which event class.

- **L24. Orchestration State** — owner: Temporal worker. Workflow
  histories, activity invocation results, retry counters, durable timer
  state, FSM cursors, signal channels. *Replay-substrate only*; not
  economic data; bound here so that the boundary discipline applies to
  workflow-history payloads as much as to MoveStream entries.

**Total: 24 leaves, 6 classes, mutually exclusive, collectively exhaustive
against the union of all 19 Phase-1 enumerations.**

---

## §2 NAZAROV minimum data-quality bar

This is the **floor every workflow must meet**. It is stated as numbered
RFC-2119-style requirements. Violations are findings, not preferences.

### N1 — Provenance is mandatory and named

**N1.1.** Every datum entering the Ledger MUST carry a named provenance
record identifying (a) the originating authority, (b) the channel by which
it arrived, (c) the message identifier as assigned at the source, (d) the
ingestion gateway that received it, (e) the wall-clock time at which the
gateway received it.

**N1.2.** Provenance MUST be stored alongside the datum, not in a
separate "lookup table" subject to drift.

**N1.3.** A datum with unknown provenance is not data; the system MUST
refuse to admit it.

### N2 — Attestation is mandatory at the boundary

**N2.1.** Every leaf in classes C4 (Observations) and L11/L12 specifically
MUST carry a cryptographically verifiable attestation envelope (L17) at
the point of entry. The envelope MUST identify a key whose authority is
recorded in the trust registry (§4 below).

**N2.2.** Where a vendor cannot sign, signing MUST happen at the
ingestion gateway under a clearly identified gateway key, AND the resulting
trust assumption ("we trust gateway X to faithfully report what vendor Y
said over TLS") MUST be a named, owned trust assumption in the registry.
**Bare REST + JSON without a gateway signature is not data; it is a rumour.**

**N2.3.** Attestation key management MUST specify generation, storage
(HSM mandatory for boundary-crossing keys), rotation cadence, revocation
procedure, and recovery from compromise. Defer cryptographic primitive
selection to a cryptographer (per NAZAROV deferral discipline) but state
the required properties: signature unforgeability, replay resistance,
key-compromise recovery.

### N3 — Ingress validation is total over a documented input domain

**N3.1.** Every ingestion workflow MUST validate inbound payloads against
a schema pinned by L21 version pin. Validation failure is an explicit
event (a "failed-ingest" record), not a silent discard.

**N3.2.** Validation MUST cover (a) syntactic well-formedness, (b)
referential integrity (every foreign key resolves), (c) attestation
verification (N2), (d) bitemporal sanity (`t_known >= t_obs`,
`t_known <= now()`), (e) idempotency-key uniqueness within scope
(N4 below).

**N3.3.** A datum failing any of (a)–(e) MUST be quarantined with full
provenance and a typed reason; downstream consumers MUST NOT see it.

### N4 — Idempotency on replay is total

**N4.1.** Every datum entering the Ledger MUST carry an idempotency
token (L20) within a named scope. Re-presenting the same token within
the scope MUST produce the same outcome (memoised) and MUST NOT cause a
fresh side effect.

**N4.2.** The token's scope MUST be one of: `transaction`, `lifecycle_event`,
`oracle_attestation`, `ccp_message`, `regulatory_submission`,
`calibration_input`. Cross-scope collisions MUST be impossible by
construction (namespace-prefixed token format).

**N4.3.** Once a token has reached a terminal outcome
(`{applied, rejected, quarantined, superseded}`), the outcome MUST be
durably memoised; replays return the memoised outcome, not a fresh
execution.

### N5 — Dispute resolution path is specified and exercised

**N5.1.** For every leaf whose corruption can produce a counterparty
dispute (L1, L8, L10, L11, L12, L14, L15, L16), the data layer MUST
provide an "as-known-at-t" replay primitive that returns the bit-identical
content the workflow consumed at the original execution time.

**N5.2.** The replay primitive's output MUST be cryptographically
verifiable against the original attestation (L17) and the original
hash-chain anchor (L22). A dispute is resolved by either (a) producing
the bit-identical replay (we were right) or (b) acknowledging a divergence
and triggering the correction protocol.

**N5.3.** Corrections MUST be modelled as new events (a `CORRECTION`
transaction in L14, a vendor-restated attestation in L10/L11, a
re-calibration in L13). Mutating prior records is forbidden under N9.

### N6 — Point-in-time reconstruction is bitemporal

**N6.1.** The data layer MUST distinguish two query modes:
**(a)** "as known at time `t`" — the snapshot of admissible data whose
`t_known ≤ t`, ignoring later corrections;
**(b)** "with corrections through `t' ≥ t`" — the snapshot of admissible
data whose `t_obs ≤ t` *and* `t_known ≤ t'`, applying restatements.

**N6.2.** Both modes MUST be available for every leaf in C1, C4, C5.
The Ledger's time-travel theorem (v10.3 §1.2 Property 6) requires both;
a single-axis "as of t" without disambiguation is forbidden.

**N6.3.** Vendor restatements, calendar amendments, LEI re-issuances,
and corporate-action late-corrections all enter as new rows under N5.3
and become visible in mode (b) but not (a) for queries at `t` < their
`t_known`.

### N7 — Failure mode when absent or contradicted is named, not silent

**N7.1.** For every leaf, the specification MUST name the consequence of
absence (datum missing) and the consequence of contradiction (two sources
disagree beyond the disagreement threshold).

**N7.2.** **Silent fallbacks are forbidden.** When an aggregation rule
falls back from primary to secondary or beyond, the fallback transition
MUST be a recorded event (in L14 or in a dedicated `fallback-event`
log), with the actually-traversed chain captured in the consuming
workflow's snapshot (L19).

**N7.3.** Hard-stop behaviour (refuse to admit the datum, halt the
dependent workflow, flag for manual review) MUST be specified per leaf;
"degrade gracefully" is permitted only when the degraded behaviour is
itself attested and quality-flagged downstream (e.g., Valuation
FSM `STALE` state per valuation v1.0 §2).

### N8 — Multi-source aggregation rule is documented per leaf

**N8.1.** For every leaf in C4 whose corruption materially affects
valuations or settlement (L10, L11 for high-stakes oracles, L12 for
settlement-status), the workflow MUST specify (a) the aggregation function
(majority / weighted-median / min-spread / authority-priority), (b) the
disagreement threshold, (c) the quorum requirement, (d) the
"aggregation failed" event semantics.

**N8.2.** A single-source datum is permitted only when (a) the source is
the unique authority (e.g., the calculation agent for a barrier
observation, the issuer for a corporate action) **and** (b) that
authority is named, owner-assigned, and has a documented
violation-detection signal in the trust registry.

### N9 — Mutable history is forbidden

**N9.1.** No leaf in C1, C4, C5 MAY be mutated in place. Append-only is
the discipline.

**N9.2.** Restatements, corrections, and supersession MUST be modelled
as new rows referencing the prior row (e.g., `corrects: tx_id`,
`superseded_by: unit_id`, `restates: attest_id`).

**N9.3.** "Garbage collection" of close-out positions, retired LEIs,
delisted instruments, expired calendars is forbidden. Retention is the
discipline; archival is a query optimisation, not a data-model change.

### N10 — Determinism is the foundation of replay

**N10.1.** Every snapshot (L19) MUST be content-addressed
(`hash(canonical_serialise(payload_set))`). Two computations consuming
the same snapshot ID MUST produce the same output.

**N10.2.** The snapshot MUST include the fallback chain *as actually
traversed*, not the configured chain — otherwise replay reconstructs a
counterfactual.

**N10.3.** Vendor corrections create new snapshots; they do not mutate
existing snapshots.

**N10.4.** "As known at `t`" vs "with corrections through `t'`" is a
first-class query the data layer MUST answer; a single
`as_of(t)` accessor that conflates the two is a violation.

### N11 — The mapping layer is part of the oracle

**N11.1.** Mapping from external schemas (FpML, FIX, ISO 20022, CDM
synonyms, vendor-specific) into the Ledger's internal representation
MUST be deterministic, total over a documented input domain, and
version-pinned (L21).

**N11.2.** Mapping failures MUST be explicit failure events, not silent
defaults.

**N11.3.** Mapping versions MUST be recorded with each ingested message;
replays MUST be bit-identical against the recorded version, even after
upstream schema upgrades.

### N12 — Trust assumptions are first-class

**N12.1.** Anything the system trusts that is not cryptographically
attested is a trust assumption. Every trust assumption MUST appear in
the trust registry (§4) with: name, scope, owner, violation consequence,
detection signal.

**N12.2.** **Untyped trust is forbidden.** "Trust the vendor feed" is
not a trust assumption; "trust the BNY Mellon Triparty Agent's
`coll_recv` allocation reports under the executed Triparty Agreement
v2018-03, scope = (lender_lei × borrower_lei × eligibility_set_ref);
violation consequence: rehypothecation conservation P19 silently breaks;
detection signal: daily reconciliation against agent allocation report"
is a trust assumption.

**N12.3.** Trust assumptions MUST be reviewed periodically (cadence
specified per assumption) and MUST be removable on violation (kill-switch
specified).

---

**Count of NAZAROV bar items: 12 named requirements (N1–N12), 36
sub-requirements (N1.1–N12.3).** Every workflow in §3 is judged against
this bar.

---

## §3 Per-leaf workflow specifications

For each of the 24 leaves I specify the workflow that satisfies the
NAZAROV bar. I am implementation-agnostic: any compliant implementation
must do these things; the *how* is for TEMPORAL and engineering teams to
realise.

For each leaf:
- **Attestation:** who attests; how the attestation is verified at ingress.
- **Ingress:** how the datum enters; which N3 validations apply.
- **Late-arrival/dispute:** how late events / restatements / disputes are
  handled.
- **Point-in-time reconstruction:** the bitemporal replay primitive.

I cluster leaves by class to avoid repetition; per-leaf differences are
called out where they matter.

### §3.1 Class C1 — Definitions (L1–L7)

**Common pattern.** Append-only versioned. Each version is signed at the
authoring authority; ingress verifies the signature against L17 and the
authority's key in L23. Validation per N3 covers schema (L21 pinned),
referential integrity, idempotency. Late corrections from the authority
arrive as new versions with their own `t_known`; "as known at `t`" returns
the version chain as it stood at `t_known ≤ t`.

**Per-leaf attestation:**

- **L1 ProductTerms.** Attestor: the registration transaction's author
  (the executor, signing on behalf of the authoring channel — listed:
  reference-data feed; OTC: counterparty-execution + CDM `BusinessEvent`;
  mandate/QIS: manager LEI + signed mandate document hash). Verification:
  the registration handler validates the inbound payload against the
  product-type schema, computes `unit_id` deterministically, refuses
  re-registration (StatesHome C10).

- **L2 Instrument Master.** Attestor: vendor (Bloomberg / Refinitiv / SIX /
  ICE Data) or exchange/CSD direct feed. Verification: vendor signature
  on each batch + multi-vendor reconciliation gate per N8 (two-source
  agreement before admitting to L1; disagreement quarantines pending
  reconciliation).

- **L3 Party/LEI.** Attestor: GLEIF (LEI), SWIFT (BIC), ISO 10383 (MIC),
  internal KYC system (regulatory classification). Verification: GLEIF
  CDF signature; LEI status check; lapsed-LEI flagging.

- **L4 Calendar/Convention.** Attestor: exchange / central bank /
  ISDA / vendor. Verification: vendor signature; multi-vendor
  reconciliation for forward-looking holiday tables; published-version
  check.

- **L5 Settlement Infrastructure.** Attestor: SSI utilities (DTCC ALERT,
  Omgeo CTM, SWIFT KYC Registry), counterparty signed SSI letter.
  Verification: per v10.3 §9.1, this leaf lives **outside the Ledger
  boundary** in the settlement layer; Ledger consumes it at projection
  time (settlement-instruction enrichment) and records the SSI version
  used at the moment of projection. The Ledger does not own freshness;
  the settlement layer does.

- **L6 Legal Agreement.** Attestor: counterparty execution (PDF + ISDA
  Create + Notices Hub). Verification: hash anchor (`document_hash`)
  matches the signed PDF; bilateral counterparty signature confirmation.

- **L7 Policy/Configuration.** Attestor: governance committee signature
  (firm-internal). Verification: change-control ticket reference; multi-eyes
  approval; documented effective date.

**Common ingress:** Validate against schema (L21); check N2 attestation;
check N4 idempotency on `(unit_id, version_seq)` (L1) or
`(authority, key, version)` (L2–L7); on validation failure, quarantine
with full provenance and typed reason.

**Late-arrival/dispute:** Vendor restatements (corrected ISIN issuance
date, lapsed LEI, late-published holiday) arrive as new versions with
later `t_known`. Per N9, never overwrite. Per N5, the dispute resolution
path produces a bit-identical replay against the version known at the
challenged time.

**Point-in-time reconstruction:** `as_of(leaf, key, t_known)` returns
the latest version with `version.t_known ≤ t_known`. For L4 calendars,
both `t_known` (when we knew the holiday) and the `effective_date` of
the holiday matter; bitemporal indices are mandatory.

### §3.2 Class C2 — Shared Status (L8 UnitStatus)

**Attestation.** UnitStatus is mutated only by the unique writer per C11
(StatesHome). Each mutation is part of a `StateDelta` written by the
executor as an entry in L14. The entry is signed by the executor's key
and hash-chained (L22) to the prior entry.

**Ingress.** UnitStatus is *not ingested from outside* — it is a
projection of L14 (the move stream). The "ingress" is the executor's
atomic commit of a `StateDelta`. Validation per N3 happens in the
handler before the executor commits.

**Late-arrival/dispute.** A late lifecycle event (e.g., a corporate
action announced after the fact) arrives via L11 (oracle attestation)
and triggers a new `StateDelta` written to L14. UnitStatus is updated
by replaying the handler against the new attestation. Per N9, the prior
UnitStatus value is preserved in L14 history.

**Point-in-time reconstruction.** UnitStatus at time `t` is the fold of
all `StateDelta`s targeting `unit_id` in L14 with `t_committed ≤ t`
(mode (a)) or with `t_logical ≤ t ∧ t_committed ≤ t'` (mode (b)).

### §3.3 Class C3 — Per-position state (L9 PositionState)

Identical pattern to L8: mutated only via `StateDelta` in L14, by the
unique-writer handler per C11 (StatesHome). The SBL six-coordinate
extension follows the Single-Coordinate Move Principle (v10.3 §15.2):
each move touches exactly one coordinate; conservation per coordinate
holds at the entity level.

**Attestation, ingress, late-arrival, replay:** as L8.

**Specific to L9:** the monotone-carrier discipline (C1 of StatesHome)
forbids garbage-collecting `Some(zero)` rows; per N9, retention is the
discipline. Wash-sale lookback, record-date entitlement, and tax-lot
lineage all depend on this.

### §3.4 Class C4 — Observations (L10–L13)

**L10 Raw Market Observation.**

- **Attestor:** market-data vendor (Bloomberg, Refinitiv, exchange
  direct), inter-dealer broker, internal trading desk. Where the vendor
  signs at source, the source signature is canonical; where the vendor
  does not sign, the ingestion gateway signs under a named gateway key
  (N2.2), and the gateway-trust assumption is registered.
- **Ingress:** `market-data-ingest` activity verifies the signature,
  validates against the typed-observation schema, applies bitemporal
  sanity checks, mints an `attest_id = hash(topic, value, t_obs, source)`,
  appends to the bitemporal index keyed on `(topic, t_known)`.
- **Late-arrival/dispute:** Vendor corrections arrive as new rows with
  later `t_known` and same or different `t_obs`. Per N9, never overwrite.
  Per v10.3 §7.7, corrections trigger downstream re-calibration and
  PnL-explain re-evaluation.
- **Point-in-time:** "Snapshot at t" is `latest-by-t_known where
  t_known ≤ t`, partitioned by `topic`. Snapshot ID (L19) identifies a
  consistent cut.

**L11 Lifecycle/Oracle Attestation.**

- **Attestor:** the named authority for the oracle kind — calculation
  agent (CDM `partyRole = CalculationAgent`) for barrier observations
  and exercise notices; index administrator for fixings and benchmark
  publications; CCP for default declarations and novation confirmations;
  CSD for settlement-finality messages; issuer agent for corporate
  actions; locate provider for SBL locates; regulator for sanctions
  determinations.
- **Ingress:** per oracle kind, an `oracle-ingest` activity verifies the
  authority's signature against L23 (capability registry); validates
  payload against the CDM-typed schema (L21); applies N3 bitemporal and
  idempotency checks; refuses unsigned/unverifiable claims (per
  NAZAROV "no bare API calls").
- **Late-arrival/dispute:** A re-fixed LIBOR after erroneous publication
  arrives as a new oracle event; the contract's idempotency key (N4)
  ensures the handler fires exactly once on the authoritative claim
  (typically the latest restated version); prior firings are recorded
  but their effects are reversed via a `CORRECTION` transaction in L14
  if necessary.
- **Point-in-time:** Same as L10. Critically, the dispute resolution
  path (N5) for a barrier-observation challenge replays the calculation
  agent's signed attestation against L22 hash-chain to demonstrate that
  the contract acted on the authoritative version known at the time.

**L12 External Confirmation/Reconciliation.**

- **Attestor:** the inbound external system (custodian for camt.053,
  CSD for sese.025/sese.023, CCP for clearing confirmation, counterparty
  for affirmation messages). Each carries a wire signature.
- **Ingress:** parse, verify, mint `(transaction_id_ref, external_message_id)`
  identity; validate that `transaction_id_ref` resolves to a prior L14
  entry; validate idempotency per N4.
- **Late-arrival/dispute:** A `FAILED` confirmation followed by a
  `SETTLED` confirmation after buy-in or extension; both retained per N9.
- **Point-in-time:** Per-`transaction_id` confirmation history, ordered
  by `t_known`.

**L13 Calibrated Market Object.**

- **Attestor:** the calibration workflow itself (Kalman filter activity).
  The certification chain is: input snapshot (L19, content-addressed) →
  Kalman update with version-pinned `(model_id, model_version)` (L21) →
  no-arbitrage projection → innovation gate → certification status. The
  workflow's signed identity (L23 capability for the calibration role)
  is the attestor.
- **Ingress:** synchronous output of the calibration workflow; written
  to L13 only when `certified = true`. Failed certifications fall back
  to the prior certified state with `quality = STALE` flag and emit a
  failure event per N7.
- **Late-arrival/dispute:** A vendor restatement of input quotes (L10)
  triggers a re-calibration; the new calibration carries a new
  `calibration_id` and `t_known` per N9. The prior calibration is
  retained.
- **Point-in-time:** Bitemporal — `as_of(target_object, t_known)`
  returns the latest certified calibration whose `published_at ≤ t_known`.
  Mode (b) replay against current data uses the latest restated version.

### §3.5 Class C5 — Effects (L14, L15, L16)

**L14 MoveStream.**

- **Attestor:** the executor (single-writer per v10.3 §7.6). Each
  transaction is signed by the executor's key, hash-chained to
  `prev_hash`.
- **Ingress:** the executor commits a transaction iff (a) all reads
  resolved (L1, L8, L9 referenced), (b) all input attestations verified
  (L10, L11 if consumed), (c) the handler returned a complete `StateDelta`
  satisfying C2/C3 (handler-class structural conservation), (d) the
  `idempotency_key` (N4) is fresh, (e) the resulting transaction's
  `prev_hash` matches the current head.
- **Late-arrival/dispute:** Late events arrive with their own
  `t_logical < t_committed`; both timestamps are stored. Corrections
  are new `CORRECTION` transactions referencing the corrected
  `tx_id` via `corrects_tx_id` (per v10.3 §10.4 — "Corrections as
  events").
- **Point-in-time:** `clone_at(t_known)` selects all transactions with
  `t_committed ≤ t_known` (mode a) or `t_logical ≤ t ∧ t_committed ≤ t'`
  (mode b). The hash chain enables tamper-evidence per Invariant P4.

**L15 ValuationRecord.**

- **Attestor:** the pricing workflow. The record carries
  `attestation_snap` (FK to L19) and `model_id` + `model_version` (L21);
  re-running the same workflow on the same snapshot must produce a
  bit-identical record (deterministic-replay invariant).
- **Ingress:** appended at each FSM transition into a Priced/Explained
  state per valuation v1.0 §2; never mutated.
- **Late-arrival/dispute:** Re-pricing on a corrected snapshot produces
  a new ValuationRecord with new `(t, model_id)`; prior records retained.
- **Point-in-time:** Same bitemporal scheme as L14.

**L16 ObligationStore.**

- **Attestor:** lifecycle handlers (registration); discharge or
  compensation activities (status updates).
- **Ingress:** every obligation registration, discharge, and compensation
  is itself a transaction in L14 (per v10.3 §14.7); ObligationStore is a
  projection. Validates per N3 + N4.
- **Late-arrival/dispute:** A late discharge proof arrives as a new
  L14 transaction; ObligationStore is updated by replaying.
- **Point-in-time:** Per `obligation_id`, the timeline of status
  transitions, indexed bitemporally.

### §3.6 Class C6 — Provenance & orchestration (L17–L24)

These leaves are meta-data and do not have independent ingress workflows;
they are produced and consumed by the workflows that own L1–L16.

- **L17 Attestation Envelope** is the discipline applied at every
  ingress in C4 and at the boundary of L1, L2, L3, L4, L6.
- **L18 Identity Keys** are deterministic outputs of canonical-hash
  rules in code; the rules themselves are version-pinned (L21) and
  any change in derivation is treated as a Breaking amendment per C8.
- **L19 Snapshots** are produced by `snapshot-build` activities at
  pricing/calibration epochs; content-addressed; immutable per N9 + N10.
- **L20 Idempotency Tokens** are minted at the workflow boundary by
  the issuing system or carried in inbound messages; uniqueness within
  scope is enforced at ingress per N4.
- **L21 Version Pins** are recorded with every transaction (executor
  binary git_sha, container_digest, CDM version, contract version,
  model version); any change is a deployment event captured in a
  pre-registered policy event.
- **L22 Hash-Chain Anchor** is computed by the executor at every commit;
  verifiable by any auditor with the genesis hash and the chain.
- **L23 Capability/Permission** is administered by the
  `capability-administration` workflow; every grant/revoke is a recorded
  L14 event; capability checks are runtime gates on every read/write.
- **L24 Orchestration State** is the Temporal-history-class data
  consumed by the workflow framework; the boundary discipline (N1, N9)
  applies — workflow histories are themselves append-only and
  cryptographically anchored.

---

## §4 Realism budget

I distinguish **unconditional guarantees** (the data layer provides them
by construction) from **conditional guarantees** (the data layer
provides them under named operational assumptions). I name every
operational assumption explicitly.

### §4.1 Unconditional guarantees (provided by construction)

- **U1.** Append-only mutation discipline on L1, L4 (chains), L6, L10,
  L11, L12, L14, L15, L16. By N9; nothing mutates in place.
- **U2.** Bitemporal indexing on every leaf in C1 and C4. By N6.
- **U3.** Deterministic identity for L18 keys. By construction
  (canonical-hash derivation in code).
- **U4.** Hash-chain tamper-evidence on L14 (and by extension, L15, L16
  as projections of L14). By L22 + N9.
- **U5.** Idempotency on inbound payloads with valid L20 tokens. By N4.
- **U6.** Schema-pinned validation at ingress. By N3 + L21.
- **U7.** Single-writer-per-field on L8 and L9 (via C11 of StatesHome,
  enforced by handler-class type-tagging).
- **U8.** Replay determinism for any consumer of L19 snapshots that uses
  only memoised activity results (per the determinism contract — TEMPORAL
  owns the workflow-history side; NAZAROV provides snapshot determinism).

### §4.2 Conditional guarantees (with named assumptions)

- **C-A1. Cryptographic primitive soundness.**
  *Guarantee:* signatures on L17 envelopes are unforgeable, replay-resistant,
  and recoverable from key compromise.
  *Assumption:* the chosen primitive (curve, hash) is sound under standard
  cryptographic assumptions; the cryptographer-of-record (TBD-with-owner)
  has ratified the choice.
  *Owner:* head of cryptography (or external advisor).
  *Violation consequence:* every attested datum becomes potentially forged;
  the boundary fails closed.
  *Detection signal:* primitive-soundness advisories from cryptographic
  community; quarterly review.

- **C-A2. HSM custody discipline.**
  *Guarantee:* boundary-crossing keys are not exfiltrated.
  *Assumption:* the HSM vendor's attestation is trustworthy; key-ceremony
  procedures are executed correctly; multi-person control is honoured.
  *Owner:* head of security operations.
  *Violation consequence:* attestation is compromised; trust assumption N12
  in registry must trigger emergency rotation.
  *Detection signal:* HSM tamper alarms; key-usage anomaly detection.

- **C-A3. Vendor honesty (per attested vendor).**
  *Guarantee:* a vendor's signed attestation reflects what the vendor's
  systems actually believe.
  *Assumption:* the vendor is not adversarial against the firm.
  *Owner:* per-vendor relationship owner (data operations).
  *Violation consequence:* coordinated false-attestation could pass
  innovation gating in L13 if gradual; the multi-source aggregation rule
  in N8 is the defence.
  *Detection signal:* cross-vendor disagreement above threshold; downstream
  PnL-explain residual.

- **C-A4. Settlement-layer SSI freshness.**
  *Guarantee:* the SSI used at settlement-instruction projection time is
  the SSI valid at that time.
  *Assumption:* the settlement layer (which owns L5 outside the Ledger
  boundary) maintains its own freshness contract per its own specification.
  *Owner:* settlement-operations team.
  *Violation consequence:* misrouted wires; CSDR penalties; in worst case,
  wires to fraudulent accounts.
  *Detection signal:* settlement-fail confirmations (L12); virtual-wallet
  contra-balance reconciliation breaks.

- **C-A5. CDM/ISO 20022/FpML schema stability within a pinned version.**
  *Guarantee:* mapping outputs are bit-identical for the same input under
  the pinned version.
  *Assumption:* the standards body does not retroactively redefine semantics
  within a published version.
  *Owner:* CDM/ISO interop lead (MATTHIAS in this team).
  *Violation consequence:* historical mappings produce different outputs on
  replay; v10.3 §17.2 limitation 9 is violated.
  *Detection signal:* round-trip test failures in the CI of the mapping
  layer.

- **C-A6. Calibration model soundness.**
  *Guarantee:* the Kalman filter posterior is a meaningful certified
  parameter estimate when `certified = true`.
  *Assumption:* the model specification (process noise `Q`, observation
  noise `R`, prior, no-arbitrage projection) is correctly specified; the
  innovation gate threshold is appropriately tuned.
  *Owner:* model-validation team (downstream of NAZAROV; not my section).
  *Violation consequence:* certified state is silently wrong; PnL-explain
  residual blows up; FSM transitions to Quarantined.
  *Detection signal:* PnL-explain residual exceeds policy tolerance (L7);
  cross-asset coherence break (valuation v1.0 §4.9).

- **C-A7. Authority registry currency.**
  *Guarantee:* signatures verify against the authority's currently-valid
  key.
  *Assumption:* GLEIF, SWIFT, ISO, FINOS publish key updates and
  revocations in a timely manner; our key-rotation pipeline ingests them
  within the advertised SLA.
  *Owner:* identity-and-trust operations.
  *Violation consequence:* either falsely accepting a revoked key (over-
  trust) or falsely rejecting a valid one (under-trust).
  *Detection signal:* authority-side revocation publications; failed-verify
  rates above baseline.

- **C-A8. Closed-system boundary integrity.**
  *Guarantee:* every datum entering the Ledger crosses a recorded boundary.
  *Assumption:* the boundary itself is honoured by every component;
  no engineering shortcut writes directly to L1, L8, L9, or L14 outside
  the executor's path.
  *Owner:* architecture review board.
  *Violation consequence:* the closed-system property of v10.3 collapses;
  every formal invariant becomes contingent on undocumented behaviour.
  *Detection signal:* code-review enforcement; integration tests that
  refuse non-executor writes.

- **C-A9. Workflow-history determinism (TEMPORAL-owned, mentioned for
  completeness).**
  *Guarantee:* a workflow replay produces the same output as the original.
  *Assumption:* workflow code is purely deterministic (no `Now()`, no
  uncaptured non-determinism); version pins are honoured.
  *Owner:* TEMPORAL (this is their section, not mine).
  *Violation consequence:* PnL-explain reconstruction fails; the
  framework's replay theorem is unprovable.
  *Detection signal:* determinism violations from Temporal SDK at replay.

- **C-A10. Retention sufficiency.**
  *Guarantee:* historical replay against any `t_known` within the
  retention window is possible.
  *Assumption:* retention policy (L7) keeps L10/L11/L12/L14/L19 long enough
  to satisfy the longest-running unit's lifetime + the longest dispute
  window + the longest regulatory record-keeping requirement.
  *Owner:* records management + compliance.
  *Violation consequence:* a 30-year bond's late-life replay or a 7-year
  regulatory audit cannot be answered.
  *Detection signal:* retention-policy-vs-instrument-lifetime crosscheck
  at unit registration.

**Total: 8 unconditional + 10 conditional assumptions = 18 budget items.**

Every assumption is owned, scoped, and detectable. Every guarantee is
either unconditional-by-construction or conditional-with-named-assumption.
Nothing in this section is unstated.

---

## §5 What I refuse to admit, and why

Per NAZAROV deferral discipline:

- **No "trust the vendor feed" without an envelope.** N2 forbids it.
- **No silent fallback to last-known-good.** N7.2 forbids it; the
  fallback chain as actually traversed is a snapshot field.
- **No mutating restatement.** N9 forbids it; restatements are new rows.
- **No single-source data on materially-impacting paths without a named
  authority assumption.** N8.2 + C-A3.
- **No hardcoded calendars, day-counts, or jurisdictions in code.** L4 +
  L7 lift them to data.
- **No "balance" written independently of the move stream.** L14 is the
  single source; L8 and L9 are projections (Lattner: "balances must
  remain a projection, forever").
- **No untyped trust assumption.** N12.2 forbids it.

---

## §6 Verification approach

An auditor confirms a candidate implementation satisfies this section by:

1. **Boundary inventory.** Enumerate every code path that writes into
   L1, L8, L9, L14. Confirm only the executor (and deterministic
   handlers reached through it) writes.
2. **Attestation audit.** For each leaf in C4, randomly sample inbound
   payloads from production traffic; verify that every payload carries
   a verifiable L17 envelope and that verification is enforced at
   ingress.
3. **Replay determinism test.** Pick a historical transaction; reconstruct
   its inputs from L19 snapshot + L21 version pins; rerun the handler;
   check bit-identical output.
4. **Bitemporal correctness test.** Pick a vendor-restatement event;
   verify "as known at `t_old`" returns the pre-restatement value and
   "with corrections through `t_new`" returns the restated value.
5. **Trust registry walk.** Open the trust assumption registry; confirm
   every assumption has name, scope, owner, violation consequence,
   detection signal; confirm at least one detection signal per
   assumption is currently being monitored.
6. **Idempotency replay.** Replay an inbound message twice; verify the
   second replay returns the memoised outcome and produces zero side
   effects.
7. **Mutation forensics.** Attempt to write directly to L1, L8, L9, L14
   bypassing the executor; verify the storage layer rejects.
8. **Hash-chain integrity check.** Sample N transactions; verify each
   `prev_hash` matches the prior canonical encoding; verify genesis
   hash matches L7.
9. **Snapshot reproducibility.** Reconstruct snapshot ID from its
   payload set; verify content-addressed match.
10. **Closed-system perimeter test.** Inject a malformed payload at
    every boundary endpoint; verify quarantine + provenance recording;
    verify no downstream consumer sees the malformed datum.

If all ten audit steps pass, the candidate implementation satisfies the
NAZAROV bar. Failures are findings, not preferences.

---

## §7 Cross-references to sibling team members

- **MATTHIAS** owns the CDM cross-walk for every leaf where CDM provides
  a typed representation (L1 ProductTerms, L6 Legal Agreement, L14
  MoveStream payloads, L11 Lifecycle/Oracle attestations). I provide the
  attestation envelope (L17) discipline; MATTHIAS provides the typed
  payload schema.
- **TEMPORAL** owns the workflow shape for every "owning workflow"
  named in §3. I specify what the workflow must guarantee (NAZAROV
  bar); TEMPORAL specifies how the workflow is structured.
- **MINSKY** owns the type design that makes illegal states
  unrepresentable. I name the closed enumerations and the totality
  conditions; MINSKY makes them types.
- **FORMALIS** owns the invariants (C1–C12, P1–P23) that the data
  layer must support. I specify the data primitives that those
  invariants rely on.
- **TESTCOMMITTEE** owns the property-based test generators. I
  specify the generator universe (closed enums in L7, L21) and the
  shrink targets (per leaf in §3).
- **ISDA** owns the regulatory direction-of-travel. I specify the
  attestation discipline that lets us comply with whatever the
  direction demands.
- **GROTHENDIECK** owns the structural argument; my six-class spine
  reduces to his three sheaves under a forgetful functor (C1+C2+C3 →
  Definitions; C4 → Observations; C5 → Effects; C6 is the
  morphism-recording layer).
- **SBL** owns the six-coordinate semantics inside L9; I provide the
  attestation discipline for the moves that touch each coordinate.
- **GEOHOT** owns the delete-test; my taxonomy survives his pressure
  because every leaf has a named violation consequence (cf. §4.2).
- **JANE STREET** owns "make illegal states unrepresentable"; my N3 +
  N9 are the boundary expression of that principle.
- **KARPATHY** owns the simplest end-to-end loader per leaf; my
  per-leaf workflow specs in §3 give him the contract.

This section is consistent with all 18 sibling enumerations.
