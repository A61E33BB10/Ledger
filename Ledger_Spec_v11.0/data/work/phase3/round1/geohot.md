# GEOHOT — Phase 3 Round 1 Adversarial Review of `proposal_v1.md`

**Stance.** Radical simplicity. Delete aggressively. Beautiful code reveals truth. Every line of spec is a liability — every line forces an implementation, a test, an invariant, a maintainer. I read this proposal as someone who will have to build it in tinygrad-line-counts.

**Verdict up front.** This is a competent integration of seven serious specialists. It is also a textbook over-engineering pattern with a defensive cover sheet. The authors *know* this — §9.2 surfaces the jane-street vetoes that are getting steamrolled by NAZAROV's leaf-elevation reflex. The "reconciliation" wording in §3 is mostly diplomacy, not engineering.

**Grade: C+.** The spine has a real shape (3 sheaves under GROTHENDIECK Pass B; 3 StatesHome maps; 1 canonical record L14). The 24-leaf presentation actively obscures it. The proposal is mergeable only after a hard cut.

---

## 1. The headline attack — 24 leaves is too many

### 1.1 What the proposal actually says, decoded

NAZAROV picked 24 because every other proposal (3, 6, 7, 16, 31, 41, 62) "maps cleanly into it." That's not a justification — that's the largest-common-refinement heuristic. **Coarsest refinement that everyone accepts is the right answer; finest refinement that nobody contradicts is the wrong answer.** The proposal picks the latter and rationalises with "specialists refine within it."

GROTHENDIECK Pass B already gave the answer: **3 sheaves**. ℱ_Defn (what things are), ℱ_Obs (external attestations), ℱ_Eff (internal events). Add C6 as the morphism layer. That's the structural argument. NAZAROV's 6 classes are a presentation; the 24 leaves are bookkeeping.

### 1.2 The leaves I would delete, with reasons

I'm asked: *which delete?* My ranked kill list:

| Leaf | Verdict | Reason |
|------|---------|--------|
| **L4 Calendar/Convention** | **Fold into L2** (or into L1 directly) | Calendars are reference data with bitemporal restatement; that is *literally* what L2 already is. The proposal even admits "Part of L2 ReferenceMaster" in §3.1 L4.F. Splitting it is type-theoretic vanity. |
| **L5 SettlementInfra** | **Delete leaf, keep boundary contract** | jane-street V10 is correct. The proposal admits "lives outside the Ledger boundary" and "the Ledger consumes but does not author". A leaf the Ledger does not author is *not a Ledger leaf*. It is a parser at the boundary. |
| **L7 Policy/Configuration** | **Delete leaf, hard-code or pin-as-L21** | jane-street V9 is correct. "≤30 fields" is a confession. Firm currency, decimals, rounding mode = **constants in code**, not a database. Tolerance thresholds = part of the calibration model (L13) or the test harness, not a load-bearing spine leaf. |
| **L17 AttestationEnvelope** | **Fold into L10/L11/L12** | The envelope is *part* of every observation; making it a separate leaf is wrapper-pattern fetishism. Every observation type has `signature`, `attestor`, `t_obs`, `t_known` *already* (see L10.N, L11.N). L17 is a redundant abstraction. |
| **L18 IdentityKeys** | **Delete; move to L21 version pin** | "Pre-registered constants in workflow code; not workflow-managed." (§3.6 L18.T) That's not data. That's a constants module. Stop putting constants modules in your data taxonomy. |
| **L19 Snapshot** | **Keep — but stop calling it a leaf** | Content-addressed bundles of (L10 ∪ L13). It is a *view*. Same status as "balance" — projection of L14 is forbidden as a leaf (V13), so why is projection of L10/L13 a leaf? **Apply V13 consistently or admit V13 is selective.** |
| **L20 IdempotencyToken** | **Fold into the envelope** | Even MINSKY admits "Cross-cutting" (§3.6 L20.F). Cross-cutting things are not leaves. They are fields. |
| **L22 HashChainAnchor** | **Fold into L14** | "Genesis hash, per-transaction `prev_hash`." That is L14's `prev_hash` field. Stop. |
| **L23 Capability** | **Borderline keep** | At least it's a real, mutable, separately-administered thing. But could plausibly fold into L7 if L7 survived. |
| **L24 OrchestrationState** | **Delete from data spine** | jane-street V11 is correct. The proposal *literally writes* "replay-substrate only; not economic data" and "no economic invariant references L24 directly". A non-economic leaf in a data spec for an economic ledger is pasting the runtime into the schema. Delete. Its invariants live in TEMPORAL's runtime guarantees (C-A9), not the data layer. |

