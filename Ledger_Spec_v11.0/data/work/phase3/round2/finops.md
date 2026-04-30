# Phase 3 Round 2 — finops-architect closure-check review

**Reviewer.** Independent finops-architect (fresh context).
**Document under review.** `phase3/round2/proposal_v2.md` (654 lines).
**Prior round verdict.** R1 finops grade D+ with seven BLOCKING items (B1–B7) embedded in the convergent T4 "operational floor missing" theme.
**Mode.** Closure-check on R1 finops blockers; new findings on whatever real-bank operational substance survives.
**Convergence test.** Zero blocking + zero unmitigated major + every minor traded.

---

## §0. Headline

The proposal has moved from D+ "navigation document" toward something a bank operator could read. Five of the seven R1 finops blockers have made it from header to substance. Two have made it to header but **not** to substance. The repeated word "skeleton" in §12 is load-bearing — it is the author admitting that the Operational Floor is a table of contents pretending to be a contract.

**Net grade. C** (up one notch from D+; not yet C+, certainly not B−).

The reasons the grade does not rise further are:

1. §12.1 Reconciliation Matrix is a 14-row stub. It has the shape of a control inventory (source / cadence / tolerance / workflow / owner) but every cell is impressionistic. A real bank reconciliation matrix has ~150 rows because it is per-leaf × per-counterparty × per-product. The proposal owns this gap by deferring to a `reconciliation_matrix.md` companion that does not exist in the bundle.
2. §12.4 Retention is a one-paragraph list of regulations with **no per-leaf × per-regulation table**. R1 finops B4 was specifically that "12 distinct horizons" had been folded into one assumption. v2 has reduced this to two assumptions (C-A10 + a paragraph in §12.4). The matrix is missing.
3. §12.5 Tempo / SLA is two sentences. T+1 affirmation by 9pm ET is named as the headline, but the per-leaf p50/p99 / DORA RTO / RPO matrix is not present.
4. §12.7 CSDR has the schema header (`rate_basis_points, days, source_lei, currency`) but no allocation rule (failing-counterparty vs failing-CSD), no daily-claim FSM, no late-matching fail-attribution discipline.

These four substance gaps are why I do not yet grade this B−. They are also why an operator reading this could not stand up the controls; they are explicitly deferred to companions.

That said, B1, B2, B3, B5, B6, B7 (header), B7 (schema sketch) are at least present. v1 had **none** of them.

---

## §1. Closure check on the seven R1 finops BLOCKERS

I cite proposal_v2 by section, with verbatim line references where load-bearing.

### B1 — Per-leaf reconciliation pair (external_authoritative_source, cadence, tolerance, break_workflow, owner). Status: **PARTIALLY CLOSED.**

**v2 location.** §12.1 Reconciliation matrix (proposal_v2 lines 460–479). 14 rows covering L1–L18 (excluding L7P, L8, L16, L19).

**What landed.**
- The five-tuple from the R1 finding is present as the row schema.
- All 13 leaves the R1 finding named (C1 / C4 / C5 + L5 / L6 / L15) have a row except L7P (Policy), L8 (LegalAgreement), L16 (ReferenceMaster), L19 (ClockAuthority) — these are silently omitted.
- Several cells are concrete enough to act on: L2 "Cross-vendor reconciliation, Daily T+0, 0 (mismatch quarantines), wf-refdata-break, Refdata operations". L6 "CCP daily statement; Custodian daily; Triparty agent, Daily T+1, Per regime, wf-position-break, Middle-office reconciliation".

