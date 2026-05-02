# R2 Consolidated Findings — Deferred Settlement Phase 3 Round 2

**Reviewers (6):** jane_street, correctness, testcommittee, nazarov, temporal, cartan.

**Verdict tally:**
- REJECT_REVISE: testcommittee (1)
- ACCEPT_WITH_CHANGES: jane_street, correctness, nazarov, temporal, cartan (5)
- PARETO_REACHED: 0

**Distance to Pareto:** ~3-7 person-days of additive patches.

---

## Residual BLOCKING items (must close in R3)

### R3-B1 — Conservation framing (jane_street B-1 mitigated-not-closed; correctness N-B-1)
**Issue.** §3.6 conservation table sums *deltas* to zero, but absolute USD across the named universe at T⁺ shows 1,000,000 with no source wallet for the pre-trade `w_us(USD) = 1,000,000`. §7.5 Conservation Lifting Theorem is stated in absolute form `Σ_w w_t(u) = 0`. Tables and theorem don't match.
**Fix.** Either:
- (a) Add an explicit `w_genesis_inception` wallet to the named universe holding the pre-trade balance as a contra (`w_genesis.own(USD) = -1,000,000` from inception); OR
- (b) Restate the §3.6 table as `Σ Δw = 0` (conservation of deltas) and reference v10.3's inception-move discipline that establishes the pre-trade balances.
Both work. Option (b) is one paragraph and cleaner.

### R3-B2 — Bijection Φ proof (cartan B-1 partial)
**Issue.** §7.4 bijection Φ between mainstream representation and first-class-unit representation is presented as "Proof sketch" by the proposal's own admission. Carrier sets are asymmetric. Inverse Φ⁻¹ is named "reconstruct" without a formula. Identity-on-composition never checked. Sign disjunction `(or -q depending on side)` itself ambiguous.
**Fix.** ~½ page. Pin carrier sets symmetrically. Define Φ⁻¹ as a function. State `Φ⁻¹ ∘ Φ = id` and `Φ ∘ Φ⁻¹ = id` as two lemmas with one-line proofs.

### R3-B3 — DS1 reformulation contradicts §4.1.5 (cartan B-3 partial)
**Issue.** Equivalent reformulation of DS1 contains a universal quantifier "no projection Π satisfies …" that is contradicted by §4.1.5's own named `inflight_in/out` projections.
**Fix.** ~3 lines. Either drop the equivalent reformulation or restrict it to "no projection over `(Position[w_real, u].own)` only".

### R3-B4 — DS19 (witness-identity determinism) not a numbered invariant (correctness B-1.f, N-B-2)
**Issue.** DS4 (no-discharge-without-witness) presupposes DS19 (witness-identity determinism). v2 names `dedup_key = hash_jcs(payload, source_lei, ts_obs)` in §4.5.1 and TA-DS-1/2 in §13.5, but DS19 is not a numbered invariant.
**Fix.** Add DS19 as numbered invariant in §11. Statement: "For every witness payload P signed by source LEI L at observation timestamp t, the dedup key K(P, L, t) is unique and deterministic; two witnesses are identical iff K(P_1, L_1, t_1) = K(P_2, L_2, t_2)." Type-vs-runtime: hybrid (compile-time hash function totality + runtime collision-check).

### R3-B5 — Differential oracle missing (correctness B-4 not closed)
**Issue.** No naive sequential reference interpreter named for differential testing. TLA+ at PO-8 is a model, not an oracle.
**Fix.** Add to §13 (or §6.5) the `LedgerReferenceInterpreter` — a single-threaded, single-machine, deterministic-clock implementation that processes the move stream and L_15 obligations sequentially. Its outputs are the differential oracle for property tests. ~½ page.

### R3-B6 — TLA+ model still at v1 fidelity (testcommittee B-1)
**Issue.** PO-8 TLA+ model still listed as "Open; tractable in minutes". v2 introduced PSS/PS wallet family, two-layer status, obligation-graph (CSDR penalty), witness envelopes, partial-fill recursion. Liveness fairness regime not stated.
**Fix.** Update PO-8 entry in §13 to specify:
- Variables match v2: `PSS_payable, PSS_receivable, PS_payable, PS_receivable, L_15_state, witness_log, clock`
- Fairness: weak fairness on `discharge_step`; strong fairness on `csdr_penalty_accrual`
- Sizing: `|W|=4, |U|=2, |trades|=4, depth=8` → ~10^5–10^6 reachable
- D_max=2 pinned (already in §13)
This is documentation work, not new model code; commits the model spec.