**Net cut: 8 leaves deleted (L4, L5, L7, L17, L18, L20, L22, L24), 1 reclassified (L19 as view).**

**Result: 16 leaves.** Coincidentally what FORMALIS independently arrived at. *That is the canonical count.* When two unrelated specialists land at 16, and your synthesis picks 24 because "everyone refines into it," your synthesis is doing CYA, not engineering.

### 1.3 What 16 leaves looks like

C1 Definitions: L1 ProductTerms, L2 InstrumentMaster (absorbs L4), L3 Party, L6 LegalAgreement. **(4)**
C2 Status: L8 UnitStatus. **(1)**
C3 PositionState: L9 PositionState. **(1)**
C4 Observations: L10 RawMarketObservation, L11 LifecycleOracleAttestation, L12 ExternalConfirmation, L13 CalibratedMarketObject. **(4)**
C5 Effects: L14 MoveStream, L15 ValuationRecord, L16 ObligationStore. **(3)**
C6 Provenance (now thin): L19 SnapshotView (named-as-view), L21 VersionPin, L23 Capability. **(3)**

**Total: 16.** L17/L18/L20/L22 absorbed as fields; L4/L5/L7/L24 deleted from spine.

---

## 2. C6 specifically: cargo or essential?

**Question asked:** Is C6 (8 leaves of provenance) cargo or essential?

**Answer: 8 leaves of C6 is cargo. The *concept* of C6 is essential.**

Provenance is real — every C1/C4 instance needs an attestor, signature, snapshot link, version pin, idempotency key, hash anchor. **But these are fields on C1/C4/C5 records, not independent leaves.** The proposal even concedes this in §3.6 opening: "These leaves are meta-data; they do not have independent ingress workflows."

That sentence is the argument for deletion. **A leaf without an ingress workflow is not a leaf — it is a column.**

Of the 8 C6 leaves:
- L17 envelope, L18 identity keys, L20 idempotency token, L22 hash anchor → **fields**, not leaves. Delete as leaves.
- L19 snapshot → **view**. Same logical status as `balance`. V13 forbids `balance` as a leaf — apply consistently.
- L21 version pin → **kept** (it is the only thing in C6 with real authoring discipline — release pipeline owns it).
- L23 capability → **kept** (administered separately, has CRUD).
- L24 orchestration state → **delete** (V11; not economic).

**Result: C6 collapses from 8 leaves to 2 (L21 + L23) plus L19 as a named view.** Whether you keep "C6" as a class label is cosmetic.

The cargo signal is unmistakable: when a class ships with 8 sub-leaves and 6 of them admit "no ingress workflow / cross-cutting / not workflow-managed / not economic data," the class is doing taxonomy-padding work, not structural work.

---

## 3. LoC budget for the simplest correct implementation

Asked: *LoC budget for simplest correct impl?*

Working from the spine after my cuts (16 leaves, single canonical record L14, three projections L8/L9 + balance/PnL):

