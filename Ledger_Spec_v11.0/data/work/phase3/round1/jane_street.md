# JANE-STREET-CTO — Phase 3 Round 1 Adversarial Review

**Reviewer.** Independent jane-street-cto instance (fresh context).
**Target.** `phase2/proposal_v1.md` (Phase-2 Synthesis Proposal v1).
**Input acknowledged.** A separate jane-street-cto instance authored
`phase2/jane_street.md` (the "P1–P10 / V1–V14 / 7-sector" position). I
treat that file as *input*, not as authority. The question for this
review is: **does the synthesis proposal honour what that file
demanded, or did it pay lip service and grow back the bloat?**

**Mode.** Adversarial. The brake stays on.

**Verdict.** **REQUEST CHANGES.** The proposal absorbs my P1–P10 cleanly
but launders four of my fourteen vetoes (V8, V9, V10, V11) through
weasel-word reconciliations that re-admit the very abstractions the
vetoes deleted. It also inflates 7 sectors back into 24 leaves, a
3.4× count creep that V7 explicitly forbids, and dresses it up by
calling the inflation "refinement". This is exactly the failure mode
the veto list was written to prevent.

---

## §0. The single dominant finding

The Phase 2 jane-street file demanded **seven sectors**. The synthesis
landed on **24 leaves across six classes plus eight C6 leaves**. The
reconciliation in §2.3 says "no contradictions; specialists refine within
NAZAROV's spine". This is a category error.

Seven sectors is not a *coarse* version of 24 leaves. Seven sectors is
the **upper bound on permissible complexity** as stated by V7. The
synthesis treats my count as a low-resolution sketch to be refined; the
actual demand was an inviolable ceiling. The proposal silently swapped
"cap" for "sketch" and called it integration.

If I had wanted 24 leaves I would have said 24 leaves.

This single substitution is the source of every BLOCKING finding below.

---

## §1. BLOCKING findings

### B1. V7 (count inflation) is violated by the synthesis itself

**Veto.** "Resist count creep; collapse on mutation discipline. ~3 + 4 = 7
sectors; if the proposal returns at 10/12/14 it is wrong." (`jane_street.md`
§2 V7, §3.)

**Status.** Violated.

The proposal carries 24 leaves explicitly, plus admits MATTHIAS-62 and
MINSKY-41 as "non-contradictory refinements" (§2.3). §9.1 says "adopt
NAZAROV's 24". My ceiling was 7. The document calls 24 "canonical"
without ever justifying why 24 is the correct count rather than 7, 16,
or 31 — it picks 24 because *every other count maps cleanly into it*
(§0 anchor 1). That is a mapping argument, not a budget argument.
Mapping is cheap; complexity budget is the constraint.

**Required fix.** Either:
1. Collapse to ≤7 sectors and present the 24-leaf view as a query lens
   (the same move §2 V1 made for the three-tier Unit Store — a query
   lens, not three databases). The 7 sectors then *are* the data layer;
   the leaves are pedagogical projections. Make this explicit in §2.
2. Or argue, sector-by-sector, why each sector beyond 7 discharges a
   concrete claim from v10.3 + addendum + valuation that no member of
   the 7-sector set discharges. The argument must be specific. "NAZAROV
   wanted it" is not an argument.

I will reject (2) for any sector whose concrete claim is already
discharged by an existing sector under a sum-type variant. I expect
(2) to fail for L4 (calendar — folded into Reference), L5 (SSI —
boundary, V10), L7 (Policy — V9 narrow form), L11 (oracle attestation —
sub-stream of Attestation, A6), L12 (external confirmation — also A6),
L18–L22 (provenance fields, not sectors, A21/A24).

### B2. V11 reconciliation is non-functional; L24 is back as ledger data

**Veto.** "Workflow / Orchestration State as ledger data. Replay
substrate, not the economic spine." (V11.)

**Status.** Lip service.

