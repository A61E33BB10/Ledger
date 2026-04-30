# Phase 3 Round 1 — SBL Adversarial Review of `proposal_v1.md`

**Reviewer.** Margaret Chen — sbl-specialist (GMSLA / ISLA Best Practice / SFTR / FINRA SLATE / EU SSR / CSDR).
**Target.** `data/work/phase2/proposal_v1.md` (10 sections, 24-leaf NAZAROV spine).
**Lens.** Does the proposal carry the SBL operating reality? Specifically: is the six-coordinate position vector L9 treatment correct; are locate evidence, manufactured-payment rates, recall windows, RQV agreement parameters, rehyp-cap counter, agent-lender disclosure, cascade-recall state, MMF reinvestment NAV, and CSDR FOP-exemption flag actually surfaced as data; does CDM Top-5 Gap #2 (SBL recall/locate/rehypothecation) block SFTR/SLATE; and what does the proposal silently omit?
**Source corpus actually inspected.** `phase2/proposal_v1.md` end-to-end; `phase2/matthias.md` §D.9–D.11, §F.1, §F.3, §F.5, §G.3; `phase2/formalis.md` §2 L6–L7, §3 A11–A14; `phase2/nazarov.md` §2 L9 + §3 L11; `phase1/sbl.md` §§1–10 (50 enumerated items, 26 SBL-tagged).

---

## §0. Verdict in one sentence

The proposal is structurally correct on the L9 six-coordinate vector and the locate / manufactured-payment / RQV / recall / rehyp-cap data items **exist in the source corpus** — but the proposal **silently compresses fourteen of them into single-line bullets inside L9 and L11**, with no per-leaf field set, no per-leaf invariant, no SFTR/SLATE field-level cross-walk, and no acknowledgement that proposal §7 Gap #2 ("SBL Recall/Locate/Rehypothecation") is **today blocking** for both regulatory regimes the proposal claims SBL satisfies. The compression is the defect, not the spine.

---

## §1. What the proposal got right

1. **Six-coordinate vector lives at L9, with FORMALIS L7 as the type-level home.** Proposal §3.3 explicitly names `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` and routes invariants through FORMALIS L7. NAZAROV §2 L9 confirms. This is the correct decision: the vector is per-`(wallet, unit)` state, monotone-carrier, mutated only via L14 StateDeltas. The Single-Coordinate Move Principle (FORMALIS L7.T2) is type-level via phantom-typed `Move[Coordinate]`. This matches v10.3 §15.
2. **Conservation lifting.** Proposal §8 Theorem 1 lifts per-handler Σ=0 to per-event-class conservation; FORMALIS L7.W1 gives the closed-form `Σ(own + borr - onloan - coll_rehyp) = externally_issued(u)`. This is the correct conservation law for SBL — it captures borrow/lend symmetry and the rehyp tail.
3. **Title-transfer vs Pledge regime as a `legal_regime` field.** SBL Phase-1 §1.4 elevates this as a ProductTerms field; the proposal absorbs it into L1 ProductTerms variant (proposal §3.1 L1-N), which is correct. P&L formula divergence between TT and SI regimes (v10.3 §13.13 remark) is preserved.
4. **CDM Top-5 Gap #2 named.** Proposal §7 row 2 explicitly flags "SBL Recall / Locate / Rehypothecation" as **Significant** and as **Blocking for SFTR/SLATE**. This is a non-negotiable gap and the proposal does not pretend otherwise.
5. **Locate as L11 lifecycle attestation, not L10 market data.** Proposal §3.4 L11-N puts `LocateConfirmation` under L11 (signed external assertion that triggers a deterministic contract action) — correct, because locate gates a smart-contract pre-condition (P14 Locate Before Short), it is not a price feed.
6. **CSDR FOP-exemption mention.** SBL Phase-1 §3.8 carries the 2023 Refit FOP exemption flag; CORRECTNESS L3 settlement-move closure references it. This is correctly preserved in the spine.

---

## §2. Findings

