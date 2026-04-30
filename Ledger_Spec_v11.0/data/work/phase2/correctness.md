# Phase 2 — Cross-Layer Correctness Synthesis (Correctness-Architect Stance)

**Author role:** Correctness Architect — end-to-end consistency across the
data layer, the unit store, the executor, the valuation FSM, the settlement
projection, and the obligation/liveness machinery.

**Inputs read:** all 19 Phase 1 enumerations under
`Ledger_Spec_v11.0/data/work/phase1/`. Source corpus
(`ledger_v10.3.tex`, `ledger_v10.3_addendum_stateshome.tex`,
`ledger_valuation_v1.0.tex`) used as tiebreak.

**Remit (Phase 2):** I do not own the master taxonomy (NAZAROV) or
per-leaf invariants (FORMALIS) or per-leaf types (MINSKY). I own the
**laws that span layers** — the consistency obligations whose
preconditions live in one data category and whose postconditions live
in another. I also own the **determinism boundary catalogue**, the
**fault catalogue** that forbids each law's failure mode, the
**property-based testing program** that witnesses the laws, and the
**unwitnessed-law residue** — laws no finite test can decide.

**Convention.** Throughout this document I use the Phase 1 vocabulary
where the panel converged: ProductTerms / UnitStatus / PositionState
(StatesHome 3-map); D1–D10 / F1–F10 / Categories 1–11 are all referring
to the same underlying tiers. I cross-reference Phase 1 enumerations
when the load-bearing data category was first named there.

---

## §1 — Cross-Layer Consistency Laws (the catalogue)

A *cross-layer* consistency law is one whose precondition mentions data
in one category (or layer) and whose postcondition mentions data in
another. I enumerate **fourteen** such laws. Each carries (i)
precondition, (ii) postcondition, (iii) data categories tied together,
(iv) the failure mode forbidden, (v) the witnessing strategy.

The laws are clustered into five groups: **L1–L4 lineage / oracle**,
**L5–L7 conservation / accounting**, **L8–L10 determinism / replay**,
**L11–L12 calibration / valuation**, **L13–L14 settlement / liveness**.

### L1 — Lineage Closure (every committed move has a primary-attested observable in its lineage)

- **Precondition.** A `pending_tx` is emitted by handler $h$ with input
  set $I = (\text{state}, \text{ProductTerms}[u], \text{snapshot})$.
- **Postcondition.** After commit, the transaction's metadata resolves
  every observable referenced in $I$ to a content-addressed
  *attestation envelope* (NAZAROV CC-1, JANE_STREET §4) whose
  `source_signature` was verified at ingestion.
- **Data categories tied.** Market (3), Oracle (4), Settlement
  Infrastructure (7), Calibrated Latent State (8), Smart-Contract
  Execution (5), Provenance (11).
- **Failure mode forbidden.** A *floating* observable: a move whose
  causal antecedent cannot be reproduced (the source was a live feed,
  unsigned, or the envelope was lost). Reduces P9 (path-independence)
  to a vacuous claim.
- **Witnessing.** Property test: for every committed move, the
  recursive closure of `(snapshot_id → observation envelopes)`
  is finite, type-checked, and every leaf has `source_signature`
  verified. **Decidable** under finite move histories.

### L2 — Snapshot Determinism Closure (calibrated state at $t$ reproducible from raw observables at $t$)

- **Precondition.** A `calibrated_state[surface, t, model_version]`
  exists with `certified == True`.
- **Postcondition.** Re-running the calibration pipeline on the
  enclosing `market_snapshot` (D4.3 / F7.3 / 3.2) under the same
  `model_version` produces a posterior $x'_{t|t}$ with
  $\|x'_{t|t} - x_{t|t}\|_{P_{t|t}^{-1}} < \epsilon_{\text{repro}}$ —
  bit-identical when arithmetic is `Decimal` (FORMALIS I16) and
  Mahalanobis-zero when MC-dependent.
- **Data categories tied.** Market (3) ↔ Calibrated Latent State (8) ↔
  Snapshot Store (3.2 / 4 / D4.3).
- **Failure mode forbidden.** *Calibration drift*: the certified
  posterior depends on a state-of-the-pipeline (warm starts, cached
  Hessians, GPU state) that was not itself snapshotted. This is the
  Goodhart trap where "the model passed at certification" but is
  unreproducible later.
- **Witnessing.** Replay test from snapshot. **Decidable** for
  deterministic pipelines; **probabilistic** for MC pipelines (use
  fixed `seed = hash(snapshot_id, unit_id, model_version)`, valuation
  §10.4).

### L3 — Settlement-Move Closure (every settlement instruction maps to exactly one move-stream segment)

- **Precondition.** A `SettlementInstruction` was emitted with
  `tx_id = T` (Category 5.1; ledger §8.1.2).
- **Postcondition.** There exists exactly one transaction $T$ in the
  move stream whose `tx_type ∈ {SETTLEMENT, COLLATERAL}` and whose
  closure under `corrects` covers exactly the moves implementing the
  instruction. Conversely, every settled segment has exactly one
  inbound `external_confirmation` (Category 4.6) bound by
  `end_to_end_id`.
- **Data categories tied.** Smart-Contract Execution (5) ↔ Settlement
  Infrastructure (7) ↔ Oracle (4.6) ↔ Provenance (11.3).
- **Failure mode forbidden.** *Phantom settlement*: instruction was
  enriched and transmitted but the move-stream segment is missing,
  duplicated, or incorrectly attributed (the `end_to_end_id` collides
  across counterparties). Catastrophic for CSDR fail-rate reporting.
- **Witnessing.** Bidirectional generator: from every
  SettlementInstruction, walk to confirmation; from every confirmation,
  walk back to instruction. Cardinality must be exactly 1↔1↔1.
  **Decidable** under finite traces.

### L4 — Bitemporal Coherence (vendor_time ≤ knowledge_time; replay is total over both axes)

- **Precondition.** Any datum $d$ in Categories 2 (Reference), 3
  (Market), 4 (Oracle) carries `(vendor_time, knowledge_time,
  effective_time)`.