**What did not land.**
- The "external authoritative source" column is impressionistic on rows that need precision. L3 says "GLEIF CDF" — but GLEIF publishes both a Concatenated File and a Golden Copy with different reconciliation semantics (downloads vs pub/sub). L5 says "Counterparty FpML / sese.025" — but a counterparty does not publish FpML; FpML is a wire format and the authoritative source is the counterparty's confirmation message via DTCC CTM, MarkitWire, or bilateral. L11 says "Inbound ISO 20022" — but ISO 20022 is a *family* (camt.053, camt.054, sese.023, sese.025, semt.018); naming the message types matters because each has a different reconciliation cadence and tolerance.
- The "tolerance" column is a vocabulary collapse. "Bit-identical", "0", "Per regime", "Per FRTB AVA", "Authoritative", "L7Pb tolerance", "FRTB PLA" do not have a common metric. A real reconciliation matrix gives `(absolute_threshold, relative_threshold, escalation_threshold)` per row; v2 gives a free-text label.
- L7P, L8, L16, L19 omitted. L8 (LegalAgreement) reconciliation is not optional — bilateral hash-anchored agreements require periodic counterparty re-attestation; on novation it is the bridge. L19 (ClockAuthority) reconciliation against NTP / PTP / GNSS sources is the entire reason the leaf was added.
- "control_owner" is at the team-name level ("Front-office trade support", "Refdata operations"). R1 finops T11 (trust-assumption owners are job titles, not people) was explicit that owners must be named individuals. v2's §10.2 names individuals for C-A1–C-A12. The reconciliation matrix should match that discipline.
- Cadence collisions are unflagged: L9 "Daily / weekly per asset class" — *which* asset classes daily, *which* weekly. L4 "Daily" — but holiday calendars are republished irregularly, often quarterly.

**Verdict.** The header has landed. The substance is at draft maturity. **PARTIALLY CLOSED — must mature to per-counterparty granularity, named-individual owners, structured tolerance schema, and add the four omitted leaves before R3 admission.**

### B2 — Break-management state machine. Status: **PARTIALLY CLOSED.**

**v2 location.** §12.2 BreakRegister FSM (proposal_v2 lines 481–483). L18 leaf added (proposal_v2 line 68 in §1, line 167 in §4.3 with ADR-3).

**What landed.**
- FSM names the states: `OPEN → INVESTIGATING → ASSIGNED → AGED-1 → AGED-3 → AGED-5 → ESCALATED → AT-RISK → MATERIAL → CLOSED-{CLEAN | ADJ | WAIVED}`.
- Mandatory four-eyes on `CLOSED-WAIVED`.
- Aging thresholds (T+1, T+3, T+5) trigger automatic escalation.
- Materiality bands: AT-RISK ≥ €1M, MATERIAL ≥ €10M.
- ADR-3 cites SOX §404 / BCBS 239 §3 / DORA Art 8 as basis.

**What did not land.**
- **Transition predicates are unspecified.** What event fires `OPEN → INVESTIGATING`? An assignment from a triage queue? A human action? An automated cluster-detect? The FSM names states but not transitions; this is the same defect FORMALIS would flag as κ-totality undefined.
- **No ageing-clock policy.** "T+1 / T+3 / T+5" relative to what — break detection time, break-event observation time, or value date of the affected transaction? On a backdated trade-amend, this matters.
- **No assignment policy.** Who owns each break? Is the assignment per-leaf (matrix lookup) or per-break (workflow decision)? Real-bank break management uses skill-based routing; v2 names none.
- **No materiality-attribution rule.** AT-RISK ≥ €1M on what — gross exposure, net exposure, P&L impact, or position notional? IFRS 13 materiality is on financial-statement impact; reconciliation materiality is typically on gross. The conflation is exactly what BCBS 239 §3 forbids.
- **No closure FSM for the four-eyes attestation.** `CLOSED-WAIVED` is gated by four-eyes but the attestation record is not modelled. No `BreakWaiverAttestation` schema; no signature-binding to the L19 ClockAuthority; no audit-evidence path.
- **No relationship to L17 RegulatorySubmission.** A break that affects a regulatory submission must restate it (DRR amendment chain). v2 does not say so.
- **No `BreakKind` closed sum.** Reconciliation breaks span ~12 categories: settlement-fail, position-mismatch, cash-mismatch, valuation-disagreement, confirmation-late, confirmation-mismatch, regulatory-ack-mismatch, collateral-disagreement, fee-mismatch, corporate-action-mismatch, calendar-mismatch, calibration-mismatch. Conflating them into a single BreakRegister with a uniform FSM masks regime-specific timers (e.g., CSDR ISD+4 buy-in trigger).

**Verdict.** State alphabet present, state semantics absent. **PARTIALLY CLOSED — must specify transition predicates, ageing-clock anchor, assignment / routing policy, materiality basis, BreakKind closed sum, and the four-eyes attestation schema. Without these the FSM is decorative.**

