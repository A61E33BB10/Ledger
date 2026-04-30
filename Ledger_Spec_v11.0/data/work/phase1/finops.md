# Ledger v11.0 — Phase 1 Independent Data Enumeration

**Discipline:** Financial Systems Operations
**Author lens:** Head of Operations (double-entry, reconciliation, settlement, audit)
**Source corpus:** ledger v10.3 (main), v10.3 StatesHome addendum, valuation v1.0
**Date:** 2026-04-29

---

## 0. Reading of the Floor and Disagreements Up Front

The brief states a six-floor taxonomy: 1. Static, 2. Reference, 3. Market, 4. Oracle, 5. Smart-contract execution, 6. Listed-instrument detail.

From operations, the floor categories conflate two different things and miss several first-class data categories that the v10.3 + addendum + valuation stack actually requires. My disagreements (argued, not asserted):

- **F1. "Static" vs. "Reference" is a false split for ops.** In every reconciliation engine I have run, *static* data (firm-level configuration: own LEI, account hierarchy, calendar choices) and *reference* data (instrument terms from external authorities: ISIN tables, exchange contract specs) have **different sources, different SLAs, different controls, and different breaks**. They should remain split, but the names need to mean what ops mean by them: **Static = firm-controlled config**, **Reference = third-party-authoritative descriptive data**. v10.3's three-tier Unit Store (Tier-1 Reference Data, Tier-2 Product Registry, Tier-3 Unit Registry) only roughly maps here, so I keep both floors but redefine them.

- **F2. "Market" and "Oracle" overlap and the addendum's Kalman layer is missing from the floor.** In valuation v1.0, raw quotes flow into the **Kalman filter / certification layer**, then into a **calibrated parameter store**, then into the Pricing DAG. "Market data" in the floor sense conflates (a) raw observable quotes, (b) certified calibrated parameters, and (c) snapshot/oracle attestations used for deterministic replay. Operationally these three are reconciled differently: raw quotes against vendor feeds; calibrations against arb-free certificate residuals; oracle snapshots against their hash chain. **I split Floor 3 (Market Observables) from Floor 4 (Oracle / Calibrated Snapshots)** and keep both.

- **F3. "Smart-contract execution" is not a category of data — it is a *layer* that produces several categories.** A smart contract emits moves, registers obligations, mutates unit state, and writes to the audit trail. From the data side, the actual ops-relevant categories produced by execution are: (i) **Move stream / event log**, (ii) **Unit-state journal** (the three StatesHome maps), (iii) **Obligation register**, (iv) **Settlement instructions and confirmations**. I expand Floor 5 into these four sub-categories rather than treat "execution data" as a single bucket.

- **F4. "Listed-instrument detail" is too narrow.** OTC trade-and-CSA data (CDM `Trade` with `Collateral`), SBL loan units, mandate-as-unit (per addendum), and managed-account / virtual-ledger configuration are all first-class identity-bearing data the framework requires. The right floor name is **Trade-and-Contract Identity & Terms**, not "listed-instrument detail."

- **F5. Critical missing floors.** The floor as given omits, at least: **Counterparty & Legal Entity** data (LEI / BIC / SSI / KYC / sanctions), **Legal Agreement** data (ISDA Master, CSA, GMSLA, MRA, OSLA, account-control agreements), **Collateral Eligibility & Haircut Schedules**, **Custody & Account Topology** (depot accounts, omnibus vs. segregated, nostro/vostro), **Corporate Action announcements**, **Holiday / Business Calendar** data, **Regulatory-reporting reference** data (UTI/USI generation rules, ESMA action-type tables, jurisdiction maps), **Tax & Withholding** reference data (treaty rates, residence flags, manufactured-payment classifications), **Obligation register** data (per the v10.3 §14 Obligation Store), **Audit & Provenance** metadata (CDM payload, oracle snapshot id, hash chain), and the **PnL-explain / valuation lifecycle** record set (the 8-state FSM in valuation v1.0).

- **F6. State home is not the floor's concern but it is mine.** The addendum's ruling that state lives in three maps (`ProductTerms`, `UnitStatus`, `PositionState`) is a **data-storage discipline**, not a data category. But operationally it tells me where each item belongs and which mutation discipline applies (append-only versioned, mutable shared, mutable per-position). I tag every item below with its StatesHome home — that is the only way ops can reconcile it.

**Net: I enumerate using twelve floors, mapping each back to the brief's six.** Items where a relabel suffices are flagged. Items where no floor applies in the brief are flagged as additions.

---

## 1. Floor Re-statement (Twelve Floors)

| # | Floor (ops naming)                                   | Brief mapping                          | Why elevated                                                   |
|---|------------------------------------------------------|----------------------------------------|----------------------------------------------------------------|
| 1 | Static / Firm Config                                 | = Floor 1 Static                       | Firm-level identity, calendars, books, accounting policy        |
| 2 | Reference / Authoritative External Descriptors        | = Floor 2 Reference                    | ISIN/CFI/MIC/LEI tables, exchange specs                         |
| 3 | Counterparty, Legal Entity & Account Topology         | **Addition**                           | LEI, BIC, SSI, custody account hierarchy, KYC/sanctions         |
| 4 | Legal Agreement                                       | **Addition**                           | ISDA, CSA, GMSLA, MRA, OSLA, ACA — economically load-bearing    |
| 5 | Trade-and-Contract Identity & Terms                  | = Floor 6 Listed-instrument detail (broadened) | Listed contract spec + OTC `Trade(+Collateral)` + SBL + mandate |
| 6 | Market Observables (Raw)                             | ⊂ Floor 3 Market                       | Raw quotes, prints, settlement prices                           |
| 7 | Calibrated Parameters & Oracle Snapshots             | ⊂ Floor 4 Oracle (broadened)           | Kalman-certified curves/surfaces, snapshot ids, hash chain      |
| 8 | Move Stream / Event Log                              | ⊂ Floor 5 Smart-contract execution     | The canonical internal record itself                            |
| 9 | Unit-State Journal (StatesHome 3 maps)               | ⊂ Floor 5                              | `ProductTerms` / `UnitStatus` / `PositionState`                 |
|10 | Obligation Register                                  | ⊂ Floor 5 (additions per v10.3 §14)    | Obligation type, deadline, discharge, compensation              |
|11 | Settlement & Confirmation Records                    | ⊂ Floor 5                              | ISO 20022 instructions, statuses, CSD/CCP confirmations         |
|12 | Valuation, PnL-Explain & Risk Records                | **Addition** (valuation v1.0 lifecycle)| ValuationRecord, FSM state, Greeks/Jacobian, model reserve     |

Each item below carries the seven mandatory fields plus the three reconciliation/break/audit fields, and is anchored to one floor.

---

## 2. The Items

Format key for every item:

1. **Canonical name**
2. **Definition**
3. **Minimum field set** — the smallest set of fields that makes the item operationally usable
4. **Identity** — what makes two records "the same" item
5. **Provenance** — who is authoritative; how does it enter our system
6. **Temporal semantics** — point-in-time vs. period; effective date vs. booking date; immutability discipline
7. **Failure consequences** — what breaks downstream if this item is wrong, missing, or stale
8. **(a) Reconciliation pair** — what external record this is checked against
9. **(b) Common operational break** — in plain language
10. **(c) Audit / SOX / IFRS implication** — the regulatory hook

---

### FLOOR 1 — STATIC / FIRM CONFIG

#### 1.1 Firm Identity & Booking Hierarchy
1. **Canonical:** `firm_identity`
2. **Definition:** The firm's own legal entity tree: top-of-house, legal entities, branches, books, sub-books, internal cost centres. Includes the firm's own LEI, BIC, jurisdiction, regulated-entity flags, and the parent/child relationships that determine consolidation.
3. **Min fields:** `entity_id`, `legal_name`, `LEI`, `parent_entity_id`, `country_of_incorporation`, `regulator_codes`, `consolidation_flag`, `effective_from`, `effective_to`.
4. **Identity:** `(LEI, effective_from)` — LEIs are reissued only on legal-entity events; the (LEI, effective_from) pair is unique.
5. **Provenance:** Firm legal/governance team. Sourced from articles of incorporation, regulator filings, and the GLEIF LEI record. Loaded by the static-data team; changes require a change-control ticket.
6. **Temporal:** Slowly-changing dimension. Versioned with `effective_from` / `effective_to`. **Append-only**; closing an entity means setting `effective_to`, not deletion.
7. **Failure consequences:** Wrong LEI → wrong UTI → entire trade rejected by trade repository. Wrong parent → wrong regulatory consolidation → CRR / Basel capital miscalculated. Wrong branch attribution → wrong tax jurisdiction → withholding error.
8. **(a) Reconciliation pair:** GLEIF LEI register; regulator entity registers (FCA Firm Reference, ESMA, FINRA, SEC EDGAR); firm's own corporate-secretary records.
9. **(b) Common break:** A firm reorganisation (intra-group novation, branch closure) is announced internally on date X but the LEI's parent record is updated by GLEIF on date Y. Between X and Y, regulatory reports are filed against the wrong consolidated parent.
10. **(c) Audit / SOX / IFRS:** SOX ITGC scope (entity-level controls); IFRS 10 (consolidation); BCBS 239 §6 (data accuracy). Misstated entity tree is a material weakness.
11. **StatesHome home:** `WalletRegistry` metadata (per addendum: this is non-state, non-financial sidecar).

#### 1.2 Reference Currency & Multi-Currency Policy
1. **Canonical:** `reference_currency_policy`
2. **Definition:** The reference currency for portfolio value (`P_t(USD)=1` per ledger v10.3 §4) and the FX-policy choice for translating positions and PnL across currencies.
3. **Min fields:** `firm_reference_ccy`, `book_reference_ccy_overrides[]`, `fx_translation_method` (spot at close / weighted avg / closing rate), `fx_source_id`, `effective_from`.
4. **Identity:** `(book_id, effective_from)`.
5. **Provenance:** Treasury / Finance policy. Approved by the CFO function.
6. **Temporal:** Immutable per period. A change is a future-effective new version.
7. **Failure consequences:** Wrong reference currency in PnL → reported PnL contains FX revaluation that should sit elsewhere → CTA (cumulative translation adjustment) noise; auditor questions classification.
8. **(a) Reconciliation pair:** Firm's published accounting policy memo; quarterly board pack.
9. **(b) Common break:** A new managed-account onboarding silently inherits the firm default reference currency when the client's mandate specifies EUR — client statement and internal report disagree by FX.
10. **(c) Audit / SOX / IFRS:** IAS 21 (effects of foreign exchange rates); IFRS 9 §B5.7 (FVTPL classification of FX gains).
11. **StatesHome home:** Configuration; not in StatesHome maps.

