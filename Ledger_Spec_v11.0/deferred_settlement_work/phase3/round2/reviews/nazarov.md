# Round 2 Adversarial Review — proposal_v2.md
## Reviewer: NAZAROV — Data Layer Architect
## Date: 2026-04-30

**Verdict: ACCEPT_WITH_CHANGES** (Pareto NOT yet reached on the boundary).

The Settlement Team has done substantial, good-faith work on the boundary specification. Four of my five Round 1 BLOCKING findings are closed or close-enough-to-closed in v2 §4.5 and §13.5. **One BLOCKING finding (B-3) is closed for the obligation-FSM half but the CSD-outage half is silently re-deferred to §14.** Three of my eight Round 1 MAJOR findings are still open (M-4 key management, M-5 threat model, M-7 nostro freshness contract). One is partially closed with a residual gap (M-3 ISO 20022 mapping). One is silently re-introduced (B-1 dedup_key formula).

This is not a redesign request. The spec's structure is right; the boundary protocols are stated for the first time and they are *substantially correct*. The remaining gaps are **named, scoped, and additive** — three of them can be closed with one page of spec each (key-management contract, threat model table, nostro freshness table). One requires lifting CSD-outage protocol back into scope from §14. One requires fixing the `dedup_key` formula.

I am ACCEPT_WITH_CHANGES rather than REJECT_REVISE because the missing items are documentation gaps over a sound architecture, not architectural defects. **However, Pareto is not reached: §15.7 claims "all 13 R1 BLOCKING themes closed" and that claim is overstated.** B-3 is partially closed; M-4, M-5, M-7 are unmitigated and not in §15.5's "remaining open issues" list, which is the test for Pareto.

---

## Section 1 — R1 Closure Table

