# Round 1 Adversarial Review — proposal_v1.md

**Reviewer:** Chris Lattner (architectural).
**Posture:** Adversarial. I wrote Phase 1 lattner.md. I have not seen any synthesis from the Settlement Team.
**Verdict line:** **ACCEPT_WITH_CHANGES.**

The unified design is recognisably descended from the Phase 1 thesis I argued for: trade-date `own` writes that are never moved by settlement; virtual contras carrying the obligation quantum; L_15 carrying lifecycle; settlement window as parameter; `position(w, u)` returning ownership only. Those are the load-bearing decisions, and they are correct. The rejection of the 7th coordinate and of `u^circ` is the right call for the right reasons.

What I am unhappy with is **encrustation**. The spec has bloated from a five-export library plus one closed-sum constructor into a ~2000-line document with ten new wallet classes, eighteen DS invariants, two parallel FSMs (per-leg and transaction-level) joined by a "MAX projection over a lattice", a 14-week type-discipline migration, and four Rosetta PRs. Some of this is unavoidable when you cross-walk seven domains. Some of it is the system gaining mass it does not need to gain. My review focuses on which is which.

I am not blocking on any of this — the architecture is sound — but several items need to be pulled back, and one (the dual-FSM question) needs to be decided cleanly before Round 2.

---

## Blocking

**B1. Two FSMs, one process — pick one as canonical.**

§2.1 declares the artifacts "well-modularised" but they aren't. There are two FSMs running:

1. The per-leg `L_15.Obligation.state` FSM: 3-leaf closed sum `Pending | Discharged | Compensated | Defaulted`.
2. The transaction-level `MoveStream[tx_id].settlement_status` FSM: 7-state lattice `EXECUTED | INSTRUCTED | PARTIALLY_SETTLED | SETTLED | FAILED | BoughtIn | CANCELLED`.

§2.4 calls (2) a "MAX projection" over (1). §5.1 then says (2) carries states (`EXECUTED`, `INSTRUCTED`, `BoughtIn`, `CANCELLED`) that have no analogue in (1). It cannot be both a projection and an independent FSM. If it's a projection, it must be a deterministic pure function of (1) plus dispatch metadata, with **no independent state**. If it carries independent state (`INSTRUCTED` is a `sese.023`-emit event with no per-leg counterpart), it's a second FSM and must answer: who is the unique writer (DS17)? Is it append-only? Are the two FSMs ever observable inconsistently? What does an operator do when they disagree?

This is exactly the "where does settlement state live" problem the spec was supposed to fix. Right now it lives in two places. **Pick one and demote the other to a derived view computed at the read site.** My recommendation: per-leg L_15 is canonical truth; the seven-state status is a pure projection function `tx_status : MoveStream[tx_id] -> Status` defined in the Library section, callable by anyone, materialised nowhere. If you need it in `L_13` for query speed (§2.1), call it a *cache* and document the cache-invalidation contract — but make it provably equal to the projection at every commit boundary.

This is blocking because the dual-FSM ambiguity is the kind of thing that, in ten years, results in a six-month "settlement state desync" investigation with five teams pointing at each other.

**B2. Conservation across virtual-wallet families is asserted, not proved.**

§2.6 says "PS/PSS wallets are full participants in W_virtual and contribute to the sum by construction" and calls conservation non-negotiable. Good. But §3.5 has the broker's virtual wallet `w_GS_broker` going to `(-100, +5000)` post-finality. Where does `w_GS_broker.own(XYZ) = -100` zero out? It is never drained anywhere visible in §3. If it is a persistent contra against the CSD wallet `w_DTC_depot`, say so explicitly — and add a row to the §3.6 conservation table that includes `w_GS_broker` AND its CSD contra. Today's table omits the broker virtual from one column-set and the CSD from the other; the eye is invited to believe `Σ = 0` because a column is missing from one row and a different column is missing from another.