#### 1.3 Holiday & Business Day Calendar
1. **Canonical:** `business_calendar`
2. **Definition:** The ordered set of business days per market / currency / settlement venue. Used for accrual periods, settlement-date adjustment, fixing dates, margin call deadlines.
3. **Min fields:** `calendar_id` (e.g. `USNY`, `EUTA`, `LON`), `year`, `holiday_dates[]`, `early_close_dates[]`, `convention` (preceding / following / mod-following), `source_publication_url`, `version`.
4. **Identity:** `(calendar_id, year, version)`.
5. **Provenance:** Vendor (FpML calendar service, ICE, exchange holiday tables). Versioned because vendors do publish corrections.
6. **Temporal:** Annual publication; corrections are new versions, **never in-place edit**. Replay must select calendar by version-as-of-knowledge-time.
7. **Failure consequences:** Wrong calendar → wrong reset/coupon date → cash flow misses settlement window → CSDR penalty; obligation deadline (per v10.3 §14) computed wrong → false default or false discharge.
8. **(a) Reconciliation pair:** Exchange holiday publications, ECB / Fed calendars, ISDA holiday-supplement files. Inter-vendor reconciliation (Bloomberg vs. Refinitiv vs. ICE).
9. **(b) Common break:** A jurisdiction adds a one-off public holiday (royal funeral, sovereign event). Two of three vendors publish; the third does not. Any swap whose calendar source is the lagging vendor pays a coupon on a non-business day.
10. **(c) Audit / SOX / IFRS:** Materially affects accrual cut-offs (IAS 1 / IAS 8 prior-period restatements if wrong); MiFID II RTS 25 (timestamps); EMIR Refit (reset date fields).
11. **StatesHome home:** Calendar tables sit outside the three maps; treated as `ProductTerms` input where they bind to a unit's schedule (e.g. swap reset dates baked into `ProductTerms[u_swap]`).

#### 1.4 Accounting Policy & Classification Map
1. **Canonical:** `accounting_classification`
2. **Definition:** Per book / per instrument-class mapping to IFRS 9 (FVTPL / FVOCI / amortised cost), US GAAP equivalents, hedge designations. Controls whether MTM flows into P&L, OCI, or is suppressed.
3. **Min fields:** `book_id`, `instrument_class`, `classification`, `hedge_designation`, `effective_from`, `approved_by`, `approval_ticket`.
4. **Identity:** `(book_id, instrument_class, effective_from)`.
5. **Provenance:** Finance / Accounting Policy committee; written approval required.
6. **Temporal:** Versioned; changes are formal accounting policy changes (rare; require disclosure).
7. **Failure consequences:** Misclassification means MTM flows into the wrong line — an FVOCI bond wrongly tagged FVTPL inflates reported P&L volatility; a hedge wrongly de-designated triggers ineffectiveness recognition.
8. **(a) Reconciliation pair:** Annual accounting policy disclosure note in financial statements; auditor's classification letter.
9. **(b) Common break:** New product launches with no accounting class assigned; system defaults it to FVTPL; quarter-end discovery requires reclassification with retrospective entries.
10. **(c) Audit / SOX / IFRS:** Direct IFRS 9 / ASC 320/321/815 obligation. Material weakness if unsupported.
11. **StatesHome home:** Out-of-scope of the three maps (purely an accounting overlay).

#### 1.5 Materiality & Tolerance Policy
1. **Canonical:** `tolerance_policy`
2. **Definition:** Per-instrument-class tolerance for PnL-explain residual (valuation v1.0 §7.3), reconciliation break threshold, late-event treatment threshold, conservation-violation alert level.
3. **Min fields:** `policy_id`, `instrument_class`, `pnl_explain_tolerance`, `position_recon_tolerance`, `cash_recon_tolerance`, `effective_from`.
4. **Identity:** `(policy_id, effective_from)`.
5. **Provenance:** Risk + Finance + Operations joint approval.
6. **Temporal:** Periodic review (typically annual); versioned.
7. **Failure consequences:** Tolerance set too tight → constant alerts, alert fatigue → real breaks missed. Tolerance too loose → real breaks accepted as noise → misstated balance sheet.
8. **(a) Reconciliation pair:** Documented in the Risk & Control Self-Assessment (RCSA); operational risk register.
9. **(b) Common break:** A merged business inherits two tolerance regimes; same instrument has two thresholds depending on which legacy system originated the trade — auditor flags inconsistent control.
10. **(c) Audit / SOX / IFRS:** SOX ICFR design effectiveness (control thresholds); BCBS 239 §6.
11. **StatesHome home:** Configuration table.

---

### FLOOR 2 — REFERENCE / AUTHORITATIVE EXTERNAL DESCRIPTORS

#### 2.1 ISIN / CUSIP / SEDOL / FIGI Master
1. **Canonical:** `security_master`
2. **Definition:** External authoritative record per security: identifier, issuer, asset class, listing venue(s), currency of denomination, lot size, ISIN-CFI classification.
3. **Min fields:** `ISIN` (primary), `CUSIP`, `SEDOL`, `FIGI`, `issuer_LEI`, `asset_class`, `cfi_code`, `currency`, `lot_size`, `pricing_currency`, `inception_date`, `delisting_date`.
4. **Identity:** `ISIN` (primary key per ISO 6166).
5. **Provenance:** ANNA / national numbering agencies. Loaded via vendor (Bloomberg BBM, Refinitiv DSS, SIX Financial). Multi-vendor recommended.
6. **Temporal:** Slowly-changing; corporate actions can rewrite. Must be **versioned** to support time travel (per ledger v10.3 §1.2 Property 6 — "knew at time t" vs. "today's corrected data").
7. **Failure consequences:** Wrong ISIN → wrong unit_id → wrong custodian instruction → fail at CSD. Wrong issuer LEI → wrong concentration aggregation → wrong large-exposure regulatory return.
8. **(a) Reconciliation pair:** Inter-vendor ISIN reconciliation; custodian's security master file; CSD's official record (DTCC for US, Euroclear/Clearstream for EU).
9. **(b) Common break:** ISIN reissued after corporate restructuring; vendor A maps old ISIN to new same-day, vendor B takes 24h. Trades booked in the gap settle to the wrong account.
10. **(c) Audit / SOX / IFRS:** Underpins balance-sheet substantiation; CSDR accurate-record obligations; SFTR/EMIR field validation.
11. **StatesHome home:** Loads into `ProductTerms[u]` at unit registration.

#### 2.2 Exchange Contract Specifications (Listed Derivatives)
1. **Canonical:** `exchange_contract_spec`
2. **Definition:** Per listed derivative: underlier, contract month, strike (for options), tick size, multiplier, settlement style (cash/physical), settlement currency, last-trading-date, first-notice-day, delivery convention, exchange MIC.
3. **Min fields:** `exchange_mic`, `product_code`, `expiry`, `strike`, `option_type`, `multiplier`, `tick_size`, `settlement_style`, `delivery_convention`, `last_trade_date`, `first_notice_date`.
4. **Identity:** `(exchange_mic, product_code, expiry, strike, option_type)` — fungibility set per ledger v10.3 §3.2.
5. **Provenance:** Exchange directly (CME ClearMRT, ICE, Eurex) or via vendor.
6. **Temporal:** Effective per listing event; immutable thereafter. Re-listing a contract under a new product code is a new identity.
7. **Failure consequences:** Wrong multiplier → variation margin error scaled by multiplier (a $50 multiplier read as $5 understates VM by 10×). Wrong settlement style → ledger thinks cash, exchange delivers physical → broken settlement.
8. **(a) Reconciliation pair:** Exchange's contract specification PDF / API; CCP product catalogue; FIA contract specifications.
9. **(b) Common break:** A new contract month is listed but the firm's static-data team has not loaded it. Trades route via OMS but cannot be priced or VM-settled in the ledger; positions accumulate without margin.
10. **(c) Audit / SOX / IFRS:** EMIR Article 11 (variation margin auditability); MiFID II RTS 25 (trade reconstruction).
11. **StatesHome home:** `ProductTerms[u_listed]`.

#### 2.3 MIC / Trading-Venue Codes
1. **Canonical:** `venue_master`
2. **Definition:** ISO 10383 Market Identifier Codes mapping venue identifier to operating MIC, segment MIC, country, regulator, MTF/OTF/RM classification.
3. **Min fields:** `MIC`, `operating_MIC`, `country`, `acronym`, `legal_name`, `regulator`, `category`.
4. **Identity:** `MIC`.
5. **Provenance:** ISO 10383 register (SWIFT-maintained).
6. **Temporal:** Slowly-changing; corrections versioned.
7. **Failure consequences:** Wrong MIC on regulatory submission → MiFIR transaction report rejected; SFTR field 11 (venue) populated wrongly.
8. **(a) Reconciliation pair:** ISO 10383 register; ESMA registers; venue's own published MIC.
9. **(b) Common break:** A venue closes a segment; old MIC is retired; replays of historical activity must use the historical version, not the current one.
10. **(c) Audit / SOX / IFRS:** MiFIR RTS 22 §65 fields; EMIR Refit field 9.
11. **StatesHome home:** Reference table.

#### 2.4 CFI / ISIN-Classification & Asset-Class Taxonomy
1. **Canonical:** `cfi_taxonomy`
2. **Definition:** ISO 10962 CFI codes mapping a 6-character classification to instrument family (equity / debt / option / future / etc.) and feature attributes.
3. **Min fields:** `cfi_code`, `category` (1st char), `group` (2nd), `attribute_1..4`.
4. **Identity:** `cfi_code`.
5. **Provenance:** ISO 10962; published per security in the ANNA record.
6. **Temporal:** Effective per issuance; updated on terms change.
7. **Failure consequences:** Drives smart-contract template binding (Tier-2 Product Registry per v10.3 §2). Wrong CFI → wrong contract template → wrong lifecycle behaviour.
8. **(a) Reconciliation pair:** ANNA / vendor CFI records; CDM `ProductQualification` output.
9. **(b) Common break:** A convertible bond loaded as plain bond CFI → embedded option not modelled → coupon payments correct but conversion event silently ignored.
10. **(c) Audit / SOX / IFRS:** Underlies IFRS 9 classification; SFTR/EMIR product type field.
11. **StatesHome home:** `ProductTerms[u]`.