I attack item by item. Severity is **BLOCKING** (must fix before convergence), **UNMITIGATED MAJOR** (must fix or document trade-off), **MINOR** (deferable with reason).

### Finding 1 — BLOCKING — L9 / L11 sub-leaf compression hides 14 SBL data items

The proposal's §3.3 L9 entry has **a single line** mentioning the six-coordinate vector. Its §3.4 L11 entry mentions **"locate confirmation"** in a parenthesised list and routes to MATTHIAS §D.9.

These two entries together are claimed to cover:
- **5.3 SBLLoanUnitState** (50+ fields decomposed across the StatesHome 3-map)
- **5.6 LocateReservationLedger** (over-location prevention, §13.16)
- **5.7 CascadeRecallState** (saga workflow, §17.5; on-lending chains)
- **5.8 RehypCapCounter** (Rule 15c3-3(b)(3) 140% cap)
- **5.9 RegulatoryReportingCursor** (SFTR / SLATE per-loan state)
- **3.3 BorrowFeeQuote** (intraday fee surface — distinct from L10 prices)
- **3.4 RebateRateFix** (cash-collateralised lending rebate)
- **3.5 ManufacturedPaymentRate** (tax-adjusted)
- **3.6 RQVSnapshot** (10:00 / 14:00 / 17:00 UTC IBP-189 cadence)
- **3.9 MMFNAV** (cash-collateral reinvestment)
- **4.1 LocateConfirmation** (with `regulatory_basis ∈ {SSR_12_1_a/b/c, RegSHO_203_b_1}`)
- **4.5 BuyInEvent** (P18 carve-out — only operation that writes lender's `own`)
- **1.6 TripartyAgreement** (cut-off times, RQV currency, eligibility-set-ref)
- **1.7 AgentLenderDisclosure** (IBP-307 reallocation event — lender LEI on a live loan changes)

**None of these items are named at the leaf level in §3** of the proposal. They are present in the source corpus (sbl.md), and MATTHIAS §D.9–D.11 + §F.1 + §F.3 + §F.5 + §G.3 carries the Rosetta sketches, but the proposal's per-leaf integrated specification (§3) does not surface them. A reader of §3 alone would not know that `LocateReservationLedger`, `CascadeRecallState`, `RehypCapCounter`, `RQVSnapshot`, `ManufacturedPaymentRate`, `AgentLenderDisclosure`, `MMFNAV`, `BuyInEvent`, or the SLATE / SFTR per-loan reporting cursor exist as first-class data.

**Why blocking.** §3 is the per-leaf integrated specification. If a leaf is not named at §3, no FORMALIS invariant is compiled against it, no MINSKY parsed type is produced, no TEMPORAL ingress shape is fixed, no MATTHIAS CDM cross-walk is targeted, no NAZAROV DQ workflow is owned. The proposal advertises 24 leaves; for SBL, that is **24 minus the 14 sub-leaves silently elided** = the proposal is under-specified by ~58% on SBL surface area.

**Required fix.** Either (a) lift the 14 items as L9.1–L9.14 / L11.1–L11.7 sub-leaves in §3, or (b) add a §3.3a "SBL sub-leaf register" cross-referencing sbl.md §§1–6 entry-by-entry with the per-leaf six-line block (N/M/T/R/F/C). Status quo — a parenthesised list — is not a specification.

### Finding 2 — BLOCKING — CDM Top-5 Gap #2 is conceded, not resolved; SFTR / SLATE today rejects what the Ledger emits

Proposal §7 row 2 acknowledges Recall / Locate / Rehypothecation are CDM-missing. MATTHIAS §F.3 carries the Rosetta sketches for `SBLRecallInstruction`, `SBLLocateInstruction`, `SBLRehypothecationInstruction` to be added to the `PrimitiveInstruction` choice. **Today, none of these are in CDM v6.0.0.**

The proposal's posture (Gap #2 column "Action: Coordinate with ISLA's CDM working group") is honest about the upstream timeline, but the proposal does **not** specify the runtime contract for the Ledger in the meantime. Concrete consequences:

1. **SFTR field 2.18 Termination/Recall date.** SFTR Annex Table 2 requires a recall flag and date. Without `SBLRecallInstruction` in CDM, the BusinessEvent payload that L14 emits has no canonical recall-event encoding; the Ledger must fall back to a generic `TerminationInstruction` or `QuantityChangeInstruction`. This is what every SFTR-reporting firm does today — but it requires a deterministic, version-pinned synonym map from the Ledger-internal recall encoding to the SFTR Action Type. The proposal does not document that the synonym map is owned at L7 (Policy/Configuration) or as part of L21 VersionPin.

2. **SLATE field 7 (Termination Date) and field 23 (Loan Modification Type).** FINRA Rule 6500 lists 6 lifecycle events (New Loan / Pre-Existing Loan Modification / Modification / Cancel / Correction / Delete). A recall is reported as a Modification with a recall-specific reason. Without a CDM-canonical recall encoding, the SLATE field-mapping layer must re-encode from a Ledger-internal event type. Proposal §3.4 L11 says **"Direct for BarrierObservation, ExerciseNotice, CreditEventNotice, SettlementConfirmation; Missing for LocateConfirmation, ManufacturedPaymentRate, DefaultEvent SBL specifics"** — this is correct, but the proposal does not surface the SLATE field-coverage matrix as data. There is no L7 or L21 entry that pins the SLATE field-list version (24 required fields, 192 sequence options, 66 conditionality options per sbl.md §5.3 / §7).

3. **Article 15 SFTR collateral re-use disclosure.** The proposal mentions rehypothecation but does not surface the **prior-disclosure documentation flag** as a first-class data item. SBL Phase-1 §7 list item "SFTR Article 15 documentation flag" is in the cross-reference table but does not appear in §3 of the proposal. Without it, P19 (rehyp regime compliance) cannot be evaluated for an EU-side leg, and the SFTR Article 15 attestation is non-existent in the data layer.

**Why blocking.** Gap #2 is on the proposal's own Top-5; the proposal's mitigation is "wait for ISLA / CDM working group". That is not a runtime contract. The Ledger ships before CDM does. The proposal must either (a) commit Ledger-internal types for the three SBL primitives and pin them at L21, with a documented forward-migration path, or (b) explicitly state the regulatory submission story in the interim (which fields of SFTR / SLATE are filled from which Ledger-internal types, and at what version pin). Neither is in `proposal_v1.md`.

### Finding 3 — UNMITIGATED MAJOR — Recall window deadline math is unsurfaced

IBP-328 specifies the recall notification deadline as **(market close − 1 hour) − max(2 business days, standard settlement cycle)**. For US equity (T+1 settled) that is one calculation; for EU equity (T+2 settled) it is another. For Eurobonds, the cycle differs again. The deadline is the **decreasing measure** that drives every recall obligation lifecycle.

The proposal places "deadline" inside L16 ObligationStore (proposal §3.5 L16-N: "Pending discharge requirements with deadlines, discharge predicates, compensation actions"). MATTHIAS §F.6 sketches the `Obligation` type. **But the proposal nowhere specifies that the recall deadline is computed from MarketCalendar (sbl.md §1.9) + settlement cycle + locale-specific business-day convention — and the input data items (DVP cutoff, FOP cutoff, ISO 20022 cutoff, auto-partial cutoff) are not surfaced as L4 fields.**

Proposal §3.1 L4 "Calendar/Convention" mentions holiday calendars and day-counts but does **not** name market cut-off times. The market cut-off catalogue is the load-bearing input to (a) IBP-124 "instruct 1 hour prior to market cut-off", (b) IBP-328 recall notification deadline, (c) CSDR penalty start-date computation, (d) RQV agent allocation cut-off. Without the cut-off fields explicit at L4, every SBL deadline computation is unsourced.

**Required fix.** L4 minimum field set must add `dvp_cutoff`, `fop_cutoff`, `iso20022_cutoff`, `auto_partial_cutoff`, `t2s_partial_hold_release_cutoff`, all per `market_iso`. Alternatively, lift sbl.md §1.9 MarketCalendar as an explicit sub-leaf L4.x with this field set.

### Finding 4 — UNMITIGATED MAJOR — Manufactured payment is described but not data-modelled

Proposal §3.4 L11 lists "manufactured-payment" inside the LifecycleEvent sum type and §7 Top-5 Gap #2 includes "ManufacturedPaymentRate" as Missing in MATTHIAS §D.10. Proposal §3 has **no field set** for the manufactured-payment data item. The required fields per sbl.md §3.5 are: `corp_action_event_id`, `lender_country`, `borrower_country`, `treaty_rate`, `gross_amount`, `manufactured_amount`, `is_full_pass_through`. The required oracle (sbl.md §4.3 TaxTreatmentOracle) has its own `treatment ∈ {full_grossup, withhold, treaty_relief, manufactured_overseas_dividend}`, `effective_rate`, `signed_off_by`.

These items are SBL-specific. They are **also** US §871(m) and HMRC-manufactured-payment-relevant. They are not duplicates of L11 generic CorporateActionAnnouncement — the manufactured payment is a **derived obligation** from the CA on lent securities, not the CA itself. The deduction-rate for the borrower depends on lender/borrower jurisdictions and treaty status, which are PARTY (L3) attributes consumed at the manufactured-payment event time.

**Required fix.** Either lift `ManufacturedPaymentRate` and `TaxTreatmentOracle` as L11 sub-leaves with field sets and CDM-Missing flag, or add a §3.4a sub-leaf register pointing to sbl.md §§3.5 + 4.3 + matthias.md §D.10. Without it, the cross-border SBL tax computation is data-layer-undefined.

### Finding 5 — UNMITIGATED MAJOR — RQV agreement parameters not surfaced as L1 / L11 data

IBP-189 specifies three triparty cadences: 10:00 UTC start-of-day, 14:00 UTC intraday, 17:00 UTC end-of-day. RQV agreement is the data that drives `coll_recv` / `coll_post` / `coll_rehyp` writes when collateral_method = `non_cash_triparty`. The triparty agent (Euroclear, Clearstream, BNYM, JPM, State Street, Citi) is a **virtual entity** in the Ledger (sbl.md §1.6 — eight agents in practice).

Proposal §3.1 L1 ProductTerms covers the loan unit's `collateral_type`. Proposal §3.1 L6 LegalAgreement covers GMSLA / CSA. Neither names `TripartyAgreement` (sbl.md §1.6) or `RQVSnapshot` (sbl.md §3.6). MATTHIAS §G.3 covers GMSLA generically but not the triparty trilateral agreement.

**Required fix.** Add TripartyAgreement as an L6 sub-leaf with field set: `agent_lei`, `lender_account`, `borrower_account`, `eligibility_set_ref`, `rqv_currency`, `rqv_calculation_method`, `intraday_revisions_allowed`, `auto_substitution`, `concentration_overrides`, `cut_off_times[market]`. Add RQVSnapshot as an L11 lifecycle attestation with field set: `triparty_agreement_ref`, `snapshot_time`, `rqv_currency`, `rqv_value`, `agent_allocation_report_ref`, `agreement_status ∈ {agreed, disputed, pending}`. Without these, daily RQV-vs-Ledger reconciliation has no canonical data target.

### Finding 6 — UNMITIGATED MAJOR — Cascade-recall topology is mentioned in §9.5 but not specified anywhere

§9.5 row 6 lists "SBL cascade-recall deadline propagation" as a TEMPORAL awkward-fit category. SBL Phase-1 §5.7 specifies the data: `root_recall_id`, `parent_loan_id`, `cascaded_loans[(loan_id, recall_qty, child_workflow_id)]`, `timeout`, `buy_in_fallback_triggered`. This is on-lending-chain workflow state. It is **economically load-bearing** because under GMSLA 9.3, when Bob has on-lent the security to Charlie and Alice recalls from Bob, Bob's failure to recall from Charlie cascades into a buy-in cost attribution chain.

The proposal places this at L24 OrchestrationState ("replay-substrate only; not economic data"), and routes it through V11 (no orchestration state as ledger data). **This is wrong for SBL.** The cascade-recall *workflow state* is replay substrate; the **cascade-recall topology** (which loans are downstream of which) and the **buy-in cost attribution chain** are economic data — they determine compensation flows, P&L attribution, and CSDR-claim ownership.

**Required fix.** Lift cascade-recall topology either as an L9 sub-leaf (per-position SBL state) or as an L16 Obligation sub-kind (`SBL_RECALL_CASCADE`). The workflow state remains at L24, but the **economic graph** it traverses is L9 / L16 data. Without this distinction, V11 silently amputates a load-bearing SBL data item.

### Finding 7 — UNMITIGATED MAJOR — Rehyp cap counter and over-location ledger missing from §3

`RehypCapCounter` (sbl.md §5.8) enforces SEC Rule 15c3-3(b)(3) 140% × customer-debit-balance cap. P19 (rehypothecation regime compliance) requires it as a runtime check at the smart contract pre-condition layer. `LocateReservationLedger` (sbl.md §5.6) prevents over-location: multiple locates against the same available inventory, an SSR Article 12(1)(c) and Reg SHO Rule 203 violation.

Both items are **per-(broker_dealer, security)** or **per-(lender, security)** counters that mutate on every locate-issuance / rehyp-write / customer-debit-balance change. They are not generic balances; they are **regulatory-cap counters** with unique aggregation semantics (BD-level for 15c3-3, lender-level for locate). Neither is named in §3.

**Required fix.** Lift as L9 sub-leaves (per-position state with non-standard aggregation key). Specify the aggregation rule: `RehypCapCounter` keys on `bd_lei` (US BD regulatory aggregation rule); `LocateReservationLedger` keys on `(lender_lei, isin)`. Specify the recalculation trigger: every customer-debit-balance move and every `coll_rehyp` write for the cap; every locate issuance / expiry / conversion for the ledger. Without these, P19 is unsourced and SSR Article 12(1)(c) violations cannot be statically detected at the smart contract pre-condition gate.

### Finding 8 — UNMITIGATED MAJOR — Agent-lender reallocation breaks "lender wallet identity is immutable" silently

IBP-307 specifies that agent lenders may reallocate beneficial ownership on a live loan. The borrower's view is unchanged; the lender LEI on the loan unit changes. SFTR Counterparty 1 = ultimate beneficial owner LEI per ESMA Q&A — so reallocation triggers a SFTR MODI counterparty change.

The proposal's §3.3 L9 says "PositionState mutated via L14 StateDelta" and FORMALIS L7.W1 references `entity` indices. **The proposal does not say** whether the lender LEI on a live loan unit is immutable (forcing close-and-reopen, which loses the SFTR UTI continuity) or mutable as a state-only update (which requires a special StateDelta kind that does not write any of the six coordinates).

SBL Phase-1 §1.7 specifies AgentLenderDisclosure as static data and §5.3 mentions "reallocation event in S_live (state-only update per §13.7 state machine)" — but proposal §3 does not reference the §13.7 reallocation transition. MATTHIAS does not have an `AgentLenderReallocation` event.

**Required fix.** Either (a) commit that lender LEI is mutable on the loan unit with a state-only StateDelta (which requires a P-invariant exempting it from coordinate-conservation), or (b) commit that reallocation is close-and-reopen (which requires a SFTR-UTI-preserving construct). The proposal as written is silent and either choice has SFTR consequences.

### Finding 9 — MINOR — CSDR FOP-exemption flag is "metadata" not "data"

Proposal §3.4 L12 ExternalConfirmation references CSDR penalty notifications. SBL Phase-1 §3.8 carries the `is_csdr_fop_exempt` flag (per 2023 Refit). The proposal does not surface this flag as a field on `CSDRPenalty`. Without it, the failing-party attribution algorithm cannot suppress non-attributable FOP collateral fails — and the Ledger emits CSDR claims that the receiving party is entitled to dispute.

**Required fix.** Add `is_csdr_fop_exempt: bool` to L12's CSDR penalty sub-shape. Document the exemption logic at L12 or L7 Policy.

### Finding 10 — MINOR — MMF reinvestment NAV missing for US cash collateral

`MMFNAV` (sbl.md §3.9) is a daily NAV of the money-market fund into which cash collateral is reinvested. In the US example v10.3 §13.14, the fixed `collateral_amount` obligation and the floating reinvestment-asset value are two distinct ledger objects. Without the MMFNAV item, reinvestment risk (the gap between obligation and asset) is unmonitored.

**Required fix.** Add as L13 CalibratedMarketObject sub-leaf or L10 RawMarketObservation sub-leaf with field set: `fund_lei_or_cik`, `ticker`, `nav`, `nav_date`, `is_constant_nav`, `breaking_buck_indicator`, `2a-7_compliance_flag`. Status: covered in MATTHIAS only as a passing reference.

### Finding 11 — MINOR — ESMA / SEC restricted-list data not surfaced

`RegulatoryRestrictionList` (sbl.md §2.5) includes `list_id ∈ {ESMA_SHORT_BAN, RCA_EMERGENCY_BAN, SEC_REGSHO_THRESHOLD, OFAC, EU_SANCTIONS, FCA_RESTRICTED}`. These gate the four-move lending transaction and the short-sell `own -= Q` move. Proposal §3.1 L7 Policy mentions tolerance thresholds and accounting class but **not regulator-published restriction lists**.

**Required fix.** Either lift as L2 InstrumentMaster sub-leaf (per-ISIN restriction flag) or as L11 lifecycle oracle (per-publication event). SBL Phase-1 §2.5 places it at Reference; CORRECTNESS does not catalogue. Without the data item, P14 (Locate Before Short) jurisdictional gates cannot fire and SSR Article 23 emergency bans (intraday-effective) cannot block trades.

### Finding 12 — MINOR — NSP threshold table absent

`NSPThresholdTable` (sbl.md §2.6) carries 0.2% / 0.1% / 0.5% thresholds per jurisdiction with the issuer share-capital reference. ESMA70-448-10 proposes centralisation. Without it, daily NSP computation fails. Severity is minor only because NSP is a regulatory submission, not a Ledger commit gate; it does not block the move stream.

### Finding 13 — UNMITIGATED MAJOR — P18 buy-in carve-out unsurfaced

Per v10.3 §13.21 P18, buy-in is the **only** SBL operation that writes the lender's `own` coordinate (because the lender's securities never came back, so a market buy-in restores them). This is a genuine exception to the conservation lifting and **must** be acknowledged in FORMALIS L7.W1 / W2 as a guarded handler. Proposal §8 Theorem 1 says "per-handler structural Σ=0 lifts to per-event-class conservation" — for buy-in this lifts only with the carve-out.

