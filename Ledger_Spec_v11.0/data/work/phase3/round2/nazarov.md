# NAZAROV — Phase 3 Round 2 Closure-Check Review

**Reviewer.** Independent NAZAROV instance (no exposure to `phase2/nazarov_v2.md`
or to the prior R1 NAZAROV authoring context).
**Subject.** `phase3/round2/proposal_v2.md`.
**Posture.** Closure check against the three R1 NAZAROV BLOCKING findings
(B-1, B-2, B-3) + new findings discovered on independent read.
**R1 grade to beat.** B−.

---

## §0. Boundary statement

The boundary I am holding is the perimeter where any datum that materially
affects valuation, settlement, or regulatory submission crosses into the
Ledger's closed-system. In this proposal the boundary is realised through:

- L9 RawMarketObservation, L10 LifecycleOracle, L11 ExternalConfirmation,
  L12 CalibratedMarketObject (C4 Observations);
- L1 ProductTerms, L2 InstrumentMaster, L3 PartyLEI, L4 CalendarConvention,
  L8 LegalAgreement, L19 ClockAuthority (C1 Definitions);
- the attestation envelope folded into the above;
- the trust assumption registry that names every untyped trust;
- the dispute-resolution protocols (N5a–N5d).

The contract I am checking: every datum that crosses this boundary must
either be cryptographically attested with named provenance, multi-source
aggregated where consequence-class demands it, dispute-resolvable through a
specified protocol, and replay-deterministic — or be quarantined.

---

## §1. R1 BLOCKING findings — closure verdict

### B-1. L13 calibration consumes L10 with no N8 multi-source aggregation gate

**R1 defect.** L10 (now L9 in v2) rows admitted to a snapshot consumed by
Kalman calibration were not gated on N8 multi-source aggregation.
Single-source rows with valid envelopes passed; this is the silent vendor
trust the bar forbids.

**v2 evidence.**

- §5.1 first bullet: "L9 RawMarketObservation now requires N8 aggregation
  gate before snapshot inclusion (closes nazarov B-1). Adds
  `aggregation_outcome ∈ {multi_source_consensus, unique_authority,
  quarantined}` field. L9 rows admitted to L19 snapshots consumed by L12
  MUST have passed multi-source aggregation OR carry explicit
  `single_source_authority_assumption_ref` to the trust registry."
