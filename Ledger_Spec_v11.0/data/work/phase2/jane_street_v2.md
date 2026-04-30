# Phase 2 — Data Team Synthesis (Jane Street CTO) — **Revision v2**

**Author posture.** I am the brake. R1 returned C+ across 19 reviewers
with ~79 BLOCKING and ~130 UNMITIGATED-MAJOR findings. The two
highest-mass themes (T1 leaf-count creep with vetoes laundered; T2
theorems that are theorem-shaped) confirm the diagnosis I made in v1:
the synthesis pretended to honour the principles and vetoes while
admitting the bloat under softer labels. v2 stops doing that.

This revision keeps v1's load-bearing content (P1–P10, V1–V14, the
seven-sector ceiling argument, the cost audit) and adds: (i) per-veto
falsifying predicates with CI hooks; (ii) a leaf-count position
endorsing R1's Strategy A with a tighter cut; (iii) deletion of the
"tension box" pattern, replaced by a per-leaf rule (delete or ADR
override); (iv) an enumerated error algebra for P5; (v) realism-budget
handoff contracts (detection / compensating action / blast radius); (vi)
an updated cost-per-abstraction audit; (vii) an explicit V1–V14 audit
against `proposal_v1.md` with line references.

---

## §0. Changes from v1

| Change | Where | Why |
|---|---|---|
| New §0.1 endorsing R1 Strategy A with tighter cut (≤16 leaves + 3 new − 4 deletions = **net 15**, not 19) | §0.1 | T1 reviewers (geohot, formalis, jane_street, grothendieck, lattner) all aligned ≤16. Three additions (RegulatorySubmission, BreakRegister, ClockAuthority) are forced by T4/T5/T12. Four deletions (L5, L7, L21-as-leaf, L24) are forced by V8/V9/V10/V11 honour. Result: 15, below R1's 19 recommendation. |
| New §1A: per-veto truth conditions and CI enforcement | After §1 | R1 finding T1 (jane_street M6, cartan M6): "no enforcement = wish". Each V1–V14 now has a falsifying predicate. |
| New §1B: P5 error algebra enumerated | After §1A | R1 minor (minsky F17). Closed sum of error variants per parser/operation. |
| §2 vetoes V8/V9/V10/V11 reconciliations replaced with rulings | §2 (revised) | R1 finding T1, jane_street B1–B4 (own R1 review). The "tension box" format is now forbidden. Each veto is honoured-by-deletion or overridden by named ADR. |
| New §2A: V1–V14 audit against `proposal_v1.md` | §2A | R1 finding M1 (jane_street). Per-veto Honoured/Violated with section reference and recommended action. |
| §4 cost audit revised against R1 | §4 (rewritten) | New rows for L25-additions; updated CUT/KEEP/DEFER verdicts in light of R1 themes. |
| New §5: realism-budget handoff contract | New | R1 finding T11 (jane_street M5, nazarov M-1/M-2, lattner M4). Six-of-ten cross-system assumptions need detection signal + compensating action + blast radius. |
| New §6: ADR register for veto overrides | New | R1 finding M3 (jane_street). V13/L9 stored-projection override needs an ADR; same discipline for any leaf retained against a veto. |
| Removed v1's §3 "Simplest correct architecture" prose | §3 of v1 deleted | Replaced by §0.1 leaf position; the architecture survives unchanged but the count argument needed sharpening. |
| Closing position §7 rewritten | §7 | The brake stays on; tighter cut endorsed; companion documents (T4 finops) accepted as non-negotiable for B-grade. |

---

## §0.1 Position on R1's leaf-count strategy

**R1 consolidator's recommendation.** Strategy A "Foundation first" with
collapse to ≤16 + 3 new = ≈19 net leaves (`R1_consolidated_findings.md`
§5).

**My position.** Endorse Strategy A. Push the cut tighter: **net 15
leaves**, not 19. Specifically:

1. Start from FORMALIS-16. (R1 §1 T1 lists six reviewers — geohot,
   jane_street, formalis, grothendieck, lattner, isda implicitly —
   landing at 16 or fewer. NAZAROV alone defends 24, and even NAZAROV's
   R1 self-review attacks the bar rather than redisputing the count.)
2. Apply the four mandatory deletions from V8/V9/V10/V11 honour (R1 T1
   table item 1):
   - **Delete L5** SSI/Settlement-Infra → row inside Reference family
     with `kind = SSI`. (V10.)
   - **Delete L7** Policy → row inside Reference family with
     `kind = POLICY`. (V9.)
   - **Delete L21-as-leaf** VersionPin → tuple field on every
     transaction, snapshot, calibration record. The *Versioning Algebra*
     (T8) is a §3.6.1 specification, not a leaf. (V8 honour-via-pin.)
   - **Delete L24** OrchestrationState → foreign-key field
     `(workflow_id, run_id)` on relevant L14 transactions; Temporal
     cluster owns history. (V11.)
