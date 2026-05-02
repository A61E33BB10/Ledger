# Round 3 Adversarial Closure Check — Correctness Architect

**Subject.** `proposal_v3.md` — Phase 3 Round 3 Settlement Team revision of the Deferred-Settlement specification.
**Reviewer.** Correctness Architect (Will Wilson, deterministic-simulation lens).
**Date.** 2026-04-30.
**Scope.** Verification of R2 residual closure for **this reviewer's** open items: B-1.f (DS19), B-3 partial (generators), B-4 not-closed (differential oracle), B-5 partial (fault catalogue: network split + bugification), N-B-1 (conservation framing), N-B-2 (DS19 numbered). Plus: an honest scan for new R3-introduced regressions in the correctness domain.

---

## Verdict

**ACCEPT_WITH_CHANGES.** Pareto **NOT** reached in this reviewer's domain.

**Why not Pareto.** Five of six R2 residuals from this reviewer are now CLOSED — the four high-leverage items (N-B-1, N-B-2, B-3 generators, B-4 differential oracle) are closed cleanly; B-3 generators are closed cleanly; B-1.f is closed via DS19; the §13.6 reference interpreter is the right shape and §13.6.3 mutation testing is honest. **Credit where due:** the v3 closure of N-B-1 (§3.6 delta-form framing reconciled with §7.5 absolute-form theorem via the v10.3 §2.7 inception-move discipline) is exactly what was asked for. The DS19 statement (§11) with hybrid CT/RT decomposition and PT-DS-19 verification is exactly what was asked for. The §13.6.1 LedgerReferenceInterpreter spec is exactly the right oracle and the API shape (`Stream[Event] → InternalState`, total step, deterministic clock, ~2k LOC) is correct.

**The one remaining BLOCKING item is the same one R2 flagged as M-4 and v3 has not addressed:** *fault catalogue completion — explicit network split protocol AND bugification operators*. R3 closes operational outage (§4.5.4-bis CSD outage) which is a related but distinct fault class; it does NOT close the FoundationDB-class "legal-but-pathological CSD behaviour" injection nor the explicit "Ledger ↔ CSD network partition" fault test. These remain absent.

The gap is **two paragraphs** of additive content. R3 is otherwise sound.

---

## R2 closure table — by R2 finding ID (this reviewer)

| R2 finding | v3 status | v3 location | Reviewer verdict |
|---|---|---|---|
| **B-1.f** Witness-Identity Determinism (DS19) | **CLOSED** | §11 DS19 + §11 type-vs-runtime row + PT-DS-19 verification list | DS19 is now a numbered invariant. Statement is biconditional (`K equal ⇔ semantically_identical`); both directions explicitly justified (forward: JCS canonicalisation + collision-resistance; reverse: hash determinism over totally-ordered argument list). Hybrid CT/RT. Severity BLOCKING. **Clean.** |
| **B-3** Generators (3 sub-blockers) | **CLOSED** | §13.4.4 + §13.4 G-DS-1/2/3 + boundary-case shrink discipline + `gen_recon_scenario` | All three sub-items closed. The boundary-case shrink discipline (`gen_partial_chain_depth` shrinks to 1 not 0; `gen_corporate_action_in_window` shrinks to 1-CA not zero) is the right discipline and was identified at R3 by testcommittee. **Clean.** Caveat: M-2 (generator coverage gate — "every inhabitant of every closed sum exercised at least once per test class") is **not** explicitly added to PO-8 in v3. Carried as residual minor. |
| **B-4** Differential testing oracle | **CLOSED** | §13.6.1 LedgerReferenceInterpreter | Pure-functional, single-threaded, total-step, deterministic-clock, no Temporal client, ~2k LOC. The boxed differential-equality assertion `LedgerReferenceInterpreter(E) = ProductionRuntime(E)` is the correct oracle specification. Owed for v11.0 release; ETA stated. **Clean.** |
| **B-5** Fault catalogue (network split, Byzantine clock, bugification, forged envelope) | **PARTIAL — STILL OPEN** | §4.5.4-bis (CSD operational outage); §13.5.3 threat model A1..A10 (incl. A8 clock-skew, A2 gateway, A5 MITM); TA-DS-5 clock-skew | **Network split between Ledger and CSD: still not named as a fault test** — operational outage is a one-sided unavailability, not a partition. **Bugification (legal-but-pathological CSD behaviour): still absent.** No `BugificationOperator` strategy; no test-class for "CSD always partials at minimum", "CSD always restates 1-share at EOD", "CSD delays each sese.025 by exactly the watchdog interval", etc. The R2 ask was specific (R2 §"Fault catalogue", four examples enumerated); v3 absorbs none of them. See N-B-3 below. |
| **N-B-1** Conservation table delta vs theorem absolute | **CLOSED** | §3.6 R3-B1 framing correction paragraph + delta-form formula + v10.3 §2.7 inception-move reference + closing reconciliation paragraph | The framing is now explicit: §3.6 tables are delta-form (`Σ Δw_t(u) = 0` per transaction over the constant universe `\mathcal{W}`); §7.5 theorem is absolute-form (`Σ_w w_t(u) = 0`); the two are inductive-step / inductive-conclusion of the same theorem; v10.3 §2.7 inception-move discipline establishes the absolute baseline via `w_genesis_inception`. **The Goodhart trap exemplar is closed.** Clean. |
| **N-B-2** DS19 not a numbered invariant | **CLOSED** | §11 DS19 (full statement) + PT-DS-19 + type-vs-runtime row | See B-1.f above. Closed. |

