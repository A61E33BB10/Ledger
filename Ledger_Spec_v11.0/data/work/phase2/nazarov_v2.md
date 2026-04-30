# Phase 2 Round 2 — Data Team Synthesis: NAZAROV section v2

**Author role.** NAZAROV — data-layer architect.
**Posture.** Hold the boundary. Every datum is either provably right or has
survived enough independent checks that we have no remaining reason to
believe it is wrong.
**Round.** Phase-2 Revision Round 2, in response to R1 consolidated
findings (79 BLOCKING, 130 UNMITIGATED MAJOR, 130 MINOR across 19
adversarial reviewers). Authoritative brief: `phase3/round1/R1_consolidated_findings.md`.

---

## §0. Changes from v1

This section is rewritten and extended; v1 paragraphs that survive
verbatim are quoted by reference rather than reproduced. The substantive
changes, by R1 finding ID:

| Change | R1 ID | Action |
|---|---|---|
| Leaf count: 24 → **19** (16 minimalist + 3 load-bearing additions) | T1 (geohot, jane_street, formalis, grothendieck, lattner) | §1 collapse to FORMALIS-16; ADD L25 RegulatorySubmission, L26 BreakRegister, L27 ClockAuthority with per-leaf ADR. |
| L25 RegulatorySubmission introduced | T5 (isda, matthias, sbl, finops) | §1.4 new leaf in C5 Effects; §1.6 ADR; L21 axis added. |
| L26 BreakRegister introduced with full FSM | T4 (finops, lattner) | §1.4 new leaf; §3.7 full state machine. |
| L27 ClockAuthority introduced | T12 (noether, formalis, temporal) | §1.4 new leaf in C1; §3.8 specification; symmetry-carrier note. |
| L13 ↔ L10 N8 aggregation gate | T7 / nazarov B-1 | §2 N8 strengthened (N8.3, N8.4); §3.4 L10/L13 ingress reworded; `aggregation_outcome` field added to L19. |
| Trust registry made a real artefact | T11 / nazarov M-1 | §4.3 "Trust Registry Contract" — schema, cadence, kill-switch, change-control. |
| Per-assumption detection signal / compensating action / blast radius | T11 / nazarov M-2, jane_street M5 | §4.2 every C-A row extended with three new fields. |
| HSM key rotation: append-only public verification keys | Singleton 2 (correctness A.3) | §2 N2.5 added; §4.2 C-A2 amended. |
| Late-discharge race rule per obligation kind | Singleton 3 (temporal B-3) | §3.6 L16 ingress section names per-kind policy. |
| Gateway-signed paths: per-vendor decomposed registry rows + bound | nazarov B-2 | §2 N2.2 reworded; §2 N2.6 bound; §4.3 registry has `gateway_signed_path_count` field. |
| N5 split into N5a–N5d | nazarov B-3 | §2 N5 rewritten; §6 audit step 4 extended. |
| Mapping round-trip discipline | nazarov M-3 | §2 N11.4 added. |
| L24 / C-A9 instability resolved by deletion | nazarov M-4 | L24 removed from spine in T1 collapse; CORRECTNESS L10 cross-referenced via TEMPORAL boundary. |
| Quality-flag downstream binding | nazarov M-5 / N7.3 | §2 N7.4 added — typed read API obligation. |
| Malformed envelope provenance | nazarov M-6 | §2 N3.4 added — gateway-attested failure event. |
| Audit cadence per item | nazarov m-3 | §6 cadence column. |
| Retention horizon for perpetual issuance | nazarov m-5, C-A10 | §4.2 C-A10 amended with horizon discriminator. |
| L4 retroactive amendment policy at bar | nazarov m-1, T12, formalis M2 | §3.1 L4 ingress + §2 N6.4 (mode-1 pin). |
| Retention matrix, tempo SLA, reconciliation pair line | T4 (finops B1, B2, B4, B6) | §4.4 retention matrix; §4.5 SLA matrix; §3 every leaf carries reconciliation-pair line. |
| §6 verification approach extended | T11, T7, T8 | new audit steps 11–14 covering aggregation gate, registry, clock, canonicalisation. |

**Counts.** v1 had N1–N12 (12 named requirements, 36 sub-requirements);
v2 has N1–N12 with new sub-requirements N2.4, N2.5, N2.6, N3.4, N5a–N5d,
N6.4, N7.4, N8.3, N8.4, N11.4 — **51 sub-requirements**. v1 listed 8
unconditional + 10 conditional realism budget items; v2 lists 8 unconditional
+ **12 conditional** (C-A11 canonical-serialiser, C-A12 cross-replica
integrity), each with 3 new fields (detection signal, compensating action,
blast radius).

**R1 findings addressed in this section.** All NAZAROV-directed BLOCKING
findings (B-1, B-2, B-3) closed; all 6 UNMITIGATED MAJOR (M-1 through M-6)
closed; 5 minor closed; relevant share of T1, T4, T5, T7, T11, T12
themes closed. Singletons 2, 3, 11 closed within scope.

What I still **defer** (not my section): T2 (theorem rewrites — FORMALIS),
T3 (notation table / definitions appendix — Foundation team), T6 (CDM
re-fetch — MATTHIAS), T8 versioning algebra in detail (lattner / lattice
authors; I commit only to the canonicalisation pin and the 5-axis
recognition), T9 SBL sub-leaf register (SBL specialist; I provide the
attestation envelope discipline), T10 Goodhart traps (TESTCOMMITTEE).

---

## §1. Master taxonomy (revised — 19 leaves)

### §1.1 Leaf-count ruling [T1]

**Ruling.** The Data Team adopts the **minimalist path** with named
overrides: collapse to the FORMALIS-aligned 16, then ADD three
load-bearing leaves under explicit ADRs.

**Rationale.** Per R1 §6 and §1 T1, the §9.2 "tension box" reconciliations
of V8/V9/V10/V11 are rejected by every reviewer who flagged them.
Continuing 24 leaves with rhetorical reconciliations is the failure mode
the round explicitly named. The minimalist path satisfies geohot,
jane_street (with three named ADR overrides), formalis, grothendieck,
lattner; it accepts isda's L25, finops' break register, and noether's
clock authority as additions; it loses nothing economically. A separate
**SBL sub-leaf register** is owned by the SBL specialist (per T9 / sbl
Finding 1); it is a refinement *inside* L9 PositionState, not 14 new
leaves on the spine.

### §1.2 Collapsed leaves (v1 → v2)

The 24-leaf v1 spine collapses under T1 fix #1 as follows:

| v1 leaf | v2 disposition | Justification |
|---|---|---|
| L1 ProductTerms | retained (L1) | StatesHome map 1; canonical |
| L2 Instrument Master | retained (L2) | distinct authoring surface |
| L3 Party/LEI | retained (L3) | distinct attestor (GLEIF) |
| L4 Calendar/Convention | **folded into L2** | per geohot B1; reference data, not its own leaf |
| L5 Settlement Infrastructure | **deleted** as a leaf | per jane_street B3 / V10; lives outside Ledger boundary; consumed via boundary parser |
| L6 Legal Agreement | retained (L4) | distinct document attestation |
| L7 Policy / Configuration | **deleted** as a leaf | per jane_street B4 / V9; constants module + L21 pin |
| L8 UnitStatus | retained (L5) — cache of L14 | per grothendieck B2 / D4 resolution; documented as cache, ADR override of V13 |
| L9 PositionState | retained (L6) — cache of L14 | as L8; SBL sub-leaves managed by SBL specialist |
| L10 Raw Market Observation | retained (L7) | with N8 gate (B-1) |
| L11 Lifecycle/Oracle Attestation | retained (L8) | distinct attestor class |
| L12 External Confirmation | retained (L9) | distinct attestor class |
| L13 Calibrated Market Object | retained (L10) | with N8.4 input gate |
| L14 MoveStream | retained (L11) | canonical record |
| L15 ValuationRecord | retained (L12) | distinct attestation chain |
| L16 ObligationStore | retained (L13) | first-class liveness object |
| L17 Attestation Envelope | **folded** into L7/L8/L9 as a field | per geohot B1, jane_street B4 |
| L18 Identity & Metadata Keys | **deleted** as a leaf | per geohot B1; constants module |
| L19 Snapshot | retained (L14) — content-addressed view | per geohot B3 selectivity, retained because consumed by replay-determinism theorem |
| L20 Idempotency Token | **folded** into the ingesting leaf | per minsky m2; closed sum within consumer |
| L21 Version Pin | retained (L15) | with 5-axis split per T8 |
| L22 Hash-Chain Anchor | **folded** into L14 MoveStream as a field | per geohot B1 |
| L23 Capability/Permission | retained (L16) | distinct administration workflow |
| L24 Orchestration State | **deleted** from spine | per jane_street B6 / lattner B3 / nazarov M-4; not economic; binding to economic invariants is severed |