#### 2.5 GLEIF LEI Record
1. **Canonical:** `lei_record`
2. **Definition:** Per legal entity: LEI, legal name, registered address, registered authority, parent LEI, status (issued / lapsed), next renewal date.
3. **Min fields:** `LEI`, `legal_name`, `registered_country`, `parent_LEI`, `status`, `last_update_date`, `next_renewal_date`.
4. **Identity:** `LEI`.
5. **Provenance:** GLEIF (Global LEI Foundation) via Local Operating Units (LOUs). Daily concatenated file (CDF) downloads.
6. **Temporal:** Daily snapshots; **must be archived** for time-travel and regulatory reconstruction.
7. **Failure consequences:** A lapsed LEI on a counterparty causes EMIR / MiFIR / SFTR reports to be rejected. Wrong parent LEI → wrong consolidated reporting.
8. **(a) Reconciliation pair:** GLEIF CDF; counterparty self-attested LEI on confirmations.
9. **(b) Common break:** Counterparty LEI lapses on Friday; trade booked Monday; report rejected; remediation requires the counterparty to re-register and us to re-submit. Settlement may proceed but reporting is non-compliant.
10. **(c) Audit / SOX / IFRS:** EMIR Refit field 1.4.4; SFTR field 1.3; MiFIR RTS 22 field 7. Direct enforcement risk.
11. **StatesHome home:** Counterparty reference; bound to virtual wallets (per v10.3 §2.5).

#### 2.6 Day-Count Conventions, Business-Day Adjustments, Schedule Generators
1. **Canonical:** `daycount_convention`
2. **Definition:** Per CDM `DayCountFractionEnum` value: the rule for converting calendar dates to year fractions (ACT/360, ACT/365, 30E/360, etc.), the business-day adjustment convention, and the schedule generator (per CDM `CalculationPeriodFrequency`).
3. **Min fields:** `daycount_code`, `formula_reference`, `adjustment_convention`, `roll_convention`, `effective_from`.
4. **Identity:** `daycount_code` (CDM-enum-bound).
5. **Provenance:** ISDA; CDM enums.
6. **Temporal:** Stable; new values added rarely.
7. **Failure consequences:** Wrong day-count → wrong accrual → wrong coupon → wrong cash settlement → counterparty dispute.
8. **(a) Reconciliation pair:** ISDA confirmation (the legal source of truth); counterparty's confirmation; CDM enum tests.
9. **(b) Common break:** Confirmation says ACT/365 fixed but trade is booked as ACT/360; first coupon differs by ~1.4%; counterparty rejects payment.
10. **(c) Audit / SOX / IFRS:** ISDA confirmation legal evidence; IFRS 9 effective interest method.
11. **StatesHome home:** `ProductTerms[u]`.

---

### FLOOR 3 — COUNTERPARTY, LEGAL ENTITY & ACCOUNT TOPOLOGY (ADDITION)

#### 3.1 Counterparty Master
1. **Canonical:** `counterparty_master`
2. **Definition:** Per active counterparty: identifiers, classification (financial / non-financial counterparty under EMIR; clearing-member / direct / indirect under MiFIR), default agreements, default settlement instructions, sanctions/PEP status, KYC validity dates, credit rating, internal credit-risk band.
3. **Min fields:** `counterparty_id`, `LEI`, `BIC`, `legal_name`, `EMIR_class` (FC/NFC/NFC+), `MIFIR_class`, `kyc_status`, `kyc_review_date`, `sanctions_check_date`, `default_csa_id`, `default_isda_id`, `internal_credit_band`, `nostro_account`, `vostro_account`.
4. **Identity:** `counterparty_id` (internal); `LEI` (external).
5. **Provenance:** Onboarding / Client Lifecycle Management workflow; sanctions screening (OFAC / EU / UN); credit team for ratings.
6. **Temporal:** Slowly-changing dimension with **mandatory periodic refresh** (KYC every 12-36 months by risk band; sanctions daily). Versioned; closure dated.
7. **Failure consequences:** Stale KYC → AML breach. Sanctions hit not flagged → criminal liability. Wrong EMIR class → wrong clearing obligation determination → uncleared OTC where clearing is mandatory → enforcement.
8. **(a) Reconciliation pair:** GLEIF; sanctions list providers (Refinitiv World-Check, Dow Jones); credit-rating-agency feeds; counterparty's own self-disclosure on the KYC questionnaire.
9. **(b) Common break:** Counterparty restructures and changes EMIR class from NFC- to NFC+; firm does not refresh; clearing obligation is missed; ESMA enforcement.
10. **(c) Audit / SOX / IFRS:** AML/KYC regulations (BSA in US, AMLD6 in EU); EMIR Article 9; MiFIR RTS 22; sanctions law.
11. **StatesHome home:** Counterparty record bound to virtual wallets (`WalletRegistry` for the virtual wallet); EMIR classification tag could live in `ProductTerms[u]` for trades booked, copied at trade time.

#### 3.2 Standing Settlement Instructions (SSI)
1. **Canonical:** `ssi_record`
2. **Definition:** Per (counterparty, currency / security) pair: the account at the custodian / nostro bank / CSD where settlement should be directed. Includes BIC, IBAN / account number, agent BIC, intermediary chain, priority, effective dates.
3. **Min fields:** `ssi_id`, `counterparty_id`, `currency_or_isin`, `account_BIC`, `account_number`, `agent_BIC`, `intermediary_chain`, `priority`, `effective_from`, `effective_to`, `last_confirmed_date`, `confirmation_method` (SWIFT MT599 / Alert / SSI utility).
4. **Identity:** `(counterparty_id, currency_or_isin, effective_from)`.
5. **Provenance:** SSI utilities (DTCC ALERT, Omgeo CTM, SWIFT KYC Registry); counterparty's signed SSI letter.
6. **Temporal:** Versioned; superseded SSIs retained for historical settlement reconstruction.
7. **Failure consequences:** Settlement misrouted → "fail to deliver" → CSDR penalty; in worst case, settlement to a fraudster's account (BEC fraud — historically the most expensive single break in operations).
8. **(a) Reconciliation pair:** ALERT GoldenSource; counterparty's signed SSI letter; SWIFT confirmation message (MT599 / 296).
9. **(b) Common break:** Counterparty changes correspondent bank but the change notice arrives only via email to the front-office trader; ops is not informed; next settlement misrouted.
10. **(c) Audit / SOX / IFRS:** SSI control is a SOX key control; AML records-keeping; CSDR settlement-fail reporting.
11. **StatesHome home:** Settlement-layer concern; not in three maps. Bound to wallet metadata at execution time per v10.3 §10.

#### 3.3 Custody & Depot Account Topology
1. **Canonical:** `custody_topology`
2. **Definition:** The hierarchy of custodian / sub-custodian / CSD accounts: omnibus vs. segregated, beneficial-owner mapping, jurisdiction, account-control agreement reference, allowable instrument types per account.
3. **Min fields:** `account_id`, `account_type` (omnibus / individually-segregated / pooled / firm-house), `custodian_BIC`, `csd_id`, `parent_account_id`, `controlling_jurisdiction`, `aca_id`, `permitted_assets[]`, `client_asset_flag` (CASS-protected / firm-asset).
4. **Identity:** `account_id` (internal).
5. **Provenance:** Custody operations; custodian onboarding documentation; account-control agreements with prime brokers.
6. **Temporal:** Effective-dated; account closure is dated, never deleted.
7. **Failure consequences:** Confusing client-asset (CASS-segregated) with house assets — instant CASS/Client Money Rules breach. Wrong omnibus → client positions reported in pool, breaching segregation.
8. **(a) Reconciliation pair:** Custodian's depot statement; ACA documentation; CSD account register.
9. **(b) Common break:** A new client onboarded in a hurry is parked in an omnibus account "temporarily" for the first day; CASS reconciliation that night flags the breach.
10. **(c) Audit / SOX / IFRS:** UK FCA CASS 6 (segregation); SEC Rule 15c3-3 (US customer protection); EU MiFID II Article 16(8); CRR collateral treatment (eligibility depends on segregation).
11. **StatesHome home:** Wallet metadata in `WalletRegistry`; not state.

#### 3.4 Tax Status, Withholding, & Manufactured-Payment Classification
1. **Canonical:** `tax_status`
2. **Definition:** Per (counterparty, account, jurisdiction-of-income): tax residence, treaty rate, exemption certificate (W-8BEN-E, FATCA self-cert, CRS self-cert), withholding rate per income type, manufactured-payment treatment under SBL.
3. **Min fields:** `counterparty_id`, `tax_residence`, `treaty_rate_table`, `fatca_status`, `crs_status`, `w8_w9_expiry`, `manufactured_payment_classification` (gross / net / specific-percentage).
4. **Identity:** `(counterparty_id, jurisdiction_of_income, effective_from)`.
5. **Provenance:** Tax operations; counterparty self-certification forms; tax treaties.
6. **Temporal:** Versioned; W-8BEN-E expires every 3 years; treaty changes are jurisdictional events.
7. **Failure consequences:** Over-withholding → counterparty short-paid, dispute. Under-withholding → firm liable for the tax. Wrong manufactured-payment classification → SBL economics break (per v10.3 SBL §13).
8. **(a) Reconciliation pair:** IRS / HMRC tax forms; treaty schedules; counterparty's signed W-form.
9. **(b) Common break:** A W-8BEN-E expires unnoticed; the next dividend is withheld at 30% instead of treaty 15%; client is short-paid and bills the firm to make whole.
10. **(c) Audit / SOX / IFRS:** FATCA / CRS reporting obligations; QI agreements with the IRS; tax-authority enforcement.
11. **StatesHome home:** Counterparty metadata; manufactured-payment rule may be encoded in `ProductTerms[u_loan]` for SBL.

---

### FLOOR 4 — LEGAL AGREEMENT (ADDITION)

#### 4.1 ISDA Master Agreement Record
1. **Canonical:** `isda_master`
2. **Definition:** The bilateral master agreement governing all OTC derivatives between two parties: counterparty pair, governing law, election schedule (tax representations, payee rep, multi-branch parties), close-out method (Loss / Market Quotation / Close-out Amount), automatic-early-termination flag.
3. **Min fields:** `agreement_id`, `version` (1992 / 2002), `parties_LEI`, `governing_law`, `effective_date`, `termination_date`, `close_out_method`, `aet_flag`, `cross_default_threshold`, `mna_reference`.
4. **Identity:** `agreement_id` (internal); cross-keyed by `(party_LEI_1, party_LEI_2, governing_law, effective_date)`.
5. **Provenance:** Legal / Documentation team; signed PDF stored in document management.
6. **Temporal:** Effective-dated; amendments are appendices; termination is dated.
7. **Failure consequences:** Without ISDA reference, OTC trade has ambiguous close-out method → counterparty default leaves us without a valid termination calculation → litigation. Wrong CDS / FX inclusion under "Specified Transactions" → cross-default fails to trigger.
8. **(a) Reconciliation pair:** Signed master PDF; ISDA Amend (electronic protocol adherence registry); counterparty's master copy.
9. **(b) Common break:** A trade booked under the wrong ISDA master (parties have several across branches); on default, the wrong governing law applies; close-out delayed by months while counsel sorts it out.
10. **(c) Audit / SOX / IFRS:** Legal-risk control under SOX entity-level; close-out netting opinion supports CRR Article 295 capital benefit; failure invalidates netting and increases capital.
11. **StatesHome home:** `ProductTerms[u_OTC]` references the ISDA via `legal_agreement_id`; the master itself sits in document management.