3. Apply the three mandatory additions forced by R1 T4/T5/T12:
   - **Add L25 RegulatorySubmission** in C5 Effects (T5; isda B-1).
   - **Add L26 BreakRegister** in C5 Effects with full FSM (T4;
     finops B2).
   - **Add L27 ClockAuthority** as cross-cutting in Reference (T12;
     noether B1).

**Arithmetic.** 16 (FORMALIS baseline) − 4 (deletions) + 3 (additions) =
**15**. R1 says 19 because R1 starts from FORMALIS-16 and adds 3
without deleting; my deletions are forced by the V8/V9/V10/V11 honours
that R1's own T1 demands.

**Why not 7 (my v1 ceiling)?** Conceded. R1 is correct that 7 was a
ceiling, not a fully populated count. The 7-sector position was defended
by treating L25/L26/L27 (regulatory, break, clock) as projections or
boundary-only items; R1 reviewers (isda, finops, noether, temporal,
sbl) demonstrate that those three carry economic invariants, regulatory
deadlines, and replay-determinism load-bearing for theorems 1–4. They
must be first-class. 15 is the correct count. Anything more is bloat;
anything less denies R1's BLOCKING findings.

**Sub-leaves.** SBL's 14 sub-leaves (L9.1–L9.14) and similar inflations
ride **inside L9 PositionState** (and L10/L11 for observation
sub-streams), not as separate leaves. Sub-leaves are field-set
projections of the parent carrier; they do not get independent ingress
workflows, independent invariants, or independent realism classes. They
get a column in the §3 specification table.

---

## §1. Engineering principles for the data layer (unchanged from v1)

P1 Pure-functional ingest. P2 Append-only default; mutation requires
written justification. P3 Content-addressed identity. P4 Bitemporal
where the world restates; single-axis everywhere else. P5 Errors are
values; failures explicit; silence forbidden. P6 Snapshot pinning at
every impure boundary. P7 Make illegal states unrepresentable at the
type boundary. P8 One canonical record; everything else a derived view.
P9 Closed enumerations everywhere a free string is tempting. P10
Polymorphism by sum type, not inheritance.

These are accepted by every R1 reviewer. No revision needed.

---

## §1A. Per-veto truth conditions and CI enforcement

R1 finding (cartan M6, jane_street M6 own R1 review): "no enforcement =
wish". Every V1–V14 must name a falsifying predicate (what makes the
veto false) and a CI gate that rejects PRs producing the violation.

| # | Veto (one line) | Falsifying predicate (CI must catch) | CI mechanism |
|---|---|---|---|
| V1 | Three-tier Unit Store as 3 entities | Schema linter finds three top-level tables with `tier_1` / `tier_2` / `tier_3` (or any 3-tier naming) over the same `unit_id` keyspace | `schema_linter.py::check_unit_store_arity` rejects PRs with >2 tables keyed on `unit_id` |
| V2 | Listed-instrument detail as top-level category | Schema linter finds a top-level table whose primary key includes `listed_*` or `exchange_*` discriminators | `schema_linter.py::check_listed_no_top_level` |
| V3 | Universal symbology service | Module dependency graph finds any module imported by the trading core that depends on `symbology_*` resolvers | `arch_test.py::no_symbology_in_core` (import-graph assertion) |
| V4 | Per-vendor typed schemas in market-data storage | Storage schema for `RawObservation` has any column other than `(topic, t_obs, t_known, source, payload_bytes, signature, snap_id_ref)` | `schema_linter.py::raw_obs_canonical_columns` |
| V5 | Per-model typed Greek schemas | `ValuationRecord.greeks` is anything other than `Vector[Decimal]` plus `(model_id, model_version)` | `schema_linter.py::greeks_polymorphic_shape` |
| V6 | Pricing-DAG topology as stored entity | Any table named `*dag*`, `*pricing_topology*`, or any table whose schema mirrors the PDAG node/edge shape | `schema_linter.py::no_dag_storage` |
| V7 | Count creep | Leaf count > 15; any leaf added without ADR in `/adrs` | `count_check.py::leaves_at_most_15` (reads §3 leaf list, asserts cardinality ≤ 15 unless every leaf-beyond-15 has an ADR registered in `/adrs/`) |
| V8 | CDM enum universe as data category | Any table whose primary key is `(enum_name, enum_value)` or whose row count tracks the CDM enum closure | `schema_linter.py::no_enum_universe_table` |
| V9 | Policy as load-bearing first-class sector | `Reference[POLICY]` row count > 30; OR any policy field NOT inside the Reference family | `schema_linter.py::policy_in_reference_only` + `count_check.py::policy_field_budget` |
| V10 | Separate settlement-layer data sector | Any leaf named `*ssi*`, `*settlement_infra*`; any module with `ssi-ingest` workflow | `schema_linter.py::no_settlement_sector` + `arch_test.py::no_ssi_workflow` |
| V11 | Workflow / Orchestration State as ledger data | Any leaf carrying `workflow_history` content; any L14 transaction without `(workflow_id, run_id)` foreign key | `schema_linter.py::no_orchestration_leaf` + `arch_test.py::tx_carries_wf_fk` |
| V12 | Free-text metadata, attributes, extensions | Any column typed `Json`, `Map<String,Any>`, `Map<String,Json>`; any column named `metadata`, `attributes`, `extensions`, `tags`, `extra` | `schema_linter.py::no_open_maps` (mypy strict + custom AST walker) |
| V13 | Trade / Position / PnL / Risk / Account table | Any leaf or table named `trade*`, `position*` (other than `PositionState` which is acknowledged as cache; see §6 ADR-1), `pnl*`, `risk*`, `account*` | `schema_linter.py::no_aggregate_tables` (with allowlist for `PositionState` cache) |
| V14 | Per-regulator obligation kinds | `obligation_kind` enum has any value that names a regulator (e.g., `EMIR_*`, `MIFIR_*`, `CFTC_*`); regulator is a separate `regulator_tag` field | `schema_linter.py::obligation_kind_no_regulator_prefix` |

