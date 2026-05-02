# Round 1 Adversarial Review — proposal_v1.md
## Reviewer: NAZAROV — Data Layer Architect
## Date: 2026-04-30

**Verdict:** ACCEPT_WITH_CHANGES

The proposal is the strongest cross-functional convergence the Ledger has produced. Its internal algebra (PS/PSS, six-coordinate orthogonality, FSM closed sums, type design) is sound. Its CDM cross-walk and regulatory matrix are rigorous. **However, the entire spec rests on an unspecified boundary.** The trust-boundary discipline I laid out in Phase 1 is referenced (DS4 cites "nazarov INV-DS-2"; DS5 cites "INV-DS-4"; DS16 cites "INV-DS-5") but the **operational protocol that makes those invariants enforceable — envelope schema, key management, dedup keys, multi-source aggregation, freshness contracts, absence-attestation, equivocation handling, restatement semantics — is largely absent or compressed into hand-waving phrases.**

This is not "missing detail to be filled in later." A boundary specification with named mitigations but unspecified mechanism is functionally equivalent to no boundary specification: the same code can pass the listed invariants while silently admitting unsigned data, single-source escapes, or inferred-fail transitions.

I am ACCEPT_WITH_CHANGES because the structural convergence is correct and the gaps are *additive*, not corrective. Most blocking findings can be closed by lifting Phase 1 §§4, 8, 9 (trust-assumption registry, threat model, freshness contracts) into the proposal proper as specifications, not citations. None require redesign.

---

## Blocking findings (must be closed before Phase 3 sign-off)

### B-1. The attestation envelope is mentioned, never specified

**Where.** §3.2 metadata `sese.025_msg_id`, `camt.054_msg_id`. §5.4 "witness message ... observed on `L_11.ExternalConfirmation`". §8.1 "each appears in `L_11.ExternalConfirmation` with bitemporal `(t_obs, t_known)`. Each document is signature-verified and content-hashed at ingress." §10.3 "each document is signature-verified and content-hashed at ingress."

**Problem.** The phrase "signature-verified" appears five times in the proposal. The signature scheme, the signing key identity, the timestamp authority, the canonicalisation rule, the dedup key composition, and the verification algorithm are nowhere specified. **The framework cannot assert DS4 (no discharge without witness) without an envelope contract**: if "witness" is "any record that arrived through the gateway", DS4 collapses to "discharge requires that something happened in the gateway", which is not a security property.

**The envelope contract MUST specify, at minimum:**

1. **Canonical envelope shape** for `L_11.ExternalConfirmation`:
   `{ payload_jcs_canonical_bytes, signature, signer_key_id, signer_lei, t_obs, t_known, attestor_class ∈ {CSD, CUSTODIAN, COUNTERPARTY, CCP, CLS, INTERNAL_OPERATOR}, dedup_key, source_message_id, source_format ∈ {sese.025, sese.024, sese.027, sese.030, sese.031, camt.054, camt.053, MT54x, FpML, custom}, schema_version_pin }`.

2. **Dedup key composition.** I see `EndToEndId` referenced in §5.5 and `(dedup_key)` referenced in §3.2 metadata, but the actual key formula is undefined. Required: `dedup_key = hash_jcs(signer_key_id || source_message_id || content_hash_of_payload)`. Two messages with the same `EndToEndId` but different content (i.e., a restatement) have *different* dedup keys and produce different envelopes. Collisions are forbidden by construction.

3. **Verification predicate.** `verify(envelope) = signature_valid_against_pubkey_active_at_t_obs(signer_key_id, payload_jcs_canonical_bytes, signature) ∧ schema_version_pin ∈ active_schema_set(t_known) ∧ envelope_not_in_dedup_table(dedup_key)`. The proposal states `verify_envelope(o.discharge_witness) = true` in DS4 without defining what that function does.