#### 4.2 Credit Support Annex (CSA) / Credit Support Deed
1. **Canonical:** `csa_record`
2. **Definition:** The collateral terms governing a portfolio of trades under an ISDA: threshold, minimum transfer amount, independent amount, eligible collateral schedule, haircuts, valuation agent, dispute resolution, notification times, regulatory IM versus VM, governing law.
3. **Min fields:** `csa_id`, `parent_isda_id`, `csa_type` (NY-Law / English-Law / Japanese / Title-transfer / Pledge), `threshold_per_party`, `minimum_transfer_amount`, `independent_amount`, `eligible_collateral_schedule_id`, `valuation_agent`, `notification_time_local`, `dispute_resolution_clause`, `regime` (UMR-IM / VM-only).
4. **Identity:** `csa_id` (internal); cross-key `(parent_isda_id, version)`.
5. **Provenance:** Legal; signed.
6. **Temporal:** Versioned; threshold/MTA changes are amendments.
7. **Failure consequences:** Threshold or MTA misread → undercollateralised exposure → margin call missed → regulatory IM breach (UMR Phase 6 — €/$8 bn AANA threshold) or counterparty default with insufficient collateral. Eligible-collateral mismatch → posted collateral rejected → CSA-VM obligation per v10.3 §14.7 fires compensation (close-out netting).
8. **(a) Reconciliation pair:** Signed CSA; counterparty's CSA copy; valuation-agent statement; AcadiaSoft / triResolve margin-call reconciliation messages.
9. **(b) Common break:** Counterparty asks to substitute Treasuries for corporates; the CSA permits Treasuries only of certain ratings/maturities; ops accepts ineligible bonds; lender's collateral floor is below the agreed haircut.
10. **(c) Audit / SOX / IFRS:** UMR (BCBS-IOSCO Margin Requirements for Non-Centrally-Cleared Derivatives); EMIR Article 11; Dodd-Frank §731; CRR Article 285 collateral haircuts.
11. **StatesHome home:** `ProductTerms[u_csa]` (CSA-as-unit per the ledger framing where CSA margin contract attaches to the collateral wallet).

#### 4.3 GMSLA / MRA / OSLA / SLMA — Securities-Financing Master Agreements
1. **Canonical:** `sft_master`
2. **Definition:** Master agreements for securities lending and repo: GMSLA 2000/2010/2018 (title transfer / pledge), Master Repurchase Agreement (US), Global Master Repurchase Agreement (international), OSLA (UK), SLMA, MSLA.
3. **Min fields:** `agreement_id`, `agreement_type`, `parties_LEI`, `effective_date`, `governing_law`, `default_collateral_method`, `rehypothecation_consent`, `manufactured_payment_treatment`, `event_of_default_clauses`, `buy_in_clause`.
4. **Identity:** `agreement_id`.
5. **Provenance:** Legal.
6. **Temporal:** Versioned; rehyp consent often per-trade overrideable.
7. **Failure consequences:** Wrong agreement type → wrong rehyp permission → ledger's `coll_rehyp` coordinate (per v10.3 GPM §13) used illegally → SFTR Article 15 breach. Wrong manufactured-dividend clause → over- or under-payment to lender on dividend dates.
8. **(a) Reconciliation pair:** ISLA signed master register; counterparty's copy.
9. **(b) Common break:** A US client lends under GMSLA 2018 (pledge) but the trader treats collateral as title-transfer (rehypothecates); first audit flags illegal rehyp.
10. **(c) Audit / SOX / IFRS:** SFTR (Article 4 reporting; Article 15 rehyp); SEC Rule 15c3-3; FINRA SLATE; UK PRA SS17/13.
11. **StatesHome home:** `ProductTerms[u_loan]` references via `legal_regime`.

#### 4.4 Investment Mandate / IMA / Sub-Fund Documentation
1. **Canonical:** `mandate_terms`
2. **Definition:** Investment management agreement / sub-fund prospectus terms: permitted instrument universe, concentration limits, leverage caps, currency restrictions, benchmark, fee schedule (management + performance), high-water mark methodology, crystallisation frequency, side-pocket and gating provisions.
3. **Min fields:** `mandate_id`, `client_id`, `effective_from`, `permitted_universe[]`, `max_position_pct`, `max_leverage`, `currency_restriction[]`, `benchmark_id`, `mgmt_fee_bps`, `perf_fee_pct`, `hurdle`, `hwm_method`, `crystallisation_frequency`, `gating_terms`, `lock_up_period`.
4. **Identity:** `mandate_id`.
5. **Provenance:** Sales / Legal; signed mandate document.
6. **Temporal:** Versioned (per StatesHome §4.2 ruling — mandate terms append `TermsVersion` for fungibility-preserving amendments; allocate fresh `u_MA_new` for breaking amendments per C8).
7. **Failure consequences:** Mandate breach (e.g. exceeded concentration) → client redemption + complaint; misapplied performance fee → restated NAV → SEC enforcement.
8. **(a) Reconciliation pair:** Signed IMA; client's authorised mandate document; fund prospectus.
9. **(b) Common break:** A new sub-class is launched but the HWM methodology in the prospectus differs from the firm default; client statement and internal fee accrual disagree.
10. **(c) Audit / SOX / IFRS:** Fiduciary obligations; Investment Advisers Act (US); UCITS / AIFMD (EU); fund auditor opinion.
11. **StatesHome home:** Per addendum: mandate is a unit `u_MA`. `ProductTerms[u_MA]` carries mandate text, fee schedule, HWM method. `PositionState[w_client, u_MA]` carries the per-client HWM value, accrued fees.

---

### FLOOR 5 — TRADE-AND-CONTRACT IDENTITY & TERMS (broadens Floor 6 of brief)

#### 5.1 Listed-Instrument Unit (Tier-3 Unit Registry, listed)
1. **Canonical:** `listed_unit`
2. **Definition:** A specific listed contract or security registered as an element of `U`: identity, terms, smart-contract template binding (Tier-2 reference). One row per ISIN or per (exchange, product, expiry, strike, type) tuple.
3. **Min fields:** Per v10.3 §2: `unit_id`, `unit_type`, `isin?`, `contract_spec?`, `product_ref` (Tier-2), `smart_contract`, `currency`, `multiplier`, `expiry`, `lifecycle_stage`, `created_by` (tx_id), `created_at`.
4. **Identity:** `unit_id` deterministically derived from CDM TransferableProduct or NonTransferableProduct (per v10.3 §2.2).
5. **Provenance:** Reference data feed at listing; or first trade if framework permits trade-driven registration.
6. **Temporal:** Immutable identity & static terms (per v10.3 §2.6 guarantee 2 and addendum C7/C10). `lifecycle_stage` mutable (lives in `UnitStatus` per addendum).
7. **Failure consequences:** Without a registered unit, no move can reference it (v10.3 §2.5 transaction-time validation). Trades booked against unregistered units would either fail or — worse — bypass conservation if a workaround exists.
8. **(a) Reconciliation pair:** Exchange listing schedule; CSD security master; vendor reference data.
9. **(b) Common break:** New futures contract month listed by exchange but not loaded in time; opening trades cannot register.
10. **(c) Audit / SOX / IFRS:** Underpins position reporting; MiFIR Article 26 fields.
11. **StatesHome home:** Identity in `ProductTerms[u]`; mutable lifecycle in `UnitStatus[u]`; per-wallet position state in `PositionState[w, u]`.

#### 5.2 OTC Trade Unit (CDM Trade with Collateral)
1. **Canonical:** `otc_trade_unit`
2. **Definition:** A bilateral OTC trade registered as a unit: full CDM `Trade` structure, including counterparty identifiers, executed economic terms, `Collateral` field referencing the governing CSA, UTI, USI.
3. **Min fields:** `unit_id` (= CDM Trade meta key), `cdm_trade_payload`, `counterparty_LEI`, `csa_id`, `isda_id`, `trade_date`, `execution_timestamp_utc`, `UTI`, `USI`, `effective_date`, `termination_date`, `economic_terms_hash`.
4. **Identity:** `unit_id` derived from CDM Trade metadata key per v10.3 §2.4 (includes counterparty + Collateral; two trades with identical payoffs but different CSAs are distinct units).
5. **Provenance:** Execution venue / electronic confirmation; FpML or CDM-native confirmation.
6. **Temporal:** Trade-date immutable; lifecycle changes (terms changes via novation/amendment) tracked per v10.3 §10.4 and addendum C8 (preserving → append TermsVersion; breaking → new unit + SupersededBy).
7. **Failure consequences:** Without unique identity, two distinct economic agreements collide → conservation violated or reporting double-counts. Wrong UTI → EMIR/SFTR pairing failure → both parties' reports unmatched.
8. **(a) Reconciliation pair:** Counterparty confirmation (FpML); SEF/MTF execution report; trade repository pairing report (DTCC GTR pairing-percent metric); ALERT for OTC rates.
9. **(b) Common break:** UTI generated by the wrong counterparty (per ESMA waterfall) → reports unpaired at trade repository → mandatory remediation within 7 days.
10. **(c) Audit / SOX / IFRS:** EMIR Refit (203 fields); MiFIR RTS 22; Dodd-Frank Part 43/45.
11. **StatesHome home:** `ProductTerms[u_OTC]` (versioned); `UnitStatus[u_OTC]` for stage; `PositionState[w, u_OTC]` for per-counterparty (wallet) state.

#### 5.3 SBL Loan Unit
1. **Canonical:** `sbl_loan_unit`
2. **Definition:** Per v10.3 §13.7: the loan itself is a priced unit. Lender holds +1, borrower holds -1; conservation by issuance.
3. **Min fields:** Per v10.3 listing: `loan_id`, `lender`, `borrower`, `agent`, `isin`, `quantity`, `original_qty`, `term_type`, `maturity_date`, `fee_rate`, `rebate_rate`, `collateral_type`, `margin_pct`, `haircut_pct`, `collateral_ccy`, `triparty_agent`, `legal_regime`, `rehyp_consent`, `lifecycle_stage`, `recall_date`, `recall_qty`, `sftr_uti`, `slate_loan_id`, `execution_ts`, `trade_date`, `last_mark_date`, `accrued_fee`, `fee_accrual_log`.
4. **Identity:** `loan_id` (one per loan, per `legal_regime`).
5. **Provenance:** SBL trading platform (EquiLend, Pirum, agent lender); FIX-Securities-Lending or proprietary message.
6. **Temporal:** `ProductTerms[u_loan]` static at inception; `UnitStatus` mutable for lifecycle stage; `PositionState[w_lender, u_loan]` and `[w_borrower, u_loan]` per holder. State machine per v10.3 §13.8.
7. **Failure consequences:** Without loan-as-unit, ledger has no scalar "fee accrual" home → bond-analogy pricing breaks → fee PnL untracked → reportable to SFTR but not internally booked.
8. **(a) Reconciliation pair:** Daily contract compare (IBP-153/155) with counterparty; agent lender pool reports; triparty (BNYM, JPM, Euroclear) RQV reports.
9. **(b) Common break:** Daily contract-compare break: borrower has loan ID L123 with quantity 10,000; lender shows 9,800 (a partial return processed by one side only). Three-day SLA to clear.
10. **(c) Audit / SOX / IFRS:** SFTR (155 fields, Article 4); FINRA SLATE; SEC Rule 15c3-3; IFRS 9 §3.2.6 (lender does not derecognise); Basel CRR Article 222 (collateral treatment).
11. **StatesHome home:** Three maps as above.