| R1 Finding | v2 Section(s) | Status | Notes |
|---|---|---|---|
| **B-1** Attestation envelope unspecified | §4.5.1 | **CLOSED with one fix** | Envelope shape, Ed25519, JCS, ts_obs/ts_known, schema_version are all there. **Defect:** `dedup_key = hash_jcs(payload, source_lei, ts_obs)` omits `payload_schema_version`. See N-1 below. |
| **B-2** Multi-source aggregation absent | §4.5.2 | **CLOSED** | CSD primary; 2-of-2 (custodian + counterparty) quorum when CSD silent; never single non-primary. Quorum-tightening is config, never relaxable below 2-of-2. The contradicting-attestations row (sese.025 vs sese.024 for same tx_id → quarantine) is correct. |
| **B-3** Absence-of-finality not attested | §4.5.3, §14 | **PARTIALLY CLOSED** | The obligation-FSM half is closed: silence_attestation envelope, watchdog never auto-FAILs, four-eyes manual override is the only Pending → Failed path. **The CSD-outage half is silently re-deferred to §14**: "CSD operational outages. Watchdog (G8) handles via Temporal saga + externalisation; the runbook is jane_street's, not in this spec." This is exactly the §14 punt I called out in R1 M-8. See N-2 below. |
| **B-4** Cum/ex as attested observation | §4.5.4 | **CLOSED** | 2-of-3 quorum from issuer_agent / primary CSD / market data vendor. Mismatch routes to `wf-ca-break`. |
| **B-5** Trust-assumption registry | §13.5 | **CLOSED** | All 10 entries (TA-DS-1..10) listed with assumption, detection signal, owner. Quarterly review cadence pinned. |
| **M-1** Restatement of already-Discharged obligations | §6.5.5 row 4, §11.A | **PARTIALLY CLOSED** | Reading (a) is committed: "treat restatement as new obligation; new `attempt_seq`." However, §11.A also says "restatements update `t_known` but original `t_obs` preserved" — these are *two different models* (new obligation vs. bitemporal correction of the same obligation). The already-discharged case is not explicitly walked through. See N-3 below. |
| **M-2** Sign convention on DS3 | §0.2, §4.1, §3, §3.X | **CLOSED** | Canonical signed convention; verified on BUY and SELL with independent computation. Closes feynman B-2 too. |
| **M-3** ISO 20022 mapping as oracle output | §4.5.1 (schema pin), §8.5 | **PARTIALLY CLOSED** | Inbound *schema* version is pinned. The **mapping function** (raw ISO 20022 bytes → internal representation) is not specified as: (a) deterministic, (b) total over a documented input domain, (c) version-pinned per mapper *implementation*, (d) emitting `UnmappableMessage` quarantine on failure rather than silent default. Pinning the schema version of the source is necessary but not sufficient — a buggy mapper at version N silently misreads schema-08 into the internal model with no quarantine event. See N-4 below. |
| **M-4** Key management | §4.5.1 (TrustRoots versioned) | **NOT CLOSED** | Single mention: "verified at L_11 ingest by the public key registered for `source_lei` in `L_7^P.TrustRoots` (versioned)." That is one line. Key generation, rotation cadence, revocation procedure, recovery on compromise, **and the verification predicate's behaviour at the boundary of a key rotation** (e.g., a 12-month-old envelope re-verified after a rotation) are unspecified. TA-DS-1 names "CSD signing key uncompromised" as an assumption but the *mechanism* by which a compromise is responded to (replay all envelopes signed under compromised key with annotation; re-verification under historical key registry) is absent. See N-5 below. |
| **M-5** Threat model | (none) | **NOT CLOSED** | Phase 1 §9 had ten attacker-class rows; v2 has none. The closest thing is the §13.5 trust-assumption registry, which is necessary but not the same artefact. A trust assumption answers "what do we believe?"; a threat model answers "who is trying to break us, with what capability?" The two are dual; both are required for an external audit. See N-6 below. |
| **M-6** §4.1 algebraic identity assumes nostro_external given | §4.1, §4.4, TA-DS-7 | **PARTIALLY CLOSED** | The §3 worked example now correctly grounds `nostro_external = 1,000,000` against `w_JPMC_nostro_USD.own(USD)` (a JPMC `camt.053` attestation). TA-DS-7 names the assumption ("Nostro statements (camt.053) auth-verified"). **What is missing:** the freshness contract per `(real_wallet, ccy, custodian)` — max staleness, update trigger, fallback chain (camt.053 primary; intraday camt.054 aggregation secondary; manual operator attestation tertiary), disagreement handling between primary and secondary. The recon engine consumes `nostro_external` from somewhere; whether that "somewhere" is the bitemporal pinned snapshot or a live cache is unspecified. See N-7 below. |
| **M-7** GS-broker discharge from CSD attestation (TA-DS-11) | (not added) | **NOT CLOSED** | I asked for TA-DS-11 covering "the CSD's discharge attestation is taken to imply the contra-leg has discharged on the counterparty's side; for non-CSD-PvP arrangements (FoP, non-DvP cross-border), this assumption requires a counterparty-side confirmation as a 2-of-2 quorum." TA-DS-1..10 do not capture this assumption. The contra-leg-from-CSD inference is in the §3 worked example without a registered trust assumption. See N-8 below. |
| **M-8** CSD operational outages | §14, §4.5.3 | **NOT CLOSED** | §15.4 row J says "Closed" for the regulatory matrix, but CSD outages are NOT in the closure table — they are in §14 out-of-scope: "the runbook is jane_street's, not in this spec." This is exactly the deferral I forbade in R1. See N-2 (combined with B-3 residual). |

---

## Section 2 — New Issues (introduced or surfaced in v2)

### N-1 (BLOCKING, simple fix). The dedup_key formula in §4.5.1 omits the schema version

**Where.** §4.5.1: `dedup_key = hash_jcs(payload, source_lei, ts_obs)`.