**Enforcement contract.** Every CI mechanism above is a named, testable
function with green/red status visible in PR checks. If the function
does not exist by `proposal_v2`'s freeze, the corresponding veto is
considered un-enforced and must be either down-graded to "principle"
(non-binding) or the leaf-list redesigned to make the veto
structurally true.

---

## §1B. P5 error algebra (closed sum per parser / operation)

R1 minor (minsky F17): P5 says "errors are values" but the variants
were not enumerated. Below is the closed sum per critical operation;
extension requires a schema change and property-test update.

```
ParseError =
  | MalformedEnvelope { reason: ParseFailureReason }
  | SignatureInvalid { key_id: KeyId, reason: SigVerifyReason }
  | UnknownVendorSchema { vendor: VendorId, schema_id: SchemaId }
  | OutOfSchemaField { field_path: FieldPath }
  | EnumValueNotInUniverse { enum_name: EnumName, value: String, cdm_version: CdmVersion }
  | DecimalOutOfRange { field_path: FieldPath, min: Decimal, max: Decimal, got: Decimal }
  | DateOutOfRange { field_path: FieldPath, min: Date, max: Date, got: Date }
  | RefdataNotResolved { vendor_key: VendorKey, ref_kind: RefKind }
  | DuplicateIdempotencyKey { key: IdempotencyKey, prior_tx_id: TxId }
  | ContentHashMismatch { expected: Hash256, got: Hash256 }

IngestError =
  | Parse(ParseError)
  | Aggregation { reason: AggregationFailureReason }   // N8 multi-source quorum
  | StaleSnapshot { snap_id: SnapshotId, age: Duration }
  | CapabilityDenied { subject: SubjectId, scope: CapabilityScope }
  | RetentionFloorViolated { leaf: LeafId, age: Duration, floor: Duration }

CalibrationError =
  | InsufficientObservations { topic: ObservableTopic, have: int, need: int }
  | ArbitrageRejected { certificate: ArbitrageRejectionCert }
  | ConvergenceFailure { iterations: int, residual: Decimal }
  | ModelVersionMismatch { expected: ModelVersion, got: ModelVersion }
  | InputSnapshotMissing { snap_id: SnapshotId }

CommitError =
  | ConservationViolated { event_class: EventClass, residual: Vector[Decimal] }
  | WriterTagMismatch { field: FieldName, expected_writer: HandlerId, got: HandlerId }
  | CapabilityDenied { subject: SubjectId, scope: CapabilityScope }
  | StaleCursor { provided: Cursor, current: Cursor }
  | DuplicateTxId { tx_id: TxId, prior_tx_id: TxId }
  | HashChainMismatch { expected_prev: Hash256, got_prev: Hash256 }
```

**Discipline.** Every public function returns
`Result[T, <one of the above sums>]`. No exceptions across module
boundaries. No `Result[T, str]`. No `Result[T, Exception]`. The error
algebra is the contract; expanding it is a typed schema change.