- **Postcondition.** $\text{vendor\_time}(d) \le
  \text{knowledge\_time}(d)$, and `read(id, as_of_knowledge=t_k,
  as_of_vendor=t_v)` is total whenever
  $t_k \ge \text{ingestion\_time of registered version}$ for some
  version with vendor time $\le t_v$.
- **Data categories tied.** Reference (2), Market (3), Oracle (4),
  Snapshot (3.2), CDM lineage (1.3).
- **Failure mode forbidden.** *Bitemporal collapse*: replay reads
  "current ISIN" instead of "ISIN as of trade time"; this is
  TEMPORAL.md risk-register row 5 ("PartyReference with bitemporal LEI
  changes — easy to read 'current LEI' instead of 'as-of LEI'").
- **Witnessing.** Hypothesis: generate $(t_{\text{econ}}, t_{\text{know}})$
  pairs across vendor restatements; assert `replay(t_econ; with knowledge
  pinned at t_know1) == replay(t_econ; with knowledge pinned at
  t_know1)` and that the two-axis replay differs from the single-axis
  one only on entries with `knowledge_time` between $t_{\text{know}_1}$
  and $t_{\text{know}_2}$. **Decidable** for finite knowledge
  histories.

### L5 — Per-Event-Class Conservation (StatesHome C2 lifted across every triggering oracle)

- **Precondition.** Any external oracle event (corp action, credit
  event, exercise notice, fixing publication, settlement
  confirmation) admitted by ingestion → handler $h$ generates
  `pending_tx` of class $c$.
- **Postcondition.** For every additive monotone field $f$
  (`accumulated_cost`, `quantity`, `cash_balance`, `nav_index_units`,
  `mandate_units`, `borrow_qty`, ...): $\sum_w \Delta f(w, u) = 0$
  *per* class $c$. The vacuous-zero-holder base case is proven by
  type construction (TESTCOMMITTEE M3, FORMALIS I1 + I8).
- **Data categories tied.** Oracle (4) → Smart-Contract Execution (5)
  → PositionState (D3) → Move stream (D7).
- **Failure mode forbidden.** *Silent absorption*: an oracle event
  produces a move but the conjugate move is omitted or routed to a
  field with no conservation law. Caught structurally if C11
  (single-writer-per-field) is enforced.
- **Witnessing.** Property test on every CDM (ProductType,
  EventIntent) cross product against generators from Category 10
  (CDM enum universe). **Decidable**.

### L6 — Mandate-as-Unit Conservation (StatesHome §4.2 issuance law, lifted across the lifecycle)

- **Precondition.** A managed-account or QIS unit $u_{\text{MA}}$ is
  registered (issuance handler) or has a fee crystallization, breach
  event, or termination.
- **Postcondition.** $w_{\text{manager}}(u_{\text{MA}}) +
  \sum_{c \in \text{clients}} w_c(u_{\text{MA}}) = 0$ at every
  timestamp; per-(w, $u_{\text{MA}}$) fee accruals discharge through
  conjugate moves into `cash_balance` / `fee_reserve` such that
  conservation holds across the boundary.
- **Data categories tied.** ProductTerms (1, mandate text) ↔
  PositionState (5.3, per-(w, $u_{\text{MA}}$) state) ↔ Wallet
  registry (2.9) ↔ Move stream (D7).
- **Failure mode forbidden.** *Cross-mandate HWM collapse*: a single
  per-wallet HWM shared across mandates → fees computed against the
  wrong baseline → revenue leak. (LATTNER §3, FORMALIS I19.)
- **Witnessing.** Property test on mandate generators; assert HWM
  state lives only at PositionState[w, $u_{\text{MA}}$] and that
  fees aggregate to zero against the firm's `fee_reserve` virtual
  wallet. **Decidable**.

### L7 — Per-CCP Conservation Scope (Cat 6.2 / footnote ledger §7.4)

- **Precondition.** Cleared contracts cleared via $\ge 2$ CCPs; per
  (wallet, contract, CCP) PositionState rows exist.
- **Postcondition.** $\sum_w \texttt{ac}(w, u_{@\text{CCP}_i}) = 0$ for
  each CCP $i$ independently; the regulatory aggregation is a strict
  superset (covering EMIR Art. 4 cross-CCP netting recognition).
- **Data categories tied.** Reference (2.7 CCP master) ↔ Listed (6.2
  CCP binding) ↔ PositionState ↔ Move stream.
- **Failure mode forbidden.** *Cross-CCP netting leak*: the
  regulator's reportable netting set is computed against the wrong
  scope; conservation appears global but is mis-attributed.
- **Witnessing.** Generators emit cross-CCP scenarios; assert
  per-CCP closure. **Decidable**.

### L8 — Replay Determinism (the master determinism law)

- **Precondition.** A committed transaction $T$ exists with
  attached `(snapshot_id, terms_version, code_hash, calibration_id,
  workflow_history)`.
- **Postcondition.** Re-executing the same handler against the same
  pinned inputs produces a `pending_tx` $T'$ with `tx_id(T') ==
  tx_id(T)` and bit-identical moves and state deltas.
- **Data categories tied.** Static (1.4 code hash, 1.5 conventions),
  Reference (2 pinned bitemporal), Market (3.2 snapshot), Calibrated
  (8 pinned by id), Orchestration (9.1 workflow history), Provenance
  (11.1 tx_id).
- **Failure mode forbidden.** *Hidden non-determinism*: a wall-clock
  read, a UUID generation, a non-canonical hash, or a mutable global
  read inside a "pure" handler. Defeats P9. (TESTCOMMITTEE M4,
  TEMPORAL §8 risk register.)
- **Witnessing.** Replay every committed transaction; assert
  bit-identical re-emission. **Decidable**.

### L9 — Forgetful-Functor Composition (CDM mapping $F$, ledger §10.4)

- **Precondition.** Two CDM business events $e_1, e_2$ are
  referentially independent (TESTCOMMITTEE cross-cutting property 5).
- **Postcondition.** $F(e_2 \circ e_1) = F(e_2) \circ F(e_1)$ — the
  ledger projection composes; cross-referencing events require an
  explicit ordering token.
- **Data categories tied.** CDM lineage payload (1.3) ↔ Move stream
  (D7) ↔ Idempotency (5.4) ↔ Provenance (11.5 correction chain).
- **Failure mode forbidden.** *Composition order silently flipped*:
  two oracle events arriving out-of-order produce different ledger
  effects than the same events in canonical order. Catches
  late-arriving events that should be CORRECTION-typed.
- **Witnessing.** Hypothesis: generate event pairs and a permutation
  of their arrival order; assert ledger commutativity for independent
  pairs and explicit ordering-token enforcement for dependent pairs.
  **Decidable** for finite traces.

### L10 — Workflow-History Replay Coherence

- **Precondition.** A workflow history $H$ exists for `workflow_id`
  with `latest_event_id = N`.
- **Postcondition.** Replaying the workflow code (pinned at
  `code_hash`) against $H$ and the captured oracle/market activity
  results yields bit-identical decisions, signals, and timer fires
  for every prefix of $H$.
- **Data categories tied.** Orchestration (9.1, 9.2, 9.5) ↔ Static
  (1.4 smart-contract code) ↔ Snapshot (3.2) ↔ Move stream (D7).
- **Failure mode forbidden.** *Workflow-task non-determinism*: code
  reads `time.time()` directly, generates a UUID at workflow level,
  or iterates a Python dict before 3.7 — Temporal aborts but the
  failure surface is silent if the workflow is re-deployed under a
  new code hash. (TEMPORAL determinism risk register.)
- **Witnessing.** Time-travel replay test under simulated worker
  restart; assert byte-equal decision history. **Decidable** under
  pinned code.

### L11 — Calibration / Valuation Model Consistency (valuation Remark 3.13)

- **Precondition.** A `ValuationRecord[u, t, model_id]` exists with a
  paired `SensitivityJacobian[u, t, model_id]` — same model id.
- **Postcondition.** PnL explain residual under the same `model_id`
  satisfies $|R_t| \le \tau_{\text{class}}$ (FINOPS, valuation §7.3),
  AND there is no calibration update at $t$ with `certified == False`
  that was nevertheless used for either record.
- **Data categories tied.** Calibrated (8.1, 8.3) ↔ Valuation Record
  (D5.3) ↔ Sensitivity Jacobian (D5.2) ↔ ProductTerms (1) ↔ Static
  (1.4 model code).
- **Failure mode forbidden.** *Cross-model contamination*: the
  Jacobian comes from one model, the price from another → PnL
  explain decomposition is mathematically meaningless. (CARTAN
  Cat 9c, MATTHIAS, TESTCOMMITTEE F10.)
- **Witnessing.** Property: every (price, jacobian, residual)
  triple shares a `model_id`; the Jacobian recovers price under
  Taylor expansion to second order on small perturbations. Includes
  metamorphic relations: put-call parity, calendar-spread bounds,
  strike homogeneity. **Decidable** within tolerance.

### L12 — No-Arbitrage Admissibility Closure ($\Theta_{\text{AF}}$ projection, valuation §5)

- **Precondition.** A calibration update produced posterior $x_{t|t}$
  with `certified == True`.
- **Postcondition.** $x_{t|t} \in \Theta_{\text{AF}}$
  (no-arbitrage region per `constraint_version`); every downstream
  ValuationRecord computed from $x_{t|t}$ inherits a `model_id` whose
  `arbitrage_free_region_id == constraint_version`. No price
  published at time $t$ using $x_{t-1}$ is allowed if $x_{t-1}$ has
  `certified == False`.
- **Data categories tied.** Calibrated (8.1) ↔ Admissibility (8.3) ↔
  Valuation FSM (9.3) ↔ Pricing DAG (D5.4 / 4b.2).
- **Failure mode forbidden.** *Arbitrage leakage*: a tightened
  constraint set is published but stale calibrations are still
  consumed → fake PnL / hedging error. (NOETHER, MATTHIAS.)
- **Witnessing.** Property: every published price's calibration
  vector lies in the active region; FSM transition T1 (UNPRICED →
  PRICING) is gated on `certified ∧ in-region` and *not* on a stale
  certification flag. **Decidable** for finite constraint families.

### L13 — Obligation Liveness Closure (P21–P23 lifted across the data layer)

- **Precondition.** An `Obligation` $o$ was registered with
  `deadline = t_d` and `discharge_predicate = δ`.
- **Postcondition.** $\forall t > t_d.\ o.\text{state} \in
  \{\text{Discharged}, \text{Compensated}, \text{Defaulted}\}$ — and
  the *evidence* for the chosen terminal state is a transaction in
  the move stream whose `corrects` or `discharges` link resolves to
  $o$.
- **Data categories tied.** Obligation (D8) ↔ Move stream (D7) ↔
  Orchestration (9.2 durable timer) ↔ Provenance (11.5 correction
  chain) ↔ Oracle (4 — discharging confirmations).
- **Failure mode forbidden.** *Silent default*: timer fires, no
  discharge move emitted, obligation rotted in `Pending` past
  deadline. The "vacuously satisfied with zero obligations" Goodhart
  trap (KARPATHY) is closed by demanding a registered obligation per
  schedule entry.
- **Witnessing.** Property over time-bounded simulations: after
  injecting deadline-elapse, every registered obligation reaches a
  terminal state within bounded clock advance. **Bounded-decidable**
  for finite time horizons; see §5 for the unbounded subtlety.

### L14 — Capability-Scope Closure (StatesHome C4 lifted across reads, writes, and replays)

- **Precondition.** A capability set $\mathcal{C}$ is granted to a
  reader / writer at time $t$ (Category 2.9 wallet registry, D10).
- **Postcondition.** Every read of a `(w, u)` PositionState row, every
  write of a `(w, u)` field, and every replay query is gated on
  $\mathcal{C}_t$ at that timestamp; cross-(w, $u_{\text{MA}}$)
  overlay reads are forbidden unless an explicit overlay capability
  is present.
- **Data categories tied.** Wallet registry (2.9) ↔ PositionState
  (D3) ↔ Move stream (D7, capability check audit) ↔ Orchestration
  (9 retry policy must respect capability denial as non-retryable).
- **Failure mode forbidden.** *Capability bypass on replay*: replay
  queries circumvent capability scope because they "are not
  production" — Goodhart trap. Replay must demonstrate the same
  audit envelope as production.
- **Witnessing.** Generators include capability-shifted operators;
  assert deny on out-of-scope reads even at replay time. **Decidable**.

---

## §2 — Determinism Boundary Catalogue

A *determinism boundary* is any place external/non-deterministic input
enters the system. For each boundary I name (i) the entry point,
(ii) where the boundary is drawn (i.e., what content-addressed object
captures it), (iii) what replay looks like across it. **Every
boundary in this list MUST be injectable in the simulation harness.**

### B1. Wall-clock reads (`now()`)

- **Entry points:** Temporal `workflow.Now()`, executor's `commit_at`,
  oracle ingestion's `received_at`.
- **Boundary captured by:** A `Clock` interface whose only
  implementation in production is monotonic, in tests is virtual
  (`HypothesisClock`). The clock's *output value* is recorded in
  workflow history (Category 9.1), the move stream's `committed_at`,
  and snapshot metadata.
- **Replay:** Read clock value from history, never call wall-clock at
  replay.

### B2. Random / entropy reads (MC pricers, UUID generation)

- **Entry points:** valuation MC pricers, RFQ id generation, simulated
  fault injection.
- **Boundary captured by:** `seed = hash(snapshot_id, unit_id,
  model_version)` (valuation §10.4); UUIDs derived from `tx_id` (no
  raw `uuid4()` allowed in handlers or workflows).
- **Replay:** Same `tx_id` ⇒ same UUID; same snapshot ⇒ same MC seed.

### B3. External price / FX / vol feeds (Categories 3.1–3.7)

- **Entry points:** Activity calls to vendor feeds.
- **Boundary captured by:** `MarketSnapshot` content-addressed bundle
  (3.2 / NAZAROV CC-2). The activity returns `(snapshot_id,
  payload)`; only the snapshot id is memoised in workflow history;
  the payload is read from the snapshot store.
- **Replay:** Reconstruct payload via snapshot store key. Snapshot
  store must outlive the longest-tenor unit (TEMPORAL §14: 30 years
  for some bonds).

### B4. External event oracles (Categories 4.1–4.6)

- **Entry points:** Activity calls to ISDA DC, OFAC, ANNA, custodian
  endpoints.
- **Boundary captured by:** Attestation envelope (NAZAROV CC-1) +
  signature verification at gateway. `OracleAttestation` is part of
  the snapshot for the lifecycle invocation that consumed it.
- **Replay:** Read envelope from immutable store; reverify signature
  against the historical key registry (D10.3, FORMALIS).

### B5. Reference data (Categories 2.1–2.10)

- **Entry points:** GLEIF, ISO 4217, ANNA, exchange rulebooks, vendor
  reference feeds.
- **Boundary captured by:** Reference adapter that records every read
  as a versioned, bitemporal envelope (FORMALIS D1.3,
  TEMPORAL bitemporal subset).
- **Replay:** `read(id, as_of_knowledge=t_k)` returns the version
  that was authoritative at `t_k`; vendor restatements create new
  knowledge-time versions, never overwrite.

### B6. Settlement infrastructure (Category 7)

- **Entry points:** SSI lookup, ISO 20022 outbound transmission,
  custodian confirmation inbound.
- **Boundary captured by:** Boundary-mocked enrichment service in
  simulation; in production, a single proxy that records the
  `enrich(...)` envelope under content addressing for replay.
- **Replay:** SSI lookup deterministically returns the version
  effective at `tx.settlement_date`; outbound message bytes are
  reproducible from `(tx_id, leg_index)`.

### B7. Calibration filter state (Category 8)

- **Entry points:** Kalman filter, sensitivity Jacobian computation.
- **Boundary captured by:** `calibrated_state[ref, t,
  model_version]` content-addressed checkpoint with full
  `(x_{t|t}, P_{t|t}, certified, ar_region_id)`.
- **Replay:** Re-run the filter from the prior checkpoint with the
  same observation envelopes — produces bit-identical posterior under
  Decimal arithmetic; Mahalanobis-zero within MC tolerance otherwise.

### B8. Workflow scheduling (Category 9)

- **Entry points:** Temporal worker, durable timer fires, retry
  policy decisions.
- **Boundary captured by:** `WorkflowHistory` (9.1) and Temporal's
  own determinism contract (TEMPORAL §1).
- **Replay:** Temporal replay engine reconstructs decisions from
  history; non-determinism is detected and aborts the workflow task
  (the framework itself enforces this — but only if the workflow
  code respects the Temporal determinism rules).

### B9. CDM enum universe (Category 10)

- **Entry points:** CDM library version pinning at trade time, at
  handler version, at test run.
- **Boundary captured by:** `cdm_version` pinned per workflow input
  and per snapshot; new enum values force a co-versioned handler /
  generator update (TESTCOMMITTEE cross-cutting 3).
- **Replay:** Pinned `cdm_version` per execution; mapping layer
  rejects unknown enums (NAZAROV CC-6).

### B10. Hash algorithm / canonicalisation (Category 11)

- **Entry points:** `tx_id` derivation, hash chain, end-to-end id.
- **Boundary captured by:** Algorithm-stable canonicalization rule;
  algorithm choice and version in every hash (`{algorithm: HashAlgEnum,
  value: bytes, inputs_canonical_form_version}`).
- **Replay:** Canonicalisation is byte-deterministic; algorithm
  rotation is a versioned event (the new chain co-exists with the
  old; no in-place rehashing).

### B11. Operator / human interaction (NEW — flagged but absent in Phase 1)

- **Entry points:** Voluntary corporate-action elections, exercise
  decisions, manual amendments, governance approvals.
- **Boundary captured by:** Signed governance attestation envelope
  (NAZAROV §F) recording `(decision, signer, signed_at, evidence)`;
  the *attestation* is the snapshotted input — not the act of
  deciding.
- **Replay:** The captured attestation is replayed; the human's
  *uncaptured deliberation* is not. **This is the only B-boundary
  whose replay is fundamentally a property of the captured envelope,
  not of the source.**

### B12. Network / message reordering (NEW — flagged but absent in Phase 1)

- **Entry points:** Inbound oracle / settlement messages may arrive
  out of order; outbound transmission may be retried.
- **Boundary captured by:** `(idempotency_token, source_publication_time,
  ingestion_time)` triple. Late-arriving messages are timestamped at
  *both* their source-publication time (economic) and ingestion time
  (booking) and routed through the late-event policy (TEMPORAL
  bitemporal property).
- **Replay:** Messages are replayed in *ingestion-time* order,
  *not* publication-time order, to preserve the original system's
  causal graph; out-of-order publication is reconstructed from
  metadata.

**Boundary count: 12.** Anything outside this list reaching a handler
or workflow is a **non-deterministic boundary I have failed to
enumerate** — Phase 3 must close any gap.

---

## §3 — Fault Catalogue per Data Cluster

I cluster the 11 Phase-1 categories into **seven fault clusters**
(grouping by shared fault profile and shared recovery posture). For
each cluster, every fault class is mapped to the law it breaks, the
detection mechanism, and the recovery posture.

The standard taxonomy is: **missing**, **late**, **duplicated**,
**contradicted**, **mis-attributed**, **silent-corruption**, plus
**partition** (the network/availability dual that is implicit in the
others but worth tracking).

### Cluster I — Identity & ProductTerms (Cat 1, 2.1–2.6, 11)

| Fault | Law broken | Detection | Recovery |
|---|---|---|---|
| missing | L1, L4 | Resolution failure at executor read | Block tx; re-load from authoritative master; emit ALERT |
| late | L4 | Bitemporal coherence check | Apply post-fact under new knowledge-time; `corrects` if conflict |
| duplicated | L1, L8 | UTI/UnitId uniqueness check | Reject second registration; ALERT |
| contradicted | L4, L1 | Cross-source aggregation (NAZAROV CC-3) | Quarantine; route to manual reconciliation |
| mis-attributed | L1, L7 | Closure-of-references audit | Compensating transaction (CORRECTION); replay verifies |
| silent-corruption | L8, L1 | Hash chain (P4); content-addressing | Detect at next chain verification; surgical replay from last good |
| partition | L1 | Gateway heartbeat | Read-only mode; freeze new registrations |

### Cluster II — Calendars, Conventions, Day-Count (Cat 1.5, 2.3, 2.4, 3.7)

| Fault | Law broken | Detection | Recovery |
|---|---|---|---|
| missing | L13 (timer never schedules) | Schedule projection refuses to emit `Obligation` | Block trade booking; load calendar |
| late | L13 (emergency closure) | Bitemporal version mismatch on replay | CORRECTION transactions for any mis-dated payments |
| duplicated | L4 | Cross-source calendar disagree | Aggregation rule (CC-3) picks primary; flag |
| contradicted | L4 | Cross-vendor diff | Quarantine + manual; emergency closures route through governance attestation |
| mis-attributed | L5, L13 | Convention test (idempotent bday-adjust) | Replay with corrected calendar; CORRECTION |
| silent-corruption | L8 | Hash chain on the calendar bundle | Replay from last good |
| partition | — | — | Calendars are slow-moving; cached copies serve indefinitely |

### Cluster III — Market Observables (Cat 3.1–3.6, 3.7 fixings)

| Fault | Law broken | Detection | Recovery |
|---|---|---|---|
| missing | L11, L12 | Snapshot capture refuses; FSM enters `Stale` (val §6.5) | Wait + retry; degraded calibration; ALERT |
| late | L4 (replay-time) | Bitemporal mismatch | Vendor-correction snapshot; both axes preserved |
| duplicated | L8 | Snapshot deduplication on content hash | Idempotent ingestion |
| contradicted | L11 | Innovation gating ($\chi^2$, val §5.5) | Down-weight or reject; log innovation record (8.2) |
| mis-attributed | L1 | Synonym mapping closure check | Mapping-version pinning; CORRECTION |
| silent-corruption | L8 | Snapshot store integrity | Re-fetch from source; replay |
| partition | — | Heartbeat + data-quality flag | FSM transitions to `Stale`; haircuts applied; obligations escalate |

### Cluster IV — Oracle / External Event Attestations (Cat 4)

| Fault | Law broken | Detection | Recovery |
|---|---|---|---|
| missing | L9, L13 | Obligation deadline check; reconciliation against issuer schedule | ALERT; manual; if proven missed, CORRECTION transaction |
| late | L4, L9 | Source-publication-time vs ingestion-time delta | Late-event policy (CORRECTION if material; otherwise apply post-fact) |
| duplicated | L9 | Idempotency token (5.4) | Reject; idempotent commit |
| contradicted | L9 | DC re-decision; DTCC supersedes | New attestation `supersedes` link; CORRECTION chain (11.5) |
| mis-attributed | L1 | Issuer / event identity re-resolution | CORRECTION |
| silent-corruption | L1 | Signature verification | Reject; ALERT |
| partition | L13 | Heartbeat per oracle | Liveness budget: define max_silence beyond which obligations escalate |

### Cluster V — Smart-Contract Execution & Move Stream (Cat 5, D7)

| Fault | Law broken | Detection | Recovery |
|---|---|---|---|
| missing | L5, L8 | Workflow-history says emit, move-stream says no | Re-emit (idempotent on `tx_id`) |
| late | L8 (post-commit emit) | committed_at vs economic timestamp delta | Acceptable up to threshold; beyond, treat as silent default and escalate |
| duplicated | L5, L8 | `tx_id` uniqueness | Idempotent reject |
| contradicted | L8 | Two replicas emit different bytes for same input | Hard fault: purity violated; quarantine workflow; halt class of handler |
| mis-attributed | L5, L7 | Conservation per scope check | Compensating moves; explicit CORRECTION |
| silent-corruption | L8 | Hash chain (Invariant 4) | Detect on chain verification; surgical replay |
| partition | L8 | Worker / DB heartbeat | Idempotency + Temporal retry policy ensures eventual emit |

### Cluster VI — Calibration Latent State (Cat 8)

| Fault | Law broken | Detection | Recovery |
|---|---|---|---|
| missing | L11, L12 | FSM enters `Stale` or `Failed`; no cert | Block dependent prices; ALERT |
| late | L4, L11 | Calibration ID timestamp vs snapshot timestamp | Acceptable if within freshness contract; else degrade |
| duplicated | L11 | Two `certified` posteriors at same `(ref, t, model_version)` | Split-brain — hard fault; quarantine |
| contradicted | L11 | Cross-asset coherence (val §5.8) | Down-weight conflicting observations; log |
| mis-attributed | L11 | Surface ref / curve ref mismatch | Reject; emit ALERT |
| silent-corruption | L11, L12 | $\Theta_{AF}$ projection check | Re-project; recertify; otherwise mark uncertified |
| partition | L11 | Filter heartbeat | FSM `Stale`; prudential haircuts |

### Cluster VII — Orchestration / Settlement / Obligations (Cat 7, 9, D8)

| Fault | Law broken | Detection | Recovery |
|---|---|---|---|
| missing | L13 | Timer / saga pending → terminal not reached | Compensation path; ALERT |
| late | L13 | Deadline elapsed | Compensation OR Defaulted state; the choice is policy |
| duplicated | L3, L13 | `end_to_end_id` uniqueness; `idempotency_token` | Idempotent reject |
| contradicted | L3 | Two confirmations disagree | Quarantine; manual reconciliation; CORRECTION |
| mis-attributed | L3 | Bidirectional walk fails | CORRECTION |
| silent-corruption | L10 | Workflow-task non-determinism abort | Halt; investigate code path |
| partition | L3, L13 | Custodian / CSD heartbeat | Saga compensation; obligation escalation |

**Total fault rows:** 7 clusters × 7 fault classes = **49 fault rows**.
Several rows are *type-prevented* (e.g., `tx_id` collision under
strong canonicalisation has near-zero frequency); none is therefore
omitted, because zero-frequency faults are precisely where Goodhart
traps form ("we have never seen one, therefore we don't test for one").

---

## §4 — Property-Based Testing Program

I refine the TESTCOMMITTEE and GROTHENDIECK proposals into a single
property-test catalogue covering the 14 cross-layer laws. Each law
maps to one or more property tests, named generators, and a verdict
oracle.

### §4.1 Generators

The closed generator universe (Category 10) enumerates:

- `gen_unit_id`, `gen_product_terms` (per CDM ProductType ×
  EventIntent matrix; TESTCOMMITTEE F2)
- `gen_party_master` (random LEI w/ check-digit; recorded-replay
  GLEIF fixture)
- `gen_calendar` (random + canonical-bundle fixture)
- `gen_quote`, `gen_market_snapshot`, `gen_fx_rate`,
  `gen_curve_observables`, `gen_vol_observables`,
  `gen_credit_observables`
- `gen_corp_action`, `gen_credit_event`, `gen_compliance_event`,
  `gen_settlement_confirmation`
- `gen_calibrated_state` (martingale-property + admissibility-region
  generator; rejection-sample to stay in $\Theta_{AF}$)
- `gen_workflow_history` (Temporal-shaped — bounded length, with
  injected timer fires and signals)
- `gen_pending_tx` (stratified by `tx_type`)
- `gen_capability_set`, `gen_wallet_pair`
- `gen_obligation` (with deadline, discharge_predicate,
  compensation_action triple)

### §4.2 Properties (one per law, plus invariant lifters)

Below: Hypothesis-style sketches.

**P-L1 — Lineage closure.** ```
@given(tx=gen_committed_tx())
def test_lineage_closure(tx):
    envelopes = walk_lineage(tx)
    assert envelopes != []
    for env in envelopes:
        assert env.signature_verified()
        assert env.snapshot_id is not None
