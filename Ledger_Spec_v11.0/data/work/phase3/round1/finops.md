# Phase 3 Round 1 — Adversarial Review (FINOPS-ARCHITECT)

**Reviewer:** independent finops-architect (financial systems ops, double-entry, reconciliation, settlement, audit)
**Target:** `Ledger_Spec_v11.0/data/work/phase2/proposal_v1.md`
**Date:** 2026-04-30
**Posture:** adversarial. Per-leaf reconciliation paths, audit-trail traceability (SOX, IFRS, BCBS 239, Basel III/IV, FRTB, EMIR, MiFIR, SFTR, CSDR, CASS, DORA), real-bank operational breaks, regulatory record-keeping under-specification.
**Reading.** Read proposal_v1 end-to-end. Drilled into `phase1/finops.md` (12-floor / 36-item enumeration) and `phase2/nazarov.md` (Realism Budget) for cross-checks against Phase-2 compression.

The grading scale is intentionally severe. A proposal at this layer is a **boundary-contract specification**: every leaf must answer "what external record do I reconcile to, with what cadence, under what tolerance, with what break-management discipline" or it is not implementable. The proposal currently does not.

---

## §0. Headline assessment

**Grade: D+ (BLOCKING). The proposal is structurally elegant and theoretically rigorous, but it is unbuildable as a regulated-firm financial system in its current form because it does not specify the boundary contracts that finops actually owns.** The 24-leaf spine, the 14 cross-layer laws, the 8+10 realism budget, and the StatesHome 3-map ruling are all defensible. What is missing is the **operational floor**: per-leaf reconciliation pairs, break-management state machines, regulatory retention, control attestations, IPV (independent price verification), the audit-trail traceability path from balance-sheet line to source attestation, and the manual-override / four-eyes governance discipline. Without these, the Ledger is a write-only mathematical object that cannot pass an external audit, cannot survive a regulatory exam, and cannot operate under T+1 settlement.

The proposal also under-specifies four classes of regulatory record-keeping (CFTC Part 45/49, EMIR Refit, MiFIR RTS 22, SFTR, FRTB) at a level where the Data Team will have to re-litigate each one in implementation. That is not a Phase-3 minor; it is the core Phase-2 deliverable.

**Counts.** 7 BLOCKING, 9 UNMITIGATED MAJOR, 11 MINOR.

---

## §1. BLOCKING findings

### B1. No per-leaf reconciliation pair is specified anywhere in the proposal

**Where.** §3 per-leaf integrated specification. Every leaf in C1, C4, C5 is described by definition / type / temporal / CDM / invariants / law-participation. **None** carry the field that ops requires: "what external record is this reconciled against, with what cadence, with what tolerance, by what control owner."

**Why this is blocking.** A leaf that is not reconciled is not a leaf — it is a write-only journal entry whose correctness cannot be proved against the world. NAZAROV N1–N12 references "DQ workflows" abstractly; jane-street P6 says "every external read is captured in an L19 snapshot keyed by content hash"; FORMALIS gives invariants. **None of these is reconciliation.** Reconciliation is the comparison of an *internal* record with an *external authoritative* record, the production of breaks, the assignment of breaks to a workflow with a maximum-age SLA, and the closure-or-escalation discipline. Phase-1 finops.md gave a concrete reconciliation pair on every one of its 36 items. Phase 2 dropped this entirely.