### R3-B7 — Mutation testing targets unstated (testcommittee B-4)
**Issue.** v2's §12.1.1 phantom wallet class IS the typed-PnL boundary that R1 B-4 asked for, but the proposal does not state the 100% target on DS1 mutations, the 80% overall target, or acknowledge the SQL-projection-mutation gap.
**Fix.** Add to §13 (one paragraph): "Mutation testing target: 80% overall on the deferred-settlement extension; 100% on the DS1 mutation class (mutations that touch wallet-class projection in PnL). The SQL-projection-mutation gap (Hypothesis cannot mutate raw SQL) is mitigated by the §12.1.1 phantom-typed wallet handles which force PnL-bearing reads through a typed projection function."

### R3-B8 — v10.3 regression gate spec missing (testcommittee B-5)
**Issue.** v2 has no §11.6 enumerating v10.3 P1-P20 with pass/migrate/replace verdict. §11.A reasserts by reference.
**Fix.** Add §11.6 (or extend §11.A) with table:
| v10.3 invariant | v2 status |
|---|---|
| P1 conservation | RESTATED (see DS2) |
| P2 atomicity | PASS unchanged |
| P5 idempotency | RESTATED (see DS6) |
| P6 replay determinism | RESTATED (see DS5, with G5 caveat) |
| P9 bitemporal monotonicity | RESTATED (see DS16) |
| P10 PnL path-independence | PASS unchanged (DS1 strengthens) |
| P11–P20 SBL | PASS unchanged (composition §7) |
| ... |
~½ page table. This is documentation, not new content.

### R3-B9 — Dedup key schema_version omission (nazarov N-1)
**Issue.** dedup_key formula `hash_jcs(payload, source_lei, ts_obs)` omits `schema_version`. A schema migration would silently allow re-discharge.
**Fix.** Restate as `dedup_key = hash_jcs(schema_version, source_lei, ts_obs, payload)` in §4.5.1. ~1 line.

### R3-B10 — CSD operational outage protocol (nazarov N-2)
**Issue.** v2 closes "absence of finality is itself attested" for the obligation FSM, but CSD operational outage (multi-day unavailability) is silently re-deferred to §14 out-of-scope. This is a real production case (T2S incident 2023, DTCC night-cycle issues).
**Fix.** Move CSD-outage protocol from §14 into spec. New subsection in §6.5 or §4.5: "When the primary CSD is operationally degraded for >`T_outage_grace`, the framework SHALL: (a) freeze new instructions; (b) maintain existing obligation FSM; (c) preserve breakage state in L_18; (d) require manual operator action to resume. The watchdog signals `csd_outage_detected` to all running SettlementSaga workflows." ~½ page.

### R3-B11 — Broker virtual semantics M-4 (jane_street M-4 not-closed)
**Issue.** Wire-recall, partial-credit, per-leg discharge-witness semantics absent from §3 broker-virtual treatment.
**Fix.** Add ~½ page in §3.X.X covering: wire recall (counterparty pulls back; L_15 reverts to Pending state with audit chain); partial credit (camt.054 with partial amount → PartiallySettled FSM transition); per-leg discharge witness (each leg has its own `dedup_key`).

---

## Unmitigated MAJOR items (must address or document trade-off)

### R3-M1 — Search attributes (temporal M-7)
**Issue.** Proposal silently drops Temporal search attributes. §4.3 forbids application-DB joins for ops queries; without search attributes the spec is operationally unrunnable.
**Fix.** Add to §6.5: search attributes `obligation_id (keyword)`, `cpty_lei (keyword)`, `expected_settle_date (datetime)`, `lifecycle_stage (keyword)`, `csd_lei (keyword)`. ~5 lines.

### R3-M2 — Various nazarov majors (N-4 mapper-version, N-5 key management contract, N-6 threat model, N-7 freshness contract)
**Issue.** ISO 20022 mapper-version pinning, key-management lifecycle contract, threat-model enumeration, per-witness-class freshness contract — all named but not specified.
**Fix.** Add §13.5.1 (additive trust-registry expansion) with these as named subsections. ~1 page.

### R3-M3 — Various temporal partials (M-1, M-3, M-4, M-5, M-8)
**Issue.** CORRECTION enforcement locus adverbial; CsdrPenaltyAccrualWorkflow not catalogued; restatement trigger unspecified; BuyIn↔SettlementSaga writer relationship; watchdog implementation form.
**Fix.** §6.5 supplement with these specifications. ~1 page.