**Problem.** A single source LEI can sign two messages with identical `payload` bytes under *different* schema versions. Example: `sese.025.001.08` and `sese.025.001.10` have overlapping but not identical field offsets; an adversary (or a vendor with a misconfigured SWIFT version setting) could produce two messages that JCS-canonicalise to the same byte sequence under a permissive parser but encode different settled quantities under different schema interpretations. The dedup table accepts the second as a duplicate (drop), but the system has actually received two different observations.

**The full required formula** (lifted from R1 B-1 with the schema field):
`dedup_key = hash_jcs(payload || schema_uri || schema_version || source_lei || ts_obs)`

Schema fields belong inside the dedup key because the verification predicate already consults `payload_schema = (schema_uri, schema_version)` — they are part of the observation, not metadata about it. A two-line fix.

**Severity.** Blocking. Cheap to close.

---

### N-2 (BLOCKING). CSD operational outages remain out-of-scope; this leaves the "absence of finality" protocol incomplete

**Where.** §14 line 2: "CSD operational outages. Watchdog (G8) handles via Temporal saga + externalisation; the runbook is jane_street's, not in this spec." Combined with §4.5.3 silence_attestation: the watchdog emits `silence_attestation` and opens `wf-confirm-break`; on `Λ_4` (T+1bd) and no resolution, "ops escalate per the regulatory clock."

**Problem.** Three layered defects:

1. **The transition `Pending → AwaitingFinality_outage` is not in the closed sum (§5.2).** R1 B-3 specified this transition as the *correct* response to a CSD outage attested out-of-band. Without it, the obligation has only two paths past `Λ_4`: (a) wait for witness (which never comes during outage), (b) four-eyes manual override to `Failed → Compensated` (§5.4). Path (b) is wrong: an obligation in CSD-outage limbo is not Failed, and operators forced to take the override path will route legitimate trades through manual compensation logic, polluting the audit trail and confusing CSDR penalty accrual.

2. **The outage attestation source is not specified.** "Externalisation" is a verb without a noun. Is the outage attested by the CSD's status page (an unsigned web feed)? By an operator-signed `L_10` envelope under TA-DS-? (no entry exists)? By a market-data vendor consensus? Without a signed source, the closed-system property is broken: an operator can declare an outage to suspend the watchdog without external verification.

3. **The re-instruction protocol on recovery is not specified.** When DTC comes back up, the framework re-issues `sese.023` for all suspended obligations? Re-confirms with the counterparty first? Triggers a fresh quorum cycle? §6.5.7 saga compensation tower covers `late_discharge` for the cancellation race, not outage recovery.

**The §14 framing — "the runbook is jane_street's, not in this spec"** — is precisely the failure mode my standing position forbids: a closed-system specification with a "the runbook handles it" exit clause is not a closed-system specification. The runbook is operational; the outage transition is structural.

**Required closure.** Three pages of spec:
- New FSM state `AwaitingFinality_outage` in the closed sum, reachable from `{Pending, Instructed, PartiallySettled}` on attested outage.
- New attestation kind `csd_outage_declaration` in the §4.5.1 envelope shape, with quorum-of-2 (CSD-status + operator-attested OR two-of-three-of (CSD-status, operator, vendor-consensus)).
- New TA-DS-11 (or extend TA-DS-1) covering "outage attestation is admissible from operator under four-eyes when CSD signing is itself unavailable."
- Re-instruction protocol: on recovery (CSD returns to signing), each suspended obligation re-emits its `sese.023` with `attempt_seq+1`; the original obligation's `csd_finality_witness` slot is now satisfied by the post-recovery `sese.025` *under the new attempt_seq*. Bitemporal: the original `t_obs`/`t_known` of the suspension is preserved.

**Severity.** Blocking. The §14 deferral to runbook is unsafe.

---

### N-3 (MAJOR). The restatement model is described in two non-equivalent ways across §6.5.5 and §11.A