**Subtotal: 16 leaves (FORMALIS-aligned).**

### §1.3 Load-bearing additions (with ADRs)

**L17 RegulatorySubmission** [T5; isda B-1].
ADR: every Phase-1 reviewer who attempted DRR/SFTR/MiFIR/SLATE/FRTB
record-keeping discovered an outbound regulatory-submission record was
missing from L14. Folding it into L14 conflates (a) the
economic-effect transaction with (b) the regulatory-submission
artefact (DRR-rule-set-version-pinned, regulator-acknowledgement-bearing,
restate-on-amendment). The two have different mutation discipline,
different attestor (the firm's regulatory-submission gateway, not the
executor) and different retention horizon. The override-justification
is: minimum reduction available without re-introducing rhetorical
reconciliations — the leaf has its own attestor, its own version axis,
its own audit. Cited evidence: ISDA UM-1, UM-3, UM-4, isda B-1, sbl
Finding 2, finops B4, matthias B-2.

**L18 BreakRegister** [T4; finops B2].
ADR: reconciliation produces breaks; breaks have an FSM that no
existing leaf models. Could be merged into L13 ObligationStore with
`obligation_subtype = RECONCILIATION_BREAK`, but breaks have a
distinct FSM (`OPEN → INVESTIGATING → ASSIGNED → AGED-1/3/5 →
ESCALATED → AT-RISK → MATERIAL → CLOSED-CLEAN | CLOSED-ADJ |
CLOSED-WAIVED`), distinct four-eyes discipline at `CLOSED-WAIVED`,
distinct retention regime (DORA Art 13 + SOX § 404), and distinct
external reconciliation cadence. Lifting as its own leaf preserves the
FSM atomicity. The override-justification is: a break is a *first-class
operational fact with its own typed FSM*, not a discharge predicate;
folding it into L13 collapses the FSM with the ObligationStore's
discharge predicate, which is a Goodhart trap.

**L19 ClockAuthority** [T12; noether B1].
ADR: the bitemporal axes `t_obs` and `t_known` reference *some* clock.
Without a versioned, attested clock authority, S3 (time-translation
invariance) has no carrier and replay determinism is unwitnessed for
any leap-second-spanning interval. Could be folded into L15
VersionPin as one more axis, but the clock has its own attestor (NTP
operator / GNSS receiver / atomic clock), its own attestation
envelope, its own freshness contract — semantically a definition-class
leaf, not a version-pin axis. The override-justification is: the
symmetry carrier matrix demands a named carrier per master symmetry;
S3 carrier is the clock; rejecting this admission re-opens the
unwitnessed bitemporal path.

**Total: 16 + 3 = 19 leaves.** Below jane_street's 7-sector
*sectorality* count, with three named ADR-sanctioned overrides.

### §1.4 The 19-leaf catalogue (renumbered from FORMALIS-16 + 3 additions)

```
SPINE — 6 structural classes, mutually exclusive on mutation discipline

C1. DEFINITIONS — append-only versioned, registration-total
├── L1.  ProductTerms                                  (= StatesHome map 1)
├── L2.  Reference Data — Instrument & Calendar Master (Tier-1 input; calendars folded in)
├── L3.  Reference Data — Party / Legal-Entity         (LEI, BIC, jurisdiction, regulatory class)
├── L4.  Legal Agreement                               (ISDA Master, CSA, GMSLA, mandate)
└── L19. ClockAuthority                                (S3 carrier; NTP/PTP/GNSS/atomic) [NEW per T12]

C2. SHARED STATUS — single-writer-per-field cache of L11
└── L5.  UnitStatus                                    (= StatesHome map 2; documented as cache, ADR-override V13)

C3. PER-POSITION STATE — single-writer-per-field cache of L11
└── L6.  PositionState                                 (= StatesHome map 3; SBL six-coordinate; SBL sub-leaves managed by SBL specialist)

C4. OBSERVATIONS — append-only attestations, bitemporal mandatory
├── L7.  Raw Market Observation                        (with N8 aggregation gate before L19/L10 consumption)
├── L8.  Lifecycle/Oracle Attestation
├── L9.  External Confirmation/Reconciliation
└── L10. Calibrated Market Object                      (output of L7 through Kalman; consumes only N8-gated L7)

C5. EFFECTS — append-only, hash-chained
├── L11. MoveStream                                    (canonical record; hash-chain anchor folded in)
├── L12. ValuationRecord
├── L13. ObligationStore
├── L17. RegulatorySubmission                          (DRR-rule-set-version-pinned) [NEW per T5]
└── L18. BreakRegister                                 (FSM-bearing operational record) [NEW per T4]

C6. PROVENANCE & ORCHESTRATION — meta-data and replay-substrate
├── L14. Snapshot                                      (content-addressed view per N10)
├── L15. VersionPin                                    (5 axes per T8 versioning algebra; canonicalisation pinned)
└── L16. Capability/Permission                         (C4 capability scopes from StatesHome)
```

**Total: 19 leaves; deleted from v1: L4 (folded), L5 (boundary parser),
L7 (constants), L17 (field), L18 (constants), L20 (folded into ingester),
L22 (field), L24 (deleted).**

### §1.5 Class-to-mutation-discipline matrix

| Class | Mutation discipline | Cache or canonical? |
|---|---|---|
| C1 (L1–L4, L19) | Append-only versioned; registration-total | Canonical |
| C2 (L5) | Single-writer-per-field cache of L11 (per StatesHome C11) | **Cache** (ADR-override V13) |
| C3 (L6) | Single-writer-per-field cache of L11 (per StatesHome C11) | **Cache** (ADR-override V13) |
| C4 (L7–L10) | Append-only attestations; bitemporal mandatory | Canonical |
| C5 (L11–L13, L17, L18) | Append-only hash-chained; immutable | Canonical |
| C6 (L14–L16) | Append-only meta-data; bound to instances of C1–C5 | Canonical (meta) |

The cache-vs-canonical distinction (per D4 resolution) is now explicit:
L5 and L6 are reads-as-projections of L11, with documented
cache-invalidation discipline (per FORMALIS Theorem 4b). Per V13's text
("balances must remain a projection"), the override is documented in the
ADR register, not silently applied.

### §1.6 ADR register (in this section)

ADRs to be lifted into the project's `ADR/` register:

- **ADR-001:** L4 Calendar folds into L2 Instrument & Calendar Master.
  Calendars are reference data; separating per V8/V9 ceiling violation.
- **ADR-002:** L5 Settlement Infrastructure deleted as leaf; remains a
  boundary parser invoked at projection time. v10.3 §9.1 places SSI
  outside the Ledger boundary.
- **ADR-003:** L7 Policy/Configuration deleted as leaf; constants module
  + L15 pin. CI schema-length check enforces the cap.
- **ADR-004:** L17 Attestation Envelope folded into observations as a
  field (`envelope: AttestationEnvelope`). It is a discipline, not a
  category.
- **ADR-005:** L19 Snapshot retained despite V13 reservation; it is a
  *content-addressed view*, not a stored projection. Selectivity
  justification: replay-determinism theorem requires a content-addressed
  artefact distinct from L11 (which is hash-chained but mutable-tail).
- **ADR-006:** L20 Idempotency Token folded into the consuming leaf as a
  closed sum field per minsky m2 / F19.
- **ADR-007:** L22 Hash-Chain Anchor folded into L11 as a field.
- **ADR-008:** L24 Orchestration State deleted from spine. Workflow-history
  is TEMPORAL-owned; binding to economic invariants severed by removing
  CORRECTNESS L10 transitivity (handed back to TEMPORAL section to
  re-state without binding L13 obligation liveness to C-A9).
- **ADR-009 (NEW):** L17 RegulatorySubmission added as separate leaf —
  distinct attestor, distinct version axis, distinct retention.
- **ADR-010 (NEW):** L18 BreakRegister added as separate leaf — distinct
  FSM, distinct four-eyes discipline.
- **ADR-011 (NEW):** L19 ClockAuthority added as separate leaf — S3
  symmetry carrier; without it, replay determinism is unwitnessed for
  leap-second-spanning intervals.
- **ADR-012:** L5 (UnitStatus) and L6 (PositionState) retained despite
  V13 — documented as caches with single-writer invariants per StatesHome
  C11. Cache-invalidation discipline named in §3.2 / §3.3.

---

## §2. NAZAROV minimum data-quality bar (revised)

The bar is unchanged in numbering N1–N12. **New** sub-requirements
introduced to address R1 findings are flagged `[NEW]`. The text below
quotes what survives unchanged and rewrites what was found insufficient.

### N1 — Provenance is mandatory and named

Unchanged (v1 §2 N1.1–N1.3).

### N2 — Attestation is mandatory at the boundary

**N2.1.** Unchanged.

