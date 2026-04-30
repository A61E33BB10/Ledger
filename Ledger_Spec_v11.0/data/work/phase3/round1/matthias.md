# Phase 3 Round 1 — Adversarial Review by MATTHIAS (rosetta-cdm-engineer)

**Reviewer role.** Independent Principal Engineer, FINOS CDM core team. Fresh-context instance. The Phase 2 author of `phase2/matthias.md` is treated as a *separate* contributor; this review attacks his cross-walk and the synthesis proposal that compresses it.

**Inputs read.**
- `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/work/phase2/proposal_v1.md` (the integrated proposal)
- `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/work/phase2/matthias.md` (the cross-walk being defended in §3 / §7 / §A.5 / §B–§H of the proposal)
- Prior agent memory: `ledger_v11_cdm_state.md`, `cdm_gap_log.md`, `sbl_isla_dependency.md`

**Posture.** The Phase 2 author of `matthias.md` is a careful reviewer. I do not deny the macro-shape of his cross-walk: 14 / 22 / 26 is broadly defensible. But (a) several of his "Strategic" or "Significant" gap classifications survive only because the verification protocol was **suspended** ("I have not re-fetched every cited file from the live repo"), and (b) the synthesis proposal §3 / §7 inherits those classifications **without re-verifying** them. That is the principal vulnerability I attack here.

**Verification disclosure for this review.** I have not re-fetched live `.rosetta` files in this round either — I have no live network access in this session. Where I challenge a Phase 2 claim about CDM type existence or field set, I mark the challenge `[CHALLENGE — verify against live repo]`. The Data Team must resolve every challenge before Round 2.

---

## §1. Headline grade

**Grade: B− / blocking issues present.**

The proposal is structurally sound. The 24-leaf NAZAROV spine survives. The 14/22/26 split is broadly defensible at the macro level. But four blocking issues and seven unmitigated-major issues prevent acceptance at this round, all concentrated in the CDM cross-walk areas the proposal compresses without re-verification.

---

## §2. BLOCKING findings

### B-1. Verification protocol was suspended; the proposal inherits unverified CDM claims as load-bearing input

The Phase 2 cross-walk closes (§K) with: *"I have not re-fetched every cited file from the live repo in this Phase 2 cycle."* The agent persona instruction explicitly requires verification before committing to type / field / cardinality claims. The proposal §3 and §7 then quote those unverified claims as Status ∈ {Direct, Partial, Missing} **without flagging the suspension in the §3 leaf entries**. This means the strategic-gap headcount in §7 (5 strategic, 26 missing) is propagated as fact into the Phase-3 attack surface even though several rows are explicitly tagged `[VERIFY]` in the source.

**Why blocking.** The whole convergence test (§10: zero blocking, zero unmitigated major) depends on knowing whether a gap is real. If ten of the twenty-six Missing items resolve to existing CDM types after live-repo verification, the strategic narrative collapses (no `cdm-valuation-lib` proposal needed for half its scope; no Rosetta extension PR needed for several SBL primitives). If they all hold, fine — but the Data Team must close the verification before the Round 2 review can rule.