```

**P-L2 — Snapshot determinism (calibration).** ```
@given(snap=gen_market_snapshot())
def test_calibration_replay(snap):
    cs1 = calibrate(snap, model_version="v1.0")
    cs2 = calibrate(snap, model_version="v1.0")
    assert mahalanobis(cs1.x, cs2.x, cs1.P) < EPS
```

**P-L3 — Settlement-move closure.** ```
@given(tx=gen_committed_tx_with_settlement())
def test_settlement_one_to_one(tx):
    instr = tx.settlement_instruction
    confirms = ledger.confirms_for(end_to_end_id=instr.e2e_id)
    assert len(confirms) <= 1
    if confirms:
        assert confirms[0].tx_id_ref == tx.tx_id
```

**P-L4 — Bitemporal coherence.** ```
@given(d=gen_bitemporal_datum(), t_v=times(), t_k=times())
def test_bitemporal_replay(d, t_v, t_k):
    if t_v <= t_k:
        v = read(d.id, as_of_knowledge=t_k, as_of_vendor=t_v)
        v2 = read(d.id, as_of_knowledge=t_k, as_of_vendor=t_v)
        assert v == v2
```

**P-L5 — Per-class conservation (lifted across oracle events).** ```
@given(ev=gen_oracle_event(), hist=gen_state())
def test_conservation_per_class(ev, hist):
    tx = handler_for(ev)(hist, ev)
    for f in MONOTONE_FIELDS:
        assert sum(d.delta(f) for d in tx.state_deltas) == 0