**Subtotal:** 5 CLOSED, 1 PARTIAL (B-5 network split + bugification). The partial is the new blocker N-B-3 below.

---

## §11 DS19 — numbered invariant check

DS19 is now numbered. The statement is biconditional and both directions are reasoned:

```
K(v, P, L, t) = hash_jcs(v, L, t, P)
∀ε₁, ε₂ ∈ EnvelopeRegistry: K(ε₁) = K(ε₂) ⇔ semantically_identical(ε₁, ε₂)
```

Forward direction: enforced by JCS canonicalisation (RFC 8785, no key-reorder equivocation) + collision-resistance.
Reverse direction: enforced by determinism of hash_jcs over totally-ordered argument list.

Type-vs-runtime row: hybrid; CT = hash_jcs total over typed envelope; RT = collision-check at L_11 intake.
Severity: BLOCKING.
PT-DS-19: tests `K(v,P,L,t) = K(v,P,L,t)` (trivial reflexivity) AND `K(v,P,L,t) ≠ K(v',P,L,t)` for `v' ≠ v` (and similar for the other arguments). Mutation test pinned: dropping `schema_version` MUST cause PT-DS-19 to fail (this validates R3-B9 fix).

**This is exactly what R2 asked for.** Closed.

---

## §13.6.1 LedgerReferenceInterpreter — pure-functional, single-threaded, total differential oracle?

Verified against the four specification properties:

1. **Pure-functional.** Yes — input is `Stream[Event]`; output is `SnapshotState`; no side effects; named.
2. **Total over closed sums.** Yes — "exhaustive `match` on input class" over closed-sum event types (§5.2 + §6.5).
3. **Single-threaded.** Yes — events consumed in `(t_known, dedup_key)` lex order.
4. **Deterministic clock.** Yes — injected `ClockOracle`; replay over same input yields identical output.

Plus:
- No Temporal client (saga simulated as state-machine over event stream) — correct.
- Implementation footprint ~2k LOC, OCaml or Python — realistic.
- Differential oracle equality boxed as `LedgerReferenceInterpreter(E) = ProductionRuntime(E)` over replay-deterministic-equivalent inputs — this is the canonical specification.

**Caveat (a residual minor, NOT blocking):** the spec says the reference interpreter enforces "DS1, DS2 (conservation), DS3 (recon identity), DS4 (witness), DS5, DS6, DS7, DS9, DS10, DS11a, DS11b, DS17, DS18, DS19" plus all v10.3 P1..P20. The list is correct but the *enforcement mechanism* is unstated — does the interpreter assert these on every step (and halt if violated)? Or does it merely produce state that satisfies them by construction? The former is the correct behaviour for a differential oracle. Add one sentence: "Each invariant is asserted at every step transition; any violation halts the interpreter with a localised diagnostic." Not blocking; m-9.

**Verdict.** §13.6.1 closes B-4. Clean.

---

## §3.6 conservation framing — Σ Δw = 0 + v10.3 §2.7 reference?

Verified. The R3-B1 framing correction is in place at §3.6 lines 392–426:

- Header: "Conservation summary across the four states (delta form — `Σ Δw_t(u) = 0` over all moves at t)".
- Explicit framing paragraph: "v3 R3-B1 framing correction. R2 jane_street B-1 / correctness N-B-1 noted that the v2 §3.6 tables sum *deltas* against a `pre-trade ≡ 0` baseline while §7.5 Conservation Lifting Theorem is stated in absolute form `Σ_w w_t(u) = 0`. Both framings are valid; v3 pins the §3.6 tables explicitly in **delta form** and re-anchors them to v10.3's inception-move discipline."
- Delta-form formula: `Σ_{m ∈ τ(t)} Δw_m(u) = 0`.
- Inception-move discipline paragraph (v10.3 §2.7 reference): `w_genesis_inception` wallet is named; `w_genesis.own(USD) = -1,000,000.00` from inception is the explicit absolute-form contra.
- Closing reconciliation paragraph: "absolute form per §7.5 Conservation Lifting Theorem (over real + cpty_virtual + csd_virtual + inception, including the v10.3 §2.7 `w_genesis_inception` wallet)".

**The Goodhart trap exemplar I flagged in R2 is closed.** A property test that mechanically reads §3.6 tables now matches a property test that mechanically applies §7.5 — both produce zero, and the framing-mismatch trap is no longer a silent agreement-by-construction. Clean.

---

## §13.4 Goodhart traps closed?

Verified.

- **G-DS-1** (quick-finality bias) — closed; empirical-distribution sampling pinned in `L_7^P.GeneratorDistributionPin`; uniform draws forbidden at code-review.
- **G-DS-2** (per-class conservation) — closed; per-`(unit_class, wallet_class)` tuple assertion auto-generated; isolation to one class-unit pair on violation.
- **G-DS-3** (record-and-replay LLM tests) — closed; hand-authored from spec; LLM-assisted refactoring forbidden for input-space choice; code-review hard-fails on `learn_from_traces(...)` patterns.

The boundary-case shrink discipline (introduced in R3 in response to testcommittee N-2/N-4) is itself a Goodhart-trap-prevention: shrinking a `_in_window` generator to "no-CA" turns the test into a vacuous test that always passes. v3's discipline ("Generators whose name encodes a presupposition MUST shrink toward the minimum-non-trivial value of that presupposition") is exactly right and is enforced at code-review.

**Verdict.** §13.4 closes B-6 fully. Clean.

---

## Fault catalogue — network split, Byzantine clock skew, bugification all present?

| Fault | v3 status | v3 location |
|---|---|---|
| CSD partial responses | **CLOSED** | §6.4 + DS11a + DS11b |
| Duplicate finality | **CLOSED** | §4.5.1 dedup_key + DS6 |
| Finality-then-retraction (G5) | **CLOSED** | §6.5.5 commutativity table |
| Reorder of finality vs trade | **CLOSED** | §6.5.5 commutativity table; DS5 |
| Forged envelope (signature failure) | **CLOSED** | §4.5.1 Ed25519 verify; §13.5.3 A2/A5 |
| CSD operational outage (multi-day) | **CLOSED** in v3 | §4.5.4-bis + §6.5.8 OutageWatchdogWorkflow + nazarov R3-B10 |
| Replay attack on stale envelope | **CLOSED** in v3 | §13.5.3 A6 (30d hot retention; cryptographic ts_obs) |
| Equivocator (CSD signs two payloads same `tx_id`) | **CLOSED** | §13.5.3 A7 + TA-DS-2 + multi-source quorum §4.5.2 |
| Clock-skew adversary | **CLOSED** as threat model | §13.5.3 A8 + TA-DS-5 (≤5s bound) |
| Expired/revoked-key adversary | **CLOSED** in v3 | §13.5.3 A9 + §13.5.2 key-mgmt + TA-DS-11 CRL/OCSP |
| Mapping-version manipulation | **CLOSED** in v3 | §13.5.3 A10 + §13.5.1 MapperRegistry + TA-DS-3 |
| **Network split (Ledger ↔ CSD partition)** | **NOT NAMED** | — |
| **Bugification (legal-but-pathological CSD behaviour)** | **NOT NAMED** | — |

