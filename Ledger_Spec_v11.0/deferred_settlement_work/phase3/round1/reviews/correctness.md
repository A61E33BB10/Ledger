# Round 1 Adversarial Review — Correctness Architect

**Subject.** `proposal_v1.md` — Phase 2 Settlement Team Unified Design for Deferred Settlement on Cash Equities.
**Reviewer.** Correctness Architect (Will Wilson, deterministic-simulation lens).
**Date.** 2026-04-30.
**Scope.** §1–§15, with adversarial focus on property completeness, determinism boundaries, witness hygiene, generator soundness, fault catalogue, and Goodhart traps specific to deferred settlement.

---

## Verdict

**ACCEPT_WITH_CHANGES** — conditional on closing **B-1 through B-6**.

The proposal is the most architecturally honest deferred-settlement specification I have reviewed in the v11.0 stream. The triple (real `own` write at T + PS/PSS contras + L_15 obligation) cleanly preserves StatesHome's three-map ruling, conservation is non-negotiated (§2.6), settlement-state-as-projection is the right architectural call, and §3 walks the entire move-pair sequence with conservation tables. §12 (type design) is the most leverage-per-line section — `PairedObligation` and phantom-typed wallet handles structurally eliminate two whole disaster classes (DS18 atomicity at discharge, DS1 economic-exposure-at-T leakage).

But the property catalogue (DS1–DS18) has silent gaps, several invariants are conflated, two non-deterministic boundaries are not enumerated, the generators are mentioned without sound construction, the differential-testing oracle is implicit, and the Goodhart traps named in the review brief (G-DS-1 quick-finality bias, G-DS-2 global-not-per-class, G-DS-3 record-and-replay) are not mentioned anywhere in §11–§13. These are blockers. None require redesign — all are closable by named property additions and explicit catalogue entries.

I do not yet trust that §4's SQL projection cannot corrupt PnL silently. I do not yet trust that §5's FSM is total under all witness orderings. I do not yet trust that the §3 worked example contains enough numerical sanity checks to catch the next sign error after the one finops corrected. These three trust gaps are concrete and addressable.

---

## Blocking — Must close before approval (B-N)

### B-1. The 18 invariants are NOT a complete property catalogue. Six gaps.

DS1–DS18 cover the structural backbone but six properties that any deferred-settlement system MUST hold are silent:

**B-1.a — Path-independence under reordering of finality witnesses.** DS5 says `apply(σ_0, π_1) = apply(σ_0, π_2)` for two interleavings. This is correct but **insufficient**. The open property is: for two trades A, B touching the **same** `(w, u)` whose finality witnesses arrive in either order, the post-state must be identical. DS5 as stated only asserts this for the *same* multiset of messages targeting the *same* obligation — not for cross-trade interleaving. Add:

```python
@given(trade_pair=trades_touching_same_wallet_unit(),
       witness_order=permutations_of_finality_messages())
def test_cross_trade_finality_path_independence(trade_pair, witness_order):
    state_a = apply_in_order(initial, trade_pair, witness_order[0])
    state_b = apply_in_order(initial, trade_pair, witness_order[1])
    assert state_a.position_state == state_b.position_state
    assert state_a.l_15_obligations == state_b.l_15_obligations
    # MoveStream order may differ but the projection MUST equal.
    assert project_settlement_status(state_a) == project_settlement_status(state_b)
```

This is the most important missing property. Without it, DS5 is a single-trade property and the proposal cannot claim "out-of-order witnesses commute" as §5.5 does.