**Concrete missing pairs (non-exhaustive).**
- **L2 InstrumentMaster.** No statement of "inter-vendor reconciliation against Bloomberg / Refinitiv / SIX / ANNA daily, T+0, with a break-management workflow." Just "N8 multi-vendor reconciliation gate" cited from temporal.md — not specified.
- **L3 Party/LEI.** No statement of "GLEIF CDF daily ingest with reconciliation against counterparty self-attested LEI on confirmations, lapsed-LEI alert at T-30 days." Without this, EMIR/MiFIR/SFTR field 1.4.4 / 1.3 / 7 will be rejected daily and there is no specified workflow.
- **L4 Calendar.** Inter-vendor reconciliation is not specified — but Phase-1 finops §1.3 gave the concrete break (royal funeral; vendor lag; coupon paid on non-business day). Calibration consistency across vendors is the first-order operational risk and the proposal omits it.
- **L5 SSI.** "Boundary contract" is asserted but the **DTCC ALERT GoldenSource reconciliation** discipline is not specified. SSI is the single most expensive break in operations (BEC fraud); the proposal disposes of it in 6 lines and a veto-reconciliation footnote.
- **L9 PositionState.** Reconciliation of `accumulated_cost`, `hwm`, `accrued_*_fee` against CCP statement / fund-administrator NAV / client statement is not specified. Per-position state is precisely where wash-sale, performance-fee, and CCP VM reconstruction breaks happen. v10.3 §7.4 worked example assumes the reconciliation; the data spec does not enforce it.
- **L10 RawMarketObservation.** Cross-vendor tick-by-tick reconciliation is not specified; FRTB Risk Factor Eligibility Test (RFET) requires it for IMA approval and it is silent.
- **L13 CalibratedMarketObject.** "Arb certificate" exists; **inter-vendor curve / surface reconciliation** (BVAL, Markit, internal) is not specified — IPV (Independent Price Verification, IFRS 13 Level 2/3, CRR Article 105) **requires it as a daily control**.
- **L14 MoveStream.** No reconciliation against custodian movement statement / CCP cash movement file / ISO 20022 inbound confirmation is specified. The MoveStream is "canonical" in the proposal — but to whom? It must reconcile to the external world or it is a fiction.
- **L16 ObligationStore.** Reconciliation against counterparty's CSA-call register, AcadiaSoft / triResolve margin-call reconciliation, trade repository reception report, regulator submission acknowledgement is not specified. v10.3 §14 made obligations first-class precisely so they would have a reconciliation home; the data spec discards that home.

**Severity.** BLOCKING. The proposal is not implementable until each leaf carries `(external_authoritative_source, cadence, tolerance, break_management_workflow_id, control_owner)`. This is the proposal's second-most-important field set after CDM mapping and it is silent.

**Required action.** Add §3.X "Reconciliation pair" line to every leaf in C1, C4, C5, plus L8, L9, L16. The field shape is fixed in finops.md §2 — copy that schema verbatim into proposal_v2.

---

### B2. No break-management state machine is specified

**Where.** Should appear in §3 per-leaf or §4 cross-cutting. Does not.

**Why this is blocking.** Reconciliation produces breaks. Breaks are operational facts with a state machine: `OPEN → INVESTIGATING → ASSIGNED → AGED-1 → AGED-3 → AGED-5 → ESCALATED → AT-RISK → MATERIAL → CLOSED-CLEAN | CLOSED-ADJ | CLOSED-WAIVED`. Each transition has an actor, an SLA, a four-eyes rule for closure, and a regulatory-disclosure threshold. The proposal has L16 ObligationStore (good for *internal* deadlines) but **no break record type, no break FSM, no break audit trail**.

**Concrete consequence.** When the daily DTCC GTR pairing report shows a 0.3% unmatched rate (typical), where is the break recorded? When AcadiaSoft margin-call reconciliation reports a $4.2M call dispute against a counterparty, where is it tracked? When inter-vendor LEI reconciliation flags 14 lapsed LEIs Friday afternoon, who owns the close-by-Tuesday-9am-UTC SLA? The proposal's answer would have to be "in some unspecified ops-tooling outside the Ledger" — but then the **audit trail from balance-sheet line back to source attestation breaks at the reconciliation layer**, which is precisely where SOX §404 / BCBS 239 §6 demand it be unbroken.

**Severity.** BLOCKING. Break management is a first-class data category; CORRECTNESS's 7-cluster × 7-fault matrix (§5) is the *taxonomy* of breaks, but the runtime *register* of a break-as-an-event is not in the spine.

**Required action.** Add **L25 BreakRegister** (or merge into L16 with `obligation_subtype = RECONCILIATION_BREAK`). State machine fully specified. Mandatory four-eyes on `CLOSED-WAIVED`.

---

### B3. Audit-trail traceability from L14 to source attestations is asserted, never demonstrated end-to-end

**Where.** §0 anchor 2 ("MoveStream is the canonical record … Wallet balances, P&L, and the balance sheet are derived views"); §8 Theorem 4 (Substantiation). §3 L14 says "Direct to CDM BusinessEvent, PrimitiveInstruction".

