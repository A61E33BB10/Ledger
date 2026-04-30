# Phase 3 — Round 1 — NAZAROV adversarial review (independent reviewer)

**Reviewer.** Independent NAZAROV instance. The Phase-2 `nazarov.md` was
authored by a sibling NAZAROV; I have re-read it and the proposal_v1.md
adversarially. I treat the sibling's bar as input — not as my own bar — and
attack it the way I attack any external claim: assume adversarial until
attested.

**Mode.** Find blocking issues, unmitigated major issues, and minor issues.
Issue a grade.

**Reading lens.** I hold the boundary. Every datum is either provably right
or has survived enough independent checks that we have no remaining reason
to believe it is wrong. I am unsentimental about the work of my sibling.

---

## §0. Verdict (read this first)

**Grade: B−.**

The 24-leaf spine is sound. The NAZAROV bar (N1–N12) is genuinely a floor
in *intent* — but the bar is **insufficiently tight in five specific places**
that, on adversarial reading, leave the boundary leaky. The realism budget
correctly names 10 conditional assumptions, but **at least three are
"owned" only nominally** — the named owner is a job title, not a person, and
the violation-detection signal is described in language that no operations
team could implement as written.

Most importantly, the proposal contains **two latent silent-vendor-trust
paths** (findings B-1 and B-2 below) and **one structural defect in N5**
(finding B-3) that means dispute resolution as specified will work for L10,
L12, L14 — but not for L1, L4, L8, or L13 in the way claimed. These are
blocking.

If the team addresses B-1, B-2, B-3 in proposal_v2 and tightens M-1 through
M-6, this becomes a strong (A−) data-layer specification. Until then, I
would not pass it through the boundary-integrity gate.

**Findings count.**
- 3 blocking
- 6 unmitigated major
- 5 minor
- 1 commendation (a section that is genuinely better than the floor demands)

---

## §1. Blocking findings

### B-1. L13 calibrated market objects depend on L10 with no documented "fed clean inputs" gate.

**Where.** §3.4 L13 ingress text: "*synchronous output of the calibration
workflow; written to L13 only when `certified = true`*". §1 conviction 6
(in the system prompt I myself carry): "**Attestation is upstream of
filtering.** The filter must see certified, multi-source-aggregated,
signature-verified observations — not raw vendor payloads."

**The defect.** The Kalman filter consumes L10 raw market observations.
The proposal says L10 carries an attestation envelope and that vendor
restatements arrive as new rows. It does **not** require that L10 has
**already passed N8 multi-source aggregation** before reaching the
filter. As specified, a single-source L10 row with a valid envelope is
admissible into the calibration input snapshot.

A coordinated adversarial vendor — the canonical NAZAROV concern, lifted
verbatim from the C-A3 conditional assumption — could feed gradually
manipulated quotes. The innovation gate is a statistical defence; my
sibling correctly notes (and I agree) that statistical defences are
insufficient when manipulation is gradual. The defence is upstream
attestation aggregation, not downstream filtering.

The sibling's N8 is the right requirement, but the sibling's §3.4 L10
ingress says "applies bitemporal sanity checks" — it does **not** say
N8 multi-source aggregation is gating ingress to L19 snapshots. The L10
description (§3.4 first bullet) says the gateway signs and the row is
appended to the bitemporal index. **Aggregation is not enforced before
the row reaches the snapshot the filter consumes.**

**Why this is blocking.** Without an N8 gate between L10 and L19, every
calibration certification (L13) is conditioned on the unstated assumption
"every individual L10 row in the snapshot is itself trustworthy". That is
exactly the silent vendor trust the bar is meant to forbid.

**Minimum compliant fix.**
1. Add **N3.4** (or strengthen N8): L10 rows admitted to a snapshot
   (L19) consumed by L13 calibration MUST have passed multi-source
   aggregation per N8 *before* snapshot inclusion, or carry an explicit
   `single_source_authority_assumption_ref` pointing into the trust
   registry.
2. Add to L19 snapshot canonical content: a per-row `aggregation_outcome`
   (a typed enum: `multi_source_consensus | unique_authority | quarantined`).
   This means snapshot determinism captures *whether* aggregation happened,
   not just *what* the value was.