**N2.2.** [REVISED per nazarov B-2] Where a vendor cannot sign at
source, signing happens at the ingestion gateway under a clearly
identified gateway key. **The resulting trust assumption decomposes
into three rows in the trust registry, not one:** (a) **vendor honesty**
("vendor Y faithfully reported its internal beliefs"), (b) **TLS chain
freshness** ("the TLS session terminating at the gateway was not
intercepted"), (c) **gateway operator integrity** ("the gateway
operator's process discipline preserves the bytes received from Y to
the moment of signing"). Each row has a separate owner, separate
violation consequence, separate detection signal. Bare REST + JSON
without all three rows is not data; it is a rumour, and the registry
is structurally incomplete.

**N2.3.** Unchanged: HSM mandatory for boundary-crossing keys; rotation,
revocation, recovery specified.

**N2.4.** [NEW per nazarov B-2] The total count of active gateway-signed
ingest paths (i.e., the count of (a) rows in the trust registry) MUST
be bounded by an explicit policy parameter `max_gateway_signed_sources`
(in the constants module, version-pinned via L15). Adding a new
gateway-signed source MUST be a governance event recorded as an L11
transaction (policy change), with change-control reference in the L18
trust registry update. Otherwise the boundary acquires unsigned-at-source
exposure monotonically and silently.

**N2.5.** [NEW per Singleton 2; correctness A.3] Public verification
keys MUST be append-only. HSM key rotation adds a new key but does not
remove any prior key. A signed envelope verifies against the key
authoritative at the envelope's `t_known`; replay against pre-rotation
material verifies against the pre-rotation key. The trust registry
records the (key_id, valid_from, valid_to, succeeded_by) chain.
Rotation MUST NOT invalidate prior envelopes.

**N2.6.** [NEW per nazarov B-2 / Singleton 11] For every gateway-signed
path, a per-vendor row in the trust registry decomposes the compound
trust assumption per N2.2 (a/b/c). The detection signal for each row
is enumerated separately: (a) cross-vendor disagreement above
threshold; (b) certificate-pinning failure; (c) gateway-side
log-tampering detection. Compound rows are forbidden.

### N3 — Ingress validation is total over a documented input domain

**N3.1, N3.2, N3.3.** Unchanged.

**N3.4.** [NEW per nazarov M-6] When the L17-class attestation envelope
is itself structurally malformed (missing field, wrong format,
unrecognised signature algorithm, expired key), the gateway MUST emit
a **failed-ingest record** that itself carries a gateway-attested
envelope describing the failure: the gateway attests "I, gateway X,
received the following bytes from source Y at time T; I was unable to
validate the inbound L17 envelope for reason Z (closed enum:
SIGNATURE_INVALID | KEY_EXPIRED | KEY_REVOKED | ALGO_NOT_ALLOWED |
ENVELOPE_MALFORMED | TIMESTAMP_OUT_OF_RANGE | ENCODING_INVALID)". The
failed-ingest record carries `(received_bytes_hash, source_advertised_id,
gateway_id, t_received, failure_reason, gateway_signature)`. Failed
ingests are first-class data; they have provenance even though the
datum they reference does not.

### N4 — Idempotency on replay is total

Unchanged (v1 §2 N4.1–N4.3).

### N5 — Dispute resolution path is specified and exercised — split into N5a/b/c/d [REWRITTEN per nazarov B-3]

The dispute-resolution path is fundamentally different across four
classes of dispute. v1's N5.1 conflated them; v2 splits.

**N5a — Intra-system replay disputes (the v1 N5).** When a counterparty
disputes "what value did your system see at time `t`?", the data layer
provides an as-known-at-`t` replay primitive that returns the
bit-identical content the workflow consumed at original execution.
Verifiable against the original L17 envelope and the L11 hash-chain.
This is N5a; it is the unconditional guarantee.

**Applies to:** L7, L9, L11, L12, L13, L17, L18.

**N5b — Input-correctness disputes (vendor-opacity surrogate, for L1
unwitnessed law).** When the dispute is "was the input attestation
itself trustworthy?", N5a is silent. The protocol is **multi-source
re-attestation**: re-fetch the same observation from at least N=3
independent sources at the disputed `(t_obs, t_known)`; compute
disagreement statistic; if disagreement exceeds the disagreement
threshold of N8, the original input is **substantively disputed** and
escalates to manual reconciliation (L18 BreakRegister with severity
MATERIAL). The bar requires this protocol to exist and to be exercised
on a documented schedule, not only on dispute event. The detection
signal is C-A3 violation indicator (cross-vendor disagreement above
threshold) running continuously.

**Applies to:** L7, L8 (where economically material), L10 (calibration
input).

**N5c — Storage-integrity disputes (cosmic-ray surrogate, for L8
unwitnessed law).** When the dispute is "was the stored byte the byte
that was attested?", N5a is silent because the L11 anchor is computed
*after* a silent flip would persist. The protocol requires
**cross-replica verification with at least N=3 independent replicas**
under independent failure modes (different storage substrates, AZs,
operators); pair-wise hash comparison MUST run continuously; replicas
disagreeing trigger a BreakRegister entry. Erasure-coding parameters
`(n, k)` MUST be specified and pinned in L15. C-A12 (added) is the
named realism budget item.

**Applies to:** L7, L8, L9, L11, L12, L13, L14, L17, L18.

**N5d — Liveness-projection disputes (for L13 obligation-liveness
unwitnessed law).** When the dispute is "will obligation O be discharged
by deadline `t_d`?", N5a is silent because no replay applies to a
future event. The protocol is **bounded-horizon structural induction
over the closed enumeration of (event_class, obligation_kind) pairs +
compensation-handler totality + insurance/escalation backstop with
explicit horizon parameter `T_max`**. The realism budget records the
bounded-horizon parameter and the backstop.

**Applies to:** L13.

**N5.unchanged.** N5.2 and N5.3 of v1 carry through as N5.2 and N5.3,
applicable to N5a only. For N5b/c/d, the operational protocol is the
dispute resolution.

### N6 — Point-in-time reconstruction is bitemporal

**N6.1–N6.3.** Unchanged.

**N6.4.** [NEW per nazarov m-1, T12, formalis M2] **Mode-1 calendar
amendment policy is pinned at the bar level.** Retroactive holiday
additions are L2 Calendar versions with later `t_known` and earlier
`effective_date`; they MUST NOT invalidate previously-pinned schedules
on existing L1 ProductTerms. Any L1 unit registered before the
amendment carries a `calendar_version_pin` that points to the calendar
version known at registration; subsequent calendar republication does
not change the pinned value. Re-running affected workflows after
amendment is via re-projection from the last-good snapshot, not by
mutating L2.

### N7 — Failure mode when absent or contradicted is named, not silent

**N7.1, N7.2, N7.3.** Unchanged.

**N7.4.** [NEW per nazarov M-5] Every downstream consumer of a
quality-flagged datum MUST declare its **quality-acceptance policy**
as a closed sum: the maximum quality class it will consume for each
downstream effect (`quality_acceptance: { effect_id → max_quality }`).
The storage layer MUST enforce the policy via a typed read API that
refuses below-policy reads. A reader requesting a `STALE` valuation
where its policy declares `FIRM_ONLY` for the effect "regulatory
submission" gets a refusal, not a value. Without N7.4, N7.3 is theatre.

### N8 — Multi-source aggregation rule is documented per leaf

**N8.1, N8.2.** Unchanged (closed sum of aggregation functions;
single-source authority must be named in registry).

**N8.3.** [NEW per nazarov B-1; T7] Every leaf in C4 (L7, L8, L9, L10)
MUST carry, on each ingested row, a typed `aggregation_outcome` field:

```
AggregationOutcome =
  | MultiSourceConsensus { source_count, function, disagreement: ε }
  | UniqueAuthority { authority_id, registry_assumption_ref }
  | Quarantined { reason, original_payload_hash }
```

A row whose `aggregation_outcome` is `Quarantined` MUST NOT be
admitted to any L14 snapshot consumed by L10 calibration or by L12
valuation.

**N8.4.** [NEW per nazarov B-1; T7] L14 Snapshot canonical content MUST
include the per-row `aggregation_outcome` of every L7 row in the
snapshot. The N10 content-addressing therefore captures *whether*
aggregation happened, not just *what* the value was. A snapshot
containing a single-source `UniqueAuthority` row whose
`registry_assumption_ref` is missing or invalid MUST fail snapshot
construction.

### N9 — Mutable history is forbidden

Unchanged (v1 §2 N9.1–N9.3).

### N10 — Determinism is the foundation of replay

**N10.1.** [REVISED per T8] Every snapshot (L14) MUST be content-addressed
under a **pinned canonicalisation algorithm** (per L15 axis
`canonicalisation_pin`). Two computations consuming the same snapshot
ID MUST produce the same output bit-identically only when both
canonicalise under the same pinned algorithm; cross-canonicalisation
replay is by definition a different snapshot. (See C-A11 below.)

**N10.2–N10.4.** Unchanged.

### N11 — The mapping layer is part of the oracle

**N11.1, N11.2, N11.3.** Unchanged.

**N11.4.** [NEW per nazarov M-3] For every ingress path that may be
**re-exported** (L1 ProductTerms in regulatory submission, L11
MoveStream in SFTR/EMIR/SLATE/MiFIR reporting via L17, L4 Legal
Agreement in counterparty confirmations), the mapping MUST be either
(a) **bijective on the round-trip** (FpML/CDM → internal → FpML/CDM
produces the original modulo a documented canonicalisation), or (b)
carry an explicit **lossy-canonicalisation declaration** in the L15
mapping version pin, naming the lossy axes. This makes C-A5's
detection signal (round-trip test failures) testable; without N11.4,
the test would be testing a property the bar does not require.

### N12 — Trust assumptions are first-class

Unchanged textually (v1 §2 N12.1–N12.3); the registry contract is now
specified in §4.3 below per nazarov M-1.

---

## §3. Per-leaf workflow specifications (revised, condensed; T4 reconciliation pair on every leaf)

For each of the 19 leaves I specify (a) attestation, (b) ingress, (c)
**reconciliation pair** [NEW per T4 / finops B1], (d) late-arrival /
dispute, (e) point-in-time reconstruction. Where v1 text survives
verbatim, I cite v1 §3.X and add only the reconciliation pair plus any
R1-required revision.

The reconciliation-pair line schema (per finops B1, copied verbatim
into v2):

```
Reconciliation: (external_authoritative_source, cadence, tolerance,
                 break_management_workflow_id, control_owner)
```

`break_management_workflow_id` resolves to an L18 BreakRegister entry
on disagreement. `control_owner` is a named role on a named team (per
T11; not a job title alone — ties to person on the org chart).

### §3.1 Class C1 — Definitions (L1–L4, L19)

**Common pattern.** v1 §3.1 carries through unchanged. Per-leaf
attestation (L1, L2, L3, L4) text from v1 §3.1 unchanged; per-leaf
revisions below.

**L1 ProductTerms.**
Reconciliation: `(L2 master + counterparty confirmation echo, T+0,
zero-delta on identifying fields, BR_L1_terms_break, control = trade
support lead [TBD-named])`. Per nazarov m-1 / N6.4: `calendar_version_pin`
is a mandatory field on every L1 unit at registration; mode-1 amendment
discipline applies.

**L2 Reference Data — Instrument & Calendar Master.** [revised: L4
folded in]
Reconciliation: `(Bloomberg ⊗ Refinitiv ⊗ SIX ⊗ ANNA ⊗ exchange direct,
T+0 daily ingest + intraday on amendment, two-of-three consensus on
identifying fields, BR_L2_master_break, control = reference-data lead
[TBD-named])`. Per N8: two-of-three quorum; pairwise disagreement
above threshold (`tolerance` per field class) quarantines the row to
BreakRegister.

**L3 Reference Data — Party/LEI.**
v1 §3.1 unchanged.
Reconciliation: `(GLEIF CDF ⊗ counterparty self-attested LEI on
confirmations, T+0 daily, exact match on lei_status / lapsed_date,
BR_L3_lei_break, control = client onboarding lead [TBD-named])`.
Lapsed-LEI alert at T-30 days triggers L13 obligation
`renew_party_attestation`.

**L4 Legal Agreement.**
v1 §3.1 (was L6) unchanged.
Reconciliation: `(ISDA Notices Hub / ISDA Create echo + counterparty
PDF hash, on execution + on amendment, exact hash, BR_L4_agreement_hash_break,
control = legal operations lead [TBD-named])`.

**L19 ClockAuthority.** [NEW]
Attestor: NTP/PTP server operator / GNSS receiver / atomic clock
authority. Each attestation is signed by the authority's key (registered
in L16); per-attestation fields:
`(authority_id, source_kind ∈ {NTP, PTP, GNSS, atomic},
leap_second_policy_version, attested_offset, attestor_signature, t_known)`.
Every `t_obs` and `t_known` in any leaf MUST carry a reference
(`clock_authority_pin`) into L19.
Ingress: standard envelope verification + sanity checks
(`attested_offset` within `(−ε, +ε)` of system clock at receipt; jump
detection).
Reconciliation: `(at least 3 independent clock authorities, continuous,
max pairwise offset 50 ms (parameter, L15-pinned), BR_L19_clock_skew_break,
control = SRE lead [TBD-named])`.
Late-arrival/dispute: leap-second policy version is a versioned
artefact; replay against pre-leap-second material verifies under the
pre-amendment leap-second policy.
Point-in-time: `as_of(authority_id, t_known)` returns the latest
attestation with `t_known' ≤ t_known`.

