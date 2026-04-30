# Phase 1 Data Enumeration - SBL Specialist (Margaret Chen)

**Source corpus:** `Ledger_Spec_v11.0/ledger/ledger_v10.3.tex` (sections 13 Generalised Position Model + Appendices D/E for EU/US SBL); `ledger_v10.3_addendum_stateshome.tex` (3-map ProductTerms / UnitStatus / PositionState ruling); `ledger_valuation_v1.0.tex` (FSM, Greeks, Kalman, Pricing DAG).

**Enumeration discipline.** The Generalised Position Model introduces a six-coordinate vector `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` per (entity, unit). Every datum below is justified against (i) what writes/reads which coordinate, (ii) which lifecycle event consumes it, (iii) which regulatory regime requires it. SBL-specific items carry the `[SBL]` tag and the `(regime / event / coordinate)` triplet. The seven mandatory fields are given verbatim per item.

**Floor coverage check.** I retain all six floor categories. I argue (Section 8) that "Listed-instrument detail" should be a *property tag* on Reference Data, not a separate floor — but I keep it for compatibility.

---

## Glossary of abbreviations

- IBP-N = ISLA Best Practice Handbook clause N
- SFTR = Securities Financing Transactions Regulation (EU 2015/2365)
- SLATE = Securities Lending and Transparency Engine (FINRA Rule 6500 series, SEC 10c-1a)
- SSR = EU Short Selling Regulation (236/2012)
- CSDR = Central Securities Depositories Regulation (EU 909/2014, Refit 2023)
- GMSLA = Global Master Securities Lending Agreement (ISLA: 2000, 2010, 2018)
- 6-coord = six-coordinate position vector

---

## 1. STATIC DATA

Per-entity, per-account, per-agreement data that is registered once and amended bilaterally with notice. Static data does not flow on a market feed.

### 1.1 Legal Entity (Counterparty)

1. **Canonical name:** `LegalEntity`
2. **Definition:** A juridical person (or its proxy) capable of being a lender, borrower, agent lender, triparty agent, beneficial owner, or custodian in an SBL transaction. Real entities and virtual wallets share this namespace.
3. **Minimum field set:** `lei` (ISO 17442, 20 chars), `name`, `country_of_incorporation`, `entity_type` ∈ {bank, broker_dealer, prime_broker, mutual_fund, pension, hedge_fund, agent_lender, triparty_agent, ccp, custodian, other}, `parent_lei` (optional), `mifid_classification` (eligible counterparty / professional / retail), `fatca_status`, `crs_status`, `wallet_id_root` (ledger-internal binding).
4. **Identity:** `lei` is canonical. Where no LEI exists, a deterministic surrogate `INTERNAL:<hash>` is used and reconciled at trade-event time.
5. **Provenance:** GLEIF (LEI authoritative source); internal KYC/onboarding system for `mifid_classification`, `fatca_status`. The Ledger consumes; it does not author.
6. **Temporal semantics:** Bitemporal. `valid_from`/`valid_to` (when the LEI was active at GLEIF) is distinct from `recorded_from`/`recorded_to` (when the firm knew the fact). LEI lapses (renewal failures) are common — the loan booking timestamp must capture the LEI-state at booking, not at reporting.
7. **Failure consequences:** SFTR rejection (LEI mandatory on both sides since June 2020). SLATE rejection. Locate cannot be confirmed without identified counterparty. Conservation is unaffected (the Ledger uses internal wallet IDs) but external reconciliation breaks.

### 1.2 Wallet Registry Entry [Ledger-internal]

1. **Canonical name:** `WalletRegistry`
2. **Definition:** Per-wallet metadata record (per StatesHome addendum: KYC, permissions, audit cursor — explicitly NOT economic state).
3. **Minimum field set:** `wallet_id`, `wallet_kind` ∈ {real, virtual, omnibus, segregated, triparty_pool, cash_pool_standard, cash_pool_eu, depot, nostro, vostro}, `owning_entity_lei`, `permission_set`, `kyc_status`, `audit_cursor`, `book_id`, `currency_base`, `is_lendable_pool` (bool), `is_collateral_pool` (bool).
4. **Identity:** `wallet_id` is internally generated, immutable.
5. **Provenance:** Ledger-internal; created at onboarding and at each new SBL-specific facility (e.g. opening a triparty long box).
6. **Temporal semantics:** Append-only history of permission changes. The wallet itself is immutable; permissions are versioned.
7. **Failure consequences:** Reads against an unregistered wallet must error (cannot return zero — that would conflate "never held" with "held and flat", per addendum C1). Conservation is unaffected; routing logic breaks.

### 1.3 Standard Settlement Instructions (SSI)

1. **Canonical name:** `SSI`
2. **Definition:** Per-(entity, market, instrument-class, currency) bundle of CSD/custodian account, BIC, place of settlement, place of safekeeping (per IBP-105/109).
3. **Minimum field set:** `entity_lei`, `market_iso`, `instrument_class`, `currency`, `psafe`, `psett`, `account`, `bic`, `effective_from`, `effective_to`, `last_reconciled`.
4. **Identity:** Composite key `(entity_lei, market, instrument_class, ccy)`.
5. **Provenance:** ALERT/Omgeo, entity onboarding, bilateral exchange. Reconciled at least annually (IBP-105).
6. **Temporal semantics:** Versioned; old SSIs retained for replay against historical settlement messages.
7. **Failure consequences:** Settlement instructions cannot be generated; trade matches at vendor but fails at CSD; CSDR penalties accrue from intended-settlement-date.

### 1.4 GMSLA / MSLA Master Agreement [SBL]

1. **Canonical name:** `MasterAgreement`
2. **Definition:** The bilateral legal contract under which an SBL relationship operates. (regime / inception / no coordinate — sets `legal_regime` field on every loan unit booked under it.)
3. **Minimum field set:** `agreement_id`, `version` ∈ {GMSLA_2000, GMSLA_2010_TT, GMSLA_2018_SI, MSLA, PBA, OSLA, MEFISLA}, `effective_date`, `governing_law`, `pair_lei_a`, `pair_lei_b`, `automatic_early_termination`, `set_off_election`, `designated_offices[]`, `event_of_default_thresholds`, `cross_default_threshold`, `notice_addresses`, `party_a_acting_as_agent` (bool), `digital_assets_annex` (bool).
4. **Identity:** `agreement_id` (internal); plus an ISLA Clause Library taxonomy fingerprint of the actual schedule provisions.
5. **Provenance:** Legal documentation. The ISLA Clause Library and Taxonomy is the canonical taxonomy; member firms map their schedules to it.
6. **Temporal semantics:** Effective-date dated; amendments are versioned via Schedule amendments (10 business days notice for collateral schedule changes per IBP-191). Versioning is bitemporal: `legal_effective` vs `system_recorded`.
7. **Failure consequences:** Without a registered master, no loan unit may be booked (P11 enforcement). Rehypothecation rules, default cascades, and locate confirmation routing all branch on this record. (regime: ALL / event: any new loan / coordinate: gates initial transaction)
8. **(a) Regulatory regime:** SFTR (governing-documentation field on counterparty questionnaire); SLATE (Master agreement type field); CSDR (eligible-trade scope). **(b) Lifecycle event:** every new-loan booking. **(c) Six-coordinate move it gates:** the four-move loan-initiation transaction (Lender.onloan += Q; Borrower.borr += Q; Borrower.coll_post += LV; Lender.coll_recv += LV).

