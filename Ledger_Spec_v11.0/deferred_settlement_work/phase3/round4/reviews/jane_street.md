# R4 Closure Review — Jane Street CTO

## Verdict: PARETO_REACHED

v4 closes the J-R1 blocker and all three minors (M-J-N2, M-J-N3, M-J-N4) cleanly via the surgical patches advertised in the v4 preamble. Zero blocking residuals. Zero unmitigated majors. The methodological gate I flagged as load-bearing in R3 — that R2/R3 findings cannot be declined inside a closure-verdict table — is installed correctly at §15.6.1 and is fence-posted against future regression. The substantive R3 work (bijection Φ, DS19, LedgerReferenceInterpreter, TLA+ at v2/v3 fidelity, mutation testing 80%/100%, CSD outage protocol, broker-virtual semantics, threat model A1..A10) is preserved unchanged. v4 is a one-pass surgical patch round of the kind R4 closure was scoped for.

Pareto declared from the production-readiness axis. Recommend independent FORMALIS-arbiter Pareto declaration as v4 §15.6.2 invites.

## R3 closure check

| R3 Finding | Status | Evidence (§ ref) |
|---|---|---|
| **J-R1** §3.X.3 + §3.Y.3 "Wait —" debugging fragments + §15.6 fiat decline of M-2.N1 | **CLOSED** | Two-pronged fix landed exactly as my R3 review specified path (a)+(b) hybrid. (1) §3.Y.3 lines 664–674: fragment rewritten cleanly. New prose states the §4.5.1 dedup-key formula directly (line 669–670 give per-leg formulas; line 671 states independence; line 674 derives equivocation, replay, contradiction in a single linear pass). No "wait, that is wrong" interjection remains. (2) §15.6.1 lines 2683–2693: dedicated subsection "R2/R3 findings declined with reasoning" extracted from the closure table. The decline records original reviewer (jane_street R2), original reasoning verbatim, decline rationale (declined-as-cosmetic with named pedagogy argument), trade-off accepted, and signed sign-off (Settlement Team — FinOps lead). Crucially the §15.6.1 trailing paragraph (line 2691) installs the **fence-post**: "all new prose introduced in R4+ MUST avoid the pattern. Future R5+ rounds that introduce a new instance of the pattern will be treated as a regression, not a re-litigation of the §15.6.1 acceptance." This is the methodological gate I demanded; it both honours the original team's pedagogy claim on the §3.X.3 fragment AND prevents the disease from spreading. The §3.X.3 line 509 "Wait —" remains by R2 acceptance with R4 narrow scoping. |
| **M-J-N2** invariant count drift (12 vs 11) | **CLOSED** | Reconciled to 12 primary across the document. §11 line 1862 header "12 primary, pruned"; §11 line 1864 "Final set: 12 primary invariants"; §11 line 1984 type-vs-runtime decomposition header "(12 invariants)" with table at lines 1986–1999 listing exactly 12 rows; §11.6 line 2058 "all 12 primary DS invariants green"; §15.7 line 2718 "The 12 primary invariants (DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS12, DS17, DS18, DS19 — DS19 added in v3)"; §13.6.2 line 2518 reconciles the apparent 12-vs-15 discrepancy honestly: "12 §11 primary invariants ... plus two restated-v10.3 invariants exercised in deferred-settlement context (DS5 replay determinism, DS6 multi-source idempotency) plus the absolute-form Conservation Lifting Theorem (§7.5)" — total 15 named TLA+ invariants. The two counts now agree on the §11 primary count (12) and decompose the TLA+ delta (3) explicitly. §6.1 line 1059, §11 DS12 line 1937, and §15.4 line 2615 all consistently state 12. |
| **M-J-N3** CSDR penalty `obligation_id` recipe missing `failing_party_lei` | **CLOSED** | §6.3 lines 1100–1107: dedicated "Deterministic ID recipe (R4 — closes jane_street M-J-N3, R1 m-3)" subsection. Recipe is now `csdr_penalty_obligation_id = hash_jcs(parent_obligation_id, failing_party_lei, accrual_date, schema_version)`. All four arguments present. Line 1100 explicitly names the bilateral-DvP-fail collision case ("each side fails the other's leg") and the chained-fails case as the motivations. Line 1107 explains the `schema_version` inclusion by analogy to the §4.5.1 `dedup_key` post-R3-B9 fix. The reconciliation-vs-`semt.044` claim at line 1107 commits to recipe canonicality at both ends (Ledger and CSD-side reconciliation). This is exactly the patch I asked for in R3; landed without scope creep. |
| **M-J-N4** DS17 statement too strong vs §6.5.9(b) BuyIn writer | **CLOSED** | §11 DS17 lines 1941–1952: statement rewritten as "exactly one workflow class per row" with explicit per-row enumeration. (a) `SettlementSaga` for original obligation transitions among `Pending, Instructed, PartiallySettled, Discharged, Failed, Cancelled`, plus the parent's `Failed → BoughtIn` transition on signal; (b) `BuyInWorkflow` for its own buy-in obligation row (separate `L_15.Obligation` with `parent_obligation_id` link per §6.5.9(b)); (c) `CsdrPenaltyAccrualWorkflow` for `CSDR_PENALTY`-kind rows; (d) `CorrectionTransactionService` for `CORRECTION`-class transitions at MoveStream-level write capability. The disambiguation §6.5.9 already implied is now reflected in the DS17 statement. Line 1950 retains the closure clause: "No other handler may mutate any `o.state` field outside its scoped row class." Type/severity preserved (compile-time, HIGH). |