#### 5.4 Mandate / Strategy Unit (`u_MA`, `u_QIS`)
1. **Canonical:** `mandate_unit`
2. **Definition:** Per addendum §4.2 and §4.3: the mandate / strategy is a first-class unit. Issued by manager (-1), held by client (+1).
3. **Min fields:** `unit_id` (= mandate_id or strategy_id), `issuer` (manager wallet), `unit_type` (`MANAGED_ACCOUNT` / `QIS_STRATEGY`), reference to `mandate_terms`, current `lifecycle_stage` (LISTED / ACTIVE / WIND_DOWN / CLOSED), per-instance state (HWM, accrued fees) in `PositionState[w_client, u_MA]`.
4. **Identity:** `unit_id`.
5. **Provenance:** Manager onboarding; signed IMA.
6. **Temporal:** Per StatesHome ruling — `ProductTerms` versioned for term changes; `UnitStatus` mutable for lifecycle / NAV index / weights; `PositionState` per-client.
7. **Failure consequences:** Without mandate-as-unit, per-wallet HWM has no home (the v10.3 line-1034 ambiguity addressed by the addendum). HWM/fee crystallisation drifts; client and manager disagree on accrued fees.
8. **(a) Reconciliation pair:** Client statement vs. internal accrual; fund administrator NAV; auditor's HWM recalc.
9. **(b) Common break:** Client holds two strategies under the same wallet; if HWM keyed only on wallet, the two HWMs collapse. Addendum's `PositionState[w_client, u_QIS_a]` vs. `[w_client, u_QIS_b]` keying prevents this — but legacy systems still hit it.
10. **(c) Audit / SOX / IFRS:** Investment Advisers Act; AIFMD reporting; fund accounting standards; performance-fee disclosure rules (SEC marketing rule).
11. **StatesHome home:** Three maps; this is the test case 2 of the addendum.

#### 5.5 Corporate-Action Definition
1. **Canonical:** `corporate_action`
2. **Definition:** Per CA event: ISIN(s) affected, action type (split, dividend, merger, spin-off, rights, tender, restructure), key dates (announcement, ex-date, record date, payment date, effective date), ratio / cash terms, election options, default option, child ISIN(s) where applicable.
3. **Min fields:** `ca_id`, `affected_isin[]`, `action_type`, `announcement_date`, `record_date`, `ex_date`, `payment_date`, `effective_date`, `ratio`, `cash_per_share`, `child_isin[]`, `elections[]`, `default_election`, `source` (issuer / vendor).
4. **Identity:** `(ca_id, vendor_source)` — vendors disagree.
5. **Provenance:** Issuer announcement → DTC / Euroclear → vendor (Bloomberg DL, Refinitiv, ICE) → us. **Multi-source mandatory.**
6. **Temporal:** Effective per date sequence (per v10.3 §5.2 multi-date model). Versioned — issuers do correct.
7. **Failure consequences:** Wrong ratio on a 2:1 vs. 1:2 → 4× position error. Missed record date → entitlement lost. Delayed ex-date → trade-date positions disagree with custodian.
8. **(a) Reconciliation pair:** Inter-vendor CA reconciliation (typical 99.5% match — the 0.5% needs human review); custodian's CA notice; issuer's official press release.
9. **(b) Common break:** Vendor A treats a stock split as 2:1 effective Monday; vendor B as 2:1 effective Tuesday (one-day timing mismatch). Choosing the wrong vendor for a particular ISIN means executing the split on the wrong day.
10. **(c) Audit / SOX / IFRS:** Position-balance integrity (BCBS 239); SFTR field 21 (collateral mark); IFRS 9 derecognition rules on share consolidation.
11. **StatesHome home:** CA event mutates `UnitStatus[u]` (e.g. `superseded_by` for a merger, per addendum §4.4 amendment discipline); cash and position moves go via the move stream.

---

### FLOOR 6 — MARKET OBSERVABLES (RAW)

#### 6.1 Raw Quote / Trade Print
1. **Canonical:** `raw_market_data`
2. **Definition:** Per (instrument, source, timestamp): a raw observable — exchange last/bid/ask, MTF quote, OTC indicative, swap dealer composite. Carries source, timestamp UTC, confidence indicator, halted/trading-status flag.
3. **Min fields:** `instrument_id` (ISIN or contract spec hash), `source_id`, `quote_type` (last / bid / ask / mid / settlement), `price`, `size`, `currency`, `timestamp_utc_microseconds`, `venue_mic`, `quote_status` (firm / indicative / stale / halted).
4. **Identity:** `(instrument_id, source_id, timestamp_utc_microseconds, quote_type)`.
5. **Provenance:** Exchange feeds (CME MDP, ICE TMC, EBS, …), MTFs, vendor consolidated feeds, OTC dealers.
6. **Temporal:** Point-in-time, microsecond resolution. **Snapshots must be retained** to support time travel "as known at t" replay (per ledger v10.3 §1.2 Property 6).
7. **Failure consequences:** Bad print fed into Kalman filter without gating → calibrated curve poisoned → every downstream price wrong. Stale quote treated as fresh → MTM stale → margin call computed off stale price.
8. **(a) Reconciliation pair:** Cross-vendor (Bloomberg / Refinitiv / ICE / direct exchange feed) tick-by-tick; exchange's official daily settlement file.
9. **(b) Common break:** Fat-finger trade prints at 1000× normal price; if Kalman gating threshold is too loose, the calibrated parameter jumps; if too tight, a real news event is rejected. Tuning is the operational craft.
10. **(c) Audit / SOX / IFRS:** IFRS 13 fair-value hierarchy (Level 1 inputs); MiFID II RTS 25 timestamps; CRR prudent valuation (Article 105); BCBS 239 §6 (data integrity).
11. **StatesHome home:** Outside the three maps. Stored in the market-data store; certified outputs feed `UnitStatus[u]` (e.g. `last_settlement_price`).

#### 6.2 Settlement Price (Exchange Official EOD)
1. **Canonical:** `settlement_price`
2. **Definition:** Exchange-published end-of-day settlement price used for variation margin and official close. Distinct from last trade price; determined per exchange rule book.
3. **Min fields:** `instrument_id`, `exchange_mic`, `settlement_date`, `settlement_price`, `publication_timestamp`, `settlement_method` (last-trade / auction / TWAP / VWAP / theoretical).
4. **Identity:** `(instrument_id, exchange_mic, settlement_date)`.
5. **Provenance:** Exchange settlement file; published once per business day; corrections possible (versioned).
6. **Temporal:** Per-trading-day point. **Audit-critical**: variation margin uses this exact value (per v10.3 §7.4).
7. **Failure consequences:** Wrong settlement price → wrong VM → cash flow to / from CCP wrong → P&L misstated. Recovery requires CCP-coordinated correction.
8. **(a) Reconciliation pair:** Exchange settlement file (authoritative); CCP's mark file; broker's daily statement.
9. **(b) Common break:** Cross-time-zone settlement: same contract series settles at different times in Singapore / London / Chicago; treating a single MtMk price for all three (vs. v10.3 §8.4 dual-valuation) creates phantom basis PnL.
10. **(c) Audit / SOX / IFRS:** EMIR Article 11; CFTC Part 22 (LSOC); IFRS 13 Level 1 inputs.
11. **StatesHome home:** Feeds `UnitStatus[u_listed].last_settlement_price` (per addendum line 109).

#### 6.3 OTC Dealer / Composite Quote
1. **Canonical:** `otc_quote`
2. **Definition:** Indicative or firm OTC quote from a dealer panel for a non-exchange-listed instrument (corporate bond, IRS, FX-NDF). Often the only price source for illiquid instruments.
3. **Min fields:** `instrument_id`, `dealer_LEI`, `quote_type` (indicative / firm / TRACE-traded / consensus), `price`, `size`, `quote_timestamp_utc`, `quote_validity_seconds`, `request_for_quote_id`.
4. **Identity:** `(instrument_id, dealer_LEI, quote_timestamp)`.
5. **Provenance:** Bloomberg ALLQ / FIT, MarketAxess, Tradeweb; bilateral RFQ records.
6. **Temporal:** Point-in-time but typically valid for seconds to minutes.
7. **Failure consequences:** Single-dealer quote used for MTM of a position the dealer wrote → conflict of interest; auditor asks for independent corroboration.
8. **(a) Reconciliation pair:** Multiple dealer quotes; TRACE reported trades; consensus services (CompositeBVAL, MarketAxess CP+).
9. **(b) Common break:** A position is held in size and the only dealer quoting is the original counterparty; their quote drifts unfavourably to us; we MTM at their level despite the conflict.
10. **(c) Audit / SOX / IFRS:** IFRS 13 Level 2/3 disclosures with sensitivity analysis; CRR Article 105 Independent Price Verification.
11. **StatesHome home:** Same as 6.1.

---

### FLOOR 7 — CALIBRATED PARAMETERS & ORACLE SNAPSHOTS