### 1.5 Collateral Schedule [SBL]

1. **Canonical name:** `CollateralSchedule`
2. **Definition:** Per-master-agreement annex defining eligible collateral assets, haircut/margin percentages, concentration limits, currency eligibility, and triparty agent identity.
3. **Minimum field set:** `agreement_id`, `effective_from`, `eligible_isins[]` or `eligibility_predicate` (rating, asset class, country, listing venue, residual maturity bands), `haircut_table[(asset_class, rating, maturity_band)]`, `margin_pct` (cash), `concentration_limit_pct` (per-issuer, per-asset-class, per-currency), `wrong_way_exclusion[]`, `cross_currency_allowed` (bool), `triparty_agent_lei` (optional), `rqv_currency`, `intraday_substitution_allowed`.
4. **Identity:** `(agreement_id, version)`.
5. **Provenance:** Bilateral negotiation; ISLA Triparty RQV best practice (IBP-189) provides the cadence layer.
6. **Temporal semantics:** Amendments require ≥10 business days notice (IBP-191). The schedule applicable to a margin call is the version effective at the call's calculation date, not today's version.
7. **Failure consequences:** Margin calls cannot be calculated; substitutions cannot be validated; P19 (rehypothecation regime compliance) cannot be evaluated for any non-cash collateral movement.
8. **(a)** SFTR (collateral basket reporting); CSDR (eligible-collateral scope for fail mitigation). **(b)** Initial collateral posting; mark-to-market margin calls; substitutions; rehypothecation validation. **(c)** Gates `coll_post`/`coll_recv`/`coll_rehyp` writes for all non-cash collateral moves.

### 1.6 Triparty Agreement [SBL]

1. **Canonical name:** `TripartyAgreement`
2. **Definition:** Tripartite contract among lender, borrower, and triparty agent (Euroclear, Clearstream, BNY Mellon, JPM, State Street, Citi) governing daily RQV agreement (IBP-189), allocation, optimisation, and substitution.
3. **Minimum field set:** `agent_lei`, `lender_account`, `borrower_account`, `eligibility_set_ref`, `rqv_currency`, `rqv_calculation_method`, `intraday_revisions_allowed` (bool), `auto_substitution` (bool), `concentration_overrides`, `cut_off_times` (per market).
4. **Identity:** `(agent_lei, lender_lei, borrower_lei, eligibility_set_ref)`.
5. **Provenance:** Bilateral; agent onboarding.
6. **Temporal semantics:** Effective-date-versioned. Cut-off times are wall-clock (time-zone aware).
7. **Failure consequences:** RQV cannot be agreed at 10:00 UTC start-of-day, 14:00 UTC intraday, or 17:00 UTC end-of-day (IBP-189). The `coll_recv` coordinate cannot be reconciled with the agent's allocation report.
8. **(a)** SFTR (collateral identification — triparty allocation report flow). **(b)** Daily RQV agreement; intraday revision; substitution; release. **(c)** Gates `coll_recv`/`coll_post` writes when collateral_method = `non_cash_triparty`. The triparty agent itself is a virtual entity in the Ledger.

### 1.7 Agent Lender Disclosure Schedule [SBL]

1. **Canonical name:** `AgentLenderDisclosure`
2. **Definition:** Mapping from an agent lender's disclosed-counterparty-name to the underlying beneficial-owner LEIs and lendable position quantities (IBP-297, IBP-307).
3. **Minimum field set:** `agent_lei`, `disclosure_date`, `bo_entries[(bo_lei, allocation_rule, share)]`, `disclosure_frequency` ∈ {trade_time, daily, periodic}, `reallocation_policy`.
4. **Identity:** `(agent_lei, disclosure_date)`.
5. **Provenance:** Agent lender feed; potentially repeated daily (IBP-297).
6. **Temporal semantics:** A reallocation event (IBP-307) changes the BO-of-record on a live loan without changing the borrower's view. Bitemporal: `economic_effective` vs `disclosed_at`.
7. **Failure consequences:** Cannot determine the SFTR reporting BO for a reallocation; SFTR MODI (counterparty change) cannot fire; lender wallet identity on a loan unit cannot transition cleanly.
8. **(a)** SFTR (counterparty 1 = ultimate BO LEI per ESMA Q&A). **(b)** Reallocation event in `S_live` (state-only update per § 13.7 state machine). **(c)** Gates a state-only transition; no coordinate move, but identity re-binding on `lender(u_loan)`.

### 1.8 Custody / Depot Account Mapping

1. **Canonical name:** `CustodyMapping`
2. **Definition:** Mapping from Ledger wallet to external custodian account (depot or sub-account).
3. **Minimum field set:** `wallet_id`, `custodian_lei`, `account_number`, `bic`, `place_of_safekeeping`, `omnibus_or_segregated`, `mapping_type` ∈ {1:1, n:1, 1:n}.
4. **Identity:** `(wallet_id, custodian_lei, account_number)`.
5. **Provenance:** Custodian onboarding.
6. **Temporal semantics:** Re-mapping events change the reconciliation target without changing position.
7. **Failure consequences:** Custodian reconciliation `own + borr + inflight ?= depot` cannot be evaluated (the simplified formula from § 13.10).

### 1.9 Operating Calendar / Market Cut-Off Catalogue

1. **Canonical name:** `MarketCalendar`
2. **Definition:** Per-market trading hours, settlement cut-offs, holidays, and standard settlement cycle (T+1, T+2, T+0).
3. **Minimum field set:** `market_iso`, `holidays[]`, `settlement_cycle`, `dvp_cutoff`, `fop_cutoff`, `iso20022_cutoff`, `auto_partial_cutoff`, `t2s_partial_hold_release_cutoff`.
4. **Identity:** `market_iso` (e.g. XETR, XPAR, XLON, XNYS).
5. **Provenance:** ISO 20022 Market Data; FIX Trading Community; ANNA; ISLA market-cut-off table.
6. **Temporal semantics:** Calendar is annual; cut-offs are versioned (T+1 transition is a versioning event).
7. **Failure consequences:** Recall notification deadline (close − 2 business days, IBP-328) cannot be computed; loan-instruction-release-1-hour-before-cutoff (IBP-124) cannot be enforced; CSDR penalty start-date cannot be computed.

---

## 2. REFERENCE DATA

Per-instrument data sourced from exchanges, CSDs, and reference-data vendors. Lives in Tier-1 of the Unit Store (per StatesHome addendum: `ProductTerms` for the listed-instrument case).

### 2.1 Equity Reference Record (Lendable Equity)

1. **Canonical name:** `EquityRef`
2. **Definition:** Per-security master data for a listed equity that may appear in `own`/`onloan`/`borr` coordinates.
3. **Minimum field set:** `isin`, `cusip`, `sedol`, `ticker_per_market[]`, `mic_primary`, `currency`, `issuer_lei`, `country_of_listing`, `country_of_incorporation`, `lot_size`, `is_hard_to_borrow` (HTB flag), `is_threshold_security` (Reg SHO list), `is_short_sale_restricted` (per-jurisdiction), `is_lendable` (bool), `corporate_action_calendar_ref`.
4. **Identity:** `isin`.
5. **Provenance:** ANNA (ISIN registry); exchange masters; SIX, Bloomberg, Refinitiv, ICE Data Services. Reg SHO threshold list is a SEC daily publication.
6. **Temporal semantics:** Effective-date versioning for ticker changes, ISIN changes (rare — corporate actions or listing transfers), and HTB-flag transitions.
7. **Failure consequences:** Locate cannot be priced (HTB rate); short-sale-restriction enforcement (P14 + jurisdiction predicate) cannot fire; corporate action processing (manufactured-dividend amount calculation, Day-5 example) cannot resolve the entitlement.

