# Round 3 Adversarial Closure Check — proposal_v3.md
## Reviewer: NAZAROV — Data Layer Architect
## Date: 2026-04-30

**Verdict: PARETO_REACHED** (on the boundary axis).

The Settlement Team has closed every R2 item I left blocking and every R2 unmitigated major I left open. The closures are not cosmetic; they are substantive and correct. The boundary is now held to my satisfaction. v3 is additive only over v2 — no architectural regressions, no silent re-deferrals, no untyped trust newly introduced. I declare PARETO_REACHED on my axis.

---

## Section 1 — R2 Closure Table

| R2 finding | Severity (R2) | v3 location | Status | Verification |
|---|---|---|---|---|
| **N-1** dedup_key omits `schema_version` | BLOCKING | §4.5.1 line 814 | **CLOSED** | Formula is now `dedup_key = hash_jcs(schema_version, source_lei, ts_obs, payload)`. The two-line fix landed exactly as specified, with an inline comment crediting R3-B9 and pointing to DS19. The argument order (schema_version first) is consistent with DS19's `K(v, P, L, t) = hash_jcs(v, L, t, P)`. |
| **N-2** CSD operational outage protocol re-deferred to §14 | BLOCKING | §4.5.4-bis (NEW, lines 878-904) | **CLOSED** | The outage protocol is now in spec, not in §14. Trigger named (`duration > T_outage_grace`, default 4h, configurable in `L_7^P.OutagePolicy`). Four-step protocol (a-d) covers freeze, FSM preservation, L_18 break preservation with new `outage_window` field, manual `OUTAGE_RESUME` (CORRECTION-class, four-eyes, `OPERATIONS_HEAD`). Multi-day tolerance addressed via §10.7 retention + replay determinism (DS5) on resumption. T2S 2023 and DTC 2024 night-cycle incidents named as covered scenarios. **Capability scoping discipline preserved**: outage freeze does not introduce a new writer; it gates the existing `SettlementSaga` writer (DS17 unchanged). This is the structural change I asked for. |
| **N-3** Restatement model A vs B ambiguity | MAJOR | §11.A (lines 1987-1989), §6.5.5 row 4 (line 1207), §6.5.9 (RestatementWatchWorkflow) | **CLOSED** | v3 commits to Reading (a) explicitly: "every restatement is a `t_known` update and creates a new L_15 row at `t_known(t)`; the original L_15 row is **immutable** and remains queryable via `as_of(original_t_known)`." Reading (b) is explicitly rejected with a stated reason (conflicts with DS5 replay determinism over the canonical bitemporal scan key). The §6.5.5 commutativity row "restated sese.025(tx_id, q')" preserves the "Reading (a): treat as new obligation" annotation; the §11.A bitemporal honesty note seals the commitment. No more A/B drift. |
| **N-4** ISO 20022 mapper-version determinism contract | MAJOR | §13.5.1 (NEW, lines 2349-2358) | **CLOSED** | Mapper-version pinning is now explicit. `(message_kind, payload_schema_uri)` keyed in `L_7^P.MapperRegistry`; canonical mapping AND canonical reverse mapping per entry; schema migrations bump mapper version (prior version remains queryable for replay determinism over historical envelopes); mapper-version mismatch on intake routes to `wf-schema-quarantine` (not silent default); round-trip property test per mapper version. The "version-pinned per mapper *implementation*" requirement I made in R2 is met. The "emitting `UnmappableMessage` quarantine on failure rather than silent default" requirement is met via the explicit `wf-schema-quarantine` route. |
| **N-5** Key management contract (rotation, revocation, recovery, historical verification) | MAJOR | §13.5.2 (NEW, lines 2360-2370) | **CLOSED** | Key lifecycle is now five-stage: issuance / rotation / revocation / expiry / audit. Issuance: `L_7^P.TrustRoots[source_lei]` with `(public_key, valid_from, valid_to, key_purpose)`; key purposes are closed-sum; cross-purpose use rejected at envelope verification. Rotation: scheduled per key purpose; new entry created, old `valid_to` set to rotation timestamp. Revocation: CRL entry in `L_7^P.CertificateRevocationList`; envelope verification at intake checks CRL and OCSP; revoked-key signature rejected and routed to `wf-revoked-key-break`. Expiry: hard `valid_to`; verify past `valid_to` is rejected. Audit: `L_7^P.TrustRoots` is bitemporal; `(t_obs_key_event, t_known_key_event)` recorded for every event. The verification chain is stated as a predicate over the registry, with explicit historical-verification semantics (`env.ts_obs ∈ [key.valid_from, key.valid_to]` — the boundary case I called out in R2). The line "envelope verification is bitemporally pinned to the key active at `ts_obs`" is in the verification predicate's `valid_from/valid_to` constraint. **One residual nit**: the predicate says "key not on `CRL_at(env.ts_known)`" rather than "CRL active for the verifier *at the time of re-verification*" — which is the correct semantics for replay (a key revoked AFTER an envelope's original ingest should not retroactively invalidate that envelope's prior acceptance). I read this as the intended semantics given the bitemporal `valid_to` envelope handling above; if not, please confirm in v3.5 (not blocking). |
| **N-6** Threat model as first-class artefact | MAJOR | §13.5.3 (NEW, lines 2372-2387) | **CLOSED** | Ten attacker classes (A1..A10) with attack/mitigation/residual-risk for each: malicious CSD, malicious gateway, malicious operator, malicious counterparty, network adversary, replay attacker, equivocator, clock-skew attacker, expired-key attacker, mapping manipulator. The "malicious gateway" mitigation is exactly what I asked for in R2 ("Ed25519 signature verify on raw bytes signed by source LEI, not by gateway — gateway cannot forge CSD signature"). The "equivocator" row is paired with TA-DS-2 detection. The "clock-skew attacker" row is paired with TA-DS-5 ±5s discipline. The "expired-key attacker" is paired with §13.5.2 CRL/OCSP. Cross-references to TAs and invariants are present per row. The closing paragraph names the limits of the model honestly (single-class robustness; multi-class collusion is residual). This is the audit-grade artefact I asked for. |
| **N-7** Per-witness-class freshness contract | MAJOR | §13.5.4 (NEW, lines 2389-2403) | **CLOSED** | Seven witness classes with freshness SLA + stale-trigger: CSD finality (4h post-EOD), custodian camt.053 (24h), counterparty affirmation (2 BDs), cum/ex CA ex-date (pre-ex-date), manual-override approval (same business day), schema-version migration notice (30 days advance), key-rotation notice (7 days advance). Each row names the trigger workflow (`wf-confirm-break`, `wf-ca-break`, `wf-key-rotation-break`, etc.) and the auto-FAIL discipline ("Stale-witness handling is **never** an auto-FAIL of the underlying obligation. It is a `BreakRegister` event with the obligation's lifecycle continuing"). The bitemporal pinning invariant I asked for in R2 ("recon engine consumes `nostro_external` from a bitemporally pinned snapshot, not a live cache") is implicit in the "stale past 48h → manual escalation" discipline plus DS5 replay determinism (recon at `t_known = old` reproducible from bitemporal pinned witnesses). I would prefer this stated explicitly as one line in §4.7.1 in a future patch; not blocking for Pareto. |
| **N-8** TA-DS-11 (CSD-implies-counterparty) and TA-DS-12 (attempt_seq durability) | MINOR/MAJOR | §13.5 (lines 2342-2345) | **CLOSED** | TA-DS-11 added: "CSD-finality-implies-counterparty-receipt: a CSD finality message logically implies the counterparty has received delivery (cash or securities). Falsifiable when CSD reports finality but counterparty disputes receipt within a 1bd window." Detection signal: CSD `sese.025` discharge AND counterparty `affirmation = REJECTED` within 1bd; signing-key freshness via CRL/OCSP at envelope verification. Owner: nazarov + TrustOps + isda. TA-DS-12 added (testcommittee N-5): `attempt_seq` durability across CaN and multi-region failover. Both registered with detection signals and owners. Quarterly review cadence applies. |
| **N-9** Watchdog `silence_attestation` signed by `our_lei` rather than dedicated `watchdog_lei` | MINOR | §4.5.3 line 853 (unchanged); §6.5 watchdog implementation pinned via `SideEffect ClockActivity` (R3-M3 / temporal N-2) | **NOT CLOSED — non-blocking** | v3 retains `source_lei = our_lei` for silence_attestation. The watchdog implementation form is now pinned via `SideEffect ClockActivity` (per R3-M3 / temporal N-2 closure in §6.5.9), which moves the determinism concern but not the capability-typing concern I raised in R2. The R3 must-close list did not include N-9 and the prompt does not require it. I flag it for v3.5 or v4: "the silence_attestation should be emitted by the watchdog activity under a dedicated `watchdog_lei` capability key, not the general `our_lei`." Not Pareto-blocking; structural improvement deferrable. |
| **N-10** `tx_id` derivation and restatement | MINOR | Subsumed by N-3 closure | **CLOSED (dependency)** | I noted in R2 that N-10 evaporates if N-3 commits to Reading (a). N-3 has committed to Reading (a) firmly (§11.A bitemporal honesty note). Therefore N-10 is closed. |