### B3 — SOX / BCBS 239 lineage cursor. Status: **PARTIALLY CLOSED, leaning towards FAILS TO CLOSE.**

**v2 location.** §12.3 Lineage cursor (proposal_v2 lines 485–487). Three sentences total.

**What landed.**
- Named as "typed graph projection over `L13 ⊕ L12 ⊕ L9 ⊕ L10 ⊕ envelopes ⊕ L21 ⊕ capabilities`".
- Materialised forward and reverse edges asserted.
- Citations to SOX §404 / BCBS 239 §3 / DORA Art 8 / IFRS 13 Level 3.
- Implementation note: "Datalog over content-addressed identities".

**What did not land.**
- The graph projection is **not typed.** No node types, no edge types, no schema. R1 finops B3 said "queryable lineage cursor" — meaning a typed query API. v2 has only the noun phrase.
- L11 (ExternalConfirmation), L14 (ValuationRecord), L17 (RegulatorySubmission), L18 (BreakRegister) are missing from the projection. A balance-sheet-line lineage that does not include the L11 affirmation is not SOX-defensible. A regulatory-submission lineage that does not include L17 is incoherent. A break lineage that does not include L18 cannot answer the BCBS 239 question "which breaks affected this number".
- No reverse-walk semantics. "From this Pillar 3 figure, walk back to source observations" is the standard examiner question. v2 names "reverse edges" but specifies neither the closure (transitive vs single-step) nor the cycle policy (DAG-pinned via L21? bitemporal-axis pinned?).
- No latency budget. Examiner expects sub-second response on lineage queries; v2 is silent.
- "Datalog" is a vocabulary; the schema and stratification rules are not given.

**Verdict.** **PARTIALLY CLOSED with a B− margin.** A reviewer with stricter instincts would call this FAILS TO CLOSE — SOX §404 substantive testing requires a queryable artefact, and "Datalog over content-addressed identities" is a one-line implementation hint, not a queryable artefact. I rule PARTIALLY CLOSED only because L13/L12/L9/L10/envelopes/L21/capabilities is the right node set, even if the type discipline is absent.

### B4 — Retention horizons folded into one assumption (~12 distinct horizons). Status: **FAILS TO CLOSE.**

**v2 location.** §12.4 Retention matrix (proposal_v2 lines 489–491). Two sentences.

**What landed.**
- Names the regulatory regimes: SOX 7y; MiFIR 5y; CFTC Part 49 "life of swap + 5y"; BCBS 239 through-the-cycle; FRTB capital-history; CASS / Rule 15c3-3 client-asset; DORA RTO/RPO; GDPR-minimisation conflict.
- Asserts binding to L21 so retention-policy change is itself versioned.

**What did not land.**
- **There is no per-leaf × per-regulation matrix.** R1 finops B4 was specific: "Per-leaf × per-regulation table with horizon, hot/archival, deletion conditions, GDPR-conflict resolution rule." v2 is a paragraph listing horizons. This is exactly the v1 defect.
- The retention assumptions in §10.2 collapse all of this back into single conditional C-A10 ("Retention sufficiency"). The "12 distinct horizons" critique survives unaddressed.
- **GDPR conflict resolution is named but not specified.** GDPR Art 5(1)(e) (storage limitation) genuinely conflicts with MiFIR / CFTC / SOX retention; the standard reconciliation is pseudonymisation-after-business-purpose-expires-but-before-regulatory-purpose-expires, with retention of the pseudonym key under separate access control. v2 names the conflict but offers no resolution rule.
- No hot / warm / archival tiering. MiFIR Art 25(2) wants "readily retrievable" for 5 years; CFTC Part 49 wants "life + 5y" for swaps but allows archival after life. The proposal does not separate these tiers.
- No deletion-condition predicate. Retention horizons end; the deletion-trigger logic must be a queryable predicate over (leaf, jurisdiction, instrument-status, customer-status). v2 offers no predicate.
- No retention-by-legal-hold override. A litigation hold blocks deletion regardless of regulatory horizon; this is omitted.