The proposal claims the reconciliation in §3.6 L24 honours the veto by
labelling L24 "replay-substrate only; not economic data". But L24 is
listed as a leaf in C6, with N/M/T/R/F/C entries, formal invariant
counts (`3T + 3W + 1C = 7 invariants`, §3.6 L24 from FORMALIS), and a
participating consistency law (L10 in §4). FORMALIS L13 = L24. CORRECTNESS
L10 references L24. Compositional theorem 2 (§8) names "workflow-history
determinism (C-A9)" as a load-bearing precondition.

If a leaf has invariants, participates in cross-layer laws, anchors a
compositional theorem, and earns named conditional assumption C-A9 with
a TEMPORAL owner — **it is ledger data**. The label "replay substrate"
is a sticker over the same shape.

V11's intent: workflow histories live in Temporal; the ledger stores a
foreign key (`workflow_id`) on the relevant transaction; the ledger does
not specify, store, or invariant-check workflow-history content. The
proposal's L24 specifies all three.

**Required fix.** Delete L24 from the leaf taxonomy. Replace with: "every
L14 transaction carries `(workflow_id, run_id)` as a foreign-key tuple;
the Temporal cluster is the authoritative store; replay determinism is
a Temporal contract documented in `temporal.md` §C-A9, not a ledger
invariant." Compositional theorem 2 then becomes a *cross-system*
property (Ledger × Temporal), not a ledger property — that distinction
matters for who owns the failure.

### B3. V10 reconciliation is non-functional; L5 is back as ledger data

**Veto.** "A separate settlement-layer data sector. SSI lives at the
boundary; the Ledger consumes, does not own." (V10.)

**Status.** Same shape as B2.