### §3.2 Class C2 — UnitStatus (L5)

v1 §3.2 unchanged. Cache-invalidation discipline: L5 is a fold of L11;
per FORMALIS Theorem 4b, the cache-invalidation event is the L11
StateDelta touching `unit_id`; cache rebuild is a deterministic
re-projection (verifiable by the audit step 3 of §6).
Reconciliation: `(custodian / fund administrator / CCP statement on
fields whose external mirror exists — last_settlement_price, lifecycle
stage, triggered-barrier flag, T+0 daily, exact, BR_L5_status_break,
control = trade support lead [TBD-named])`.

### §3.3 Class C3 — PositionState (L6)

v1 §3.3 unchanged for the spine semantics. SBL six-coordinate
sub-leaves are managed by the SBL specialist (per T9); from this bar's
perspective they are *fields on L6*, each subject to single-writer C11
discipline.
Reconciliation: `(CCP statement / fund-administrator NAV / client
statement / agent-lender allocation report, T+1 by 9am UTC,
field-class-specific tolerance, BR_L6_position_break, control =
position control lead [TBD-named])`.

### §3.4 Class C4 — Observations (L7–L10) [REVISED per B-1]

**L7 Raw Market Observation.** [revised: N8 gate enforced]
v1 §3.4 L10 first three bullets carry through. **The fourth bullet is
revised:** the bitemporal index now stores the row with
`aggregation_outcome` (per N8.3) attached at write time. Snapshot
construction (N8.4) refuses to admit a row with
`aggregation_outcome = Quarantined` and refuses to admit a row with
`UniqueAuthority` whose `registry_assumption_ref` is invalid.
Reconciliation: `(cross-vendor: Bloomberg ⊗ Refinitiv ⊗ ICE Data,
continuous tick-by-tick, vendor-tier-specific spread tolerance,
BR_L7_quote_break, control = market data lead [TBD-named])`.

**L8 Lifecycle/Oracle Attestation.**
v1 §3.4 L11 unchanged.
Reconciliation: `(corporate-action: SIX ⊗ DTCC ANNA, on event +
ex-date check; fixings: index administrator authoritative; default
declaration: CCP authoritative; locate: locate provider authoritative,
event-driven, exact match where multi-source, BR_L8_oracle_break,
control = lifecycle ops lead [TBD-named])`.

**L9 External Confirmation/Reconciliation.**
v1 §3.4 L12 unchanged.
Reconciliation: `(CSD: sese.025 against L11 outbound; cash: camt.053
against L11 cash moves; CCP: clearing-confirmation against L11 cleared
move; affirmation: T+1 by 9pm ET on T+0, exact transaction_id_ref
match, BR_L9_confirm_break, control = settlement ops lead [TBD-named])`.

**L10 Calibrated Market Object.** [revised: input gate]
v1 §3.4 L13 unchanged for the calibration FSM. **Ingress is revised
per nazarov B-1 / T7:** the calibration workflow MUST consume only L7
rows whose `aggregation_outcome ∈ {MultiSourceConsensus,
UniqueAuthority(registered)}`. Single-source rows without registered
authority are excluded by N8.4 at snapshot construction. The L10
output record carries a derived `input_aggregation_summary` (counts of
each `AggregationOutcome` variant in the input snapshot). Failed
calibration falls back per N7.3 with `quality = STALE`; downstream
consumers honour quality acceptance per N7.4.
Reconciliation: `(BVAL ⊗ Markit ⊗ internal IPV daily, T+1 9am UTC for
prior day's close, IPV variance threshold per FRTB AVA category,
BR_L10_ipv_break, control = independent price verification lead
[TBD-named])`.

### §3.5 Class C5 — Effects (L11–L13, L17, L18)

**L11 MoveStream.** v1 §3.5 L14 unchanged.
Reconciliation: `(custodian movement statement / CCP cash movement
file / ISO 20022 inbound confirmations, T+1 by 9am UTC, exact
transaction_id mapping, BR_L11_move_break, control = settlement ops
lead [TBD-named])`. Hash-chain anchor is now a field on each L11
transaction (`prev_hash`, `chain_anchor_id`); folded per ADR-007.