**Where.**
- §6.5.5 row 4: "`restated sese.025(tx_id, q')` ... new attempt_seq; **Reading (a): treat as new obligation**."
- §11.A bottom: "**replay determinism over the multiset of finalised witnesses; restatements update `t_known` but original `t_obs` preserved.** This subsumes v1 DS16."

**Problem.** "Treat as new obligation" and "update t_known on the same record" are two *different bitemporal models*:

- **Model A (new obligation).** The original `o` retains its state and witnesses untouched; a new `o'` is created carrying the delta (or replacing). The original's `corrections_chain` grows by one. `as_of(t)` returns the original; `with_corrections_through(t')` returns the chain-resolved view. This is the model R1 M-1 demanded ("RESTATEMENT_DELTA sibling obligation").

- **Model B (in-place bitemporal correction).** The same `o` row gets a new `(t_obs, t_known)` tuple appended; the prior tuple is preserved in the bitemporal index. `as_of(t)` traverses the tuple chain; the obligation's identity is one record across all its bitemporal lives.

These are *information-equivalent* (you can transform between them) but they are *different schemas* and they impose *different reasoning patterns* on consumers (recon engine, ECL stage estimator, regulatory reporter). The proposal needs to commit to one.

**Concretely:** for an `o.state = Discharged` obligation whose CSD-issued `sese.025` is restated by a new `sese.025` with a different settled quantity:
- Under Model A: `o.state` stays Discharged; new `o'` of kind `RESTATEMENT_DELTA` carries the (q' − q) move; `corrections_chain` on `o` grows by one.
- Under Model B: `o.state` stays Discharged; the existing row gets a new `(t_obs', t_known')` with the corrected quantity and (logically) the prior view is "as-known-at(t_known)."

§15.4 row F says "Closed under Model B" ("restatements update `t_known` but original `t_obs` preserved"). §6.5.5 says Model A. Pick one.

**My recommendation.** Model A. Bitemporal correction at the `L_15` row level inside an already-Discharged obligation conflates "what we observed" with "what was true." Better: the original is what we observed *and* it stayed true as observed; the restatement is a new observation with its own deltas. This matches Phase 1 §7.4 and the IAS 8.42 prior-period restatement discipline §10.9.5 already commits to.

**Severity.** Major. Unresolved ambiguity; not unsafe but defective for replay.

---

### N-4 (MAJOR). The mapping function (ISO 20022 → internal representation) lacks a determinism contract

**Where.** §4.5.1 schema_pin closes part of M-3. §8.5 identifies messages as witnesses. Nowhere is the mapping itself specified.

**Problem.** A schema-pinned message is half the boundary; the other half is the *mapper code*. Two scenarios:
1. Mapper version 1.4 reads `sese.025.001.08` `SettledQuantity` correctly. Mapper 1.5 introduces a regression on the same schema — silently misreading partial-settlement quantities. Replay of a year-old envelope under mapper 1.5 produces a different internal representation than under 1.4. **Replay determinism (DS5) is broken.**
2. An incoming `MT540` (legacy) is normalised to `sese.023` family per §8.5. The normalisation is a translation that loses information. Whether a `MT540` carrying field 22F:RPCO is mapped to `sese.023` `SettlementParameters/Indicator/PartialSettlementIndicator` or dropped entirely is a mapper-version choice. No invariant.

**Required closure.** Add to §4.5.1 (or new §4.5.6 "Mapper contract"):
- `mapper_version` is recorded with each envelope at intake (alongside `payload_schema`).
- Replay uses the *historical* mapper version (`mapper_version_active_at(t_known)`).
- Mapper functions are **total over the documented input domain**; messages that fall outside (unrecognised tags, schema-version not in the active set) emit `UnmappableMessage` events to `L_18` of kind `mapper_unmappable`. Silent defaults are forbidden.
- Mapper version is append-only in `L_7^P.MapperRegistry`; rollouts are version-bumped, not in-place patched.