```

**P-L6 — Mandate-as-unit conservation.** ```
@given(m=gen_mandate(), trades=lists(gen_mandate_lifecycle_event()))
def test_mandate_zero_sum(m, trades):
    state = apply_all(trades)
    units = sum(state.position(w, m.unit_id) for w in state.wallets)
    assert units == 0
```

**P-L7 — Per-CCP conservation.** ```
@given(u=gen_cleared_unit(), trades=lists(gen_cleared_trade()))
def test_per_ccp_zero_sum(u, trades):
    state = apply_all(trades)
    for ccp in u.ccps:
        s = sum(state.acc_cost(w, u, ccp) for w in state.wallets)
        assert s == 0
```

**P-L8 — Replay determinism.** ```
@given(tx=gen_committed_tx())
def test_replay_bit_identical(tx):
    rerun = handler_replay(tx.handler, tx.inputs_pinned)
    assert tx.tx_id == content_hash(rerun.moves + rerun.deltas)
    assert rerun.moves == tx.moves and rerun.deltas == tx.deltas
```

**P-L9 — Forgetful composition.** ```
@given(e1=gen_event(), e2=gen_event())
def test_F_composition(e1, e2):
    assume(referentially_independent(e1, e2))
    assert F(compose(e2, e1)) == compose(F(e2), F(e1))
