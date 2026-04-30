# Ledger v11.0 Data Specification — Phase 2 Synthesis Proposal v1

**Status.** Phase-2 integrated proposal, prepared for Phase-3 adversarial review.
**Inputs.** 19 Phase-1 enumerations (`work/phase1/*.md`) and 7 Phase-2 specialist sections (`work/phase2/{nazarov,jane_street,temporal,minsky,matthias,correctness,formalis}.md`).
**Reading order.** §0 (executive summary) → §1 (principles + vetoes) → §2 (master taxonomy) → §3 (per-leaf integrated specification) → §4–§8 (cross-cutting) → §9 (surfaced disagreements — *the most important section for Phase 3*).
**Convention.** Where this document compresses a specialist's argument, the specialist file is the authoritative source. Reviewers should drill into the named file when the compressed claim is challenged.

---

## §0. Executive summary

Phase 1's 19 independent enumerations and Phase 2's 7 role-specific syntheses converge on a single coherent design with five anchors:

1. **Three structural classes** (Definitions / Observations / Effects), refined into NAZAROV's six-class spine with **24 canonical leaves**. The collapse of the user's six floor categories into this spine is unanimous across Phase 2; the disagreement was on whether the spine has 3, 6, 7, 16, 24, 31, 41, or 62 leaves — driven by granularity, not by structure. NAZAROV's 24 leaves is adopted as canonical because every other count maps cleanly into it (or refines it consistently).
2. **The MoveStream is the canonical record.** L8 UnitStatus and L9 PositionState are projections of L14 MoveStream. Wallet balances, P&L, and the balance sheet are derived views, never independently stored. Phase 1 convergence on this point was overwhelming; jane-street's V13 ("no Trade/Position/PnL/Risk/Account table") cements it at the engineering level.
3. **The bitemporal axis is mandatory** for every leaf in C1 (Definitions) and C4 (Observations). NAZAROV N6 and FORMALIS L4 both make `t_obs` vs `t_known` first-class. Single-axis "as-of" is a violation.
4. **CDM v6.0.0 is the canonical vocabulary** for product terms, business events, and synonym mapping into ISO 20022. MATTHIAS produced 14 direct mappings, 22 partial, and 26 missing — five of the missing items are *strategic* (the entire calibrated-market-data layer, oracle attestation envelope, tokenised collateral, manufactured-payment rates, locate evidence) and require CDM extensions sketched in `matthias.md`.
5. **The data layer is the boundary contract.** NAZAROV's twelve-item data-quality bar (N1–N12) is the floor every workflow must meet. jane-street's ten engineering principles (P1–P10) and fourteen vetoes (V1–V14) are the upper bound on complexity. FORMALIS's per-leaf invariants and CORRECTNESS's 14 cross-layer laws are the proof obligations.

**Open issues for Phase 3** (full list in §9): jane-street's V8/V9/V10/V11 vetoes overlap with NAZAROV/CORRECTNESS leaves the others elevate; CORRECTNESS surfaces 4 unwitnessed laws that cannot be tested by any finite suite (surrogate strategies are sketched but not validated); 26 CDM gaps create dependency on extensions that may not land; TEMPORAL flags 6 categories where the durable-execution model is genuinely awkward.

---

## §1. Engineering principles and anti-over-engineering vetoes

### §1.1 Engineering principles (jane-street, `jane_street.md` §1)

| # | Principle | One-line statement |
|---|-----------|--------------------|
| P1 | Pure-functional ingest | Every transformation is a pure function of captured inputs; no ambient state. |
| P2 | Append-only by default | In-place mutation requires written justification; every leaf in C1, C4, C5 is append-only. |
| P3 | Content-addressed identity | Where deterministic, identity is the hash of canonical content (L18, L19). |
| P4 | Bitemporal where the world restates | Single-axis "as-of" elsewhere; conflating the two is a violation. |
| P5 | Errors are values | `Result<Parsed, Error>`; never silent. |
| P6 | Snapshot pinning at every impure boundary | Every external read is captured in an L19 snapshot keyed by content hash. |
| P7 | Make illegal states unrepresentable | At the type boundary (parsed types, sum types, refinements). |
| P8 | One canonical record | Everything else is a derived view (`balance`, `PnL`, `position` are queries, not tables). |
| P9 | Closed enumerations everywhere a free string is tempting | Currency, MIC, day-count, lifecycle stage all closed. |
| P10 | Polymorphism by sum type, not inheritance | No subclass hierarchies in data. |

### §1.2 Anti-over-engineering vetoes (jane-street, `jane_street.md` §2)

Fourteen patterns to refuse:

| # | Veto | What it prevents |
|---|------|------------------|
| V1 | Three-tier Unit Store as 3 storage entities | The "tier" is a query lens, not three databases. |
| V2 | "Listed-instrument detail" as a top-level data category | Folded into ProductTerms variants. |
| V3 | The "universal symbology service" | Per-vendor identifier mapping is per-leaf, not a global service. |
| V4 | Per-vendor typed schemas in market-data storage | Storage is canonical; per-vendor lives in the parser ring. |
| V5 | Per-model typed Greek schemas | Greeks are model-tagged; one polymorphic shape. |
| V6 | The Pricing-DAG topology as a stored, versioned entity | The DAG is rebuilt from ProductTerms + observation lineage, not stored. |
| V7 | "12-floor / 14-category / 19-category" inflation | Resist count creep; collapse on mutation discipline. |
| V8 | CDM enum universe as a first-class data category | The closed enum is in code (a library version pin), not a table. |
| V9 | "Configuration / Policy" as a load-bearing first-class sector | Policy is a thin sidecar, not a parallel data spine. |
| V10 | A separate "settlement-layer" data sector | SSI lives at the boundary; the Ledger consumes, does not own. |
| V11 | "Workflow / Orchestration State" as ledger data | Replay substrate, not the economic spine. |
| V12 | Free-text `metadata`, `attributes`, `extensions` | Closed schemas only. |
| V13 | A "Trade", "Position", "PnL", "Risk", or "Account" table | All are projections of L14. |
| V14 | Per-regulator obligation kinds | The obligation is uniform; the regulator is a tag. |

**Tension flagged for Phase 3.** V8/V9/V10/V11 partially conflict with leaves NAZAROV elevates (L7 Policy, L5 Settlement Infrastructure, L24 Orchestration State) and with CORRECTNESS Cluster VII. The reconciliation: **these leaves are on the spine but their realism budget is "thin sidecar / boundary metadata", not parallel economic data**. See §9 for the negotiated wording.

---