This is a worked-example bug, not necessarily a design bug, but the worked example is described as "the load-bearing concrete artifact" that the entire spec leans on. Fix the worked example so a reader can verify `Σ_w w_t(u) = 0` over **the same set of wallets at every snapshot** — including the broker virtual wallet at the broker's CSD contra. If you can't get conservation right in the canonical example, you will not get it right in the SBL composition (§7) where there are eight wallets and two coordinate flips per transaction.

---

## Major

**M1. Ten wallet classes is a smell.**

§2.3 introduces `wallet_class ∈ { real, virtual_cpty, virtual_PS_payable, virtual_PS_receivable, virtual_PSS_payable, virtual_PSS_receivable, virtual_nostro, virtual_depot, virtual_inflight_out, virtual_inflight_in }`. That's a 10-way enum. v10.3's wallet model is binary (`is_virtual`) plus a free-form identifier. We have just baked operational classification into the schema.

Two questions to ask before committing:

(a) **Is the distinction observable?** `virtual_PS_payable` vs `virtual_PS_receivable` is observable from the *sign* of the balance and the structure of the trade. Why is it a class? If finops genuinely needs the gross-not-net presentation (§2.7, IFRS 7, fair point), the split is in *how PS_payable and PS_receivable wallets are keyed and constructed*, not in a class enum. The class enum locks in today's taxonomy. The next regulator who wants a third side ("contingent payable on optionality exercise") forces a schema migration.

(b) **What is `virtual_inflight_out` vs `virtual_PS_payable`?** §4.1 has `inflight_out` as a separate term in the recon identity. So we have *two* representations of "money leaving us": the obligation-stage payable and the wire-in-flight inflight. Are they ever simultaneously non-zero for the same trade? If yes (and they probably are, between sese.023 emit and camt.054 ack), conservation requires a transition rule between them, and §3 doesn't show one.

Pull this back. Three classes maximum: `real`, `virtual_obligation_contra`, `virtual_external_mirror` (nostro/depot). The payable/receivable distinction is sign + key, not class. The inflight-out vs PS_payable distinction is **stage in the same FSM**, not two separate wallets — the PS_payable wallet itself transitions through stages, with the stage stored on the wallet's metadata or (better) inferable from the state of the L_15 obligation that holds it.

**M2. The simple case is not yet expressible without invoking the complex case.**

§3 ("standard buy") references PS/PSS wallets, the L_15 obligation row, the discharge predicate, the EndToEndId witness machinery, the seven-state lattice, the bitemporal recon identity with five terms, the `D_2`/`D_18`/`D_8` decimal discipline, the `attempt_seq` tx_id formula, and the saga-tower compensation handler — to describe one buy of 100 XYZ at $50.

A v10.3 reader who has internalised the 3-map ruling should be able to read the standard buy in **one screen** (as in Phase 1 §1.1). They cannot here. The progressive-disclosure failure is real: the spec front-loads every concern that *might* matter (CSDR penalty, partial fill, four-eyes correction, FX leg, Herstatt) instead of starting from the trivial path and adding concerns as variants. §3 should be:

```
trade-date: 4 moves, conservation holds, position is true at T.
T+1: nothing happens.
T+2: 4 moves on virtual wallets, real wallet unchanged, position invariant.
```

Ten lines. **Then** §3.X variants: partial fill, fail, recall, FX, corp action. Reader who only cares about the happy path stops at line ten. Reader who needs partials reads §3.X.partial. Today's §3 is a dump of every consideration, weighted equally.

This is the same bug Apple's old `NSURLConnection` had: the simple case (download a URL) cost the same conceptual budget as the complex case (proxy auth + cert pinning + bandwidth throttling), so newcomers gave up. Swift's `URLSession.dataTask(with:)` fixed it by making the simple thing one line and pushing complexity into options structs that you only see if you ask for them. Same lesson.

**M3. The "MAX projection over a lattice" is not progressive disclosure; it is a leak.**