**Why this is blocking.** The substantiation theorem is qualitative. SOX §404, BCBS 239 §3 (lineage), DORA Article 8 (ICT testing), and IFRS 13 Level 2/3 disclosure obligations require a **demonstrated** path: balance-sheet line item L → trial-balance row T → ledger projection P → MoveStream tx τ → CDM BusinessEvent β → input snapshot σ → raw observations {y_i} → vendor attestation envelopes {α_j} → vendor signing key K_j and chain of custody. **Not one** of these hops is specified as a queryable, indexable trail. Without it:

- An auditor asking "show me the source attestation for the 2026-04-29 mark on UNIT XYZ" cannot be answered in finite time.
- A regulator under EMIR Article 9 requesting the lineage for trade U at point-in-time t_obs / t_known cannot be served deterministically.
- IFRS 13.93(d) mandatory sensitivity disclosure for Level 3 inputs has no source layer to point to.

**Severity.** BLOCKING. The proposal must specify the **lineage cursor** — a deterministic many-to-many edge type spanning (L14, L13, L10, L11, L19, L17, L21) such that any balance-sheet line can be traced back to its founding attestations in O(depth) time.

**Required action.** Add §4.X "Lineage Cursor": a typed graph projection over (L14 ⊕ L13 ⊕ L10 ⊕ L11 ⊕ L19 ⊕ L17 ⊕ L21 ⊕ L23) with materialised forward and reverse edges, retention horizon equal to the longest applicable regulatory horizon, and an "audit query" API surface. CORRECTNESS L1 (Lineage Closure) is the *invariant*; the cursor is the *implementation contract* the data layer must expose.

---

### B4. Regulatory record-keeping retention is unspecified — and is jurisdictionally mandatory

**Where.** Implicit in C-A10 ("Retention sufficiency"; owner: Records management + compliance). §6 line: that is the entire treatment.

**Why this is blocking.** Each regulation imposes a different retention horizon on different *artefacts*. The proposal does not enumerate them, does not bind them to leaves, does not specify what is purged when, and does not surface the conflicts (where the longest retention dominates).

| Regulation | Retention | Scope (proposal leaves implicated) |
|---|---|---|
| **SOX §404 / PCAOB AS 1215** | 7 years post-audit | L14, L15, L16, full lineage cursor; L17 envelopes |
| **MiFIR RTS 22** | 5 years; CA may extend to 7 | L14, L19, L18 (UTI/USI), L1, L2 |
| **MiFID II Art 16(11) / RTS 24** | 5 years (records of orders & transactions) | L14, L20 |
| **EMIR Refit Art 9** | 5 years past trade termination | L14 OTC trades, L11 lifecycle, L16 reporting obligation |
| **SFTR Art 4(4)** | 5 years past loan termination | L1 loan-as-unit, L14 SBL moves, L16 |
| **CFTC Part 45 / 17 CFR §1.31** | 5 years readily accessible + 5 years archival | L14, L11, L17 |
| **CFTC Part 49** (SDR) | Life of swap + 5 years | L14, L19, L17, L16 |
| **BCBS 239 / Basel III** | "Through-the-cycle" — effectively indefinite for risk artefacts | L9, L13, L14, L15 |
| **FRTB IMA** | RFET history must be queryable for 1-year and stress windows | L10, L13 |
| **CASS 6.6.34R (UK)** | 5 years for client-asset records | L9 client-segregated wallets, L14 client-asset moves |
| **GDPR / CCPA** | "No longer than necessary"; conflicting with above for PII fields in L3 | L3 PII fields |
| **DORA Art 13** | ICT incident records; 5 years | L17, L24, break register |

**The conflict between GDPR minimisation and SOX/MiFIR maximum is unaddressed.** This is a known operational nightmare: PII in L3 (counterparty contact, KYC documents) must be minimised under GDPR but the EMIR/MiFIR transaction record (containing structured LEI references and possibly natural-person identifiers) must be retained 5 years. The proposal's L3 section makes no statement on PII isolation.

**Severity.** BLOCKING. The realism budget treats this as one assumption (C-A10) with one owner. It is at least 12 distinct retention regimes with conflicting GDPR overlay.

**Required action.** Add §6.X "Retention matrix": per-leaf × per-regulation table with retention horizon, archival vs hot, deletion conditions, GDPR-conflict resolution rule. Bind to L21 VersionPin so a retention-policy change is itself versioned.

