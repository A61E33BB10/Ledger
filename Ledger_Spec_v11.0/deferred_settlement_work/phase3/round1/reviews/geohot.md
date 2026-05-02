# Round 1 Adversarial Review — geohot

**Verdict: REJECT_REVISE.**

The proposal is technically defensible and probably correct. It is also a 19,770-word cathedral built where my Phase 1 tent stood. The Settlement Team converged toward maximalism. I dissent from the converged design on grounds of complexity, not correctness.

If the goal is "minimum delta to v10.3 to close the deferred-settlement gap" (their own thesis, line 29), this is not the minimum delta. Four new things were added — PS_payable, PS_receivable, L_15 Obligation row, transaction-level FSM, plus per-leg sub-FSM — and labelled as one. The Phase 2 §0 "withdrawal" of the 7th coordinate was the right move. Replacing one rejected thing with four accepted things is not victory; it is rebound complexity.

---

## Blocking issues

### B-1. The "one mechanism" claim hides four new things

§1 sells this as "the smallest possible delta." Counted honestly:

1. PS_payable virtual wallet family
2. PS_receivable virtual wallet family (separate, gross presentation)
3. L_15 Obligation row, kind `SettlementInstructionDelivery`
4. Per-transaction settlement_status FSM on `MoveStream`
5. Per-leg sub-FSM under it (lattice projection)

Plus 10 new `wallet_class` enum values (line 92), four new sidecar columns on `WalletRegistry`, and a 7-state FSM that the team admits compresses to a 3-leaf closed sum (line 555).

Each of (1)-(5) needs to earn its place individually. Calling them "the triple" (§2.1) and waving at "convergence" does not discharge that. **Rebut each one or cut it.** My Phase 1 position — one new field, settlement_status, on the existing Obligation envelope — has not been argued against in this proposal. It has been ignored.

### B-2. PS_payable AND PS_receivable when one signed wallet would do

§2.7 invokes IFRS 7 to justify the gross split. Three reasons given (line 81):

1. Right-of-set-off is jurisdiction-specific — true, **but this is a presentation concern**, not a storage concern. The framework's own ruling (line 144) is "store gross, present net." Storing gross does not require **two wallets**; it requires storing the contributing legs. A single signed `PS[w, cpty, ccy]` with separate `+/-` accumulators (or simply two transactions with opposite signs in the same wallet) preserves the same audit trail.
2. "Aged-payable and aged-receivable trigger different ops workflows." Aging is a **property of the underlying obligation**, not of the wallet. Look at L_15. The wallet is bookkeeping.
3. "Pacioli (1494)." Appeal to authority in a 19,770-word specification is a code smell.

**One PS wallet per (w, cpty, ccy_or_ISIN), signed, is sufficient.** Halves the wallet cardinality, halves the recon scan width, eliminates the question "which side of the split does this hit?" Reject §2.7's argument or live with the doubled cardinality knowingly.

### B-3. Per-leg sub-FSM is unjustified

§5.2 defends per-leg FSM with a single sentence: "needed for partial settlement (one leg `Discharged`, the other `Pending` in DvP Model 2/3 systems) and for half-failed trades."

Partial settlement is on the **quantity** dimension, not the **leg** dimension (one leg, fewer shares delivered than promised). Half-failed DvP is the genuine case. **It happens. How often?** The proposal does not say. CSD-PvP (Model 1) is dominant for cleared cash equity; the half-fail edge is rare and operationally manual anyway (G4: "manual ops workflow").

If half-fail is the only justification for per-leg FSM, **do not run a parallel FSM for the 99% case where both legs share the same fate.** Run one FSM per transaction; emit a `LegInconsistent` failure reason when the rare case fires; route to manual ops. Same outcome, one FSM.

### B-4. The FSM is two FSMs pretending to be one

§5.6: 7 observable states. §5.1: 3 internal leaf states. §2.4: a "MAX projection" maps one to the other via a 7-element lattice. Three FSMs are running:

- Per-leg internal: `{Pending, Discharged, Compensated, Defaulted}` (4)
- Per-transaction observable: `{EXECUTED, INSTRUCTED, PARTIALLY_SETTLED, SETTLED, FAILED, BoughtIn, CANCELLED}` (7)
- Mapping lattice between them

If the projection is deterministic from per-leg state, **delete the transaction-level field**. Compute it on read. If the per-transaction FSM exists for query-speed reasons, say so explicitly and benchmark the cost of computing the projection on read. Do not silently denormalise state and call it convenience.

### B-5. §11 invariants — 12 of 18 are derivable, restated, or trivial

DS1 (Economic-Exposure-at-T) is the only invariant unique to deferred settlement. The rest:

- DS2 (conservation) — restates v10.3 P1
- DS5 (replay determinism) — restates v10.3 P9
- DS6 (idempotency) — restates v10.3 P5/P6
- DS8 (status monotonicity) — derivable from closed-sum FSM definition
- DS12 (variant degeneration) — a meta-claim about the spec, not an invariant
- DS13 (recon pair anchoring) — restates DS3
- DS16 (bitemporal restatement) — restates v10.3 bitemporal model
- DS17 (capability scoping) — restates StatesHome C11
- DS18 (DvP atomicity) — restates v10.3 §8.4

Cut to **6 invariants that are actually new**: DS1, DS3 (recon identity, the new closed-form), DS4 (witness-driven discharge), DS7 (failure non-reversal — new because it depends on DS1), DS11 (partial-conservation), DS14 (CSDR penalty determinism). The rest are inherited and should be referenced, not restated.

A long invariant list is not a stronger invariant list. It is a noisier one. **Aggressive cut required.**

### B-6. §12 type design is a separate proposal

The 14-week migration plan in §12.9 is implementation engineering, not deferred-settlement specification. Phantom-typed wallet handles, newtype dates, smart constructors with 14 rejection cases — every one of these is a good idea **for v10.3 as it stands, today, regardless of deferred settlement**. Tying them to v11.0 means deferred settlement now depends on a 14-week refactor that has nothing structurally to do with deferred settlement.

**Remove §12 from this proposal.** Submit it as a separate type-discipline RFP. Let v11.0 ship runtime invariants for everything, accept the cost, and revisit when the type-discipline RFP lands.

---

## Unmitigated major issues

### M-1. §3 worked example contains the entire spec

The 217-line worked example (§3.2-§3.7) is the most useful section of the document. It is concrete, testable, and falsifiable. **Half the rest of the document is restating it abstractly.** If §3 stood alone with §4.1 (the recon identity), §5.1 (the FSM), and §11 (cut to 6 invariants), the spec would be ~3,000 words and load-bearing.

Specifically: §6.1-6.5 (variants) is a worked-example fan-out that adds nothing. §7 (SBL composition) is a compatibility argument that belongs in v10.3 §13 as an addendum, not as 8 sections of this proposal. §8 (CDM cross-walk) is informational for CDM upstream; cut to a one-page summary plus a separate Rosetta-PR document.

### M-2. §6 variants — same mechanism, same words, repeated

§6.1 (T+1) repeats §9.3. §6.2 (T+0) repeats §9.4. §6.3 (failed) repeats §6.5 of §9.2. §6.4 (partial) is genuinely new (the recursion bound). §6.5 (cancel) is genuinely new (saga shape).

**Three of five variant subsections are duplications.** Delete §6.1, §6.2, §6.3. Keep §6.4 and §6.5. The "settlement window is a parameter" thesis is stated in §1, §6.1, §6.2, §9.3, §9.4, and §13 (DS12). Six restatements. Pick one.

### M-3. §10 accounting — 16 sub-sections is a treatise, not a spec

§10.1 (trade-date mandatory) — keep, this is load-bearing.
§10.2 (worked journal entries) — keep, useful.
§10.3 (audit chain) — could be one paragraph.
§10.4-§10.5 (IFRS 9 / CRR) — informational; reference the standards, do not restate.
§10.6 (SOX/SOC 1 controls) — operational, not architectural.
§10.7 (materiality) — operational.
§10.8 (year-end tie-out) — operational.
§10.9 (CORRECTION policy) — restates §6.5.
§10.10 (cum/ex) — out of scope per §14 already.
§10.11 (Herstatt) — restates §9.3(a).

**Cut §10 from 16 subsections to 3:** trade-date mandatory ruling (§10.1), worked journal entries (§10.2), audit-evidence chain (§10.3 in one paragraph). The rest is operational guidance for an ops team, not specification surface.

### M-4. The "Phase 1 sign error" admission undermines confidence

§4.2 / §4.7: finops "corrects its own Phase 1 §7.7 sign error." §15.1: PO-3 admits the recon-identity sign convention is **still** open for the SBL composition path and "the property test is not yet written." Two phases in, the load-bearing algebraic identity has been pinned twice with the **wrong sign once** and remains unverified for SBL composition.

**Block on PO-3 closure before merge.** Property tests over generated trade streams. No prose. Demonstrate the identity holds on 100k randomly generated trade-counterparty-currency triples crossing both cash-equity and SBL composition paths.

### M-5. Section overlap: §5 + §6 + §11 + §12 all describe the FSM

The same FSM is specified in:

- §2.4 (transaction-level lifecycle)
- §5.1, §5.3, §5.6 (the 7-state observable summary)
- §6.3-§6.5 (variant transitions)
- §11 DS8 (monotonicity)
- §12.1 (type-level encoding)