## §2. Master taxonomy

### §2.1 The six structural classes (NAZAROV `nazarov.md` §1.3)

| Class | Mutation discipline | Leaves |
|-------|---------------------|--------|
| **C1. Definitions** | Append-only versioned; registration-total | L1 ProductTerms, L2 InstrumentMaster, L3 Party/LEI, L4 Calendar/Convention, L5 SSI/SettlementInfra, L6 LegalAgreement, L7 Policy/Configuration |
| **C2. Shared Status** | Mutable per-unit; single-writer-per-field | L8 UnitStatus |
| **C3. Per-position State** | Monotone-carrier; Option accessor; per-(w, u) | L9 PositionState |
| **C4. Observations** | Append-only attestations; bitemporal mandatory | L10 RawMarketObservation, L11 LifecycleOracleAttestation, L12 ExternalConfirmation, L13 CalibratedMarketObject |
| **C5. Effects** | Append-only hash-chained; immutable | L14 MoveStream, L15 ValuationRecord, L16 ObligationStore |
| **C6. Provenance & Orchestration** | Meta-data bound to instances of C1–C5 | L17 AttestationEnvelope, L18 IdentityKeys, L19 Snapshot, L20 IdempotencyToken, L21 VersionPin, L22 HashChainAnchor, L23 Capability, L24 OrchestrationState |

The 6 classes reduce to GROTHENDIECK's three sheaves (`grothendieck.md` Pass B) under a forgetful functor:
- C1 + C2 + C3 → ℱ_Defn (what things ARE)
- C4 → ℱ_Obs (external attestations)
- C5 → ℱ_Eff (internal events)
- C6 is the morphism-recording layer (provenance edges in all three sheaves)

### §2.2 Floor-to-spine mapping

| User floor category | Spine class | Notes |
|---------------------|-------------|-------|
| Static | C1 (split L1–L7) | Renamed; finer split by mutation discipline |
| Reference | C1 (L2–L7) | Distinguished by authoritative source |
| Market | C4 (L10 + L13) | **Mandatory split**: raw observation vs Kalman-certified posterior |
| Oracle | C4 (L11) + C6 (L17) | Lifecycle/non-price oracles + envelope discipline |
| Smart-contract execution | C5 (L14, L15) | Execution outputs are MoveStream + ValuationRecord |
| Listed-instrument detail | (rejected) | Folded into L1 ProductTerms as a `unit_type` variant |

### §2.3 Specialist leaf-count reconciliation

| Specialist | Leaf count | Reconciliation |
|------------|-----------|----------------|
| NAZAROV (canonical) | 24 | The spine. |
| jane-street | 7 sectors | 3 structural + 4 cross-cutting. Folds C6 (provenance) into the structural spine implicitly; consistent with NAZAROV. |
| TEMPORAL | 31 | NAZAROV's 24 with 7 sub-leaves split out for workflow-shape distinctions (e.g., FX rates vs equities; corporate-action announcements vs barrier observations). Refines, does not contradict. |
| MINSKY | 41 | NAZAROV's 24 with finer-grained type-level splits (e.g., `UnitId` vs `ProductTerms` envelope; `RawQuote` vs `OracleAttestation` wrapper). Consistent. |
| MATTHIAS | 62 | NAZAROV's 24 with sub-leaf expansion driven by CDM type granularity (e.g., `EquityQuote`, `ListedDerivativeQuote`, `FXRate`, `RatesQuote`, `VolatilityQuote`, `CreditSpread`, `ReferenceMark` are all sub-leaves of L10 `RawMarketObservation`). Refinement at the CDM-type layer. |
| CORRECTNESS | 7 fault-clusters | Orthogonal to leaves: clusters group leaves by failure-mode similarity, not by mutation discipline. Both views co-exist. |
| FORMALIS | 16 leaves | Slightly coarser than NAZAROV's 24; FORMALIS folded `(L17–L22)` into `L13 WorkflowHistory` and `L14 WalletRegistry/Capability/KeyRegistry`. Reconciliation: **adopt NAZAROV's 24** as canonical; FORMALIS's per-leaf invariants apply transparently. |
| GROTHENDIECK | 57 (Pass A) → 3 sheaves (Pass B) | Pass A inflates; Pass B compresses. Pass B is the structural argument that justifies NAZAROV's 6 classes. |

**Verdict.** No contradictions. NAZAROV's 24-leaf spine is canonical; specialists refine within it.

---

## §3. Per-leaf integrated specification

For each leaf, this section names the seven specialist contributions in compressed form. **Full content is in the named files; reviewers should drill in.**

Notation: each leaf entry has six lines:
- **N** (NAZAROV): definition + minimum field set + DQ workflow + realism class
- **M** (MINSKY): parsed type sketch + boundary parser + sum-type / refinement
- **T** (TEMPORAL): ingress shape + idempotency key + replay-determinism class
- **R** (MATTHIAS): CDM cross-walk status (direct / partial / missing) + path
- **F** (FORMALIS): per-leaf invariant counts (T+W+C); whether the invariant is type-level or runtime
- **C** (CORRECTNESS): which of laws L1–L14 the leaf participates in

### §3.1 Class C1 — Definitions (L1–L7)

**L1. ProductTerms** (`= StatesHome map 1`)
- **N**: Immutable, versioned-append-only specification of what a unit *is*. Min fields: `unit_id`, `product_type`, `terms_payload`, `version_seq`, `t_known`, `attestor`, `signature`. Owner: `unit-registration` and `terms-amendment` workflows. **Realism: unconditional U1, U2** (append-only, bitemporal).
- **M**: `ProductTerms = NonEmpty<TermsVersion>` with `TermsVersion = { fields: Fields; is_fungibility_preserving: TermsVersion -> bool }`. Closed enum `LifecycleIntent`. Refined `UnitId` newtype with private constructor. (`minsky.md` §1.1–§1.2)
- **T**: Activity result; `idempotency_key = hash(unit_id, version_seq)`; replay-determinism: snapshot-pinned. Listed/OTC/bond/mandate/QIS/SBL all share this shape. (`temporal.md` §2.1)
- **R**: **Direct** for OTC (`Product → ContractualProduct → EconomicTerms`); **Partial** for listed (CDM lacks `ExchangeContractSpec` granularity in v6.0.0). Rosetta sketch in `matthias.md` §A.5.
- **F**: 3T + 2W + 2C = 7 invariants (`formalis.md` L1). Type-level: registration totality, version monotonicity. Runtime: signature verify, fungibility predicate.
- **C**: Participates in L1 (lineage), L4 (bitemporal), L5 (per-event-class conservation), L8 (replay).