- §1 well-formedness predicate for L9: "`aggregation_outcome ∈
  {multi_source_consensus, unique_authority, quarantined}` recorded".
- §8 fault catalogue cluster III: "N8 aggregation; quarantine on threshold".
- ADR-9: "Single-source admission via N8.2 explicit assumption ref — Vendor
  honesty C-A3 named assumption; multi-source default."
- Sibling `nazarov_v2.md §2` N8.3 (typed `aggregation_outcome` mandatory on
  every C4 row) and N8.4 (snapshot canonical content includes per-row
  `aggregation_outcome`; snapshot construction refuses Quarantined and
  refuses unique-authority without an assumption ref).

**Verdict: CLOSED.** The gate exists at three nested levels: (i) the row
carries a typed outcome field; (ii) the snapshot-construction operation
refuses non-conformant rows; (iii) the unique-authority escape carries an
explicit registry reference (no anonymous trust). N8.4's promotion of
`aggregation_outcome` into snapshot canonical content is the load-bearing
move — it makes the gate an audit object, not just a validation check. The
Kalman input is now guaranteed clean attested data, with statistical
filtering downstream of attestation as conviction §6 requires.

**Residual.** None blocking. Minor: verify the per-leaf threshold table in
N8 specifies the disagreement threshold *numerically*, not deferred to TBD.
This is a Phase 3 follow-up, not a B-1 reopen.

---

### B-2. N2.2 gateway-signed paths permit "trust the vendor feed" with names attached

**R1 defect.** N2.2 specified *that* a trust assumption must exist when a
gateway signs on a vendor's behalf, but not *what its content must be* nor
*how many gateway-signed paths are admissible*. The trust assumption was
registered as a single line — "trust the vendor AND the TLS chain AND the
gateway operator's process discipline" — collapsing three independent
failure modes into one row. The bound on gateway-signed sources was absent;
the boundary acquired unsigned-at-source exposure monotonically and
silently.

**v2 evidence.**

- The proposal_v2 *consolidator* document does not strengthen N2.2 inline
  (§3, §10 do not contain N2.2 detail). However sibling `nazarov_v2.md` §2
  contains the strengthening:
  - **N2.2 reworded** — every gateway-signed path's trust assumption is
    explicitly decomposed into (a) vendor honesty, (b) TLS chain freshness,
    (c) gateway operator integrity. Compound rows forbidden (N2.6).
  - **N2.4 NEW** — `max_gateway_signed_sources` policy bound; new gateway
    paths require L11 governance event with change-control reference.
  - **N2.6 NEW** — per-vendor row, three decomposed sub-rows per vendor,
    distinct detection signals (cross-vendor disagreement; cert-pinning
    failure; gateway-side log-tampering).
- Trust-registry schema (`nazarov_v2.md §4.3`) carries a
  `decomposition_class` enum with `vendor_honesty`,
  `tls_chain_freshness`, `gateway_operator_integrity` as distinct values
  — three-row decomposition is type-enforced.
- For 10 vendors, 12 base + 30 decomposition = 42-row population stated
  inline.

**Verdict: CLOSED via sibling.** B-2's three minimum-compliant fixes are
all present in `nazarov_v2.md`. Each is structurally implemented (typed
enum value, schema field, governance event) rather than aspirationally
named.

**However — partial-closure caveat (new finding §2).** The
*consolidator-level* §10.2 table shows only the 12 top-level
conditional-assumption rows. The fan-out (3 rows × N vendors) is invisible
in the consolidator's artefact. An R3 reviewer reading only proposal_v2.md
(without sibling) would see C-A3 "Vendor honesty (per attested vendor)"
exactly as v1 had it: one row, owner "Per-vendor named relationship owner
(data ops)". The decomposition is one indirection away. **Closed in
substance; presentationally fragile.** I will issue this as new finding
NM-1 below; it does not reopen B-2.

---

### B-3. N5 dispute resolution insufficient for the 4 unwitnessed laws

**R1 defect.** N5.1 (replay primitive) resolved "did we compute consistently"
but did not resolve "was the input attestation trustworthy" (L1 vendor
opacity), "which restatement reflects truth" (L4 unbounded restatement),
"is the storage medium intact" (L8 cosmic ray), or "will the obligation
discharge" (L13 liveness). Four laws were tagged unwitnessed without N5
having a corresponding resolution path.

**v2 evidence.**

- §6 Λ-table reclassifies the four laws: Λ1 genuinely unwitnessed (vendor
  opacity, accepted as architectural risk with named owners CRO + Head of
  Reference Data); Λ4 witnessed-by-induction over bounded restatement
  chain; Λ8 witnessed via erasure-coding ε bound; Λ13 witnessed via TLA+
  Büchi automaton + bounded-horizon simulation + production observability.
- §6 footnote: "1 genuinely unwitnessed + 3 witnessed-via-composition.
  Surrogate parameters specified per `formalis_v2.md §7`."
- Sibling `nazarov_v2.md §2 N5` is **rewritten** as N5a–N5d:
  - **N5a** intra-system replay disputes (the v1 N5).
  - **N5b** input-correctness disputes — multi-source re-attestation chain,
    surrogate for Λ1.
  - **N5c** storage-integrity disputes — cross-replica verification +
    erasure-coded reconstruction, surrogate for Λ8.
  - **N5d** liveness-projection disputes — bounded-horizon structural
    induction + insurance/compensation backstop, surrogate for Λ13.
- C-A12 NEW (cross-replica integrity) added to realism budget (§10.2),
  binding to N5c.
- ADR-11 (public verification keys append-only) ratifies HSM rotation
  discipline, allowing N5a replay against pre-rotation envelopes.

**Verdict: CLOSED.** All four B-3 minimum-compliant fixes present:
(i) N5 split into four sub-protocols, each named with operational mechanism
not just data primitive; (ii) per-surrogate conditional assumption with
detection signal and compensating action; (iii) explicit ε / bounded-horizon
parameters live in formalis §7 and are referenced from the realism budget.

**Residual.** Λ4 (bitemporal coherence) — surrogate parameter `κ_restate`
(bounded restatement chain length) is named as "pinned in L7Pb" but the
*numeric* value is not in proposal_v2 §10. I'll surface as NM-3 below;
it's a parameterisation gap, not a B-3 reopen.

---

## §2. New findings (independent of R1)

### NM-1. Trust-assumption owners in proposal_v2 §10.2 are still job titles

**Severity.** UNMITIGATED MAJOR.

**Where.** §10.2 (the trust-registry-snapshot table inside the proposal_v2
document itself).

**Substance.** Of the 12 conditional assumptions listed in §10.2, exactly
**one** owner is a named natural person: C-A9 "Arjun Mehta (TEMPORAL
lead)". The remaining 11 are job titles or team designations:

- C-A1: "Head of cryptography (TBD; OPEN)"
- C-A2: "Head of security operations (TBD; OPEN)"
- C-A3: "Per-vendor named relationship owner (data ops)" — *no named
  vendor, no named relationship owner*
- C-A4: "Settlement-operations team lead"
- C-A5: "CDM/ISO interop lead (MATTHIAS in this team)" — *MATTHIAS is a
  reviewer pseudonym, not a person*
- C-A6: "Model-validation team lead"
- C-A7: "Identity-and-trust operations team lead"
- C-A8: "Architecture review board chair"
- C-A10: "Records management + compliance lead"
- C-A11: "TEMPORAL canonicalisation owner" — *role title, not person*
- C-A12: "Storage operations lead"

R1 NAZAROV M-2 said: "*C-A3 with owner 'per-vendor relationship owner' is
what an auditor would call no owner — the title belongs to no specific
person.*" v2 sibling `nazarov_v2.md §4.3` Trust Registry Contract specifies
the owner field as `(person_id, team_id)` — typed for concreteness. But
the consolidator's §10.2 has not been populated with the resulting names.

The only owners explicitly marked OPEN with deployment-block conditions
are C-A1 and C-A2. The other ten are presented as if owned, but are not.

**Why this is major and not blocking.** R1 NAZAROV M-2 graded this UNMITIGATED
MAJOR, not BLOCKING; the schema has been correctly specified (sibling §4.3),
the population is what is missing. Production deployment cannot proceed
without these names, but R2 review can.

**Required fix.**
1. Either populate §10.2 with concrete `(person_id, team_id)` for the 10
   currently-titled owners, or mark each as `OPEN — production deployment
   blocked on assignment` (the C-A1/C-A2 pattern).
2. C-A5 owner cannot be "MATTHIAS"; that is the reviewer pseudonym for the
   CDM cross-walk specialist, not a registry-owner identity.
3. C-A3 must show — at the consolidator level — the per-vendor fan-out
   that the §4.3 contract specifies. At minimum: a table of currently
   active gateway-signed vendors with their three decomposed assumption
   rows. If no vendors are yet onboarded, state so explicitly with
   N2.4 `max_gateway_signed_sources = 0` until vendor governance event.

**Owner of fix.** Data team in coordination with HR / legal / compliance
to surface concrete person assignments; output is a populated §10.2 with
zero job titles.

---

### NM-2. Trust registry artefact specified in sibling, not in proposal_v2

**Severity.** UNMITIGATED MAJOR.

**Where.** §10.2 closing line: "Trust-assumption registry artefact (closes
nazarov M-1): schema, review cadence, kill-switch per assumption. Detail in
`nazarov_v2.md §2 N12`."

**Substance.** A closure-check reviewer reading proposal_v2.md alone
encounters one sentence claiming the artefact exists, with detail
delegated to a sibling document. The sibling does specify the contract
(schema, edit discipline, review cadence, kill-switch list, retention). But
proposal_v2 itself does not surface even a one-paragraph summary of the
artefact's shape.

R1 nazarov M-1 said: "*Without the artefact existing as a concrete
specification, 'trust assumptions are first-class' is aspirational.*" The
sibling closes M-1 in substance. The proposal_v2 closes it by reference
only — which is fragile under: (i) sibling-file divergence (proposal_v2 is
the artefact reviewers attack; sibling could be amended out of sync); (ii)
new reader who treats proposal_v2 as the spec and never reads the sibling;
(iii) audit who reads proposal_v2 as "the document".

**Required fix.** Inline the trust-registry schema (10–15 lines) into
proposal_v2 §10.3 (NEW subsection). Specifically: the `TrustAssumption`
record schema, the edit discipline (governance event + two-eyes signoff),
the review-cadence enforcement (L13 obligation), the kill-switch list
(KS-A1 through KS-A12). This is no more than half a page; the gain is
that the *consolidator* document — the one R2 reviewers attack — contains
the artefact.

---

### NM-3. Surrogate parameters for Λ4 / Λ8 / Λ13 not in proposal_v2

**Severity.** UNMITIGATED MAJOR.

**Where.** §6 Λ-table; §17 open-issue 4 acknowledges the gap as a reviewer
verification task.

**Substance.** The §6 Λ-table classifies Λ4, Λ8, Λ13 as "witnessed via
composition" with surrogate-parameter strategy named in `formalis_v2.md §7`.
But the *numeric values* of the surrogate parameters — `κ_restate` for Λ4,
erasure-coding `(n, k, ε)` for Λ8, `T_max` and `N_handler` for Λ13 — do
not appear in proposal_v2.

R1 karpathy M4 / lattner M4 / nazarov M-3 audit-cadence finding all
required these parameters be specified, not just named. §17 open-issue 4
("Surrogate parameters for witnessed-via-composition laws are specified —
Λ4 retention horizon, Λ8 erasure-coding (n,k,ε), Λ13 T_max + N_handler")
treats the requirement as a reviewer-verification task, not as a
proposal-side commitment. This inverts the burden: the proposal should
*state* the parameters, the reviewer *verifies* them.

**Required fix.** Add proposal_v2 §6.1 (NEW): a table of surrogate
parameters by law, with numeric value (or explicit TBD-with-owner) per
parameter. At minimum:

| Law | Parameter | Value | Owner |
|---|---|---|---|
| Λ4 | `κ_restate` (max restatement chain length) | TBD-with-owner | Head of Reference Data |
| Λ8 | erasure-coding `(n, k)` | TBD | Storage operations lead |
| Λ8 | bit-flip detection probability ε | TBD | Storage operations lead |
| Λ13 | `T_max` (obligation deadline horizon) | TBD | CRO |
| Λ13 | `N_handler` (handler bounded delay) | TBD | TEMPORAL lead |

A proposal that ratifies four "witnessed via composition" reclassifications
without numeric parameters has converted four blocking findings into four
TBDs with names attached.

---

### NM-4. ADR-11 (HSM key rotation) lacks rotation-frequency commitment

**Severity.** MINOR.

**Where.** ADR-11 in §16: "Public verification keys append-only — HSM
rotation discipline; replay re-verify of old envelopes."

**Substance.** ADR-11 closes B-2-adjacent finding (Singleton 2 / correctness
A.3) by committing to append-only public verification keys, which is the
correct architectural property — replay against pre-rotation envelopes
remains verifiable. Sibling `nazarov_v2.md §2 N2.5` ratifies this
("Rotation MUST NOT invalidate prior envelopes").

But the rotation *cadence* is not specified anywhere I can see. Rotation
discipline has two parts: (i) the structural property (append-only,
chained valid_from / valid_to / succeeded_by), which v2 has; (ii) the
operational frequency (e.g., quarterly, post-incident, per FIPS 140-3
guidance), which is unstated.

**Required fix.** State the rotation cadence as a constants-module value
or mark TBD-with-owner. Recommended: add to constants-module per N2.4
discipline.

---

### NM-5. `single_source_authority_assumption_ref` registration discipline invisible at proposal_v2 level

**Severity.** MINOR.

**Where.** §5.1 first bullet (B-1 closure text); §1 L9 well-formedness
predicate.

**Substance.** §5.1 says L9 rows passing snapshot consumption must "carry
explicit `single_source_authority_assumption_ref` to the trust registry"
— but the discipline by which such a ref is *registered* is not stated.
Specifically: who has authority to register a unique-authority assumption?
What is the governance event? What detection signal and compensating
action attach to it? The sibling `nazarov_v2.md` registry schema has
`single_source_authority` as a `decomposition_class` value, but the
*creation rules* are inherited rather than spelled out.

If unique-authority refs can be created by any operator without governance,
the gate is hollow — single-source admission becomes self-attesting. This
is the same N2.4 governance event discipline that gateway-signed paths
required for B-2 closure; it should apply identically here.

**Required fix.** Extend N2.4 (governance-event discipline) to cover
`single_source_authority` registry rows: each requires governance event,
change-control reference, two-eyes signoff. Bound the count of admissible
single-source assumption refs (`max_single_source_authorities`) — by
default 0; non-zero requires explicit ratification.

---

## §3. Trust assumption registry — direct review

Per my standing deliverable list, I review the registry as if it were
the standalone artefact.

**Schema.** v2 (sibling §4.3) specifies `(assumption_id,
decomposition_class, scope, owner, violation_consequence, detection_signal,
compensating_action, blast_radius, review_cadence, last_reviewed_at,
next_review_due, kill_switch_id, change_control_ticket, attestor)`.
**Verdict: structurally complete.** Compares favourably to the Chainlink
DON's published trust assumption documents and to RedStone's signed-package
provenance schemas. Owner field typed `(person_id, team_id)` rather than
free string is correct and corrects R1 M-2 in principle.

**Edit discipline.** L11 transaction (policy change), two-eyes signoff,
downstream impact assessment for `detection_signal` or `compensating_action`
changes. **Verdict: correct.**

**Review cadence enforcement.** Each row has L13 obligation
`review_trust_assumption(assumption_id)` with deadline `next_review_due`.
Missed reviews escalate per L13 standard. **Verdict: correct — the L13
obligation type binds the registry into the witnessed-liveness regime.
This is exactly the kind of cross-binding the closed-system property
requires.**

**Kill-switch list.** KS-A1 through KS-A12 enumerated with trip /
behaviour / un-trip. **Verdict: complete in shape; KS-A3.[vendor] family
correctly per-vendor.**

**Population.** N=12 conditional + 3 × N_vendors decomposition rows. For
N_vendors = 10, that is 42 rows minimum. **Verdict: stated; per NM-1 the
actual population in proposal_v2 §10.2 is incomplete.**

**Retention.** Per C-A10 (longest applicable horizon). **Verdict: correct
in principle; per NM-3, the longest-applicable horizon is itself
unparameterised.**

**Overall.** The registry artefact is now a real specification (was R1's
M-1). One residual structural gap: the schema does not specify a `version`
or `succeeded_by_or_null` history-walking field as a first-class query (it
is implied in the storage discipline but not in the schema record). For
auditing the question "what was C-A3.bloomberg's detection signal three
years ago?", this matters. Surface as MINOR.

---

## §4. Threat model — re-running the four classes

Following my operating method §5.

| Attacker class | Capability | v1 mitigation (per R1) | v2 mitigation | Residual |
|---|---|---|---|---|
| Malicious vendor | Inject false price | Single-source pass | N8 multi-source aggregation gate (B-1 closed); N5b multi-source re-attestation dispute (B-3 closed) | Coordinated multi-vendor collusion — bounded by C-A3 with vendor diversity policy (TBD per leaf) |
| Malicious gateway | Re-sign altered vendor bytes | One trust row per gateway path | Three-row decomposition (vendor honesty / TLS / gateway operator) per N2.6 (B-2 closed); cert-pinning detection signal | Gateway operator collusion with vendor — explicitly carried as separate row; KS-A3.[vendor] kill-switch |
| Malicious operator | Forge envelope post-rotation | Implicit | Append-only verification keys per N2.5 / ADR-11; old envelopes still verify against historical key | Operator who can write to the verification-key registry — bounded by N12 governance events |
| Malicious consumer | Replay stale data | Snapshot pinning, hash chain | Plus boundary-integrity production test (GT1); cross-replica integrity per N5c / C-A12 | Quorum-bypass via replica compromise — bounded by replica diversity (TBD per NM-3) |
| Network adversary | Reorder, partition | Idempotency keys | Idempotency keys; canonical serialiser pin (RFC 8785 JCS) per ADR-6; cross-replica quorum | Long partition during reconciliation — covered by BreakRegister FSM |

**Verdict.** Threat model materially strengthened vs v1. All four R1 named
classes have first-class mitigations. The residuals are parameterisation
gaps (NM-3) rather than structural holes.

---

## §5. Verification approach for an auditor

How would an auditor confirm a candidate implementation satisfies these
requirements?

1. **B-1 audit.** Pull a sample of 1000 L19 snapshot constructions; for
   each, list the L9 rows admitted; assert every row has a typed
   `aggregation_outcome ∈ {multi_source_consensus, unique_authority,
   quarantined}`; assert no `quarantined` row was admitted; for every
   `unique_authority` row, assert the `single_source_authority_assumption_ref`
   resolves to a registered trust assumption with a non-expired
   `next_review_due`. Failure on any sample → finding.

2. **B-2 audit.** Enumerate every active gateway-signed path; for each,
   verify the trust registry contains *three* rows (vendor honesty / TLS /
   gateway operator integrity); verify the count of paths is below
   `max_gateway_signed_sources`; verify each new path admission was an L11
   governance event with change-control reference. Failure on any path →
   finding.

3. **B-3 audit.** For each of N5a/b/c/d, exercise the dispute resolution
   protocol against a synthesised dispute of the matching kind (intra-system
   replay; vendor-input-correctness; storage-integrity bit-flip;
   liveness-projection deadline). Verify the protocol terminates with a
   recorded resolution. Failure → finding.

4. **NM-1 audit (new).** §10.2 row-by-row: for each owner, attempt to
   resolve to a `(person_id, team_id)` record in HR. Job-title matches
   without person resolution → finding.

5. **NM-2 audit (new).** Reviewer reads only proposal_v2.md (no siblings);
   confirms trust-registry contract is fully specified. If the reviewer
   has to follow a reference to determine the schema → finding.

6. **NM-3 audit (new).** For each of `κ_restate`, `(n, k, ε)`, `T_max`,
   `N_handler`, find a numeric value in a constants module pinned via L21.
   TBD without owner → finding.

---

## §6. Consolidated closure verdict

| R1 NAZAROV finding | Closure status |
|---|---|
| B-1 (L13 calibration N8 gate) | **CLOSED** |
| B-2 (gateway-signed compound trust) | **CLOSED via sibling**; presentationally fragile (NM-1, NM-2) |
| B-3 (N5 dispute resolution insufficient) | **CLOSED** |
| M-1 (trust registry artefact) | **CLOSED via sibling**; presentationally fragile (NM-2) |
| M-2 (C-A1/C-A2 owners TBD) | **PARTIALLY CLOSED** (C-A1/C-A2 explicitly OPEN with deployment-block); 10 other owners are still job titles (NM-1) |
| M-3 audit cadence inline | **CLOSED** (sibling §4.6) |
| M-5 (graceful degradation typed read API) | **CLOSED** (sibling §3) |
| M-6 (malformed envelope) | **CLOSED** (sibling §2 N3.4) |
| m-2 (L7 cap) | **CLOSED** (V9 CI mechanism, ADR-12) |
| m-3 (audit cadence) | **CLOSED** |
| m-4 (L24 instability) | **CLOSED** (L24 deleted; ADR-3 / ADR-4 sub) |
| m-5 (C-A10 horizon) | **PARTIALLY CLOSED** (sibling retention matrix; numeric horizons still TBD per NM-3) |

**New findings (this review):**
- NM-1 owners still job titles in §10.2 — UNMITIGATED MAJOR
- NM-2 trust registry artefact in sibling not consolidator — UNMITIGATED
  MAJOR
- NM-3 surrogate parameters numeric values absent — UNMITIGATED MAJOR
- NM-4 HSM rotation cadence missing — MINOR
- NM-5 `single_source_authority_assumption_ref` registration discipline
  invisible — MINOR

**Three R1 BLOCKERS: closed.** The proposal addresses every minimum-compliant
fix I named in R1, with the substance carried in `nazarov_v2.md` and the
shape ratified in proposal_v2 ADRs. The architectural posture has shifted
from "trust me, we've thought about it" to "every assumption has a
decomposition, an owner, a detection signal, a compensating action, a
blast radius". This is the move from rumour to attestation. The
unwitnessed-laws restructuring (1 + 3) is correct.

**Three new UNMITIGATED MAJORs.** None of these reopens a R1 blocker; all
three are about the proposal_v2 *artefact* under-surfacing what the
sibling has correctly specified. The fixes are inline insertions of
existing sibling content (10–30 lines per finding).

---

## §7. Grade

**Grade: B+** (was B−).

**Rationale.** A full letter grade up. The three R1 BLOCKERs are
substantively closed — gate, decomposition, dispute-protocol-split — at a
quality level that compares favourably to Chainlink DON architectural
documents. The realism budget has typed owners with detection /
compensating action / blast radius (the ADR-1-equivalent move RedStone
made for signed-package custody disclosure). The trust-registry contract
exists as a real artefact with edit discipline, review cadence enforcement,
and kill-switch enumeration. Λ-renaming closes the L-prefix collision that
made v1 painful. The N5 split into N5a/b/c/d is the cleanest closure I
have seen for the four-unwitnessed-laws problem in any Phase 2/3 round.

**Why not A−.** Three UNMITIGATED MAJORs (NM-1, NM-2, NM-3) prevent the
proposal from being self-contained: a reviewer cannot grade *this document*
without reading siblings. NM-1 leaves trust-assumption ownership at
job-title resolution for 10 of 12 rows — auditability remains aspirational
until concrete persons land. NM-3 leaves the surrogate parameters that
*define* whether Λ4/Λ8/Λ13 are actually witnessed at all as TBDs.

**Path to A−.** Inline 30 lines of sibling content (NM-2), populate 10
names (NM-1), pin five numeric parameters or mark each TBD-with-owner
(NM-3). NM-4, NM-5 are MINOR and can ride. R3 should converge if these
land.

**Convergence.** Not yet converged for NAZAROV — three UNMITIGATED MAJORs
remain. But on the path of closure: every UMAJ is a presentation /
parameterisation gap, not a structural defect. R3 should close them.

---

**Reviewer note.** I wrote this review without consulting `phase2/nazarov_v2.md`
during initial reading of proposal_v2; I consulted the sibling only after
forming closure verdicts on the consolidator alone, in order to verify the
substance behind references. That sequence is what made NM-1 and NM-2
visible: the substance is correct, but it is not in the document
reviewers attack. A R2 reviewer who reads proposal_v2 alone (as instructed
in §18) will not see the closures I verified.

— NAZAROV (independent R2 instance)