Five locations. Different formalisms. Inconsistencies likely. **Pick one canonical specification.** I recommend §5.1 + the OCaml type in §12.1 if §12 stays. Delete the prose restatements.

### M-6. The reconciliation identity is stated three times with different signs

§4.1: `nostro_external = own + Σ PS_payable - Σ PS_receivable - inflight_out + inflight_in`
§7.9: `own + borr − onloan − Σ signed_qty(open) = depot`
§11 DS3: `own = depot + InFlight`

Three forms. The proposal does not prove they are equivalent. They might be (§7.9 is for SBL composition; §11 DS3 is shorthand). **State them once with full quantifiers and prove equivalence**, or state one canonical form and derive the others.

---

## Minor issues

- **m-1.** §1 line 31: "smallest possible delta" — falsified by §1 line 33 listing four new constructs. Pick a different framing.
- **m-2.** §2.3: 10 new `wallet_class` enum values. Half (`virtual_nostro`, `virtual_depot`, `virtual_inflight_out`, `virtual_inflight_in`) appear nowhere else in the spec. Delete the unused four.
- **m-3.** §3.2 the `tx_id` formula `hash("ECON_REC", "BUY", ...)` includes the literal string `"BUY"` but no field for `"SELL"`. Specify the closed sum of side strings or use a more obviously closed encoding.
- **m-4.** §4.5 break taxonomy includes `wf-confirm-break` four times for four different conditions. Either they are the same workflow with different inputs (then say so) or they are different workflows that share a name (rename).
- **m-5.** §5.1 lattice has `BoughtIn` between `FAILED` and `Instructed` — but a transaction that has been bought-in is terminal-good (line 610). The lattice ordering `Settled > PartiallySettled > Failed > BoughtIn > Instructed > Executed > Cancelled` puts `BoughtIn` below `Failed` which is below `Settled`. Either `BoughtIn` is terminal-equivalent-to-`Settled` (then put it adjacent) or it is a transitional state (then it is not terminal). Pick.
- **m-6.** §8 has 24 inventory rows then claims 11 Direct + 6 Partial + 7 Missing = 24. Recount: I count 8 Direct, 5 Partial, 7 Missing in the four blocks (24 rows total but composition layer has 5 not 4). Numbers do not add up. Audit.
- **m-7.** §9.1 regulatory matrix has 9 regimes but body discusses only MiFIR, EMIR, CSDR, SFTR. Delete the rows you do not specify, or specify all 9.
- **m-8.** §13 lists 12 gaps and 10 proof obligations. PO-7 has not been completed (minsky's recommendation pending). PO-8 (TLA+ run) has not been executed. **The spec ships unverified.** Either run PO-8 or downgrade the convergence claim.
- **m-9.** §14 lists 5 out-of-scope items. Item 3 (title vs beneficial ownership) is one sentence in scope: "the framework does not encode beneficial-ownership chains." Good. The other four items (liquidity, CSD outages, novation, mass-cancel) leak into the spec elsewhere — §10.4 (ECL = liquidity), G8 (CSD outages), §7.1 (novation in passing). **Either out of scope means out of scope, or it does not.**
- **m-10.** The proposal references "v10.3 FAQ Q5" (line 1527) and "v10.3 FAQ Q6" (line 247) without providing URLs or section numbers. Reviewers cannot verify the cited claims.

---

## What works

- **§3 worked example is excellent.** Concrete, calculable, falsifiable. It is the load-bearing artefact and survives the cut.
- **§4.1 recon identity** (with §4.3 constant-time scan) is genuinely new and genuinely useful. The algebraic-classification approach (§4.8) — CLEAN / EXPECTED LEAD-LAG / BREAK as an algebraic decision, not a manual triage — is the right architecture. **Keep this.**
- **§1's rejection of the 7th coordinate** is correct. Margaret Chen's withdrawal in Phase 2 §0 is the most important paragraph in the proposal. The reasoning (StatesHome 3-map discipline; granularity recoverable as projection) is exactly right.
- **DS1 (economic-exposure-at-T) as an enforced semantic** is a genuine contribution and arguably the entire reason this spec needs to exist. Type-level enforcement via phantom-typed wallet handles (§12.3) is the right mechanism — even though I argue §12 belongs elsewhere.
- **Witness-driven discharge (DS4)** — no fail-by-inference, no fail-by-clock — is correct and load-bearing. Keep.
- **§9.4 T+0 degeneracy table** is the strongest argument that the FSM is genuinely parameter-driven. One concrete artefact, one architectural claim.

---

## Section-by-section DELETE / MERGE / KEEP

| Section | Verdict | Reason |
|---|---|---|
| §1 Convergence | KEEP, cut 50% | Useful framing; "smallest possible delta" is a false claim. |
| §2 State representation | KEEP §2.1, §2.4, §2.5; DELETE §2.7 | §2.7 (gross-vs-net IFRS 7 argument) does not justify the dual-wallet split. |
| §3 Worked example | KEEP in full | Load-bearing. The spec without §3 is unverifiable. |
| §4 Reconciliation | KEEP §4.1, §4.3, §4.8; cut §4.4-§4.7 to operational appendix | §4.4-§4.7 is ops runbook, not spec. |
| §5 FSM | KEEP §5.1, §5.4; DELETE §5.2-§5.3, §5.6 | Per-leg FSM not justified (B-3); restatement of §5.1. |
| §6 Variants | KEEP §6.4, §6.5; DELETE §6.1-§6.3 | Three of five subsections duplicate §9. |
| §7 SBL composition | MERGE into v10.3 §13 addendum; do not duplicate here | Belongs in v10.3 SBL spec, not v11.0 deferred settlement. |
| §8 CDM cross-walk | DELETE most; keep one-page Gap-6/8/9/10 summary | Implementation note for Rosetta upstream; not v11.0 spec. |
| §9 Regulatory | KEEP §9.1 row count, §9.4 (T+0 test); DELETE §9.2, §9.3, §9.5-§9.7 | Regulatory mapping is ops, not spec. T+0 test is the architectural argument. |
| §10 Accounting | KEEP §10.1, §10.2, §10.3 (paragraph); DELETE §10.4-§10.11 | 16 subsections is a treatise. 3 is a spec. |
| §11 Invariants | CUT from 18 to 6 | DS1, DS3, DS4, DS7, DS11, DS14. The rest are inherited. |
| §12 Type design | EXTRACT to separate RFP | Independent of deferred settlement. Couples v11.0 to a 14-week refactor. |
| §13 Gaps + POs | KEEP, but block on PO-3 + PO-8 | PO-3 (sign convention) and PO-8 (TLA+) must close before merge. |
| §14 Out of scope | KEEP, cut to one paragraph | Useful boundary statement. |
| §15 Ready-for-review | DELETE | Self-praise. The reviewers decide if it is ready. |

**Estimated post-cut length: 4,500-5,500 words.** Down from 19,770. Same correctness. Better hackability.

---

## Argument against the maximalists by name

- **finops** — gross PS_payable + PS_receivable split. **Rebut B-2 or accept the doubled cardinality knowingly.** The IFRS 7 argument is presentation, not storage.
- **formalis** — per-leg sub-FSM. **Rebut B-3 with frequency data on half-failed DvP** or accept that the per-leg FSM exists for the rare-edge case and run one FSM for the 99% path.
- **ashworth** — §10's 16 subsections. **Cut to 3.** Most of §10 is operational guidance, not architectural specification.
- **matthias** — §8's 24-row CDM cross-walk + 4 Rosetta PRs. **This is upstream-CDM advocacy work, not v11.0 spec.** Submit to FINOS as a separate paper.
- **minsky** — §12's 14-week type-discipline refactor. **Submit as separate RFP.** v11.0 should not depend on this.
- **isda** — 9 regulatory regimes in §9.1. **Specify all or delete.** A row in a table that the body does not discuss is noise.
- **testcommittee** — PO-8 (TLA+) is a proof obligation, not a deliverable. **Run TLC before merge** or downgrade the "implementation-ready" claim to "implementation-ready pending TLA+."
- **Settlement Team as a whole** — §1's "smallest possible delta" claim is rhetorically convenient and technically false. **Rename it "the convergent design" and stop selling minimality you have not delivered.**

---

## Recommendation

**REJECT_REVISE.** Block on:

1. **B-1 + B-2 + B-3:** Rebut the four-things-not-one criticism explicitly, or cut PS_receivable, cut per-leg sub-FSM, cut transaction-level denormalised status.
2. **B-5:** Cut §11 invariants from 18 to ~6 genuinely new ones.
3. **B-6:** Extract §12 to a separate type-discipline RFP. v11.0 ships with runtime invariants for everything except DS17 (capability scoping) which v10.3 already has.
4. **M-3:** Cut §10 to 3 subsections.
5. **M-4:** Close PO-3 with property tests before merge.
6. **m-8:** Run PO-8 (TLA+ TLC) before claiming convergence.

Word count target after revision: 4,500-5,500. The revised proposal will be **easier to verify, easier to implement, and harder to misread**. The Geohot Test (§Geohot principles): "Is this the simplest possible solution? Could anything be removed?" Yes. Aggressively. Most of it.

**The cathedral is impressive. We need the chapel.**

— geohot