3. Add to §6 audit step 4 (bitemporal): an aggregation-coverage audit —
   sample calibration snapshots, confirm zero rows with implicit single-source
   trust without a registry-linked assumption.

**Owner.** Data team must update proposal_v2.

---

### B-2. The "ingestion gateway signs under a named gateway key" path silently re-introduces vendor trust at scale.

**Where.** N2.2: "*Where a vendor cannot sign, signing MUST happen at the
ingestion gateway under a clearly identified gateway key, AND the
resulting trust assumption ('we trust gateway X to faithfully report what
vendor Y said over TLS') MUST be a named, owned trust assumption in the
registry.*"

**The defect.** N2.2 is correct in principle but specifies only *that* a
trust assumption must exist, not *what its content must be* nor *how
many gateway-signed paths are admissible*. In practice, every vendor
that lacks signed-at-source data (which is most vendors today, including
many of the named market-data vendors in §3.4 — Bloomberg, Refinitiv,
SIX, ICE Data) collapses to one trust assumption per vendor.

The C-A3 budget item is stated **once** but is silently invoked **per
vendor**. A 50-vendor production deployment carries 50 instances of
C-A3, each with its own owner, freshness contract, and detection signal.
The proposal does not require this fan-out to be enumerated.

**Worse.** N2.2 says the trust assumption applies to "what vendor Y said
over TLS". But TLS terminates at the gateway. The gateway sees the
vendor's bytes; if the gateway is compromised, *every* gateway-signed
attestation is forged. The trust assumption is therefore a compound
"trust the vendor AND the TLS chain AND the gateway operator's process
discipline" — but it is registered as a single line.

**Why this is blocking.** The sibling's own N12.2 forbids exactly this:
"Trust the vendor feed" without scope-explicit decomposition is forbidden.
But N2.2 as written manufactures these compound trust assumptions and
N12.2 does not catch them, because they have *names* (just bad ones). The
boundary leaks vendor trust through the gateway path in a way that the
trust registry does not adequately constrain.

**Minimum compliant fix.**
1. N2.2 must require, for each gateway-signed source, a **per-vendor row in
   the trust registry** (not one row per gateway). Each row decomposes:
   (a) vendor honesty assumption, (b) TLS chain freshness assumption,
   (c) gateway operator integrity assumption — three rows, three owners,
   three detection signals.
2. Add **N2.4**: the count of gateway-signed paths admissible at any time
   MUST be bounded by an explicit policy (L7 field: `max_gateway_signed_sources`).
   Adding a new gateway-signed source MUST be a governance event with
   change-control reference. Otherwise the boundary acquires unsigned-at-source
   exposure monotonically and silently.
3. Add to §6 audit a step: enumerate every active gateway-signed path; verify
   each has its three decomposed registry rows; verify the count is below
   policy bound.

**Owner.** Data team + identity-and-trust operations to update proposal_v2.

---

### B-3. N5 dispute-resolution path is structurally insufficient for the four unwitnessed CORRECTNESS laws.

**Where.** N5 (entire) + §9.4 of proposal_v1 ("**Phase 3 must rule on
whether the surrogate strategies are accepted as proxies, or whether the
unwitnessed laws are themselves accepted as architectural risks**").

**The defect.** N5.1 says the data layer "MUST provide an as-known-at-t
replay primitive that returns the bit-identical content the workflow
consumed". This works for L10 (raw observation), L12 (external confirmation),
L14 (move stream), L15 (valuation record) — all of which have a
ground-truth primary attestor whose signed payload exists somewhere
recoverable.

It does **not** work for the four CORRECTNESS unwitnessed laws:

- **L1 Lineage Closure under vendor opacity.** "Bit-identical replay"
  requires the inputs to be reconstructible. If a vendor's payload is
  itself partially manipulated (the C-A3 violation case), the bit-identical
  replay will faithfully reproduce the manipulated input — and the
  dispute is *whether the input was right*, not whether we processed it
  correctly. N5 resolves "did we compute it consistently" but does not
  resolve "was the input attestation itself trustworthy".

- **L4 Bitemporal coherence under unbounded restatement chains.** If a
  vendor restates 12 times, with the 13th restatement disputed, N5.1
  produces 13 bit-identical replays — none of which resolves which
  restatement reflects the truth. The dispute is between two restatements,
  not between us and the vendor.

- **L8 Replay determinism under cosmic-ray bit flips / silent corruption.**
  N5.2 says replay is "cryptographically verifiable against the original
  attestation and the original hash-chain anchor". If the storage medium
  silently flipped a bit and the L22 anchor matches the flipped state
  (because the anchor was computed *after* the flip), N5 cannot detect
  the corruption. It can detect tampering against the anchor; it cannot
  detect tampering of the anchor itself unless cross-replica verification
  is mandated — which N5 does not require.

- **L13 Obligation liveness over unbounded futures.** N5 has no role here
  — disputes about whether an obligation *will be* discharged on a future
  deadline are not about replay; they are about projected behaviour. N5
  is silent on the entire law.

**Why this is blocking.** The proposal claims (proposal_v1 §9.4) that
"surrogate strategies are sketched but not validated" and asks Phase 3 to
rule on them. **Surrogate strategies for L1, L4, L8, L13 are not in the
NAZAROV section.** They are in the CORRECTNESS section, behind a reference.
The NAZAROV bar implicitly claims to provide dispute resolution but does
not say "for L1, L4, L8, L13, dispute resolution requires an *additional
mechanism beyond N5*". This is the silent gap.

**Minimum compliant fix.**
1. Split N5 into N5a (intra-system replay disputes — bit-identical replay,
   the current text), N5b (input-correctness disputes — multi-source
   re-attestation chain, the surrogate for L1), N5c (storage-integrity
   disputes — cross-replica verification + erasure-coded reconstruction,
   the surrogate for L8), N5d (liveness disputes — bounded-horizon
   structural induction + insurance/compensation backstop, the surrogate
   for L13).
2. For each, name the operational protocol that resolves the dispute, not
   just the data primitive that supports it.
3. Add to §4 realism budget: explicit conditional assumption per surrogate
   (e.g., **C-A11**: cross-replica integrity — at least N=3 independent
   replicas with pair-wise hash comparison for L8 silent-corruption
   detection).

**Owner.** Data team in coordination with CORRECTNESS to update proposal_v2.

---

## §2. Unmitigated major findings

### M-1. The trust assumption registry is described as a deliverable but its concrete artefact does not exist.

**Where.** N12 + §4.2 list 10 conditional assumptions with named owners
and detection signals. There is no actual registry document referenced by
file path.

**The defect.** A trust assumption registry is a living artefact — a
table that is *queryable* by ops, *auditable* by compliance, *kept current*
by a named team. The proposal lists assumptions but does not specify:

- Where the registry lives (DB table? structured YAML? SoR?).
- Who edits it under change control.
- What its review cadence actually is (each assumption says "periodic"
  or "quarterly" but the cadences are not collected).
- How a violation-detection signal is wired to a kill-switch (N12.3 says
  "kill-switch specified" but no kill-switch is specified for any of the
  10 assumptions).
- What happens when a row is deleted (data-retention rules for the
  registry itself).

**Why this is major.** Without the artefact existing as a concrete
specification, "trust assumptions are first-class" is aspirational, not
operational. C-A3 with owner "per-vendor relationship owner" is what an
auditor would call *no owner* — the title belongs to no specific person.

**Mitigation.** proposal_v2 must include a registry schema (fields,
types, constraints), a review-cadence table, and a kill-switch
specification per assumption. The registry itself can be deferred to
implementation, but the *contract* the registry must satisfy must be
specified at the bar level.

---

### M-2. C-A1 (cryptographic primitive soundness) and C-A2 (HSM) are owned by "TBD-with-owner" / job titles only.

**Where.** §4.2 C-A1 *Owner: head of cryptography (or external advisor)*.
C-A2 *Owner: head of security operations*.

**The defect.** "Head of cryptography" is a role; the project may not
have one yet. The deferral discipline is correct (defer primitive choice
to a cryptographer) but the **proposal commits to an unconditional
guarantee that a person who does not exist will ratify**. This is a
Conway's-law trap: by the time someone is hired, the primitive choices
are baked into the snapshot canonical-serialise format and rotation
becomes architectural surgery.

**Mitigation.** Either (a) name an external cryptographic advisor as the
interim ratifier and place a named person in C-A1's owner field, or (b)
explicitly mark C-A1 / C-A2 as **OPEN — no current ratifier; production
deployment blocked on assignment**. Treating an unowned conditional
assumption as if it were owned is itself a violation of N12.2.

---

### M-3. Mapping-layer determinism (N11) does not address the synonym-mapping ambiguity surface.

**Where.** N11.1: "*Mapping ... MUST be deterministic, total over a
documented input domain, and version-pinned (L21).*"

**The defect.** "Deterministic and total" is correct — but N11 does not
require the mapping to be **bijective** on the round-trip (FpML →
internal → FpML must produce the original FpML, modulo a documented
canonicalisation). Without round-trip discipline:

- A re-export of a CDM-mapped trade for regulatory submission may differ
  bit-wise from the original, even with deterministic mapping, because
  CDM synonyms are not bijective.
- C-A5 (schema stability) says "round-trip test failures" are the
  detection signal — but no requirement says round-trip must hold.

This is exactly the C-A5 violation being detected, but the test would be
testing a property the bar does not require.

**Mitigation.** Add **N11.4**: for every ingress path that may be
re-exported (L1 ProductTerms in regulatory submission, L14 MoveStream in
SFTR/EMIR/SLATE reporting), the mapping MUST be either bijective on the
relevant round-trip or carry an explicit lossy-canonicalisation declaration
in the mapping version pin.

---

### M-4. L24 Orchestration State is half-admitted, half-vetoed — the reconciliation is unstable.

**Where.** §3.6 L24 + §9.2 reconciliation note ("L24 is replay-substrate
only; not referenced by economic invariants").

**The defect.** The proposal says (a) L24 is on the spine, (b) it is
"replay-substrate only", and (c) "no economic invariant references L24
directly". But the proposal **does** carry CORRECTNESS L10
(workflow-history replay coherence) which directly references L24 in its
witness condition. So statement (c) is false in the small.

The TEMPORAL-owned C-A9 (workflow-history determinism) is a load-bearing
realism budget item. If an economic invariant (e.g., obligation liveness
L13) depends on a non-economic assumption (workflow-history determinism),
then L24 *is* economically load-bearing in effect, even if not by name.

**Mitigation.** Either (a) accept that L24 is in fact an economic
dependency and update the realism budget to make C-A9 a *primary* (not
"mentioned for completeness") assumption with detection signals owned by
the data team's compliance posture, or (b) re-state CORRECTNESS L10 such
that it does not transitively bind L13 obligation liveness to C-A9. The
current text papers over the dependency.

---

### M-5. N7.3 "graceful degradation" carries an unstated trust assumption.

**Where.** N7.3: "*'degrade gracefully' is permitted only when the
degraded behaviour is itself attested and quality-flagged downstream
(e.g., Valuation FSM `STALE` state per valuation v1.0 §2)*".

**The defect.** "Quality-flagged downstream" is a contract; the proposal
does not require the **consumer of the flag** to honour it. A downstream
PnL-explain process could read a `STALE` valuation and use it as if it
were `FIRM`. The flag without an enforced consumer obligation is a
suggestion, not a guarantee.

The N7.3 mechanism is correct at the producer; nothing at the consumer
side prevents misuse.

**Mitigation.** Add **N7.4**: every downstream consumer of a quality-flagged
datum MUST declare its quality-acceptance policy (the maximum quality
class it will consume for each downstream effect) and the storage layer
MUST enforce it via a typed read API that refuses below-policy reads.
Otherwise N7.3 is theatre.

---

### M-6. The proposal does not specify what happens when the L17 attestation envelope itself is malformed.

**Where.** N2 + N3.

**The defect.** N3.2 requires validation of "(c) attestation verification".
A failed verification quarantines the datum. But what if the envelope
itself is structurally malformed (missing field, wrong format, signature
algorithm not in the closed enum)? The path is implicit: presumably
quarantine via N3.3. But because L17 is itself the attestation, its
validation failure is fundamentally different from the *content* failing
validation — there is no attested provenance for a malformed attestation,
which is the limiting case.

If a pile of malformed envelopes arrives, where do they go? They cannot
be stored alongside the datum (no datum is admitted). The "failed-ingest
record" must itself be attestable somehow. The proposal does not say so.

**Mitigation.** Add **N3.4**: failed-ingest records carry a gateway-attested
envelope **about the failure event**, not about the datum. The gateway
attests "I, gateway X, received the following bytes from source Y at
time T and was unable to validate the L17 envelope for reason Z". This
makes the failure itself first-class data with provenance.

---

## §3. Minor findings

### m-1. §1.4 L4 Calendar/Convention does not specify retroactive amendment policy.

The bar says (N9) append-only and (N6) bitemporal. But TEMPORAL §6.1
flagged retroactive calendar amendments as the worst-fit category. The
NAZAROV section needs a one-line policy: retroactive holiday additions
are **L4 versions with later `t_known` and earlier `effective_date`**;
they invalidate downstream `now()` reads of calendars in workflows that
have already executed. Repair is via re-running affected workflows from
the last-good snapshot, not by mutating L4. This should be explicit at
the bar level rather than in TEMPORAL's tension list.

### m-2. L7 Policy / Configuration is described as "thin sidecar (≤30 fields)" but the bound is decorative.

The reconciliation with V9 (jane-street veto) says L7 is bounded at "~30
fields" to honour the veto. There is no enforcement mechanism. A schema
test in CI is the minimum; the bar should say so.

### m-3. The §6 verification approach lists 10 audits but does not specify how often each runs.

For a candidate implementation, "satisfies the bar" is point-in-time.
For a production implementation, "continues to satisfy" is a cadence
problem. The proposal should specify minimum audit cadence per item
(e.g., audit 1 boundary inventory: per release; audit 5 trust registry
walk: quarterly; audit 10 closed-system perimeter test: per release +
quarterly fuzz).

### m-4. The realism budget has 8 unconditional + 10 conditional = 18, but no item covers "downstream consumer correctness".

The budget is upstream-of-the-data-layer. There is no item for "the
consumer of the data layer reads it correctly". If a workflow misreads
a snapshot ID and feeds the wrong snapshot to the Kalman filter, that's
an executor concern, not a data layer concern — but the realism budget
should at least *name the boundary* and disclaim it explicitly. Currently
the omission is silent.

### m-5. C-A10 (retention sufficiency) does not address the longest-running unit class.

C-A10 says retention must cover "the longest-running unit's lifetime +
the longest dispute window + the longest regulatory record-keeping
requirement". The longest-running unit class in this stack is potentially
**a 50-year covered bond** or **a perpetual issuance**. Stating C-A10
without a numeric placeholder ("retention horizon: TBD years, decided
by [owner]") leaves the assumption open. A perpetual unit cannot
satisfy a finite retention horizon — that is itself a bar finding.

---

## §4. Commendation (one section is genuinely better than the bar demands)

**§5 "What I refuse to admit, and why"** is excellent. It is a
seven-bullet list of refusals, each tied to a numbered N-rule, each with
a one-line justification. This is the kind of artefact an architecture
review board can hold to. The bar would be improved by lifting this
section into a formal "veto list" parallel to jane-street's V1–V14, so
that the boundary's refusals are first-class deliverables alongside the
boundary's requirements.

---

## §5. Where the proposal silently degrades to "trust the vendor"

This question is in the user's prompt; I answer it explicitly here.

The four silent vendor-trust paths I found (in order of severity):

1. **B-1 above.** L13 ingest from L10 without N8 aggregation gate.
2. **B-2 above.** N2.2 gateway-signed paths collapsing N+M trust into
   one budget line.
3. **§3.1 L2 Instrument Master ingress.** "*Vendor signature on each batch
   + multi-vendor reconciliation gate per N8 (two-source agreement
   before admitting to L1; disagreement quarantines pending
   reconciliation)*". The "two-source agreement" is named but the bar
   (N8) says quorum and aggregation function are leaf-specific. The L2
   spec does not pin them. A two-source agreement with one corrupt
   source and one honest source is 50/50, not consensus.
4. **§3.4 L13 attestor**: "*The workflow's signed identity (L23
   capability for the calibration role) is the attestor*". The attestor
   for a calibrated market object is the **workflow signing its own
   output**. This is correct — but the trust here is "the workflow code
   is what it claims to be", which is C-A8 (closed-system boundary
   integrity). C-A8's owner is "architecture review board" — see M-2 on
   ownership thinness.

---

## §6. Are the 10 conditional assumptions actually owned?

This question is in the user's prompt; I answer it explicitly.

**Genuinely owned (named function with concrete operational responsibility):**
- C-A4 settlement-layer SSI freshness — settlement-operations team.
  Ownership credible because v10.3 §9.1 already places L5 outside the
  Ledger boundary; there is a separate team.
- C-A5 schema stability — MATTHIAS / CDM interop lead. Concrete
  individual scope.
- C-A6 calibration model soundness — model-validation team.
- C-A10 retention — records management + compliance.

**Owned in name only (job title, no clear individual):**
- C-A1 cryptographic primitive — "head of cryptography or external advisor".
- C-A2 HSM — "head of security operations".
- C-A3 vendor honesty — "per-vendor relationship owner".
- C-A7 authority registry — "identity-and-trust operations".
- C-A8 closed-system boundary integrity — "architecture review board".

**Disclaimed but load-bearing:**
- C-A9 workflow-history determinism — "TEMPORAL (this is their section,
  not mine)". See M-4 on the L24 instability.

So **5 of 10 are genuinely owned; 5 are nominally owned**. This is below
the threshold I would expect for production sign-off.

---

## §7. Summary table

| # | Type | Claim | Severity |
|---|------|-------|----------|
| B-1 | Blocking | L13 calibration consumes L10 without N8 aggregation gate | Boundary leak |
| B-2 | Blocking | N2.2 gateway-signed paths collapse multi-vendor trust into single budget rows | Boundary leak |
| B-3 | Blocking | N5 dispute resolution structurally insufficient for L1, L4, L8, L13 | Bar incomplete |
| M-1 | Major | Trust assumption registry is described as deliverable but artefact unspecified | Operational gap |
| M-2 | Major | C-A1, C-A2 owners are TBD/job-titles | Ownership thin |
| M-3 | Major | N11 mapping determinism does not require round-trip bijection | Re-export risk |
| M-4 | Major | L24 / C-A9 reconciliation is unstable; obligation liveness transitively binds workflow-history determinism | Realism budget defect |
| M-5 | Major | N7.3 graceful degradation does not bind downstream consumers | Quality-flag theatre risk |
| M-6 | Major | Malformed L17 envelope handling unspecified | Boundary edge case |
| m-1 | Minor | L4 retroactive calendar amendment policy not at bar level | Specification gap |
| m-2 | Minor | L7 ≤30 fields bound has no enforcement | Decorative bound |
| m-3 | Minor | §6 audit cadences unspecified | Operational gap |
| m-4 | Minor | Realism budget silent on downstream consumer correctness | Scope omission |
| m-5 | Minor | C-A10 retention has no numeric horizon for perpetual units | Open parameter |
| C-1 | Commend | §5 "What I refuse to admit" is a model artefact | Lift to bar level |

---

## §8. Verification approach for proposal_v2

If the team produces a proposal_v2 addressing B-1, B-2, B-3 and the six
major findings, my Round-2 review will check:

1. Does proposal_v2 enforce N8 aggregation between L10 and L19 with a
   typed `aggregation_outcome` field captured in snapshot canonical
   serialisation? (B-1)
2. Does proposal_v2 require per-vendor decomposed trust registry rows
   and a policy bound on gateway-signed source count? (B-2)
3. Does proposal_v2 split N5 into N5a–N5d with named operational
   protocols for each unwitnessed-law surrogate? (B-3)
4. Does proposal_v2 specify a registry schema, review cadence, and
   kill-switch contract? (M-1)
5. Does proposal_v2 either name individual owners for C-A1/C-A2 or mark
   them OPEN with deployment block? (M-2)
6. Does N11 require round-trip bijection or explicit lossy declaration?
   (M-3)
7. Is C-A9 promoted and the L24 reconciliation re-stated to remove
   transitivity through L13? (M-4)
8. Does N7.4 (or equivalent) bind downstream consumers via typed read
   API enforcement? (M-5)
9. Does the bar specify how malformed L17 envelopes are themselves
   provenanced? (M-6)

Until all three blocking findings are addressed, my grade stands at B−
and I do not recommend convergence.

---

**End of Phase 3 Round 1 NAZAROV adversarial review.**
