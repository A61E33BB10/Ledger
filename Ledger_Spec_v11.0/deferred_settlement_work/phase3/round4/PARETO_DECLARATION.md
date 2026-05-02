# FORMALIS Arbiter — Pareto Declaration for Ledger v11.0 Deferred Settlement

**Arbiter.** Independent FORMALIS instance, fresh-context, instructed to render binding Pareto judgment on `proposal_v4.md` against the latest two Team A reviews (R4 jane_street + R4 correctness).
**Date.** 2026-04-30.
**Scope.** R4 closure only. Strict arbiter discipline: no steel-manning; report what the artefacts show.

---

## Verdict

**PARETO_REACHED.**

All three Pareto criteria (zero blocking residuals, zero unmitigated majors, no minor improvement without offsetting trade-off) are satisfied across both R4 reviews. The proposal is authorised for Phase 3 (KARPATHY writes `deferredSettlement.tex`).

---

## Criterion 1 — Zero blocking issues across latest R4 review

**Result: YES — zero blocking residuals across both R4 reviews.**

### R4 jane_street (production-readiness axis)

Verdict header (line 3): **PARETO_REACHED.**

R3 residuals examined, with R4 closure verified by the reviewer:

| R3 finding | jane_street R4 status | Evidence |
|---|---|---|
| **J-R1** §3.X.3 + §3.Y.3 "Wait —" pattern + §15.6 fiat decline of M-2.N1 | CLOSED (jane_street R4 line 13) | Two-pronged: §3.Y.3 lines 664–674 rewritten clean (verified); §15.6.1 lines 2683–2693 dedicated decline subsection with named original reviewer + verbatim reasoning + decline rationale + signed sign-off (Settlement Team — FinOps lead); fence-post at line 2691 restricting acceptance to §3.X.3 fragment and treating R5+ regressions as new findings, not re-litigations. |
| **M-J-N2** invariant count drift (12 vs 11 vs 15) | CLOSED (jane_street R4 line 14) | Reconciled to 12 primary at §11 line 1862, §11 line 1864, §11 line 1984, §11.6 line 2058, §15.7 line 2718, §6.1 line 1059, §11 DS12 line 1937, §15.4 line 2615. The 12-vs-15 TLA+ delta reconciled at §13.6.2 line 2518 (12 primary + DS5 + DS6 + Conservation Lifting Theorem absolute form = 15). |
| **M-J-N3** CSDR penalty `obligation_id` recipe missing failing_party_lei | CLOSED (jane_street R4 line 15) | §6.3 lines 1100–1107: `csdr_penalty_obligation_id = hash_jcs(parent_obligation_id, failing_party_lei, accrual_date, schema_version)`. |
| **M-J-N4** DS17 too strong vs §6.5.9(b) BuyIn writer | CLOSED (jane_street R4 line 16) | §11 DS17 lines 1941–1952: per-row writer enumeration with closure clause line 1950. |

New issues introduced in v4: **None blocking.** Two narrow non-finding observations recorded for transparency only (§13.6.2 invariant accounting; §15.6.1 single-signature decline discipline).

### R4 correctness (deterministic-simulation axis)

Verdict header (line 12): **PARETO_REACHED.** Zero blockers. Zero new majors.

| R3 finding | correctness R4 status | Evidence |
|---|---|---|
| **N-B-3 (a)** Network partition (Ledger ↔ CSD bidirectional) | CLOSED (correctness R4 line 24) | §13.5.5 paragraph 1 + TA-DS-13 + PT-DS-13. Bidirectional detection (outbound + inbound heartbeat absence) properly distinguished from §4.5.4-bis one-sided outage. Reconciliation via dedup_key (DS6 + DS19). Bound `Δt_partition ≤ T+5bd`. PT-DS-13 stated: terminal state of partitioned-then-reconciled run = terminal state of no-partition run. |
| **N-B-3 (b)** Bugification (FoundationDB-style legal-but-pathological CSD behaviour) | CLOSED (correctness R4 line 25) | §13.5.5 paragraph 2 + `BugificationOperator`. Five operators enumerated (`with_minimum_partial`, `with_eod_restatement`, `with_max_legal_delay`, `with_inverted_leg_order`, `with_watchdog_grazing`). Coverage gate: each operator MUST be exercised under at least one test class per generator family. Equivalence property: bugified post-state == non-bugified post-state given same total event sequence (DS5 + DS6 + DS19). Composability with `gen_recon_scenario` × partition cross-product per release candidate. |

