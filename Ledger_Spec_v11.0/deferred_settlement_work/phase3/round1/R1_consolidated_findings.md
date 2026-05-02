# R1 Consolidated Findings — Deferred Settlement Phase 3 Round 1

**Reviewers (10):** jane_street, correctness, testcommittee, nazarov, geohot, feynman, temporal, halmos, cartan, lattner.

**Verdict tally:**
- REJECT_REVISE: geohot, temporal (2)
- REQUEST CHANGES: jane_street (1)
- ACCEPT_WITH_CHANGES: correctness, testcommittee, nazarov, feynman, halmos, cartan, lattner (7)

**Total findings:** ~48 blocking, ~74 major, ~30 minor. **Pareto NOT reached.** Round 2 required.

---

## Cross-cutting BLOCKING themes (must close in v2)

### Theme 1 — The §3 worked-example conservation table is broken (jane_street B-1, lattner B-2, feynman, halmos B-6)
**Issue.** The post-finality wallet snapshot leaves `w_GS_broker.own(USD) = +5,000` and `(XYZ) = -100` as the contra, but never explains where on the CSD/JPMC side the matching mirror lives. The internal sum no longer closes to zero unless the nostro mirror wallets are added — which is what makes conservation hold under v10.3 §2 `Q(u)=0`.
**Fix in v2.** Add explicit `w_DTC_depot_mirror[GS]` and `w_JPMC_nostro_mirror[GS]` virtual wallets that are credited at finality so that the conservation sum closes over a constant set. Tighten the §2.6 conservation summary tables to show this constant set throughout T, T+1, T+2⁻, T+2⁺.

### Theme 2 — Sign convention in §4.1 recon identity vs §11 DS3 (feynman B-2, jane_street B-2, halmos B-7, cartan B-3)
**Issue.** The §4.1 boxed identity and §11 DS3 statement use opposite sign conventions on the receivable terms. The buy worked example coincidentally produces the right number; the SELL case fails by 100,000 in feynman's independent computation. §15.1 admits sign convention is open weakness; §4.2 claims it is fixed. Contradiction.
**Fix in v2.** Pick one canonical sign convention. Restate §4.1, §11 DS3, and verify it on BOTH a BUY and a SELL worked example. Anchor in unit tests (testcommittee m6).

### Theme 3 — Attestation envelope completely unspecified (nazarov B-1 to B-5)
**Issue.** DS4 ("no discharge without witness") is referenced but the attestation envelope (signature scheme, dedup key, verification predicate, schema-version pin), multi-source aggregation protocol, fallback chain, "absence of finality is itself attested", and trust-assumption registry are all referenced and not specified.
**Fix in v2.** New subsection in §5 (or §4) specifying:
- Attestation envelope = JCS-canonical payload + Ed25519 sig + ts + dedup_key + schema_version
- Multi-source aggregation: CSD primary; quorum-of-2 from custodian + counterparty when CSD silent; never single non-primary
- Absence-of-finality protocol: silence past T+2 cutoff + watchdog timer triggers `wf-confirm-break`, NOT auto-FAIL
- Trust-assumption registry TA-DS-1..10 listed in §13 gaps as named entries
- Cum/ex ex-date observation as multi-source attestation

### Theme 4 — Workflow layer underspecified (temporal B-1 to B-5 + 10 majors)
**Issue.** SettlementSaga, BuyInWorkflow, MorningReconWorkflow are named and leaned on for DS5/DS6/DS9/DS17/DS18 enforcement but not specified. Specifically:
- `tx_id` formula in §3.2 lacks `business_event_id` namespace and `attempt_seq`
- §3.5 DvP discharge as one transaction contradicts independent arrival of sese.025/camt.054
- DS5 (replay determinism) not testable without commutativity table for signal handlers
- T+2 trigger mechanism (deadline + fallback poll) silently dropped from Phase 1
- Workflow ID granularity (per-leg vs per-bucket) unspecified
**Fix in v2.** New §6.5 (workflow specification) covering:
- Canonical `tx_id = hash_jcs(business_event_id, attempt_seq)` with `attempt_seq` carried across ContinueAsNew
- DvP atomicity at discharge: producer-monotonic per-leg consumption with single observable settlement event
- Signal-handler commutativity table covering all DS5 axes
- T+2 trigger = deadline timer with watchdog fallback (Phase 1 design restored)
- Workflow ID = per-obligation; ContinueAsNew payload schema specified