```

**P-L10 — Workflow history coherence.** ```
@given(h=gen_workflow_history())
def test_workflow_replay(h):
    decisions1 = replay_workflow(h, code_hash=h.code_hash)
    decisions2 = replay_workflow(h, code_hash=h.code_hash)
    assert decisions1 == decisions2
```

**P-L11 — Calibration / valuation model consistency (incl. metamorphic).** ```
@given(u=gen_option(), pert=gen_perturbation())
def test_put_call_parity(u, pert):
    v_call = price(u.as_call(), pert.snapshot)
    v_put  = price(u.as_put(),  pert.snapshot)
    F = forward_price(u.underlying, u.expiry, pert.snapshot)
    K = u.strike
    discount = df(u.expiry, pert.snapshot)
    assert abs((v_call - v_put) - discount * (F - K)) < EPS
```
(Plus: calendar-spread non-negativity, strike homogeneity for European
vanillas, Jacobian-recovers-Taylor-expansion-to-2nd-order.)

**P-L12 — Admissibility closure.** ```
@given(cs=gen_calibrated_state())
def test_certified_in_region(cs):
    if cs.certified:
        assert in_region(cs.x, cs.ar_region_id)
```

**P-L13 — Obligation liveness (bounded).** ```
@given(o=gen_obligation(), env=gen_simulation_horizon())
def test_obligation_terminates(o, env):
    sim = run_until(env, deadline=o.deadline + env.compensation_window)
    final = sim.obligation_state(o.id)
    assert final in {Discharged, Compensated, Defaulted}