**Specific items requiring live-repo re-fetch before Round 2.** The Phase 2 file is explicit on these as `[VERIFY]`-tagged or low-confidence:
- §G.2 `CreditSupportAgreementElections` field set
- §B.3 `CorporateAction` event-shape coverage in `cdm-event-lib`
- §F.4 `TradeState` exact field set (load-bearing for Gap #5)
- §A.2 `Security.rosetta` extension surface
- The path `cdm-product-lib/src/main/rosetta/product/asset/Security.rosetta` (Phase 2 cites; CDM 6.0.0 may have moved this — `Instrument.rosetta` is also plausible)

**Required action.** Re-fetch every `.rosetta` path cited in §A–§H of `phase2/matthias.md`. Re-issue any row whose Status changes. Confirm any row whose Status holds. The Data Team can no longer carry "Direct / Partial / Missing" labels into a Round 2 conversation while the source disclaims its own verification.

### B-2. Gap #5 (TradeState ↔ StatesHome alignment) is the architectural risk that owns every other CDM claim, and the proposal ranks it last

Per `phase2/matthias.md` §F.4 and §J Gap 5, **the alignment between CDM `TradeState` and StatesHome's three-map (`ProductTerms`, `UnitStatus`, `PositionState`) factorisation is asserted, not verified**. The proposal §7 ranks it #5 (Architectural). This ranking is wrong. **It is the gating risk.** If `TradeState` cannot host the StatesHome three-map projection without lossy compression, then:

- Every `BusinessEvent` payload is a parallel-shape carrier (the `unitStateDeltas` block of F.2), not a CDM-native carrier.
- Every regulatory submission (DRR / SFTR / EMIR) is a re-shape, not a passthrough.
- Every replay is now two replays (the StatesHome replay and the CDM replay), with conservation laws to prove they coincide.
- The closed-system property of v10.3 §10 weakens because the boundary contract (CDM) does not match the internal data shape (StatesHome).

This is not "Architectural — affects every replay and every regulatory submission" rated below tokenised collateral and SBL gaps. It is the **load-bearing gap** that determines whether CDM is the boundary contract or merely a translation target.

**Why blocking.** The proposal seeds a `cdm-valuation-lib` proposal (Gap 1), an SBL extension (Gap 2), a tokenisation extension (Gap 3), and an attestation-envelope discipline (Gap 4) — all of which assume the CDM core (TradeState + BusinessEvent + Transfer) faithfully carries the StatesHome economic content. If Gap 5 reveals it does not, the upstream proposal strategy is mis-shaped: **the firm needs a `cdm-stateshome-alignment` PR before any of the four downstream extensions land**, otherwise the extensions sit on top of a structural mismatch.

**Required action.** Promote Gap 5 to top of §7. Make Round-2 admission conditional on a re-run of Rosetta NS1–7 mapping against the three-map schema. If the re-run shows lossy compression, the §8 compositional theorems (Conservation Lifting, Replay Determinism Lifting, Substantiation) need their proof sketches re-validated under the lossy projection — *they may no longer compose*.

### B-3. The proposal §6 (V10) reconciliation accepts SSI as Ledger-consumed-only; the Phase 2 §B.6 Rosetta sketch then defines a full SSI type — these contradict

Proposal §3.1 L5 honors V10 by stating "**L5 is admitted at the boundary contract level; the Ledger consumes but does not author**." But `phase2/matthias.md` §B.6 sketches a `StandingSettlementInstruction` Rosetta type with `[metadata key]`, suggesting it is to be authored / extended by the Ledger. These two positions cannot both be right under the proposal's own veto reconciliation.

**Why blocking.** This is exactly the class of inconsistency Phase 3 is supposed to surface. Either:
- (A) L5 is purely Ledger-consumed: then the Rosetta sketch in §B.6 should be deleted, and the right artefact is a *parser* that maps inbound SSI feeds (DTCC ALERT, Omgeo CTM, ISO 20022 `setr.027`, `secl.005`) into an opaque Ledger-internal `SsiSnapshotRef`. No CDM extension PR.
- (B) L5 is partially Ledger-authored (the Ledger records the SSI it used per transaction): then V10 reconciliation §3.1 is wrong; the Ledger does *author* a slim SSI artefact — namely, the record of which version was consumed at projection time.

Pick one. Option (B) is materially weaker than the proposal currently claims, but probably closer to what is operationally required (an audit needs to know which SSI version the Ledger used).

**Required action.** Resolve A vs B in proposal_v2. Delete or strengthen §B.6 Rosetta sketch accordingly.

### B-4. The 5-strategic-gaps narrative compresses 3 gaps into 1 in some places and inflates 1 gap into 5 in others

The §7 ranking is *visually* clean but the underlying counting is incoherent across the proposal:

- §7 claims **5 strategic gaps**, but the underlying Phase 2 §J (which the proposal cites as authoritative) says **Top 5 = (Calibrated Market layer, SBL triplet, Tokenised collateral, Attestation envelope, TradeState↔StatesHome alignment)**. Of these, **Gap 1 expands to 6 sub-leaves** (E.1–E.6: YieldCurve / VolSurface / FXSurface / CreditHazardCurve / KalmanPosterior / SensitivityJacobian / ValuationRecord — that's 7, not 6). **Gap 2 expands to 3 sub-leaves** (Recall / Locate / Rehypothecation), each of which is a separate `PrimitiveInstruction` extension. **Gap 4 expands to 2 sub-leaves** (AttestationEnvelope + MarketDataSnapshot). So the headcount "5 strategic" hides a true headcount closer to **15 distinct CDM PR units** (calibrated layer 7 + SBL 3 + tokenised 2 + attestation 2 + alignment 1 = 15).
- The proposal's §9.3 "26 CDM types are missing for leaves the proposal requires" cites 26, the cross-walk §L cites 26 — but §L explicitly says **8 of those 26 are correctly out of CDM scope**, leaving 18 Missing genuinely needing attention.

**Why blocking.** Risk-rating governance needs honest headcount. "Five strategic gaps" suggests ≤5 PRs upstream; the truth is ~15 PRs. That is the budget the Data Team is committing to. The arbiter (FORMALIS) cannot rule on mitigations if the gap headcount is hand-waved.

**Required action.** Re-issue §7 with the true distinct-PR-unit count. Specifically: state per strategic gap the number of CDM type extensions it implies, not the number of conceptual "gaps".

---

## §3. UNMITIGATED MAJOR findings

### M-1. Could 3 of the 5 strategic gaps be closed with existing types? Likely no, but with caveats — **two are softer than claimed**

The user asked me directly to attack: "are 5 strategic CDM gaps actually strategic, or could 3 be closed with existing types?" My ruling, gap by gap:

**Gap 1 (Calibrated Market Data Layer): genuinely strategic.** CDM was never designed as a calibration store. `Curve` / `YieldCurveDefinition` model the underlying instrument *schedule*, not posterior parameters. `Valuation` exists at observation level but does not carry `KalmanPosterior` shape. **Cannot be closed with existing types.** Phase 2 ranking holds.

**Gap 2 (SBL Recall / Locate / Rehypothecation): genuinely a gap, but not strategic — it's *operational* and ISLA-owned.** Per memory `sbl_isla_dependency.md`, ISLA's CDM working group is actively contributing here. The right action is "wait and adopt", not "design and propose". The Phase 2 cross-walk recognises this in §J Gap 2 ("Coordinate with ISLA's CDM working group") but the proposal §7 carries it as an active strategic deliverable. Demote: **Significant operational, not Strategic.** No firm PR; track ISLA cadence.

**Gap 3 (Tokenised Collateral): could partially be closed with existing types, with caveats.** `EligibleCollateralSchedule` and `EligibleCollateral` types exist. `Asset` is a choice including `DigitalAsset` — **and `DigitalAsset` already carries some tokenisation hooks in CDM 6.0.0** `[CHALLENGE — verify exact `DigitalAsset` field set against `cdm-product-lib/src/main/rosetta/product/asset/DigitalAsset.rosetta` or current path]`. The **strategic** part is the `(chainId, contractAddress, tokenStandard, backingModel)` quadruple plus proof-of-reserves attestation envelope. Of these, `chainId` and `contractAddress` could plausibly fit as `AssetIdentifier` variants. `tokenStandard` and `backingModel` need new enum types. `proofOfReservesLink` is a CC-1 attestation envelope (Gap 4) wrapping a Merkle root attestation — already covered by the attestation-envelope work. **Demote: Significant, not Strategic**, and recast as "extend `DigitalAsset` + add two enums + use Gap-4 envelope" — not a new `cdm-tokenisation-lib`.

**Gap 4 (Attestation Envelope): genuinely a gap, but mis-located.** This is **Ledger-internal discipline**, not a CDM extension proposal. The Phase 2 §J Gap 4 already says so: *"Ledger-native first-class types (no upstream proposal — this is firm-level discipline)"*. So why is it in the **Strategic CDM gap** list at all? It is a strategic *Ledger* gap, not a strategic *CDM* gap. Move it out of §7 entirely; track under H.4 / H.5 as Ledger-native infrastructure. **Remove from CDM strategic-gap list.**

**Gap 5: see B-2 above. Strategic, gating, and mis-ranked.** This *is* genuinely strategic; it is the most strategic of the five.

**Summary.** Of the five gaps, **Gaps 1 and 5 are genuinely strategic CDM gaps**; **Gap 2 is operational (ISLA-owned)**; **Gap 3 is significant, partially closable with `DigitalAsset` + minor enums**; **Gap 4 is not a CDM gap — it is a Ledger-native discipline gap**. So the answer to the user's question: **yes, 3 of the 5 can be closed or substantially shrunk** with existing CDM types or by re-classification. The headline "5 strategic CDM gaps" should be re-issued as "**2 strategic CDM gaps (Calibrated Layer, TradeState alignment), 1 significant CDM-extension (Tokenised collateral via DigitalAsset extension), 1 operational SBL coordination, 1 Ledger-internal discipline**".

### M-2. The proposal claims a CDM type exists when it almost certainly does not, in at least three places

`[CHALLENGE — verify against live repo]` — but on prior knowledge, the following Phase 2 § path / type claims are suspect:

- **§D.8 `MarginCallInstruction` and `MarginCallResponse`** — Phase 2 says: *"Path: `cdm-collateral-lib/src/main/rosetta/collateral/`. Status: Direct on the type system."* On my recollection of CDM 6.0.0, `MarginCall` types exist in CDM but the path may be `cdm-event-lib` margin processing, not `cdm-collateral-lib`. The exact name `MarginCallInstruction` `[VERIFY]` — CDM has historically used `CollateralCallEvent` / `MarginCallRequest` naming. If the type names don't match, "Direct" is wrong.
- **§F.3 `IndexTransitionInstruction`** in the `PrimitiveInstruction` choice list — `[CHALLENGE — verify]`. CDM 6.0.0 added IBOR-cessation handling via `IndexTransition`-related types, but whether `IndexTransitionInstruction` is the exact spelling and whether it is in the `PrimitiveInstruction` choice (rather than handled via `ObservationInstruction`) needs verification.
- **§G.2 `LegalAgreementType`** — Phase 2 cites `agreementType LegalAgreementType (1..1)`. The original prompt knowledge cites `LegalAgreementTypeEnum`. If the type is now an enum, the field declaration is wrong; if a type, the prompt knowledge is stale. **One of the two is wrong.** The proposal cannot resolve this without a re-fetch.

**Severity.** Each individual error is small. Cumulatively they erode confidence in the §3 leaf table. Until re-fetched, every Status="Direct" claim should be downgraded to "Direct (pending verification)" — which violates the proposal's convergence criterion of "no minor improvement remaining without trade-off".

### M-3. Tokenised-collateral Rosetta extension's compatibility with FINOS direction-of-travel is unaddressed

The user asked: "is tokenised-collateral Rosetta extension compatible with FINOS direction-of-travel?" The proposal §7 Gap 3 simply says "Rosetta extension proposal" — no engagement with FINOS direction. My ruling:

- FINOS is currently extending CDM via the `DigitalAsset` choice on `Asset` (CDM 6.0.0). The trajectory is **integration into the existing `Asset` hierarchy**, not a parallel `cdm-tokenisation-lib`. Phase 2 §G.9 sketches `EligibleTokenisedCollateral` as a *standalone* type with a flat `chainId / contractAddress / tokenStandard` triple, which ignores the existing `DigitalAsset` integration point.
- The FINOS-direction-of-travel-compatible shape is: **extend `DigitalAsset` (or `AssetIdentifier`) with a chain-aware identifier sub-type**, and place it under `EligibleCollateralSchedule` — *not* a new top-level type. This way the tokenised collateral remains queryable through the existing `Asset` choice and inherits all `Asset`-level conditions (price observability, lifecycle, transferability).
- The `BackingModel` enum (CUSTODIAL_MIRROR / ON_CHAIN_NATIVE / SYNTHETIC) is good and would fit cleanly. The `proofOfReservesLink` should be a `[metadata reference]` to an `AttestationEnvelope` (Gap 4) carrying a Merkle root — not a free string.

**Severity.** The Phase 2 §G.9 sketch as written would be **rejected by FINOS** as insufficiently integrated. The Data Team should rewrite §G.9 as a `DigitalAsset` extension PR, not a new `cdm-tokenisation-lib` proposal.

### M-4. The "Partial" classifications hide material gaps in five places

The user asked: "for partial mappings, is the gap material?" Material partials (where the missing piece is operationally load-bearing):

1. **§A.2 ListedEquity Partial** — the missing fields (boardLotSize, votingRights, dividendPolicyRef, corporateActionFeedRef) are operationally load-bearing: missing `boardLotSize` makes block-trade compliance reports wrong; missing `votingRights` blocks proxy-voting workflows. Material.
2. **§A.3 ExchangeContractSpec Partial** — missing CCP-as-unit-identity coupling. Per StatesHome, CCP identity is part of unit identity. Without `clearingHouse` first-class on `ListedDerivative`, two CME-vs-ICE units are aliased. Material; flagged in v10.3 §3.10. *This is closer to a Missing than a Partial.*
3. **§D.2 ISO 20022 Settlement Message Partial (`seev.*`)** — corporate-action `seev.*` synonym mapping is patchy. Operational impact is high (every dividend record date / ex-date / payment date triggers a Ledger event). Material.
4. **§F.4 TradeState Partial** — see B-2. Architectural.
5. **§G.4 TradeCollateralProvisions Partial (CCP-cleared)** — no dedicated type for CCP margin rules. Material for cleared-trade reconciliation; relevant for the CCP-conservation-scope law (CORRECTNESS L7).

**Severity.** Each Partial that is materially Missing inflates the true gap headcount (B-4) further. After re-classification, the **direct/partial/missing split likely shifts from 14/22/26 toward 12/14/36 or worse**.

### M-5. The §8 Compositional Theorems are conditional on Gap 5 (TradeState alignment) holding without lossy compression

Theorem 1 (Conservation Lifting) requires that "handler-class type-tagging is enforced" — but if `TradeState.state` cannot host the StatesHome `(σ(u), staleness, FSM cursor)` triple natively, then handler-class type-tagging is enforced *in a parallel data structure*, and the lifting condition holds only on the parallel structure. The CDM-native `TradeState` does not see it. So:

- **Theorem 1's premise is conditional on Gap 5.**
- **Theorem 2 (Replay Determinism Lifting) is conditional on Gap 5 + the snapshot-id binding being CDM-recordable.**
- **Theorem 4 (Substantiation: the balance sheet IS the ledger) is conditional on Gap 5 + the `BusinessEvent` payload faithfully carrying `unitStateDeltas` without ambiguity.**

The proposal §8 lists each theorem with bracketed conditions but does not flag that **three of the five theorems share the same external dependency (Gap 5 resolution)**. If Gap 5 re-runs reveal lossy compression, three theorems unwind simultaneously. This is a non-redundant single-point risk concentration.

**Severity.** The risk-of-bundling failure mode is what makes this a Major: the failure of one verification (the Rosetta NS1–7 re-mapping) cascades through three load-bearing theorems. Mitigation: structure the verification so it can fail gracefully. If the re-mapping reveals lossy compression in some axes but not others (likely outcome), the theorem bracketing should be axis-specific, not theorem-global.

### M-6. The proposal §3 Status="Direct" claims for `Reset` and `BusinessEvent` need a corner-case audit

`Reset` (§C.2) and `BusinessEvent` (§F.3 sub-claim) are listed as Direct. They are direct **at the type level** (the names exist; the cardinalities are right). But the *semantic* directness is subtle:

- **`Reset`** carries `resetValue Price (1..1)` and `observations ObservationEvent (0..*)` — but does it carry the *observation snapshot id* (FK to L19 Snapshot) needed for replay determinism? On my prior knowledge: **no**. CDM `Reset` does not have a snapshot-id field. So the replay-determinism law L8 (witnessed) requires a parallel sidecar, not a CDM-native record. **Direct → Partial after corner-case audit.**
- **`BusinessEvent`** has `instruction PrimitiveInstruction (1..*) and after TradeState (1..*)` — but does it carry the executor signature, hash-chain prev-pointer, and idempotency-token (L20) that v10.3 §13 requires? On my prior knowledge: **no for executor signature; no for hash-chain pointer**. So the substantiation theorem (§8 Theorem 4) hosts these in a sidecar. **Direct → Partial after corner-case audit.**

These are two of the most load-bearing "Direct" rows. If both downgrade to Partial after audit, the 14-Direct headcount drops to 12, and the Phase 2 §L summary table is materially wrong.

**Severity.** Major because `Reset` and `BusinessEvent` are the most-cited Direct rows in the proposal; they appear in §3.4 / §3.5 and are referenced as the canonical CDM hosts for L10 / L14 / L11 leaves.

### M-7. The Gap-5 verification deliverable ("Re-run Rosetta NS1–7 mapping against the three-map schema") is undefined in scope and acceptance criteria

The proposal §7 Gap 5 says: *"Phase 3 verification deliverable."* But:
- What does "Re-run NS1–7" mean as a finite test? Which trades? Which lifecycle events? Under which CDM version?
- What is the pass criterion? Bit-identical round-trip? Surjective projection only? Lossy projection with named axes lost?
- Who owns it? `unit-registration` workflow? CDM/ISO interop lead (MATTHIAS)?
- What is the deadline before Round 2 can rule on convergence?

**Severity.** Major because Gap 5 is now (per B-2) the gating risk, and the deliverable is ill-defined. A vague verification deliverable is the failure mode where Round 5 still cannot converge because no one knows when the deliverable is done.

**Required action.** Re-issue §7 Gap 5 with: (a) the trade/event corpus to round-trip, (b) the projection-equivalence criterion, (c) the owner, (d) the deadline.

---

## §4. MINOR findings

### m-1. Counterparty cardinality `(2..2)` on TradableProduct is correctly cited (§I.4); good
This is the most commonly mis-modelled CDM constraint. Correctly identified. Keep.

### m-2. `Qualify_*` qualification function naming is correctly cited but coverage gaps need to be enumerated
§I.2 lists three qualification functions correctly. But the proposal does not enumerate which products in scope (variance swap, equity option, IRS, FX forward, CDS, bond, listed future, listed option, SBL loan) have qualification function coverage and which don't. Per agent persona instructions, "the qualification scope in CDM is not complete for all product types and this is worth flagging" — flag it explicitly per leaf in §3.

### m-3. The §1.2 V12 veto on free-text `metadata` is in tension with Phase 2 §A.10 `WalletRegistry.kycStatus KYCStatusEnum` — fine, but ensure no free strings creep in elsewhere
The Phase 2 cross-walk uses several free-string fields (`sourceVendor string`, `attestationSignature string`, `kalmanWorkflowId string`). Per V12 these should be refined newtypes, not raw strings. Mostly fine since the field carries `[metadata scheme]` via convention, but the proposal §1.2 should be reconciled with the §3 Rosetta sketches in proposal_v2.

### m-4. The `LifecycleEvent` sum type in §3.4 L11 (`CorporateAction | Barrier | Fixing | Exercise | Default | Locate | RegulatoryThreshold | ForceMajeure | …`) ends with `…`
A sum type cannot end with ellipsis; sum types are closed. Either enumerate the full set or refactor as `LifecycleEvent = CoreLifecycleEvent | LedgerLifecycleEvent` where the latter is a closed extension point.

### m-5. The `Move` type extension in §F.1 with `coordinate PositionCoordinateEnum (1..1)` overloads `Transfer`
A single `Transfer` doesn't have a "coordinate" — coordinates live on the *position vector*, not on the move that updates it. The Phase 2 sketch is conceptually muddy. Cleaner: `Move = SimpleTransfer | SBLCoordinateTransfer { coord: PositionCoordinateEnum, … }` — sum type, not extension.

### m-6. `TimeTuple` (§H.3) `(economicTime, bookingTime, knowledgeTime)` should align with CDM `BusinessEvent.eventDate / effectiveDate` naming
Phase 2 §H.3 invents `economicTime / bookingTime / knowledgeTime`. CDM uses `eventDate / effectiveDate / publicationDate` in various event types. The proposal should align names with CDM conventions to ease synonym mapping.

### m-7. `ObligationStateEnum` values include `ATTEMPTED` (§F.6) — semantically blurry
`ATTEMPTED` mixes runtime workflow state with persistent obligation state. Either it is an L24 OrchestrationState concept (not L16) or it should be split into `ATTEMPTING` (transient) vs `RETRY_EXHAUSTED` (terminal). The single `ATTEMPTED` value is confusing.

---

## §5. Summary of required Round-2 actions

| ID | Class | Action | Owner |
|---|---|---|---|
| B-1 | BLOCKING | Re-fetch all `.rosetta` paths cited in `phase2/matthias.md` §A–§H against the live CDM 6.0.0 release; re-issue Status labels | MATTHIAS (Phase 2 author, with live repo access) |
| B-2 | BLOCKING | Promote Gap 5 (TradeState alignment) to top of §7; make admission conditional on NS1–7 re-mapping | Data Team architects |
| B-3 | BLOCKING | Resolve V10 vs §B.6 SSI contradiction; pick "consumed only" or "thinly authored" and align Rosetta sketch | NAZAROV + MATTHIAS |
| B-4 | BLOCKING | Re-issue §7 with true distinct-CDM-PR-unit headcount (~15 not 5) | Data Team architects |
| M-1 | MAJOR | Re-classify gaps: 2 strategic, 1 significant CDM ext, 1 operational, 1 Ledger-internal | MATTHIAS |
| M-2 | MAJOR | Verify three suspect CDM type/path claims (MarginCall*, IndexTransition*, LegalAgreementType vs LegalAgreementTypeEnum) | MATTHIAS |
| M-3 | MAJOR | Rewrite tokenised-collateral §G.9 as `DigitalAsset` extension, not standalone `cdm-tokenisation-lib` | MATTHIAS |
| M-4 | MAJOR | Re-classify five Partials (A.2, A.3, D.2 seev, F.4, G.4) — flag where Partial is materially Missing | MATTHIAS |
| M-5 | MAJOR | Re-bracket §8 Theorems 1, 2, 4 for shared Gap-5 dependency; structure for axis-specific failure | FORMALIS |
| M-6 | MAJOR | Audit `Reset` and `BusinessEvent` Direct claims for snapshot-id / executor-signature / hash-chain-pointer support | MATTHIAS + CORRECTNESS |
| M-7 | MAJOR | Define Gap-5 verification deliverable scope, criterion, owner, deadline | Data Team architects |
| m-1 to m-7 | MINOR | See §4 | various |

---

## §6. Convergence verdict for Round 1

Per proposal §10:
- **Zero blocking?** No — 4 blocking (B-1, B-2, B-3, B-4).
- **Zero unmitigated major?** No — 7 unmitigated major.
- **No minor improvement without trade-off?** No — 7 minors.

**Convergence: not achieved. Round 2 required after Data Team addresses B-1 through B-4 and proposes mitigations for M-1 through M-7.**

**Grade: B−.** Substantively the proposal is sound. The grade reflects that the CDM cross-walk underpinning §7 has admitted (in §K of the source) a verification gap the proposal carries forward unflagged, and that the gap ranking in §7 ranks the gating risk last. Both are recoverable; both block convergence at this round.

— Matthias Vogt, FINOS CDM core team (independent Phase-3 reviewer)