4. **Schema-version pin.** §1.10 type design pins date conventions; nothing pins the inbound ISO 20022 schema version. A `sese.025.001.08` and a `sese.025.001.10` parse different bits at different offsets. If the mapper assumes 08 and the message is 10, the framework silently misreads `SettledQuantity`. **Schema version is part of the envelope; mapping is parameterised by schema version; replays must use the same version-pinned mapper.**

**Why this is blocking.** Without an envelope contract, every DS4 reference is decorative. An auditor cannot confirm "every Discharged obligation has a verified witness" because "verified" is undefined. The framework cannot replay a 12-month-old settlement and confirm bit-identical state because the verification is not pinned to historical state. This is the difference between a security claim and a security property.

**Closure.** Add §X (between current §5 and §8) "Attestation Envelope Specification" with the four sub-sections above. The Phase 1 §0–§2 of `nazarov.md` is the source draft; lift, sharpen, integrate.

---

### B-2. Multi-source aggregation protocol is absent

**Where.** Phase 1 §4.2 specified four attestor classes (CSD primary, custodian secondary, counterparty back-office tertiary, CCP quaternary) with an explicit aggregation rule: `Discharged ← CSD attestation alone OR (custodian + counterparty 2-of-2)`. None of this appears in the proposal.

**Problem.** §5.4 says "An obligation transitions Pending → Discharged ONLY when [...] A witness message is observed [...] matches the discharge predicate [...] reconciles within tolerance." This is single-source-discharges-the-obligation logic. **A single CSD message is admitted as authoritative.** If the CSD is compromised, equivocates, or sends a wrong-content `sese.025` whose payload still matches the `EndToEndId` (e.g., wrong `SettledQuantity` within tolerance — see §4.5 row 4 hard quarantine, but only a "wrong amount or quantity" check, not a quorum check), the obligation is silently Discharged on a single attestor's say-so.

The proposal calls this out *operationally* in §4.5 row 4 ("HARD: do not apply the finality moves; quarantine") for amount/quantity mismatch *against the recognition tx*. Good. But it does **not** call out the case where the CSD message agrees with the recognition tx and the custodian's MT535 disagrees with the CSD message. That is silent single-source-trust.

**Required closure.**

1. **Aggregation rule per attestor-class set.** Default: `CSD attestation suffices` (CSD is the legal point of finality per CSDR Art 39). But the rule is *named*, not implicit; alternative rules (`2-of-2 secondary+tertiary`, `CCP override`, `bilateral non-CSD trade requires custodian + counterparty`) are configured per `(venue, instrument_class, settlement_type)` in `L_7^P.PolicyConfiguration` with bitemporal versioning.

2. **Disagreement detection.** When CSD `sese.025` says Settled and custodian MT535 says Pending or Failed, the *obligation does not advance*. A `L_18.BreakRegister` row of kind `wf-settlement-disagreement` is opened; FSM holds at `Pending`; resolution requires a *new* attestation (operator-signed `L_10` with named trust assumption + four-eyes, or counterparty-issued correction). This is the contract Phase 1 §4.2 specified; it is not in the proposal.

3. **Disagreement timer.** Disagreements that remain unresolved past `T_disagree_max` (TBD; suggested 1 BD post-ISD) escalate to risk committee per §10.7 materiality. Not mentioned.

**Why this is blocking.** §4.5 ("not a break") row 7 says `sese.025` finality arriving up to 1 BD late for cross-border is *expected*, not a break. Combined with single-source CSD discharge, this means: CSD sends one message, framework writes Discharged, custodian disagrees the next morning, framework already moved virtual-wallet balances to broker, and the only signal is a recon break two days later. **By that point, downstream consumers (regulatory reports, P&L, capital) have consumed a wrong-discharged trade.**

**Closure.** Lift Phase 1 §4.2 verbatim into the proposal as §5.X "Aggregation protocol per attestor class."

---

### B-3. Absence of finality is not specified as an attested observation