The seven-state operational status (`EXECUTED → INSTRUCTED → PARTIALLY_SETTLED → SETTLED | FAILED | BoughtIn | CANCELLED`) is what an operations user wants to see. The three-leaf per-leg state is what the framework needs to reason. Right now both are exposed, and the spec spends pages defining the lattice that maps one to the other.

Pick a layering:

- **Library layer (operations):** the seven-state status is a function `status(tx_id) -> Status`. Single export. Operations dashboards call it. Has a stable docstring with the lattice.
- **Closed-system layer (framework):** per-leg L_15 obligation states. That's the only thing the framework proves invariants over. DS8 (status monotonicity) is on the per-leg states. The seven-state thing has no invariants because it has no independent state.

Progressive disclosure: the operations user never sees `Pending | Discharged | Compensated | Defaulted`. The framework engineer never sees `EXECUTED | INSTRUCTED`. They are two views; one materialised, one derived. Today's spec mixes them in §2, §5, §11, §12, and the reader has to keep both in their head simultaneously.

**M4. Eighteen invariants is too many; many are redundant or projections.**

§11 lists DS1 through DS18. Some are genuine new content (DS1 economic-exposure-at-T; DS4 no-discharge-without-witness; DS18 DvP atomicity). Others are direct restatements of v10.3 invariants under new names (DS2 conservation = v10.3 P1; DS5 replay determinism = v10.3 P9 + Λ_8; DS6 idempotency = v10.3 P5 + P6; DS16 bitemporal restatement = the entire bitemporal model). Two are *projections* over other invariants (DS3 reconciliation identity is a theorem from DS2 + the wallet algebra; DS13 reconciliation pair anchoring is a corollary of DS3 + L_11 wellformedness).

Each duplicated invariant is a place where a future restatement of v10.3 P1 (say, when v12 lifts conservation to multi-currency netting) silently desynchronises from DS2, and the formalist who finds the desync three years from now has to figure out which one is "really" the law.

Recommend: prune to the genuinely-new invariants. My count: DS1, DS4, DS7, DS9, DS10, DS11, DS12, DS14, DS17, DS18 are new content. The other eight are either restatements (cite the parent v10.3 invariant; do not re-axiomatise) or theorems (state them as theorems with proofs, not as invariants on the same epistemic footing as DS1).

This isn't pedantry. The invariant register is the **spec for the test generator**. If DS2 and v10.3 P1 are both invariants, the test generator runs both, and the failure mode where they diverge is the kind of thing nobody catches until the second time they diverge.

**M5. Type discipline (§12) is correct in principle, oversold in scope.**

§12 proposes `PairedObligation`, phantom-typed wallet handles, newtype dates, smart constructor with 14 rejection reasons, phantom-typed accounting bases — and a 14-week migration. This is the right *direction* but the wrong *scope* for v11.0.

The five things that are worth their type-system weight:
1. Phantom wallet class (real vs virtual) — DS1 enforcement, cheap, decisive.
2. `PairedObligation` for DvP — DS18 atomicity, structural elimination of half-discharge.
3. Closed sum on lifecycle states — DS8 monotonicity, ban string typos.
4. Closed sum on `failure_reason` — DS9 totality.
5. Newtype `TradeDate` vs `SettleDate` — DS1's enabling discipline.

The five things that are nice-to-have but should be deferred:
6. Phantom-typed accounting basis (trade-date vs settle-date projections at the type level). Settle-date is a *projection*; the projection function being explicit is enough; phantom-typing it is gilding.
7. The 14-failure-mode smart constructor — half of those (Unknown_isin, Unknown_csd_mic, Unknown_party_lei) are reference-data lookups, not type concerns. They belong at the I/O boundary, not in the constructor.
8. Phantom-typed write capability on `SettlStatus` (DS17). The capability discipline of StatesHome C11 is the right place for this; phantom-typing in OCaml is a second mechanism for the same thing.
9. The migration plan as a 14-week project. Stages 1–3 (the five things above) are 6 weeks. Don't sell this as a 14-week project; sell it as a 6-week project with optional follow-on.
10. The cross-currency Herstatt type (`fx_discharge_state`). Right idea; should live in the FX-leg library, not in the settlement core. Otherwise every settlement consumer pays the cognitive cost of FX even when they're trading single-currency.