| Component | LoC budget | Rationale |
|-----------|-----------|-----------|
| Refined newtype + closed-enum library (UnitId, ISIN, LEI, MIC, BIC, TxId, SnapId, Hash256, signatures, day-count, BD-conv, lifecycle stage) | **~400** | One file. ~25 newtypes × ~10 LoC + ~10 closed enums × ~15 LoC. |
| L1 ProductTerms (incl. listed/OTC/bond/mandate/QIS/SBL variants) parsed types + version monotonicity | **~300** | Sum type + parse from FpML/CDM + 2 invariants. |
| L2 InstrumentMaster + L4 calendar/convention (folded) | **~250** | Vendor parser ring-isolation + closed-enum lookups. |
| L3 Party + L6 LegalAgreement | **~150** | Mostly newtype + parse. |
| L8 UnitStatus + L9 PositionState (with field-level writer caps) | **~250** | Phantom types do the heavy lifting; record + monotone-carrier helpers. |
| L10 RawMarketObservation + L11 OracleAttestation + L12 ExternalConfirmation | **~400** | Sum types + per-source parser; bitemporal index helpers. |
| L13 CalibratedMarketObject (witness type, no-arb certificate, snapshot FK) | **~200** | Posterior bundle + admissibility check stub. |
| **L14 MoveStream (canonical record, hash-chained, conservation-refined)** | **~400** | The spine. Conservation refinements + hash-chain + StateDelta. The thing that earns its 11 invariants. |
| L15 ValuationRecord + L16 ObligationStore | **~250** | Both records + saga compensation hook. |
| L19 Snapshot view + L21 VersionPin + L23 Capability | **~200** | Content-address helper + pin record + capability checker. |
| Bitemporal index + replay harness | **~300** | The shared substrate. |
| Conservation invariant checker (5 laws witnessed, 4 surrogate strategies) | **~400** | The proof obligations. |
| **TOTAL core** | **~3,500 LoC** | |
| CDM Rosetta cross-walk (forgetful functor + round-trip test) | **+1,000 LoC** | One-time mapping table; mostly mechanical. |
| Property-based test harness covering all 14 laws (with Goodhart-trap mitigations) | **+1,500 LoC** | Generators + shrinkers + metamorphic relations. |
| **TOTAL with tests + CDM** | **~6,000 LoC** | |

**Anchor: tinygrad core is ~5,000 LoC and runs on real hardware. A correct, hash-chained, bitemporal, single-canonical-record financial ledger should not need more than that.** If the implementation comes in at 30,000 LoC, the spec lost.

Reject any implementation that ships >10,000 LoC for the core (excluding adapters and tests). That is the budget. If it doesn't fit, the spec is wrong, not the budget.

---

## 4. Worst over-engineering pattern that survived Phase 2

Asked: *Worst over-engineering pattern that survived?*

**Winner: §9.2 "reconciliation" of jane-street's V8/V9/V10/V11 vetoes.**

This is the worst pattern because it is over-engineering disguised as compromise. The proposal records four direct vetoes from the engineering specialist, then "reconciles" each by *keeping the leaf and adding a paragraph of qualifying language*:

- V9 vs L7 → "L7 is admitted as a thin sidecar (≤30 fields)"
- V10 vs L5 → "L5 is admitted at the boundary"
- V11 vs L24 → "L24 is admitted at the boundary contract level"
- V8 vs CDM enum universe → "CDM enum closure is a library version pin"

**The pattern:** when an engineer says "do not put X in the data spine," and the response is "X is in the data spine but with qualifying language," X is in the data spine. The qualifying language is enforcement-vacuum; nothing in the structure prevents L7 from growing past 30 fields, nothing prevents L5 from being mutated by Ledger workflows, nothing prevents economic invariants from accidentally referencing L24.

**Closely related runner-up:** §9.4's "surrogate strategies" for 4 unwitnessed laws. Trust registries, threat models, multi-source consensus, content-addressing+erasure-coding, structural induction — these are *defenses-in-depth*, not witnesses. Calling them "surrogate witnesses" is a vocabulary trick. The honest framing: **these laws are accepted as architectural risks with named owners.** Say so.

**Bronze:** the §3.6 C6 sub-section — 8 leaves with admissions like "cross-cutting," "not workflow-managed," "no ingress workflow," "internal to Temporal." These admissions *are* the deletion argument. They are documented and then ignored.

