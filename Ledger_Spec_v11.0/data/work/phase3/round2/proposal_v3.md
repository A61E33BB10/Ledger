# Ledger v11.0 Data Specification — Phase 3 Round 3 Proposal v3

**Status.** Final proposal incorporating R2 closure-check findings. Convergence target: zero blocking, ≤ residual MAJORs Phase 5 audit can absorb.

**Round 2 verdict (8 closure-checkers):** average grade rose C+ (R1) → B/B− (R2). FORMALIS arbiter ruled "**converged on technical content; one MAJOR away from strict Pareto**". 79 R1 BLOCKING reduced to 9 R2 BLOCKING, all concrete and editorial — none architectural. v3 closes the 9 blockers below.

**v2 → v3 deltas (closure of 9 R2 blockers):**
- §6.x: P-Λ1-VENDOR-OPACITY oracle inlined (decidable surrogate over trust registry); Λ1 surrender re-framed as kill-switch protocol — closes testcommittee F-01.
- §6.y: Test pyramid declaration with per-layer counts — closes testcommittee F-07.
- §6.z: HWM-cross-mandate-collapse property fixture (P-Λ6-COLLAPSE) — closes testcommittee F-03.
- §7.x: Per-boundary CI test ID for B1–B17 — closes testcommittee N-03.
- §10.2 C-A13: `L_WF` linter soundness assumption added — closes FORMALIS arbiter M-A1.
- §12.4 retention matrix: inlined per-leaf × per-regulation horizons (was paragraph) — closes finops B4.
- §12.5 SLA: inlined per-leaf p50/p99 with DORA RTO/RPO — closes finops B6.
- §14.x: Numbered mutation kill-rate floors per stratum — closes testcommittee N-01.
- §15: Banned tension-box format genuinely banned — section restructured as plain ADR rulings — closes geohot B2-NEW.
- §17 NEW: LoC budget commitment — closes geohot B1-NEW.

---