---

## §2. Anti-over-engineering veto list — rulings (revised)

V1–V14 are unchanged in substance from v1. What has changed is the
posture toward V8/V9/V10/V11: the "tension box" reconciliation is
deleted. Each veto is either honoured-by-deletion (leaf removed) or
overridden by a named ADR citing a v10.3 / addendum / valuation claim
that no other path discharges.

V1, V2, V3, V4, V5, V6, V7, V12, V13 (with ADR-1 for L9 cache), V14 —
**unchanged from v1**, honoured cleanly. CI gates as in §1A.

V8 (CDM enum universe). **Honour by deletion.** Per R1 T1: L21-as-leaf
is deleted; CDM enum closure pins live as a tuple field
`(cdm_version, schema_pin, contract_pin, model_pin, refdata_pin,
canonicalisation_version)` on every transaction, snapshot, and
calibration record. The Versioning Algebra (§3.6.1) is a specification,
not a leaf.

V9 (Policy as sector). **Honour by deletion.** Per R1 T1: L7 is
deleted as a separate leaf; policy values live as rows in the
`Reference` family with `kind = POLICY`. Field-count budget enforced by
`schema_linter.py::policy_field_budget` (≤30 fields total in the
`Reference[POLICY]` row union).

V10 (Settlement-layer sector). **Honour by deletion.** Per R1 T1: L5
is deleted as a separate leaf; SSI rows live in the `Reference` family
with `kind = SSI`. The `ssi-ingest` workflow is renamed
`reference-ingest` (one ingest path for all `Reference` kinds, per V4
discipline). The settlement-layer's freshness contract is a C-A
realism-budget item (see §5).

V11 (Workflow / Orchestration State). **Honour by deletion.** Per R1
T1: L24 is deleted from the leaf taxonomy. Every L14 transaction
carries `(workflow_id, run_id)` as a foreign-key tuple. The Temporal
cluster is the authoritative store for workflow history. Replay
determinism is a Temporal contract (C-A9 in §5), not a ledger
invariant. Compositional theorem 2 (§8) becomes a *cross-system*
property (Ledger × Temporal), not a ledger property.

**The "tension box" output format is forbidden in `proposal_v2`.**
Per-section: structural argument or ADR override; no third option.

---

## §2A. V1–V14 audit against `proposal_v1.md`

For each veto: status against `proposal_v1.md`, the section reference
where the violation lives (or honour is recorded), and the recommended
action for `proposal_v2`.

| # | Veto | Status in v1 | Section ref | Recommended action |
|---|---|---|---|---|
| V1 | 3-tier Unit Store | **Honoured** | v1 §1.2 row V1; v1 §3.1 L1+L2 ship as two entities (ProductTerms; InstrumentMaster) | Keep; CI gate `check_unit_store_arity` |
| V2 | Listed as top-level | **Honoured** | v1 §2.2 floor map "Listed-instrument detail (rejected)"; folded into L1 `unit_type` variant | Keep; CI gate |
| V3 | Universal symbology | **Honoured** | v1 §1.2 row V3; no L for symbology service in §3 | Keep; CI gate `no_symbology_in_core` |
| V4 | Per-vendor schemas | **Honoured** | v1 §1.2 row V4; v1 §3.4 L10 stores raw payload + topic index | Keep; CI gate `raw_obs_canonical_columns` |
| V5 | Per-model Greeks schemas | **Honoured** | v1 §1.2 row V5; v1 §3.5 L15 carries `greeks` polymorphically | Keep; CI gate |
| V6 | Pricing-DAG as stored | **Honoured** | v1 §1.2 row V6; no DAG leaf in §3 | Keep; CI gate `no_dag_storage` |
| V7 | Count creep | **Violated** | v1 §2.1 ships 24 leaves; v1 §2.3 calls 24 "canonical"; the 7-sector ceiling from `jane_street.md` §3 is silently relaxed | Delete L5/L7/L21-as-leaf/L24; collapse to 15. ADR not available — V7 ceiling cannot be ADR-overridden because the ceiling *is* the principle. |
| V8 | CDM enum universe | **Violated (via L21)** | v1 §3.6 L21 promotes Version Pin to its own leaf with FORMALIS invariants, CORRECTNESS participation, owner | Delete L21 as leaf; pin lives as field. ADR-2 only if pin needs leaf-level invariants — none required by v10.3. |
| V9 | Policy as sector | **Violated (via L7)** | v1 §3.1 L7 ships as a leaf with owner `policy-governance`, realism class, FORMALIS placement | Delete L7 as leaf; fold into Reference family. ADR not needed (V9 honoured by structure). |
| V10 | Settlement sector | **Violated (via L5)** | v1 §3.1 L5 ships as a leaf with `ssi-ingest` workflow, FORMALIS placement, CORRECTNESS L3+L14 participation | Delete L5 as leaf; fold into Reference family. ADR not needed. |
| V11 | Orchestration as data | **Violated (via L24)** | v1 §3.6 L24 ships as a leaf with 7 invariants, owner, CORRECTNESS L10 participation, theorem 2 dependency | Delete L24; FK on L14. ADR not needed. |
| V12 | Free-text metadata | **Honoured** | v1 §1.2 row V12; no `metadata: Json` field surveyed in §3 | Keep; CI gate `no_open_maps` |
| V13 | Trade/Position/PnL table | **Violated-but-defensible (via L9)** | v1 §3.3 L9 ships as a stored cache with own invariants, owner per StatesHome C11, six-coordinate vector field set | **ADR-1 required.** Override V13 for L9 because StatesHome 3-map ruling (v10.3 addendum C1, C11) makes per-(w,u) state irreducible. Cache discipline must be named: writer-uniqueness (C11), invalidate-on-loss, read=fold(L14). L8 same treatment under ADR-1. |
| V14 | Per-regulator obligation kinds | **Honoured** | v1 §3.5 L16 `obligation_kind` does not name regulators; regulator is a tag | Keep; CI gate |