**Required fix.** Either FORMALIS L7 must add a `BuyIn` handler in W1/W2 with the explicit guard, or the proposal §8 Theorem 1 must explicitly enumerate buy-in as the exception to the per-handler structural zero-sum. Currently neither does.

### Finding 14 — MINOR — Borrow fee quote vs rebate rate fix duality

SBL has two rate paradigms depending on collateral_type: a **fee** for non-cash collateralised loans (borrower pays the lender bps on loan value) and a **rebate** for cash-collateralised loans (lender pays borrower at benchmark + spread on cash collateral). Sign convention reverses. Proposal §3.4 L10 RawMarketObservation lists "borrow-fee" and "repo-rate" but not the rebate-fix-with-spread surface.

**Required fix.** Add `BorrowFeeQuote` and `RebateRateFix` as L10 sub-leaves with the dual field sets per sbl.md §3.3 and §3.4. Note that benchmark cessation events (LIBOR-style) require fallback application and per-loan effective-rate substitution — a material lifecycle event.

### Finding 15 — MINOR — Tokenised collateral L2 sub-leaf absent

Proposal §7 Top-5 Gap #3 names tokenised collateral. §3.1 L2 InstrumentMaster routes to `matthias.md §A.5` "tokenised-asset (chainId, contractAddress, tokenStandard, backingModel)". sbl.md §2.3 specifies further: `corporate_action_processing_layer ∈ {custodial, token, hybrid}`, `redemption_mechanism`, `mirror_or_native`. The fractional CA processing question (custodial layer vs token layer) is SBL-specific and not in matthias.md §A.5. Without it, P19 against tokenised collateral has no haircut composition rule (underlying + platform risk).

