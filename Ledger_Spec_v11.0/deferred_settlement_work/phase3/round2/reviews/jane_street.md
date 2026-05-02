# R2 Closure Review — Jane Street CTO

## Verdict
**ACCEPT_WITH_CHANGES** — Pareto NOT YET reached, but distance is small.

The architecture is sound and the substantive work has been done. v2 closes 4 of 5 R1 blockers cleanly; B-1 is structurally addressed but the framing rests on a sleight-of-hand the proposal does not own up to. Of 7 R1 majors, 5 are closed, 2 are mitigated with documented trade-offs (M-3 honestly downscoped; M-4 not addressed at the depth I asked for). Two new minor regressions appeared in §3.X (the SELL worked example has a paragraph of internally muddled valuation prose) and §10.7 (a numeric inconsistency that an on-call recon engineer will read at 3am and trip on). Neither is a release-blocker. One unmitigated major remains: **M-4 (broker virtual semantics)** has been answered in surface form — the v2 contras are now `csd_virtual` mirrors rather than `w_GS_broker` directly — but the wire-recall / partial-credit semantics I asked for are nowhere in §3.5 / §3.X.4 / §6.5.3.

If the team patches §3.6, §3.X math prose, §10.7 storage numbers, and §3.5/§6.5.3 wire-recall semantics, this is shippable. None of those is a re-architecture. Pareto in R3 is realistic.

## R1 closure check