---

## Section 2 — Verification of the prompt's six explicit checks

| Check | v3 location | Result |
|---|---|---|
| §4.5.1 dedup_key includes `schema_version`? | line 814 | YES. `dedup_key = hash_jcs(schema_version, source_lei, ts_obs, payload)` with inline credit to R3-B9 and pointer to DS19. |
| §4.5.4 (or §6.5) CSD operational outage protocol IN spec (not §14 punt)? | §4.5.4-bis (lines 878-904) | YES. Full protocol: trigger, four-step procedure (a-d), multi-day tolerance with §10.7 retention + DS5 replay, capability scoping discipline preserved, real incidents named. |
| §13.5.1-§13.5.4 mapper-version, key-management, 10-attacker threat model, freshness contracts present? | §13.5.1, §13.5.2, §13.5.3, §13.5.4 | YES on all four. Mapper-version: `L_7^P.MapperRegistry` keyed by `(message_kind, payload_schema_uri, mapper_version)`. Key-management: five-stage lifecycle with CRL/OCSP at envelope verify. Threat model: A1-A10 with mitigation and residual risk. Freshness: seven witness classes with SLA + stale-trigger. |
| §13.5 TA-DS-11 (CSD-implies-counterparty) and TA-DS-12 (attempt_seq durability) added? | §13.5 lines 2342-2345 | YES. Both registered with detection signals and owners. TA-DS-11 owner: nazarov + TrustOps + isda. TA-DS-12 owner: temporal + testcommittee. |
| §6.5.5 / §11.A: Reading (a) restatement model committed? | §6.5.5 row 4 (line 1207) + §11.A bitemporal honesty note (lines 1987-1989) + §6.5.9 (c) RestatementWatchWorkflow | YES. Reading (a) committed; Reading (b) explicitly rejected with stated reason (conflicts with DS5). RestatementWatchWorkflow catalogued. |