**Verdict.** **FAILS TO CLOSE.** The header is present, the matrix is not. The R1 finding requires the matrix; v2 has not produced it.

### B5 — IPV / CRR-105 PVA / FRTB AVA on L14 ValuationRecord. Status: **CLOSED (header), PARTIALLY CLOSED on substance.**

**v2 location.** §12.6 IPV / FRTB AVA (proposal_v2 lines 497–499). Field list also referenced in §5.1 (line 255).

**What landed.**
- Schema fields present: `(fair_value_level ∈ {1,2,3}, ipv_status, ipv_variance, ipv_source_id, prudent_valuation_adjustment_components: {market_price_uncertainty, close_out_cost, model_risk, concentrated_position, future_admin_costs, early_termination, operational_risk}, unobservable_inputs[], unobservable_input_sensitivity[])`.
- The seven PVA components correctly enumerate the CRR Article 105 / EBA RTS on Prudent Valuation buckets.
- Reconciliation row L9 "Multi-vendor IPV at FVH" with workflow `wf-ipv-break` and IPV-team owner.

**What did not land — these are still substantive gaps.**
- **`ipv_status` is an undefined enum.** Closed sum needed: `{Pending, Run, Variance-Within-Tolerance, Variance-Above-Tolerance-Approved, Variance-Above-Tolerance-Quarantined, Stale}` or similar. v2 does not enumerate.
- **`ipv_variance` is dimensionless.** Should be `(absolute_amount, currency, relative_pct)`; threshold vs L7Pb tolerance is implied but not specified.
- **No FVH (fair-value hierarchy) determination rule.** Level 1/2/3 classification is itself a control with named criteria (active-market test, observable-input test, materially-unobservable test). v2 stores the level as a field but does not pin the determination procedure.
- **No FRTB PLA (P&L attribution test) schema.** Mentioned only as "FRTB PLA" tolerance in §12.1 row L14. R1 finops M8 was explicit: PnL-explain / FRTB PLA schema needed. The four PLA tests (Spearman, Kolmogorov-Smirnov, mean-ratio, variance-ratio) and the green / amber / red bands are not modelled.
- **No CRR-105 RTS Art 9–17 mapping.** EBA's "core approach" vs "fallback approach" per AVA component is not addressed; for level-2 inputs only the core approach is permitted, etc. The proposal stores the seven components but not the methodology pin.
- **`unobservable_inputs[]` and `unobservable_input_sensitivity[]` are typed as arrays of unknown shape.** Per IFRS 13.93(d)/(h) the disclosure requires `(input_name, range_min, range_max, weighted_average, sensitivity_to_reasonably_possible_change, valuation_technique)`; this should be a closed structured type.

**Verdict.** **PARTIALLY CLOSED.** The closed-sum component list nails the CRR-105 substance — this is the strongest delivery in the operational floor. But the enum fields and the FRTB PLA schema must mature before R3 admission. Calling this CLOSED would let through a valuation record that satisfied the type-checker but not a CRR-105 examination.

### B6 — T+1/T+0 SLA unaddressed. Status: **FAILS TO CLOSE.**

**v2 location.** §12.5 Tempo / SLA matrix (proposal_v2 lines 493–495). Two sentences.

**What landed.**
- The headline is named: "T+1 affirmation by 9pm ET on T+0; T+0 settlement."
- DORA RTO/RPO mentioned.

**What did not land.**
- **There is no matrix.** R1 finops B6 required "Per-leaf p50/p99 ingress SLA, degraded-mode behaviour, DORA RTO/RPO". v2 names neither p50 nor p99 nor degraded-mode nor any per-leaf number.
- The 9pm ET T+1 deadline is a US equity / DTCC NSCC affirmation deadline; for OTC derivatives it is the CFTC Part 23 confirmation timeliness rule (different); for tri-party repo it is the BNYM / JPM cut-off (different); for SBL it is the SLATE / SFTR window (different). v2 collapses these into a single sentence.
- DORA Art 12 requires `recovery_time_objective` and `recovery_point_objective` per ICT system. None named.
- No per-leaf affirmation-status FSM (R1 finops M7). Leaf L11 should have `affirmation_status ∈ {Pending, Matched, AffirmedT0_9PMET, AffirmedT1, Late, ExceptionAged}`; v2 does not.
- T+0 settlement readiness is named but not addressed; the SDR-DTC accelerated-settlement initiative is not modelled.