This is a half-page of spec; M-3 is closable in v3.

**Severity.** Major. DS5 is at risk under mapper-version drift.

---

### N-5 (MAJOR). Key management contract is one line; key rotation, revocation, recovery, historical-verification semantics are absent

**Where.** §4.5.1 line 6: "Verified at L_11 ingest by the public key registered for `source_lei` in `L_7^P.TrustRoots` (versioned)." TA-DS-1: "CSD signing key uncompromised."

**Problem.** "Versioned" is doing all the work in that one line. A signing key has a lifecycle (generate → registered → active → rotated → expired → revoked); each event has a witness; each historical envelope must be verifiable against the key active at *its* `t_obs`, not the key currently active. None of this is specified. Concretely:

1. **What `L_7^P.TrustRoots` actually contains.** I infer (key_id, source_lei, public_key_bytes, valid_from, valid_to|null, revoked_at|null, replaced_by|null, evidence_attestation). Specify it.
2. **Key registration.** When a new CSD signing key is registered, what attests its identity? An out-of-band ceremony? An LEI-issuer attestation? An incumbent-key signature? Each option has a different threat model.
3. **Key rotation.** Pre-announced or live? Overlap window where two keys are simultaneously valid?
4. **Key revocation on compromise.** What happens to envelopes signed under the compromised key between *suspected compromise time* and *revocation time*? A blanket "replay everything" is operationally infeasible at scale; a finer-grained "envelopes signed in the suspect window are quarantined to L_18 with kind `replay_under_compromised_key` for forensic" is what I'd specify.
5. **Re-verification on rotation.** A 12-month-old envelope's signature is verified against the historical public key (`active_at(t_obs)`), not the current one. The append-only `TrustRoots` makes this reproducible — but it must be stated as an invariant ("envelope verification is bitemporally pinned to the key active at `ts_obs`").
6. **Operator-LEI keys for manual `L_10` synthesis** (manual override / CORRECTION). The same discipline applies: append-only registration, four-eyes on key registration itself, revocation procedure for departed operators.

**Required closure.** New subsection §4.5.6 "Key management contract" or extend TA-DS-1 into a multi-row block (TA-DS-1a key uncompromised, TA-DS-1b key registry append-only, TA-DS-1c verification bitemporally pinned to `t_obs`, TA-DS-1d revocation triggers replay-of-affected-window). Defer cryptographic primitive selection to a cryptographer (already noted in Phase 1 §11).

**Severity.** Major. The whole "verify(envelope)" semantics rests on this. Closable in 1-2 pages.

---

### N-6 (MAJOR). Threat model is not enumerated as a first-class artefact

**Where.** Implicit throughout. §13.5 trust-assumption registry is the closest analogue.

**Problem.** A spec that claims zero-trust at the boundary owes the reader an enumeration of attacker classes and the mitigation matrix, not just the trust assumptions. Phase 1 §9 had ten rows. v2 has zero. Concretely the reader cannot answer:

- **Malicious vendor.** What if Bloomberg signs an ex-date that disagrees with DTC and S&P? (TA-DS-9 names the assumption; the threat model would specify the attacker capability and the mitigation: 2-of-3 quorum routes mismatch to wf-ca-break.)
- **Malicious gateway.** What if our own L_11 ingestion gateway is compromised — could it forge envelopes? (Mitigation: gateway does not hold any signing keys; it forwards signed envelopes from upstream sources only.)
- **Malicious operator.** What if a settlement operator manually overrides a Pending → Compensated transition to hide a real fail? (Mitigation: §5.4 four-eyes, §10.9.6 SOX implications "10 CORRECTIONs/month from same trader = red flag.") This is partially covered.
- **Equivocating CSD.** TA-DS-2 names the assumption; the mitigation (`dedup_key`-collision over different payloads) is named. **But what does the framework do on detection?** Quarantine all CSD-signed envelopes for the `tx_id`? Page someone? Open a wf-confirm-break? Silent on this.
- **Replay attacker.** Mitigation is dedup_key (with the N-1 schema fix). Stated.
- **Clock-skew adversary.** TA-DS-5 names ±5s bound. Threat: an adversary who can manipulate `ts_obs` on a signed envelope to make a stale message appear fresh, or a fresh message appear stale. Mitigation depends on whether signers also include their NTP source attestation; not specified.
- **Key-rotation adversary.** Stale signing key kept alive past official rotation. Tied to N-5.
- **Mapping-layer manipulator.** Tied to N-4.