**Honourable mention (cargo masquerading as rigour):** the leaf-count reconciliation table (§2.3) where 7 inflates to 16, 24, 31, 41, 57, 62 and the response is "no contradictions; everyone refines within NAZAROV's 24." When inflation factors of 2x–4x produce no contradictions, the *coarser* number is right. Inflation that produces no new constraints is decoration.

---

## 5. Beauty diagnostic

The aesthetic test: **read the per-leaf entries in §3 aloud.** Does it sound like one coherent system, or like seven specialists each appended a line?

Each leaf has six lines (N/M/T/R/F/C) — one per specialist. Reading L14 aloud: "Append-only, hash-chained, dual-timestamped, CDM-payload-bearing... `Move`, `Transaction`, `StateDelta` as sum types... Activity result; `idempotency_key = tx_id`... Direct to CDM `BusinessEvent`... 4T + 5W + 2C = 11 invariants... Participates in L1, L3, L5, L6, L7, L8."

That is committee-speak, not architecture. The shape that earns L14's 11 invariants is buried under bookkeeping. **The MoveStream is the most important leaf in the entire spec — it deserves prose, not a six-row attribution table.** Promote L14 to its own section. Demote the rest.

The §1 principles (P1–P10) and vetoes (V1–V14) are the *actual* spec. The leaf taxonomy is implementation detail. Re-order: principles first (kept), vetoes next (with teeth — see §6), then *one* leaf table (16 leaves, one line each), then drill-downs only for L1, L8, L9, L10, L11, L13, L14, L15, L16. The other 7 leaves can be field-list bullets.

---

## 6. Findings

### BLOCKING

**B1. Leaf-count over-inflation.** 24 leaves is bookkeeping, not structure. Cut to 16 (FORMALIS-aligned). Specifically delete L4 (fold into L2), L5 (boundary parser, not leaf), L7 (constants + L21), L17 (field on observations), L18 (constants), L20 (cross-cutting field), L22 (field on L14), L24 (V11 — not economic data). Reclassify L19 as a view.

**B2. Vetoes V8/V9/V10/V11 are not actually reconciled.** §9.2 records the vetoes, then keeps the leaves with paragraphs of qualifying language. Either (a) honour the vetoes by deleting/folding the leaves, or (b) reject the vetoes explicitly and document why. The current half-measure is enforcement-vacuum: nothing structural prevents the qualifications from drifting away during implementation.

**B3. C6 contradicts V13 selectively.** V13 forbids `balance`, `PnL`, `position` as tables (correct — they are projections of L14). L19 Snapshot is *also* a projection (of L10 ∪ L13) but is a leaf. L8 UnitStatus and L9 PositionState are *also* projections of L14 (per the spine philosophy) but are leaves. Either V13 is universal (then L8, L9, L19 are views, not leaves) or V13 is selective (then state which projections become leaves and why). Pick one. The current state is incoherent.

### UNMITIGATED MAJOR

**M1. "Surrogate witnesses" is a vocabulary trick.** §9.4: 4 laws are unwitnessed by finite tests; the proposal calls trust-registries / bounded-horizon tests / content-addressing "surrogate strategies." Rename to "architectural risks accepted with named owners." Surrogates are not witnesses; pretending they are leaves the integrator with false confidence.

**M2. The line "specialists refine within NAZAROV's 24" is unfalsifiable cope.** Refinement that produces no new constraints is decoration. The proposal needs to defend 24 *against* coarser counts (16 from FORMALIS, 7 from jane-street), not just claim the finer counts are non-contradictory. Coarsest count that admits all required invariants is the right answer.

**M3. CDM gap risk is acknowledged but not bounded.** §9.3: 26 missing types, 5 strategic. The proposal says "Phase 3 must rule on whether the Ledger is willing to operate with CDM-missing leaves represented as Ledger-internal types." That is the *architectural* decision dressed as a Phase-3 deliverable. State the position now: **Ledger-internal types are first-class until upstream lands; the migration cost is owned by the CDM-interop lead (MATTHIAS).** Stop deferring.