The proposal §3.1 L5 admits "SSI / Settlement Infrastructure" as a
leaf, lists owner `ssi-ingest`, names workflow obligations (`Activity
result + bitemporal restatement`), names CDM gaps (Rosetta sketch
needed), names FORMALIS structural placement ("part of L2"), and
participates in CORRECTNESS L3 + L14. The reconciliation in §3.1
("L5 is admitted as a leaf at the boundary contract level; the Ledger
consumes but does not author") admits an `ssi-ingest` workflow inside
the Ledger spec (§3.1 L5 N-line). An ingest workflow is authoring.

**Required fix.** Delete L5 from the leaf taxonomy. SSI is a row inside
the Reference family (A20 in `jane_street.md` §4) with `kind = SSI`, no
distinct sector, no Ledger-owned ingest workflow. The settlement layer
is responsible for its own freshness; the Ledger reads from the
Reference snapshot at projection time. C-A4 stays; the leaf does not.

### B4. V9 reconciliation re-admits Policy as a sector

**Veto.** "Configuration / Policy as a load-bearing first-class sector.
Policy is a thin sidecar, not a parallel data spine." (V9.)

**Status.** Half-honoured, half-violated.

The reconciliation (§3.1 L7 tension box) caps L7 at "≤30 fields". My
own narrow form (`jane_street.md` §2 V9: "single bitemporal
`PolicyConfig[id]` map with one row format and one ingest path") is
**not the same as a leaf with its own owner workflow
(`policy-governance`), realism class, FORMALIS invariants, and
CORRECTNESS law participation**. A "thin sidecar" is a row in the
Reference family with `kind = POLICY`. It is not a leaf with its own
infrastructure.

**Required fix.** Delete L7 as a separate leaf. Fold its content into
the Reference family as `Reference.PolicyConfig` rows. The 30-field
cap is fine; the separate leaf is not.

### B5. V8 reconciliation is correct in §9.2 but contradicted in §3.6 L21

§9.2's reconciliation for V8 is good: "CDM enum closure is a library
version pin (L21), not a stored data category. Generators consume it
via `cdm_version` import, not a queryable table." That honours V8.

But §3.6 L21 promotes "Version Pin" to its own leaf with FORMALIS
invariants ("Part of L16 SmartContract / Model code"), CORRECTNESS
participation (L8 + L9), realism class U6 + C-A5, and an owner
("deployment pipeline + governance"). A library version pin is *a
field on a record*, not a leaf. Promoting the pin to a leaf reproduces
the V8 violation under a different name.

**Required fix.** Delete L21 as a leaf. Version pin is a tuple field on
every transaction, snapshot, and calibration record. Document it where
it lives, not as a separate leaf.

### B6. L24 OrchestrationState is ceremony

This is partly a restatement of B2; I separate it because the
ceremony-vs-needed question was specifically asked.

**Verdict on L24 in isolation.** Ceremony.

What L24 actually adds, beyond a foreign key:
- Realism class (U6, U8, C-A9) — but C-A9 is owned by TEMPORAL, not the
  Ledger. The Ledger does not implement this guarantee; it consumes it.
- FORMALIS invariants (3T + 3W + 1C = 7) — but the proposal admits
  these are "opaque to MINSKY; managed by Temporal SDK". An invariant
  the data layer cannot inspect is not a data-layer invariant.
- CORRECTNESS L10 (Workflow-History Replay Coherence) — this is a
  Temporal-cluster property, not a ledger property, by the proposal's
  own admission.
- An owner ("Temporal worker") — which is the Temporal cluster, not
  anyone in the Ledger team.

A leaf that names invariants the data layer cannot check, an owner who
is not on the data team, a realism assumption owned by another system,
and zero queryable content beyond a foreign key, **is not a leaf**. It
is a foreign-key field on transactions and a sentence in the operating
contract.

**Required fix.** Same as B2.

---

## §2. UNMITIGATED MAJOR findings

### M1. The veto-honouring claim in §0 is not audited

The executive summary §0 anchor 5 claims my "fourteen vetoes are the
upper bound on complexity". The proposal then violates V7, V8 (via
L21), V9 (via L7), V10 (via L5), V11 (via L24), and arguably V13 (see
M3). That is **6 of 14 vetoes either violated or trivially redressed**.
A 43% violation rate dressed up as "tension flagged for Phase 3" (§1.2
closing paragraph) is not honouring the upper bound; it is asking
permission after the fact.

**Required fix.** §0 must list, for each of V1–V14, the specific
realisation in the proposal that honours the veto, with section
reference. Where a veto is violated, say so plainly and present the
case for an exception. Do not hide violations behind "tension".

### M2. The "tension flagged for Phase 3" pattern is rhetorical laundering

§1.2 closing paragraph, §3.1 L5/L7 tension boxes, §3.6 L24 tension box,
and §9.2 all use the same move: name a veto, name a leaf that contradicts
it, and write a "reconciliation" that admits the leaf with a softer label
("thin sidecar", "boundary contract level", "replay-substrate only",
"library version pin"). The label changes; the leaf, the workflow, the
owner, the invariants, and the CORRECTNESS participation do not.

This pattern is not honest disagreement-surfacing — it is the
synthesis pretending to contest itself while admitting everything. A
real reconciliation would either delete the leaf or delete the veto.
Doing both is what I am rejecting.

**Required fix.** Phase 3 must rule, leaf-by-leaf, whether the leaf
stays as written (and the veto is overridden, with the override
documented as a deliberate architectural decision) or the leaf is
deleted. The tension box format is a forbidden output for Phase 3.

### M3. V13 is honoured at the storage layer but violated at the leaf layer

V13 forbids Trade / Position / PnL / Risk / Account tables. The
proposal honours this at the storage layer: §0 anchor 2 makes L8/L9
projections of L14, and §1.1 P8 carries the principle. Good.

But L9 PositionState is listed as a leaf with **its own FORMALIS
invariants** (2T + 3W + 2C, §3.3) and **its own owner** ("handlers per
StatesHome C11"). A projection with seven type-level invariants and a
named owner is operationally a table — it has a schema, a writer
contract, and a consistency proof. The proposal calls it a "monotone
carrier" but ships it as a position table.

This may actually be defensible — the addendum's three-map ruling
demands per-(w,u) state — but the proposal must say so explicitly:
"L9 is a stored cache with single-writer invariants; V13 is overridden
for L9 because of three-map ruling C11; the override is documented as
ADR-N." Currently the proposal claims V13 is honoured *and* ships L9
as a stored leaf with invariants. Both cannot be true.

**Required fix.** Add an architectural-decision-record (ADR) section
listing every veto override with the concrete claim that justifies it.
For L9 specifically: which v10.3/addendum/valuation claim makes a
stored per-(w,u) table irreducible? Cite it.

### M4. Compositional theorem 2 conflates Ledger and Temporal correctness

§8 theorem 2: "snapshot determinism (U3) at the data layer +
workflow-history determinism (C-A9) at the orchestration layer compose
to v10.3 Property 6 (time travel) at the ledger layer."

This is a **cross-system theorem**, not a ledger theorem. Its
conclusion holds only if the Temporal cluster behaves as specified.
The Ledger team cannot be on the hook for that conclusion if the
Temporal cluster fails. The theorem must be re-stated as either:
- "If `(Ledger, Temporal)` jointly satisfy `(U3, C-A9)`, then the joint
  system has time-travel," or
- "The Ledger's contribution is U3; time-travel is a downstream
  property of the joint system; the Ledger does not own it."

Both forms are honest. The current form is not.

**Required fix.** Restate theorem 2; flag any other theorem (1, 3, 4, 5)
that has the same Ledger-vs-joint-system confusion. Theorem 3 likely
has the same problem (durable timer is Temporal-owned).

### M5. Realism budget owners cross system boundaries without explicit handoff

§6 lists C-A1 through C-A10 with owners. C-A2 is "Head of security
operations". C-A3 is "Per-vendor relationship owner". C-A4 is
"Settlement-operations team". C-A5 is "CDM/ISO interop lead
(MATTHIAS)". C-A6 is "Model-validation team". C-A9 is "TEMPORAL".
C-A10 is "Records management + compliance".

**Six of ten conditional guarantees are owned outside the Ledger team.**
This is fine in principle (the Ledger is part of a larger firm), but
the proposal has no operating contract describing what the Ledger
detects when an external owner fails to deliver, what compensating
actions trigger, and what the Ledger's exposure is during the failure
window. Without that contract the realism budget is performative.

**Required fix.** Each conditional assumption needs three additional
fields beyond owner: (a) detection signal (what tells the Ledger the
assumption is broken), (b) compensating action (what the Ledger does
during the failure window), (c) blast radius (what economic invariants
fail open during the window). Without these, C-A1–C-A10 is a
prose paragraph, not a contract.

### M6. The "≤30 fields" cap on L7 is unenforceable

§3.1 L7 tension box: "the realism budget is small sidecar, not a
parallel data spine. The veto is honoured by refusing to let L7 grow
beyond ~30 fields." How? By whom? At which CI gate? With what blocker
when the 31st field arrives mid-quarter?

A field-count cap with no enforcement is a wish. The same critique
applies to V12 (no free-text metadata) — present in P9/P10 but with no
named CI check that rejects an `extension: Json` field on a future
PR. Vetoes without enforcement collapse on the first contributor who
hasn't read this document.

**Required fix.** Each enforcement-bearing veto needs a named
mechanism: a schema linter, a `pyright`/`mypy`/`tsc` rule, a CI
contract test, an ADR-required-for-PR gate. "Refusing to let it grow"
is not a mechanism.

---

## §3. MINOR findings

### m1. §2.1 "C6 is the morphism-recording layer (provenance edges in all three sheaves)"

This is a GROTHENDIECK sentence in a NAZAROV table. If C6 maps onto
GROTHENDIECK's morphism layer, say so structurally — does that mean
C6 is *not* a class of leaves at all but a layer of edges? If yes,
L17–L24 should not be leaves; they should be field-fragments on
C1–C5 leaves. (This dovetails with B6.)

### m2. §3 leaf entries are 6-line stubs that delegate authority elsewhere

Each leaf entry has six lines (N/M/T/R/F/C) and each line says "see
file X". I cannot review what I cannot read in this document. Either
the proposal is the artefact (and contains the content), or the seven
specialist files are the artefact (and the proposal is a table of
contents). It cannot be both. Per HALMOS B-class concern; relevant
here because the veto-vs-leaf reconciliations *cite* the specialist
files but the specialist files are not visible to a Phase 3 reviewer
working from `proposal_v1.md`.

### m3. §7 strategic gap #5 ("TradeState ↔ StatesHome 3-map alignment, asserted but not verified")

This is a genuine open problem that should not be filed under "CDM
gap". It is a structural alignment that determines whether the
StatesHome ruling holds at all. Promote to its own §, name an owner,
name a deliverable.

### m4. §9.2 table column "Reconciliation proposal" should be "Reconciliation decision"

Phase 3 is reviewing decisions, not proposals. If §9.2 carries
proposals, it belongs in Phase 2. If decisions, the column header is
misleading.

### m5. §9.5 "Phase 3 must rule on whether these architectural tensions are resolved or whether they require revisiting the Temporal-everywhere posture"

The Temporal-everywhere posture was never put up for vote. If the
architecture rests on it and TEMPORAL flags six awkward-fit
categories, three of which (calendar amendments, tick streams, Kalman
ContinueAsNew) are load-bearing, the answer is *the posture needs
revisiting* and the proposal should say so directly.

### m6. P1–P10 are accepted into the proposal verbatim

Good. No finding. Acknowledging where the proposal got it right.

### m7. The MoveStream-as-canonical claim (§0 anchor 2) is correctly absorbed

V13 storage-layer honouring is correct. The architecture is sound at
the foundation; my findings are about what was bolted on top.

---

## §4. What was done well (briefly)

- P1–P10 are absorbed verbatim and applied through §3 entries.
- V1, V2, V3, V4, V5, V6, V12, V14 are honoured cleanly.
- The MoveStream-as-canonical claim is structurally correct.
- The bitemporal/single-axis distinction (P4) is preserved.
- The §9 "surfaced disagreements" intent is correct (do not smooth)
  even where the execution (§9.2) launders rather than surfaces.
- §6 realism-budget structure (unconditional vs conditional) is good
  thinking, even if the conditional contract is incomplete (M5).

The core architecture survives. What needs to be cut is the carapace.

---

## §5. Summary scorecard

| Category | Count |
|----------|-------|
| BLOCKING | 6 (B1 count creep, B2 L24, B3 L5, B4 L7, B5 L21, B6 L24-as-ceremony) |
| UNMITIGATED MAJOR | 6 (M1 veto-audit, M2 tension-laundering, M3 ADR for V13/L9, M4 cross-system theorems, M5 realism contract, M6 enforcement) |
| MINOR | 7 |

**Vetoes-honoured score.** 8 of 14 honoured cleanly (V1, V2, V3, V4,
V5, V6, V12, V14); 4 violated via leaves (V7, V9, V10, V11); 1 violated
via promoted field (V8 via L21); 1 violated via stored projection
(V13 via L9, defensibly but undocumented). **8/14 clean = 57%.** Below
my acceptance threshold of "all 14 honoured or all overrides
documented as ADRs".

---

## §6. Grade

**Grade: C+ (REQUEST CHANGES).**

The architecture is sound. The synthesis discipline is poor. The
proposal absorbed the principles cleanly and the vetoes badly. Six
BLOCKING items, six UNMITIGATED-MAJOR items. Most of the BLOCKING
items reduce to one structural fix: collapse 24 leaves to ≤7 sectors
(or document each leaf-beyond-7 as an ADR-justified veto override),
and delete L5/L7/L21/L24 as separate leaves. That is one week of
synthesis work, not a structural rewrite.

If `proposal_v2.md` collapses the leaves, deletes the four laundered
leaves, and adds ADRs for any V13/L9-style overrides, this proposal
becomes APPROVE.

The brake stays on.

---

**End of jane-street-cto Phase 3 Round 1 review.**