All five checks pass.

---

## Section 3 — New Issues (introduced or surfaced in v3)

None of significance on the boundary axis.

I scanned v3 for new untyped trust, silent fallback, mutable history, or unspecified attestation paths introduced by the v3 patches. Nothing found. The v3 patches are additive over v2 and do not weaken any envelope, aggregation, or freshness discipline.

One observation worth noting (not a finding):

**O-1 (cosmetic).** The §13.5.2 key-management predicate `envelope_signature_verify(env)` references `OCSP_responder_says_good(key, env.ts_known)` — a synchronous check against the OCSP responder at envelope verification time. For replay (re-verification of a 12-month-old envelope), the OCSP responder may give a different answer today than at original ingest. The intended semantics is presumably "OCSP-was-good at original ingest, recorded in the verification log; replay uses the recorded answer, not a live OCSP query." This is consistent with the bitemporal `t_obs ∈ [valid_from, valid_to]` discipline in the predicate, but worth pinning explicitly in a future patch as: "replay verification consumes the bitemporally-pinned OCSP record from `L_11.envelope_verification_log` rather than re-querying the OCSP responder." Not blocking.

---

## Section 4 — Pareto Judgment

**Boundary axis: Pareto REACHED.** Every R2 BLOCKING item closed; every R2 unmitigated MAJOR closed; one R2 MINOR (N-9 watchdog_lei) deferred non-blockingly per the prompt's must-close list; the cosmetic observation O-1 above is documentation not architecture.