**Required closure.** Lift Phase 1 §9 ten-row table into the proposal as §4.5.7 "Threat model": each row (attacker class, capability, mitigation, residual risk). Cross-reference TAs and invariants. This is two pages of spec; the table is the whole artefact.

**Severity.** Major. An auditor reading v2 cannot ask "show me your threat model" and be answered. This is an audit gap, not a security defect *per se* — but it is the audit gap that lets future security defects accumulate undetected.

---

### N-7 (MAJOR). The nostro_external freshness contract is unspecified

**Where.** §4.4 morning recon report: "nostro_external_balance: 1,234,567.89 (camt.053 from L_11)." TA-DS-7: "Nostro statements (camt.053) auth-verified."

**Problem.** The morning recon (§4.7 cadence: "09:00 local") consumes `nostro_external(w, ccy, t)`. The freshness contract — how stale can the camt.053 be before recon refuses to run, what fallback applies if camt.053 has not arrived for 2 days, what happens when intraday camt.054 aggregation diverges from the most recent camt.053 — is not stated. Concretely:

- If JPMC's daily camt.053 for prior-day-EOD has not arrived by 09:00 local, does the recon (a) skip the affected currency, (b) fall back to last-known camt.053 + intraday camt.054 deltas, (c) quarantine and page? §4.4 row "OVERDUE ... 3bd AGED" suggests the framework gracefully ages; whether the framework gracefully ages a *missing nostro statement* (vs. an open trade past ISD) is not addressed.

- If the most recent camt.053 says 1,000,000 and intraday camt.054 aggregation since says +50,000, the live nostro estimate is 1,050,000. The recon engine compares against 1,000,000 (last camt.053) or 1,050,000 (estimate)? Either choice is correct *under a stated freshness contract*; both are wrong silently.

- The recon is replayable: a 12-month-old recon-state must reproduce bit-identically. This means `nostro_external(w, ccy, t)` is consumed from a **bitemporally pinned snapshot**, not a live cache. This invariant is not stated.

**Required closure.** New §4.7.1 or extend §4.5 with "Freshness contract per witness class":

| Witness class | Primary | Max staleness | Fallback 1 | Fallback 2 | Hard stop |
|---|---|---|---|---|---|
| `nostro_external(USD, JPMC)` | camt.053 daily EOD | 24h post-EOD | camt.053 + intraday camt.054 estimate (named class) | operator manual attestation, four-eyes, TA-DS-7-extended | recon refuses, BREAK kind=`nostro_unavailable` |
| `csd_finality(US, DTC)` | sese.025 | by ISD+1bd | (none — silence triggers wf-confirm-break per §4.5.3) | — | per N-2 above (CSD-outage path) |
| `corp_action_ex_date(ISIN)` | issuer agent attestation | by record_date | DTC CA attestation | market data vendor consensus | wf-ca-break |

Plus the bitemporal pinning invariant: "all witness consumption by the recon engine is from the bitemporally pinned snapshot at recon time."

**Severity.** Major. M-7 was named in R1; v2 named the assumption (TA-DS-7) but did not specify the contract. Half-step.

---

### N-8 (MINOR). TA-DS-11 (CSD-implies-counterparty discharge for non-CSD-PvP) is missing