What should land in v11.0: items 1–5. What should be flagged for v12: items 6–10. Don't ship a 14-week refactor as part of v11.0; ship the high-leverage 6-week piece and signal the rest.

**M6. The deferred-settlement module leaks into too many sections of v10.3.**

The advertised scope (§1) is "smallest possible delta to v10.3". The actual delta touches:

- WalletRegistry KYC schema (10-class enum) — §2.3
- L_15 with new obligation kinds and fields — §2.1
- L_13 MoveStream with `settlement_status` field — §2.1
- L_11 ExternalConfirmation discharge witnesses — §5.4
- L_18 BreakRegister with new break kinds — §4.5
- L_4 CalendarConvention with per-MIC settlement cycles — §6.1
- L_16 ReferenceMaster with CSD enum + κ catalogue — gaps G4
- L_17 RegulatorySubmission with rule-set version pin — §9
- L_7^P PolicyConfiguration with CSDR rate matrix and tolerances — §4.6, §9.2
- ProductTerms with settlement_cycle — §6.1, §9.3
- The 18 invariants vs v10.3's 23 — §11
- A new type system layer — §12

That is not a "smallest possible delta". It's a horizontal cross-cut. Some of those are inevitable (L_11 has to know the discharge witness; L_15 has to carry the obligation row; L_13 has to record the move). Others are scope creep:

- The CSDR rate matrix in `L_7^P` belongs in a separate **CSDR Penalty** module that depends on this module, not inside it.
- The κ catalogue per CSD belongs in a **CSD Reference Data** module.
- The MiFIR/EMIR/SFTR/SLATE matrix in §9 belongs in a **Regulatory Submission** module.

The deferred-settlement module exports the obligation, the discharge predicate, the lifecycle states, and the conservation algebra. That's it. Penalty calculation, regulatory reporting, and CSD-specific compensation are *consumers* of the obligation, not parts of the obligation module. Today's spec fuses them. Decompose them so a reader can read the deferred-settlement module in isolation.

This is the modularity test. v10.3 has the right module decomposition (positions, units, moves, obligations, breaks, calendars, ref data, policy, regulatory, lifecycle). The Settlement spec respects none of it. Pull the module boundaries back.

---

## Minor

**N1. The recon SQL in §4.3 is wrong.** The `SELECT` aliases `wallet_id` as `w_id` once, then groups by `w_id, ccy` while joining `position_state` (which has its own `wallet_id`) — aliasing collides. This is illustrative code and the syntax issue is minor, but the constant-time-vs-join claim hinges on a query that, as written, doesn't compile. Either fix the SQL or write it as relational algebra so the asymptotic claim is verifiable.

**N2. §3.7 PnL math is correct but the framing "path-independence" is misused.** Path-independence in v10.3 P10 means PnL is a function of state, not history. The §3.7 calculation is *PnL preservation across settlement*, which is implied by P10 + DS1 (no real-wallet move at settlement) — but it is not P10 itself. Tighten the citation.

**N3. The deterministic `tx_id` formula in §3.2** uses the literal string `"ECON_REC"` as a domain separator. Fine. But §6.4 partial uses `"FINAL"` with `attempt_seq=0` and `attempt_seq=1` as the disambiguator. The closed sum of domain separators (`ECON_REC`, `FINAL`, `CANCEL`, `BUYIN`, …) should be enumerated and pinned somewhere — otherwise the next person who adds a transaction kind will pick `FINALITY` and silently collide with replays of `FINAL` from before the rename.