### Theme 5 — FSM/projection contradiction (lattner B-1, halmos M8)
**Issue.** Two FSMs run in parallel: per-leg `L_15.Obligation.state` (3-leaf for Pending/Discharged/Compensated/Defaulted) and transaction-level `MoveStream[tx_id].settlement_status` (7-state for EXECUTED/INSTRUCTED/PARTIALLY_SETTLED/SETTLED/FAILED/BoughtIn/CANCELLED). The 7-state cannot be a "MAX projection" of the 3-state because EXECUTED, INSTRUCTED, BoughtIn, CANCELLED have no per-leg analogue.
**Fix in v2.** Pick per-leg `L_15.Obligation.state` (with a fuller closed sum: `Pending | Instructed | PartiallySettled | Discharged | Failed reason | BoughtIn | Cancelled | Compensated`) as canonical. The transaction-level field is a Library-layer projection function `tx_status(L_15 rows for tx)` — NOT stored, NOT a separate FSM. Demote to ops-convenience view in §5.

### Theme 6 — Goodhart traps for deferred settlement not addressed (correctness B-6)
**Issue.** The brief and prior-art identify three deferred-settlement-specific Goodhart traps:
- G-DS-1 (quick-finality bias in generators)
- G-DS-2 (global conservation tested but not per-class)
- G-DS-3 (record-and-replay LLM tests)
None addressed in §11–§13.
**Fix in v2.** Add these to §13 as dedicated Goodhart subsection with per-trap mitigation.

### Theme 7 — Walking-skeleton test gaps (testcommittee B-2)
**Issue.** 8 of 12 walking-skeleton variants from Phase 1 §2.3 have no test in proposal_v1: Sell happy, T+1 happy, recon-lag E2E, short, recall, CA, FX Herstatt, DvP CSD-reject.
**Fix in v2.** Add §10.X (or §13 PO-X) test plan listing all 12 walking-skeleton tests as sign-off prerequisites.

### Theme 8 — Property generators unsound (correctness B-3, testcommittee B-3)
**Issue.** Generators described in prose, not implementable. Failure-reason space not enumerated as closed sum. CA generation outside the open window. Single-trade-only DS5 generator.
**Fix in v2.** Specify generator type signatures + shrink lattices for the 6 new dimensions. Enumerate failure_reason as closed sum (must match minsky §12 closed-sum exhaustively).

### Theme 9 — Notation discipline (halmos B-1 to B-7)
**Issue.** No §0 notation table. PS/PSS namespace inconsistent (six surface forms). 8/18 invariants have implicit ∀-binders in prose. Greek/ad-hoc symbols (Λ_n, κ_buyin, Δ_CSDR, F_terminal, D_max, τ_*) introduced without home. Obligation naming bimodal (`u_sale`/`o_sec`/`o`).
**Fix in v2.** Add §0 notation table (single canonical form for every symbol). Pin obligation naming convention. Pin wallet-class naming convention. Pin scope/quantification on every invariant in §11.

### Theme 10 — Conservation Lifting not stated as theorem (cartan B-2)
**Issue.** Conservation Lifting is asserted as conclusion (§2.6) without being stated as a theorem with explicit hypotheses.
**Fix in v2.** State as Theorem with hypothesis list:
- H1: every PS/PSS-touching transaction is balanced
- H2: virtual wallet credits and debits are signed-correctly per §1.5
- H3: ...
Then conclusion `Σ_w w_t(u) = 0 ∀(t,u)`. Proof outline by induction on transaction kinds.

### Theme 11 — Storage strategy missing (jane_street B-4)
**Issue.** Per-leg L_15 at 10^7 trades/day = ~10^10 obligation rows/year with 7-year retention. Sharding, archival, hot-vs-cold partitioning all absent.
**Fix in v2.** New §10.X.X (storage and retention) covering: hot retention 90 days; warm 7 years; ID partitioning by `(year, business_event_id_hash_prefix)`; index strategy.

### Theme 12 — First-class unit dismissal underargued (cartan B-1)
**Issue.** §15.2 says the two representations would map 1-to-1; this IS the bijection $\Phi$ that would have been the proof. Either prove it (and rest the rejection on operational cost) or identify what differs.
**Fix in v2.** Either:
- Prove bijection $\Phi$: `(virtual wallets + L_15 row + FSM) ↔ first-class u_obligation` → choose mainstream on operational cost.
- Or identify a fact only the first-class representation captures (e.g., exposure transfers between sub-balances) and reject because that fact is not load-bearing.

### Theme 13 — Forgetful functor F is lossy, not a homomorphism (cartan B-4)
**Issue.** §8.4 calls F a homomorphism but the proposal's own "F loses" list contradicts.
**Fix in v2.** Rename to "lossy non-faithful functor" OR define the wallet-axis-collapsed quotient `Lg_econ` and state F restricted to that quotient is a homomorphism.