**Where.** §3 worked example writes a move on `w_GS_broker` based on a DTC `sese.025`. R1 M-7 asked for TA-DS-11.

**Problem.** Standalone, this is a small gap — the assumption is sound for DTC PvP and most cross-border CSD-mediated DvP. It becomes load-bearing for FoP delivery (different cash agent), non-DvP arrangements, and some emerging-markets CSDs. The proposal targets v11.0 cash equities (mostly DTC/T2S DvP), where the assumption is operationally airtight.

**Required closure.** Add as TA-DS-11 to §13.5: "the CSD's discharge attestation is taken to imply the contra-leg has discharged on the counterparty's side; for non-CSD-PvP (FoP, non-DvP cross-border), the assumption requires a counterparty-side confirmation as a 2-of-2 quorum override of TA-DS-11." Owner: settlement operations.

**Severity.** Minor in current scope; will become major when v11.0 expands to FoP / EM / non-DvP. Cheap to close.

---

### N-9 (MINOR). The `silence_attestation` envelope is signed by `our_lei` but not subject to four-eyes

**Where.** §4.5.3 silence_attestation envelope: `source_lei = our_lei (we are attesting our own observation of silence)`.

**Problem.** Self-signed silence is permitted to open `wf-confirm-break`, which then routes to ops. So far so good. But the structure invites a subtle attack: a malicious operator with access to the `our_lei` signing key (or a misconfigured automation) could emit a silence_attestation when a sese.025 is *actually present in the inbound queue but not yet processed*. The watchdog opens a break, and the trade is now in a manual-investigation pipeline rather than a clean discharge pipeline.

**Mitigation.** The silence_attestation should be emitted by the **watchdog activity** under a dedicated key (`watchdog_lei`), not the general `our_lei`. The watchdog activity is the only writer of silence_attestation; capability-typed writer; emitted only on `now() > intended_settlement_date + Λ_n AND L_15.csd_finality_witness IS NULL` evaluated at activity time. This makes silence_attestation forgery impossible by design.

**Severity.** Minor. Architectural.

---

### N-10 (MINOR). The §3.5 `tx_id` derivation does not include `payload_content_hash`

**Where.** §6.5.1 `tx_id = hash_jcs(business_event_id, attempt_seq)`.

**Problem.** Closes temporal B-1, good. But cross-referencing with R1 m-1: if a `sese.025` is restated under Reading (a) (new obligation, new attempt_seq), `tx_id` changes correctly. If it is restated under Reading (b) bitemporal correction (different model from §11.A), the `tx_id` *does not change* but the underlying message did. Combined with N-3 ambiguity, a restatement could produce two move-emissions tagged with the same `tx_id` but referring to different witness payloads.

**Mitigation.** Either commit to Reading (a) firmly (per N-3) and the issue evaporates, or include `attestation_envelope_dedup_key` in the `tx_id` derivation. The first is cleaner.

**Severity.** Minor. Subsumed by N-3 if N-3 is closed in favour of Reading (a).

---

## Section 3 — Pareto Judgment

**§15.7 claims:** "Zero blocking remaining; zero unmitigated major remaining; no minor improvement without offsetting trade-off."

**My audit of that claim:**

| Category | §15.7 claim | My assessment | Net |
|---|---|---|---|
| R1 BLOCKING | 0 remaining | 1 BLOCKING residual (B-3 / N-2 CSD outages) + 1 BLOCKING-easy-fix (N-1 dedup_key schema) | **2 blocking remain** |
| R1 MAJOR unmitigated | 0 remaining | M-3 partial (N-4); M-4 (N-5); M-5 (N-6); M-7 (N-7) — four major findings unmitigated | **4 unmitigated majors** |
| §15.5 honest open issues | 4 (PO-4, PO-5, PO-6, PO-8) | None of M-4 / M-5 / M-7 / N-2 appear in §15.5 | Pareto test fails |
| Minor | (claim implicit) | N-8, N-9, N-10 surfaced; all cheap to close | Tractable |