**L12 ValuationRecord.** v1 §3.5 L15 unchanged.
**Schema extension per finops B5:** add `(fair_value_level ∈ {1,2,3},
ipv_status, ipv_variance, ipv_source_id,
prudent_valuation_adjustment_components, unobservable_inputs[],
unobservable_input_sensitivity[])` per CRR Article 105 / FRTB AVA. (Schema
detail owned by FORMALIS / pricing team; my bar requires the fields
exist and feed the round-trip.)
Reconciliation: `(IPV: independent valuation source against firm mark,
T+0 EOD, IPV-variance threshold, BR_L12_val_break, control = product
control lead [TBD-named])`.

**L13 ObligationStore.** v1 §3.5 L16 unchanged.
**Late-discharge race rule per Singleton 3 (temporal B-3):** for each
obligation kind, the late-discharge policy is one of {REJECT,
CANCEL_COMPENSATION, QUEUE_AND_RECONCILE} declared on the obligation
type's metadata.
- SBL recall: `REJECT` (deadline sacrosanct under GMSLA standard).
- Standard cash settlement: `CANCEL_COMPENSATION` (acceptable to cancel
  buy-in if late discharge proof arrives during compensation).
- Regulatory submission: `QUEUE_AND_RECONCILE` (late ack updates state
  but the original escalation persists in record).