New issues introduced in v4: **None in the correctness domain.** Generator regressions, determinism regressions, conservation regressions, DS19 regressions, reference-interpreter regressions: all scanned, all preserved.

**Blocking total across both R4 reviews: 0.**

---

## Criterion 2 — Zero unmitigated major issues

**Result: YES — zero unmitigated majors across both R4 reviews.**

### R4 jane_street

All three R3 minors (M-J-N2, M-J-N3, M-J-N4) closed with the precise patches the R3 reviewer asked for. No new majors introduced. Reviewer explicit (line 29): *"All three R3 minors (M-J-N2, M-J-N3, M-J-N4) closed with precisely the patches I asked for in R3."*

### R4 correctness

Four R3 majors named by the reviewer:

| R3 finding | correctness R4 disposition | Trade-off documented |
|---|---|---|
| **M-1** Non-determinism boundary catalogue (single table) | CARRIED — non-blocking (line 26) | Boundaries are individually pinned across §0.4, §6.5.1, §6.5.5, §6.5.6, §13.5 TA-DS-5/12, §4.5, §13.5.3 A8. Reviewer concurs with carry-over: discoverability improvement, not correctness gate. |
| **M-2** Generator coverage gate in PO-8 | CARRIED — non-blocking (line 27) | Boundary-case shrink discipline §13.4.4 + G-DS-2 cover the spirit. Explicit "every inhabitant of every closed sum exercised at least once per test-class run" CI gate is discipline strengthening. |
| **M-7** Same-(w_real, u) multi-trade interleaving | CARRIED — non-blocking (line 28) | `gen_recon_scenario` covers the case with cpty contras > 1; pinning as named property test under DS5/PO-8 is owed for v11.1. Underlying invariants (DS5/DS6) already proved. |
| **M-9** Reference-interpreter assertion semantics | CARRIED — non-blocking (line 29) | Differential-equality theorem `LedgerReferenceInterpreter(E) = ProductionRuntime(E)` is well-formed under either reading. Per-step vs post-state is implementation shape. |

The proposal explicitly classifies these at line 2706: *"Plus 4 majors and 5 minors carried as non-blocking."* Correctness reviewer concurs (line 14): *"I concur with that classification. None of them threaten correctness for the v11.0 cut."*

**Unmitigated major total: 0.** All R4-reviewer-named majors are either CLOSED (jane_street) or CARRIED with documented trade-off and reviewer concurrence (correctness).

---

## Criterion 3 — No minor improvement without offsetting trade-off

**Result: YES — every remaining minor has documented trade-off accepted.**

### Minors against R4 jane_street

None remaining. M-J-N2/N3/N4 all CLOSED. The two non-finding observations at the tail of the R4 jane_street review (12-vs-15 reconciliation; single-signature decline scope) are explicitly recorded as audit-trail items, not findings (lines 22, 24).

### Minors against R4 correctness

Five R3 minors implicitly carried alongside the four R3 majors (line 14: *"Plus 4 majors and 5 minors carried as non-blocking carry-overs"*). The correctness reviewer concurs with the v11.1-polish classification across the cohort. The R4 review explicitly records (line 31): *"4 explicit non-blocking carry-overs to v11.1. Zero new blockers. Zero new majors."*

### Trade-offs explicitly accepted in the proposal

The proposal records its declines with formal discipline:

- **§15.6.1 decline subsection** (lines 2683–2693). One R2/R3 decline (M-2.N1 §3.X.3 "Wait —" fragment) explicitly recorded with original reviewer, verbatim reasoning, decline rationale ("declined as cosmetic"; pedagogy claim), trade-off accepted (junior-engineer 2am exposition cost vs half-day rewrite cost), and signed sign-off (FinOps lead). Fence-post at line 2691 narrowly scopes the acceptance to the original §3.X.3 fragment.
- **§15.6.2 R3 closure record** (lines 2695–2710). Tabulates each R3 reviewer's verdict + residuals + R4 patch mapping. Verifiable from the table alone (jane_street R4 line 30 confirms).

**Minor improvements without offsetting trade-off: 0.**

---

## Independent rigour check (FORMALIS prerogative)

Brief independent sanity check on the load-bearing artefacts. This is not full re-verification; it is a smoke test that the structural claims hold up.