**Where.** §5.4 "after T_max = expected + 5bd ... the obligation auto-promotes to a break in L_18.BreakRegister of kind obligation_overdue — but the obligation itself remains Pending until a witness arrives or the fallback handler executes a CORRECTION (Compensated) or default (Defaulted)." §11 DS4 statement.

**Problem.** This is good *for the obligation FSM*: it correctly does not auto-Fail on absence. But the proposal then says (§5.6 row 5) `FAILED` happens "≥ 1 leg past deadline, witness shows fail" and says (§7.5) at T+3 "Workflow detects: u_sale.lifecycle_stage == FAILED, regime=US_REG_SHO" — **how does the workflow detect FAILED?** A `sese.024` arrives. Or it doesn't.

**The case where no message arrives at all is unresolved.** Phase 1 INV-DS-3 requires positive attestation of fail (CSD-issued fail status, or a custodian's positive non-receipt confirmation). The proposal nowhere requires this. The text "T_max exhaust + fallback handler" in §5.3 transition table is a transition, not a witness; a workflow timer is not a signed external observation; the closed system cannot infer the external state by clock alone without violating zero-trust.

**Required closure.**

1. **Explicit rule:** Pending → Failed requires either a `sese.024` (CSD-issued fail attestation) **or** a *positive non-receipt attestation* from a designated witness (e.g., custodian's daily participant statement explicitly listing the obligation as unsettled past ISD), signed by the witness LEI. No transition by clock alone.

2. **The "CSD goes silent at T+2 cutoff" case.** Phase 1 §11 flagged this explicitly as Phase 2 work; the proposal acknowledges it in §14 ("CSD operational outages") only as deferred. **It must be in scope** because the framework's zero-trust posture is meaningless if it auto-promotes to FAILED on a missing message. The current §14 wording ("do not auto-promote to FAILED; wait for CSD recovery; re-instruct on recovery") is the right answer but must be lifted into a normative invariant.

3. **Fallback chain, primary-secondary-tertiary, with freshness contracts.** Phase 1 §4.3 specified maximum staleness per source. None of this is in the proposal. Without it, "the witness arrived late but is admissible" vs. "the witness is too stale to credit" is undefined.

**Closure.** Add invariant DS4a (or extend DS4): "FAILED requires positive fail attestation; absence-of-message produces AwaitingFinality with operator-attested escalation, never Failed by inference." Add §X.Y freshness-contract table per attestor (Phase 1 §4.3).

---

### B-4. Cum/ex determination is treated as known fact, not as an attested observation

**Where.** §6.4 corporate actions in passing. §10.10 ("cum/ex corporate action audit trail") names the manufactured-payment obligation. §13 G11 ("manufactured payment / claim recipient determination") calls it a Phase-2 closable item.

**Problem.** Cum/ex is mentioned. The data-source for the ex-date determination is not. **The ex-date is itself an attested observation** (Phase 1 §6.3): typically aggregated across Bloomberg + Refinitiv + CSD/Index admin. If those three sources disagree (rare but real, especially around DR cum/ex windows and cross-listed securities), the proposal does not specify how the framework computes the cum/ex flag.

This is the single most common silent-bug class in cash equities, and it is the cum/ex tax-fraud surface (§10.10 cites the German scandal). Treating the ex-date as an oracle output without naming the oracle is a control failure.

**Required closure.**

1. **Cum/ex flag is computed from a multi-source attestation aggregation** with the same protocol as B-2: primary (issuer/index admin), secondary (CSD CA notification), tertiary (vendor — Bloomberg/Refinitiv); aggregation rule and disagreement handling specified.

2. **Trust-assumption registry entry** TA-DS-5 (Phase 1 §8) lifted into the proposal: "the corporate-action provider's ex-date attestation is treated as authoritative; if it is wrong, manufactured payments are computed wrong."

3. **The manufactured-payment obligation's discharge predicate** must reference the bitemporal CA-pin, not a closed-over snapshot (this is what G3/PO-4 is *trying* to capture but is buried).

**Closure.** Lift Phase 1 §6.3 into proposal §6.X "Cum/ex and corporate-action attestation."

---

### B-5. Trust-assumption registry is mentioned, not provided

**Where.** §13 G12 references "TA-DS-1 through TA-DS-10" as if they exist. They do — in `nazarov.md` (Phase 1) §8. They are **not in the proposal.**

**Problem.** "Single-source escape is permitted only with a registered authority assumption" (G12 text, paraphrasing §4.2 of Phase 1). If the registry is not in the proposal, an implementation cannot be checked against it. The "operational, not provable" language in §15.2 item 5 ("registry exists as documentation; quarterly review cadence is operational, not provable") is precisely the failure mode my Phase 1 forbids: untyped trust.

**Required closure.** Lift Phase 1 §8 (the TA-DS-1..TA-DS-10 table) verbatim into the proposal as §X "Trust assumption registry." Each row: name, scope, owner, violation consequence, detection signal. **The table is the spec**, not a supplementary appendix.

**Why this is blocking.** A regulator or auditor reading the proposal cannot ask "what trust assumptions are you operating under?" and get an answer. The convergence claim in §15.3 ("the deferred-settlement specification is implementation-ready") is false until this is in the spec. Implementation-ready means: the named, scoped, owned, owner-assigned trust assumptions are part of the specification, against which violations can be audited.

---

## Unmitigated major findings (must be closed in this phase or moved to a named open-item with closing constraint)

### M-1. Restatement semantics for already-Discharged obligations is hand-waved

**Where.** §13 G5 ("replay determinism in the presence of restated confirmations") "Recommendation: (a) treat restatement as a *new* obligation (clean separation, append-only)."

**Problem.** Recommendation (a) is correct. But the proposal does not commit to it. The text is "two design choices: (a) ..., (b) ..., **Recommendation: (a)**." A recommendation is not a specification.

DS16 ("bitemporal restatement, never mutation") in §11 says the right thing structurally: "the original L_11 row is preserved; a new row is appended ... corrections_chain grows by one." But §11 is about the L_11 envelope, not about the L_15 obligation that has *already absorbed* the original envelope. If `o.state = Discharged` and the originating `sese.025` is restated by a new `sese.025` with corrected `SettledQuantity`, what is the new state of `o`?

Phase 1 §7.4 ("worked example — corrections chain") gave the canonical answer: `o.corrections_chain += new_event.id`; `as_of(t_known)` returns the historical view; `with_corrections_through(t_known')` returns the corrected view; the diff opens an `L_18` break for amount mismatch. The proposal needs to lift this.

**Closure.** Pin G5 to Recommendation (a) as a normative DS-invariant: restatement of an already-discharged confirmation does **not** mutate the obligation; instead it creates a new sibling obligation (kind `RESTATEMENT_DELTA`) that carries the difference. Both query modes (`as_of` and `with_corrections_through`) are first-class. The originating obligation's `corrections_chain` grows by one.

---

### M-2. Sign convention on DS3 is acknowledged-open but not closed

**Where.** §15.1 weakness 1, §15.2 item 3, PO-3.

**Problem.** §4.1 carries the corrected identity (good). §4.2 ("Phase 1 §4.1 sign was wrong; this supersedes it") explicitly sign-corrects the cash recon. The SBL composition recon identity (§7.9) is given but not pinned by property test (PO-3). I am sympathetic — sign conventions are easy to flip and the corrected identity is published — but the proposal cannot ship to implementation with an open sign assertion in a load-bearing recon identity. **The recon identity is the algebraic anchor for DS3 (HIGH severity invariant).** If the sign is wrong, the recon engine flags clean trades as breaks and clean breaks as clean.

**Closure.** PO-3 must be discharged within Phase 3 with a property test over generated trade streams (cash recon + SBL recon). Until property test is green, mark §7.9 identity as `PROVISIONAL` in the spec, not `pinned`.

---

### M-3. ISO 20022 mapping is treated as transparent — it is not

**Where.** §8.5 "Critical observation: each ISO 20022 message is a witness to a state transition, not the transition itself." §8.6 "Settlement status on Trade.contractDetails [is wrong]" with corrections. §13 G1 (closedness of CSD failure-type enumeration).

**Problem.** ISO 20022 mapping (`sese.023/024/025/027`, `camt.053/054`, `MT54x`, FpML) is the boundary mapping layer. Per my standing position (Convictions #4): **the mapping layer is part of the oracle from a security perspective.** A bug in the mapper is an oracle bug. The proposal acknowledges G1 (CSD failure-reason normalisation) but does not specify:

1. **Mapper determinism contract.** The mapper from ISO 20022 to internal representation is total over a documented input domain, deterministic, version-pinned per inbound schema. Failures are explicit failure events (`UnmappableMessage` quarantined to `L_18`), never silent defaults.
2. **Mapper version is recorded with each ingested message** so replays produce bit-identical state. Phase 1 §1 referenced this; the proposal does not.
3. **The MT54x → sese.0xx normalisation** (§8.5 row 6) is a real translation step that loses information (`MT540` collapses to `sese.023` family; field-level mapping has known asymmetries). This translation is an oracle output. Its specification is not in the proposal.

**Closure.** Add invariant DS19 (or extend DS5): "ISO 20022 mapping is total, version-pinned, deterministic; mapping failures produce quarantined `UnmappableMessage` events; replays are bit-identical under the pinned mapper version." Cross-reference G1/PO-5 for the closed-sum failure-reason mapping per CSD.

---

### M-4. Key management discipline is invisible

**Where.** Nowhere directly.

**Problem.** "Signature-verified" recurs without mention of: how CSD/custodian/counterparty signing keys are obtained, registered, rotated, revoked, and recovered; how the verifier knows which key was active at `t_obs`; how a 12-month-old envelope is re-verified after a key rotation; what happens when a key compromise is reported.

Phase 1 INV-DS-7 ("witness key-integrity") and §11 (open items) flagged this; the proposal carries no mechanism. ADR-11 in `ledger_data_v1.0` (referenced in Phase 1) makes verification keys append-only. The proposal should reference and inherit this discipline.

**Closure.** Add §X "Key management contract": (a) signer keys are append-only (`L_3 PartyLEI` keyed sub-row) with `(key_id, signer_lei, valid_from, valid_to|null, revoked_at|null)`; (b) verification predicate fetches the key valid at `t_obs`; (c) key-compromise event triggers replay of all envelopes signed by compromised key with key-rotation pinning; (d) operator-LEI keys (for manual `L_10` synthesis) follow the same discipline. Defer cryptographic primitive selection to a cryptographer (Phase 1 §11).

---

### M-5. Threat model is referenced indirectly, not enumerated

**Where.** Implicit throughout. Phase 1 §9 had ten attacker-class rows; none in the proposal.

**Problem.** §15 ready-for-review identifies 8 known weaknesses but no threat model. A specification that names invariants without naming attackers is asking the reader to derive the attacker classes from the invariants — fine for a working group, indefensible for an external audit.

**Closure.** Lift Phase 1 §9 (ten-row threat-model table: malicious vendor, malicious gateway, malicious operator, malicious counterparty back-office, network adversary, replay attacker, equivocating CSD, clock-skew adversary, forgery via expired key, mapping-layer manipulation) into proposal §X "Threat model." Each row: capability, mitigation, residual risk.

---

### M-6. The `algebraic identity` (§4.1) silently assumes `nostro_external` is given

**Where.** §4.1 boxed identity. §3.6 conservation table (final column `nostro_external`).

**Problem.** `nostro_external(w, ccy, t)` is an *external attestation* (JPMC daily `camt.053`). The identity holds only when the attestation has arrived, been verified, deduplicated, snapshotted, and pinned bitemporally. None of this appears in §4. The recon engine (§4.8) classifies based on the identity; if the right-hand side is computed against a stale or unverified `nostro_external`, the classification is wrong and the engine produces false negatives (clean trades flagged as breaks) or false positives (breaks not flagged).

**Closure.**

1. Specify the freshness contract for `nostro_external` per `(real_wallet, ccy, custodian)`: max staleness, update trigger, fallback chain (primary `camt.053`, secondary intraday `camt.054` aggregation, tertiary manual operator attestation with named trust assumption).
2. The recon engine MUST consume `nostro_external(w, ccy, t)` from the bitemporal pinned snapshot, not from a "live" cache. Replay must produce bit-identical recon classification.
3. Disagreement between custodian `camt.053` and intraday `camt.054` aggregation opens `wf-nostro-disagreement` in `L_18`; recon engine produces `BREAK` classification with kind `nostro_disagreement`, not silent.

---

### M-7. The §3 worked example uses `w_GS_broker` as the discharge counterparty wallet — but the discharge is sourced from a CSD message, not from GS

**Where.** §3.5 finality moves: `Move 1: from = w_GS_broker, to = PSS_receivable[w_us, GS, XYZ], qty = 100`.

**Problem.** The economic semantics is right (broker virtual wallet absorbs the delivery). But the *attestation* is from DTC (the CSD). The framework writes a move on `w_GS_broker` based on a `sese.025` from DTC. There is no GS-issued attestation of the discharge — the framework infers GS's side of the trade from DTC's view of the world. **This is not wrong, but it is a trust assumption** ("DTC's view of GS's depot position is correct"; "the contra-leg of our settled trade is GS's settled trade"), and that assumption is not registered.

For most cases (DTC PvP, T2S DvP) this assumption is operationally airtight because the CSD operates the omnibus accounts on both sides. For non-CSD-PvP arrangements (FoP delivery vs separate cash payment, cross-border with separate cash agent) the assumption is shakier. Phase 1 TA-DS-3 covered this for custodian-side; the GS-broker case is an additional layer.

**Closure.** Add to trust registry: `TA-DS-11: the CSD's discharge attestation is taken to imply the contra-leg has discharged on the counterparty's side; for non-CSD-PvP arrangements (FoP, non-DvP cross-border), this assumption requires a counterparty-side confirmation as a 2-of-2 quorum.` Owner: settlement operations.

---

### M-8. Out-of-scope §14 quietly punts CSD operational outages — the most important failure mode for a zero-trust spec

**Where.** §14 bullet "CSD operational outages."

**Problem.** This is the case where the closed-system invariant is most stressed. The proposal's framing — "do not auto-promote to FAILED; wait for CSD recovery; re-instruct on recovery; ESMA grace per CSDR Art 7" — is correct, but it is **deferred to operational runbook** ("specification deferred to a future revision"). My read: the framework's zero-trust posture **fails in production** the first time DTC has an outage longer than the workflow timer's deadline. Without specification, an implementation will either (a) auto-FAIL on absence (violating DS4a as proposed in B-3) or (b) hold Pending forever (silent liveness violation; G8 territory but worse).

**Closure.** Lift CSD-outage protocol into scope. Minimum: (1) outage attestation source (CSD's own status page, or an out-of-band attestation from operator); (2) workflow timer extension protocol gated on outage attestation; (3) explicit transition `Pending → AwaitingFinality_outage` with named trust assumption (operator-attested outage is admissible); (4) re-instruction protocol on recovery with new envelope. This is closable in Phase 3 with three pages of spec; not a Phase 4 deferral.

---

## Minor findings (should be addressed; non-blocking)

### m-1. §3.5 `tx_id = hash("FINAL", TX1.tx_id, sese.025_msg_id, camt.054_msg_id)`

The hash inputs include the inbound message IDs but not the *content hashes* of those messages. If a message is restated (M-1 above), the inbound msg_id stays the same in some implementations and differs in others — the hash should include both `msg_id` and the canonical-payload content hash to be deterministic across all restatement regimes.

### m-2. §4.5 row 5 (`sese.024` inbound) opens a `wf-confirm-break` and spawns a `CSDR_PENALTY` obligation

DS4a (B-3) requires: a `sese.024` is the witness that drives `Pending → Failed`. Spawning a CSDR penalty at the same time is good. But the §4.5 wording suggests the break is opened and the obligation moves to Failed — make it explicit that the FSM transition `Pending → Failed` is the *normal* response to `sese.024` (positive fail attestation), not a break. A break is opened only if there's a *disagreement* between attestors (e.g., CSD says fail, custodian says settled).

### m-3. §5.5 idempotency is by `EndToEndId`

This is the right key for ISO 20022. Note: `EndToEndId` is a *trade-side* identifier, not an *envelope-side* identifier. The dedup table key should be `(envelope_dedup_key, EndToEndId)` so that a restatement of the same trade (different envelope, same EndToEndId) is correctly handled as a new envelope, not as a duplicate.

### m-4. §8.4 forgetful functor `F` is a homomorphism

Strong claim. Worth stating which structure it preserves (composition, identity, conservation) and which it does not (per-wallet density, virtual-wallet contras, multi-leg atomicity). The §8.4 paragraph "F preserves: ... F loses: ..." does this informally. Tighten with the explicit theorem statement (it is a conservation-preserving functor on the sub-category of balanced atomic transactions).

### m-5. §10.10 cum/ex audit trail names the data points but not the source attestation

Cross-reference to B-4 above. The "trade execution date T; settlement date T+k; corporate action ex-date; record date; ..." list should attribute each datum to its attestor (trade execution: trader auth; ex-date: CA provider aggregation; record date: CA provider; manufactured payment obligation: framework-generated from the above).

### m-6. §13 G7 "the 'true at T+2⁻' semantics — time-of-day convention"

Closable now. Specify: reconciliation timestamp anchored to relevant CSD's batch settlement time (ECS T2S 18:00 CET; DTCC NSCC end-of-day batch ~16:30 ET; etc.) recorded in `L_4 CalendarConvention` per CSD. Phase 1 §4.3 freshness contract carries this implicitly; lift.

### m-7. §13 G12 "single-source escape on attestation"

Phase 1 §8 had this as TA-DS-10 with quarterly review. The proposal cites G12 as "documentation/registry" Phase-2 work. **It is not closable as documentation.** Single-source escape must be enumerated, owned, and reviewable as part of the trust registry, with detection signals tied to recon-engine output. Not a documentation gap; a specification gap.

---

## What works (preserve)

1. **The PS/PSS virtual wallet pattern with payable/receivable split.** The argument in §2.7 (gross presentation per IFRS 7) is correct, and the constant-time recon scan in §4.3 is operationally elegant. This pattern is the right architectural answer.

2. **The triple representation in §2.1 (real-wallet `own`, virtual wallet contra, `L_15` lifecycle, transaction-level projection).** The boundaries between economic position, contra quantity, lifecycle, and projection are the right ones. PnL path-independence (§3.7) falls out cleanly.

3. **The orthogonality of GPM six-coordinate and deferred-settlement state** (§7.1). The composition examples (short sale lifecycle, recall in window, prepay collateral, naked-short pre-trade guard) are convincing and exhaustive.

4. **The CDM cross-walk** (§8) is rigorous. The 24-element inventory, the Direct/Partial/Missing classification, the six gaps with PR-1..PR-4 sketches are publication-quality. PR-4 (Obligation root type) is the right Rosetta direction.

5. **The accounting/audit/capital section** (§10) is the most thorough I've seen. The five-document audit evidence chain (§10.3), the IFRS 9 ECL staging (§10.4), the CRR Art 378–380 capital ramp (§10.5), and the SOX-404 control objectives (§10.6) are operational-ready. The CO-8 phantom-typing argument (§10.6 final paragraph) is exactly right: "converts segregation of duties from procedural assertion to system property."

6. **The 18 invariants DS1–DS18.** The naming, the parents, the type-vs-runtime decomposition (§11.6 cross-tabbed) are clean. DS1 (Economic-Exposure-at-T), DS4 (no discharge without witness), DS5 (replay determinism), DS18 (DvP atomicity) are the load-bearers; my B-1..B-5 findings make them stronger, not weaker.

7. **The type design** (§12). PairedObligation (§12.2), phantom-typed wallet handles (§12.3), newtype dates (§12.4), the smart-constructor 14-case rejection list (§12.5) are exactly the right type-system investments. The 14-week migration plan (§12.9) is realistic.

8. **The honesty in §13 (gaps) and §15 (known weaknesses).** Settlement Team self-identifies eight known weaknesses; gaps are named with closing constraints; PO-1..PO-10 have named owners. This is the discipline I want in every Phase 2 doc.

9. **The variant-degeneration ruling (§6, DS12).** "T+0 / T+1 / T+2 is a parameter, not an architecture" with the explicit per-variant table (§9.4) is the right structural commitment. The architecture absorbs T+0 atomic on-chain by changing the discharge predicate kind, not by re-architecting.

10. **The append-only log + bitemporal CORRECTION discipline** (§4.9, §6.5, §10.9). Four-eyes non-negotiable; original tx preserved; both query modes first-class. This is the IAS 8.42 prior-period discipline structurally implemented.

---

## Recommendation

ACCEPT_WITH_CHANGES. Five blocking findings (B-1..B-5), eight unmitigated major findings (M-1..M-8), and seven minor findings (m-1..m-7). All findings are *additive* to the proposal — none require redesign of the convergent architecture. The fixes mostly consist of:

- **Lifting Phase 1 §§0, 4, 8, 9 (boundary, aggregation, trust registry, threat model) into the proposal as normative specifications.**
- Closing G5/G7/G12 with normative invariants instead of deferring to documentation.
- Pinning the envelope contract, mapper-version contract, and key-management contract.
- Pulling CSD-outage protocol into scope (§14 deferral is unsafe).

I estimate 2–3 person-weeks of additional spec work to close the blocking findings; the unmitigated majors and minors can be addressed in the same pass. None of this is invention; the source material is in `nazarov.md` Phase 1 plus the cross-references already in the proposal's invariant attributions.

**Pareto-arbiter ruling required (additional, beyond §15.3 list):**

- B-3 (absence-of-finality as attested observation, including CSD-outage protocol) vs §14's deferral. My position: in scope.
- B-5 (trust registry as part of spec, not documentation) vs §15.2 item 5's "operational, not provable" framing. My position: in spec.
- M-3 (ISO 20022 mapping as oracle output) vs the proposal's implicit treatment as transparent. My position: mapping is part of the boundary; specify accordingly.

**Verification approach for Phase 3 audit.** When closures are in place, an auditor confirms compliance by:

1. **Boundary completeness audit** (Phase 1 §10 item 1): every `L_15.Obligation.state` mutation gated by an envelope-verified witness or a `BreakRegister` resolution that itself produced a new attestation.
2. **Replay determinism property test** under random envelope-arrival permutations: 100% pass rate.
3. **Trust-registry coverage check**: every untyped-trust path enumerated against the registry; no orphans.
4. **Threat-model exercise**: for each row of the threat model, the listed mitigation activates against a synthetic attack.
5. **Conservation-under-corrections**: synthesised restatement streams; `Σ_w w(u) = 0` holds in both `as_of` and `with_corrections_through` views.
6. **Key-rotation re-verification**: replay 12-month-old envelopes; confirm verification against historical keys.
7. **Disagreement handling**: synthesised cases where CSD and custodian disagree; obligation does not advance; `L_18` opens; resolution requires four-eyes attestation.

Hold the boundary. The proposal is close. The work that remains is to make the boundary's mechanism as precise as the rest of the architecture.

— NAZAROV, 2026-04-30