**B-1.b — PnL invariance across the discharge boundary (DS1's enforceable runtime form).** DS1 says no projection differs during `[T, t_d^-]` from after `Settled`. Make this a runtime test, not a definitional claim:

```python
@given(trade=any_t2_trade(), price_path=any_price_path_between_T_and_settled())
def test_pnl_path_independence_through_discharge(trade, price_path):
    pnl_no_discharge = compute_pnl(state_at_T_plus_2_minus(trade, price_path))
    pnl_after_discharge = compute_pnl(state_at_T_plus_2_plus_settled(trade, price_path))
    assert pnl_no_discharge == pnl_after_discharge  # exact decimal equality
```

This catches the worked-example claim of §3.7 by construction.

**B-1.c — Reconciliation identity preservation under partial settlement chains.** DS3 holds for fully-settled or fully-pending trades. The recursion-bounded partial cascade (§6.4, PO-9) is silent on whether the identity holds after each `TX_partial_k` step. Add:

```python
@given(trade=any_trade(), partial_sequence=any_partial_fill_sequence(max_depth=D_max))
def test_recon_identity_holds_at_every_partial_checkpoint(trade, partial_sequence):
    state = initial
    for partial_event in partial_sequence:
        state = apply(state, partial_event)
        assert recon_lhs(state) == recon_rhs(state)  # every checkpoint
```

**B-1.d — Compensation κ-totality across `EventClass × ObligationKind`.** Data spec L_15 (`Φ_15^C`) requires κ-totality. The proposal §11 lists DS9 (buy-in compensation closure) as runtime / HIGH, but does not assert that the κ-matrix is structurally exhaustive. This is the moral equivalent of "what happens if a witness arrives that no handler dispatches on" — a witness-launderer's paradise. Add a **compile-time** invariant: `compensation_handler` is a closed-sum dispatch over the populated `EventClass × ObligationKind` grid; missing cells fail to compile.

**B-1.e — Obligation count conservation across partial-fill recursion.** PO-9 caps recursion at D_max. What is the property that beyond D_max the cascade transitions to Defaulted? Spell it out:

```python
@given(trade=any_trade(), pathological_partial_path=adversarial_partial_path())
def test_partial_cascade_terminates_at_d_max(trade, pathological_partial_path):
    state = apply_partial_cascade(initial, trade, pathological_partial_path)
    open_obligations = count_pending(state, trade.tx_id)
    assert open_obligations == 0  # all terminal
    assert all_descendants_in_terminal_state(state, trade.tx_id)
```

**B-1.f — Witness-uniqueness invariant (precondition for DS6).** DS6 (idempotency by EndToEndId) holds **only if** EndToEndId is a hash function over witness essentials with no collisions in the reachable space. The proposal §5.5 names `EndToEndId` but does not assert collision-resistance; the data spec Λ_10 commits to `tx_id = hash_jcs(business_event_id, attempt_seq)` but does not pin the witness-side. Add an explicit invariant: **DS19 — Witness-Identity Determinism**: every confirmation message has a content-addressed identity such that two structurally-equivalent confirmations from the same CSD have identical IDs. Without this, idempotency is faith.

### B-2. Two non-deterministic boundaries are NOT enumerated as injectable.

§3.5 says the SettlementWorkflow consumes the inbound finality and emits TX1_FINAL "atomically". §11 DS17 names capability scoping. But the **non-deterministic boundaries** are not catalogued. The proposal needs a §11.bis or §13.bis that exhaustively lists every source of non-determinism, classified as injectable / not-injectable:

| Boundary | Source | Injectable? | DS gate |
|---|---|---|---|
| Wall-clock time at trade execution | `ClockAuthority` | yes (per L_19) | tested via DS5 |
| Settle-date computation | `CalendarPin` (L_4 versioned) | yes | tested via §12.4 |
| Inbound `sese.025` arrival ordering | CSD network | yes (SimulationCSD) | DS5 + B-1.a |
| Inbound `camt.054` arrival ordering | Cash agent | yes | same |
| **`tx_id` hash function** | `hash_jcs(business_event_id, attempt_seq)` | yes if seed-pinned, **NO if hash collisions** | NOT NAMED |
| **CSDR rate-matrix lookup** | L_7^P version pin | yes via VersionPinSidecar | DS14 |
| **Counterparty default declaration** | LifecycleOracle event | yes? | DS15 — UNDER-SPECIFIED |
| **Concurrency between inbound witness and outgoing CORRECTION** | Temporal scheduler | yes (deterministic Temporal in test) | NOT NAMED |
| **Restated confirmation arrival** | CSD restatement after we already discharged | yes | G5 (UNCLOSED) |
| Random `attempt_seq` selection on retry | Temporal | yes via `attempt_seq` field | Λ_10 |

The two missing rows (`tx_id` collision and inbound-witness-vs-outbound-CORRECTION race) are blockers because:
- A `tx_id` collision in the partial-fill recursion (§6.4) silently merges two distinct partial events into one. The `attempt_seq` field is named but not proved injective in §6.4's two-partial example (`hash("FINAL", TX1.tx_id, sese.025_partial1_msg, 0)` vs `hash("FINAL", TX1.tx_id, sese.025_partial2_msg, 1)` — this assumes `sese.025_msg_id` is unique per partial; if a CSD restates a partial with the same msg_id, the sequence collides).
- The race between an arriving `sese.025` and an in-flight `CORRECTION` cancellation (§6.5 "post-instruction cancel") needs a documented conflict-resolution policy. Currently §6.5 says "the trade is locked, cancellation impossible until either settle or fail", but the SettlementWorkflow's signal-handler ordering is the deciding factor. This is exactly the kind of race that dooms FoundationDB-class systems.

### B-3. Generators (§13 mention, no construction) are unsound as currently described.

The proposal mentions property-tests over "generated trade streams" (PO-3, PO-4) but **never specifies the generator**. This is the single biggest "tests ship green but find no bugs" risk. Three generator-soundness blockers:

**B-3.a — Witness multisets must be generated, not single-traced.** A generator that produces `(trade_T, sese.023_T+ε, sese.025_T+2)` linearly will never find the B-1.a cross-trade-reorder bugs. Generators must produce a **multiset** of witnesses for a multiset of trades and apply them in **all permutations** (or a Hypothesis-shrinkable subset).

**B-3.b — Failure-reason space must be enumerated, not free-form.** §12.1's `failure_reason` closed sum has 6 cases. The generator must produce one of each (Hypothesis `sampled_from`), with `CsdReject` further enumerating the closed `Csd_reject_code` sum (G1, PO-5 — currently NOT pinned, see B-5). A generator that only produces `DeadlineMissed` will type-check and pass and find zero CSD-reject bugs.

**B-3.c — Pathological-but-legal corporate actions must be generated within the open window.** G3 / PO-4 names the 2-for-1 split case. Generators must produce: (i) splits, (ii) reverse splits, (iii) cum-dividend record dates inside `(T, t_d]`, (iv) symbol changes, (v) merger with cash-or-stock election. Without a generator that synthesizes these inside the open window, the bitemporal-predicate-evaluation property is theatre.

Until §13 produces a **generator catalogue** (one generator per type that any property test consumes), the property tests are decorative.

### B-4. Differential testing oracle is unnamed — what does the implementation differ AGAINST?

§11 DS5 says "replay determinism". §13 PO-8 says "TLA+ model check at |W|=3, |U|=2, depth=8". Neither names a **reference implementation** for differential testing. Two missing oracles:

**B-4.a — A naive sequential reference.** The simplest possible implementation that violates none of DS1, DS2, DS18 — process witnesses one-at-a-time, single-threaded, no Temporal, no caching — produces a reference state. The high-performance Temporal-driven implementation must produce **bit-identical** state. Without this, "the implementation passes its own property tests" can be satisfied by a circular oracle (the implementation is its own oracle).

**B-4.b — CDM forgetful-functor F as an oracle.** §8.4 defines F : Lg → CDM. F is described as a homomorphism. The differential test is: for any deferred-settlement scenario, F(ledger_state_after_scenario) must equal CDM_state_after_F_applied_to_each_event(scenario). This is a structural oracle. Currently §8 names F but does not commit to F as a test oracle.

Add to §13 PO-11 (new): "Implement a reference sequential interpreter and a CDM-state homomorphism oracle. Every property test in PO-1..PO-10 must additionally check the implementation's state matches the reference and projects to the CDM state."

### B-5. Fault injection catalogue is incomplete vs. the review brief's enumerated list.

The review brief enumerates: CSD partial responses, duplicate finality, finality-then-retraction, reorder of finality vs trade, network split, clock skew. The proposal addresses some but not all:

| Fault | Addressed? | Where |
|---|---|---|
| CSD partial responses | Partial — §6.4 covers happy-path partial; §13 G1 names the closed-sum mapping gap | PO-5 owner=isda |
| Duplicate finality | Yes — §4.5 row 7 (idempotently dropped) + DS6 | Pinned |
| **Finality-then-retraction (G5)** | Named as G5 with recommended (a) "treat as new obligation" — **but no property test** | **NOT CLOSED** |
| Reorder of finality vs trade | Yes — DS5 + §5.5 | Partial; B-1.a deepens it |
| Network split | **NOT NAMED** anywhere | **MISSING** |
| Clock skew | Partial — §13 G7 names time-of-day; G8 names cluster outage | **MISSING the Byzantine clock case** |
| CSD silently double-debits nostro and reports it | NOT NAMED — recon catches it but no property | **MISSING** |
| L_11 envelope signature-verify failure | §10.3 says "signature-verified at ingress"; no fault-injection of forged envelopes | **MISSING** |
| Bugification (legal-but-pathological CSD behaviour) | NOT NAMED | **MISSING** |

**Network split** is non-negotiable. The proposal sites the SettlementWorkflow on Temporal (§13 PO-10). Temporal can fail-over; during fail-over, an inbound `sese.025` may be retried. The proposal must specify: under network split between Ledger and CSD, what is the property? My read is `eventual idempotent re-ingestion preserves DS6`, but it is NOT stated.

**Clock skew under Byzantine assumption** matters for G7. If two CSDs report finality at ostensibly the same wall-clock time but the Ledger's `ClockAuthority` is skewed, does the deterministic projection produce the same answer? §11 DS17 names capability scoping but not clock-source attestation. Add to DS5: replay is deterministic *only when ClockAuthority is also pinned*.

**Bugification** (FoundationDB term) — injecting legal-but-pathological CSD behaviour: a CSD that always sends `sese.025` 10 seconds before the matching `camt.054`; a CSD that always partials at exactly the legal minimum; a CSD that always restates 1 share at end-of-day. The fault catalogue must include a **bugification operator** that systematically tests these. Without it, the test suite finds the average bug, not the adversarial bug.

### B-6. The three deferred-settlement Goodhart traps are not addressed.

The review brief explicitly enumerates G-DS-1 (quick-finality bias), G-DS-2 (global-not-per-class), G-DS-3 (record-and-replay). These are **not mentioned** in §11, §12, §13, or §15.

**G-DS-1: Quick-finality bias.** A test suite that only generates `expected_settlement_date = T+2` and `actual_finality = T+2` will never test the long tail (T+5, T+15, T+45 CSDR migration). Coverage criterion: the generator MUST produce trades whose actual settlement date is sampled from the empirical fail-tail distribution, not the median. Without this, the framework optimizes for the easy 99% and fails on the catastrophic 1%.

**G-DS-2: Global-not-per-class.** A coverage metric of "98% of trades are CLEAN" is meaningless if that 98% is 100% of liquid-share trades and 0% of illiquid-bond trades. CSDR rates differ per asset class (§9.2: 1.0 bps/day for liquid shares, 0.10 bps/day for liquid sovereign debt). Coverage MUST be per-CSDR-class. Without this, capital and PnL are systematically wrong on the asset class that contributes most to fails.

**G-DS-3: Record-and-replay.** Replay determinism (DS5) is necessary but **insufficient**. A test that records production traffic and replays it will deterministically reproduce production behaviour — including production bugs. The generator catalogue (B-3) must produce **adversarial** traces that have never occurred in production. Otherwise the property tests are documentation, not falsification.

Add a §13.3 explicitly naming these three Goodhart traps with mitigation properties.

---

## Unmitigated Major (M-N)

### M-1. §4 SQL — a bug in this query corrupts PnL silently.

The §4.3 query is a single GROUP BY scan over `position_state JOIN wallet_registry`. Two failure modes:

1. **Wallet-class typo.** A wallet incorrectly classified as `virtual_PS_payable` when it should be `virtual_PSS_payable` (cash vs. securities) silently inflates the cash recon by the security notional. The current query has no cross-check that `unit` matches the expected class. Add a CHECK constraint: `wallet_class IN ('virtual_PS_payable', 'virtual_PS_receivable')` implies `unit ∈ currency_master`; `wallet_class IN ('virtual_PSS_*')` implies `unit ∈ instrument_master`. Without this, a single misclassified wallet corrupts the daily recon and only manifests as a slow-burning PnL drift.

2. **Real-wallet FK collision.** `wr.real_wallet = :w` assumes uniqueness of the real-wallet ID across the registry. If `WalletRegistry` is bitemporal (it should be — KYC sidecar metadata is restated), the query needs to read at a knowledge time. The proposal does not say which `t_known` the recon uses; if it uses "latest", a restatement of `real_wallet` FK during the recon window produces non-deterministic recon outputs.

The catching test: differential test the SQL projection against the CDM forgetful-functor F (B-4.b). A discrepancy is the bug.

### M-2. §5 FSM totality is asserted, not proved (closed-sum proof needed).

§5.3 lists allowed transitions. §5.6 lists 7 observable states. §11 DS8 names monotonicity. But:

- The transition set in §5.3 contains `INSTRUCTED → PARTIALLY_SETTLED → SETTLED | FAILED`, `FAILED → SETTLED | BoughtIn | Defaulted`, `* → CANCELLED`. The cardinality of the transition set is not stated. The closed-sum proof requires: for every (state_in, witness_event) pair, exactly one transition is admitted. The pattern-match in §12.1's `step` function returns `Step | Reject | Idempotent`, which is correct in shape, but **the case enumeration is not produced**.

- The FSM has 7 observable states × ~10 event classes = ~70 `(state, event)` cells. How many are `Step`, how many `Reject`, how many `Idempotent`? Without the table, the FSM is asserted-total, not proved-total. For a system where `lifecycle_stage = "setled"` shipped at a tier-1 firm, asserted-total is not enough.

Add to §5: a transition matrix as a literal table (rows = current state, columns = event class, cells = next state | Reject | Idempotent). Generate the matrix from the type definitions; check it compiles to the same matrix the prose specifies; export it as an artefact.

### M-3. The §3 worked example needs more numerical sanity checks.

Finops corrected one sign error in their Phase 1 §7.7 (acknowledged in §4.2). The Phase 2 worked example has the corrected sign. But:

- The §3.7 PnL computation `PnL_{T+2} = -50` is a single-trace check. It does not prove path-independence; it proves that one path produced the right answer.
- Conservation tables in §3.6 are checked at four states. They are not checked at intermediate states (e.g., between sese.025 arrival and camt.054 arrival in the partial DvP case).
- Sign discipline for **short** trades is mentioned (§7.3.2) but the conservation table is not in §3-style detail. Reviewer would want to see a §3-equivalent for a short sale + recall + buy-in chain to ensure no sign error compounds across the chain.

Add §3.bis: a long-with-cancel example, a short-with-buy-in example, and an FX-funded buy example — each with full conservation tables at every transition. Without this, finops's Phase 1 sign error is one-of, not class-of.

### M-4. The 18 invariants — DS3, DS13, and DS18 are arguably redundant or one is subsumed.

- **DS3 (recon identity)** and **DS13 (recon pair anchoring)** overlap: DS13 says "ledger and external agree on every transaction in a terminal state, and lead-lag is exactly the sum of non-terminal obligations (DS3)". DS13 is DS3-restricted-to-terminals. If DS3 holds at all times, DS13 is implied. The proposal should either (a) merge DS3+DS13 or (b) explain what DS13 catches that DS3 does not.

- **DS18 (DvP atomicity)** is structural and named CRITICAL. The §12 type design enforces it at the type level via `PairedObligation`. If §12 ships, DS18 is structurally guaranteed and cannot be a runtime test. The proposal should mark DS18 as "CT" (compile-time) in the §11 type column — currently marked CT but the proposal does not commit to §12 as a hard requirement; if §12 is optional, DS18 is unwitnessed.

**Single most important invariant.** DS1 (Economic-Exposure-at-T) is the load-bearing one. Every other DS exists to support DS1. If DS1 fails: PnL is wrong, capital is wrong, regulatory reports are wrong, audit fails, and every downstream consumer gets a different answer for "what is your position". The proposal correctly marks it CRITICAL but does not state "DS1 is the single property whose violation invalidates the system". Make it explicit.

### M-5. §12 type design — does it actually prevent the disasters, or is it cosmetic?

The phantom-typed wallet handles + `PairedObligation` are real wins. But three concerns:

- **Witness-laundering through cast.** A type system "prevents" a bug only as far as the cast / `__new__` / reflection escape hatches are also banned. Data spec GT_5 names this; the proposal §12 does not. Add: "no `cast` / `__new__` / reflection on `wallet_handle` outside the constructor module; AST lint fails the build." Without this, `cpty_virtual_wallet wallet_handle` can be constructed from a `real_wallet` by a careless engineer and the type system passes.

- **`PairedObligation` constructed once, consumed once.** The type prevents single-leg discharge. But the proposal does not say `PairedObligation` is **linear** (consumed once). If two handlers can both consume the same `PairedObligation`, the second one's `discharge` call fires on already-discharged legs. Either make `PairedObligation` linear (Rust ownership / OCaml affine type / runtime "consumed" flag) or document the property test that no second-discharge is possible.

- **`ObligationStatus` mutation outside SettlementWorkflow.** DS17 names capability scoping. §12 does not show how the type system enforces that *only* the SettlementWorkflow can call `step` on `lifecycle`. If `step` is a public function, any handler can call it. The phantom-typed writer-capability mechanism (data spec C11) needs to wrap `step` in a capability witness. The proposal mentions DS17 but does not show the type signature.

### M-6. Reproducibility — replay from (seed, snapshot, refdata, inputs) is asserted, not constructed.

DS5 (replay determinism) and Λ_10 (`tx_id = hash_jcs(...)`) commit to determinism. But the proposal does not specify the **seed quadruple** that fully determines the replay:

- (seed_random, snapshot_id, refdata_pin, inputs_log) → state.

Required: a §13 (or §15) section stating: "every state is reproducible from `(L_19_clock_seed, L_12_snapshot_id, L_7^P_version_pin, L_11_external_confirmation_log)`". Without this, "byte-replayable" is faith. Property test: serialise the quadruple, reproduce on a different machine, byte-equal the resulting state.

The data spec says C-A_12 covers erasure-coding but not the replay quadruple. The proposal should commit to the quadruple as the minimal reproducer.

### M-7. Witness-launderer hunt — three places where the type system "passes" but runtime invariant could break.

1. **`Obligation.create` (§12.5) takes 14 rejection cases as its constructor.** It does NOT reject the case where `intended_settlement_date > T_max + safety_margin` (a "settlement date 3 years out" obligation). DS9 (buy-in compensation closure) and Λ_13 (Obligation Liveness) require deadlines bounded by `T_max`. Add rejection 15: `settle_date - trade_date > T_max + safety_margin`.

2. **`Sese_025_msg.t` (§12.2 discharge function).** The type assumes the ISO 20022 message is well-formed at the type level. But `sese.025` is parsed from XML; a malformed XML can construct a `Sese_025_msg.t` whose `RelatedRef` is `null`. The discharge function then dispatches on a null reference. Add: `Sese_025_msg.parse : string -> (Sese_025_msg.t, parse_error) Result.t`; no public unsafe constructor.

3. **The §3 PnL computation uses `× 1.0000` for USD price.** A common bug is `Decimal × float` silently coercing to float and losing precision. §4.6 forbids floats but the §3 example doesn't pin the type of `1.0000`. Add: `Decimal × Decimal` only; `1.0000` must be `D_8(1.0000_0000)`.

---

## Minor (m-N)

**m-1.** §2.4 says transaction-level status is the **MAX projection** under the lattice `Settled > PartiallySettled > Failed > BoughtIn > Instructed > Executed > Cancelled`. But `Cancelled` is at the bottom; the MAX of `(Cancelled, Settled)` is Settled, which is **wrong** — a CANCELLED+SETTLED pair shouldn't exist (CANCELLED is terminal pre-settlement). Either prove the precondition holds or use the lattice carefully. Likely fix: CANCELLED is its own absorbing element (top, not bottom), reachable only via four-eyes CORRECTION pre-settlement.

**m-2.** §2.5 conformance verdict: "PS/PSS pattern adds zero state to StatesHome. No fourth map." Strictly true for PositionState but the proposal adds 4 fields to `WalletRegistry` (`wallet_class`, `real_wallet`, `cpty_lei`, `expected_settle_window`). The conformance claim should be: "zero new fields on PositionState; four new fields on WalletRegistry KYC sidecar permitted per StatesHome §2."

**m-3.** §6.4 partial settlement — the formula `tx_id = hash("FINAL", TX1.tx_id, sese.025_partial_msg, attempt_seq)` puts `attempt_seq` inside the hash, but §11 DS19-equivalent (witness identity) requires `attempt_seq` to be deterministic. What generates `attempt_seq` for partials? §6.4 says "the `attempt_seq` field in the deterministic `tx_id` formula prevents collision between the two partial finality messages" — but does not specify the generator. If `attempt_seq = ordinal_in_partial_chain`, then a CSD that restates partial 1 after partial 2 has shipped collides on `attempt_seq=0`. Pin it to `(intended_partial_seq, ingestion_order_seq)`.

**m-4.** §7.4 recall-during-window — the table at row "T+3 (recall due)" says `B delivers up to avail = -600 + 1000 = 400. Insufficient.` The math is right but the cell "intended" deliverable is 1000 (the full recall) not 400; the "delivered" is 400. The cell-text is ambiguous and would confuse a property-test author writing the generator for this scenario.

**m-5.** §10.4 IFRS 9 ECL table — "CSDR fail extending past contractual settlement date is a **non-rebuttable** Stage 2 trigger." The auditor in me asks: by what authority "non-rebuttable"? IFRS 9 paragraph 5.5.11 allows rebuttal under "reasonable and supportable" evidence. Soften to "presumptive Stage 2, with Stage 1 rebuttal requiring documented evidence." Otherwise an auditor will reject the framework.

**m-6.** §11 DS12 (variant degeneration) — "for all variants, DS1–DS11 hold without modification". This implies DS1–DS11 are independent of the workflow timer, which is true *if* the timer enters only the discharge predicate and not the invariant statement. Verify by inspection: DS5 (replay determinism) names "the same multiset of confirmation messages" — a multiset is a static object, not timer-dependent. DS9 names `Δ_CSDR` — timer-dependent. So DS9 does NOT degenerate; T+0 has no `Δ_CSDR` because there is no fail. Either restate DS9 conditionally or note T+0 makes DS9 vacuous.

**m-7.** §13 PO-9 "D_max" — currently jane_street caps at 2, sbl/temporal allow recursion. The Settlement Team accepted "a bound but has not numerically pinned it." Pin it: D_max = 3 is operationally generous; D_max = 2 is jane_street's pragma. The TLA+ model check (PO-8) needs a number to bound the state space.

**m-8.** §15.1 weakness 1 (sign convention on DS3 / PO-3) — flagged honestly. But §4.1's identity has been corrected. The remaining open is the SBL-composition path (§7.9). Add a property test for that path explicitly.

---

## What works (genuine strengths — credit where due)

1. **The triple representation (§2.1).** Real `own` write at T + PS/PSS contras + L_15 obligation is the cleanest delta-to-v10.3 I have seen. Withdrawing the 7th coordinate (Margaret Chen, Phase 2 §0) is the right call; the rationale (§1 "What was rejected") is pedagogically sound.

2. **§3 worked example as the load-bearing concrete artefact.** Numerical, conservation-checked at every state, signs explicit, decimal types explicit. This is what every framework spec should contain. The §3.6 conservation summary table is exemplary. Two more examples (long-cancel, short-buy-in, FX-funded — see M-3) and §3 is best-in-class.

3. **§5 witness-driven discharge (DS4).** "The framework never marks a leg `Discharged` by inference, by clock, or by absence of evidence." This is the single most important architectural commitment and the proposal makes it correctly. No fail-by-inference is the correctness commitment.

4. **§6.2 T+0 / atomic DLT degeneracy test as the architecture's correctness oracle.** "Hardcoding T+2 is technical debt with a known due date" — yes. The variant-degeneration property (DS12) is the right way to validate that the deferred-settlement representation is parameterised, not architectural.

5. **§7 SBL composition.** The "long that has never owned" example (§7.7) and the prepay-collateral overnight exposure (§7.8) are non-trivial scenarios handled by the same primitives. This is a strong validation of orthogonality (§7.1).

6. **§8 CDM cross-walk with Direct/Partial/Missing.** The 24-element inventory is honest. The 5 strategic gaps (Gap 6/7/8/9/10/11) are correctly identified. The forgetful functor F is the right abstraction.

7. **§12 type design.** `PairedObligation`, phantom-typed wallet handles, newtype dates, smart constructor with 14 rejection cases, accounting-basis phantom types. Each one structurally eliminates a bug class. The honest §12.8 "6 CT / 9 RT / 3 hybrid" boundary is intellectually disciplined.

8. **§13.1 G1–G12 honest gap enumeration with named owners.** The proposal enumerates its own weaknesses with named owners and named property tests. This is the correct adversarial-review-readiness posture.

9. **§15.1 weakness honesty.** Calling out the 8 known weaknesses with named owners and PO links is exactly what a Phase 2 → Phase 3 handoff should look like. Most specs hide weaknesses; this one publishes them.

---

## Recommendation

**ACCEPT_WITH_CHANGES.** Conditional on closing **B-1 through B-6** before Phase 3 Round 2.

Priority ordering for the Settlement Team:

1. **B-1 (property catalogue gaps), B-3 (generator soundness), B-6 (Goodhart traps)** — close together. They are one piece of work: a generator catalogue + 6 new properties + 3 named Goodhart traps. ~2 weeks.

2. **B-2 (non-determinism boundaries)** — one section addition (§11.bis). 2 days.

3. **B-4 (differential oracle)** — define the reference sequential interpreter and the F-homomorphism oracle. 1 week.

4. **B-5 (fault catalogue completion)** — add network split, Byzantine clock, bugification operator. 1 week.

5. **M-1 through M-7** — incremental polish, none architecturally blocking. 1 week.

6. **m-1 through m-8** — copy-edit quality. 1 day.

Total: ~6 weeks of focused work. None of this is redesign. All of it is property-coverage hardening.

**The proposal earns my conditional approval because the architectural choices are sound; my blockers are about making the *test* of the architecture as good as the architecture itself.** The Settlement Team has built the right system. They have not yet built the right witness that the system is correct. That is the Phase 3 Round 2 ask.

**Goodhart's Law explicit warning.** A property-test pass rate of 100% on a generator that produces only liquid-share T+2 buys with same-day matched finality is worth less than a pass rate of 95% on a generator that produces the empirical fail-tail with adversarial restatements and pathological-but-legal CSD partials. Coverage criteria honesty (B-6) is the *real* phase 3 deliverable; everything else is in service of it.

**Single most important property in the catalogue: DS1 (Economic-Exposure-at-T).** Every other DS exists to support it. If you can only run one property test, run DS1.

---

*Reviewer: Correctness Architect. Adversarial focus per review brief. Cross-referenced ledger_data_v1.0.tex (L_15, Λ_13, Φ_15^{T,W,C}, Goodhart trap inventory GT_1–GT_5, witness inventory W_1–W_5).*