**Verdict.** **FAILS TO CLOSE.** Two sentences naming the headline does not constitute the matrix R1 demanded.

### B7 — CSDR penalty regime no first-class home. Status: **PARTIALLY CLOSED.**

**v2 location.** §12.7 CSDR penalty regime (proposal_v2 lines 501–503). Also surfaces as L18 reference in §10.2 row C-A4 ("CSDR penalty L18 record").

**What landed.**
- `obligation_kind = CSDR_PENALTY` named as a constructor.
- Schema: `(rate_basis_points, days, source_lei, currency)`.
- L15 Obligation closed-sum framing extends to host this constructor.

**What did not land.**
- **No allocation rule.** CSDR mandates that the failing party owes the non-failing party; in chains (CCP-novated, agent-lender) the attribution is non-trivial. The schema does not name `failing_party_lei` vs `claimant_lei`, only `source_lei`.
- **No daily-claim FSM.** CSDR penalties accrue daily from ISD+1 until settlement; each day's accrual is a separate claim but the firm books a running provision. v2's flat schema cannot represent the accrual / claim / dispute / waive lifecycle.
- **No netting rule.** Penalty Netting Service (T2S) nets across CSDs daily; without modelling the netting layer, the firm's ledger sees gross when the cash settles net.
- **No mandatory buy-in trigger.** ISD+4 (or +7 for SME instruments, +15 for collateral-management transactions) was the original CSDR buy-in trigger; suspended in 2022 but the regime remains on the books and may reactivate. The proposal makes no architectural commitment to support it.
- **No CSDR cash-penalty-vs-late-matching distinction.** CSDR has *cash penalties* (settlement-fail) and *late-matching penalties* (matching-fail); same headline regime, different attribution. v2 conflates.

**Verdict.** **PARTIALLY CLOSED.** The leaf has a home; the home is not yet inhabitable.

---

## §2. Closure summary table

| R1 Blocker | Status | Reason |
|------------|--------|--------|
| B1 Reconciliation pair | PARTIALLY CLOSED | 14-row stub; 4 leaves omitted; tolerance schema unstructured; owners team-level |
| B2 BreakRegister FSM | PARTIALLY CLOSED | State alphabet present; transitions / predicates / BreakKind / waiver-attestation absent |
| B3 Lineage cursor | PARTIALLY CLOSED (margin to FAILS) | Three-sentence stub; node types absent; L11/L14/L17/L18 not in projection; no reverse-walk semantics |
| B4 Retention horizons | **FAILS TO CLOSE** | No per-leaf × per-regulation matrix; collapsed back into C-A10 |
| B5 IPV / FRTB AVA | PARTIALLY CLOSED | CRR-105 components correct; ipv_status / ipv_variance / FVH-rule / PLA schema absent |
| B6 T+1/T+0 SLA | **FAILS TO CLOSE** | Two sentences; no per-leaf p50/p99; no DORA RTO/RPO numbers; no degraded-mode |
| B7 CSDR penalty | PARTIALLY CLOSED | Constructor + schema present; allocation rule / daily-claim FSM / netting / buy-in absent |

**Score: 0 fully closed / 5 partially closed / 2 fails to close.** R1 demanded zero blockers remain; R2 has reduced their severity but eliminated none.

---

## §3. The "skeleton" tell

Five times in §12 the proposal uses the word "skeleton" or defers to a companion file:
- §12.1 "Inlined skeleton (full table in companion `reconciliation_matrix.md`)."
- The companion file is not in the bundle.
- §1 line 47 "Inlined skeleton" for definitions.
- §8 line 316 "Inlined skeleton" for the fault catalogue.
- §0 line 7 "Operational-floor matrices (reconciliation, break-management FSM, lineage cursor, retention, SLA)" listed as if completed.

**The pattern is consistent.** The proposal author has taken every R1 finops blocker, declared a section header, and emitted a stub with a forward reference to a companion that does not exist. This is the same anti-pattern R1 testcommittee called "convergence by table-of-contents" and that R1 jane_street called "rhetorical laundering". The substance has not been written; the obligation to write it has been moved into a footnote.