---

### B5. No specification of Independent Price Verification (IPV), price-source hierarchy, or daily IPV control

**Where.** L13 CalibratedMarketObject mentions `gating_outcome`, `arbitrage_certification_status`. L15 ValuationRecord mentions `quality ∈ {FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED}` and `attestation_snap`. L10 RawMarketObservation has no source-hierarchy field.

**Why this is blocking.** IFRS 13 Level 1/2/3 hierarchy, CRR Article 105 ("Prudent Valuation"), FRTB AVA (Additional Valuation Adjustments), and SOX ITGC over price feeds require:
1. A **price-source hierarchy** per instrument class (Level 1 = exchange settlement; Level 2 = composite vendor BVAL/MarketAxess CP+ / Markit; Level 3 = single dealer / model).
2. A **daily IPV** control: for every position, an independent price source (independent of front-office) compares against the FIRM ValuationRecord, with documented variance, threshold, and escalation.
3. A **stale-price policy**: when independent source unavailable, what fallback governs and at what valuation-quality demotion.
4. A **Level 3 sensitivity disclosure** (IFRS 13.93(d)): unobservable inputs must be tagged and aggregated for the annual report.

The proposal's `quality` enum is necessary but **not sufficient**: there is no `level` field (1/2/3), no `ipv_status` field (CONFIRMED / DISPUTED / NOT_AVAILABLE), no `ipv_variance` field, no `prudent_valuation_adjustment` (CRR PVA / FRTB AVA), no `unobservable_inputs[]` for Level 3 disclosure.

**Severity.** BLOCKING for any IFRS-reporting / CRR-supervised entity. Will be an audit material weakness on day 1.

**Required action.** Extend L15 ValuationRecord schema with `(fair_value_level ∈ {1,2,3}, ipv_status, ipv_variance, ipv_source_id, prudent_valuation_adjustment_components: {market_price_uncertainty, close_out_cost, model_risk, concentrated_position, future_admin_costs, early_termination, operational_risk}, unobservable_inputs[], unobservable_input_sensitivity[])`. These are not optional; CRR Article 105 enumerates exactly these AVA components.

---

### B6. T+1 (and forthcoming T+0) settlement is not addressed as a performance / data-availability constraint

**Where.** §0 Phase 3 instructions. Not addressed.

**Why this is blocking.** Since SEC Rule 15c6-1 amendment effective May 2024 (US securities at T+1), and with EU/UK consultation paths for T+1 by 2027, the data layer must commit by EOD T+0:

- L1 / L2 unit registration must be complete for every traded unit by T+0 close (else T+1 settlement instruction cannot be projected).
- L11 lifecycle attestation (CA ex-date) must be ingested and applied within hours, not days.
- L12 ExternalConfirmation must accept and process inbound `sese.025` / `camt.054` within minutes of receipt to avoid CSDR penalty (mandatory since 2022; ~€1bn industry penalties annually).
- L14 MoveStream commit latency must support intraday VM cycles.
- L16 ObligationStore liveness must trigger same-day (e.g., SBL recall under GMSLA standard 3-day → today's tighter T+1 reality).

The proposal's TEMPORAL section flags "high-frequency tick streams" as awkward (§9.5) but **no SLA is stated for any leaf**. T+0 demands per-leaf p99 latency SLAs and a degraded-mode policy for SLA breach.

**Severity.** BLOCKING. The proposal is silent on the operational tempo it must support.

**Required action.** Add §4.Y "Tempo and SLA matrix": per-leaf hot-path SLA (ingress p50/p99), degraded-mode behaviour, and recovery RTO/RPO under DORA Article 11 (recovery objectives).

---

### B7. Settlement-fail and CSDR penalty regime have no first-class home

**Where.** L11 mentions "settlement confirmation"; L12 mentions ISO 20022 settlement messages; L16 generically covers obligations.

**Why this is blocking.** Since CSDR Settlement Discipline Regime (Feb 2022 in EU; UK retains a modified version), settlement fails generate **mandatory cash penalties** computed daily until settlement, with detailed apportionment rules:

- Penalty rate per ISIN class per day (basis-point schedule per CSDR RTS 2018/1229).
- Penalty payer and receiver designation (CSD computes and distributes).
- "Mandatory buy-in" trigger after the extension period (currently suspended in EU but live in some jurisdictions).
- T+4 partial-settlement obligations.

The proposal's L11/L12/L16 collapse into "lifecycle attestation / external confirmation / obligation". The **CSDR penalty itself is a financial event with a debit/credit in the firm's books** — it must produce an L14 MoveStream entry tied back to the failed settlement. There is no leaf for the penalty record, no reconciliation against the CSD's penalty file, no obligation-discharge linkage.

**Severity.** BLOCKING for any EU-active firm. Live regulatory exposure.

**Required action.** Either (a) add explicit `obligation_type = CSDR_PENALTY` with full schema (rate, basis-points, days outstanding, source `instruction_id`, counterparty), or (b) acknowledge as a known gap with named owner and a Phase-3 deliverable. v10.3 §14 Table 14.1 omitted this — the proposal inherits the omission.

---

## §2. UNMITIGATED MAJOR findings

### M1. The C-A budget hides the entire IPV / model-validation / control-attestation stack inside C-A6 ("Calibration model soundness")

C-A6 has owner "Model-validation team". This is a 3-line treatment of a function that occupies an entire dedicated team at every Tier-1 firm, with monthly model-validation reports, annual model-risk inventory, FRTB IMA-eligibility certifications, BoE SS1/23 / SR 11-7 governance, and a chain of evidence to L13/L15. The proposal makes no statement about model-inventory data, validation-report records, or model-risk reserve (Phase-1 finops 12.3). All of these are first-class data and the spec hides them in one assumption.

**Severity.** Major. **Action.** Either elevate `ModelInventory`, `ModelValidationReport`, `ModelReserve` as sub-leaves of L7 / L13 / L15, or add a §3.X "Model risk overlay" section.

---

### M2. Tax / withholding / manufactured-payment data is entirely absent

Phase-1 finops §3.4 enumerated tax_status, treaty rates, W-8/W-9 expiry, FATCA/CRS, manufactured-payment classification. Phase 2 dropped this. Manufactured-payment treatment is **economically load-bearing** for SBL (a manufactured dividend treated as gross when treaty says net is a direct cash impact on the lender) and is one of the proposal's own Top-5 Strategic Gaps (#2 SBL Manufactured-Payment Rates). The proposal cites the gap in CDM but does not specify the leaf-level home for the rate, the lifecycle for W-8 expiry, the reconciliation against IRS QI agreement obligations, or the audit trail.

**Severity.** Major. **Action.** Add `TaxClassification` as a sub-leaf of L3 (party-bound) and `ManufacturedPaymentRule` as a sub-leaf of L1 / L6 (terms-bound).

---

### M3. KYC / sanctions / PEP screening is not addressed

L3 mentions "sanctions" classification but no record of the daily sanctions-screening operation, no Refinitiv World-Check / Dow Jones Risk reconciliation, no PEP-flag record, no KYC-refresh-due date and its breach as an obligation. AMLD6 / BSA Section 5318 / OFAC SDN list checks are daily controls; a missed sanction match is a criminal exposure. The proposal treats this as a static classification on L3 — it is in fact a continuous reconciled stream.

**Severity.** Major. **Action.** Add `KYCStatus` and `SanctionsScreeningRun` records, with daily reconciliation pair against named providers and refresh-due as L16 obligation.

---

### M4. CASS / Rule 15c3-3 client-asset segregation has no leaf and no invariant

CASS 6 (UK FCA) and SEC Rule 15c3-3 (US) demand that client assets be **continuously segregated** from house assets, with daily reconciliation, internal vs external records balanced, surplus deposit calculation, and a breach-reporting obligation within hours. Phase-1 finops §3.3 (`custody_topology`, `client_asset_flag`) flagged this. Phase-2 proposal has no `client_asset_flag` on L9 PositionState wallets, no segregation invariant in §4 cross-cutting laws, no "CASS reconciliation" obligation in L16.

This omission alone is a regulatory show-stopper for any UK/US-regulated broker-dealer.

**Severity.** Major. **Action.** (a) Add `client_asset_flag` and `segregation_account_type` on L9 PositionState wallet metadata. (b) Add invariant L15 "Client-Asset Segregation Closure" to §4. (c) Add `obligation_type = CASS_RECONCILIATION_BREACH` to L16.

---

### M5. Corporate-actions are listed as L11 LifecycleOracleAttestation but the multi-vendor reconciliation discipline is not specified

CA breaks are the second-most-expensive operational risk after SSI fraud (industry data: ISITC 2024 survey). Inter-vendor CA reconciliation typically achieves ~99.5% match — the 0.5% requires human review against the issuer's official press release. The proposal treats CA as a single signed attestation. This is fine in theory; in practice **the attestation is constructed *from* a reconciled multi-vendor stream**, and the reconciliation provenance must be in the lineage cursor. Phase-1 finops §5.5 spelled this out; Phase 2 collapsed it.

**Severity.** Major. **Action.** L11 sub-class `CorporateAction` must carry `vendor_attestations[]` (≥2 required), `reconciliation_decision` (auto / manual), `reviewer_id` if manual.

---

### M6. CCP / clearing-member binding is in L9 but the daily CCP reconciliation is not specified

L9 PositionState carries `ccp_binding`. CORRECTNESS L7 (Per-CCP Conservation Scope) is invariant. **Daily reconciliation against CCP statement** (CME Cleared, LCH SwapAgent, Eurex Clearing, ICE Clear) for VM, IM, settlement, default-fund contribution, and Σ-residual (per v10.3 §7.4 worked example) is not specified. Capital implications are direct: CRR Article 305 favourable risk-weight on cleared exposures depends on this reconciliation evidence.

**Severity.** Major. **Action.** Add CCP-statement reconciliation pair to L9 and tie to L16 obligation `obligation_type = CCP_RECONCILIATION` daily T+1.

---

### M7. Bilateral confirmation matching ("affirmation" in T+1 parlance) has no first-class home

DTCC CTM, Markit Connect, Bloomberg VCON: confirmation-affirmation is the bridge between trade booking and settlement instruction. SEC's T+1 mandate added a 9pm-ET-on-T+0 affirmation deadline; missed affirmation is a compliance event with FINRA reporting. The proposal lists L12 ExternalConfirmation but treats it as inbound message ingestion — not as the bilaterally-affirmed economic-terms-match that **is the prerequisite** to L11 settlement projection.

**Severity.** Major. **Action.** Add `affirmation_status ∈ {UNAFFIRMED, ALLEGED, MATCHED, MISMATCHED, AGED}` to L14 transactions of type SETTLEMENT, and a daily affirmation-aging report.

---

### M8. PnL-explain / FRTB PLA tests are mentioned but no schema

§4 Law L11 ("Calibration / Valuation Model Consistency") is "witnessed (metamorphic test)". Phase-1 finops §12.2 specified a `pnl_attribution` record with delta_pnl, parameter_pnl[], gamma_pnl, theta_pnl, cashflow_pnl[], unexplained_residual, tolerance_applied, passed. FRTB PLA (KS test, Spearman test) is a regulatory test for IMA eligibility. The proposal implies the record exists ("ValuationRecord" carries it) but the schema is not stated.

**Severity.** Major. **Action.** Add `PnLAttributionRecord` as sub-leaf of L15 with full schema.

---

### M9. The proposal's "single-writer" discipline (U7) has no specified cross-system write-conflict resolution

When two systems both want to write `UnitStatus[u].lifecycle_stage` (e.g., a CA-handler and a default-handler racing on a defaulted name with a coupon ex-date), the proposal asserts single-writer-per-field (StatesHome C11). It does not say what happens when the unique writer's system is partitioned, when the writer's worker is wedged, or when human intervention is required during a partition. CORRECTNESS Cluster VII (orchestration/settlement/obligations) covers this abstractly; the data spec needs an explicit `manual_override` mechanism with four-eyes approval, recorded in the lineage cursor.

**Severity.** Major. **Action.** Specify `OverrideRecord` (actor, two approvers, justification, original-writer-state, applied-state) as a sub-leaf of L17 / L23.

---

## §3. MINOR findings

- **m1.** L7 Policy is capped at "~30 fields". This is arbitrary; bind to a versioned schema in L21 instead of a field count.
- **m2.** L18 "TradeIdentifier Direct" CDM mapping for UTI/USI is correct, but **UTI-generation waterfall** (ESMA / CFTC algorithm) is itself a versioned policy and must be in L7 with bitemporal pinning. A UTI-waterfall change retroactively re-validates trades.
- **m3.** L4 Calendar bitemporal handling is acknowledged; specify the **inter-vendor break** (different vendors publish corrections at different times) as a recurring break-management workflow, not a Temporal awkward fit.
- **m4.** L19 Snapshot is content-addressed; specify the **canonical-serialiser version pin** in L21 — change to canonical serialisation invalidates every prior snapshot id.
- **m5.** L17 AttestationEnvelope: specify **HSM key rotation** policy and the resulting "old-key signature still valid" provenance (a re-signed-with-current-key policy breaks audit; key history must be retained).
- **m6.** L20 IdempotencyToken's 9-shape canonical algebra is referenced (`temporal.md` §7); copy the table into the proposal — it is too important to leave one indirection deep.
- **m7.** L15 ValuationRecord `quality = INDICATIVE` is undefined operationally; INDICATIVE in front-office means "not for settlement"; INDICATIVE in finance means "not for official PnL"; specify which book consumes which quality.
- **m8.** Timestamp granularity not specified globally; MiFIR RTS 25 demands microsecond for HFT venues, MiFID II demands second otherwise. Specify per-leaf and per-source.
- **m9.** No explicit **negative-balance prohibition** on cash wallets, no specification of overdraft / facility tracking. CASS 7 client-money rules require positive balances.
- **m10.** No statement on **fungibility-preserving amendment classification governance**: the C8 distinction between Preserving and Breaking is load-bearing economically (merging vs. forking lots) and must have a committee owner.
- **m11.** §5 Fault catalogue is a 7×7 = 49 cell matrix in `correctness.md` — should be summarised in proposal_v1 with at minimum the top-5 most-common cells (per industry data) and their handling.

---

## §4. Cross-cutting observations on the proposal's posture

1. **Mathematical elegance over operational realism.** The proposal is the work of mathematicians, type-theorists, and orchestration engineers. The finops voice that wrote `phase1/finops.md` is missing in `phase2/`. The result: the spec is internally consistent but does not specify the controls a CFO has to attest to.
2. **The "boundary contract" doctrine is asserted but unenforced.** SSI (L5), KYC, sanctions, custody-topology, segregation, IPV, and tax all "live at the boundary" — yet there is no specified handshake protocol, no SLA, no reconciliation evidence trail, no break workflow. "It's the boundary's problem" is not a finops answer; it is finops abdication.
3. **Vetoes over additions.** Jane-street vetoes V8/V9/V10/V11 collapse legitimate finops categories (configuration, settlement, orchestration) to "thin sidecars" without specifying the fields. This is anti-engineering posturing where engineering is needed. **The vetoes are aspirational; the production system requires the categories**, just not as bloated tables.
4. **CDM dependency is a real risk.** §9.3 is correct that 26 missing CDM types is a strategic risk. The proposal's posture — operate with Ledger-internal types until CDM catches up — is correct **if and only if** the Ledger-internal types are themselves specified at the same fidelity. They are not.

---

## §5. Recommended Phase-3 path

To clear blocking items, the Data Team should produce **three companion documents** alongside `proposal_v2.md`:

1. **`reconciliation_matrix.md`** — per-leaf × external-source × cadence × tolerance × control-owner.
2. **`retention_matrix.md`** — per-leaf × per-regulation × hot/archival × deletion-condition × GDPR-conflict-resolution.
3. **`tempo_sla_matrix.md`** — per-leaf × p50/p99 ingress SLA × degraded-mode × DORA RTO/RPO.

Without these, no number of FORMALIS-arbitrated rounds will produce an implementable spec.

---

## §6. Grade

**Grade: D+ (BLOCKING).**

- Conceptual architecture: A− (the spine is sound).
- Type-driven correctness: B+ (FORMALIS / MINSKY rigour is real).
- Operational readiness: D (blocking items B1–B7 above).
- Regulatory readiness: D− (retention, IPV, CSDR, CASS, FRTB unspecified).
- Audit-trail traceability: C− (asserted; not implementable end-to-end).

**Convergence verdict.** Cannot converge in this round. Minimum **3 additional rounds** required to clear B1–B7, plus the three companion documents. Phase 3 should not advance to FORMALIS-as-arbiter until the Data Team responds with proposal_v2 addressing every blocking item by name.

---

**End of FINOPS-ARCHITECT Phase 3 Round 1 review.**