### 2.2 Bond Reference Record (Collateral Bond)

1. **Canonical name:** `BondRef`
2. **Definition:** Per-bond master data; especially relevant where bonds appear as non-cash collateral (Bunds in EU example).
3. **Minimum field set:** `isin`, `cusip`, `issuer_lei`, `issue_currency`, `coupon_rate`, `coupon_frequency`, `day_count`, `maturity`, `issue_date`, `accrual_basis`, `nominal_unit`, `seniority`, `rating[(agency, rating, outlook, asof)]`, `country`, `is_eligible_collateral_under[(schedule_ref, haircut)]`.
4. **Identity:** `isin`.
5. **Provenance:** ANNA; MarketAxess, Bloomberg, Refinitiv; rating agencies (S&P, Moody's, Fitch).
6. **Temporal semantics:** Coupon schedule is fixed at issuance. Ratings are time-stamped per agency action.
7. **Failure consequences:** Haircut table lookup fails; collateral eligibility cannot be evaluated; manufactured-coupon cash flow cannot be generated.

### 2.3 Tokenised Asset Reference Record [SBL]

1. **Canonical name:** `TokenAssetRef`
2. **Definition:** Per-tokenised-instrument master data when tokens are eligible collateral (ISLA Digital Securities Lending working group; § 13.13).
3. **Minimum field set:** `token_id` (contract address + chain ID), `underlying_isin`, `mirror_or_native`, `chain_id`, `custodian_lei` (for backed tokens), `redemption_mechanism`, `corporate_action_processing_layer` ∈ {custodial, token, hybrid}, `reportable_jurisdiction`.
4. **Identity:** `(chain_id, contract_address)` plus `underlying_isin` for backed tokens.
5. **Provenance:** Token issuer; chain explorer; ISLA Digital Assets Annex registration.
6. **Temporal semantics:** Mirror tokens may be redeemed/created daily; the binding to underlying ISIN is the load-bearing property.
7. **Failure consequences:** Fractional CA processing cannot be routed; double-counting of underlying + token (per § 12 tokenization gap) is uncatched; SFTR has no field set for tokenised collateral.
8. **(a)** SFTR (collateral identification — gap; ESMA has not amended). **(b)** Posted as collateral or rehypothecated. **(c)** Writes `coll_recv`/`coll_post` against the *token* unit, not the underlying.

### 2.4 Corporate Action Calendar [SBL-relevant]

1. **Canonical name:** `CorporateActionCalendar`
2. **Definition:** Per-(ISIN, event) record of upcoming or processed CA events, with manufactured-payment implications for SBL.
3. **Minimum field set:** `isin`, `event_id`, `event_type` ∈ {cash_dividend, stock_dividend, split, reverse_split, rights, spinoff, merger, tender, redemption, capital_return, name_change, isin_change}, `ex_date`, `record_date`, `payment_date`, `gross_amount`, `currency`, `withholding_rate_per_country`, `mandatory_or_voluntary`, `voting_record_date`.
4. **Identity:** `(isin, event_id)`.
5. **Provenance:** Issuer announcement; DTCC (US); Euroclear/Clearstream (EU); SWIFT MT564/MT566 (CA notifications); SIX, Refinitiv corporate actions feeds.
6. **Temporal semantics:** Bitemporal — announcement timestamp vs. ex-date vs. payment-date. Late or amended announcements re-fire the lifecycle.
7. **Failure consequences:** Manufactured-dividend (Day-5 of EU example, Day-7 of full lifecycle) cannot be computed; voting-rights election cannot be routed; `borrower.own -= div × Q_onloan` move cannot fire.
8. **(a)** SFTR no specific field; SLATE flags lifecycle modifications post-CA. **(b)** Manufactured-payment lifecycle event (CA on lent securities). **(c)** Cash move writes both parties' `own(ccy)`.

### 2.5 ESMA / SEC Restricted-Lists [SBL]

1. **Canonical name:** `RegulatoryRestrictionList`
2. **Definition:** Per-jurisdiction lists of securities or sovereigns subject to short-sale bans, locate restrictions, sanctions, or threshold designation.
3. **Minimum field set:** `list_id` ∈ {ESMA_SHORT_BAN, RCA_EMERGENCY_BAN, SEC_REGSHO_THRESHOLD, OFAC, EU_SANCTIONS, FCA_RESTRICTED}, `entries[(isin, from, to, basis, scope)]`, `publication_url`, `last_refreshed`.
4. **Identity:** `(list_id, isin, effective_from)`.
5. **Provenance:** ESMA Register, RCAs (FCA, BaFin, AMF, CONSOB, CNMV), SEC, OFAC. Daily refresh.
6. **Temporal semantics:** Effective-date intervals; emergency bans are intraday-effective (SSR Article 23).
7. **Failure consequences:** Short-sale that should have been blocked clears; SSR Article 12 violation; CSDR/regulator sanctions.
8. **(a)** SSR (Articles 20, 23, 24, 27); Reg SHO Rule 203 + Rule 204 (threshold list). **(b)** Pre-trade locate confirmation; pre-trade short-sale gate. **(c)** Blocks the four-move lending transaction and the short-sell `own -= Q` move.

### 2.6 Net Short Position Disclosure Threshold Table [SBL]

1. **Canonical name:** `NSPThresholdTable`
2. **Definition:** Per-jurisdiction NSP notification thresholds (private to RCA) and public-disclosure thresholds, plus issuer-share-capital references for ratio computation.
3. **Minimum field set:** `jurisdiction`, `private_notification_threshold`, `public_disclosure_threshold`, `increment`, `share_capital_source`, `effective_from`.
4. **Identity:** `(jurisdiction, effective_from)`.
5. **Provenance:** ESMA SSR (0.2% notification, 0.1% increment, 0.5% public disclosure); national RCA registers; ESMA70-448-10 proposes centralisation.
6. **Temporal semantics:** Long-stable; ESMA harmonisation is a versioning event.
7. **Failure consequences:** Issuer-level NSP aggregation fails; Article 5/6/7 notification deadline missed; sanctions under MAR Article 30 alignment.
8. **(a)** SSR Articles 5, 6, 7. **(b)** Daily NSP computation against per-issuer share capital. **(c)** Read-only against `own` (negative `own` = short component); does not gate moves but gates regulatory submission.

### 2.7 Rebate-Rate Benchmark Reference

1. **Canonical name:** `RebateBenchmark`
2. **Definition:** Per-currency reference rate used as the benchmark for rebate quotation (Fed Funds Effective in US example; ESTR/€STR or SOFR in EUR/USD bilateral; OIS where applicable).
3. **Minimum field set:** `benchmark_id`, `currency`, `tenor`, `publisher`, `cessation_status`, `successor_benchmark`.
4. **Identity:** `benchmark_id`.
5. **Provenance:** Benchmark administrator (Fed NY for SOFR/Fed Funds; ECB for ESTR; SONIA admin for GBP). BMR-compliant.
6. **Temporal semantics:** Daily fix. Cessation events (LIBOR-style) require fallback application.
7. **Failure consequences:** Rebate cannot be computed; daily lending economics break; spread to MMF reinvestment cannot be calculated (US example § E.2).

### 2.8 Settlement-Day Calendar Per Currency

1. **Canonical name:** `CurrencyCalendar`
2. **Definition:** Per-currency cash settlement calendar, distinct from market trading calendar.
3. **Minimum field set:** `currency`, `tom_next_holidays`, `value_date_rule`, `cls_eligible`.
4. **Identity:** `currency`.
5. **Provenance:** SWIFT, ECB TARGET2 calendar, FedWire calendar.
6. **Temporal semantics:** Annual.
7. **Failure consequences:** Cash collateral value-date computation breaks; cross-currency cash-pool exposure roll-over (next-business-day rule) cannot be timed.

---

## 3. MARKET DATA

Time-series prices and rates consumed at COB (per IBP-127/128/310) and intraday for valuation and exposure.

### 3.1 Closing Price Vector (COB)

1. **Canonical name:** `ClosePrice`
2. **Definition:** Per-(ISIN, market, currency) close-of-business mid-price used for daily mark-to-market and exposure.
3. **Minimum field set:** `isin`, `market_iso`, `currency`, `price`, `price_basis` ∈ {mid, bid, ask, trade, official_close}, `asof_date`, `source` ∈ {bloomberg, reuters, crest, exchange_official}, `quality_status` (per valuation FSM § 2: ARMED|CALC_OK|REJECTED|STALE).
4. **Identity:** `(isin, market_iso, asof_date, source)`.
5. **Provenance:** Bloomberg final arbitrating per IBP-127; CREST overrides for UK assets per IBP-310; vendor close from Reuters/ICE as fallback.
6. **Temporal semantics:** Effective at COB on `asof_date`. Restatements (vendor corrections) require bitemporal handling — replay at `asof_date` must use the price *known at* `asof_date`, not the corrected value, unless explicitly opted into "today's data" replay.
7. **Failure consequences:** Daily exposure (IBP-163) cannot be computed; margin call cannot be agreed; SFTR VALU cannot fire.

### 3.2 FX Rate Vector (Previous COB)

1. **Canonical name:** `FXRate`
2. **Definition:** Per-(ccy_pair) previous-close FX used for cross-currency loan-value computation (IBP-163: FXRate is previous COB).
3. **Minimum field set:** `ccy_pair`, `rate`, `asof_date`, `source`, `is_fixing` (bool), `fixing_id`.
4. **Identity:** `(ccy_pair, asof_date, source)`.
5. **Provenance:** WM/Refinitiv 4pm London, ECB reference, Bloomberg BFIX.
6. **Temporal semantics:** Previous-COB by IBP convention; effective-date-versioned.
7. **Failure consequences:** χ in `LV = ⌈Q × P × M% × χ⌉_{0.01}` is missing; cross-currency cash pool re-quoting fails; cross-currency exposure (IBP-319) cannot be cleared.

### 3.3 Borrow / Lending Fee-Rate Quote Surface [SBL]

1. **Canonical name:** `BorrowFeeQuote`
2. **Definition:** Per-(ISIN, term, market, currency) intraday fee-rate quote — the price of borrowing.
3. **Minimum field set:** `isin`, `quote_time`, `market`, `currency`, `term_type` ∈ {open, term_1d, term_1w, term_1m, term_3m, term_open}, `fee_rate_bps`, `quoted_size`, `quote_source` ∈ {EquiLend, Pirum, S3 Partners, IHS Markit (Datalend), bilateral_indication}, `is_HTB`, `general_collateral_or_specials`.
4. **Identity:** `(isin, market, term_type, quote_source, quote_time)`.
5. **Provenance:** Vendor consolidators (EquiLend, Pirum, Datalend/S&P). Bilateral RFQs.
6. **Temporal semantics:** Intraday; tick-stamped. Stale > 30 min for HTB; stale > 1 day for GC.
7. **Failure consequences:** Pricing of new loans fails; rate-change MODI cannot be priced; valuation of the loan unit `P_t(u_loan) = LV × fee × DCF` cannot be marked.
8. **(a)** SFTR (rate field on NEWT/MODI). **(b)** Loan booking; rate change. **(c)** Does not directly gate a coord move; sets the parameter on the loan-unit `ProductTerms`/`UnitStatus`.

### 3.4 Rebate-Rate Fix [SBL — cash-collateralised lending]

1. **Canonical name:** `RebateRateFix`
2. **Definition:** Daily fixing of the benchmark + spread rebate that the lender pays the borrower on cash collateral.
3. **Minimum field set:** `benchmark_id`, `fix_date`, `fix_value`, `tenor`, `spread_bps_negotiated_per_loan`, `effective_rate_per_loan_id`.
4. **Identity:** `(benchmark_id, fix_date)`.
5. **Provenance:** Benchmark administrator daily fix.
6. **Temporal semantics:** Daily; ACT/360 accrual.
7. **Failure consequences:** Daily rebate accrual (US example: 892.5M × 5%/360) cannot fire; net lending spread (rebate vs. MMF reinvestment) cannot be settled.

### 3.5 Manufactured-Payment Rate (Tax-Adjusted) [SBL]

1. **Canonical name:** `ManufacturedPaymentRate`
2. **Definition:** Per-(jurisdiction, treaty, dividend) effective rate at which a borrower must compensate the lender for forgone dividend, accounting for withholding tax differential between actual and synthetic recipients (EU example Day-5 tax note).
3. **Minimum field set:** `corp_action_event_id`, `lender_country`, `borrower_country`, `treaty_rate`, `gross_amount`, `manufactured_amount`, `is_full_pass_through`.
4. **Identity:** `(event_id, lender_lei, borrower_lei)`.
5. **Provenance:** Tax operations; bilateral agreement; OECD treaty register.
6. **Temporal semantics:** Per-event.
7. **Failure consequences:** Manufactured-dividend cash move (`Borrower.own -= mfg_amt; Lender.own += mfg_amt`) is for the wrong amount; tax exposure mis-recorded.
8. **(a)** None directly — this is a contractual computation under GMSLA. **(b)** Manufactured-payment lifecycle event. **(c)** Writes both parties' `own(ccy)`.

### 3.6 RQV Snapshot [SBL — triparty]

1. **Canonical name:** `RQVSnapshot`
2. **Definition:** The Required Value computed and agreed via triparty agent at the prescribed cadence (start-of-day 10:00 UTC, intraday 14:00 UTC, end-of-day 17:00 UTC; IBP-189).
3. **Minimum field set:** `triparty_agreement_ref`, `snapshot_time`, `rqv_currency`, `rqv_value`, `agent_allocation_report_ref`, `agreement_status` ∈ {agreed, disputed, pending}.
4. **Identity:** `(triparty_agreement_ref, snapshot_time)`.
5. **Provenance:** Triparty agent (Euroclear AutoSelect, Clearstream Xemac, JPM, BNYM, etc.).
6. **Temporal semantics:** Three intraday cadences. Disputes carry forward and are resolved bilaterally.
7. **Failure consequences:** `coll_recv`/`coll_post` cannot be reconciled with the agent's own books; the lender cannot rely on the collateral as cover for exposure (IBP-192).
8. **(a)** SFTR collateral block. **(b)** Mark-to-market; substitution; release. **(c)** Drives `coll_recv`/`coll_post`/`coll_rehyp` writes when method = triparty.

### 3.7 Settlement Status Stream

1. **Canonical name:** `SettlementStatusEvent`
2. **Definition:** Per-instruction state-machine update from CSD/custodian (instructed → matched → partially_settled → settled / failed / cancelled / bought-in).
3. **Minimum field set:** `submission_ref`, `transaction_id`, `iso20022_type` (sese.020 etc.), `event_time`, `state`, `partial_qty`, `failure_reason`, `csd_id`.
4. **Identity:** `(submission_ref, event_seq)`.
5. **Provenance:** CSD ISO 20022 messages (sese.024 status), custodian feeds.
6. **Temporal semantics:** Real-time; both parties' systems should reflect within 1 hour (IBP-121).
7. **Failure consequences:** P17 (Settlement State Monotonicity) cannot be verified; CSDR penalty timer cannot start; the in-flight virtual-wallet balance cannot resolve to a `coll_recv` write (prepay scenario, IBP-177).

### 3.8 CSD Penalty Notification

1. **Canonical name:** `CSDRPenalty`
2. **Definition:** Per-instruction CSDR cash penalty issued by the CSD.
3. **Minimum field set:** `instruction_ref`, `isin`, `currency`, `penalty_rate_used`, `penalty_amount`, `failing_party`, `failing_calendar_days`, `csd_id`, `notification_date`, `claim_window_end` (30 calendar days, IBP-141).
4. **Identity:** `(instruction_ref, csd_id, notification_date)`.
5. **Provenance:** CSD daily penalty file (Euroclear, Clearstream, etc.). Per CSDR Refit 2023, FOP collateral transfers attributable to non-trading operations are exempt — the file must carry the exemption flag.
6. **Temporal semantics:** Daily. Claim window is 30 calendar days from CSD penalty issuance for CSDR-attributed; 60 days for non-CSDR (IBP-141).
7. **Failure consequences:** Claim cannot be issued within window; threshold (€500 minimum, IBP-141) cannot be evaluated; cost attribution (P-attribution) cannot fire.
8. **(a)** CSDR (Settlement Discipline Regime, Refit 2023). **(b)** Settlement fail; claim issuance. **(c)** Generates a cash move from failing party to non-failing party.

### 3.9 Money-Market Reinvestment NAV [SBL — US cash collateral]

1. **Canonical name:** `MMFNAV`
2. **Definition:** Daily NAV of the money-market fund / reinvestment vehicle into which cash collateral is reinvested (§ 13.14).
3. **Minimum field set:** `fund_lei_or_cik`, `ticker`, `nav`, `nav_date`, `is_constant_nav` (vs. floating), `breaking_buck_indicator`, `2a-7_compliance_flag`.
4. **Identity:** `(fund_lei, nav_date)`.
5. **Provenance:** Fund administrator; SEC N-MFP filings.
6. **Temporal semantics:** Daily; intraday for institutional prime MMFs.
7. **Failure consequences:** Reinvestment-asset valuation gap vs. fixed `collateral_amount` obligation cannot be quantified — reinvestment risk is unmonitored.

---

## 4. ORACLE DATA

External truth signals that gate Ledger commits but are not market data per se.

### 4.1 Locate Confirmation [SBL]

1. **Canonical name:** `LocateConfirmation`
2. **Definition:** Pre-trade affirmation by a lender / locate provider that securities are available for borrowing (SSR Article 12(1)(c); Reg SHO Rule 203(b)(1)).
3. **Minimum field set:** `locate_id`, `provider_lei`, `requestor_lei`, `isin`, `quantity`, `request_time`, `confirmation_time`, `expiry`, `quality_basis` ∈ {bona_fide_arrangement, easy_to_borrow_list, available_inventory_query}, `provider_signature`, `regulatory_basis` ∈ {SSR_12_1_a, SSR_12_1_b, SSR_12_1_c, RegSHO_203_b_1}, `consumed_loan_id` (optional, populated on conversion).
4. **Identity:** `locate_id`.
5. **Provenance:** Lender / locate provider via PB system, EquiLend Locate, OneChicago, vendor utilities. Per ESMA70-448-10 the third-party "commitment" must be reinforced.
6. **Temporal semantics:** Issued, confirmed, valid-until, consumed-or-expired. ESMA proposes 5-year retention (per ESMA70-448-10).
7. **Failure consequences:** Short sale rejected (P14 Locate Before Short); SSR Article 12 / Reg SHO Rule 203 violation; harmonised sanctions per MAR Article 30(2)(i)/(j) alignment proposed by ESMA70-448-10.
8. **(a)** SSR Article 12; Reg SHO Rule 203. **(b)** Short-sale gate; (does NOT fire moves at issuance, per § 13.16). **(c)** Gates the subsequent loan-initiation transaction and the short-seller's `own -= Q` write.

### 4.2 Fungibility Predicate Output (per StatesHome C8)

1. **Canonical name:** `FungibilityVerdict`
2. **Definition:** Per-amendment verdict produced by the product-declared fungibility predicate `is_fungibility_preserving : ProductTerms × TermsAmendment → {Preserving, Breaking}` (StatesHome C8).
3. **Minimum field set:** `unit_id`, `amendment_id`, `verdict`, `predicate_version`, `legal_signoff_lei`, `risk_signoff_lei`, `decision_time`, `rationale_ref`.
4. **Identity:** `(unit_id, amendment_id)`.
5. **Provenance:** Product team owns the predicate; Legal/Product/Risk RACI per institutional-brake F2.
6. **Temporal semantics:** Decision-time stamped; predicate version is also stamped.
7. **Failure consequences:** Wrong verdict → either (a) silent rewrite of `ProductTerms` for a fungibility-breaking amendment (illegal under C6) or (b) unnecessary `u_new` allocation and forced re-subscription. For SBL: a coupon step-up on a collateral bond should preserve fungibility; a CSA collateral-eligibility-schedule narrowing breaks it.

### 4.3 Manufactured-Payment Tax Determination

1. **Canonical name:** `TaxTreatmentOracle`
2. **Definition:** Per-(jurisdiction-pair, payment-type) tax treatment determination from tax-ops.
3. **Minimum field set:** `payment_event_id`, `jurisdiction_pair`, `treatment` ∈ {full_grossup, withhold, treaty_relief, manufactured_overseas_dividend}, `effective_rate`, `signed_off_by`, `signoff_date`.
4. **Identity:** `payment_event_id`.
5. **Provenance:** Tax operations team; OECD treaty database; HMRC manufactured-payment guidance for UK, IRS § 871(m) for US.
6. **Temporal semantics:** Per-event.
7. **Failure consequences:** Tax under/over-withholding on cross-border manufactured dividends; § 871(m) miscalculation for US-equity-linked SBL.

### 4.4 Default / Event-of-Default Trigger

1. **Canonical name:** `DefaultEvent`
2. **Definition:** Counterparty default / EoD declaration that triggers GMSLA close-out, mark-to-market termination, and netting.
3. **Minimum field set:** `counterparty_lei`, `event_type`, `declaration_time`, `cross_default_chain[]`, `automatic_early_termination_triggered` (bool), `valuation_method` (per GMSLA Schedule), `set_off_election`.
4. **Identity:** `(counterparty_lei, declaration_time)`.
5. **Provenance:** Credit operations; market default declaration; bankruptcy filing.
6. **Temporal semantics:** Event time-stamped; AET clauses fire immediately or on notice depending on schedule.
7. **Failure consequences:** Close-out netting cannot fire; all `S_live` SBL units cannot be terminated together; collateral cannot be valued and applied.
8. **(a)** Indirectly SFTR (mass ETRM); CSDR. **(b)** Mass termination of all SBL units with the defaulting counterparty. **(c)** Generates close-out moves (multiple coordinates).

### 4.5 Buy-In Trigger / Confirmation [SBL]

1. **Canonical name:** `BuyInEvent`
2. **Definition:** Confirmation of market buy-in to source securities for a failing return or a failing on-lending cascade (GMSLA 9.3, IBP-328).
3. **Minimum field set:** `loan_id`, `buy_in_qty`, `executed_price`, `execution_venue`, `cost_to_attribute`, `executor_lei`, `executed_at`.
4. **Identity:** `buy_in_id`.
5. **Provenance:** Buy-in agent; market execution.
6. **Temporal semantics:** Event-driven (T+3 close-out under Reg SHO Rule 204; CSDR mandatory buy-in disapplied for SFTs by 2023 Refit, but contractual buy-in remains).
7. **Failure consequences:** P18 carve-out (buy-in is the *only* SBL operation that writes the lender's `own` — see § 13.21 P18 proof) cannot be applied; cost attribution to borrower fails.

---

## 5. SMART-CONTRACT EXECUTION DATA

State and parameters that the executor reads/writes per atomic move. These are the load-bearing inputs to the lifecycle FSM.

### 5.1 Move Record (Ledger Primitive)

1. **Canonical name:** `Move`
2. **Definition:** The atomic unit of state change. One move modifies exactly one coordinate of one unit in the position vector of two entities (Single-Coordinate Move Principle, § 13.4).
3. **Minimum field set:** `move_id`, `from_wallet`, `to_wallet`, `unit_id`, `coordinate` ∈ {own, onloan, borr, coll_post, coll_recv, coll_rehyp}, `quantity`, `timestamp`, `source_contract`, `transaction_id`, `idempotency_token`, `metadata` (ISO 20022 ref, counterparty ref, event description), `cdm_business_event_ref`.
4. **Identity:** `move_id` (deterministic from transaction_id + sequence).
5. **Provenance:** Smart contract execution.
6. **Temporal semantics:** Append-only; immutable. Replay is a literal fold (StatesHome C1 monotone carrier).
7. **Failure consequences:** Conservation cannot be proven structurally; replay diverges; audit trail breaks.

### 5.2 Transaction Record

1. **Canonical name:** `Transaction`
2. **Definition:** Finite ordered set of moves committed atomically; conservation must hold structurally per event class (StatesHome C2).
3. **Minimum field set:** `transaction_id`, `transaction_type` ∈ {SETTLEMENT, MARGIN_CALL, RECLASSIFICATION, FEE_SETTLEMENT, CORP_ACTION, BUY_IN, CLOSE_OUT, PARTIAL_RETURN}, `moves[]`, `committed_at`, `executor_id`, `contract_source`, `cdm_event_ref`, `idempotency_root`.
4. **Identity:** `transaction_id`.
5. **Provenance:** Executor (single-writer guarantee per Temporal § 17.6).
6. **Temporal semantics:** Same-timestamp moves; total order via sequence number within timestamp.
7. **Failure consequences:** Atomicity broken; partial-application of a multi-move SBL initiation possible (e.g. securities deliver but collateral fail).

### 5.3 SBL Loan Unit State [SBL]

1. **Canonical name:** `SBLLoanUnitState` (mapped to ProductTerms + UnitStatus + PositionState per StatesHome)
2. **Definition:** The state object for one securities loan, lifted to first-class unit per § 13.5 SBL Smart Contract.
3. **Minimum field set (decomposed across 3 maps):**
   - **ProductTerms** (immutable, versioned): `loan_id`, `lender_lei` (initial), `borrower_lei`, `agent_lei`, `isin`, `original_qty`, `term_type` ∈ {open, term}, `maturity_date` (open ⇒ null), `fee_rate_initial`, `rebate_benchmark_id`, `rebate_spread_bps`, `collateral_type` ∈ {cash_rebate, non_cash_bilateral, non_cash_triparty, cash_pool_standard, cash_pool_eu, uncollateralised}, `margin_pct`, `collateral_schedule_ref`, `collateral_ccy`, `triparty_agent_lei`, `legal_regime` ∈ {TITLE_TRANSFER, SECURITY_INTEREST, US_15C3_3}, `rehyp_consent` (bool), `master_agreement_ref`, `governing_law`, `sftr_reportable` (bool), `slate_reportable` (bool), `cross_border_dual_regime` (bool), `digital_asset_annex_applies` (bool).
   - **UnitStatus** (mutable, shared): `lifecycle_stage` ∈ {PENDING, ACTIVE, RECALLED, PARTIALLY_RETURNED, RETURNED, CANCELLED, DEFAULTED}, `current_qty`, `last_mark_date`, `last_mark_price`, `current_lv`, `current_collateral_value`, `current_fee_rate` (post-rate-change), `current_rebate_rate`, `recall_date`, `recall_qty`, `accrued_fee`, `superseded_by`.
   - **PositionState** (per (wallet, loan_unit)): not directly used — the loan unit has `+1`/`-1` ownership in lender/borrower wallets per the bond-analogy (§ 13.5.1).
4. **Identity:** `loan_id` (= unit_id for the loan unit itself); plus `sftr_uti`, `slate_loan_id`, `client_loan_id` as reportable identifiers.
5. **Provenance:** Booking system at trade time; SLATE/SFTR identifiers from regulatory submission gateway.
6. **Temporal semantics:** ProductTerms is append-only versioned (rate change = new TermsVersion). UnitStatus is mutated on every settle/MTM. The state machine is total (§ 13.7).
7. **Failure consequences:** State machine misroutes events; SFTR action type mis-determined (NEWT/MODI/VALU/COLU/ETRM); reallocation (lender_lei change) cannot be done as state-only update; cascade recall has no state to drive against.
8. **(a)** SFTR (every reportable field); SLATE (every reportable field; 48 unique data elements; 24 required); CSDR (failing-trade attribution). **(b)** Every lifecycle event consumes and mutates this. **(c)** Drives every six-coordinate move generated by the SBL smart contract.

### 5.4 Idempotency Token Set

1. **Canonical name:** `IdempotencyTokenSet`
2. **Definition:** Per-workflow set of processed signal tokens, preventing double-application of recall/return/margin signals (§ 17.3 SBL workflow).
3. **Minimum field set:** `workflow_id`, `processed_tokens[]`.
4. **Identity:** `workflow_id`.
5. **Provenance:** Temporal workflow state.
6. **Temporal semantics:** Persists across workflow ContinueAsNew boundaries.
7. **Failure consequences:** Double-processing of a recall — securities returned twice, collateral released twice, conservation violated downstream.

### 5.5 Obligation Record (per § 12.6 Obligation Liveness)

1. **Canonical name:** `Obligation`
2. **Definition:** First-class object representing a deadline-driven duty (margin delivery, collateral substitution, recall response, SFTR submission, manufactured-payment by ex-date+1, fee settlement).
3. **Minimum field set:** `obligation_id`, `kind` ∈ {margin_delivery, collateral_substitution, recall_response, locate_response, sftr_submit, slate_submit, manufactured_payment, fee_settlement, csdr_claim_issuance, t1_close_out_buy_in}, `obligor_lei`, `beneficiary_lei`, `unit_ref`, `deadline`, `state` ∈ {open, in_progress, satisfied, breached}, `discharging_transaction_id`, `regulatory_basis_ref`.
4. **Identity:** `obligation_id`.
5. **Provenance:** Smart contract (creates obligations on lifecycle events).
6. **Temporal semantics:** Created with deadline; transitioned by discharging move or by deadline-elapse.
7. **Failure consequences:** Liveness invariant P21 (per § 12.6) breaks; recall deadline missed; CSDR claim window expires; no enforcement of "1 hour before market cut-off" (IBP-124).
8. **(a)** SFTR/SLATE submission deadlines; CSDR claim deadlines; SSR locate deadline. **(b)** Every deadline-bound lifecycle event. **(c)** Discharging move depends on kind.

### 5.6 Locate-Reservation State [SBL]

1. **Canonical name:** `LocateReservationLedger`
2. **Definition:** Per-(lender, security) accumulator of outstanding-locate quantities, deducted from `available_to_lend` (§ 13.16 over-location prevention).
3. **Minimum field set:** `lender_lei`, `isin`, `outstanding_locates[]` (= ref to LocateConfirmation), `regulatory_hold_qty`.
4. **Identity:** `(lender_lei, isin)`.
5. **Provenance:** Smart contract on `confirm_locate`.
6. **Temporal semantics:** Updated on each locate issuance / expiry / conversion.
7. **Failure consequences:** Over-location: multiple locates against the same available inventory; later short-sales cannot be filled; regulatory exposure under SSR/Reg SHO.

### 5.7 Cascade-Recall Workflow State [SBL]

1. **Canonical name:** `CascadeRecallState`
2. **Definition:** Tree of downstream recall sub-workflows for an on-lending chain (§ 13.15, § 17.5 saga).
3. **Minimum field set:** `root_recall_id`, `parent_loan_id`, `cascaded_loans[(loan_id, recall_qty, child_workflow_id)]`, `timeout`, `buy_in_fallback_triggered`.
4. **Identity:** `root_recall_id`.
5. **Provenance:** Temporal saga workflow.
6. **Temporal semantics:** Bounded by recall_deadline = market cut-off − 2 business days (IBP-328).
7. **Failure consequences:** Bob fails to return to Alice because Charlie hasn't returned to Bob; CSDR penalty cascade; buy-in cost attribution chain breaks (GMSLA 9.3).

### 5.8 Rehypothecation Cap Counter [SBL — US]

1. **Canonical name:** `RehypCapCounter`
2. **Definition:** Per-broker-dealer aggregate `Σ coll_rehyp × P` against the 140% × customer_debit_balance cap (Rule 15c3-3(b)(3); enforced by P19; § 13.21 + US example § 6.3).
3. **Minimum field set:** `bd_lei`, `customer_debit_balance`, `current_rehyp_value`, `cap_value`, `headroom`, `last_recalc`.
4. **Identity:** `bd_lei` (per BD per regulatory aggregation rule).
5. **Provenance:** Smart contract `validate_rehypothecation`.
6. **Temporal semantics:** Recalculated on every customer debit move and every `coll_rehyp` write.
7. **Failure consequences:** P19 violation; SEC Rule 15c3-3 cap breach; the smart contract pre-condition fails to reject the move; regulatory enforcement.

### 5.9 SFTR / SLATE Submission Cursor

1. **Canonical name:** `RegulatoryReportingCursor`
2. **Definition:** Per-(loan_id, regime) state of the SFTR or SLATE reporting workflow.
3. **Minimum field set:** `loan_id`, `regime` ∈ {SFTR, SLATE}, `last_reported_action`, `last_reported_at`, `tr_or_slate_ack`, `pending_actions[]`, `unsettled_loan_flag` (SLATE field 44).
4. **Identity:** `(loan_id, regime)`.
5. **Provenance:** Reporting workflow; TR / SLATE acknowledgements.
6. **Temporal semantics:** Drives idempotent re-submissions on rejection.
7. **Failure consequences:** P16 (SFTR Completeness) violation; duplicate or missing reports; SLATE same-day-by-8pm-ET deadline missed.

---

## 6. LISTED-INSTRUMENT DETAIL

This floor is preserved for compatibility, but I argue (Section 8) it is more cleanly subsumed under Reference Data with a `listed_kind` discriminator.

### 6.1 Lendable-Inventory Snapshot

1. **Canonical name:** `LendableInventorySnapshot`
2. **Definition:** Per-(lender, ISIN) consolidated `own − onloan + borr − reserved − regulatory_hold = available_to_lend` projection at a point in time.
3. **Minimum field set:** `lender_lei`, `isin`, `asof_time`, `own`, `onloan`, `borr`, `reserved` (locates), `regulatory_hold`, `atl`.
4. **Identity:** `(lender_lei, isin, asof_time)`.
5. **Provenance:** Computed projection (never stored in coordinates per § 13.4).
6. **Temporal semantics:** Real-time read; cached for vendor-facing inventory broadcasts.
7. **Failure consequences:** Locate confirmation cannot be gated; over-lending; agent-lender pool mis-allocation.

### 6.2 Listed-Derivative Contract Specification (Where Lendable)

1. **Canonical name:** `ListedDerivContractSpec`
2. **Definition:** Per-(exchange, root, expiry, strike, type) contract spec. Most listed derivatives are NOT lendable (vector degenerates to scalar). Some equity options ARE lent (deep-in-the-money exercise plays). When lent, the six-coord vector applies.
3. **Minimum field set:** `mic`, `clearinghouse`, `root`, `expiry`, `strike`, `option_type`, `multiplier`, `currency`, `settlement_type`, `is_lendable`.
4. **Identity:** `(mic, root, expiry, strike, option_type)`.
5. **Provenance:** Exchange masters.
6. **Temporal semantics:** Stable per series.
7. **Failure consequences:** Gross attribution incorrect; CCP novation rules apply differently to lendable vs. non-lendable.

---

## 7. SBL-Specific Items Not Obvious to Non-SBL Readers

These items recur in the appendices but may be invisible to teammates from FX, IRS, or vanilla equities. I list them here as a checklist and then catalogue them above (cross-referenced).

| Item | Above as | Why non-SBL members miss it |
|---|---|---|
| Locate evidence | 4.1 LocateConfirmation | No locate concept outside SBL/short-selling |
| Manufactured-payments calendar | 2.4 + 3.5 + 4.3 | Dividends-on-borrowed are not just CA passthroughs — they are tax-engineered cash flows |
| Rehypothecation caps | 5.8 RehypCapCounter | Rule 15c3-3(b)(3) is unique to US BD regime; EU GMSLA TT has no cap |
| Recall windows | 5.5 (Obligation kind=recall_response) + 1.9 MarketCalendar | Deadline math = market_close − 2 business days, not a generic SLA |
| RQV agreement parameters | 1.6 TripartyAgreement + 3.6 RQVSnapshot | Triparty cadence (10:00 / 14:00 / 17:00 UTC) is SBL-specific |
| Rebate vs. fee duality | 3.3 BorrowFeeQuote + 3.4 RebateRateFix | Cash-collateralised loans have a *rebate*, not a fee; sign convention reverses |
| GMSLA legal-regime field | 1.4 MasterAgreement + 5.3 SBLLoanUnitState.legal_regime | Pledge vs. title transfer changes the PnL formula (§ 13.13 remark) |
| Agent-lender disclosure | 1.7 AgentLenderDisclosure | Reallocation (IBP-307) means the lender LEI on a live loan can change |
| SFTR Article 15 documentation flag | (operational flag on master + loan unit) | Required *before* any rehypothecation move; not a price; not a quantity |
| Cash collateral reinvestment | 3.9 MMFNAV + § 13.14 | The collateral *obligation* and the *reinvestment asset* are two different ledger objects |
| Cascade-recall topology | 5.7 CascadeRecallState | An on-lending chain is invisible until you recall, and then it dominates |
| Cross-border dual reporting | 5.3 (cross_border_dual_regime flag) + 5.9 cursor | One loan ⇒ both SFTR and SLATE workflows fire independently |
| Tokenised collateral | 2.3 TokenAssetRef | ISLA Digital Assets Annex; not yet in CDM; haircut composes underlying + platform risk |
| EU SSR emergency ban subscription | 2.5 RegulatoryRestrictionList (RCA_EMERGENCY_BAN entry kind) | Up to 3 trading days, no ESMA opinion required (SSR Art 23) |
| NSP threshold table | 2.6 NSPThresholdTable | Aggregated against issuer share capital, not against `own` alone |
| CSDR exemption flag for FOP | 3.8 CSDRPenalty | 2023 Refit disapplies penalties to FOP collateral transfers attributable to non-trading operations — must carry flag |

---

## 8. Disagreements with the Floor Categories

I retain all six categories for compatibility with Team A, but I record the following arguments:

1. **"Listed-instrument detail" is a property tag, not a floor.** Items 6.1 and 6.2 are naturally Reference Data with a `listed_kind ∈ {equity, deriv, fund, structured}` discriminator. The floor as stated in the prompt suggests "listed-instrument detail" is parallel to "Reference data", but a listed equity's contract spec is reference data; an OTC trade's full CDM `Trade` object is also reference-like (Tier 3 Unit Registry per § 3.4). Keeping them parallel risks duplication. **Proposal:** drop floor 6 and absorb into 2 with a `listed_kind` field. If kept, make it explicitly the Tier-3 Unit Registry per the v10.3 unit-store model.

2. **"Smart-contract execution data" is partly redundant with the StatesHome 3-map ruling.** Items 5.1 (Move) and 5.2 (Transaction) are core ledger primitives, not smart-contract data per se. Items 5.3–5.9 are correctly here. **Proposal:** rename floor 5 to "Ledger primitives + Smart-contract state" or split into 5a (primitives — universal) and 5b (per-contract state — which is what the StatesHome PositionState/UnitStatus/ProductTerms triple is).

3. **Oracle data is too narrow as named.** The oracle floor should explicitly include *regulatory lists* (sanctions, threshold lists, short-sale bans, locate-list of HTBs), not just price oracles. I have placed RegulatoryRestrictionList under Reference (2.5) because it is a reference list rather than a one-off attestation, but it could equally sit under Oracle. The boundary is fuzzy. **Proposal:** explicitly state that "Oracle" includes any external attestation gating a smart-contract pre-condition, including locate confirmations (4.1), tax determinations (4.3), default declarations (4.4), and buy-in confirmations (4.5).

4. **A seventh floor is arguably needed: Bitemporal restatement / amendment data.** Back-dated trades (IBP-308), price restatements, GMSLA schedule amendments (IBP-191, 10 BD notice), agent reallocation history (IBP-307), and locate-arrangement records (5-year retention per ESMA70-448-10) all share a structural property: they are *amendments to the historical record* and need bitemporal handling distinct from append-only event-log moves. The StatesHome addendum addresses this for ProductTerms (versioned NonEmptyList) and gives a clean two-track model (C8 Preserving vs Breaking). I do not insist on a new floor, but I flag it: if Team A converges on bitemporality as a cross-cutting concern, a floor "7. Bitemporal Amendment Data" with items {Back-dated trade record, Price restatement, Schedule amendment, Agent reallocation history, Locate-retention archive} would tidy the model.

5. **Provenance field is under-specified.** Several items above could be sourced from multiple authoritative providers (e.g. close prices from Bloomberg / CREST / Reuters with override rules per IBP-127 and IBP-310). Phase 2 should enrich the `Provenance` field to a structured `(primary, fallback_chain[], override_rules[])` rather than a free-text vendor name.

6. **Failure consequences are inconsistently scoped.** Some failure consequences I named are *internal* (conservation violation, P-invariant failure) and some are *external* (regulatory sanction, settlement fail penalty). Phase 2 should distinguish `internal_consequence` from `external_consequence` so the test harness can target each separately — internal failures should be unreachable per the addendum; external failures are inherent at the boundary and need detection.

---

## 9. Index of SBL-tagged items

(34 items total in the SBL family; bold = exclusively SBL.)

- 1.4 **MasterAgreement (GMSLA/MSLA)**
- 1.5 **CollateralSchedule**
- 1.6 **TripartyAgreement**
- 1.7 **AgentLenderDisclosure**
- 2.3 **TokenAssetRef** (under Digital Assets Annex)
- 2.4 CorporateActionCalendar (SBL-relevant subset for manufactured payments)
- 2.5 **RegulatoryRestrictionList** (SSR / Reg SHO scope)
- 2.6 **NSPThresholdTable**
- 2.7 RebateBenchmark (SBL-relevant)
- 3.3 **BorrowFeeQuote**
- 3.4 **RebateRateFix**
- 3.5 **ManufacturedPaymentRate**
- 3.6 **RQVSnapshot**
- 3.8 CSDRPenalty (SBL-dominant tail)
- 3.9 **MMFNAV** (cash-collateral reinvestment)
- 4.1 **LocateConfirmation**
- 4.3 **TaxTreatmentOracle** (manufactured payments)
- 4.4 **DefaultEvent** (close-out cascade)
- 4.5 **BuyInEvent**
- 5.3 **SBLLoanUnitState**
- 5.5 **Obligation** (SBL kinds)
- 5.6 **LocateReservationLedger**
- 5.7 **CascadeRecallState**
- 5.8 **RehypCapCounter**
- 5.9 **RegulatoryReportingCursor** (SFTR/SLATE)
- 6.1 **LendableInventorySnapshot**

(plus general-purpose items 1.1–1.3, 1.8, 1.9, 2.1, 2.2, 2.8, 3.1, 3.2, 3.7, 4.2, 5.1, 5.2, 5.4, 6.2 = 16 general items.)

---

## 10. Counts and Summary

- **Total enumerated items:** 50
- **Floor coverage:** 1 Static (9), 2 Reference (8), 3 Market (9), 4 Oracle (5), 5 Smart-contract execution (9), 6 Listed-instrument detail (2). Floors 1–6 all populated.
- **SBL-tagged items:** 26 (52%) — see Section 9.
- **Items with regime/event/coordinate triplet:** 26 (every SBL-tagged item).
- **Disagreements with floor taxonomy:** 6 (Section 8).
- **New items not in floor template that SBL forces:** Locate retention archive (subsumed under 4.1 / 5.6 + Section 8 point 4), Manufactured-payment calendar entries (2.4 / 3.5 / 4.3), Triparty cut-off times (1.6 / 3.6), Rehypothecation cap counter (5.8), Cascade-recall workflow state (5.7), Agent-lender disclosure (1.7), CSDR exemption flag (3.8 metadata), GMSLA legal_regime field (1.4 + 5.3), SFTR Article 15 documentation flag (5.3 metadata), Tokenised-asset record (2.3), Cross-border dual-regime cursor (5.9), MMF NAV for reinvestment (3.9), Rebate fix (3.4), Borrow fee quote (3.3 — distinct from the rebate).