In a banking control environment, a skeleton FSM is a control that does not exist. SOX §404 ITGC examiners do not accept "skeleton" as a state for a control; they grade it Material Weakness. The honest disposition for v2 is to label every §12 subsection "DRAFT" and forbid R3 admission until the substance lands.

---

## §4. NEW findings (real-bank operational gaps that survive v2)

These are issues v2 has not made worse and v1 did not surface.

### N1 (UNMITIGATED MAJOR) — No Settlement Instruction (SSI) leaf survives V10 deletion

ADR-1 documents the V10 carve-out for L5/L6 caches, and §4.2 collapses v1's "L5 SSI" by stating SSI lives at the boundary. But settlement operations need to *consume* SSI bitemporally — when an old trade settles on a stale SSI version, the firm needs to reconstruct what it knew at booking time. v2 has no leaf or sub-leaf that hosts SSI as bitemporal observed reference data. The solution is to fold SSI as a sub-cohort of L3 PartyLEI (or L11 ExternalConfirmation when DTCC ALERT publishes) with bitemporal reconciliation cadence; v2 currently does neither, and the operational lacuna is unflagged.

### N2 (UNMITIGATED MAJOR) — Tax-treatment / withholding / 871(m) layer absent

Manufactured-payment gross-up rules per jurisdiction are named in L6.7 (proposal_v2 line 219) but no L10 sub-leaf for `TaxTreatmentOracle` lands. R1 finops M2 / sbl Finding 4 / isda M-3 all flagged this; v2 mentions it once and moves on. For a US/EU SBL desk, IRC §871(m) treatment of manufactured dividends is the difference between booking 30% withholding or 0% — a per-trade economic call. There is no first-class data home.

### N3 (UNMITIGATED MAJOR) — Client-asset segregation flag (CASS / 15c3-3) not in L6 schema

R1 finops M4 was raised; the SBL sub-leaf register (proposal_v2 §4.5) does not surface `client_asset_flag`, `segregation_account_type`, `cass_resolution_pack_id`. CASS 7 reconciliation (FCA, daily, zero-tolerance, breach-reportable in 1 business day) is the most regulator-attention-getting reconciliation a UK desk runs. v2 omits it.

### N4 (UNMITIGATED MAJOR) — No PnL-explain attribution record schema (FRTB PLA)

R1 finops M8 raised this. v2 §12.6 mentions "FRTB PLA" as a tolerance but does not model `PnLAttributionRecord = {risk_attributed_pnl, hypothetical_pnl, actual_pnl, mean_ratio, variance_ratio, ks_statistic, spearman_rho, pla_band ∈ {Green, Amber, Red}}`. This is the daily artefact a desk's IMA permission turns on; it is not optional infrastructure.

### N5 (UNMITIGATED MAJOR) — Affirmation-status FSM still absent on L11

R1 finops M7. The 9pm-ET-T+0 affirmation deadline has reconciliation rows in §12.1 but no leaf-level FSM `{Pending, Matched, AffirmedT0_9PMET, AffirmedT1, Late, ExceptionAged}` on L11 ExternalConfirmation. Without it, the SLA matrix has nothing to time against.

### N6 (MAJOR) — `obligation_kind` enumeration not specified

§12.7 introduces `obligation_kind = CSDR_PENALTY` but the closed sum it implies is never enumerated. ObligationKinds in production span ~15 categories: settlement, margin-call, fee, manufactured-payment, dividend, coupon, redemption, recall, locate, regulatory-submission, regulatory-fee, CSDR-penalty, late-matching-penalty, buy-in, mandatory-corporate-action. The closed sum belongs in §5/L15 spec; ADR-3 cites it but the enum is absent.

### N7 (MAJOR) — Trust-assumption registry artefact still abstract

§10.2 names individuals or marks OPEN; ADR-1 references the trust-assumption-registry contract; nazarov_v2.md §2 N12 is cited as the schema home. **The registry schema itself is not in proposal_v2**, despite §17 item 8 instructing reviewers to verify it is "a real artefact". Either it is in `nazarov_v2.md` (which I did not read) or it is missing. As of `proposal_v2.md` alone, the artefact does not appear.