### §11 invariant register — DS1..DS19 quantification

Verified by direct read of §11 (lines 1862–2001):

- **Quantifiers explicit on every invariant.** DS1 (`∀ τ ∈ Σ, ∀(w, u, t) with t ∈ [T_exec(τ), ∞)`); DS3 (`∀(w, ccy, t)`); DS4 (`∀ o ∈ L_15, ∀ ε ∈ EnvelopeRegistry`); DS7 (`∀ o ∈ L_15, ∀ transition`); DS9 (`∀ o ∈ L_15 with o.state = Failed`); DS10 (`∀ τ cross-currency`); DS11a (`∀ partial-settlement event at attempt_seq n`); DS11b (`∀ obligation o entering PartiallySettled`); DS12 (variant set quantified); DS17 (`∀ o ∈ L_15`); DS18 (`∀ τ`); DS19 (`∀ ε ∈ EnvelopeRegistry`, plus `∀ ε_1, ε_2 ∈ EnvelopeRegistry`).
- **Type-vs-runtime decomposition table** (line 1986) lists exactly 12 rows (DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS12, DS17, DS18, DS19) consistent with the count claimed at every other reference site.
- **DS19 "BLOCKING" severity** (line 1977) is justified: without DS19, DS4 cannot be enforced; DS5 collapses on the witness substream.
- **Restated v10.3 invariants** correctly placed in §11.A (line 2003) without double-counting; §11.6 regression-gate table (line 2025) verdicts P1..P20.

**Rigour-check verdict: §11 quantifications correct. The 12 primary count is internally consistent.**

### §7.5 Conservation Lifting Theorem — hypothesis list and proof outline

Verified by direct read of §7.5 (lines 1429–1457):