**Network split.** §4.5.4-bis CSD operational outage is a one-sided unavailability (CSD is degraded; we detect via watchdog and freeze). It is **not** a network partition: a partition is a bidirectional connectivity failure where each side may continue operating with stale state, and reconnection requires conflict reconciliation. Property test: "under simulated bidirectional partition between Ledger and CSD (each side processes its own queue), eventual reconnection produces the same final state as no-partition" — this is missing. The R2 ask was a TA-DS-11 named "network partition"; v3 uses TA-DS-11 for "CSD-finality-implies-counterparty-receipt + key-not-on-CRL", which is unrelated.

**Bugification.** The R2 ask was a §13.4.5 `BugificationOperator` strategy enumerating four legal-but-pathological CSD behaviours:
- A CSD that always sends `sese.025` 10 seconds before the matching `camt.054`.
- A CSD that always partials at exactly the legal minimum.
- A CSD that always restates 1 share at end-of-day.
- A CSD that delays each `sese.025` by exactly the watchdog interval `Λ_4`.

v3 absorbs none of them. The threat-model in §13.5.3 covers *adversarial* attacks (A1..A10) but not *legal-but-pathological* operating regimes. This is a category distinct from a malicious-CSD threat: a real-world, well-meaning CSD whose operational policy happens to land precisely on every test-suite blind spot. The FoundationDB lesson — and the reason we stress this — is that adversarial threat models catch the obvious; bugification catches the unobvious-but-legal. R2 named this; v3 has not absorbed it.