**M4. L24 OrchestrationState as a data leaf.** Even after §3.6 admits it is "replay-substrate only; not economic data," it remains a leaf with 7 invariants. Pure leaf inflation. Move the workflow-history determinism guarantee into TEMPORAL's runtime contract (C-A9), where it already lives.

**M5. No LoC / complexity budget for the implementation.** A spec without a complexity budget is a spec that grows. State: **core implementation must fit in ≤10,000 LoC excluding adapters and tests; if it does not, the spec is wrong.** Without this constraint, every future "the spec already covers it" addition is a free option.

### MINOR

**m1.** L17 Attestation Envelope is named separately but its fields (`signature`, `attestor`, `t_obs`, `t_known`) already appear inline in L1, L2, L3, L10, L11. Pick one — either factor out the envelope record consistently *and delete the duplicated fields elsewhere*, or inline always. Currently both.

**m2.** §2.3's "MATTHIAS 62" sub-leaf expansion driven by CDM type granularity belongs in the *adapter layer*, not the spine. EquityQuote, FXRate, RatesQuote, VolatilityQuote etc. are all `RawMarketObservation` payload variants — 62 is the CDM serialisation count, not a Ledger leaf count.

**m3.** §3.1 L7's "≤30 fields" upper bound is a cap nobody will enforce. Either codify it (schema-level cap; CI check fails if L7 grows) or delete it.

**m4.** §6 realism budget mixes 8 unconditional + 10 conditional = 18 things, but C-A9 (workflow determinism) is owned by TEMPORAL and C-A8 (closed-system boundary) is owned by an architecture review board. These are not data-layer concerns; they are runtime / governance concerns. Move them.

**m5.** §9.7 "None" — every specialist contribution integrated cleanly. This is suspicious. Phase-2 syntheses with seven specialists and zero un-integrated contributions are usually hiding the un-integrated parts in qualifying language. Re-audit.

**m6.** §3.4 L13 calls the calibrated-market-data layer a strategic CDM gap (Gap #1) and proposes "seed `cdm-valuation-lib` upstream proposal." Upstream proposals to standards bodies take years. The Ledger needs to ship before then. State the local-types posture as the *primary* answer; the upstream proposal is a nice-to-have.

**m7.** The 14 cross-layer laws (§4) are correctly numbered but their unwitnessed/witnessed split (10/4) is never tested as a *whole*. Add a meta-witness: a CI job that, on every release, exercises the 10 witnessed laws in a single integration test. Without that, "witnessed" is per-test, not per-system.

---

## 7. Grade

**C+.**

- **+** The structural argument (3 sheaves; 1 canonical record L14; 3 StatesHome maps; bitemporal mandatory) is correct.
- **+** Phase 1's principles and vetoes (P1–P10, V1–V14) are real engineering, not committee-speak.
- **+** The compositional theorems (§8) are the right artefact for the LaTeX target.
- **−** 24 leaves is bookkeeping inflation; the FORMALIS-aligned 16 is the canonical count.
- **−** §9.2 reconciliations are diplomatic, not structural; vetoes get steamrolled with qualifying language.
- **−** C6 ships 8 leaves where 2 + 1 view would suffice.
- **−** "Surrogate witnesses" obfuscates accepted architectural risks.
- **−** No LoC budget; no enforcement of `≤30 fields` cap on L7; no structural prevention of leaf-creep.

**Path to A:** apply the cuts in §6 (B1, B2, B3), rename surrogates as accepted risks (M1), cap implementation at ≤10,000 LoC (M5), promote L14 to its own prose section (Beauty), demote C6 to fields-on-records-plus-2-leaves (B1, M4). Re-issue as `proposal_v2.md` at 16 leaves, with vetoes that have teeth.

**The most important sentence in the proposal is in §1.2: "every line you keep is a line someone must read."** It does not actually appear in the proposal — it should. The proposal is currently 545 lines defending 24 leaves. A correct version is 300 lines defending 16.

---

**End of geohot review.**