### R3-M4 — Other testcommittee leftovers (M-2 fairness, M-4 char tests, M-6 bitemporal honesty)
**Issue.** Fairness regime not stated; six v10.3 characterisation tests absent; bitemporal honesty re option-(a).
**Fix.** Roll into R3-B6 (TLA+ fairness) and R3-B8 (regression gate); add three lines on bitemporal under §11.A.

---

## NEW issues introduced in v2 (regressions)

| Reviewer | ID | Issue | Severity |
|---|---|---|---|
| jane_street | M-2.N1 | §3.X.3 SELL prose contains debugging-by-trial "Wait —" | Minor (cosmetic) |
| jane_street | M-2.N2 | absolute-Q vs delta-Q framing (folded into R3-B1) | Blocking |
| jane_street | M-2.N3 | wire-recall semantics carry-over (folded into R3-B11) | Blocking |
| correctness | N-B-1 | Conservation table delta vs theorem absolute (folded into R3-B1) | Blocking |
| correctness | N-B-2 | DS19 not numbered invariant (folded into R3-B4) | Blocking |
| testcommittee | N-1 | TLA+ doubly stale after wallet refactor (folded into R3-B6) | Blocking |
| testcommittee | N-2 | gen_partial_chain_depth shrinks to 0 | Minor |
| testcommittee | N-3 | WS-11 conflates DvP-reject types | Minor |
| testcommittee | N-4 | gen_corporate_action_in_window shrinks to none | Minor |
| testcommittee | N-5 | attempt_seq durability across CaN+failover | Major |
| testcommittee | N-6 | DS3 verified at 2 points; needs property test | Major |
| nazarov | N-3 | restatement model A/B ambiguity | Major |
| nazarov | N-8 | TA-DS-11 missing | Major |
| temporal | N-1 | producer-monotonic attempt_seq not pinned | Major |
| temporal | N-2 | watchdog pseudocode determinism-suspect | Major |
| temporal | N-3 | DS17 unique-writer inconsistent with BuyInWorkflow | Major |
| temporal | N-4 | §6.5.2 cross-workflow signal contradicts §6.5.3 | Major |

---

## R3 work plan

Round 3 is a **focused patch round**. Total estimated work: ~3-5 person-days. No architecture change.

### R3 closure checklist (11 blocking + ~10 majors → ~30 line items)
1. R3-B1 — conservation framing (1 paragraph)
2. R3-B2 — bijection Φ proof (½ page)
3. R3-B3 — DS1 reformulation (3 lines)
4. R3-B4 — DS19 invariant added (½ paragraph)
5. R3-B5 — LedgerReferenceInterpreter (½ page)
6. R3-B6 — TLA+ PO-8 spec at v2 fidelity (½ page)
7. R3-B7 — mutation testing targets (1 paragraph)
8. R3-B8 — v10.3 regression gate table (½ page)
9. R3-B9 — dedup_key schema_version (1 line)
10. R3-B10 — CSD outage protocol in spec (½ page)
11. R3-B11 — broker virtual semantics M-4 (½ page)
12. R3-M1 — search attributes (5 lines)
13. R3-M2 — nazarov majors (mapper-version, key-management, threat-model, freshness contract) (1 page)
14. R3-M3 — temporal majors (CORRECTION locus, CsdrPenaltyAccrual, restatement trigger, writer relationship, watchdog form) (1 page)
15. R3-M4 — testcommittee fairness, char tests, bitemporal honesty (3 lines, rolled into earlier items)
16. Address temporal N-1/N-2/N-3/N-4 (each 1-2 sentences in §6.5)
17. Address testcommittee N-2/N-3/N-4/N-5/N-6 (each 1-2 sentences)
18. Address nazarov N-3/N-8 (each 1 sentence in §13.5)

Total v3 delta over v2: ~5-7 pages additive.

### R3 panel
Per the original brief's "minimum 5 rounds, max 20" mandate, R3 will be a tight closure-verification panel. Recommended: jane_street, cartan, correctness, testcommittee, nazarov, temporal — same 6 as R2 — to verify their own R2-residual findings are closed.

### Pareto declaration
After R3, if 6/6 reviewers declare PARETO_REACHED, an independent FORMALIS arbiter sees the latest proposal + the latest review only, and renders binding judgment. If not, R4 with the same scope.

---

End of R2 consolidated findings. Settlement Team: produce proposal_v3 closing R3-B1 to R3-B11 + R3-M1 to R3-M4 + the new-issues list. Total work ~3-5 person-days.