#### 7.1 Calibrated Yield Curve / Vol Surface / Hazard Curve
1. **Canonical:** `calibrated_object`
2. **Definition:** Per valuation v1.0 §4: the Kalman-filtered, arbitrage-free, certified parameter vector representing a market state — yield curve nodes, vol surface coefficients, credit hazard rates.
3. **Min fields:** `calibration_id`, `object_type` (yield_curve / vol_surface / credit_curve / fx_surface), `state_vector` (the parameter ket), `state_covariance`, `kalman_gain`, `innovation_mahalanobis_distance`, `arb_certificate` (pass / fail), `certified_at_utc`, `input_observations[]`, `process_noise_q`, `observation_noise_r`, `version`.
4. **Identity:** `(object_type, calibration_id, certified_at_utc, version)`.
5. **Provenance:** Calibration workflow (per valuation v1.0 §6 PricingDAG calibration nodes). Inputs are raw observables (Floor 6.1).
6. **Temporal:** Per-cycle snapshot. **Versioned**; old calibrations retained for time-travel replay. Critical: replay "as known at t" uses the snapshot in force at t (per ledger v10.3 §7.7).
7. **Failure consequences:** Stale calibration → all dependent prices drift; valuation FSM (valuation v1.0 §3) eventually transitions affected units to Stale. Failed arb certificate → certified flag false → downstream Pricing DAG nodes refuse to fire → Pricing DAG ground-stop until manual override.
8. **(a) Reconciliation pair:** Multi-source inter-vendor curve check (Bloomberg vs. Refinitiv vs. internal); arb-free certificate residuals; consensus vendors (BVAL / Markit).
9. **(b) Common break:** A new mandatory clearing rate cap (e.g. SOFR floor) is added to the swap calibration but the bootstrap routine is not updated; calibrated curve fits worse on the floor side; PnL-explain residual inflates on rates trades.
10. **(c) Audit / SOX / IFRS:** IFRS 13 Level 2/3 (model inputs); CRR Article 105 prudent valuation; FRTB Internal Model Approach valuation.
11. **StatesHome home:** Calibration outputs feed `UnitStatus` of the calibration unit (if treated as a unit) and are an input to the price function `P_t(u)` — not in any of the three state maps directly, but versioned similarly to `ProductTerms`.

#### 7.2 Oracle Snapshot / Market Data Snapshot
1. **Canonical:** `market_data_snapshot`
2. **Definition:** A point-in-time, versioned, hash-chained bundle of certified market data used as input to a single lifecycle / pricing / settlement decision. Per v10.3 §7.7: the deterministic-oracle requirement.
3. **Min fields:** `snapshot_id`, `snapshot_time_utc`, `source_chain[]` (primary, fallback), `included_calibrations[]`, `included_rawquotes[]`, `hash` (SHA-256), `parent_hash`, `signed_by`.
4. **Identity:** `snapshot_id` + `hash`.
5. **Provenance:** Captured by the lifecycle workflow at the moment of execution (the oracle).
6. **Temporal:** Immutable once written; hash-chained; cryptographically attested per v10.3 invariant 4.
7. **Failure consequences:** Without snapshots, replay is non-deterministic → time travel fails → audit defence fails. Hash break → tamper evidence → forensic investigation.
8. **(a) Reconciliation pair:** Hash chain self-consistency; cross-system snapshot comparison (e.g. trading vs. valuation snapshot at same time).
9. **(b) Common break:** Worker uses live feed instead of stored snapshot during replay → "non-deterministic execution" Temporal error → workflow non-replayable → escalation.
10. **(c) Audit / SOX / IFRS:** BCBS 239 Principle 6 (accuracy); MiFID II RTS 25 (reconstruction); EU DORA (Article 8 ICT testing).
11. **StatesHome home:** Outside the three maps; immutable side log.

#### 7.3 ValuationRecord (per Valuation v1.0 §3)
1. **Canonical:** `valuation_record`
2. **Definition:** The structured output of a pricing cycle for a unit at a time: dirty price (= scalar `P_t(u)`), clean price, accrued, Greeks (model-specific Jacobian), model id, market_data_snap, compute_ms, `quality` (FIRM / INDICATIVE / APPROXIMATE / STALE / FAILED), `fsm_state`.
3. **Min fields:** As per valuation v1.0 Definition 3.1.
4. **Identity:** `(unit_id, timestamp, model_id)`.
5. **Provenance:** Pricing workflow (valuation v1.0 §6).
6. **Temporal:** Per cycle. Versioned per `(unit, timestamp, model)`. FSM state per valuation v1.0 §2.
7. **Failure consequences:** No FIRM record at EOD → official PnL cannot use it (per valuation principle "FIRM-only PnL") → reverts to last good with prudential haircut → reportable to risk.
8. **(a) Reconciliation pair:** Independent Price Verification function; multi-model consensus per valuation v1.0 §3.7 (model reserve = max disagreement); the prior FIRM record (PnL-explain).
9. **(b) Common break:** Model M1 prices a corporate bond at 98.50; M2 at 98.10; reserve = 0.40. Reserve unchanged for weeks → audit asks why no narrowing or escalation.
10. **(c) Audit / SOX / IFRS:** IFRS 13 sensitivity disclosures; CRR Article 105; FRTB (model risk management).
11. **StatesHome home:** Stored in the Valuation Store; not in the three maps.

---

### FLOOR 8 — MOVE STREAM / EVENT LOG

#### 8.1 Atomic Move
1. **Canonical:** `move`
2. **Definition:** Per v10.3 §2.3: an indivisible transfer of quantity of one unit between two wallets at a timestamp, with full provenance. The atomic unit of state change.
3. **Min fields:** `move_id`, `transaction_id`, `from_wallet_id`, `to_wallet_id`, `unit_id`, `quantity` (Decimal, positive), `coordinate` (per GPM: own / onloan / borr / coll_post / coll_recv / coll_rehyp), `timestamp_utc`, `source_contract_id`, `metadata` (event description, external refs, ISO 20022 message id, counterparty UTI).
4. **Identity:** `move_id` (deterministic from `(transaction_id, sequence_within_transaction)`).
5. **Provenance:** Smart contract proposes; executor commits (per v10.3 §7.7.1 — sole mutator).
6. **Temporal:** **Append-only, immutable, microsecond-stamped** (Invariant 4). Carries economic timestamp + booking timestamp.
7. **Failure consequences:** Lost or duplicated move → conservation broken → entire ledger correctness gone. Wrong coordinate (per GPM) → e.g. lend writes `own` instead of `onloan` → ownership invariant P18 broken.
8. **(a) Reconciliation pair:** Custodian movement statement (for moves crossing virtual-wallet boundary); CCP cash movement file; ISO 20022 confirmation.
9. **(b) Common break:** A retry of a settlement instruction submits twice; idempotency must hold (Invariant 5). If `transaction_id` is regenerated rather than reused, the executor commits twice → conservation still holds within each tx, but the position is doubled → custodian reconciliation breaks.
10. **(c) Audit / SOX / IFRS:** Event sourcing as the audit trail; SOX §404 (control over financial reporting); BCBS 239 (data lineage); DORA (audit trail).
11. **StatesHome home:** Move stream is the input log; mutates `PositionState`. Per addendum §2.4: `apply_all(events)` is the literal fold.

#### 8.2 Transaction
1. **Canonical:** `transaction`
2. **Definition:** Per v10.3 §2.4: a finite collection of moves at one timestamp satisfying conservation. Carries a `type` (SETTLEMENT / COLLATERAL / LIFECYCLE / ACCOUNTING / CORRECTION).
3. **Min fields:** `transaction_id` (idempotency key), `timestamp_utc`, `economic_timestamp` (vs. booking), `type`, `moves[]`, `source_contract_id`, `cdm_event_payload`, `corrects[]` (for compensating tx), `obligation_id?` (when discharging an obligation).
4. **Identity:** `transaction_id`.
5. **Provenance:** Smart contract output, validated and committed by executor.
6. **Temporal:** Atomic / all-or-nothing (Invariant 2); immutable post-commit; append-only (Invariant 4).
7. **Failure consequences:** Partial commit → inconsistent state → conservation violated. Without `transaction_id` idempotency → Temporal retries double-book.
8. **(a) Reconciliation pair:** CDM `BusinessEvent` payload should round-trip through the forgetful map F (v10.3 §10); replay should reproduce.
9. **(b) Common break:** Worker crash mid-commit; Temporal retries; without strict idempotency the second attempt creates a duplicate transaction with a fresh id.
10. **(c) Audit / SOX / IFRS:** Same as 8.1; specifically also EMIR Article 9 timestamp granularity; MiFIR RTS 24 microsecond.
11. **StatesHome home:** Transaction is the atomic delta unit per addendum C3 (atomic across `ProductTerms` / `UnitStatus` / `PositionState`).

#### 8.3 Compensating / Correction Transaction
1. **Canonical:** `correction_transaction`
2. **Definition:** Per v10.3 §9.4: an event-sourcing correction. New transaction with `type = CORRECTION` whose `corrects` field references the original transaction. Original is **not deleted**.
3. **Min fields:** All transaction fields plus `corrects: original_tx_id`, `correction_reason` (typo / market-data-correction / counterparty-dispute / vendor-restatement), `approved_by`, `approval_ticket`.
4. **Identity:** `transaction_id`.
5. **Provenance:** Manual or automated (e.g. obligation compensation per v10.3 §14).
6. **Temporal:** Booked at correction-discovery time; references the original economic timestamp.
7. **Failure consequences:** Without explicit chain → audit cannot distinguish economic events from corrections → SOX failure. Without preservation of the original → revisionist history → investigative impossibility.
8. **(a) Reconciliation pair:** Approval ticket (Jira / change-control); supervisor sign-off; counterparty notification.
9. **(b) Common break:** A correction is applied without the `corrects` field set → looks like a brand-new event → ledger statistics over-count economic activity.
10. **(c) Audit / SOX / IFRS:** SOX §302/404 (controls over corrections); IAS 8 (errors and changes in accounting estimates).
11. **StatesHome home:** Same as transaction.

---

### FLOOR 9 — UNIT-STATE JOURNAL (StatesHome 3 Maps)

The addendum ruling: state is in three maps. Each is a separate data category from ops' perspective because **each has a different mutation discipline and a different reconciliation question**.

#### 9.1 ProductTerms (Versioned, Append-Only)
1. **Canonical:** `product_terms_record`
2. **Definition:** Per addendum: immutable versioned `NonEmptyList[TermsVersion]` per unit_id. Carries multiplier, currency, expiry, CCP, strike, ISIN, fee schedule, mandate text, benchmark identity, index methodology, day-count, fungibility predicate.
3. **Min fields:** `unit_id`, `version_number`, `terms_payload`, `effective_from`, `effective_to?`, `is_fungibility_preserving_predicate`, `created_by_tx_id`, `created_at`, `superseded_by_unit_id?`.
4. **Identity:** `(unit_id, version_number)`.
5. **Provenance:** Unit registration (C7) or amendment (C8).
6. **Temporal:** **Append-only, never in-place mutation** (C6). Per addendum P6 ("immutability of terms") is structurally unreachable to violate.
7. **Failure consequences:** Wrong version applied at lifecycle event → wrong cash flows. In-place edit (which addendum forbids) → audit trail broken.
8. **(a) Reconciliation pair:** Confirmation document; CDM `Trade` payload at trade ingestion; counterparty's product master.
9. **(b) Common break:** Counterparty proposes a "minor" coupon-step-up amendment that actually shifts the schedule by a day; if booked as fungibility-preserving (C8 Preserving) when it should have been Breaking, two lots merge that should not have.
10. **(c) Audit / SOX / IFRS:** IFRS 9 derecognition rules on substantial modification; ISDA confirmation evidence; BCBS 239.
11. **StatesHome home:** This is the map.