## New issues introduced in v4

**None blocking.** The v4 patch set is surgical and additive in shape; no architectural change. Two narrow observations, both non-blocking and recorded only for transparency:

1. **§13.6.2 line 2518 invariant accounting (informational, not a finding).** The 12-vs-15 reconciliation is sound (12 primary + DS5 + DS6 + Conservation Lifting Theorem = 15). The arithmetic 12 + 2 + 1 = 15 is correct and now explicitly stated. Closed as a finding because it answers M-J-N2 cleanly; recorded here only for the audit trail.

2. **§15.6.1 acceptance is correctly scoped to a single named individual (Settlement Team — FinOps lead) rather than a panel.** This matches the multi-agent adversarial methodology — declines are *signed*, not consensus-rolled. Future rounds should preserve this discipline (one signature per decline). Not a finding; reinforcing the §15.6.1 fence-post.

## Pareto judgment

- **Zero blocking?** **YES.** J-R1 closed via §3.Y.3 rewrite + §15.6.1 dedicated decline subsection + R4-narrow-scoping fence-post. No new blockers introduced.
- **Zero unmitigated major?** **YES.** All three R3 minors (M-J-N2, M-J-N3, M-J-N4) closed with precisely the patches I asked for in R3.
- **All R3 residuals rolled in?** **YES.** §15.6.2 R3 closure record (lines 2695–2710) tabulates every R3 reviewer's residuals against the corresponding R4 patch with section reference. Patches 1, 2, 4, 5, 6 cover my four residuals; Patch 3 covers correctness N-B-3; Patch 7 covers cartan's two non-blocking polish items. The bookkeeping is complete and verifiable from the table alone.
- **Pareto declared?** **YES, from the production-readiness axis.**

The substantive engineering across R1, R2, R3 (bijection Φ, DS19, LedgerReferenceInterpreter scaffolding, TLA+ at v2/v3 fidelity, mutation testing targets, CSD outage protocol, broker-virtual semantics, threat model A1..A10) was correct entering v4 and is preserved unchanged. v4 was an editorial-discipline pass plus the §6.3 hash recipe one-liner, executed cleanly. Ship v4 as the closure-round artefact and route to FORMALIS-arbiter for the final cross-axis Pareto seal.

## What v4 did particularly well

- **§15.6.1 fence-post (line 2691).** Explicitly restricts the M-2.N1 acceptance to the original §3.X.3 fragment and warns that R5+ instances will be treated as regression, not re-litigation. This is the right precedent — the multi-agent methodology survives v4 with its decline gate intact.
- **§6.3 patch surgical scope (lines 1100–1107).** One subsection added; old recipe replaced; rationale linked back to §4.5.1 R3-B9 dedup_key fix. No collateral edits. Exactly the right shape for an R4 patch.
- **§11 DS17 rewrite (lines 1941–1952).** Per-row writer enumeration matches §6.5.9 reality; trailing closure clause (line 1950) preserves the original safety guarantee. Compile-time / HIGH severity preserved.
- **§15.6.2 R3 closure record table (lines 2699–2710).** Tabulating every R3 reviewer's residual verdict against the R4 patch number is the right audit trail shape; an outsider auditor can verify R4 closure without consulting individual R3 review files.

End of R4 closure review. PARETO_REACHED from production-readiness axis. Recommend independent FORMALIS-arbiter declaration.