---

## Cross-cutting MAJOR themes (must address in v2 or document trade-off)

### Theme A — Too many invariants (jane_street M-2, lattner M-4, geohot B-5, cartan M-3)
DS2/DS5/DS6/DS16 are restatements of v10.3 P1/P9/P5+P6/the bitemporal model. DS3/DS13 are theorems, not invariants. **Prune to ~10 genuinely new ones.**

### Theme B — Type-discipline migration scope (jane_street M-3, lattner M-5, geohot B-6)
14-week / 1.5-engineer migration is fantasy AND/OR out of v11.0 scope. **Keep core 5 items in v11.0 (~6 weeks): phantom wallet class, PairedObligation, lifecycle closed sum, failure_reason closed sum, TradeDate/SettleDate newtypes. Defer rest to v12 RFP.**

### Theme C — CORRECTION transaction policy underspecified (jane_street M-5, M-6, temporal M-1)
Cross-correction, regulatory-already-reported, correction-of-correction; manual override absent from FSM. **Spell out in §10.9 + §6.X.**

### Theme D — Block-and-allocation chains absent (jane_street M-7, finops Phase 1 also flagged)
Asset-manager dominant flow shape. **Add as §7.X composition case.**

### Theme E — Wallet class enum bloat (lattner M-1, geohot)
10 classes; side (payable/receivable) is sign+key not class; inflight-stage is FSM state not separate family. **Pull back to 3 classes.**

### Theme F — Bitemporal restatement under DS5 (correctness, cartan M-2, testcommittee M-6)
DS5 over-quantified relative to G5 (CSD restatement is allowed). **Restate as: replay determinism over the multiset of finalised witnesses; restatements update t_known but original t_obs preserved.**

### Theme G — DS3/DS13 redundancy and DS11 split (cartan M-3)
DS6⊂DS5; DS13⊂DS3; DS11 should split into per-partial-fill conservation + monotonicity through partials. **Restructure §11.**

### Theme H — DvP atomicity used in 3 senses (cartan M-5, lattner)
"DvP atomicity" used at: (a) ledger-transaction-level (Move pair atomicity), (b) settlement-utility-level (CSD DvP Model 1), (c) economic-recognition-level (PairedObligation discharge). **Disambiguate as DvP-L, DvP-S, DvP-E.**

### Theme I — Capital reasoning depth (ashworth Phase 2 OK, but reviewers want more)
Pillar 3 disclosure shape; specific RWA aging schedule under CRR Article 379. **Already in §10.6 but reviewers want a worked example.**

### Theme J — Regulatory regime expansion (isda matrix), but geohot wants it cut
Tradeoff: keep matrix (operational), but cut prose to table + 1-paragraph-per-regime.

---

## Settlement Team v2 work plan

The Settlement Team must produce `proposal_v2.md` in Round 2 closing every BLOCKING finding and addressing every MAJOR finding (or documenting the trade-off). Round 2 panel should include:
- Original 7 Settlement Team members (revising their sections)
- New temporal-engineer seat for the workflow layer (Theme 4) — temporal is ADDED to Settlement Team for v2

The arbiter (independent FORMALIS instance) declares Pareto when:
- Zero blocking remain
- Zero unmitigated major remain
- No minor improvement without offsetting trade-off

Estimated work: 7-10 person-days of revision; one more R2 review of ~5-8 reviewers; then Pareto check.

---

## Proposed v2 structural additions (new sections)

- **§0** Notation table (closes Theme 9)
- **§4.5** Attestation envelope + multi-source aggregation + absence protocol (closes Theme 3)
- **§6.5** Workflow specification — saga shapes, signal handlers, idempotency keys (closes Theme 4)
- **§10.X** Storage and retention strategy (closes Theme 11)
- **§13.4** Goodhart traps for deferred settlement (closes Theme 6)
- **§13.5** Trust-assumption registry TA-DS-1..10 (part of Theme 3)

## Proposed v2 structural changes

- §3 worked example: re-derive with constant-wallet-set conservation table; add SELL worked example
- §4.1 + §11 DS3: unify sign convention; verify on BUY and SELL
- §5 FSM: per-leg L_15 canonical, tx_status as projection function (closes Theme 5)
- §11: prune from 18 to ~10 invariants; restructure DS3/DS13/DS11 (closes Theme A, G)
- §12 type design: scope to 5-item v11.0 core (closes Theme B)

---

End of consolidated findings. Settlement Team to produce proposal_v2.md addressing each Theme.