```

**P-L14 — Capability scope.** ```
@given(c=gen_capability_set(), q=gen_query())
def test_capability_gate(c, q):
    expected_allow = q.scope.subseteq(c.granted)
    actual = ledger.read(q, capability=c)
    assert (actual is not Denied) == expected_allow
```

### §4.3 Cross-cutting (lifted) properties

These are checked once per *committed transaction*, not per generator
input — they are universal regardless of test scenario:

- `P-CCC-1` Hash chain integrity (Invariant 4).
- `P-CCC-2` Per-class conservation (C2 enforced).
- `P-CCC-3` Single-writer-per-field (C11).
- `P-CCC-4` Single-coordinate-per-move (Principle §15.2).
- `P-CCC-5` `from != to` and `quantity > 0` per move.
- `P-CCC-6` `tx_id == content_hash(canonical(moves || deltas))`.

These are continuously verified — every committed tx contributes a
data point.

### §4.4 Mutation operator set (refines TESTCOMMITTEE M1–M10)

Mutation testing exercises the property catalogue. The minimum
operator set, ranked by expected kill rate against the 14 laws:

1. M-CONS: flip sign on a delta in a state_delta (kills L5–L7).
2. M-BOUND: flip `<` ↔ `≤` on FSM / freshness boundary (kills
   L11–L13).
3. M-VACUOUS: drop the empty-holder-set base case in conservation
   proof (kills L5).
4. M-CLOCK: insert `time.time()` in a handler or workflow (kills
   L8 / L10).
5. M-CACHE: cache an adjusted date / first-touch (kills L4 / L13).
6. M-NOPROJ: skip $\Theta_{AF}$ projection on Kalman update (kills
   L12).
7. M-CANON: alter canonicalisation (whitespace / key order) on hash
   construction (kills L8 / L9 — same tx, two hashes).
8. M-CDM: silently accept unknown enum value (kills L9 / cross-cutting).
9. M-CAP: skip capability check (kills L14).
10. M-LATE: ingest a late oracle event without setting late-flag
    (kills L4 / L9).

Mutation-score targets: **80% overall, 90% on event handlers**, per
addendum §6 — applied to the surviving categories from
TESTCOMMITTEE §"What survives a refactor."

---

## §5 — The Unwitnessed-Event Problem

Some laws above are *not witnessed by a finite test*: no terminating
program can decide whether they hold over the system's life. These
must be flagged, given a degraded surrogate property, and explicitly
documented as residual risk.

I find **four** unwitnessed (or weakly witnessed) laws.

### U1 — L13 obligation liveness over unbounded futures

**Why unwitnessed:** L13 states that for *every* obligation $o$ with
deadline $t_d$, eventually $o$ reaches a terminal state. In a 30-year
bond with deferred coupons, the closure horizon exceeds any test
horizon. A finite simulation can witness the *bounded* version (P-L13
above with `env.compensation_window`), but not the *true* statement.

**Surrogate.** Two layered surrogates, each finite:
1. *Time-bounded*: every obligation reaches terminal within
   `deadline + max(compensation_horizon, escalation_horizon)`. Witness
   by simulation with virtual clock.
2. *Inductive*: prove by structural induction on the obligation type
   that the discharge predicate is total at the deadline (every
   reachable state has a terminal successor). This is a *type-system*
   witness, not a test witness; FORMALIS I10 captures it.

**Residual risk.** The system might be *operationally correct* yet a
particular real-world obligation falls outside the simulated horizons
because of an uncaptured compensation primitive. Mitigation: the
obligation-store invariant is *also* checked at runtime as a periodic
audit (the freshness-map analogue for liveness).

### U2 — L4 bitemporal coherence under unbounded vendor restatement chains

**Why unwitnessed:** A vendor may issue an arbitrary chain of
restatements (`v1 → v2 → v3 → ...`); the law states that replay is
total over both axes for the entire chain. Tests bound the chain
length; the true statement is over $\omega$.

**Surrogate.** Bounded-length restatement chains (Hypothesis fuzzes
to ~100 deep). Operational guard: each restatement is itself a
versioned, attested envelope; the mapping is total over the *currently
known* versions. Periodic audit verifies bitemporal closure for
every datum touched in the audit window.

**Residual risk.** A poison restatement that arrives many years after
the original observation may break replay if the snapshot store has
been compacted. Mitigation: snapshot retention horizon must exceed
the longest-tenor unit (TEMPORAL §14).

### U3 — L1 lineage closure under undisclosed sources

**Why weakly witnessed:** L1 is decidable for the *modelled* lineage,
but cannot detect a source that was deliberately hidden — a vendor
internally aggregating multiple sub-vendors and presenting a single
attestation envelope. The test sees an envelope; it cannot see *into*
it.

**Surrogate.** NAZAROV CC-7 (trust-assumption registry) and CC-8
(threat model class "Malicious vendor"). Each named source carries
a documented trust assumption with explicit *violation
consequence* and *detection signal*. The test cannot prove the
trust assumption holds; it can only prove that *if* the registry is
truthful, *then* the lineage closes.

**Residual risk.** Boundary-of-the-world: trust must be asserted
somewhere. Mitigation: multi-source aggregation (CC-3) where
feasible; innovation-gating downstream (Cluster III) catches a
lying vendor whose data is statistically inconsistent with peers
(but not one whose lies are within the gating threshold).

### U4 — L8 replay determinism under cosmic-ray / silent-bit-flip

**Why weakly witnessed:** L8 holds against modelled non-determinism
(clocks, randomness, ordering). It cannot witness a single-bit-flip
in stored data between commit and replay. The hash chain (P-CCC-1)
detects the flip *if* it lands in chained territory; but a flip
inside a snapshot blob outside the chain may go undetected.

**Surrogate.** Content-addressing covers everything that is read:
a snapshot's content hash is chained into the move that consumed it.
Periodic full re-hash verifies storage integrity end-to-end.
Erasure-coded storage at the persistence layer reduces probability
to operational tolerance.

**Residual risk.** Probabilistic, bounded by storage-integrity
failure rate × replay frequency. Mitigation: cross-replica content-
hash verification on every read.

### Summary table of unwitnessed laws

| ID | Law | Why unwitnessed | Surrogate | Residual risk class |
|---|---|---|---|---|
| U1 | L13 (liveness) | Unbounded time horizon | Bounded-horizon test + structural induction (FORMALIS I10) | Low — type system covers it; runtime audit detects late drift |
| U2 | L4 (bitemporal) | Unbounded restatement chains | Bounded-chain test + retention horizon | Low — operationally bounded |
| U3 | L1 (lineage) | Vendor opacity | Trust registry (CC-7) + threat model (CC-8) + multi-source consensus | Medium — trust assumption is the boundary |
| U4 | L8 (replay determinism) | Hardware faults | Content addressing + erasure coding + cross-replica verification | Low — probabilistic, mitigated |

**Count: 4 unwitnessed (or weakly witnessed) laws out of 14.**

The remaining 10 laws (L2, L3, L5, L6, L7, L9, L10, L11, L12, L14)
are witnessed by finite property tests under the generators in §4.

---

## §6 — Goodhart Traps Specific to the Data Layer

I document four Goodhart traps that the data team should explicitly
guard against — situations where optimising a metric will produce
locally-passing tests at the cost of actual correctness:

1. **"Snapshot coverage = 100%"** — every transaction has a snapshot
   id, but the snapshot store has been silently swapped for a
   stub that returns a constant. Mitigation: P-L8 demands
   *byte-identical* replay, not "snapshot exists".

2. **"Mutation score is high"** — but the mutation set excludes M-CDM,
   M-CANON, or M-LATE. Mitigation: TESTCOMMITTEE M1–M10 plus my
   M-CAP / M-LATE / M-NOPROJ are mandatory operators.

3. **"Property catalogue is large"** — but the generators are biased
   toward common cases. Mitigation: stratified generators per CDM
   ProductType × EventIntent matrix (TESTCOMMITTEE F9.2); coverage
   measured against the matrix, not the test count.

4. **"Conservation passes everywhere"** — but conservation is checked
   over an aggregate that *averages out* a violation in one
   sub-scope. Mitigation: per-(scope) conservation (L7 per-CCP, L6
   per-mandate, C2 per-event-class); any aggregation MUST be
   accompanied by the per-scope check.

---

## §7 — Recommendations to NAZAROV / FORMALIS / MINSKY

For Phase 3 convergence, I cross-reference my cross-layer laws to
the master taxonomy / per-leaf invariants / per-leaf types as
follows:

- **NAZAROV master taxonomy**: structurally compatible with my
  cluster groupings (§3). My Cluster IV (Oracle) maps to NAZAROV's
  expanded Floor 4 (D / "External event attestations"). Recommend
  NAZAROV adopt the 7-cluster fault structure as a presentation
  axis orthogonal to the 6 floors.

- **FORMALIS per-leaf invariants**: my 14 cross-layer laws are
  *consequences* of FORMALIS I1–I20 + cross-leaf composition. Where
  FORMALIS asserts I-invariants per tier, I assert L-laws across
  tiers. Recommend FORMALIS treat my L-laws as *theorems* derived
  from his I-axioms, with the proof obligation explicit per law.

- **MINSKY per-leaf types**: my generators (§4.1) are inhabitants of
  MINSKY's typed schemas. Recommend MINSKY publish per-tier type
  signatures *with* generator stubs to keep the type space
  property-testable, not merely well-typed.

---

## §8 — Closing

The 14 cross-layer laws are the **load-bearing claim** of the data
layer: every guarantee the framework offers (atomicity, conservation,
determinism, time-travel, value invariance under deterministic
lifecycle, regulatory reconstruction) is a corollary of one or more
of L1–L14. The 12-boundary catalogue is the determinism-discipline
contract — every boundary captured, every replay total. The 49-row
fault catalogue is the adversarial budget — every fault cataloged,
detected, and recovered. The four unwitnessed laws are the residual
risk envelope — each surrogated, each documented.

I hold the boundary across layers. Phase 3 arbitration may rename
or re-cluster these laws; it may not drop one without explicit
demonstration that the failure mode it forbids is structurally
unreachable.

— end of Phase 2 cross-layer correctness synthesis —