**§15.6 closure record audit.** The §15.6 R2 closure record (lines 2599-2643) is honest. Each R3-B and R3-M item has a one-line summary that accurately reflects the v3 patch. No misrepresentation; no overclaiming. The new-issues regression-roll-in table (lines 2630-2643) is comprehensive — 11 new-issue items closed via additive patches, including my N-3 (restatement) and N-8 (TA-DS-11) explicitly.

**§15.7 convergence claim audit.** "Zero blocking remaining; zero unmitigated major remaining." On my axis, this claim holds. On other reviewer axes, I cannot speak — but the §15.6 closure record gives a per-reviewer-finding audit that an arbiter can verify directly.

**§15.8 Pareto-arbiter ruling.** The team correctly identifies that R3 closure-verification by the same six R2 reviewers is the test. I am confirming closure on the nazarov-axis findings.

**Overall.** The boundary is held. The work is done. Hand off to the arbiter.

---

## Section 5 — What v3 Got Right (preserve)

1. **§4.5.1 envelope formula.** The dedup_key fix is exactly the right shape: `hash_jcs(schema_version, source_lei, ts_obs, payload)`. The inline comment crediting R3-B9 and pointing to DS19 is good craft.
2. **§4.5.4-bis CSD outage protocol.** The four-step protocol with `OUTAGE_RESUME` as a CORRECTION-class transaction (four-eyes, `OPERATIONS_HEAD`) is structural-grade. The capability scoping discipline ("the freeze does not introduce a new writer; it gates the existing `SettlementSaga` writer") preserves DS17 cleanly. T2S 2023 / DTC 2024 named as covered scenarios is the audit-grade detail I want to see in a real spec.
3. **DS19 elevation.** Lifting witness-identity determinism to a numbered invariant with hybrid CT+RT decomposition closes a hole I had not myself flagged in R1 (correctness B-1.f did). The mutation-test discipline ("a mutation that drops `schema_version` from the formula MUST cause PT-DS-19 to fail") is a strong control.
4. **§13.5.2 key-management contract.** The five-stage lifecycle, the CRL/OCSP precondition before signature verify, the bitemporal `valid_to` envelope handling, the closed-sum `key_purpose` enum that rejects cross-purpose use — this is the contract I asked for in R2 N-5.
5. **§13.5.3 ten-attacker threat model.** A1-A10 with mitigation and residual-risk per row. The honest closing paragraph ("multi-class collusion is a residual, mitigated only via cross-functional controls") is exactly the right tone for an audit artefact.
6. **§11.A bitemporal honesty note.** The explicit commitment to Reading (a) and the explicit rejection of Reading (b) with stated reason ("conflicts with DS5 replay determinism over the canonical bitemporal scan key") is the discipline I want to see whenever a spec faces a model dichotomy.
7. **§13.5 quarterly review cadence.** Pinned in `L_7^P.TrustAssumptionReview`; registry version bumps trigger re-review of dependent invariants. The TA registry is now a living artefact, not a one-off table.
8. **No silent re-deferrals to §14.** v2 had the §14 punt for CSD outages; v3 closes it. v3 has its own §14 (out-of-scope) but I scanned it for re-deferred items; nothing on the boundary axis is silently re-deferred.

---

Hold the boundary held. The boundary is held to my satisfaction.

— NAZAROV, 2026-04-30
