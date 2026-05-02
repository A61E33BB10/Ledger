# Round 4 Adversarial Closure Check — Correctness Architect

**Subject.** `proposal_v4.md` — Phase 3 Round 4 Settlement Team revision of the Deferred-Settlement specification.
**Reviewer.** Correctness Architect (Will Wilson, deterministic-simulation lens).
**Date.** 2026-04-30.
**Scope.** Verification that R4 Patch 3 closes the single R3 blocker N-B-3 (network partition + bugification absent from fault catalogue). Honest re-scan for new R4-introduced regressions in the correctness domain.

---

## Verdict

**PARETO_REACHED.** Zero blockers. Zero new majors. The single R3 residual blocker (N-B-3) is closed cleanly and additively in §13.5.5.

The four R3 residual MAJORS that I named (M-1 boundary catalogue, M-2 generator coverage gate, M-7 same-`(w,u)` interleaving, M-9 reference-interpreter assertion semantics) are explicitly **accepted as non-blocking carry-overs** at line 2706 of v4 ("Plus 4 majors and 5 minors carried as non-blocking"). I concur with that classification. None of them threaten correctness for the v11.0 cut; all four are bookkeeping/discipline items appropriate for v11.1.

Pareto reached in this reviewer's domain.

---

## R3 closure table — by R3 finding ID (this reviewer)

| R3 finding | v4 status | v4 location | Reviewer verdict |
|---|---|---|---|
| **N-B-3 (a)** Network partition (Ledger ↔ CSD bidirectional) | **CLOSED** | §13.5.5 paragraph 1 + TA-DS-13 + PT-DS-13 | Symmetric loss of connectivity correctly distinguished from §4.5.4-bis one-sided outage. Detection signal is bidirectional heartbeat absence on BOTH outbound (we cannot reach CSD) AND inbound (CSD attestation feed silent) — correct framing of a partition vs an outage. Reconciliation protocol uses `dedup_key` (DS6 + DS19) for at-most-once application — exactly the right primitive. TA-DS-13 statement is concrete: `Δt_partition ≤ T+5bd` bound, `t_known` delayed but `t_obs` preserved from envelopes. PT-DS-13 boxed: terminal state of partitioned-then-reconciled run equals terminal state of no-partition run. Coverage gate: at least one PT-DS-13 instance per generator family per CI run. **Clean.** |
| **N-B-3 (b)** Bugification (FoundationDB-style legal-but-pathological CSD behaviour) | **CLOSED** | §13.5.5 paragraph 2 + `BugificationOperator` strategy | All five operators enumerated: `with_minimum_partial`, `with_eod_restatement`, `with_max_legal_delay`, `with_inverted_leg_order`, `with_watchdog_grazing`. Category-distinction from adversarial threat model (§13.5.3 A1..A10) is explicit and correct: "adversarial threat models catch the obvious; bugification catches the unobvious-but-legal" — that is the FoundationDB lesson stated correctly. Coverage gate: each operator MUST be exercised under at least one test class per generator family. Equivalence property: a CSD bugified under any single operator MUST produce identical post-state to a non-bugified CSD given the same total event sequence (DS5 replay determinism; DS6 idempotency; DS19 witness identity). Composability: `BugificationOperator` × `gen_recon_scenario` × partition generator cross-product per release candidate. **Clean.** |
| **M-1** Non-determinism boundary catalogue (single table) | **CARRIED — non-blocking** | n/a (not added) | Accepted as v11.1-polish. Bookkeeping task; does not threaten correctness for v11.0 because the boundaries are individually pinned (§0.4 ts_obs/ts_known, §6.5.1 tx_id, §6.5.5 commutativity, §6.5.6 dedup_key, §13.5 TA-DS-5/12, §4.5 envelope dedup, §13.5.3 A8). Single-table consolidation is a discoverability improvement, not a correctness gate. **Concur with carry-over.** |
| **M-2** Generator coverage gate in PO-8 | **CARRIED — non-blocking** | n/a (not added explicitly; partial via §13.4.4 G-DS-2) | Accepted as v11.1-polish. The boundary-case shrink discipline (§13.4.4) and G-DS-2 per-class conservation already cover the spirit. The explicit "every inhabitant of every closed sum exercised at least once per test-class run" CI gate is a discipline strengthening, not a correctness gate. **Concur with carry-over.** |
| **M-7** Same-`(w_real, u)` multi-trade interleaving property | **CARRIED — non-blocking** | n/a (covered implicitly by `gen_recon_scenario`) | Accepted as v11.1-polish. `gen_recon_scenario` covers the case when `cpty contras > 1`; the explicit pinning as a named property test under DS5/PO-8 is owed for v11.1. Not a correctness gate because the underlying invariants (DS5 replay determinism, DS6 idempotency) are already proved on the multiset of finalised witnesses. **Concur with carry-over.** |
| **M-9** Reference-interpreter assertion semantics (per-step halt vs post-state property) | **CARRIED — non-blocking** | n/a (one-sentence edit deferred) | Accepted as v11.1-polish. The current §13.6.1 spec lists invariants enforced; whether enforcement is per-step (halt on first violation) or post-state (asserted at output) is implementation-shape detail. The differential-equality theorem `LedgerReferenceInterpreter(E) = ProductionRuntime(E)` is well-formed under either reading. **Concur with carry-over** (recommend per-step for v11.1).  |

**Subtotal:** 1 CLOSED (the only blocker), 4 explicit non-blocking carry-overs to v11.1. Zero new blockers. Zero new majors.

---

## §13.5.5 quality check — TA-DS-13 + BugificationOperator

### TA-DS-13 — Eventual reconnection convergence