**Pareto NOT REACHED.** 

For Round 3, the Settlement Team must:
- **Close N-1** (dedup_key formula fix; one-line change).
- **Close N-2** (CSD-outage protocol moved from §14 into §4.5 / §5.2 with new FSM state, attestation source, re-instruction protocol; ~3 pages).
- **Close N-3** (commit to Reading (a) bitemporal restatement model and align §11.A wording; ~half page).
- **Close N-5** (key-management contract subsection; ~1-2 pages).
- **Close N-6** (threat model table; ~2 pages).
- **Close N-7** (freshness contract per witness class; ~1 page table).
- **Mitigate N-4** (mapper-version pinning; ~half page).
- **Add N-8** (TA-DS-11; one row).
- **Refine N-9** (watchdog_lei separation; one paragraph).

Total v3 work: ~8-10 pages of additive specification on top of v2's ~21k words. None of this is invention; all of it is in Phase 1 nazarov.md or in my R1. 

The convergence is real. The boundary is *almost* held. The gaps are documentation/specification gaps over a sound architecture, not architectural defects. The team has earned the right to close in v3 rather than be sent back to v2.5.

**Recommendation: proposal_v2 is ACCEPT_WITH_CHANGES; arbiter should not declare Pareto on the boundary axis until N-1, N-2, N-5, N-6, N-7 are closed in v3.**

---

## Section 4 — What v2 Got Right (preserve)

1. **§4.5.1 envelope shape.** With the N-1 dedup_key fix, this is the right structure. Ed25519, JCS, ts_obs/ts_known split (clock-skew handling at TA-DS-5), schema_version pin, idempotency key. Clean.

2. **§4.5.2 multi-source aggregation.** The "never single non-primary" rule, the configurable quorum-tightening to 3-of-3 (but never relaxable below 2-of-2 by configuration — hard rule encoded in workflow code), the explicit contradicting-attestations row (sese.025 vs sese.024 → `wf-confirm-break`). This is the discipline I asked for.

3. **§4.5.3 silence_attestation.** The shape is right (named attestation kind, watchdog poll cadence Λ_0..Λ_4, never auto-FAIL). With N-9 fix (dedicated watchdog_lei), this becomes architectural-grade.

4. **§4.5.4 cum/ex 2-of-3 quorum.** Issuer agent + primary CSD + market data vendor; mismatch routes to `wf-ca-break`. Closes B-4 cleanly.

5. **§13.5 trust-assumption registry.** Ten named assumptions, named owners, stated detection signals, quarterly review cadence pinned in `L_7^P.TrustAssumptionReview`. With TA-DS-11 added (N-8), this is the registry I asked for in B-5.

6. **§3.X SELL worked example.** Independent verification of the recon identity. The sign discipline survives a hostile read.

7. **§6.5.5 commutativity table.** The non-commuting cases (terminal absorbs; contradictions quarantine; correction-vs-discharge) are explicitly *not* "out-of-order replay produces different state" but deterministic precedences. This is the right framing.

8. **§10.9 CORRECTION transaction policy** with the explicit NOT-permitted list (hiding fail by reversing original; pre-dating; deleting a CORRECTION; silent CORRECTION). This is exactly the discipline I would have written.

9. **§13.4 Goodhart traps named.** G-DS-1 quick-finality bias mitigated by empirical-distribution pinning; G-DS-2 per-class conservation; G-DS-3 record-and-replay forbidden. The "code-review hard-fail on `learn_from_traces(...)` patterns" is a strong control.

10. **§11 invariant pruning.** 18 → 10 with the `§11.A restated v10.3` appendix. Clean separation of "genuinely new" from "restated for completeness."

---

Hold the boundary. Two more pages of envelope discipline (N-1, N-2, N-5, N-6, N-7) and the boundary is held to my satisfaction.

— NAZAROV, 2026-04-30