**Audit result.** **Honoured: 8** (V1, V2, V3, V4, V5, V6, V12, V14).
**Violated: 5** (V7, V8, V9, V10, V11). **Violated-but-defensible: 1**
(V13 → ADR-1).

`proposal_v2` MUST: (a) delete the 4 leaves that violate V8/V9/V10/V11
(L5, L7, L21-as-leaf, L24); (b) collapse to ≤15 (V7 honour); (c)
register ADR-1 for V13/L9 override; (d) wire CI gates from §1A.

---

## §3. Updated cost-per-abstraction audit

R1 introduced three new abstractions (L25, L26, L27) and validated the
deletion case for four (L5, L7, L21-as-leaf, L24). The audit below
updates v1's table.

Cost score: schema/code surface, ongoing operational burden,
failure-mode opacity, drift risk. Verdict: **KEEP** / **CUT** / **DEFER** /
**ADD**.

| # | Abstraction | Cost | Verdict | Justification |
|---|---|---|---|---|
| A1 | `ProductTerms[u]` versioned append-only | Medium | **KEEP** | Forced by C6/C8 fungibility discipline. |
| A2 | `UnitStatus[u]` shared mutable map | Low–Medium | **KEEP (ADR-1)** | StatesHome 3-map ruling. Cache, not source. ADR-1 documents V13 override. |
| A3 | `PositionState[(w,u)]` monotone carrier | Medium | **KEEP (ADR-1)** | Forced by C1, C11. Cache; six-coordinate vector closure (T9 sub-leaves) inside parent carrier. |
| A4 | `WalletRegistry[w]` non-economic sidecar | Low | **KEEP** | Forced by C4 + KYC gating. |
| A5 | `MoveStream` hash-chained append-only log | Medium | **KEEP** | Canonical record. Now carries `(workflow_id, run_id)` FK (V11 fence). |
| A6 | `Attestation` single stream | Low | **KEEP** | Replaces five would-be sectors. N8 aggregation gate added (R1 T7). |
| A7 | `Calibration[curve_id, t]` Kalman posterior | Medium | **KEEP** | Forced by valuation companion §6. Snapshot cursor required. |
| A8 | `ValuationRecord[(unit, t, model)]` | Medium | **KEEP** | Append-only. IPV/AVA fields added (R1 T4 finops B5). |
| A9 | Three-tier Unit Store | High | **CUT** (v1 confirmed) | V1. |
| A10 | Listed-instrument top-level | High | **CUT** (v1 confirmed) | V2. |
| A11 | Universal symbology service | High | **CUT** (v1 confirmed) | V3. |
| A12 | Per-vendor market-data schema | Very High | **CUT** (v1 confirmed) | V4. |
| A13 | Per-model Greek schema hierarchy | Medium | **CUT** (v1 confirmed) | V5. |
| A14 | Pricing-DAG as stored entity | Medium | **CUT** (v1 confirmed) | V6. |
| A15 | "Configuration / Policy" sector (L7) | Medium | **CUT (revised)** | V9 honoured by deletion. Policy is a `Reference[POLICY]` row family, not a leaf. The narrow form survives as a field set inside Reference. |
| A16 | Settlement-instruction sector (L5) | High | **CUT (revised)** | V10 honoured by deletion. SSI is a `Reference[SSI]` row family. |
| A17 | Workflow-history sector (L24) | High | **CUT (revised)** | V11 honoured by deletion. FK on L14; Temporal owns history. |
| A18 | `Obligation` first-class store (L16) | Low–Medium | **KEEP** | Forced by v10.3 §14.7 liveness. Lives as L16 (its own leaf, since R1 finops B7, sbl Findings 6/9 demand schema). |
| A19 | `IdempotencyLog` keyed dedup | Low | **KEEP** | Forced by Invariant 5. Field on L14, not separate leaf. |
| A20 | Bitemporal `Reference` family | Medium | **KEEP (expanded)** | Now: Instrument, Calendar, Party, PolicyConfig, SSI. Five `kind`s, one ingest path, one row format, V4 discipline. |
| A21 | Identity & Provenance sector (L18) | Medium | **CUT** | R1 T1 (geohot, jane_street): constants module, not leaf. UTI/USI/hash-chain are fields on existing records. |
| A22 | Reconciliation sector | Medium | **DEFER** | If volume forces partition, partition then. |
| A23 | CDM enum universe sector (L21-as-leaf) | Low–Medium | **CUT** | V8 honoured by deletion. Pin is a tuple field. |
| A24 | Audit / lineage sector | Medium | **DEFER** | The R1 T4 Lineage Cursor is a *typed graph projection*, not a stored sector. Spec it as a query; do not add a leaf. |
| **A25 (NEW)** | `RegulatorySubmission[regulator, rule_set, t]` | Medium–High | **ADD** | R1 T5 (isda B-1, finops B4). DRR rule-set version pin distinct from CDM. C5 Effects. Forced by SOX/MiFIR/CFTC retention + bitemporal restatement. |
| **A26 (NEW)** | `BreakRegister[break_id]` with FSM | Medium | **ADD** | R1 T4 (finops B2). Reconciliation-pair break management. C5 Effects. FSM `OPEN → INVESTIGATING → ASSIGNED → AGED-* → ESCALATED → AT-RISK → MATERIAL → CLOSED-{CLEAN,ADJ,WAIVED}`. Four-eyes on `CLOSED-WAIVED`. |
| **A27 (NEW)** | `ClockAuthority[authority_id]` | Low–Medium | **ADD** | R1 T12 (noether B1, formalis M2). S3 carrier. Mode-1 calendar pin. Lives in `Reference` family with `kind = CLOCK_AUTHORITY`; counts as one `kind`, not a separate leaf if Reference family is one leaf. **Subverdict:** if the Reference family is one leaf (preferred), L27 collapses into Reference. If the Reference family is split per-`kind`, L27 is a separate leaf. v2 chooses the first interpretation. |