**N4. §5.5 idempotency claim is correct; the proof is hand-waved.** "Witness matching is by `EndToEndId`. Replay produces no duplicate state transition (StatesHome P5 idempotency by `tx_id`)." But the witness's `EndToEndId` is not the L_13 `tx_id`; it is a CSD-side identifier. The dedup is on `(EndToEndId, finality_attestation_id)` (§4.5 row), and the property test promised by PO-2/PO-10 is the only thing standing between this claim and a production replay bug. Get PO-10 done before Round 2.

**N5. §6.5 cancellation distinguishes pre-instruction (immediate anti-move) from post-instruction (saga via `sese.030`/`sese.031`). Good.** But the FSM in §5.3 has `* → CANCELLED only via four-eyes CORRECTION`. Post-instruction, the cancellation is contingent on the CSD ack (`sese.031`); the four-eyes is necessary but not sufficient — the CSD has to allow it. State this explicitly: `CANCELLED` requires both four-eyes AND CSD ack OR explicit CSD reject + ops escalation. Today's text says four-eyes alone, which an implementer reading §5.3 in isolation would believe.

**N6. The "Single-Coordinate Move Principle" cited in §10.1 is Lattner-shaped vocabulary** (it's the lemma that each move alters one coordinate of one unit at one entity). Fine. But the spec uses it as a closing argument for why settle-date accounting can't be a primitive, and the actual reason is DS1 + the StatesHome 3-map ruling. The principle is a statement about the *form* of moves; the prohibition is about *when economic recognition happens*. Tighten the argument so it survives the inevitable v12 question of whether settle-date can be a downstream projection (it can; §10.1 even says so) without contradicting the ruling that it can't be a primitive.

**N7. §7.5 short-sale guard is a pre-trade smart-contract check — good.** But the guard reads `avail = own - onloan + borr`, which reads the GPM coordinates. The phantom-typed wallet handles in §12.3 say only `emit_trade` writes real wallets. Fine for writes, but reads are unconstrained — a future "smart" caller could read the wrong projection (e.g., `own_after_pending_settles`) and approve a naked short. Add a positive statement: the locate guard reads only the GPM coordinates, never a settlement-aware projection.

**N8. The "honest gaps" section (§13) is well-done — keep it.** This is the most useful part of the doc for a reviewer trying to figure out what's open. Five of the twelve are closable in Phase 2; commit to closing them before Round 2 rather than carrying them into Round 2 review.

---

## What works (briefly)

- **The thesis: trade-date `own` write, virtual contras, L_15 lifecycle, settlement window as parameter.** This is the right architecture and the spec defends it well against the 7th-coordinate and `u^circ` alternatives. Both rejections are reasoned, not dismissed.
- **DS1 (economic-exposure-at-T) as the load-bearing invariant** with type-level enforcement via phantom-typed wallet handles. This is the single most important commitment in the doc and it is correct.
- **Witness-driven discharge (DS4): no FSM transition without an attested envelope.** This is the right discipline and forecloses the "fail by inference" bug class.
- **§6 variant section: T+0, T+1, T+2, partial, fail, cancel all degenerate to the same FSM with different timer parameters.** This is what "settlement window is a parameter" means concretely. The decade test (T+0 atomic DLT, voluntary corp action choices, partial-then-buy-in cascades) is met by parameterisation, not redesign. This is the test of the architecture and it passes.
- **§8 CDM cross-walk.** The honest classification (Direct 11 / Partial 6 / Missing 7) and the four Rosetta PRs as independent units of upstream work is the right way to engage CDM 6.0.0 → 7.0.0. Keep the forgetful functor F: MoveStream → CDM BusinessEvent — it is the right framing for "Ledger first, CDM downstream".
- **§7.4 recall-during-window: two independent obligations, recursive composition, same FSM at every level.** This is the kind of result that says the architecture composes. The recall doesn't preempt the sale; the sale doesn't preempt the recall; the conflict is resolved by buy-in saga which is itself the same FSM. Lovely.
- **§10.6 segregation of duties via capability typing converts SoD from procedural to structural.** This is the right move. SOX 404 "control" becomes a system property.
- **§13 honest gaps.** Twelve open items, named owners, named properties, distinguished from proof obligations. This is how to handle uncertainty in a spec.

---

## Recommendation

**ACCEPT_WITH_CHANGES.** Approve the architectural thesis. Require the following before Round 2:

1. **Resolve B1.** Pick per-leg L_15 as canonical; make seven-state status a derived projection. Document the cache contract if it is materialised in `L_13`. (1 week.)
2. **Fix B2.** Rewrite §3.5–§3.6 conservation tables to include the broker virtual wallet's CSD contra so `Σ` closes over a constant set of wallets. (1 day.)
3. **M1: collapse the 10-class wallet enum to 3 classes.** Side and inflight-stage become key/sign/state, not class. (3 days.)
4. **M2: rewrite §3 with the 10-line trivial path first, variants later.** Partial / fail / FX / corp action are §3.X subsections, not interleaved into the canonical flow. (1 week.)
5. **M3: split the lifecycle treatment into Library (seven-state for ops) and Closed-system (per-leg L_15 for framework). Stop showing both in §5.** (3 days.)
6. **M4: prune DS to the genuinely-new invariants. Mark restatements as citations and corollaries as theorems.** (3 days.)
7. **M5: scope §12 type discipline to the 6-week core (items 1–5 above); flag the rest as v12.** (1 day documentation update.)
8. **M6: lift CSDR penalty, regulatory matrix, and CSD κ catalogue out of the deferred-settlement module into their own modules with declared dependencies.** (1 week scoping; module boundaries become the contract.)
9. **Discharge PO-1, PO-3, PO-4, PO-9, PO-10** before Round 2 — they are the closable proof obligations and they are the difference between an architectural claim and a verified one.

Items 1–8 are documentation/scoping; ~2.5 weeks calendar with one author. Item 9 is real engineering work; do it in parallel.

**Do not block on:** the Pareto questions (per-counterparty vs per-instruction keying; D_max numeric bound; type-discipline scope). Pareto-arbiter rulings are the right gate, not Round 1. My vote on each:
- **Per-counterparty as the floor; per-instruction as a derived view.** Match the spec's current pin. Per-counterparty is the right granularity for break investigation; per-instruction is recoverable from the move stream + L_15 join.
- **D_max = 2.** Three is a baroque API surface for a workflow that has never recursed beyond 2 in any documented production scenario. Cap at 2; transition to `Defaulted` if the cascade tries to recurse deeper. Pin via property test (PO-9).
- **Type-discipline scope for v11.0:** items 1–5 of M5 above. Items 6–10 deferred to v12 with named owners.

---

## The decade test

Re-read this in 2036.

A reader who has internalised v11.0 + the StatesHome 3-map ruling + L_15 should be able to extend this to:

- T+0 atomic on-chain DvP (already covered, parameter change). Pass.
- Voluntary corporate-action choices in (T, t_d] with default election (covered by L_15 obligation kind extension + saga). Pass.
- Partial fail followed by partial buy-in followed by partial fail (cascade). Pass *if* PO-9 pins D_max and the property test is in place; *fail* if D_max is left unbounded.
- Multi-leg PvP with three legs (CLS-on-chain bridge with three currencies). Pass — `PairedObligation` generalises to `NLegObligation` with the same DvP-atomicity discipline.
- Settlement on a CSD that doesn't yet exist. Pass — CSD κ catalogue is a registry, not a code change.
- Quantum-resistant signature on `sese.025` envelopes. Pass — the L_11 verification predicate is parameterised on signature scheme.

The architecture passes the decade test. The spec, as written, does not — it carries enough operational detail (CSDR rate tables, FINRA SLATE, ESMA recalibration history) inline that a 2036 reader has to do textual archaeology to find the load-bearing primitives. **The architecture should be 200 pages; the operational detail should be in separate modules with versioned references.** The Settlement Team has the architecture right. They have the modularity wrong.

Fix the modularity, ship the architecture, and the next Lattner-equivalent in 2036 will have something to extend rather than something to throw out.

— C.L.