#### 9.2 UnitStatus (Mutable, Shared)
1. **Canonical:** `unit_status_record`
2. **Definition:** Per addendum: mutable per-unit, shared across all holders. `lifecycle_stage`, `last_settlement_price`, `last_settlement_date`, `current_weights` (for QIS), `nav_index`, `triggered_barrier`, `superseded_by`.
3. **Min fields:** `unit_id`, `lifecycle_stage`, `last_settlement_price`, `last_settlement_date`, `current_weights[]`, `nav_index`, `triggered_barrier_flag`, `superseded_by_unit_id?`, `mutated_at`, `mutated_by_tx_id`.
4. **Identity:** `unit_id`.
5. **Provenance:** Lifecycle handler output; updated atomically per C3.
6. **Temporal:** Mutable; latest value visible. **Historical reconstruction by replay** of the move stream / lifecycle event log.
7. **Failure consequences:** Out-of-date `last_settlement_price` → next VM uses wrong base → reset chain breaks. `triggered_barrier` not set → optionality miscomputed.
8. **(a) Reconciliation pair:** Exchange settlement file; index publisher (S&P, MSCI, FTSE) for QIS / structured-product weights.
9. **(b) Common break:** Barrier breached intraday but `triggered_barrier` only flipped at next workflow tick; settlement that fires in between produces stale state.
10. **(c) Audit / SOX / IFRS:** IFRS 13 daily fair value; FRTB risk-factor observability; structured-product disclosures.
11. **StatesHome home:** This is the map.

#### 9.3 PositionState (Per-Position, Monotone)
1. **Canonical:** `position_state_record`
2. **Definition:** Per addendum: per-`(wallet_id, unit_id)` tuple. `accumulated_cost`, `ccp_binding`, per-position OTC lifecycle, `entry_nav`, `hwm`, `accrued_mgmt_fee`, `accrued_perf_fee`, `benchmark_nav_at_inception`, `mandate_breach_flags`. **Monotone carrier**: once created, never deleted (C1). **Option accessor**: `None` ≠ `Some(zero)`.
3. **Min fields:** `wallet_id`, `unit_id`, position field set (varies by unit type), `last_mutated_at`, `last_mutated_by_tx_id`.
4. **Identity:** `(wallet_id, unit_id)`.
5. **Provenance:** Atomic StateDelta from lifecycle handlers (C3, C11 — each field has a unique writer handler).
6. **Temporal:** Mutable per-field (per writer); overall row monotone-retained.
7. **Failure consequences:** Loss of `accumulated_cost` history → futures VM reset wrong (per v10.3 §7.4 worked example). Loss of HWM history → performance fee miscomputed → restated NAV.
8. **(a) Reconciliation pair:** CCP statement (for `accumulated_cost` of a wallet); fund administrator NAV vs. internal HWM.
9. **(b) Common break:** Sub-account closed and PositionState row garbage-collected; six months later wash-sale lookback for tax requires the closed history → cannot reconstruct.
10. **(c) Audit / SOX / IFRS:** IRS wash-sale rules; tax 1099-B; performance-fee audit; EMIR Article 11 VM reconstruction.
11. **StatesHome home:** This is the map.

---

### FLOOR 10 — OBLIGATION REGISTER (per v10.3 §14)

#### 10.1 Obligation Record
1. **Canonical:** `obligation`
2. **Definition:** Per v10.3 Definition 14.1: tuple `(id, type, source, t_d, D, κ)` registered in the Obligation Store with a deadline, discharge predicate, and compensation action.
3. **Min fields:** `obligation_id`, `obligation_type` (per Table 14.1: bond_coupon / option_expiry / IRS_reset / futures_VM / SBL_recall_return / SBL_manuf_dividend / SBL_collateral_subst / CSA_VM / CSA_IM / collateral_substitution / SBL_collateral_topup / close_out_netting / SFTR_report / SLATE_report / EMIR_report / settlement_instruction), `source_unit_or_agreement_id`, `deadline_utc`, `discharge_predicate_id`, `compensation_action_id`, `state` (PENDING / ATTEMPTED / DISCHARGED / COMPENSATED / DEFAULTED), `created_by_tx_id`, `last_state_change_tx_id`.
4. **Identity:** `obligation_id` deterministically derived from `(source_event_id, obligation_type)`.
5. **Provenance:** Lifecycle handler output (Principle 14.1 Obligation Completeness).
6. **Temporal:** Created at event time; lifecycle through the 5-state FSM (Pending / Attempted / Discharged / Compensated / Defaulted); terminal states absorbing.
7. **Failure consequences:** Untracked obligation → silent miss → P21 (Obligation Liveness) violated → contractual breach. Specifically: SBL recall return missed → forced buy-in; CSA VM missed → close-out trigger; SFTR/SLATE/EMIR report missed → regulatory penalty.
8. **(a) Reconciliation pair:** Counterparty's obligation tracking (e.g. counterparty's CSA call register); regulator's submission acknowledgement; trade repository reception report.
9. **(b) Common break:** SBL collateral substitution demanded by phone; ops fails to register the obligation; deadline passes; lender escalates; relationship damaged. The whole point of v10.3 §14 is to make this structurally impossible.
10. **(c) Audit / SOX / IFRS:** SOX §404 (operational controls); EMIR Article 9 (reporting deadlines); SFTR Article 4 (T+1); UMR (margin call timing); GMSLA Section 9 (buy-in obligations).
11. **StatesHome home:** Per v10.3 §14.4: a view over the event log filtered to obligation entries; functionally a sibling registry to Unit Store.

#### 10.2 Obligation Type Catalogue
1. **Canonical:** `obligation_type_definition`
2. **Definition:** Per obligation_type: deadline-derivation rule (relative to source event date), discharge predicate definition, compensation action definition, scope (Unit / Agreement / Regulatory), regulatory anchor.
3. **Min fields:** `obligation_type`, `scope`, `deadline_rule`, `discharge_predicate_definition`, `compensation_action_definition`, `applicable_jurisdictions[]`, `regulatory_anchor`.
4. **Identity:** `obligation_type` (closed CDM-extended enum).
5. **Provenance:** Smart-contract author + Compliance + Legal joint sign-off (per F2 of the addendum risk register, predicate ownership is currently ungoverned and is a Phase-1 governance gap).
6. **Temporal:** Versioned; predicate changes are events.
7. **Failure consequences:** Predicate logic wrong → obligations marked discharged when they are not.
8. **(a) Reconciliation pair:** Legal text of the master agreement; regulator's reporting-deadline schedule.
9. **(b) Common break:** A regulatory deadline shortens (e.g. SFTR T+1 historically was T+2); the predicate is not updated; obligations now silently miss.
10. **(c) Audit / SOX / IFRS:** Direct regulatory; ISDA / GMSLA legal interpretation.
11. **StatesHome home:** Catalogue table.

---

### FLOOR 11 — SETTLEMENT & CONFIRMATION RECORDS

#### 11.1 SettlementInstruction
1. **Canonical:** `settlement_instruction`
2. **Definition:** Per v10.3 Definition 9.2: the projection of a SETTLEMENT or COLLATERAL transaction. ISIN, quantity, parties, dates, type (DvP / FOP / CASH).
3. **Min fields:** Per v10.3 §9.1: `instruction_id` (= tx_id), `trade_date`, `settlement_date`, `security_isin?`, `security_quantity?`, `delivering_party?`, `receiving_party?`, `cash_currency?`, `cash_amount?`, `cash_payer?`, `cash_receiver?`, `counterparty_LEI`, `execution_venue_MIC`, `settlement_type`.
4. **Identity:** `instruction_id`.
5. **Provenance:** `settle_projection(tx)` function (v10.3 §9.1).
6. **Temporal:** Generated at projection time; status lifecycle EXECUTED → INSTRUCTED → SETTLED / FAILED (v10.3 §9.7).
7. **Failure consequences:** Wrong settlement_date / SSI / amount → fail at CSD → CSDR penalty; in worst case, money sent to wrong party.
8. **(a) Reconciliation pair:** ISO 20022 `sese.025` (securities) / `camt.054` (cash) confirmation; CSD's daily statement; counterparty's allege.
9. **(b) Common break:** Trade settles on T+2 but settlement layer enriches with an SSI that effective-from is T+3; instruction rejected by CSD; manual repair cycle.
10. **(c) Audit / SOX / IFRS:** CSDR settlement discipline regime (mandatory penalty regime since 2022); SEC Rule 15c6-1 (T+1 in US); BCBS Principle for Financial Market Infrastructures.
11. **StatesHome home:** Generated transient; settlement state lifecycle bound back to `UnitStatus[u_settlement]` or as obligation discharge state per v10.3 §14.

#### 11.2 Settlement Status Transition
1. **Canonical:** `settlement_status_event`
2. **Definition:** Status change event per v10.3 §9.7: EXECUTED / INSTRUCTED / SETTLED / FAILED transitions, with cause and external reference.
3. **Min fields:** `instruction_id`, `from_status`, `to_status`, `transition_timestamp_utc`, `external_message_ref` (e.g. `sese.025` reference), `cause_code`.
4. **Identity:** `(instruction_id, transition_timestamp)`.
5. **Provenance:** ISO 20022 confirmation ingestion (CSD → settlement layer → ledger).
6. **Temporal:** Sequence per instruction; **append-only** lifecycle log.
7. **Failure consequences:** Status event lost → ledger thinks instruction is INSTRUCTED but CSD has SETTLED → reconciliation break; double-bookings risk.
8. **(a) Reconciliation pair:** CSD daily statement; bilateral allege/agree (DTCC TradeSuite for US equities; Omgeo CTM).
9. **(b) Common break:** SETTLED confirmation routed to wrong queue and unprocessed for days; daily reconciliation eventually catches it.
10. **(c) Audit / SOX / IFRS:** CSDR; T+1 settlement deadlines; failure attribution.
11. **StatesHome home:** Lifecycle log.