### N8 (MAJOR) — Reconciliation matrix has no aging-policy column

R1 finops T4 listed reconciliation cadence and tolerance but the operational reality is that *aging* is the third metric: how many days a break may live before escalation. The reconciliation matrix conflates this into the BreakRegister FSM, which is acceptable only if every reconciliation routes breaks to L18; v2 does not say so.

### N9 (MAJOR) — No journal-entry / general-ledger projection from L13

L13 MoveStream is the canonical record but the projection to the firm's general ledger (chart of accounts, double-entry posting) is unspecified. ADR-1 implicitly treats L5/L6 as the cache; for finance and treasury reconciliation against the GL, there must be a typed projection `μ_GL: L13 → JournalEntry`. T4b Cache Coherence covers L5/L6 but not GL. R1 finops did not raise this explicitly; in R2 it surfaces because the reconciliation matrix names "Daily T+1" cadences that imply a GL but the GL projection is unmodelled.

### N10 (MINOR) — Decimal precision and rounding mode pinned in L7Pa but not on L14 schema

L7Pa is documented to carry "firm currency / decimal precision / rounding mode" (proposal_v2 line 57) but L14 ValuationRecord field types do not pin this; the IPV component fields could in principle store float. Insist on `Decimal` typing with explicit precision per currency.

### N11 (MINOR) — DORA Art 28 ICT third-party-risk register unaddressed

DORA effective Jan 17 2025; vendor concentration risk register, exit plans per critical ICT vendor, contract-clause register are all expected. v2's vendor-honesty assumption C-A3 names "per-vendor relationship owner" but the register itself is not modelled.

---

## §5. What v2 got right

In fairness:

- §10.2 ownership contract (detection / compensating action / blast radius per conditional assumption) is a bank-grade artefact. C-A1 / C-A2 marked OPEN with "production deployment blocked on assignment" is the disposition R1 finops T11 demanded. C-A11 / C-A12 are well-chosen additions.
- The CRR-105 PVA seven-component enumeration is correct and complete.
- ADR-3 cites the right authorities (SOX §404 / BCBS 239 / DORA Art 8) for the BreakRegister leaf.
- The four-eyes mandate on `CLOSED-WAIVED` is the correct minimum control posture.
- L19 ClockAuthority elevation closes the time-source authority gap that any T+0 / T+1 SLA discussion would otherwise hand-wave.
- The §11 Versioning Algebra distinguishing seven version axes (`drr_rule_set_pin` separate from `cdm_version`) is materially better than v1's L21 conflation.

The **direction of travel** is correct. The substance is half-baked.

---

## §6. Grade

**Grade: C** (was D+ at R1).

The grade rises because:
- Every R1 finops blocker has at least a section heading in v2 (was 0 of 7 in v1).
- §10.2 is a genuine improvement and is bank-grade.
- L17, L18, L19 are correctly justified by ADR.
- The §13 CDM gap re-fetch ruling is honest (matthias verification suspension lifted, headcount corrected).

The grade does not rise to C+ or B− because:
- 2 of 7 blockers FAIL TO CLOSE (B4 retention, B6 SLA).
- 5 of 7 are PARTIALLY CLOSED, where "partially" means "header without substance".
- The "skeleton" pattern is the dominant operational anti-pattern of v2; in a bank control environment it is graded Material Weakness.
- 11 new findings (NEW §4 N1–N11), of which 7 are UNMITIGATED MAJOR.

**Convergence verdict.** **NOT CONVERGED.** R3 must produce: the per-leaf × per-regulation retention matrix; the per-leaf p50/p99 / DORA RTO/RPO SLA matrix; the BreakRegister transition predicates / BreakKind closed sum / waiver-attestation schema; the L11 affirmation-status FSM; the FRTB PLA schema; the closed `obligation_kind` enum; the typed lineage-cursor schema with L11/L14/L17/L18 nodes; SSI bitemporal home; tax-treatment oracle; CASS / 15c3-3 segregation flag; GL projection. Without these the spec remains unshippable.

---

**End of review.**