---

## §3. Cross-cutting structural observation

The proposal's strategy is to compress specialist material into a six-line block per leaf with pointers to specialist files. **For SBL, this strategy fails because SBL adds 26 SBL-tagged data items across 6 floor categories** (sbl.md §9), and the §3 per-leaf block has no slot for "this leaf has 14 SBL sub-leaves with named fields per regulatory-event-coordinate triplet". The fix is not deeper compression; it is an explicit SBL sub-leaf register, either as a §3 appendix or as numbered sub-leaves L9.1–L9.x / L11.1–L11.y.

This is a Top-5-Gap-#2-adjacent argument: even if CDM lands the three SBL PrimitiveInstructions, the **Ledger-internal data layer** still needs to enumerate the SBL sub-leaves explicitly, because they participate in P-invariants (P14, P18, P19), in regulatory submission deadlines (SFTR T+1, SLATE same-day-by-8pm-ET), and in cross-border dual-regime workflows (SFTR + SLATE simultaneously for a US-EU bilateral loan).

---

## §4. Summary of findings and grade

| # | Severity | Title |
|---|----------|-------|
| 1 | **BLOCKING** | L9 / L11 sub-leaf compression hides 14 SBL data items |
| 2 | **BLOCKING** | CDM Top-5 Gap #2 conceded but no runtime contract specified |
| 3 | UNMITIGATED MAJOR | Recall window deadline math unsurfaced; market cut-off catalogue missing from L4 |
| 4 | UNMITIGATED MAJOR | Manufactured payment described but not data-modelled |
| 5 | UNMITIGATED MAJOR | RQV / triparty agreement parameters not L1 / L11 |
| 6 | UNMITIGATED MAJOR | Cascade-recall topology mis-routed to L24 (V11) |
| 7 | UNMITIGATED MAJOR | Rehyp cap counter and over-location ledger missing from §3 |
| 8 | UNMITIGATED MAJOR | Agent-lender reallocation silent; SFTR UTI continuity unspecified |
| 9 | MINOR | CSDR FOP-exemption flag missing from L12 |
| 10 | MINOR | MMF reinvestment NAV missing from L10 / L13 |
| 11 | MINOR | ESMA / SEC restricted-list data not surfaced |
| 12 | MINOR | NSP threshold table absent |
| 13 | UNMITIGATED MAJOR | P18 buy-in carve-out unsurfaced in conservation lifting |
| 14 | MINOR | Borrow fee vs rebate rate fix duality not split |
| 15 | MINOR | Tokenised collateral SBL-specific fields not in L2 |

**Counts.** 2 blocking, 7 unmitigated major, 6 minor.

**Grade. C+ (with high upside on revision).** The structural decisions are correct (six-coordinate at L9, locate at L11, FOP exemption at L12, conservation lifting at §8, Top-5 Gap #2 named). The execution at §3 collapses 14 SBL sub-leaves into single-line bullets, with no field set, no per-leaf invariant, and no SFTR/SLATE cross-walk. A `proposal_v2.md` that lifts the sbl.md §§1–6 enumeration as numbered sub-leaves under L9 / L11 / L12 / L4 / L1 / L6, with a 5-line sub-leaf block (field set / CDM status / regulatory regime / lifecycle event / coordinate touched) per item, would resolve all 9 major-or-blocking findings. The 6 minor findings are deferable with documented reason.

**Convergence not reached.** Two blocking findings preclude convergence per the §10 criteria. Recommend Round 2.