#### 11.3 ISO 20022 Message (sese.023, sese.025, pacs.008, camt.054, mt541, mt543, sese.020 etc.)
1. **Canonical:** `iso20022_message`
2. **Definition:** The wire-format message; carries `EndToEndId`, `TxId`, `MessageId`, full structured payload.
3. **Min fields:** `message_id`, `message_type`, `payload_xml`, `EndToEndId`, `TxId`, `direction` (out / in), `submission_timestamp`, `acknowledgement_status`.
4. **Identity:** `message_id`.
5. **Provenance:** Settlement layer (outbound) or CSD/counterparty (inbound).
6. **Temporal:** Per-message; archived per regulatory retention (typically 7 years).
7. **Failure consequences:** Non-conformant XML → CSD rejects → settlement fails; incident.
8. **(a) Reconciliation pair:** Inbound ack (`pacs.002`); CSD's message log.
9. **(b) Common break:** A schema upgrade (CBPR+ migration to ISO 20022 in correspondent banking) — sender on old schema, receiver on new; messages rejected.
10. **(c) Audit / SOX / IFRS:** SWIFT compliance; CPMI-IOSCO PFMI; CSDR reporting.
11. **StatesHome home:** Outside three maps; archived in message store.

---

### FLOOR 12 — VALUATION, PnL-EXPLAIN & RISK RECORDS (Addition; valuation v1.0)

#### 12.1 Valuation Lifecycle FSM State (per Valuation v1.0 §2)
1. **Canonical:** `valuation_fsm_state`
2. **Definition:** Per unit: the current state in the 8-state FSM (Unpriced / Pricing / Priced / Explaining / Explained / Quarantined / Stale / Failed).
3. **Min fields:** `unit_id`, `current_state`, `transitioned_at_utc`, `transition_trigger`, `last_firm_record_id`, `staleness_timer_due`.
4. **Identity:** `unit_id` (one current state per unit).
5. **Provenance:** PricingWorkflow internal state (Temporal-durable).
6. **Temporal:** Mutable; state transitions logged in workflow history.
7. **Failure consequences:** FSM stuck in Quarantined → official PnL uses last FIRM (with prudential adjustment); Stale beyond 3× cadence → obligation alert (v10.3 §14).
8. **(a) Reconciliation pair:** Workflow history vs. valuation store; valuation status report.
9. **(b) Common break:** A unit's calibrator goes silent; FSM transitions Stale → Failed; everything downstream loses FIRM coverage; days of partial pricing.
10. **(c) Audit / SOX / IFRS:** FRTB IMA risk-factor observability tests; IFRS 13 input observability classification; Independent Price Verification.
11. **StatesHome home:** Could be slotted into `UnitStatus[u]` as `valuation_fsm_state` (it is one-per-unit, mutable, shared) — this is a defensible mapping given the addendum schema.

#### 12.2 PnL Attribution Record (per Valuation v1.0 §7)
1. **Canonical:** `pnl_attribution`
2. **Definition:** Per cycle: total PnL decomposed into delta · ΔS, parameter Jacobian · ΔΘ, gamma · (ΔS)², theta · Δt, plus unexplained residual ε.
3. **Min fields:** `unit_id`, `from_record_id`, `to_record_id`, `total_pnl`, `delta_pnl`, `parameter_pnl[]` (per parameter), `gamma_pnl`, `theta_pnl`, `cashflow_pnl[]`, `unexplained_residual`, `tolerance_applied`, `passed`, `model_id`.
4. **Identity:** `(unit_id, from_record_id, to_record_id)`.
5. **Provenance:** PnL Explain function (valuation v1.0 §7).
6. **Temporal:** Per cycle; immutable post-publication.
7. **Failure consequences:** Unexplained residual exceeds tolerance → quarantine → official PnL contaminated → restated.
8. **(a) Reconciliation pair:** Front-office PnL system; risk system PnL; finance EOD PnL; client statement PnL.
9. **(b) Common break:** Unexplained residual is non-zero but consistent across many units → systemic Greek-computation bug or model-consistency violation (Remark on model consistency).
10. **(c) Audit / SOX / IFRS:** FRTB PnL Attribution Test (PLA: KS test, Spearman test); CRR Article 105; daily SOX-relevant control.
11. **StatesHome home:** Outside three maps; valuation store.

#### 12.3 Model Risk Reserve
1. **Canonical:** `model_reserve`
2. **Definition:** Per unit: max disagreement across approved models, held as a reserve against price uncertainty.
3. **Min fields:** `unit_id`, `as_of_utc`, `models_compared[]`, `max_diff`, `reserve_amount`, `change_from_prior`.
4. **Identity:** `(unit_id, as_of_utc)`.
5. **Provenance:** Multi-model pricing run.
6. **Temporal:** Per cycle.
7. **Failure consequences:** Stale reserve → undercapitalised; growing reserve → market regime change.
8. **(a) Reconciliation pair:** IPV multi-source; auditor's independent revaluation.
9. **(b) Common break:** Reserve calculated using only two of three approved models because third was failing → understated reserve.
10. **(c) Audit / SOX / IFRS:** CRR Article 105 prudent valuation (model risk AVA); FRTB DRC.
11. **StatesHome home:** Valuation store.

---

## 3. Floor Coverage Map (back to brief's six)

| Brief floor | My items mapped                                            |
|-------------|------------------------------------------------------------|
| 1. Static   | 1.1 firm_identity, 1.2 reference_currency_policy, 1.3 business_calendar, 1.4 accounting_classification, 1.5 tolerance_policy |
| 2. Reference| 2.1 security_master, 2.2 exchange_contract_spec, 2.3 venue_master, 2.4 cfi_taxonomy, 2.5 lei_record, 2.6 daycount_convention |
| 3. Market   | 6.1 raw_market_data, 6.2 settlement_price, 6.3 otc_quote     |
| 4. Oracle   | 7.1 calibrated_object, 7.2 market_data_snapshot, 7.3 valuation_record |
| 5. Smart-contract execution | 8.1 move, 8.2 transaction, 8.3 correction_transaction, 9.1 product_terms_record, 9.2 unit_status_record, 9.3 position_state_record, 10.1 obligation, 10.2 obligation_type_definition, 11.1 settlement_instruction, 11.2 settlement_status_event, 11.3 iso20022_message |
| 6. Listed-instrument detail | 5.1 listed_unit (and broadened: 5.2 otc_trade_unit, 5.3 sbl_loan_unit, 5.4 mandate_unit, 5.5 corporate_action) |
| **Additions outside the 6 floors** | 3.1 counterparty_master, 3.2 ssi_record, 3.3 custody_topology, 3.4 tax_status, 4.1 isda_master, 4.2 csa_record, 4.3 sft_master, 4.4 mandate_terms, 12.1 valuation_fsm_state, 12.2 pnl_attribution, 12.3 model_reserve |

**Item count:** 36 items across 12 floors. Brief floors covered: all 6, with relabelling/broadening of Floors 1–6 as argued in §0.

---

## 4. Disagreements Summary (for downstream phases)

1. **Static vs. Reference must remain split** (Floor 1 vs. Floor 2) but with operational definitions: firm-controlled vs. third-party-authoritative.
2. **Market and Oracle should be split into raw observables (Floor 6 in mine) and certified/calibrated/snapshot (Floor 7).** The brief's Floor 3 + Floor 4 do this in spirit but the names "Market" and "Oracle" undersell the Kalman/certification machinery.
3. **"Smart-contract execution" is not one floor but four**: Move stream, Unit-state journal (3 maps), Obligation register, Settlement records.
4. **"Listed-instrument detail" must broaden to "Trade-and-contract identity & terms"** to admit OTC, SBL, mandate, and corporate-action unit types.
5. **Five floors are missing entirely from the brief**: Counterparty / Legal-entity / Account topology (Floor 3), Legal Agreement (Floor 4), Obligation Register (Floor 10), Valuation/PnL-explain/Risk records (Floor 12), and arguably Tax/Withholding (treated under Floor 3 here but could be its own).
6. **StatesHome's three maps are themselves a data category**, not just a storage schema, because each map answers a different reconciliation question and has a different mutation discipline.
7. **The Obligation Register is the most operationally important addition** in v10.3 §14: without it, recall returns, collateral substitutions, regulatory reports, and CSA margin calls have no first-class home and no liveness guarantee. Phase 1 must enumerate it alongside the move stream; otherwise the data model is incomplete on the most failure-prone surfaces.

---

## 5. Audit-Trail / SOX / IFRS Crosswalk (Selected Highlights)

| Regulation / Standard | Items most directly load-bearing |
|------------------------|----------------------------------|
| SOX §404 (ICFR)        | 1.1 firm_identity, 1.4 accounting_classification, 1.5 tolerance_policy, 8.x move stream, 8.3 correction_transaction, 10.1 obligation |
| BCBS 239              | All of Floor 1, 2, 3; full Floor 8 lineage; Floor 12 valuation |
| IFRS 9                 | 1.4 accounting_classification, 5.x trade units (FVTPL/FVOCI determination), 8.1 move (derecognition), 5.3 sbl_loan_unit (paragraph 3.2.6 — lender does not derecognise) |
| IFRS 13                | 6.x raw market data, 7.x calibrated/snapshot, 12.2 pnl_attribution, 12.3 model_reserve |
| EMIR Refit             | 2.5 lei_record, 5.2 otc_trade_unit, 4.1/4.2 master/CSA, 10.1 obligation (reporting), 11.x settlement |
| MiFIR RTS 22 / RTS 25  | All of Floor 2; Floor 6 timestamps; Floor 8 microsecond stamping |
| SFTR / SLATE           | 5.3 sbl_loan_unit, 4.3 sft_master, 10.1 obligation, 11.x settlement |
| UMR (BCBS-IOSCO IM)   | 4.2 csa_record, 10.1 obligation (CSA_IM_DELIVERY) |
| CSDR (settlement disc.)| 11.1 settlement_instruction, 11.2 settlement_status_event |
| CASS 6 / Rule 15c3-3   | 3.3 custody_topology, account_segregation flag |
| EU DORA               | 7.2 market_data_snapshot (hash chain), 8.1 move (audit trail), 12.1 valuation_fsm_state |
| FRTB                   | 7.x calibrated_object (Risk Factor Eligibility Test), 12.2 pnl_attribution (PLA test), 12.3 model_reserve |
| GDPR / PII            | 3.1 counterparty_master (PII fields), 3.4 tax_status (W-8/W-9 retention) |

---

## 6. Closing Position

The Ledger v11.0 framework, taken together with the StatesHome addendum and the valuation v1.0 stack, requires **at least 36 distinct first-class data categories**, organised into 12 ops-coherent floors. The brief's six-floor taxonomy is a defensible top-level grouping but undersells five operational realities: (i) counterparty/legal-entity data, (ii) legal-agreement data, (iii) the obligation register, (iv) the valuation lifecycle, and (v) the StatesHome three-map distinction.

Every item enumerated above carries a concrete reconciliation pair (so we know what to compare against), a plain-language failure mode (so engineers can rehearse the break), and a regulatory anchor (so the audit committee has its line). The reconciliation pairs alone — once enumerated — surface the operational surface area the framework must cover end-to-end. None should be omitted on the grounds of "implementation detail." In financial systems, the reconciliation pair *is* the specification.