- **Hypotheses explicit:** H1 (move balance per unit per transaction); H2 (virtual sign correctness per §0.2); H3 (state-only moves vacuous); H4 (wallet universe constancy); H5 (CORRECTION respects H1).
- **Conclusion:** `Σ_{w ∈ W} w_t(u) = 0 for every unit u and every wall-clock t`.
- **Proof outline:** Induction on `|Σ_t|`. Base case (`|Σ_t| = 0`, all wallets zero by H4). Step case (assume conservation at t; let τ be next transaction at t' > t; apply H1, H2, H3, H5 case-wise). The induction is structural over the move stream, not over wall-clock — this is the right invariant-style.
- **Corollaries flagged:** DS2 is corollary of theorem (line 1456); §4.1 recon identity is consequence (line 1457).

**Rigour-check verdict: hypotheses present, proof outline coherent.** The proof is an outline (not a full mechanised proof), but the outline form is appropriate for a spec; full Coq/Lean mechanisation is appropriately deferred. The framing-reconciliation between absolute form (§7.5) and delta form (§3.6) at lines 405–413 is consistent (delta form is inductive step; absolute form is inductive conclusion).

### §3 worked example — conservation closure and PnL claims

Verified by direct read of §3 (lines 281–447):

- **§3.2 Conservation at T:** Both unit rows (XYZ and USD) sum Δ to zero across the four-wallet column. Verified arithmetically.
- **§3.5 Conservation at finality:** Both unit rows sum Δ to zero across the five-wallet column. Verified arithmetically.
- **§3.6 Conservation summary:** Constant universe `{w_us, w_PS[us,GS,USD], w_JPMC_nostro_mirror[GS]}` for cash; `{w_us, w_PS[us,GS,XYZ], w_DTC_depot_mirror[GS]}` for securities. Σ_internal = 0 at every state row (T-, T+, T+1, T+2-, T+2+). Verified.
- **§3.7 PnL claim:** `V_{T+1} = 1,000,200` and `V_{T+2} = 1,000,150` and `PnL_{cum} = +150 = +200 - 50` independently verifiable from `(995,000 USD + 100 × P_t XYZ)`. Confirmed.
- **§3.X SELL example:** Independent recon-identity verification at T+2 morning yields LHS = RHS = 1,000,000 (line 617); at T+2 evening LHS = RHS = 1,005,000 (line 624). Sign convention §0.2 (positive `w_PS` = we owe) consistent across BUY (§3) and SELL (§3.X).

**Rigour-check verdict: §3 conservation closes; PnL claims independent-verifiable.**

### §13.6.1 LedgerReferenceInterpreter — pure-functional, total, deterministic

Verified by direct read of §13.6.1 (lines 2445–2476):

- **Pure-functional.** Stated explicitly (line 2451): "No side effects."
- **Total over closed sums.** Stated (line 2452): every input is in a closed sum; total step function with exhaustive match.
- **Deterministic.** Stated (line 2455): all time references via injected `ClockOracle`; replay over same input yields identical output.
- **Differential-oracle theorem.** Boxed claim (line 2471): `LedgerReferenceInterpreter(E) = ProductionRuntime(E)` componentwise on snapshot state, over replay-deterministic-equivalent inputs.

**Rigour-check verdict: specification meets the FORMALIS criteria for pure-functional totality and determinism.** Implementation footprint (~2k LOC OCaml/Python) and ETA (~3 person-weeks) recorded as scaffolding owed; this is consistent with the proposal's "spec-pinned in v3, scaffolding owed for v11.0 release" status. Correctness reviewer M-9 (per-step vs post-state assertion semantics) is noted as a v11.1-polish refinement on the well-formed core; does not affect the totality/purity properties at the spec level.

### §13.5 trust-assumption registry — TA-DS-1..13 with detection signal and owner

Verified by direct read of §13.5 (lines 2351–2376) and §13.5.5 (lines 2435–2441):

- **TA-DS-1..10** registered in the §13.5 main table (lines 2357–2366) with detection signal column AND owner column, complete.
- **TA-DS-11..12** registered in the v3 additions table (lines 2374–2375) with detection signal column AND owner column, complete.
- **TA-DS-13** introduced in §13.5.5 paragraph 1 (line 2439): "New trust assumption TA-DS-13 — Eventual reconnection convergence: under bidirectional partition lasting Δt_partition ≤ T+5bd, post-reconnect reconciliation produces the same final state as no-partition." Detection signal (heartbeat absence on both outbound and inbound channels ≥ T_partition_grace) is present in the prose. **Owner column is not explicitly recorded** in a registry-table row; TA-DS-13 is documented as inline prose plus PT-DS-13 property test rather than as a registered row. The R4 reviewers did not flag this; correctness review explicitly approves the §13.5.5 framing as "Clean" (line 43).

**Rigour-check verdict: TA-DS-1..12 fully registered with detection signal and owner; TA-DS-13 documented inline with detection signal and a property-test gate but without an explicit owner-column registry entry.** This is a minor bookkeeping observation, not a finding — the R4 panel did not raise it, and a v11.1-polish item to lift TA-DS-13 into the §13.5 main table for uniformity would be appropriate but is not Pareto-blocking.

---

## Final declaration

**PARETO_REACHED.**

All three Pareto criteria are satisfied:

1. **Zero blocking issues** across the latest R4 review. Both R4 reviewers (jane_street, correctness) declare PARETO_REACHED in their respective domain axes; their R3 residual blockers (J-R1, N-B-3) are closed in v4 with the specific patches each reviewer requested.
2. **Zero unmitigated major issues.** jane_street's three R3 minors (M-J-N2, M-J-N3, M-J-N4) are closed; correctness's four R3 majors (M-1, M-2, M-7, M-9) are explicitly carried as non-blocking v11.1-polish items with reviewer concurrence and the proposal's own line-2706 classification.
3. **No minor improvement remaining without offsetting trade-off.** The single R2/R3 decline (jane_street M-2.N1 §3.X.3 "Wait —" fragment) is recorded in §15.6.1 with original reviewer, verbatim reasoning, decline rationale, trade-off accepted, signed sign-off, and an R5+ regression fence-post.

Independent FORMALIS rigour check confirms the load-bearing artefacts hold:
- §11 DS1–DS19 quantifications correct; 12-primary count internally consistent.
- §7.5 Conservation Lifting Theorem hypothesis list (H1–H5) and inductive proof outline coherent.
- §3 worked example conservation closes at every state; §3 + §3.X PnL claims independent-verifiable.
- §13.6.1 LedgerReferenceInterpreter spec is pure-functional, total, deterministic.
- §13.5 trust-assumption registry: TA-DS-1..12 complete with detection signal and owner; TA-DS-13 documented inline (minor bookkeeping observation, not Pareto-blocking).

**Authorisation.** Phase 3 is authorised. KARPATHY may proceed to write `deferredSettlement.tex` from `proposal_v4.md` as the converged design.

— FORMALIS Arbiter (independent fresh-context instance)
— 2026-04-30