**Verdict on faults:** 12 of 14 closed (excellent absolute progress over v2's 5/9); **2 still missing — network partition and bugification.** This is exactly the residual M-4 from R2, unchanged in v3. **N-B-3 below** (single new blocker, but the gap is two paragraphs of additive content).

---

## NEW BLOCKING (v3-residual)

### N-B-3. Network partition + bugification still missing from fault catalogue

**Issue.** R2 M-4 listed two specific fault classes still missing in v2: **(a) Ledger ↔ CSD bidirectional network partition** and **(b) bugification operators for legal-but-pathological CSD behaviour**. v3 closes the *related-but-distinct* CSD operational outage (§4.5.4-bis) and the threat model (§13.5.3 A1..A10). It does NOT close the two original gaps.

**Fix (two paragraphs).**

1. **§13.5.3-bis or §4.5.4-ter — Network partition (Ledger ↔ CSD bidirectional).** New TA entry (TA-DS-13 since 11 and 12 are taken):

> **TA-DS-13 — Eventual reconnection convergence.** Under bidirectional network partition between Ledger and CSD lasting `Δt_partition`, both sides process their own inbound queues independently. On reconnection, the Ledger replays its outbound queue through the CSD and ingests the CSD's outbound queue; the dedup_key registry (DS6 + DS19) ensures at-most-once application. Property test PT-DS-13: under simulated partition of arbitrary `Δt_partition` ≤ T+5bd, reconciliation post-reconnect produces the same final state as no-partition. Detection signal: heartbeat absence ≥ `T_partition_grace`; routes to OutageWatchdogWorkflow if one-sided, partition-reconcile workflow if bidirectional.

2. **§13.4.5 — Bugification operators (legal-but-pathological CSD behaviour).**

```python
class BugificationOperator(Strategy):
    """Inject legal-but-pathological CSD behaviour. Each is spec-legal but
    adversarially constructed to land precisely on a test-suite blind spot."""
    def with_minimum_partial(self):    # always partials at the legal minimum
    def with_eod_restatement(self):    # always restates 1-unit at EOD
    def with_max_legal_delay(self):    # always delays sese.025 to last legal moment
    def with_inverted_leg_order(self): # always camt.054 before sese.025 (inverted DvP)
    def with_watchdog_grazing(self):   # delays each sese.025 by exactly Λ_4 (watchdog interval)
```

The bugification operators MUST be exercised under at least one test class per generator family (`gen_failure_reason`, `gen_settlement_window`, `gen_partial_chain_depth`, `gen_corporate_action_in_window`). Coverage gate: a CSD bugified under any single operator MUST produce identical post-state to a non-bugified CSD with the same total event sequence (DS5 replay determinism; DS6 idempotency; DS19 witness identity).

**Why this matters.** This is not redundant with §13.5.3 threat model. Threat model = adversary trying to corrupt state. Bugification = well-meaning operator whose policy happens to break every property test that was implicitly tuned to "typical" behaviour. The FoundationDB simulation testing literature — and our own correctness discipline — treats these as separate categories because they expose different bug classes. Threat model is closed in v3 via signature/dedup/quorum/CRL/audit. Bugification has zero coverage.

**Fix scope.** ~½ page total. Block on this for Pareto.

---

## Remaining MAJOR (carried from R2 + new)

### M-1 (carried from R2). Non-determinism boundary catalogue still scattered

§13.6 is a new section but is dedicated to oracle/TLA/mutation. There is no §13.7 or §11.bis enumerating ALL non-deterministic boundaries with `injectable / not-injectable / mitigated-via-trust-assumption` classification in a single table. The boundaries remain scattered across §0.4 (ts_obs/ts_known), §6.5.1 (tx_id), §6.5.5 (commutativity), §6.5.6 (dedup_key), §13.5 (TA-DS-5 clock skew, TA-DS-12 attempt_seq durability), §4.5 (envelope dedup), §13.5.3 (A8 clock-skew adversary). **~1 page bookkeeping task; not blocking but should land in R4.** Add §13.7 — single table.

### M-2 (carried from R2). Generator coverage gate not in PO-8

§13.4.4 lists generators; §13.4 G-DS-2 names per-class conservation; but PO-8 does not name the coverage gate "every inhabitant of every closed sum is exercised in every test class". A `gen_failure_reason` that always returns `DeadlineMissed` will type-check, pass, and find zero `CsdReject` bugs. Add to §13.2 PO-8 entry: "Coverage gate: framework checks histogram showing every inhabitant of every closed sum (`LifecycleState`, `failure_reason`, `CsdRejectCode`, `SettlementWindow`, `CorpActionKind`) is exercised at least once per test-class run; CI fails on any zero-hit inhabitant." Without this, B-3 is closed in letter, not spirit.

### M-7 (carried from R2). R1 B-1.a same-(w,u)-multi-trade interleaving still partial

R2 noted that §6.5.5's last commutativity row "Cross-trade signals (different `tx_id`) — independent" is the easy case; the hard case is two trades touching the same `(real_wallet, unit)` but different `tx_id`s, with finality witnesses interleaved. v3 adds `gen_recon_scenario` (testcommittee N-6 closure) which is the right primitive but the same-`(w,u)` interleaving property is not explicitly listed in §13.3 walking-skeleton or §13.4.4 generators. **Add a property test under DS5/PO-8** specifically for "two trades on same `(w_real, u)`, different `tx_id`, all interleavings of finality witnesses produce same final state". `gen_recon_scenario` covers it implicitly when `cpty contras > 1`, but the explicit test pinning is missing.

### M-9 (new minor — see §13.6.1 caveat above). Reference interpreter assertion semantics

§13.6.1 lists invariants the interpreter "enforces" but does not specify whether enforcement is per-step assertion (halt on violation, localised diagnostic) or post-state property. For a differential oracle, per-step is required. Add one sentence.

---

## Minor (m-N, v3)

**m-1.** §11 invariant count is "11 invariants" in the type-vs-runtime row title (line 1954) but only 11 numbered DS rows (DS1, DS3, DS4, DS7, DS9, DS10, DS11a, DS11b, DS12, DS17, DS18, DS19) — that's actually 12. Re-count or re-title.

**m-2.** §3.6 closing paragraph (line 426) lists the absolute-form universe as "real + cpty_virtual + csd_virtual + inception". But §3.6 tables only show three columns per unit (real + cpty_virtual + csd_virtual_mirror). The inception column is implicit (constant `-1,000,000.00`). For pedagogical completeness, add a fourth column showing `w_genesis_inception(USD) = -1,000,000.00` constant across all five rows. ~5 lines.

**m-3.** §13.6.1 says reference interpreter is "OCaml or Python". Pick one. Mixed-language reference oracles are a coordination smell.

**m-4.** §13.6.2 lists 15 invariants encoded in TLA+: DS1, DS3, DS4, DS5, DS6, DS7, DS9, DS10, DS11a, DS11b, DS12, DS17, DS18, DS19, plus absolute-form Conservation Lifting Theorem. That's 15. But DS5/DS6 are absent from §11 numbered list (they are in §11.A "restated v10.3" not as numbered DS). The TLA+ invariant naming should match §11 numbering scheme. Cosmetic.

**m-5.** §11 DS19 (line 1939) uses notation `K(ε)` where the formal definition takes `(v, P, L, t)` arguments. The biconditional reads `K(ε₁) = K(ε₂) ⇔ semantically_identical(ε₁, ε₂)` but earlier line says `K(v, P, L, t)` is the formula. Two-page-later read: which is canonical? Make `K` overloaded with explicit type.

---

## What works in v3 — credit where due

1. **§3.6 R3-B1 closure is exemplary.** The framing reconciliation (delta-form is inductive step, absolute-form is inductive conclusion, both tied to v10.3 §2.7 inception-move discipline) is exactly the right structural fix for the Goodhart trap I flagged in R2.

2. **§11 DS19 is exactly what was asked for.** Biconditional, both directions justified, hybrid CT/RT, severity BLOCKING, PT-DS-19 listed, mutation test pinned, threat-model coverage stated. This is the model for how a missing invariant should be added in a focused patch round.

3. **§13.6.1 LedgerReferenceInterpreter.** Pure-functional, total over closed sums, single-threaded, no Temporal client, deterministic clock, ~2k LOC, owned by testcommittee. The boxed differential-equality is the canonical specification.

4. **§13.6.2 TLA+ at v2/v3 fidelity.** Variables match v2/v3 ontology; fairness regime stated (weak on `discharge_step`, strong on `csdr_penalty_accrual`); sizing pinned (`|W|=4, |U|=2, |trades|=4, depth=8`); 15 invariants encoded.

5. **§13.6.3 mutation testing.** Honest acknowledgement of the SQL-projection-mutation gap with the §12.1.1 phantom-typed wallet handles as the explicit mitigation. The four DS1 mutations enumerated. 80% / 100% targets committed.

6. **Boundary-case shrink discipline.** "Generators whose name encodes a presupposition MUST shrink toward the minimum-non-trivial value of that presupposition" — this is a generator-level Goodhart-trap-prevention discipline that I did not explicitly call out in R2, and v3 added it spontaneously in response to testcommittee N-2/N-4. Genuine discipline-internalisation by the Settlement Team.

7. **§13.5.3 threat model A1..A10.** Ten attacker classes with attack / mitigation / residual risk. Cross-references to TA-DS-N and §13.5 contracts. The defence-in-depth design (signature + dedup + quorum + CRL + audit chain) is correctly named as robust against single-class attacks; multi-class collusion is honestly acknowledged as residual.

8. **§15.6 R2 closure record.** A 17-row table mapping every R2-residual to its v3 closure section with one-line summary. Saves the R3 reviewer ~30 minutes per item.

---

## Pareto judgment

**Pareto NOT reached.** One blocker (N-B-3) and four majors (M-1 boundary catalogue, M-2 coverage gate, M-7 same-(w,u) interleaving, M-9 reference interpreter assertion semantics) prevent zero-blocker-zero-major status.

**However:** the gap is **two paragraphs**.
- N-B-3 = §13.4.5 bugification operators (½ page) + TA-DS-13 network partition (½ page).
- M-1 = §13.7 single-table boundary catalogue (~1 page bookkeeping).
- M-2 = one paragraph in PO-8.
- M-7 = one property test pinned.
- M-9 = one sentence in §13.6.1.

**Total work to Pareto: ~1 person-day.**

**Recommended R4:** one revision pass closing N-B-3, M-1, M-2, M-7, M-9. Minor m-1..m-5 absorbed in copy-edit. R4 panel: same 6 reviewers, single-round closure verification.

**Verdict.** ACCEPT_WITH_CHANGES. The Settlement Team has executed R3 with discipline — five of six R2 residuals (this reviewer) closed cleanly, several with exemplary framing. The remaining gap is the original R2 M-4 fault-catalogue residual, which has been carried unaddressed across two rounds. **Single most important item to close before R4: N-B-3 bugification + network partition.** The FoundationDB lesson cannot keep being deferred — bugification is the technique that finds the bugs the threat model misses by construction.

**Single most important property in the catalogue (unchanged from R1, R2):** DS1 (Economic-Exposure-at-T). v3 preserves DS1's hybrid CT+RT mechanism and the type-vs-runtime decomposition. Credit.

---

*Reviewer: Correctness Architect. R3 closure-check brief. Cross-referenced R2_consolidated_findings.md, proposal_v3.md §3.6 / §11 / §13.4 / §13.5.3 / §13.6, and prior R1 + R2 reviews.*