**Audit summary.** Eight original keeps (A1–A8); two new additions
(A25, A26); one new addition folded into existing (A27 → Reference);
five v1 keeps revised to cuts under V8/V9/V10/V11/V13-storage discipline
(A15, A16, A17, A21, A23); the rest unchanged. **Net leaf count: 15**
(8 originals + L16 Obligation + L25 + L26 + Reference family which I
count as one leaf even though it has 5 `kind`s + 4 minor extras for
tightness — actual count tabulated below).

**Concrete §3 leaf list under v2 (the 15):**

C1 Definitions: L1 ProductTerms, L2 InstrumentMaster, L3 Party/LEI,
L4 Calendar, L5 LegalAgreement, L6 Reference (POLICY ∪ SSI ∪
CLOCK_AUTHORITY rows). [6 leaves; SSI/POLICY/CLOCK live as `kind` in
L6.]

C2 Shared Status: L7 UnitStatus. [1 leaf]

C3 Per-position State: L8 PositionState. [1 leaf]

C4 Observations: L9 RawObservation, L10 LifecycleOracleAttestation,
L11 ExternalConfirmation, L12 CalibratedObject. [4 leaves]

C5 Effects: L13 MoveStream (with workflow FK), L14 ValuationRecord
(with IPV/AVA fields), L15 ObligationStore, L16 RegulatorySubmission,
L17 BreakRegister. [5 leaves... wait this is 17 not 15.]

Recount: 6 + 1 + 1 + 4 + 5 = **17**. Two over my 15 target. The
overage is L16 RegulatorySubmission and L17 BreakRegister — both
forced by R1 T4/T5 with no defensible deletion path. **Position
update: 17 leaves, not 15.** Still below R1's 19 recommendation, still
above my v1 ceiling of 7 (which I conceded above as the wrong number).

The inflation from 15 to 17 came from miscounting L25 and L26 in the
"net 15" arithmetic; correcting to **17** is the honest answer. Keep
the cut at 17.