**L2. Reference Data — Instrument Master**
- **N**: Externally-authored instrument descriptors (ISIN, contract spec, exchange listing, issuer LEI, bond terms, tokenised-asset metadata). Tier-1 input to L1. Min fields: `instrument_id`, `descriptors`, `vendor`, `vendor_msg_id`, `t_obs`, `t_known`, `signature`. Owner: `refdata-ingest`. **Realism: U1, U2 + C-A3** (vendor honesty).
- **M**: Refined `ISIN`, `CFI6`, `MIC` newtypes. `InstrumentMasterRecord` parses from vendor-specific schema in the parser ring. (`minsky.md` §1.4 partial)
- **T**: Activity result with N8 multi-vendor reconciliation gate; `idempotency_key = hash(vendor, vendor_msg_id, version)`; long-poll subscription typical. (`temporal.md` §2.1 implicit)
- **R**: **Direct** for many fields via FpML / CDM `Asset` types; **Partial** for tokenised-asset `(chainId, contractAddress, tokenStandard, backingModel)` — strategic gap (`matthias.md` §A.5 + Top-5 Gap #3).
- **F**: 4T + 2W + 1C = 7 invariants (`formalis.md` L2).
- **C**: L1, L4. Cluster I.

**L3. Reference Data — Party / Legal-Entity**
- **N**: LEI, BIC, MIC, jurisdiction, regulatory classifications (FC/NFC, EMIR class, MiFIR class, US Person, sanctions). Sources: GLEIF, SWIFT, ISO, internal KYC. Owner: `party-ingest`. **Realism: U1, U2 + C-A7** (authority registry currency).
- **M**: `LEI = LEI20` refined newtype; `BIC = BIC11` refined; `MIC = MIC4` closed enum. Sum type `PartyClassification = FC | NFC | UsPerson | Sanctioned | …`. (`minsky.md` §5)
- **T**: Long-poll workflow against GLEIF + SWIFT KYC Registry; bitemporal restatement supported. (`temporal.md` §2.5)
- **R**: **Direct** to `LegalEntity` / `Party` types (`matthias.md` §A.8).
- **F**: 2T + 1W + 1C = 4 invariants (`formalis.md` L4).
- **C**: L1, L4. Cluster I.

**L4. Reference Data — Calendar / Convention**
- **N**: Holiday calendars per `BusinessCenterEnum`, day-count fractions, business-day adjustment rules, roll conventions, weekend rules. Sourced from exchanges, central banks, ISDA, vendors. Owner: `calendar-ingest`. **Realism: U1, U2 + C-A3**.
- **M**: Closed enum `DayCountFractionEnum`; `BusinessDayAdjustmentEnum`; `BusinessCenterEnum` (from CDM). Calendar = `Set<Date>` parameterised by year-range. (`minsky.md` §1.4)
- **T**: Awkward fit (`temporal.md` §6.1) — retroactive calendar amendments invalidate scheduled timers in already-running workflows. **Tension: how is a workflow updated when a holiday is added two months retroactively?** Answer: workflow versioning + signal-driven schedule rebuild.
- **R**: **Direct** (`BusinessCenters`, `BusinessDayConventions`, `DayCountFraction`) (`matthias.md` §A.6, §A.7).
- **F**: Part of L2 ReferenceMaster; bitemporal mandatory.
- **C**: L1, L4, L8 (`now()` + holiday → calendar reads must be snapshot-pinned). NOETHER flagged calendar versioning as a silent conservation violator if not bitemporally pinned.

**L5. Reference Data — Settlement Infrastructure**
- **N**: SSIs, CSD participant IDs, custodian account hierarchies, BIC routing, CCP clearing-member bindings, cut-off times. **Lives outside the Ledger boundary** (v10.3 §9.1); the Ledger consumes at projection time and records the SSI version used. Owner: `ssi-ingest`. **Realism: U1, U2 + C-A4** (settlement-layer freshness — SSI freshness contract is owned by settlement-ops, not the Ledger).
- **M**: Refined `SsiId`, `CustodyAccount`. Sum type `SettlementMethod = Dvp | Fop | Cash`. (`minsky.md` partial; `matthias.md` §B.6)
- **T**: Activity result + bitemporal restatement. (`temporal.md` §2.7)
- **R**: **Partial** — DTCC ALERT, Omgeo CTM, and SWIFT KYC SSI registry have no canonical CDM type; `StandingSettlementInstructions` exists in some FpML/ISO 20022 messages but is not a CDM v6.0.0 type. Rosetta sketch needed (`matthias.md` §B.6 + Top-5 Gap not listed but mentioned).
- **F**: Part of L2.
- **C**: L3, L14 (settlement-move closure + capability scope).

**Tension — jane-street V10 vs. NAZAROV L5.** Jane-street's V10 vetoes "a separate settlement-layer data sector". NAZAROV L5 keeps SSI as a leaf but explicitly notes it lives **outside the Ledger boundary**. Reconciliation: **L5 is admitted as a leaf at the boundary contract level; the Ledger consumes but does not author**. The veto is honoured by ensuring no Ledger workflow attempts to maintain L5 freshness — that is the settlement layer's contract.

**L6. Legal Agreement**
- **N**: ISDA Master, CSA, GMSLA, MSLA, GMRA, OSLA, mandate documents — keyed by `agreement_id` and version. Hash-anchored to the signed document. Bound into L1 (its `Collateral` field is part of `unit_id`). Owner: `legal-ingest`. **Realism: U1, U2 + C-A1** (cryptographic primitive soundness).
- **M**: `AgreementId` refined; `LegalAgreement` parsed from ISDA Create / Notices Hub envelope. (`minsky.md` §1.3)
- **T**: Activity result; multi-counterparty signing wait; idempotent. (`temporal.md` §2.6)
- **R**: **Partial** — ISDA Create and CDM CSA representations are converging; `CollateralProvisions`, `CreditSupportAnnex` exist but are incomplete (`matthias.md` §A.5).
- **F**: 2T + 1W + 1C = 4 invariants (`formalis.md` L3).
- **C**: L1.

**L7. Policy / Configuration**
- **N**: Firm reference currency, decimal precision policy, rounding mode, tolerance thresholds (PnL-explain, reconciliation, conservation alert), accounting classification map (FVTPL/FVOCI/AC), capability schema (C4), versioning policy (CDM/contract/calendar version pins). Owner: `policy-governance`. **Realism: U1, U6** (schema-pinned validation).
- **M**: Closed `RoundingMode` enum; refined `Tolerance`; `AccountingClass` sum type. (`minsky.md` §0 partial)
- **T**: Activity result + signal-driven update; idempotent. (`temporal.md` §2.8 partial)
- **R**: **Missing** — no CDM type. Sketch: a Rosetta `class FirmPolicy { ... }` proposal, but unlikely to land in CDM proper; live as Ledger-internal.
- **F**: Part of L2.
- **C**: L4, L11 (model consistency depends on tolerance policy versioning).

**Tension — jane-street V9 vs. NAZAROV L7.** Jane-street vetoes "Configuration/Policy as a load-bearing first-class sector". NAZAROV's L7 is part of the spine but explicitly thin — its content is small (firm currency, decimals, tolerance thresholds, capability schema, version pins). Reconciliation: **L7 is admitted as a leaf with bitemporal/version-pinned discipline, but the realism budget is "small sidecar, not a parallel data spine"**. The veto is honoured by refusing to let L7 grow beyond ~30 fields.

### §3.2 Class C2 — Shared Status (L8 UnitStatus)

**L8. UnitStatus** (`= StatesHome map 2`)
- **N**: Per-unit shared mutable status: lifecycle stage, last settlement price/date, current weights (QIS), nav index, triggered-barrier flag, superseded-by, valuation FSM state σ(u), staleness timer. Mutated only via L14 `StateDelta`s by the unique writer per StatesHome C11. Owner: lifecycle handlers. **Realism: U1, U7** (single-writer-per-field).
- **M**: Sum type `LifecycleStage = Live | Suspended | Matured | Defaulted | Superseded { by: UnitId }`. `UnitStatus` record with field-tagged writer phantom types. (`minsky.md` §4)
- **T**: Read by activities; written by handlers via executor (`temporal.md` §4.4). Reads must be snapshot-pinned for replay determinism.
- **R**: **Partial** — CDM `TradeState`, `Position`, `BusinessEvent` cover lifecycle transitions but not all UnitStatus fields directly. (`matthias.md` Top-5 Gap #5 — TradeState ↔ StatesHome alignment).
- **F**: 3T + 2W + 2C = 7 invariants (`formalis.md` L5).
- **C**: L5 (per-event-class conservation), L10 (workflow-history coherence), L14.

### §3.3 Class C3 — Per-position State (L9 PositionState)

**L9. PositionState** (`= StatesHome map 3`)
- **N**: Per-(wallet, unit) monotone-carrier with Option accessor. `accumulated_cost`, `hwm`, `entry_nav`, `accrued_mgmt_fee`, `accrued_perf_fee`, `mandate_breach_flags`, `benchmark_nav_at_inception`, `ccp_binding`, plus the SBL six-coordinate vector `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)`. Mutated via L14 `StateDelta`. Owner: handlers per StatesHome C11. **Realism: U1, U7**.
- **M**: `PositionState` record with **field-level writer-cap phantom types** (handler X writes field f only). `PositionVector` with newtype-tagged six coordinates; sum-type `Move` with single-coordinate constructor. (`minsky.md` §4)
- **T**: Read-as-activity; written by handlers; replay determinism via snapshot. (`temporal.md` §4.2)
- **R**: **Partial** — CDM `Position` is scalar; the six-coordinate vector and SBL semantics require a Rosetta extension (`matthias.md` §C / SBL gaps + `D.9`–`D.11`).
- **F**: 2T + 3W + 2C = 7 invariants for L6 PositionState; +6 invariants for L7 PositionVector (`formalis.md` L6, L7).
- **C**: L5, L7 (per-CCP conservation scope), L13 (obligation liveness for SBL recall).

### §3.4 Class C4 — Observations (L10–L13)

**L10. Raw Market Observation**
- **N**: Single attestation `y_t` of an observable (bid/ask/last/settle/swap-rate/CDS-spread/ATM-vol/risk-reversal/butterfly/FX/dividend forecast/borrow-fee/repo-rate). Carries `t_obs`, `t_known`, `source`, `signature`. Bitemporal mandatory. **Realism: U1, U2 + C-A3**.
- **M**: `RawQuote` with refined `Price`, `Tenor`, `BusinessCenter`. `OracleAttestation` wrapper. (`minsky.md` §2.1, §2.2)
- **T**: Out-of-Temporal high-frequency stream → batch ingest via activity; `idempotency_key = hash(topic, t_obs, source, value)`. Awkward fit for tick streams (`temporal.md` §6.2) — high-frequency observations should not be Temporal workflows.
- **R**: **Direct** for many sub-types (`EquityQuote`, `ListedDerivativeQuote`, `FXRate`, `RatesQuote`, `VolatilityQuote`, `CreditSpread`, `ReferenceMark`); **Partial** for `OracleAttestation` envelope. (`matthias.md` §C.1–C.4 + Top-5 Gap #4)
- **F**: Part of L8 (4T + 3W + 2C = 9 invariants for L8 RawObs/Oracle/Snap combined) (`formalis.md` L8).
- **C**: L1, L4, L11.

**L11. Lifecycle / Oracle Attestation**
- **N**: Signed external assertion that triggers a deterministic contract action: corporate-action, barrier, fixing (LIBOR/SOFR/EURIBOR/€STR/SONIA/TONA), exercise notice, default, locate confirmation, regulatory threshold, force-majeure. Distinct from L10 because the consumer is the lifecycle handler / obligation store, not the Pricing DAG. Owner: `oracle-ingest` (per oracle kind). **Realism: U1, U2 + C-A3**.
- **M**: Sum type `LifecycleEvent = CorporateAction | Barrier | Fixing | Exercise | Default | Locate | RegulatoryThreshold | ForceMajeure | …`. Each constructor carries its required fields. (`minsky.md` §2.3)
- **T**: Signal entering a lifecycle workflow; signal carries `idempotency_token`; bounded-retry activity for verification; `idempotency_key = hash(business_event_id, attestor)`. (`temporal.md` §3.8, §4.7)
- **R**: **Direct** for `BarrierObservation`, `ExerciseNotice`, `CreditEventNotice`, `SettlementConfirmation`; **Missing** for `LocateConfirmation`, `ManufacturedPaymentRate`, `DefaultEvent` SBL specifics. (`matthias.md` §D.3–D.11 + Top-5 Gap #2 — SBL recall/locate/rehypothecation gaps).
- **F**: Part of L8.
- **C**: L1, L4, L11.

**L12. External Confirmation / Reconciliation**
- **N**: Inbound ISO 20022 / SWIFT messages confirming or contradicting prior outbound action: `sese.025`/`sese.023`, `camt.053`/`camt.054`, custodian depot statements, CCP clearing confirmations. Distinct from L11 because L11 *triggers*, L12 *confirms*. Owner: `confirmation-ingest`. **Realism: U1, U2**.
- **M**: `ExternalConfirmation` parsed from ISO 20022 envelope. (`minsky.md` partial)
- **T**: Activity result; signal channel for late confirmations; idempotency by `(transaction_id_ref, external_message_id)`. (`temporal.md` §4.7)
- **R**: **Direct** (`ISO20022SettlementMessage`, `SettlementConfirmation`, `CustodianAttestation`) (`matthias.md` §D.1–D.7).
- **F**: Part of L8.
- **C**: L3 (settlement-move closure).

**L13. Calibrated Market Object**
- **N**: Certified Bayesian posterior `(x_{t|t}, P_{t|t})` for a target object (yield curve, vol surface, hazard curve, FX vol cube, correlation matrix). Carries `input_snapshot_id` (FK to L19), `model_id`, `gating_outcome`, `arbitrage_certification_status`. Reaches consumers only when `certified = true`. Owner: `calibration` workflow. **Realism: U6, U8 + C-A6** (calibration model soundness).
- **M**: `CalibratedState` with witness type `arbitrage_certificate`; refined `(model_id, model_version)`. (`minsky.md` §2.5; witness types §0)
- **T**: Singleton long-running workflow per (target_object, model); `ContinueAsNew` on cadence; `idempotency_key = (calibrated_object_id, certification_timestamp, model_id)`; replay-determinism risk register (`temporal.md` §3.2 + §6.5).
- **R**: **Missing** — entire calibrated layer (`CalibratedYieldCurve`, `CalibratedVolSurface`, `KalmanPosterior`, `SensitivityJacobian`, `ValuationRecord`) is CDM-missing. Strategic gap #1; seeds a `cdm-valuation-lib` upstream proposal. (`matthias.md` §E + Top-5 Gap #1)
- **F**: 4T + 2W + 2C = 8 invariants (`formalis.md` L9, includes `CertifiedCalibration / Jacobian / ValuationRecord`).
- **C**: L2 (snapshot determinism), L11 (calibration consistency), L12 (no-arbitrage admissibility).

### §3.5 Class C5 — Effects (L14, L15, L16)

**L14. MoveStream**
- **N**: The canonical record. Append-only, hash-chained, dual-timestamped, CDM-payload-bearing. Single-writer (executor) per v10.3 §7.6. The source from which L8, L9, balances, P&L, and balance-sheet projections derive. Owner: executor. **Realism: U1, U4** (hash-chain tamper-evidence).
- **M**: `Move`, `Transaction`, `StateDelta` as sum types; `Transaction` ≈ `NonEmpty<Move>` with conservation refinement; CDM `BusinessEvent` payload. (`minsky.md` §3.1, §3.2)
- **T**: Activity result (executor commit); `idempotency_key = tx_id` derived from canonical content; replay-determinism: deterministic activity output. (`temporal.md` §4.5)
- **R**: **Direct** to CDM `BusinessEvent`, `PrimitiveInstruction`. (`matthias.md` §C / D / E partial)
- **F**: 4T + 5W + 2C = 11 invariants — the highest count, reflecting load-bearing role (`formalis.md` L10).
- **C**: L1, L3, L5, L6, L7, L8 (lineage, settlement-move closure, conservation, mandate-as-unit, per-CCP, replay).

**L15. ValuationRecord**
- **N**: Per (unit, t, model) tuple: dirty/clean price, accrued, Greeks, `quality ∈ {FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED}`, `attestation_snap` (FK to L19), valuation FSM state. Owner: `pricing` workflow. **Realism: U1, U2, U6 + C-A6**.
- **M**: `ValuationRecord` with model-tagged GADT `'m greeks` for sensitivity Jacobian. (`minsky.md` §3.4)
- **T**: Activity result (pricing); `idempotency_key = (unit_id, snapshot_id, model_id, model_version)`. (`temporal.md` §3.4)
- **R**: **Missing** — see L13 strategic gap #1.
- **F**: Part of L9 (`formalis.md`).
- **C**: L2, L11.

**L16. ObligationStore**
- **N**: Per v10.3 §14.7. Pending discharge requirements with deadlines, discharge predicates, compensation actions. Carries `obligation_id`, `kind`, `created_by_tx_id`, `deadline`, `discharge_predicate`, `compensation_handler`, `status ∈ {PENDING, DISCHARGED, COMPENSATED, DEFAULTED}`. Owner: lifecycle handlers + obligation-discharge workflow. **Realism: U1, U2** + (unwitnessed) liveness over unbounded futures (CORRECTNESS U1).
- **M**: Sum type `ObligationState = Pending | Discharged | Compensated | Defaulted`; refined `obligation_kind` enum. (`minsky.md` §3.5)
- **T**: ChildWorkflow per obligation; durable timer for deadline; signal for discharge; saga compensation pattern. (`temporal.md` §4.6)
- **R**: **Missing** — CDM has no first-class `Obligation`; mapped to lifecycle `BusinessEvent` post-hoc. Sketch in `matthias.md` §F.
- **F**: 3T + 4W + 1C = 8 invariants (`formalis.md` L12).
- **C**: L13 (obligation liveness — *unwitnessed* by any finite test).

### §3.6 Class C6 — Provenance & Orchestration (L17–L24)

These leaves are meta-data; they do not have independent ingress workflows. They are produced and consumed by C1–C5 workflows.

**L17. Attestation Envelope**
- **N**: Signature, key-id, timestamps, chain-of-custody wrapper. Required at every ingress in C4 and at the boundary of L1, L2, L3, L4, L6. **Realism: C-A1 + C-A2** (cryptographic + HSM).
- **M**: `AttestationEnvelope` with refined signature/key types. (`minsky.md` §0)
- **T**: Cross-cutting; carried inside every signal and activity payload. (`temporal.md` §5)
- **R**: **Missing** — no CDM type for cryptographic envelope. Sketch needed; strategic gap #4. (`matthias.md` §G + Top-5 Gap #4)
- **F**: Part of L8.
- **C**: L1.

**L18. Identity & Metadata Keys**
- **N**: Deterministic-hash derivation of `unit_id`, `tx_id`, UTI, USI, `obligation_id`, `snap_id`. The derivation rule is version-pinned (L21). **Realism: U3** (deterministic identity).
- **M**: All refined newtypes (`UnitId`, `TxId`, `UTI`, `USI`, `ObligationId`, `SnapshotId`). (`minsky.md` §0)
- **T**: Pre-registered constants in workflow code; not workflow-managed. (`temporal.md` §1 implicit)
- **R**: **Direct** for UTI / USI (`TradeIdentifier`); **Partial** for internal keys.
- **F**: Part of L1.
- **C**: L8 (replay), L9 (forgetful-functor composition).

**L19. Snapshot**
- **N**: Content-addressed bundle of (L10 ∪ L13) rows used for one reproducible computation cycle. `snapshot_id = hash(canonical_serialise(payload_set))`. Owner: `snapshot-build` activity. **Realism: U3, U8** (deterministic identity, replay determinism).
- **M**: `Snapshot` parsed from canonical-serialise output; witness type `snapshot_certificate`. (`minsky.md` §2.4 + §0)
- **T**: Activity result; `idempotency_key = snap_id` (content-addressed). (`temporal.md` §3.3)
- **R**: **Missing** — no CDM equivalent. Internal to Ledger.
- **F**: Part of L8 + L15 MarketDataSnapshot in FORMALIS (`formalis.md` L15).
- **C**: L2 (snapshot determinism), L8.

**L20. Idempotency Token**
- **N**: Minted at workflow boundary or carried in inbound messages (CDM `EndToEndId`, FpML `messageId`, FIX `ClOrdID`, ISO 20022 `EndToEndId`). Per v10.3 §13. **Realism: U5**.
- **M**: Refined `IdempotencyToken` with namespace prefix. (`minsky.md` §0)
- **T**: 9-shape canonical algebra (`temporal.md` §7): `unit_id`, `tx_id`, `business_event_id`, `obligation_id`, `signal.idempotency_token`, `snap_id`, `(unit_id, version_seq)`, `(workflow_id, run_id)`, `(calibrated_object_id, certification_timestamp, model_id)`.
- **R**: **Direct** for ISO 20022 / CDM tokens.
- **F**: Cross-cutting.
- **C**: L8.

**L21. Version Pin**
- **N**: `(component_name, git_sha, container_digest)` for executor / lifecycle workers / pricers; `cdm_version` for CDM enums and synonyms; `(contract_id, contract_version)` for smart contracts; `(model_id, model_version)` for Kalman/pricing models. Owner: deployment pipeline + governance. **Realism: U6 + C-A5** (CDM/ISO schema stability).
- **M**: Refined `GitSha`, `ContainerDigest`, `ModelVersion`. (`minsky.md` §0)
- **T**: Pre-registered in workflow `RegisterDynamicWorkflow`; recorded with every activity invocation. (`temporal.md` §1, §2.2)
- **R**: **Missing** as a CDM concept; CDM has its own version axis but does not pin third-party model versions.
- **F**: Part of L16 SmartContract / Model code (`formalis.md` L16).
- **C**: L8, L9.

**L22. Hash-Chain Anchor**
- **N**: Genesis hash, per-transaction `prev_hash`, periodic checkpoints. Per Invariant P4. Owner: executor (writes); auditor (verifies). **Realism: U4**.
- **M**: `HashChainAnchor` as refined `Hash256`. (`minsky.md` §0)
- **T**: Pre-registered constant `LedgerGenesis`. (`temporal.md` §1)
- **R**: **Missing** as a CDM concept. (`matthias.md` §A.11)
- **F**: Part of L1 + L10.
- **C**: L8.

**L23. Capability / Permission**
- **N**: StatesHome C4 capability scopes — which subjects can read which `(w, u)`, write which field, emit which event class. Owner: capability-administration workflow. **Realism: U6**.
- **M**: `Capability` as refined sum-type with phantom subject scope. (`minsky.md` §0 + §4)
- **T**: Activity result; signal-driven update. (`temporal.md` §5 partial)
- **R**: **Missing** — no CDM equivalent.
- **F**: Part of L14 (`formalis.md` L14).
- **C**: L14 (capability-scope closure).

**L24. Orchestration State**
- **N**: Workflow histories, activity invocation results, retry counters, durable timer state, FSM cursors, signal channels. **Replay-substrate only; not economic data.** Owner: Temporal worker. **Realism: U6, U8 + C-A9** (workflow-history determinism — TEMPORAL-owned).
- **M**: Opaque to MINSKY; managed by Temporal SDK.
- **T**: Owner of this leaf. (`temporal.md` §4.8, §4.9, §4.10)
- **R**: **Missing** — internal to Temporal.
- **F**: 3T + 3W + 1C = 7 invariants (`formalis.md` L13).
- **C**: L10 (workflow-history replay coherence).

**Tension — jane-street V11 vs. NAZAROV L24.** V11 vetoes "Workflow / Orchestration State as ledger data". NAZAROV L24 keeps it on the spine but explicitly notes "replay-substrate only; not economic data". Reconciliation: **L24 is admitted at the boundary contract level (the Ledger guarantees workflow-history determinism is part of the closed-system property); but no economic invariant references L24 directly**.

---

## §4. Cross-cutting consistency laws

CORRECTNESS catalogues 14 cross-layer laws (`correctness.md` §1):

| # | Law | Data categories tied | Witness? |
|---|-----|----------------------|----------|
| L1 | Lineage Closure | L14 ∋ ∀ inputs in L10/L11 ∋ snapshot id | **Unwitnessed under vendor opacity** (U3 surrogate: trust-assumption registry + threat model + multi-source consensus) |
| L2 | Snapshot Determinism Closure | L13 ↔ L19 ↔ L21 | Witnessed (replay test) |
| L3 | Settlement-Move Closure | L14 ↔ L12 settlement | Witnessed |
| L4 | Bitemporal Coherence | All C1, C4 | **Unwitnessed under unbounded restatement chains** (U2 surrogate: bounded chains + retention horizon) |
| L5 | Per-Event-Class Conservation | L14 + L8 + L9 | Witnessed (per-handler unit test) |
| L6 | Mandate-as-Unit Conservation | L14 + L9 mandate-unit issuance | Witnessed |
| L7 | Per-CCP Conservation Scope | L14 + L9 ccp_binding | Witnessed |
| L8 | Replay Determinism (master) | All | **Unwitnessed under cosmic-ray bit flips** (U4 surrogate: content-addressing + erasure coding + cross-replica verification) |
| L9 | Forgetful-Functor Composition | L14 ↔ CDM mapping | Witnessed (round-trip test) |
| L10 | Workflow-History Replay Coherence | L24 + L14 | Witnessed |
| L11 | Calibration / Valuation Model Consistency | L13 + L15 | Witnessed (metamorphic test) |
| L12 | No-Arbitrage Admissibility Closure | L13 (Θ_AF projection) | Witnessed |
| L13 | Obligation Liveness Closure | L16 + L24 | **Unwitnessed under unbounded futures** (U1 surrogate: bounded-horizon test + structural induction) |
| L14 | Capability-Scope Closure | L23 + all reads/writes | Witnessed |

**4 unwitnessed laws (L1, L4, L8, L13) are the most important Phase 3 risk class** — Phase 3 reviewers must validate the surrogate strategies are sufficient, or escalate as architectural risks.

---

## §5. Fault catalogue

CORRECTNESS produces a 7-cluster × 7-fault-class matrix = 49 cells (`correctness.md` §3). Clusters: I Identity & ProductTerms; II Calendars/Conventions; III Market observables; IV Oracle attestations; V Smart-contract / move stream; VI Calibration latent state; VII Orchestration / settlement / obligations. Fault classes: missing / late / duplicated / contradicted / mis-attributed / silent-corruption / partition.

Each cell: which consistency law breaks, detection mechanism, recovery posture. **Detail in `correctness.md` §3.**

---

## §6. Realism budget (NAZAROV `nazarov.md` §4)

**8 unconditional guarantees (provided by construction):**
- U1 Append-only mutation (C1, C4, C5 by N9).
- U2 Bitemporal indexing on every C1/C4 leaf (N6).
- U3 Deterministic identity for L18 keys.
- U4 Hash-chain tamper-evidence on L14.
- U5 Idempotency on inbound payloads with valid L20 tokens.
- U6 Schema-pinned validation at ingress (N3 + L21).
- U7 Single-writer-per-field on L8/L9 (StatesHome C11).
- U8 Replay determinism for snapshot consumers (with TEMPORAL workflow-history determinism).

**10 conditional guarantees (with named operational assumptions):**
| # | Assumption | Owner |
|---|------------|-------|
| C-A1 | Cryptographic primitive soundness | Head of cryptography |
| C-A2 | HSM custody discipline | Head of security operations |
| C-A3 | Vendor honesty (per attested vendor) | Per-vendor relationship owner |
| C-A4 | Settlement-layer SSI freshness | Settlement-operations team |
| C-A5 | CDM/ISO 20022/FpML schema stability within version | CDM/ISO interop lead (MATTHIAS) |
| C-A6 | Calibration model soundness | Model-validation team |
| C-A7 | Authority registry currency (GLEIF/SWIFT/ISO) | Identity-and-trust operations |
| C-A8 | Closed-system boundary integrity | Architecture review board |
| C-A9 | Workflow-history determinism | TEMPORAL |
| C-A10 | Retention sufficiency | Records management + compliance |

Each assumption: name, scope, owner, violation consequence, detection signal. **Detail in `nazarov.md` §4.2.**

---

## §7. CDM gap analysis (top 5 strategic gaps from MATTHIAS `matthias.md`)

| # | Gap | Severity | Impact | Action |
|---|-----|----------|--------|--------|
| 1 | **Calibrated Market Data Layer** — `CalibratedYieldCurve`, `CalibratedVolSurface`, `KalmanPosterior`, `SensitivityJacobian`, `ValuationRecord` are CDM-missing | Strategic | Entire valuation-document v1.0 stack has no CDM home | Seed `cdm-valuation-lib` upstream proposal |
| 2 | **SBL Recall / Locate / Rehypothecation** — three explicit gaps in `PrimitiveInstruction` choice | Significant | Blocking for SFTR / SLATE | Coordinate with ISLA's CDM working group |
| 3 | **Tokenised Collateral & Backing Attestations** — no first-class `(chainId, contractAddress, tokenStandard, backingModel)` | Significant | v10.3 §10.6 central tokenisation risk | Rosetta extension proposal |
| 4 | **Oracle Attestation Envelope & Snapshot Format** — NAZAROV CC-1 / CC-2 not in CDM | Significant | Required for end-to-end replay determinism | Ledger-internal until CDM catches up |
| 5 | **TradeState ↔ StatesHome 3-map alignment** — asserted but not verified | Architectural | Affects every replay and every regulatory submission | Phase 3 verification deliverable |

Full table of 14/22/26 (direct/partial/missing) in `matthias.md`.

---

## §8. Compositional theorems (FORMALIS `formalis.md` §6)

Five cross-cutting theorems of the form "if data layer satisfies X and executor satisfies Y, then ledger satisfies Z":

1. **Conservation Lifting.** Per-handler structural Σ = 0 (StatesHome C2) lifts to the per-event-class conservation property of v10.3 §13.4 over the entire move stream, conditional on (a) handler-class type-tagging is enforced, (b) executor commits StateDeltas atomically.
2. **Replay Determinism Lifting.** Snapshot determinism (U3) at the data layer + workflow-history determinism (C-A9) at the orchestration layer compose to v10.3 Property 6 (time travel) at the ledger layer.
3. **Obligation Liveness Lifting.** L16 ObligationStore append-only discipline + L24 durable timer + saga compensation lifts to v10.3 P21–P23 obligation liveness, conditional on (a) timer ranges are bounded by retention policy (L7), (b) compensation handlers are total over their input domain.
4. **Substantiation (the balance-sheet IS the ledger).** L14 hash-chained move stream + L18 deterministic identity + multi-replica verification compose to the substantiation property of v10.3 §10 — the balance sheet is a projection of L14, and every entry has cryptographic provenance.
5. **No-Arbitrage Pricing Lifting.** L13 calibrated market objects with `arbitrage_certification_status = certified` + L11 admissible no-arbitrage projection compose to the no-arbitrage admissibility law of valuation v1.0 §5.

**Each theorem is the LaTeX-document target for §invariants of `ledger_data_v1.0.tex`.** Detailed proof sketches in `formalis.md` §6.

---

## §9. Surfaced disagreements / open issues for Phase 3

This section is the most important for Phase 3 reviewers. Disagreements are *not smoothed* — they are surfaced explicitly with attribution.

### §9.1 Leaf-numbering reconciliation (low-risk, mechanical)

Each specialist used a different numbering. NAZAROV's 24 is canonical. The mappings:

- TEMPORAL 31 ↔ NAZAROV 24: TEMPORAL splits L4 into 4a (calendars) + 4b (day-counts) + 4c (BD-conv); L10 into ten sub-streams (FX, equities, rates, etc.). All folds are non-contradictory.
- MINSKY 41 ↔ NAZAROV 24: MINSKY splits at the type level (e.g., `UnitId` and `ProductTerms` get separate sub-leaves in §1.1, §1.2). Non-contradictory.
- MATTHIAS 62 ↔ NAZAROV 24: CDM-type granularity drives sub-leaf expansion (especially L10 raw observables; L14 BusinessEvent payloads). Non-contradictory.
- FORMALIS 16 ↔ NAZAROV 24: FORMALIS folds C6 leaves L17–L22 into L13/L14. **Recommendation: adopt NAZAROV's 24; FORMALIS invariants apply transparently.**

### §9.2 jane-street vetoes vs. NAZAROV/CORRECTNESS leaves (medium-risk)

| Veto | Conflicts with | Reconciliation proposal |
|------|----------------|-------------------------|
| V8 (no CDM enum universe) | testcommittee Phase-1 + correctness §4 generator universe | **Reconcile**: CDM enum closure is a *library version pin* (L21), not a stored data category. Generators consume it via `cdm_version` import, not via a queryable table. |
| V9 (no Policy as load-bearing) | NAZAROV L7 | **Reconcile**: L7 is admitted as a thin sidecar (≤30 fields), not a parallel data spine. |
| V10 (no settlement-layer data sector) | NAZAROV L5 | **Reconcile**: L5 is admitted at the boundary (Ledger consumes), not as Ledger-owned data. |
| V11 (no orchestration state as ledger data) | NAZAROV L24, FORMALIS L13, CORRECTNESS L10 | **Reconcile**: L24 is replay-substrate only; not referenced by economic invariants. |

**Phase 3 must validate that these reconciliations actually hold under the proposed structure**. If any reconciliation collapses under adversarial review, the corresponding leaf must be deleted.

### §9.3 CDM dependency risk (high-risk)

26 CDM types are missing for leaves the proposal requires. 5 are strategic (§7). **Phase 3 must rule on whether the Ledger is willing to operate with CDM-missing leaves represented as Ledger-internal types**, accepting that a future CDM-native migration will be required when the upstream extensions land. The risk: **CDM extensions for the calibrated-market-data layer (Gap #1) may not land for years**.

### §9.4 Unwitnessed correctness laws (high-risk)

CORRECTNESS surfaces 4 of 14 laws as **unwitnessed by any finite test suite**:
- L1 Lineage closure under vendor opacity → surrogate: trust registry + threat model + multi-source consensus
- L4 Bitemporal under unbounded restatement chains → surrogate: bounded chains + retention horizon
- L8 Replay determinism under cosmic-ray bit flips → surrogate: content-addressing + erasure coding + cross-replica verification
- L13 Obligation liveness over unbounded futures → surrogate: bounded-horizon test + structural induction

**Phase 3 must rule on whether the surrogate strategies are accepted as proxies, or whether the unwitnessed laws are themselves accepted as architectural risks (with named owners).**

### §9.5 TEMPORAL awkward-fit categories (medium-risk)

TEMPORAL identifies 6 categories where durable-execution is genuinely awkward (`temporal.md` §6):
1. Retroactive calendar amendments (worst fit)
2. High-frequency tick streams (must be out-of-Temporal)
3. Bitemporal vendor restatements (application discipline, not Temporal feature)
4. Pricing-DAG topology object (recompute, don't store)
5. Kalman ContinueAsNew payload completeness
6. SBL cascade-recall deadline propagation

**Phase 3 must rule on whether these architectural tensions are resolved or whether they require revisiting the Temporal-everywhere posture.**

### §9.6 Goodhart traps (low-risk if monitored)

CORRECTNESS surfaces 4 testing-discipline Goodhart traps (`correctness.md` §4 partial):
1. Snapshot coverage stub-swap (passing tests but not actually replaying)
2. Mutation set exclusion (mutation testing without conservation-violating mutations)
3. Biased generators (PBT generators that miss the failure modes)
4. Aggregation-averaged conservation (bug hidden under per-class averaging)

**Phase 3 must ensure the property-based testing program (CORRECTNESS §4) avoids each trap explicitly.**

### §9.7 Specialist contributions that did not integrate cleanly

None. All 7 specialist contributions integrate cleanly into NAZAROV's 24-leaf spine. The disagreements above are within a coherent integration; none are contradictions.

---

## §10. Phase 3 instructions

This document is the artefact Phase 3 reviewers will attack.

**Phase 3 mode:** adversarial review.
**Convergence:** zero blocking, zero unmitigated major, no minor improvement without trade-off.
**Iteration bounds:** minimum 5 rounds, maximum 20 rounds.
**Arbiter:** independent FORMALIS instance (fresh context).

Reviewers are expected to:
1. Read this document end-to-end before issuing findings.
2. Drill into the named specialist files when challenging a compressed claim.
3. Issue findings classified as blocking / unmitigated-major / minor.
4. Issue a grade for the proposal.

The Data Team is expected to:
1. Address every blocking and unmitigated-major item.
2. Make a documented choice on each minor (accept / reject with reason / defer with reason).
3. Re-issue the proposal as `proposal_v2.md`, `proposal_v3.md`, etc.

**Convergence criteria** (FORMALIS-as-arbiter):
- Zero blocking issues across the latest review.
- Zero unmitigated major issues.
- No minor improvement remaining without offsetting trade-off.

---

## Appendix A. Source files

| Section | File |
|---------|------|
| Master taxonomy + DQ workflows | `phase2/nazarov.md` |
| Engineering principles + vetoes | `phase2/jane_street.md` |
| Workflow shapes | `phase2/temporal.md` |
| Type-driven design | `phase2/minsky.md` |
| CDM cross-walks | `phase2/matthias.md` |
| Cross-layer consistency laws + faults | `phase2/correctness.md` |
| Per-leaf invariants + theorems | `phase2/formalis.md` |
| 19 Phase-1 enumerations | `phase1/*.md` |

## Appendix B. Phase-1 contributors (19)

CARTAN, CORRECTNESS-ARCHITECT, FEYNMAN, FINOPS-ARCHITECT, FORMALIS, GEOHOT, GROTHENDIECK, HALMOS, ISDA-BOARD-ADVISOR, JANE-STREET-CTO, KARPATHY, LATTNER, MATTHIAS (rosetta-cdm-engineer), MINSKY, NAZAROV (data-architect), NOETHER, SBL-SPECIALIST, TEMPORAL-ENGINEER, TESTCOMMITTEE.

(WILL-WILSON was not registered as a Team A agent; the FoundationDB-style determinism perspective is covered by CORRECTNESS-ARCHITECT and TESTCOMMITTEE.)

---

**End of Phase 2 Synthesis Proposal v1.**