- CSDR penalty: `QUEUE_AND_RECONCILE` (penalty already accrued; late
  settlement is an L11 closing event but doesn't refund the penalty).
- Manufactured payment: `QUEUE_AND_RECONCILE`.
- LEI renewal: `QUEUE_AND_RECONCILE`.
- Margin call: `CANCEL_COMPENSATION`.
The closed enum of obligation kinds MUST carry the policy field;
default policies are forbidden.
Reconciliation: `(CSA-call register / AcadiaSoft / triResolve / TR
ack / regulator ack, by obligation kind, exact ack ID, BR_L13_obligation_break,
control = obligation manager lead [TBD-named])`.

**L17 RegulatorySubmission.** [NEW per T5]
Attestor: regulatory-submission gateway, signing under a key registered
in L16.
Schema: `(submission_id, regulator ∈ {CFTC, ESMA, FCA, ASIC, MAS, ...},
rule_set ∈ {DRR-CFTC, DRR-EMIR, DRR-SFTR, MiFIR-RTS22, SLATE,
FRTB-Pillar3, BCBS239, ...}, rule_set_version_pin (axis on L15),
payload (CDM-native, canonicalised per L15.canonicalisation_pin),
tx_id_lineage[] (FK to L11), acknowledgement_status ∈ {PENDING_SEND,
SENT, ACKED, REJECTED, RESUBMIT_REQUIRED}, restatement_chain_pred
(FK to prior L17 if a restatement), bitemporal: (t_obs = transaction
event time, t_known = submission time))`.
Ingress: synchronous output of the regulatory submission workflow;
written to L17 only after gateway signature; idempotency by
`submission_id` per N4 with closed-scope `regulatory_submission`.
Late-arrival/dispute: amendments arrive as new L17 entries with
`restatement_chain_pred` pointing to prior; original retained per N9.
Reconciliation: `(regulator acknowledgement file, regulator-specific
cadence, exact submission_id match, BR_L17_reg_submit_break, control =
regulatory reporting lead [TBD-named])`.
Point-in-time: per `submission_id`, the timeline of acknowledgement
status transitions, indexed bitemporally.

**L18 BreakRegister.** [NEW per T4]
Attestor: the reconciliation workflow producing the break.
Schema: `(break_id, leaf_class (which spine leaf produced the break),
external_source_id, internal_record_id, break_kind (closed enum),
opened_at, opened_by_workflow_id, fsm_state ∈ {OPEN, INVESTIGATING,
ASSIGNED, AGED_1, AGED_3, AGED_5, ESCALATED, AT_RISK, MATERIAL,
CLOSED_CLEAN, CLOSED_ADJ, CLOSED_WAIVED}, current_owner, sla_aging,
disposition_predicate, four_eyes_signoffs[] (required for CLOSED_WAIVED:
≥2 distinct signers, neither the original assignee), disposition_at,
linked_obligation_id (FK to L13 if material))`.
FSM: `OPEN → INVESTIGATING → ASSIGNED → (timer) → AGED_1 → AGED_3 →
AGED_5 → ESCALATED → AT_RISK → MATERIAL → {CLOSED_CLEAN | CLOSED_ADJ |
CLOSED_WAIVED}`. Backwards transitions forbidden. Mandatory four-eyes
on CLOSED_WAIVED.
Ingress: any reconciliation pair (above) producing disagreement opens
a break; idempotency on `(leaf_class, external_source_id,
internal_record_id, t_observed)`.
Late-arrival/dispute: break amendments arrive as new L18 entries via
`amends_break_id`.
Reconciliation: `(SOX § 404 break-population audit, quarterly, full
population CLOSED_WAIVED with ≥2 four-eyes signoffs, BR_L18_meta_audit,
control = head of internal audit [TBD-named])`.
Point-in-time: per `break_id`, FSM history.

### §3.6 Class C6 — Provenance & Orchestration (L14–L16)

**L14 Snapshot.** v1 §3.6 L19 unchanged.
**Per N8.4:** snapshot canonical content includes per-row
`aggregation_outcome` for L7 rows. **Per T8:** snapshot ID computed
under L15-pinned `canonicalisation_pin`.
Reconciliation: `(content-addressed self-verification: snapshot_id ==
hash(canonical_serialise(payload_set)), continuous on read, exact,
BR_L14_snap_break, control = data platform lead [TBD-named])`.

**L15 VersionPin.** v1 §3.6 L21 unchanged in spirit. **Per T8: 5 axes
named separately** — `component_pin`, `schema_pin`, `contract_pin`,
`model_pin`, `refdata_pin` — plus the new ones from R1: `drr_rule_set_version_pin`
(per T5 / isda UM-1), `canonicalisation_pin` (per T8), `clock_authority_pin`
(per T12, redundant with L19 pointer but explicit). Composition rule
per invariant: see lattner-owned versioning algebra section [DEFER to
lattner B1 fix, not my section]; the bar requires the axes are named
and individually traversable.
Reconciliation: `(deployment manifest vs running container digest,
per release, exact, BR_L15_pin_break, control = SRE lead [TBD-named])`.

**L16 Capability/Permission.** v1 §3.6 L23 unchanged.
Reconciliation: `(capability registry vs IAM ground truth, T+0 hourly,
exact, BR_L16_cap_break, control = IAM lead [TBD-named])`.

### §3.7 BreakRegister FSM — full specification [NEW per T4]

The FSM transitions, actor and SLA per transition:

| From | To | Actor | SLA | Notes |
|---|---|---|---|---|
| (init) | OPEN | reconciliation workflow | immediate | break opens automatically on disagreement |
| OPEN | INVESTIGATING | break-management workflow | within 30 min | initial triage |
| INVESTIGATING | ASSIGNED | break-management lead | within 2 hr | assigned to named owner |
| ASSIGNED | AGED_1 | timer | T+1 from OPEN | warning escalation |
| AGED_1 | AGED_3 | timer | T+3 from OPEN | regulatory disclosure threshold approached |
| AGED_3 | AGED_5 | timer | T+5 from OPEN | further escalation |
| AGED_5 | ESCALATED | timer or actor | T+5 or actor judgement | escalated to senior |
| ESCALATED | AT_RISK | manager judgement | per leaf class | reputational / regulatory exposure starts |
| AT_RISK | MATERIAL | manager + risk + compliance | as soon as known | financial impact crosses materiality |
| any non-terminal | CLOSED_CLEAN | break-management lead | n/a | reconciliation matches; no adjustment needed |
| any non-terminal | CLOSED_ADJ | break-management lead | n/a | adjustment booked via L11 |
| any non-terminal | CLOSED_WAIVED | break-management lead + 2 four-eyes signers | n/a | break dropped; mandatory four-eyes |

Backwards transitions forbidden. The FSM is monotone; reopening a
break creates a new break with `prior_break_id` pointer, not a
backwards transition.

### §3.8 ClockAuthority — operational note [NEW per T12]

Workflows that compute over `t_known` MUST pin `clock_authority_id`
into the snapshot (L14) and the L11 transaction record at commit. The
audit step 12 of §6 verifies that random sampling of L11 entries
references a valid L19 entry within `(t − 50 ms, t + 50 ms)`.
Leap-second policy versions evolve as L19 versions (append-only); a
disputed leap second is resolved by replay against the pinned policy
version at the disputed time.

---

## §4. Realism budget (revised)

### §4.1 Unconditional guarantees

Unchanged (v1 §4.1 U1–U8); U7 wording adjusted to reflect L8/L9 cache
status (single-writer-per-field on the cache, with deterministic
re-projection from L11).

### §4.2 Conditional guarantees — extended per nazarov M-2 / T11 / jane_street M5

Each conditional guarantee now carries three new fields beyond v1:

- **Detection signal** — the concrete observable that fires when the
  assumption is broken.
- **Compensating action** — what runs during the failure window.
- **Blast radius** — what economic invariants fail open.

**C-A1. Cryptographic primitive soundness.**
- Guarantee, assumption, owner, violation consequence: as v1.
- **Owner** [REVISED per nazarov M-2]: marked **OPEN** until external
  cryptographic advisor is named with concrete identity. Production
  deployment blocked on assignment. Interim: NCC Group / Trail of Bits
  ratification engagement [TBD-resourced].
- **Detection signal:** primitive-soundness advisories from NIST PQC,
  IACR ePrint, vendor CVE feeds.
- **Compensating action:** halt new envelope generation under affected
  primitive; freeze rotation; emergency multi-party algorithm transition
  workflow (out-of-band).
- **Blast radius:** every attested datum becomes potentially forged;
  the boundary fails closed; replay against pre-rotation envelopes
  loses verifiability.

**C-A2. HSM custody discipline.**
- Guarantee, assumption: as v1.
- **Owner** [REVISED]: marked **OPEN** until head of security
  operations is named with concrete identity. Production deployment
  blocked on assignment.
- **Detection signal:** HSM tamper alarms; key-usage anomaly detection
  (rate / IP / time-of-day deviations); HSM vendor advisories.
- **Compensating action:** isolate suspect HSM; freeze rotations
  involving its keys; emergency rotation under multi-party control.
- **Blast radius:** signing under a compromised key for the window
  before detection; trust assumption registry must trigger emergency
  rotation per N2.5 (which preserves prior envelopes' verifiability).

**C-A3. Vendor honesty.**
- Guarantee, assumption: as v1, with N2.2 decomposition (a/b/c) per
  N2.6.
- **Owner**: per-vendor relationship owner — concrete person on the
  data-operations org chart per N12.2; "per-vendor" means N=count of
  active gateway-signed sources (per N2.4 bound). Each vendor has a
  named individual.
- **Detection signal:** cross-vendor disagreement above threshold for
  the leaf class (per N8); downstream PnL-explain residual; FRTB RFET
  outlier flagging.
- **Compensating action:** quarantine the vendor's path; demote
  downstream `quality` to STALE; route consumers to remaining vendors
  under N7.3/N7.4 acceptance policy.
- **Blast radius:** the quarantined vendor's contribution to L7 is
  excluded; if quorum drops below `min_quorum`, all rows from the
  partition fall to `Quarantined` and downstream calibration freezes
  per N7.

**C-A4. Settlement-layer SSI freshness.**
- v1 unchanged.
- **Owner:** settlement-operations team — concrete named individual
  [TBD-named on org chart].
- **Detection signal:** settlement-fail confirmations (L9);
  virtual-wallet contra-balance reconciliation breaks (L18).
- **Compensating action:** halt outbound projection on affected SSI
  channel; manual SSI verification.
- **Blast radius:** misrouted wires; CSDR penalties (now first-class
  per L13 obligation kind `CSDR_PENALTY`); BEC fraud risk in worst case.

**C-A5. Schema stability within pinned version.**
- v1 unchanged.
- **Owner:** MATTHIAS / CDM interop lead — concrete named individual.
- **Detection signal:** round-trip test failures in mapping CI (per
  N11.4).
- **Compensating action:** freeze the pinned version; do not pin a
  later version until standards body clarifies.
- **Blast radius:** historical mappings produce different outputs on
  replay; v10.3 §17.2 limitation 9 violated; regulatory submissions
  may diverge from prior submissions of the same trade.

**C-A6. Calibration model soundness.**
- v1 unchanged.
- **Owner:** model-validation team — concrete named individual.
- **Detection signal:** PnL-explain residual exceeds policy (per
  L7-deleted constants module); cross-asset coherence break per
  valuation v1.0 §4.9; FSM `Quarantined` rate above baseline.
- **Compensating action:** demote calibration `quality` to STALE; halt
  L10 publication for affected target object; freeze model rotation;
  invoke model validation SR 11-7 / SS 1/23 review.
- **Blast radius:** L12 ValuationRecord quality degrades to STALE for
  affected positions; downstream regulatory-submission L17 may report
  STALE valuations and trigger IPV variance breaks.

**C-A7. Authority registry currency.**
- v1 unchanged.
- **Owner:** identity-and-trust operations — concrete named individual.
- **Detection signal:** authority-side revocation publications;
  failed-verify rates above baseline; OCSP / CRL freshness lag.
- **Compensating action:** suspend authority's path; pull fresh keys;
  if revocation, invalidate pending writes from that key.
- **Blast radius:** envelopes from a revoked key potentially admitted
  before detection (bounded by detection lag); under N2.5 (append-only
  public keys), historical envelopes remain verifiable against the
  pre-revocation key — only post-revocation admittance is the risk.

**C-A8. Closed-system boundary integrity. [SPLIT C-A8a / C-A8b per
nazarov-aligned reading + noether M5]**
- **C-A8a — boundary perimeter:** every datum entering the Ledger
  crosses a recorded boundary; no engineering shortcut writes directly
  to L1, L5, L6, L11.
  - Owner: architecture review board chair — concrete named individual.
  - Detection signal: code-review enforcement; integration tests
    refusing non-executor writes; storage-layer ACL audit.
  - Compensating action: rollback non-executor writes; investigate
    intent.
  - Blast radius: closed-system property of v10.3 collapses.
- **C-A8b — partition fault handling:** under network partition, the
  CAP choice is documented; the bar pins **CP** (refuse, do not
  stale-cache without quality demotion) for L7/L10/L17 paths; **AP** is
  permitted only on read-only L14 snapshot consumption with explicit
  staleness flag.
  - Owner: SRE lead.
  - Detection signal: split-brain alerting; quorum loss.
  - Compensating action: refuse new writes on minority partition; allow
    reads with STALE quality flag.
  - Blast radius: bounded by which leaf class participates in quorum.

**C-A9. Workflow-history determinism (TEMPORAL-owned). [REVISED per
nazarov M-4]**
- v1 disclaimed this. v2 acknowledges the latent dependency: if any
  economic invariant transitively depends on workflow-history replay
  (per CORRECTNESS L10), C-A9 is economically load-bearing in effect.
  The proposal's resolution is to **remove that transitive dependency**
  by deleting L24 from the spine (per ADR-008) and asking TEMPORAL to
  re-state CORRECTNESS L10 such that L13 obligation liveness no longer
  binds to C-A9. Until that re-statement is complete, C-A9 is treated
  as a primary assumption.
- Owner: TEMPORAL section lead — concrete named individual.
- Detection signal: determinism violations from Temporal SDK at
  replay; non-deterministic activity output detection.
- Compensating action: pin workflow versions; halt advancement on
  affected workflows pending resolution.
- Blast radius (until L24 transitive binding severed): replay of
  affected economic events fails; PnL-explain reconstruction may fail.

**C-A10. Retention sufficiency. [REVISED per nazarov m-5 / T4 / finops B4]**
- Guarantee: as v1, but parameterised.
- Assumption: retention policy (in the constants module per ADR-003)
  keeps L7/L8/L9/L11/L14 long enough to satisfy the longest-running
  unit's lifetime + the longest dispute window + the longest regulatory
  record-keeping requirement, jurisdiction-specific, GDPR-PII-isolated.
- **Perpetual-issuance handling:** for unit classes with no fixed
  maturity (perpetual bonds, perpetual swaps, mandate accounts), the
  retention horizon is `max(7y_post_termination, 50y_from_inception)`,
  and the retention policy must specify a **review cadence** rather
  than a finite end date. Termination of a perpetual unit is itself an
  L11 transaction; retention is reset relative to that termination.
  GDPR-PII conflict resolution: PII fields on L3 are isolated and may
  be redacted while non-PII transactional data is retained per SOX/MiFIR.
- Owner: records management + compliance — concrete named individual.
- Detection signal: retention-policy-vs-instrument-lifetime crosscheck
  at unit registration; periodic GDPR audit report.
- Compensating action: extend retention; re-pin policy version.
- Blast radius: a 30-year bond's late-life replay cannot be answered;
  audit material weakness; regulatory exam finding.

**C-A11. Canonical-serialiser stability. [NEW per T8 / minsky F10 /
feynman BLOCKING-G1]**
- Guarantee: under the L15-pinned `canonicalisation_pin`, two
  implementations producing the canonical encoding of the same logical
  payload produce bit-identical bytes.
- Assumption: the pinned canonicalisation algorithm (RFC 8785 JCS /
  Protobuf canonical with field-tag pin / CBOR per RFC 8949 §4.2.1) is
  fully specified and implementations conform.
- Owner: data platform lead — concrete named individual.
- Detection signal: cross-implementation hash divergence test in CI;
  snapshot reproduction test against archived snapshot ID.
- Compensating action: halt new snapshot creation under affected
  canonicaliser; freeze L15 axis until conformance tests pass.
- Blast radius: snapshot IDs cease to be portable; replay determinism
  fails across implementation versions; any cross-system replay claim
  becomes rhetorical.

**C-A12. Cross-replica integrity. [NEW per nazarov B-3 / N5c]**
- Guarantee: silent corruption of stored bytes is detected within
  `T_detect` of occurrence.
- Assumption: at least N=3 independent replicas with independent
  failure modes (different storage substrates, AZs, operators);
  pair-wise hash comparison runs continuously; erasure-coding `(n, k)`
  parameters pinned in L15.
- Owner: data platform / storage lead — concrete named individual.
- Detection signal: pair-wise replica hash mismatch; erasure-coded
  reconstruction failure rate above baseline.
- Compensating action: quarantine affected partition; reconstruct from
  surviving replicas; if reconstruction fails, escalate to L18
  BreakRegister (severity MATERIAL) and trigger N5c protocol.
- Blast radius: bounded by erasure-coding tolerance — `(n, k)` with
  `k` survivors required for reconstruction; below `k`, the data is
  reported lost and the dispute resolution path moves to N5c
  reconstruction-from-vendor-attestations.

**Total: 8 unconditional + 12 conditional = 20 budget items.**

### §4.3 Trust Registry Contract [NEW per nazarov M-1 / T11]

The trust registry is a real artefact with the following contract:

**Storage.** Append-only versioned table; rows immutable (per N9); each
row has `(registry_row_id, valid_from, valid_to_or_null, succeeded_by_or_null)`.

**Schema (per row).**
```
TrustAssumption {
  assumption_id              : ID                       -- e.g. "C-A3.bloomberg"
  decomposition_class        : Enum {
                                  vendor_honesty,
                                  tls_chain_freshness,
                                  gateway_operator_integrity,
                                  authority_currency,
                                  hsm_custody,
                                  primitive_soundness,
                                  schema_stability,
                                  model_soundness,
                                  boundary_perimeter,
                                  partition_fault,
                                  workflow_determinism,
                                  retention_sufficiency,
                                  canonicaliser_stability,
                                  cross_replica_integrity,
                                  single_source_authority
                                }
  scope                      : ScopeSpec                -- e.g. (vendor_id, leaf_class, jurisdictions[])
  owner                      : (person_id, team_id)     -- concrete person, not job title
  violation_consequence      : Text                     -- what breaks if assumption violated
  detection_signal           : (metric_id, threshold,
                                alert_runbook_id)       -- monitored, alerted
  compensating_action        : (workflow_id, escalation_chain)
  blast_radius               : Text + (affected_leaf_classes[],
                                affected_invariants[])
  review_cadence             : Enum {
                                  continuous,
                                  daily, weekly,
                                  monthly, quarterly,
                                  annual
                                }
  last_reviewed_at           : Timestamp
  next_review_due            : Timestamp
  kill_switch_id             : KillSwitchId             -- references killswitch registry
  change_control_ticket      : Ref                      -- governance reference
  attestor                   : Signature                -- signed by registry custodian
}
```

**Edit discipline.** Every edit is a governance event recorded as an
L11 transaction (policy change). Direct DB writes forbidden. Edit
authoring requires (a) change-control ticket, (b) two-eyes registry
custodian signoff, (c) downstream impact assessment for any change to
`detection_signal` or `compensating_action`.

**Review cadence.** Each row's `review_cadence` is enforced by an L13
obligation `review_trust_assumption(assumption_id)` with deadline
`next_review_due`. Missed reviews escalate per L13 standard.

**Kill-switch.** Each assumption has an associated `kill_switch_id`
pointing to a kill-switch registry (separate artefact). The kill-switch
specifies (a) what trips it (auto on detection signal exceeding
threshold for `T` consecutive periods, or manual by named role), (b)
what it does (halt ingestion on affected path, demote quality
downstream, freeze rotations, raise BreakRegister at MATERIAL severity),
(c) what un-trips it (recovery condition + manual confirmation by
two-eyes).

**Specifically required kill-switches** (one per major assumption
class):
- KS-A1: cryptographic primitive break — halt new envelope generation.
- KS-A2: HSM compromise — isolate affected HSM, freeze its rotations.
- KS-A3.[vendor]: vendor compromise — quarantine path, demote
  downstream.
- KS-A4: SSI freshness break — halt outbound on affected channel.
- KS-A7: authority key revocation — suspend authority's path.
- KS-A8a: boundary perimeter breach — halt non-executor write source.
- KS-A8b: partition — refuse minority writes.
- KS-A11: canonicaliser break — halt snapshot creation.
- KS-A12: cross-replica integrity — quarantine partition.

**Field-level audit signals.** For every assumption row, the
`gateway_signed_path_count` (per N2.4) is a derived field; its value
must be ≤ `max_gateway_signed_sources` from the constants module.

**Population.** At project deployment, the registry is populated with
N=12 conditional assumption rows + per-vendor decomposition rows under
C-A3 (3 rows per vendor under N2.6). For an N=10 production vendor
deployment, this is 12 + 30 = 42 rows minimum.

**Retention.** Registry rows retained per C-A10 (longest applicable
horizon).

### §4.4 Retention matrix [NEW per T4 / finops B4]

The full retention matrix is an addendum (`retention_matrix.md`) per
the recommended companion-document strategy. The bar requires:

- Per leaf × per regulation row.
- Per row: `horizon`, `hot_or_archival`, `deletion_conditions`,
  `gdpr_conflict_resolution_rule`.
- The matrix is bound to L15 `refdata_pin` so a retention policy
  change is itself versioned.

A skeleton is provided in §4.6 mapping leaves to regulations:

| Leaf | SOX | MiFIR | EMIR | SFTR | CFTC P49 | BCBS239 | FRTB | CASS | DORA | GDPR-conflict |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 7y | 5y | 5y | 5y | swap+5y | TtC | n/a | 5y | n/a | none |
| L2 | 7y | 5y | n/a | n/a | n/a | n/a | n/a | n/a | n/a | none |
| L3 | 7y | 5y | n/a | n/a | n/a | n/a | n/a | n/a | n/a | **PII isolation: redact when L3 drops below SOX/MiFIR end** |
| L4 | 7y | 5y | n/a | 5y | swap+5y | n/a | n/a | n/a | n/a | none |
| L5 | 7y | 5y | n/a | n/a | n/a | TtC | n/a | n/a | n/a | none |
| L6 | 7y | 5y | n/a | 5y | n/a | TtC | n/a | 5y | n/a | none |
| L7 | n/a | n/a | n/a | n/a | n/a | n/a | RFET 1y+stress | n/a | n/a | none |
| L8 | 7y | 5y | 5y | 5y | swap+5y | TtC | n/a | n/a | n/a | none |
| L9 | 7y | 5y | n/a | n/a | swap+5y | TtC | n/a | 5y | n/a | none |
| L10 | n/a | n/a | n/a | n/a | n/a | TtC | RFET history | n/a | n/a | none |
| L11 | 7y | 5y | 5y | 5y | swap+5y | TtC | n/a | 5y | 5y | none |
| L12 | 7y | n/a | n/a | n/a | n/a | TtC | AVA history | n/a | n/a | none |
| L13 | 7y | 5y | 5y | 5y | swap+5y | TtC | n/a | 5y | 5y | none |
| L14 | 7y | 5y | 5y | 5y | swap+5y | TtC | n/a | 5y | 5y | none |
| L15 | 7y | 5y | 5y | 5y | swap+5y | TtC | n/a | n/a | 5y | none |
| L16 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 5y | none |
| L17 | 7y | 5y | 5y | 5y | swap+5y | n/a | Pillar3 | n/a | 5y | none |
| L18 | 7y | 5y | n/a | n/a | n/a | n/a | n/a | n/a | 5y | none |
| L19 | 7y | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 5y | none |

(TtC = "through the cycle" = effectively indefinite for risk artefacts.)

### §4.5 Tempo / SLA matrix [NEW per T4 / finops B6]

Skeleton (full matrix in companion document):

| Leaf | Ingress p50 | Ingress p99 | Degraded mode | DORA RTO | DORA RPO |
|---|---|---|---|---|---|
| L1 (registration) | 100 ms | 1 s | refuse | 4 h | 0 |
| L2 (ref data ingest) | n/a (batch) | T+0 EOD | run on stale + flag | 8 h | 1 day |
| L7 (quotes) | 10 ms | 100 ms | quality=STALE downstream | 1 h | 5 min |
| L8 (oracle attest) | 100 ms | 1 s | refuse | 4 h | 0 |
| L9 (confirmation) | 100 ms | 1 s | refuse + retry | 4 h | 0 |
| L10 (calibration) | 1 s | 10 s | quality=STALE; freeze | 4 h | 0 |
| L11 (move commit) | 50 ms | 500 ms | refuse new writes | 2 h | 0 |
| L12 (valuation) | n/a (batch) | EOD + 1 h | quality=STALE | 4 h | 0 |
| L13 (obligation) | 100 ms | 1 s | refuse new; alert | 4 h | 0 |
| L14 (snapshot) | per epoch | per epoch | refuse | 4 h | 0 |
| L17 (reg submit) | per regulator | per regulator | retry queue | 8 h | 0 |
| L18 (break) | event | 1 hr | manual escalation | 4 h | 0 |
| L19 (clock) | continuous | 50 ms skew | refuse new writes | 1 h | 0 |

### §4.6 Audit cadence [NEW per nazarov m-3]

Per audit step in §6, the cadence is specified inline with the step.

---

## §5. What I refuse to admit, and why

Per NAZAROV deferral discipline, the v1 §5 list carries through with
two new refusals from R1:

- **No "trust the vendor feed" without an envelope.** N2 forbids it.
- **No silent fallback to last-known-good.** N7.2 forbids it.
- **No mutating restatement.** N9 forbids it.
- **No single-source data on materially-impacting paths without a
  named authority assumption.** N8.2 + C-A3 forbid it.
- **No hardcoded calendars, day-counts, or jurisdictions in code.**
  L2 + ADR-003 lift them.
- **No "balance" written independently of the move stream.** L11 is
  the single source; L5 and L6 are documented caches per ADR-012.
- **No untyped trust assumption.** N12.2 forbids it.
- **[NEW per T8] No content-addressed ID without a pinned
  canonicalisation algorithm.** N10.1 + C-A11 forbid it.
- **[NEW per T11] No conditional assumption owned by a job title.**
  N12.2 + every C-A row in §4.2 forbid it. Production deployment
  blocked on assignment of a concrete person to every owner field.
- **[NEW per nazarov B-1] No L7 row admitted to an L14 snapshot
  consumed by L10 calibration without a typed `aggregation_outcome`
  field.** N8.3 + N8.4 forbid it.
- **[NEW per nazarov B-2] No gateway-signed path without three
  decomposed registry rows (vendor honesty, TLS chain freshness,
  gateway operator integrity).** N2.2 + N2.6 forbid it.

---

## §6. Verification approach (extended)

An auditor confirms a candidate implementation satisfies this section
by the following audits, each with a cadence:

1. **Boundary inventory** — per release. Enumerate every code path
   that writes into L1, L5, L6, L11. Confirm only the executor (and
   deterministic handlers reached through it) writes.
2. **Attestation audit** — quarterly + per release. For each leaf in
   C4 + L17, randomly sample inbound payloads from production traffic;
   verify every payload carries a verifiable envelope and verification
   is enforced at ingress.
3. **Replay determinism test** — per release + monthly random sample.
   Pick a historical transaction; reconstruct inputs from L14 snapshot
   + L15 version pins; rerun handler; check bit-identical output.
4. **Bitemporal correctness test** — quarterly + on every restatement
   event. Pick a vendor-restatement event; verify "as known at
   `t_old`" returns the pre-restatement value and "with corrections
   through `t_new`" returns the restated value.
5. **Trust registry walk** — quarterly. Open the registry; confirm
   every assumption has name, scope, named-person owner, violation
   consequence, detection signal, compensating action, blast radius,
   review cadence, kill-switch; confirm at least one detection signal
   per assumption is currently being monitored; confirm the registry
   carries N=12 conditional rows + N×3 per-vendor decomposition rows.
6. **Idempotency replay** — per release. Replay an inbound message
   twice; verify the second replay returns the memoised outcome and
   produces zero side effects.
7. **Mutation forensics** — per release. Attempt to write directly to
   L1, L5, L6, L11 bypassing the executor; verify the storage layer
   rejects.
8. **Hash-chain integrity check** — continuous + per release.
9. **Snapshot reproducibility** — per release + monthly random sample.
   Reconstruct snapshot ID from its payload set under the pinned
   canonicalisation algorithm; verify content-addressed match.
10. **Closed-system perimeter test** — per release + quarterly fuzz.
    Inject a malformed payload at every boundary endpoint; verify
    quarantine + provenance recording (per N3.4); verify no downstream
    consumer sees the malformed datum.
11. **[NEW per B-1 / T7] Aggregation gate audit** — quarterly. Sample
    L14 snapshots consumed by L10 calibration; confirm zero rows with
    `aggregation_outcome ∈ {Quarantined}`; confirm every
    `UniqueAuthority` row has a valid `registry_assumption_ref`;
    confirm `MultiSourceConsensus` rows meet quorum and threshold per
    leaf-class N8 specification.
12. **[NEW per T12] Clock authority audit** — monthly. Sample L11
    transactions; verify every `t_obs` and `t_known` references a
    valid L19 `clock_authority_id`; verify pairwise authority offset
    within the L15-pinned skew budget.
13. **[NEW per T4] BreakRegister audit** — quarterly. Sample
    `CLOSED_WAIVED` breaks; verify each carries ≥2 four-eyes
    signoffs from distinct signers, neither the original assignee.
    Sample `MATERIAL` breaks; verify regulatory-disclosure timeline.
14. **[NEW per T11] Owner currency audit** — semi-annual. Verify each
    trust assumption row's `owner.person_id` resolves to an active
    person on the org chart; raise `MATERIAL` BreakRegister entry on
    the registry itself if any owner is unfilled or stale.

If all audit steps pass under their cadences, the candidate
implementation satisfies the NAZAROV bar.

---

## §7. Cross-references to sibling team members (revised)

v1 §7 unchanged in spirit, with the following adjustments:

- **MATTHIAS** owns the CDM cross-walk per T6; T6 fix (re-fetch all
  paths, promote Gap 5, re-rank gaps) is theirs.
- **TEMPORAL** owns the workflow shape; per ADR-008, removing L24
  from the spine requires TEMPORAL to re-state CORRECTNESS L10 such
  that L13 obligation liveness no longer transitively binds C-A9.
- **MINSKY** owns the type design — F1, F2, F4, F5, F6, F8, F11
  closed-sum / smart-constructor / refinement-type fixes from R1 §2
  are theirs.
- **FORMALIS** owns the theorem rewrites per T2; fix is theirs.
- **TESTCOMMITTEE** owns the per-stratum coverage targets, mutation
  operators (T10), historical-bug fixture corpus (singletons 24, 25).
- **ISDA** owns the dual-sided vs unilateral reporting position;
  L17 schema is mine, the rule_set position is theirs.
- **GROTHENDIECK** owns the categorical decoration; per cartan B2 /
  grothendieck B1, the forgetful functor must be defined or the
  decoration withdrawn.
- **SBL specialist** owns the L6 sub-leaf register (14 sub-leaves);
  the bar requires the sub-leaves carry the standard L6 reconciliation
  pair extended per six-coordinate.
- **GEOHOT** owns the delete-test and the LoC budget (singleton 22).
- **JANE STREET** owns the V1–V14 audit (R1 §0 anchor 5).
- **KARPATHY** owns the worked-example end-to-end loaders per T9.
- **CORRECTNESS** owns the goodhart trap detection mechanisms per T10.
- **NOETHER** owns the symmetry carrier matrix; my L19 ClockAuthority
  is the S3 carrier; other carriers are theirs.
- **FINOPS** owns the reconciliation-pair schema, the IPV control
  specification, the CSDR penalty obligation kind. The bar consumes
  their schema.

---

## §8. Closing note

This v2 closes every NAZAROV-directed BLOCKING (B-1, B-2, B-3) and
UNMITIGATED MAJOR (M-1 through M-6) finding, plus the relevant share
of T1, T4, T5, T7, T11, T12 themes and singletons 2, 3, 11. The leaf
count drops from 24 to 19, the bar grows from 36 to 51 sub-requirements,
the realism budget grows from 18 to 20 items each carrying three new
fields (detection / compensating action / blast radius), the trust
registry becomes a real artefact with schema/cadence/kill-switch, and
N5 splits into N5a/b/c/d for four genuinely different dispute classes.

What this v2 does **not** close (out of scope for NAZAROV):

- T2 theorem rewrites — FORMALIS section.
- T3 notation table / definitions appendix — Foundation team.
- T6 CDM re-fetch — MATTHIAS section.
- T8 versioning algebra in detail beyond the canonicalisation pin —
  lattner-led section.
- T9 SBL sub-leaf register — SBL specialist section.
- T10 Goodhart trap detection mechanisms — TESTCOMMITTEE section.
- The dependent NAZAROV claims that cross into TEMPORAL: workflow
  determinism (C-A9), late-discharge race (Singleton 3) — I name the
  required policies but the workflow shape is TEMPORAL-owned.

The boundary holds. The boundary is now witnessable.

---

*End of NAZAROV v2.*