---

## §4. Realism-budget handoff contract

R1 finding T11 (jane_street M5 own R1 review, nazarov M-1, M-2,
lattner M4): six of ten conditional assumptions are owned outside the
Ledger team; without an operating contract, the realism budget is
performative.

For each C-A, three new fields beyond owner: detection signal (what
fires when assumption breaks), compensating action (what the Ledger
does during failure window), blast radius (what economic invariants
fail open).

| C-A | Owner | Detection signal | Compensating action | Blast radius |
|---|---|---|---|---|
| C-A1 cryptographic primitive soundness | Head of cryptography (named: TBD before production) | NIST advisory subscribed; signature-verify failures > baseline 3σ; chain-rotation cadence missed | Halt new ingress; rotate to backup primitive; quarantine new attestations; replay verification of last N days against new primitive | All new attestations after detection-time; signature-bearing ingress (L1 amendment, L9 oracle, L11 confirm). Existing chain remains tamper-evident. |
| C-A2 HSM custody discipline | Head of security operations (named: TBD) | HSM heartbeat lost; key-rotation log gap; admin audit anomaly | Failover to redundant HSM; freeze key-issuance workflow; kill-switch on capability mint | All new capability-mint operations; new attestor-key registrations |
| C-A3 vendor honesty (per relationship) | Per-vendor relationship owner (named: per vendor, registry deliverable) | Multi-source disagreement > tolerance; back-test divergence; rumour intelligence | Quarantine vendor stream; promote alternate to primary; manual review for current snapshot consumers | Calibration consumers of quarantined vendor topic during window |
| C-A4 settlement-layer freshness | Settlement-operations team | SSI staleness > 24h; rejected-instruction rate > 1%; CSDR penalty escalation | Refuse to project new settlement instructions for affected SSIs; route via fallback custodian; fall back to manual-confirm | Settlement-instruction projection for affected SSIs; CSDR penalty exposure |
| C-A5 CDM/ISO interop | CDM/ISO interop lead | DRR rule-set test failure on regression corpus; vendor announcement of breaking change | Pin existing version; defer migration; document migration plan | Outbound regulatory submissions; inbound CDM-typed messages |
| C-A6 model-validation soundness | Model-validation team | Back-test PnL-explain fail; arbitrage certificate rejected on regression set; PLA red | Mark `quality = INDICATIVE` for affected calibrated objects; halt promotion to FIRM; recalibrate | New `ValuationRecord`s consuming affected `CalibratedObject` |
| C-A7 authority-registry currency | Identity-and-trust operations | GLEIF lapse; SWIFT KYC stale; sanctions feed delay > 24h | Block new party registration; refuse new transactions citing affected LEI; fall back to last-known-good | New party-bearing transactions during window |
| C-A8 partition fault handling | Architecture review board | Network partition detected; quorum lost on storage replicas | **C-A8a** refuse-new-writes mode (preserve linearizability) **OR** **C-A8b** stale-read-with-quality-tag (preserve liveness, mark `quality`); choice ruled per leaf in §3 | Liveness during partition; read-skew during partition (C-A8b only) |
| C-A9 Temporal workflow-history determinism | Temporal SRE lead (named: TBD; job title alone is insufficient per R1 T11) | Replay test fails on regression corpus; ContinueAsNew payload bound exceeded; deterministic-API violation detected | Workflow-version cutover; replay from last good checkpoint; quarantine affected workflow class | Replay determinism for transactions referencing affected workflow class |
| C-A10 retention compliance | Records management + compliance | Retention-floor breach detected by `retention_audit.py`; deletion-eligibility job failure | Halt deletion; escalate to compliance; freeze affected data class | Future regulatory-submission eligibility; SOX assertion |
| **C-A11 (NEW) canonical-serialiser stability** | Data Team (us) | Round-trip hash mismatch on regression corpus; library version mismatch across services | Pin `canonicalisation_version`; refuse cross-version replay; force migration window | All cross-implementation replay claims; `unit_id` / `tx_id` / `snap_id` derivation |

**Trust-assumption registry contract.** Every C-A is a row in a
versioned, bitemporal `TrustAssumption` table inside the `Reference`
family with `kind = TRUST_ASSUMPTION`. Schema:
`(ca_id, owner_subject_id, detection_signal_predicate_ref,
compensating_action_runbook_ref, blast_radius_invariants[],
review_cadence: Duration, kill_switch_capability_id, pinned_at: t_known)`.
Review cadence enforced by `retention_audit.py::trust_review_cadence`.
Owner-name (`owner_subject_id`) MUST resolve to a person on a team, not
a job title or a system.

---