| R1 Finding | Status | Evidence |
|---|---|---|
| **B-1** §3 conservation | **MITIGATED** (not fully CLOSED) | §3.6 tables sum to zero, but only because they are explicitly tabulating *deltas from pre-trade* (footnote line 386 "Reading: Δ from pre-trade"). Absolute `Q(u) = Σ_w w_t(u) = 0` per v10.3 P1 is NOT shown — at T+2⁺ finality the absolute USD sum across the constant universe `{w_us, w_PS, w_JPMC_nostro_mirror[GS]}` is `995,000 + 0 + 5,000 = 1,000,000`, NOT zero. The pre-existing 1M in `w_us` has no contra in the displayed universe. Acceptable IF the proposal explicitly stated "pre-trade `w_us.own(USD) = 1,000,000` was seeded via a v10.3 inception move from a `w_issuer_USD`; the issuer contra holds -1,000,000 outside this example's scope." It does not. The footnote "treating the pre-trade nostro float as a real `w_us` cash balance (no flow through GS)" is a hand-wave, not a citation of the v10.3 inception-move discipline. **Fix:** one sentence in §3.1 or §3.6 naming the issuer-virtual contra and citing v10.3 §2 lines 206–239. |
| **B-2** inflight wallets / recon identity | **CLOSED** | §4.1.5 names `inflight_out` / `inflight_in` as **projections** over `L_15` rows with explicit predicates (lines 620–638). Witness-field columns (`wire_dispatch_witness`, `cpty_dispatch_witness`, `csd_finality_witness`) are pinned on the `L_15.Obligation` schema. The recon identity at §4.1 is parametric-explicit. The "inflight is non-ledger state smuggled into the identity" trap is properly defused — `inflight_*` is a *projection function over L_15 rows in non-terminal states with witness present but finality absent*, which is exactly the right call. |
| **B-3** "constant-time" oversell | **CLOSED** | §4.3 (lines 664–682) downgrades the claim: "constant-time per (w, ccy)" with explicit complement that "`inflight_out`/`inflight_in` projections add a second scan over `L_15`," with the indexing pinned in §10.7.4 (`(wallet_id, unit, lifecycle_state)` hash index, line 1503). The "no replay over MoveStream" framing is preserved as the actual win. Acceptable — though the absolute throughput target on representative data I asked for is still absent (it's listed as part of PO-8 / TLA+ work in §15.5). I won't block on this. |
| **B-4** per-leg storage at 10^7 trades/day | **CLOSED with one numeric sloppiness** | §10.7.1 cites 10^7 trades × 2 legs × 365d × 7y = ~5×10^10 obligation rows; tier strategy (hot/warm/cold) is laid out; partitioning is `(year_month(intended_settlement_date), hash_prefix_8(business_event_id))` — exactly what I recommended. **However:** §10.7.1 says "At 50 bytes/row plus indexes, ~2.5 TB of L_15 storage." 5×10^10 rows × 50 bytes = 2.5×10^12 bytes = **2.5 TB**, fine — but the "plus indexes" qualifier and the §10.7.4 four indexes (each adding ~20-40% overhead in B-tree cases) puts this at 5–8 TB hot+warm of L_15 alone, *before* envelope payloads. The "10–15 TB hot+warm" in line 1474 is plausible only if envelope blobs are deduplicated across tx_ids (one envelope, many `dedup_key` references) — the spec doesn't say they are. **Fix:** clarify whether envelope blobs are stored once-per-source-message or once-per-`(tx_id, leg)`. |
| **B-5** tx_id collision | **CLOSED** | §6.5.1 (lines 1000–1017): `tx_id = hash_jcs(business_event_id, attempt_seq)` with `business_event_id` content-addressed on stable upstream fields (`exec:venue_mic:exec_id:leg_label` etc.), `attempt_seq` carried across ContinueAsNew via the §6.5.6 payload schema, never `run_id`. JCS canonicalisation pinned. Idempotency story rooted in `L_13.tx_id` primary key. This is exactly the pin I asked for. |
| **M-1** PS/PSS ↔ GPM coordinate confusion | **CLOSED** | §0.2 (lines 71–81) explicitly: three wallet classes only (`real`, `cpty_virtual`, `csd_virtual`); cpty_virtual stores a *signed* `own` on a scalar unit; "side handling: payable vs receivable is sign, not class"; explicit collapse of `PS_payable`/`PS_receivable` v1 forms. §2.2 lines 175–189 pin storage as signed scalar with disclosure-layer gross projections. The GPM 6-tuple is not invoked for cpty_virtual. The schema is now honest. |
| **M-2** 18 invariants / TLC budget | **CLOSED** | §11 prunes to 10 invariants (DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS12, DS17, DS18 — that's actually 11 by my count, not 10, but the team is consistent in the §11 type-vs-runtime decomposition table at lines 1715–1727 which lists 11; the §15 closure mentions "10 invariants" twice). v10.3 restatements (DS2, DS5, DS6, DS8, DS14, DS15, DS16) demoted to §11.A as "restated, not reasserted as new" with parent reference. DS13 folded into DS3. DS11 split into DS11a (conservation) + DS11b (monotonicity). The folds I called for are done. **Minor inconsistency:** §15.6 says "10 invariants"; §11 lists 11 (DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS12, DS17, DS18). Pick one. I am not going to block on this. |
| **M-3** type-discipline migration cost | **MITIGATED with honest trade-off** | §12.1 scopes v11.0 core to 5 items (phantom wallet class; PairedObligation; lifecycle closed sum; failure_reason closed sum; TradeDate/SettleDate newtypes); §12.2 lays out a 6-week / 1.5-engineer plan; §12.3 brackets the rest (smart constructor with 14 rejections; phantom accounting basis; total step migration; fx_discharge_state) for v12 RFP. This is the honest plan. The 14-week / 1.5-engineer fantasy is gone. **However**, even the 6-week plan does not address (i) backward compatibility with persisted `lifecycle_stage : string` rows in the bitemporal store; (ii) the CDM 6.0 string-deserialisation boundary; (iii) build / CI cost of `-warn-error +partial-match` across the tree; (iv) migration of existing test surface. I called these out in R1; v2 is silent. The trade-off is acknowledged ("Stages 1–3 are type-additive; Stage 4 removes dead code" — line 1883) but the persisted-state migration is the silent rock that grinds these timelines down. I will not block, but **flag this for R3:** add a one-paragraph "what the 6-week plan does NOT cover" annex listing (i)–(iv) with explicit owner. |
| **M-4** `w_GS_broker.own` semantics / wire-recall | **NOT CLOSED** | The surface form is fixed: §3.5 now drains into `w_DTC_depot_mirror[GS]` and `w_JPMC_nostro_mirror[GS]` (csd_virtual), not into `w_GS_broker` directly. The renaming is correct. **But the substance of the R1 finding is unaddressed:** wire-recall semantics, partial-credit at the beneficiary bank, the distinction between "JPMC debited our nostro per camt.054" and "GS actually received the wire," and the Herstatt-window per-leg discharge-witness discipline. §3.5 still treats `camt.054` as the cash leg's discharge witness without specifying that this attests to *our debit*, not *GS's credit*. §6.5.3 disambiguates DvP-L / DvP-S / DvP-E but does not name the wire-recall failure mode. §10.11 mentions Herstatt at the disclosure level (CRR Art 442) but does not connect the `csd_virtual` mirror semantics to "what happens when our wire goes out, JPMC debits us, and the beneficiary bank rejects the credit." The DS10 statement in §11 (line 1667) is honest that "Framework does not eliminate Herstatt risk; it names, quantifies, routes compensation" — fine — but the worked example for it is missing. **Fix:** add a §3.X.6 subsection or §6.5.3 paragraph naming the failure mode and showing the FSM transition (the cash leg should go `Instructed → PartiallySettled → Failed(BeneficiaryReject)`, with the `w_JPMC_nostro_mirror[GS]` short by 5,000 until a wire-recall produces a counter-camt.054 reversing the debit). |
| **M-5** late corrections / cross-correction / regulatory-already-reported / correction-of-correction | **CLOSED** | §10.9 (lines 1531–1601) addresses all three explicitly: §10.9.1 lists "cross-correction of a prior CORRECTION (with stricter four-eyes)" and "regulatory-already-reported correction (with regulatory-amendment four-eyes)" as permitted; §10.9.3 specifies required fields for each (CROSS_CORRECTION needs `affected_tx_ids` + `scope_attestation`; REG_ALREADY_REPORTED needs `reg_amendment_handler ∈ {MIFIR_AMEND | EMIR_AMEND | SFTR_AMEND}` + `amend_reference`; CORRECTION_OF_CORRECTION needs `prior_correction_tx_id` + `audit_committee_attestation`). §10.9.6 SOX implications: ">10 CORRECTIONs/month from same trader = control-environment red flag"; "Any CORRECTION_OF_CORRECTION = automatic audit committee review." This is the right level of detail. |
| **M-6** manual override / FSM `MANUAL_DISCHARGE` | **CLOSED** | §5.4 (lines 894–911): explicit `Override` envelope with `requester_lei != approver_lei` check, `approver_role ∈ {OPERATIONS_HEAD, RISK_OFFICER, CFO_DELEGATE}`, mandatory `justification`, `evidence_ref`. §10.9.4 confirms "Manual override on a `Pending|Instructed|PartiallySettled|Failed` obligation transitioning to `Compensated` is a CORRECTION with full four-eyes per §5.4. It does NOT emit anti-moves; it transitions the lifecycle state and registers compensating evidence as the discharge witness." This is the discipline I called for. The `attestation_class ∈ {CRYPTOGRAPHIC, MANUAL}` distinction I asked for is implicit in §4.5.1's `attestation_kind: { sese.025 | camt.054 | sese.024 | camt.053 | affirmation | corp_action_ex_date | manual_override | ... }` enum (line 731) — could be tighter (the literal `attestation_class` field would help downstream consumers) but acceptable. |
| **M-7** block-and-allocation chains | **CLOSED** | §7.6 (lines 1218–1260): block trade B → allocation event A spawning per-fund children. Block obligation transitions to `Compensated (kind = ALLOCATION_SPLIT)`; per-child obligations spawn with `parent_obligation_id` reference; per-child FSMs proceed independently; allocation-correction path (anti-moves under four-eyes) specified. §7.6.3 acknowledges the two settlement-day discharge modes (one-block-message vs per-allocation-message) and absorbs both. This is the right structural placement (parallel worked example to the standard buy, not a corner case). Acceptable. |

## R1 minor closure (m-1..m-8)

| R1 minor | Status | Evidence |
|---|---|---|
| m-1 C11 capability split | **CLOSED** | §2.1 row 2 (line 170) splits writers: "`apply_trade_move` at T (initial credit/debit); same handler at T+N (drain)." §6.5.8 names the SettlementSaga as the writer of `o.state` and finality moves. Acceptable. |
| m-2 PnL base currency | **NOT explicitly addressed** | §3.7 still uses `P_T(USD) = 1.0000` without an explicit base-currency declaration. Footnote in §3.1 line 250 says "Decimal discipline: prices D_8" but nothing names "USD-base book." Trivial; not blocking. |
| m-3 CSDR penalty obligation_id | **NOT addressed** | The hash recipe still does not encode `failing_party_lei`. §6.3 (line 952 onwards in the lifecycle context) inherits v1 form. Trivial; minor. |
| m-4 PS_receivable sign convention | **CLOSED** | §0.2 lines 71–81 + §2.2 lines 175–189 pin the sign convention canonically in one place. The convention is reused in §3, §3.X, §4. Excellent closure. |
| m-5 retrograde edges Failed → Instructed | **CLOSED via reformulation** | §5.2 transition table (line 854): `Failed → BoughtIn | Compensated` — no retrograde to Instructed. Reading my R1 again, I conflated re-instruction-post-fail with re-Pending. v2's Failed-as-terminal-conditional with explicit BuyIn / Compensated routes is the correct closure. |
| m-6 DS5 multi-permutation replay | **CLOSED** | §6.5.5 (lines 1082–1097) signal-handler commutativity table with explicit cases including non-commuting deterministic precedences (terminal absorbs; contradictions quarantine). This is now testable and documents what DS5 actually means. PO-8 TLA+ is owed; this is the design pin that makes PO-8 tractable. |
| m-7 smart constructor case 5 | **DEFERRED to v12 RFP** | §12.3 explicitly defers the 14-rejection smart constructor. Honest; acceptable. |
| m-8 per-counterparty vs per-instruction PS keying | **CLOSED** | §0.2 line 76 + §2.2 line 177 commit to per-counterparty: "For each `(real_wallet w, counterparty cpty, unit u)`, **one** virtual wallet." The call is made and owned. Excellent. |

## New blocking issues introduced (if any)

**None blocking.** The substantive architecture is correct.

## Remaining unmitigated major issues

### M-2.N1 — §3.X SELL valuation prose is internally muddled (NEW MAJOR — minor regression)

Lines 470–497 of §3.X.3 read like a stream of consciousness:

```
PnL_{T+1} = V_{T+1} - V_T = 0      (we have no XYZ; we have +5,000 cash claim)

Wait — at T+1, the receivable `w_PS[us,GS,USD] = -5,000` is a claim, not yet cash;
valuation must include it.
```

The `Wait —` mid-derivation is unprofessional in a load-bearing artifact. The author is *thinking out loud* in the ledger spec. Then the prose flips between two valuation conventions ("for sell-side, the payable on XYZ is what *we owe to deliver* and reduces V by `100 × $50`; the receivable in cash adds `+5,000`") before settling on the formula at line 487. A junior engineer reading this at 2am during an incident will not be able to tell which valuation convention is canonical.

The arithmetic does work out — V_{T+1} = 1,005,200 with PnL = +$200, which is the right answer for "short XYZ at $50, mark to $48, gain $200" — but the *path to it* is debugging-by-trial-and-error written into the spec. Compare to §3.7 BUY's clean three-line derivation.

**Fix.** Rewrite §3.X.3 as: state the valuation function once (the formula at lines 487–490 is correct: `V_t = w_us-value + (-w_PS[us,GS,XYZ].own · P_t(XYZ)) + (-w_PS[us,GS,USD].own · 1)`); compute V_T, V_{T+1}, V_{T+2} directly; declare PnL. No `Wait —`. No flip-flop. The right thinking belongs in a worked-example commentary, not in the canonical artifact.

**Why major.** §3 is the load-bearing concrete artifact; §3.X is the SELL companion. Both must be obvious code-as-prose. The current §3.X.3 prose is *less obvious* than v1 was on the BUY side, even though the math is right. This is a prose regression in the load-bearing block.

### M-2.N2 — §3.6 absolute conservation framing not connected to v10.3 inception-move discipline

Restated from B-1 above: the §3.6 conservation tables sum *deltas* to zero, not absolute balances. v10.3 P1 says `Q(u) = Σ_w w_t(u) = 0` over **all** wallets at every time, with opening balances seeded by inception moves from issuer-virtual contras. The v2 footnote "treating the pre-trade nostro float as a real `w_us` cash balance (no flow through GS)" papers over this without citing v10.3's inception-move discipline.

**Why major.** A reader who scans §3.6 and §11.A's "Conservation `Σ_w w_t(u) = 0` corollary of §7.5" will reasonably expect §3.6's tables to *demonstrate* the corollary on the worked example. They do not. The "Δ from pre-trade" reading is a genuinely correct projection (transactions preserve Q(u), so sum-of-deltas = 0 if-and-only-if Σ_w w_t(u) = constant), but the proposal does not connect the dots.

**Fix.** One paragraph in §3.6 (or §3.1 setup) stating: "Pre-trade `w_us.own(USD) = 1,000,000` and `w_us.own(XYZ) = 0` are seeded by v10.3 inception moves from `w_issuer_USD` (with contra `w_issuer_USD.own(USD) = -1,000,000`) — not displayed in this worked example's universe. The constant universe shown here is the trade-local universe; absolute Q(u) closure is preserved by the inception-move discipline. The Δ-tables in §3.6 demonstrate the *trade*'s conservation contribution; absolute conservation is the corollary."

This is one paragraph. It bridges the §3 worked example, §7.5 Conservation Lifting Theorem, and v10.3 P1 cleanly. As-written, B-1 is **mitigated** but the bridge is missing.

### M-2.N3 — Wire-recall / per-leg discharge-witness substance unaddressed (carry-over from R1 M-4)

See M-4 row in the R1 closure table above. The surface rename (csd_virtual mirrors instead of `w_GS_broker.own`) is good but does not address the substantive R1 finding. **Fix:** §3.X.6 wire-recall worked example, or §6.5.3 paragraph naming the BeneficiaryReject failure mode and the FSM transition. Without this, the production team's first wire-recall incident exits the framework via an undocumented CORRECTION.

## Pareto judgment

- **Zero blocking?** YES — strictly speaking. B-1 is mitigated; M-2.N2 lifts it back up to "should-fix-before-Pareto" but it is not a re-architecture demand. All other R1 blockers are cleanly closed.
- **Zero unmitigated major?** NO — three remain (M-2.N1 prose regression in §3.X; M-2.N2 absolute-Q(u) framing missing; M-2.N3 wire-recall semantics carry-over). All three are 1-2 paragraph fixes; none requires re-architecture.
- **Any minor improvable without trade-off?** YES — m-2 (PnL base ccy declaration), m-3 (CSDR penalty hash needs `failing_party_lei`), invariant count inconsistency (§11 lists 11; §15.6 says 10).
- **Recommend Pareto declared?** **NO**, but on a tight margin. Recommend **R3 with bounded scope**: §3.6 paragraph (closes M-2.N2); §3.X.3 prose rewrite (closes M-2.N1); §3.X.6 or §6.5.3 wire-recall worked example (closes M-2.N3); the three minors (m-2, m-3, invariant count). All five fixes together: 1 person-day. Then declare Pareto. Do not let the margin slide.

## What v2 did well — explicit acknowledgment

- **§6.5 workflow specification.** The §6.5 block (lines 996–1134) is *exactly* the kind of artifact that earns its place. The commutativity table (§6.5.5) is the highest-leverage page in the document — a future on-call engineer can read it in 30 seconds and know which signal interleavings are deterministic and which quarantine. This is the test that catches the bug everyone writes once. Excellent work.
- **§4.5 attestation envelope.** JCS-canonical, Ed25519, dedup_key, schema_version, multi-source quorum, absence-of-finality protocol — all the pieces are there with concrete production discipline. The 3-of-3-tightening-via-`L_7^P.QuorumPolicy`-but-never-relaxable-below-2-of-2-by-config rule is the right call. This is well-engineered.
- **§10.7 storage.** Even with the numeric sloppiness flagged in B-4, the partitioning scheme (`year_month(intended_settlement_date), hash_prefix_8(business_event_id)`) is the right pragmatic call and aligns with the recon scan keys. Hot-warm-cold tiering is realistic.
- **§7.6 block-and-allocation.** Promoted to a first-class worked example (parallel to §3 standard buy). Allocation-correction via four-eyes anti-moves is the honest mechanism.
- **§10.9 CORRECTION policy.** The triple of cross-correction, regulatory-already-reported, and correction-of-correction is now spelled out with required fields, rejection conditions, and SOX implications. The "no correction-of-correction is a doctrine, not a mechanism" finding from R1 is properly resolved by *requiring* `audit_committee_attestation` rather than forbidding the operation.
- **§12 type design honest scoping.** The 14-week-1.5-engineer fantasy is gone; v11.0 core is 6 weeks for 5 items, with v12 RFP brackets for the rest. This is the kind of honest scoping that prevents week-12 stall.
- **§5.4 manual override.** Four-eyes with `requester_lei != approver_lei` rejection, named approver role, mandatory justification, evidence_ref. Production reality is now in the framework rather than exiting it via undocumented CORRECTIONs.

The substantive engineering is largely correct. The remaining work is editorial discipline and one missing worked example. Patch and ship.

## Recommendation

R3 with bounded scope. Five fixes, 1 person-day:
1. §3.6: paragraph connecting the Δ-table to v10.3 inception-move discipline (closes M-2.N2 / fully closes B-1).
2. §3.X.3: rewrite valuation prose; remove `Wait —`; state formula once; compute three values; declare PnL (closes M-2.N1).
3. §3.X.6 or §6.5.3: wire-recall / BeneficiaryReject worked example (closes M-2.N3 / fully closes M-4).
4. m-3: add `failing_party_lei` to CSDR penalty `obligation_id` recipe.
5. Invariant count: §15.6 says 10; §11 lists 11. Pick one and reconcile.

Then declare Pareto. Do not declare Pareto on the current v2 — the margin is too thin and the §3.X prose regression alone would embarrass the team if a competent outsider read it cold at audit.