Stated correctly. The bound `Δt_partition ≤ T+5bd` is conservative (consistent with §10.5 buy-in regime and §6.5.8 watchdog interval Λ_4). The `t_known` delayed / `t_obs` preserved framing is consistent with v11.0 §0.4 bitemporal discipline. The dedup-key reconciliation primitive is the same primitive used for ordinary at-most-once envelope application (§4.5.1 + DS6); reusing it for partition reconciliation is the correct cohomological move (no new mechanism, just amplitude over `Δt_partition`).

PT-DS-13 statement: "under simulated partition of arbitrary `Δt_partition`, terminal state of partitioned-then-reconciled run equals terminal state of no-partition run" — this is the canonical eventual-consistency property test (Bailis et al. 2014 highly-available-transactions framing).

**Verdict:** Clean. Closure of the partition-class fault.

### BugificationOperator (5 operators)

Each operator targets a known test-suite blind spot:

| Operator | Targets | Spec-legal? | Adversarial dimension |
|---|---|---|---|
| `with_minimum_partial` | Partial chain depth tests that implicitly assume "typical" partials | Yes (any positive partial below the gross is legal) | Forces every test class to actually run partial chains with `q_partial = 1` boundary case |
| `with_eod_restatement` | Restatement tests that implicitly assume mid-day restatements | Yes (CSD policy choice) | Stresses the bitemporal discipline at end-of-day cut-over |
| `with_max_legal_delay` | Watchdog tests that implicitly assume "typical" CSD latency | Yes (within SLA) | Forces watchdog to trigger on every legal slowest path |
| `with_inverted_leg_order` | DvP tests that implicitly assume sese.025 → camt.054 ordering | Yes (DvP atomicity does not require a canonical wire order) | Stresses §6.5.5 commutativity matrix |
| `with_watchdog_grazing` | Tests that assume CSD never grazes the watchdog interval `Λ_4` | Yes (any time within Λ_4 is legal) | Forces detection of the racy boundary at exactly Λ_4 |

This is a strong enumeration. The five operators collectively target the five most likely blind spots in a property-test suite tuned to "typical" CSD behaviour — exactly what the FoundationDB literature warns against.

**Coverage-gate clause** ("each operator MUST be exercised under at least one test class per generator family") is a hard CI gate, not aspirational. The post-state equivalence property (`bugified_post = non_bugified_post given same total event sequence`) is the canonical bugification invariant — it asserts that the *system* is robust, not that any particular CSD policy is preferred.

**Cross-product composability** (`BugificationOperator × partition × generator-family`) is genuinely interesting: it stresses the case where a partition reconciles with a CSD that has been bugified during the partition. This is a category I would not have asked for explicitly but is the right test surface.

**Verdict:** Clean. Closure of the bugification-class fault. The Settlement Team has internalised the FoundationDB discipline.

---

## New issues introduced in v4

None in the correctness domain. v4 is a 7-patch surgical revision of v3; Patches 1, 2, 4, 5, 6, 7 do not touch fault-tolerance or determinism scope. Patch 3 (§13.5.5) is purely additive and self-contained.

I scanned for the usual regression classes:
- **Generator regressions** (a generator silently weakened): none. §13.4.4 generators preserved verbatim from v3.
- **Determinism regressions** (a non-deterministic boundary newly introduced): none. The partition simulation uses an injected partition oracle (analogous to ClockOracle); composable with the existing replay framework.
- **Conservation regressions** (§3.6 / §7.5 framing): none. v3 R3-B1 closure preserved verbatim.
- **DS19 regressions**: none. §11 DS19 statement preserved verbatim.
- **Reference-interpreter regressions**: none. §13.6.1 preserved verbatim.

---

## Goodhart-trap audit on v4

The bugification operators themselves are a Goodhart-trap-prevention discipline:
- A test suite that achieves 100% line coverage by exercising "typical" CSD behaviour is a Goodhart-coverage trap; bugification breaks the ceteris-paribus by making "typical" itself adversarial.
- The post-state equivalence property prevents the trap "we exercised the bugified path but it produced a different terminal state, which we then accepted as 'expected'" — by construction the equivalence property forbids that escape hatch.
- The composability with `gen_recon_scenario` + partition prevents the trap "bugification finds bugs only in single-trade single-CSD-policy regimes".

**No new Goodhart traps observed in v4.**

---

## Pareto judgment

**PARETO_REACHED in correctness domain.**

- Zero blockers.
- Zero new majors.
- The four R3 residual majors I named are correctly classified as non-blocking carry-overs to v11.1; the proposal explicitly so notes at line 2706.
- The single R3 blocker (N-B-3) is closed cleanly, additively, with the exact two-paragraph patch I asked for in R3 (TA-DS-13 + BugificationOperator), plus a sixth bugification operator that I did not ask for (`with_inverted_leg_order`) and which is genuinely useful.

**Recommended action:** Submit v4 to FORMALIS-arbiter for independent Pareto declaration. From the correctness-architect lens, v4 is submission-ready.

**Single most important property in the catalogue (unchanged from R1, R2, R3):** DS1 (Economic-Exposure-at-T). v4 preserves DS1's hybrid CT+RT mechanism unchanged. Credit.

**Single most important new content in v4:** §13.5.5 BugificationOperator. The internalisation of the FoundationDB discipline — "adversarial threat models catch the obvious; bugification catches the unobvious-but-legal" — into the spec text itself is the methodological win of this round. It means the next round of adversarial review on this spec will not need to re-litigate the category distinction; it can move directly to enumerating new bugification operators as the system grows.

---

*Reviewer: Correctness Architect. R4 closure-check brief. Cross-referenced R3 reviews/correctness.md, proposal_v4.md §13.5.5 + §15.6.2 R3 closure record + line 2706 explicit carry-over classification.*