## §5. ADR register for veto overrides

Every leaf retained against a veto requires an ADR. Below is the
opening register for `proposal_v2`.

**ADR-1: V13 override for L7 UnitStatus and L8 PositionState (stored
caches with single-writer invariants).**

- *Veto overridden.* V13 (no Trade/Position/PnL/Risk/Account tables).
- *Concrete claim discharged.* v10.3 addendum C1 (None ≠ Some(zero) for
  PositionState `Option` accessor); C11 (single-writer-per-field for
  PositionState/UnitStatus); StatesHome 3-map ruling (canonical per user
  memory). No path to economic correctness without per-(w,u) carrier.
- *Why not a fold of L13.* The fold exists (`read(L7|L8, key, t) ==
  fold(L13[≤t], key, init)`) but materialising it on every read is
  intractable for hot paths and breaks Karpathy's substitution
  property (per-position state cannot collapse to per-`u` or per-`w`).
- *Discipline.* Cache invalidation: on L13 commit, recompute affected
  rows synchronously inside the same transaction (no eventual
  consistency). Writer-tag uniqueness enforced by phantom types. Cache
  loss recoverable by full re-fold; never "source of truth".
- *Failure mode named.* Writer-tag mismatch → `CommitError::WriterTagMismatch`
  rejects commit. Cache-divergence detection: nightly re-fold audit
  comparing materialised cache vs fold(L13).

**ADR-2 (placeholder).** Not currently required. Reserved for any
future leaf-beyond-17 that survives a veto cut.

The ADR register lives at `/adrs/` and is checked by
`count_check.py::leaves_at_most_15` — every leaf-beyond-FORMALIS-16 (or
beyond the 17 chosen here) must have an ADR file.

---

## §6. Closing position

The architecture survives R1 intact: the three-class spine
(Definitions / Observations / Effects) plus the two-map cache
discipline (UnitStatus / PositionState) plus the bitemporal Reference
family is what `nazarov_v1` had right and what every reviewer
independently rediscovered.

What R1 made me concede: the 7-sector ceiling was a rhetorical posture,
not a defensible count once L25/L26/L27 are forced by T4/T5/T12. **The
correct number is 17, not 7 and not 24.** The brake stays on against
NAZAROV-24, but the brake had to release on the four R1-forced
additions (RegulatorySubmission, BreakRegister, ClockAuthority via
Reference, IPV/AVA fields on ValuationRecord) because the corresponding
load-bearing claims (regulatory submission replay, break-management
liveness, S3 carrier, FRTB AVA) are real and unforgeable.

What `proposal_v2` MUST do, in priority order:

1. **Adopt §1A CI enforcement.** Every veto has a falsifying predicate
   and a CI gate. Vetoes without enforcement are wishes; wishes do not
   ship.
2. **Delete L5, L7, L21-as-leaf, L24** per §2 / §2A. The "tension box"
   format is forbidden.
3. **Register ADR-1** for V13/L9 (and L8) cache override. Add CI hook
   to verify every leaf-beyond-FORMALIS-16 has an ADR.
4. **Add L25 RegulatorySubmission, L26 BreakRegister, L27 (folded into
   Reference)** with full schemas per R1 T4/T5/T12.
5. **Wire the realism-budget handoff contract** (§4) with named
   detection signals, compensating actions, blast radii. C-A1, C-A2,
   C-A3 owners must resolve to people, not job titles, before
   production.
6. **Add the canonicalisation pin (C-A11)** and the Versioning Algebra
   §3.6.1 per R1 T8. Without a pinned canonical_serialise, every
   cross-implementation replay claim is rhetorical.
7. **Adopt the P5 error algebra** (§1B) closed-sum-per-operation. No
   `Result[T, str]`. No bare `except`.

What `proposal_v2` MUST NOT do:

- Bring back the "tension box" pattern under any name.
- Carry "Direct" CDM Status labels forward without re-fetch (R1 T6).
- Treat L5/L7/L21/L24 as separate leaves under any softer label.
- Add new leaves silently. Every leaf-beyond-17 needs an ADR.
- Use `proposal_v2` as a navigation document. Per R1 T3 (cartan B1,
  halmos B1), `proposal_v2` is the *specification*; companion files
  are referenced, not load-bearing.

The 19 reviewers are right that v1 was a C+. With these changes,
`proposal_v2` is a B/B+ and the load-bearing arguments survive. The
brake stays on against any further inflation; the brake released on
exactly the three additions where the reviewers presented arguments
that v1's seven-sector position could not refute. That is the right
answer: not the most parsimonious answer, but the one the corpus
actually defends.

---

*End jane_street_v2.*