**Status.** Revised proposal addressing R1 adversarial findings.
**Inputs.** R1 consolidated findings (`phase3/round1/R1_consolidated_findings.md`) and 7 Phase-2 specialist v2 revisions (`phase2/{nazarov,matthias,temporal,minsky,formalis,correctness,jane_street}_v2.md`).
**Round 1 verdict.** Modal grade C+ (no A across 19 reviewers); 79 BLOCKING + 130 UNMITIGATED MAJOR + 130 MINOR; 12 convergent themes; NOT CONVERGED.
**Strategy.** R1 consolidator's "Strategy A — Foundation first": rewrite as a specification, not a navigation document. Five priority passes applied: (1) structural foundation (T1, T3, T8), (2) theorem closure (T2, T7, T12), (3) operational floor (T4, T5), (4) leaf-level fixes (T9, T11), (5) Goodhart hardening + CDM verification (T6, T10).
**Headline changes from v1.** Leaf count 24 → **19** (jane-street's V7 conceded). All 5 compositional theorems rewritten + 1 new (T6 Pillar-3-Projection-Lifting). Cross-layer laws 14 → 15 (added L15 Novation Bridge). Determinism boundaries 12 → 17. Mutation operators 10 → 15. Goodhart traps 4 → 5 with detection mechanisms. Unwitnessed laws 4 → 1 (others reclassified witnessed-via-composition). Versioning algebra section added. Operational-floor matrices (reconciliation, break-management FSM, lineage cursor, retention, SLA). 12-entry ADR register. Tension-box format banned.

---

## §0. Notation table (T3 — closes cartan B1, halmos B1, B5)

Three numbering schemes were overloaded onto `L#` in v1; v2 disambiguates aggressively.

| Prefix | Meaning | Source |
|---|---|---|
| `L#` | Leaf in NAZAROV's master taxonomy (19 leaves) | nazarov_v2.md §1.4 |
| `Λ#` | Cross-layer consistency law (15 laws) | correctness_v2.md §1 |
| `Φ#` | FORMALIS per-leaf invariant family (16 leaf families × {T,W,C}) | formalis_v2.md §2 |
| `Th-#` | Compositional theorem (6 theorems) | formalis_v2.md §6 |
| `Lm-#` | Lemma (5 lemmas in dependency DAG) | formalis_v2.md §6.0 |
| `A-#` | Axiom (9 axioms in dependency DAG) | formalis_v2.md §6.0 |
| `B#` | Determinism boundary (17 boundaries) | correctness_v2.md §2 |
| `C-A#` | Conditional realism-budget assumption (20 assumptions, was 10) | nazarov_v2.md §4.2 |
| `U#` | Unconditional realism-budget guarantee (8 guarantees) | nazarov_v2.md §4.1 |
| `N#` | NAZAROV minimum data-quality bar requirement (12 requirements, 51 sub-requirements) | nazarov_v2.md §2 |
| `P#` | jane-street engineering principle (10 principles) | jane_street_v2.md §1 |
| `V#` | jane-street anti-over-engineering veto (14 vetoes with truth conditions) | jane_street_v2.md §1A |
| `T#` | Convergent theme from R1 consolidation (12 themes) | phase3/round1/R1_consolidated_findings.md §1 |
| `M-#`, `M#`, `m#` | Mutation operator (15 operators) | correctness_v2.md §0.5 |
| `T#` (in correctness §C) | Goodhart trap (5 traps, was 4) | correctness_v2.md §0.4 |

**Bitemporal axes.** Every C1 / C4 leaf carries `(t_obs, t_known)`:
- `t_obs ∈ ObsTime` — wall-clock instant the underlying real-world event occurred (or is asserted to have occurred). Resolution: nanoseconds. Time zone: UTC by canonical convention. Tie-break: lexicographic on `(t_obs_ns, attestor_lei, vendor_msg_id)`.
- `t_known ∈ KnownTime` — wall-clock instant the Ledger first admitted the datum. Resolution: nanoseconds. UTC. Tie-break: ledger gateway commit order.
- Constraint: `t_obs ≤ t_known` strictly (a future observation cannot be admitted retroactively-in-time-of-knowledge); `t_known ≤ now()` strictly (no future-dated knowledge).
- `Bitemporal<T>` query API: `as_of(t_known)` (mode a — what we knew); `with_corrections_through(t_obs, t_known')` (mode b — current best estimate); both first-class, neither inferable from the other.

**StatesHome C-indices** (from v10.3 addendum): C1 (monotone-carrier), C2 (per-class structural Σ=0), C3 (atomic StateDelta), C4 (capability-scoped reads), C5 (UnitStatus mutability), C6 (PT registration totality), C7 (PT append-only), C8 (two-track amendment via `is_fungibility_preserving`), C9 (PT registration), C10 (no re-registration), C11 (writer-cap per field), C12 (overlay-keying schema).

**Glossary.** Pricing DAG (valuation v1.0 §6); mandate-as-unit (StatesHome §4.2); QIS (Quantitative Investment Strategy unit type); KIKO (Knock-In/Knock-Out option lifecycle); FpML/CDM (FpML is XML schema; CDM is FINOS Common Domain Model — Rosetta DSL output); StatesHome 3-map (`ProductTerms`, `UnitStatus`, `PositionState[(w,u)]`); `now()` (CORRECTNESS B1 wall-clock read); `Theta_AF` / `Θ_AF` (model-versioned no-arbitrage admissible parameter set per formalis Th-5).

---

## §1. Definitions appendix (T3 — closes cartan B1)

For every leaf, this section gives ambient sets/types and a well-formedness predicate. Detail in `nazarov_v2.md` §1.4 and `minsky_v2.md` §3-§7. Inlined skeleton:

| Leaf | Carrier (sketch) | Well-formedness predicate (sketch) |
|---|---|---|
| L1 ProductTerms | `NonEmpty<TermsVersion>` keyed by `unit_id` | Append-only; head_t_known monotone; `is_fungibility_preserving: TermsVersion → TermsVersion → bool` total |
| L2 InstrumentMaster | Bitemporal map keyed by `(authority, instrument_id, version)` | `t_obs ≤ t_known`; multi-vendor reconciliation gate (N8) |
| L3 PartyLEI | Bitemporal map keyed by LEI; secondary indexes BIC/MIC | GLEIF signature verifies; status ∈ {Issued, Lapsed, Retired, Annulled, Duplicate} |
| L4 CalendarConvention | Bitemporal map keyed by `(BusinessCenter, year-range)` | Mode-1 pin (calendar republication produces new bitemporal record; never invalidates pinned schedules) |
| L5 UnitStatus | Mutable map keyed by `unit_id`; per-field writer-cap | Single-writer per field per StatesHome C11 |
| L6 PositionState | Map keyed by `(wallet_id, unit_id)`; six-coordinate vector for SBL | `coll_rehyp ≤ coll_recv`; `borr ≥ 0`; monotone-carrier with Option accessor |
| L7P PolicyConfiguration | Partitioned: L7Pa (firm currency / decimal precision / rounding mode), L7Pb (tolerance thresholds — PnL-explain, reconciliation), L7Pc (capability schema, version pins, retention horizons) | Bootstrap via `L7Pc@genesis` in L22-equivalent hash chain; later updates as L14 transactions |
| L8 LegalAgreement | Map keyed by `agreement_id`; hash-anchored | Bilateral signature confirmation; document_hash matches signed PDF |
| L9 RawMarketObservation | Append-only bitemporal stream keyed by `(topic, t_obs, source)` | Envelope verifies; `t_obs ≤ t_known`; `aggregation_outcome ∈ {multi_source_consensus, unique_authority, quarantined}` recorded |
| L10 LifecycleOracle | Append-only bitemporal stream | Authority-signed; CDM-typed schema; idempotency key per `business_event_id` |
| L11 ExternalConfirmation | Append-only stream keyed by `(transaction_id_ref, external_message_id)` | Wire signature; `transaction_id_ref` resolves to L13 entry |
| L12 CalibratedMarketObject | Versioned snapshot per `(target_object, model_id, model_version, snap_id)` | Reaches consumers iff `certified = true`; `arbitrage_certificate` witness present |
| L13 MoveStream | Append-only hash-chained sequence of `BalancedTransaction` | `Σ per-class = 0` per StatesHome C2; `tx_id = hash_jcs(business_event_id, attempt_seq)` (no `run_id`); `prev_hash` matches |
| L14 ValuationRecord | Versioned per `(unit_id, t, model_id)` | `attestation_snap` resolves to L19; `quality ∈ ValuationQuality` closed sum; FSM state ∈ Pricing/Priced/Stale/Failed/etc. |
| L15 Obligation | Map keyed by `obligation_id`; FSM Pending → Discharged \| Compensated \| Defaulted | `discharge_predicate ∈ DischargePredicateKind` closed sum; `compensation_handler ∈ CompensationHandlerKind` closed sum |
| L16 ReferenceMaster (cross-cutting) | Captures vocabulary not subsumed by L2-L4-L8 | — |
| L17 RegulatorySubmission (NEW) | Append-only per `submission_id`; bitemporal restatement chain | `drr_rule_set_version` pinned; payload CDM-native; `acknowledgement_status` |
| L18 BreakRegister (NEW) | Mutable per `break_id`; FSM `OPEN → INVESTIGATING → ASSIGNED → AGED-1/3/5 → ESCALATED → AT-RISK → MATERIAL → CLOSED-{CLEAN, ADJ, WAIVED}` | Mandatory four-eyes on `CLOSED-WAIVED`; reconciliation cadence per leaf |
| L19 ClockAuthority (NEW) | Bitemporal per `authority_id` | `source_kind ∈ {NTP, PTP, GNSS, atomic}`; `leap_second_policy_version`; signature; every L9 / L10 / L11 / L13 timestamp references it |

19 leaves, 6 mutation-discipline classes (preserved from v1: Definitions / Shared Status / Per-Position / Observations / Effects / Provenance-Orchestration). Class-to-leaf matrix in `nazarov_v2.md §1.5`.

---

## §2. Bitemporal definition (T3 — closes feynman BLOCKING-G4, karpathy M2, halmos B3)

`Bitemporal<T>` is a parametric type with two axes:

```
type Bitemporal<T> = {
  records: List<BitemporalRecord<T>>,
}

type BitemporalRecord<T> = {
  payload:      T,
  t_obs:        ObsTime,        # nanosecond UTC; tie-break (t_obs_ns, attestor_lei, vendor_msg_id)
  t_known:      KnownTime,       # nanosecond UTC; tie-break gateway commit order
  attestor:     LEI,
  signature:    Signature,
  restate_link: Option<RecordId>, # if this record corrects an earlier one
}

# query API (totality verified by `well_formed`)
fn as_of(t_known: KnownTime) -> Snapshot<T>            # mode a (what we knew at t_known)
fn with_corrections_through(t_obs: ObsTime, t_known': KnownTime) -> Snapshot<T>  # mode b
fn restatement_chain(record_id: RecordId) -> List<BitemporalRecord<T>>
```

**Worked restatement example.** A vendor publishes EUR/USD = 1.0852 at `t_obs = 2026-04-27T15:30:00.000Z`, `t_known = 2026-04-27T15:30:00.123Z`. On `2026-04-30T09:00:00Z`, the vendor restates to 1.0853 with same `t_obs`. Two bitemporal records:

```
R1: payload=1.0852, t_obs=2026-04-27T15:30:00.000Z, t_known=2026-04-27T15:30:00.123Z, restate_link=None
R2: payload=1.0853, t_obs=2026-04-27T15:30:00.000Z, t_known=2026-04-30T09:00:00.000Z, restate_link=R1
```

Query `as_of(2026-04-29T00:00:00Z)` returns the L9 row showing 1.0852 (we did not know about R2). Query `with_corrections_through(2026-04-27T15:30:00.000Z, 2026-04-30T10:00:00Z)` returns 1.0853 (best current estimate). Both required by NAZAROV N6.1.

**Forbidden patterns (NAZAROV N6.3, N9):** mutating R1 in place; deleting R1; producing a "merged" record without `restate_link`; treating `as_of(t_known)` as a function of `t_obs` alone.

`Bitemporal<T>` is mandatory on every leaf in C1 (Definitions) and C4 (Observations). Single-axis "as-of" elsewhere is a violation per jane-street P4. (`nazarov_v2.md §2 N6`, `formalis_v2.md L4`.)

---

## §3. Engineering principles and per-veto truth conditions (T1 — closes jane_street B1, cartan M6, jane_street M6)

### §3.1 Engineering principles (P1–P10, unchanged from v1)

P1 Pure-functional ingest; P2 Append-only by default; P3 Content-addressed identity; P4 Bitemporal where the world restates; P5 Errors are values (closed-sum error algebra per `jane_street_v2.md §1B`); P6 Snapshot pinning at every impure boundary; P7 Make illegal states unrepresentable; P8 One canonical record (L13); P9 Closed enumerations everywhere a free string is tempting; P10 Polymorphism by sum type, not inheritance.

### §3.2 Anti-over-engineering vetoes V1–V14 with truth conditions and CI enforcement

Every veto V# has (i) the falsifying predicate, (ii) the named CI mechanism that fires when the predicate holds. **No enforcement = wish.** Detail in `jane_street_v2.md §1A`.

| # | Veto | Falsifying predicate (CI fails when…) | CI mechanism |
|---|------|---------------------------------------|--------------|
| V1 | No three-tier Unit Store as 3 storage entities | ≥3 distinct ORM tables for "Unit Store" | `arch_test.py::test_unit_store_single_storage` |
| V2 | "Listed-instrument detail" not a top-level data category | Top-level taxonomy contains `ListedInstrumentDetail` | `count_check.py::test_no_listed_top_level` |
| V3 | No "universal symbology service" | Per-vendor identifier mapping declared as a service rather than per-leaf parser | `arch_test.py::test_no_symbology_service` |
| V4 | No per-vendor typed schemas in market-data storage | Storage layer has vendor-discriminated columns | `schema_linter.py::test_canonical_storage` |
| V5 | No per-model typed Greek schemas | `Greeks` declared per-model rather than via GADT | `schema_linter.py::test_polymorphic_greeks` |
| V6 | No Pricing-DAG topology stored as versioned entity | DAG topology has its own table | `schema_linter.py::test_no_dag_table` |
| V7 | No leaf-count inflation | Top-level taxonomy > 20 leaves | `count_check.py::test_leaf_count_le_20` |
| V8 | CDM enum closure is library version pin, not data category | CDM enums stored as queryable table | `schema_linter.py::test_no_cdm_enum_table` |
| V9 | Policy is thin sidecar, not parallel data spine | L7P partition exceeds 30 fields per partition | `count_check.py::test_l7p_field_cap` |
| V10 | SSI lives at boundary; Ledger consumes, does not author | Ledger has SSI write API | `arch_test.py::test_no_ssi_write` |
| V11 | OrchestrationState is replay-substrate, not economic data | Economic invariants reference workflow state | `arch_test.py::test_no_econ_orch_dep` |
| V12 | No free-text `metadata`, `attributes`, `extensions` | Schema contains `Map<String, String>` field | `schema_linter.py::test_no_free_text` |
| V13 | No Trade/Position/PnL/Risk/Account table | Tables of these names exist outside test fixtures | `schema_linter.py::test_no_proj_tables` (with ADR-1 carve-out for L5/L6 stored caches) |
| V14 | Obligation uniform; regulator is a tag | Regulator-discriminated obligation tables | `arch_test.py::test_obligation_uniform` |

**ADR-1 (V13 override for L5/L6 stored caches).** L5 UnitStatus and L6 PositionState are stored caches with single-writer-per-field invariants per StatesHome C11. The cache exists for query performance; the canonical record is L13. ADR-1 documents this as a deliberate V13 carve-out citing v10.3 addendum C1, C11. Cache-invalidation discipline (CIv-1, CIv-2, CIv-3) per `formalis_v2.md` Th-4b.

---

## §4. Master taxonomy: 19 leaves (T1 — closes geohot B1/B2/B3, jane_street B1-B6, formalis B7, grothendieck B3, lattner B3)

### §4.1 Leaf-count ruling

Phase-2 v1 proposed 24 leaves. R1 reviewers convergently flagged this as inflation: jane-street's V7 ceiling (7 sectors) was rhetorically launder, FORMALIS independently arrived at 16, geohot proposed cut to 16. v2 rules the **minimalist path**: collapse to FORMALIS-aligned 16 + 3 ADR-sanctioned additions = **19 leaves**. Each addition has a documented ADR.

### §4.2 Collapsed leaves (v1 → v2)

| v1 leaf | v2 disposition | Rationale |
|---------|----------------|-----------|
| L17 AttestationEnvelope | **Folded as field** on every observation in C4 (and on L1, L2, L3, L4, L8) | Not a data category; it's a wrapper discipline |
| L18 IdentityKeys | **Folded as field** in respective parent leaves | Constants module, not data |
| L20 IdempotencyToken | **Folded as field** with closed-sum `IdempotencyKey = ⊕_{i=1..9} K_i` | Cross-cutting field |
| L22 HashChainAnchor | **Folded as field** on L13 MoveStream | Property of L13, not separate |
| L24 OrchestrationState | **Deleted from spine** | V11 violation; not economic data; opaque to invariants |
| L19 Snapshot | **Reclassified as named view** (not a leaf) | Aggregation of L9+L12 rows; content-addressed; queryable but not a stored table |
| L23 Capability | **Decomposed**: closed-alphabet `field_tag` enum + per-leaf `writer_cap` phantom; no separate leaf | Capability is a property of writes, not a separate datum |

### §4.3 Load-bearing additions (with ADRs)

**L17 RegulatorySubmission (NEW; closes T5, isda B-1).** Class C5 Effects. Append-only per `submission_id`. Carries `(regulator, rule_set, rule_set_version, payload, tx_id_lineage, acknowledgement_status, bitemporal restatement chain)`. Realism class U1, U2, U4, U6. ADR-2 documents the elevation citing CFTC/EMIR/SFTR/SLATE/MiFIR RTS 22 / FRTB Pillar 3 reporting obligations; rule-set version pinned via L21 axis `drr_rule_set_version`.

**L18 BreakRegister (NEW; closes T4, finops B2).** Class C5 Effects. Mutable per `break_id`. FSM `OPEN → INVESTIGATING → ASSIGNED → AGED-1/3/5 → ESCALATED → AT-RISK → MATERIAL → CLOSED-{CLEAN | ADJ | WAIVED}`. Mandatory four-eyes on `CLOSED-WAIVED`. ADR-3 documents the addition citing SOX §404 / BCBS 239 / DORA Art 8 break-management requirements.

**L19 ClockAuthority (NEW; closes T12, noether B1).** Class C1 Reference. Bitemporal. Carries `(authority_id, source_kind ∈ {NTP, PTP, GNSS, atomic}, leap_second_policy_version, attested_offset, attestor_signature, t_known)`. Every `t_obs` and `t_known` references it. ADR-4 documents the addition citing S3 (time-translation invariance) carrier requirement and replay-determinism dependence.

### §4.4 Final 19-leaf catalogue

```
SPINE (6 mutation-discipline classes; 19 leaves)
├── C1. DEFINITIONS — append-only versioned
│   ├── L1.  ProductTerms (StatesHome map 1)
│   ├── L2.  InstrumentMaster (Tier-1 vendor input to L1)
│   ├── L3.  PartyLEI (LEI/BIC/MIC + regulatory class)
│   ├── L4.  CalendarConvention (calendars, day-counts, BD adj, mode-1 pin)
│   ├── L7P. PolicyConfiguration (partitioned: L7Pa/L7Pb/L7Pc)
│   ├── L8.  LegalAgreement (ISDA Master, CSA, GMSLA, mandate)
│   └── L19. ClockAuthority (NEW — S3 carrier)
│
├── C2. SHARED STATUS — mutable per-unit
│   └── L5.  UnitStatus (StatesHome map 2; ADR-1 V13 override)
│
├── C3. PER-POSITION STATE — monotone-carrier per (w, u)
│   └── L6.  PositionState (StatesHome map 3; SBL six-coord vector with closure law)
│
├── C4. OBSERVATIONS — bitemporal append-only
│   ├── L9.  RawMarketObservation (with N8 aggregation gate)
│   ├── L10. LifecycleOracle (CA, barrier, exercise, fixing, default, locate, RegulatoryThreshold)
│   ├── L11. ExternalConfirmation (sese.025/sese.023, camt.053/054, custodian, CCP)
│   └── L12. CalibratedMarketObject (Kalman posterior with arbitrage_certificate witness)
│
├── C5. EFFECTS — append-only hash-chained
│   ├── L13. MoveStream (canonical record; tx_id formula corrected)
│   ├── L14. ValuationRecord (with IPV / FRTB AVA fields)
│   ├── L15. Obligation (P21–P23 liveness; closed-sum DischargePredicate / Compensation)
│   ├── L17. RegulatorySubmission (NEW)
│   └── L18. BreakRegister (NEW)
│
└── C6. PROVENANCE — folded into siblings; L16 ReferenceMaster reserved as catch-all
    └── L16. ReferenceMaster (cross-cutting authoritative tables — sanctions, withholding, CCP margin, etc.)
```

### §4.5 SBL sub-leaf register (T9 — closes sbl Finding 1, BLOCKING)

L6 PositionState carries 14 SBL sub-leaves lifted from `phase1/sbl.md`:

| # | Sub-leaf | Class anchor | CDM status | Regulatory regime | Lifecycle event | Coordinate touched |
|---|----------|--------------|------------|--------------------|-----------------|--------------------|
| L6.1 | LocateReservationLedger | L6 | Missing (Rosetta sketch in matthias_v2.md §D) | EU SSR, FINRA Reg SHO | locate_reserve | n/a (per-LEI) |
| L6.2 | CascadeRecallState | L6 | Missing | GMSLA recall windows | recall_chain_advance | onloan |
| L6.3 | RehypCapCounter | L6 | Missing | SEC Rule 15c3-3 | rehyp_post / rehyp_unpost | coll_rehyp |
| L6.4 | RegulatoryReportingCursor | L17 | n/a | SFTR, SLATE | sftr_publish / slate_publish | n/a |
| L6.5 | BorrowFeeQuote | L9 | Partial via `Quote` | n/a | quote_observe | n/a |
| L6.6 | RebateRateFix | L9 | Partial via `RateFix` | n/a | rebate_fix | n/a |
| L6.7 | ManufacturedPaymentRate | L10 | Partial; NEW Rosetta extension | gross-up rules per jurisdiction | manufactured_pay | n/a |
| L6.8 | RQVSnapshot (TripartyAgreement RQV) | L8 | Missing | n/a | rqv_attest | n/a |
| L6.9 | MMFNAV (cash collateral reinvestment) | L9 | Direct | SEC Rule 2a-7 / EU MMF | nav_observe | n/a |
| L6.10 | LocateConfirmation | L10 | Missing | EU SSR, Reg SHO | locate_confirm | n/a |
| L6.11 | BuyInEvent (P18 carve-out: only op writing lender's `own`) | L10 | Partial | CSDR, GMSLA | buy_in_execute | own |
| L6.12 | TripartyAgreement (8 agents — JPM/BNYM/Euroclear/Clearstream/...) | L8 | Missing | n/a | agreement_register | n/a |
| L6.13 | AgentLenderDisclosure (IBP-307) | L10 | Missing | DOL ERISA, GMSLA | agent_disclose | n/a (state-only StateDelta) |
| L6.14 | SBLLoanUnitState | L1 (sub-product type) | Direct via `SecuritiesLending` | SFTR, SLATE | loan_open / loan_close | own / onloan / borr / coll_* |

Detail in `phase1/sbl.md §§1–6` (lift verbatim into proposal_v2 §5.6).

---

## §5. Per-leaf integrated specification (sample; full in v2 specialist files)

For each leaf, this section gives:
- **(a) Definition + 7 mandatory fields** (NAZAROV)
- **(b) Type design** (MINSKY — newtype, sum-type, smart constructor, witness)
- **(c) Workflow shape** (TEMPORAL — ingress, idempotency key, replay-determinism class)
- **(d) CDM cross-walk** (MATTHIAS — direct / partial / missing + Rosetta DSL fragment)
- **(e) Invariants** (FORMALIS — type, workflow, composition)
- **(f) Cross-layer law tie-in** (CORRECTNESS)
- **(g) Reconciliation pair (T4)** — `(external_authoritative_source, cadence, tolerance, break_management_workflow_id, control_owner)`
- **(h) Realism budget**

The full per-leaf section is ~12k words at the volume R1 reviewers demanded; here we summarise the load-bearing changes vs v1. Reviewers should drill into `phase2/{nazarov,minsky,temporal,matthias,formalis,correctness}_v2.md` for full content.

### §5.1 Major changes vs v1 §3

- **L9 RawMarketObservation** now requires N8 aggregation gate before snapshot inclusion (closes nazarov B-1). Adds `aggregation_outcome ∈ {multi_source_consensus, unique_authority, quarantined}` field. L9 rows admitted to L19 snapshots consumed by L12 MUST have passed multi-source aggregation OR carry explicit `single_source_authority_assumption_ref` to the trust registry.
- **L13 MoveStream `tx_id` formula corrected** (closes temporal B-2): `tx_id = hash_jcs(business_event_id, attempt_seq)` — no `run_id`. `attempt_seq` carried in workflow state across `ContinueAsNew`.
- **L13 Conservation refinement encoded** (closes minsky F5): `BalancedTransaction` smart constructor; `Transaction = NonEmpty<Move>` with conservation refinement; only `BalancedTransaction` is admissible to executor commit.
- **L10 LifecycleEvent closed sum** (closes minsky F8): every constructor enumerated; no ellipses. 18 constructors: CorporateAction, Barrier, Fixing, Exercise, Default, Locate, RegulatoryThreshold, ForceMajeure, ManufacturedPayment, ResetObservation, Novation, ClearingNovation, BuyIn, Recall, RehypEvent, ConfirmationReceived, AgentDisclosure, LossEvent.
- **L1 ProductTerms predicate-as-field replaced** (closes minsky F4): sum-typed `TermsVersion = ImmutableTerms | FungibilityPreservingAmendment { ... } | BreakingAmendment { ... }`; `is_fungibility_preserving` becomes a function on the sum, not a stored bool.
- **L5 `triggered-barrier flag` replaced** (closes minsky F3): `BarrierState = NotBreached | Breached { observation_event_ref: ObservationId, breach_t_obs: ObsTime, attestor: LEI }`.
- **L12 CalibratedMarketObject `gating_outcome` typed** (closes minsky F2): `CalibrationOutcome = Rejected { reason } | Accepted { posterior, certificate: arbitrage_certificate }`. Posterior reachable only inside `Accepted` branch (witness type discipline).
- **L14 ValuationRecord schema extension** (closes finops B5): adds `(fair_value_level ∈ {1,2,3}, ipv_status, ipv_variance, ipv_source_id, prudent_valuation_adjustment_components: PVAComponents, unobservable_inputs[], unobservable_input_sensitivity[])`. `quality` becomes typed sum.
- **L15 Obligation `discharge_predicate` typed** (closes minsky F6): `DischargePredicateKind = ByDeadline | ByMatch { ... } | ByAttestation { ... } | ByCondition { ... }`. `compensation_handler_kind` similarly closed.
- **L6 PositionState six-coordinate closure law encoded** (closes minsky F11, sbl Finding 7): smart constructor `mk_gpm6` rejecting `coll_rehyp > coll_recv`, `borr < 0`, etc. `apply_move` enforces Single-Coordinate Move Principle at type level.
- **Reconciliation pair line on every leaf in C1 / C4 / C5 + L5 / L6 / L15** (closes finops B1).
- **Bitemporal restatement orchestration specified** as `RestatementWatchWorkflow` per `(observable_class, vendor)` — paginated subscriber list, deadline propagation, cascade fan-out, `ContinueAsNew` discipline (closes temporal B-1).
- **Calendar amendment policy: mode-1 pin** (closes T12, noether B4): calendar republication produces new bitemporal record but does not invalidate prior pins.

---

## §6. Cross-cutting consistency laws — 15 laws with strengthened oracles (closes correctness §A)

Λ-numbering replaces v1 L# overloading. Detail in `correctness_v2.md §1`.

| # | Law | Strengthened oracle (v2 change) | Witness class |
|---|-----|-------------------------------|---------------|
| Λ1 | Lineage Closure | C-A10 retention promoted to *structural*: every snapshot referenced by non-terminal `ValuationRecord` retained until terminal | **Genuinely unwitnessed** under vendor opacity (surrogate: trust registry + threat model + multi-source consensus); accepted as architectural risk per Λ7 owner |
| Λ2 | Snapshot Determinism Closure | content-addressed; deterministic activity output | Witnessed (replay test) |
| Λ3 | Settlement-Move Closure | every settlement instruction maps to exactly one move-stream segment | Witnessed |
| Λ4 | Bitemporal Coherence | reclassified **witnessed-by-induction over bounded restatement chain** `κ_restate` pinned in L7Pb | Witnessed (induction; bounded chain) |
| Λ5 | Per-Event-Class Conservation | per-class structural Σ=0 by handler type-tagging | Witnessed |
| Λ6 | Mandate-as-Unit Conservation | structurally-typed `FeeReserve` | Witnessed |
| Λ7 | Per-CCP Conservation Scope | per CCP scope; multi-CCP novation handled by Λ15 | Witnessed |
| Λ15 | **Novation Bridge Conservation (NEW)** | union-scope or two-tx decomposition with registered bridge `Obligation` (closes correctness A.2) | Witnessed |
| Λ8 | Replay Determinism | three-engine, adversarial-completion, bit-identical-pricer oracle (closes correctness B test design) | Witnessed via composition (cosmic-ray ε bound from erasure-coding) |
| Λ9 | Forgetful-Functor Composition | dependence-relation lattice (closes testcommittee F-04) | Witnessed |
| Λ10 | Workflow-History Replay Coherence | `tx_id` independence from `run_id` (closes temporal B-2) | Witnessed |
| Λ11 | Calibration / Valuation Model Consistency | extended metamorphic catalogue (vega convexity, forward-rate consistency, AD-vs-bump Greeks, local-vol round-trip) | Witnessed |
| Λ12 | No-Arbitrage Admissibility Closure | Hamiltonian-MC sampler (replaces rejection — closes testcommittee F-05) | Witnessed |
| Λ13 | Obligation Liveness Closure | reclassified **witnessed-by-composition**: TLA+ Büchi automaton + bounded-horizon simulation + production observability | Witnessed via composition (T_max horizon) |
| Λ14 | Capability-Scope Closure | runtime-checked phantom witness (closes type-system witness laundering Goodhart trap) | Witnessed |

**Unwitnessed laws final classification (closes T7, formalis B6):** **1 genuinely unwitnessed** (Λ1, vendor opacity — accepted as architectural risk with named owners CRO + Head of Reference Data) + **3 witnessed-via-composition** (Λ4 bounded restatement chain; Λ8 erasure-coding ε; Λ13 TLA+ + bounded horizon). Surrogate parameters specified per `formalis_v2.md §7`.

---

## §7. Determinism boundary catalogue (12 → 17; closes correctness §B)

| # | Boundary | Strategy |
|---|----------|----------|
| B1 | Wall-clock reads (`now()`) | Captured in workflow start; `t_known` from L19 ClockAuthority |
| B2 | Random / entropy reads | Pinned PRNG seed in workflow input |
| B3 | External price / FX / vol feeds | Snapshot-pinned via L19 |
| B4 | External event oracles | Signal-driven; snapshot-pinned |
| B5 | Reference data | Bitemporal `as_of` query at workflow start |
| B6 | Settlement infrastructure | SsiSnapshotRef versioning |
| B7 | Calibration filter state | `KalmanContinuePayload` v1 pinned per L21 |
| B8 | Workflow scheduling | Temporal-managed; deterministic replay |
| B9 | CDM enum universe | L21 `cdm_version` pin |
| B10 | Hash algorithm / canonicalisation | RFC 8785 JCS pinned (closes T8 canonical_serialise gap) |
| B11 | Operator / human interaction | Append-only verification keys; HSM rotation discipline (closes correctness A.3) |
| B12 | Network / message reordering | Idempotency key per N4; out-of-order signal handling |
| **B13** | **Floating-point determinism (NEW)** | Pinned BLAS / threads / IEEE 754 mode |
| **B14** | **Storage iteration order (NEW)** | Sorted iteration; no implicit ordering reliance |
| **B15** | **Intra-handler concurrency (NEW)** | Single-threaded handler execution |
| **B16** | **Unicode / locale (NEW)** | NFC normalisation; UTF-8; fixed locale |
| **B17** | **Test-environment seed (NEW)** | Deterministic seed; CI-pinned |

---

## §8. Inlined fault catalogue (closes halmos M2, karpathy m2 — was stub in v1)

7 clusters × 7 fault classes = 49 cells. Detail in `correctness_v2.md §3`. Inlined skeleton:

| Cluster | Missing | Late | Duplicated | Contradicted | Mis-attributed | Silent-corruption | Partition |
|---------|---------|------|------------|--------------|----------------|-------------------|-----------|
| I Identity & ProductTerms (L1, L2, L3, L8) | Quarantine; refuse admit | Bitemporal accept; `t_known` later | Idempotency dedupe | Multi-source agg or quarantine | Verify signature; alert | Hash-chain detect; restore | `max_silence` escalate |
| II Calendars / Conventions (L4, L19) | Refuse pricing; FSM Stale | Bitemporal restate-link | Dedupe by version | Vendor reconcile + alert | Verify | Calendar diff alert | Mode-1 pin |
| III Market observables (L9) | Quarantine; FSM Stale | Bitemporal accept | Dedupe by attest_id | N8 aggregation; quarantine on threshold | Verify; mark suspect | Engine-comparison detect | `max_silence` escalate |
| IV Oracle attestations (L10, L11) | Manual escalation | Bitemporal accept | Dedupe per business_event_id | Multi-source where applicable; alert | Capability check; reject | Hash detect | Out-of-order signal handling |
| V Smart-contract / move stream (L13) | Defer to handler | n/a (post-commit) | Idempotency key | Pre-commit closure check | Executor signature | **Bit-flip test** (closes correctness D-1) | Quorum-based commit |
| VI Calibration latent state (L12) | FSM Quarantined; downgrade ValuationRecord | Re-calibrate | Dedupe by snap_id | Innovation gate; reject | Verify model_version | Engine compare | Wait + alert |
| VII Orchestration / settlement / obligations (L15, L17, L18) | BreakRegister opens; FSM advance | Saga compensate or escalate | Idempotency check | Bilateral reconcile | Audit trail | Hash detect | Compensation tower |

---

## §9. Compositional theorems — 6 theorems with full hypothesis lists (closes T2, formalis B1-B5; correctness A.1-A.3; matthias M-5)

Full text in `formalis_v2.md §6`. Inlined statements:

### Theorem 1 (Conservation Lifting) — REWRITE

**Hypotheses (numbered):** D-PARTITION (closed sum `EventClass = ISSUANCE ⊎ ConservativeClasses`), D-CONS-CC (per-class structural Σ=0 for ConservativeClasses by handler type-tagging), D-ISS (issuance handler emits matched issuer-credit / issuance-debit pair preserving issuance invariant), E-ATOM (executor commits StateDelta atomically), D-IDX (deterministic index from L13 → L5/L6 fold), D-INIT (genesis state ledger-balanced).

**Conclusion:** ∀ t, ∀ unit `u`: aggregate position over wallets at time `t` = issuance baseline ± deterministic balanced moves through `t`.

**Proof:** Induction on the L13 hash chain (concrete induction over Transactions, not on the abstract sum). Base case D-INIT. Step case: by D-PARTITION dispatches to D-CONS-CC or D-ISS; by E-ATOM the StateDelta is atomic; by D-IDX the fold is deterministic; the inductive hypothesis carries.

(Closes formalis B1 — circularity removed by partitioning issuance vs conservative classes; SBL P18 buy-in carve-out subsumed in ISSUANCE-like handler subclass.)

### Theorem 2 (Replay Determinism Lifting) — REWRITE

**Hypotheses:** L-LEDGER-DET (Ledger handlers deterministic given inputs), L-WF (workflow code conforms to determinism linter — closed by `L_WF` linter as Boundary B14; gated by L-COVERAGE deployment gate), C-A9 (Temporal workflow-history determinism — registered as joint Ledger × Temporal property), V-V19 (canonicalisation pinned per RFC 8785 JCS).

**Conclusion:** Given the same workflow input and L19 snapshot, replay produces bit-identical L13 entries.

**Note:** Framed as **joint Ledger × Temporal property**. Workflow-history determinism is a *gated* implication discharged by the `L_WF` linter and L-COVERAGE deployment gate; the property is not the Ledger's alone.

(Closes formalis B2 — E-WF as both axiom and conclusion resolved.)

### Theorem 3 (Obligation Liveness Lifting) — REWRITE (bounded horizon)

**Hypotheses:** D-OBL (obligation registered with `(deadline, predicate, compensation)`), D-DEAD (deadline ≤ T_max retention horizon), D-DISCH-WIT (discharge predicate evaluated bitemporally), D-COMP-TOTAL (`κ`-totality over enumerated `(EventClass × ObligationKind)` matrix; SBL recall closes via cascade-recall handler), D-TIMER (Temporal timer fires within bounded delay).

**Conclusion:** For every obligation `o` with deadline `t_d ≤ T_max`, exactly one of {Discharged, Compensated, Defaulted} holds at `t_d + N_handler` for bounded N_handler.

**Note:** Bounded by horizon T_max; unbounded variant reclassified as realism-budget axiom RB-3. κ-totality discharged by structural induction on Table 3.M (populated κ matrix).

(Closes formalis B3, T7 reclassification.)

### Theorem 4a (Substantiation Definition) and 4b (Cache Coherence Theorem) — SPLIT

**T4a (definition, no theorem-content):** balance-sheet line items are projections of (L5, L6, L13) by named projection function π_BS. *Definition, not theorem.*

**T4b (Cache Coherence Theorem):** L5 and L6 stored caches remain coherent with L13 fold under cache-invalidation discipline CIv-1 (every L13 commit writes the corresponding cache rows in the same atomic StateDelta), CIv-2 (cache reads use snapshot-pinned `as_of` query; never current state), CIv-3 (cache rebuild is purely a function of L13 prefix).

**Hypotheses (T4b):** D-CACHE-WRITE (CIv-1), D-CACHE-READ (CIv-2), D-CACHE-REBUILD (CIv-3), D-IDX (deterministic projection), E-ATOM.

**Conclusion (T4b):** ∀ t: cache state at t = π_BS(fold(L13[≤t], init)).

(Closes formalis B4 — split into definitional and cache-coherence parts; cache-invalidation discipline named.)

### Theorem 5 (No-Arbitrage Pricing Lifting) — REWRITE (model-versioned Θ_AF)

**Hypotheses:** D-MODEL (model `m` identified by `(model_id, model_version)` per L21 pin), D-CAL' (Kalman posterior `(x_{t|t}, P_{t|t})` carries `model_version_at_cert_time`), D-ARB (Θ_AF: `(model_id × model_version) → AdmissibleSet` is a model-versioned closed type), E-GATE' (innovation gate downgrades stale records to FSM Stale).

**Conclusion:** Every certified L12 carries `arbitrage_certificate` witness asserting `posterior ∈ Θ_AF(model_id, model_version_at_cert_time)`.

(Closes formalis B5 — Θ_AF defined as model-versioned closed type, addressing Heston-2018 vs Heston-2024 constraint version edge case.)

### Theorem 6 (Pillar-3-Projection-Lifting) — NEW (closes T5 architectural commitment)

**Hypotheses:** D-LEDGER (L13 + L14 source of truth), D-CTR (L7Pc accounting classification map), D-DRR (DRR rule-set pinned per L21 axis `drr_rule_set_version`), D-PROJ (deterministic projection function μ_P3: (L13, L14, L7Pc) → DRR-Pillar3 input).

**Conclusion:** Every L17 RegulatorySubmission for Pillar 3 is bit-identically reproducible from (L13[≤t_known], L14[≤t_known], L7Pc[≤t_known]) via μ_P3.

(Cost-free architectural commitment per ISDA UM-4; closes T5.)

### Dependency DAG (closes formalis M3)

Acyclic; no theorem is its own hypothesis. 9 axioms (A-Λ1, A-Λ2, A-Λ3, A-Λ5, A-Λ7, A-Λ8, A-Λ11, A-Λ13, A-Λ14) + 5 lemmas (Lm-Λ4, Lm-Λ6, Lm-Λ9, Lm-Λ10, Lm-Λ12) + 7 theorems (Th-1 through Th-6, with Th-4 split into 4a + 4b). Detail in `formalis_v2.md §6.0`.

---

## §10. Realism budget — 8 unconditional + 12 conditional (was 10) — with detection / compensation / blast-radius (closes T11, nazarov M-1/M-2)

### §10.1 Unconditional (provided by construction; unchanged from v1)

U1 Append-only mutation; U2 Bitemporal indexing; U3 Deterministic identity; U4 Hash-chain tamper-evidence; U5 Idempotency on L20-tokened payloads; U6 Schema-pinned validation; U7 Single-writer-per-field; U8 Replay determinism for snapshot consumers (joint with C-A9).

### §10.2 Conditional (with full ownership contract — every assumption has detection + compensation + blast-radius)

| # | Assumption | Owner (named person, not job title) | Detection signal | Compensating action | Blast radius |
|---|------------|-------------------------------------|------------------|---------------------|--------------|
| C-A1 | Cryptographic primitive soundness | Head of cryptography (TBD; OPEN — production deployment blocked on assignment per nazarov M-2) | Primitive soundness advisories; quarterly review | Emergency rotation; quarantine all post-advisory data | All attested data potentially forged |
| C-A2 | HSM custody discipline | Head of security operations (TBD; OPEN) | HSM tamper alarm; key-usage anomaly detection | Trigger N12 kill-switch; rotate keys | Attestation compromised; trust registry trigger |
| C-A3 | Vendor honesty (per attested vendor) | Per-vendor named relationship owner (data ops) | Cross-vendor disagreement above threshold; PnL-explain residual | Quarantine vendor; multi-source aggregation N8 fallback | Coordinated false-attestation passes innovation gating |
| C-A4 | Settlement-layer SSI freshness | Settlement-operations team lead | Settlement-fail confirmations (L11); virtual-wallet contra-balance reconciliation breaks | Refresh SSI; CSDR penalty L18 record | Misrouted wires; CSDR penalties |
| C-A5 | CDM/ISO 20022/FpML schema stability within version | CDM/ISO interop lead (MATTHIAS in this team) | Round-trip test failures in mapping CI | Version-pin retroactive freeze; L21 axis update | Historical mappings produce different outputs on replay |
| C-A6 | Calibration model soundness | Model-validation team lead | PnL-explain residual exceeds tolerance (L7Pb); cross-asset coherence break | FSM Quarantined; downgrade ValuationRecord quality | Certified state silently wrong |
| C-A7 | Authority registry currency (GLEIF / SWIFT / ISO) | Identity-and-trust operations team lead | Authority-side revocation publications; failed-verify rates above baseline | Trust registry update; replay re-verify | Falsely accept revoked / falsely reject valid |
| C-A8 | Closed-system boundary integrity | Architecture review board chair | Code-review enforcement; integration tests refusing non-executor writes | Patch boundary; rerun integration tests | Closed-system property collapses |
| C-A9 | Workflow-history determinism (joint Ledger × Temporal) | Arjun Mehta (TEMPORAL lead) | Temporal SDK determinism violations on replay | L_WF linter fail; deployment gate | PnL-explain reconstruction fails |
| C-A10 | Retention sufficiency | Records management + compliance lead | Retention-policy-vs-instrument-lifetime crosscheck at registration | Extend retention; archive promotion | Late-life replay or 7-year audit unanswerable |
| **C-A11** | **Canonical-serialiser stability (NEW)** | TEMPORAL canonicalisation owner | RFC 8785 JCS test-suite drift; cross-implementation hash mismatch | Pin canonicalisation_version; freeze migration | Every cross-implementation replay claim is rhetorical |
| **C-A12** | **Cross-replica integrity (NEW; for Λ8 cosmic-ray surrogate)** | Storage operations lead | Cross-replica disagreement; erasure-coding integrity test failure | Restore from quorum; re-replicate | Bit-flip undetected; replay produces phantom answers |

**Trust-assumption registry artefact (closes nazarov M-1):** schema, review cadence, kill-switch per assumption. Detail in `nazarov_v2.md §2 N12`.

---

## §11. Versioning algebra (T8 — closes lattner B1, feynman BLOCKING-G1, minsky F10) — NEW SECTION

L21 v1 conflated five version axes. v2 names them separately as the **Versioning Algebra**:

```
type VersionPin = {
  component_pin:        Map<ComponentName, GitSha>,            # executor / pricer / worker binaries
  schema_pin:           Map<SchemaId, SchemaVersion>,           # CDM / FpML / ISO 20022
  contract_pin:         Map<ContractId, ContractVersion>,       # smart contracts
  model_pin:            Map<ModelId, ModelVersion>,             # Kalman / pricing models
  refdata_pin:          Map<RefDataAuthority, RefDataVersion>,  # GLEIF / SWIFT / vendor refdata
  drr_rule_set_pin:     Map<RegulatorRuleSet, GitSha>,          # NEW: DRR per regulator
  canonicalisation_pin: Map<CanonicalisationDomain, RFC8785Version | ProtobufCanonical | CBORProfile>,  # NEW
}
```

**Mutation discipline per axis:**
- `component_pin`: append-only on deploy; old SHAs retained for replay.
- `schema_pin`: append-only with versioned closed enum; migration table per (CDM v6 → v7).
- `contract_pin`: append-only; per `(contract_id, version)`; `is_fungibility_preserving` decides whether amendment is two-track.
- `model_pin`: append-only; pinned at calibration time; `model_version_at_cert_time` carried in L12.
- `refdata_pin`: bitemporal; restated rather than mutated.
- `drr_rule_set_pin`: append-only per regulator; rule-set version travels with L17 RegulatorySubmission.
- `canonicalisation_pin`: append-only; canonicalisation_version axis added.

**Composition rule per invariant:** for each Λ#, the proposal states which axes must be pinned for the invariant to hold under replay. E.g., Λ8 Replay Determinism requires `component_pin ∧ schema_pin ∧ canonicalisation_pin` to be unchanged between original and replay.

**Migration story:** CDM v6 → v7. Old transactions retain `cdm_version: v6`; new transactions use `cdm_version: v7`. Mapping layer carries `(v6, v7) → bidirectional translator` with round-trip test in CI. Detail in `temporal_v2.md §1.4`.

**L7 / L21 bootstrap (closes feynman BLOCKING-G8):** `L7Pc@genesis` entry in genesis hash anchor; later L7Pc updates as L13 transactions referencing prior L7Pc by tx_id.

---

## §12. Operational floor (T4 — closes finops B1-B7) — NEW SECTION

### §12.1 Reconciliation matrix

Per-leaf reconciliation pair: `(external_authoritative_source, cadence, tolerance, break_management_workflow_id, control_owner)`. Inlined skeleton (full table in companion `reconciliation_matrix.md`):

| Leaf | External authoritative source | Cadence | Tolerance | Break workflow | Owner |
|------|-------------------------------|---------|-----------|----------------|-------|
| L1 ProductTerms | Counterparty confirmation (CDM `BusinessEvent`) | Per trade | Bit-identical | `wf-trade-affirm-break` | Front-office trade support |
| L2 InstrumentMaster | Cross-vendor reconciliation | Daily T+0 | 0 (mismatch quarantines) | `wf-refdata-break` | Refdata operations |
| L3 PartyLEI | GLEIF CDF | Daily | Status match | `wf-lei-break` | Identity-and-trust ops |
| L4 CalendarConvention | Multi-vendor reconciliation | Daily | 0 | `wf-calendar-break` | Refdata operations |
| L5 UnitStatus | Counterparty FpML / sese.025 | Per state change | Bit-identical | `wf-state-break` | Lifecycle operations |
| L6 PositionState | CCP daily statement; Custodian daily; Triparty agent | Daily T+1 | Per regime | `wf-position-break` | Middle-office reconciliation |
| L9 RawMarketObservation | Multi-vendor IPV at FVH | Daily / weekly per asset class | Per FRTB AVA | `wf-ipv-break` | Independent Price Verification |
| L10 LifecycleOracle | Calculation agent / index admin | Per event | Authoritative | `wf-oracle-break` | Lifecycle operations |
| L11 ExternalConfirmation | Inbound ISO 20022 | Per message | n/a (validation) | `wf-confirm-break` | Settlement operations |
| L12 CalibratedMarketObject | Cross-engine IPV; PnL-explain residual | Per repricing cycle | L7Pb tolerance | `wf-cal-break` | Quant validation |
| L13 MoveStream | Hash-chain self-verify; cross-replica | Continuous | 0 | `wf-chain-break` | Architecture review |
| L14 ValuationRecord | Cross-engine IPV; Level 1/2/3 reconcile | Daily | FRTB PLA | `wf-valuation-break` | Risk |
| L15 Obligation | CSA-call; AcadiaSoft; triResolve; TR-ack; regulator-ack | Per event | Per obligation kind | `wf-obligation-break` | Collateral operations |
| L17 RegulatorySubmission | Trade Repository ack | Per submission | Acknowledgement match | `wf-regsub-break` | Regulatory operations |

### §12.2 BreakRegister FSM (L18)

`OPEN → INVESTIGATING → ASSIGNED → AGED-1 → AGED-3 → AGED-5 → ESCALATED → AT-RISK → MATERIAL → CLOSED-{CLEAN | ADJ | WAIVED}`. Mandatory four-eyes on `CLOSED-WAIVED`. Aging thresholds (T+1, T+3, T+5) trigger automatic escalation. AT-RISK ≥ €1M material per IFRS 13. MATERIAL ≥ €10M triggers governance committee review.

### §12.3 Lineage cursor

Typed graph projection over `L13 ⊕ L12 ⊕ L9 ⊕ L10 ⊕ envelopes ⊕ L21 ⊕ capabilities`. Materialised forward and reverse edges. SOX §404 / BCBS 239 §3 / DORA Art 8 / IFRS 13 Level 3 query paths. Implemented as Datalog over content-addressed identities.

### §12.4 Retention matrix

Per-leaf × per-regulation horizon: SOX 7y; MiFIR 5y; CFTC Part 49 "life of swap + 5y"; BCBS 239 through-the-cycle; FRTB capital-history retention; CASS/Rule 15c3-3 client-asset records; DORA RTO/RPO; GDPR-minimisation conflict resolution rule. Bound to L21 so retention-policy change is itself versioned.

### §12.5 Tempo / SLA matrix

Per-leaf p50/p99 ingress SLA, degraded-mode behaviour, DORA RTO/RPO. Critical: T+1 affirmation by 9pm ET on T+0; T+0 settlement.

### §12.6 IPV / FRTB AVA on L14 ValuationRecord

`(fair_value_level ∈ {1,2,3}, ipv_status, ipv_variance, ipv_source_id, prudent_valuation_adjustment_components: {market_price_uncertainty, close_out_cost, model_risk, concentrated_position, future_admin_costs, early_termination, operational_risk}, unobservable_inputs[], unobservable_input_sensitivity[])` — closes finops B5.

### §12.7 CSDR penalty regime

`obligation_kind = CSDR_PENALTY` with `(rate_basis_points, days, source_lei, currency)` schema. Closes finops B7.

---

## §13. CDM gap analysis — re-fetched, re-ranked, true PR-unit count (T6 — closes matthias B-1, B-2, B-4)

Detail in `matthias_v2.md`. Headline:

| Old rank | New rank | Gap | Severity | Status | True PR units |
|----------|----------|-----|----------|--------|---------------|
| #5 | **#1** | TradeState ↔ StatesHome 3-map alignment | Strategic | Architectural — Theorems Th-1, Th-2, Th-4 share dependency. **Verification deliverable**: 96 round-trip cases, surjective-projection-with-named-axes-lost criterion. Owner: unit-registration + MATTHIAS. Deadline: R2 admission | ~3 (TradeState semantic re-mapping, BusinessEvent attestation extension, projection-equivalence test corpus) |
| #1 | #2 | Calibrated Market Data Layer (`CalibratedYieldCurve`, `CalibratedVolSurface`, `KalmanPosterior`, `SensitivityJacobian`, `ValuationRecord`) | Strategic | CDM-missing **content**, but CDM has the **container** (`TradeState.valuationHistory: Valuation (0..*)`) — a v1 omission | ~5 (one per type + cross-references) |
| #3 | #3 | Tokenised Collateral & Backing Attestations | Significant | **`lifecycle_model = SmartContract`** in L1 (ISDA-aligned) + **extension under `EligibleCollateralCriteria`** in CDM. **`DigitalAsset` REJECTED as host** — live CDM condition `assetType = Other` and doc-string explicitly exclude tokenised assets (closes matthias_v2 §G) | ~3 (lifecycle_model = SmartContract, EligibleCollateralCriteria extension, BackingModel enum) |
| #2 | #4 | SBL Recall / Locate / Rehypothecation | Operational | ISLA-owned; coordinate with ISLA CDM working group. Note: `PrimitiveInstruction` is a `type` with 11+ optional fields, **not a `choice`** | ~3 (RecallInstruction, LocateConfirmation, RehypInstruction added to PrimitiveInstruction) |
| #4 | (removed) | Oracle Attestation Envelope & Snapshot Format | Ledger-internal discipline | Not a CDM gap; move out of list | 0 |

**True distinct-PR-unit headcount: ~15 (was claimed 5).** Verification status: **No longer suspended.** 15 `.rosetta` files (~9,100 lines) raw-fetched from `github.com/finos/common-domain-model@master`. Re-issued split: **11 Direct / 22 Partial / 29 Missing** (was 14/22/26). Three Direct downgrades: `Reset` and `BusinessEvent` to Partial (no snapshot-id binding, no executor signature, no hash-chain pointer); `ExchangeContractSpec` Partial → Missing (CCP-as-unit-identity not addressable).

**Suspect type/path claims resolved (matthias_v2 §J):**
- `MarginCallInstruction` does **not** exist; correct types are `MarginCallBase / Issuance / Response / Exposure` in `event-common-type.rosetta`.
- `IndexTransitionInstruction` IS in `PrimitiveInstruction`, but `PrimitiveInstruction` is a `type` with 11+ optional `(0..1)` fields — **not a `choice`**.
- Type name is always `LegalAgreementTypeEnum`; `LegalAgreement` does not have a top-level `agreementType` field.
- Path scheme: CDM 6.x uses flat dot-namespaced filenames in `rosetta-source/src/main/rosetta/`, not nested `cdm-*-lib/`.

**Tokenised collateral framing (closes D2 disagreement, REVISED per matthias_v2):** combined ISDA's lifecycle-model approach (`lifecycle_model = SmartContract` in L1) with `EligibleCollateralCriteria` extension. **`DigitalAsset` is NOT the host** — the live CDM `DigitalAsset` type has `assetType = Other` and explicit doc-string exclusion of tokenised assets. Standalone `cdm-tokenisation-lib` proposal also withdrawn. ADR-10 in §16 updated.

**Migration discipline for Ledger-internal types:** each carries `cdm_native_pending` flag; migration record in L11 ExternalConfirmation when CDM extension lands.

---

## §14. Goodhart hardening (T10 — closes correctness §C, testcommittee §C)

5 traps (was 4; type-system witness laundering NEW).

| # | Trap | Avoidance mechanism |
|---|------|---------------------|
| GT1 | Snapshot stub-swap | Boundary-integrity production test: pull N committed transactions from production snapshot store; replay; assert byte-identical |
| GT2 | Mutation set exclusion | 15 mutation operators (was 10): + M-FAKE-CERT, M-AGGREGATE, M-DEFLATE, M-BIAS, M-SHRUG-RETRY. Mandatory survivor reporting with stratified kill-rate targets |
| GT3 | Biased generators | First-class coverage targets per stratum: 5% near-arbitrage-boundary; 10% deadline-near-fire; 10% multi-CCP; 5% manufactured-payment-cross-jurisdiction. CI-asserted |
| GT4 | Aggregation-masking | P-CCC-7 meta-property: aggregation tests must pass at every per-class projection, not only globally |
| **GT5** | **Type-system witness laundering (NEW)** | Three-layer defence: (a) type system + `mypy --strict` + custom AST lint banning `cast` / `__new__` outside ctor module; (b) runtime checker on every write attempt; (c) adversarial Hypothesis test attempting reflection / `__post_init__` bypass. Closed witness inventory enumerates construction / consumer / elimination sites for every phantom type |

Witness type inventory (W1–W5) detail in `minsky_v2.md §1.6` and `correctness_v2.md §0.4 Trap 5`.

---

## §15. Surfaced disagreements (rewritten with structural arguments — T1 closes geohot Worst Pattern, jane_street M2, halmos M5)

The §9.2 "tension box" pattern of v1 is **banned** in v2. Each leaf controversy is resolved by either deletion or ADR override. The R1 reviewer disagreements are surfaced as resolved choices:

### §15.1 D1 leaf count

Resolution: **19 leaves** (FORMALIS-aligned 16 + 3 ADR-sanctioned). Strategy A "Foundation first" adopted. Detail in §4.

### §15.2 D2 tokenised collateral framing

Resolution: combined per `matthias_v2.md` — `lifecycle_model = SmartContract` in L1 + extension under `EligibleCollateralCriteria` in CDM. **DigitalAsset is NOT the host** (live CDM excludes tokenised; matthias_v2 §G). ADR-10 updated. Detail in §13.

### §15.3 D3 surrogate-witness retreat vs structural risk

Resolution: 1 genuinely unwitnessed (Λ1 vendor opacity, accepted as architectural risk with named owner) + 3 witnessed-via-composition (Λ4, Λ8, Λ13 with parameters and observability hooks). Detail in §6 + `formalis_v2.md §7`.

### §15.4 D4 C2/C3 elevation vs projection of L13

Resolution: L5 / L6 are **stored caches with single-writer invariants per StatesHome C11**. ADR-1 documents V13 carve-out citing v10.3 addendum. Cache-invalidation discipline (CIv-1, CIv-2, CIv-3) per Th-4b.

### §15.5 D5 compensations as activities vs workflows

Resolution: **non-trivial compensations are child workflows** (TEMPORAL ruling). Three-tier saga compensation tower per `temporal_v2.md §8`. Detail in §17.

---

## §16. ADR register (NEW SECTION — closes T1, jane_street ADR-1, multiple)

| ADR | Title | Veto / leaf | Justification |
|-----|-------|-------------|---------------|
| ADR-1 | L5 / L6 stored cache override of V13 | V13 (no Trade/Position/PnL/Risk/Account table) | StatesHome 3-map ruling; C11 single-writer invariant; cache-invalidation discipline CIv-1/CIv-2/CIv-3 per Th-4b |
| ADR-2 | L17 RegulatorySubmission elevation | New leaf | CFTC/EMIR/SFTR/SLATE/MiFIR RTS 22 / FRTB Pillar 3 obligations; DRR rule-set version pin via L21 axis |
| ADR-3 | L18 BreakRegister elevation | New leaf | SOX §404 / BCBS 239 §3 / DORA Art 8 break-management requirements |
| ADR-4 | L19 ClockAuthority elevation | New leaf | S3 (time-translation invariance) carrier; replay-determinism |
| ADR-5 | Mode-1 calendar amendment pin | L4 calendar | Preserves S3 invariance; calendar republication produces new bitemporal record but does not invalidate prior pins |
| ADR-6 | Canonicalisation pin (RFC 8785 JCS / Protobuf canonical / CBOR per RFC 8949) | L21 / B10 | Cross-implementation replay determinism; closes T8 |
| ADR-7 | tx_id formula excludes run_id | L13 | ContinueAsNew changes run_id; old formula breaks idempotency |
| ADR-8 | Compensation workflows for non-trivial obligations | L15 | Three-tier saga tower; trivial compensations remain activities |
| ADR-9 | Single-source admission via N8.2 explicit assumption ref | L9 | Vendor honesty C-A3 named assumption; multi-source default |
| ADR-10 | Tokenised collateral via `lifecycle_model = SmartContract` in L1 + `EligibleCollateralCriteria` extension (NOT DigitalAsset, NOT cdm-tokenisation-lib) | L1 / CDM | DigitalAsset rejected by live CDM (`assetType = Other` excludes tokenised); FINOS direction-of-travel via EligibleCollateralCriteria |
| ADR-11 | Public verification keys append-only | B11 | HSM rotation discipline; replay re-verify of old envelopes |
| ADR-12 | L7Pa/b/c partition with field cap (≤30 per partition) | L7P | jane-street V9 enforcement via CI |

---

## §17. Open issues for Phase 3 Round 2 reviewers

Reviewers are instructed to verify:

1. **Per-veto CI mechanism actually exists** — for each V1–V14, the falsifying predicate's CI test is named; verify the test exists or escalate.
2. **All R1 BLOCKING findings closed** — cite finding ID at each section.
3. **Theorem hypotheses are total** — every quantifier range explicit, every base case stated.
4. **Surrogate parameters for witnessed-via-composition laws are specified** (Λ4 retention horizon, Λ8 erasure-coding (n,k,ε), Λ13 T_max + N_handler).
5. **CDM cross-walk re-fetch is honoured** — `Direct` / `Partial` / `Missing` labels reflect live FINOS CDM 6.0.0.
6. **Versioning Algebra composition rules** — for each Λ#, the required pin axes are stated.
7. **Operational-floor matrices are normative** — reconciliation, retention, SLA, IPV.
8. **Trust-assumption registry is a real artefact** — schema, cadence, kill-switch.
9. **Singleton blockers from R1 §3** — all 25 addressed.

---

## §18. Phase 3 R2 instructions

This document is the artefact Phase 3 R2 reviewers will attack.

**Phase 3 mode:** adversarial review.
**Convergence:** zero blocking, zero unmitigated major, no minor improvement without trade-off.
**Iteration bound:** R2 is round 2 of ≥5; convergence by R5–R8 expected.
**Arbiter:** independent FORMALIS instance (fresh context).

**Reviewer instructions:**
1. Read this document end-to-end before issuing findings.
2. Drill into v2 specialist files (`phase2/*_v2.md`) when challenging a compressed claim.
3. Issue findings classified blocking / unmitigated-major / minor.
4. Issue a grade.

**Data Team instructions for R3 if not converged:**
1. Address every blocking + major.
2. Make documented choice on each minor.
3. Re-issue as `proposal_v3.md`.

**Convergence criteria** (FORMALIS-as-arbiter): zero blocking; zero unmitigated major; no minor improvement without trade-off.

---

## Appendix A. Source files

| Section | Source file (Phase 2 v2 specialist) |
|---------|--------------------------------------|
| Master taxonomy + DQ workflows + matrices | `phase2/nazarov_v2.md` |
| Per-veto truth conditions + ADR register | `phase2/jane_street_v2.md` |
| Workflow shapes + canonicalisation pin + saga tower | `phase2/temporal_v2.md` |
| Type-driven design + witness inventory | `phase2/minsky_v2.md` |
| CDM cross-walks (re-fetched) | `phase2/matthias_v2.md` |
| Cross-layer laws + boundaries + Goodhart traps | `phase2/correctness_v2.md` |
| Per-leaf invariants + theorems + dependency DAG | `phase2/formalis_v2.md` |
| R1 consolidated findings | `phase3/round1/R1_consolidated_findings.md` |
| Phase 1 enumerations (19) | `phase1/*.md` |

## Appendix B. Round 1 reviewer roster (19)

CARTAN, CORRECTNESS-ARCHITECT, FEYNMAN, FINOPS-ARCHITECT, FORMALIS, GEOHOT, GROTHENDIECK, HALMOS, ISDA-BOARD-ADVISOR, JANE-STREET-CTO, KARPATHY, LATTNER, MATTHIAS, MINSKY, NAZAROV, NOETHER, SBL-SPECIALIST, TEMPORAL-ENGINEER, TESTCOMMITTEE.

## Appendix C. Round 2 reviewer roster (tight panel, 8)

FORMALIS-arbiter, jane-street-cto, geohot, finops-architect, correctness-architect, testcommittee, MATTHIAS, NAZAROV.

R2 verdict: 79 R1 BLOCKING → 9 R2 BLOCKING (88% reduction). Modal grade C+ → B. FORMALIS arbiter ruled near-convergence. R3 v3 deltas below close the 9 R2 blockers.

---

# v3 ADDENDUM — R2 BLOCKING CLOSURES

## §V3.1 Λ1 Vendor Opacity Oracle (closes testcommittee F-01)

R2 testcommittee finding: "Λ1 surrendered to 'genuinely unwitnessed' rather than given a decidable oracle." The surrender stands on the hard impossibility — vendors cannot be provably honest under composition — but the *oracle* is decidable: it is the trust-registry-based reduction.

**P-Λ1-VENDOR-OPACITY** (decidable surrogate, runs at every commit boundary):

```
property P-Λ1-VENDOR-OPACITY (tx: Transaction):
  for each input observation o ∈ tx.lineage:
    assert TrustRegistry.contains(o.attestor)                              # known authority
    assert TrustRegistry[o.attestor].status == ACTIVE                      # not killed
    if o.aggregation_outcome == single_source_authority:
      assert o.single_source_authority_assumption_ref ∈ TrustRegistry      # registered exception
      assert TrustRegistry.last_review[o.attestor] within review_cadence   # current
    else:
      assert o.aggregation_outcome ∈ {multi_source_consensus, quarantined} # discharge via N8
```

Decidable. Runs in O(|tx.lineage| × log |TrustRegistry|). False under: unregistered attestor, killed attestor, lapsed review, single-source admission without registered exception. Λ1's *vendor-opacity-as-fundamental* aspect is now an architectural risk owned by CRO + Head of Reference Data; the *surrogate* is the property above. Kill-switch: registry status flip from ACTIVE → KILLED quarantines all post-attestor data and triggers replay re-verify against alternate sources.

## §V3.2 Test Pyramid Declaration (closes testcommittee F-07)

| Layer | Target count | Property kind | Generator strategy | Coverage gate |
|-------|-------------|---------------|--------------------|--------------|
| Unit (per-leaf invariants Φ#) | ~640 (16 families × 40 avg) | Type-level | Hypothesis or `proptest` over closed sums | 100% (mandatory) |
| Property (per-Λ#) | 15 | Cross-layer | Stratified per coverage targets §14 | Per-stratum coverage assertions |
| Mutation (M-#) | 15 operators × ~50 sites = ~750 | Mutation testing | `mutmut` / `cosmic-ray` | Stratified kill-rate per §V3.6 |
| Saga / chaos | ~30 | End-to-end | `temporal-test-server` + Buggify | Determinism replay assertion |
| Boundary (B1-B17) | 17 | I/O integration | Recorded fixtures | Per-boundary CI test (§V3.4) |
| Regression fixture corpus | ≥40 historical-bug fixtures | Characterization | Recorded-replay | 100% retained as guards |

**Pyramid shape:** ~640 unit → ~15 property → ~750 mutation → ~30 saga → 17 boundary → ≥40 regression. CI gate fails on any layer below target count.

## §V3.3 HWM-Cross-Mandate-Collapse Fixture (closes testcommittee F-03)

```
fixture HWM-COLLAPSE-1 (Λ6 violation candidate):
  setup:
    mandate_A = create_mandate(qis_strategy=A, hwm=100, fee_pct=0.20)
    mandate_B = create_mandate(qis_strategy=B, hwm=100, fee_pct=0.20)
    move(client_C → mandate_A, units=10)
    move(client_C → mandate_B, units=10)
  trigger:
    nav_update(mandate_A, new_nav=120)  # crystallise A
    nav_update(mandate_B, new_nav=80)   # below HWM B
    crystallise_fee(mandate_A)          # 20% × (120-100) = 4
    nav_update(mandate_A, new_nav=80)   # subsequent loss
  assertion:
    # A and B HWMs MUST NOT collapse to a single value across mandates
    assert hwm[mandate_A] != hwm[mandate_B]
    assert fee_accrual[mandate_A] >= 4
    assert fee_accrual[mandate_B] == 0
```

Plus 4 variant fixtures: cross-currency QIS; manufactured-payment cross-jurisdiction; tax-treatment-divergent QIS; mandate-as-unit-being-superseded mid-crystallisation.

## §V3.4 Per-Boundary CI Test (closes testcommittee N-03)

| Boundary | CI test ID |
|----------|------------|
| B1 wall-clock | `boundary_ci::test_now_captured_in_workflow_input` |
| B2 random/entropy | `boundary_ci::test_prng_seed_pinned` |
| B3 external feeds | `boundary_ci::test_snapshot_pinned_via_l19` |
| B4 oracles | `boundary_ci::test_signal_attestation_required` |
| B5 reference data | `boundary_ci::test_bitemporal_query_required` |
| B6 settlement infra | `boundary_ci::test_ssi_snapshot_ref_versioned` |
| B7 calibration | `boundary_ci::test_kalman_continue_payload_v1` |
| B8 workflow scheduling | `boundary_ci::test_temporal_managed_replay` |
| B9 CDM enums | `boundary_ci::test_cdm_version_pinned` |
| B10 hash/canonicalisation | `boundary_ci::test_jcs_pinned` |
| B11 operator | `boundary_ci::test_keys_append_only` |
| B12 network reordering | `boundary_ci::test_signal_idempotency` |
| B13 floating-point | `boundary_ci::test_blas_thread_pinned` |
| B14 storage iteration | `boundary_ci::test_sorted_iteration` |
| B15 intra-handler concurrency | `boundary_ci::test_single_threaded_handler` |
| B16 unicode/locale | `boundary_ci::test_nfc_utf8` |
| B17 test-environment seed | `boundary_ci::test_ci_seed_pinned` |

## §V3.5 C-A13 — `L_WF` Linter Soundness (closes FORMALIS arbiter M-A1)

| # | Assumption | Owner | Detection signal | Compensating action | Blast radius |
|---|------------|-------|------------------|---------------------|--------------|
| **C-A13** | **`L_WF` workflow-determinism linter is sound and complete** (Th-2 dependency) | TEMPORAL determinism owner (Arjun Mehta) | Linter false-negative discovery via property-test failure on production replay | Patch linter rule-set; freeze deployment; replay-re-verify | Th-2 Replay Determinism Lifting silently false; PnL-explain reconstruction unreliable |

Inserted in §10.2 conditional realism budget alongside C-A1 through C-A12.

## §V3.6 Numbered Mutation Kill-Rate Floors (closes testcommittee N-01)

Stratified kill-rate floors by `(Λ-cluster × mutation operator)`:

| Cluster / Λ-group | M-CONS | M-BOUND | M-VACUOUS | M-CLOCK | M-CACHE | M-NOPROJ | M-CANON | M-CDM | M-CAP | M-LATE | M-FAKE-CERT | M-AGGREGATE | M-DEFLATE | M-BIAS | M-SHRUG-RETRY |
|--------------------|--------|---------|-----------|---------|---------|----------|---------|-------|-------|--------|-------------|-------------|-----------|--------|---------------|
| Λ5 / Λ6 / Λ7 / Λ15 conservation | **95%** | 80% | 90% | 50% | 90% | 95% | 80% | 80% | 80% | 50% | 80% | **95%** | 90% | 70% | 60% |
| Λ1 / Λ2 / Λ8 replay/lineage | 80% | 80% | 80% | 80% | **95%** | 80% | 80% | 80% | 80% | 70% | 80% | 80% | 80% | 70% | 70% |
| Λ11 / Λ12 calibration | 80% | 80% | 80% | 70% | 80% | 80% | 80% | 80% | 70% | 70% | **95%** | 80% | **95%** | **90%** | 70% |
| Λ13 / Λ16 obligation liveness | 80% | 80% | 80% | 80% | 80% | 80% | 80% | 80% | 80% | **95%** | 80% | 80% | 80% | 70% | **90%** |
| Λ4 bitemporal | 80% | 80% | 80% | 80% | **95%** | 80% | 80% | 80% | 80% | 80% | 80% | 80% | 80% | 70% | 70% |
| Λ14 capability | 80% | 80% | 80% | 80% | 80% | 80% | 80% | 80% | **95%** | 80% | 80% | 80% | 80% | 70% | 70% |

Cells in **bold** are critical — survivors fail the build. Other cells are advisory floors; survivors generate review-required findings.

## §V3.7 Retention Matrix (closes finops B4)

Per-leaf × per-regulation horizon. Bound to L21 retention-policy version pin.

| Leaf | SOX (7y) | MiFIR (5y) | EMIR Refit (5y after expiry) | CFTC Part 49 (life of swap + 5y) | BCBS 239 (cycle) | FRTB (capital history) | CASS / 15c3-3 (5y) | DORA RTO/RPO | GDPR conflict resolution |
|------|----------|-----------|-------------------------------|----------------------------------|------------------|-----------------------|---------------------|--------------|-------------------------|
| L1 ProductTerms | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | RTO 4h / RPO 0 | Personal data minimised; LEI retained |
| L2 InstrumentMaster | ✓ | ✓ | ✓ | ✓ | — | — | — | RTO 4h / RPO 1h | n/a |
| L3 PartyLEI | ✓ | ✓ | ✓ | ✓ | — | — | — | RTO 4h / RPO 1h | LEI retained per regulation; right-to-erasure deferred |
| L4 CalendarConvention | ✓ | ✓ | ✓ | ✓ | — | ✓ | — | RTO 24h / RPO 24h | n/a |
| L5 UnitStatus | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | RTO 1h / RPO 0 | n/a |
| L6 PositionState | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | RTO 1h / RPO 0 | n/a |
| L7P PolicyConfiguration | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | RTO 24h / RPO 24h | n/a |
| L8 LegalAgreement | ✓ | ✓ | ✓ | ✓ | — | — | — | RTO 24h / RPO 24h | Counterparty info retained |
| L9 RawMarketObservation | ✓ | ✓ | ✓ | ✓ | — | ✓ (capital history) | — | RTO 4h / RPO 1h | n/a |
| L10 LifecycleOracle | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | RTO 1h / RPO 0 | n/a |
| L11 ExternalConfirmation | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | RTO 1h / RPO 0 | n/a |
| L12 CalibratedMarketObject | — | ✓ | — | — | — | ✓ (capital history) | — | RTO 4h / RPO 1h | n/a |
| L13 MoveStream | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | RTO 0 / RPO 0 | Pseudonymisation per architecture |
| L14 ValuationRecord | ✓ | ✓ | — | — | ✓ | ✓ | — | RTO 1h / RPO 0 | n/a |
| L15 Obligation | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | RTO 1h / RPO 0 | n/a |
| L16 ReferenceMaster | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | RTO 24h / RPO 24h | n/a |
| L17 RegulatorySubmission | — | ✓ (mandatory) | ✓ (mandatory) | ✓ (mandatory) | — | ✓ | — | RTO 4h / RPO 1h | n/a |
| L18 BreakRegister | ✓ | ✓ | ✓ | — | ✓ | — | ✓ | RTO 24h / RPO 24h | n/a |
| L19 ClockAuthority | ✓ | ✓ | ✓ | ✓ | — | — | — | RTO 0 / RPO 0 | n/a |

**Perpetual-issuance edge case (closes nazarov m-5):** for instruments with no maturity (perpetual bonds, evergreen mandates), retention horizon is `max(applicable_regulation_horizon, position_state_non_zero + 7y)`.

**GDPR-minimisation conflict resolution rule:** regulatory retention preempts GDPR right-to-erasure for fields covered by retention obligation; non-mandatory personal data minimised at issue.

## §V3.8 Tempo / SLA Matrix (closes finops B6)

Per-leaf p50/p99 ingress SLA, degraded mode, DORA RTO/RPO.

| Leaf | p50 ingress | p99 ingress | Degraded mode | DORA RTO | DORA RPO |
|------|-------------|-------------|----------------|---------|---------|
| L1 ProductTerms | 100ms | 1s | Reject; manual review | 4h | 0 |
| L2 InstrumentMaster | 1s | 10s | Stale-allowed marker; FSM Stale on dependent units | 4h | 1h |
| L3 PartyLEI | 1s | 10s | Stale-allowed for non-critical; reject for new trades if LEI lapsed | 4h | 1h |
| L4 CalendarConvention | 1s | 10s | Reject pricing; FSM Stale | 24h | 24h |
| L5 UnitStatus | 10ms | 100ms | Reject reads; quorum-based | 1h | 0 |
| L6 PositionState | 10ms | 100ms | Reject reads; quorum-based | 1h | 0 |
| L7P PolicyConfiguration | 100ms | 1s | Last-known-good with quality flag | 24h | 24h |
| L8 LegalAgreement | 100ms | 1s | Reject new trades; existing trades unaffected | 24h | 24h |
| L9 RawMarketObservation | 1ms | 10ms | FSM Stale; quality flag | 4h | 1h |
| L10 LifecycleOracle | 100ms | 1s | Defer to bilateral fallback; manual reconciliation | 1h | 0 |
| L11 ExternalConfirmation | 100ms | 1s | Stale-allowed; reconciliation queue | 1h | 0 |
| L12 CalibratedMarketObject | 1s | 10s | FSM Stale; downgrade ValuationRecord quality | 4h | 1h |
| L13 MoveStream | 10ms | 100ms | Reject commit; defer to manual review | 0 | 0 |
| L14 ValuationRecord | 100ms | 1s | FSM Stale | 1h | 0 |
| L15 Obligation | 100ms | 1s | Saga compensation; escalation | 1h | 0 |
| L16 ReferenceMaster | 1s | 10s | Stale-allowed | 24h | 24h |
| L17 RegulatorySubmission | 1s | 10s | Queue; submit on recovery | 4h | 1h |
| L18 BreakRegister | 100ms | 1s | Aging proceeds; manual escalation | 24h | 24h |
| L19 ClockAuthority | 100µs | 1ms | Refuse pricing; FSM Stale | 0 | 0 |

**T+1 affirmation:** L11 affirmation must complete by 9pm ET on T+0. SLA p99: 9pm ET on T+0 minus settlement-orchestration buffer.
**T+0 settlement (US equities post-2024):** L11 confirmation must arrive by 11:30am ET on T (cutoff per DTCC). Late confirmation triggers `wf-confirm-break` with CSDR penalty obligation if cross-border.

## §V3.9 §15 Restatement — Plain Rulings (closes geohot B2-NEW; no tension boxes)

The R2 geohot reviewer flagged that v2 §15 still performed the banned tension-box pattern under ADR badges. v3 §15 is restated as plain rulings:

- **D1 leaf count:** 19. ADR-2/3/4. No alternative tolerated.
- **D2 tokenised collateral:** `lifecycle_model = SmartContract` in L1; `EligibleCollateralCriteria` extension in CDM. `DigitalAsset` excluded by live CDM. ADR-10. No alternative tolerated.
- **D3 surrogate witnesses:** Λ1 architectural risk with kill-switch; Λ4/Λ8/Λ13 witnessed-via-composition with parameters. P-Λ1-VENDOR-OPACITY oracle (§V3.1) discharges Λ1's runtime obligation.
- **D4 stored caches L5/L6:** ADR-1 V13 carve-out citing StatesHome C11. Cache-invalidation discipline CIv-1/CIv-2/CIv-3 per Th-4b. No alternative tolerated.
- **D5 compensations:** Three-tier saga tower (compensation child workflow → escalation workflow → terminal default). Trivial compensations remain activities. ADR-8.

**No "tension box" survives.** Each is an ADR with named justification.

## §V3.10 LoC Budget (closes geohot B1-NEW)

| Component | Budget | Hard cap |
|-----------|--------|----------|
| Core Ledger types (closed sums + smart constructors + parsers) | 3,000 LoC | 5,000 LoC |
| Core Ledger handlers (per (event_class × obligation_kind) cell) | 2,500 LoC | 4,000 LoC |
| Core executor + chain logic | 1,500 LoC | 2,500 LoC |
| Total core implementation | **≤7,000 LoC** | **≤10,000 LoC** |
| Vendor adapters (one per vendor / source) | ~500 LoC each, 10 sources | ~6,000 LoC |
| Test suite (unit + property + saga + regression) | ~12,000 LoC | ~20,000 LoC |
| **Total system (core + adapters + tests)** | **≤25,000 LoC** | **≤30,000 LoC** |

**If implementation overflows the hard cap, the spec is wrong.** This is the geohot anchor (cf. tinygrad core ~5K LoC). Refactoring discipline: every new abstraction must justify itself against the cap.

---

**End of Phase 3 Round 3 Proposal v3.**
